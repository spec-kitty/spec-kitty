"""Project activation resolution follows the same overlay roots as profile loading."""

from pathlib import Path

import pytest

from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.kind_vocabulary import UnknownArtifactIdError, resolve_artifact_urn
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.unit]


def _profile(root: Path, value: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "local.agent.yaml").write_text(f"profile-id: {value}\n")


def test_compiler_resolves_project_profile_from_charter_pointer(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    _profile(kittify / "charter-packs" / "agent_profiles", "project-local")
    (kittify / "config.yaml").write_text("charter: .kittify/custom/charter.yaml\n")
    source = kittify / "custom" / "charter.yaml"
    source.parent.mkdir()
    source.write_text("activated_agent_profiles: [local]\n")
    assert resolve_config_activated_roots(repo_root=tmp_path).agent_profiles == ["project-local"]


def test_compiler_missing_profile_names_actual_store_and_project_layer(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    source = kittify / "charter.yaml"
    (kittify / "config.yaml").write_text("charter: .kittify/charter.yaml\n")
    source.write_text("activated_agent_profiles: [absent]\n")
    with pytest.raises(UnknownArtifactIdError) as exc:
        resolve_config_activated_roots(repo_root=tmp_path)
    assert str(source) in str(exc.value)
    # Neither project root exists: the project layer is reported at the project pack root.
    assert str(kittify / "charter-packs" / "agent_profiles") in str(exc.value)


def test_project_overrides_org_and_later_org_overrides_earlier(tmp_path: Path) -> None:
    first, second, project = (tmp_path / name for name in ("first", "second", "project"))
    _profile(first / "agent_profiles", "first")
    _profile(second / "agent_profiles", "second")
    _profile(project / "doctrine" / "agent_profiles", "project")
    kwargs = {"doctrine_root": tmp_path, "org_roots": [first, second]}
    assert resolve_artifact_urn(ArtifactKind.AGENT_PROFILE, "local", **kwargs) == "agent_profile:second"
    assert resolve_artifact_urn(ArtifactKind.AGENT_PROFILE, "local", layer_roots={"project": project / "doctrine"}, **kwargs) == "agent_profile:project"


def test_compiler_preflights_proposed_activation_without_writing(tmp_path: Path) -> None:
    import dataclasses
    from charter.activation.pack_context import PackContext

    kittify = tmp_path / ".kittify"
    _profile(kittify / "charter-packs" / "agent_profiles", "project-local")
    config = kittify / "config.yaml"
    config.write_text("activated_agent_profiles: []\n")
    proposed = dataclasses.replace(PackContext.from_config(tmp_path), activated_agent_profiles=frozenset({"local"}))
    assert resolve_config_activated_roots(repo_root=tmp_path, pack_context=proposed).agent_profiles == ["project-local"]
    assert config.read_text() == "activated_agent_profiles: []\n"
