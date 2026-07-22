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

This pulls in `httpx` and `geopandas`, so feature methods return GeoDataFrames out
of the box.

## A first call

You make requests through a client. Feature results come back as GeoDataFrames, so
you can map them right away.

```python
from closecity import Client

# The key (ck_live_ or ck_test_) comes from https://account.close.city
close = Client("ck_live_your_key")   # use your own key here

# Grocery stores within a 1.5 km walk of a point, as points:
groceries = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500, type = 30)
groceries.plot()
```

Catalog and lookup routes are free and need no key:

```python
close = Client()
close.modes().data["modes"]                    # walk, bike, transit
close.places("Providence").data["places"][0]   # a city name to its GEOID and centre
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

## Spatial output, on or off

Feature methods return GeoDataFrames by default. Block routes join census-block
boundaries for you, using `pygris` (the `tiger` extra) to download them once. To work
with the raw data instead, build the client with `spatial=False`:

```python
close = Client("ck_live_your_key", spatial = False)   # use your own key here
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
