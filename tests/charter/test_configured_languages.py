"""One operator-confirmed language list in ``.kittify/config.yaml`` governs evidence and scoping (#6444, FR-020, SC-006)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.interview import CharterInterview, apply_answer_overrides, default_interview
from charter.activation.language_authority import configured_languages, write_configured_languages
from charter.activation.language_scope import infer_repo_languages
from charter.activation.synthesizer.interview_mapping import normalize_interview_snapshot, resolve_sections
from charter.offering.shared.scoping import applies_to_languages_match

pytestmark = [pytest.mark.fast, pytest.mark.regression]


def _touch(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _config(root: Path, text: str) -> None:
    _touch(root, ".kittify/config.yaml", text)


def _tooling_package_json_repo(root: Path) -> Path:
    """A Python project whose root ``package.json`` is tooling only, with JS config files."""
    _touch(root, "pyproject.toml", "[project]\nname='x'\n")
    _touch(root, "package.json", "{}")
    _touch(root, "eslint.config.js")
    _touch(root, "commitlint.config.js")
    _touch(root, "src/app.py", "x = 1\n")
    return root


def _interview(answer: str) -> CharterInterview:
    return apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": answer},
    )


def _scope_targets(snapshot: dict[str, Any]) -> list[str]:
    return [context["language"] for section, context in resolve_sections(snapshot) if section == "language_scope"]


# -- evidence ---------------------------------------------------------------


def test_configured_list_is_the_evidence_languages(tmp_path: Path) -> None:
    _tooling_package_json_repo(tmp_path)
    assert CodeReadingCollector(tmp_path).collect().primary_language == "javascript"  # the heuristic alone is wrong here
    _config(tmp_path, "languages:\n- python\n")

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.languages == ("python",)
    assert signals.primary_language == "python"
    assert signals.scope_tag == "python"


def test_configured_primary_is_the_first_entry_and_skips_the_source_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(tmp_path, "build.gradle.kts")
    _config(tmp_path, "languages: [typescript, python]\n")

    def _boom(_root: Path) -> None:
        raise AssertionError("the uncapped source count must not run when languages are configured (NFR-005)")

    monkeypatch.setattr("charter.activation.evidence.code_reader.count_sources_uncapped", _boom)

    signals = CodeReadingCollector(tmp_path).collect()

    assert signals.languages == ("typescript", "python")
    assert signals.primary_language == "typescript"


def test_absent_key_keeps_detection(tmp_path: Path) -> None:
    _tooling_package_json_repo(tmp_path)
    _config(tmp_path, "vcs:\n  type: git\n")

    assert configured_languages(tmp_path) is None
    assert CodeReadingCollector(tmp_path).collect().primary_language == "javascript"


# -- doctrine scoping -------------------------------------------------------


def test_configured_list_wins_over_interview_free_text(tmp_path: Path) -> None:
    _tooling_package_json_repo(tmp_path)
    _config(tmp_path, "languages:\n- python\n")
    interview = _interview("TypeScript and Node")

    assert infer_repo_languages(tmp_path, interview=interview) == ["python"]
    assert infer_repo_languages(tmp_path, interview=interview, prefer_interview=True) == ["python"]
    assert infer_repo_languages(tmp_path) == ["python"]


def test_configured_list_wins_over_the_compiled_catalog(tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8") as handle:
        YAML().dump({"schema_version": "2.0.0", "catalog": {"languages": ["javascript"]}}, handle)
    _config(tmp_path, "languages: [python]\n")

    assert infer_repo_languages(tmp_path) == ["python"]


def test_absent_key_keeps_free_text_fallback(tmp_path: Path) -> None:
    assert infer_repo_languages(tmp_path, interview=_interview("TypeScript")) == ["typescript"]


def test_family_tagged_artifact_matches_a_configured_member(tmp_path: Path) -> None:
    _config(tmp_path, "languages: [kotlin]\n")

    active = infer_repo_languages(tmp_path)

    assert active == ["kotlin"]
    assert applies_to_languages_match(["jvm"], active)
    assert "jvm" not in (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")


# -- validation -------------------------------------------------------------


def test_read_drops_invalid_entries_with_a_diagnostic_and_keeps_valid_ones(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _config(tmp_path, "languages: [Python, jvm, cobol, python, '']\n")

    with caplog.at_level(logging.WARNING, logger="charter.activation.language_authority"):
        assert configured_languages(tmp_path) == ("python",)

    text = caplog.text
    assert "jvm" in text and "cobol" in text


def test_read_of_only_invalid_entries_falls_back_to_detection(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _config(tmp_path, "languages: [jvm]\n")

    with caplog.at_level(logging.WARNING, logger="charter.activation.language_authority"):
        assert configured_languages(tmp_path) is None
        assert infer_repo_languages(tmp_path, interview=_interview("TypeScript")) == ["typescript"]

    assert "jvm" in caplog.text


@pytest.mark.parametrize("text", ["languages: python\n", "languages: []\n", "languages:\n", "languages: [1, {a: b}]\n", "languages: [unclosed\n"])
def test_unusable_values_read_as_absent(tmp_path: Path, text: str) -> None:
    _config(tmp_path, text)

    assert configured_languages(tmp_path) is None


@pytest.mark.parametrize("bad", [["jvm"], ["python", "cobol"], [], ["unknown"]])
def test_write_refuses_invalid_lists_and_leaves_the_file_alone(tmp_path: Path, bad: list[str]) -> None:
    _config(tmp_path, "vcs:\n  type: git\n")
    before = (tmp_path / ".kittify" / "config.yaml").read_bytes()

    with pytest.raises(ValueError, match=r"at least one language|cannot be stored"):
        write_configured_languages(tmp_path, bad)

    assert (tmp_path / ".kittify" / "config.yaml").read_bytes() == before


def test_write_preserves_other_keys_and_comments(tmp_path: Path) -> None:
    _config(tmp_path, "# top comment\nvcs:\n  type: git  # inline\ncharter: .kittify/charter/charter.yaml\n")

    write_configured_languages(tmp_path, ["Python", "kotlin", "python"])

    text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "# top comment" in text and "# inline" in text
    assert "charter: .kittify/charter/charter.yaml" in text
    assert configured_languages(tmp_path) == ("python", "kotlin")


def test_write_creates_the_config_when_missing(tmp_path: Path) -> None:
    write_configured_languages(tmp_path, ["go"])

    assert configured_languages(tmp_path) == ("go",)


# -- language_scope targets (review leftover a) ------------------------------


def test_language_scope_entries_go_through_the_language_authority() -> None:
    snapshot = normalize_interview_snapshot({"language_scope": ["Python 3.12", "go", "jvm", "n/a"]})

    assert snapshot["language_scope"] == ["python", "go"]
    assert _scope_targets(snapshot) == ["python", "go"]


def test_synthesis_request_carries_the_configured_list_as_language_scope(tmp_path: Path) -> None:
    from charter.activation.interview import write_interview_answers
    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    _tooling_package_json_repo(tmp_path)
    _config(tmp_path, "languages: [python]\n")
    interview = _interview("TypeScript, Node")
    answers = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True)
    write_interview_answers(answers, interview)

    request, _adapter = _build_synthesis_request(tmp_path, "fixture")

    snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    assert _scope_targets(snapshot) == ["python"]
