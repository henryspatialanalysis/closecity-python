closecity
=========

This is the Python software development kit for the Close.City API. It returns
travel times from every US census block to nearby places, on foot, by bike, and by
public transit. The data behind `close.city <https://close.city>`_ is served over
`api.close.city <https://api.close.city>`_.

.. code-block:: python

   from closecity import Client, close_map

   # The key (ck_live_) comes from https://account.close.city
   close = Client("ck_live_your_key")   # use your own key here

   # Routes with geometry return a GeoDataFrame, ready to map:
   supermarkets = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500, type = 30)
   close_map(supermarkets, color = "#e8590c")   # interactive map, bright hoverable points

By default, results come back as a GeoDataFrame where geometry applies (points,
isochrones, and block polygons) and a plain DataFrame otherwise. Install it from GitHub for now (see
:doc:`installation`); PyPI is coming. The catalog and lookup routes are free; the
data routes need a key from `account.close.city <https://account.close.city>`_.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   getting_started
   token_use
   tutorials/index
   api
