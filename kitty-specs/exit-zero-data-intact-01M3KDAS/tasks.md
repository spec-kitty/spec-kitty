# Work Packages: Exit 0 means your data is intact

**Inputs**: Design documents from `kitty-specs/exit-zero-data-intact-01M3KDAS/`
**Prerequisites**: plan.md (design decisions D1–D7), spec.md (FR-001–FR-022), research.md (R1–R6 evidence), data-model.md, contracts/failure-surface.md, quickstart.md (red-first recipes)

**Tests**: explicitly required by the spec (NFR-001 red-first per issue, NFR-002 destructive-fixture invariant). Every code WP writes an issue-pinned `@pytest.mark.regression` reproduction that fails on the pre-fix code through the real CLI entry point, makes it pass, then converts it into focused unit/integration tests with the `regression` marker removed (ADR `2026-07-17-1`).

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each code WP opens with a behaviour-preserving campsite step on the functions it touches (brownfield standing order 2). Test files are separate per WP so parallel lanes never collide. `docs/changelog/CHANGELOG.md` is owned only by WP08.

**Prompt files**: one per WP in `tasks/`. Deep implementation detail lives in the prompt files.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Create `kernel/text_decode.py` (`decode_unambiguous`, `normalize_newlines`) | WP01 | |
| T002 | Unit tests for the kernel text primitives | WP01 | [P] |
| T003 | Delegate charter encoding recovery's BOM/strict steps, fix UTF-32 ordering (red-first) | WP01 | |
| T004 | `hash_content` uses `normalize_newlines` (non-regression) | WP01 | [P] |
| T005 | WP01 gate run | WP01 | |
| T006 | Campsite: typing findings in decisions service/doctor | WP02 | |
| T007 | Red-first #4919 CLI repros (index divergence, legacy pair, unfoldable, stale status) | WP02 | |
| T008 | Shared transition rule + order-independent fold | WP02 | |
| T009 | Diagnose runs the fold and compares folded status | WP02 | |
| T010 | Repair exits non-zero on malformed, keeps decisions; help text | WP02 | |
| T011 | Convert repros; WP02 gate run | WP02 | |
| T012 | Campsite + one leaf `is_assigned_mission_number` definition | WP03 | |
| T013 | Red-first #4900 repros (driver null, sequential consolidates, hand-numbered, resume) | WP03 | |
| T014 | Merge driver: unassigned target number is unset | WP03 | |
| T015 | Write the number into the target tree via the bookkeeping commit | WP03 | |
| T016 | Read back on target; announce after verification; baked flag + resume | WP03 | |
| T017 | Fault-injected mismatch fails non-zero | WP03 | |
| T018 | Convert repros; WP03 gate run | WP03 | |
| T019 | Red-first #4933 CLI repros (root checkout + lane worktree) and controls | WP04 | |
| T020 | Depth-exact `meta.json` anchor in `is_self_bookkeeping_churn` | WP04 | |
| T021 | Allowlist negative cases + caller-class tests | WP04 | [P] |
| T022 | Convert repros; WP04 gate run | WP04 | |
| T023 | Campsite + `SettingsNotDecodableError` | WP05 | |
| T024 | Red-first #4940 repros (sync-hooks, live-work, init/upgrade writer) | WP05 | |
| T025 | `_load`/`_save` use `decode_unambiguous`, byte backup, typed refusal | WP05 | |
| T026 | `prepare_commands`/`apply_prepared` path | WP05 | |
| T027 | Read-only probes report undecodable instead of crashing | WP05 | [P] |
| T028 | CLI surfacing (sync-hooks, live-work install/uninstall) | WP05 | |
| T029 | Convert repros; WP05 gate run | WP05 | |
| T030 | Campsite: typing findings in skills installer/verifier | WP06 | |
| T031 | Red-first #4998 repros (doctrine skills, command skills, convergence, consent) | WP06 | |
| T032 | Normalise newlines in `ensure_skill_frontmatter` | WP06 | |
| T033 | Normalise at the command-skill decode, before SPDD/description | WP06 | |
| T034 | `.gitattributes` `eol=lf` for shipped sources + test | WP06 | [P] |
| T035 | Convert repros; WP06 gate run | WP06 | |
| T036 | Red-first #4964 repro parametrised over every migrate subcommand | WP07 | |
| T037 | Extract forward-or-refuse helper for group flags | WP07 | |
| T038 | Ratchets: trailing flag, `--no-dry-run`, no-subcommand path | WP07 | |
| T039 | Convert repros; WP07 gate run | WP07 | |
| T040 | CHANGELOG `[Unreleased]` entry | WP08 | |
| T041 | Docs for changed contracts (doctor decisions exit, settings refusal, migrate flags) | WP08 | [P] |
| T042 | Docs index/freshness + terminology guard | WP08 | |

---

## Work Package WP01: Kernel text primitives (Priority: P0, foundation)

**Goal**: One dependency-free, non-guessing decode rule and one newline normaliser, reused by charter; fixes the latent UTF-32-LE mis-decode in `recover()`.
**Independent Test**: `tests/kernel/test_text_decode.py` plus a charter test proving `recover()` reports `utf-32-le` for a UTF-32-LE BOM input.
**Prompt**: `tasks/WP01-kernel-text-primitives.md`
**Requirement Refs**: FR-014

### Included Subtasks

T001 Create `kernel/text_decode.py` (WP01)
T002 Unit tests for the kernel text primitives (WP01)
T003 Delegate charter encoding recovery's BOM/strict steps, fix UTF-32 ordering (WP01)
T004 `hash_content` uses `normalize_newlines` (WP01)
T005 WP01 gate run (WP01)

### Implementation Notes

- Standard library only in `kernel/` (C-002; review-enforced, not test-enforced).
- `decode_unambiguous(data: bytes) -> tuple[str, str] | None`; BOMs checked UTF-32 before UTF-16.

### Parallel Opportunities

- T002 and T004 can proceed in parallel once T001 exists.

### Dependencies

- None (foundation). WP05 and WP06 depend on it.

### Risks & Mitigations

- `recover()` output changes for a UTF-32-LE BOM input: pinned by a new charter test, intentional.

**Estimated prompt size**: ~220 lines

---

## Work Package WP02: Decisions survive defer-then-resolve and repair (Priority: P1)

**Goal**: #4919 — the documented defer→resolve flow folds correctly (new and existing logs, any order); diagnose is truthful; repair never erases.
**Independent Test**: CLI open→defer→resolve, delete `index.json`, `doctor decisions --repair` rebuilds the decision as resolved; an unfoldable history makes repair exit 1 and keeps the decision.
**Prompt**: `tasks/WP02-decisions-defer-resolve-repair.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004

### Included Subtasks

T006 Campsite: typing findings in decisions service/doctor (WP02)
T007 Red-first #4919 CLI repros (WP02)
T008 Shared transition rule + order-independent fold (WP02)
T009 Diagnose runs the fold and compares folded status (WP02)
T010 Repair exits non-zero on malformed, keeps decisions; help text (WP02)
T011 Convert repros; WP02 gate run (WP02)

### Dependencies

- None.

### Risks & Mitigations

- The documented "doctor decisions always exits 0" contract changes for `--repair` with malformed decisions (C-007; docs in WP08).
- `--json` must emit exactly one JSON document before exiting 1.

**Estimated prompt size**: ~300 lines

---

## Work Package WP03: Truthful mission numbering (Priority: P1)

**Goal**: #4900 — the number `spec-kitty consolidate` announces is the number recorded on the target branch; mismatch fails non-zero; resume re-verifies.
**Independent Test**: two sequential consolidations record 1 and 2 on the target; `merge-driver-meta` keeps a mission-side number over a null target.
**Prompt**: `tasks/WP03-truthful-mission-numbering.md`
**Requirement Refs**: FR-005, FR-006, FR-007

### Included Subtasks

T012 Campsite + one leaf `is_assigned_mission_number` definition (WP03)
T013 Red-first #4900 repros (WP03)
T014 Merge driver: unassigned target number is unset (WP03)
T015 Write the number into the target tree via the bookkeeping commit (WP03)
T016 Read back on target; announce after verification; baked flag + resume (WP03)
T017 Fault-injected mismatch fails non-zero (WP03)
T018 Convert repros; WP03 gate run (WP03)

### Dependencies

- None. Highest-risk WP (terminus gate path) — review with extra care.

**Estimated prompt size**: ~340 lines

---

## Work Package WP04: User meta.json edits survive consolidation (Priority: P1)

**Goal**: #4933 — only Spec Kitty-owned mission metadata is exempt from the dirty-tree check, in the repository root checkout and in lane worktrees.
**Independent Test**: a dirty tracked `src/app/meta.json` makes `spec-kitty consolidate` exit 1 naming the file, with the edit intact, in both locations.
**Prompt**: `tasks/WP04-user-meta-json-preserved.md`
**Requirement Refs**: FR-008, FR-009, FR-010

### Included Subtasks

T019 Red-first #4933 CLI repros and controls (WP04)
T020 Depth-exact `meta.json` anchor (WP04)
T021 Allowlist negative cases + caller-class tests (WP04)
T022 Convert repros; WP04 gate run (WP04)

### Dependencies

- None. Tests exercise `consolidation/executor.py` gates owned by WP03 but WP04 does not edit that file.

**Estimated prompt size**: ~220 lines

---

## Work Package WP05: Agent settings file is never replaced (Priority: P1)

**Goal**: #4940 — provably-encoded `.claude/settings.json` files merge with every entry kept (original bytes backed up before re-encoding); anything else is refused untouched, non-zero.
**Independent Test**: UTF-16/BOM fixtures keep all user entries and Spec Kitty session hooks; the issue's cp1252 fixture stays byte-identical with exit 1, via `agent config sync --sync-hooks` and `live-work install`.
**Prompt**: `tasks/WP05-agent-settings-preserved.md`
**Requirement Refs**: FR-011, FR-012, FR-013, FR-014

### Included Subtasks

T023 Campsite + `SettingsNotDecodableError` (WP05)
T024 Red-first #4940 repros (WP05)
T025 `_load`/`_save` use `decode_unambiguous`, byte backup, typed refusal (WP05)
T026 `prepare_commands`/`apply_prepared` path (WP05)
T027 Read-only probes report undecodable (WP05)
T028 CLI surfacing (WP05)
T029 Convert repros; WP05 gate run (WP05)

### Dependencies

- Depends on WP01.

**Estimated prompt size**: ~320 lines

---

## Work Package WP06: Line-ending-safe skill rendering (Priority: P1)

**Goal**: #4998 — CRLF sources render byte-identically to LF sources for doctrine skills and command skills; corrupted manifest-matching installs converge; shipped sources pinned to LF.
**Independent Test**: CRLF vs LF render comparison; seeded corrupted install converges under `upgrade`; user-edited file still needs consent.
**Prompt**: `tasks/WP06-crlf-safe-skill-rendering.md`
**Requirement Refs**: FR-015, FR-016, FR-017, FR-018, FR-019

### Included Subtasks

T030 Campsite: typing findings in skills installer/verifier (WP06)
T031 Red-first #4998 repros (WP06)
T032 Normalise in `ensure_skill_frontmatter` (WP06)
T033 Normalise at the command-skill decode (WP06)
T034 `.gitattributes` `eol=lf` + test (WP06)
T035 Convert repros; WP06 gate run (WP06)

### Dependencies

- Depends on WP01.

**Estimated prompt size**: ~300 lines

---

## Work Package WP07: Migrate group flags are honoured or refused (Priority: P2)

**Goal**: #4964 — `migrate --dry-run <sub>` never runs the real migration; unforwardable group flags are a usage error.
**Independent Test**: parametrised over every registered migrate subcommand; the working tree is unchanged.
**Prompt**: `tasks/WP07-migrate-group-flags.md`
**Requirement Refs**: FR-020, FR-021, FR-022

### Included Subtasks

T036 Red-first #4964 repro parametrised over every subcommand (WP07)
T037 Extract forward-or-refuse helper (WP07)
T038 Ratchets: trailing flag, `--no-dry-run`, no-subcommand path (WP07)
T039 Convert repros; WP07 gate run (WP07)

### Dependencies

- None.

**Estimated prompt size**: ~210 lines

---

## Work Package WP08: Changelog and documentation closeout (Priority: P2)

**Goal**: Record the user-visible changes and update documentation for the changed contracts (C-007).
**Independent Test**: docs freshness check reports 0 errors; terminology guard passes.
**Prompt**: `tasks/WP08-changelog-and-docs.md`
**Requirement Refs**: NFR-003

### Included Subtasks

T040 CHANGELOG `[Unreleased]` entry (WP08)
T041 Docs for changed contracts (WP08)
T042 Docs index/freshness + terminology guard (WP08)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06, WP07.

**Estimated prompt size**: ~160 lines

---

## Parallelization

- Lane-parallel from the start: WP01, WP02, WP03, WP04, WP07.
- After WP01: WP05 and WP06 in parallel.
- WP08 last.
- MVP: WP02 + WP03 + WP04 (the three silent-loss paths on default flows); WP01 unblocks WP05/WP06.
