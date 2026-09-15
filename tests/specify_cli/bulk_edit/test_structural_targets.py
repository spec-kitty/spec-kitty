"""Tests for the ``structural_targets:`` review-gate exemption.

PR #3134 follow-on: the bulk_edit diff-compliance REVIEW gate hard-blocks a
work package that makes a genuinely STRUCTURAL change to a ``src/*.py`` file
(a new function, a refactor) whenever the path-heuristic classifier maps that
file to a ``do_not_change`` category (e.g. ``code_symbols`` or
``cli_commands``) — even though the change is not a bulk find/replace
occurrence at all. ``structural_targets:`` is a narrow, reviewer-declared,
per-file exemption modeled directly on the existing ``moves:`` idiom
(:mod:`specify_cli.bulk_edit.occurrence_map`, ``MoveEntry``): it names ONE
path or glob whose changes in THIS mission are exempt from the
``do_not_change`` heuristic, never a blanket "ignore all src/*.py".

Covers:
* C-OMAP-1 backward compatibility (a legacy map with no ``structural_targets``
  block validates exactly as before).
* Parsing and structural/schema validation of the new block.
* The review-time diff exemption itself (declared target passes).
* Anti-vacuity: a genuine do_not_change bulk-occurrence violation in a file
  NOT declared as a structural target still blocks review.
* Narrowness invariant (MAJOR + MINOR, second-opinion squad): a bare
  directory, an unbounded glob, or ANY ``**`` directory recursion is
  rejected at validation AND re-checked independently at the review-time
  consumption point, so it can never grant an exemption regardless of how
  it entered the map.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.bulk_edit.diff_check import (
    _structural_target_for,
    assess_file,
    check_diff_compliance,
)
from specify_cli.bulk_edit.occurrence_map import (
    OccurrenceMap,
    StructuralTarget,
    _is_narrow_structural_path,
    check_admissibility,
    load_occurrence_map,
    validate_against_schema,
    validate_occurrence_map,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


ALL_EIGHT_CATEGORIES = {
    "code_symbols": {"action": "do_not_change"},
    "import_paths": {"action": "rename"},
    "filesystem_paths": {"action": "manual_review"},
    "serialized_keys": {"action": "do_not_change"},
    "cli_commands": {"action": "do_not_change"},
    "user_facing_strings": {"action": "rename_if_user_visible"},
    "tests_fixtures": {"action": "rename"},
    "logs_telemetry": {"action": "do_not_change"},
}


def _legacy_map_data() -> dict[str, Any]:
    """A complete, valid single-term map with NO structural_targets block."""
    return {
        "target": {
            "term": "constitution",
            "replacement": "charter",
            "operation": "rename",
        },
        "categories": copy.deepcopy(ALL_EIGHT_CATEGORIES),
        "exceptions": [],
    }


def _write(feature_dir: Path, content: dict[str, Any]) -> Path:
    yaml = YAML()
    path = feature_dir / "occurrence_map.yaml"
    with open(path, "w") as f:
        yaml.dump(content, f)
    return path


# ---------------------------------------------------------------------------
# C-OMAP-1 — legacy maps validate EXACTLY as before
# ---------------------------------------------------------------------------


class TestLegacyBackwardCompat:
    def test_legacy_map_has_empty_structural_targets(self, tmp_path: Path) -> None:
        _write(tmp_path, _legacy_map_data())
        omap = load_occurrence_map(tmp_path)
        assert omap is not None
        assert omap.structural_targets == []

    def test_legacy_map_structural_validation_unchanged(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path, _legacy_map_data())
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)

        assert result.valid is True
        assert result.errors == []
        assert not any("structural_targets" in w for w in result.warnings)

    def test_legacy_map_admissibility_unchanged(self, tmp_path: Path) -> None:
        _write(tmp_path, _legacy_map_data())
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = check_admissibility(omap)

        assert result.valid is True
        assert result.errors == []

    def test_legacy_map_passes_schema(self) -> None:
        result = validate_against_schema(_legacy_map_data())
        assert result.valid, result.errors

    def test_null_structural_targets_is_treated_as_legacy(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = None
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None
        assert omap.structural_targets == []
        assert validate_occurrence_map(omap).valid is True


# ---------------------------------------------------------------------------
# structural_targets: block — parse, validate, schema
# ---------------------------------------------------------------------------


class TestStructuralTargetsParsing:
    def test_structural_targets_block_parsed_into_entries(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [
            {
                "path": "src/specify_cli/bulk_edit/gate.py",
                "reason": "New helper function, not a bulk-occurrence edit",
            },
            {"path": "src/specify_cli/bulk_edit/diff_check.py"},
        ]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        assert len(omap.structural_targets) == 2
        first = omap.structural_targets[0]
        assert isinstance(first, StructuralTarget)
        assert first.path == "src/specify_cli/bulk_edit/gate.py"
        assert first.reason == "New helper function, not a bulk-occurrence edit"
        assert omap.structural_targets[1].reason is None

    def test_malformed_entries_are_skipped_on_parse(self, tmp_path: Path) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [
            "not-a-mapping",
            {"reason": "missing path"},
            {"path": ""},
            {"path": "src/valid.py"},
        ]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None
        assert len(omap.structural_targets) == 1
        assert omap.structural_targets[0].path == "src/valid.py"


class TestStructuralTargetsValidation:
    def test_valid_structural_targets_block_validates_and_gates(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [
            {"path": "src/specify_cli/bulk_edit/gate.py", "reason": "refactor"},
        ]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        assert validate_occurrence_map(omap).valid is True
        assert check_admissibility(omap).valid is True
        assert validate_against_schema(data).valid is True

    def test_structural_target_missing_path_is_rejected(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"reason": "missing path"}]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is False
        assert any(
            "path" in e and "structural_targets[0]" in e for e in result.errors
        )

    def test_structural_targets_not_a_list_is_rejected(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = {"path": "src/a.py"}
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is False
        assert any(
            "structural_targets" in e and "list" in e for e in result.errors
        )

    def test_schema_rejects_structural_target_without_path(self) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"reason": "missing path"}]
        result = validate_against_schema(data)
        assert result.valid is False


# ---------------------------------------------------------------------------
# MAJOR hardening (architect-alphonso): narrowness is a validator invariant,
# not documentation. `_path_matches` (shared with `moves:`) does
# directory-PREFIX matching, so an unvalidated `path: "src"` or a bare `**`
# would silently exempt every file beneath it -- reopening the defect class
# (Directive 043) this gate exists to close. These tests prove the invariant
# is enforced structurally: a too-broad `path`, or a missing `reason`, is
# REJECTED before it can ever reach the runtime exemption in diff_check.py.
# ---------------------------------------------------------------------------


class TestStructuralTargetNarrownessInvariant:
    @pytest.mark.parametrize(
        "bad_path",
        [
            "src",
            "src/specify_cli",
            "src/specify_cli/bulk_edit/",
            "*",
            "**",
            "**/*",
            "file.*",
            # `**` directory recursion (MAJOR, second-opinion squad): a fixed
            # basename extension does NOT make these narrow -- `**` still
            # matches an unbounded number of directories, so each of these
            # would silently exempt every .py file under src/ if accepted.
            "**/*.py",
            "src/**/*.py",
            "**/bar_*.py",
            "src/**",
        ],
    )
    def test_broad_path_is_rejected_at_validation(
        self, tmp_path: Path, bad_path: str
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"path": bad_path, "reason": "refactor"}]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is False
        assert any(
            "structural_targets[0]" in e and "path" in e for e in result.errors
        )

    @pytest.mark.parametrize(
        "good_path",
        [
            "src/specify_cli/bulk_edit/gate.py",
            "src/specify_cli/bulk_edit/*.py",
        ],
    )
    def test_narrow_path_is_accepted_at_validation(
        self, tmp_path: Path, good_path: str
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"path": good_path, "reason": "refactor"}]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is True, result.errors
        assert validate_against_schema(data).valid is True

    def test_missing_reason_is_rejected_at_validation(
        self, tmp_path: Path
    ) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"path": "src/foo/bar.py"}]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is False
        assert any(
            "structural_targets[0]" in e and "reason" in e for e in result.errors
        )

    def test_empty_reason_is_rejected_at_validation(self, tmp_path: Path) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"path": "src/foo/bar.py", "reason": "   "}]
        _write(tmp_path, data)
        omap = load_occurrence_map(tmp_path)
        assert omap is not None

        result = validate_occurrence_map(omap)
        assert result.valid is False
        assert any(
            "structural_targets[0]" in e and "reason" in e for e in result.errors
        )

    def test_schema_rejects_structural_target_without_reason(self) -> None:
        data = _legacy_map_data()
        data["structural_targets"] = [{"path": "src/foo/bar.py"}]
        result = validate_against_schema(data)
        assert result.valid is False


# ---------------------------------------------------------------------------
# Review-time diff exemption for declared structural targets
# ---------------------------------------------------------------------------


def _map_with_structural_targets(
    targets: list[StructuralTarget],
) -> OccurrenceMap:
    raw = {
        "target": {"term": "oldName", "operation": "rename"},
        "categories": copy.deepcopy(ALL_EIGHT_CATEGORIES),
        "exceptions": [],
        "structural_targets": [
            {"path": t.path, **({"reason": t.reason} if t.reason else {})}
            for t in targets
        ],
    }
    return OccurrenceMap(
        target_term="oldName",
        target_replacement=None,
        target_operation="rename",
        categories=copy.deepcopy(ALL_EIGHT_CATEGORIES),
        exceptions=[],
        status=None,
        raw=raw,
        structural_targets=targets,
    )


class TestStructuralTargetDiffExemption:
    def test_declared_structural_src_file_is_exempt(self) -> None:
        # code_symbols (src/*.py) is do_not_change in this fixture map; a
        # declared structural target must exempt the named file.
        omap = _map_with_structural_targets(
            [
                StructuralTarget(
                    path="src/specify_cli/bulk_edit/gate.py",
                    reason="Structural refactor",
                )
            ]
        )
        a = assess_file("src/specify_cli/bulk_edit/gate.py", omap)
        assert a.violation is False
        assert a.source == "structural-target"

    def test_extension_bounded_glob_target_matches_sibling_file(self) -> None:
        # Deliberately NOT a bare directory (rejected at validation, see
        # TestStructuralTargetNarrownessInvariant) -- an extension-bounded
        # glob is the narrow, validator-accepted way to cover several files.
        omap = _map_with_structural_targets(
            [StructuralTarget(path="src/specify_cli/bulk_edit/*.py")]
        )
        a = assess_file("src/specify_cli/bulk_edit/diff_check.py", omap)
        assert a.violation is False
        assert a.source == "structural-target"

    def test_check_diff_compliance_passes_with_structural_target(self) -> None:
        omap = _map_with_structural_targets(
            [StructuralTarget(path="src/specify_cli/bulk_edit/gate.py")]
        )
        result = check_diff_compliance(
            ["src/specify_cli/bulk_edit/gate.py"], omap
        )
        assert result.passed is True

    # -----------------------------------------------------------------
    # Anti-vacuity: an undeclared do_not_change bulk-occurrence violation
    # in a DIFFERENT file must still block review.
    # -----------------------------------------------------------------

    def test_undeclared_do_not_change_file_still_blocks(self) -> None:
        omap = _map_with_structural_targets(
            [StructuralTarget(path="src/specify_cli/bulk_edit/gate.py")]
        )
        # A sibling .py file not named as a structural target still
        # classifies as code_symbols (do_not_change) and violates.
        a = assess_file("src/specify_cli/bulk_edit/other_module.py", omap)
        assert a.violation is True
        assert a.source == "path-heuristic"

    def test_check_diff_compliance_blocks_mixed_diff_with_undeclared_file(
        self,
    ) -> None:
        omap = _map_with_structural_targets(
            [StructuralTarget(path="src/specify_cli/bulk_edit/gate.py")]
        )
        result = check_diff_compliance(
            [
                "src/specify_cli/bulk_edit/gate.py",  # declared -> ok
                "src/specify_cli/bulk_edit/other_module.py",  # undeclared -> blocks
            ],
            omap,
        )
        assert result.passed is False
        assert any(
            "other_module.py" in e for e in result.errors
        )

    def test_no_structural_targets_declared_still_blocks(self) -> None:
        # A map with an EMPTY structural_targets block behaves exactly like
        # one with none at all -- the exemption is opt-in per file, not a
        # standing allowance.
        omap = _map_with_structural_targets([])
        a = assess_file("src/specify_cli/bulk_edit/gate.py", omap)
        assert a.violation is True
        assert a.source == "path-heuristic"


# ---------------------------------------------------------------------------
# MAJOR hardening: every structural-target exemption must be VISIBLE in gate
# output. Before this, check_diff_compliance emitted no warning at all when
# a structural-target exemption fired -- a WP could pass review with no
# trace that a do_not_change category was bypassed for a specific file. This
# mirrors the existing manual_review / field-path-pin warning idiom.
# ---------------------------------------------------------------------------


class TestStructuralTargetExemptionVisibility:
    def test_exemption_emits_warning_naming_file_and_reason(self) -> None:
        omap = _map_with_structural_targets(
            [
                StructuralTarget(
                    path="src/specify_cli/bulk_edit/gate.py",
                    reason="New helper function, not a bulk-occurrence edit",
                )
            ]
        )
        result = check_diff_compliance(
            ["src/specify_cli/bulk_edit/gate.py"], omap
        )
        assert result.passed is True
        assert any(
            "src/specify_cli/bulk_edit/gate.py" in w
            and "New helper function, not a bulk-occurrence edit" in w
            for w in result.warnings
        )

    def test_no_structural_target_warning_when_exemption_does_not_fire(
        self,
    ) -> None:
        omap = _map_with_structural_targets(
            [StructuralTarget(path="src/specify_cli/bulk_edit/gate.py")]
        )
        # gate.py is NOT part of this diff -- no exemption fires, so no
        # structural-target warning should appear (only the plain
        # do_not_change violation for the undeclared file).
        result = check_diff_compliance(
            ["src/specify_cli/bulk_edit/other_module.py"], omap
        )
        assert result.passed is False
        assert not any("structural-target" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# MINOR hardening (defense-in-depth, second-opinion squad): narrowness must
# not rely SOLELY on finalize-time validation. `_structural_target_for` --
# the actual consumption point that grants the exemption at review time --
# re-checks `_is_narrow_structural_path` itself, so a broad entry that
# reaches `omap.structural_targets` by ANY route (a map finalized by a
# pre-hardening version, or hand-edited after finalize, bypassing
# `validate_occurrence_map` entirely) still cannot grant an exemption.
# ---------------------------------------------------------------------------


class TestStructuralTargetConsumptionPointRevalidation:
    @pytest.mark.parametrize("broad_path", ["src", "src/**/*.py", "**/*.py"])
    def test_broad_target_built_directly_grants_no_exemption(
        self, broad_path: str
    ) -> None:
        # Bypasses validate_occurrence_map entirely -- constructs the
        # OccurrenceMap by hand, exactly as a hand-edited-after-finalize
        # occurrence_map.yaml (or one written by a pre-hardening version)
        # would be loaded. _structural_target_for must still refuse it.
        omap = _map_with_structural_targets(
            [StructuralTarget(path=broad_path, reason="looks legitimate")]
        )
        assert _structural_target_for(
            "src/specify_cli/bulk_edit/gate.py", omap
        ) is None

    @pytest.mark.parametrize("broad_path", ["src", "src/**/*.py", "**/*.py"])
    def test_broad_target_does_not_exempt_do_not_change_file_from_review(
        self, broad_path: str
    ) -> None:
        # End-to-end through assess_file/check_diff_compliance: a do_not_change
        # .py file must still block, not silently pass, even though the map
        # carries a (validation-bypassing) blanket-looking structural target.
        omap = _map_with_structural_targets(
            [StructuralTarget(path=broad_path, reason="looks legitimate")]
        )
        a = assess_file("src/specify_cli/bulk_edit/gate.py", omap)
        assert a.violation is True
        assert a.source != "structural-target"

        result = check_diff_compliance(
            ["src/specify_cli/bulk_edit/gate.py"], omap
        )
        assert result.passed is False

    def test_is_narrow_structural_path_rejects_recursive_glob_directly(
        self,
    ) -> None:
        # Direct unit coverage of the predicate both call sites share.
        assert _is_narrow_structural_path("src/**/*.py") is False
        assert _is_narrow_structural_path("**/*.py") is False
        assert _is_narrow_structural_path("**/bar_*.py") is False
        assert _is_narrow_structural_path("src/**") is False
        assert _is_narrow_structural_path("src/foo/*.py") is True
        assert _is_narrow_structural_path("src/foo/bar.py") is True
