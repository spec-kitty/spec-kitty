---
type: reference
updated: 2026-11-12
---

# Foldable issues for sub-epic #7546

Search: `gh api -X GET search/issues -f q='repo:spec-kitty/spec-kitty is:issue is:open …'` over
WRONG_SURFACE, placement, settlement, topology_settled, spec-commit, safe-commit, protected target,
coordination worktree, remedy, baseline-tests, lanes_with_coord (2026-11-12).

| # | Title (short) | Class | Reason |
|---|---|---|---|
| 7551 | spec-commit / safe-commit WRONG_SURFACE after settlement | CORE | Reproduced live |
| 7601 | protected-target lanes_with_coord cannot implement from root | CORE | Reproduced live |
| 7602 | accept path-convention message names `.worktrees/<slug>-coord/…` | CORE | Confirmed by reading |
| 7595 | implement / move-task banner shows `main` for a settled Mission | **FOLD** (operator ruling, relayed 2026-11-12) | Same root: target helpers bypass the seam reader |
| 7594 | setup-plan vs check-prerequisites checkout verdict | EXCLUDE here (operator ruling: later slice) | Phase-aware expected-checkout contract, partly pre-settlement |
| 5406 | `--abort` remedy assumes single_branch | REFS | Closed by #7567 |
| 7550 | accept stages a coord path from root | REFS | Closed by #7567 |
| 7540 | lanes_with_coord closeout umbrella | REFS | Item 6 = #7551; can close once it lands |
| 5501 | spec-commit drops decision/trace/status args | REFS | Closed; re-checked, not regressed |
| 5515 | tracer-append safe_commit "failed to stage" in coord worktree | REFS | tracer-append works after settlement in the probes; needs its own repro |
| 5543 | review artifacts leave PRIMARY duplicates | REFS | Duplicate writer, not placement |
| 7331 | claim leaves meta.json staged in root | REFS | Sub-epic B (#7545) |
| 5319 | remedy recommends SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS | REFS | Different remedy family |
| 5264 | recovery hints point at the wrong command | REFS | Not settlement-tied |
| 6152 | route command-entry repo_root/branch consumers through the declaration-first entry | REFS | Broader strangler |
| 7599 | accept "Next steps" text for a coord Mission | REFS | Owned by sub-epic A2 (#7598) |
| 1878, 1619 | placement/identity strangler; unified execution context | REFS | Parent epics, not re-parented |
| 7545 | sub-epic B: CLI commits its own writes | REFS | Neighbour |
| 5602 | coord-routing tests in test_protection_config_honoring.py red locally | REFS | Watch when touching protection checks |
| 5936, 5764, 7297, 2802, 7589, 5905, 5644, 4169, 5783 | (various) | EXCLUDE | Different causes / other epics |

## In-scope findings with no issue yet (same class, found by the squad)

- `move-task --note` on a protected root refuses `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH`
  for a settled Mission (same mechanism as #7601) → proposed in #7601's slice.
- `baseline-tests.json` silently left uncommitted after settlement (no warning) → #7551 sentence 2.
- Coordination status lock (#5353 L1) skipped for settled default Missions → proposed fold.
- `SafeCommitHeadMismatch` remedy names an impossible checkout → #7546 "every remedy string".

## Overlap with open work

- PR #7596 (`feat/7578-review-context`, draft) renames `resolution.py::_default_mission_primary_ref`
  (adjacent to `_declared_primary_write_dir`). Low textual conflict risk; coordinate on rebase.
- PR #7591: no overlap with the files above.
- Sub-epic A2 (#7598): no open PR or branch found; this Mission does not touch consolidation recovery.
