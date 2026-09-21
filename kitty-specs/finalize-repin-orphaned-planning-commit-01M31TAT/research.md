# Research: Finalize re-pins an orphaned planning_commit_sha (#4827)

Phase 0 consolidation. Grounding by two profile-loaded lenses (alignment + scope) and stress-tested by two post-spec adversarial lenses (invariant + regression). No new third-party dependency is introduced, so the supply-chain planning gate is N/A (documented, not silently skipped).

## Decision D1 — Orphan discriminator keys off the target-branch tip, not the lane HEAD

- **Decision**: classify the recorded `planning_commit_sha` against the **planning target-branch tip** using two git predicates: `git merge-base --is-ancestor <recorded> <tip>` (reachability) and `git cat-file -e <recorded>^{commit}` (object presence). Four classes: captured / current-advanced / orphaned (present, unreachable) / foreign (absent).
- **Rationale**: the regression lens proved that the allocator's *existing* no-op gate `is-ancestor <pin> <lane HEAD>` (worktree_allocator.py:612-621) is a **different question** — it short-circuits when the pin is reachable from the lane HEAD, and the merge (hence any conflict) only runs when it is NOT, which is the *normal healthy* state of a fresh coord lane (#2993). Keying orphan detection off lane-HEAD reachability would misfire on every healthy allocation. The rebase orphans the pin relative to the *target branch*, so the target tip is the correct discriminator, and it matches finalize's own classification.
- **Alternatives considered**: lane-HEAD reachability (rejected — see above); object-presence alone (rejected — cannot separate advanced from orphaned).

## Decision D2 — Re-pin target is the target-branch tip; do NOT content-match (C-004)

- **Decision**: re-pin to `_capture_target_branch_tip(target_branch)`, the same value the fresh-capture (`tasks_finalize.py:371`) and `doctor mission-state --fix` (`migration/mission_state.py:1586`) writers already use.
- **Rationale (adversarially confirmed by the invariant lens)**: on coord/lanes topology, WP-implementation commits are confined to lane branches (`execution-lanes.md` rule 5: merge flows `lane → mission → target`; `branch-target-routing.md`: code → lane branch, planning/`lanes.json`/`meta.json` → target branch). So re-pin-to-tip **cannot** drag sibling-lane WP work into a lane's merge base — the over-merge the scope lens feared does not materialize. Moreover the rebase already re-parents the planning commit onto the advanced base, so a content-matched pin would descend from the *same* base (content-match does not avoid base drift) and would only make the re-pin path **diverge** from the other three writers, violating C-002. Content-matched (patch-id) precision is deferred to the durable-artifact-SHA work (context #2897).
- **Alternatives considered**: content/patch-id match (rejected — no benefit here, diverges writers, must handle squash/fixup/drop); blind `HEAD` of the current checkout (rejected — must be the *target branch* tip specifically).
- **Disposition**: `accepted`.

## Decision D3 — Explicit `--allow-orphaned` gate; default fails closed only on a PROVEN orphan

- **Decision**: default (no-flag) finalize fails closed on a **proven orphaned** pin (present + unreachable + tip capturable) with an orphan-specific diagnostic naming `--refresh-planning-commit --allow-orphaned`. The re-pin itself requires the explicit `--allow-orphaned` operator assertion. Bare `--refresh-planning-commit` keeps #4141 advance-only refusal (message retains the substring "not an ancestor"). Foreign objects are refused even with `--allow-orphaned`.
- **Rationale**: a present-but-unreachable pin is topologically indistinguishable from a benign rebase orphan vs a genuinely divergent side-branch pin (the #4141 `test_refresh_refused_when_recorded_sha_not_ancestor` fixture is exactly this shape). The tool must not auto-guess; the operator asserts "I rebased; re-point to the live tip." The `--allow-orphaned` **default False** is what keeps the #4141 refusal test green unmodified.
- **Alternatives considered**: default auto-repair on orphan (rejected — cannot distinguish benign rebase from divergence without operator intent); extend bare `--refresh-planning-commit` to accept orphans (rejected — breaks the #4141 refusal contract/test).
- **Disposition**: `accepted`.

## Decision D4 — Default path DEGRADES to preserve on non-git / uncapturable-tip / foreign

- **Decision**: the no-flag default fails closed **only** for a proven orphan against a capturable tip. When the tip is uncapturable, the workspace is not a git repo, or the object is absent (foreign), the default degrades to the historical #3311 preserve.
- **Rationale (regression lens HIGH-2)**: `test_issue_3311_finalize_rewrites_active_lanes.py` seeds a synthetic SHA (`deadbeef…`, absent) in a **non-git** tmp workspace and asserts preserve on a plain run. A blanket fail-closed would flip that test → NFR-001 regression. `_capture_target_branch_tip` already returns `None` gracefully (never raises) — the degrade path reuses that.
- **Disposition**: `accepted`.

## Decision D5 — Centralize detection in the shared helper; reconcile all consumers (Finding 2)

- **Decision**: orphan detection lives in the single shared `_merge_recorded_planning_commit` helper (covering `worktree_allocator.py` :419/:482/:562 and `implement_support.py:352`). `check_claim_ancestry` (`implement_support.py:497`) and `_mt_resolve_owned_review_base` (`tasks_move_task.py:697`) are reconciled with the same classification so an orphan never surfaces as three different unreconciled diagnostics. The helper gains a target-branch ref argument (C-006) to run the classification.
- **Rationale (invariant lens Finding 2)**: `_mt_resolve_owned_review_base` reads the pin via `rev-parse --verify <sha>^{commit}`, which SUCCEEDS on an orphan (object present) → the owned-review diff is silently computed against a **dead base** — a correctness bug, not just a UX gap. `check_claim_ancestry` refuses the claim without naming the recovery. Both must recognize the orphan.
- **Disposition**: `accepted`.

## Decision D6 — NFR-003 admits an already-allocated-lane catch-up merge (Finding 1)

- **Decision**: idempotence is asserted for **finalize re-reads** and **not-yet-allocated** lanes only. An **already-allocated** lane (worktree merged the OLD pin) will, on its next `implement`, perform a legitimate **catch-up merge** of the re-pinned live planning state; a conflict there is a *genuine* content conflict (live base), the operator's to resolve — distinct from the pre-re-pin stale-pin dead-end.
- **Rationale (invariant lens Finding 1)**: the re-pin heals the finalize field and fresh allocation, but a lane materialized before the rebase merged the old pin; after re-pin the new pin is reachable (not orphaned), so the allocator's lane-HEAD merge runs a real 3-way merge to bring the lane up to the live planning state. This is correct-by-design catch-up, but it is a mutation — NFR-003's original "no further mutation" was false and is corrected. The stale-pin error only fires while the pin is *orphaned*; once re-pinned, genuine conflicts stay genuine.
- **Disposition**: `accepted` (scoped + documented; not folding a separate reuse-path repair — the catch-up merge is the correct behavior).

## Decision D7 — FR-010 folds the #4178 preserve-WARN false-positive + print-before-write

- **Decision**: correct the preserve-path drift WARN so it (a) does not point an orphan at the bare `--refresh-planning-commit` that then refuses, (b) does not fire on the tool's own finalize bookkeeping commit, and (c) prints the decision AFTER the `lanes.json` write.
- **Rationale (regression lens CONFIRMED-6)**: verified the ordering — `_compute_and_write_lanes` captures the recorded SHA before `_commit_finalize_artifacts` advances the tip, so `branch_tip (T+1) != sha (T)` fires the WARN on every execution-begun no-flag run even absent an operator amendment (the existing test masks it by mocking `commit_for_mission`). Same lines FR-009's report touches → fold together.
- **Disposition**: `accepted` (opportunistic, same code region; #4178 stays open for its docs-whitespace bullet).

## Confirmed safe (captured so a later reviewer does not re-litigate)

- **FR-009/ADR-2026-07-29-1 provenance**: the orphan re-pin is a *fresh, equally-frozen snapshot* into the same `lanes.json` write — the ADR's own "Negative/accepted trade-offs" already sanctions a re-finalize recording a new value. No second commit, no allocate-time live read. NFR-004 holds: only the *added* planning ancestor changes; lane parents (coordination/mission branch) are untouched.
- **`target_branch` identity note**: the scenario type-checks when `target_branch` is the branch that was rebased (where planning commits live); `merge_target_branch` is the separate real landing. A third party advancing a shared `target_branch` between rebase and re-pin is bounded identically to what fresh-capture/doctor-fix already accept — not flip-forcing.

## Not folded (noted for the PR body, per C-005)

- #2273 (first-class "rebase mission onto moved base"), #3936 (guided dependency-lane conflict resolution), #2897 (doctrine: no bare SHAs in durable artifacts). Fixing #4827 shrinks #3936's false-conflict surface as a side effect; not a folded deliverable.
