# Tasks: Mission-State Repair Audit-Trail Durability (#4928)

Branch: `fix/mission-state-audit-trail-durability` · Merge target: `fix/mission-state-audit-trail-durability` → local `main` → PR to `spec-kitty/spec-kitty` `main`.

Scope: relocate the `doctor mission-state --fix` audit trail (manifest + dup-key manifest + quarantine) from git-ignored `.kittify/migrations/mission-state` to tracked `.kittify/mission-state-audit/`, reconcile the #2384 accept/merge non-gating property via self-bookkeeping-churn classification, add a write-only operator exit summary (+ `--json`), and migrate the governance/guard/test surfaces. **No row-canonicality change.**

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Introduce `MISSION_STATE_AUDIT_ROOT = .kittify/mission-state-audit` constant | WP01 | |
| T002 | Repoint the 3 write sites (mission-state manifest, dup-key manifest, quarantine) to the audit root | WP01 | |
| T003 | Drop `MANIFEST_ROOT` from the `_assert_git_safe` checked path-set (self-block fix) | WP01 | |
| T004 | Repoint `_POLICY_TRACKED` off the ignored path to the audit root | WP01 | |
| T005 | Update `state/contract.py` `migration_state_ledger` surface → audit-root path + `git_class=TRACKED`, rewrite #2384 note; add audit-trail RepairReport fields | WP01 | |
| T006 | Red-first tests: relocation to check-ignore-clean root, two-consecutive-`--fix` succeeds, state-contract + gitignore-contract updated | WP01 | |
| T007 | Cover `.kittify/mission-state-audit/` in `is_self_bookkeeping_churn` | WP02 | |
| T008 | Red-first test: a `--fix` before accept/merge/record-analysis is not gated (churn-classified) | WP02 | |
| T009 | Render write-only exit summary (human): manifest path always; quarantine path + row count + commit instruction when quarantining | WP03 | [P] |
| T010 | Thread `audit_manifest_path` / `audit_quarantine_path` / `quarantined_rows` into `--fix --json` | WP03 | [P] |
| T011 | Update `test_doctor_mission_state.py` old-path literals; add human/JSON parity test | WP03 | [P] |
| T012 | Repoint 3 architectural archive/exclusion ratchets off the old quarantine root; record the trail is reviewable-not-immutable | WP04 | |
| T013 | Migrate remaining old-path-asserting tests (teamspace rehearsal, fidelity e2e); confirm legacy `.kittify/migrations/` ignore kept | WP04 | |
| T014 | NEW e2e `test_audit_trail_durability_4928.py`: both writers → check-ignore clean → `git add`+commit → `git clean -xfd` survival → accept-not-gated | WP04 | |

## Work Packages

### WP01 — Relocate the audit trail + reconcile the state contract (foundational)
- **Goal**: move all three audit writes to the tracked root, make the canonical state contract (which derives `.gitignore`) agree, fix the `_assert_git_safe` self-block, repoint `_POLICY_TRACKED`, and expose audit paths on the RepairReport.
- **Priority**: P1 (foundational — everything depends on it).
- **Independent test**: `--fix` writes manifest+quarantine under a `git check-ignore`-clean path; two consecutive `--fix` runs succeed without `--allow-dirty`; `test_state_contract`/`test_gitignore_contract` green.
- **Subtasks**: T001–T006.
- **Dependencies**: none.
- **Requirements**: FR-001, FR-002, FR-003, FR-006, FR-007, FR-009, FR-011, NFR-001, NFR-002, NFR-003a, NFR-003b.
- Est. ~320 lines.

### WP02 — Accept/merge non-gating via self-bookkeeping-churn (dep WP01)
- **Goal**: register the audit root as self-bookkeeping churn so a repair's tracked-but-uncommitted output never gates `accept`/`merge`/`record-analysis` — the #2384 property, now by classification.
- **Priority**: P1.
- **Independent test**: after a `--fix` that writes uncommitted audit artifacts, the dirty-tree preflight classifies them as churn and does not refuse.
- **Subtasks**: T007–T008.
- **Dependencies**: WP01.
- **Requirements**: FR-008, NFR-005, C-006.
- Est. ~180 lines.

### WP03 — Write-only operator exit summary + `--json` parity (dep WP01)
- **Goal**: on `--fix` completion, name the audit artifacts (tracked-but-uncommitted) and instruct the operator to commit; add `--json` field parity.
- **Priority**: P1.
- **Independent test**: quarantining run names manifest+quarantine+count with a commit instruction; zero-quarantine run names the manifest; `--json` carries the same paths/count.
- **Subtasks**: T009–T011.
- **Dependencies**: WP01.
- **Requirements**: FR-004, FR-005, NFR-004.
- Est. ~220 lines.

### WP04 — Governance ratchets, test migration, durability e2e (dep WP01, WP02, WP03)
- **Goal**: repoint the architectural archive ratchets, migrate old-path-asserting tests, keep the legacy ignore for back-compat, and add the end-to-end durability guard.
- **Priority**: P1 (closes the mission's success criteria).
- **Independent test**: the new e2e proves both writers land tracked, survive `git clean` after commit, and do not gate accept.
- **Subtasks**: T012–T014.
- **Dependencies**: WP01, WP02, WP03.
- **Requirements**: FR-010, C-003, C-005.
- Est. ~260 lines.
