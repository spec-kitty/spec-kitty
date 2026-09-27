"""Contract test for the canonical-root resolver (WP03/T016, FR-013).

Pins two contracts:

1. ``resolve_canonical_root`` returns the main repo root (not the
   worktree path) when called from inside a real ``git worktree``.
2. ``emit_status_transition`` from inside a worktree appends to the
   *canonical* repo's ``status.events.jsonl``, not to a stale copy
   under the worktree.

A real ``git worktree add`` is used so the ``commondir`` parsing path
is exercised end-to-end.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.status.emit import emit_status_transition
from specify_cli.workspace.root_resolver import (
    _reset_cache,
    resolve_canonical_root,
)


pytestmark = [pytest.mark.contract, pytest.mark.git_repo]


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _bootstrap_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")
    return path.resolve()


def _bootstrap_mission(repo: Path, slug: str) -> Path:
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": slug, "target_branch": "main"}),
        encoding="utf-8",
    )
    # status.events.jsonl is created on first append; nothing to seed.
    return feature_dir


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache()
    yield
    _reset_cache()


@pytest.mark.contract
@pytest.mark.git_repo
def test_canonical_root_resolves_from_inside_worktree(tmp_path: Path) -> None:
    repo = _bootstrap_repo(tmp_path / "main")
    worktree = tmp_path / "wt-feature"
    _git(repo, "worktree", "add", "-b", "feature-branch", str(worktree))

    nested = worktree / "src" / "deep"
    nested.mkdir(parents=True)

    assert resolve_canonical_root(worktree) == repo
    assert resolve_canonical_root(nested) == repo


@pytest.mark.contract
@pytest.mark.git_repo
def test_emit_from_worktree_writes_to_canonical_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status emitted from a worktree CWD must land in the canonical repo."""
    slug = "fixture-mission"
    repo = _bootstrap_repo(tmp_path / "main")
    canonical_feature_dir = _bootstrap_mission(repo, slug)

    # Seed WP01 out of the non-display 'genesis' state into 'planned' (as
    # finalize-tasks does) so the claimed transition is legal.
    seed_event = {
        "actor": "seed",
        "at": "2026-05-31T00:00:00+00:00",
        "event_id": "01HXYZ0123456789ABCDEFGS01",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_slug": slug,
        "reason": "seed",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": "WP01",
    }
    (canonical_feature_dir / "status.events.jsonl").write_text(json.dumps(seed_event, sort_keys=True) + "\n", encoding="utf-8")

    worktree = tmp_path / "wt-feature"
    _git(repo, "worktree", "add", "-b", "feature", str(worktree))

    # Caller passes the worktree-rooted feature_dir, simulating a stale
    # path computed inside the worktree.
    worktree_feature_dir = worktree / "kitty-specs" / slug

    monkeypatch.chdir(worktree)
    emit_status_transition(
        feature_dir=worktree_feature_dir,
        mission_slug=slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="contract-test",
    )

    canonical_log = canonical_feature_dir / "status.events.jsonl"
    worktree_log = worktree_feature_dir / "status.events.jsonl"

    assert canonical_log.exists(), "canonical event log must exist"
    canonical_lines = [line for line in canonical_log.read_text(encoding="utf-8").splitlines() if line]
    # genesis->planned seed + the planned->claimed transition under test.
    assert len(canonical_lines) == 2
    payload = json.loads(canonical_lines[-1])
    assert payload["wp_id"] == "WP01"
    assert payload["to_lane"] == "claimed"

    if worktree_log.exists():
        # Permissible only if it is empty / does not contain the new event.
        worktree_lines = [line for line in worktree_log.read_text(encoding="utf-8").splitlines() if line]
        assert worktree_lines == [], "emit must not write to the stale worktree-local event log"
