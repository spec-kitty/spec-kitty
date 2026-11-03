# Mission Specification: Analysis freshness ignores claim-time runtime fields

**Mission Branch**: `analysis-freshness-claim-fields-01M6G9PP`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#7106 — "[bug] Claiming a work package makes the analysis report stale: every later claim is refused with analysis_report_required" (P0, milestone 4.0.0 release scope).

## Problem

`spec-kitty agent action implement WPxx` on a fresh lane stamps runtime provenance
into two files that the analysis-freshness material closure fingerprints
(`src/specify_cli/analysis_inputs.py`):

- `tasks/WPxx-*.md` gets `base_branch`, `base_commit` and `created_at`
  (`lanes/implement_support.create_lane_workspace`), and those keys are not in
  `migration.strip_frontmatter.MUTABLE_FIELDS`, so they are hashed.
- `meta.json` gets `vcs` and `vcs_locked_at` (`implement_support.ensure_vcs_locked`),
  and `meta.json` is hashed whole.

So the first claim of a mission invalidates a report recorded with
`record-analysis --report-only` (the material-manifest path), and every later claim
of an unchanged mission is refused with `analysis_report_required` /
`stale_analysis_report` until the operator re-records an analysis nobody re-ran.
The claim invalidates the gate that guards the claim. Grounding reproduction on
`main` @ `d18c4f1d58`:

```
$ spec-kitty agent action implement WP01 --agent alice   # rc=0
$ spec-kitty agent action implement WP02 --agent alice   # rc=1
Error: analysis_report_required: ...
  Reason: stale_analysis_report
  Stale inputs:
    - material:kitty-specs/<slug>/meta.json
    - material:kitty-specs/<slug>/tasks/WP01-m1.md
```

This is the same class as #1764 (status churn in `tasks.md`) and #2493 (pipe-table
status cells), and it is the residual the per-file normalisation those fixes added
never covered: the claim writes to a different file.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A recorded analysis survives the mission's claims (Priority: P1)

An orchestrator, `spec-kitty next`, or a human implements a multi-work-package
mission. The analysis report is recorded once, verdict `ready`. Each successive
`agent action implement WPxx` claims its work package and starts work, without
re-recording the analysis and without any operator intervention.

**Why this priority**: without it the implement loop cannot claim a second work
package at all, and the only way past the gate is to re-record an analysis that was
never re-run — which trains every operator to defeat the readiness check.

**Independent Test**: record an analysis on a finalized two-WP mission, claim WP01,
claim WP02; the second claim exits 0 and prints no `analysis_report_required`.

**Acceptance Scenarios**:

1. **Given** a finalized mission with a recorded `ready` analysis, **When** WP01 is
   claimed on a fresh lane (stamping `base_branch`/`base_commit`/`created_at` into
   its prompt and `vcs`/`vcs_locked_at` into `meta.json`), **Then** the report is
   still current and WP02 claims successfully.
2. **Given** the same mission, **When** a claim rewrites only those runtime fields
   (a re-claim, a second lane, a different base commit), **Then** the fingerprint is
   unchanged.

---

### User Story 2 - Planning edits still make the report stale (Priority: P1)

The gate keeps refusing implementation when the planning content actually changed
after the analysis was recorded.

**Why this priority**: it is the half that makes the fix safe. Narrowing the
fingerprint must not turn the readiness gate into a rubber stamp.

**Independent Test**: after a recorded analysis, edit `subtasks`, `dependencies`,
`requirement_refs`, `owned_files` or the WP prompt body of a claimed work package
in turn; every edit makes the report stale, and the claim is refused.

**Acceptance Scenarios**:

1. **Given** a recorded analysis and a claimed WP01, **When** its `subtasks` (or
   `dependencies`, `requirement_refs`, `owned_files`) change, **Then** the report is
   stale and implement is refused with `analysis_report_required`.
2. **Given** a recorded analysis and a claimed WP01, **When** the prompt body
   changes, **Then** the report is stale.
3. **Given** a recorded analysis, **When** a work package prompt is added or removed,
   **Then** the report is stale (the closure's key set still covers additions and
   removals).

---

### Edge Cases

- `meta.json` fields other than the VCS lock (`target_branch`, `topology`,
  `mission_id`, `status_phase`, …) must keep staling the report, and so must a
  `vcs` value other than the only supported backend.
- A rejected work package's review-cycle artifacts (`tasks/<wp>/review-cycle-N.md`,
  `review-feedback-N.md`, `baseline-tests.json`) must not stale the report: they are
  generated runtime output, and following them made a rework re-claim impossible.
- A WP prompt authored before this change, carrying `planning_base_branch` /
  `merge_target_branch` / an unknown legacy key, must not raise: the fingerprint is
  a projection over a declared field set, never a strict re-parse of the file.
  Those two keys (and `branch_strategy`) also stop staling the report: they are
  frozen planning-branch provenance written once by `finalize-tasks` before the
  analysis, and they are classified as descriptive rather than authored content by
  the canonical WP projection this mission reuses. That narrowing is deliberate and
  is the second half of "planning content only".
- A report recorded *without* `--report-only` (no material manifest) keeps its
  existing `spec.md`/`plan.md`/`tasks.md`/charter-only contract — unchanged.
- A WP prompt with the same planning fields but reordered YAML keys must not stale
  the report (the projection serialises with sorted keys, as it does today).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Claim leaves the analysis current | As an implementer, I want claiming a work package to leave a recorded analysis current, so that I can claim the next one without re-recording an unchanged report. | High | Open | [build] | no |
| FR-002 | Runtime-set exclusion for WP prompts | As a maintainer, I want the WP prompt fingerprint to exclude exactly the declared runtime/claim keys, so that a claim's own provenance cannot stale a report while every authored field (and unknown legacy key) still does. | High | Open | [build] | no |
| FR-003 | VCS lock normalised out of the meta.json fingerprint | As a maintainer, I want the mission `meta.json` fingerprint to normalise the VCS selection (absent == `git`) and drop its lock timestamp, so that a mission's first claim does not stale its analysis while an unexplained backend value still does. | High | Open | [build] | no |
| FR-004 | Planning edits still stale the report | As a reviewer, I want substantive planning edits (subtasks, dependencies, requirement_refs, owned_files, body, added/removed WP) to keep making the report stale, so that the readiness gate still protects the mission. | High | Open | [build] | no |
| FR-005 | One declared authority for the excluded fields | As a maintainer, I want the claim's provenance field set declared once and consumed by both the writer and the fingerprint, so that the exclusion cannot drift from what the claim actually writes. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new false refusals | A mission whose only change since `record-analysis` is claim-time runtime provenance must claim 100% of its work packages in the end-to-end fixture (0 `analysis_report_required` refusals). | Reliability | High | Open |
| NFR-002 | No gate weakening | Every positive control in FR-004 must still produce a stale verdict and a non-zero exit, measured on the same fixture that proves FR-001. | Correctness | High | Open |
| NFR-003 | Fingerprint cost unchanged in order | The material closure must stay a single pass over the declared paths, with no per-call git or network access added (existing tests assert the closure is stable across incidental writes). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | One declared field set, no inline duplicates | The excluded claim triple is `frontmatter.WP_CLAIM_PROVENANCE_FIELDS`, consumed by the writer (`create_lane_workspace`) and by the fingerprint; the VCS-lock set is `kernel.vcs_lock.VCS_LOCK_META_FIELDS`; `MUTABLE_FIELDS` stays the stripper's. `analysis_inputs` mints no new list. | Technical | High | Open |
| C-002 | No strict re-parse of legacy prompts | The WP prompt fingerprint must not start failing on prompts the old code hashed happily (no `WPMetadata` `extra="forbid"` validation inside the analysis closure). | Technical | High | Open |
| C-003 | What the gate requires is unchanged | This mission changes what counts as planning *input*; it does not change which artifacts `record-analysis` requires, nor the `--report-only` material-manifest contract. | Technical | High | Open |

### Key Entities

- **Material closure**: the declared set of paths (`collect_material_inputs`) whose
  content the analysis report fingerprints, keyed `material:<repo-relative path>`.
- **Planning projection**: the subset of a work package prompt's frontmatter that
  defines its authored contract, hashed together with the prompt body.
- **VCS lock**: the `vcs`/`vcs_locked_at` pair `meta.json` gains on a mission's first
  claim.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the end-to-end fixture (finalize-tasks → `record-analysis --report-only` → claim WP01 → claim WP02), the second claim exits 0 with no `analysis_report_required` and no re-record. — [build] · no-op passable: no
- **SC-002**: Each of `subtasks`, `dependencies`, `requirement_refs`, `owned_files`, the prompt body, an added/removed work package and an unexpected `vcs` value still turns the same fixture's report stale (7/7 positive controls), while a per-WP review-cycle artifact does not and a rejected+re-claimed work package claims again. — [build] · no-op passable: no
- **SC-003**: Re-adding either excluded set to the fingerprint (the WP provenance triple, or the `meta.json` lock normalisation) makes exactly the matching FR-001 regression test fail (mutation check performed and recorded in the PR). — [build] · no-op passable: no
- **SC-004**: The existing material-closure invariants (`tests/specify_cli/test_analysis_inputs.py`, the report-transaction and owned-currency suites) stay green. — [ratchet] · no-op passable: no
