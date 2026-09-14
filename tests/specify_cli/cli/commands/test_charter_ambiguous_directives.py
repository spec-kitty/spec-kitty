"""Ambiguous selections report skips; mandatory policy prevents generation."""

import json
from pathlib import Path
import subprocess

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from charter.activation.kind_vocabulary import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.mark.parametrize("required", [False, True])
def test_ambiguous_directive_keeps_siblings_and_reports_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    packs = [tmp_path / "company", tmp_path / "team"]
    for pack, identity in zip(packs, ["COMPANY-SEC", "TEAM-SEC"], strict=True):
        (pack / "directives").mkdir(parents=True)
        (pack / "directives/security.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {identity}\ntitle: {identity}\nintent: Require security review.\nenforcement: required\n'
        )
    # Also collide with the raw ID: persisting it as a sentinel would activate
    # COMPANY-SEC under the guise of TEAM-SEC instead of rejecting ambiguity.
    (packs[0] / "directives/TEAM-SEC.directive.yaml").write_text(
        'schema_version: "1.0"\nid: COMPANY-SEC\ntitle: Company security\nintent: Require company review.\nenforcement: required\n'
    )
    paradigm = sorted(built_in_dir(ArtifactKind.PARADIGM).glob("*.paradigm.yaml"))[0].name.removesuffix(".paradigm.yaml")
    tactic = sorted(built_in_dir(ArtifactKind.TACTIC).glob("*.tactic.yaml"))[0].name.removesuffix(".tactic.yaml")
    if required:
        (packs[1] / "org-charter.yaml").write_text(
            f"org_name: Team\nrequired_directives: [TEAM-SEC, DIRECTIVE_001]\nrequired_tactics: [{tactic}]\nrequired_paradigms: [{paradigm}]\n"
        )
    yaml = YAML()
    config = {
        "charter_packs": {"org": {"packs": [{"name": pack.name, "local_path": str(pack)} for pack in packs]}},
        "activated_directives": [],
        "activated_tactics": [],
        "activated_paradigms": [],
    }
    with (tmp_path / ".kittify/config.yaml").open("w") as stream:
        yaml.dump(config, stream)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    args = ["interview", "--mission-type", "software-dev", "--profile", "minimal", "--defaults", "--json"]
    if not required:
        args += ["--selected-directives", "TEAM-SEC,DIRECTIVE_001", "--selected-paradigms", paradigm]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["promotion_warnings"], payload
    assert any("TEAM-SEC" in warning for warning in payload["promotion_warnings"])
    saved = yaml.load((tmp_path / ".kittify/config.yaml").read_text())
    assert saved["activated_directives"] == ["001-architectural-integrity-standard"]
    assert paradigm in saved["activated_paradigms"]
    if required:
        assert tactic in saved["activated_tactics"]
    delivered = build_activation_aware_doctrine_service(tmp_path).directives
    assert "DIRECTIVE_001" in delivered
    assert "TEAM-SEC" not in delivered
    assert "COMPANY-SEC" not in delivered
    config_before = (tmp_path / ".kittify/config.yaml").read_bytes()
    generated = CliRunner().invoke(app, ["generate", "--from-interview", "--json"])
    if required:
        assert generated.exit_code != 0, generated.output
        assert "TEAM-SEC" in generated.output
        assert (tmp_path / ".kittify/config.yaml").read_bytes() == config_before
        assert not (tmp_path / ".kittify/charter/charter.yaml").exists()
    else:
        assert generated.exit_code == 0, generated.output


def test_generate_rejects_ambiguous_required_directive_without_interview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    directory = tmp_path / ".kittify/doctrine/directive"
    directory.mkdir(parents=True)
    (directory / "025-boy-scout-rule.directive.yaml").write_text(
        'schema_version: "1.0"\nid: REQUIRED-POLICY\ntitle: Required\nintent: Require review.\nenforcement: required\n'
    )
    org = tmp_path / "org"
    org.mkdir()
    (org / "org-charter.yaml").write_text("org_name: Org\nrequired_directives: [REQUIRED-POLICY]\n")
    config = tmp_path / ".kittify/config.yaml"
    config.write_text(f"charter_packs:\n  org:\n    packs:\n      - name: org\n        local_path: '{org}'\nactivated_directives: []\n")
    before = config.read_bytes()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["generate", "--no-from-interview", "--mission-type", "software-dev", "--json"])
    assert result.exit_code != 0, result.output
    assert "REQUIRED-POLICY" in result.output
    assert config.read_bytes() == before
    assert not (tmp_path / ".kittify/charter/charter.yaml").exists()
