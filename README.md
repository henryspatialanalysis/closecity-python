# closecity

Python client for the Close API. Get travel times from every US census block to
nearby places, on foot, by bike, and by public transit. This is the data behind
[close.city](https://close.city), read over the [Close API](https://api.close.city).

**Documentation:** https://henryspatialanalysis.github.io/closecity-python/

## Install

```bash
pip install closecity
pip install "closecity[tiger]"   # to auto-download census-block boundaries
```

This pulls in `httpx`, `pandas`, and `geopandas`, so results come back as data
frames out of the box: a GeoDataFrame where geometry applies, a plain DataFrame
otherwise.

## A first call

You make requests through a client. Routes with geometry come back as
GeoDataFrames, so you can map them right away.

```python
from closecity import Client

# The key (ck_live_) comes from https://account.close.city (5,000 free tokens
# on signup, no card). You can also set the CLOSECITY_KEY environment variable
# and call Client() with no argument.
close = Client("ck_live_your_key")   # use your own key here

# Grocery stores within a 1.5 km walk of a point, as points:
groceries = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500, type = 30)
groceries.plot()
```

Catalog and lookup routes are free, need no key, and come back as data frames:

```python
close = Client()
close.modes()                  # walk, bike, transit
close.places("Providence")     # a city name to its GEOID and centre
```

## Words you will see

A few terms come up throughout the API:

- **Census block.** The smallest area the Census Bureau publishes. Each one has a
  15-digit id called a **GEOID**.
- **Destination type.** A category of place, such as grocery stores or libraries.
  Each type has a numeric id. Look them up with `close.destination_types()`.
- **Mode.** How someone travels: walk, bike, or transit.
- **Isochrone.** The area you can reach from a point within a time limit, as a
  polygon.
- **Catchment.** The reverse of an isochrone: every block that can reach a place.

## Choosing an output

Set `output` on the client, or per call:

- `output = "spatial"` (the default) returns a GeoDataFrame where geometry applies
  and a DataFrame otherwise. Block routes join census-block boundaries with
  `pygris` (the `tiger` extra), downloaded once and cached.
- `output = "tabular"` returns a plain DataFrame for every route and never
  downloads boundaries. Reach for it when you only want the numbers.
- `output = "raw"` returns the underlying `Reply` / `Paginator`, with the parsed
  body on `.data` and the token counts alongside.

```python
close = Client("ck_live_your_key", output = "raw")   # use your own key here
for poi in close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500):
    print(poi["name"])
```

## Handling errors

Problem responses become typed exceptions. Catch a specific one, or the
`CloseAPIError` base.

```python
from closecity import TokensExhaustedError, CloseAPIError

try:
    close.block_summary("000000000000000")
except TokensExhaustedError:
    ...
except CloseAPIError as err:
    print(err.status, err.slug)
```

The client does not retry automatically. On a `RateLimitedError` or
`ServiceUnavailableError`, wait `err.retry_after` seconds (from the
`Retry-After` header) and retry the request yourself.

## Reference

- Documentation: https://henryspatialanalysis.github.io/closecity-python/
- Interactive API: https://api.close.city/docs
- Machine-readable contract: https://api.close.city/openapi.json

## Development

```bash
pip install -e '.[dev]'
pytest        # unit tests, no network (httpx MockTransport)
ruff check src tests
```
