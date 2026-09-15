"""Regression tests for acceptance pipeline fixes (feature 052).

Each test targets exactly one of the 4 regressions fixed in WP01-WP03:
- T012: materialize() no longer dirties the repo during verification
- T013: perform_acceptance() persists accept_commit SHA to meta.json
- T014: standalone tasks_cli.py --help works via subprocess
- T015: malformed JSONL raises AcceptanceError, not StoreError
- T016: acceptance.py and acceptance_support.py stay API-aligned
"""

from __future__ import annotations

import json
import re
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import Tuple

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.acceptance import (
    AcceptanceError,
    AcceptanceSummary,
    acceptance_lane_derivations,
    collect_feature_summary,
    perform_acceptance,
)
from specify_cli.task_utils import LANES
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.store import StoreError, append_annotations_atomic_verified, append_event
from specify_cli.cli.commands import accept as accept_module

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: subprocess CLI invocation
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Shared test helper
# ---------------------------------------------------------------------------

_FEATURE_SLUG = "099-test-feature"


def _summary_with_lanes(tmp_path: Path, lanes: dict[str, list[str]]) -> AcceptanceSummary:
    full_lanes = {lane: list(lanes.get(lane, [])) for lane in LANES}
    return AcceptanceSummary(
        feature=_FEATURE_SLUG,
        repo_root=tmp_path,
        feature_dir=tmp_path,
        tasks_dir=tmp_path,
        branch="test",
        worktree_root=tmp_path,
        primary_repo_root=tmp_path,
        lanes=full_lanes,
        work_packages=[],
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
    )


def _summary_with_states(
    tmp_path: Path,
    lanes: dict[str, list[str]],
    *,
    provenance: dict[str, bool] | None = None,
) -> AcceptanceSummary:
    """Like :func:`_summary_with_lanes`, but carries per-WP operator provenance.

    WP06 / T023: the provenance-free ``_summary_with_lanes`` builds no
    ``work_packages``, so every ``canceled`` WP reads as synthetic. This variant
    materializes a :class:`WorkPackageState` per WP with the operator-provenance
    flag, exercising the command-level acceptable-ending decision (FR-001/FR-003)
    that ``AcceptanceSummary`` makes per-WP.
    """
    from specify_cli.acceptance.summary_core import WorkPackageState

    provenance = provenance or {}
    full_lanes = {lane: list(lanes.get(lane, [])) for lane in LANES}
    work_packages = [
        WorkPackageState(
            work_package_id=wp_id,
            lane=lane,
            title=wp_id,
            path=f"tasks/{wp_id}.md",
            has_lane_entry=True,
            latest_lane=lane,
            metadata={"agent": "test-agent"},
            has_operator_provenance=provenance.get(wp_id, False),
        )
        for lane, wp_ids in full_lanes.items()
        for wp_id in wp_ids
    ]
    summary = _summary_with_lanes(tmp_path, lanes)
    object.__setattr__(summary, "work_packages", work_packages)
    return summary


def test_approved_plus_operator_cancellation_is_eligible(tmp_path: Path) -> None:
    """T023: approved + operator-canceled -> acceptance eligible (FR-001/FR-009).

    The operator cancellation is an acceptable ending, so ``all_done`` holds and
    the canceled WP is NOT surfaced as a lane blocker; only the surviving
    ``approved`` WP counts as delivered work.
    """
    summary = _summary_with_states(
        tmp_path,
        {"approved": ["WP01"], "canceled": ["WP02"]},
        provenance={"WP02": True},
    )

    assert summary.all_done is True
    outstanding = summary.outstanding()
    assert "lane_blockers" not in outstanding
    assert "delivered_nothing" not in outstanding


def test_synthetic_cancellation_stays_a_blocker(tmp_path: Path) -> None:
    """T023: a synthetic cancellation stays a blocker with the FR-003 diagnostic.

    Provenance-free cancellation must not be usable to skip work silently: the
    blocker names the WP and states operator-authored cancellation provenance is
    required.
    """
    summary = _summary_with_states(
        tmp_path,
        {"approved": ["WP01"], "canceled": ["WP02"]},
        provenance={"WP02": False},
    )

    assert summary.all_done is False
    blockers = summary.outstanding()["lane_blockers"]
    assert len(blockers) == 1
    assert "WP02: canonical lane is 'canceled'" in blockers[0]
    assert "operator-authored cancellation provenance required" in blockers[0]
    assert "approved or done" in blockers[0]


@pytest.mark.parametrize("lane", ["in_review", "blocked", "canceled"])
def test_acceptance_summary_all_done_rejects_non_accepted_ready_lanes(tmp_path: Path, lane: str) -> None:
    summary = _summary_with_lanes(tmp_path, {"approved": ["WP01"], lane: ["WP02"]})

    assert summary.all_done is False
    assert summary.ok is False


@pytest.mark.parametrize(
    ("lane", "expected_action"),
    [
        ("in_review", "complete the review"),
        ("blocked", "resolve the blocker"),
        # WP06 / T023: evolve the interim assertion to the FINAL FR-003 behavior.
        # WP02 widened the canceled blocker into a SUPERSET ("operator-authored
        # cancellation provenance required — reopen or replace it … approved or
        # done") to keep this suite green while deferring the assertion's
        # evolution to WP06. The canceled row now pins the FR-003 core — a
        # synthetic cancellation must name the missing operator provenance, not
        # merely offer generic "reopen or replace it" guidance (which is still
        # asserted present, below, so nothing is weakened).
        ("canceled", "operator-authored cancellation provenance required"),
    ],
)
def test_acceptance_summary_reports_actionable_lane_blockers(tmp_path: Path, lane: str, expected_action: str) -> None:
    summary = _summary_with_lanes(tmp_path, {"approved": ["WP01"], lane: ["WP02"]})

    outstanding = summary.outstanding()
    failed_checks = summary.failed_checks()
    payload = summary.to_dict()

    assert "lane_blockers" in outstanding
    assert len(outstanding["lane_blockers"]) == 1
    assert f"WP02: canonical lane is '{lane}'" in outstanding["lane_blockers"][0]
    assert expected_action in outstanding["lane_blockers"][0]
    assert "approved or done" in outstanding["lane_blockers"][0]
    if lane == "canceled":
        # The retained actionable guidance is NOT dropped by the FR-003
        # strengthening above — both the provenance demand and the
        # reopen/replace recovery hint must coexist.
        assert "reopen or replace it" in outstanding["lane_blockers"][0]
    assert any(item.check == "lane_blockers" and expected_action in item.detail for item in failed_checks)
    assert any(item["check"] == "lane_blockers" and expected_action in item["detail"] for item in payload["failed_checks"])


def test_acceptance_summary_preserves_existing_not_done_bucket(tmp_path: Path) -> None:
    summary = _summary_with_lanes(
        tmp_path,
        {
            "planned": ["WP01"],
            "claimed": ["WP02"],
            "in_progress": ["WP03"],
            "for_review": ["WP04"],
            "in_review": ["WP05"],
        },
    )

    outstanding = summary.outstanding()

    assert outstanding["not_done"] == ["WP01", "WP02", "WP03", "WP04"]
    assert any("WP05: canonical lane is 'in_review'" in item for item in outstanding["lane_blockers"])


def test_acceptance_lane_derivations_are_shared(tmp_path: Path) -> None:
    summary = _summary_with_lanes(tmp_path, {"approved": ["WP01"], "done": ["WP02"]})

    assert acceptance_lane_derivations(summary) == {
        "accepted_wps": ["WP01", "WP02"],
        "approved_wps": ["WP01"],
        "done_wps": ["WP02"],
        "merge_pending_wps": ["WP01"],
    }


def _create_test_feature(
    tmp_path: Path,
    mission_slug: str = _FEATURE_SLUG,
    *,
    malformed_events: str | None = None,
    omit_status_events: bool = False,
) -> Tuple[Path, Path]:
    """Create a minimal but valid feature for acceptance testing.

    Returns (repo_root, feature_dir).
    """
    repo_root = tmp_path
    # Initialise a git repo
    subprocess.run(
        ["git", "init", str(repo_root)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )

    feature_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    # The software-dev mission declares required path conventions. The build dirs
    # (src/, tests/, docs/) live at the repo root; contracts/ is a MISSION artifact
    # and lives under the feature dir (#2115). collect_feature_summary() validates
    # them and, under the default strict mode, turns a missing convention path into
    # a hard ``path_violations`` entry that forces ``summary.ok`` to False and makes
    # perform_acceptance() raise AcceptanceError. Create the dirs (with a committed
    # ``.gitkeep`` so git tracks the otherwise-empty dirs and the repo stays clean)
    # so acceptance reflects the WP/lane state under test, not a fixture artifact.
    for convention_dir in ("src", "tests", "docs"):
        (repo_root / convention_dir).mkdir(parents=True, exist_ok=True)
        (repo_root / convention_dir / ".gitkeep").write_text("")
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)
    (feature_dir / "contracts" / ".gitkeep").write_text("")

    # meta.json
    meta = {
        "mission_number": "099",
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Test Feature",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Minimal required artifacts
    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    # WP file with all required frontmatter fields
    wp_content = (
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n"
    )
    (tasks_dir / "WP01-test.md").write_text(wp_content)

    # Status event log
    if omit_status_events:
        pass
    elif malformed_events is not None:
        (feature_dir / "status.events.jsonl").write_text(malformed_events)
    else:
        # Build a valid transition chain: planned -> done (with force to skip intermediate)
        from ulid import ULID

        now = now_utc_iso()
        event = StatusEvent(
            event_id=str(ULID()),
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at=now,
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        )
        append_event(feature_dir, event)
        append_annotations_atomic_verified(
            feature_dir,
            [
                InnerStateChanged(
                    event_id=str(ULID()),
                    wp_id="WP01",
                    at=now,
                    actor="test-agent",
                    delta=WPInnerStateDelta(agent="test-agent"),
                )
            ],
        )

        # Pre-materialize so status.json is part of the committed state.
        # In real usage, status.json would already exist from prior operations.
        from specify_cli.status.reducer import materialize

        materialize(feature_dir)

    # Initial commit so the repo is clean
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "-A"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    return repo_root, feature_dir


# ---------------------------------------------------------------------------
# T012: materialize() does not dirty the repo
# ---------------------------------------------------------------------------


def test_collect_feature_summary_does_not_dirty_repo(tmp_path: Path) -> None:
    """Regression: collect_feature_summary() must not leave the repo dirty.

    Before the fix, materialize() wrote status.json (with a fresh timestamp)
    *before* the git-cleanliness check, making every clean feature fail.
    """
    repo_root, _feature_dir = _create_test_feature(tmp_path)

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG)
    assert summary.git_dirty == [], f"First call dirtied the repo: {summary.git_dirty}"

    # Call a second time -- must still report clean (no cumulative drift)
    summary2 = collect_feature_summary(repo_root, _FEATURE_SLUG)
    assert summary2.git_dirty == [], f"Second call dirtied the repo: {summary2.git_dirty}"


def test_collect_feature_summary_reads_planning_artifacts_from_primary(tmp_path: Path) -> None:
    """FR-002 (#2085, WP03): the accept gate reads PLANNING artifacts from PRIMARY.

    This previously asserted the OPPOSITE — that the coord worktree was the
    artifact-read surface for spec/plan/tasks. WP03 split the single
    ``status_feature_dir`` per-partition: PLANNING reads now resolve the PRIMARY
    surface via the WP01 kind-aware seam, while only the STATUS reads
    (status.events.jsonl, acceptance-matrix) stay coord-aware. The coord-only
    single-authority read was the drift this mission removes, not a contract to
    preserve (unification, not parity).

    The coord-topology setup is kept; the assertions invert to the new contract:

    * spec/plan/tasks deleted from PRIMARY (still present on coord) are reported
      MISSING — proving the gate read primary, not coord;
    * a ``NEEDS CLARIFICATION`` marker planted ONLY in the coord ``spec.md`` is
      NOT surfaced — proving the clarification scan read the (now-absent) primary
      ``spec.md`` rather than the coord copy.
    """
    repo_root, feature_dir = _create_test_feature(tmp_path)
    mid8 = "01ABCDEF"
    coord_feature_dir = repo_root / ".worktrees" / f"{_FEATURE_SLUG}-{mid8}-coord" / "kitty-specs" / f"{_FEATURE_SLUG}-{mid8}"
    coord_feature_dir.mkdir(parents=True)

    for path in feature_dir.rglob("*"):
        if path.is_file():
            target = coord_feature_dir / path.relative_to(feature_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mid8"] = mid8
    meta["coordination_branch"] = f"kitty/mission-{_FEATURE_SLUG}-{mid8}"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (coord_feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (repo_root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (coord_feature_dir / "tasks.md").write_text("# tasks.md\n- [ ] Coord-only unfinished task\n", encoding="utf-8")
    # Coord ``spec.md`` carries a clarification marker; primary ``spec.md`` is
    # deleted below. Post-WP03 the gate reads primary, so this coord marker MUST
    # NOT leak into ``needs_clarification``.
    (coord_feature_dir / "spec.md").write_text(
        "# spec.md\n[NEEDS CLARIFICATION: coord marker] <!-- decision_id: 01KS0ABCDEF0123456789ABCDE -->\n",
        encoding="utf-8",
    )
    for artifact_name in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / artifact_name).unlink()
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "Simulate coord-only required artifacts"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG)

    assert summary.feature_dir == feature_dir
    # PLANNING reads resolve PRIMARY (FR-002): the artifacts present only on coord
    # are now correctly reported missing. A gate still reading coord would report
    # ZERO missing (the false-green this remediation removes).
    assert {"spec.md", "plan.md", "tasks.md"}.issubset(set(summary.missing_artifacts))
    # The clarification scan read the (absent) primary ``spec.md``, NOT the coord
    # copy — so the coord-only marker is not surfaced.
    assert summary.needs_clarification == []


_MISSION_ID = "01ABCDEF0123456789ABCDEFGH"


@pytest.mark.parametrize(
    "handle",
    # The handle tiers that resolve the fixture mission via resolve_mission:
    # mid8 (mission_id[:8]), full ULID (mission_id), and the numeric prefix of the
    # mission *slug* (099-test-feature -> "099"; NOT meta.mission_number).
    [_MISSION_ID[:8], _MISSION_ID, _FEATURE_SLUG.split("-", 1)[0]],
    ids=["mid8", "ulid", "numeric"],
)
def test_collect_feature_summary_anchors_primary_across_handle_tiers(tmp_path: Path, handle: str) -> None:
    """A mid8 / ULID / numeric handle must resolve the accept gate's PRIMARY-partition
    reads to the primary mission dir (#2126), while STATUS reads stay coord-aware.

    Asserts all three legs: the identity anchor (``feature_dir``), the
    ``_iter_work_packages`` leg (``lanes``), and the ``_planning_read_dir`` leg
    (``missing_artifacts`` — a raw-handle mis-resolve would list spec/plan/tasks as
    missing because it would compose a nonexistent ``kitty-specs/<handle>`` dir)."""
    repo_root, feature_dir = _create_test_feature(tmp_path)
    mid8 = _MISSION_ID[:8]
    coord_feature_dir = repo_root / ".worktrees" / f"{_FEATURE_SLUG}-{mid8}-coord" / "kitty-specs" / f"{_FEATURE_SLUG}-{mid8}"
    coord_feature_dir.mkdir(parents=True)

    for path in feature_dir.rglob("*"):
        if path.is_file():
            target = coord_feature_dir / path.relative_to(feature_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = _MISSION_ID
    meta["mid8"] = mid8
    meta["coordination_branch"] = f"kitty/mission-{_FEATURE_SLUG}-{mid8}"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (coord_feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (repo_root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "Backfill identity + coord topology"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, handle)

    # Identity anchor -> primary checkout dir.
    assert summary.feature_dir == feature_dir
    # `_iter_work_packages` leg (WP tasks/) resolved off the primary surface.
    assert summary.lanes["done"] == ["WP01"]
    # `_planning_read_dir` leg (spec/plan/tasks) resolved off the primary surface.
    assert summary.missing_artifacts == []


# ---------------------------------------------------------------------------
# T013: accept_commit persisted to meta.json
# ---------------------------------------------------------------------------


def test_perform_acceptance_persists_accept_commit(tmp_path: Path) -> None:
    """Regression: perform_acceptance() must write the commit SHA to meta.json.

    Before the fix, record_acceptance() was called with accept_commit=None
    and the real SHA was never written back after the commit was created.
    """
    repo_root, feature_dir = _create_test_feature(tmp_path)
    # perform_acceptance commits the acceptance meta through the protected-primary
    # router (01KVMBD6). The flattened fixture mission commits to the current ref;
    # 'main' is protected and would be refused, so run from the (never-protected)
    # mission branch — the same pattern the sibling regression tests use.
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", f"kitty/mission-{_FEATURE_SLUG}"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG)
    result = perform_acceptance(summary, mode="local", actor="test-agent")

    # Read meta.json after acceptance
    meta = json.loads((feature_dir / "meta.json").read_text())

    # accept_commit must be a valid 40-char hex SHA
    accept_commit = meta.get("accept_commit")
    assert accept_commit is not None, "accept_commit missing from meta.json"
    assert re.fullmatch(r"[0-9a-f]{40}", accept_commit), f"accept_commit is not a valid SHA: {accept_commit!r}"

    # acceptance_history[-1] must match
    history = meta.get("acceptance_history", [])
    assert history, "acceptance_history is empty"
    assert history[-1].get("accept_commit") == accept_commit, (
        f"acceptance_history[-1]['accept_commit'] mismatch: {history[-1].get('accept_commit')!r} != {accept_commit!r}"
    )

    # AcceptanceResult.accept_commit must also match
    assert result.accept_commit == accept_commit, f"Result.accept_commit mismatch: {result.accept_commit!r} != {accept_commit!r}"

    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""

    committed_meta = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_FEATURE_SLUG}/meta.json"],
        check=True,
        capture_output=True,
        text=True,
    )
    committed = json.loads(committed_meta.stdout)
    assert committed["accept_commit"] == accept_commit
    assert committed["acceptance_history"][-1]["accept_commit"] == accept_commit


# ---------------------------------------------------------------------------
# T017: accept diagnostics expose skipped cascade checks
# ---------------------------------------------------------------------------


def test_collect_feature_summary_allows_main_branch_for_lane_acceptance(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add lanes manifest"], check=True, capture_output=True)

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert not any("Acceptance must run on mission branch" in issue for issue in summary.activity_issues)
    assert not any(item.check == "mission_branch" for item in summary.blocked_checks)
    assert any("Acceptance matrix" in issue and "required" in issue for issue in summary.activity_issues)
    skipped = {item.check for item in summary.skipped_checks}
    assert "acceptance_matrix_verdict" in skipped
    assert not any("Switch to the mission branch" in item for item in summary.recommended_fix_order)
    assert any("acceptance-matrix.json" in item for item in summary.recommended_fix_order)


def test_collect_feature_summary_allows_planning_artifact_research_without_matrix(
    tmp_path: Path,
) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path, "research-planning-only")
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)
    (repo_root / ".kittify").mkdir(exist_ok=True)

    from tests.lane_test_utils import write_single_lane_manifest

    deliverables_path = "docs/research/research-planning-only/"
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = "01K00000000000000000000000"
    meta["mission_type"] = "research"
    meta["mission"] = "research"
    meta["deliverables_path"] = deliverables_path
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    for path_name in ("research", "data", "findings", "reports"):
        directory = repo_root / deliverables_path / path_name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").write_text("", encoding="utf-8")

    write_single_lane_manifest(
        feature_dir,
        wp_ids=("WP01",),
        lane_id="lane-planning",
        write_scope=(f"{deliverables_path}**",),
        predicted_surfaces=("planning",),
    )
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "Add planning research artifacts"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, "research-planning-only", mutate_matrix=False)

    assert summary.ok is True
    assert not any("Acceptance matrix" in issue for issue in summary.activity_issues)
    assert not any(item.check == "acceptance_matrix" for item in summary.blocked_checks)
    assert not summary.path_violations
    assert any(item.check == "acceptance_matrix_presence" and "planning_artifact-only" in item.detail for item in summary.skipped_checks)


def test_accept_cli_no_commit_json_allows_planning_artifact_research_without_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path, "research-planning-only")
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)
    (repo_root / ".kittify").mkdir(exist_ok=True)

    from tests.lane_test_utils import write_single_lane_manifest

    deliverables_path = "docs/research/research-planning-only/"
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = "01K00000000000000000000000"
    meta["mission_type"] = "research"
    meta["mission"] = "research"
    meta["deliverables_path"] = deliverables_path
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    for path_name in ("research", "data", "findings", "reports"):
        directory = repo_root / deliverables_path / path_name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").write_text("", encoding="utf-8")

    write_single_lane_manifest(
        feature_dir,
        wp_ids=("WP01",),
        lane_id="lane-planning",
        write_scope=(f"{deliverables_path}**",),
        predicted_surfaces=("planning",),
    )
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "Add planning research artifacts"],
        check=True,
        capture_output=True,
    )

    cli = typer.Typer()
    cli.command(name="accept")(accept_module.accept)
    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)

    result = CliRunner().invoke(
        cli,
        [
            "--mission",
            "research-planning-only",
            "--no-commit",
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["ok"] is True
    assert not any(item.get("check") == "acceptance_matrix" for item in payload["summary"]["blocked_checks"])
    assert any(
        item.get("check") == "acceptance_matrix_presence" and "planning_artifact-only" in item.get("detail", "") for item in payload["summary"]["skipped_checks"]
    )
    assert not payload["summary"]["path_violations"]


def test_collect_feature_summary_blocks_unrelated_branch_for_lane_acceptance(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add lanes manifest"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", "scratch/unrelated-operator-branch"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert any("Acceptance must run on mission or target branch" in issue for issue in summary.activity_issues)
    assert any(item.check == "mission_branch" for item in summary.blocked_checks)
    skipped = {item.check for item in summary.skipped_checks}
    assert "acceptance_matrix_presence" in skipped
    assert any("mission branch or configured target branch" in item for item in summary.recommended_fix_order)
    assert not any(item.check == "acceptance_matrix" for item in summary.blocked_checks)


def test_collect_feature_summary_blocks_detached_head_for_lane_acceptance(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_FEATURE_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-01",
                    description="Acceptance proof",
                    proof_type="automated_test",
                    evidence="pytest",
                    pass_fail="pass",
                    verified_by="ci",
                )
            ],
        ),
    )
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add lane acceptance proof"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "checkout", "--detach", "HEAD"], check=True, capture_output=True)

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert summary.branch is None
    assert any("detached HEAD" in issue for issue in summary.activity_issues)
    assert any(item.check == "mission_branch" for item in summary.blocked_checks)
    skipped = {item.check for item in summary.skipped_checks}
    assert "acceptance_matrix_presence" in skipped


def test_collect_feature_summary_blocks_meta_lanes_target_branch_mismatch(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
    from tests.lane_test_utils import write_single_lane_manifest

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["target_branch"] = "scratch/unrelated-operator-branch"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, target_branch="main")
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_FEATURE_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-01",
                    description="Acceptance proof",
                    proof_type="automated_test",
                    evidence="pytest",
                    pass_fail="pass",
                    verified_by="ci",
                )
            ],
        ),
    )
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add divergent lane target"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", "scratch/unrelated-operator-branch"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert summary.ok is False
    assert any("Acceptance target branch mismatch" in issue for issue in summary.activity_issues)
    assert any(item.check == "mission_branch" for item in summary.blocked_checks)
    skipped = {item.check for item in summary.skipped_checks}
    assert "acceptance_matrix_presence" in skipped


def test_collect_feature_summary_reports_missing_matrix_skipped_checks(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add lanes manifest"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", f"kitty/mission-{_FEATURE_SLUG}"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert any("Acceptance matrix" in issue and "required" in issue for issue in summary.activity_issues)
    assert any(item.check == "acceptance_matrix" for item in summary.blocked_checks)
    skipped = {item.check for item in summary.skipped_checks}
    assert {"acceptance_matrix_evidence", "negative_invariants", "acceptance_matrix_verdict"} <= skipped
    assert any("acceptance-matrix.json" in item for item in summary.recommended_fix_order)


def test_collect_feature_summary_blocks_malformed_matrix_verdict_values(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    (feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(
            {
                "mission_slug": _FEATURE_SLUG,
                "criteria": [
                    {
                        "criterion_id": "AC-01",
                        "description": "Automated acceptance proof",
                        "proof_type": "automated_test",
                        "pass_fail": "failed",
                    }
                ],
                "negative_invariants": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add malformed acceptance matrix"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", f"kitty/mission-{_FEATURE_SLUG}"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert "Evidence: AC-01: pass_fail must be one of fail, pass, pending; got 'failed'" in summary.activity_issues
    assert "Acceptance matrix verdict is 'fail' — negative invariants or criteria not satisfied" in summary.activity_issues
    assert summary.ok is False


@pytest.mark.parametrize(
    "lanes_payload",
    [
        "{not-json",
        '{"version": 1}',
    ],
)
def test_collect_feature_summary_blocks_corrupt_lanes_json(tmp_path: Path, lanes_payload: str) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    (feature_dir / "lanes.json").write_text(lanes_payload, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add corrupt lanes manifest"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", f"kitty/mission-{_FEATURE_SLUG}"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert summary.all_done is True
    assert summary.ok is False
    assert any("lanes.json" in issue and "corrupt or malformed" in issue for issue in summary.activity_issues)
    assert any(item.check == "lanes_manifest" for item in summary.blocked_checks)
    skipped = {item.check for item in summary.skipped_checks}
    assert {
        "acceptance_matrix_presence",
        "acceptance_matrix_evidence",
        "negative_invariants",
        "acceptance_matrix_verdict",
    } <= skipped
    assert any("lanes.json" in item for item in summary.recommended_fix_order)


def test_collect_feature_summary_blocks_unreadable_lanes_path(tmp_path: Path) -> None:
    repo_root, feature_dir = _create_test_feature(tmp_path)
    subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True)

    from tests.lane_test_utils import write_single_lane_manifest

    write_single_lane_manifest(feature_dir)
    (feature_dir / "lanes.json").unlink()
    (feature_dir / "lanes.json").mkdir()
    (feature_dir / "lanes.json" / ".keep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Add unreadable lanes manifest"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-b", f"kitty/mission-{_FEATURE_SLUG}"],
        check=True,
        capture_output=True,
    )

    summary = collect_feature_summary(repo_root, _FEATURE_SLUG, mutate_matrix=False)

    assert summary.ok is False
    assert any("lanes.json" in issue and "corrupt or malformed" in issue for issue in summary.activity_issues)
    assert any(item.check == "lanes_manifest" for item in summary.blocked_checks)


# ---------------------------------------------------------------------------
# Integration branch guard: merge guidance must not target integration branch
# ---------------------------------------------------------------------------


class TestIntegrationBranchGuard:
    """perform_acceptance() must never emit 'git merge <integration>' or
    'git branch -d <integration>' when the current branch IS the integration
    branch (e.g. main, 2.x).
    """

    def _make_summary_on_branch(self, tmp_path: Path, branch: str, *, target_branch: str = "main") -> AcceptanceSummary:
        """Create a minimal AcceptanceSummary as if on *branch*."""
        repo_root, feature_dir = _create_test_feature(tmp_path)
        # Patch meta.json with the desired target_branch and recommit
        # so the repo stays clean (summary.ok requires no dirty files).
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["target_branch"] = target_branch
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "-A"],
            check=True,
            capture_output=True,
        )
        # Commit only if there are staged changes (target_branch may already
        # match the value written by _create_test_feature).
        diff = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if diff.returncode != 0:
            subprocess.run(
                ["git", "-C", str(repo_root), "commit", "-m", "patch target_branch"],
                check=True,
                capture_output=True,
            )

        summary = collect_feature_summary(tmp_path, _FEATURE_SLUG)
        # Override the detected branch to simulate the desired state
        object.__setattr__(summary, "branch", branch)
        return summary

    def test_branch_main_no_merge_guidance(self, tmp_path: Path) -> None:
        """branch='main' with target_branch='main' must NOT produce 'git merge main'."""
        summary = self._make_summary_on_branch(tmp_path, "main", target_branch="main")
        result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

        merged = " ".join(result.instructions + result.cleanup_instructions)
        assert "git merge main" not in merged, f"Should not suggest merging integration branch. instructions={result.instructions}"
        assert "git branch -d main" not in merged, f"Should not suggest deleting integration branch. cleanup={result.cleanup_instructions}"

    def test_branch_2x_no_merge_guidance(self, tmp_path: Path) -> None:
        """branch='2.x' with target_branch='2.x' must NOT produce 'git merge 2.x'."""
        summary = self._make_summary_on_branch(tmp_path, "2.x", target_branch="2.x")
        result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

        merged = " ".join(result.instructions + result.cleanup_instructions)
        assert "git merge 2.x" not in merged
        assert "git branch -d 2.x" not in merged

    def test_pr_mode_integration_branch_no_push_branch(self, tmp_path: Path) -> None:
        """PR mode on integration branch should not say 'Push your branch'."""
        summary = self._make_summary_on_branch(tmp_path, "main", target_branch="main")
        result = perform_acceptance(summary, mode="pr", actor="tester", auto_commit=False)

        merged = " ".join(result.instructions)
        assert "Push your branch" not in merged, f"Should not suggest pushing integration branch as feature. instructions={result.instructions}"

    def test_feature_branch_still_gets_merge_guidance(self, tmp_path: Path) -> None:
        """A real feature branch must still get spec-kitty merge + cleanup guidance."""
        summary = self._make_summary_on_branch(tmp_path, "kitty/mission-054-my-feature-lane-a", target_branch="main")
        result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

        merged = " ".join(result.instructions + result.cleanup_instructions)
        assert "spec-kitty merge --mission" in merged, f"Feature branch should get merge guidance. instructions={result.instructions}"
        assert "git branch -d kitty/mission-054-my-feature-lane-a" in merged, f"Feature branch should get cleanup guidance. cleanup={result.cleanup_instructions}"

    def test_well_known_branch_without_meta_target(self, tmp_path: Path) -> None:
        """When meta.json has no target_branch, well-known names are guarded."""
        repo_root, feature_dir = _create_test_feature(tmp_path)
        # Remove target_branch from meta and recommit
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta.pop("target_branch", None)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "-A"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", "remove target_branch"],
            check=True,
            capture_output=True,
        )

        summary = collect_feature_summary(tmp_path, _FEATURE_SLUG)
        object.__setattr__(summary, "branch", "master")
        result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

        merged = " ".join(result.instructions + result.cleanup_instructions)
        assert "git merge master" not in merged
        assert "git branch -d master" not in merged


# NOTE: T014 ``test_standalone_tasks_cli_help`` was retired with the standalone
# tasks surface (WP03/FR-004) — it subprocess-ran the standalone tasks CLI's
# ``--help``, which no longer exists. The canonical ``spec-kitty`` CLI help is
# covered by the CLI command test suites.


# ---------------------------------------------------------------------------
# T015: malformed JSONL raises AcceptanceError
# ---------------------------------------------------------------------------


class TestMalformedJsonlRaisesAcceptanceError:
    """Regression: malformed status.events.jsonl must raise AcceptanceError.

    Before the fix, StoreError propagated uncaught to the CLI layer,
    producing an unhandled traceback instead of a structured error.
    """

    def test_completely_invalid_json(self, tmp_path: Path) -> None:
        """Totally invalid JSON raises AcceptanceError with 'corrupted'."""
        repo_root, _feature_dir = _create_test_feature(
            tmp_path,
            malformed_events="this is not valid json\n",
        )

        with pytest.raises(AcceptanceError, match="corrupted") as exc_info:
            collect_feature_summary(repo_root, _FEATURE_SLUG)

        # Must be AcceptanceError, NOT StoreError
        assert not isinstance(exc_info.value, StoreError)

    def test_partially_valid_jsonl(self, tmp_path: Path) -> None:
        """First line valid JSON, second line invalid -- still AcceptanceError."""
        valid_line = json.dumps({"key": "value"})
        malformed = f"{valid_line}\nthis is broken\n"
        repo_root, _feature_dir = _create_test_feature(
            tmp_path,
            malformed_events=malformed,
        )

        with pytest.raises(AcceptanceError, match="corrupted") as exc_info:
            collect_feature_summary(repo_root, _FEATURE_SLUG)

        assert not isinstance(exc_info.value, StoreError)

    def test_empty_events_file_does_not_raise(self, tmp_path: Path) -> None:
        """Empty file (zero bytes) is not an error -- read_events returns []."""
        repo_root, _feature_dir = _create_test_feature(
            tmp_path,
            malformed_events="",
        )

        # Should not raise -- empty events file is valid
        summary = collect_feature_summary(repo_root, _FEATURE_SLUG)
        # But the feature won't be "ok" because there's no canonical state
        assert isinstance(summary, AcceptanceSummary)

    def test_missing_events_file_reports_bootstrap_issue(self, tmp_path: Path) -> None:
        """Missing status.events.jsonl reports bootstrap guidance instead of crashing."""
        repo_root, _feature_dir = _create_test_feature(
            tmp_path,
            omit_status_events=True,
        )

        summary = collect_feature_summary(repo_root, _FEATURE_SLUG)

        assert isinstance(summary, AcceptanceSummary)
        assert any("status.events.jsonl" in issue for issue in summary.activity_issues)
        assert any("finalize-tasks" in issue for issue in summary.activity_issues)


# NOTE: T016 ``test_copy_parity_between_acceptance_modules`` was retired with the
# standalone tasks surface (WP03/FR-004). It asserted that the standalone
# acceptance re-export shim mirrored ``specify_cli.acceptance`` object-for-object;
# once that shim is gone (WP04) the parity check is moot. The canonical surface is
# ``specify_cli.acceptance`` directly.
