"""Integration tests for research CSV schema detection migration (0.13.0).

Tests validate that the migration correctly detects schema mismatches in
research feature CSVs and provides informational messages without auto-fixing.
"""

from __future__ import annotations

import json

import pytest

from specify_cli.upgrade.migrations.m_0_13_0_research_csv_schema_check import (
    ResearchCSVSchemaCheckMigration,
)

pytestmark = pytest.mark.fast


@pytest.fixture
def mock_research_project(tmp_path):
    """Create a mock spec-kitty project with research features."""
    # Create kitty-specs structure
    kitty_specs = tmp_path / "kitty-specs"
    kitty_specs.mkdir()

    return tmp_path


@pytest.fixture
def research_feature_with_correct_schema(mock_research_project):
    """Create a research feature with correct CSV schemas."""
    feature_dir = mock_research_project / "kitty-specs" / "001-test-feature"
    feature_dir.mkdir()

    # Create meta.json
    meta = {"mission": "research"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    # Create research directory with correct schemas
    research_dir = feature_dir / "research"
    research_dir.mkdir()

    # Correct evidence-log.csv schema
    (research_dir / "evidence-log.csv").write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n2025-01-25T10:00:00,journal,Citation,Finding,high,Notes\n",
        encoding="utf-8",
    )

    # Correct source-register.csv schema
    (research_dir / "source-register.csv").write_text(
        "source_id,citation,url,accessed_date,relevance,status\nS001,Citation,https://example.com,2025-01-25,high,reviewed\n",
        encoding="utf-8",
    )

    return mock_research_project


@pytest.fixture
def research_feature_with_wrong_evidence_schema(mock_research_project):
    """Create a research feature with wrong evidence-log.csv schema."""
    feature_dir = mock_research_project / "kitty-specs" / "002-wrong-evidence"
    feature_dir.mkdir()

    # Create meta.json
    meta = {"mission": "research"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    # Create research directory with WRONG schema
    research_dir = feature_dir / "research"
    research_dir.mkdir()

    # WRONG evidence-log.csv schema (wrong column names and order)
    (research_dir / "evidence-log.csv").write_text(
        "evidence_id,component,finding,citation,confidence,timestamp,notes\nE001,Component,Finding,Citation,high,2025-01-25T10:00:00,Notes\n",
        encoding="utf-8",
    )

    return mock_research_project


@pytest.fixture
def research_feature_with_wrong_source_schema(mock_research_project):
    """Create a research feature with wrong source-register.csv schema."""
    feature_dir = mock_research_project / "kitty-specs" / "003-wrong-source"
    feature_dir.mkdir()

    # Create meta.json
    meta = {"mission": "research"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    # Create research directory with WRONG schema
    research_dir = feature_dir / "research"
    research_dir.mkdir()

    # WRONG source-register.csv schema
    (research_dir / "source-register.csv").write_text(
        "id,reference,link,date,priority\n1,Reference,http://example.com,2025-01-25,high\n",
        encoding="utf-8",
    )

    return mock_research_project


@pytest.fixture
def software_dev_feature(mock_research_project):
    """Create a software-dev feature (should be skipped by migration)."""
    feature_dir = mock_research_project / "kitty-specs" / "004-software-dev"
    feature_dir.mkdir()

    # Create meta.json with software-dev mission
    meta = {"mission": "software-dev"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    return mock_research_project


class TestDetection:
    """Tests for migration detection logic."""

    def test_detect_no_features(self, mock_research_project):
        """Test detection returns False when no features exist."""
        migration = ResearchCSVSchemaCheckMigration()
        assert migration.detect(mock_research_project) is False

    def test_detect_correct_schema(self, research_feature_with_correct_schema):
        """Test detection returns False when schemas are correct."""
        migration = ResearchCSVSchemaCheckMigration()
        assert migration.detect(research_feature_with_correct_schema) is False

    def test_detect_wrong_evidence_schema(self, research_feature_with_wrong_evidence_schema):
        """Test detection returns True when evidence-log.csv schema is wrong."""
        migration = ResearchCSVSchemaCheckMigration()
        assert migration.detect(research_feature_with_wrong_evidence_schema) is True

    def test_detect_wrong_source_schema(self, research_feature_with_wrong_source_schema):
        """Test detection returns True when source-register.csv schema is wrong."""
        migration = ResearchCSVSchemaCheckMigration()
        assert migration.detect(research_feature_with_wrong_source_schema) is True

    def test_detect_skips_software_dev(self, software_dev_feature):
        """Test detection skips software-dev features."""
        migration = ResearchCSVSchemaCheckMigration()
        assert migration.detect(software_dev_feature) is False


class TestMigrationApply:
    """Tests for migration application."""

    def test_apply_no_features(self, mock_research_project):
        """Test migration handles project with no features."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(mock_research_project, dry_run=False)

        assert result.success is True
        assert len(result.errors) == 0
        # Empty kitty-specs directory means all schemas are correct (no mismatches found)
        assert any("correct" in change.lower() for change in result.changes_made)

    def test_apply_correct_schemas(self, research_feature_with_correct_schema, capsys):
        """Test migration reports success when schemas are correct."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(research_feature_with_correct_schema, dry_run=False)

        assert result.success is True
        assert len(result.errors) == 0
        assert any("correct" in change.lower() for change in result.changes_made)

        # Should not print informational report
        captured = capsys.readouterr()
        assert "Schema mismatch" not in captured.out

    def test_apply_wrong_evidence_schema(self, research_feature_with_wrong_evidence_schema, capsys):
        """Test migration reports mismatch for wrong evidence-log.csv schema."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(research_feature_with_wrong_evidence_schema, dry_run=False)

        assert result.success is True  # Informational only
        assert len(result.errors) == 0
        assert any("mismatch" in change.lower() for change in result.changes_made)

        # Should print informational report
        captured = capsys.readouterr()
        assert "Research CSV Schema Check" in captured.out
        assert "evidence-log.csv" in captured.out
        assert "Expected:" in captured.out
        assert "Actual:" in captured.out
        assert "timestamp,source_type,citation,key_finding,confidence,notes" in captured.out

    def test_apply_wrong_source_schema(self, research_feature_with_wrong_source_schema, capsys):
        """Test migration reports mismatch for wrong source-register.csv schema."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(research_feature_with_wrong_source_schema, dry_run=False)

        assert result.success is True  # Informational only
        assert len(result.errors) == 0
        assert any("mismatch" in change.lower() for change in result.changes_made)

        # Should print informational report
        captured = capsys.readouterr()
        assert "source-register.csv" in captured.out
        assert "source_id,citation,url,accessed_date,relevance,status" in captured.out

    def test_apply_skips_software_dev(self, software_dev_feature):
        """Test migration skips software-dev features."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(software_dev_feature, dry_run=False)

        assert result.success is True
        # Should report no mismatches (skipped non-research feature)
        assert any("correct" in change.lower() for change in result.changes_made)

    def test_apply_dry_run(self, research_feature_with_wrong_evidence_schema, capsys):
        """Test dry run mode produces same output."""
        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(research_feature_with_wrong_evidence_schema, dry_run=True)

        assert result.success is True
        assert len(result.errors) == 0

        # Dry run should still report (informational only, no changes made)
        captured = capsys.readouterr()
        assert "schema mismatch" in captured.out.lower()

    def test_apply_provides_migration_tips(self, research_feature_with_wrong_evidence_schema, capsys):
        """Test migration provides actionable migration tips."""
        migration = ResearchCSVSchemaCheckMigration()
        migration.apply(research_feature_with_wrong_evidence_schema, dry_run=False)

        captured = capsys.readouterr()
        # Check for migration tips
        assert "To fix this schema mismatch" in captured.out
        assert "implement.md" in captured.out
        assert "LLM agents can help" in captured.out

    def test_apply_does_not_modify_files(self, research_feature_with_wrong_evidence_schema):
        """Test migration does NOT modify CSV files (informational only)."""
        csv_path = research_feature_with_wrong_evidence_schema / "kitty-specs" / "002-wrong-evidence" / "research" / "evidence-log.csv"
        original_content = csv_path.read_text()

        migration = ResearchCSVSchemaCheckMigration()
        migration.apply(research_feature_with_wrong_evidence_schema, dry_run=False)

        # File should be unchanged
        assert csv_path.read_text() == original_content

    def test_can_apply_always_returns_true(self, mock_research_project):
        """Test can_apply always returns True (informational migration)."""
        migration = ResearchCSVSchemaCheckMigration()
        can_apply, reason = migration.can_apply(mock_research_project)

        assert can_apply is True
        assert reason == ""


class TestMultipleFeatures:
    """Tests with multiple research features."""

    def test_mixed_correct_and_wrong_schemas(self, mock_research_project, capsys):
        """Test migration reports only wrong schemas when mix exists."""
        # Create one correct feature
        correct_feature = mock_research_project / "kitty-specs" / "001-correct"
        correct_feature.mkdir()
        (correct_feature / "meta.json").write_text(json.dumps({"mission": "research"}))
        research_dir = correct_feature / "research"
        research_dir.mkdir()
        (research_dir / "evidence-log.csv").write_text("timestamp,source_type,citation,key_finding,confidence,notes\n")

        # Create one wrong feature
        wrong_feature = mock_research_project / "kitty-specs" / "002-wrong"
        wrong_feature.mkdir()
        (wrong_feature / "meta.json").write_text(json.dumps({"mission": "research"}))
        research_dir = wrong_feature / "research"
        research_dir.mkdir()
        (research_dir / "evidence-log.csv").write_text("id,component,finding\n")

        migration = ResearchCSVSchemaCheckMigration()
        result = migration.apply(mock_research_project, dry_run=False)

        assert result.success is True
        captured = capsys.readouterr()

        # Should report only the wrong feature
        assert "002-wrong" in captured.out
        assert "001-correct" not in captured.out


class TestMalformedMetaSkipped:
    """#2477: the routed ``load_meta`` read keeps the skip-on-malformed contract."""

    @pytest.mark.parametrize(
        "raw",
        [b"{invalid json", b"[1, 2]", b"\xff\xfe{"],
        ids=["syntax-error", "non-object", "undecodable"],
    )
    def test_malformed_meta_is_skipped(self, mock_research_project, raw):
        feature_dir = mock_research_project / "kitty-specs" / "005-broken"
        feature_dir.mkdir()
        (feature_dir / "meta.json").write_bytes(raw)
        research_dir = feature_dir / "research"
        research_dir.mkdir()
        (research_dir / "evidence-log.csv").write_text("id,component,finding\n")

        migration = ResearchCSVSchemaCheckMigration()

        assert migration.detect(mock_research_project) is False
        result = migration.apply(mock_research_project, dry_run=False)
        assert result.success is True
        assert result.errors == []
