"""Integration tests for nested subdirectory discovery across all doctrine repositories.

Acceptance criterion: artifacts stored in subdirectories of `built_in /` are resolved
when calling `list_all()` or `get()` on any doctrine repository.

These tests use a temporary filesystem — they do not depend on real shipped artifacts.
"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.integration, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_yaml(path: Path, data: dict) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# Minimal valid fixtures per artifact type
# ---------------------------------------------------------------------------

TOOLGUIDE = {
    "schema_version": "1.0",
    "id": "nested-toolguide",
    "tool": "bash",
    "title": "Nested Toolguide",
    "guide_path": "src/charter/offering/toolguides/built-in/POWERSHELL_SYNTAX.md",
    "summary": "A toolguide stored in a subdirectory.",
}

DIRECTIVE = {
    "schema_version": "1.0",
    "id": "DIRECTIVE_998",
    "title": "Nested Directive",
    "intent": "Test that nested directives are discovered.",
    "enforcement": "advisory",
}

TACTIC = {
    "schema_version": "1.0",
    "id": "nested-tactic",
    "name": "Nested Tactic",
    "steps": [{"title": "Only step"}],
}

STYLEGUIDE = {
    "schema_version": "1.0",
    "id": "nested-styleguide",
    "title": "Nested Styleguide",
    "scope": "code",
    "principles": ["Keep it simple"],
}

PROCEDURE = {
    "schema_version": "1.0",
    "id": "nested-procedure",
    "name": "Nested Procedure",
    "purpose": "Test nested discovery.",
    "entry_condition": "Always.",
    "exit_condition": "Done.",
    "steps": [{"title": "Do the thing"}],
}

PARADIGM = {
    "schema_version": "1.0",
    "id": "nested-paradigm",
    "name": "Nested Paradigm",
    "summary": "A paradigm in a subdirectory.",
}

MISSION_STEP_CONTRACT = {
    "schema_version": "1.0",
    "id": "nested-action",
    "action": "nested",
    "mission": "test-mission",
    "steps": [{"id": "step-1", "description": "Do something."}],
}

AGENT_PROFILE = {
    "profile-id": "nested-agent",
    "name": "Nested Agent",
    "description": "Agent profile in a subdirectory.",
    "schema-version": "1.0",
    "role": "implementer",
    "purpose": "Test nested discovery for agent profiles.",
    "specialization": {
        "primary-focus": "Testing",
        "avoidance-boundary": "Nothing to avoid.",
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolguideNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-toolguide.toolguide.yaml", TOOLGUIDE)

        from charter.offering.toolguides.repository import ToolguideRepository

        repo = ToolguideRepository(built_in_dir=built_in)
        ids = [t.id for t in repo.list_all()]
        assert "nested-toolguide" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-toolguide.toolguide.yaml", TOOLGUIDE)

        from charter.offering.toolguides.repository import ToolguideRepository

        repo = ToolguideRepository(built_in_dir=built_in)
        assert repo.get("nested-toolguide") is not None


class TestDirectiveNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "998-nested.directive.yaml", DIRECTIVE)

        from charter.offering.directives.repository import DirectiveRepository

        repo = DirectiveRepository(built_in_dir=built_in)
        ids = [d.id for d in repo.list_all()]
        assert "DIRECTIVE_998" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "998-nested.directive.yaml", DIRECTIVE)

        from charter.offering.directives.repository import DirectiveRepository

        repo = DirectiveRepository(built_in_dir=built_in)
        assert repo.get("DIRECTIVE_998") is not None


class TestTacticNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-tactic.tactic.yaml", TACTIC)

        from charter.offering.tactics.repository import TacticRepository

        repo = TacticRepository(built_in_dir=built_in)
        ids = [t.id for t in repo.list_all()]
        assert "nested-tactic" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-tactic.tactic.yaml", TACTIC)

        from charter.offering.tactics.repository import TacticRepository

        repo = TacticRepository(built_in_dir=built_in)
        assert repo.get("nested-tactic") is not None


class TestStyleguideNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-styleguide.styleguide.yaml", STYLEGUIDE)

        from charter.offering.styleguides.repository import StyleguideRepository

        repo = StyleguideRepository(built_in_dir=built_in)
        ids = [s.id for s in repo.list_all()]
        assert "nested-styleguide" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-styleguide.styleguide.yaml", STYLEGUIDE)

        from charter.offering.styleguides.repository import StyleguideRepository

        repo = StyleguideRepository(built_in_dir=built_in)
        assert repo.get("nested-styleguide") is not None


class TestProcedureNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-procedure.procedure.yaml", PROCEDURE)

        from charter.offering.procedures.repository import ProcedureRepository

        repo = ProcedureRepository(built_in_dir=built_in)
        ids = [p.id for p in repo.list_all()]
        assert "nested-procedure" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-procedure.procedure.yaml", PROCEDURE)

        from charter.offering.procedures.repository import ProcedureRepository

        repo = ProcedureRepository(built_in_dir=built_in)
        assert repo.get("nested-procedure") is not None


class TestParadigmNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-paradigm.paradigm.yaml", PARADIGM)

        from charter.offering.paradigms.repository import ParadigmRepository

        repo = ParadigmRepository(built_in_dir=built_in)
        ids = [p.id for p in repo.list_all()]
        assert "nested-paradigm" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-paradigm.paradigm.yaml", PARADIGM)

        from charter.offering.paradigms.repository import ParadigmRepository

        repo = ParadigmRepository(built_in_dir=built_in)
        assert repo.get("nested-paradigm") is not None


class TestMissionStepContractNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(
            built_in / "subdir" / "nested-action.step-contract.yaml",
            MISSION_STEP_CONTRACT,
        )

        from charter.offering.missions.step_contracts import MissionStepContractRepository

        repo = MissionStepContractRepository(built_in_dir=built_in)
        ids = [c.id for c in repo.list_all()]
        assert "nested-action" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(
            built_in / "subdir" / "nested-action.step-contract.yaml",
            MISSION_STEP_CONTRACT,
        )

        from charter.offering.missions.step_contracts import MissionStepContractRepository

        repo = MissionStepContractRepository(built_in_dir=built_in)
        assert repo.get("nested-action") is not None


class TestAgentProfileNestedDiscovery:
    def test_list_all_finds_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-agent.agent.yaml", AGENT_PROFILE)

        from charter.offering.agent_profiles.repository import AgentProfileRepository

        repo = AgentProfileRepository(built_in_dir=built_in)
        ids = [p.profile_id for p in repo.list_all()]
        assert "nested-agent" in ids

    def test_get_resolves_artifact_in_subdirectory(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in"
        write_yaml(built_in / "subdir" / "nested-agent.agent.yaml", AGENT_PROFILE)

        from charter.offering.agent_profiles.repository import AgentProfileRepository

        repo = AgentProfileRepository(built_in_dir=built_in)
        assert repo.get("nested-agent") is not None
