"""``doctor`` must not claim health over surfaces it never examined (#6891).

A ``.kittify/config.yaml`` with **no** ``agents.available`` list is the legacy
every-agent fallback (#6501): the CLI treats every supported agent as available.
Both audits derive their examined set from ``config.available`` — empty here —
and then printed health over nothing:

    $ spec-kitty doctor skills
    Command Skills: all manifest entries healthy (0 file(s))
    $ spec-kitty doctor tool-surfaces
    Tool Surfaces: all surfaces healthy (0 checked)

The fix names the cause instead: the project states no agent list, so the CLI
cannot tell which surfaces to verify, and nothing was checked. These tests hold
the standing invariant that a summary may assert health only over a non-empty
examined set, and pair every "no health claim" assertion on the legacy fixture
with a positive control on the same fixture family (a stated agent list still
produces a real healthy line with a non-zero count, and still reports real
findings).

Red-first record: ``research/red-first-run.txt``; half-fix revert:
``research/half-fix-revert.txt``. JSON key sets are frozen from
``research/keysets.txt`` (captured on ``6f73b2a98e``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands._command_surface_doctor as surface_doctor_mod
import specify_cli.cli.commands.doctor as doctor_mod
from charter.hasher import hash_content
from specify_cli.cli.commands.doctor import app
from specify_cli.core import agent_config
from specify_cli.skills import command_installer

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

#: A legacy project: the ``agents`` section exists but states no agent list.
LEGACY_CONFIG = "agents:\n  auto_commit: true\n"

#: The every-agent fallback assumes every tool; one existing tool folder is
#: enough for the ``no_tool_folder`` check to stay quiet, which is what makes
#: these commands reach their healthy summary in the first place.
COMMANDS = (
    "accept",
    "analyze",
    "charter",
    "consolidate",
    "implement",
    "plan",
    "research",
    "review",
    "specify",
    "status",
    "tasks",
    "tasks-finalize",
    "tasks-outline",
    "tasks-packages",
)

#: ``doctor skills --json`` on the legacy fixture, captured on 6f73b2a98e.
SKILLS_JSON_KEYS = frozenset(
    {
        "canonical_commands",
        "collisions",
        "configured_agents",
        "drift",
        "entries",
        "gaps",
        "legacy",
        "manifest_agents",
        "ok",
        "orphans",
        "pack_skills",
        "pruned",
        "repair_errors",
        "repaired_agents",
        "repaired_paths",
        "repaired_vibe_config",
        "slash_commands",
        "stale",
        "tool_folders",
        "uninstalled_agents",
        "unsafe",
        "vibe_config_missing",
    }
)

#: ``doctor tool-surfaces --json`` top-level keys on the same fixture.
TOOL_SURFACE_JSON_KEYS = frozenset(
    {
        "configured_tools",
        "findings",
        "ok",
        "project_root",
        "schema_version",
        "summary",
        "surfaces",
    }
)

TOOL_SURFACE_SUMMARY_KEYS = frozenset({"drifted", "errors", "missing", "present", "surfaces", "warnings"})

HEALTH_CLAIMS = ("all manifest entries healthy", "all surfaces healthy")


def _write_legacy_project(root: Path) -> Path:
    """A realistic legacy project: no agent list, plus a tool folder from an old init."""
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(LEGACY_CONFIG, encoding="utf-8")
    commands = root / ".claude" / "commands"
    commands.mkdir(parents=True)
    for command in COMMANDS:
        (commands / f"spec-kitty.{command}.md").write_text(
            f"---\ndescription: hand-edited spec-kitty {command}\n---\n\nstale 2.0 body\n",
            encoding="utf-8",
        )
    return root


def _write_stated_list(root: Path, *agents: str) -> None:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["agents:", "  available:"] + [f"    - {agent}" for agent in agents]
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _invoke(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str):
    """Invoke the real ``doctor`` app against *root* (both root seams patched)."""
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: root)
    monkeypatch.setattr(surface_doctor_mod, "locate_project_root", lambda: root)
    return runner.invoke(app, [*args])


def _tree_snapshot(root: Path) -> dict[str, str]:
    """Content fingerprint of every file in *root* (TID251: use the charter hasher)."""
    return {str(path.relative_to(root)): hash_content(path.read_text(encoding="utf-8")) for path in sorted(root.rglob("*")) if path.is_file()}


def test_legacy_skills_summary_names_the_missing_agent_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The command-skills summary must not claim health over zero examined files."""
    _write_legacy_project(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "skills")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "nothing to check" in result.output
    assert "all manifest entries healthy" not in result.output


def test_legacy_tool_surfaces_summary_names_the_missing_agent_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool-surface summary must not claim health over zero checked surfaces."""
    _write_legacy_project(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "tool-surfaces")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "nothing to check" in result.output
    assert "all surfaces healthy" not in result.output


def test_legacy_summary_does_not_prescribe_installing_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-002: name the state and the gap, prescribe nothing (no duplicate-surface advice)."""
    _write_legacy_project(tmp_path)

    output = _invoke(monkeypatch, tmp_path, "skills").output + _invoke(monkeypatch, tmp_path, "tool-surfaces").output

    for advice in ("agent config add", "spec-kitty upgrade", "install"):
        assert advice not in output, f"legacy summary prescribes {advice!r}: {output}"


def test_stated_agent_list_still_reports_real_command_skill_health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the same fixture family: a stated list is examined and healthy."""
    _write_legacy_project(tmp_path)
    _write_stated_list(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")

    result = _invoke(monkeypatch, tmp_path, "skills")

    assert result.exit_code == 0, result.output
    assert "all manifest entries healthy" in result.output
    assert "nothing to check" not in result.output
    match = re.search(r"all manifest entries healthy \((\d+) file\(s\)\)", result.output)
    assert match is not None, result.output
    assert int(match.group(1)) > 0


def test_stated_agent_list_still_reports_a_real_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a stated list with a deleted managed file still fails."""
    _write_legacy_project(tmp_path)
    _write_stated_list(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")
    (tmp_path / ".agents" / "skills" / "spec-kitty-tasks" / "SKILL.md").unlink()

    result = _invoke(monkeypatch, tmp_path, "skills")

    assert result.exit_code == 1, result.output
    assert "Missing managed files" in result.output
    assert "nothing to check" not in result.output


def test_legacy_real_finding_still_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real finding in the legacy shape is reported, not replaced by the honest line."""
    _write_legacy_project(tmp_path)
    collision = tmp_path / ".agents" / "skills" / "spec-kitty-plan" / "SKILL.md"
    collision.parent.mkdir(parents=True)
    collision.write_text("user content\n", encoding="utf-8")

    result = _invoke(monkeypatch, tmp_path, "skills")

    assert result.exit_code == 1, result.output
    assert "spec-kitty-plan" in result.output
    assert "nothing to check" not in result.output


def test_legacy_kept_leftover_warning_survives_the_truthful_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A kept, edited dotted leftover is a warning (`ok` stays true) and must not be swallowed.

    ``command_installer.verify()`` records an unrecorded dotted leftover under ``legacy``
    without failing the report, so the truthful line must be *followed* by that warning —
    not printed instead of it (review round 1, blocker).
    """
    _write_legacy_project(tmp_path)
    leftover = tmp_path / ".agents" / "skills" / "spec-kitty.plan" / "SKILL.md"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("my own edits\n", encoding="utf-8")

    result = _invoke(monkeypatch, tmp_path, "skills")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "all manifest entries healthy" not in result.output
    assert ".agents/skills/spec-kitty.plan/SKILL.md" in result.output
    assert "no longer managed" in result.output


def test_legacy_fix_json_keeps_the_envelope_and_the_truthful_line_stays_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--json --fix`` together: frozen envelope, no repair, no write."""
    _write_legacy_project(tmp_path)
    before = _tree_snapshot(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "skills", "--json", "--fix")

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert set(payload) == SKILLS_JSON_KEYS
    assert payload["repaired_agents"] == []
    assert payload["repaired_paths"] == []
    assert "no stated agent list" not in result.output
    assert _tree_snapshot(tmp_path) == before


def test_legacy_tool_surfaces_fix_repairs_nothing_and_stays_truthful(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``doctor tool-surfaces --fix`` in the legacy shape writes nothing and stays truthful."""
    from types import SimpleNamespace

    _write_legacy_project(tmp_path)
    before = _tree_snapshot(tmp_path)
    # `--fix` first asks the checkout-identity seam whether this invocation may write
    # (#2613). The fixture lives outside this checkout, so grant ownership here; the
    # subject under test is the summary, not the refusal.
    monkeypatch.setattr(
        surface_doctor_mod,
        "resolve_checkout_identity",
        lambda *_args, **_kwargs: SimpleNamespace(write_refusal=lambda: None),
    )

    result = _invoke(monkeypatch, tmp_path, "tool-surfaces", "--fix")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "all surfaces healthy" not in result.output
    assert "Repaired" not in result.output
    assert _tree_snapshot(tmp_path) == before


def test_missing_config_file_does_not_claim_the_file_states_anything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A project with `.kittify/` but no `config.yaml` is legacy too; the wording must not lie."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".claude" / "commands").mkdir(parents=True)

    result = _invoke(monkeypatch, tmp_path, "tool-surfaces")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "does not state an agents.available list" in result.output
    assert "states no agents.available list" not in result.output


def test_legacy_skills_json_key_set_is_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-005: the truthful wording is human-only; the JSON envelope keys do not move."""
    _write_legacy_project(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "skills", "--json")

    payload = json.loads(result.output)
    assert set(payload) == SKILLS_JSON_KEYS


def test_legacy_tool_surfaces_json_key_set_is_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-005: same freeze for the tool-surface envelope."""
    _write_legacy_project(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "tool-surfaces", "--json")

    payload = json.loads(result.output)
    assert set(payload) == TOOL_SURFACE_JSON_KEYS
    assert set(payload["summary"]) == TOOL_SURFACE_SUMMARY_KEYS


def test_legacy_fix_repairs_nothing_and_stays_truthful(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--fix`` in the legacy shape installs nothing and must not claim a repair."""
    _write_legacy_project(tmp_path)
    before = _tree_snapshot(tmp_path)

    result = _invoke(monkeypatch, tmp_path, "skills", "--fix")

    assert result.exit_code == 0, result.output
    assert "no stated agent list" in result.output
    assert "Repaired" not in result.output
    assert _tree_snapshot(tmp_path) == before


def test_command_files_shell_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C-003 ratchet: ``doctor command-files`` keeps its own healthy line and exit code."""
    from specify_cli.runtime import doctor as runtime_doctor

    monkeypatch.setattr(runtime_doctor, "check_command_file_health", lambda _root: [])

    healthy = _invoke(monkeypatch, tmp_path, "command-files")

    assert healthy.exit_code == 0, healthy.output
    assert "all files healthy" in healthy.output
    assert "no stated agent list" not in healthy.output

    monkeypatch.setattr(
        runtime_doctor,
        "check_command_file_health",
        lambda _root: [{"agent": "claude", "command": "plan", "file": "f.md", "severity": "error", "issue": "missing"}],
    )

    unhealthy = _invoke(monkeypatch, tmp_path, "command-files")

    assert unhealthy.exit_code == 1, unhealthy.output
    assert "Command Files" in unhealthy.output
    assert "no stated agent list" not in unhealthy.output


def test_legacy_audits_add_no_config_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006 / NFR-002: the fix reuses the config the command already loaded (baseline 3 / 1)."""
    _write_legacy_project(tmp_path)
    calls = {"n": 0}
    real = agent_config.load_agent_config

    def counting(root: Path):
        calls["n"] += 1
        return real(root)

    monkeypatch.setattr(agent_config, "load_agent_config", counting)

    calls["n"] = 0
    _invoke(monkeypatch, tmp_path, "skills")
    assert calls["n"] == 3

    calls["n"] = 0
    _invoke(monkeypatch, tmp_path, "tool-surfaces")
    assert calls["n"] == 1
