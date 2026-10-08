"""Public charter authoring parity regression for #4098."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


@pytest.mark.parametrize("kind", ["directive", "tactic", "styleguide", "procedure", "agent_profile"])
def test_charter_scaffold_and_validate(kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kittify").mkdir()
    artifact_id = "SAMPLE" if kind == "directive" else "sample"
    result = runner.invoke(app, ["new", kind, artifact_id])
    assert result.exit_code == 0, result.output
    assert "deprecated" not in result.output.lower()
    result = runner.invoke(app, ["validate", ".kittify/charter-packs"])
    assert result.exit_code == 0, result.output
    assert "1 artifact(s) passed validation" in result.output
    assert runner.invoke(app, ["new", kind, artifact_id]).exit_code == 1


def test_charter_org_and_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".kittify").mkdir()
    result = runner.invoke(app, ["org", "init", "org-pack"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "org-pack" / "org-charter.yaml").is_file()
    result = runner.invoke(app, ["org", "validate", "org-pack"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["fetch", "--dry-run"])
    assert result.exit_code == 1
    assert "No org charter packs configured" in result.output
