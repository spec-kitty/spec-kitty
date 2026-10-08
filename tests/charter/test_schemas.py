"""Tests for charter schemas module."""

import pytest
import tempfile
from pathlib import Path

from charter.activation.schemas import (
    BranchStrategyConfig,
    CommitConfig,
    Directive,
    DirectivesConfig,
    GovernanceCharterConfig,
    ExtractionMetadata,
    GovernanceConfig,
    PerformanceConfig,
    QualityConfig,
    SectionsParsed,
    CharterTestingConfig,
    emit_yaml,
)

pytestmark = pytest.mark.fast

class TestCharterTestingConfig:
    def test_default_values(self) -> None:
        config = CharterTestingConfig()
        assert config.min_coverage == 0
        assert config.tdd_required is False
        assert config.framework == ""
        assert config.type_checking == ""


class TestQualityConfig:
    def test_default_values(self) -> None:
        config = QualityConfig()
        assert config.linting == ""
        assert config.pr_approvals == 1
        assert config.pre_commit_hooks is False


class TestPerformanceConfig:
    def test_default_values(self) -> None:
        config = PerformanceConfig()
        assert config.cli_timeout_seconds == 2.0
        assert config.dashboard_max_wps == 100


class TestBranchStrategyConfig:
    def test_default_values(self) -> None:
        config = BranchStrategyConfig()
        assert config.main_branch == "main"
        assert config.dev_branch is None
        assert config.rules == []


class TestDoctrineSelectionConfig:
    def test_default_values(self) -> None:
        config = GovernanceCharterConfig()
        assert config.selected_paradigms == []
        assert config.selected_directives == []
        assert config.available_tools == []
        assert config.governance_references == []
        assert config.template_set is None


class TestGovernanceConfig:
    def test_default_values(self) -> None:
        config = GovernanceConfig()
        assert isinstance(config.testing, CharterTestingConfig)
        assert isinstance(config.quality, QualityConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.charter, GovernanceCharterConfig)
        assert config.enforcement == {}

    def test_custom_nested_values(self) -> None:
        config = GovernanceConfig(
            testing=CharterTestingConfig(min_coverage=90, tdd_required=True),
            quality=QualityConfig(linting="ruff"),
            charter=GovernanceCharterConfig(selected_paradigms=["test-first"]),
        )
        assert config.testing.min_coverage == 90
        assert config.quality.linting == "ruff"
        assert config.charter.selected_paradigms == ["test-first"]


class TestDirective:
    def test_required_fields(self) -> None:
        directive = Directive(id="D001", title="Test Coverage")
        assert directive.id == "D001"
        assert directive.title == "Test Coverage"
        assert directive.severity == "warn"


class TestDirectivesConfig:
    def test_default_values(self) -> None:
        config = DirectivesConfig()
        assert config.directives == []


class TestExtractionMetadata:
    def test_default_values(self) -> None:
        meta = ExtractionMetadata()
        assert meta.schema_version == "1.0.0"
        assert meta.extraction_mode == "deterministic"
        assert meta.source_path == ".kittify/charter/charter.md"
        assert isinstance(meta.sections_parsed, SectionsParsed)


class TestEmitYAML:
    def test_emit_yaml_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"
            config = CharterTestingConfig(min_coverage=90, tdd_required=True)
            emit_yaml(config, output_path)
            assert output_path.exists()

    def test_emit_yaml_includes_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"
            config = CharterTestingConfig(min_coverage=90)
            emit_yaml(config, output_path)
            content = output_path.read_text()
            assert "Auto-generated from charter.md" in content
            assert "do not edit directly" in content

    def test_emit_yaml_nested_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "governance.yaml"
            config = GovernanceConfig(
                testing=CharterTestingConfig(min_coverage=90),
                quality=QualityConfig(linting="ruff"),
                commits=CommitConfig(convention="conventional"),
            )
            emit_yaml(config, output_path)
            content = output_path.read_text()
            assert "testing:" in content
            assert "quality:" in content
            assert "min_coverage: 90" in content

    def test_emit_yaml_list_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "directives.yaml"
            config = DirectivesConfig(
                directives=[
                    Directive(id="D001", title="Coverage"),
                    Directive(id="D002", title="TDD"),
                ]
            )
            emit_yaml(config, output_path)
            content = output_path.read_text()
            assert "directives:" in content
            assert "D001" in content
            assert "D002" in content
