"""close_map builds a plotly Figure from a GeoDataFrame; no network. Skipped
when the optional plotting deps are absent."""

import pytest

gpd = pytest.importorskip("geopandas")
pytest.importorskip("plotly")
from shapely.geometry import Point, Polygon  # noqa: E402

from closecity import close_map  # noqa: E402


def _points():
    return gpd.GeoDataFrame(
        {"name": ["A", "B"]},
        geometry = [Point(-71.41, 41.82), Point(-71.42, 41.83)],
        crs = 4326,
    )


def _polys():
    def sq(x, y):
        return Polygon([(x, y), (x + 0.01, y), (x + 0.01, y + 0.01),
                        (x, y + 0.01), (x, y)])
    return gpd.GeoDataFrame(
        {"name": ["g1", "g2"], "near": [True, False]},
        geometry = [sq(-71.42, 41.82), sq(-71.40, 41.82)], crs = 4326,
    )


def test_close_map_points():
    import plotly.graph_objects as go
    assert isinstance(close_map(_points(), color = "#e8590c"), go.Figure)


def test_close_map_polygons_with_highlight():
    import plotly.graph_objects as go
    fig = close_map(_polys(), color = "#2f9e44", highlight = "near")
    assert isinstance(fig, go.Figure)


def test_close_map_shades_by_fill():
    import plotly.graph_objects as go
    polys = _polys()
    polys["score"] = [2, 5]
    fig = close_map(polys, fill = "score", palette = "YlGnBu")
    assert isinstance(fig, go.Figure)


def test_close_map_boundary_and_background_layers():
    import plotly.graph_objects as go
    polys = _polys()
    boundary = polys.geometry.union_all()   # a bare shapely geometry
    fig = close_map(_points(), boundary = boundary,
                    background = [polys], background_color = "#3b6fb0")
    # one background fill + one boundary outline + the point layer
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3
