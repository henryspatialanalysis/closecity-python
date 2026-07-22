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

*Running this tutorial uses about 110 tokens.*

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
walk_times = walk_times.merge(amenity_types[["dest_type_id", "name"]], on = "dest_type_id")
walk_times.sort_values("travel_time")[["name", "travel_time"]]
```

## Map the supermarkets within a 30-minute walk

A 30-minute walk is a travel-time question, not a distance one, so let the routing
answer it. Take the 30-minute walk isochrone from the starting point, pull every
supermarket in the city, and keep the ones that fall inside that walkshed.
`close_map()` draws the result on an interactive basemap in one line, with the city
boundary behind it for context.

```{code-cell} python
walkshed_30min = close.isochrone(lon = start_lon, lat = start_lat, mode = "walk",
                                 direction = "from", minutes = 30, format = "geojson")

city_supermarkets = close.place_pois(geoid = providence_ri["geoid"],
                                     type = supermarket_type)
nearby_supermarkets = city_supermarkets[city_supermarkets.within(walkshed_30min.union_all())]

city_boundary = close.place_boundary(geoid = providence_ri["geoid"])
close_map(nearby_supermarkets, color = "#e8590c", boundary = city_boundary, label = "name")
```

## Draw how far you can walk

An isochrone is the headline map: the area you can reach on foot in 10, 20, and 30
minutes. Shade it by the `contour` minutes; blue marks the nearest, most-reachable
ring.

```{code-cell} python
rings = close.isochrone(lon = start_lon, lat = start_lat, mode = "walk",
                        direction = "from", contours = [10, 20, 30], format = "geojson")
close_map(rings, fill = "contour", reverse = True)
```

## Walk versus transit

The same starting point and the same 30-minute budget, on foot and by bus — the
clearest way to see what transit buys you.

```{code-cell} python
walk = close.isochrone(lon = start_lon, lat = start_lat, mode = "walk",
                       direction = "from", minutes = 30, format = "geojson")
transit = close.isochrone(lon = start_lon, lat = start_lat, mode = "transit",
                          direction = "from", minutes = 30, format = "geojson")

close_map(walk, color = "#058040")
```

```{code-cell} python
close_map(transit, color = "#202a5b")
```

## Where to next

- [Looking for a home](home_search): find blocks near several amenities at once,
  then narrow to a commute.
- [The amenity basket](amenity_basket): population-weighted walkability coverage
  across a whole city.
- [Competitor walksheds](competitor_walksheds): who else draws from your
  neighbourhood.
