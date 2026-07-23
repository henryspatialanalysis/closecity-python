---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# Get started

`closecity` reads the Close API: travel times from every US census block to nearby
places, on foot, by bike, and by public transit. This page is a short tour; the
three tutorials go further. The full list of query methods is on the
[API reference](api.rst), and the wider API is documented at
[docs.close.city](https://docs.close.city).

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client, close_map
import plotly.io as pio

# Emit self-contained HTML for each map so myst-nb renders it in the docs build.
pio.renderers.default = "notebook_connected"
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Key terms

A few terms come up throughout:

- **Census block.** The smallest area the Census Bureau publishes. Each one has a
  15-digit id, its **GEOID**. Block GEOIDs come from the census. Look them up with
  `pygris` or the Census Bureau geocoder/API, or read them straight off Close's
  block routes (`blocks_query`, `place_blocks`).
- **Destination type.** A category of place, such as grocery stores or libraries.
  Every type has a numeric id.
- **Mode.** How someone travels: walk, bike, or transit.
- **Isochrone** or **catchment**: the area you can reach starting from a point
  within a time limit, by a selected travel mode.

## Travel times

Times to nearby places are **capped at 30 minutes** for each mode, and recorded in
**whole minutes**. A missing time means the place is not reachable within the cap,
not that it is zero. Isochrones are the exception: they are available for any budget
up to an hour.

## Build a client

You make every request through a client.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

The catalog and lookup routes are free, so `Client()` with no key also works for
those.

```{code-cell} python
close.modes()
```

## Look things up instead of guessing

Two free calls save you from memorising codes. Both come back as data frames, so you
filter and index them the usual way: read the numeric id for a category from the
catalog, and turn a city name into a GEOID and a centre point.

```{code-cell} python
amenity_types = close.destination_types()
supermarket_type = amenity_types.loc[amenity_types["label"] == "grocery_stores",
                                     "dest_type_id"].iloc[0]

providence_ri = close.places(q = "Providence").iloc[0]
providence_ri[["name", "state", "geoid"]]
```

The catalog's `name` column is the readable label ("Grocery stores"); the underscored
`label` is the internal key you match on. A place lookup carries a `state`, so you can
tell Providence, RI from the one in Utah. When you have a point rather than a block,
`point_summary(lat = , lon = )` reads the same travel times for a `lat`/`lon` starting
point instead of a GEOID.

## Make a call and map it

Routes with geometry return a GeoDataFrame. `close_map()` draws it on an interactive
basemap in one line: bright, hoverable points here, with the city boundary behind
them and the view zoomed to fit.

```{code-cell} python
supermarkets = close.place_pois(geoid = providence_ri["geoid"], type = supermarket_type)
city_boundary = close.place_boundary(geoid = providence_ri["geoid"])
close_map(supermarkets, color = "#e8590c", boundary = city_boundary, label = "name")
```

## Choose an output

Set `output` on the client, or per call:

- `output = "spatial"` (the default) returns a GeoDataFrame for inherently spatial
  data and a DataFrame otherwise. Block routes join census-block boundaries with
  `pygris` (the `tiger` extra), downloaded once and cached.
- `output = "tabular"` returns a plain DataFrame for every route and never downloads
  boundaries. Reach for it when you only want the numbers.
- `output = "raw"` returns the underlying `Reply` / `Paginator`, with the parsed body
  on `.data` and the token counts alongside.

A block summary, with the readable category names merged on and sorted by time:

```{code-cell} python
walk_times = close.block_summary(geoid = "440070008001068", mode = "walk")
walk_times = walk_times.merge(
    amenity_types[["dest_type_id", "name"]],
    on = "dest_type_id"
)
walk_times.sort_values("travel_time")[["name", "travel_time"]]
```

...and the same call as the raw reply, whose parsed `results` you can inspect yourself:

```{code-cell} python
raw = close.block_summary(geoid = "440070008001068", mode = "walk", output = "raw")
raw.data["results"][:3]
```

## The client methods

Every data-getting method lives on the client; see the [API reference](api.rst) for
full signatures.

Catalog and lookups (free, no key):

- {py:meth}`~closecity.Client.modes`: the travel modes (walk, bike, transit).
- {py:meth}`~closecity.Client.destination_types`: the catalog of amenity categories and their numeric ids.
- {py:meth}`~closecity.Client.places`: a city name to its GEOID and centre point.
- {py:meth}`~closecity.Client.place_boundary`: the boundary polygon of a census place.
- {py:meth}`~closecity.Client.vintage`: the data vintage.
- {py:meth}`~closecity.Client.last_updated`: when the data was last refreshed.
- {py:meth}`~closecity.Client.isochrone_meta`: isochrone modes, directions, and assumptions.
- {py:meth}`~closecity.Client.health`: a service health check.

Travel times from a block or a point:

- {py:meth}`~closecity.Client.block_summary`: walk/bike/transit time from a block to each amenity type.
- {py:meth}`~closecity.Client.point_summary`: the same, from a `lat`/`lon` point.
- {py:meth}`~closecity.Client.block_pois`: the individual POIs reachable from a block, each with its travel time.
- {py:meth}`~closecity.Client.point_pois`: the same, from a `lat`/`lon` point.

Points of interest:

- {py:meth}`~closecity.Client.pois_search`: search POIs by radius or bounding box.
- {py:meth}`~closecity.Client.poi`: the details of one POI.
- {py:meth}`~closecity.Client.poi_catchment`: the blocks that can walk to a POI (its catchment).

Whole areas:

- {py:meth}`~closecity.Client.blocks_query`: per-block travel times for a polygon, or a centre and radius.
- {py:meth}`~closecity.Client.place_blocks`: per-block travel times for every block in a place.
- {py:meth}`~closecity.Client.place_pois`: every POI within a place's boundary.
- {py:meth}`~closecity.Client.isochrone`: travel-time contours from a block or a point.

## Handling errors

Problem responses become typed exceptions. Catch a specific one, or the
`CloseAPIError` base.

```python
from closecity import TokensExhaustedError, CloseAPIError

try:
    close.block_summary(geoid = "000000000000000")
except TokensExhaustedError:
    ...
except CloseAPIError as err:
    print(err.status, err.slug)
```
