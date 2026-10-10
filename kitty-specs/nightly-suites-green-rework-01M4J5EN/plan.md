# Implementation Plan: Nightly Suites Green — coord & charter rework fallout

**Branch**: `fix/nightly-suites-green-rework` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/nightly-suites-green-rework-01M4J5EN/spec.md`

## Summary

Restore the five nightly suites escalated by run 38021225055 (25 failing tests, #5987–#5991) to green. One genuine product regression — owned-checkout mission create/next re-deriving the canonical repo root (from the #5883 canonical mission-lock rework) — is fixed in the code behind a non-vacuous guard. The remaining failures are test-reality drift, CI-environment/corpus artifacts, a stale derived artifact, a doc-sync gap, and a `--help` import regression plus an operator-owned perf-budget calibration — each fixed at its true root with a red-first repro.

## Technical Context

**Language/Version**: Python 3.11+ (nightly also runs 3.12 / 3.13 interpreter shards)
**Primary Dependencies**: existing spec-kitty internals (pytest, typer, ruamel.yaml, requests) — **no new dependencies added or upgraded** (supply-chain security section N/A)
**Storage**: N/A
**Testing**: pytest, targeted per-WP surfaces only (`NO_FULL_HEAVY_SUITES_IN_MISSION`); each defect lands an issue-pinned red-first `@pytest.mark.regression` repro (ATDD C-011, SO#4/#9); `PWHEADLESS=1 .venv/bin/python -m pytest`
**Target Platform**: Linux/macOS/Windows CI; the authoritative measure is the nightly runner
**Project Type**: single
**Performance Goals**: `spec-kitty --help` startup ratio within the confirmed `STARTUP_RATIO_LIMIT` (default 2.90) on the nightly runner, after shaving the eager-import regression
**Constraints**: fix at true root (no green-washing, no relaxing a check that guards real behavior); edit SOURCE templates under `packs/built-in/`, never agent copies; terminology canon; perf limit value is operator/CI-owned
**Scale/Scope**: 25 tests across 5 suites; 8 implementation concerns

## Charter Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

- **ATDD-first / red-first (C-011, SO#4, SO#9)**: PASS — each fix lands a red-first issue-pinned regression repro through the pre-existing entry point; reviewer verifies RED→GREEN on the WP base. Encoded as NFR-004.
- **Architectural gate discipline (SO#5)**: FR-003 adds a guard that an owned-context writer cannot resolve canonical `R`; it must start **non-vacuous** (concrete floor + self-mutation test), per `architectural-gate-non-vacuity`. No shrink-only allowlist introduced.
- **Canonical sources (SO#6, C-004)**: PASS — the implement-template fix edits the SOURCE template under `packs/built-in/`; the pinning inventory is re-derived by its canonical script; terminology guard respected.
- **Mission hygiene (SO#8)**: PASS — every issue (#5987–#5991) gets an issue-matrix row + claim + verdict; reviewer ≠ implementer.
- **Red-main discipline (SO#9)**: PASS — these are honest P0 reds; we land reproductions and work them down, never green-wash.
- **Test-remediation judgment (SO#4)**: PASS — each test is judged (stale→re-pin, valid→fix product): #5988 is product (fix code); #5987/#5989-ctx/#5990-corpus are test/CI (harden test/oracle to match correct behavior); #5989-pinning is derived (re-derive); #5990-terminology is doc.

No charter violations; Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-suites-green-rework-01M4J5EN/
├── plan.md              # This file
├── research.md          # Phase 0 — classification decisions + squad dispositions
├── spec.md              # Mission spec
├── meta.json            # contracts: none (test remediation)
├── checklists/requirements.md
└── tasks/               # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── core/mission_creation.py, mission_creation_meta.py, paths.py   # IC-01 owned-root threading
├── status/mission_write.py, work_package_lifecycle.py, emit.py     # IC-01 lock/status writers
├── workspace/root_resolver.py                                      # IC-01 early-return seam
├── coordination/status_transition.py, transaction.py               # IC-01 transition writers
├── cli/commands/next_cmd.py                                        # IC-08 eager-import shave
└── charter_packs/sources/git_source.py                            # IC-02 clone seam (read-only ref)

tests/
├── integration/test_owned_lifecycle_acceptance_{finalize,e2e,review}.py  # IC-01 pins (14)
├── specify_cli/cli/commands/test_cli_boundary_context.py                 # IC-03 (4)
├── specify_cli/charter_packs/test_sources_security.py                    # IC-02 (1)
├── contract/_mission_status_oracles.py, test_mission_status_reality.py   # IC-04 (2)
├── specify_cli/upgrade/test_occurrence_classification.py                 # IC-05 (1)
├── release/{test_pinning_inventory_fresh.py, pinning_rule_inventory.json}# IC-06 (1)
├── contract/test_terminology_guards.py                                   # IC-07 (1)
└── performance/test_cli_startup_budget_4409.py, _perf_helpers.py         # IC-08 (1)

docs/development/reference/terminology-exemptions.md                      # IC-07
packs/built-in/missions/mission-steps/software-dev/implement/            # IC-05 SOURCE template
scripts/ci/derive_pinning_inventory.py                                    # IC-06 derivation
```

**Structure Decision**: Single project; changes are localized per concern. IC-01 is the only cross-module code change; all others are single-surface test/doc/artifact fixes.

## Complexity Tracking

*No charter-check violations — section intentionally empty.*

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Owned-checkout ownership boundary (code regression)

- **Purpose**: Stop an owned-checkout mission from crossing into the repository-root checkout `R`. Brownfield scout confirmed this is **TWO distinct seams**, each a single targeted edit, not per-caller threading:
  - **Seam A (lock-root convergence, sub-cluster A)**: `_write_create_meta` is the lone create writer that drops `write_root` and locks the birth write on `R` while every sibling threads `P`. Fix: thread `write_root` (`core/mission_creation.py:572/683`) → `_write_create_meta` → `mission_write_lock(..., repo_root=write_root)`. `resolve_status_lock_root` already early-returns a non-None `repo_root` (`root_resolver.py:57-58`). One hop, one caller; the other ~98 lock callers already thread a `repo_root` — do NOT touch them.
  - **Sub-cluster B (13 owned next-walk tests)** was NOT a product redirect bug — verified at implement that `canonicalize_feature_dir` is uninvolved; the failures were acceptance tests not updated for the `analyze` DAG step (#5885), re-primed to the sibling pattern (prime to `analyze` + `analysis_is_current`), ownership/R-unchanged pins untouched. The only code fix is Seam A (birth-write lock).
- **Relevant requirements**: FR-001, FR-002, FR-003 (#5988, 14 tests)
- **Affected surfaces**: `core/mission_creation.py`, `core/mission_creation_meta.py`, `workspace/root_resolver.py`. Owned facts (carriers, read-only): `core/owned_mission.py:419/453/477`, `mission_runtime/owned_checkout.py:147`. Pins: `tests/integration/test_owned_lifecycle_acceptance_{finalize,e2e,review}.py` (14 tests) + new behavioral guards.
- **Sequencing/depends-on**: none (foundational). **Not split** — one ownership-seam decision; splitting A from B would fracture atomicity and overlap on `root_resolver.py`.
- **Risks**: **R1 — two conflated roots in `root_resolver`**: the LOCK mutex root (tolerated under `R`; tests `tolerate_status_mutex_for`) vs the STATUS-SURFACE root (must be `P`). #5883 collapsed both onto `resolve_canonical_root`→`R`. The fix must keep them separate — do NOT "fix" the lock root to `P` (that de-converges the mutex, a new regression). **R2 — parallel authority**: `owned.repository_root` (`R`, for the mutex) vs `owned.checkout`/`owned_root` (`P`, for the surface) are different fields of the same fact used per-concern; never harmonize them globally. **Out of scope (deferred)**: collapsing the lock-root-vs-surface-root conflation into two named resolvers — do not broaden this release fix into that refactor; file it as a follow-up.

### IC-02 — Git-source credential-redaction test realignment (test drift)

- **Purpose**: Pin the redaction property through the real clone seam the production path now uses.
- **Relevant requirements**: FR-004 (#5987, 1 test)
- **Affected surfaces**: `tests/specify_cli/charter_packs/test_sources_security.py::test_git_source_redacts_injected_oauth_token_from_stderr`; reference: `src/specify_cli/charter_packs/sources/git_source.py` `_clone`→`clone_repository` (:270) and `_redact_git_tokens` (:274).
- **Sequencing/depends-on**: none
- **Risks**: must keep the positive control (token present → redacted) AND the absence check (no raw token) on one shared fixture.

### IC-03 — Non-project context test hardening (CI-env artifact)

- **Purpose**: Make the `not_in_project` pin independent of where pytest basetemp lives; production resolution unchanged.
- **Relevant requirements**: FR-005 (#5989, 4 cases)
- **Affected surfaces**: `tests/specify_cli/cli/commands/test_cli_boundary_context.py::test_non_project_context_errors_are_json`; reference: `task_utils/support.py:48`, `core/paths.py:197` (unbounded walk-up, `stop=`).
- **Sequencing/depends-on**: none
- **Risks**: do NOT relax expected codes; guarantee no enclosing project ancestor (assert/skip when `locate_project_root(cwd) is not None`, or hermetic cwd).

### IC-04 — Mission-status reality oracle remote-arm parity (CI/corpus artifact)

- **Purpose**: Make the independent oracle mirror the resolver's live-remote (`ls-remote`) presence arm so scan and oracle agree when remotes are online.
- **Relevant requirements**: FR-006 (#5990, 2 tests)
- **Affected surfaces**: `tests/contract/_mission_status_oracles.py` (`derive_fallbacks:193`, `derived_but_remote_present:210`, `drift_oracle:374`), `tests/contract/test_mission_status_reality.py`; reference: `coordination/surface_resolver.py` (`_coord_branch_exists:691`, `_coord_branch_exists_via_remote:675`).
- **Sequencing/depends-on**: none
- **Risks**: keep the oracle independent while matching the resolver's documented three-arm rule; do not prune remotes to dodge it.

### IC-05 — Implement command-template verification reference (source template drift)

- **Purpose**: Restore agreement between the implement template's verification guidance and its pinning test on the canonical `command-templates` path.
- **Relevant requirements**: FR-007 (#5989, 1 test)
- **Affected surfaces**: SOURCE template under `packs/built-in/missions/mission-steps/software-dev/implement/`; test `tests/specify_cli/upgrade/test_occurrence_classification.py::TestImplementTemplateContent::test_verification_checks_template_dirs`.
- **Sequencing/depends-on**: none
- **Risks**: classify restore-source-guidance vs realign-test during the WP; edit SOURCE, never agent copies (C-004).

### IC-06 — Pinning-rule inventory re-derivation (stale derived artifact)

- **Purpose**: Re-derive the committed inventory and disposition the new rule (never regenerate-away).
- **Relevant requirements**: FR-008 (#5989, 1 test)
- **Affected surfaces**: `tests/release/pinning_rule_inventory.json`, `scripts/ci/derive_pinning_inventory.py`, the new `retiring-step` rule in `tests/specify_cli/charter_packs/test_pack_validator_org_endpoints.py`.
- **Sequencing/depends-on**: none
- **Risks**: the new rule must be dispositioned per the test's own warning (C-003).

### IC-07 — Terminology-exemption doc coverage (doc-sync)

- **Purpose**: Document `docs/archive/` (and any other undocumented `docs/` exempt root) in the policy doc.
- **Relevant requirements**: FR-009 (#5990, 1 test)
- **Affected surfaces**: `docs/development/reference/terminology-exemptions.md`; test `tests/contract/test_terminology_guards.py::test_terminology_exemption_policy_doc_is_present_and_consistent` (+ `tests/_support/terminology_scope.py` FORBIDDEN_SCAN_ROOTS).
- **Sequencing/depends-on**: none
- **Risks**: cover EVERY `docs/` exempt root the shared list declares; confirm the canonical doc path (the test reads `docs/development/reference/...` but asserts a guard-source reference to `docs/development/terminology-exemptions.md`).

### IC-08 — `--help` startup import shave + budget calibration (perf)

- **Purpose**: Defer the eager module-scope imports that pull charter-activation / runtime-schema / status chains onto the `--help` path; pin their absence; confirm the budget on CI.
- **Relevant requirements**: FR-010, FR-011 (#5991, 1 test)
- **Affected surfaces**: `src/specify_cli/cli/commands/next_cmd.py:57-59`; new import-absence test; `tests/performance/test_cli_startup_budget_4409.py`, `tests/_perf_helpers.py:94` (`STARTUP_RATIO_LIMIT`, operator/CI-owned).
- **Sequencing/depends-on**: none
- **Risks**: FR-011 is no-op passable by a bare limit bump — the FR-010 import-absence test is its positive control. The final limit number is an operator decision measured on the nightly runner (C-005).
