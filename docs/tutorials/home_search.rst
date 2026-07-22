Looking for a home
==================

**Question.** In a city, which blocks are within a **10-minute walk of a
supermarket**, a **5-minute walk of a restaurant**, and a **20-minute walk of a
frequent-transit stop**? Then: given two workplaces, which of those blocks sit in
the overlap of both commutes — the obvious neighbourhood to choose?

We use **Somerville, MA** — dense and transit-rich, so all three criteria bite.

Find the place and the type ids
-------------------------------

Both lookups are free (no tokens):

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key_here")

   somerville = close.places("Somerville").data["places"][0]
   geoid = somerville["geoid"]          # census place GEOID

   # Confirm the destination-type ids we need.
   types = {t["name"]: t["dest_type_id"]
            for t in close.destination_types().data["destination_types"]}
   GROCERY, RESTAURANT, FREQ_TRANSIT = 30, 27, 61   # from the catalog

Pull the per-block walk times
-----------------------------

One bounded request for the whole (small) city, walking only, just the three
categories:

.. code-block:: python

   rows = list(close.place_blocks(
       geoid, mode="walk", type=[GROCERY, RESTAURANT, FREQ_TRANSIT],
   ))

   # Pivot to one record per block: {geoid: {type_id: minutes}}
   from collections import defaultdict
   by_block = defaultdict(dict)
   for r in rows:
       by_block[r["geoid"]][r["dest_type_id"]] = r["travel_time"]

Filter to the blocks that meet all three thresholds — this is local and free:

.. code-block:: python

   def meets(t):
       return (t.get(GROCERY, 99) <= 10
               and t.get(RESTAURANT, 99) <= 5
               and t.get(FREQ_TRANSIT, 99) <= 20)

   candidates = [g for g, t in by_block.items() if meets(t)]
   print(len(candidates), "candidate blocks")

Map the candidates
------------------

Block replies carry only GEOIDs, so join census-block boundaries. With
``pip install "closecity[geo]"`` the SDK can pull them for you:

.. code-block:: python

   import geopandas as gpd
   blocks = close.place_blocks(geoid, mode="walk", type=[GROCERY]).to_geopandas(
       fetch=True)                       # TIGER 2020 blocks via pygris
   hits = blocks[blocks.geoid.isin(candidates)]
   hits.plot(color="#f36e21", edgecolor="none")

Narrow to the overlap of two commutes
-------------------------------------

Say the two of you work near Kendall Square and downtown Boston. A **15-minute
transit isochrone** from each workplace is one token per contour:

.. code-block:: python

   kendall = close.isochrone(lon=-71.0865, lat=42.3625, mode="transit",
                             direction="from", minutes=20).to_geopandas()
   downtown = close.isochrone(lon=-71.0589, lat=42.3555, mode="transit",
                              direction="from", minutes=20).to_geopandas()

   commute_overlap = gpd.overlay(kendall, downtown, how="intersection")
   # Candidate homes inside both commutes:
   chosen = gpd.sjoin(hits, commute_overlap, predicate="intersects")
   chosen.plot(color="#058040")

The blocks in ``chosen`` are walkable to groceries, food, and frequent transit
**and** a reasonable transit commute for both workers — a short, ranked shortlist.

Token cost
----------

- ``places`` + ``destination_types``: **free**.
- ``place_blocks`` over Somerville (~800 blocks × 3 categories): **~2,400 tokens**
  (once; reuse the result for the map by caching ``rows``).
- Two transit isochrones: **~2 tokens**.

Comfortably inside a 5,000-token month. For a larger city, replace
``place_blocks(geoid, …)`` with a bounded disc —
``blocks_query(center={"lon": …, "lat": …}, radius_m=2500, …)`` — to cap the pull.
