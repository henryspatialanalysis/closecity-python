closecity
=========

Python client for the **Close API** (`api.close.city <https://api.close.city>`_) —
travel times from every US census block to nearby points of interest, by walking,
biking, and public transit.

.. code-block:: python

   from closecity import Client

   # The catalog and health routes are free; data routes need a key from
   # https://account.close.city
   with Client("ck_live_your_key_here") as close:
       # Fastest walk time to each destination category from a census block.
       summary = close.block_summary("250173523004004", mode="walk")
       for row in summary.results:
           print(row["dest_type_id"], row["travel_time"])

       # Metering is surfaced on every metered reply.
       print(summary.tokens_charged, "charged;", summary.tokens_remaining, "left")

The client mirrors the public API exactly and makes its mechanics first-class:
per-request **metering** (``tokens_charged`` / ``tokens_remaining``), **ETag / 304**
conditional requests, opaque-cursor **pagination**, typed **RFC 9457** errors, and
opt-in **GeoPandas** output.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   getting_started
   tutorials/index
   api
