"""A thin, typed client for the Close API (https://api.close.city).

Design goals: mirror the public OpenAPI contract exactly, surface the metering
and conditional-request mechanics (token headers, ETag/304) as first-class, map
``problem+json`` errors to precise exceptions, and iterate keyset-paginated
endpoints transparently. Cursors are opaque and never constructed client-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Sequence

import httpx

from . import errors

__all__ = ["Client", "Reply", "Paginator"]

DEFAULT_BASE_URL = "https://api.close.city"


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop None-valued params (so optional filters simply vanish)."""
    return {k: v for k, v in (params or {}).items() if v is not None}


def _as_list(value: Any) -> Any:
    """Wrap a scalar in a list, for POST-body fields the API requires as arrays.
    ``None`` and existing lists/tuples pass through unchanged."""
    if value is None or isinstance(value, (list, tuple)):
        return value
    return [value]


def _int(value: str | None) -> int | None:
    return int(value) if value is not None else None


def _retry_after(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


@dataclass
class Reply:
    """One API response, with the metering + caching metadata exposed.

    ``data`` is the parsed JSON body (a ``dict`` for every route). For a ``304``
    revalidation ``not_modified`` is True and ``data`` is None. ``tokens_charged``
    / ``tokens_remaining`` are None on free and member-unmetered responses.
    """

    data: Any
    status: int
    tokens_charged: int | None = None
    tokens_remaining: int | None = None
    etag: str | None = None
    request_id: str | None = None
    not_modified: bool = False

    @property
    def results(self) -> list[dict]:
        """The ``results`` array of a list endpoint (empty if absent)."""
        return self.data.get("results", []) if isinstance(self.data, dict) else []

    @property
    def next_cursor(self) -> str | None:
        return self.data.get("next_cursor") if isinstance(self.data, dict) else None

    def to_geopandas(self, **kwargs):
        """Convert this reply to a :class:`geopandas.GeoDataFrame`.

        Points for POI replies, polygons for isochrone ``format=geojson``. Block
        replies need a ``block_geometry=`` GeoDataFrame or ``fetch=True`` (which
        downloads TIGER blocks with ``pygris``). See
        :func:`closecity.spatial.to_geopandas`.
        """
        from . import spatial
        return spatial.to_geopandas(self, **kwargs)


@dataclass
class Paginator:
    """Lazily follows ``next_cursor`` across pages.

    Iterate it directly to get every record; use :meth:`pages` for per-page
    :class:`Reply` objects (each carrying its own token/ETag metadata); use
    :meth:`page` to fetch a single page.
    """

    _client: "Client"
    _method: str
    _path: str
    _params: dict[str, Any] = field(default_factory = dict)
    _json: dict[str, Any] | None = None
    _cursor_in: str = "params"  # "params" for GETs, "json" for POST body

    def page(self, cursor: str | None = None) -> Reply:
        params = dict(self._params)
        body = dict(self._json) if self._json is not None else None
        if cursor is not None:
            if self._cursor_in == "json":
                body = {**(body or {}), "cursor": cursor}
            else:
                params["cursor"] = cursor
        return self._client._request(
            self._method, self._path, params = params, json = body
        )

    def pages(self) -> Iterator[Reply]:
        cursor = None
        while True:
            reply = self.page(cursor)
            yield reply
            cursor = reply.next_cursor
            if not cursor:
                return

    def __iter__(self) -> Iterator[dict]:
        for reply in self.pages():
            yield from reply.results

    def to_geopandas(self, **kwargs):
        """Collect every page and convert the rows to a
        :class:`geopandas.GeoDataFrame`. See
        :func:`closecity.spatial.to_geopandas`.
        """
        from . import spatial
        return spatial.to_geopandas(self, **kwargs)


class Client:
    """Client for the Close API.

    ``api_key`` is optional (the catalog and health routes are free), but every
    data route needs one (a ``ck_live_`` or ``ck_test_`` key), created at
    https://account.close.city. Usable as a context manager.

    Feature methods return a :class:`geopandas.GeoDataFrame` when ``spatial`` is
    True (the default), or the raw :class:`Reply` / :class:`Paginator` otherwise.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        spatial: bool = True,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.spatial = spatial
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = http_client or httpx.Client(
            base_url = base_url.rstrip("/"), timeout = timeout, headers = headers,
            transport = transport,
        )

    def _spatial(self, source):
        """Convert a feature reply to a GeoDataFrame when ``spatial`` is on."""
        if not self.spatial:
            return source
        from . import spatial
        return spatial.to_geopandas(source, fetch = True)

    # -- context manager ----------------------------------------------------

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # -- core ---------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        if_none_match: str | None = None,
    ) -> Reply:
        headers = {"If-None-Match": if_none_match} if if_none_match else None
        resp = self._http.request(
            method, path, params = _clean(params), json = json, headers = headers
        )
        request_id = resp.headers.get("X-Request-Id")
        if resp.status_code == 304:
            return Reply(
                data = None, status = 304, not_modified = True,
                etag = resp.headers.get("ETag"), request_id = request_id,
            )
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            if not isinstance(body, dict):
                body = {"title": str(body)}
            raise errors.error_from_problem(
                resp.status_code, body, request_id,
                _retry_after(resp.headers.get("Retry-After")),
            )
        return Reply(
            data = resp.json() if resp.content else None,
            status = resp.status_code,
            tokens_charged = _int(resp.headers.get("X-Tokens-Charged")),
            tokens_remaining = _int(resp.headers.get("X-Tokens-Remaining")),
            etag = resp.headers.get("ETag"),
            request_id = request_id,
        )

    def _get(self, path: str, params=None, *, if_none_match=None) -> Reply:
        return self._request("GET", path, params = params, if_none_match = if_none_match)

    # -- catalog (free) -----------------------------------------------------

    def health(self) -> Reply:
        """Liveness check (free). Touches no database."""
        return self._get("/v1/health")

    def last_updated(self) -> Reply:
        """Publication timestamp of the newest published data (free)."""
        return self._get("/v1/last-updated")

    def modes(self) -> Reply:
        """The travel modes and their numeric ids (free)."""
        return self._get("/v1/meta/modes")

    def destination_types(self) -> Reply:
        """The destination-type taxonomy with leaf expansions (free)."""
        return self._get("/v1/meta/destination-types")

    def vintage(self) -> Reply:
        """The active version of each dataset component (free)."""
        return self._get("/v1/meta/vintage")

    def places(self, q: str, *, limit: int | None = None) -> Reply:
        """Search census places by name (free). Each match carries the place's
        GEOID and WGS84 centroid. Feed a centre into `blocks_query(center=...)`,
        or a GEOID into `place_blocks(...)`. `q` is a name substring; `limit`
        caps the matches (1 to 20)."""
        return self._get("/v1/places", {"q": q, "limit": limit})

    # -- origin block / point (metered) -------------------------------------

    def block_summary(
        self, geoid: str, *, mode = None, type = None, if_none_match: str | None = None
    ) -> Reply:
        """Fastest travel time to each destination category from a census block,
        by mode. `geoid` is a 15-digit block GEOID; `mode`/`type` are optional
        filters (scalar or list). Supports `if_none_match` (ETag/304)."""
        return self._get(
            f"/v1/blocks/{geoid}/summary",
            {"mode": mode, "type": type}, if_none_match = if_none_match,
        )

    def block_pois(
        self, geoid: str, *, mode = None, type = None, dest_id = None,
        max_minutes = None, limit = None,
    ) -> Paginator:
        """Every nearby POI and its travel time from a block, one row per (POI,
        mode). Returns a GeoDataFrame of points, or a `Paginator` when the client
        was built with `spatial=False`."""
        return self._spatial(Paginator(
            self, "GET", f"/v1/blocks/{geoid}/pois",
            _clean({"mode": mode, "type": type, "dest_id": dest_id,
                    "max_minutes": max_minutes, "limit": limit}),
        ))

    def point_summary(
        self, lat: float, lon: float, *, mode = None, type = None,
        if_none_match: str | None = None,
    ) -> Reply:
        """Like `block_summary`, but from the census block containing a lat/lon.
        The resolved block GEOID is echoed as `resolved_block`."""
        return self._get(
            "/v1/point/summary",
            {"lat": lat, "lon": lon, "mode": mode, "type": type},
            if_none_match = if_none_match,
        )

    def point_pois(
        self, lat: float, lon: float, *, mode = None, type = None, dest_id = None,
        max_minutes = None, limit = None,
    ) -> Paginator:
        """Like `block_pois`, but from the block containing a lat/lon. Returns a
        GeoDataFrame of points, or a `Paginator` when `spatial=False`."""
        return self._spatial(Paginator(
            self, "GET", "/v1/point/pois",
            _clean({"lat": lat, "lon": lon, "mode": mode, "type": type,
                    "dest_id": dest_id, "max_minutes": max_minutes, "limit": limit}),
        ))

    # -- POI search / detail / catchment (metered) --------------------------

    def pois_search(
        self, *, lat = None, lon = None, radius_m = None, bbox = None, type = None,
        q = None, limit = None,
    ) -> Paginator:
        """Search POIs by bounding box (``bbox``) or radius (``lat`` + ``lon`` +
        ``radius_m``). Returns a GeoDataFrame of points, or a `Paginator` when
        `spatial=False`."""
        return self._spatial(Paginator(
            self, "GET", "/v1/pois",
            _clean({"lat": lat, "lon": lon, "radius_m": radius_m, "bbox": bbox,
                    "type": type, "q": q, "limit": limit}),
        ))

    def poi(self, dest_id: int, *, if_none_match: str | None = None):
        """Name, location, address, types, and whitelisted attributes for one POI.
        Returns a one-row GeoDataFrame of a point, or a `Reply` when
        `spatial=False`."""
        return self._spatial(
            self._get(f"/v1/pois/{dest_id}", if_none_match = if_none_match)
        )

    def poi_catchment(
        self, dest_id: int, *, mode = None, block = None, max_minutes = None,
        limit = None,
    ) -> Paginator:
        """Every census block that can reach a POI, one row per (block, mode).
        Returns a GeoDataFrame of block polygons, or a `Paginator` when
        `spatial=False`."""
        return self._spatial(Paginator(
            self, "GET", f"/v1/pois/{dest_id}/catchment",
            _clean({"mode": mode, "block": block, "max_minutes": max_minutes,
                    "limit": limit}),
        ))

    # -- areal (metered) ----------------------------------------------------

    def blocks_query(
        self, *, polygon: dict | None = None, center: dict | None = None,
        radius_m: float | None = None, type: Sequence[int] | None = None,
        mode: Sequence[str] | None = None, include_population: bool | None = None,
        limit: int | None = None,
    ) -> Paginator:
        """Blocks within a GeoJSON ``polygon`` or a ``center`` + ``radius_m``.
        Returns a GeoDataFrame of block polygons, or a `Paginator` when
        `spatial=False`."""
        body = _clean({
            "polygon": polygon, "center": center, "radius_m": radius_m,
            "type": _as_list(type), "mode": _as_list(mode),
            "include_population": include_population, "limit": limit,
        })
        return self._spatial(Paginator(self, "POST", "/v1/blocks/query",
                                       _json = body, _cursor_in = "json"))

    def place_blocks(
        self, geoid: str, *, mode = None, type = None, include_population = None,
        limit = None,
    ) -> Paginator:
        """Per-block travel times for every census block in a place (city or
        town), by place GEOID. Returns a GeoDataFrame of block polygons, or a
        `Paginator` when `spatial=False`."""
        return self._spatial(Paginator(
            self, "GET", f"/v1/places/{geoid}/blocks",
            _clean({"mode": mode, "type": type,
                    "include_population": include_population, "limit": limit}),
        ))

    # -- isochrone ----------------------------------------------------------

    def isochrone(
        self, *, block = None, lon = None, lat = None, mode = None, direction = None,
        minutes = None, contours = None, format = None, v = None,
        if_none_match: str | None = None,
    ):
        """Travel-time contours from a ``block`` (GEOID) or ``lon`` + ``lat``.
        Pass ``minutes`` (single) or ``contours`` (up to 4 ascending levels, a
        list or a comma string). Returns a GeoDataFrame of contour polygons, or a
        `Reply` when `spatial=False` or `format="blocks"`."""
        if isinstance(contours, (list, tuple)):
            contours = ",".join(str(c) for c in contours)
        reply = self._get(
            "/v1/isochrone",
            {"block": block, "lon": lon, "lat": lat, "mode": mode,
             "direction": direction, "minutes": minutes, "contours": contours,
             "format": format, "v": v},
            if_none_match = if_none_match,
        )
        return reply if format == "blocks" else self._spatial(reply)

    def isochrone_meta(self, *, if_none_match: str | None = None) -> Reply:
        """The active isochrone store version, available directions/modes, and the
        routing assumptions (free, keyless)."""
        return self._get("/v1/isochrone/meta", if_none_match = if_none_match)
