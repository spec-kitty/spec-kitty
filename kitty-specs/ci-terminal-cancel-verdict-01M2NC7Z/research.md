# Phase 0 Research: CI Terminal-Cancel Verdict (infra-error)

**Mission**: `ci-terminal-cancel-verdict-01M2NC7Z` · **ADR**: `docs/adr/3.x/2026-09-15-1` Axis 4 (#4430) · **Scope**: 4a + 4b.
**Method**: pre-spec 2-lens squad (reviewer-renata never-green/precedence; debugger-debbie head-release/live-evidence), profile-loaded, read-only; orchestrator verified the live bug + #4430 closure. Full record: `work/ci-honesty-4437/stage3-squad-adjudication.md`. Zero `[NEEDS CLARIFICATION]`.

## D-01 — Premise verified (ADR accurate this time)
Bug LIVE on `main` (`fleet_verdict.py:89` red-set lacks `cancelled`; no classify commit since the ADR). #4430 CLOSED COMPLETED at the ADR-ratification timestamp = a *process* closure, not a landed fix. Cancellation frequent (22/80 recent `ci-modules.yml` runs cancelled). → Stage 3 genuinely needed; reopen #4430 at PR time.

## D-02 — 4a classify precedence (settled; reviewer caught a real flaw)
The orchestrator's first default (gate on `len(present)==len(runs)`) was WRONG: `:93` rejects only *absent* runs, so a present-but-`in_progress` run slips through → premature `infra-error` while a gate still flies. **Corrected: the `infra-error` branch must gate on `all(r.status=="completed" for r in present)`.** Precedence (each returns immediately): red (`:89`) → deferred (`:91`) → incomplete (`:93`) → **terminal-cancel NEW (between :94/:95): `all present completed AND any cancelled` → `infra-error`** → green/running (`:95`, unchanged). Keyed on `conclusion=="cancelled"` specifically (not "not-green") so `skipped` stays `running` and `timed_out` stays `red`.
- **Rationale:** the class must be never-green by construction (needs ≥1 cancelled), never premature (all-completed), never infra-wash a red (after :89), never override deferred (after :91).
- **Alternatives rejected:** "complete-but-not-green → infra-error" (regresses `skipped→running`, `test_fleet_verdict.py:176`/`test_fleet_main.py:113`); gating only on completeness-of-count (premature-fire, INV-2).

## D-03 — Head-release mechanism (verified end-to-end)
`classify → evidence["state"]` → dedup `report():325-331`. The running-guard `:329` (`state=="running" and latest.startswith("[ci] running @")`) suppresses the repost today. `infra-error` makes `:329` False → fresh `[ci] infra-error @head` posts (comment_body `:279` emits `[ci] {state} @{head}` generically) → head released, never-green. Recognition regex `:323` already lists `infra-error` → subsequent identical events fingerprint-dedup. **Zero dedup/YAML/regex change for 4a.**

## D-04 — Main-path coherence is free
`fleet_main.py:81` reuses `classify`; `body()` reuses `comment_body`. P0 gate `:121` keys on `state != "red"` → a cancelled `main` run emits `infra-error` and creates **no P0 incident** (correct — infra-error ≠ code-red). `fleet_main.py` itself needs **no code edit**; only its test (`test_fleet_main.py:109`, which pins `cancelled→running`) must migrate (split: cancelled→infra-error + no-P0; skipped/None→running). ADR under-scoped this test.

## D-05 — 4b stale-running sweep (design)
- **Why needed with 4a:** 4a fixes the cancelled-*producer* case. It cannot help when *no reporter fired* — a cancelled *reporter* run (Stage-1 "survivor-no-successor" soft-wedge) or the cancelled-`main` residual. 4b is the reactive safety net.
- **Decision — shape:** a new **pure detector** `scripts/ci/stale_running_sweep.py` (`find_stale_running(heads, comments, runs) -> list[stale]`), `gh` at the edge (mirrors `select_source_artifacts.py`/`source_eligibility.py`). Detect: for each open PR head (and the `main` head), latest `[ci]` verdict is `running @<head>` AND every required run for `<head>` is terminal (`completed`, incl. `cancelled`) → stale.
- **Decision — surface (watch item, NOT authority):** post/update a single **de-duplicated `[ci-sweep]`-namespaced** watch comment (NOT a `[ci] <state> @head` verdict — that format is the reporter's authority) + a workflow-log annotation. Idempotent by fingerprint (a re-run must not repost). It **never** posts green/red, never edits the reporter's comments, never re-triggers CI (C-003/FR-008).
- **Decision — host:** a scheduled + `workflow_dispatch` step; **candidate = `ci-nightly.yml`** (the existing night-watch surface) OR a small dedicated `ci-stale-running-sweep.yml`. **[PLAN POINT-CUT — confirm with operator]** default: add a job to `ci-nightly.yml` for minimal surface, unless a dedicated cadence is wanted.
- **Reuse:** the `[ci] <state> @<head>` recognition regex + the `GitHub` client from `fleet_verdict` by **import** (read-only; do not edit `fleet_verdict.py` from WP02).
- **Alternatives rejected:** auto-release / re-trigger (violates ADR "release in-CI, not by a sweep"; risks green/red-wash); a per-PR trigger (it's a backstop sweep, not a per-event reporter).

## D-06 — Non-fakeable test strategy
The strand-release must be proven via the **full `report()` path** (seed stale `[ci] running @head` + cancelled gate; assert today `not api.posts` (suppressed), after-fix `posts[0].startswith("[ci] infra-error @head")`) — a bare `classify(...)=="infra-error"` proves classification, not *release*. Template = `test_fleet_verdict.py:242`. Plus: flip pinned `:175`/`:319` (cancelled→infra-error), the 5 invariant tests (INV-1..5), the `test_fleet_main.py:109` split, and the incident-append-doesn't-escalate test. 4b: red-first detector tests (stale / not-stale-terminal-latest / not-stale-in-flight / idempotent) + an execution-grounded workflow wiring guard. Honest: the classify + report paths are fully unit/`report()`-provable offline; the sweep *wiring* is golden-YAML/execution-guard-provable only (state this, don't pretend a unit test covers the YAML).

## D-07 — Supply-chain / boundaries
No new dependencies (stdlib + existing `gh`); DIRECTIVE_051 N/A (explicit no-op). Boundaries: do NOT touch `router_gate.py`'s separate `classify` (C-001); do NOT change Stage-1 concurrency levers or the dedup guard/regex (C-002); the sweep never auto-releases (C-003).

## Adversarial evidence ledger (per `contracts/adversarial-evidence-contract.md`)
| Finding | Disposition |
|---|---|
| Orchestrator's `len(present)==len(runs)` default fires infra-error prematurely on cancel+in_flight (reviewer HIGH) | **changed** → D-02 gate on `all present completed` |
| Must key on `cancelled` not "not-green" (else skipped regresses) (reviewer HIGH) | **accepted** → D-02, FR-004 |
| infra-error after red (else infra-wash a failure) (reviewer MED) | **accepted** → D-02, INV-3 |
| `test_fleet_main.py:109` also pins cancelled→running, ADR under-scoped (reviewer MED) | **accepted** → D-04 test in-scope |
| Strand-release must be proven via full report(), not bare classify (both lenses) | **accepted** → D-06 |
| #4430 closed-COMPLETED but bug live (orchestrator) | **accepted** → D-01, reopen at PR |
| 4b needed for cancelled-reporter/cancelled-main residual (debugger) | **accepted** → D-05 (operator folded 4b in) |
| body() red-P0 suffix on infra-error tip; comment_body no infra line; docstring (reviewer LOW) | **accepted** → FR-006 honesty polish |
No contested finding silently dropped.
