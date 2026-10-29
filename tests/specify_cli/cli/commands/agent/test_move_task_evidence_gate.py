"""The ``move-task`` evidence and independence gates on every topology (#6715).

``_mt_require_implementation_evidence`` refuses an unforced move that crosses into review
territory when the work package's evidence window (the one consolidate reads, through
``consolidation/wp_evidence.py``) holds no change to its owned files.
``_mt_require_independent_approval`` refuses an unforced move into ``approved``/``done`` by the
implementer's own ``tool:model:profile`` identity. ``--force`` bypasses both (ruling 3); an owned
checkout keeps its own evidence gate; an unknown implementer or approver does not refuse at the
move (accept and consolidate stay strict).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from mission_runtime import ActionContextError, OwnedCheckout
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.consolidation import wp_evidence
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes import single_branch_landing
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.resolved_binding import ResolvedBinding

pytestmark = [pytest.mark.unit]

_PLANNING_COMMIT = "plan0000"


def _lane(lane_id: str, wp_ids: tuple[str, ...], depends_on: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=wp_ids, write_scope=(), predicted_surfaces=(), depends_on_lanes=depends_on, parallel_group=0)


def _manifest(*lanes: ExecutionLane, planning_commit: str | None = _PLANNING_COMMIT) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="fx",
        mission_id=None,
        mission_branch="kitty/mission-fx",
        target_branch="main",
        lanes=list(lanes),
        computed_at="2026-10-27T00:00:00+00:00",
        computed_from="test",
        planning_commit_sha=planning_commit,
    )


def _state(target_lane: Lane, *, old_lane: Lane = Lane.IN_PROGRESS, force: bool = False, agent: str | None = "claude") -> move_task_module._MoveTaskState:
    return move_task_module._MoveTaskState(
        task_id="WP02",
        to=target_lane.value,
        mission="fx",
        agent=agent,
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
        force=force,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        target_lane=target_lane,
        feature_dir=Path("kitty-specs/fx"),
        old_lane=old_lane,
    )


@dataclass
class _Facts:
    """A lanes Mission whose WP02 sits on code lane-b; ``paths`` steers each window's changed paths."""

    manifest: LanesManifest | None
    paths: dict[tuple[str, str], set[str] | Exception] = field(default_factory=dict)
    windows: list[tuple[str, str]] = field(default_factory=list)


@pytest.fixture
def lanes_mission(monkeypatch: pytest.MonkeyPatch) -> _Facts:
    facts = _Facts(manifest=_manifest(_lane("lane-a", ("WP01",)), _lane("lane-b", ("WP02",))))

    def _paths(_repo: Path, window: tuple[str, str], _slug: str) -> frozenset[str]:
        facts.windows.append(window)
        found = facts.paths.get(window, set())
        if isinstance(found, Exception):
            raise found
        return frozenset(found)

    monkeypatch.setattr(move_task_module, "_mt_lanes_manifest", lambda _st: facts.manifest)
    monkeypatch.setattr(single_branch_landing, "is_single_branch_mission", lambda _repo, _manifest: False)
    monkeypatch.setattr(wp_evidence, "evidence_paths", _paths)
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: ("tools/check.sh",))
    return facts


def _lane_b_window() -> tuple[str, str]:
    return (_PLANNING_COMMIT, "kitty/mission-fx-lane-b")


# ---------------------------------------------------------------- evidence


@pytest.mark.parametrize("target_lane", [Lane.FOR_REVIEW, Lane.APPROVED, Lane.DONE])
def test_a_hollow_lane_move_refuses_implementation_missing(lanes_mission: _Facts, target_lane: Lane) -> None:
    lanes_mission.paths = {_lane_b_window(): {"src/unrelated.py"}}

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(target_lane))

    assert refused.value.code == "IMPLEMENTATION_MISSING"
    assert str(refused.value).startswith("IMPLEMENTATION_MISSING: WP02 cannot move into review")
    assert f"{_PLANNING_COMMIT}..kitty/mission-fx-lane-b (lane-b)" in str(refused.value)


def test_an_owned_change_in_the_lane_window_passes(lanes_mission: _Facts) -> None:
    lanes_mission.paths = {_lane_b_window(): {"tools/check.sh"}}

    move_task_module._mt_require_implementation_evidence(_state(Lane.APPROVED))

    assert lanes_mission.windows == [_lane_b_window()], "one diff per lane when the owned change is found"


def test_a_planning_lane_is_windowed_on_the_target_branch(lanes_mission: _Facts) -> None:
    lanes_mission.manifest = _manifest(_lane("lane-planning", ("WP02",)))
    lanes_mission.paths = {(_PLANNING_COMMIT, "main"): {"tools/check.sh"}}

    move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert lanes_mission.windows == [(_PLANNING_COMMIT, "main")]


def test_a_dependency_window_counts_the_lanes_own_commits(lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    lanes_mission.manifest = _manifest(_lane("lane-a", ("WP01",)), _lane("lane-b", ("WP02",), depends_on=("lane-a",)))
    dependency_window = ("mergebase", "kitty/mission-fx-lane-b")
    lanes_mission.paths = {_lane_b_window(): set(), dependency_window: {"tools/check.sh"}}
    monkeypatch.setattr(wp_evidence, "_dependency_evidence_windows", lambda _repo, _manifest, _lane: [dependency_window])

    move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert lanes_mission.windows == [_lane_b_window(), dependency_window]


def test_an_unreadable_dependency_window_refuses_unreadable(lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    lanes_mission.manifest = _manifest(_lane("lane-a", ("WP01",)), _lane("lane-b", ("WP02",), depends_on=("lane-a",)))

    def _unreadable(_repo: Path, _manifest: LanesManifest, _lane: ExecutionLane) -> list[tuple[str, str]]:
        raise GitProbeError("no merge base")

    monkeypatch.setattr(wp_evidence, "_dependency_evidence_windows", _unreadable)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert refused.value.code == "IMPLEMENTATION_UNREADABLE"


def test_an_unreadable_window_refuses_unreadable(lanes_mission: _Facts) -> None:
    lanes_mission.paths = {_lane_b_window(): GitProbeError("bad revision")}

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert refused.value.code == "IMPLEMENTATION_UNREADABLE"
    assert str(refused.value).startswith("IMPLEMENTATION_UNREADABLE: ")


def test_no_planning_commit_refuses_window_uncomputable(lanes_mission: _Facts) -> None:
    lanes_mission.manifest = _manifest(_lane("lane-b", ("WP02",)), planning_commit=None)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert refused.value.code == "EVIDENCE_WINDOW_UNCOMPUTABLE"
    assert "finalize-tasks" in str(refused.value)


def test_a_wp_in_no_lane_refuses_window_uncomputable(lanes_mission: _Facts) -> None:
    lanes_mission.manifest = _manifest(_lane("lane-a", ("WP01",)))

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert refused.value.code == "EVIDENCE_WINDOW_UNCOMPUTABLE"


def test_no_owned_files_refuses_implementation_missing(lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    lanes_mission.paths = {_lane_b_window(): {"tools/check.sh"}}
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: ())

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.FOR_REVIEW))

    assert refused.value.code == "IMPLEMENTATION_MISSING"


@pytest.mark.parametrize(
    ("target_lane", "old_lane", "force"),
    [
        (Lane.APPROVED, Lane.IN_PROGRESS, True),  # ruling 3: --force bypasses the move gate
        (Lane.APPROVED, Lane.IN_REVIEW, False),  # not crossing into review territory
        (Lane.IN_PROGRESS, Lane.CLAIMED, False),  # not a review-ward move
    ],
)
def test_the_evidence_gate_does_not_run(lanes_mission: _Facts, target_lane: Lane, old_lane: Lane, force: bool) -> None:
    lanes_mission.paths = {_lane_b_window(): set()}

    move_task_module._mt_require_implementation_evidence(_state(target_lane, old_lane=old_lane, force=force))

    assert lanes_mission.windows == []


def test_an_owned_checkout_keeps_its_own_gate(lanes_mission: _Facts) -> None:
    lanes_mission.paths = {_lane_b_window(): set()}
    st = _state(Lane.APPROVED)
    st.owned = cast(OwnedCheckout, object())

    move_task_module._mt_require_implementation_evidence(st)

    assert lanes_mission.windows == []


def test_a_missing_lanes_manifest_keeps_todays_behaviour(lanes_mission: _Facts) -> None:
    lanes_mission.manifest = None

    move_task_module._mt_require_implementation_evidence(_state(Lane.APPROVED))

    assert lanes_mission.windows == []


def test_the_lanes_manifest_is_none_when_missing_or_corrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import persistence

    def _missing(_dir: Path) -> LanesManifest:
        raise persistence.MissingLanesError("missing")

    def _corrupt(_dir: Path) -> LanesManifest:
        raise persistence.CorruptLanesError("corrupt")

    for reader in (_missing, _corrupt):
        monkeypatch.setattr(persistence, "require_lanes_json", reader)
        assert move_task_module._mt_lanes_manifest(_state(Lane.APPROVED)) is None


def test_single_branch_keeps_its_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(move_task_module, "_mt_lanes_manifest", lambda _st: _manifest(_lane("lane-planning", ("WP02",))))
    monkeypatch.setattr(single_branch_landing, "is_single_branch_mission", lambda _repo, _manifest: True)
    monkeypatch.setattr(single_branch_landing, "single_branch_evidence_window", lambda _repo, _manifest, **_kw: (_PLANNING_COMMIT, "kitty/mission-fx"))
    monkeypatch.setattr(wp_evidence, "evidence_paths", lambda _repo, _window, _slug: frozenset())
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda _st: ("tools/check.sh",))

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_state(Lane.APPROVED))

    assert refused.value.code == "SINGLE_BRANCH_IMPLEMENTATION_MISSING"


def test_the_owned_matcher_is_the_evidence_matcher() -> None:
    patterns = ("src/m1/**", "tools/check.sh")
    for path in ("src/m1/a.py", "./tools/check.sh", "src\\m1\\b.py", "src/m2/a.py"):
        assert move_task_module._mt_matches_owned_file(path, patterns) is wp_evidence.matches_owned(path, patterns)


# ---------------------------------------------------------------- independence


@pytest.fixture
def implementer(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """The implementer of record the gate reads (``[identity]``)."""
    recorded: list[str | None] = ["claude::"]
    monkeypatch.setattr(move_task_module, "_mt_implementer_identity", lambda _st: recorded[0])
    return recorded


@pytest.mark.parametrize("target_lane", [Lane.APPROVED, Lane.DONE])
def test_an_unforced_self_approval_refuses_review_not_independent(implementer: list[str | None], target_lane: Lane) -> None:
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(target_lane))

    assert refused.value.code == "REVIEW_NOT_INDEPENDENT"
    assert str(refused.value) == (
        "REVIEW_NOT_INDEPENDENT: WP02 cannot be approved by its implementer (claude::): the approver (claude::) is not provably "
        "another identity (same agent, and no model or profile recorded on both sides that differs). Have a reviewer with a "
        "different agent approve it, or pass the full --agent <tool>:<model>:<profile> of both implementer and reviewer."
    )


def test_single_branch_self_approval_uses_its_alias_code(implementer: list[str | None], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(move_task_module, "_mt_is_single_branch", lambda _st: True)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED))

    assert refused.value.code == "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT"
    assert str(refused.value).startswith("SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: WP02 cannot be approved by its implementer")


def test_the_same_agent_with_another_profile_is_independent(implementer: list[str | None]) -> None:
    implementer[0] = "claude::implementer-ivan"
    st = _state(Lane.APPROVED)
    st.resolved_binding = ResolvedBinding(agent_profile="reviewer-renata")

    move_task_module._mt_require_independent_approval(st)


def test_the_compact_agent_profile_segment_counts(implementer: list[str | None]) -> None:
    implementer[0] = "claude:opus:implementer-ivan"
    move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, agent="claude:opus:reviewer-renata"))


@pytest.mark.parametrize(
    ("recorded", "agent"),
    [
        ("claude::", "claude:opus:reviewer-renata"),  # profile and model recorded on the approver's side only
        ("claude:opus:implementer-ivan", "claude"),  # recorded on the implementer's side only
        ("claude:opus:", "claude:opus:reviewer-renata"),  # same model, profile on one side only
    ],
)
def test_a_one_sided_segment_never_proves_independence(implementer: list[str | None], recorded: str, agent: str) -> None:
    """#6715 squad fold, operator ruling R1: the same tool with no segment recorded on both sides that differs refuses."""
    implementer[0] = recorded

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, agent=agent))

    assert refused.value.code == "REVIEW_NOT_INDEPENDENT"


@pytest.mark.parametrize(
    ("recorded", "target_lane", "force", "agent"),
    [
        (None, Lane.APPROVED, False, "claude"),  # unknown implementer: accept/consolidate stay strict
        ("claude::", Lane.APPROVED, True, "claude"),  # ruling 3: --force bypasses the move gate
        ("claude::", Lane.FOR_REVIEW, False, "claude"),  # not an approval
        ("claude::", Lane.APPROVED, False, "bob"),  # a different reviewer
        (None, Lane.APPROVED, True, None),  # ruling 3: --force bypasses the placeholder refusal too
    ],
)
def test_the_independence_gate_does_not_refuse(implementer: list[str | None], recorded: str | None, target_lane: Lane, force: bool, agent: str | None) -> None:
    implementer[0] = recorded

    move_task_module._mt_require_independent_approval(_state(target_lane, force=force, agent=agent))


def test_a_bare_approval_out_of_in_review_is_judged_against_the_review_claimer(implementer: list[str | None], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(move_task_module, "_mt_resolve_active_reviewer_identity", lambda _st: "claude")

    with pytest.raises(ActionContextError):
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, old_lane=Lane.IN_REVIEW, agent=None))


def test_the_implementer_identity_reads_the_latest_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import tasks as tasks_module

    def _event(to_lane: str, actor: object) -> StatusEvent:
        return StatusEvent.from_dict(
            {
                "event_id": "01J0000000000000000000000A",
                "mission_slug": "fx",
                "wp_id": "WP02",
                "from_lane": "planned",
                "to_lane": to_lane,
                "at": "2026-10-27T00:00:00+00:00",
                "actor": actor,
                "force": False,
                "execution_mode": "worktree",
            }
        )

    monkeypatch.setattr(tasks_module, "read_events_transactional", lambda **_kw: [_event("claimed", "claude:opus:implementer-ivan")])
    st = _state(Lane.APPROVED)
    st.mission_slug = "fx"

    assert move_task_module._mt_implementer_identity(st) == "claude:opus:implementer-ivan"
    st.mission_slug = ""
    assert move_task_module._mt_implementer_identity(st) is None


# ---------------------------------------------------------------- placeholder approver (review cycle 1)

_PLACEHOLDER_MESSAGE = (
    "REVIEW_NOT_INDEPENDENT: WP02 cannot be approved without a reviewer identity: the approval would be recorded as the "
    "placeholder 'user'. Pass --agent <your identity> (a reviewer other than the implementer)."
)


@pytest.mark.parametrize("recorded", ["claude::", None])
@pytest.mark.parametrize("old_lane", [Lane.IN_PROGRESS, Lane.FOR_REVIEW])
def test_an_approval_without_agent_refuses_as_a_placeholder(implementer: list[str | None], recorded: str | None, old_lane: Lane) -> None:
    """No ``--agent``: the auto-walk records the approval as ``user``, which is never an independent reviewer."""
    implementer[0] = recorded

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, old_lane=old_lane, agent=None))

    assert refused.value.code == "REVIEW_NOT_INDEPENDENT"
    assert str(refused.value) == _PLACEHOLDER_MESSAGE


def test_a_placeholder_agent_refuses(implementer: list[str | None]) -> None:
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.DONE, agent="user"))

    assert refused.value.code == "REVIEW_NOT_INDEPENDENT"


def test_a_binding_without_agent_still_records_the_placeholder_tool(implementer: list[str | None]) -> None:
    st = _state(Lane.APPROVED, agent=None)
    st.resolved_binding = ResolvedBinding(agent_profile="reviewer-renata")

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(st)

    assert "placeholder 'user'" in str(refused.value)


def test_single_branch_placeholder_uses_its_alias_code(implementer: list[str | None], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(move_task_module, "_mt_is_single_branch", lambda _st: True)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, agent=None))

    assert refused.value.code == "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT"
    assert str(refused.value).startswith("SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: WP02 cannot be approved without a reviewer identity")


def test_a_bare_approval_out_of_in_review_records_the_real_review_claimer(implementer: list[str | None], monkeypatch: pytest.MonkeyPatch) -> None:
    """``agent action review --agent bob`` then a bare approval: the executor records ``bob``, so it passes."""
    monkeypatch.setattr(move_task_module, "_mt_resolve_active_reviewer_identity", lambda _st: "bob")

    move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, old_lane=Lane.IN_REVIEW, agent=None))


@pytest.mark.parametrize("claimer", ["user", None])
def test_a_bare_approval_out_of_a_placeholder_review_claim_refuses(implementer: list[str | None], monkeypatch: pytest.MonkeyPatch, claimer: str | None) -> None:
    """A review claimed as ``user`` (or not claimed at all) records the approval as ``user``."""
    monkeypatch.setattr(move_task_module, "_mt_resolve_active_reviewer_identity", lambda _st: claimer)

    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_independent_approval(_state(Lane.APPROVED, old_lane=Lane.IN_REVIEW, agent=None))

    assert str(refused.value) == _PLACEHOLDER_MESSAGE
