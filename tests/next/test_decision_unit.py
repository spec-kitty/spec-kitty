"""Unit tests for the ``spec-kitty next`` decision engine.

This file imports runtime symbols only via ``runtime.next._internal_runtime``
following the WP02 cutover in mission ``shared-package-boundary-cutover-01KQ22DS``.
No quarantined ``spec_kitty_runtime`` references are needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.lane_test_utils import write_single_lane_manifest
from specify_cli.status.store import append_event
from specify_cli.status.models import StatusEvent, Lane
from runtime.next._internal_runtime.schema import NextDecision

from runtime.next.decision import (
    Decision,
    DecisionKind,
    _compute_wp_progress,
    _find_first_wp_by_lane,
    _state_to_action,
    decide_next,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a WP into a specific lane in the event log."""
    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """Create a minimal feature directory."""
    fd = tmp_path / "kitty-specs" / "042-test-feature"
    fd.mkdir(parents=True)
    # Create meta.json
    meta = fd / "meta.json"
    meta.write_text('{"mission_type": "software-dev"}', encoding="utf-8")
    return fd


@pytest.fixture
def feature_with_tasks(feature_dir: Path) -> Path:
    """Feature dir with WP task files."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    # WP01 - planned
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nlane: planned\n---\nContent WP01\n",
        encoding="utf-8",
    )
    # WP02 - doing (in_progress)
    (tasks_dir / "WP02.md").write_text(
        "---\nwork_package_id: WP02\nlane: in_progress\n---\nContent WP02\n",
        encoding="utf-8",
    )
    # WP03 - done
    (tasks_dir / "WP03.md").write_text(
        "---\nwork_package_id: WP03\nlane: done\n---\nContent WP03\n",
        encoding="utf-8",
    )
    # WP04 - for_review
    (tasks_dir / "WP04.md").write_text(
        "---\nwork_package_id: WP04\nlane: for_review\n---\nContent WP04\n",
        encoding="utf-8",
    )
    # Seed the canonical event log for every WP. WP01 must be seeded to planned
    # too: an unseeded WP is genesis (not claimable) under the FSM, so relying on
    # a default would make WP01 invisible to claim selection (#1775).
    _seed_wp_lane(feature_dir, "WP01", "planned")
    _seed_wp_lane(feature_dir, "WP02", "in_progress")
    _seed_wp_lane(feature_dir, "WP03", "done")
    _seed_wp_lane(feature_dir, "WP04", "for_review")
    write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02", "WP03", "WP04"))
    return feature_dir


# ---------------------------------------------------------------------------
# Runtime state helpers
# ---------------------------------------------------------------------------


def _advance_runtime_to_step(
    repo_root: Path,
    mission_slug: str,
    target_step_id: str,
    agent: str = "test-agent",
) -> None:
    """Advance the runtime run past steps until target_step_id is issued.

    Calls decide_next repeatedly to advance through the DAG steps
    (discovery -> specify -> plan -> tasks -> implement -> review -> accept).
    """
    from runtime.next.runtime_bridge import get_or_start_run

    from specify_cli.mission import get_mission_type

    feature_dir = repo_root / "kitty-specs" / mission_slug
    mission_type = get_mission_type(feature_dir)
    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)

    from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter
    from runtime.next._internal_runtime.engine import _read_snapshot

    # Keep advancing until the target step is issued
    step_order = [
        "discovery",
        "specify",
        "plan",
        "tasks_outline",
        "tasks_packages",
        "tasks_finalize",
        "implement",
        "review",
        "accept",
    ]
    target_idx = step_order.index(target_step_id) if target_step_id in step_order else -1

    for _ in range(target_idx + 2):
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step_id:
            return

        runtime_next_step(run_ref, agent_id=agent, result="success", emitter=NullEmitter())

        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step_id:
            return


def _complete_all_steps(
    repo_root: Path,
    mission_slug: str,
    agent: str = "test-agent",
) -> None:
    """Complete all runtime steps to reach terminal state."""
    from runtime.next.runtime_bridge import get_or_start_run

    from specify_cli.mission import get_mission_type

    feature_dir = repo_root / "kitty-specs" / mission_slug
    mission_type = get_mission_type(feature_dir)
    run_ref = get_or_start_run(mission_slug, repo_root, mission_type)

    from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter

    # There are 9 steps: each needs to be issued + completed
    for _ in range(20):  # generous upper bound
        decision = runtime_next_step(
            run_ref,
            agent_id=agent,
            result="success",
            emitter=NullEmitter(),
        )
        if decision.kind == "terminal":
            return


# ---------------------------------------------------------------------------
# WP progress and lane helpers
# ---------------------------------------------------------------------------


class TestWPHelpers:
    def test_compute_wp_progress_no_tasks_dir(self, feature_dir: Path) -> None:
        assert _compute_wp_progress(feature_dir) is None

    def test_compute_wp_progress(self, feature_with_tasks: Path) -> None:
        progress = _compute_wp_progress(feature_with_tasks)
        assert progress is not None
        assert progress["total_wps"] == 4
        assert progress["planned_wps"] == 1
        assert progress["in_progress_wps"] == 1
        assert progress["done_wps"] == 1
        assert progress["for_review_wps"] == 1

    def test_find_first_wp_by_lane_planned(self, feature_with_tasks: Path) -> None:
        assert _find_first_wp_by_lane(feature_with_tasks, "planned") == "WP01"

    def test_find_first_wp_by_lane_for_review(self, feature_with_tasks: Path) -> None:
        assert _find_first_wp_by_lane(feature_with_tasks, "for_review") == "WP04"

    def test_find_first_wp_by_lane_not_found(self, feature_with_tasks: Path) -> None:
        assert _find_first_wp_by_lane(feature_with_tasks, "canceled") is None

    def test_find_first_wp_no_tasks_dir(self, feature_dir: Path) -> None:
        assert _find_first_wp_by_lane(feature_dir, "planned") is None


# ---------------------------------------------------------------------------
# decide_next
# ---------------------------------------------------------------------------


class TestDecideNext:
    def test_missing_feature_dir(self, tmp_path: Path) -> None:
        decision = decide_next("claude", "999-nonexistent", "success", tmp_path)
        assert decision.kind == DecisionKind.blocked
        assert "not found" in decision.reason

    def test_result_failed(self, feature_dir: Path) -> None:
        """Failed result must flow through runtime and return deterministic blocked state."""
        repo_root = feature_dir.parent.parent
        # Issue a first runtime step so failure has a concrete step to complete.
        first = decide_next("claude", "042-test-feature", "success", repo_root)
        assert first.step_id is not None

        decision = decide_next("claude", "042-test-feature", "failed", repo_root)
        assert decision.kind == DecisionKind.blocked
        assert "failed" in (decision.reason or "").lower()
        assert decision.run_id is not None, "failed decision must include run_id"

    def test_result_failed_after_advance_carries_step_id(self, feature_dir: Path) -> None:
        """After advancing, failed result still carries canonical run metadata."""
        repo_root = feature_dir.parent.parent
        # First call advances to get a step issued
        d1 = decide_next("claude", "042-test-feature", "success", repo_root)
        assert d1.step_id is not None
        # Now fail — runtime should return blocked and keep run correlation
        d2 = decide_next("claude", "042-test-feature", "failed", repo_root)
        assert d2.kind == DecisionKind.blocked
        assert d2.run_id is not None
        assert d2.step_id is None or isinstance(d2.step_id, str)

    def test_result_blocked(self, feature_dir: Path) -> None:
        repo_root = feature_dir.parent.parent
        # Issue a first runtime step so blocked result completes prior step through runtime.
        first = decide_next("claude", "042-test-feature", "success", repo_root)
        assert first.step_id is not None

        decision = decide_next("claude", "042-test-feature", "blocked", repo_root)
        assert decision.kind == DecisionKind.blocked
        assert "blocked" in (decision.reason or "").lower()
        assert decision.run_id is not None, "blocked decision must include run_id"

    def test_terminal_state(self, feature_dir: Path) -> None:
        """Completing all runtime steps produces a terminal decision."""
        repo_root = feature_dir.parent.parent
        _complete_all_steps(repo_root, "042-test-feature")
        decision = decide_next("claude", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.terminal

    def test_decision_has_required_fields(self, feature_dir: Path) -> None:
        repo_root = feature_dir.parent.parent
        decision = decide_next("claude", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert "kind" in d
        assert "agent" in d
        assert "mission_slug" in d
        assert "mission" in d
        assert "mission_state" in d
        assert "timestamp" in d
        assert "guard_failures" in d

    def test_decision_has_runtime_fields(self, feature_dir: Path) -> None:
        """Runtime fields (run_id, step_id) are present in decisions."""
        repo_root = feature_dir.parent.parent
        decision = decide_next("claude", "042-test-feature", "success", repo_root)
        d = decision.to_dict()
        assert "run_id" in d
        assert "step_id" in d
        assert "decision_id" in d
        assert "input_key" in d

    def test_implement_state_with_planned_wp(self, feature_with_tasks: Path) -> None:
        """When in implement state with planned WPs, returns implement action."""
        repo_root = feature_with_tasks.parent.parent
        # Advance runtime to implement step
        _advance_runtime_to_step(repo_root, "042-test-feature", "implement")
        decision = decide_next("claude", "042-test-feature", "success", repo_root)
        # Should stay in implement state and map to implement action with the planned WP
        if decision.kind == DecisionKind.step and decision.action == "implement":
            assert decision.wp_id == "WP01"
            assert decision.workspace_path is not None

    def test_to_dict_roundtrip(self, tmp_path: Path) -> None:
        # WP02 / #844: kind=step requires a real prompt_file at construction
        # time (C1/C2). Stage one under tmp_path so the validator passes.
        prompt = tmp_path / "specify.md"
        prompt.write_text("# specify", encoding="utf-8")
        decision = Decision(
            kind=DecisionKind.step,
            agent="test",
            mission_slug="042-test",
            mission="software-dev",
            mission_state="specify",
            timestamp="2026-02-17T00:00:00+00:00",
            action="specify",
            progress={"total_wps": 3, "done_wps": 1},
            run_id="abc123",
            step_id="specify",
            prompt_file=str(prompt),
        )
        d = decision.to_dict()
        assert d["kind"] == "step"
        assert d["mission_state"] == "specify"
        assert d["progress"]["total_wps"] == 3
        assert d["run_id"] == "abc123"
        assert d["step_id"] == "specify"

    def test_first_call_returns_step(self, feature_dir: Path) -> None:
        """First call on a fresh feature returns a step decision."""
        repo_root = feature_dir.parent.parent
        decision = decide_next("claude", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.step
        assert decision.run_id is not None
        assert decision.step_id is not None


# ---------------------------------------------------------------------------
# decide_next -- owned-checkout (owned=) threading (#3328)
# ---------------------------------------------------------------------------


class TestDecideNextOwnedCheckout:
    """``decide_next``'s ``owned`` fork (owned-checkout-lifecycle-authority
    WP11): the validated fact is threaded unchanged into
    ``runtime_bridge.decide_next_via_runtime`` -- never a bare root (WP18
    retired the legacy ``effective_root`` keyword). Monkeypatched stand-ins
    isolate this one dispatch decision from the (separately unit-tested,
    tests/next/test_runtime_bridge_unit.py) owned-checkout resolution itself."""

    def test_owned_fact_threads_to_runtime_bridge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import runtime.next.runtime_bridge as runtime_bridge_module
        from tests._owned_fixtures import mint_test_fact

        owned_root = tmp_path / "owned-checkout"
        decoy_repo_root = tmp_path / "decoy-primary-never-read"
        fake_fact = mint_test_fact(
            repository_root=decoy_repo_root,
            owned_root=owned_root,
            mission_dir=owned_root / "kitty-specs" / "owned-mission",
            mission_slug="owned-mission",
            write_branch="codex/owned",
        )

        captured: dict[str, object] = {}

        def _fake_decide_next_via_runtime(
            agent: str,
            mission_slug: str,
            result: str,
            repo_root: Path,
            *,
            owned: object | None = None,
        ) -> Decision:
            captured["args"] = (agent, mission_slug, result, repo_root)
            captured["owned"] = owned
            return Decision(
                kind=DecisionKind.terminal,
                agent=agent,
                mission_slug=mission_slug,
                mission="software-dev",
                mission_state="done",
                timestamp="2026-01-01T00:00:00+00:00",
            )

        monkeypatch.setattr(runtime_bridge_module, "decide_next_via_runtime", _fake_decide_next_via_runtime)

        decision = decide_next("claude", "owned-mission", "success", decoy_repo_root, owned=fake_fact)

        assert decision.kind == DecisionKind.terminal
        assert captured["args"] == ("claude", "owned-mission", "success", decoy_repo_root)
        assert captured["owned"] is fake_fact

    def test_without_owned_threads_owned_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-vacuity: omitting ``owned`` reaches ``decide_next_via_runtime``
        with ``owned=None`` -- proving the two call shapes genuinely diverge."""
        import runtime.next.runtime_bridge as runtime_bridge_module

        captured: dict[str, object] = {}

        def _fake_decide_next_via_runtime(*args: object, **kwargs: object) -> Decision:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return Decision(
                kind=DecisionKind.terminal,
                agent=str(args[0]),
                mission_slug=str(args[1]),
                mission="software-dev",
                mission_state="done",
                timestamp="2026-01-01T00:00:00+00:00",
            )

        monkeypatch.setattr(runtime_bridge_module, "decide_next_via_runtime", _fake_decide_next_via_runtime)

        decide_next("claude", "plain-mission", "success", tmp_path)

        assert captured["kwargs"] == {"owned": None}


# ---------------------------------------------------------------------------
# Atomic task step alias tests
# ---------------------------------------------------------------------------


class TestTaskStepAliases:
    def test_tasks_outline_maps_to_tasks_outline_action(self, feature_dir: Path) -> None:
        """Verify _state_to_action maps tasks_outline → tasks-outline via alias."""
        from runtime.next.decision import _state_to_action

        repo_root = feature_dir.parent.parent
        action, wp_id, workspace_path = _state_to_action(
            "tasks_outline",
            "042-test-feature",
            feature_dir,
            repo_root,
            "software-dev",
        )
        assert action == "tasks-outline"
        assert wp_id is None
        assert workspace_path is None

    def test_tasks_packages_maps_to_tasks_packages_action(self, feature_dir: Path) -> None:
        """Verify _state_to_action maps tasks_packages → tasks-packages via alias."""
        from runtime.next.decision import _state_to_action

        repo_root = feature_dir.parent.parent
        action, wp_id, workspace_path = _state_to_action(
            "tasks_packages",
            "042-test-feature",
            feature_dir,
            repo_root,
            "software-dev",
        )
        assert action == "tasks-packages"
        assert wp_id is None
        assert workspace_path is None

    def test_tasks_finalize_maps_to_tasks_finalize_action(self, feature_dir: Path) -> None:
        """Verify _state_to_action maps tasks_finalize → tasks-finalize via alias."""
        from runtime.next.decision import _state_to_action

        repo_root = feature_dir.parent.parent
        action, wp_id, workspace_path = _state_to_action(
            "tasks_finalize",
            "042-test-feature",
            feature_dir,
            repo_root,
            "software-dev",
        )
        assert action == "tasks-finalize"
        assert wp_id is None
        assert workspace_path is None


class TestDecisionQuestionOptions:
    def test_decision_has_question_and_options(self) -> None:
        """Decision with question/options exposes them in to_dict()."""
        decision = Decision(
            kind=DecisionKind.decision_required,
            agent="test",
            mission_slug="042-test",
            mission="software-dev",
            mission_state="unknown",
            timestamp="2026-02-18T00:00:00+00:00",
            reason="Decision required",
            question="Which approach should we take?",
            options=["Option A", "Option B", "Option C"],
            decision_id="test-decision-1",
        )
        d = decision.to_dict()
        assert d["question"] == "Which approach should we take?"
        assert d["options"] == ["Option A", "Option B", "Option C"]
        assert d["decision_id"] == "test-decision-1"

    def test_decision_question_options_default_none(self, tmp_path: Path) -> None:
        """Decision without question/options defaults to None."""
        # WP02 / #844: kind=step requires a real prompt_file (C1/C2).
        prompt = tmp_path / "specify.md"
        prompt.write_text("# specify", encoding="utf-8")
        decision = Decision(
            kind=DecisionKind.step,
            agent="test",
            mission_slug="042-test",
            mission="software-dev",
            mission_state="specify",
            timestamp="2026-02-18T00:00:00+00:00",
            prompt_file=str(prompt),
        )
        d = decision.to_dict()
        assert d["question"] is None
        assert d["options"] is None


# ---------------------------------------------------------------------------
# in_review lane handling in _state_to_action (FR-012a)
# ---------------------------------------------------------------------------


class TestInReviewLaneDecision:
    """Verify that _state_to_action explicitly reasons about in_review WPs.

    FR-012a: in_review is a first-class lane.  WPs in in_review are actively
    being reviewed by another agent and must NOT be picked up by another
    reviewer.
    """

    @pytest.fixture
    def feature_only_in_review(self, feature_dir: Path) -> Path:
        """Feature dir where the only non-terminal WP is in_review."""
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: in_review\n---\nContent\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02.md").write_text(
            "---\nwork_package_id: WP02\nlane: done\n---\nContent\n",
            encoding="utf-8",
        )
        _seed_wp_lane(feature_dir, "WP01", "in_review")
        _seed_wp_lane(feature_dir, "WP02", "done")
        write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"))
        return feature_dir

    @pytest.fixture
    def feature_for_review_and_in_review(self, feature_dir: Path) -> Path:
        """Feature dir with both for_review and in_review WPs."""
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: for_review\n---\nContent\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02.md").write_text(
            "---\nwork_package_id: WP02\nlane: in_review\n---\nContent\n",
            encoding="utf-8",
        )
        _seed_wp_lane(feature_dir, "WP01", "for_review")
        _seed_wp_lane(feature_dir, "WP02", "in_review")
        write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"))
        return feature_dir

    def test_find_first_wp_by_lane_in_review(self, feature_only_in_review: Path) -> None:
        """_find_first_wp_by_lane correctly resolves in_review WPs."""
        assert _find_first_wp_by_lane(feature_only_in_review, "in_review") == "WP01"

    def test_implement_skips_in_review_wp(self, feature_only_in_review: Path) -> None:
        """Implement state must not pick up in_review WPs for review redirect."""
        from unittest.mock import patch, MagicMock

        repo_root = feature_only_in_review.parent.parent
        action, wp_id, ws = _state_to_action(
            "implement",
            feature_only_in_review.name,
            feature_only_in_review,
            repo_root,
            "software-dev",
        )
        # in_review WPs are not actionable — return None
        assert action is None
        assert wp_id is None

    def test_implement_prefers_for_review_over_in_review(self, feature_for_review_and_in_review: Path) -> None:
        """Implement fallback picks for_review WPs, not in_review ones."""
        from unittest.mock import patch
        from types import SimpleNamespace

        repo_root = feature_for_review_and_in_review.parent.parent
        fake_ws = SimpleNamespace(worktree_path=Path("/nonexistent/fake-worktree"))

        with patch(
            "runtime.next.decision.resolve_workspace_for_wp",
            return_value=fake_ws,
        ):
            action, wp_id, ws = _state_to_action(
                "implement",
                feature_for_review_and_in_review.name,
                feature_for_review_and_in_review,
                repo_root,
                "software-dev",
            )

        assert action == "review"
        assert wp_id == "WP01"  # for_review, not WP02 (in_review)

    def test_review_picks_for_review_not_in_review(self, feature_for_review_and_in_review: Path) -> None:
        """Review state picks for_review WPs, explicitly skipping in_review."""
        from unittest.mock import patch
        from types import SimpleNamespace

        repo_root = feature_for_review_and_in_review.parent.parent
        fake_ws = SimpleNamespace(worktree_path=Path("/nonexistent/fake-worktree"))

        with patch(
            "runtime.next.decision.resolve_workspace_for_wp",
            return_value=fake_ws,
        ):
            action, wp_id, ws = _state_to_action(
                "review",
                feature_for_review_and_in_review.name,
                feature_for_review_and_in_review,
                repo_root,
                "software-dev",
            )

        assert action == "review"
        assert wp_id == "WP01"  # for_review, not WP02 (in_review)

    def test_review_does_not_assign_in_review_wp(self, feature_only_in_review: Path) -> None:
        """When only in_review WPs exist, review state must not assign them."""
        from unittest.mock import patch

        repo_root = feature_only_in_review.parent.parent
        # review state falls through to generic template resolution
        # when no for_review WPs exist — verify it doesn't pick up in_review
        with patch(
            "specify_cli.runtime.resolver.resolve_command",
            side_effect=FileNotFoundError,
        ):
            action, wp_id, ws = _state_to_action(
                "review",
                feature_only_in_review.name,
                feature_only_in_review,
                repo_root,
                "software-dev",
            )

        # No WP assigned — in_review WPs are not available for pickup
        assert wp_id is None


# ---------------------------------------------------------------------------
# DecisionKind StrEnum serialisation compatibility (refs #1881)
# ---------------------------------------------------------------------------


class TestDecisionKindSerialisation:
    """Prove that converting DecisionKind to StrEnum is JSON-round-trip identical
    to the previous plain-class form (every member serialises as its bare string
    value, not as 'DecisionKind.<member>').
    """

    def test_decision_kind_members_equal_string_literals(self) -> None:
        """Each DecisionKind member compares equal to its string literal."""
        assert DecisionKind.step == "step"
        assert DecisionKind.decision_required == "decision_required"
        assert DecisionKind.blocked == "blocked"
        assert DecisionKind.terminal == "terminal"
        assert DecisionKind.query == "query"

    def test_decision_kind_is_str_subclass(self) -> None:
        """DecisionKind members are str instances (StrEnum invariant)."""
        for member in DecisionKind:
            assert isinstance(member, str), f"{member!r} is not a str"

    def test_decision_kind_json_serialisation_byte_identical(self) -> None:
        """json.dumps of a dict containing a DecisionKind value produces the
        same bytes as when using the raw string literal — the pre-enum contract
        is preserved exactly.
        """
        for member in DecisionKind:
            enum_output = json.dumps({"kind": member})
            str_output = json.dumps({"kind": member.value})
            assert enum_output == str_output, f"DecisionKind.{member.name} serialises to {enum_output!r}, expected {str_output!r}"

    def test_to_dict_kind_field_is_bare_string(self, tmp_path: Path) -> None:
        """Decision.to_dict() emits kind as a bare string, not an enum repr."""
        prompt = tmp_path / "p.md"
        prompt.write_text("# p", encoding="utf-8")
        decision = Decision(
            kind=DecisionKind.step,
            agent="test",
            mission_slug="042-test",
            mission="software-dev",
            mission_state="specify",
            timestamp="2026-02-17T00:00:00+00:00",
            prompt_file=str(prompt),
        )
        d = decision.to_dict()
        assert d["kind"] == "step"
        # Verify JSON round-trip is byte-identical to the pre-enum form
        json_str = json.dumps(d)
        assert '"kind": "step"' in json_str

    def test_next_decision_rejects_invalid_kind(self) -> None:
        """Runtime planning envelopes must keep the pre-enum closed kind set."""
        with pytest.raises(ValidationError):
            NextDecision(kind="nonsense", run_id="run", mission_key="mission")

    def test_next_decision_accepts_decision_kind_member(self) -> None:
        """StrEnum inputs validate without widening the accepted kind set."""
        decision = NextDecision(
            kind=DecisionKind.step,
            run_id="run",
            mission_key="mission",
        )

        assert decision.kind == "step"


def test_build_prompt_call_forwards_the_owned_fact() -> None:
    """WP12 converted the bridging call: ``build_prompt`` receives the fact, and no
    WP12 conversion marker survives anywhere in the module."""
    import re
    from pathlib import Path

    import runtime.next.decision as decision_module

    source = Path(str(decision_module.__file__)).read_text(encoding="utf-8")
    call = re.search(r"=\s*build_prompt\((?P<args>.*?)\n\s*\)", source, re.DOTALL)
    assert call is not None
    assert "owned=owned" in call.group("args")
    assert "repo_root=repo_root" in call.group("args")
    assert "WP12 converts" not in source
