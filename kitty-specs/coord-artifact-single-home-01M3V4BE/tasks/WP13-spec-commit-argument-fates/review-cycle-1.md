---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T18:55:06Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-k tip `a7e83a55c3`, base `e7b085d26c` (WP05).

## What already passes

- **Tidy-first `771977e90f`:** a pure move. The existing spec-commit and 2739 guard tests pass at that commit (12/12). `spec_commit_command` is now C901 7.
- **R5 red-first:** red at `bba6938f09` with 10 failures, including `KeyError: 'surfaces'` and both R5 CLI tests. Green at the tip.
- **Lane hygiene:** the lane is clean. `git status` is empty, and the diff against `e7b085d26c` touches only the two owned files.
- **Coverage and static checks:** diff coverage is 100% (107/107 changed statements). ruff, format, C901, RUF100 and mypy --strict are clean. The `ff-advance` wording is gone from the help text.
- **`arguments` key:** it is defined by `contracts/commit-outcome.md` (L56-73), so it is not a second outcome shape. Surfaces are serialized only through `commit_outcome_payload`.
- **Lock test (T073):**
  - The reason mapping is pinned: mutating the router's lock reason from `STATUS_LOCK_HELD` to `error` fails it.
  - The surface status is pinned: mutating the error surface status to `unchanged` fails it.
  - Accepting `{"refused","error"}` is not a vacuity hole, because both are legitimate refusal statuses and the named reason is asserted.
- **Fate matching:** removing the suffix match fails 4 tests, and bypassing `render_commit_outcome` fails 2. The suffix match uses a `/` boundary with exact-match-first, so misattribution needs the same Mission-relative path under two prefixes. That is low risk; accepted (see N3 for the root cause).

## Blocking

**B1: the FR-007a success override is untested; a mutation survives.**
- `_compute_success`'s `and not surface_failed` is the core of FR-007a. It is the only thing that turns `success` false when the legacy status is `committed`/`unchanged` but another surface was refused.
- Realistic case: a mixed batch whose coordination group is `no_op_wrong_surface` (refused `WRONG_SURFACE`). The PRIMARY-partition caller group committed, so `_merge_group_results` returns `committed` legacy fields. That is the #5513 masking shape.
- I mutated `return base_success and not surface_failed` to `return base_success`. All 26 tests in `test_spec_commit_cmd.py` still pass.
- **Required:**
  - A unit test on `_render_spec_commit_result` with a hand-built `CommitRouterResult(status="committed", surfaces=(primary committed, coordination refused WRONG_SURFACE))`. Assert `success: false` and `typer.Exit(1)` in both JSON and text mode.
  - Preferably also a real-router variant.

**B2: text mode still masks the other surface on the error and wrong-surface arms.**
- In text mode, `_render_spec_commit_result` calls `render_commit_outcome` only for the `committed`/`unchanged` legacy statuses.
- On the T073 mixed batch (lock held), the legacy status is `error`. The text output is only `Error: <lock diagnostic>`, so the operator never learns that `spec.md` WAS committed on the target branch. That is the FR-007 masking, now in text instead of JSON.
- **Required:**
  - Whenever `result.surfaces` is populated, print the `render_commit_outcome(result)` lines and the non-committed argument lines on EVERY arm. Keep the existing actionable `Error:` line after them.
  - Add a text-mode variant of `test_spec_commit_reports_refused_coordination_surface` asserting a `primary (...)` committed line, a `coordination (...)` refused/error line naming `STATUS_LOCK_HELD`, and exit code 1.

**B3: an argument reported `refused` can coexist with `success: true` and exit 0.**
- Every input matching no surface entry gets fate `refused` / `PATH_UNROUTABLE`, but `success` and the exit code look only at surfaces.
- Realistic cases:
  - a foreign-worktree path dropped by staging (`DROP_FOREIGN_WORKTREE`);
  - a legacy Mission whose coordination dir name differs from the root dir name, so the suffix match also misses.
- Spec-commit would print "refused" for an argument and still exit 0. FR-007a forbids exactly that: "never reports success while ignoring one".
- **Required:** `success` is false (exit 1) when any argument's fate is `refused`. At minimum this applies to the `PATH_UNROUTABLE` fallback, which T070 itself calls a contract violation. Extend `test_input_absent_from_every_surface_is_path_unroutable` (or add a render-level test) to assert `success: false` and exit 1.

## Non-blocking

- **N1 (rich markup):** `console.print(line)` and `_print_argument_fate_lines` pass branch names, paths and router diagnostics through rich markup. A `[`…`]` in any of them is swallowed or mis-styled. Use `console.print(line, markup=False)` or `rich.markup.escape`. Glyphs: the previous code already printed `✓` through rich, so encoding behaviour is unchanged.
- **N2 (control test):** the real router produces `no_op_no_changes` deterministically for this fixture. WP05's translation stages the coordination path and the commit is a zero diff; I probed the payload. Pin `REASON_NO_CHANGES` instead of accepting a set, so a regression in which no-op flavour is reported is caught.
- **N3 (WP05 contract gap behind the suffix heuristic):**
  - The `_index_surface_fates` docstring says skipped/refused entries "already carry the caller's OWN path". That is false: `no_op_no_changes` skips carry the worktree-nested path (`.worktrees/<coord>/kitty-specs/...`), as the probe shows.
  - The suffix match exists only because the router never fills `PathFate.owning_path` (contract rule 2), nor maps committed paths back to caller paths.
  - Fix the docstring. Ask the coordinator to file a WP05 follow-up: the router should record the caller path plus `owning_path` for every translated or IN_PLACE path, so consumers can drop the heuristic.
- **N4 (process):** T002 asked for the helper tests in the tidy-first commit, pinning pre-extraction payloads and exit codes. They landed in the red commit instead, against the WP13 signature, so the tidy commit was verified only by the pre-existing tests (which do pass). Note it in the activity log.

## Tests run by the reviewer (`-n 3 --dist loadfile`)

| Suite | Result |
|---|---|
| test_spec_commit_cmd + 2739 guard + commit_router_partition(+_authority) + commit_router_fail_loud + test_commit_outcome | 71 passed |
| All 8 `grep -rl spec_commit tests/integration` files (accept_matrix_coord_partition, **explicit_checkout_commands**, is_committed_contract, owned_checkout_mark_status, **owned_lifecycle_acceptance_e2e**, placement_partition_golden_path, protected_primary_spec_commit, specify_plan_commit_boundary) | 187 passed, 0 failed |
| Gates: no_dead_symbols, dead_symbol_allowlist_contract, layer_rules, no_legacy_terminology | 208 passed, 2 failed (only `COORD_SEED_TRAILER`, the WP06 transitional red) |

Spot-mutations (all reverted; worktree clean):

| Mutation | Result |
|---|---|
| Lock reason → `error` | caught |
| Error surface status → `unchanged` | caught |
| `_compute_success` ignores surfaces | **survives (B1)** |
| Suffix match removed | caught (4 failures) |
| Renderer bypassed | caught (2 failures) |
