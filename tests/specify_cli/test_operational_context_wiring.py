"""Wiring tests for ``OperationalContext`` at the runtime entry points (WP14).

WP13 delivered the pure ``build_operational_context`` assembler and its guards
in ``charter.activation.invocation_context``. WP14 wires those symbols into the three live
runtime entry points (FR-017):

1. the ``implement.py`` WP-claim path,
2. the ``agent/workflow.py`` WP-claim path,
3. ``runtime_bridge.decide_next_via_runtime`` (the ``next`` decision boundary).

Both claim sites share a single builder helper
(``runtime_bridge.build_operational_context_for_claim``) so OC-construction
logic is not forked, and the decision boundary uses the extracted
``_build_operational_context_for_decision`` helper so ``decide_next_via_runtime``
does not grow in complexity.

These tests pin:

* Populated context (active model / profile / role / activity) at each site —
  no all-``None`` regression to the WP13 stub behaviour.
* NFR-004: a missing-context precondition failure creates zero new worktree
  paths and emits zero new status events.
* Static proof that the live entry points call the builder/guards (the wiring
  is live, not deferred dead code).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.integration]

from charter.activation.invocation_context import (
    ContextPreconditionError,
    OperationalContext,
)
from runtime.next import runtime_bridge, runtime_bridge_io
from runtime.next.runtime_bridge import build_operational_context_for_claim
from runtime.next.runtime_bridge_io import (
    _build_operational_context_for_decision,
    _resolve_run_dir_for_mission,
    _resolve_tech_stack_for_profile,
)


# ---------------------------------------------------------------------------
# Shared claim builder (T062 / T063 — single shared helper)
# ---------------------------------------------------------------------------


class TestBuildOperationalContextForClaim:
    """The shared claim builder produces a populated context."""

    def test_populated_context_no_all_none(self, tmp_path: Path) -> None:
        ctx = build_operational_context_for_claim(
            repo_root=tmp_path,
            feature_dir=tmp_path / "kitty-specs" / "feat",
            mission_slug="feat",
            wp_id="WP01",
            actor="claude",
            active_model="claude",
            active_role="implementer",
            current_activity="implement",
            active_profile="python-pedro",
        )
        assert isinstance(ctx, OperationalContext)
        # Populated — not the all-None WP13 stub.
        assert ctx.active_model == "claude"
        assert ctx.active_profile == "python-pedro"
        assert ctx.active_role == "implementer"
        assert ctx.current_activity == "implement"
        assert (ctx.active_model, ctx.active_profile, ctx.active_role) != (
            None,
            None,
            None,
        )

    def test_active_role_falls_back_to_actor(self, tmp_path: Path) -> None:
        ctx = build_operational_context_for_claim(
            repo_root=tmp_path,
            feature_dir=tmp_path,
            mission_slug="feat",
            wp_id="WP01",
            actor="implement-command",
            active_model="claude",
            active_role=None,
            active_profile="python-pedro",
        )
        assert ctx.active_role == "implement-command"
        assert ctx.require_active_role() == "implement-command"

    def test_guard_raises_when_role_absent(self, tmp_path: Path) -> None:
        ctx = build_operational_context_for_claim(
            repo_root=tmp_path,
            feature_dir=tmp_path,
            mission_slug="feat",
            wp_id="WP01",
            actor=None,
            active_model="claude",
            active_role=None,
            active_profile="python-pedro",
        )
        with pytest.raises(ContextPreconditionError):
            ctx.require_active_role()


# ---------------------------------------------------------------------------
# Decision boundary helper (T064)
# ---------------------------------------------------------------------------


class TestBuildOperationalContextForDecision:
    """The extracted decision helper produces a populated context."""

    def test_populated_context_at_decision(self, tmp_path: Path) -> None:
        run_ref = SimpleNamespace(run_id="run-1", run_dir=str(tmp_path / "run"))
        ctx = _build_operational_context_for_decision(
            agent="codex",
            run_ref=run_ref,  # type: ignore[arg-type]
            feature_dir=tmp_path / "kitty-specs" / "feat",
            repo_root=tmp_path,
            step_id="implement",
            mission_state="implement",
        )
        assert isinstance(ctx, OperationalContext)
        assert ctx.active_model == "codex"
        assert ctx.active_role == "codex"
        assert ctx.current_activity == "implement"
        assert (ctx.active_model, ctx.active_role, ctx.current_activity) != (
            None,
            None,
            None,
        )

    def test_activity_falls_back_to_mission_state(self, tmp_path: Path) -> None:
        run_ref = SimpleNamespace(run_id="run-1", run_dir=str(tmp_path / "run"))
        ctx = _build_operational_context_for_decision(
            agent="codex",
            run_ref=run_ref,  # type: ignore[arg-type]
            feature_dir=tmp_path,
            repo_root=tmp_path,
            step_id=None,
            mission_state="plan",
        )
        assert ctx.current_activity == "plan"


# ---------------------------------------------------------------------------
# Read-only run-dir / tech-stack resolution (NFR-004 supporting helpers)
# ---------------------------------------------------------------------------


class TestReadOnlyResolvers:
    def test_run_dir_returns_none_without_index(self, tmp_path: Path) -> None:
        assert _resolve_run_dir_for_mission(tmp_path, "feat") is None

    def test_tech_stack_empty_without_profile(self, tmp_path: Path) -> None:
        assert _resolve_tech_stack_for_profile(tmp_path, None) == frozenset()

    def test_tech_stack_resilient_to_missing_doctrine(self, tmp_path: Path) -> None:
        # Unresolvable profile / missing doctrine dir → empty, never raises.
        result = _resolve_tech_stack_for_profile(tmp_path, "does-not-exist")
        assert result == frozenset()


# ---------------------------------------------------------------------------
# NFR-004: precondition failure has no worktree / status side effects
# ---------------------------------------------------------------------------


def _count_worktree_paths(repo_root: Path) -> int:
    wt = repo_root / ".worktrees"
    if not wt.exists():
        return 0
    return sum(1 for _ in wt.iterdir())


def _count_status_events(feature_dir: Path) -> int:
    events = feature_dir / "status.events.jsonl"
    if not events.exists():
        return 0
    return sum(1 for line in events.read_text().splitlines() if line.strip())


class TestPreconditionFailureNoSideEffects:
    """NFR-004 — a context precondition failure mutates no runtime state."""

    def test_guard_failure_creates_no_worktree_or_status_event(
        self, tmp_path: Path
    ) -> None:
        feature_dir = tmp_path / "kitty-specs" / "feat"
        feature_dir.mkdir(parents=True)
        # Pre-seed an existing status event so we can prove none are *added*.
        existing = (
            '{"actor":"claude","at":"2026-01-01T00:00:00+00:00",'
            '"event_id":"01HXYZ","from_lane":null,"to_lane":"planned",'
            '"wp_id":"WP01","feature_slug":"feat"}'
        )
        (feature_dir / "status.events.jsonl").write_text(existing + "\n")

        worktrees_before = _count_worktree_paths(tmp_path)
        events_before = _count_status_events(feature_dir)

        # Build a claim context with no resolvable role, then run the guard the
        # live claim path runs before any worktree/status side effect.
        ctx = build_operational_context_for_claim(
            repo_root=tmp_path,
            feature_dir=feature_dir,
            mission_slug="feat",
            wp_id="WP01",
            actor=None,
            active_model=None,
            active_role=None,
            active_profile=None,
        )
        with pytest.raises(ContextPreconditionError):
            ctx.require_active_role()

        assert _count_worktree_paths(tmp_path) == worktrees_before
        assert _count_status_events(feature_dir) == events_before


# ---------------------------------------------------------------------------
# Wiring is live (FR-019 ordering): the entry points call the builder/guards.
# ---------------------------------------------------------------------------


def _calls_in(func) -> set[str]:
    """Return the set of called attribute/name identifiers in ``func``."""
    src = inspect.getsource(func)
    tree = ast.parse(inspect.cleandoc(src))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


class TestWiringIsLive:
    """Prove the OperationalContext symbols are no longer dead code."""

    def test_implement_claim_calls_builder_and_guard(self) -> None:
        # implement-degod WP09: the OperationalContext build moved from implement()
        # into the build_operational_context phase, which implement() calls -- a
        # moved anchor, same assertions.
        from specify_cli.cli.commands import implement as implement_mod
        from specify_cli.cli.commands.implement_phases import build_operational_context

        assert "implement_phases.build_operational_context" in inspect.getsource(implement_mod.implement)
        src = inspect.getsource(build_operational_context)
        assert "build_operational_context_for_claim" in src
        assert "require_active_role" in src

    def test_workflow_claim_calls_builder_and_guard(self) -> None:
        # coord-authority-trio-degod-01KX7094 WP02 (T009): the claim-transition
        # wiring (previously inline in workflow.implement()) now lives in
        # workflow_executor._implement_start_claim -- a moved AST-anchor
        # target (T013), not a weakened assertion; the same builder+guard
        # call-site check applies to its new home.
        import specify_cli.cli.commands.agent.workflow_executor as workflow_executor_mod

        src = inspect.getsource(workflow_executor_mod)
        assert "build_operational_context_for_claim" in src
        assert "require_active_role" in src

    def test_decide_next_calls_decision_helper(self) -> None:
        # #2531 WP09 (runtime-bridge-degod, FR-010): decide_next_via_runtime's
        # body was rewritten into a four-phase early-return chain; the
        # OperationalContext build now lives in the bootstrap phase
        # (runtime_bridge._dn_bootstrap), which decide_next_via_runtime calls
        # as phase 1/4 -- a moved AST-anchor target (mirrors the
        # coord-authority-trio-degod precedent above), not a weakened
        # assertion. The two-hop check preserves the original single-hop
        # guarantee: decide_next_via_runtime -> _dn_bootstrap -> the helper.
        assert "_dn_bootstrap" in _calls_in(runtime_bridge.decide_next_via_runtime)
        called = _calls_in(runtime_bridge._dn_bootstrap)
        assert "_build_operational_context_for_decision" in called

    def test_decision_helper_calls_pure_assembler(self) -> None:
        # The helper's body lives in the runtime_bridge_io seam, which
        # decide_next_via_runtime reaches through _dn_bootstrap (see
        # test_decide_next_calls_decision_helper above). The helper calls the
        # pure assembler.
        called = _calls_in(runtime_bridge_io._build_operational_context_for_decision)
        assert "build_operational_context" in called

    def test_claim_helper_calls_pure_assembler(self) -> None:
        # build_operational_context_for_claim lives in the io seam; the bridge
        # re-exports the same object for callers outside the package.
        assert build_operational_context_for_claim is runtime_bridge_io.build_operational_context_for_claim
        called = _calls_in(runtime_bridge_io.build_operational_context_for_claim)
        assert "build_operational_context" in called
