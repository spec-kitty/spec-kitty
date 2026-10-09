"""
Test suite for AgentProfile Pydantic model and value objects.

Follows ATDD approach with ZOMBIES ordering:
- Zero: Empty/minimal profile construction
- One: Single profile with all fields
- Many: Multiple profiles with different roles
- Boundary: routing_priority, max_concurrent_tasks edge cases
- Interface: YAML round-trip serialization
- Exceptions: Missing required fields
- Simple: Role enum coercion and custom roles
"""

import warnings

import pytest
from pydantic import ValidationError

from charter.offering.agent_profiles.profile import (
    AgentProfile,
    CollaborationContract,
    DirectiveRef,
    ModeDefault,
    Role,
    Specialization,
    SpecializationContext,
    TaskContext,
)


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]
class TestAgentProfileZero:
    """Zero: Minimal valid profile construction."""

    def test_minimal_profile_creation(self):
        """Minimal profile with only required fields succeeds."""
        profile = AgentProfile(
            profile_id="test-minimal",
            name="Minimal Agent",
            purpose="Test minimal creation",
            specialization=Specialization(primary_focus="Testing"),
            roles=["implementer"],
        )

        assert profile.profile_id == "test-minimal"
        assert profile.name == "Minimal Agent"
        assert profile.purpose == "Test minimal creation"
        assert profile.specialization.primary_focus == "Testing"
        assert profile.role == Role.IMPLEMENTER
        assert profile.routing_priority == 50  # default
        assert profile.max_concurrent_tasks == 5  # default


class TestAgentProfileOne:
    """One: Single profile with all fields populated."""

    def test_full_profile_creation(self):
        """Profile with all sections populated."""
        profile = AgentProfile(
            profile_id="architect",
            name="Architect",
            description="System design specialist",
            schema_version="1.0",
            role=Role.ARCHITECT,
            capabilities=["read", "write", "search", "edit", "bash"],
            routing_priority=50,
            max_concurrent_tasks=3,
            purpose="Clarify and decompose complex socio-technical systems",
            specialization=Specialization(
                primary_focus="System decomposition, design interfaces, ADRs",
                secondary_awareness="Cultural, political constraints",
                avoidance_boundary="Coding-level specifics",
                success_definition="Architectural clarity improves traceability",
            ),
            collaboration=CollaborationContract(
                handoff_to=["planner", "implementer"],
                handoff_from=["researcher"],
                works_with=["reviewer"],
                output_artifacts=["ADR", "architecture-diagram"],
                operating_procedures=["Decompose before delegating"],
                canonical_verbs=["audit", "synthesize", "plan"],
            ),
            mode_defaults=[
                ModeDefault(
                    mode="/analysis-mode",
                    description="Structured reasoning",
                    use_case="Technical analysis",
                )
            ],
            initialization_declaration="Agent initialized. Purpose acknowledged.",
            specialization_context=SpecializationContext(
                languages=["python", "typescript"],
                frameworks=["fastapi", "django"],
                file_patterns=["src/**/*.py"],
                domain_keywords=["architecture", "design"],
                writing_style=["technical"],
                complexity_preference=["high"],
            ),
            directive_references=[
                DirectiveRef(
                    code="001",
                    name="CLI & Shell Tooling",
                    rationale="Repo discovery",
                )
            ],
        )

        assert profile.profile_id == "architect"
        assert profile.role == Role.ARCHITECT
        assert set(profile.capabilities) == {"read", "write", "search", "edit", "bash"}
        assert profile.routing_priority == 50
        assert set(profile.collaboration.handoff_to) == {"planner", "implementer"}
        assert {m.mode for m in profile.mode_defaults} == {"/analysis-mode"}
        assert profile.specialization_context is not None
        assert set(profile.specialization_context.languages) == {"python", "typescript"}


class TestAgentProfileMany:
    """Many: Multiple profiles with different roles."""

    def test_multiple_profiles_different_roles(self):
        """Create profiles for each role type."""
        roles_data = [
            (Role.IMPLEMENTER, "implementer-profile"),
            (Role.REVIEWER, "reviewer-profile"),
            (Role.ARCHITECT, "architect-profile"),
            (Role.DESIGNER, "designer-profile"),
            (Role.PLANNER, "planner-profile"),
            (Role.RESEARCHER, "researcher-profile"),
            (Role.CURATOR, "curator-profile"),
            (Role.MANAGER, "manager-profile"),
        ]

        profiles = []
        for role, profile_id in roles_data:
            profile = AgentProfile(
                profile_id=profile_id,
                name=str(role).title(),
                purpose=f"{role} purpose",
                specialization=Specialization(primary_focus=f"{role} focus"),
                roles=[role],
            )
            profiles.append(profile)

        assert all(isinstance(p.role, Role) for p in profiles)
        assert {p.role for p in profiles} == {Role(r) for r in Role._KNOWN}


class TestAgentProfileBoundaries:
    """Boundary: Edge cases for routing_priority and max_concurrent_tasks."""

    @pytest.mark.parametrize("priority", [0, 50, 100])
    def test_routing_priority_valid_boundaries(self, priority: int):
        """Valid routing_priority values at boundaries."""
        profile = AgentProfile(
            profile_id="test",
            name="Test",
            purpose="Test",
            specialization=Specialization(primary_focus="Test"),
            roles=["implementer"],
            routing_priority=priority,
        )
        assert profile.routing_priority == priority

    @pytest.mark.parametrize("priority", [-1, 101, -100, 150])
    def test_routing_priority_invalid_boundaries(self, priority: int):
        """Invalid routing_priority values raise ValidationError."""
        with pytest.raises(ValidationError, match="routing_priority"):
            AgentProfile(
                profile_id="test",
                name="Test",
                purpose="Test",
                specialization=Specialization(primary_focus="Test"),
                routing_priority=priority,
            )

    @pytest.mark.parametrize("tasks", [1, 5, 10, 100])
    def test_max_concurrent_tasks_valid(self, tasks: int):
        """Valid max_concurrent_tasks (>0)."""
        profile = AgentProfile(
            profile_id="test",
            name="Test",
            purpose="Test",
            specialization=Specialization(primary_focus="Test"),
            roles=["implementer"],
            max_concurrent_tasks=tasks,
        )
        assert profile.max_concurrent_tasks == tasks

    @pytest.mark.parametrize("tasks", [0, -1, -10])
    def test_max_concurrent_tasks_invalid(self, tasks: int):
        """Invalid max_concurrent_tasks (<=0) raise ValidationError."""
        with pytest.raises(ValidationError, match="max_concurrent_tasks"):
            AgentProfile(
                profile_id="test",
                name="Test",
                purpose="Test",
                specialization=Specialization(primary_focus="Test"),
                max_concurrent_tasks=tasks,
            )


class TestAgentProfileInterface:
    """Interface: YAML round-trip serialization."""

    def test_yaml_round_trip_fidelity(self):
        """Profile serialization and deserialization preserves data."""
        original = AgentProfile(
            profile_id="test-roundtrip",
            name="Roundtrip Test",
            description="Testing YAML round-trip",
            purpose="Validate serialization",
            roles=["implementer"],
            specialization=Specialization(
                primary_focus="Serialization testing",
                secondary_awareness="Data fidelity",
            ),
            collaboration=CollaborationContract(
                handoff_to=["reviewer"],
                canonical_verbs=["test", "validate"],
            ),
            specialization_context=SpecializationContext(
                languages=["python"],
                frameworks=["pytest"],
            ),
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        reconstructed = AgentProfile.model_validate(data)

        # Verify equality
        assert reconstructed.profile_id == original.profile_id
        assert reconstructed.name == original.name
        assert reconstructed.description == original.description
        assert reconstructed.purpose == original.purpose
        assert reconstructed.specialization.primary_focus == original.specialization.primary_focus
        assert reconstructed.collaboration.handoff_to == original.collaboration.handoff_to
        assert reconstructed.specialization_context.languages == original.specialization_context.languages

    def test_yaml_with_kebab_case_fields(self):
        """Profile accepts kebab-case field names from YAML."""
        data = {
            "profile-id": "kebab-test",  # kebab-case
            "name": "Kebab Test",
            "purpose": "Test kebab-case",
            "specialization": {"primary-focus": "Testing"},  # kebab-case
            "roles": ["implementer"],
            "routing-priority": 75,  # kebab-case
            "max-concurrent-tasks": 3,  # kebab-case
        }

        profile = AgentProfile.model_validate(data)
        assert profile.profile_id == "kebab-test"
        assert profile.routing_priority == 75
        assert profile.max_concurrent_tasks == 3

    def test_references_survive_schema_declared_artifact_lists(self):
        """Runtime model preserves all canonical ``*-references`` surfaces."""
        data = {
            "profile-id": "reference-artifacts",
            "name": "Reference Artifacts",
            "purpose": "Prove *-references artifact lists survive validation",
            "roles": ["reviewer"],
            "specialization": {"primary-focus": "testing"},
            "directive-references": [
                {"code": "001", "name": "Integrity", "rationale": "boundaries"},
            ],
            "tactic-references": [
                {"id": "code-review-incremental", "rationale": "review discipline"},
            ],
            "toolguide-references": [
                {"id": "python-review-checks", "rationale": "python review"},
            ],
            "styleguide-references": [
                {"id": "python-conventions", "rationale": "python style"},
            ],
        }

        profile = AgentProfile.model_validate(data)

        assert [r.id for r in profile.tactic_references] == ["code-review-incremental"]
        assert [r.id for r in profile.toolguide_references] == ["python-review-checks"]
        assert [r.id for r in profile.styleguide_references] == ["python-conventions"]

    def test_retired_context_sources_block_is_rejected(self):
        """Authoring the retired ``context-sources`` surface fails loud at load.

        The consolidation in mission doctrine-drg-silent-drop-boundary-01M0PE7E
        removed ``context-sources`` from the model; ``extra="forbid"`` turns any
        residual authoring into an explicit load error rather than a silent drop
        (FR-006).
        """
        data = {
            "profile-id": "retired-context-sources",
            "name": "Retired Context Sources",
            "purpose": "Prove the retired context-sources block is rejected",
            "roles": ["reviewer"],
            "specialization": {"primary-focus": "testing"},
            "context-sources": {
                "directives": ["001"],
                "tactics": ["code-review-incremental"],
            },
        }

        with pytest.raises(ValidationError, match="context-sources"):
            AgentProfile.model_validate(data)


class TestAgentProfileExceptions:
    """Exceptions: Missing required fields."""

    def test_missing_profile_id(self):
        """Missing profile_id raises ValidationError."""
        with pytest.raises(ValidationError, match="profile-id"):
            AgentProfile(
                name="Test",
                purpose="Test",
                specialization=Specialization(primary_focus="Test"),
            )

    def test_missing_name(self):
        """Missing name raises ValidationError."""
        with pytest.raises(ValidationError, match="name"):
            AgentProfile(
                profile_id="test",
                purpose="Test",
                specialization=Specialization(primary_focus="Test"),
            )

    def test_missing_purpose(self):
        """Missing purpose raises ValidationError."""
        with pytest.raises(ValidationError, match="purpose"):
            AgentProfile(
                profile_id="test",
                name="Test",
                specialization=Specialization(primary_focus="Test"),
            )

    def test_missing_specialization(self):
        """Missing specialization raises ValidationError."""
        with pytest.raises(ValidationError, match="specialization"):
            AgentProfile(
                profile_id="test",
                name="Test",
                purpose="Test",
            )

    def test_missing_specialization_primary_focus(self):
        """Missing specialization.primary_focus raises ValidationError."""
        with pytest.raises(ValidationError, match="primary-focus"):
            Specialization()


class TestAgentProfileSimple:
    """Simple: Role enum coercion and custom roles."""

    @pytest.mark.parametrize(
        "role_input,expected",
        [
            ("architect", Role.ARCHITECT),
            ("ARCHITECT", Role.ARCHITECT),
            ("Architect", Role.ARCHITECT),
            ("implementer", Role.IMPLEMENTER),
            ("reviewer", Role.REVIEWER),
            ("planner", Role.PLANNER),
        ],
    )
    def test_role_string_coercion_to_enum(self, role_input: str, expected: Role):
        """Known role strings coerce to Role enum (case-insensitive)."""
        profile = AgentProfile(
            profile_id="test",
            name="Test",
            purpose="Test",
            specialization=Specialization(primary_focus="Test"),
            role=role_input,
        )
        assert profile.role == expected
        assert isinstance(profile.role, Role)

    def test_custom_role_passes_through_with_warning(self):
        """Custom role string passes through via scalar coercion with deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            profile = AgentProfile(
                profile_id="test",
                name="Test",
                purpose="Test",
                specialization=Specialization(primary_focus="Test"),
                role="devops-engineer",
            )
            assert profile.role == "devops-engineer"
            assert isinstance(profile.role, str)
            assert isinstance(profile.role, Role)  # Role is a str subclass; custom roles are valid Role instances
            assert not Role.is_known(profile.role)  # but not a well-known constant
            # Verify deprecation warning was issued for scalar role: syntax
            assert len(w) > 0
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()


class TestTaskContext:
    """TaskContext model validation."""

    def test_minimal_task_context(self):
        """Minimal TaskContext with defaults."""
        ctx = TaskContext()
        assert ctx.language is None
        assert ctx.framework is None
        assert ctx.file_paths == []
        assert ctx.keywords == []
        assert ctx.complexity == "medium"
        assert ctx.required_role is None
        assert ctx.active_tasks == {}

    def test_task_context_full(self):
        """TaskContext with all fields populated."""
        ctx = TaskContext(
            language="python",
            framework="fastapi",
            file_paths=["src/api/routes.py"],
            keywords=["api", "rest"],
            complexity="high",
            required_role=Role.IMPLEMENTER,
            active_tasks={"implementer": 3, "python-pedro": 5},
        )
        assert ctx.language == "python"
        assert ctx.framework == "fastapi"
        assert ctx.file_paths == ["src/api/routes.py"]
        assert ctx.complexity == "high"
        assert ctx.required_role == Role.IMPLEMENTER

    @pytest.mark.parametrize("complexity", ["low", "medium", "high"])
    def test_complexity_valid_values(self, complexity: str):
        """Valid complexity values."""
        ctx = TaskContext(complexity=complexity)
        assert ctx.complexity == complexity

    def test_complexity_invalid_value(self):
        """Invalid complexity value raises ValidationError."""
        with pytest.raises(ValidationError, match="complexity"):
            TaskContext(complexity="ultra-high")

    def test_required_role_none_stays_none(self):
        """required_role=None must remain None, not become string 'None'."""
        ctx = TaskContext(required_role=None)
        assert ctx.required_role is None
