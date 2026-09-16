"""The executable capability matrix — no silent green, machine-tested."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.config import AI_CHOICES
from specify_cli.live_work.capability import (
    CapabilityMatrix,
    CapabilityStatus,
    LIVE_WORK_HOOK_COMMAND_MARKER,
    matrix_for_harness,
)
from specify_cli.live_work.install import CLAUDE_LIVE_WORK_COMMAND, CODEX_NOTIFY_LINE

pytestmark = pytest.mark.fast


def test_matrix_rows_cover_both_adapted_harnesses() -> None:
    claude = matrix_for_harness("claude")
    codex = matrix_for_harness("codex")
    assert claude and codex
    claude_surfaces = {row.surface for row in claude}
    for surface in ("session_start", "session_end", "tool_invocations", "file_edit", "test_runs", "delegation"):
        assert surface in claude_surfaces, surface
    codex_surfaces = {row.surface for row in codex}
    assert "tool_invocations" in codex_surfaces
    assert next(row for row in codex if row.surface == "tool_invocations").status == CapabilityStatus.NOT_OBSERVABLE


def test_never_captured_rows_are_explicit_policy() -> None:
    matrix = CapabilityMatrix(Path("."))
    rows = {(row.harness, row.surface): row for row in matrix.rows()}
    assert rows[("all", "secrets_credentials_env")].status == CapabilityStatus.NEVER_CAPTURED
    assert rows[("all", "raw_terminal_output")].status == CapabilityStatus.NEVER_CAPTURED
    # The deliberately-unbuilt surfaces are named, not silently absent.
    assert rows[("all", "mission_review_outcomes")].status == CapabilityStatus.NOT_INSTRUMENTED
    assert "#4231" in rows[("all", "mission_review_outcomes")].limitation
    # #4269 landed: authored messages are an exact-attribution supported
    # surface now, with the live-ring-only honesty limitation stated.
    assert rows[("all", "authored_messages")].status == CapabilityStatus.EXACT
    assert "#4269" in rows[("all", "authored_messages")].limitation
    assert "never a capture hook" in rows[("all", "authored_messages")].limitation


def test_whole_mission_lifecycle_is_mapped_per_the_2026_09_14_clarification() -> None:
    """Every mission phase names its contract, seam and consumer — or its absence.

    #4268's 2026-09-14 whole-mission coverage clarification: a coverage
    matrix for first specify, plan, task generation, implementation,
    review/rework, acceptance/merge and retrospective, mapped to the
    existing event contract with the concrete producer and live consumer,
    and unsupported capture explicit.
    """
    matrix = CapabilityMatrix(Path("."))
    rows = {row.surface: row for row in matrix.rows() if row.harness == "all"}
    for surface in (
        "mission_first_specify",
        "mission_plan",
        "mission_task_generation",
        "mission_implementation",
        "mission_review_rework",
        "mission_acceptance_merge",
        "mission_retrospective",
    ):
        assert surface in rows, surface
    # The phases with an existing live seam are mapped to it, exactly.
    for surface in ("mission_first_specify", "mission_plan", "mission_task_generation", "mission_implementation", "mission_retrospective"):
        row = rows[surface]
        assert row.status == CapabilityStatus.EXACT, surface
        # contract kind, concrete producer seam, and the live consumer all named
        assert "spec_kitty_events" in row.mechanism or "WPStatusChanged" in row.mechanism or "retrospective/lifecycle_events.py" in row.mechanism
        assert "->" in row.mechanism
        assert "event.publish" in row.mechanism or "work.lifecycle.retrospective_" in row.mechanism
    # The phases with no live producer say so explicitly — never silence.
    assert rows["mission_review_rework"].status == CapabilityStatus.NOT_OBSERVABLE
    assert "#4231" in rows["mission_review_rework"].limitation
    assert rows["mission_acceptance_merge"].status == CapabilityStatus.NOT_OBSERVABLE
    assert "no producer" in rows["mission_acceptance_merge"].limitation
    # The retrospective row is this package's own producer (folded #4267).
    assert "work.lifecycle.retrospective_" in rows["mission_retrospective"].mechanism


def test_every_other_production_harness_is_enumerated_not_claimed() -> None:
    matrix = CapabilityMatrix(Path("."))
    rows = matrix.rows()
    per_harness = [row for row in rows if row.harness != "all"]
    instrumented = {row.harness for row in per_harness if row.status == CapabilityStatus.EXACT}
    assert instrumented == {"claude", "codex"}
    not_instrumented = {row.harness for row in per_harness if row.status == CapabilityStatus.NOT_INSTRUMENTED}
    # The repo's full harness roster (core.config.AI_CHOICES) minus the two
    # adapted harnesses. Derived from AI_CHOICES rather than hand-listed, so
    # registering a new agent in AI_CHOICES without enumerating it here (or
    # giving it an EXACT adapter) fails this gate instead of silently dropping
    # it from the coverage matrix — the failure mode that let #3973 add
    # `llxprt` everywhere except `_OTHER_HARNESSES` while this test stayed green.
    assert not_instrumented == set(AI_CHOICES) - instrumented


def test_codec_state_is_a_visible_matrix_field() -> None:
    matrix = CapabilityMatrix(Path("."))
    payload = matrix.as_dict()
    assert payload["codec"] in {"typed", "pending-events-10"}


def _claude_settings(root: Path, with_live_work: bool) -> None:
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    hooks: dict[str, list] = {}
    if with_live_work:
        for event in ("SessionStart", "SessionEnd", "PreToolUse", "PostToolUse"):
            hooks[event] = [{"hooks": [{"type": "command", "command": CLAUDE_LIVE_WORK_COMMAND}]}]
    (settings_dir / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_configured_harness_without_hooks_is_degraded(tmp_path: Path) -> None:
    _claude_settings(tmp_path, with_live_work=False)
    matrix = CapabilityMatrix(tmp_path)
    degraded = matrix.degraded_harnesses(frozenset({"claude"}))
    assert degraded == ["claude"]  # no silent green


def test_installed_hooks_are_healthy(tmp_path: Path) -> None:
    _claude_settings(tmp_path, with_live_work=True)
    matrix = CapabilityMatrix(tmp_path)
    assert matrix.degraded_harnesses(frozenset({"claude"})) == []
    health = matrix.health()["claude"]
    assert health.hooks_installed
    assert "SessionStart" in health.detail


def test_unconfigured_harness_degradation_is_only_reported_for_adapted(tmp_path: Path) -> None:
    matrix = CapabilityMatrix(tmp_path)
    # A harness with no adapter (e.g. cursor) is a not-instrumented row, not
    # a degraded state.
    assert matrix.degraded_harnesses(frozenset({"cursor", "claude"})) == ["claude"]


def test_codex_health_reads_the_notify_config(tmp_path: Path) -> None:
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(CODEX_NOTIFY_LINE + "\n", encoding="utf-8")
    matrix = CapabilityMatrix(tmp_path)
    assert matrix.degraded_harnesses(frozenset({"codex"})) == []
    # Without the entry: degraded.
    (codex_dir / "config.toml").write_text("# nothing\n", encoding="utf-8")
    assert CapabilityMatrix(tmp_path).degraded_harnesses(frozenset({"codex"})) == ["codex"]


def test_health_detection_uses_the_command_marker(tmp_path: Path) -> None:
    assert "live-work hook" in LIVE_WORK_HOOK_COMMAND_MARKER
    assert "live-work hook" in CLAUDE_LIVE_WORK_COMMAND
