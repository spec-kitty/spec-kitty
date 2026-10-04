"""C-008 (coord-commit-integrity, SURFACE C): the move-task pre-review gate
reads ``baseline-tests.json`` from the PRIMARY partition, not the coord husk.

``baseline-tests.json`` (``tasks/<wp_slug>/``) is a WORK_PACKAGE_TASK-kind,
PRIMARY-partition artifact authored by ``implement_capture_baseline``. Under
coord topology ``_MoveTaskState.feature_dir`` is the KIND-BLIND coord leg —
where the PRIMARY-authored baseline does NOT exist. Reading the baseline off
``st.feature_dir`` therefore returns ``None`` and silently drops
pre-existing-failure suppression (false review friction).

The fix routes the READ through the SAME kind-aware seam the review-side
baseline block uses (``workflow._resolve_workflow_read_dir(kind=
WORK_PACKAGE_TASK)``). This test pins that wiring: with the coord husk and the
seam-resolved PRIMARY dir DELIBERATELY divergent, the gate must load the
baseline that lives under the PRIMARY dir — RED against the coord-husk read.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent import tasks_move_task
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
from specify_cli.review.baseline import BaselineTestResult
from specify_cli.status import Lane

pytestmark = pytest.mark.fast

_MODULE = "specify_cli.cli.commands.agent.tasks_move_task"
_WORKFLOW = "specify_cli.cli.commands.agent.workflow"
_WP_SLUG = "WP01-coord-baseline"
_MISSION = "coord-commit-integrity-baseline"


def _make_state(*, coord_husk: Path) -> _MoveTaskState:
    """A minimal ``for_review`` move-task state anchored on a coord husk dir."""
    st = _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=_MISSION,
        agent="claude",
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        skip_pre_review_gate=False,
    )
    st.target_lane = Lane.FOR_REVIEW
    st.main_repo_root = coord_husk.parent / "main-repo-root"
    st.target_branch = "main"
    st.mission_slug = _MISSION
    # Coord topology: the STATUS leg (coord husk) is DISTINCT from the primary
    # planning partition that owns the WORK_PACKAGE_TASK baseline.
    st.feature_dir = coord_husk
    st.wp = SimpleNamespace(path=Path(f"{_WP_SLUG}.md"), frontmatter="")
    return st


def _author_primary_baseline(primary_dir: Path) -> None:
    """Author a realistic PRIMARY-partition baseline with a pre-existing failure."""
    baseline = BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-07-23T09:30:00+00:00",
        base_branch="main",
        base_commit="a1b2c3d4e5f6a7b8",
        test_runner="pytest",
        total=42,
        passed=41,
        failed=1,
        skipped=0,
    )
    target = primary_dir / "tasks" / _WP_SLUG / "baseline-tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(baseline.to_dict()), encoding="utf-8")


@pytest.mark.git_repo
def test_pre_review_gate_reads_baseline_from_primary_not_coord_husk(
    tmp_path: Path,
) -> None:
    """The pre-review gate resolves ``baseline-tests.json`` via the kind-aware
    seam (PRIMARY partition), NOT the kind-blind coord husk (``st.feature_dir``).

    The coord husk holds NO baseline; the seam-resolved PRIMARY dir holds one
    with a pre-existing failure. The gate must load the PRIMARY baseline — so
    the captured ``BaselineTestResult.load`` path lands under the PRIMARY dir
    and the load returns the authored result. Goes RED if the read reverts to
    ``st.feature_dir`` (the coord-husk path holds no baseline → ``None``).
    """
    coord_husk = tmp_path / ".worktrees" / f"{_MISSION}-coord" / "kitty-specs" / _MISSION
    coord_husk.mkdir(parents=True)
    primary_dir = tmp_path / "kitty-specs" / _MISSION
    primary_dir.mkdir(parents=True)
    _author_primary_baseline(primary_dir)

    st = _make_state(coord_husk=coord_husk)

    captured: dict[str, Any] = {}
    real_load = BaselineTestResult.load

    def _spy_load(path: Path) -> BaselineTestResult | None:
        captured["path"] = path
        return real_load(path)

    with (
        patch("specify_cli.cli.commands.agent.tasks_move_task_gates._resolve_wp_slug", return_value=_WP_SLUG),
        patch(
            f"{_WORKFLOW}._resolve_workflow_read_dir", return_value=primary_dir
        ) as seam_mock,
        patch.object(BaselineTestResult, "load", side_effect=_spy_load),
    ):
        # ``_mt_resolve_gate_baseline`` is the shared baseline loader the WP09
        # (doctrine-controlled-transition-gates) refactor extracted from the
        # pre-review gate; both the handler context and the FR-004 override tier
        # call it, and it is where the C-008 kind-aware seam routing lives. The
        # full-gate entry point now reaches it ONLY when the active doctrine
        # binds a handler to the for_review edge (absent in this minimal fixture),
        # so exercise the C-008 concern at the seam that owns it.
        tasks_move_task._mt_resolve_gate_baseline(st)

    # The kind-aware seam was consulted for the WORK_PACKAGE_TASK read dir.
    seam_mock.assert_called_once()
    assert seam_mock.call_args.kwargs["mission_slug"] == _MISSION
    assert seam_mock.call_args.kwargs["kind"].name == "WORK_PACKAGE_TASK"

    # The baseline path resolves under the PRIMARY dir, NEVER the coord husk.
    loaded_path = captured["path"]
    assert loaded_path == primary_dir / "tasks" / _WP_SLUG / "baseline-tests.json"
    assert coord_husk not in loaded_path.parents

    # And the PRIMARY-authored baseline was actually found (suppression intact).
    assert real_load(loaded_path) is not None
