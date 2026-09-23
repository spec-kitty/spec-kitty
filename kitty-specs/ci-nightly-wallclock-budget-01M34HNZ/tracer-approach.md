# Tracer: Approach

Mission: ci-nightly-wallclock-budget-01M34HNZ (issues #4865, #4864)

## Why these two issues are one mission

Both defects live on the nightly CI wall-clock surface and share a root
cause: a budget or shard count set without fixture-aware, per-suite
measurement. #4865's `performance-and-e2e` job blends three suites into one
60-minute budget and one verdict; #4864's `charter` shard_count was sized from
timings that measure only pytest's call phase, missing the fixture-setup cost
that actually dominates `charter`'s wall-clock. Fixing them together lets the
spec state the shared finding once — CI budgets in this repo have
historically been sized by copying an old number or eyeballing a wall-clock
total, not by deriving them from a measurement tool built for the job — rather
than repeating it across two mission specs.

## Chosen approach

**#4865 — split, don't raise the cap.** The operator explicitly rejected
raising `performance-and-e2e`'s single `timeout-minutes` (e.g. to 90-120) as a
half-fix: it would still blend perf/e2e/stress into one verdict, which is
the exact harm that made 2026-09-20's genuine e2e regression indistinguishable
from ordinary timeout cancellation. The spec instead calls for three
independent jobs, each with its own timeout re-partitioned from the 65-minute
observed combined total (not copied), plus updating `nightly-summary`'s
`needs:` list and preserving the existing exit-0/exit-5-pass, fail-loud
convention per job. The hard constraint carried through every FR/AC: no
`pull_request` trigger may appear anywhere in the split
(`test_performance_marker_guard.py` is the enforcement mechanism).

**#4864 — recapture with the purpose-built tool, then re-derive.** The
operator explicitly rejected the `349b73fc0` heuristic (bump shard_count by
wall-clock÷target, skip recapture) as a precedent, because it would leave the
registry's own "measured, never guessed" claim (NFR-005) false for `charter`
too — exactly as it remains false for `agent`/`upgrade` today, where that
heuristic was previously applied. Instead: run
`scripts/ci/capture_shard_timings.py --module charter --write` (fixture-aware,
purpose-built, docstring names `tests/upgrade` as the standing example of this
exact failure mode), then re-derive `shard_count` from the real data via the
existing LPT skew gate. The ~110 minutes of serial execution this costs is
accepted, explicitly sized into the plan as its own step rather than folded
into "edit a YAML number."

## Why the vacuous-gate framing matters

The key finding this mission is built around: `charter`'s current timings
produce near-uniform (~0.098s mean) per-test durations, which makes the LPT
bin-packing skew computation return ~0% skew for ANY shard_count from 1 to
4211. The ≤20% skew gate (NFR-005) is not merely "passing" for `charter` — it
is mathematically incapable of failing, so it cannot validate whatever
`shard_count` is written into the registry. This is a direct instance of
charter Standing Order #5 ("a gate-unmask cannot self-validate"): recapturing
with the fixture-aware tool is what restores the gate's ability to actually
check something for this module, not just a data-freshness nicety.

## Scope boundary held explicitly

14 of 21 registry modules are stale by the same measurement standard; only
`charter` is recaptured in this mission. The other 13 (`agent`, `cli`,
`core_misc`, `execution_context`, `glossary`, `kernel`, `lanes`, `missions`,
`next`, `post_merge`, `release`, `upgrade`) are named in the spec's
Clarifications section as explicitly out of scope, with no follow-up issue
filed (per the project's no-follow-up-issues standing rule) — the boundary is
recorded for the orchestrator to ledger at mission exit instead.

## Evidence Summary (WP07, T034-T036, 2026-09-22)

Every item below is sourced from a prior WP's own Activity Log / recorded commit — none is
re-derived or re-estimated by this WP. Where a number could be independently re-checked, WP07 did
so itself (CLAUDE.md's "every number must be one you verify yourself"); results are noted inline.

### WP01 — Phase 0 baseline + campsite-clean

- T001 baseline: `uv run --frozen pytest tests/architectural/test_module_shard_registry.py
  tests/architectural/test_performance_marker_guard.py -q` → `28 passed in 36.71s`, 0 failed. 100%
  pass → T002 (file a pre-existing-failure issue) correctly SKIPPED; no issue filed.
- Supplementary baseline: `make test-fast` → `1941 passed, 5 skipped, 5 warnings in 222.31s
  (0:03:42)`, exit 0.
- Campsite-clean commit landed twice under a tooling defect (see "Known tooling defects" below):
  first on the undeclared lane branch (`d1e7d5177`, stale, superseded), then re-applied directly
  on `issue-4865-ci-nightly-wallclock-budget` as `3fb1c8bb7` — the commit actually carried forward
  by every subsequent WP.

### Evidence of the pre-split harm (WP07, independently re-verified 2026-09-22)

`gh run view <id> --repo spec-kitty/spec-kitty --json jobs` against the three pre-split nightlies
named in the PR body:

- **`35683539593`** — `performance-and-e2e` `cancelled` at 65m01s. Step-level: `performance` suite
  step `success`, `e2e` (heavy/e2e-marked) suite step `success`, `stress`-marked suite step still
  `in_progress` (killed by cancellation), `Upload nightly performance/e2e reports` step `status:
  pending` — **never ran**.
- **`35557999753`** — `performance-and-e2e` `cancelled`. Step-level: `performance` `success`, `e2e`
  `success`, `stress` `failure`, `Upload nightly performance/e2e reports` `skipped` — **never ran**.
- **`35486813855`** — `performance-and-e2e` `failure`. Step-level: `performance` `success`, `e2e`
  `success`, `stress` `success`, `Upload nightly performance/e2e reports` `success` (artifact
  preserved), terminal `Fail the job if any nightly suite was red` step `failure` — the fail-loud
  gate worked as designed on this run.

Two of three destroyed already-passing suites' evidence via the shared upload step; the third
demonstrates the fail-loud gate functioning correctly when the upload step does run. This precision
is deliberate — it does not generalise to all six red nightlies the mission's readiness probe
found.

### WP02 — Split `performance-and-e2e` into three jobs (Commit B)

- Commit `f45a69ff9` (`feat(ci): split performance-and-e2e into independent
  performance/e2e/stress jobs`) — three independent jobs (`performance` 35m, `e2e` 40m, `stress`
  90m Stage-A-provisional), `nightly-summary.needs` updated, three hardcoded-job-name guard tests
  updated (FR-010), the two `pull_request`-trigger guard tests left unchanged.
- WP02's own task-file Activity Log carries no entries beyond "Prompt created" — the evidence above
  is sourced from the commit itself (git is the durable record here; WP07 did not re-derive it).

### WP03 — Pre-merge dispatch evidence + Stage B stress-timeout re-derivation

- Dispatch run `35756657364` (`mode: full`), captured in commit `154a6c6e6`'s own message:
  `performance` 23m23s, `e2e` 9m04s, `stress` 4m44s (success, xunit 33 tests/20 skipped/0 failed).
  Stress completed well inside Stage A's 90-minute ceiling — the widen-retry ladder (T015) and
  hang-escalation path (T016) were both correctly SKIPPED (their skip-condition, not their
  execution, is what is recorded `done` — see "Known tooling defects" below).
- Stage B commit `154a6c6e6` (`fix(ci): re-derive stress timeout from measured dispatch duration
  (Stage B)`) — 284s × 1.5 headroom ≈ 426s, rounded to `timeout-minutes: 10`, separate from WP02's
  Commit B as required.
- Reviewer-requested follow-up commit `7b0cda679` — adds `DO NOT add
  SPEC_KITTY_RUN_PERFORMANCE=...` warning comments at both the `performance` job's `env:` block
  and the `stress` job's `timeout-minutes`, naming #4865 and the truncation consequence explicitly.
- No T016 escalation issue was filed (T016 never triggered).

### WP04 — Recapture `charter` shard timings (NFR-004)

- T020: `scripts/ci/capture_shard_timings.py --module charter --write` → exit_code 0, 18m59s real
  elapsed against the plan's ~110-minute budgeted estimate; 6144 passed/12 skipped/20 deselected.
- T021: `module_capture_provenance["charter"]` populated, `auth`-shaped (`run_id`/`command`/
  `captured_at`/`test_dirs`/`selection`/`unique_tests_measured`/`exit_code`/`producer`),
  `exit_code == 0`. `module_test_count["charter"]` 4211 → 6156, matching the consumer's own
  `pytest tests/charter tests/doctrine -m "not performance and not stress" --collect-only -q`
  count (6156). Duration sum 410.755s → 1134.188s; sub-2ms share 77.3% → 36.3% (no longer
  near-uniform).
- T022 (conditional pre-existing-failure path): not triggered (`exit_code == 0`).
- T023 commit `66e5255dc` (`chore(ci): recapture charter shard timings via
  capture_shard_timings.py`) — `.github/ci-shard-timings.json` only; `.github/ci-module-registry.yml`
  untouched (WP05's scope); lane branch `kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-b`
  tip unchanged at `d1e7d5177`.

### WP05 — Re-derive `charter` `shard_count` (FR-007/SC-007) + operator-ruled correction

- T024/T025 commit `ea26fa934` (`fix(ci): re-derive charter shard_count from recaptured
  timings`) derived `shard_count = 5` from WP04's recaptured data via `_lpt_bin_pack`/`_skew_of`.
  Its own commit message and initial row comment characterized the skew gate as having become
  "non-vacuous" post-recapture — **this claim was subsequently withdrawn** (see below).
- T026 (PR #4886 collision check, first pass): `gh pr view 4886` → `state: MERGED`, `mergedAt:
  2026-09-22T13:48:39Z`, merge commit `7ff43479c094337ae8709e08eac1b838ee30dfe8`, already an
  ancestor of this branch's HEAD. The PR's only touch to `.github/ci-module-registry.yml` is a
  `test_dirs` addition under the distant `core_misc` row, not inside `charter`'s (lines 143–176).
  Outcome recorded: **merged-but-clean**.
- **Operator ruling, Decision Moment `DM-01M3584PY5A6F79DWX1QFDHW87`** (binding, implemented by a
  fresh corrective agent, not the WP05 author): WP05's committed claim that the recapture made the
  skew gate "genuinely `shard_count`-sensitive" does **not** stand. Independent re-measurement
  against the gate's own `_lpt_bin_pack`/`_skew_of`, comparing the true pre-recapture file
  (`git show 66e5255dc~1:.github/ci-shard-timings.json`, 4211 entries) to the post-recapture file
  (6156 entries), found: skew stays ~0% across the whole practical `shard_count` range (2–40ish)
  both before and after recapture; the pre-recapture data crossed the 20% NFR-005 ceiling
  **earlier** (first at `shard_count=52`, 20.1%) and **worse** (39.4% at `shard_count=67` vs
  post-recapture's 19.9% at the same k) than the post-recapture data; the k≥68 failure is a
  structural bin-packing artifact (the largest single test, 20.99s, exceeding one ideal bin's
  share), not the gate detecting genuine imbalance. `shard_count=5`'s numeric value is correct and
  unchanged by this ruling — it is justified by projected per-shard CI wall-clock (the empirically
  measured ~6.72× CI/local ratio from dispatch run `35756657364`: 5 shards summed to 7624s CI
  wall-clock against 1134.188s local for the same 6156 tests) against `module-tests.yml`'s real
  40-minute per-shard `timeout-minutes`, never by skew.
- Correction commit `d0fd9e3f3` (`fix(ci): correct inaccurate skew-gate non-vacuity claim in
  charter row comment`) reframes the row comment to state only what recapture actually fixed —
  the length match, not skew-gate sensitivity.

### WP06 — Non-vacuity repoint + committed length-agreement gate

- Per the same Decision Moment, WP06's originally-specified test
  (`test_charter_shard_skew_sensitivity.py`, asserting `shard_count`-sensitive skew) was
  **superseded** — it would have asserted a property that predates this mission.
- Honest 21-module measurement (2026-09-22): only `charter` (6156==6156, this mission's recaptured
  module) agrees between `.github/ci-shard-timings.json`'s committed duration-list length and live
  `pytest <test_dirs> -m "not performance and not stress" --collect-only -q` collection. The other
  20 rows mismatch and predate this mission, e.g. `status` 1702 committed vs 1758 collected — a
  number the Decision Moment cites independently. WP07 confirmed three of these figures directly
  against `tests/architectural/test_module_length_agreement.py`'s own `_MISMATCH_ALLOWLIST`:
  `cli` committed=2704 collected=682; `next` committed=1588 collected=559; `core_misc`
  committed=5927 collected=3574. `_BASELINE_ALLOWLIST_COUNT = 20`, matching "20 of 21 modules
  remain mismatched."
- Commit `bbb463ee2` (`test(ci): add module committed/collected length-agreement gate`) adds
  `tests/architectural/test_module_length_agreement.py` — asserts committed/collected length
  agreement for every non-allowlisted module, shrink-only allowlist (`_MISMATCH_ALLOWLIST`, 20
  entries), a dead-entry check forcing removal once a module is recaptured, a hard guard that
  `charter` can never enter the allowlist, and self-mutation tests proving the comparator fires on
  a synthetic mismatch without a subprocess call.
- WP07 independently re-ran (2026-09-22, this WP): `tests/architectural/test_module_length_agreement.py`
  → **8 passed** (32.74s); `tests/architectural/test_module_shard_registry.py` → **17 passed**
  (0.52s). Both match WP06's own recorded T031/T032 figures.

### WP07 — T034 follow-up dispatch (AC4) and T039 re-check

- **T039 (PR #4886 re-check, immediately pre-push)**: `gh pr view 4886` reconfirmed `state:
  MERGED`, `mergedAt: 2026-09-22T13:48:39Z`, merge commit `7ff43479c094337ae8709e08eac1b838ee30dfe8`
  — already an ancestor of this branch's HEAD (`git merge-base --is-ancestor` confirms). `git diff
  origin/main -- .github/ci-module-registry.yml` shows only the `charter` row's derivation-comment
  block changed (35 diff lines, one file); grep confirms zero occurrences of `core_misc` in that
  diff. **Outcome: merged-but-clean — no divergence, no escalation needed.**
- **T034 (AC4 follow-up dispatch)**: WP03's own dispatch (`35756657364`) ran BEFORE WP05's registry
  edit and WP06's new test landed (its charter-shard timestamps predate `ea26fa934`/`66e5255dc` by
  several hours), so it cannot evidence AC4 on its own. A fresh `workflow_dispatch` (`mode: full`)
  was triggered on `issue-4865-ci-nightly-wallclock-budget` at a tip carrying all registry/test
  changes: run `35781833461` (https://github.com/spec-kitty/spec-kitty/actions/runs/35781833461).
  All five `full-module-matrix` `charter` shards completed `success`. Per-shard wall-clock (own
  timestamps, `startedAt`→`completedAt`):

  | shard | duration |
  |---|---|
  | 1/5 | 16m02s |
  | 2/5 | 27m11s |
  | 3/5 | **29m57s** (long pole) |
  | 4/5 | 29m11s |
  | 5/5 | 15m36s |

  **Honest comparison, not spun:**
  - Against the pre-fix spread spec.md cites (`27m20s/27m41s/17m37s/21m13s/16m22s`, long pole
    `27m41s`): the new long pole (`29m57s`) is **worse by 2m16s**, not "no worse than." AC4's
    literal criterion — long pole no worse than the pre-fix spread — is **not met** by this
    dispatch.
  - Against the mid-mission diagnostic run `35756657364` (`21m10s/27m45s/31m13s/22m20s/24m36s`,
    long pole `31m13s`, the run that exposed #4864's positional-fallback bug in the first place):
    the new long pole is modestly better, by 1m16s.
  - Against `module-tests.yml`'s real `timeout-minutes: 40`: `29m57s` leaves ~10 minutes of
    margin — safe, consistent with WP05/DM-01M3584PY5A6F79DWX1QFDHW87's derivation, which was
    never based on beating the pre-fix baseline or on skew (both are explicitly disclaimed there).
  - Read together with WP05's own finding (local per-test-duration skew ≈0% at shard_count=5, both
    pre- and post-recapture): the ~2x spread observed here (15m36s to 29m57s) is not an artifact of
    algorithmic imbalance — it is CI-side wall-clock variance (runner contention, checkout/sync
    overhead now a proportionally larger share of a short-per-shard job) that the local-duration
    skew computation cannot see or control for. `shard_count=5`'s justification (safe margin under
    the real timeout, per WP05) still holds; AC4's stronger "no worse than pre-fix" framing does
    not.

### Known tooling defects hit during this mission (SK-91/SK-199 class)

- **WP01/WP02/WP03**: `agent action implement` silently provisioned an undeclared lane worktree
  (`.worktrees/ci-nightly-wallclock-budget-01M34HNZ-lane-a`, branch
  `kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a`) for a mission whose `meta.json`
  declares `topology: single_branch` — recorded first-hand in `tracer-tooling-friction.md`'s
  2026-09-22T15:47:11Z entry. WP01's campsite-clean commit landed on that undeclared lane branch
  first (`d1e7d5177`) and had to be re-applied directly on the target branch (`3fb1c8bb7`) on
  operator instruction.
- **WP07 (this WP)**: `agent action implement WP07` failed both attempts with `Error
  self-healing workspace for WP07: cannot auto-merge dependency lane 'lane-a'
  (kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a) into lane 'lane-planning': the merge
  conflicts.` Root cause confirmed by direct inspection: lane-a's pinned tip (`d1e7d5177`) predates
  WP02's later edits to the same file region (`.github/workflows/ci-nightly.yml`'s
  `performance-and-e2e`/`performance` job, `timeout-minutes: 60` vs the split jobs'
  `timeout-minutes: 35`) — the self-heal was attempting to merge a stale, already-superseded lane
  branch into a target branch that already carries that lane's content (and more) via different
  commit hashes, which is a genuine but spurious conflict, not real divergence. Per the operator's
  dispatch brief (pre-diagnosed as SK-91/SK-199 class) and this repo's own ledger entries
  (SK-91, SK-152, SK-199), WP07 did **not** attempt to resolve the merge, did **not** touch any
  lane branch, and did **not** retry the broken command a third time. Instead: claimed via
  `spec-kitty agent tasks move-task WP07 --to claimed` then `--to in_progress` directly (these
  transitions do not invoke the lane self-heal machinery) and did all work in the primary checkout
  — exactly where `create_planning_workspace` resolves a `lane-planning` WP's workspace to anyway.
  All four lane branches (`-lane-a/b/c/d`) were verified still pinned at `d1e7d5177` before and
  after every commit this WP made.

### Blast radius (plan.md, cited verbatim)

> Downstream consumers of the three files this mission changes: **`ci-nightly.yml` job names**: any
> downstream automation naming `performance-and-e2e` literally (a dashboard query, a Slack alert
> rule, a status-check branch-protection reference, or a sibling repo's workflow that watches this
> job's conclusion via the GitHub API) breaks silently the moment this merges — it will simply stop
> finding that job name. This repo's own `nightly-summary` and `test_performance_marker_guard.py`
> are the only in-repo consumers found by grep (already covered by FR-003/FR-010); `team-kitty-missions`
> and `muster-missions` were not found by this mission's own grep sweep to reference
> `performance-and-e2e` by name, but neither checkout was searched directly (out of this worktree's
> reach) — call this out in the PR description as an unverified-but-likely-low-risk external
> surface, per CLAUDE.md's "no follow-up issues... escalate" guidance rather than silently assuming
> zero risk.

### PR #4886 known collision (plan.md, cited verbatim)

> `gh pr view 4886` (or equivalent) should be re-checked at implementation time, but per the spec's
> own verified Correction #7: PR #4886 is open and touches `.github/ci-module-registry.yml`'s
> `core_misc` row (a `test_dirs` addition) — distant from, and non-overlapping with, this mission's
> `charter`-row-only edit (C-004). A clean merge is **not assumed**. If #4886 lands first: re-apply
> this mission's `charter`-row diff on top of the updated upstream file... If this mission's PR
> lands first, #4886 inherits the same obligation in the other direction — out of this mission's
> control, noted for the record only.

WP05's T026 and WP07's T039 both independently confirm #4886 landed first and cleanly — no
re-apply was needed.

### C-006 / C-007 (diff-cover and `sonar-pr` scope)

- **C-006**: `diff-cover` has nothing to score for the `.github/*.yml`/`.json` files in this diff —
  only `tests/architectural/test_module_length_agreement.py` (WP06) is diff-cover-measurable, and
  it is covered by definition once the always-on `tests/architectural/` tier runs.
- **C-007**: `sonar-pr` (`ci-aggregate.yml`) is reported, not required — `continue-on-error`, and
  excluded from `aggregate-gate`'s `needs:` set.

### Scoped test commands run across the mission (CLAUDE.md §6)

- `uv run --frozen pytest tests/architectural/test_module_shard_registry.py
  tests/architectural/test_performance_marker_guard.py -q` (WP01 T001) — 28 passed, 0 failed.
- `make test-fast` (WP01 supplementary) — 1941 passed, 5 skipped.
- `uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q` (WP02 T011,
  WP03 T019 re-run) — 5 passed (WP02); 2 passed (WP03's scoped trigger-test re-run).
- `tests/architectural/test_module_length_agreement.py` (WP06 T031; independently re-run by WP07)
  — 8 passed.
- `tests/architectural/test_module_shard_registry.py` (WP06 T032; independently re-run by WP07) —
  17 passed.
- Full `tests/architectural/` battery, `-m "not performance and not stress and not timing" -n auto
  --dist loadfile` (WP06 T033) — 2805 passed/3 skipped/2 xfailed without the new file; 2813
  passed/3 skipped/2 xfailed with it (one non-reproducing xdist race between
  `test_charter_sole_door_resolver_imports.py` and `test_topology_inference_retired.py`'s scratch
  file, noted, not ours). WP07 independently re-ran the same battery twice (with the file present,
  as committed): once at **2813 passed, 3 skipped, 2 xfailed in 310.60s**, and again at **2813
  passed, 3 skipped, 2 xfailed in 253.94s** (no xdist race either time) — both match WP06's "with
  it" figure exactly. The earlier verbal telling of this mission's own baseline number ("2808
  passed / 4 skipped") does not match WP06's own committed Activity Log or either independent
  re-run and must not be quoted.
- `make test-fast` (WP07, mission-final re-verification) — **1941 passed, 5 skipped in 326.21s** —
  matches WP01's baseline exactly.
- `make format-check` (WP07, mission-final re-verification) — `2229 files already formatted`.
- `npx commitlint --from origin/main --to HEAD` (WP07) — fails on exactly one commit, `2c9f9ef38`
  ("Add scaffold for feature ci-nightly-wallclock-budget-01M34HNZ", `type-empty`/`subject-empty`) —
  tool-generated by `spec-kitty agent mission create`; `commitlint.config.cjs`'s `ignores` regex
  (`^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) `) covers `Add ... for feature/mission`
  shapes but not `Add scaffold for` — ledger SK-64's documented gap. Not fixed here (see PR body).
