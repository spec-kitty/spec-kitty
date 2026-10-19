"""#6442 -- the testing styleguide's directive edge survives the real ``charter synthesize``.

The table edge ``directive:DIRECTIVE_034 --suggests--> styleguide:testing-style-guide`` is
emitted ALWAYS (operator decision): whether or not the directive is selected or active in
the project. The activation filter must not decide whether the styleguide is a root.

Runs the real CLI in a temp git project; each absence is paired with a positive control.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.compiler import _direct_root_urns, resolve_config_activated_roots
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_DIRECTIVE = "DIRECTIVE_034"
_DIRECTIVE_URN = f"directive:{_DIRECTIVE}"
_DIRECTIVE_STEM = "034-test-first-development"
_STYLEGUIDE_URN = "styleguide:testing-style-guide"
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}


def _project(root: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=root, check=True, capture_output=True)
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(
        "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
        "  mission_type: software_dev\n  testing_philosophy: test-driven\n  risk_appetite: moderate\n"
        "selected_paradigms: []\nselected_directives: []\navailable_tools: []\n",
        encoding="utf-8",
    )
    generated = runner.invoke(app, ["generate", "--from-interview"], catch_exceptions=False)
    assert generated.exit_code == 0, generated.output


def _write_generated_artifacts(root: Path) -> None:
    """Hand the ``generated`` adapter a body for every target the real request derives."""
    from charter.activation.synthesizer.interview_mapping import resolve_sections
    from charter.activation.synthesizer.targets import build_targets
    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    request, _ = _build_synthesis_request(root, "generated")
    snapshot = request.interview_snapshot
    for target in build_targets(snapshot, resolve_sections(snapshot), request.drg_snapshot):
        folder = root / ".kittify" / "charter" / "generated" / _PLURALS[target.kind]
        folder.mkdir(parents=True, exist_ok=True)
        base = {"id": target.artifact_id, "schema_version": "1.0"}
        if target.kind == "directive":
            body = {**base, "title": target.title, "intent": "Project intent body.", "enforcement": "advisory"}
        elif target.kind == "tactic":
            body = {**base, "name": target.title, "purpose": "p", "steps": [{"title": "s", "description": "d"}]}
        else:
            body = {**base, "title": target.title, "scope": "code", "principles": ["Be good."]}
        (folder / target.filename).write_text(yaml.safe_dump(body), encoding="utf-8")


def _synthesize(root: Path) -> None:
    _write_generated_artifacts(root)
    result = runner.invoke(app, ["synthesize", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def _edge_present(root: Path) -> bool:
    graph = yaml.safe_load((root / ".kittify" / "charter-packs" / "graph.yaml").read_text(encoding="utf-8"))
    return any(e["source"] == _DIRECTIVE_URN and e["target"] == _STYLEGUIDE_URN and e["relation"] == "suggests" for e in graph["edges"])


def _is_root(root: Path) -> bool:
    return _STYLEGUIDE_URN in _direct_root_urns(resolve_config_activated_roots(repo_root=root), root)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, charter_cwd_isolation: Callable[..., Path]) -> Path:
    charter_cwd_isolation(tmp_path)
    monkeypatch.chdir(tmp_path)
    _project(tmp_path)
    return tmp_path


def test_default_project_emits_edge_and_styleguide_is_not_a_root(project: Path) -> None:
    config = (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "activated_directives" not in config, "control: the default project has no activation key"

    _synthesize(project)

    assert _edge_present(project)
    assert not _is_root(project)


def test_deactivating_the_directive_keeps_the_edge_and_the_styleguide_stays_reach_only(project: Path) -> None:
    activate = runner.invoke(app, ["activate", "directive", _DIRECTIVE_STEM, "--no-compile"], catch_exceptions=False)
    assert activate.exit_code == 0, activate.output
    _synthesize(project)
    assert _edge_present(project), "control: edge present while the directive is active"

    deactivate = runner.invoke(app, ["deactivate", "directive", _DIRECTIVE_STEM, "--no-compile"], catch_exceptions=False)
    assert deactivate.exit_code == 0, deactivate.output
    _synthesize(project)

    assert _edge_present(project)
    assert not _is_root(project)
