# Changelog

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
