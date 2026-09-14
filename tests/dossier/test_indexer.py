"""Unit tests for artifact indexing and missing detection (WP03).

Tests cover:
- Recursive directory scanning
- Artifact classification (6 deterministic classes)
- Missing artifact detection
- Unreadable artifact handling (permission errors, encoding issues)
- MissionDossier building
- Step-aware completeness checking
- Error handling without silent failures
"""

import os
import pytest
import tempfile
from kernel.clock import now_utc
from pathlib import Path
from unittest.mock import MagicMock, patch

from specify_cli.dossier.indexer import Indexer
from specify_cli.dossier.manifest import (
    ManifestRegistry,
    ExpectedArtifactManifest,
    ExpectedArtifactSpec,
    ArtifactClassEnum,
)
from specify_cli.dossier.models import ArtifactRef, MissionDossier


pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestIndexerScanning:
    """Test Indexer directory scanning."""

    def test_scan_directory_yields_files(self, tmp_path):
        """Indexer._scan_directory yields all files (non-hidden)."""
        # Create test structure
        (tmp_path / "spec.md").write_text("# Specification")
        (tmp_path / "plan.md").write_text("# Plan")
        (tmp_path / "tasks").mkdir()
        (tmp_path / "tasks" / "WP01.md").write_text("# WP01")
        (tmp_path / "tasks" / "WP02.md").write_text("# WP02")

        indexer = Indexer(ManifestRegistry())
        files = list(indexer._scan_directory(tmp_path))

        # Should have exactly these 4 files (membership is the contract, not just count).
        file_names = {f.name for f in files}
        assert file_names == {"spec.md", "plan.md", "WP01.md", "WP02.md"}

    def test_scan_directory_skips_hidden_files(self, tmp_path):
        """Indexer._scan_directory skips hidden files (names starting with .)."""
        (tmp_path / "spec.md").write_text("# Specification")
        (tmp_path / ".hidden.md").write_text("hidden")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("git config")

        indexer = Indexer(ManifestRegistry())
        files = list(indexer._scan_directory(tmp_path))

        # Should only have spec.md
        assert {f.name for f in files} == {"spec.md"}

    def test_scan_directory_skips_kittify_directory(self, tmp_path):
        """Indexer._scan_directory skips .kittify directory."""
        (tmp_path / "spec.md").write_text("# Specification")
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text("config")

        indexer = Indexer(ManifestRegistry())
        files = list(indexer._scan_directory(tmp_path))

        assert {f.name for f in files} == {"spec.md"}

    def test_scan_directory_recursive(self, tmp_path):
        """Indexer._scan_directory recursively traverses subdirectories."""
        (tmp_path / "level1.md").write_text("level 1")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "level2.md").write_text("level 2")
        (tmp_path / "subdir" / "deeper").mkdir()
        (tmp_path / "subdir" / "deeper" / "level3.md").write_text("level 3")

        indexer = Indexer(ManifestRegistry())
        files = list(indexer._scan_directory(tmp_path))

        names = {f.name for f in files}
        assert names == {"level1.md", "level2.md", "level3.md"}


class TestArtifactClassification:
    """Test deterministic artifact classification."""

    def test_classify_spec_as_input(self, tmp_path):
        """Classify spec.md as input."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Specification")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(spec_file, None)
        assert artifact_class == "input"

    def test_classify_plan_as_workflow(self, tmp_path):
        """Classify plan.md as workflow."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Plan")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(plan_file, None)
        assert artifact_class == "workflow"

    def test_classify_tasks_as_workflow(self, tmp_path):
        """Classify tasks.md as workflow."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("# Tasks")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(tasks_file, None)
        assert artifact_class == "workflow"

    def test_classify_wp_file_as_workflow(self, tmp_path):
        """Classify WP*.md files as workflow."""
        wp_file = tmp_path / "WP01.md"
        wp_file.write_text("# Work Package 1")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(wp_file, None)
        assert artifact_class == "workflow"

    def test_classify_research_as_evidence(self, tmp_path):
        """Classify research.md as evidence."""
        research_file = tmp_path / "research.md"
        research_file.write_text("# Research")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(research_file, None)
        assert artifact_class == "evidence"

    def test_classify_gap_analysis_as_evidence(self, tmp_path):
        """Classify gap-analysis.md as evidence."""
        gap_file = tmp_path / "gap-analysis.md"
        gap_file.write_text("# Gap Analysis")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(gap_file, None)
        assert artifact_class == "evidence"

    def test_classify_analysis_report_as_evidence(self, tmp_path):
        """Classify analysis-report.md as evidence."""
        report_file = tmp_path / "analysis-report.md"
        report_file.write_text("# Analysis Report")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(report_file, None)
        assert artifact_class == "evidence"

    def test_classify_test_file_as_evidence(self, tmp_path):
        """Classify test_*.py files as evidence."""
        test_file = tmp_path / "test_something.py"
        test_file.write_text("# Test")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(test_file, None)
        assert artifact_class == "evidence"

    def test_classify_requirements_as_policy(self, tmp_path):
        """Classify requirements.md as policy."""
        req_file = tmp_path / "requirements.md"
        req_file.write_text("# Requirements")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(req_file, None)
        assert artifact_class == "policy"

    def test_classify_constraints_as_policy(self, tmp_path):
        """Classify constraints.md as policy."""
        constraint_file = tmp_path / "constraints.md"
        constraint_file.write_text("# Constraints")

        indexer = Indexer(ManifestRegistry())
        artifact_class = indexer._classify_artifact(constraint_file, None)
        assert artifact_class == "policy"

    def test_classify_deterministic(self, tmp_path):
        """Classification is deterministic (same file, always same class)."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Specification")

        indexer = Indexer(ManifestRegistry())
        class1 = indexer._classify_artifact(spec_file, None)
        class2 = indexer._classify_artifact(spec_file, None)
        class3 = indexer._classify_artifact(spec_file, None)

        assert class1 == class2 == class3 == "input"

    def test_classify_fails_explicitly_if_unrecognized(self, tmp_path):
        """Classification fails explicitly (raises ValueError) for unrecognized files."""
        unknown_file = tmp_path / "xyz_unknown_file.bin"
        unknown_file.write_text("unknown content")

        indexer = Indexer(ManifestRegistry())
        with pytest.raises(ValueError, match="Cannot classify artifact"):
            indexer._classify_artifact(unknown_file, None)


class TestMissingArtifactDetection:
    """Test missing artifact detection."""

    def test_detect_missing_required_artifact(self):
        """Missing required artifact is detected with reason_code='not_found'."""
        # Create mock manifest with required spec
        spec = ExpectedArtifactSpec(
            artifact_key="input.spec.main",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
            blocking=True,
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_always=[spec],
        )

        # Create dossier with no artifacts
        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[],
            manifest=manifest.model_dump(),
        )

        # Mock manifest registry
        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            missing = indexer._detect_missing_artifacts(dossier)

        assert [m.artifact_key for m in missing] == ["input.spec.main"]
        assert missing[0].error_reason == "not_found"
        assert missing[0].is_present is False
        assert missing[0].required_status == "required"

    def test_detect_multiple_missing_artifacts(self):
        """Multiple missing required artifacts are detected."""
        specs = [
            ExpectedArtifactSpec(
                artifact_key="input.spec.main",
                artifact_class=ArtifactClassEnum.INPUT,
                path_pattern="spec.md",
            ),
            ExpectedArtifactSpec(
                artifact_key="workflow.plan",
                artifact_class=ArtifactClassEnum.WORKFLOW,
                path_pattern="plan.md",
            ),
        ]
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_always=specs,
        )

        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[],
            manifest=manifest.model_dump(),
        )

        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            missing = indexer._detect_missing_artifacts(dossier)

        assert {m.artifact_key for m in missing} == {"input.spec.main", "workflow.plan"}

    def test_no_missing_when_all_required_present(self):
        """No missing artifacts when all required artifacts are present."""
        spec = ExpectedArtifactSpec(
            artifact_key="input.spec.main",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_always=[spec],
        )

        # Create artifact that matches spec
        artifact = ArtifactRef(
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            required_status="required",
            is_present=True,
        )

        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[artifact],
            manifest=manifest.model_dump(),
        )

        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            missing = indexer._detect_missing_artifacts(dossier)

        assert len(missing) == 0

    def test_optional_artifacts_not_flagged_as_missing(self):
        """Optional artifacts are not flagged as missing."""
        optional_spec = ExpectedArtifactSpec(
            artifact_key="evidence.gap.analysis",
            artifact_class=ArtifactClassEnum.EVIDENCE,
            path_pattern="gap-analysis.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            optional_always=[optional_spec],
        )

        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[],
            manifest=manifest.model_dump(),
        )

        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            missing = indexer._detect_missing_artifacts(dossier)

        assert len(missing) == 0

    def test_step_aware_missing_detection(self):
        """Missing artifacts for specific step are detected."""
        step_spec = ExpectedArtifactSpec(
            artifact_key="workflow.tasks",
            artifact_class=ArtifactClassEnum.WORKFLOW,
            path_pattern="tasks.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_by_step={"planning": [step_spec]},
        )

        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[],
            manifest=manifest.model_dump(),
        )

        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            # Check for planning step
            missing = indexer._detect_missing_artifacts(dossier, step_id="planning")

        assert [m.artifact_key for m in missing] == ["workflow.tasks"]


class TestUnreadableArtifactHandling:
    """Test graceful handling of unreadable artifacts."""

    def test_permission_denied_artifact(self, tmp_path):
        """Artifact with no read permission is recorded with error_reason='unreadable'."""
        protected_file = tmp_path / "protected.md"
        protected_file.write_text("protected content")
        # Remove read permission
        os.chmod(protected_file, 0o000)

        try:
            indexer = Indexer(ManifestRegistry())
            artifact = indexer._index_file(protected_file, tmp_path, "software-dev")

            assert artifact is not None
            assert artifact.is_present is False
            assert artifact.error_reason == "unreadable"
            assert artifact.content_hash_sha256 == ""
        finally:
            # Restore permission for cleanup
            os.chmod(protected_file, 0o644)

    def test_invalid_utf8_artifact(self, tmp_path):
        """Artifact with invalid UTF-8 is recorded with error_reason='invalid_utf8'."""
        invalid_file = tmp_path / "invalid.txt"
        # Write invalid UTF-8 sequence
        with open(invalid_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00")

        indexer = Indexer(ManifestRegistry())
        artifact = indexer._index_file(invalid_file, tmp_path, "software-dev")

        assert artifact is not None
        assert artifact.is_present is False
        assert artifact.error_reason == "invalid_utf8"

    def test_scan_continues_after_unreadable_artifact(self, tmp_path):
        """Scan continues after encountering unreadable artifact (no exception)."""
        readable_file = tmp_path / "readable.md"
        readable_file.write_text("readable content")

        protected_file = tmp_path / "protected.md"
        protected_file.write_text("protected content")
        os.chmod(protected_file, 0o000)

        try:
            indexer = Indexer(ManifestRegistry())
            files = list(indexer._scan_directory(tmp_path))
            indexed_artifacts = []
            for file_path in files:
                artifact = indexer._index_file(file_path, tmp_path, "software-dev")
                if artifact:
                    indexed_artifacts.append(artifact)

            # Should have exactly these 2 artifacts, one readable and one not.
            by_path = {a.relative_path: a for a in indexed_artifacts}
            assert set(by_path) == {"readable.md", "protected.md"}
            assert by_path["readable.md"].is_present is True
            assert by_path["protected.md"].is_present is False
            assert by_path["protected.md"].error_reason == "unreadable"
        finally:
            os.chmod(protected_file, 0o644)


class TestMissionDossierBuilder:
    """Test MissionDossier builder."""

    def test_index_feature_builds_complete_dossier(self, tmp_path):
        """index_feature builds complete MissionDossier with indexed artifacts."""
        (tmp_path / "spec.md").write_text("# Specification")
        (tmp_path / "plan.md").write_text("# Plan")
        (tmp_path / "tasks.md").write_text("# Tasks")

        indexer = Indexer(ManifestRegistry())
        dossier = indexer.index_feature(tmp_path, "software-dev")

        assert dossier.mission_type == "software-dev"
        assert dossier.mission_slug == tmp_path.name
        assert dossier.feature_dir == str(tmp_path)
        assert len(dossier.artifacts) >= 3

    def test_dossier_includes_all_indexed_artifacts(self, tmp_path):
        """Dossier includes all indexed artifacts (present + unreadable)."""
        (tmp_path / "spec.md").write_text("# Specification")

        protected_file = tmp_path / "protected.md"
        protected_file.write_text("protected")
        os.chmod(protected_file, 0o000)

        try:
            indexer = Indexer(ManifestRegistry())
            dossier = indexer.index_feature(tmp_path, "software-dev")

            # Should have both readable and unreadable
            assert len(dossier.artifacts) >= 2
            readable = [a for a in dossier.artifacts if a.is_present]
            unreadable = [a for a in dossier.artifacts if not a.is_present]
            assert len(readable) >= 1
            assert len(unreadable) >= 1
        finally:
            os.chmod(protected_file, 0o644)

    def test_dossier_includes_missing_artifacts(self):
        """Dossier includes missing artifacts (is_present=False)."""
        spec = ExpectedArtifactSpec(
            artifact_key="input.spec.main",
            artifact_class=ArtifactClassEnum.INPUT,
            path_pattern="spec.md",
        )
        manifest = ExpectedArtifactManifest(
            mission_type="software-dev",
            required_always=[spec],
        )

        indexer = Indexer(ManifestRegistry())
        with patch.object(
            indexer.manifest_registry, "load_manifest", return_value=manifest
        ):
            # Create empty temp directory
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                dossier = indexer.index_feature(tmp_path, "software-dev")

        # Should have missing artifact
        missing = [a for a in dossier.artifacts if not a.is_present]
        assert len(missing) > 0

    def test_dossier_timestamp_set(self, tmp_path):
        """Dossier timestamp is set correctly."""
        (tmp_path / "spec.md").write_text("# Specification")

        indexer = Indexer(ManifestRegistry())
        before = now_utc()
        dossier = indexer.index_feature(tmp_path, "software-dev")
        after = now_utc()

        assert dossier.dossier_updated_at is not None
        assert before <= dossier.dossier_updated_at <= after


class TestCompletenessStatus:
    """Test step-aware completeness checking."""

    def test_completeness_status_complete(self):
        """completeness_status='complete' when all required artifacts present."""
        artifact = ArtifactRef(
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            required_status="required",
            is_present=True,
        )
        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[artifact],
            manifest={"required": ["spec"]},  # Has manifest
        )
        assert dossier.completeness_status == "complete"

    def test_completeness_status_incomplete(self):
        """completeness_status='incomplete' when required artifact missing."""
        artifact = ArtifactRef(
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="",
            size_bytes=0,
            required_status="required",
            is_present=False,
            error_reason="not_found",
        )
        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[artifact],
            manifest={"required": ["spec"]},
        )
        assert dossier.completeness_status == "incomplete"

    def test_completeness_status_unknown_no_manifest(self):
        """completeness_status='unknown' when no manifest available."""
        artifact = ArtifactRef(
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            required_status="required",
            is_present=True,
        )
        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[artifact],
            manifest=None,  # No manifest
        )
        assert dossier.completeness_status == "unknown"

    def test_optional_artifacts_dont_affect_completeness(self):
        """Optional artifacts don't affect completeness status."""
        required = ArtifactRef(
            artifact_key="required",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            required_status="required",
            is_present=True,
        )
        optional = ArtifactRef(
            artifact_key="optional",
            artifact_class="evidence",
            relative_path="research.md",
            content_hash_sha256="",
            size_bytes=0,
            required_status="optional",
            is_present=False,
            error_reason="not_found",
        )
        dossier = MissionDossier(
            mission_type="software-dev",
            mission_run_id="run-001",
            mission_slug="test-feature",
            feature_dir="/nonexistent/test",
            artifacts=[required, optional],
            manifest={"required": ["spec"]},
        )
        # Optional missing should not affect completeness
        assert dossier.completeness_status == "complete"


class TestLargeScaleIndexing:
    """Test indexing with many artifacts."""

    def test_scan_30_plus_artifacts_without_errors(self, tmp_path):
        """Scan feature directory with 30+ files, no errors."""
        # Create 30+ test files
        for i in range(35):
            if i % 5 == 0:
                (tmp_path / f"spec_{i}.md").write_text(f"# Spec {i}")
            elif i % 5 == 1:
                (tmp_path / f"plan_{i}.md").write_text(f"# Plan {i}")
            elif i % 5 == 2:
                (tmp_path / f"WP{i:02d}.md").write_text(f"# WP {i}")
            elif i % 5 == 3:
                (tmp_path / f"research_{i}.md").write_text(f"# Research {i}")
            else:
                (tmp_path / f"test_{i}.py").write_text(f"# Test {i}")

        indexer = Indexer(ManifestRegistry())
        dossier = indexer.index_feature(tmp_path, "software-dev")

        # Should have indexed 35 artifacts without errors -- this test is
        # specifically about scale (30+ generated files), not particular
        # filenames, so the count itself is the contract.
        assert len(dossier.artifacts) == 35
        # All should be present (no errors)
        present = [a for a in dossier.artifacts if a.is_present]
        assert len(present) == 35


class TestUnparseableWPHandling:
    """#2883 items 3/4: invalid WP frontmatter is handled without aborting the
    scan, and only the churn-prone case (present-but-schema-invalid) fails
    closed; a stub/malformed doc with no runtime mapping stays present."""

    def test_list_frontmatter_wp_survives_scan(self, tmp_path):
        """Item 4: a YAML-list frontmatter no longer aborts the scan with a
        TypeError. No runtime mapping to churn, so it stays present via the
        stable raw-byte fallback."""
        (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        (tasks / "WP01.md").write_text("---\n- a\n- b\n---\nbody\n", encoding="utf-8")

        # Previously raised TypeError out of index_feature; must now survive.
        dossier = Indexer(ManifestRegistry()).index_feature(tmp_path, "software-dev")

        wp = next(a for a in dossier.artifacts if a.relative_path.endswith("WP01.md"))
        assert wp.is_present is True
        assert wp.content_hash_sha256  # stable raw-byte hash

    def test_schema_invalid_frontmatter_wp_fails_closed(self, tmp_path):
        """Item 3: a present-but-schema-invalid WP (valid mapping, bad wp id)
        fails closed rather than raw-byte hashing runtime-mutable frontmatter
        that a lane transition would churn into a false DIVERGENCE."""
        (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        (tasks / "WP01.md").write_text("---\nwork_package_id: NOT-A-WP\ntitle: x\ndependencies: []\n---\nbody\n", encoding="utf-8")

        dossier = Indexer(ManifestRegistry()).index_feature(tmp_path, "software-dev")

        wp = next(a for a in dossier.artifacts if a.relative_path.endswith("WP01.md"))
        assert wp.is_present is False  # fail-closed, no churning raw-byte hash
        assert wp.content_hash_sha256 == ""
        assert wp.error_reason and "invalid" in wp.error_reason


class TestIndexerOrgAwareManifest:
    """#3525 Fold C: ``ManifestRegistry.load_manifest`` already builds the
    org-pack override branch, but no production caller passed ``repo_root``
    -- so an org ``expected-artifacts.yaml`` override changed governance-gate
    behaviour but never reached the dossier completeness index. ``Indexer``
    now accepts an optional ``repo_root`` at construction and threads it
    through every ``load_manifest`` call site.
    """

    def setup_method(self):
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        ManifestRegistry.clear_cache()

    def _write_org_pack_config(self, repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
        config_dir = repo_root / ".kittify"
        config_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if packs:
            lines += ["doctrine:", "  org:", "    packs:"]
            for name, local_path in packs:
                lines.append(f"      - name: {name}")
                lines.append(f"        local_path: {local_path}")
        (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_org_manifest(self, org_root: Path, mission_type: str, data: dict) -> None:
        from ruamel.yaml import YAML

        target_dir = org_root / "missions" / mission_type
        target_dir.mkdir(parents=True, exist_ok=True)
        yaml = YAML()
        yaml.default_flow_style = False
        with (target_dir / "expected-artifacts.yaml").open("w") as fh:
            yaml.dump(data, fh)

    def test_org_override_changes_required_artifact_set(self, tmp_path: Path) -> None:
        """Red-first (#3525 Fold C): an org-pack ``expected-artifacts.yaml``
        override registered in ``.kittify/config.yaml`` must change what the
        dossier indexer reports as missing -- not just what the governance
        gate reports. Pre-fix, ``Indexer`` never passed ``repo_root`` to
        ``load_manifest``, so this org-required artifact never appeared as
        ``missing`` in the indexed dossier even though it was genuinely
        absent from disk.
        """
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        org_root = tmp_path / "org-pack"
        self._write_org_manifest(
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
        self._write_org_pack_config(repo_root, packs=[("acme", org_root)])

        (repo_root / "spec.md").write_text("# Spec\n", encoding="utf-8")

        dossier = Indexer(ManifestRegistry(), repo_root=repo_root).index_feature(
            repo_root, "software-dev"
        )

        assert dossier.manifest is not None
        assert dossier.manifest.get("manifest_version") == "org-1"
        ghost = next(
            (a for a in dossier.artifacts if a.artifact_key == "policy.org-required"),
            None,
        )
        assert ghost is not None, "org-required artifact must surface as a missing (ghost) artifact"
        assert ghost.is_present is False
        assert ghost.required_status == "required"

    def test_no_repo_root_stays_byte_identical(self, tmp_path: Path) -> None:
        """The no-org path (``repo_root`` omitted at construction) must
        produce a dossier identical to before this fold -- the built-in
        manifest only, no org lookup attempted."""
        (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")

        with_repo_root_none = Indexer(ManifestRegistry()).index_feature(tmp_path, "software-dev")
        ManifestRegistry.clear_cache()
        explicit_none = Indexer(ManifestRegistry(), repo_root=None).index_feature(tmp_path, "software-dev")

        assert with_repo_root_none.manifest == explicit_none.manifest
        assert [a.artifact_key for a in with_repo_root_none.artifacts] == [
            a.artifact_key for a in explicit_none.artifacts
        ]
