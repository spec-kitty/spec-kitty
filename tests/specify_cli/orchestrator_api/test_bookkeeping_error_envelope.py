"""A ``BookkeepingError`` from a status transition must become a JSON envelope (#5642).

``start-implementation``, ``start-review`` and ``transition`` write status through
the transactional shell (``emit_status_transition_transactional`` /
``start_*_status``), which raises :class:`~specify_cli.coordination.transaction_errors.BookkeepingError`
subclasses -- a policy refusal, a lock timeout, a diverged coordination status
surface, a worktree that cannot be resolved. None of those is a
``TransitionError``, so before this slice they escaped every ``except`` arm as a
raw Python traceback with nothing on stdout.

The orchestrator-api contract is that *every* failure is one JSON envelope on
stdout with a stable ``error_code``. These tests inject one ``BookkeepingError``
per transition verb and assert the envelope, the documented envelope code and the
exception's own code in ``data``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.coordination.transaction_errors import BookkeepingLockTimeout
from specify_cli.orchestrator_api import _common
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4FBD"
_MID8 = _MISSION_ID[:8]
_HUMAN_SLUG = "bookkeeping-error-envelope"
_MISSION_SLUG = f"{_HUMAN_SLUG}-{_MID8}"

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
    (primary / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Example\ndependencies: []\n---\n\n## Activity Log\n\n- seed\n",
        encoding="utf-8",
    )
    return repo_root, primary


def _envelope(result) -> dict:
    """Parse the single JSON envelope on stdout, failing loudly on a traceback."""
    lines = [line for line in result.output.strip().splitlines() if line.strip()]
    assert lines, f"no stdout envelope (a traceback escaped): {result.exception!r}"
    return json.loads(lines[0])


def _assert_bookkeeping_envelope(result) -> None:
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "BOOKKEEPING_FAILED"
    assert envelope["data"]["bookkeeping_error_code"] == "BOOKKEEPING_LOCK_TIMEOUT"
    assert "lock" in envelope["data"]["message"].lower()


def test_transition_surfaces_a_bookkeeping_error_as_a_json_envelope(tmp_path: Path) -> None:
    repo_root, primary = _seed_mission(tmp_path)

    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo_root),
        patch.object(_common, "_resolve_mission_dir", return_value=primary),
        patch(
            "specify_cli.coordination.status_transition.emit_status_transition_transactional",
            side_effect=BookkeepingLockTimeout("status lock held by another writer past its bound"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "transition",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                "WP01",
                "--to",
                "in_progress",
                "--actor",
                "test-actor",
                "--policy",
                _POLICY,
            ],
            catch_exceptions=True,
        )

    _assert_bookkeeping_envelope(result)
    assert result.exit_code != 0


def test_start_implementation_surfaces_a_bookkeeping_error_as_a_json_envelope(tmp_path: Path) -> None:
    """The composite ``start-implementation`` claim path (#5642).

    Its pre-steps are stubbed at their own seams (the write-checkout claim lock,
    lane allocation, the ancestry gate, the reused-lane context refresh) so the
    test exercises the one thing under test: the ``BookkeepingError`` arm around
    the status write itself.
    """
    from specify_cli.orchestrator_api import wp_lifecycle

    repo_root, primary = _seed_mission(tmp_path)
    workspace = wp_lifecycle._StartWorkspace(workspace_path=str(tmp_path / "workspace"))

    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo_root),
        patch.object(_common, "_resolve_mission_dir", return_value=primary),
        patch.object(wp_lifecycle, "_enter_checkout_claim_lock"),
        patch.object(wp_lifecycle, "_resolve_start_workspace", return_value=workspace),
        patch.object(wp_lifecycle, "_enforce_claim_ancestry"),
        patch("specify_cli.lanes.implement_support.refresh_reused_lane_context", return_value=False),
        patch(
            "specify_cli.status.start_implementation_status",
            side_effect=BookkeepingLockTimeout("status lock held by another writer past its bound"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                "WP01",
                "--actor",
                "test-actor",
                "--policy",
                _POLICY,
            ],
            catch_exceptions=True,
        )

    _assert_bookkeeping_envelope(result)
    assert result.exit_code != 0


def test_start_review_surfaces_a_bookkeeping_error_as_a_json_envelope(tmp_path: Path) -> None:
    repo_root, primary = _seed_mission(tmp_path)

    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo_root),
        patch.object(_common, "_resolve_mission_dir", return_value=primary),
        patch(
            "specify_cli.status.start_review_status",
            side_effect=BookkeepingLockTimeout("status lock held by another writer past its bound"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "start-review",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                "WP01",
                "--actor",
                "test-reviewer",
                "--policy",
                _POLICY,
            ],
            catch_exceptions=True,
        )

    _assert_bookkeeping_envelope(result)
    assert result.exit_code != 0
