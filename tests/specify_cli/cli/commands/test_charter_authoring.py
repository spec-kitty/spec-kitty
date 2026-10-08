"""Public charter authoring parity regression for #4098."""

from pathlib import Path

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app
from specify_cli.cli.commands.doctrine import app as doctrine_app

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


@pytest.mark.parametrize("command", [("new",), ("validate",), ("fetch",), ("org", "init"), ("org", "validate")])
def test_authoring_surface_preserves_options(command: tuple[str, ...]) -> None:
    charter = get_command(app)
    doctrine = get_command(doctrine_app)
    for name in command:
        charter = charter.commands[name]
        doctrine = doctrine.commands[name]
    assert [(p.name, p.opts, p.required, p.default) for p in charter.params] == [(p.name, p.opts, p.required, p.default) for p in doctrine.params]


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
    assert "No org doctrine packs configured" in result.output


def test_deprecation_names_remaining_surfaces(tmp_path: Path) -> None:
    result = runner.invoke(doctrine_app, ["validate", str(tmp_path / "missing")])
    for remaining in ("regenerate-graph", "pack validate", "pack assemble", "asset", "mission-type list"):
        assert remaining in result.output
