# Implementation Plan: specify_cli out-of-matrix nightly drift reds

**Branch**: `issue-5258-nightly-drift-reds` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/nightly-drift-reds-01M3M14S/spec.md`

## Summary

This mission turns the 23 reds in the spec's verdict table green, each on the side DIRECTIVE_041 assigns it:

- **Test-side:** 17 re-pins or deletes, plus one scoped guard exemption for dated `docs/reports/` snapshots.
- **Harness-side:** Typer's own rich console is made colourless inside the existing autouse plain-console seam.
- **Product-side:** DIRECTIVE_052 gets an incoming edge in the built-in pack.
- **Data-side:** the two un-flipped dogfood missions are cut over with the canonical migration.
- **Wording:** one stale "features" in the `src/` documentation template is fixed. The fork's retirement is tracked as #5280.

## Technical Context

**Language/Version**: Python 3.11+ (nightly also runs 3.13)
**Primary Dependencies**: typer / rich (colour seam), spec-kitty-events 10.4.x (R23), charter DRG (R7)
**Storage**: kitty-specs dogfood mission files (R9); built-in pack YAML (R7)
**Testing**: targeted pytest files only (NFR-001); red-first reproduction for the harness fix via `GITHUB_ACTIONS=true`
**Target Platform**: GitHub Actions ubuntu runners (nightly) and local dev
**Project Type**: single (CLI)
**Performance Goals**: N/A
**Constraints**: C-001 sibling-owned paths untouched; C-002 no skip/xfail/quarantine
**Scale/Scope**: about 14 test files, 1 conftest, 2 pack YAMLs, 2 dogfood missions, 1 template line

## Charter Check

- **Standing order 4 (DIRECTIVE_041):** every red carries a verdict with commit evidence in `spec.md`. The PR repeats a one-line verdict per re-pin. PASS.
- **Standing order 9 (red-main discipline):** nothing is skipped, xfailed or reverted. The two DELETEs remove tests that pin retired behaviour, and positive coverage of the new behaviour is kept or added (R15 gets a CLI-level fail-closed assertion). PASS.
- **Single canonical authority:**
  - The colour fix extends the existing `_plain_cli_console_seam` fixture instead of adding a second helper.
  - The `docs/reports/` exemption reuses the existing archive classification.
  - The DIRECTIVE_052 edge follows the 053 precedent (`3e3bcb4da`).
  
  PASS.
- **Pack tiers:** DIRECTIVE_052 lives in `packs/built-in` (consumer doctrine), and the new edge stays in that tier. The pack-manifest regeneration runs through `spec-kitty doctrine regenerate-graph`. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION:** only targeted files and named gate files are run (`test_archive_root_byte_identical.py`, `test_no_legacy_terminology.py`, packaging/pack gates implicated by R7). PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-drift-reds-01M3M14S/
├── spec.md
├── plan.md
├── tasks.md
├── tasks/WP0*.md
├── issue-matrix.json
└── traces/
```

### Source Code (repository root)

```
tests/conftest.py                                   # IC-01 colour seam
tests/specify_cli/cli/commands/                      # IC-02 re-pins (doctor golden, doctor coordination, mission-type fallback)
tests/specify_cli/cli/test_decision_command_shape_consistency.py  # IC-02/IC-03
tests/contract/test_terminology_guards.py           # IC-03 (#5187)
docs/development/reference/terminology-exemptions.md # IC-03 exemption record
tests/specify_cli/test_audit_tail_readers.py        # IC-02
tests/specify_cli/invocation/cli/test_dispatch.py   # IC-02
packs/built-in/agent_profiles/debugger-debbie.agent.yaml, packs/built-in/*.graph.yaml  # IC-04
tests/specify_cli/charter_lint/checks/test_orphan.py, tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py  # IC-04
tests/specify_cli/skills/test_installer*.py         # IC-05
tests/migration/test_verdict_provenance_backfill.py # IC-05
kitty-specs/{doctrine-org-init-from-template-01KXNA6P,org-init-template-security-remediation-01KY4S90}/  # IC-06
tests/architectural/test_archive_root_byte_identical.py (sanctioned-corrections entry)  # IC-06
src/specify_cli/missions/documentation/templates/task-prompt-template.md  # IC-06
```

**Structure Decision**: Single project. All edits are in existing files; no new modules.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Colour-independent in-process CLI output

- **Purpose**: Make Typer's help and usage renderer colourless under the autouse seam, so assertions behave the same on GitHub runners.
- **Relevant requirements**: FR-001, SC-002
- **Affected surfaces**: `tests/conftest.py::_plain_cli_console_seam`; the stale "does not reach Typer" notes in `test_complete.py` and `test_events_tail.py`
- **Sequencing/depends-on**: none
- **Risks**: Tests that deliberately assert colour. Grep for `\x1b[` expectations under in-process runners before landing. The fix pins and restores the two module globals `FORCE_TERMINAL` and `COLOR_SYSTEM`.

### IC-02 — Re-pin stale CLI-surface oracles

- **Purpose**: Fix the R4 `--fix` loop in the product. Align R1–R5, R15–R17 and R21–R22 with the intentional product contract, and remove the dead fallback-print branch.
- **Relevant requirements**: FR-002
- **Affected surfaces**: `src/specify_cli/cli/commands/_coordination_doctor.py` (`_apply_missing_worktree_fix` reclassifies on `exc.coordination_branch`); `src/specify_cli/cli/commands/mission_type.py` (dead branch); the doctor golden, doctor coordination, decision shape, mission-type fallback, audit-tail and dispatch tests
- **Sequencing/depends-on**: none
- **Risks**: Hand-edited golden. Render the expected text through the file's own `force_wide_help_console` and `normalize_help` so it stays byte-true.

### IC-03 — Dated report snapshots exempt from literal guards

- **Purpose**: Stop two literal guards from forcing edits to historical findings.
- **Relevant requirements**: FR-003
- **Affected surfaces**: `test_terminology_guards.py`, `test_decision_command_shape_consistency.py`, `terminology-exemptions.md`
- **Sequencing/depends-on**: none
- **Risks**: Over-broad exemption. Keep it scoped to the dated `docs/reports/` tree the archive classification already covers.

### IC-04 — DIRECTIVE_052 reachability and the corpus-count ratchet

- **Purpose**: Add the incoming `requires` edge, then re-pin the dependent ledgers and SC-011 counts.
- **Relevant requirements**: FR-004, FR-005
- **Affected surfaces**: `src/charter/offering/drg/migration/extractor.py` `_CURATED_ARTIFACT_EDGES` (a `procedure:disciplined-defect-diagnosis --suggests--> directive:DIRECTIVE_052` edge, following the DISCIPLINED_REFACTORING precedent), regenerated built-in graph shards and pack manifest (`spec-kitty doctrine regenerate-graph`), a new ledger entry (23) in `test_extractor_projection.py`, the orphan and bulk-edit ledgers
- **Sequencing/depends-on**: none (FR-005's count depends on it, so they land together)
- **Risks**: Ledger fan-out. Owning test dirs are `tests/charter/` and `tests/doctrine/` (CLAUDE.md blast-radius rule 2), run as the named files only. A `suggests` edge must not move the `requires` histogram.

### IC-05 — Installer and verdict-backfill oracles

- **Purpose**: Re-pin R18–R20 (R20 gets a rebuild call-count spy; its causing commit is bisected, not guessed) and R23 (plus a positive pin that a stale approval is dropped).
- **Relevant requirements**: FR-007
- **Affected surfaces**: `test_installer.py`, `test_installer_global_reassess_convergence.py`, `test_verdict_provenance_backfill.py`
- **Sequencing/depends-on**: none
- **Risks**: Keep the lock-file tolerance exact: same bytes and mode, only mtime may move.

### IC-06 — Dogfood corpus cutover and template wording

- **Purpose**: Cut over the two missions with `spec-kitty migrate backfill-runtime-state`, record the sanctioned archive correction, and fix the template word.
- **Relevant requirements**: FR-006, FR-008
- **Affected surfaces**: the two dogfood mission dirs, `test_archive_root_byte_identical.py` sanctioned list, the src documentation template
- **Sequencing/depends-on**: none
- **Risks**: The migration must run from a standalone checkout (precedent `9f4105ee3`). The archive sanction is an operator decision, recorded as sanctioned by the #5258 mission brief.
