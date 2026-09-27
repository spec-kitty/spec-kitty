"""WP06 (design-phase-orchestrator-api-01M1HE6M) -- ``design-status``
read-only query verb (FR-010, NFR-001/002/005).

Acceptance scenarios (see
``kitty-specs/design-phase-orchestrator-api-01M1HE6M/tasks/WP06-design-status-verb.md``,
spec User Story 4):

1. Only ``spec.md`` scaffolded -> ``data.current_phase: "specify"``,
   ``data.next_action`` names the ``plan`` verb.
2. An open, unresolved decision moment -> ``data.open_decisions`` lists it,
   ``data.next_action`` indicates resolution is required, REGARDLESS of
   which design phase the mission is otherwise in.
3. ``tasks/`` finalized, ``analysis-report.md`` absent ->
   ``data.current_phase``/``data.next_action`` indicate ``analyze`` is next,
   naming ``check-prerequisites``.
4. Idempotency (binding): two consecutive calls against an unchanged mission
   return BYTE-IDENTICAL ``current_phase``/``next_action`` fields, AND no
   new entry is appended to ``status.events.jsonl`` between the two calls --
   a stronger check than field-identity alone, proving no state transition
   and no event emission actually occurred (not merely "same-looking
   output").

Plus a torn/truncated-read regression test (ledger SK-131): ``design-status``
reads ``status.events.jsonl`` (via the SAME ``reduce(read_events(...))``
reduction ``list-ready`` already uses) to derive the tasks/-finalized signal.
Only 2 of 6 event-log writers take the feature status lock, and a rollback
TRUNCATES the log in place -- so the log is not reliably append-only. A torn
or truncated read must surface a structured ``DESIGN_STATUS_EVENT_LOG_UNREADABLE``
failure, never a silently wrong (but plausible-looking) ``current_phase``.

Clarification 6 (spec, binding, not re-derived here): ``design-status`` does
NOT delegate to ``resolve_next_workflow_action`` or
``decide_next``/``query_current_state`` -- it defines its own narrow
design-phase-only reduction over on-disk artifact presence and the
``decisions/index.json`` ledger, the same shape of deliberate narrowing
``list-ready`` already applies to WP state.

This is the RED-then-GREEN ATDD anchor (charter C-011): pre-implementation,
``design-status`` does not exist as an ``@app.command`` on
``orchestrator_api.commands.app``, so every scenario below fails at the
Typer "no such command" / non-zero-exit level.

Real mission scaffolding (real files under ``kitty-specs/<slug>/`` via the
``specify``/``plan``/``tasks``/``open-decision`` verbs -- WP03/WP05) -- hence
``integration``/``git_repo`` (NOT ``fast``), mirroring
``test_check_prerequisites_record_analysis.py``'s / ``test_decision_verbs.py``'s
precedent.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
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

_SUBSTANTIVE_SPEC = """# Spec — WP06 verbs

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Do the thing | Users can do the thing end to end. | High | Open |

## User Scenarios
A user does the thing via the orchestrator-api.
"""


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
    subprocess.run(["git", "init", "-b", "wp06-work"], cwd=repo, check=True, capture_output=True)
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


def _build_spec_only_mission(repo: Path, slug: str) -> tuple[str, Path]:
    """``specify`` a real mission -- ``spec.md`` scaffolded, nothing else.

    Returns ``(mission_slug, feature_dir)``.
    """
    created = _specify(repo, slug)
    assert created["success"] is True, created
    mission_slug = created["data"]["mission_slug"]
    feature_dir = Path(created["data"]["feature_dir"])
    return mission_slug, feature_dir


def _build_tasks_finalized_mission(repo: Path, slug: str) -> tuple[str, Path]:
    """Specify + plan + tasks a real mission, matching WP03/WP04's proven flow.

    Returns ``(mission_slug, feature_dir)``. The mission carries real,
    committed spec.md/plan.md/tasks.md, and finalize-tasks has bootstrapped
    canonical status for WP01 into status.events.jsonl -- ``analysis-report.md``
    is deliberately never written here.
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

    status = _git(repo, "status", "--porcelain").stdout
    if status.strip():
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "post-tasks bookkeeping")

    return mission_slug, feature_dir


def _open_decision(repo: Path, mission_slug: str) -> dict[str, Any]:
    result = _run(
        repo,
        [
            "open-decision",
            "--mission",
            mission_slug,
            "--origin",
            "specify",
            "--input-key",
            "team_size",
            "--question",
            "How many engineers?",
            "--step-id",
            "step-1",
            "--actor",
            "test-agent",
            "--policy",
            _POLICY,
        ],
    )
    return _envelope(result)


def _design_status(repo: Path, mission_slug: str) -> dict[str, Any]:
    result = _run(repo, ["design-status", "--mission", mission_slug])
    return _envelope(result)


# ---------------------------------------------------------------------------
# Acceptance Scenario 1 -- only spec.md scaffolded
# ---------------------------------------------------------------------------


def test_design_status_spec_only_reports_specify_phase(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_spec_only_mission(repo, "wp06-scenario1")

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is True, envelope
    data = envelope["data"]
    assert data["mission_slug"] == mission_slug
    assert data["current_phase"] == "specify"
    assert data["next_action"] == "plan"
    assert data["open_decisions"] == []


# ---------------------------------------------------------------------------
# Acceptance Scenario 2 -- an open, unresolved decision moment
# ---------------------------------------------------------------------------


def test_design_status_open_decision_blocks_regardless_of_phase(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, _feature_dir = _build_spec_only_mission(repo, "wp06-scenario2")
    opened = _open_decision(repo, mission_slug)
    assert opened["success"] is True, opened
    decision_id = opened["data"]["decision_id"]

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is True, envelope
    data = envelope["data"]
    assert data["open_decisions"] == [{"decision_id": decision_id, "origin": "specify"}]
    assert data["next_action"] == "resolve-decision"


# ---------------------------------------------------------------------------
# Acceptance Scenario 3 -- tasks/ finalized, analysis-report.md absent
# ---------------------------------------------------------------------------


def test_design_status_tasks_finalized_reports_analyze_next(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_tasks_finalized_mission(repo, "wp06-scenario3")
    assert not (feature_dir / "analysis-report.md").exists()

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is True, envelope
    data = envelope["data"]
    assert data["current_phase"] == "tasks"
    assert data["next_action"] == "check-prerequisites"
    assert data["open_decisions"] == []


# ---------------------------------------------------------------------------
# Acceptance Scenario 4 -- idempotency: no state transition, no event emission
# ---------------------------------------------------------------------------


def test_design_status_is_idempotent_and_emits_no_new_events(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_tasks_finalized_mission(repo, "wp06-scenario4")
    events_path = feature_dir / "status.events.jsonl"
    before = events_path.read_bytes() if events_path.exists() else b""

    first = _design_status(repo, mission_slug)
    after_first = events_path.read_bytes() if events_path.exists() else b""

    second = _design_status(repo, mission_slug)
    after_second = events_path.read_bytes() if events_path.exists() else b""

    assert first["success"] is True, first
    assert second["success"] is True, second
    assert first["data"]["current_phase"] == second["data"]["current_phase"]
    assert first["data"]["next_action"] == second["data"]["next_action"]

    # No new entry was appended between (or after) either call -- a
    # stronger proof of "no event emission" than output-field equality
    # alone (T031).
    assert after_first == before
    assert after_second == before


# ---------------------------------------------------------------------------
# Negative path -- nonexistent mission slug
# ---------------------------------------------------------------------------


def test_design_status_nonexistent_mission_is_structured_not_bare(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    envelope = _design_status(repo, "999-does-not-exist")

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Torn/truncated status.events.jsonl (ledger SK-131) -- a structured failure,
# never a silently wrong current_phase/next_action snapshot.
# ---------------------------------------------------------------------------


def test_design_status_torn_event_log_fails_closed_not_silently_wrong(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_tasks_finalized_mission(repo, "wp06-torn-read")
    events_path = feature_dir / "status.events.jsonl"
    assert events_path.exists()

    # Simulate an unlocked-writer race / rollback truncation landing mid-line
    # (SK-131): the last line is cut off mid-JSON-object, exactly the shape
    # `read_events`/`StoreError` is documented to reject.
    original = events_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    assert lines, "fixture must carry at least one bootstrapped WP event"
    torn_last_line = lines[-1][: max(1, len(lines[-1]) // 2)]
    torn_content = "\n".join([*lines[:-1], torn_last_line]) + "\n"
    events_path.write_text(torn_content, encoding="utf-8")

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"
    # Never silently reported as "tasks/ unfinalized" (a plausible-but-wrong
    # snapshot) -- the failure envelope carries no current_phase field at all.
    assert "current_phase" not in envelope["data"]


def test_design_status_clean_whole_line_truncation_fails_closed_not_silently_wrong(
    tmp_path: Path,
) -> None:
    """WP06-001 (review finding, severity 4): a CLEAN record-boundary
    truncation -- the trailing bootstrap ``planned`` event line dropped
    WHOLE, not torn mid-JSON -- is the ACTUAL shape
    ``coordination/transaction.py``'s ``_rollback`` produces
    (``fh.truncate(self._pre_emit_size)``, a byte-offset captured before the
    append began; the file is append-only, so truncating to that offset
    always lands on a line boundary). Every remaining line is still valid
    JSON, so ``read_events``/``StoreError`` never fires and the mid-line
    torn-read defense above (which DOES catch a half-written JSON object)
    never engages.

    Live-reproduced pre-fix: dropping the trailing ``planned`` event line
    whole from a real tasks-finalized mission's ``status.events.jsonl``
    made ``design-status`` return ``success: true``,
    ``current_phase: "plan"``, ``next_action: "tasks"`` -- silently WRONG
    (the mission genuinely has WP01 finalized), with no error and no hint
    anything is wrong. This is the "plausible-but-wrong snapshot" failure
    class this WP's own commit message and docstring claim to prevent, for
    the ONE concrete corruption mechanism (SK-131's cited
    ``transaction.py`` rollback) this WP was built to defend against.

    Fixed behaviour: a structural drift check compares the freshly
    event-log-derived ``work_packages`` set against ``status.json``'s own
    persisted set (the SAME ``SNAPSHOT_DRIFT`` concept ``status/store.py``
    already names for ``doctor mission-state --fix``, issue #1782, reused
    here rather than inventing a parallel one) -- when the persisted record
    knows about a WP the fresh reduction no longer sees, that is drift
    evidence, not "unfinalized", and the verb fails closed with the SAME
    structured ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` code the mid-line tear
    already uses.
    """
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_tasks_finalized_mission(repo, "wp06-clean-trunc")
    events_path = feature_dir / "status.events.jsonl"
    assert events_path.exists()
    assert (feature_dir / "status.json").exists(), (
        "finalize-tasks's own bootstrap_canonical_state must have materialized status.json for this drift check to have a persisted record to compare against"
    )

    # Precondition: BEFORE truncation, design-status correctly sees WP01
    # as finalized.
    before = _design_status(repo, mission_slug)
    assert before["success"] is True, before
    assert before["data"]["current_phase"] == "tasks"

    # A CLEAN whole-line drop of the trailing event -- the SAME shape
    # `_rollback`'s `fh.truncate(self._pre_emit_size)` produces (a byte
    # offset captured before the append, always landing on a line
    # boundary): every remaining line still parses as valid JSON.
    original = events_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    assert lines, "fixture must carry at least one bootstrapped WP event"
    truncated_content = "\n".join(lines[:-1])
    if truncated_content:
        truncated_content += "\n"
    events_path.write_text(truncated_content, encoding="utf-8")

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"
    # Never silently reported as "tasks/ unfinalized" (current_phase: "plan")
    # -- the failure envelope carries no current_phase field at all.
    assert "current_phase" not in envelope["data"]


# ---------------------------------------------------------------------------
# Fold-in review finding -- a corrupted decisions/index.json must fail
# closed with the SAME structured DESIGN_STATUS_EVENT_LOG_UNREADABLE
# envelope the torn status.events.jsonl shapes above already produce, never
# a bare traceback. ``_open_decisions`` -> ``decisions.store.load_index``
# (inside ``design_status``'s ``try``/``except StoreError`` block) can raise
# ``json.JSONDecodeError`` (malformed JSON text) or a pydantic
# ``ValidationError`` (JSON-valid but schema-invalid) -- NEITHER of which is
# a ``StoreError``, so pre-fix both propagated un-enveloped.
# ---------------------------------------------------------------------------


def test_design_status_malformed_decisions_index_json_fails_closed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_spec_only_mission(repo, "wp06-corrupt-index-a")

    opened = _open_decision(repo, mission_slug)
    assert opened["success"] is True, opened

    index_path = feature_dir / "decisions" / "index.json"
    assert index_path.exists()
    index_path.write_text("{not valid json", encoding="utf-8")

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"
    assert "current_phase" not in envelope["data"]


def test_design_status_schema_invalid_decisions_index_fails_closed(tmp_path: Path) -> None:
    """JSON-valid but schema-invalid (``version`` outside the ``Literal[1]``
    the model declares) -- the pydantic ``ValidationError`` branch, distinct
    from the malformed-JSON-text branch above.
    """
    repo = _init_repo(tmp_path)
    mission_slug, feature_dir = _build_spec_only_mission(repo, "wp06-corrupt-index-b")

    opened = _open_decision(repo, mission_slug)
    assert opened["success"] is True, opened

    index_path = feature_dir / "decisions" / "index.json"
    assert index_path.exists()
    index_path.write_text(
        json.dumps({"version": 2, "mission_id": "some-mission-id", "entries": []}),
        encoding="utf-8",
    )

    envelope = _design_status(repo, mission_slug)

    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"
    assert "current_phase" not in envelope["data"]
