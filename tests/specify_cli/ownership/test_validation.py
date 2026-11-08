"""Tests for ownership.validation — overlap, authoritative surface, mode consistency."""

from __future__ import annotations

import pytest

from pathlib import Path

from specify_cli.ownership.models import WorkProductKind, OwnershipManifest
from specify_cli.ownership.validation import (
    ValidationResult,
    build_wp_manifests,
    validate_all,
    validate_authoritative_surface,
    validate_execution_mode_consistency,
    validate_glob_matches,
    validate_no_overlap,
    validate_ownership,
)
from specify_cli.status.wp_metadata import WPMetadata


pytestmark = [pytest.mark.unit, pytest.mark.fast]
def _manifest(
    mode: WorkProductKind = WorkProductKind.CODE_CHANGE,
    owned: tuple[str, ...] = ("src/foo/**",),
    surface: str = "src/foo/",
) -> OwnershipManifest:
    return OwnershipManifest(execution_mode=mode, owned_files=owned, authoritative_surface=surface)


# ---------------------------------------------------------------------------
# validate_no_overlap
# ---------------------------------------------------------------------------


class TestValidateNoOverlap:
    def test_no_overlap_returns_empty(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/bar/**",), surface="src/bar/"),
        }
        errors = validate_no_overlap(manifests)
        assert errors == []

    def test_identical_globs_overlap(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        errors = validate_no_overlap(manifests)
        assert len(errors) == 1
        assert "WP01" in errors[0] and "WP02" in errors[0]

    def test_nested_glob_overlap(self) -> None:
        """src/** overlaps with src/context/** — parent captures child."""
        manifests = {
            "WP01": _manifest(owned=("src/**",), surface="src/"),
            "WP02": _manifest(owned=("src/context/**",), surface="src/context/"),
        }
        errors = validate_no_overlap(manifests)
        assert len(errors) >= 1

    def test_disjoint_paths_no_overlap(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/alpha/**",), surface="src/alpha/"),
            "WP02": _manifest(owned=("src/beta/**",), surface="src/beta/"),
            "WP03": _manifest(owned=("tests/alpha/**",), surface="tests/alpha/"),
        }
        errors = validate_no_overlap(manifests)
        assert errors == []

    def test_sibling_prefix_component_no_overlap(self) -> None:
        """#6312 — ``src/p1/**`` vs ``src/p10/**`` share a string prefix but not
        a path component: they are disjoint directories and must not overlap."""
        manifests = {
            "WP01": _manifest(owned=("src/p1/**",), surface="src/p1/"),
            "WP02": _manifest(owned=("src/p10/**",), surface="src/p10/"),
        }
        errors = validate_no_overlap(manifests)
        assert errors == []

    def test_single_wp_no_overlap(self) -> None:
        manifests = {"WP01": _manifest()}
        errors = validate_no_overlap(manifests)
        assert errors == []

    def test_empty_manifests_no_overlap(self) -> None:
        errors = validate_no_overlap({})
        assert errors == []


class TestValidateNoOverlapSequential:
    """Dependency-aware overlap: same-lane sequential WPs may share owned_files.

    Captures the #2017-class guard bug — a linearized refactor chain (WPs with a
    directed dependency path between them) runs in one worktree, in order, never
    concurrently, so sharing owned_files is legitimate. The no-overlap guard must
    bind only *concurrent* (dependency-unordered / parallel-lane) WPs.
    """

    def test_sequential_pair_with_dependency_allows_overlap(self) -> None:
        # WP02 depends on WP01 → strictly sequential → identical owned_files is OK.
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        errors = validate_no_overlap(manifests, {"WP02": ["WP01"]})
        assert errors == []

    def test_transitive_sequential_allows_overlap(self) -> None:
        # WP03→WP02→WP01: WP01 and WP03 share files but are transitively ordered.
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/bar/**",), surface="src/bar/"),
            "WP03": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        deps = {"WP02": ["WP01"], "WP03": ["WP02"]}
        errors = validate_no_overlap(manifests, deps)
        assert errors == []

    def test_concurrent_pair_still_errors_with_deps(self) -> None:
        # WP01 and WP02 overlap but have NO dependency path → concurrent → ERROR.
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP03": _manifest(owned=("src/bar/**",), surface="src/bar/"),
        }
        # WP03 depends on both, but WP01/WP02 are siblings (no path between them).
        deps = {"WP03": ["WP01", "WP02"]}
        errors = validate_no_overlap(manifests, deps)
        assert len(errors) == 1
        assert "WP01" in errors[0] and "WP02" in errors[0]

    def test_no_deps_preserves_legacy_all_pairs_behavior(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        # dependencies=None → legacy all-pairs overlap detection.
        assert len(validate_no_overlap(manifests, None)) == 1

    def test_validate_all_threads_dependencies(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        result = validate_all(manifests, {"WP02": ["WP01"]})
        assert result.passed, result.errors


# ---------------------------------------------------------------------------
# validate_authoritative_surface
# ---------------------------------------------------------------------------


class TestValidateAuthoritativeSurface:
    def test_valid_prefix(self) -> None:
        m = _manifest(owned=("src/foo/**",), surface="src/foo/")
        errors = validate_authoritative_surface(m)
        assert errors == []

    def test_exact_match_valid(self) -> None:
        m = _manifest(owned=("src/foo",), surface="src/foo")
        errors = validate_authoritative_surface(m)
        assert errors == []

    def test_surface_not_a_prefix_returns_error(self) -> None:
        m = _manifest(owned=("src/bar/**",), surface="src/foo/")
        errors = validate_authoritative_surface(m)
        assert len(errors) == 1
        assert "prefix" in errors[0].lower() or "authoritative_surface" in errors[0]

    def test_empty_surface_returns_error(self) -> None:
        m = _manifest(owned=("src/foo/**",), surface="")
        errors = validate_authoritative_surface(m)
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_no_owned_files_but_surface_present(self) -> None:
        m = _manifest(owned=(), surface="src/foo/")
        errors = validate_authoritative_surface(m)
        # No files to prefix → surface is not a prefix of any file
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# validate_execution_mode_consistency
# ---------------------------------------------------------------------------


class TestValidateExecutionModeConsistency:
    def test_code_change_with_src_files_no_warning(self) -> None:
        m = _manifest(mode=WorkProductKind.CODE_CHANGE, owned=("src/foo/**",), surface="src/foo/")
        warnings = validate_execution_mode_consistency(m)
        assert warnings == []

    def test_code_change_with_tests_files_no_warning(self) -> None:
        m = _manifest(
            mode=WorkProductKind.CODE_CHANGE,
            owned=("tests/specify_cli/**",),
            surface="tests/specify_cli/",
        )
        warnings = validate_execution_mode_consistency(m)
        assert warnings == []

    def test_code_change_with_only_kitty_specs_warns(self) -> None:
        m = _manifest(
            mode=WorkProductKind.CODE_CHANGE,
            owned=("kitty-specs/001-feature/**",),
            surface="kitty-specs/001-feature/",
        )
        warnings = validate_execution_mode_consistency(m)
        assert len(warnings) == 1

    def test_planning_artifact_with_kitty_specs_no_warning(self) -> None:
        m = _manifest(
            mode=WorkProductKind.PLANNING_ARTIFACT,
            owned=("kitty-specs/001-feature/**",),
            surface="kitty-specs/001-feature/",
        )
        warnings = validate_execution_mode_consistency(m)
        assert warnings == []

    def test_planning_artifact_with_docs_no_warning(self) -> None:
        m = _manifest(
            mode=WorkProductKind.PLANNING_ARTIFACT,
            owned=("docs/features/**",),
            surface="docs/features/",
        )
        warnings = validate_execution_mode_consistency(m)
        assert warnings == []

    def test_planning_artifact_with_src_warns(self) -> None:
        m = _manifest(
            mode=WorkProductKind.PLANNING_ARTIFACT,
            owned=("src/specify_cli/ownership/**",),
            surface="src/specify_cli/ownership/",
        )
        warnings = validate_execution_mode_consistency(m)
        assert len(warnings) == 1

    def test_empty_owned_files_no_warning(self) -> None:
        m = _manifest(mode=WorkProductKind.CODE_CHANGE, owned=(), surface="src/")
        warnings = validate_execution_mode_consistency(m)
        # Empty owned_files → no inconsistency to detect
        assert warnings == []


# ---------------------------------------------------------------------------
# validate_all / validate_ownership
# ---------------------------------------------------------------------------


class TestValidateAll:
    def test_valid_manifests_pass(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/alpha/**",), surface="src/alpha/"),
            "WP02": _manifest(owned=("src/beta/**",), surface="src/beta/"),
        }
        result = validate_all(manifests)
        assert result.passed

    def test_overlap_fails(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/**",), surface="src/"),
            "WP02": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        result = validate_all(manifests)
        assert not result.passed
        assert any("WP01" in e or "WP02" in e for e in result.errors)

    def test_bad_surface_fails(self) -> None:
        manifests = {
            "WP01": _manifest(owned=("src/bar/**",), surface="src/foo/"),
        }
        result = validate_all(manifests)
        assert not result.passed

    def test_mode_inconsistency_is_warning_not_error(self) -> None:
        # planning_artifact owns src/ → warning only
        manifests = {
            "WP01": _manifest(
                mode=WorkProductKind.PLANNING_ARTIFACT,
                owned=("src/foo/**",),
                surface="src/foo/",
            ),
        }
        result = validate_all(manifests)
        # Surface check will fail (src/ is not a planning path) — that is an error
        # but mode inconsistency itself is a warning
        assert any("WP01" in w for w in result.warnings)

    def test_validate_ownership_alias(self) -> None:
        """validate_ownership must be an alias for validate_all."""
        manifests = {
            "WP01": _manifest(owned=("src/foo/**",), surface="src/foo/"),
        }
        r1 = validate_all(manifests)
        r2 = validate_ownership(manifests)
        assert r1.passed == r2.passed
        assert r1.errors == r2.errors

    def test_validation_result_is_dataclass(self) -> None:
        result = ValidationResult()
        assert result.passed
        result.errors.append("some error")
        assert not result.passed


# ---------------------------------------------------------------------------
# T013: validate_glob_matches — warns when globs match zero files
# ---------------------------------------------------------------------------


class TestValidateGlobMatches:
    def test_nonexistent_glob_emits_warning(self, tmp_path: Path) -> None:
        """A zero-match glob pattern must produce a warning (not a hard error)."""
        manifests = {
            "WP01": _manifest(
                owned=("nonexistent_dir/**",),
                surface="nonexistent_dir/",
            ),
        }
        result = validate_glob_matches(manifests, tmp_path)
        # Glob patterns are soft warnings — command still passes
        assert result.passed, f"Glob zero-match should not be a hard error: {result.errors}"
        assert len(result.warnings) == 1
        assert "WP01" in result.warnings[0]
        assert "nonexistent_dir/**" in result.warnings[0]

    def test_existing_glob_no_warning(self, tmp_path: Path) -> None:
        """A glob that matches at least one file must produce no warning."""
        # Create a file so the glob matches
        src_dir = tmp_path / "src" / "module"
        src_dir.mkdir(parents=True)
        (src_dir / "foo.py").write_text("# hello")

        manifests = {
            "WP01": _manifest(owned=("src/**",), surface="src/"),
        }
        result = validate_glob_matches(manifests, tmp_path)
        assert result.passed
        assert result.warnings == []
        assert result.errors == []

    def test_multiple_globs_one_missing_warns(self, tmp_path: Path) -> None:
        """Only the missing glob gets a warning; existing one is fine."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "present.py").write_text("# present")

        manifests = {
            "WP01": OwnershipManifest(
                execution_mode=WorkProductKind.CODE_CHANGE,
                owned_files=("src/**", "missing_path/**"),
                authoritative_surface="src/",
            ),
        }
        result = validate_glob_matches(manifests, tmp_path)
        assert result.passed  # glob warnings don't fail passed
        assert len(result.warnings) == 1
        assert "missing_path/**" in result.warnings[0]

    def test_empty_manifests_no_warnings(self, tmp_path: Path) -> None:
        result = validate_glob_matches({}, tmp_path)
        assert result.passed
        assert result.warnings == []
        assert result.errors == []

    def test_warnings_sorted_by_wp_id(self, tmp_path: Path) -> None:
        """Warnings are emitted in sorted WP ID order."""
        manifests = {
            "WP02": _manifest(owned=("miss_b/**",), surface="miss_b/"),
            "WP01": _manifest(owned=("miss_a/**",), surface="miss_a/"),
        }
        result = validate_glob_matches(manifests, tmp_path)
        assert result.passed
        assert len(result.warnings) == 2
        assert result.warnings[0].startswith("WP01")
        assert result.warnings[1].startswith("WP02")

    def test_literal_zero_match_error_hints_create_intent(self, tmp_path: Path) -> None:
        """Regression for issue #1982.

        A literal owned_files path that matches zero files must produce an error
        message containing a YAML-format create_intent snippet so agents can
        self-recover without consulting documentation.

        The assertion checks for the YAML-list syntax form which is absent in
        the pre-fix message ("add it to 'create_intent' in the WP frontmatter")
        and present only after the fix adds the inline YAML fragment.
        """
        absent_path = "src/specify_cli/new_planned_module.py"
        manifests = {
            "WP01": OwnershipManifest(
                owned_files=(absent_path,),
                authoritative_surface="src/specify_cli/",
                execution_mode=WorkProductKind.CODE_CHANGE,
            )
        }

        result = validate_glob_matches(manifests, tmp_path)

        assert not result.passed, "Expected validation to fail for absent literal path"
        assert result.errors, "Expected at least one error message"
        error_text = result.errors[0]
        # Assert YAML-list syntax — absent in pre-fix message, present only after the fix.
        # Pre-fix: "add it to 'create_intent' in the WP frontmatter."
        # Post-fix: "declare it in the WP frontmatter:\n  create_intent:\n    - <path>"
        assert "  create_intent:\n    -" in error_text, (
            f"Error must contain YAML snippet '  create_intent:\\n    -' (absent in pre-fix "
            f"message). Got: {error_text!r}"
        )
        assert absent_path in error_text, (
            f"Error message must include the offending path '{absent_path}'. Got: {error_text!r}"
        )


# ---------------------------------------------------------------------------
# #1753 follow-up: ownership overlap decided logically from WPMetadata stubs.
#
# These prove the invariant WITHOUT real WP files or finalize-command scaffolding:
# build_wp_manifests + validate_ownership is the pure seam finalize-tasks uses.
# Invariant: scope=codebase-wide is the ONLY exemption; lane/dependency
# structure (modelled via the `dependencies` field) never exempts an overlap.
# ---------------------------------------------------------------------------


def _wp(
    wp_id: str,
    owned: tuple[str, ...],
    surface: str,
    *,
    scope: str | None = None,
    deps: tuple[str, ...] = (),
) -> WPMetadata:
    """Minimal WPMetadata stub with explicit ownership (no files involved)."""
    return WPMetadata(
        work_package_id=wp_id,
        execution_mode="code_change",
        owned_files=list(owned),
        authoritative_surface=surface,
        scope=scope,
        dependencies=list(deps),
    )


class TestBuildWpManifestsOverlap:
    """The validator is exercised logically from WPMetadata stubs."""

    def test_independent_wps_overlap_fails(self) -> None:
        """Two independent (different-lane) narrow WPs on the same files fail."""
        result = validate_ownership(
            build_wp_manifests(
                {
                    "WP01": _wp("WP01", ("src/foo/**",), "src/foo/"),
                    "WP02": _wp("WP02", ("src/foo/**",), "src/foo/"),
                }
            )
        )
        assert not result.passed
        assert any("WP01" in e and "WP02" in e for e in result.errors)

    def test_dependency_hierarchy_does_not_exempt(self) -> None:
        """WP02 → WP01 dependency (one lane) does NOT exempt narrow overlap."""
        result = validate_ownership(
            build_wp_manifests(
                {
                    "WP01": _wp("WP01", ("src/foo/**",), "src/foo/"),
                    "WP02": _wp("WP02", ("src/foo/**",), "src/foo/", deps=("WP01",)),
                }
            )
        )
        assert not result.passed

    def test_codebase_wide_is_the_only_exemption(self) -> None:
        """A codebase-wide WP overlapping a narrow WP passes (scope carried)."""
        result = validate_ownership(
            build_wp_manifests(
                {
                    "WP01": _wp("WP01", ("src/**",), "src/", scope="codebase-wide"),
                    "WP02": _wp(
                        "WP02", ("src/foo/bar.py",), "src/foo/bar.py", deps=("WP01",)
                    ),
                }
            )
        )
        assert result.passed

    def test_wp_without_ownership_is_skipped(self) -> None:
        """WPs without execution_mode/owned_files are not manifested."""
        assert build_wp_manifests({"WP01": WPMetadata(work_package_id="WP01")}) == {}
