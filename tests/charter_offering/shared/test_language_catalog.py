"""Match-time family expansion over the one language catalog (#6444, FR-009, FR-013)."""

from __future__ import annotations

import pytest

from charter.offering.shared.language_catalog import (
    BUILD_TOOLS,
    LANGUAGES,
    expand_language_families,
    is_language_family,
    language_for_extension,
    languages_for_manifest,
)
from charter.offering.shared.scoping import applies_to_languages_match

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.regression]


@pytest.mark.parametrize("active", [["kotlin"], ["java"], ["jvm"], ["kotlin", "java"]])
def test_jvm_tagged_artifact_matches_jvm_languages(active: list[str]) -> None:
    assert applies_to_languages_match(["jvm"], active) is True


def test_java_tagged_artifact_does_not_match_kotlin() -> None:
    assert applies_to_languages_match(["java"], ["kotlin"]) is False


def test_kotlin_tagged_artifact_does_not_match_java() -> None:
    assert applies_to_languages_match(["kotlin"], ["java"]) is False


def test_family_token_active_does_not_imply_its_members() -> None:
    assert applies_to_languages_match(["kotlin"], ["jvm"]) is False
    assert applies_to_languages_match(["java"], ["jvm"]) is False


def test_non_jvm_language_does_not_match_jvm_artifact() -> None:
    assert applies_to_languages_match(["jvm"], ["python"]) is False


# -- the catalog itself --------------------------------------------------------


def test_expand_language_families_adds_the_family_once_in_stable_order() -> None:
    assert expand_language_families(["kotlin", "java", "python"]) == ("kotlin", "jvm", "java", "python")


def test_expand_language_families_is_case_and_whitespace_insensitive() -> None:
    assert expand_language_families([" Kotlin "]) == ("kotlin", "jvm")


def test_expand_language_families_leaves_families_and_unknown_tokens_alone() -> None:
    assert expand_language_families(["jvm", "zig"]) == ("jvm", "zig")
    assert expand_language_families([]) == ()


def test_family_is_not_a_language() -> None:
    assert is_language_family("jvm") is True
    assert is_language_family("JVM") is True
    assert is_language_family("kotlin") is False


def test_catalog_tokens_are_unique_and_include_kotlin() -> None:
    tokens = [spec.token for spec in LANGUAGES]

    assert len(tokens) == len(set(tokens))
    assert {"python", "javascript", "typescript", "java", "kotlin", "go", "rust", "ruby", "php", "swift"} == set(tokens)


def test_jvm_manifests_belong_to_java_and_kotlin_and_kt_is_kotlin() -> None:
    assert languages_for_manifest("build.gradle.kts") == ("java", "kotlin")
    assert languages_for_manifest("pom.xml") == ("java", "kotlin")
    assert languages_for_manifest("go.mod") == ("go",)
    assert languages_for_manifest("README.md") == ()
    assert language_for_extension(".kt") == "kotlin"
    assert language_for_extension(".java") == "java"
    assert language_for_extension(".md") is None


def test_build_tools_declare_only_the_jvm_family() -> None:
    assert {tool.token for tool in BUILD_TOOLS} == {"gradle", "maven", "junit"}
    assert {tool.family for tool in BUILD_TOOLS} == {"jvm"}
