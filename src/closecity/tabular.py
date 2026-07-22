"""Turn Close API replies into pandas DataFrames.

The client does this for you by default; this module is the machinery, and
:func:`to_pandas` is also usable by hand. Every list route (``results``) and every
catalog route (``places``, ``modes``, ``destination_types``, ``vintage``) becomes
one row per record; a single-object body (a POI detail) becomes a one-row frame;
an isochrone ``format=geojson`` reply becomes one row per contour (its feature
properties). Metering and envelope metadata that has no natural column ride along
on ``df.attrs`` (see :func:`_stamp_attrs`).

The row-shaping here is shared with :mod:`closecity.spatial`, which adds geometry
on top of the same frames.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

__all__ = ["to_pandas"]

# Top-level keys whose value is the per-record array for a given route. `results`
# covers every paginated and summary route; the rest are the catalog routes.
_ROW_KEYS = (
    "results", "places", "modes", "destination_types", "components", "blocks",
)
# Keys never worth copying onto df.attrs: the record arrays themselves, the GeoJSON
# feature list, the opaque cursor, and the constant "FeatureCollection" tag.
_SKIP_ATTR_KEYS = set(_ROW_KEYS) | {"features", "next_cursor", "type"}


def _is_isochrone(data: Any) -> bool:
    """True for an isochrone ``format=geojson`` body (a custom envelope whose
    ``features`` is a list, not a bare FeatureCollection)."""
    return isinstance(data, dict) and isinstance(data.get("features"), list)


def _meta_from_reply(reply: Any) -> dict[str, Any]:
    return {
        "status": reply.status,
        "tokens_charged": reply.tokens_charged,
        "tokens_remaining": reply.tokens_remaining,
        "etag": reply.etag,
        "request_id": reply.request_id,
    }


def _collect(source: Any) -> tuple[Any, dict[str, Any]]:
    """Return ``(data, meta)`` for a Reply, Paginator, dict body, or row list.

    For a Paginator every page is fetched once here: the rows are concatenated
    into a single ``results`` body carrying the first page's envelope, and the
    metering is folded together (charges summed, the rest taken from the last
    page). This is the only place that walks a Paginator, so callers never
    re-iterate it.
    """
    from .client import Paginator, Reply

    if isinstance(source, Reply):
        return source.data, _meta_from_reply(source)
    if isinstance(source, Paginator):
        return _collect_pages(source)
    if isinstance(source, dict):
        return source, {}
    if isinstance(source, list):
        return list(source), {}
    raise TypeError(
        f"Cannot convert {type(source).__name__}; pass a Reply, Paginator, or body."
    )


def _collect_pages(paginator: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    rows: list[dict] = []
    envelope: dict[str, Any] | None = None
    charged = 0
    charged_any = False
    last = None
    for reply in paginator.pages():
        last = reply
        if envelope is None and isinstance(reply.data, dict):
            envelope = {
                k: v for k, v in reply.data.items() if not isinstance(v, list)
            }
        rows.extend(reply.results)
        if reply.tokens_charged is not None:
            charged += reply.tokens_charged
            charged_any = True
    meta: dict[str, Any] = {}
    if last is not None:
        meta = {
            "status": last.status,
            "tokens_charged": charged if charged_any else None,
            "tokens_remaining": last.tokens_remaining,
            "etag": last.etag,
            "request_id": last.request_id,
        }
    data = dict(envelope or {})
    data["results"] = rows
    return data, meta


def _rows_and_envelope(data: Any, key: str | None = None) -> tuple[list[dict], Any]:
    """Split a body into ``(rows, envelope)``.

    ``envelope`` is the surrounding dict when the rows came from a record array
    (so its scalar members are metadata worth stamping), or None when the body
    itself is the single row (a POI detail) and its members are real columns.
    """
    if isinstance(data, list):
        return list(data), None
    if not isinstance(data, dict):
        return [], None
    candidates = (key, *_ROW_KEYS) if key else _ROW_KEYS
    for name in candidates:
        if name and isinstance(data.get(name), list):
            return list(data[name]), data
    return [data], None


def _broadcast_geoid(df: pd.DataFrame, envelope: Any) -> None:
    """Give summary frames an origin ``geoid`` column so they are self-describing
    and can be concatenated across blocks. Only the summary routes carry the
    origin block as an envelope ``block`` dict."""
    if len(df) == 0 or "geoid" in df.columns:
        return
    block = envelope.get("block") if isinstance(envelope, dict) else None
    geoid = block.get("geoid") if isinstance(block, dict) else None
    if geoid is not None:
        df.insert(0, "geoid", geoid)


def _stamp_attrs(df: pd.DataFrame, envelope: Any, meta: dict[str, Any]) -> None:
    """Attach metering and leftover envelope fields to ``df.attrs``.

    pandas ``attrs`` do not reliably survive downstream frame operations, so read
    them right after the call (or use ``output="raw"`` when the metadata is load
    bearing). Populated: ``status``, ``tokens_charged``, ``tokens_remaining``,
    ``etag``, ``request_id``, plus route envelope such as ``block_geoid``,
    ``resolved_block``, ``dest_id``, ``direction``, ``assumptions``.
    """
    for key, value in meta.items():
        if value is not None:
            df.attrs[key] = value
    if isinstance(envelope, dict):
        for key, value in envelope.items():
            if key not in _SKIP_ATTR_KEYS:
                df.attrs[key] = value


def to_pandas(source: Any, *, key: str | None = None) -> pd.DataFrame:
    """Convert a Close API reply into a :class:`pandas.DataFrame`.

    ``source`` is a :class:`~closecity.Reply`, a :class:`~closecity.Paginator`
    (all pages are collected), or a raw response body. ``key`` names the record
    array explicitly; when omitted it is detected from the body. Metering and
    envelope metadata land on ``df.attrs``.
    """
    data, meta = _collect(source)
    if _is_isochrone(data):
        rows = [dict(f.get("properties") or {}) for f in (data.get("features") or [])]
        envelope: Any = data
    else:
        rows, envelope = _rows_and_envelope(data, key)
    df = pd.DataFrame(list(rows))
    _broadcast_geoid(df, envelope)
    _stamp_attrs(df, envelope, meta)
    return df
