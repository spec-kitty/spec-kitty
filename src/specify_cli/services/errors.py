"""Service refusals: the fail-closed error vocabulary of the service launcher (#6590, FR-005).

Every way the CLI declines to run a service binary is a :class:`ServiceRefusal`
carrying a stable :class:`ServiceRefusalCode`, a message saying what is wrong
and a remedy saying what to do. Remedies come from one table
(:data:`_REMEDIES`) so the wording lives in one place. Nothing here ever
carries a token, a digest or an environment dump: callers pass only file
names, paths, target names and environment-variable *names*.

The existing ``WRITE_SERVICE_ENDPOINT_*`` codes
(``specify_cli.status.write_service_protocol.EndpointFileError``) are not
redefined here; they pass through unchanged.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from kernel.service_artifacts import ASSET_DIR_ENV, SERVICE_BINARY_DIGEST_MISMATCH, SERVICE_BINARY_MISSING
from kernel.service_pin import SERVICE_PIN_INVALID
from specify_cli.core.errors import StructuredError
from specify_cli.status import ENDPOINT_DIRECTORY

__all__ = ["ServiceRefusal", "ServiceRefusalCode", "remedy_for"]

_FETCH_COMMAND = "`spec-kitty service fetch`"
_STOP_COMMAND = "`spec-kitty service stop`"


class ServiceRefusalCode(enum.StrEnum):
    """The stable codes of a service refusal (``data-model.md``, ServiceRefusal).

    The codes the kernel already owns are imported, never redefined.
    """

    BINARY_MISSING = SERVICE_BINARY_MISSING
    DIGEST_MISMATCH = SERVICE_BINARY_DIGEST_MISMATCH
    UNSUPPORTED_PLATFORM = "SERVICE_UNSUPPORTED_PLATFORM"
    UNHEALTHY = "SERVICE_UNHEALTHY"
    VERSION_MISMATCH = "SERVICE_VERSION_MISMATCH"
    PIN_INVALID = SERVICE_PIN_INVALID


#: Remedy templates keyed by ``(code, variant)``; ``None`` is the default variant.
_REMEDIES: Mapping[tuple[ServiceRefusalCode, str | None], str] = MappingProxyType(
    {
        (ServiceRefusalCode.BINARY_MISSING, None): f"run {_FETCH_COMMAND} while online, or set {ASSET_DIR_ENV} to a directory holding {{asset}}",
        (ServiceRefusalCode.BINARY_MISSING, "explicit"): "point {env_var} at an existing file, or unset it to use the pinned build",
        (ServiceRefusalCode.BINARY_MISSING, "cache"): (
            "make the service cache {cache} writable (free space, fix its permissions), or set XDG_CACHE_HOME to a writable directory"
        ),
        (ServiceRefusalCode.BINARY_MISSING, "install"): "reinstall the package that provides the {service} binary, or uninstall it to use the pinned download",
        (ServiceRefusalCode.BINARY_MISSING, "spawn"): (
            "check that {program} can be executed: it needs its exec permission, and its file system must not be mounted noexec"
            f" (set XDG_CACHE_HOME to a directory on an exec-capable file system, then run {_FETCH_COMMAND})"
        ),
        (ServiceRefusalCode.DIGEST_MISMATCH, None): (
            f"delete {{path}} and run {_FETCH_COMMAND}; if it persists, the release or your mirror does not match the pin"
        ),
        (ServiceRefusalCode.DIGEST_MISMATCH, "asset_dir"): (
            f"replace or remove {{path}} in {ASSET_DIR_ENV} with the pinned release asset (check it against the release's SHA256SUMS);"
            f" or, online, run {_FETCH_COMMAND} without that file"
        ),
        (ServiceRefusalCode.DIGEST_MISMATCH, "explicit"): "point {env_var} at the pinned build for this host, or unset it to use the pinned download",
        (ServiceRefusalCode.DIGEST_MISMATCH, "install"): "install the binary package matching this spec-kitty version, or uninstall it to use the pinned download",
        (ServiceRefusalCode.UNSUPPORTED_PLATFORM, None): "install a Java 25 runtime (JAVA_HOME) to use the pinned jar, or run on one of: {targets}",
        (ServiceRefusalCode.UNSUPPORTED_PLATFORM, "no_jar"): "run on one of: {targets}; this spec-kitty pins no build for any other host",
        (ServiceRefusalCode.UNHEALTHY, None): f"see {{gcd}}/{ENDPOINT_DIRECTORY}/service.log; then {_STOP_COMMAND} and retry",
        (ServiceRefusalCode.UNHEALTHY, "state_dir"): (
            "make {directory} writable (the service keeps its endpoint and log there; a read-only or full git directory cannot host it),"
            " and remove a symlink named service.log there; then retry"
        ),
        (ServiceRefusalCode.VERSION_MISMATCH, None): f"upgrade spec-kitty or stop the running service ({_STOP_COMMAND})",
        (ServiceRefusalCode.PIN_INVALID, None): "this spec-kitty version has no pin for {service} yet",
        (ServiceRefusalCode.PIN_INVALID, "malformed"): "re-run `spec-kitty service vendor`",
    }
)


def remedy_for(code: ServiceRefusalCode, *, variant: str | None = None, **fields: object) -> str:
    """The remedy text of *code* (and *variant*), with *fields* filled in.

    Unknown variants fall back to the code's default remedy, so a refusal always
    carries one.
    """
    template = _REMEDIES.get((code, variant), _REMEDIES[(code, None)])
    return template.format(**fields)


class ServiceRefusal(StructuredError):
    """The CLI refuses to run a service binary; ``code`` says why, ``remedy`` what to do."""

    def __init__(self, code: ServiceRefusalCode, message: str, remedy: str) -> None:
        super().__init__(message)
        self.code = code
        self.error_code = code.value
        self.message = message
        self.remedy = remedy

    def __str__(self) -> str:
        return f"{self.message}\nRemedy: {self.remedy}\nError code: {self.code}."

    def to_dict(self) -> dict[str, Any]:
        """The JSON envelope: the code, the bare message and the remedy."""
        return {"error_code": self.error_code, "message": self.message, "remedy": self.remedy}
