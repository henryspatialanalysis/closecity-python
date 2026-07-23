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

A coffee shop wants to understand the competition inside its own catchment. Its
**walkshed** is every residential block that can walk to it in 10 minutes. This
tutorial asks, block by block, how many other cafes those residents can also reach on
foot, and which one is closest. The example city is Providence, Rhode Island.

*Running this tutorial uses about 450 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
import numpy as np
import plotly.colors as pc
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

`place_pois` returns every cafe within the city's boundary. Pick one as the subject,
then pull its walkshed: every block that can walk to it in 10 minutes. Draw the
walkshed with the cafes on top, our shop in orange.

```{code-cell} python
cafes = close.place_pois(geoid = city["geoid"], type = cafe)
ours = cafes.iloc[0]
print(ours["name"])

our_shed = close.poi_catchment(dest_id = int(ours["dest_id"]), mode = "walk",
                               max_minutes = 10)
close_map(
    cafes,
    color = ["#f36e21" if d == ours["dest_id"] else "#202a5b" for d in cafes["dest_id"]],
    label = "name",
    background = our_shed.dissolve(),
    background_color = "#74b9ff",
    boundary = city_boundary,
)
```

## What each block can reach

Now split the walkshed by block. A single `block_pois` call takes the whole list of
walkshed blocks and returns, for every block, each cafe its residents can walk to
within 10 minutes — the real routed answer, not a straight-line guess, and one
request rather than one per block. Passing a list of GEOIDs tags every row with its
origin `geoid`, so grouping by it reads two things per block: how many cafes are in
reach, and which one is closest by walk time.

```{code-cell} python
reach = close.block_pois(
    list(our_shed["geoid"]),
    mode = "walk", type = cafe, max_minutes = 10, output = "tabular",
)

per_block = reach.groupby("geoid")
our_shed["n_cafes"] = (
    our_shed["geoid"].map(per_block.size()).fillna(0).astype(int)
)
winners = reach.loc[per_block["travel_time"].idxmin()].set_index("geoid")
our_shed["closest_cafe"] = our_shed["geoid"].map(winners["dest_id"])
```

## How many cafes each block can reach

Shade every block in the walkshed by the number of cafes within a 10-minute walk;
blue marks the blocks with the most choice.

```{code-cell} python
close_map(our_shed, fill = "n_cafes", reverse = True, boundary = city_boundary)
```

## Which cafe is closest

Give each cafe that wins at least one block a colour, then paint every block with the
colour of its closest cafe. The cafe points share those colours. The result is the
contested ground — where our shop's catchment gives way to a competitor's.

```{code-cell} python
closest = [int(c) for c in our_shed["closest_cafe"].dropna().unique()]
colors = pc.qualitative.Bold
palette = {cid: colors[i % len(colors)] for i, cid in enumerate(closest)}

block_color = [palette[int(c)] if not np.isnan(c) else "#dddddd"
               for c in our_shed["closest_cafe"]]
winning = cafes[cafes["dest_id"].isin(closest)]

close_map(
    our_shed,
    color = block_color,
    points = winning,
    points_color = [palette[int(d)] for d in winning["dest_id"]],
    boundary = city_boundary,
)
```

The same recipe scales up: raise `max_minutes`, or compare whole cities by pulling
each one's cafes with `place_pois`.
