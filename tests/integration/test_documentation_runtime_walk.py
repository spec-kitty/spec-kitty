"""Real-runtime integration walk for the documentation mission.

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

This file proves SC-001 / SC-003 / SC-004 for documentation mission composition (#502):
    ``get_or_start_run('demo-docs-walk', tmp_repo, 'documentation')``
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
    _resolve_runtime_template_in_root,
    decide_next_via_runtime,
    get_or_start_run,
)


# ---------------------------------------------------------------------------
# Test infrastructure — repo scaffold + documentation mission feature_dir
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


_NON_INVOCATION_OP_FILES = {
    "lifecycle.jsonl",
    "ops-index.jsonl",
    "propagation-errors.jsonl",
}


def _invocation_trail_files(repo_root: Path) -> list[Path]:
    invocations_dir = repo_root / EVENTS_DIR
    return sorted(
        path
        for path in invocations_dir.glob("*.jsonl")
        if path.name not in _NON_INVOCATION_OP_FILES
    )


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
    subprocess.run(
        ["git", "add", "README.md"], cwd=repo_root, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )


def _scaffold_documentation_feature(
    repo_root: Path,
    mission_slug: str,
    *,
    happy_path: bool = False,
) -> Path:
    """Create kitty-specs/<slug>/ with mission_type=documentation meta.

    When ``happy_path`` is True the helper also seeds every documentation
    gate artifact (spec.md, gap-analysis.md, plan.md, docs/index.md,
    audit-report.md, release.md) so the post-execution guard chain has no
    missing-artifact failure to surface.
    """
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "documentation"}),
        encoding="utf-8",
    )
    if happy_path:
        # Author every documentation gate artifact so the post-execution
        # guard chain has no missing-artifact failure to surface.
        (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
        (feature_dir / "gap-analysis.md").write_text(
            "# gap analysis", encoding="utf-8"
        )
        (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
        (feature_dir / "docs").mkdir()
        (feature_dir / "docs" / "index.md").write_text("# docs", encoding="utf-8")
        (feature_dir / "audit-report.md").write_text(
            "# audit report", encoding="utf-8"
        )
        (feature_dir / "release.md").write_text("# release", encoding="utf-8")
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
# Test 1 — fresh documentation mission starts without MissionRuntimeError
# ---------------------------------------------------------------------------


def test_get_or_start_run_succeeds_for_documentation(isolated_repo: Path) -> None:
    """FR-001 / SC-001: a fresh documentation mission starts without MissionRuntimeError.

    Mirrors the research-walk v1 P0 closure pattern: the runtime template
    chain MUST resolve a documentation template key, the run is created,
    state.json is bootstrapped, and the feature-runs index records the
    entry under the documentation mission key (not a software-dev fallback).
    """
    _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=True
    )

    run_ref = get_or_start_run("demo-docs-walk", isolated_repo, "documentation")

    # Run was created and persisted under .kittify/runtime/runs/.
    run_dir = Path(run_ref.run_dir)
    assert run_dir.is_dir(), f"run_dir not created: {run_dir}"
    assert (run_dir / "state.json").is_file(), (
        f"state.json missing — run never bootstrapped: {run_dir}"
    )

    # The run_ref must carry a documentation mission key (NOT a default fallback).
    assert run_ref.mission_key == "documentation", (
        f"Expected mission_key='documentation'; got {run_ref.mission_key!r}. "
        "If this is 'software-dev', the template resolver fell through to a "
        "wrong default and SC-007 has regressed."
    )

    # The feature-runs index records the entry under the documentation key.
    # WP05 / FR-016: keyed by mission_id, or ``legacy-<slug>`` for a mission
    # without one (this scaffold's meta.json); the bare slug is never a key.
    feature_runs = isolated_repo / ".kittify" / "runtime" / "feature-runs.json"
    assert feature_runs.is_file()
    index = json.loads(feature_runs.read_text(encoding="utf-8"))
    entry = index["legacy-demo-docs-walk"]
    assert entry["mission_type"] == "documentation"
    assert entry["mission_slug"] == "demo-docs-walk"


# ---------------------------------------------------------------------------
# Test 2 — runtime sidecar template resolves for the documentation mission
# ---------------------------------------------------------------------------


def test_documentation_template_resolves_runtime_sidecar() -> None:
    """SC-007: the loader resolves mission-runtime.yaml ahead of legacy mission.yaml.

    The runtime sidecar must be present under
    ``src/specify_cli/missions/documentation/`` and the bridge's resolver
    MUST prefer it over the legacy ``mission.yaml`` fallback. This is the
    structural prerequisite for the composed dispatch path.
    """
    package_root = (
        Path(__file__).resolve().parents[1].parent
        / "src"
        / "specify_cli"
        / "missions"
    )
    resolved = _resolve_runtime_template_in_root(package_root, "documentation")
    assert resolved is not None, (
        "Documentation runtime sidecar not resolved under "
        f"{package_root}; SC-007 is unmet."
    )
    assert resolved.name == "mission-runtime.yaml", (
        f"Resolver returned {resolved.name!r}; expected 'mission-runtime.yaml'."
    )


# ---------------------------------------------------------------------------
# Test 3 — composition path advances the run state for a documentation step
# ---------------------------------------------------------------------------


def test_composition_advances_one_documentation_step(isolated_repo: Path) -> None:
    """FR-002: composition advances the first documentation action via spec-kitty next.

    Observable proof (no patches on the C-007 forbidden list):

    * (a) Run state advances past the initial step — the engine snapshot's
      ``completed_steps`` moves from empty to containing the first
      documentation-native step ID.
    * (b) The ``Decision`` returned by ``decide_next_via_runtime`` carries
      a documentation-native mission and a documentation-native issued
      step ID — not a software-dev verb such as ``"plan"``.
    * (c) No legacy ``runtime_next_step`` was re-entered for the
      composed action — implicitly proven because the snapshot
      advanced exactly one step rather than two (a fall-through would
      double-advance).
    """
    _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=True
    )

    # First call issues the first step (no advance yet).
    first = decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )
    documentation_actions = {
        "discover",
        "audit",
        "design",
        "generate",
        "validate",
        "publish",
    }
    assert first.mission == "documentation", (
        f"Expected mission='documentation'; got {first.mission!r}."
    )
    assert first.step_id in documentation_actions, (
        f"Expected first step in {sorted(documentation_actions)}; "
        f"got {first.step_id!r}. A software-dev verb (e.g., 'specify' or "
        "'plan') means the planner is using software-dev defaults."
    )
    initial_step = first.step_id

    # Snapshot before the composition dispatch — completed_steps is empty.
    run_ref = get_or_start_run("demo-docs-walk", isolated_repo, "documentation")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    assert list(snapshot_before.completed_steps) == []
    assert snapshot_before.issued_step_id == initial_step

    # Drive the composition dispatch by reporting success on the issued step.
    decision = decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )

    # (a) The snapshot advanced — initial step is now in completed_steps.
    snapshot_after = _read_snapshot(Path(run_ref.run_dir))
    assert initial_step in snapshot_after.completed_steps, (
        f"{initial_step!r} not marked completed; completed_steps="
        f"{snapshot_after.completed_steps!r}"
    )

    # (b) Decision is documentation-native.
    assert decision.mission == "documentation", (
        f"Expected decision.mission='documentation'; got {decision.mission!r}."
    )
    decision_kind = (
        decision.kind.value
        if hasattr(decision.kind, "value")
        else str(decision.kind)
    )
    assert decision_kind in ("step", "blocked"), (
        f"Expected step or blocked decision; got {decision.kind!r}"
    )

    # The next issued step must also be a documentation-native action.
    next_step = snapshot_after.issued_step_id
    assert next_step in documentation_actions, (
        f"Expected next step in {sorted(documentation_actions)}; "
        f"got {next_step!r}. A value like 'plan' would mean the bridge fell "
        "back to software-dev planning."
    )


# ---------------------------------------------------------------------------
# Test 4 — paired invocation lifecycle records carry documentation action_hint
# ---------------------------------------------------------------------------


def test_paired_invocation_lifecycle_is_recorded(isolated_repo: Path) -> None:
    """FR-011 + FR-012 + NFR-006: invocation trail records paired started/done.

    The composition dispatch routes through ``ProfileInvocationExecutor``
    which writes JSONL records under the canonical Op storage directory.
    Each invocation must have a ``started`` line paired with a
    ``completed`` line whose outcome is ``done`` or ``failed``. The
    recorded ``action`` MUST stay within the documentation-native step
    IDs (no software-dev verbs leaking through).

    Reading the trail directly (not patching the writer) keeps this test
    out of the C-007 forbidden surface.
    """
    _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=True
    )

    # Issue the first step then dispatch composition for it.
    decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )
    decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )

    invocations_dir = isolated_repo / EVENTS_DIR
    assert invocations_dir.is_dir(), (
        f"Invocations dir missing: {invocations_dir}. Composition dispatch "
        "did not produce a paired invocation trail."
    )
    trail_files = _invocation_trail_files(isolated_repo)
    assert trail_files, (
        f"No invocation trail files written under {invocations_dir}. "
        "ProfileInvocationExecutor.invoke was not called from the composed "
        "documentation dispatch."
    )

    documentation_actions = {
        "discover",
        "audit",
        "design",
        "generate",
        "validate",
        "publish",
    }
    valid_outcomes = {"done", "failed"}
    saw_started = False
    saw_pair = False
    saw_doc_action = False
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
        assert first.get("event") == "started", (
            f"First record in {trail.name} is not a started event: {first!r}"
        )
        saw_started = True
        # The recorded action MUST be a documentation-native step ID — not a
        # software-dev verb. The action_hint flows from the contract.action
        # through the composed executor into the InvocationRecord, so this is
        # the structural assertion that the documentation dispatch wired the
        # right action.
        action = first.get("action")
        assert action in documentation_actions, (
            f"Recorded action {action!r} is not a documentation-native step "
            f"ID. Trail={trail.name}; record={first!r}"
        )
        saw_doc_action = True
        # FR-012: every started invocation MUST be paired with a completed
        # event whose outcome is 'done' or 'failed'. A trail that holds only a
        # started record indicates a torn lifecycle and would let FR-012
        # silently regress.
        completed = [e for e in events if e.get("event") == "completed"]
        assert completed, (
            f"Trail {trail.name} has a started record but no completed event; "
            "FR-012 requires paired lifecycle for every dispatched invocation."
        )
        outcome = completed[-1].get("outcome")
        assert outcome in valid_outcomes, (
            f"Completed event in {trail.name} has invalid outcome "
            f"{outcome!r}; FR-012 requires one of {sorted(valid_outcomes)}."
        )
        saw_pair = True
    assert saw_started, "No started records found across the invocation trail."
    assert saw_pair, (
        "No paired started+completed records found across the invocation "
        "trail."
    )
    assert saw_doc_action, (
        "No documentation-native action recorded across the invocation trail."
    )


# ---------------------------------------------------------------------------
# Test 5 — missing artifact blocks advancement at the DISPATCH layer (T11)
# ---------------------------------------------------------------------------


def test_missing_artifact_blocks_with_structured_failure(
    isolated_repo: Path,
) -> None:
    """FR-005 + SC-004 (F-4 closure): the missing-artifact assertion MUST observe
    a structured **blocked decision** through ``decide_next_via_runtime``
    rather than calling ``_check_composed_action_guard()`` directly.

    With ``happy_path=False`` the feature_dir holds only ``meta.json`` (no
    ``spec.md``). Driving the runtime through one issuance + one success
    record MUST produce:

    * a ``Decision`` whose ``kind`` is ``DecisionKind.blocked``,
    * ``guard_failures`` mentioning ``spec.md``, and
    * **no advancement** of the run-state snapshot (read before AND after
      the dispatch attempt; both are equal — empty ``completed_steps`` and
      ``issued_step_id`` unchanged at ``"discover"``).

    The legacy helper-level coverage (``_check_composed_action_guard``)
    survives in :func:`test_unknown_documentation_action_fails_closed`
    because the unknown-action fail-closed default cannot be exercised
    through ``decide_next_via_runtime`` (the bridge does not accept
    arbitrary action input). Per FR-006 / D6 of the fix-up plan, both
    levels of coverage are intentionally retained.
    """
    _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=False
    )

    # Issue the first step (discover) — no advance yet.
    decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )

    # Read the run snapshot BEFORE the dispatch attempt.
    run_ref = get_or_start_run("demo-docs-walk", isolated_repo, "documentation")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    assert list(snapshot_before.completed_steps) == [], (
        f"Pre-dispatch snapshot already advanced; completed_steps="
        f"{snapshot_before.completed_steps!r}"
    )
    assert snapshot_before.issued_step_id == "discover"

    # Drive composition dispatch — guard MUST fire post-execution because
    # spec.md is absent.
    decision = decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )

    # Surface 1: the Decision is blocked.
    decision_kind = (
        decision.kind.value
        if hasattr(decision.kind, "value")
        else str(decision.kind)
    )
    assert decision_kind == "blocked", (
        f"Expected blocked decision when spec.md is missing; got "
        f"{decision.kind!r}"
    )

    # Surface 2: guard_failures mention spec.md.
    assert decision.guard_failures, (
        f"Expected guard_failures populated; got {decision.guard_failures!r}"
    )
    assert any("spec.md" in failure for failure in decision.guard_failures), (
        f"spec.md not mentioned in guard_failures="
        f"{decision.guard_failures!r}. Structured failure surface "
        "regressed."
    )

    # Surface 3: state did NOT advance — snapshot before == snapshot after.
    snapshot_after = _read_snapshot(Path(run_ref.run_dir))
    assert list(snapshot_after.completed_steps) == [], (
        f"Run advanced despite guard failure; completed_steps="
        f"{snapshot_after.completed_steps!r}"
    )
    assert snapshot_after.issued_step_id == "discover", (
        f"issued_step_id moved off discover despite guard failure: "
        f"{snapshot_after.issued_step_id!r}"
    )
    assert (
        list(snapshot_after.completed_steps)
        == list(snapshot_before.completed_steps)
    ), (
        "Snapshot advanced through a blocked dispatch — completed_steps "
        f"changed from {snapshot_before.completed_steps!r} to "
        f"{snapshot_after.completed_steps!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 — unknown documentation action fails closed at the helper surface
# ---------------------------------------------------------------------------


def test_unknown_documentation_action_fails_closed(isolated_repo: Path) -> None:
    """FR-006 / D6: helper-level fail-closed default for unknown actions.

    This is intentionally a **helper-level** assertion (not a dispatch-level
    one). The bridge's ``decide_next_via_runtime`` does not accept an
    arbitrary action string — it always plans the next step from the run
    state — so the only way to exercise the
    ``"No guard registered for documentation action: <action>"`` default is
    by calling ``_check_composed_action_guard()`` directly. Per FR-006 of
    the fix-up plan, the dispatch-level guard coverage in
    :func:`test_missing_artifact_blocks_with_structured_failure` and this
    helper-level coverage are both required.

    The bridge's ``_check_composed_action_guard`` chain MUST emit
    ``"No guard registered for documentation action: ghost"`` for any
    unknown documentation action so the dispatch path cannot mistake an
    unhandled action for success.
    """
    feature_dir = _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=True
    )

    failures = _check_composed_action_guard(
        "ghost", feature_dir, mission="documentation"
    )
    assert failures == [
        "No guard registered for documentation action: ghost"
    ], (
        f"Fail-closed default did not fire for unknown documentation action; "
        f"got failures={failures!r}"
    )


# ---------------------------------------------------------------------------
# Test 7 — full advancement through all 6 documentation actions (T09 + T10)
# ---------------------------------------------------------------------------


# Documentation actions in DAG order with the gate artifact each one
# requires before the post-execution guard chain accepts advancement.
_DOCUMENTATION_WALK: tuple[tuple[str, str], ...] = (
    ("discover", "spec.md"),
    ("audit", "gap-analysis.md"),
    ("design", "plan.md"),
    ("generate", "docs/index.md"),
    ("validate", "audit-report.md"),
    ("publish", "release.md"),
)


def test_full_advancement_through_six_actions(isolated_repo: Path) -> None:
    """FR-003 + FR-004 + SC-003 (F-3 closure): the integration walk MUST drive
    every one of the 6 composed documentation actions through dispatch and
    record a paired ``started`` + ``done`` (or ``failed``) trail entry per
    advancing action.

    Each iteration:

    1. Authors the gate artifact for the current action under the feature
       directory (creating ``docs/`` for the ``generate`` step) so the
       post-execution guard chain has nothing to fail on.
    2. Calls ``decide_next_via_runtime(..., "success", ...)`` to drive the
       composition dispatch for the currently-issued step.
    3. Asserts the snapshot's ``completed_steps`` grew to include the
       expected action and that the dispatch returned a documentation-native
       ``Decision`` (mission == "documentation"; not blocked).

    After the loop finishes the test cross-checks the per-action paired
    invocation trail under
    the canonical Op storage directory (T10): every advancing
    action MUST have at least one trail file containing a paired
    ``started`` + ``completed`` record whose ``action`` is the
    documentation-native verb. This is a stricter assertion than the
    single-action :func:`test_paired_invocation_lifecycle_is_recorded`
    test — it asserts coverage across **all six** advancing actions.
    """
    feature_dir = _scaffold_documentation_feature(
        isolated_repo, "demo-docs-walk", happy_path=False
    )
    run_ref = get_or_start_run("demo-docs-walk", isolated_repo, "documentation")
    run_dir = Path(run_ref.run_dir)

    # Issue the first step (discover) — runtime is now waiting for a
    # success record on it.
    first = decide_next_via_runtime(
        "test-operator",
        "demo-docs-walk",
        "success",
        isolated_repo,
    )
    assert first.mission == "documentation", (
        f"Expected mission='documentation'; got {first.mission!r}."
    )
    assert first.step_id == "discover", (
        f"Expected first issued step 'discover'; got {first.step_id!r}."
    )

    advanced_actions: list[str] = []
    for action, artifact in _DOCUMENTATION_WALK:
        # Author the gate artifact for THIS action before reporting success.
        artifact_path = feature_dir / artifact
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"# {action}\n", encoding="utf-8")

        snapshot_before = _read_snapshot(run_dir)
        assert snapshot_before.issued_step_id == action, (
            f"Pre-advance snapshot issued_step_id="
            f"{snapshot_before.issued_step_id!r}; expected {action!r}."
        )

        # Report success on the currently-issued step. The bridge runs the
        # composed dispatch, applies the post-execution guard chain, and
        # advances the run state when the guard passes.
        decision = decide_next_via_runtime(
            "test-operator",
            "demo-docs-walk",
            "success",
            isolated_repo,
        )
        assert decision.mission == "documentation", (
            f"Decision for {action!r} carried wrong mission "
            f"{decision.mission!r}; expected 'documentation'."
        )
        decision_kind = (
            decision.kind.value
            if hasattr(decision.kind, "value")
            else str(decision.kind)
        )
        assert decision_kind != "blocked", (
            f"Action {action!r} produced a blocked decision despite the "
            f"gate artifact {artifact!r} being authored. "
            f"guard_failures={decision.guard_failures!r}"
        )

        snapshot_after = _read_snapshot(run_dir)
        assert action in snapshot_after.completed_steps, (
            f"{action!r} not added to completed_steps after dispatch; "
            f"completed_steps={snapshot_after.completed_steps!r}"
        )
        advanced_actions.append(action)

    # All six actions advanced through dispatch in DAG order.
    assert advanced_actions == [a for a, _ in _DOCUMENTATION_WALK], (
        f"Action advancement order regressed; got {advanced_actions!r}."
    )

    # T10: every advancing action MUST have a paired started/completed
    # trail record under the canonical Op storage directory with the
    # documentation-native action name on the started event.
    invocations_dir = isolated_repo / EVENTS_DIR
    assert invocations_dir.is_dir(), (
        f"Invocations dir missing: {invocations_dir}. Composition dispatch "
        "did not produce any paired invocation trails."
    )

    valid_outcomes = {"done", "failed"}
    paired_actions: set[str] = set()
    for trail in _invocation_trail_files(isolated_repo):
        events: list[dict[str, object]] = []
        for raw in trail.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            continue
        first_event = events[0]
        if first_event.get("event") != "started":
            continue
        action_name = first_event.get("action")
        if not isinstance(action_name, str):
            continue
        completed = [e for e in events if e.get("event") == "completed"]
        if not completed:
            continue
        outcome = completed[-1].get("outcome")
        if outcome not in valid_outcomes:
            continue
        paired_actions.add(action_name)

    expected_actions = {a for a, _ in _DOCUMENTATION_WALK}
    missing = expected_actions - paired_actions
    assert not missing, (
        f"Missing paired started+completed trail records for documentation "
        f"actions {sorted(missing)!r}. Recorded paired actions: "
        f"{sorted(paired_actions)!r}. Expected at least: "
        f"{sorted(expected_actions)!r}."
    )
