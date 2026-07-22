closecity
=========

Python client for the Close API (`api.close.city <https://api.close.city>`_). Get
travel times from every US census block to nearby places, on foot, by bike, and by
public transit. This is the data behind `close.city <https://close.city>`_.

.. code-block:: python

   from closecity import Client, close_map

   # The key (ck_live_) comes from https://account.close.city
   close = Client("ck_live_your_key")   # use your own key here

   # Routes with geometry return a GeoDataFrame, ready to map:
   supermarkets = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500, type = 30)
   close_map(supermarkets, color = "#e8590c")   # interactive map, bright hoverable points

Results are tabular by default: a GeoDataFrame where geometry applies, a plain
DataFrame otherwise. Install with ``pip install closecity``. The catalog and
lookup routes are free; the data routes need a key from
`account.close.city <https://account.close.city>`_.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   getting_started
   token_use
   tutorials/index
   api
