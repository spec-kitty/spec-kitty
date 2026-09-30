# Pre-spec options memo: owned-checkout-lifecycle-authority

- **Base:** origin/main af847be7, 2026-09-28
- **Issues:** #3449, #5026, #4252, #5277. Candidate fold: #4867.
- **Squad:** architect-alphonso (architecture), debugger-debbie (live CLI repros), python-pedro (call-site census), planner-priti (foldables and cherry-pick map). All profile-loaded and read-only.

## Convergent findings
All four lenses agree on these points.

1. **Seven defects reproduce on main through the real CLI.**
   - **#3449, `agent tasks status`:** `MISSION_NOT_FOUND` for every handle form.
   - **#3449/#4252, `setup-plan`:** `PLAN_CONTEXT_UNRESOLVED`.
   - **#5026, `context resolve`:** `WORK_PACKAGE_UNRESOLVED`.
   - **`next --owned-checkout`, tasks→implement:** uncaught `ValueError` traceback; the run state is left wedged at implement.
   - **Stale primary copy:** `context resolve` exits 0 but returns the primary WP file and a nonexistent lane worktree. This is the **fail-open split-brain** case.
   - **`finalize-tasks` in an owned checkout under `.worktrees/`:** refused, but only after a **partial uncommitted write** (a status event plus a rewritten WP file).
   - **Create:** reads charter activation from primary.

   Already working on main: `next` handle resolution and owned finalize outside `.worktrees/`.

2. **Root cause: the placement seam has no owned-checkout arm.** `placement_seam(repo_root)` and `get_main_repo_root` fold every read back to primary (`workspace/context.py:557,642,734`). `next_cmd.py:176` already sets `repo_root = owned`, and the reads still land in primary. So #5009's approach of threading `effective_root` through callers cannot close the class.

3. **There are three ownership authorities today:**
   - `resolve_owned_mission`, the canonical one;
   - `next`, which validates only `resolve_ownership_claim` and skips the topology and branch checks;
   - `missions/operation_context.py`, which adopts the current directory implicitly and so violates ADR 2026-08-12-1.

   There are also two call shapes: `repo_root = effective_root = owned` in `next`, and `repo_root = primary, effective_root = owned` in `move-task` and the status transaction.

4. **Status source.** A `.worktrees` path-shape predicate overrides the stored topology (`status_service.py:59-75,163`). #5009 answers this with a parallel `OWNED_CHECKOUT` read source, which is a second authority. The fix belongs in `surface_resolver.py` (#4959).

5. **Coverage gaps in #5009.** It misses roughly 6 of 13 seams:
   - the #4980 task-board authority;
   - the CLI flags for `tasks status`, `setup-plan` and `context resolve`;
   - the cwd-adopting operation context;
   - review-base selection (`workflow_executor.py:2236`, which matches commit subjects and silently falls back to an unscoped diff);
   - making `finalize-tasks` atomic;
   - converting the `ValueError` into a blocked decision.

## Options (architect-alphonso)

| | A: thread `effective_root` (#5009) | **B: validate once into a typed carrier (recommended)** | C: ownership-aware resolvers |
|---|---|---|---|
| Mechanism | A bare `Path` passed as a kwarg to every reader | A frozen `OwnedCheckout` carrying `primary` and `root`, defined in `mission_runtime` with no `specify_cli` imports and minted **only** by `resolve_owned_mission`. `PlacementSeam`, `resolve_workspace_for_wp`, `mission_context_for`, `DecideNextContext`, `TransitionRequest` and `surface_resolver` take the carrier. | Resolvers discover ownership themselves |
| Single authority | No: every reader must opt in | Yes: one minter, plus an architectural test pinning it and forbidding new `effective_root: Path` parameters | Yes, but discovery is ambient |
| Layer ledgers | Unchanged | Unchanged: `specify_cli` imports downward into `mission_runtime`, and `runtime`→`mission_runtime` is already allowed | Grows or risks growing |
| Primary-only charter authoring | Kept | Kept: authoring is pinned to `carrier.primary` | At risk |
| Reuse of #5009 | ~100% | ~60%: all test commits, cache keying, and the decision and prompt wiring | ~20% |
| ADR | None | Amend 2026-09-03-1, which accepted kwarg threading. Small note on 2026-06-07-1 for the new public `mission_runtime` symbol. | Violates 2026-08-12-1, which disqualifies it |

Under B:
- Owned workspace resolution returns a distinct `resolution_kind="owned_checkout"` with `lane_id=None`. A lane id then always means a lane worktree.
- `enforce_checkout_identity` gates on the carrier.
- `next` is routed through `resolve_owned_mission`.
- `operation_context`'s cwd adoption is replaced by an explicit `--owned-checkout` flag.

## Decisions for the operator
1. **Architecture:** A, B or C. Recommended: B, with an amendment to ADR 2026-09-03-1.
2. **Charter and template read root at create.** `next` already reads from the owned checkout; create reads from primary.
   - Recommended: read from the owned checkout, so create matches `next`.
   - Authoring stays primary-only (#4785).
3. **Scope of CLI entry points.**
   - Recommended: add `--owned-checkout` to `agent tasks status`, `agent mission setup-plan` and `agent context resolve`.
   - `implement` and `agent action review` refuse owned single_branch missions with a typed error; supporting them is #5100 territory.
4. **Fold #4867.** Recommended: yes. It is the same `runtime_bridge` owned-coord code path, so fold it in as a regression case.
5. **Handling #5009.**
   - **Carry** the 7 test commits with `cherry-pick -x`, keeping Samuel Goff as author, then adapt them.
   - **Drop** the 4 session-log doc commits and 1 formatting-descendant commit.
   - **Re-express** the 3 fix commits: e6923bc97, b1a1693bf, and 77aa62913 (the status authority). Credit Samuel Goff with `Co-authored-by`.
   - Once the mission PR is open, close #5009 with a pointer to it. The operator makes that call.

## Proposed WP skeleton (pedro, adjusted to B)
- **WP01 — Carrier and placement-seam owned arm.** `OwnedCheckout` value object, the seam's owned arm, the owned arm and cache key in `resolve_workspace_for_wp`, and the single-minter architectural test. Also retires `effective_root_kwargs`.
- **WP02 — Status surface arm** in `surface_resolver`, plus making `finalize-tasks` atomic. Depends on WP01.
- **WP03 — `mission_runtime` WP-bearing fields** (#5026): a typed unresolved result and no split-brain with a stale primary copy. Depends on WP01.
- **WP04 — Runtime `next`:** the context, decision, prompt builder, composition dispatch and #4980 board authority. The `ValueError` becomes a blocked decision. Folds #4867. Depends on WP01–03.
- **WP05 — CLI entry points:** `next` validation, `tasks status`, `setup-plan`, `context resolve`, and typed refusals for `implement` and `action review`. Retires `operation_context` cwd adoption. Depends on WP01–04.
- **WP06 — Owned review base:** deterministic claim commit and fail-closed. Depends on WP01.
- **WP07 — Create-time charter and template read root,** per decision 2.
- **ADR amendment** lands with the spec.

## Acceptance scenarios (debbie; all RED on main today)
- **Fixture:** a primary made with `spec-kitty init`, a linked owned worktree, and a byte snapshot of primary. Handles are parametrised over slug, mid8 and ULID.
- **AS-1 (#3449):** `agent tasks status` succeeds and primary is unchanged.
- **AS-2 (#4252):** `setup-plan` succeeds after owned create and spec commit, and primary is unchanged.
- **AS-3 (#5026):** `context resolve` for implement returns the WP file and workspace under the owned root, with no lane resolution kind.
- **AS-4:** AS-3 with a stale primary copy never points into primary; the same holds for `next`.
- **AS-5:** `next` crosses tasks→implement as a JSON step or blocked decision, never a traceback.
- **AS-6:** `finalize-tasks` under `.worktrees/` succeeds, and any refusal leaves `git status` clean.
- **AS-7:** the create-time activation read root is deterministic, per decision 2.
- **Guard:** coord and lanes_with_coord `.worktrees` protections stay green.

## Operator decisions (2026-09-28), locked
1. **Architecture:** B, the typed `OwnedCheckout` carrier minted only by `resolve_owned_mission`. Amend ADR 2026-09-03-1 alongside the spec.
2. **Charter and template read root at create:** the owned checkout. Authoring stays primary-only (#4785).
3. **Scope, all four added:**
   - fold #4867;
   - `--owned-checkout` on `agent tasks status`, `setup-plan` and `context resolve`, and retire the cwd adoption in `operation_context`;
   - typed refusals for `implement` and `action review`;
   - atomic `finalize-tasks`.
4. **#5009:** carry the tests with `-x` under Samuel Goff's authorship, re-express the fixes with a `Co-authored-by` credit, drop the session-log and formatting commits, and close #5009 with a pointer once the mission PR exists.
