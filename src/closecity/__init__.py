"""closecity — Python client for the Close API (https://api.close.city).

    from closecity import Client

    with Client("ck_live_…") as close:
        print(close.block_summary("410390020001010").data)
        for poi in close.pois_search(lat = 44.05, lon = -123.09, radius_m = 2000):
            print(poi["name"])
"""

from .client import Client, Paginator, Reply
from .spatial import to_geopandas
from .errors import (
    AuthenticationError,
    BadRequestError,
    CloseAPIError,
    CloseError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ServiceUnavailableError,
    TokensExhaustedError,
)

__version__ = "1.0.0"

__all__ = [
    "Client",
    "Paginator",
    "Reply",
    "to_geopandas",
    "CloseError",
    "CloseAPIError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitedError",
    "TokensExhaustedError",
    "ServiceUnavailableError",
    "__version__",
]
