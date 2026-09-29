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


def _reference_ids(repo: Path) -> list[str]:
    return [str(reference["id"]) for reference in _catalog(repo)["references"]]


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
    """RED (pins the fix): no ``python-*`` reference survives a Zig regenerate (split-brain).

    Reads ``charter.yaml`` (the source of truth), and compares against the
    Python positive control below so the assertion is non-vacuous.
    """
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Zig with the zig build system")

    _generate(tmp_path, "--from-interview")

    ids = _reference_ids(tmp_path)
    assert ids, "compile produced no references; the assertion below would be vacuous"
    assert not any(i.split(":", 1)[-1].startswith("python-") for i in ids)


def test_python_regenerate_still_includes_python_conventions(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): a Python answer resolves the Python styleguide."""
    _git_init(tmp_path)
    _seed_charter_yaml(tmp_path, ["python"])
    _write_answers(tmp_path, language_answer="Python backend with pytest checks")

    _generate(tmp_path, "--from-interview")

    assert _PYTHON_STYLEGUIDE_ID in _reference_ids(tmp_path)


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
