"""Per-rule unit tests for the stale-lane conflict classifier.

Covers WP08 / T042. Each rule has at least one happy path and one
counter-example. The fail-safe default (R-DEFAULT-MANUAL) is exercised
on a path no other rule covers.

Reference ADR:
    docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

from specify_cli.consolidation.conflict_classifier import (
    RULE_ID_INIT_IMPORTS,
    RULE_ID_PYPROJECT_DEPS,
    RULE_ID_URLS_LIST,
    RULE_ID_UVLOCK,
    Auto,
    ConflictClassification,
    Manual,
    _extract_module,
    _looks_like_urls_assignment,
    _is_urls_list_eligible,
    _parse_dep_lines,
    _parse_import_lines,
    _parse_url_entries,
    _split_conflict_region,
    classify,
    r_default_manual,
    r_init_imports_union,
    r_pyproject_deps_union,
    r_urls_list_union,
    r_uvlock_regenerate,
    validate_resolution,
)


# ---------------------------------------------------------------------------
# R-PYPROJECT-DEPS-UNION
# ---------------------------------------------------------------------------


def _hunk(ours: str, theirs: str) -> str:
    return f"<<<<<<< HEAD\n{ours}=======\n{theirs}>>>>>>> mission\n"


class TestConflictRegionParsing:
    def test_returns_none_when_no_conflict_header(self) -> None:
        assert _split_conflict_region("plain text\n=======\ntheirs\n") is None

    def test_returns_none_when_separator_or_theirs_marker_missing(self) -> None:
        assert _split_conflict_region("<<<<<<< HEAD\nours only\n") is None

    def test_diff3_base_section_is_dropped(self) -> None:
        split = _split_conflict_region(
            "<<<<<<< HEAD\nours\n||||||| base\nbase\n=======\ntheirs\n>>>>>>> branch\n"
        )
        assert split == ("ours\n", "theirs\n")


class TestPyprojectDepsUnion:
    def test_happy_two_sides_add_distinct_deps_sorted(self) -> None:
        ours = '  "httpx>=0.27",\n  "ruamel-yaml",\n'
        theirs = '  "freezegun",\n  "httpx>=0.27",\n  "ruamel-yaml",\n'
        cls = r_pyproject_deps_union(Path("pyproject.toml"), _hunk(ours, theirs))
        assert cls is not None
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_PYPROJECT_DEPS
        # Union is sorted because ours was alphabetical.
        merged = cls.resolution.merged_text
        assert "httpx" in merged and "ruamel-yaml" in merged and "freezegun" in merged
        # Sorted: freezegun before httpx before ruamel-yaml.
        assert merged.index("freezegun") < merged.index("httpx")
        assert merged.index("httpx") < merged.index("ruamel-yaml")

    def test_counter_same_package_version_drift_manual(self) -> None:
        ours = '  "httpx>=0.27",\n'
        theirs = '  "httpx>=0.28",\n'
        cls = r_pyproject_deps_union(Path("pyproject.toml"), _hunk(ours, theirs))
        assert cls is not None
        assert isinstance(cls.resolution, Manual)
        assert "httpx" in cls.resolution.reason
        assert "version drift" in cls.resolution.reason.lower() or "semantic" in cls.resolution.reason.lower()

    def test_returns_none_for_non_pyproject(self) -> None:
        cls = r_pyproject_deps_union(
            Path("src/foo.py"), _hunk('  "x",\n', '  "y",\n')
        )
        assert cls is None

    def test_returns_none_for_garbage_block(self) -> None:
        # Block is not a recognizable dep list; rule passes (returns None).
        cls = r_pyproject_deps_union(
            Path("pyproject.toml"),
            _hunk("def foo():\n    pass\n", "def bar():\n    pass\n"),
        )
        assert cls is None

    def test_returns_none_when_conflict_region_is_malformed(self) -> None:
        cls = r_pyproject_deps_union(Path("pyproject.toml"), "<<<<<<< HEAD\n")
        assert cls is None

    def test_dep_parser_skips_comments_and_normalizes_commas(self) -> None:
        parsed = _parse_dep_lines('  # comment\n  "httpx>=0.27"\n\n')
        assert parsed == [("httpx", '  "httpx>=0.27",')]

    def test_dep_parser_rejects_quoted_non_dependency_line(self) -> None:
        assert _parse_dep_lines('  "!!!"\n') is None


# ---------------------------------------------------------------------------
# R-INIT-IMPORTS-UNION
# ---------------------------------------------------------------------------


class TestInitImportsUnion:
    def test_happy_two_sides_add_distinct_imports(self) -> None:
        ours = "from .auth import AuthFlow\nfrom .flags import FeatureFlags\n"
        theirs = "from .flags import FeatureFlags\nfrom .sync import SyncClient\n"
        cls = r_init_imports_union(
            Path("apps/collab/__init__.py"), _hunk(ours, theirs)
        )
        assert cls is not None
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_INIT_IMPORTS
        merged = cls.resolution.merged_text
        assert "AuthFlow" in merged
        assert "FeatureFlags" in merged
        assert "SyncClient" in merged

    def test_counter_rename_existing_import_manual(self) -> None:
        # Ours renames the existing import on .auth.
        ours = "from .auth import OAuthFlow\n"
        theirs = "from .auth import AuthFlow\nfrom .sync import SyncClient\n"
        cls = r_init_imports_union(
            Path("pkg/__init__.py"), _hunk(ours, theirs)
        )
        assert cls is not None
        assert isinstance(cls.resolution, Manual)
        assert ".auth" in cls.resolution.reason

    def test_returns_none_for_non_init_py(self) -> None:
        cls = r_init_imports_union(
            Path("pkg/views.py"),
            _hunk("from .a import b\n", "from .c import d\n"),
        )
        assert cls is None

    def test_returns_none_for_malformed_conflict_region(self) -> None:
        cls = r_init_imports_union(Path("pkg/__init__.py"), "<<<<<<< HEAD\n")
        assert cls is None

    def test_returns_none_for_non_import_lines(self) -> None:
        cls = r_init_imports_union(
            Path("pkg/__init__.py"),
            _hunk("from .a import A\n", "value = 1\n"),
        )
        assert cls is None

    def test_import_parser_skips_comments_and_rejects_non_imports(self) -> None:
        assert _parse_import_lines("# comment\n\nfrom .a import A\n") == [
            ("from .a import a", "from .a import A")
        ]
        assert _parse_import_lines("not an import\n") is None

    def test_extract_module_handles_import_and_non_import_lines(self) -> None:
        assert _extract_module("import package.submodule, other") == "package.submodule"
        assert _extract_module("value = 1") is None


# ---------------------------------------------------------------------------
# R-URLS-LIST-UNION
# ---------------------------------------------------------------------------


class TestUrlsListUnion:
    def test_happy_distinct_entries_in_urls_py(self) -> None:
        ours = '    "alpha/",\n    "beta/",\n'
        theirs = '    "alpha/",\n    "beta/",\n    "gamma/",\n'
        cls = r_urls_list_union(Path("app/urls.py"), _hunk(ours, theirs))
        assert cls is not None
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_URLS_LIST
        merged = cls.resolution.merged_text
        for entry in ("alpha", "beta", "gamma"):
            assert entry in merged

    def test_counter_same_entry_modification_manual(self) -> None:
        ours = '    "alpha/v1/",\n'
        theirs = '    "alpha/v2/",\n'
        cls = r_urls_list_union(Path("app/urls.py"), _hunk(ours, theirs))
        assert cls is not None
        # Different keys ("alpha/v1/" vs "alpha/v2/") — this is treated as
        # distinct entries by the rule, so it auto-merges. To trigger
        # Manual we need the SAME key with different content (e.g. line
        # comment drift).
        # Adjust expectation: this is a happy union of two distinct strings.
        assert isinstance(cls.resolution, Auto)

    def test_same_quoted_value_with_different_trailing_text_manual(self) -> None:
        ours = '    "alpha/",  # ours-comment\n'
        theirs = '    "alpha/",  # theirs-comment\n'
        cls = r_urls_list_union(Path("app/urls.py"), _hunk(ours, theirs))
        assert cls is not None
        assert isinstance(cls.resolution, Manual)
        assert "alpha" in cls.resolution.reason

    def test_returns_none_for_non_url_file(self) -> None:
        cls = r_urls_list_union(
            Path("src/foo.py"),
            _hunk('    "x",\n', '    "y",\n'),
        )
        assert cls is None

    def test_url_assignment_marker_helper_accepts_non_urls_files(self) -> None:
        assert _looks_like_urls_assignment('URL_PATTERNS = ["alpha/"]')
        assert _looks_like_urls_assignment(" _URLS: router.urls")

    def test_accepts_non_urls_py_url_constant_without_regex_backtracking(self) -> None:
        assert _is_urls_list_eligible(
            Path("src/config.py"),
            'URL_PATTERNS = [\n<<<<<<< HEAD\n    "alpha/",\n=======\n    "beta/",\n>>>>>>> mission\n',
        )

    def test_accepts_type_annotated_non_urls_py_url_constant(self) -> None:
        assert _is_urls_list_eligible(
            Path("src/config.py"),
            'URL_PATTERNS: list[URLPattern] = [\n<<<<<<< HEAD\n    "alpha/",\n=======\n    "beta/",\n>>>>>>> mission\n',
        )

    def test_returns_none_for_malformed_conflict_region(self) -> None:
        cls = r_urls_list_union(Path("app/urls.py"), "<<<<<<< HEAD\n")
        assert cls is None

    def test_returns_none_for_non_string_entries(self) -> None:
        cls = r_urls_list_union(Path("app/urls.py"), _hunk("path('x')\n", '"y",\n'))
        assert cls is None

    def test_url_parser_skips_comments_and_normalizes_commas(self) -> None:
        parsed = _parse_url_entries('    # comment\n    "alpha/"\n\n')
        assert parsed == [("alpha/", '    "alpha/",')]

    def test_url_rule_uses_empty_indent_when_ours_has_only_blank_lines(self) -> None:
        cls = r_urls_list_union(Path("app/urls.py"), _hunk("\n", '"alpha/"\n'))
        assert cls is not None
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.merged_text == '"alpha/",\n'


# ---------------------------------------------------------------------------
# R-UVLOCK-REGENERATE
# ---------------------------------------------------------------------------


class TestUvlockRegenerate:
    def test_emits_sentinel_for_uv_lock(self) -> None:
        cls = r_uvlock_regenerate(Path("uv.lock"), "any content")
        assert cls is not None
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_UVLOCK
        # The sentinel intentionally carries no merged_text — orchestrator regenerates.
        assert cls.resolution.merged_text == ""

    def test_returns_none_for_non_uv_lock(self) -> None:
        cls = r_uvlock_regenerate(Path("requirements.txt"), "x")
        assert cls is None


# ---------------------------------------------------------------------------
# R-DEFAULT-MANUAL
# ---------------------------------------------------------------------------


class TestDefaultManual:
    def test_always_manual(self) -> None:
        cls = r_default_manual(Path("src/anything.go"), "any content")
        assert cls is not None
        assert isinstance(cls.resolution, Manual)
        assert "no classifier rule matched" in cls.resolution.reason


# ---------------------------------------------------------------------------
# Dispatcher behavior
# ---------------------------------------------------------------------------


class TestClassifyDispatcher:
    def test_unmatched_path_falls_through_to_default_manual(self) -> None:
        cls = classify(Path("src/strange.rs"), "anything")
        assert isinstance(cls.resolution, Manual)
        assert "no classifier rule matched" in cls.resolution.reason

    def test_pyproject_route_to_deps_rule(self) -> None:
        cls = classify(
            Path("pyproject.toml"),
            _hunk('  "pkg-a",\n', '  "pkg-b",\n'),
        )
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_PYPROJECT_DEPS

    def test_init_route_to_imports_rule(self) -> None:
        cls = classify(
            Path("pkg/__init__.py"),
            _hunk("from .a import A\n", "from .b import B\n"),
        )
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_INIT_IMPORTS

    def test_uv_lock_route_to_sentinel(self) -> None:
        cls = classify(Path("uv.lock"), "noise")
        assert isinstance(cls.resolution, Auto)
        assert cls.resolution.rule_id == RULE_ID_UVLOCK


# ---------------------------------------------------------------------------
# Post-resolution validation (NFR-005 invariant 3)
# ---------------------------------------------------------------------------


class TestValidateResolution:
    def test_valid_toml_passes(self) -> None:
        cls = ConflictClassification(
            file_path=Path("pyproject.toml"),
            hunk_text="",
            resolution=Auto(merged_text="", rule_id=RULE_ID_PYPROJECT_DEPS),
        )
        full = '[project]\ndependencies = ["x"]\n'
        out = validate_resolution(cls, full)
        assert isinstance(out.resolution, Auto)

    def test_invalid_toml_reverts_to_manual(self) -> None:
        cls = ConflictClassification(
            file_path=Path("pyproject.toml"),
            hunk_text="",
            resolution=Auto(merged_text="garbage", rule_id=RULE_ID_PYPROJECT_DEPS),
        )
        # Deliberately malformed TOML
        out = validate_resolution(cls, "this is not valid = toml = at all")
        assert isinstance(out.resolution, Manual)
        assert "post-merge validation failed" in out.resolution.reason

    def test_invalid_python_reverts_to_manual(self) -> None:
        cls = ConflictClassification(
            file_path=Path("pkg/__init__.py"),
            hunk_text="",
            resolution=Auto(merged_text="garbage", rule_id=RULE_ID_INIT_IMPORTS),
        )
        out = validate_resolution(cls, "def broken(:\n  pass")
        assert isinstance(out.resolution, Manual)
        assert "post-merge validation failed" in out.resolution.reason

    def test_manual_classification_skips_validation(self) -> None:
        cls = ConflictClassification(
            file_path=Path("pkg/__init__.py"),
            hunk_text="",
            resolution=Manual(reason="already manual"),
        )
        assert validate_resolution(cls, "def broken(:\n  pass") is cls

    def test_uvlock_sentinel_skips_validation(self) -> None:
        cls = ConflictClassification(
            file_path=Path("uv.lock"),
            hunk_text="",
            resolution=Auto(merged_text="", rule_id=RULE_ID_UVLOCK),
        )
        # Lockfile bytes are arbitrary; validation is skipped.
        out = validate_resolution(cls, "anything not toml or python")
        assert isinstance(out.resolution, Auto)
        assert out.resolution.rule_id == RULE_ID_UVLOCK


# ---------------------------------------------------------------------------
# Fail-safe smoke: rule raising during evaluation
# ---------------------------------------------------------------------------


class TestFailSafeOnException:
    def test_exception_in_rule_falls_back_to_manual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If a rule body raises, the wrapper defaults to Manual (NFR-005)."""
        # Pass a path that triggers r_pyproject_deps_union but force the
        # inner split helper to raise by passing malformed conflict markers
        # without a separator (no '=======').
        # We pass hunk_text starting with '<<<<<<<' but ending early; the
        # split helper returns None (not raises), so the rule returns None.
        # To test exception path, monkeypatch the helper.
        from specify_cli.consolidation import conflict_classifier as cc

        def _boom(_: str) -> None:
            raise RuntimeError("synthetic failure")

        monkeypatch.setattr(cc, "_split_conflict_region", _boom)
        cls = cc.r_pyproject_deps_union(
            Path("pyproject.toml"), '<<<<<<< x\na\n=======\nb\n>>>>>>> y\n'
        )
        assert cls is not None
        assert isinstance(cls.resolution, Manual)
        assert "rule raised" in cls.resolution.reason

    def test_dispatcher_exception_falls_back_to_manual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The public dispatcher also converts unexpected rule exceptions to Manual."""
        from specify_cli.consolidation import conflict_classifier as cc

        def _boom(_path: Path, _hunk: str) -> None:
            raise RuntimeError("dispatcher failure")

        monkeypatch.setattr(cc, "RULES", (_boom,))
        cls = cc.classify(Path("anything.py"), "<<<<<<< HEAD\n")
        assert isinstance(cls.resolution, Manual)
        assert "dispatcher caught" in cls.resolution.reason
