"""Native next projection preserves the existing command as authority."""

from __future__ import annotations

import importlib
import contextlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]
POLICY = json.dumps(
    {
        "orchestrator_id": "test",
        "orchestrator_version": "1",
        "agent_family": "codex",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)


def invoke(args: list[str], delegate):
    module = importlib.import_module("specify_cli.orchestrator_api.runtime_next")
    app = typer.Typer()
    app.command("next")(module.runtime_next)
    app.command("unused")(lambda: None)
    with TemporaryDirectory() as checkout:
        root = Path(checkout)
        (root / "kitty-specs" / "example").mkdir(parents=True)
        with (
            patch.object(module._common, "_get_main_repo_root", return_value=root),
            patch("specify_cli.cli.commands.next_cmd.next_step", side_effect=delegate),
            patch.object(module, "_completion_gate", return_value=contextlib.nullcontext()),
        ):
            result = CliRunner().invoke(app, ["next", *args])
    return result, json.loads(result.stdout)


def test_query_passes_explicit_read_only_parameters_and_multiline_json() -> None:
    calls = []

    def delegate(**kwargs):
        calls.append(kwargs)
        print(json.dumps({"kind": "query", "mission_slug": "example", "is_query": True}, indent=2))

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 0
    assert payload["success"] is True
    assert calls == [{"agent": None, "result": None, "mission": "example", "json_output": True, "answer": None, "decision_id": None, "owned_checkout": None}]


def test_advancing_without_policy_does_not_delegate() -> None:
    def delegate(**kwargs):
        pytest.fail("Missing policy must refuse before authority")

    result, payload = invoke(["--mission", "example", "--result", "success", "--agent", "codex"], delegate)
    assert result.exit_code == 1
    assert payload["error_code"] == "POLICY_METADATA_REQUIRED"


def test_advancing_returns_bounded_host_prompt(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# Implement the canonical step\n")

    def delegate(**kwargs):
        assert kwargs["result"] == "success"
        print(json.dumps({"kind": "step", "mission_slug": "example", "prompt_file": str(prompt)}, indent=2))

    result, payload = invoke(["--mission", "example", "--result", "success", "--agent", "codex", "--policy", POLICY], delegate)
    assert result.exit_code == 0
    assert payload["data"]["prompt"]["content"] == prompt.read_text()
    assert "prompt_file" not in payload["data"]
    assert len(payload["data"]["prompt"]["sha256"]) == 64


@pytest.mark.parametrize("kind", ["blocked", "error"])
def test_native_blocked_is_failure_not_outer_success(kind: str) -> None:
    def delegate(**kwargs):
        print(json.dumps({"kind": kind, "mission_slug": "example", "reason": "blocked for real"}, indent=2))

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 1
    assert payload["success"] is False
    assert payload["data"]["reason"] == "blocked for real"


def test_decision_required_keeps_typed_native_boundary() -> None:
    def delegate(**kwargs):
        print(json.dumps({"kind": "decision_required", "mission_slug": "example", "decision_id": "input:review", "question": "Approve?"}, indent=2))

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 0
    assert payload["data"]["kind"] == "decision_required"


def test_native_exit_retains_inner_error() -> None:
    def delegate(**kwargs):
        print(json.dumps({"error_code": "RUN_STATE_CORRUPT", "error": "Cannot decode"}, indent=2))
        raise typer.Exit(1)

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 1
    assert payload["error_code"] == "RUNTIME_NEXT_FAILED"
    assert payload["data"]["error_code"] == "RUN_STATE_CORRUPT"


def test_missing_prompt_fails_truthfully(tmp_path: Path) -> None:
    def delegate(**kwargs):
        print(json.dumps({"kind": "step", "mission_slug": "example", "prompt_file": str(tmp_path / "missing")}, indent=2))

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 1
    assert payload["error_code"] == "RUNTIME_NEXT_FAILED"
    assert str(tmp_path) not in json.dumps(payload)


def test_answer_byte_limit_refuses_before_native() -> None:
    def delegate(**kwargs):
        pytest.fail("Oversize answers must refuse before native next")

    result, payload = invoke(["--mission", "example", "--answer", "x" * 262145], delegate)
    assert result.exit_code == 1
    assert payload["error_code"] == "RUNTIME_NEXT_FAILED"


_QUERY_DOC = json.dumps({"kind": "query", "mission_slug": "example", "is_query": True})


@pytest.mark.parametrize(
    "stdout",
    [
        "diagnostics only",
        f"warning: noise\n{_QUERY_DOC}",
        f"{_QUERY_DOC}\ntrailing noise",
        f"{_QUERY_DOC}\n{_QUERY_DOC}",
    ],
    ids=["no-json", "leading-noise", "trailing-noise", "two-documents"],
)
def test_native_malformed_output_fails_truthfully(stdout: str) -> None:
    def delegate(**kwargs):
        print(stdout)

    result, payload = invoke(["--mission", "example"], delegate)
    assert result.exit_code == 1
    assert payload["error_code"] == "RUNTIME_NEXT_FAILED"
