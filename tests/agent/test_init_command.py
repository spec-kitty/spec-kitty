"""Scope: init command unit tests — no real git or subprocesses."""

from __future__ import annotations

import io
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console

from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command

pytestmark = pytest.mark.fast

@pytest.fixture()
def cli_app(monkeypatch: pytest.MonkeyPatch) -> tuple[Typer, Console, list[str]]:
    console = Console(file=io.StringIO(), force_terminal=False)
    outputs: list[str] = []
    app = Typer()

    def fake_show_banner():  # noqa: D401
        outputs.append("banner")

    def fake_activate(project_path: Path, mission_type: str, mission_display: str, _console: Console) -> str:
        outputs.append(f"activate:{mission_type}")
        return mission_display

    def fake_ensure_scripts(path: Path, tracker=None):  # noqa: D401
        outputs.append(f"scripts:{path}")

    register_init_command(
        app,
        console=console,
        show_banner=fake_show_banner,
        activate_mission=fake_activate,
        ensure_executable_scripts=fake_ensure_scripts,
    )
    return app, console, outputs


def _invoke(cli: Typer, args: list[str]) -> CliRunner:
    runner = CliRunner()
    result = runner.invoke(cli, args, catch_exceptions=False)
    if result.exit_code != 0:
        raise AssertionError(result.output)
    return runner


# =============================================================================
# VCS Detection and Configuration Tests
# =============================================================================


def test_init_creates_vcs_config(cli_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Init should create config.yaml with git vcs section."""
    app, console, outputs = cli_app
    monkeypatch.chdir(tmp_path)

    def fake_local_repo(override_path=None):
        return tmp_path / "templates"

    def fake_copy(local_repo: Path, project_path: Path):
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        return commands_dir

    monkeypatch.setattr(init_module, "get_local_repo_root", fake_local_repo)
    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)

    # Git available
    with patch.object(init_module, "is_git_available", return_value=True):
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "init",
                "config-project",
                "--ai",
                "claude",
                "--non-interactive",
            ],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"

    # Check config.yaml was created
    config_file = tmp_path / "config-project" / ".kittify" / "config.yaml"
    assert config_file.exists(), f"Config file not found at {config_file}"

    config = yaml.safe_load(config_file.read_text())
    assert "vcs" in config
    assert config["vcs"]["type"] == "git"


def test_init_non_interactive_requires_ai(cli_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    app, console, _ = cli_app
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "missing-ai",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 1
    console_output = console.file.getvalue()
    assert "--ai is required in non-interactive mode" in console_output


def test_init_non_interactive_no_project_name_defaults_to_current_directory(
    cli_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    app, console, _ = cli_app
    monkeypatch.chdir(tmp_path)

    def fake_local_repo(override_path=None):
        return tmp_path / "templates"

    def fake_copy(local_repo: Path, project_path: Path):
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        return commands_dir

    monkeypatch.setattr(init_module, "get_local_repo_root", fake_local_repo)
    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "--ai",
            "claude",
            "--non-interactive",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".templates").exists()
    console_output = console.file.getvalue()
    assert "Target Path" not in console_output


def test_init_non_interactive_env_var(cli_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    app, console, _ = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")

    def fake_local_repo(override_path=None):
        return tmp_path / "templates"

    def fake_copy(local_repo: Path, project_path: Path):
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        return commands_dir

    monkeypatch.setattr(init_module, "get_local_repo_root", fake_local_repo)
    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "env-non-interactive",
            "--ai",
            "claude",
        ],
    )
    assert result.exit_code == 0, result.output


def test_init_writes_event_log_merge_attributes(
    cli_app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    app, _, _ = cli_app
    monkeypatch.chdir(tmp_path)

    def fake_local_repo(override_path=None):
        return tmp_path / "templates"

    def fake_copy(local_repo: Path, project_path: Path):
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        return commands_dir

    monkeypatch.setattr(init_module, "get_local_repo_root", fake_local_repo)
    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "event-log-project",
            "--ai",
            "claude",
            "--non-interactive",
        ],
    )

    assert result.exit_code == 0, result.output
    attributes = (tmp_path / "event-log-project" / ".gitattributes").read_text(encoding="utf-8")
    assert "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log" in attributes
    assert "kitty-specs/**/status.json linguist-generated=true" in attributes
    assert "kitty-specs/**/tasks/** linguist-generated=true" in attributes
    assert "kitty-specs/**/research/evidence-log.csv linguist-generated=true" in attributes
    assert ".kittify/workspaces/** linguist-generated=true" in attributes
    assert ".kittify/workspaces/** -diff" in attributes
    assert ".kittify/migrations/** linguist-generated=true" in attributes
    assert ".kittify/migrations/** -diff" in attributes


@pytest.mark.parametrize(
    "git_failure",
    [
        FileNotFoundError("git"),
        subprocess.CalledProcessError(1, ["git", "config", "--local"]),
        UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte"),
    ],
)
def test_init_tolerates_merge_driver_git_config_failure(
    cli_app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    git_failure: OSError | subprocess.CalledProcessError | UnicodeError,
) -> None:
    """Regression #4159: optional git-config wiring must not abort init."""
    from specify_cli.lanes import merge as merge_module

    app, console, _ = cli_app
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: tmp_path / "templates")

    def fake_copy(local_repo: Path, project_path: Path) -> Path:
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        (project_path / ".git").mkdir()
        return commands_dir

    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)
    ensure_config = MagicMock(side_effect=git_failure)
    monkeypatch.setattr(merge_module, "_ensure_merge_driver_git_config", ensure_config)

    result = CliRunner().invoke(
        app,
        ["init", "git-optional-project", "--ai", "claude", "--non-interactive"],
    )

    assert result.exit_code == 0, result.output
    ensure_config.assert_called_once_with(tmp_path / "git-optional-project")
    warning = console.file.getvalue()
    assert "Could not configure Spec Kitty merge drivers" in warning
    assert str(git_failure) in warning
    assert (tmp_path / "git-optional-project" / ".kittify").is_dir()


def test_init_gitattributes_merge_driver_keys_have_git_config_registrations(
    cli_app,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """FIX-M2-01 / Finding 1: every ``merge=<key>`` driver ``init`` declares in
    ``.gitattributes`` must have a matching git-config *definition* -- the
    ``specify_cli.lanes.merge._MERGE_DRIVERS`` registry that
    ``_ensure_merge_driver_git_config`` (the self-heal every real merge path
    now calls: ``lanes/worktree_allocator.py``, ``lanes/auto_rebase.py``,
    ``lanes/merge.py::_merge_branch_into``) turns into real
    ``git config --local merge.<key>.driver`` entries.

    Before FIX-M2-01, ``init`` wrote the ``.gitattributes`` half but the two
    lane-worktree merges ``spec-kitty implement`` actually runs
    (``_merge_recorded_planning_commit`` / ``_merge_dependency_lane_tips``)
    never called the self-heal, so a fresh project could reach ``implement``
    with driver keys declared but never defined -- the merge silently fell
    back to a plain 3-way merge and conflicted deterministically. This test
    pins the two halves against drift in the OTHER direction (a key
    ``.gitattributes`` declares with no registry entry at all, which no
    self-heal call anywhere could ever satisfy) -- the runtime proof that a
    registered key actually reconciles a real merge lives in
    ``tests/lanes/test_worktree_allocator_merge_driver_selfheal.py`` (real
    git, per this module's own no-real-git scope note).
    """
    from specify_cli.lanes.merge import _MERGE_DRIVERS

    app, console, outputs = cli_app
    monkeypatch.chdir(tmp_path)

    def fake_local_repo(override_path=None):
        return tmp_path / "templates"

    def fake_copy(local_repo: Path, project_path: Path):
        commands_dir = project_path / ".templates"
        commands_dir.mkdir(parents=True, exist_ok=True)
        return commands_dir

    monkeypatch.setattr(init_module, "get_local_repo_root", fake_local_repo)
    monkeypatch.setattr(init_module, "copy_specify_base_from_local", fake_copy)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "merge-driver-coverage-project",
            "--ai",
            "claude",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 0, result.output

    attributes = (
        tmp_path / "merge-driver-coverage-project" / ".gitattributes"
    ).read_text(encoding="utf-8")

    declared_keys = set(re.findall(r"\bmerge=(\S+)", attributes))
    assert declared_keys, "expected at least one merge=<key> attribute entry"

    registered_keys = {spec.config_key for spec in _MERGE_DRIVERS}
    missing = declared_keys - registered_keys
    assert not missing, (
        f".gitattributes declares merge driver key(s) {sorted(missing)} with no "
        "matching specify_cli.lanes.merge._MERGE_DRIVERS entry -- the "
        "git-config self-heal (_ensure_merge_driver_git_config) can never "
        "register them, so any real merge routed through this attribute falls "
        "back to a plain 3-way merge and conflicts (FIX-M2-01)."
    )


def test_ensure_event_log_merge_attributes_preserves_existing_file(tmp_path: Path) -> None:
    attributes_path = tmp_path / ".gitattributes"
    original_line = "*.png binary"
    attributes_path.write_text(
        "\n".join(
            [
                original_line,
                "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    changed = init_module._ensure_event_log_merge_attributes(tmp_path)

    lines = attributes_path.read_text(encoding="utf-8").splitlines()
    assert changed is True
    assert lines[0] == original_line
    assert lines.count("kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log") == 1
    assert "kitty-specs/**/status.json linguist-generated=true" in lines
    assert ".kittify/migrations/** -diff" in lines


def test_ensure_event_log_merge_attributes_is_idempotent(tmp_path: Path) -> None:
    init_module._ensure_event_log_merge_attributes(tmp_path)

    changed = init_module._ensure_event_log_merge_attributes(tmp_path)

    lines = (tmp_path / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert changed is False
    assert lines.count("kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log") == 1
    assert lines.count(".kittify/workspaces/** -diff") == 1


# test_init_amends_initial_commit_after_cleanup deleted in feature 076:
# the initial git commit block was removed from init.py.


def test_init_rejects_removed_agent_strategy_option(cli_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    app, _, _ = cli_app
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "bad-strategy-option",
            "--ai",
            "codex",
            "--agent-strategy",
            "random",
            "--non-interactive",
        ],
    )
    assert result.exit_code == 2
    plain_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "No such option" in plain_output
    assert "--agent-strategy" in plain_output
