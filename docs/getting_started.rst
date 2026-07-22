Getting started
===============

This is a five-minute tour of the client. For end-to-end analyses see the
:doc:`tutorials <tutorials/index>`.

A client
--------

.. code-block:: python

   from closecity import Client

   close = Client("ck_live_your_key_here")   # or Client() for the free routes

``Client`` is usable as a context manager (``with Client(...) as close:``) so the
underlying HTTP connection is closed for you.

Free catalog (no key)
---------------------

.. code-block:: python

   close = Client()
   print(close.modes().data["modes"])                 # walk / bike / transit
   print(close.destination_types().data["destination_types"][:3])
   print(close.last_updated().data["last_updated"])

Use :meth:`~closecity.Client.destination_types` to find the numeric ``type`` ids the
data routes filter on (e.g. grocery ``30``, restaurants ``27``, cafes ``31``,
libraries ``43``, parks ``63``, frequent-transit stops ``61``).

One metered call
----------------

.. code-block:: python

   summary = close.block_summary("250173523004004", mode="walk")
   for row in summary.results:
       print(row["dest_type_id"], row["mode"], row["travel_time"])

Every metered reply carries its accounting:

.. code-block:: python

   print(summary.tokens_charged, "charged;", summary.tokens_remaining, "left")

Metering is **1 token per returned row** (minimum 1 per request); isochrones are the
exception at **10 tokens per contour**. A ``304`` revalidation is free.

Pagination
----------

List endpoints return a :class:`~closecity.Paginator` that transparently follows the
opaque cursor:

.. code-block:: python

   pois = close.pois_search(lat=41.823, lon=-71.412, radius_m=1500, type=31)
   for poi in pois:                 # every record across all pages
       print(poi["name"], poi["lat"], poi["lon"])

   # or page-by-page, to read per-page token metadata:
   for page in close.pois_search(lat=41.823, lon=-71.412, radius_m=1500).pages():
       print(len(page.results), page.tokens_remaining)

Conditional requests (free revalidation)
-----------------------------------------

.. code-block:: python

   first = close.block_summary("250173523004004")
   again = close.block_summary("250173523004004", if_none_match=first.etag)
   assert again.not_modified          # 304 — no tokens charged

Errors
------

Problem+JSON responses become typed exceptions:

.. code-block:: python

   from closecity import TokensExhaustedError, CloseAPIError

   try:
       close.block_summary("250173523004004")
   except TokensExhaustedError:
       ...                            # out of tokens (HTTP 429)
   except CloseAPIError as err:
       print(err.status, err.slug)

Spatial output
--------------

Turn a reply into a GeoDataFrame (needs ``pip install "closecity[geo]"``):

.. code-block:: python

   pts = close.pois_search(lat=41.823, lon=-71.412, radius_m=1500).to_geopandas()
   iso = close.isochrone(block="250173523004004", minutes=15).to_geopandas()

POIs become point geometry and isochrones become polygons offline; block replies
join to census-block boundaries (pass ``block_geometry=`` or ``fetch=True``).
