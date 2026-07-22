"""closecity: Python client for the Close API (https://api.close.city).

    from closecity import Client

    close = Client("ck_live_your_key")   # use your own key here
    groceries = close.pois_search(lat = 44.05, lon = -123.09, radius_m = 2000)
    groceries.plot()
"""

from .client import Client, Paginator, Reply
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
from .map import close_map
from .spatial import to_geopandas
from .tabular import to_pandas

__version__ = "1.3.0"

__all__ = [
    "Client",
    "Paginator",
    "Reply",
    "close_map",
    "to_geopandas",
    "to_pandas",
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
