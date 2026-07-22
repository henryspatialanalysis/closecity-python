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
They come back as data frames:

```{code-cell} python
close.modes()
```

## Look things up instead of guessing

Read the numeric id for a category from the catalog, and turn a city name into a
GEOID and a centre point. Both are plain data frames, so you filter and index them
the usual way.

```{code-cell} python
types = close.destination_types()
grocery = types.loc[types["label"] == "grocery_stores", "dest_type_id"].iloc[0]

matches = close.places("Providence")
providence = matches.iloc[0]
providence["geoid"]
```

## Make a call and map it

Routes with geometry return a GeoDataFrame, so you can map the result straight
away.

```{code-cell} python
groceries = close.pois_search(lat = providence["lat"], lon = providence["lon"],
                              radius_m = 1500, type = grocery)
groceries.plot(color = "#202a5b")
```

## Choose an output

Every route returns tabular data by default. The `output` setting controls the
shape:

- `"spatial"` (the default) returns a GeoDataFrame where geometry applies, and a
  plain DataFrame otherwise.
- `"tabular"` returns a plain DataFrame for every route and never downloads block
  boundaries. Reach for it when you only want the numbers.
- `"raw"` returns the underlying reply, with the parsed body on `.data` and the
  token counts alongside.

Set it on the client, or pass `output=` to a single call.

```{code-cell} python
close.output = "raw"
summary = close.block_summary("440070008001068", mode = "walk")
summary.results
```

```{code-cell} python
:tags: [remove-cell]
close.output = "spatial"
```

In the frame modes, the token counts and other reply metadata ride on `df.attrs`.

## Errors

Problem responses become typed exceptions.

```{code-cell} python
from closecity import CloseAPIError

try:
    close.block_summary("000000000000000")
except CloseAPIError as err:
    print(err.status, err.slug)
```
