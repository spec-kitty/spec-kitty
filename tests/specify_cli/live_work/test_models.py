"""Per-kind model validation — the honest-shape tests.

Mirrors the shared contract's own conformance posture: an enum registration
alone is not capture coverage; every emitted kind must have a
constructible, validated shape, and the dishonest shapes (a pre-result
observation inventing an outcome, a failure without inline text, a
delegation without a counterpart, an un-namespaced extension) must fail
closed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from specify_cli.live_work.kinds import WorkEmissionKind
from specify_cli.live_work.models import (
    ActivityBinding,
    ActorBinding,
    CoverageDetail,
    FileDetail,
    FileOperation,
    MissionBinding,
    Observation,
    Provenance,
    RepositoryBinding,
    SessionBinding,
    TestRunDetail,
    ToolDetail,
    ToolOutcome,
    ToolState,
    UnknownActor,
)
from tests.specify_cli.live_work.test_kinds import SHARED_CONTRACT_KINDS

pytestmark = pytest.mark.fast


def _observation(**overrides) -> Observation:
    """A minimal valid tool observation, overridable per test."""
    base = {
        "kind": WorkEmissionKind.TOOL_INVOKED,
        "session": SessionBinding(session_id="sess-1"),
        "actor": ActorBinding(harness="claude"),
        "repository": RepositoryBinding(slug="acme/repo"),
        "provenance": Provenance(source="harness_hook", capability="live-work.test"),
        "action": ToolDetail(tool="Bash", state=ToolState.RESULT, outcome=ToolOutcome.SUCCESS),
        "occurred_at": "2026-09-14T12:00:00+00:00",
    }
    base.update(overrides)
    return Observation(**base)


def test_every_emitted_kind_has_a_constructible_shape() -> None:
    # Every kind in the emission set is constructible with its own honest
    # minimal shape — no inert enum members.
    shapes: dict[WorkEmissionKind, dict] = {
        WorkEmissionKind.SESSION_STARTED: {"text": "session started"},
        WorkEmissionKind.SESSION_ENDED: {"text": "session ended"},
        WorkEmissionKind.DELEGATION_STARTED: {"counterpart": "general-purpose", "text": "delegated"},
        WorkEmissionKind.DELEGATION_ENDED: {"counterpart": "general-purpose", "text": "delegation ended"},
        WorkEmissionKind.TOOL_INVOKED: {"action": ToolDetail(tool="Bash", state=ToolState.RESULT, outcome=ToolOutcome.SUCCESS)},
        WorkEmissionKind.FILE_EDITED: {"action": FileDetail(operation=FileOperation.EDIT, path="src/a.py", bytes_added=10, bytes_removed=2)},
        WorkEmissionKind.TEST_EXECUTED: {
            "action": TestRunDetail(
                selector="pytest::tests/a.py",
                state=ToolState.RESULT,
                passed=5,
                failed=0,
                skipped=0,
                outcome=ToolOutcome.SUCCESS,
            )
        },
        WorkEmissionKind.RETROSPECTIVE_CAPTURED: {"text": "retrospective captured"},
        WorkEmissionKind.RETROSPECTIVE_FAILED: {"text": "retrospective failed: generator error"},
        WorkEmissionKind.RETROSPECTIVE_SKIPPED: {"text": "retrospective skipped: cli_flag"},
        WorkEmissionKind.COVERAGE_GAP: {"coverage": CoverageDetail(area="claude-code-capture")},
        # #4269's authored kinds: the prose is the observation.
        WorkEmissionKind.NARRATIVE_INTENT_DECLARED: {"text": "intent: ship the launcher", "action": None},
        WorkEmissionKind.NARRATIVE_PROGRESS_REPORTED: {"text": "progress: WP02 done", "action": None},
        WorkEmissionKind.NARRATIVE_QUESTION_ASKED: {"text": "which tag ships?", "action": None},
        WorkEmissionKind.NARRATIVE_QUESTION_ANSWERED: {"text": "the stable 4.x tag", "action": None},
        WorkEmissionKind.NARRATIVE_DECISION_RECORDED: {"text": "decision: pin the stable tag", "action": None},
        WorkEmissionKind.NARRATIVE_HANDOFF_PERFORMED: {"text": "handoff to reviewer", "action": None},
        WorkEmissionKind.NARRATIVE_BLOCKER_RAISED: {"text": "blocked on relay auth", "action": None},
        WorkEmissionKind.NARRATIVE_BLOCKER_RESOLVED: {"text": "relay auth fixed", "action": None},
        WorkEmissionKind.NARRATIVE_NEXT_PROPOSED: {"text": "next: run the walkthrough", "action": None},
        WorkEmissionKind.MESSAGE_PEER_SENT: {"text": "peer reply", "action": None},
    }
    assert set(shapes) == set(WorkEmissionKind)
    for kind, overrides in shapes.items():
        observation = _observation(kind=kind, **overrides)
        assert observation.kind.value in SHARED_CONTRACT_KINDS


def test_started_tool_must_not_invent_an_outcome() -> None:
    with pytest.raises(ValidationError):
        ToolDetail(tool="Bash", state=ToolState.STARTED, outcome=ToolOutcome.SUCCESS)


def test_result_tool_requires_an_outcome() -> None:
    with pytest.raises(ValidationError):
        ToolDetail(tool="Bash", state=ToolState.RESULT)


def test_cancelled_is_a_first_class_terminal_state() -> None:
    detail = ToolDetail(tool="Bash", state=ToolState.CANCELLED)
    assert detail.outcome is None


def test_pre_result_test_must_not_invent_counts() -> None:
    with pytest.raises(ValidationError):
        TestRunDetail(selector="pytest", state=ToolState.RUNNING, passed=1)


def test_result_test_requires_counts() -> None:
    with pytest.raises(ValidationError):
        TestRunDetail(selector="pytest", state=ToolState.RESULT, outcome=ToolOutcome.FAILURE)


def test_rename_requires_destination_and_only_rename_carries_it() -> None:
    with pytest.raises(ValidationError):
        FileDetail(operation=FileOperation.RENAME, path="a.py", bytes_added=0, bytes_removed=0)
    with pytest.raises(ValidationError):
        FileDetail(
            operation=FileOperation.EDIT,
            path="a.py",
            destination_path="b.py",
            bytes_added=0,
            bytes_removed=0,
        )


def test_failure_and_skip_lifecycle_kinds_require_inline_text() -> None:
    for kind in (WorkEmissionKind.RETROSPECTIVE_FAILED, WorkEmissionKind.RETROSPECTIVE_SKIPPED):
        with pytest.raises(ValidationError):
            _observation(kind=kind)


def test_delegation_requires_a_named_counterpart() -> None:
    with pytest.raises(ValidationError):
        _observation(kind=WorkEmissionKind.DELEGATION_STARTED, text="delegated")
    # Either the child-side parent link or the counterpart names it.
    ok = _observation(
        kind=WorkEmissionKind.DELEGATION_STARTED,
        session=SessionBinding(session_id="child-1", parent_session_id="parent-1"),
        text="delegated",
    )
    assert ok.session.parent_session_id == "parent-1"


def test_action_kinds_must_not_carry_inline_text() -> None:
    with pytest.raises(ValidationError):
        _observation(text="prose on a tool action")
    with pytest.raises(ValidationError):
        _observation(
            kind=WorkEmissionKind.FILE_EDITED,
            action=FileDetail(operation=FileOperation.EDIT, path="a.py", bytes_added=1, bytes_removed=0),
            text="prose on a file action",
        )


def test_extension_keys_must_be_x_namespaced() -> None:
    with pytest.raises(ValidationError):
        _observation(extensions={"summary": "pytest -q"})
    ok = _observation(extensions={"x-summary": "pytest -q"})
    assert ok.extensions == {"x-summary": "pytest -q"}


def test_unknown_actor_is_a_first_class_shape() -> None:
    observation = _observation(actor=UnknownActor())
    assert observation.actor.unknown is True


def test_action_kind_requires_its_typed_detail() -> None:
    with pytest.raises(ValidationError):
        _observation(kind=WorkEmissionKind.FILE_EDITED)  # missing FileDetail
    with pytest.raises(ValidationError):
        _observation(
            kind=WorkEmissionKind.TEST_EXECUTED,
            action=ToolDetail(tool="Bash", state=ToolState.RESULT, outcome=ToolOutcome.SUCCESS),
        )


def test_coverage_detail_only_on_coverage_kind() -> None:
    with pytest.raises(ValidationError):
        _observation(coverage=CoverageDetail(area="x"))


def test_mission_binding_is_optional_and_never_defaulted() -> None:
    observation = _observation()
    assert observation.mission is None
    bound = _observation(mission=MissionBinding(mission_id="01HXYZMISSIONID0000000000ABCD"))
    assert bound.mission is not None
    assert bound.mission.mission_id == "01HXYZMISSIONID0000000000ABCD"


def test_activity_lineage_preserves_parent() -> None:
    observation = _observation(activity=ActivityBinding(activity_id="child-act", parent_activity_id="parent-act"))
    assert observation.activity is not None
    assert observation.activity.parent_activity_id == "parent-act"


def test_extra_fields_fail_closed() -> None:
    with pytest.raises(ValidationError):
        _observation(stdout="leaked")  # type: ignore[call-arg]
