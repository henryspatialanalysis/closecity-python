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
amenities: a grocery store, a library, a park, a frequent-transit stop, a restaurant,
and a cafe. This tutorial measures how many residents already have that, and shows
where the gaps are. The idea follows
[this analysis](https://nathenry.com/writing/2023-02-07-seattle-walkability.html),
here applied to Richmond, Virginia.

*Running this tutorial uses about 3,500 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
from closecity import Client
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Read the six category ids from the free catalog, and turn the city name into a centre
point.

```python
from closecity import Client

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
ids = dict(zip(types["label"], types["dest_type_id"]))
basket = {
    "grocery": ids["grocery_stores"],
    "library": ids["libraries"],
    "park": ids["parks"],
    "transit": ids["frequent_transit"],
    "restaurant": ids["restaurants"],
    "cafe": ids["cafes"],
}

city = close.places("Richmond").iloc[0]
```

## Pull the blocks, with population

One call gets the walk time from every block near downtown to each of the six
categories, along with each block's population.

```{code-cell} python
blocks = close.blocks_query(
    center = {"lon": city["lon"], "lat": city["lat"]}, radius_m = 2500,
    mode = "walk", type = list(basket.values()), include_population = True)

one_per_block = blocks.drop_duplicates("geoid")
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

Map one amenity to see the pattern.

```{code-cell} python
near_transit = set(blocks.loc[(blocks.dest_type_id == basket["transit"]) &
                              (blocks.travel_time <= 15), "geoid"])
one_per_block = one_per_block.assign(
    has_transit = one_per_block.geoid.isin(near_transit))
one_per_block.plot(column = "has_transit", cmap = "Greens")
```

## The 15-minute-city score

Count, for each block, how many of the six amenities are within a 15-minute walk.
That score, from 0 to 6, is the map planners reach for. It reuses the data you
already pulled, so it costs nothing more.

```{code-cell} python
covered = blocks[blocks.travel_time <= 15]
score = covered.groupby("geoid")["dest_type_id"].nunique()
one_per_block = one_per_block.assign(
    score = one_per_block.geoid.map(score).fillna(0).astype(int))
one_per_block.plot(column = "score", cmap = "viridis", legend = True)
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

one_per_block = one_per_block.assign(
    full_basket = one_per_block.geoid.isin(covered_all))
one_per_block.plot(column = "full_basket", cmap = "Oranges")
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

Map the uncovered blocks to see where new amenities would do the most good.

```{code-cell} python
one_per_block = one_per_block.assign(
    uncovered = one_per_block.geoid.isin(uncovered))
one_per_block.plot(column = "uncovered", cmap = "Blues")
```
