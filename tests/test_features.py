import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

from gridscout.features import candidate_grid, compute_features
from gridscout.pipeline import CRS


def layers():
    sites = gpd.GeoDataFrame({"site_id":["A"]}, geometry=[Point(0,0)], crs=CRS)
    lines = gpd.GeoDataFrame({"line_id":["hv","lv"],"voltage_kv":[345,69]},geometry=[LineString([(3000,-10000),(3000,10000)]),LineString([(10,-100),(10,100)])],crs=CRS)
    plants = gpd.GeoDataFrame({"plant_id":["one","edge","outside"],"name":["one","edge","outside"],"solar_mw":[100,0,999],"wind_mw":[0,200,0],"renewable_mw":[100,200,999],"source_id":["fake"]*3},geometry=[Point(10000,0),Point(25000,0),Point(25001,0)],crs=CRS)
    return sites,lines,plants


def test_line_distance_and_radius_inclusion():
    result = compute_features(*layers()).iloc[0]
    assert result.distance_to_hv_m == pytest.approx(3000)
    assert result.voltage_kv == 345
    assert result.renewable_count == 2
    assert result.solar_count == result.wind_count == 1
    assert result.renewable_capacity_mw == 300


def test_ties_select_highest_voltage_without_duplicate_candidates():
    sites, lines, plants = layers()
    lines.loc[2] = ["tie",500,LineString([(-3000,-10000),(-3000,10000)])]
    lines = lines.set_crs(CRS, allow_override=True)
    result = compute_features(sites,lines,plants)
    assert len(result) == 1
    assert result.iloc[0].line_id == "tie"


def test_reject_latlon_and_mismatched_crs():
    sites,lines,plants = layers()
    with pytest.raises(ValueError,match="projected"):
        compute_features(sites.to_crs(4326),lines,plants)
    with pytest.raises(ValueError,match="same projected"):
        compute_features(sites,lines.to_crs(3857),plants)


def test_empty_renewables_and_missing_hv():
    sites,lines,plants = layers()
    result = compute_features(sites,lines,plants.iloc[:0])
    assert result.iloc[0].renewable_count == 0
    with pytest.raises(ValueError,match="No known transmission"):
        compute_features(sites,lines.iloc[:0],plants)


def test_border_cells_points_stay_inside_state():
    counties = gpd.GeoDataFrame({"geoid":["48fake"],"name":["fake"]},geometry=[box(1500,1500,8500,8500)],crs=CRS)
    points,cells = candidate_grid(counties,5000)
    assert len(points) == 4
    assert points.within(counties.geometry.iloc[0]).all()
    assert cells.area.sum() == pytest.approx(counties.area.sum())
