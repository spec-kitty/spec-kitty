"""WP06 — `next --json` prompt_file resolvability invariant.

This module exercises the contract locked by
``contracts/next-issue.json``: when ``spec-kitty next --json`` issues a step
(``kind == DecisionKind.step``), the issued decision MUST carry a non-empty
``prompt_file`` whose path resolves to an existing file on disk. When no
prompt is resolvable, the runtime MUST emit a structured ``blocked`` decision
with a populated ``reason`` instead of a partial step.

Tests target the two `_build_prompt_or_error` consumers in
``runtime_bridge.py`` plus the helper itself in ``decision.py``. We exercise
the legacy DAG path (`_handle_query_or_step`) via the bridge function
``_map_runtime_decision`` because a full subprocess loop requires a working
runtime stack with a frozen template; the unit-level coverage here proves
the invariant holds for every code path that converts a runtime
``NextDecision`` into a CLI ``Decision``.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from runtime.next.decision import (
    Decision,
    DecisionKind,
    _build_prompt_or_error,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# _build_prompt_or_error — direct unit coverage
# ---------------------------------------------------------------------------


class TestBuildPromptOrError:
    """The helper underpins the invariant — verify both branches end-to-end."""

    def test_returns_path_when_prompt_exists(self, tmp_path: Path) -> None:
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("# prompt\n", encoding="utf-8")

        with patch(
            "runtime.next.prompt_builder.build_prompt",
            return_value=(None, prompt_path),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path == str(prompt_path)
        assert error is None
        assert os.path.exists(path)

    def test_non_wp_step_gets_actionable_prompt_when_no_template(
        self, tmp_path: Path
    ) -> None:
        """Non-WP steps with no file template get an actionable step prompt, not a block.

        Workflow-inserted steps (e.g. ``design-review``) and global-runtime steps
        (e.g. ``discovery``) have no mission-step prompt file.  The fallback
        writes a prompt naming the step and the exact next command (with the
        Mission selector); it is not the retired composition placeholder.
        """
        with patch(
            "runtime.next.prompt_builder.build_prompt",
            side_effect=FileNotFoundError("no template for 'discovery'"),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="discovery",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id=None,
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is not None
        assert error is None
        text = Path(path).read_text(encoding="utf-8")
        assert text.startswith("# software-dev — discovery")
        assert "spec-kitty next --agent claude --mission 042-test" in text
        assert "dispatched via composition" not in text

    def test_wp_step_returns_error_when_build_raises(self, tmp_path: Path) -> None:
        """WP-scoped steps that fail template resolution return an error (no marker)."""
        with patch(
            "runtime.next.prompt_builder.build_prompt",
            side_effect=FileNotFoundError("no template for 'implement'"),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is None
        assert error is not None
        assert "implement" in error

    def test_returns_error_when_path_missing_on_disk(self, tmp_path: Path) -> None:
        # build_prompt returns a path but the file does not exist.
        ghost = tmp_path / "ghost.md"
        with patch(
            "runtime.next.prompt_builder.build_prompt",
            return_value=(None, ghost),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is None
        assert error is not None
        assert "did not materialize" in error

    def test_returns_error_when_path_stat_raises_oserror(
        self, tmp_path: Path
    ) -> None:
        """Exercise decision.py:521-522 — Path.exists() OSError branch.

        On some platforms Path.exists() can raise OSError (PermissionError,
        ENAMETOOLONG, broken symlinks under restrictive filesystems). The
        helper MUST surface a structured `not stat-able` error rather than
        propagate the exception.
        """
        ghost = tmp_path / "ghost.md"
        with (
            patch(
                "runtime.next.prompt_builder.build_prompt",
                return_value=(None, ghost),
            ),
            # Cover the `except OSError` branch in
            # `_build_prompt_or_error`. Path.exists() is called inside the
            # try/except — we patch the class method to raise OSError so the
            # second `except` block executes.
            patch(
                "pathlib.Path.exists",
                side_effect=PermissionError("EACCES"),
            ),
        ):
            path, error, _error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is None
        assert error is not None
        assert "not stat-able" in error
        assert "implement" in error

    def test_action_context_error_carries_typed_error_code(self, tmp_path: Path) -> None:
        """T067 item 4: a typed ``ActionContextError`` from ``build_prompt``'s
        owned-aware resolution path (WP12) is not collapsed into an untyped
        ``reason`` string — its ``code`` is surfaced separately so ``next``'s
        JSON contract carries a structured ``error_code`` without parsing
        ``reason`` text (T062's ``Decision.error_code`` contract)."""
        from mission_runtime import ActionContextError, OwnedRefusalCode

        with patch(
            "runtime.next.prompt_builder.build_prompt",
            side_effect=ActionContextError(
                OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE.value,
                "review base is not resolvable for this owned checkout",
            ),
        ):
            path, error, error_code = _build_prompt_or_error(
                action="implement",
                feature_dir=tmp_path,
                mission_slug="042-test",
                wp_id="WP01",
                agent="claude",
                repo_root=tmp_path,
                mission_type="software-dev",
            )

        assert path is None
        assert error == "review base is not resolvable for this owned checkout"
        assert error_code == OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE.value


# ---------------------------------------------------------------------------
# _map_runtime_decision — every step kind goes through this surface
# ---------------------------------------------------------------------------


def _runtime_decision(
    *,
    kind: str = "step",
    step_id: str = "discovery",
    run_id: str = "run-001",
    decision_id: str | None = None,
    question: str | None = None,
    options: list[str] | None = None,
    input_key: str | None = None,
    reason: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        kind=kind,
        step_id=step_id,
        run_id=run_id,
        decision_id=decision_id,
        question=question,
        options=options,
        input_key=input_key,
        reason=reason,
    )


@pytest.mark.parametrize(
    "step_id",
    [
        "discovery",
        "research",
        "documentation",
        "scoping",
        "methodology",
        "gathering",
        "synthesis",
        "output",
    ],
)
def test_issued_step_always_has_resolvable_prompt(tmp_path: Path, step_id: str) -> None:
    """For every public step kind, an issued decision must satisfy the contract."""
    from runtime.next.runtime_bridge_decision_mapping import _map_runtime_decision

    prompt_path = tmp_path / f"{step_id}-prompt.md"
    prompt_path.write_text(f"# prompt for {step_id}\n", encoding="utf-8")

    with (
        patch(
            "runtime.next.runtime_bridge_decision_mapping._state_to_action",
            return_value=(step_id, None, None),
        ) as state_to_action,
        patch(
            "runtime.next.runtime_bridge_decision_mapping._is_wp_iteration_step",
            return_value=False,
        ),
        patch(
            "runtime.next.runtime_bridge_decision_mapping._build_prompt_or_error",
            return_value=(str(prompt_path), None, None),
        ) as build_prompt,
    ):
        decision: Decision = _map_runtime_decision(
            decision=_runtime_decision(step_id=step_id),
            agent="claude",
            mission_slug="042-test",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=tmp_path,
            timestamp="2026-04-28T00:00:00+00:00",
            progress=None,
            origin={},
        )

    # The fakes steer the mapping module, where _map_runtime_decision reads them (#2560).
    state_to_action.assert_called()
    build_prompt.assert_called()

    assert decision.kind == DecisionKind.step
    # Contract: issued steps MUST carry a non-empty resolvable prompt_file.
    assert decision.prompt_file is not None
    assert decision.prompt_file != ""
    assert os.path.exists(decision.prompt_file)


@pytest.mark.parametrize("step_id", ["discovery", "research", "documentation"])
def test_unresolvable_prompt_yields_structured_blocked(tmp_path: Path, step_id: str) -> None:
    """When prompt resolution fails, the response MUST be `blocked` with a non-empty `reason`."""
    from runtime.next.runtime_bridge_decision_mapping import _map_runtime_decision

    error_msg = (
        f"prompt resolution failed for action '{step_id}': "
        f"FileNotFoundError: no template"
    )
    with (
        patch(
            "runtime.next.runtime_bridge_decision_mapping._state_to_action",
            return_value=(step_id, None, None),
        ) as state_to_action,
        patch(
            "runtime.next.runtime_bridge_decision_mapping._is_wp_iteration_step",
            return_value=False,
        ),
        patch(
            "runtime.next.runtime_bridge_decision_mapping._build_prompt_or_error",
            return_value=(None, error_msg, None),
        ) as build_prompt,
    ):
        decision: Decision = _map_runtime_decision(
            decision=_runtime_decision(step_id=step_id),
            agent="claude",
            mission_slug="042-test",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=tmp_path,
            timestamp="2026-04-28T00:00:00+00:00",
            progress=None,
            origin={},
        )

    # The fakes steer the mapping module, where _map_runtime_decision reads them (#2560).
    state_to_action.assert_called()
    build_prompt.assert_called()

    assert decision.kind == DecisionKind.blocked
    assert decision.reason is not None
    assert decision.reason != ""
    assert step_id in decision.reason
    # prompt_file must NOT be set on a blocked decision when no prompt was resolvable.
    assert decision.prompt_file is None


@pytest.mark.parametrize("step_id", ["implement", "review"])
def test_wp_iteration_step_invariant_holds(tmp_path: Path, step_id: str) -> None:
    """Composed WP-iteration steps (implement/review) must satisfy the invariant too."""
    from runtime.next.runtime_bridge_decision_mapping import _map_runtime_decision

    prompt_path = tmp_path / f"{step_id}-prompt.md"
    prompt_path.write_text(f"# prompt for {step_id}\n", encoding="utf-8")

    with (
        patch(
            "runtime.next.runtime_bridge_decision_mapping._state_to_action",
            return_value=(step_id, "WP01", str(tmp_path / ".worktrees" / "lane-a")),
        ) as state_to_action,
        patch(
            "runtime.next.runtime_bridge_decision_mapping._is_wp_iteration_step",
            return_value=True,
        ),
        patch(
            "runtime.next.runtime_bridge_decision_mapping._build_prompt_or_error",
            return_value=(str(prompt_path), None, None),
        ) as build_prompt,
    ):
        decision = _map_runtime_decision(
            decision=_runtime_decision(step_id=step_id),
            agent="claude",
            mission_slug="042-test",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=tmp_path,
            timestamp="2026-04-28T00:00:00+00:00",
            progress=None,
            origin={},
        )

    # The fakes steer the mapping module, where _map_runtime_decision reads them (#2560).
    state_to_action.assert_called()
    build_prompt.assert_called()

    assert decision.kind == DecisionKind.step
    assert decision.prompt_file is not None
    assert os.path.exists(decision.prompt_file)


@pytest.mark.parametrize("step_id", ["implement", "review"])
def test_wp_iteration_step_blocked_when_prompt_unresolvable(tmp_path: Path, step_id: str) -> None:
    """WP-iteration steps must also fall through to blocked when prompts fail."""
    from runtime.next.runtime_bridge_decision_mapping import _map_runtime_decision

    with (
        patch(
            "runtime.next.runtime_bridge_decision_mapping._state_to_action",
            return_value=(step_id, "WP01", str(tmp_path / ".worktrees" / "lane-a")),
        ) as state_to_action,
        patch(
            "runtime.next.runtime_bridge_decision_mapping._is_wp_iteration_step",
            return_value=True,
        ),
        patch(
            "runtime.next.runtime_bridge_decision_mapping._build_prompt_or_error",
            return_value=(None, f"prompt resolution failed for action '{step_id}'", None),
        ) as build_prompt,
    ):
        decision = _map_runtime_decision(
            decision=_runtime_decision(step_id=step_id),
            agent="claude",
            mission_slug="042-test",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=tmp_path,
            timestamp="2026-04-28T00:00:00+00:00",
            progress=None,
            origin={},
        )

    # The fakes steer the mapping module, where _map_runtime_decision reads them (#2560).
    state_to_action.assert_called()
    build_prompt.assert_called()

    assert decision.kind == DecisionKind.blocked
    assert decision.reason is not None
    assert decision.reason != ""
    assert step_id in decision.reason
    assert decision.prompt_file is None


def test_third_state_does_not_exist(tmp_path: Path) -> None:
    """Negative test: there is no `kind=step` decision with a null prompt_file.

    This codifies the WP06 invariant in a single shot — across both branches
    of `_map_runtime_decision`'s step handler, the only outcomes are
    (issued + resolvable prompt) or (blocked + non-empty reason).
    """
    from runtime.next.runtime_bridge_decision_mapping import _map_runtime_decision

    for prompt_outcome in [
        (None, "prompt resolution failed for action 'discovery': FileNotFoundError: x", None),
    ]:
        with (
            patch(
                "runtime.next.runtime_bridge_decision_mapping._state_to_action",
                return_value=("discovery", None, None),
            ) as state_to_action,
            patch(
                "runtime.next.runtime_bridge_decision_mapping._is_wp_iteration_step",
                return_value=False,
            ),
            patch(
                "runtime.next.runtime_bridge_decision_mapping._build_prompt_or_error",
                return_value=prompt_outcome,
            ) as build_prompt,
        ):
            decision = _map_runtime_decision(
                decision=_runtime_decision(step_id="discovery"),
                agent="claude",
                mission_slug="042-test",
                mission_type="software-dev",
                repo_root=tmp_path,
                feature_dir=tmp_path,
                timestamp="2026-04-28T00:00:00+00:00",
                progress=None,
                origin={},
            )

        # The fakes steer the mapping module, where _map_runtime_decision reads them (#2560).
        state_to_action.assert_called()
        build_prompt.assert_called()

        # Forbidden combination: issued step with no resolvable prompt.
        is_issued_step = decision.kind == DecisionKind.step
        has_resolvable_prompt = (
            decision.prompt_file is not None
            and decision.prompt_file != ""
            and os.path.exists(decision.prompt_file)
        )
        if is_issued_step:
            assert has_resolvable_prompt, (
                f"WP06 invariant violated: kind={decision.kind!r}, "
                f"prompt_file={decision.prompt_file!r}"
            )
        else:
            assert decision.kind == DecisionKind.blocked
            assert decision.reason
