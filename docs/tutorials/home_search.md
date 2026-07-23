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

*Running this tutorial uses about 2,600 tokens.*

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

Build a client, then read the pieces you need from the free catalog instead of
memorising codes.

```python
from closecity import Client, close_map

close = Client("ck_live_your_key")   # use your own key here
```

```{code-cell} python
# The catalog lists every category with its numeric id. Pull the ids you need.
amenity_types = close.destination_types()
ids = dict(zip(amenity_types["label"], amenity_types["dest_type_id"]))

supermarket_dest_id = ids["grocery_stores"]
restaurant_dest_id = ids["restaurants"]
freq_transit_stop_dest_id = ids["frequent_transit"]

# Turn the city name into a GEOID and pull its boundary for context.
city = close.places(q = "Somerville").iloc[0]
city_boundary = close.place_boundary(geoid = city["geoid"])
```

## See what is around

Look at the raw ingredients first: every supermarket, restaurant, and frequent-transit
stop **within Somerville**, from `place_pois` — the city boundary, not a guessed
radius, is the edge. Give each category a colour and map them together.

```{code-cell} python
supermarkets = close.place_pois(geoid = city["geoid"], type = supermarket_dest_id)
restaurants = close.place_pois(geoid = city["geoid"], type = restaurant_dest_id)
stops = close.place_pois(geoid = city["geoid"], type = freq_transit_stop_dest_id)

supermarkets["kind"] = "Supermarket"
restaurants["kind"] = "Restaurant"
stops["kind"] = "Transit stop"
around = pd.concat([supermarkets, restaurants, stops])

palette = {"Supermarket": "#058040", "Restaurant": "#c6cbe0", "Transit stop": "#f36e21"}
close_map(
    around,
    color = [palette[k] for k in around["kind"]],
    label = "kind",
    boundary = city_boundary
)
```

## Find the blocks that qualify

Somerville is a census place, so one call by place GEOID pulls the per-block walk
times for every block in the city — `place_blocks` reads every page and returns one
row per (block, category); block boundaries come from `pygris`, downloaded once and
cached. (To search an arbitrary area instead, use `blocks_query` with a centre and
radius or a polygon — we do that with a radius in the other tutorials only to keep
their token cost low; a place GEOID pulls the whole city.)

```{code-cell} python
blocks = close.place_blocks(
    geoid = city["geoid"],
    mode = "walk",
    type = [supermarket_dest_id, restaurant_dest_id, freq_transit_stop_dest_id]
)
```

Reshape to one row per block, with a walk-time column for each amenity, so a block
carries all three times at once (and the hover on the map shows them). Then flag the
blocks that pass every rule.

```{code-cell} python
city_blocks = blocks.drop_duplicates("geoid")[["geoid", "geometry"]].reset_index(
    drop = True
)
def time_to(type_id):
    sub = blocks[blocks["dest_type_id"] == type_id].set_index("geoid")["travel_time"]
    return city_blocks["geoid"].map(sub)
city_blocks["supermarket_min"] = time_to(supermarket_dest_id)
city_blocks["restaurant_min"] = time_to(restaurant_dest_id)
city_blocks["transit_min"] = time_to(freq_transit_stop_dest_id)

city_blocks["qualifies"] = ((city_blocks["supermarket_min"] <= 10) &
                            (city_blocks["restaurant_min"] <= 5) &
                            (city_blocks["transit_min"] <= 20))
```

Show every block in the city, highlight the ones that qualify, and hover any block to
read its walk time to each amenity.

```{code-cell} python
close_map(
    city_blocks,
    highlight = "qualifies",
    color = "#f36e21",
    boundary = city_boundary
)
```

## Narrow to a shared commute

Suppose two of you work in different places. A transit isochrone from each workplace
shows how far each commute reaches; drawn together, half-transparent, you can see both
at once.

```{code-cell} python
work_a = close.isochrone(
    lon = -71.0865,
    lat = 42.3625,
    mode = "transit",
    direction = "from",
    minutes = 20,
    format = "geojson"
)
work_b = close.isochrone(
    lon = -71.0589,
    lat = 42.3555,
    mode = "transit",
    direction = "from",
    minutes = 20,
    format = "geojson"
)

close_map(
    work_a,
    color = "#058040",
    opacity = 0.5,
    background = work_b,
    background_color = "#f36e21",
    background_opacity = 0.5
)
```

Keep the qualifying blocks that also sit inside both commutes. The final map shows
those winning blocks, with the shortlist — inside both commutes — highlighted, over
the two commute walksheds.

```{code-cell} python
both_commutes = work_a.union_all().intersection(work_b.union_all())
winners = city_blocks[city_blocks["qualifies"]].copy()
winners["shortlist"] = winners.intersects(both_commutes)

close_map(
    winners,
    highlight = "shortlist",
    color = "#1f78b4",
    boundary = city_boundary,
    background = [work_a, work_b],
    background_color = ["#058040", "#f36e21"],
    background_fill = False
)
```
