"""WP12 — charter activate/deactivate CLI wiring (FR-013/014/020/035).

Black-box CLI tests (DIRECTIVE_036) exercising the live wiring of the WP10
activation engine and the WP11 scoped cascade engine through the CLI surface:

* T053 — ``--cascade`` scope is threaded (not collapsed to a bool): selected
  kinds activate only those kinds; ``--cascade all`` activates every referenced
  kind; absence emits a no-cascade warning (FR-013/014, Contract C3.3).
* T054 — invalid pack config fails closed: a clean exit-1 with the
  ``ACTIVE_CHARTER_CONFIG_INVALID`` code and no mutation (FR-035, C1.5).
* T056 — the dead ``charter_activate_app`` / ``charter_deactivate_app`` exports
  are gone; the callbacks are the live exports and the commands stay registered.
* T058 — cascade + no-cascade rendering, malformed-config fail-closed.

The cascade tests use the real built-in doctrine corpus: ``architect-alphonso``
references both directives and tactics (plus other kinds) in the DRG.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.integration]

# A real built-in agent profile whose DRG node references directives + tactics
# (and other kinds) — used to exercise scoped cascade activation.
_CASCADE_SOURCE_KIND = "agent-profile"
_CASCADE_SOURCE_ID = "architect-alphonso"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A minimal project with an empty .kittify/config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("# empty config\n", encoding="utf-8")
    return tmp_path


def _config(project_root: Path) -> dict:
    raw = (project_root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


def _activate(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _deactivate(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["deactivate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _list(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["list", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _write_directive(directory: Path, stem: str, artifact_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.directive.yaml").write_text(
        textwrap.dedent(
            f"""\
            id: {artifact_id}
            schema_version: "1.0"
            title: {artifact_id}
            intent: Enforce project operational guidance.
            enforcement: required
            """
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T056 — command registration + dead-export removal
# ---------------------------------------------------------------------------


class TestRegistration:
    def _assert_cascade_option_registered(self, command_name: str) -> None:
        click_group = get_command(charter_app)
        click_command = click_group.commands[command_name]
        cascade_options = [
            param
            for param in click_command.params
            if getattr(param, "name", None) == "cascade"
        ]
        assert cascade_options, f"{command_name} command is missing cascade parameter"
        assert "--cascade" in cascade_options[0].opts
        assert "Cascade" in cascade_options[0].help

    def test_activate_registered(self) -> None:
        result = runner.invoke(charter_app, ["activate", "--help"], terminal_width=160)
        assert result.exit_code == 0, result.output
        self._assert_cascade_option_registered("activate")

    def test_deactivate_registered(self) -> None:
        result = runner.invoke(charter_app, ["deactivate", "--help"], terminal_width=160)
        assert result.exit_code == 0, result.output
        self._assert_cascade_option_registered("deactivate")

    def test_dead_subapp_exports_removed(self) -> None:
        """``charter_activate_app`` / ``charter_deactivate_app`` are gone (FR-020)."""
        import specify_cli.cli.commands.charter.activate as activate_mod
        import specify_cli.cli.commands.charter.deactivate as deactivate_mod

        assert not hasattr(activate_mod, "charter_activate_app")
        assert not hasattr(deactivate_mod, "charter_deactivate_app")
        # FR-020 pins that the DEAD ``charter_activate_app`` sub-app export is
        # gone (the two ``assert not hasattr`` lines above). ``activate.py``
        # legitimately also exports ``run_full_synthesize`` (renamed from
        # ``run_resynthesize_pipeline`` — FR-013 naming-footgun fix, WP05: the
        # function calls the FULL synthesize pipeline, not a bounded
        # resynthesize) — the public activate=>refresh-or-fail-closed
        # freshness seam entry point added by #2519 (it is imported by the
        # ``charter status``/resynthesize CLI). It is a live public symbol,
        # not a dead sub-app, so it belongs in ``__all__``.
        assert activate_mod.__all__ == ["activate_cmd", "run_full_synthesize"]
        assert deactivate_mod.__all__ == ["deactivate_cmd"]


class TestLayerAwareActivation:
    def test_org_artifact_listed_by_all_can_be_activated_and_deactivated(
        self, project_root: Path, tmp_path: Path
    ) -> None:
        org_pack = tmp_path / "org-pack"
        _write_directive(
            org_pack / "doctrine" / "directives" / "org",
            "900-org-only-directive",
            "DIRECTIVE_900",
        )
        (project_root / ".kittify" / "config.yaml").write_text(
            textwrap.dedent(
                f"""\
                doctrine:
                  org:
                    packs:
                      - name: acme
                        local_path: {org_pack}
                """
            ),
            encoding="utf-8",
        )

        listed = _list(project_root, "--all")
        assert listed.exit_code == 0, listed.output
        assert "900-org-only-directive" in listed.output

        activated = _activate(project_root, "directive", "900-org-only-directive")
        assert activated.exit_code == 0, activated.output
        data = _config(project_root)
        assert "900-org-only-directive" in data["activated_directives"]

        deactivated = _deactivate(project_root, "directive", "900-org-only-directive")
        assert deactivated.exit_code == 0, deactivated.output
        data = _config(project_root)
        assert "900-org-only-directive" not in data["activated_directives"]

    def test_project_artifact_listed_by_all_can_be_activated(
        self, project_root: Path
    ) -> None:
        _write_directive(
            project_root / ".kittify" / "doctrine" / "directive",
            "950-project-only-directive",
            "DIRECTIVE_950",
        )

        listed = _list(project_root, "--all")
        assert listed.exit_code == 0, listed.output
        assert "950-project-only-directive" in listed.output

        activated = _activate(project_root, "directive", "950-project-only-directive")
        assert activated.exit_code == 0, activated.output
        data = _config(project_root)
        assert "950-project-only-directive" in data["activated_directives"]


# ---------------------------------------------------------------------------
# T053 — cascade scope threaded (not a bool)
# ---------------------------------------------------------------------------


class TestCascadeScope:
    def test_cascade_all_activates_referenced_kinds(self, project_root: Path) -> None:
        """``--cascade all`` activates referenced directives AND tactics."""
        result = _activate(
            project_root,
            "--cascade",
            "all",
            _CASCADE_SOURCE_KIND,
            _CASCADE_SOURCE_ID,
        )
        assert result.exit_code == 0, result.output
        data = _config(project_root)
        # Source itself activated.
        assert _CASCADE_SOURCE_ID in (data.get("activated_agent_profiles") or [])
        # Cascade pulled in both directives and tactics (multiple kinds).
        assert data.get("activated_directives"), result.output
        assert data.get("activated_tactics"), result.output

    def test_cascade_scope_limits_to_selected_kind(self, project_root: Path) -> None:
        """``--cascade directive`` activates directives only, NOT tactics."""
        result = _activate(
            project_root,
            "--cascade",
            "directive",
            _CASCADE_SOURCE_KIND,
            _CASCADE_SOURCE_ID,
        )
        assert result.exit_code == 0, result.output
        data = _config(project_root)
        assert data.get("activated_directives"), result.output
        # Tactics were referenced but OUT of scope — not activated.
        assert not data.get("activated_tactics")
        # Out-of-scope kinds are reported so the operator sees the exclusion.
        assert "out of scope" in result.output.lower()

    def test_cascade_scope_is_not_collapsed_to_bool(self, project_root: Path) -> None:
        """A multi-kind scope is honored distinctly from 'all' (no bool collapse)."""
        result = _activate(
            project_root,
            "--cascade",
            "directive,paradigm",
            _CASCADE_SOURCE_KIND,
            _CASCADE_SOURCE_ID,
        )
        assert result.exit_code == 0, result.output
        data = _config(project_root)
        assert data.get("activated_directives")
        assert data.get("activated_paradigms")
        # Tactics referenced but not in the explicit scope.
        assert not data.get("activated_tactics")

    def test_bad_cascade_token_exits_1(self, project_root: Path) -> None:
        """An unknown kind token in the scope fails with a structured error."""
        result = _activate(
            project_root,
            "--cascade",
            "not-a-kind",
            _CASCADE_SOURCE_KIND,
            _CASCADE_SOURCE_ID,
        )
        assert result.exit_code == 1
        # No mutation on a bad scope.
        assert "not-a-kind" not in str(_config(project_root))


# ---------------------------------------------------------------------------
# T053/FR-013 — no-cascade warning
# ---------------------------------------------------------------------------


class TestNoCascadeWarning:
    def test_absent_cascade_warns_about_referenced(self, project_root: Path) -> None:
        """Without --cascade, referenced artifacts are reported as a warning (FR-013)."""
        result = _activate(project_root, _CASCADE_SOURCE_KIND, _CASCADE_SOURCE_ID)
        assert result.exit_code == 0, result.output
        # Direct activation still happened.
        data = _config(project_root)
        assert _CASCADE_SOURCE_ID in (data.get("activated_agent_profiles") or [])
        # But referenced kinds were NOT cascaded.
        assert not data.get("activated_directives")
        # The no-cascade warning + recovery hint surfaced.
        assert "not activated" in result.output.lower()
        assert "--cascade" in result.output

    def test_no_cascade_does_not_activate_referenced(self, project_root: Path) -> None:
        """Absent --cascade never means 'all' (Contract C3.3)."""
        _activate(project_root, _CASCADE_SOURCE_KIND, _CASCADE_SOURCE_ID)
        data = _config(project_root)
        assert not data.get("activated_tactics")
        assert not data.get("activated_directives")


# ---------------------------------------------------------------------------
# T054 / FR-035 — fail-closed on malformed pack config
# ---------------------------------------------------------------------------


class TestFailClosedConfig:
    @pytest.fixture()
    def malformed_project(self, tmp_path: Path) -> Path:
        """A project whose config.yaml has an invalid charter-pack shape."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        # A non-list activation key is rejected by PackContext.from_config.
        (kittify / "config.yaml").write_text(
            "activated_directives: not-a-list\n", encoding="utf-8"
        )
        return tmp_path

    def test_activate_fails_closed(self, malformed_project: Path) -> None:
        before = (malformed_project / ".kittify" / "config.yaml").read_bytes()
        result = _activate(malformed_project, "directive", "001-architectural-integrity-standard")
        assert result.exit_code == 1
        assert "ACTIVE_CHARTER_CONFIG_INVALID" in result.output
        # No mutation: config bytes unchanged.
        after = (malformed_project / ".kittify" / "config.yaml").read_bytes()
        assert before == after

    def test_deactivate_fails_closed(self, malformed_project: Path) -> None:
        before = (malformed_project / ".kittify" / "config.yaml").read_bytes()
        result = _deactivate(malformed_project, "directive", "001-architectural-integrity-standard")
        assert result.exit_code == 1
        assert "ACTIVE_CHARTER_CONFIG_INVALID" in result.output
        after = (malformed_project / ".kittify" / "config.yaml").read_bytes()
        assert before == after

    def test_fail_closed_mentions_remediation(self, malformed_project: Path) -> None:
        result = _activate(malformed_project, "directive", "001-architectural-integrity-standard")
        assert "spec-kitty upgrade" in result.output or "config.yaml" in result.output


# ---------------------------------------------------------------------------
# T055 — mission-type warning still emitted via the generalized seam
# ---------------------------------------------------------------------------


class TestMissionTypeGeneralized:
    def test_mission_type_activation_still_works(self, project_root: Path) -> None:
        """mission-type activation works without a special-cased CLI branch."""
        result = _activate(project_root, "mission-type", "software-dev")
        assert result.exit_code == 0, result.output
        data = _config(project_root)
        assert "software-dev" in (data.get("mission_type_activations") or [])


# ---------------------------------------------------------------------------
# FR-005 — deactivation fail-closed + happy path
# ---------------------------------------------------------------------------


class TestDeactivate:
    def test_none_state_exits_1_with_guidance(self, project_root: Path) -> None:
        """A None-state kind surfaces the engine error as a clean exit-1 (WP12)."""
        result = _deactivate(project_root, "directive", "some-directive")
        assert result.exit_code == 1
        assert "spec-kitty upgrade" in result.output

    def test_deactivate_removes_from_config(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text(
            "activated_directives:\n  - some-directive\n", encoding="utf-8"
        )
        result = _deactivate(tmp_path, "directive", "some-directive")
        assert result.exit_code == 0, result.output
        data = _config(tmp_path)
        assert "some-directive" not in (data.get("activated_directives") or [])
