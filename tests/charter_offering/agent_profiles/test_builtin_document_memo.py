"""The built-in profile layer parses each file once per change (#5526).

A single command builds the agent-profile repository dozens of times; each
build used to re-parse every shipped profile. The parsed documents are now
memoized against each file's size and modification time.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering import yaml_utils
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.pack_paths import built_in_dir
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.corpus]

_PROFILE = "reviewer-renata"


@pytest.fixture
def built_in(tmp_path: Path) -> Path:
    directory = tmp_path / "agent_profiles"
    directory.mkdir()
    shutil.copy2(built_in_dir(ArtifactKind.AGENT_PROFILE) / f"{_PROFILE}.agent.yaml", directory)
    return directory


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []
    original = YAML.load

    def _counted(self: YAML, stream: object) -> object:
        # ruamel opens a Path and re-enters load() with the stream; count paths only.
        if isinstance(stream, Path) and stream.name.endswith(".agent.yaml"):
            calls.append(stream)
        return original(self, stream)

    monkeypatch.setattr(yaml_utils, "_SHIPPED_DOCUMENT_MEMO", {}, raising=False)
    monkeypatch.setattr(YAML, "load", _counted)
    return calls


def test_repeat_builds_parse_each_built_in_profile_once(built_in: Path, parses: list[object]) -> None:
    graph = load_built_in_graph()

    first = AgentProfileRepository(built_in_dir=built_in, drg=graph)
    second = AgentProfileRepository(built_in_dir=built_in, drg=graph)

    assert len(parses) == 1
    assert first.get(_PROFILE) == second.get(_PROFILE)
    assert first.get(_PROFILE) is not second.get(_PROFILE)


def test_an_edited_built_in_profile_is_reparsed(built_in: Path, parses: list[object]) -> None:
    graph = load_built_in_graph()
    path = built_in / f"{_PROFILE}.agent.yaml"
    original = AgentProfileRepository(built_in_dir=built_in, drg=graph).get(_PROFILE)
    assert original is not None
    original_name = original.name

    text = path.read_text(encoding="utf-8")
    assert f"name: {original_name}" in text
    path.write_text(text.replace(f"name: {original_name}", "name: Renamed Reviewer", 1), encoding="utf-8")
    reloaded = AgentProfileRepository(built_in_dir=built_in, drg=graph).get(_PROFILE)

    assert len(parses) == 2
    assert reloaded is not None
    assert reloaded.name == "Renamed Reviewer"
