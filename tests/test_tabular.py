"""Tests for the tabular output mode: catalog and summary routes become plain
DataFrames, metering rides on df.attrs, and output="tabular" never downloads
block boundaries. No network beyond the mocked transport.
"""

import httpx
import pytest

pd = pytest.importorskip("pandas")

from closecity import Client, Reply, to_pandas  # noqa: E402


def make_client(handler, output = "tabular"):
    return Client("ck_live_abc", base_url = "https://api.close.city",
                  output = output, transport = httpx.MockTransport(handler))


# -- catalog routes become frames --------------------------------------------

def test_modes_becomes_a_dataframe():
    def handler(request):
        return httpx.Response(200, json = {"modes": [
            {"mode_id": 1, "mode": "walk", "description": "Walking"},
            {"mode_id": 2, "mode": "bike", "description": "Biking"}]},
            headers = {"X-Tokens-Charged": "0"})

    df = make_client(handler).modes()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["mode_id", "mode", "description"]
    assert df["mode"].tolist() == ["walk", "bike"]


def test_destination_types_keeps_leaf_ids_list_column():
    def handler(request):
        return httpx.Response(200, json = {"destination_types": [
            {"dest_type_id": 61, "name": "Frequent transit", "label": "frequent_transit",
             "is_leaf": False, "leaf_ids": [201, 203]}]})

    df = make_client(handler).destination_types()
    assert df.loc[0, "leaf_ids"] == [201, 203]
    assert not df.loc[0, "is_leaf"]


def test_vintage_reads_the_components_array():
    def handler(request):
        return httpx.Response(200, json = {"components": [
            {"component": "pois", "version": "osm-2026-03",
             "effective_date": "2026-03-01"}]})

    df = make_client(handler).vintage()
    assert df["component"].tolist() == ["pois"]


def test_places_tabular_is_a_plain_frame_with_lon_lat():
    def handler(request):
        return httpx.Response(200, json = {"places": [
            {"name": "Providence", "geoid": "4459000", "lon": -71.42, "lat": 41.82}]})

    df = make_client(handler).places("Providence")
    assert not hasattr(df, "geometry")
    assert {"name", "geoid", "lon", "lat"}.issubset(df.columns)


# -- summaries broadcast the origin geoid and carry the block on attrs ---------

def test_block_summary_broadcasts_geoid_and_stamps_block():
    def handler(request):
        return httpx.Response(200, json = {
            "block": {"geoid": "440070008001068", "population": 31, "land_area_m2": 4.0},
            "results": [
                {"dest_type_id": 30, "mode": "walk", "travel_time": 6.5},
                {"dest_type_id": 31, "mode": "walk", "travel_time": 12.0}]},
            headers = {"X-Tokens-Charged": "2", "X-Tokens-Remaining": "998",
                       "ETag": '"e1"', "X-Request-Id": "r1"})

    df = make_client(handler).block_summary("440070008001068")
    assert df["geoid"].tolist() == ["440070008001068", "440070008001068"]
    assert list(df.columns)[0] == "geoid"
    assert df.attrs["tokens_charged"] == 2
    assert df.attrs["tokens_remaining"] == 998
    assert df.attrs["block"]["population"] == 31


def test_point_summary_broadcasts_resolved_block():
    def handler(request):
        return httpx.Response(200, json = {
            "resolved_block": "440070008001068",
            "block": {"geoid": "440070008001068", "population": 31,
                      "land_area_m2": 4.0},
            "results": [{"dest_type_id": 30, "mode": "walk", "travel_time": 6.5}]})

    df = make_client(handler).point_summary(41.82, -71.42)
    assert df["geoid"].tolist() == ["440070008001068"]
    assert df.attrs["resolved_block"] == "440070008001068"


# -- metering rides on attrs, summed across pages -----------------------------

def test_paginator_attrs_sum_tokens_across_pages():
    pages = {
        None: {"results": [{"dest_id": 1, "name": "A", "lat": 44.0, "lon": -123.0}],
               "next_cursor": "C2"},
        "C2": {"results": [{"dest_id": 2, "name": "B", "lat": 44.1, "lon": -123.1}],
               "next_cursor": None},
    }

    def handler(request):
        cur = request.url.params.get("cursor")
        return httpx.Response(200, json = pages[cur],
                              headers = {"X-Tokens-Charged": "1",
                                         "X-Tokens-Remaining": "500" if cur else "501"})

    df = make_client(handler).pois_search(lat = 44.0, lon = -123.0, radius_m = 1000)
    assert df["dest_id"].tolist() == [1, 2]
    assert df.attrs["tokens_charged"] == 2  # summed across the two pages
    assert df.attrs["tokens_remaining"] == 500  # last page


def test_block_pois_stamps_block_geoid_on_attrs():
    def handler(request):
        return httpx.Response(200, json = {
            "block_geoid": "440070008001068",
            "results": [{"dest_id": 1, "mode": "walk", "travel_time": 5.0,
                         "name": "Shop", "lon": -71.4, "lat": 41.8,
                         "address": {"street": "1 Main St"}}],
            "next_cursor": None})

    df = make_client(handler).block_pois("440070008001068")
    assert "geoid" not in df.columns  # POIs, not the origin block
    assert df.attrs["block_geoid"] == "440070008001068"


# -- output="tabular" skips the TIGER download for block routes ----------------

def test_blocks_query_tabular_needs_no_geometry_download():
    def handler(request):
        return httpx.Response(200, json = {"results": [
            {"geoid": "440070008001068", "dest_type_id": 30, "mode_id": 1,
             "travel_time": 6.5, "population": 31}], "next_cursor": None})

    # No pygris installed / no block_geometry passed: tabular must not need it.
    df = make_client(handler).blocks_query(
        center = {"lon": -71.42, "lat": 41.82}, radius_m = 1000)
    assert df["geoid"].tolist() == ["440070008001068"]
    assert df["mode_id"].tolist() == [1]  # areal rows carry the int mode_id


def test_isochrone_blocks_format_becomes_a_frame():
    def handler(request):
        return httpx.Response(200, json = {
            "blocks": [{"geoid": "440070008001068", "travel_min": 7}],
            "reachable_blocks": 1, "block": "440070008001068", "direction": "from",
            "mode": "walk", "version": "v1", "assumptions": {}})

    df = make_client(handler).isochrone(block = "440070008001068", format = "blocks")
    assert df["travel_min"].tolist() == [7]
    assert df.attrs["reachable_blocks"] == 1
    assert df.attrs["direction"] == "from"


def test_isochrone_geojson_tabular_is_feature_properties():
    def handler(request):
        return httpx.Response(200, json = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": None,
                 "properties": {"contour": 15, "mode": "walk", "reachable_blocks": 9}},
                {"type": "Feature", "geometry": None,
                 "properties": {"contour": 30, "mode": "walk", "reachable_blocks": 20}}],
            "block": "440070008001068", "direction": "to", "mode": "walk",
            "version": "v1", "assumptions": {}})

    df = make_client(handler).isochrone(block = "440070008001068", contours = [15, 30])
    assert df["contour"].tolist() == [15, 30]
    assert df.attrs["block"] == "440070008001068"


# -- per-call override, raw passthrough, and validation -----------------------

def test_per_call_output_override_beats_client_default():
    def handler(request):
        return httpx.Response(200, json = {"modes": [
            {"mode_id": 1, "mode": "walk", "description": "Walking"}]})

    client = make_client(handler, output = "tabular")
    assert isinstance(client.modes(output = "raw"), Reply)


def test_304_stays_raw_in_every_mode():
    def handler(request):
        return httpx.Response(304, headers = {"ETag": '"e1"'})

    reply = make_client(handler, output = "tabular").block_summary(
        "440070008001068", if_none_match = '"e1"')
    assert isinstance(reply, Reply)
    assert reply.not_modified is True


def test_invalid_output_raises():
    with pytest.raises(ValueError, match = "output must be one of"):
        Client("ck_live_abc", output = "geojson")


def test_empty_results_gives_an_empty_frame():
    def handler(request):
        return httpx.Response(200, json = {"results": [], "next_cursor": None})

    df = make_client(handler).pois_search(lat = 44.0, lon = -123.0, radius_m = 1000)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


# -- module-level helper ------------------------------------------------------

def test_module_to_pandas_on_a_reply():
    reply = Reply(
        data = {"places": [{"name": "X", "geoid": "1", "lon": 0.0, "lat": 0.0}]},
        status = 200,
    )
    df = to_pandas(reply, key = "places")
    assert df["name"].tolist() == ["X"]
