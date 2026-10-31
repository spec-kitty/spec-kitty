---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: centralized-runtime-detection-is-project-local-01M68ZFE
mission_id: 01M68ZFE2BP5YQ37ZFXE5CQDNW
generated_at: '2026-10-31T12:43:10.803276+00:00'
analyzer_agent: claude
input_artifacts:
  spec.md:
    path: kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/spec.md
    sha256: 05bfd6f08f606e4bfeb813f5dba5ec5c78b8824e7e598e001e9c2bc5ee372d9b
  plan.md:
    path: kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/plan.md
    sha256: c583e06bcbfd742b1901a87dba7c4004ba785a353e0a3d9c5d58fe1844287bfe
  tasks.md:
    path: kitty-specs/centralized-runtime-detection-is-project-local-01M68ZFE/tasks.md
    sha256: 5fa14747b7495c48fc60a2c58381e4c4d26a129400d4b2536c41acbad7577ac2
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  high: 0
  low: 2
  medium: 1
  info: 0
findings:
- id: U1
  severity: medium
  category: underspecification
  summary: WP01 T001 step 7 offers an escape hatch that would replace the required same-fixture positive control with a weaker parseable-output assertion, which the non-vacuity tactic forbids.
- id: D1
  severity: low
  category: duplication
  summary: WP02 T008 and T009 both write traces/design-decisions.md without saying which owns the file, so a sequential implementer could append twice.
- id: A1
  severity: low
  category: ambiguity
  summary: Tasks/WP test commands name `.venv/bin/python` while the mission brief and repo convention prefer `uv run`; the implementer should be told both are acceptable.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| U1 | Underspecification | MEDIUM | tasks/WP01-project-stamped-detection.md, Subtask T001 step 7 | The same-fixture positive control is required, then immediately hedged with "if a genuine positive control is not reachable cheaply, assert instead ...". A hedged non-vacuity rule is how a vacuous green gets written. | Replace the hedge with the concrete positive control: assert the ledger still parses and still records both ids after the run, and add one companion test on the *same* fixture shape where the migration must run (pre-2.0 stamp) so the probe is proven able to observe a change. |
| D1 | Duplication | LOW | tasks.md T008/T009, tasks/WP02-changelog-and-deferrals.md | T008 writes `traces/design-decisions.md`; T009 also appends to `design-decisions`. Two writers, one file, no ownership note. | Make T008 the single writer of `design-decisions.md` and have T009 append only `approach` and `tooling-friction`. |
| A1 | Ambiguity | LOW | tasks/WP01-project-stamped-detection.md, Subtask T006 | Test commands are written as `.venv/bin/python -m pytest ...`; the brief and repo convention accept `uv run`. | Say explicitly that `uv run pytest ...` (or the venv interpreter in a source checkout) is equivalent, so the implementer does not stall on a missing `.venv`. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 project-metadata-first | yes | T002, T005 | |
| FR-002 legacy-migrations-skip | yes | T002 | Asserts both `detect()` results in one test |
| FR-003 converged-upgrade-noop | yes | T001 | Production path via the real `upgrade` command |
| FR-004 pre-2.x-still-repairs | yes | T003 | Positive control for FR-001/FR-002 |
| FR-005 metadata-less-unchanged | yes | T006 | Existing four `test_compat.py` cases re-run |
| NFR-001 clean-tree | yes | T001 | `git status --porcelain` empty |
| NFR-002 detection-writes-nothing | yes | T005 | Docstring + no-write constraint stated |
| NFR-003 fast-tier-budget | yes | T001 | `integration` + `git_repo` markers, no heavy suite |
| C-001 ledger-selection-untouched | yes | T005 | Explicit do-not-touch list |
| C-002 one-predicate-owner | yes | T005 | |
| C-003 repair-out-of-scope | yes | T008 | Recorded in Deferred |
| SC-001..SC-004 | yes | T001, T002, T006, T007 | All referenced from WP01/WP02 |

**Charter Alignment Issues:** none. The plan's Charter Check table covers the
binding gates (ATDD-first, locality of change, ledger authority, heavy-suite
discipline, pre-existing-failure reporting).

**Unmapped Tasks:** none — T001–T009 all appear in exactly one work package.

**Metrics:**

- Total Requirements: 11 (5 FR, 3 NFR, 3 C)
- Total Tasks: 9
- Coverage %: 100
- Ambiguity Count: 1
- Duplication Count: 1
- Critical Issues Count: 0
