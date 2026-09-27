---
description: "Work package task list for mission consolidate-canonical-terminology-01M3GSSV (#3080)"
---

# Work Packages: Consolidate — canonical lane-consolidation terminology

**Inputs**: Design documents from `kitty-specs/consolidate-canonical-terminology-01M3GSSV/`
**Prerequisites**: [plan.md](./plan.md) (required — see **Post-Plan Brownfield Amendments A1–A6**, binding), [spec.md](./spec.md) (user stories, FR/NFR/C), [research.md](./research.md), [data-model.md](./data-model.md), [occurrence_map.yaml](./occurrence_map.yaml) (**the per-site classification authority — sole authority for rename-vs-keep, DIRECTIVE_035**).

**Tests**: This is a rename mission with a hard behavior-preservation contract (NFR-001) and a red-first drift-guard proof (FR-009/SC-003). Tests are mandatory throughout.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP references a matching prompt in `tasks/`.

## Decomposition rationale (why 4 WPs, why WP01 is one atomic package)

The plan adjudicated (Post-Plan Amendment **A1**) that the physical `merge/`→`consolidation/`
package rename **atomically breaks every importer** — including the CLI command file, the
delegation seams (`mission.py:323`, `mission_accept_merge.py:252`), and the unowned external
importer `orchestrator_api/commands.py`. These cannot be independent green commits, so the
rename + command surface + drift-guard baseline + machine-contract regeneration are **one
write-scope-atomic WP (WP01)**. WP01 legitimately exceeds the 10-subtask guideline — this is
the documented atomic exception (**A1/A6**); it stays ONE WP with logically grouped subtasks.
The three downstream WPs (WP02 gate/agents, WP03 packs templates, WP04 docs prose) have disjoint
write scopes, all depend only on WP01, and may run in parallel.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Include precise file paths or modules.
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single CLI package: `src/specify_cli/`, plus `src/charter/`, `src/mission_runtime/`, `src/runtime/`; tests under `tests/`; consumer doctrine under `packs/built-in/`; docs under `docs/`.

---

## Work Package WP01: Atomic rename + guard + machine contracts (Priority: P1) 🎯 CORE

**Goal**: Physically rename the lane-consolidation module/package/command surface (`merge/`→`consolidation/`, `lanes/merge.py`→`lanes/consolidation.py`, `cli/commands/merge.py`→`consolidate.py`, `tests/merge/`→`tests/consolidation/`), rename the lane-consolidation-sense symbols, make `consolidate` the primary CLI command with `merge` a hidden migration-error stub, repoint every internal + external importer and delegation seam, rename the orchestrator command `merge-mission`→`consolidate-mission`, extend the drift-guard (baseline paths + new command-surface ratchet), and regenerate the generated machine contracts — all in one write-scope-atomic commit set. Frozen KEEPS stay verbatim.
**Independent Test**: `spec-kitty consolidate --mission <fixture>` folds lanes identically to former `merge`; `spec-kitty merge` exits non-zero with a "renamed to `consolidate`" message; `spec-kitty consolidate --resume` reads the unchanged `state.json`; the former `tests/merge/` (now `tests/consolidation/`) suite is green with 0 regressions; `test_no_legacy_terminology.py` bites a new `spec-kitty merge` and passes on `git merge`/publish.
**Prompt**: `tasks/WP01-atomic-rename-guard-contracts.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-009, FR-010; NFR-001, NFR-002, NFR-003, NFR-004; C-001, C-002, C-003, C-004, C-007

### Included Subtasks

T001 Physically rename `src/specify_cli/merge/` → `src/specify_cli/consolidation/` (git mv) + fix intra-package imports
T002 Rename `src/specify_cli/lanes/merge.py` → `lanes/consolidation.py`; symbols `LaneMergeResult`→`LaneConsolidationResult`, `MissionMergeResult`→`MissionConsolidationResult`
T003 Rename symbols across the package: `MergeState`→`ConsolidationState`, `_run_lane_based_merge`→`_run_lane_based_consolidation`; keep frozen `MergeStrategy`/`"merge"` value
T004 Rename `cli/commands/merge.py`→`consolidate.py`; `merge()`→`consolidate()`; register `consolidate` as the primary command
T005 Add the hidden `merge` migration-error stub (non-zero exit, "renamed to `consolidate`" — no working body, no alias)
T006 Repoint delegation seams: `cli/commands/mission.py:323 top_level_merge = _merge` and `mission_accept_merge.py:252` to the `consolidate` body; fix `test_wrapper_delegation.py:130`
T007 [P] Repoint all internal importers + `orchestrator_api/commands.py` (:829/:833/:981/:984/:986/:988)
T008 Rename orchestrator command `merge-mission`→`consolidate-mission` (`orchestrator_api/commands.py:2129`) + `core/upstream_contract.json:92` (keep `:108 merge-feature` forbidden)
T009 Rename `tests/merge/`→`tests/consolidation/` + update all 72 test files + importers; fix `test_merge_compat_surface.py:329`, `test_json_contract_enumeration.py:357`
T010 Fix stale logger name `merge/_constants.py:21`; converge `post-merge` prose in `consolidation/baseline.py` (FR-010); freeze `baseline_merge_commit` wire-key
T011 Update `tests/architectural/_gate_coverage.py:1983 _PRE_MISSION_MAPPED_SRC_DIRS` for the dir rename
T012 Update drift-guard baseline paths `test_no_legacy_terminology.py:360/:362` + `:491 _currently_real`
T013 Add the new command-surface `"spec-kitty merge"` ratchet + historical allowlist + `packs/` scan root (FR-009 fold); red-first + green-on-legit proofs
T014 [P] Regenerate `docs/api/cli-commands.md` + `docs/api/agent-subcommands.md` via `scripts/docs/build_cli_reference.py`
T015 Version bump `pyproject.toml` + `CHANGELOG.md` entry (C-007 — `cli/commands/__init__.py` changed)

### Implementation Notes

- Rename with `git mv` to preserve history; grow public `__all__`, never shrink (#2057).
- Frozen KEEPS (occurrence_map exceptions): `baseline_merge_commit` key, `MergeStrategy`/`"merge"` value, `state.json` filename + `.kittify/runtime/merge/<id>/` dir, merge-driver plumbing, `trigger_mode` `post_merge` (schema.py). Never rename.
- No re-export shim (A3): repoint importers directly.

### Dependencies

- None (dependency root of the mission).

### Risks & Mitigations

- Half-rename / whack-a-field → occurrence_map + full `tests/consolidation/` + import-boundary tests.
- Renaming a frozen KEEP → verify SC-005 positive controls; assert `baseline_merge_commit`, `MergeStrategy="merge"` unchanged.
- Red tree mid-mission → the rename lands as one commit set (A1); do not stage partial importer updates.

---

## Work Package WP02: Gate-step command surface + agents/skills regeneration (Priority: P1)

**Goal**: Rename the mission gate-step/command surface (`command_installer.py` list/description/command-map `merge`→`consolidate`), rename the skill `spk-gate-merge`→`spk-gate-consolidate` at its source, and regenerate the 13 agent command/skill copies via `spec-kitty upgrade`.
**Independent Test**: After `spec-kitty upgrade`, at least `.claude`, `.codex`, `.opencode` expose `consolidate` / `spk-gate-consolidate` (not `merge` / `spk-gate-merge`); SC-004 verified.
**Prompt**: `tasks/WP02-gate-step-agents-skills.md`
**Requirement Refs**: FR-006; NFR-003, NFR-004; C-005

### Included Subtasks

T016 `src/specify_cli/skills/command_installer.py` (:99 list, :110 description, :116 command-map merge→consolidate)
T017 Rename skill source `src/charter/offering/skills/spk-gate-merge/`→`spk-gate-consolidate/` + `.kittify/command-skills-manifest.json`
T018 Regenerate the 13 agent command/skill copies + command-skills via `spec-kitty upgrade`
T019 Verify SC-004 on `.claude`, `.codex`, `.opencode`

### Dependencies

- Depends on WP01 (consolidate command must exist before the gate-step/skill names it).

### Risks & Mitigations

- Editing generated copies instead of source (C-005) → edit `command_installer.py` + `src/charter/offering/skills/` only, then regenerate.
- Incomplete regeneration across 13 agents → run upgrade, verify the three named agents.

---

## Work Package WP03: Prompt templates + toolguides (Priority: P1)

**Goal**: Convert lane-consolidation-sense `spec-kitty merge`→`spec-kitty consolidate` in the `packs/**` prompt templates and toolguides, classifying each site against `occurrence_map.yaml`.
**Independent Test**: Grep the owned packs/ files → no active lane-consolidation-sense `spec-kitty merge`; git-merge/publish prose untouched.
**Prompt**: `tasks/WP03-prompt-templates-toolguides.md`
**Requirement Refs**: FR-007; NFR-004; C-003, C-005, C-006

### Included Subtasks

T020 `mission-steps/software-dev/accept/prompt.md` (:105, :120) + `specify/prompt.md` (:591)
T021 `packs/built-in/toolguides/POWERSHELL_SYNTAX.md` (:54)
T022 [P] Classify + convert other lane-consolidation-sense `packs/**` sites: `directives/045-prs-only-and-read-intent.directive.yaml`, `procedures/mission-wrap-up-sequence.procedure.yaml`
T023 [P] Confirm each converted site is Sense 1 (lane consolidation) per occurrence_map; leave any git-merge/publish sense verbatim

### Dependencies

- Depends on WP01 (the canonical command word must be settled before templates name it).

### Risks & Mitigations

- Missing a template that regenerates stale agent guidance → grep the whole packs/ tree; classify every hit.
- Converting a git-merge/publish sense by mistake → occurrence_map `manual_review` rubric per site.

---

## Work Package WP04: Docs prose + CLAUDE.md campsite (Priority: P2)

**Goal**: Convert the ~5–8 high-value active doc files to `consolidate` and fix the stale `CLAUDE.md:396` `merge-state.json` reference (modern file is `state.json`). Defer long-tail/archival prose (C-008) and never touch immutable history (kitty-specs/, docs/adr/, docs/changelog/) or generated `docs/api/**` (WP01 owns those).
**Independent Test**: The owned doc files read `consolidate` for the lane-consolidation sense; `CLAUDE.md:396` reads `state.json`; deferred/immutable trees untouched; drift-guard green.
**Prompt**: `tasks/WP04-docs-prose-claude-campsite.md`
**Requirement Refs**: FR-008; NFR-004; C-003, C-006, C-008

### Included Subtasks

T024 `docs/context/orchestration.md` + `docs/context/ops-vs-missions.md`
T025 [P] `docs/architecture/git-workflow.md`, `spec-kitty-mission-workflow.md`, `mission-system.md`
T026 [P] `docs/development/how-to/review-gates.md`, `docs/guides/how-to/missions/accept-and-merge.md`, `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`
T027 Fix `CLAUDE.md:396` stale `merge-state.json` → `state.json` (campsite, DIRECTIVE_025)

### Dependencies

- Depends on WP01 (docs describe the settled command/behavior).

### Risks & Mitigations

- Over-reaching into archival/immutable artifacts → obey occurrence_map exceptions; defer `docs/plans/**`, `docs/adr/**`, `docs/changelog/**`.
- Touching generated `docs/api/**` → owned by WP01; WP04 must not write there.

---

## Dependency & Execution Summary

- **Sequence**: WP01 (atomic root) → { WP02, WP03, WP04 } in parallel.
- **Parallelization**: WP02/WP03/WP04 have disjoint write scopes and may run concurrently after WP01.
- **MVP Scope**: WP01 delivers SC-001/SC-002/SC-003/SC-005; WP02 delivers SC-004.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP02 |
| FR-007 | WP03 |
| FR-008 | WP04 |
| FR-009 | WP01 (shares `test_no_legacy_terminology.py`) |
| FR-010 | WP01 (`consolidation/baseline.py` prose) |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01, WP02, WP03, WP04 |
| NFR-004 | WP01, WP02, WP03, WP04 |
| C-001 | WP01, WP02, WP03, WP04 (occurrence_map authority) |
| C-002 | WP01 |
| C-003 | WP01, WP02, WP03, WP04 |
| C-004 | WP01 |
| C-005 | WP02, WP03 |
| C-006 | WP03, WP04 |
| C-007 | WP01 |
| C-008 | WP04 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Rename merge/ → consolidation/ | WP01 | P1 | No |
| T002 | Rename lanes/merge.py + Lane*Result symbols | WP01 | P1 | No |
| T003 | MergeState→ConsolidationState, _run_lane_based_* | WP01 | P1 | No |
| T004 | cli/commands/merge.py→consolidate.py, primary cmd | WP01 | P1 | No |
| T005 | Hidden merge migration-error stub | WP01 | P1 | No |
| T006 | Repoint delegation seams + test_wrapper_delegation | WP01 | P1 | No |
| T007 | Repoint internal + orchestrator_api importers | WP01 | P1 | Yes |
| T008 | merge-mission→consolidate-mission + upstream_contract | WP01 | P1 | No |
| T009 | tests/merge/→tests/consolidation/ + fixtures | WP01 | P1 | No |
| T010 | logger name, baseline.py prose (FR-010), freeze key | WP01 | P1 | No |
| T011 | _gate_coverage.py:1983 dir rename | WP01 | P1 | No |
| T012 | drift-guard baseline paths :360/:362/:491 | WP01 | P1 | No |
| T013 | new command-surface ratchet + red/green proofs | WP01 | P1 | No |
| T014 | regenerate docs/api/*.md | WP01 | P1 | Yes |
| T015 | version bump + CHANGELOG | WP01 | P1 | No |
| T016 | command_installer.py list/desc/map | WP02 | P1 | No |
| T017 | spk-gate-merge→spk-gate-consolidate source + manifest | WP02 | P1 | No |
| T018 | spec-kitty upgrade regenerates 13 agent copies | WP02 | P1 | No |
| T019 | verify SC-004 on .claude/.codex/.opencode | WP02 | P1 | No |
| T020 | accept/specify prompt.md conversions | WP03 | P1 | No |
| T021 | POWERSHELL_SYNTAX.md conversion | WP03 | P1 | Yes |
| T022 | other packs/** doctrine sites | WP03 | P1 | Yes |
| T023 | per-site Sense-1 classification confirm | WP03 | P1 | Yes |
| T024 | docs/context/ conversions | WP04 | P2 | No |
| T025 | docs/architecture/ conversions | WP04 | P2 | Yes |
| T026 | docs/development + docs/guides/how-to conversions | WP04 | P2 | Yes |
| T027 | CLAUDE.md:396 merge-state.json→state.json | WP04 | P2 | No |

---

> Deep implementation detail lives in the per-WP prompt files under `tasks/`. `occurrence_map.yaml` is the sole authority for which occurrence is rename-vs-keep.
