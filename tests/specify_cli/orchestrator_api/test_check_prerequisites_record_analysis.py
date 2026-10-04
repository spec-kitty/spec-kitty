"""WP04 (design-phase-orchestrator-api-01M1HE6M) -- ``check-prerequisites``/
``record-analysis`` orchestrator-api verbs (FR-004/FR-005, NFR-004/SK-93,
SK-06/#3133).

Acceptance scenarios (see
``kitty-specs/design-phase-orchestrator-api-01M1HE6M/tasks/WP04-check-prerequisites-record-analysis.md``):

1. ``check-prerequisites --mission <slug> --include-tasks`` returns the SAME
   validated-structure fields the host CLI's own ``check_prerequisites``
   Typer command (``mission_check_prerequisites.py:498``) returns for
   ``--json --include-tasks`` -- verified here by calling BOTH the
   orchestrator-api verb and the host function directly and diffing their
   payloads, not by re-deriving the shape independently (a real field-parity
   proof, not an assertion against a hand-copied fixture).
2. ``record-analysis`` (NFR-004 / SK-93): the artifact-verification mechanism
   is the SOLE success signal -- three genuinely distinct SC-005 scenarios:
   (a) swallowed-exception-but-written -> ``success: true`` (the SK-93
       regression guard: a raised exception after a real write must NOT be
       reported as failure).
   (b) hang-but-written -> the command returns within its enforced timeout
       bound regardless of the underlying write path blocking forever (a real
       wall-clock assertion, not "eventually returned").
   (c) stale-but-coincidentally-matching-verdict -> ``success: false`` (the
       SPEC-VERIFY-001 regression guard: a verdict-string match alone is
       never sufficient -- the re-read ``generated_at`` must also be strictly
       later than the call-start timestamp).
3. SK-06 / #3133: an ``unknown`` verdict (a report with no valid
   ``analysis-findings/v1`` carrier) is NEVER reported as ``success: true``,
   even when the underlying write genuinely succeeds with a fresh timestamp.

This is the RED-then-GREEN ATDD anchor (charter C-011): pre-implementation,
neither ``check-prerequisites`` nor ``record-analysis`` exist as
``@app.command``s on ``orchestrator_api.commands.app``, so every scenario
below fails at the Typer "no such command" / non-zero-exit level.

Real mission scaffolding (real files under ``kitty-specs/<slug>/``, real git
commits via the ``specify``/``plan``/``tasks`` verbs -- WP03) plus real
``analysis-report.md`` disk I/O -- hence ``integration``/``git_repo`` (NOT
``fast``), mirroring ``test_specify_plan_tasks_verbs.py``'s /
``test_transition_subtask_gate.py``'s precedent.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from tests._factories import provision_test_charter
from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.0.1",
        "agent_family": "claude",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)

_SUBSTANTIVE_SPEC = """# Spec — WP04 verbs

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Do the thing | Users can do the thing end to end. | High | Open |

## User Scenarios
A user does the thing via the orchestrator-api.
"""

_CARRIER_READY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)

_LEGACY_NO_CARRIER_BODY = "# Specification Analysis Report\n\nNo carrier at all -- a legacy report.\n"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    """A real, non-protected-branch git repo with an activated mission type."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "wp04-work"], cwd=repo, check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    provision_test_charter(repo)
    return repo


def _run(repo: Path, args: list[str]) -> Result:
    """Invoke the real orchestrator-api ``app`` with cwd pinned at ``repo``."""
    with contextlib.chdir(repo):
        return runner.invoke(app, args, catch_exceptions=False)


def _envelope(result: Result) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(result.output.strip().split("\n")[0]))


def _specify(repo: Path, mission_slug: str, *, mission_type: str = "software-dev") -> dict[str, Any]:
    result = _run(
        repo,
        [
            "specify",
            "--mission",
            mission_slug,
            "--mission-type",
            mission_type,
            "--topology",
            "single_branch",
            "--policy",
            _POLICY,
        ],
    )
    return _envelope(result)


def _build_mission(repo: Path, slug: str) -> tuple[str, Path]:
    """Specify + plan + tasks a real mission, matching WP03's proven flow.

    Returns ``(mission_slug, feature_dir)``. The mission carries real,
    committed spec.md/plan.md/tasks.md -- the exact set
    ``write_analysis_report``'s required-artifact check demands.
    """
    created = _specify(repo, slug)
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]
    feature_dir = Path(created["data"]["feature_dir"])

    spec_file = Path(created["data"]["spec_file"])
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "substantive spec")

    plan_result = _run(repo, ["plan", "--mission", mission_slug, "--policy", _POLICY])
    plan_envelope = _envelope(plan_result)
    assert plan_envelope["success"] is True, plan_envelope

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_wp01/**\n"
        "authoritative_surface: src/module_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed tasks")

    tasks_result = _run(repo, ["tasks", "--mission", mission_slug, "--policy", _POLICY])
    tasks_envelope = _envelope(tasks_result)
    assert tasks_envelope["success"] is True, tasks_envelope

    # Every phase transition leaves the tree clean before the next one starts
    # (matching a real orchestrator's own commit-between-phases workflow) --
    # `tasks` leaves its own bookkeeping residue (e.g. `.kittify/sync-state.json`)
    # uncommitted, which is unrelated to record-analysis's OWN dirty-tree guard
    # (SK-114) and must not be mistaken for it.
    status = _git(repo, "status", "--porcelain").stdout
    if status.strip():
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "post-tasks bookkeeping")

    return mission_slug, feature_dir


def _record_analysis(repo: Path, mission_slug: str, body: str, *, tmp_path: Path, agent: str = "test-agent") -> dict[str, Any]:
    input_file = tmp_path / "report-body.md"
    input_file.write_text(body, encoding="utf-8")
    result = _run(
        repo,
        [
            "record-analysis",
            "--mission",
            mission_slug,
            "--input-file",
            str(input_file),
            "--agent",
            agent,
            "--policy",
            _POLICY,
        ],
    )
    return _envelope(result)


# ---------------------------------------------------------------------------
# Acceptance Scenario 1 -- check-prerequisites: field-parity with the host CLI
# ---------------------------------------------------------------------------


def test_check_prerequisites_field_parity_with_host_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_mission(repo, "wp04-scenario1")
    monkeypatch.setattr(
        "specify_cli.context.resolver.now_utc_iso",
        lambda: "2026-09-03T00:00:00Z",
    )

    import contextlib
    import io

    monkeypatch.chdir(repo)
    from specify_cli.cli.commands.agent.mission_check_prerequisites import (
        check_prerequisites as host_check_prerequisites,
    )

    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        host_check_prerequisites(feature=mission_slug, json_output=True, include_tasks=True)
    host_payload = json.loads(capture.getvalue().strip().split("\n")[0])

    result = _run(
        repo,
        ["check-prerequisites", "--mission", mission_slug, "--include-tasks"],
    )
    envelope = _envelope(result)

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]

    # Field-parity: every field the host CLI's own check_prerequisites Typer
    # command emits must be present with an identical value on the
    # orchestrator-api verb's payload (C-002: context only, no re-derivation).
    for key, value in host_payload.items():
        assert key in data, f"missing field {key!r} from orchestrator-api check-prerequisites payload"
        assert data[key] == value, f"field {key!r} diverges: host={value!r} orch={data[key]!r}"

    # Transport-contract identity field.
    assert data["mission_slug"] == mission_slug
    assert data["valid"] is True


# Fold-in review finding -- ``check-prerequisites`` re-emits the host CLI
# delegate's ``validate_feature_structure`` dict verbatim as the versioned
# 1.4.0 contract ``data`` (docs/api/orchestrator-api.md's "check-
# prerequisites" section: "the host CLI's own ``validate_feature_structure``
# shape, with ``mission_slug`` filled in"). Nothing pins that shape to the
# contract version, so a delegate shape change would otherwise silently
# mutate the external contract with no test ever failing. Captured against a
# real, live invocation (NOT re-derived from the implementation).
_CHECK_PREREQUISITES_SUCCESS_DATA_KEYS = frozenset(
    {
        "AVAILABLE_DOCS",
        "BASE_BRANCH",
        "BRANCH_MATCHES_TARGET",
        "CURRENT_BRANCH",
        "EXPECTED_BASE_BRANCH",
        "EXPECTED_TARGET_BRANCH",
        "FEATURE_DIR",
        "MERGE_TARGET_BRANCH",
        "NOW_UTC_ISO",
        "PLANNING_BASE_BRANCH",
        "TARGET_BRANCH",
        "artifact_dirs",
        "artifact_files",
        "available_docs",
        "base_branch",
        "branch_context",
        "branch_matches_target",
        "branch_strategy_summary",
        "current_branch",
        "errors",
        "merge_target_branch",
        "mission_dir",
        "mission_slug",
        "paths",
        "planning_base_branch",
        "runtime_vars",
        "spec_kitty_version",
        "target_branch",
        "valid",
        "warnings",
    }
)


def test_check_prerequisites_success_data_key_shape_is_pinned(tmp_path: Path) -> None:
    """Pin the exact key-SET (not values -- git branch names/timestamps are
    environment-dependent) so a future field added/removed/renamed on the
    host CLI's ``validate_feature_structure`` delegate trips this test.
    """
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_mission(repo, "wp04-pin-shape")

    result = _run(
        repo,
        ["check-prerequisites", "--mission", mission_slug, "--include-tasks"],
    )
    envelope = _envelope(result)

    assert envelope["success"] is True, envelope
    assert set(envelope["data"].keys()) == _CHECK_PREREQUISITES_SUCCESS_DATA_KEYS


def test_check_prerequisites_missing_mission_fails_closed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    result = _run(
        repo,
        ["check-prerequisites", "--mission", "999-does-not-exist"],
    )
    envelope = _envelope(result)

    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_check_prerequisites_translates_forbidden_code_in_nested_payload_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-TESTS-002 (severity 4, R3-confirmed LIVE defect, not merely
    untested): ``_classify_check_prerequisites_error`` translates the
    delegate's forbidden ``error_code: "FEATURE_CONTEXT_UNRESOLVED"`` to the
    canonical ``MISSION_NOT_FOUND`` at the envelope's TOP level -- but the
    raw delegate payload it also returns (spread verbatim into ``data``)
    still carried the SAME forbidden string, untranslated, under its own
    nested ``error_code`` key. Gets past the mission-existence gate (a real
    mission dir must exist), then makes the delegate itself raise with a
    real production-shaped ``FEATURE_CONTEXT_UNRESOLVED`` payload (mirroring
    ``mission_check_prerequisites._build_setup_plan_detection_error``'s own
    shape) -- proving the translation now covers the WHOLE payload, not
    just the field this function happens to return first.
    """
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_mission(repo, "wp04-scenario-tests002")

    import specify_cli.cli.commands.agent.mission_check_prerequisites as host_module

    def _raises_feature_context_unresolved(*, feature: str | None, json_output: bool, include_tasks: bool = False) -> None:
        payload = {
            "error_code": "FEATURE_CONTEXT_UNRESOLVED",
            "mission_flag": feature,
            "error": "simulated feature-context resolution failure",
            "remediation": "Re-run with --mission <slug>",
        }
        print(json.dumps(payload))
        raise typer.Exit(1)

    monkeypatch.setattr(host_module, "check_prerequisites", _raises_feature_context_unresolved)

    result = _run(repo, ["check-prerequisites", "--mission", mission_slug])
    envelope = _envelope(result)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "MISSION_NOT_FOUND"
    assert envelope["data"]["error_code"] == "MISSION_NOT_FOUND", envelope

    # Assert on the WHOLE serialized envelope, not just the two fields above
    # -- the forbidden string must not survive anywhere, at any nesting
    # depth, so the next leak through a DIFFERENT nested field is caught too.
    serialized = json.dumps(envelope)
    assert "FEATURE_CONTEXT_UNRESOLVED" not in serialized, serialized


def test_sanitize_forbidden_error_code_scrubs_dict_keys_and_substrings() -> None:
    """PR-TESTS-002 residual (severity 3): the prior sanitizer recursed
    dict/list VALUES only and matched the forbidden token by whole-value
    ``==``, so a verifier defeated the "no forbidden token anywhere in the
    serialized envelope" claim two ways it never covered: the token as a
    dict KEY, and the token embedded as a SUBSTRING of a longer string.
    Neither shape needs the full CLI plumbing to prove -- both are direct
    properties of :func:`_sanitize_forbidden_error_code` -- so this asserts
    against the function itself rather than round-tripping through a real
    delegate failure a second time.
    """
    from specify_cli.orchestrator_api.design_phase import _sanitize_forbidden_error_code

    forbidden = "FEATURE_CONTEXT_UNRESOLVED"
    replacement = "MISSION_NOT_FOUND"

    # Shape 1: the forbidden token as a dict KEY (the old sanitizer only
    # ever recursed ``.items()`` VALUES, so a key never got visited).
    key_shape = {forbidden: "some value", "nested": {forbidden: ["x"]}}
    sanitized_keys = _sanitize_forbidden_error_code(key_shape, forbidden, replacement)
    assert forbidden not in json.dumps(sanitized_keys), sanitized_keys
    assert sanitized_keys == {replacement: "some value", "nested": {replacement: ["x"]}}

    # Shape 2: the forbidden token as a SUBSTRING of a larger string (the
    # old sanitizer matched with ``value == forbidden``, an exact
    # whole-string match that a longer string embedding the token defeats).
    substring_shape = {"message": f"error: {forbidden}_v2 occurred while resolving"}
    sanitized_substring = _sanitize_forbidden_error_code(substring_shape, forbidden, replacement)
    assert forbidden not in json.dumps(sanitized_substring), sanitized_substring
    assert sanitized_substring == {"message": f"error: {replacement}_v2 occurred while resolving"}


# ---------------------------------------------------------------------------
# PR-CONTRACT-001 (host-CLI parity, severity 3, R3-confirmed live-reproduced
# defect): record-analysis's dirty-worktree preflight must run BEFORE body
# validation, matching the host CLI's own ordering exactly. This is the
# THIRD instance of the "check in the right place but the wrong order" class
# in this mission (after WP05-001/WP08-001) -- ``_host_record_analysis_
# error_code`` below is a reusable, verb-agnostic helper (not hand-rolled
# per-test as the first two instances were): it drives the SAME on-disk
# fixture through the host CLI's OWN ``record_analysis`` function and
# returns its ``error_code``, so any future record-analysis ordering test
# (or a similarly-shaped verb) can assert parity against real host-CLI
# behavior instead of a hand-copied expectation. A full production-code
# "closed by construction" guard (e.g. a shared preflight-order descriptor
# consumed by both callers) was judged infeasible within this diff: the
# mission's mutating verbs each have a structurally DIFFERENT preflight
# shape (record-analysis's body-read + dirty-tree pair vs.
# defer/cancel-decision's --rationale check vs. answer-decision's --result
# check) with no common ordering primitive to extract without forcing an
# artificial abstraction over otherwise-unrelated validation logic for a
# class with only 3 known instances -- this test-level parity harness is
# the pragmatic mitigation instead.
# ---------------------------------------------------------------------------


def _host_record_analysis_error_code(repo: Path, mission_slug: str, body: str, *, tmp_path: Path, agent: str = "test-agent") -> str:
    """Invoke the host CLI's OWN ``record_analysis`` (``mission_record_analysis.py``)
    directly against *repo* and return its ``error_code`` -- ground truth for
    ordering-parity assertions, mirroring ``test_check_prerequisites_field_
    parity_with_host_cli``'s established "call the real host function, don't
    re-derive its shape" precedent. Callers are expected to pass a failure
    fixture (this helper asserts the call raises ``typer.Exit``).
    """
    import io

    from specify_cli.cli.commands.agent.mission_record_analysis import (
        record_analysis as host_record_analysis,
    )

    input_file = tmp_path / "host-record-analysis-body.md"
    input_file.write_text(body, encoding="utf-8")

    capture = io.StringIO()
    with contextlib.chdir(repo), contextlib.redirect_stdout(capture), pytest.raises(typer.Exit):
        host_record_analysis(
            feature=mission_slug,
            input_file=str(input_file),
            analyzer_agent=agent,
            json_output=True,
        )
    payload = json.loads(capture.getvalue().strip().split("\n")[0])
    return str(payload["error_code"])


def test_record_analysis_dirty_worktree_wins_over_empty_body_matching_host_cli(
    tmp_path: Path,
) -> None:
    """PR-CONTRACT-001: under a SIMULTANEOUS dirty-worktree + empty-body
    condition, orchestrator-api's ``record-analysis`` must report the SAME
    first ``error_code`` the host CLI reports for the identical on-disk
    state -- ``DIRTY_WORKTREE``, never ``RECORD_ANALYSIS_EMPTY_BODY`` (which
    is what a body-validated-before-preflight ordering would surface
    instead). Ground-truthed against the REAL host CLI function (not a
    hand-copied expectation) via ``_host_record_analysis_error_code``.
    """
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_mission(repo, "wp04-contract001-ordering")

    # Dirty the tree with one untracked, non-bookkeeping file -- real dirt
    # neither surface's residue-churn allowlist would filter out.
    (repo / "untracked-dirty-marker.txt").write_text("dirt\n", encoding="utf-8")
    status = _git(repo, "status", "--porcelain").stdout
    assert "untracked-dirty-marker.txt" in status, "fixture setup failed to dirty the tree"

    orch_envelope = _record_analysis(repo, mission_slug, "", tmp_path=tmp_path)
    assert orch_envelope["success"] is False, orch_envelope
    assert orch_envelope["error_code"] == "DIRTY_WORKTREE", orch_envelope

    host_error_code = _host_record_analysis_error_code(repo, mission_slug, "", tmp_path=tmp_path)
    assert host_error_code == "DIRTY_WORKTREE"

    # The parity assertion itself: both surfaces agree on the SAME first
    # error_code for the SAME on-disk state.
    assert orch_envelope["error_code"] == host_error_code


# ---------------------------------------------------------------------------
# Acceptance Scenario 2 -- record-analysis: ordinary success path
# ---------------------------------------------------------------------------


def test_record_analysis_persists_and_verifies_via_reread(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-scenario2")

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]
    assert data["mission_slug"] == mission_slug
    assert data["verdict"] == "ready"
    report_path = feature_dir / "analysis-report.md"
    assert report_path.exists()
    assert Path(data["path"]) == report_path
    # Fold-in review finding: record-analysis's success payload must carry
    # the SAME mission identity block every other mission-scoped verb
    # includes (_mission_identity_payload), so a host can key on
    # mission_number/mission_type without a second lookup.
    assert data["mission_type"] == "software-dev"
    assert "mission_number" in data


# ---------------------------------------------------------------------------
# SK-06 / #3133 -- an unknown verdict is never reported as success
# ---------------------------------------------------------------------------


def test_record_analysis_never_reports_unknown_verdict_as_success(tmp_path: Path) -> None:
    """A legacy report (no analysis-findings/v1 carrier) writes real
    ``verdict: unknown`` content to disk (a genuinely successful WRITE) --
    but the orchestrator-api verb must still report ``success: false``,
    because an unrecorded/unknown verdict is never a trustworthy signal
    (the exact SK-06/#3133 near-miss: a malformed carrier producing
    ``verdict: unknown`` with exit 0 and no warning).
    """
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-scenario-sk06")

    envelope = _record_analysis(repo, mission_slug, _LEGACY_NO_CARRIER_BODY, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "RECORD_ANALYSIS_VERDICT_UNRELIABLE"
    # The write DID genuinely happen (unlike SC-005a/c) -- disk carries the
    # real unknown-verdict artifact; the API just refuses to call it success.
    report_path = feature_dir / "analysis-report.md"
    assert report_path.exists()
    assert "verdict: unknown" in report_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SC-005(a) -- swallowed-exception-but-written (the SK-93 regression guard)
# ---------------------------------------------------------------------------


def test_record_analysis_sc005a_swallowed_exception_but_written_reports_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-scenario-sc005a")

    import specify_cli.analysis_report as analysis_report_module

    real_write = analysis_report_module.write_analysis_report

    def _raises_after_real_write(**kwargs: Any) -> Any:
        real_write(**kwargs)
        raise RuntimeError("simulated SK-93 swallowed-exception-but-written failure")

    monkeypatch.setattr(analysis_report_module, "write_analysis_report", _raises_after_real_write)

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]
    assert data["verdict"] == "ready"
    report_path = feature_dir / "analysis-report.md"
    assert report_path.exists()


# ---------------------------------------------------------------------------
# SC-005(b) -- hang-but-written (the majority documented SK-93 failure shape)
# ---------------------------------------------------------------------------


def test_record_analysis_sc005b_hang_reports_write_not_confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-scenario-sc005b")

    from specify_cli.orchestrator_api import design_phase

    # Small bound so the test proves the mechanism quickly (the mocked write
    # NEVER returns/sets the event -- a real, unbounded hang).
    monkeypatch.setattr(design_phase, "_RECORD_ANALYSIS_TIMEOUT_SECONDS", 0.3)

    never_set = threading.Event()

    def _hangs_forever(**_kwargs: Any) -> Any:
        never_set.wait()  # never set -> blocks forever
        raise AssertionError("unreachable")

    monkeypatch.setattr("specify_cli.analysis_report.write_analysis_report", _hangs_forever)

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "RECORD_ANALYSIS_WRITE_NOT_CONFIRMED"
    # Nothing was written -- success is determined by the re-read, never by
    # whether the mocked call "returned".
    assert not (feature_dir / "analysis-report.md").exists()


@pytest.mark.performance
def test_record_analysis_sc005b_hang_returns_within_enforced_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.orchestrator_api import design_phase

    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_mission(repo, "wp04-scenario-sc005b")

    # Small bound so the test proves the mechanism quickly (the mocked write
    # NEVER returns/sets the event -- a real, unbounded hang).
    monkeypatch.setattr(design_phase, "_RECORD_ANALYSIS_TIMEOUT_SECONDS", 0.3)

    never_set = threading.Event()

    def _hangs_forever(**_kwargs: Any) -> Any:
        never_set.wait()  # never set -> blocks forever
        raise AssertionError("unreachable")

    monkeypatch.setattr("specify_cli.analysis_report.write_analysis_report", _hangs_forever)

    started = time.monotonic()
    _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)
    elapsed = time.monotonic() - started

    # A REAL enforced bound: comfortably under any sane CI-slowness margin,
    # nowhere near "the mocked call eventually returned" (it never does).
    assert_timing_budget(elapsed, 5.0, name="record-analysis enforced hang bound")


# ---------------------------------------------------------------------------
# SC-005(c) -- stale-but-coincidentally-matching-verdict (SPEC-VERIFY-001)
# ---------------------------------------------------------------------------


def test_record_analysis_sc005c_stale_matching_verdict_reports_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-scenario-sc005c")

    # Pre-seed a STALE analysis-report.md whose verdict happens to equal what
    # THIS call will submit ("ready"), but whose generated_at is ancient --
    # long before this test's call-start.
    stale_content = (
        "---\n"
        "schema_version: 1\n"
        "artifact_type: spec-kitty.analysis-report\n"
        "command: /spec-kitty.analyze\n"
        f"mission_slug: {mission_slug}\n"
        "mission_id: null\n"
        "generated_at: '2001-01-01T00:00:00+00:00'\n"
        "analyzer_agent: unknown\n"
        "input_artifacts: {}\n"
        "verdict: ready\n"
        "issue_counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
        "findings: []\n"
        "---\n\n"
        "# Stale pre-existing report\n"
    )
    (feature_dir / "analysis-report.md").write_text(stale_content, encoding="utf-8")
    # Commit the pre-seeded stale artifact so the ONLY thing exercised here is
    # the re-read/correlate logic -- not an incidental dirty-tree refusal.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "pre-seed stale analysis report")

    def _fails_before_writing(**_kwargs: Any) -> Any:
        raise RuntimeError("simulated early-exit failure before write_analysis_report")

    monkeypatch.setattr("specify_cli.analysis_report.write_analysis_report", _fails_before_writing)

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "RECORD_ANALYSIS_WRITE_NOT_CONFIRMED"
    # The stale file is untouched -- verdict-string equality alone (both are
    # "ready") must NOT have been treated as sufficient evidence.
    on_disk = (feature_dir / "analysis-report.md").read_text(encoding="utf-8")
    assert "2001-01-01T00:00:00+00:00" in on_disk


# ---------------------------------------------------------------------------
# PR-TESTS-003 (severity 3, R3-confirmed genuine coverage gap; production
# verified correct by the refuter's own independent repro): record-analysis's
# three preflight fail-closed branches ahead of the write itself --
# ``RECORD_ANALYSIS_MALFORMED_CARRIER``, ``PLACEMENT_RESOLUTION_REQUIRED``,
# and ``DIRTY_WORKTREE`` -- had zero test coverage. The five pre-existing
# ``test_record_analysis_*`` tests all submit well-formed carriers against
# clean, resolvable worktrees; none of these three branches was reached.
# ---------------------------------------------------------------------------


def test_record_analysis_malformed_carrier_fails_closed(tmp_path: Path) -> None:
    """An unparseable ``analysis-findings/v1`` carrier (opening ``---`` with
    no closing ``---``) must surface ``RECORD_ANALYSIS_MALFORMED_CARRIER``,
    never propagate a bare parse exception or silently write anyway."""
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-tests003-carrier")

    malformed_body = "---\nschema: analysis-findings/v1\nfindings: [\n"
    envelope = _record_analysis(repo, mission_slug, malformed_body, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "RECORD_ANALYSIS_MALFORMED_CARRIER", envelope
    assert not (feature_dir / "analysis-report.md").exists()


def test_record_analysis_placement_resolution_required_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unresolvable write placement (``PlacementResolutionRequired``) must
    surface ``PLACEMENT_RESOLUTION_REQUIRED`` -- a typed-exception pass-
    through, never a bare crash or a silent fall-through to the write."""
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-tests003-placement")

    import specify_cli.cli.commands.agent.mission_record_analysis as host_ra_module
    from specify_cli.core.errors import PlacementResolutionRequired

    def _raises_placement_required(placement_ref: object, *, mission_slug: str) -> object:
        raise PlacementResolutionRequired(f"simulated unresolvable placement for mission {mission_slug!r}")

    monkeypatch.setattr(host_ra_module, "_require_record_analysis_placement", _raises_placement_required)

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PLACEMENT_RESOLUTION_REQUIRED", envelope
    assert not (feature_dir / "analysis-report.md").exists()


def test_record_analysis_dirty_worktree_fails_closed_with_well_formed_body(
    tmp_path: Path,
) -> None:
    """A pre-existing dirty worktree must refuse with ``DIRTY_WORKTREE`` even
    with an otherwise well-formed, non-empty body -- isolated from
    PR-CONTRACT-001's ordering fix (which also covers the dirty+EMPTY-body
    combination) by submitting a genuinely valid carrier here, so this test
    exercises the dirty-tree preflight branch specifically, not the
    ordering question."""
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_mission(repo, "wp04-tests003-dirty")

    (repo / "untracked-dirty-marker.txt").write_text("dirt\n", encoding="utf-8")
    status = _git(repo, "status", "--porcelain").stdout
    assert "untracked-dirty-marker.txt" in status, "fixture setup failed to dirty the tree"

    envelope = _record_analysis(repo, mission_slug, _CARRIER_READY, tmp_path=tmp_path)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "DIRTY_WORKTREE", envelope
    assert not (feature_dir / "analysis-report.md").exists()
