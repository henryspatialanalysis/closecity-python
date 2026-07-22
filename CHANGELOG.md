# Changelog

## 1.0.0

First public release of the `closecity` Python client for the Close API
(api.close.city).

- A thin, typed `Client` over the metered, read-only public endpoints: catalog,
  block/point summaries and POIs, POI search/detail/catchment, areal block
  queries, and isochrones.
- First-class metering (`tokens_charged` / `tokens_remaining`), ETag/304
  conditional requests, keyset pagination (`Paginator`), and typed RFC 9457
  errors.
- `places()` place-name lookup (city/town → GEOID + centroid).
- Opt-in spatial output: `Reply.to_geopandas()` / `Paginator.to_geopandas()`
  (POI points, isochrone polygons, and census-block joins) under the `geo` extra.
