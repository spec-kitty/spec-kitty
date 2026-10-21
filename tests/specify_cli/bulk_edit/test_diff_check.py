"""Unit tests for the review-time diff compliance checker (FR-007 + FR-008)."""

from __future__ import annotations

import pytest

from specify_cli.bulk_edit.diff_check import (
    assess_file,
    check_diff_compliance,
    classify_path,
)
from specify_cli.bulk_edit.occurrence_map import OccurrenceMap


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_map(
    categories: dict[str, dict[str, str]],
    exceptions: list[dict[str, str]] | None = None,
) -> OccurrenceMap:
    raw = {
        "target": {"term": "oldName", "operation": "rename"},
        "categories": categories,
        "exceptions": exceptions or [],
    }
    return OccurrenceMap(
        target_term="oldName",
        target_replacement=None,
        target_operation="rename",
        categories=categories,
        exceptions=exceptions or [],
        status=None,
        raw=raw,
    )


ALL_EIGHT_RENAME = {
    "code_symbols": {"action": "rename"},
    "import_paths": {"action": "rename"},
    "filesystem_paths": {"action": "rename"},
    "serialized_keys": {"action": "rename"},
    "cli_commands": {"action": "rename"},
    "user_facing_strings": {"action": "rename"},
    "tests_fixtures": {"action": "rename"},
    "logs_telemetry": {"action": "rename"},
}

PROTECTIVE_MAP = {
    "code_symbols": {"action": "rename"},
    "import_paths": {"action": "rename"},
    "filesystem_paths": {"action": "manual_review"},
    "serialized_keys": {"action": "do_not_change"},
    "cli_commands": {"action": "do_not_change"},
    "user_facing_strings": {"action": "rename_if_user_visible"},
    "tests_fixtures": {"action": "rename"},
    "logs_telemetry": {"action": "do_not_change"},
}


# ---------------------------------------------------------------------------
# classify_path
# ---------------------------------------------------------------------------


class TestClassifyPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            # tests_fixtures (highest priority)
            ("tests/test_foo.py", "tests_fixtures"),
            ("src/pkg/__tests__/foo.py", "tests_fixtures"),
            ("conftest.py", "tests_fixtures"),
            ("pkg/__snapshots__/a.snap", "tests_fixtures"),
            # cli_commands
            ("src/specify_cli/cli/commands/implement.py", "cli_commands"),
            # user_facing_strings
            ("README.md", "user_facing_strings"),
            ("docs/architecture/foo.md", "user_facing_strings"),
            ("CHANGELOG.md", "user_facing_strings"),
            # serialized_keys
            ("pkg/config.yaml", "serialized_keys"),
            ("pyproject.toml", "serialized_keys"),
            ("data/thing.json", "serialized_keys"),
            # code_symbols
            ("src/pkg/module.py", "code_symbols"),
            ("src/app.ts", "code_symbols"),
            # web and build surfaces (Rails/Phoenix/Laravel layouts)
            ("app/views/layouts/application.html.erb", "code_symbols"),
            ("app/assets/stylesheets/base.css", "code_symbols"),
            ("assets/app.scss", "code_symbols"),
            ("lib/tasks/import.rake", "code_symbols"),
            ("Rakefile", "code_symbols"),
            ("Gemfile", "code_symbols"),
            ("my_gem.gemspec", "code_symbols"),
            ("templates/page.haml", "code_symbols"),
            ("components/Thing.vue", "code_symbols"),
            ("lib/web/live/page.heex", "code_symbols"),
            ("docs/example.erb", "user_facing_strings"),  # docs beat the template rule
            ("Dockerfile", "filesystem_paths"),
            ("services/aligneur/Dockerfile", "filesystem_paths"),
            ("Dockerfile.staging", "filesystem_paths"),
            ("docker-compose.yml", "filesystem_paths"),
            # unclassified
            ("binary.dat", None),
            ("Makefile", None),
        ],
    )
    def test_classify(self, path: str, expected: str | None) -> None:
        assert classify_path(path) == expected

    def test_tests_wins_over_cli_commands(self) -> None:
        """A test file under cli/commands should still classify as tests."""
        assert (
            classify_path("tests/cli/commands/test_implement.py")
            == "tests_fixtures"
        )

    def test_cli_commands_wins_over_code(self) -> None:
        """A CLI command .py should classify as cli_commands, not code_symbols."""
        assert (
            classify_path("src/specify_cli/cli/commands/foo.py")
            == "cli_commands"
        )


# ---------------------------------------------------------------------------
# assess_file — individual verdicts
# ---------------------------------------------------------------------------


class TestAssessFile:
    def test_permits_rename_category(self) -> None:
        omap = _make_map(ALL_EIGHT_RENAME)
        a = assess_file("src/pkg/foo.py", omap)
        assert a.violation is False
        assert a.category == "code_symbols"
        assert a.action == "rename"

    def test_rejects_do_not_change_category(self) -> None:
        omap = _make_map(PROTECTIVE_MAP)
        a = assess_file("pkg/config.yaml", omap)
        assert a.violation is True
        assert a.category == "serialized_keys"
        assert a.action == "do_not_change"
        assert "do_not_change" in a.reason or "FR-007" in a.reason

    def test_rejects_unclassified_surface(self) -> None:
        """FR-008 — files that match no category rule are blocked."""
        omap = _make_map(ALL_EIGHT_RENAME)
        a = assess_file("binary.dat", omap)
        assert a.violation is True
        assert a.category is None
        assert "FR-008" in a.reason or "unclassified" in a.reason.lower()

    def test_rejects_when_category_not_in_map(self) -> None:
        """If a path classifies to a category that's absent from the map,
        treat it as unclassified per FR-008."""
        partial = {
            "code_symbols": {"action": "rename"},
            "import_paths": {"action": "rename"},
            "filesystem_paths": {"action": "rename"},
            "serialized_keys": {"action": "rename"},
            "cli_commands": {"action": "rename"},
            "user_facing_strings": {"action": "rename"},
            "tests_fixtures": {"action": "rename"},
            "logs_telemetry": {"action": "rename"},
        }
        # Drop user_facing_strings and classify a .md file
        del partial["user_facing_strings"]
        omap = _make_map(partial)
        a = assess_file("docs/foo.md", omap)
        assert a.violation is True
        assert a.category == "user_facing_strings"
        assert "not present" in a.reason

    def test_exception_permits_do_not_change_file(self) -> None:
        """An explicit exception with a non-do_not_change action bypasses
        the category-level block."""
        omap = _make_map(
            PROTECTIVE_MAP,
            exceptions=[
                {
                    "path": "pkg/allowed.yaml",
                    "action": "rename",
                    "reason": "explicitly allowed",
                },
            ],
        )
        a = assess_file("pkg/allowed.yaml", omap)
        assert a.violation is False
        assert a.source == "exception"
        assert a.action == "rename"

    def test_exception_can_forbid_otherwise_allowed_file(self) -> None:
        omap = _make_map(
            ALL_EIGHT_RENAME,
            exceptions=[
                {
                    "path": "src/pkg/legacy.py",
                    "action": "do_not_change",
                    "reason": "historical file",
                },
            ],
        )
        a = assess_file("src/pkg/legacy.py", omap)
        assert a.violation is True
        assert a.source == "exception"

    def test_glob_exception_matches(self) -> None:
        omap = _make_map(
            PROTECTIVE_MAP,
            exceptions=[
                {
                    "path": "migrations/*.py",
                    "action": "do_not_change",
                    "reason": "migrations are historical",
                },
            ],
        )
        a = assess_file("migrations/0001_init.py", omap)
        assert a.violation is True
        assert a.source == "exception"

    def test_double_star_glob_matches_nested(self) -> None:
        omap = _make_map(
            PROTECTIVE_MAP,
            exceptions=[
                {
                    "path": "src/**/legacy/*.py",
                    "action": "do_not_change",
                    "reason": "legacy subtree",
                },
            ],
        )
        a = assess_file("src/pkg/inner/legacy/mod.py", omap)
        assert a.violation is True
        assert a.source == "exception"


# ---------------------------------------------------------------------------
# check_diff_compliance — aggregate
# ---------------------------------------------------------------------------


class TestCheckDiffCompliance:
    def test_empty_diff_passes(self) -> None:
        omap = _make_map(PROTECTIVE_MAP)
        result = check_diff_compliance([], omap)
        assert result.passed is True
        assert result.errors == []

    def test_all_safe_files_pass(self) -> None:
        omap = _make_map(ALL_EIGHT_RENAME)
        result = check_diff_compliance(
            ["src/pkg/foo.py", "tests/test_foo.py", "README.md"], omap
        )
        assert result.passed is True

    def test_any_forbidden_file_blocks(self) -> None:
        omap = _make_map(PROTECTIVE_MAP)
        result = check_diff_compliance(
            ["src/pkg/foo.py", "config.yaml"],  # config.yaml -> serialized_keys -> do_not_change
            omap,
        )
        assert result.passed is False
        assert any("config.yaml" in e for e in result.errors)
        # The safe file should still be in assessments
        assert any(a.path == "src/pkg/foo.py" and not a.violation for a in result.assessments)

    def test_manual_review_surfaces_as_warning(self) -> None:
        omap = _make_map(PROTECTIVE_MAP)
        result = check_diff_compliance(["src/paths.py"], omap)
        # code_symbols is rename — but if we touch filesystem_paths via
        # the type, let's pick a clearer case:
        # filesystem_paths is manual_review in PROTECTIVE_MAP but path heuristic
        # doesn't distinguish — code_symbols applies first.
        # So this test just confirms manual_review warnings surface for
        # categories that the heuristic picks.
        omap2 = _make_map(
            {**ALL_EIGHT_RENAME, "code_symbols": {"action": "manual_review"}},
        )
        result = check_diff_compliance(["src/pkg/foo.py"], omap2)
        assert result.passed is True
        assert any("manual_review" in w for w in result.warnings)

    def test_exceptions_honored_in_aggregate(self) -> None:
        omap = _make_map(
            PROTECTIVE_MAP,
            exceptions=[
                {"path": "CHANGELOG.md", "action": "do_not_change", "reason": "historical"},
            ],
        )
        result = check_diff_compliance(["CHANGELOG.md"], omap)
        assert result.passed is False
        assert any("CHANGELOG.md" in e for e in result.errors)
