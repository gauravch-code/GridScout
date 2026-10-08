"""Deterministic synthetic inputs, explicitly unrelated to actual infrastructure."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point, Polygon

from .features import build_features
from .pipeline import CRS


def build_demo(data_dir):
    data = Path(data_dir)
    data.mkdir(parents=True, exist_ok=True)
    # Simplified illustrative Texas outline, not a boundary product.
    outline = Polygon([(-106.65,31.8),(-103.05,32),(-103.05,36.5),(-100,36.5),(-100,34.6),(-94.5,33.6),(-93.6,31.1),(-94.5,29.7),(-96.5,28.3),(-97.2,25.9),(-99.1,26.4),(-100.5,29),(-103,29),(-104.6,30.6)])
    counties = gpd.GeoDataFrame({"geoid": ["DEMO"], "name": ["Illustrative Texas"], "source_id": ["synthetic"]}, geometry=[outline], crs=4326).to_crs(CRS)
    rng = np.random.default_rng(42)
    state = counties.geometry.iloc[0]
    xmin, ymin, xmax, ymax = state.bounds
    corridors = [LineString([(xmin + (xmax - xmin) * f, ymin), (xmin + (xmax - xmin) * (f + .12), ymax)]) for f in [.2,.4,.6,.75]]
    corridors += [LineString([(xmin, ymin + (ymax-ymin)*f), (xmax, ymin + (ymax-ymin)*(f+.1))]) for f in [.3,.5,.7]]
    lines = gpd.GeoDataFrame({"line_id": [f"DEMO-L{i}" for i in range(7)], "voltage_kv": [345,138,345,500,115,230,345], "owner": ["Synthetic"]*7, "sourcedate": ["synthetic"]*7, "volt_class": ["synthetic"]*7, "source_id": ["synthetic"]*7}, geometry=corridors, crs=CRS)
    lines["status"] = "SYNTHETIC"
    points = []
    while len(points) < 260:
        point = Point(rng.uniform(xmin,xmax),rng.uniform(ymin,ymax))
        if state.contains(point):
            points.append(point)
    solar = rng.random(len(points)) > .45
    mw = rng.uniform(20,350,len(points)).round(1)
    plants = gpd.GeoDataFrame({"plant_id": [f"DEMO-P{i}" for i in range(len(points))], "name": [f"Synthetic renewable {i:03}" for i in range(len(points))], "type": np.where(solar,"Solar","Wind"), "capacity_mw": mw, "solar_mw": np.where(solar,mw,0), "wind_mw": np.where(solar,0,mw), "renewable_mw": mw, "source_id": "synthetic"}, geometry=points, crs=CRS)
    for name, frame in [("counties",counties),("transmission",lines),("plants",plants)]:
        frame.to_parquet(data/f"{name}.parquet",index=False)
    (data/"manifest.json").write_text(json.dumps({"mode":"synthetic", "crs":CRS, "sources":{name:{"vintage":"Seed 42, illustrative boundary and fictional infrastructure","kind":"synthetic"} for name in ["counties","transmission","plants"]}}),encoding="utf-8")
    build_features(data)
