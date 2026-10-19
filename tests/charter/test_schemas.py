"""Tests for charter schemas module."""

import pytest
import tempfile
from pathlib import Path

from charter.activation.schemas import (
    CommitConfig,
    Directive,
    DirectivesConfig,
    GovernanceConfig,
    QualityConfig,
    CharterTestingConfig,
    emit_yaml,
)

pytestmark = pytest.mark.fast

class TestEmitYAML:
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
