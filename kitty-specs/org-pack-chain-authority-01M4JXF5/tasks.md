# Tasks: One org-pack chain authority (#6006)

**Mission**: `org-pack-chain-authority-01M4JXF5` · **Branch**: `kitty/org-pack-chain-authority-stack` (stacked on PR #6005)
**Planning base / merge target**: `kitty/org-pack-chain-authority-stack`

Subtask completion is event-sourced via `spec-kitty agent tasks mark-status Txxx --status done`. Rows below are reference rows, not checkboxes.

**Gate scope (operator ruling):** the empty-allowlist gate (WP06) is path-scoped to `src/charter/**` + `src/specify_cli/cli/commands/charter/**`; every chain-deriving caller in those surfaces migrates onto `resolve_pack_chain()` this mission. The ~12 non-charter callers + tree-wide gate are a named follow-up (see spec Out of Scope).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add `resolve_pack_chain(repo_root, *, strict)` authority | WP01 | |
| T002 | Re-point `resolve_org_root_chain` to delegate to the authority | WP01 | |
| T003 | Re-point `resolve_org_dirs` onto `resolve_pack_chain(strict=False)` (preserve WARNING) | WP01 | |
| T004 | Strict posture: raise naming the unfetched pack + `spec-kitty charter fetch` | WP01 | |
| T005 | Red-first repro: two-pack lenient ordering + strict-raise-on-missing | WP01 | |
| T006 | ruff/mypy clean, complexity ≤15 | WP01 | |
| T007 | `effective_set`: declared→strict authority; readable/fallback→lenient authority | WP02 | [P] |
| T008 | `preset_application`: `_Roots.of`/`_available_mission_types`→authority | WP02 | [P] |
| T009 | `org_charter`: `resolve_org_root_chain`→`resolve_pack_chain` (keep layer_roots pairing) | WP02 | [P] |
| T010 | `deactivate` + `_resynthesis_preflight`: →`resolve_pack_chain` | WP08 | [P] |
| T011 | `interview` + `context` (re-point) + `pack_asset`: →`resolve_pack_chain` | WP08 | [P] |
| T012 | Behavioural positive control: pack-2 artifact observable via effective_set + preset_application | WP02 | |
| T013 | ruff/mypy; confirm `_org_scan_dirs` flat-wins test green (NFR-005) | WP02 | |
| T014 | `list_cmd` templates (:88): full-chain org template tier | WP03 | [P] |
| T015 | `list_cmd` availability (:197/:245): full-chain org scan | WP03 | [P] |
| T016 | `invocation_context`: remove dead `ProjectContext.org_root` + `org_roots[0]` | WP03 | [P] |
| T017 | `action_governance_bundle`: drop legacy `org_root` param; migrate :209 to authority (lenient) | WP03 | [P] |
| T018 | Update `TestListAllLayersBackCompat` (SUPERSEDE pack-2-hidden; KEEP two) + `test_invocation_context` | WP03 | |
| T019 | Reader regression repros; ruff/mypy; NFR-001 dict unchanged | WP03 | |
| T020 | `_scan_layer_dirs`: add `org_root_chain`; one ORG pair per root last-declared-first; fallback | WP04 | [P] |
| T021 | `list_available` / `list_available_detailed`: thread `org_root_chain` | WP04 | |
| T022 | `activate`: pass chain to scan; migrate `activate.py` `resolve_org_root_chain` calls | WP04 | |
| T023 | Remove `_activate_cascade_target`; collapse call site to single `manager.activate` | WP04 | |
| T024 | Retry-loop repro: pack-2 artifact activates via single scan; assert cascade helper gone | WP04 | |
| T025 | ruff/mypy; pins `test_pack_manager*`, `test_mission_type_path_layout_ssot` green | WP04 | |
| T026 | `requirement_kinds.py`: frozen models, `extra=forbid` | WP05 | [P] |
| T027 | `resolve_org_requirement_kinds` sibling: last-matching-file-wins, whole-file, fail-closed | WP05 | [P] |
| T028 | `load_requirement_kinds` tier walk: built-in→org(strict chain)→project; module cache | WP05 | |
| T029 | Project tier `.kittify/doctrine/missions/<type>/requirement-kinds.yaml` (project wins) [Div A] | WP05 | |
| T030 | Fail-closed: invalid refuses; missing-declared refuses via strict chain [Div B]; default constant | WP05 | |
| T031 | Loader tests (override, corrupted-refusal, project-wins); ruff/mypy | WP05 | |
| T032 | `test_org_pack_chain_single_authority.py`: AST census, path-scoped, module-ownership, empty allowlist | WP06 | |
| T033 | Non-vacuity: planted-violation + owner-bypass + file-count-floor controls | WP06 | |
| T034 | Confirm invariant over the charter scope (zero in-scope violations) | WP06 | |
| T035 | ruff/mypy; gate green over the charter scope | WP06 | |
| T036 | `manifest_loader`: migrate `load_manifest`'s `_resolve_existing_org_roots` onto the authority (lenient) | WP05 | |
| T037 | ruff/mypy; charter-CLI regression suites green | WP08 | |
| T038 | `active_charter_service_builder`: `_self_resolve_existing_org_roots`→authority (lenient) | WP07 | [P] |
| T039 | `_drg_helpers`: `resolve_existing_org_roots`→authority (lenient) | WP07 | [P] |
| T040 | `language_vocabulary`: `resolve_existing_org_roots` loop→authority (lenient) | WP07 | [P] |
| T041 | `profile_resolution` + `project_registration` + `skill_preparation`: →authority | WP07 | [P] |
| T042 | `charter/offering/resolver` loops + `charter/drg` re-export→authority; ruff/mypy | WP07 | |

## Work Packages

### WP01 — Pack chain authority *(foundation)*
- **Goal**: `resolve_pack_chain(repo_root, *, strict)` as the sole producer of the ordered, existing chain (last-declared-wins), strict + lenient. Prompt: `tasks/WP01-pack-chain-authority.md`
- **Requirements**: FR-001, FR-007, NFR-004 · **Subtasks**: T001–T006 · **Dependencies**: none

### WP02 — Migrate charter-activation core consumers
- **Goal**: Route `effective_set`, `preset_application`, `org_charter` through the authority (strict/lenient per surface). Prompt: `tasks/WP02-migrate-chain-consumers.md`
- **Requirements**: FR-002, FR-008, NFR-004, NFR-005 · **Subtasks**: T007, T008, T009, T012, T013 · **Dependencies**: WP01

### WP03 — Fix the pack-1-only readers
- **Goal**: `charter list --all` full chain; remove dead `ProjectContext.org_root`; drop `action_governance_bundle` legacy param (migrate its :209 call to the authority). Prompt: `tasks/WP03-pack-one-only-readers.md`
- **Requirements**: FR-003, FR-005, NFR-001 · **Subtasks**: T014–T019 · **Dependencies**: WP01

### WP04 — Retire the retry loop (widen ActiveCharterManager)
- **Goal**: Remove `_activate_cascade_target`; widen `ActiveCharterManager` with `org_root_chain`; migrate `activate.py` chain calls. Prompt: `tasks/WP04-retire-retry-loop.md`
- **Requirements**: FR-004, NFR-001, NFR-005 · **Subtasks**: T020–T025 · **Dependencies**: WP01

### WP05 — Requirement-kinds loader seam (#5956) + manifest_loader migration
- **Goal**: Model + `load_requirement_kinds()` through built-in→org(strict)→project, whole-file, fail-closed; and migrate `load_manifest`'s existing chain call onto the authority. Prompt: `tasks/WP05-requirement-kinds-loader.md`
- **Requirements**: FR-009, FR-010, FR-011, FR-002, SC-004 · **Subtasks**: T026–T031, T036 · **Dependencies**: WP01

### WP06 — Empty-allowlist architectural gate *(path-scoped; lands last)*
- **Goal**: AST-census gate scoped to `src/charter/**` + `src/specify_cli/cli/commands/charter/**`, empty allowlist, non-vacuity controls. Prompt: `tasks/WP06-empty-allowlist-gate.md`
- **Requirements**: FR-006, NFR-002 · **Subtasks**: T032–T035 · **Dependencies**: WP02, WP03, WP04, WP05, WP07, WP08

### WP07 — Migrate remaining charter-activation/offering consumers
- **Goal**: Route the remaining charter-tier primitive callers (`active_charter_service_builder`, `_drg_helpers`, `language_vocabulary`, `profile_resolution`, `project_registration`, `skill_preparation`, `offering/resolver`, `charter/drg` re-export) through the authority. Mechanical, lenient. Prompt: `tasks/WP07-migrate-activation-offering.md`
- **Requirements**: FR-002 · **Subtasks**: T038–T042 · **Dependencies**: WP01

### WP08 — Migrate CLI charter consumers
- **Goal**: Route `deactivate`, `_resynthesis_preflight`, `interview`, `context` (re-point), `pack_asset` through the authority. Prompt: `tasks/WP08-migrate-cli-charter.md`
- **Requirements**: FR-002 · **Subtasks**: T010, T011, T037 · **Dependencies**: WP01

## Dependency graph

```
WP01 ──┬── WP02 ──┐
       ├── WP03 ──┤
       ├── WP04 ──┤
       ├── WP05 ──┼── WP06  (gate, path-scoped, last)
       ├── WP07 ──┤
       └── WP08 ──┘
```

## MVP / sequencing

WP01 is the foundation. WP02–WP05, WP07, WP08 parallelize after it (each is a
distinct, non-overlapping file set). WP06 (the gate) lands last — it goes red
until every in-scope migration is complete.
