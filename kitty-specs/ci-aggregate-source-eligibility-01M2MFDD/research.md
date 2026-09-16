# Phase 0 Research: CI Aggregate Source-Eligibility (main-verdict provenance)

**Mission**: `ci-aggregate-source-eligibility-01M2MFDD` · **ADR**: `docs/adr/3.x/2026-09-15-1` Axis 3a (#4360-A) · **Scope**: B (honestly re-scoped)
**Method**: pre-spec adversarial brownfield squad (architect / debugger / reviewer, profile-loaded, read-only) + a focused consumer-trace investigation, each verified independently by the orchestrator against the live tree/API. Full squad record: `work/ci-honesty-4437/stage2-squad-adjudication.md`.

All `[NEEDS CLARIFICATION]` from spec = **0**. The one central open question is resolved below.

---

## D-01 — The ADR's #4360-A mechanism is falsified post-Stage-1 (verified)

- **Decision**: Write the spec/plan against the LIVE mechanism, not the ADR prose; annotate the ADR (FR-007).
- **Rationale**: Verified directly — `grep report-main .github/workflows/ci-modules.yml` → 0 hits (no such legs exist); `gh run list --workflow ci-modules.yml --branch main` → main runs conclude `success` (6/8 recent; 2 `cancelled` are pre-Stage-1); the `--branch main` fallback query *finds and downloads* a run. The refusal is from `reconcile` (SELECTED-but-undelivered shards), not an empty query.
- **Alternatives considered**: Trust the ADR prose verbatim — rejected (DIRECTIVE_010 spec fidelity; would target a mechanism that no longer occurs).

## D-02 — The `main`-labelled aggregate failure is COSMETIC; no main-verdict consumer reads it (verified) — **resolves the central open question**

- **Decision**: Treat #4360-A as a **doctrine-record error + untested provenance-blind source surface**, NOT a release-authority correctness bug. Keep the fix inside source-selection; do **not** add job-flow/attribution surgery, do **not** relabel or suppress the PR's own correct red.
- **Rationale (verified linchpins)**:
  - `scripts/ci/fleet_main.py:50` — main verdict derived from `actions/runs?head_sha={head}&event=push&branch=main`; a `workflow_run`-event aggregate is invisible to it.
  - `scripts/ci/fleet_verdict.py:395-405` — an aggregate trigger is resolved *back to its source CI Modules run* (`api.request("actions/runs/{source_id}")`), and `main=true` is tested on **that source run's** `event`/`head_branch` (line 405), not on the aggregate's `headBranch=main` label. A PR-head aggregate → source `event=pull_request` → PR path, never `main=true`.
  - Branch protection: `repos/spec-kitty/spec-kitty/branches/main/protection` → required checks = `["Clean install verification"]`, `strict:false`. `CI Aggregate` is **not** required.
  - The failed aggregate run *is* the PR's own correct red (its coverage was incomplete); it is merely displayed under a `main` label GitHub assigns to `workflow_run` handlers and that cannot be relabelled.
- **Consequence**: FR-004/NFR-002 were re-scoped from "remove a consumed main false-red" (empty goal) to "correct, provenance-honest source resolution + verified provenance classification." The provenance rule is **defense-in-depth + honesty**.
- **Alternatives considered**: (a) Build job-flow gating to stop the run concluding failure — rejected: it is the PR's correct red; suppressing it would hide a real PR coverage gap (false-green risk) and touch `collect.if` (C-002 boundary). (b) Drop the mission — rejected: the tested provenance surface is real, ratified value (the ADR's named red-first seam).

## D-03 — Seam placement: a NEW module `scripts/ci/source_eligibility.py` (unanimous squad)

- **Decision**: New `scripts/ci/source_eligibility.py` + `tests/ci/test_source_eligibility.py`. Do **not** extend `aggregate_source.py`.
- **Rationale**: `aggregate_source.py::prepare_source` is single-run provenance validation + git materialization of the *one trusted triggering run* (no ledger query); source-eligibility is a **git-free, cross-run ledger decision keyed on trigger provenance** — a different responsibility, different inputs, different failure vocabulary (DIRECTIVE_001/031). The established #4360-B extraction pattern (`reconcile_shards.py`) is one module + one pure decision function + its own test file.
- **Template**: `scripts/ci/select_source_artifacts.py` — pure `select_artifacts(source, jobs, artifacts)`, `gh api | jq` at the workflow edge, `key=value` to `GITHUB_OUTPUT`, named `ValueError`s. NOT `test_aggregate_source.py`'s subprocess git-fixture (a git repo cannot represent `gh run list` results).
- **Alternatives considered**: Extend `aggregate_source.py` — rejected (overloads a crisp bounded context; folds a ledger query into a git-materialization module).

## D-04 — Provenance rule + eligibility contract

- **Decision**: A pure decision `resolve_source(trigger, candidates, default_branch) -> SourceDecision` where:
  - `trigger.event == "workflow_dispatch"` → `NoFallback` (exact-source-only; preserve the existing `github.event_name != 'workflow_dispatch'` gate).
  - `trigger.event == "pull_request"` OR `trigger.conclusion == "failure"` → `NotAMainSource(reason)` — never resolves a `main` source run-id.
  - else (`event == "push"` main lineage / eligible PR source-branch): resolve the most-recent `status == "success"` run on `{source_branch}` then `{default_branch}` → `EligibleSource(run_id)`; none → `NoEligibleSource(reason)`.
- **Rationale**: Encodes D-02's provenance honesty as a pure predicate; keeps the success-only + branch-scope filters (reviewer LEAK-A/B) load-bearing; every terminal is *named*, never a silent `[]` (FR-003).
- **Output contract**: helper writes ONLY `run-id=<id|"">` + `eligibility=<slug>` (a `::notice::`/`::error::`-style named reason) to stdout/`GITHUB_OUTPUT`. It NEVER writes `complete`/`missing`/`coverage` (C-003 / reviewer INV-4). It does NOT hard-exit on no-source — it emits empty `run-id` + reason and lets `reconcile` remain the fail-closed terminus (reviewer INV / NFR-004; a hard-exit would make the diagnostic-rich `:298` shard-list message unreachable).

## D-05 — Non-fakeable test strategy

- **Decision**: (a) Red-first unit tests over injected inputs for all six named branches (NFR-003). Assert the **rejections** (red run rejected, unrelated-branch rejected, pr-head named not-a-main-source), not a happy string. (b) An execution-grounded wiring guard mirroring `tests/ci/test_aggregate_source.py:146-153,309-327`: load `ci-aggregate.yml`, select the `last-success` step, assert its `run:` invokes `scripts/ci/source_eligibility.py` (not inline `gh run list`), execute the extracted block against a stubbed no-eligible-source inventory, assert `run-id="" + named slug`, and assert the fail-closed guard step's `run:` is byte-unchanged (reviewer INV-6).
- **Rationale**: A grep-only guard is fakeable; a construction-asserting unit test proves nothing (reviewer's biggest anti-laziness risk). Execution + rejection-assertion is the non-fakeable contract.
- **Honesty about coverage**: the YAML wiring itself is provable only by the golden-YAML/execution guard + workflow-lint, NOT by a unit test — stated plainly (ADR lines 310-314). Only the pure decision is unit-testable red-first.

## D-06 — #4334 sonar-pr cross-coupling: RESOLVED, no coupling (was [HYP])

- **Decision**: Carry a light regression check; no design change needed.
- **Rationale**: `sonar-pr` reads `out/aggregate/source/source.json` written by `aggregate_source.py::prepare_source` from the *current* run — independent of the fallback source query. It is `continue-on-error`, excluded from `aggregate-gate`, and skips-with-`::notice::` when incomplete. Live-proven **skipped, not failed** in aggregate run `35062966456`. A source-eligibility change can at most flip run-vs-skip, which it already tolerates.

## D-07 — Supply-chain / dependency posture

- **Decision**: No new dependencies. The helper uses only the Python stdlib (`argparse`, `json`, `re`, `sys`) exactly like `select_source_artifacts.py`; `gh`/`jq` already exist in the workflow. Registry/lifecycle-script/LTS checks (DIRECTIVE_051) are **N/A** — nothing is added, upgraded, or removed. Recorded per the plan supply-chain step; silence is not compliance, so this is an explicit no-op.

---

## Adversarial evidence ledger (per `contracts/adversarial-evidence-contract.md`)

| Finding (source lens) | Disposition |
|---|---|
| ADR premise falsified — no report-main legs / main concludes success / fallback succeeds (debugger, verified) | **accepted** → D-01, FR-007, honest re-scope |
| The `main`-labelled failure is cosmetic; no consumer reads it (consumer-trace, verified) | **accepted** → D-02, spec re-scope, operator-ratified |
| Seam = new module, not extend aggregate_source.py (architect, unanimous) | **accepted** → D-03 |
| Green-path leaks LEAK-A/B/C (drop `--status success` / widen branch set / legacy `selected is None`) (reviewer) | **accepted** → D-04 success-only + branch-scope filters; INV-1/4 preserved |
| Helper must not hard-exit; reconcile stays fail-closed terminus (reviewer) | **accepted** → D-04 output contract, NFR-004 |
| Wiring guard must execute + assert rejections, not grep/construction (reviewer) | **accepted** → D-05 |
| #4334 sonar-pr [HYP] | **changed** → resolved to no-coupling (D-06) with live proof |
| "main-eligible push source exists, contingent on Stage 1" (architect) | **accepted** as context (D-02 Assumptions); not a blocker — Stage 1 is merged |

No contested finding was silently dropped.
