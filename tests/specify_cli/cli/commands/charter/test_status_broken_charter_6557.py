"""Regression tests for #6557: ``charter status`` refuses an unsound ``charter.yaml`` with a typed code.

``charter status`` used to read a broken ``charter.yaml`` through the bundle
check and its collectors: an unparseable file surfaced as ``Unexpected error:
mapping values are not allowed here ...`` and a list-rooted one as the
bundle-schema "run spec-kitty upgrade" message. These tests pin the refusal
through the shared soundness gate (#6415): exit 1, ``ACTIVE_CHARTER_CONFIG_INVALID``,
the file and the remedy named, the canonical ``{"ok": false, "error": {...}}``
envelope under ``--json`` (operator decision 01M5ZCANVH16B2ANT1BJ115S8R), and
nothing written under ``.kittify/``.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from charter.activation.api import ActiveCharterConfigError
from charter.activation.evidence.orchestrator import ConfigShapeError
from kernel.errors import KittyInternalConsistencyError
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter.status import _status_error
from specify_cli.task_utils import TaskCliError

pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]

runner = CliRunner()

_CODE = "ACTIVE_CHARTER_CONFIG_INVALID"
_CHARTER_REL = ".kittify/charter/charter.yaml"
_REMEDY = "spec-kitty charter generate --from-interview"
#: The broken charter the gating scenario (refuses-unsound-governance, PR-CHARTER-REFUSAL-003) writes.
_BROKEN_YAML = "this: is not: a valid charter\n\t- broken\n:::\n"
_LIST_ROOT_YAML = "- a\n- b\n"
_COMMENT_ONLY_YAML = "# nothing here\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture(scope="module")
def _generated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One generated charter project, copied per test (``generate`` is the slow step)."""
    repo = tmp_path_factory.mktemp("charter-6557-template")
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
        "  purpose: Test charter for the #6557 status refusal regression suite.\n",
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
    assert _snapshot(repo) == before, "a refused status must write nothing under .kittify/"
    return " ".join(output.split())


def _assert_text_refusal(text: str) -> None:
    assert f"Error ({_CODE}):" in text, text
    assert _CHARTER_REL in text, text
    assert _REMEDY in text, text
    assert "Unexpected" not in text, text
    assert "Bundle schema version" not in text, text
    assert "spec-kitty upgrade" not in text, text


def _assert_json_refusal(result: object) -> str:
    payload = json.loads(getattr(result, "stdout", ""))
    assert set(payload) == {"ok", "error"}, payload
    assert payload["ok"] is False, payload
    assert set(payload["error"]) == {"code", "message"}, payload
    assert payload["error"]["code"] == _CODE, payload
    message = payload["error"]["message"]
    assert isinstance(message, str)
    assert _CHARTER_REL in message, message
    assert _REMEDY in message, message
    assert "Unexpected" not in message, message
    assert "Bundle schema version" not in message, message
    assert "spec-kitty upgrade" not in message, message
    return message


@pytest.mark.parametrize("content", [_BROKEN_YAML, _LIST_ROOT_YAML, _COMMENT_ONLY_YAML], ids=["unparseable", "list-root", "comment-only"])
def test_status_text_refuses_unsound_charter(project: Path, content: str) -> None:
    (project / _CHARTER_REL).write_text(content, encoding="utf-8")
    before = _snapshot(project)

    text = _assert_refused(_invoke(project, "status"), before, project)

    _assert_text_refusal(text)


@pytest.mark.parametrize("content", [_BROKEN_YAML, _LIST_ROOT_YAML, _COMMENT_ONLY_YAML], ids=["unparseable", "list-root", "comment-only"])
def test_status_json_refuses_unsound_charter_with_canonical_envelope(project: Path, content: str) -> None:
    (project / _CHARTER_REL).write_text(content, encoding="utf-8")
    before = _snapshot(project)

    result = _invoke(project, "status", "--json")

    _assert_refused(result, before, project)
    _assert_json_refusal(result)


def test_status_empty_charter_names_no_content(project: Path) -> None:
    (project / _CHARTER_REL).write_text("", encoding="utf-8")
    before = _snapshot(project)

    result = _invoke(project, "status", "--json")

    _assert_refused(result, before, project)
    message = _assert_json_refusal(result)
    assert "no content" in message, message


def test_status_sound_charter_succeeds(project: Path) -> None:
    """Positive control on the same fixture: a sound charter keeps the success payload."""
    result = _invoke(project, "status", "--json")

    assert getattr(result, "exit_code", None) == 0, getattr(result, "output", "")
    payload = json.loads(getattr(result, "stdout", ""))
    assert payload["result"] == "success", payload


# ---------------------------------------------------------------------------
# Every status error uses the coded envelope (operator decision 01M5ZCANVH16B2ANT1BJ115S8R)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "code", "message"),
    [
        (ActiveCharterConfigError("charter.yaml is broken"), _CODE, "charter.yaml is broken"),
        (KittyInternalConsistencyError("SOME_CODE"), "SOME_CODE", "SOME_CODE"),
        (ConfigShapeError(".kittify/config.yaml is not a mapping"), "CHARTER_CONFIG_SHAPE_INVALID", ".kittify/config.yaml is not a mapping"),
        (TaskCliError("not inside a repository"), "CHARTER_STATUS_FAILED", "not inside a repository"),
        (RuntimeError("boom"), "INTERNAL_ERROR", "Unexpected error: boom"),
    ],
    ids=["typed", "typed-no-body", "config-shape", "task-cli", "internal"],
)
def test_status_error_maps_each_exception_to_its_code(exc: Exception, code: str, message: str) -> None:
    assert _status_error(exc) == (code, message)


@pytest.mark.parametrize(
    ("exc", "code", "message"),
    [
        (TaskCliError("not inside a repository"), "CHARTER_STATUS_FAILED", "not inside a repository"),
        (RuntimeError("boom"), "INTERNAL_ERROR", "Unexpected error: boom"),
    ],
    ids=["task-cli", "internal"],
)
def test_status_renders_every_error_with_the_coded_envelope(exc: Exception, code: str, message: str) -> None:
    with patch.object(charter_pkg, "find_repo_root", side_effect=exc):
        as_json = runner.invoke(charter_app, ["status", "--json"], catch_exceptions=False)
        as_text = runner.invoke(charter_app, ["status"], catch_exceptions=False)

    assert as_json.exit_code == 1, as_json.output
    assert json.loads(as_json.stdout) == {"ok": False, "error": {"code": code, "message": message}}
    assert as_text.exit_code == 1, as_text.output
    assert f"Error ({code}): {message}" in " ".join(as_text.output.split())
