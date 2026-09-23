"""T1.6 — Regression tests: init inside an existing git repo leaves git state unchanged.

Verifies:
- Running init inside a repo with an existing commit leaves HEAD hash unchanged.
- git log still shows only the original commit (no new commit added).
- git status --porcelain shows only new init files (no modified tracked files).
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console  # noqa: F401  (used in _make_app helper)
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _make_app(monkeypatch: pytest.MonkeyPatch) -> Typer:
    out = io.StringIO()
    console = Console(file=out, force_terminal=False, highlight=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


def _git(*args: str, cwd: Path) -> str:
    """Run a git command and return its stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _setup_git_repo_with_commit(repo_path: Path) -> str:
    """Initialize a git repo and create one commit.  Return the HEAD hash."""
    _git("init", cwd=repo_path)
    _git("config", "user.email", "test@example.com", cwd=repo_path)
    _git("config", "user.name", "Test User", cwd=repo_path)

    readme = repo_path / "README.md"
    readme.write_text("# Test project\n", encoding="utf-8")

    _git("add", "README.md", cwd=repo_path)
    _git("-c", "commit.gpgsign=false", "commit", "-m", "initial user commit", cwd=repo_path)

    return _git("rev-parse", "HEAD", cwd=repo_path)


# ---------------------------------------------------------------------------
# T1.6: init inside existing repo does not touch git state
# ---------------------------------------------------------------------------

def test_init_does_not_touch_git_state_in_existing_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """T1.6: Running init inside an existing git repo leaves HEAD hash and history unchanged."""
    repo = tmp_path / "myrepo"
    repo.mkdir()

    # Set up a git repo with one commit
    head_before = _setup_git_repo_with_commit(repo)
    assert head_before, "HEAD hash should be non-empty after initial commit"

    commit_count_before = len(
        _git("log", "--oneline", cwd=repo).splitlines()
    )
    assert commit_count_before == 1, "Should have exactly 1 commit before init"

    # Run init inside the existing repo
    app = _make_app(monkeypatch)

    monkeypatch.chdir(repo)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "--ai", "codex", "--non-interactive"])
    assert result.exit_code == 0, f"init failed inside existing repo: {result.output}"

    # HEAD hash must be unchanged
    head_after = _git("rev-parse", "HEAD", cwd=repo)
    assert head_after == head_before, (
        f"HEAD changed after init!\n  before: {head_before}\n  after:  {head_after}\n"
        "init must not create any commits."
    )

    # Commit count must be unchanged
    commit_count_after = len(
        _git("log", "--oneline", cwd=repo).splitlines()
    )
    assert commit_count_after == commit_count_before, (
        f"Commit count changed from {commit_count_before} to {commit_count_after}.\n"
        "init must not create any git commits."
    )

    # Existing tracked files must be unmodified (README.md should be clean)
    porcelain = _git("status", "--porcelain", cwd=repo)
    modified_tracked = [
        line for line in porcelain.splitlines()
        if not line.startswith("?? ")  # untracked new files are expected
    ]
    assert modified_tracked == [], (
        "init modified existing tracked files:\n"
        + "\n".join(modified_tracked)
    )


# ---------------------------------------------------------------------------
# #4146: init installs the merge-driver git-config half, not just .gitattributes
# ---------------------------------------------------------------------------

def test_init_registers_merge_driver_git_config_in_existing_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """#4146: a fresh ``init`` inside an existing git repo installs BOTH halves
    of the merge-driver wiring -- the ``.gitattributes`` mapping (long-standing)
    and the ``git config --local merge.<key>.name`` / ``.driver`` definitions.

    Before #4146, init wrote only the attribute half; the union driver stayed
    inert (git fell back to a plain 3-way merge on the append-only event log)
    until the first merge/auto-rebase happened to self-heal the config -- by
    which time a lane claim could already have conflicted.
    """
    from specify_cli.lanes.merge import _MERGE_DRIVERS

    repo = tmp_path / "driver-config-repo"
    repo.mkdir()
    _setup_git_repo_with_commit(repo)

    # Precondition (the defect): no merge-driver config in a fresh repo.
    # ``--get-regexp`` exits 1 (with empty stdout) when nothing matches, so
    # this is a raw call, not the module's check=True ``_git`` helper.
    probe = subprocess.run(
        ["git", "config", "--local", "--get-regexp", r"merge\.spec-kitty"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 1 and probe.stdout.strip() == "", (
        "test precondition: fresh repo must start with no merge.spec-kitty config"
    )

    app = _make_app(monkeypatch)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "--ai", "codex", "--non-interactive"])
    assert result.exit_code == 0, f"init failed inside existing repo: {result.output}"

    # The attribute half (already covered elsewhere) plus the config half.
    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log" in attributes

    for spec in _MERGE_DRIVERS:
        name = _git(
            "config", "--local", "--get", f"merge.{spec.config_key}.name", cwd=repo
        )
        driver = _git(
            "config", "--local", "--get", f"merge.{spec.config_key}.driver", cwd=repo
        )
        assert name == spec.name, (
            f"init did not register merge.{spec.config_key}.name "
            f"(got {name!r}, expected {spec.name!r})"
        )
        assert driver == spec.command, (
            f"init did not register merge.{spec.config_key}.driver "
            f"(got {driver!r}, expected {spec.command!r})"
        )


def test_init_without_git_repo_does_not_fail_on_merge_driver_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """#4146: the git-config install is a guarded no-op when the target is not
    a git repository yet (the historical reason init never installed it) --
    init in a plain directory must still succeed.
    """
    project = tmp_path / "not-a-repo"
    # Deliberately NOT pre-created: init with an explicit project name refuses
    # an existing directory ("Directory Conflict"), so the non-git target must
    # be left for init itself to create.

    app = _make_app(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", str(project.name), "--ai", "codex", "--non-interactive"])
    assert result.exit_code == 0, f"init failed in non-git directory: {result.output}"
