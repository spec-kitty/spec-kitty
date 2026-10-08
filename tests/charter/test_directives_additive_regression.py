"""Regression: project-local directives are additive, not replacing (#3728).

Pins the defect reported in https://github.com/Priivacy-ai/spec-kitty/issues/3728:
a single ``directives:`` declaration in ``charter.yaml`` collapsed the resolved
directive set from the full built-in catalog (34 directives) down to just the
one local declaration. ``_resolve_directives_selection`` must instead **union**
project-local declarations onto the resolved base set, announce the merge with a
diagnostic, and carry ``"…+project_local"`` provenance.

The defect is fixed (this PR). These assertions were red-first against the
pre-fix replace behaviour — ``result.directives == ["LOCAL_QA_PROBE"]`` and
``directives_source == "catalog_fallback"`` (no additive union, no merge
diagnostic) — and now stand as a permanent guard against the silent-replace
regression recurring. The #3728 reference is retained as history.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from charter.activation.resolver import resolve_project_governance
from tests.charter.test_resolver import _write_charter_files

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_CATALOG = SimpleNamespace(
    paradigms=frozenset(),
    directives=frozenset({"DIRECTIVE_003", "DIRECTIVE_010"}),
    template_sets=frozenset({"software-dev-default"}),
    domains_present=frozenset(),
)


def _patch_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("charter.activation.resolver.load_doctrine_catalog", lambda: _CATALOG)


def test_single_local_directive_unions_onto_catalog_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One local declaration is appended to the catalog base, never replacing it."""
    _patch_catalog(monkeypatch)
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
        directives="""
directives:
  - id: LOCAL_QA_PROBE
    title: Local QA probe
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    # Base (sorted catalog) then the appended local id — no base id dropped.
    assert result.directives == ["DIRECTIVE_003", "DIRECTIVE_010", "LOCAL_QA_PROBE"]
    assert result.metadata["directives_source"] == "catalog_fallback+project_local"
    assert any("project-local directive" in line and "LOCAL_QA_PROBE" in line for line in result.diagnostics), result.diagnostics


def test_multiple_local_directives_lose_no_base_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: three local declarations add three ids; every base id survives."""
    _patch_catalog(monkeypatch)
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
        directives="""
directives:
  - id: LOCAL_A
    title: Local A
  - id: LOCAL_B
    title: Local B
  - id: LOCAL_C
    title: Local C
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.directives == [
        "DIRECTIVE_003",
        "DIRECTIVE_010",
        "LOCAL_A",
        "LOCAL_B",
        "LOCAL_C",
    ]
    # No base id lost.
    assert "DIRECTIVE_003" in result.directives
    assert "DIRECTIVE_010" in result.directives
    assert result.metadata["directives_source"] == "catalog_fallback+project_local"
