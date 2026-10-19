"""``pack_fetch``: sparse fetch at a SHA, cache, digest verification, atomic placement (WP02).

Every error code is driven by real git against a ``file://`` bare repository.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from charter.offering.packs.pack_fetch import (
    PACK_COMMIT_UNRESOLVABLE,
    PACK_DIGEST_MISMATCH,
    PACK_PIN_INVALID,
    PACK_SYNC_UNAVAILABLE,
    PackSyncError,
    PackTreeStatus,
    check_pack,
    fetch_to_cache,
    place_pack,
    recover_interrupted_swap,
)
from tests.charter_offering.conftest_pack_remote import make_pack_remote, write_pack_tree

pytestmark = [pytest.mark.git_repo]

_BAD_DIGEST = "f" * 64
_MISSING_SHA = "0" * 40


@pytest.mark.parametrize("subtree", ["built-in", "packs/built-in"])
def test_fresh_sync_places_tree_whose_digest_matches(tmp_path: Path, subtree: str) -> None:
    remote = make_pack_remote(tmp_path, subtree=subtree)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    place_pack(cached, dest, pin)
    assert (dest / "pack.yaml").is_file()
    assert not (dest / ".git").exists()
    assert check_pack(pin, dest) is PackTreeStatus.OK


def test_second_sync_is_a_cache_hit_without_the_remote(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cache = tmp_path / "cache"
    cold_start = time.perf_counter()
    first = fetch_to_cache(pin, cache_root=cache)
    cold = time.perf_counter() - cold_start
    shutil.move(str(remote.bare), str(tmp_path / "gone.git"))  # the remote is now unreachable
    warm_start = time.perf_counter()
    second = fetch_to_cache(pin, cache_root=cache)
    warm = time.perf_counter() - warm_start
    assert second == first
    print(f"NFR timings: cold={cold:.3f}s warm={warm:.4f}s")  # noqa: T201 - recorded in the WP note
    assert warm < cold


def test_digest_mismatch_leaves_previous_tree_and_cache_clean(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="previous")
    before = (dest / "directives" / "001-x.directive.yaml").read_text()
    cache = tmp_path / "cache"
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(remote.pin(digest=_BAD_DIGEST), cache_root=cache)
    assert info.value.code == PACK_DIGEST_MISMATCH
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == before
    assert not any(cache.glob("*/*")), "a tree that failed its digest must not stay in the cache"


def test_unknown_sha_is_commit_unresolvable(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(remote.pin(sha=_MISSING_SHA), cache_root=tmp_path / "cache")
    assert info.value.code == PACK_COMMIT_UNRESOLVABLE


def test_unreachable_remote_without_cache_names_make_sync_packs(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin(url=(tmp_path / "nowhere.git").as_uri())
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(pin, cache_root=tmp_path / "cache")
    assert info.value.code == PACK_SYNC_UNAVAILABLE
    assert "make sync-packs" in str(info.value)


def test_offline_without_cache_is_sync_unavailable(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(remote.pin(), offline=True, cache_root=tmp_path / "cache")
    assert info.value.code == PACK_SYNC_UNAVAILABLE
    assert "make sync-packs" in str(info.value)


def test_offline_with_cache_succeeds(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    cache = tmp_path / "cache"
    first = fetch_to_cache(remote.pin(), cache_root=cache)
    assert fetch_to_cache(remote.pin(), offline=True, cache_root=cache) == first


def test_filter_refusing_server_still_syncs(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path, allow_filter=False)
    cached = fetch_to_cache(remote.pin(), cache_root=tmp_path / "cache")
    assert (cached / "pack.yaml").is_file()


def test_corrupt_cache_is_discarded_and_refetched(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    cache = tmp_path / "cache"
    cached = fetch_to_cache(remote.pin(), cache_root=cache)
    (cached / "directives" / "001-x.directive.yaml").write_text("id: X\nbody: poisoned\n")
    again = fetch_to_cache(remote.pin(), cache_root=cache)
    assert check_pack(remote.pin(), again) is PackTreeStatus.OK


def test_corrupt_cache_offline_is_unavailable_not_trusted(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    cache = tmp_path / "cache"
    cached = fetch_to_cache(remote.pin(), cache_root=cache)
    (cached / "pack.yaml").write_text("tampered\n")
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(remote.pin(), offline=True, cache_root=cache)
    assert info.value.code == PACK_SYNC_UNAVAILABLE


def test_place_pack_rehashes_the_staged_copy(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="previous")
    before = (dest / "directives" / "001-x.directive.yaml").read_text()
    (cached / "directives" / "001-x.directive.yaml").write_text("id: X\nbody: poisoned after the hit\n")
    with pytest.raises(PackSyncError) as info:
        place_pack(cached, dest, pin)
    assert info.value.code == PACK_DIGEST_MISMATCH
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == before
    assert not [p for p in dest.parent.iterdir() if p.name.startswith(".")], "no staging or aside dir may remain"


def test_check_pack_ok_stale_missing(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    dest = tmp_path / "packs" / "built-in"
    assert check_pack(pin, dest) is PackTreeStatus.MISSING
    place_pack(fetch_to_cache(pin, cache_root=tmp_path / "cache"), dest, pin)
    assert check_pack(pin, dest) is PackTreeStatus.OK
    (dest / "directives" / "001-x.directive.yaml").write_text("id: X\nbody: edited\n")
    assert check_pack(pin, dest) is PackTreeStatus.STALE


def test_check_pack_never_trusts_a_marker_file(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="other")
    (dest / ".synced").write_text(pin.commit)
    assert check_pack(pin, dest) is PackTreeStatus.STALE


def test_symlink_in_fetched_tree_is_refused(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path, symlink="evil-link")
    with pytest.raises(PackSyncError, match="symlink"):
        fetch_to_cache(remote.pin(), cache_root=tmp_path / "cache")


def test_symlink_planted_in_cache_is_refused_by_place_pack(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    (cached / "link").symlink_to(tmp_path)
    with pytest.raises(PackSyncError, match="symlink"):
        place_pack(cached, tmp_path / "packs" / "built-in", pin)


def test_subtree_absent_in_commit_is_refused(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    absent = type(pin)(repository=pin.repository, commit=pin.commit, tree_digest=pin.tree_digest, subtree="no/such")
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(absent, cache_root=tmp_path / "cache")
    assert info.value.code == PACK_COMMIT_UNRESOLVABLE


def test_interrupted_swap_is_restored_on_next_run(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="previous")

    calls: list[tuple[Path, Path]] = []

    class Crash(BaseException):
        """Stands for a kill between the aside-rename and the final rename."""

    def crashing_rename(src: Path, dst: Path) -> None:
        calls.append((src, dst))
        if len(calls) == 2:
            raise Crash
        src.rename(dst)

    with pytest.raises(Crash):
        place_pack(cached, dest, pin, rename=crashing_rename)
    # The in-call cleanup already put the old tree back; simulate a hard kill by moving it aside again.
    if dest.exists():
        dest.rename(dest.parent / ".built-in.aside")
    assert not dest.exists()
    recover_interrupted_swap(dest)
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == "id: X\nbody: previous\n"
    place_pack(cached, dest, pin)
    assert check_pack(pin, dest) is PackTreeStatus.OK


def test_failed_swap_restores_previous_tree_in_call(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="previous")
    seen = 0

    def failing_second(src: Path, dst: Path) -> None:
        nonlocal seen
        seen += 1
        if seen == 2:
            raise PermissionError("locked")
        src.rename(dst)

    with pytest.raises(PermissionError):
        place_pack(cached, dest, pin, rename=failing_second, retries=1)
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == "id: X\nbody: previous\n"
    assert not [p for p in dest.parent.iterdir() if p.name.startswith(".")]


def test_rename_is_retried_a_bounded_number_of_times(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    attempts = 0

    def flaky(src: Path, dst: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("antivirus holds the dir")
        src.rename(dst)

    place_pack(cached, dest, pin, rename=flaky, retries=3, retry_delay=0)
    assert check_pack(pin, dest) is PackTreeStatus.OK


def test_pin_without_subtree_is_refused(tmp_path: Path) -> None:
    remote = make_pack_remote(tmp_path)
    pin = remote.pin()
    bare = type(pin)(repository=pin.repository, commit=pin.commit, tree_digest=pin.tree_digest, subtree=None)
    with pytest.raises(PackSyncError):
        fetch_to_cache(bare, cache_root=tmp_path / "cache")


@pytest.mark.parametrize(("field", "value"), [("subtree", "-built-in"), ("repository", "--upload-pack=evil")])
def test_unsafe_pin_that_bypasses_validation_is_pack_pin_invalid(tmp_path: Path, field: str, value: str) -> None:
    pin = make_pack_remote(tmp_path).pin()
    object.__setattr__(pin, field, value)  # a pin built without __post_init__ (e.g. mutated after load)
    with pytest.raises(PackSyncError) as info:
        fetch_to_cache(pin, cache_root=tmp_path / "cache")
    assert info.value.code == PACK_PIN_INVALID


def test_recover_when_dest_exists_removes_the_stale_aside(tmp_path: Path) -> None:
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="current")
    aside = dest.parent / ".built-in.aside"
    write_pack_tree(aside, marker="old")
    recover_interrupted_swap(dest)
    assert not aside.exists()
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == "id: X\nbody: current\n"


def test_recover_without_aside_is_a_noop(tmp_path: Path) -> None:
    dest = tmp_path / "packs" / "built-in"
    write_pack_tree(dest, marker="current")
    recover_interrupted_swap(dest)
    assert (dest / "directives" / "001-x.directive.yaml").read_text() == "id: X\nbody: current\n"


def test_permission_error_retries_exhaust_then_raise_and_restore(tmp_path: Path) -> None:
    pin = make_pack_remote(tmp_path).pin()
    cached = fetch_to_cache(pin, cache_root=tmp_path / "cache")
    dest = tmp_path / "packs" / "built-in"
    attempts = 0

    def always_locked(src: Path, dst: Path) -> None:
        nonlocal attempts
        attempts += 1
        raise PermissionError("locked")

    with pytest.raises(PermissionError):
        place_pack(cached, dest, pin, rename=always_locked, retries=3, retry_delay=0)
    assert attempts == 3
    assert not dest.exists()


def test_scratch_fetch_repository_with_read_only_objects_is_removed(tmp_path: Path) -> None:
    """The scratch repo holds a .git (refused by the plain guard) and read-only object files (Windows)."""
    import stat

    from charter.offering.packs import pack_fetch

    work = tmp_path / "cache" / ".fetch-abc-1"
    objects = work / ".git" / "objects" / "pack"
    objects.mkdir(parents=True)
    idx = objects / "pack-1.idx"
    idx.write_text("x")
    idx.chmod(stat.S_IREAD)
    (work / "built-in").mkdir()

    pack_fetch._remove_scratch_repo(work)

    assert not work.exists()
