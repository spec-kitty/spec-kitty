# Tasks: move-task / approval-gate ergonomics (#3469)

**Mission**: `move-task-approval-ergonomics-01M302R0`
**Branch**: `fix/move-task-approval-ergonomics` (final merge target: upstream `main` via PR)

Subtask completion is event-sourced — record with `spec-kitty agent tasks mark-status Txxx --status done`.
The rows below are reference rows, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression: default-gating + demotion signals + multi-occurrence | WP01 | |
| T002 | `GatingClass` value object + pure classifier (aggregate, default-gating) | WP01 | |
| T003 | Extend discovery to retain all occurrences + attach classification | WP01 | |
| T004 | Scaffold records non-gating classes as non-gating (not gating rows) | WP01 | |
| T005 | Unit tests: marker forms, PR forms, cross-repo exclusion, impl-target-wins | WP01 | |
| T006 | Red-first: `not-applicable` accepted, non-gating at approved, terminal at done | WP02 | |
| T007 | Add `NOT_APPLICABLE` to `IssueMatrixVerdict` (additive) | WP02 | |
| T008 | Thread `not-applicable` + evidence-token doc through `issue-verdict` CLI/help | WP02 | |
| T009 | Approval blocker: consume classifier for gating; `not-applicable` non-gating + terminal; lever SSOT | WP02 | |
| T010 | ADR for the verdict-vocabulary contract change (supersede WP09 intent) | WP02 | |
| T011 | Red-first: cross-site consistency (non-gating at approved ⇒ merge + doctor) | WP03 | |
| T012 | `merge_gates` consumes the shared classifier | WP03 | [P] |
| T013 | `status/doctor` consumes the shared classifier | WP03 | [P] |
| T014 | Early approval-gating warning in specify/plan/tasks/analyze prompts | WP03 | [P] |
| T015 | Red-first: `move-task --actor/--reason` accepted | WP04 | |
| T016 | Add `--actor`/`--reason` aliases to `move-task` | WP04 | |
| T017 | Fix stale `--assignee` help string; add inert-checkbox guidance → `mark-status` | WP04 | |
| T018 | CHANGELOG `[Unreleased]` entry + affected CLI docs | WP05 | |
| T019 | User doc for `not-applicable` verdict + classification behavior | WP05 | |
| T020 | Regenerate docs retrieval index + freshness/terminology checks | WP05 | |

---

## WP01 — Reference classification seam (foundation)

**Goal**: Give every discovered `#NNNN` a gating classification (implementation-target = gating;
context-only / PR-or-commit = non-gating), computed as an aggregate over ALL occurrences, defaulting
to gating. One shared, pure classifier the whole mission consumes.
**Priority**: P1 (foundation / critical path). **Independent test**: classify a fixture set of
references and assert the gating verdict per FR-011/FR-015.
**Subtasks**: T001, T002, T003, T004, T005 (~5).
**Depends on**: none. **Blocks**: WP02, WP03.
**Requirements**: FR-001, FR-002, FR-011, FR-012 (defines), FR-015, NFR-003, NFR-005.
**Implementation sketch**: red-first test → `GatingClass` + classifier in the discovery module →
extend `IssueReference`/`discover_issue_references` to keep all occurrences → scaffold uses
classification → unit tests. **Risks**: first-occurrence dedupe today (FR-015); must not exclude
cross-repo behavior. **Est. size**: ~380 lines.

## WP02 — Verdict contract (`not-applicable`) + approval-blocker + ADR

**Goal**: Add the truthful, additive, terminal, non-gating `not-applicable` verdict across the enum,
the `issue-verdict` CLI/help (incl. the evidence-token rule), and the approval-blocker logic
(consume the WP01 classifier; pin the lever SSOT). Record the ADR.
**Priority**: P1. **Independent test**: `not-applicable` accepted, non-gating at `approved`, passes
`done`/merge; legacy verdicts unchanged.
**Subtasks**: T006, T007, T008, T009, T010 (~5).
**Depends on**: WP01. **Blocks**: WP03.
**Requirements**: FR-003, FR-004, FR-006, FR-010, FR-013, FR-014, NFR-001, NFR-005.
**Implementation sketch**: red-first → enum value → CLI/help + evidence-token doc → approval blocker
(gating from classifier, `not-applicable` non-gating + terminal, SSOT rules) → ADR. **Risks**: shared
file `tasks_parsing_validation.py` — WP02 owns it; WP03 must not touch it. **Est. size**: ~460 lines.

## WP03 — Cross-site adoption + early-warning surfacing

**Goal**: Make `merge_gates` and `status/doctor` derive gating from the same WP01 classifier (no
divergence), and surface a non-gating early approval-gating warning at specify/plan/tasks/analyze.
**Priority**: P1. **Independent test**: a reference non-gating at `approved` is non-gating at merge
and clean in doctor (NFR-006).
**Subtasks**: T011, T012, T013, T014 (~4).
**Depends on**: WP01, WP02. **Blocks**: —.
**Requirements**: FR-007, FR-012 (realizes cross-site), NFR-006, NFR-005.
**Implementation sketch**: red-first cross-site test → merge_gates consumes classifier → doctor
consumes classifier → early-warning note in mission-step prompts. **Risks**: three consumers must
share ONE decision; test all three. **Est. size**: ~340 lines.

## WP04 — move-task CLI ergonomics + docs (parallel lane)

**Goal**: Add `--actor`/`--reason` aliases to `move-task` (matching `issue-verdict`'s `--actor`), fix
the stale `--assignee` help string, and add inert-checkbox guidance pointing at `mark-status`.
**Priority**: P2. **Independent test**: `move-task … --actor X --reason Y` succeeds identically to
`--agent`/`--note`. **Runs fully in parallel with the spine.**
**Subtasks**: T015, T016, T017 (~3).
**Depends on**: none. **Blocks**: —.
**Requirements**: FR-005, FR-008, FR-009, NFR-005.
**Implementation sketch**: red-first → aliases → help/docstring/guidance. **Risks**: do NOT touch the
#2816 subtask-completion code path — guidance only. **Est. size**: ~240 lines.

## WP05 — Docs, CHANGELOG, retrieval index (planning artifact)

**Goal**: User-facing docs + CHANGELOG `[Unreleased]` entry for the new verdict/behavior, and
regenerate the docs retrieval index (an ADR was added) with freshness + terminology checks.
**Priority**: P3. **Independent test**: docs freshness `--ci` errors=0; terminology guard passes.
**Subtasks**: T018, T019, T020 (~3).
**Depends on**: WP02 (ADR exists), WP03 (behavior final), WP04 (alias docs mirror shipped flags). **Blocks**: —.
**Requirements**: FR-006 (docs surface), NFR-004.
**Implementation sketch**: CHANGELOG + CLI docs → user doc for `not-applicable` → regenerate index +
run `check_docs_freshness.py --ci` + `test_no_legacy_terminology.py`. **Risks**: keep docs mirroring
shipped behavior. **Est. size**: ~220 lines.

---

**MVP**: WP01+WP02 deliver the core honest-gate fix. **Parallelization**: WP04 runs alongside the
WP01→WP02→WP03 spine; WP05 last.
