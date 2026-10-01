# Contract: skip-if-green on ready-for-review (`scripts/ci/green_match.py`)

**Requirements**: FR-011, SC-005 · **Design**: research.md D-15, D-16, R3 §1 · **Decision Moments**: 01M3TZHMR2CVAY2FNHSGNJJYSR, 01M3V02AV3002PNZYY8HFJ6DQF, 01M3V1F7JYH2YNZCM4TAHB3Q3P

## Tested key

`(workflow file, PR number, head SHA, base SHA)` where base SHA is the **first parent of the merge commit the run actually tested** (bound via the commits API; the second parent must equal the PR head). The Actions API's `pull_requests[].base.sha` is NOT used: it reports the PR's current base, not the tested one.

Every executing `pull_request` run uploads a zero-content artifact `ci-tested-key-pr<N>-base-<sha>`. A run that skipped uploads `ci-green-match-run-<id>-attempt-<n>` instead and is never itself a match candidate.

## Decision (`decide`, pure)

| Condition | Result |
|---|---|
| event ≠ `pull_request` (push, dispatch, workflow_call, schedule) | Run |
| merge ref cannot be bound to a tested key | Run |
| action ≠ `ready_for_review` | Run (records tested key) |
| run attempt ≠ 1 (re-run) | Run — re-running a skip run forces execution |
| a completed, successful, same-workflow `pull_request` run for the head SHA carries a non-expired `ci-tested-key-pr<N>-base-<base>` artifact | **Skip**, naming the matched run (`::notice::` + step summary) |
| otherwise (no candidate, prior failed/cancelled/in progress, moved base) | Run |
| any lookup error (HTTP, network, JSON, missing key) | Run, with `::warning::` |
| A4: a skip marker from an EARLIER attempt of the same run (re-run all jobs) | ignored — markers bind to their attempt (`created_at >= run_started_at`); the re-run executes and Aggregate does not re-point |

Outputs: `skip`, `reason`, `marker`, `matched-run-id`, `matched-run-attempt`, `matched-run-url`.

Transport: `gh api` (testable through the fake-`gh` harness); `bind_tested_base(parents, head)` lives here and is reused by `aggregate_source.py`.

## Workflow integration

- Router `changes`, Packs `changes` and CI Modules `generate-matrix` each run the helper first (permission `actions: read`); on skip they skip their path-filter step so all path-gated jobs skip and the required gate (`router gate`, `CI Modules gate`) reports success. No job `if:` or `needs:` changes.
- CI Aggregate `collect` gains a first `effective-source` step: if the source run carries a green-match marker, it re-points every source-run reference to the matched CI Modules run after re-verifying head SHA, workflow, event, success and tested identity from the matched run's immutable merge ref; on any mismatch `collect` fails ("re-run CI Modules to execute") — never a silent empty-selection green. Step names and env var names are preserved; `run-name` stays bound to the skip run so Fleet Verdict finds it.
- Sonar's informational per-change upload may repeat on a skip run (accepted).

## Verification

- Parametrised unit tests over recorded API fixtures cover every row above (15 negative cases) and the Aggregate `effective-source` path.
- Live verification of the Aggregate half is a post-merge follow-up (it runs from `main`'s workflow file via `workflow_run`).
- Amendment to ADR 2026-09-23-1 records that a required gate may pass on matched prior-run evidence under exactly this key.
