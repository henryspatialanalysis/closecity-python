---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# Competitor walksheds

A coffee shop wants to know which competitors draw from the same neighbourhood it
does. Its **walkshed** is every residential block that can walk to it. This tutorial
finds nearby competitors and measures how much of that walkshed they share. The
example city is Providence, Rhode Island.

*Running this tutorial uses about 900 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Read the cafe category id from the free catalog and find the city centre.

```python
from closecity import Client

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
ids = dict(zip(types["label"], types["dest_type_id"]))
cafe = ids["cafes"]

city = close.places("Providence").iloc[0]
```

## Find the shops

Search for cafes near downtown. The result is a GeoDataFrame of points, so plot them
and pick one shop as the subject.

```{code-cell} python
cafes = close.pois_search(lat = city["lat"], lon = city["lon"],
                          radius_m = 1200, type = cafe)
cafes.plot(color = "#202a5b")

ours = cafes.iloc[0]
ours["name"]
```

## Our walkshed

Ask for every block that can reach our shop within a 10-minute walk. This comes back
as polygons, with the block boundaries downloaded by `pygris`.

```{code-cell} python
our_shed = close.poi_catchment(int(ours["dest_id"]), mode = "walk",
                               max_minutes = 10)
our_geoids = set(our_shed.geoid)

ax = our_shed.plot(color = "#eef0f7", edgecolor = "#c6cbe0")
cafes.iloc[[0]].plot(ax = ax, color = "#f36e21", markersize = 60)
```

## Who else serves it

For each of the nearest competitors, pull their walkshed and count the blocks they
share with ours. Both walksheds are just sets of block ids, so the overlap is a plain
set intersection.

```{code-cell} python
for i in range(1, 6):
    competitor = cafes.iloc[i]
    their_shed = close.poi_catchment(int(competitor["dest_id"]), mode = "walk",
                                     max_minutes = 10)
    shared = our_geoids & set(their_shed.geoid)
    print(f"{competitor['name']:28} {len(shared):3} shared blocks "
          f"({len(shared) / len(our_shed):.0%} of ours)")
```

## Map the contested ground

Draw our walkshed, then every cafe on top, with our shop highlighted.

```{code-cell} python
ax = our_shed.plot(color = "#eef0f7", edgecolor = "#c6cbe0")
cafes.plot(ax = ax, color = "#202a5b")
cafes.iloc[[0]].plot(ax = ax, color = "#f36e21", markersize = 60)
```

The same recipe works over a wider area: search a bounding box instead of a radius,
and loop over more shops.
