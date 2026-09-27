"""Unification routing gate (mission ``merge-destructive-op-safety-01M2XQF8``,
WP05/T018-T020, NFR-006/FR-007, ``contracts/routing-invariant.md``).

A non-vacuous architectural gate (DIRECTIVE_043) proving the defect class this
mission fixes (a destructive git command run against dirty/off-target state)
is closed BY CONSTRUCTION, not by reviewer goodwill:

1. **T018 -- routing/allowlist gate.** Every ``git reset --hard``,
   user-facing ``git worktree remove ... --force``, ``git merge --abort``,
   and ``git stash push`` command LITERAL under ``src/specify_cli/`` is
   either (a) inside the WP01 guard's own implementation (``git/destructive_guard.py``,
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

``git stash push`` census (user-content-preservation epic #4915, finding #1
of #4946, folded into PR #4936): PR #4936's #4888 fix already removed
``git stash push --staged`` / ``git stash pop --index`` from
``git/commit_helpers.py::safe_commit``, but nothing censused ``git stash``
argv literals repo-wide, and two dead helpers (``core/vcs/git.py::git_stash``
/ ``git_stash_pop``) still carried the footgun argv with no production
caller. Those helpers are deleted (mission ``fold-4946-stash-gate``); this
gate now censuses ``("stash", "push")`` the same way it censuses the other
three destructive patterns, so a FUTURE reintroduction of a raw
hide-then-restore stash call is caught here rather than relying on review.
The live census currently finds zero ``("stash", "push")`` argv literals
under ``src/specify_cli/``, so no ``_ALLOWLIST`` entry is needed.

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
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SPECIFY_CLI_ROOT,
    SRC_ROOT,
    argv_tokens,
    assert_changed_argument_is_unexpected,
    assert_partition_survives_drift,
    CensusKey,
    assert_second_identical_op_is_unexpected,
    census_keys,
    census_keys_for_sources,
    census_partition,
    describe_unexpected,
    diff_against_allowlist,
    drop_one_entry,
    enclosing_qualname,
    iter_py_files,
    module_string_constants,
    ordered_subsequence,
    parse,
    parse_with_source,
    read_sources,
    render_census_key,
    scan_planted_source,
    with_duplicated_statement,
    with_leading_argument,
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
_STASH_PUSH = "stash_push"

_PATTERN_NEEDLES: dict[str, tuple[str, ...]] = {
    _RESET_HARD: ("reset", "--hard"),
    _WORKTREE_REMOVE_FORCE: ("worktree", "remove", "--force"),
    _MERGE_ABORT: ("merge", "--abort"),
    _STASH_PUSH: ("stash", "push"),
}


def _classify_argv(tokens: list[str | None]) -> str | None:
    for pattern, needles in _PATTERN_NEEDLES.items():
        if ordered_subsequence(tokens, *needles):
            return pattern
    return None


def _find_destructive_literals(path: Path) -> list[tuple[int, str]]:
    """``(lineno, pattern)`` for every destructive-command argv literal in *path*."""
    tree = parse(path)
    consts = module_string_constants(tree)
    hits: list[tuple[int, str]] = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.List, _ast.Tuple)):
            pattern = _classify_argv(argv_tokens(node, consts))
            if pattern is not None:
                hits.append((node.lineno, pattern))
    return hits


def _live_sources() -> dict[str, str]:
    """``{repo-rel path: source}`` for every file the census scans."""
    return read_sources(iter_py_files(SPECIFY_CLI_ROOT))


def _census_keys(sources: Mapping[str, str]) -> dict[CensusKey, int]:
    """Content-keyed live census: ``{CensusKey: lineno}`` (the line is diagnostic only)."""
    return census_keys_for_sources(sources, _find_destructive_literals)


# ---------------------------------------------------------------------------
# The frozen allowlist. Built from a LIVE census of the integrated tree
# (post WP01-WP04). Each entry is keyed by CONTENT, not by line (mission
# ratchet-baseline-census-gate-remediation-01M3EW3Z, FR-006): ``CensusKey`` =
# (repo-relative path, enclosing qualname, normalized token line of the argv
# literal, op, op_ordinal among identical live sites in that function). An
# unrelated line shift never re-pins an entry; a second identical op or a
# changed argument is a NEW key and fails. Shrink-only: an entry whose site
# disappears only warns (stale), never fails. A NEW entry must be justified
# here in the SAME PR that introduces it -- paste the ``CensusKey(...)``
# literal from the gate's failure message.
# ---------------------------------------------------------------------------
_ALLOWLIST: dict[CensusKey, str] = {
    # --- reset --hard (5) --------------------------------------------------
    CensusKey(
        rel="src/specify_cli/doctrine/sources/git_source.py",
        qualname="GitSource._update",
        token_line="reset_proc = self . _run_git ( [ , , str ( target_dir ) , , , reset_target ] )",
        op="reset_hard",
        op_ordinal=0,
    ): (
        "guarded reset (#4989): _update runs `git reset --hard` on the persistent "
        "pack clone ONLY after _local_changes_refusal has fail-closed refused when "
        "the working tree holds uncommitted local changes OR carries local commits "
        "ahead of the reset target -- so this reset can never silently discard "
        "hand-authored pack content; the target itself is resolved by ref type "
        "(_resolve_reset_target) rather than blanket origin/<ref>. Rationale "
        "rewritten in WP03 (mission asset-preservation-migrate-fetch): the old "
        "'throwaway doctrine-pack clone' rationale was false after WP02 rewrote "
        "_update -- the clone is persistent (.git preserved across fetches) and "
        "the reset is now dirty/ahead-guarded, not unguarded."
    ),
    CensusKey(
        rel="src/specify_cli/consolidation/git_probes.py", qualname="_refresh_primary_checkout_after_merge", token_line="[ , , , ] ,", op="reset_hard", op_ordinal=0
    ): (
        "guarded by WP03/T011 (#4752): refuses via assert_checkout_on_target "
        "before this reset runs whenever expected_branch is supplied; the "
        "live merge preflight always supplies it."
    ),
    CensusKey(
        rel="src/specify_cli/git/ref_advance.py",
        qualname="advance_branch_ref",
        token_line="reset = _run_git ( worktree , [ , , branch ] , env = env )",
        op="reset_hard",
        op_ordinal=0,
    ): (
        "the reused guard primitive's OWN resync implementation -- this "
        "module defines _dirty_entries (the residue-aware dirty check every "
        "other guard call reuses) and only resets after that check already "
        "passed for this worktree. Re-pinned from :462 (#4997 follow-up, "
        "data-loss fix): the new public seam reset_would_obstruct_untracked "
        "(consumed by merge/preflight.py::is_pure_behind_head_lag, INV-3) "
        "was added earlier in the file, shifting this line; same "
        "advance_branch_ref resync site/rationale, confirmed by a direct read "
        "-- not a new destructive op."
    ),
    CensusKey(
        rel="src/specify_cli/lanes/worktree_allocator.py",
        qualname="_merge_dependency_lane_tips",
        token_line="[ , , , pre_loop_ref ] ,",
        op="reset_hard",
        op_ordinal=0,
    ): (
        "atomic rollback to a pre-loop ref (#1915) AFTER the loop's own "
        "half-merge was already aborted -- lane-loop-scoped recovery, not an "
        "arbitrary destroy of operator state."
    ),
    CensusKey(
        rel="src/specify_cli/consolidation/executor.py", qualname="_recover_behind_head_primary_on_resume", token_line="[ , , , ] ,", op="reset_hard", op_ordinal=0
    ): (
        "#4997 behind-own-HEAD resume recovery (_recover_behind_head_primary_on_resume): "
        "runs ONLY after a provably-pure-lag proof -- classify_resume_dirty_remedy == "
        "BEHIND_OWN_HEAD (lane already an ancestor of HEAD) AND is_pure_behind_head_lag "
        "(working tree AND index byte-identical to the persisted pre_mutation_target_sha, "
        "HEAD its strict descendant, no untracked file obstructing a restored path). It "
        "resets the primary to its OWN already-advanced HEAD (restoring phantom staged "
        "deletions), destroying nothing genuine; any deviation refuses fail-closed instead."
    ),
    # --- worktree remove --force (10) --------------------------------------
    CensusKey(
        rel="src/specify_cli/core/vcs/git.py",
        qualname="GitVCS.remove_workspace",
        token_line="[ , , , str ( workspace_path ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): (
        "dead adapter -- VcsProvider.remove_workspace has zero callers "
        "(contracts/routing-invariant.md); it is explicitly NOT the "
        "chokepoint (guarded_worktree_remove is)."
    ),
    CensusKey(
        rel="src/specify_cli/consolidation/ordering.py",
        qualname="_compute_next_mission_number_or_none",
        token_line="[ , , , str ( tmp_path ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("ephemeral detached scan worktree, torn down in the same function's own finally block; never operator-visible state."),
    CensusKey(
        rel="src/specify_cli/consolidation/ordering.py",
        qualname="_write_mission_number_to_branch",
        token_line="[ , , , str ( mission_tmp_path ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("ephemeral detached scan worktree (mission-number bake), same class as the sibling ordering.py:329 site."),
    CensusKey(
        rel="src/specify_cli/consolidation/workspace.py",
        qualname="cleanup_merge_workspace",
        token_line="[ , , , , str ( workspace_path ) ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("merge scratch workspace (C-006) -- always removed unconditionally by design, out of the guard's scope."),
    CensusKey(
        rel="src/specify_cli/review/baseline.py",
        qualname="_baseline_worktree",
        token_line="[ , , , str ( tmp_worktree ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("detached temp baseline-comparison worktree, torn down in the same context manager that created it."),
    CensusKey(
        rel="src/specify_cli/cli/commands/mission_type.py",
        qualname="_remove_lane_worktrees",
        token_line="[ , , str ( repo_root ) , , , str ( entry ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("reached only via `--discard` (_discard_mission): an operator-requested, intentional mission abandonment -- not an implicit/accidental destroy."),
    CensusKey(
        rel="src/specify_cli/git/destructive_guard.py",
        qualname="_remove_worktree_force",
        token_line="[ , , str ( worktree ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("the chokepoint's OWN inline implementation (_remove_worktree_force, called only from guarded_worktree_remove) -- this IS the guard, not a bypass of it."),
    CensusKey(
        rel="src/specify_cli/lanes/consolidation.py",
        qualname="preview_mission_target_integration",
        token_line="[ , , , str ( tmp_path ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): (
        "read-only forecast scratch worktree, created detached in the same "
        "ExitStack and force-removed even when the simulated merge leaves "
        "intentional conflict entries; never operator-visible state. "
        "Re-pinned from :969 (#5173 status.json reconcile inserted code "
        "earlier in the file); same site/rationale, confirmed by a direct read."
    ),
    CensusKey(
        rel="src/specify_cli/lanes/consolidation.py",
        qualname="_merge_branch_into",
        token_line="[ , , , str ( tmp_path ) , ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): ("ephemeral lane-merge tmp worktree, unconditionally cleaned up via ExitStack on exit."),
    CensusKey(
        rel="src/specify_cli/lanes/worktree_allocator.py",
        qualname="_remove_lane_worktree",
        token_line="[ , , , , str ( worktree_path ) ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): (
        "fresh-path atomicity (#3281/T010): removes a just-created worktree "
        "AFTER _merge_recorded_planning_commit already aborted the "
        "half-merge -- the tree is clean by construction; best-effort, "
        "reports a warning rather than raising on failure."
    ),
    CensusKey(
        rel="src/specify_cli/coordination/workspace.py",
        qualname="_remove_worktree_registration",
        token_line="[ , , str ( repo_root ) , _GIT_WORKTREE , , , str ( path ) ] ,",
        op="worktree_remove_force",
        op_ordinal=0,
    ): (
        "_remove_worktree_registration: prunes a registration whose "
        "worktree directory is already ABSENT from disk -- the guard "
        "cannot run here even in principle (it resolves the repo root by "
        "executing git INSIDE the worktree). GUARD-EXEMPT per the module's "
        "own docstring, not an unrouted/unexplained raw force-remove."
    ),
    # --- merge --abort (6) --------------------------------------------------
    CensusKey(rel="src/specify_cli/consolidation/state.py", qualname="abort_git_merge", token_line="[ , , ] ,", op="merge_abort", op_ordinal=0): (
        "abort_git_merge's own generic primitive; its one live caller "
        "(cli.commands.merge._dispatch_abort, WP04/#4754) passes only the "
        "scoped merge-workspace path, never repo_root (INV-5). Re-pinned "
        "from :638 (terminus-reconciliation-attribution-integrity, #5021 r1): "
        "the reconciliation_passed_target_sha resume-anchor field shifted the "
        "line, same primitive/rationale."
    ),
    CensusKey(rel="src/specify_cli/lanes/consolidation.py", qualname="_merge_branch_into", token_line="[ , , ] ,", op="merge_abort", op_ordinal=0): (
        "scoped to the ephemeral lane-merge tmp worktree (squash-conflict rollback), never repo_root."
    ),
    CensusKey(rel="src/specify_cli/lanes/consolidation.py", qualname="_merge_branch_into", token_line="[ , , ] ,", op="merge_abort", op_ordinal=1): (
        "scoped to the ephemeral lane-merge tmp worktree (merge-conflict rollback), never repo_root."
    ),
    CensusKey(
        rel="src/specify_cli/lanes/worktree_allocator.py", qualname="_merge_recorded_planning_commit", token_line="[ , , ] ,", op="merge_abort", op_ordinal=0
    ): ("scoped to the lane worktree (planning-commit merge-conflict rollback), never repo_root."),
    CensusKey(rel="src/specify_cli/lanes/worktree_allocator.py", qualname="_merge_dependency_lane_tips", token_line="[ , , ] ,", op="merge_abort", op_ordinal=0): (
        "scoped to the lane worktree (dependency-lane merge-conflict rollback), never repo_root."
    ),
    CensusKey(
        rel="src/specify_cli/lanes/auto_rebase.py", qualname="_abort_with_failure", token_line="_run ( [ , , ] , worktree_path )", op="merge_abort", op_ordinal=0
    ): ("scoped to the lane worktree (auto-rebase conflict rollback), never repo_root."),
}


def _census_partition(sources: Mapping[str, str]) -> tuple[set[CensusKey], set[CensusKey]]:
    """This gate's binding of :func:`census_partition` (finder + ``_ALLOWLIST``)."""
    return census_partition(_census_keys(sources), _ALLOWLIST)


#: Files-scanned floor (NFR-002): the finder scanned 1013 files on the planning
#: base (3717c7ea). A scan that silently shrinks below it is vacuous.
_FILES_SCANNED_FLOOR = 1013

#: Every file carrying an allowlisted site; the line-drift test runs per file.
_DRIFT_FILES: tuple[str, ...] = tuple(sorted({key.rel for key in _ALLOWLIST}))


def test_destructive_commands_only_at_allowlisted_or_guard_sites() -> None:
    """NFR-006/FR-007/INV-3: every destructive-command literal under
    ``src/specify_cli/`` is either inside the guard's own implementation or
    a member of the frozen, rationalized allowlist. A NEW site fails; a
    disappeared site only warns (shrink-only ratchet)."""
    sources = _live_sources()
    assert len(sources) >= _FILES_SCANNED_FLOOR, f"census scanned {len(sources)} files, below the pinned floor {_FILES_SCANNED_FLOOR}"
    unexpected, suppressed = _census_partition(sources)
    stale = set(_ALLOWLIST) - suppressed

    assert not unexpected, (
        "New destructive git command literal(s) found outside the routed "
        "guard (guarded_worktree_remove / assert_checkout_on_target / "
        "assert_worktree_clean) and the frozen allowlist (NFR-006/FR-007). "
        "Route the site through the guard, or add a rationale entry to "
        f"_ALLOWLIST in this file: {describe_unexpected(unexpected, sources, _find_destructive_literals)}"
    )
    assert suppressed, "Non-vacuity: the census suppressed no allowlisted site at all"
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
    rel_paths = {key.rel for key in _ALLOWLIST}
    missing = sorted(rel for rel in rel_paths if not (REPO_ROOT / rel).is_file())
    assert not missing, f"Allowlisted file(s) no longer exist: {missing}"


# ---------------------------------------------------------------------------
# Positive routing proof (C-003): the three LIVE user-facing force-removal
# call sites actually reach the shared chokepoint. The allowlist scan above
# proves no UNROUTED raw literal exists anywhere; this proves the specific
# known routed sites are not merely "absent because the file doesn't exist".
# ---------------------------------------------------------------------------
_ROUTED_WORKTREE_REMOVE_SITES: tuple[str, ...] = (
    "specify_cli/consolidation/executor.py",
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
    SPECIFY_CLI_ROOT / "consolidation",
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
        "specify_cli/consolidation/git_probes.py::_raw_porcelain_status",
        "specify_cli/consolidation/git_probes.py::_paths_have_status_changes",
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
    source, tree = parse_with_source(path)
    consts = module_string_constants(tree)
    hits: list[tuple[int, str]] = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.List, _ast.Tuple)) and ordered_subsequence(argv_tokens(node, consts), "status", "--porcelain"):
            hits.append((node.lineno, enclosing_qualname(source, node.lineno)))
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


def test_scanner_detects_a_planted_unrouted_stash_push(tmp_path: Path) -> None:
    """T020/non-vacuity for the ``git stash push`` needle (#4915/#4946): a
    planted, un-rationalized raw hide-then-restore stash call is caught by
    the exact scanner the primary allowlist gate runs."""
    hits = scan_planted_source(
        tmp_path,
        "planted_stash.py",
        'import subprocess\n\n\ndef _sneaky_hide(workspace_path):\n    subprocess.run(["git", "-C", str(workspace_path), "stash", "push"])\n',
        _find_destructive_literals,
    )
    assert hits == [(5, _STASH_PUSH)], f"Non-vacuity failure: the routing scanner did not detect a planted raw `git stash push` call. Got: {hits!r}."


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
    live = _census_keys(_live_sources())
    victim, shrunk_allowlist = drop_one_entry(_ALLOWLIST)

    unexpected, _stale = diff_against_allowlist(live, shrunk_allowlist)

    assert victim in unexpected, (
        f"Self-mutation check failed: removing {victim!r} from the allowlist "
        "did not reproduce a gate failure against the live tree. The primary "
        "routing gate is vacuous -- investigate diff_against_allowlist / "
        "_census_keys before trusting a green run."
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


# ---------------------------------------------------------------------------
# Line-drift tolerance (NFR-001) and non-widening (FR-006) through the seam.
# ---------------------------------------------------------------------------

_NON_WIDENING_REL = "src/specify_cli/lanes/consolidation.py"


def _site_linenos(rel: str, op: str | None = None) -> list[int]:
    return sorted(lineno for lineno, hit_op in _find_destructive_literals(REPO_ROOT / rel) if op is None or hit_op == op)


def test_destructive_drift_files_cover_the_allowlist() -> None:
    """Companion floor: the drift test runs over at least the 15 allowlisted files."""
    assert len(_DRIFT_FILES) >= 15, _DRIFT_FILES


@pytest.mark.parametrize("rel", _DRIFT_FILES)
def test_destructive_census_survives_line_drift(rel: str) -> None:
    """NFR-001: an unrelated line shift (blank line at the top; a probe
    statement above every census site) leaves ``(unexpected, suppressed)``
    unchanged. RED on the line-keyed allowlist, GREEN on content keys."""
    source = (REPO_ROOT / rel).read_text(encoding="utf-8")
    file_keys = [key for key in _ALLOWLIST if key.rel == rel]
    assert_partition_survives_drift(rel, source, _census_partition, _site_linenos(rel), file_keys)


def test_second_identical_op_in_exempted_function_fails() -> None:
    """Non-widening guard: duplicating an exempted ``merge --abort`` statement
    inside its function is reported as unexpected. GREEN on the line-keyed base
    (a new line already yields a new key) and must stay GREEN on content keys
    (``op_ordinal`` makes the duplicate a new key)."""
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    lineno = _site_linenos(_NON_WIDENING_REL, _MERGE_ABORT)[0]
    assert_second_identical_op_is_unexpected(_NON_WIDENING_REL, source, _census_partition, lineno)


def test_changed_argument_on_exempted_op_fails() -> None:
    """Non-widening guard: adding a NAME element to an exempted argv literal
    (same line, so the line count is unchanged) makes the site unexpected and
    its old entry stale. RED on the line-keyed base (the ``path:line:op`` key
    silently keeps blessing the changed argument); GREEN on content keys (the
    token line changes). Editing only a string element would not change the
    tokens: ``composite_key`` strips strings."""
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    lineno = _site_linenos(_NON_WIDENING_REL, _MERGE_ABORT)[0]
    mutated = with_leading_argument(source, lineno, (_ast.List, _ast.Tuple))
    assert_changed_argument_is_unexpected(_NON_WIDENING_REL, source, _census_partition, mutated)


# ---------------------------------------------------------------------------
# CensusKey construction (T018): ordinals, file and op separation, rendering.
# ---------------------------------------------------------------------------

_TWIN_SOURCE = (
    "import subprocess\n\n\n"
    "def rollback(wt):\n"
    '    subprocess.run(["git", "-C", wt, "merge", "--abort"])\n'
    "    wt.touch()\n"
    '    subprocess.run(["git", "-C", wt, "merge", "--abort"])\n'
)


def test_census_keys_assign_ordinals_to_a_same_key_pair() -> None:
    """Two identical ops in one function share ``(qualname, token_line, op)``
    and are told apart only by ``op_ordinal``, in line order."""
    keys = census_keys("pkg/mod.py", _TWIN_SOURCE, [(7, _MERGE_ABORT), (5, _MERGE_ABORT)])
    token_line = "subprocess . run ( [ , , wt , , ] )"
    assert keys == {
        CensusKey("pkg/mod.py", "rollback", token_line, _MERGE_ABORT, 0): 5,
        CensusKey("pkg/mod.py", "rollback", token_line, _MERGE_ABORT, 1): 7,
    }


def test_census_keys_are_distinct_across_files() -> None:
    """The same site in two files yields two keys: ``rel`` is part of the key."""
    first = census_keys("pkg/a.py", _TWIN_SOURCE, [(5, _MERGE_ABORT)])
    second = census_keys("pkg/b.py", _TWIN_SOURCE, [(5, _MERGE_ABORT)])
    assert first.keys().isdisjoint(second.keys())


def test_census_keys_are_distinct_across_ops() -> None:
    """Two op labels on one line never share an ordinal sequence."""
    keys = census_keys("pkg/mod.py", _TWIN_SOURCE, [(5, _MERGE_ABORT), (5, _RESET_HARD)])
    assert {(key.op, key.op_ordinal) for key in keys} == {(_MERGE_ABORT, 0), (_RESET_HARD, 0)}


def test_render_census_key_names_identity_line_and_tokens() -> None:
    """Failure output carries ``rel::qualname::op#ordinal``, the diagnostic line
    and the token line, so an author can write the ``CensusKey(...)`` literal."""
    [(key, lineno)] = census_keys("pkg/mod.py", _TWIN_SOURCE, [(7, _MERGE_ABORT)]).items()
    rendered = render_census_key(key, lineno)
    assert rendered == f"pkg/mod.py::rollback::{_MERGE_ABORT}#0 (line 7) tokens=subprocess . run ( [ , , wt , , ] )"


# ---------------------------------------------------------------------------
# T024 -- real-data ordinal non-widening and actionable failure output.
# ---------------------------------------------------------------------------

_TWIN_QUALNAME = "_merge_branch_into"


def _twin_merge_abort_keys() -> list[CensusKey]:
    return sorted(key for key in _ALLOWLIST if key.rel == _NON_WIDENING_REL and key.qualname == _TWIN_QUALNAME and key.op == _MERGE_ABORT)


def test_duplicating_the_twin_merge_abort_reports_op_ordinal_2() -> None:
    """``lanes/consolidation.py::_merge_branch_into`` holds the two exempted
    ``merge --abort`` twins (``op_ordinal`` 0 and 1). A third identical one is
    ``op_ordinal=2``: not in the allowlist, so the gate reports it."""
    twins = _twin_merge_abort_keys()
    assert [key.op_ordinal for key in twins] == [0, 1], twins
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    live = census_keys(_NON_WIDENING_REL, source, _find_destructive_literals(REPO_ROOT / _NON_WIDENING_REL))
    second_twin_line = live[twins[1]]

    unexpected, suppressed = _census_partition({_NON_WIDENING_REL: with_duplicated_statement(source, second_twin_line)})

    assert unexpected == {twins[1]._replace(op_ordinal=2)}
    assert set(twins) <= suppressed


def test_gate_failure_message_renders_identity_line_and_tokens() -> None:
    """An unexpected key is rendered as ``rel::qualname::op#ordinal (line N)
    tokens=...`` so the author can write the ``CensusKey(...)`` literal."""
    twin = _twin_merge_abort_keys()[1]
    source = (REPO_ROOT / _NON_WIDENING_REL).read_text(encoding="utf-8")
    line = census_keys(_NON_WIDENING_REL, source, _find_destructive_literals(REPO_ROOT / _NON_WIDENING_REL))[twin]
    mutated = with_duplicated_statement(source, line)
    unexpected, _ = _census_partition({_NON_WIDENING_REL: mutated})

    [rendered] = describe_unexpected(unexpected, {_NON_WIDENING_REL: mutated}, _find_destructive_literals)

    assert rendered.startswith(f"{_NON_WIDENING_REL}::{_TWIN_QUALNAME}::{_MERGE_ABORT}#2 (line ")
    assert rendered.endswith(f"tokens={twin.token_line}")


def test_census_partition_splits_unexpected_from_suppressed() -> None:
    """The shared seam: a live key absent from the allowlist is unexpected, a
    live allowlisted key is suppressed, and a stale allowlist key is neither."""
    live = {"kept": 10, "new": 20}
    allowlist = {"kept": "rationale", "gone": "rationale"}
    assert census_partition(live, allowlist) == ({"new"}, {"kept"})
