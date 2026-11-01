#!/usr/bin/env python3
"""Build and verify the ``spec-kitty-services`` companion wheels from the pinned service assets (#6904).

ADR 2026-10-29-1, Amendment 2026-10-31. For the release commit's ``pins/``:

- one **platform wheel** per native target that has at least one pinned companion
  service (the write service and the charter service; never the read service),
  holding exactly those pinned assets, each fetched and sha256-verified through
  ``kernel.service_artifacts.fetch_asset`` and never rebuilt;
- one binary-free **fallback wheel** (``py3-none-any``), always.

Every wheel's version is the ``[project].version`` of the repository's
``pyproject.toml`` (the CLI version). Wheels are written to a scratch directory
next to ``--out`` and moved there only when all of them pass the size gate
(fail above ``--max-mb``, default 95; warn above ``--warn-mb``, default 60).

A platform wheel's tag states the oldest OS it supports, so the build reads that minimum out of
every binary the wheel carries (``scripts.service_platform``: the highest ``GLIBC_x.y`` version
need for Linux, ``LC_BUILD_VERSION`` ``minos`` for macOS) and refuses
``SERVICE_PLATFORM_FLOOR_EXCEEDED`` when a binary needs more than the declared floor
(``--glibc-floor``, ``--macos-floor``), or ``SERVICE_PLATFORM_FLOOR_UNREADABLE`` when it cannot
read one. The declared floor stays the published tag: raising it is a release-contract change, so
it is never derived from the binaries inside a build (#6948).

``--verify DIR`` checks built wheels against the pins and changes nothing:
the manifest names this CLI version and the wheel's own target, every bundled
binary is a pinned asset of that target with the pinned sha256, nothing else is
bundled, and each whole wheel is byte-identical to the deterministic build of those
verified bytes (so no other file, provider, ``.pth``, metadata or tag can differ); the
fallback wheel exists and is binary-free. ``--verify`` re-measures the floor of the
bundled binaries too, so a wheel built with a floor below what they need cannot pass.

Exit 1 on any failure, with a stable ``SERVICE_*`` or ``COMPANION_*`` code on
stderr. It imports only ``kernel`` (run with ``PYTHONPATH=src``) and the
companion's own writer, loaded by path.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import re
import shutil
import sys
import tempfile
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

# Run directly (`python scripts/build_services_wheel.py`), neither the repo root nor `src` is on sys.path.
for _root in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[1] / "src"):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from kernel.service_artifacts import ServiceArtifactError, default_cache_root, fetch_asset  # noqa: E402 - after the sys.path setup above
from kernel.service_pin import PINS_DIR, SERVICE_PIN_INVALID, ServicePin, ServicePinError, ServiceTarget, load_service_pin, pin_file  # noqa: E402
from scripts.service_platform import GLIBC, MACOS, UnreadableBinary, exceeds, floor_kind, required_floor  # noqa: E402

COMPANION_PROJECT = Path("packages") / "spec-kitty-services"
COMPANION_SIZE_EXCEEDED = "COMPANION_SIZE_EXCEEDED"
COMPANION_VERIFY_FAILED = "COMPANION_VERIFY_FAILED"
COMPANION_OUT_NOT_EMPTY = "COMPANION_OUT_NOT_EMPTY"
COMPANION_BUILD_FAILED = "COMPANION_BUILD_FAILED"
SERVICE_PLATFORM_FLOOR_EXCEEDED = "SERVICE_PLATFORM_FLOOR_EXCEEDED"
SERVICE_PLATFORM_FLOOR_UNREADABLE = "SERVICE_PLATFORM_FLOOR_UNREADABLE"
_MB = 1024 * 1024
#: How a floor kind reads in a message, and the build input that declares it.
_KIND_LABEL = {GLIBC: ("glibc", "--glibc-floor"), MACOS: ("macOS", "--macos-floor")}
#: The floor component of a platform tag, in a wheel's own file name.
_TAG_FLOOR = re.compile(r"(?:manylinux|macosx)_(\d+_\d+)_")
_WRITER_MODULE = "spec_kitty_services_build_writer"


class BuildError(RuntimeError):
    """One refusal: a stable code and a message naming the asset, pin or wheel."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code} {message}")
        self.code = code


@dataclass(frozen=True)
class SizeGate:
    """Fail a wheel above ``max_bytes``; warn above ``warn_bytes``."""

    max_bytes: int
    warn_bytes: int


def load_writer(repo_root: Path) -> ModuleType:
    """The companion's own wheel writer (``spec_kitty_services/wheel.py``), loaded by path: one writer for the backend and this script."""
    path = repo_root / COMPANION_PROJECT / "spec_kitty_services" / "wheel.py"
    spec = importlib.util.spec_from_file_location(_WRITER_MODULE, path)
    if spec is None or spec.loader is None:
        raise BuildError(COMPANION_VERIFY_FAILED, f"cannot load the companion wheel writer from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_WRITER_MODULE] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def companion_pins(repo_root: Path, services: Sequence[str]) -> list[ServicePin]:
    """The pins of the companion *services* that exist under ``<repo_root>/pins``, sorted by service."""
    pins: list[ServicePin] = []
    for service in sorted(services):
        path = pin_file(repo_root / PINS_DIR, service)
        if not path.is_file():
            continue
        try:
            pins.append(load_service_pin(path))
        except ServicePinError as exc:
            raise BuildError(SERVICE_PIN_INVALID, f"{service}: {exc}") from exc
    return pins


def _fetch(pin: ServicePin, target: ServiceTarget, *, offline: bool, cache_root: Path) -> bytes:
    asset = pin.assets[target]
    try:
        return fetch_asset(pin, asset, offline=offline, cache_root=cache_root).read_bytes()
    except ServiceArtifactError as exc:
        raise BuildError(exc.code, f"{asset.name}: {str(exc).removeprefix(f'{exc.code}: ')}") from exc


def _check_size(path: Path, gate: SizeGate, warn: Callable[[str], None]) -> None:
    size = path.stat().st_size
    if size > gate.max_bytes:
        raise BuildError(COMPANION_SIZE_EXCEEDED, f"{path.name} is {size / _MB:.1f} MB, above the {gate.max_bytes / _MB:.0f} MB cap (PyPI allows 100 MB per file)")
    if size > gate.warn_bytes:
        warn(f"warning: {path.name} is {size / _MB:.1f} MB, above {gate.warn_bytes / _MB:.0f} MB")


def _declared_floors(writer: ModuleType, glibc_floor: str | None, macos_floor: str | None) -> dict[str, str]:
    """The floors the wheel tags claim, both validated up front whether or not that platform is pinned."""
    declared = {
        GLIBC: writer.DEFAULT_GLIBC_FLOOR if glibc_floor is None else glibc_floor,
        MACOS: writer.DEFAULT_MACOS_FLOOR if macos_floor is None else macos_floor,
    }
    try:
        writer.platform_tag("linux-x64", declared[GLIBC], declared[MACOS])
    except ValueError as exc:
        raise BuildError(COMPANION_BUILD_FAILED, str(exc)) from exc
    return declared


def _floor_violation(target: str, binaries: dict[str, bytes], declared: dict[str, str]) -> tuple[str, str] | None:
    """``(code, message)`` when *target*'s binaries need an OS newer than its wheel tag claims, else ``None``.

    The tag is the release contract, so a binary that needs more is a refusal, never a quietly raised
    tag: raising the floor changes which hosts can install the companion, and that is a reviewed
    change to ``--glibc-floor`` / ``--macos-floor`` in ``release.yml`` (#6948).
    """
    kind = floor_kind(target)
    if kind is None:
        return None
    label, option = _KIND_LABEL[kind]
    try:
        need = required_floor(target, binaries)
    except UnreadableBinary as exc:
        return SERVICE_PLATFORM_FLOOR_UNREADABLE, f"{target}: cannot read the {label} floor the tag would claim: {exc}"
    if need is None or not exceeds(need.floor, declared[kind]):
        return None
    return SERVICE_PLATFORM_FLOOR_EXCEEDED, (
        f"{target}: {need.asset} needs {label} {need.floor}, above the {declared[kind]} its wheel tag claims; "
        f"raise {option} to {need.floor} in release.yml (and the published tag with it), or pin a build that does not need it"
    )


def _tag_floor(wheel_name: str) -> str | None:
    """The floor a wheel file name claims (``…-manylinux_2_28_x86_64.whl`` -> ``2_28``), or ``None``."""
    match = _TAG_FLOOR.search(wheel_name)
    return None if match is None else match.group(1)


def build(
    repo_root: Path,
    out: Path,
    *,
    cache_root: Path,
    offline: bool = False,
    glibc_floor: str | None = None,
    macos_floor: str | None = None,
    gate: SizeGate,
    warn: Callable[[str], None],
) -> list[Path]:
    """Build every companion wheel into *out* (created; must not already hold wheels) and return their paths."""
    writer = load_writer(repo_root)
    project = repo_root / COMPANION_PROJECT
    version = writer.project_version(repo_root)
    declared = _declared_floors(writer, glibc_floor, macos_floor)
    pins = companion_pins(repo_root, writer.COMPANION_SERVICES)
    if out.is_dir() and any(out.glob("*.whl")):
        raise BuildError(COMPANION_OUT_NOT_EMPTY, f"{out} already holds wheels; build into an empty directory so no stale wheel ships")
    out.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=".companion-", dir=out.parent))
    try:
        built = [writer.build_companion_wheel(scratch, project_root=project, version=version, target=None, binaries={})]
        for target_value in writer.NATIVE_TARGETS:
            target = ServiceTarget(target_value)
            binaries = {
                writer.BundledBinary(service=pin.service, tag=pin.tag, asset=pin.assets[target].name, sha256=pin.assets[target].sha256): _fetch(
                    pin, target, offline=offline, cache_root=cache_root
                )
                for pin in pins
                if target in pin.assets
            }
            if binaries:
                violation = _floor_violation(target_value, {binary.asset: data for binary, data in binaries.items()}, declared)
                if violation is not None:
                    raise BuildError(*violation)
                built.append(
                    writer.build_companion_wheel(
                        scratch,
                        project_root=project,
                        version=version,
                        target=target_value,
                        binaries=binaries,
                        glibc_floor=declared[GLIBC],
                        macos_floor=declared[MACOS],
                    )
                )
        for path in built:
            _check_size(path, gate, warn)
        out.mkdir(parents=True, exist_ok=True)
        return [Path(shutil.move(str(path), out / path.name)) for path in built]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _expected_binaries(pins: Sequence[ServicePin], target: str | None) -> dict[str, tuple[str, str, str]]:
    """asset name -> (service, tag, sha256) that a wheel of *target* must carry, from the pins."""
    if target is None:
        return {}
    return {
        pin.assets[ServiceTarget(target)].name: (pin.service, pin.tag, pin.assets[ServiceTarget(target)].sha256)
        for pin in pins
        if ServiceTarget(target) in pin.assets
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 - release-asset integrity digest, the pin's own format


def _read_companion(writer: ModuleType, wheel: Path) -> tuple[Any, dict[str, bytes]]:
    """``(manifest, bundled binaries by asset name)`` of *wheel*; any unreadable shape raises ``BuildError``."""
    package = writer.IMPORT_NAME
    prefix = f"{package}/{writer.BIN_DIR}/"
    try:
        with zipfile.ZipFile(wheel) as archive:
            manifest = writer.parse_manifest(archive.read(f"{package}/{writer.MANIFEST_NAME}"))
            bundled = {member.removeprefix(prefix): archive.read(member) for member in archive.namelist() if member.startswith(prefix)}
    except (OSError, KeyError, zipfile.BadZipFile, writer.ManifestError) as exc:
        raise BuildError(COMPANION_VERIFY_FAILED, f"{wheel.name}: not a readable companion wheel ({type(exc).__name__}: {exc})") from exc
    return manifest, bundled


def _wheel_problems(
    writer: ModuleType, wheel: Path, *, project: Path, version: str, pins: Sequence[ServicePin], declared: dict[str, str]
) -> tuple[str | None, list[str]]:
    """``(target, problems)`` of one wheel (target ``None`` = the fallback).

    The bundled binaries must be exactly the pinned assets of the manifest's target, and then
    the whole wheel must be byte-identical to the deterministic build of those verified bytes:
    no other file, provider, ``.pth``, metadata or tag can differ (the RECORD inside a wheel is
    written by whoever wrote the wheel, so it proves nothing). The bundled bytes are also
    re-measured against their own tag, so a wheel built with too low a declared floor is caught.
    """
    try:
        manifest, bundled = _read_companion(writer, wheel)
    except BuildError as exc:
        return None, [str(exc).removeprefix(f"{exc.code} ")]
    name = wheel.name
    problems: list[str] = []
    if manifest.cli_version != version:
        problems.append(f"{name}: built for CLI {manifest.cli_version}, not {version}")
    expected = _expected_binaries(pins, manifest.target)
    if set(bundled) != set(expected):
        problems.append(f"{name}: bundles {sorted(bundled)}, the pins require {sorted(expected)}")
    binaries = {}
    for asset, (service, tag, sha256) in expected.items():
        data = bundled.get(asset)
        if data is None:
            continue
        if not hmac.compare_digest(_sha256(data), sha256):
            problems.append(f"{name}: {asset} does not match its pinned sha256")
            continue
        binaries[writer.BundledBinary(service=service, tag=tag, asset=asset, sha256=sha256)] = data
    if problems:
        return manifest.target, problems
    if manifest.target is not None:
        claimed = dict(declared)
        tag_floor = _tag_floor(name)
        kind = floor_kind(manifest.target)
        if kind is not None and tag_floor is not None:
            claimed[kind] = tag_floor  # what this wheel already claims, whatever it was built with
        violation = _floor_violation(manifest.target, {binary.asset: data for binary, data in binaries.items()}, claimed)
        if violation is not None:
            return manifest.target, [f"{name}: {violation[1]}"]
    with tempfile.TemporaryDirectory() as scratch:
        rebuilt = writer.build_companion_wheel(
            Path(scratch),
            project_root=project,
            version=version,
            target=manifest.target,
            binaries=binaries,
            glibc_floor=declared[GLIBC],
            macos_floor=declared[MACOS],
        )
        if rebuilt.name != name or rebuilt.read_bytes() != wheel.read_bytes():
            problems.append(f"{name}: differs from the deterministic build of its pinned assets ({rebuilt.name}); something else was added or changed")
    return manifest.target, problems


def verify(repo_root: Path, wheel_dir: Path, *, glibc_floor: str | None = None, macos_floor: str | None = None) -> list[str]:
    """Every problem of the companion wheels in *wheel_dir* against the pins; empty when they hold exactly the pinned digests."""
    writer = load_writer(repo_root)
    version = writer.project_version(repo_root)
    declared = _declared_floors(writer, glibc_floor, macos_floor)
    pins = companion_pins(repo_root, writer.COMPANION_SERVICES)
    project = repo_root / COMPANION_PROJECT
    wheels = sorted(wheel_dir.glob("*.whl"))
    problems: list[str] = []
    others = sorted(path.name for path in wheel_dir.iterdir() if path.suffix != ".whl") if wheel_dir.is_dir() else []
    if others:
        problems.append(f"{wheel_dir}: holds files that are not companion wheels and would be published unverified: {others}")
    targets: list[str | None] = []
    for wheel in wheels:
        target, found = _wheel_problems(writer, wheel, project=project, version=version, pins=pins, declared=declared)
        targets.append(target)
        problems.extend(found)
    if targets.count(None) != 1:
        problems.append(f"{wheel_dir}: expected exactly one fallback wheel, found {targets.count(None)}")
    wanted = {target for target in writer.NATIVE_TARGETS if _expected_binaries(pins, target)}
    present = {target for target in targets if target is not None}
    if present != wanted or len(present) != len(targets) - targets.count(None):
        problems.append(f"{wheel_dir}: platform wheels for {sorted(present)}, pins require exactly {sorted(wanted)}")
    return problems


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_services_wheel", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--out", type=Path, help="build the companion wheels into this directory")
    action.add_argument("--verify", type=Path, metavar="DIR", help="verify the companion wheels in DIR against the pins; change nothing")
    parser.add_argument(
        "--glibc-floor",
        default=None,
        help="Linux manylinux floor as <major>_<minor> (default: the companion's default, 2_39); the build refuses a binary that needs a newer one",
    )
    parser.add_argument(
        "--macos-floor",
        default=None,
        help="macOS floor as <major>_<minor> (default: the companion's default, 11_0); the build refuses a binary that needs a newer one",
    )
    parser.add_argument("--offline", action="store_true", help="use only the cache and SPEC_KITTY_SERVICE_ASSET_DIR; never download")
    parser.add_argument("--max-mb", type=float, default=95.0, help="fail a wheel above this size (default 95)")
    parser.add_argument("--warn-mb", type=float, default=60.0, help="warn about a wheel above this size (default 60)")
    return parser


def _report(message: str) -> None:
    print(message, file=sys.stderr)


def main(argv: Sequence[str] | None = None, *, repo_root: Path | None = None, cache_root: Path | None = None) -> int:
    """Build or verify; *repo_root* defaults to this script's repository, *cache_root* to the shared cache."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    try:
        if args.verify is not None:
            problems = verify(root, args.verify, glibc_floor=args.glibc_floor, macos_floor=args.macos_floor)
            for problem in problems:
                _report(f"{COMPANION_VERIFY_FAILED} {problem}")
            if not problems:
                print(f"verified {len(list(args.verify.glob('*.whl')))} companion wheel(s) in {args.verify}")
            return 1 if problems else 0
        gate = SizeGate(max_bytes=int(args.max_mb * _MB), warn_bytes=int(args.warn_mb * _MB))
        cache = default_cache_root() if cache_root is None else Path(cache_root)
        for path in build(
            root, args.out, cache_root=cache, offline=args.offline, glibc_floor=args.glibc_floor, macos_floor=args.macos_floor, gate=gate, warn=_report
        ):
            print(f"built {path}")
    except BuildError as exc:
        _report(str(exc))
        return 1
    except ValueError as exc:  # the writer's own refusals (a malformed manifest, version or pin asset name)
        _report(f"{COMPANION_BUILD_FAILED} {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
