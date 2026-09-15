"""Direct project authoring must reach activation without pre-seeded graphs."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app
from tests.charter.test_project_registration import author_guidance

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


def test_activation_registers_project_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    sources = author_guidance(tmp_path)
    before = {key: path.read_bytes() for key, path in sources.items()}
    result = runner.invoke(app, ["activate", "agent-profile", "ops-responder"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".kittify/doctrine/graph.yaml").is_file()
    from charter.activation.synthesizer.manifest import load_yaml, verify

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    assert {a.kind for a in manifest.artifacts} == set(sources)
    assert {key: path.read_bytes() for key, path in sources.items()} == before
    from specify_cli.cli.commands.charter._status_collectors import _collect_manifest_status

    summary, _ = _collect_manifest_status(tmp_path)
    # The five artifact kinds are the contract (#4097): procedures and agent
    # profiles join directives, tactics and styleguides.
    assert summary["artifact_count"] == 5
    assert summary["live_artifact_count"] == 5
