"""Real-runtime integration walk for the research mission.

C-007 enforcement (spec constraint, FINAL GATE):
    The following symbols MUST NOT appear in any unittest.mock.patch target
    in this file. Reviewer greps; any hit blocks approval and blocks the
    mission from merging.

        - _dispatch_via_composition
        - StepContractExecutor.execute
        - ProfileInvocationExecutor.invoke
        - _load_frozen_template (and any frozen-template loader)
        - load_validated_graph
        - resolve_context

This is the test that proves the v1 P0 finding is closed:
    `get_or_start_run('demo-research-walk', tmp_repo, 'research')`
    succeeds end-to-end without raising MissionRuntimeError, the runtime
    advances at least one composed step via the real composition path, and
    structured guard failures fire on missing artifacts.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from specify_cli.invocation.writer import EVENTS_DIR
from runtime.next._internal_runtime.engine import _read_snapshot
from runtime.next.runtime_bridge import (
    _check_composed_action_guard,
    decide_next_via_runtime,
    get_or_start_run,
    query_current_state,
)


# ---------------------------------------------------------------------------
# Test infrastructure — repo scaffold + research mission feature_dir
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


_NON_INVOCATION_OP_FILES = {
    "lifecycle.jsonl",
    "ops-index.jsonl",
    "propagation-errors.jsonl",
}


def _invocation_trail_files(repo_root: Path) -> list[Path]:
    invocations_dir = repo_root / EVENTS_DIR
    return sorted(path for path in invocations_dir.glob("*.jsonl") if path.name not in _NON_INVOCATION_OP_FILES)


def _init_min_repo(repo_root: Path) -> None:
    """Initialize a minimal git repo as the test mission's project root."""
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    (repo_root / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_root, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )


def _scaffold_research_feature(repo_root: Path, mission_slug: str) -> Path:
    """Create kitty-specs/<slug>/ with mission_type=research meta."""
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "research"}),
        encoding="utf-8",
    )
    return feature_dir


@pytest.fixture
def isolated_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A fresh git repo with no kitty-specs folder."""
    repo_root = tmp_path / "repo"
    _init_min_repo(repo_root)

    # Clear discovery env that might steer template resolution.
    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)
    monkeypatch.delenv("KITTIFY_MISSION_PATHS", raising=False)

    yield repo_root


# ---------------------------------------------------------------------------
# Test 1 — closes the v1 P0 finding: research template resolves & runs start
# ---------------------------------------------------------------------------


def test_get_or_start_run_succeeds_for_research(isolated_repo: Path) -> None:
    """V1 P0 closure: ``get_or_start_run('demo-research-walk', repo, 'research')``.

    The v1 finding raised ``MissionRuntimeError: Mission 'research' not found``
    because the runtime template chain could not resolve a research template
    key. WP01 added ``mission-runtime.yaml`` for the research mission; this
    test proves the resolution succeeds end-to-end without any patching.
    """
    _scaffold_research_feature(isolated_repo, "demo-research-walk")

    run_ref = get_or_start_run("demo-research-walk", isolated_repo, "research")

    # Run was created and persisted under .kittify/runtime/runs/.
    run_dir = Path(run_ref.run_dir)
    assert run_dir.is_dir(), f"run_dir not created: {run_dir}"
    assert (run_dir / "state.json").is_file(), f"state.json missing — run never bootstrapped: {run_dir}"

    # The run_ref must carry a research mission key (NOT a default fallback).
    assert run_ref.mission_key == "research", (
        f"Expected mission_key='research'; got {run_ref.mission_key!r}. "
        "If this is 'software-dev', the template resolver fell through to a "
        "wrong default and the v1 P0 finding is still open."
    )

    # The feature-runs index records the entry under the research key.
    # WP05 / FR-016: keyed by mission_id, or ``legacy-<slug>`` for a mission
    # without one (this scaffold's meta.json); the bare slug is never a key.
    feature_runs = isolated_repo / ".kittify" / "runtime" / "feature-runs.json"
    assert feature_runs.is_file()
    index = json.loads(feature_runs.read_text(encoding="utf-8"))
    entry = index["legacy-demo-research-walk"]
    assert entry["mission_type"] == "research"
    assert entry["mission_slug"] == "demo-research-walk"


def test_initial_success_bootstrap_issues_research_scoping_prompt(
    isolated_repo: Path,
) -> None:
    """CLI advancing bootstrap semantics issue a real type-specific prompt."""
    _scaffold_research_feature(isolated_repo, "research-handoff")

    decision = decide_next_via_runtime(
        "codex",
        "research-handoff",
        "success",
        isolated_repo,
    )

    assert decision.kind.value == "step"
    assert decision.action == "scoping"
    assert decision.step_id == "scoping"
    assert decision.prompt_file is not None
    assert Path(decision.prompt_file).is_file()


def test_read_only_replay_query_preserves_outstanding_research_step(
    isolated_repo: Path,
) -> None:
    """Lost handoff output must not make a replay complete the issued step."""
    _scaffold_research_feature(isolated_repo, "research-handoff-replay")
    first = decide_next_via_runtime(
        "codex",
        "research-handoff-replay",
        "success",
        isolated_repo,
    )
    assert first.step_id == "scoping"

    run_ref = get_or_start_run("research-handoff-replay", isolated_repo, "research")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    query = query_current_state("codex", "research-handoff-replay", isolated_repo)
    snapshot_after = _read_snapshot(Path(run_ref.run_dir))

    assert query.kind.value == "query"
    assert query.mission_state == "scoping"
    assert query.step_id == "scoping"
    assert query.run_id == run_ref.run_id
    assert snapshot_after == snapshot_before
    assert snapshot_after.issued_step_id == "scoping"
    assert list(snapshot_after.completed_steps) == []


# ---------------------------------------------------------------------------
# Test 2 — composition path advances the run state for a research step
# ---------------------------------------------------------------------------


def test_research_advances_one_composed_step(isolated_repo: Path) -> None:
    """The research/scoping action advances the runtime via the composition path.

    Observable proof (no patches on the C-007 forbidden list):

    * (a) Run state advances past the initial step — the engine snapshot's
      ``completed_steps`` moves from empty to containing ``"scoping"``.
    * (b) The ``Decision`` returned by ``decide_next_via_runtime`` after
      success carries the next research-native step ID
      (``"methodology"``) — not a software-dev default verb such as
      ``"plan"``. This proves the composed dispatch fired for the
      research mission and the planner moved through the research DAG.
    * (c) The invocation trail under
      the canonical Op storage directory contains paired started + completed
      lifecycle records (asserted in
      :func:`test_paired_invocation_lifecycle_recorded`).
    * (d) No legacy ``runtime_next_step`` was re-entered for the
      composed scoping action — implicitly proven because the snapshot
      advanced exactly one step rather than two (a fall-through would
      double-advance).
    """
    feature_dir = _scaffold_research_feature(isolated_repo, "demo-research-walk")
    # Scoping requires spec.md per the research guard chain.
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")

    # First call issues the first step (no advance yet).
    first = decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )
    assert first.step_id == "scoping", f"Expected scoping as first step; got {first.step_id!r}. If this is 'specify' the planner is using software-dev defaults."

    # Snapshot before the composition dispatch — completed_steps is empty.
    run_ref = get_or_start_run("demo-research-walk", isolated_repo, "research")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    assert list(snapshot_before.completed_steps) == []
    assert snapshot_before.issued_step_id == "scoping"

    # Drive the composition dispatch by reporting success on the issued step.
    decision = decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )

    # (a) The snapshot advanced — scoping is now in completed_steps.
    snapshot_after = _read_snapshot(Path(run_ref.run_dir))
    assert "scoping" in snapshot_after.completed_steps, f"scoping not marked completed; completed_steps={snapshot_after.completed_steps!r}"

    # (b) Next research-native step issued — methodology, not 'plan'.
    assert snapshot_after.issued_step_id == "methodology", (
        f"Expected next step 'methodology' (research-native); got "
        f"{snapshot_after.issued_step_id!r}. A value of 'plan' would mean "
        "the bridge fell back to software-dev planning."
    )
    decision_kind = decision.kind.value if hasattr(decision.kind, "value") else str(decision.kind)
    assert decision_kind in ("step", "blocked"), f"Expected step or blocked decision; got {decision.kind!r}"
    assert decision.mission == "research"


# ---------------------------------------------------------------------------
# Test 3 — paired invocation lifecycle records carry research action_hint
# ---------------------------------------------------------------------------


def test_paired_invocation_lifecycle_recorded(isolated_repo: Path) -> None:
    """Each composed invocation writes paired started + completed records.

    The composition dispatch routes through ``ProfileInvocationExecutor``
    which writes JSONL records under the canonical Op storage directory.
    Each invocation must have at least one ``started`` line; the test also
    confirms recorded ``action`` values stay within the research-native
    step IDs (no software-dev verbs leaking through).

    Reading the trail directly (not patching the writer) keeps this test
    out of the C-007 forbidden surface.
    """
    feature_dir = _scaffold_research_feature(isolated_repo, "demo-research-walk")
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")

    # Issue the first step then dispatch composition for it.
    decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )
    decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )

    invocations_dir = isolated_repo / EVENTS_DIR
    assert invocations_dir.is_dir(), f"Invocations dir missing: {invocations_dir}. Composition dispatch did not produce a paired invocation trail."
    trail_files = _invocation_trail_files(isolated_repo)
    assert trail_files, (
        f"No invocation trail files written under {invocations_dir}. ProfileInvocationExecutor.invoke was not called from the composed research/scoping dispatch."
    )

    research_actions = {"scoping", "methodology", "gathering", "synthesis", "output"}
    valid_outcomes = {"done", "failed"}
    saw_started = False
    saw_pair = False
    for trail in trail_files:
        events: list[dict[str, object]] = []
        for raw in trail.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        # Each trail file must contain at least one record.
        assert events, f"Invocation trail empty: {trail}"
        # The first record is always a started event.
        first = events[0]
        assert first.get("event") == "started", f"First record in {trail.name} is not a started event: {first!r}"
        saw_started = True
        # The recorded action MUST be a research-native step ID — not a
        # software-dev verb (e.g., 'specify', 'plan'). The action_hint flows
        # from the contract.action through StepContractExecutor.invoke into
        # the InvocationRecord, so this is the structural assertion that the
        # research dispatch wired the right action.
        action = first.get("action")
        assert action in research_actions, f"Recorded action {action!r} is not a research-native step ID. Trail={trail.name}; record={first!r}"
        # FR-012: every started invocation in this trail MUST be paired with
        # a completed event whose outcome is 'done' or 'failed'. A trail
        # that holds only a started record indicates a torn lifecycle and
        # would let FR-012 silently regress.
        completed = [e for e in events if e.get("event") == "completed"]
        assert completed, f"Trail {trail.name} has a started record but no completed event; FR-012 requires paired lifecycle for every dispatched invocation."
        outcome = completed[-1].get("outcome")
        assert outcome in valid_outcomes, f"Completed event in {trail.name} has invalid outcome {outcome!r}; FR-012 requires one of {sorted(valid_outcomes)}."
        saw_pair = True
    assert saw_started, "No started records found across the invocation trail."
    assert saw_pair, "No paired started+completed records found across the trail."


# ---------------------------------------------------------------------------
# Test 4 — missing artifact blocks advancement with structured guard failure
# ---------------------------------------------------------------------------


def test_missing_artifact_blocks_advancement_with_structured_error(
    isolated_repo: Path,
) -> None:
    """Without spec.md the research/scoping guard surfaces a structured failure.

    Observable surface (no forbidden patches):

    * The post-composition guard returns the structured failure
      ``"Required artifact missing: spec.md"`` for ``research/scoping``.
    * The ``Decision`` returned by ``decide_next_via_runtime`` is
      ``blocked`` with that failure threaded through ``guard_failures``.
    * The run-state snapshot does NOT advance — ``completed_steps``
      remains empty and ``issued_step_id`` stays at ``"scoping"``.
    """
    _scaffold_research_feature(isolated_repo, "demo-research-walk")
    # Intentionally do NOT write spec.md.

    # Issue scoping.
    decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )

    # Drive composition dispatch; the guard MUST fire post-execution.
    decision = decide_next_via_runtime(
        "test-operator",
        "demo-research-walk",
        "success",
        isolated_repo,
    )

    # Surface check: the Decision is blocked with the spec.md failure.
    decision_kind = decision.kind.value if hasattr(decision.kind, "value") else str(decision.kind)
    assert decision_kind == "blocked", f"Expected blocked decision when spec.md is missing; got {decision.kind!r}"
    assert decision.guard_failures, f"Expected guard_failures populated; got {decision.guard_failures!r}"
    assert any("spec.md" in failure for failure in decision.guard_failures), (
        f"spec.md not mentioned in guard_failures={decision.guard_failures!r}. Structured failure surface regressed."
    )

    # State did not advance — scoping stayed pending.
    run_ref = get_or_start_run("demo-research-walk", isolated_repo, "research")
    snapshot = _read_snapshot(Path(run_ref.run_dir))
    assert list(snapshot.completed_steps) == [], f"Run advanced despite guard failure; completed_steps={snapshot.completed_steps!r}"
    assert snapshot.issued_step_id == "scoping", f"issued_step_id moved off scoping despite guard failure: {snapshot.issued_step_id!r}"


# ---------------------------------------------------------------------------
# Test 5 — unknown research action fails closed at the dispatch surface
# ---------------------------------------------------------------------------


def test_unknown_research_action_fails_closed(tmp_path: Path) -> None:
    """``mission='research'`` with an unknown action surfaces a structured failure.

    Closes the v1 P1 silent-pass finding at the integration layer: the
    bridge's ``_check_composed_action_guard`` chain MUST emit
    ``"No guard registered for research action: <action>"`` for any
    unknown research action so the dispatch path cannot mistake an
    unhandled action for success.

    WP05's bridge unit test covers the unit-level surface; this test
    confirms the same fail-closed default fires through the actual
    bridge module's exported guard function (no patches).
    """
    feature_dir = tmp_path / "kitty-specs" / "research-test-feature"
    feature_dir.mkdir(parents=True)
    # Seed every research artifact so the guard cannot fail on a real
    # artifact check; the unknown-action default is the only path left.
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "source-register.csv").write_text("id,citation\n1,A\n2,B\n3,C\n", encoding="utf-8")
    (feature_dir / "findings.md").write_text("# findings", encoding="utf-8")
    (feature_dir / "report.md").write_text("# report", encoding="utf-8")
    (feature_dir / "mission-events.jsonl").write_text(
        "\n".join(
            json.dumps(entry, sort_keys=True)
            for entry in [
                {"name": "src-1", "type": "source_documented"},
                {"name": "src-2", "type": "source_documented"},
                {"name": "src-3", "type": "source_documented"},
                {"name": "publication_approved", "type": "gate_passed"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    failures = _check_composed_action_guard("bogus", feature_dir, mission="research")
    assert failures == ["No guard registered for research action: bogus"], (
        f"Fail-closed default did not fire for unknown research action; got failures={failures!r}"
    )
