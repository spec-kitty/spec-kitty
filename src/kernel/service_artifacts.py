"""The verified service-asset cache (#6590, FR-002, FR-010, NFR-003).

The only way to obtain the path of a pinned service asset. A cached asset
lives at ``<cache_root>/<service>/<tag>/<name>`` (``data-model.md``,
CachedAsset) and is trusted only while its SHA-256 equals the pin's: every
resolve re-hashes it, and a copy that does not verify (or is a symlink, or is
not a regular file) is deleted. No function here returns an unverified path.

:func:`fetch_asset` tries, in order: the cache; the offline asset directory
(``SPEC_KITTY_SERVICE_ASSET_DIR``, flat ``<dir>/<name>`` then
``<dir>/<tag>/<name>``), whose verified file is *copied* into the cache and
never run in place; then, unless offline, a download through
``kernel.release_assets`` (the one download owner) into a scratch file that is
verified before it is renamed into the cache.

Failures are :class:`ServiceArtifactError` with ``code``
:data:`SERVICE_BINARY_MISSING` (unreachable, absent, cache not writable) or
:data:`SERVICE_BINARY_DIGEST_MISMATCH` (the bytes are not the pinned bytes).
Messages never echo a digest. This mirrors
``charter.offering.packs.pack_fetch`` ("a poisoned cache is never trusted",
scratch-then-rename, the Windows rename retry) without importing it: ``kernel``
is the root layer.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from kernel.release_assets import ReleaseAssetUnavailable, asset_url, download
from kernel.service_pin import ServiceAsset, ServicePin, ServiceTarget
from kernel.tree_removal import remove_tool_owned_tree
from kernel.user_dirs import user_cache_dir

__all__ = [
    "ASSET_DIR_ENV",
    "SERVICE_BINARY_DIGEST_MISMATCH",
    "SERVICE_BINARY_MISSING",
    "ServiceArtifactError",
    "cached_path",
    "default_cache_root",
    "fetch_asset",
    "sha256_file",
    "verify_asset",
]

SERVICE_BINARY_MISSING = "SERVICE_BINARY_MISSING"
SERVICE_BINARY_DIGEST_MISMATCH = "SERVICE_BINARY_DIGEST_MISMATCH"
#: Environment variable naming an offline directory that can supply pinned assets.
ASSET_DIR_ENV = "SPEC_KITTY_SERVICE_ASSET_DIR"

_CHUNK = 1024 * 1024
_EXECUTABLE_MODE = 0o755
_RETRIES = 5
_RETRY_DELAY = 0.2
_SCRATCH_SUFFIX = ".download"
_ASSET_DIR_HINT = f"set {ASSET_DIR_ENV} to a directory holding the pinned asset"
_MISMATCH_TAIL = "does not match the pinned sha256"
_replace = os.replace


class ServiceArtifactError(RuntimeError):
    """A pinned service asset could not be provided; ``code`` is a stable ``SERVICE_BINARY_*`` code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def default_cache_root() -> Path:
    """``${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services``, on Windows too (no ``LOCALAPPDATA`` branch)."""
    return user_cache_dir(windows_local_appdata=False) / "spec-kitty" / "services"


def _hash_stream(fd: int) -> str:
    digest = hashlib.sha256()  # noqa: TID251 - file-integrity check against the pinned release digest, not the charter freshness hash
    with os.fdopen(fd, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    """The hex SHA-256 of the file at *path*, read in chunks."""
    return _hash_stream(os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0)))


def _regular_file_digest(path: Path) -> str | None:
    """The digest of *path* when it is a regular file reached without a symlink, else ``None``."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        if path.is_symlink():
            return None
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        regular = stat.S_ISREG(os.fstat(fd).st_mode)
    except OSError:
        regular = False
    if not regular:
        os.close(fd)
        return None
    try:
        return _hash_stream(fd)
    except OSError:
        return None


def verify_asset(path: Path, asset: ServiceAsset) -> bool:
    """True only when *path* is a regular, non-symlink file whose SHA-256 is the pinned one."""
    digest = _regular_file_digest(Path(path))
    return digest is not None and hmac.compare_digest(digest, asset.sha256)


def cached_path(pin: ServicePin, asset: ServiceAsset, cache_root: Path) -> Path:
    """Where *asset* of *pin* lives in the cache: ``<cache_root>/<service>/<tag>/<name>``."""
    return Path(cache_root) / pin.service / pin.tag / asset.name


def _root(cache_root: Path | None) -> Path:
    return default_cache_root() if cache_root is None else Path(cache_root)


def _not_writable(path: Path, exc: OSError) -> ServiceArtifactError:
    cause = f"{type(exc).__name__}: {exc.strerror}" if exc.strerror else type(exc).__name__
    return ServiceArtifactError(
        SERVICE_BINARY_MISSING,
        f"the service cache {path} is not writable ({cause}); {_ASSET_DIR_HINT}, or free space in or fix the permissions of the cache",
    )


def _evict(path: Path, cache_root: Path) -> None:
    try:
        if path.is_dir() and not path.is_symlink():
            remove_tool_owned_tree(path, tool_root=cache_root, reason="evict an unverified service cache entry")
        else:
            path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _not_writable(path.parent, exc) from exc


def resolve_cached(pin: ServicePin, asset: ServiceAsset, *, cache_root: Path | None = None) -> Path | None:
    """The cached path of *asset* when it verifies; otherwise ``None``.

    A cache entry that exists but does not verify (wrong bytes, a symlink, a
    directory) is deleted first, so the next fetch replaces it. A verified native
    build is handed out with mode 0o755 on POSIX, whatever mode the file had.
    """
    root = _root(cache_root)
    path = cached_path(pin, asset, root)
    if verify_asset(path, asset):
        _ensure_executable(pin, asset, path)
        return path
    if path.is_symlink() or path.exists():
        _evict(path, root)
    return None


def _discard(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def _cleanup(scratch: Path) -> None:
    """Remove a scratch file left by any failure or interrupt; after a successful install there is none."""
    with contextlib.suppress(OSError):
        scratch.unlink()


def _scratch(target: Path) -> Path:
    """A fresh, empty scratch file beside *target* (creating the cache directory)."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=_SCRATCH_SUFFIX)
    except OSError as exc:
        raise _not_writable(target.parent, exc) from exc
    os.close(fd)
    return Path(name)


def _is_native(pin: ServicePin, asset: ServiceAsset) -> bool:
    return any(pinned == asset and target is not ServiceTarget.JVM for target, pinned in pin.assets.items())


def _ensure_executable(pin: ServicePin, asset: ServiceAsset, path: Path) -> None:
    """Re-assert the exec bits of a verified native build on POSIX (a restored cache or a copy can drop them)."""
    if os.name != "posix" or not _is_native(pin, asset):
        return
    try:
        if stat.S_IMODE(path.stat().st_mode) != _EXECUTABLE_MODE:
            path.chmod(_EXECUTABLE_MODE)
    except OSError as exc:
        raise _not_writable(path.parent, exc) from exc


def _rename_with_retry(src: Path, dst: Path) -> None:
    """``os.replace`` with bounded retries for the transient ``PermissionError`` Windows raises."""
    for attempt in range(1, _RETRIES + 1):
        try:
            _replace(src, dst)
        except PermissionError:
            if attempt == _RETRIES:
                raise
            time.sleep(_RETRY_DELAY)
        else:
            return


def _install(pin: ServicePin, asset: ServiceAsset, scratch: Path, target: Path) -> Path:
    """Move the verified *scratch* file to *target* (executable when it is a native build)."""
    try:
        if os.name == "posix" and _is_native(pin, asset):
            scratch.chmod(_EXECUTABLE_MODE)
        _rename_with_retry(scratch, target)
    except OSError as exc:
        _discard(scratch)
        raise _not_writable(target.parent, exc) from exc
    return target


def _asset_dir(asset_dir: Path | None) -> Path | None:
    if asset_dir is not None:
        return Path(asset_dir)
    configured = os.environ.get(ASSET_DIR_ENV)
    return Path(configured) if configured else None


def _from_asset_dir(pin: ServicePin, asset: ServiceAsset, source_dir: Path, target: Path) -> Path | None:
    """Copy *asset* from the offline directory into the cache, or ``None`` when it is not there.

    The first existing candidate decides. A candidate that fails verification
    is not ours, so it is left in place and refused.
    """
    for candidate in (source_dir / asset.name, source_dir / pin.tag / asset.name):
        if not (candidate.is_symlink() or candidate.exists()):
            continue
        if not verify_asset(candidate, asset):
            raise ServiceArtifactError(SERVICE_BINARY_DIGEST_MISMATCH, f"{candidate} {_MISMATCH_TAIL} of {asset.name}")
        scratch = _scratch(target)
        try:
            return _copy_and_install(pin, asset, candidate, scratch, target)
        finally:
            _cleanup(scratch)
    return None


def _copy_and_install(pin: ServicePin, asset: ServiceAsset, candidate: Path, scratch: Path, target: Path) -> Path:
    try:
        shutil.copyfile(candidate, scratch)
    except OSError as exc:
        raise _not_writable(target.parent, exc) from exc
    if not verify_asset(scratch, asset):  # the source changed while it was copied
        raise ServiceArtifactError(SERVICE_BINARY_DIGEST_MISMATCH, f"{candidate} changed while it was copied; {asset.name} {_MISMATCH_TAIL}")
    return _install(pin, asset, scratch, target)


def _download_into_cache(pin: ServicePin, asset: ServiceAsset, target: Path) -> Path:
    scratch = _scratch(target)
    try:
        return _download_and_install(pin, asset, scratch, target)
    finally:
        _cleanup(scratch)  # a failure or a Ctrl-C leaves no scratch file behind


def _download_and_install(pin: ServicePin, asset: ServiceAsset, scratch: Path, target: Path) -> Path:
    try:
        download(asset_url(pin.repository, pin.tag, asset.name), scratch)
    except ReleaseAssetUnavailable as exc:
        if exc.local_error is not None:  # a full disk or a permission here: the cache, not the network
            raise _not_writable(target.parent, exc.local_error) from exc.local_error
        raise ServiceArtifactError(
            SERVICE_BINARY_MISSING,
            f"cannot fetch {asset.name} of {pin.service} {pin.tag} ({exc.reason}); {_ASSET_DIR_HINT}",
        ) from exc
    if not verify_asset(scratch, asset):
        raise ServiceArtifactError(SERVICE_BINARY_DIGEST_MISMATCH, f"downloaded {asset.name} of {pin.service} {pin.tag} {_MISMATCH_TAIL}")
    return _install(pin, asset, scratch, target)


def fetch_asset(
    pin: ServicePin,
    asset: ServiceAsset,
    *,
    offline: bool = False,
    cache_root: Path | None = None,
    asset_dir: Path | None = None,
) -> Path:
    """The verified cache path of *asset*: from the cache, the asset directory, or a download.

    *asset_dir* defaults to ``$SPEC_KITTY_SERVICE_ASSET_DIR``. With *offline*,
    nothing is downloaded. Raises :class:`ServiceArtifactError`.
    """
    root = _root(cache_root)
    cached = resolve_cached(pin, asset, cache_root=root)
    if cached is not None:
        return cached
    target = cached_path(pin, asset, root)
    source_dir = _asset_dir(asset_dir)
    if source_dir is not None:
        supplied = _from_asset_dir(pin, asset, source_dir, target)
        if supplied is not None:
            return supplied
    if offline:
        raise ServiceArtifactError(
            SERVICE_BINARY_MISSING, f"{asset.name} of {pin.service} {pin.tag} is not cached and offline mode forbids a download; {_ASSET_DIR_HINT}"
        )
    return _download_into_cache(pin, asset, target)
