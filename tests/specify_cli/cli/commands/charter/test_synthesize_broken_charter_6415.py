"""Regression tests for #6415: synthesis commands fail closed on an unsound ``charter.yaml``.

``charter synthesize`` gated its fresh-project seed on ``charter.yaml`` merely
existing, and the establishment probe read an unparseable file as "never
activated". A broken ``charter.yaml`` therefore took the destructive
minimal-seed path and exited 0. These tests pin the refusal: exit 1, the
``ACTIVE_CHARTER_CONFIG_INVALID`` code, the file and the remedy named, and
nothing written under ``.kittify/`` -- in every mode, and for the sibling
commands that also read the charter.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]

runner = CliRunner()

_CODE = "ACTIVE_CHARTER_CONFIG_INVALID"
_CHARTER_REL = ".kittify/charter/charter.yaml"
_REMEDY = "spec-kitty charter generate --from-interview"
#: The broken charter the gating scenario (refuses-unsound-governance, PR-CHARTER-REFUSAL-003) writes.
_BROKEN_YAML = "this: is not: a valid charter\n\t- broken\n:::\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture(scope="module")
def _generated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One generated charter project, copied per test (``generate`` is the slow step)."""
    repo = tmp_path_factory.mktemp("charter-6415-template")
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: Test charter for the #6415 fail-closed regression suite.\n",
        encoding="utf-8",
    )
    with contextlib.chdir(repo):
        result = runner.invoke(charter_app, ["generate", "--from-interview"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert (repo / _CHARTER_REL).is_file(), "test pre-condition: generate must write charter.yaml"
    return repo


@pytest.fixture
def project(_generated_template: Path, tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    shutil.copytree(_generated_template, repo, symlinks=True)
    return repo


def _snapshot(repo: Path) -> dict[str, bytes]:
    kittify = repo / ".kittify"
    return {str(p.relative_to(repo)): p.read_bytes() for p in sorted(kittify.rglob("*")) if p.is_file()}


def _invoke(repo: Path, *args: str) -> object:
    with contextlib.chdir(repo):
        return runner.invoke(charter_app, list(args), catch_exceptions=False)


def _assert_refused(result: object, before: dict[str, bytes], repo: Path) -> str:
    output = (getattr(result, "stdout", "") or "") + (getattr(result, "output", "") or "")
    assert getattr(result, "exit_code", None) == 1, f"expected a fail-closed refusal (exit 1), got {getattr(result, 'exit_code', None)}: {output!r}"
    assert _snapshot(repo) == before, "a refused run must write nothing under .kittify/"
    assert not (repo / ".kittify" / "charter-packs").exists(), "the minimal seed must not be materialized"
    return " ".join(output.split())


def _assert_names_file_and_remedy(text: str) -> None:
    assert _CODE in text, text
    assert _CHARTER_REL in text, text
    assert _REMEDY in text, text


# ---------------------------------------------------------------------------
# charter synthesize: every mode refuses a broken charter.yaml
# ---------------------------------------------------------------------------


def test_synthesize_refuses_unparseable_charter(project: Path) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "synthesize"), before, project)

    _assert_names_file_and_remedy(text)
    assert "not valid YAML" in text
    assert "fresh project" not in text.lower()


def test_synthesize_dry_run_refuses_unparseable_charter(project: Path) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "synthesize", "--dry-run"), before, project)

    _assert_names_file_and_remedy(text)
    assert "would materialize" not in text


def test_synthesize_json_emits_typed_failure_envelope(project: Path) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    result = _invoke(project, "synthesize", "--json")

    _assert_refused(result, before, project)
    payload = json.loads(result.stdout)
    assert payload["result"] == "failure"
    assert payload["written_artifacts"] == []
    assert payload["code"] == _CODE
    detail = " ".join(payload["warnings"])
    _assert_names_file_and_remedy(detail)


def test_synthesize_refuses_broken_charter_on_established_store(project: Path) -> None:
    """A real prior synthesis plus answers on disk: a broken charter must not fall through to the adapter."""
    manifest = project / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest.write_text(
        "schema_version: '3'\n"
        "mission_id: null\n"
        "created_at: '2026-01-01T00:00:00+00:00'\n"
        "run_id: 01JTESTRUNIDXXXXXXXXXXXXXX\n"
        "adapter_id: generated\n"
        "adapter_version: '0.0.0'\n"
        "synthesizer_version: '0.0.0'\n"
        "manifest_hash: " + ("a" * 64) + "\n"
        "artifacts: []\n"
        "built_in_only: false\n",
        encoding="utf-8",
    )
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "synthesize"), before, project)

    _assert_names_file_and_remedy(text)


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        pytest.param("- a\n- b\n", "root must be a mapping, got", id="list-root"),
        pytest.param("just a string\n", "root must be a mapping, got", id="scalar-root"),
        pytest.param("\n  \n", "it has no content", id="whitespace-only"),
        pytest.param("# only a comment\n", "it has no content", id="comment-only"),
        pytest.param("schema_version: !!int xyz\n", "not valid YAML", id="constructor-valueerror"),
        pytest.param("catalog:\n  generated_at: 2001-13-45\n", "not valid YAML", id="impossible-date"),
    ],
)
def test_synthesize_refuses_unsound_charter_shape(project: Path, body: str, reason: str) -> None:
    (project / _CHARTER_REL).write_text(body, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "synthesize"), before, project)

    _assert_names_file_and_remedy(text)
    assert reason in text


# ---------------------------------------------------------------------------
# Sibling commands that read the charter refuse too, and write nothing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("activate", "tactic", "usage-examples-sync"), id="activate"),
        pytest.param(("deactivate", "tactic", "usage-examples-sync"), id="deactivate"),
    ],
)
def test_activation_commands_refuse_broken_charter(project: Path, args: tuple[str, ...]) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, *args), before, project)

    assert _CODE in text
    assert "charter.yaml" in text


def test_resynthesize_refuses_broken_charter_with_typed_reason(project: Path) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "resynthesize", "--topic", "tactic:usage-examples-sync"), before, project)

    _assert_names_file_and_remedy(text)
    assert "Unexpected error" not in text


def test_resynthesize_json_refusal_is_one_json_document(project: Path) -> None:
    (project / _CHARTER_REL).write_text(_BROKEN_YAML, encoding="utf-8")
    before = _snapshot(project)

    result = _invoke(project, "resynthesize", "--topic", "tactic:usage-examples-sync", "--json")

    _assert_refused(result, before, project)
    payload = json.loads(result.stdout)
    _assert_names_file_and_remedy(json.dumps(payload))
