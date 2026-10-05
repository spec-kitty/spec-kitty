"""Regression tests for #2222 — vcs-lock claim-friction (WP02).

Back-to-back dependency-free root claims under ``auto_commit=False`` were wrongly
blocked: the FIRST claim's one-time vcs-lock self-write to ``meta.json`` (via
``mission_metadata.set_vcs_lock``) left the working tree dirty, so the SECOND
claim's dirty-tree guard (``_ensure_planning_artifacts_committed_git``) aborted
with ``Exit(1)`` citing uncommitted planning artifacts.

The fix excludes a *lock-field-only* ``meta.json`` change from the dirty-tree
guard under ``auto_commit=False`` (operator decision: STOP-GATING, not
auto-committing — the lock is VCS-TYPE state, never the concurrency mutex, so
the exclusion opens no race). The default ``auto_commit=True`` path is unchanged
(NFR-001), and a ``meta.json`` dirtied with any NON-lock field still blocks
(the exclusion is strictly lock-field-only, not a blanket meta.json bypass).

The guard tests call the planning-artifact commit phase of the claim
(``implement_phases.commit_planning_artifacts``) directly against a real git
repository, so the REAL guard runs and nothing in the implement command family
is patched; the first claim's residue is established by the production writer
``set_vcs_lock`` (the exact bytes the first claim leaves), which isolates the
variable under test from unrelated first-claim side effects.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from kernel.vcs_lock import is_vcs_lock_only_change
from specify_cli.cli.commands import implement_phases
from specify_cli.cli.commands.implement_phases import ClaimPreflight, ImplementContext
from specify_cli.cli.commands.implement_cores import _is_self_write_only_diff, resolve_planning_artifact_staging
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.mission_metadata import set_vcs_lock

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_SLUG = "vcs-lock-claim-demo"
_LOCKED_AT = "2026-06-27T08:30:00+00:00"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_out(repo_root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": feature_dir.name,
                "slug": feature_dir.name,
                "friendly_name": feature_dir.name,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-06-27T00:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_lanes(feature_dir: Path) -> None:
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=feature_dir.name,
            mission_id=f"mission-{feature_dir.name}",
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/a/**",),
                    predicted_surfaces=("runtime",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
                ExecutionLane(
                    lane_id="lane-b",
                    wp_ids=("WP02",),
                    write_scope=("src/b/**",),
                    predicted_surfaces=("runtime",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
            ],
            computed_at="2026-06-27T00:00:00Z",
            computed_from="test",
        ),
    )


def _write_wp(tasks_dir: Path, wp_id: str, owned_glob: str) -> None:
    (tasks_dir / f"{wp_id}-plan.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} root work\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        f"  - {owned_glob}\n"
        f"authoritative_surface: {owned_glob.rstrip('*')}\n"
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )


def _seed_event(mission_slug: str, wp_id: str, event_suffix: str) -> dict[str, Any]:
    return {
        "actor": "seed",
        "at": "2026-06-27T00:00:00+00:00",
        "event_id": f"01HXYZ0123456789ABCDEFG{event_suffix}",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_slug": mission_slug,
        "reason": "seed",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": wp_id,
    }


def _build_mission_repo(tmp_path: Path) -> Path:
    """Seed a realistic two-root-WP mission in a real git repo, committed on
    ``main``. Both WP01 (lane-a) and WP02 (lane-b) are dependency-free roots
    seeded into ``planned`` (as ``finalize-tasks`` does)."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_meta(feature_dir)
    _write_lanes(feature_dir)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\nDeliver two independent root work packages.\n",
        encoding="utf-8",
    )
    _write_wp(tasks_dir, "WP01", "src/a/**")
    _write_wp(tasks_dir, "WP02", "src/b/**")
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_seed_event(_MISSION_SLUG, "WP01", "S01"), sort_keys=True) + "\n" + json.dumps(_seed_event(_MISSION_SLUG, "WP02", "S02"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test Runner")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed mission")
    return feature_dir


def _planning_commit_phase(tmp_path: Path, feature_dir: Path, wp_id: str) -> None:
    """Run the REAL planning-artifact commit phase (the dirty-tree guard) for an
    ``auto_commit=False`` claim of *wp_id*, with real phase values.

    A claim the guard BLOCKS raises ``typer.Exit(1)`` here and never reaches the
    workspace allocation that follows this phase in ``implement``; a claim the
    guard PASSES returns normally.
    """
    ctx = ImplementContext(
        repo_root=tmp_path,
        auto_commit=False,
        mission_slug=feature_dir.name,
        feature_dir=feature_dir,
        wp_file=feature_dir / "tasks" / f"{wp_id}-plan.md",
        declared_deps=[],
    )
    preflight = ClaimPreflight(planning_branch="main", status_feature_dir=feature_dir, lanes_feature_dir=feature_dir)
    implement_phases.commit_planning_artifacts(ctx, wp_id, preflight)


def test_second_auto_commit_false_claim_not_blocked_by_lock_self_write(tmp_path: Path) -> None:
    """#2222 core: after the first claim's uncommitted vcs-lock self-write to
    meta.json, the second dependency-free ``auto_commit=False`` claim must NOT
    be blocked by the dirty-tree guard.

    RED pre-fix: the guard aborts the planning-commit phase with ``typer.Exit(1)``
    citing uncommitted planning artifacts.
    GREEN post-fix: the phase returns, so the claim proceeds to allocation.
    """
    feature_dir = _build_mission_repo(tmp_path)
    # The first claim's exact production residue: a one-time vcs-lock written to
    # meta.json and left uncommitted in the working tree.
    set_vcs_lock(feature_dir, vcs_type="git", locked_at=_LOCKED_AT)
    head = _git_out(tmp_path, "rev-parse", "HEAD")

    _planning_commit_phase(tmp_path, feature_dir, "WP02")

    # auto_commit=False: the guard passed without committing anything.
    assert _git_out(tmp_path, "rev-parse", "HEAD") == head


def test_non_lock_dirty_meta_still_blocks_auto_commit_false_claim(tmp_path: Path) -> None:
    """Required negative guard: a meta.json dirtied with a NON-lock field (here
    alongside the lock fields) still aborts the ``auto_commit=False`` claim — the
    exclusion is strictly lock-field-only, never a blanket meta.json bypass."""
    feature_dir = _build_mission_repo(tmp_path)
    set_vcs_lock(feature_dir, vcs_type="git", locked_at=_LOCKED_AT)
    # Dirty a genuine, non-lock planning field on top of the lock write.
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["purpose_tldr"] = "operator changed the mission purpose; must still block"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    with pytest.raises(typer.Exit) as exc_info:
        _planning_commit_phase(tmp_path, feature_dir, "WP02")

    assert exc_info.value.exit_code == 1


def test_drop_helper_is_noop_under_auto_commit_true(tmp_path: Path) -> None:
    """NFR-001: under ``auto_commit=True`` the exclusion is a byte-identical
    no-op — the meta.json path stays in the staging plan's commit set even
    when its only diff is the vcs-lock fields, so the default path's commit
    semantics are unchanged.

    WP14 / IC-07d: the ``auto_commit`` gate moved from the retired
    ``_drop_vcs_lock_only_meta`` helper itself to its caller
    (:func:`resolve_planning_artifact_staging` applies :func:`_drop_if` only
    when ``not auto_commit``), so this is now exercised at the staging-plan
    level rather than the bare predicate.
    """
    feature_dir = _build_mission_repo(tmp_path)
    set_vcs_lock(feature_dir, vcs_type="git", locked_at=_LOCKED_AT)
    meta_rel = (feature_dir / "meta.json").relative_to(tmp_path).as_posix()

    plan = resolve_planning_artifact_staging(tmp_path, feature_dir, None, [], auto_commit=True)

    assert meta_rel in plan.files_to_commit


def test_drop_helper_excludes_lock_only_meta_under_auto_commit_false(
    tmp_path: Path,
) -> None:
    """Under ``auto_commit=False`` a lock-only meta.json diff is dropped while a
    sibling non-meta planning edit is preserved."""
    feature_dir = _build_mission_repo(tmp_path)
    set_vcs_lock(feature_dir, vcs_type="git", locked_at=_LOCKED_AT)
    meta_rel = (feature_dir / "meta.json").relative_to(tmp_path).as_posix()
    spec_rel = (feature_dir / "spec.md").relative_to(tmp_path).as_posix()

    kept = [p for p in (meta_rel, spec_rel) if not _is_self_write_only_diff(tmp_path, p, None)]

    assert kept == [spec_rel]


def test_drop_helper_keeps_non_lock_dirty_meta_under_auto_commit_false(
    tmp_path: Path,
) -> None:
    """A meta.json carrying a non-lock change is NOT dropped under
    ``auto_commit=False`` — the guard must still see (and block on) it."""
    feature_dir = _build_mission_repo(tmp_path)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = _LOCKED_AT
    meta["friendly_name"] = "renamed-by-operator"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta_rel = meta_path.relative_to(tmp_path).as_posix()

    assert _is_self_write_only_diff(tmp_path, meta_rel, None) is False


@pytest.mark.parametrize(
    ("committed", "working", "expected"),
    [
        # Pure lock-field additions vs the committed baseline -> lock-only.
        ({"slug": "m"}, {"slug": "m", "vcs": "git", "vcs_locked_at": _LOCKED_AT}, True),
        # A lock-field value flip is still lock-only.
        ({"vcs": "hg"}, {"vcs": "git"}, True),
        # Committed baseline absent (brand-new meta) with only a lock field.
        (None, {"vcs": "git"}, True),
        # A non-lock key changed alongside the lock -> NOT lock-only.
        (
            {"slug": "m"},
            {"slug": "m2", "vcs": "git", "vcs_locked_at": _LOCKED_AT},
            False,
        ),
        # No diff at all -> the kernel comparator treats the empty difference
        # set as trivially lock-only (True), unlike the retired predicate's
        # ``bool(changed_keys)`` guard (WP03 / T016 -- FR-006 semantics shift).
        ({"vcs": "git"}, {"vcs": "git"}, True),
        # Only a non-lock change -> NOT lock-only.
        ({"slug": "m"}, {"slug": "m", "purpose_tldr": "x"}, False),
        # Removing a non-lock null-valued key is still a dirty meta change.
        (
            {"mission_number": None},
            {"vcs": "git", "vcs_locked_at": _LOCKED_AT},
            False,
        ),
        # Adding a non-lock null-valued key is still a dirty meta change.
        (
            {"vcs": "git", "vcs_locked_at": _LOCKED_AT},
            {"vcs": "git", "vcs_locked_at": _LOCKED_AT, "mission_number": None},
            False,
        ),
    ],
)
def test_is_vcs_lock_only_change_truth_table(
    committed: dict[str, Any] | None,
    working: dict[str, Any],
    expected: bool,
) -> None:
    """WP03 / T016: the retired ``_is_vcs_lock_only_meta_diff`` comparator is
    routed onto the single canonical
    :func:`kernel.vcs_lock.is_vcs_lock_only_change` (FR-006). It distinguishes a
    lock-field-only diff from every diff that touches a non-lock key
    (absent != present-but-null, C-005); an EMPTY diff is trivially lock-only
    (``True``) under the kernel comparator."""
    assert is_vcs_lock_only_change(committed, working) is expected
