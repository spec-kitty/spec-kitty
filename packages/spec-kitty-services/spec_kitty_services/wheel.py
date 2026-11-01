"""Deterministic standard-library wheel writer and manifest of ``spec-kitty-services`` (#6904).

One authority for the companion's wheel layout: the in-tree build backend
(``_backend/spec_kitty_services_backend.py``) builds the binary-free fallback and
editable wheels with it, and ``scripts/build_services_wheel.py`` builds the
platform wheels with it from the pinned, digest-verified service assets
(ADR 2026-10-29-1, Amendment 2026-10-31).

Every wheel holds the providers (``spec_kitty_services/__init__.py``), this module,
and ``spec_kitty_services/_manifest.json``; a platform wheel also holds
``spec_kitty_services/bin/<asset>`` for each pinned binary of its target. Output is
byte-identical for identical input: fixed timestamps, sorted members, fixed modes.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import re
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BIN_DIR",
    "COMPANION_SERVICES",
    "DEFAULT_GLIBC_FLOOR",
    "DEFAULT_MACOS_FLOOR",
    "DISTRIBUTION",
    "ENTRY_POINT_GROUP",
    "FALLBACK_TAG",
    "IMPORT_NAME",
    "MANIFEST_NAME",
    "NATIVE_TARGETS",
    "BundledBinary",
    "Manifest",
    "ManifestError",
    "build_companion_wheel",
    "build_editable_wheel",
    "build_sdist",
    "manifest_bytes",
    "parse_manifest",
    "platform_tag",
    "project_version",
    "wheel_name",
    "write_wheel",
]

DISTRIBUTION = "spec-kitty-services"
IMPORT_NAME = "spec_kitty_services"
MANIFEST_NAME = "_manifest.json"
BIN_DIR = "bin"
ENTRY_POINT_GROUP = "spec_kitty.service_binaries"
#: Service -> provider function in ``spec_kitty_services``. Never the read service (ADR 2026-10-29-1 D-6).
_PROVIDERS: Mapping[str, str] = {"charter-service": "charter_service", "write-service": "write_service"}
COMPANION_SERVICES: tuple[str, ...] = tuple(sorted(_PROVIDERS))
DEFAULT_GLIBC_FLOOR = "2_39"
DEFAULT_MACOS_FLOOR = "11_0"
FALLBACK_TAG = "py3-none-any"
_MANIFEST_SCHEMA = 1
_REQUIRES_PYTHON = ">=3.11"
_SUMMARY = "Optional companion of spec-kitty-cli: the pinned, digest-verified service binaries for one platform."
#: The zip epoch: the earliest timestamp a zip entry can carry, so builds are reproducible.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_FILE_MODE = 0o100644
_EXEC_MODE = 0o100755
_FLOOR = re.compile(r"^[0-9]+_[0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
#: A release asset name: a plain file name with no separator, drive or stream form (``C:x``), and no leading dot.
_ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RELEASE_TAG = re.compile(r"^service-v[0-9]")
#: ``kernel.service_pin.ServiceTarget`` value -> wheel platform tag (``{glibc}`` is the Linux floor).
_PLATFORMS: Mapping[str, str] = {
    "linux-x64": "manylinux_{glibc}_x86_64",
    "linux-arm64": "manylinux_{glibc}_aarch64",
    "macos-arm64": "macosx_{macos}_arm64",
    "windows-x64": "win_amd64",
}
NATIVE_TARGETS: tuple[str, ...] = tuple(_PLATFORMS)
#: The package's own source files, copied into every wheel and the sdist.
_SOURCE_FILES = ("__init__.py", "py.typed", "wheel.py")


class ManifestError(ValueError):
    """A ``_manifest.json`` that does not match the companion manifest schema."""


@dataclass(frozen=True)
class BundledBinary:
    """One pinned binary a platform wheel carries: the service, the release tag, the asset name and its sha256."""

    service: str
    tag: str
    asset: str
    sha256: str


@dataclass(frozen=True)
class Manifest:
    """The parsed ``_manifest.json``: the CLI version it was built for, its target (``None``: fallback) and binaries."""

    cli_version: str
    target: str | None
    binaries: tuple[BundledBinary, ...]

    def binary_for(self, service: str) -> BundledBinary | None:
        """The bundled binary of *service*, or ``None``."""
        return next((binary for binary in self.binaries if binary.service == service), None)


def platform_tag(target: str, glibc_floor: str = DEFAULT_GLIBC_FLOOR, macos_floor: str = DEFAULT_MACOS_FLOOR) -> str:
    """The wheel tag of a native *target* (``linux-x64`` -> ``py3-none-manylinux_2_39_x86_64``).

    *glibc_floor* and *macos_floor* are the OS minimums the tag claims, and both are validated whether or
    not *target* uses them: a floor that is not ``<major>_<minor>`` is refused before anything is built.
    The caller is responsible for those floors being true of the binaries in the wheel; the release
    build reads them out of each binary and refuses a wheel that would understate one (#6948).
    """
    for label, floor in (("glibc", glibc_floor), ("macOS", macos_floor)):
        if not _FLOOR.match(floor):
            raise ValueError(f"{label} floor {floor!r} is not <major>_<minor>")
    try:
        return "py3-none-" + _PLATFORMS[target].format(glibc=glibc_floor, macos=macos_floor)
    except KeyError:
        raise ValueError(f"{target!r} is not a native service target ({', '.join(NATIVE_TARGETS)})") from None


def wheel_name(version: str, tag: str) -> str:
    """The wheel file name of this distribution: ``spec_kitty_services-<version>-<tag>.whl``."""
    return f"{IMPORT_NAME}-{version}-{tag}.whl"


def manifest_bytes(cli_version: str, target: str | None, binaries: Iterable[BundledBinary]) -> bytes:
    """Canonical manifest JSON (sorted keys, binaries sorted by service, trailing newline)."""
    entries = [
        {"asset": binary.asset, "service": binary.service, "sha256": binary.sha256, "tag": binary.tag}
        for binary in sorted(binaries, key=lambda binary: binary.service)
    ]
    document = {"cli_version": cli_version, "schema": _MANIFEST_SCHEMA, "services": entries, "target": target}
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _require_str(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{key!r} must be a non-empty string")
    return value


def _parse_binary(raw: object) -> BundledBinary:
    if not isinstance(raw, dict) or set(raw) != {"asset", "service", "sha256", "tag"}:
        raise ManifestError("each services entry has exactly asset, service, sha256 and tag")
    binary = BundledBinary(service=_require_str(raw, "service"), tag=_require_str(raw, "tag"), asset=_require_str(raw, "asset"), sha256=_require_str(raw, "sha256"))
    if binary.service not in _PROVIDERS:
        raise ManifestError(f"service {binary.service!r} is not a companion service")
    if not _SHA256.match(binary.sha256):
        raise ManifestError(f"sha256 of {binary.asset!r} is not 64 lowercase hex characters")
    if not _ASSET_NAME.match(binary.asset):
        raise ManifestError(f"asset {binary.asset!r} is not a plain file name")
    if not _RELEASE_TAG.match(binary.tag):
        raise ManifestError(f"tag {binary.tag!r} is not a service-v* release tag")
    return binary


def parse_manifest(data: bytes) -> Manifest:
    """Parse and validate a manifest; any deviation from the schema is a :class:`ManifestError`."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"not JSON: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"cli_version", "schema", "services", "target"}:
        raise ManifestError("a manifest has exactly cli_version, schema, services and target")
    if document["schema"] != _MANIFEST_SCHEMA:
        raise ManifestError(f"unsupported manifest schema {document['schema']!r}")
    target = document["target"]
    if target is not None and target not in _PLATFORMS:
        raise ManifestError(f"target {target!r} is not a native service target")
    services = document["services"]
    if not isinstance(services, list):
        raise ManifestError("services must be a list")
    binaries = tuple(_parse_binary(raw) for raw in services)
    if len({binary.service for binary in binaries}) != len(binaries):
        raise ManifestError("a service is listed twice")
    if target is None and binaries:
        raise ManifestError("the fallback manifest (target null) carries no binary")
    return Manifest(cli_version=_require_str(document, "cli_version"), target=target, binaries=binaries)


def project_version(project_root: Path) -> str:
    """The ``[project].version`` of the ``pyproject.toml`` in *project_root*."""
    data = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{project_root / 'pyproject.toml'} has no [project].version")
    return version


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()  # noqa: TID251 - the wheel RECORD format (PEP 376/427), not a charter freshness hash
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _entry_points() -> bytes:
    lines = [f"[{ENTRY_POINT_GROUP}]", *(f"{service} = {IMPORT_NAME}:{function}" for service, function in sorted(_PROVIDERS.items()))]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _metadata(version: str, description: str = "") -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {DISTRIBUTION}",
        f"Version: {version}",
        f"Summary: {_SUMMARY}",
        "License: MIT",
        f"Requires-Python: {_REQUIRES_PYTHON}",
    ]
    if description:
        lines.append("Description-Content-Type: text/markdown")
        return ("\n".join(lines) + "\n\n" + description).encode("utf-8")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _wheel_file(tag: str) -> bytes:
    purelib = "true" if tag == FALLBACK_TAG else "false"
    lines = ["Wheel-Version: 1.0", f"Generator: {DISTRIBUTION} (stdlib wheel writer)", f"Root-Is-Purelib: {purelib}", f"Tag: {tag}"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _zip_entry(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3  # unix, whatever the build host, so the bytes match across hosts
    return info


def write_wheel(
    out_dir: Path,
    *,
    version: str,
    tag: str,
    members: Mapping[str, bytes],
    executables: frozenset[str] = frozenset(),
    description: str = "",
) -> Path:
    """Write ``spec_kitty_services-<version>-<tag>.whl`` holding *members* plus its ``dist-info``; return its path.

    *members* maps archive names to bytes; names in *executables* get mode 0755; *description* is the
    Markdown long description (the project README) shown on PyPI.
    """
    dist_info = f"{IMPORT_NAME}-{version}.dist-info"
    files = dict(members)
    files[f"{dist_info}/METADATA"] = _metadata(version, description)
    files[f"{dist_info}/WHEEL"] = _wheel_file(tag)
    files[f"{dist_info}/entry_points.txt"] = _entry_points()
    record_name = f"{dist_info}/RECORD"
    record = "".join(f"{name},{_record_hash(data)},{len(data)}\n" for name, data in sorted(files.items())) + f"{record_name},,\n"
    files[record_name] = record.encode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / wheel_name(version, tag)
    with zipfile.ZipFile(path, "w") as archive:
        package_first = sorted(files, key=lambda name: (name.startswith(dist_info), name))
        for name in [*(name for name in package_first if name != record_name), record_name]:
            archive.writestr(_zip_entry(name, _EXEC_MODE if name in executables else _FILE_MODE), files[name])
    return path


def _source_members(project_root: Path) -> dict[str, bytes]:
    package = project_root / IMPORT_NAME
    return {f"{IMPORT_NAME}/{name}": (package / name).read_bytes() for name in _SOURCE_FILES}


def build_companion_wheel(
    out_dir: Path,
    *,
    project_root: Path,
    version: str,
    target: str | None,
    binaries: Mapping[BundledBinary, bytes],
    glibc_floor: str = DEFAULT_GLIBC_FLOOR,
    macos_floor: str = DEFAULT_MACOS_FLOOR,
) -> Path:
    """A companion wheel: the platform wheel of *target* holding *binaries*, or the fallback wheel (``target=None``, no binary)."""
    if target is None and binaries:
        raise ValueError("the fallback wheel carries no binary")
    tag = FALLBACK_TAG if target is None else platform_tag(target, glibc_floor, macos_floor)
    members = _source_members(project_root)
    manifest = manifest_bytes(version, target, binaries)
    parse_manifest(manifest)  # refuse what no provider would accept (an asset name the allowlist rejects, a bad tag)
    members[f"{IMPORT_NAME}/{MANIFEST_NAME}"] = manifest
    executables: set[str] = set()
    for binary, data in binaries.items():
        name = f"{IMPORT_NAME}/{BIN_DIR}/{binary.asset}"
        members[name] = data
        executables.add(name)
    description = (project_root / "README.md").read_text(encoding="utf-8")
    return write_wheel(out_dir, version=version, tag=tag, members=members, executables=frozenset(executables), description=description)


def build_editable_wheel(out_dir: Path, *, project_root: Path, version: str) -> Path:
    """An editable wheel: a ``.pth`` that puts *project_root* on ``sys.path`` (no manifest, so providers offer nothing)."""
    root = str(project_root.resolve())
    if any(char in root for char in "\r\n"):
        raise ValueError(f"cannot write an editable .pth for a path with a line break: {root!r}")  # a .pth line could run code
    pth = (root + "\n").encode("utf-8")
    return write_wheel(out_dir, version=version, tag=FALLBACK_TAG, members={f"{IMPORT_NAME}_editable.pth": pth})


def build_sdist(out_dir: Path, *, project_root: Path, version: str, backend_files: Iterable[Path]) -> Path:
    """A reproducible ``spec_kitty_services-<version>.tar.gz`` of the project sources plus ``PKG-INFO``."""
    top = f"{IMPORT_NAME}-{version}"
    files: dict[str, bytes] = {"PKG-INFO": _metadata(version, (project_root / "README.md").read_text(encoding="utf-8"))}
    for name in ("pyproject.toml", "README.md"):
        files[name] = (project_root / name).read_bytes()
    files.update(_source_members(project_root))
    for path in backend_files:
        files[path.relative_to(project_root).as_posix()] = path.read_bytes()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(files):
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(files[name])
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(files[name]))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{top}.tar.gz"
    with path.open("wb") as handle, gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as gz:
        gz.write(raw.getvalue())
    return path
