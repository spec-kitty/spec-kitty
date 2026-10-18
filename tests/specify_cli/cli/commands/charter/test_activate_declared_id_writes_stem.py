"""#6406 blast radius: ``charter activate`` of a stem != declared id artifact writes the stem (#2529).

Activation by declared id on the CLI is gated by the stem-based availability set of
the activation engine and is outside WP01; this pins the producer contract (stems
stay the written form) now that ``resolve_artifact_urn`` accepts declared ids.
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


def _activated(root: Path) -> list[str]:
    config = yaml.safe_load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    return list(config["activated_tactics"])


def test_activate_tactic_by_stem_writes_stem(tactic_pack_project: Path) -> None:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(tactic_pack_project), "--no-compile", "tactic", "qa-tactic-seven"])
    assert result.exit_code == 0, result.output
    activated = _activated(tactic_pack_project)
    assert "qa-tactic-seven" in activated
    # Pre-existing: the materialised effective set may also list the org tactic
    # by declared id (narrowed by WP06); the contract here is the stem is written.


def test_activate_unknown_tactic_still_fails(tactic_pack_project: Path) -> None:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(tactic_pack_project), "--no-compile", "tactic", "qa-ghost"])
    assert result.exit_code != 0
