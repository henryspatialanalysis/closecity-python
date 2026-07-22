# Changelog

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
