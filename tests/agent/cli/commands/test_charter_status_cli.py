"""CLI tests for `spec-kitty charter status` operator surfaces."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app
from specify_cli.cli.commands.charter._status_collectors import _collect_governance_reference_status
from specify_cli.task_utils import TaskCliError

pytestmark = pytest.mark.fast

runner = CliRunner()


VALID_DIRECTIVE_BODY = {
    "id": "PROJECT_001",
    "schema_version": "1.0",
    "title": "Mission Scope Directive",
    "intent": "Capture project mission scope for governance synthesis tests.",
    "enforcement": "required",
}


def _write_interview_answers(repo_root: Path) -> None:
    answers_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.write_text(
        """\
schema_version: '1'
mission: software-dev
profile: minimal
answers:
  mission_type: software_dev
  testing_philosophy: ''
  neutrality_posture: ''
  risk_appetite: ''
selected_paradigms: []
selected_directives: []
available_tools: []
""",
        encoding="utf-8",
    )


def _write_url_config(repo_root: Path) -> None:
    config_path = repo_root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """\
charter:
  synthesis_inputs:
    url_list:
      - https://example.com/governance
""",
        encoding="utf-8",
    )


def _write_governance_yaml(repo_root: Path) -> None:
    """Write the ``governance:`` section into the consolidated ``charter.yaml``.

    IC-04 (#2773) retired the standalone ``.kittify/charter/governance.yaml``:
    ``load_governance_config`` now reads the hand-authored ``governance:``
    section directly off ``charter.yaml`` (``charter.activation.schemas.CharterYaml``).
    The governance references live at ``governance.charter.governance_references``.
    """
    path = repo_root / ".kittify" / "charter" / "charter.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """\
schema_version: '2.0.0'
governance:
  doctrine:
    governance_references:
      - spec/constitution.md
      - docs/missing-governance.md
""",
        encoding="utf-8",
    )


def _seed_complete_bundle(repo_root: Path) -> None:
    """Materialize the authoritative ``charter.yaml`` so the #2773 fail-closed
    preflight (``_raise_if_bundle_incomplete``) passes and the real-run
    synthesize path is reached.

    Mirrors ``_seed_complete_bundle`` in
    ``tests/agent/cli/commands/test_charter_synthesize_cli.py``:
    ``first_missing_bundle_file`` is a pure existence check over
    ``BUNDLE_CONTENT_HASH_FILES == ("charter.yaml",)``, so seeding this one
    file at the fixed path is sufficient. It is independent of the config
    ``charter:`` key, which this test intentionally keeps in the inline
    ``synthesis_inputs`` shape so ``url_list`` stays configured.
    """
    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.parent.mkdir(parents=True, exist_ok=True)
    charter_yaml.write_text(
        "schema_version: '2.0.0'\n"
        "governance: {}\n"
        "directives: {}\n"
        "metadata:\n"
        "  bundle_schema_version: 2\n",
        encoding="utf-8",
    )


def _write_generated_directive(repo_root: Path, body: dict[str, object]) -> None:
    path = (
        repo_root
        / ".kittify"
        / "charter"
        / "generated"
        / "directives"
        / "001-mission-type-scope-directive.directive.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(body, fh)


class TestCharterStatus:
    def test_status_collector_reports_missing_governance_reference(
        self, tmp_path: Path
    ) -> None:
        _write_governance_yaml(tmp_path)
        (tmp_path / "spec").mkdir()
        (tmp_path / "spec" / "constitution.md").write_text("# Public Constitution\n", encoding="utf-8")

        status = _collect_governance_reference_status(tmp_path)

        assert status["available"] is True
        assert len(status["references"]) == 2
        assert status["warnings"] == [
            "Missing governance reference docs/missing-governance.md. Create it under the repository root "
            "or remove it from governance_references in .kittify/charter/charter.md."
        ]

    def test_status_json_gracefully_degrades_without_charter_bundle(
        self, tmp_path: Path
    ) -> None:
        _write_url_config(tmp_path)

        with patch(
            "specify_cli.cli.commands.charter.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            side_effect=TaskCliError("Charter not found"),
        ):
            result = runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["charter_sync"]["available"] is False
        assert data["synthesis"]["generation_state"] == "not_started"
        assert data["synthesis"]["evidence"]["configured_url_count"] == 1

    def test_generated_host_roundtrip_status_reports_promoted_provenance(
        self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
    ) -> None:
        _write_interview_answers(tmp_path)
        _write_url_config(tmp_path)
        _seed_complete_bundle(tmp_path)
        _write_generated_directive(tmp_path, VALID_DIRECTIVE_BODY)
        charter_cwd_isolation()

        with patch(
            "specify_cli.cli.commands.charter.find_repo_root",
            return_value=tmp_path,
        ):
            synth_result = runner.invoke(app, ["synthesize"])
        assert synth_result.exit_code == 0, synth_result.output

        doctrine_path = (
            tmp_path
            / ".kittify"
            / "charter-packs"
            / "directive"
            / "001-mission-type-scope-directive.directive.yaml"
        )
        provenance_path = (
            tmp_path
            / ".kittify"
            / "charter"
            / "provenance"
            / "directive-mission-type-scope-directive.yaml"
        )
        manifest_path = (
            tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
        )

        assert doctrine_path.exists()
        assert provenance_path.exists()
        assert manifest_path.exists()

        updated_body = dict(VALID_DIRECTIVE_BODY)
        updated_body["title"] = "Mission Scope Directive Updated"
        updated_body["intent"] = "Updated mission scope after host-directed resynthesis."
        _write_generated_directive(tmp_path, updated_body)

        with patch(
            "specify_cli.cli.commands.charter.find_repo_root",
            return_value=tmp_path,
        ):
            resynth_result = runner.invoke(
                app,
                ["resynthesize", "--topic", "directive:PROJECT_001"],
            )
        assert resynth_result.exit_code == 0, resynth_result.output

        yaml = YAML(typ="safe")
        doctrine_data = yaml.load(doctrine_path.read_text(encoding="utf-8"))
        assert doctrine_data["title"] == "Mission Scope Directive Updated"
        assert "host-directed resynthesis" in doctrine_data["intent"]

        with patch(
            "specify_cli.cli.commands.charter.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            side_effect=TaskCliError("Charter not found"),
        ):
            status_result = runner.invoke(app, ["status", "--json", "--provenance"])

        assert status_result.exit_code == 0, status_result.output
        data = json.loads(status_result.output)
        # FR-005 (charter-pack-usage-journey WP03): ``_collect_charter_sync_status``
        # now keys presence on the authoritative ``charter.yaml`` (seeded by
        # ``_seed_complete_bundle`` above) via the CLI sibling resolver, not the
        # display-only ``charter.md`` this fixture never writes -- so this
        # collector correctly reports ``available: True`` here. It never calls
        # ``ensure_charter_bundle_fresh`` (read-only per its own docstring /
        # FR-010), so the patched ``side_effect`` above does not affect this
        # field; it existed to isolate `status` from that write path, not to
        # force an "unavailable" charter_sync result.
        assert data["charter_sync"]["available"] is True
        assert data["synthesis"]["generation_state"] == "promoted"
        assert data["synthesis"]["manifest"]["state"] == "valid"
        assert data["synthesis"]["generated_inputs"]["counts"]["directive"] == 1
        assert data["synthesis"]["provenance"]["parsed_count"] == 1
        assert data["synthesis"]["evidence"]["configured_url_count"] == 1
        entry = data["synthesis"]["provenance"]["entries"][0]
        assert entry["artifact_urn"] == "directive:PROJECT_001"
        assert entry["adapter_id"] == "generated"
