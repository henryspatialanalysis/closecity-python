Installation
============

.. code-block:: bash

   pip install closecity

The only runtime dependency is `httpx <https://www.python-httpx.org/>`_.

Optional extras
---------------

.. code-block:: bash

   pip install "closecity[geo]"    # GeoPandas / Shapely output (to_geopandas)

The ``geo`` extra pulls in ``geopandas`` and ``shapely`` for
:func:`closecity.to_geopandas`, plus ``pygris`` for the ``fetch=True``
census-block boundary download.

API keys
--------

The catalog and health routes are free and need no key. Every data route needs an
API key (``ck_live_…`` or ``ck_test_…``), created at
`account.close.city <https://account.close.city>`_. Pass it to the client:

.. code-block:: python

   from closecity import Client
   close = Client("ck_live_your_key_here")

Python 3.9 or newer is supported.
