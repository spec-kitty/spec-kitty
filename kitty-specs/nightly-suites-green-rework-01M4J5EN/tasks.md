# Tasks: Nightly Suites Green — coord & charter rework fallout

**Mission**: `nightly-suites-green-rework-01M4J5EN`
**Planning base**: `fix/nightly-suites-green-rework` → merges to `fix/nightly-suites-green-rework` → PR to upstream `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

8 work packages, one per implementation concern (IC-01…IC-08). All are independently implementable; none depends on another (IC-01 is foundational but nothing else builds on it), so every lane can run in parallel. Each defect lands a red-first `@pytest.mark.regression` repro (NFR-004).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro: armed-pin + a sub-cluster-B owned-next test RED (pin #5988) | WP01 | |
| T002 | Thread owned `write_root` into `_write_create_meta` birth-write lock (sub-cluster A) | WP01 | |
| T003 | Thread owned root through finalize/status-transition/work-package-lifecycle/emit writers (sub-cluster B) | WP01 | |
| T004 | Non-vacuous guard: owned-context writer cannot resolve canonical R (FR-003) | WP01 | |
| T005 | Verify all 14 owned-lifecycle integration tests green; demote transitional repros | WP01 | |
| T006 | Red-first repro: redaction test currently bypasses the real clone seam (pin #5987) | WP02 | [P] |
| T007 | Drive token-bearing stderr through `clone_repository`; assert redaction + no raw token | WP02 | [P] |
| T008 | Verify `test_sources_security` green; positive+absence controls share one fixture | WP02 | [P] |
| T009 | Red-first repro: `not_in_project` flips under in-repo basetemp (pin #5989) | WP03 | [P] |
| T010 | Harden the test so its cwd has no enclosing project ancestor (no code/code-weakening) | WP03 | [P] |
| T011 | Verify all 4 `test_non_project_context_errors_are_json` cases green | WP03 | [P] |
| T012 | Red-first repro: oracle vs resolver diverge on remote-live coord branch (pin #5990) | WP04 | [P] |
| T013 | Make the oracle mirror the resolver's live-remote (`ls-remote`) presence arm | WP04 | [P] |
| T014 | Verify both `test_mission_status_reality` corpus tests green | WP04 | [P] |
| T015 | Red-first repro: implement template missing `command-templates` reference (pin #5989) | WP05 | [P] |
| T016 | Restore the verification reference in the SOURCE template (or realign the test) | WP05 | [P] |
| T017 | Verify `test_verification_checks_template_dirs` green; SOURCE edit only | WP05 | [P] |
| T018 | Re-derive `pinning_rule_inventory.json`; disposition the new `retiring-step` rule | WP06 | [P] |
| T019 | Verify `test_inventory_is_reproducible_by_rerunning_the_derivation` green | WP06 | [P] |
| T020 | Document `docs/archive/` (every docs/ exempt root) in the exemption policy doc | WP07 | [P] |
| T021 | Verify `test_terminology_exemption_policy_doc_is_present_and_consistent` green | WP07 | [P] |
| T022 | Red-first repro: heavy modules imported on `spec-kitty --help` (pin #5991) | WP08 | [P] |
| T023 | Defer `next_cmd.py:57-59` module-scope imports into function bodies | WP08 | [P] |
| T024 | Import-absence test (FR-010 positive control) asserting the chains are not on `--help` | WP08 | [P] |
| T025 | Confirm startup budget; flag the final limit value as an operator/CI decision (C-005) | WP08 | [P] |

## Work Packages

### WP01 — Owned-checkout ownership boundary (code regression #5988)

- **Goal**: Stop owned mission create/next from re-deriving the canonical/main repo root; anchor on the owned checkout root; add a non-vacuous guard. FR-001, FR-002, FR-003.
- **Priority**: P1 (the only genuine product regression; heart of the mission). **MVP**.
- **Independent test**: `tests/integration/test_owned_lifecycle_acceptance_{finalize,e2e,review}.py` (14 tests) green.
- **Subtasks**: T001–T005.
- **Depends on**: none. **Risks**: HIGH whack-a-field — ~50 callers of `resolve_status_lock_root`, ~98 of `mission_write_lock`; a brownfield scout runs on this seam before implementation. Sub-cluster B (13 tests) line-traced in T003.
- **Prompt**: [tasks/WP01-owned-checkout-boundary.md](./tasks/WP01-owned-checkout-boundary.md)

### WP02 — Git-source credential-redaction test realignment (#5987)

- **Goal**: Pin redaction through the real clone seam (`clone_repository`). FR-004.
- **Priority**: P2. **Independent test**: `test_sources_security.py::test_git_source_redacts_injected_oauth_token_from_stderr`.
- **Subtasks**: T006–T008. **Depends on**: none.
- **Prompt**: [tasks/WP02-git-redaction-test.md](./tasks/WP02-git-redaction-test.md)

### WP03 — Non-project context test hardening (#5989)

- **Goal**: `not_in_project` pin independent of pytest basetemp location; production unchanged. FR-005.
- **Priority**: P2. **Independent test**: `test_cli_boundary_context.py::test_non_project_context_errors_are_json` (×4).
- **Subtasks**: T009–T011. **Depends on**: none.
- **Prompt**: [tasks/WP03-context-test-hardening.md](./tasks/WP03-context-test-hardening.md)

### WP04 — Mission-status oracle remote-arm parity (#5990)

- **Goal**: Oracle mirrors the resolver's live-remote presence arm. FR-006.
- **Priority**: P2. **Independent test**: `test_mission_status_reality.py` corpus tests (×2).
- **Subtasks**: T012–T014. **Depends on**: none.
- **Prompt**: [tasks/WP04-status-oracle-remote-parity.md](./tasks/WP04-status-oracle-remote-parity.md)

### WP05 — Implement command-template verification reference (#5989)

- **Goal**: Template guidance and its pinning test agree on the canonical `command-templates` path (SOURCE edit). FR-007.
- **Priority**: P2. **Independent test**: `test_occurrence_classification.py::TestImplementTemplateContent::test_verification_checks_template_dirs`.
- **Subtasks**: T015–T017. **Depends on**: none.
- **Prompt**: [tasks/WP05-implement-template-reference.md](./tasks/WP05-implement-template-reference.md)

### WP06 — Pinning-rule inventory re-derivation (#5989)

- **Goal**: Committed inventory == fresh derivation; new `retiring-step` rule dispositioned. FR-008.
- **Priority**: P2. **Independent test**: `test_pinning_inventory_fresh.py::test_inventory_is_reproducible_by_rerunning_the_derivation`.
- **Subtasks**: T018–T019. **Depends on**: none.
- **Prompt**: [tasks/WP06-pinning-inventory-rederive.md](./tasks/WP06-pinning-inventory-rederive.md)

### WP07 — Terminology-exemption doc coverage (#5990)

- **Goal**: Policy doc documents every `docs/` exempt root incl. `docs/archive/`. FR-009.
- **Priority**: P2. **Independent test**: `test_terminology_guards.py::test_terminology_exemption_policy_doc_is_present_and_consistent`.
- **Subtasks**: T020–T021. **Depends on**: none. (planning_artifact — docs/ only)
- **Prompt**: [tasks/WP07-terminology-exemption-doc.md](./tasks/WP07-terminology-exemption-doc.md)

### WP08 — `--help` startup import shave + budget (#5991)

- **Goal**: Defer eager imports on the `--help` path; pin their absence; confirm budget. FR-010, FR-011.
- **Priority**: P2. **Independent test**: `test_cli_startup_budget_4409.py::test_help_stays_inside_its_startup_budget` + new import-absence test.
- **Subtasks**: T022–T025. **Depends on**: none. **Risk**: final limit value is operator/CI-owned (C-005).
- **Prompt**: [tasks/WP08-help-startup-imports.md](./tasks/WP08-help-startup-imports.md)
