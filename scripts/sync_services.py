#!/usr/bin/env python3
"""Fetch, verify and unpack the pinned service assets for this host into the shared cache (#6590, #6915).

Thin argparse wrapper over :mod:`kernel.service_artifacts`; it holds no fetch or
verification logic of its own. For each ``pins/<service>.source.yaml`` (or the one named by
``--service``) it takes the host's native build (the jar when the pin has no
build for this host) plus every extras asset, and fetches and verifies each into
``${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services``. Every verified extras archive
(``*.tar.gz``) is then unpacked once into ``<tag dir>/<its pinned sha256>/``: a pin bump
changes that directory, so a stale tree is never read. ``make sync-services`` runs
``--service all``; ``make dev-setup`` runs it with ``--extras-only``.

- ``--offline``: use only the cache and ``SPEC_KITTY_SERVICE_ASSET_DIR``; never download.
- ``--check``: verify the cached copies against the pins; fetch, write, unpack and delete nothing.
- ``--extras-only``: only the extras (contract bundles, contract tools, conformance fixtures), no build.
- ``--extras-path SERVICE:EXTRA``: print where that extra is unpacked (unpacking the verified
  cached archive if needed); never downloads. Tests and CI steps read the pinned extras here.

No pin at all prints ``no service pinned`` and exits 0. Exit 1 on any failure, with a
stable ``SERVICE_*`` code on stderr; an archive member that is not a plain file or
directory, or that leaves the extraction root, refuses the whole archive
(``SERVICE_ASSET_ARCHIVE_UNSAFE``).

It imports only from ``kernel`` (run with ``PYTHONPATH=src``), so it works
before, or without, an editable project install.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

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
    KNOWN_EXTRAS,
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
SERVICE_ASSET_ARCHIVE_UNSAFE = "SERVICE_ASSET_ARCHIVE_UNSAFE"
NO_SERVICE_PINNED = "no service pinned"
NO_EXTRAS_PINNED = "no extras pinned"
_ALL = "all"
_REMEDY = "run `make sync-services`"
_ARCHIVE_SUFFIX = ".tar.gz"
_PARTIAL = ".partial-"


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


def _extras(pin: ServicePin) -> list[Wanted]:
    return [Wanted(key, asset) for key, asset in sorted(pin.extras.items())]


def wanted_assets(pin: ServicePin, host: ServiceTarget | None, *, extras_only: bool = False) -> list[Wanted]:
    """The host's native build (else the jar; ``kernel.service_hosts.select_build``), then every extras asset.

    With *extras_only*, the extras alone: no native build and no jar (``--extras-only``).
    """
    if extras_only:
        return _extras(pin)
    build = select_build(pin, host)
    if build is None:
        targets = ", ".join(sorted(target.value for target in pin.assets))
        raise SyncServicesError(
            SERVICE_UNSUPPORTED_PLATFORM,
            f"{pin.service} {pin.tag}: no build for this host and no jar (pinned targets: {targets})",
        )
    return [Wanted(build.target.value, build.asset), *_extras(pin)]


def _verified_cached(pin: ServicePin, asset: ServiceAsset, cache_root: Path) -> Path:
    """The cached copy of *asset* when its bytes match the pin; never downloads, never evicts."""
    path = cached_path(pin, asset, cache_root)
    if verify_asset(path, asset):
        return path
    if path.is_symlink() or path.exists():
        raise SyncServicesError(SERVICE_BINARY_DIGEST_MISMATCH, f"{asset.name}: the cached copy does not match the pinned sha256; {_REMEDY}")
    raise SyncServicesError(SERVICE_BINARY_MISSING, f"{asset.name}: not in the cache; {_REMEDY}")


def _check_one(pin: ServicePin, item: Wanted, cache_root: Path) -> str:
    """Verify the cached copy without changing anything (a bad copy is reported, not evicted)."""
    path = _verified_cached(pin, item.asset, cache_root)
    return f"{pin.service} {pin.tag} {item.label}: ok {path}"


def _fetch_one(pin: ServicePin, item: Wanted, cache_root: Path, *, offline: bool) -> str:
    try:
        path = fetch_asset(pin, item.asset, offline=offline, cache_root=cache_root)
    except ServiceArtifactError as exc:
        raise SyncServicesError(exc.code, f"{item.asset.name}: {str(exc).removeprefix(f'{exc.code}: ')}") from exc
    if _is_archive(item.asset):
        unpacked = unpack(pin, item.asset, cache_root)
        return f"{pin.service} {pin.tag} {item.label}: verified {path}, unpacked {unpacked}"
    return f"{pin.service} {pin.tag} {item.label}: verified {path}"


# --------------------------------------------------------------------------- #
# Unpacking the extras archives
# --------------------------------------------------------------------------- #


def _is_archive(asset: ServiceAsset) -> bool:
    return asset.name.endswith(_ARCHIVE_SUFFIX)


def extraction_dir(pin: ServicePin, asset: ServiceAsset, cache_root: Path) -> Path:
    """Where the verified archive *asset* is unpacked: ``<tag dir>/<its pinned sha256>/``, so a pin bump never reads a stale tree."""
    return cached_path(pin, asset, cache_root).parent / asset.sha256


def _unsafe_member(member: tarfile.TarInfo) -> str | None:
    """Why *member* may not be unpacked, or ``None`` for a plain file or directory inside the extraction root."""
    if not (member.isreg() or member.isdir()):
        return f"{member.name!r} is not a regular file or directory"
    parts = PurePosixPath(member.name.replace("\\", "/"))
    if parts.is_absolute() or ".." in parts.parts:
        return f"{member.name!r} leaves the extraction root"
    return None


def _unpack_into(archive_path: Path, scratch: Path, asset: ServiceAsset) -> None:
    """Unpack *archive_path* into *scratch*, refusing the whole archive when any member is unsafe."""
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            reason = _unsafe_member(member)
            if reason is not None:
                raise SyncServicesError(SERVICE_ASSET_ARCHIVE_UNSAFE, f"{asset.name}: {reason}; nothing was unpacked")
        _extract(archive, members, scratch)


def _has_data_filter() -> bool:
    """Whether ``tarfile`` has the ``data`` extraction filter (Python 3.11.4+)."""
    return hasattr(tarfile, "data_filter")


def _extract(archive: tarfile.TarFile, members: list[tarfile.TarInfo], scratch: Path) -> None:
    """Extract the already-checked *members*: through the ``data`` filter where it exists, else one by one without metadata."""
    if _has_data_filter():
        archive.extractall(scratch, members=members, filter="data")
        return
    for member in members:  # Python < 3.11.4: _unsafe_member above refused every shape the data filter would
        archive.extract(member, scratch, set_attrs=False)


def unpack(pin: ServicePin, asset: ServiceAsset, cache_root: Path) -> Path:
    """Unpack the cached, already verified archive *asset* once and return its extraction directory.

    It is unpacked into a scratch sibling and renamed into place, so no reader sees a
    half-written tree; an existing directory is reused (a concurrent unpack that won the
    rename is reused too).
    """
    target = extraction_dir(pin, asset, cache_root)
    if target.is_dir():
        return target
    scratch = target.with_name(f"{target.name}{_PARTIAL}{os.getpid()}")
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    try:
        _unpack_into(cached_path(pin, asset, cache_root), scratch, asset)
        try:
            os.replace(scratch, target)
        except OSError:
            if not target.is_dir():
                raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return target


def extras_root(repo_root: Path, service: str, extra: str, *, cache_root: Path | None = None) -> Path:
    """The extraction directory of *service*'s pinned *extra*, unpacking the verified cached archive if needed.

    Never downloads and never evicts: a missing or mismatched archive raises
    :class:`SyncServicesError` with ``SERVICE_BINARY_MISSING`` or ``SERVICE_BINARY_DIGEST_MISMATCH``
    and the remedy ``run `make sync-services```. An extra this pin does not carry is ``SERVICE_PIN_INVALID``.
    """
    pin = _load(Path(repo_root), service)
    asset = pin.extras.get(extra)
    if asset is None:
        raise SyncServicesError(SERVICE_PIN_INVALID, f"{service} {pin.tag} pins no {extra!r} extra (pinned: {sorted(pin.extras)})")
    cache = default_cache_root() if cache_root is None else Path(cache_root)
    _verified_cached(pin, asset, cache)
    return unpack(pin, asset, cache)


@dataclass(frozen=True)
class _Mode:
    offline: bool
    check: bool
    extras_only: bool


def _run_service(root: Path, service: str, cache_root: Path, *, mode: _Mode, report: Callable[[str], None]) -> bool:
    """Fetch (or check) every wanted asset of *service*; True when any of them failed."""
    try:
        pin = _load(root, service)
        items = wanted_assets(pin, host_target(), extras_only=mode.extras_only)
    except SyncServicesError as exc:
        report(str(exc))
        return True
    if not items:
        print(f"{pin.service} {pin.tag}: {NO_EXTRAS_PINNED}")
        return False
    failed = False
    for item in items:
        try:
            line = _check_one(pin, item, cache_root) if mode.check else _fetch_one(pin, item, cache_root, offline=mode.offline)
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
    parser.add_argument("--extras-only", action="store_true", help="only the extras (contract bundles, contract tools, conformance fixtures); no service build")
    parser.add_argument(
        "--extras-path",
        type=_extras_selector,
        metavar="SERVICE:EXTRA",
        help=f"print where an extra of a pin is unpacked (EXTRA is one of {', '.join(sorted(KNOWN_EXTRAS))}); never downloads",
    )
    return parser


def _extras_selector(value: str) -> tuple[str, str]:
    service, sep, extra = value.partition(":")
    if not sep or service not in KNOWN_SERVICES or extra not in KNOWN_EXTRAS:
        raise argparse.ArgumentTypeError(f"expected SERVICE:EXTRA with SERVICE in {sorted(KNOWN_SERVICES)} and EXTRA in {sorted(KNOWN_EXTRAS)}; got {value!r}")
    return service, extra


def _report(message: str) -> None:
    print(message, file=sys.stderr)


def main(argv: Sequence[str] | None = None, *, repo_root: Path | None = None, cache_root: Path | None = None) -> int:
    """Fetch and verify; *repo_root* defaults to this script's repository, *cache_root* to the shared cache."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    cache = default_cache_root() if cache_root is None else Path(cache_root)
    if args.extras_path is not None:
        return _print_extras_path(root, *args.extras_path, cache_root=cache)
    if args.service == _ALL:
        services = pinned_services(root)
        if not services:
            print(NO_SERVICE_PINNED)
            return 0
    else:
        services = [args.service]
    mode = _Mode(offline=args.offline, check=args.check, extras_only=args.extras_only)
    failed = False
    for service in services:
        failed |= _run_service(root, service, cache, mode=mode, report=_report)
    return 1 if failed else 0


def _print_extras_path(root: Path, service: str, extra: str, *, cache_root: Path) -> int:
    try:
        print(extras_root(root, service, extra, cache_root=cache_root))
    except SyncServicesError as exc:
        _report(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
