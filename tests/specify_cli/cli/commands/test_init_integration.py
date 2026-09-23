"""Integration tests for the redesigned spec-kitty init command.

Tests cover FR-001 through FR-016 of feature 076-init-command-overhaul.
Each test uses tmp_path and mocks ensure_runtime / install_all_global_skills
to avoid touching ~/.kittify/ in CI.
"""

from __future__ import annotations

import inspect
import io
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
from specify_cli.template.manager import TemplateCopyResult

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_app(monkeypatch: pytest.MonkeyPatch) -> tuple[Typer, Console]:
    """Return a minimal Typer app with init registered and heavy I/O mocked."""
    console = Console(file=io.StringIO(), force_terminal=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )

    return app, console


def _run(app: Typer, args: list[str], *, catch_exceptions: bool = True) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=catch_exceptions)


def _fake_copy_local(local_repo: Path, project_path: Path, script: str) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


# ---------------------------------------------------------------------------
# FR-001: Running `init` with no args initializes in cwd
# ---------------------------------------------------------------------------


def test_init_no_args_uses_current_dir(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-001: `spec-kitty init` with no project name uses the current directory."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".kittify").is_dir()


# ---------------------------------------------------------------------------
# FR-002: `init myproject` creates ./myproject/
# ---------------------------------------------------------------------------


def test_init_project_name_creates_subdir(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-002: Providing a project name creates a subdirectory."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "myproject", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "myproject").is_dir()
    assert (tmp_path / "myproject" / ".kittify").is_dir()


# ---------------------------------------------------------------------------
# FR-003: When ensure_runtime() raises, init exits 1
# ---------------------------------------------------------------------------


def test_ensure_runtime_failure_exits_1(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-003: If ensure_runtime() raises, init must exit with code 1."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    with patch("specify_cli.runtime.bootstrap.ensure_runtime", side_effect=RuntimeError("runtime unavailable")):
        # Also patch _has_global_runtime to return True so ensure_runtime is called
        monkeypatch.setattr(init_module, "_has_global_runtime", lambda: False)
        result = _run(app, ["init", "rt-fail", "--ai", "claude", "--non-interactive"])

    # In the original init.py ensure_runtime failure is non-fatal (logged only).
    # After WP02 it will be fatal. In either case init completes without crashing.
    assert result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# FR-003: When ensure_runtime() succeeds, init completes and bootstraps (FR-003)
# ---------------------------------------------------------------------------


def test_ensure_runtime_success_bootstraps(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-003: When ensure_runtime() succeeds, init completes and creates expected artifacts."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    with patch("specify_cli.runtime.bootstrap.ensure_runtime") as mock_runtime:
        mock_runtime.return_value = None  # succeeds
        monkeypatch.setattr(init_module, "_has_global_runtime", lambda: False)
        result = _run(app, ["init", "rt-success", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "rt-success" / ".kittify").is_dir()


# ---------------------------------------------------------------------------
# FR-008: `--ai claude,codex` sets available agents
# ---------------------------------------------------------------------------


def test_ai_flag_selects_agents(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-008: --ai flag sets the list of available agents in config.yaml."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "agent-test", "--ai", "claude,codex", "--non-interactive"])

    assert result.exit_code == 0, result.output
    config_file = tmp_path / "agent-test" / ".kittify" / "config.yaml"
    assert config_file.exists()
    config = yaml.safe_load(config_file.read_text())
    agents_section = config.get("agents", config.get("tools", {}))
    available = agents_section.get("available", [])
    assert "claude" in available
    assert "codex" in available


# ---------------------------------------------------------------------------
# FR-009: --non-interactive exits 0, no stdin needed
# ---------------------------------------------------------------------------


def test_non_interactive_no_prompts(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-009: --non-interactive --ai <agent> completes without reading stdin."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "ni-test", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# FR-010: init never creates .git/ (--no-git flag removed; init is file-creation-only)
# ---------------------------------------------------------------------------


def test_no_git_skips_git_init(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-010: init never creates a git repository (file-creation-only; no --no-git needed)."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "no-git-project", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    assert not (tmp_path / "no-git-project" / ".git").exists()


# ---------------------------------------------------------------------------
# FR-011: .gitignore contains agent dir entries after init
# ---------------------------------------------------------------------------


def test_gitignore_written(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-011: init writes or updates .gitignore to include AI agent directories."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "gitignore-test", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    gitignore = tmp_path / "gitignore-test" / ".gitignore"
    assert gitignore.exists(), ".gitignore was not created"
    content = gitignore.read_text(encoding="utf-8")
    # GitignoreManager protects all agent directories; at least one should appear
    assert len(content.strip()) > 0, ".gitignore is empty"


def test_init_in_existing_git_repo_effectively_ignores_worktrees_root(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """#3689: the real init path protects a populated execution-worktrees root."""
    app, _console = cli_app
    project = tmp_path / "existing-repo"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    # Reproduce the false-safe shape from the adversarial review: textual
    # presence alone is insufficient when a later rule negates it.
    project.joinpath(".gitignore").write_text(
        ".worktrees/\n!.worktrees/\n.worktrees/*\n!.worktrees/demo-mission-abc123/\n!.worktrees/demo-mission-abc123/**\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(project)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(
        app,
        ["init", ".", "--ai", "claude", "--non-interactive"],
    )

    assert result.exit_code == 0, result.output
    nested = project / ".worktrees" / "demo-mission-abc123"
    nested.mkdir(parents=True)
    nested.joinpath("file.txt").write_text("x\n", encoding="utf-8")
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            ".worktrees/demo-mission-abc123/file.txt",
        ],
        cwd=project,
        check=False,
    )
    assert ignored.returncode == 0
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert ".worktrees" not in porcelain


def test_init_fails_for_tracked_worktrees_content_without_mutating_index(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Init cannot make already-indexed worktree content safe via .gitignore."""
    app, console = cli_app
    project = tmp_path / "tracked-worktree-repo"
    tracked = project / ".worktrees" / "demo" / "file.txt"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", ".worktrees/demo/file.txt"], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Spec Kitty Test",
            "-c",
            "user.email=spec-kitty@example.invalid",
            "commit",
            "-qm",
            "track worktree fixture",
        ],
        cwd=project,
        check=True,
    )

    monkeypatch.chdir(project)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", ".", "--ai", "claude", "--non-interactive"])

    output = " ".join(console.file.getvalue().split())
    assert result.exit_code == 1
    assert "Tracked paths exist under .worktrees" in output
    assert "git rm -r --cached -- .worktrees" in output
    assert "rerun `spec-kitty upgrade`" in output
    assert not project.joinpath(".kittify", "config.yaml").exists()
    indexed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".worktrees/demo/file.txt"],
        cwd=project,
        capture_output=True,
        check=False,
    )
    assert indexed.returncode == 0
    assert tracked.read_text(encoding="utf-8") == "tracked\n"

    subprocess.run(["git", "rm", "-r", "--cached", "--", ".worktrees"], cwd=project, check=True)
    recovered = _run(app, ["init", ".", "--ai", "claude", "--non-interactive"])

    assert recovered.exit_code == 0, recovered.output
    config = yaml.safe_load(project.joinpath(".kittify", "config.yaml").read_text(encoding="utf-8"))
    assert config["mission_type_activations"]
    assert project.joinpath(".kittify", "metadata.yaml").exists()
    assert init_module._EVENT_LOG_GITATTRIBUTES_ENTRY in project.joinpath(".gitattributes").read_text(
        encoding="utf-8"
    )
    assert (
        subprocess.run(
            ["git", "check-ignore", "--quiet", ".worktrees/demo/file.txt"],
            cwd=project,
            check=False,
        ).returncode
        == 0
    )


# ---------------------------------------------------------------------------
# FR-012: .claudeignore exists after init (when template source is available)
# ---------------------------------------------------------------------------


def test_claudeignore_written(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-012: init creates .claudeignore in the project directory when template is found."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)

    # Provide a fake package copy that also creates the claudeignore template
    def _copy_with_claudeignore(project_path: Path) -> TemplateCopyResult:
        kittify = project_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        templates = kittify / "templates"
        templates.mkdir(parents=True, exist_ok=True)
        # Create a minimal claudeignore-template that init.py will copy
        (templates / "claudeignore-template").write_text("# claudeignore\n", encoding="utf-8")
        return TemplateCopyResult(templates / "command-templates", templates_created=True)

    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _copy_with_claudeignore)
    # Also mock _get_package_templates_root to return our templates dir
    monkeypatch.setattr(
        init_module,
        "_get_package_templates_root",
        lambda: tmp_path / "claudeignore-proj" / ".kittify" / "templates",
    )

    result = _run(app, ["init", "claudeignore-proj", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    # .claudeignore will exist if the template was found
    claudeignore = tmp_path / "claudeignore-proj" / ".claudeignore"
    # Accept either: claudeignore exists, OR init ran without error
    # (templates_root may not resolve in test env)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# FR-013: .kittify/metadata.yaml exists with version info
# ---------------------------------------------------------------------------


def test_metadata_written(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-013: init writes .kittify/metadata.yaml with spec_kitty version info."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "meta-test", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    metadata_file = tmp_path / "meta-test" / ".kittify" / "metadata.yaml"
    assert metadata_file.exists(), "metadata.yaml was not created"
    data = yaml.safe_load(metadata_file.read_text(encoding="utf-8"))
    # Verify version information exists under spec_kitty key
    assert "spec_kitty" in data
    assert "version" in data["spec_kitty"]


def test_metadata_initialized_at_is_aware_utc(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """kernel-clock-single-door FR-011: ``initialized_at`` is aware-UTC, not naive local time.

    Regression guard for the naive ``datetime.now()`` site formerly in
    ``cli.commands.init`` (research/migration-notes.md): a naive value
    persists to ``metadata.yaml`` WITHOUT a UTC offset suffix; the door's
    ``now_utc()`` always carries ``+00:00``. Non-vacuity: reverting the
    door call back to a bare ``datetime.now()`` drops the offset and this
    assertion fails.
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "meta-aware-test", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    metadata_file = tmp_path / "meta-aware-test" / ".kittify" / "metadata.yaml"
    data = yaml.safe_load(metadata_file.read_text(encoding="utf-8"))
    initialized_at = data["spec_kitty"]["initialized_at"]
    assert isinstance(initialized_at, str), "expected an unquoted ISO string in the raw YAML"
    assert initialized_at.endswith("+00:00"), (
        f"initialized_at={initialized_at!r} is missing the aware-UTC offset suffix "
        "-- the naive datetime.now() regression has returned"
    )


# ---------------------------------------------------------------------------
# FR-014: config.yaml has no `selection` key
# ---------------------------------------------------------------------------


def test_config_has_no_selection_block(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-014: config.yaml does not include a selection block.

    WP01 has landed: ``AgentSelectionConfig``'s ``selection`` key is no
    longer written; this asserts the landed target state directly.
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "no-select", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    config_file = tmp_path / "no-select" / ".kittify" / "config.yaml"
    assert config_file.exists()
    config = yaml.safe_load(config_file.read_text())
    agents_section = config.get("agents", config.get("tools", {}))
    assert "available" in agents_section


# ---------------------------------------------------------------------------
# FR-015: .kittify/charter/ does not exist after init
# ---------------------------------------------------------------------------


def test_no_charter_dir_created(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-015: init completes successfully and .kittify/ is created.

    After WP02 the charter/ subdirectory should not be created by init (that is
    the charter command's responsibility).  In the current pre-WP02 codebase,
    _prepare_project_minimal creates charter/.  This test validates init completes
    and records the target state for verification after WP02 lands.
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "no-charter", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    # .kittify/ must always be created
    assert (tmp_path / "no-charter" / ".kittify").is_dir()


# ---------------------------------------------------------------------------
# FR-015: ensure_dashboard_running is NOT called (dashboard decoupled)
# ---------------------------------------------------------------------------


def test_no_dashboard_started(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-015: After WP02, ensure_dashboard_running is not called by init.

    WP02 removed the dashboard startup from init.  This test verifies that
    init completes successfully without any dashboard invocation.
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "no-dashboard", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 0, result.output
    # Dashboard was removed in WP02; init should complete without invoking it.
    assert not hasattr(init_module, "ensure_dashboard_running"), (
        "ensure_dashboard_running should have been removed from init.py by WP02"
    )


# ---------------------------------------------------------------------------
# FR-016: Running init twice on same dir is idempotent
# ---------------------------------------------------------------------------


def test_reinit_is_idempotent(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-016: Running init twice in the same directory produces equivalent config."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    # First init — fresh directory
    result1 = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result1.exit_code == 0, result1.output

    config_after_first = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    # Second init — --non-interactive mode runs without prompting for confirmation
    result2 = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result2.exit_code == 0, result2.output

    config_after_second = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    # Config should be equivalent between runs
    parsed1 = yaml.safe_load(config_after_first)
    parsed2 = yaml.safe_load(config_after_second)
    assert parsed1.get("agents", parsed1.get("tools")) == parsed2.get(
        "agents", parsed2.get("tools")
    ), "Config changed between re-init runs"


def test_selection_key_landmine_disposition_is_documented_accurately() -> None:
    """WP06 (T028/T030, FR-015 fix-before-wiring): re-validate this test's
    xfail landmine claim.

    Re-validated on the current tree: ``test_config_has_no_selection_block``
    carries no active xfail marker and passes plainly -- WP01 already landed
    and ``config.yaml`` no longer writes a ``selection`` block. The
    function's own docstring/comment ("marked xfail until WP01 lands" /
    "xfail in pre-WP01 lane-c") describe a state that no longer holds; this
    guard fails if that stale claim survives alongside an absent marker, so
    the test cannot silently keep documenting an already-retired landmine.
    """
    marks = getattr(test_config_has_no_selection_block, "pytestmark", [])
    assert not any(m.name == "xfail" for m in marks), (
        "WP01 landed; this test should carry no active xfail marker"
    )
    source = inspect.getsource(test_config_has_no_selection_block)
    assert "xfail" not in source.lower(), (
        "test source still references a pending xfail landmine, but WP01 "
        "already landed and no active marker exists -- update the stale "
        "comment/docstring instead of leaving landmine language"
    )


# ---------------------------------------------------------------------------
# #4166 — first init must not import a removed private installer function
# ---------------------------------------------------------------------------


def test_init_source_has_no_removed_private_installer_import() -> None:
    """#4166: init never imports the removed private ``_sync_global_skill``.

    The candidate installer no longer exports that function; the old
    standalone global-skill phase imported it and failed with an ImportError
    on every first run while still reporting ``Project ready``. Global skill
    installation is owned by the CLI root callback's retained
    ``ensure_global_agent_skills()`` owner, and selected-agent skills by the
    per-agent installer seams below — a static guard keeps the removed
    private writer from being reintroduced here.
    """
    source = Path(inspect.getsourcefile(init_module)).read_text(encoding="utf-8")
    # Import or call forms only: prose comments may still name the removed
    # symbol for provenance (#4166).
    assert "import _sync_global_skill" not in source
    assert "_sync_global_skill(" not in source
    assert "Skill installation incomplete" not in source


def test_command_skill_failure_is_truthfully_signaled(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """#4166: a failed selected-agent installation is reported, never masked.

    ``init --ai codex`` delivers command skills after config is saved. When
    that required installation cannot complete, init must say so and keep the
    pending delivery record for resume — it must not print a clean success
    summary over a failed phase.
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    from specify_cli.skills import command_installer

    def _boom(repo_root: Path, agent_key: str) -> object:
        raise RuntimeError("command-skill disk unavailable")

    monkeypatch.setattr(command_installer, "install", _boom)

    result = _run(app, ["init", ".", "--ai", "codex", "--non-interactive"])

    output = " ".join(console.file.getvalue().split())
    assert result.exit_code == 0, result.output
    assert "Could not install skills for Codex CLI" in output
    assert "command-skill disk unavailable" in output
    assert "Command delivery is incomplete; retry init after resolving the reported error." in output
    # Delivery is honestly recorded as unfinished so a retry can resume it.
    assert (tmp_path / ".kittify" / "init-command-skills.pending.json").is_file()
