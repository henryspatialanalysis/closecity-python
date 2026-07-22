# closecity — Python client for the Close API

Travel times from every US census block to nearby points of interest, by walking,
biking, and public transit — the data behind [close.city](https://close.city),
over the [Close API](https://api.close.city).

**Documentation:** https://henryspatialanalysis.github.io/closecity-python/

```bash
pip install closecity
pip install "closecity[geo]"   # + GeoPandas output (to_geopandas)
```

## Quickstart

```python
from closecity import Client

# The API key (ck_live_… / ck_test_…) is created at https://account.close.city.
with Client("ck_live_your_key_here") as close:
    # Fastest travel time to each category from a census block.
    summary = close.block_summary("410390020001010", mode = ["walk", "transit"])
    for row in summary.results:
        print(row["dest_type_id"], row["mode"], row["travel_time"])

    # Metering is surfaced on every metered reply.
    print(summary.tokens_charged, "charged;", summary.tokens_remaining, "left")
```

Free routes (catalog, place lookup, health) need no key:

```python
from closecity import Client
close = Client()
print(close.modes().data["modes"])
print(close.last_updated().data["last_updated"])

# Resolve a city name to its census place GEOID + centroid:
print(close.places("Providence").data["places"][0])
```

## Pagination

List endpoints return a `Paginator` that follows the opaque keyset cursor for you.
Iterate it for every record, or use `.pages()` for per-page metadata:

```python
# Every POI near a point, across all pages:
for poi in close.pois_search(lat = 44.05, lon = -123.09, radius_m = 2000):
    print(poi["name"], poi["address"]["city"])

# Or page-by-page, watching the token balance drop:
for page in close.block_pois("410390020001010", limit = 500).pages():
    print(len(page.results), "rows;", page.tokens_remaining, "tokens left")
```

Cursors are opaque and signed — never construct or modify them.

## Conditional requests (free revalidation)

Metered `GET`s return an `ETag`. Send it back to revalidate for free — a `304`
costs no tokens, even at a zero balance:

```python
first = close.block_summary("410390020001010")
again = close.block_summary("410390020001010", if_none_match = first.etag)
if again.not_modified:
    ...  # your cached copy is still current; nothing was charged
```

## Isochrones

```python
iso = close.isochrone(block = "410390020001010", contours = [15, 30, 45],
                      mode = "walk", direction = "to")
for feature in iso.data["features"]:
    print(feature["properties"]["contour"], feature["properties"]["reachable_blocks"])
```

## Errors

Errors are [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `problem+json`,
mapped to exceptions. Catch a precise class or the `CloseAPIError` base; the stable
machine key is `err.slug`:

```python
from closecity import CloseAPIError, TokensExhaustedError, RateLimitedError

try:
    close.block_summary("000000000000000")
except TokensExhaustedError:
    ...  # buy more tokens at account.close.city
except RateLimitedError as err:
    time.sleep(err.retry_after or 1)
except CloseAPIError as err:
    print(err.slug, err.status, err.title, err.request_id)
```

## Spatial output

With `pip install "closecity[geo]"`, turn any reply into a GeoDataFrame — POIs
become points, isochrones become polygons, and block replies join census-block
boundaries:

```python
pts = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500).to_geopandas()
iso = close.isochrone(block = "440070036001010", minutes = 15).to_geopandas()
```

## Reference

- Documentation: https://henryspatialanalysis.github.io/closecity-python/
- Interactive API: https://api.close.city/docs
- Machine-readable contract: https://api.close.city/openapi.json

## Development

```bash
pip install -e '.[dev,geo]'
pytest        # unit tests (no network — httpx MockTransport)
ruff check src tests
```
