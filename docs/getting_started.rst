Getting started
===============

A short tour of the client. The tutorials go further.

Words you will see
------------------

A few terms come up throughout:

- **Census block.** The smallest area the Census Bureau publishes. Each one has a
  15-digit id, its **GEOID**.
- **Destination type.** A category of place, such as grocery stores or libraries.
  Every type has a numeric id.
- **Mode.** How someone travels: walk, bike, or transit.
- **Isochrone.** The area reachable from a point within a time limit, as a polygon.
- **Catchment.** The reverse: every block that can reach a given place.

Build a client
--------------

You make every request through a client.

.. code-block:: python

   from closecity import Client

   # The key (ck_live_ or ck_test_) comes from https://account.close.city
   close = Client("ck_live_your_key")   # use your own key here

The catalog and lookup routes are free, so you can also start without a key:

.. code-block:: python

   close = Client()
   close.modes().data["modes"]                    # walk, bike, transit
   close.last_updated().data["last_updated"]

Look things up instead of guessing
----------------------------------

Two free calls save you from memorising codes. Read the numeric id for a category
from the catalog, and turn a city name into a GEOID and a centre point.

.. code-block:: python

   types = close.destination_types().data["destination_types"]
   ids = {t["label"]: t["dest_type_id"] for t in types}
   grocery = ids["grocery_stores"]

   providence = close.places("Providence").data["places"][0]
   providence["geoid"]

Make a call and map it
----------------------

Feature methods return a :class:`geopandas.GeoDataFrame`, so you can map the result
straight away.

.. code-block:: python

   groceries = close.pois_search(lat = providence["lat"], lon = providence["lon"],
                                 radius_m = 1500, type = grocery)
   groceries.plot(color = "#202a5b")     # needs matplotlib

Turn spatial output off
-----------------------

Set ``spatial=False`` to work with the raw data. Then list routes return a
:class:`~closecity.Paginator` you can iterate.

.. code-block:: python

   close = Client("ck_live_your_key", spatial = False)   # use your own key here
   for poi in close.pois_search(lat = providence["lat"], lon = providence["lon"],
                                radius_m = 1500):
       print(poi["name"])

Block methods join census-block boundaries for you, using the ``pygris`` package
(``pip install "closecity[tiger]"``) to download them once.

Conditional requests
--------------------

Metered routes return an ``ETag``. Send it back to revalidate for free.

.. code-block:: python

   close = Client("ck_live_your_key", spatial = False)   # use your own key here
   first = close.block_summary("440070036001010")
   again = close.block_summary("440070036001010", if_none_match = first.etag)
   assert again.not_modified

Errors
------

Problem responses become typed exceptions.

.. code-block:: python

   from closecity import TokensExhaustedError, CloseAPIError

   try:
       close.block_summary("000000000000000")
   except TokensExhaustedError:
       ...
   except CloseAPIError as err:
       print(err.status, err.slug)
