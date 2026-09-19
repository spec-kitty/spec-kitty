"""#2899 pre-PR squad (HIGH): decision write verbs must route
``DecisionEventLogReadError`` through the JSON error envelope.

WP07 hardened ``decisions/service.py::_opened_event_exists`` to raise
``DecisionEventLogReadError`` (a ``GuardedReadError``) when
``status.events.jsonl`` exists but cannot be decoded. That helper is reached
from ``open_decision`` -> ``_repair_missing_opened_event`` ->
``_opened_event_exists`` on the idempotent re-open path (an existing,
non-terminal decision is looked up again).

Pre-fix, the four orchestrator-api decision write verbs
(``open-decision``/``resolve-decision``/``defer-decision``/
``cancel-decision``) caught only ``DecisionError`` and
``DecisionIndexReadError`` -- ``DecisionEventLogReadError`` escaped as a raw
traceback to the CLI hook: prose on stderr, EMPTY stdout. That violates the
JSON-first machine contract (C-005/NFR-002, the #2879 orchestrator-api
envelope surface).

This test mirrors ``test_typed_error_fail_closed.py``'s style: build a real
mission fixture on disk, corrupt ``status.events.jsonl``, and drive the
``open-decision`` idempotent re-open path through the CLI, asserting a
parseable JSON envelope on stdout carrying the
``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` error_code -- never empty stdout /
stderr prose.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api import commands as orch
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast, pytest.mark.regression]

runner = CliRunner()

_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4FBE"
_MISSION_SLUG = "decision-event-log-read-error"

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

_ORIGIN = "specify"
_STEP_ID = "s1"
_INPUT_KEY = "k1"
_QUESTION = "Which option?"
_ACTOR = "test-agent"


def _open_decision_args() -> list[str]:
    return [
        "open-decision",
        "--mission",
        _MISSION_SLUG,
        "--origin",
        _ORIGIN,
        "--input-key",
        _INPUT_KEY,
        "--question",
        _QUESTION,
        "--step-id",
        _STEP_ID,
        "--actor",
        _ACTOR,
        "--policy",
        _POLICY,
    ]


def _seed_mission(tmp_path: Path) -> Path:
    """A minimal, real (non-git) mission dir -- no coordination topology."""
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "slug": _MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "status_phase": 2,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return repo_root


def test_open_decision_idempotent_reopen_with_corrupt_event_log_emits_json_envelope(
    tmp_path: Path,
) -> None:
    """RED (pre-fix): a corrupt ``status.events.jsonl`` on the idempotent
    re-open path escapes as a raw traceback (empty stdout). GREEN (post-fix):
    a parseable JSON envelope on stdout carrying
    ``DESIGN_STATUS_EVENT_LOG_UNREADABLE``.
    """
    repo_root = _seed_mission(tmp_path)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        # First call: mints the decision and writes a well-formed opened event.
        first = runner.invoke(app, _open_decision_args(), catch_exceptions=False)
        first_envelope = json.loads(first.output.strip().split("\n")[0])
        assert first_envelope["success"] is True, first_envelope

        # Corrupt the event log the idempotent re-open repair path reads.
        events_path = repo_root / "kitty-specs" / _MISSION_SLUG / "status.events.jsonl"
        assert events_path.exists()
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write("{not valid json\n")

        # Second call: same logical key -> idempotent re-open -> repair path
        # -> _opened_event_exists reads the now-corrupt event log.
        second = runner.invoke(app, _open_decision_args(), catch_exceptions=False)

    assert second.stdout.strip(), f"stdout must carry a JSON envelope, never be empty, even when the underlying read fails closed; stderr={second.stderr!r}"
    envelope = json.loads(second.stdout.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE", envelope
