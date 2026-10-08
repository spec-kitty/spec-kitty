"""Exact-owner lock prevention and supported index-only recovery over real Git."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import CommitTarget
from specify_cli.cli.commands.decision import decision_app
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, resolve_owned_mission
from specify_cli.decisions.service import _decisions_lock_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
runner = CliRunner()


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def seed(c, state="tracked"):
    lock = _decisions_lock_path(c.mission_dir)
    lock.parent.mkdir()
    lock.write_bytes(b"")
    ledger = lock.parent / "index.json"
    ledger.write_text('{"decisions": []}\n')
    authored = lock.parent / "authored.lock"
    authored.write_text("authored content\n")
    git(c.owned_root, "add", "--", str(ledger), str(authored))
    if state == "tracked":
        git(c.owned_root, "add", "-f", "--", str(lock))
    if state == "ignored":
        (lock.parent / ".gitignore").write_text("/index.json.lock\n")
        git(c.owned_root, "add", "--", str(lock.parent / ".gitignore"))
    git(c.owned_root, "commit", "-qm", "seed decision payloads")
    return lock


def invoke(c, monkeypatch, *extra):
    monkeypatch.chdir(c.owned_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(c.owned_root))
    return runner.invoke(decision_app, ["repair-runtime-lock", "--mission", c.mission_slug,
        "--owned-checkout", str(c.owned_root), *extra])


def snapshot(root):
    return (git(root, "rev-parse", "HEAD"), git(root, "status", "--porcelain=v1", "--untracked-files=all"),
            git(root, "diff", "--cached", "--binary"),
            {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts})


def test_owned_next_excludes_only_service_lock(owned_checkouts):
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations
    c = owned_checkouts
    lock = seed(c, "untracked")
    authored = lock.parent / "new-authored.lock"
    authored.write_text("should be committed\n")
    fact = resolve_owned_mission(c.repository_root, c.owned_root, c.mission_slug, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    before_inode = lock.stat().st_ino
    _commit_owned_next_mutations(fact)
    files = git(c.owned_root, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert str(lock.relative_to(c.owned_root)) not in files
    assert str(authored.relative_to(c.owned_root)) in files
    assert lock.stat().st_ino == before_inode


@pytest.mark.parametrize("state", ["tracked", "untracked", "ignored"])
@pytest.mark.parametrize("dry", [True, False])
def test_repair_preserves_payload_inode_and_other_roots(owned_checkouts, monkeypatch, state, dry):
    c = owned_checkouts
    lock = seed(c, state)
    (c.owned_root / "README.md").write_text("staged\n")
    git(c.owned_root, "add", "README.md")
    (c.owned_root / "README.md").write_text("unstaged half\n")
    other_index = git(c.owned_root, "diff", "--cached", "--", "README.md")
    r, s, p = snapshot(c.repository_root), snapshot(c.sibling), snapshot(c.owned_root)
    inode = lock.stat().st_ino
    result = invoke(c, monkeypatch, *(["--dry-run"] if dry else []))
    assert result.exit_code == 0, result.output
    assert snapshot(c.repository_root) == r
    assert snapshot(c.sibling) == s
    assert lock.stat().st_ino == inode
    assert git(c.owned_root, "diff", "--cached", "--", "README.md") == other_index
    assert (c.owned_root / "README.md").read_text() == "unstaged half\n"
    if dry:
        assert snapshot(c.owned_root) == p
    else:
        assert str(lock.relative_to(c.owned_root)) not in git(c.owned_root, "ls-files").splitlines()
        assert git(c.owned_root, "check-ignore", str(lock))
        assert (lock.parent / "index.json").read_text() == '{"decisions": []}\n'
        assert (lock.parent / "authored.lock").read_text() == "authored content\n"
        head = git(c.owned_root, "rev-parse", "HEAD")
        again = invoke(c, monkeypatch)
        assert again.exit_code == 0, again.output
        assert git(c.owned_root, "rev-parse", "HEAD") == head


def test_dry_run_does_not_create_lock(owned_checkouts, monkeypatch):
    c = owned_checkouts
    before = snapshot(c.owned_root)
    result = invoke(c, monkeypatch, "--dry-run")
    assert result.exit_code == 0, result.output
    assert snapshot(c.owned_root) == before
    assert not _decisions_lock_path(c.mission_dir).exists()


@pytest.mark.parametrize("fault", ["branch", "detached", "foreign", "root", "symlink", "dirty_ignore", "staged_ignore", "dirty_lock", "staged_lock"])
def test_repair_refuses_before_any_write(owned_checkouts, monkeypatch, fault):
    c = owned_checkouts
    lock = seed(c)
    if fault == "branch":
        git(c.owned_root, "checkout", "-qb", "codex/foreign")
    elif fault == "detached":
        git(c.owned_root, "checkout", "--detach", "-q")
    elif fault in {"dirty_ignore", "staged_ignore"}:
        (lock.parent / ".gitignore").write_text("operator edit\n")
        if fault == "staged_ignore":
            git(c.owned_root, "add", str(lock.parent / ".gitignore"))
    elif fault in {"dirty_lock", "staged_lock"}:
        lock.write_text("operator lock bytes\n")
        if fault == "staged_lock":
            git(c.owned_root, "add", "-f", str(lock))
    elif fault == "symlink":
        lock.unlink()
        lock.symlink_to(c.sibling / "README.md")
    p, r, s = snapshot(c.owned_root), snapshot(c.repository_root), snapshot(c.sibling)
    monkeypatch.chdir(c.owned_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(c.owned_root))
    claim = c.sibling if fault == "foreign" else c.repository_root if fault == "root" else c.owned_root
    result = runner.invoke(decision_app, ["repair-runtime-lock", "--mission", c.mission_slug, "--owned-checkout", str(claim)])
    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert snapshot(c.owned_root) == p
    assert snapshot(c.repository_root) == r
    assert snapshot(c.sibling) == s


def test_rejecting_hook_restores_only_own_ignore_delta(owned_checkouts, monkeypatch):
    c = owned_checkouts
    lock = seed(c)
    hooks = Path(git(c.owned_root, "rev-parse", "--git-path", "hooks"))
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    before = snapshot(c.owned_root)
    inode = lock.stat().st_ino
    result = invoke(c, monkeypatch)
    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert snapshot(c.owned_root) == before
    assert lock.stat().st_ino == inode


def test_index_only_capability_refuses_non_owner_path(owned_checkouts):
    from specify_cli.git.commit_helpers import safe_commit
    c = owned_checkouts
    fact = resolve_owned_mission(c.repository_root, c.owned_root, c.mission_slug, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    path = c.owned_root / "README.md"
    before = snapshot(c.owned_root)
    with pytest.raises(ValueError, match="decision runtime lock"):
        safe_commit(repo_root=c.owned_root, worktree_root=c.owned_root, target=CommitTarget(ref=fact.write_branch),
                    message="refuse arbitrary removal", paths=(path,), owned=fact,
                    expected_parent_sha=git(c.owned_root, "rev-parse", "HEAD"), index_only_removals=(path,))
    assert snapshot(c.owned_root) == before


def test_repair_reasserts_exact_ignore_after_authored_negation(owned_checkouts, monkeypatch):
    c = owned_checkouts
    lock = seed(c)
    ignore = lock.parent / ".gitignore"
    original = "# operator rules\n/index.json.lock\n!/index.json.lock\nkeep.tmp\n"
    ignore.write_text(original)
    git(c.owned_root, "add", str(ignore))
    git(c.owned_root, "commit", "-qm", "authored ignore")
    result = invoke(c, monkeypatch)
    assert result.exit_code == 0, result.output
    assert ignore.read_text().startswith(original)
    assert git(c.owned_root, "check-ignore", "--no-index", str(lock))
    assert subprocess.run(["git", "check-ignore", "--no-index", str(lock.parent / "authored.lock")], cwd=c.owned_root, capture_output=True).returncode == 1


def test_repair_compare_and_swap_refusal_preserves_index(owned_checkouts, monkeypatch):
    from specify_cli.git import commit_helpers
    c = owned_checkouts
    lock = seed(c)
    before = snapshot(c.owned_root)
    inode = lock.stat().st_ino
    def refuse(*args, **kwargs):
        raise RuntimeError("injected expected-parent race")
    monkeypatch.setattr(commit_helpers, "_compare_and_swap_commit_ref", refuse)
    result = invoke(c, monkeypatch)
    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert snapshot(c.owned_root) == before
    assert lock.stat().st_ino == inode


def test_repair_requires_explicit_claim(owned_checkouts, monkeypatch):
    c = owned_checkouts
    before = snapshot(c.owned_root)
    monkeypatch.chdir(c.owned_root)
    result = runner.invoke(decision_app, ["repair-runtime-lock", "--mission", c.mission_slug])
    assert result.exit_code != 0
    assert "owned-checkout" in result.output
    assert snapshot(c.owned_root) == before


def test_repair_refuses_ignore_symlink(owned_checkouts, monkeypatch):
    c = owned_checkouts
    lock = seed(c)
    (lock.parent / ".gitignore").symlink_to(c.sibling / "README.md")
    before = snapshot(c.owned_root)
    result = invoke(c, monkeypatch)
    assert result.exit_code != 0
    assert "symlink" in result.output.lower()
    assert snapshot(c.owned_root) == before


@pytest.mark.parametrize("policy", ["pr_bound", "commit_to_target"])
def test_repair_preserves_owned_protected_policy(make_owned_checkouts, monkeypatch, policy):
    import json
    from tests.integration.test_owned_protected_single_branch import _rewrite_meta, _commit_all
    c = make_owned_checkouts(protected_target=True, target_branch="release")
    if policy == "pr_bound":
        _rewrite_meta(c, pr_bound=True, mission_branch="codex/planning")
        git(c.owned_root, "checkout", "-qb", "codex/planning")
    else:
        _rewrite_meta(c, commit_to_target=True)
    _commit_all(c.owned_root, "fixture protected policy")
    lock = seed(c)
    metadata = (c.mission_dir / "meta.json").read_bytes()
    before_target = git(c.owned_root, "rev-parse", "release")
    result = invoke(c, monkeypatch)
    assert result.exit_code == 0, result.output
    assert (c.mission_dir / "meta.json").read_bytes() == metadata
    assert json.loads(metadata)["target_branch"] == "release"
    assert lock.exists()
    if policy == "pr_bound":
        assert git(c.owned_root, "rev-parse", "release") == before_target
