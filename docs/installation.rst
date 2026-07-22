Installation
============

.. code-block:: bash

   pip install closecity

This pulls in `httpx <https://www.python-httpx.org/>`_ and
`geopandas <https://geopandas.org/>`_, so feature methods return GeoDataFrames out of
the box.

Optional extras
---------------

Block methods (``blocks_query``, ``place_blocks``, ``poi_catchment``) join
census-block boundaries. To let them download the boundaries for you, add the
``tiger`` extra:

.. code-block:: bash

   pip install "closecity[tiger]"

Plotting a GeoDataFrame uses matplotlib:

.. code-block:: bash

   pip install matplotlib

API keys
--------

The catalog and lookup routes are free and need no key. Every data route needs a key
(``ck_live_`` or ``ck_test_``), created at
`account.close.city <https://account.close.city>`_.

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key")   # use your own key here

Python 3.9 or newer is supported.
