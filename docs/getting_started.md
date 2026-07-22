---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# Getting started

A short tour of the client. The tutorials go further.

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Words you will see

A few terms come up throughout:

- **Census block.** The smallest area the Census Bureau publishes. Each one has a
  15-digit id, its **GEOID**.
- **Destination type.** A category of place, such as grocery stores or libraries.
  Every type has a numeric id.
- **Mode.** How someone travels: walk, bike, or transit.
- **Isochrone.** The area reachable from a point within a time limit, as a polygon.
- **Catchment.** The reverse: every block that can reach a given place.

## Build a client

You make every request through a client.

```python
from closecity import Client

close = Client("ck_live_your_key")   # use your own key here
```

The catalog and lookup routes are free, so `Client()` with no key works for those.

```{code-cell} python
close.modes().data["modes"]
```

## Look things up instead of guessing

Read the numeric id for a category from the catalog, and turn a city name into a
GEOID and a centre point.

```{code-cell} python
types = close.destination_types().data["destination_types"]
ids = {t["label"]: t["dest_type_id"] for t in types}
grocery = ids["grocery_stores"]

providence = close.places("Providence").data["places"][0]
providence["geoid"]
```

## Make a call and map it

Feature methods return a GeoDataFrame, so you can map the result straight away.

```{code-cell} python
groceries = close.pois_search(lat = providence["lat"], lon = providence["lon"],
                              radius_m = 1500, type = grocery)
groceries.plot(color = "#202a5b")
```

## Turn spatial output off

Set the client's `spatial` flag to `False` to work with the raw data.

```{code-cell} python
close.spatial = False
summary = close.block_summary("440070036001010", mode = "walk")
summary.results
```

## Errors

Problem responses become typed exceptions.

```{code-cell} python
from closecity import CloseAPIError

try:
    close.block_summary("000000000000000")
except CloseAPIError as err:
    print(err.status, err.slug)
```
