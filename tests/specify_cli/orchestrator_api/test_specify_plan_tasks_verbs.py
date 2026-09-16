"""WP03 (design-phase-orchestrator-api-01M1HE6M) — ``specify``/``plan``/
``tasks`` orchestrator-api verbs (FR-001/002/003).

Acceptance scenarios (see
``kitty-specs/design-phase-orchestrator-api-01M1HE6M/tasks/WP03-specify-plan-tasks-verbs.md``):

1. ``specify --mission-type <type> --mission <slug> --policy <...>`` against a
   scratch project with no existing mission → ``success: true`` and the
   ENRICHED ``data`` shape (``scaffold_only``/``spec_state``/``next_action``/
   ``next_step`` plus mission identity + ``spec_file``) — the enrichment
   ``lifecycle._create_mission_for_specify_json`` adds on top of
   ``agent_feature.create_mission``'s raw payload (Clarification 1).
2. ``plan --mission <slug> --policy <...>`` against an already-``specify``'d
   mission (with a substantive, committed spec.md) → ``data.plan_file`` and
   the file exists on disk. NOTE: the WP prompt's own prose calls this field
   ``plan_path``; the real, verified ``agent_feature.setup_plan(...,
   json_output=True)`` payload key is ``plan_file`` (confirmed against
   production by direct invocation during implementation) — asserting on the
   real key is the genuine "unenriched pass-through" contract T011 requires;
   asserting on a field that does not exist would not be a meaningful test.
3. ``tasks --mission <slug> --policy <...>`` against a mission with a
   completed ``tasks/`` dir → the finalized WP-manifest shape
   (``wp_count``/``modified_wps``) matches
   ``agent_feature.finalize_tasks(..., json_output=True)``'s own shape.
4. ``specify`` called twice for the same slug → ``success: false`` with a
   structured ``error_code`` (never a bare exception), and the FIRST mission
   directory's ``meta.json`` is unchanged.

This is the RED-then-GREEN ATDD anchor (charter C-011): pre-implementation,
none of ``specify``/``plan``/``tasks`` exist as ``@app.command``s on
``orchestrator_api.commands.app``, so every scenario below fails at the
Typer "no such command" / non-zero-exit level.

Real mission scaffolding (real files under ``kitty-specs/<slug>/``, real git
commits via ``create_mission``/``setup_plan``/``finalize_tasks``) — hence
``integration``/``git_repo`` (NOT ``fast``, per this repo's own
``pytest.ini:25`` definition reserving ``fast`` for no-subprocess/no-git
tests), mirroring ``test_transition_subtask_gate.py``'s precedent.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from tests._factories import provision_test_charter

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

_SUBSTANTIVE_SPEC = """# Spec — WP03 verbs

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Do the thing | Users can do the thing end to end. | High | Open |

## User Scenarios
A user does the thing via the orchestrator-api.
"""

# Fold-in review finding -- the exact ``data`` key-set each verb's success
# envelope re-emits verbatim from its host-CLI delegate (docs/api/
# orchestrator-api.md's "Design-Phase Commands" section: ``specify`` =
# ``agent_feature.create_mission``'s raw payload plus the enrichment
# ``scaffold_only``/``spec_state``/``next_action``/``next_step``; ``plan`` =
# ``agent_feature.setup_plan``'s raw payload verbatim, ``mission_slug``
# filled in only if absent; ``tasks`` = ``agent_feature.finalize_tasks``'s
# raw payload verbatim, ``mission_slug`` always filled in). Captured against
# a real, live invocation (NOT re-derived from the implementation) so a
# future delegate ``--json`` shape change trips this test instead of
# silently mutating the versioned external contract (1.5.0 after the additive
# ``planning_commit`` object, #4141; 1.4.0 before it).
_SPECIFY_SUCCESS_DATA_KEYS = frozenset(
    {
        "BASE_BRANCH",
        "BRANCH_MATCHES_TARGET",
        "CURRENT_BRANCH",
        "EXPECTED_BASE_BRANCH",
        "EXPECTED_TARGET_BRANCH",
        "MERGE_TARGET_BRANCH",
        "NOW_UTC_ISO",
        "PLANNING_BASE_BRANCH",
        "TARGET_BRANCH",
        "base_branch",
        "branch_context",
        "branch_matches_target",
        "branch_strategy_summary",
        "coordination_branch",
        "coordination_branch_created",
        "created_at",
        "created_files",
        "current_branch",
        "feature_dir",
        "friendly_name",
        "merge_target_branch",
        "meta_file",
        "mission_id",
        "mission_number",
        "mission_slug",
        "mission_type",
        "next_action",
        "next_step",
        "origin_binding",
        "plan_guard",
        "planning_base_branch",
        "purpose_context",
        "purpose_tldr",
        "requires_agent_authoring",
        "result",
        "runtime_vars",
        "scaffold_only",
        "slug",
        "spec_file",
        "spec_kitty_version",
        "spec_state",
        "target_branch",
        "topology",
        "uncommitted_artifacts",
        "write_mode",
    }
)

_PLAN_SUCCESS_DATA_KEYS = frozenset(
    {
        "BASE_BRANCH",
        "BRANCH_MATCHES_TARGET",
        "CURRENT_BRANCH",
        "EXPECTED_BASE_BRANCH",
        "EXPECTED_TARGET_BRANCH",
        "MERGE_TARGET_BRANCH",
        "NOW_UTC_ISO",
        "PLANNING_BASE_BRANCH",
        "TARGET_BRANCH",
        "base_branch",
        "branch_context",
        "branch_matches_target",
        "branch_strategy_summary",
        "current_branch",
        "feature_dir",
        "merge_target_branch",
        "mission_slug",
        "phase_complete",
        "plan_file",
        "plan_substantive",
        "planning_base_branch",
        "result",
        "runtime_vars",
        "scaffold_only",
        "spec_file",
        "spec_kitty_version",
        "target_branch",
    }
)

_TASKS_SUCCESS_DATA_KEYS = frozenset(
    {
        "bootstrap",
        "commit_created",
        "commit_hash",
        "commit_hashes",
        "dependencies_parsed",
        "files_committed",
        "lanes",
        "mission_slug",
        "modified_wps",
        "ownership_warnings",
        "planning_commit",
        "post_integration_acceptance_warnings",
        "preserved_wps",
        "requirement_extraction_warnings",
        "requirement_refs_parsed",
        "result",
        "spec_kitty_version",
        "target_branch_override",
        "tasks_dir",
        "unchanged_wps",
        "updated_wp_count",
        "wp_count",
    }
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    """A real, non-protected-branch git repo with an activated mission type.

    Branch name deliberately not ``main``/``master`` (the default protected
    set, ``specify_cli/git/protection_policy.py``) so the mission-creation
    commits this test drives for real are never refused by the protected-
    branch guard — no ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` escape
    hatch needed.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "wp03-work"], cwd=repo, check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    provision_test_charter(repo)
    return repo


def _run(repo: Path, args: list[str]) -> Result:
    """Invoke the real orchestrator-api ``app`` with cwd pinned at ``repo``.

    ``specify``/``plan``/``tasks`` resolve their project root and mission dir
    via real filesystem discovery (``locate_project_root`` /
    ``_get_main_repo_root``), so — unlike the lighter fail-closed suites —
    this drives the genuine end-to-end path with no ``_get_main_repo_root``
    patch.
    """
    import os

    prev_cwd = Path.cwd()
    os.chdir(repo)
    try:
        return runner.invoke(app, args, catch_exceptions=False)
    finally:
        os.chdir(prev_cwd)


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


# ---------------------------------------------------------------------------
# Acceptance Scenario 1 — specify: enriched scaffold-state shape
# ---------------------------------------------------------------------------


def test_specify_creates_mission_with_enriched_scaffold_state(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    envelope = _specify(repo, "wp03-scenario1")

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]
    # The enriched shape Clarification 1 requires — NOT the raw create_mission
    # payload one layer beneath it.
    assert data["scaffold_only"] is True
    assert data["spec_state"] == "scaffold_only"
    assert "next_action" in data and data["next_action"]
    assert data["next_step"] == data["next_action"]
    # Mission identity + spec.md path, present on the raw payload too.
    assert data["mission_slug"].startswith("wp03-scenario1-")
    spec_file = Path(data["spec_file"])
    assert spec_file.name == "spec.md"
    assert spec_file.exists()
    feature_dir = Path(data["feature_dir"])
    assert feature_dir.is_dir()
    assert (feature_dir / "meta.json").exists()


def test_specify_success_data_carries_mission_slug_even_if_delegate_omits_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fold-in review finding: unlike ``plan``/``tasks``/
    ``check_prerequisites`` (each ``setdefault``s ``mission_slug`` from the
    resolved mission identity), ``specify`` relied entirely on the delegate
    payload carrying the field -- a delegate payload missing it would
    otherwise reach ``validate_outbound_payload`` and raise an un-enveloped
    ``ContractViolationError`` on the success path.

    Drives the REAL mission creation (so the mid8-suffixed canonical slug
    genuinely exists on disk) but strips ``mission_slug`` from the
    intercepted JSON payload before it reaches ``specify()``, forcing the
    fallback resolution path -- and asserting that fallback recovers the
    real, mid8-suffixed slug, not the raw pre-suffix ``--mission`` input.
    """
    import contextlib
    import io

    repo = _init_repo(tmp_path)

    import specify_cli.cli.commands.lifecycle as lifecycle_module

    real_create = lifecycle_module._create_mission_for_specify_json

    def _omit_mission_slug(mission: str, mission_type: str, topology: object) -> None:
        inner_capture = io.StringIO()
        with contextlib.redirect_stdout(inner_capture):
            real_create(mission, mission_type, topology)
        payload = json.loads(inner_capture.getvalue().strip().split("\n")[0])
        del payload["mission_slug"]
        print(json.dumps(payload))

    monkeypatch.setattr(lifecycle_module, "_create_mission_for_specify_json", _omit_mission_slug)

    envelope = _specify(repo, "wp03-missing-slug")

    assert envelope["success"] is True, envelope
    data = envelope["data"]
    assert data["mission_slug"].startswith("wp03-missing-slug-")
    # The real, mid8-suffixed slug -- not the raw pre-suffix --mission input.
    assert data["mission_slug"] != "wp03-missing-slug"
    feature_dir = Path(data["feature_dir"])
    assert (feature_dir / "meta.json").exists()


# ---------------------------------------------------------------------------
# Acceptance Scenario 2 — plan: unenriched pass-through of setup_plan
# ---------------------------------------------------------------------------


def test_plan_scaffolds_plan_md_as_raw_pass_through(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    created = _specify(repo, "wp03-scenario2")
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]

    # Author + commit a substantive spec so setup_plan proceeds past the
    # committed-and-substantive gate (mirrors test_specify_plan_commit_boundary.py).
    spec_file = Path(created["data"]["spec_file"])
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "substantive spec")

    result = _run(
        repo,
        ["plan", "--mission", mission_slug, "--policy", _POLICY],
    )
    envelope = _envelope(result)

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]
    # Real, verified setup_plan() payload key (see module docstring note 2).
    assert "plan_file" in data, data
    plan_file = Path(data["plan_file"])
    assert plan_file.name == "plan.md"
    assert plan_file.exists()
    # Transport-contract identity field (upstream_contract.json's
    # required_payload_fields) -- filled from the resolved input, not
    # business-payload enrichment (see commands.py comment).
    assert data["mission_slug"] == mission_slug
    # Unenriched pass-through: no specify-only fields leaked onto plan's data.
    assert "scaffold_only" in data  # setup_plan's OWN field, not specify's enrichment
    assert "spec_state" not in data
    assert "next_action" not in data


# ---------------------------------------------------------------------------
# Acceptance Scenario 3 — tasks: unenriched pass-through of finalize_tasks
# ---------------------------------------------------------------------------


def test_tasks_finalizes_wp_manifest_as_raw_pass_through(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    created = _specify(repo, "wp03-scenario3")
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

    result = _run(repo, ["tasks", "--mission", mission_slug, "--policy", _POLICY])
    envelope = _envelope(result)

    assert envelope["success"] is True, envelope
    assert envelope["error_code"] is None
    data = envelope["data"]
    # Real finalize_tasks() shape — WP count + modified-WP roster.
    assert data["wp_count"] == 1
    assert data["modified_wps"] == ["WP01"]
    # Same transport-contract identity fill as plan (finalize_tasks' raw
    # payload genuinely lacks mission_slug -- verified against production).
    assert data["mission_slug"] == mission_slug
    # Unenriched pass-through: no specify-only fields leaked here either.
    assert "scaffold_only" not in data
    assert "spec_state" not in data


# ---------------------------------------------------------------------------
# Acceptance Scenario 4 — specify twice: structured duplicate-mission failure
# ---------------------------------------------------------------------------


def test_specify_twice_for_same_slug_fails_closed_with_structured_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second ``specify`` call for the identical slug must NOT succeed silently
    and must NOT propagate a bare exception/traceback — it must fail closed
    with a structured ``error_code``, leaving the first mission's meta.json
    byte-identical (never a silent overwrite).

    Ground truth (verified during implementation by direct invocation): a
    second ``create_mission`` call for the same slug that regenerates
    byte-identical scaffold content (same minted ``mission_id`` -> same
    ``mid8`` -> same directory, same ``created_at``) makes the underlying
    ``safe_commit`` see an empty changeset and raise -- this is the
    "already-established duplicate-mission error" the WP prompt refers to;
    classifying it into a stable ``error_code`` (rather than letting the bare
    ``{"error": ...}`` propagate uncoded) is this WP's job.

    ``mission_id`` is minted from a real ULID (``str(ULID())``,
    ``mission_creation.py:666``), whose first-8-char ``mid8`` prefix is
    timestamp-derived at ~256ms granularity -- colliding it by real-time
    proximity alone was observed to be FLAKY (two back-to-back calls through
    the full create_mission pipeline, with real git I/O between them, land in
    different 256ms buckets often enough to matter). Freeze both entropy
    sources the scaffold content depends on (``ULID`` mint + ``created_at``)
    so the collision is deterministic on every run, not a timing bet.
    """
    from ulid import ULID

    frozen_mission_id = ULID()
    monkeypatch.setattr("specify_cli.core.mission_creation.ULID", lambda: frozen_mission_id)
    monkeypatch.setattr(
        "specify_cli.core.mission_creation.now_utc_iso",
        lambda: "2026-01-01T00:00:00+00:00",
    )

    repo = _init_repo(tmp_path)

    first = _specify(repo, "wp03-scenario4")
    assert first["success"] is True, first
    feature_dir = Path(first["data"]["feature_dir"])
    meta_before = (feature_dir / "meta.json").read_text(encoding="utf-8")

    second = _specify(repo, "wp03-scenario4")

    assert second["success"] is False, second
    assert second["error_code"] is not None
    assert second["error_code"] != ""
    # #3861: the duplicate refusal arrives as the delegate's TYPED
    # ``MissionAlreadyExistsError`` signal (emitted by the #4033 guard, the
    # first refusal a frozen-``mission_id`` re-run hits), carried through the
    # ``--json`` error payload as ``error_code`` -- pinned here so a future
    # message-wording change in the delegate can never flip the reported
    # failure code.
    assert second["error_code"] == "MISSION_ALREADY_EXISTS"
    # Never a bare unstructured exception surface.
    assert "message" in second["data"]

    # The first mission directory is untouched.
    assert feature_dir.exists()
    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == meta_before


# ---------------------------------------------------------------------------
# PR-TESTS-001 (severity 3, R3-confirmed genuine coverage gap; production
# verified correct by the refuter's own independent repro): specify/plan/
# tasks' delegate-failure fallback codes (MISSION_CREATE_FAILED/
# PLAN_SETUP_FAILED/TASKS_FINALIZE_FAILED) had ZERO test coverage -- the
# only existing failure test (Scenario 4 above) exercises a DIFFERENT
# branch (the duplicate-marker pattern match), never the generic
# ``except typer.Exit`` fallback any of the three verbs falls back to when
# the delegate raises with no parseable/typed JSON payload on stdout.
# ---------------------------------------------------------------------------


def test_specify_delegate_typer_exit_with_no_json_falls_back_to_mission_create_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """specify()'s generic (non-duplicate, no-payload) fallback branch --
    distinct from ``test_specify_twice_for_same_slug_fails_closed_with_
    structured_error`` above, which drives the DUPLICATE-marker branch of
    the SAME classify function, never this one.
    """
    repo = _init_repo(tmp_path)

    import specify_cli.cli.commands.lifecycle as lifecycle_module

    def _raises_non_json(mission: str, mission_type: str, topology: object) -> None:
        print("totally not json, a bare stderr-shaped failure")
        raise typer.Exit(1)

    monkeypatch.setattr(lifecycle_module, "_create_mission_for_specify_json", _raises_non_json)

    envelope = _specify(repo, "wp03-tests001-specify")

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "MISSION_CREATE_FAILED"


def test_plan_delegate_typer_exit_with_no_json_falls_back_to_plan_setup_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """plan()'s ``except typer.Exit`` fallback branch -- never previously
    driven by any test in this suite (grep confirms zero hits for
    ``PLAN_SETUP_FAILED`` anywhere under ``tests/``)."""
    repo = _init_repo(tmp_path)
    created = _specify(repo, "wp03-tests001-plan")
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]

    spec_file = Path(created["data"]["spec_file"])
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "substantive spec")

    import specify_cli.cli.commands.agent.mission as agent_mission_module

    def _raises_non_json(*, feature: str, json_output: bool) -> None:
        print("totally not json, a bare stderr-shaped failure")
        raise typer.Exit(1)

    monkeypatch.setattr(agent_mission_module, "setup_plan", _raises_non_json)

    result = _run(repo, ["plan", "--mission", mission_slug, "--policy", _POLICY])
    envelope = _envelope(result)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PLAN_SETUP_FAILED"


def test_tasks_delegate_typer_exit_with_no_json_falls_back_to_tasks_finalize_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """tasks()'s ``except typer.Exit`` fallback branch -- never previously
    driven by any test in this suite (grep confirms zero hits for
    ``TASKS_FINALIZE_FAILED`` anywhere under ``tests/``)."""
    repo = _init_repo(tmp_path)
    created = _specify(repo, "wp03-tests001-tasks")
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]

    spec_file = Path(created["data"]["spec_file"])
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "substantive spec")

    plan_result = _run(repo, ["plan", "--mission", mission_slug, "--policy", _POLICY])
    plan_envelope = _envelope(plan_result)
    assert plan_envelope["success"] is True, plan_envelope

    import specify_cli.cli.commands.agent.mission as agent_mission_module

    def _raises_non_json(*, feature: str, json_output: bool) -> None:
        print("totally not json, a bare stderr-shaped failure")
        raise typer.Exit(1)

    monkeypatch.setattr(agent_mission_module, "finalize_tasks", _raises_non_json)

    result = _run(repo, ["tasks", "--mission", mission_slug, "--policy", _POLICY])
    envelope = _envelope(result)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "TASKS_FINALIZE_FAILED"


# ---------------------------------------------------------------------------
# Fold-in review finding -- pin the pass-through data shape
# ---------------------------------------------------------------------------


def test_specify_plan_tasks_success_data_key_shape_is_pinned(tmp_path: Path) -> None:
    """``specify``/``plan``/``tasks`` re-emit their host-CLI delegate's
    ``--json`` dict verbatim as the versioned (now 1.5.0) contract ``data`` --
    nothing pins that shape to the contract version, so a delegate
    ``--json`` change would otherwise silently mutate the external contract
    with no test ever failing. Assert the exact key-SET (not values -- git
    branch names/timestamps/hashes are environment-dependent) each verb's
    success ``data`` carries, so a future field added/removed/renamed on
    either delegate trips this test.
    """
    repo = _init_repo(tmp_path)
    created = _specify(repo, "wp03-pin-shape")
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]

    assert set(created["data"].keys()) == _SPECIFY_SUCCESS_DATA_KEYS

    spec_file = Path(created["data"]["spec_file"])
    spec_file.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "substantive spec")

    plan_result = _run(repo, ["plan", "--mission", mission_slug, "--policy", _POLICY])
    plan_envelope = _envelope(plan_result)
    assert plan_envelope["success"] is True, plan_envelope
    assert set(plan_envelope["data"].keys()) == _PLAN_SUCCESS_DATA_KEYS

    feature_dir = Path(created["data"]["feature_dir"])
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
    assert set(tasks_envelope["data"].keys()) == _TASKS_SUCCESS_DATA_KEYS
