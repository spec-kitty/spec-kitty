"""An operator-time writer leaves an absent ``activated_<kind>`` key absent (#6685).

While ``activated_<kind>`` is absent, every available artifact of that kind is in
force. ``charter interview`` (without ``--narrow-activation``) and the first
``charter activate <kind> <id>`` (without ``--only``) used to materialise that
whole in-force set into the key before appending the selection. Runtime
governance did not change — the list written is what was already in force — but
``charter synthesize`` reads a *present* list as an operator's activation: it
demands one companion tactic per directive and skips the fresh-project seed, so
``implement`` refuses every work package with ``synthesized_drg missing``. That
is the #6629 block, re-created at operator time.

The #6629 / #6683 ruling is that an absent key means "everything in force", so
writing a list changes its meaning; the upgrade promotion and the org-required
union already follow it. These tests pin it for the two remaining writers,
through the pre-existing CLI entry points (interview → generate → synthesize).
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.interview import default_interview, write_interview_answers
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter._synthesis import _catalog_is_established

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Built-in ids; every one of them is in force while the key is absent.
SELECTED_DIRECTIVE = "010-specification-fidelity-requirement"
SELECTED_DIRECTIVE_ID = "DIRECTIVE_010"
SELECTED_PARADIGM = "atomic-design"
ACTIVATED_DIRECTIVE = "001-architectural-integrity-standard"

#: Every file the activation surface can live in (the activation ledger, or the legacy keys beside it).
SURFACE_FILES = (
    Path(".kittify") / "charter" / "activation.yaml",
    Path(".kittify") / "config.yaml",
    Path(".kittify") / "charter" / "charter.yaml",
)


@pytest.fixture
def unrestricted_project(tmp_path: Path) -> Path:
    """The #6685 shape: a git project with no ``activated_*`` key at all."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    return tmp_path


def _invoke(project: Path, *args: str):
    """Run a charter command from inside *project* (the CLI resolves the repo root from cwd)."""
    with contextlib.chdir(project):
        return CliRunner().invoke(charter_app, list(args), catch_exceptions=False)


def _activation_keys(project: Path) -> list[str]:
    """``<file>:<key>`` for every ``activated_*`` key on the activation surface."""
    found: list[str] = []
    for relative in SURFACE_FILES:
        path = project / relative
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            name = line.split(":", 1)[0].strip()
            if name.startswith("activated_"):
                found.append(f"{relative}:{name}")
    return found


def _synthesize_mode(project: Path) -> str:
    """The mode ``charter synthesize --dry-run --json`` reports."""
    result = _invoke(project, "synthesize", "--dry-run", "--json")
    assert result.exit_code == 0, result.stdout
    return str(json.loads(result.stdout)["mode"])


def _write_answers(project: Path) -> None:
    """Record interview selections the way the interview would, without running its promotion."""
    interview = dataclasses.replace(
        default_interview(mission="software-dev", profile="minimal"),
        selected_directives=[SELECTED_DIRECTIVE_ID],
        selected_paradigms=[SELECTED_PARADIGM],
    )
    write_interview_answers(project / ".kittify" / "charter" / "interview" / "answers.yaml", interview)


def _generate(project: Path) -> None:
    """``charter generate``: the step between the interview and ``charter synthesize``."""
    result = _invoke(project, "generate")
    assert result.exit_code == 0, result.stdout
    assert not _activation_keys(project), "control: generate writes no activation key of its own"


def test_interview_without_narrow_writes_no_activation_key_and_synthesis_stays_fresh(unrestricted_project: Path) -> None:
    """The interview records the selection, writes no list, and synthesis still takes the fresh-project seed."""
    project = unrestricted_project

    result = _invoke(
        project,
        "interview",
        "--defaults",
        "--selected-directives",
        SELECTED_DIRECTIVE_ID,
        "--selected-paradigms",
        SELECTED_PARADIGM,
    )

    assert result.exit_code == 0, result.stdout
    assert _activation_keys(project) == [], "the interview wrote an activation key into the absent-key state (#6685)"
    assert _catalog_is_established(project) is False, "a seeded list reads as an operator's activation (#2577/#4785)"
    assert "activated_directives" in result.stdout, result.stdout
    assert "--narrow-activation" in result.stdout, "the message must name the flag that writes an explicit list"
    assert (project / ".kittify" / "charter" / "interview" / "answers.yaml").is_file(), "the answers are still recorded"

    _generate(project)
    assert _synthesize_mode(project) == "fresh_project_seed_dry_run"


def test_first_activate_of_an_in_force_artifact_writes_no_activation_key(unrestricted_project: Path) -> None:
    """A first ``charter activate`` of an artifact the absent key already puts in force writes nothing."""
    project = unrestricted_project
    _write_answers(project)
    _generate(project)

    result = _invoke(project, "activate", "directive", ACTIVATED_DIRECTIVE)

    assert result.exit_code == 0, result.stdout
    assert _activation_keys(project) == [], "the first activate wrote an allow list into the absent-key state (#6685)"
    assert _catalog_is_established(project) is False
    assert ACTIVATED_DIRECTIVE in result.stdout, result.stdout
    assert _synthesize_mode(project) == "fresh_project_seed_dry_run"
