# Work Packages: Sonar new-code reliability blockers removed at source

**Inputs**: `kitty-specs/sonar-new-code-reliability-01M6GRHZ/` — spec.md, plan.md, research.md, `evidence/`
**Prerequisites**: spec.md, plan.md

Two work packages. The first removes the three constructs that a SonarCloud reliability finding misreads (two BLOCKER false positives and one provably-dead branch) and pins the absence plus the behaviour each rewrite must preserve. The second writes the adjudication the issue actually needs, because four findings are on new code and nineteen are not — and because the fifth new-code finding (Java `S5960`) is a documented scan-scope decision this repository cannot reverse on its own.

There is no config change, no suppression marker, and no edit to any of the nineteen pre-existing sites. The rating moves E → C; reaching A needs a maintainer decision, which the second work package names.

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Remove the three new-code reliability constructs at source (Priority: P1)

**Goal**: `events.py` resolves the `--kind` default by name from the closed registry, `compiler.py` binds `ActiveCharterService` before the annotation that names it, and `backfill_identity.py` states the refusal invariant instead of a provably-dead guard — each behaviour unchanged, each verified by a guard that reds when the fix is reverted.
**Independent Test**: `pytest tests/architectural/test_new_code_reliability_shapes.py -q` fails on the pre-change tree for all three sites and passes after; reverting one fix at a time reds exactly its own assertion.
**Prompt**: `tasks/WP01-remove-the-three-constructs.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-004, SC-001, SC-003

### Included Subtasks

- T001 Red first: create the `architectural`+`fast` guard module with one shape assertion per site and a positive control for the AST probe; capture the three failures verbatim
- T002 `events.py`: `_DEFAULT_LOG_KIND = "status"` plus `_LogKind[_DEFAULT_LOG_KIND.upper()]`, with the comment naming `S5756`
- T003 `compiler.py`: move the function-local `import` above the `if`, delete the duplicate below, keep it function-local
- T004 `backfill_identity.py`: replace the dead ternary with an explicit narrowing; state the helper's precondition in its docstring
- T005 Prove non-vacuity half by half (three single-hunk reverts, three reds) and add the behavioural half of each test with both outcomes on one fixture shape
- T006 Confirm the diff surface (four files, no suppression, no `sonar-project.properties`/`sonar.yml` change)

### Dependencies

- None

---

## Work Package WP02: Record the adjudication and the changelog (Priority: P2)

**Goal**: The 4-vs-19 split, its query, and each finding's disposition are recorded where a maintainer can re-check them, updated with the post-change state; the changelog fragment exists in the `internal` section.
**Independent Test**: the evidence README's claims match the raw JSON beside it and the reproduction command returns the stated numbers; `check_changelog_style` and `check_spelling --pass unreleased` exit 0.
**Prompt**: `tasks/WP02-record-the-adjudication.md`
**Requirement Refs**: FR-004, NFR-001, C-002, C-003, SC-002, SC-004

### Included Subtasks

- T007 Re-check the evidence against the committed JSON; add the post-change state and the E → C (not A) statement with the Java reason
- T008 Author `docs/changelog/unreleased/7139.internal.md` in the fragment shape
- T009 Run `check_changelog_style` and `check_spelling --pass unreleased`
- T010 Draft the PR body's `## Change` and `## Deferred` from the evidence, naming the Java scope decision and the nineteen pre-existing findings

### Dependencies

- Depends on WP01 (the record describes what landed)
