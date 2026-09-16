"""Integration tests for runtime-bridge composition dispatch (WP02).

Mission: ``software-dev-composition-rewrite-01KQ26CY``.

These tests lock in the bridge ↔ ``StepContractExecutor`` handoff:

* The dispatch branch fires only for ``mission == "software-dev"`` AND a
  composed action ID (``specify``, ``plan``, ``tasks``, ``implement``,
  ``review``).
* The legacy ``tasks_outline`` / ``tasks_packages`` / ``tasks_finalize`` step
  IDs collapse to a single composed ``tasks`` action.
* Any other mission or step ID falls through to the legacy DAG handler
  unchanged (constraint C-008).
* ``StepContractExecutionError`` surfaces as a structured CLI failure
  (``Decision`` with ``kind=blocked`` and populated ``guard_failures``) — not
  a Python traceback (FR-009).
* The collapsed ``tasks`` post-action guard asserts the union of the three
  legacy ``tasks_*`` checks (no weakening of validation).
* The ``specify`` and ``plan`` post-action guards behave like their legacy
  counterparts.

The tests mock ``StepContractExecutor.execute`` rather than instantiating it,
so no real DRG is required.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
    StepContractExecutionError,
)
from runtime.next import runtime_bridge as rb
from runtime.next._internal_runtime import MissionRunRef
from runtime.next.runtime_bridge import (
    _check_composed_action_guard,
    _dispatch_via_composition,
    _normalize_action_for_composition,
    _should_dispatch_via_composition,
)


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _local_only_sync_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Composition dispatch tests are local runtime tests, not SaaS sync tests."""
    from runtime.next import runtime_bridge
    from runtime.next._internal_runtime.events import NullEmitter

    monkeypatch.setattr(runtime_bridge, "runtime_emitter_for_mission", lambda **_: NullEmitter())


_KNOWN_ACTION_SEQUENCES: dict[str, list[str]] = {
    "software-dev": ["specify", "plan", "tasks", "implement", "review"],
    "documentation": ["discover", "audit", "design", "generate", "validate", "publish", "accept"],
    "research": ["scoping", "methodology", "gathering", "synthesis", "output"],
    "plan": [],
}


def _mock_resolve_mission_type_context(
    repo_root: object, *, mission_type: str | None = None, feature_dir: object = None
) -> SimpleNamespace:
    """Return the built-in action sequence for the given mission type.

    Used as an autouse fixture patch so integration tests don't need a live
    MissionTypeRepository (which is provided by a later WP).
    """
    from charter.activation.mission_type_profiles import UnknownMissionTypeError

    result = _KNOWN_ACTION_SEQUENCES.get(mission_type)
    if result is None:
        raise UnknownMissionTypeError(mission_type)
    return SimpleNamespace(action_sequence=result)


@pytest.fixture(autouse=True)
def _mock_charter_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch charter.resolve_mission_type_context so tests run without MissionTypeRepository.

    After WP07, _should_dispatch_via_composition and _composition_dispatch_inputs
    call charter.resolve_mission_type_context.  The MissionTypeRepository is provided
    by a later WP; this autouse fixture patches the call for all tests in this
    module so they remain self-contained.
    """
    import charter.activation.mission_type_profiles as _cmt

    monkeypatch.setattr(
        _cmt,
        "resolve_mission_type_context",
        _mock_resolve_mission_type_context,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DEFAULT_SPEC_MD = (
    "# Spec\n\n"
    "## Functional Requirements\n\n"
    "| ID | Requirement | Acceptance Criteria | Status |\n"
    "| --- | --- | --- | --- |\n"
    "| FR-001 | First | Covered by WP01. | proposed |\n"
)


def _write_wp_file(
    tasks_dir: Path,
    wp_id: str,
    *,
    with_dependencies: bool = True,
    requirement_refs: list[str] | None = ("FR-001",),
) -> Path:
    """Write a minimal WP*.md file with optional 'dependencies:' frontmatter."""
    wp_file = tasks_dir / f"{wp_id}-test.md"
    deps_line = "dependencies: []\n" if with_dependencies else ""
    refs_line = ""
    if requirement_refs:
        refs_line = f"requirement_refs: [{', '.join(requirement_refs)}]\n"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test\n{deps_line}{refs_line}---\nbody\n",
        encoding="utf-8",
    )
    return wp_file


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    """Bare feature dir (no spec.md / plan.md / tasks.md / WP files)."""
    fd = tmp_path / "kitty-specs" / "test-feature"
    fd.mkdir(parents=True)
    return fd


@pytest.fixture()
def feature_dir_with_full_tasks(tmp_path: Path) -> Path:
    """Feature dir with spec.md, plan.md, tasks.md, and one valid WP*.md."""
    fd = tmp_path / "kitty-specs" / "test-feature"
    fd.mkdir(parents=True)
    (fd / "spec.md").write_text(_DEFAULT_SPEC_MD, encoding="utf-8")
    (fd / "plan.md").write_text("# plan", encoding="utf-8")
    (fd / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks = fd / "tasks"
    tasks.mkdir()
    _write_wp_file(tasks, "WP01")
    return fd


# ---------------------------------------------------------------------------
# Helper-function unit tests (cheap, no executor)
# ---------------------------------------------------------------------------


def test_should_dispatch_fires_for_software_dev_composed_actions(
    tmp_path: Path,
) -> None:
    """All five composed actions on software-dev route through composition.

    After WP07, dispatch is driven by charter.resolve_mission_type_context, not a
    static frozenset.  The MissionTypeRepository is mocked so the test stays
    self-contained.
    """
    from unittest.mock import patch

    sw_actions = ["specify", "plan", "tasks", "implement", "review"]
    with patch(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        return_value=SimpleNamespace(action_sequence=sw_actions),
    ):
        for action in sw_actions:
            assert _should_dispatch_via_composition(
                "software-dev", action, repo_root=tmp_path
            ) is True


def test_should_dispatch_falls_through_for_unknown_mission_helper(
    tmp_path: Path,
) -> None:
    """Any mission type unknown to charter falls through (C-008)."""
    from charter.activation.mission_type_profiles import UnknownMissionTypeError
    from unittest.mock import patch

    with patch(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        side_effect=UnknownMissionTypeError("documentation"),
    ):
        for action in ("specify", "plan", "tasks", "implement", "review"):
            assert (
                _should_dispatch_via_composition(
                    "documentation", action, repo_root=tmp_path
                )
                is False
            )

    with patch(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        side_effect=UnknownMissionTypeError("other"),
    ):
        for action in ("specify", "plan", "tasks", "implement", "review"):
            assert (
                _should_dispatch_via_composition("other", action, repo_root=tmp_path)
                is False
            )


def test_should_dispatch_falls_through_for_unknown_step_id_helper(
    tmp_path: Path,
) -> None:
    """Step IDs outside the composed set fall through (e.g. ``accept``)."""
    from unittest.mock import patch

    sw_actions = ["specify", "plan", "tasks", "implement", "review"]
    with patch(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        return_value=SimpleNamespace(action_sequence=sw_actions),
    ):
        for step_id in ("accept", "merge", "bootstrap", "unknown_step"):
            assert (
                _should_dispatch_via_composition(
                    "software-dev", step_id, repo_root=tmp_path
                )
                is False
            )


def test_normalize_collapses_legacy_tasks_step_ids() -> None:
    """All three legacy tasks_* IDs collapse to the composed ``tasks`` action."""
    assert _normalize_action_for_composition("tasks_outline") == "tasks"
    assert _normalize_action_for_composition("tasks_packages") == "tasks"
    assert _normalize_action_for_composition("tasks_finalize") == "tasks"
    # Composed actions and other step IDs pass through unchanged.
    for step_id in ("specify", "plan", "tasks", "implement", "review", "accept"):
        assert _normalize_action_for_composition(step_id) == step_id


# ---------------------------------------------------------------------------
# Test #1 — Composition fires for software-dev specify
# ---------------------------------------------------------------------------


def test_dispatch_via_composition_fires_for_software_dev_specify(feature_dir_with_full_tasks: Path, tmp_path: Path) -> None:
    """``software-dev/specify`` routes through ``StepContractExecutor.execute``.

    Verifies (a) the executor is called exactly once with a context whose
    mission/action match, and (b) the legacy DAG handler is NOT entered for
    this dispatch decision.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    fake_result = MagicMock()
    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        return_value=fake_result,
    ) as mock_execute:
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="specify",
            actor="researcher-robbie",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir_with_full_tasks,
        )

    assert mock_execute.call_count == 1
    # Inspect the StepContractExecutionContext that was passed in.
    (call_args, call_kwargs) = mock_execute.call_args
    # execute(context) — single positional context argument.
    context = call_args[0] if call_args else call_kwargs.get("context")
    assert isinstance(context, StepContractExecutionContext)
    assert context.mission == "software-dev"
    assert context.action == "specify"
    assert context.actor == "researcher-robbie"
    # Composition succeeded AND post-action guard passed → returns None.
    assert failures is None


# ---------------------------------------------------------------------------
# Test #2 — Composition fires for collapsed tasks (each legacy step ID)
# ---------------------------------------------------------------------------


def test_dispatch_via_composition_fires_for_collapsed_tasks(feature_dir_with_full_tasks: Path, tmp_path: Path) -> None:
    """Each legacy ``tasks_*`` step ID routes to a single composed ``tasks``.

    The bridge first normalizes the step_id; then dispatches one composition
    call per invocation (no triplication).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    for legacy_step_id in ("tasks_outline", "tasks_packages", "tasks_finalize"):
        # Normalization must collapse the legacy ID to "tasks".
        normalized = _normalize_action_for_composition(legacy_step_id)
        assert normalized == "tasks"
        # And a single composition dispatch must produce a single
        # executor call for the composed "tasks" action.
        with patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=MagicMock(),
        ) as mock_execute:
            failures = _dispatch_via_composition(
                repo_root=repo_root,
                mission="software-dev",
                action=normalized,
                actor="architect-alphonso",
                profile_hint=None,
                request_text=None,
                mode_of_work=None,
                feature_dir=feature_dir_with_full_tasks,
            )
        assert mock_execute.call_count == 1, f"Expected one composition call for {legacy_step_id}; got {mock_execute.call_count}"
        context = mock_execute.call_args[0][0]
        assert context.action == "tasks"
        assert failures is None


# ---------------------------------------------------------------------------
# Test #3 — Fall-through for unknown mission
# ---------------------------------------------------------------------------


def test_dispatch_falls_through_for_unknown_mission(tmp_path: Path) -> None:
    """For any non-software-dev mission, composition MUST NOT be entered.

    We assert the routing predicate returns False — the bridge's caller
    only invokes composition when the predicate fires, so a False result
    proves the legacy DAG handler is the only dispatch path.

    After WP07, the predicate calls charter.resolve_mission_type_context; missions
    unknown to charter raise UnknownMissionTypeError and the predicate degrades
    to False gracefully.
    """
    from charter.activation.mission_type_profiles import UnknownMissionTypeError

    # Pre-condition: the executor is never called when the predicate is False.
    def _raise_unknown(
        repo_root: object, *, mission_type: str | None = None, feature_dir: object = None
    ) -> SimpleNamespace:
        raise UnknownMissionTypeError(mission_type)

    with (
        patch("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute") as mock_execute,
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            side_effect=_raise_unknown,
        ),
    ):
        for mission in ("other-mission", "documentation", "architecture"):
            for step_id in ("specify", "plan", "tasks", "implement", "review"):
                assert _should_dispatch_via_composition(mission, step_id, repo_root=tmp_path) is False
        # Predicate never matched → the bridge would never call _dispatch.
        mock_execute.assert_not_called()


# ---------------------------------------------------------------------------
# Test #4 — Fall-through for unknown step ID inside software-dev
# ---------------------------------------------------------------------------


def test_dispatch_falls_through_for_unknown_step_id(tmp_path: Path) -> None:
    """``software-dev`` step IDs outside the composed set fall through.

    Examples: ``accept``, ``merge``, ``bootstrap`` — these are legitimate
    runtime DAG steps but are not part of the composition layer in this
    slice. The predicate must return False so the bridge keeps using the
    legacy DAG handler for them.

    After WP07, the predicate uses charter.resolve_mission_type_context so a
    repo_root must be provided; the charter call is mocked to return only the
    five composed actions.
    """
    sw_actions = ["specify", "plan", "tasks", "implement", "review"]
    with patch(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        return_value=SimpleNamespace(action_sequence=sw_actions),
    ):
        for step_id in ("accept", "merge", "bootstrap", "unknown_step"):
            assert _should_dispatch_via_composition("software-dev", step_id, repo_root=tmp_path) is False


# ---------------------------------------------------------------------------
# Test #5 — StepContractExecutionError → structured CLI error (FR-009)
# ---------------------------------------------------------------------------


def test_missing_contract_surfaces_structured_cli_error(feature_dir_with_full_tasks: Path, tmp_path: Path) -> None:
    """A raised ``StepContractExecutionError`` becomes a structured failure.

    No Python traceback escapes; the bridge gets a non-empty failure list
    that it can wrap in a ``Decision(kind=blocked, guard_failures=[...])``
    response — same UX as the legacy guard-failure surface.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    err_message = "No step contract found for mission/action software-dev/specify"
    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        side_effect=StepContractExecutionError(err_message),
    ) as mock_execute:
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="specify",
            actor="researcher-robbie",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir_with_full_tasks,
        )

    assert mock_execute.call_count == 1
    assert failures is not None
    assert len(failures) == 1
    # The CLI-surface message preserves the executor's error text and tags
    # the mission/action so operators can correlate.
    assert "software-dev/specify" in failures[0]
    assert err_message in failures[0]
    # Must NOT be a Python repr — confirms structured surfacing rather than
    # ``repr(exception)`` style which would leak the class name in brackets.
    assert "Traceback" not in failures[0]


# ---------------------------------------------------------------------------
# Test #6 — Collapsed tasks guard requires tasks.md
# ---------------------------------------------------------------------------


def test_tasks_guard_requires_tasks_md(tmp_path: Path) -> None:
    """Composed ``tasks`` guard fails when tasks.md is absent.

    Mirrors the legacy ``tasks_outline`` negative case under the collapsed
    guard.
    """
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    # Intentionally do NOT create tasks.md.
    failures = _check_composed_action_guard("tasks", fd)
    assert any("tasks.md" in f for f in failures), f"Expected a failure mentioning tasks.md; got {failures!r}"


# ---------------------------------------------------------------------------
# Test #7 — Collapsed tasks guard requires at least one WP*.md file
# ---------------------------------------------------------------------------


def test_tasks_guard_requires_wp_files(tmp_path: Path) -> None:
    """Composed ``tasks`` guard fails when tasks/ exists but has no WP*.md.

    Mirrors the legacy ``tasks_packages`` negative case.
    """
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    (fd / "tasks.md").write_text("# tasks", encoding="utf-8")
    (fd / "tasks").mkdir()
    failures = _check_composed_action_guard("tasks", fd)
    assert any("WP*.md" in f for f in failures), f"Expected a failure mentioning WP*.md; got {failures!r}"


# ---------------------------------------------------------------------------
# Test #8 — Collapsed tasks guard requires raw 'dependencies:' frontmatter
# ---------------------------------------------------------------------------


def test_tasks_guard_requires_dependencies_frontmatter(tmp_path: Path) -> None:
    """Composed ``tasks`` guard fails when WP*.md lacks raw dependencies.

    Mirrors the legacy ``tasks_finalize`` negative case (the one that asserts
    every WP*.md has a 'dependencies:' field in raw frontmatter, indicating
    that 'spec-kitty agent mission finalize-tasks' has run).
    """
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    (fd / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks = fd / "tasks"
    tasks.mkdir()
    # WP file without 'dependencies:' frontmatter.
    _write_wp_file(tasks, "WP01", with_dependencies=False)
    failures = _check_composed_action_guard("tasks", fd)
    assert any("dependencies" in f for f in failures), f"Expected a failure mentioning dependencies; got {failures!r}"
    # The remediation hint should also surface the finalize-tasks command.
    assert any("finalize-tasks" in f for f in failures)


# ---------------------------------------------------------------------------
# #3396 (WP05) — composed-dispatch teeth tests: the bare-prose requirement
# signal reaches the composed ``tasks`` guard at both the packages and
# terminal/finalize boundaries, through this module's own
# ``_check_composed_action_guard`` integration entry point (not only the
# pure ``evaluate_guards`` core — see tests/runtime/test_bridge_cores.py).
# ---------------------------------------------------------------------------

_BARE_PROSE_REPRO_SPEC = (
    "# Spec\n\n"
    "## Functional Requirements\n\n"
    "FR-001 the loader must reject bad input. FR-002 the error must name "
    "the offending path.\n\n"
    "| ID | Requirement | Acceptance Criteria | Status |\n"
    "| --- | --- | --- | --- |\n"
    "| NFR-001 | Perf | Some criteria. | proposed |\n"
)


def test_composed_tasks_packages_guard_blocks_bare_prose_requirements_zero_wp_files(tmp_path: Path) -> None:
    """Zero WP files (the guard would otherwise only report the generic
    'materialize WP packages first' message) -- the bare-prose failure must
    still surface, naming FR-001/FR-002."""
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    (fd / "spec.md").write_text(_BARE_PROSE_REPRO_SPEC, encoding="utf-8")
    (fd / "tasks.md").write_text("# tasks", encoding="utf-8")
    (fd / "tasks").mkdir()

    failures = _check_composed_action_guard("tasks", fd, legacy_step_id="tasks_packages")
    assert any("FR-001" in f and "FR-002" in f for f in failures), failures
    assert any("WP*.md" in f for f in failures), failures


def test_composed_tasks_finalize_guard_blocks_bare_prose_requirements_with_unrelated_wp_files(
    tmp_path: Path,
) -> None:
    """>=1 WP file exists, referencing only the correctly-declared NFR-001 --
    the pre-existing requirement-mapping check is clean here by construction
    (no FR is declared in a recognized shape), so a message naming
    FR-001/FR-002 proves the new signal, not the pre-existing check."""
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    (fd / "spec.md").write_text(_BARE_PROSE_REPRO_SPEC, encoding="utf-8")
    (fd / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks = fd / "tasks"
    tasks.mkdir()
    _write_wp_file(tasks, "WP01", requirement_refs=["NFR-001"])

    failures = _check_composed_action_guard("tasks", fd, legacy_step_id="tasks_finalize")
    assert any("FR-001" in f and "FR-002" in f for f in failures), failures


# ---------------------------------------------------------------------------
# Test #9 — Specify guard requires spec.md
# ---------------------------------------------------------------------------


def test_specify_guard_requires_spec_md(tmp_path: Path) -> None:
    """Composed ``specify`` guard fails when spec.md is absent.

    Parity with legacy ``_check_cli_guards("specify", ...)``.
    """
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    failures = _check_composed_action_guard("specify", fd)
    assert any("spec.md" in f for f in failures), f"Expected a failure mentioning spec.md; got {failures!r}"


# ---------------------------------------------------------------------------
# Test #10 — Plan guard requires plan.md
# ---------------------------------------------------------------------------


def test_plan_guard_requires_plan_md(tmp_path: Path) -> None:
    """Composed ``plan`` guard fails when plan.md is absent.

    Parity with legacy ``_check_cli_guards("plan", ...)``.
    """
    fd = tmp_path / "kitty-specs" / "feat"
    fd.mkdir(parents=True)
    failures = _check_composed_action_guard("plan", fd)
    assert any("plan.md" in f for f in failures), f"Expected a failure mentioning plan.md; got {failures!r}"


# ---------------------------------------------------------------------------
# Mission-review follow-up tests (post-merge fixes for findings R-2 and R-3)
# ---------------------------------------------------------------------------


def test_dispatch_logs_invocation_chain_on_success(
    feature_dir_with_full_tasks: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-008: the bridge forwards the executor's invocation_id chain to logs.

    Mission-review finding R-2: prior to this test, ``_dispatch_via_composition``
    captured no return value from ``StepContractExecutor.execute``, so the
    ``StepContractExecutionResult.invocation_ids`` chain was discarded on the
    live path. This test pins the new behavior: composition success emits an
    INFO log line that includes the mission, action, count, and the
    invocation_ids tuple so downstream operators / event-trail consumers can
    correlate the composed action with its underlying ProfileInvocationExecutor
    calls.
    """
    import logging

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001", "inv-002", "inv-003", "inv-004")

    with (
        caplog.at_level(logging.INFO, logger="runtime.next.runtime_bridge"),
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ),
    ):
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="tasks",
            actor="architect-alphonso",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir_with_full_tasks,
        )

    assert failures is None
    # The chain must reach the bridge log so it can be consumed by event/trail
    # writers and operator triage tools.
    composition_logs = [r for r in caplog.records if "composed software-dev/tasks emitted" in r.message]
    assert composition_logs, f"Expected a composition INFO log forwarding the invocation chain; got {[r.message for r in caplog.records]!r}"
    log_msg = composition_logs[0].getMessage()
    assert "4 invocation(s)" in log_msg
    assert "inv-001" in log_msg


def test_dispatch_handles_non_sized_invocation_ids_and_returns_guard_failures(
    feature_dir: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Guard failures still surface when executor metadata is non-sized."""
    import logging

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    fake_result = MagicMock()
    fake_result.invocation_ids = object()

    with (
        caplog.at_level(logging.INFO, logger="runtime.next.runtime_bridge"),
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ),
    ):
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="tasks",
            actor="architect-alphonso",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir,
        )

    assert failures is not None
    assert any("tasks.md" in failure for failure in failures)
    log_messages = [record.getMessage() for record in caplog.records]
    assert any("emitted 0 invocation(s)" in message for message in log_messages)


def test_unexpected_exception_surfaces_structured_cli_error(feature_dir_with_full_tasks: Path, tmp_path: Path) -> None:
    """FR-009: any executor exception class becomes a structured CLI failure.

    Mission-review finding R-3: prior to this test, only
    ``StepContractExecutionError`` was caught; a ``ValueError`` (or any other
    exception class) raised by the executor would escape as a Python traceback,
    contradicting FR-009's "structured CLI error, NOT crash" mandate. This
    test pins the widened catch: an unexpected exception class becomes a
    well-formed failure list the caller can wrap in a
    ``Decision(kind=blocked, guard_failures=[...])``.

    The assertion text checks for the ``crashed`` keyword (vs. the expected
    ``failed`` from the narrow catch) so the two failure modes remain
    distinguishable in operator-facing surfaces.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    err_message = "transient error reading contract from disk"
    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        side_effect=ValueError(err_message),
    ) as mock_execute:
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="implement",
            actor="implementer-ivan",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir_with_full_tasks,
        )

    assert mock_execute.call_count == 1
    assert failures is not None
    assert len(failures) == 1
    surface = failures[0]
    # Distinguishes "unexpected" path from the narrow StepContractExecutionError
    # path which uses "failed".
    assert "crashed" in surface
    assert "software-dev/implement" in surface
    # Exception class is named so operators can triage by type.
    assert "ValueError" in surface
    assert err_message in surface
    # Must NOT be a Python repr / traceback — confirms structured surfacing.
    assert "Traceback" not in surface


# ---------------------------------------------------------------------------
# Hotfix tests for collapsed-tasks-guard regression (P0)
# ---------------------------------------------------------------------------
#
# Reviewer-reproduced bug: the legacy DAG fires the bridge once per substep
# (``tasks_outline`` → ``tasks_packages`` → ``tasks_finalize``), and the
# collapsed guard demanded the post-finalize terminal state on every call.
# That broke the live tasks_* flow because the user can only have produced
# the post-outline artifacts after the first call. Fix: the guard branches
# on ``legacy_step_id`` so it asks for only what the user is expected to
# have produced at that substep.


def test_collapsed_tasks_guard_passes_after_outline_with_only_tasks_md(
    feature_dir: Path,
) -> None:
    """tasks_outline guard requires only tasks.md, not WP files yet.

    Reproduces the reviewer-reported live-flow blocker: with only spec.md +
    plan.md + tasks.md (no WP files yet), the collapsed-on-tasks_outline
    guard previously returned a "Required: at least one tasks/WP*.md file"
    failure, blocking the user from progressing to tasks_packages.
    """
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_outline")
    assert failures == [], f"tasks_outline must accept only tasks.md being present at this point; got blocking failures {failures!r}"


def test_collapsed_tasks_guard_fails_after_outline_when_tasks_md_missing(
    feature_dir: Path,
) -> None:
    """tasks_outline guard still fails when tasks.md is absent."""
    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_outline")
    assert any("tasks.md" in f for f in failures), f"Expected tasks.md missing failure; got {failures!r}"


def test_collapsed_tasks_guard_passes_after_packages_without_dependencies(
    feature_dir: Path,
) -> None:
    """tasks_packages guard accepts WP files without dependencies frontmatter.

    Reproduces the second flavor of the reviewer-reported blocker: with WP
    files present but no ``dependencies:`` frontmatter (because finalize
    hasn't run yet), the collapsed-on-tasks_packages guard previously
    returned a "missing 'dependencies' in frontmatter — run finalize-tasks"
    failure that pushed the user back to a step that wouldn't help.
    """
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_file(tasks_dir, "WP01", with_dependencies=False)
    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_packages")
    assert failures == [], f"tasks_packages must accept WP files without dependencies (finalize-tasks adds them next); got {failures!r}"


def test_collapsed_tasks_guard_fails_after_packages_when_no_wp_files(
    feature_dir: Path,
) -> None:
    """tasks_packages guard requires at least one WP*.md file."""
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_packages")
    assert any("WP*.md" in f for f in failures), f"Expected WP*.md missing failure; got {failures!r}"


def test_collapsed_tasks_guard_fails_after_packages_when_tasks_md_missing(
    feature_dir: Path,
) -> None:
    """tasks_packages guard still requires the top-level tasks.md artifact."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_file(tasks_dir, "WP01", with_dependencies=False)

    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_packages")
    assert any("tasks.md" in f for f in failures), f"tasks_packages must require tasks.md; got {failures!r}"


def test_collapsed_tasks_guard_demands_dependencies_on_finalize(
    feature_dir: Path,
) -> None:
    """tasks_finalize guard demands the full terminal state including deps."""
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_file(tasks_dir, "WP01", with_dependencies=False)
    failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_finalize")
    assert any("dependencies" in f for f in failures), f"Expected dependencies-missing failure on finalize; got {failures!r}"


def test_collapsed_tasks_guard_terminal_when_no_legacy_step_id(
    feature_dir_with_full_tasks: Path,
) -> None:
    """Composition-only invocation (no legacy_step_id) demands terminal state.

    Backward-compat with the original collapsed guard semantics: when
    something invokes the composed ``tasks`` action directly (not via a
    legacy DAG substep), the user has implicitly committed to producing the
    full post-finalize state in one shot, so the guard demands all three
    legacy checks pass.
    """
    failures = _check_composed_action_guard("tasks", feature_dir_with_full_tasks)
    assert failures == [], f"Composition-only tasks call against a fully-finalized feature dir must pass; got {failures!r}"

    # And conversely: terminal-state demand still fails when WP deps missing.
    bare = feature_dir_with_full_tasks.parent / "bare"
    bare.mkdir()
    (bare / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks_dir = bare / "tasks"
    tasks_dir.mkdir()
    _write_wp_file(tasks_dir, "WP02", with_dependencies=False)
    failures2 = _check_composed_action_guard("tasks", bare)
    assert any("dependencies" in f for f in failures2), f"Composition-only call without deps must surface dependencies failure; got {failures2!r}"


def test_dispatch_threads_legacy_step_id_to_guard(feature_dir: Path, tmp_path: Path) -> None:
    """End-to-end: bridge passes legacy_step_id through to the guard.

    Reproduces the reviewer's decide_next() walk in a tighter form: after a
    successful executor call (mocked) for a tasks_outline substep, the
    bridge's guard check accepts only-tasks_md state instead of demanding
    WP files. Without legacy_step_id threading, this would block.
    """
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)
    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        return_value=fake_result,
    ):
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="software-dev",
            action="tasks",
            actor="architect-alphonso",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir,
            legacy_step_id="tasks_outline",
        )
    assert failures is None, f"tasks_outline through dispatch must not block on missing WP files; got {failures!r}"


# ---------------------------------------------------------------------------
# WP01 / Issue #786 — Single-dispatch invariant tests
# ---------------------------------------------------------------------------
#
# These tests pin the FR-001 / FR-002 / FR-005 / FR-015 contract for the
# composition-backed software-dev path:
#
#   1. After a successful composition, ``runtime_next_step`` (the legacy DAG
#      dispatch handler) MUST NOT be called for the same action attempt.
#   2. Run-state advancement still happens — via
#      ``_advance_run_state_after_composition``.
#   3. ``Decision`` shape is unchanged.
#   4. Non-composed actions still flow through ``runtime_next_step``.
#   5. If the advancement helper raises, the error surfaces via the existing
#      ``Decision`` blocked shape, and ``runtime_next_step`` is **not**
#      entered as a silent fallback (EDGE-003).


import json
import subprocess

from runtime.next.decision import Decision, DecisionKind


def _init_git_repo_for_run(path: Path) -> None:
    """Initialize a minimal git repo so ``decide_next_via_runtime`` can resolve."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_software_dev_project(tmp_path: Path) -> tuple[Path, Path, str]:
    """Scaffold a minimal software-dev project with a feature dir.

    Returns ``(repo_root, feature_dir, mission_slug)``.
    """
    mission_slug = "042-test-feature"
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo_for_run(repo_root)

    (repo_root / ".kittify").mkdir()

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "software-dev"}),
        encoding="utf-8",
    )
    return repo_root, feature_dir, mission_slug


def _advance_runtime_to_step(repo_root: Path, mission_slug: str, target_step: str) -> None:
    """Drive the runtime engine until ``issued_step_id == target_step``."""
    from runtime.next._internal_runtime.engine import (
        _read_snapshot,
        next_step as engine_next_step,
    )
    from runtime.next._internal_runtime.events import NullEmitter
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    for _ in range(20):
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step:
            return
        engine_next_step(run_ref, agent_id="test", result="success", emitter=NullEmitter())
    raise RuntimeError(f"Could not drive runtime to step {target_step!r}; current snapshot ={_read_snapshot(Path(run_ref.run_dir))!r}")


def _seed_wp_event_for_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a single status event so ``get_wp_lane`` returns ``lane`` for ``wp_id``."""
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

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


@pytest.fixture()
def composed_software_dev_project(tmp_path: Path):
    """Scaffold a software-dev project with all composed-action artifacts present.

    Yields ``(repo_root, feature_dir, mission_slug)``. Ready for tests that
    reach the composition path of ``decide_next_via_runtime``. WP01 is seeded
    in the ``done`` lane so the bridge's WP-iteration short-circuit advances
    past ``implement`` / ``review`` and the composition path is reached.
    """
    repo_root, feature_dir, mission_slug = _scaffold_software_dev_project(tmp_path)
    # Lay down the artifacts every composed action's guard wants present so a
    # success path actually reaches the advancement helper.
    (feature_dir / "spec.md").write_text(_DEFAULT_SPEC_MD, encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks = feature_dir / "tasks"
    tasks.mkdir()
    _write_wp_file(tasks, "WP01")
    # Seed WP01 into the ``done`` lane so the WP-iteration check
    # (_should_advance_wp_step) does NOT short-circuit before we reach the
    # composition dispatch path for the implement / review actions.
    _seed_wp_event_for_lane(feature_dir, "WP01", "done")
    yield repo_root, feature_dir, mission_slug


_COMPOSED_SOFTWARE_DEV_ACTIONS = ("specify", "plan", "tasks", "implement", "review")


@pytest.mark.parametrize("step_id", _COMPOSED_SOFTWARE_DEV_ACTIONS)
def test_composition_success_skips_legacy_dispatch(composed_software_dev_project, step_id: str) -> None:
    """FR-001 / FR-015: ``runtime_next_step`` is NOT called after composition.

    Parametrized over the five composed software-dev actions. We patch the
    legacy DAG dispatch entry point as imported into the bridge module
    (``runtime.next.runtime_bridge.runtime_next_step``) and assert it is
    not entered when the composition path succeeds.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, step_id)

    from runtime.next.runtime_bridge import decide_next_via_runtime

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)
    sentinel_decision = Decision(
        # WP02 / #844: kind=step now requires a non-null, on-disk-resolvable
        # prompt_file. This sentinel is only used as the return value of a
        # patched ``_advance_run_state_after_composition`` and the test does
        # not assert on its ``kind`` — switch to ``terminal`` so the
        # construction-time validator is not tripped.
        kind=DecisionKind.terminal,
        agent="test",
        mission_slug=mission_slug,
        mission="software-dev",
        mission_state="next",
        timestamp="2026-04-25T00:00:00+00:00",
        action="next",
        run_id="run-x",
        step_id="next",
    )
    with (
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ),
        patch(
            "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
            return_value=sentinel_decision,
        ) as mock_advance,
        patch(
            "runtime.next.runtime_bridge.runtime_next_step",
        ) as mock_legacy,
    ):
        decision = decide_next_via_runtime("test", mission_slug, "success", repo_root)

    # The legacy DAG dispatch handler MUST NOT be called after composition
    # success — that is the single-dispatch invariant (FR-001).
    mock_legacy.assert_not_called()
    # And the advancement helper is the one that runs.
    assert mock_advance.call_count == 1
    # The Decision returned is the one produced by the helper.
    assert decision is sentinel_decision


def test_composition_success_advances_run_state_and_lane_events(
    composed_software_dev_project,
) -> None:
    """FR-002: composition success advances run state and emits lane events.

    The advancement helper is responsible for the legacy path's progression
    primitives. After a successful composition for ``specify``, the run
    snapshot's ``issued_step_id`` must move forward, and the runtime event log
    must record a ``NextStepAutoCompleted`` for the just-completed step.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next.runtime_bridge import (
        decide_next_via_runtime,
        get_or_start_run,
    )

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    run_dir = Path(run_ref.run_dir)

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)

    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        return_value=fake_result,
    ):
        decision = decide_next_via_runtime("test", mission_slug, "success", repo_root)

    # Run-state advanced past ``specify``.
    snapshot = _read_snapshot(run_dir)
    assert "specify" in snapshot.completed_steps, f"Expected 'specify' in completed_steps after composition success; snapshot={snapshot!r}"

    # The runtime event log received the canonical ``NextStepAutoCompleted``
    # event for the step we just composed — emitted exactly once for this
    # advance (no duplicate from a legacy fall-through).
    event_log = run_dir / "run.events.jsonl"
    log_lines = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    auto_completed = [ev for ev in log_lines if ev.get("event_type") == "NextStepAutoCompleted" and ev.get("payload", {}).get("step_id") == "specify"]
    assert len(auto_completed) == 1, f"Expected exactly one NextStepAutoCompleted for 'specify'; got {auto_completed!r}"
    # And the returned Decision reflects progression (or terminal).
    assert decision.kind in (
        DecisionKind.step,
        DecisionKind.terminal,
        DecisionKind.decision_required,
    )


def test_advancement_helper_persists_decision_required_branch(
    composed_software_dev_project,
) -> None:
    """RISK-2 follow-up: the advancement helper must mirror the engine's
    ``decision_required`` branch.

    The original WP01 helper handled only ``step`` and ``terminal``; if
    ``plan_next()`` returned ``decision_required``, the bridge would map and
    return a Decision but never persist ``pending_decisions`` or emit
    ``DecisionInputRequested``. This test patches ``plan_next`` to force a
    ``decision_required`` outcome on the composition path and asserts the
    helper:

    1. Persists ``pending_decisions[<decision_id>]`` in the run snapshot.
    2. Appends exactly one ``DecisionInputRequested`` event to
       ``run.events.jsonl``.
    3. Returns a ``Decision`` carrying the decision metadata that callers
       can answer.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import (
        decide_next_via_runtime,
        get_or_start_run,
    )

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    run_dir = Path(run_ref.run_dir)

    # Read the live snapshot so the synthetic decision references the real
    # run_id / mission_key (NextDecision is frozen-validated).
    snapshot_before = _read_snapshot(run_dir)

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)

    synthetic_decision = NextDecision(
        kind="decision_required",
        run_id=snapshot_before.run_id,
        mission_key=snapshot_before.mission_key,
        step_id="post-specify-gate",
        decision_id="dm-test-001",
        input_key="post_specify_review",
        question="Do you approve the spec output?",
        options=["yes", "no"],
    )

    with (
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ),
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=synthetic_decision,
        ),
    ):
        decision = decide_next_via_runtime("test", mission_slug, "success", repo_root)

    # 1. pending_decisions persisted in the snapshot.
    snapshot_after = _read_snapshot(run_dir)
    assert "dm-test-001" in snapshot_after.pending_decisions, (
        f"Expected pending_decisions to include 'dm-test-001'; got pending_decisions={dict(snapshot_after.pending_decisions)!r}"
    )

    # 2. Exactly one DecisionInputRequested event appended for this decision.
    event_log = run_dir / "run.events.jsonl"
    log_lines = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    requested = [ev for ev in log_lines if ev.get("event_type") == "DecisionInputRequested" and ev.get("payload", {}).get("decision_id") == "dm-test-001"]
    assert len(requested) == 1, f"Expected exactly one DecisionInputRequested event for 'dm-test-001'; got {requested!r}"

    # 3. Returned Decision carries the decision metadata so callers can answer.
    assert decision.kind == DecisionKind.decision_required
    assert decision.decision_id == "dm-test-001"
    assert decision.input_key == "post_specify_review"
    assert decision.question == "Do you approve the spec output?"


def test_advancement_helper_runs_default_post_completion_retrospective(
    composed_software_dev_project,
) -> None:
    repo_root, feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import (
        _advance_run_state_after_composition,
        get_or_start_run,
    )

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    captures: list[dict[str, object]] = []
    emitted_completed: list[object] = []

    class _Emitter:
        def seed_from_snapshot(self, snapshot: object) -> None:
            return None

        def emit_next_step_auto_completed(self, payload: object) -> None:
            return None

        def emit_mission_run_completed(self, payload: object) -> None:
            emitted_completed.append(payload)

    with (
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=NextDecision(
                kind="terminal",
                run_id=snapshot_before.run_id,
                mission_key=snapshot_before.mission_key,
            ),
        ),
        patch(
            "runtime.next.runtime_bridge._run_retrospective_learning_capture",
            side_effect=lambda **kwargs: captures.append(dict(kwargs)),
        ),
    ):
        decision = _advance_run_state_after_composition(
            run_ref=run_ref,
            agent="test-agent",
            mission_slug=mission_slug,
            mission_type="software-dev",
            repo_root=repo_root,
            feature_dir=feature_dir,
            timestamp="2026-05-19T00:00:00+00:00",
            progress={},
            origin={},
            sync_emitter=_Emitter(),  # type: ignore[arg-type]
        )

    assert decision.kind == DecisionKind.terminal
    assert emitted_completed
    assert captures and captures[0]["block_on_failure"] is False


def test_advancement_helper_runs_strict_retrospective_before_completion(
    composed_software_dev_project,
) -> None:
    repo_root, feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import (
        _advance_run_state_after_composition,
        get_or_start_run,
    )

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))
    captures: list[dict[str, object]] = []

    class _Emitter:
        def seed_from_snapshot(self, snapshot: object) -> None:
            return None

        def emit_next_step_auto_completed(self, payload: object) -> None:
            return None

        def emit_mission_run_completed(self, payload: object) -> None:
            return None

    strict_policy = type(
        "StrictPolicy",
        (),
        {"enabled": True, "timing": "before_completion", "failure_policy": "block"},
    )()

    with (
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=NextDecision(
                kind="terminal",
                run_id=snapshot_before.run_id,
                mission_key=snapshot_before.mission_key,
            ),
        ),
        patch(
            "runtime.next.runtime_bridge._resolve_retrospective_policy_for_runtime",
            return_value=(strict_policy, {"enabled": "test"}, None),
        ),
        patch(
            "runtime.next.runtime_bridge._run_retrospective_learning_capture",
            side_effect=lambda **kwargs: captures.append(dict(kwargs)),
        ),
    ):
        decision = _advance_run_state_after_composition(
            run_ref=run_ref,
            agent="test-agent",
            mission_slug=mission_slug,
            mission_type="software-dev",
            repo_root=repo_root,
            feature_dir=feature_dir,
            timestamp="2026-05-19T00:00:00+00:00",
            progress={},
            origin={},
            sync_emitter=_Emitter(),  # type: ignore[arg-type]
        )

    assert decision.kind == DecisionKind.terminal
    assert captures and captures[0]["block_on_failure"] is True


def test_advancement_helper_raises_policy_error_for_strict_retrospective(
    composed_software_dev_project,
) -> None:
    repo_root, feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import (
        _advance_run_state_after_composition,
        get_or_start_run,
    )

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    snapshot_before = _read_snapshot(Path(run_ref.run_dir))

    class _Emitter:
        def seed_from_snapshot(self, snapshot: object) -> None:
            return None

        def emit_next_step_auto_completed(self, payload: object) -> None:
            return None

    strict_policy = type(
        "StrictPolicy",
        (),
        {"enabled": True, "timing": "before_completion", "failure_policy": "block"},
    )()
    policy_error = RuntimeError("bad retrospective policy")

    with (
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=NextDecision(
                kind="terminal",
                run_id=snapshot_before.run_id,
                mission_key=snapshot_before.mission_key,
            ),
        ),
        patch(
            "runtime.next.runtime_bridge._resolve_retrospective_policy_for_runtime",
            return_value=(strict_policy, {"enabled": "test"}, policy_error),
        ),
        pytest.raises(RuntimeError, match="bad retrospective policy"),
    ):
        _advance_run_state_after_composition(
            run_ref=run_ref,
            agent="test-agent",
            mission_slug=mission_slug,
            mission_type="software-dev",
            repo_root=repo_root,
            feature_dir=feature_dir,
            timestamp="2026-05-19T00:00:00+00:00",
            progress={},
            origin={},
            sync_emitter=_Emitter(),  # type: ignore[arg-type]
        )


def test_decision_shape_unchanged_for_composed_action(
    composed_software_dev_project,
) -> None:
    """FR-005: composed-path Decision exposes the same field set as the legacy path.

    Snapshot the ``Decision`` field set so a future change that adds or
    removes a field on the composed path will fail loudly. The expected set
    is the dataclass's documented fields; the comparison is a strict equality
    so renaming or hiding any field reads as a regression.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)
    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        return_value=fake_result,
    ):
        decision = decide_next_via_runtime("test", mission_slug, "success", repo_root)

    expected_fields = {
        "kind",
        "agent",
        "mission_slug",
        "mission",
        "mission_state",
        "timestamp",
        "action",
        "wp_id",
        "workspace_path",
        "prompt_file",
        "reason",
        "guard_failures",
        # #3883: the path each failing guard read, carried beside the failure
        # names so a blocked decision is diagnosable without a source read.
        # Additive and defaulted — ``guard_failures`` itself is untouched.
        "guard_failure_paths",
        "progress",
        "origin",
        "run_id",
        "step_id",
        "decision_id",
        "input_key",
        "question",
        "options",
        "is_query",
        "preview_step",
        "mission_number",
        "mission_type",
    }
    actual_fields = set(vars(decision).keys())
    assert actual_fields == expected_fields, (
        f"Decision field set drifted on the composed path; unexpected={actual_fields - expected_fields!r}, missing={expected_fields - actual_fields!r}"
    )


def test_non_composed_action_uses_legacy_runtime_next_step(
    composed_software_dev_project,
) -> None:
    """EDGE-002: actions outside the composition allow-list still call the legacy path.

    Uses the software-dev mission's ``bootstrap`` step (not in the composition
    allow-list) so that ``_should_dispatch_via_composition`` returns False and
    the bridge falls through to the legacy ``runtime_next_step`` path. This
    pins the non-composed regression: composition-side helpers must not run,
    and the legacy DAG handler is the one and only entry point exercised.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project

    # The first ``decide_next_via_runtime`` call has no prior issued step
    # (current_step_id == None), so the composition predicate is False
    # because the gating ``current_step_id and ...`` is False; the bridge
    # therefore falls through to ``runtime_next_step``.
    from runtime.next.runtime_bridge import decide_next_via_runtime

    sentinel_runtime_decision = MagicMock()
    sentinel_runtime_decision.kind = "terminal"
    sentinel_runtime_decision.step_id = None
    sentinel_runtime_decision.run_id = "run-y"
    sentinel_runtime_decision.reason = "Mission complete"

    with (
        patch("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute") as mock_execute,
        patch("runtime.next.runtime_bridge_engine.advance_run_state_after_composition") as mock_advance,
        patch(
            "runtime.next.runtime_bridge.runtime_next_step",
            return_value=sentinel_runtime_decision,
        ) as mock_legacy,
    ):
        decide_next_via_runtime("test", mission_slug, "success", repo_root)

    # For a non-composed entry path the legacy DAG handler is the only one
    # that runs; composition-side helpers are never entered.
    mock_legacy.assert_called_once()
    mock_execute.assert_not_called()
    mock_advance.assert_not_called()


def test_advancement_helper_failure_propagates_no_legacy_fallback(
    composed_software_dev_project,
) -> None:
    """EDGE-003: helper raises → ``Decision(blocked)`` and NO legacy fallback.

    If the advancement helper itself raises after a successful composition,
    the bridge MUST surface the failure as a structured ``Decision`` and MUST
    NOT silently re-enter ``runtime_next_step`` as a fallback. Doing so would
    re-introduce the very double-dispatch this WP forbids.
    """
    repo_root, _feature_dir, mission_slug = composed_software_dev_project
    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)

    with (
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ),
        patch(
            "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
            side_effect=RuntimeError("boom: snapshot persistence broken"),
        ) as mock_advance,
        patch(
            "runtime.next.runtime_bridge.runtime_next_step",
        ) as mock_legacy,
    ):
        decision = decide_next_via_runtime("test", mission_slug, "success", repo_root)

    assert mock_advance.called
    # CRITICAL: the legacy DAG dispatch handler must NOT be entered as a
    # silent fallback when the advancement helper fails.
    mock_legacy.assert_not_called()
    assert decision.kind == DecisionKind.blocked
    assert decision.reason is not None
    assert "boom: snapshot persistence broken" in decision.reason
    assert "RuntimeError" in decision.reason


# ===========================================================================
# Mission ``local-custom-mission-loader-01KQ2VNJ`` (WP04) — gate widening +
# profile_hint plumbing.
#
# Two concerns get test pressure here:
#
#   1. Custom missions whose active step sets ``agent_profile`` must dispatch
#      through composition AND the resolved profile must arrive at the
#      executor as ``profile_hint``.
#   2. Built-in ``software-dev`` dispatch must remain byte-identical: the
#      executor is invoked with ``profile_hint=None`` (built-in templates
#      don't set ``agent_profile``; ``_ACTION_PROFILE_DEFAULTS`` resolves it
#      inside the executor).
# ===========================================================================


class TestCustomMissionComposition:
    """WP04: composition gate widening + profile_hint plumbing."""

    @staticmethod
    def _patch_frozen_template_agent_profile(run_dir: Path, step_id: str, agent_profile: str) -> None:
        """Mutate the run's frozen template to set ``agent_profile`` on a step.

        Tests use this to convert one of the existing (built-in) frozen
        template steps into a custom-mission-equivalent step, exercising the
        widened gate without scaffolding a fully discoverable custom mission.
        """
        import yaml as _yaml

        frozen_path = run_dir / "mission_template_frozen.yaml"
        data = _yaml.safe_load(frozen_path.read_text(encoding="utf-8"))
        for step in data.get("steps", []):
            if step.get("id") == step_id:
                step["agent_profile"] = agent_profile
                break
        else:  # pragma: no cover — guard against test scaffolding drift
            raise AssertionError(f"step {step_id!r} not found in frozen template at {frozen_path}")
        frozen_path.write_text(_yaml.safe_dump(data), encoding="utf-8")

    def test_builtin_software_dev_ignores_template_agent_profile(self, composed_software_dev_project) -> None:
        """Built-in dispatch ignores template-side ``agent_profile`` values.

        Custom missions read ``agent_profile`` from the frozen template, but
        built-in ``software-dev`` must keep PR #797's fast path and continue
        using ``_ACTION_PROFILE_DEFAULTS`` inside the executor.
        """
        repo_root, _feature_dir, mission_slug = composed_software_dev_project
        _advance_runtime_to_step(repo_root, mission_slug, "specify")

        from runtime.next.runtime_bridge import (
            decide_next_via_runtime,
            get_or_start_run,
        )

        run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
        # Inject a step-level ``agent_profile`` so the call site picks it up
        # via ``_resolve_step_agent_profile`` and threads it through.
        self._patch_frozen_template_agent_profile(Path(run_ref.run_dir), "specify", "implementer-ivan")

        fake_result = MagicMock()
        fake_result.invocation_ids = ("inv-001",)

        sentinel_decision = Decision(
            # WP02 / #844: kind=step now requires a non-null, on-disk-resolvable
            # prompt_file. This sentinel is only used as the return value of a
            # patched ``_advance_run_state_after_composition`` and the test does
            # not assert on its ``kind`` — switch to ``terminal`` so the
            # construction-time validator is not tripped.
            kind=DecisionKind.terminal,
            agent="test",
            mission_slug=mission_slug,
            mission="software-dev",
            mission_state="next",
            timestamp="2026-04-25T00:00:00+00:00",
            action="next",
            run_id="run-x",
            step_id="next",
        )

        with (
            patch(
                "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
                return_value=fake_result,
            ) as mock_execute,
            patch(
                "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
                return_value=sentinel_decision,
            ),
        ):
            decide_next_via_runtime("test", mission_slug, "success", repo_root)

        # Exactly one composition call, with no profile threaded in for the
        # built-in fast path.
        assert mock_execute.call_count == 1
        call = mock_execute.call_args
        # The executor receives a single ``StepContractExecutionContext``
        # argument; ``call.args`` may be empty if the bridge passed it
        # positionally or via the ``context=`` kwarg. Cover both shapes.
        context = call.args[0] if call.args else call.kwargs["context"]
        assert isinstance(context, StepContractExecutionContext)
        assert context.profile_hint is None, f"Built-in software-dev dispatch must ignore template-side agent_profile; got {context.profile_hint!r}"

    def test_builtin_software_dev_dispatches_with_none_profile_hint(self, composed_software_dev_project) -> None:
        """FR-010: built-in dispatch is byte-identical — ``profile_hint`` stays ``None``.

        Built-in software-dev frozen templates do NOT set ``agent_profile``,
        so ``_resolve_step_agent_profile`` returns ``None`` and the executor
        receives ``profile_hint=None`` exactly as before this WP. The
        executor's internal ``_resolve_profile_hint`` then falls back to
        ``_ACTION_PROFILE_DEFAULTS`` — that fallback path is unchanged.
        """
        repo_root, _feature_dir, mission_slug = composed_software_dev_project
        _advance_runtime_to_step(repo_root, mission_slug, "specify")

        from runtime.next.runtime_bridge import decide_next_via_runtime

        fake_result = MagicMock()
        fake_result.invocation_ids = ("inv-001",)

        sentinel_decision = Decision(
            # WP02 / #844: kind=step now requires a non-null, on-disk-resolvable
            # prompt_file. This sentinel is only used as the return value of a
            # patched ``_advance_run_state_after_composition`` and the test does
            # not assert on its ``kind`` — switch to ``terminal`` so the
            # construction-time validator is not tripped.
            kind=DecisionKind.terminal,
            agent="test",
            mission_slug=mission_slug,
            mission="software-dev",
            mission_state="next",
            timestamp="2026-04-25T00:00:00+00:00",
            action="next",
            run_id="run-x",
            step_id="next",
        )

        with (
            patch(
                "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
                return_value=fake_result,
            ) as mock_execute,
            patch(
                "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
                return_value=sentinel_decision,
            ),
        ):
            decide_next_via_runtime("test", mission_slug, "success", repo_root)

        assert mock_execute.call_count == 1
        call = mock_execute.call_args
        context = call.args[0] if call.args else call.kwargs["context"]
        assert isinstance(context, StepContractExecutionContext)
        assert context.profile_hint is None, (
            f"Built-in software-dev dispatch must keep profile_hint=None to "
            f"preserve the executor's _ACTION_PROFILE_DEFAULTS fallback path; "
            f"got {context.profile_hint!r}"
        )

    def test_custom_mission_dispatch_resolves_via_registry(self, composed_software_dev_project) -> None:
        """F-1: ``_dispatch_via_composition`` looks up the synthesized
        contract in :class:`RuntimeContractRegistry` by id
        ``custom:<mission>:<action>`` and passes it to
        :meth:`StepContractExecutor.execute` as ``contract=...``.

        This is the regression that the merged mission's tests missed.
        Custom missions never write step contracts to disk; the only
        place they exist at runtime is the in-memory registry. Without
        the registry lookup the executor falls through to
        ``MissionStepContractRepository.get_by_action(...)`` which has
        no record and raises :class:`StepContractExecutionError`.
        """
        from charter.offering.missions.step_contracts import (
            MissionStepContract,
            MissionStepContractStep as MissionStep,
        )

        from specify_cli.mission_loader.registry import (
            get_runtime_contract_registry,
        )
        from runtime.next.runtime_bridge import decide_next_via_runtime

        repo_root, _feature_dir, mission_slug = composed_software_dev_project
        _advance_runtime_to_step(repo_root, mission_slug, "specify")

        # Pretend the active step is a custom-mission composed step:
        # widen the gate by setting ``agent_profile`` on the frozen
        # template's ``specify`` step.
        from runtime.next.runtime_bridge import get_or_start_run

        run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
        self._patch_frozen_template_agent_profile(Path(run_ref.run_dir), "specify", "implementer-ivan")

        # Register a synthesized contract under the id the dispatcher
        # is expected to query.
        synthesized = MissionStepContract(
            id="custom:software-dev:specify",
            schema_version="1.0",
            action="specify",
            mission="software-dev",
            steps=[
                MissionStep(
                    id="specify.execute",
                    description="synthesized for F-1 regression test",
                ),
            ],
        )
        registry = get_runtime_contract_registry()
        registry.clear()
        registry.register([synthesized])

        try:
            fake_result = MagicMock()
            fake_result.invocation_ids = ("inv-001",)

            sentinel_decision = Decision(
                # WP02 / #844: kind=step now requires a non-null,
                # on-disk-resolvable prompt_file. This sentinel is only the
                # return value of a patched
                # ``_advance_run_state_after_composition`` and the test does
                # not assert on ``kind`` — use ``terminal`` so the
                # construction-time validator is not tripped.
                kind=DecisionKind.terminal,
                agent="test",
                mission_slug=mission_slug,
                mission="software-dev",
                mission_state="next",
                timestamp="2026-04-25T00:00:00+00:00",
                action="next",
                run_id="run-x",
                step_id="next",
            )

            with (
                patch(
                    "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
                    return_value=fake_result,
                ) as mock_execute,
                patch(
                    "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
                    return_value=sentinel_decision,
                ),
            ):
                decide_next_via_runtime("test", mission_slug, "success", repo_root)

            assert mock_execute.call_count == 1
            call = mock_execute.call_args
            # ``contract=`` is the second positional or a kwarg; cover both.
            passed_contract = call.kwargs.get("contract") if "contract" in call.kwargs else (call.args[1] if len(call.args) > 1 else None)
            assert passed_contract is synthesized, (
                "dispatcher must resolve the synthesized contract from "
                "RuntimeContractRegistry and pass it via contract=...; "
                f"got passed_contract={passed_contract!r}"
            )
        finally:
            registry.clear()


# ---------------------------------------------------------------------------
# WP04 T027 (#3704, AC-10) -- end-to-end demonstration that a custom mission
# family gates on its own declared filenames, at the conventional org-tier
# layout (`<org_root>/missions/<type>/expected-artifacts.yaml`), reachable
# now that this branch is stacked on #3708's path-anchor fix.
#
# Unlike ``TestAC1AC2ComposedActionGuardOrgTierConvergence`` above (which
# calls the leaf ``_check_composed_action_guard`` directly and then hand-
# builds a ``Decision`` via ``_dn_composition_blocked_decision``), this test
# drives the real decision-walk phase function ``_dn_dependency_gate`` --
# the exact, unmodified callable ``decide_next_via_runtime`` invokes as
# Phase 2 of its ``for phase in (_dn_dependency_gate, _dn_composition_dispatch,
# _dn_decision_materialize):`` loop (see that function's docstring). This is
# structurally the ONLY call site a custom, guard-table-unregistered family
# can reach without opting into composition dispatch (frozen-template
# ``agent_profile``/``contract_ref`` widening is a different, orthogonal
# feature -- AC-10 is about guard evaluation reaching the org-tier manifest,
# not about composed-action dispatch), per
# ``TestAC8RepoRootThreadedThroughDnDependencyGate``'s own docstring.
#
# The walk asserts BOTH halves on the real ``Decision``/gate-release the
# production code actually produces:
#   * absent blocking artifact -> ``_dn_dependency_gate`` returns a real
#     ``Decision`` with ``kind == DecisionKind.blocked`` and
#     ``guard_failures`` naming the missing file.
#   * artifact created -> ``_dn_dependency_gate`` returns ``None`` -- the
#     documented "no phase blocked, fall through to the next phase" signal --
#     and a second, real phase call (``_dn_composition_dispatch``, also
#     unmodified) is chained on top and independently confirmed to release
#     control too, so the walk demonstrates the guard no longer holds the
#     run at *any* reachable phase once the artifact exists.
# ---------------------------------------------------------------------------


def _t027_write_org_pack_config(repo_root: Path, *, org_name: str, org_root: Path) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        f"      - name: {org_name}\n"
        f"        local_path: {org_root}\n",
        encoding="utf-8",
    )


def _t027_write_org_manifest(org_root: Path, mission_type: str, yaml_text: str) -> None:
    # Conventional org-tier layout fixed by #3703/PR #3708:
    # <org_root>/missions/<mission_type>/expected-artifacts.yaml
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "expected-artifacts.yaml").write_text(yaml_text, encoding="utf-8")


def _t027_write_meta(feature_dir: Path, mission_type: str) -> None:
    import json as _json

    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        _json.dumps({"mission_type": mission_type}), encoding="utf-8"
    )


def _t027_seed_approved_wp(feature_dir: Path, wp_id: str) -> None:
    """Seed one WP file plus a canonical status event placing it in ``approved``
    -- all WPs "handed off", so the WP-iteration pre-check proceeds to the
    guard check instead of staying in WP-iteration mode."""
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} task\n---\n# {wp_id}\nDo something.\n",
        encoding="utf-8",
    )
    event = StatusEvent(
        event_id=f"t027-{wp_id}-approved",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.APPROVED,
        at="2026-08-24T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


_T027_QA_FAMILY = "qa"
_T027_QA_ORG_YAML = """\
schema_version: "1.0"
mission_type: "qa"
manifest_version: "org-1"
required_always: []
required_by_step:
  implement:
    - artifact_key: "output.qa.coverage"
      artifact_class: "output"
      path_pattern: "qa-coverage.json"
      blocking: true
optional_always: []
"""


class TestAC10CustomFamilyOrgTierNextDecisionWalk:
    """WP04 T027 -- AC-10 end-to-end: a custom ``qa`` family with ONLY an
    org-tier manifest at the conventional layout gates on its own declared
    filename, walked through the real decision-phase functions."""

    def _make_project(self, tmp_path: Path) -> tuple[Path, Path]:
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _t027_write_org_manifest(org_root, _T027_QA_FAMILY, _T027_QA_ORG_YAML)
        _t027_write_org_pack_config(project_root, org_name="acme", org_root=org_root)

        feature_dir = project_root / "kitty-specs" / "042-qa-mission"
        _t027_write_meta(feature_dir, _T027_QA_FAMILY)
        _t027_seed_approved_wp(feature_dir, "WP01")
        return project_root, feature_dir

    def _make_ctx(self, project_root: Path, feature_dir: Path, run_dir: Path) -> rb.DecideNextContext:
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(
            run_id="run-qa-t027", run_dir=str(run_dir), mission_key="042-qa-mission"
        )
        return rb.DecideNextContext(
            agent="agent-x",
            mission_slug="042-qa-mission",
            result="success",
            repo_root=project_root,
            feature_dir=feature_dir,
            now="2026-08-24T00:00:00+00:00",
            mission_type=_T027_QA_FAMILY,
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={"mission_tier": "custom", "mission_path": _T027_QA_FAMILY},
            progress={"total_wps": 1},
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="implement",
        )

    def test_absent_blocking_artifact_blocks_the_real_decision_walk(
        self, tmp_path: Path
    ) -> None:
        project_root, feature_dir = self._make_project(tmp_path)
        ctx = self._make_ctx(project_root, feature_dir, tmp_path / "run")

        # qa-coverage.json does not exist on disk.
        decision = rb._dn_dependency_gate(ctx)

        assert decision is not None, (
            "Phase 2 of the real decide_next_via_runtime walk must hold the "
            "run in place when the org-tier manifest's blocking artifact is "
            "absent -- returning None here would mean the walk silently "
            "advanced past an unmet blocking:true requirement (#3704)."
        )
        assert decision.kind == DecisionKind.blocked
        assert decision.guard_failures != []
        assert any("qa-coverage.json" in failure for failure in decision.guard_failures), (
            f"expected the org-tier manifest's declared filename in "
            f"guard_failures, got {decision.guard_failures!r}"
        )

    def test_artifact_created_advances_the_real_decision_walk(self, tmp_path: Path) -> None:
        project_root, feature_dir = self._make_project(tmp_path)
        ctx = self._make_ctx(project_root, feature_dir, tmp_path / "run")

        # Flip presence: same context, same manifest, only the artifact's
        # existence on disk changes -- proves the guard is genuinely
        # re-evaluated, not a fixture that only ever exercises one branch.
        (feature_dir / "qa-coverage.json").write_text("{}", encoding="utf-8")

        gate_decision = rb._dn_dependency_gate(ctx)
        assert gate_decision is None, (
            "Phase 2 must release the run (return None -- the documented "
            "'no phase blocked, fall through' signal) once the declared "
            f"blocking artifact exists; got {gate_decision!r}"
        )

        # Chain the next real, unmodified phase to confirm the walk
        # genuinely continues toward advancement rather than being
        # silently re-blocked one phase later.
        composition_decision = rb._dn_composition_dispatch(ctx)
        assert composition_decision is None, (
            "qa has no charter-registered action sequence and no "
            "agent_profile/contract_ref widening on this run's frozen "
            "template, so composition dispatch must also fall through "
            f"cleanly; got {composition_decision!r}"
        )
