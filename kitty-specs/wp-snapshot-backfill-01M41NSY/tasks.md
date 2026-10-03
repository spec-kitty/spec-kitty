# Work Packages: Drain the snapshot-versus-files work-package disagreement

**Inputs**: `kitty-specs/wp-snapshot-backfill-01M41NSY/` — spec.md, plan.md, research.md
**Prerequisites**: plan.md, spec.md, research.md

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: WP-status gap planner and seed writer (Priority: P1)

**Goal**: Pure planner (gap, terminal evidence, deterministic seed events) plus a writer function inside the existing migration writer.
**Independent Test**: fixture Missions (partial log, no log, `WPCreated`-only, finished, deleted-coord-branch meta) reach snapshot/file parity; re-run appends nothing.
**Prompt**: `tasks/WP01-gap-planner-and-seed-writer.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-010, FR-011, FR-012, C-001, C-002, C-003

### Included Subtasks

- T001 Red-first regression repro through `materialize` on a fixture Mission missing file WPs
- T002 `migration/wp_status_backfill.py`: gap detection (set-based, both directions)
- T003 Terminal evidence resolution (`accepted_at`/`merged_at`, evidence manifest)
- T004 Deterministic seed construction (`planned`, forced `planned → done`, `migration:` actor)
- T005 Writer in `backfill_runtime_state.py` reusing lock + atomic verified append + id dedupe; regenerate `status.json` only if present
- T006 Tests: idempotence, dry-run, validate_transition legality, evidence=None readers, interleaving with runtime backfill, deleted-coord-branch fixture

### Dependencies

- None

---

## Work Package WP02: `spec-kitty migrate backfill-wp-status` CLI (Priority: P1)

**Goal**: Operator subcommand with `--mission`, `--dry-run`, `--evidence-manifest`, `--json`.
**Independent Test**: typer-runner tests over a tmp corpus; JSON contract inventory updated.
**Prompt**: `tasks/WP02-migrate-backfill-wp-status-cli.md`
**Requirement Refs**: FR-007, FR-005

### Included Subtasks

- T007 Subcommand body in `cli/commands/migrate/backfill_wp_status.py`, registered in `migrate_cmd.py`
- T008 Evidence-manifest loader (YAML, schema-checked, fail closed on unknown slug)
- T009 Human + `--json` summary; exit codes
- T010 CLI tests + `test_json_contract_enumeration.py` / migrate-flags inventory updates

### Dependencies

- Depends on WP01

---

## Work Package WP03: Corpus drain (Priority: P2)

**Goal**: Author the evidence manifest and run the repair over this repository's committed Missions.
**Independent Test**: after the run, the dry-run reports zero would-seed; snapshot/file parity holds except bucket C.
**Prompt**: `tasks/WP03-corpus-drain.md`
**Requirement Refs**: FR-008

### Included Subtasks

- T011 Evidence manifest `kitty-specs/wp-snapshot-backfill-01M41NSY/evidence-manifest.yaml`
- T012 Run `spec-kitty migrate backfill-wp-status --evidence-manifest …` over the corpus; commit regenerated logs
- T013 Record the list of modified (not added) frozen files for WP04

### Dependencies

- Depends on WP02

---

## Work Package WP04: Corpus parity gate and sanctioned corrections (Priority: P2)

**Goal**: Set-based parity test with shrink-only reasoned exemptions; ledger modified frozen files.
**Independent Test**: gate green on branch; self-mutation (injected unseeded WP) fails it; stale exemption fails it.
**Prompt**: `tasks/WP04-corpus-parity-gate.md`
**Requirement Refs**: FR-009

### Included Subtasks

- T014 `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` with exemption table
- T015 Self-mutation and stale-exemption controls
- T016 `_OPERATOR_SANCTIONED_CORRECTIONS` entries in `test_archive_root_byte_identical.py`

### Dependencies

- Depends on WP03

---

## Work Package WP05: Docs and CHANGELOG (Priority: P3)

**Goal**: Document the subcommand and record the change.
**Independent Test**: docs freshness check errors=0; terminology guard green.
**Prompt**: `tasks/WP05-docs-and-changelog.md`
**Requirement Refs**: FR-007

### Included Subtasks

- T017 How-to/reference for `migrate backfill-wp-status`
- T018 `[Unreleased]` CHANGELOG entry (#5579)
- T019 Docs index regen + freshness check

### Dependencies

- Depends on WP02
