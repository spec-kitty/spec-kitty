"""
Test suite for AgentProfileRepository.

Follows ATDD approach with ZOMBIES ordering:
- Zero: Empty repository
- One: Single profile
- Many: Multiple profiles from shipped + project
- Boundary: Edge cases (routing_priority 0/100, missing dirs)
- Interface: Field-level merge, YAML round-trip
- Exceptions: Invalid YAML, cycles, orphans
- Simple: Query methods, hierarchy traversal, matching
"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.agent_profiles.profile import AgentProfile, Role, TaskContext
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _lineage_drg(*pairs: tuple[str, str]) -> DRGGraph:
    """Build a DRG with ``specializes_from`` edges for ``(child, parent)`` pairs.

    Lineage is authored as DRG ``specializes_from`` edges (FR-002 / WP05); the
    retired ``specializes-from`` profile field is gone.
    """
    ids = {pid for pair in pairs for pid in pair}
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-02T00:00:00Z",
        generated_by="test_profile_repository",
        nodes=[DRGNode(urn=f"agent_profile:{pid}", kind=NodeKind.AGENT_PROFILE) for pid in sorted(ids)],
        edges=[
            DRGEdge(
                source=f"agent_profile:{child}",
                target=f"agent_profile:{parent}",
                relation=Relation.SPECIALIZES_FROM,
            )
            for child, parent in pairs
        ],
    )


def _shipped_drg() -> DRGGraph:
    """Lineage DRG for the ``shipped_profiles_dir`` fixture."""
    return _lineage_drg(("python-pedro", "generic-implementer"))



@pytest.fixture
def minimal_profile_yaml() -> str:
    """Minimal valid agent profile YAML."""
    return """profile-id: test-profile
name: Test Profile
purpose: Testing purpose
roles:
  - implementer
specialization:
  primary-focus: Testing
"""


@pytest.fixture
def shipped_profiles_dir(tmp_path: Path) -> Path:
    """Create temporary shipped profiles directory with test fixtures."""
    shipped = tmp_path / "built-in"
    shipped.mkdir()

    # Parent profile: architect
    (shipped / "architect-alphonso.agent.yaml").write_text("""profile-id: architect-alphonso
name: Architect Alphonso
purpose: System design and architecture
roles:
  - architect
routing-priority: 80
specialization:
  primary-focus: Architecture and design
  domain-keywords:
    - architecture
    - design
    - system
specialization-context:
  languages:
    - python
    - typescript
  frameworks:
    - django
  file-patterns:
    - "architecture/**/*.md"
  domain-keywords:
    - design patterns
    - system architecture
""")

    # Child profile: python-pedro (specializes from generic implementer)
    (shipped / "python-pedro.agent.yaml").write_text("""profile-id: python-pedro
name: Python Pedro
purpose: Python implementation specialist
roles:
  - implementer
routing-priority: 90
specialization:
  primary-focus: Python development
  domain-keywords:
    - python
    - django
    - pytest
specialization-context:
  languages:
    - python
  frameworks:
    - django
    - pytest
  file-patterns:
    - "**/*.py"
  domain-keywords:
    - python
    - backend
""")

    # Generic implementer (root)
    (shipped / "generic-implementer.agent.yaml").write_text("""profile-id: generic-implementer
name: Generic Implementer
purpose: General-purpose implementation
roles:
  - implementer
routing-priority: 50
specialization:
  primary-focus: General implementation
""")

    return shipped


@pytest.fixture
def project_profiles_dir(tmp_path: Path) -> Path:
    """Create temporary project profiles directory."""
    project = tmp_path / "project"
    project.mkdir()

    # Override python-pedro with higher priority
    (project / "python-pedro.agent.yaml").write_text("""profile-id: python-pedro
routing-priority: 95
specialization:
  primary-focus: Custom Python development
""")

    # New custom profile
    (project / "custom-reviewer.agent.yaml").write_text("""profile-id: custom-reviewer
name: Custom Reviewer
purpose: Code review specialist
roles:
  - reviewer
routing-priority: 70
specialization:
  primary-focus: Code review
""")

    return project


class TestAgentProfileRepositoryZero:
    """Test zero/empty cases."""

    def test_empty_repository_no_dirs(self):
        """Empty repository with no shipped or project dirs returns empty list."""
        repo = AgentProfileRepository(built_in_dir=Path("/nonexistent"), project_dir=None)
        assert repo.list_all() == []


class TestAgentProfileCollisionWarning:
    """Profile shadowing emits a DoctrineLayerCollisionWarning (MEDIUM-1)."""

    def test_project_override_of_shipped_profile_warns(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ) -> None:
        """The shipped+project fixtures define python-pedro twice; this must warn."""
        from charter.offering.base import DoctrineLayerCollisionWarning

        with pytest.warns(DoctrineLayerCollisionWarning) as record:
            AgentProfileRepository(
                built_in_dir=shipped_profiles_dir,
                project_dir=project_profiles_dir,
            )

        msgs = [str(w.message) for w in record]
        pedro_msgs = [m for m in msgs if "python-pedro" in m]
        assert pedro_msgs, msgs
        assert any("project" in m and "builtin" in m for m in pedro_msgs)
        assert any("agent_profile" in m for m in pedro_msgs)

    def test_no_warning_for_distinct_project_profile(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ) -> None:
        """custom-reviewer exists only in project — no collision, no warning for it."""
        from charter.offering.base import DoctrineLayerCollisionWarning
        import warnings as _w

        with _w.catch_warnings(record=True) as captured:
            _w.simplefilter("always")
            AgentProfileRepository(
                built_in_dir=shipped_profiles_dir,
                project_dir=project_profiles_dir,
            )

        msgs = [
            str(w.message)
            for w in captured
            if isinstance(w.message, DoctrineLayerCollisionWarning)
        ]
        # custom-reviewer must NOT appear in any collision message.
        assert not any("custom-reviewer" in m for m in msgs), msgs

    def test_get_nonexistent_profile_returns_none(self, shipped_profiles_dir: Path):
        """Getting nonexistent profile returns None."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        assert repo.get("nonexistent") is None


class TestAgentProfileRepositoryOne:
    """Test single profile cases."""

    def test_load_single_shipped_profile(self, shipped_profiles_dir: Path):
        """Single shipped profile loads correctly."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        profiles = repo.list_all()
        assert {p.profile_id for p in profiles} == {  # We have 3 shipped profiles
            "architect-alphonso",
            "python-pedro",
            "generic-implementer",
        }

        alphonso = repo.get("architect-alphonso")
        assert alphonso is not None
        assert alphonso.name == "Architect Alphonso"
        assert alphonso.role == Role.ARCHITECT
        assert alphonso.routing_priority == 80

    def test_get_existing_profile(self, shipped_profiles_dir: Path):
        """Get returns correct profile by ID."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        profile = repo.get("python-pedro")
        assert profile is not None
        assert profile.profile_id == "python-pedro"
        assert profile.name == "Python Pedro"


class TestAgentProfileRepositoryMany:
    """Test multiple profiles."""

    def test_load_multiple_shipped_profiles(self, shipped_profiles_dir: Path):
        """Multiple shipped profiles load correctly."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        profiles = repo.list_all()
        profile_ids = {p.profile_id for p in profiles}
        assert profile_ids == {"architect-alphonso", "python-pedro", "generic-implementer"}

    def test_load_shipped_and_project_profiles(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ):
        """Both shipped and project profiles load correctly."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_profiles_dir
        )
        profiles = repo.list_all()
        # 3 shipped + 1 new project - 1 override = 4 total
        profile_ids = {p.profile_id for p in profiles}
        assert profile_ids == {
            "architect-alphonso",
            "python-pedro",
            "generic-implementer",
            "custom-reviewer",
        }

    def test_filters_language_scoped_profiles_when_active_languages_do_not_match(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        (shipped / "python-only.agent.yaml").write_text(
            """profile-id: python-only
name: Python Only
purpose: Python specialist
roles:
  - implementer
applies_to_languages:
  - python
specialization:
  primary-focus: Python implementation
""",
            encoding="utf-8",
        )
        (shipped / "generic.agent.yaml").write_text(
            """profile-id: generic
name: Generic
purpose: Generic specialist
roles:
  - implementer
specialization:
  primary-focus: General implementation
""",
            encoding="utf-8",
        )

        repo = AgentProfileRepository(built_in_dir=shipped, active_languages=["typescript"])
        profile_ids = {profile.profile_id for profile in repo.list_all()}

        assert "generic" in profile_ids
        assert "python-only" not in profile_ids

    def test_keeps_language_scoped_profiles_when_active_languages_are_unset(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        (shipped / "python-only.agent.yaml").write_text(
            """profile-id: python-only
name: Python Only
purpose: Python specialist
roles:
  - implementer
applies_to_languages:
  - python
specialization:
  primary-focus: Python implementation
""",
            encoding="utf-8",
        )
        (shipped / "generic.agent.yaml").write_text(
            """profile-id: generic
name: Generic
purpose: Generic specialist
roles:
  - implementer
specialization:
  primary-focus: General implementation
""",
            encoding="utf-8",
        )

        repo = AgentProfileRepository(built_in_dir=shipped)
        profile_ids = {profile.profile_id for profile in repo.list_all()}

        assert "generic" in profile_ids
        assert "python-only" in profile_ids

    def test_scope_filtered_ids_record_language_scoped_drops(
        self, tmp_path: Path
    ) -> None:
        """#4572: a language-scope drop is recorded, not silent.

        Parity with ``BaseDoctrineRepository.scope_filtered_ids`` (FR-013):
        the catalog-miss diagnosis reads this set so a present-but-scoped
        profile surfaces ``SCOPE_FILTERED`` instead of ``MISSING_ARTIFACT``.
        """
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        (shipped / "python-only.agent.yaml").write_text(
            """profile-id: python-only
name: Python Only
purpose: Python specialist
roles:
  - implementer
applies_to_languages:
  - python
specialization:
  primary-focus: Python implementation
""",
            encoding="utf-8",
        )
        (shipped / "generic.agent.yaml").write_text(
            """profile-id: generic
name: Generic
purpose: Generic specialist
roles:
  - implementer
specialization:
  primary-focus: General implementation
""",
            encoding="utf-8",
        )

        repo = AgentProfileRepository(built_in_dir=shipped, active_languages=["typescript"])

        assert repo.get("python-only") is None
        assert repo.scope_filtered_ids == frozenset({"python-only"})
        # The unscoped profile is neither dropped nor recorded.
        assert repo.get("generic") is not None
        assert "generic" not in repo.scope_filtered_ids

    def test_later_layer_readmission_removes_scope_filtered_record(
        self, tmp_path: Path
    ) -> None:
        """#4572: an org overlay that re-admits a scoped-out builtin clears the record.

        The record must never outlive the drop it describes — once a higher
        layer loads the profile (e.g. by widening or removing its
        ``applies_to_languages`` scope), the id is in the catalog and
        ``get()`` resolves it, so it is no longer scope-filtered.
        """
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "python-only.agent.yaml").write_text(
            """profile-id: python-only
name: Python Only
purpose: Python specialist
roles:
  - implementer
applies_to_languages:
  - python
specialization:
  primary-focus: Python implementation
""",
            encoding="utf-8",
        )
        org = tmp_path / "org-pack"
        org.mkdir()
        # Same profile-id, no language scope: the org layer re-admits it.
        (org / "python-only.agent.yaml").write_text(
            """profile-id: python-only
name: Python Only (org override)
purpose: Python specialist, any language
roles:
  - implementer
specialization:
  primary-focus: Python implementation
""",
            encoding="utf-8",
        )

        repo = AgentProfileRepository(
            built_in_dir=shipped, org_dirs=[org], active_languages=["typescript"]
        )

        assert repo.get("python-only") is not None
        assert repo.scope_filtered_ids == frozenset()

    def test_skips_project_profiles_when_language_scope_does_not_match(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "python-pedro.agent.yaml").write_text(
            """profile-id: python-pedro
applies_to_languages:
  - python
routing-priority: 99
""",
            encoding="utf-8",
        )
        (project / "typescript-reviewer.agent.yaml").write_text(
            """profile-id: typescript-reviewer
name: TypeScript Reviewer
purpose: Review TypeScript changes
roles:
  - reviewer
applies_to_languages:
  - typescript
specialization:
  primary-focus: TypeScript review
""",
            encoding="utf-8",
        )

        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir,
            project_dir=project,
            active_languages=["go"],
        )

        python_pedro = repo.get("python-pedro")
        assert python_pedro is not None
        assert python_pedro.routing_priority == 90
        assert repo.get("typescript-reviewer") is None


class TestAgentProfileRepositoryBoundaries:
    """Test boundary conditions."""

    def test_routing_priority_boundaries(self, shipped_profiles_dir: Path):
        """Profiles with routing_priority 0 and 100 are valid."""
        shipped = shipped_profiles_dir
        (shipped / "min-priority.agent.yaml").write_text("""profile-id: min-priority
name: Min Priority
purpose: Test
roles:
  - planner
routing-priority: 0
specialization:
  primary-focus: Testing
""")
        (shipped / "max-priority.agent.yaml").write_text("""profile-id: max-priority
name: Max Priority
purpose: Test
roles:
  - planner
routing-priority: 100
specialization:
  primary-focus: Testing
""")

        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        min_prof = repo.get("min-priority")
        max_prof = repo.get("max-priority")
        assert min_prof.routing_priority == 0
        assert max_prof.routing_priority == 100


class TestAgentProfileRepositoryInterface:
    """Test interface contracts and field-level merge."""

    def test_field_level_merge_overrides_some_fields(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ):
        """Project profile overrides specific fields, retains others from shipped."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_profiles_dir
        )
        pedro = repo.get("python-pedro")

        # Overridden fields from project
        assert pedro.routing_priority == 95  # From project override
        assert pedro.specialization.primary_focus == "Custom Python development"  # From project

        # Retained fields from shipped
        assert pedro.name == "Python Pedro"  # Not overridden, from shipped
        assert pedro.role == Role.IMPLEMENTER  # Not overridden, from shipped
        assert pedro.purpose == "Python implementation specialist"  # From shipped

    def test_project_only_profile_loads(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ):
        """Project-only profile (not in shipped) loads correctly."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_profiles_dir
        )
        custom = repo.get("custom-reviewer")
        assert custom is not None
        assert custom.profile_id == "custom-reviewer"
        assert custom.role == Role.REVIEWER


class TestAgentProfileRepositoryExceptions:
    """Test exception handling and validation."""

    def test_invalid_yaml_skipped_with_warning(
        self, shipped_profiles_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        """Invalid YAML file is skipped and warning is logged."""
        (shipped_profiles_dir / "invalid.agent.yaml").write_text("invalid: yaml: {")

        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        # Should load valid profiles, skip invalid
        assert {p.profile_id for p in repo.list_all()} == {  # Only the 3 valid profiles
            "architect-alphonso",
            "python-pedro",
            "generic-implementer",
        }

    def test_source_path_absent_for_a_project_layer_profile_that_fails_validation(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """T026 twin-verification regression (WP06, D-M8, mission #3062).

        The ``AssetRepository.__init__`` docstring claims its ``_source_paths``
        bookkeeping "mirrors AgentProfileRepository" — the pre-planning ledger
        flagged this as a second instance of the same premature-bookkeeping
        ordering bug T025 fixed via ``_post_validate``. Reading ``_load_layer``
        (``src/charter/offering/agent_profiles/repository.py:370-496``) shows the
        ``self._source_paths[profile.profile_id] = yaml_file`` write (line 493)
        sits *after* the ``try/except ValidationError`` block (lines 463-479,
        which ``continue``s past line 493 on a validation failure) and after
        the language-scope gate (lines 481-482) — i.e. already ordered
        correctly, unlike pre-fix ``AssetRepository._pre_validate``. This test
        proves that with a live red/green check rather than assuming the
        ledger's claim: a project-layer profile missing required fields
        (``purpose``, ``specialization``) must fail ``AgentProfile.model_
        validate`` and leave no ``get_source_path`` entry.
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / "broken.agent.yaml").write_text(
            "profile-id: broken\nname: Broken Profile\nroles:\n  - implementer\n"
            # 'purpose' and 'specialization' are required and deliberately omitted.
        )

        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project
        )

        assert repo.get("broken") is None
        assert repo.get_source_path("broken") is None

    def test_cycle_detection(self, tmp_path: Path):
        """Validate hierarchy detects cycles."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        # Create cycle: A → B → C → A (lineage authored as DRG edges)
        (shipped / "a.agent.yaml").write_text("""profile-id: profile-a
name: Profile A
purpose: Test
roles:
  - implementer
specialization:
  primary-focus: Testing
""")
        (shipped / "b.agent.yaml").write_text("""profile-id: profile-b
name: Profile B
purpose: Test
roles:
  - implementer
specialization:
  primary-focus: Testing
""")
        (shipped / "c.agent.yaml").write_text("""profile-id: profile-c
name: Profile C
purpose: Test
roles:
  - implementer
specialization:
  primary-focus: Testing
""")

        drg = _lineage_drg(
            ("profile-a", "profile-c"),
            ("profile-b", "profile-a"),
            ("profile-c", "profile-b"),
        )
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None, drg=drg)
        errors = repo.validate_hierarchy()
        assert len(errors) > 0
        assert any("cycle" in err.lower() for err in errors)

    def test_orphaned_reference_warning(self, tmp_path: Path):
        """Validate hierarchy detects orphaned references."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        (shipped / "orphan.agent.yaml").write_text("""profile-id: orphan-child
name: Orphan Child
purpose: Test
roles:
  - implementer
specialization:
  primary-focus: Testing
""")

        drg = _lineage_drg(("orphan-child", "nonexistent-parent"))
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None, drg=drg)
        errors = repo.validate_hierarchy()
        assert len(errors) > 0
        assert any("orphan" in err.lower() or "nonexistent" in err.lower() for err in errors)


class TestAgentProfileRepositorySimple:
    """Test simple query operations."""

    def test_find_by_role_enum(self, shipped_profiles_dir: Path):
        """Find profiles by role enum."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        implementers = repo.find_by_role(Role.IMPLEMENTER)
        ids = {p.profile_id for p in implementers}  # python-pedro and generic-implementer
        assert ids == {"python-pedro", "generic-implementer"}

    def test_find_by_role_string(self, shipped_profiles_dir: Path):
        """Find profiles by role string."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        implementers = repo.find_by_role("implementer")
        assert {p.profile_id for p in implementers} == {"python-pedro", "generic-implementer"}

    def test_find_by_role_returns_empty_for_nonexistent(self, shipped_profiles_dir: Path):
        """Find by role returns empty list for nonexistent role."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        assert repo.find_by_role("nonexistent") == []


class TestAgentProfileRepositoryHierarchy:
    """Test hierarchy traversal."""

    def test_get_children(self, shipped_profiles_dir: Path):
        """Get children returns direct descendants."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        children = repo.get_children("generic-implementer")
        assert {c.profile_id for c in children} == {"python-pedro"}
        assert children[0].profile_id == "python-pedro"

    def test_get_children_of_leaf_returns_empty(self, shipped_profiles_dir: Path):
        """Get children of leaf profile returns empty list."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        assert repo.get_children("python-pedro") == []

    def test_get_ancestors(self, shipped_profiles_dir: Path):
        """Get ancestors returns parent chain."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        ancestors = repo.get_ancestors("python-pedro")
        assert ancestors == ["generic-implementer"]

    def test_get_ancestors_of_root_returns_empty(self, shipped_profiles_dir: Path):
        """Get ancestors of root profile returns empty list."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        assert repo.get_ancestors("generic-implementer") == []

    def test_get_hierarchy_tree(self, shipped_profiles_dir: Path):
        """Get hierarchy tree returns nested structure."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        tree = repo.get_hierarchy_tree()

        # Should have 2 roots: architect-alphonso and generic-implementer
        assert "architect-alphonso" in tree
        assert "generic-implementer" in tree

        # generic-implementer should have python-pedro as child
        assert "python-pedro" in tree["generic-implementer"]["children"]


class TestAgentProfileRepositoryMatching:
    """Test context-based profile matching."""

    def test_find_best_match_with_language(self, shipped_profiles_dir: Path):
        """Find best match returns specialist for matching language."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        context = TaskContext(
            task_type="implement",
            language="python",
            complexity="medium",
        )
        match = repo.find_best_match(context)
        assert match is not None
        assert match.profile_id == "python-pedro"  # Specialist with higher priority

    def test_find_best_match_no_context_returns_highest_priority(
        self, shipped_profiles_dir: Path
    ):
        """Find best match with no context returns highest routing_priority."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        context = TaskContext(task_type="implement", complexity="medium")
        match = repo.find_best_match(context)
        assert match is not None
        # python-pedro has routing_priority 90, highest among all
        assert match.profile_id == "python-pedro"

    def test_find_best_match_with_workload_penalty(self, shipped_profiles_dir: Path):
        """Workload penalty reduces score for busy profiles."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=None, drg=_shipped_drg()
        )
        context = TaskContext(
            task_type="implement",
            language="python",
            complexity="medium",
            current_workload=5,  # 5+ tasks = 0.70 penalty
        )
        match = repo.find_best_match(context)
        # Should still match python-pedro despite penalty
        assert match is not None

    def test_find_best_match_returns_none_for_zero_profiles(self):
        """Find best match returns None when repository is empty."""
        repo = AgentProfileRepository(built_in_dir=Path("/nonexistent"), project_dir=None)
        context = TaskContext(task_type="implement", complexity="medium")
        assert repo.find_best_match(context) is None


class TestAgentProfileRepositorySaveDelete:
    """Test save and delete operations."""

    def test_save_creates_yaml_file(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """Save writes profile as YAML to project directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_dir
        )

        new_profile = AgentProfile(
            profile_id="new-tester",
            name="New Tester",
            purpose="Testing",
            roles=[Role.REVIEWER],
            specialization={"primary_focus": "Test review"},
        )

        repo.save(new_profile)

        # Verify file exists
        yaml_file = project_dir / "new-tester.agent.yaml"
        assert yaml_file.exists()

        # Verify profile is in repository
        assert repo.get("new-tester") is not None

    def test_save_without_project_dir_raises_error(self, shipped_profiles_dir: Path):
        """Save without project_dir raises ValueError."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)
        profile = AgentProfile(
            profile_id="test",
            name="Test",
            purpose="Test",
            roles=[Role.PLANNER],
            specialization={"primary_focus": "Testing"},
        )

        with pytest.raises(ValueError, match="project_dir"):
            repo.save(profile)

    def test_delete_removes_project_only_profile(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ):
        """Delete removes project-only profile."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_profiles_dir
        )

        # custom-reviewer is project-only
        assert repo.get("custom-reviewer") is not None
        result = repo.delete("custom-reviewer")
        assert result is True
        assert repo.get("custom-reviewer") is None

    def test_delete_reverts_merged_profile_to_shipped(
        self, shipped_profiles_dir: Path, project_profiles_dir: Path
    ):
        """Delete on merged profile reverts to shipped version."""
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_profiles_dir
        )

        # python-pedro is merged (project overrides shipped)
        pedro_before = repo.get("python-pedro")
        assert pedro_before.routing_priority == 95  # Project override

        result = repo.delete("python-pedro")
        assert result is True

        # Should revert to shipped version
        pedro_after = repo.get("python-pedro")
        assert pedro_after is not None
        assert pedro_after.routing_priority == 90  # Back to shipped value

    def test_delete_nonexistent_returns_false(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """Delete nonexistent profile returns False."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project_dir
        )
        result = repo.delete("nonexistent")
        assert result is False

    def test_delete_without_project_dir_raises_error(self, shipped_profiles_dir: Path):
        """Delete without project_dir raises ValueError."""
        repo = AgentProfileRepository(built_in_dir=shipped_profiles_dir, project_dir=None)

        with pytest.raises(ValueError, match="project_dir"):
            repo.delete("anything")


# ── Loader boundary tests ──────────────────────────────────────────────────


class TestAgentProfileRepositoryLoader:
    """Loader boundary: glob patterns, None data, missing profile-id, rglob depth."""

    def test_shipped_rglob_finds_profiles_in_subdirectory(self, tmp_path: Path):
        """Shipped loader uses rglob and finds profiles nested in subdirectories."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        sub = shipped / "sub"
        sub.mkdir()
        (sub / "nested.agent.yaml").write_text(
            "profile-id: nested\nname: Nested\npurpose: Test\n"
            "roles:\n  - implementer\nspecialization:\n  primary-focus: Testing\n"
        )
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        assert repo.get("nested") is not None

    def test_project_rglob_finds_profiles_in_subdirectory(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """Project loader recurses (parity with built-in) and finds nested profiles.

        Regression for #3490: org/project overlay discovery is now
        unconditionally recursive via the single ``discovery_recursion``
        authority, matching the built-in tier's ``rglob`` (see
        ``test_shipped_rglob_finds_profiles_in_subdirectory`` above). A profile
        one directory deep in the project overlay must load, not be silently
        dropped as it was under the previous non-recursive ``glob``.
        """
        project = tmp_path / "project"
        sub = project / "sub"
        sub.mkdir(parents=True)
        (sub / "deep.agent.yaml").write_text(
            "profile-id: deep\nname: Deep\npurpose: Test\n"
            "roles:\n  - implementer\nspecialization:\n  primary-focus: Testing\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project
        )
        assert repo.get("deep") is not None

    def test_non_agent_yaml_files_are_ignored(self, tmp_path: Path):
        """Files not matching *.agent.yaml pattern are silently ignored."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "notes.yaml").write_text("note: not a profile\n")
        (shipped / "profile.agent.yml").write_text("profile-id: wrong-ext\n")
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        assert repo.list_all() == []

    def test_empty_yaml_file_is_silently_skipped(self, tmp_path: Path):
        """Empty YAML (data is None) is skipped without raising."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "empty.agent.yaml").write_text("")
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        assert repo.list_all() == []

    def test_project_profile_missing_profile_id_is_recorded(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """Project YAML with no profile-id key is recorded as skipped (FR-005/006/007)."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "no-id.agent.yaml").write_text(
            "name: No ID Profile\npurpose: Test\nroles:\n  - implementer\n"
            "specialization:\n  primary-focus: Testing\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project, drg=_shipped_drg()
        )
        ids = {p.profile_id for p in repo.list_all()}
        assert "no-id" not in ids
        skipped = repo.skipped_profiles()
        assert any(s.layer == "project" and s.profile_id is None for s in skipped)

    def test_invalid_shipped_yaml_is_recorded(self, tmp_path: Path):
        """Shipped YAML with parse error is recorded as skipped and other profiles load."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "good.agent.yaml").write_text(
            "profile-id: good\nname: Good\npurpose: Test\n"
            "roles:\n  - implementer\nspecialization:\n  primary-focus: Testing\n"
        )
        (shipped / "bad.agent.yaml").write_text("invalid: yaml: {")
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        assert repo.get("good") is not None
        assert repo.get("bad") is None
        assert any(s.layer == "builtin" for s in repo.skipped_profiles())

    def test_skip_recorded_once_per_invalid_shipped_file(self, tmp_path: Path):
        """A single invalid built-in file produces exactly one skip record on load."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "bad.agent.yaml").write_text("invalid: yaml: {")
        repo = AgentProfileRepository(built_in_dir=shipped, project_dir=None)
        builtin_skips = [s for s in repo.skipped_profiles() if s.layer == "builtin"]
        assert {s.path for s in builtin_skips} == {str(shipped / "bad.agent.yaml")}

    def test_invalid_project_yaml_is_recorded(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """Project YAML with parse error is recorded as skipped for that file."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "broken.agent.yaml").write_text("broken: yaml: {")
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project, drg=_shipped_drg()
        )
        assert any(s.layer == "project" for s in repo.skipped_profiles())


# ── _apply_excluding tests ─────────────────────────────────────────────────


class TestResolveProfileWithExcluding:
    """resolve_profile applies excluding from the leaf profile after union merge."""

    def _make_shipped_dir(self, tmp_path: Path) -> Path:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "base.agent.yaml").write_text(
            "profile-id: base\nname: Base\npurpose: Base profile\n"
            "roles:\n  - implementer\nrouting-priority: 50\n"
            "capabilities:\n  - read\n  - write\n  - edit\n"
            "specialization:\n  primary-focus: Base implementation\n"
        )
        (shipped / "child.agent.yaml").write_text(
            "profile-id: child\nname: Child\npurpose: Child profile\n"
            "roles:\n  - implementer\nrouting-priority: 60\n"
            "specialization:\n  primary-focus: Child implementation\n"
            "excluding:\n  capabilities:\n    - edit\n"
        )
        return shipped

    def test_excluding_dict_removes_specific_list_values(self, tmp_path: Path):
        """Child's excluding dict removes named values from parent list fields."""
        shipped = self._make_shipped_dir(tmp_path)
        repo = AgentProfileRepository(
            built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("child", "base"))
        )
        child = repo.resolve_profile("child")
        assert "edit" not in child.capabilities
        assert "read" in child.capabilities
        assert "write" in child.capabilities

    def test_excluding_list_removes_entire_field(self, tmp_path: Path):
        """Child's excluding list removes the entire named field."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "base2.agent.yaml").write_text(
            "profile-id: base2\nname: Base2\npurpose: Base2 profile\n"
            "roles:\n  - implementer\nrouting-priority: 50\n"
            "capabilities:\n  - read\n  - write\n"
            "specialization:\n  primary-focus: Base2 implementation\n"
        )
        (shipped / "child2.agent.yaml").write_text(
            "profile-id: child2\nname: Child2\npurpose: Child2 profile\n"
            "roles:\n  - implementer\n"
            "specialization:\n  primary-focus: Child2 implementation\n"
            "excluding:\n  - capabilities\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped, project_dir=None, drg=_lineage_drg(("child2", "base2"))
        )
        child = repo.resolve_profile("child2")
        assert child.capabilities == []


# ── Multi-field merge assertions ───────────────────────────────────────────


class TestFieldLevelMergeComplete:
    """Project override: verify every asserted field individually."""

    def test_project_override_preserves_all_non_overridden_shipped_fields(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """When project overrides only routing-priority, all other fields come from shipped."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "architect-alphonso.agent.yaml").write_text(
            "profile-id: architect-alphonso\nrouting-priority: 99\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project
        )
        profile = repo.get("architect-alphonso")
        assert profile.routing_priority == 99          # overridden
        assert profile.name == "Architect Alphonso"    # from shipped
        assert profile.role == Role.ARCHITECT           # from shipped
        assert profile.purpose == "System design and architecture"  # from shipped

    def test_project_new_profile_is_fully_independent(
        self, shipped_profiles_dir: Path, tmp_path: Path
    ):
        """New project-only profile is completely independent; no shipped merge."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "standalone.agent.yaml").write_text(
            "profile-id: standalone\nname: Standalone\npurpose: Custom purpose\n"
            "roles:\n  - curator\nrouting-priority: 42\n"
            "specialization:\n  primary-focus: Standalone work\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped_profiles_dir, project_dir=project
        )
        profile = repo.get("standalone")
        assert profile is not None
        assert profile.profile_id == "standalone"
        assert profile.routing_priority == 42
        assert profile.role == Role.CURATOR


# ── Hierarchy ancestors multi-level ────────────────────────────────────────


class TestMultiLevelHierarchy:
    """Hierarchy traversal with chains longer than one level."""

    def _three_level_shipped(self, tmp_path: Path) -> Path:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "root.agent.yaml").write_text(
            "profile-id: root\nname: Root\npurpose: Root\nroles:\n  - implementer\n"
            "specialization:\n  primary-focus: Root\n"
        )
        (shipped / "mid.agent.yaml").write_text(
            "profile-id: mid\nname: Mid\npurpose: Mid\nroles:\n  - implementer\n"
            "specialization:\n  primary-focus: Mid\n"
        )
        (shipped / "leaf.agent.yaml").write_text(
            "profile-id: leaf\nname: Leaf\npurpose: Leaf\nroles:\n  - implementer\n"
            "specialization:\n  primary-focus: Leaf\n"
        )
        return shipped

    def _three_level_drg(self) -> DRGGraph:
        return _lineage_drg(("mid", "root"), ("leaf", "mid"))

    def test_get_ancestors_returns_full_chain_nearest_first(self, tmp_path: Path):
        shipped = self._three_level_shipped(tmp_path)
        repo = AgentProfileRepository(
            built_in_dir=shipped, project_dir=None, drg=self._three_level_drg()
        )
        ancestors = repo.get_ancestors("leaf")
        assert ancestors == ["mid", "root"]

    def test_get_children_returns_only_direct_children(self, tmp_path: Path):
        shipped = self._three_level_shipped(tmp_path)
        repo = AgentProfileRepository(
            built_in_dir=shipped, project_dir=None, drg=self._three_level_drg()
        )
        root_children = repo.get_children("root")
        assert [p.profile_id for p in root_children] == ["mid"]
        # leaf is NOT a direct child of root
        assert "leaf" not in [p.profile_id for p in root_children]

    def test_resolve_profile_inherits_through_full_chain(self, tmp_path: Path):
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        (shipped / "root.agent.yaml").write_text(
            "profile-id: root\nname: Root\npurpose: Root\nroles:\n  - implementer\n"
            "routing-priority: 10\ncapabilities:\n  - read\n"
            "specialization:\n  primary-focus: Root\n"
        )
        (shipped / "mid.agent.yaml").write_text(
            "profile-id: mid\nname: Mid\npurpose: Mid\nroles:\n  - implementer\n"
            "capabilities:\n  - write\n"
            "specialization:\n  primary-focus: Mid\n"
        )
        (shipped / "leaf.agent.yaml").write_text(
            "profile-id: leaf\nname: Leaf\npurpose: Leaf\nroles:\n  - implementer\n"
            "capabilities:\n  - search\n"
            "routing-priority: 90\n"
            "specialization:\n  primary-focus: Leaf\n"
        )
        repo = AgentProfileRepository(
            built_in_dir=shipped,
            project_dir=None,
            drg=_lineage_drg(("mid", "root"), ("leaf", "mid")),
        )
        resolved = repo.resolve_profile("leaf")
        # Leaf overrides root's routing-priority
        assert resolved.routing_priority == 90
        # Capabilities union: root=read, mid=write, leaf=search
        assert "read" in resolved.capabilities
        assert "write" in resolved.capabilities
        assert "search" in resolved.capabilities


# ── Multi-role routing ─────────────────────────────────────────────────────


from charter.offering.agent_profiles.repository import _filter_candidates_by_role, _exact_id_signal  # noqa: E402


def _make_profile(profile_id: str, roles: list[str]) -> AgentProfile:
    return AgentProfile(**{
        "profile-id": profile_id,
        "name": f"Test {profile_id}",
        "purpose": "Test purpose",
        "roles": roles,
        "specialization": {"primary-focus": "Testing"},
    })


class TestMultiRoleRouting:
    """Profiles with multiple roles — filter and signal behaviour."""

    def test_secondary_role_included_in_filter(self):
        """A profile with a secondary role passes the role filter for that role."""
        p = _make_profile("arch-alex", ["architect", "researcher"])
        assert p in _filter_candidates_by_role([p], "researcher")

    def test_mixed_case_role_included_in_filter(self):
        """Profile role list case is normalized before routing filters run."""
        p = _make_profile("arch-alex", ["ARCHITECT", "Researcher"])
        assert p in _filter_candidates_by_role([p], "researcher")

    def test_primary_role_included_in_filter(self):
        p = _make_profile("arch-alex", ["architect", "researcher"])
        assert p in _filter_candidates_by_role([p], "architect")

    def test_unrelated_role_excluded_from_filter(self):
        p = _make_profile("arch-alex", ["architect", "researcher"])
        assert p not in _filter_candidates_by_role([p], "implementer")

    def test_primary_role_signal_is_1_0(self):
        p = _make_profile("arch-alex", ["architect", "researcher"])
        ctx = TaskContext(required_role=Role("architect"))
        assert _exact_id_signal(ctx, p) == 1.0

    def test_mixed_case_primary_role_signal_is_1_0(self):
        p = _make_profile("arch-alex", ["ARCHITECT", "researcher"])
        ctx = TaskContext(required_role="architect")
        assert _exact_id_signal(ctx, p) == 1.0

    def test_secondary_role_signal_is_0_5(self):
        p = _make_profile("arch-alex", ["architect", "researcher"])
        ctx = TaskContext(required_role=Role("researcher"))
        assert _exact_id_signal(ctx, p) == 0.5

    def test_no_match_signal_is_0_0(self):
        p = _make_profile("arch-alex", ["architect", "researcher"])
        ctx = TaskContext(required_role=Role("implementer"))
        assert _exact_id_signal(ctx, p) == 0.0

    def test_profile_id_match_signal_is_1_0(self):
        p = _make_profile("arch-alex", ["architect"])
        ctx = TaskContext(required_role=Role("arch-alex"))
        assert _exact_id_signal(ctx, p) == 1.0

    def test_no_required_role_signal_is_0_0(self):
        p = _make_profile("arch-alex", ["architect"])
        ctx = TaskContext(required_role=None)
        assert _exact_id_signal(ctx, p) == 0.0


class TestRoleLookup:
    """find_by_role checks all role positions; get() is keyed by profile_id."""

    def _repo_with(self, *profiles: AgentProfile) -> AgentProfileRepository:
        repo = AgentProfileRepository.__new__(AgentProfileRepository)
        repo._profiles = {p.profile_id: p for p in profiles}
        repo._hierarchy_index = None
        return repo

    def test_find_by_role_returns_primary_role_profile(self):
        p = _make_profile("arch-alex", ["architect"])
        repo = self._repo_with(p)
        assert p in repo.find_by_role("architect")

    def test_find_by_role_returns_secondary_role_profile(self):
        """find_by_role checks all roles, not just primary."""
        p = _make_profile("arch-bob", ["implementer", "architect"])
        repo = self._repo_with(p)
        assert p in repo.find_by_role("architect")

    def test_find_by_role_returns_multiple_profiles_sharing_a_role(self):
        """When several profiles list the same role, all are returned."""
        primary = _make_profile("arch-alex", ["architect"])
        secondary = _make_profile("arch-bob", ["implementer", "architect"])
        repo = self._repo_with(primary, secondary)

        result = repo.find_by_role("architect")
        assert len(result) == 2
        assert primary in result
        assert secondary in result

    def test_find_by_role_returns_empty_when_no_match(self):
        p = _make_profile("arch-alex", ["architect"])
        repo = self._repo_with(p)
        assert repo.find_by_role("implementer") == []

    def test_find_by_role_returns_empty_for_blank_query(self):
        p = _make_profile("arch-alex", ["architect"])
        repo = self._repo_with(p)
        assert repo.find_by_role("") == []

    def test_find_by_role_with_role_instance(self):
        """find_by_role accepts a Role instance."""
        p = _make_profile("impl-ivan", ["implementer"])
        repo = self._repo_with(p)
        assert p in repo.find_by_role(Role.IMPLEMENTER)

    def test_find_by_role_normalizes_query_case(self):
        p = _make_profile("impl-ivan", ["implementer"])
        repo = self._repo_with(p)
        assert p in repo.find_by_role("IMPLEMENTER")

    def test_get_returns_profile_for_known_id(self):
        p = _make_profile("arch-alex", ["architect"])
        repo = self._repo_with(p)
        assert repo.get("arch-alex") is p

    def test_get_returns_none_for_unknown_id(self):
        repo = self._repo_with()
        assert repo.get("nonexistent") is None

    def test_get_is_unique_two_profiles_with_different_ids(self):
        """Different profile_ids never collide."""
        p1 = _make_profile("arch-alex", ["architect"])
        p2 = _make_profile("arch-bob", ["architect"])
        repo = self._repo_with(p1, p2)
        assert repo.get("arch-alex") is p1
        assert repo.get("arch-bob") is p2
        assert repo.get("arch-alex") is not p2


# ---------------------------------------------------------------------------
# WP03 T011 — direct unit tests for _parse_profile_from_file, extracted from
# _load_layer (R-011-B) to keep its cognitive complexity within the ruff C901
# limit (15).
# ---------------------------------------------------------------------------


class TestParseProfileFromFileDirect:
    def _repo(self, tmp_path: Path) -> AgentProfileRepository:
        """A minimally-loaded repository (no built-in dir) to host direct
        ``_parse_profile_from_file`` calls without pulling in shipped profiles."""
        empty = tmp_path / "empty-built-in"
        empty.mkdir()
        return AgentProfileRepository(built_in_dir=empty, project_dir=None)

    def test_returns_none_and_records_skip_for_empty_document(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo(tmp_path)
        empty_file = tmp_path / "empty.agent.yaml"
        empty_file.write_text("", encoding="utf-8")

        result = repo._parse_profile_from_file(
            YAML(typ="safe"), empty_file, layer="org", built_in_profiles={}
        )

        assert result is None
        summaries = [s.error_summary for s in repo.skipped_profiles()]
        assert any("Empty profile file" in s for s in summaries)

    def test_returns_none_and_records_skip_for_missing_profile_id(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo(tmp_path)
        no_id_file = tmp_path / "noid.agent.yaml"
        no_id_file.write_text("name: No ID Profile\n", encoding="utf-8")

        result = repo._parse_profile_from_file(
            YAML(typ="safe"), no_id_file, layer="org", built_in_profiles={}
        )

        assert result is None
        skips = repo.skipped_profiles()
        assert any(s.path == str(no_id_file) for s in skips)

    def test_returns_none_and_records_skip_for_unparsable_yaml(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo(tmp_path)
        bad_file = tmp_path / "bad.agent.yaml"
        bad_file.write_text("profile-id: [unterminated\n", encoding="utf-8")

        result = repo._parse_profile_from_file(
            YAML(typ="safe"), bad_file, layer="org", built_in_profiles={}
        )

        assert result is None
        summaries = [s.error_summary for s in repo.skipped_profiles()]
        assert any("YAML/read error" in s for s in summaries)

    def test_returns_none_and_records_skip_for_schema_validation_failure(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo(tmp_path)
        broken_file = tmp_path / "broken.agent.yaml"
        # 'purpose' and 'specialization' are required and deliberately omitted.
        broken_file.write_text(
            "profile-id: broken\nname: Broken\nroles:\n  - implementer\n",
            encoding="utf-8",
        )

        result = repo._parse_profile_from_file(
            YAML(typ="safe"), broken_file, layer="org", built_in_profiles={}
        )

        assert result is None
        skips = repo.skipped_profiles()
        assert any(s.profile_id == "broken" for s in skips)

    def test_returns_profile_for_valid_builtin_layer_file(
        self, tmp_path: Path, minimal_profile_yaml: str
    ) -> None:
        repo = self._repo(tmp_path)
        valid_file = tmp_path / "valid.agent.yaml"
        valid_file.write_text(minimal_profile_yaml, encoding="utf-8")

        result = repo._parse_profile_from_file(
            YAML(typ="safe"), valid_file, layer="builtin", built_in_profiles={}
        )

        assert result is not None
        assert result.profile_id == "test-profile"
        # builtin layer never triggers the collision diagnostic.
        assert repo.skipped_profiles() == []

    def test_merges_onto_built_in_when_profile_id_already_present(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo(tmp_path)
        base = AgentProfile.model_validate(
            {
                "profile-id": "test-profile",
                "name": "Base Name",
                "purpose": "Base purpose",
                "roles": ["implementer"],
                "specialization": {"primary-focus": "Base focus"},
            }
        )
        override_file = tmp_path / "override.agent.yaml"
        override_file.write_text(
            "profile-id: test-profile\nname: Overridden Name\n", encoding="utf-8"
        )

        result = repo._parse_profile_from_file(
            YAML(typ="safe"),
            override_file,
            layer="org",
            built_in_profiles={"test-profile": base},
        )

        assert result is not None
        assert result.name == "Overridden Name"
        assert result.purpose == "Base purpose"  # inherited, field-merge
