"""Which pinned service build runs on this host (#6590, research R-6).

The one authority for the platform-to-target table (:data:`HOST_TARGETS`,
:func:`host_target`) and for the "native build for this host, else the jar"
rule (:func:`select_build`). The sync script (``scripts/sync_services.py``,
which imports only ``kernel``), ``spec-kitty service fetch`` and binary
resolution all read these, so the three never disagree on which build a host
gets. Finding a Java runtime for the jar stays in ``specify_cli.services.host``.

Standard library only: ``kernel`` is the zero-dependency root layer.
"""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from kernel.service_pin import ServiceAsset, ServicePin, ServiceTarget

__all__ = ["host_target", "select_build"]

#: ``(platform.system(), platform.machine().lower())`` to the native release target.
HOST_TARGETS: Mapping[tuple[str, str], ServiceTarget] = MappingProxyType(
    {
        ("Linux", "x86_64"): ServiceTarget.LINUX_X64,
        ("Linux", "amd64"): ServiceTarget.LINUX_X64,
        ("Linux", "aarch64"): ServiceTarget.LINUX_ARM64,
        ("Linux", "arm64"): ServiceTarget.LINUX_ARM64,
        ("Darwin", "arm64"): ServiceTarget.MACOS_ARM64,
        ("Windows", "amd64"): ServiceTarget.WINDOWS_X64,
        ("Windows", "x86_64"): ServiceTarget.WINDOWS_X64,
    }
)


def host_target(*, system: str | None = None, machine: str | None = None) -> ServiceTarget | None:
    """The native release target of this host (or of *system*/*machine*), else ``None``."""
    key = (system if system is not None else platform.system(), (machine if machine is not None else platform.machine()).lower())
    return HOST_TARGETS.get(key)


@dataclass(frozen=True)
class SelectedBuild:
    """The build a host runs: its target (a native one, or ``jvm``) and the pinned asset."""

    target: ServiceTarget
    asset: ServiceAsset


def select_build(pin: ServicePin, host: ServiceTarget | None) -> SelectedBuild | None:
    """The pinned native build for *host*, else the pinned jar, else ``None`` (nothing this host can run)."""
    native = pin.asset_for(host) if host is not None else None
    if host is not None and native is not None:
        return SelectedBuild(host, native)
    jar = pin.asset_for(ServiceTarget.JVM)
    return None if jar is None else SelectedBuild(ServiceTarget.JVM, jar)
