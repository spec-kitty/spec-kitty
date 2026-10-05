"""Regression: ``create_mission_core`` emits ``SpecifyStarted`` locally.

Issue #1067 requires the canonical lifecycle stream to record the
specify-phase entry point, not just its completion. Mission creation
already scaffolds ``spec.md`` from mission configuration and opens the specify phase —
that is the canonical moment to emit ``SpecifyStarted``. Without it, a
fresh mission's ``status.events.jsonl`` skips straight from
``MissionCreated`` to ``SpecifyCompleted`` (emitted at setup-plan time),
leaving TeamSpace and the local dashboard blind to the in-progress
specify state.

This regression test was missing when #1067 was first closed; the
constant ``SPECIFY_STARTED`` was defined but never emitted. Reopening
fixed that gap and proved it stays fixed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.mission_type_profiles import ResolvedMissionType
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.runtime.resolver import TemplateConfigurationError


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]



@pytest.fixture(autouse=True)
def _cwd_outside_any_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree-context guard reads the real process cwd, and pytest may run
    from inside a lane worktree. Run each test from its ``tmp_path`` so the real
    guard sees a non-worktree directory (no patch)."""
    monkeypatch.chdir(tmp_path)


def _init_repo(repo: Path) -> None:
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    # WP04 fail-closed (C-A1): create_mission_core requires a non-empty
    # activated mission-type set; software-dev is the only type resolved
    # for real in this file (the documentation-typed test mocks
    # resolve_mission_type_context directly).
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    # A REAL ``main`` (independent of ``init.defaultBranch``); the
    # default coord create mints the coordination branch for real, so the
    # canonical status log is the coordination surface's (see _canonical_log).
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").title()
    return {
        "friendly_name": title,
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


def _canonical_log(result: MissionCreationResult) -> Path:
    """The status log the create wrote: the coordination surface's on a coord create."""
    [log] = [p for p in result.created_files if p.name == "status.events.jsonl"]
    return log


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_mission_create_appends_mission_created_and_specify_started(tmp_path: Path) -> None:
    """A fresh mission's canonical event log records both `MissionCreated` and `SpecifyStarted`."""
    _init_repo(tmp_path)

    result = create_mission_core(tmp_path, "lifecycle-stream-1067", **_mission_summary("lifecycle-stream-1067"))

    log = _canonical_log(result)
    rows = _read_jsonl(log)
    event_types = [row.get("event_type") for row in rows]

    assert "MissionCreated" in event_types, f"MissionCreated missing from {log}: {event_types}"
    assert "SpecifyStarted" in event_types, (
        "SpecifyStarted must be emitted at mission-create time so the canonical "
        f"lifecycle is complete (#1067). Log contents: {event_types}"
    )
    # MissionCreated must precede SpecifyStarted on the canonical timeline.
    assert event_types.index("MissionCreated") < event_types.index("SpecifyStarted")


def test_mission_create_specify_started_payload_references_spec_md(tmp_path: Path) -> None:
    """The `SpecifyStarted` payload identifies the spec.md artifact."""
    _init_repo(tmp_path)

    result = create_mission_core(tmp_path, "lifecycle-stream-1067", **_mission_summary("lifecycle-stream-1067"))

    rows = _read_jsonl(_canonical_log(result))
    specify = next(r for r in rows if r.get("event_type") == "SpecifyStarted")
    assert specify["payload"]["mission_slug"] == result.mission_slug
    artifact_path = specify["payload"].get("artifact_path") or ""
    assert artifact_path.endswith("spec.md"), specify


def test_mission_create_specify_started_is_idempotent(tmp_path: Path) -> None:
    """Re-running create_mission_core (e.g. ``--resume``) does not duplicate `SpecifyStarted`.

    ``emit_artifact_phase`` dedupes on ``(event_type, mission_slug, artifact_path)``.
    """
    _init_repo(tmp_path)

    first = create_mission_core(tmp_path, "lifecycle-stream-1067", **_mission_summary("lifecycle-stream-1067"))

    # Replay an emit at the same artifact_path, into the directory of the log
    # the create wrote (the coordination Mission dir on a coord create); the
    # dedupe key in ``emit_artifact_phase`` should make this a no-op.
    from specify_cli.status.lifecycle_events import (
        SPECIFY_STARTED,
        emit_artifact_phase,
    )

    log = _canonical_log(first)
    second = emit_artifact_phase(
        log.parent,
        event_type=SPECIFY_STARTED,
        mission_slug=first.mission_slug,
        actor="spec-kitty mission create",
        artifact_path="spec.md",
    )

    rows = _read_jsonl(log)
    specify_events = [r for r in rows if r.get("event_type") == "SpecifyStarted"]
    assert len(specify_events) == 1, (
        f"SpecifyStarted must be idempotent on (mission_slug, artifact_path); "
        f"got {len(specify_events)} rows: {specify_events}"
    )
    assert second is None


def test_template_configuration_failure_emits_no_lifecycle_events(tmp_path: Path) -> None:
    """Template selection fails before MissionCreated or SpecifyStarted can be emitted."""
    _init_repo(tmp_path)
    invalid_context = ResolvedMissionType(
        mission_type="documentation",
        governance_text="",
        action_sequence=[],
        provenance="test",
        _template_set_thunk=lambda: None,
    )

    with (
        patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            return_value=invalid_context,
        ),
        pytest.raises(TemplateConfigurationError),
    ):
        create_mission_core(
            tmp_path,
            "no-false-lifecycle",
            mission="documentation",
            **_mission_summary("no-false-lifecycle"),
        )

    event_logs = list((tmp_path / "kitty-specs").glob("*/status.events.jsonl"))
    assert event_logs == []
    # Nor on a coordination surface: the failure precedes the coordination mint.
    assert not (tmp_path / ".worktrees").exists()
