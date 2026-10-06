# Tasks: Skill surface and upgrade integrity

**Mission**: `skill-surface-upgrade-integrity-01M482Z3` · **Issues**: #4275, #5801
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/doctor-skills-json.md](contracts/doctor-skills-json.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro: upgrade with configured tool folder absent fails | WP01 | |
| T002 | Merge structurally identical directory creates in `coalesce_effects` | WP01 | |
| T003 | Conflict message names destination, both owners, differing fields | WP01 | |
| T004 | `managed_skills` local merge delegates to the coalescer | WP01 | |
| T005 | Unit tests: merge, negative cases, `.agents/skills` multi-tool fixture | WP01 | |
| T006 | Red-first repro: failed final surface repair leaves version stamped | WP02 | |
| T007 | Snapshot version trio before the runner | WP02 | |
| T008 | Restore snapshot on runner or `finalize_upgrade` failure | WP02 | |
| T009 | Keep #1158 schema-stamp repair and no-migration path covered | WP02 | |
| T010 | Red-first repro: doctor healthy with in-force skill never projected | WP03 | [P] |
| T011 | `KIND_MISSING` in `find_pack_skill_findings` (never-installed + absent file) | WP03 | [P] |
| T012 | `doctor skills --fix` projects via `project_pack_skills`, re-checks | WP03 | [P] |
| T013 | `no_tool_folder` finding in `tool_folders` payload list | WP03 | [P] |
| T014 | Update JSON goldens additively; focused tests per branch | WP03 | [P] |
| T015 | How-to lists `missing` + `no_tool_folder` | WP04 | |
| T016 | ADR 2026-09-27-1 amendment | WP04 | |
| T017 | CHANGELOG `[Unreleased]` entries for #4275 and #5801 | WP04 | |
| T018 | Docs index/freshness and terminology gates | WP04 | |

## WP01 — Upgrade plans a missing tool folder once (IC-01)

**Prompt**: [tasks/WP01-coalesce-identical-directory-creates.md](tasks/WP01-coalesce-identical-directory-creates.md) · ~250 lines
**Goal**: `upgrade` succeeds when a configured tool folder is absent; real conflicts still fail with both owners named. **Priority**: P1.
**Independent test**: kittify temp project with claude, remove `.claude/`, `upgrade --project --yes` exits 0.

T001 Red-first repro: upgrade with configured tool folder absent fails (WP01)
T002 Merge structurally identical directory creates in `coalesce_effects` (WP01)
T003 Conflict message names destination, both owners, differing fields (WP01)
T004 `managed_skills` local merge delegates to the coalescer (WP01)
T005 Unit tests: merge, negative cases, `.agents/skills` multi-tool fixture (WP01)

**Dependencies**: none. **Risks**: masking real conflicts — strict equality on everything but owner.

## WP02 — A failed upgrade restores the recorded version (IC-02)

**Prompt**: [tasks/WP02-restore-version-on-failed-upgrade.md](tasks/WP02-restore-version-on-failed-upgrade.md) · ~230 lines
**Goal**: version, last-upgraded time and schema version are restored when the runner or the final surface repair fails. **Priority**: P1.
**Independent test**: force `finalize_upgrade` repair failure; `metadata.yaml` version unchanged.

T006 Red-first repro: failed final surface repair leaves version stamped (WP02)
T007 Snapshot version trio before the runner (WP02)
T008 Restore snapshot on runner or `finalize_upgrade` failure (WP02)
T009 Keep #1158 schema-stamp repair and no-migration path covered (WP02)

**Dependencies**: Depends on WP01 (same upgrade flow; serial). **Risks**: breaking the existing #3334 restore; restore must not touch the applied-migrations record.

## WP03 — Doctor reports and repairs missing pack skills (IC-03)

**Prompt**: [tasks/WP03-doctor-missing-pack-skills.md](tasks/WP03-doctor-missing-pack-skills.md) · ~300 lines
**Goal**: `doctor skills` exits 1 on missing pack skills or no tool folder; `--fix` projects missing skills. **Priority**: P1.
**Independent test**: in-force skill + empty manifest → exit 1 `missing`; `--fix` → re-run exit 0.

T010 Red-first repro: doctor healthy with in-force skill never projected (WP03)
T011 `KIND_MISSING` in `find_pack_skill_findings` (never-installed + absent file) (WP03)
T012 `doctor skills --fix` projects via `project_pack_skills`, re-checks (WP03)
T013 `no_tool_folder` finding in `tool_folders` payload list (WP03)
T014 Update JSON goldens additively; focused tests per branch (WP03)

**Dependencies**: none (parallel with WP01/WP02). **Risks**: false `missing` on tools without skill support; golden churn must be additive.

## WP04 — Documentation, ADR amendment, changelog

**Prompt**: [tasks/WP04-docs-adr-changelog.md](tasks/WP04-docs-adr-changelog.md) · ~150 lines
**Goal**: operators and pack authors can read what the new findings mean. **Priority**: P2.

T015 How-to lists `missing` + `no_tool_folder` (WP04)
T016 ADR 2026-09-27-1 amendment (WP04)
T017 CHANGELOG `[Unreleased]` entries for #4275 and #5801 (WP04)
T018 Docs index/freshness and terminology gates (WP04)

**Dependencies**: Depends on WP01, WP02, WP03 (documents shipped behaviour).

## Parallelism & MVP

- Lane A: WP01 → WP02 (serial, shared upgrade flow). Lane B: WP03. WP04 last.
- MVP: WP01 (unblocks the only pack-skill projection path).
