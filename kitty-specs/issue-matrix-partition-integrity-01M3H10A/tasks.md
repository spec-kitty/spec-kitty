# Tasks: Issue-Matrix Partition Read Integrity & Merge Verdict-Terminality

**Mission**: issue-matrix-partition-integrity-01M3H10A
**Branch**: `claude/spec-kitty-ci-failures-r0xui3` (planning + merge target)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

5 work packages. Dependency chain: **WP01 → WP02 → {WP03, WP04} → WP05**. WP03 and WP04 are
parallelizable (disjoint files). Every WP is ATDD red-first: the failing-first test is committed
before the fix, RED on the base and GREEN on the WP's final commit; refusal/absence assertions are
paired with same-fixture positive controls (coord-vs-flat, in-mission-vs-terminal).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing-first test: coord-ref content read + fail-closed legs + #4959 non-regression | WP01 | |
| T002 | Add ref-content read authority in resolution.py, resolving the ref via resolve_lifecycle_phase | WP01 | |
| T003 | #4959 carve-out: UNMATERIALIZED→ref-read for ISSUE_MATRIX only; keep the raise for other kinds | WP01 | |
| T004 | Fail-closed legs: deleted ref, probe error, empty-with-references (each paired positive control) | WP01 | |
| T005 | Failing-first test: readers accept a coord-ref content source (post-consolidation) | WP02 | |
| T006 | Factor the (primary_discovery, coord_matrix) two-partition split into one shared helper | WP02 | |
| T007 | Extend load_issue_matrix / issue_matrix_artifact_present to accept a content source | WP02 | |
| T008 | Extend validate_issue_matrix (review/_issue_matrix.py) + check_issue_matrix (doctor.py) | WP02 | |
| T009 | Failing-first test: review Gate-4 reads coord verdicts (coord-vs-flat, in-mission control) | WP03 | |
| T010 | review/__init__.py _evaluate_issue_matrix: separate discovery(PRIMARY) from matrix(COORD/ref) via the shared helper | WP03 | |
| T011 | SKILL.md Gate-4: replace raw `cat` with a resolver-backed read (positive control on rendered doctrine) | WP03 | |
| T012 | Failing-first test: merge gate coord-husk discovery + terminal-verdict (block/warn) + parity | WP04 | |
| T013 | merge_gates.py completeness gate: repo_root/mission_slug + discovery(PRIMARY via seam) + verdict(COORD/ref via shared helper) | WP04 | |
| T014 | merge_gates.py: terminal-verdict sibling gate reusing _issue_matrix_approval_blocker (covers unknown too); executor wiring | WP04 | |
| T015 | Non-vacuous architectural guard: no raw issue-matrix path reads / no split-helper bypass in review+merge consumers (self-mutation check) | WP05 | |

## Work Packages

### WP01 — Coordination-ref content read primitive (IC-01a)
- **Goal**: A new seam read that returns ISSUE_MATRIX content from the correct git ref (resolved by
  the same lifecycle-phase authority the write uses), fail-closed, without regressing #4959.
- **Priority**: P1 (foundational). **Depends on**: none.
- **Requirements**: FR-005, FR-007, NFR-002, NFR-003.
- **Independent test**: T001 — witnesses the post-consolidation read (coord ref) + fail-closed legs +
  #4959 non-regression, RED before T002/T003/T004.
- **Subtasks**: T001, T002, T003, T004. **Est.** ~300 lines. **Prompt**: [tasks/WP01-coord-ref-read-primitive.md](./tasks/WP01-coord-ref-read-primitive.md)

### WP02 — Reader content-source + shared split helper (IC-01b + IC-shared)
- **Goal**: Readers accept a coord-ref content source; the two-partition split is factored into one
  helper all consumers call.
- **Priority**: P1. **Depends on**: WP01.
- **Requirements**: FR-005, NFR-001.
- **Independent test**: T005 — readers resolve post-consolidation content, RED before T006–T008.
- **Subtasks**: T005, T006, T007, T008. **Est.** ~350 lines. **Prompt**: [tasks/WP02-reader-content-source-and-shared-helper.md](./tasks/WP02-reader-content-source-and-shared-helper.md)

### WP03 — Mission-review gate partition split + Gate-4 doctrine (IC-02)
- **Goal**: Review Gate 4 reads references from PRIMARY and verdicts from COORD/ref; the doctrine uses
  a resolver-backed read instead of a raw `cat`.
- **Priority**: P1. **Depends on**: WP02. **Parallel with**: WP04.
- **Requirements**: FR-001, FR-002, FR-008 (partial).
- **Independent test**: T009 — coord-vs-flat divergent-matrix fixture + in-mission control, RED before T010/T011.
- **Subtasks**: T009, T010, T011. **Est.** ~300 lines. **Prompt**: [tasks/WP03-review-gate-partition-and-doctrine.md](./tasks/WP03-review-gate-partition-and-doctrine.md)

### WP04 — Merge gate partition split + terminal-verdict enforcement (IC-03 + IC-04)
- **Goal**: The merge completeness gate discovers from PRIMARY and reads verdicts from COORD/ref; a
  sibling gate enforces the terminal-verdict rule (block refuses, warn lists) reusing the existing rule.
- **Priority**: P1. **Depends on**: WP02. **Parallel with**: WP03.
- **Requirements**: FR-003, FR-004, FR-006.
- **Independent test**: T012 — coord-husk-discovery + divergent-partition + terminal-verdict (block/warn) + coord-vs-lanes parity, RED before T013/T014.
- **Subtasks**: T012, T013, T014. **Est.** ~380 lines. **Prompt**: [tasks/WP04-merge-gate-partition-and-verdict-terminality.md](./tasks/WP04-merge-gate-partition-and-verdict-terminality.md)

### WP05 — Regression guard (IC-05)
- **Goal**: A non-vacuous architectural guard closing the improvised-path / split-bypass class by construction.
- **Priority**: P2. **Depends on**: WP03, WP04.
- **Requirements**: FR-008, NFR-001.
- **Independent test**: T015 — the guard itself, with a self-mutation check (injecting a raw read trips it).
- **Subtasks**: T015. **Est.** ~150 lines. **Prompt**: [tasks/WP05-partition-regression-guard.md](./tasks/WP05-partition-regression-guard.md)

## MVP / sequencing note

WP01+WP02 are the enabling foundation. WP03 (closes #5171) and WP04 (closes both #4943 legs) are the
user-visible deliverables and run in parallel once WP02 lands. WP05 locks the class shut.

## Completion verdicts (issue-matrix)

The finalize-tasks auto-classifier mis-scaffolded some rows (see traces/tooling-friction.md). Corrected: #5169/#5172 → not-applicable (out of scope); #3044 → not-applicable (epic parent). **At mission completion the implementer/reviewer MUST author the gating verdicts** (the row for #4943 currently scaffolds `not-applicable` but the mission closes it):
- `spec-kitty agent issue-verdict --mission <slug> --issue '#5171' --verdict fixed --actor <id> --wp WP03 --evidence-ref <link>`
- `spec-kitty agent issue-verdict --mission <slug> --issue '#4943' --verdict fixed --actor <id> --wp WP04 --evidence-ref <link>`
