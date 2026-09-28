# Tasks: Squad doctrine: single owner and profile-per-task rule (fold-in: #5218, #5202, #5078)

**Mission**: `squad-doctrine-single-owner-01M3KBP7`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

**Sequencing:**
- WP01 (migration), WP02 (P0 guidelines owner) and WP03 (safe-commit recipes) have no dependencies.
- Content owners: WP04 (squad), WP05 (testing/BDD), WP06 (Common Docs), WP07 (change scope / review) and WP08 (supply chain) follow WP02.
- WP11 (served prompts, contracts, profiles) follows WP02, WP04, WP05 and WP08.
- WP09 is the single owner of every generated and wiring surface. It runs after WP01, WP04–WP08 and WP11.
- WP10 dogfoods the migration on this repo, then handles charter, docs and glossary.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests (own commit, RED) | WP01 | |
| T002 | Extract `_retired_activation.py` | WP01 | |
| T003 | Thin rtk migration | WP01 | |
| T004 | The new migration | WP01 | |
| T005 | Allowlists | WP01 | |
| T006 | Red-first test (own commit, RED) | WP02 | |
| T007 | Merge the four software-dev files (onto the `mission-steps` base) | WP02 | |
| T008 | Repoint the loader | WP02 | |
| T009 | Delete the 17 `actions/*/guidelines.md` | WP02 | |
| T010 | Docs | WP02 | |
| T011 | Red-first test (own commit, RED) | WP03 | |
| T012 | A single recipe helper | WP03 | |
| T013 | Replace the recipes | WP03 | |
| T014 | Update pinned output tests | WP03 | |
| T015 | Red-first owner test (own commit, RED) | WP04 | |
| T016 | Rewrite the procedure | WP04 | |
| T017 | Shrink the skill | WP04 | |
| T018 | Re-point the lens guard | WP04 | |
| T019 | Delete the styleguide and repoint the references | WP04 | |
| T020 | Fixed-lens prose and modes | WP04 | |
| T021 | Red-first owner test (own commit, RED) | WP05 | |
| T022 | Fold the checklist into `test-first-bug-fixing`, then delete it | WP05 | |
| T023 | Terms: one owner | WP05 | |
| T024 | Mutation | WP05 | |
| T025 | BDD | WP05 | |
| T026 | 030/034 edits | WP05 | |
| T027 | Red-first test (own commit, RED) | WP06 | |
| T028 | A1 and A2 edits | WP06 | |
| T029 | A3 and A5 (data file, asset loader, tests/docs updates) | WP06 | |
| T030 | A4 (the same-change rule owner) and the validate vocabulary mapping | WP06 | |
| T031 | Curation fold and delete, plus the handoff | WP06 | |
| T032 | Red-first test (own commit, RED) | WP07 | |
| T033 | Reconciler and 024/025 prose | WP07 | |
| T034 | Fold and delete the locality tactic | WP07 | |
| T035 | Review-tactic layering | WP07 | |
| T036 | `boring-code-review` kind change | WP07 | |
| T037 | In-house moves (internal pack and fragment) | WP07 | |
| T038 | Red-first test `tests/doctrine/test_supply_chain_single_owner.py` (own commit, RED) | WP08 | |
| T039 | 051 and the neutral tactic | WP08 | |
| T040 | Toolguides and `dependency-hygiene` | WP08 | |
| T044 | Red-first edge test `tests/doctrine/drg/test_single_owner_edges.py` and delivery test (own commit, RED) | WP09 | |
| T045 | Curated edges, overlay fixes, FR-014 conditional | WP09 | |
| T046 | REFINES wording and doc parity | WP09 | |
| T047 | Activation packs and action indexes | WP09 | |
| T048 | Regenerate, then run the gates | WP09 | |
| T049 | Ledgers, reachability and pinned-test updates | WP09 | |
| T050 | Cascade totals and census counts (grep tests for pinned cascade totals; update with rationale) | WP09 | |
| T051 | Red-first test `tests/doctrine/test_dogfood_single_owner.py` (own commit, RED) | WP10 | |
| T052 | Dogfood the migration and charter regeneration | WP10 | |
| T053 | Charter prose and docs | WP10 | |
| T054 | Glossary | WP10 | |
| T055 | Red-first test `tests/doctrine/test_served_prompts_single_owner.py` (own commit, RED) | WP11 | |
| T056 | Prompts and guidelines (the guidelines are out-of-map) | WP11 | |
| T057 | Step contracts: slugs, supply-chain and disposition references | WP11 | |
| T058 | The #5078 implement prompt | WP11 | |
| T059 | Profiles: supply chain, disposition and the checklist retarget | WP11 | |

## Work Packages

### WP01 — Consumer retirement migration (shared, data-driven)

**Prompt**: [tasks/WP01-retirement-migration.md](tasks/WP01-retirement-migration.md) · **Requirements**: FR-009 · **Dependencies**: none

T001 Red-first tests (own commit, RED) (WP01)
T002 Extract `_retired_activation.py` (WP01)
T003 Thin rtk migration (WP01)
T004 The new migration (WP01)
T005 Allowlists (WP01)

### WP02 — Guidelines single owner (#5202, P0)

**Prompt**: [tasks/WP02-guidelines-single-owner.md](tasks/WP02-guidelines-single-owner.md) · **Requirements**: FR-016, FR-017 · **Dependencies**: none

T006 Red-first test (own commit, RED) (WP02)
T007 Merge the four software-dev files (onto the `mission-steps` base) (WP02)
T008 Repoint the loader (WP02)
T009 Delete the 17 `actions/*/guidelines.md` (WP02)
T010 Docs (WP02)

### WP03 — Printed commit recipes use safe-commit (#5078 code)

**Prompt**: [tasks/WP03-safe-commit-recipes.md](tasks/WP03-safe-commit-recipes.md) · **Requirements**: FR-018 · **Dependencies**: none

T011 Red-first test (own commit, RED) (WP03)
T012 A single recipe helper (WP03)
T013 Replace the recipes (WP03)
T014 Update pinned output tests (WP03)

### WP04 — Squad doctrine single owner (#5219 content + disposition contract)

**Prompt**: [tasks/WP04-squad-single-owner.md](tasks/WP04-squad-single-owner.md) · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-007, FR-011, FR-013, FR-027 · **Dependencies**: WP02

T015 Red-first owner test (own commit, RED) (WP04)
T016 Rewrite the procedure (WP04)
T017 Shrink the skill (WP04)
T018 Re-point the lens guard (WP04)
T019 Delete the styleguide and repoint the references (WP04)
T020 Fixed-lens prose and modes (WP04)

### WP05 — Testing, bug-fixing and BDD doctrine owners (#5220)

**Prompt**: [tasks/WP05-testing-bugfix-bdd.md](tasks/WP05-testing-bugfix-bdd.md) · **Requirements**: FR-020, FR-021, FR-022, FR-023 · **Dependencies**: WP02

T021 Red-first owner test (own commit, RED) (WP05)
T022 Fold the checklist into `test-first-bug-fixing`, then delete it (WP05)
T023 Terms: one owner (WP05)
T024 Mutation (WP05)
T025 BDD (WP05)
T026 030/034 edits (WP05)

### WP06 — Common Docs doctrine owners (#5221 A)

**Prompt**: [tasks/WP06-common-docs-owners.md](tasks/WP06-common-docs-owners.md) · **Requirements**: FR-024 · **Dependencies**: WP02

T027 Red-first test (own commit, RED) (WP06)
T028 A1 and A2 edits (WP06)
T029 A3 and A5 (data file, asset loader, tests/docs updates) (WP06)
T030 A4 (the same-change rule owner) and the validate vocabulary mapping (WP06)
T031 Curation fold and delete, plus the handoff (WP06)

### WP07 — Change-scope reconciler, review tactics, kind change and in-house moves (#5221 B, D)

**Prompt**: [tasks/WP07-change-scope-review-tactics.md](tasks/WP07-change-scope-review-tactics.md) · **Requirements**: FR-023, FR-025, FR-028 · **Dependencies**: WP02

T032 Red-first test (own commit, RED) (WP07)
T033 Reconciler and 024/025 prose (WP07)
T034 Fold and delete the locality tactic (WP07)
T035 Review-tactic layering (WP07)
T036 `boring-code-review` kind change (WP07)
T037 In-house moves (internal pack and fragment) (WP07)

### WP08 — Supply-chain doctrine owner: DIRECTIVE_051, neutral tactic, per-ecosystem toolguides (#5221 C)

**Prompt**: [tasks/WP08-supply-chain-owner.md](tasks/WP08-supply-chain-owner.md) · **Requirements**: FR-026 · **Dependencies**: WP02

T038 Red-first test `tests/doctrine/test_supply_chain_single_owner.py` (own commit, RED) (WP08)
T039 051 and the neutral tactic (WP08)
T040 Toolguides and `dependency-hygiene` (WP08)

### WP09 — DRG wiring, activation packs and regeneration (single owner of generated surfaces)

**Prompt**: [tasks/WP09-drg-wiring-regeneration.md](tasks/WP09-drg-wiring-regeneration.md) · **Requirements**: FR-005, FR-006, FR-008, FR-012, FR-014, FR-021, FR-023 · **Dependencies**: WP01, WP04, WP05, WP06, WP07, WP08, WP11

T044 Red-first edge test `tests/doctrine/drg/test_single_owner_edges.py` and delivery test (own commit, RED) (WP09)
T045 Curated edges, overlay fixes, FR-014 conditional (WP09)
T046 REFINES wording and doc parity (WP09)
T047 Activation packs and action indexes (WP09)
T048 Regenerate, then run the gates (WP09)
T049 Ledgers, reachability and pinned-test updates (WP09)
T050 Cascade totals and census counts (grep tests for pinned cascade totals; update with rationale) (WP09)

### WP10 — Dogfood the migration, charter, docs and glossary

**Prompt**: [tasks/WP10-dogfood-docs-glossary.md](tasks/WP10-dogfood-docs-glossary.md) · **Requirements**: FR-010, FR-015, FR-023 · **Dependencies**: WP01, WP09

T051 Red-first test `tests/doctrine/test_dogfood_single_owner.py` (own commit, RED) (WP10)
T052 Dogfood the migration and charter regeneration (WP10)
T053 Charter prose and docs (WP10)
T054 Glossary (WP10)

### WP11 — Served prompts, step contracts and profiles reference the owners (#5221 C/E, #5078 prompt, #5220 profiles)

**Prompt**: [tasks/WP11-served-prompts-contracts-profiles.md](tasks/WP11-served-prompts-contracts-profiles.md) · **Requirements**: FR-019, FR-020, FR-026, FR-027, FR-028 · **Dependencies**: WP02, WP04, WP05, WP08

T055 Red-first test `tests/doctrine/test_served_prompts_single_owner.py` (own commit, RED) (WP11)
T056 Prompts and guidelines (the guidelines are out-of-map) (WP11)
T057 Step contracts: slugs, supply-chain and disposition references (WP11)
T058 The #5078 implement prompt (WP11)
T059 Profiles: supply chain, disposition and the checklist retarget (WP11)
