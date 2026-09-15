"""The ``spec-kitty live-work`` command group — exit-0 posture, matrix gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.live_work import app

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/acme/repo.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(root)
    monkeypatch.delenv("SPEC_KITTY_NO_MOMENT_HANDLERS", raising=False)
    return root


def _hook_payload(repo: Path) -> str:
    return json.dumps(
        {
            "hook_event_name": "SessionStart",
            "session_id": "s1",
            "cwd": str(repo),
            "source": "startup",
        }
    )


def test_hook_command_publishes_and_exits_zero(repo: Path, monkeypatch) -> None:
    published: list = []
    from specify_cli.live_work import publisher as publisher_module

    def _fake_publish(observations, *, cwd, report=None):
        published.extend(observations)
        return report if report is not None else publisher_module.PublishReport()

    monkeypatch.setattr(publisher_module, "publish_observations", _fake_publish)
    result = runner.invoke(app, ["hook", "claude"], input=_hook_payload(repo))
    assert result.exit_code == 0, result.output
    assert published and published[0].kind.value == "session.started"


def test_hook_command_exits_zero_on_garbage_stdin(repo: Path) -> None:
    result = runner.invoke(app, ["hook", "claude"], input="not json at all")
    assert result.exit_code == 0


def test_hook_command_exits_zero_on_empty_stdin(repo: Path) -> None:
    result = runner.invoke(app, ["hook", "claude"], input="")
    assert result.exit_code == 0


def test_hook_command_exits_zero_for_unknown_harness(repo: Path) -> None:
    result = runner.invoke(app, ["hook", "cursor"], input=_hook_payload(repo))
    assert result.exit_code == 0


def test_hook_command_honors_the_kill_switch(repo: Path, monkeypatch) -> None:
    published: list = []
    from specify_cli.live_work import publisher as publisher_module

    monkeypatch.setattr(
        publisher_module,
        "publish_observations",
        lambda observations, *, cwd, report=None: published.extend(observations) or publisher_module.PublishReport(),
    )
    monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")
    result = runner.invoke(app, ["hook", "claude"], input=_hook_payload(repo))
    assert result.exit_code == 0
    assert published == []


def test_hook_command_never_raises_even_when_publish_explodes(repo: Path, monkeypatch) -> None:
    from specify_cli.live_work import publisher as publisher_module

    def _explode(observations, *, cwd, report=None):
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(publisher_module, "publish_observations", _explode)
    result = runner.invoke(app, ["hook", "claude"], input=_hook_payload(repo))
    assert result.exit_code == 0


def test_matrix_command_exits_nonzero_when_configured_harness_is_degraded(repo: Path, monkeypatch) -> None:
    from specify_cli.core.agent_config import AgentConfig

    monkeypatch.setattr(
        "specify_cli.core.agent_config.load_agent_config",
        lambda root: AgentConfig(available=["claude"]),
    )
    result = runner.invoke(app, ["matrix"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["degraded_harnesses"] == ["claude"]


def test_matrix_command_allow_degraded_exits_zero(repo: Path, monkeypatch) -> None:
    from specify_cli.core.agent_config import AgentConfig

    monkeypatch.setattr(
        "specify_cli.core.agent_config.load_agent_config",
        lambda root: AgentConfig(available=["claude"]),
    )
    result = runner.invoke(app, ["matrix", "--allow-degraded"])
    assert result.exit_code == 0


def test_matrix_command_healthy_when_hooks_installed(repo: Path, monkeypatch) -> None:
    from specify_cli.core.agent_config import AgentConfig
    from specify_cli.live_work.install import CLAUDE_LIVE_WORK_COMMAND

    monkeypatch.setattr(
        "specify_cli.core.agent_config.load_agent_config",
        lambda root: AgentConfig(available=["claude"]),
    )
    settings = repo / ".claude"
    settings.mkdir()
    hooks = {
        event: [{"hooks": [{"type": "command", "command": CLAUDE_LIVE_WORK_COMMAND}]}] for event in ("SessionStart", "SessionEnd", "PreToolUse", "PostToolUse")
    }
    (settings / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    result = runner.invoke(app, ["matrix"])
    assert result.exit_code == 0, result.output


def test_install_and_uninstall_roundtrip(repo: Path) -> None:
    settings = repo / ".claude"
    settings.mkdir()
    (settings / "settings.json").write_text("{}", encoding="utf-8")
    installed = runner.invoke(app, ["install", "claude"])
    assert installed.exit_code == 0, installed.output
    payload = json.loads((settings / "settings.json").read_text(encoding="utf-8"))
    assert "SessionStart" in payload["hooks"]
    removed = runner.invoke(app, ["uninstall", "claude"])
    assert removed.exit_code == 0, removed.output
    payload = json.loads((settings / "settings.json").read_text(encoding="utf-8"))
    assert all(hook.get("command") != "spec-kitty live-work hook claude" for entries in payload["hooks"].values() for entry in entries for hook in entry["hooks"])
