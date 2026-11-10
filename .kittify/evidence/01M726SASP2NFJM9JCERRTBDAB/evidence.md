# Code grounding: #7493 (Op 01M726SASP2NFJM9JCERRTBDAB)

Base: origin/main 9518fb71. Parent epic #2017.

## Defect, confirmed on HEAD
- `lanes/implement_support.py::_ensure_repo_root_checkout_available` (single_branch only) computes dirt via
  `checkout_occupancy.dirty_paths(write_checkout, owned_prefixes=_owned_status_prefixes(slug))` and raises
  `WriteCheckoutDirtyError` (WRITE_CHECKOUT_DIRTY). `_owned_status_prefixes` has no entry for
  `kitty-specs/<m>/decisions/index.json.lock`; `dirty_paths` consults no predicate.
- `dirty_paths` has exactly ONE caller (the claim check), so option B in the issue covers no other caller.

## Second defect found while reproducing (folded)
- Through the CLI verb (`spec-kitty implement` / the claim seam), the planning auto-commit
  (`cli/commands/implement_planning_commit.py::_ensure_planning_artifacts_committed_git`, staging core
  `implement_cores.resolve_planning_artifact_staging`) COMMITS the lock as
  "chore: planning artifacts for <slug>" before the claim check runs. That violates #5925/#6628
  ("no committer may stage it") on every topology, and on single_branch it is why the claim then passes.
- Red reproduction: `test_cli_implement_accepts_decisions_runtime_lock` (exit 0, lock in `git ls-files`).

## Fix choice
- Claim check: neither literal option. A slug-exact entry in `_owned_status_prefixes` (option A) still refuses on
  ANOTHER Mission's lock in a shared single_branch checkout (red test
  `test_another_missions_decisions_lock_in_shared_write_checkout_is_not_dirty`), contradicting #6628
  ("no dirty-state gate may refuse on it"). Putting the predicate inside generic `dirty_paths` (option B) would
  break its "caller names what it excludes" contract (NFR-004). Chosen: a `_claim_dirty_paths` helper in the
  caller that applies the ONE predicate `coherence.is_decisions_runtime_lock` after the claim's own list. The
  claim does not adopt `is_self_bookkeeping_churn`, so the "do not align the lists" docstring holds.
- Auto-commit: drop the lock in `_feature_dir_status_entries` (status + structural legs) and in the coordination
  walk leg, mirroring the dossier-snapshot exclusion beside it.

## Other dirty-state gates (squad sweep; no change needed)
record-analysis (is_self_bookkeeping_churn), accept (untracked skipped; ledger_dirt excludes lock),
consolidate primary probe + entry_preflight (ResidueContext -> is_self_bookkeeping_churn; another Mission's lock
in a mission worktree still dirt, consistent with #5966), planning_commit, move-task Check 1
(is_toolchain_generated_churn), settlement/create switch (Mission dir exempt), finalize-tasks (explicit names).
Residual, lane-only, low risk (decision service writes the placement surface, not lanes): for_review
`_check_uncommitted_worktree_changes`, allocator `_validate_worktree_clean`, move-task lane auto-commit.
Collapsed untracked `decisions/` holding only the lock is reported as the directory (same as record-analysis);
not changed here.

## Invariants kept
#5925 (lock persists, never staged), #6628 (depth-exact predicate, single owner), #5930 claim list untouched,
"Do not align the lists" docstring (only the one lock rule borrowed, documented).

## Gates run
test_layer_rules, test_status_read_single_door, test_lane_adoption_single_seam, test_status_events_writes_gate,
test_exemption_registry_ratchet, test_commit_scope_owner, test_wp_integrity_partition_call_shape,
test_no_dead_symbols, test_status_module_boundary, test_no_legacy_terminology: green.

## Folds
- Folded: the planning auto-commit staging the lock (same verb, same invariant, found by the red CLI test).
- Not folded: #6293 (orchestrator-api mid8 handle into `_owned_status_prefixes`; different fix), #6836, #6298,
  #7331, #5938 (different surfaces). No other #2017 child touches the claim dirty check.

## Delivery shape
Governed Op (small, local, no contract change), not a Mission.
