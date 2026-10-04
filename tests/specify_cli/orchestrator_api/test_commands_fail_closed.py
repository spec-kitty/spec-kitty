"""Fail-closed regressions for ``orchestrator_api/commands.py``.

WP08 (runtime-state-eviction, FR-007 / T031): ``append-history`` emits a
``note`` ``InnerStateChanged`` annotation instead of committing a WP-file edit,
so the former WP prompt-file history-commit placement resolver (and its FR-004
fail-closed unit tests) was deleted with its last caller. What remains pinned
here is the command's *current* structured-envelope contract: a failed emit
still returns ``_fail(...)``'s JSON error, never a bare traceback.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api import _common
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4FBD"
_MID8 = _MISSION_ID[:8]
_HUMAN_SLUG = "fail-closed-history-commit"
_MISSION_SLUG = f"{_HUMAN_SLUG}-{_MID8}"


def _seed_mission(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal, realistic primary mission dir carrying one WP prompt file."""
    repo_root = tmp_path / "repo"
    primary = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "slug": _MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "status_phase": 2,
    }
    (primary / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Example\ndependencies: []\n---\n\n"
        "## Activity Log\n\n- seed\n",
        encoding="utf-8",
    )
    return repo_root, primary


def test_append_history_surfaces_structured_error_code_on_emit_failure(
    tmp_path: Path,
) -> None:
    """End-to-end (WP08 / T031): a failed ``InnerStateChanged`` emit still
    surfaces the orchestrator-api's own structured ``HISTORY_COMMIT_FAILED``
    envelope -- never a bare traceback -- even though ``append-history`` no
    longer routes through a WP-file-commit placement seam at all (see the
    module docstring).
    """
    repo_root, _primary = _seed_mission(tmp_path)

    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo_root),
        patch(
            # WP02 (verdict-seam-boundary-hardening-01KZG179, T006): the
            # command now resolves this via ``from specify_cli.status import
            # emit_inner_state_changed`` (the facade symbol), not the
            # ``status.emit`` submodule object, so the mock target moves to
            # the facade's own already-bound attribute.
            "specify_cli.status.emit_inner_state_changed",
            side_effect=ValueError("boom"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "append-history",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                "WP01",
                "--actor",
                "test-actor",
                "--note",
                "attempted history append",
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "HISTORY_COMMIT_FAILED"


# ---------------------------------------------------------------------------
# WP03 (design-phase-orchestrator-api-01M1HE6M / T013): specify/plan/tasks
# fail-closed policy gates. Pure in-process CliRunner invocations -- the
# --policy check runs BEFORE any mission resolution in all three verbs, so
# no mission fixture / _get_main_repo_root patch is needed (consistent with
# this file's ``fast`` marker: no subprocess, no real git I/O).
# ---------------------------------------------------------------------------


def test_specify_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["specify", "--mission", "wp03-missing-policy", "--mission-type", "software-dev"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_plan_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["plan", "--mission", "wp03-missing-policy"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_tasks_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["tasks", "--mission", "wp03-missing-policy"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_specify_invalid_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "specify",
            "--mission",
            "wp03-invalid-policy",
            "--mission-type",
            "software-dev",
            "--policy",
            "{}",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_VALIDATION_FAILED"


def test_plan_invalid_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["plan", "--mission", "wp03-invalid-policy", "--policy", "{}"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_VALIDATION_FAILED"


def test_tasks_invalid_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["tasks", "--mission", "wp03-invalid-policy", "--policy", "{}"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# WP04 (design-phase-orchestrator-api-01M1HE6M / T015): record-analysis
# fail-closed policy gates. Pure in-process CliRunner invocations -- the
# --policy check runs BEFORE any mission resolution (matching
# specify/plan/tasks above), so no mission fixture / _get_main_repo_root
# patch is needed. ``check-prerequisites`` is deliberately absent here: it is
# a read-only verb and takes no --policy at all (spec Edge Cases).
# ---------------------------------------------------------------------------


def test_record_analysis_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["record-analysis", "--mission", "wp04-missing-policy"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_record_analysis_invalid_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        ["record-analysis", "--mission", "wp04-invalid-policy", "--policy", "{}"],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# WP05 (design-phase-orchestrator-api-01M1HE6M / T027): open-decision/
# resolve-decision/defer-decision/cancel-decision fail-closed gates. Pure
# in-process CliRunner invocations -- the --policy check (and, for
# open-decision, the FR-012 --origin scope guard) run BEFORE any mission
# resolution, matching specify/plan/tasks/record-analysis above, so no
# mission fixture / _get_main_repo_root patch is needed for those cases.
# The nonexistent-decision-id case DOES need a real (non-git) mission dir --
# ``_seed_wp05_mission`` below mirrors this file's own ``_seed_mission``
# pattern but adds ``mission_id`` (decisions/service.py hard-requires it;
# WP04's verbs never read it).
# ---------------------------------------------------------------------------

_WP05_MISSION_SLUG = "wp05-fail-closed-mission"
_WP05_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4WP5"


def _seed_wp05_mission(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal, real (non-git) mission dir carrying a ``mission_id``."""
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / _WP05_MISSION_SLUG
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": _WP05_MISSION_ID,
        "mission_slug": _WP05_MISSION_SLUG,
        "slug": _WP05_MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "status_phase": 2,
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return repo_root, mission_dir


def test_open_decision_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "open-decision",
            "--mission",
            "wp05-missing-policy",
            "--origin",
            "specify",
            "--input-key",
            "k",
            "--question",
            "q?",
            "--step-id",
            "s1",
            "--actor",
            "test-agent",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_resolve_decision_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "resolve-decision",
            "--mission",
            "wp05-missing-policy",
            "--decision-id",
            "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "--final-answer",
            "5",
            "--actor",
            "test-agent",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_defer_decision_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "defer-decision",
            "--mission",
            "wp05-missing-policy",
            "--decision-id",
            "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "--rationale",
            "need more info",
            "--actor",
            "test-agent",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_cancel_decision_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "cancel-decision",
            "--mission",
            "wp05-missing-policy",
            "--decision-id",
            "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "--rationale",
            "no longer relevant",
            "--actor",
            "test-agent",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"


def test_open_decision_invalid_origin_is_structured_not_bare() -> None:
    """FR-012: an --origin outside {charter, specify, plan} is rejected
    BEFORE mission resolution -- no mission fixture needed here either.
    """
    result = runner.invoke(
        app,
        [
            "open-decision",
            "--mission",
            "wp05-invalid-origin",
            "--origin",
            "analyze",
            "--input-key",
            "k",
            "--question",
            "q?",
            "--step-id",
            "s1",
            "--actor",
            "test-agent",
            "--policy",
            json.dumps(
                {
                    "orchestrator_id": "test-orch",
                    "orchestrator_version": "0.0.1",
                    "agent_family": "claude",
                    "approval_mode": "full_auto",
                    "sandbox_mode": "workspace_write",
                    "network_mode": "none",
                    "dangerous_flags": [],
                }
            ),
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "INVALID_ORIGIN_FLOW"


def test_resolve_decision_nonexistent_decision_id_is_structured_not_bare(
    tmp_path: Path,
) -> None:
    """A --decision-id naming a decision absent from the ledger fails closed
    with the service layer's own DECISION_NOT_FOUND -- never a bare
    exception or a silent no-op success.
    """
    repo_root, _mission_dir = _seed_wp05_mission(tmp_path)

    with patch.object(_common, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "resolve-decision",
                "--mission",
                _WP05_MISSION_SLUG,
                "--decision-id",
                "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "--final-answer",
                "5",
                "--actor",
                "test-agent",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "DECISION_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP08 (design-phase-orchestrator-api-01M1HE6M): ``answer-decision``'s own
# ``--policy`` fail-closed gate -- same pattern as the WP05 decision verbs
# above (the policy check runs BEFORE any mission resolution, so no mission
# fixture is needed).
# ---------------------------------------------------------------------------


def test_answer_decision_missing_policy_is_structured_not_bare() -> None:
    result = runner.invoke(
        app,
        [
            "answer-decision",
            "--mission",
            "wp08-missing-policy",
            "--agent",
            "test-agent",
            "--answer",
            "approve",
            "--result",
            "success",
        ],
        catch_exceptions=False,
    )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "POLICY_METADATA_REQUIRED"
