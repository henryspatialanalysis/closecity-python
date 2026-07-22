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

Say you are moving to a new city and want to live near the amenities that are
important to you. In this tutorial, we find the blocks that are within a 10-minute
walk of a supermarket, a 5-minute walk of a restaurant, and a 20-minute walk of a
frequent-transit stop. Then, we narrow those blocks to the overlap of two commutes.
The example city is Somerville, Massachusetts.

*Running this tutorial uses about 2,900 tokens.*

```{code-cell} python
:tags: [remove-cell]
import os
import pandas as pd
import geopandas as gpd
from closecity import Client, close_map
import plotly.io as pio

# Emit self-contained HTML for each map so myst-nb renders it in the docs build.
pio.renderers.default = "notebook_connected"
close = Client(os.environ.get("CLOSECITY_KEY"))
```

## Set up

Build a client, then read the pieces you need from the free catalog.

```python
from closecity import Client, close_map
import pandas as pd
import geopandas as gpd

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
types = close.destination_types()
ids = dict(zip(types["label"], types["dest_type_id"]))
supermarket_dest_id = ids["grocery_stores"]
restaurant_dest_id = ids["restaurants"]
freq_transit_stop_dest_id = ids["frequent_transit"]

city = close.places("Somerville").iloc[0]
```

## See what is around

Look at the raw ingredients first. Each search returns points; give each category
a colour and map them together.

```{code-cell} python
supermarkets = close.pois_search(lat = city["lat"], lon = city["lon"],
                                 radius_m = 3000, type = supermarket_dest_id)
restaurants = close.pois_search(lat = city["lat"], lon = city["lon"],
                                radius_m = 3000, type = restaurant_dest_id)
stops = close.pois_search(lat = city["lat"], lon = city["lon"],
                          radius_m = 3000, type = freq_transit_stop_dest_id)

supermarkets["kind"] = "Supermarket"
restaurants["kind"] = "Restaurant"
stops["kind"] = "Transit stop"
around = pd.concat([supermarkets[["kind", "geometry"]],
                    restaurants[["kind", "geometry"]],
                    stops[["kind", "geometry"]]])

palette = {"Supermarket": "#058040", "Restaurant": "#c6cbe0",
           "Transit stop": "#f36e21"}
close_map(around, color = [palette[k] for k in around["kind"]], label = "kind")
```

## Find the blocks that qualify

Somerville is a census place, so one call by place GEOID pulls the per-block walk
times for every block in the city — a GeoDataFrame with one row per (block,
category); the boundaries come from `pygris`, downloaded once. (To search an
arbitrary area instead, use `blocks_query` with a centre and radius or a polygon —
we do that with a radius in the other tutorials only to keep their token cost low;
a place GEOID pulls the whole city.)

```{code-cell} python
blocks = close.place_blocks(city["geoid"], mode = "walk",
                            type = [supermarket_dest_id, restaurant_dest_id,
                                    freq_transit_stop_dest_id])
```

Take the blocks that pass each rule, then keep the blocks that pass all three.

```{code-cell} python
near_supermarket = set(blocks.loc[(blocks.dest_type_id == supermarket_dest_id) &
                                  (blocks.travel_time <= 10), "geoid"])
near_restaurant = set(blocks.loc[(blocks.dest_type_id == restaurant_dest_id) &
                                 (blocks.travel_time <= 5), "geoid"])
near_transit = set(blocks.loc[(blocks.dest_type_id == freq_transit_stop_dest_id) &
                              (blocks.travel_time <= 20), "geoid"])

candidates = near_supermarket & near_restaurant & near_transit
```

Show every block in the city, and highlight the ones that qualify.

```{code-cell} python
city_blocks = blocks.drop_duplicates("geoid").copy()
city_blocks["qualifies"] = city_blocks["geoid"].isin(candidates)
close_map(city_blocks, highlight = "qualifies", color = "#f36e21")
```

## Narrow to a shared commute

Suppose two of you work in different places. A transit isochrone from each workplace
shows how far each commute reaches.

```{code-cell} python
work_a = close.isochrone(lon = -71.0865, lat = 42.3625, mode = "transit",
                         direction = "from", minutes = 20)
work_b = close.isochrone(lon = -71.0589, lat = 42.3555, mode = "transit",
                         direction = "from", minutes = 20)

close_map(work_a, color = "#058040")
```

```{code-cell} python
close_map(work_b, color = "#f36e21")
```

Keep the qualifying blocks that also sit inside both commutes. That short list is
where to look.

```{code-cell} python
both_commutes = gpd.overlay(work_a, work_b, how = "intersection")
winners = city_blocks[city_blocks["qualifies"]].copy()
matched = gpd.sjoin(winners, both_commutes, predicate = "intersects")
winners["shortlist"] = winners.index.isin(matched.index)
close_map(winners, highlight = "shortlist", color = "#058040")
```
