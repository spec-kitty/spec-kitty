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

from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import CheckoutRole, ResidueContext
from specify_cli.git.destructive_guard import (
    BRANCH_HAS_UNIQUE_COMMITS,
    DESTRUCTIVE_OP_ONLY_COPY,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    DestructiveOpRefused,
    RemoveOutcome,
    assert_checkout_on_target,
    assert_worktree_clean,
    guarded_branch_delete,
    guarded_merge_abort,
    guarded_reset_hard,
    guarded_tree_delete,
    guarded_worktree_prune,
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


def test_destructive_op_refused_carries_all_fields(tmp_path: Path) -> None:
    worktree_path = tmp_path / "example"
    exc = DestructiveOpRefused(
        error_code="MERGE_UNSAFE_WORKTREE_DIRTY",
        worktree_path=worktree_path,
        current_branch="main",
        expected_branch="fix/x",
        dirty_entries=[" M some/file.py"],
        remediation="Commit or stash, then retry.",
    )
    assert exc.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    assert exc.worktree_path == worktree_path
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


def test_untracked_only_passes_by_default(tmp_path: Path) -> None:
    """Parity/control: WITHOUT ``treat_untracked_as_dirty``, a non-obstructing
    untracked file does not block (unchanged default reading -- correct for a
    ``reset --hard`` caller)."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")
    (root / "scratch.txt").write_text("untracked, non-obstructing\n", encoding="utf-8")

    assert assert_worktree_clean(root, is_residue=_never_residue) is None


def test_untracked_only_raises_when_treat_untracked_as_dirty(tmp_path: Path) -> None:
    """#4753 Finding A: ``treat_untracked_as_dirty=True`` flags a
    non-obstructing untracked file that the default reading lets through --
    the removal-destined-worktree case."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")
    (root / "scratch.txt").write_text("untracked local work\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        assert_worktree_clean(root, is_residue=_never_residue, treat_untracked_as_dirty=True)

    assert any("scratch.txt" in entry for entry in excinfo.value.dirty_entries)


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


def test_guarded_worktree_remove_untracked_only_no_retain_raises(tmp_path: Path) -> None:
    """#4753 Finding A (red-first): an untracked-ONLY file (no tracked edit)
    in a worktree must still block ``guarded_worktree_remove(retain=False)``.

    Pre-fix, ``assert_worktree_clean`` -> ``_dirty_entries`` only flagged an
    untracked entry when it obstructed a path in the (here-absent) target
    tree, so a genuinely untracked operator file never surfaced as dirty and
    ``git worktree remove --force`` silently deleted it -- the exact
    untracked-only data-loss hole #4753 identifies."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-untracked-only"
    _add_worktree(root, worktree, "lane-untracked-only")
    (worktree / "scratch.txt").write_text("implementer's in-progress notes\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as excinfo:
        guarded_worktree_remove(worktree, retain=False, is_residue=_never_residue)

    assert excinfo.value.error_code == "MERGE_UNSAFE_WORKTREE_DIRTY"
    assert any("scratch.txt" in entry for entry in excinfo.value.dirty_entries)
    # Fail-closed: the worktree and its untracked file survive the refusal.
    assert worktree.exists()
    assert (worktree / "scratch.txt").read_text(encoding="utf-8") == "implementer's in-progress notes\n"


def test_guarded_worktree_remove_untracked_only_retain_retains(tmp_path: Path) -> None:
    """The ``retain=True`` sibling of the case above: an untracked-only
    worktree is RETAINED (not silently removed) instead of raising."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-untracked-only-retain"
    _add_worktree(root, worktree, "lane-untracked-only-retain")
    (worktree / "scratch.txt").write_text("in-progress notes\n", encoding="utf-8")

    result = guarded_worktree_remove(worktree, retain=True, is_residue=_never_residue)

    assert result.outcome is RemoveOutcome.RETAINED_DIRTY
    assert worktree.exists()
    assert (worktree / "scratch.txt").read_text(encoding="utf-8") == "in-progress notes\n"


def test_guarded_worktree_remove_residue_untracked_still_exempt(tmp_path: Path) -> None:
    """An untracked path the injected classifier recognizes as toolchain
    churn stays exempt even under ``treat_untracked_as_dirty`` (routed
    through ``guarded_worktree_remove``'s removal path) -- the exemption
    applies uniformly, not only to tracked entries."""
    root = tmp_path / "repo"
    _init_repo(root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(root, "seed")

    worktree = tmp_path / "wt-residue-untracked"
    _add_worktree(root, worktree, "lane-residue-untracked")
    (worktree / "meta.json").write_text('{"slug": "residue"}\n', encoding="utf-8")

    result = guarded_worktree_remove(worktree, retain=False, is_residue=_residue_for_meta_json)

    assert result.outcome is RemoveOutcome.REMOVED
    assert not worktree.exists()


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


# --- WP02 (#5965 / #5966): context-aware guard API --------------------------------

_SLUG = "m-01ABCDEF"
_OTHER = "other-01ZZZZZZ"


def _ctx(role: CheckoutRole = CheckoutRole.REPOSITORY_ROOT) -> ResidueContext:
    return ResidueContext(role, _SLUG, MissionTopology.COORD)


def _mission_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _init_repo(root)
    mission = root / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    (mission / "status.json").write_text("{}\n", encoding="utf-8")
    (mission / "meta.json").write_text("{}\n", encoding="utf-8")
    (root / "src.py").write_text("x = 1\n", encoding="utf-8")
    (root / "notes.txt").write_text("notes\n", encoding="utf-8")
    _commit_all(root, "seed")
    return root


def _snapshot(root: Path) -> tuple[str, str, dict[str, bytes]]:
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    status = _git(root, "status", "--porcelain=v1", "-uall").stdout
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    return head, status, files


def test_context_and_is_residue_together_is_a_type_error(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)

    with pytest.raises(TypeError, match="exactly one"):
        assert_worktree_clean(root, context=_ctx(), is_residue=_never_residue)
    with pytest.raises(TypeError, match="exactly one"):
        guarded_worktree_remove(root, retain=False, context=_ctx(), is_residue=_never_residue)


def test_neither_context_nor_is_residue_is_a_type_error(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)

    with pytest.raises(TypeError, match="exactly one"):
        assert_worktree_clean(root)
    with pytest.raises(TypeError, match="exactly one"):
        guarded_worktree_remove(root, retain=False)


def test_legacy_is_residue_still_works(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    (root / "kitty-specs" / _SLUG / "meta.json").write_text('{"a": 1}\n', encoding="utf-8")

    assert_worktree_clean(root, is_residue=_residue_for_meta_json)


def test_assert_clean_with_context_refuses_another_missions_traces(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    other = root / "kitty-specs" / _OTHER / "traces"
    other.mkdir(parents=True)
    (other / "notes.md").write_text("only copy\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as info:
        assert_worktree_clean(root, context=_ctx(), treat_untracked_as_dirty=True)
    assert any(_OTHER in entry for entry in info.value.dirty_entries)


def test_assert_clean_with_context_cleans_the_missions_own_status_copy(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    (root / "kitty-specs" / _SLUG / "status.json").write_text('{"stale": true}\n', encoding="utf-8")

    assert_worktree_clean(root, context=_ctx())


def test_assert_clean_in_a_coordination_checkout_keeps_the_review_cycle(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    review = root / "kitty-specs" / _SLUG / "tasks" / "WP01"
    review.mkdir(parents=True)
    (review / "review-cycle-1.md").write_text("feedback\n", encoding="utf-8")

    assert_worktree_clean(root, context=_ctx(CheckoutRole.REPOSITORY_ROOT), treat_untracked_as_dirty=True)
    with pytest.raises(DestructiveOpRefused):
        assert_worktree_clean(root, context=_ctx(CheckoutRole.COORDINATION), treat_untracked_as_dirty=True)


def test_guarded_worktree_remove_with_context_refuses_and_keeps_the_worktree(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    worktree = tmp_path / "wt"
    _add_worktree(root, worktree, "lane-x")
    (worktree / "kitty-specs" / _OTHER / "traces").mkdir(parents=True)
    (worktree / "kitty-specs" / _OTHER / "traces" / "n.md").write_text("keep\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        guarded_worktree_remove(worktree, retain=False, context=_ctx(CheckoutRole.LANE))
    assert (worktree / "kitty-specs" / _OTHER / "traces" / "n.md").exists()
    assert guarded_worktree_remove(worktree, retain=True, context=_ctx(CheckoutRole.LANE)).outcome is RemoveOutcome.RETAINED_DIRTY


def test_refusal_lists_at_most_twenty_entries_then_a_count() -> None:
    entries = [f" M f{i:03d}.py" for i in range(27)]

    message = str(DestructiveOpRefused(error_code="X", dirty_entries=entries, remediation="fix"))

    assert "f019.py" in message and "f020.py" not in message
    assert "... and 7 more" in message


def test_refusal_with_exactly_twenty_entries_has_no_count() -> None:
    entries = [f" M f{i:03d}.py" for i in range(20)]

    assert "more" not in str(DestructiveOpRefused(error_code="X", dirty_entries=entries, remediation="fix"))


# --- guarded_reset_hard -----------------------------------------------------------


def test_guarded_reset_hard_clean_runs(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    first = _git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "src.py").write_text("x = 2\n", encoding="utf-8")
    _commit_all(root, "second")

    guarded_reset_hard(root, first, context=_ctx())

    assert _git(root, "rev-parse", "HEAD").stdout.strip() == first
    assert (root / "src.py").read_text(encoding="utf-8") == "x = 1\n"


def test_guarded_reset_hard_dirty_refuses_without_mutation(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    (root / "src.py").write_text("operator edit\n", encoding="utf-8")
    before = _snapshot(root)

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_reset_hard(root, "HEAD", context=_ctx())

    assert info.value.error_code == MERGE_UNSAFE_WORKTREE_DIRTY
    assert _snapshot(root) == before


def test_guarded_reset_hard_failure_raises(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)

    with pytest.raises(Exception, match="(?i)bad revision|unknown revision|not a valid|ambiguous|failed"):
        guarded_reset_hard(root, "does-not-exist", context=_ctx())


# --- guarded_merge_abort ------------------------------------------------------------


def _conflicting_merge(tmp_path: Path) -> Path:
    root = _mission_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "side")
    (root / "src.py").write_text("x = side\n", encoding="utf-8")
    _commit_all(root, "side")
    _git(root, "checkout", "-q", "main")
    (root / "src.py").write_text("x = main\n", encoding="utf-8")
    _commit_all(root, "main")
    result = subprocess.run(["git", "merge", "side"], cwd=str(root), capture_output=True, text=True, check=False)
    assert result.returncode != 0
    return root


def test_guarded_merge_abort_discards_the_merges_own_conflict(tmp_path: Path) -> None:
    root = _conflicting_merge(tmp_path)

    guarded_merge_abort(root, context=_ctx())

    assert (root / "src.py").read_text(encoding="utf-8") == "x = main\n"
    assert not (root / ".git" / "MERGE_HEAD").exists()


def test_guarded_merge_abort_refuses_an_operators_unrelated_edit(tmp_path: Path) -> None:
    root = _conflicting_merge(tmp_path)
    (root / "notes.txt").write_text("operator edit\n", encoding="utf-8")
    (root / "kitty-specs" / _SLUG / "meta.json").write_text('{"edit": 1}\n', encoding="utf-8")
    before = _snapshot(root)

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_merge_abort(root, context=_ctx())

    assert info.value.error_code == DESTRUCTIVE_OP_ONLY_COPY
    assert _snapshot(root) == before
    assert (root / ".git" / "MERGE_HEAD").exists()


def test_merge_owned_paths_is_empty_without_a_merge(tmp_path: Path) -> None:
    from specify_cli.git.destructive_guard import _merge_owned_paths

    assert _merge_owned_paths(_mission_repo(tmp_path), None) == frozenset()


# --- guarded_worktree_prune -----------------------------------------------------------


def test_guarded_worktree_prune_drops_a_registration_whose_directory_is_gone(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    worktree = tmp_path / "gone-wt"
    _add_worktree(root, worktree, "lane-gone")
    import shutil

    shutil.rmtree(worktree)

    guarded_worktree_prune(root)

    assert "gone-wt" not in _git(root, "worktree", "list", "--porcelain").stdout


def test_guarded_worktree_prune_refuses_when_a_prunable_path_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _mission_repo(tmp_path)
    existing = tmp_path / "still-here"
    existing.mkdir()
    import specify_cli.git.destructive_guard as guard

    real = guard._git_ok

    def fake(cwd: Path, args: list[str], env: dict[str, str] | None) -> str:
        if args[:2] == ["worktree", "list"]:
            return f"worktree {existing}\nHEAD abc\nprunable gitdir file points to non-existent location\n\n"
        return real(cwd, args, env)

    monkeypatch.setattr(guard, "_git_ok", fake)

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_worktree_prune(root)
    assert info.value.dirty_entries == [str(existing)]


# --- guarded_branch_delete ---------------------------------------------------------------


def _branch_with_commit(root: Path, name: str) -> str:
    base = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "checkout", "-q", "-b", name)
    (root / f"{name}.txt").write_text(name, encoding="utf-8")
    _commit_all(root, name)
    _git(root, "checkout", "-q", "main")
    return base


def test_branch_delete_refuses_unique_commits_beyond_the_creation_base(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    base = _branch_with_commit(root, "work")

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_branch_delete(root, "work", creation_base=base)

    assert info.value.error_code == BRANCH_HAS_UNIQUE_COMMITS
    assert _git(root, "rev-parse", "--verify", "refs/heads/work")


def test_branch_delete_refuses_unique_commits_without_a_creation_base(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    _branch_with_commit(root, "work")

    with pytest.raises(DestructiveOpRefused):
        guarded_branch_delete(root, "work", creation_base=None)


def test_branch_delete_allows_commits_reachable_from_another_ref(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    base = _branch_with_commit(root, "work")
    _git(root, "merge", "-q", "--ff-only", "work")

    guarded_branch_delete(root, "work", creation_base=base)

    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/heads/work"], cwd=str(root), capture_output=True).returncode != 0


def test_branch_delete_allows_a_branch_with_nothing_beyond_its_creation_base(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "branch", "fresh")

    guarded_branch_delete(root, "fresh", creation_base=base)

    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/heads/fresh"], cwd=str(root), capture_output=True).returncode != 0


def test_branch_delete_of_a_missing_branch_is_a_no_op(tmp_path: Path) -> None:
    guarded_branch_delete(_mission_repo(tmp_path), "never-existed", creation_base=None)


# --- guarded_tree_delete -------------------------------------------------------------------


def test_tree_delete_removes_a_clean_checkout(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    worktree = tmp_path / "wt"
    _add_worktree(root, worktree, "lane-del")

    guarded_tree_delete(worktree, context=_ctx(CheckoutRole.LANE))

    assert not worktree.exists()


def test_tree_delete_refuses_an_untracked_only_copy_without_mutation(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    worktree = tmp_path / "wt"
    _add_worktree(root, worktree, "lane-del2")
    (worktree / "kitty-specs" / _OTHER / "traces").mkdir(parents=True)
    (worktree / "kitty-specs" / _OTHER / "traces" / "n.md").write_text("keep\n", encoding="utf-8")
    before = _snapshot(worktree)

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_tree_delete(worktree, context=_ctx(CheckoutRole.LANE))

    assert info.value.error_code == DESTRUCTIVE_OP_ONLY_COPY
    assert _snapshot(worktree) == before


def test_tree_delete_inside_a_checkout_only_judges_its_own_subtree(tmp_path: Path) -> None:
    root = _mission_repo(tmp_path)
    (root / "scratch").mkdir()
    (root / "scratch" / "a.txt").write_text("a\n", encoding="utf-8")
    _commit_all(root, "scratch")
    (root / "src.py").write_text("dirty elsewhere\n", encoding="utf-8")

    guarded_tree_delete(root / "scratch", context=_ctx())

    assert not (root / "scratch").exists()
    assert (root / "src.py").read_text(encoding="utf-8") == "dirty elsewhere\n"


def test_tree_delete_refuses_a_directory_that_is_not_a_checkout(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "f.txt").write_text("x", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused, match="not a git checkout"):
        guarded_tree_delete(plain, context=_ctx())
    assert (plain / "f.txt").exists()


def test_tree_delete_of_a_missing_path_is_a_no_op(tmp_path: Path) -> None:
    guarded_tree_delete(tmp_path / "gone", context=_ctx())
