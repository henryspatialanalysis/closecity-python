Installation
============

The package will soon be published to PyPI. Until then, install it from GitHub:

.. code-block:: bash

   pip install git+https://github.com/henryspatialanalysis/closecity-python.git

Once it lands on PyPI, ``pip install closecity`` will work. Either way, this pulls
in `httpx <https://www.python-httpx.org/>`_ and
`geopandas <https://geopandas.org/>`_, so feature methods return GeoDataFrames out of
the box.

Optional extras
---------------

In the default spatial output mode, block methods (``blocks_query``,
``place_blocks``, ``poi_catchment``) join census-block boundaries. To let them
download the boundaries for you, add the ``tiger`` extra:

.. code-block:: bash

   pip install "closecity[tiger] @ git+https://github.com/henryspatialanalysis/closecity-python.git"

You do not need it for ``output="tabular"``, which returns the same rows without
geometry.

Plotting a GeoDataFrame uses matplotlib:

.. code-block:: bash

   pip install matplotlib

API keys
--------

The catalog and lookup routes are free and need no key. Every data route needs a
key (``ck_live_``), created at
`account.close.city <https://account.close.city>`_.

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key")   # use your own key here

Python 3.9 or newer is supported.
