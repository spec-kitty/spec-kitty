"""Language authority: one observed + declared vocabulary, kotlin token, jvm family (#6444, FR-009, FR-013)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.interview import CharterInterview, apply_answer_overrides, default_interview
from charter.activation.language_authority import (
    TreeObservation,
    declared_languages,
    expand_language_families,
    observe_primary_language,
    resolve_primary_language,
)
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


def test_java_scoped_doctrine_is_not_guidance_for_kotlin(tmp_path: Path) -> None:
    _write_overlay(tmp_path, languages=["java"])

    assert lacks_specialist_guidance(["kotlin"], tmp_path) is True


# -- the authority itself ------------------------------------------------------


def test_observe_primary_language_matches_the_collector(tmp_path: Path) -> None:
    _gradle_repo(tmp_path, kotlin=2, java=1)

    assert observe_primary_language(tmp_path) == "kotlin"
    assert observe_primary_language(tmp_path / "missing") == "unknown"


def test_jvm_split_reads_sources_below_the_scan_depth(tmp_path: Path) -> None:
    _touch(tmp_path / "pom.xml")
    for i in range(3):
        _touch(tmp_path / "src" / "main" / "kotlin" / "com" / "acme" / "deep" / f"K{i}.kt")

    assert observe_primary_language(tmp_path, max_depth=1) == "kotlin"


def test_single_non_jvm_manifest_never_pays_for_the_uncapped_walk() -> None:
    observation = TreeObservation(indicator_depths={"Cargo.toml": 0})

    def _boom() -> Counter[str]:
        raise AssertionError("source counting must not run for a single non-JVM manifest")

    assert resolve_primary_language(observation, _boom) == "rust"
    assert resolve_primary_language(TreeObservation(), _boom) == "unknown"


def test_kotlin_sources_without_a_jvm_manifest_do_not_make_a_kotlin_repo(tmp_path: Path) -> None:
    _touch(tmp_path / "pyproject.toml")
    for i in range(5):
        _touch(tmp_path / "scripts" / f"K{i}.kt")

    assert observe_primary_language(tmp_path) == "python"


def test_typescript_package_json_is_still_typescript(tmp_path: Path) -> None:
    _touch(tmp_path / "package.json")
    _touch(tmp_path / "tsconfig.json")

    assert observe_primary_language(tmp_path) == "typescript"


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
