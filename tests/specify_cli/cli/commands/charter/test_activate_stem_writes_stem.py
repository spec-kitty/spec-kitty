"""#6406 blast radius: ``charter activate`` of a stem != declared id artifact writes the stem (#2529).

Activation by stem writes the stem (the producer contract, now that
``resolve_artifact_urn`` accepts declared ids). Activation by *declared id*
writes the stem too (#6423), and the materialised list never holds the declared
id beside it (#6435, #6527).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.integration]


@pytest.fixture()
def tactic_pack_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One org pack holding tactic stem ``qa-tactic-seven`` declaring ``id: qa-seven``."""
    tactics = tmp_path / "packs" / "acme" / "tactics"
    tactics.mkdir(parents=True)
    (tactics / "qa-tactic-seven.tactic.yaml").write_text(
        "schema_version: '1.0'\nid: qa-seven\nname: Seven\npurpose: Seven.\nsteps:\n  - title: Do\n    description: Do it.\n", encoding="utf-8"
    )
    config = {
        "mission_type_activations": ["software-dev"],
        "charter_packs": {"org": {"packs": [{"name": "acme", "local_path": "packs/acme"}]}},
    }
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(charter_pkg, "find_repo_root", lambda: tmp_path)
    return tmp_path


def _seed_present_tactic_list(root: Path) -> None:
    """A present ``activated_tactics`` list in config.yaml, so an activation has somewhere to write (#6685)."""
    config_path = root / ".kittify" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["activated_tactics"] = ["acceptance-test-first"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")


def _activated(root: Path) -> list[str]:
    config = yaml.safe_load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    return list(config["activated_tactics"])


def test_activate_tactic_by_stem_writes_stem(tactic_pack_project: Path) -> None:
    # #6685: an in-force artifact is not written into an absent key, so a present list is seeded first.
    _seed_present_tactic_list(tactic_pack_project)
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(tactic_pack_project), "--no-compile", "tactic", "qa-tactic-seven"])
    assert result.exit_code == 0, result.output
    activated = _activated(tactic_pack_project)
    assert "qa-tactic-seven" in activated
    # Re-pin (#6435): the written list holds the org tactic once, by its stem.
    assert "qa-seven" not in activated


def test_activate_tactic_by_declared_id_writes_stem(tactic_pack_project: Path) -> None:
    _seed_present_tactic_list(tactic_pack_project)
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(tactic_pack_project), "--no-compile", "tactic", "qa-seven"])
    assert result.exit_code == 0, result.output
    assert "qa-tactic-seven" in _activated(tactic_pack_project)


def test_activate_unknown_tactic_still_fails(tactic_pack_project: Path) -> None:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(tactic_pack_project), "--no-compile", "tactic", "qa-ghost"])
    assert result.exit_code != 0
