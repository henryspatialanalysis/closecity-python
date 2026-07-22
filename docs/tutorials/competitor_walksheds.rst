Competitor walksheds
====================

**Question.** For a given business in a given industry, which **competitors also
serve its walkshed** — the residential blocks that can walk to it — and how much do
their catchments overlap?

We use **Providence, RI** and the coffee-shop trade (destination type ``31``).

Pick the business and its industry
----------------------------------

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key_here")

   CAFE = 31   # from close.destination_types()
   providence = close.places("Providence").data["places"][0]
   center = {"lon": providence["lon"], "lat": providence["lat"]}

   # Cafes near downtown; take the first as "our" business.
   cafes = list(close.pois_search(lat=center["lat"], lon=center["lon"],
                                  radius_m=1200, type=CAFE))
   ours = cafes[0]
   competitors = cafes[1:6]          # the five nearest others
   print("our shop:", ours["name"])

Our walkshed
------------

Every block that can reach our shop within a 10-minute walk:

.. code-block:: python

   def walkshed(dest_id):
       rows = list(close.poi_catchment(dest_id, mode="walk", max_minutes=10))
       return {r["geoid"] for r in rows}

   ours_shed = walkshed(ours["dest_id"])
   print(len(ours_shed), "blocks in our walkshed")

Which competitors contest it
----------------------------

For each competitor, how much of *our* walkshed they also serve — local set math,
free once the catchments are pulled:

.. code-block:: python

   for c in competitors:
       shed = walkshed(c["dest_id"])
       shared = ours_shed & shed
       print(f"{c['name']:30} shares {len(shared):3} blocks "
             f"({len(shared)/len(ours_shed):.0%} of ours)")

Map the contested ground
------------------------

Convert POIs to points and the shared blocks to polygons:

.. code-block:: python

   import geopandas as gpd
   import pandas as pd

   pts = close.pois_search(lat=center["lat"], lon=center["lon"],
                           radius_m=1200, type=CAFE).to_geopandas()

   contested = ours_shed.copy()
   for c in competitors:
       contested |= (ours_shed & walkshed(c["dest_id"]))

   shed_blocks = close.poi_catchment(ours["dest_id"], mode="walk",
                                     max_minutes=10).to_geopandas(fetch=True)
   ax = shed_blocks.plot(color="#eef0f7", edgecolor="#c6cbe0")
   pts.plot(ax=ax, color="#202a5b", markersize=20)          # all cafes
   pts[pts.dest_id == ours["dest_id"]].plot(ax=ax, color="#f36e21", markersize=60)

The map shows our shop's walkshed, every competitor in it, and the blocks each one
contests — a first cut at cannibalisation and white-space for a new location.

Scaling to a county or state
----------------------------

The same recipe runs over a wider area — search a bounding box instead of a radius,
and iterate businesses — but catchment pulls are metered per block, so a county-wide
sweep can run into thousands of tokens. Keep ``max_minutes`` small and page in
batches to stay on budget.

Token cost
----------

- ``places`` + one ``pois_search``: free lookup + **~a few dozen tokens**.
- Six 10-minute walk catchments (ours + five competitors), ~50–150 blocks each:
  **~600 tokens** total.

Well inside a 5,000-token month for a single business and its near neighbours.
