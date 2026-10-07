"""#5443 — what ``spec-kitty upgrade`` does after a failure, with ignored files, in a cold HOME, with held files.

Companion to ``test_upgrade_commit_scope_5443``: the P0-class holes the validation
squad found around the schema-3 migration's commit (a failed run still committed
its backup, an ignored secret reached history, a cold HOME suppressed the whole
commit, an upgraded worktree followed none of the main checkout's rules).
Everything runs through ``python -m specify_cli upgrade --yes`` in a hermetic sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.migration.schema_version import CURRENT_SCHEMA_VERSION
from specify_cli.upgrade import autocommit
from tests.upgrade._legacy_upgrade_fixture import (
    MARKED_COMMAND_FILE,
    HomeState,
    all_history_blob_text,
    build_legacy,
    commit_files,
    flat,
    git,
    head,
    new_commit_files,
    new_commits,
    run_upgrade,
    status_z,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_TOKEN = "tok-5443-secret"
_FAILED_RUN_REASON = getattr(
    autocommit,
    "FAILED_RUN_LEFT_UNCOMMITTED_WARNING",
    "The upgrade failed, so its changes were left uncommitted",
)
_IMPLEMENT = ".claude/commands/spec-kitty.implement.md"
_CUSTOM = ".claude/commands/spec-kitty.custom.md"
_CUSTOM_BODY = "# my own command\nhand written, no version marker\n"
_DEBRIS = {".migration-backup", "kitty-specs-backup", "gitignore-backup", "gitignore-absent"}
_WORKTREE = "001-demo-lane-a"


def _manual_review_paths(stdout: str) -> list[str]:
    """Paths listed under the "Manual review required:" section of the text report."""
    paths: list[str] = []
    in_section = False
    for line in stdout.splitlines():
        if line.strip() == "Manual review required:":
            in_section = True
            continue
        if in_section:
            if not line.strip():
                break
            paths.append(line.strip().lstrip("!").strip())
    return paths


def _kittify_names(project: Path) -> set[str]:
    return {entry.name for entry in (project / ".kittify").iterdir()}


@pytest.mark.p0_repro(issue=5443)
@pytest.mark.parametrize("ignore_setup", ["no-gitignore", "tracked-gitignore"])
def test_failed_upgrade_commits_nothing_and_cleans_up(tmp_path: Path, ignore_setup: str) -> None:
    gitignore = None if ignore_setup == "no-gitignore" else ".kittify/workspaces/\n"
    project, env = build_legacy(
        tmp_path,
        agents=["claude"],
        gitignore=gitignore,
        # A tracked regular file where the migration needs the ``.kittify/derived`` directory:
        # step 9 (move derived files) fails after step 8 wrote ``.gitignore`` and the shims.
        extra_files={
            ".kittify/derived": "not a directory\n",
            "kitty-specs/001-demo/status.json": "{}\n",
            **{_IMPLEMENT: MARKED_COMMAND_FILE},
        },
    )
    if ignore_setup == "no-gitignore":
        exclude = project / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(".kittify/workspaces/\n", encoding="utf-8")
    token = project / ".kittify" / "workspaces" / "token.json"
    token.parent.mkdir(parents=True)
    token.write_text(f'{{"token": "{_TOKEN}"}}\n', encoding="utf-8")
    assert git(project, env, "check-ignore", "-q", ".kittify/workspaces/token.json", check=False).returncode == 0
    head0 = head(project, env)
    before = _kittify_names(project)
    gitignore_before = (project / ".gitignore").read_bytes() if gitignore is not None else None

    result = run_upgrade(project, env)

    assert _TOKEN not in all_history_blob_text(project, env), "the ignored token reached history"
    assert "token.json" not in {path.rsplit("/", 1)[-1] for _status, path in new_commit_files(project, env, head0)}
    assert head(project, env) == head0, "a failed upgrade must commit nothing"
    assert flat(_FAILED_RUN_REASON) in flat(result.stdout + result.stderr)
    assert not (project / ".kittify" / ".migration-backup").exists()
    if gitignore_before is None:
        assert not (project / ".gitignore").exists()
    else:
        assert (project / ".gitignore").read_bytes() == gitignore_before
    after = _kittify_names(project)
    assert not (_DEBRIS & after)
    assert after <= before | {"skills-manifest.json"}


@pytest.mark.p0_repro(issue=5443)
def test_ignored_operator_file_is_never_committed(tmp_path: Path) -> None:
    ignore_lines = ".kittify/workspaces/\n.kittify/merge-state.json\n"
    project, env = build_legacy(tmp_path, agents=["claude"], gitignore=ignore_lines, extra_files={_IMPLEMENT: MARKED_COMMAND_FILE})
    token = project / ".kittify" / "workspaces" / "token.json"
    token.parent.mkdir(parents=True)
    token.write_text(f'{{"token": "{_TOKEN}"}}\n', encoding="utf-8")
    head0 = head(project, env)

    result = run_upgrade(project, env)

    committed = new_commit_files(project, env, head0)
    assert committed, "the upgrade's own work is still committed"
    assert not [path for _status, path in committed if path.startswith(".kittify/workspaces/")]
    assert _TOKEN not in all_history_blob_text(project, env)
    on_disk = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".kittify/workspaces/" in on_disk
    assert ".kittify/merge-state.json" in on_disk
    assert git(project, env, "check-ignore", "-q", ".kittify/workspaces/token.json", check=False).returncode == 0
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.p0_repro(issue=5443)
@pytest.mark.parametrize(
    ("agents", "home"),
    [
        pytest.param(["claude"], "cold", id="cold-home-configured-agent"),
        pytest.param([], "cold", id="cold-home-no-agents"),
        pytest.param(["claude"], "warm", id="warm-home-configured-agent"),
    ],
)
def test_clean_legacy_upgrade_commits(tmp_path: Path, agents: list[str], home: HomeState) -> None:
    project, env = build_legacy(tmp_path, agents=agents, gitignore="*.pyc\n", home=home, extra_files={_IMPLEMENT: MARKED_COMMAND_FILE})
    head0 = head(project, env)

    result = run_upgrade(project, env)

    revs = new_commits(project, env, head0)
    assert len(revs) == 1
    assert ".kittify/metadata.yaml" in {path for _status, path in commit_files(project, env, revs[0])}
    stamped = yaml.safe_load(git(project, env, "show", "HEAD:.kittify/metadata.yaml").stdout)
    assert stamped["spec_kitty"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "Manual review required" not in result.stdout
    assert status_z(project, env) == []
    if home == "warm":
        assert ("D", _IMPLEMENT) in commit_files(project, env, revs[0])
        assert not (project / _IMPLEMENT).exists()
    else:
        assert (project / _IMPLEMENT).exists()
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.p0_repro(issue=5443)
def test_customised_command_file_is_held_and_named(tmp_path: Path) -> None:
    project, env = build_legacy(
        tmp_path,
        agents=["claude"],
        gitignore="*.pyc\n",
        extra_files={_IMPLEMENT: MARKED_COMMAND_FILE, _CUSTOM: _CUSTOM_BODY},
    )
    head0 = head(project, env)

    result = run_upgrade(project, env)

    revs = new_commits(project, env, head0)
    assert len(revs) == 1, "the upgrade commits the rest even though one file is held"
    assert _CUSTOM not in {path for _status, path in new_commit_files(project, env, head0)}
    assert (project / _CUSTOM).read_text(encoding="utf-8") == _CUSTOM_BODY
    assert _manual_review_paths(result.stdout) == [_CUSTOM]
    assert "Skipped auto-commit" not in result.stdout
    assert f"Held for manual review (not committed): {_CUSTOM}" in flat(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr


def _add_worktree(project: Path, env: dict[str, str], files: dict[str, str]) -> Path:
    exclude = project / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(".worktrees/\n", encoding="utf-8")
    worktree = project / ".worktrees" / _WORKTREE
    git(project, env, "worktree", "add", "-q", "-b", "lane-a", str(worktree))
    for rel, content in files.items():
        target = worktree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(worktree, env, "add", "--", *sorted(files))
    git(worktree, env, "commit", "-q", "-m", "worktree additions")
    return worktree


@pytest.mark.p0_repro(issue=5443)
@pytest.mark.parametrize("case", ["worktree-failed-migration", "worktree-held-file"])
def test_upgraded_worktree_follows_main_rules(tmp_path: Path, case: str) -> None:
    project, env = build_legacy(tmp_path, agents=["claude"], gitignore="*.pyc\n", extra_files={_IMPLEMENT: MARKED_COMMAND_FILE})
    additions = {".kittify/derived": "not a directory\n"} if case == "worktree-failed-migration" else {_CUSTOM: _CUSTOM_BODY}
    worktree = _add_worktree(project, env, additions)
    tip0 = git(project, env, "rev-parse", "lane-a").stdout.strip()
    head0 = head(project, env)

    result = run_upgrade(project, env)
    output = flat(result.stdout + result.stderr)

    tip = git(project, env, "rev-parse", "lane-a").stdout.strip()
    if case == "worktree-failed-migration":
        assert tip == tip0, "a worktree whose migrations failed gets no commit"
        assert f"Worktree {_WORKTREE}: {flat(_FAILED_RUN_REASON)}" in output
        assert len(new_commits(project, env, head0)) == 1, "the main checkout's own commit is unaffected"
        return
    revs = git(project, env, "rev-list", "--reverse", f"{tip0}..lane-a").stdout.split()
    assert len(revs) == 1, "the worktree commits the rest even though one file is held"
    assert _CUSTOM not in {path for rev in revs for _status, path in commit_files(worktree, env, rev)}
    assert (worktree / _CUSTOM).read_text(encoding="utf-8") == _CUSTOM_BODY
    assert f"Worktree {_WORKTREE}: Held for manual review (not committed): {_CUSTOM}" in output
    assert f"Worktree {_WORKTREE}: Skipped auto-commit" not in output
