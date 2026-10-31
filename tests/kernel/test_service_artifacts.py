"""``kernel.service_artifacts``: the verified service-asset cache (FR-002, FR-010, NFR-003).

Every return path is checked against the pin: a corrupted, tampered or
symlinked cache entry is never returned, a corrupt release leaves nothing
cached, the offline asset directory is digest-checked and copied (never run in
place), and an unwritable cache names ``SPEC_KITTY_SERVICE_ASSET_DIR`` as the
way out. No network: releases are ``file://`` fixtures from
``tests.kernel.service_release_fixture``.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from kernel import service_artifacts
from kernel.release_assets import ReleaseAssetUnavailable
from kernel.service_artifacts import (
    ASSET_DIR_ENV,
    SERVICE_BINARY_DIGEST_MISMATCH,
    SERVICE_BINARY_MISSING,
    ServiceArtifactError,
    cached_path,
    default_cache_root,
    fetch_asset,
    resolve_cached,
    sha256_file,
    verify_asset,
)
from kernel.service_pin import ServiceTarget
from tests.kernel.service_release_fixture import SUMS_FILE, build_release

pytestmark = pytest.mark.fast

_NATIVE = ServiceTarget.LINUX_X64


@pytest.fixture(autouse=True)
def _no_asset_dir_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASSET_DIR_ENV, raising=False)


def _forbid_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(url: str, dest: Path, *, timeout: float = 60.0) -> None:
        raise AssertionError(f"unexpected download of {url}")

    monkeypatch.setattr(service_artifacts, "download", boom)


def _flip_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[0] ^= 0xFF
    path.write_bytes(bytes(data))


# --------------------------------------------------------------------------- #
# Fixture builder (T008)
# --------------------------------------------------------------------------- #


def test_fixture_release_has_sums_and_a_file_uri(tmp_path: Path) -> None:
    pin, release_dir = build_release(tmp_path / "rel", extras={"contracts": b"bundle"})
    assert pin.repository.startswith("file://")
    sums = (release_dir / SUMS_FILE).read_text(encoding="utf-8").splitlines()
    assert len(sums) == 3
    for asset in (*pin.assets.values(), *pin.extras.values()):
        assert verify_asset(release_dir / asset.name, asset)
        assert f"{asset.sha256}  {asset.name}" in sums


def test_fixture_corrupt_pins_a_wrong_digest(tmp_path: Path) -> None:
    pin, release_dir = build_release(tmp_path / "rel", corrupt={_NATIVE.value})
    native = pin.assets[_NATIVE]
    assert not verify_asset(release_dir / native.name, native)
    jar = pin.assets[ServiceTarget.JVM]
    assert verify_asset(release_dir / jar.name, jar)


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #


def test_default_cache_root_is_under_the_xdg_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_root() == tmp_path / "spec-kitty" / "services"


def test_cached_path_layout(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    assert cached_path(pin, asset, tmp_path / "c") == tmp_path / "c" / "write-service" / "service-v0.1.0" / asset.name


def test_sha256_file_streams_the_digest(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_verify_asset_rejects_missing_directory_and_symlink(tmp_path: Path) -> None:
    pin, release_dir = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    assert not verify_asset(tmp_path / "absent", asset)
    (tmp_path / "dir").mkdir()
    assert not verify_asset(tmp_path / "dir", asset)
    link = tmp_path / "link"
    link.symlink_to(release_dir / asset.name)
    assert not verify_asset(link, asset)
    assert verify_asset(release_dir / asset.name, asset)


# --------------------------------------------------------------------------- #
# fetch_asset / resolve_cached
# --------------------------------------------------------------------------- #


def test_fetch_into_empty_cache_then_resolve_does_no_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    cache = tmp_path / "cache"

    path = fetch_asset(pin, asset, cache_root=cache)

    assert path == cached_path(pin, asset, cache)
    assert verify_asset(path, asset)
    assert [p.name for p in path.parent.iterdir()] == [asset.name], "no scratch file left behind"
    _forbid_download(monkeypatch)
    assert fetch_asset(pin, asset, cache_root=cache) == path
    assert resolve_cached(pin, asset, cache_root=cache) == path


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits")
def test_native_asset_is_executable_and_jar_is_not(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    native = fetch_asset(pin, pin.assets[_NATIVE], cache_root=tmp_path / "c")
    jar = fetch_asset(pin, pin.assets[ServiceTarget.JVM], cache_root=tmp_path / "c")
    assert native.stat().st_mode & stat.S_IXUSR
    assert not jar.stat().st_mode & stat.S_IXUSR


def test_flipped_byte_in_cache_is_evicted_and_refetched(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    cache = tmp_path / "cache"
    path = fetch_asset(pin, asset, cache_root=cache)
    _flip_byte(path)

    assert resolve_cached(pin, asset, cache_root=cache) is None
    assert not path.exists(), "a mismatching cache entry is deleted"

    refetched = fetch_asset(pin, asset, cache_root=cache)
    assert verify_asset(refetched, asset)


def test_corrupt_release_asset_raises_digest_mismatch_and_caches_nothing(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel", corrupt={_NATIVE.value})
    asset = pin.assets[_NATIVE]
    cache = tmp_path / "cache"

    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, asset, cache_root=cache)

    assert info.value.code == SERVICE_BINARY_DIGEST_MISMATCH
    assert asset.name in str(info.value)
    assert asset.sha256 not in str(info.value)
    target_dir = cached_path(pin, asset, cache).parent
    assert not target_dir.exists() or list(target_dir.iterdir()) == []


def test_unreachable_release_raises_missing_and_caches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]

    def unavailable(url: str, dest: Path, *, timeout: float = 60.0) -> None:
        raise ReleaseAssetUnavailable(url, "URLError: unreachable")

    monkeypatch.setattr(service_artifacts, "download", unavailable)
    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, asset, cache_root=tmp_path / "cache")
    assert info.value.code == SERVICE_BINARY_MISSING
    assert list(cached_path(pin, asset, tmp_path / "cache").parent.iterdir()) == []


def test_offline_with_warm_cache_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    path = fetch_asset(pin, asset, cache_root=tmp_path / "cache")
    _forbid_download(monkeypatch)
    assert fetch_asset(pin, asset, offline=True, cache_root=tmp_path / "cache") == path


def test_offline_with_empty_cache_raises_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    _forbid_download(monkeypatch)
    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, pin.assets[_NATIVE], offline=True, cache_root=tmp_path / "cache")
    assert info.value.code == SERVICE_BINARY_MISSING
    assert ASSET_DIR_ENV in str(info.value)


def test_symlink_in_cache_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, release_dir = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    cache = tmp_path / "cache"
    target = cached_path(pin, asset, cache)
    target.parent.mkdir(parents=True)
    target.symlink_to(release_dir / asset.name)  # right bytes, but a symlink

    assert resolve_cached(pin, asset, cache_root=cache) is None
    assert not target.is_symlink()
    assert (release_dir / asset.name).exists(), "the symlink target is not ours and is not touched"


def test_directory_squatting_the_cache_path_is_removed(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    target = cached_path(pin, asset, tmp_path / "cache")
    target.mkdir(parents=True)
    (target / "x").write_text("x", encoding="utf-8")
    assert resolve_cached(pin, asset, cache_root=tmp_path / "cache") is None
    assert not target.exists()


# --------------------------------------------------------------------------- #
# Offline asset directory (T007)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("tagged", [False, True], ids=["flat", "tagged"])
def test_asset_dir_supplies_the_asset_and_is_copied_into_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tagged: bool) -> None:
    pin, release_dir = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    asset_dir = tmp_path / "assets"
    source_dir = asset_dir / pin.tag if tagged else asset_dir
    source_dir.mkdir(parents=True)
    shutil.copyfile(release_dir / asset.name, source_dir / asset.name)
    monkeypatch.setenv(ASSET_DIR_ENV, str(asset_dir))
    _forbid_download(monkeypatch)

    path = fetch_asset(pin, asset, offline=True, cache_root=tmp_path / "cache")

    assert path == cached_path(pin, asset, tmp_path / "cache")
    assert verify_asset(path, asset)
    assert (source_dir / asset.name).exists(), "the asset directory copy is left in place"


def test_explicit_asset_dir_argument_wins_over_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, release_dir = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    monkeypatch.setenv(ASSET_DIR_ENV, str(tmp_path / "nowhere"))
    _forbid_download(monkeypatch)
    path = fetch_asset(pin, asset, offline=True, cache_root=tmp_path / "cache", asset_dir=release_dir)
    assert verify_asset(path, asset)


def test_wrong_digest_in_asset_dir_raises_and_keeps_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    bad = asset_dir / asset.name
    bad.write_bytes(b"not the pinned bytes")
    _forbid_download(monkeypatch)

    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, asset, cache_root=tmp_path / "cache", asset_dir=asset_dir)

    assert info.value.code == SERVICE_BINARY_DIGEST_MISMATCH
    assert str(bad) in str(info.value)
    assert bad.read_bytes() == b"not the pinned bytes"
    assert resolve_cached(pin, asset, cache_root=tmp_path / "cache") is None


def test_asset_dir_without_the_file_falls_through_to_download(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    (tmp_path / "empty").mkdir()
    path = fetch_asset(pin, asset, cache_root=tmp_path / "cache", asset_dir=tmp_path / "empty")
    assert verify_asset(path, asset)


# --------------------------------------------------------------------------- #
# Unwritable cache
# --------------------------------------------------------------------------- #


def test_unwritable_cache_is_reported_even_as_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unwritable cache root refuses with the asset-dir hint, for every uid (seam-injected, #5691)."""
    pin, _ = build_release(tmp_path / "rel")

    def no_mkdir(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("read-only file system")

    monkeypatch.setattr(Path, "mkdir", no_mkdir)
    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, pin.assets[_NATIVE], cache_root=tmp_path / "cache")
    assert info.value.code == SERVICE_BINARY_MISSING
    assert ASSET_DIR_ENV in str(info.value)


def test_failed_rename_into_cache_is_reported_and_leaves_no_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = build_release(tmp_path / "rel")
    asset = pin.assets[_NATIVE]
    monkeypatch.setattr(service_artifacts, "_RETRY_DELAY", 0.0)

    def locked(_src: object, _dst: object) -> None:
        raise PermissionError("in use")

    monkeypatch.setattr(service_artifacts, "_replace", locked)
    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, asset, cache_root=tmp_path / "cache")
    assert info.value.code == SERVICE_BINARY_MISSING
    assert list(cached_path(pin, asset, tmp_path / "cache").parent.iterdir()) == []


def test_error_carries_its_code() -> None:
    error = ServiceArtifactError(SERVICE_BINARY_MISSING, "gone")
    assert error.code == SERVICE_BINARY_MISSING
    assert str(error) == "SERVICE_BINARY_MISSING: gone"


# --------------------------------------------------------------------------- #
# F3: a native cached asset is executable whenever it is handed out (POSIX)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
@pytest.mark.parametrize("via", ["resolve_cached", "fetch_asset"])
def test_a_native_cached_asset_that_lost_its_exec_bit_gets_it_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, via: str) -> None:
    pin, _ = build_release(tmp_path / "rel")
    native = pin.assets[_NATIVE]
    cache = tmp_path / "cache"
    path = fetch_asset(pin, native, cache_root=cache)
    path.chmod(0o644)  # a restored CI cache or a umask-ed copy can drop the bit
    _forbid_download(monkeypatch)

    handed = resolve_cached(pin, native, cache_root=cache) if via == "resolve_cached" else fetch_asset(pin, native, cache_root=cache)

    assert handed == path
    assert stat.S_IMODE(handed.stat().st_mode) == 0o755


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_the_jar_keeps_its_mode(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rel")
    jar = pin.assets[ServiceTarget.JVM]
    cache = tmp_path / "cache"
    path = fetch_asset(pin, jar, cache_root=cache)
    path.chmod(0o644)
    assert resolve_cached(pin, jar, cache_root=cache) == path
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


# --------------------------------------------------------------------------- #
# F10: Ctrl-C while filling the cache leaves no scratch or part file
# --------------------------------------------------------------------------- #


def _leftovers(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def test_an_interrupted_download_leaves_no_scratch_in_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel import release_assets

    pin, _ = build_release(tmp_path / "rel")
    real_open = release_assets._open

    class _Interrupting:
        def __init__(self, url: str, timeout: float) -> None:
            self._inner = real_open(url, timeout)

        def __enter__(self) -> _Interrupting:
            return self

        def __exit__(self, *exc: object) -> None:
            self._inner.close()

        def read(self, size: int = -1) -> bytes:
            raise KeyboardInterrupt

    monkeypatch.setattr(release_assets, "_open", _Interrupting)
    cache = tmp_path / "cache"

    with pytest.raises(KeyboardInterrupt):
        fetch_asset(pin, pin.assets[_NATIVE], cache_root=cache)

    assert _leftovers(cache) == []


def test_an_interrupted_copy_from_the_asset_dir_leaves_no_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, release_dir = build_release(tmp_path / "rel")

    def interrupted_copy(src: object, dst: object) -> None:
        Path(str(dst)).write_bytes(b"partial")
        raise KeyboardInterrupt

    monkeypatch.setattr(shutil, "copyfile", interrupted_copy)
    cache = tmp_path / "cache"

    with pytest.raises(KeyboardInterrupt):
        fetch_asset(pin, pin.assets[_NATIVE], cache_root=cache, asset_dir=release_dir)

    assert _leftovers(cache) == []


def test_an_asset_dir_file_that_changes_while_copied_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F13: the copy is verified again after it lands, so a source swapped mid-copy never reaches the cache."""
    pin, release_dir = build_release(tmp_path / "rel")
    native = pin.assets[_NATIVE]
    source = release_dir / native.name
    original = source.read_bytes()

    def swapped_copy(src: object, dst: object) -> None:
        Path(str(dst)).write_bytes(b"swapped while it was copied")

    monkeypatch.setattr(shutil, "copyfile", swapped_copy)
    _forbid_download(monkeypatch)
    cache = tmp_path / "cache"

    with pytest.raises(ServiceArtifactError) as info:
        fetch_asset(pin, native, cache_root=cache, asset_dir=release_dir)

    assert info.value.code == SERVICE_BINARY_DIGEST_MISMATCH
    assert "changed while it was copied" in str(info.value)
    assert native.sha256 not in str(info.value)
    assert source.read_bytes() == original
    assert _leftovers(cache) == []
