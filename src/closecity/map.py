"""A one-line interactive map for the GeoDataFrames the client returns.

Built on plotly over a CARTO Positron basemap: points become bright hoverable
markers, block polygons are filled and can highlight the features meeting a
criterion. The view auto-zooms to the data, hover shows every attribute, and a
city ``boundary`` outline or semi-transparent ``background`` layers can sit
underneath. plotly is GDAL-free (unlike leaflet/mapgl in R), and geopandas emits
the GeoJSON directly, so no extra system dependency.
"""

from __future__ import annotations

import math
from typing import Any

# Below this many filled polygons, draw one trace each (largest first) so
# overlapping fills — e.g. nested isochrone contours — each stay hoverable.
# Above it (block maps), a single trace keeps rendering fast.
_OVERLAP_MAX = 12


def _rgba(hexcolor: str, alpha: float) -> str:
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _as_layer(obj):
    """Normalise a boundary/background argument to a GeoDataFrame, accepting a
    GeoDataFrame, a GeoSeries, or a bare shapely geometry (assumed WGS84)."""
    import geopandas as gpd

    if isinstance(obj, gpd.GeoDataFrame):
        return obj
    if isinstance(obj, gpd.GeoSeries):
        return gpd.GeoDataFrame(geometry = obj)
    return gpd.GeoDataFrame(geometry = [obj], crs = "EPSG:4326")


def _bounds(g):
    minx, miny, maxx, maxy = g.total_bounds
    return [minx, miny, maxx, maxy]


def _center_zoom(bounds_list, buffer):
    """A CARTO-Positron centre and zoom that frame every layer, plus a margin."""
    minx = min(b[0] for b in bounds_list)
    miny = min(b[1] for b in bounds_list)
    maxx = max(b[2] for b in bounds_list)
    maxy = max(b[3] for b in bounds_list)
    center = {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2}
    span = max(maxx - minx, maxy - miny, 0.005) * (1 + 2 * buffer)
    zoom = max(1.0, min(16.0, math.log2(360 / span) - 0.5))
    return center, zoom


def _polygon_lines(g):
    """Exterior rings of every (multi)polygon as one lon/lat path, ``None``-split."""
    lons: list = []
    lats: list = []
    for geom in g.geometry:
        if geom is None or geom.is_empty:
            continue
        polys = list(geom.geoms) if geom.geom_type.startswith("Multi") else [geom]
        for poly in polys:
            x, y = poly.exterior.xy
            lons += list(x) + [None]
            lats += list(y) + [None]
    return lons, lats


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.5f}".rstrip("0").rstrip(".")
    if isinstance(v, dict):
        return ", ".join(str(x) for x in v.values() if x is not None)
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    return str(v)


def _hover(g, label):
    """One hover string per row: every non-geometry attribute, ``label`` first."""
    cols = [c for c in g.columns if c != g.geometry.name]
    lead = [label] if label and label in cols else []
    ordered = lead + [c for c in cols if c not in lead]
    out = []
    for _, row in g.iterrows():
        parts = [
            (f"<b>{_fmt(row[c])}</b>" if c == label else f"{c}: {_fmt(row[c])}")
            for c in ordered
        ]
        out.append("<br>".join(parts))
    return out


def close_map(
    gdf,
    *,
    color: str = "#e8590c",
    highlight: Any = None,
    fill: Any = None,
    palette: str = "YlGnBu",
    reverse: bool = False,
    label: str | None = None,
    size: int = 9,
    opacity: float = 0.65,
    boundary=None,
    background=None,
    background_color: Any = "#3b6fb0",
    background_opacity: float = 0.3,
    buffer: float = 0.15,
):
    """Draw a :class:`geopandas.GeoDataFrame` from a client method as an
    interactive map on a CARTO Positron basemap.

    Points (POIs, places) render as bright hoverable markers; polygons (census
    blocks) are filled, optionally greying the features that do not meet
    ``highlight`` so the ones that matter stand out. The view auto-zooms to fit
    every layer with a ``buffer`` margin, and hover shows all attributes.

    ``highlight`` is a boolean sequence or the name of a boolean/0-1 column.
    ``fill`` is the name of a numeric column to shade features by, on a
    continuous ColorBrewer scale with a legend (use it OR ``highlight``);
    ``palette`` (default ``"YlGnBu"``) and ``reverse`` control that scale.
    ``reverse=False`` puts the blue end at the high values; pass ``reverse=True``
    when high values mean *less* access, e.g. travel time.

    ``boundary`` is a polygon GeoDataFrame drawn as a grey outline underneath
    (e.g. a city boundary from ``place_boundary``). ``background`` is one polygon
    GeoDataFrame, or a list of them, drawn as semi-transparent fills underneath
    (e.g. commute isochrones or a walkshed); ``background_color`` recycles across
    them. Returns a plotly ``Figure``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "close_map needs plotly: pip install 'closecity[maps]' or plotly"
        ) from exc

    g = gdf.to_crs(4326)
    traces = []
    coloraxis = None
    bounds = [_bounds(g)]

    # Semi-transparent background fills, drawn first (underneath everything).
    if background is not None:
        layers = background if isinstance(background, (list, tuple)) else [background]
        colors = (background_color if isinstance(background_color, (list, tuple))
                  else [background_color])
        for i, layer in enumerate(layers):
            lg = _as_layer(layer).to_crs(4326)
            bounds.append(_bounds(lg))
            lons, lats = _polygon_lines(lg)
            col = colors[i % len(colors)]
            traces.append(go.Scattermapbox(
                lon=lons, lat=lats, mode="lines", fill="toself",
                fillcolor=_rgba(col, background_opacity),
                line={"color": _rgba(col, min(1.0, background_opacity + 0.3)),
                      "width": 1},
                hoverinfo="skip", showlegend=False,
            ))

    # City-boundary outline (no fill), above the background fills.
    if boundary is not None:
        bg = _as_layer(boundary).to_crs(4326)
        bounds.append(_bounds(bg))
        lons, lats = _polygon_lines(bg)
        traces.append(go.Scattermapbox(
            lon=lons, lat=lats, mode="lines",
            line={"color": "#666666", "width": 1.5},
            hoverinfo="skip", showlegend=False,
        ))

    hover = _hover(g, label)
    hl = None
    if highlight is not None:
        col = g[highlight] if isinstance(highlight, str) else highlight
        hl = [bool(v) for v in col]
    fv = None
    if fill is not None and isinstance(fill, str) and fill in g.columns:
        fv = g[fill].astype(float).tolist()

    geom_type = g.geom_type.iloc[0] if len(g) else "Point"
    if "Point" in geom_type:
        if fv is not None:
            marker = {"size": size, "color": fv, "colorscale": palette,
                      "reversescale": reverse, "showscale": True,
                      "colorbar": {"title": fill}}
        else:
            marker_color = color if hl is None else [
                color if h else "#888888" for h in hl
            ]
            marker = {"size": size, "color": marker_color}
        traces.append(go.Scattermapbox(
            lat=g.geometry.y.tolist(), lon=g.geometry.x.tolist(),
            mode="markers", marker=marker,
            text=hover, hoverinfo="text", showlegend=False,
        ))
    else:
        import json

        g = g.reset_index(drop=True)
        g["_id"] = [str(i) for i in range(len(g))]

        if fv is not None and len(g) <= _OVERLAP_MAX:
            # Filled polygons that may overlap (nested isochrone contours): one
            # trace each, largest first, so every one stays hoverable. A shared
            # coloraxis gives them a single colorbar.
            order = g.to_crs(3857).geometry.area.sort_values(ascending=False).index
            for i in order:
                sub = g.loc[[i], ["_id", "geometry"]].reset_index(drop=True)
                traces.append(go.Choroplethmapbox(
                    geojson=json.loads(sub.to_json()), locations=[g.at[i, "_id"]],
                    featureidkey="properties._id", z=[fv[i]], coloraxis="coloraxis",
                    marker={"opacity": opacity, "line": {"width": 0}},
                    text=[hover[i]], hoverinfo="text", showlegend=False))
            coloraxis = {"colorscale": palette, "reversescale": reverse,
                         "cmin": min(fv), "cmax": max(fv), "colorbar": {"title": fill}}
        else:
            geojson = json.loads(g[["_id", "geometry"]].to_json())
            common = {
                "geojson": geojson, "locations": g["_id"].tolist(),
                "featureidkey": "properties._id",
                "marker": {"opacity": opacity, "line": {"width": 0}},
                "text": hover, "hoverinfo": "text", "showlegend": False,
            }
            if fv is not None:
                traces.append(go.Choroplethmapbox(
                    z=fv, colorscale=palette, reversescale=reverse,
                    showscale=True, colorbar={"title": fill}, **common))
            else:
                z = [1] * len(g) if hl is None else [int(h) for h in hl]
                colorscale = ([[0, color], [1, color]] if hl is None
                              else [[0, "#888888"], [1, color]])
                traces.append(go.Choroplethmapbox(
                    z=z, colorscale=colorscale, showscale=False, **common))

    center, zoom = _center_zoom(bounds, buffer)
    fig = go.Figure(traces)
    fig.update_layout(
        mapbox={"style": "carto-positron", "zoom": zoom, "center": center},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    if coloraxis is not None:
        fig.update_layout(coloraxis=coloraxis)
    return fig
