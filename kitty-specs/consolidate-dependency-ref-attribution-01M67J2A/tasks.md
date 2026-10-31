# Tasks: Consolidate dependency-ref attribution (#6771)

**Mission**: `consolidate-dependency-ref-attribution-01M67J2A` · **Branch**: `issue-6771-consolidate-dependency-ref-attribution`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first unit tests: an exempt commit set silences the merge axis; a spine-overlapping declaration REFUSEs; an unresolvable or unmerged ref REFUSEs | WP01 | |
| T002 | `resolve_external_dependency_refs` + `_external_dependency_refusal` in `reconciliation.py` | WP01 | |
| T003 | `ApprovedWpCommitSet` exempt fields and `build_approved_wp_set(external_dependency_refs=...)` | WP01 | |
| T004 | `_unattributable_in` shared window scan; merge and squash axes skip the exempt sets | WP01 | |
| T005 | Attribution hint on `VerifyResult.recovery_guidance` (names `--dependency-ref`) | WP01 | [P] |
| T006 | Red-first forecast tests: dry-run exits 1 on the undeclared repro and 0 with the declaration | WP02 | |
| T007 | `--dependency-ref` option on `consolidate`, threaded into `ConsolidateOptions` | WP02 | |
| T008 | `_MergeRunState.dependency_refs` + `ConsolidationState` persistence (resume keeps the declaration) | WP02 | |
| T009 | `phase_claim` / `phase_gate` pass the declaration into the claim | WP02 | |
| T010 | `run_dry_run_forecast`: build the claim, run the closed-world window scan, exit 1 with the recovery | WP02 | |
| T011 | Red-first end-to-end real-CLI repro (merge strategy, dry-run vs real, with and without the declaration) | WP03 | |
| T012 | Squash-strategy variant of the same repro | WP03 | |
| T013 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry | WP03 | [P] |
| T014 | `docs/guides/how-to/missions/merge-mission.md`: the supported restack path and the new flag | WP03 | [P] |
| T015 | Issue-matrix verdicts for #6771, #4945, #4977, #4981, #5013 | WP03 | |

## Phase 1 — Claim attribution

### WP01 — Declaration resolution, claim threading and verifier exemptions

**Goal**: a verified declaration turns a lane's merged dependency content into inherited history under both strategies, and every mis-declaration REFUSEs before any ref moves. **Priority**: P1. **Prompt**: [tasks/WP01-claim-attribution.md](tasks/WP01-claim-attribution.md)
**Independent test**: `tests/consolidation/test_dependency_ref_claim.py` — the exempt claim passes verification, the spine-overlapping declaration refuses, the undeclared claim still fails.

T001 Red-first unit tests: an exempt commit set silences the merge axis; a spine-overlapping declaration REFUSEs; an unresolvable or unmerged ref REFUSEs (WP01)
T002 `resolve_external_dependency_refs` + `_external_dependency_refusal` in `reconciliation.py` (WP01)
T003 `ApprovedWpCommitSet` exempt fields and `build_approved_wp_set(external_dependency_refs=...)` (WP01)
T004 `_unattributable_in` shared window scan; merge and squash axes skip the exempt sets (WP01)
T005 Attribution hint on `VerifyResult.recovery_guidance` (names `--dependency-ref`) (WP01)

Dependencies: none. Risk: the pinned divergence wording (`describe()`) — the hint goes on the guidance, never inside `describe()`.

## Phase 2 — Operator surface and forecast parity

### WP02 — `--dependency-ref`, run-state persistence and the dry-run forecast

**Goal**: the operator declares the ref once; the forecast and the real run reach the same verdict. **Priority**: P1. **Prompt**: [tasks/WP02-forecast-parity.md](tasks/WP02-forecast-parity.md)
**Independent test**: `tests/consolidation/test_dependency_ref_forecast.py` — the forecast refuses the undeclared repro with the same code and text the real run would use, and passes once declared.

T006 Red-first forecast tests: dry-run exits 1 on the undeclared repro and 0 with the declaration (WP02)
T007 `--dependency-ref` option on `consolidate`, threaded into `ConsolidateOptions` (WP02)
T008 `_MergeRunState.dependency_refs` + `ConsolidationState` persistence (resume keeps the declaration) (WP02)
T009 `phase_claim` / `phase_gate` pass the declaration into the claim (WP02)
T010 `run_dry_run_forecast`: build the claim, run the closed-world window scan, exit 1 with the recovery (WP02)

Dependencies: WP01 (the resolver and the claim fields). Risk: building the claim in the forecast must not run merge-only axes — only the window scan.

## Phase 3 — Proof and record

### WP03 — End-to-end repro, changelog and docs

**Goal**: the issue's reproduction is a regression test through the real CLI under both strategies, and the operator-facing docs name the supported restack path. **Priority**: P2. **Prompt**: [tasks/WP03-repro-and-docs.md](tasks/WP03-repro-and-docs.md)
**Independent test**: `tests/consolidation/test_dependency_ref_attribution_6771.py` drives `spec-kitty consolidate` end to end; the changelog entry and the merge how-to describe the flag.

T011 Red-first end-to-end real-CLI repro (merge strategy, dry-run vs real, with and without the declaration) (WP03)
T012 Squash-strategy variant of the same repro (WP03)
T013 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (WP03)
T014 `docs/guides/how-to/missions/merge-mission.md`: the supported restack path and the new flag (WP03)
T015 Issue-matrix verdicts for #6771, #4945, #4977, #4981, #5013 (WP03)

Dependencies: WP01, WP02 (the flag and the claim must exist before the CLI repro can pass). Risk: the real-CLI fixture is slow (~20s/test); keep the repro to three runs.
