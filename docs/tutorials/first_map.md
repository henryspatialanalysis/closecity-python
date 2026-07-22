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
the groceries around it, then draw how far you can walk from it. The example city
is Providence, Rhode Island.

*Running this tutorial uses about 90 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
import matplotlib.pyplot as plt
from closecity import Client
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Build a client, then read what you need from the free catalog.

```python
from closecity import Client
import matplotlib.pyplot as plt

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
grocery = types.loc[types["label"] == "grocery_stores", "dest_type_id"].iloc[0]

downtown = close.places("Providence").iloc[0]
```

## Read one block's travel times

Pick a block and ask how long it takes to walk to each kind of amenity. The result
is a small table, one row per category.

```{code-cell} python
summary = close.block_summary("440070008001068", mode = "walk")
summary[["dest_type_id", "travel_time"]].head()
```

## Map the groceries nearby

A radius search returns points, ready to map.

```{code-cell} python
groceries = close.pois_search(lat = downtown["lat"], lon = downtown["lon"],
                              radius_m = 1200, type = grocery)
groceries.plot(color = "#058040", markersize = 20)
```

## Draw how far you can walk

An isochrone is the headline map: the area you can reach on foot in 10, 20, and 30
minutes. The contours come back largest first, so drawing them in order paints the
nearer times on top.

```{code-cell} python
rings = close.isochrone(block = "440070008001068", mode = "walk",
                        direction = "from", contours = [10, 20, 30])
rings.plot(column = "contour", cmap = "YlGnBu_r", legend = True,
           edgecolor = "white", linewidth = 0.5)
```

## Walk versus transit

The same block, the same 30-minute budget, two modes side by side. It is the
clearest way to see what the bus buys you.

```{code-cell} python
walk = close.isochrone(block = "440070008001068", mode = "walk",
                       direction = "from", minutes = 30)
transit = close.isochrone(block = "440070008001068", mode = "transit",
                          direction = "from", minutes = 30)

fig, (left, right) = plt.subplots(1, 2, figsize = (10, 5))
walk.plot(ax = left, color = "#058040")
left.set_title("Walk, 30 min")
transit.plot(ax = right, color = "#202a5b")
right.set_title("Transit, 30 min")
```

## Where to next

- [Looking for a home](home_search): find blocks near several amenities at once,
  then narrow to a commute.
- [The amenity basket](amenity_basket): population-weighted walkability coverage
  across a whole city.
- [Competitor walksheds](competitor_walksheds): who else draws from your
  neighbourhood.
