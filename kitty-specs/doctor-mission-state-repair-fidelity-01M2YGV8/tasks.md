# Tasks: Doctor mission-state legacy repair & report fidelity

**Mission**: doctor-mission-state-repair-fidelity-01M2YGV8
**Planning base / merge target**: `fix/doctor-mission-state-repair-fidelity` (final PR → `main`)
**Discipline**: ATDD red-first for every FR. No `packs/` edits. Do NOT edit `audit/shape_registry.py`. New helpers stay out of `__all__`; no new routed `load_meta` read.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: repair of a mission with `change_mode: regular` must exit 0 & drop the field | WP01 | |
| T002 | Add `_normalize_change_mode` in `mission_metadata.py` (non-`bulk_edit` → drop), keep `VALID_CHANGE_MODES` + write-guard unchanged | WP01 | |
| T003 | Add `meta_actions` field to `MissionRepairResult` + `to_dict()` wiring | WP01 | |
| T004 | Wire canonicalizer to normalize before `validate_meta` and record `normalized_change_mode` **conditionally** (only when field present) | WP01 | |
| T005 | Red+green: idempotency — second `--fix` reports `missions_updated==0` for normalized mission | WP01 | |
| T006 | Red+green: generalize to any non-canonical/malformed value (FR-011) | WP01 | |
| T007 | Assert `--audit` and `--fix` agree (repairable) with NO `shape_registry.py` edit (FR-010) | WP01 | |
| T008 | Red: `--fix` terminal names each errored/normalized mission + reason (not counts only) | WP02 | |
| T009 | Rewrite `_pretty_repair` to render per-mission slug + `meta_actions`/`validation_errors` | WP02 | |
| T010 | Red: `--teamspace-dry-run` terminal names each affected mission + reason | WP02 | |
| T011 | Rewrite `_pretty_dry_run` to render per-mission `errors[]` (slug/artifact/line/message); keep `valid`/`Exit(1)` refusal semantics untouched | WP02 | |
| T012 | Assert `--fix --json` and `--teamspace-dry-run --json` carry per-mission records (parity) with no gitignored read (NFR-003) | WP02 | |
| T013 | Enrich the MagicMock characterization builders so per-mission rendering is actually asserted | WP02 | |
| T014 | Red: behavior-preservation — enumerate EVERY `change_mode` reader; legacy-value ≡ absent | WP03 | [P] |
| T015 | `implement.py:1340` `is not None` → `== "bulk_edit"` | WP03 | [P] |
| T016 | `gate.py:91-95` stop propagating raw legacy value; pin `GateResult.change_mode ∈ {"bulk_edit", None}` | WP03 | [P] |
| T017 | Update `test_implement_command.py` / `test_gate.py` for the aligned contract (encoding update, not regression) | WP03 | [P] |
| T018 | Integration: e2e over a seeded legacy-mission fixture proving SC-001..006 | WP04 | |
| T019 | Run blast-radius suite + `tests/architectural/` only if a gate fires; classify any red | WP04 | |
| T020 | CHANGELOG `[Unreleased]` entry (no version bump — release gate) | WP04 | |

## Work Packages

### WP01 — Repair normalization + `meta_actions` + non-fatal reconciliation
- **Goal**: `doctor mission-state --fix` repairs legacy `change_mode` by normalizing it to absent (recorded in a new `meta_actions` report field), exits 0, idempotent; audit and fix agree it is repairable — with no `shape_registry.py` edit.
- **Priority**: P1 (MVP). **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-010, FR-011, FR-013, NFR-002, C-001, C-002, C-003.
- **Independent test**: seed `change_mode: regular`; `--fix` → updated, field gone, action recorded, exit 0; rerun → 0 changes.
- **Subtasks**: T001–T007. **Depends on**: none. **Est**: ~450 lines.
- **Prompt**: [tasks/WP01-repair-normalization.md](./tasks/WP01-repair-normalization.md)

### WP02 — Reporting fidelity + dry-run parity
- **Goal**: `--fix` and `--teamspace-dry-run` surface per-mission slug + reason in terminal and `--json`; triage needs no gitignored file. Additive only — refusal semantics unchanged.
- **Priority**: P1. **Requirements**: FR-005, FR-006, FR-007, FR-008, FR-009, NFR-003, NFR-004, C-006.
- **Independent test**: forced failing/normalized run → terminal + `--json` name each mission and reason; dry-run parity.
- **Subtasks**: T008–T013. **Depends on**: WP01 (consumes `meta_actions`). **Est**: ~420 lines.
- **Prompt**: [tasks/WP02-reporting-fidelity.md](./tasks/WP02-reporting-fidelity.md)

### WP03 — Reader alignment (durable fix)
- **Goal**: Align every implicit `change_mode` presence-reader to the canonical `== "bulk_edit"` check so a legacy value and absence are indistinguishable at every reader (NFR-001), closing the whack-a-field class.
- **Priority**: P1 (blocker fold). **Requirements**: FR-012, NFR-001.
- **Independent test**: enumeration test — every reader returns identical behavior for legacy-value vs absent.
- **Subtasks**: T014–T017. **Depends on**: none (file-disjoint; runs parallel to WP01). **Est**: ~350 lines.
- **Prompt**: [tasks/WP03-reader-alignment.md](./tasks/WP03-reader-alignment.md)

### WP04 — Integration verification + CHANGELOG
- **Goal**: End-to-end proof of SC-001..006 over a seeded fixture; blast-radius green; CHANGELOG entry (no version bump).
- **Priority**: P2 (capstone). **Requirements**: (verification of all FR/SC) — no new FR.
- **Independent test**: e2e fixture run green; documented blast-radius counts.
- **Subtasks**: T018–T020. **Depends on**: WP01, WP02, WP03. **Est**: ~300 lines.
- **Prompt**: [tasks/WP04-integration-changelog.md](./tasks/WP04-integration-changelog.md)

## Dependency graph
```
WP01 ─┬─► WP02 ─┐
      │         ├─► WP04
WP03 ─┴─────────┘
```
WP01 and WP03 are file-disjoint and may run in parallel lanes. WP02 waits on WP01. WP04 is the capstone (depends on all).

## MVP scope
WP01 + WP03 deliver the milestone-blocking repair (#4778) and its behavior-preservation guarantee. WP02 adds the observability (#4780/#4779). WP04 verifies.
