import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, box

from gridscout.pipeline import Audit, CRS, clean_lines, clean_plants


def test_unknown_voltage_and_reversed_duplicates():
    line = LineString([(0,0),(1000,0)])
    frame = gpd.GeoDataFrame({"VOLTAGE":[345,345,-999999,"unknown"]}, geometry=[line,LineString(list(line.coords)[::-1]),LineString([(0,100),(1000,100)]),None], crs=CRS)
    audit = Audit()
    result = clean_lines(frame,box(-1,-1,2000,2000),audit)
    assert len(result) == 2
    assert result.voltage_kv.isna().sum() == 1
    assert any(e["reason"] == "dropped_duplicate_geometry_and_voltage" and e["count"] == 1 for e in audit.events)


def test_generator_aggregation_and_operating_filter():
    plants = pd.DataFrame({"plant code":[1,2],"plant name":["Hybrid","Bad coordinates"],"latitude":[31,999],"longitude":[-100,-100]})
    generators = pd.DataFrame({"plant code":[1,1,1,1,2],"generator id":["a","b","b","standby","c"],"status":["OP","OP","OP","SB","OP"],"energy source 1":["SUN","WND","WND","SUN","SUN"],"nameplate capacity (mw)":[100,200,200,999,10]})
    region = gpd.GeoSeries([box(-107,25,-92,37)],crs=4326).to_crs(CRS).iloc[0]
    result = clean_plants(plants,generators,region,Audit())
    assert len(result) == 1
    assert result.iloc[0].renewable_mw == 300
    assert result.iloc[0].type == "Solar + wind"
