# Tasks: Verdict-matrix RMW preservation (#4858 + #4868)

**Mission**: `verdict-matrix-rmw-preservation-01M32M9G`
**Branch**: `fix/verdict-matrix-rmw-preservation`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Two independent work packages (disjoint files → parallel lanes). Each is ATDD red-first: the
failing reproduction is committed BEFORE the fix, per root (C-006/C-011). Completion is recorded
via `spec-kitty agent tasks mark-status Txxx --status done` (event-sourced; no checkboxes).

## Subtask Index (reference only — not a tracking surface)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first NI-mode concurrent lost-update harness (flat) | WP01 | |
| T002 | Red-first coord + criterion variants + gate spies/ordering | WP01 | |
| T003 | Fix: locked re-read + single-row splice (both modes) | WP01 | |
| T004 | Fix: atomic write at shared acceptance writer | WP01 | |
| T005 | Verify red→green + blast radius (#4858) | WP01 | |
| T006 | Lint/type/format (#4858) | WP01 | |
| T007 | Red-first coord legacy-md issue-verdict repro | WP02 | [P] |
| T008 | Red-first write-staging spy + idempotency + malformed guard | WP02 | [P] |
| T009 | Fix: coord-aware migration read + structured malformed error | WP02 | [P] |
| T010 | Verify red→green + blast radius + lint (#4868) | WP02 | [P] |

## Work Packages

### WP01 — #4858 acceptance-verdict concurrency lost-update (P1/P0)
- **Goal**: locked re-read + single-row splice + atomic write so concurrent verdict writers never
  lose a committed row and `overall_verdict` never flips fail→pass; flat + coord; both modes.
- **Priority**: P0 (release blocker). **Independent test**: deterministic serialized concurrency
  harness (no threads) + gate spies; RED on base, GREEN on fix.
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Dependencies**: none. **Prompt**: [tasks/WP01-acceptance-verdict-concurrency.md](./tasks/WP01-acceptance-verdict-concurrency.md) (~250 lines)
- **Risks**: the "re-read outside the lock" mutant (killed by the strict ordering assertion);
  NI splice resetting the judged row to pending; fail-open on timeout; read≠commit surface.

### WP02 — #4868 issue-verdict coord legacy-Markdown migration (P1)
- **Goal**: migrate the coord-aware authoritative surface, preserving existing issue verdicts;
  write staging stays primary (C-011).
- **Priority**: P1. **Independent test**: integration repro (real write-seam) + write-staging spy
  (mutation-tested) + idempotency + malformed guard; RED on base, GREEN on fix.
- **Subtasks**: T007, T008, T009, T010
- **Dependencies**: none (disjoint files from WP01 → parallel). **Prompt**:
  [tasks/WP02-issue-verdict-coord-migration.md](./tasks/WP02-issue-verdict-coord-migration.md) (~200 lines)
- **Risks**: the residue-only guard does not kill the `read_dir`-as-write mutant; malformed `.md`
  raw-traceback; unmaterialized-coord degradation precondition.

## Parallelization

WP01 and WP02 touch disjoint files (`acceptance_verdict.py`/`matrix.py` vs
`issue_verdict.py`/`issue_matrix_migration.py`) and no shared seam — fully parallel lanes. Both
only *import* (never edit) the shared coord fixture `_build_coord_mission_for_matrix`.

## MVP scope

WP01 (#4858, P0) is the MVP — the release-blocking data-loss fix. WP02 (#4868, P1) closes the
sibling root in the same class.

## Post-merge / close-out checklist (not a WP — but tracked here so it is not honor-system)

Per the mission brief, after `spec-kitty merge` consolidates lanes into local `main`:
- [ ] **CHANGELOG.md** entry added for the #4858 + #4868 fix (owed even though no `__init__.py`
      change forces a version bump — C-009). Do NOT skip.
- [ ] Any touched docs updated.
- [ ] Set issue-matrix verdicts #4858/#4868 `in-mission → fixed` (via `spec-kitty agent
      issue-verdict`) once each WP is implemented + reviewed, before `move-task --to approved`.
      (#2482 already `not-applicable`.)
- [ ] Pre-merge review squad over the final aggregate diff; fold all findings.
- [ ] Clean branch history (coherent commits, `#`-referenced, attribution footer).
- [ ] Rebase on latest `skupstream/main` (re-fetch first).
- [ ] Open the draft PR to `spec-kitty/spec-kitty` targeting `main`; operator merges.
