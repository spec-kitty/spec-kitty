---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T03:23:03Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-o tip `5229d9c01c`, base = WP07 tip `7afabf4eff`.

## What already passes

- **#5519 red-first (R4).** `d80ee7cf59` is red: 2 failed at that commit. It is green at the tip.
- **WP07 follow-up gate.** `seed_committed_this_txn` now gates on `location.seed.coord_commit is not None`. Mutation checks (scratch worktree, reverted):
  - the old `Establishment in (SEEDED, RESTORED_FROM_BRANCH)` gate fails 2 tests;
  - the "SEEDED only" gate fails 2 tests.

  Both mutants die.
- **`decisions/service.py` writers.** They go through `write_dir(STATUS_STATE)` (`_write_mission_dir` / `_write_events_path`). Reads stay on `read_dir`, so the idempotency probe never seeds. The direct `materialize_coord_surface_for_write` calls are gone.
- **Mutation: `service.py` back to `read_dir`.** This fails 4 T052/R4 tests, so it is pinned.
- **`DecisionGitLog`.** `mission_dir=` is now a required kwarg, and the legacy composer inside the class is deleted.
- **Non-owned bridge arm.** It goes through `write_dir(DECISION_LOG)`. A failure on that arm raises `DecisionGitLogUnavailable` (fail-closed); the bridge never writes to the root checkout.
- **Decision CLI.** `open`, `resolve`, `defer` and `cancel` render `COORD_SEED_FORK_REFUSED` / `STATUS_LOCK_HELD` with hints, and tests cover all four verbs.
- **Ledger placement.** The ledger stays PRIMARY (DM-*.md, `index.json`), per WP12.
- **T052 sentinel deviation.** Accepted. A plain-git intervening commit reproduces the R4 shape, which is red at `d80ee7cf59`. `tracer-append` is blocked on lane-o by a `tracer_writer` defect that WP10 rewrites; WP10 must re-verify R4 with a real `tracer-append`.
- **Gates.** Every widened named gate is green, including `test_cold_import_status_boundary.py` (3 passed). The only exception is the `COORD_SEED_TRAILER` pair (transitional; WP06 cures it in lane-d).
- **Static checks.** ruff check, C901 and `ruff format --check --force-exclude` are clean. No excluded file was reformatted, and no new `noqa`. mypy --strict errors in the touched files are identical to base: one each in `coord_seed.py`, `transaction.py` and `service.py`, all inherited.

## Blocking

**B1 (regression from the out-of-map `a6b4165638`): a WP03 test is now red.**
- **Failing test:** `tests/coordination/test_coord_seed.py::test_owned_arm_translates_workspace_failure` fails with `DID NOT RAISE ActionContextError`.
- **Bisect:** green at `7afabf4eff` and at `2790253bb5`; red from `a6b4165638` on.
- **Cause:**
  - The owned-aware meta read loads `meta.json` from `owned.mission_dir` and falls back to `{}` when it is absent.
  - So an owned fact whose own PRIMARY dir has no `meta.json` (the test's shape) now reads no `coordination_branch`.
  - It silently degrades to the declared-PRIMARY location instead of materializing and translating the failure to `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
  - That is a fail-open the accessor's contract forbids.
- **Required:** make the owned read authoritative without silently degrading. Either:
  - fall back to the repository-root `meta.json` when the owned copy lacks `coordination_branch`; or
  - key coordination routing for an owned call on `owned.topology` (the fact's stored topology) and treat a coordination topology with no declared branch as a refusal, not a PRIMARY write.

  Then keep this test green, add the `a6b4165638` scenario (owned meta present and declaring the branch) as a positive test, and record the choice.

**B2: the `# pragma: no cover` additions on handler-raises `return`s.**
- `2790253bb5` adds 8 `# pragma: no cover` lines in `decision.py`.
- **Diff coverage:** 100% with them excluded, 88.6% if they count as uncovered statements.
- The charter forbids suppression to reach coverage (NFR-005, "no new suppressions"), and the structural fix is cheap:
  - annotate `_handle_coord_seed_fork_refused` and `_handle_status_lock_timeout` as `-> NoReturn` (they always raise `typer.Exit`);
  - delete the 8 dead `return`s.

  mypy then knows the arm terminates, and coverage has nothing to exclude.
- The `dispatch.py` precedent does not license new instances. The sibling `_handle_index_read_error` / `_handle_status_read_path_error` `# unreachable` returns can stay as they are (out of scope), or get the same treatment if trivial.

**B3: the dir-name agreement (P-M4) binding is not discharged.**
- The binding required one of two things, with the choice recorded:
  - **(a)** a pinned proof, over the reachable creation paths, that no coordination-routed Mission has differing `kitty-specs/<slug>/` vs `coord_mission_dir_name(slug, mid8)` shapes; or
  - **(b)** carry and fold a legacy `kitty-specs/<slug>/decisions.events.jsonl` stream once into the canonical dir, under the seed lock, reusing `event_prefix`.
- The agreement test covers canonical (mid8-embedding) slugs only, and the docstring defers the bare-slug case to "the final report".
- The differing shape is real:
  - `coord_mission_dir_name` deliberately preserves verbatim pre-083 `NNN-` slugs (`"060-test"` → `"060-test-01COORD0"`);
  - the deleted composer wrote `<worktree>/kitty-specs/060-test/decisions.events.jsonl`;
  - the new path is `…/060-test-01COORD0/decisions.events.jsonl`.

  Any such Mission with an existing stream now gets a second stream, and the old one is orphaned: a #5519-class fork.
- **Required:**
  - add the bare or legacy-slug variant of the agreement test, asserting the actual resulting paths;
  - choose (a) with proof, or (b);
  - if (b) is deferred, record it and have the coordinator assign it explicitly (WP17's fork detection is the natural owner).

**B4: the `decisions/emit.py` write-side change is not pinned (T052 step 5).**
- Reverting `emit._mission_dir` to `read_dir` leaves the WP09 tests (16/16) and the broader `tests/specify_cli/decisions/` + `tests/decisions/` + `tests/runtime/` (1312 passed) all GREEN.
- The reason: every production path into `emit` goes through `service.py`, which pre-resolves `write_dir` first, so emit's own `read_dir` already sees MATERIALIZED.
- **Required:** add one focused test that calls the `emit` writer directly on a pre-fix EMPTY Mission (no service pre-resolve) and asserts the row lands in the coordination log. Alternatively, if the change is pure belt-and-braces, say so and justify why it needs no test. The prompt asks for one per writer.

## Non-blocking

- **N1: owned `DecisionGitLog` arm reverted to the historical ladder** (`a58281214b`). Accepted as a recorded residual, part of WP06's owned-coordination INV-COORD-HOME follow-up. The O8 owned `lanes_with_coord` shape mints its coordination branch without recording it in `meta.json`, so `write_dir`'s owned arm cannot resolve it.
  - That arm re-composes `worktree_root / KITTY_SPECS_DIR / mission_slug`, which is a second composer.
  - Prefer `coord_mission_dir_name(mission_slug, mid8=_mid8)` there, so the owned stream cannot disagree with the transaction dir (B3's shape).
  - Record it in `design-decisions` and the follow-up.
- **N2:** the bridge folds a `CoordSeedForkRefused` raised by `write_dir(DECISION_LOG)` into `DecisionGitLogUnavailable`, losing the code. That is fail-closed, so acceptable. Consider chaining the typed code into the message for operators.

## Tests run by the reviewer (`-n 3 --dist loadfile`, tip `5229d9c01c`)

| Suite | Result |
|---|---|
| decisions (`specify_cli/decisions`, `decisions`), `tests/runtime/`, `tests/next/`, `tests/coordination/`, `tests/specify_cli/coordination/`, `tests/specify_cli/events/`, zeitgeist handler, regression 1615-1618, guard_capability_regression, coord_read_seam_callers, and the 6 `test_decision*`/charter-decision CLI files | 3112 passed, 12 skipped, **1 failed** (B1) |
| `tests/specify_cli/cli/commands/` (whole) | 5142 passed, 10 skipped, 2 xfailed, 3 failed: `test_doctrine_asset.py::test_asset_path_resolves_every_internal_pack_asset_to_its_blob[...]` ×3, **red at `7afabf4eff` too (base-red, not WP09)** |
| `tests/integration/test_owned_next_runtime.py` + 43 `grep -rlE "decision\|DecisionGitLog\|runtime_bridge" tests/integration` files | 456 passed, 7 failed: documentation and research runtime-walk tests (base-red, known) |

Gates (11, individually): all green except `test_no_dead_symbols` and `test_dead_symbol_allowlist_contract` on `COORD_SEED_TRAILER` only (transitional).

Diff coverage vs `7afabf4eff`: 100% (63/63) with the pragma lines excluded; **88.6%** if those 8 pragma'd lines count as statements (B2).
