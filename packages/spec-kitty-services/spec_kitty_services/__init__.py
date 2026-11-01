"""``spec-kitty-services``: the optional companion of ``spec-kitty-cli`` (#6904).

A platform wheel of this distribution carries the pinned, digest-verified native
builds of the services the CLI launches (the write service and the charter
service) for one target, and registers them in the ``spec_kitty.service_binaries``
entry-point group that ``specify_cli.services.resolution`` consults after an
explicit path and before its cache (ADR 2026-10-29-1 D-5, Amendment 2026-10-31).

A provider returns the path of its bundled binary only when the companion was
built for the installed CLI version and for this host; otherwise it returns
``None`` and the CLI falls through to its cache and first-run fetch. It never
raises. Whatever it returns, the CLI still checks against its own pin.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

from spec_kitty_services.wheel import BIN_DIR, MANIFEST_NAME, ManifestError, parse_manifest

__all__ = ["charter_service", "write_service"]

#: The distribution whose version the companion is locked to.
_CLI_DISTRIBUTION = "spec-kitty-cli"


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _installed_cli_version() -> str | None:
    try:
        return importlib.metadata.version(_CLI_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return None


def _host_target() -> str | None:
    """This host's service target, from the CLI's own authority (``kernel.service_hosts``)."""
    from kernel.service_hosts import host_target  # lazy: a broken CLI install must not break importing the providers

    target = host_target()
    return None if target is None else target.value


def _pinned_sha256(service: str, target: str) -> str | None:
    """The sha256 the CLI's own pin names for *service* on *target*, or ``None`` when it pins none."""
    from kernel.service_pin import ServiceTarget  # lazy, like _host_target
    from specify_cli.services.resolution import find_pin, load_pin

    path = find_pin(service)
    if path is None:
        return None
    asset = load_pin(path).asset_for(ServiceTarget(target))
    return None if asset is None else asset.sha256


def _provide(service: str) -> str | None:
    package = _package_dir()
    manifest_path = package / MANIFEST_NAME
    if not manifest_path.is_file():
        return None  # a source checkout or an editable install: nothing is bundled
    try:
        manifest = parse_manifest(manifest_path.read_bytes())
    except (OSError, ManifestError):
        return None
    if manifest.target is None or manifest.cli_version != _installed_cli_version():
        return None  # the fallback wheel, or a version skew: the CLI fetches its own pinned build
    if manifest.target != _host_target():
        return None  # a wheel forced onto another platform
    binary = manifest.binary_for(service)
    if binary is None or binary.sha256 != _pinned_sha256(service, manifest.target):
        return None  # a build the CLI does not pin: step aside rather than have the CLI refuse it
    path = package / BIN_DIR / binary.asset
    return str(path) if path.is_file() and not path.is_symlink() else None


def _safe_provide(service: str) -> str | None:
    # Broad on purpose: the CLI turns a raising provider into a SERVICE_BINARY_MISSING
    # refusal that would block its own fetch, so any failure here must mean "offer nothing".
    try:
        return _provide(service)
    except Exception:
        return None


def write_service() -> str | None:
    """The bundled write-service binary for this host and CLI version, or ``None``."""
    return _safe_provide("write-service")


def charter_service() -> str | None:
    """The bundled charter-service binary for this host and CLI version, or ``None``."""
    return _safe_provide("charter-service")
