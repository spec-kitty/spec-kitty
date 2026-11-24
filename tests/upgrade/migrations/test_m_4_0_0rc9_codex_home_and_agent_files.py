"""The two clone-local #7729 steps: Codex home exclusion and the agent-folder notice.

- ``4.0.0rc9_exclude_project_local_codex_home`` adds the project's ``.codex/`` to
  the clone's ``.git/info/exclude`` (anchored at the project) when it is a Codex
  home git shows files from; it settles only once it has excluded one.
- ``4.0.0rc9_report_newly_visible_agent_files`` lists, once per clone, the
  untracked files git shows in agent folders, leaving a Codex home's own out.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.agent_utils import codex_home
from specify_cli.agent_utils.codex_home import is_codex_home
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import GitignoreManager
from specify_cli.upgrade.migrations import m_4_0_0rc9_exclude_project_local_codex_home as exclusion
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations import m_4_0_0rc9_report_newly_visible_agent_files as notice
from specify_cli.upgrade.migrations.m_4_0_0rc9_exclude_project_local_codex_home import ExcludeProjectLocalCodexHomeMigration
from specify_cli.upgrade.migrations.m_4_0_0rc9_report_newly_visible_agent_files import ReportNewlyVisibleAgentFilesMigration

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_ROOT_RULE = "/.codex/"
_GIT = ("-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false")


@pytest.fixture(autouse=True)
def _no_codex_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _narrowed(project: Path) -> Path:
    """A project with the committed agent-files block for codex and cursor."""
    (project / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(project, AgentConfig(available=["codex", "cursor"]))
    assert GitignoreManager(project).protect_all_agents().success
    return project


def _project(tmp_path: Path) -> Path:
    return _narrowed(_init(tmp_path))


def _write(project: Path, *paths: str) -> None:
    for rel in paths:
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")


def _exclude_lines(repo: Path) -> list[str]:
    exclude = repo / ".git" / "info" / "exclude"
    return exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []


def _untracked(repo: Path, *prefixes: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "-uall"], check=True, capture_output=True, text=True).stdout
    wanted = prefixes or (".codex/", ".cursor/")
    return sorted(line[3:] for line in out.splitlines() if line.startswith("?? ") and line[3:].startswith(wanted))


class TestIdentity:
    @pytest.mark.parametrize(
        ("migration", "migration_id"),
        [
            (ExcludeProjectLocalCodexHomeMigration(), "4.0.0rc9_exclude_project_local_codex_home"),
            (ReportNewlyVisibleAgentFilesMigration(), "4.0.0rc9_report_newly_visible_agent_files"),
        ],
    )
    def test_identity_and_routing(self, migration: BaseMigration, migration_id: str) -> None:
        assert migration.migration_id == migration_id
        assert migration.target_version == "4.0.0rc9"
        assert migration.clone_local_effect is True
        assert migration.requires_git_repository is False


class TestCodexHomeExclusion:
    def test_codex_home_is_excluded_in_this_clone(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml")
        migration = ExcludeProjectLocalCodexHomeMigration()
        assert _untracked(project) == [".codex/config.toml"]  # the committed block leaves config.toml to the clone
        assert migration.detect(project)

        result = migration.apply(project)

        assert result.success, result.errors
        assert _ROOT_RULE in _exclude_lines(project)
        assert _untracked(project) == []
        assert result.changes_made == [f"Added {_ROOT_RULE} to .git/info/exclude (this clone's .codex/ is a Codex home)"]
        assert any("Codex home" in warning for warning in result.warnings)
        assert not migration.detect(project)  # settled: nothing shows any more

    def test_apply_is_idempotent(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/auth.json", ".codex/config.toml")
        migration = ExcludeProjectLocalCodexHomeMigration()

        migration.apply(project)
        second = migration.apply(project)

        assert second.success
        assert _exclude_lines(project).count(_ROOT_RULE) == 1
        assert second.changes_made == ["No Codex home to exclude in this clone"]

    def test_plain_project_codex_folder_is_not_detected(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/config.toml", ".cursor/rules/team.md")

        assert not ExcludeProjectLocalCodexHomeMigration().detect(project)
        assert _ROOT_RULE not in _exclude_lines(project)

    def test_a_clone_without_a_codex_home_is_not_settled(self, tmp_path: Path) -> None:
        """Review finding 3: with no Codex home the step is not applicable, so a later one is still excluded."""
        project = _project(tmp_path)
        _write(project, ".cursor/rules/team.md")
        migration = ExcludeProjectLocalCodexHomeMigration()
        assert not migration.detect(project)  # the runner records nothing that settles it

        _write(project, ".codex/version.json", ".codex/config.toml")  # the clone gets a Codex home later

        assert migration.detect(project)
        assert migration.apply(project).success
        assert _untracked(project, ".codex/") == []

    def test_codex_home_env_marks_a_folder_without_markers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/config.toml")
        monkeypatch.setenv("CODEX_HOME", str(project / ".codex"))

        assert ExcludeProjectLocalCodexHomeMigration().apply(project).success

        assert _ROOT_RULE in _exclude_lines(project)
        assert _untracked(project) == []

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml")
        before = _exclude_lines(project)

        result = ExcludeProjectLocalCodexHomeMigration().apply(project, dry_run=True)

        assert result.success
        assert _exclude_lines(project) == before
        assert result.changes_made == [f"Would add {_ROOT_RULE} to .git/info/exclude (this clone's .codex/ is a Codex home)"]

    def test_tracked_team_files_stay_tracked(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/config.toml")
        subprocess.run(["git", "-C", str(project), *_GIT, "add", ".codex/config.toml", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(project), *_GIT, "commit", "-q", "-m", "team config"], check=True)
        _write(project, ".codex/version.json", ".codex/logs_2.sqlite", ".codex/new-team-file.md")

        assert ExcludeProjectLocalCodexHomeMigration().apply(project).success

        tracked = subprocess.run(["git", "-C", str(project), "ls-files"], check=True, capture_output=True, text=True).stdout.split()
        assert ".codex/config.toml" in tracked
        assert _untracked(project) == []

    def test_project_below_the_repository_root_gets_an_anchored_rule(self, tmp_path: Path) -> None:
        """Review finding 2: paths are compared from the repository root; a sibling project's team .codex/ stays visible."""
        repo = _init(tmp_path / "repo")
        project = _narrowed(repo / "svc-a")
        sibling = _narrowed(repo / "svc-b")
        _write(project, ".codex/version.json", ".codex/config.toml")
        _write(sibling, ".codex/config.toml")
        migration = ExcludeProjectLocalCodexHomeMigration()
        assert migration.detect(project)

        result = migration.apply(project)

        assert result.success, result.errors
        assert "/svc-a/.codex/" in _exclude_lines(repo)
        assert _untracked(repo, "svc-a/.codex/") == []
        assert _untracked(repo, "svc-b/.codex/") == ["svc-b/.codex/config.toml"]

    def test_a_failed_exclude_write_is_a_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Review finding 4: the step never claims a rule it did not write."""
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml")
        monkeypatch.setattr(exclusion, "exclude_from_git_index", lambda *_args, **_kwargs: None)  # swallowed OSError

        result = ExcludeProjectLocalCodexHomeMigration().apply(project)

        assert not result.success
        assert "Could not write /.codex/ to .git/info/exclude" in result.errors[0]
        assert not result.changes_made

    @pytest.mark.parametrize("negation", ["!.codex/", "!/.codex/"])
    def test_an_operator_rule_that_unignores_the_folder_wins_without_failing(self, tmp_path: Path, negation: str) -> None:
        """Review cycle 2, N1: an operator's own whole-folder negation is respected; no upgrade fails over it."""
        project = _project(tmp_path)
        with (project / ".gitignore").open("a", encoding="utf-8") as handle:
            handle.write(f"{negation}\n")
        _write(project, ".codex/version.json", ".codex/config.toml")
        migration = ExcludeProjectLocalCodexHomeMigration()

        first = migration.apply(project)
        second = migration.apply(project)

        for result in (first, second):
            assert result.success, result.errors
            assert result.manual_review_required
            assert "a rule of your own in a .gitignore un-ignores" in result.warnings[0]
        assert _exclude_lines(project).count(_ROOT_RULE) == 1
        assert ".codex/config.toml" in _untracked(project)  # the operator's rule decides

    @pytest.mark.parametrize("folder", ["foo[1]", "a*b", "what?", "back\\slash"])
    def test_a_project_path_with_glob_characters_is_excluded(self, tmp_path: Path, folder: str) -> None:
        """Review cycle 3, F1(a): the written rule escapes gitignore glob characters, so it matches the project."""
        repo = _init(tmp_path / "repo")
        project = _narrowed(repo / "apps" / folder)
        _write(project, ".codex/version.json", ".codex/config.toml")

        result = ExcludeProjectLocalCodexHomeMigration().apply(project)

        assert result.success, result.errors
        assert _untracked(repo, f"apps/{folder}/.codex/") == []
        assert "un-ignores" not in " ".join(result.warnings)

    def test_files_still_visible_without_an_operator_negation_is_a_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Review cycle 3, F1(b): only a proven operator negation turns 'still visible' into a warning."""
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml")

        # The rule reads as written but matches nothing (as an unescaped glob would); no operator rule exists.
        monkeypatch.setattr(exclusion, "exclude_from_git_index", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(exclusion, "_exclude_has_rule", lambda _project, _rule: True)

        result = ExcludeProjectLocalCodexHomeMigration().apply(project)

        assert not result.success
        assert "does not hide" in result.errors[0]
        assert ".codex/config.toml" in _untracked(project)

    @pytest.mark.parametrize(
        ("path", "pattern"),
        [
            (".codex/", ".codex/"),
            ("apps/foo[1]/.codex/", "apps/foo\\[1\\]/.codex/"),
            ("a*b?/.codex/", "a\\*b\\?/.codex/"),
            ("back\\slash/.codex/", "back\\\\slash/.codex/"),
            ("trailing ", "trailing\\ "),
        ],
    )
    def test_escape_gitignore(self, path: str, pattern: str) -> None:
        assert exclusion._escape_gitignore(path) == pattern

    def test_the_negation_probe_reads_a_failed_git_call_as_unproven(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = _project(tmp_path)

        def _fail(*_args: object, **_kwargs: object) -> object:
            raise OSError("git missing")

        monkeypatch.setattr(exclusion, "run_git", _fail)
        assert not exclusion._exclude_alone_hides(project, ".codex/")
        monkeypatch.setattr(exclusion, "git_exclude_file", lambda _path: None)
        assert not exclusion._exclude_alone_hides(project, ".codex/")

    def test_a_narrow_negation_is_pre_empted_by_the_folder_rule(self, tmp_path: Path) -> None:
        """Review cycle 2, N2 (a recorded choice): git never descends into the excluded Codex home."""
        project = _project(tmp_path)
        with (project / ".gitignore").open("a", encoding="utf-8") as handle:
            handle.write("!.codex/config.toml\n")
        _write(project, ".codex/version.json", ".codex/config.toml")

        result = ExcludeProjectLocalCodexHomeMigration().apply(project)

        assert result.success, result.errors
        assert _untracked(project) == []
        assert "git add -f" in result.warnings[0]

    def test_an_unreadable_exclude_file_reads_as_not_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(exclusion, "git_exclude_file", lambda _path: None)

        assert not exclusion._exclude_has_rule(tmp_path, _ROOT_RULE)

    def test_an_exclude_file_read_error_reads_as_not_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        directory = tmp_path / "exclude-is-a-directory"
        directory.mkdir()
        monkeypatch.setattr(exclusion, "git_exclude_file", lambda _path: directory)

        assert not exclusion._exclude_has_rule(tmp_path, _ROOT_RULE)

    def test_outside_a_repository_nothing_happens(self, tmp_path: Path) -> None:
        migration = ExcludeProjectLocalCodexHomeMigration()
        _write(tmp_path, ".codex/version.json")

        assert not migration.detect(tmp_path)
        assert migration.can_apply(tmp_path) == (False, "Not a git repository")
        assert migration.apply(tmp_path).changes_made == ["Skipped: not a git repository"]
        assert exclusion.codex_dir_from_root(tmp_path) is None

    def test_can_apply_in_a_repository(self, tmp_path: Path) -> None:
        assert ExcludeProjectLocalCodexHomeMigration().can_apply(_project(tmp_path)) == (True, "")

    def test_a_failed_git_read_shows_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml")

        def _fail(*_args: object, **_kwargs: object) -> tuple[()]:
            raise OSError("git missing")

        monkeypatch.setattr(exclusion, "status_entries", _fail)

        assert not ExcludeProjectLocalCodexHomeMigration().detect(project)


class TestNewlyVisibleNotice:
    def test_lists_team_files_once(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/config.toml", ".cursor/rules/team.md")
        migration = ReportNewlyVisibleAgentFilesMigration()
        assert migration.detect(project)

        result = migration.apply(project)

        assert result.success
        assert result.manual_review_required
        assert len(result.warnings) == 1
        assert ".codex/config.toml" in result.warnings[0]
        assert ".cursor/rules/team.md" in result.warnings[0]
        assert "git add" not in result.warnings[0]  # test_commit_scope_owner reads a quoted git command as a commit route
        assert _ROOT_RULE not in _exclude_lines(project)  # the notice writes nothing

    def test_a_codex_home_is_never_listed(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/version.json", ".codex/config.toml", ".cursor/rules/team.md")

        for dry_run in (True, False):
            warning = ReportNewlyVisibleAgentFilesMigration().apply(project, dry_run=dry_run).warnings[0]
            assert ".cursor/rules/team.md" in warning
            assert ".codex/" not in warning

    def test_dry_run_says_would(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".cursor/rules/team.md")

        result = ReportNewlyVisibleAgentFilesMigration().apply(project, dry_run=True)

        assert result.changes_made == ["Would list the untracked files git shows in agent folders"]

    def test_nothing_to_show_is_not_detected(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        _write(project, ".codex/auth.json", ".codex/sessions/s.jsonl")  # all ignored by the committed block
        migration = ReportNewlyVisibleAgentFilesMigration()

        assert not migration.detect(project)
        assert migration.apply(project).changes_made == ["No untracked files in agent folders"]

    def test_no_agent_folder_runs_no_git_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = _project(tmp_path)

        def _boom(*_args: object, **_kwargs: object) -> tuple[()]:
            raise AssertionError("git status must not run without an agent folder")

        monkeypatch.setattr(notice, "status_entries", _boom)

        assert not ReportNewlyVisibleAgentFilesMigration().detect(project)

    def test_a_failed_git_read_shows_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = _project(tmp_path)
        _write(project, ".cursor/rules/team.md")

        def _fail(*_args: object, **_kwargs: object) -> tuple[()]:
            raise OSError("git missing")

        monkeypatch.setattr(notice, "status_entries", _fail)

        assert not ReportNewlyVisibleAgentFilesMigration().detect(project)

    def test_outside_a_repository_nothing_happens(self, tmp_path: Path) -> None:
        migration = ReportNewlyVisibleAgentFilesMigration()
        _write(tmp_path, ".cursor/rules/team.md")

        assert not migration.detect(tmp_path)
        assert migration.can_apply(tmp_path) == (False, "Not a git repository")
        assert migration.apply(tmp_path).changes_made == ["Skipped: not a git repository"]

    def test_can_apply_in_a_repository(self, tmp_path: Path) -> None:
        assert ReportNewlyVisibleAgentFilesMigration().can_apply(_project(tmp_path)) == (True, "")

    def test_long_listing_is_truncated(self) -> None:
        paths = [f".claude/f{i:02}.md" for i in range(25)]

        warning = notice._visibility_warning(paths)

        assert warning is not None
        assert "25 untracked file(s)" in warning
        assert ".claude/f19.md" in warning
        assert ".claude/f20.md" not in warning
        assert "and 5 more" in warning
        assert notice._visibility_warning([]) is None


class TestCodexHomeEdges:
    def test_unreadable_codex_folder_is_not_a_codex_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / ".codex").mkdir()

        def _unreadable(_self: Path) -> object:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "iterdir", _unreadable)

        assert not is_codex_home(tmp_path, environ={})

    def test_unresolvable_codex_home_env_is_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        folder = tmp_path / ".codex"
        folder.mkdir()

        def _unresolvable(_self: Path, strict: bool = False) -> Path:
            raise OSError("loop")

        monkeypatch.setattr(Path, "resolve", _unresolvable)

        assert not codex_home._codex_home_env_points_at(folder, {"CODEX_HOME": str(folder)})
