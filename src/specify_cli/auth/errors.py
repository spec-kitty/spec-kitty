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
        super().__init__(f"Refresh token was just rotated by another process (retry_after={retry_after}s).")
        self.retry_after: int = retry_after


class NetworkError(AuthenticationError):
    """Raised on network-level failures (timeouts, DNS, connection refused)."""


#: Stable remedy identifier surfaced by :class:`IssuerTargetMismatchError`.
#: Kept as a module constant so every raiser and every message quotes the
#: same recovery command (Sonar S1192) — see
#: ``kitty-specs/token-target-issuer-guard-01M319HS/contracts/issuer-target-helper.md``.
ISSUER_MISMATCH_REMEDY: str = "auth login --force"


class IssuerTargetMismatchError(AuthenticationError):
    """Raised when a stored session's issuer does not match the resolved server target.

    A session's ``issuer_url`` records the hosted server it was minted
    against (recorded at login). When the process now resolves a *different*
    server target (env var or ``config.toml`` changed since login), pairing
    the session's bearer tokens with that new target would send them
    somewhere they were never authenticated for. This error refuses that
    pairing instead of silently sending the token cross-target.

    The message names the issuer host, the resolved host, the configuration
    source the resolved target came from, and the stable remedy — and
    contains **zero token material** (NFR-006): callers must never
    interpolate an access or refresh token into this message.
    """

    def __init__(
        self,
        *,
        issuer_url: str,
        resolved_url: str,
        source_name: str,
        remedy: str = ISSUER_MISMATCH_REMEDY,
    ) -> None:
        super().__init__(f"Session is for {issuer_url}; {source_name} now points at {resolved_url} — run `spec-kitty {remedy}`.")
        self.issuer_url = issuer_url
        self.resolved_url = resolved_url
        self.remedy = remedy


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
