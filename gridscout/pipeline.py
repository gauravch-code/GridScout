"""Public downloads and audited cleaning. All distance-ready outputs use EPSG:3083."""
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely import make_valid, normalize

from .settings import read_config

LOG = logging.getLogger(__name__)
CRS = "EPSG:3083"  # NAD83 / Texas Centric Albers Equal Area, units meters


class Audit:
    def __init__(self):
        self.events = []

    def record(self, dataset, reason, count):
        self.events.append({"dataset": dataset, "reason": reason, "count": int(count)})
        LOG.info("%s: %s = %s", dataset, reason, count)


def checked_json(url, params):
    response = requests.get(url, params=params, timeout=(15, 120))
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"ArcGIS error: {data['error']}")
    return data


def download_file(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    temporary = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=(15, 120)) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                output.write(chunk)
    if not zipfile.is_zipfile(temporary):
        temporary.unlink(missing_ok=True)
        raise ValueError(f"Expected a ZIP archive from {url}; check config/sources.json")
    temporary.replace(path)
    return path


def download_transmission(url, path):
    """Use object-ID batches so ArcGIS record limits cannot truncate silently."""
    path = Path(path)
    if path.exists():
        return path
    metadata = checked_json(url, {"f": "json"})
    names = {field["name"] for field in metadata["fields"]}
    if "VOLTAGE" not in names:
        raise ValueError("Transmission service no longer exposes VOLTAGE")
    query = url.rstrip("/") + "/query"
    # Deliberately wider than Texas: exact 25 km buffer filtering occurs after projection.
    ids = checked_json(query, {"f": "json", "where": "1=1", "geometry": "-107,25,-92,37",
                              "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                              "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true"})
    object_ids = sorted(ids.get("objectIds") or [])
    if not object_ids:
        raise ValueError("Transmission query returned no features")
    features = []
    # Keep GET URLs under common proxy limits even for long object IDs.
    batch_size = min(100, metadata.get("maxRecordCount", 100))
    for start in range(0, len(object_ids), batch_size):
        batch = object_ids[start:start + batch_size]
        data = checked_json(query, {"f": "geojson", "objectIds": ",".join(map(str, batch)),
                                   "outFields": "*", "outSR": 4326, "returnGeometry": "true"})
        if data.get("exceededTransferLimit") or len(data.get("features", [])) != len(batch):
            raise ValueError("ArcGIS returned an incomplete batch; no partial dataset saved")
        features.extend(data["features"])
        LOG.info("Fetched transmission %d/%d", len(features), len(object_ids))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    path.with_suffix(".metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return path


def prepare_geometry(frame, dataset, allowed, audit):
    if frame.crs is None:
        raise ValueError(f"{dataset}: missing CRS; provide a properly attributed source")
    frame = frame.copy()
    bad = frame.geometry.isna() | frame.geometry.is_empty
    audit.record(dataset, "dropped_missing_or_empty_geometry", bad.sum())
    frame = frame.loc[~bad].copy()
    invalid = ~frame.geometry.is_valid
    audit.record(dataset, "repaired_invalid_geometry", invalid.sum())
    frame.geometry = frame.geometry.map(make_valid)
    good = frame.geometry.geom_type.isin(allowed) & ~frame.geometry.is_empty
    audit.record(dataset, "dropped_wrong_geometry_type_after_repair", (~good).sum())
    frame = frame.loc[good].to_crs(CRS).copy()
    finite = np.isfinite(frame.geometry.bounds).all(axis=1)
    audit.record(dataset, "dropped_nonfinite_projected_geometry", (~finite).sum())
    return frame.loc[finite].reset_index(drop=True)


def clean_counties(frame, audit):
    frame.columns = [c.lower() for c in frame.columns]
    if "statefp" not in frame or "geoid" not in frame:
        raise ValueError("County file needs STATEFP, GEOID and NAME")
    tx = frame.loc[frame.statefp.astype(str).str.zfill(2) == "48"].copy()
    audit.record("counties", "selected_texas_counties", len(tx))
    tx = prepare_geometry(tx, "counties", ["Polygon", "MultiPolygon"], audit)
    tx["source_id"] = "counties"
    return tx[["geoid", "name", "source_id", "geometry"]]


def clean_lines(frame, region, audit):
    frame = frame.copy()
    frame.columns = [c.lower() for c in frame.columns]
    if "voltage" not in frame:
        raise ValueError("Transmission file must have a numeric VOLTAGE (kV) field")
    frame = prepare_geometry(frame, "transmission", ["LineString", "MultiLineString"], audit)
    if "status" not in frame:
        frame["status"] = "UNKNOWN"
    inactive = frame.status.astype(str).str.upper().str.strip().isin(["INACTIVE", "OUT OF SERVICE", "UNDER CONSTRUCTION", "PROPOSED"])
    audit.record("transmission", "dropped_known_nonoperating_lines", inactive.sum())
    frame = frame.loc[~inactive].copy()
    keep = frame.intersects(region)
    audit.record("transmission", "dropped_outside_texas_25km_buffer", (~keep).sum())
    frame = frame.loc[keep].copy()
    frame["voltage_kv"] = pd.to_numeric(frame.voltage, errors="coerce")
    unknown = ~np.isfinite(frame.voltage_kv) | (frame.voltage_kv <= 0)
    frame.loc[unknown, "voltage_kv"] = np.nan
    audit.record("transmission", "retained_unknown_voltage_excluded_from_hv_features", unknown.sum())
    frame["geometry_key"] = frame.geometry.map(lambda g: normalize(g).wkb_hex)
    duplicate = frame.duplicated(["geometry_key", "voltage_kv"])
    audit.record("transmission", "dropped_duplicate_geometry_and_voltage", duplicate.sum())
    frame = frame.loc[~duplicate].copy()
    id_field = next((x for x in ["id", "objectid_1", "objectid"] if x in frame), None)
    frame["line_id"] = frame[id_field].astype(str) if id_field else frame.index.astype(str)
    frame["source_id"] = "transmission"
    for field in ["owner", "sourcedate", "volt_class"]:
        if field not in frame:
            frame[field] = "unknown"
    return frame[["line_id", "voltage_kv", "status", "owner", "sourcedate", "volt_class", "source_id", "geometry"]].reset_index(drop=True)


def read_eia_sheet(content, sheet, required):
    """Discover header rows across annual workbook layout changes."""
    for header in range(6):
        frame = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=header)
        frame.columns = [str(c).strip().lower().replace("\n", " ") for c in frame.columns]
        if set(required).issubset(frame.columns):
            return frame
    raise ValueError(f"EIA header not found in sheet {sheet}; required columns: {required}")


def load_eia(path, region, audit):
    with zipfile.ZipFile(path) as archive:
        plant_file = next(n for n in archive.namelist() if Path(n).name.lower().startswith("2_") and n.endswith(".xlsx"))
        gen_file = next(n for n in archive.namelist() if Path(n).name.lower().startswith("3_1_") and n.endswith(".xlsx"))
        plants = read_eia_sheet(archive.read(plant_file), "Plant", ["plant code", "latitude", "longitude"])
        generators = read_eia_sheet(archive.read(gen_file), "Operable", ["plant code", "generator id", "status", "energy source 1", "nameplate capacity (mw)"])
    return clean_plants(plants, generators, region, audit)


def clean_plants(plants, generators, region, audit):
    plants, generators = plants.copy(), generators.copy()
    for frame in [plants, generators]:
        frame["plant code"] = pd.to_numeric(frame["plant code"], errors="coerce")
        valid = frame["plant code"].notna()
        audit.record("plants", "dropped_invalid_plant_id", (~valid).sum())
        frame.drop(index=frame.index[~valid], inplace=True)
        frame["plant code"] = frame["plant code"].astype(int)
    duplicate = plants.duplicated("plant code")
    audit.record("plants", "dropped_duplicate_plant_records", duplicate.sum())
    plants = plants.loc[~duplicate].copy()
    duplicate = generators.duplicated(["plant code", "generator id"])
    audit.record("plants", "dropped_duplicate_generators", duplicate.sum())
    generators = generators.loc[~duplicate].copy()
    # Operable also contains standby/out-of-service units. Count only operating OP.
    operating = generators.status.astype(str).str.strip().str.upper() == "OP"
    audit.record("plants", "excluded_nonoperating_generators", (~operating).sum())
    generators = generators.loc[operating].copy()
    generators["mw"] = pd.to_numeric(generators["nameplate capacity (mw)"], errors="coerce")
    valid_mw = np.isfinite(generators.mw) & (generators.mw >= 0)
    audit.record("plants", "dropped_generators_invalid_capacity", (~valid_mw).sum())
    generators = generators.loc[valid_mw].copy()
    generators["solar_mw"] = generators.mw.where(generators["energy source 1"].astype(str).str.strip() == "SUN", 0)
    generators["wind_mw"] = generators.mw.where(generators["energy source 1"].astype(str).str.strip() == "WND", 0)
    capacities = generators.groupby("plant code").agg(capacity_mw=("mw", "sum"), solar_mw=("solar_mw", "sum"), wind_mw=("wind_mw", "sum"))
    unlocated = ~generators["plant code"].isin(plants["plant code"])
    audit.record("plants", "generators_without_plant_record", unlocated.sum())
    plants = plants.merge(capacities, left_on="plant code", right_index=True, how="inner", validate="one_to_one")
    lat, lon = pd.to_numeric(plants.latitude, errors="coerce"), pd.to_numeric(plants.longitude, errors="coerce")
    valid = lat.between(-90, 90) & lon.between(-180, 180) & np.isfinite(lat) & np.isfinite(lon)
    audit.record("plants", "dropped_invalid_coordinates", (~valid).sum())
    plants = plants.loc[valid].copy()
    geo = gpd.GeoDataFrame(plants, geometry=gpd.points_from_xy(lon[valid], lat[valid]), crs=4326).to_crs(CRS)
    keep = geo.intersects(region)
    audit.record("plants", "dropped_outside_texas_25km_buffer", (~keep).sum())
    geo = geo.loc[keep].copy()
    geo["plant_id"] = geo["plant code"].astype(str)
    geo["name"] = geo["plant name"].fillna("Unnamed plant")
    geo["renewable_mw"] = geo.solar_mw + geo.wind_mw
    geo["type"] = np.select([(geo.solar_mw > 0) & (geo.wind_mw > 0), geo.solar_mw > 0, geo.wind_mw > 0], ["Solar + wind", "Solar", "Wind"], default="Other")
    geo["source_id"] = "plants"
    return geo[["plant_id", "name", "type", "capacity_mw", "solar_mw", "wind_mw", "renewable_mw", "source_id", "geometry"]].reset_index(drop=True)


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pipeline(raw_dir, output_dir, download=False):
    raw, output = Path(raw_dir), Path(output_dir)
    raw.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    sources = read_config("sources")
    audit = Audit()
    paths = {name: raw / sources[name]["filename"] for name in ["counties", "plants", "transmission"]}
    if download:
        for name in ["counties", "plants"]:
            download_file(sources[name]["url"], paths[name])
        download_transmission(sources["transmission"]["url"], paths["transmission"])
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw files: {missing}. Use --download or place local files matching config/sources.json.")
    counties = clean_counties(gpd.read_file(f"zip://{paths['counties'].resolve().as_posix()}"), audit)
    if counties.empty:
        raise ValueError("No Texas county geometries found")
    region = counties.geometry.union_all().buffer(read_config()["renewable_radius_m"])
    lines = clean_lines(gpd.read_file(paths["transmission"]), region, audit)
    plants = load_eia(paths["plants"], region, audit)
    if lines.empty or plants.empty:
        raise ValueError("No transmission lines or plants found; inspect source files")
    for name, frame in [("counties", counties), ("transmission", lines), ("plants", plants)]:
        frame.to_parquet(output / f"{name}.parquet", index=False)
        audit.record(name, "output_rows", len(frame))
    manifest = {"mode": "public", "created_at": datetime.now(timezone.utc).isoformat(), "crs": CRS,
                "sources": {name: {**sources[name], "sha256": fingerprint(path), "file": path.name} for name, path in paths.items()},
                "audit": audit.events}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
