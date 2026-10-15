---
title: "Grounding note — #4941 wall-clock claim loses a real-time rejection"
issue: 4941
priority: P0
updated: 2026-10-15
status: grounding complete; §2 remedy escalation pending operator ruling
divio_type: explanation
audience: agentic-framework-core-team
---

# #4941 — the status reducer orders by wall clock, so a rejection minted after a future-stamped approval is silently dropped and `consolidate` lands rejected code

Read-only grounding committed before any spec/fix (semi-auto-delivery procedure:
"never specify before grounding"). Every claim below was checked against the
code at this checkout (branch `issue-4941-wall-clock-claim-fix`, off `main`
`3f890918`), not from memory. Empirical anchor: the red-first repro
`tests/consolidation/test_wall_clock_claim_p0_repro.py` (brought in from PR
#6230) **FAILS** on this branch through its gate
(`SPEC_KITTY_RUN_P0_REPRO=1 pytest … -n0` → 1 failed), confirming the defect.

## 1. Root cause (confirmed against code)

The scenario: WP02 is `in_review`. Reviewer A approves (`in_review -> approved`)
from a clock **+10 min ahead**, so the approval row carries a future `at`.
Reviewer B, on a correct clock, then rejects.

1. **Emit derives `from_lane` from the reduced snapshot.**
   `emit.emit_status_transition` reduces the write surface (`_reduce_write_surface`
   → `status.reducer.reduce` → `spec_kitty_events.diary.reduce_parsed`,
   `src/specify_cli/status/emit.py:985`, `:290`) and `_derive_from_lane`
   (`emit.py:294`) returns the current lane. The approval is already in the log,
   so the current lane reads `approved`. Reviewer B's rejection is therefore
   minted as **`approved -> in_progress`** (`emit.py:222`,
   `at=at or now_utc_iso()` — the real, earlier clock).
2. **The reducer orders by `at` (wall clock).** `diary._order_transitions`
   sorts by `(at, approval-pairing flag, event_id)`
   (`.venv/.../spec_kitty_events/diary.py:1685-1709`). The rejection (`at`=T)
   sorts **before** the approval (`at`=T+600s).
3. **Arm (ii) continuity (#69) then drops the rejection.** In the fold, at the
   rejection's sort position the WP is still `in_review` (the approval hasn't
   folded yet). The rejection's `from_lane=approved != in_review` and it is not a
   rollback event (`_is_rollback_event` requires `from_lane ∈ {in_review,
   for_review+ref}`; `diary.py:1083-1095`, `_REJECTION_ROLLBACK_TARGETS` at
   `:1071`), so `_arbitrate_event` returns `LOST_ON_CONTINUITY`
   (`diary.py:1563-1569`) and the rejection is **dropped**. The approval then
   folds cleanly (`in_review -> approved`). Final lane: `approved`.
4. **Everything downstream trusts that mis-reduction and reports success.**
   - `emit` prints `OK approved -> in_progress` (the row exists; `store` only
     confirms existence, `store.py:317-333`).
   - `status validate` PASSes — it replays sorted by `(at, event_id)` and checks
     per-edge legality only, never that an event's `from_lane` equals the lane the
     preceding events produce (`validate.py:154-187`, `:168`).
   - **The consolidation gate is exposed.** `reconciliation.build_approved_wp_set`
     reads WP membership through `status.reducer.materialize_snapshot`
     (`reconciliation.py:1442,:1473`), and `materialize_snapshot`
     (`reducer.py:373,:377`) calls `reduce_shared_state =
     spec_kitty_events.status.reduce`, which **is** `diary.reduce` (verified:
     `status.reduce is diary.reduce` → True; `status.py:169`). It is NOT the
     Lamport `reduce_status_events` (`status.py:763`, uncalled from `src/`). So
     the gate keeps WP02 in its approved claim and `consolidate` lands the
     rejected content on the target.

**Correction to a prevalent misreading (and to one discovery-squad finding):**
`materialize_snapshot` is *not* Lamport-robust. The docstrings in
`src/specify_cli/consolidation/` that call it "the Lamport reduction wrapper"
are wrong (operator triage ruling 2026-10-14; #6213). CLI lane transitions carry
no `lamport_clock` at all, so even the Lamport reducer would degrade to a
timestamp tiebreak for these rows.

## 2. Invariant the fix must establish, with citations

**Write-time per-WP monotonicity of `at` is the missing invariant.** A locally
appended transition must sort *after* the lane event it was derived from. The
issue's "Expected" names three ways to get there (emitter refuse/warn; stamp
`at ≥ last_transition_at`; or a causal reducer). The reducer's arm (ii)
(`diary.py:1498-1572`, #69, spec-kitty-events#87) already tries causal
precedence but is defeated precisely because the emitter derived
`from_lane=approved` from a future-stamped predecessor — i.e. the real defect is
at **write time**, not read time.

Related invariants that must survive:
- Rollback-aware precedence (ADR `docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md`;
  #4990 from-lane continuity, events 10.4.0) — the fix must not reopen a
  done/canceled/reworked WP.
- Explicit-`at` callers must keep their `at`: the batch path synthesizes
  monotonic microsecond-stepped `at` (`emit.py:1113`,
  `status_transition.py:2024`) and migration/backfill builders set **historical**
  `at` on purpose (`migration/backfill_runtime_state.py:867…`,
  `wp_status_backfill.py:278`, `verdict_provenance_backfill.py:393`). A clamp
  must fire **only when `at is None`** (the live-emit default) or it corrupts
  reconstruction and breaks `tests/status/test_transition_pipeline.py:276,278`
  (explicit-`at` passthrough assertions).
- P0 red-main discipline (charter SO#9, ADR `2026-07-17-1`): the red-first repro
  witnesses the bug; the fix turns it green and removes its `p0_repro` marker.
- Shared-package boundary (charter "External Contract Packages", ADR
  `2026-04-25-1`): `spec_kitty_events` is an external contract package; changing
  its reducer is a cross-repo contract-version action (escalation on versioning
  mechanics), not an in-repo edit.

## 3. Every write/read surface that shares this defect-shape (similar-surfaces squad)

**Live lane-transition write doors** (all pass through the one build authority
`status/transition_pipeline.py::prepare_transition:245` → `build_status_event`):
- Flat/primary shell: `emit.emit_status_transition:860`, `emit_status_transition_batch:1126`.
- **Transactional shell** `coordination/status_transition.py`:
  `emit_status_transition_transactional:1598`, `…_batch_transactional:1887` — these
  call `prepare_transition` **directly** and append via the transaction; they do
  **not** go through `emit.emit_status_transition`. **A clamp placed only in
  `emit.emit_status_transition` would miss them** (and orchestrator-api, which
  reuses the transactional door: `orchestrator_api/wp_lifecycle.py:846,851`).
  → Disposition: **in-scope-now** — the clamp belongs at `prepare_transition`
  (single authority), fed `last_transition_at` from each shell's already-reduced
  snapshot, gated on `at is None`.
- Migration/backfill direct builders bypass `prepare_transition` and set
  historical `at` → **out of scope by design** (excluded from any clamp).

**Reads that trust the wall-clock reduce** (defense-in-depth context, not all
in-scope): `status/doctor.py` stale-claim age (a future `at` suppresses stale
detection), `review/arbiter.py`, subtask/move-task reads via
`wp_snapshot_state`. The approval/merge/validate gates read `materialize_snapshot`
(same wall-clock reducer — exposed, per §1).

**Union merge driver** `status/event_log_merge.py:176-182` also orders by `at`.
A teammate's skewed row arriving purely via `git pull` with **no subsequent
local emit** is NOT fixed by an emit-time clamp (the clamp only governs rows this
process mints). The existing backstop is `detect_concurrent_fork:91` (narrow) and
the reducer's from-lane continuity. → **file-and-link** as a cross-clone /
reducer-level residual (spec-kitty-events), not silently widened here.

**Text-vs-instant ordering residual** (issue comment 2026-10-13): `diary`
orders/pairs `at` as text, so mixed `…Z` vs `…+00:00` spellings can invert order.
A spec-kitty-events change. → **file-and-link**; the in-repo clamp must compare
*parsed instants* and emit `+00:00` to avoid reintroducing it locally.

## 4. Tracked-issues disposition (tracked-issues squad)

| Issue/PR | State | Disposition |
|---|---|---|
| #4941 | OPEN P0, parent epic #3893 | **Closes** |
| #6230 | OPEN PR (repro, `pr:p0-repro`) | **Refs**; its test de-markered here (base on it or land it first — operator decides) |
| #6213 | **CLOSED** (PR #6231 fixed only AGENTS.md) | **Refs**; fold the deferred consolidation-docstring + dead-test sweep it left "until #4941 settles the ordering" |
| #4990 | CLOSED (events 10.4.0) | supersede note — fixed only the concurrent arm; general wall-clock skew remains here |
| #2985/#2989, #3960/#4071, #4858/#4884, #4899/#4935 | closed/unrelated shapes | none |
| epic #1795 | OPEN | not parent (explicitly does not cover timestamp-ordered reduction) |
| epic #3893 | OPEN | **live parent** |

Siblings/duplicates sweep ("wall clock" / "clock skew" / "4941"): no live
collision — only #4941 (open) and #6230 (open). No scope widening.

Dead test to repair/delete (in #6213's scope, folded here):
`tests/consolidation/test_reconciliation.py::test_build_claim_excludes_committed_rejection_lamport`
patches `reducer.reduce_parsed` (a name `materialize_snapshot` never calls) and
its cancel is wall-clock-later than the approval, so it cannot fail on the
property it names.

## 5. Gates / ledgers touching these surfaces, and how to keep each green honestly

- `tests/_support/test_p0_repro.py` + `tests/architectural/test_marker_job_completeness.py`
  — implicated by removing the `p0_repro` marker; run them specifically.
- `tests/architectural/test_no_legacy_terminology.py` — if docstring edits touch
  prose; cheap (~0.1s).
- No architectural allowlist/shrink-only ledger is grown by the candidate fix
  (in-repo emitter change). Per `NO_FULL_HEAVY_SUITES_IN_MISSION`, run the
  specific gate files above — never a bare `tests/architectural/` sweep.

## 6. Recommended remedy (pending operator §2 ruling — escalation required)

**(a) Emitter monotonic clamp at the single build authority.** In
`prepare_transition` (fed the current WP's `last_transition_at` from each shell's
snapshot), when `at is None` and the current lane's `last_transition_at` is in
the future relative to the emitter's own clock, stamp `at = last_transition_at +
ε` (compare parsed instants; emit `+00:00`) so the new transition sorts after the
anomalous predecessor and takes effect; warn on the detected skew. Smallest
in-repo diff that fixes the write-time root; covers every live door (flat,
transactional, orchestrator-api); stays inside the shared-package boundary;
honors the operator's rejection intent; turns the repro green.
- Does **not** fix the pure `git pull` union-merge path or the text-vs-instant
  residual (both spec-kitty-events-level) — file-and-link, do not widen.
- Optional defense-in-depth: a `status validate` continuity check (flag a log
  whose file-order successor has an earlier `at` and a `from_lane` the reducer
  does not produce), per the issue's "Expected".

**(a′) Emitter refuse** — same site, raise `TransitionError` instead of clamping.
Fail-closed and loud, but blocks a legitimate rejection until the clock catches
up (minutes). Accepted by the repro.

**(b) Causal reducer (external `spec_kitty_events`)** — correct at root and also
fixes the git-pull path, but a cross-repo contract-version change (bump + machine
contract + version ledger + human docs together; itself a further escalation on
versioning mechanics) and crosses the shared-package boundary. Must not be taken
silently.

**(c) Gate-side only (reconciliation + validate)** — defense-in-depth; does not
fix the emit-side false "OK" and the self-healing-lane confusion.

Recommendation: **(a)** with the optional validate-side guard. The choice is an
escalation-class decision (shared seam + public/versioned contract boundary) and
is put to the operator before any production code.

## 7. BDD acceptance-scenario feasibility (operator addendum)

Assessed per the dispatcher-relayed operator addendum/correction: can the #4941
behaviour feasibly be captured as a **customer-first** Gherkin acceptance
scenario (`tests/scenarios/<area>/*.feature`, Cucumber-JVM, tagged
`@promise:<id>` only — not `@defect:`), *without* widening the P0 fix to build
new test infrastructure?

**Verdict (corrected after operator challenge): land the scenario now as a
drafted `@wip`, and track binding separately.** The acceptance-scenarios how-to
(`docs/development/testing/acceptance-scenarios.md` §"Drafted scenarios") has a
first-class workflow for exactly this: "A scenario drafted from a promise page
lands as `@wip` … It may use steps that have no binding yet. An engineer then
binds the steps, adds a positive control and removes `@wip`." A `@wip` scenario
runs only in the non-gating `@wip` pass and never fails the leg, and the per-PR
contract (`scenario_contract.py`) reports an unbound step in a non-gating
scenario as `INFO`, not `ERROR` (`is_gating` False → `severity = INFO`). So the
behaviour can be captured in-repo **now** without building any automation.

What is genuinely deferred (removing `@wip`) still needs the black-box "build a
WP to a Mission state" fixtures — issue **#6137**, under BDD epic **#6133** — and
new Arrange/Act/Assert JVM step defs; the only black-box-injectable skew shape is
the production-equivalent planted future-`at` row (the CLI reads no clock env var
and the JVM runner cannot monkeypatch `kernel.clock`). Not built in this P0 fix.

**Disposition:** add `tests/scenarios/status/event-traceability.feature` as a
`@wip` scenario (customer-first promise: "recorded work-package decisions are
honoured in the order they happen"; `@wip @wip-owner @wip-since` only — **no
`@promise` tag**, since resolving the behaviour to a promise id is a QA-team
concern added at binding; no clocks/skew/bug wording), and file **#6260** as the
"bind the steps, assign the promise id, remove `@wip`" follow-up (child of #6133,
refs #6137). The de-markered pytest repro remains the gating regression guard.

## 8. 90-day churn / interactions

`spec_kitty_events.diary` reducer precedence has churned heavily
(#4990/10.4.0 causal arm; spec-kitty-events#81/#87; #6061 seed narrowing). The
in-repo emitter clamp avoids touching that hot external surface. Sibling cloud
runs today touch CI routing, charter-pack, next-runtime-bridge, #6235
autocrlf, and #6247 upgrade/command-migration — none touch `status/` or
`consolidation/`; no file collision with this run.
