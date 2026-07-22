"""Optional spatial conversion — turn Close API replies into GeoDataFrames.

Import-light and lazy: ``geopandas`` / ``shapely`` are needed only when you call a
converter, and are declared under the ``geo`` extra (``pip install
'closecity[geo]'``). The client's default return stays plain JSON.

Three response shapes are recognised automatically:

* **POI rows** (``lat`` / ``lon``) — :meth:`Client.pois_search`, :meth:`block_pois`,
  :meth:`point_pois`, :meth:`poi` — become **point** geometry, built offline.
* **Isochrone** ``format=geojson`` — :meth:`Client.isochrone` — becomes **polygon**
  geometry, built offline from the ``features`` envelope (which is a custom object,
  not a bare FeatureCollection).
* **Block rows** (``geoid`` only) — :meth:`blocks_query`, :meth:`place_blocks`,
  :meth:`poi_catchment`, :meth:`block_summary` — become **polygons** by joining census
  block boundaries you pass as ``block_geometry`` (a GeoDataFrame keyed on
  ``geoid_col``), or that we pull with ``pygris`` when ``fetch=True``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["to_geopandas"]


def _require_geopandas():
    try:
        import geopandas as gpd
        from shapely.geometry import Point, shape
    except ImportError as exc:  # pragma: no cover - exercised via install matrix
        raise ImportError(
            "Spatial conversion needs geopandas + shapely. "
            "Install the extra: pip install 'closecity[geo]'."
        ) from exc
    return gpd, Point, shape


def _normalise(source: Any) -> tuple[Any, list[dict]]:
    """Return ``(data, rows)`` for a Reply, Paginator, dict body, or row list."""
    from .client import Paginator, Reply

    if isinstance(source, Reply):
        return source.data, list(source.results or [])
    if isinstance(source, Paginator):
        return None, list(source)
    if isinstance(source, dict):
        rows = source.get("results")
        return source, list(rows) if isinstance(rows, list) else []
    if isinstance(source, list):
        return None, list(source)
    raise TypeError(
        f"Cannot convert {type(source).__name__}; pass a Reply, Paginator, or body."
    )


def _is_isochrone(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("features"), list)


def _isochrone_gdf(data: dict, gpd, shape, crs):
    geoms, records = [], []
    for feature in data.get("features") or []:
        geom = feature.get("geometry")
        geoms.append(shape(geom) if geom else None)
        records.append(dict(feature.get("properties") or {}))
    return gpd.GeoDataFrame(records, geometry = geoms, crs = crs)


def _points_gdf(rows: list[dict], gpd, Point, crs):
    geoms = [
        Point(r["lon"], r["lat"])
        if r.get("lon") is not None and r.get("lat") is not None
        else None
        for r in rows
    ]
    return gpd.GeoDataFrame(list(rows), geometry = geoms, crs = crs)


def _fetch_blocks(geoids: list[str], geoid_col: str):
    try:
        import pandas as pd
        import pygris
    except ImportError as exc:
        raise ImportError(
            "fetch=True needs pygris (and pandas). Install: pip install 'closecity[geo]'."
        ) from exc
    pairs = sorted({(g[:2], g[2:5]) for g in geoids if g})
    frames = [pygris.blocks(state = s, county = c, year = 2020, cache = True)
              for s, c in pairs]
    gdf = pd.concat(frames, ignore_index = True)
    if geoid_col not in gdf.columns and "GEOID20" in gdf.columns:
        gdf = gdf.rename(columns = {"GEOID20": geoid_col})
    return gdf


def _blocks_gdf(rows, block_geometry, geoid_col, crs, fetch, gpd):
    import pandas as pd

    df = pd.DataFrame(list(rows))
    if block_geometry is None:
        if fetch:
            block_geometry = _fetch_blocks([r.get("geoid") for r in rows], geoid_col)
        else:
            raise ValueError(
                "Block replies carry only GEOIDs. Pass block_geometry=<GeoDataFrame> "
                "(joined on `geoid_col`, default 'GEOID20'), or fetch=True to pull TIGER "
                "blocks with pygris."
            )
    geo = block_geometry.rename(columns = {geoid_col: "geoid"})
    merged = df.merge(geo[["geoid", "geometry"]], on = "geoid", how = "left")
    out_crs = getattr(block_geometry, "crs", None) or crs
    return gpd.GeoDataFrame(merged, geometry = "geometry", crs = out_crs)


def to_geopandas(
    source: Any,
    *,
    block_geometry: Any = None,
    geoid_col: str = "GEOID20",
    crs: Any = "EPSG:4326",
    fetch: bool = False,
):
    """Convert a Close API reply into a :class:`geopandas.GeoDataFrame`.

    ``source`` is a :class:`~closecity.Reply`, a :class:`~closecity.Paginator`
    (all pages are collected), or a raw response body. The geometry kind is
    detected from the payload; see the module docstring. ``block_geometry`` /
    ``geoid_col`` / ``fetch`` only apply to block replies. Requires the ``geo``
    extra.
    """
    gpd, Point, shape = _require_geopandas()
    data, rows = _normalise(source)

    if _is_isochrone(data):
        return _isochrone_gdf(data, gpd, shape, crs)

    first = rows[0] if rows else None
    if first is not None and "lat" in first and "lon" in first:
        return _points_gdf(rows, gpd, Point, crs)
    if first is not None and "geoid" in first:
        return _blocks_gdf(rows, block_geometry, geoid_col, crs, fetch, gpd)

    # Non-list bodies: a single POI dict, or a summary whose block is the geometry.
    if isinstance(data, dict):
        if data.get("lat") is not None and data.get("lon") is not None:
            return _points_gdf([data], gpd, Point, crs)
        block = data.get("block")
        if isinstance(block, dict) and block.get("geoid"):
            return _blocks_gdf([block], block_geometry, geoid_col, crs, fetch, gpd)

    raise ValueError(
        "This reply has no lat/lon, isochrone features, or block GEOIDs to build "
        "geometry from."
    )
