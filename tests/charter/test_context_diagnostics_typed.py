"""#6460: governance diagnostics are typed ``{code, message}`` entries.

Pins the user-observable contract of mission ``typed-context-diagnostics``:

* ``charter context --json`` emits ``diagnostics`` as a list of objects with
  exactly the keys ``code`` and ``message`` (schema ``1.4.0``, unchanged);
* every ``code`` belongs to the closed set below;
* each resolver producer site carries its documented code (data-model.md), so
  consumers classify on ``code`` and never on the message wording.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from charter.activation.context import build_charter_context_json
from charter.activation.interview import default_interview
from charter.activation.resolver import (
    UNKNOWN_SELECTION_DIAGNOSTIC,
    GovernanceResolution,
    resolve_governance_for_profile,
    resolve_project_governance,
)
from tests.charter.test_resolver import _identity_project, _write_charter_files

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_CODES = frozenset(
    {
        "UNKNOWN_SELECTION_DROPPED",
        "CATALOG_DEFAULT_APPLIED",
        "FALLBACK_APPLIED",
        "SELECTION_MERGED",
        "UNRESOLVED_REFERENCE",
    }
)


def _entries(payload: dict[str, object]) -> list[dict[str, object]]:
    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, list)
    return cast("list[dict[str, object]]", diagnostics)


def _codes_by_message(resolution: GovernanceResolution) -> dict[str, str]:
    """Map each diagnostic's message to its code value (fails on plain strings)."""
    from charter.activation.api import GovernanceDiagnostic

    diagnostics: list[object] = list(resolution.diagnostics)
    assert diagnostics, "expected at least one diagnostic"
    assert all(isinstance(d, GovernanceDiagnostic) for d in diagnostics), diagnostics
    typed = cast("list[GovernanceDiagnostic]", diagnostics)
    return {d.message: d.code.value for d in typed}


def test_context_json_diagnostics_are_typed_objects(tmp_path: Path) -> None:
    """A bare project's context JSON lists ``{code, message}`` objects only."""
    _write_charter_files(tmp_path, governance="charter: {}\n")

    payload = build_charter_context_json(tmp_path, action="plan")

    assert payload["context_schema_version"] == "1.4.0"
    entries = _entries(payload)
    assert entries, "a bare project reports at least the catalog-default / fallback notes"
    for entry in entries:
        assert isinstance(entry, dict), entry
        assert set(entry) == {"code", "message"}, entry
        assert entry["code"] in _CODES, entry
        assert isinstance(entry["message"], str) and entry["message"], entry


def test_unknown_selected_directive_has_drop_code(tmp_path: Path) -> None:
    """A typo'd selection surfaces as one ``UNKNOWN_SELECTION_DROPPED`` entry naming the id."""
    repo = _identity_project(
        tmp_path,
        selected="[QA_003, NOPE_999]",
        activated_directives=["001-architectural-integrity-standard"],
    )

    payload = build_charter_context_json(repo, action="plan")

    dropped = [e for e in _entries(payload) if e.get("code") == "UNKNOWN_SELECTION_DROPPED"]
    assert len(dropped) == 1, _entries(payload)
    assert dropped[0]["message"] == UNKNOWN_SELECTION_DIAGNOSTIC.format(kind="directive", token="NOPE_999")
    assert "NOPE_999" in cast("str", dropped[0]["message"])


def test_bare_project_resolution_codes_catalog_default_and_fallback(tmp_path: Path) -> None:
    """Catalog defaults (paradigms, directives) and fallbacks (tools, template set) carry their codes."""
    _write_charter_files(tmp_path, governance="charter: {}\n")

    codes = _codes_by_message(resolve_project_governance(tmp_path))

    by_code: dict[str, list[str]] = {}
    for message, code in codes.items():
        by_code.setdefault(code, []).append(message)
    assert any("paradigm" in m for m in by_code.get("CATALOG_DEFAULT_APPLIED", [])), codes
    assert any("directive" in m for m in by_code.get("CATALOG_DEFAULT_APPLIED", [])), codes
    assert any("runtime tool registry fallback" in m for m in by_code.get("FALLBACK_APPLIED", [])), codes
    assert any("Template set not selected" in m for m in by_code.get("FALLBACK_APPLIED", [])), codes
    assert "UNKNOWN_SELECTION_DROPPED" not in by_code


def test_selection_beyond_base_codes_selection_merged(tmp_path: Path) -> None:
    """Charter selections, extra tools and project-local directives merged onto a base are ``SELECTION_MERGED``."""
    repo = _identity_project(tmp_path, selected="[QA_003]", activated_directives=["001-architectural-integrity-standard"])

    codes = _codes_by_message(resolve_project_governance(repo))

    merged = [m for m, c in codes.items() if c == "SELECTION_MERGED"]
    assert any("beyond the activation base" in m and "QA_003" in m for m in merged), codes


def test_project_local_and_tool_merges_code_selection_merged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool-union and project-local-directive notes are ``SELECTION_MERGED`` too."""
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_010"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )
    _write_charter_files(
        tmp_path,
        governance="charter:\n  available_tools: [ruff]\n",
        directives="directives:\n  - id: LOCAL_ONLY\n    title: Local rule\n",
    )

    codes = _codes_by_message(resolve_project_governance(tmp_path, tool_registry={"git"}))

    merged = [m for m, c in codes.items() if c == "SELECTION_MERGED"]
    assert any("beyond the runtime registry" in m and "ruff" in m for m in merged), codes
    assert any("project-local directive" in m and "LOCAL_ONLY" in m for m in merged), codes


def test_profile_path_unresolved_reference_code() -> None:
    """``resolve_governance_for_profile`` codes a dangling reference ``UNRESOLVED_REFERENCE``."""
    interview = default_interview(mission="software-dev", profile="minimal")
    profile = SimpleNamespace(profile_id="reviewer", directive_references=[SimpleNamespace(code="MISSING_DIRECTIVE")])
    charter_service = MagicMock()
    charter_service.agent_profiles.resolve_profile.return_value = profile
    graph_result = SimpleNamespace(
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        unresolved=[("directive", "MISSING_DIRECTIVE")],
    )

    with patch("charter.activation.resolver.resolve_references_transitively", return_value=graph_result):
        resolution = resolve_governance_for_profile("reviewer", None, charter_service, interview, graph=SimpleNamespace())

    codes = _codes_by_message(resolution)
    assert codes == {"Unresolved reference: directive/MISSING_DIRECTIVE": "UNRESOLVED_REFERENCE"}


def test_diagnostic_value_object_json_shape() -> None:
    """``GovernanceDiagnostic.to_json`` is exactly ``{code, message}`` with the plain code string."""
    from charter.activation.api import GovernanceDiagnostic, GovernanceDiagnosticCode

    assert {c.value for c in GovernanceDiagnosticCode} == _CODES
    entry = GovernanceDiagnostic(GovernanceDiagnosticCode.FALLBACK_APPLIED, "text")
    assert entry.to_json() == {"code": "FALLBACK_APPLIED", "message": "text"}
    assert type(entry.to_json()["code"]) is str
