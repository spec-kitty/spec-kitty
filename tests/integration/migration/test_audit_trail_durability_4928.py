"""#4928 end-to-end: the mission-state repair audit trail is durable + non-gating.

Proves the mission's success criteria against a REAL git repo (not mocks):

* SC-001 — the manifest and quarantine land under a ``git check-ignore``-clean
  path (``.kittify/mission-state-audit/``), never the legacy gitignored path.
* SC-002 — after ``git add`` + commit, a ``git clean -xfd`` leaves them on disk
  (the linchpin: on the OLD gitignored path ``git add`` is a silent no-op, so the
  operator could never commit → the trail died on clean).
* SC-005 — the tracked-but-uncommitted trail is classified self-bookkeeping
  churn, so an accept/merge dirty-tree preflight does not gate on it (#2384
  property preserved via classification, WP02).
* C-005 — the legacy ``.kittify/migrations/`` ignore stays for back-compat.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.coherence import is_self_bookkeeping_churn
from specify_cli.migration.mission_state import (
    MISSION_STATE_AUDIT_ROOT,
    repair_duplicate_key_artifacts,
    repair_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LEGACY_IGNORE = ".kittify/migrations/"

# A dual-``review_feedback``-key WP artifact (empty then real pointer) — the
# input the duplicate-key repair (the SECOND audit-trail writer) heals.
_DUAL_KEY_ARTIFACT = (
    "---\nwork_package_id: WP01\ntitle: Something\nreview_feedback: ''\nsubtasks:\n- T001\nreview_feedback: review-cycle-1.md\n---\nBody content.\n"
)


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "e2e@spec-kitty.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "e2e"], cwd=repo, check=True)
    # The legacy ignore is what a real spec-kitty project ships (C-005 back-compat).
    (repo / ".gitignore").write_text(_LEGACY_IGNORE + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True)


def _seed_quarantining_mission(repo: Path) -> Path:
    mission = repo / "kitty-specs" / "042-audit-e2e"
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "friendly_name": "Audit E2E",
                "mission": "software-dev",
                "slug": "042-audit-e2e",
                "target_branch": "main",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    row = {
        "actor": "Claude Code",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
        "execution_mode": "worktree",
        "feature_slug": "042-audit-e2e",
        "force": False,
        "from_lane": "doing",
        "legacy_aggregate_id": "feature:042-audit-e2e",
        "to_lane": "in_review",
        "work_package_id": "WP01",
    }
    duplicate = dict(row)  # duplicate event_id → one row quarantined
    (mission / "status.events.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in (row, duplicate)) + "\n",
        encoding="utf-8",
    )
    return mission


def _check_ignored(repo: Path, rel: str) -> bool:
    return subprocess.run(["git", "check-ignore", rel], cwd=repo).returncode == 0


def _porcelain(repo: Path, *paths: str) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout


def test_audit_trail_is_durable_and_non_gating_e2e(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_quarantining_mission(repo)
    _init_git_repo(repo)

    report = repair_repo(repo)
    assert report.missions[0].quarantined_rows == 1

    # --- SC-001: artifacts land under the tracked audit root, not the old path ---
    manifests = sorted((repo / MISSION_STATE_AUDIT_ROOT).glob("*.json"))
    assert manifests, "manifest must be under .kittify/mission-state-audit/"
    assert not (repo / ".kittify" / "migrations" / "mission-state").exists(), "the mission-state repair must write nothing to the legacy gitignored path"
    assert report.quarantine_root_path is not None
    quarantine_file = next((repo / report.quarantine_root_path).rglob("status.events.jsonl"))

    manifest_rel = manifests[-1].relative_to(repo).as_posix()
    quarantine_rel = quarantine_file.relative_to(repo).as_posix()
    assert not _check_ignored(repo, manifest_rel), f"{manifest_rel} must not be gitignored"
    assert not _check_ignored(repo, quarantine_rel), f"{quarantine_rel} must not be gitignored"

    # C-005: the legacy path stays ignored for back-compat.
    assert _check_ignored(repo, ".kittify/migrations/mission-state/legacy.json")

    # --- SC-002 linchpin: git add actually STAGES them (not a silent no-op) ---
    subprocess.run(["git", "add", str(MISSION_STATE_AUDIT_ROOT)], cwd=repo, check=True)
    staged = _porcelain(repo, str(MISSION_STATE_AUDIT_ROOT))
    assert manifest_rel in staged and "A " in staged, "audit trail must be stageable"

    # Commit, then a routine clean must NOT destroy the trail.
    subprocess.run(["git", "commit", "-q", "-m", "record repair audit trail"], cwd=repo, check=True)
    subprocess.run(["git", "clean", "-xfd"], cwd=repo, check=True)
    assert manifests[-1].exists(), "manifest must survive git clean once committed"
    assert quarantine_file.exists(), "quarantine must survive git clean once committed"

    # --- SC-005: the trail is self-bookkeeping churn → accept/merge not gated ---
    assert is_self_bookkeeping_churn(manifest_rel), "manifest must be churn (accept not gated)"
    assert is_self_bookkeeping_churn(quarantine_rel), "quarantine must be churn (accept not gated)"


def test_second_repair_not_blocked_by_committed_or_uncommitted_trail_e2e(tmp_path: Path) -> None:
    """The self-block fix (WP01/FR-009) holds end-to-end: a prior run's audit
    trail (tracked, whether committed or not) never makes the next --fix refuse."""
    repo = tmp_path
    _seed_quarantining_mission(repo)
    _init_git_repo(repo)

    repair_repo(repo)  # run 1: canonicalizes + writes the trail
    # Commit only the mission; leave the audit trail tracked-but-uncommitted.
    subprocess.run(["git", "add", "kitty-specs"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "canonicalized"], cwd=repo, check=True)
    assert _porcelain(repo, str(MISSION_STATE_AUDIT_ROOT)).strip(), "precondition: trail uncommitted"

    # run 2 must not raise on its own uncommitted output.
    report = repair_repo(repo)
    assert report.missions[0].status == "unchanged"


def test_dup_key_repair_manifest_is_durable_and_non_gating_e2e(tmp_path: Path) -> None:
    """FR-006: the SECOND writer — the duplicate-key repair — relocates on the
    same terms. Its ``dup-key-<run>.json`` manifest is tracked, stageable,
    survives ``git clean``, and is self-bookkeeping churn (accept not gated)."""
    repo = tmp_path
    scan_dir = repo / "kitty-specs"
    artifact = scan_dir / "mission-a" / "tasks" / "WP.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(_DUAL_KEY_ARTIFACT, encoding="utf-8")
    _init_git_repo(repo)  # commits the baseline including the dual-key artifact

    # allow_dirty: healing the artifact dirties the tree; the audit root itself
    # is (correctly) NOT in the _assert_git_safe checked set (FR-009).
    report = repair_duplicate_key_artifacts(repo, scan_root=scan_dir, allow_dirty=True)
    assert sum(len(m.file_changes) for m in report.missions) == 1

    manifests = sorted((repo / MISSION_STATE_AUDIT_ROOT).glob("dup-key-*.json"))
    assert manifests, "dup-key manifest must be under .kittify/mission-state-audit/"
    assert not (repo / ".kittify" / "migrations").exists(), "the dup-key repair must write nothing to the legacy gitignored path"
    manifest_rel = manifests[-1].relative_to(repo).as_posix()

    # SC-001: check-ignore clean.
    assert not _check_ignored(repo, manifest_rel), f"{manifest_rel} must not be gitignored"
    # SC-002 linchpin: git add STAGES it; survives clean after commit.
    subprocess.run(["git", "add", str(MISSION_STATE_AUDIT_ROOT)], cwd=repo, check=True)
    assert manifest_rel in _porcelain(repo, str(MISSION_STATE_AUDIT_ROOT)), "must be stageable"
    subprocess.run(["git", "commit", "-q", "-m", "record dup-key audit trail"], cwd=repo, check=True)
    subprocess.run(["git", "clean", "-xfd"], cwd=repo, check=True)
    assert manifests[-1].exists(), "dup-key manifest must survive git clean once committed"
    # SC-005: churn-classified → accept/merge not gated.
    assert is_self_bookkeeping_churn(manifest_rel), "dup-key manifest must be churn"
