# Changelog

## 1.5.0

- Multi-origin calls. `block_summary`, `block_pois`, `point_summary`,
  `point_pois`, and `poi_catchment` now accept many origins in one request:
  pass a list of GEOIDs (or `dest_id`s), or a list of `(lat, lon)` points, and
  the whole set is queried in a single call — one request against the
  300/minute rate limit instead of one per origin. Results come back as a flat
  frame tagged by origin (`geoid`, or `origin_lat` / `origin_lon`, or
  `dest_id`); per-origin `errors` and any `truncated` origins ride on
  `df.attrs`. A batch is charged only for what the account can pay for, so a
  huge query stops at the balance rather than overspending.

## 1.4.0

- `Client.place_boundary(geoid)` — the boundary polygon of a census place, as a
  one-row GeoDataFrame. Free (no API key); handy as a `boundary` layer for
  `close_map`.
- `close_map` gains layered context and smarter defaults: it auto-zooms to the
  data, shows every attribute on hover, defaults to the ColorBrewer `YlGnBu`
  scale (blue = most accessible), and takes a `boundary` outline and
  semi-transparent `background` layers (e.g. a city boundary, commute isochrones,
  or a walkshed under its POIs). A `mark` argument drops an X on a point of
  interest (e.g. a starting point).

## 1.3.0

- `Client.place_pois(geoid, ...)` — every point of interest within a census
  place (city or town), by place GEOID. The place analog of `pois_search`; pass
  `type` to get, e.g., all supermarkets in a city.
- `close_map(gdf, ...)` — a one-line interactive map (CARTO Positron basemap,
  hoverable points, or filled blocks that highlight the features meeting a
  criterion) for the GeoDataFrames the client returns. Built on plotly (the
  `closecity[maps]` extra); GDAL-free.
- `places()` results now carry a `state` column (two-letter USPS abbreviation),
  so same-named places are distinguishable.

## 1.2.0

- `Client()` reads the `CLOSECITY_KEY` environment variable when no `api_key` is
  passed, so scripts and agents can authenticate without hardcoding the key. A
  401 with no key set now carries an actionable hint pointing at `CLOSECITY_KEY`
  and the free-signup page (`err.hint`).
- Ship the PEP 561 `py.typed` marker so downstream type checkers (mypy, pyright)
  see the inline type hints.
- Document that the client does not retry: on `RateLimitedError` /
  `ServiceUnavailableError`, wait `err.retry_after` seconds and retry yourself.

## 1.1.0

Tabular results by default, across every route.

- New `output` mode replaces the `spatial` flag: `Client(output = "spatial")` (the
  default) returns a `GeoDataFrame` where geometry applies and a plain
  `pandas.DataFrame` for catalog and summary routes; `output = "tabular"` returns a
  plain `DataFrame` everywhere and never downloads block boundaries (the cheap path
  when you only want the numbers); `output = "raw"` returns the underlying `Reply` /
  `Paginator`. Set it on the client or per call.
- Catalog routes (`modes()`, `destination_types()`, `vintage()`, `places()`) and
  the block and point summaries now return data frames instead of nested replies.
  `block_summary()` / `point_summary()` broadcast the origin GEOID to a `geoid`
  column. `isochrone(format = "blocks")` now converts too.
- Metering and envelope metadata (`tokens_charged`, `tokens_remaining`, `etag`,
  `block_geoid`, `assumptions`, ...) ride on `df.attrs`.
- New `to_pandas()` module function and `Reply.to_pandas()` / `Paginator.to_pandas()`
  methods, beside the existing geopandas ones. `pandas` is now a direct dependency.

## 1.0.0

First public release of the `closecity` Python client for the Close API
(api.close.city).

- A typed `Client` over the metered, read-only public endpoints: catalog, place
  lookup, block and point summaries and POIs, POI search, detail, and catchment,
  areal block queries, and isochrones.
- Feature methods return `geopandas.GeoDataFrame` objects by default. Pass
  `spatial=False` for the raw `Reply` / `Paginator`. Block boundaries are joined
  with `pygris` (the `tiger` extra).
- First-class metering (`tokens_charged`, `tokens_remaining`), ETag/304 conditional
  requests, keyset pagination (`Paginator`), and typed RFC 9457 errors.
- `places()` looks up a city or town by name and returns its GEOID and centre.
