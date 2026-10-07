"""#5443 — ``spec-kitty upgrade`` on a legacy project commits only what it wrote.

Real-git reproduction through the pre-existing entry point (``python -m specify_cli
upgrade --yes`` in a hermetic sandbox, see ``_legacy_upgrade_fixture``). The
schema-3 migration runner used to ``git add -A`` and retry with ``--no-verify``;
every operator file in the checkout landed in the migration commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.migration.schema_version import CURRENT_SCHEMA_VERSION
from specify_cli.upgrade import autocommit
from tests.upgrade._legacy_upgrade_fixture import (
    MARKED_COMMAND_FILE,
    all_history_blob_text,
    build_legacy,
    flat,
    git,
    head,
    install_pre_commit_hook,
    new_commit_files,
    new_commits,
    run_upgrade,
    staged,
    status_z,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_SECRET = "s3cr3t-5443"
_MARKED = {".claude/commands/spec-kitty.implement.md": MARKED_COMMAND_FILE}


def _committed_schema_version(project: Path, env: dict[str, str]) -> object:
    text = git(project, env, "show", "HEAD:.kittify/metadata.yaml").stdout
    return yaml.safe_load(text)["spec_kitty"]["schema_version"]


@pytest.mark.p0_repro(issue=5443)
def test_upgrade_never_commits_operator_work(tmp_path: Path) -> None:
    project, env = build_legacy(
        tmp_path,
        agents=["claude"],
        gitignore=".kittify/workspaces/\n",
        extra_files=_MARKED,
    )
    (project / "secrets.env").write_text(f"TOKEN={_SECRET}\n", encoding="utf-8")
    (project / "src" / "staged.py").write_text("STAGED = True\n", encoding="utf-8")
    git(project, env, "add", "--", "src/staged.py")
    app_edit = "A = 1\nB = 2  # operator edit\n"
    (project / "src" / "app.py").write_text(app_edit, encoding="utf-8")
    git(project, env, "rm", "--cached", "-q", "--", "docs/old.md")
    gitignore_edit = ".kittify/workspaces/\noperator-only/\n"
    (project / ".gitignore").write_text(gitignore_edit, encoding="utf-8")
    head0 = head(project, env)
    staged0 = staged(project, env)
    assert staged0 == ["docs/old.md", "src/staged.py"]

    result = run_upgrade(project, env)

    committed = new_commit_files(project, env, head0)
    committed_paths = {path for _status, path in committed}
    # (a) the untracked secret is in no commit, not even under a backup path
    assert "secrets.env" not in committed_paths
    assert _SECRET not in all_history_blob_text(project, env)
    # (b) the operator's staged file is in no commit and is still staged
    assert "src/staged.py" not in committed_paths
    assert "src/staged.py" in staged(project, env)
    # (c) the unstaged edit survives on disk and is still unstaged
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == app_edit
    assert "src/app.py" not in committed_paths
    assert "src/app.py" in git(project, env, "diff", "--name-only").stdout.split()
    # (d) the operator's staged deletion stays staged and uncommitted
    assert ("D", "docs/old.md") not in committed
    assert git(project, env, "ls-tree", "HEAD", "docs/old.md").stdout.strip() != ""
    assert "docs/old.md" in staged(project, env)
    # (e) the file the operator had dirty and the migration also rewrote stays uncommitted with both contents
    assert ".gitignore" not in committed_paths
    on_disk = (project / ".gitignore").read_text(encoding="utf-8")
    assert "operator-only/" in on_disk
    assert ".kittify/derived/" in on_disk
    # (f) the upgrade's own work is committed, with the schema stamp
    assert ".kittify/metadata.yaml" in committed_paths
    assert _committed_schema_version(project, env) == CURRENT_SCHEMA_VERSION
    # (g) exactly one new commit
    assert len(new_commits(project, env, head0)) == 1
    # (h) success
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.p0_repro(issue=5443)
def test_rejecting_hook_is_honoured_and_never_bypassed(tmp_path: Path) -> None:
    project, env = build_legacy(tmp_path, agents=["claude"], gitignore="*.pyc\n", extra_files=_MARKED)
    counter = install_pre_commit_hook(project, tmp_path, reject=True)
    head0 = head(project, env)
    staged0 = staged(project, env)

    result = run_upgrade(project, env)

    assert head(project, env) == head0, "a rejecting hook must leave HEAD alone (no --no-verify retry)"
    assert counter.read_text(encoding="utf-8").splitlines() == ["x"], "the hook runs exactly once, for the upgrade's single attempt"
    assert flat(autocommit.UPGRADE_COMMIT_SKIP_WARNING) in flat(result.stdout)
    on_disk = yaml.safe_load((project / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
    assert on_disk["spec_kitty"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert any(path == ".kittify/metadata.yaml" and "M" in xy for xy, path in status_z(project, env))
    assert staged(project, env) == staged0


def test_accepting_hook_commits_normally(tmp_path: Path) -> None:
    project, env = build_legacy(tmp_path, agents=["claude"], gitignore="*.pyc\n", extra_files=_MARKED)
    counter = install_pre_commit_hook(project, tmp_path, reject=False)
    head0 = head(project, env)

    result = run_upgrade(project, env)

    assert len(new_commits(project, env, head0)) == 1
    assert counter.read_text(encoding="utf-8").splitlines() == ["x"]
    assert result.returncode == 0, result.stdout + result.stderr
