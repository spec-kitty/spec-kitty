"""#4955: the mission→target squash seam must reconcile a both-sides-divergent
derived ``status.json`` (regenerate from the union-merged event log) instead of
failing closed.

Once #4892 dropped ``-X theirs``, the squash correctly fails closed on genuine
conflicts — but ``status.json`` (a derived reduced snapshot with no merge driver)
began BLOCKING legitimate integrations whenever it diverged on both sides, even
though the event log union-merges cleanly. The fix regenerates the snapshot from
the merged log at the seam. A genuine (non-derived) both-sides conflict still
fails closed.

Scope note: this mission fixes the ``status.json`` reconciliation on the squash
seam. Union drivers for the OTHER driver-less append-only logs
(``mission-events.jsonl``, ``kitty-ops/lifecycle.jsonl``) and the
``decisions/index.json`` re-fold — which require new governed MissionArtifactKind
classification and a C-006 completeness-guard decision — are deferred to the
dedicated design pass #4955 itself calls for.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.merge import preview_mission_target_integration
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "squash-seam-4955"
_EVENT_LOG_GITATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitattributes").write_text(_EVENT_LOG_GITATTRIBUTES_ENTRY + "\n", encoding="utf-8")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_event(feature_dir: Path, *, event_id: str, wp_id: str, at: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(
            {
                "event_id": event_id,
                "mission_slug": MISSION_SLUG,
                "wp_id": wp_id,
                "from_lane": "genesis",
                "to_lane": "planned",
                "at": at,
                "actor": "seed",
                "force": False,
                "execution_mode": "worktree",
                "reason": None,
                "review_ref": None,
                "evidence": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_snapshot(feature_dir: Path, marker: str) -> None:
    (feature_dir / "status.json").write_text(json.dumps({"stale_side": marker}) + "\n", encoding="utf-8")


def _use_venv_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))


def _setup(tmp_path: Path, *, human_conflict: bool) -> Path:
    """Target (main) and a source branch both ADD divergent status.json +
    union-able status.events.jsonl (add/add from a common seed). Returns repo."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    source_branch = f"kitty/mission-{MISSION_SLUG}"
    _git(repo, "branch", source_branch)

    # Source side adds its own mission bookkeeping.
    _git(repo, "checkout", "-q", source_branch)
    _write_event(feature_dir, event_id="01EVTSOURCE0000000000000AA", wp_id="WP01", at="2026-08-22T09:00:00Z")
    _write_snapshot(feature_dir, "source")
    if human_conflict:
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("SOURCE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "source: events + snapshot")

    # Target side (main) independently adds the SAME paths with different content.
    _git(repo, "checkout", "-q", "main")
    _write_event(feature_dir, event_id="01EVTTARGET0000000000000BB", wp_id="WP02", at="2026-08-22T08:00:00Z")
    _write_snapshot(feature_dir, "target")
    if human_conflict:
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("TARGET = 2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "target: events + snapshot")
    return repo


def test_divergent_status_json_does_not_block_squash_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _setup(tmp_path, human_conflict=False)
    _use_venv_on_path(monkeypatch)

    preview = preview_mission_target_integration(repo, f"kitty/mission-{MISSION_SLUG}", "main", strategy=MergeStrategy.SQUASH)

    # Pre-fix: status.json appears in conflicting_paths. Post-fix: reconciled, so
    # the preview reports no blocking conflict.
    assert preview.conflicting_paths == ()


def test_human_authored_conflict_still_blocks_squash_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _setup(tmp_path, human_conflict=True)
    _use_venv_on_path(monkeypatch)

    preview = preview_mission_target_integration(repo, f"kitty/mission-{MISSION_SLUG}", "main", strategy=MergeStrategy.SQUASH)

    # A genuine both-sides conflict on a non-derived file must still block —
    # the derived-snapshot regeneration must not green-wash it. When a real
    # conflict coexists, the reconciler refuses to partially resolve (all-or-
    # nothing), so the whole merge fails closed with the genuine conflict named.
    assert any("src/app.py" in p for p in preview.conflicting_paths)
