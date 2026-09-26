"""Pure unit tests for the Decision-builder core (#2531 WP07, T027, FR-011).

``runtime_bridge_cores.DecisionEnvelope`` + ``step_or_blocked`` collapse the 29
open-coded ``Decision(...)`` constructions (+ the 4x ``_state_to_action ->
_build_prompt_or_error -> step-or-blocked`` triad) that used to be scattered
across ``runtime_bridge.py``. This module exercises the builder directly,
in-memory (NFR-003/SC-004):

1. The blocked/query/terminal/decision_required branch is PURE — no I/O, no
   branching on ``prompt_file`` (``_non_step_decision``).
2. The step branch is PORT-INJECTED via ``prompt_exists`` — both the
   True and False stub outcomes, plus the defense-in-depth
   ``InvalidStepDecision`` race guard (the injected predicate says "yes" but
   ``Decision.__post_init__``'s own disk stat still says "no").
3. The builder never stamps ``timestamp``/``run_id``/``decision_id`` itself —
   whatever the envelope carries (including ``None``) passes straight
   through.
4. A structural regression: zero raw ``Decision(...)`` constructions remain
   in ``runtime_bridge.py`` (the residual), and every one of the 29 former
   sites now routes through ``_materialize_decision`` /
   ``DecisionEnvelope`` (an AST-level count check).
"""

from __future__ import annotations

import ast
import inspect

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next import runtime_bridge_cores as cores
from runtime.next.decision import Decision, DecisionKind

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _minimal_envelope(**overrides: object) -> cores.DecisionEnvelope:
    fields: dict[str, object] = {
        "kind": DecisionKind.blocked,
        "agent": "agent-x",
        "mission_slug": "042-mission",
        "mission": "software-dev",
        "mission_state": "implement",
        "timestamp": "2026-07-11T00:00:00+00:00",
    }
    fields.update(overrides)
    # A loosely-typed test-helper dict deliberately carries heterogeneous
    # value types (str/list/dict/None) across every DecisionEnvelope field so
    # callers can override any subset; mypy cannot narrow a **dict[str,
    # object] unpack against the dataclass's precise per-field signature.
    # Test-only helper, not production code — see coding-standards.md on
    # narrowly-scoped, individually-justified suppressions.
    return cores.DecisionEnvelope(**fields)  # type: ignore[arg-type]


class _RaisingPromptExists:
    """A ``prompt_exists`` stub that fails the test if ever called.

    Used to prove the pure branches (blocked/terminal/decision_required/
    query) never touch the injected port at all.
    """

    def __call__(self, path: str) -> bool:
        raise AssertionError(f"prompt_exists must not be called for a non-step envelope (got {path!r})")


class _RecordingPromptExists:
    """A ``prompt_exists`` stub that records calls and returns a fixed value."""

    def __init__(self, result: bool) -> None:
        self.result = result
        self.calls: list[str] = []

    def __call__(self, path: str) -> bool:
        self.calls.append(path)
        return self.result


# ---------------------------------------------------------------------------
# 1. Pure branches — blocked / terminal / decision_required / query
# ---------------------------------------------------------------------------


def test_blocked_branch_is_pure_and_preserves_all_fields() -> None:
    envelope = _minimal_envelope(
        kind=DecisionKind.blocked,
        reason="Feature directory not found: /fake-feature-dir/x",
        action="implement",
        wp_id="WP03",
        workspace_path="/repo/.worktrees/x",
        progress={"total_wps": 3},
        origin={"mission_tier": "built-in"},
        run_id="run-123",
        step_id="implement",
    )
    decision = cores.step_or_blocked(envelope, ["guard failure one"], prompt_exists=_RaisingPromptExists())

    assert decision.kind == DecisionKind.blocked
    assert decision.agent == "agent-x"
    assert decision.mission_slug == "042-mission"
    assert decision.mission == "software-dev"
    assert decision.mission_state == "implement"
    assert decision.timestamp == "2026-07-11T00:00:00+00:00"
    assert decision.reason == "Feature directory not found: /fake-feature-dir/x"
    assert decision.action == "implement"
    assert decision.wp_id == "WP03"
    assert decision.workspace_path == "/repo/.worktrees/x"
    assert decision.guard_failures == ["guard failure one"]
    assert decision.progress == {"total_wps": 3}
    assert decision.origin == {"mission_tier": "built-in"}
    assert decision.run_id == "run-123"
    assert decision.step_id == "implement"
    assert decision.is_query is False
    assert decision.prompt_file is None


def test_blocked_branch_preserves_guard_failure_order() -> None:
    """SC-007-adjacent: guard_failures content AND order must survive the builder."""
    envelope = _minimal_envelope(kind=DecisionKind.blocked, reason="multiple guards failed")
    ordered = ["first failure", "second failure", "third failure"]
    decision = cores.step_or_blocked(envelope, ordered, prompt_exists=_RaisingPromptExists())
    assert decision.guard_failures == ordered


def test_terminal_branch_is_pure() -> None:
    envelope = _minimal_envelope(
        kind=DecisionKind.terminal,
        mission_state="done",
        reason="Mission complete",
        run_id="run-9",
        step_id="accept",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_RaisingPromptExists())
    assert decision.kind == DecisionKind.terminal
    assert decision.mission_state == "done"
    assert decision.reason == "Mission complete"
    assert decision.is_query is False
    assert decision.guard_failures == []


def test_decision_required_branch_is_pure_and_carries_its_own_fields() -> None:
    envelope = _minimal_envelope(
        kind=DecisionKind.decision_required,
        mission_state="review",
        reason="Decision required",
        run_id="run-7",
        step_id="review",
        decision_id="dec-1",
        input_key="answer",
        question="Which WP?",
        options=["WP01", "WP02"],
        prompt_file="/fake-prompt-dir/decision-prompt.md",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_RaisingPromptExists())
    assert decision.kind == DecisionKind.decision_required
    assert decision.decision_id == "dec-1"
    assert decision.input_key == "answer"
    assert decision.question == "Which WP?"
    assert decision.options == ["WP01", "WP02"]
    assert decision.prompt_file == "/fake-prompt-dir/decision-prompt.md"
    assert decision.is_query is False


def test_query_branch_is_pure_and_derives_is_query_from_kind() -> None:
    envelope = _minimal_envelope(
        kind=DecisionKind.query,
        mission_state="implement",
        reason=None,
        run_id="run-4",
        preview_step="implement",
        wp_id="WP02",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_RaisingPromptExists())
    assert decision.kind == DecisionKind.query
    assert decision.is_query is True
    assert decision.preview_step == "implement"
    assert decision.wp_id == "WP02"
    # Query decisions never carry origin — the residual query-side builders
    # never populate it, matching the pre-extraction sites exactly.
    assert decision.origin == {}


# ---------------------------------------------------------------------------
# 2. Step branch — port-injected via prompt_exists
# ---------------------------------------------------------------------------


def test_step_branch_builds_step_decision_when_prompt_exists_true(tmp_path: object) -> None:
    # Decision.__post_init__ (decision.py:129) independently stats disk for
    # kind="step" — a real on-disk file is needed here (not just a stub
    # saying "true") so the happy path exercises both layers of the
    # defense-in-depth check identically (see the race-guard test below for
    # the "stub lies" case).
    real_prompt = tmp_path / "WP03-prompt.md"  # type: ignore[operator]
    real_prompt.write_text("# prompt\n", encoding="utf-8")
    prompt_exists = _RecordingPromptExists(result=True)
    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        wp_id="WP03",
        workspace_path="/repo/.worktrees/x",
        prompt_file=str(real_prompt),
        reason="unused-if-step-succeeds",
        run_id="run-1",
        step_id="implement",
    )
    decision = cores.step_or_blocked(envelope, ["gf"], prompt_exists=prompt_exists)

    assert decision.kind == DecisionKind.step
    assert decision.prompt_file == str(real_prompt)
    assert decision.action == "implement"
    assert decision.wp_id == "WP03"
    assert decision.workspace_path == "/repo/.worktrees/x"
    assert decision.guard_failures == ["gf"]
    assert decision.run_id == "run-1"
    assert decision.step_id == "implement"
    # kind=step Decision never carries `reason` (matches every one of the 4
    # pre-extraction "return Decision(kind=step, ...)" sites — none set it).
    assert decision.reason is None
    assert prompt_exists.calls == [str(real_prompt)]


def test_step_branch_falls_back_to_blocked_when_prompt_file_is_none() -> None:
    """Mirrors each of the 4 triads' own 'prompt_file is None' branch.

    ``prompt_exists`` must never be called (nothing to check) and the
    pre-computed ``envelope.reason`` (the residual's own
    ``prompt_error or "<site-default>"``) is used verbatim.
    """
    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        wp_id="WP03",
        workspace_path="/repo/.worktrees/x",
        prompt_file=None,
        reason="no action mapped for step 'implement'; cannot resolve prompt",
        run_id="run-1",
        step_id="implement",
    )
    prompt_exists = _RaisingPromptExists()
    decision = cores.step_or_blocked(envelope, [], prompt_exists=prompt_exists)

    assert decision.kind == DecisionKind.blocked
    assert decision.reason == "no action mapped for step 'implement'; cannot resolve prompt"
    assert decision.prompt_file is None
    assert decision.action == "implement"
    assert decision.wp_id == "WP03"


def test_step_branch_falls_back_to_blocked_when_prompt_exists_returns_false() -> None:
    """The resolved-but-does-not-exist branch always uses the literal
    ``"prompt_file_not_resolvable"`` — verified against all 4 pre-extraction
    triads' ``except InvalidStepDecision`` clauses (see DecisionEnvelope's
    docstring). ``envelope.reason`` is deliberately set to something else
    here to prove the literal wins, not the envelope's own reason field."""
    prompt_exists = _RecordingPromptExists(result=False)
    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        wp_id="WP03",
        prompt_file="/fake-prompt-dir/WP03-prompt-vanished.md",
        reason="this-must-not-be-used",
        run_id="run-1",
        step_id="implement",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=prompt_exists)

    assert decision.kind == DecisionKind.blocked
    assert decision.reason == "prompt_file_not_resolvable"
    assert prompt_exists.calls == ["/fake-prompt-dir/WP03-prompt-vanished.md"]


def test_step_branch_invalid_step_decision_race_guard_still_fires(tmp_path: object) -> None:
    """Defense-in-depth: even when the injected predicate says "yes", the
    real ``Decision.__post_init__`` disk stat is still authoritative — a
    fooled ``prompt_exists`` (always True regardless of the real path) must
    still fall back to blocked when the path genuinely does not resolve,
    exactly like the pre-extraction try/except InvalidStepDecision guard."""
    missing_path = str(tmp_path / "does-not-exist.md")  # type: ignore[operator]

    def _always_true(_path: str) -> bool:
        return True

    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        prompt_file=missing_path,
        reason="this-must-not-be-used-either",
        run_id="run-1",
        step_id="implement",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_always_true)

    assert decision.kind == DecisionKind.blocked
    assert decision.reason == "prompt_file_not_resolvable"


def test_step_branch_succeeds_against_a_real_file(tmp_path: object) -> None:
    """Production-shaped smoke test using the real ``Path.is_file`` port
    (not a stub) end to end, proving the production wiring on the residual
    (its ``_prompt_exists`` helper) agrees with the pure predicate."""
    real_prompt = tmp_path / "WP03-prompt.md"  # type: ignore[operator]
    real_prompt.write_text("# prompt\n", encoding="utf-8")

    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        wp_id="WP03",
        prompt_file=str(real_prompt),
        run_id="run-1",
        step_id="implement",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=rb._prompt_exists)
    assert decision.kind == DecisionKind.step
    assert decision.prompt_file == str(real_prompt)


# ---------------------------------------------------------------------------
# 3. Never stamps timestamp/run_id/decision_id (NFR-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [DecisionKind.blocked, DecisionKind.terminal, DecisionKind.decision_required, DecisionKind.query],
)
def test_never_stamps_timestamp_run_id_decision_id_when_present(kind: str) -> None:
    envelope = _minimal_envelope(
        kind=kind,
        timestamp="caller-supplied-timestamp",
        run_id="caller-supplied-run-id",
        decision_id="caller-supplied-decision-id",
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_RaisingPromptExists())
    assert decision.timestamp == "caller-supplied-timestamp"
    assert decision.run_id == "caller-supplied-run-id"
    assert decision.decision_id == "caller-supplied-decision-id"


@pytest.mark.parametrize(
    "kind",
    [DecisionKind.blocked, DecisionKind.terminal, DecisionKind.decision_required, DecisionKind.query],
)
def test_never_invents_run_id_or_decision_id_when_absent(kind: str) -> None:
    """When the caller has none to thread (run_id/decision_id absent), the
    builder must leave them ``None`` rather than minting a substitute."""
    envelope = _minimal_envelope(kind=kind, run_id=None, decision_id=None)
    decision = cores.step_or_blocked(envelope, [], prompt_exists=_RaisingPromptExists())
    assert decision.run_id is None
    assert decision.decision_id is None


def test_never_invents_run_id_for_step_kind(tmp_path: object) -> None:
    real_prompt = tmp_path / "WP03-prompt.md"  # type: ignore[operator]
    real_prompt.write_text("# prompt\n", encoding="utf-8")
    prompt_exists = _RecordingPromptExists(result=True)
    envelope = _minimal_envelope(
        kind=DecisionKind.step,
        action="implement",
        prompt_file=str(real_prompt),
        run_id=None,
    )
    decision = cores.step_or_blocked(envelope, [], prompt_exists=prompt_exists)
    assert decision.kind == DecisionKind.step
    assert decision.run_id is None


# ---------------------------------------------------------------------------
# 4. guard_failures normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_failures", [None, []])
def test_guard_failures_none_or_empty_normalizes_to_empty_list(guard_failures: list[str] | None) -> None:
    envelope = _minimal_envelope(kind=DecisionKind.blocked, reason="x")
    decision = cores.step_or_blocked(envelope, guard_failures, prompt_exists=_RaisingPromptExists())
    assert decision.guard_failures == []


def test_guard_failures_default_matches_decision_default_factory() -> None:
    """Several original sites never set ``guard_failures`` at all (relying on
    ``Decision``'s own default-factory ``[]``); others passed ``guard_failures
    or []`` explicitly. Both collapse to the identical empty list here."""
    envelope_a = _minimal_envelope(kind=DecisionKind.blocked, reason="x")
    envelope_b = _minimal_envelope(kind=DecisionKind.blocked, reason="x")
    decision_a = cores.step_or_blocked(envelope_a, None, prompt_exists=_RaisingPromptExists())
    decision_b = cores.step_or_blocked(envelope_b, [], prompt_exists=_RaisingPromptExists())
    assert (
        decision_a.guard_failures
        == decision_b.guard_failures
        == Decision(
            kind=DecisionKind.blocked,
            agent=None,
            mission_slug="x",
            mission="x",
            mission_state="x",
            timestamp="x",
        ).guard_failures
    )


# ---------------------------------------------------------------------------
# 5. Structural regression — every former open-coded site routes through the
#    builder (#2531 WP07 acceptance: "29 Decision(...) sites collapsed")
# ---------------------------------------------------------------------------


def _iter_calls(tree: ast.AST) -> list[ast.Call]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def test_runtime_bridge_has_zero_raw_decision_constructions() -> None:
    """The residual (``runtime_bridge.py``) must not construct ``Decision``
    directly anywhere anymore — every construction is routed through
    ``runtime_bridge_cores.step_or_blocked`` via ``_materialize_decision``."""
    source = inspect.getsource(rb)
    tree = ast.parse(source)
    bare_decision_calls = [call for call in _iter_calls(tree) if isinstance(call.func, ast.Name) and call.func.id == "Decision"]
    assert bare_decision_calls == [], "runtime_bridge.py must not construct Decision(...) directly; route through _materialize_decision/DecisionEnvelope instead"


def test_runtime_bridge_materializes_every_former_decision_site() -> None:
    """29 pre-extraction ``Decision(...)`` sites collapsed via the 4x
    triad (12 sites -> 4 calls) into 21 ``_materialize_decision(...)`` call
    sites (29 - 8 = 21; each triad saves 2 calls by folding its
    prompt-file-None / step / InvalidStepDecision-except trio into one
    ``kind=step`` envelope call). A regression on this exact count catches a
    silent re-introduction of an open-coded ``Decision(...)`` construction
    that bypasses the builder.

    22nd site (#801, PR #845): the ``_dn_bootstrap`` merged-mission
    short-circuit materializes its terminal decision through the builder —
    a legitimate site routed through ``_materialize_decision``. #2947 then
    added the committed-authority merged-mission
    short-circuit, whose two verdicts (``kind=terminal`` and the
    conflict/stale-workspace case) are emitted from
    ``_merged_mission_short_circuit``. Later EXP routing contributes one more
    legitimate site, making the live count 24. Mission
    runtime-advance-guard-topology-wp-completion-01M1W6VZ (#3884, FR-010) adds
    the 25th: ``_dn_dependency_gate``'s new sibling
    ``except MissionSelectorAmbiguous`` arm (alongside the existing
    ``except CanonicalStatusNotFoundError`` arm), converting an ambiguous
    ``mission_slug`` handle into a structured ``blocked`` Decision through the
    same builder rather than letting the exception propagate uncaught. Mission
    advancing-next-board-unification (#4980, #4975) adds the 26th and 27th: the
    board-authority-backed WP-iteration selector routes its ``kind=blocked``
    (no-actionable-WP / coord-read fail-closed recovery) and re-dispatch
    ``kind=step`` envelopes through the same builder in
    ``_build_wp_iteration_decision`` / ``_map_wp_step_decision``, replacing the
    bare ``_state_to_action`` divergence. All go
    through ``_materialize_decision``; the zero-open-coded-``Decision``
    invariant is unchanged. A regression on this exact count catches a silent
    re-introduction of an open-coded ``Decision(...)`` construction that
    bypasses the builder."""
    source = inspect.getsource(rb)
    tree = ast.parse(source)
    materialize_calls = [call for call in _iter_calls(tree) if isinstance(call.func, ast.Name) and call.func.id == "_materialize_decision"]
    assert len(materialize_calls) == 27


def test_cores_module_is_the_sole_home_of_raw_decision_construction() -> None:
    """``runtime_bridge_cores.py`` is the ONLY module allowed to construct
    ``Decision(...)`` directly post-WP07 (its three private helpers
    ``_non_step_decision`` / ``_step_decision`` / ``_blocked_from_step_
    envelope``)."""
    source = inspect.getsource(cores)
    tree = ast.parse(source)
    bare_decision_calls = [call for call in _iter_calls(tree) if isinstance(call.func, ast.Name) and call.func.id == "Decision"]
    # Exactly 3: one in each of the three construction helpers.
    assert len(bare_decision_calls) == 3
