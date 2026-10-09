"""Tests for deriving active languages from charter inputs."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.interview import (
    CharterInterview,
    apply_answer_overrides,
    default_interview,
    write_interview_answers,
)
from charter.activation.language_scope import extract_declared_languages, infer_repo_languages, lacks_specialist_guidance

pytestmark = pytest.mark.fast


def _write_charter_yaml(repo_root: Path, *, languages: list[str] | None) -> None:
    """Write a minimal ``charter.yaml`` fixture, optionally with ``catalog.languages``.

    Passing ``languages=None`` omits the ``catalog`` section's ``languages``
    key entirely, simulating a charter compiled before this field existed
    (the FR-010 backward-compat shape).
    """
    charter_yaml_path = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    catalog: dict[str, object] = {
        "mission": "software-dev",
        "template_set": "default",
        "references": [],
    }
    if languages is not None:
        catalog["languages"] = languages
    payload: dict[str, object] = {
        "schema_version": "2.0.0",
        "catalog": catalog,
    }

    yaml = YAML()
    yaml.default_flow_style = False
    with charter_yaml_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def test_extract_declared_languages_deduplicates_alias_hits() -> None:
    languages = extract_declared_languages(
        "Python services with pytest and ruff. TypeScript frontend built with tsc."
    )

    assert languages == ["python", "typescript"]


def test_infer_repo_languages_prefers_compiled_charter_over_stale_interview(tmp_path: Path) -> None:
    """The compiled charter's structured field wins even when the interview transcript disagrees.

    This is the corrected (charter-authoritative) contract for the test that
    used to be named ``test_infer_repo_languages_prefers_interview_answers``
    and pinned the opposite (buggy) precedence. Confirmed red-first: this
    exact scenario (interview says "python", compiled charter says
    "typescript") passed with `infer_repo_languages(tmp_path) == ["python"]`
    against the pre-fix code — proof the old precedence was interview-first.
    """
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)

    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )
    write_interview_answers(answers_path, interview)

    # A charter.md that disagrees with everything (WP08: must never be read
    # to resolve languages — its presence/content is irrelevant here).
    (tmp_path / ".kittify" / "charter" / "charter.md").write_text(
        "JavaScript only",
        encoding="utf-8",
    )

    # Compiled charter disagrees with both the interview transcript ("python")
    # and the never-read charter.md free text ("javascript") — it must win
    # regardless.
    _write_charter_yaml(tmp_path, languages=["typescript"])

    assert infer_repo_languages(tmp_path) == ["typescript"]


def test_infer_repo_languages_reads_structured_field_without_consulting_interview(tmp_path: Path) -> None:
    """The structured field is returned directly; no interview transcript exists at all."""
    _write_charter_yaml(tmp_path, languages=["rust", "go"])

    # `go` is not in the recognized alias set and normalize_languages passes
    # unknown tokens through unchanged, so it round-trips as-is.
    assert infer_repo_languages(tmp_path) == ["rust", "go"]


def test_infer_repo_languages_empty_compiled_list_is_authoritative_not_absent(tmp_path: Path) -> None:
    """``languages: []`` in compiled charter is authoritative — must NOT fall back to interview/charter.md.

    Kills the mutation: replacing ``if compiled_languages is not None:`` with
    ``if compiled_languages:`` would cause this test to fall back to a
    charter.md scan and return ``["java"]`` instead of ``[]``.
    """
    # Write a charter.md that would produce a non-empty result IF it were
    # ever read (WP08: it must not be — no fallback reaches it any more).
    charter_path = tmp_path / ".kittify" / "charter" / "charter.md"
    charter_path.parent.mkdir(parents=True, exist_ok=True)
    charter_path.write_text("This repository uses Java and Maven.", encoding="utf-8")

    # Compiled charter says "no languages" — this must win over any fallback.
    _write_charter_yaml(tmp_path, languages=[])

    assert infer_repo_languages(tmp_path) == []


def test_infer_repo_languages_returns_none_without_inputs(tmp_path: Path) -> None:
    """No compiled charter, no interview transcript: truly no signal -> ``None``.

    ``None`` (not ``[]``) is load-bearing here (regression fix,
    charter-sole-door-bypass-closure-01KZ3WAA landing fold):
    ``charter.offering.shared.scoping.applies_to_languages_match`` treats ``None`` as
    admit-all for scoped artifacts and ``[]`` as admit-none. This test used
    to assert ``== []`` before the fix, which silently dropped every
    language-scoped built-in profile from a bare project's catalog.
    """
    assert infer_repo_languages(tmp_path) is None


def test_infer_repo_languages_falls_back_when_compiled_charter_predates_structured_field(
    tmp_path: Path,
) -> None:
    """FR-010 backward compatibility: a charter.yaml without ``catalog.languages``.

    This is the compiled-charter shape produced before this field existed.
    Resolution must fall back to interview-transcript extraction (tier-2) —
    it must NOT fall back to a charter.md free-text read, which no longer
    exists as a resolution path (WP08 / FR-009).
    """
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)

    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )
    write_interview_answers(answers_path, interview)

    # A charter.md that disagrees with the interview ("javascript" vs
    # "python") — proves it is never consulted, only the interview is.
    (tmp_path / ".kittify" / "charter" / "charter.md").write_text(
        "JavaScript only",
        encoding="utf-8",
    )

    # charter.yaml exists (charter was compiled) but predates the
    # catalog.languages field — no "languages" key under "catalog" at all.
    _write_charter_yaml(tmp_path, languages=None)

    assert infer_repo_languages(tmp_path) == ["python"]


def test_infer_repo_languages_returns_none_when_no_compiled_charter_and_no_interview(
    tmp_path: Path,
) -> None:
    """No charter.yaml, no interview transcript: resolves to ``None`` — NOT a charter.md scan.

    This is the INV-3 completeness assertion (reviewer guidance): a
    charter.md that would produce a non-empty result via free-text
    extraction must be proven irrelevant. Prior to WP08 this scenario fell
    back to scanning charter.md and returned ``["java"]``; now there is no
    tier-3 charter.md read at all.

    ``None`` (not ``[]``) is load-bearing (regression fix,
    charter-sole-door-bypass-closure-01KZ3WAA landing fold): this is the
    "truly no signal at all" bare-project case, distinct from a configured
    project's deliberate empty answer. Before the fix this resolved to
    ``[]``, which ``charter.offering.shared.scoping.applies_to_languages_match``
    treats as admit-none — silently dropping every language-scoped built-in
    profile from a bare project's catalog.
    """
    charter_path = tmp_path / ".kittify" / "charter" / "charter.md"
    charter_path.parent.mkdir(parents=True, exist_ok=True)
    charter_path.write_text("This repository uses Java, Maven, and JUnit.", encoding="utf-8")

    assert infer_repo_languages(tmp_path) is None


def test_infer_repo_languages_falls_back_when_charter_yaml_is_malformed(tmp_path: Path) -> None:
    """A malformed/unparseable charter.yaml must degrade to the interview
    fallback rather than hard-failing language resolution, and must NOT
    reach a charter.md read (no such path exists any more)."""
    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    # Unterminated flow sequence — raises ruamel YAMLError on load.
    charter_yaml_path.write_text("catalog:\n  languages: [unterminated\n", encoding="utf-8")

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )
    write_interview_answers(answers_path, interview)

    (tmp_path / ".kittify" / "charter" / "charter.md").write_text(
        "This repository uses Java, Maven, and JUnit.",
        encoding="utf-8",
    )

    assert infer_repo_languages(tmp_path) == ["python"]


def test_infer_repo_languages_falls_back_when_languages_field_is_not_a_list(tmp_path: Path) -> None:
    """A ``languages`` field that is present but not a list is treated as absent
    (fall back), never coerced — a malformed compiled field must not win."""
    _write_charter_yaml(tmp_path, languages=[])
    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        "schema_version: '2.0.0'\ncatalog:\n  languages: python\n",
        encoding="utf-8",
    )

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )
    write_interview_answers(answers_path, interview)

    assert infer_repo_languages(tmp_path) == ["python"]


def test_infer_repo_languages_ignores_charter_md_content_entirely(tmp_path: Path) -> None:
    """INV-3 completeness (reviewer guidance): no charter.md content, in any
    shape, ever changes the resolved language set — with or without a
    compiled charter.yaml or an interview transcript present."""
    charter_path = tmp_path / ".kittify" / "charter" / "charter.md"
    charter_path.parent.mkdir(parents=True, exist_ok=True)
    charter_path.write_text("Rust, Ruby, PHP, Swift — every language at once.", encoding="utf-8")

    _write_charter_yaml(tmp_path, languages=["python"])

    assert infer_repo_languages(tmp_path) == ["python"]


def test_characterization_compiled_empty_list_beats_interview_override(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): compiled ``[]`` stays authoritative over an interview."""
    _write_charter_yaml(tmp_path, languages=[])
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust with cargo"},
    )

    assert infer_repo_languages(tmp_path, interview=interview) == []


def test_characterization_absent_compiled_field_uses_interview_override(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): absent compiled field falls through to the interview."""
    _write_charter_yaml(tmp_path, languages=None)
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust with cargo"},
    )

    assert infer_repo_languages(tmp_path, interview=interview) == ["rust"]


# ---------------------------------------------------------------------------
# WP03 (#5284 #4613 #4614): unknown detection, hyphen rule, precedence
# ---------------------------------------------------------------------------

_DEFAULTS_KEY = "languages_frameworks"


def _interview(answer: object, **extra: object) -> CharterInterview:
    """Build an in-memory interview exactly as ``answers.yaml`` round-trips it (``str(v)`` per answer)."""
    return CharterInterview.from_dict({"answers": {_DEFAULTS_KEY: answer, **extra}})


def _packaged_default_answer() -> str:
    import importlib.resources

    text = importlib.resources.files("charter").joinpath("defaults.yaml").read_text(encoding="utf-8")
    return str(YAML(typ="safe").load(text)["answers"][_DEFAULTS_KEY])


def _write_overlay_artifact(repo_root: Path, *, kind_dir: str, name: str, languages: list[str]) -> None:
    directory = repo_root / ".kittify" / "charter-packs" / kind_dir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.{kind_dir}.yaml").write_text(
        f"id: {name}\napplies_to_languages: {languages!r}\n".replace("'", ""),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Zig 0.16.0 is the primary implementation language",
        ["Zig", "C"],
        "Django",
    ],
)
def test_unrecognised_declaration_resolves_to_unknown(answer: object) -> None:
    """RED (pins the fix): a real declaration naming no recognised language is ``["unknown"]``."""
    assert infer_repo_languages(None, interview=_interview(answer)) == ["unknown"]


@pytest.mark.parametrize(
    "answer",
    ["", [], None, "N/A", "na", "none", "TBD", "any", "language-agnostic", "unknown", "-", "[NEEDS CLARIFICATION: which?]"],
)
def test_placeholder_declaration_resolves_to_none(answer: object) -> None:
    """GREEN control (pins unchanged behaviour): placeholders are no signal, never ``unknown``."""
    assert infer_repo_languages(None, interview=_interview(answer)) is None


@pytest.mark.parametrize("answer", [["unknown"], ["N/A"], "['any']"])
def test_list_shaped_placeholder_resolves_to_none(answer: object) -> None:
    """GREEN control (pins unchanged behaviour): list-repr placeholders must not become ``unknown``."""
    assert infer_repo_languages(None, interview=_interview(answer)) is None


def test_shipped_default_answer_resolves_to_none() -> None:
    """GREEN control (pins unchanged behaviour, #3292): the shipped default text is no signal."""
    assert infer_repo_languages(None, interview=_interview(_packaged_default_answer())) is None


def test_default_answer_plus_zig_in_other_prose_resolves_to_none() -> None:
    """GREEN control: free prose in another answer can only ADD recognised languages, never signal unknown."""
    interview = _interview(_packaged_default_answer(), project_intent="Port the tool to Zig")

    assert infer_repo_languages(None, interview=interview) is None


def test_recognised_language_wins_over_unrecognised() -> None:
    """GREEN control: "Python and Zig" resolves to python only (no unknown)."""
    assert infer_repo_languages(None, interview=_interview("Python and Zig")) == ["python"]


def test_doctrine_derived_vocabulary_recognises_overlay_language(tmp_path: Path) -> None:
    """RED (pins the fix, FR-017/C-001): a language scoped only by a project-overlay artifact is recognised."""
    _write_overlay_artifact(tmp_path, kind_dir="tactic", name="elixir-tactic", languages=["elixir"])

    assert infer_repo_languages(tmp_path, interview=_interview("Elixir 1.17")) == ["elixir"]


def test_overlay_language_absent_means_unknown(tmp_path: Path) -> None:
    """RED (pins the fix): without the overlay artifact the same answer is unknown."""
    assert infer_repo_languages(tmp_path, interview=_interview("Elixir 1.17")) == ["unknown"]


def test_html_with_zig_resolves_to_html() -> None:
    """RED (pins the fix): ``html`` is scoped by a shipped profile, so it is recognised; Zig is ignored."""
    assert infer_repo_languages(None, interview=_interview("HTML with Zig")) == ["html"]


def test_c_sharp_style_tokens_are_out_of_scope_and_resolve_to_unknown() -> None:
    """RED (pins the fix): only whole words are tokenised; ``C#`` is not a word and resolves to unknown."""
    assert infer_repo_languages(None, interview=_interview("C#")) == ["unknown"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Java-based backend", ["java"]),
        ("Python-based services", ["python"]),
        ("Java 21 with Gradle", ["java"]),
        ("librespot-java", []),
        ("my-python-thing", []),
    ],
)
def test_hyphen_prefix_rule(text: str, expected: list[str]) -> None:
    """Mixed: ``librespot-java``/``my-python-thing`` RED (no longer match); trailing compounds are GREEN controls."""
    assert extract_declared_languages(text) == expected


# ---------------------------------------------------------------------------
# Operator decision D1 (2026-09-29): a real languages/frameworks declaration wins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "extra", "expected"),
    [
        ("Zig", {"quality_standards": "each node in the build graph is cached"}, ["unknown"]),
        ("Zig", {"testing_requirements": "pytest for helper scripts"}, ["unknown"]),
        ("Python and Twig", {}, ["python", "twig"]),
        ("Rust with cargo", {"testing_requirements": "pytest for helper scripts"}, ["rust"]),
        ("Django", {"testing_requirements": "pytest"}, ["unknown"]),
        ("Python", {}, ["python"]),
    ],
)
def test_declared_answer_alone_decides_languages(answer: str, extra: dict[str, str], expected: list[str], tmp_path: Path) -> None:
    """RED (pins D1): a real languages answer resolves from THAT ANSWER ALONE (built-in + vocabulary hits)."""
    _write_overlay_artifact(tmp_path, kind_dir="tactic", name="twig-tactic", languages=["twig"])

    assert infer_repo_languages(tmp_path, interview=_interview(answer, **extra)) == expected


@pytest.mark.parametrize("answer", ["", "N/A", "unknown", "[NEEDS CLARIFICATION: which?]", _packaged_default_answer()])
def test_absent_or_placeholder_languages_answer_still_scans_other_answers(answer: str) -> None:
    """GREEN control (legacy path kept): without a real declaration other answers are scanned by the built-in detector."""
    assert infer_repo_languages(None, interview=_interview(answer, testing_requirements="pytest")) == ["python"]


def test_default_interview_resolves_to_none_under_declared_answer_rule() -> None:
    """GREEN control (#3292 guard): the untouched default interview is no signal."""
    assert infer_repo_languages(None, interview=default_interview(mission="software-dev", profile="minimal")) is None


@pytest.mark.parametrize("answer", ["n/a, none", "none; tbd", "N/A / none", "unknown, n/a"])
def test_separator_joined_placeholders_resolve_to_none(answer: str) -> None:
    """RED (pins F4): a scalar answer made only of separator-joined placeholders declares nothing."""
    assert infer_repo_languages(None, interview=_interview(answer)) is None


def test_separator_joined_placeholder_does_not_hide_a_real_declaration() -> None:
    """GREEN control: a real token next to placeholders still declares (and here is unrecognised)."""
    assert infer_repo_languages(None, interview=_interview("n/a, Zig")) == ["unknown"]


def test_language_token_after_word_hyphen_does_not_count() -> None:
    """Pins the accepted FR-015 side effect: ``React-TypeScript`` does not declare typescript (only ``word-`` prefixes are guarded)."""
    assert extract_declared_languages("React-TypeScript") == []
    assert infer_repo_languages(None, interview=_interview("React-TypeScript")) == ["unknown"]


@pytest.mark.parametrize(
    ("languages", "expected"),
    [
        (["unknown"], True),
        (["rust"], True),
        (["python"], False),
        (["python", "rust"], False),
        (["python", "unknown"], False),
        (None, False),
        ([], False),
    ],
)
def test_lacks_specialist_guidance(languages: list[str] | None, expected: bool) -> None:
    """D2: True iff some language is set and none (bar reserved tokens) has an installed scoped artifact."""
    assert lacks_specialist_guidance(languages, None) is expected


def test_lacks_specialist_guidance_honours_project_overlay_vocabulary(tmp_path: Path) -> None:
    """D2: a language scoped only by a project-overlay artifact has specialist guidance for that project."""
    _write_overlay_artifact(tmp_path, kind_dir="tactic", name="elixir-tactic", languages=["elixir"])

    assert lacks_specialist_guidance(["elixir"], None) is True
    assert lacks_specialist_guidance(["elixir"], tmp_path) is False


def _write_disk_answers(repo_root: Path, language_answer: str) -> None:
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": language_answer},
    )
    write_interview_answers(repo_root / ".kittify" / "charter" / "interview" / "answers.yaml", interview)


def test_packaged_default_interview_defers_to_on_disk_answers_like_the_runtime(tmp_path: Path) -> None:
    """RED (pins F5): with no compiled tier, the shipped-default interview must not mask the on-disk Zig answers."""
    _write_disk_answers(tmp_path, "Zig")

    default = default_interview(mission="software-dev", profile="minimal")

    assert infer_repo_languages(tmp_path, interview=default) == infer_repo_languages(tmp_path) == ["unknown"]


def test_packaged_default_interview_without_disk_answers_is_no_signal(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): default interview and nothing on disk stays ``None`` (#3292)."""
    default = default_interview(mission="software-dev", profile="minimal")

    assert infer_repo_languages(tmp_path, interview=default) is None


def test_user_interview_is_not_overridden_by_on_disk_answers(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): a real (non-default) supplied interview wins over the disk transcript."""
    _write_disk_answers(tmp_path, "Zig")

    assert infer_repo_languages(tmp_path, interview=_interview("Python")) == ["python"]


def test_prefer_interview_skips_compiled_tier(tmp_path: Path) -> None:
    """RED (pins the fix): ``prefer_interview=True`` resolves from the interview alone."""
    _write_charter_yaml(tmp_path, languages=["python"])
    interview = _interview("Zig 0.16.0")

    assert infer_repo_languages(tmp_path, interview=interview, prefer_interview=True) == ["unknown"]


def test_default_precedence_stays_compiled_first(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour, #2395/#3292): compiled tier still wins by default."""
    _write_charter_yaml(tmp_path, languages=["python"])

    assert infer_repo_languages(tmp_path, interview=_interview("Zig 0.16.0")) == ["python"]


def test_prefer_interview_without_any_interview_falls_back_to_compiled(tmp_path: Path) -> None:
    """RED (pins the fix): the new keyword exists; with nothing to prefer the compiled tier answers."""
    _write_charter_yaml(tmp_path, languages=["python"])

    assert infer_repo_languages(tmp_path, prefer_interview=True) == ["python"]


def test_unknown_language_helpers_are_re_exported() -> None:
    """RED (pins the fix): ``language_scope`` re-exports the scoping authority's unknown helpers."""
    from charter.activation import language_scope
    from charter.offering.shared import scoping

    assert language_scope.UNKNOWN_LANGUAGE == "unknown"
    assert language_scope.is_unknown_language is scoping.is_unknown_language


def test_prefer_interview_reads_on_disk_transcript_when_none_supplied(tmp_path: Path) -> None:
    """The on-disk transcript counts as "an interview available" for ``prefer_interview``."""
    _write_charter_yaml(tmp_path, languages=["python"])
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    write_interview_answers(answers_path, _interview("Zig 0.16.0"))

    assert infer_repo_languages(tmp_path, prefer_interview=True) == ["unknown"]
    assert infer_repo_languages(tmp_path) == ["python"]


def test_prefer_interview_may_resolve_to_none(tmp_path: Path) -> None:
    """A placeholder interview preferred over a compiled list yields no signal."""
    _write_charter_yaml(tmp_path, languages=["python"])

    assert infer_repo_languages(tmp_path, interview=_interview("N/A"), prefer_interview=True) is None


def test_packaged_default_answer_accessor() -> None:
    """The shared accessor returns the shipped text and ``None`` for an unknown key."""
    from charter.activation.interview import packaged_default_answer

    assert packaged_default_answer(_DEFAULTS_KEY) == _packaged_default_answer()
    assert packaged_default_answer("no_such_question") is None


def test_packaged_default_answer_is_none_when_defaults_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing/invalid ``defaults.yaml`` degrades to ``None`` rather than raising."""
    from charter.activation import interview as interview_module

    monkeypatch.setattr(interview_module, "_load_packaged_defaults", lambda: {"answers": "garbled"})

    assert interview_module.packaged_default_answer(_DEFAULTS_KEY) is None
