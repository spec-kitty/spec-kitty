"""CLI tests for the FR-018 Selections section in ``spec-kitty doctor doctrine``.

These tests cover the *functional* contract:

- the section appears (with its header) on the human output,
- empty kinds render as ``(none)``,
- declared project-charter selections surface with a ``source:`` annotation,
- the JSON output carries a structured ``selections`` block.

The byte-exact format is pinned separately by
``tests/cli/test_doctor_doctrine_selections_snapshot.py``.
"""

from __future__ import annotations

import contextlib
import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_governance_with_selections(repo_root: Path) -> None:
    """Write a minimal charter.yaml declaring one selected styleguide.

    consolidate-charter-bundle (#2773) retired the compiled ``governance.yaml``
    and folded selections under ``charter.yaml``'s ``governance.doctrine``
    section, which is what ``_read_project_selections`` now reads.
    """
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(
        textwrap.dedent(
            """
            governance:
              doctrine:
                selected_styleguides:
                  - my-project-styleguide
                selected_directives:
                  - PROJECT_DIRECTIVE_01
            """
        ).lstrip(),
        encoding="utf-8",
    )
    # charter.md is required so load_governance_config doesn't try to
    # auto-sync from a missing source.
    (charter_dir / "charter.md").write_text("# Project Charter\n", encoding="utf-8")


def _write_kittify_skeleton(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text("doctrine: {}\n", encoding="utf-8")


def test_doctor_doctrine_renders_selections_header(tmp_path: Path) -> None:
    """The Selections section header MUST appear in the human-readable output."""
    _write_kittify_skeleton(tmp_path)
    _write_governance_with_selections(tmp_path)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["doctrine"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert "Selections (active globally-selected artifacts)" in result.stdout


def test_doctor_doctrine_empty_kinds_render_as_none(tmp_path: Path) -> None:
    """Kinds with no selection MUST surface as ``(none)`` so the audit is complete."""
    _write_kittify_skeleton(tmp_path)
    _write_governance_with_selections(tmp_path)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["doctrine"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    # paradigms, tactics, toolguides etc were not selected — they appear
    # as ``<kind>: (none)``.
    assert "paradigms: (none)" in result.stdout
    assert "tactics: (none)" in result.stdout


def test_doctor_doctrine_lists_declared_project_selections(tmp_path: Path) -> None:
    """A project-charter-declared selection surfaces with its id."""
    _write_kittify_skeleton(tmp_path)
    _write_governance_with_selections(tmp_path)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["doctrine"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    # The id appears under styleguides; the source annotation MUST be one of
    # the canonical tokens.
    assert "my-project-styleguide" in result.stdout
    assert "PROJECT_DIRECTIVE_01" in result.stdout
    assert "source:" in result.stdout


def test_doctor_doctrine_json_includes_selections_block(tmp_path: Path) -> None:
    """``--json`` MUST carry the same data in a structured ``selections`` key."""
    _write_kittify_skeleton(tmp_path)
    _write_governance_with_selections(tmp_path)

    with contextlib.chdir(tmp_path):
        result = runner.invoke(doctor_app, ["doctrine", "--json"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "selections" in payload
    selections = payload["selections"]
    # Every canonical kind appears, even when empty.
    for kind in (
        "directives",
        "tactics",
        "paradigms",
        "styleguides",
        "toolguides",
        "procedures",
        "mission_step_contracts",
        "agent_profiles",
    ):
        assert kind in selections
    # Declared project styleguide is present with its id and a source field.
    sg_ids = {entry["id"] for entry in selections["styleguides"]}
    assert "my-project-styleguide" in sg_ids
    for entry in selections["styleguides"]:
        if entry["id"] == "my-project-styleguide":
            assert "source" in entry
