"""#4614 / FR-011: ``charter generate --from-interview`` re-derives ``catalog.languages``.

``charter generate`` (``--from-interview`` is the default) used to read the
previously compiled ``catalog.languages`` back as authoritative, so a stale
``[python]`` survived a regenerate from a Zig interview, and the doctrine
references were resolved under the stale language (split-brain). Regeneration
now derives the languages from the CURRENT interview; every other compile path
(``--no-from-interview``, ``charter activate``, pack recompiles) stays
compiled-first.

Red-first labelling (charter C-011): every test docstring says either
``RED (pins the fix)`` -- fails on the WP03 tip -- or ``GREEN control (pins
unchanged behaviour)`` -- passes before and after.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.compiler import _SCOPE_FILTERED_PLACEHOLDER_SUMMARY_TEMPLATE
from charter.activation.interview import (
    apply_answer_overrides,
    default_interview,
    write_interview_answers,
)
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

_LANGUAGES_KEY = "languages_frameworks"
_PYTHON_STYLEGUIDE_ID = "STYLEGUIDE:python-conventions"
_BASELINE_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_ACTIVATED_DIRECTIVE_STEM = "025-boy-scout-rule"

#: Stable prefix of every ``SCOPE_FILTERED`` placeholder summary, derived
#: from the compiler's own template rather than a hand-copied sentence
#: (#5257 landing fold, 2026-09-30) -- so this test tracks the compiler's
#: actual emitted text and cannot silently drift from it.
_SCOPE_FILTERED_PLACEHOLDER_PREFIX = _SCOPE_FILTERED_PLACEHOLDER_SUMMARY_TEMPLATE.split("{suggestion}")[0]


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _charter_yaml_path(repo: Path) -> Path:
    return repo / ".kittify" / "charter" / "charter.yaml"


def _seed_charter_yaml(repo: Path, languages: list[str]) -> None:
    """Seed a previously compiled ``charter.yaml`` carrying ``catalog.languages``."""
    path = _charter_yaml_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0.0",
        "catalog": {"mission": "software-dev", "template_set": "software-dev-default", "languages": languages, "references": []},
    }
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _write_answers(repo: Path, *, language_answer: str | None = None, available_tools: list[str] | None = None) -> None:
    """Persist ``answers.yaml``; ``language_answer=None`` keeps the shipped default text."""
    interview = default_interview(mission="software-dev", profile="minimal")
    answers = {_LANGUAGES_KEY: language_answer} if language_answer is not None else None
    interview = apply_answer_overrides(interview, answers=answers, available_tools=available_tools)
    write_interview_answers(repo / ".kittify" / "charter" / "interview" / "answers.yaml", interview)


def _generate(repo: Path, *args: str) -> dict:
    with contextlib.chdir(repo):
        result = runner.invoke(charter_app, ["generate", "--json", "--force", *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _catalog(repo: Path) -> dict:
    document = YAML(typ="safe").load(_charter_yaml_path(repo).read_text(encoding="utf-8"))
    return document["catalog"]


def _references(repo: Path) -> list[dict]:
    """Full ``catalog.references`` records (id/kind/title/summary/source_path/...).

    Extends the pre-existing id-only ``_reference_ids`` accessor (#5257
    landing fold, 2026-09-30) rather than duplicating the YAML-loading
    ``_catalog`` call at a new call site.
    """
    return list(_catalog(repo)["references"])


def _reference_ids(repo: Path) -> list[str]:
    return [str(reference["id"]) for reference in _references(repo)]


@pytest.mark.parametrize(
    ("seed", "answer", "expected"),
    [
        (["python"], "Zig with the zig build system", ["unknown"]),
        (["python"], "Rust with cargo", ["rust"]),
        (["rust"], "Python and Zig", ["python"]),
    ],
    ids=["zig-is-unknown", "rust-recognised", "python-and-zig-keeps-python"],
)
def test_from_interview_rederives_languages_from_the_answer(tmp_path: Path, seed: list[str], answer: str, expected: list[str]) -> None:
    """RED (pins the fix): a stale compiled list never survives ``generate --from-interview``."""
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, seed)
    _write_answers(tmp_path, language_answer=answer)

    _generate(tmp_path, "--from-interview")

    assert _catalog(tmp_path)["languages"] == expected


@pytest.mark.parametrize(
    "answer",
    [None, "N/A"],
    ids=["shipped-default", "placeholder-n-a"],
)
def test_from_interview_default_or_placeholder_answer_leaves_languages_absent(tmp_path: Path, answer: str | None) -> None:
    """RED (pins the fix): default / placeholder answers erase the stale seed; the field is ABSENT."""
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer=answer)

    _generate(tmp_path, "--from-interview")

    assert not _catalog(tmp_path).get("languages")


def test_no_from_interview_keeps_recorded_languages(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): ``--no-from-interview`` stays compiled-first."""
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Zig with the zig build system")

    _generate(tmp_path, "--no-from-interview")

    assert _catalog(tmp_path)["languages"] == ["python"]


def test_no_from_interview_compile_agrees_with_runtime_for_on_disk_zig_answers(tmp_path: Path) -> None:
    """RED (pins F5): no compiled tier + on-disk Zig answers -> the default-interview compile stamps ``[unknown]`` like the runtime."""
    _git_init(tmp_path)
    _write_answers(tmp_path, language_answer="Zig with the zig build system")

    _generate(tmp_path, "--no-from-interview")

    assert _catalog(tmp_path).get("languages") == ["unknown"]


def test_zig_regenerate_resolves_references_under_rederived_languages(tmp_path: Path) -> None:
    """RED (pins the fix): no ``python-*`` reference is RESOLVED after a Zig regenerate (split-brain).

    Re-pinned 2026-09-30 (#5257 landing fold, PR #5429; re-pins #4614's
    intent). #4614's module docstring states the property this test guards:
    after a regenerate, doctrine references must not be resolved under the
    stale ``python`` language. This was originally pinned as "no
    ``python-*`` id survives the compile at all" (``not any(id startswith
    python-)``), which happened to coincide with "not resolved" on main
    because a scope-filtered id was silently DROPPED from
    ``catalog.references``. #5257 (FR-001/FR-002) changed that silent drop
    into a reason-bearing PLACEHOLDER record: an activated -- including
    DRG-transitively reached -- ``python-*`` id that is out of the
    rederived (Zig) language scope now stays in ``catalog.references`` as
    an ``unresolved``/``scope_filtered`` placeholder (empty
    ``source_path``, a summary that says definition-unavailable) instead of
    disappearing. The old assertion is over-broad relative to #4614's
    intent and goes red on this legitimate placeholder shape; it is
    re-pinned here to the real property -- "not resolved", not "absent" --
    by asserting every ``python-*`` catalog entry is a scope-filtered
    placeholder (never a real, resolved definition) AND that the CLI's
    structured ``unresolved_references`` diagnostics agree. Zero
    ``python-*`` ids would also satisfy "not resolved"; this scenario is
    expected to produce at least one (the DRG-reachable
    ``python-conventions`` styleguide), so the non-vacuity guard is kept.
    Reads ``charter.yaml`` (the source of truth) plus the ``--json``
    diagnostics payload, and compares against the Python positive control
    below so the assertion is non-vacuous.
    """
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Zig with the zig build system")

    payload = _generate(tmp_path, "--from-interview")

    assert _catalog(tmp_path).get("languages") == ["unknown"]

    python_references = [reference for reference in _references(tmp_path) if str(reference["id"]).split(":", 1)[-1].startswith("python-")]
    assert python_references, "compile produced no python-* references; the assertion below would be vacuous"
    for reference in python_references:
        assert reference["summary"].startswith(_SCOPE_FILTERED_PLACEHOLDER_PREFIX), (
            f"python-* reference {reference['id']!r} must be a scope_filtered placeholder, not a resolved "
            f"definition, under the rederived Zig scope; got summary={reference['summary']!r}"
        )
        assert reference["title"] == str(reference["id"]).split(":", 1)[-1], (
            f"python-* reference {reference['id']!r} must carry the bare-id placeholder title, got {reference['title']!r}"
        )
        assert not reference["source_path"], (
            f"python-* reference {reference['id']!r} must carry no real source_path (placeholder-only), got source_path={reference['source_path']!r}"
        )

    python_unresolved = [record for record in payload["unresolved_references"] if str(record["id"]).split(":", 1)[-1].startswith("python-")]
    assert python_unresolved, "the --json unresolved_references diagnostics must record the filtered python-* ids"
    assert all(record["cause"] == "scope_filtered" for record in python_unresolved)


def test_python_regenerate_still_includes_python_conventions(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): a Python answer RESOLVES the Python styleguide.

    Strengthened 2026-09-30 alongside the Zig test's re-pin (same fold):
    the pre-existing assertion only checked that
    ``STYLEGUIDE:python-conventions`` appears among the reference ids --
    which a scope-filtered PLACEHOLDER record (#5257) would also satisfy,
    so it would not actually distinguish "resolved" from "placeholdered".
    Now also asserts the record carries a real title (a placeholder's title
    is the bare id) and a summary that is NOT the scope-filtered
    placeholder text (``source_path`` is empty for resolved DRG-rendered
    records too, so it cannot discriminate), proving this
    positive control genuinely resolves a real definition -- the exact
    contrast the Zig test above depends on for non-vacuity.
    """
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Python backend with pytest checks")

    _generate(tmp_path, "--from-interview")

    references = {str(reference["id"]): reference for reference in _references(tmp_path)}
    assert _PYTHON_STYLEGUIDE_ID in references
    styleguide = references[_PYTHON_STYLEGUIDE_ID]
    assert styleguide["title"] != _PYTHON_STYLEGUIDE_ID.split(":", 1)[-1], "a placeholder's title is the bare id; a resolved definition has its own title"
    assert not styleguide["summary"].startswith(_SCOPE_FILTERED_PLACEHOLDER_PREFIX), (
        f"the Python styleguide must be genuinely resolved, not scope-filtered; got summary={styleguide['summary']!r}"
    )


def test_activate_preserves_recorded_languages(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): ``charter activate`` recompiles compiled-first."""
    _git_init(tmp_path)
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        f"activated_directives:\n- {_BASELINE_DIRECTIVE_STEM}\nactivated_kinds:\n- directives\nmission_type_activations:\n- research\n",
        encoding="utf-8",
    )
    _generate(tmp_path, "--no-from-interview")
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Zig with the zig build system")

    activated = runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(tmp_path), "directive", _ACTIVATED_DIRECTIVE_STEM],
        catch_exceptions=False,
    )

    assert activated.exit_code == 0, activated.output
    assert _catalog(tmp_path)["languages"] == ["python"]


def test_unregistered_tool_is_diagnosed_as_a_tool_id_not_a_language(tmp_path: Path) -> None:
    """RED (pins the fix): the ``available_tools`` diagnostic names a tool id; ``zig`` is not a language."""
    _git_init(tmp_path)
    _write_answers(tmp_path, available_tools=["git", "spec-kitty", "zig"])

    payload = _generate(tmp_path, "--from-interview")

    diagnostics = "\n".join(payload["diagnostics"])
    assert "available_tools: 'zig' is not a registered tool id" in diagnostics
    assert "Ignored unknown available_tools" not in diagnostics
    assert "languages" not in _catalog(tmp_path)
    assert "zig" not in payload["available_tools"]
