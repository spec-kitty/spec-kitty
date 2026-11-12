"""New lanes get the pinned packs trees from the local cache (#7577, FR-012, SC-006).

A lane checkout of a repository that pins its packs (``packs/<name>.source.yaml``)
and does not commit the trees gets the pinned, digest-verified tree placed from the
local open-packs cache, offline only. A cold cache leaves no tree and a remedy line;
a repository without pin files is untouched.

Every case drives real git: a ``file://`` bare open-packs remote, a real cache
under an isolated ``XDG_CACHE_HOME`` and a real lane repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from charter.offering.packs import pack_fetch
from charter.offering.packs.pack_fetch import PACK_SYNC_UNAVAILABLE, PackTreeStatus, check_pack, fetch_to_cache
from charter.offering.packs.pack_pin import PackPin, write_pack_pin
from kernel.pack_tiers import BUILT_IN, pin_filename
from specify_cli.lanes.lane_packs import LanePacksResult, place_pinned_packs
from tests.charter_offering.conftest_pack_remote import make_pack_remote

pytestmark = [pytest.mark.git_repo]

_GITIGNORE = "/packs/built-in/\n/packs/internal/\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty per-user cache: ``fetch_to_cache`` resolves its default root under it."""
    home = tmp_path / "xdg-cache"
    home.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(home))
    return home


@pytest.fixture()
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any remote fetch is a test failure: placing packs into a lane is offline only."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("place_pinned_packs contacted the open-packs remote")

    monkeypatch.setattr(pack_fetch, "fetch_commit_subtree", _refuse)


def _pinned_lane(tmp_path: Path, pin: PackPin) -> Path:
    """A lane repository that commits the built-in pin and the gitignore, not the tree."""
    lane = tmp_path / "lane"
    lane.mkdir()
    _git(lane, "init", "-q", "-b", "trunk")
    _git(lane, "config", "user.email", "t@example.com")
    _git(lane, "config", "user.name", "Test")
    _git(lane, "config", "commit.gpgsign", "false")
    (lane / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")
    (lane / "packs").mkdir()
    write_pack_pin(pin, lane / "packs" / pin_filename(BUILT_IN))
    _git(lane, "add", "-A")
    _git(lane, "commit", "-q", "-m", "pin the packs")
    return lane


def _warm(pin: PackPin) -> None:
    """Fill the default cache for *pin* the way ``make sync-packs`` does (online, once)."""
    fetch_to_cache(pin)


def test_warm_cache_places_a_tree_that_verifies_against_the_pin(tmp_path: Path, cache_home: Path) -> None:
    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)
    _warm(pin)

    result = place_pinned_packs(lane)

    assert result == LanePacksResult(placed=(BUILT_IN,), skipped=())
    assert result.remedy_lines(lane) == ()
    assert check_pack(pin, lane / "packs" / BUILT_IN) is PackTreeStatus.OK


def test_cold_cache_places_nothing_and_returns_the_remedy(tmp_path: Path, cache_home: Path, no_network: None) -> None:
    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)

    result = place_pinned_packs(lane)

    assert not (lane / "packs" / BUILT_IN).exists()
    assert result.placed == ()
    assert result.skipped == ((BUILT_IN, PACK_SYNC_UNAVAILABLE),)
    assert result.remedy_lines(lane) == (f"packs/{BUILT_IN} not placed in the lane ({PACK_SYNC_UNAVAILABLE}); run `make sync-packs` in {lane}",)


def test_warm_cache_never_contacts_the_remote(tmp_path: Path, cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)
    _warm(pin)
    monkeypatch.setattr(pack_fetch, "fetch_commit_subtree", _raise_network)

    assert place_pinned_packs(lane).placed == (BUILT_IN,)


def _raise_network(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("place_pinned_packs contacted the open-packs remote")


def test_a_tree_already_present_is_left_untouched(tmp_path: Path, cache_home: Path, no_network: None) -> None:
    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)
    existing = lane / "packs" / BUILT_IN
    existing.mkdir()
    marker = existing / "operator-owned.txt"
    marker.write_text("keep me\n", encoding="utf-8")
    before = marker.stat().st_mtime_ns

    result = place_pinned_packs(lane)

    assert result == LanePacksResult(placed=(), skipped=())
    assert marker.read_text(encoding="utf-8") == "keep me\n"
    assert marker.stat().st_mtime_ns == before
    assert sorted(p.name for p in existing.iterdir()) == ["operator-owned.txt"]


def test_a_repository_without_pin_files_is_a_silent_no_op(tmp_path: Path, cache_home: Path, no_network: None, capsys: pytest.CaptureFixture[str]) -> None:
    lane = tmp_path / "consumer"
    (lane / "src").mkdir(parents=True)

    result = place_pinned_packs(lane)

    assert result == LanePacksResult(placed=(), skipped=())
    assert result.remedy_lines(lane) == ()
    assert not (lane / "packs").exists()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_the_placed_tree_is_ignored_by_git(tmp_path: Path, cache_home: Path) -> None:
    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)
    _warm(pin)

    place_pinned_packs(lane)

    assert (lane / "packs" / BUILT_IN / "pack.yaml").is_file()
    assert _git(lane, "status", "--porcelain", "--untracked-files=all") == ""


def test_an_unreadable_pin_is_skipped_with_a_bounded_reason(tmp_path: Path, cache_home: Path, no_network: None) -> None:
    lane = tmp_path / "lane"
    (lane / "packs").mkdir(parents=True)
    (lane / "packs" / pin_filename(BUILT_IN)).write_text("not: [a valid pin\n", encoding="utf-8")

    result = place_pinned_packs(lane)

    assert result.placed == ()
    assert [name for name, _reason in result.skipped] == [BUILT_IN]
    (line,) = result.remedy_lines(lane)
    assert line.startswith(f"packs/{BUILT_IN} not placed in the lane (")
    assert len(line) < 400


def test_a_placement_os_error_is_skipped_with_a_one_line_bounded_reason(tmp_path: Path, cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.packs

    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)
    _warm(pin)

    def _disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("No space left on device\n" + "x" * 500)

    monkeypatch.setattr(charter.packs, "place_pack", _disk_full)

    result = place_pinned_packs(lane)

    assert result.placed == ()
    ((name, reason),) = result.skipped
    assert name == BUILT_IN
    assert reason.startswith("OSError: No space left on device x")
    assert reason.endswith("...") and len(reason) == 160
    assert "\n" not in reason


def test_the_lane_checkout_seam_degrades_an_unexpected_error_to_a_remedy_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from specify_cli.lanes import lane_checkout, lane_packs

    def _boom(_lane: Path) -> LanePacksResult:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(lane_packs, "place_pinned_packs", _boom)

    lane_checkout._place_pinned_packs(tmp_path)

    assert capsys.readouterr().err == f"packs not placed in the lane (unexpected RuntimeError); run `make sync-packs` in {tmp_path}\n"


def test_the_lane_checkout_seam_prints_each_remedy_line_to_stderr(tmp_path: Path, cache_home: Path, no_network: None, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.lanes import lane_checkout

    pin = make_pack_remote(tmp_path).pin()
    lane = _pinned_lane(tmp_path, pin)

    lane_checkout._place_pinned_packs(lane)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"packs/{BUILT_IN} not placed in the lane ({PACK_SYNC_UNAVAILABLE}); run `make sync-packs` in {lane}\n"
