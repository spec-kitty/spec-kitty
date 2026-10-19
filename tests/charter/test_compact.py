"""Focused coverage for charter compact rendering edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.compact import (
    extract_section_anchors,
    render_compact_view,
)
from charter.activation.resolver import GovernanceResolutionError
from kernel.charter_pack_paths import project_pack_root


pytestmark = pytest.mark.fast


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


def test_render_compact_view_labels_project_pack_root_as_layer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = project_pack_root(tmp_path)
    monkeypatch.setattr(
        "charter.activation.compact.resolve_project_root",
        lambda _repo_root: pack_root,
    )

    compact = render_compact_view(tmp_path, section_anchors=())

    assert f"Project layer root: {pack_root}" in compact.text
    assert "Project root:" not in compact.text


def test_render_compact_view_omits_missing_project_layer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "charter.activation.compact.resolve_project_root",
        lambda _repo_root: None,
    )

    compact = render_compact_view(tmp_path, section_anchors=())

    assert "Project layer root:" not in compact.text


def test_render_compact_view_omits_languages_when_inference_cannot_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Characterization: an unreadable charter/interview drops the footnote, not the render."""
    from charter.activation import compact as compact_module
    from charter.activation._diagnostics import CharterEncodingDiagnostic
    from charter.activation._io import CharterEncodingError

    ambiguous = CharterEncodingError(CharterEncodingDiagnostic.AMBIGUOUS, "ambiguous encoding")
    for error in (OSError("unreadable"), ambiguous):

        def _raise(_repo_root: Path, *, _error: Exception = error) -> list[str]:
            raise _error

        monkeypatch.setattr(compact_module, "infer_repo_languages", _raise)
        compact = render_compact_view(tmp_path, directive_ids=["DIRECTIVE_001"])

        assert "DIRECTIVE_001" in compact.text
        assert "Languages:" not in compact.text


def test_render_compact_view_lists_compiled_languages(tmp_path: Path) -> None:
    """Characterization: a compiled ``catalog.languages`` renders the sorted footnote."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("catalog:\n  languages: [python, go]\n", encoding="utf-8")

    compact = render_compact_view(tmp_path)

    assert "  - Languages: go, python" in compact.text


def test_compact_view_surfaces_unknown_selection_diagnostic(tmp_path: Path) -> None:
    """#6407: an unknown selected id is named in the compact text; the org id is listed."""
    from charter.activation.resolver import UNKNOWN_SELECTION_DIAGNOSTIC
    from tests.charter.test_resolver import _identity_project

    repo = _identity_project(
        tmp_path,
        selected="[QA_003, NOPE_999]",
        activated_directives=["001-architectural-integrity-standard"],
    )

    compact = render_compact_view(repo)

    assert UNKNOWN_SELECTION_DIAGNOSTIC.format(kind="directive", token="NOPE_999") in compact.text
    assert "QA_003" in compact.text
    assert "QA_003_NO_FAKE_GREEN" not in compact.text
    assert "governance unresolved" not in compact.text


def test_compact_view_clean_selection_has_no_unknown_diagnostic(tmp_path: Path) -> None:
    from tests.charter.test_resolver import _identity_project

    repo = _identity_project(tmp_path, selected="[QA_003]", activated_directives=[])

    compact = render_compact_view(repo)

    assert "Unknown selected" not in compact.text
    assert "QA_003" in compact.text
