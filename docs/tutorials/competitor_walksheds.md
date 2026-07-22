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
finds the competitors and measures how much of that walkshed they share. The example
city is Providence, Rhode Island.

*Running this tutorial uses about 700 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client, close_map
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Read the cafe category id from the free catalog and find the city.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
ids = dict(zip(types["label"], types["dest_type_id"]))
cafe = ids["cafes"]

city = close.places("Providence").iloc[0]
```

## Find the shops

`place_pois` returns every cafe within the city's boundary — no radius to guess.
Pick one as the subject and draw it in orange; the rest are the field.

```{code-cell} python
cafes = close.place_pois(city["geoid"], type = cafe)
ours = cafes.iloc[0]
ours["name"]

cafes["is_ours"] = cafes["dest_id"] == ours["dest_id"]
close_map(cafes, color = ["#f36e21" if o else "#202a5b" for o in cafes["is_ours"]],
          label = "name")
```

## Our walkshed

Ask for every block that can reach our shop within a 10-minute walk. This comes back
as polygons, with the block boundaries downloaded by `pygris`.

```{code-cell} python
our_shed = close.poi_catchment(int(ours["dest_id"]), mode = "walk",
                               max_minutes = 10)
our_geoids = set(our_shed.geoid)
close_map(our_shed, color = "#74b9ff")
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

Draw every cafe, with our shop in orange and the field in navy. The clusters of
competitors sitting inside our walkshed are the ones competing for the same walk-in
traffic.

```{code-cell} python
close_map(cafes, color = ["#f36e21" if o else "#202a5b" for o in cafes["is_ours"]],
          label = "name")
```

The same recipe scales up: loop `poi_catchment` over more competitors, or compare
whole cities by pulling each one's cafes with `place_pois`.
