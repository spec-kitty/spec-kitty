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
from types import SimpleNamespace

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
    """Pin the placement to COORD_REF and the read dir to ``<repo>/kitty-specs/<mission>``."""
    monkeypatch.setattr(done_bookkeeping, "resolve_placement_only", lambda *_a, **_k: SimpleNamespace(ref=COORD_REF))
    monkeypatch.setattr(
        done_bookkeeping,
        "placement_seam",
        lambda repo_root, slug, **_k: SimpleNamespace(read_dir=lambda _kind: repo_root / "kitty-specs" / slug),
    )


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
