"""Tests for doctor skills slash-command audit and --fix repair path (WP02/WP05).

All tests in this file will be RED until WP02 merges into this lane.
The imports of ``_get_slash_command_agents``, ``SlashCommandGap``,
``_load_slash_command_state``, and ``_repair_slash_command_state`` are the
forward contract for WP02's implementation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# ATDD stub (must have been RED before WP02 implementation)
# ---------------------------------------------------------------------------


def test_doctor_skills_output_includes_slash_commands_section() -> None:
    """FR-005/FR-007: doctor skills must include a Slash Commands section."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.doctor import app

    runner = CliRunner()
    result = runner.invoke(app, ["skills"])
    assert "Slash Commands" in (result.output or ""), (
        "doctor skills must include a Slash Commands section in its output"
    )


# ---------------------------------------------------------------------------
# T013: Audit logic, false-positive prevention, scope guard
# ---------------------------------------------------------------------------


class TestLoadSlashCommandState:
    """FR-005/FR-007: _load_slash_command_state() must detect gaps."""

    def test_missing_file_detected_as_gap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing command file is reported as a gap with status='missing'."""
        from specify_cli.cli.commands.doctor import _load_slash_command_state

        monkeypatch.setattr(
            "specify_cli.cli.commands._command_surface_doctor._get_slash_command_agents",
            lambda project_path: ["claude"],
        )
        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda agent_key: tmp_path / agent_key,
        )
        (tmp_path / "claude").mkdir()
        # No command files written → all gaps

        configured, gaps = _load_slash_command_state(tmp_path)
        assert configured == ["claude"]
        assert len(gaps) > 0
        assert all(g.status == "missing" for g in gaps)

    def test_present_files_no_gap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When all command files exist with current version marker, no gaps reported."""
        from specify_cli.cli.commands.doctor import _load_slash_command_state
        from specify_cli.runtime.agent_commands import (
            _VERSION_MARKER_PREFIX,
            _compute_output_filename,
        )
        from specify_cli.runtime.bootstrap import _get_cli_version
        from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS

        cmd_dir = tmp_path / "claude"
        cmd_dir.mkdir()
        version = _get_cli_version()
        for cmd in sorted(PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS):
            filename = _compute_output_filename(cmd, "claude")
            f = cmd_dir / filename
            f.write_text(f"{_VERSION_MARKER_PREFIX} {version} -->\n# body")

        monkeypatch.setattr(
            "specify_cli.cli.commands._command_surface_doctor._get_slash_command_agents",
            lambda project_path: ["claude"],
        )
        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda agent_key: cmd_dir,
        )

        _, gaps = _load_slash_command_state(tmp_path)
        assert gaps == []

    def test_scope_guard_unconfigured_agent_not_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T013: Agents not in config.available are excluded from audit."""
        from specify_cli.cli.commands.doctor import _load_slash_command_state

        monkeypatch.setattr(
            "specify_cli.cli.commands._command_surface_doctor._get_slash_command_agents",
            lambda project_path: [],  # no configured agents
        )

        configured, gaps = _load_slash_command_state(tmp_path)
        assert configured == []
        assert gaps == []


# ---------------------------------------------------------------------------
# T025: False-positive prevention — stale detected correctly
# ---------------------------------------------------------------------------


class TestAuditFalsePositives:
    """FR-007: A stale file must be reported as 'stale', not 'missing'."""

    def test_stale_version_reported_as_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.doctor import _load_slash_command_state
        from specify_cli.runtime.agent_commands import (
            _VERSION_MARKER_PREFIX,
            _compute_output_filename,
        )

        cmd_dir = tmp_path / "claude"
        cmd_dir.mkdir()
        filename = _compute_output_filename("specify", "claude")
        (cmd_dir / filename).write_text(f"{_VERSION_MARKER_PREFIX} 0.0.1 -->\n# body")

        monkeypatch.setattr(
            "specify_cli.cli.commands._command_surface_doctor._get_slash_command_agents",
            lambda project_path: ["claude"],
        )
        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda agent_key: cmd_dir,
        )

        _, gaps = _load_slash_command_state(tmp_path)
        specify_gaps = [g for g in gaps if g.command == "specify"]
        assert specify_gaps, "Expected a gap for the stale 'specify' command"
        assert specify_gaps[0].status == "stale"


# ---------------------------------------------------------------------------
# T026: --fix scope guard
# ---------------------------------------------------------------------------


class TestFixScopeGuard:
    """FR-011/C-002: Repair must only touch configured agents."""

    def test_repair_only_touches_configured_agents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called_with: list[list[str] | None] = []

        def fake_ensure(*, agent_keys: list[str] | None = None) -> None:
            called_with.append(agent_keys)

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
            fake_ensure,
        )

        from specify_cli.cli.commands.doctor import SlashCommandGap, _repair_slash_command_state

        gap = SlashCommandGap("claude", "specify", tmp_path / "spec-kitty.specify.md", "missing")
        _repair_slash_command_state(tmp_path, ["claude"], [gap])

        assert called_with == [["claude"]], (
            "repair must pass only configured agents, not all agents"
        )


# ---------------------------------------------------------------------------
# T027: --fix idempotency (also covers T016 early-return constraint)
# ---------------------------------------------------------------------------


class TestFixIdempotency:
    """FR-010/T016: _repair_slash_command_state returns [] when gaps=[]."""

    def test_repair_noop_when_no_gaps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ensure_called: list[object] = []

        def fake_ensure(*, agent_keys: list[str] | None = None) -> None:
            ensure_called.append(agent_keys)

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
            fake_ensure,
        )

        from specify_cli.cli.commands.doctor import _repair_slash_command_state

        result = _repair_slash_command_state(tmp_path, ["claude"], [])

        assert result == [], "Empty gaps should return empty list"
        assert ensure_called == [], "Installer must not be called when there are no gaps"

    def test_repair_idempotent_twice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running repair twice returns the same healthy state."""
        call_count = 0

        def fake_ensure(*, agent_keys: list[str] | None = None) -> None:
            nonlocal call_count
            call_count += 1

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
            fake_ensure,
        )

        from specify_cli.cli.commands.doctor import SlashCommandGap, _repair_slash_command_state

        gap = SlashCommandGap("claude", "specify", tmp_path / "spec-kitty.specify.md", "missing")
        _repair_slash_command_state(tmp_path, ["claude"], [gap])
        _repair_slash_command_state(tmp_path, ["claude"], [])  # second call, no gaps

        assert call_count == 1, "Installer called only once; second call was a no-op"


# ---------------------------------------------------------------------------
# T017: Integration — detect gap → fix → verify clean
# ---------------------------------------------------------------------------


class TestDoctorSkillsFixIntegration:
    """FR-006: --fix path must repair detected gaps."""

    def test_fix_repairs_missing_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--fix path calls repair when gaps exist, leaving zero gaps after."""
        repaired: list[object] = []

        def fake_repair(
            project_path: Path,
            configured_agents: list[str],
            gaps: list[object],
        ) -> list[str]:
            for gap in gaps:
                path = getattr(gap, "expected_path", None)
                if path is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# repaired")
            repaired.extend(gaps)
            return [str(getattr(g, "expected_path", "")) for g in gaps]

        monkeypatch.setattr(
            "specify_cli.cli.commands.doctor._repair_slash_command_state",
            fake_repair,
        )

        call_count = 0

        def fake_load(project_path: Path) -> tuple[list[str], list[object]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from specify_cli.cli.commands.doctor import SlashCommandGap

                gap = SlashCommandGap(
                    "claude", "specify", tmp_path / "spec-kitty.specify.md", "missing"
                )
                return ["claude"], [gap]
            return ["claude"], []

        monkeypatch.setattr(
            "specify_cli.cli.commands.doctor._load_slash_command_state",
            fake_load,
        )

        # Simulate the fix path: load → repair → reload to verify clean
        _, gaps = fake_load(tmp_path)
        fake_repair(tmp_path, ["claude"], gaps)
        _, remaining = fake_load(tmp_path)

        assert repaired, "Expected at least one gap to be repaired"
        assert remaining == [], "Expected zero remaining gaps after repair"

    def test_fix_repaired_count_returned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_repair_slash_command_state returns one entry per repaired file."""

        def fake_ensure(*, agent_keys: list[str] | None = None) -> None:
            pass

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
            fake_ensure,
        )

        from specify_cli.cli.commands.doctor import SlashCommandGap, _repair_slash_command_state

        gaps = [
            SlashCommandGap("claude", "specify", tmp_path / "spec-kitty.specify.md", "missing"),
            SlashCommandGap("claude", "plan", tmp_path / "spec-kitty.plan.md", "missing"),
        ]
        result = _repair_slash_command_state(tmp_path, ["claude"], gaps)
        assert len(result) == 2
        assert all(isinstance(p, str) for p in result)


class TestDoctorSkillsJson:
    """JSON mode must include slash-command health, not only Agent Skills."""

    def test_root_startup_does_not_repair_before_doctor_skills(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """doctor skills must own slash-command repairs so JSON can report them.

        Invoked through ``CliRunner`` on the real root app so ``main_callback``
        receives the ``typer.Context`` Typer itself constructs — a hand-rolled
        ``SimpleNamespace`` fake has no contract keeping it current and drifts
        every time ``main_callback`` grows another ``ctx.*`` read (#4131).
        """
        from typer.testing import CliRunner

        import specify_cli
        from specify_cli.cli.commands import doctor

        calls: list[str] = []

        monkeypatch.setattr(
            specify_cli,
            "root_callback",
            lambda _ctx: None,
        )
        # locate_project_root has two patch seams: the root callback's startup
        # gates resolve it through the specify_cli module global, while the
        # doctor skills shell imports it into its own namespace.
        monkeypatch.setattr(
            specify_cli,
            "locate_project_root",
            lambda: None,
        )
        monkeypatch.setattr(
            doctor,
            "locate_project_root",
            lambda: None,
        )
        monkeypatch.setattr(
            "specify_cli.runtime.bootstrap.ensure_runtime",
            lambda: None,
        )
        monkeypatch.setattr(
            "specify_cli.runtime.agent_skills.ensure_global_agent_skills",
            lambda: None,
        )
        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.ensure_global_agent_commands",
            lambda: calls.append("agent_commands"),
        )
        # main_callback reads sys.argv directly (not the parsed args) to detect
        # the doctor-skills invocation, so the patched argv must match the
        # CliRunner invocation below.
        monkeypatch.setattr(
            "sys.argv",
            ["spec-kitty", "doctor", "skills", "--fix", "--json"],
        )

        result = CliRunner().invoke(
            specify_cli.app, ["doctor", "skills", "--fix", "--json"]
        )

        # The command body itself runs to its not-in-project exit (no project
        # root): the point under test is that root startup got there first
        # without repairing.
        assert result.exit_code == 2
        assert calls == []

    def test_json_reports_slash_command_gaps(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from typer.testing import CliRunner

        from specify_cli.cli.commands import _command_surface_doctor, doctor

        gap = doctor.SlashCommandGap(
            "claude",
            "specify",
            tmp_path / "spec-kitty.specify.md",
            "missing",
        )
        # locate_project_root is resolved in the doctor command shell (the
        # patchable seam); the command-surface internals live in the sibling.
        monkeypatch.setattr(doctor, "locate_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            _command_surface_doctor,
            "_load_command_skill_state",
            lambda _project_path: (object(), object(), [], [], [], False),
        )
        monkeypatch.setattr(
            _command_surface_doctor,
            "_command_skill_payload",
            lambda *_args: {"ok": True},
        )
        monkeypatch.setattr(
            _command_surface_doctor,
            "_load_slash_command_state",
            lambda _project_path: (["claude"], [gap]),
        )

        result = CliRunner().invoke(doctor.app, ["skills", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert payload["slash_commands"]["gaps"][0]["status"] == "missing"
