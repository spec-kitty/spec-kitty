"""Occurrence-map field-path granularity (WP02, FR-002/C-005/SC-011).

``exceptions[]`` matches by *path glob* alone. Mission B2's exemptions are
*field*-scoped, and the two do not line up: many of its GOVERNANCE
files also carry MIGRATE entries, and most RAW_MATERIAL files do too
(#5367). The asserts below check this relationally against the canonical
measurement tool — see ``scripts/doctrine/inline_reference_inventory.py`` —
rather than pinning an exact count. No file-level cut
separates the MIGRATE occurrences from the GOVERNANCE + RAW ones, so the
guardrail cannot express its own mission.

This module is the ATDD contract (charter C-011 / mission C-006): its first
commit is RED against the schema/code as they stood before this WP — a
field-scoped exception did not validate and did not change ``assess_file``'s
verdict. It is GREEN once the schema, loader, admissibility check, and
diff-compliance honouring land.

SC-011's own demonstration duty is discharged here against B2's REAL
exemption set, per the WP prompt's explicit guidance: ``owned_files`` for
this WP may not reference ``kitty-specs/`` paths, so B2's real
``occurrence_map.yaml`` cannot be owned or rewritten here, and a throwaway
fixture *labelled* "B2's exemption set" is exactly the cheapest-fake shape
flagged by the post-tasks squad. Instead, :class:`TestB2RealExemptionSet`
below reads B2's actual map (to confirm the problem it describes is real and
still unaddressed) and reproduces B2's actual (file, field) classification
via the same inventory module SC-011's own numbers are measured with.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import types
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.bulk_edit.diff_check import assess_file, check_diff_compliance
from specify_cli.bulk_edit.occurrence_map import (
    FieldPathException,
    OccurrenceMap,
    check_admissibility,
    load_occurrence_map,
    validate_against_schema,
    validate_occurrence_map,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]

# A real, already-committed, schema-clean legacy map (C-OMAP-1 proof must be
# against a committed map, not a fixture — see the WP prompt's binding note).
_LEGACY_MAP_DIR = (
    _REPO_ROOT
    / "kitty-specs"
    / "charter-ownership-consolidation-and-neutrality-hardening-01KPD880"
)

# B2's real, in-flight bulk-edit mission — the exemption set FR-002/SC-011
# exists to make expressible.
_B2_FEATURE_DIR = (
    _REPO_ROOT / "kitty-specs" / "drg-edge-migration-extractor-retirement-01KYFV8C"
)

_INVENTORY_MODULE_PATH = (
    _REPO_ROOT / "scripts" / "doctrine" / "inline_reference_inventory.py"
)


def _load_inventory_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Load the canonical MIGRATE/GOVERNANCE/RAW_MATERIAL measurement tool.

    Not on pytest's ``pythonpath`` (only ``src`` is, by design — see
    ``pytest.ini``), so it is loaded directly by file path rather than via
    ``sys.path`` mutation. Its own dynamic import of
    ``charter.offering.drg.migration.extractor`` still resolves because ``src`` is
    already on ``sys.path``.
    """
    module_name = "inline_reference_inventory"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, _INVENTORY_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ALL_EIGHT_CATEGORIES = {
    "code_symbols": {"action": "rename"},
    "import_paths": {"action": "rename"},
    "filesystem_paths": {"action": "manual_review"},
    "serialized_keys": {"action": "manual_review"},
    "cli_commands": {"action": "do_not_change"},
    "user_facing_strings": {"action": "rename_if_user_visible"},
    "tests_fixtures": {"action": "rename"},
    "logs_telemetry": {"action": "do_not_change"},
}


def _map_data(exceptions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "target": {"term": "oldName", "operation": "rename"},
        "categories": copy.deepcopy(ALL_EIGHT_CATEGORIES),
        "exceptions": exceptions if exceptions is not None else [],
    }


def _write(feature_dir: Path, content: dict[str, Any]) -> Path:
    yaml = YAML()
    path = feature_dir / "occurrence_map.yaml"
    with open(path, "w") as fh:
        yaml.dump(content, fh)
    return path


def _make_map(
    exceptions: list[dict[str, Any]] | None = None,
    field_path_exceptions: list[FieldPathException] | None = None,
) -> OccurrenceMap:
    raw = _map_data(exceptions)
    return OccurrenceMap(
        target_term="oldName",
        target_replacement=None,
        target_operation="rename",
        categories=raw["categories"],
        exceptions=raw["exceptions"],
        status=None,
        raw=raw,
        field_path_exceptions=field_path_exceptions or [],
    )


# ---------------------------------------------------------------------------
# Schema — a field-path exception must validate, and stay well-formed
# ---------------------------------------------------------------------------


class TestFieldPathExceptionSchema:
    def test_field_path_exception_validates_against_schema(self) -> None:
        data = _map_data(
            [
                {
                    "path": "src/charter/offering/agent_profiles/built-in/*.agent.yaml",
                    "field_path": "directive-references",
                    "action": "do_not_change",
                    "reason": "Governance seed field, never migrated",
                }
            ]
        )
        result = validate_against_schema(data)
        assert result.valid, result.errors

    def test_field_path_must_be_non_empty_string(self) -> None:
        data = _map_data(
            [
                {
                    "path": "src/x.yaml",
                    "field_path": "",
                    "action": "do_not_change",
                }
            ]
        )
        result = validate_against_schema(data)
        assert not result.valid

    def test_field_path_exception_still_requires_path_and_action(self) -> None:
        data = _map_data([{"field_path": "directive-references"}])
        result = validate_against_schema(data)
        assert not result.valid

    def test_field_path_exception_rejects_unknown_keys(self) -> None:
        """``additionalProperties: false`` discipline must survive the extension."""
        data = _map_data(
            [
                {
                    "path": "src/x.yaml",
                    "field_path": "a.b",
                    "action": "do_not_change",
                    "unexpected_key": "nope",
                }
            ]
        )
        result = validate_against_schema(data)
        assert not result.valid


# ---------------------------------------------------------------------------
# Loader + hand-rolled validation
# ---------------------------------------------------------------------------


class TestFieldPathExceptionLoading:
    def test_field_path_exceptions_are_parsed(self, tmp_path: Path) -> None:
        data = _map_data(
            [
                {
                    "path": "profiles/*.yaml",
                    "field_path": "directive-references",
                    "action": "do_not_change",
                    "reason": "seeds governance closure",
                }
            ]
        )
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        assert omap.field_path_exceptions == [
            FieldPathException(
                path="profiles/*.yaml",
                field_path="directive-references",
                action="do_not_change",
                reason="seeds governance closure",
            )
        ]

    def test_whole_file_exceptions_are_not_parsed_as_field_path(
        self, tmp_path: Path
    ) -> None:
        data = _map_data(
            [{"path": "**/migrations/*.py", "action": "do_not_change"}]
        )
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        assert omap.field_path_exceptions == []
        # Legacy whole-file exception is still present in the raw list.
        assert omap.exceptions == [
            {"path": "**/migrations/*.py", "action": "do_not_change"}
        ]

    def test_absent_exceptions_block_yields_no_field_path_exceptions(
        self, tmp_path: Path
    ) -> None:
        data = _map_data(None)
        del data["exceptions"]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None
        assert omap.field_path_exceptions == []

    def test_validate_occurrence_map_accepts_valid_field_path_exception(
        self, tmp_path: Path
    ) -> None:
        data = _map_data(
            [
                {
                    "path": "profiles/*.yaml",
                    "field_path": "directive-references",
                    "action": "do_not_change",
                }
            ]
        )
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid, result.errors

    def test_validate_occurrence_map_flags_blank_field_path(
        self, tmp_path: Path
    ) -> None:
        data = _map_data([{"path": "x.yaml", "field_path": "   ", "action": "do_not_change"}])
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert not result.valid
        assert any("field_path" in e for e in result.errors)

    def test_check_admissibility_still_requires_all_standard_categories(
        self, tmp_path: Path
    ) -> None:
        """WP01 binding constraint: standard-category totality must survive
        the extension unchanged, even when field-path exceptions are present.
        """
        data = _map_data(
            [
                {
                    "path": "profiles/*.yaml",
                    "field_path": "directive-references",
                    "action": "do_not_change",
                }
            ]
        )
        del data["categories"]["logs_telemetry"]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = check_admissibility(omap)
        assert not result.valid
        assert any("logs_telemetry" in e for e in result.errors)


# ---------------------------------------------------------------------------
# C-OMAP-1 — a real, committed legacy map validates EXACTLY as before
# ---------------------------------------------------------------------------


class TestBackwardCompatibilityAgainstACommittedMap:
    def test_committed_legacy_map_still_loads_and_validates(self) -> None:
        omap = load_occurrence_map(_LEGACY_MAP_DIR)
        assert omap is not None

        hand_rolled = validate_occurrence_map(omap)
        schema = validate_against_schema(omap.raw)
        admissibility = check_admissibility(omap)

        assert hand_rolled.valid, hand_rolled.errors
        assert schema.valid, schema.errors
        assert admissibility.valid, admissibility.errors
        # No field-path exceptions: this map predates WP02 and uses only the
        # legacy path-glob form.
        assert omap.field_path_exceptions == []
        assert len(omap.exceptions) > 0


# ---------------------------------------------------------------------------
# diff_check.py — field-path exceptions do not force a whole-file verdict
# ---------------------------------------------------------------------------


class TestDiffCheckHonoursFieldPathExceptions:
    def test_field_path_exception_does_not_block_the_whole_file(self) -> None:
        omap = _make_map(
            field_path_exceptions=[
                FieldPathException(
                    path="profiles/a.agent.yaml",
                    field_path="directive-references",
                    action="do_not_change",
                    reason="governance seed",
                )
            ]
        )

        assessment = assess_file("profiles/a.agent.yaml", omap)

        # Classified normally by its category (serialized_keys -> manual_review
        # in this fixture) — NOT force-blocked by the field-scoped exception.
        assert assessment.violation is False
        assert assessment.category == "serialized_keys"
        assert assessment.action == "manual_review"
        assert assessment.field_path_pins == ("directive-references",)

    def test_multiple_field_path_exceptions_on_one_file_all_pin(self) -> None:
        omap = _make_map(
            field_path_exceptions=[
                FieldPathException(
                    path="profiles/*.yaml",
                    field_path="directive-references",
                    action="do_not_change",
                ),
                FieldPathException(
                    path="profiles/*.yaml",
                    field_path="context-sources.tactics",
                    action="do_not_change",
                ),
            ]
        )

        assessment = assess_file("profiles/a.yaml", omap)

        assert assessment.field_path_pins == (
            "context-sources.tactics",
            "directive-references",
        )

    def test_legacy_whole_file_do_not_change_exception_still_blocks(self) -> None:
        """Regression: a NON-field-scoped exception must still behave exactly
        as before — full-file override, not merely a pin.
        """
        omap = _make_map(
            exceptions=[
                {"path": "**/migrations/*.py", "action": "do_not_change"}
            ]
        )

        assessment = assess_file("src/app/migrations/0001_init.py", omap)

        assert assessment.violation is True
        assert assessment.source == "exception"
        assert assessment.field_path_pins == ()

    def test_field_path_exception_produces_a_targeted_warning(self) -> None:
        omap = _make_map(
            field_path_exceptions=[
                FieldPathException(
                    path="profiles/a.agent.yaml",
                    field_path="directive-references",
                    action="do_not_change",
                )
            ]
        )

        result = check_diff_compliance(["profiles/a.agent.yaml"], omap)

        assert result.passed is True
        assert any(
            "directive-references" in w and "profiles/a.agent.yaml" in w
            for w in result.warnings
        ), result.warnings


# ---------------------------------------------------------------------------
# SC-011 — expressibility against B2's REAL exemption set
# ---------------------------------------------------------------------------


class TestB2RealExemptionSet:
    """B2's map is read, not owned or rewritten (owned_files cannot reference
    ``kitty-specs/``); its real (file, field) classification is reproduced via
    the same measurement tool SC-011's own numbers come from.
    """

    def test_b2_map_documents_the_gap_and_has_no_field_path_exceptions_yet(
        self,
    ) -> None:
        omap = load_occurrence_map(_B2_FEATURE_DIR)
        assert omap is not None
        # B2's own map explicitly defers field-level protection until this WP
        # lands — confirming the problem this WP exists to fix is real and,
        # as of this read, still unaddressed.
        assert omap.field_path_exceptions == []
        assert omap.categories["serialized_keys"]["action"] == "manual_review"

    def test_governance_and_raw_material_occurrences_have_the_sc011_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shape invariants over the shipped doctrine corpus, not counts.

        SC-011 is an *archived* mission's measurement of the corpus at
        authoring time ("188 GOVERNANCE occurrences across 17 files") — an
        archived measurement, not a live cardinality contract. The archived
        spec itself is never edited (C-006); the mistaken claim is corrected
        here, where it is actually asserted. What SC-011's own
        inexpressibility argument needs is only that the GOVERNANCE and
        RAW_MATERIAL dispositions are each non-empty and land on the file
        shapes the field-path exception mechanism has to be able to express
        — agent profiles for GOVERNANCE, styleguides/toolguides for
        RAW_MATERIAL — and that the GOVERNANCE/MIGRATE overlap (the harder
        half of the argument, where a single file needs per-field
        disposition rather than a file-level exclusion) is itself non-empty
        and confined to agent profiles. None of this depends on how many
        profiles, styleguides or toolguides the corpus currently ships, so a
        legitimate new profile or styleguide needs 0 edits here (NFR-003).

        The per-triple contract — every real GOVERNANCE (file, field) pair
        is individually expressible as a field-path exception — is asserted
        separately by
        ``test_every_real_governance_field_is_expressible_as_field_path_exception``
        below and is untouched by this shape check.
        """
        inv = _load_inventory_module(monkeypatch)
        inventory = inv.collect()

        gov = [e for e in inventory.entries if e.disposition == inv.GOVERNANCE]
        raw = [e for e in inventory.entries if e.disposition == inv.RAW_MATERIAL]
        gov_files = {e.path for e in gov}
        raw_files = {e.path for e in raw}
        migrate_files = {
            e.path for e in inventory.entries if e.disposition == inv.MIGRATE
        }

        # Non-vacuity: the corpus must actually exercise both dispositions,
        # or the inexpressibility argument this WP exists to fix has nothing
        # to point at.
        assert gov and raw

        # Every GOVERNANCE occurrence is a ``directive-references`` entry on
        # a built-in agent profile — the governance closure's seed surface
        # (``src/charter/resolver.py``).
        assert all(PurePosixPath(path).match("agent_profiles/*.agent.yaml") for path in gov_files), gov_files

        # Every RAW_MATERIAL occurrence is a path string carried by a
        # styleguide or toolguide — the non-artefact files the doctrine
        # README sanctions carrying (module docstring above ``collect``).
        assert all(
            path.startswith("styleguides/") or path.startswith("toolguides/")
            for path in raw_files
        ), raw_files

        # The GOVERNANCE/MIGRATE overlap is the harder half of SC-011's
        # argument: a file carrying BOTH a governed and a migrated field
        # needs per-field disposition, not a file-level exclusion. It must
        # be non-empty (some profile really does carry both) and confined
        # to agent profiles, which keeps the overlap's target set
        # non-vacuous without naming its members.
        overlap = gov_files & migrate_files
        assert overlap
        assert all(PurePosixPath(path).match("agent_profiles/*.agent.yaml") for path in overlap), overlap

    def test_every_real_governance_field_is_expressible_as_field_path_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The central SC-011 claim: for each of B2's real (file, field)
        GOVERNANCE pairs, a field-path exception naming that exact field
        do_not_change validates against the schema — including for files
        that (per the assertion above) ALSO carry MIGRATE entries.
        """
        inv = _load_inventory_module(monkeypatch)
        inventory = inv.collect()
        gov = [e for e in inventory.entries if e.disposition == inv.GOVERNANCE]

        pairs = {(e.path, e.field_name) for e in gov}
        assert pairs, "expected at least one real GOVERNANCE (file, field) pair"

        for path, field_name in sorted(pairs):
            data = _map_data(
                [
                    {
                        "path": path,
                        "field_path": field_name,
                        "action": "do_not_change",
                        "reason": "governance field, never migrated (WP02 demonstration)",
                    }
                ]
            )
            result = validate_against_schema(data)
            assert result.valid, (path, field_name, result.errors)

    def test_raw_field_name_collides_with_migrate_in_the_same_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Honest boundary, not oversold: RAW and MIGRATE share the exact same
        field name (``references``) in 7 of the 10 RAW files (at #5367), so a
        field-path exception can name the FIELD for reviewer attention but — by
        design — cannot, on its own, separate individual list entries within
        it. B2's own map delegates that finer, entry-level cut to the FR-015
        inventory-based gate, not to this schema. This test pins that the
        schema still *validates* the field-scoped form on those files (the
        field CAN be named) while documenting why it is not a complete
        per-entry guarantee there.
        """
        inv = _load_inventory_module(monkeypatch)
        inventory = inv.collect()
        raw = [e for e in inventory.entries if e.disposition == inv.RAW_MATERIAL]
        migrate = [e for e in inventory.entries if e.disposition == inv.MIGRATE]

        raw_field_names = {e.field_name for e in raw}
        assert raw_field_names == {"references"}

        raw_files = {e.path for e in raw}
        migrate_field_names_in_raw_files = {
            e.field_name for e in migrate if e.path in raw_files
        }
        assert "references" in migrate_field_names_in_raw_files, (
            "the collision this test documents must actually be present, or "
            "the boundary claim is untested"
        )

        for path in sorted(raw_files):
            data = _map_data(
                [
                    {
                        "path": path,
                        "field_path": "references",
                        "action": "do_not_change",
                        "reason": "raw material allowlist (WP02 demonstration)",
                    }
                ]
            )
            result = validate_against_schema(data)
            assert result.valid, (path, result.errors)
