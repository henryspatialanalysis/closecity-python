closecity
=========

Python client for the Close API (`api.close.city <https://api.close.city>`_). Get
travel times from every US census block to nearby places, on foot, by bike, and by
public transit. This is the data behind `close.city <https://close.city>`_.

.. code-block:: python

   from closecity import Client

   # The key (ck_live_ or ck_test_) comes from https://account.close.city
   close = Client("ck_live_your_key")   # use your own key here

   # Feature methods return a GeoDataFrame, ready to map:
   groceries = close.pois_search(lat = 41.823, lon = -71.412, radius_m = 1500)
   groceries.plot()

Install with ``pip install closecity``. The catalog and lookup routes are free; the
data routes need a key from `account.close.city <https://account.close.city>`_.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   getting_started
   tutorials/index
   api
