# Tracer: Approach — charter-catalog-coherence (#4785)

How the mission is being executed; what worked, what was reworked.

## Planning

- Ran a 4-lens grounding squad (debugger root-cause + repro, architect right-design,
  paula-patterns surface/whack-a-field map, researcher supersession/related-tickets)
  before speccing, per operator steer. All 4 findings confirmed real on `main @ ba4e590142`.
- Reconciled scope into 4 work stories mapped 1:1 to the findings; brownfield cut: F4a's
  "minimal one-entry writer" rejected on single-authority grounds.
- Folded the CLI-charter-write half of duplicate #4250 into F3; cross-referenced the rest.

- Pre-implement brownfield scout caught 4 traps folded into the WP prompts before dispatch:
  (1) WP01 layer rule — compiler.py (charter) must NOT import `drg_urn_to_config_id` (specify_cli);
  use in-layer `resolve_config_id`/`normalize_directive_id`. (2) WP01 deleting the dead builder breaks
  `tests/charter/test_builtin_reader_relocation.py` (added to owned_files). (3) WP04 must NOT delete
  `_is_inside_git_worktree` (unowned importers + permissive semantics); add the WP02 guard alongside.
  (4) contract WP tags corrected.

## Implement

- Order: WP01 (compiler completeness) + WP02 (worktree helper) as independent foundations first
  (parallel sonnet implementers, red-first); then WP03 (activate/deactivate) + WP04 (synthesize),
  whose lanes auto-merged their dependency lanes. Each WP: red-first regression → fix → opus review.
- Rework during review: WP04 tripped the ruff-format-exclude ratchet (reformatted excluded files) →
  removed the 7 now-clean exclude entries; WP02's foundation-forward `_charter_write_root` needed a
  dead-module allowlist entry (added by WP02, removed by WP03/WP04 when they wired the caller —
  bidirectional ratchet).

## Review / Close

- Consolidated via `spec-kitty merge` (squash) after all 4 WPs approved. The integration suite on
  the merged tree caught 3 real cross-WP regressions (+ 1 stale format.exclude entry for WP01's
  deleted test file) — all fixed at root before the PR. Pre-PR opus diff-review found no additional
  cross-WP defects. Non-draft PR to upstream `main`; operator merges.
