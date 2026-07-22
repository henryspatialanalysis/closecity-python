"""A one-line interactive map for the GeoDataFrames the client returns.

Built on plotly over a CARTO Positron basemap: points become bright hoverable
markers, block polygons are filled and can highlight the features meeting a
criterion. plotly is GDAL-free (unlike leaflet/mapgl in R), and geopandas emits
the GeoJSON directly, so no extra system dependency.
"""

from __future__ import annotations

from typing import Any


def close_map(
    gdf,
    *,
    color: str = "#e8590c",
    highlight: Any = None,
    fill: Any = None,
    palette: str = "Viridis",
    reverse: bool = True,
    label: str = "name",
    size: int = 9,
    zoom: float = 10,
    opacity: float = 0.65,
):
    """Draw a :class:`geopandas.GeoDataFrame` from a client method as an
    interactive map on a CARTO Positron basemap.

    Points (POIs, places) render as bright hoverable markers; polygons (census
    blocks) are filled, optionally greying the features that do not meet
    ``highlight`` so the ones that matter stand out.

    ``highlight`` is either a boolean sequence (length ``len(gdf)``) or the name
    of a boolean/0-1 column. ``fill`` is the name of a numeric column to shade
    features by, on a continuous scale with a legend (use it OR ``highlight``);
    ``palette`` and ``reverse`` control that scale. ``label`` names the hover
    column. Returns a plotly ``Figure``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "close_map needs plotly: pip install 'closecity[maps]' or plotly"
        ) from exc

    g = gdf.to_crs(4326)
    hl = None
    if highlight is not None:
        col = g[highlight] if isinstance(highlight, str) else highlight
        hl = [bool(v) for v in col]
    fv = None
    if fill is not None and isinstance(fill, str) and fill in g.columns:
        fv = g[fill].astype(float).tolist()

    minx, miny, maxx, maxy = g.total_bounds
    center = {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2}
    hover = g[label].astype(str).tolist() if label in g.columns else None
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
        fig = go.Figure(go.Scattermapbox(
            lat = g.geometry.y.tolist(), lon = g.geometry.x.tolist(),
            mode = "markers", marker = marker,
            text = hover, hoverinfo = "text" if hover else "none",
        ))
    else:
        import json

        g = g.reset_index(drop = True)
        g["_id"] = [str(i) for i in range(len(g))]
        geojson = json.loads(g[["_id", "geometry"]].to_json())
        common = {
            "geojson": geojson, "locations": g["_id"].tolist(),
            "featureidkey": "properties._id",
            "marker": {"opacity": opacity, "line": {"width": 0}},
            "text": hover, "hoverinfo": "text" if hover else "none",
        }
        if fv is not None:
            trace = go.Choroplethmapbox(
                z = fv, colorscale = palette, reversescale = reverse,
                showscale = True, colorbar = {"title": fill}, **common)
        else:
            z = [1] * len(g) if hl is None else [int(h) for h in hl]
            colorscale = ([[0, color], [1, color]] if hl is None
                          else [[0, "#888888"], [1, color]])
            trace = go.Choroplethmapbox(
                z = z, colorscale = colorscale, showscale = False, **common)
        fig = go.Figure(trace)

    fig.update_layout(
        mapbox = {"style": "carto-positron", "zoom": zoom, "center": center},
        margin = {"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig
