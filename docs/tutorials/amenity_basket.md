---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# The amenity basket

A city planner wants every resident to be able to walk to a basket of six everyday
amenities: a supermarket, a library, a park, a frequent-transit stop, a restaurant,
and a cafe. This tutorial measures how many residents already have that, and shows
where the gaps are. The idea follows
[this analysis](https://nathenry.com/writing/2023-02-07-seattle-walkability.html),
here applied to Richmond, Virginia.

*Running this tutorial uses about 3,600 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
import pandas as pd
import numpy as np
from closecity import Client, close_map
import plotly.io as pio

# Emit self-contained HTML for each map so myst-nb renders it in the docs build.
pio.renderers.default = "notebook_connected"
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Turn the city name into a centre point and a boundary, and build the basket as a
small table: each amenity paired with its destination-type id.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
amenity_types = close.destination_types()
ids = dict(zip(amenity_types["label"], amenity_types["dest_type_id"]))
basket = pd.DataFrame({
    "amenity": ["supermarket", "library", "park", "transit", "restaurant", "cafe"],
    "dest_type_id": [ids[k] for k in ["grocery_stores", "libraries", "parks",
                                      "frequent_transit", "restaurants", "cafes"]],
})

city = close.places(q = "Richmond").iloc[0]
city_boundary = close.place_boundary(geoid = city["geoid"])
```

## Pull the blocks, with population

One call gets the walk time from every block to each of the six categories, plus each
block's population. To keep this tutorial cheap we take the central blocks within a
radius; `place_blocks(geoid = city["geoid"])` pulls **every** block in the city the
same way (at a higher token cost).

```{code-cell} python
blocks = close.blocks_query(
    center = {"lon": city["lon"], "lat": city["lat"]}, radius_m = 2500,
    mode = "walk", type = basket["dest_type_id"].tolist(), include_population = True)
```

Reshape to one row per block: keep just the GEOID and geometry, add the population,
and add a walk-time column for each amenity (`NaN` when it is more than 30 minutes
away). One clean table, no leftover census-block metadata.

```{code-cell} python
one_per_block = blocks.drop_duplicates("geoid")[["geoid", "geometry"]].reset_index(drop = True)
population = blocks.drop_duplicates("geoid").set_index("geoid")["population"]
one_per_block["population"] = one_per_block["geoid"].map(population)
for _, row in basket.iterrows():
    times = blocks[blocks["dest_type_id"] == row["dest_type_id"]].set_index("geoid")["travel_time"]
    one_per_block[f"{row['amenity']}_min"] = one_per_block["geoid"].map(times)
total_pop = one_per_block["population"].sum()

# The six walk-time columns as a boolean "within 15 minutes" table, for the tallies.
min_cols = [f"{a}_min" for a in basket["amenity"]]
within_15 = (one_per_block[min_cols] <= 15).fillna(False)
```

## Coverage, one amenity at a time

For each amenity, a block counts as covered when it is within a 15-minute walk.

```{code-cell} python
for a in basket["amenity"]:
    covered = within_15[f"{a}_min"]
    pop = one_per_block.loc[covered, "population"].sum()
    print(f"{a:11} {100 * pop / total_pop:3.0f}%")
```

Parks and restaurants tend to be everywhere; supermarkets and libraries are usually
the hardest to reach. Map the library coverage — every block shown, the covered ones
highlighted, the library locations as points, the city boundary behind.

```{code-cell} python
one_per_block["has_library"] = within_15["library_min"]
library_type = int(basket.loc[basket["amenity"] == "library", "dest_type_id"].iloc[0])
libraries = close.pois_search(lat = city["lat"], lon = city["lon"], radius_m = 2500,
                              type = library_type)
close_map(one_per_block, highlight = "has_library", color = "#058040",
          points = libraries, boundary = city_boundary)
```

## The 15-minute-city score

Count, for each block, how many of the six amenities are within a 15-minute walk.
That score, from 0 to 6, is the map planners reach for; blue marks the best-served
blocks. It reuses the data you already pulled, so it costs nothing more.

```{code-cell} python
one_per_block["score"] = within_15.sum(axis = 1)
close_map(one_per_block, fill = "score", reverse = True, boundary = city_boundary)
```

## Who can reach all six

A block is fully covered only when all six amenities are within 15 minutes.

```{code-cell} python
one_per_block["full_basket"] = one_per_block["score"] == 6
basket_pop = one_per_block.loc[one_per_block["full_basket"], "population"].sum()
print(f"All six amenities: {100 * basket_pop / total_pop:.0f}% of residents")

close_map(one_per_block, highlight = "full_basket", color = "#f36e21",
          boundary = city_boundary)
```

## Which amenity to add first

Count how many not-yet-covered residents are missing each amenity. The amenity the
most people lack is the one to add first.

```{code-cell} python
for a in basket["amenity"]:
    lacking = ~one_per_block["full_basket"] & ~within_15[f"{a}_min"]
    print(f"{a:11} {one_per_block.loc[lacking, 'population'].sum():6.0f} residents would gain access")
```

## Who is one or two amenities away

The residents worth targeting first are the ones *almost* there — a block with five
of the six is a much easier win than one with none. Count how many amenities each
block is missing, and for the blocks short by just one or two, break down which
amenities are the gap.

```{code-cell} python
have = within_15.to_numpy()
amenities = list(basket["amenity"])
n_missing = 6 - one_per_block["score"].to_numpy()
gap = np.array([" + ".join(a for a, h in zip(amenities, row) if not h) for row in have])
pops = one_per_block["population"].to_numpy()

almost = np.isin(n_missing, [1, 2])
almost_pop = pops[almost].sum()
print(f"{100 * almost_pop / total_pop:.0f}% of residents are one or two amenities "
      f"short of the full basket.\n")

by_gap = (pd.Series(pops[almost], index = gap[almost])
          .groupby(level = 0).sum().sort_values(ascending = False))
for g, p in by_gap.items():
    print(f"  missing {g:22} {100 * p / almost_pop:3.0f}%")
```

## Site a new supermarket

The counts above say *which* amenity to add; the next question is *where*. Pick the
candidate site automatically: a populated block with no supermarket within a 15-minute
walk, nearest the middle of the study area. A `direction="to"` isochrone then gives
the blocks that could reach the site on foot in 15 minutes, and the ones not already
served are the population this site would newly reach.

```{code-cell} python
uncovered = one_per_block[~within_15["supermarket_min"] & (one_per_block["population"] > 0)]
points = uncovered.geometry.representative_point()
middle = one_per_block.geometry.union_all().centroid
site = points.iloc[(((points.x - middle.x) ** 2 + (points.y - middle.y) ** 2)).to_numpy().argmin()]

reachable = close.isochrone(lon = site.x, lat = site.y, mode = "walk",
                            direction = "to", minutes = 15, format = "blocks")
near_supermarket = set(one_per_block.loc[within_15["supermarket_min"], "geoid"])
newly_served = (set(reachable["geoid"]) & set(one_per_block["geoid"])) - near_supermarket
gain_pop = one_per_block.loc[one_per_block["geoid"].isin(newly_served), "population"].sum()
print(f"A supermarket here would newly serve {gain_pop:.0f} residents")
```

Map the whole city and highlight the blocks that would newly gain access, with the
candidate site marked by an X.

```{code-cell} python
one_per_block["newly_served"] = one_per_block["geoid"].isin(newly_served)
close_map(one_per_block, highlight = "newly_served", color = "#e8590c",
          mark = (site.x, site.y), boundary = city_boundary)
```
