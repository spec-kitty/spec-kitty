"""Tests for ownership.inference — execution mode and owned_files inference."""

from __future__ import annotations

import pytest

from specify_cli.ownership.inference import (
    SRC_FALLBACK_GLOB,
    SRC_FALLBACK_WARNING,
    detect_post_integration_acceptance,
    infer_authoritative_surface,
    infer_execution_mode,
    infer_owned_files,
    infer_ownership,
)
from specify_cli.ownership.models import WorkProductKind, OwnershipManifest
from specify_cli.ownership.validation import validate_authoritative_surface


# ---------------------------------------------------------------------------
# infer_execution_mode
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestInferExecutionMode:
    def test_code_change_default_no_signals(self) -> None:
        """When content has no discernible signals, default to code_change."""
        mode = infer_execution_mode("Create a new feature.", [])
        assert mode == WorkProductKind.CODE_CHANGE

    def test_src_path_implies_code_change(self) -> None:
        content = "Create src/specify_cli/ownership/__init__.py with public exports."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.CODE_CHANGE

    def test_test_path_implies_code_change(self) -> None:
        content = "Add tests/specify_cli/ownership/test_models.py covering all branches."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.CODE_CHANGE

    def test_kitty_specs_only_implies_planning_artifact(self) -> None:
        content = (
            "Update kitty-specs/057-feature/spec.md with FR-004 and FR-005. "
            "Also update kitty-specs/057-feature/plan.md."
        )
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.PLANNING_ARTIFACT

    def test_spec_md_implies_planning_artifact(self) -> None:
        content = "Write spec.md and plan.md for the new feature."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.PLANNING_ARTIFACT

    def test_tasks_md_implies_planning_artifact(self) -> None:
        content = "Generate tasks.md with work packages."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.PLANNING_ARTIFACT

    def test_data_model_md_implies_planning_artifact(self) -> None:
        content = "Write data-model.md describing the entity relationships."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.PLANNING_ARTIFACT

    def test_mixed_content_code_change_wins(self) -> None:
        """When both code and planning signals are present, code_change wins."""
        content = "Update kitty-specs/001/spec.md and implement src/specify_cli/foo.py."
        mode = infer_execution_mode(content, [])
        assert mode == WorkProductKind.CODE_CHANGE

    def test_wp_files_list_contributes(self) -> None:
        content = "Do some work."
        wp_files = ["src/specify_cli/new_module.py"]
        mode = infer_execution_mode(content, wp_files)
        assert mode == WorkProductKind.CODE_CHANGE


# ---------------------------------------------------------------------------
# infer_owned_files
# ---------------------------------------------------------------------------


class TestInferOwnedFiles:
    def test_planning_artifact_defaults_to_feature_glob(self) -> None:
        content = "Update kitty-specs/057-feature/spec.md and plan.md."
        globs, warnings = infer_owned_files(content, "057-my-feature")
        assert "kitty-specs/057-my-feature/**" in globs
        assert warnings == []

    def test_code_change_extracts_src_paths(self) -> None:
        content = (
            "Create src/specify_cli/ownership/__init__.py\n"
            "Create src/specify_cli/ownership/models.py\n"
        )
        globs, warnings = infer_owned_files(content, "057-feature")
        assert any("src/" in g for g in globs)
        assert warnings == []

    def test_code_change_extracts_tests_paths(self) -> None:
        content = "Add tests/specify_cli/ownership/test_models.py"
        globs, warnings = infer_owned_files(content, "057-feature")
        assert any("tests" in g for g in globs)
        assert warnings == []

    def test_fallback_when_no_paths_found(self) -> None:
        """When no path tokens are found in a code_change WP, return src/** with warning."""
        content = "Implement the new feature logic."
        globs, warnings = infer_owned_files(content, "057-feature")
        assert globs == ["src/**"]
        assert len(warnings) == 1
        assert "src/**" in warnings[0]

    def test_deduplicates_results(self) -> None:
        content = (
            "Create src/specify_cli/foo.py\n"
            "Create src/specify_cli/bar.py\n"
        )
        globs, _warnings = infer_owned_files(content, "057-feature")
        assert len(globs) == len(set(globs))


# ---------------------------------------------------------------------------
# infer_authoritative_surface
# ---------------------------------------------------------------------------


class TestInferAuthoritativeSurface:
    def test_single_pattern_returns_prefix(self) -> None:
        surface = infer_authoritative_surface(["src/specify_cli/ownership/**"])
        assert surface == "src/specify_cli/ownership/"

    def test_common_prefix_shared_paths(self) -> None:
        surface = infer_authoritative_surface([
            "src/specify_cli/ownership/**",
            "src/specify_cli/ownership/models.py",
        ])
        assert "src/specify_cli/ownership" in surface

    def test_divergent_paths_shorter_common(self) -> None:
        surface = infer_authoritative_surface([
            "src/specify_cli/alpha/**",
            "src/specify_cli/beta/**",
        ])
        assert surface.startswith("src/specify_cli/")

    def test_empty_list_returns_empty_string(self) -> None:
        surface = infer_authoritative_surface([])
        assert surface == ""

    def test_planning_artifact_path(self) -> None:
        surface = infer_authoritative_surface(["kitty-specs/057-feature/**"])
        assert surface == "kitty-specs/057-feature/"

    # --- #2446: single-entry filename globs must resolve to their directory ---

    def test_single_entry_filename_glob_py(self) -> None:
        """`src/foo/*.py` (trailing filename glob) → its directory `src/foo/`."""
        assert infer_authoritative_surface(["src/foo/*.py"]) == "src/foo/"

    def test_single_entry_filename_glob_ts(self) -> None:
        assert infer_authoritative_surface(["src/foo/*.ts"]) == "src/foo/"

    def test_single_entry_question_glob(self) -> None:
        assert infer_authoritative_surface(["src/foo/data_?.json"]) == "src/foo/"

    def test_single_entry_charclass_glob(self) -> None:
        assert infer_authoritative_surface(["src/foo/[abc].py"]) == "src/foo/"

    # --- #2446 regression guards: existing wildcard shapes unchanged ---

    def test_double_star_still_strips_to_dir(self) -> None:
        assert infer_authoritative_surface(["src/foo/**"]) == "src/foo/"

    def test_single_star_still_strips_to_dir(self) -> None:
        assert infer_authoritative_surface(["src/foo/*"]) == "src/foo/"

    def test_plain_trailing_slash_dir_unchanged(self) -> None:
        assert infer_authoritative_surface(["src/foo/"]) == "src/foo/"

    # --- #2446: multi-entry filename globs sharing a dir collapse to that dir ---

    def test_two_entry_same_dir_filename_globs(self) -> None:
        surface = infer_authoritative_surface(["src/api/*.py", "src/api/*.ts"])
        assert surface == "src/api/"

    def test_disjoint_top_level_uses_first_owned_directory(self) -> None:
        assert infer_authoritative_surface(["src/foo/*.py", "tests/foo/test_bar.py"]) == "src/foo/"

    def test_single_literal_file_uses_its_directory(self) -> None:
        assert infer_authoritative_surface(["src/foo/bar.py"]) == "src/foo/"


# ---------------------------------------------------------------------------
# #2446: inferred surface must satisfy authoritative-surface validation
# (finalize-tasks calls infer_authoritative_surface then
#  validate_authoritative_surface — the inferred value must pass the gate.)
# ---------------------------------------------------------------------------


class TestInferredSurfacePassesValidation:
    @pytest.mark.parametrize(
        "owned",
        [
            ["src/foo/*.py"],
            ["src/foo/*.ts"],
            ["src/foo/data_?.json"],
            ["src/foo/[abc].py"],
            ["src/foo/**"],
            ["src/foo/*"],
            ["src/foo/"],
            ["src/api/*.py", "src/api/*.ts"],
            ["src/foo/bar.py"],
            ["src/foo/*.py", "tests/foo/test_bar.py"],
        ],
    )
    def test_inferred_surface_validates(self, owned: list[str]) -> None:
        surface = infer_authoritative_surface(owned)
        manifest = OwnershipManifest(
            execution_mode=WorkProductKind.CODE_CHANGE,
            owned_files=tuple(owned),
            authoritative_surface=surface,
        )
        assert validate_authoritative_surface(manifest) == []


# ---------------------------------------------------------------------------
# infer_ownership (convenience wrapper)
# ---------------------------------------------------------------------------


class TestInferOwnership:
    def test_code_and_tests_manifest_passes_surface_validation(self) -> None:
        content = "Update src/foo/bar.py and tests/foo/test_bar.py."
        manifest, warnings = infer_ownership(content, "057-feature")
        assert warnings == []
        assert manifest.authoritative_surface == "src/foo/"
        assert validate_authoritative_surface(manifest) == []

    def test_returns_ownership_manifest(self) -> None:
        content = "Create src/specify_cli/ownership/__init__.py"
        manifest, warnings = infer_ownership(content, "057-feature")
        assert isinstance(manifest, OwnershipManifest)
        assert manifest.execution_mode == WorkProductKind.CODE_CHANGE
        assert len(manifest.owned_files) > 0
        assert manifest.authoritative_surface != ""
        assert warnings == []

    def test_planning_artifact_manifest(self) -> None:
        content = "Update kitty-specs/057-feature/spec.md and plan.md."
        manifest, warnings = infer_ownership(content, "057-feature")
        assert manifest.execution_mode == WorkProductKind.PLANNING_ARTIFACT
        assert any("kitty-specs/057-feature" in f for f in manifest.owned_files)
        assert warnings == []

    def test_wp_files_override_contributes(self) -> None:
        content = "Do something."
        manifest, _warnings = infer_ownership(content, "057-feature", wp_files=["src/foo.py"])
        assert manifest.execution_mode == WorkProductKind.CODE_CHANGE

    def test_fallback_manifest_has_warning(self) -> None:
        """WP with no file paths → src/** fallback, warning returned."""
        content = "Implement the new feature logic."
        manifest, warnings = infer_ownership(content, "057-feature")
        assert "src/**" in manifest.owned_files
        assert len(warnings) == 1
        assert "src/**" in warnings[0]


# ---------------------------------------------------------------------------
# T014: src/** fallback warning
# ---------------------------------------------------------------------------


class TestSrcFallbackWarning:
    def test_src_fallback_emits_warning(self) -> None:
        """When no file paths are found, the fallback glob is returned with a warning."""
        content = "Implement the new feature logic with no paths mentioned."
        globs, warnings = infer_owned_files(content, "057-feature")
        assert SRC_FALLBACK_GLOB in globs
        assert len(warnings) == 1
        assert SRC_FALLBACK_WARNING in warnings

    def test_explicit_paths_no_fallback_warning(self) -> None:
        """When explicit paths are found, no fallback warning is emitted."""
        content = "Create src/specify_cli/ownership/__init__.py with exports."
        globs, warnings = infer_owned_files(content, "057-feature")
        # No fallback needed → no warning
        assert warnings == []
        # And the glob is not the fallback (or if it matches, src/** was derived,
        # which would be odd for explicit content — assert no warning is the key check)

    def test_planning_artifact_no_fallback_warning(self) -> None:
        """Planning artifact WPs return the feature glob, no fallback warning."""
        content = "Update kitty-specs/057-feature/spec.md and plan.md."
        globs, warnings = infer_owned_files(content, "057-feature")
        assert "kitty-specs/057-feature/**" in globs
        assert warnings == []

    def test_fallback_glob_constant_matches_actual(self) -> None:
        """SRC_FALLBACK_GLOB constant matches what infer_owned_files returns."""
        content = "Do something generic with no paths."
        globs, _warnings = infer_owned_files(content, "057-feature")
        assert SRC_FALLBACK_GLOB in globs


# ---------------------------------------------------------------------------
# #227: a nested sub-heading under Acceptance Criteria must not truncate scope
# ---------------------------------------------------------------------------


class TestAcceptanceCriteriaScopeHeadingDepth:
    def test_marker_under_nested_subheading_is_detected(self) -> None:
        content = """---
work_package_id: WP01
title: t
---
# WP01
## Acceptance Criteria
- foo
### Notes
- the dashboard is only observable once merged
"""
        warnings = detect_post_integration_acceptance(content, ["src/x.py"])
        assert warnings
        assert "once merged" in warnings[0]

    def test_scope_still_closes_on_sibling_heading(self) -> None:
        """A heading at the same level as the acceptance heading still closes scope."""
        content = """---
work_package_id: WP01
title: t
---
# WP01
## Acceptance Criteria
- foo
## Implementation Notes
- the dashboard is only observable once merged
"""
        warnings = detect_post_integration_acceptance(content, ["src/x.py"])
        assert warnings == []

    def test_scope_closes_on_shallower_heading(self) -> None:
        """A heading shallower than the acceptance heading closes scope."""
        content = """---
work_package_id: WP01
title: t
---
## Acceptance Criteria
- foo
# Next Section
- the dashboard is only observable once merged
"""
        warnings = detect_post_integration_acceptance(content, ["src/x.py"])
        assert warnings == []

    def test_marker_under_doubly_nested_subheading_is_detected(self) -> None:
        """Depth-tracking holds for more than one level of nesting."""
        content = """---
work_package_id: WP01
title: t
---
## Acceptance Criteria
- foo
### Notes
#### Details
- the dashboard is only observable once merged
"""
        warnings = detect_post_integration_acceptance(content, ["src/x.py"])
        assert warnings
        assert "once merged" in warnings[0]
