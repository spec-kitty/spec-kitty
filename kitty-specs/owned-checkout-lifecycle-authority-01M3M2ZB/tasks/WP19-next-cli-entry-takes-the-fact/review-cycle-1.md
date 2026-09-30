---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T15:52:33Z'
reviewer_agent: claude
wp_id: WP19
---

# WP19 review, cycle 1: REJECT (changes requested)

Reviewer: reviewer-renata. Lane-r HEAD fab7d0ea0; WP commits 1469a36f1, bc701fe7b, fa3b70961, 3aa810c19, ce6242c7c, fd2e48863.

## Blocking

### [HIGH] tests/integration/test_owned_lifecycle_acceptance_next.py:365-378: the FR-022 twin is a strict xfail that hides a mission regression
The WP names this row as "green on the base (ratchet)", and spec FR-022 is a [ratchet]: coordination-topology owned `next` must pass unchanged. The xfail turns that guard into an accepted failure. This mission bans ratchets like that.

Evidence comes from a standalone probe that runs the real CLI as a subprocess against each `src/` tree: owned `agent mission create --topology lanes_with_coord --owned-checkout P ...`, then `next --owned-checkout P --mission <slug> --json` run from R.
- origin/main 5b3bd9cf7: exit 0, `kind: query` (a non-error decision). Green.
- The mission merge-base 9b524be7d: exit 0, `kind: query`. Green.
- ea6057b67: green.
- 988990eb9 `fix(next): T060-T063/T067 thread OwnedCheckout through runtime entry points` (WP11): exit 1, `error_code: MISSION_NOT_FOUND`. **First bad commit**, found by read-only bisection over `git rev-list --bisect`.
- fa3b70961 (the WP19 base) and fd2e48863 (the WP19 fix): exit 1, `MISSION_NOT_FOUND`.

Required fix:
- Make the create -> `next` flow return a non-error decision again for a fresh owned `lanes_with_coord` mission.
- Remove the `xfail` on `test_next_after_create_is_a_non_error_decision`, so it is a real green ratchet.
- The defect sits in WP11's runtime owned arm, where the owned query/advance resolves through the coordination surface. That surface is unmaterialized, or has no `tasks/`, for a just-created mission. On main, the owned read came from P. Those files belong to WP11, so the orchestrator must either route the runtime fix back to WP11 or explicitly authorize a declared out-of-map edit here. Do not work around it in `next_cmd`.

### [MEDIUM] src/specify_cli/cli/commands/next_cmd.py:96-118 (`_discover_owned_handle`): handle-less `next --owned-checkout P` validates ownership twice
FR-003 and NFR-002 require exactly 1 validation per owned invocation; "0 or >=2 fails". The handle-less path does two:
1. `resolve_owned_create_root` -> `_require_owned_claim` -> `resolve_ownership_claim`.
2. `resolve_owned_or_adopt` -> `resolve_owned_mission` -> `_require_owned_claim` -> `resolve_ownership_claim` again.

`_discover_owned_handle` also re-derives R (`get_main_repo_root`) and re-composes the relative checkout path (`cwd / owned_checkout`). Both duplicate `resolve_owned_or_adopt` and create a second path composer. `TestHandlelessOwnedNext` never asserts the count, so the violation is unpinned.

Required fix (single validation):
- Move sole-mission discovery INTO the sole minter, after its claim check. For example, `resolve_owned_mission(..., handle=None, discover_sole=True)`, or a named `resolve_owned_mission_discovering_sole(...)` in `core/owned_mission.py`. It runs `_require_owned_claim` once and then calls `sole_mission_for_selection(claim.claimed_checkout)`. It raises a typed discovery error for 0 or >1 missions, which `next_cmd` renders through the existing `_emit_missing_handle_discovery`. `resolve_owned_or_adopt` forwards it.
- Delete `_discover_owned_handle`.
- Add `assert len(validation_count) == 1` to the handle-less rows. Commit that red-first, before the fix.
- Editing `owned_mission.py` or `_owned_checkout.py` is a declared out-of-map edit, and must stay minimal.

### [MEDIUM] Red-first order: the `TestHandlelessOwnedNext` rows (test_owned_lifecycle_acceptance_next.py:381-419) arrived in the fix commit fd2e48863, not in 3aa810c19
Those rows cover new behaviour (T103 step 3). Commit them, with the count assertion above, in a red-first test commit ahead of the fix.

## Non-blocking (LOW)
- src/specify_cli/cli/commands/agent/mission_create.py:507 and tests/agent/test_agent_feature.py:698 name the deleted `next_cmd._emit_checkout_ownership_error` in comments. Re-point them to `_owned_checkout.emit_owned_refusal`.
- next_cmd.py:1280 `_print_stalled_wp_interventions(mission_slug, repo_root)`: on an owned human-mode advance, `show_kanban_status` reads the ambient board, not the fact. This predates WP19 and is observability-only. Either thread `owned` or leave a tracked note.
- tests/specify_cli/cli/commands/test_next_answer_effective_root.py:129 patches `specify_cli.core.paths.get_main_repo_root`. `next_cmd` binds that name at import, so this poison does not reach `next_cmd.get_main_repo_root`. Patch `next_cmd.get_main_repo_root` as test_next_owned_fact.py does.
- The fd2e48863 body's out-of-map list omits `test_next_owned_commit_guard.py` and the new `test_next_owned_fact.py`. Both appear only under "Tests:". List them explicitly.

## Verified OK
- The carried commits are verbatim cherry-picks. Samuel Goff's authorship and dates are preserved, with `-x` trailers.
- The T101 adaptation mints facts through the real validator. The review-prompt test is `xfail(strict=True)` and owned by WP12 T069.
- The US3-AS1 full row is `xfail(strict=True)` and owned by WP12 T068. WP12 task lines 147-148, 264 and 290 own removing both markers.
- Red-first: 3aa810c19 has 10 failed, 19 passed and 2 xfailed on its own tree. This matches the claim (O9, O8, FR-007 x2, FR-003 x2, AS6, FR-021 flagless x3).
- C2: the flagless-adoption rows are red at 3aa810c19, which comes before the `_require_main_repo_unless_owned` rework in fd2e48863.
- U3: the AS6 hook asserts that the flip fired and that the branch changed. A mutation test proves the contract fails on re-derivation.
- I5: the snapshot baseline is taken after the flip, plus a pristine start/end snapshot that includes HEAD. This is a declared deviation that is at least as strong.
- DoD greps: `effective_root`, the claim primitives, and `_emit_checkout_ownership_error` are all absent from next_cmd. `TRANSITIONAL(WP18)` = 0; `bridging: WP19` = 0.
- Owned arms read the fact. Five mutations were all killed: `--answer` via placement_seam, commit target = main, commit roots = R, decide_next dropping `owned`, slug via the resolver.
- ruff check, ruff format, and C901 at 15 are clean. mypy `--strict --explicit-package-bases` over 7 files (callers and callees) gives 20 errors on base and 20 on head, identical. All 20 are pre-existing, in runtime_bridge_engine.py and _internal_runtime/engine.py.
- The lazy-import allowance is legitimate: at module scope `_owned_checkout` imports only json, typer, rich, mission_runtime and cli.json_contract, which the `next` path already loads.
