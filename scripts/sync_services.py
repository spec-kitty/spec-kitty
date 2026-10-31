#!/usr/bin/env python3
"""Fetch and verify the pinned service assets for this host into the shared cache (#6590).

Thin argparse wrapper over :mod:`kernel.service_artifacts`; it holds no fetch or
verification logic. For each ``pins/<service>.source.yaml`` (or the one named by
``--service``) it takes the host's native build (the jar when the pin has no
build for this host) plus every extras asset, and fetches and verifies each into
``${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services``. ``make sync-services`` runs
``--service all``.

- ``--offline``: use only the cache and ``SPEC_KITTY_SERVICE_ASSET_DIR``; never download.
- ``--check``: verify the cached copies against the pins; fetch, write and delete nothing.

No pin yet (spec-kitty-events has not cut its first ``service-v*`` release):
prints ``no service pinned`` and exits 0. Exit 1 on any failure, with a stable
``SERVICE_*`` code on stderr.

It imports only from ``kernel`` (run with ``PYTHONPATH=src``), so it works
before, or without, an editable project install.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.service_hosts import host_target, select_build
from kernel.service_artifacts import (
    SERVICE_BINARY_DIGEST_MISMATCH,
    SERVICE_BINARY_MISSING,
    ServiceArtifactError,
    cached_path,
    default_cache_root,
    fetch_asset,
    verify_asset,
)
from kernel.service_pin import (
    KNOWN_SERVICES,
    PIN_SUFFIX,
    PINS_DIR,
    SERVICE_PIN_INVALID,
    ServiceAsset,
    ServicePin,
    ServicePinError,
    ServiceTarget,
    load_service_pin,
    pin_file,
)

SERVICE_UNSUPPORTED_PLATFORM = "SERVICE_UNSUPPORTED_PLATFORM"
NO_SERVICE_PINNED = "no service pinned"
_ALL = "all"
_REMEDY = "run `make sync-services`"


class SyncServicesError(RuntimeError):
    """One refusal: a stable ``SERVICE_*`` code and a message naming the asset or pin."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code} {message}")
        self.code = code


@dataclass(frozen=True)
class Wanted:
    """One asset to fetch or check: the label it is reported under and the pinned asset."""

    label: str
    asset: ServiceAsset


def pinned_services(root: Path) -> list[str]:
    """The services that have a lockfile under ``<root>/pins``, sorted."""
    pins_dir = root / PINS_DIR
    if not pins_dir.is_dir():
        return []
    return sorted(path.name[: -len(PIN_SUFFIX)] for path in pins_dir.glob(f"*{PIN_SUFFIX}") if path.is_file())


def _load(root: Path, service: str) -> ServicePin:
    try:
        return load_service_pin(pin_file(root / PINS_DIR, service))
    except ServicePinError as exc:
        raise SyncServicesError(SERVICE_PIN_INVALID, f"{service}: {exc}") from exc


def wanted_assets(pin: ServicePin, host: ServiceTarget | None) -> list[Wanted]:
    """The host's native build (else the jar; ``kernel.service_hosts.select_build``), then every extras asset."""
    build = select_build(pin, host)
    if build is None:
        targets = ", ".join(sorted(target.value for target in pin.assets))
        raise SyncServicesError(
            SERVICE_UNSUPPORTED_PLATFORM,
            f"{pin.service} {pin.tag}: no build for this host and no jar (pinned targets: {targets})",
        )
    return [Wanted(build.target.value, build.asset), *(Wanted(key, asset) for key, asset in sorted(pin.extras.items()))]


def _check_one(pin: ServicePin, item: Wanted, cache_root: Path) -> str:
    """Verify the cached copy without changing anything (a bad copy is reported, not evicted)."""
    path = cached_path(pin, item.asset, cache_root)
    if verify_asset(path, item.asset):
        return f"{pin.service} {pin.tag} {item.label}: ok {path}"
    if path.is_symlink() or path.exists():
        raise SyncServicesError(SERVICE_BINARY_DIGEST_MISMATCH, f"{item.asset.name}: the cached copy does not match the pinned sha256; {_REMEDY}")
    raise SyncServicesError(SERVICE_BINARY_MISSING, f"{item.asset.name}: not in the cache; {_REMEDY}")


def _fetch_one(pin: ServicePin, item: Wanted, cache_root: Path, *, offline: bool) -> str:
    try:
        path = fetch_asset(pin, item.asset, offline=offline, cache_root=cache_root)
    except ServiceArtifactError as exc:
        raise SyncServicesError(exc.code, f"{item.asset.name}: {str(exc).removeprefix(f'{exc.code}: ')}") from exc
    return f"{pin.service} {pin.tag} {item.label}: verified {path}"


def _run_service(root: Path, service: str, cache_root: Path, *, offline: bool, check: bool, report: Callable[[str], None]) -> bool:
    """Fetch (or check) every wanted asset of *service*; True when any of them failed."""
    try:
        pin = _load(root, service)
        items = wanted_assets(pin, host_target())
    except SyncServicesError as exc:
        report(str(exc))
        return True
    failed = False
    for item in items:
        try:
            line = _check_one(pin, item, cache_root) if check else _fetch_one(pin, item, cache_root, offline=offline)
        except SyncServicesError as exc:
            failed = True
            report(str(exc))
        else:
            print(line)
    return failed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sync_services", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--service", choices=[*sorted(KNOWN_SERVICES), _ALL], default=_ALL)
    parser.add_argument("--offline", action="store_true", help="use only the cache and SPEC_KITTY_SERVICE_ASSET_DIR; never download")
    parser.add_argument("--check", action="store_true", help="verify the cached assets against their pins; change nothing")
    return parser


def _report(message: str) -> None:
    print(message, file=sys.stderr)


def main(argv: Sequence[str] | None = None, *, repo_root: Path | None = None, cache_root: Path | None = None) -> int:
    """Fetch and verify; *repo_root* defaults to this script's repository, *cache_root* to the shared cache."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    cache = default_cache_root() if cache_root is None else Path(cache_root)
    if args.service == _ALL:
        services = pinned_services(root)
        if not services:
            print(NO_SERVICE_PINNED)
            return 0
    else:
        services = [args.service]
    failed = False
    for service in services:
        failed |= _run_service(root, service, cache, offline=args.offline, check=args.check, report=_report)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
