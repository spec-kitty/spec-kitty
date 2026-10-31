"""Resolve the verified binary of a pinned service, or refuse (#6590, FR-004, FR-005, FR-011).

:func:`resolve_binary` returns the first verified candidate in this fixed order:

1. **explicit** -- ``SPEC_KITTY_<SERVICE>_BINARY`` (``SPEC_KITTY_WRITE_SERVICE_BINARY``),
   accepted only when its bytes are the pinned host build or the pinned jar;
2. **install** -- the ``spec_kitty.service_binaries`` entry-point slot of a future
   companion wheel (ADR 2026-10-29-1 D-4), digest-checked the same way;
3. **cache** -- the pinned native asset for this host, through
   ``kernel.service_artifacts.fetch_asset`` (cache, offline asset directory,
   download);
4. **jar** -- the pinned jar under a Java 25+ runtime, only when there is no
   native build for this host, or when the native build is unavailable and the
   jar is already in the cache or the asset directory (it is never downloaded
   after the native download failed: that refusal is raised instead; research R-6);
5. otherwise a :class:`~specify_cli.services.errors.ServiceRefusal`.

There is no Python fallback writer: resolution yields verified bytes or refuses.
:func:`verify_before_exec` re-hashes the chosen file immediately before spawn
(NFR-003, research R-3).

Developer opt-in (FR-011): ``SPEC_KITTY_SERVICE_UNPINNED=1`` -- exactly ``"1"`` --
is honoured only together with an explicit path whose bytes match no pinned
asset. The result is ``pinned=False`` with a warning the launcher prints on every
start. The CLI's own tests and CI never set it outside the tests of the opt-in
itself.

The pin is the CLI's own, read through :func:`find_pin` from :func:`pins_dir`: the
``pins/`` directory of the spec-kitty source checkout the running ``specify_cli``
package belongs to (an editable install; :func:`source_checkout_root`), else the
``specify_cli/_pins/`` package resource of an installed wheel
(:data:`INSTALLED_PINS_PACKAGE_DIR`; packaging force-includes ``pins/`` there).
It is never read from the user's project: a ``pins/`` there names nothing the CLI
runs.
"""

from __future__ import annotations

import hmac
import importlib.resources
import os
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Literal, Protocol

import specify_cli
from kernel.service_artifacts import (
    ASSET_DIR_ENV,
    SERVICE_BINARY_MISSING,
    ServiceArtifactError,
    cached_path,
    default_cache_root,
    fetch_asset,
    sha256_file,
    verify_asset,
)
from kernel.service_hosts import host_target, select_build
from kernel.service_pin import PIN_SUFFIX, PINS_DIR, ServiceAsset, ServicePin, ServicePinError, ServiceTarget, load_service_pin
from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode, remedy_for
from specify_cli.services.host import find_java
from specify_cli.status import SUPPORTED_PROTOCOL_VERSIONS

# The constants and ``binary_env_var`` stay public (tests, the launcher and packaging name them) but are
# not exported: only the resolution entry points are the package's cross-module surface.
__all__ = [
    "ResolvedBinary",
    "artifact_refusal",
    "find_pin",
    "load_pin",
    "no_build_refusal",
    "pins_dir",
    "resolve_binary",
    "source_checkout_root",
    "verify_before_exec",
]

#: The package-resource directory of ``specify_cli`` that holds the pins in an installed wheel.
INSTALLED_PINS_PACKAGE_DIR = "_pins"
#: The distribution a source checkout's ``pyproject.toml`` must name for its ``pins/`` to be the CLI's own.
_DISTRIBUTION = "spec-kitty-cli"
_PYPROJECT = "pyproject.toml"
_SRC_DIR = "src"
#: The developer opt-in; honoured only as exactly ``"1"`` and only with an explicit path.
UNPINNED_ENV = "SPEC_KITTY_SERVICE_UNPINNED"
#: Entry-point group of the install-provided slot: name = service, value = a callable returning a path.
BINARY_PROVIDER_GROUP = "spec_kitty.service_binaries"
_WRITE_SERVICE = "write-service"
_JAR_FLAG = "-jar"
#: Never created: stands for "no asset directory" so ``fetch_asset`` does not read the process env.
_NO_ASSET_DIR = ".no-asset-dir"

Source = Literal["explicit", "install", "cache", "jar", "unpinned"]


@dataclass(frozen=True)
class ResolvedBinary:
    """A service binary ready to spawn: ``argv_prefix`` is ``(path,)`` or ``(java, "-jar", path)``."""

    argv_prefix: tuple[str, ...]
    path: Path
    source: Source
    sha256: str
    pinned: bool
    warning: str | None = None


def binary_env_var(service: str) -> str:
    """The explicit-path variable of *service*: ``write-service`` -> ``SPEC_KITTY_WRITE_SERVICE_BINARY``."""
    return f"SPEC_KITTY_{service.upper().replace('-', '_')}_BINARY"


def _package_root() -> Traversable:
    return importlib.resources.files("specify_cli")


def checkout_root_of(package_file: Path) -> Path | None:
    """The spec-kitty source checkout holding *package_file* (``<root>/src/specify_cli/__init__.py``), else ``None``.

    Mirrors the source-checkout guard of ``charter.offering.pack_paths``: the tree two
    levels above the package counts only when the package sits in that tree's ``src/``
    and its ``pyproject.toml`` names this distribution, so a wheel in ``site-packages``
    or installed with ``pip install --target`` inside such a tree never qualifies.
    """
    package_dir = Path(package_file).resolve().parent
    if package_dir.parent.name != _SRC_DIR:
        return None  # a wheel on site-packages, --target or PYTHONPATH: never a checkout
    root = package_dir.parent.parent
    try:
        project = tomllib.loads((root / _PYPROJECT).read_text(encoding="utf-8")).get("project", {})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return root if isinstance(project, dict) and project.get("name") == _DISTRIBUTION else None


def source_checkout_root() -> Path | None:
    """The spec-kitty source checkout the running ``specify_cli`` package belongs to, else ``None`` (a wheel)."""
    return checkout_root_of(Path(specify_cli.__file__))


def pins_dir() -> Path | None:
    """The CLI's own pin directory: its source checkout's ``pins/``, else the wheel's ``specify_cli/_pins``.

    Never the user's project: the pin names the build *this* CLI runs.
    """
    root = source_checkout_root()
    if root is not None:
        return root / PINS_DIR
    installed = _package_root() / INSTALLED_PINS_PACKAGE_DIR
    return Path(str(installed)) if installed.is_dir() else None


def find_pin(service: str) -> Path | None:
    """The pin lockfile of *service* in :func:`pins_dir`, or ``None`` when this CLI pins no build of it."""
    directory = pins_dir()
    if directory is None:
        return None
    path = directory / f"{service}{PIN_SUFFIX}"
    return path if path.is_file() else None


def load_pin(path: Path) -> ServicePin:
    """Load the lockfile at *path*; a malformed one is a ``SERVICE_PIN_INVALID`` refusal with the vendor remedy."""
    try:
        return load_service_pin(path)
    except ServicePinError as exc:
        raise ServiceRefusal(
            ServiceRefusalCode.PIN_INVALID, f"the pin {path} is invalid: {exc}", remedy_for(ServiceRefusalCode.PIN_INVALID, variant="malformed")
        ) from exc


def _load_pin(service: str) -> ServicePin:
    path = find_pin(service)
    if path is None:
        raise ServiceRefusal(
            ServiceRefusalCode.PIN_INVALID, f"no pin lockfile for {service} was found", remedy_for(ServiceRefusalCode.PIN_INVALID, service=service)
        )
    return load_pin(path)


def _check_protocol(pin: ServicePin) -> None:
    if pin.service != _WRITE_SERVICE or set(pin.protocol_versions) & set(SUPPORTED_PROTOCOL_VERSIONS):
        return
    raise ServiceRefusal(
        ServiceRefusalCode.VERSION_MISMATCH,
        f"the pinned {pin.service} {pin.tag} speaks protocol {list(pin.protocol_versions)}; this CLI speaks {list(SUPPORTED_PROTOCOL_VERSIONS)}",
        remedy_for(ServiceRefusalCode.VERSION_MISMATCH),
    )


def _native_targets(pin: ServicePin) -> str:
    return ", ".join(sorted(target.value for target in pin.assets if target is not ServiceTarget.JVM)) or "none"


def _unsupported(pin: ServicePin, why: str) -> ServiceRefusal:
    """``SERVICE_UNSUPPORTED_PLATFORM``; the remedy offers Java only when the pin has a jar to run under it."""
    variant = None if pin.asset_for(ServiceTarget.JVM) is not None else "no_jar"
    return ServiceRefusal(
        ServiceRefusalCode.UNSUPPORTED_PLATFORM, why, remedy_for(ServiceRefusalCode.UNSUPPORTED_PLATFORM, variant=variant, targets=_native_targets(pin))
    )


def no_build_refusal(pin: ServicePin) -> ServiceRefusal:
    """The pin has no native build for this host and no jar (``kernel.service_hosts.select_build`` gave none)."""
    return _unsupported(pin, f"{pin.service} {pin.tag} has no pinned build for this host")


@dataclass(frozen=True)
class _Context:
    """Everything one resolution reads: the pin, the injected environment and the fetch options."""

    pin: ServicePin
    env: Mapping[str, str]
    host: ServiceTarget | None
    offline: bool
    cache_root: Path

    @property
    def asset_dir(self) -> Path:
        """The offline asset directory from the injected env only.

        ``fetch_asset`` reads the process environment when ``asset_dir`` is ``None``, so
        without one the resolver passes a directory inside its own cache that never
        exists: the injected env alone decides (``env={}`` means no asset directory).
        """
        configured = self.env.get(ASSET_DIR_ENV)
        return Path(configured) if configured else self.cache_root / _NO_ASSET_DIR


def _jar_argv(ctx: _Context, jar: Path) -> tuple[str, ...]:
    java = find_java(env=ctx.env)
    if java is None:
        raise _unsupported(ctx.pin, f"{jar} is the pinned {ctx.pin.service} jar, but no Java 25+ runtime was found")
    return (str(java), _JAR_FLAG, str(jar))


def _match_supplied(ctx: _Context, path: Path) -> tuple[tuple[str, ...], ServiceAsset] | None:
    """``(argv_prefix, asset)`` when *path* holds the pinned host build or the pinned jar, else ``None``."""
    native = ctx.pin.asset_for(ctx.host) if ctx.host is not None else None
    if native is not None and verify_asset(path, native):
        return (str(path),), native
    jar = ctx.pin.asset_for(ServiceTarget.JVM)
    if jar is not None and verify_asset(path, jar):
        return _jar_argv(ctx, path), jar
    return None


def _unpinned(service: str, path: Path) -> ResolvedBinary:
    """The opt-in result. It runs *path* directly, so an unpinned ``.jar`` must be wrapped by the developer."""
    warning = f"Running an UNPINNED {service} binary at {path} ({UNPINNED_ENV}=1). This build is not verified against the pin."
    return ResolvedBinary(argv_prefix=(str(path),), path=path, source="unpinned", sha256=sha256_file(path), pinned=False, warning=warning)


def _explicit(ctx: _Context) -> ResolvedBinary | None:
    env_var = binary_env_var(ctx.pin.service)
    raw = ctx.env.get(env_var)
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise ServiceRefusal(
            ServiceRefusalCode.BINARY_MISSING,
            f"{env_var} names {path}, which is not a file",
            remedy_for(ServiceRefusalCode.BINARY_MISSING, variant="explicit", env_var=env_var),
        )
    matched = _match_supplied(ctx, path)
    if matched is not None:
        argv, asset = matched
        return ResolvedBinary(argv_prefix=argv, path=path, source="explicit", sha256=asset.sha256, pinned=True)
    if ctx.env.get(UNPINNED_ENV) == "1":
        return _unpinned(ctx.pin.service, path)
    raise ServiceRefusal(
        ServiceRefusalCode.DIGEST_MISMATCH,
        f"{path} (from {env_var}) is not the pinned {ctx.pin.service} {ctx.pin.tag} build for this host",
        remedy_for(ServiceRefusalCode.DIGEST_MISMATCH, variant="explicit", env_var=env_var),
    )


class _ProviderEntry(Protocol):
    """The part of ``importlib.metadata.EntryPoint`` the install slot uses."""

    def load(self) -> Any: ...


def _binary_providers(service: str) -> Iterable[_ProviderEntry]:
    """The install-slot entry points registered for *service* (none today); loaded by :func:`_provided_path`."""
    return list(entry_points(group=BINARY_PROVIDER_GROUP, name=service))


def _provided_path(service: str, entry: _ProviderEntry) -> Path | None:
    try:
        raw = entry.load()()
    except Exception as exc:  # a third-party provider: a failure to load or to run becomes a refusal, never a crash
        raise ServiceRefusal(
            ServiceRefusalCode.BINARY_MISSING,
            f"the installed {service} binary provider failed ({type(exc).__name__})",
            remedy_for(ServiceRefusalCode.BINARY_MISSING, variant="install", service=service),
        ) from exc
    return None if raw is None else Path(str(raw)).resolve()


def _install(ctx: _Context) -> ResolvedBinary | None:
    for entry in _binary_providers(ctx.pin.service):
        path = _provided_path(ctx.pin.service, entry)
        if path is None:
            continue
        matched = _match_supplied(ctx, path)
        if matched is None:
            raise ServiceRefusal(
                ServiceRefusalCode.DIGEST_MISMATCH,
                f"the installed {ctx.pin.service} binary {path} is not the pinned {ctx.pin.tag} build for this host",
                remedy_for(ServiceRefusalCode.DIGEST_MISMATCH, variant="install", service=ctx.pin.service),
            )
        argv, asset = matched
        return ResolvedBinary(argv_prefix=argv, path=path, source="install", sha256=asset.sha256, pinned=True)
    return None


def _kernel_reason(exc: ServiceArtifactError) -> str:
    """The kernel's own cause, without its code prefix and without its trailing hint (the remedy replaces it)."""
    return str(exc).removeprefix(f"{exc.code}: ").split("; ", 1)[0]


def _asset_dir_candidate(asset_dir: Path | None, pin: ServicePin, asset: ServiceAsset) -> Path | None:
    """The asset-directory file ``fetch_asset`` would use for *asset* (the first that exists), else ``None``."""
    if asset_dir is None:
        return None
    for candidate in (asset_dir / asset.name, asset_dir / pin.tag / asset.name):
        if candidate.is_symlink() or candidate.exists():
            return candidate
    return None


def artifact_refusal(pin: ServicePin, asset: ServiceAsset, exc: ServiceArtifactError, *, cache_root: Path, asset_dir: Path | None) -> ServiceRefusal:
    """The refusal for a ``kernel.service_artifacts`` failure, with the remedy that fits its cause.

    ``SERVICE_BINARY_MISSING``: a cache the kernel could not write (an ``OSError`` cause: a full
    disk, a permission) points at the cache; anything else at ``service fetch`` or the asset
    directory. ``SERVICE_BINARY_DIGEST_MISMATCH``: an existing asset-directory file is the source
    (the cache is checked first and a bad copy evicted, and such a file decides without a
    download), else the cache or the download. Shared by resolution and ``service fetch``.
    """
    reason = _kernel_reason(exc)
    if exc.code == SERVICE_BINARY_MISSING:
        if isinstance(exc.__cause__, OSError):
            return ServiceRefusal(ServiceRefusalCode.BINARY_MISSING, reason, remedy_for(ServiceRefusalCode.BINARY_MISSING, variant="cache", cache=cache_root))
        return ServiceRefusal(ServiceRefusalCode.BINARY_MISSING, reason, remedy_for(ServiceRefusalCode.BINARY_MISSING, asset=asset.name))
    candidate = _asset_dir_candidate(asset_dir, pin, asset)
    if candidate is not None:
        remedy = remedy_for(ServiceRefusalCode.DIGEST_MISMATCH, variant="asset_dir", path=candidate)
    else:
        remedy = remedy_for(ServiceRefusalCode.DIGEST_MISMATCH, path=cached_path(pin, asset, cache_root))
    return ServiceRefusal(ServiceRefusalCode.DIGEST_MISMATCH, reason, remedy)


def _fetch(ctx: _Context, asset: ServiceAsset, *, local_only: bool = False) -> Path | ServiceRefusal:
    """The verified cache path of *asset*; an unavailable asset is returned as a refusal, anything else raises one.

    ``SERVICE_BINARY_MISSING`` is returned (the jar may still stand in); every other
    code, ``SERVICE_BINARY_DIGEST_MISMATCH`` included, refuses outright (fail closed).
    With *local_only*, nothing is downloaded: only the cache and the asset directory.
    """
    try:
        return fetch_asset(ctx.pin, asset, offline=ctx.offline or local_only, cache_root=ctx.cache_root, asset_dir=ctx.asset_dir)
    except ServiceArtifactError as exc:
        refusal = artifact_refusal(ctx.pin, asset, exc, cache_root=ctx.cache_root, asset_dir=ctx.asset_dir)
        if exc.code == SERVICE_BINARY_MISSING:
            return refusal
        raise refusal from exc


def _cache(ctx: _Context, asset: ServiceAsset) -> ResolvedBinary | ServiceRefusal:
    fetched = _fetch(ctx, asset)
    if isinstance(fetched, ServiceRefusal):
        return fetched
    return ResolvedBinary(argv_prefix=(str(fetched),), path=fetched, source="cache", sha256=asset.sha256, pinned=True)


def _jar(ctx: _Context, asset: ServiceAsset, *, standing_in: bool) -> ResolvedBinary | None:
    """The pinned jar under a Java 25+ runtime, or ``None`` without one.

    *standing_in* (the native build was unavailable): the jar is taken only from the cache or
    the asset directory, never downloaded (whatever kept the native build away keeps the jar
    away too), and its absence returns ``None`` so the native build's refusal is raised.
    """
    java = find_java(env=ctx.env)
    if java is None:
        return None
    fetched = _fetch(ctx, asset, local_only=standing_in)
    if isinstance(fetched, ServiceRefusal):
        if standing_in:
            return None
        raise fetched
    return ResolvedBinary(argv_prefix=(str(java), _JAR_FLAG, str(fetched)), path=fetched, source="jar", sha256=asset.sha256, pinned=True)


def resolve_binary(
    service: str,
    *,
    env: Mapping[str, str] | None = None,
    offline: bool = False,
    cache_root: Path | None = None,
) -> ResolvedBinary:
    """The verified binary of *service* (see the module docstring for the order), or a :class:`ServiceRefusal`.

    *env* (default: the process environment) is the only environment resolution reads:
    the explicit path, the opt-in, the asset directory and ``JAVA_HOME``/``PATH``.
    """
    pin = _load_pin(service)
    _check_protocol(pin)
    ctx = _Context(
        pin=pin,
        env=os.environ if env is None else env,
        host=host_target(),
        offline=offline,
        cache_root=default_cache_root() if cache_root is None else Path(cache_root),
    )
    supplied = _explicit(ctx) or _install(ctx)
    if supplied is not None:
        return supplied
    build = select_build(pin, ctx.host)
    if build is None:
        raise no_build_refusal(pin)
    if build.target is ServiceTarget.JVM:
        jar = _jar(ctx, build.asset, standing_in=False)
        if jar is None:
            raise _unsupported(pin, f"there is no pinned {service} build for this host and no usable Java 25+ runtime for the pinned jar")
        return jar
    cached = _cache(ctx, build.asset)
    if isinstance(cached, ResolvedBinary):
        return cached
    jar_asset = pin.asset_for(ServiceTarget.JVM)
    standin = _jar(ctx, jar_asset, standing_in=True) if jar_asset is not None else None
    if standin is not None:
        return standin
    raise cached


def verify_before_exec(resolved: ResolvedBinary) -> None:
    """Re-hash the file about to run; raise ``SERVICE_BINARY_DIGEST_MISMATCH`` when it changed since resolve.

    An unpinned binary (the developer opt-in) is not checked.
    """
    if not resolved.pinned:
        return
    try:
        digest = sha256_file(resolved.path)
    except OSError:
        digest = ""
    if not hmac.compare_digest(digest, resolved.sha256):
        raise ServiceRefusal(
            ServiceRefusalCode.DIGEST_MISMATCH,
            f"{resolved.path} changed after it was verified and was not run",
            remedy_for(ServiceRefusalCode.DIGEST_MISMATCH, path=resolved.path),
        )
