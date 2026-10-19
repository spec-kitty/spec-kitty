"""#6443 -- ``charter synthesize --dry-run-evidence`` never renames the legacy directive.

``--dry-run-evidence`` prints the evidence summary and exits without synthesis, so it must
leave the legacy ``mission-type-scope-directive`` file where it is. The positive control runs
the shared rename helper for real on the same project and shows it does move the file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.api import rename_legacy_project_intent_directive
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_LEGACY = "001-mission-type-scope-directive.directive.yaml"
_RENAMED = "001-project-intent-directive.directive.yaml"


def _project(root: Path) -> Path:
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(
        "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
        "  mission_type: software_dev\nselected_paradigms: []\nselected_directives: []\navailable_tools: []\n",
        encoding="utf-8",
    )
    directive_dir = root / ".kittify" / "charter-packs" / "directive"
    directive_dir.mkdir(parents=True)
    (directive_dir / _LEGACY).write_text(
        'schema_version: "1.0"\nid: PROJECT_001\ntitle: Mission Type Scope Directive\nintent: Scope.\nenforcement: advisory\n',
        encoding="utf-8",
    )
    return directive_dir


def test_dry_run_evidence_leaves_the_legacy_directive_in_place(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    directive_dir = _project(tmp_path)
    charter_cwd_isolation(tmp_path)

    result = runner.invoke(app, ["synthesize", "--dry-run-evidence", "--skip-code-evidence", "--skip-corpus", "--json"])

    assert result.exit_code == 0, result.output
    assert (directive_dir / _LEGACY).is_file()
    assert not (directive_dir / _RENAMED).exists()

    renamed = rename_legacy_project_intent_directive(tmp_path)  # control: the helper really renames
    assert renamed.pending
    assert (directive_dir / _RENAMED).is_file()
    assert not (directive_dir / _LEGACY).exists()
