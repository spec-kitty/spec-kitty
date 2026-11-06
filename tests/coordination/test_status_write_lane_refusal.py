"""FR-041: a status write whose target is inside a registered lane checkout refuses.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10 (S6, restated ruling 3):
lane checkouts never show the Mission's status files, lanes never change them,
and readers never read them. The write seam classifies the target through the
git worktree registry (a registered linked checkout on a lane branch), never by
the ``.worktrees/`` path shape, so a lane checkout placed anywhere refuses with
``STATUS_WRITE_TARGETS_LANE_CHECKOUT``. Positive control: the same write to the
registered coordination worktree succeeds.

The registry check runs where the write already pays for git: the
``BookkeepingTransaction`` resolves its write contract through
:func:`refuse_status_write_into_lane_checkout`. The contract validator in
``status_service`` stays git-free (NFR-002, pinned by
``tests/specify_cli/coordination/test_status_surface_owned.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.status_service import (
    StatusContractError,
    refuse_status_write_into_lane_checkout,
)
from specify_cli.coordination.transaction import BookkeepingTransaction
from specify_cli.coordination.transaction_errors import BookkeepingCommitFailed
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LANE_CODE = "STATUS_WRITE_TARGETS_LANE_CHECKOUT"
_SLUG = "lwr"
_MID8 = "01M6QY1M"
_MISSION_ID = f"{_MID8}LWRZZZZZZZZZZZZZZZZZZ"
_COORD_BRANCH = f"kitty/mission-{_SLUG}-{_MID8}"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _event(event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=f"{_SLUG}-{_MID8}",
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-11-06T12:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )


def _repo(tmp_path: Path) -> Path:
    """A coordination-topology Mission with a committed ``meta.json`` and a coordination branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    mission_dir = repo / "kitty-specs" / f"{_SLUG}-{_MID8}"
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _SLUG,
        "mid8": _MID8,
        "mission_type": "research",
        "target_branch": "main",
        "created_at": "2026-11-06T00:00:00+00:00",
        "friendly_name": "FR-041 lane write refusal",
        "coordination_branch": _COORD_BRANCH,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", _COORD_BRANCH)
    return repo


def _acquire(repo: Path) -> BookkeepingTransaction:
    return BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=_MISSION_ID,
        mission_slug=_SLUG,
        mid8=_MID8,
        destination_ref=_COORD_BRANCH,
        operation="fr041-lane-write-refusal",
    )


def _log_bytes(feature_dir: Path) -> bytes:
    log = feature_dir / "status.events.jsonl"
    return log.read_bytes() if log.exists() else b""


def test_registry_classifies_lane_checkouts_wherever_they_live(tmp_path: Path) -> None:
    """A lane checkout under ``.worktrees/`` and one outside it both refuse; the root and a coord worktree do not."""
    repo = _repo(tmp_path)
    under = repo / ".worktrees" / f"{_SLUG}-{_MID8}-lane-a"
    outside = tmp_path / "elsewhere" / "lane-b-checkout"
    coord = repo / ".worktrees" / f"{_SLUG}-{_MID8}-coord"
    _git(repo, "worktree", "add", "-q", "-b", f"{_COORD_BRANCH}-lane-a", str(under), "main")
    _git(repo, "worktree", "add", "-q", "-b", f"{_COORD_BRANCH}-lane-b", str(outside), "main")
    _git(repo, "worktree", "add", "-q", str(coord), _COORD_BRANCH)

    for checkout in (under, outside):
        with pytest.raises(StatusContractError) as excinfo:
            refuse_status_write_into_lane_checkout(checkout / "kitty-specs" / f"{_SLUG}-{_MID8}")
        assert getattr(excinfo.value, "error_code", None) == _LANE_CODE
        assert _LANE_CODE in str(excinfo.value)
        assert checkout.name in str(excinfo.value)

    refuse_status_write_into_lane_checkout(repo / "kitty-specs" / f"{_SLUG}-{_MID8}")
    refuse_status_write_into_lane_checkout(coord / "kitty-specs" / f"{_SLUG}-{_MID8}")


def test_transaction_write_into_coord_named_lane_checkout_refuses(tmp_path: Path) -> None:
    """The path says coordination worktree; the registry says lane checkout. The registry wins."""
    repo = _repo(tmp_path)
    with pytest.raises(StatusContractError) as excinfo, _acquire(repo) as txn:
        assert txn.worktree_root == CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
        _git(txn.worktree_root, "switch", "-q", "-c", f"{_COORD_BRANCH}-lane-z")
        before = _log_bytes(txn.feature_dir)
        try:
            txn.append_event(_event("01M6QY1MLANEWRITE000000001"))
        finally:
            assert _log_bytes(txn.feature_dir) == before, "a refused write never touches the lane copy"

    assert getattr(excinfo.value, "error_code", None) == _LANE_CODE
    assert f"{_COORD_BRANCH}-lane-z" in str(excinfo.value)


def test_transaction_write_to_coord_worktree_succeeds(tmp_path: Path) -> None:
    """Positive control: the registered coordination worktree accepts the identical write."""
    repo = _repo(tmp_path)
    with _acquire(repo) as txn:
        txn.append_event(_event("01M6QY1MLANEWRITE000000002"))
        feature_dir = txn.feature_dir

    assert "01M6QY1MLANEWRITE000000002" in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert "01M6QY1MLANEWRITE000000002" in _git(repo, "show", f"{_COORD_BRANCH}:kitty-specs/{feature_dir.name}/status.events.jsonl")


def test_transaction_write_into_unregistered_coord_husk_is_structured(tmp_path: Path) -> None:
    """A husk refuses with the structured Bookkeeping error, names its remedy and writes nothing."""
    repo = _repo(tmp_path)
    husk = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
    husk.mkdir(parents=True)

    with pytest.raises(BookkeepingCommitFailed) as excinfo, _acquire(repo) as txn:
        txn.append_event(_event("01M6QY1MLANEWRITE000000003"))

    assert "spec-kitty doctor workspaces --fix" in str(excinfo.value)
    assert not any(husk.rglob("status.events.jsonl")), "nothing is written into a husk"
