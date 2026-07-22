"""Offline tests for the opt-in spatial converters. No network, no TIGER download:
POI and isochrone geometry is inherent, and the block join is exercised with a tiny
in-memory fake geometry frame. Skipped entirely if geopandas is not installed.
"""

import httpx
import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Point, Polygon  # noqa: E402

from closecity import Client, Reply, to_geopandas  # noqa: E402


def make_client(handler, spatial = False):
    return Client("ck_test_abc", base_url = "https://api.close.city",
                  spatial = spatial, transport = httpx.MockTransport(handler))


def test_spatial_by_default_returns_a_geodataframe():
    def handler(request):
        return httpx.Response(200, json = {"results": [
            {"dest_id": 1, "name": "A", "lat": 44.0, "lon": -123.0}],
            "next_cursor": None})

    # spatial defaults to True, so the method returns a GeoDataFrame directly.
    gdf = make_client(handler, spatial = True).pois_search(
        lat = 44.0, lon = -123.0, radius_m = 1000)
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert list(gdf.geometry.geom_type) == ["Point"]


# -- POI rows -> points ------------------------------------------------------

def test_poi_rows_become_points():
    reply = Reply(
        data = {"results": [
            {"dest_id": 1, "name": "Cafe A", "lat": 44.05, "lon": -123.09},
            {"dest_id": 2, "name": "Cafe B", "lat": 44.06, "lon": -123.10},
        ]},
        status = 200,
    )
    gdf = reply.to_geopandas()
    assert list(gdf.geometry.geom_type.unique()) == ["Point"]
    assert len(gdf) == 2
    assert gdf.crs == "EPSG:4326"
    assert gdf.geometry.iloc[0].x == pytest.approx(-123.09)
    assert set(["dest_id", "name"]).issubset(gdf.columns)


def test_single_poi_detail_becomes_one_point():
    reply = Reply(data = {"dest_id": 7, "name": "Library", "lat": 40.0, "lon": -75.0,
                          "type_ids": [43]}, status = 200)
    gdf = reply.to_geopandas()
    assert len(gdf) == 1 and gdf.geometry.iloc[0].equals(Point(-75.0, 40.0))


# -- isochrone geojson -> polygons -------------------------------------------

def test_isochrone_features_become_polygons():
    square = [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]
    reply = Reply(
        data = {
            "type": "FeatureCollection",  # note: real envelope is custom; features is what matters
            "features": [
                {"type": "Feature",
                 "geometry": {"type": "Polygon", "coordinates": square},
                 "properties": {"contour": 15, "mode": "walk", "reachable_blocks": 12}},
                {"type": "Feature", "geometry": None,
                 "properties": {"contour": 30, "mode": "walk", "reachable_blocks": 0}},
            ],
            "block": "410390020001010", "mode": "walk", "direction": "to",
        },
        status = 200,
    )
    gdf = reply.to_geopandas()
    assert len(gdf) == 2
    assert gdf.geometry.iloc[0].geom_type == "Polygon"
    assert gdf.geometry.iloc[1] is None or gdf.geometry.iloc[1].is_empty
    assert gdf["contour"].tolist() == [15, 30]


# -- block rows -> polygons via a supplied geometry frame --------------------

def _fake_blocks():
    return gpd.GeoDataFrame(
        {"GEOID20": ["100", "200"]},
        geometry = [Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
                    Polygon([(1, 0), (1, 1), (2, 1), (2, 0)])],
        crs = "EPSG:4326",
    )


def test_block_rows_need_geometry_and_join_on_supplied_frame():
    reply = Reply(
        data = {"results": [
            {"geoid": "100", "dest_type_id": 30, "mode_id": 1, "travel_time": 6.5,
             "population": 1187},
            {"geoid": "200", "dest_type_id": 30, "mode_id": 1, "travel_time": 12.0,
             "population": 640},
        ]},
        status = 200,
    )
    # Without geometry it refuses, with a clear message.
    with pytest.raises(ValueError, match = "block_geometry"):
        reply.to_geopandas()
    # With a supplied frame it joins on the GEOID.
    gdf = reply.to_geopandas(block_geometry = _fake_blocks())
    assert len(gdf) == 2
    assert list(gdf.geometry.geom_type.unique()) == ["Polygon"]
    assert gdf.loc[gdf.geoid == "100", "travel_time"].iloc[0] == 6.5


def test_summary_block_meta_becomes_one_polygon():
    reply = Reply(
        data = {"block": {"geoid": "100", "population": 1187, "land_area_m2": 1.0},
                "results": [{"dest_type_id": 30, "mode": "walk", "travel_time": 6.5}]},
        status = 200,
    )
    gdf = reply.to_geopandas(block_geometry = _fake_blocks())
    assert len(gdf) == 1 and gdf.geometry.iloc[0].geom_type == "Polygon"


# -- Paginator collects across pages -----------------------------------------

def test_paginator_to_geopandas_collects_all_pages():
    pages = {
        None: {"results": [{"dest_id": 1, "name": "A", "lat": 44.0, "lon": -123.0}],
               "next_cursor": "C2"},
        "C2": {"results": [{"dest_id": 2, "name": "B", "lat": 44.1, "lon": -123.1}],
               "next_cursor": None},
    }

    def handler(request):
        return httpx.Response(200, json = pages[request.url.params.get("cursor")])

    gdf = make_client(handler).pois_search(lat = 44.0, lon = -123.0,
                                           radius_m = 1000).to_geopandas()
    assert len(gdf) == 2 and list(gdf["dest_id"]) == [1, 2]


# -- module-level function + empty --------------------------------------------

def test_module_function_and_empty_reply():
    assert to_geopandas([{"lat": 1.0, "lon": 2.0}]).geometry.iloc[0].equals(Point(2.0, 1.0))
    with pytest.raises(ValueError):
        to_geopandas(Reply(data = {"results": []}, status = 200))
