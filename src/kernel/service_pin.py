"""Service pin lockfile model (``pins/<service>.source.yaml``, #6590).

A pin records **which released build of a service core runs**: the
spec-kitty-events ``service-v*`` tag, the commit it resolves to, the protocol
versions the build speaks, the core range it needs and, per target, the release
asset's file name and SHA-256 digest (ADR 2026-10-29-1, D-3). The schema is
``kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md``.

Everything is validated once, at load or construction time, into frozen value
objects, so later code (cache, launcher, vendor) never re-validates. Every
refusal is a :class:`ServicePinError` carrying ``SERVICE_PIN_INVALID`` and a
message that names the offending field. Messages never echo a digest and never
echo any value longer than a short preview. A placeholder pin (tag
``service-v0.0.0`` or an all-zero commit) refuses (C-003).

This module mirrors ``charter.offering.packs.pack_pin`` without importing it:
``kernel`` is the root layer and imports neither ``charter`` nor
``specify_cli``. YAML is read with ``ruamel.yaml`` (already used across the
kernel) and written through :func:`kernel.yaml_io.serialize_mapping` and
:func:`kernel.atomic.atomic_write`.
"""

from __future__ import annotations

import enum
import re
import types
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.atomic import atomic_write
from kernel.yaml_io import serialize_mapping

__all__ = [
    "DEFAULT_ASSET_PREFIXES",
    "KNOWN_SERVICES",
    "PINS_DIR",
    "PIN_SUFFIX",
    "SERVICE_PIN_INVALID",
    "ServiceAsset",
    "ServicePin",
    "ServicePinError",
    "ServiceTarget",
    "check_repository",
    "load_service_pin",
    "pin_file",
    "tag_version",
    "write_service_pin",
]

SERVICE_PIN_INVALID = "SERVICE_PIN_INVALID"
PINS_DIR = "pins"
PIN_SUFFIX = ".source.yaml"
KNOWN_SERVICES: frozenset[str] = frozenset({"write-service", "read-service", "charter-service"})
KNOWN_EXTRAS: frozenset[str] = frozenset({"contracts", "contract_tools", "fixtures"})
#: The deployable asset prefix of each service's builds in a ``service-v*`` release
#: (``<prefix>-<ver><target suffix>``); ``spec-kitty service vendor --asset-prefix`` overrides it.
DEFAULT_ASSET_PREFIXES: Mapping[str, str] = types.MappingProxyType(
    {
        # Agreed with spec-kitty-events (its ADR 0003): the mission-status read service.
        "read-service": "mission-status-api",
        # Agreed with spec-kitty-events (its ADR 0003): command-cli's binary is the write service.
        "write-service": "command-cli",
        # Provisional: until spec-kitty-charter (where the charter service's releases live) names its release asset.
        "charter-service": "spec-kitty-charter-service",
    }
)

#: Top-level keys in schema order; the writer emits them in this order.
_KEY_ORDER: tuple[str, ...] = (
    "service",
    "repository",
    "tag",
    "commit",
    "protocol_versions",
    "requires_core",
    "assets",
    "extras",
)
_OPTIONAL_KEYS: frozenset[str] = frozenset({"extras"})
_ASSET_KEYS: frozenset[str] = frozenset({"name", "sha256"})

_ALLOWED_REPOSITORY_SCHEMES = ("https", "file")
#: The agreed release tag rule, the only one (``tag_version``): an optional
#: ``-<pre-release>`` suffix, no ``+build`` metadata.
_TAG_RE = re.compile(r"service-v([0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?)")
_PLACEHOLDER_TAG = "service-v0.0.0"
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_PLACEHOLDER_COMMIT = "0" * 40
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_PREVIEW_LIMIT = 40
#: The userinfo part of a URL (``scheme://user:secret@``), which may carry a token.
_URL_USERINFO_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/]*@")

_HEADER = (
    "# Pin lockfile: which released build of this service core runs.\n"
    "# Bump only with `spec-kitty service vendor --service <name> --tag <tag>`; never edit by hand.\n"
)


class ServicePinError(ValueError):
    """A service pin lockfile is missing, malformed, or a placeholder."""

    error_code = SERVICE_PIN_INVALID


class ServiceTarget(enum.StrEnum):
    """A release target: a native host build, or the portable jar."""

    LINUX_X64 = "linux-x64"
    LINUX_ARM64 = "linux-arm64"
    MACOS_ARM64 = "macos-arm64"
    WINDOWS_X64 = "windows-x64"
    JVM = "jvm"

    @property
    def asset_suffix(self) -> str:
        """What follows ``<prefix>-<ver>`` in this target's release asset name: ``-<target>`` (``.exe`` on Windows) or ``.jar``."""
        if self is ServiceTarget.JVM:
            return ".jar"
        return f"-{self.value}.exe" if self is ServiceTarget.WINDOWS_X64 else f"-{self.value}"


def _preview(value: object) -> str:
    """A short ``repr`` of *value* for a message (never the whole of a long value)."""
    text = repr(value)
    if len(text) <= _PREVIEW_LIMIT:
        return text
    return f"{text[: _PREVIEW_LIMIT - 3]}..."


def _redact_userinfo(url: str) -> str:
    """*url* with any ``user:secret@`` part replaced by ``***@``, so a message never shows a credential."""
    return _URL_USERINFO_RE.sub(r"\1***@", url)


def _check_asset_name(name: str) -> None:
    if not name or name in {".", ".."}:
        raise ServicePinError(f"name: must be a non-empty plain file name; got {_preview(name)}")
    if any(token in name for token in ("/", "\\", "\x00", "..")):
        raise ServicePinError(f"name: must be a plain file name without '/', '\\', NUL or '..'; got {_preview(name)}")


@dataclass(frozen=True)
class ServiceAsset:
    """One release asset: its verbatim file name and its SHA-256 digest."""

    name: str
    sha256: str

    def __post_init__(self) -> None:
        _check_asset_name(self.name)
        if not _SHA256_RE.fullmatch(self.sha256):
            # Never echo the value: it is digest-shaped and may be long.
            raise ServicePinError("sha256: must be 64 lowercase hex characters")


def _check_service(service: str) -> None:
    if service not in KNOWN_SERVICES:
        raise ServicePinError(f"service: must be one of {sorted(KNOWN_SERVICES)}; got {_preview(service)}")


def check_repository(repository: str) -> None:
    """Refuse a release repository other than an ``https://`` or ``file://`` URL without credentials.

    The one repository rule (the pin model and ``spec-kitty service vendor`` both use it).
    A message never shows the credentials: any ``user:secret@`` part is redacted.
    """
    parts = urllib.parse.urlsplit(repository)
    if parts.scheme not in _ALLOWED_REPOSITORY_SCHEMES or not repository.startswith(f"{parts.scheme}://"):  # urlsplit lowercases; the download owner does not
        raise ServicePinError(f"repository: must be an https:// or file:// URL; got {_preview(_redact_userinfo(repository))}")
    if "@" in parts.netloc:
        raise ServicePinError(
            "repository: the URL carries credentials (user:password@ or token@); the release must be public,"
            f" pass the URL without them; got {_preview(_redact_userinfo(repository))}"
        )


def tag_version(tag: str) -> str | None:
    """The release version of *tag* (``service-v0.1.0-rc.1`` gives ``0.1.0-rc.1``), or ``None`` when it is no release tag."""
    match = _TAG_RE.fullmatch(tag)
    return None if match is None else match.group(1)


def _check_tag(tag: str) -> None:
    if tag_version(tag) is None:
        raise ServicePinError(f"tag: must look like service-v<major>.<minor>.<patch>[-<pre-release>]; got {_preview(tag)}")
    if tag == _PLACEHOLDER_TAG:
        raise ServicePinError(f"tag: {_PLACEHOLDER_TAG} is a placeholder, not a released build")


def _check_commit(commit: str) -> None:
    if not _COMMIT_RE.fullmatch(commit):
        raise ServicePinError(f"commit: must be 40 lowercase hex characters; got {_preview(commit)}")
    if commit == _PLACEHOLDER_COMMIT:
        raise ServicePinError("commit: an all-zero commit is a placeholder, not a released build")


def _check_protocol_versions(versions: tuple[int, ...]) -> None:
    if not versions:
        raise ServicePinError("protocol_versions: must list at least one version")
    for version in versions:
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ServicePinError(f"protocol_versions: every version must be a positive integer; got {_preview(version)}")


def _check_unique_names(assets: Mapping[ServiceTarget, ServiceAsset], extras: Mapping[str, ServiceAsset]) -> None:
    seen: set[str] = set()
    for asset in (*assets.values(), *extras.values()):
        if asset.name in seen:
            raise ServicePinError(f"assets: duplicate asset name {_preview(asset.name)}")
        seen.add(asset.name)


@dataclass(frozen=True)
class ServicePin:
    """The pin of one service: which released build core runs, and its digests."""

    service: str
    repository: str
    tag: str
    commit: str
    protocol_versions: tuple[int, ...]
    requires_core: str
    assets: Mapping[ServiceTarget, ServiceAsset]
    extras: Mapping[str, ServiceAsset] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_service(self.service)
        check_repository(self.repository)
        _check_tag(self.tag)
        _check_commit(self.commit)
        object.__setattr__(self, "protocol_versions", tuple(self.protocol_versions))
        _check_protocol_versions(self.protocol_versions)
        if not self.requires_core.strip():
            # A PEP 440 specifier; kernel has no `packaging` dependency, so the
            # vendor command (WP05) checks its meaning.
            raise ServicePinError("requires_core: must be a non-empty version specifier")
        if not self.assets:
            raise ServicePinError("assets: must list at least one target")
        unknown_extras = set(self.extras) - KNOWN_EXTRAS
        if unknown_extras:
            raise ServicePinError(f"extras: unknown key(s) {sorted(unknown_extras)}; allowed {sorted(KNOWN_EXTRAS)}")
        _check_unique_names(self.assets, self.extras)
        object.__setattr__(self, "assets", types.MappingProxyType(dict(self.assets)))
        object.__setattr__(self, "extras", types.MappingProxyType(dict(self.extras)))

    def asset_for(self, target: ServiceTarget) -> ServiceAsset | None:
        """The asset pinned for *target*, or ``None`` when this pin has no build for it."""
        return self.assets.get(target)


def pin_file(pins_dir: Path, service: str) -> Path:
    """The lockfile path of *service* in the pin directory *pins_dir*."""
    return Path(pins_dir) / f"{service}{PIN_SUFFIX}"


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _service_from_path(path: Path) -> str:
    name = path.name
    return name[: -len(PIN_SUFFIX)] if name.endswith(PIN_SUFFIX) else path.stem


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ServicePinError(f"service {_preview(_service_from_path(path))} is not pinned in this core version (no {path.name})")
    try:
        raw = YAML(typ="safe").load(path.read_bytes())
    except (OSError, YAMLError) as exc:
        raise ServicePinError(f"cannot read pin lockfile {path.name}: {type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise ServicePinError(f"{path.name}: expected a mapping at the top level")
    return raw


def _require_str(data: Mapping[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ServicePinError(f"{where}{key}: missing or not a string")
    return value


def _require_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ServicePinError(f"{key}: must be a mapping")
    return value


def _asset_from(raw: object, where: str) -> ServiceAsset:
    if not isinstance(raw, dict):
        raise ServicePinError(f"{where}: must be a mapping with 'name' and 'sha256'")
    unknown = set(raw) - _ASSET_KEYS
    if unknown:
        raise ServicePinError(f"{where}: unknown field(s) {sorted(map(str, unknown))}")
    name = _require_str(raw, "name", f"{where}.")
    sha256 = _require_str(raw, "sha256", f"{where}.")
    try:
        return ServiceAsset(name=name, sha256=sha256)
    except ServicePinError as exc:
        raise ServicePinError(f"{where}.{exc}") from exc


def _assets_from(raw: Mapping[str, Any]) -> dict[ServiceTarget, ServiceAsset]:
    assets: dict[ServiceTarget, ServiceAsset] = {}
    for key, value in raw.items():
        try:
            target = ServiceTarget(key)
        except ValueError:
            raise ServicePinError(f"assets: unknown target {_preview(key)}; allowed {[t.value for t in ServiceTarget]}") from None
        assets[target] = _asset_from(value, f"assets.{target.value}")
    return assets


def _extras_from(raw: Mapping[str, Any]) -> dict[str, ServiceAsset]:
    extras: dict[str, ServiceAsset] = {}
    for key, value in raw.items():
        if key not in KNOWN_EXTRAS:
            raise ServicePinError(f"extras: unknown key {_preview(key)}; allowed {sorted(KNOWN_EXTRAS)}")
        extras[key] = _asset_from(value, f"extras.{key}")
    return extras


def _protocol_versions_from(raw: Mapping[str, Any]) -> tuple[int, ...]:
    value = raw.get("protocol_versions")
    if not isinstance(value, list):
        raise ServicePinError("protocol_versions: must be a list of positive integers")
    return tuple(value)


def _check_keys(raw: Mapping[str, Any]) -> None:
    unknown = set(raw) - set(_KEY_ORDER)
    if unknown:
        raise ServicePinError(f"unknown top-level key(s) {sorted(map(str, unknown))}; allowed {list(_KEY_ORDER)}")
    missing = [key for key in _KEY_ORDER if key not in raw and key not in _OPTIONAL_KEYS]
    if missing:
        raise ServicePinError(f"missing top-level key(s) {missing}")


def load_service_pin(path: Path) -> ServicePin:
    """Load and validate the lockfile at *path* (fail closed).

    A missing file raises :class:`ServicePinError` saying the service is not
    pinned in this core version; callers turn that into their user-facing
    refusal.
    """
    path = Path(path)
    raw = _read_mapping(path)
    _check_keys(raw)
    service = _require_str(raw, "service", "")
    _check_service(service)
    if path.name != f"{service}{PIN_SUFFIX}":
        raise ServicePinError(f"service: {_preview(service)} does not match the file name {path.name}")
    extras_raw = raw.get("extras")
    return ServicePin(
        service=service,
        repository=_require_str(raw, "repository", ""),
        tag=_require_str(raw, "tag", ""),
        commit=_require_str(raw, "commit", ""),
        protocol_versions=_protocol_versions_from(raw),
        requires_core=_require_str(raw, "requires_core", ""),
        assets=_assets_from(_require_mapping(raw, "assets")),
        extras=_extras_from(_require_mapping(raw, "extras")) if extras_raw is not None else {},
    )


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def _asset_payload(asset: ServiceAsset) -> dict[str, str]:
    return {"name": asset.name, "sha256": asset.sha256}


def write_service_pin(pin: ServicePin, path: Path) -> None:
    """Write *pin* to *path* atomically: header comment, schema key order, sorted assets.

    Writing the same pin twice yields identical bytes. Empty ``extras`` are omitted.
    """
    payload: dict[str, Any] = {
        "service": pin.service,
        "repository": pin.repository,
        "tag": pin.tag,
        "commit": pin.commit,
        "protocol_versions": list(pin.protocol_versions),
        "requires_core": pin.requires_core,
        "assets": {target.value: _asset_payload(pin.assets[target]) for target in sorted(pin.assets, key=lambda t: t.value)},
    }
    if pin.extras:
        payload["extras"] = {key: _asset_payload(pin.extras[key]) for key in sorted(pin.extras)}
    atomic_write(Path(path), _HEADER.encode("utf-8") + serialize_mapping(payload))
