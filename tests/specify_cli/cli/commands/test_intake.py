"""Tests for ``spec-kitty intake`` — including the ``--auto`` flag (T006-T009)."""
from __future__ import annotations

from pathlib import Path
import hashlib

import pytest
import typer
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.intake import intake
from specify_cli.mission_brief import BRIEF_SOURCE_FILENAME, MISSION_BRIEF_FILENAME
from tests.specify_cli.intake_test_helpers import patched_intake_command_environment

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

# Single shared runner (no mix_stderr — not supported in typer 0.24.x)
runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def intake_app() -> typer.Typer:
    """Return a minimal Typer app with only the intake command."""
    app = typer.Typer()
    app.command()(intake)
    return app


def _make_plan_file(tmp_path: Path, rel: str = "plan.md", content: str = "# Plan") -> Path:
    """Write a plan file under *tmp_path* and return its absolute path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# T006: --auto, no candidates → exit 1, no .kittify/ created
# ---------------------------------------------------------------------------


def test_auto_no_matches_exits_1(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto with no plan files found exits 1 and leaves .kittify/ untouched."""
    with patched_intake_command_environment(tmp_path, mock_sources=[]):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code == 1
    assert not (tmp_path / ".kittify").exists()


# ---------------------------------------------------------------------------
# T007: --auto, single candidate → exit 0, BRIEF DETECTED in output, source_agent present
# ---------------------------------------------------------------------------


def test_auto_single_match_writes_brief(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto with one match exits 0, prints BRIEF DETECTED, writes source_agent."""
    plan = _make_plan_file(tmp_path, "opencode-plan.md")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    assert "BRIEF DETECTED" in result.output
    # Rich may line-wrap long paths mid-string; join wrapped segments before the
    # substring check so tmp_path length doesn't flake the assertion.
    output_unwrapped = result.output.replace("\n", "")
    assert plan.name in output_unwrapped, f"output: {result.output}"

    brief_path = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    source_path = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    assert brief_path.exists(), "mission-brief.md should be created"
    assert source_path.exists(), "brief-source.yaml should be created"

    source_data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    assert source_data.get("source_agent") == "opencode", (
        f"Expected source_agent='opencode' in brief-source.yaml, got: {source_data}"
    )


# ---------------------------------------------------------------------------
# T007b: --auto, single match, existing brief, no --force → exit 1
# ---------------------------------------------------------------------------


def test_auto_single_match_existing_brief_no_force(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto with existing brief and no --force exits 1, does not overwrite."""
    _make_plan_file(tmp_path, "opencode-plan.md", content="# New Plan")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    # Pre-create both brief files. The conflict guard keys on the brief's
    # existence alone (#4910); with the brief present it refuses regardless of
    # the sidecar. Both files present is the canonical "complete state" case.
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    existing_brief = kittify / MISSION_BRIEF_FILENAME
    existing_brief.write_text("# Old Brief", encoding="utf-8")
    (kittify / BRIEF_SOURCE_FILENAME).write_text("source", encoding="utf-8")

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code == 1
    # Brief must not have been overwritten
    assert existing_brief.read_text(encoding="utf-8") == "# Old Brief"


# ---------------------------------------------------------------------------
# T008: --auto, single match, existing brief, --force → exit 0, overwritten
# ---------------------------------------------------------------------------


def test_auto_single_match_force_overwrites(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto --force overwrites an existing brief and exits 0."""
    _make_plan_file(tmp_path, "opencode-plan.md", content="# Updated Plan")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    existing_brief = kittify / MISSION_BRIEF_FILENAME
    existing_brief.write_text("# Old Brief", encoding="utf-8")

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto", "--force"], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    new_content = existing_brief.read_text(encoding="utf-8")
    assert "Updated Plan" in new_content, "Brief should have been overwritten"


# ---------------------------------------------------------------------------
# #4910: existing brief with an ABSENT provenance sidecar must still refuse.
# A missing sidecar is unknown provenance (refuse without --force), not
# safe-to-overwrite partial state. Covers both the --auto gate and the
# explicit-path/stdin gate. RED on the pre-fix `brief AND source` conjunction.
# ---------------------------------------------------------------------------


def test_auto_existing_brief_missing_sidecar_refuses(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto with a brief present but no sidecar refuses and preserves it (#4910)."""
    _make_plan_file(tmp_path, "opencode-plan.md", content="# New Plan")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    existing_brief = kittify / MISSION_BRIEF_FILENAME
    existing_brief.write_text("# HAND-WRITTEN BRIEF", encoding="utf-8")
    # No brief-source.yaml on purpose.

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code == 1, f"output: {result.output}"
    assert "--force" in result.output
    assert existing_brief.read_text(encoding="utf-8") == "# HAND-WRITTEN BRIEF"
    assert not (kittify / BRIEF_SOURCE_FILENAME).exists()


def test_explicit_path_existing_brief_missing_sidecar_refuses(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Explicit-path intake with a brief present but no sidecar refuses it (#4910)."""
    plan = _make_plan_file(tmp_path, content="# New Plan")

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    existing_brief = kittify / MISSION_BRIEF_FILENAME
    existing_brief.write_text("# HAND-WRITTEN BRIEF", encoding="utf-8")
    # No brief-source.yaml on purpose.

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code == 1, f"output: {result.output}"
    assert "--force" in result.output
    assert existing_brief.read_text(encoding="utf-8") == "# HAND-WRITTEN BRIEF"
    assert not (kittify / BRIEF_SOURCE_FILENAME).exists()


def test_explicit_path_orphan_sidecar_no_brief_still_writes(intake_app: typer.Typer, tmp_path: Path) -> None:
    """An orphan sidecar with no brief is recoverable partial state — write proceeds (#4910)."""
    plan = _make_plan_file(tmp_path, content="# Fresh Plan")

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    # Only the sidecar exists (no mission-brief.md): genuine partial state.
    (kittify / BRIEF_SOURCE_FILENAME).write_text("stale: sidecar", encoding="utf-8")

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    brief_path = kittify / MISSION_BRIEF_FILENAME
    assert brief_path.exists()
    assert "Fresh Plan" in brief_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T009: --auto, multiple candidates, non-TTY → exit 1, candidates listed
# ---------------------------------------------------------------------------


def test_auto_multiple_matches_non_tty_exits_1(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto with multiple matches in non-TTY exits 1 and lists candidates."""
    _make_plan_file(tmp_path, "plan-a.md")
    _make_plan_file(tmp_path, "plan-b.md")
    mock_sources = [
        ("harness-a", "agent-a", ["plan-a.md"]),
        ("harness-b", "agent-b", ["plan-b.md"]),
    ]

    with patched_intake_command_environment(tmp_path, mock_sources, tty=False):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code == 1
    # Both candidates should be mentioned in the combined output
    assert "plan-a.md" in result.output or "harness-a" in result.output
    assert "plan-b.md" in result.output or "harness-b" in result.output


# ---------------------------------------------------------------------------
# T006b: --auto + positional path → exit 1, mutual exclusion error
# ---------------------------------------------------------------------------


def test_auto_with_path_arg_exits_1(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto combined with a positional path exits 1 before scanning."""
    plan = _make_plan_file(tmp_path)
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(
            intake_app, [str(plan), "--auto"], catch_exceptions=False
        )

    assert result.exit_code == 1
    # Must not have created .kittify/
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


# ---------------------------------------------------------------------------
# T006c: Manual intake via path → brief-source.yaml has NO source_agent key
# ---------------------------------------------------------------------------


def test_manual_intake_no_source_agent(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Manual intake writes brief-source.yaml without a source_agent key."""
    plan = _make_plan_file(tmp_path, content="# Manual Plan")

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"

    source_path = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    assert source_path.exists()
    source_data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    assert "source_agent" not in source_data, (
        f"source_agent should NOT appear in manual intake; got: {source_data}"
    )


# ---------------------------------------------------------------------------
# T006d: --show still works after --auto changes
# ---------------------------------------------------------------------------


def test_show_works_after_auto_changes(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--show prints brief and provenance; unaffected by --auto changes."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / MISSION_BRIEF_FILENAME).write_text("# My Brief", encoding="utf-8")
    (kittify / BRIEF_SOURCE_FILENAME).write_text(
        "source_file: manual.md\ningested_at: 2026-01-01T00:00:00+00:00\nbrief_hash: abc123\n",
        encoding="utf-8",
    )

    with patched_intake_command_environment(tmp_path):
        result = runner.invoke(intake_app, ["--show"], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    assert "My Brief" in result.output
    assert "manual.md" in result.output


# ---------------------------------------------------------------------------
# T009b: --auto, multiple candidates, TTY — interactive selection
# ---------------------------------------------------------------------------


def test_auto_tty_valid_selection_ingests_correct_file(
    intake_app: typer.Typer, tmp_path: Path
) -> None:
    """TTY --auto: entering a valid number ingests the chosen candidate."""
    _make_plan_file(tmp_path, "plan-a.md", content="# Plan A")
    _make_plan_file(tmp_path, "plan-b.md", content="# Plan B")
    mock_sources = [
        ("harness-a", "agent-a", ["plan-a.md"]),
        ("harness-b", "agent-b", ["plan-b.md"]),
    ]

    with patched_intake_command_environment(tmp_path, mock_sources, tty=True):
        # CliRunner feeds "2\n" through its own input mechanism (not sys.stdin),
        # so typer.prompt still receives the selection correctly.
        result = runner.invoke(intake_app, ["--auto"], input="2\n", catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    assert "BRIEF DETECTED" in result.output
    brief = (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).read_text(encoding="utf-8")
    assert "Plan B" in brief

    source_data = yaml.safe_load(
        (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).read_text(encoding="utf-8")
    )
    assert source_data.get("source_agent") == "agent-b"


def test_auto_tty_non_numeric_input_exits_1(
    intake_app: typer.Typer, tmp_path: Path
) -> None:
    """TTY --auto: non-numeric selection exits 1 with an error message."""
    _make_plan_file(tmp_path, "plan-a.md")
    _make_plan_file(tmp_path, "plan-b.md")
    mock_sources = [
        ("harness-a", "agent-a", ["plan-a.md"]),
        ("harness-b", "agent-b", ["plan-b.md"]),
    ]

    with patched_intake_command_environment(tmp_path, mock_sources, tty=True):
        result = runner.invoke(intake_app, ["--auto"], input="abc\n", catch_exceptions=False)

    assert result.exit_code == 1
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


def test_auto_tty_out_of_range_number_exits_1(
    intake_app: typer.Typer, tmp_path: Path
) -> None:
    """TTY --auto: a number outside the valid range exits 1."""
    _make_plan_file(tmp_path, "plan-a.md")
    _make_plan_file(tmp_path, "plan-b.md")
    mock_sources = [
        ("harness-a", "agent-a", ["plan-a.md"]),
        ("harness-b", "agent-b", ["plan-b.md"]),
    ]

    with patched_intake_command_environment(tmp_path, mock_sources, tty=True):
        result = runner.invoke(intake_app, ["--auto"], input="99\n", catch_exceptions=False)

    assert result.exit_code == 1
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


def test_auto_tty_zero_input_exits_1(
    intake_app: typer.Typer, tmp_path: Path
) -> None:
    """TTY --auto: selection of 0 (below valid range) exits 1."""
    _make_plan_file(tmp_path, "plan-a.md")
    _make_plan_file(tmp_path, "plan-b.md")
    mock_sources = [
        ("harness-a", "agent-a", ["plan-a.md"]),
        ("harness-b", "agent-b", ["plan-b.md"]),
    ]

    with patched_intake_command_environment(tmp_path, mock_sources, tty=True):
        result = runner.invoke(intake_app, ["--auto"], input="0\n", catch_exceptions=False)

    assert result.exit_code == 1
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


def test_manual_intake_of_packet_writes_sidecar_overlay(
    intake_app: typer.Typer, tmp_path: Path
) -> None:
    """A v1 packet overlays provenance fields; hash remains SHA-256 of raw content."""
    packet = (
        "---\n"
        "handoff_packet: 1\n"
        "source_tool: example-tool\n"
        "source_mission: widget-booking\n"
        "source_ref: abc123\n"
        "requirements:\n"
        "  - id: FR-001\n"
        "    statement: Book a widget.\n"
        "---\n\n"
        "# widget-booking\n"
    )
    plan = _make_plan_file(tmp_path, "packet.md", content=packet)

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    source_path = tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME
    source_data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    assert source_data["source_tool"] == "example-tool"
    assert source_data["source_mission"] == "widget-booking"
    assert source_data["source_ref"] == "abc123"
    assert source_data["packet_version"] == 1
    assert source_data["requirement_count"] == 1
    assert source_data["source_agent"] == "example-tool"
    expected_hash = hashlib.sha256(packet.encode()).hexdigest()  # noqa: TID251 — mission-brief content fingerprint
    assert source_data["brief_hash"] == expected_hash
