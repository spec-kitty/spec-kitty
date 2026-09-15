---
title: 'ADR: Main-Tip Verdict Topology — Adjudicating the #4347/#4371/#4360-A/#4430 Coupled Cluster'
description: 'Ratified coupled levers (main-concurrency, fan-out cap, main-green source, terminal-cancel verdict) so a landed main tip proves itself green honestly, in bounded time.'
status: Accepted
date: '2026-09-15'
updated: '2026-09-15'
---

## Context and Problem Statement

> **Ratified by the operator (agentic-framework-core-team) on 2026-09-15.** The
> recommended coherent bundle below — **1a / 2a / 3a (+3b target) / 4a (+4b backstop)** —
> is accepted; a follow-on implementation mission stages it per the rollout plan. Every
> mechanism claim carries a `file:line` or `issue#` (verified at the pre-mission HEAD
> `e72e13ca01`; the implementing mission re-verifies exact lines, as `main` has since
> advanced and #4360-B landed); hypotheses are labelled **[HYP]**.

Epic [#4437](https://github.com/spec-kitty/spec-kitty/issues/4437) ("CI pipeline
honesty", P1, milestone 4.0.0) rests on one invariant, set by ADR
[`2026-07-17-1-red-main-is-honest-ci-is-release-authority`](2026-07-17-1-red-main-is-honest-ci-is-release-authority.md):
mainline CI status is the release authority, which only holds if **red means a real
regression and green means actually proven**. This ADR addresses the sub-cluster of
#4437 where that invariant is broken not by a single bug but by a **shared topology**:

> **Shared root.** Main-branch CI gates are built on PR-head-triggered `workflow_run`
> fan-out, and a non-green terminal state has no honest way to report itself.

Four issues are the same shape expressed as four symptoms. The epic body (and #4371
itself) names #4347/#4360/#4371 as "one remediation, solve together"; #4430 rides the
same fleet-verdict surface and is folded in here for the same reason. **They are one
ADR, not four, because a point fix on any one lever reopens the others** (#4371:
"A point fix on any one of the three leaves the other two … Resolve together").

The four in-scope mechanisms, all confirmed against the tree at HEAD `e72e13ca01`:

1. **#4347 — main-concurrency cancel-cascade.** `.github/workflows/ci-router.yml:35-37`:
   ```
   concurrency:
     group: ci-router-${{ github.ref }}
     cancel-in-progress: true
   ```
   On `push: branches: [main]` (`ci-router.yml:22-23`) the group key is
   `ci-router-refs/heads/main` — **a single group for all of main** — so each push in
   a merge burst cancels the previous main run in-flight. Pushed content lands with
   **zero terminal evaluation**; the first survivor evaluates several merged pushes at
   once and misattributes the verdict to whichever head survives (#4347 body; six
   cancelled main runs observed 09:07–10:29Z 2026-09-14). PR refs share the same
   `cancel-in-progress: true` block but each PR ref is its own key, so PRs
   self-coalesce and are unharmed — the damage is specific to the shared
   `refs/heads/main` key.

2. **#4371 — per-tip `workflow_run` fan-out.** `.github/workflows/ci-fleet-verdict.yml:3-6`
   triggers on **eight upstream workflows** × **three event types**
   (`types: [requested, in_progress, completed]`), so up to 24 re-fires per upstream
   run, and each of those eight workflows itself runs per tip. Measured live: the
   **current main tip `e72e13ca01` alone has 60 `CI Fleet Verdict` runs** in the
   last-60 window (LIVE_CI_GROUNDING.md; #4371 quoted 45→61→94→97→82→98). There is **no
   top-level `concurrency:` block** in `ci-fleet-verdict.yml` (verified: file has only
   `on:` at `:3` and `jobs:` at `:8`; 94 lines total) and the entry job `identify`
   (`:9`) carries none, so every trigger fires a fresh `identify`. Serialization exists
   only downstream on `report` (`:42-44`, per-PR group) and `report-main` (`:71-73`,
   group `ci-fleet-verdict-main`, `cancel-in-progress: false`). `cancel-in-progress:
   false` on `report-main` means main-verdict runs **queue rather than coalesce** —
   they pile up faster than they drain (#4371: 96→183 queued in ~5 min) instead of a
   survivor dropping the stale ones.

3. **#4360-A — main-ledger empty stale-fallback (the COUPLED half of #4360).** CI
   Aggregate triggers on `workflow_run` of "CI Modules" completed
   (`.github/workflows/ci-aggregate.yml:55-58`); a `workflow_run` handler always
   executes the default-branch file and GitHub labels the run against `main`. The
   fallback source query sets `SOURCE_BRANCH` from the PR head
   (`ci-aggregate.yml:187`), queries the PR branch for a successful CI Modules run
   (`:192-193`), and on empty falls back to `--branch main --status success`
   (`:194-199`). When a **red PR-head** run triggers the main aggregate, the PR query
   returns `[]` (PR head was red) and the main query returns `[]` because **main has no
   successful CI Modules run of its own** (on main the CI Modules `report-main` legs are
   `skipped`, not `success`). The fail-closed guard then correctly refuses
   (`ci-aggregate.yml:375-382`, "N registry-expected shard(s) missing from BOTH the
   current and fallback runs … refusing to silently treat this run as complete"). **The
   guard is right; the fallback source is unsatisfiable** — live-grounded by "CI
   Aggregate = 1 failure" in the recent-25 main window (LIVE_CI_GROUNDING.md).

4. **#4430 — terminal-cancel posts no verdict.** `scripts/ci/fleet_verdict.py:86-95`:
   the red set at `:89` is `{"failure","timed_out","startup_failure","action_required"}`
   — **`cancelled` is absent** — and `:95` returns `green` only when all runs are
   `completed`/`success`. So a run with `status=completed, conclusion=cancelled` (the
   #4399 timeout-kill case) is neither red nor green → **`running`**. The
   running-dedup then suppresses the repost: `fleet_verdict.py:325-331` returns without
   posting when the new state is `running` and the latest `[ci]` comment already starts
   with `[ci] running @<sha>` (`:329`). A terminally-cancelled run therefore posts **no
   new comment, forever** — the PR strands on a stale `[ci] running`. The reporter *is*
   invoked on the cancel (`ci-fleet-verdict.yml:6` includes `completed`); it runs,
   computes `running`, and honestly-but-wrongly stays silent because it cannot tell
   "still flying" from "terminally cancelled." (`infra-error` / `no suite` exist in the
   recognition regex `:323` and vocabulary but are never *produced* by `classify`.)

**Why one decision.** The candidate menus in the four issue bodies overlap and
interact (Lens B §2, confirmed):

- **#4347 lever "drop cancel-in-progress on main" == #4371 lever (c) "stop cancelling
  in-flight main runs."** One YAML change satisfies both axes.
- **#4371 lever (a) "cap/dedup fleet fan-out per tip" also relieves #4360-A's ledger
  pollution** — fewer, coalesced main-verdict runs means fewer PR-head runs recorded
  against main's ledger.
- **#4371 lever (d) "non-Actions main baseline" would obviate #4360-A entirely** — a
  first-class main-green proof that does not depend on the Actions `workflow_run`
  ledger removes the need to fix source-eligibility at all.

Choosing one lever changes whether the others are still needed. This is a **single
design decision with coupled levers**, and it is the release-authority contract of ADR
`2026-07-17-1` — which is why the epic marks these children "deliberately NOT promoted
to `status:ready` … the design must settle before implementation" (EPIC_CONTEXT.md:10-11).

### Explicitly out of scope (the cluster boundary)

So a reader sees where this ADR stops:

- **#4360-B (diff-scoped shard reconciliation)** — the operator-flagged live repro (PR
  #4448) is a **separable** defect in the aggregate's inline reconciler
  (`ci-aggregate.yml:293-294,336,340-356`) that reproduces on a PR's *own* green head
  with no main ledger involved (Lens B §6). It is going into its own mission and is
  **not** decided here.
- **#4454** (tests-only diff selects no module), **#4208** (router-gate cannot
  distinguish timeout-kill from external-cancel), **#4212** (nightly `set +e` swallow),
  **#4374** (128 out-of-matrix test dirs — human P3 policy) — each a distinct
  mechanism, settled or human-owned, shipped separately.
- **#4420** (`status:claimed` + `ready-for-squad` = fleet) and **#4429** (closed) —
  not ours.

#4208 and #4334 are out of scope but **cross-coupled** to this cluster; see Consequences.

## Decision Drivers

- **Honesty over convenience (ADR `2026-07-17-1`).** Green must mean actually proven;
  red must mean a real regression. Neither a false-green nor a permanent false-red is
  acceptable, and both are live failure modes of the current topology.
- **Bounded time-to-green-proof.** A landed main tip must be able to prove itself green
  in bounded runner time (#4371's title verbatim: "Actions lane cannot prove a landed
  main tip green in bounded time").
- **Single canonical authority (charter).** One main-green source of truth, not two
  competing ledgers.
- **Preserve the fail-closed guard.** `ci-aggregate.yml:375-382` is correct; only
  *source-eligibility* may change (#4360: "the fix is in source eligibility, not in
  softening the guard"). No option below softens the guard.
- **Verify where the defect lives.** These are `main`-tip behaviours; a fix is only
  proven on the merged main tip, never on the PR head that carries it ("a gate never
  run is not a gate" — MEMORY).
- **Human-owned, release-authority-shaping.** This alters how `main` proves itself
  green; the lever selection is the operator's to ratify.

## Considered Options (per decision axis)

Four coupled axes. For each, the candidate levers, a **recommended** lever with
rationale, and the tradeoff of the alternatives.

### Axis 1 — Main-concurrency policy (resolves #4347)

- **1a — Per-SHA group on `main` (RECOMMENDED).** Change `ci-router.yml:35-37` so the
  push-to-main path keys concurrency on `github.sha` (or drops `cancel-in-progress` for
  the `refs/heads/main` group), leaving PR refs on the existing per-ref
  `cancel-in-progress: true`. Each landed tip then gets its **own** terminal
  evaluation; no push cancels another's. This is the shared **#4347 lever == #4371(c)**.
  *Rationale:* directly removes the cancel-starvation that lands content unevaluated;
  minimal, scoped to the main key only; keeps PR self-coalescing intact.
  *Tradeoff:* more concurrent main runs consume runners — which is exactly why Axis 2
  (fan-out cap) must land with it, or the extra main runs multiply the fleet-verdict
  storm.
- **1b — Merge-gate bookkeeping.** Record each tip's verdict in a durable ledger the
  merge agent reads, tolerating cancellation. *Tradeoff:* larger surface, introduces a
  second bookkeeping authority (charter single-authority tension), does not stop the
  cancellation itself.
- **1c — Merged-tree preflight.** Evaluate the merged tree before it lands.
  *Tradeoff:* changes the landing flow, heavier; useful long-term but out of proportion
  to the immediate honesty hole.
- **1d — Cancelled-run reconcile sweep.** A sweep re-runs or reconciles cancelled main
  runs after the fact. *Tradeoff:* reactive, adds a moving part, and leaves the window
  where main is unproven.

### Axis 2 — Fleet-verdict fan-out cap / dedup (resolves #4371)

- **2a — Top-level `concurrency` + trim `types:` + dedup (RECOMMENDED).** Add a
  top-level `concurrency:` block to `ci-fleet-verdict.yml` keyed per tip (per-SHA for
  main, per-PR for PR heads) so redundant triggers coalesce to a single surviving
  `identify`; trim `types: [requested, in_progress, completed]` (`:6`) to `completed`
  only — a verdict is a function of *terminal* upstream state, so `requested` and
  `in_progress` transitions are pure fan-out with no verdict value; and keep/reinforce
  the dedup in `scripts/ci/fleet_verdict.py` / `fleet_main.py`. This is **#4371(a)**.
  *Rationale:* attacks the multiplicative fan-out at its two roots (event-type triple ×
  no throttle); the survivor always re-reads current state, so coalescing loses no
  information; **also relieves #4360-A** by cutting the volume of PR-head runs recorded
  against main's ledger. *Tradeoff:* a mis-scoped cap could drop the one verdict a
  landed tip needs (a false-red/wedge) — mitigated because the dedup keeps the
  *survivor* that re-reads current evidence, never drops the last writer; the
  `report-main` group must move from `cancel-in-progress: false` (queue) toward
  coalesce-with-survivor so the queue cannot outgrow the drain.
- **2b — Prioritize main-tip over PR-head runs.** Give main runs runner priority.
  *Tradeoff:* does not reduce the fan-out, only reorders it; GitHub-Actions priority
  control is coarse.
- **2c — Stop cancelling in-flight main runs.** Identical to Axis 1a — listed by #4371
  as its lever (c); adopting 1a satisfies it. Not an independent Axis-2 choice.
- **2d — Non-Actions main baseline.** See Axis 3, lever 3b — a baseline that obviates
  the fan-out's role as the main-green proof.

### Axis 3 — Main-green source of truth (resolves #4360-A)

- **3a — Fix source-eligibility, keep the guard (RECOMMENDED near-term).** Change which
  branch/source the fallback query treats as eligible (`ci-aggregate.yml:187-199`) so
  a PR-head `workflow_run` run labelled against `main` resolves a **main-eligible**
  source or fails with a *named* eligibility error — never returns `[]` silently. The
  extraction of that inline shell logic (`:191-201`) into a Python helper under
  `scripts/ci/` is the **one genuine pytest red-first entry point** in this cluster.
  **The fail-closed guard (`:375-382`) is preserved unchanged.** *Rationale:* smallest
  change that makes the main ledger honest; keeps the guard; testable. *Tradeoff:* it
  keeps main-green *dependent on the Actions ledger* — the deeper fragility #4371(d)
  removes. Contingency: if Axis 2 (fan-out cap) is chosen such that main produces a
  first-class successful CI Modules run of its own, the fallback becomes satisfiable and
  3a's role shrinks to a safety net.
- **3b — Stand up a non-Actions main baseline (RECOMMENDED as the durable target).**
  An authoritative main-green proof that does not depend on the `workflow_run` ledger
  (**#4371(d)**) — this **obviates #4360-A entirely**. *Rationale:* removes the "PR-head
  runs are inputs to a main gate" shape at the root. *Tradeoff:* a larger build (a new
  producer/store and its own trust model); higher risk if rushed. **Recommendation:
  adopt 3a now behind the preserved guard, and record 3b as the target that retires
  this axis** — do not soften the guard to bridge the gap.
- **3c — Exclude PR-branch `workflow_run` from the main ledger.** Filter the aggregate
  so PR-head runs never post against main. *Tradeoff:* correct in spirit but leaves
  main with *no* proof source until 3a/3b supplies one — risks a permanent false-red on
  main. Best combined with 3a, not alone.

### Axis 4 — Terminal-cancel verdict class + consumer (resolves #4430)

- **4a — In-CI `infra-error` terminal verdict, releases the head (RECOMMENDED).** Add a
  terminal-cancel class to `classify` (`fleet_verdict.py:86-95`): when a required run is
  `completed`/`cancelled` (and not already red via `timed_out`), emit `infra-error` —
  distinct from both `running` and `green` — and ensure the dedup (`:325-331`) does
  **not** suppress it (the running-guard at `:329` matches only `state=="running"`, so a
  fresh `infra-error` comment posts and releases the head as re-triggerable). Thread the
  same class through the main path (`scripts/ci/fleet_main.py`,
  `ci-fleet-verdict.yml:92-93`) for one coherent "terminal-cancel = infra-error, never
  green, always released" semantics across PR and main. *Rationale:* smallest honest
  fix; preserves the never-green safety (`fleet_verdict.py:87`); un-strands the PR.
  RED-FIRST via `tests/ci/test_fleet_verdict.py` (flip the pinned
  `("completed","cancelled","running")` contract at `:155`/`:289-290` to a non-green,
  non-running class, plus a new `test_terminal_cancel_reposts_and_is_not_suppressed`).
  *Tradeoff:* `classify`/`report` are the release-authority gate for every PR; a wrong
  change here could green-wash or spuriously red — mitigated by keeping `infra-error`
  strictly outside the green path.
- **4b — Merge-agent sweep surfaces the stale-running as a watch item.** A consumer
  (merge/night-watch agent) flags "last verdict is `running` but its run is terminal."
  *Tradeoff:* lives outside CI (`agents/merge.md` surface), reactive, does not release
  the head automatically. *Recommendation:* pair as a backstop to 4a, not as the
  primary — the head should be released in-CI, not by a human/agent sweep.

## Decision Outcome (ratified 2026-09-15)

**Ratified coherent bundle** (the levers are chosen *together* precisely because they
interact; the operator ratified all four recommended levers on 2026-09-15):

| Axis | Recommended lever | Resolves | Coupling note |
|------|-------------------|----------|---------------|
| 1 — main-concurrency | **1a** per-SHA group on `main` | #4347 | == #4371(c) |
| 2 — fleet fan-out | **2a** top-level `concurrency` + trim `types:` to `completed` + dedup | #4371 | relieves #4360-A |
| 3 — main-green source | **3a** fix source-eligibility, **guard preserved**; **3b** non-Actions baseline as the target that retires the axis | #4360-A | #4371(d) obviates 3a |
| 4 — terminal-cancel | **4a** in-CI `infra-error`, releases head; 4b sweep as backstop | #4430 | shares fleet-verdict surface with Axis 2 |

**Why this bundle and not four point fixes.** 1a removes cancel-starvation but *adds*
main runs; 2a caps the fan-out those extra runs would otherwise multiply — so 1a and 2a
must land together. 2a's coalescing cuts PR-head pollution of main's ledger, shrinking
what 3a must repair. 3b, if built, retires Axis 3 outright. 4a shares the exact
`classify`/`report` surface 2a's dedup touches, so they must be one coherent
terminal-state semantics. A point fix on any one silently reopens another (#4371).

### The two bounding failure modes, and how the bundle avoids each

Every option is bounded by two outcomes, both worse than the status quo (Lens B §4):

1. **False-green — the fleet merges unproven code.** Avoided by: **keeping the
   fail-closed guard** (`ci-aggregate.yml:375-382`) untouched — only source-eligibility
   (3a) changes; `infra-error` (4a) is defined strictly outside the green path
   (`fleet_verdict.py:87` never-green invariant preserved); no PR-head partial-shard set
   is ever allowed to satisfy the main ledger. This upholds ADR `2026-07-17-1`: green
   still means actually proven.
2. **False-red / permanent-wedge — main never proves green.** Avoided by: 1a giving
   each landed tip its own terminal evaluation (no cancel-starvation); 2a's dedup
   keeping the *survivor* that re-reads current evidence (never dropping the last-writer
   verdict a landed tip needs); 4a posting `infra-error` to *release* a
   terminally-cancelled head instead of stranding it on `[ci] running`; and 3a resolving
   a named eligibility error instead of an empty `[]`.

The recommendation deliberately refuses the two tempting shortcuts that would break (1):
softening the aggregate guard, and letting a PR-head run's partial shards count as
main-green. Both are explicitly rejected.

## Consequences

### Positive

- A landed main tip can prove itself green in bounded runner time; the 60-runs-per-tip
  fan-out (LIVE_CI_GROUNDING.md) collapses toward one verdict per tip.
- Merge bursts no longer land content on main unevaluated (#4347 closed).
- The main ledger stops being fed by PR-head runs, or fails with a *named* error instead
  of a silent `[]` (#4360-A closed near-term; #4371(d) path recorded for durable close).
- A terminally-cancelled PR is released and re-triggerable instead of wedged on `[ci]
  running` (#4430 closed).
- Single main-green authority preserved; the fail-closed guard is untouched, so
  release-authority honesty (ADR `2026-07-17-1`) is strengthened, not weakened.

### Negative / accepted risk

- The concurrency (1a) and fan-out (2a) changes are **config-level YAML**, largely not
  unit-testable in pytest; provable only by workflow-lint / golden-YAML shape assertions
  plus dedup unit tests in `tests/ci/`. Only Axis 3a's extracted eligibility helper has
  a genuine pytest red-first pin. The mission spec must state this honestly rather than
  pretend a unit test covers the YAML change (Lens B §3).
- `classify`/`report` (Axis 4a) is the per-PR release gate; the change adds a new
  non-green class and must not widen the green path. MEDIUM risk; the never-green tests
  (`fleet_verdict.py:87`, `test_truncated_files_and_deferred_pr_never_green`) must stay
  green.
- 1a increases concurrent main runs; without 2a landing with it, the fleet-verdict storm
  worsens. The two are sequenced together for this reason.

### Staged rollout — "a gate never run is not a gate"

These are `main`-tip behaviours. The change alters the very lane that would validate the
PR carrying it, so it **can only be fully proven on `main` after merge** — the first
moment the main-tip path exists (Lens B §4; MEMORY "a gate never run is not a gate").
The implementing mission must therefore:

1. Land the levers in a **staged sequence** (concurrency + fan-out cap together, then
   source-eligibility, then terminal-cancel), each on an `issue-<n>-<slug>` branch → PR
   → operator merges (never a push to `main`).
2. **Verify each stage on the merged main tip**, not on the PR head — count fleet-verdict
   runs per tip, confirm a single coalesced verdict, confirm the aggregate resolves a
   main-eligible source, confirm a forced cancel posts `infra-error`.
3. Treat any consumer this ADR did not name as a **finding against this ADR**, not a
   licence to improvise around it.

### Cross-coupling (out-of-scope issues this cluster moves)

- **#4208 (its inputs).** #4347's `cancel-in-progress` is what *produces* the
  `cancelled` states #4208's router-gate must classify. Adopting Axis 1a **stops
  cancelling main runs, changing #4208's input distribution** — the two must be
  coordinated so #4208's timeout-vs-external-cancel classifier is not built against a
  distribution this ADR removes.
- **#4334 (sonar-pr consumes aggregate shards).** The `sonar-pr` job in
  `ci-aggregate.yml` consumes the reconciled shard coverage; it is `continue-on-error`
  and excluded from the terminal `aggregate-gate` (reported, not required). An Axis-3a
  source-eligibility change must be verified to leave `sonar-pr` tolerant of the
  resolved source set — non-blocking, so a smaller/different set is not a false-red on
  the PR path, but confirm it does not error the informational job. **[HYP]** — sonar-pr
  not re-read this pass.

### Neutral

- No doctrine is changed. ADR `2026-07-17-1` remains in force and unedited; this ADR
  operationalises its "green means proven" invariant on the main-tip topology.
- The diff-scoped reconciler (#4360-B) is untouched and proceeds as its own mission;
  this ADR's Axis-3 changes do not read the reconciler's selection logic.

## Confirmation

Ratification of this ADR is confirmed in practice when, on the merged main tip:
(a) one landed tip produces a bounded, single coalesced `CI Fleet Verdict` rather than
dozens; (b) no main content lands without a terminal evaluation during a merge burst;
(c) CI Aggregate on main resolves a main-eligible source or fails with a named
eligibility error, with the fail-closed guard (`ci-aggregate.yml:375-382`) unchanged;
and (d) a terminally-cancelled PR-head run posts `infra-error` and releases the head.
A main tip reported green on unproven content, or a permanently-wedged main verdict,
is a violation of this ADR and of ADR `2026-07-17-1`.

Confidence: **high** on the mechanisms (every `file:line` re-verified in-tree at HEAD
`e72e13ca01`); **medium** on the exact YAML/dedup mechanics, which are the implementing
mission's to finalise within the lever selection ratified here.

## References

- Issues: [#4437](https://github.com/spec-kitty/spec-kitty/issues/4437) (epic),
  [#4347](https://github.com/spec-kitty/spec-kitty/issues/4347),
  [#4371](https://github.com/spec-kitty/spec-kitty/issues/4371),
  [#4360](https://github.com/spec-kitty/spec-kitty/issues/4360) (part A — the coupled
  main-ledger half; part B out of scope),
  [#4430](https://github.com/spec-kitty/spec-kitty/issues/4430). Cross-coupled but out
  of scope: [#4208](https://github.com/spec-kitty/spec-kitty/issues/4208),
  [#4334](https://github.com/spec-kitty/spec-kitty/issues/4334).
- Governing ADR: [`2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`](2026-07-17-1-red-main-is-honest-ci-is-release-authority.md).
- Research inputs (local, `work/`): `EPIC_CONTEXT.md`, `SYNTHESIS.md`,
  `LIVE_CI_GROUNDING.md`, `lenses/B-fanout-cluster.md` (primary),
  `lenses/C-verdict-and-nightly.md` (#4430).
- Code anchors (HEAD `e72e13ca01`): `.github/workflows/ci-router.yml:22-23,35-37`;
  `.github/workflows/ci-fleet-verdict.yml:3-6,42-44,71-73,92-93`;
  `.github/workflows/ci-aggregate.yml:55-58,187-199,375-382`;
  `scripts/ci/fleet_verdict.py:86-95,323-331`; `scripts/ci/fleet_main.py`.
