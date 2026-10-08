"""WP02 (#3728, FR-007): ``charter context --json`` surfaces ``directives_source``.

The resolution-level ``directives_source`` provenance produced by WP01
(``GovernanceResolution.metadata["directives_source"]``) must appear as a
top-level key in the ``build_charter_context_json`` payload, obtained from a
*single* governance resolution, with the value distinct from the per-entry
``all_directives[].source`` artifact-origin field.

Mirrors WP01's regression fixture (``test_directives_additive_regression.py``):
a monkeypatched 2-directive catalog base plus one project-local directive
declaration resolves to ``"catalog_fallback+project_local"`` with the base
preserved (SC-001 at the JSON layer).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import charter.activation.resolver as _resolver
from charter.activation.context import build_charter_context_json
from charter.activation.context_contract import CONTEXT_CONTRACT_TOP_LEVEL_KEYS
from tests.charter.test_resolver import _write_charter_files

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_CATALOG = SimpleNamespace(
    paradigms=frozenset(),
    directives=frozenset({"DIRECTIVE_003", "DIRECTIVE_010"}),
    template_sets=frozenset({"software-dev-default"}),
    domains_present=frozenset(),
)
_BASE_COUNT = len(_CATALOG.directives)


def _patch_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_resolver, "load_offering_catalog", lambda: _CATALOG)


def _seed_local_directive(root: Path) -> None:
    _write_charter_files(
        root,
        governance="charter: {}\n",
        directives="""
directives:
  - id: LOCAL_QA_PROBE
    title: Local QA probe
""",
    )


def test_directives_source_surfaced_in_json_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The payload carries the resolution branch as a top-level string key."""
    _patch_catalog(monkeypatch)
    _seed_local_directive(tmp_path)

    payload = build_charter_context_json(tmp_path, action="plan")

    assert payload["directives_source"] == "catalog_fallback+project_local"
    # SC-001 at the JSON layer: base preserved end-to-end, plus the local id.
    assert isinstance(payload["all_directives"], list)
    assert len(payload["all_directives"]) == _BASE_COUNT + 1
    # The new key is declared in the frozen contract ledger.
    assert "directives_source" in CONTEXT_CONTRACT_TOP_LEVEL_KEYS


def test_directives_source_is_distinct_from_per_entry_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolution-level provenance is a top-level sibling, never nested in the
    per-entry ``all_directives[].source`` artifact-origin field."""
    _patch_catalog(monkeypatch)
    _seed_local_directive(tmp_path)

    payload = build_charter_context_json(tmp_path, action="plan")

    assert payload.get("directives_source") == "catalog_fallback+project_local"
    entries = payload["all_directives"]
    assert isinstance(entries, list)
    # Per-entry ``source`` is artifact-origin, a different vocabulary.
    per_entry_sources = {entry.get("source") for entry in entries}
    assert per_entry_sources <= {"project", "builtin", "org"}
    assert "catalog_fallback+project_local" not in per_entry_sources


def test_directives_source_comes_from_single_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The builder resolves governance exactly once per payload (no double
    resolve to obtain the provenance separately)."""
    _patch_catalog(monkeypatch)
    _seed_local_directive(tmp_path)

    real_resolve = _resolver.resolve_project_governance
    calls = {"n": 0}

    def _counting_resolve(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        return real_resolve(*args, **kwargs)

    monkeypatch.setattr(_resolver, "resolve_project_governance", _counting_resolve)

    payload = build_charter_context_json(tmp_path, action="plan")

    assert payload["directives_source"] == "catalog_fallback+project_local"
    assert calls["n"] == 1, (
        f"resolve_project_governance called {calls['n']}x; the JSON payload must obtain all_directives and directives_source from a single resolution."
    )
