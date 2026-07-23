"""A thin, typed client for the Close API (https://api.close.city).

Design goals: mirror the public OpenAPI contract exactly, surface the metering
and conditional-request mechanics (token headers, ETag/304) as first-class, map
``problem+json`` errors to precise exceptions, and iterate keyset-paginated
endpoints transparently. Cursors are opaque and never constructed client-side.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import errors

__all__ = ["Client", "Reply", "Paginator"]

DEFAULT_BASE_URL = "https://api.close.city"

# The three output modes, shared with the R SDK. "spatial" returns a GeoDataFrame
# where geometry applies (and a plain DataFrame otherwise); "tabular" returns a
# plain DataFrame everywhere and never downloads block boundaries; "raw" returns
# the underlying Reply / Paginator.
OUTPUT_MODES = ("spatial", "tabular", "raw")


def _check_output(mode: str) -> str:
    if mode not in OUTPUT_MODES:
        raise ValueError(
            f"output must be one of {OUTPUT_MODES}, not {mode!r}."
        )
    return mode


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop None-valued params (so optional filters simply vanish)."""
    return {k: v for k, v in (params or {}).items() if v is not None}


def _as_list(value: Any) -> Any:
    """Wrap a scalar in a list, for POST-body fields the API requires as arrays.
    ``None`` and existing lists/tuples pass through unchanged."""
    if value is None or isinstance(value, (list, tuple)):
        return value
    return [value]


def _point_origins(points: Any) -> list[dict[str, float]]:
    """Normalise a batch of point origins to ``[{"lon": .., "lat": ..}, ...]``.

    Each item is either a ``(lat, lon)`` pair — matching the ``(lat, lon)``
    argument order of the single-point calls — or a ``{"lat": .., "lon": ..}``
    mapping.
    """
    out: list[dict[str, float]] = []
    for point in points:
        if isinstance(point, dict):
            out.append({"lon": point["lon"], "lat": point["lat"]})
        else:
            lat, lon = point
            out.append({"lon": lon, "lat": lat})
    return out


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

    def to_pandas(self, **kwargs):
        """Convert this reply to a :class:`pandas.DataFrame` (no geometry). See
        :func:`closecity.tabular.to_pandas`.
        """
        from . import tabular
        return tabular.to_pandas(self, **kwargs)


@dataclass
class Paginator:
    """Lazily follows ``next_cursor`` across pages.

    Iterate it directly to get every record; use :meth:`pages` for per-page
    :class:`Reply` objects (each carrying its own token/ETag metadata); use
    :meth:`page` to fetch a single page.
    """

    _client: Client
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

    def to_pandas(self, **kwargs):
        """Collect every page and convert the rows to a
        :class:`pandas.DataFrame`. See :func:`closecity.tabular.to_pandas`.
        """
        from . import tabular
        return tabular.to_pandas(self, **kwargs)


class Client:
    """Client for the Close API.

    ``api_key`` is optional (the catalog and health routes are free), but every
    data route needs one (a ``ck_live_`` key), created at
    https://account.close.city (5,000 free tokens on signup, no card). When
    ``api_key`` is not given, the ``CLOSECITY_KEY`` environment variable is used
    if set. Usable as a context manager.

    ``output`` sets how results come back, and defaults to ``"spatial"``:

    * ``"spatial"`` returns a :class:`geopandas.GeoDataFrame` for routes with
      geometry (points, isochrone and block polygons) and a plain
      :class:`pandas.DataFrame` for the rest;
    * ``"tabular"`` returns a plain :class:`pandas.DataFrame` for every route and
      never downloads block boundaries (the cheap path when you only want the
      numbers);
    * ``"raw"`` returns the underlying :class:`Reply` / :class:`Paginator`.

    Set it on the client (``close.output = "raw"``) or per call
    (``close.blocks_query(..., output = "tabular")``).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        output: str = "spatial",
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        if api_key is None:
            api_key = os.getenv("CLOSECITY_KEY") or None
        self._has_key = bool(api_key)
        self.output = _check_output(output)
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = http_client or httpx.Client(
            base_url = base_url.rstrip("/"), timeout = timeout, headers = headers,
            transport = transport,
        )

    def _resolve_output(self, output: str | None) -> str:
        return _check_output(output if output is not None else self.output)

    def _deliver(self, source, *, geometry: bool, key: str | None = None,
                 output: str | None = None):
        """Return ``source`` shaped per the resolved output mode. ``geometry``
        says whether this route can carry geometry in ``spatial`` mode; ``key``
        names the record array for the tabular path."""
        mode = self._resolve_output(output)
        if mode == "raw":
            return source
        # A 304 revalidation has no body to convert.
        if isinstance(source, Reply) and source.not_modified:
            return source
        if mode == "spatial" and geometry:
            from . import spatial
            return spatial.to_geopandas(source, fetch = True)
        from . import tabular
        return tabular.to_pandas(source, key = key)

    # -- context manager ----------------------------------------------------

    def __enter__(self) -> Client:
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
            hint = None
            if resp.status_code == 401 and not self._has_key:
                hint = (
                    "No API key set. Pass Client(api_key=...) or set the "
                    "CLOSECITY_KEY environment variable. Create a free key "
                    "(5,000 tokens, no card) at https://account.close.city."
                )
            raise errors.error_from_problem(
                resp.status_code, body, request_id,
                _retry_after(resp.headers.get("Retry-After")), hint,
            )
        return Reply(
            data = resp.json() if resp.content else None,
            status = resp.status_code,
            tokens_charged = _int(resp.headers.get("X-Tokens-Charged")),
            tokens_remaining = _int(resp.headers.get("X-Tokens-Remaining")),
            etag = resp.headers.get("ETag"),
            request_id = request_id,
        )

    def _get(self, path: str, params = None, *, if_none_match = None) -> Reply:
        return self._request("GET", path, params = params, if_none_match = if_none_match)

    # -- catalog (free) -----------------------------------------------------

    def health(self) -> Reply:
        """Liveness check (free). Touches no database. Always a raw `Reply`."""
        return self._get("/v1/health")

    def last_updated(self) -> Reply:
        """Publication timestamp of the newest published data (free). Always a
        raw `Reply`."""
        return self._get("/v1/last-updated")

    def modes(self, *, output: str | None = None):
        """The travel modes and their numeric ids (free). A DataFrame of
        `mode_id, mode, description`, or a raw `Reply` when `output="raw"`."""
        return self._deliver(self._get("/v1/meta/modes"),
                             geometry = False, key = "modes", output = output)

    def destination_types(self, *, output: str | None = None):
        """The destination-type taxonomy with leaf expansions (free). A DataFrame
        of `dest_type_id, name, label, is_leaf, leaf_ids`, or a raw `Reply` when
        `output="raw"`. Filtering by a parent type expands to its `leaf_ids`."""
        return self._deliver(self._get("/v1/meta/destination-types"),
                             geometry = False, key = "destination_types",
                             output = output)

    def vintage(self, *, output: str | None = None):
        """The active version of each dataset component (free). A DataFrame of
        `component, version, effective_date`, or a raw `Reply`."""
        return self._deliver(self._get("/v1/meta/vintage"),
                             geometry = False, key = "components", output = output)

    def places(self, q: str, *, limit: int | None = None, output: str | None = None):
        """Search census places by name (free). Each match carries the place's
        GEOID and WGS84 centroid. Feed a centre into `blocks_query(center=...)`,
        or a GEOID into `place_blocks(...)`. `q` is a name substring; `limit`
        caps the matches (1 to 20). A points GeoDataFrame (or a plain DataFrame
        under `output="tabular"`, a raw `Reply` under `output="raw"`)."""
        return self._deliver(self._get("/v1/places", {"q": q, "limit": limit}),
                             geometry = True, key = "places", output = output)

    # -- origin block / point (metered) -------------------------------------

    def block_summary(
        self, geoid, *, mode = None, type = None,
        if_none_match: str | None = None, output: str | None = None,
    ):
        """Fastest travel time to each destination category from a census block,
        by mode. `geoid` is a 15-digit block GEOID; `mode`/`type` are optional
        filters (scalar or list). Supports `if_none_match` (ETag/304). A DataFrame
        (the origin GEOID broadcast to a `geoid` column), or a raw `Reply`.

        Pass a **list of GEOIDs** to query many blocks in one call (one request,
        one rate-limit tick): the frame is the flat, `geoid`-tagged union of every
        origin's rows, and per-origin `errors` / `truncated` / `truncated_reason`
        ride on `df.attrs`. `if_none_match` applies to the single-block form only.
        """
        if isinstance(geoid, (list, tuple)):
            reply = self._request("POST", "/v1/blocks/summary", json = _clean(
                {"origins": list(geoid), "mode": _as_list(mode),
                 "type": _as_list(type)}))
            return self._deliver(reply, geometry = False, key = "results",
                                 output = output)
        return self._deliver(
            self._get(f"/v1/blocks/{geoid}/summary",
                      {"mode": mode, "type": type}, if_none_match = if_none_match),
            geometry = False, key = "results", output = output,
        )

    def block_pois(
        self, geoid, *, mode = None, type = None, dest_id = None,
        max_minutes = None, limit = None, output: str | None = None,
    ):
        """Every nearby POI and its travel time from a block, one row per (POI,
        mode). A GeoDataFrame of points (a plain DataFrame under
        `output="tabular"`, a `Paginator` under `output="raw"`).

        Pass a **list of GEOIDs** to query many blocks in one call (one request,
        one rate-limit tick): rows are the flat, `geoid`-tagged union of every
        origin's POIs, with per-origin `errors` / `truncated` / `truncated_reason`
        on `df.attrs`. The batch form is not paginated (`limit` is ignored)."""
        if isinstance(geoid, (list, tuple)):
            reply = self._request("POST", "/v1/blocks/pois", json = _clean(
                {"origins": list(geoid), "mode": _as_list(mode),
                 "type": _as_list(type), "dest_id": _as_list(dest_id),
                 "max_minutes": max_minutes}))
            return self._deliver(reply, geometry = True, output = output)
        return self._deliver(Paginator(
            self, "GET", f"/v1/blocks/{geoid}/pois",
            _clean({"mode": mode, "type": type, "dest_id": dest_id,
                    "max_minutes": max_minutes, "limit": limit}),
        ), geometry = True, output = output)

    def point_summary(
        self, lat, lon = None, *, mode = None, type = None,
        if_none_match: str | None = None, output: str | None = None,
    ):
        """Like `block_summary`, but from the census block containing a lat/lon.
        The resolved block GEOID is echoed as `resolved_block` and broadcast to a
        `geoid` column. A DataFrame, or a raw `Reply`.

        Pass a **list of points** as the first argument — each a `(lat, lon)` pair
        or a `{"lat": .., "lon": ..}` mapping — to query many points in one call.
        Each row is tagged with its `origin_lat` / `origin_lon`; resolved blocks,
        `errors`, and `truncated` ride on `df.attrs`."""
        if isinstance(lat, (list, tuple)):
            if lon is not None:
                raise ValueError(
                    "For multiple points pass a list of (lat, lon) pairs as the "
                    "first argument and leave lon unset."
                )
            reply = self._request("POST", "/v1/point/summary", json = _clean(
                {"origins": _point_origins(lat), "mode": _as_list(mode),
                 "type": _as_list(type)}))
            return self._deliver(reply, geometry = False, key = "results",
                                 output = output)
        return self._deliver(
            self._get("/v1/point/summary",
                      {"lat": lat, "lon": lon, "mode": mode, "type": type},
                      if_none_match = if_none_match),
            geometry = False, key = "results", output = output,
        )

    def point_pois(
        self, lat, lon = None, *, mode = None, type = None, dest_id = None,
        max_minutes = None, limit = None, output: str | None = None,
    ):
        """Like `block_pois`, but from the block containing a lat/lon. A
        GeoDataFrame of points (a plain DataFrame under `output="tabular"`, a
        `Paginator` under `output="raw"`).

        Pass a **list of points** as the first argument — each a `(lat, lon)` pair
        or a `{"lat": .., "lon": ..}` mapping — to query many points in one call.
        Each row is tagged with its `origin_lat` / `origin_lon`. The batch form is
        not paginated (`limit` is ignored)."""
        if isinstance(lat, (list, tuple)):
            if lon is not None:
                raise ValueError(
                    "For multiple points pass a list of (lat, lon) pairs as the "
                    "first argument and leave lon unset."
                )
            reply = self._request("POST", "/v1/point/pois", json = _clean(
                {"origins": _point_origins(lat), "mode": _as_list(mode),
                 "type": _as_list(type), "dest_id": _as_list(dest_id),
                 "max_minutes": max_minutes}))
            return self._deliver(reply, geometry = True, output = output)
        return self._deliver(Paginator(
            self, "GET", "/v1/point/pois",
            _clean({"lat": lat, "lon": lon, "mode": mode, "type": type,
                    "dest_id": dest_id, "max_minutes": max_minutes, "limit": limit}),
        ), geometry = True, output = output)

    # -- POI search / detail / catchment (metered) --------------------------

    def pois_search(
        self, *, lat = None, lon = None, radius_m = None, bbox = None, type = None,
        q = None, limit = None, output: str | None = None,
    ):
        """Search POIs by bounding box (``bbox``) or radius (``lat`` + ``lon`` +
        ``radius_m``). A GeoDataFrame of points (a plain DataFrame under
        `output="tabular"`, a `Paginator` under `output="raw"`)."""
        return self._deliver(Paginator(
            self, "GET", "/v1/pois",
            _clean({"lat": lat, "lon": lon, "radius_m": radius_m, "bbox": bbox,
                    "type": type, "q": q, "limit": limit}),
        ), geometry = True, output = output)

    def poi(self, dest_id: int, *, if_none_match: str | None = None,
            output: str | None = None):
        """Name, location, address, types, and whitelisted attributes for one POI.
        A one-row points GeoDataFrame (a plain DataFrame under `output="tabular"`,
        a `Reply` under `output="raw"`)."""
        return self._deliver(
            self._get(f"/v1/pois/{dest_id}", if_none_match = if_none_match),
            geometry = True, output = output,
        )

    def poi_catchment(
        self, dest_id, *, mode = None, block = None, max_minutes = None,
        limit = None, output: str | None = None,
    ):
        """Every census block that can reach a POI, one row per (block, mode).
        A GeoDataFrame of block polygons (a plain DataFrame under
        `output="tabular"`, a `Paginator` under `output="raw"`).

        Pass a **list of dest_ids** to query many POIs in one call (one request,
        one rate-limit tick): rows are the flat, `dest_id`-tagged union of every
        POI's catchment, with per-POI `errors` / `truncated` on `df.attrs`. The
        batch form is not paginated (`limit` is ignored)."""
        if isinstance(dest_id, (list, tuple)):
            reply = self._request("POST", "/v1/pois/catchment", json = _clean(
                {"dest_ids": list(dest_id), "mode": _as_list(mode),
                 "block": _as_list(block), "max_minutes": max_minutes}))
            return self._deliver(reply, geometry = True, output = output)
        return self._deliver(Paginator(
            self, "GET", f"/v1/pois/{dest_id}/catchment",
            _clean({"mode": mode, "block": block, "max_minutes": max_minutes,
                    "limit": limit}),
        ), geometry = True, output = output)

    # -- areal (metered) ----------------------------------------------------

    def blocks_query(
        self, *, polygon: dict | None = None, center: dict | None = None,
        radius_m: float | None = None, type: Sequence[int] | None = None,
        mode: Sequence[str] | None = None, include_population: bool | None = None,
        limit: int | None = None, output: str | None = None,
    ):
        """Blocks within a GeoJSON ``polygon`` or a ``center`` + ``radius_m``.
        Rows carry the numeric `mode_id` (join `modes()` to label it). A
        GeoDataFrame of block polygons (a plain DataFrame under
        `output="tabular"`, a `Paginator` under `output="raw"`)."""
        body = _clean({
            "polygon": polygon, "center": center, "radius_m": radius_m,
            "type": _as_list(type), "mode": _as_list(mode),
            "include_population": include_population, "limit": limit,
        })
        return self._deliver(
            Paginator(self, "POST", "/v1/blocks/query",
                      _json = body, _cursor_in = "json"),
            geometry = True, output = output,
        )

    def place_blocks(
        self, geoid: str, *, mode = None, type = None, include_population = None,
        limit = None, output: str | None = None,
    ):
        """Per-block travel times for every census block in a place (city or
        town), by place GEOID. Rows carry the numeric `mode_id` (join `modes()`
        to label it). A GeoDataFrame of block polygons (a plain DataFrame under
        `output="tabular"`, a `Paginator` under `output="raw"`)."""
        return self._deliver(Paginator(
            self, "GET", f"/v1/places/{geoid}/blocks",
            _clean({"mode": mode, "type": type,
                    "include_population": include_population, "limit": limit}),
        ), geometry = True, output = output)

    def place_pois(
        self, geoid: str, *, type = None, q = None, limit = None,
        output: str | None = None,
    ):
        """Every point of interest within a census place (city or town), by
        place GEOID. The place analog of `pois_search`; pass `type` to get,
        e.g., all supermarkets in a city. Spatial only — no travel times. A
        GeoDataFrame of points (a plain DataFrame under `output="tabular"`, a
        `Paginator` under `output="raw"`)."""
        return self._deliver(Paginator(
            self, "GET", f"/v1/places/{geoid}/pois",
            _clean({"type": type, "q": q, "limit": limit}),
        ), geometry = True, output = output)

    def place_boundary(self, geoid: str, *, output: str | None = None):
        """The boundary polygon of a census place (city or town), by place GEOID.
        Handy as a `boundary` layer for `close_map` when mapping a city's blocks
        or POIs. Free (no API key). A one-row polygon GeoDataFrame (a `Reply`
        under `output="raw"`)."""
        reply = self._get(f"/v1/places/{geoid}/boundary")
        if self._resolve_output(output) == "raw":
            return reply
        from . import spatial
        return spatial.to_geopandas(reply)

    # -- isochrone ----------------------------------------------------------

    def isochrone(
        self, *, block = None, lon = None, lat = None, mode = None, direction = None,
        minutes = None, contours = None, format = None, v = None,
        if_none_match: str | None = None, output: str | None = None,
    ):
        """Travel-time contours from a ``block`` (GEOID) or ``lon`` + ``lat``.
        Pass ``minutes`` (single) or ``contours`` (up to 4 ascending levels, a
        list or a comma string). In `spatial` mode `format="geojson"` gives
        contour polygons and `format="blocks"` gives block polygons; `tabular`
        gives the matching rows; `raw` gives a `Reply`."""
        if isinstance(contours, (list, tuple)):
            contours = ",".join(str(c) for c in contours)
        reply = self._get(
            "/v1/isochrone",
            {"block": block, "lon": lon, "lat": lat, "mode": mode,
             "direction": direction, "minutes": minutes, "contours": contours,
             "format": format, "v": v},
            if_none_match = if_none_match,
        )
        return self._deliver(reply, geometry = True, output = output)

    def isochrone_meta(self, *, if_none_match: str | None = None) -> Reply:
        """The active isochrone store version, available directions/modes, and the
        routing assumptions (free, keyless). Always a raw `Reply`."""
        return self._get("/v1/isochrone/meta", if_none_match = if_none_match)
