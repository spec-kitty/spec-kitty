"""
Integration tests for shipped reference profiles.

Verifies that all shipped reference profiles:
- Load via AgentProfileRepository
- Pass schema validation
- Have no hierarchy errors
- Have no duplicate profile_ids
- Have non-empty purpose and specialization.primary_focus
"""

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.agent_profiles.profile import AgentProfile, Role
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.agent_profiles.validation import validate_agent_profile_yaml
from charter.offering.pack_paths import resolve_pack_root
from tests.doctrine._builtin_inventory import builtin_profile_ids

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
# Post-relocation the shipped built-in profiles live at
# ``packs/built-in/agent_profiles/`` (the per-kind ``built-in/`` subdir was
# flattened out). Resolve through the canonical pack-root seam rather than a
# ``src/doctrine`` literal, which is now emptied of built-in content.
BUILT_IN_DIR = resolve_pack_root("built-in") / "agent_profiles"
MISSION_RUNTIME_DIRS = (
    # Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
    # relocated missions/ from src/charter/offering/missions to packs/built-in/missions.
    REPO_ROOT / "packs" / "built-in" / "missions",
    # The repo-local ``.kittify/overrides/missions`` mirror tier was deleted by
    # #5128 (its absence is guarded in tests/dossier/test_manifest.py), so the
    # built-in pack is the only mission-runtime surface left to scan.
)
# The Python-package README (``src/charter/offering/agent_profiles/README.md``) was NOT
# relocated; the built-in-pack README moved to the flattened pack dir.
AGENT_PROFILES_README = REPO_ROOT / "src" / "charter" / "offering" / "agent_profiles" / "README.md"
BUILT_IN_README = BUILT_IN_DIR / "README.md"

# Derived from the shipped ``packs/built-in/agent_profiles/*.agent.yaml`` source
# files (#3234), not a frozen literal: this drives the per-profile contract
# parametrization AND is the independent inventory the load assertions compare
# against. ``builtin_profile_ids()`` globs the source files and parses each
# ``profile-id``; the repository fixtures below LOAD those files through the real
# ``AgentProfileRepository`` pipeline. So ``loaded_ids == EXPECTED_PROFILE_IDS``
# still reds if the loader skips a shipped profile or loads a mismatched id --
# but a newly-added profile file is inventoried automatically and does not red.
EXPECTED_PROFILE_IDS = builtin_profile_ids()

# Sentinel profiles are workflow markers, not real agents.  They intentionally
# have empty context sources and directive references.
_SENTINEL_PROFILES = {"human-in-charge"}
_AGENT_PROFILE_IDS = EXPECTED_PROFILE_IDS - _SENTINEL_PROFILES


def _profile_ids_from_yaml_files() -> set[str]:
    yaml = YAML(typ="safe")
    profile_ids = set()
    for yaml_file in BUILT_IN_DIR.glob("*.agent.yaml"):
        with yaml_file.open() as f:
            data = yaml.load(f)
        profile_ids.add(data["profile-id"])
    return profile_ids


def _profile_ids_from_readme_table(readme_path: Path, profile_id_column: str) -> set[str]:
    lines = readme_path.read_text().splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if profile_id_column not in cells:
            continue
        column_index = cells.index(profile_id_column)
        profile_ids = set()
        for row in lines[index + 2 :]:
            if not row.startswith("|"):
                break
            row_cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            profile_ids.add(row_cells[column_index].strip("`"))
        return profile_ids
    raise AssertionError(f"No markdown table with column {profile_id_column!r} in {readme_path}")


def _iter_agent_profile_refs(value: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "agent-profile" and isinstance(child, str):
                refs.add(child)
            refs.update(_iter_agent_profile_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_iter_agent_profile_refs(child))
    return refs


@pytest.fixture(scope="module")
def repo() -> AgentProfileRepository:
    """Load repository from the actual shipped profiles directory."""
    return AgentProfileRepository(built_in_dir=BUILT_IN_DIR, project_dir=None)


@pytest.fixture(scope="module")
def all_profiles(repo: AgentProfileRepository) -> list[AgentProfile]:
    """All loaded profiles from shipped directory."""
    return repo.list_all()


class TestShippedProfilesLoad:
    """Verify all shipped profiles load correctly."""

    def test_shipped_dir_exists(self):
        """Shipped profiles directory exists."""
        assert BUILT_IN_DIR.exists(), f"Shipped directory not found: {BUILT_IN_DIR}"
        assert BUILT_IN_DIR.is_dir()

    def test_all_profiles_load(self, all_profiles: list[AgentProfile]):
        """All expected profiles are loaded."""
        assert len(all_profiles) == len(EXPECTED_PROFILE_IDS), (
            f"Expected {len(EXPECTED_PROFILE_IDS)} profiles, got {len(all_profiles)}: "
            f"{[p.profile_id for p in all_profiles]}"
        )

    def test_expected_profile_ids_present(self, all_profiles: list[AgentProfile]):
        """All expected profile IDs are present."""
        loaded_ids = {p.profile_id for p in all_profiles}
        assert loaded_ids == EXPECTED_PROFILE_IDS, (
            f"Missing: {EXPECTED_PROFILE_IDS - loaded_ids}, Extra: {loaded_ids - EXPECTED_PROFILE_IDS}"
        )

    def test_mission_runtime_agent_profiles_are_shipped(self):
        """Mission runtime templates only reference shipped profile IDs."""
        yaml = YAML(typ="safe")
        refs_by_path: dict[str, set[str]] = {}
        for runtime_dir in MISSION_RUNTIME_DIRS:
            for runtime_path in runtime_dir.glob("*/mission-runtime.yaml"):
                data = yaml.load(runtime_path.read_text(encoding="utf-8")) or {}
                refs = _iter_agent_profile_refs(data)
                missing = refs - EXPECTED_PROFILE_IDS
                if missing:
                    refs_by_path[str(runtime_path.relative_to(REPO_ROOT))] = missing

        assert refs_by_path == {}

    def test_no_duplicate_profile_ids(self, all_profiles: list[AgentProfile]):
        """No duplicate profile IDs exist."""
        ids = [p.profile_id for p in all_profiles]
        assert len(ids) == len(set(ids)), f"Duplicate profile IDs found: {ids}"

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_each_profile_accessible_by_id(self, repo: AgentProfileRepository, profile_id: str):
        """Each shipped profile is accessible via repo.get()."""
        profile = repo.get(profile_id)
        assert profile is not None, f"Profile '{profile_id}' not found in repository"
        assert profile.profile_id == profile_id

    @pytest.mark.parametrize(
        "readme_path,profile_id_column",
        [
            (AGENT_PROFILES_README, "Profile ID"),
            (BUILT_IN_README, "Profile ID"),
        ],
    )
    def test_readme_profile_ids_match_shipped_yaml(
        self,
        readme_path: Path,
        profile_id_column: str,
    ):
        """README shipped-profile tables list exactly the packaged profile ids."""
        actual_ids = _profile_ids_from_yaml_files()
        readme_ids = _profile_ids_from_readme_table(readme_path, profile_id_column)
        assert readme_ids == actual_ids, f"{readme_path} drifted from shipped profiles"


class TestShippedProfilesRoles:
    """Verify profiles have correct roles."""

    @pytest.mark.parametrize(
        "profile_id,expected_role",
        [
            ("architect-alphonso", Role.ARCHITECT),
            ("designer-dagmar", Role.DESIGNER),
            ("generic-agent", Role.IMPLEMENTER),
            ("implementer-ivan", Role.IMPLEMENTER),
            ("python-pedro", Role.IMPLEMENTER),
            ("reviewer-renata", Role.REVIEWER),
            ("frontend-freddy", Role.IMPLEMENTER),
            ("node-norris", Role.IMPLEMENTER),
            ("paula-patterns", "architecture-scout"),
            ("planner-priti", Role.PLANNER),
            ("randy-reducer", Role.IMPLEMENTER),
            ("researcher-robbie", Role.RESEARCHER),
            ("curator-carla", Role.CURATOR),
            ("doctrine-daphne", Role.CURATOR),
        ],
    )
    def test_profile_has_correct_role(
        self,
        repo: AgentProfileRepository,
        profile_id: str,
        expected_role: Role,
    ):
        """Each profile has the correct primary role."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.role == expected_role, (
            f"Profile '{profile_id}' has role={profile.role!r}, expected {expected_role!r}"
        )

    def test_all_shipped_profiles_have_roles(self, all_profiles: list[AgentProfile]):
        """Every shipped profile has at least one role in the roles list."""
        for profile in all_profiles:
            assert len(profile.roles) >= 1, (
                f"Profile '{profile.profile_id}' has empty roles list"
            )

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_no_deprecation_warnings_on_load(self, profile_id: str):
        """Loading shipped profiles must not emit DeprecationWarning (no scalar role: field)."""
        import warnings
        from ruamel.yaml import YAML as _YAML

        yaml = _YAML(typ="safe")
        yaml_file = BUILT_IN_DIR / f"{profile_id}.agent.yaml"
        with yaml_file.open() as f:
            data = yaml.load(f)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AgentProfile(**data)
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0, (
            f"Profile '{profile_id}' emits DeprecationWarning on load: "
            + str([str(x.message) for x in deprecation_warnings])
        )


class TestShippedProfilesContent:
    """Verify profiles have non-empty required content."""

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_purpose_is_non_empty(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has a non-empty purpose."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.purpose.strip(), f"Profile '{profile_id}' has empty purpose"

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_primary_focus_is_non_empty(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has a non-empty specialization.primary_focus."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.specialization.primary_focus.strip(), (
            f"Profile '{profile_id}' has empty specialization.primary_focus"
        )

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_name_is_non_empty(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has a non-empty name."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.name.strip(), f"Profile '{profile_id}' has empty name"

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_self_identity_prose_matches_name(self, repo: AgentProfileRepository, profile_id: str):
        """Any "<role-word> <Token>"-shaped self-identity phrase in purpose/init prose
        must equal the profile's own name.

        DIRECTIVE_043 (Close Defect Classes by Construction): the profile's own
        ``name:`` field is the single source of truth for identity. Prose that
        restates identity (e.g. "Researcher Robbie reduces uncertainty...", "I am
        Researcher Robbie...") is free to do so, but it must not drift from
        ``name`` the way researcher-robbie's purpose/init once drifted to
        "Researcher Rosa". This does not require every profile to declare an
        identity at all -- several (generic-agent, human-in-charge,
        retrospective-facilitator) phrase their prose differently and are left
        untouched by this check.
        """
        profile = repo.get(profile_id)
        assert profile is not None
        role_word = profile.name.split()[0]
        prose = f"{profile.purpose}\n{profile.initialization_declaration}"
        pattern = re.compile(rf"\b{re.escape(role_word)}\s+[A-Z][A-Za-z'-]*\b")
        for match in pattern.finditer(prose):
            assert match.group(0) == profile.name, (
                f"Profile '{profile_id}' prose declares identity '{match.group(0)}' "
                f"which does not match its own name '{profile.name}'"
            )

    @pytest.mark.parametrize(
        "profile_id,expected_priority",
        [
            ("architect-alphonso", 50),
            ("designer-dagmar", 50),
            ("generic-agent", 10),
            ("implementer-ivan", 50),
            ("python-pedro", 80),
            ("reviewer-renata", 50),
            ("frontend-freddy", 80),
            ("node-norris", 80),
            ("paula-patterns", 65),
            ("planner-priti", 50),
            ("randy-reducer", 70),
            ("researcher-robbie", 40),
            ("curator-carla", 40),
            ("doctrine-daphne", 48),
        ],
    )
    def test_routing_priority(
        self,
        repo: AgentProfileRepository,
        profile_id: str,
        expected_priority: int,
    ):
        """Each profile has the expected routing priority."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.routing_priority == expected_priority, (
            f"Profile '{profile_id}' has routing_priority={profile.routing_priority}, expected {expected_priority}"
        )

    @pytest.mark.parametrize(
        "profile_id,expected_max",
        [
            ("architect-alphonso", 3),
            ("designer-dagmar", 4),
            ("generic-agent", 5),
            ("implementer-ivan", 5),
            ("python-pedro", 5),
            ("reviewer-renata", 8),
            ("frontend-freddy", 5),
            ("node-norris", 5),
            ("paula-patterns", 1),
            ("planner-priti", 3),
            ("randy-reducer", 2),
            ("researcher-robbie", 4),
            ("curator-carla", 6),
            ("doctrine-daphne", 4),
        ],
    )
    def test_max_concurrent_tasks(
        self,
        repo: AgentProfileRepository,
        profile_id: str,
        expected_max: int,
    ):
        """Each profile has the expected max_concurrent_tasks."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert profile.max_concurrent_tasks == expected_max, (
            f"Profile '{profile_id}' has max_concurrent_tasks={profile.max_concurrent_tasks}, expected {expected_max}"
        )


class TestShippedProfilesSchemaValidation:
    """Verify all profiles pass YAML schema validation."""

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILE_IDS))
    def test_profile_passes_schema_validation(self, profile_id: str):
        """Each shipped profile passes the agent-profile JSON schema validation."""
        yaml_file = BUILT_IN_DIR / f"{profile_id}.agent.yaml"
        assert yaml_file.exists(), f"Profile file not found: {yaml_file}"

        yaml = YAML(typ="safe")
        with yaml_file.open() as f:
            data = yaml.load(f)

        errors = validate_agent_profile_yaml(data)
        assert errors == [], f"Schema validation failed for '{profile_id}':\n" + "\n".join(f"  - {e}" for e in errors)


class TestShippedProfilesHierarchy:
    """Verify hierarchy validation returns no errors."""

    def test_validate_hierarchy_returns_no_errors(self, repo: AgentProfileRepository):
        """Shipped profiles have valid hierarchy (no cycles, no orphans)."""
        errors = repo.validate_hierarchy()
        assert errors == [], "Hierarchy validation failed:\n" + "\n".join(f"  - {e}" for e in errors)

    def test_specializes_from_targets_exist(
        self, repo: AgentProfileRepository, all_profiles: list[AgentProfile]
    ):
        """Any shipped profile that specializes from another must reference an existing shipped profile.

        Lineage is now sourced from the DRG ``specializes_from`` edges
        (FR-002 / WP05), not the retired ``specializes-from`` profile field.
        """
        shipped_ids = {p.profile_id for p in all_profiles}
        for profile in all_profiles:
            # Immediate lineage parent (if any) per the DRG.
            ancestors = repo.get_ancestors(profile.profile_id)
            if ancestors:
                parent = ancestors[0]
                assert parent in shipped_ids, (
                    f"Shipped profile '{profile.profile_id}' specializes from "
                    f"'{parent}', which is not a shipped profile"
                )


class TestShippedProfilesCollaboration:
    """Verify collaboration contracts have required fields."""

    @pytest.mark.parametrize("profile_id", sorted(_AGENT_PROFILE_IDS))
    def test_collaboration_has_canonical_verbs(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has at least one canonical verb."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert len(profile.collaboration.canonical_verbs) > 0, f"Profile '{profile_id}' has no canonical verbs"

    @pytest.mark.parametrize("profile_id", sorted(_AGENT_PROFILE_IDS))
    def test_collaboration_has_output_artifacts(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile defines at least one output artifact."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert len(profile.collaboration.output_artifacts) > 0, f"Profile '{profile_id}' has no output artifacts"

    @pytest.mark.parametrize("profile_id", sorted(_AGENT_PROFILE_IDS))
    def test_mode_defaults_are_non_empty(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has at least one mode default."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert len(profile.mode_defaults) > 0, f"Profile '{profile_id}' has no mode defaults"

    @pytest.mark.parametrize("profile_id", sorted(_AGENT_PROFILE_IDS))
    def test_mode_defaults_have_use_case(self, repo: AgentProfileRepository, profile_id: str):
        """Each mode default has a non-empty use_case."""
        profile = repo.get(profile_id)
        assert profile is not None
        for mode in profile.mode_defaults:
            assert mode.use_case.strip(), f"Profile '{profile_id}' mode '{mode.mode}' has empty use_case"


class TestShippedProfilesContextSources:
    """Verify the canonical ``*-references`` doctrine surface is defined.

    The retired ``context-sources`` surface was removed in mission
    doctrine-drg-silent-drop-boundary-01M0PE7E; profiles now carry references
    solely on the top-level ``*-references`` fields.
    """

    @pytest.mark.parametrize("profile_id", sorted(_AGENT_PROFILE_IDS))
    def test_directive_references_are_defined(self, repo: AgentProfileRepository, profile_id: str):
        """Each profile has at least one directive reference."""
        profile = repo.get(profile_id)
        assert profile is not None
        assert len(profile.directive_references) > 0, f"Profile '{profile_id}' has no directive references"

    @pytest.mark.parametrize(
        "profile_id,expected_tactics",
        [
            (
                "debugger-debbie",
                [
                    "five-paradigm-parallel-debugging",
                    "code-review-incremental",
                    "review-intent-and-risk-first",
                ],
            ),
            (
                "paula-patterns",
                [
                    "paula-patterns-architecture-scout-review",
                    "anti-corruption-layer",
                    "domain-event-capture",
                    "review-intent-and-risk-first",
                ],
            ),
            (
                "reviewer-renata",
                [
                    "code-review-incremental",
                    "language-driven-design",
                    "reverse-speccing",
                    "test-scaffolding-as-design-smell",
                    "supply-chain-install-safety",
                ],
            ),
        ],
    )
    def test_shipped_tactic_references_include_expected(
        self,
        repo: AgentProfileRepository,
        profile_id: str,
        expected_tactics: list[str],
    ):
        """Shipped tactic references survive loading and cover the tactics that
        the retired ``context-sources.tactics`` surface used to pin.

        The consolidation folded ``context-sources.tactics`` (a subset) onto the
        canonical ``tactic-references`` surface; every previously-pinned tactic
        must remain reachable there.
        """
        profile = repo.get(profile_id)
        assert profile is not None
        tactic_ids = {ref.id for ref in profile.tactic_references}
        missing = [t for t in expected_tactics if t not in tactic_ids]
        assert missing == [], (
            f"Profile '{profile_id}' lost tactic references {missing} in the "
            f"context-sources consolidation; present: {sorted(tactic_ids)}"
        )


class TestShippedProfilesLoadCount:
    """Functional companion to TestShippedProfilesPerformance (split, #4015):
    the load-count check must run on the per-PR path, not only nightly."""

    def test_shipped_profile_load_returns_all_profiles(self) -> None:
        """Loading all shipped profiles returns exactly EXPECTED_PROFILE_IDS."""
        repo = AgentProfileRepository(built_in_dir=BUILT_IN_DIR, project_dir=None)
        profiles = repo.list_all()

        assert len(profiles) == len(EXPECTED_PROFILE_IDS), (
            f"Expected {len(EXPECTED_PROFILE_IDS)} profiles, got {len(profiles)}"
        )


@pytest.mark.performance
class TestShippedProfilesPerformance:
    """Performance gate: loading all shipped profiles must complete quickly.

    Timing budget only (split, #4015): functional coverage moved to
    TestShippedProfilesLoadCount, above.
    """

    def test_shipped_profile_load_time(self) -> None:
        """Loading all shipped profiles must complete in under 2 seconds."""
        import time

        from tests._perf_helpers import assert_timing_budget

        start = time.perf_counter()
        repo = AgentProfileRepository(built_in_dir=BUILT_IN_DIR, project_dir=None)
        repo.list_all()
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 2.0, name="shipped_profile_load")
