# Data Model: CI Aggregate Source-Eligibility

No persistent storage. These are the in-process value objects of the pure decision `resolve_source(...)`. All are plain, immutable data (dataclasses or tagged dicts — implementer's call; the contract is the shape + semantics).

## Inputs

### TriggerMeta — the triggering `workflow_run`'s provenance
| Field | Type | Source | Notes |
|---|---|---|---|
| `event` | `str` | `github.event.workflow_run.event` | `push` \| `pull_request` \| `workflow_dispatch` \| other |
| `head_branch` | `str` | `github.event.workflow_run.head_branch` | the source run's branch (PR branch for PR-head; `main` for push-main) |
| `conclusion` | `str` | `github.event.workflow_run.conclusion` | `success` \| `failure` \| … (the trigger can be a `failure` — `collect.if` fires on it) |

### CandidateRun — one entry from `gh run list --json databaseId,conclusion,headBranch,event,...`
| Field | Type | Notes |
|---|---|---|
| `databaseId` | `int` | resolved into `run-id` when eligible |
| `conclusion` | `str` | only `success` is an eligible backfill source (FR-005 / LEAK-A) |
| `headBranch` | `str` | must be in `{source_branch, default_branch}` (FR-005 / LEAK-B) |
| `event` | `str` | (carried for future assertions; not required for v1 decision) |

`candidates` are already scoped by the workflow to the `ci-modules.yml` workflow; the pure function applies the success + branch filters (it does not trust the query alone).

## Output — `SourceDecision` (a tagged union; exactly one variant)

| Variant | Carries | `run-id` output | `eligibility` slug | When |
|---|---|---|---|---|
| `EligibleSource` | `run_id: int` | `<run_id>` | `eligible-source` | eligible provenance + a `success` run on `{source ∪ default}` |
| `NoEligibleSource` | `reason: str` | `""` | `no-success-source` | eligible provenance but no `success` candidate |
| `NotAMainSource` | `reason: str` | `""` | `pr-head-trigger` \| `failed-trigger` | `event=pull_request` or `conclusion=failure` |
| `NoFallback` | — | `""` (step skipped upstream) | `dispatch-no-fallback` | `event=workflow_dispatch` |

### Invariants (testable — map to reviewer INV-*)
- **INV-A (success-only)**: no `EligibleSource` ever carries a `conclusion != success` run. (FR-005)
- **INV-B (branch-scope)**: no `EligibleSource` ever carries a `headBranch ∉ {source, default}` run. (FR-005)
- **INV-C (never silent)**: every variant maps to a non-empty `eligibility` slug; `run-id=""` always co-occurs with a named slug. (FR-003)
- **INV-D (output boundary)**: `main()` writes ONLY `run-id` + `eligibility`; never `complete`/`missing`/`coverage`. (C-003)
- **INV-E (no hard-exit on no-source)**: `NoEligibleSource`/`NotAMainSource`/`NoFallback` exit 0 with an empty `run-id`; only *malformed input* raises. (NFR-004 — reconcile stays the fail-closed terminus)
- **INV-F (dispatch)**: `workflow_dispatch` → `NoFallback`, no ledger query attempted. (FR-006)

### State transitions
None — a pure function; no lifecycle, no persisted state.
