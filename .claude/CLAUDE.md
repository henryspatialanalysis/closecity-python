# closecity (Python SDK)

Python client for the Close travel-time API (https://api.close.city). httpx-based,
returns `geopandas` by default. Sphinx + Furo docs deploy to GitHub Pages; PyPI (via
OIDC trusted publishing) is the eventual target. Public repo:
`henryspatialanalysis/closecity-python`. The R sibling is
`henryspatialanalysis/closecity-r` -- keep the two SDKs behaviourally in step.

## Conventions (these are binding -- do not re-litigate)

- **Prose:** follow the humanizer STYLE (no em dashes, no hype, short active
  sentences, Oxford comma). Beginner audience: keep the getting-started glossary
  current. Explain, do not sell.
- **ASCII only** in all code and docs (no smart quotes, arrows, or non-ASCII glyphs).
- **Attribution:** copyright and funder is "Henry Spatial Analysis", never "Close".
  Author `Nathaniel Henry <nat@henryspatialanalysis.com>`.
- **Code style:** line length 90, spaces around `=` even inside calls (Nat overrides
  linters on this). `ruff` clean.
- **API shape:** `Client` with one method per route; `Reply` / `Paginator`. Feature
  methods convert to geopandas via `spatial.py` (`to_geopandas()` is also public).
- **Spatial by default:** feature methods (POIs, catchments, areal blocks, isochrones)
  return a `GeoDataFrame`. `Client(spatial=True)` is the default; `spatial=False` (on
  the client or per call) returns the raw `Reply`. Catalog/places/summaries stay raw.
- **Dependencies:** `geopandas>=0.14` is a hard dependency. `pygris` is the `[tiger]`
  extra, used only to fetch block boundaries for the GEOID-only block routes
  (`fetch=True`). Keep the runtime footprint minimal otherwise.
- **Tutorials (notebooks):** dead-simple and linear, **no helper functions**. Pull
  destination-type ids from the **free catalog** (`client.destination_types()`), never
  hardcode numeric codes. Draw a **map at each stage**. **No token-cost talk.** After a
  placeholder key, inline `# use your own key here`.
- **Example cities:** Somerville MA (home search), Richmond VA (amenity basket),
  Providence RI (competitor walksheds). **No Seattle anywhere.**
- **Docs execute live** at build time (see below), guarded on `CLOSECITY_KEY` so a
  keyless / PyPI build stays green (`conf.py` sets `nb_execution_mode` from the key).

## Gotchas (hard-won -- do not re-hit)

- **`blocks_query` needs JSON arrays:** the POST `/v1/blocks/query` body requires list
  fields, so scalar `mode`/`type` are normalised with `_as_list()`. A scalar mode
  returns 400.
- **CRS:** TIGER blocks arrive in NAD83 (EPSG:4269); `_blocks_gdf` reprojects to 4326
  so they match POI/isochrone geometry. geopandas warns / errors on mismatched CRS.
- **Blocks TIGER lacks** (e.g. water blocks) get NaN geometry from the left join;
  `_blocks_gdf` drops them (`geometry.notna()`) so plotting and spatial joins work. The
  block join renames the key to `geoid` before merging (the R SDK had a bug here; do
  not regress).
- **`place_blocks()` works since 2026-07-22** (server-side query fix in wtm.api). The
  home-search tutorial now uses it for whole-city pulls; `blocks_query` remains the
  tool for a radius or polygon. A rarely-queried big place can take a few seconds on
  the first call while the database cache warms; it is not broken again.

## Local live doc build (this EFS host)

```bash
python -m pip install -e '.[docs]'
export CLOSECITY_KEY=$(aws ssm get-parameter --name /wtm-api/internal-test-key \
  --with-decryption --region us-west-2 --query Parameter.Value --output text)  # do not print it
python -m sphinx -b html docs docs/_build/html -W --keep-going
```

Notebooks (`docs/getting_started.md` + `docs/tutorials/*.md`) are myst-nb `.md`
notebooks; they execute when the key is set (else `nb_execution_mode` is off). A hidden
`:tags: [remove-cell]` auth cell builds the real client; a display-only block shows the
placeholder key. `docs.yml` passes the `CLOSECITY_KEY` secret to the build. Tests:
`python -m pytest` (offline, no key).

## Git

Read-only unless Nat says otherwise; Nat runs commit sessions (modular, single-sentence,
present-tense messages, no AI-attribution trailers). Push is a separate gate.
