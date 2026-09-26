# Implementation Plan: Mission-State Repair Audit-Trail Durability

**Branch**: `fix/mission-state-audit-trail-durability` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/mission-state-audit-trail-durability-01M37PWG/spec.md`

## Summary

Move the `doctor mission-state --fix` audit trail — the per-run manifest and the verbatim quarantine copy of removed rows — out of the git-ignored `.kittify/migrations/mission-state` root into a git-tracked audit root (`.kittify/mission-state-audit/`), for **both** repair flows (mission-state repair and duplicate-key repair). Add a write-only, operator-visible exit summary (human + `--json` parity) that names the artifacts, marks them tracked-but-uncommitted, and instructs the operator to commit them. Reconcile the `_POLICY_TRACKED` declaration with `.gitignore`. Touch no row-canonicality code.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: spec-kitty CLI internals (`specify_cli.migration.mission_state`, `specify_cli.core.atomic.atomic_write`, `specify_cli.core.paths`); Typer/Rich CLI surface (`cli/commands/doctor.py`)
**Storage**: filesystem — JSON manifest + JSONL quarantine artifacts under a repo-relative audit root
**Testing**: pytest (`tests/migration/`, `tests/integration/migration/`, `tests/status/` for the canonicality-regression guard)
**Target Platform**: Linux/macOS/Windows dev + CI (host-safe path handling; no symlink assumptions)
**Project Type**: single (CLI toolkit)
**Performance Goals**: no measurable wall-clock regression on a repair run (NFR-004); the summary reuses data the repair already computed
**Constraints**: placement/visibility seam only (C-001); write-only, operator commits (C-002); `_assert_git_safe` git-safety preserved (NFR-003); zero canonicality change (NFR-002)
**Scale/Scope**: ~1 source module primary (`migration/mission_state.py`), 1 CLI surface (`cli/commands/doctor.py` output), `.gitignore` reconciliation; ~3 focused test files

## Constitution / Charter Check

*GATE: Must pass before Phase 0. Re-check after Phase 1.*

- **DIRECTIVE_024 (Locality of Change)**: change confined to the repair module's write-path + its CLI output; no ripple into the status/decisions subsystems. ✅
- **DIRECTIVE_001 (Architectural Integrity)**: introduces one named audit-root constant consulted by both writers; no new authority crosses a module boundary. ✅
- **DIRECTIVE_010 (Specification Fidelity)**: every FR maps to a design element below; no scope drift beyond the spec. ✅
- **DIRECTIVE_025 (Domain-Matched Debt / Boy-Scout)**: FR-007 (`_POLICY_TRACKED` vs `.gitignore` reconciliation) is on-domain debt folded in, not opportunistic scope creep. ✅
- **C-001 boundary**: no edit to `AUTHORITATIVE_NON_LANE_EVENT_TYPES`, `is_non_lane_event`, `_is_preserved_non_lane_row`. Enforced by keeping the #4897 regression suite green (NFR-002). ✅

No charter conflicts. Supply-chain section: N/A — no dependency added, upgraded, or removed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-state-audit-trail-durability-01M37PWG/
├── plan.md              # This file
├── research.md          # Phase 0: path choice, two-writer survey, git-safety analysis
├── data-model.md        # Phase 1: audit-root + artifact entities, invariants
├── quickstart.md        # Phase 1: operator-facing before/after walkthrough
└── contracts/
    └── audit-trail-contract.md   # exit-summary + --json field contract
```

### Source Code (repository root) — scope expanded by the post-plan brownfield pointcut

```
src/specify_cli/migration/mission_state.py        # audit-root constant; relocate manifest (mission-state + dup-key) + quarantine writes; assemble summary payload; repoint _POLICY_TRACKED (:85-89); DROP MANIFEST_ROOT from _assert_git_safe checked set (:716,:908)
src/specify_cli/cli/commands/doctor.py            # render the write-only exit summary (human) + thread audit paths/count into --json
src/specify_cli/state/contract.py                 # migration_state_ledger StateSurface (:271-287): repoint path to audit root + git_class TRACKED; this SSOT DERIVES .gitignore, so no manual .gitignore edit
src/specify_cli/coordination/coherence.py         # is_self_bookkeeping_churn (:50): cover .kittify/mission-state-audit/ so accept/merge/record-analysis don't gate a repair's output (#2384 property via classification)

.gitignore                                        # KEEP the legacy .kittify/migrations/ entry (back-compat, C-005); the new tracked root is not ignored (already, by construction)

tests/architectural/test_archive_root_byte_identical.py       # repoint _ARCHIVE_ROOTS off old quarantine path (FR-010)
tests/architectural/test_transition_guard_shrink_only.py      # repoint _EXCLUSION_ROOTS off old quarantine path (FR-010)
tests/architectural/test_upgrade_recovery_preservation.py     # parametrized old quarantine path (FR-010)
tests/migration/test_mission_state_repair.py                  # manifest/quarantine relocation + summary payload + two-consecutive-fix (NFR-003b)
tests/migration/test_teamspace_migration_rehearsal.py         # remove hard-coded old-path literals (:143,:231-232)
tests/cli/commands/test_doctor_mission_state.py               # test-set manifest_path literals (:283,:376,:446)
tests/integration/migration/test_mission_state_repair_fidelity_e2e.py  # 'gitignored manifest' premise reversed
tests/specify_cli/test_state_contract.py / test_gitignore_contract.py  # contract-derived gitignore assertions
tests/integration/migration/test_audit_trail_durability_4928.py # NEW: check-ignore + git-clean-survival + accept-not-gated round trip (BOTH writers)
tests/status/test_authoritative_non_lane_registry_4897.py     # unchanged; must stay green (canonicality regression guard)
```

**Guard-citation correction (brownfield):** `_assert_git_safe` (dirty-path porcelain refusal) is at `mission_state.py:~2611`, NOT `:526` — `:526` is inside `_anchor_repair_root` (repo-boundary anchoring). NFR-003 was split into NFR-003a (anchoring, `_anchor_repair_root`) and NFR-003b (dirty-path refusal on a now-tracked root, `_assert_git_safe`).

## Phase 0: Research → `research.md`

Resolved before design (no open NEEDS CLARIFICATION):

1. **Audit-root path choice** — `.kittify/mission-state-audit/` is confirmed not git-ignored (`git check-ignore` reports tracked-ok) and mirrors the already-tracked `.kittify/evidence/` precedent. Alternatives (un-ignore the existing `.kittify/migrations/` tree; write under `kitty-specs/`) rejected — see research.md.
2. **Two-writer survey** — both the mission-state repair (`mission_state.py:713,752,1712-1715`) and the duplicate-key repair (`mission_state.py:904-913`) write under `MANIFEST_ROOT`; both must move (FR-006).
3. **Git-safety** — `_assert_git_safe` (`mission_state.py:526`) and `_POLICY_TRACKED` (`:85-89`) analysis: the new root must remain inside the repo boundary and be added to the tracked-policy set; `.gitignore` reconciled to match (FR-003, FR-007).
4. **Write-only guarantee** — no git add/commit is introduced (NFR-001); durability is realized on operator commit (C-002).

## Phase 1: Design & Contracts

- **`data-model.md`** — entities: Audit Root, Repair Manifest, Quarantine Artifact; invariants (manifest every run; quarantine only when rows removed; both under a non-ignored root; repair never commits).
- **`contracts/audit-trail-contract.md`** — the exit-summary text contract (always: manifest path + tracked-but-uncommitted marker; when quarantining: quarantine path + row count + commit instruction) and the `--json` field additions (`audit_manifest_path`, `audit_quarantine_path`, `quarantined_rows`), with human/JSON parity.
- **`quickstart.md`** — operator before/after: run `--fix`, observe the summary, `git check-ignore` shows tracked, `git clean -xfd` no longer destroys the trail.

Post-design Charter re-check: unchanged — locality and boundary hold.

## Engineering Alignment (confirmed)

Three governing Decision Moments drove the design and are resolved: **both-relocate-and-warn** (fix direction), **write-only-operator-commits** (commit behavior), and **relocate-properly-full-scope** (the post-plan brownfield scope pivot). The post-plan brownfield pointcut (architect + debugger lenses) corrected the plan in material ways: (1) there is **no runtime reader** of the old path — the trail is genuinely write-only, so no stale-reader split-brain; (2) the gitignored placement is a **deliberate #2384 decision** to keep repair from gating accept/merge, and `.gitignore` is *derived from* `state/contract.py`, so the fix must repoint the state contract and register the new root as **self-bookkeeping churn** rather than hand-edit `.gitignore`; (3) the `_assert_git_safe` append becomes a **self-block** once the path is tracked (drop it); (4) three architectural archive ratchets pin the old quarantine root; (5) keep the legacy ignore for **back-compat**. The riskiest elements are the state-contract change and the churn-classification (they must land together, or a repair gates accept). All are explicit WPs with direct tests.

## Branch Contract

- Current branch at plan start: `fix/mission-state-audit-trail-durability`
- Planning/base branch: `fix/mission-state-audit-trail-durability`
- Final merge target: `fix/mission-state-audit-trail-durability` → local `main` consolidation, then PR to `spec-kitty/spec-kitty` `main`
- `branch_matches_target`: true

## Next

`/spec-kitty.tasks` — translate the implementation concerns above into executable work packages. (Not created by this command.)
