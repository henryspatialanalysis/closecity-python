"""Exceptions mapped from the API's RFC 9457 ``problem+json`` responses.

Every error the API returns has a stable ``type`` URI whose final path segment is
the *slug* (e.g. ``tokens-exhausted``). We map on that slug, falling back to the
HTTP status, so callers can catch a precise class or the ``CloseAPIError`` base.
"""

from __future__ import annotations

from typing import Any

PROBLEM_SLUG_PREFIX = "https://api.close.city/problems/"


class CloseError(Exception):
    """Base class for every error raised by this client."""


class CloseAPIError(CloseError):
    """An error response from the API (a problem+json body).

    Attributes mirror the problem document: ``slug`` (the stable machine key),
    ``title``, ``status``, ``detail``, plus ``request_id`` (from ``X-Request-Id``,
    quote it in support requests), ``retry_after`` when present, and ``extras``
    for any additional problem members (e.g. validation ``errors``).
    """

    def __init__(
        self,
        *,
        status: int,
        slug: str,
        title: str,
        detail: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        extras: dict[str, Any] | None = None,
    ):
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail
        self.request_id = request_id
        self.retry_after = retry_after
        self.extras = extras or {}
        message = f"{status} {slug}: {title}"
        if detail:
            message += f": {detail}"
        if request_id:
            message += f" (request {request_id})"
        super().__init__(message)


# --- families, so callers can catch broad or narrow ------------------------

class BadRequestError(CloseAPIError):
    """400: invalid parameters, cursor, geometry, bbox, etc."""


class AuthenticationError(CloseAPIError):
    """401: missing or invalid API key."""


class PermissionDeniedError(CloseAPIError):
    """403: the key's account is disabled (or membership is required)."""


class NotFoundError(CloseAPIError):
    """404: the block, POI, place, or point is not in the published data."""


class RateLimitedError(CloseAPIError):
    """429 rate-limited: too many requests; see ``retry_after``."""


class TokensExhaustedError(CloseAPIError):
    """429 tokens-exhausted: the account's token balance is zero."""


class ServiceUnavailableError(CloseAPIError):
    """503: a backend is briefly unavailable; the request was not charged."""


# Slug -> class for the cases that need a distinct type. Everything else falls
# back to the status map below.
_BY_SLUG = {
    "tokens-exhausted": TokensExhaustedError,
    "rate-limited": RateLimitedError,
}

_BY_STATUS = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitedError,
    503: ServiceUnavailableError,
}


def error_from_problem(
    status: int,
    body: dict[str, Any],
    request_id: str | None,
    retry_after: float | None,
) -> CloseAPIError:
    """Build the most specific exception for a problem+json body."""

    type_uri = body.get("type", "")
    slug = type_uri[len(PROBLEM_SLUG_PREFIX):] if type_uri.startswith(
        PROBLEM_SLUG_PREFIX
    ) else (type_uri or f"http-{status}")
    cls = _BY_SLUG.get(slug) or _BY_STATUS.get(status, CloseAPIError)
    known = {"type", "title", "status", "detail"}
    extras = {k: v for k, v in body.items() if k not in known}
    return cls(
        status = status,
        slug = slug,
        title = body.get("title", ""),
        detail = body.get("detail"),
        request_id = request_id,
        retry_after = retry_after,
        extras = extras,
    )
