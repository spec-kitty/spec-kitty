"""Real compiler/builder/provider consumers at the upgrade composition boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
import yaml

from specify_cli import app
from specify_cli.tool_surface.operations import ApplyConsent
from specify_cli.upgrade.assessment import apply_upgrade_repairs, preflight_upgrade_repairs, prepare_upgrade_repairs
from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("key_present", [False, True], ids=["missing-key", "explicit-empty"])
def test_real_composer_retains_descriptor_and_applies_cold_owners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key_present: bool) -> None:
    """One retained assessment must survive its own authorized provisioning."""
    project = tmp_path / "project"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "setup-home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "setup-home"))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "setup-home/.kittify"))
    initialized = CliRunner().invoke(app, ["init", str(project), "--ai", "codex", "--non-interactive"])
    assert initialized.exit_code == 0, initialized.output
    config_path = project / ".kittify/config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config.pop("charter", None)
    config.pop("mission_type_activations", None)
    if key_present:
        config["mission_type_activations"] = []
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    missing = project / ".agents/skills/spec-kitty-plan/SKILL.md"
    expected_command = missing.read_bytes()
    missing.unlink()
    home = tmp_path / "cold-home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    roots = {"project": project, "home": home}
    before = snapshot(roots)
    prepared = prepare_upgrade_repairs(project, consent=ApplyConsent(automatic=True))
    assert prepared.complete, prepared.diagnostics
    assert prepared.composition is not None
    assert prepared.composition.commands.prepared.provisioning is prepared.provisioning
    assert prepared.installation.project_skills.prepared.provisioning is prepared.provisioning
    assert_unchanged(before, snapshot(roots))
    with preflight_upgrade_repairs(prepared) as errors:
        assert not errors, errors
        assert_unchanged(before, snapshot(roots))
        assert prepared.provisioning.apply() is not key_present
        results = apply_upgrade_repairs(prepared)
    assert all(result.outcome in {"applied", "skipped"} for result in results), results
    assert missing.read_bytes() == expected_command
    assert config_path.read_bytes() == prepared.provisioning.write.desired_bytes
    expected = {(effect.destination, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode) for effect in prepared.effects}
    actual = {
        (roots[effect.root] / effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
        for effect in net_delta(before, snapshot(roots))
    }
    assert expected == actual
