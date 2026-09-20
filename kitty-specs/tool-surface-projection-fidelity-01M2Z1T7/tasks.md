# Tasks: Tool-surface projection honesty

**Mission**: tool-surface-projection-fidelity-01M2Z1T7
**Planning base / merge target**: `fix/tool-surface-projection-fidelity` (final PR → `main`)
**Discipline**: ATDD red-first for every FR. No `packs/` edits. Windows simulated by monkeypatching `kernel.paths.is_windows` (module attribute) + observed dir mode. Two file-disjoint seams → 2 parallel lanes + capstone.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: registry `can_write` gemini AND llxprt True with no `.gemini`/`.llxprt` dir | WP01 | [P] |
| T002 | Drop `check_dir` from gemini + llxprt rows in `writers/registry.py:42-43` (only) | WP01 | [P] |
| T003 | Red+green: repair-path regression — selected+stale gemini/llxprt, no harness dir → `repaired` (not `skipped`/`not_applicable`) | WP01 | [P] |
| T004 | NFR-002 parity table test: detect-applicable == repair-applicable for every supported writer | WP01 | [P] |
| T005 | Migration backfill test: configured gemini, `.gemini/` absent → GEMINI.md backfilled (behavior change vs today's detect==False) | WP01 | [P] |
| T006 | Verify cursor test `test_markdown_rules_writer.py:207-216` stays green (do NOT change generic `can_write`) | WP01 | [P] |
| T007 | Red: Windows-simulated (`is_windows`→True + observed dir mode≠0o755) `upgrade` converges in ONE pass, exit 0, no `Completed command output changed` | WP02 | [P] |
| T008 | Relax ONLY `managed_skills.py:179` dir-effect mode comparison, gated on `kernel.paths.is_windows()` (module attr), dir-scoped | WP02 | [P] |
| T009 | Red+green: second `upgrade` run is a clean no-op (NFR-001) + `upgrade --dry-run` zero repairs (#4777) under the Windows condition | WP02 | [P] |
| T010 | #4134: exclude `installed_at` from the recheck comparison hash (mirror `managed_skills.py:702 _expected_entries`); command seam `command_installer.py:514/610`; do NOT null stored value | WP02 | [P] |
| T011 | Red+green: cross-invocation `installed_at` stability for an unchanged command skill | WP02 | [P] |
| T012 | POSIX guard: a wrong SKILL.md **file** mode on a POSIX host still refuses (NFR-003); keep `[mode]` 0o700 dir tests `test_managed_skills.py:1371/1409` green | WP02 | [P] |
| T013 | Honest-failure path: a selected+stale+truly-unwritable surface → `failed`/non-zero, never exit-0 silent (FR-009) | WP03 | |
| T014 | e2e over BOTH seams: GEMINI.md+LLXPRT.md refresh (Seam A) AND Windows single-pass convergence + no phantom dry-run (Seam B) | WP03 | |
| T015 | Blast-radius run + classify; CHANGELOG `[Unreleased]` Fixed entry (no version bump) | WP03 | |

## Work Packages

### WP01 — Seam A: session-presence repair applicability (gemini/llxprt)
- **Goal**: `doctor tool-surfaces --fix`/`upgrade` refresh a stale root-level context file (GEMINI.md, LLXPRT.md) regardless of whether the harness command dir exists; a detected-stale selected surface is repaired or reported `failed`, never silently skipped.
- **Priority**: P1. **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-009 (Seam-A half), NFR-002.
- **Independent test**: stale GEMINI.md + no `.gemini/` → `--fix` refreshes it, reported repaired.
- **Surgical scope**: drop `check_dir` from `writers/registry.py:42-43` ONLY; do NOT touch `markdown_rules.py` `can_write` body (cursor/windsurf/kiro depend on it).
- **Subtasks**: T001–T006. **Depends on**: none. **Est**: ~380 lines.
- **Prompt**: [tasks/WP01-session-presence-applicability.md](./tasks/WP01-session-presence-applicability.md)

### WP02 — Seam B: managed-skills completion re-check host-awareness + manifest determinism
- **Goal**: `upgrade` converges in one invocation on Windows (dir-mode recheck host-aware) and `--dry-run` reports no phantom `chmod` repairs; command-skills manifest content is deterministic so a wall-clock `installed_at` never drives a phantom drift — without weakening POSIX correctness.
- **Priority**: P1. **Requirements**: FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-003.
- **Independent test**: Windows-simulated single-pass convergence + clean second run + zero `--dry-run` repairs; POSIX wrong-mode still refuses.
- **Surgical scope**: relax ONLY `managed_skills.py:179` (dir effect), gated on `kernel.paths.is_windows()`; #4134 excludes `installed_at` from the comparison hash. Do NOT touch `:195`/`:199`/`:308` or `manifest.py:_retain_entry_times`.
- **Subtasks**: T007–T012. **Depends on**: none (file-disjoint from WP01). **Est**: ~450 lines.
- **Prompt**: [tasks/WP02-managed-skills-recheck.md](./tasks/WP02-managed-skills-recheck.md)

### WP03 — Capstone: honest-failure + e2e + CHANGELOG
- **Goal**: prove the honesty invariant (FR-009) and SC-001..006 end-to-end across both seams; record the change.
- **Priority**: P2 (capstone). **Requirements**: FR-009 (integration), NFR-001 (integration).
- **Independent test**: e2e fixture green (both seams + honest-failure); blast-radius documented; CHANGELOG updated.
- **Subtasks**: T013–T015. **Depends on**: WP01, WP02. **Est**: ~300 lines.
- **Prompt**: [tasks/WP03-integration-changelog.md](./tasks/WP03-integration-changelog.md)

## Dependency graph
```
WP01 (Seam A) ─┐
               ├─► WP03 (capstone: honest-failure + e2e + CHANGELOG)
WP02 (Seam B) ─┘
```
WP01 ∥ WP02 are file-disjoint (session_presence vs tool_surface+skills) → parallel lanes. WP03 is the capstone.

## MVP scope
WP01 + WP02 deliver both P0 fixes (GEMINI.md refresh + Windows single-pass convergence). WP03 verifies the honesty invariant end-to-end and records the change.
