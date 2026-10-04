"""WP03 / FR-002 (#2085): accept-gate multi-site read split — two-surface proof.

The accept gate (``collect_feature_summary``) reads ~9 artifacts off a per-mission
read dir. WP01 placed the PLANNING-kind artifacts (spec/plan/tasks/research/
data-model) on the PRIMARY surface for both read and write; the STATUS-kind reads
(``status.events.jsonl``, acceptance-matrix) stay on the COORDINATION surface for a
coord-topology mission (C-001 append-only event log lives on coord).

These tests pin the per-partition split in ONE coord-topology fixture and are
deliberately NON-FAKEABLE / anti-mutant (NFR-004):

* ``test_planning_reads_resolve_primary`` — planting the planning docs ONLY on
  PRIMARY and asserting ``missing_artifacts == []`` proves the gate read PRIMARY.
  PRE-WP03 the gate read those docs off the coord-aware ``status_feature_dir``;
  with the docs absent from coord it mis-blocked them as missing (RED — see
  ``test_pre_fix_planning_off_coord_mis_blocks`` for the witnessed precondition).
  Reverting any planning read to ``status_feature_dir`` turns this assertion RED.
* ``test_status_read_resolves_coord`` — planting the status event log ONLY on the
  COORD surface and asserting the gate does NOT raise the "no canonical state"
  activity issue proves the STATUS read still resolved COORD. Redirecting the
  status read to the primary dir (where no event log exists) turns this RED.

Both assertions hold on the SAME fixture, so the pair kills both the "always
coord" and the "always primary" mutant. Identity is production-shaped: a real
26-char Crockford ULID and the on-disk ``<slug>-<mid8>`` layout (NFR-002/NFR-005).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.acceptance import (
    AcceptanceError,
    AcceptanceSummary,
    _accept_planning_artifact_kinds,
    _planning_read_dir,
    collect_feature_summary,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_PLANNING_READ_DIR_QUARANTINE = pytest.mark.quarantine(
    reason="spec-kitty#1021: flakes under the full parallel main baseline"
    " (first seen in baseline @a7b8bd306 2026-09-01T10:32Z; recurred in PR"
    " runs @8725b44f 2026-09-01T12:10Z and @4b9f767d 2026-09-01T12:46Z);"
    " passes on the serial re-run and in isolation each time. Root cause"
    " (cross-test nondeterminism reached by -n auto scheduling) is tracked"
    " in the issue; this quarantine is debt, remove on root-cause fix."
)

# Production-shaped identity: a full 26-char Crockford-base32 ULID, uppercase
# mid8, and the canonical on-disk ``<slug>-<mid8>`` layout. The operator HANDLE is
# the composed ``<slug>-<mid8>`` (a bare-slug fixture would false-green because the
# resolver could coincidentally land on primary for the wrong reason).
_MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"
_MID8 = _MISSION_ID[:8]  # "01KVW9B0"
_SLUG = "gate-read-surface-completion"
_HANDLE = f"{_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_SLUG}-{_MID8}"

_PLANNING_FILES = ("spec.md", "plan.md", "tasks.md", "research.md", "data-model.md")

_STATUS_EVENT = {
    "actor": "claude",
    "at": "2026-06-24T12:00:00+00:00",
    "event_id": "01KVW9B0XFXPKTBE77QT3KRSWZ",
    "evidence": None,
    "execution_mode": "worktree",
    "feature_slug": _HANDLE,
    "force": False,
    "from_lane": "genesis",
    "reason": None,
    "review_ref": None,
    "to_lane": "planned",
    "wp_id": "WP01",
}


def _write_meta(feature_dir: Path, *, coord: bool) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": _HANDLE,
        "mission_type": "software-dev",
    }
    if coord:
        meta["coordination_branch"] = _COORD_BRANCH
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _plant_planning(feature_dir: Path) -> None:
    """Write substantive planning docs (no NEEDS CLARIFICATION markers)."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    for name in _PLANNING_FILES:
        (feature_dir / name).write_text(f"# {name}\n\nContent.\n", encoding="utf-8")


def _plant_status_events(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_STATUS_EVENT) + "\n", encoding="utf-8"
    )


def _plant_wp_tasks(feature_dir: Path) -> None:
    """Plant a minimal WP task file so ``_iter_work_packages`` can run.

    The WP-task read (``WORK_PACKAGE_TASK`` kind) is a PRIMARY-partition kind, so
    a production-shaped coord mission carries its WP tasks ONLY on PRIMARY (INV-5
    write/read symmetry). The closeout fix routes ``_iter_work_packages`` through
    the kind-aware seam onto PRIMARY; we plant the WP task on the PRIMARY surface
    so the gate genuinely exercises that primary read. (Pre-closeout this was
    planted on COORD too, masking the real gate's "no tasks directory" break.)
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-sample.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Sample\n"
        "agent: claude\n"
        "assignee: claude\n"
        "shell_pid: '1'\n"
        "---\n\n# WP01\n",
        encoding="utf-8",
    )


def _build_coord_topology(
    repo_root: Path, *, planning_on: str, events_on: str
) -> tuple[Path, Path]:
    """Build a coord-topology mission with split planning / status surfaces.

    ``planning_on`` / ``events_on`` ∈ {"primary", "coord"} decide which surface
    carries the planning docs and the status event log respectively. Returns
    ``(primary_feature_dir, coord_feature_dir)``.
    """
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo_root, check=True)

    primary_feature_dir = repo_root / "kitty-specs" / _HANDLE
    _write_meta(primary_feature_dir, coord=True)

    coord_root = CoordinationWorkspace.worktree_path(repo_root, _SLUG, _MID8)
    coord_feature_dir = coord_root / "kitty-specs" / _HANDLE
    _write_meta(coord_feature_dir, coord=True)

    surfaces = {"primary": primary_feature_dir, "coord": coord_feature_dir}
    _plant_planning(surfaces[planning_on])
    _plant_status_events(surfaces[events_on])
    # WORK_PACKAGE_TASK is a PRIMARY-partition kind: a real coord mission carries
    # WP tasks ONLY on primary. Plant them there so the gate's WP-task iteration
    # genuinely exercises the PRIMARY read (closeout N+1 de-mask — planting on
    # coord masked the real "no tasks directory" break).
    _plant_wp_tasks(primary_feature_dir)

    # The coord branch must exist so the topology classifies as coord (not a stale
    # husk) — mirror the canonical coord fixture.
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "branch", _COORD_BRANCH],
        cwd=repo_root,
        check=True,
    )
    return primary_feature_dir, coord_feature_dir


def _summary(repo_root: Path) -> AcceptanceSummary:
    return collect_feature_summary(
        repo_root, _HANDLE, strict_metadata=False, mutate_matrix=False
    )


def test_planning_reads_resolve_primary(tmp_path: Path) -> None:
    """Planning docs on PRIMARY only → the gate finds them (reads primary)."""
    _build_coord_topology(tmp_path, planning_on="primary", events_on="coord")

    summary = _summary(tmp_path)

    # FR-002: the required planning artifacts (spec/plan/tasks) resolve on the
    # PRIMARY surface and are NOT mis-reported as missing. Reverting any planning
    # read to ``status_feature_dir`` (coord) turns this assertion RED.
    assert summary.missing_artifacts == [], (
        "Accept gate mis-blocked planning artifacts as missing — it read the "
        "coord surface instead of primary (planning-read split regressed)."
    )


def test_status_read_resolves_coord(tmp_path: Path) -> None:
    """Status event log on COORD only → the gate consults it (reads coord)."""
    _build_coord_topology(tmp_path, planning_on="primary", events_on="coord")

    summary = _summary(tmp_path)

    # C-002: the STATUS read (status.events.jsonl) still resolves the COORD
    # surface. If it were redirected to primary (no event log there),
    # ``_collect_snapshot_wps`` would append the "No canonical state found"
    # activity issue. Asserting that message is ABSENT proves the coord read.
    no_canonical_state = [
        issue for issue in summary.activity_issues if "No canonical state found" in issue
    ]
    assert no_canonical_state == [], (
        "Accept gate lost the status event log — it read the primary surface "
        "instead of coord (status-read split regressed; C-002 violated)."
    )


def test_pre_fix_planning_off_coord_mis_blocks(tmp_path: Path) -> None:
    """Witness the PRE-WP03 bug: planning on coord, primary bare → mis-block.

    This documents the precondition the fix removes. With planning docs on the
    COORD surface and the PRIMARY surface bare, the PRE-fix gate (reading planning
    off ``status_feature_dir`` = coord) would PASS, while the fixed gate (reading
    primary) correctly reports them missing. The post-fix run therefore SEES them
    missing — proving the read moved to primary, not coord.
    """
    _build_coord_topology(tmp_path, planning_on="coord", events_on="coord")

    summary = _summary(tmp_path)

    # Post-fix the gate reads PRIMARY (bare here) → spec/plan/tasks are missing.
    # A gate still reading coord would report ZERO missing (false-green) — so a
    # non-empty missing list here is the anti-mutant proof that the read moved.
    assert {"spec.md", "plan.md", "tasks.md"}.issubset(set(summary.missing_artifacts)), (
        "Post-fix gate did NOT read primary for planning artifacts (it still "
        "found them on coord) — the planning-read split did not take effect."
    )


def test_flattened_topology_planning_and_status_resolve(tmp_path: Path) -> None:
    """NFR-001 regression: a FLATTENED mission (no coord) resolves on primary.

    With no ``coordination_branch`` both partitions resolve the primary feature
    dir, so planting BOTH planning docs and the status event log on primary must
    leave the gate with no missing-artifact and no missing-state issue.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    primary_feature_dir = tmp_path / "kitty-specs" / _HANDLE
    _write_meta(primary_feature_dir, coord=False)
    _plant_planning(primary_feature_dir)
    _plant_status_events(primary_feature_dir)
    _plant_wp_tasks(primary_feature_dir)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=tmp_path, check=True
    )

    summary = _summary(tmp_path)

    assert summary.missing_artifacts == []
    assert not [
        issue for issue in summary.activity_issues if "No canonical state found" in issue
    ]


def test_all_planning_kinds_are_primary_partition() -> None:
    """Invariant: every accept-gate planning artifact is a PRIMARY-partition kind.

    The "resolve once, reuse" optimisation in ``_planning_read_dir`` is only valid
    while ALL the read planning kinds share the primary partition. This pins that
    precondition directly (NFR-004) so a future cross-partition reclassification in
    ``mission_runtime.artifacts`` is caught by THIS test, not by a silent stale read.
    """
    from mission_runtime import is_primary_artifact_kind, kind_for_mission_file

    kinds = _accept_planning_artifact_kinds()
    assert set(kinds) == {
        "spec.md",
        "plan.md",
        "tasks.md",
        "research.md",
        "data-model.md",
        "quickstart.md",
    }
    assert all(is_primary_artifact_kind(kind) for kind in kinds.values())
    # The accept map and the shared file classifier are two hand-kept tables; they must agree.
    for name, kind in kinds.items():
        assert kind_for_mission_file(f"kitty-specs/{_SLUG}/{name}") is kind, name


@_PLANNING_READ_DIR_QUARANTINE
def test_planning_read_dir_raises_when_kind_leaves_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard branch fails LOUD when a planning kind leaves the primary partition.

    Simulating ``is_primary_artifact_kind`` returning False for the gate's planning
    kinds must raise ``AcceptanceError`` rather than silently resolving a coord
    surface for one artifact (FR-002 split-integrity guard).
    """
    import mission_runtime

    monkeypatch.setattr(mission_runtime, "is_primary_artifact_kind", lambda _kind: False)

    with pytest.raises(AcceptanceError, match="planning split invariant violated"):
        _planning_read_dir(Path("/nonexistent-repo"), _HANDLE)
