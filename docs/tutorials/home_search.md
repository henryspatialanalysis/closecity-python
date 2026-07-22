---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  name: python3
---

# Looking for a home

Say you are moving to a new city and want to live somewhere walkable. Here you find
the blocks that are within a 10-minute walk of a grocery store, a 5-minute walk of a
restaurant, and a 20-minute walk of a frequent-transit stop. Then you narrow those
blocks to the overlap of two commutes. The example city is Somerville, Massachusetts.

```{code-cell} python
:tags: [remove-cell]
import os
import geopandas as gpd
from closecity import Client
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Build a client, then read the pieces you need from the free catalog.

```python
from closecity import Client
import geopandas as gpd

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types().data["destination_types"]
ids = {t["label"]: t["dest_type_id"] for t in types}
grocery = ids["grocery_stores"]
restaurant = ids["restaurants"]
transit = ids["frequent_transit"]

city = close.places("Somerville").data["places"][0]
```

## See what is around

Each search returns points, so plot the three amenities as three layers.

```{code-cell} python
groceries = close.pois_search(lat = city["lat"], lon = city["lon"],
                              radius_m = 3000, type = grocery)
restaurants = close.pois_search(lat = city["lat"], lon = city["lon"],
                                radius_m = 3000, type = restaurant)
stops = close.pois_search(lat = city["lat"], lon = city["lon"],
                          radius_m = 3000, type = transit)

ax = restaurants.plot(color = "#c6cbe0", markersize = 6)
groceries.plot(ax = ax, color = "#058040")
stops.plot(ax = ax, color = "#f36e21", marker = "^")
```

## Find the blocks that qualify

Pull the per-block walk times for the whole city. The result is a GeoDataFrame with
one row per (block, category); the boundaries come from `pygris`, downloaded once.

```{code-cell} python
blocks = close.place_blocks(city["geoid"], mode = "walk",
                            type = [grocery, restaurant, transit])
```

Take the blocks that pass each rule, then keep the blocks that pass all three.

```{code-cell} python
near_grocery = set(blocks.loc[(blocks.dest_type_id == grocery) &
                              (blocks.travel_time <= 10), "geoid"])
near_restaurant = set(blocks.loc[(blocks.dest_type_id == restaurant) &
                                 (blocks.travel_time <= 5), "geoid"])
near_transit = set(blocks.loc[(blocks.dest_type_id == transit) &
                              (blocks.travel_time <= 20), "geoid"])

candidates = near_grocery & near_restaurant & near_transit
winners = blocks[blocks.geoid.isin(candidates)]

ax = blocks.plot(color = "#eef0f7", edgecolor = "white")
winners.plot(ax = ax, color = "#f36e21")
```

## Narrow to a shared commute

Suppose two of you work in different places. A transit isochrone from each workplace
shows how far each commute reaches. Both come back as polygons.

```{code-cell} python
work_a = close.isochrone(lon = -71.0865, lat = 42.3625, mode = "transit",
                         direction = "from", minutes = 20)
work_b = close.isochrone(lon = -71.0589, lat = 42.3555, mode = "transit",
                         direction = "from", minutes = 20)

both_commutes = gpd.overlay(work_a, work_b, how = "intersection")
```

Keep the winning blocks that also sit inside both commutes. That short list is where
to look.

```{code-cell} python
shortlist = gpd.sjoin(winners, both_commutes, predicate = "intersects")

ax = winners.plot(color = "#eef0f7", edgecolor = "white")
shortlist.plot(ax = ax, color = "#058040")
```
