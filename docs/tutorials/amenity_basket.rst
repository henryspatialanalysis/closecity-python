The amenity basket
==================

**Question.** If we want every resident to be able to **walk to a basket of six
everyday amenities**, what share of the population is already covered — and which
**five new amenities**, sited where, would raise that share the most?

This is the population-weighted "15-minute city" method from
`this analysis <https://nathenry.com/writing/2023-02-07-seattle-walkability.html>`_,
applied here to **Richmond, VA**. The basket:

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key_here")

   BASKET = {30: "grocery", 43: "library", 63: "park",
             61: "frequent transit", 27: "restaurant", 31: "cafe"}
   THRESHOLD = 15   # minutes, walking

Pull per-block walk times and population
----------------------------------------

Resolve the city (free), then pull a bounded disc around downtown with population:

.. code-block:: python

   richmond = close.places("Richmond").data["places"][0]
   center = {"lon": richmond["lon"], "lat": richmond["lat"]}

   rows = list(close.blocks_query(
       center=center, radius_m=2500, mode="walk",
       type=list(BASKET), include_population=True,
   ))

   from collections import defaultdict
   times = defaultdict(dict)
   pop = {}
   for r in rows:
       times[r["geoid"]][r["dest_type_id"]] = r["travel_time"]
       pop[r["geoid"]] = r.get("population") or 0

Current coverage
----------------

All of this is local and free:

.. code-block:: python

   def covered(t, type_id):
       return t.get(type_id, 99) <= THRESHOLD

   total = sum(pop.values())
   for type_id, name in BASKET.items():
       share = sum(pop[g] for g, t in times.items() if covered(t, type_id)) / total
       print(f"{name:18} {share:5.0%}")

   fully = [g for g, t in times.items()
            if all(covered(t, ti) for ti in BASKET)]
   basket_share = sum(pop[g] for g in fully) / total
   print(f"\nAll six amenities: {basket_share:.0%} of residents")

In the study area only a small share of residents can reach *all six* on foot —
parks and restaurants are widespread, while **grocery** and **frequent transit** are
the binding constraints.

Which amenities to add, and where
---------------------------------

A new facility of type *X* placed at a block covers every block within a 15-minute
walk of it — exactly a ``direction="from"`` walk isochrone (10 tokens each). We greedily
pick the five sites that turn the most *currently-uncovered* residents into
fully-covered ones.

.. code-block:: python

   import geopandas as gpd

   # Block geometries (for candidate-site centroids); reuse one pull's rows.
   blocks = close.blocks_query(center=center, radius_m=2500, mode="walk",
                               type=[30]).to_geopandas(fetch=True)
   blocks = blocks.set_index("geoid")
   blocks["centroid"] = blocks.geometry.representative_point()

   def missing(g):
       return [ti for ti in BASKET if not covered(times.get(g, {}), ti)]

   # Candidate sites: uncovered, populous blocks, each missing exactly one amenity
   # (adding that one amenity flips them to fully-covered).
   candidates = sorted(
       (g for g in times if len(missing(g)) == 1 and g in blocks.index),
       key=lambda g: pop[g], reverse=True,
   )[:25]

   def walkshed(g):
       c = blocks.loc[g, "centroid"]
       iso = close.isochrone(lon=c.x, lat=c.y, mode="walk",
                             direction="from", minutes=THRESHOLD, format="blocks")
       return {b["geoid"] for b in iso.data["blocks"]}

   sheds = {g: (missing(g)[0], walkshed(g)) for g in candidates}

   # Greedy: repeatedly take the site adding the most newly-covered population.
   chosen, still_missing = [], {g: missing(g)[0] for g in times if missing(g)}
   for _ in range(5):
       def gain(site):
           amenity, shed = sheds[site]
           return sum(pop[g] for g in shed
                      if still_missing.get(g) == amenity)
       best = max(sheds, key=gain)
       amenity, shed = sheds[best]
       newly = [g for g in shed if still_missing.get(g) == amenity]
       chosen.append((best, BASKET[amenity], sum(pop[g] for g in newly)))
       for g in newly:
           still_missing.pop(g, None)
       del sheds[best]

   for site, amenity, gained in chosen:
       print(f"add a {amenity} near block {site}: +{gained:,} residents covered")

The result is a ranked, mapped list of five concrete interventions — *"a grocery
here, a transit stop there"* — each annotated with the population it brings into
walkable range of the whole basket.

Token cost
----------

- ``places``: free. ``blocks_query`` disc (~700 blocks × 6 categories):
  **~4,000 tokens** (cache ``rows`` and reuse it for the geometry pull).
- Up to 25 candidate isochrones (1 contour each, 10 tokens): **~250 tokens**.

Around 4,300 tokens — inside a 5,000-token month. Shrink ``radius_m`` (or the
candidate count) to trade coverage for budget; widen it, across several months, for a
whole city.
