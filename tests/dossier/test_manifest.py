"""Tests for expected artifact manifest system (WP02).

Tests cover:
- Manifest schema validation
- YAML loading from expected-artifacts.yaml files
- ManifestRegistry loading and caching
- Step-aware artifact querying
- Unknown mission handling (graceful degradation)
- Path pattern validation
"""

import pytest
from pathlib import Path
from typing import Optional
from pydantic import ValidationError
from ruamel.yaml import YAML

from specify_cli.dossier.manifest import (
    ArtifactClassEnum,
    ExpectedArtifactSpec,
    ExpectedArtifactManifest,
    ManifestRegistry,
    ManifestSchemaError,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestArtifactClassEnum:
    """Test ArtifactClassEnum values and usage."""

    def test_enum_values_exist(self):
        """Verify all expected enum values exist."""
        assert ArtifactClassEnum.INPUT.value == "input"
        assert ArtifactClassEnum.WORKFLOW.value == "workflow"
        assert ArtifactClassEnum.OUTPUT.value == "output"
        assert ArtifactClassEnum.EVIDENCE.value == "evidence"
        assert ArtifactClassEnum.POLICY.value == "policy"
        assert ArtifactClassEnum.RUNTIME.value == "runtime"

    def test_enum_has_six_values(self):
        """Verify exactly 6 artifact classes."""
        assert frozenset(m.name for m in ArtifactClassEnum) == frozenset({"INPUT", "WORKFLOW", "OUTPUT", "EVIDENCE", "POLICY", "RUNTIME"})


class TestExpectedArtifactSpec:
    """Test ExpectedArtifactSpec model creation and validation."""

    def test_create_simple_spec(self):
        """Create a simple artifact spec."""
        spec = ExpectedArtifactSpec(
            artifact_key="input.spec.main",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
        )
        assert spec.artifact_key == "input.spec.main"
        assert spec.artifact_class == ArtifactClassEnum.INPUT
        assert spec.path_pattern == "spec.md"
        assert spec.blocking is False  # Default

    def test_create_blocking_spec(self):
        """Create a blocking artifact spec."""
        spec = ExpectedArtifactSpec(
            artifact_key="output.tasks.list",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="tasks.md",
            blocking=True,
        )
        assert spec.blocking is True

    def test_artifact_key_with_dots_and_underscores(self):
        """Artifact keys can use dots and underscores."""
        spec = ExpectedArtifactSpec(
            artifact_key="evidence.gap_analysis.final",
            artifact_class=ArtifactClassEnum.EVIDENCE,
            path_pattern="gap-analysis.md",
        )
        assert spec.artifact_key == "evidence.gap_analysis.final"

    def test_path_pattern_with_wildcards(self):
        """Path patterns support glob wildcards."""
        spec = ExpectedArtifactSpec(
            artifact_key="output.tasks.per_wp",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="tasks/*.md",
        )
        assert spec.path_pattern == "tasks/*.md"

    def test_path_pattern_with_double_wildcards(self):
        """Path patterns support recursive glob.**."""
        spec = ExpectedArtifactSpec(
            artifact_key="output.docs.all",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="docs/**/*.md",
        )
        assert spec.path_pattern == "docs/**/*.md"

    def test_invalid_artifact_class_string(self):
        """Invalid artifact_class string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ExpectedArtifactSpec(
                artifact_key="test.key",
                artifact_class="invalid_class",  # type: ignore
                path_pattern="test.md",
            )
        assert "artifact_class" in str(exc_info.value)

    def test_empty_artifact_key_invalid(self):
        """Empty artifact_key is invalid."""
        with pytest.raises(ValidationError):
            ExpectedArtifactSpec(
                artifact_key="",
                artifact_class=ArtifactClassEnum.INPUT,
                path_pattern="spec.md",
            )

    def test_empty_path_pattern_invalid(self):
        """Empty path_pattern is invalid."""
        with pytest.raises(ValidationError):
            ExpectedArtifactSpec(
                artifact_key="test.key",
                artifact_class=ArtifactClassEnum.INPUT,
                path_pattern="",
            )


class TestExpectedArtifactManifest:
    """Test ExpectedArtifactManifest model and methods."""

    def test_create_empty_manifest(self):
        """Create a manifest with only mission_type."""
        manifest = ExpectedArtifactManifest(mission_type="software-dev")
        assert manifest.mission_type == "software-dev"
        assert manifest.schema_version == "1.0"
        assert manifest.manifest_version == "1"
        assert manifest.required_always == []
        assert manifest.required_by_step == {}
        assert manifest.optional_always == []

    def test_create_manifest_with_specs(self):
        """Create a manifest with artifact specs."""
        spec1 = ExpectedArtifactSpec(
            artifact_key="input.spec.main",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
            blocking=True,
        )
        spec2 = ExpectedArtifactSpec(
            artifact_key="evidence.research",
            artifact_class=ArtifactClassEnum.EVIDENCE,
            path_pattern="research.md",
            blocking=False,
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_always=[spec1],
            optional_always=[spec2],
        )
        assert [s.artifact_key for s in manifest.required_always] == ["input.spec.main"]
        assert [s.artifact_key for s in manifest.optional_always] == ["evidence.research"]

    def test_create_manifest_with_step_specs(self):
        """Create a manifest with step-specific specs."""
        spec = ExpectedArtifactSpec(
            artifact_key="output.plan.main",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="plan.md",
            blocking=True,
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_by_step={"plan": [spec]},
        )
        assert "plan" in manifest.required_by_step
        assert len(manifest.required_by_step["plan"]) == 1

    def test_get_step_ids(self):
        """Get list of step IDs from manifest."""
        manifest = ExpectedArtifactManifest(
            mission_type="research",
            required_by_step={
                "scoping": [],
                "methodology": [],
                "gathering": [],
                "synthesis": [],
            },
        )
        step_ids = manifest.get_step_ids()
        assert set(step_ids) == {"scoping", "methodology", "gathering", "synthesis"}


class TestManifestRegistry:
    """Test ManifestRegistry loading and querying."""

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        ManifestRegistry.clear_cache()

    def test_load_software_dev_manifest(self):
        """Load software-dev manifest successfully."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        assert manifest.mission_type == "software-dev"
        assert manifest.schema_version == "1.0"

    def test_load_research_manifest(self):
        """Load research manifest successfully."""
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        assert manifest.mission_type == "research"

    def test_load_documentation_manifest(self):
        """Load documentation manifest successfully."""
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None
        assert manifest.mission_type == "documentation"

    def test_load_unknown_mission_returns_none(self):
        """Unknown mission type returns None (graceful degradation)."""
        manifest = ManifestRegistry.load_manifest("unknown_mission_xyz")
        assert manifest is None

    def test_manifest_caching(self):
        """Manifest is cached after first load."""
        manifest1 = ManifestRegistry.load_manifest("software-dev")
        manifest2 = ManifestRegistry.load_manifest("software-dev")
        assert manifest1 is manifest2  # Same object (cached)

    def test_unknown_mission_cached_as_none(self):
        """Unknown mission type cached as None."""
        result1 = ManifestRegistry.load_manifest("fake_mission")
        result2 = ManifestRegistry.load_manifest("fake_mission")
        assert result1 is None
        assert result2 is None

    def test_get_required_artifacts_specify_step(self):
        """Get required artifacts for software-dev specify step."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "specify")
        assert len(specs) > 0
        # Should include spec.md requirement
        assert any(s.artifact_key == "input.spec.main" for s in specs)

    def test_get_required_artifacts_plan_step(self):
        """Get required artifacts for software-dev plan step."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "plan")
        assert [s.artifact_key for s in specs] == ["output.plan.main"]

    def test_get_required_artifacts_unknown_step(self):
        """Get required artifacts for unknown step returns gracefully."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "nonexistent_step")
        # Should return only required_always (may be empty)
        assert specs is not None

    def test_get_blocking_artifacts(self):
        """Filter to blocking artifacts only."""
        spec1 = ExpectedArtifactSpec(
            artifact_key="key1",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
            blocking=True,
        )
        spec2 = ExpectedArtifactSpec(
            artifact_key="key2",
            artifact_class=ArtifactClassEnum.EVIDENCE,
            path_pattern="research.md",
            blocking=False,
        )
        specs = [spec1, spec2]
        blocking = ManifestRegistry.get_blocking_artifacts(specs)
        assert [b.artifact_key for b in blocking] == ["key1"]

    def test_get_optional_artifacts(self):
        """Get optional artifacts from manifest."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        optional = ManifestRegistry.get_optional_artifacts(manifest)
        assert len(optional) > 0
        # All should have blocking=False
        assert all(not s.blocking for s in optional)

    def test_software_dev_manifest_has_all_states(self):
        """Software-dev manifest covers all states."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        step_ids = manifest.get_step_ids()
        # Should have steps for discovery, specify, plan, implement, review, done
        expected_steps = {"discovery", "specify", "plan", "implement", "review", "done"}
        assert expected_steps.issubset(set(step_ids))

    def test_research_manifest_has_all_states(self):
        """Research manifest covers all states."""
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        step_ids = manifest.get_step_ids()
        # Should have research-specific states
        expected_steps = {"scoping", "methodology", "gathering", "synthesis", "output", "done"}
        assert expected_steps.issubset(set(step_ids))

    def test_documentation_manifest_has_all_states(self):
        """Documentation manifest covers expected states."""
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None
        step_ids = manifest.get_step_ids()
        # Should have documentation-specific states
        assert len(step_ids) > 0


class TestManifestValidation:
    """Test manifest validation."""

    def test_validate_valid_manifest(self):
        """Validate a valid manifest."""
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_by_step={"specify": []},
        )
        mission_dir = Path(__file__).parent.parent.parent / "missions" / "software-dev"
        is_valid, errors = ManifestRegistry.validate_manifest(manifest, mission_dir)
        # Should pass or only have minor warnings
        assert isinstance(is_valid, bool)

    def test_validate_manifest_with_absolute_path(self):
        """Manifest with absolute path should fail validation."""
        spec = ExpectedArtifactSpec(
            artifact_key="test.key",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="/absolute/path/spec.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="test",
            required_always=[spec],
        )
        mission_dir = Path(".")
        is_valid, errors = ManifestRegistry.validate_manifest(manifest, mission_dir)
        assert not is_valid
        assert any("absolute" in e.lower() for e in errors)

    def test_validate_manifest_with_parent_reference(self):
        """Manifest with parent directory reference should fail."""
        spec = ExpectedArtifactSpec(
            artifact_key="test.key",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="../spec.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="test",
            required_always=[spec],
        )
        mission_dir = Path(".")
        is_valid, errors = ManifestRegistry.validate_manifest(manifest, mission_dir)
        assert not is_valid
        assert any("parent" in e.lower() for e in errors)

    def test_clear_cache(self):
        """Test cache clearing."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        # Cache should have entry
        assert len(ManifestRegistry._cache) > 0
        ManifestRegistry.clear_cache()
        assert len(ManifestRegistry._cache) == 0


class TestManifestIntegration:
    """Integration tests with actual manifest files."""

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def test_software_dev_manifest_spec_step_has_spec_requirement(self):
        """software-dev manifest requires spec.md at specify step."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "specify")
        # Find spec.md requirement
        spec_md = [s for s in specs if s.artifact_key == "input.spec.main"]
        assert len(spec_md) > 0
        assert spec_md[0].blocking is True
        assert spec_md[0].path_pattern == "spec.md"

    def test_software_dev_manifest_plan_step_has_plan_only(self):
        """software-dev manifest requires only plan.md at plan step."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "plan")
        plan_md = [s for s in specs if s.artifact_key == "output.plan.main"]
        tasks_md = [s for s in specs if s.artifact_key == "output.tasks.list"]
        assert len(plan_md) > 0
        assert tasks_md == []
        assert all(s.blocking for s in plan_md)

    def test_software_dev_has_optional_research_evidence(self):
        """software-dev manifest includes optional research.md."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        optional = ManifestRegistry.get_optional_artifacts(manifest)
        research = [s for s in optional if s.artifact_key == "evidence.research"]
        assert len(research) > 0
        assert research[0].path_pattern == "research.md"

    def test_software_dev_tasks_outline_requires_tasks_artifact(self):
        """software-dev manifest requires tasks.md at the tasks-outline step."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "tasks_outline")
        tasks = [s for s in specs if s.artifact_key == "output.tasks.list"]
        assert len(tasks) > 0
        assert tasks[0].blocking is True
        assert tasks[0].path_pattern == "tasks.md"

    def test_research_manifest_scoping_step_requires_spec(self):
        """research manifest requires spec.md at scoping step."""
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "scoping")
        assert any(s.artifact_key == "input.spec.research" for s in specs)

    def test_research_manifest_synthesis_step_requires_findings(self):
        """research manifest requires findings.md at synthesis step."""
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "synthesis")
        assert any(s.artifact_key == "output.findings.main" for s in specs)

    def test_documentation_manifest_audit_requires_gap_analysis(self):
        """documentation manifest requires gap-analysis.md at audit step."""
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "audit")
        # Gap analysis should be required for audit step
        gap = [s for s in specs if s.artifact_key == "evidence.gap-analysis"]
        assert len(gap) > 0


class TestManifestYAMLFormat:
    """Test manifest loading from the shipped YAML files.

    T003 (WP01 / #3770): ``ExpectedArtifactManifest.from_yaml_file`` was
    deleted -- it constructed via ``cls(**data)``, a bare-construction path
    the arch-gate forbidding bare ``model_validate(``/bare
    ``ExpectedArtifactManifest(`` cannot police (FR-013/D6). These three
    tests are migrated to the canonical loader
    (``ManifestRegistry.load_manifest``, which internally reads the same
    on-disk files via ``MissionTemplateRepository.get_expected_artifacts``
    and applies ``model_validate``), preserving the original intent (each
    shipped manifest loads and reports the right ``mission_type``).
    """

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        ManifestRegistry.clear_cache()

    def test_from_yaml_file_software_dev(self):
        """Load software-dev manifest through the canonical loader."""
        yaml_path = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions" / "software-dev" / "expected-artifacts.yaml"
        assert yaml_path.exists(), f"Manifest file not found: {yaml_path}"
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        assert manifest.mission_type == "software-dev"

    def test_from_yaml_file_research(self):
        """Load research manifest through the canonical loader."""
        yaml_path = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions" / "research" / "expected-artifacts.yaml"
        assert yaml_path.exists(), f"Manifest file not found: {yaml_path}"
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        assert manifest.mission_type == "research"

    def test_from_yaml_file_documentation(self):
        """Load documentation manifest through the canonical loader."""
        yaml_path = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions" / "documentation" / "expected-artifacts.yaml"
        assert yaml_path.exists(), f"Manifest file not found: {yaml_path}"
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None
        assert manifest.mission_type == "documentation"


# ---------------------------------------------------------------------------
# T005 (WP01, mission expected-artifacts-loader-unification-01M1C9VQ, #3770):
# shim re-export object-identity contract
# (contracts/shim-reexport-surface.md) + cache-delegate characterization.
#
# All tests below are CHARACTERIZATION (green-stays-green), never
# @pytest.mark.regression (D8) -- they lock a refactor-time invariant, not a
# behavior that was ever red on main.
# ---------------------------------------------------------------------------


class TestManifestLoaderShimReexportSurface:
    """FR-002/contracts/shim-reexport-surface.md: the four relocated names
    (`ManifestRegistry`, `load_manifest`, `ManifestSchemaError`,
    `MalformedManifestError`) still resolve from the OLD
    `specify_cli.dossier.manifest` path after WP01's relocation, with OBJECT
    IDENTITY to the new charter-resident authority -- not a re-implemented
    copy. Identity (not mere equality) matters because 8+ pre-existing
    `except ManifestSchemaError`/`except MalformedManifestError` catch sites
    (`sync/namespace.py`, `sync/dossier_pipeline.py`, and this file's own
    tests) must keep catching errors the charter authority raises.
    """

    def test_manifest_schema_error_is_the_same_object_as_charter_authority(self) -> None:
        import specify_cli.dossier.manifest as legacy_module
        from charter.activation.manifest_loader import (
            ManifestSchemaError as CharterManifestSchemaError,
        )

        assert legacy_module.ManifestSchemaError is CharterManifestSchemaError

    def test_malformed_manifest_error_is_the_same_object_as_charter_authority(self) -> None:
        import specify_cli.dossier.manifest as legacy_module
        from charter.offering.missions.repository import (
            MalformedManifestError as CharterMalformedManifestError,
        )

        assert legacy_module.MalformedManifestError is CharterMalformedManifestError

    def test_load_manifest_function_is_the_same_object_as_charter_authority(self) -> None:
        import specify_cli.dossier.manifest as legacy_module
        from charter.activation.manifest_loader import load_manifest as charter_load_manifest

        assert legacy_module.load_manifest is charter_load_manifest

    def test_manifest_registry_still_resolves_from_old_path(self) -> None:
        """`ManifestRegistry` itself never moved (D3) -- still importable
        from the old path, still exposing `load_manifest` as a callable."""
        from specify_cli.dossier.manifest import ManifestRegistry as LegacyManifestRegistry

        assert LegacyManifestRegistry is ManifestRegistry
        assert callable(LegacyManifestRegistry.load_manifest)

    def test_manifest_registry_load_manifest_delegate_returns_same_object_as_authority(
        self,
    ) -> None:
        """Delegate parity (contract's 4th bullet): `ManifestRegistry.load_manifest(...)`
        returns the SAME object the charter authority itself returns for
        identical inputs -- not a re-wrapped/copied value. The second call
        hits the (shared) cache, so identity here also exercises the
        cache-delegate path below.
        """
        from charter.activation.manifest_loader import load_manifest as charter_load_manifest

        ManifestRegistry.clear_cache()
        via_registry = ManifestRegistry.load_manifest("software-dev")
        via_authority = charter_load_manifest("software-dev")

        assert via_registry is not None
        assert via_registry is via_authority


class TestManifestRegistryCacheDelegatesToCharterAuthority:
    """NFR-002: `ManifestRegistry._cache` is the SAME dict object as
    `charter.activation.manifest_loader._cache` (an alias, not a copy) --
    the cache-introspection tests in `TestManifestRegistryOrgTier` below
    (cache-key shape, cross-root non-shadowing, declaration order) exercise
    this same shared object through the delegate and must keep passing
    unchanged; these two tests pin the aliasing itself.
    """

    def setup_method(self) -> None:
        ManifestRegistry.clear_cache()

    def teardown_method(self) -> None:
        ManifestRegistry.clear_cache()

    def test_manifest_registry_cache_is_the_same_object_as_charter_authority_cache(
        self,
    ) -> None:
        from charter.activation.manifest_loader import _cache as charter_cache

        assert ManifestRegistry._cache is charter_cache

    def test_manifest_registry_clear_cache_clears_charter_authority_cache(self) -> None:
        from charter.activation.manifest_loader import _cache as charter_cache

        ManifestRegistry.load_manifest("software-dev")
        assert len(charter_cache) > 0
        assert len(ManifestRegistry._cache) > 0

        ManifestRegistry.clear_cache()

        assert len(charter_cache) == 0
        assert len(ManifestRegistry._cache) == 0


# ---------------------------------------------------------------------------
# T027 (WP05, FR-008 + cache-key fix): `ManifestRegistry.load_manifest`
# org-tier override, and the `(mission_type, org_roots)` cache-key regression
# that closes the process-global-cache-shadows-across-projects defect.
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Write ``<repo_root>/.kittify/config.yaml`` with a ``doctrine.org.packs``
    registry only -- no mission-type-activation block, since
    ``ManifestRegistry.load_manifest`` reads org packs directly via
    ``resolve_org_roots``/``resolve_org_expected_artifacts``, not through the
    `existing_mission_types()` activation gate `_resolve_expected_artifacts_slot`
    (charter side) goes through.
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if packs:
        lines += ["doctrine:", "  org:", "    packs:"]
        for name, local_path in packs:
            lines.append(f"      - name: {name}")
            lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_manifest(org_root: Path, mission_type: str, data: dict) -> None:
    """Write ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``
    (raw-root shape, C-4 -- see ``test_org_expected_artifacts.py``'s module
    docstring).
    """
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (target_dir / "expected-artifacts.yaml").open("w") as fh:
        yaml.dump(data, fh)


class TestManifestRegistryOrgTier:
    """T027: org-tier override through `ManifestRegistry.load_manifest`, plus
    the SC-005 byte-identical-no-override proof and the cache-key regression
    this WP's fix exists to close.
    """

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        ManifestRegistry.clear_cache()

    def test_org_override_delta_through_load_manifest(self, tmp_path: Path) -> None:
        """Mirrors T026's shape but through `ManifestRegistry.load_manifest`
        with a `repo_root` argument: a delta in `required_always`, not
        merely "no exception."
        """
        before = ManifestRegistry.load_manifest("software-dev")
        assert before is not None
        before_count = len(before.required_always)

        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(
            org_root,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "org-1",
                "required_always": [
                    {
                        "artifact_key": "policy.org-required",
                        "artifact_class": "policy",
                        "path_pattern": "org-policy.md",
                        "blocking": True,
                    }
                ],
            },
        )
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        after = ManifestRegistry.load_manifest("software-dev", repo_root=project_root)

        assert after is not None
        assert len(after.required_always) == before_count + 1
        assert after.manifest_version == "org-1"
        assert any(spec.artifact_key == "policy.org-required" for spec in after.required_always)

    def test_no_repo_root_is_byte_identical_to_pre_wp_behavior(self, tmp_path: Path) -> None:
        """SC-005 Given #2: `load_manifest(mission_type)` with no `repo_root`
        (and with `repo_root=None` explicitly) produces output identical to
        pre-this-WP behavior -- proving the new optional parameter did not
        silently change the default call shape that
        `specify_cli.sync.namespace.resolve_manifest_version` depends on.
        """
        no_arg_result = ManifestRegistry.load_manifest("software-dev")
        ManifestRegistry.clear_cache()
        explicit_none_result = ManifestRegistry.load_manifest("software-dev", repo_root=None)

        assert no_arg_result is not None
        assert explicit_none_result is not None
        assert no_arg_result.model_dump() == explicit_none_result.model_dump()

    def test_cache_key_does_not_shadow_across_different_repo_roots(self, tmp_path: Path) -> None:
        """Cache-key regression (T023's fix): two different `repo_root`s
        resolving the SAME mission_type in the same process must not
        silently share a cached result -- this is exactly the defect this
        WP's cache-key fix exists to close. The cache is deliberately NOT
        cleared between the two calls below, since proving
        no-shadowing-without-clearing is the point.
        """
        project_a = tmp_path / "project-a"
        project_a.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(
            org_root,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "project-a-org",
            },
        )
        _write_org_pack_config(project_a, packs=[("acme", org_root)])

        project_b = tmp_path / "project-b"
        project_b.mkdir()
        # No org pack configured for project_b -- built-in tree only.

        result_a = ManifestRegistry.load_manifest("software-dev", repo_root=project_a)
        result_b = ManifestRegistry.load_manifest("software-dev", repo_root=project_b)

        assert result_a is not None
        assert result_b is not None
        assert result_a.manifest_version == "project-a-org"
        # The defect this fix closes: without the cache-key fix, project_b's
        # call would silently return project_a's cached (org-overridden)
        # result instead of resolving its own (built-in-only) manifest.
        assert result_b.manifest_version != "project-a-org"
        assert result_b.manifest_version == "1"

    def test_cache_key_preserves_declaration_order_for_same_root_set(self, tmp_path: Path) -> None:
        """Same SET of org roots, declared in different order across two
        `repo_root`s, must not collide on one cache key. Per NFR-003 /
        C-4 ("last-EXISTING-match wins"), reversing declaration order
        flips which org root's manifest wins -- so a cache key built from
        a *sorted* tuple of root strings (order-blind) would map both
        projects to the same key, and the second project would silently
        receive the first project's cached, order-wrong manifest. This is
        distinct from `test_cache_key_does_not_shadow_across_different_repo_roots`,
        which only covers *different* root sets.
        """
        org_x = tmp_path / "org-x"
        org_y = tmp_path / "org-y"
        _write_org_manifest(
            org_x,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "x-wins",
            },
        )
        _write_org_manifest(
            org_y,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "y-wins",
            },
        )

        project_xy = tmp_path / "project-xy"
        project_xy.mkdir()
        _write_org_pack_config(project_xy, packs=[("x", org_x), ("y", org_y)])

        project_yx = tmp_path / "project-yx"
        project_yx.mkdir()
        _write_org_pack_config(project_yx, packs=[("y", org_y), ("x", org_x)])

        # Cache deliberately not cleared between calls -- proving the two
        # differently-ordered-but-same-set projects don't collide is the
        # point, same as the different-root-sets regression test above.
        result_xy = ManifestRegistry.load_manifest("software-dev", repo_root=project_xy)
        result_yx = ManifestRegistry.load_manifest("software-dev", repo_root=project_yx)

        assert result_xy is not None
        assert result_yx is not None
        # project_xy declared [x, y] -> last-match-wins is y.
        assert result_xy.manifest_version == "y-wins"
        # project_yx declared [y, x] -> last-match-wins is x.
        assert result_yx.manifest_version == "x-wins"

    def test_org_file_failing_schema_validation_raises_manifest_schema_error(self, tmp_path: Path) -> None:
        """paula rank-2: a parseable org YAML mapping that fails
        `ExpectedArtifactManifest` schema validation (e.g. missing the
        required `mission_type` field) must fail as loudly as a
        schema-invalid BUILT-IN manifest does -- raising `ManifestSchemaError`
        -- not be silently swallowed to `None`. An org author authored this
        file and expects it to take effect; before this fix the org-tier
        branch caught `except Exception` around the whole schema-validation
        attempt and degraded ANY failure (including a genuine schema typo)
        to `None`, hiding a real misconfiguration behind the same "not
        found" signal as a mission type with no org override at all.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(
            org_root,
            "software-dev",
            # Missing required `mission_type` field -> pydantic ValidationError.
            {"schema_version": "1.0", "manifest_version": "broken"},
        )
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        with pytest.raises(ManifestSchemaError) as exc_info:
            ManifestRegistry.load_manifest("software-dev", repo_root=project_root)

        exc = exc_info.value
        assert exc.mission_type == "software-dev"
        # No single org file path is available (resolve_org_expected_artifacts
        # doesn't report which root matched) -- the origin label instead
        # names the org tier + mission type + the roots that were checked.
        assert "org-tier" in exc.origin
        assert str(org_root) in exc.origin
        # str() is operator-actionable: names the mission type, the origin
        # label, AND the underlying pydantic detail (the missing field).
        assert "software-dev" in str(exc)
        assert "mission_type" in str(exc)
        assert isinstance(exc.__cause__, ValidationError)

        # Nothing is cached on a raise -- a subsequent call re-attempts
        # resolution rather than silently returning a stale None forever.
        org_roots = (str(org_root),)
        cache_key = ("software-dev", org_roots)
        assert cache_key not in ManifestRegistry._cache

    def test_cache_key_shape_is_tuple_of_mission_type_and_org_roots(self) -> None:
        """Every cached key is a `(mission_type, tuple[str, ...])` 2-tuple —
        durable proof the cache-key fix's shape (not just its behavior) is
        what's actually stored, so a future refactor that silently reverts
        to a bare `mission_type` key would fail this test even before any
        cross-project shadowing test caught it.
        """
        ManifestRegistry.load_manifest("software-dev")
        # Pins the whole cache -- exactly one entry, keyed by the
        # `(mission_type, org_roots)` 2-tuple shape. `==` against a `list`
        # of one `tuple` literal fails on a bare `"software-dev"` key (the
        # regression this test guards against), a differently-shaped key,
        # an extra entry, or a non-tuple `org_roots` part (e.g. a `list`)
        # just as surely as the old count-plus-isinstance-poke sequence did.
        assert list(ManifestRegistry._cache.keys()) == [("software-dev", ())]


class TestSchemaHardeningAndLoudFailure:
    """WP01 (IC-01): FR-009 schema hardening + FR-016 loud-failure propagation.

    A typo'd `expected-artifacts.yaml` key must fail loudly, both at direct
    Pydantic construction (`ExpectedArtifactSpec`/`ExpectedArtifactManifest`,
    FR-009) and through the one real production loading path,
    `ManifestRegistry.load_manifest()` (FR-016). See
    kitty-specs/expected-artifacts-manifest-repair-01KZY498/tracer-design-decisions.md
    Decision 3 for the full blast-radius rationale.
    """

    _TYPO_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "expected_artifacts_typo.yaml"

    def test_expected_artifact_spec_rejects_extra_keyword(self):
        """A typo'd keyword argument to ExpectedArtifactSpec raises ValidationError."""
        with pytest.raises(ValidationError):
            ExpectedArtifactSpec(
                artifact_key="x",
                artifact_class="input",
                path_pattern="x.md",
                blocking=True,
                blockign=True,  # type: ignore[call-arg]  # deliberate typo
            )

    def test_expected_artifact_manifest_rejects_extra_keyword(self):
        """A typo'd top-level keyword argument to ExpectedArtifactManifest raises ValidationError."""
        with pytest.raises(ValidationError):
            ExpectedArtifactManifest(
                mission_type="x",
                required_alwyas=[],  # type: ignore[call-arg]  # deliberate typo
            )

    def test_all_shipped_manifests_load_after_hardening(self):
        """The three manifests WP01 owns still load cleanly after `extra="forbid"`.

        `plan`'s loadability is NOT asserted here: the `plan` manifest is
        authored in WP03, a separate WP that WP01 has no dependency on, so a
        `plan` assertion in this test would be structurally unable to pass at
        WP01's own completion. `plan`'s loadability is covered separately by
        WP03's `TestPlanManifest.test_plan_manifest_loads_and_matches_state_machine`,
        which is the sole place `plan`'s loadability is asserted.
        """
        for mission_type in ("research", "documentation", "software-dev"):
            manifest = ManifestRegistry.load_manifest(mission_type)
            assert manifest is not None, f"{mission_type} manifest failed to load"

    def test_load_manifest_raises_on_schema_violating_key(self, monkeypatch: pytest.MonkeyPatch):
        """`ManifestRegistry.load_manifest()` raises `ManifestSchemaError` on a
        typo'd/extra key -- a domain type, NOT the raw `pydantic.ValidationError`
        (adversarial-review MAJOR fix): catching the raw pydantic type at a
        consumer boundary is a proxy for "the manifest schema is broken" that
        misfires on any unrelated `ValidationError` raised later in the same
        call stack (see
        `tests/sync/test_dossier_pipeline.py::TestSyncFeatureDossier::test_artifactref_validation_error_is_not_misattributed_to_manifest_schema`
        for the concrete M1 misattribution this fixes).

        The fixture (`expected_artifacts_typo.yaml`) is syntactically valid
        YAML — this exercises the `extra="forbid"` schema-validation path, NOT
        a YAML-syntax failure (bad indentation, unclosed structures, etc.);
        that gap is tracked separately in
        https://github.com/Priivacy-ai/spec-kitty/issues/3412. Routes the
        typo'd fixture through the same
        `_doctrine_repository().get_expected_artifacts()` seam the real loader
        uses -- WP01 (#3770) relocated that seam from
        `specify_cli.dossier.manifest` into
        `charter.activation.manifest_loader` alongside the load+cache logic
        it belongs to, so the monkeypatch below targets the new module -- by
        monkeypatching `_doctrine_repository` to return a fake repository
        whose `get_expected_artifacts()` serves the fixture's parsed YAML as
        a real `ConfigResult`.
        """
        import charter.activation.manifest_loader as manifest_loader_module
        from charter.offering.missions.repository import ConfigResult

        content = self._TYPO_FIXTURE_PATH.read_text(encoding="utf-8")
        import ruamel.yaml

        yaml = ruamel.yaml.YAML(typ="safe")
        parsed = yaml.load(content)

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
                return ConfigResult(content=content, origin="test-fixture", parsed=parsed)

        monkeypatch.setattr(manifest_loader_module, "_doctrine_repository", lambda: _FakeRepository())

        with pytest.raises(ManifestSchemaError) as exc_info:
            ManifestRegistry.load_manifest("typo-fixture")

        assert exc_info.value.mission_type == "typo-fixture"
        assert exc_info.value.origin == "test-fixture"
        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_load_manifest_validation_error_names_the_manifest_file(self, monkeypatch: pytest.MonkeyPatch):
        """#3542-A: the raised `ManifestSchemaError` must name *which*
        expected-artifacts.yaml was schema-invalid, not just the offending
        key.

        The underlying `pydantic.ValidationError` already names the bad key
        ("Extra inputs are not permitted"), but gives an org author
        debugging a typo no way to find the file on its own. Uses the same
        fake-repository seam as `test_load_manifest_raises_on_schema_violating_key`
        above, but with a distinctive ``origin`` label to prove that label is
        readable BOTH via the typed ``.origin`` field AND via plain
        ``str(exc)`` -- so any consumer that renders `str(exc)` (e.g.
        `cli/commands/reconcile.py`'s generic `except Exception as exc: ...
        f"...: {exc}"`) shows the file without needing to know to read a PEP
        678 exception note.
        """
        import charter.activation.manifest_loader as manifest_loader_module
        from charter.offering.missions.repository import ConfigResult

        content = self._TYPO_FIXTURE_PATH.read_text(encoding="utf-8")
        import ruamel.yaml

        yaml = ruamel.yaml.YAML(typ="safe")
        parsed = yaml.load(content)
        distinctive_origin = "doctrine/typo-fixture/expected-artifacts.yaml"

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
                return ConfigResult(content=content, origin=distinctive_origin, parsed=parsed)

        monkeypatch.setattr(manifest_loader_module, "_doctrine_repository", lambda: _FakeRepository())

        with pytest.raises(ManifestSchemaError) as exc_info:
            ManifestRegistry.load_manifest("typo-fixture")

        assert exc_info.value.origin == distinctive_origin
        # str() -- not just an exception note only some callers know to
        # read -- names both the origin file and the underlying key.
        formatted = str(exc_info.value)
        assert distinctive_origin in formatted, (
            "ManifestSchemaError's str() must name the offending manifest file so an org author can find and fix the typo; got: " + formatted
        )
        assert "required_alwyas" in formatted


class TestManifestReconciliation:
    """WP02 (IC-02): reconcile manifest `required_by_step` content against
    `runtime_bridge_cores.py`'s actual guard-table behavior (FR-001-FR-008).

    Reconciliation direction is manifest-to-match-guard, never the reverse
    (`tracer-approach.md`) -- these tests pin the CORRECTED manifest content,
    not the runtime guard behavior, which is untouched by this WP (C-001). See
    kitty-specs/expected-artifacts-manifest-repair-01KZY498/tasks/WP02-reconcile-manifests.md.
    """

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        ManifestRegistry.clear_cache()

    def test_research_manifest_gathering_requires_source_register(self):
        """FR-001/AS1: research `gathering` step requires source-register.csv,
        matching `_evaluate_gathering_guard`'s filesystem check."""
        manifest = ManifestRegistry.load_manifest("research")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "gathering")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in specs] == [
            ("evidence.source-register", ArtifactClassEnum.EVIDENCE, "source-register.csv", True),
        ]

    def test_documentation_manifest_audit_design_reconciled(self):
        """FR-002/FR-003/AS2: documentation `audit` requires only
        gap-analysis.md (not plan.md/tasks.md); `design` requires only
        plan.md (not tasks.md), matching `_evaluate_documentation_guards`."""
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None

        audit_specs = ManifestRegistry.get_required_artifacts(manifest, "audit")
        # Pins the whole collection -- exactly gap-analysis.md; a stray
        # plan.md or tasks.md entry (the reconciled-away requirements) fails
        # this equality even though it wouldn't have failed a bare `any(...)`.
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in audit_specs] == [
            ("evidence.gap-analysis", ArtifactClassEnum.EVIDENCE, "gap-analysis.md", True),
        ]

        design_specs = ManifestRegistry.get_required_artifacts(manifest, "design")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in design_specs] == [
            ("workflow.plan.documentation", ArtifactClassEnum.WORKFLOW, "plan.md", True),
        ]

    def test_documentation_manifest_validate_publish_reconciled(self):
        """FR-004/FR-005/AS3: documentation `validate` requires
        audit-report.md; `publish` requires release.md, matching
        `_evaluate_documentation_guards`."""
        manifest = ManifestRegistry.load_manifest("documentation")
        assert manifest is not None

        validate_specs = ManifestRegistry.get_required_artifacts(manifest, "validate")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in validate_specs] == [
            ("evidence.audit-report", ArtifactClassEnum.EVIDENCE, "audit-report.md", True),
        ]

        publish_specs = ManifestRegistry.get_required_artifacts(manifest, "publish")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in publish_specs] == [
            ("output.release.main", ArtifactClassEnum.OUTPUT, "release.md", True),
        ]

    def test_software_dev_manifest_plan_step_has_plan_only(self):
        """FR-006/AS4: software-dev `plan` step requires only plan.md, not
        tasks.md -- `_evaluate_software_dev_guards`'s `plan` branch only
        checks the plan artifact; tasks.md is produced/checked by the
        separate CLI-native tasks_outline/tasks_packages/tasks_finalize
        steps."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "plan")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in specs] == [
            ("output.plan.main", ArtifactClassEnum.OUTPUT, "plan.md", True),
        ]

    def test_software_dev_manifest_tasks_outline_packages_finalize(self):
        """FR-007/AS5: the CLI-native tasks_outline/tasks_packages/
        tasks_finalize steps each carry a required artifact matching
        `_evaluate_cli_tasks_guard`'s dispatch. tasks_packages/tasks_finalize
        use the exact `tasks/WP*.md` glob the guard itself checks
        (`tasks_dir.glob("WP*.md")`, runtime_bridge_io.py:796) -- not the
        broader `tasks/*.md`."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None

        outline_specs = ManifestRegistry.get_required_artifacts(manifest, "tasks_outline")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in outline_specs] == [
            ("output.tasks.list", ArtifactClassEnum.OUTPUT, "tasks.md", True),
        ]

        packages_specs = ManifestRegistry.get_required_artifacts(manifest, "tasks_packages")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in packages_specs] == [
            ("output.tasks.per_wp", ArtifactClassEnum.OUTPUT, "tasks/WP*.md", True),
        ]

        finalize_specs = ManifestRegistry.get_required_artifacts(manifest, "tasks_finalize")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in finalize_specs] == [
            ("output.tasks.per_wp", ArtifactClassEnum.OUTPUT, "tasks/WP*.md", True),
        ]

    def test_software_dev_manifest_implement_has_no_filesystem_requirement(self):
        """FR-008/AS6: software-dev `implement` step has no required
        artifacts. `_evaluate_wp_iteration_guard` never checks for
        analysis-report.md on disk -- it only checks WP status
        (`wp_advance_ready`). The guard-side reading ("the guard is wrong")
        is explicitly rejected for this WP (`tracer-approach.md`, C-001):
        fixed here by removing the manifest entry, not by touching
        `runtime_bridge_cores.py`."""
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        specs = ManifestRegistry.get_required_artifacts(manifest, "implement")
        assert specs == []


class TestPlanManifest:
    """WP03 (IC-03): author `plan` mission type's `expected-artifacts.yaml`,
    keyed on `plan`'s own state machine and real artifacts (FR-010-FR-013).

    `plan` is authored against its own `mission.yaml` state machine and
    artifacts, NOT `software-dev`'s CLI vocabulary, even though that is the
    dispatch chain `plan`-type steps currently (and silently) fall through
    to -- see
    kitty-specs/expected-artifacts-manifest-repair-01KZY498/tracer-design-decisions.md
    Decision 1. This manifest is honest scaffolding, not a claim that any
    guard branch enforces it.
    """

    _PLAN_MANIFEST_PATH = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions" / "plan" / "expected-artifacts.yaml"

    def setup_method(self):
        """Clear cache before each test."""
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        ManifestRegistry.clear_cache()

    def test_plan_manifest_loads_and_matches_state_machine(self):
        """FR-010/AS1-AS4 of US2: `plan` manifest loads, matches
        `mission.yaml`'s state machine exactly (order-sensitive), and
        requires only `plan`'s own real artifacts -- `goals.md`,
        `research.md`, `plan.md` -- at the steps that gate on them via
        `artifact_exists(...)` in `mission.yaml`'s transitions."""
        manifest = ManifestRegistry.load_manifest("plan")
        assert manifest is not None
        assert manifest.mission_type == "plan"
        assert manifest.manifest_version == "1"

        # Order-sensitive: matches packs/built-in/missions/plan/mission.yaml's
        # `states` list (lines 9-26) exactly.
        assert manifest.get_step_ids() == [
            "goals",
            "research",
            "structure",
            "draft",
            "review",
            "done",
        ]

        goals_specs = ManifestRegistry.get_required_artifacts(manifest, "goals")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in goals_specs] == [
            ("output.goals.main", ArtifactClassEnum.OUTPUT, "goals.md", True),
        ]

        research_specs = ManifestRegistry.get_required_artifacts(manifest, "research")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in research_specs] == [
            ("evidence.research", ArtifactClassEnum.EVIDENCE, "research.md", True),
        ]

        draft_specs = ManifestRegistry.get_required_artifacts(manifest, "draft")
        assert [(s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in draft_specs] == [
            ("output.plan.main", ArtifactClassEnum.OUTPUT, "plan.md", True),
        ]

        # `structure`, `review`, and `done` have no filesystem-artifact
        # requirement expressible by this schema: `structure->draft` is an
        # unconditional transition in mission.yaml, and `review->done` gates
        # on `gate_passed("plan_approved")`, not artifact_exists(...).
        assert ManifestRegistry.get_required_artifacts(manifest, "structure") == []
        assert ManifestRegistry.get_required_artifacts(manifest, "review") == []
        assert ManifestRegistry.get_required_artifacts(manifest, "done") == []

    def test_plan_manifest_header_names_guard_gap_mechanism(self):
        """AS4 of US2 (tasks-phase adversarial review fix, round 4,
        TASKS-FRESH4-001): the header comment must name the SPECIFIC
        mechanism from `tracer-design-decisions.md` Decision 1 -- the
        hardcoded `mission_family="software-dev"` in `_check_cli_guards`
        plus the `review`-step lexical collision -- not a vaguer "no guard
        exists yet" framing. Mirrors WP04's T018 pattern
        (`test_override_mirror_files_carry_deprecation_header`): reads the
        raw file text, not the parsed model, since the header comment is
        not part of the parsed schema."""
        raw_text = self._PLAN_MANIFEST_PATH.read_text(encoding="utf-8")

        assert "mission_family" in raw_text
        assert "software-dev" in raw_text
        assert "_check_cli_guards" in raw_text
        # Names the specific `review`-step lexical collision, not merely
        # "no branch recognizes plan step ids".
        assert "review" in raw_text.lower()
        assert "collide" in raw_text.lower()

        # The vaguer, explicitly-rejected framing must be absent so a future
        # genericization of the header is caught, not silently passed.
        assert "no guard exists yet" not in raw_text.lower()


class TestOverrideMirrorDeprecation:
    """WP04 (IC-04): mark the two dead
    `.kittify/overrides/missions/{research,documentation}/expected-artifacts.yaml`
    mirror files as explicitly deprecated/inert via a header comment, rather
    than refreshing their content to parity with WP02/WP03's reconciled
    `packs/built-in/missions/` copies -- per
    kitty-specs/expected-artifacts-manifest-repair-01KZY498/tracer-design-decisions.md
    Decision 4 (mark-deprecated, don't refresh, don't delete; refreshing dead
    content to keep it "in sync" is the literal shape of parity-with-a-dead-quirk,
    charter DIRECTIVE_044's named anti-pattern). Verified first-hand:
    `MissionTemplateRepository._expected_artifacts_path()`
    (`src/charter/offering/missions/repository.py`) composes only
    `default_missions_root()` -> `charter.offering.pack_paths.built_in_missions_root()`
    (the `packs/built-in/missions` tree); `src/charter/offering/resolver.py` -- the
    module that DOES implement the `.kittify/overrides/missions/{mission}/...`
    tier -- only wires that tier for `templates/`, `command-templates/`, and
    `mission.yaml`, never for `expected-artifacts.yaml`. So no reader anywhere
    in this repository ever opens these two override files.

    The `software-dev` mirror entry was removed by a later operator
    decision: rather than leave the software-dev override permanently
    header-only/inert, the operator chose to delete
    `.kittify/overrides/missions/software-dev/expected-artifacts.yaml`
    outright as part of a full software-dev override resync. The
    research/documentation mirrors are untouched and keep the Decision 4
    mark-deprecated treatment.
    """

    _OVERRIDE_ROOT = Path(__file__).parent.parent.parent / ".kittify" / "overrides" / "missions"

    _MIRROR_FILES = {
        "research": _OVERRIDE_ROOT / "research" / "expected-artifacts.yaml",
        "documentation": _OVERRIDE_ROOT / "documentation" / "expected-artifacts.yaml",
    }

    # Full body-content fingerprints as they existed before WP04's
    # header-only edit -- exercised below to prove the body was NOT
    # refreshed to parity with the reconciled built-in copies, only the
    # header comment changed (Decision 4's "don't refresh" half). Each
    # dict is the COMPLETE parsed YAML document (every key, every leaf
    # value) for its mirror, not just a hand-picked structural subset --
    # so a maintainer can see exactly what is protected at a glance, and
    # any drift to any leaf (a path_pattern, a blocking flag, a list
    # member, ...) fails the equality check below.
    _EXPECTED_CONTENT = {
        "research": {
            "schema_version": "1.0",
            "mission_type": "research",
            "manifest_version": "1",
            "required_always": [],
            "required_by_step": {
                "scoping": [
                    {
                        "artifact_key": "input.spec.research",
                        "artifact_class": "input",
                        "path_pattern": "spec.md",
                        "blocking": True,
                    },
                ],
                "methodology": [
                    {
                        "artifact_key": "workflow.plan.methodology",
                        "artifact_class": "workflow",
                        "path_pattern": "plan.md",
                        "blocking": True,
                    },
                ],
                "gathering": [],
                "synthesis": [
                    {
                        "artifact_key": "output.findings.main",
                        "artifact_class": "output",
                        "path_pattern": "findings.md",
                        "blocking": True,
                    },
                ],
                "output": [
                    {
                        "artifact_key": "output.report.publication",
                        "artifact_class": "output",
                        "path_pattern": "report.md",
                        "blocking": True,
                    },
                ],
                "done": [],
            },
            "optional_always": [
                {
                    "artifact_key": "evidence.methodology.detailed",
                    "artifact_class": "evidence",
                    "path_pattern": "methodology.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.synthesis.notes",
                    "artifact_class": "evidence",
                    "path_pattern": "synthesis.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.literature-review",
                    "artifact_class": "evidence",
                    "path_pattern": "literature-review.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.gap-analysis",
                    "artifact_class": "evidence",
                    "path_pattern": "gap-analysis.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.research-log",
                    "artifact_class": "evidence",
                    "path_pattern": "research.md",
                    "blocking": False,
                },
            ],
        },
        "documentation": {
            "schema_version": "1.0",
            "mission_type": "documentation",
            "manifest_version": "1",
            "required_always": [],
            "required_by_step": {
                "discover": [
                    {
                        "artifact_key": "input.spec.documentation",
                        "artifact_class": "input",
                        "path_pattern": "spec.md",
                        "blocking": True,
                    },
                ],
                "audit": [
                    {
                        "artifact_key": "workflow.plan.documentation",
                        "artifact_class": "workflow",
                        "path_pattern": "plan.md",
                        "blocking": True,
                    },
                    {
                        "artifact_key": "workflow.tasks.documentation",
                        "artifact_class": "workflow",
                        "path_pattern": "tasks.md",
                        "blocking": True,
                    },
                    {
                        "artifact_key": "evidence.gap-analysis",
                        "artifact_class": "evidence",
                        "path_pattern": "gap-analysis.md",
                        "blocking": True,
                    },
                ],
                "design": [
                    {
                        "artifact_key": "workflow.plan.documentation",
                        "artifact_class": "workflow",
                        "path_pattern": "plan.md",
                        "blocking": True,
                    },
                    {
                        "artifact_key": "workflow.tasks.documentation",
                        "artifact_class": "workflow",
                        "path_pattern": "tasks.md",
                        "blocking": True,
                    },
                ],
                "generate": [
                    {
                        "artifact_key": "output.docs.generated",
                        "artifact_class": "output",
                        "path_pattern": "docs/**/*.md",
                        "blocking": False,
                    },
                ],
                "validate": [],
                "publish": [],
            },
            "optional_always": [
                {
                    "artifact_key": "evidence.research",
                    "artifact_class": "evidence",
                    "path_pattern": "research.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.data-model",
                    "artifact_class": "evidence",
                    "path_pattern": "data-model.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.quickstart",
                    "artifact_class": "evidence",
                    "path_pattern": "quickstart.md",
                    "blocking": False,
                },
                {
                    "artifact_key": "evidence.audit-report",
                    "artifact_class": "evidence",
                    "path_pattern": "audit-report.md",
                    "blocking": False,
                },
            ],
        },
    }

    def test_override_mirror_files_carry_deprecation_header(self):
        """T018: each mirror file's header names the SPECIFIC inert
        mechanism (`_expected_artifacts_path()` / "no override tier for this
        asset type"), not merely a generic "deprecated" string, and each
        file's body content is byte-for-byte unchanged at the leaf level --
        the full parsed YAML document (every key, every leaf value, not
        just structural properties like key order or list length) is
        compared against a committed expected value, so ANY drift below
        the header (a path_pattern, a blocking flag, a list member, ...)
        fails this test."""
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")

        for mission_type, path in self._MIRROR_FILES.items():
            assert path.is_file(), f"expected mirror file at {path}"
            raw_text = path.read_text(encoding="utf-8")
            lower_text = raw_text.lower()

            # Recognizable deprecated/inert marker.
            assert "deprecated" in lower_text or "inert" in lower_text, f"{path} header must state the file is deprecated/inert"
            # Specific-mechanism language, not a vague "deprecated" alone:
            # names the actual resolver method that never reads this file.
            assert "_expected_artifacts_path" in raw_text, (
                f"{path} header must name the specific resolver mechanism (_expected_artifacts_path()) that never consults this override tier"
            )
            # Points at the canonical, actually-consumed copy.
            assert "packs/built-in/missions" in raw_text, f"{path} header must point at the canonical, consumed copy under packs/built-in/missions/"

            # Body content unchanged: parse and compare the WHOLE document
            # against the committed expected value below -- every key and
            # every leaf value, not a hand-picked subset. Comments are not
            # part of the parsed YAML, so this is independent of the
            # header-comment assertions above -- it fails if T019 (or any
            # future "drift hygiene" refresh) touches ANY required_by_step/
            # optional_always leaf value (e.g. a path_pattern), not just
            # structural properties like key order or list length.
            parsed = yaml.load(raw_text)
            assert parsed == self._EXPECTED_CONTENT[mission_type], (
                f"{path} body content drifted from the committed fingerprint "
                "-- Decision 4 requires header-only edits to this dead mirror; "
                "if this is an intentional content change, it likely belongs "
                "in packs/built-in/missions/ instead (the canonical, consumed copy)"
            )
