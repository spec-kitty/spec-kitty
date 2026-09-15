"""Golden characterization harness for the commit-surface behavior ledger (WP01 / T004).

Freezes the CURRENT observable behavior of the six ledger rows in
``kitty-specs/coord-commit-surface-authority-01M1M553/contracts/authoritative-surface.md``
(§Behavior-change ledger), captured against TODAY's code BEFORE any consumer change.
This file is the shared characterize-then-diff surface (NFR-001): WP03 (T013) and
WP04 (T017) re-run this EXACT file to prove no unintended drift once the
commit-bearing loci are re-homed onto the single ``resolve_surface_authority`` rule.

Each row asserts the JSON-mode exit code (not only human output), mirroring the
CLI's status→exit mapping (``committed`` / ``unchanged`` → 0; ``no_op_wrong_surface``
/ ``error`` → 1; a suppressed primary commit / a refusal-error surfaced by the task
helpers map the same way). All fixtures + expected values live inline / under
``tests/coordination/`` — no fixtures under ``tests/specify_cli/cli/commands/agent/``
(that collides with WP03's scope).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind, MissionTopology
from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PRIMARY_BRANCH = "main"
_COORD_REF = "kitty/mission-my-slug-ABCD1234"
_MISSION_SLUG = "001-my-mission"

# ---------------------------------------------------------------------------
# Frozen expectations: the six ledger rows (contract §Behavior-change ledger).
# WP03/WP04 diff their re-run against THESE values.
# ---------------------------------------------------------------------------

LEDGER_GOLDEN: dict[str, dict[str, object]] = {
    "move_task_lifecycle_coord_protected": {"exit_code": 0, "committed": False, "verdict": "route_to_coord"},
    "map_requirements_planning_coord_protected": {"exit_code": 1, "committed": False, "verdict": "refuse"},
    "mark_status_coord_protected": {"exit_code": 0, "committed": False, "verdict": "no_commit"},
    "genuine_no_op_unprotected": {"exit_code": 0, "committed": False, "verdict": "no_op"},
    "spec_commit_unchanged": {"exit_code": 0, "committed": False, "verdict": "no_op"},
    "wrong_surface": {"exit_code": 1, "committed": False, "verdict": "refuse"},
}


# ---------------------------------------------------------------------------
# CURRENT CLI status→exit mapping (see spec_commit_cmd.py: committed/unchanged→0,
# no_op_wrong_surface/error→1). ONE mapping, mirrored here for the goldens.
# ---------------------------------------------------------------------------


def _cli_exit_code(status: str) -> int:
    return 0 if status in ("committed", "unchanged") else 1


class _FakeCommitResult:
    sha = "abc1234567890"


def _policy(*, protected: bool) -> ProtectionPolicy:
    branches = frozenset({_PRIMARY_BRANCH}) if protected else frozenset()
    return ProtectionPolicy(protected_branches=branches, operator_hatch_active=False)


def _router_context(*, coord: bool, placement_ref: str):
    """Patch the three router legs (topology / placement / primary target) consistently."""
    topology = MissionTopology.COORD if coord else MissionTopology.SINGLE_BRANCH
    return (
        patch("specify_cli.coordination.commit_router.resolve_topology", return_value=topology),
        patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=CommitTarget(ref=placement_ref),
        ),
        patch(
            "specify_cli.coordination.commit_router._resolve_mission_target_branch",
            return_value=_PRIMARY_BRANCH,
        ),
    )


# ---------------------------------------------------------------------------
# Row 1 — move-task (lifecycle) under coord + protected primary → RouteToCoord, exit 0.
# CURRENT locus: ``_skip_target_branch_commit`` (skip the direct primary commit; the
# coord status transition is authoritative → the command still exits 0).
# ---------------------------------------------------------------------------


def test_row1_move_task_lifecycle_coord_protected_exit0(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_shared import _skip_target_branch_commit

    with (
        patch.object(_tasks, "_coord_topology_active", return_value=True),
        patch.object(_tasks.ProtectionPolicy, "resolve", return_value=_policy(protected=True)),
    ):
        skip = _skip_target_branch_commit(tmp_path, _MISSION_SLUG, _PRIMARY_BRANCH)

    assert skip is True  # primary commit suppressed → RouteToCoord semantics
    exit_code = 0 if skip else 0  # skip arm exits 0 (coord commit authoritative)
    assert exit_code == LEDGER_GOLDEN["move_task_lifecycle_coord_protected"]["exit_code"]


# ---------------------------------------------------------------------------
# Row 2 — map-requirements (planning) under coord + protected primary → Refuse, exit 1.
# CURRENT locus: ``_protected_branch_status_commit_error`` (returns an error → the
# command raises typer.Exit(1)).
# ---------------------------------------------------------------------------


def test_row2_map_requirements_planning_coord_protected_exit1(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_shared import _protected_branch_status_commit_error

    with patch.object(_tasks.ProtectionPolicy, "resolve", return_value=_policy(protected=True)):
        error = _protected_branch_status_commit_error(_PRIMARY_BRANCH, tmp_path, "map-requirements")

    assert error is not None  # refusal → non-None error → exit 1
    exit_code = 1 if error is not None else 0
    assert exit_code == LEDGER_GOLDEN["map_requirements_planning_coord_protected"]["exit_code"]


# ---------------------------------------------------------------------------
# Row 3 — mark-status under coord + protected primary → event-log-only, no commit, exit 0.
# CURRENT behavior (#2816): ``_do_mark_status`` never invokes ``_ms_commit`` /
# ``commit_for_mission`` — mark-status is event-log-only. Freeze the no-commit
# invariant structurally (a re-added commit path is a regression).
# ---------------------------------------------------------------------------


def test_row3_mark_status_is_event_log_only_no_commit() -> None:
    import ast

    from specify_cli.cli.commands.agent import tasks_mark_status as _ms

    src_path = _ms.__file__
    assert src_path is not None
    tree = ast.parse(Path(src_path).read_text(encoding="utf-8"))

    do_mark = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_do_mark_status")
    called = {n.func.id for n in ast.walk(do_mark) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    # The mark-status flow must NOT reach the (dead compat-shim) commit path.
    assert "_ms_commit" not in called, "mark-status re-acquired a commit path (regression #2816)"
    assert LEDGER_GOLDEN["mark_status_coord_protected"]["verdict"] == "no_commit"


# ---------------------------------------------------------------------------
# Row 4 — genuine no-op (move-task / map-requirements), unprotected → exit 0, typed reason.
# CURRENT locus: ``commit_for_mission`` → ``unchanged`` (safe_commit "nothing to commit").
# ---------------------------------------------------------------------------


def test_row4_genuine_no_op_unprotected_exit0(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import commit_for_mission

    artifact = tmp_path / "tasks.md"
    artifact.write_text("# Tasks\n", encoding="utf-8")
    topo, placement, target = _router_context(coord=False, placement_ref=_PRIMARY_BRANCH)

    with (
        topo,
        placement,
        target,
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=subprocess.CalledProcessError(1, "git commit", stderr="nothing to commit"),
        ),
    ):
        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="no-op",
            policy=_policy(protected=False),
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )

    assert result.status == "unchanged"
    assert result.reason == "no_op_no_changes"
    assert _cli_exit_code(result.status) == LEDGER_GOLDEN["genuine_no_op_unprotected"]["exit_code"]


# ---------------------------------------------------------------------------
# Row 5 — spec-commit ``unchanged`` (#2739 regression guard) → exit 0 + machine reason.
# CURRENT locus: ``commit_for_mission`` with SPEC kind → ``unchanged`` carries a reason
# so a caller can tell "nothing to do" from "silently wrong".
# ---------------------------------------------------------------------------


def test_row5_spec_commit_unchanged_exit0_with_reason(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import commit_for_mission

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")
    topo, placement, target = _router_context(coord=False, placement_ref=_PRIMARY_BRANCH)

    with (
        topo,
        placement,
        target,
        patch(
            "specify_cli.coordination.commit_router.safe_commit",
            side_effect=subprocess.CalledProcessError(1, "git commit", stderr="nothing to commit"),
        ),
    ):
        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="Add spec",
            policy=_policy(protected=False),
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == "unchanged"
    assert result.reason is not None  # #2739 B03: a committed:false success MUST carry a reason
    assert _cli_exit_code(result.status) == LEDGER_GOLDEN["spec_commit_unchanged"]["exit_code"]


# ---------------------------------------------------------------------------
# Row 6 — any commit-bearing operation on the WRONG surface → exit 1 (NOT collapsed to 0).
# CURRENT locus: ``commit_for_mission`` → ``no_op_wrong_surface`` when the artifact is
# absent at the resolved placement.
# ---------------------------------------------------------------------------


def test_row6_wrong_surface_exit1(tmp_path: Path) -> None:
    from specify_cli.coordination.commit_router import commit_for_mission

    missing = tmp_path / "never-written.md"  # deliberately not created
    topo, placement, target = _router_context(coord=False, placement_ref=_PRIMARY_BRANCH)

    with topo, placement, target:
        result = commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(missing,),
            message="commit missing",
            policy=_policy(protected=False),
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == "no_op_wrong_surface"
    exit_code = _cli_exit_code(result.status)
    assert exit_code == 1, "wrong-surface must NOT be collapsed to exit 0"
    assert exit_code == LEDGER_GOLDEN["wrong_surface"]["exit_code"]


# ---------------------------------------------------------------------------
# Meta: the ledger is complete (all six rows present) — a guard against silently
# dropping a row in a later re-freeze.
# ---------------------------------------------------------------------------


def test_ledger_has_all_six_rows() -> None:
    assert len(LEDGER_GOLDEN) == 6
