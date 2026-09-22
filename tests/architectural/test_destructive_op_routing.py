"""Unification routing gate (mission ``merge-destructive-op-safety-01M2XQF8``,
WP05/T018-T020, NFR-006/FR-007, ``contracts/routing-invariant.md``).

A non-vacuous architectural gate (DIRECTIVE_043) proving the defect class this
mission fixes (a destructive git command run against dirty/off-target state)
is closed BY CONSTRUCTION, not by reviewer goodwill:

1. **T018 -- routing/allowlist gate.** Every ``git reset --hard``,
   user-facing ``git worktree remove ... --force``, and ``git merge --abort``
   command LITERAL under ``src/specify_cli/`` is either (a) inside the WP01
   guard's own implementation (``git/destructive_guard.py``,
   ``git/ref_advance.py``), (b) reached only via the shared
   ``guarded_worktree_remove`` chokepoint (proven separately -- those live
   call sites carry no raw literal at all, by construction), or (c) a member
   of the frozen, individually-rationalized ``_ALLOWLIST`` below. The census
   is LIVE (AST-driven, re-run every test run against the actual tree) --
   not a hand-copied snapshot -- and shrink-only: a site disappearing from
   source is a (non-failing) prompt to trim the allowlist; a NEW raw literal
   outside both the guard and the allowlist fails the gate.
2. **T019 -- no new parallel dirty predicate.** The guard reuses
   ``ref_advance._dirty_entries`` (data-model.md); this asserts no NEW
   module-level ``git status --porcelain``-parsing "is dirty" predicate was
   introduced in the ``git``/``merge``/``coordination``/``core/vcs`` seams
   beyond the pre-existing, curated baseline.
3. **T020 -- self-mutation (non-vacuity).** Both scans are proven to
   actually bite: a planted, un-rationalized destructive-command literal (or
   a planted new dirty predicate) is detected by the SAME scanner the primary
   gates use, and separately, temporarily dropping one real entry from each
   frozen baseline reproduces the exact failure the primary gate would raise
   for a genuine regression -- proving the diff logic itself is not vacuous.

Detection strategy
-------------------
A bare text ``grep`` for ``"reset", "--hard"`` would miss the one real
indirection this codebase has (``coordination/workspace.py``'s
``_GIT_WORKTREE = "worktree"`` module constant, used in place of the string
literal at the one intentionally-guard-exempt call site). This gate instead
walks every ``ast.List``/``ast.Tuple`` literal, resolves each element that is
either a string constant or a `Name` bound to a module-level string constant,
and matches an ORDERED (not necessarily contiguous) subsequence of the
target command's tokens -- so ``[..., _GIT_WORKTREE, "remove", "--force",
...]`` is caught exactly like the literal spelling.

Known, out-of-band scope note (C-004 follow-up, NOT this gate's job)
---------------------------------------------------------------------
A separate, deferred loss surface -- standalone ``git branch -D`` deleting an
unmerged branch's commits (``merge/executor.py``, ``orchestrator_api/``,
``core/mission_creation.py``) -- needs its own is-branch-merged guard. It is
a distinct command family from the three NFR-006 names and is intentionally
out of this gate's scope; tracked as a follow-up mission in the WP05 PR body.
"""

from __future__ import annotations

import ast as _ast
import warnings
from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SPECIFY_CLI_ROOT,
    SRC_ROOT,
    argv_tokens,
    diff_against_allowlist,
    drop_one_entry,
    enclosing_qualname,
    iter_py_files,
    module_string_constants,
    ordered_subsequence,
    parse,
    scan_planted_source,
)

pytestmark = pytest.mark.architectural

# The AST plumbing (file iteration, parsing, module-constant resolution, argv
# tokenisation, ordered-subsequence matching, qualname resolution, the
# allowlist diff, and the self-mutation harness) is the single shared authority
# in ``_destructive_op_census`` (DIRECTIVE_044); this file keeps only the
# git-argv classifier and its ``_ALLOWLIST``.

# ---------------------------------------------------------------------------
# T018 -- destructive-command routing/allowlist gate
# ---------------------------------------------------------------------------

_RESET_HARD = "reset_hard"
_WORKTREE_REMOVE_FORCE = "worktree_remove_force"
_MERGE_ABORT = "merge_abort"

_PATTERN_NEEDLES: dict[str, tuple[str, ...]] = {
    _RESET_HARD: ("reset", "--hard"),
    _WORKTREE_REMOVE_FORCE: ("worktree", "remove", "--force"),
    _MERGE_ABORT: ("merge", "--abort"),
}


def _classify_argv(tokens: list[str | None]) -> str | None:
    for pattern, needles in _PATTERN_NEEDLES.items():
        if ordered_subsequence(tokens, *needles):
            return pattern
    return None


def _find_destructive_literals(path: Path) -> list[tuple[int, str]]:
    """``(lineno, pattern)`` for every destructive-command argv literal in *path*."""
    tree = parse(path)
    if tree is None:
        return []
    consts = module_string_constants(tree)
    hits: list[tuple[int, str]] = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.List, _ast.Tuple)):
            pattern = _classify_argv(argv_tokens(node, consts))
            if pattern is not None:
                hits.append((node.lineno, pattern))
    return hits


def _scan_repo_for_destructive_literals() -> dict[str, list[tuple[int, str]]]:
    violations: dict[str, list[tuple[int, str]]] = {}
    for py_file in iter_py_files(SPECIFY_CLI_ROOT):
        hits = _find_destructive_literals(py_file)
        if hits:
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            violations[rel] = hits
    return violations


def _flatten(live: dict[str, list[tuple[int, str]]]) -> set[str]:
    return {f"{rel}:{lineno}:{pattern}" for rel, hits in live.items() for lineno, pattern in hits}


# ---------------------------------------------------------------------------
# The frozen allowlist. Built from a LIVE census of the integrated tree
# (post WP01-WP04) -- every entry below was verified present, at the line
# shown, by the census this file's own scanner reproduces. Shrink-only: an
# entry whose site disappears is reported by ``test_growth_fails_shrinkage_warns``-
# style shrink warning, never a failure. A NEW entry must be justified here
# in the SAME PR that introduces it.
# ---------------------------------------------------------------------------
_ALLOWLIST: dict[str, str] = {
    # --- reset --hard (4) --------------------------------------------------
    "src/specify_cli/doctrine/sources/git_source.py:98:reset_hard": (
        "doctrine pack CLONE dir (not repo_root) -- git_source.py owns its own "
        "fetch+reset consistency story for a throwaway doctrine-pack clone, "
        "unrelated to the operator checkout the guard protects."
    ),
    "src/specify_cli/merge/git_probes.py:239:reset_hard": (
        "guarded by WP03/T011 (#4752): refuses via assert_checkout_on_target "
        "before this reset runs whenever expected_branch is supplied; the "
        "live merge preflight always supplies it."
    ),
    "src/specify_cli/git/ref_advance.py:415:reset_hard": (
        "the reused guard primitive's OWN resync implementation -- this "
        "module defines _dirty_entries (the residue-aware dirty check every "
        "other guard call reuses) and only resets after that check already "
        "passed for this worktree."
    ),
    "src/specify_cli/lanes/worktree_allocator.py:967:reset_hard": (
        "atomic rollback to a pre-loop ref (#1915) AFTER the loop's own "
        "half-merge was already aborted -- lane-loop-scoped recovery, not an "
        "arbitrary destroy of operator state."
    ),
    # --- worktree remove --force (10) --------------------------------------
    "src/specify_cli/core/vcs/git.py:222:worktree_remove_force": (
        "dead adapter -- VcsProvider.remove_workspace has zero callers "
        "(contracts/routing-invariant.md); it is explicitly NOT the "
        "chokepoint (guarded_worktree_remove is)."
    ),
    "src/specify_cli/merge/ordering.py:329:worktree_remove_force": (
        "ephemeral detached scan worktree, torn down in the same function's own finally block; never operator-visible state."
    ),
    "src/specify_cli/merge/ordering.py:667:worktree_remove_force": (
        "ephemeral detached scan worktree (mission-number bake), same class as the sibling ordering.py:329 site."
    ),
    "src/specify_cli/merge/workspace.py:113:worktree_remove_force": (
        "merge scratch workspace (C-006) -- always removed unconditionally by design, out of the guard's scope."
    ),
    "src/specify_cli/review/baseline.py:294:worktree_remove_force": (
        "detached temp baseline-comparison worktree, torn down in the same context manager that created it."
    ),
    "src/specify_cli/cli/commands/mission_type.py:1181:worktree_remove_force": (
        "reached only via `--discard` (_discard_mission): an operator-requested, intentional mission abandonment -- not an implicit/accidental destroy."
    ),
    "src/specify_cli/git/destructive_guard.py:229:worktree_remove_force": (
        "the chokepoint's OWN inline implementation (_remove_worktree_force, called only from guarded_worktree_remove) -- this IS the guard, not a bypass of it."
    ),
    "src/specify_cli/lanes/merge.py:772:worktree_remove_force": ("ephemeral lane-merge tmp worktree, unconditionally cleaned up via ExitStack on exit."),
    "src/specify_cli/lanes/worktree_allocator.py:1155:worktree_remove_force": (
        "fresh-path atomicity (#3281/T010): removes a just-created worktree "
        "AFTER _merge_recorded_planning_commit already aborted the "
        "half-merge -- the tree is clean by construction; best-effort, "
        "reports a warning rather than raising on failure."
    ),
    "src/specify_cli/coordination/workspace.py:204:worktree_remove_force": (
        "_remove_worktree_registration: prunes a registration whose "
        "worktree directory is already ABSENT from disk -- the guard "
        "cannot run here even in principle (it resolves the repo root by "
        "executing git INSIDE the worktree). GUARD-EXEMPT per the module's "
        "own docstring, not an unrouted/unexplained raw force-remove."
    ),
    # --- merge --abort (6) --------------------------------------------------
    "src/specify_cli/merge/state.py:493:merge_abort": (
        "abort_git_merge's own generic primitive; its one live caller "
        "(cli.commands.merge._dispatch_abort, WP04/#4754) passes only the "
        "scoped merge-workspace path, never repo_root (INV-5)."
    ),
    "src/specify_cli/lanes/merge.py:812:merge_abort": ("scoped to the ephemeral lane-merge tmp worktree (squash-conflict rollback), never repo_root."),
    "src/specify_cli/lanes/merge.py:918:merge_abort": ("scoped to the ephemeral lane-merge tmp worktree (merge-conflict rollback), never repo_root."),
    "src/specify_cli/lanes/worktree_allocator.py:785:merge_abort": ("scoped to the lane worktree (planning-commit merge-conflict rollback), never repo_root."),
    "src/specify_cli/lanes/worktree_allocator.py:959:merge_abort": ("scoped to the lane worktree (dependency-lane merge-conflict rollback), never repo_root."),
    "src/specify_cli/lanes/auto_rebase.py:739:merge_abort": ("scoped to the lane worktree (auto-rebase conflict rollback), never repo_root."),
}


def test_destructive_commands_only_at_allowlisted_or_guard_sites() -> None:
    """NFR-006/FR-007/INV-3: every destructive-command literal under
    ``src/specify_cli/`` is either inside the guard's own implementation or
    a member of the frozen, rationalized allowlist. A NEW site fails; a
    disappeared site only warns (shrink-only ratchet)."""
    live_flat = _flatten(_scan_repo_for_destructive_literals())
    unexpected, stale = diff_against_allowlist(live_flat, _ALLOWLIST)

    assert not unexpected, (
        "New destructive git command literal(s) found outside the routed "
        "guard (guarded_worktree_remove / assert_checkout_on_target / "
        "assert_worktree_clean) and the frozen allowlist (NFR-006/FR-007). "
        "Route the site through the guard, or add a rationale entry to "
        f"_ALLOWLIST in this file: {sorted(unexpected)}"
    )
    if stale:
        warnings.warn(
            f"Shrink-only allowlist: the following site(s) no longer carry a raw destructive-command literal -- safe to delete from _ALLOWLIST: {sorted(stale)}",
            UserWarning,
            stacklevel=1,
        )


def test_allowlisted_files_exist() -> None:
    """Sanity: a renamed/deleted allowlisted file must not silently drop out
    of the scan (an absent file reads as zero live hits, i.e. a false
    "shrink", masking a rename the allowlist should track by path)."""
    rel_paths = {key.rsplit(":", 2)[0] for key in _ALLOWLIST}
    missing = sorted(rel for rel in rel_paths if not (REPO_ROOT / rel).is_file())
    assert not missing, f"Allowlisted file(s) no longer exist: {missing}"


# ---------------------------------------------------------------------------
# Positive routing proof (C-003): the three LIVE user-facing force-removal
# call sites actually reach the shared chokepoint. The allowlist scan above
# proves no UNROUTED raw literal exists anywhere; this proves the specific
# known routed sites are not merely "absent because the file doesn't exist".
# ---------------------------------------------------------------------------
_ROUTED_WORKTREE_REMOVE_SITES: tuple[str, ...] = (
    "specify_cli/merge/executor.py",
    "specify_cli/coordination/workspace.py",
    "specify_cli/orchestrator_api/commands.py",
)


def test_live_worktree_removal_sites_route_through_the_guard() -> None:
    """C-003: merge lane cleanup, coordination teardown+stale-prune, and
    orchestrator cleanup each call ``guarded_worktree_remove`` -- not a raw
    ``git worktree remove --force``."""
    missing = [rel for rel in _ROUTED_WORKTREE_REMOVE_SITES if "guarded_worktree_remove(" not in (SRC_ROOT / rel).read_text(encoding="utf-8")]
    assert not missing, f"Expected routed site(s) no longer call guarded_worktree_remove(...): {missing}"


# ---------------------------------------------------------------------------
# T019 -- no new parallel dirty predicate
# ---------------------------------------------------------------------------

_DIRTY_PREDICATE_SEAM_DIRS: tuple[Path, ...] = (
    SPECIFY_CLI_ROOT / "git",
    SPECIFY_CLI_ROOT / "merge",
    SPECIFY_CLI_ROOT / "coordination",
    SPECIFY_CLI_ROOT / "core" / "vcs",
)

#: Pre-existing (as of this mission's base) ``git status --porcelain``-parsing
#: "is dirty" functions in the merge/vcs/coordination/git seam, PLUS the
#: reused ``_dirty_entries`` primitive. ``git/destructive_guard.py`` (the
#: WP01 guard) deliberately carries ZERO entries here: it calls
#: ``ref_advance._dirty_entries`` rather than parsing porcelain itself
#: (INV-3) -- a new porcelain-parsing function appearing there or anywhere
#: else in these seams beyond this set is exactly the regression T019 guards
#: against.
_KNOWN_DIRTY_PREDICATES: frozenset[str] = frozenset(
    {
        "specify_cli/merge/git_probes.py::_raw_porcelain_status",
        "specify_cli/merge/git_probes.py::_paths_have_status_changes",
        "specify_cli/git/ref_advance.py::_dirty_entries",
        "specify_cli/coordination/transaction.py::BookkeepingTransaction._worktree_has_pending_changes",
        "specify_cli/coordination/commit_router.py::_paths_uncommitted_in_primary",
        "specify_cli/core/vcs/git.py::GitVCS.get_workspace_info",
        "specify_cli/core/vcs/git.py::GitVCS.detect_conflicts",
        "specify_cli/core/vcs/git.py::GitVCS.has_conflicts",
        # Pre-existing, unrelated problem domain (sparse-checkout remediation,
        # not merge/worktree-removal safety) -- predates this mission.
        "specify_cli/git/sparse_checkout_remediation.py::_is_dirty",
        "specify_cli/git/sparse_checkout_remediation.py::_run_remediation_steps",
    }
)


def _status_porcelain_hits(path: Path) -> list[tuple[int, str]]:
    """``(lineno, qualname)`` for every ``git status --porcelain`` argv
    literal in *path* -- deliberately NOT ``git worktree list --porcelain``
    (a different subcommand, listing worktrees rather than checking
    dirtiness), tagged with its enclosing function/method's qualname."""
    tree = parse(path)
    if tree is None:
        return []
    consts = module_string_constants(tree)
    hits: list[tuple[int, str]] = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.List, _ast.Tuple)) and ordered_subsequence(argv_tokens(node, consts), "status", "--porcelain"):
            hits.append((node.lineno, enclosing_qualname(tree, node.lineno)))
    return hits


def _scan_dirty_predicates() -> set[str]:
    found: set[str] = set()
    for seam_root in _DIRTY_PREDICATE_SEAM_DIRS:
        for py_file in iter_py_files(seam_root):
            rel = py_file.relative_to(SRC_ROOT).as_posix()
            for _lineno, qualname in _status_porcelain_hits(py_file):
                found.add(f"{rel}::{qualname}")
    return found


def test_no_new_parallel_dirty_predicate_beyond_known_baseline() -> None:
    """INV-3/NFR-006: no NEW ``git status --porcelain``-parsing 'is dirty'
    predicate was introduced in the git/merge/coordination/core-vcs seams
    beyond the pre-existing, curated baseline (which already reuses
    ``ref_advance._dirty_entries`` rather than duplicating it)."""
    live = _scan_dirty_predicates()
    unexpected = live - _KNOWN_DIRTY_PREDICATES
    assert not unexpected, (
        "New `git status --porcelain`-parsing 'is dirty' predicate "
        "introduced in the merge/vcs/coordination/git seam beyond the "
        "reused ref_advance._dirty_entries + WP01 guard (INV-3/NFR-006). "
        "Reuse _dirty_entries (via destructive_guard.assert_worktree_clean "
        f"/ guarded_worktree_remove) instead of hand-rolling another: {sorted(unexpected)}"
    )


# ---------------------------------------------------------------------------
# T020 -- self-mutation (non-vacuity) proof, both directions, for both gates.
# ---------------------------------------------------------------------------


def test_scanner_detects_a_planted_unrouted_worktree_remove_force(tmp_path: Path) -> None:
    """A planted, un-rationalized raw force-remove is caught by the exact
    scanner the primary allowlist gate runs."""
    hits = scan_planted_source(
        tmp_path,
        "planted_unrouted.py",
        'import subprocess\n\n\ndef _sneaky_cleanup(worktree):\n    subprocess.run(["git", "worktree", "remove", str(worktree), "--force"])\n',
        _find_destructive_literals,
    )
    assert hits == [(5, _WORKTREE_REMOVE_FORCE)], (
        f"Non-vacuity failure: the routing scanner did not detect a planted raw `git worktree remove --force` call. Got: {hits!r}."
    )


def test_scanner_resolves_module_constant_indirection(tmp_path: Path) -> None:
    """The real ``_GIT_WORKTREE = "worktree"`` indirection
    (``coordination/workspace.py``) must not evade detection -- a
    name-only-literal scanner would be structurally blind to it, a live
    false-negative vacuity risk."""
    hits = scan_planted_source(
        tmp_path,
        "planted_indirection.py",
        "import subprocess\n\n"
        '_GIT_WORKTREE = "worktree"\n\n\n'
        "def _remove(repo_root, path):\n"
        '    subprocess.run(["git", "-C", str(repo_root), _GIT_WORKTREE, "remove", "--force", str(path)])\n',
        _find_destructive_literals,
    )
    assert hits == [(7, _WORKTREE_REMOVE_FORCE)], (
        f"Non-vacuity failure: the scanner did not resolve a module-level string-constant indirection for the destructive-command literal. Got: {hits!r}."
    )


def test_scanner_does_not_flag_unrelated_worktree_calls(tmp_path: Path) -> None:
    """Control: ``worktree add`` / ``worktree list --porcelain`` (no
    ``remove``+``--force``) must not be flagged -- proves the scanner isn't
    simply matching on the word "worktree" (vacuous in the OTHER direction)."""
    hits = scan_planted_source(
        tmp_path,
        "planted_benign.py",
        "import subprocess\n\n\n"
        "def _list_and_add(repo_root, path, branch):\n"
        '    subprocess.run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"])\n'
        '    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", str(path), branch])\n',
        _find_destructive_literals,
    )
    assert hits == []


def test_removing_an_allowlist_entry_reproduces_a_gate_failure() -> None:
    """Non-vacuity (T020): temporarily dropping ONE real allowlist entry and
    re-diffing against the ACTUAL live scan reproduces exactly the failure
    the primary gate (``test_destructive_commands_only_at_allowlisted_or_guard_sites``)
    would raise if that site were ever un-routed and un-rationalized --
    proving the primary gate is not vacuously green."""
    live_flat = _flatten(_scan_repo_for_destructive_literals())
    victim, shrunk_allowlist = drop_one_entry(_ALLOWLIST)

    unexpected, _stale = diff_against_allowlist(live_flat, shrunk_allowlist)

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the allowlist "
        "did not reproduce a gate failure against the live tree. The primary "
        "routing gate is vacuous -- investigate diff_against_allowlist / "
        "_scan_repo_for_destructive_literals before trusting a green run."
    )


def test_predicate_scan_detects_a_planted_new_predicate(tmp_path: Path) -> None:
    """A planted, brand-new porcelain-parsing 'is dirty' function is caught
    by the exact scanner the primary no-new-predicate gate runs."""
    hits = scan_planted_source(
        tmp_path,
        "planted_predicate.py",
        "import subprocess\n\n\n"
        "def _is_worktree_dirty(path):\n"
        "    result = subprocess.run(\n"
        '        ["git", "status", "--porcelain"], cwd=path, capture_output=True\n'
        "    )\n"
        "    return bool(result.stdout)\n",
        _status_porcelain_hits,
    )
    assert [qualname for _lineno, qualname in hits] == ["_is_worktree_dirty"], (
        f"Non-vacuity failure: the predicate scanner did not detect a planted new dirty predicate. Got: {hits!r}."
    )


def test_predicate_scan_does_not_flag_worktree_list(tmp_path: Path) -> None:
    """Control: ``git worktree list --porcelain`` (a different subcommand,
    never an 'is dirty' check) must not be flagged."""
    hits = scan_planted_source(
        tmp_path,
        "planted_worktree_list.py",
        'import subprocess\n\n\ndef _list_worktrees(repo_root):\n    return subprocess.run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"])\n',
        _status_porcelain_hits,
    )
    assert hits == []


def test_removing_a_known_predicate_reproduces_a_gate_failure() -> None:
    """Non-vacuity (T020): temporarily dropping ONE real entry from the
    known-predicate baseline and re-scanning the ACTUAL seam directories
    reproduces exactly the failure
    ``test_no_new_parallel_dirty_predicate_beyond_known_baseline`` would
    raise for a genuine new-predicate regression."""
    live = _scan_dirty_predicates()
    victim = next(iter(_KNOWN_DIRTY_PREDICATES))
    shrunk_baseline = _KNOWN_DIRTY_PREDICATES - {victim}

    unexpected = live - shrunk_baseline

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the known-"
        "predicate baseline did not reproduce a gate failure against the "
        "live seam scan -- the no-new-predicate check is vacuous."
    )
