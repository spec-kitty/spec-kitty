"""``spec-kitty implement`` places the pinned packs trees into a new lane (#7577, FR-012, SC-006).

Driven through the ``implement`` command on a seeded fixture repository that pins
``packs/built-in`` (``packs/built-in.source.yaml``) and gitignores the tree, the way
this repository does. A warm open-packs cache gives the new lane a tree that verifies
against the pin; a cold cache leaves the lane without it, prints the remedy line naming
the lane, and ``implement`` still succeeds.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.offering.packs import pack_fetch
from charter.offering.packs.pack_fetch import PACK_SYNC_UNAVAILABLE, PackTreeStatus, check_pack, fetch_to_cache
from charter.offering.packs.pack_pin import PackPin, write_pack_pin
from kernel.pack_tiers import BUILT_IN, pin_filename
from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from tests.charter_offering.conftest_pack_remote import make_pack_remote
from tests.specify_cli.cli.commands.test_implement_characterization import (
    ARGS,
    LANE_WORKTREE,
    activate_repo,
    flat,
    git,
    implement_cli,
    init_repo,
    lanes_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _reset_ambient_warning_latch() -> Iterator[None]:
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture()
def pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PackPin:
    """A real open-packs remote and its pin, with the per-user cache isolated and empty."""
    cache_home = tmp_path / "xdg-cache"
    cache_home.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    remote_root = tmp_path / "open-packs"
    remote_root.mkdir()
    return make_pack_remote(remote_root).pin()


@pytest.fixture()
def pinned_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pin: PackPin) -> Path:
    """A project repository that commits the built-in pin and gitignores the tree."""
    root = init_repo(tmp_path / "repo")
    (root / ".gitignore").write_text("/packs/built-in/\n/packs/internal/\n", encoding="utf-8")
    (root / "packs").mkdir()
    write_pack_pin(pin, root / "packs" / pin_filename(BUILT_IN))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "pin the packs")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("implement contacted the open-packs remote")

    monkeypatch.setattr(pack_fetch, "fetch_commit_subtree", _refuse)


def test_a_warm_cache_gives_the_new_lane_the_verified_tree(pinned_repo: Path, pin: PackPin, monkeypatch: pytest.MonkeyPatch) -> None:
    fetch_to_cache(pin)  # what `make sync-packs` left behind in the per-user cache
    _block_network(monkeypatch)
    lanes_mission(pinned_repo)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    lane = pinned_repo / LANE_WORKTREE
    assert check_pack(pin, lane / "packs" / BUILT_IN) is PackTreeStatus.OK
    assert "not placed in the lane" not in flat(result.output)
    assert git(lane, "status", "--porcelain", "--untracked-files=all") == ""


def test_a_cold_cache_leaves_no_tree_prints_the_remedy_and_still_succeeds(pinned_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    lanes_mission(pinned_repo)

    result = implement_cli(*ARGS)

    assert result.exit_code == 0, result.output
    lane = pinned_repo / LANE_WORKTREE
    assert lane.is_dir()
    assert not (lane / "packs" / BUILT_IN).exists()
    expected = f"packs/{BUILT_IN} not placed in the lane ({PACK_SYNC_UNAVAILABLE}); run `make sync-packs` in {lane}"
    assert expected in flat(result.output)
