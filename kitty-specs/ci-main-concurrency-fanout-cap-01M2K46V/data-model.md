# Data Model: CI Main Concurrency + Fleet Fan-out Cap (Stage 1)

This mission has no persistent datastore. The "entities" are the CI concurrency-key domains and the verdict-state machine the fan-out cap must not perturb.

## Entity: Concurrency Group (GitHub Actions)

A GitHub Actions concurrency group serializes/coalesces runs that share a `group` key. At most one run per group runs at a time; `cancel-in-progress` decides whether a newer run cancels an in-flight one or queues behind it.

| Workflow | Scope | Group key (target) | cancel-in-progress | Membership meaning |
|---|---|---|---|---|
| `ci-router.yml` | top-level | `ci-router-<sha>` on push→main; `ci-router-<ref>` on PR/dispatch | `false` on push, `true` otherwise | One group **per landed main tip** (singleton) vs one **per PR ref** |
| `ci-fleet-verdict.yml` | top-level (NEW) | `ci-fleet-verdict-<head_sha>` | `true` | One group **per tip** (main or PR head) — coalesces redundant `completed` triggers |
| `ci-fleet-verdict.yml` | `report-main` job | `ci-fleet-verdict-main` (**UNCHANGED**) | `false` (**UNCHANGED**) | Single group across **all** main tips — **cross-tip serialization preserved** (two concurrent red tips cannot both create an incident issue); inflow is now ≈1/tip via the top-level coalesce, so the queue drains trivially |
| `ci-fleet-verdict.yml` | `report` job (PR) | `ci-fleet-verdict-pr-<matrix.pr>` (unchanged) | `false` (unchanged) | One group **per PR** — unchanged by Stage 1 (comment refreshed only; C-YAML-6) |

**Invariant CK-1 (no cross-*landed-tip* coalescing).** No group that can span two distinct **landed main tips** may carry `cancel-in-progress: true` — otherwise a newer main tip could cancel an older tip's unposted verdict (violates NFR-002). Concretely, every `cancel:true` group keyed on **main content** embeds `github.sha` / `head_sha` (top-level fleet-verdict per-SHA; router per-SHA on push). **PR-ref coalescing is explicitly intended and exempt**: `ci-router-<ref>` (`cancel:true`, keyed on `github.ref`) SHOULD supersede an older PR commit's run — correct FR-002 behavior, not a CK-1 violation. Do **not** "fix" the PR-ref key to per-SHA. Note `report-main`'s single shared group carries `cancel:false`, so it is exempt by construction (no cancellation at all).

**Invariant CK-2 (PR path preserved).** The `pull_request` branch of `ci-router.yml` and the `report` (PR) job keep their existing keys and `cancel-in-progress` values byte-for-byte (FR-002).

## Entity: workflow_run Trigger

`ci-fleet-verdict.yml` fires on the `workflow_run` of 8 upstream workflows.

| Field | Before | After | Note |
|---|---|---|---|
| `workflows` | 8 named workflows | unchanged | The set the reporter's golden-YAML test asserts against |
| `types` | `[requested, in_progress, completed]` | `[completed]` | Verdict is a function of terminal state only (FR-004) |

**Invariant WT-1.** Only `completed` upstream transitions may start a verdict evaluation; `requested`/`in_progress` are removed as pure fan-out.

## Entity: Fleet Verdict State (unchanged by Stage 1 — pinned, not modified)

`classify()` (`fleet_verdict.py:86-95`) maps observed upstream runs → one of:

```
             ┌───────── any present run completed & conclusion ∈
             │          {failure, timed_out, startup_failure, action_required}
   red ◄─────┤
             │
 running ◄───┼──── labels ∩ {pr:deferred, pr:skip-ci}  OR  evidence absent/incomplete
             │     OR  a present run not completed/success
             │     (NOTE: cancelled → running today; Stage 3/#4430 will add infra-error — NOT this stage)
   green ◄───┴──── all present runs completed & success
```

**Invariant VS-1 (never-green preserved).** Absent, cancelled, skipped, or incomplete evidence never becomes green (`fleet_verdict.py:87`; `test_truncated_files_and_deferred_pr_never_green`). Stage 1 does not touch `classify`.

**Invariant VS-2 (survivor re-reads).** The reporter double-snapshots current evidence and refuses to publish if head/evidence drifted between reads (`report()` `:317` + `:332-334`; `fleet_main.report()` `:124`). The fan-out cap (CK-1) depends on this: the coalesced survivor always recomputes from live state, so coalescing loses no verdict.

## Entity: Verdict Ledger

- **PR path**: `[ci] <state> @<head_sha> …` bot comments on the PR issue; deduped by an embedded `<!-- evidence: … -->` fingerprint and a `[ci] running @<sha>` running-suppression (`fleet_verdict.py:318-341`).
- **Main path**: a single open `from:ci` P0 incident issue, deduped/fingerprinted by `fleet_main.report()`.

**Invariant VL-1.** Stage 1 does not change the ledger format, the fingerprint, or the running-suppression regex (`:323`, which already *recognizes* `infra-error`/`no suite` for Stage 3). Coalescing operates above the ledger; the ledger's idempotence is what makes concurrent survivors safe.

## State transition: a merge burst of N tips (target behavior)

```
push A, push B, push C  (within one CI cycle)
   │
   ├─ ci-router:  group ci-router-<A>, <B>, <C>  → 3 independent runs, none cancelled   (FR-001)
   │
   └─ each upstream workflow completes per tip → ci-fleet-verdict fires (types: completed)
         group ci-fleet-verdict-<head_sha=A|B|C>, cancel-in-progress: true
             → redundant per-tip triggers coalesce to the last completion (survivor)
             → survivor re-reads live evidence, posts ONE terminal verdict per tip        (FR-003/005, NFR-002)
   Result: 3 tips, 3 terminal verdicts, ~3 coalesced fleet-verdict runs (not ~180).
```
