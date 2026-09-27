"""Layer-4 seam interception tests for the WP05 move_task-family relocation.

Mission ``tasks-py-degod-wave2-01KWH9EQ`` — parity-contract Layer 4 (NFR-002):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/contracts/parity-contract.md``.

This file now carries ONE battery (the WP06 / dev-assist-retire-path-hardening
ruling, mission ``dev-assist-retire-path-hardening-01KXAVR0``, #2565):

1. **Interception** — each test patches ``...agent.tasks.<symbol>`` with a
   sentinel and drives a relocated ``_mt_*`` phase helper (or ``_do_move_task``
   collaborator construction) THROUGH the moved body, asserting the sentinel is
   hit — proving the lazy ``_tasks.<attr>`` seam bridge preserves patch
   interception, not merely import resolution. The C-001 divergence wiring
   (``_skip_target_branch_commit`` pre-gate position + auto-commit gating) is
   pinned explicitly. This coverage is UNIQUE — no observable-contract test
   (including the Fake-port ``test_move_task_orchestration.py`` projections)
   proves a call-site is still routed through the patchable ``tasks.<attr>``
   seam, since those tests never patch ``tasks.<attr>`` to assert phase-helper
   routing; they drive ``_do_move_task`` with injected Fake ports instead. A
   same-object identity check cannot observe patchability either. KEEP is the
   default per the WP05 review ruling.

The **identity** battery (``test_tasks_binding_is_tasks_move_task_object``,
parametrized over the 51-symbol move-set) and the exact-set completeness pin
(``test_move_set_matches_tasks_move_task_defs``) were RETIRED at WP06: both
are mechanically subsumed by WP05's consolidated re-export guard —
``tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py``
(``test_tasks_binding_is_seam_object`` for identity;
``test_guard_symbol_is_genuinely_native_to_its_seam`` +
``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
exact-set/completeness claim over the same 51 ``tasks_move_task`` symbols).

Seam checklist (per-symbol evidence):
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kernel.clock import parse_iso, timedelta
from specify_cli.cli.commands.agent import tasks, tasks_move_task, tasks_verdict_persistence
from specify_cli.cli.commands.agent.tasks_move_task import (
    _MoveTaskState,
    _binding_role_for_lane,
    _mt_approval_policy_metadata,
    _mt_hop_policy_metadata,
)
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import is_non_resolvable_review_ref
from specify_cli.status import Lane, ReviewResult, ReviewResultLookup, StatusEvent
from specify_cli.status._unsafe import append_event
from specify_cli.status.resolved_binding import ResolvedBinding
from specify_cli.status.store import read_events

pytestmark = pytest.mark.fast

_TASKS = "specify_cli.cli.commands.agent.tasks"
_VERDICT_SEAM = "specify_cli.cli.commands.agent.tasks_verdict_persistence"


class _SentinelHit(Exception):
    """Raised by sentinel patches to prove the patched attribute was called."""


class _StopFlow(Exception):
    """Raised by fake ports to halt a phase helper after the point under test."""


def _make_state(**overrides: Any) -> _MoveTaskState:
    """A minimal ``_MoveTaskState`` (raw command inputs only) with overrides."""
    kwargs: dict[str, Any] = {
        "task_id": "WP01",
        "to": "doing",
        "mission": "034-feature",
        "agent": None,
        "assignee": None,
        "shell_pid": None,
        "note": None,
        "review_feedback_file": None,
        "approval_ref": None,
        "reviewer": None,
        "self_review_fallback": False,
        "intended_reviewer": None,
        "reviewer_failure_reason": None,
        "done_override_reason": None,
        "force": False,
        "tracker_ref": None,
        "skip_review_artifact_check": False,
        "auto_commit": None,
        "json_output": True,
    }
    field_overrides = {k: v for k, v in overrides.items() if k in kwargs}
    kwargs.update(field_overrides)
    st = _MoveTaskState(**kwargs)
    for key, value in overrides.items():
        if key not in field_overrides:
            setattr(st, key, value)
    return st


# ---------------------------------------------------------------------------
# Interception battery — patch tasks.<symbol>, drive the relocated body,
# assert the sentinel bites. All patches target the ``tasks`` namespace; the
# bodies live in ``tasks_move_task`` (research.md D1 seam bridge).
# ---------------------------------------------------------------------------


def test_c001_pre_gate_intercepts_through_tasks_namespace(tmp_path: Path) -> None:
    """C-001: the ``_skip_target_branch_commit`` pre-gate fires at its original
    position in ``_mt_resolve_targets`` — after auto-commit/mission/branch
    resolution, before everything else — and is reached via ``_tasks.<attr>``,
    so the historical ``tasks``-namespace patches keep intercepting."""
    st = _make_state()
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path) as locate_mock,
        patch(f"{_TASKS}._emit_sparse_session_warning") as sparse_mock,
        patch(f"{_TASKS}.get_auto_commit_default", return_value=True) as auto_mock,
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature") as slug_mock,
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ) as branch_mock,
        patch(
            f"{_TASKS}._skip_target_branch_commit", side_effect=_SentinelHit
        ) as skip_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_move_task._mt_resolve_targets(st, ports=MagicMock())
    locate_mock.assert_called_once()
    sparse_mock.assert_called_once()
    auto_mock.assert_called_once_with(tmp_path)
    slug_mock.assert_called_once()
    branch_mock.assert_called_once_with(tmp_path, "034-feature", True)
    skip_mock.assert_called_once_with(tmp_path, "034-feature", "main")


def test_c001_pre_gate_not_consulted_when_auto_commit_resolves_false(
    tmp_path: Path,
) -> None:
    """C-001 wiring: with auto-commit resolved False the pre-gate is NOT
    consulted (``skip_target_branch_commit`` stays False by the original
    ternary), and the flow proceeds to the ports read."""
    st = _make_state()
    ports = MagicMock()
    ports.coord.feature_write_dir.side_effect = _StopFlow
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path),
        patch(f"{_TASKS}._emit_sparse_session_warning"),
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False),
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature"),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
        patch(f"{_TASKS}._skip_target_branch_commit") as skip_mock,
        pytest.raises(_StopFlow),
    ):
        tasks_move_task._mt_resolve_targets(st, ports=ports)
    skip_mock.assert_not_called()
    assert st.skip_target_branch_commit is False


@pytest.mark.parametrize(
    ("to", "expected_action"),
    [
        ("doing", "implement"),
        ("for_review", "implement"),
        ("in_review", "review"),
        ("approved", "review"),
        ("done", "review"),
    ],
)
def test_mt_resolve_targets_dispatch_binding_action_by_target(
    tmp_path: Path, to: str, expected_action: str
) -> None:
    """FR-006 (red-first, T1): the dispatch-binding ``action`` resolution
    table. Brownfield gap: an APPROVED (or DONE) target used to resolve
    ``action="implement"`` (only ``IN_REVIEW`` resolved ``"review"``), so the
    reviewer's binding for an approve stamped the WRONG profile/model onto
    ``_mt_approval_policy_metadata``'s ``policy_metadata`` sidecar. Every
    other target's resolution is unchanged (regression guard)."""
    st = _make_state(to=to)
    ports = MagicMock()
    ports.coord.feature_write_dir.side_effect = _StopFlow
    with (
        patch(f"{_TASKS}.locate_project_root", return_value=tmp_path),
        patch(f"{_TASKS}._emit_sparse_session_warning"),
        patch(f"{_TASKS}.get_auto_commit_default", return_value=False),
        patch(f"{_TASKS}._find_mission_slug", return_value="034-feature"),
        patch(
            f"{_TASKS}._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow._resolve_dispatch_binding"
        ) as binding_mock,
        pytest.raises(_StopFlow),
    ):
        tasks_move_task._mt_resolve_targets(st, ports=ports)
    binding_mock.assert_called_once()
    assert binding_mock.call_args.kwargs["action"] == expected_action


def test_patched_decide_transition_intercepts_run_decision() -> None:
    """``tasks.decide_transition`` (sentinel-monkeypatch seam) bites through
    ``_mt_run_decision``'s ``_tasks.<attr>`` route."""
    st = _make_state()
    st.request = cast(Any, MagicMock())
    st.verdict_artifact_path = None  # keeps the OLD-timing override persist inert
    with (
        patch(f"{_TASKS}.decide_transition", side_effect=_SentinelHit) as decide_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_move_task._mt_run_decision(st)
    decide_mock.assert_called_once_with(st.request)


def test_patched_review_gates_intercept_gather_review_facts() -> None:
    """``tasks._check_unchecked_subtasks`` / ``tasks._validate_ready_for_review``
    bite through ``_mt_gather_review_facts`` and land in the built request."""
    st = _make_state(to="for_review")
    st.target_lane = Lane.FOR_REVIEW
    st.wp = cast(Any, SimpleNamespace(path=Path("WP01-x.md"), frontmatter=""))
    with (
        patch(
            f"{_TASKS}._check_unchecked_subtasks", return_value=["T9"]
        ) as unchecked_mock,
        patch(
            f"{_TASKS}._validate_ready_for_review", return_value=(False, ["fix it"])
        ) as ready_mock,
    ):
        tasks_move_task._mt_gather_review_facts(st)
    unchecked_mock.assert_called_once()
    ready_mock.assert_called_once()
    assert st.request is not None
    assert st.request.unchecked_subtasks == ("T9",)
    assert st.request.review_ready is False
    assert st.request.review_guidance == ("fix it",)


def test_patched_workspace_and_ancestry_intercept_done_facts(tmp_path: Path) -> None:
    """``tasks.resolve_workspace_for_wp`` / ``tasks._wp_branch_merged_into_target``
    bite through ``_mt_done_ancestry_facts``."""
    st = _make_state(to="done")
    st.target_lane = Lane.DONE
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.target_branch = "main"
    with (
        patch(
            f"{_TASKS}.resolve_workspace_for_wp",
            return_value=SimpleNamespace(execution_mode="code_change"),
        ) as ws_mock,
        patch(
            f"{_TASKS}._wp_branch_merged_into_target",
            return_value=(True, "merged via PR"),
        ) as merged_mock,
    ):
        mode, merged, msg = tasks_move_task._mt_done_ancestry_facts(st)
    ws_mock.assert_called_once_with(tmp_path, "034-feature", "WP01")
    merged_mock.assert_called_once()
    assert (mode, merged, msg) == ("code_change", True, "merged via PR")


def test_patched_detect_reviewer_intercepts_approval_facts() -> None:
    """``tasks._detect_reviewer_name`` (module-resident def) bites through
    ``_mt_approval_facts`` when no ``--reviewer`` is given."""
    st = _make_state(to="approved")
    st.target_lane = Lane.APPROVED
    with patch(
        f"{_TASKS}._detect_reviewer_name", return_value="sentinel-reviewer"
    ) as detect_mock:
        reviewer, approval_ref = tasks_move_task._mt_approval_facts(st)
    detect_mock.assert_called_once()
    assert reviewer == "sentinel-reviewer"
    assert approval_ref is not None and approval_ref.startswith("auto-approval:WP01:")


def test_seam_read_dir_intercepts_issue_matrix_facts(tmp_path: Path) -> None:
    """``_mt_issue_matrix_facts`` routes its PRIMARY-anchor read through the
    kind-aware placement seam directly with ``MissionArtifactKind.SPEC``.

    read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): this test
    replaces ``test_patched_primary_feature_dir_intercepts_issue_matrix_facts``
    (retired — its entire subject was the ``_tasks.<attr>`` patch-seam bridge
    onto the retiring ``primary_feature_dir_for_mission`` wrapper, which this
    call site no longer uses; DIRECTIVE_041 "delete, don't repair" for a test
    whose whole subject is the old shape). ``SPEC`` (not ``ISSUE_MATRIX``) is
    the correct kind: ``_issue_matrix_approval_blocker``'s ``primary_feature_dir``
    argument is consulted only to detect ``spec.md``'s referenced issues.
    """
    st = _make_state(to="approved")
    st.target_lane = Lane.APPROVED
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.feature_dir = tmp_path
    with (
        patch(
            f"{tasks_move_task.__name__}.placement_seam", side_effect=_SentinelHit
        ) as seam_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_move_task._mt_issue_matrix_facts(st)
    seam_mock.assert_called_once()


def test_patched_read_events_intercepts_current_event_lane(tmp_path: Path) -> None:
    """``tasks.read_events_transactional`` bites through ``_mt_current_event_lane``."""
    st = _make_state()
    st.feature_dir = tmp_path
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    fake_events = [SimpleNamespace(wp_id="WP01", to_lane="in_progress")]
    with patch(
        f"{_TASKS}.read_events_transactional", return_value=fake_events
    ) as events_mock:
        lane = tasks_move_task._mt_current_event_lane(st)
    events_mock.assert_called_once()
    assert lane == "in_progress"


def test_patched_feature_status_lock_intercepts_execute(tmp_path: Path) -> None:
    """``tasks.feature_status_lock`` (top-D7 context-manager seam) bites through
    ``_mt_execute`` before any emit/persist side effect."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    with (
        patch(f"{_TASKS}.feature_status_lock", side_effect=_SentinelHit) as lock_mock,
        pytest.raises(_SentinelHit),
    ):
        tasks_move_task._mt_execute(st, ports=MagicMock())
    lock_mock.assert_called_once_with(tmp_path, "034-feature")


# (WP10 closeout) ``test_patched_console_intercepts_tracker_ref_warning`` removed:
# it drove ``_mt_persist_tracker_refs``, the frontmatter tracker-refs writer the
# god-write cut (WP06, FR-006) DELETED — tracker refs are now an off-axis
# ``InnerStateChanged`` union delta, so there is no longer a WP-file write leg to
# warn about. The remaining seam bindings above still pin the compat surface.


def test_patched_output_helpers_intercept_mt_output(tmp_path: Path) -> None:
    """``tasks._status_event_result_fields`` / ``_coord_status_events_path`` /
    ``_output_result`` / ``_check_dependent_warnings`` all bite through
    ``_mt_output`` (the coord skip arm drives the polymorphic envelope)."""
    st = _make_state()
    st.wp = cast(Any, SimpleNamespace(path=tmp_path / "WP01-x.md"))
    st.decision = cast(Any, SimpleNamespace(skip_primary=True))
    st.feature_dir = tmp_path
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.canonical_lane = "in_progress"
    coord_events = tmp_path / "coord" / "status.events.jsonl"
    with (
        patch(
            f"{_TASKS}._status_event_result_fields",
            return_value={"event_id": "01H", "to_lane": "in_progress"},
        ) as fields_mock,
        patch(
            f"{_TASKS}._coord_status_events_path", return_value=coord_events
        ) as coord_mock,
        patch(f"{_TASKS}._output_result") as output_mock,
        patch(f"{_TASKS}._check_dependent_warnings") as warn_mock,
    ):
        tasks_move_task._mt_output(st)
    fields_mock.assert_called_once_with(st.event)
    coord_mock.assert_called_once_with(tmp_path, "034-feature")
    warn_mock.assert_called_once()
    result = output_mock.call_args.args[1]
    assert result["wp_file_update"] == "skipped"
    assert result["status_events_path"] == str(coord_events)


def test_default_ports_constructs_through_tasks_bindings() -> None:
    """The moved ``_default_move_task_ports`` constructs its adapters via the
    ``tasks`` bindings, so ``@patch("...tasks.<Adapter>")`` intercepts
    construction (the WP03 checklist invariant, preserved across the move)."""
    with (
        patch(f"{_TASKS}.seam_coord_router") as router_factory,
        patch(f"{_TASKS}.RealFsReader") as fs_cls,
        patch(f"{_TASKS}.RealGitOps") as git_cls,
        patch(f"{_TASKS}.RealRender") as render_cls,
    ):
        ports = tasks._default_move_task_ports()
    # move_task routes BOTH seams through ``tasks`` (route_emit=True), no target_branch.
    router_factory.assert_called_once_with(route_emit=True)
    assert ports.coord is router_factory.return_value
    assert ports.fs is fs_cls.return_value
    assert ports.git is git_cls.return_value
    assert ports.render is render_cls.return_value


# NOTE (WP06 / #2565): the identity battery
# (``test_tasks_binding_is_tasks_move_task_object``, 51 symbols) and the
# exact-set completeness pin (``test_move_set_matches_tasks_move_task_defs``)
# formerly lived here. Both are RETIRED — mechanically subsumed by WP05's
# consolidated guard, ``test_tasks_compat_surface.py``
# (``test_tasks_binding_is_seam_object`` for identity;
# ``test_guard_symbol_is_genuinely_native_to_its_seam`` +
# ``test_guard_keyset_is_superset_of_all_six_seams_native_defs`` for the
# exact-set claim), which covers the same 51-symbol ``tasks_move_task``
# surface. See the module docstring above for the reconcile ruling on the
# interception battery kept in this file.


# ===========================================================================
# WP06 (review-cycle-verdict-seam-rebuild-01KZ2W7W): the verdict-persistence
# seam extraction. Two batteries below:
#
# 1. ``tasks_verdict_persistence`` direct unit coverage — exercises the four
#    extracted sites' actual logic against real fixtures/fakes (NOT merely
#    re-running the existing ``tasks_move_task`` suite through the new call
#    path), satisfying the ≥90% diff-coverage obligation the move carries.
# 2. Delegation/forwarder interception — proves the three frozen-compat
#    symbols left behind in ``tasks_move_task.py``
#    (``_mt_fire_override_persist``, ``_mt_finalize_plan``'s two call sites,
#    ``_run_arbiter_override``) call straight into the new module rather than
#    re-implementing the extracted logic inline.
# ===========================================================================


def _write_review_cycle_artifact(wp_dir: Path, cycle_n: int, verdict: str) -> Path:
    wp_dir.mkdir(parents=True, exist_ok=True)
    artifact = wp_dir / f"review-cycle-{cycle_n}.md"
    artifact.write_text(
        f"---\ncycle_number: {cycle_n}\nverdict: {verdict}\nwp_id: WP01\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return artifact


# --- resolve_review_verdict_facts (site 1) ----------------------------------


def test_resolve_review_verdict_facts_no_artifacts(tmp_path: Path) -> None:
    """No review-cycle artifacts under the WP dir -> all-``None`` facts."""
    wp_path = tmp_path / "WP01-do-a-thing.md"
    verdict, artifact_path, artifact_name = tasks_verdict_persistence.resolve_review_verdict_facts(
        wp_path
    )
    assert (verdict, artifact_path, artifact_name) == (None, None, None)


def test_resolve_review_verdict_facts_picks_highest_cycle(tmp_path: Path) -> None:
    """WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint: resolves
    the event-sourced verdict (``event_sourced_review_result``), never
    ``review-cycle-N.md`` frontmatter — the exact site-1 shape, now
    event-authority-bound. The on-disk artifacts are written only as
    realistic surrounding state (matching what the real writer leaves
    behind); the returned ``artifact_path`` comes from the event's own
    ``feedback_path``, never a re-glob of the directory.

    Nests the WP file under ``tasks/`` (unlike the flat pre-WP05 fixture)
    so ``wp_path.parent.parent`` resolves to an ISOLATED per-test
    ``tmp_path`` for the event log -- not the shared pytest base tmp dir a
    flat one-level fixture would degrade onto.
    """
    tasks_dir = tmp_path / "tasks"
    wp_path = tasks_dir / "WP01-do-a-thing.md"
    wp_dir = tasks_dir / "WP01-do-a-thing"
    _write_review_cycle_artifact(wp_dir, 1, "rejected")
    cycle2 = _write_review_cycle_artifact(wp_dir, 2, "approved")
    append_event(
        tmp_path,
        StatusEvent(
            event_id="01T023PICKSHIGHEST0000001",
            mission_slug=tmp_path.name,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="approved",
                reference=f"review-cycle://{tmp_path.name}/WP01-do-a-thing/review-cycle-2.md",
                feedback_path=str(cycle2),
            ),
        ),
    )

    verdict, artifact_path, artifact_name = tasks_verdict_persistence.resolve_review_verdict_facts(
        wp_path
    )
    assert verdict == "approved"
    assert artifact_path == cycle2
    assert artifact_name == cycle2.name


def test_mt_gather_review_facts_delegates_to_resolve_review_verdict_facts() -> None:
    """``_mt_gather_review_facts`` (frozen compat symbol) calls straight into
    the extracted resolver rather than resolving the verdict inline."""
    st = _make_state(to="approved")
    st.target_lane = Lane.APPROVED
    st.wp = cast(Any, SimpleNamespace(path=Path("WP01-x.md"), frontmatter=""))
    with (
        patch(f"{_TASKS}._check_unchecked_subtasks", return_value=[]),
        patch(f"{_TASKS}._validate_ready_for_review", return_value=(True, [])),
        patch(
            f"{tasks_move_task.__name__}.resolve_review_verdict_facts",
            return_value=("approved", Path("review-cycle-1.md"), "review-cycle-1.md"),
        ) as resolve_mock,
    ):
        tasks_move_task._mt_gather_review_facts(st)
    resolve_mock.assert_called_once_with(Path("WP01-x.md"))
    assert st.verdict_artifact_path == Path("review-cycle-1.md")
    assert st.request is not None
    assert st.request.review_verdict == "approved"
    assert st.request.review_artifact_name == "review-cycle-1.md"


# --- persist_review_override_before_guard (site 2) --------------------------


def test_persist_review_override_before_guard_noop_without_signal(tmp_path: Path) -> None:
    """No override signal -> the write helper is never reached."""
    st = _make_state()
    st.request = cast(Any, SimpleNamespace())
    st.verdict_artifact_path = tmp_path / "review-cycle-1.md"
    with (
        patch(f"{_VERDICT_SEAM}.override_persist_signal", return_value=False),
        patch(f"{_VERDICT_SEAM}._persist_review_artifact_override") as persist_mock,
    ):
        tasks_verdict_persistence.persist_review_override_before_guard(st)
    persist_mock.assert_not_called()


def test_persist_review_override_before_guard_fires_write(tmp_path: Path) -> None:
    """Signal true + a resolved artifact path -> the write helper fires with
    the exact args the incumbent inline block used."""
    st = _make_state(agent="claude", note="  because reasons  ")
    st.request = cast(Any, SimpleNamespace())
    st.verdict_artifact_path = tmp_path / "review-cycle-1.md"
    st.main_repo_root = tmp_path
    st.task_id = "WP01"
    with (
        patch(f"{_VERDICT_SEAM}.override_persist_signal", return_value=True),
        patch(f"{_VERDICT_SEAM}._persist_review_artifact_override") as persist_mock,
    ):
        tasks_verdict_persistence.persist_review_override_before_guard(st)
    persist_mock.assert_called_once_with(
        st.verdict_artifact_path,
        repo_root=tmp_path,
        wp_id="WP01",
        actor="claude",
        reason="because reasons",
    )


def test_mt_fire_override_persist_forwards_to_verdict_seam() -> None:
    """``_mt_fire_override_persist`` (frozen compat symbol) is a thin
    forwarder onto :func:`persist_review_override_before_guard`."""
    st = _make_state()
    with patch(
        f"{tasks_move_task.__name__}.persist_review_override_before_guard"
    ) as forward_mock:
        tasks_move_task._mt_fire_override_persist(st)
    forward_mock.assert_called_once_with(st)


# --- _persist_approved_review_cycle / persist_rejected_review_cycle_for_rollback (site 3) ---


def test_persist_approved_review_cycle_writes_first_pass_when_no_prior_cycle(
    tmp_path: Path,
) -> None:
    """FR-007 (T2, governance-at-the-gate WP04) — INVERTED from the retired
    ``test_persist_approved_review_cycle_noop_when_no_prior_cycle`` pin.

    Brownfield gap this closes: a genuine first-pass approval (no prior
    event-sourced verdict slot at all) used to be an unconditional no-op, so
    it authored NO ``review-cycle-N.md`` evidence artifact (SC-006). It now
    WRITES an ``approved`` cycle through the already verdict-symmetric
    ``create_rejected_review_cycle(..., verdict="approved")`` writer — the
    SAME writer the stale-rejection flip (:544/:563 below) already used —
    carrying a non-null ``reproduction_command`` (SC-006's "at least a
    reproduction_command").

    WP05 (verdict-seam-write-unification-01KZ9Q35, T023): the "is the current
    verdict a rejection" probe was repointed from ``latest_review_artifact_
    verdict`` (retired) to ``event_sourced_review_result``.
    """
    st = _make_state(to="approved")
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.task_id = "WP01"
    ports = MagicMock()
    with (
        patch(
            f"{_VERDICT_SEAM}.event_sourced_review_result",
            return_value=ReviewResultLookup(slot_present=False, result=None),
        ),
        patch(f"{_VERDICT_SEAM}.create_rejected_review_cycle") as create_mock,
    ):
        tasks_verdict_persistence._persist_approved_review_cycle(st, ports)
    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["verdict"] == "approved"
    assert call_kwargs["reproduction_command"]
    assert "WP01" in call_kwargs["reproduction_command"]
    assert "--to approved" in call_kwargs["reproduction_command"]


def test_persist_approved_review_cycle_noop_on_malformed_slot(tmp_path: Path) -> None:
    """Unchanged fail-safe: a damaged/malformed event-sourced slot
    (``slot_present=True, result=None``) stays a no-op -- distinct from a
    genuine first-pass (``slot_present=False``) — the reader already fails
    closed rather than fabricate a verdict, and this writer must not paper
    over that ambiguity with a synthesized approval write."""
    st = _make_state(to="approved")
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.task_id = "WP01"
    ports = MagicMock()
    with (
        patch(
            f"{_VERDICT_SEAM}.event_sourced_review_result",
            return_value=ReviewResultLookup(slot_present=True, result=None),
        ),
        patch(f"{_VERDICT_SEAM}.create_rejected_review_cycle") as create_mock,
    ):
        tasks_verdict_persistence._persist_approved_review_cycle(st, ports)
    create_mock.assert_not_called()


def test_persist_approved_review_cycle_noop_when_latest_already_approved(tmp_path: Path) -> None:
    """The event-sourced verdict is already ``approved`` -> no redundant write."""
    st = _make_state(to="approved")
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.task_id = "WP01"
    ports = MagicMock()
    lookup = ReviewResultLookup(
        slot_present=True,
        result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="x"),
    )
    with (
        patch(f"{_VERDICT_SEAM}.event_sourced_review_result", return_value=lookup),
        patch(f"{_VERDICT_SEAM}.create_rejected_review_cycle") as create_mock,
    ):
        tasks_verdict_persistence._persist_approved_review_cycle(st, ports)
    create_mock.assert_not_called()


def test_persist_approved_review_cycle_writes_over_stale_rejection(tmp_path: Path) -> None:
    """A stale event-sourced ``changes_requested`` verdict -> a fresh
    ``approved`` cycle is written (FR-001), threading ``ports.coord`` as the
    commit router when auto-commit is resolved on."""
    st = _make_state(to="approved", reviewer="alice", approval_ref="LGTM")
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.task_id = "WP01"
    st.resolved_auto_commit = True
    lookup = ReviewResultLookup(
        slot_present=True,
        result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
    )
    ports = MagicMock()
    with (
        patch(f"{_VERDICT_SEAM}.event_sourced_review_result", return_value=lookup),
        patch(f"{_VERDICT_SEAM}.create_rejected_review_cycle") as create_mock,
    ):
        tasks_verdict_persistence._persist_approved_review_cycle(st, ports)
    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["verdict"] == "approved"
    assert call_kwargs["reviewer_agent"] == "alice"
    assert "Approved by alice: LGTM" in call_kwargs["body"]
    assert call_kwargs["commit_router"] is ports.coord


def test_persist_rejected_review_cycle_for_rollback_writes_and_updates_state(
    tmp_path: Path,
) -> None:
    """The rollback persist writes the rejection cycle and mutates ``st`` in
    place (``review_feedback_pointer`` / ``rejected_review_result``) exactly
    as the incumbent inline block did."""
    st = _make_state()
    st.main_repo_root = tmp_path
    st.mission_slug = "034-feature"
    st.task_id = "WP01"
    st.resolved_feedback_source = tmp_path / "feedback.md"
    st.resolved_feedback_source.write_text("fix this", encoding="utf-8")
    st.agent = "claude"
    st.resolved_auto_commit = False
    review_result = ReviewResult(reviewer="claude", verdict="changes_requested", reference="ref")
    # WP11 (T048/T049/T050, DM-01KZ6JE62Q6CQ24DMBX8KZZ5R9): the rollback
    # writer now also reads ``artifact_path``/``artifact.cycle_number`` off
    # the created cycle to build a ``VerdictDurabilitySignal`` -- the fake
    # needs those two fields alongside the pre-existing ``pointer``/
    # ``review_result`` this test already asserted on.
    fake_cycle = SimpleNamespace(
        pointer="review-cycle://034-feature/WP01/1",
        review_result=review_result,
        artifact_path=tmp_path / "review-cycle-1.md",
        artifact=SimpleNamespace(cycle_number=1),
    )
    ports = MagicMock()
    with patch(
        f"{_VERDICT_SEAM}.create_rejected_review_cycle", return_value=fake_cycle
    ) as create_mock:
        tasks_verdict_persistence.persist_rejected_review_cycle_for_rollback(st, ports)
    create_mock.assert_called_once()
    assert create_mock.call_args.kwargs["feedback_source"] == st.resolved_feedback_source
    assert create_mock.call_args.kwargs["commit_router"] is None  # auto-commit resolved off
    assert st.review_feedback_pointer == fake_cycle.pointer
    assert st.rejected_review_result is review_result


def test_persist_rejected_review_cycle_for_rollback_asserts_feedback_source() -> None:
    """The guard lives at the call site (``_mt_finalize_plan``); this function
    asserts its precondition rather than silently no-op-ing on a broken caller."""
    st = _make_state()
    st.resolved_feedback_source = None
    with pytest.raises(AssertionError):
        tasks_verdict_persistence.persist_rejected_review_cycle_for_rollback(st, MagicMock())


def test_mt_persist_rejection_cycle_threads_reviewer_identity_and_restores_agent() -> None:
    """#4899 (WP01 T004, campsite tidy-first): ``_mt_persist_rejection_cycle``
    (the extracted pointer-restore-and-persist block) threads the resolved
    reviewer identity through ``st.agent`` for the persist call only, then
    restores the caller-declared ``--agent`` immediately after -- and stores
    the persist's return value onto ``st.pending_verdict_write`` -- exactly
    as the former inline block in ``_mt_finalize_plan`` did."""
    st = _make_state(to="doing", agent="declared-agent")
    st.reviewer = "reviewer-rita"
    st.old_lane = Lane.IN_REVIEW
    st.target_lane = Lane.IN_PROGRESS
    seen_agent_during_call: list[str | None] = []

    def _fake_persist(inner_st: Any, _ports: Any) -> str:
        seen_agent_during_call.append(inner_st.agent)
        return "fake-durability-signal"

    ports = MagicMock()
    with patch(
        f"{tasks_move_task.__name__}.persist_rejected_review_cycle_for_rollback",
        side_effect=_fake_persist,
    ) as rollback_mock:
        tasks_move_task._mt_persist_rejection_cycle(st, ports)
    rollback_mock.assert_called_once_with(st, ports)
    assert seen_agent_during_call == ["reviewer-rita"], (
        "the reviewer identity (not the declared --agent) must be threaded through st.agent for the persist call"
    )
    assert st.agent == "declared-agent", "st.agent must be restored to the caller-declared value after the call"
    assert st.pending_verdict_write == "fake-durability-signal"


def test_mt_persist_rejection_cycle_restores_agent_even_on_failure() -> None:
    """The ``finally`` restore must fire even when the persist call raises."""
    st = _make_state(to="doing", agent="declared-agent")
    st.reviewer = None
    ports = MagicMock()
    with (
        patch(
            f"{tasks_move_task.__name__}.persist_rejected_review_cycle_for_rollback",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        tasks_move_task._mt_persist_rejection_cycle(st, ports)
    assert st.agent == "declared-agent"


def test_finalize_plan_delegates_approved_persist() -> None:
    """``_mt_finalize_plan`` calls :func:`_persist_approved_review_cycle`
    rather than running the former closure's body inline."""
    st = _make_state(to="approved")
    st.target_lane = Lane.APPROVED
    st.old_lane = Lane.IN_PROGRESS
    st.resolved_feedback_source = None
    st.decision = cast(
        Any,
        SimpleNamespace(
            plan=SimpleNamespace(canonical_lane="approved"),
            evidence_dict=None,
            note_text=None,
            is_review_rejection=False,
            arbiter_forward=False,
            done_override_note=False,
        ),
    )
    ports = MagicMock()
    with (
        patch(
            f"{tasks_move_task.__name__}.persist_rejected_review_cycle_for_rollback"
        ) as rollback_mock,
        patch(f"{tasks_move_task.__name__}._persist_approved_review_cycle") as approved_mock,
    ):
        tasks_move_task._mt_finalize_plan(st, ports)
    rollback_mock.assert_not_called()
    approved_mock.assert_called_once_with(st, ports)


# --- WP04 (governance-at-the-gate) T1/T2 — approve-gate evidence capture ----


def test_finalize_plan_never_rebuilds_plan_for_forward_approve() -> None:
    """Deliberate NON-widening (see ``_mt_finalize_plan``'s own note): a
    forward ``in_review -> approved`` edge must NOT trigger the
    ``build_transition_plan`` rebuild, even though ``old_lane == IN_REVIEW``.

    An earlier attempt widened this trigger and threaded
    ``st.plan_review_result.reference`` into ``emit_review_ref`` — but that
    value can diverge from the ``hop_review_result`` ``_mt_emit_transitions``
    independently selects on the non-durably-persisted approval path,
    tripping ``_check_review_result_consistency``'s "review_ref must match
    review_result.reference" guard (caught by the REAL CLI integration test
    ``tests/integration/test_review_cycle_rejection_only.py::
    test_approving_a_rejected_wp_writes_no_verdict_artifact`` — a FAKE-ports
    orchestration test never exercises that guard). FR-006's ``review_ref``
    is instead derived per-hop in ``_mt_hop_review_ref``, directly from the
    SAME object used as ``review_result`` — this test pins the NON-rebuild
    half of that fix."""
    st = _make_state(to="approved")
    st.target_lane = Lane.APPROVED
    st.old_lane = Lane.IN_REVIEW
    st.resolved_feedback_source = None
    st.decision = cast(
        Any,
        SimpleNamespace(
            plan=SimpleNamespace(canonical_lane="approved"),
            evidence_dict=None,
            note_text=None,
            is_review_rejection=False,
            arbiter_forward=False,
            done_override_note=False,
        ),
    )
    ports = MagicMock()
    with (
        patch(f"{tasks_move_task.__name__}.build_transition_plan") as build_mock,
        patch(f"{tasks_move_task.__name__}._persist_approved_review_cycle"),
    ):
        tasks_move_task._mt_finalize_plan(st, ports)
    build_mock.assert_not_called()
    assert st.emit_plan is st.decision.plan


class TestMtHopReviewRef:
    """FR-006 (red-first, T1): ``_mt_hop_review_ref`` derives ``review_ref``
    from the SAME ``hop_review_result`` object used as the request's
    ``review_result`` — guaranteeing ``_check_review_result_consistency``
    can never see a mismatch."""

    def test_plan_level_ref_wins_when_set(self) -> None:
        """A backward/rollback hop's plan-level ``emit_review_ref`` always
        wins, unchanged from the pre-WP04 behavior."""
        rr = ReviewResult(reviewer="claude", verdict="rejected", reference="other-ref")
        assert (
            tasks_move_task._mt_hop_review_ref("plan-ref", Lane.PLANNED, rr)
            == "plan-ref"
        )

    def test_derives_from_hop_review_result_for_approved(self) -> None:
        rr = ReviewResult(
            reviewer="reviewer-renata", verdict="approved", reference="approval:WP01"
        )
        assert (
            tasks_move_task._mt_hop_review_ref(None, Lane.APPROVED, rr) == "approval:WP01"
        )

    def test_derives_from_hop_review_result_for_done(self) -> None:
        rr = ReviewResult(reviewer="claude", verdict="approved", reference="done:WP01")
        assert tasks_move_task._mt_hop_review_ref(None, Lane.DONE, rr) == "done:WP01"

    def test_none_for_untouched_lane(self) -> None:
        rr = ReviewResult(reviewer="claude", verdict="approved", reference="x")
        assert tasks_move_task._mt_hop_review_ref(None, Lane.CLAIMED, rr) is None

    def test_none_when_hop_review_result_absent(self) -> None:
        assert tasks_move_task._mt_hop_review_ref(None, Lane.APPROVED, None) is None


class TestBindingRoleForLane:
    """FR-006 (T1): ``_binding_role_for_lane`` grows an APPROVED/DONE arm."""

    def test_claimed_is_implementer(self) -> None:
        assert _binding_role_for_lane(Lane.CLAIMED) == "implementer"

    def test_in_review_is_reviewer(self) -> None:
        assert _binding_role_for_lane(Lane.IN_REVIEW) == "reviewer"

    def test_approved_is_reviewer(self) -> None:
        assert _binding_role_for_lane(Lane.APPROVED) == "reviewer"

    def test_done_is_reviewer(self) -> None:
        assert _binding_role_for_lane(Lane.DONE) == "reviewer"

    def test_planned_is_none(self) -> None:
        assert _binding_role_for_lane(Lane.PLANNED) is None


class TestApprovalPolicyMetadata:
    """FR-006 (red-first, T1): the APPROVED/DONE hop's ``policy_metadata``
    sidecar — non-null, carrying ``tool``/``profile``/``model``/``shell_pid``,
    shaped like ``build_claim_policy_metadata`` (a flat dict of primitives)."""

    def test_populates_tool_profile_model_shell_pid(self) -> None:
        st = _make_state(to="approved", shell_pid="4242")
        st.request = cast(Any, SimpleNamespace(effective_reviewer="reviewer-renata"))
        st.resolved_binding = ResolvedBinding(
            agent_profile="reviewer-renata", model="claude-sonnet-5"
        )
        metadata = _mt_approval_policy_metadata(st)
        assert metadata == {
            "tool": "reviewer-renata",
            "profile": "reviewer-renata",
            "model": "claude-sonnet-5",
            "shell_pid": "4242",
        }

    def test_non_null_even_with_no_binding_or_request(self) -> None:
        """SC-006: the sidecar is ALWAYS present (never omitted) — an absent
        binding/request degrades to explicit ``None`` fields, not a missing
        dict."""
        st = _make_state(to="approved", agent="claude")
        st.request = None
        st.resolved_binding = None
        metadata = _mt_approval_policy_metadata(st)
        assert metadata == {"tool": "claude", "profile": None, "model": None}
        assert "shell_pid" not in metadata

    def test_tool_falls_back_through_reviewer_agent_actor(self) -> None:
        st = _make_state(to="approved")
        st.request = None
        st.reviewer = None
        st.agent = None
        st.actor = "user"
        st.resolved_binding = None
        metadata = _mt_approval_policy_metadata(st)
        assert metadata["tool"] == "user"

    def test_mt_hop_policy_metadata_routes_approved_and_done(self) -> None:
        st = _make_state(to="approved", agent="claude")
        st.request = None
        st.resolved_binding = None
        for target in (Lane.APPROVED, Lane.DONE):
            metadata = _mt_hop_policy_metadata(st, target)
            assert metadata is not None
            assert metadata["tool"] == "claude"

    def test_mt_hop_policy_metadata_none_for_untouched_lanes(self) -> None:
        st = _make_state(to="doing")
        assert _mt_hop_policy_metadata(st, Lane.IN_REVIEW) is None
        assert _mt_hop_policy_metadata(st, Lane.PLANNED) is None


def test_finalize_plan_delegates_rollback_persist(tmp_path: Path) -> None:
    """``_mt_finalize_plan`` calls
    :func:`persist_rejected_review_cycle_for_rollback` for the planned-rollback
    path rather than running the former inline block."""
    st = _make_state(to="planned")
    st.target_lane = Lane.PLANNED
    st.old_lane = Lane.IN_PROGRESS
    st.resolved_feedback_source = tmp_path / "feedback.md"
    st.decision = cast(
        Any,
        SimpleNamespace(
            plan=SimpleNamespace(canonical_lane="planned"),
            evidence_dict=None,
            note_text=None,
            is_review_rejection=True,
            arbiter_forward=False,
            done_override_note=False,
        ),
    )
    ports = MagicMock()
    with (
        patch(f"{tasks_move_task.__name__}.build_transition_plan") as build_mock,
        patch(
            f"{tasks_move_task.__name__}.persist_rejected_review_cycle_for_rollback"
        ) as rollback_mock,
        patch(f"{tasks_move_task.__name__}._persist_approved_review_cycle") as approved_mock,
    ):
        tasks_move_task._mt_finalize_plan(st, ports)
    rollback_mock.assert_called_once_with(st, ports)
    approved_mock.assert_not_called()
    build_mock.assert_called_once()


# --- persist_arbiter_override_decision (site 4) -----------------------------


def test_persist_arbiter_override_decision_success_prints_and_persists(
    tmp_path: Path,
) -> None:
    """The happy path persists the decision and prints both console lines,
    matching the incumbent inline try block exactly."""
    from specify_cli.review.arbiter import ArbiterCategory, create_arbiter_decision

    decision = create_arbiter_decision(
        arbiter_name="claude", category="wrong_context", explanation="wrong WP"
    )
    feature_dir = tmp_path / "feature"
    persisted_path = tmp_path / "arbiter-override-1.json"
    with (
        patch(f"{_TASKS}.console") as console_mock,
        patch(
            "specify_cli.review.arbiter.persist_arbiter_decision",
            return_value=persisted_path,
        ) as persist_mock,
    ):
        tasks_verdict_persistence.persist_arbiter_override_decision(
            feature_dir=feature_dir,
            wp_id="WP01",
            review_ref="review-cycle://034-feature/WP01/1",
            decision=decision,
            category=ArbiterCategory.WRONG_CONTEXT,
            explanation="wrong WP",
            json_output=False,
            main_repo_root=tmp_path,
        )
    persist_mock.assert_called_once_with(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref="review-cycle://034-feature/WP01/1",
        decision=decision,
        repo_root=tmp_path,
    )
    assert console_mock.print.call_count == 2


def test_persist_arbiter_override_decision_json_output_suppresses_console(
    tmp_path: Path,
) -> None:
    """``json_output=True`` never prints, but the persist call still fires."""
    from specify_cli.review.arbiter import ArbiterCategory, create_arbiter_decision

    decision = create_arbiter_decision(
        arbiter_name="claude", category="custom", explanation="custom reason"
    )
    with (
        patch(f"{_TASKS}.console") as console_mock,
        patch(
            "specify_cli.review.arbiter.persist_arbiter_decision",
            return_value=tmp_path / "x.json",
        ) as persist_mock,
    ):
        tasks_verdict_persistence.persist_arbiter_override_decision(
            feature_dir=tmp_path / "feature",
            wp_id="WP01",
            review_ref=None,
            decision=decision,
            category=ArbiterCategory.CUSTOM,
            explanation="custom reason",
            json_output=True,
            main_repo_root=tmp_path,
        )
    persist_mock.assert_called_once()
    console_mock.print.assert_not_called()


def test_persist_arbiter_override_decision_propagates_persist_error(
    tmp_path: Path,
) -> None:
    """T054 (FR-009/FR-010/FR-011, WP12, DM-01KZ6X4Y7A3XPK5AJ96AA49XJ9):
    RE-PINNED. A raising persist call used to degrade to a dim console
    warning and swallow the exception -- silent under ``--json`` (the
    ``if not json_output:`` guard meant NO output at all in that mode). Once
    T051/T052 retire the frontmatter/JSON-sidecar fallbacks, the event-sourced
    ``ReviewOverride`` emit inside ``persist_arbiter_decision`` is the ONLY
    durable record of an override -- a failure here is not a best-effort
    side effect to warn-and-continue past. The exception now propagates
    (this function no longer catches it at all) to
    ``tasks_move_task.py``'s existing outer ``except Exception as e:``
    handler, which already reports failures correctly under both ``--json``
    and plain output -- see that module's ``_do_move_task``. This test
    asserts the NEW contract: the call raises, and no success/console
    output is produced by this function on the way out.
    """
    from specify_cli.review.arbiter import ArbiterCategory, create_arbiter_decision

    decision = create_arbiter_decision(
        arbiter_name="claude", category="custom", explanation="custom reason"
    )
    with (
        patch(f"{_TASKS}.console") as console_mock,
        patch(
            "specify_cli.review.arbiter.persist_arbiter_decision",
            side_effect=OSError("disk full"),
        ),
        pytest.raises(OSError, match="disk full"),
    ):
        tasks_verdict_persistence.persist_arbiter_override_decision(
            feature_dir=tmp_path / "feature",
            wp_id="WP01",
            review_ref=None,
            decision=decision,
            category=ArbiterCategory.CUSTOM,
            explanation="custom reason",
            json_output=False,
            main_repo_root=tmp_path,
        )
    console_mock.print.assert_not_called()


def test_run_arbiter_override_delegates_persist_to_verdict_seam(tmp_path: Path) -> None:
    """``_run_arbiter_override`` (frozen compat symbol) builds the decision
    and calls straight into :func:`persist_arbiter_override_decision` instead
    of running the persist try/except inline.

    FR-016 (WP07): also pins that this function's own already-resolved
    ``main_repo_root`` parameter is forwarded to ``persist_arbiter_override_
    decision`` rather than dropped on the floor -- the regression this WP
    fixes (the downstream ``persist_arbiter_decision`` no longer self-infers
    it from ``feature_dir.parent.parent``, which is wrong under a
    coordination topology).
    """
    other_root = tmp_path / "resolved-main-repo-root"
    fake_event = SimpleNamespace(wp_id="WP01", review_ref="review-cycle://034-feature/WP01/1")
    with (
        patch(f"{_TASKS}.read_events_transactional", return_value=[fake_event]),
        patch(
            f"{tasks_move_task.__name__}.persist_arbiter_override_decision"
        ) as persist_mock,
    ):
        result = tasks_move_task._run_arbiter_override(
            feature_dir=tmp_path,
            mission_slug="034-feature",
            main_repo_root=other_root,
            task_id="WP01",
            note_text="pre_existing_failure: flaky in CI",
            agent="claude",
            json_output=False,
        )
    persist_mock.assert_called_once()
    call_kwargs = persist_mock.call_args.kwargs
    assert call_kwargs["feature_dir"] == tmp_path
    assert call_kwargs["wp_id"] == "WP01"
    assert call_kwargs["review_ref"] == "review-cycle://034-feature/WP01/1"
    assert call_kwargs["json_output"] is False
    assert call_kwargs["main_repo_root"] == other_root
    assert result == "review-cycle://034-feature/WP01/1"


# ===========================================================================
# WP01 (review-feedback-to-implementer-01M3GKZ8, #4899) -- SC-001/SC-002
# red-first regression battery, T001.
#
# Real-CLI, real-git harness (mirrors ``tests/integration/
# test_review_cycle_rejection_only.py::for_review_repo``, extended one hop
# further into ``in_review`` so the two rejection edges under test --
# ``in_review -> planned`` and ``in_review -> in_progress`` (the
# re-implement/"doing" edge) -- both start from a genuine in-review WP.
# ===========================================================================

_PARITY_MISSION_SLUG = "001-parity-mission"
_PARITY_WP_SLUG = "WP01-test-task"
_FEEDBACK_BODY = "## Reviewer feedback\n\nAlign the widget margin and add the missing docstring.\n"


def _write_parity_wp(wp_path: Path) -> None:
    write_frontmatter(
        wp_path,
        {
            "work_package_id": "WP01",
            "subtasks": ["T001"],
            "title": "Test Task",
            "phase": "Phase 1",
            "lane": "planned",
            "dependencies": [],
            "assignee": "",
            "agent": "claude",
            "shell_pid": "",
            "review_status": "none",
            "review_feedback": "",
            "history": [],
        },
        "# WP01 Prompt\n",
    )


def _build_in_review_repo(root: Path, mission_slug: str = _PARITY_MISSION_SLUG) -> tuple[Path, Path, Path]:
    """Build a git repo with one WP driven event-by-event into ``in_review``.

    Returns ``(repo_root, feature_dir, sub_artifact_dir)``. The lifecycle hops
    (``planned -> claimed -> in_progress -> for_review -> in_review``) are
    written directly to the event log (mirrors the existing integration
    fixtures) so the two edges under test start from an identical, genuine
    in-review WP -- only the REAL ``move-task`` CLI invocation under test is
    driven through the real command surface.
    """
    repo = root / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)

    (repo / ".kittify").mkdir()

    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "mission_slug": mission_slug,
                "created_at": "2026-09-27T00:00:00Z",
                "friendly_name": mission_slug,
                "mission": "software-dev",
                "slug": mission_slug,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=f"mission-{mission_slug}",
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-09-27T00:00:00Z",
            computed_from="test",
        ),
    )
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    _write_parity_wp(tasks_dir / f"{_PARITY_WP_SLUG}.md")

    hops: tuple[tuple[Lane, Lane], ...] = (
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW),
    )
    for index, (from_lane, to_lane) in enumerate(hops, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"01PARITY{str(index).zfill(18)}",
                mission_slug=mission_slug,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-09-27T12:00:{index:02d}Z",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed in-review fixture"], cwd=repo, check=True, capture_output=True)

    sub_artifact_dir = feature_dir / "tasks" / _PARITY_WP_SLUG
    return repo, feature_dir, sub_artifact_dir


def _move_task_cli(
    *,
    mission_slug: str,
    to: str,
    feedback_file: Path | None,
    agent: str = "reviewer-rita",
) -> Any:
    """Invoke the REAL ``move-task`` CLI. Caller must already have chdir'd
    (``monkeypatch.chdir``) into the target repo."""
    args = [
        "move-task",
        "WP01",
        "--to",
        to,
        "--mission",
        mission_slug,
        "--agent",
        agent,
        "--no-auto-commit",
    ]
    if feedback_file is not None:
        args += ["--review-feedback-file", str(feedback_file)]
    runner = CliRunner()
    return runner.invoke(tasks.app, args)


@pytest.mark.regression
class TestReviewRejectionEdgeValueParity:
    """SC-001 (#4899, issue-pinned): ``in_review -> in_progress`` (the
    re-implement edge) must match ``in_review -> planned`` BY VALUE on a
    shared feedback fixture -- a committed review-cycle record, a populated
    feedback location, a resolvable ``review-cycle://`` reference, and (gate
    5 coverage) the EMITTED event's ``review_result`` matching field-for-field
    -- NOT the approval-shaped fallback (``verdict=approved``,
    ``reference="auto-forward:<WP>"``). This assertion fails if
    ``_mt_hop_review_result`` (gate 5) is not ALSO routed through the
    rejection-edge predicate, so the fix cannot be masked by gates 1-4 alone.
    """

    def test_reimplement_edge_matches_planned_edge_by_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_planned, feature_dir_planned, sub_planned = _build_in_review_repo(tmp_path / "planned-side")
        repo_reimpl, feature_dir_reimpl, sub_reimpl = _build_in_review_repo(tmp_path / "reimpl-side")

        feedback_planned = repo_planned / "feedback.md"
        feedback_planned.write_text(_FEEDBACK_BODY, encoding="utf-8")
        feedback_reimpl = repo_reimpl / "feedback.md"
        feedback_reimpl.write_text(_FEEDBACK_BODY, encoding="utf-8")

        monkeypatch.chdir(repo_planned)
        result_planned = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="planned", feedback_file=feedback_planned)
        monkeypatch.chdir(repo_reimpl)
        result_reimpl = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_reimpl)

        assert result_planned.exit_code == 0, result_planned.stdout
        assert result_reimpl.exit_code == 0, result_reimpl.stdout

        # (a) a committed review-cycle-<N>.md record exists on BOTH edges.
        artifact_planned = ReviewCycleArtifact.latest(sub_planned)
        artifact_reimpl = ReviewCycleArtifact.latest(sub_reimpl)
        assert artifact_planned is not None
        assert artifact_reimpl is not None, (
            "the re-implement edge (in_review -> in_progress) produced no "
            "review-cycle record -- gates 1/2 are not routed through the "
            "rejection-edge predicate."
        )

        # (b) the feedback body is populated and equal BY VALUE to the input,
        # and matches the sibling ->planned edge on the same fixture.
        assert artifact_reimpl.body.strip() == _FEEDBACK_BODY.strip()
        assert artifact_reimpl.body == artifact_planned.body
        assert artifact_reimpl.cycle_number == artifact_planned.cycle_number == 1

        events_planned = read_events(feature_dir_planned)
        events_reimpl = read_events(feature_dir_reimpl)
        event_planned = events_planned[-1]
        event_reimpl = events_reimpl[-1]

        # (c) the emitted review_ref is resolvable on BOTH edges -- never the
        # non-resolvable synthetic ``review:<WP>`` marker.
        assert event_planned.review_ref is not None
        assert event_reimpl.review_ref is not None
        assert is_non_resolvable_review_ref(event_planned.review_ref) is False
        assert is_non_resolvable_review_ref(event_reimpl.review_ref) is False, (
            f"expected a resolvable review-cycle:// pointer, got "
            f"{event_reimpl.review_ref!r} -- gate 3 is not routed through "
            "the rejection-edge predicate."
        )
        assert event_reimpl.review_ref.startswith("review-cycle://")
        assert event_reimpl.review_ref == event_planned.review_ref

        # (d) GATE 5 COVERAGE: the EMITTED event's review_result matches the
        # in_review -> planned edge BY VALUE (reviewer/verdict/reference) --
        # NOT the approval-shaped fallback. This is the assertion that fails
        # if only gates 1-4 are routed and gate 5 (``_mt_hop_review_result``)
        # is left selecting the ``target == Lane.PLANNED`` arm alone.
        assert event_planned.review_result is not None
        assert event_reimpl.review_result is not None, (
            "the re-implement edge emitted no review_result at all -- gate 5 "
            "(_mt_hop_review_result) is not routed through the predicate."
        )
        assert event_reimpl.review_result.verdict == event_planned.review_result.verdict == "changes_requested"
        assert event_reimpl.review_result.reviewer == event_planned.review_result.reviewer
        assert event_reimpl.review_result.reference == event_planned.review_result.reference
        assert event_reimpl.review_result.reference == event_reimpl.review_ref
        assert event_reimpl.review_result.verdict != "approved", (
            "the re-implement edge's emitted review_result is approval-shaped "
            "-- gate 5 fell through to the auto-forward branch instead of "
            "returning the rejection result."
        )
        assert event_reimpl.review_result.reference != f"auto-forward:{'WP01'}"


@pytest.mark.regression
class TestReimplementEdgeRequiresRationale:
    """SC-002 (#4899, issue-pinned): a no-rationale rejection on the
    re-implement edge (``in_review -> in_progress``) is REFUSED as an
    observable failure (non-zero exit, no recorded transition) -- never a
    logged no-op that still advances the lane. Paired with an accepted
    with-rationale rejection on the SAME fixture."""

    def test_no_rationale_refused_then_with_rationale_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, feature_dir, _sub = _build_in_review_repo(tmp_path / "sc-002")
        monkeypatch.chdir(repo)

        refused = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=None)

        assert refused.exit_code != 0, (
            "a no-rationale in_review -> in_progress rejection must be "
            f"refused (non-zero exit), got {refused.exit_code}. "
            f"stdout:\n{refused.stdout}"
        )
        events_after_refusal = read_events(feature_dir)
        assert events_after_refusal[-1].to_lane == Lane.IN_REVIEW, (
            "a refused move must never still record the transition -- latest "
            f"event is {events_after_refusal[-1].to_lane}, expected it to "
            "remain in_review."
        )

        feedback_file = repo / "feedback.md"
        feedback_file.write_text(_FEEDBACK_BODY, encoding="utf-8")
        accepted = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_file)

        assert accepted.exit_code == 0, accepted.stdout
        events_after_accept = read_events(feature_dir)
        assert events_after_accept[-1].to_lane == Lane.IN_PROGRESS


def _seconds_after_latest_event(feature_dir: Path, *offsets: int) -> list[str]:
    """ISO-8601 timestamps ``offsets`` seconds after the latest status event."""
    latest = parse_iso(read_events(feature_dir)[-1].at.replace("Z", "+00:00"))
    return [(latest + timedelta(seconds=offset)).isoformat() for offset in offsets]


@pytest.mark.regression
class TestFr008ReviewCycleCounterOnReimplementEdge:
    """FR-008 (conditional, #3451): the review-cycle counter must increment
    EXACTLY ONCE per real rejection on the re-implement edge. WP01's fix
    routes this edge through a SINGLE persist call site
    (``_mt_persist_rejection_cycle``, called once per CLI invocation from
    ``_mt_finalize_plan``) -- this scenario proves the counter does not
    reproduce #3451's double-increment on the newly-routed edge. See the WP
    Activity Log for the disposition (does not reproduce; recorded
    out-of-scope reasoning)."""

    def test_two_sequential_reimplement_rejections_advance_by_exactly_one_each(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, feature_dir, sub_artifact_dir = _build_in_review_repo(tmp_path / "fr-008")
        monkeypatch.chdir(repo)

        feedback_1 = repo / "feedback-1.md"
        feedback_1.write_text("## Cycle 1 issues\n\nFix the off-by-one.\n", encoding="utf-8")
        first = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_1)
        assert first.exit_code == 0, first.stdout

        latest_after_first = ReviewCycleArtifact.latest(sub_artifact_dir)
        assert latest_after_first is not None
        assert latest_after_first.cycle_number == 1, (
            "expected the FIRST rejection to allocate cycle 1 exactly once, "
            f"got {latest_after_first.cycle_number} -- a value of 2+ here "
            "would indicate a double-increment on a single rejection."
        )

        # Drive the WP back through for_review -> in_review for a genuine
        # second review round (mirrors the real implement/review lifecycle).
        # Stamp the hand-appended events AFTER the first rejection, which the
        # CLI stamped with the wall clock: a fixed literal timestamp sorts
        # before it once the clock passes the literal, and the lane reducer
        # then sees in_progress -> in_progress.
        second_round_at = _seconds_after_latest_event(feature_dir, 1, 2)
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01PARITYSECONDROUND000001",
                mission_slug=_PARITY_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at=second_round_at[0],
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01PARITYSECONDROUND000002",
                mission_slug=_PARITY_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.IN_REVIEW,
                at=second_round_at[1],
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

        feedback_2 = repo / "feedback-2.md"
        feedback_2.write_text("## Cycle 2 issues\n\nFix the remaining edge case.\n", encoding="utf-8")
        second = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_2)
        assert second.exit_code == 0, second.stdout

        latest_after_second = ReviewCycleArtifact.latest(sub_artifact_dir)
        assert latest_after_second is not None
        assert latest_after_second.cycle_number == 2, (
            "expected the SECOND rejection to advance the counter by EXACTLY "
            f"one (1 -> 2), got {latest_after_second.cycle_number} -- "
            "#3451's double-increment would show 3+ here."
        )
        cycle_files = sorted(p.name for p in sub_artifact_dir.glob("review-cycle-*.md"))
        assert cycle_files == ["review-cycle-1.md", "review-cycle-2.md"], (
            f"expected exactly two review-cycle artifacts (1 and 2), got: {cycle_files}"
        )
