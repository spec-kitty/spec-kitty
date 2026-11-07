"""``_durable_coordination_lanes`` has a declared ref-missing arm (FR-004, WP04 review cycle 2).

The resume reconciliation reads the COMMITTED coordination ref. When that ref does not exist
(a non-coord topology, a legacy Mission, a torn-down branch) or ``repo_root`` is not a git
repository at all, the function returns ``None`` and the caller falls back to the transactional
on-disk check, as its docstring promises. A ref that exists but cannot be read still raises
``StatusSurfaceRefUnreadable``: it is never read as genesis and never swallowed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import done_bookkeeping
from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable

pytestmark = [pytest.mark.git_repo]

MISSION = "durable-arm-01KXDURA"
COORD_REF = f"refs/heads/kitty/mission-{MISSION}"
LOG_PATH = f"kitty-specs/{MISSION}/status.events.jsonl"

_EVENT = {
    "actor": "durable-arm",
    "at": "2026-11-06T00:00:00+00:00",
    "event_id": "01KXDURA0000000000000000001",
    "evidence": None,
    "execution_mode": "worktree",
    "feature_slug": MISSION,
    "force": False,
    "from_lane": "approved",
    "reason": None,
    "review_ref": None,
    "to_lane": "done",
    "wp_id": "WP01",
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(root: Path) -> Path:
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "durable@example.invalid")
    _git(root, "config", "user.name", "Durable")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("durable arm\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "root")
    return root


@pytest.fixture()
def pinned_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the door's committed-ref entry to COORD_REF and the Mission dir ``kitty-specs/<mission>``.

    The entry's own declared arm is kept: a ref that names no object (or no repository) is ``None``.
    """
    from mission_runtime import MissionTopology
    from specify_cli.coordination.status_service import ref_names_object
    from specify_cli.status import read_surface
    import specify_cli.status as _status_pkg  # #7276: callers import the read door from the package

    def _committed(repo_root: Path, mission: str) -> read_surface.StatusReadSurface | None:
        if not ref_names_object(repo_root, COORD_REF):
            return None
        return read_surface.StatusReadSurface(
            topology=MissionTopology.LANES_WITH_COORD,
            source=read_surface.StatusReadSource.COORD_BRANCH_REF,
            mission_dir_name=mission,
            path=None,
            repo_root=repo_root,
            ref=COORD_REF,
        )

    monkeypatch.setattr(_status_pkg, "resolve_committed_status_read", _committed)


def _lanes(repo_root: Path) -> dict[str, str] | None:
    return done_bookkeeping._durable_coordination_lanes(repo_root=repo_root, mission_slug=MISSION, candidate_wps=["WP01", "WP02"])


@pytest.mark.usefixtures("pinned_placement")
def test_missing_coordination_ref_returns_none(tmp_path: Path) -> None:
    """A repository without the coordination ref takes the declared arm: ``None`` (on-disk fallback)."""
    repo = _init_repo(tmp_path / "repo")

    assert _lanes(repo) is None


@pytest.mark.usefixtures("pinned_placement")
def test_non_repository_root_returns_none(tmp_path: Path) -> None:
    """A ``repo_root`` that is not a git repository has no ref, so it takes the same arm."""
    assert _lanes(tmp_path) is None


@pytest.mark.usefixtures("pinned_placement")
def test_existing_but_unreadable_ref_raises(tmp_path: Path) -> None:
    """A ref that exists but points at an object the repository lacks raises, never falls back."""
    repo = _init_repo(tmp_path / "repo")
    corrupt = repo / ".git" / "refs" / "heads" / "kitty" / f"mission-{MISSION}"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")

    with pytest.raises(StatusSurfaceRefUnreadable):
        _lanes(repo)


@pytest.mark.usefixtures("pinned_placement")
def test_readable_ref_returns_committed_lanes(tmp_path: Path) -> None:
    """Positive control: a readable ref reduces each candidate to its committed lane."""
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "checkout", "-q", "-b", f"kitty/mission-{MISSION}")
    log = repo / LOG_PATH
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(_EVENT, sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "coordination log")
    _git(repo, "checkout", "-q", "main")

    lanes = _lanes(repo)

    assert lanes is not None
    assert lanes["WP01"] == "done"
