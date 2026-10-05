"""Unit tests for the drift-policy wiring: DriftPolicySummary + run_surface_repair.

Contract: drift-policy-01
NFR-007: --yes alone MUST NOT trigger overwrite of drifted files.
NFR-006: Second consecutive run on an unedited project reports zero surfaces created/repaired.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import SurfaceDefinition, SurfaceInstance
from specify_cli.tool_surface.repair import (
    DriftPolicySummary,
    RepairResult,
    _prompt_overwrite,
    render_surface_summary_lines,
    run_surface_repair,
)
from specify_cli.tool_surface.status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    STATE_STALE,
    SurfaceReport,
    SurfaceSummary,
    SurfaceStatus,
    _surface_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _definition(
    kind: ToolSurfaceKind = ToolSurfaceKind.COMMAND_SKILL,
    *,
    install_scope: InstallScope = InstallScope.PROJECT,
    required_policy: RequiredPolicy = RequiredPolicy.REPAIRABLE_REQUIRED,
    activation_mode: ActivationMode = ActivationMode.ALWAYS,
) -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=install_scope,
        path_pattern="x/{command}",
        required_policy=required_policy,
        activation_mode=activation_mode,
        provider_key="p",
        repair_hint="fix",
    )


def _make_status(
    state: str,
    path: str = "a.md",
    *,
    definition: SurfaceDefinition | None = None,
    owner: str = "codex",
) -> SurfaceStatus:
    inst = SurfaceInstance(
        definition=definition or _definition(),
        path=Path("/proj") / path,
        exists=state != STATE_MISSING,
        file_hash=None,
        owner=owner,
    )
    return SurfaceStatus(instance=inst, state=state)


def _empty_summary() -> SurfaceSummary:
    return SurfaceSummary(
        surfaces=0, present=0, missing=0, drifted=0, warnings=0, errors=0
    )


def _empty_report(surfaces: tuple[SurfaceStatus, ...] = ()) -> SurfaceReport:
    return SurfaceReport(
        ok=True,
        project_root="/proj",
        configured_tools=("codex",),
        summary=_empty_summary(),
        surfaces=surfaces,
        findings=(),
    )


class _RepairRecorder:
    """Minimal provider stub that records what was passed to repair()."""

    provider_key = "p"

    def __init__(self) -> None:
        self.received: list[SurfaceStatus] = []

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return True

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        return []

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(instance=instance, state=STATE_PRESENT)

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        self.received.extend(statuses)
        return RepairResult(
            repaired=tuple(_surface_id(s.instance) for s in statuses),
            dry_run=dry_run,
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        return True


# ---------------------------------------------------------------------------
# DriftPolicySummary dataclass
# ---------------------------------------------------------------------------


class TestDriftPolicySummary:
    def test_default_is_all_empty(self) -> None:
        summary = DriftPolicySummary()
        assert summary.created == []
        assert summary.repaired == []
        assert summary.drifted_overwritten == []
        assert summary.drifted_reported == []
        assert summary.skipped == []

    def test_fields_are_independent_lists(self) -> None:
        a = DriftPolicySummary()
        b = DriftPolicySummary()
        a.created.append(Path("/x"))
        assert b.created == [], "default_factory must produce independent lists"


# ---------------------------------------------------------------------------
# run_surface_repair — integration via mocked service layer
# ---------------------------------------------------------------------------


def _patch_surface_layer(
    report: SurfaceReport,
    recorder: _RepairRecorder | None = None,
) -> Any:
    """Return a context-manager that stubs the full surface infrastructure.

    Patches are applied at the *source* module path because
    ``run_surface_repair`` uses lazy ``from X import Y`` imports inside the
    function body.  Patching via the repair module namespace would fail
    (the names are not bound there at import time).
    """
    if recorder is None:
        recorder = _RepairRecorder()

    providers = [recorder]

    def _fake_build_providers() -> list[_RepairRecorder]:
        return providers

    def _fake_build_registry(tools: Sequence[str]) -> MagicMock:
        return MagicMock()

    mock_builder = MagicMock()
    mock_builder.build.return_value = []

    mock_status_cls = MagicMock(return_value=MagicMock())
    mock_status_cls.return_value.collect.return_value = report

    class _Context:
        def __enter__(self) -> _Context:
            self._patches = [
                # Patch at source so lazy `from .service import build_providers`
                # inside run_surface_repair picks up the stub.
                patch(
                    "specify_cli.tool_surface.service.build_providers",
                    _fake_build_providers,
                ),
                patch(
                    "specify_cli.tool_surface.service.build_registry",
                    _fake_build_registry,
                ),
                patch(
                    "specify_cli.tool_surface.plan.SurfacePlanBuilder",
                    return_value=mock_builder,
                ),
                patch(
                    "specify_cli.tool_surface.status.SurfaceStatusService",
                    mock_status_cls,
                ),
                patch(
                    "specify_cli.core.agent_config.get_configured_agents",
                    return_value=["codex"],
                ),
            ]
            for p in self._patches:
                p.start()
            self.recorder = recorder
            self.builder = mock_builder
            return self

        def __exit__(self, *args: object) -> None:
            for p in self._patches:
                p.stop()

    return _Context()


class TestRunSurfaceRepairRules:
    """Verify each of the 6 drift-policy rules in isolation."""

    # Rule 1 — missing → auto-created (no prompt)
    def test_rule1_missing_creates_silently(self) -> None:
        missing = _make_status(STATE_MISSING, "m.md")
        report = _empty_report(surfaces=(missing,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert len(summary.created) == 1
        assert summary.created[0] == Path("/proj/m.md")
        assert summary.repaired == []
        assert summary.drifted_overwritten == []
        assert summary.drifted_reported == []
        # Provider was called for the missing surface
        assert len(recorder.received) == 1

    def test_auto_repair_does_not_plan_plugin_bundles(self) -> None:
        """init/upgrade repair must not build optional disabled plugin bundles."""
        report = _empty_report()
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder) as ctx:
            run_surface_repair(Path("/proj"), interactive=True, repair_drift=False)

        ctx.builder.build.assert_called_once_with(["codex"], Path("/proj"))

    def test_optional_disabled_missing_surface_is_not_auto_created(self) -> None:
        """Optional disabled surfaces remain explicit doctor/build work."""
        plugin_def = _definition(
            ToolSurfaceKind.PLUGIN_MANIFEST,
            install_scope=InstallScope.PLUGIN_BUNDLE,
            required_policy=RequiredPolicy.OPTIONAL,
            activation_mode=ActivationMode.DISABLED,
        )
        missing = _make_status(
            STATE_MISSING,
            "dist/spec-kitty-plugins/claude-code/.claude-plugin/plugin.json",
            definition=plugin_def,
            owner="plugin_bundle",
        )
        report = _empty_report(surfaces=(missing,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.created == []
        assert recorder.received == []

    def test_amazon_q_profiles_are_not_auto_created_in_home(self) -> None:
        """Amazon Q user-global profile writes require explicit repair intent."""
        profile_def = _definition(ToolSurfaceKind.AGENT_PROFILE)
        missing = SurfaceStatus(
            instance=SurfaceInstance(
                definition=profile_def,
                path=Path.home()
                / ".aws"
                / "amazonq"
                / "cli-agents"
                / "analyst-alex.json",
                exists=False,
                file_hash=None,
                owner="q",
            ),
            state=STATE_MISSING,
        )
        report = _empty_report(surfaces=(missing,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.created == []
        assert recorder.received == []

    # Rule 2 — stale → auto-repaired (no prompt)
    def test_rule2_stale_repaired_silently(self) -> None:
        stale = _make_status(STATE_STALE, "s.md")
        report = _empty_report(surfaces=(stale,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.repaired == [Path("/proj/s.md")]
        assert summary.created == []
        assert summary.drifted_overwritten == []
        assert summary.drifted_reported == []

    # Rule 3 — drifted + interactive + no --repair-drift → prompt; y → overwrite
    def test_rule3_drifted_interactive_y_overwrites(self) -> None:
        drifted = _make_status(STATE_DRIFTED, "d.md")
        report = _empty_report(surfaces=(drifted,))
        recorder = _RepairRecorder()

        with (
            _patch_surface_layer(report, recorder),
            patch("builtins.input", return_value="y"),
        ):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.drifted_overwritten == [Path("/proj/d.md")]
        assert summary.drifted_reported == []

    # Rule 3 — drifted + interactive + no --repair-drift → prompt; N → report only
    def test_rule3_drifted_interactive_n_reports_only(self) -> None:
        drifted = _make_status(STATE_DRIFTED, "d.md")
        report = _empty_report(surfaces=(drifted,))
        recorder = _RepairRecorder()

        with (
            _patch_surface_layer(report, recorder),
            patch("builtins.input", return_value="N"),
        ):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.drifted_reported == [Path("/proj/d.md")]
        assert summary.drifted_overwritten == []
        assert recorder.received == [], "provider must NOT be called for a report-only outcome"

    # Rule 4 — drifted + non-interactive (--yes) + no --repair-drift → report only
    def test_rule4_nfr007_yes_does_not_overwrite(self) -> None:
        """NFR-007: --yes (interactive=False) MUST NOT overwrite drifted files."""
        drifted = _make_status(STATE_DRIFTED, "d.md")
        report = _empty_report(surfaces=(drifted,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            # Simulate --yes: interactive=False, repair_drift=False
            summary = run_surface_repair(
                Path("/proj"), interactive=False, repair_drift=False
            )

        assert summary.drifted_reported == [Path("/proj/d.md")]
        assert summary.drifted_overwritten == []
        assert recorder.received == [], "must not call repair for drifted file when interactive=False"

    # Rule 5 — --repair-drift=overwrite → unconditional overwrite
    def test_rule5_repair_drift_overwrites_unconditionally(self) -> None:
        drifted = _make_status(STATE_DRIFTED, "d.md")
        report = _empty_report(surfaces=(drifted,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=False, repair_drift=True
            )

        assert summary.drifted_overwritten == [Path("/proj/d.md")]
        assert summary.drifted_reported == []
        assert len(recorder.received) == 1

    # Rule 6 — not_applicable → skip silently
    def test_rule6_not_applicable_skipped(self) -> None:
        na = _make_status(STATE_NOT_APPLICABLE, "na.md")
        report = _empty_report(surfaces=(na,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.skipped == [Path("/proj/na.md")]
        assert recorder.received == []

    # NFR-006 — second run on unedited project is a no-op
    def test_nfr006_second_run_zero_changes(self) -> None:
        """All surfaces present → zero created, zero repaired on second run."""
        present = _make_status(STATE_PRESENT, "p.md")
        report = _empty_report(surfaces=(present,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )

        assert summary.created == []
        assert summary.repaired == []
        assert summary.drifted_overwritten == []
        assert summary.drifted_reported == []
        assert recorder.received == []


class TestRunSurfaceRepairEdgeCases:
    """Edge-case and guard tests."""

    def test_empty_configured_tools_returns_empty_summary(self) -> None:
        """No configured agents → empty DriftPolicySummary, no error."""
        with patch(
            "specify_cli.core.agent_config.get_configured_agents",
            return_value=[],
        ):
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )
        assert summary == DriftPolicySummary()

    def test_get_configured_agents_exception_falls_back(self) -> None:
        """If get_configured_agents raises, AGENT_DIR_TO_KEY values are used."""
        report = _empty_report(surfaces=())
        recorder = _RepairRecorder()

        with (
            _patch_surface_layer(report, recorder),
            patch(
                "specify_cli.core.agent_config.get_configured_agents",
                side_effect=RuntimeError("config error"),
            ),
        ):
            # Should not raise; returns empty summary (no surfaces in report)
            summary = run_surface_repair(
                Path("/proj"), interactive=True, repair_drift=False
            )
        # If fallback tools are used, we may get an empty or non-empty summary
        # depending on mock. The critical invariant: no exception raised.
        assert isinstance(summary, DriftPolicySummary)

    def test_mixed_states_all_rules_applied(self) -> None:
        """Multiple surface states are each handled by their respective rule."""
        missing = _make_status(STATE_MISSING, "m.md")
        stale = _make_status(STATE_STALE, "s.md")
        drifted = _make_status(STATE_DRIFTED, "d.md")
        na = _make_status(STATE_NOT_APPLICABLE, "na.md")
        report = _empty_report(surfaces=(missing, stale, drifted, na))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            # Non-interactive: drifted goes to reported, not overwritten
            summary = run_surface_repair(
                Path("/proj"), interactive=False, repair_drift=False
            )

        assert len(summary.created) == 1
        assert len(summary.repaired) == 1
        assert summary.drifted_reported == [Path("/proj/d.md")]
        assert summary.skipped == [Path("/proj/na.md")]
        assert summary.drifted_overwritten == []

    def test_repair_drift_true_with_interactive_false_still_overwrites(self) -> None:
        """Rule 5 applies regardless of interactive flag."""
        drifted = _make_status(STATE_DRIFTED, "d.md")
        report = _empty_report(surfaces=(drifted,))
        recorder = _RepairRecorder()

        with _patch_surface_layer(report, recorder):
            summary = run_surface_repair(
                Path("/proj"), interactive=False, repair_drift=True
            )

        assert summary.drifted_overwritten == [Path("/proj/d.md")]


# ---------------------------------------------------------------------------
# _prompt_overwrite helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CLI-level drift policy (T042) — exercises the rules through real init/upgrade
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.non_sandbox
class TestDriftPolicyViaCli:
    """End-to-end drift-policy coverage driving the actual ``spec-kitty`` CLI.

    These complement the fast mocked tests above by proving the rules hold when
    routed through ``init``/``upgrade`` wiring (FR-001/FR-002), not just when
    ``run_surface_repair`` is called directly. Rules 3 (interactive prompt) and
    5 (``--repair-drift=overwrite``) require a TTY / a flag not yet exposed on
    the CLI and are covered by the mocked tests in ``TestRunSurfaceRepairRules``.
    """

    @staticmethod
    def _init(root: Path) -> None:
        from .integration._compat_support import run_spec_kitty

        result = run_spec_kitty(
            "init", "--ai", "claude", "--non-interactive", cwd=root
        )
        assert result.returncode == 0, result.stderr

    def test_rule1_missing_created_via_upgrade(self, tmp_path: Path) -> None:
        """Rule 1: a deleted profile dir is auto-created by ``upgrade`` (no prompt)."""
        import shutil

        from .integration._compat_support import run_spec_kitty

        self._init(tmp_path)
        # Prime the up-to-date path so the wiring marker exists.
        run_spec_kitty("upgrade", "--yes", cwd=tmp_path)

        agents = tmp_path / ".claude" / "agents"
        shutil.rmtree(agents)
        result = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert list(agents.glob("*.md")), "missing profiles must be auto-created"

    def test_rule4_drifted_reported_only_under_yes(self, tmp_path: Path) -> None:
        """Rule 4 / NFR-007: ``--yes`` reports drift, never overwrites, exits non-zero."""
        from .integration._compat_support import run_spec_kitty

        self._init(tmp_path)
        run_spec_kitty("upgrade", "--yes", cwd=tmp_path)

        agents = tmp_path / ".claude" / "agents"
        target = sorted(agents.glob("*.md"))[0]
        custom = "# user edit\n"
        target.write_text(custom, encoding="utf-8")

        result = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
        assert result.returncode != 0, "--yes must exit non-zero on unresolved drift"
        assert target.read_text(encoding="utf-8") == custom, (
            "drifted file must be preserved verbatim under --yes"
        )
        # #4925: a non-zero exit names its reason and never claims success.
        assert f"Not updated, your local edit was kept: .claude/agents/{target.name}" in result.stdout
        assert "spec-kitty doctor tool-surfaces" in result.stdout
        assert "already up to date" not in result.stdout.lower()
        assert result.stdout.rstrip().splitlines()[-1] == (
            "Upgrade finished, but 1 managed file(s) with local edits were not updated."
        )

    def test_rule4_drifted_reported_only_under_yes_json(
        self,
        tmp_path: Path,
    ) -> None:
        """Rule 4 applies equally to machine-readable ``upgrade --yes --json``."""
        from .integration._compat_support import run_spec_kitty

        self._init(tmp_path)
        run_spec_kitty("upgrade", "--yes", cwd=tmp_path)

        agents = tmp_path / ".claude" / "agents"
        target = sorted(agents.glob("*.md"))[0]
        custom = "# user edit\n"
        target.write_text(custom, encoding="utf-8")

        result = run_spec_kitty("upgrade", "--yes", "--json", cwd=tmp_path)
        assert result.returncode != 0, (
            "--yes --json must exit non-zero on unresolved drift"
        )
        payload = result.json()
        assert payload["status"] == "failed"
        assert payload["success"] is False
        assert payload["errors"]
        assert payload["errors"][0].startswith(
            f"Not updated, your local edit was kept: .claude/agents/{target.name}"
        )
        drifted = payload["surface_repair"]["drifted_reported"]
        assert any(Path(path).name == target.name for path in drifted)
        assert target.read_text(encoding="utf-8") == custom, (
            "drifted file must be preserved verbatim under --yes --json"
        )


class TestPromptOverwrite:
    def test_y_returns_true(self) -> None:
        with patch("builtins.input", return_value="y"):
            assert _prompt_overwrite(Path("/x")) is True

    def test_Y_returns_true(self) -> None:
        with patch("builtins.input", return_value="Y"):
            assert _prompt_overwrite(Path("/x")) is True

    def test_n_returns_false(self) -> None:
        with patch("builtins.input", return_value="N"):
            assert _prompt_overwrite(Path("/x")) is False

    def test_empty_returns_false(self) -> None:
        with patch("builtins.input", return_value=""):
            assert _prompt_overwrite(Path("/x")) is False

    def test_eoferror_returns_false(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            assert _prompt_overwrite(Path("/x")) is False


class TestRenderSurfaceSummaryLines:
    """FR-007: the summary reports *counts*, never raw Path-list reprs.

    Regression guard for RISK-1, where the ``skipped`` line interpolated the
    raw ``list[Path]`` instead of ``len(...)``.
    """

    def test_skipped_line_shows_count_not_list_repr(self) -> None:
        summary = DriftPolicySummary(
            skipped=[Path("/a/b.md"), Path("/c/d.md"), Path("/e/f.md")]
        )
        lines = render_surface_summary_lines(summary)
        assert lines == ["  3 surface(s) not applicable, skipped."]
        # The raw Path repr must never leak into the rendered text.
        joined = "\n".join(lines)
        assert "PosixPath" not in joined and "WindowsPath" not in joined
        assert "[" not in joined

    def test_empty_summary_renders_no_lines(self) -> None:
        assert render_surface_summary_lines(DriftPolicySummary()) == []

    def test_all_buckets_report_counts(self) -> None:
        summary = DriftPolicySummary(
            created=[Path("/c1")],
            repaired=[Path("/r1"), Path("/r2")],
            drifted_overwritten=[Path("/o1")],
            drifted_reported=[Path("/d1"), Path("/d2"), Path("/d3")],
            skipped=[Path("/s1")],
        )
        lines = render_surface_summary_lines(summary)
        assert lines == [
            "[dim]Created 1 tool surface(s)[/dim]",
            "[dim]Repaired 2 stale tool surface(s)[/dim]",
            "[dim]Overwrote 1 drifted tool surface(s)[/dim]",
            "[dim]Note: 3 tool surface(s) have local edits "
            "— run 'spec-kitty doctor tool-surfaces' to review[/dim]",
            "  1 surface(s) not applicable, skipped.",
        ]
