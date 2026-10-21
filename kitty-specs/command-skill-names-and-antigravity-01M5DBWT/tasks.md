# Tasks: Spec-conformant command skill names + Antigravity skills delivery

**Mission**: `command-skill-names-and-antigravity-01M5DBWT` · **Topology**: single_branch (WPs run
sequentially in the repository root checkout on `issue-6475-6470-command-skill-names`).
**Inputs**: [spec.md](spec.md), [plan.md](plan.md) (read the *Post-plan squad dispositions* table —
it overrides the concern text), [research.md](research.md), [data-model.md](data-model.md),
[occurrence_map.yaml](occurrence_map.yaml).

## Subtask Format: `[Txxx] [P?] Description`

## Path Conventions

Source under `src/`, tests under `tests/` mirroring the source tree, CI under `.github/` and
`scripts/ci/`, docs under `docs/`.

## Work Package WP01: Red-first P0 reproductions (Priority: P0)

**Goal**: commit failing `p0_repro` tests for #6475 and #6470 through `spec-kitty init` before any
fix. **Independent test**: both tests fail on the base commit with `SPEC_KITTY_RUN_P0_REPRO=1`.

### Included Subtasks

T001 Write `@pytest.mark.p0_repro(issue=6475)` init repro asserting hyphenated, spec-valid command skills (WP01)
T002 Write `@pytest.mark.p0_repro(issue=6470)` init repro asserting Antigravity command skills and no `~/.agent/workflows` Spec Kitty files (WP01)
T003 Capture the red run output into the mission traces and commit the tests alone (WP01)

### Dependencies

None.

### Risks & Mitigations

Vacuity: assert literals, never the naming authority; absolute normalised HOME.

## Work Package WP02: Naming authority and invocation rewrite (Priority: P0)

**Goal**: one leaf module owns the command-skill name, path parsing (canonical vs legacy), the
uniqueness assertion, legacy names and the agent-independent invocation rewrite; the renderer and
the pack-skill renderer use it.

### Included Subtasks

T004 Create `skills/command_skill_names.py` (name, rel path, parse canonical/legacy, LEGACY names, invocation rewrite, per-agent UI token) (WP02)
T005 Build-time uniqueness check against charter skills, built-in pack skills, retired and legacy sets (WP02)
T006 Command renderer uses the authority for name, description fallback and body invocation rewrite; `_user_input_block` text (WP02)
T007 Pack-skill renderer: `builtin:` accepts both forms, renders `spec-kitty-<cmd>` (WP02)
T008 Architectural gate: no other module composes `spec-kitty.<cmd>`/`spec-kitty-<cmd>` command-skill names (WP02)

### Dependencies

WP01.

## Work Package WP03: Installer, provider and doctor on the new names (Priority: P0)

**Goal**: the installer writes `spec-kitty-<cmd>`, classifies legacy dotted entries with the
keep-edited rule on every repair path, skips a user folder at a canonical path with a warning, and
doctor/init/ownership read the authority. Includes the init acceptance scenario.

### Included Subtasks

T009 Installer: canonical paths, legacy class (owned+equal → delete, edited → keep+drop entry+warn), never drift-delete legacy (WP03)
T010 Installer: canonical-path collision → per-path skip disposition, batch continues (WP03)
T011 Manifest schema accepts canonical + legacy forms; `verify()` adds `legacy` and `collisions`, orphan scan keyed on the explicit set (WP03)
T012 Provider `command_skills.py`, `ownership.is_projected_skills_path`, init helpers and `_COMMAND_SKILL_AGENTS` from the roster (WP03)
T013 `doctor skills` reports legacy leftovers and collisions (read-only, never feeds `--fix` deletion by name) (WP03)
T014 Acceptance scenario `tests/scenarios/init/` for the collision + step check; update existing tests that pin the dotted path (WP03)

### Dependencies

WP02.

## Work Package WP04: Rename migration and new-invocation notice (Priority: P1)

### Included Subtasks

T015 Migration `4.0.0rc8_command_skill_hyphen_names` (clone-local, idempotent, config-aware, calls the installer) + order manifest entry (WP04)
T016 Migration tests with prior-release dotted bytes, edited file, user folder, missing manifest, worktree, idempotence, ledger record (WP04)
T017 init next-steps and upgrade report print the new invocation; release-note text hook (WP04)

### Dependencies

WP03.

## Work Package WP05: Antigravity command skills and project workflows archive (Priority: P0)

### Included Subtasks

T018 Add antigravity to the roster; remove from `AGENT_COMMAND_CONFIG`, `AGENT_DIRS`, `AGENT_DIR_TO_KEY`; one `configured_slash_agents()` filter; fix every consumer (WP05)
T019 Init/agent config/capability matrix/path matrix wording for Antigravity (WP05)
T020 Migration `4.0.0rc8_retire_antigravity_workflows`: archive marker-proven files to `.kittify/backups/antigravity-workflows/`, symlink refusal, never the dir/foreign files, install skills when configured (WP05)
T021 Tests: registry invariants, init --ai antigravity, migration fixtures (WP05)

### Dependencies

WP03.

## Work Package WP06: Home-folder writer scoped to configured agents (Priority: P1)

### Included Subtasks

T022 Startup passes configured slash agents (none outside a project); `agent config add` triggers its write (WP06)
T023 Freshness stamp per key; scoped calls write it; short-circuit for healthy requested keys; schema field forces first rebuild (WP06)
T024 `~/.agent/workflows` owned cleanup via inventory retire / strict marker+bytes proof; symlink refusal (WP06)
T025 Tests incl. startup timing guard and cleanup fixtures (WP06)

### Dependencies

WP05.

## Work Package WP07: Spec-conformant frontmatter projection and limits (Priority: P1)

### Included Subtasks

T026 `skills/skill_frontmatter.py`: allowed fields, root classification, projection, validation rules mirroring skills-ref (WP07)
T027 Command skills render spec-only frontmatter; charter/pack skill install and verifier apply the root projection; global `~/.agents/skills` writer too (WP07)
T028 Plugin bundles: Claude native projection, Codex/Copilot spec projection (WP07)
T029 Pack skill validation: rendered name ≤64, description incl. Triggers ≤1024 (WP07)
T030 Tests + architectural gate: one frontmatter authority (WP07)

### Dependencies

WP03.

## Work Package WP08: Agent Skills validator in CI (Priority: P2)

### Included Subtasks

T031 `scripts/ci/validate_agent_skills.py` (shipped tree projected + generated project) using `skills-ref==0.1.1` (WP08)
T032 Always-on `ci-router.yml` job + router-gate needs + CI wiring tests (WP08)
T033 Show the check failing on a seeded bad skill (WP08)

### Dependencies

WP07.

## Work Package WP09: Docs, ADR, agent tables and changelog (Priority: P2)

### Included Subtasks

T034 ADR `docs/adr/4.x/2026-10-20-1-...` amending 2026-04-07-1 (+ pointer in the old ADR) (WP09)
T035 CLAUDE.md / AGENTS.md agent tables; docs occurrences per the occurrence map; docs index/freshness (WP09)
T036 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry with release note (new invocations, downgrade caveat) (WP09)

### Dependencies

WP04, WP05, WP06, WP07, WP08.

## Work Package WP10: open-packs text fix and pin bump (Priority: P2)

### Included Subtasks

T037 open-packs PR: `packs/internal/README.md` names the hyphenated command-skill folders (WP10)
T038 Bump the internal (and, if changed, built-in) pin with `charter pack vendor`, `make sync-packs`, verify (WP10)

### Dependencies

WP09.

## Dependency & Execution Summary

WP01 → WP02 → WP03 → {WP04, WP05, WP07} → WP06 (after WP05), WP08 (after WP07) → WP09 → WP10.
Single-branch topology runs them one at a time in this order: WP01, WP02, WP03, WP04, WP05, WP06,
WP07, WP08, WP09, WP10.

## Requirements Coverage Summary

| WP | Requirements |
|----|--------------|
| WP01 | FR-001, FR-008, SC-004 |
| WP02 | FR-001, FR-002, FR-003, FR-017, FR-016 |
| WP03 | FR-001, FR-004, FR-007, FR-019, FR-020, NFR-001 |
| WP04 | FR-005, FR-006, NFR-002 |
| WP05 | FR-008, FR-009, FR-010, NFR-005 |
| WP06 | FR-011, NFR-003 |
| WP07 | FR-012, FR-013, FR-014, NFR-004 |
| WP08 | FR-015, SC-001 |
| WP09 | FR-018, FR-006 |
| WP10 | FR-016 |

## Subtask Index (Reference)

| Subtask | Description | WP | Parallel |
|---------|-------------|----|----------|
| T001-T003 | P0 repros | WP01 | |
| T004-T008 | naming authority | WP02 | |
| T009-T014 | installer/provider/doctor | WP03 | |
| T015-T017 | rename migration | WP04 | |
| T018-T021 | Antigravity | WP05 | |
| T022-T025 | home writer | WP06 | |
| T026-T030 | frontmatter | WP07 | |
| T031-T033 | CI validator | WP08 | |
| T034-T036 | docs | WP09 | |
| T037-T038 | open-packs | WP10 | |
