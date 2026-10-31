"""Bump a service pin lockfile from a release: the one path that rewrites ``pins/<service>.source.yaml`` (#6590, FR-013, US4).

:func:`vendor_pin` resolves the release tag to its commit, downloads the release's
``SHA256SUMS``, maps its entries onto pin fields by exact name (``<prefix>-<ver>-<target>``,
``<prefix>-<ver>.jar`` and the shared ``contract-bundles``/``contract-tools``/``conformance-fixtures``
archives, so another service's build in the same release is never taken), downloads every mapped asset and
checks it against its line, enforces ``requires_core`` and only then writes the
lockfile, through :func:`kernel.service_pin.write_service_pin`. Any refusal is a
:class:`VendorError` and leaves the lockfile byte-identical. Nothing else is written.

:func:`check_pin` verifies a lockfile: offline against the shape rules, online also
against the release's ``SHA256SUMS`` (and, for an ``https://`` repository, the tag's commit).

Ownership: git contact goes through :func:`kernel.git.remote.remote_tag_commit` and
every download through :func:`kernel.release_assets.download` (the architectural gates
``test_remote_contact_owner`` and ``test_release_asset_download_owner`` hold both).

Tag to commit: an ``https://`` repository is asked with ``git ls-remote`` against
``<repository>.git`` (an annotated tag is peeled to its commit); an explicit ``commit``
must then agree. A ``file://`` repository (fixtures, offline mirrors) has no git remote,
so ``commit`` is required there.

Follow-ups, out of scope here: verifying the release's SLSA build attestation, and
``protocol_versions`` from release metadata. No release carries those versions today,
so the caller passes them (default ``1``) and they must match the release notes.
TODO(#6590): read them from the release manifest spec-kitty-events plans to publish.
"""

from __future__ import annotations

import hmac
import re
import tempfile
import urllib.parse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from kernel.git.remote import RemoteUnreachable, remote_tag_commit
from kernel.release_assets import ReleaseAssetUnavailable, asset_url, download
from kernel.service_artifacts import sha256_file
from kernel.service_pin import (
    DEFAULT_ASSET_PREFIXES,
    KNOWN_SERVICES,
    SERVICE_PIN_INVALID,
    ServiceAsset,
    ServicePin,
    ServicePinError,
    ServiceTarget,
    check_repository,
    load_service_pin,
    pin_file,
    write_service_pin,
)
from kernel.service_pin import tag_version as _release_version

__all__ = ["VendorError", "check_pin", "vendor_pin"]

VENDOR_USAGE = "SERVICE_VENDOR_USAGE"
VENDOR_COMMIT_REQUIRED = "SERVICE_VENDOR_COMMIT_REQUIRED"
VENDOR_TAG_UNRESOLVED = "SERVICE_VENDOR_TAG_UNRESOLVED"
VENDOR_RELEASE_UNAVAILABLE = "SERVICE_VENDOR_RELEASE_UNAVAILABLE"
VENDOR_RELEASE_INVALID = "SERVICE_VENDOR_RELEASE_INVALID"
VENDOR_DIGEST_MISMATCH = "SERVICE_VENDOR_DIGEST_MISMATCH"
VENDOR_REQUIRES_CORE = "SERVICE_VENDOR_REQUIRES_CORE"

DEFAULT_REPOSITORY = "https://github.com/spec-kitty/spec-kitty-events"
SUMS_FILE = "SHA256SUMS"
_HTTPS = "https"
_FILE = "file"
_SCRATCH_PREFIX = "service-vendor-"
_SUMS_LINE_RE = re.compile(r"([0-9a-f]{64}) [ *](\S.*)")
_PREFIX_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
#: ``<stem>-<ver>.tar.gz`` names a shared extra of the release.
_EXTRA_STEMS: tuple[tuple[str, str], ...] = (
    ("contracts", "contract-bundles"),
    ("contract_tools", "contract-tools"),
    ("fixtures", "conformance-fixtures"),
)


class VendorError(RuntimeError):
    """A bump or check step refused; ``code`` is a stable ``SERVICE_VENDOR_*`` (or ``SERVICE_PIN_INVALID``) code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VendorResult:
    """The pin now in force, the ``SHA256SUMS`` entries that map to no pin field (ignored), and the native targets the release has no build for."""

    pin: ServicePin
    ignored: tuple[str, ...]
    absent_targets: tuple[ServiceTarget, ...] = ()


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def _check_service(service: str) -> None:
    if service not in KNOWN_SERVICES:
        raise VendorError(VENDOR_USAGE, f"--service must be one of {sorted(KNOWN_SERVICES)}; got {service!r}")


def _scheme(url: str) -> str:
    return urllib.parse.urlsplit(url).scheme.lower()


def _check_repository(repository: str) -> None:
    """The kernel's one repository rule (https or file, no credentials), as a usage error."""
    try:
        check_repository(repository)
    except ServicePinError as exc:
        raise VendorError(VENDOR_USAGE, str(exc)) from exc


def _git_url(repository: str) -> str:
    return repository.rstrip("/").removesuffix(".git") + ".git"


def resolve_commit(repository: str, tag: str, commit: str | None, *, scratch: Path) -> str:
    """The commit *tag* names in *repository*; an explicit *commit* is required for ``file://`` and must agree for ``https://``."""
    if _scheme(repository) == _FILE:
        if commit is None:
            raise VendorError(VENDOR_COMMIT_REQUIRED, "a file:// repository has no git remote to resolve the tag; pass --commit <40-hex sha>")
        return commit
    try:
        resolved = remote_tag_commit(scratch, _git_url(repository), tag)
    except RemoteUnreachable as exc:
        raise VendorError(VENDOR_TAG_UNRESOLVED, f"cannot ask {repository} for tag {tag}: {exc}") from exc
    if resolved is None:
        raise VendorError(VENDOR_TAG_UNRESOLVED, f"{repository} has no tag {tag}")
    if commit is not None and commit != resolved:
        raise VendorError(VENDOR_TAG_UNRESOLVED, f"--commit {commit} does not match tag {tag}, which names {resolved}")
    return resolved


def _current_pin(path: Path) -> ServicePin | None:
    """The lockfile now in force, or ``None`` when there is none or it is invalid (a bump repairs it)."""
    try:
        return load_service_pin(path)
    except ServicePinError:
        return None


def _default_requires_core(core_version: str) -> str:
    try:
        version = Version(core_version)
    except InvalidVersion as exc:
        raise VendorError(VENDOR_REQUIRES_CORE, f"this core's version {core_version!r} is not a PEP 440 version") from exc
    return f">={version.public},<{version.major + 1}"


def _specifier(requires_core: str) -> SpecifierSet:
    try:
        return SpecifierSet(requires_core)
    except InvalidSpecifier as exc:
        raise VendorError(VENDOR_REQUIRES_CORE, f"requires_core {requires_core!r} is not a valid version specifier") from exc


def _check_requires_core(requires_core: str, core_version: str) -> None:
    if not _specifier(requires_core).contains(core_version, prereleases=True):
        raise VendorError(VENDOR_REQUIRES_CORE, f"incompatible requires_core: the pin requires {requires_core!r} but core is {core_version}")


# --------------------------------------------------------------------------- #
# The release's SHA256SUMS
# --------------------------------------------------------------------------- #


def _fetch(repository: str, tag: str, name: str, dest: Path) -> None:
    try:
        download(asset_url(repository, tag, name), dest)
    except ReleaseAssetUnavailable as exc:
        raise VendorError(VENDOR_RELEASE_UNAVAILABLE, f"cannot download {name} of {tag}: {exc.reason}") from exc


def parse_sums(text: str) -> dict[str, str]:
    """``{name: sha256}`` from ``sha256sum`` output; a malformed or repeated line refuses."""
    sums: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = _SUMS_LINE_RE.fullmatch(line)
        if match is None:
            raise VendorError(VENDOR_RELEASE_INVALID, f"{SUMS_FILE} line {number} is not '<64 hex>  <name>'")
        digest, name = match.groups()
        if name in sums:
            raise VendorError(VENDOR_RELEASE_INVALID, f"{SUMS_FILE} lists {name} twice")
        sums[name] = digest
    return sums


def _read_sums(repository: str, tag: str, scratch: Path) -> dict[str, str]:
    dest = scratch / SUMS_FILE
    _fetch(repository, tag, SUMS_FILE, dest)
    try:
        text = dest.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VendorError(VENDOR_RELEASE_INVALID, f"{SUMS_FILE} of {tag} is unreadable ({type(exc).__name__})") from exc
    return parse_sums(text)


def tag_version(tag: str) -> str:
    """The release version of *tag* (the kernel's one tag rule); any other tag is a usage error."""
    version = _release_version(tag)
    if version is None:
        raise VendorError(VENDOR_USAGE, f"--tag must look like service-v<major>.<minor>.<patch>[-<pre-release>]; got {tag!r}")
    return version


def asset_prefix(service: str, override: str | None) -> str:
    """The deployable prefix of *service*'s builds: *override*, else :data:`DEFAULT_ASSET_PREFIXES`."""
    prefix = DEFAULT_ASSET_PREFIXES[service] if override is None else override
    if not _PREFIX_RE.fullmatch(prefix):
        raise VendorError(VENDOR_USAGE, f"--asset-prefix must be a plain file-name prefix; got {prefix!r}")
    return prefix


def expected_names(prefix: str, version: str) -> dict[str, ServiceTarget | str]:
    """Every release file name that fills a pin field, mapped to that field (a target or an extras key)."""
    names: dict[str, ServiceTarget | str] = {f"{prefix}-{version}{target.asset_suffix}": target for target in ServiceTarget}
    names.update({f"{stem}-{version}.tar.gz": key for key, stem in _EXTRA_STEMS})
    return names


def map_assets(service: str, names: Iterable[str], *, prefix: str, version: str) -> tuple[dict[ServiceTarget | str, str], tuple[str, ...]]:
    """Map release asset *names* onto pin fields by exact name; returns ``({field: name}, ignored names)``.

    Only ``<prefix>-<version>-<target>`` / ``<prefix>-<version>.jar`` are this service's builds, so
    a target the release has no build of for this service is omitted, never filled with another
    service's file. Anything else is ignored (and listed back).
    """
    expected = expected_names(prefix, version)
    mapped: dict[ServiceTarget | str, str] = {}
    ignored: list[str] = []
    for name in sorted(names):
        field = expected.get(name)
        if field is None:
            ignored.append(name)
        else:
            mapped[field] = name
    if not any(isinstance(field, ServiceTarget) for field in mapped):
        raise VendorError(VENDOR_RELEASE_INVALID, f"{SUMS_FILE} lists no build of {service} named {prefix}-{version}-<target> or {prefix}-{version}.jar")
    return mapped, tuple(ignored)


def _verified_asset(repository: str, tag: str, name: str, digest: str, scratch: Path) -> ServiceAsset:
    """Download *name* and check it against its ``SHA256SUMS`` digest; the digest is never echoed."""
    dest = scratch / "assets" / name
    dest.parent.mkdir(exist_ok=True)
    _fetch(repository, tag, name, dest)
    if not hmac.compare_digest(sha256_file(dest), digest):
        raise VendorError(VENDOR_DIGEST_MISMATCH, f"the downloaded {name} does not match its line in {SUMS_FILE} of {tag}")
    try:
        return ServiceAsset(name=name, sha256=digest)
    except ServicePinError as exc:
        raise VendorError(SERVICE_PIN_INVALID, f"{name}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Bump
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Release:
    commit: str
    assets: Mapping[ServiceTarget, ServiceAsset]
    extras: Mapping[str, ServiceAsset]
    ignored: tuple[str, ...]


@dataclass(frozen=True)
class _Request:
    service: str
    repository: str
    tag: str
    commit: str | None
    prefix: str
    version: str


def _download_release(request: _Request, scratch: Path) -> _Release:
    repository, tag = request.repository, request.tag
    resolved = resolve_commit(repository, tag, request.commit, scratch=scratch)
    sums = _read_sums(repository, tag, scratch)
    mapped, ignored = map_assets(request.service, sums, prefix=request.prefix, version=request.version)
    assets: dict[ServiceTarget, ServiceAsset] = {}
    extras: dict[str, ServiceAsset] = {}
    for field, name in mapped.items():
        asset = _verified_asset(repository, tag, name, sums[name], scratch)
        if isinstance(field, ServiceTarget):
            assets[field] = asset
        else:
            extras[field] = asset
    return _Release(commit=resolved, assets=assets, extras=extras, ignored=ignored)


def vendor_pin(
    *,
    pins_dir: Path,
    service: str,
    tag: str,
    repository: str | None = None,
    commit: str | None = None,
    protocol_versions: Sequence[int] = (1,),
    asset_prefix_override: str | None = None,
    core_version: str,
) -> VendorResult:
    """Rewrite ``<pins_dir>/<service>.source.yaml`` from release *tag*; fail closed, the lockfile is untouched on any refusal.

    *repository* defaults to the current pin's, else :data:`DEFAULT_REPOSITORY`. A new pin keeps
    the current ``requires_core`` (or ``>=<core>,<<major+1>``), and *core_version* must satisfy it.
    Builds are matched by exact name, ``<prefix>-<ver>-<target>`` and ``<prefix>-<ver>.jar``, where
    ``<ver>`` is *tag* without ``service-v`` and the prefix is *asset_prefix_override* or the
    service's entry in :data:`DEFAULT_ASSET_PREFIXES`.
    """
    _check_service(service)
    version = tag_version(tag)
    prefix = asset_prefix(service, asset_prefix_override)
    path = pin_file(pins_dir, service)
    current = _current_pin(path)
    repository = repository or (current.repository if current else DEFAULT_REPOSITORY)
    _check_repository(repository)
    requires_core = current.requires_core if current else _default_requires_core(core_version)
    _check_requires_core(requires_core, core_version)
    with tempfile.TemporaryDirectory(prefix=_SCRATCH_PREFIX) as scratch_name:
        request = _Request(service=service, repository=repository, tag=tag, commit=commit, prefix=prefix, version=version)
        release = _download_release(request, Path(scratch_name))
    try:
        pin = ServicePin(
            service=service,
            repository=repository,
            tag=tag,
            commit=release.commit,
            protocol_versions=tuple(protocol_versions),
            requires_core=requires_core,
            assets=release.assets,
            extras=release.extras,
        )
    except ServicePinError as exc:
        raise VendorError(SERVICE_PIN_INVALID, str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    write_service_pin(pin, path)
    absent = tuple(target for target in ServiceTarget if target is not ServiceTarget.JVM and target not in pin.assets)
    return VendorResult(pin=pin, ignored=release.ignored, absent_targets=absent)


# --------------------------------------------------------------------------- #
# Check
# --------------------------------------------------------------------------- #


def _recorded(pin: ServicePin) -> list[ServiceAsset]:
    return [*pin.assets.values(), *pin.extras.values()]


def _sums_problems(pin: ServicePin, sums: Mapping[str, str]) -> list[str]:
    problems: list[str] = []
    for asset in _recorded(pin):
        listed = sums.get(asset.name)
        if listed is None:
            problems.append(f"{asset.name} is not listed in {SUMS_FILE} of {pin.tag}")
        elif not hmac.compare_digest(listed, asset.sha256):
            problems.append(f"the recorded sha256 of {asset.name} disagrees with {SUMS_FILE} of {pin.tag}")
    return problems


def _online_problems(pin: ServicePin) -> list[str]:
    with tempfile.TemporaryDirectory(prefix=_SCRATCH_PREFIX) as scratch_name:
        scratch = Path(scratch_name)
        try:
            problems: list[str] = []
            if _scheme(pin.repository) == _HTTPS:
                try:
                    resolve_commit(pin.repository, pin.tag, pin.commit, scratch=scratch)
                except VendorError as exc:
                    problems.append(f"commit: {exc}")
            return problems + _sums_problems(pin, _read_sums(pin.repository, pin.tag, scratch))
        except VendorError as exc:
            return [str(exc)]


def check_pin(*, pins_dir: Path, service: str, online: bool) -> list[str]:
    """Problems with the lockfile of *service* (empty when it is sound); nothing is written.

    Offline: the shape rules, and a parseable ``requires_core``. Online: also every recorded
    digest against the release's ``SHA256SUMS``, and an ``https://`` tag's commit.
    """
    _check_service(service)
    try:
        pin = load_service_pin(pin_file(pins_dir, service))
    except ServicePinError as exc:
        return [str(exc)]
    try:
        _specifier(pin.requires_core)
    except VendorError as exc:
        return [str(exc)]
    return _online_problems(pin) if online else []
