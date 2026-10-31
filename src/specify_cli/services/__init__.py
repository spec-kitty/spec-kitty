"""Pinned service binaries: resolution, verification and refusals (#6590).

The CLI runs a service (the Java write service, the charter service) only from
bytes whose SHA-256 matches the service's pin lockfile. This package resolves
those bytes (:func:`resolve_binary`), re-verifies them just before spawn
(:func:`verify_before_exec`) and refuses with a :class:`ServiceRefusal` otherwise.
There is no Python fallback writer.
"""

from __future__ import annotations

from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode
from specify_cli.services.resolution import ResolvedBinary, find_pin, resolve_binary, verify_before_exec

__all__ = ["ResolvedBinary", "ServiceRefusal", "ServiceRefusalCode", "find_pin", "resolve_binary", "verify_before_exec"]
