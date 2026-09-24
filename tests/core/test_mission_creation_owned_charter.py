"""An explicitly owned checkout supplies its own charter and templates."""

from pathlib import Path
import subprocess

import pytest

from charter.activation.pack_context import CharterPackConfigError
from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.mark.parametrize("owned_active", [True, False])
def test_owned_checkout_controls_charter_and_template(tmp_path, monkeypatch, owned_active):
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "main")
    _git(primary, "config", "user.email", "test@example.com")
    _git(primary, "config", "user.name", "Test")
    (primary / ".kittify").mkdir()
    (primary / ".kittify/config.yaml").write_text("mission_type_activations: []\n")
    _git(primary, "add", ".")
    _git(primary, "commit", "-m", "initial")
    owned = tmp_path / "owned"
    _git(primary, "worktree", "add", "-b", "feature", str(owned))
    active = owned if owned_active else primary
    (active / ".kittify/config.yaml").unlink()
    provision_test_charter(active)
    monkeypatch.chdir(owned)

    class TemplateReached(Exception):
        pass

    def resolve_template(name, root, context):
        assert name == "spec"
        assert root == owned
        raise TemplateReached

    monkeypatch.setattr("specify_cli.runtime.resolver.resolve_configured_template", resolve_template)
    expected = TemplateReached if owned_active else CharterPackConfigError
    with pytest.raises(expected):
        create_mission_core(
            primary,
            "owned-charter",
            owned_checkout=owned,
            topology=MissionTopology.SINGLE_BRANCH,
            friendly_name="Owned charter",
            purpose_tldr="Resolve the selected checkout charter.",
            purpose_context="Keep mission creation bound to the explicitly owned checkout configuration.",
        )
    assert not (primary / "kitty-specs").exists()
    assert not (owned / "kitty-specs").exists()
