"""Vectorized spatial joins; candidate features always measured from a site point."""
import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import box

from .settings import read_config

LOG = logging.getLogger(__name__)


def require_meters(frame):
    if frame.crs is None or not frame.crs.is_projected:
        raise ValueError("Distance math requires a projected CRS in meters")
    if any(axis.unit_name.lower() not in {"metre", "meter"} for axis in frame.crs.axis_info):
        raise ValueError("Distance math requires meter units")


def candidate_grid(counties, size_m=5000):
    require_meters(counties)
    if not np.isfinite(size_m) or size_m < 1000:
        raise ValueError("Cell size must be finite and at least 1000 m")
    state = counties.geometry.union_all()
    xmin, ymin, xmax, ymax = state.bounds
    # Anchor to a global grid for IDs stable across a repeated data refresh.
    xmin, ymin = np.floor([xmin / size_m, ymin / size_m]) * size_m
    xs, ys = np.meshgrid(np.arange(xmin, xmax, size_m), np.arange(ymin, ymax, size_m))
    cells = gpd.GeoDataFrame({"site_id": [f"TX-{int(x / size_m)}-{int(y / size_m)}-{int(size_m)}" for x, y in zip(xs.ravel(), ys.ravel())]},
                            geometry=[box(x, y, x + size_m, y + size_m) for x, y in zip(xs.ravel(), ys.ravel())], crs=counties.crs)
    cells = cells.loc[cells.intersects(state)].copy()
    cells.geometry = cells.geometry.intersection(state)
    cells = cells.loc[cells.area > 1].reset_index(drop=True)
    points = cells.copy()
    # Representative points stay inside clipped border cells and offshore exclusions.
    points.geometry = cells.geometry.representative_point()
    points["cell_area_km2"] = cells.area / 1e6
    points["cell_size_m"] = size_m
    county_join = gpd.sjoin(points, counties[["geoid", "name", "geometry"]], how="left", predicate="intersects")
    county_join = county_join.sort_values(["site_id", "geoid"]).drop_duplicates("site_id")
    points["county"] = county_join.set_index("site_id").reindex(points.site_id)["name"].to_numpy()
    points["county_geoid"] = county_join.set_index("site_id").reindex(points.site_id)["geoid"].to_numpy()
    return points, cells


def compute_features(candidates, lines, plants, minimum_voltage=115, radius_m=25000):
    for frame in [candidates, lines, plants]:
        require_meters(frame)
        if frame.crs != candidates.crs:
            raise ValueError("All layers must have the same projected CRS")
    if radius_m <= 0 or minimum_voltage <= 0:
        raise ValueError("Radius and voltage threshold must be positive")
    result = candidates.copy().reset_index(drop=True)
    if result.site_id.duplicated().any():
        raise ValueError("Candidate site IDs must be unique")
    hv = lines.loc[lines.voltage_kv >= minimum_voltage].copy()
    if hv.empty:
        raise ValueError("No known transmission lines meet the high-voltage threshold")
    nearest = gpd.sjoin_nearest(result[["site_id", "geometry"]], hv[["line_id", "voltage_kv", "geometry"]], how="left", distance_col="distance_to_hv_m")
    # Ties select highest voltage, then line ID. No duplicate candidates.
    nearest = nearest.sort_values(["site_id", "distance_to_hv_m", "voltage_kv", "line_id"], ascending=[True, True, False, True]).drop_duplicates("site_id").set_index("site_id")
    for name in ["line_id", "voltage_kv", "distance_to_hv_m"]:
        result[name] = nearest.reindex(result.site_id)[name].to_numpy()
    renewables = plants.loc[plants.renewable_mw > 0].copy()
    if renewables.plant_id.duplicated().any():
        raise ValueError("Plants must be aggregated to unique plant IDs")
    nearby = gpd.sjoin(result[["site_id", "geometry"]], renewables, how="inner", predicate="dwithin", distance=radius_m)
    if not nearby.empty:
        nearby["solar_flag"] = (nearby.solar_mw > 0).astype(int)
        nearby["wind_flag"] = (nearby.wind_mw > 0).astype(int)
        aggregates = nearby.groupby("site_id").agg(renewable_count=("plant_id", "nunique"), solar_count=("solar_flag", "sum"), wind_count=("wind_flag", "sum"), renewable_capacity_mw=("renewable_mw", "sum"))
        nearby["distance_m"] = nearby.geometry.distance(gpd.GeoSeries(renewables.loc[nearby.index_right, "geometry"].to_numpy(), index=nearby.index, crs=result.crs))
        evidence = nearby.groupby("site_id").apply(lambda group: json.dumps(group[["plant_id", "name", "solar_mw", "wind_mw", "renewable_mw", "distance_m", "source_id"]].sort_values("plant_id").to_dict("records")), include_groups=False)
    else:
        aggregates = pd.DataFrame(columns=["renewable_count", "solar_count", "wind_count", "renewable_capacity_mw"])
        evidence = pd.Series(dtype=str)
    for name in ["renewable_count", "solar_count", "wind_count", "renewable_capacity_mw"]:
        result[name] = result.site_id.map(aggregates[name]).fillna(0)
    result["nearby_plants_json"] = result.site_id.map(evidence).fillna("[]")
    result["radius_m"] = radius_m
    wgs = result.to_crs(4326)
    result["longitude"], result["latitude"] = wgs.geometry.x, wgs.geometry.y
    return result


def build_features(data_dir, cell_size=5000):
    data = Path(data_dir)
    counties, lines, plants = [gpd.read_parquet(data / f"{name}.parquet") for name in ["counties", "transmission", "plants"]]
    config = read_config()
    points, cells = candidate_grid(counties, cell_size)
    result = compute_features(points, lines, plants, config["minimum_voltage_kv"], config["renewable_radius_m"])
    result.to_parquet(data / "candidates.parquet", index=False)
    cells.to_parquet(data / "cells.parquet", index=False)
    LOG.info("Created %d candidates with %s m cells", len(result), cell_size)
    return result
