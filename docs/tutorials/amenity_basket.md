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

*Running this tutorial uses about 3,500 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client, close_map
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Read the six category ids from the free catalog, and turn the city name into a centre
point.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
ids = dict(zip(types["label"], types["dest_type_id"]))
basket = {
    "supermarket": ids["grocery_stores"],
    "library": ids["libraries"],
    "park": ids["parks"],
    "transit": ids["frequent_transit"],
    "restaurant": ids["restaurants"],
    "cafe": ids["cafes"],
}

city = close.places("Richmond").iloc[0]
```

## Pull the blocks, with population

One call gets the walk time from every block to each of the six categories, plus
each block's population. To keep this tutorial cheap we take the central blocks
within a radius; `place_blocks(city["geoid"])` pulls **every** block in the city
the same way (at a higher token cost).

```{code-cell} python
blocks = close.blocks_query(
    center = {"lon": city["lon"], "lat": city["lat"]}, radius_m = 2500,
    mode = "walk", type = list(basket.values()), include_population = True)

one_per_block = blocks.drop_duplicates("geoid").copy()
total_pop = one_per_block["population"].sum()
```

## Coverage, one amenity at a time

For each amenity, a block counts as covered when it is within a 15-minute walk.

```{code-cell} python
for name, type_id in basket.items():
    covered = set(blocks.loc[(blocks.dest_type_id == type_id) &
                             (blocks.travel_time <= 15), "geoid"])
    pop = one_per_block.loc[one_per_block.geoid.isin(covered), "population"].sum()
    print(f"{name:11} {100 * pop / total_pop:3.0f}%")
```

Map one amenity — every block shown, the covered ones highlighted.

```{code-cell} python
near_transit = set(blocks.loc[(blocks.dest_type_id == basket["transit"]) &
                              (blocks.travel_time <= 15), "geoid"])
one_per_block["has_transit"] = one_per_block.geoid.isin(near_transit)
close_map(one_per_block, highlight = "has_transit", color = "#058040")
```

## The 15-minute-city score

Count, for each block, how many of the six amenities are within a 15-minute walk.
That score, from 0 to 6, is the map planners reach for. It reuses the data you
already pulled, so it costs nothing more.

```{code-cell} python
covered = blocks[blocks.travel_time <= 15]
score = covered.groupby("geoid")["dest_type_id"].nunique()
one_per_block["score"] = one_per_block.geoid.map(score).fillna(0).astype(int)
close_map(one_per_block, fill = "score")
```

## Who can reach all six

A block is fully covered only if all six amenities are within 15 minutes.

```{code-cell} python
covered_all = set(one_per_block.geoid)
for type_id in basket.values():
    covered = set(blocks.loc[(blocks.dest_type_id == type_id) &
                             (blocks.travel_time <= 15), "geoid"])
    covered_all &= covered

basket_pop = one_per_block.loc[one_per_block.geoid.isin(covered_all),
                               "population"].sum()
print(f"All six amenities: {100 * basket_pop / total_pop:.0f}% of residents")

one_per_block["full_basket"] = one_per_block.geoid.isin(covered_all)
close_map(one_per_block, highlight = "full_basket", color = "#f36e21")
```

## Which amenity to add first

Count how many not-yet-covered residents are missing each amenity. The amenity the
most people lack is the one to add first.

```{code-cell} python
uncovered = set(one_per_block.geoid) - covered_all
for name, type_id in basket.items():
    covered = set(blocks.loc[(blocks.dest_type_id == type_id) &
                             (blocks.travel_time <= 15), "geoid"])
    lacking = uncovered - covered
    pop = one_per_block.loc[one_per_block.geoid.isin(lacking), "population"].sum()
    print(f"{name:11} {pop:6.0f} residents would gain access")
```

## Site a new supermarket

The counts above say *which* amenity to add; the next question is *where*. Take a
candidate site near the city centre and ask how many residents would newly gain a
supermarket within a 15-minute walk if one opened there. A `direction="to"`
isochrone gives exactly the blocks that could reach the site on foot in 15 minutes.

```{code-cell} python
reachable = close.isochrone(lon = city["lon"], lat = city["lat"], mode = "walk",
                            direction = "to", minutes = 15, format = "blocks")

near_supermarket = set(blocks.loc[(blocks.dest_type_id == basket["supermarket"]) &
                                  (blocks.travel_time <= 15), "geoid"])
newly_served = set(reachable.geoid) - near_supermarket
gain_pop = one_per_block.loc[one_per_block.geoid.isin(newly_served),
                             "population"].sum()
print(f"A supermarket here would newly serve {gain_pop:.0f} residents")
```

Map the whole city and highlight the blocks that would newly gain access.

```{code-cell} python
one_per_block["newly_served"] = one_per_block.geoid.isin(newly_served)
close_map(one_per_block, highlight = "newly_served", color = "#e8590c")
```
