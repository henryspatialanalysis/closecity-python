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

The quickest way to feel what Close gives you: read one block's travel times, map
the supermarkets around it, then draw how far you can walk from it. The example
city is Providence, Rhode Island.

*Running this tutorial uses about 85 tokens.*

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
types = close.destination_types()
supermarket_dest_type = types.loc[types["label"] == "grocery_stores",
                                  "dest_type_id"].iloc[0]

providence_ri = close.places("Providence").iloc[0]
```

## Read one block's travel times

Pick a block and ask how long it takes to walk to each kind of amenity. Join the
catalog's readable `name` and sort by time, so the nearest things are on top.

```{code-cell} python
walk_times = close.block_summary("440070008001068", mode = "walk")
walk_times = walk_times.merge(types[["dest_type_id", "name"]], on = "dest_type_id")
walk_times.sort_values("travel_time")[["name", "travel_time"]]
```

## Map the supermarkets nearby

`close_map()` draws the result on an interactive basemap in one line — bright,
hoverable points here.

```{code-cell} python
supermarkets = close.pois_search(lat = providence_ri["lat"], lon = providence_ri["lon"],
                                 radius_m = 1200, type = supermarket_dest_type)
close_map(supermarkets, color = "#e8590c")
```

## Draw how far you can walk

An isochrone is the headline map: the area you can reach on foot in 10, 20, and 30
minutes. Shade it by the `contour` minutes and the nearer times stand out.

```{code-cell} python
rings = close.isochrone(block = "440070008001068", mode = "walk",
                        direction = "from", contours = [10, 20, 30])
close_map(rings, fill = "contour")
```

## Walk versus transit

The same block and the same 30-minute budget, on foot and by bus — the clearest
way to see what transit buys you.

```{code-cell} python
walk = close.isochrone(block = "440070008001068", mode = "walk",
                       direction = "from", minutes = 30)
transit = close.isochrone(block = "440070008001068", mode = "transit",
                          direction = "from", minutes = 30)

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
