"""Focused coverage for charter compact rendering edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.compact import (
    CompactView,
    extract_section_anchors,
    render_compact_view,
)
from charter.activation.resolver import GovernanceResolutionError


pytestmark = pytest.mark.fast


def test_compact_view_token_estimate_has_minimum() -> None:
    view = CompactView(text="")

    assert view.token_estimate == 1


def test_extract_section_anchors_skips_empty_and_duplicates() -> None:
    text = "\n".join(
        [
            "# Overview",
            "## Overview",
            "# Details",
        ]
    )

    assert extract_section_anchors(text) == ["Overview", "Details"]


def test_render_compact_view_uses_explicit_section_anchors(tmp_path: Path) -> None:
    compact = render_compact_view(
        tmp_path,
        directive_ids=["DIRECTIVE_001"],
        tactic_ids=["TAC-001"],
        section_anchors=["Chosen Anchor"],
        charter_text="# Ignored Charter Anchor",
    )

    assert compact.directive_ids == ("DIRECTIVE_001",)
    assert compact.tactic_ids == ("TAC-001",)
    assert compact.section_anchors == ("Chosen Anchor",)
    assert "DIRECTIVE_001" in compact.text
    assert "TAC-001" in compact.text
    assert "Chosen Anchor" in compact.text


def test_render_compact_view_reads_charter_file_when_text_omitted(tmp_path: Path) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text("# From Disk\n", encoding="utf-8")

    compact = render_compact_view(tmp_path)

    assert compact.section_anchors == ("From Disk",)


def test_render_compact_view_handles_unreadable_charter_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    charter_path = charter_dir / "charter.md"
    charter_path.write_text("# From Disk\n", encoding="utf-8")

    def _raise_oserror(*_args, **_kwargs) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", _raise_oserror)

    compact = render_compact_view(tmp_path)

    assert compact.section_anchors == ()
    assert "(none)" in compact.text


def test_render_compact_view_reports_governance_resolution_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_resolution_error(_repo_root: Path):
        raise GovernanceResolutionError(["missing directive"])

    monkeypatch.setattr("charter.activation.compact.resolve_project_governance", _raise_resolution_error)

    compact = render_compact_view(tmp_path)

    assert "governance unresolved" in compact.text
    assert "missing directive" in compact.text


def test_render_compact_view_labels_doctrine_directory_as_layer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doctrine_root = tmp_path / ".kittify" / "doctrine"
    monkeypatch.setattr(
        "charter.activation.compact.resolve_project_root",
        lambda _repo_root: doctrine_root,
    )

    compact = render_compact_view(tmp_path, section_anchors=())

    assert f"Doctrine layer root: {doctrine_root}" in compact.text
    assert "Project root:" not in compact.text


def test_render_compact_view_omits_missing_doctrine_layer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "charter.activation.compact.resolve_project_root",
        lambda _repo_root: None,
    )

    compact = render_compact_view(tmp_path, section_anchors=())

    assert "Doctrine layer root:" not in compact.text
