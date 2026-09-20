"""Exception hierarchy for the spec-kitty auth subsystem (feature 080).

All auth-related errors inherit from ``AuthenticationError``. Other modules in
``specify_cli`` and downstream WPs import error types from this module only —
never from flow-internal modules — so the public contract stays stable.
"""

from __future__ import annotations


class AuthenticationError(Exception):
    """Base class for all spec-kitty auth errors."""


class NotAuthenticatedError(AuthenticationError):
    """Raised when an operation requires a session but none exists."""


class ConfigurationError(AuthenticationError):
    """Raised when configuration (env vars, etc.) is missing or invalid."""


class TokenRefreshError(AuthenticationError):
    """Base class for token refresh failures."""


class RefreshTokenExpiredError(TokenRefreshError):
    """Raised when the refresh token itself has expired (re-login required)."""


class SessionInvalidError(TokenRefreshError):
    """Raised when SaaS reports the session has been invalidated server-side."""


class RefreshReplayError(TokenRefreshError):
    """Raised when the server returns 409 refresh_replay_benign_retry.

    Indicates the presented refresh token was spent within the server's
    reuse-grace window. The token family is NOT revoked. The retry decision
    is made by run_refresh_transaction._run_locked, not the caller.
    """

    def __init__(self, retry_after: int = 0) -> None:
        super().__init__(
            f"Refresh token was just rotated by another process "
            f"(retry_after={retry_after}s)."
        )
        self.retry_after: int = retry_after


class NetworkError(AuthenticationError):
    """Raised on network-level failures (timeouts, DNS, connection refused)."""


# ----- Loopback / browser flow errors -----


class CallbackError(AuthenticationError):
    """Base class for OAuth callback errors."""


class CallbackTimeoutError(CallbackError):
    """Raised when the loopback callback server times out (5 minutes)."""


class CallbackValidationError(CallbackError):
    """Raised when the callback fails CSRF state validation or is malformed."""


class StateExpiredError(CallbackError):
    """Raised when the PKCEState used for the callback has expired."""


class BrowserLaunchError(AuthenticationError):
    """Raised when no browser is available to launch."""


# ----- Device flow errors -----


class DeviceFlowError(AuthenticationError):
    """Base class for device authorization flow errors."""


class DeviceFlowDenied(DeviceFlowError):
    """Raised when the user denies device authorization."""


class DeviceFlowExpired(DeviceFlowError):
    """Raised when the device code expires before user approval."""


# ----- Storage errors -----


class SecureStorageError(AuthenticationError):
    """Base class for secure storage backend errors."""


class StorageBackendUnavailableError(SecureStorageError):
    """Raised when no secure storage backend is available."""


class StorageDecryptionError(SecureStorageError):
    """Raised when an encrypted file cannot be decrypted (corruption, wrong key)."""


class SessionFilePermissionsError(SecureStorageError):
    """Raised when the session file has unsafe (non-owner-only) permissions.

    The secure-storage layer fails closed on read (NFR-013) rather than
    decrypting a file other local users could have read. The message always
    carries the built-in remedy (``chmod 600 <path>``) so callers can surface
    it instead of steering the user to ``auth login``, which would silently
    overwrite the loose file (#4761).
    """
