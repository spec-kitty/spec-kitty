"""Crash-between-commits regression pin: FR-001 idempotent re-drive (R5 / #2702).

write-path-integrity WP04 / T021. The partition fix (WP02) commits a coord
mission's planning batch in TWO ``BookkeepingTransaction`` legs: the PRIMARY group
to the mission's target branch, then the COORD-residue group to the coordination
ref. That opens a crash window: if the process dies AFTER the PRIMARY commit but
BEFORE the COORD commit, a naive re-drive would either hard-fail (empty PRIMARY
changeset) or strand residue on the wrong partition — the #2702 shape.

FR-001 closes it with per-partition idempotent re-drive: each leg commits via
``commit_idempotent``, so re-invoking the auto-commit path re-runs BOTH legs; the
PRIMARY leg finds its staged paths byte-identical to HEAD and no-ops, and the
COORD leg commits fresh. This pin proves that recovery and guards against the
#2702 regression:

* PRIMARY (``lanes.json``) lands ONLY on the target branch — never the coord ref.
* COORD (``status.events.jsonl``) lands ONLY on the coord ref — never the target.
* The interrupted re-drive raises NO error (no empty-commit hard-fail).

The crash is simulated by failing the SECOND (coord) ``_run_planning_artifact_commit``
leg on the first run, then re-driving with the real function restored — exactly a
process death between the two partition commits.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "wp-integrity-crash-recovery-01KZZD69"
_MISSION_ID = "01KZZD69CRASHRECOVERY00000P"
_MID8 = _MISSION_ID[:8]
# A real coord + PR-bound mission targets a NON-protected feature branch, so the
# fixed PRIMARY commit is not refused by the protected-branch policy.
_TARGET_BRANCH = "pr/write-path-integrity-crash-recovery"

_PRIMARY_REL = f"kitty-specs/{_MISSION_SLUG}/lanes.json"
_COORD_REL = f"kitty-specs/{_MISSION_SLUG}/status.events.jsonl"


class _SimulatedCrash(RuntimeError):
    """Stands in for a process death between the PRIMARY and COORD commits."""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _ls_tree_paths(repo: Path, ref: str) -> set[str]:
    out = _git(repo, "ls-tree", "-r", "--name-only", ref)
    return set(out.splitlines())


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MID8,
                "mission_type": "software-dev",
                "target_branch": _TARGET_BRANCH,
                "created_at": "2026-08-14T00:00:00+00:00",
                "friendly_name": "write-path-integrity crash recovery",
                "coordination_branch": coordination_branch,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_coord_mission(tmp_path: Path) -> tuple[Path, Path, str]:
    """A real coord mission with a dirty PRIMARY (``lanes.json``) and a dirty
    COORD-residue (``status.events.jsonl``) artifact staged in the working tree.
    Returns (repo, feature_dir, coord_branch)."""
    from specify_cli.missions._create import ensure_coordination_branch

    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", _TARGET_BRANCH, "main")
    _git(repo, "checkout", "-q", _TARGET_BRANCH)

    coord_result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        target_branch=_TARGET_BRANCH,
    )
    assert coord_result.created
    coord_branch = coord_result.branch_name

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta(feature_dir, coordination_branch=coord_branch)
    # PRIMARY-partition artifact (dirty, uncommitted).
    (feature_dir / "lanes.json").write_text('{"version": 1}\n', encoding="utf-8")
    # COORD-residue artifact (dirty, uncommitted). WP07 re-pin
    # (coord-artifact-single-home-01M3V4BE): the coordination commit leg now
    # resolves through the single write-location accessor, which parses this
    # file's event_id sequence to decide what (if anything) to carry onto the
    # coordination branch on first write (contracts/seed.md) -- a line with
    # no ``event_id`` key is a malformed-event-log refusal there, not a
    # silent skip. Carries the minimal field the parser requires while
    # staying the same deliberately-minimal placeholder otherwise.
    (feature_dir / "status.events.jsonl").write_text(
        '{"event_id": "01TESTSEEDEDPLACEHOLDER01", "wp_id": "WP01", "to_lane": "claimed"}\n', encoding="utf-8"
    )
    return repo, feature_dir, coord_branch


def _commit_batch(repo: Path, feature_dir: Path, coord_branch: str) -> None:
    from specify_cli.cli.commands.implement import _commit_planning_artifacts_transaction

    _commit_planning_artifacts_transaction(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=_MISSION_SLUG,
        planning_branch=_TARGET_BRANCH,
        files_to_commit=[_PRIMARY_REL, _COORD_REL],
        commit_msg=f"chore: planning artifacts for {_MISSION_SLUG}",
        placement_ref=CommitTarget(ref=coord_branch),
    )


def test_crash_between_partition_commits_recovers_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-001 / R5 / #2702: a crash after the PRIMARY commit and before the COORD
    commit is recovered by re-invoking the auto-commit path — no stranded residue,
    no error.
    """
    import specify_cli.cli.commands.implement as im

    repo, feature_dir, coord_branch = _seed_coord_mission(tmp_path)

    # --- Simulate the crash: the PRIMARY leg (commit_to_primary_target=True) runs
    # for real; the COORD leg (commit_to_primary_target False) dies mid-flight.
    real_commit = im._run_planning_artifact_commit
    fired = {"crashed": False}

    def crashing_commit(**kwargs: object) -> None:
        if not kwargs.get("commit_to_primary_target", False):
            fired["crashed"] = True
            raise _SimulatedCrash("process died before the coord commit")
        real_commit(**kwargs)

    monkeypatch.setattr(im, "_run_planning_artifact_commit", crashing_commit)

    with pytest.raises(_SimulatedCrash):
        _commit_batch(repo, feature_dir, coord_branch)
    assert fired["crashed"], "the coord leg must have been reached and crashed"

    # --- Intermediate state after the crash: PRIMARY committed to the target
    # branch; the COORD file is NOT yet on the coord ref; and critically NO coord
    # residue was stranded onto the PRIMARY target (the PRIMARY leg carried only
    # ``lanes.json``) -- the #2702 shape is absent even mid-crash.
    assert _PRIMARY_REL in _ls_tree_paths(repo, _TARGET_BRANCH)
    assert _COORD_REL not in _ls_tree_paths(repo, _TARGET_BRANCH), (
        "coord residue stranded on the PRIMARY target branch (#2702 shape)"
    )
    assert _COORD_REL not in _ls_tree_paths(repo, coord_branch), (
        "the coord commit was supposed to have crashed before landing"
    )

    # --- Recovery: restore the real function and re-drive (re-invoke the
    # auto-commit path). The PRIMARY leg is byte-identical -> commit_idempotent
    # no-ops; the COORD leg commits fresh. No error.
    monkeypatch.setattr(im, "_run_planning_artifact_commit", real_commit)
    _commit_batch(repo, feature_dir, coord_branch)  # must NOT raise

    # --- Final state: strict partition purity, no cross-contamination.
    target_paths = _ls_tree_paths(repo, _TARGET_BRANCH)
    coord_paths = _ls_tree_paths(repo, coord_branch)

    assert _PRIMARY_REL in target_paths, "PRIMARY lanes.json must be on the target branch"
    assert _PRIMARY_REL not in coord_paths, "PRIMARY lanes.json must NEVER land on coord (#3371)"
    assert _COORD_REL in coord_paths, "COORD status.events.jsonl must be on the coord ref after recovery"
    assert _COORD_REL not in target_paths, "COORD residue must NEVER land on the target branch (#2549/#2702)"
