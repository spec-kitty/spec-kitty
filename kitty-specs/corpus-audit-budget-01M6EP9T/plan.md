# Implementation Plan: Calibrate the full-corpus recovery test budget

**Branch**: `issue-5716-corpus-audit-budget` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

## Planning Answers

- The existing test is a correctness and historical-integrity contract, not a throughput benchmark. Its eleven CLI audits and their healthy controls must stay.
- There is no observed completed CI total yet. The first implementation phase is therefore a diagnostic measurement, not a guessed permanent timeout.
- The user authorized separate work to unblock #7071; no merge bypass or change to that PR's reviewed fixture is authorized or needed.
- A single work package owns the measurement and resulting correction because the second phase depends on the first phase's evidence and touches the same behavioral contract.

## Summary

Create a temporary, push-triggered hosted-runner diagnostic job restricted to `issue-5716-corpus-audit-budget` and changes to its own workflow file. Invoke only the existing failing node with a bounded outer timeout and the unchanged inner subprocess boundary. A new dispatch-only workflow is not registered on main and is unsuitable here; do not use a PR trigger or open a PR until the file is removed. Record source/runner metadata, overall duration and timing records for real audits/CLI calls, corpus construction, inventories, recovery and gates; distinguish nested timings rather than double-counting them. Keep all failures and artifact links. Record the compared main SHA and the source diff for `src/`, `tests/` and `pytest.ini` (expected empty during measurement). Obtain independent review of the evidence before selecting the smallest justified final correction. Remove disposable measurement wiring from the final product diff and retain its immutable CI run reference and results in Mission research/PR evidence.

If measurement exposes a genuine failure or cannot complete within the bound, stop calibration. A broad production-audit optimization, scheduling change, or relaxed integrity contract requires a new scope decision, not a silent expansion.

## Technical Context

**Language/Version**: Python 3.11+ for the test; GitHub Actions YAML for temporary measurement wiring.  
**Primary Dependencies**: existing pytest, pytest-timeout, uv, real spec-kitty CLI and Git; no new package.  
**Storage**: pinned Git corpus objects, throwaway filesystem fixture, CI logs/artifacts.  
**Testing**: the exact `tests/upgrade/test_mission_corpus_recovery.py::test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes` node; existing fast siblings and relevant named gates only after edits.  
**Target Platform**: the same `ubuntu-24.04` hosted class as the failing module shard.  
**Project Type**: existing CLI test harness.  
**Performance Goals**: record the true completion time and all eleven audit durations before choosing bounded headroom; no new product performance promise.  
**Constraints**: diagnostic outer limit <=900 seconds, job <=25 minutes; existing per-CLI 180-second bound unchanged unless new evidence explicitly justifies separate correction.  
**Scale/Scope**: one historical-corpus contract (423 immediate directories, about 228 MB); no full local architectural/integration/nightly sweep.

## Charter Check

- One canonical test and corpus: no copied contract or second behavioral oracle.
- Red-first evidence is the same node's documented current-main 240-second failure; the diagnostic changes only instrumentation/time permitted for measurement.
- No skips, quarantine, xfails, retry plugin, retry-to-green, broad global budget change, removed audit, membership check or healthy control.
- All artifact authoring remains in the Mission's owned checkout and topic branch. A tracer CLI that drops owned-checkout scope is reported rather than bypassing protected-main policy.
- The final diff and any test-local timeout are independently reviewed against recorded hosted evidence.

## Project Structure

### Mission artifacts

- `spec.md`: scope and acceptance criteria.
- `plan.md`: this plan.
- `research.md`: evidence, run URLs, phase durations, budget decision and unresolved questions.
- `tasks.md` and `tasks/WP01-corpus-budget.md`: one sequentially executed package.
- `traces/`: approach, design decisions and tooling friction.

### Existing and temporary code surfaces

- `tests/upgrade/test_mission_corpus_recovery.py`: existing contract, possible final narrowly scoped correction.
- `.github/workflows/corpus-budget-diagnostic.yml`: temporary one-node diagnostic job, push-triggered on this branch and its own path only, no secrets and contents-read only. Check out the repository before resolving the local warmup action, just as `module-tests.yml` does. Reuse warmup in `pr` mode, preserve full history, and match the shard's derived package coverage flags for comparability. Use an explicit basetemp and override retention to `all` so successful runs retain their CLI evidence; upload only logs/metrics/JUnit/CLI reports, never the reconstructed corpus.
- A temporary pytest instrumentation plugin created in the job's runner temp directory: wraps the real audit/CLI only to time it and preserves return values and exceptions; not a production module or permanent test dependency.

## Implementation Concern Map

### IC-01 — Evidence collection

- **Purpose**: complete the exact existing contract on its CI runner class within a bounded diagnostic window.
- **Relevant requirements**: FR-001, FR-003, NFR-001, NFR-003.
- **Affected surfaces**: temporary diagnostic workflow; runner-temporary plugin; Mission research evidence.
- **Sequencing/depends-on**: none.
- **Risks**: cold setup, missing historical Git objects, altered source context, inner subprocess stall. Fetch complete history, record source/environment and distinguish setup from test timing.

### IC-02 — Calibrated final correction

- **Purpose**: correct only a measured execution-budget mismatch or proven localized bottleneck while retaining all integrity controls.
- **Relevant requirements**: FR-002, FR-003, NFR-002, SC-002.
- **Affected surfaces**: existing corpus test and evidence; remove temporary workflow once its work is complete.
- **Sequencing/depends-on**: IC-01 and independent evidence review.
- **Risks**: guessing a larger timeout from a censored failure, hiding a slow regression, or widening scope into production semantics. Do not select a value before measurement; justify explicit headroom.

## Validation and Review

Before any full-corpus run, inspect the already-recorded CI results. Diagnostic runs invoke one named node, serially, with no retries. The temporary workflow is not a new permanent pytest workflow: it would fail the existing workflow-set equality gate while present. Do not expand the workflow allowlist; resolve the branch/trigger sequencing before dispatch, and remove the temporary workflow before the final PR is opened. Test-only edits are checked with the existing owning test and focused gates, not a full heavy suite. A local recurrence of the documented early inner-180-second stall is retained and investigated as separate evidence, never sized into the CI budget; hosted validation of the complete corrected contract remains mandatory. Any new failure signature is a finding, not automatically environmental. Reviewers assess whether measured durations justify the chosen limit and whether every original control remains effective. Final evidence lists every run, including failed diagnostics, and the source SHA it tested.

No additional permanent regression file or config-value-only test is planned: the existing corruption/healthy-control pairs are the behavioral acceptance test. The final PR is draft until complete and green; the operator receives the merge decision.
