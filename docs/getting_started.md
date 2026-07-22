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
from closecity import Client, close_map
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Key terms

A few terms come up throughout:

- **Census block.** The smallest area the Census Bureau publishes. Each one has a
  15-digit id, its **GEOID**.
- **Destination type.** A category of place, such as grocery stores or libraries.
  Every type has a numeric id.
- **Mode.** How someone travels: walk, bike, or transit.
- **Isochrone** or **catchment.** Two views of the same reachability: the area
  reachable from a point within a time limit (an isochrone), or every block that
  can reach a given place (a catchment).

## Travel times

Times to nearby places are **capped at 30 minutes** for each mode, and recorded in
**whole minutes**. A missing time means the place is not reachable within the cap,
not that it is zero. Isochrones are the exception: they are available for any
budget up to an hour.

## Build a client

You make every request through a client.

```python
from closecity import Client, close_map

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
the usual way. The catalog's `name` column is the readable label ("Grocery
stores"); the underscored `label` is the internal key you match on. A place lookup
carries a `state`, so you can tell Providence, RI from the one in Utah.

```{code-cell} python
types = close.destination_types()
supermarket_dest_type = types.loc[types["label"] == "grocery_stores",
                                  "dest_type_id"].iloc[0]

providence_ri = close.places("Providence").iloc[0]
providence_ri[["name", "state", "geoid"]]
```

## Make a call and map it

Routes with geometry return a GeoDataFrame. `close_map()` draws it on an
interactive basemap in one line — bright, hoverable points here.

```{code-cell} python
supermarkets = close.place_pois(providence_ri["geoid"], type = supermarket_dest_type)
close_map(supermarkets, color = "#e8590c")
```

## Choose an output

Every route returns tabular data by default: a GeoDataFrame where geometry applies,
a plain DataFrame otherwise. The `output` setting changes the shape — `"tabular"`
never downloads boundaries, and `"raw"` returns the underlying reply with its
metering and cursor fields. Set it on the client, or pass `output=` to one call.

The same block summary as a DataFrame (the default):

```{code-cell} python
close.block_summary("440070008001068", mode = "walk")
```

...and as the raw reply, whose `results` you can index yourself:

```{code-cell} python
raw = close.block_summary("440070008001068", mode = "walk", output = "raw")
raw.results[:3]
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
