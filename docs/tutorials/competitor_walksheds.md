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

A coffee shop wants to know which competitors draw from the same neighbourhood it does.
Its **walkshed** is every residential block that can walk to it. This tutorial finds
the competitors — the cafes those same blocks can also walk to — and maps them. The
example city is Providence, Rhode Island.

*Running this tutorial uses about 2,000 tokens.*

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

Read the cafe category id from the free catalog and find the city.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
amenity_types = close.destination_types()
ids = dict(zip(amenity_types["label"], amenity_types["dest_type_id"]))
cafe = ids["cafes"]

city = close.places(q = "Providence").iloc[0]
city_boundary = close.place_boundary(geoid = city["geoid"])
```

## Find the shops and our walkshed

`place_pois` returns every cafe within the city's boundary — no radius to guess. Pick
one as the subject, then pull its walkshed: every block that can walk to it in 10
minutes.

```{code-cell} python
cafes = close.place_pois(geoid = city["geoid"], type = cafe)
ours = cafes.iloc[0]
print(ours["name"])
cafes["is_ours"] = cafes["dest_id"] == ours["dest_id"]

our_shed = close.poi_catchment(dest_id = int(ours["dest_id"]), mode = "walk",
                               max_minutes = 10)
walkshed = our_shed.dissolve()
```

Draw the walkshed, with the cafes on top and our shop in orange.

```{code-cell} python
close_map(cafes, color = ["#f36e21" if o else "#202a5b" for o in cafes["is_ours"]],
          label = "name", background = walkshed, background_color = "#74b9ff",
          boundary = city_boundary)
```

## Who else those blocks can reach

A competitor is a cafe that the residents of *our* walkshed can also walk to. So take
the blocks in our walkshed, and for each of the nearest cafes, pull its walkshed: if
the two share blocks, those residents can reach it too. `our_shed["geoid"]` is just a
column of block ids, so the overlap is a plain set intersection. (We check the nearest
cafes to keep the token cost down; the recipe scales to all of them.)

```{code-cell} python
our_geoids = set(our_shed["geoid"])
others = cafes[~cafes["is_ours"]].copy()
others["dist"] = (others["lon"] - ours["lon"]) ** 2 + (others["lat"] - ours["lat"]) ** 2
nearest = others.nsmallest(min(15, len(others)), "dist")

shared = {}
for _, cafe_row in nearest.iterrows():
    their_shed = close.poi_catchment(dest_id = int(cafe_row["dest_id"]), mode = "walk",
                                     max_minutes = 10)
    shared[cafe_row["dest_id"]] = len(our_geoids & set(their_shed["geoid"]))

for dest_id, n in sorted(shared.items(), key = lambda kv: -kv[1]):
    if n == 0:
        continue
    name = nearest.loc[nearest["dest_id"] == dest_id, "name"].iloc[0]
    print(f"{name:28} {n:3} shared blocks ({100 * n / len(our_geoids):.0f}% of ours)")

competitors = {d for d, n in shared.items() if n > 0}
cafes["is_competitor"] = cafes["dest_id"].isin(competitors)
```

## Map the contested ground

Draw every cafe over our walkshed: our shop in orange, the competitors those blocks can
also reach in red, and the rest in navy. The red cafes are the ones fighting for the
same walk-in traffic.

```{code-cell} python
def cafe_color(row):
    if row["is_ours"]:
        return "#f36e21"
    return "#e03131" if row["is_competitor"] else "#202a5b"

close_map(cafes, color = [cafe_color(r) for _, r in cafes.iterrows()], label = "name",
          background = walkshed, background_color = "#74b9ff", boundary = city_boundary)
```

The same recipe scales up: raise the cafe count you check, or compare whole cities by
pulling each one's cafes with `place_pois`.
