# Mission Specification: CI Main Concurrency + Fleet Fan-out Cap (Stage 1)

**Mission Branch**: `fix/ci-main-concurrency-fanout-cap`
**Created**: 2026-09-15
**Status**: Draft
**Input**: Stage 1 of the ratified main-tip verdict-topology cluster of epic #4437. Governing authority: ADR [`docs/adr/3.x/2026-09-15-1-ci-main-verdict-topology.md`](../../docs/adr/3.x/2026-09-15-1-ci-main-verdict-topology.md) (PR #4534). This mission implements ADR levers **1a** (#4347) and **2a** (#4371) — the two coupled levers that must land together.

> **Cluster context.** This is the first of **three sequential stage-missions** implementing one coupled ADR. Stage 2 (`ci-aggregate-source-eligibility`, ADR 3a / #4360-A) and Stage 3 (`ci-terminal-cancel-verdict`, ADR 4a / #4430) are separate missions, each created and implemented only **after its predecessor has landed on upstream `main` and been verified on the merged main tip** ("a gate never run is not a gate"). Each stage is its own PR to upstream `main`, operator-merged.

## User Scenarios & Testing *(mandatory)*

The "user" of this mission is the **release-authority contract** (ADR `2026-07-17-1`): a maintainer relying on main-branch CI status to mean *green = actually proven, red = a real regression*. Today that contract is broken by a shared CI topology; Stage 1 fixes the two coupled halves that produce unevaluated landings and an unbounded verdict fan-out.

### User Story 1 - A landed main tip is never cancelled into oblivion during a merge burst (Priority: P1)

When several PRs merge to `main` in quick succession, each pushed tip must receive its **own terminal CI evaluation**. Today all main pushes share one concurrency group (`ci-router-refs/heads/main`, `cancel-in-progress: true`), so each push cancels the previous run in flight; content lands with zero terminal evaluation and the surviving run misattributes one verdict across several merged tips.

**Why this priority**: This is the direct honesty hole — main content that was never evaluated is reported under a verdict computed for a different tip. It violates the release-authority invariant at its root.

**Independent Test**: Land a burst of ≥3 commits on the merged main tip; confirm via `gh run list --branch main` that each tip has its own non-cancelled CI run and no tip's run was cancelled by a later push.

**Acceptance Scenarios**:

1. **Given** three commits landing on `main` within one CI cycle, **When** the pushes trigger CI, **Then** each commit's CI run reaches a terminal conclusion and none is `cancelled` by a subsequent main push.
2. **Given** a single PR ref receiving two pushes, **When** the second push triggers CI, **Then** the first (now-stale) PR-ref run is still cancelled — PR self-coalescing is unchanged.

### User Story 2 - The fleet-verdict fan-out per tip is bounded (Priority: P1)

A landed tip must produce a **bounded, single coalesced** `CI Fleet Verdict`, not dozens. Today `ci-fleet-verdict.yml` triggers on eight upstream workflows × three `workflow_run` event types with no top-level throttle, and `report-main` queues rather than coalesces — the current main tip alone accumulated **60 fleet-verdict runs** (LIVE_CI_GROUNDING). This is what makes "prove a landed main tip green in bounded time" impossible.

**Why this priority**: Without a cap, lever 1a (which *adds* concurrent main runs) multiplies the storm. The two are coupled and must land together; an uncapped fan-out means a landed tip cannot prove itself in bounded runner time.

**Independent Test**: On the merged main tip, count `CI Fleet Verdict` runs attributable to one landed SHA (`gh run list --workflow "CI Fleet Verdict"`); expect ≈1 coalesced verdict, not dozens.

**Acceptance Scenarios**:

1. **Given** one landed main tip, **When** its upstream workflows complete, **Then** the redundant fleet-verdict triggers coalesce to a single surviving verdict run for that tip.
2. **Given** a burst of upstream `workflow_run` events for one tip, **When** they fire, **Then** only terminal (`completed`) events start a verdict evaluation; `requested`/`in_progress` transitions do not.
3. **Given** a main-verdict run superseded by a newer one for the same tip, **When** the newer run starts, **Then** the queue coalesces to the survivor and the survivor re-reads current state.

### User Story 3 - Coupling safety: no dropped verdict, no widened green path, no broken classifier (Priority: P1)

The cap and dedup must never drop the **last-writer verdict** a landed tip needs (that would be a false-red / permanent wedge), must never widen the **green path** (the aggregate fail-closed guard stays untouched), and must leave the shipped #4208 `router_gate.py` classifier correct under the changed `cancelled`-input distribution that lever 1a produces.

**Why this priority**: Both bounding failure modes (false-green and false-red/permanent-wedge) are worse than the status quo. This story pins the invariants that keep Stage 1 honest.

**Independent Test**: The existing never-green tests (`tests/ci/test_fleet_verdict.py::test_truncated_files_and_deferred_pr_never_green`) and the aggregate fail-closed guard stay green; a dedup unit test proves the survivor re-reads and never drops the terminal verdict; the #4208 router-gate classifier is re-verified on the merged main tip.

**Acceptance Scenarios**:

1. **Given** a coalesced survivor verdict run, **When** it evaluates, **Then** it re-reads current evidence and posts the terminal verdict rather than dropping it.
2. **Given** this stage's diff, **When** the aggregate source-eligibility and fail-closed guard are inspected, **Then** they are unchanged (source-eligibility is Stage 2).
3. **Given** the new main-concurrency policy, **When** a main run is *not* cancelled that previously would have been, **Then** the #4208 router-gate classifier still produces the correct pass/block verdict for the resulting job set.

### Edge Cases

- **Docs-only / no-op push to `main`**: still receives its own terminal evaluation; it is not silently cancelled by a following push.
- **Fleet-verdict trigger storm on one tip**: coalesces to a single survivor; the survivor always re-reads current upstream state, so coalescing loses no verdict information.
- **`report-main` queue growing faster than it drains**: prevented by coalesce-with-survivor; the last writer for a tip wins and re-reads state.
- **Interaction with Stage 3 (terminal-cancel verdict, #4430)**: Stage 1's dedup must remain compatible with a future non-`running` terminal class — coalescing must not become a new suppression path for the `infra-error` verdict Stage 3 will add. Stage 1 preserves the existing running-only dedup guard and does not broaden it.
- **A `cancelled` main run still occurring** (e.g. a genuine timeout-kill, #4399): must remain classifiable by #4208's router-gate; Stage 1 only removes *push-cancellation-cascade* cancels, not all `cancelled` states.
- **PR refs**: entirely unaffected — per-PR concurrency keys keep self-coalescing exactly as before.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Per-SHA main concurrency | As the release-authority contract, I want each push to `main` keyed on its own commit SHA so no landed tip's CI run is cancelled by a later main push and every tip gets its own terminal evaluation. | High | Open |
| FR-002 | PR-ref concurrency preserved | As a PR author, I want per-PR-ref concurrency to keep self-coalescing (`cancel-in-progress: true` per PR ref) unchanged, so only main-key behaviour changes. | High | Open |
| FR-003 | Top-level fleet-verdict concurrency | As the release-authority contract, I want a top-level per-tip `concurrency:` block on the fleet-verdict workflow (per-SHA for main, per-PR for PR heads) so redundant triggers coalesce to a single surviving evaluation. | High | Open |
| FR-004 | Trim workflow_run event types | As a maintainer, I want the fleet-verdict `workflow_run` `types:` trimmed to `[completed]` only, since a verdict is a function of terminal upstream state and `requested`/`in_progress` transitions are pure fan-out with no verdict value. | High | Open |
| FR-005 | report-main coalesce-with-survivor | As the release-authority contract, I want the `report-main` serialization to coalesce to a surviving run (rather than queue with `cancel-in-progress: false`) so the main-verdict queue cannot outgrow its drain; the survivor re-reads current state. | High | Open |
| FR-006 | Dedup never drops the last writer | As the release-authority contract, I want the dedup in `fleet_verdict.py`/`fleet_main.py` kept and reinforced so the surviving run always re-reads current evidence and never drops the terminal (last-writer) verdict a landed tip needs. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Green path not widened | The aggregate fail-closed guard (`ci-aggregate.yml`, "reconciled coverage set is INCOMPLETE … refusing", post-#4360-B) is untouched by this stage; no PR-head partial-shard set may satisfy the main ledger. Measured by: existing never-green and aggregate-guard tests remain green, and the stage diff touches no source-eligibility or guard logic. | Reliability | High | Open |
| NFR-002 | No dropped last-writer verdict | Coalescing/dedup must never drop the terminal verdict for a landed tip; a landed tip always yields exactly one terminal verdict (no false-red / permanent wedge). Measured by: a dedup unit test asserting the survivor re-reads and posts; on the merged main tip, every landed tip carries exactly one terminal fleet verdict. | Reliability | High | Open |
| NFR-003 | Cross-coupling verified, linters clean | The #4208 `router_gate.py` classifier is verified to produce correct verdicts under the new (fewer-`cancelled`) main-run distribution 1a produces; `actionlint` and `shellcheck` report 0 findings on every touched workflow. Measured by: 0 actionlint/shellcheck findings; a merged-main-tip observation that the router-gate verdict is correct. | Reliability | High | Open |
| NFR-004 | Coupled levers land together | Levers 1a and 2a land in the **same** stage/PR; 1a is never merged without 2a (1a alone worsens the fan-out storm). Measured by: the single Stage-1 PR contains both the router concurrency change and the fleet-verdict cap. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Staged rollout, operator-merged | Stage 1 of 3; lands as its own PR to upstream `main`, **operator-merged** (never a push to `main`, never `spec-kitty merge --push`); acceptance is verified on the **merged main tip**, not the PR head. | Technical | High | Open |
| C-002 | YAML provable only by shape + dedup tests | The concurrency/fan-out changes are config-level YAML, not unit-testable in pytest; they are provable only by workflow-lint / golden-YAML shape assertions plus dedup unit tests in `tests/ci/`. The spec and PR must state this honestly and must not pretend a pytest test covers the YAML change. | Technical | High | Open |
| C-003 | Consume, do not modify, adjacent surfaces | The #4360-B reconciler/guard (`scripts/ci/reconcile_shards.py` + aggregate guard) and the #4208 `router_gate.py` classifier are **consumed, not modified** by this stage. Source-eligibility is Stage 2 (#4360-A); terminal-cancel verdict is Stage 3 (#4430). | Technical | High | Open |
| C-004 | jobs-API path is plural | Any jobs-API interaction uses the `/attempts/` (plural) path, not `/attempt/` (a singular path 404s — corrected mid-#4515). | Technical | Medium | Open |
| C-005 | ADR is the governing authority | This mission references ADR `2026-09-15-1` (PR #4534) as the settled authority; it does not re-author or re-litigate the ADR. Any consumer of the fleet-verdict surface this ADR did not name is a finding against the ADR, not a licence to improvise. | Technical | High | Open |

### Key Entities

- **`ci-router.yml`**: the path-router workflow whose `push: [main]` concurrency group currently cancel-cascades main runs. Owns lever 1a.
- **`ci-fleet-verdict.yml`**: the per-tip verdict workflow with no top-level concurrency and an over-broad `workflow_run` trigger; `report`/`report-main` jobs carry per-scope groups. Owns lever 2a's YAML surface.
- **`scripts/ci/fleet_verdict.py` / `scripts/ci/fleet_main.py`**: the PR and main verdict reporters — `classify()` and the running-dedup live here; lever 2a reinforces the dedup on this surface (the terminal-cancel *class* is Stage 3).
- **Fleet-verdict comment ledger**: the `[ci] <state> @<sha>` PR/commit comments the reporters post and dedup against.
- **`router_gate.py` (#4208, consumed)**: the shipped router-gate classifier whose input distribution 1a changes; verified, not modified.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the merged main tip, one landed tip produces a bounded, single coalesced `CI Fleet Verdict` run (down from ~60), measured via `gh run list --workflow "CI Fleet Verdict"`.
- **SC-002**: During a merge burst on `main`, **zero** tips land without a terminal CI evaluation (no `cancelled`-by-later-push runs), measured via `gh run list --branch main`.
- **SC-003**: The #4208 router-gate classifier produces the correct pass/block verdict under the new main-run distribution — no new false-red or false-green observed on the merged main tip.
- **SC-004**: `actionlint` and `shellcheck` report **0** findings on every workflow touched by this stage.
- **SC-005**: All pre-existing never-green and aggregate fail-closed guard tests remain green; a new dedup unit test proves the survivor re-reads current state and never drops the terminal verdict.
