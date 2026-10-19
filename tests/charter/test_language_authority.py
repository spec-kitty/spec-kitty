"""Language authority: one observed + declared vocabulary, kotlin token, jvm family (#6444, FR-009, FR-013)."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.interview import CharterInterview, apply_answer_overrides, default_interview
from charter.activation.language_authority import (
    EXCLUDED_DIRS,
    TreeObservation,
    count_sources_uncapped,
    declared_languages,
    expand_language_families,
    resolve_languages,
)
from charter.offering.shared.scoping import applies_to_languages_match
from charter.activation.language_scope import extract_declared_languages, infer_repo_languages, lacks_specialist_guidance

pytestmark = [pytest.mark.fast, pytest.mark.regression]


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")


def _gradle_repo(root: Path, *, kotlin: int, java: int) -> None:
    _touch(root / "build.gradle.kts")
    for i in range(kotlin):
        _touch(root / "src" / "main" / "kotlin" / "com" / "acme" / f"K{i}.kt")
    for i in range(java):
        _touch(root / "src" / "main" / "java" / "com" / "acme" / f"J{i}.java")


def _interview(answer: str) -> CharterInterview:
    return apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": answer},
    )


def _write_overlay(repo_root: Path, *, languages: list[str]) -> None:
    directory = repo_root / ".kittify" / "charter-packs" / "tactic"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "jvm-tactic.tactic.yaml").write_text(f"id: jvm-tactic\napplies_to_languages: [{', '.join(languages)}]\n", encoding="utf-8")


# -- observed ---------------------------------------------------------------


def test_gradle_repo_with_more_kotlin_sources_is_kotlin(tmp_path: Path) -> None:
    _gradle_repo(tmp_path, kotlin=5, java=2)

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.primary_language == "kotlin"
    assert signals.scope_tag == "kotlin"
    assert signals.stack_id.startswith("kotlin")


def test_gradle_repo_with_more_java_sources_is_java(tmp_path: Path) -> None:
    _gradle_repo(tmp_path, kotlin=2, java=5)

    assert CodeReadingCollector(tmp_path).collect().primary_language == "java"


def test_maven_repo_with_kotlin_sources_is_kotlin(tmp_path: Path) -> None:
    _touch(tmp_path / "pom.xml")
    for i in range(3):
        _touch(tmp_path / "src" / "main" / "kotlin" / f"K{i}.kt")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "kotlin"


def test_jvm_source_tie_stays_java(tmp_path: Path) -> None:
    _gradle_repo(tmp_path, kotlin=3, java=3)

    assert CodeReadingCollector(tmp_path).collect().primary_language == "java"


def test_kotlin_majority_beats_root_package_json_tie(tmp_path: Path) -> None:
    _touch(tmp_path / "build.gradle.kts")
    _touch(tmp_path / "package.json")
    for i in range(4):
        _touch(tmp_path / "src" / "main" / "kotlin" / f"K{i}.kt")

    assert CodeReadingCollector(tmp_path).collect().primary_language == "kotlin"


# -- declared ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kotlin and Spring", ["kotlin"]),
        ("Kotlin, Gradle, JUnit", ["kotlin"]),
        ("Gradle", ["jvm"]),
        ("Maven and JUnit", ["jvm"]),
        ("Java, Gradle", ["java"]),
        ("Java 21 with Gradle", ["java"]),
    ],
)
def test_declared_languages_apply_the_build_token_rule(text: str, expected: list[str]) -> None:
    assert extract_declared_languages(text) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("Kotlin and Spring", ["kotlin"]), ("Kotlin, Gradle, JUnit", ["kotlin"]), ("Gradle", ["jvm"]), ("Java, Gradle", ["java"])],
)
def test_infer_repo_languages_resolves_declared_jvm_answers(answer: str, expected: list[str]) -> None:
    assert infer_repo_languages(None, interview=_interview(answer)) == expected


# -- lacks_specialist_guidance expands families before intersecting -----------


@pytest.mark.parametrize("active", [["kotlin"], ["java"]])
def test_jvm_scoped_doctrine_counts_as_guidance_for_a_jvm_language(tmp_path: Path, active: list[str]) -> None:
    _write_overlay(tmp_path, languages=["jvm"])

    assert lacks_specialist_guidance(active, tmp_path) is False


def test_java_scoped_doctrine_is_not_guidance_for_kotlin() -> None:
    """Asserted at the matching seam, independent of the shipped doctrine (whose jvm toolguides do guide Kotlin)."""
    assert applies_to_languages_match(["java"], ["kotlin"]) is False
    assert applies_to_languages_match(["jvm"], ["kotlin"]) is True, "control: a jvm-tagged artifact is guidance for kotlin"


# -- the authority itself ------------------------------------------------------


def _primary(root: Path) -> str:
    return CodeReadingCollector(root).collect().primary_language


def test_collector_walks_the_tree_once_without_a_jvm_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-005: the collector's single scan feeds the authority; no extra count without a JVM manifest or tie."""
    _touch(tmp_path / "pyproject.toml")
    walks: list[str] = []
    real_walk = os.walk

    def _spy(top: str) -> Iterator[tuple[str, list[str], list[str]]]:
        walks.append(top)
        return real_walk(top)

    monkeypatch.setattr(os, "walk", _spy)

    assert _primary(tmp_path) == "python"
    assert len(walks) == 1


def test_collector_counts_sources_only_when_a_jvm_manifest_is_present(tmp_path: Path) -> None:
    _gradle_repo(tmp_path, kotlin=2, java=1)

    assert _primary(tmp_path) == "kotlin"


def test_jvm_split_reads_sources_below_the_scan_depth(tmp_path: Path) -> None:
    _touch(tmp_path / "pom.xml")
    for i in range(3):
        _touch(tmp_path / "src" / "main" / "kotlin" / "com" / "acme" / "deep" / f"K{i}.kt")

    assert CodeReadingCollector(tmp_path, max_depth=1).collect().primary_language == "kotlin"


def test_single_non_jvm_manifest_never_pays_for_the_uncapped_walk() -> None:
    observation = TreeObservation(indicator_depths={"Cargo.toml": 0})

    def _boom() -> Counter[str]:
        raise AssertionError("source counting must not run for a single non-JVM manifest")

    assert resolve_languages(observation, _boom).primary == "rust"
    assert resolve_languages(TreeObservation(), _boom).primary == "unknown"


def test_kotlin_sources_without_a_jvm_manifest_do_not_make_a_kotlin_repo(tmp_path: Path) -> None:
    _touch(tmp_path / "pyproject.toml")
    for i in range(5):
        _touch(tmp_path / "scripts" / f"K{i}.kt")

    assert _primary(tmp_path) == "python"


def test_typescript_package_json_is_still_typescript(tmp_path: Path) -> None:
    _touch(tmp_path / "package.json")
    _touch(tmp_path / "tsconfig.json")

    assert _primary(tmp_path) == "typescript"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Python and TypeScript", ["python", "typescript"]),
        ("Rust with cargo", ["rust"]),
        ("librespot-java", []),
        ("Java-based backend", ["java"]),
        ("Kotlin or Java", ["java", "kotlin"]),
        ("", []),
    ],
)
def test_declared_languages(text: str, expected: list[str]) -> None:
    assert declared_languages(text) == expected


def test_families_are_never_persisted_for_a_declared_language() -> None:
    assert "jvm" not in declared_languages("Kotlin, Gradle, JUnit, Maven")
    assert expand_language_families(declared_languages("Kotlin")) == ("kotlin", "jvm")


# -- declared order is preserved for non-JVM answers (persisted via the unsorted fallback) --


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("TypeScript and Rust", ["typescript", "rust"]),
        ("JavaScript, Rust", ["javascript", "rust"]),
        ("React with Node.js and TypeScript", ["typescript", "javascript"]),
        ("Swift, PHP", ["swift", "php"]),
        ("Rails and PHP", ["ruby", "php"]),
        ("Swift and Ruby", ["swift", "ruby"]),
        ("Java and Python", ["python", "java"]),
        ("Gradle and Python", ["python", "jvm"]),
    ],
)
def test_declared_order_matches_the_pre_catalog_pattern_order(text: str, expected: list[str]) -> None:
    assert extract_declared_languages(text) == expected


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ({"testing_philosophy": "jest + tsc + pytest"}, ["python", "typescript", "javascript"]),
        ({"project_description": "Swift app, PHP backend"}, ["swift", "php"]),
    ],
)
def test_unsorted_fallback_keeps_declared_order(answers: dict[str, str], expected: list[str]) -> None:
    interview = apply_answer_overrides(default_interview(mission="software-dev", profile="minimal"), answers=answers)

    assert infer_repo_languages(None, interview=interview) == expected


_TOOL_DIRS = (
    ".kittify",
    ".claude",
    ".agents",
    ".codex",
    ".gemini",
    ".cursor",
    ".qwen",
    ".opencode",
    ".windsurf",
    ".kilocode",
    ".augment",
    ".amazonq",
    ".kiro",
    ".agent",
    ".llxprt",
    ".vibe",
    ".worktrees",
)


def _kotlin_ts_repo(root: Path) -> None:
    _touch(root / "build.gradle.kts")
    _touch(root / "package.json")
    for i in range(3):
        _touch(root / "src" / "main" / "kotlin" / f"K{i}.kt")
        _touch(root / "web" / f"c{i}.ts")


def test_tool_directories_do_not_make_a_python_repo(tmp_path: Path) -> None:
    _kotlin_ts_repo(tmp_path)
    for tool_dir in _TOOL_DIRS:
        _touch(tmp_path / tool_dir / "missions" / "built_in_step_contracts" / "__init__.py")
        _touch(tmp_path / tool_dir / "scripts" / "helper.py")

    observed = CodeReadingCollector(tmp_path).collect()

    assert "python" not in observed.languages
    assert {"kotlin", "typescript"} <= set(observed.languages), "control: the real languages are still listed"
    assert "python" not in count_sources_uncapped(tmp_path)
    assert count_sources_uncapped(tmp_path)["kotlin"] == 3, "control: real sources are still counted"


@pytest.mark.parametrize("tool_dir", _TOOL_DIRS)
def test_every_tool_directory_is_excluded(tool_dir: str) -> None:
    assert tool_dir in EXCLUDED_DIRS
