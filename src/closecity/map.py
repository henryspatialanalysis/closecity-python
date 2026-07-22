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
    of a boolean/0-1 column. ``label`` names the hover column. Returns a plotly
    ``Figure``.
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

    minx, miny, maxx, maxy = g.total_bounds
    center = {"lon": (minx + maxx) / 2, "lat": (miny + maxy) / 2}
    hover = g[label].astype(str).tolist() if label in g.columns else None
    geom_type = g.geom_type.iloc[0] if len(g) else "Point"

    if "Point" in geom_type:
        marker_color = color if hl is None else [
            color if h else "#888888" for h in hl
        ]
        fig = go.Figure(go.Scattermapbox(
            lat = g.geometry.y.tolist(), lon = g.geometry.x.tolist(),
            mode = "markers",
            marker = dict(size = size, color = marker_color),
            text = hover, hoverinfo = "text" if hover else "none",
        ))
    else:
        import json

        g = g.reset_index(drop = True)
        g["_id"] = [str(i) for i in range(len(g))]
        z = [1] * len(g) if hl is None else [int(h) for h in hl]
        geojson = json.loads(g[["_id", "geometry"]].to_json())
        colorscale = (
            [[0, color], [1, color]] if hl is None
            else [[0, "#888888"], [1, color]]
        )
        fig = go.Figure(go.Choroplethmapbox(
            geojson = geojson, locations = g["_id"].tolist(), z = z,
            featureidkey = "properties._id", colorscale = colorscale,
            showscale = False,
            marker = dict(opacity = opacity, line = dict(width = 0)),
            text = hover, hoverinfo = "text" if hover else "none",
        ))

    fig.update_layout(
        mapbox = dict(style = "carto-positron", zoom = zoom, center = center),
        margin = dict(l = 0, r = 0, t = 0, b = 0),
    )
    return fig
