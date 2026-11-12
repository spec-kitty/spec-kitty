# WP02 review feedback (cycle 1) - reviewer-renata (claude-reviewer)

Verdict: changes requested (one small blocker). Everything else verified and good:
red->green proven (c2da8428 red for the right reasons with the adapter stubbed in:
11 wiring tests fail on missing key/block; 161 green at tip), goldens gain exactly one
key, planted-change test uses one fixture with a tmp root venv (2/2 lane incl.
grandchild, 1/1 root), review prompt change is exactly one call, fail-open guarded,
no baseline growth, never persisted, ruff/format/mypy/C901 clean. Deviations 1-4 accepted.

## Blocker

1. `src/specify_cli/review/lane_test_invocation.py:33` - `LANE_TEST_INVOCATION_HEADER` is in
   `__all__` but has no src caller outside its module. `tests/architectural/test_no_dead_symbols.py`
   flags it, and its intra-module rescue applies only to names NOT in `__all__`; WP04 will not
   import it (WP04 reuses only `lane_test_invocation_for`), so this red would outlive WP04.
   Fix: drop it from `__all__` (keep the constant; tests may still import it directly).
   Re-run `tests/architectural/test_no_dead_symbols.py` and confirm only the WP01/WP04-pending
   names remain (EvidenceTree, INTERPRETER_REDIRECT_KEYS, capture_evidence_tree, run_environment,
   lane_test_invocation_for).

## Non-blocking (take or leave)

2. `src/specify_cli/cli/commands/implement.py:505` - `_lane_test_invocation` runs after
   `commit_claim` without a guard; an unexpected error (e.g. a git/OS error in
   `tracked_paths` other than GitCommandError) would exit 1 after the claim is committed.
   Consider the same fail-open as the prompts (render an unverified probe / `null`-safe JSON).
3. `review/lane_test_invocation.py:46` - the FOREIGN advice says "outside this lane" also
   for a single_branch write checkout; "outside this workspace" (or lane/write checkout)
   would be accurate.
4. Cost note only: `agent action implement` on a fresh lane probes twice (banner inside
   `top_level_implement`, then the prompt). By design (A6/T9 re-derive per surface); ~0.1 s.
