# Work Packages: Analysis freshness ignores claim-time runtime fields

**Inputs**: Design documents from `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md
**Issue**: spec-kitty/spec-kitty#7106 (P0)

**Organization**: one work package. The projection and its positive controls cannot be
delivered apart — a narrowed fingerprint without the controls is an unproven gate.

**Prompt Files**: `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/tasks/WP01-planning-fingerprint.md`

## Subtask Format: `[Txxx] [P?] Description`

Subtask rows are reference rows, not checkboxes: record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Source**: `src/specify_cli/`
- **Tests**: `tests/`

---

## Work Package WP01: Planning-only fingerprint for the analysis material closure (Priority: P0)

**Goal**: A claim leaves a recorded analysis current; a planning edit still does not.
**Independent Test**: `pytest tests/specify_cli/test_analysis_inputs.py tests/integration/test_analysis_freshness_claim_7106.py`
**Prompt**: `kitty-specs/analysis-freshness-claim-fields-01M6G9PP/tasks/WP01-planning-fingerprint.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Red-first unit fixtures: claim-time provenance in a WP prompt and the VCS lock in `meta.json` must not change the material key. Run them against unmodified `main` and record the failure.
T002 Red-first end-to-end reproduction: finalized two-WP `lanes` mission, `record-analysis --report-only`, claim WP01 through the real `agent action implement`, then claim WP02; the second claim must exit 0 **and** reduce WP02 to `in_progress` (an exit-0 early path is not a pass). Fails on `main` with `analysis_report_required`.
T003 Implement the WP-prompt planning projection in `collect_material_inputs` (`WP_STATIC_PROJECTION_FIELDS` allow-list, body unchanged, tolerant read).
T004 Implement the `meta.json` projection in `collect_material_inputs` (every key except `VCS_LOCK_META_FIELDS`).
T005 [P] Positive controls: `subtasks`, `dependencies`, `requirement_refs`, `owned_files`, prompt body and an added WP each still stale the report — at unit level and through the end-to-end fixture.
T006 Mutation check (re-add a claim field to the projection; confirm the new tests go red — record both outputs under the PR's `## Tests run` / `Self-review:` block), ruff/mypy, and the blast-radius suites.

**Mission-level deliverable (not a WP01 subtask, so it cannot gate `for_review`):** the per-PR changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` (impact-first lead, `(#7106)`) is written once `gh pr create` has assigned the number, and `docs/changelog/unreleased/**` stays in WP01's `owned_files` so the path is attributed.

### Implementation Notes

- Everything the fix needs is already declared: `src/specify_cli/dossier/hasher.py::WP_STATIC_PROJECTION_FIELDS` and `src/kernel/vcs_lock.py::VCS_LOCK_META_FIELDS`. No new field list.
- The two new fingerprint branches are small helpers so each is directly testable.
- Do not widen `MUTABLE_FIELDS`: it belongs to the corpus stripper, not the freshness gate.

### Parallel Opportunities

- T005's unit controls can be authored alongside T003/T004; T001/T002 must exist (and be red) before either.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Widening the exclusion too far would turn the readiness gate into a rubber stamp — the T005 controls are the guard, and they run on the same fixture that proves FR-001 (half-by-half proof).
- A legacy WP prompt with retired keys must not start raising — the projection is applied to the tolerant `FrontmatterManager` read.

---

## Dependency Graph

```
WP01
```
