"""#5443 / FR-022 -- the upgrade commit carries the migration's own ``git rm --cached``.

The 3.2.5 backfill ignores ``.agents/skills/`` and untracks what was already
committed there (``git rm --cached``; the file stays on disk). The upgrade
commit must record that removal, or the file stays tracked and ignored at once.
Real git through the ``spec-kitty upgrade --yes`` entry point, with a warm HOME
so the upgrade actually commits.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.upgrade._legacy_upgrade_fixture import (
    MARKED_COMMAND_FILE,
    build_legacy,
    git,
    head,
    install_pre_commit_hook,
    new_commit_files,
    new_commits,
    run_upgrade,
    staged,
    status_z,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_SKILL = ".agents/skills/demo/SKILL.md"
_SKILL_BYTES = "demo skill\n"
_EXTRA = {_SKILL: _SKILL_BYTES, ".claude/commands/spec-kitty.implement.md": MARKED_COMMAND_FILE}


def _legacy(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    return build_legacy(tmp_path, agents=["claude"], gitignore=".kittify/workspaces/\n", home="warm", extra_files=_EXTRA)


def test_upgrade_commits_migration_untrack(tmp_path: Path) -> None:
    project, env = _legacy(tmp_path)
    head0 = head(project, env)
    (project / "src" / "operator_staged.py").write_text("S = 1\n", encoding="utf-8")
    git(project, env, "add", "--", "src/operator_staged.py")
    counter = install_pre_commit_hook(project, tmp_path, reject=False)

    result = run_upgrade(project, env)
    assert result.returncode == 0, result.stdout + result.stderr

    commits = new_commit_files(project, env, head0)
    assert ("D", _SKILL) in commits
    assert _SKILL not in git(project, env, "ls-tree", "-r", "--name-only", "HEAD").stdout.split("\n")
    assert (project / _SKILL).read_text(encoding="utf-8") == _SKILL_BYTES
    assert git(project, env, "check-ignore", "-q", "--", _SKILL, check=False).returncode == 0
    assert all(path != _SKILL for xy, path in status_z(project, env) if xy != "!!")
    # the operator's staged unrelated file: still staged, in no commit
    assert "src/operator_staged.py" in staged(project, env)
    assert all(path != "src/operator_staged.py" for _s, path in commits)
    # nothing from the upgrade is left staged
    assert staged(project, env) == ["src/operator_staged.py"]
    # hooks ran for the upgrade commit
    assert counter.exists() and counter.read_text().count("x") >= 1
    assert len(new_commits(project, env, head0)) == 1


def test_operator_staged_deletion_stays_staged(tmp_path: Path) -> None:
    project, env = _legacy(tmp_path)
    head0 = head(project, env)
    git(project, env, "rm", "--cached", "-q", "--", "docs/old.md")
    result = run_upgrade(project, env)
    assert result.returncode == 0, result.stdout + result.stderr
    committed = new_commit_files(project, env, head0)
    assert ("D", _SKILL) in committed
    assert ("D", "docs/old.md") not in committed
    assert git(project, env, "ls-tree", "HEAD", "docs/old.md").stdout.strip() != ""
    assert staged(project, env) == ["docs/old.md"]


def test_operator_untrack_the_migration_later_ignores_is_not_ours_to_commit(tmp_path: Path) -> None:
    """The operator's own ``git rm --cached`` of the very file the migration then ignores stays staged.

    The path is a staged deletion, on disk and ignored after the run -- the same shape as the
    migration's own untrack -- but it was already dirty at baseline, so it is the operator's.
    """
    project, env = _legacy(tmp_path)
    head0 = head(project, env)
    git(project, env, "rm", "--cached", "-q", "--", _SKILL)
    result = run_upgrade(project, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("D", _SKILL) not in new_commit_files(project, env, head0)
    assert git(project, env, "ls-tree", "HEAD", _SKILL).stdout.strip() != ""
    assert staged(project, env) == [_SKILL]
    assert (project / _SKILL).read_text(encoding="utf-8") == _SKILL_BYTES


def test_rejecting_hook_commits_nothing_and_file_stays(tmp_path: Path) -> None:
    project, env = _legacy(tmp_path)
    head0 = head(project, env)
    counter = install_pre_commit_hook(project, tmp_path, reject=True)
    run_upgrade(project, env)
    assert counter.exists(), "the hook never ran"
    assert head(project, env) == head0
    assert git(project, env, "ls-tree", "HEAD", _SKILL).stdout.strip() != ""
    assert (project / _SKILL).read_text(encoding="utf-8") == _SKILL_BYTES


def test_file_present_at_every_step(tmp_path: Path) -> None:
    project, env = _legacy(tmp_path)
    head0 = head(project, env)
    seen = tmp_path / "presence"
    hook = project / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    probe = f"os.path.exists({str(project / _SKILL)!r})"
    hook.write_text(
        f"#!{sys.executable}\nimport os\nwith open({str(seen)!r}, 'a') as fh:\n    fh.write(('present' if {probe} else 'missing') + '\\n')\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    result = run_upgrade(project, env)
    assert result.returncode == 0, result.stdout + result.stderr
    records = seen.read_text().split()
    assert records, "the hook never ran"
    assert set(records) == {"present"}
    assert ("D", _SKILL) in new_commit_files(project, env, head0)


def test_only_ignored_present_non_baseline_deletions_are_the_migrations_untracks(tmp_path: Path) -> None:
    """The collector keeps a staged deletion only when the file is on disk, now ignored, and was clean at baseline."""
    from specify_cli.upgrade.autocommit import capture_upgrade_baseline, migration_index_untracks

    project, env = _legacy(tmp_path)
    git(project, env, "rm", "--cached", "-q", "--", "docs/old.md")  # operator's, before the run
    baseline = capture_upgrade_baseline(project)
    assert baseline is not None
    # what a migration then does: untrack one ignored file, one not-ignored file, one file that is gone
    (project / ".gitignore").write_text(".kittify/workspaces/\n.agents/skills/\n", encoding="utf-8")
    git(project, env, "rm", "--cached", "-q", "--", _SKILL, "src/app.py")
    git(project, env, "rm", "-q", "--", "kitty-specs/001-demo/meta.json")
    assert migration_index_untracks(project, baseline) == [Path(_SKILL)]
    assert migration_index_untracks(project, None) == []


def test_index_residue_after_the_commit_landed_is_reported_as_landed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A residue check that fails AFTER the temp-index commit landed must say "DID land".

    ``SafeCommitIndexResidue`` is raised once HEAD has moved. If it were a plain
    ``SafeCommitError``, ``commit_touched_checkout`` would flatten it into the generic
    "Could not auto-commit" skip warning and the upgrade would report the commit as not made.
    Fault injection: ``changed_paths`` fails only once HEAD has moved past the baseline commit.
    """
    import os
    import subprocess

    from kernel.git import GitCommandError
    from specify_cli.cli.commands import upgrade as upgrade_cmd
    from specify_cli.git import commit_helpers
    from specify_cli.upgrade.autocommit import UPGRADE_COMMIT_SKIP_WARNING, capture_upgrade_baseline
    from specify_cli.upgrade.outcome import UpgradeOutcome
    from specify_cli.upgrade.runner import UpgradeResult

    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))

    repo = tmp_path / "repo"
    repo.mkdir()

    def _git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    _git("init", "--template=", "-b", "work")
    _git("config", "user.email", "t@example.com")
    _git("config", "user.name", "T")
    _git("config", "commit.gpgsign", "false")
    (repo / _SKILL).parent.mkdir(parents=True)
    (repo / _SKILL).write_text(_SKILL_BYTES, encoding="utf-8")
    (repo / ".gitignore").write_text(".kittify/workspaces/\n", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "init")
    head0 = _git("rev-parse", "HEAD")

    baseline = capture_upgrade_baseline(repo)
    assert baseline is not None
    # what the 3.2.5 backfill does: ignore the skills dir and untrack what was committed there
    (repo / ".gitignore").write_text(".kittify/workspaces/\n.agents/skills/\n", encoding="utf-8")
    _git("rm", "--cached", "-q", "--", _SKILL)

    real_changed_paths = commit_helpers.changed_paths

    def _fails_after_landing(*args: object, **kwargs: object) -> object:
        if _git("rev-parse", "HEAD") != head0:
            raise GitCommandError(argv=("diff", "--cached"), cwd=repo, returncode=128, stderr="fatal: index file corrupt (injected)")
        return real_changed_paths(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(commit_helpers, "changed_paths", _fails_after_landing)

    outcome = UpgradeOutcome(result=UpgradeResult(success=True, from_version="3.2.4", to_version="3.2.5"))
    ctx = upgrade_cmd._FinalizerRenderContext()
    committed = upgrade_cmd._finalizer_step_commit_churn(outcome, ctx, project_path=repo, baseline_changed_paths=baseline)

    landed = _git("rev-parse", "HEAD")
    assert landed != head0, "the temp-index commit must have landed before the injected failure"
    assert committed is True, "HEAD moved, so the outcome must report the commit as made"
    assert ctx.commit_warning != UPGRADE_COMMIT_SKIP_WARNING
    assert outcome.commit_recovery_failed is True
    assert [reason.value for reason in outcome.reasons] == ["commit_recovery_failed"]
    rendered = " ".join(outcome.result.errors)
    assert f"Commit {landed} DID land." in rendered
    assert "Could not auto-commit" not in rendered
    assert "No commit landed" not in rendered
