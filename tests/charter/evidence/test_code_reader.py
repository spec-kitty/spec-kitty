"""Tests for CodeReadingCollector.

Each test creates a synthetic project in tmp_path so the suite is
fully self-contained and does not depend on the real spec-kitty repo layout.
"""

from __future__ import annotations

import pytest

from charter.activation.evidence.code_reader import CodeReadingCollector, CodeReadingError
from tests._perf_helpers import assert_timing_budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

def _make_file(path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# Test 1: Python / Django / pytest project
# ---------------------------------------------------------------------------


def test_python_django_pytest(tmp_path):
    """Detect python+django+pytest from a canonical Django project layout."""
    _make_file(tmp_path / "pyproject.toml", "[tool.poetry]\nname = 'myapp'")
    _make_file(tmp_path / "manage.py", "#!/usr/bin/env python")
    _make_file(tmp_path / "conftest.py", "import pytest")
    _make_file(tmp_path / "myapp" / "views.py", "from django.http import HttpResponse")
    _make_file(tmp_path / "tests" / "test_views.py", "def test_index(): pass")

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.stack_id == "python+django+pytest"
    assert signals.primary_language == "python"
    assert signals.scope_tag == "python"
    assert "django" in signals.frameworks
    assert "pytest" in signals.test_frameworks


# ---------------------------------------------------------------------------
# Test 2: TypeScript / Next.js / Jest
# ---------------------------------------------------------------------------


def test_typescript_nextjs_jest(tmp_path):
    """Detect typescript+nextjs+jest from a Next.js project layout."""
    _make_file(tmp_path / "package.json", '{"name":"myapp"}')
    _make_file(tmp_path / "tsconfig.json", '{"compilerOptions":{}}')
    _make_file(tmp_path / "next.config.ts", "export default {};")
    _make_file(tmp_path / "jest.config.ts", "export default {};")
    _make_file(tmp_path / "src" / "index.ts", "export const x = 1;")
    _make_file(tmp_path / "__tests__" / "index.test.ts", "test('x', () => {});")

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.stack_id == "typescript+nextjs+jest"
    assert signals.primary_language == "typescript"
    assert "nextjs" in signals.frameworks
    assert "jest" in signals.test_frameworks


# ---------------------------------------------------------------------------
# Test 3: Go project
# ---------------------------------------------------------------------------


def test_go_project(tmp_path):
    """Detect go from a minimal Go project."""
    _make_file(tmp_path / "go.mod", "module example.com/myapp\n\ngo 1.21")
    _make_file(tmp_path / "main.go", "package main\n\nfunc main() {}")

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "go"
    assert signals.stack_id == "go"


# ---------------------------------------------------------------------------
# Test 4: Unknown / empty directory
# ---------------------------------------------------------------------------


def test_unknown_empty_dir(tmp_path):
    """Empty directory returns unknown signals without raising."""
    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.stack_id == "unknown"
    assert signals.primary_language == "unknown"
    assert signals.frameworks == ()
    assert signals.test_frameworks == ()
    assert signals.representative_files == ()


# ---------------------------------------------------------------------------
# Test 5: Exclusion of node_modules
# ---------------------------------------------------------------------------


def test_node_modules_excluded(tmp_path):
    """Files inside node_modules must not appear in representative_files."""
    _make_file(tmp_path / "package.json", '{"name":"myapp"}')
    _make_file(tmp_path / "tsconfig.json", '{"compilerOptions":{}}')
    _make_file(tmp_path / "src" / "index.ts", "export const x = 1;")
    # Simulate a heavy transitive dependency that must NOT be walked
    _make_file(tmp_path / "node_modules" / "heavy.ts", "export const y = 2;")

    signals = CodeReadingCollector(tmp_path).collect()

    for f in signals.representative_files:
        assert "node_modules" not in f, (
            f"Expected node_modules to be excluded but found: {f}"
        )


# ---------------------------------------------------------------------------
# Test 6: Depth limit
# ---------------------------------------------------------------------------


def test_depth_limit(tmp_path):
    """A file at depth 4 must not appear when max_depth=3."""
    # depth 0: tmp_path
    # depth 1: level1/
    # depth 2: level1/level2/
    # depth 3: level1/level2/level3/
    # depth 4: level1/level2/level3/level4/  <- beyond limit
    _make_file(tmp_path / "pyproject.toml", "")
    deep_file = (
        tmp_path / "level1" / "level2" / "level3" / "level4" / "deep.py"
    )
    _make_file(deep_file, "# deep")

    signals = CodeReadingCollector(tmp_path, max_depth=3).collect()

    for f in signals.representative_files:
        assert "deep.py" not in f, (
            f"File beyond max_depth should not appear: {f}"
        )


# ---------------------------------------------------------------------------
# Test 7: Nonexistent root raises CodeReadingError
# ---------------------------------------------------------------------------


def test_nonexistent_root_raises(tmp_path):
    """Passing a path that does not exist must raise CodeReadingError."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(CodeReadingError):
        CodeReadingCollector(missing).collect()


# ---------------------------------------------------------------------------
# Test 8: Performance — 1 000 Python files in < 5 seconds
# ---------------------------------------------------------------------------


def _seed_1000_file_tree(tmp_path) -> None:
    """Spread 1 000 files across 3 levels (≤ max_depth) under *tmp_path*."""
    _make_file(tmp_path / "pyproject.toml", "")
    count = 0
    for level1 in range(10):
        for level2 in range(10):
            for level3 in range(10):
                f = tmp_path / f"pkg{level1}" / f"sub{level2}" / f"mod{level3}.py"
                _make_file(f, f"# {count}")
                count += 1


@pytest.mark.timeout(10)
def test_collect_detects_primary_language_on_a_1000_file_tree(tmp_path):
    """Functional companion to test_performance_1000_files (split, #4015):
    collect() correctly detects the primary language on a large tree. Timing
    budget lives in the @performance sibling below."""
    _seed_1000_file_tree(tmp_path)

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "python"


@pytest.mark.performance
@pytest.mark.timeout(10)
def test_performance_1000_files(tmp_path):
    """NFR timing budget only (split, #4015): collect() must complete in
    under 5 seconds on a 1 000-file tree. Functional coverage moved to
    test_collect_detects_primary_language_on_a_1000_file_tree, above."""
    import time

    _seed_1000_file_tree(tmp_path)

    start = time.monotonic()
    CodeReadingCollector(tmp_path).collect()
    elapsed = time.monotonic() - start

    assert_timing_budget(elapsed, 5.0, name="collect_1000_files")


# ---------------------------------------------------------------------------
# #6405: root-first stack detection
# ---------------------------------------------------------------------------


def _site_manifests(root) -> None:
    _make_file(root / "site" / "package.json", '{"name":"site"}')
    _make_file(root / "site" / "tsconfig.json", "{}")


def test_gradle_kts_root_with_nested_site_is_java(tmp_path):
    """Root Gradle Kotlin DSL build beats a nested docs-site package.json."""
    _make_file(tmp_path / "build.gradle.kts", "")
    _make_file(tmp_path / "settings.gradle.kts", "")
    _make_file(tmp_path / "gradlew", "#!/bin/sh")
    _make_file(tmp_path / "src" / "main" / "java" / "App.java", "class App {}")
    _site_manifests(tmp_path)

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "java"
    assert signals.scope_tag == "java"


def test_docs_only_site_is_still_typescript_control(tmp_path):
    """Positive control: with no root indicator the nested site still wins."""
    _site_manifests(tmp_path)

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "typescript"


@pytest.mark.parametrize(
    "indicators",
    [["build.gradle.kts"], ["settings.gradle"], ["gradlew"], ["mvnw"], ["pom.xml"]],
)
def test_jvm_indicators_resolve_java(tmp_path, indicators):
    for name in indicators:
        _make_file(tmp_path / name, "")
    _site_manifests(tmp_path)

    assert CodeReadingCollector(tmp_path).collect().primary_language == "java"


def test_root_pyproject_beats_deeply_nested_package_json(tmp_path):
    _make_file(tmp_path / "pyproject.toml", "")
    _make_file(tmp_path / "a" / "b" / "c" / "package.json", "{}")
    _make_file(tmp_path / "a" / "b" / "c" / "tsconfig.json", "{}")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "python"


def test_equal_depth_tie_broken_by_source_counts(tmp_path):
    _make_file(tmp_path / "pyproject.toml", "")
    _make_file(tmp_path / "package.json", "{}")
    for i in range(3):
        _make_file(tmp_path / "src" / f"m{i}.js", "")
    _make_file(tmp_path / "src" / "only.py", "")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "javascript"


def test_equal_depth_count_tie_uses_indicator_order(tmp_path):
    _make_file(tmp_path / "pyproject.toml", "")
    _make_file(tmp_path / "go.mod", "")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "python"


def test_nested_only_manifests_resolve_by_counts(tmp_path):
    _make_file(tmp_path / "svc" / "pyproject.toml", "")
    _make_file(tmp_path / "web" / "package.json", "{}")
    for i in range(3):
        _make_file(tmp_path / "svc" / f"m{i}.py", "")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "python"


def test_frameworks_still_detected_from_nested_files(tmp_path):
    _make_file(tmp_path / "pom.xml", "")
    _make_file(tmp_path / "web" / "next.config.js", "")
    _make_file(tmp_path / "web" / "jest.config.js", "")

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "java"
    assert "nextjs" in signals.frameworks
    assert "jest" in signals.test_frameworks


def test_root_package_json_beats_nested_android_gradle(tmp_path):
    """Root-first rule: a root package.json wins over a nested android/build.gradle (React Native shape)."""
    _make_file(tmp_path / "package.json", "{}")
    _make_file(tmp_path / "android" / "build.gradle", "")
    _make_file(tmp_path / "android" / "app" / "src" / "main" / "java" / "Main.java", "class Main {}")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "javascript"
