---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# Your first walkability map

The quickest way to feel what Close gives you: read the walk times from a starting
point, map the supermarkets you can reach on foot, then draw how far a 30-minute walk
takes you. The example city is Providence, Rhode Island.

*Running this tutorial uses about 90 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client, close_map
import plotly.io as pio

# Emit self-contained HTML for each map so myst-nb renders it in the docs build.
pio.renderers.default = "notebook_connected"
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Build a client, then read what you need from the free catalog.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
amenity_types = close.destination_types()
supermarket_type = amenity_types.loc[amenity_types["label"] == "grocery_stores",
                                     "dest_type_id"].iloc[0]

providence_ri = close.places(q = "Providence").iloc[0]
start_lon = providence_ri["lon"]
start_lat = providence_ri["lat"]
```

## Read travel times from a starting point

Pick a starting point — here the centre of Providence — and ask how long it takes to
walk to each kind of amenity. `point_summary()` takes a `lat`/`lon` instead of a block
GEOID. Join the catalog's readable `name` and sort by time, so the nearest things are
on top.

```{code-cell} python
walk_times = close.point_summary(lat = start_lat, lon = start_lon, mode = "walk")
walk_times = walk_times.merge(
    amenity_types[["dest_type_id", "name"]],
    on = "dest_type_id"
)
walk_times.sort_values("travel_time")[["name", "travel_time"]]
```

## Map the supermarkets within a 30-minute walk

A 30-minute walk is a travel-time question, not a distance one, so let the routing
answer it directly: `point_pois` returns every POI reachable from the starting point
within `max_minutes`, each carrying its walk time — no isochrone to overlay.
`close_map()` draws them in one line, shaded by that walk time (blue = closest),
with the starting point marked by an X and the city boundary behind for context.

```{code-cell} python
nearby_supermarkets = close.point_pois(
    lat = start_lat,
    lon = start_lon,
    mode = "walk",
    type = supermarket_type,
    max_minutes = 30
)

city_boundary = close.place_boundary(geoid = providence_ri["geoid"])
close_map(
    nearby_supermarkets,
    fill = "travel_time",
    boundary = city_boundary,
    label = "name",
    mark = (start_lon, start_lat)
)
```

## Draw how far you can walk

An isochrone is the headline map: the area you can reach on foot in 10, 20, and 30
minutes. Shade it by the `contour` minutes; blue marks the nearest, most-reachable
ring.

```{code-cell} python
rings = close.isochrone(
    lon = start_lon,
    lat = start_lat,
    mode = "walk",
    direction = "from",
    contours = [10, 20, 30],
    format = "geojson"
)
close_map(rings, fill = "contour")
```

## Walk versus transit

The same starting point and the same 30-minute budget, on foot and by bus — the
clearest way to see what transit buys you.

```{code-cell} python
walk = close.isochrone(
    lon = start_lon,
    lat = start_lat,
    mode = "walk",
    direction = "from",
    minutes = 30,
    format = "geojson"
)
transit = close.isochrone(
    lon = start_lon,
    lat = start_lat,
    mode = "transit",
    direction = "from",
    minutes = 30,
    format = "geojson"
)

close_map(walk, color = "#058040")
```

```{code-cell} python
close_map(transit, color = "#202a5b")
```
