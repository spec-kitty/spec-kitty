---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: analysis-freshness-claim-fields-01M6G9PP
mission_id: 01M6G9PPGVYGBEG54S597HG1AX
generated_at: '2026-11-03T09:38:26.107535+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/analysis-freshness-claim-fields-01M6G9PP/spec.md
    sha256: 6d06b806fcf75a382d939a23659f192271b956fb1be9c4d771eb32d4a1a20a7a
  plan.md:
    path: kitty-specs/analysis-freshness-claim-fields-01M6G9PP/plan.md
    sha256: 1e3ba264a04117af4e0924dca6ee48a6629f1a87d2fa1d85a54291c83532d402
  tasks.md:
    path: kitty-specs/analysis-freshness-claim-fields-01M6G9PP/tasks.md
    sha256: 5736b23eab35ba8d657999efc7e904fc6ea87a57e3415e105ae444aef00667a5
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 0
  low: 0
  high: 0
  critical: 0
  info: 5
findings: []
---

## Specification Analysis Report

Cross-artifact pass over `spec.md`, `plan.md`, `tasks.md` and
`tasks/WP01-planning-fingerprint.md`, checked against the code the plan changes
(`src/specify_cli/analysis_inputs.py`, `analysis_report.py`,
`dossier/hasher.py`, `kernel/vcs_lock.py`) and against the charter
(ATDD-first, locality of change, single canonical authority, tests-as-scaffold).

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | plan.md §Phase 1 D-1 | The plan says "project onto `WP_STATIC_PROJECTION_FIELDS`" but never lists the keys whose treatment changes versus today's `metadata \ MUTABLE_FIELDS`. A reviewer cannot check the narrowing without doing that diff by hand. | Add the field-by-field delta (unchanged / newly excluded / newly included) to D-1. |
| A2 | Inconsistency | MEDIUM | plan.md §D-2 vs spec.md §Edge Cases | The plan acknowledges that `planning_base_branch`, `merge_target_branch` and `branch_strategy` also stop staling the report; the spec's Edge Cases list only the claim triple and the VCS lock. | State the same set in the spec so the acceptance surface and the design agree. |
| C1 | Coverage | MEDIUM | plan.md §Project Structure, tasks/WP01 (subtasks T001-T006) | The repository requires a per-PR changelog fragment for a user-facing fix; neither the plan's file map nor any subtask produces it. | Add the fragment to the plan's structure and to WP01 as a subtask, noting the PR number is only known after `gh pr create`. |
| E1 | Coverage | MEDIUM | tasks.md §T002 | "Second claim exits 0 and prints no `analysis_report_required`" can be satisfied by an early-exit path that never claims WP02. | Require the test to assert WP02's reduced lane is `in_progress` (or equivalent) after the second claim. |
| L1 | Style | LOW | research.md, spec.md SC-002/SC-003 | The mutation check is a success criterion, but no artifact says where its output is captured for the reviewer. | Name the capture point (PR `## Tests run` / `Self-review:`) in T006. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 claim-leaves-analysis-current | yes | T001, T002, T003, T004 | unit + end-to-end |
| FR-002 planning-only-wp-fingerprint | yes | T003 | |
| FR-003 vcs-lock-excluded | yes | T004 | |
| FR-004 planning-edits-still-stale | yes | T005 | 6 positive controls |
| FR-005 one-declared-field-authority | yes | T003, T004 | reuse only, no new list |
| NFR-001 no-new-false-refusals | yes | T002 | 100% claims in fixture |
| NFR-002 no-gate-weakening | yes | T005 | same fixture, both directions |
| NFR-003 fingerprint-cost | yes | T003, T004 | no git/network added |
| C-001 reuse-canonical-projections | yes | T003, T004 | |
| C-002 no-strict-reparse | yes | T003 | tolerant `FrontmatterManager` read kept |
| C-003 gate-requirements-unchanged | yes | T003, T004, T006 | no change to `analysis_report.py` |
| SC-001 | yes | T002 | |
| SC-002 | yes | T005 | |
| SC-003 | yes | T006 | |
| SC-004 | yes | T006 | |

**Charter Alignment Issues:** none. The mission reuses the single canonical
classifications instead of minting a second field list, keeps the diff inside one
source module, and proves the fix red-first through the pre-existing CLI entry
point.

**Unmapped Tasks:** none. Every subtask (T001-T006) maps to at least one FR/NFR or
success criterion.

**Metrics:**

- Total Requirements: 15 (5 FR, 3 NFR, 3 C, 4 SC)
- Total Tasks: 6 (one work package)
- Coverage %: 100
- Ambiguity Count: 1
- Duplication Count: 0
- Critical Issues Count: 0

**Verdict**: `ready` — no high or critical finding; the four medium findings are
artifact-completeness gaps to fix before implementation begins (A1, A2, C1, E1)
and one housekeeping item (L1).

## Remediation applied before implementation (all 5 findings closed)

No finding remains open on the current artifacts: the five raised by the first pass were
remediated in `spec.md`, `plan.md`, `tasks.md` and the WP01 prompt before implementation
began, and this report is re-recorded against the remediated artifacts.

| Finding | Remediation |
| --- | --- |
| A1 | `plan.md` §Phase 1 D-1 now carries the field-by-field delta table (today → after, with the reason for each newly excluded key). |
| A2 | `spec.md` Edge Cases now states that `planning_base_branch`, `merge_target_branch` and `branch_strategy` also stop staling the report, and why. |
| C1 | `plan.md` §Project Structure names `docs/changelog/unreleased/<pr>.fixed.md`; WP01 gained subtask T007 and owns `docs/changelog/unreleased/**`. |
| E1 | WP01's T002 now requires the second claim to reduce WP02 to `in_progress`, not merely to exit 0. |
| L1 | WP01's T006 names the capture point for the mutation-check output (the PR's `## Tests run` / `Self-review:` block). |

Re-recorded after these edits; verdict stays `ready`.

## Second pass: independent planning review (2026-11-03)

An independent reviewer (`openai-codex/gpt-6.1-sol`, read-only) attacked the
approved plan against the code before implementation began. Three of its findings
changed the design; they are recorded in `research.md` ("Design revision") and
`plan.md` §D-1, and the artifacts were amended before any code was written:

| # | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| R1 | HIGH | The closure recursed into `tasks/<wp>/`, where a rejection writes `review-cycle-N.md` / `review-feedback-N.md` / `baseline-tests.json`, so a rework re-claim would still be refused. | `tasks/` is fingerprinted as the flat planning surface it is: the directory sentinel plus every non-directory entry, never a per-WP sub-directory. |
| R2 | HIGH | The proposed allow-list (`WP_STATIC_PROJECTION_FIELDS`) would have stopped watching 17 keys the gate watches today — `status`, `agent_profile`, `model`, `role`, `reviewer*`, the descriptive `mission_*` set, the WP's landing instructions — plus every unknown legacy key. That is a gate-policy widening for the maintainer, not a repair. | Rejected the allow-list; the exclusion is exactly the declared runtime/claim sets (`MUTABLE_FIELDS` + a newly declared `WP_CLAIM_PROVENANCE_FIELDS`). Nothing becomes newly unwatched except the claim's own stamp. |
| R3 | MEDIUM | Dropping the whole `vcs` lock would also hide an unexpected backend value. | Normalise instead: absent == `git` (the only supported backend), any other value is fingerprinted as written, only the lock timestamp is dropped. |

Its remaining points (field-delta accuracy, positive-control breadth, per-writer
mutation checks, capture point for the mutation output) were folded into
`plan.md` §D-3 and WP01 T005/T006; the `test_owned_analysis_recording` failures it
flagged in passing are a pre-existing red on `main` (cited issue #6787), not this
mission's.

**Verdict**: `ready`, findings closed, design amended before implementation.
