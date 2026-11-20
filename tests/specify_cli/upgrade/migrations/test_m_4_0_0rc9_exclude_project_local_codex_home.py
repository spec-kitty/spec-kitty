"""``4.0.0rc9_exclude_project_local_codex_home``: per-clone Codex home exclusion and agent-folder notice (#7729)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.agent_utils import codex_home
from specify_cli.agent_utils.codex_home import is_codex_home
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import GitignoreManager
from specify_cli.upgrade.migrations import m_4_0_0rc9_exclude_project_local_codex_home as module
from specify_cli.upgrade.migrations.m_4_0_0rc9_exclude_project_local_codex_home import (
    MIGRATION_ID,
    ExcludeProjectLocalCodexHomeMigration,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_EXCLUDE_RULE = ".codex/"


@pytest.fixture(autouse=True)
def _no_codex_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)


def _project(tmp_path: Path) -> Path:
    """A narrowed project: the committed agent-files block for codex and cursor."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["codex", "cursor"]))
    assert GitignoreManager(tmp_path).protect_all_agents().success
    return tmp_path


def _write(project: Path, *paths: str) -> None:
    for rel in paths:
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")


def _exclude_lines(project: Path) -> list[str]:
    return (project / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()


def _untracked(project: Path) -> list[str]:
    """Untracked files git shows in the agent folders this fixture writes."""
    out = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "-uall"], check=True, capture_output=True, text=True).stdout
    return sorted(line[3:] for line in out.splitlines() if line.startswith("?? ") and line[3:].startswith((".codex/", ".cursor/")))


def test_identity_and_routing() -> None:
    migration = ExcludeProjectLocalCodexHomeMigration()

    assert migration.migration_id == MIGRATION_ID == "4.0.0rc9_exclude_project_local_codex_home"
    assert migration.target_version == "4.0.0rc9"
    assert migration.clone_local_effect is True
    assert migration.requires_git_repository is False


def test_codex_home_is_excluded_in_this_clone(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/version.json", ".codex/config.toml")
    migration = ExcludeProjectLocalCodexHomeMigration()
    assert _untracked(project) == [".codex/config.toml"]  # the committed block leaves config.toml to the clone
    assert migration.detect(project)

    result = migration.apply(project)

    assert result.success
    assert _EXCLUDE_RULE in _exclude_lines(project)
    assert _untracked(project) == []
    assert any("Codex home" in warning for warning in result.warnings)
    assert not result.manual_review_required  # nothing is left for the operator to review
    assert not migration.detect(project)  # settled: nothing shows any more


def test_apply_is_idempotent(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/auth.json", ".codex/config.toml")
    migration = ExcludeProjectLocalCodexHomeMigration()

    migration.apply(project)
    second = migration.apply(project)

    assert second.success
    assert _exclude_lines(project).count(_EXCLUDE_RULE) == 1
    assert second.changes_made == ["No Codex home to exclude in this clone"]


def test_plain_project_codex_folder_is_not_excluded_but_listed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/config.toml", ".cursor/rules/team.md")
    migration = ExcludeProjectLocalCodexHomeMigration()
    assert migration.detect(project)

    result = migration.apply(project)

    assert result.success
    assert _EXCLUDE_RULE not in _exclude_lines(project)
    assert _untracked(project) == [".codex/config.toml", ".cursor/rules/team.md"]
    assert result.manual_review_required
    assert len(result.warnings) == 1
    assert ".codex/config.toml" in result.warnings[0]
    assert ".cursor/rules/team.md" in result.warnings[0]


def test_codex_home_env_marks_a_folder_without_markers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/config.toml")
    monkeypatch.setenv("CODEX_HOME", str(project / ".codex"))

    result = ExcludeProjectLocalCodexHomeMigration().apply(project)

    assert _EXCLUDE_RULE in _exclude_lines(project)
    assert _untracked(project) == []
    assert result.success


def test_dry_run_writes_nothing_and_previews(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/version.json", ".codex/config.toml", ".cursor/rules/team.md")
    before = _exclude_lines(project)

    result = ExcludeProjectLocalCodexHomeMigration().apply(project, dry_run=True)

    assert result.success
    assert _exclude_lines(project) == before
    assert result.changes_made[0].startswith("Would add .codex/")
    listing = result.warnings[-1]
    assert ".cursor/rules/team.md" in listing
    assert ".codex/config.toml" not in listing  # the preview drops what the exclusion would hide


def test_tracked_team_files_stay_tracked(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/config.toml")
    git = ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "add", ".codex/config.toml", ".gitignore"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "team config"], check=True)
    _write(project, ".codex/version.json", ".codex/logs_2.sqlite", ".codex/new-team-file.md")

    ExcludeProjectLocalCodexHomeMigration().apply(project)

    tracked = subprocess.run([*git, "ls-files"], check=True, capture_output=True, text=True).stdout.split()
    assert ".codex/config.toml" in tracked
    assert _untracked(project) == []


def test_nothing_to_show_is_not_detected(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/auth.json", ".codex/sessions/s.jsonl")  # all ignored by the committed block

    assert not ExcludeProjectLocalCodexHomeMigration().detect(project)


def test_no_agent_folder_runs_no_git_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> tuple[()]:
        raise AssertionError("git status must not run without an agent folder")

    monkeypatch.setattr(module, "status_entries", _boom)

    assert not ExcludeProjectLocalCodexHomeMigration().detect(project)


def test_a_failed_git_read_shows_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    _write(project, ".codex/config.toml")

    def _fail(*_args: object, **_kwargs: object) -> tuple[()]:
        raise OSError("git missing")

    monkeypatch.setattr(module, "status_entries", _fail)

    assert not ExcludeProjectLocalCodexHomeMigration().detect(project)


def test_not_a_git_repository(tmp_path: Path) -> None:
    migration = ExcludeProjectLocalCodexHomeMigration()
    _write(tmp_path, ".codex/version.json")

    assert not migration.detect(tmp_path)
    assert migration.can_apply(tmp_path) == (False, "Not a git repository")
    result = migration.apply(tmp_path)
    assert result.success
    assert result.changes_made == ["Skipped: not a git repository"]


def test_can_apply_in_a_repository(tmp_path: Path) -> None:
    assert ExcludeProjectLocalCodexHomeMigration().can_apply(_project(tmp_path)) == (True, "")


def test_long_listing_is_truncated() -> None:
    paths = [f".claude/f{i:02}.md" for i in range(25)]

    warning = module._visibility_warning(paths)

    assert warning is not None
    assert "25 untracked file(s)" in warning
    assert ".claude/f19.md" in warning
    assert ".claude/f20.md" not in warning
    assert "and 5 more" in warning
    assert module._visibility_warning([]) is None


def test_unreadable_codex_folder_is_not_a_codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".codex").mkdir()

    def _unreadable(_self: Path) -> object:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "iterdir", _unreadable)

    assert not is_codex_home(tmp_path, environ={})


def test_unresolvable_codex_home_env_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / ".codex"
    folder.mkdir()

    def _unresolvable(_self: Path, strict: bool = False) -> Path:
        raise OSError("loop")

    monkeypatch.setattr(Path, "resolve", _unresolvable)

    assert not codex_home._codex_home_env_points_at(folder, {"CODEX_HOME": str(folder)})
