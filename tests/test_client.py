"""Unit tests for the closecity client, driven over an httpx MockTransport so no
network is touched. They pin the mechanics the SDK exists to get right: bearer
auth, token-header surfacing, opaque-cursor pagination, ETag/304 revalidation,
and problem+json -> exception mapping.
"""

import json

import httpx
import pytest

from closecity import (
    AuthenticationError,
    Client,
    NotFoundError,
    RateLimitedError,
    TokensExhaustedError,
)
from closecity.errors import BadRequestError

PROBLEM = "application/problem+json"


def problem(status, slug, title, **extra):
    body = {"type": f"https://api.close.city/problems/{slug}",
            "title": title, "status": status, **extra}
    return httpx.Response(status, json = body,
                          headers = {"content-type": PROBLEM,
                                     "X-Request-Id": "req-123"})


def make_client(handler, api_key = "ck_live_abc"):
    # output = "raw" so methods return the raw Reply / Paginator we assert on.
    return Client(api_key, base_url = "https://api.close.city", output = "raw",
                  transport = httpx.MockTransport(handler))


# -- auth + metered headers --------------------------------------------------

def test_bearer_auth_and_token_headers():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200, json = {"block": {"geoid": "1", "population": None,
                                   "land_area_m2": None}, "results": []},
            headers = {"X-Tokens-Charged": "1", "X-Tokens-Remaining": "4999",
                       "ETag": '"abc"', "X-Request-Id": "r1"},
        )

    reply = make_client(handler).block_summary("410390020001010")
    assert seen["auth"] == "Bearer ck_live_abc"
    assert reply.tokens_charged == 1
    assert reply.tokens_remaining == 4999
    assert reply.etag == '"abc"'
    assert reply.request_id == "r1"
    assert reply.data["block"]["geoid"] == "1"


def test_places_lookup_is_a_free_get():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["q"] = request.url.params.get("q")
        seen["limit"] = request.url.params.get("limit")
        return httpx.Response(200, json = {"places": [
            {"name": "Providence", "geoid": "4459000", "lon": -71.42, "lat": 41.82}]})

    reply = make_client(handler).places("Providence", limit = 5)
    assert seen["path"] == "/v1/places"
    assert seen["q"] == "Providence" and seen["limit"] == "5"
    assert reply.data["places"][0]["geoid"] == "4459000"


def test_free_route_needs_no_key():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json = {"status": "ok", "version": "0.1.0"})

    reply = Client(transport = httpx.MockTransport(handler)).health()
    assert reply.data["status"] == "ok"
    assert reply.tokens_charged is None  # free route


# -- list params + filters ---------------------------------------------------

def test_repeated_and_dropped_params():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json = {"results": [], "next_cursor": None})

    list(make_client(handler).block_pois(
        "410390020001010", mode = ["walk", "transit"], type = [30], max_minutes = None
    ))
    # both modes repeated; the None max_minutes is omitted entirely
    assert "mode=walk" in seen["url"] and "mode=transit" in seen["url"]
    assert "type=30" in seen["url"]
    assert "max_minutes" not in seen["url"]


# -- pagination --------------------------------------------------------------

def test_paginator_follows_cursor_across_pages():
    pages = {
        None: {"results": [{"dest_id": 1}, {"dest_id": 2}], "next_cursor": "CUR2"},
        "CUR2": {"results": [{"dest_id": 3}], "next_cursor": None},
    }
    calls = []

    def handler(request):
        cur = request.url.params.get("cursor")
        calls.append(cur)
        return httpx.Response(200, json = pages[cur],
                              headers = {"X-Tokens-Charged": "2"})

    got = list(make_client(handler).pois_search(lat = 44.0, lon = -123.0,
                                                radius_m = 1000))
    assert [r["dest_id"] for r in got] == [1, 2, 3]
    assert calls == [None, "CUR2"]  # exactly two page fetches, then stop


def test_pages_expose_per_page_metadata():
    def handler(request):
        return httpx.Response(200, json = {"results": [{"x": 1}], "next_cursor": None},
                              headers = {"X-Tokens-Remaining": "7"})

    page = make_client(handler).point_pois(44.0, -123.0).page()
    assert page.tokens_remaining == 7
    assert page.results == [{"x": 1}]


def test_blocks_query_is_post_with_cursor_in_body():
    bodies = []
    methods = []

    def handler(request):
        methods.append(request.method)
        body = json.loads(request.content)
        bodies.append(body)
        nxt = "C2" if body.get("cursor") is None else None
        return httpx.Response(200, json = {"results": [{"geoid": "g"}],
                                           "next_cursor": nxt})

    pg = make_client(handler).blocks_query(
        center = {"lon": -123.0, "lat": 44.0}, radius_m = 1000,
        mode = "walk", type = 30, include_population = True,
    )
    records = list(pg)
    assert methods == ["POST", "POST"]
    assert len(records) == 2
    assert bodies[0]["center"] == {"lon": -123.0, "lat": 44.0}
    assert bodies[0]["include_population"] is True
    # Scalar mode/type are wrapped in lists (the POST body needs arrays).
    assert bodies[0]["mode"] == ["walk"]
    assert bodies[0]["type"] == [30]
    assert bodies[1]["cursor"] == "C2"  # cursor threaded through the body


# -- conditional requests ----------------------------------------------------

def test_if_none_match_304_is_free_and_not_modified():
    def handler(request):
        assert request.headers.get("if-none-match") == '"etag-1"'
        return httpx.Response(304, headers = {"ETag": '"etag-1"'})

    reply = make_client(handler).block_summary("410390020001010",
                                               if_none_match = '"etag-1"')
    assert reply.not_modified is True
    assert reply.data is None
    assert reply.tokens_charged is None
    assert reply.etag == '"etag-1"'


# -- error mapping -----------------------------------------------------------

@pytest.mark.parametrize("status,slug,exc", [
    (401, "invalid-key", AuthenticationError),
    (404, "block-not-found", NotFoundError),
    (429, "tokens-exhausted", TokensExhaustedError),
    (429, "rate-limited", RateLimitedError),
    (400, "invalid-parameters", BadRequestError),
])
def test_problem_json_maps_to_exceptions(status, slug, exc):
    def handler(request):
        return problem(status, slug, f"{slug} happened")

    with pytest.raises(exc) as ei:
        make_client(handler).poi(999)
    err = ei.value
    assert err.slug == slug
    assert err.status == status
    assert err.request_id == "req-123"


def test_rate_limited_exposes_retry_after_and_extras():
    def handler(request):
        return httpx.Response(
            429, json = {"type": "https://api.close.city/problems/rate-limited",
                         "title": "Slow down", "status": 429},
            headers = {"content-type": PROBLEM, "Retry-After": "30",
                       "X-Request-Id": "req-9"},
        )

    with pytest.raises(RateLimitedError) as ei:
        make_client(handler).modes()
    assert ei.value.retry_after == 30.0


def test_validation_errors_extension_is_preserved():
    def handler(request):
        return problem(400, "invalid-parameters", "Bad input",
                       errors = [{"loc": ["query", "lat"], "msg": "required",
                                  "type": "missing"}])

    with pytest.raises(BadRequestError) as ei:
        make_client(handler).point_summary(0.0, 0.0)
    assert ei.value.extras["errors"][0]["loc"] == ["query", "lat"]


# -- isochrone contours normalisation ---------------------------------------

def test_isochrone_contours_list_becomes_csv():
    seen = {}

    def handler(request):
        seen["contours"] = request.url.params.get("contours")
        return httpx.Response(200, json = {"type": "FeatureCollection",
                                           "features": []})

    make_client(handler).isochrone(block = "410390020001010",
                                   contours = [15, 30, 45])
    assert seen["contours"] == "15,30,45"


# -- api key sourcing --------------------------------------------------------

def test_api_key_read_from_environment(monkeypatch):
    monkeypatch.setenv("CLOSECITY_KEY", "ck_live_env")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json = {"modes": []})

    Client(base_url = "https://api.close.city", output = "raw",
           transport = httpx.MockTransport(handler)).modes()
    assert seen["auth"] == "Bearer ck_live_env"


def test_explicit_key_overrides_environment(monkeypatch):
    monkeypatch.setenv("CLOSECITY_KEY", "ck_live_env")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json = {"modes": []})

    Client("ck_live_explicit", base_url = "https://api.close.city",
           output = "raw", transport = httpx.MockTransport(handler)).modes()
    assert seen["auth"] == "Bearer ck_live_explicit"


def test_missing_key_401_adds_actionable_hint(monkeypatch):
    monkeypatch.delenv("CLOSECITY_KEY", raising = False)

    def handler(request):
        return problem(401, "missing-key", "Provide an API key.")

    client = Client(base_url = "https://api.close.city", output = "raw",
                    transport = httpx.MockTransport(handler))
    with pytest.raises(AuthenticationError) as ei:
        client.block_summary("410390020001010")
    assert ei.value.hint is not None
    assert "CLOSECITY_KEY" in ei.value.hint
    assert "CLOSECITY_KEY" in str(ei.value)


def test_invalid_key_401_has_no_missing_key_hint():
    # A key IS set (make_client passes one), so the "you forgot your key" hint
    # must not fire on an invalid-key 401.
    def handler(request):
        return problem(401, "invalid-key", "Unknown or revoked API key.")

    with pytest.raises(AuthenticationError) as ei:
        make_client(handler).block_summary("410390020001010")
    assert ei.value.hint is None
