<!--
  Work Packages for mission-type-canonical-source-01M302V9
  Single-branch topology; WPs are sequential (per-commit greenness is binding).
-->

# Work Packages: Single canonical mission-type source (#3831 #4088)

> **RE-SCOPED 2026-09-21 (operator decision).** WP03 found the charter tier does not carry built-in
> path/artifact data equivalent to legacy `mission.yaml` (different concerns; see spec Re-scope /
> tracer D10). Full convergence is the #2652 epic. This mission is now the targeted **org-aware
> loader** fix: **WP01 ✓, WP02 ✓, WP03 (redefined = org-aware loader), WP06 (docs).**
> **WP04 (retire resolver) and WP05 (migration) are CANCELED** — deferred to #2652.

**Mission**: `mission-type-canonical-source-01M302V9`
**Branch**: `fix/mission-type-canonical-source-3831`
**Spec/Plan**: `spec.md`, `plan.md` (this dir)

## Subtask Format: `[Txxx] [P?] Description`

- `[P]` = can run in parallel with sibling `[P]` subtasks in the same WP (different files, no ordering).
- Every defect-fixing subtask lands an issue-pinned `@pytest.mark.regression` repro RED through the pre-existing entry point before the fix (ADR 2026-07-17-1).

## Path Conventions

- Canonical mission-type source: `src/charter/` (governance authority). Consumers in `src/specify_cli/` read downward.
- Tests mirror source; new fixtures under `tests/fixtures/` and `tests/doctrine/` helpers.

---

## Work Package WP01: Fixtures & red-first repros (Priority: P0) 🎯 dependency root

Build the missing test scaffolding and the two failing repros that define done.

### Included Subtasks

- [T001] [P] Build an org-activated custom-mission-type consumer-project fixture: `.kittify/config.yaml` (`doctrine.org.packs`) + org pack `mission_types/<type>.yaml` + a feature `meta.json` recording that type, **no `.kittify/missions/`**. Mine `tests/doctrine/{test_org_pack_subdir.py,drg/test_org_pack_config_resolve_existing_org_roots.py}` helpers.
- [T002] [P] Build a project-override fixture: legacy `.kittify/overrides/missions/<type>/` and the canonical target `.kittify/doctrine/mission_types/<type>/`.
- [T003] Red-first regression repro for #3831 (SC-001): `get_mission_for_feature(feature_dir)` on the T001 fixture currently returns `Software Dev Kitty`; assert it must return the custom type's identity/conventions/artifacts. `@pytest.mark.regression`, issue-pinned, RED.
- [T004] Red-first regression repro for #4088 (SC-002): the pre-migration `.kittify/overrides/missions/<type>/` override is ignored today. `@pytest.mark.regression`, issue-pinned, RED.

### Dependencies
None (root).

### Risks & Mitigations
- Fixture drift from real org-pack shape → copy structure from `tests/doctrine/` canonical helpers, not older missions.

---

## Work Package WP02: `path_conventions` doctrine slot + `VALID_PATH_KEYS` relocation + ADR (Priority: P0)

Create the one genuinely-new schema home and the decision record.

### Included Subtasks

- [T010] Add a `path_conventions` field to the charter mission-type schema (`src/charter/offering/missions/models.py`) and the doctrine mission-type artifact schema.
- [T011] Add `VALID_PATH_KEYS` + the path-convention validator to `src/charter/offering/missions/models.py` as the canonical home (the `specify_cli/mission.py` copy is removed and both importers `specify_cli/mission.py:159,191` + `config/path_conventions.py:20,92` are repointed downward in WP04, keeping each module atomic per commit; transient dual-home is green).
- [T012] [P] Unit tests: `path_conventions` parse/validate; relocation import parity; a type declaring no conventions yields a no-op.
- [T013] [P] Author ADR `docs/adr/3.x/2026-09-20-*-canonical-mission-type-source.md` (canonical source = `ResolvedMissionType`; legacy resolver retired; `path_conventions` new slot; **name the `Mission` collision** with `charter/offering/missions/models.py`; companion to 2026-07-14-2/2026-07-15-1, reconciles 2026-08-28-1).
- [T014] Regenerate the pack manifest (`spec-kitty doctrine regenerate-graph`) for the net-new `path_conventions` field; fold the regen output in this commit.

### Dependencies
WP01.

### Risks & Mitigations
- Layer violation on relocation → `VALID_PATH_KEYS` moves *down* into charter (legal); verify no `charter → specify_cli` edge.

---

## Work Package WP03: Consumer rewire onto charter/dossier (Priority: P1)

Rewire every consumer of the legacy `Mission` onto the canonical source — **atomic per module**.

### Included Subtasks

- [T020] Rewire `acceptance/__init__.py`: source expected/optional artifact tokens from `ResolvedMissionType.expected_artifacts` / dossier `ManifestRegistry`; drop `get_mission_for_feature` + the `Mission` import from acceptance. Exact-token parity incl. `checklists/`.
- [T021] Rewire `core/worktree.py:654-661` sparse-checkout inventory to charter `expected_artifacts` (flat-list adapter; no lossy collapse — assert exact token sets).
- [T022] Rewire `acceptance/summary_core.py:165` `evaluate_path_conventions` + `validators/paths.py:287` to read `path_conventions` from charter (gated on WP02); no-op for types declaring none.
- [T023] [P] Golden-shard parity (`tests/dossier/*`, `tests/specify_cli/acceptance/test_missing_artifacts_from_config.py`) green for software-dev/research/documentation (NFR-001). Fold shard updates here.

### Dependencies
WP02.

### Risks & Mitigations
- Silent wrong-artifact list (flat↔per-step) → the T003/T021 exact-token repros gate it.

---

## Work Package WP04: Retire the legacy resolver + display rewire + FR-010 gate (Priority: P1)

Strangle the org-blind loader; route through charter.

### Included Subtasks

- [T030] Retire `_mission_path_by_name`, `get_mission_by_name`, `get_mission_for_feature` (fallback `:801-806`), `discover_missions`, `list_available_missions`, `_packaged_missions_dir`; route mission loading through the charter source. Remove the `specify_cli/mission.py` `VALID_PATH_KEYS` copy and repoint `config/path_conventions.py` to the charter home (finishing the WP02 relocation). **Preserve** the typeless→software-dev *template* default (`:783`, C-006/FR-003a); a typed-but-unknown type surfaces visibly (never warn-and-substitute). Keep `get_mission_type`. Flips T003 (#3831) GREEN.
- [T031] Rewire display consumers: `dashboard/handlers/features.py:109-112` (retire domain/version) and `cli/commands/mission_type.py` panel; **REMOVE the partial-#3831 `catch_warnings` band-aid at `:195-215`** (do not stack).
- [T032] Rewrite/delete the ~14 test files importing retired symbols (`tests/git_ops/test_worktree.py`, `tests/test_dashboard/test_api_handler.py`, `tests/cross_cutting/misc/test_acceptance_support.py`, `tests/specify_cli/cli/commands/test_selector_resolution.py`, `tests/charter/test_pack_manager.py`, …) — same commit, per-commit greenness.
- [T033] Fold the FR-010 reader-invariant gate: update `tests/architectural/test_mission_type_reader_invariants.py` + `mission_type_reader_allowlist.yaml` (the allowlist exempts the retired lines by number) in this commit.

### Dependencies
WP02, WP03.

### Risks & Mitigations
- Intermediate red from a missed consumer → the WP03 atomic rewire + T032 test sweep + `git grep` of retired symbols before commit.

---

## Work Package WP05: Consumer migration + doctor audit (Priority: P2)

Migrate legacy consumer overrides to the canonical homes.

### Included Subtasks

- [T040] `spec-kitty upgrade` migration: legacy `.kittify/missions/<type>/mission.yaml` `paths` → `path_conventions` slot; templates → template dirs; `.kittify/overrides/missions/<type>/` → `.kittify/doctrine/mission_types/<type>/`. Drop retired fields with an audit note; flat `required/optional` → unassigned/all-steps bucket (FR-005).
- [T041] `spec-kitty doctor` audit surface reporting migration state.
- [T042] Migration unit/integration tests; flip T004 (#4088) GREEN post-migration.

### Dependencies
WP02, WP04.

### Risks & Mitigations
- Fail-open migration losing data → fail-closed on ambiguous/corrupt `mission.yaml`; audit every dropped field.

---

## Work Package WP06: Docs / CHANGELOG / freshness (Priority: P2)

### Included Subtasks

- [T050] `docs/changelog/CHANGELOG.md` `[Unreleased]` entries — impact-first, `(#3831)` and `(#4088)`, before→after.
- [T051] Update affected docs (mission-type resolution, doctrine `path_conventions` slot); run `scripts/docs/docs_index.py --write`, `scripts/docs/check_docs_freshness.py --ci` (errors=0), `tests/architectural/test_no_legacy_terminology.py`.
- [T052] Assess the three tracer files at close.

### Dependencies
WP01–WP05.

### Risks & Mitigations
- Docs freshness gate red on the new ADR → regenerate the retrieval index in the same commit.

---

## Dependency & Execution Summary

```
WP01 → WP02 → WP03 → WP04 → WP05 → WP06   (sequential; single_branch)
```

## Requirements Coverage Summary

| WP | FR | SC | Issue |
|----|----|----|-------|
| WP01 | (repro scaffolding) | SC-001, SC-002 (RED) | #3831, #4088 |
| WP02 | FR-004, FR-009 | SC-004 (partial) | — |
| WP03 | FR-002, FR-003, FR-007 | SC-001 (GREEN), SC-002 (GREEN), SC-003 | #3831, #4088 |
| ~~WP04~~ | CANCELED — deferred to #2652 | — | — |
| ~~WP05~~ | CANCELED — deferred to #2652 | — | — |
| WP06 | (docs) | SC-005 (terminology) | #3831, #4088 |

## Subtask Index (Reference)

WP01: T001–T004 · WP02: T010–T014 · WP03: T020–T023 · WP04: T030–T033 · WP05: T040–T042 · WP06: T050–T052.
