"""Spec-kitty auth subsystem (feature 080: browser-mediated OAuth CLI auth).

Public API:

- :func:`get_token_manager` — process-wide :class:`TokenManager` factory with
  double-checked-locking lazy init. Every WP that needs a bearer token calls
  ``await get_token_manager().get_access_token()``.
- :func:`reset_token_manager` — test-only helper to drop the shared instance
  between test cases (used by ``tests/auth/conftest.py``).
- :class:`TokenManager` — re-exported for type hints and direct construction
  in unit tests.
- :class:`SecureStorage` — re-exported so callers can construct custom
  backends or use ``SecureStorage.from_environment()`` directly.
- The auth error hierarchy — re-exported so downstream code imports errors
  from ``specify_cli.auth`` instead of flow-internal modules.

The singleton state lives in :mod:`specify_cli.auth.manager` to avoid
mutable globals at package-init time. Double-checked locking rationale is
documented there.
"""

from __future__ import annotations

from .errors import (
    AuthenticationError,
    BrowserLaunchError,
    CallbackError,
    CallbackTimeoutError,
    CallbackValidationError,
    ConfigurationError,
    DeviceFlowDenied,
    DeviceFlowError,
    DeviceFlowExpired,
    NetworkError,
    NotAuthenticatedError,
    RefreshTokenExpiredError,
    SecureStorageError,
    SessionFilePermissionsError,
    SessionInvalidError,
    StateExpiredError,
    StorageBackendUnavailableError,
    StorageDecryptionError,
    TokenRefreshError,
)
from .manager import get_token_manager, reset_token_manager
from .secure_storage import SecureStorage
from .token_manager import TokenManager

__all__ = [
    # Factory + test helper
    "get_token_manager",
    "reset_token_manager",
    # Core classes
    "TokenManager",
    "SecureStorage",
    # Error hierarchy
    "AuthenticationError",
    "NotAuthenticatedError",
    "ConfigurationError",
    "TokenRefreshError",
    "RefreshTokenExpiredError",
    "SessionInvalidError",
    "NetworkError",
    "CallbackError",
    "CallbackTimeoutError",
    "CallbackValidationError",
    "StateExpiredError",
    "BrowserLaunchError",
    "DeviceFlowError",
    "DeviceFlowDenied",
    "DeviceFlowExpired",
    "SecureStorageError",
    "SessionFilePermissionsError",
    "StorageBackendUnavailableError",
    "StorageDecryptionError",
]
