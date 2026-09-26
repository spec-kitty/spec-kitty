"""T013 (WP03, #3389) — ``procedures`` as the fifth typed array in ``--json``.

Promotes ``procedure`` from a *reference-only* kind (folded into the flat
``references[]`` link set) to a first-class top-level typed array, decorated
exactly like ``directives`` (each entry carrying ``references[]`` + a
``delivery`` cadence marker). The versioned contract bumps atomically with the
shape change:

* top-level ``procedures`` is a typed array whenever ≥1 procedure is delivered,
  and its entries carry the same progressive-disclosure decoration as the
  ``directives`` entries;
* ``context_schema_version == "1.1.0"`` (bumped from ``1.0.0`` in the same
  change — FR-010 / C-005);
* ``"procedures"`` is recorded in ``CONTEXT_CONTRACT_TOP_LEVEL_KEYS``;
* ``asset`` stays deliberately reference-only — there is **no** top-level
  ``assets`` array (FR-009 / D-003, #3037).

Red-first: on the base (no ``procedures[]``, ``CONTEXT_SCHEMA_VERSION == "1.0.0"``,
no ``"procedures"`` in the ledger) every assertion below fails.

Harness note: the ``software-dev/implement`` action scopes four procedures
(``disciplined-defect-diagnosis``/``legacy-codebase-triage``/``refactoring``/
``test-first-bug-fixing`` — see ``packs/built-in/action.graph.yaml``), so a
bootstrap ``implement`` payload with ``mission_type="software-dev"`` delivers a
non-empty procedure set through the live built-in charter (no stubbing).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation.context import build_charter_context_json
from charter.activation.context_contract import (
    CONTEXT_CONTRACT_TOP_LEVEL_KEYS,
    CONTEXT_SCHEMA_VERSION,
)

pytestmark = [pytest.mark.fast]

#: The progressive-disclosure decoration every delivered typed-array entry
#: carries (``references[]`` link set + ``delivery`` cadence marker — WP15).
_DECORATION_KEYS = frozenset({"references", "delivery"})


def _write_charter_fixture(tmp_path: Path) -> None:
    """A minimal, activation-provisioned charter repo (mirrors test_context_bootstrap_markers)."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (charter_dir / "charter.md").write_text(
        textwrap.dedent(
            """\
            # Project Charter

            ## Policy Summary

            - Intent: deterministic procedures-array fixture

            ## Terminology Canon

            - Canonical product term is "Mission".
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "governance.yaml").write_text(
        textwrap.dedent(
            """\
            charter:
              template_set: software-dev-default
              selected_paradigms: []
              selected_directives: []
              available_tools: []
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text('schema_version: "1.0.0"\nreferences: []\n', encoding="utf-8")


def _implement_payload(tmp_path: Path) -> dict[str, object]:
    _write_charter_fixture(tmp_path)
    return build_charter_context_json(tmp_path, action="implement", mission_type="software-dev")


class TestProceduresTypedArray:
    def test_procedures_is_a_decorated_typed_array(self, tmp_path: Path) -> None:
        """``procedures`` is a top-level typed array decorated like ``directives``."""
        payload = _implement_payload(tmp_path)

        assert "procedures" in payload, "bootstrap payload missing 'procedures' key"
        procedures = payload["procedures"]
        assert isinstance(procedures, list)
        assert procedures, "software-dev/implement scopes >=1 procedure"

        directives = payload["directives"]
        assert isinstance(directives, list)
        assert directives, "fixture sanity: directives are delivered too"

        # Same decoration as the directives entries: id + provenance + the
        # progressive-disclosure fields (references[] + delivery marker).
        for entry in procedures:
            assert isinstance(entry, dict)
            assert isinstance(entry.get("id"), str) and entry["id"]
            assert entry.get("source") in {"builtin", "org", "project"}
            assert entry.keys() >= _DECORATION_KEYS, f"procedure entry missing decoration: {sorted(entry.keys())}"
            assert isinstance(entry["references"], list)
            assert entry["delivery"] in {"inline", "link"}

        # Decoration parity with the reference kind (directives) — the same
        # progressive-disclosure fields are present on both arrays.
        directive_decoration = _DECORATION_KEYS & directives[0].keys()
        procedure_decoration = _DECORATION_KEYS & procedures[0].keys()
        assert directive_decoration == procedure_decoration == _DECORATION_KEYS

    def test_procedures_still_named_in_the_reference_link_set(self, tmp_path: Path) -> None:
        """Reference completeness preserved: procedure ids still appear in references[]."""
        payload = _implement_payload(tmp_path)
        procedure_ids = {entry["id"] for entry in payload["procedures"]}  # type: ignore[union-attr]
        reference_ids = {ref["id"] for ref in payload["references"]}  # type: ignore[union-attr]
        assert procedure_ids, "fixture sanity: >=1 procedure delivered"
        assert procedure_ids <= reference_ids, "moving procedure into repos_by_kind must preserve reference completeness"

    def test_schema_version_tracks_the_combined_contract(self, tmp_path: Path) -> None:
        """The versioned contract includes procedures and directives-source (C-005)."""
        assert CONTEXT_SCHEMA_VERSION == "1.3.0"
        payload = _implement_payload(tmp_path)
        assert payload["context_schema_version"] == "1.3.0"

    def test_procedures_recorded_in_top_level_ledger(self) -> None:
        """``procedures`` is declared in the top-level key ledger."""
        assert "procedures" in CONTEXT_CONTRACT_TOP_LEVEL_KEYS

    def test_asset_stays_reference_only_no_assets_array(self, tmp_path: Path) -> None:
        """``asset`` is deliberately NOT promoted — no top-level ``assets`` array."""
        payload = _implement_payload(tmp_path)
        assert "assets" not in payload
        assert "assets" not in CONTEXT_CONTRACT_TOP_LEVEL_KEYS
