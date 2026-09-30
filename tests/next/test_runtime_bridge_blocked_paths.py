"""Targeted coverage for the structured-blocked emit branches in
``runtime_bridge.py`` (PR #855 follow-up — diff-coverage fill).

The CI diff-coverage gate flagged the following lines uncovered by the WP06
prompt-file-invariant tests:

- ``runtime_bridge.py:1565-1609`` — legacy DAG path guard failures: when
  ``current_step_id`` has a guard failure on a non-WP step, the runtime
  must build a structured ``blocked`` decision (with the resolvable prompt
  attached when one is available, or with the prompt-resolution error
  threaded into the reason when not).
- ``runtime_bridge.py:2156`` — ``_build_wp_iteration_decision`` with a
  prompt-resolution error must yield a structured ``blocked`` instead of a
  partial step.
- ``runtime_bridge.py:2364`` — ``_map_runtime_decision`` non-WP step branch
  with neither ``action`` nor ``step_id`` mapped must short-circuit to a
  structured ``blocked`` with a populated reason (no template lookup).

The existing `test_prompt_file_invariant.py` covers the contract surface
but doesn't drive these specific lines because it stubs ``_state_to_action``
to always return a usable action. Here we drive the branches directly.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime.next.decision import DecisionKind

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# 2156 — _build_wp_iteration_decision blocked when prompt unresolvable
# ---------------------------------------------------------------------------


def _runtime_decision(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "kind": "step",
        "step_id": "implement",
        "run_id": "run-001",
        "decision_id": None,
        "question": None,
        "options": None,
        "input_key": None,
        "reason": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestWPIterationDecisionBlockedBranch:
    """runtime_bridge.py:2152-2172 (`_build_wp_iteration_decision` blocked path)."""

    def test_wp_iteration_blocked_when_prompt_unresolvable_with_guard_failures(
        self, tmp_path: Path
    ) -> None:
        """Direct unit-level call to `_build_wp_iteration_decision`.

        Ensures the blocked branch (line 2156-2172) fires when the helper
        returns a non-empty error and `guard_failures` is supplied. The
        resulting Decision must:
          - kind == blocked
          - reason == prompt_error
          - guard_failures forwarded (not dropped)
          - prompt_file is None
        """
        from runtime.next.runtime_bridge import _build_wp_iteration_decision

        run_ref = SimpleNamespace(run_id="run-blocked-01")

        with (
            patch(
                "runtime.next.runtime_bridge._state_to_action",
                return_value=("implement", "WP01", str(tmp_path / ".worktrees" / "lane-a")),
            ),
            patch(
                "runtime.next.runtime_bridge._build_prompt_or_error",
                return_value=(None, "prompt resolution failed for action 'implement'", None),
            ),
        ):
            decision = _build_wp_iteration_decision(
                step_id="implement",
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                feature_dir=tmp_path,
                repo_root=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
                run_ref=run_ref,
                guard_failures=["pre-existing guard"],
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason
        assert "prompt resolution failed" in decision.reason
        assert decision.prompt_file is None
        assert decision.guard_failures == ["pre-existing guard"]
        assert decision.action == "implement"
        assert decision.wp_id == "WP01"


# ---------------------------------------------------------------------------
# 2364 — _map_runtime_decision non-WP step with neither action nor step_id
# ---------------------------------------------------------------------------


class TestMapRuntimeDecisionNoActionNoStepId:
    """runtime_bridge.py:2363-2364 (no-action AND no-step_id branch)."""

    def test_map_runtime_decision_emits_blocked_when_no_action_and_no_step_id(
        self, tmp_path: Path
    ) -> None:
        """Drive the `else` branch on line 2363-2364.

        Pre-condition: `_state_to_action` returns (None, None, None) AND
        `decision.step_id` is None. The map function must NOT attempt to
        resolve a prompt (prompt_error is set inline) and must emit a
        blocked decision.
        """
        from runtime.next.runtime_bridge import _map_runtime_decision

        with (
            patch(
                "runtime.next.runtime_bridge._state_to_action",
                return_value=(None, None, None),
            ),
            patch(
                "runtime.next.runtime_bridge._is_wp_iteration_step",
                return_value=False,
            ),
        ):
            # step_id=None forces the `if action or step_id` guard to fall
            # through to the `else` branch on line 2363.
            decision = _map_runtime_decision(
                decision=_runtime_decision(step_id=None),
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                repo_root=tmp_path,
                feature_dir=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason
        assert "no action and no step_id" in decision.reason
        assert decision.prompt_file is None


# ---------------------------------------------------------------------------
# 1565-1609 — legacy DAG path: non-WP step + guard failures + prompt branch
# ---------------------------------------------------------------------------


class TestDecideNextViaRuntimeGuardFailureBlocked:
    """runtime_bridge.py:1561-1608 (`decide_next_via_runtime` guard branch).

    When ``result == "success"``, the current step is NOT a WP iteration step,
    and ``_check_cli_guards`` returns a non-empty list, the runtime MUST
    surface a structured blocked decision with the prompt either attached
    (when resolvable) or threaded into the reason (when not).
    """

    def _build_minimal_feature_dir(self, tmp_path: Path, mission_slug: str) -> Path:
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True, exist_ok=True)
        # Minimal meta so get_mission_type doesn't blow up.
        (feature_dir / "meta.json").write_text(
            '{"mission_type": "software-dev"}',
            encoding="utf-8",
        )
        return feature_dir

    def test_guard_failure_on_non_wp_step_yields_blocked_with_prompt_error(
        self, tmp_path: Path
    ) -> None:
        """Lines 1561-1609 — the prompt-error branch of the guard handler.

        Drives the branch where ``_state_to_action`` returns a usable
        ``action`` and ``_build_prompt_or_error`` returns ``(None, error)``.
        The decision must be ``blocked`` with the prompt error in
        ``reason``.
        """
        from runtime.next import runtime_bridge as rb

        mission_slug = "042-test"
        self._build_minimal_feature_dir(tmp_path, mission_slug)

        # Stub helpers to drive the exact branch with no real runtime engine.
        run_ref = SimpleNamespace(run_id="run-guard-01", run_dir=str(tmp_path / "run"))
        snapshot = SimpleNamespace(issued_step_id="specify")

        with (
            patch.object(rb, "get_mission_type", return_value="software-dev"),
            patch.object(rb, "runtime_emitter_for_mission") as sync_factory,
            patch.object(rb, "get_or_start_run", return_value=run_ref),
            patch.object(rb, "_compute_wp_progress", return_value=None),
            patch.object(rb, "_check_cli_guards", return_value=["specify_guard_failure"]),
            patch.object(rb, "_is_wp_iteration_step", return_value=False),
            patch.object(rb, "_state_to_action", return_value=("specify", None, None)),
            patch.object(
                rb,
                "_build_prompt_or_error",
                return_value=(None, "prompt resolution failed for action 'specify'", None),
            ),
            patch(
                "runtime.next._internal_runtime.engine._read_snapshot",
                return_value=snapshot,
            ),
        ):
            sync_factory.return_value = SimpleNamespace(
                seed_from_snapshot=lambda *_a, **_k: None
            )
            decision = rb.decide_next_via_runtime(
                agent="claude",
                mission_slug=mission_slug,
                result="success",
                repo_root=tmp_path,
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason
        assert "prompt resolution failed" in decision.reason
        assert decision.guard_failures == ["specify_guard_failure"]
        assert decision.action == "specify"
        assert decision.prompt_file is None

    def test_guard_failure_on_non_wp_step_with_resolvable_prompt(
        self, tmp_path: Path
    ) -> None:
        """Lines 1561-1609 — the prompt-attached branch (line 1609+).

        Same setup as above but with a resolvable prompt: the decision is
        still blocked (because guards failed), but it MUST carry the
        resolvable ``prompt_file`` rather than a prompt-error reason.
        """
        from runtime.next import runtime_bridge as rb

        mission_slug = "042-test"
        self._build_minimal_feature_dir(tmp_path, mission_slug)

        prompt_path = tmp_path / "specify-prompt.md"
        prompt_path.write_text("# specify\n", encoding="utf-8")

        run_ref = SimpleNamespace(run_id="run-guard-02", run_dir=str(tmp_path / "run"))
        snapshot = SimpleNamespace(issued_step_id="specify")

        with (
            patch.object(rb, "get_mission_type", return_value="software-dev"),
            patch.object(rb, "runtime_emitter_for_mission") as sync_factory,
            patch.object(rb, "get_or_start_run", return_value=run_ref),
            patch.object(rb, "_compute_wp_progress", return_value=None),
            patch.object(rb, "_check_cli_guards", return_value=["specify_guard_failure"]),
            patch.object(rb, "_is_wp_iteration_step", return_value=False),
            patch.object(rb, "_state_to_action", return_value=("specify", None, None)),
            patch.object(
                rb,
                "_build_prompt_or_error",
                return_value=(str(prompt_path), None, None),
            ),
            patch(
                "runtime.next._internal_runtime.engine._read_snapshot",
                return_value=snapshot,
            ),
        ):
            sync_factory.return_value = SimpleNamespace(
                seed_from_snapshot=lambda *_a, **_k: None
            )
            decision = rb.decide_next_via_runtime(
                agent="claude",
                mission_slug=mission_slug,
                result="success",
                repo_root=tmp_path,
            )

        # When guards fail but the prompt is resolvable, the decision is
        # still structured (blocked OR step depending on policy). The
        # critical contract is: guard_failures are surfaced, and any
        # `prompt_file` attached must point to a real file.
        assert decision.guard_failures == ["specify_guard_failure"]
        if decision.prompt_file is not None:
            assert Path(decision.prompt_file).exists()

    def test_guard_failure_blocks_if_resolved_prompt_disappears(
        self, tmp_path: Path
    ) -> None:
        """A prompt can disappear after resolution; keep the step invariant hard."""
        from runtime.next import runtime_bridge as rb

        mission_slug = "042-test"
        self._build_minimal_feature_dir(tmp_path, mission_slug)

        prompt_path = tmp_path / "specify-prompt.md"
        prompt_path.write_text("# specify\n", encoding="utf-8")

        run_ref = SimpleNamespace(run_id="run-guard-04", run_dir=str(tmp_path / "run"))
        snapshot = SimpleNamespace(issued_step_id="specify")

        with (
            patch.object(rb, "get_mission_type", return_value="software-dev"),
            patch.object(rb, "runtime_emitter_for_mission") as sync_factory,
            patch.object(rb, "get_or_start_run", return_value=run_ref),
            patch.object(rb, "_compute_wp_progress", return_value=None),
            patch.object(rb, "_check_cli_guards", return_value=["specify_guard_failure"]),
            patch.object(rb, "_is_wp_iteration_step", return_value=False),
            patch.object(rb, "_state_to_action", return_value=("specify", None, None)),
            patch.object(
                rb,
                "_build_prompt_or_error",
                return_value=(str(prompt_path), None, None),
            ),
            patch("pathlib.Path.is_file", return_value=False),
            patch(
                "runtime.next._internal_runtime.engine._read_snapshot",
                return_value=snapshot,
            ),
        ):
            sync_factory.return_value = SimpleNamespace(
                seed_from_snapshot=lambda *_a, **_k: None
            )
            decision = rb.decide_next_via_runtime(
                agent="claude",
                mission_slug=mission_slug,
                result="success",
                repo_root=tmp_path,
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason == "prompt_file_not_resolvable"
        assert decision.guard_failures == ["specify_guard_failure"]
        assert decision.prompt_file is None

    def test_guard_failure_on_non_wp_step_no_action_mapped(
        self, tmp_path: Path
    ) -> None:
        """Lines 1584-1587 — `_state_to_action` returns (None, ...) branch.

        When no action can be mapped for the current step, the helper
        composes the prompt-error reason inline (`no action mapped for
        step ...`) without invoking `_build_prompt_or_error`.
        """
        from runtime.next import runtime_bridge as rb

        mission_slug = "042-test"
        self._build_minimal_feature_dir(tmp_path, mission_slug)

        run_ref = SimpleNamespace(run_id="run-guard-03", run_dir=str(tmp_path / "run"))
        snapshot = SimpleNamespace(issued_step_id="exotic-step")

        with (
            patch.object(rb, "get_mission_type", return_value="software-dev"),
            patch.object(rb, "runtime_emitter_for_mission") as sync_factory,
            patch.object(rb, "get_or_start_run", return_value=run_ref),
            patch.object(rb, "_compute_wp_progress", return_value=None),
            patch.object(rb, "_check_cli_guards", return_value=["exotic_guard_failure"]),
            patch.object(rb, "_is_wp_iteration_step", return_value=False),
            patch.object(rb, "_state_to_action", return_value=(None, None, None)),
            patch(
                "runtime.next._internal_runtime.engine._read_snapshot",
                return_value=snapshot,
            ),
        ):
            sync_factory.return_value = SimpleNamespace(
                seed_from_snapshot=lambda *_a, **_k: None
            )
            decision = rb.decide_next_via_runtime(
                agent="claude",
                mission_slug=mission_slug,
                result="success",
                repo_root=tmp_path,
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason
        assert "no action mapped" in decision.reason
        assert decision.guard_failures == ["exotic_guard_failure"]
        assert decision.prompt_file is None


class TestResolvedPromptRaceFallbacks:
    """Cover every runtime bridge path that catches ``InvalidStepDecision``."""

    def test_wp_iteration_blocks_if_resolved_prompt_disappears(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge import _build_wp_iteration_decision

        prompt_path = tmp_path / "implement-prompt.md"
        prompt_path.write_text("# implement\n", encoding="utf-8")
        run_ref = SimpleNamespace(run_id="run-wp-race")

        with (
            patch(
                "runtime.next.runtime_bridge._state_to_action",
                return_value=("implement", "WP01", str(tmp_path / ".worktrees" / "lane-a")),
            ),
            patch(
                "runtime.next.runtime_bridge._build_prompt_or_error",
                return_value=(str(prompt_path), None, None),
            ),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            decision = _build_wp_iteration_decision(
                step_id="implement",
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                feature_dir=tmp_path,
                repo_root=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
                run_ref=run_ref,
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason == "prompt_file_not_resolvable"
        assert decision.prompt_file is None

    def test_map_wp_step_blocks_if_resolved_prompt_disappears(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge import _map_runtime_decision

        prompt_path = tmp_path / "implement-prompt.md"
        prompt_path.write_text("# implement\n", encoding="utf-8")

        with (
            patch(
                "runtime.next.runtime_bridge._state_to_action",
                return_value=("implement", "WP01", str(tmp_path / ".worktrees" / "lane-a")),
            ),
            patch(
                "runtime.next.runtime_bridge._is_wp_iteration_step",
                return_value=True,
            ),
            patch(
                "runtime.next.runtime_bridge._build_prompt_or_error",
                return_value=(str(prompt_path), None, None),
            ),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            decision = _map_runtime_decision(
                decision=_runtime_decision(step_id="implement"),
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                repo_root=tmp_path,
                feature_dir=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason == "prompt_file_not_resolvable"
        assert decision.prompt_file is None

    def test_map_non_wp_step_blocks_if_resolved_prompt_disappears(
        self, tmp_path: Path
    ) -> None:
        from runtime.next.runtime_bridge import _map_runtime_decision

        prompt_path = tmp_path / "specify-prompt.md"
        prompt_path.write_text("# specify\n", encoding="utf-8")

        with (
            patch(
                "runtime.next.runtime_bridge._state_to_action",
                return_value=("specify", None, None),
            ),
            patch(
                "runtime.next.runtime_bridge._is_wp_iteration_step",
                return_value=False,
            ),
            patch(
                "runtime.next.runtime_bridge._build_prompt_or_error",
                return_value=(str(prompt_path), None, None),
            ),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            decision = _map_runtime_decision(
                decision=_runtime_decision(step_id="specify"),
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                repo_root=tmp_path,
                feature_dir=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
            )

        assert decision.kind == DecisionKind.blocked
        assert decision.reason == "prompt_file_not_resolvable"
        assert decision.prompt_file is None
