"""Unit tests for the refuse-before-destroy guard primitive (WP01, #4752/#4753).

Covers ``DestructiveOpRefused``, ``assert_checkout_on_target``,
``assert_worktree_clean``, and the shared removal chokepoint
``guarded_worktree_remove`` in ``specify_cli.git.destructive_guard``.

Red-first (T004): every test in this file fails at collection before
``src/specify_cli/git/destructive_guard.py`` exists (``ModuleNotFoundError``),
and fails on assertions afterward until the guard functions are implemented
to spec (data-model.md / contracts/guard-api.md).
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from specify_cli.git.destructive_guard import (
    DestructiveOpRefused,
    RemoveOutcome,
    assert_checkout_on_target,
    assert_worktree_clean,
    guarded_worktree_remove,
)

# All tests here shell out to real git; mirrors test_ref_advance_meta_diagnosability.py.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")


def _commit_all(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _never_residue(_path: str) -> bool:
    """Stub matching the ``Callable[[str], bool]`` classifier contract."""
    return False


def _residue_for_meta_json(path: str) -> bool:
    """Stub matching ``coordination.coherence.is_toolchain_generated_churn``'s
    contract: path-based, content-agnostic — any ``meta.json`` is toolchain
    bookkeeping churn regardless of what changed (NFR-003)."""
    return Path(path).name == "meta.json"


# --- DestructiveOpRefused -----------------------------------------------------


def test_destructive_op_refused_carries_all_fields() -> None:
    exc = DestructiveOpRefused(
        error_code="MERGE_UNSAFE_WORKTREE_DIRTY",
        worktree_path=Path("/tmp/example"),
        current_branch="main",
        expected_branch="fix/x",
        dirty_entries=[" M some/file.py"],
        remediation="Commit or stash, then retry.",
    )
    assert exc.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    assert exc.worktree_path == Path("/tmp/example")
    assert exc.current_branch == "main"
    assert exc.expected_branch == "fix/x"
    assert exc.dirty_entries == [" M some/file.py"]
    assert exc.remediation == "Commit or stash, then retry."
    # Message names the condition and the fix.
    assert "MERGE_UNSAFE_WORKTREE_DIRTY" in str(exc) or "dirty" in str(exc).lower()
    assert "Commit or stash" in str(exc)


def test_destructive_op_refused_is_not_safe_commit_head_mismatch() -> None:
    """C-002: this module must not reuse/overload SafeCommitHeadMismatch."""
    from specify_cli.git.commit_helpers import SafeCommitHeadMismatch

    assert not issubclass(DestructiveOpRefused, SafeCommitHeadMismatch)
    assert not issubclass(SafeCommitHeadMismatch, DestructiveOpRefused)


# --- assert_checkout_on_target ------------------------------------------------


def test_on_target_passes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    # No exception raised.
    assert assert_checkout_on_target(root, "main") is None


def test_off_target_raises(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")
    _git(root, "checkout", "-q", "-b", "other-branch")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        assert_checkout_on_target(root, "main")

    exc = excinfo.value
    assert exc.error_code == "MERGE_UNSAFE_PRIMARY_OFF_TARGET"
    assert exc.current_branch == "other-branch"
    assert exc.expected_branch == "main"
    assert exc.remediation


# --- assert_worktree_clean ----------------------------------------------------


def test_clean_worktree_passes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    assert assert_worktree_clean(root, is_residue=_never_residue) is None


def test_tracked_dirty_raises(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    tracked = root / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _commit_all(root, "seed")
    tracked.write_text("v2 - local edit\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        assert_worktree_clean(root, is_residue=_never_residue)

    exc = excinfo.value
    assert exc.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    assert any("tracked.txt" in entry for entry in exc.dirty_entries)
    assert exc.remediation


def test_tracked_dirty_honors_error_code_override(tmp_path: Path) -> None:
    """The primary-checkout caller (WP03/FR-002) passes MERGE_UNSAFE_PRIMARY_DIRTY."""
    root = tmp_path / "repo"
    _init_repo(root)
    tracked = root / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _commit_all(root, "seed")
    tracked.write_text("v2 - local edit\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        assert_worktree_clean(
            root,
            is_residue=_never_residue,
            error_code="MERGE_UNSAFE_PRIMARY_DIRTY",
        )

    assert excinfo.value.error_code == "MERGE_UNSAFE_PRIMARY_DIRTY"


def test_untracked_obstruction_raises(tmp_path: Path) -> None:
    """An untracked path that would be clobbered by resetting to ``new_sha``
    is treated as destructible local state (mirrors ``ref_advance``'s
    obstruction check) even though nothing is tracked-dirty.

    Builds the target commit purely via plumbing (``hash-object`` /
    ``update-index --cacheinfo`` / ``write-tree`` / ``commit-tree``) so the
    working tree is never checked out to it — the untracked file created
    afterward genuinely stays untracked, unlike a real branch switch (which
    would delete a tracked-then-removed path from the worktree).
    """
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    base_sha = _commit_all(root, "seed")

    blob_sha = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=str(root),
        input="built content\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob_sha},generated/output.txt")
    tree_sha = _git(root, "write-tree").stdout.strip()
    target_sha = _git(root, "commit-tree", tree_sha, "-p", base_sha, "-m", "add generated output").stdout.strip()
    _git(root, "reset", "-q")  # drop the staged entry; working tree untouched

    generated_dir = root / "generated"
    generated_dir.mkdir()
    (generated_dir / "output.txt").write_text("local untracked content\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        assert_worktree_clean(root, new_sha=target_sha, is_residue=_never_residue)

    exc = excinfo.value
    assert exc.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    assert any("generated" in entry for entry in exc.dirty_entries)


def test_residue_only_meta_json_change_passes(tmp_path: Path) -> None:
    """NFR-003: a meta.json diff the injected classifier recognizes as
    toolchain-generated churn never triggers a refusal, even though the file
    is tracked-modified."""
    root = tmp_path / "repo"
    _init_repo(root)
    meta_dir = root / "kitty-specs" / "some-mission"
    meta_dir.mkdir(parents=True)
    meta_path = meta_dir / "meta.json"
    meta_path.write_text('{"slug": "some-mission"}\n', encoding="utf-8")
    _commit_all(root, "seed meta.json")

    # Mutate the tracked meta.json (VCS-lock-stamp-shaped edit); the injected
    # classifier exempts it purely by path, matching the real classifier's
    # content-agnostic contract.
    meta_path.write_text(
        '{"slug": "some-mission", "vcs_locked_at": "2026-09-19T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    assert assert_worktree_clean(root, is_residue=_residue_for_meta_json) is None


def test_residue_classifier_does_not_exempt_unrelated_files(tmp_path: Path) -> None:
    """The injected classifier is path-scoped: it must not blanket-exempt
    every dirty entry, only the ones it actually recognizes."""
    root = tmp_path / "repo"
    _init_repo(root)
    tracked = root / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _commit_all(root, "seed")
    tracked.write_text("v2 - local edit\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        assert_worktree_clean(root, is_residue=_residue_for_meta_json)


# --- guarded_worktree_remove ---------------------------------------------------


def _add_worktree(root: Path, worktree: Path, branch: str) -> None:
    _git(root, "worktree", "add", "-q", "-b", branch, str(worktree), "main")


def test_guarded_worktree_remove_clean_removes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-clean"
    _add_worktree(root, worktree, "lane-clean")
    assert worktree.exists()

    result = guarded_worktree_remove(worktree, retain=False, is_residue=_never_residue)

    assert result.outcome is RemoveOutcome.REMOVED
    assert result.worktree_path == worktree
    assert not worktree.exists()


def test_guarded_worktree_remove_dirty_no_retain_raises(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    tracked = root / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-dirty"
    _add_worktree(root, worktree, "lane-dirty")
    (worktree / "tracked.txt").write_text("local edit, uncommitted\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        guarded_worktree_remove(worktree, retain=False, is_residue=_never_residue)

    assert excinfo.value.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    # Fail-closed: the worktree must survive the refusal untouched.
    assert worktree.exists()
    assert (worktree / "tracked.txt").read_text(encoding="utf-8") == "local edit, uncommitted\n"


def test_guarded_worktree_remove_retain_dirty_keeps(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    tracked = root / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-retain-dirty"
    _add_worktree(root, worktree, "lane-retain-dirty")
    (worktree / "tracked.txt").write_text("local edit, uncommitted\n", encoding="utf-8")

    result = guarded_worktree_remove(worktree, retain=True, is_residue=_never_residue)

    assert result.outcome is RemoveOutcome.RETAINED_DIRTY
    assert result.worktree_path == worktree
    assert worktree.exists()
    assert (worktree / "tracked.txt").read_text(encoding="utf-8") == "local edit, uncommitted\n"


def test_guarded_worktree_remove_retain_clean_still_removes(tmp_path: Path) -> None:
    """Retention only holds back the DIRTY case (data-model US2 AC2/AC3): a
    clean worktree carries no data-loss risk, so it is removed as today even
    with ``retain=True`` — ``RemoveOutcome`` has no third "retained-clean"
    bucket."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-retain-clean"
    _add_worktree(root, worktree, "lane-retain-clean")

    result = guarded_worktree_remove(worktree, retain=True, is_residue=_never_residue)

    assert result.outcome is RemoveOutcome.REMOVED
    assert not worktree.exists()


# --- T005: git-plumbing purity + complexity -----------------------------------


def test_module_imports_zero_specify_cli_application_modules() -> None:
    """C-005: no ``specify_cli`` (application-layer) or ``coordination``
    import in this module — the caller injects the churn classifier. A
    relative sibling import of ``ref_advance`` (same git-plumbing package) is
    fine; an absolute reach into ``specify_cli.coordination`` or similar is
    not."""
    module_path = Path(__file__).resolve().parents[3] / "src" / "specify_cli" / "git" / "destructive_guard.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(
                alias.name
                for alias in node.names
                if alias.name == "specify_cli" or alias.name.startswith("specify_cli.") or alias.name == "coordination" or alias.name.startswith("coordination.")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and (node.module == "specify_cli" or node.module.startswith("specify_cli.") or node.module == "coordination" or node.module.startswith("coordination."))
        ):
            offenders.append(node.module)
    assert not offenders, f"destructive_guard.py must stay git-plumbing pure; found: {offenders!r}"
