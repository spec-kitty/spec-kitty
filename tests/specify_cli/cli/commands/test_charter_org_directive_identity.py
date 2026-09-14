"""Acceptance contract for org directive adoption through the real charter CLI (#4185)."""

from pathlib import Path
import subprocess

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.mark.parametrize("project_override", [False, True])
@pytest.mark.parametrize("directive_id", ["ACME-001-FOO", "ACME_001_FOO"])
@pytest.mark.parametrize("intake", ["required", "selected", "activated"])
def test_org_directive_interview_and_generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directive_id: str, intake: str, project_override: bool) -> None:
    """A declared ID distinct from its filename survives every supported intake."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    packs = [tmp_path / "company", tmp_path / "team"]
    for pack in packs:
        (pack / "directives").mkdir(parents=True)
    (packs[1] / "directives/foo.directive.yaml").write_text(
        f'schema_version: "1.0"\nid: {directive_id}\ntitle: Acme Policy\nintent: Require independent Acme validation.\nenforcement: required\n'
    )
    expected_stem = "foo"
    if project_override:
        project_dir = tmp_path / ".kittify/doctrine/directive"
        project_dir.mkdir(parents=True)
        (project_dir / "project-policy.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {directive_id}\ntitle: Acme Policy\nintent: Require independent Acme validation.\nenforcement: required\n'
        )
        expected_stem = "project-policy"
    if intake == "required":
        (packs[1] / "org-charter.yaml").write_text(f"org_name: Acme\nrequired_directives:\n  - {directive_id}\n")
    config = {
        "charter_packs": {"org": {"packs": [{"name": pack.name, "local_path": str(pack)} for pack in packs]}},
        "activated_directives": [directive_id] if intake == "activated" else [],
    }
    yaml = YAML()
    with (tmp_path / ".kittify/config.yaml").open("w") as stream:
        yaml.dump(config, stream)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    service = build_activation_aware_doctrine_service(tmp_path)
    raw = service.raw_repository("directives")
    assert directive_id in {item.id for item in raw.list_all()}
    if intake != "activated":
        assert directive_id not in service.directives
    runner = CliRunner()
    args = ["interview", "--mission-type", "software-dev", "--profile", "minimal", "--defaults", "--json"]
    if intake == "selected":
        args += ["--selected-directives", directive_id]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Could not resolve selected directive" not in result.output
    if intake != "activated":
        saved = yaml.load((tmp_path / ".kittify/config.yaml").read_text())
        assert expected_stem in saved["activated_directives"]
        assert directive_id not in saved["activated_directives"]
    generated = runner.invoke(app, ["generate", "--from-interview", "--json"])
    assert generated.exit_code == 0, generated.output
    bundle = yaml.load((tmp_path / ".kittify/charter/charter.yaml").read_text())
    expected_activation = directive_id if intake == "activated" else expected_stem
    assert expected_activation in bundle["activated_directives"]
    assert raw.get(directive_id) is not None
    delivered = build_activation_aware_doctrine_service(tmp_path).directives
    assert directive_id in delivered, "Promoted org policy must be delivered, not merely compiled"
    assert delivered[directive_id].title == "Acme Policy"
    assert delivered[directive_id].intent == "Require independent Acme validation."


@pytest.mark.parametrize("intake", ["required", "selected"])
def test_colliding_override_stem_preserves_selected_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, intake: str) -> None:
    """A project filename cannot redirect adoption to a different built-in ID."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    project_dir = tmp_path / ".kittify/doctrine/directive"
    project_dir.mkdir(parents=True)
    (project_dir / "025-boy-scout-rule.directive.yaml").write_text(
        'schema_version: "1.0"\nid: DIRECTIVE_001\ntitle: Project architecture\nintent: Require project architecture review.\nenforcement: required\n'
    )
    org = tmp_path / "org"
    org.mkdir()
    if intake == "required":
        (org / "org-charter.yaml").write_text("org_name: Acme\nrequired_directives:\n  - DIRECTIVE_001\n")
    yaml = YAML()
    with (tmp_path / ".kittify/config.yaml").open("w") as stream:
        yaml.dump({"charter_packs": {"org": {"packs": [{"name": "org", "local_path": str(org)}]}}, "activated_directives": []}, stream)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    args = ["interview", "--mission-type", "software-dev", "--profile", "minimal", "--defaults", "--json"]
    if intake == "selected":
        args += ["--selected-directives", "DIRECTIVE_001"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    saved = yaml.load((tmp_path / ".kittify/config.yaml").read_text())
    assert saved["activated_directives"] == ["001-architectural-integrity-standard"]
    delivered = build_activation_aware_doctrine_service(tmp_path).directives
    assert "DIRECTIVE_025" not in delivered
    assert delivered["DIRECTIVE_001"].title == "Project architecture"
    assert delivered["DIRECTIVE_001"].intent == "Require project architecture review."
