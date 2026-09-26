"""Regression coverage for charter ``--json`` error-path parseability."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.resolution import NotInsideRepositoryError
from charter.activation.synthesizer.errors import TopicSelectorUnresolvedError
from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.charter_bundle import app as bundle_app
from specify_cli.task_utils import TaskCliError

pytestmark = [pytest.mark.fast]

runner = CliRunner()


def _assert_json_error(output: str) -> dict[str, object]:
    payload = json.loads(output)
    assert payload["result"] == "error"
    assert payload["success"] is False
    assert isinstance(payload["error"], str)
    assert payload["error"]
    return payload


@pytest.mark.parametrize(
    ("argv", "exit_code"),
    [
        (["context", "--action", "specify", "--json"], 1),
        (["interview", "--defaults", "--profile", "minimal", "--json"], 1),
        (["sync", "--json"], 1),
        (["resynthesize", "--list-topics", "--json"], 1),
        (["lint", "--json"], 1),
    ],
)
def test_charter_json_commands_emit_parseable_error_when_repo_root_missing(
    argv: list[str],
    exit_code: int,
) -> None:
    with patch(
        "specify_cli.cli.commands.charter.find_repo_root",
        side_effect=TaskCliError("repo root unavailable"),
    ):
        result = runner.invoke(charter_app, argv)

    assert result.exit_code == exit_code, result.output
    payload = _assert_json_error(result.output)
    assert payload["error"] == "repo root unavailable"


def test_resynthesize_json_unresolved_topic_error_is_parseable(tmp_path: Path) -> None:
    evidence_result = SimpleNamespace(warnings=["corpus unavailable"], bundle=SimpleNamespace())
    unresolved = TopicSelectorUnresolvedError(
        raw="does-not-exist",
        candidates=("directive:PROJECT_001",),
        attempted_forms=("kind_slug",),
    )

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.charter._collect_evidence_result", return_value=evidence_result),
        patch("specify_cli.cli.commands.charter._build_synthesis_request", return_value=(SimpleNamespace(), SimpleNamespace())),
        patch("charter.activation.synthesizer.resynthesize_pipeline.run", side_effect=unresolved),
    ):
        result = runner.invoke(charter_app, ["resynthesize", "--topic", "does-not-exist", "--json"])

    assert result.exit_code == 2, result.output
    payload = _assert_json_error(result.output)
    assert "does-not-exist" in str(payload["error"])
    assert "directive:PROJECT_001" in str(payload["error"])


def test_resynthesize_json_keeps_evidence_warnings_inside_payload(tmp_path: Path) -> None:
    evidence_result = SimpleNamespace(warnings=["corpus unavailable"], bundle=SimpleNamespace())

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.charter._collect_evidence_result", return_value=evidence_result),
        patch("specify_cli.cli.commands.charter._build_synthesis_request", return_value=(SimpleNamespace(), SimpleNamespace())),
        patch(
            "specify_cli.cli.commands.charter._list_resynthesis_topics",
            return_value={
                "project_artifacts": [],
                "drg_urns": [],
                "interview_sections": [],
            },
        ),
    ):
        result = runner.invoke(charter_app, ["resynthesize", "--list-topics", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "success"
    assert payload["warnings"] == ["corpus unavailable"]


def test_sync_json_error_result_is_parseable_and_nonzero(tmp_path: Path) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
    sync_result = SimpleNamespace(
        synced=False,
        stale_before=False,
        files_written=[],
        extraction_mode="llm",
        error="charter parse failed",
    )

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("charter.activation.sync.sync", return_value=sync_result),
    ):
        result = runner.invoke(charter_app, ["sync", "--json"])

    assert result.exit_code == 1, result.output
    payload = _assert_json_error(result.output)
    assert payload["error"] == "charter parse failed"


def test_sync_json_filesystem_failure_does_not_log_to_stderr(tmp_path: Path) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    # consolidate-charter-bundle (#2773) retired the compiled ``governance.yaml``
    # scrape; ``charter sync`` no longer reads or writes it (governance/directives
    # are hand-authored inside ``charter.yaml`` now). The file ``sync`` actually
    # reads is ``charter.md`` — make THAT a directory so the read raises and the
    # command must surface a parseable JSON error on stdout (not stderr).
    (charter_dir / "charter.md").mkdir(parents=True)

    with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
        result = runner.invoke(charter_app, ["sync", "--json"])

    assert result.exit_code == 1, result.output
    payload = _assert_json_error(result.stdout)
    assert "charter.md" in str(payload["error"])
    assert result.stderr == ""


def test_interview_json_keeps_org_prefill_messages_inside_payload(tmp_path: Path) -> None:
    interview_data = SimpleNamespace(
        mission="software-dev",
        profile="minimal",
        answers={},
        selected_paradigms=[],
        selected_directives=[],
        available_tools=[],
    )

    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.charter.default_interview", return_value=interview_data),
        patch(
            "specify_cli.doctrine.org_charter.apply_org_charter_to_interview",
            return_value=["applied org default"],
        ),
        patch("charter.activation.interview.write_interview_answers"),
        patch("charter.activation.interview.apply_answer_overrides", return_value=interview_data),
        patch("charter.activation.interview.MINIMAL_QUESTION_ORDER", []),
        patch("charter.activation.interview.QUESTION_ORDER", []),
        patch("charter.activation.interview.QUESTION_PROMPTS", {}),
        patch("specify_cli.cli.commands.charter._get_widen_prereqs_absent", return_value=None),
    ):
        result = runner.invoke(charter_app, ["interview", "--defaults", "--profile", "minimal", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "success"
    assert payload["org_prefill_messages"] == ["applied org default"]
    assert payload["org_prefill_warning"] is None


def test_bundle_validate_json_resolver_error_is_parseable() -> None:
    with patch(
        "specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root",
        side_effect=NotInsideRepositoryError("not a repo"),
    ):
        result = runner.invoke(bundle_app, ["validate", "--json"])

    assert result.exit_code == 2, result.output
    payload = _assert_json_error(result.output)
    assert "not a repo" in str(payload["error"])


def test_non_json_error_preserves_bracketed_tokens() -> None:
    """#5130: a charter error message carrying a bracketed doctrine token (e.g.
    ``[build]``) must render verbatim, not be eaten by Rich markup.

    This is the error-path twin of the #5061 ``markup=False`` success-path fix.
    It drives the real Typer CLI so the production error-rendering path
    (``_emit_error``) is exercised, not a helper, and patches a *dependency*
    (``resolve_org_roots``) rather than the code under test. Positive control:
    the plain-text sibling ``not a repo`` message above proves ordinary error
    text is unaffected. Red-first: without ``rich.markup.escape`` the token is
    silently stripped and this assertion fails.
    """
    with patch(
        "charter.drg.resolve_org_roots",
        side_effect=TaskCliError("unresolved selector [build] in doctrine request"),
    ):
        result = runner.invoke(charter_app, ["context", "--action", "implement"])

    assert result.exit_code == 1, result.output
    assert "[build]" in result.output, result.output
