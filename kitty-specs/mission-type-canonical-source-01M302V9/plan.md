# Implementation Plan: Single canonical mission-type source (#3831 #4088)

**Branch**: `fix/mission-type-canonical-source-3831` | **Date**: 2026-09-20 | **Spec**: `kitty-specs/mission-type-canonical-source-01M302V9/spec.md`
**Input**: Feature specification (this mission dir) + grounding (research/architecture/related-issue squads) + post-spec adversarial folds.

## Summary

Retire the org-blind `specify_cli/mission.py` `Mission`/`MissionConfig`/`mission.yaml` resolver and route mission-type loading through the single canonical charter `ResolvedMissionType` source, so an org-tier custom mission type loads as itself instead of being warn-and-substituted to software-dev (#3831), and project overrides take effect (#4088, via migration to the canonical `.kittify/doctrine/mission_types/` home). The one genuinely-new schema is a `path_conventions` doctrine slot (with `VALID_PATH_KEYS` relocated into `charter`); all other legacy fields migrate to existing charter/dossier homes or retire. The typeless→software-dev *template* default is preserved (C-006/FR-003a); its removal is the sequenced #2660.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: internal — `charter` (governance authority: `resolve_mission_type_context`, `ResolvedMissionType`, `MissionTypeRepository`, `resolve_org_dirs`), `specify_cli` (adapter: mission loader + consumers), dossier `ManifestRegistry`. pydantic, typer, ruamel.yaml.
**Storage**: doctrine YAML (`packs/built-in/mission_types/<t>.yaml`, org packs, project `.kittify/doctrine/mission_types/`), feature `meta.json`.
**Testing**: pytest. New red-first `@pytest.mark.regression` repros for #3831/#4088; unit tests for the `path_conventions` slot, flat→per-step artifact mapping, migration; golden-shard parity for built-in types.
**Target Platform**: CLI (Linux/macOS/Windows).
**Project Type**: single (library + CLI).
**Performance Goals**: N/A (resolution is not on a hot path).
**Constraints**: layer chain `kernel <- charter <- {glossary,runtime,mission_runtime} <- specify_cli`; canonical source in `charter` (C-001 forbids charter→specify_cli); never route via `mission_runtime` (shrink-only ledger); complexity ≤15; ruff+mypy clean; no new suppressions.
**Scale/Scope**: ~7 external consumers rewired; 1 new doctrine schema slot; 1 migration; 1 ADR; 3 built-in types held byte-for-byte.

## Constitution Check

*GATE: charter (`.kittify/charter/charter.md`).*

- **Single canonical authority** ✅ — converge onto the existing charter `ResolvedMissionType`; no second mission-type authority, no parity shim (C-003). #4088 resolved by migration to the one canonical override home, not a second path.
- **Architectural alignment** ✅ — canonical source stays in `charter`; consumers depend downward; `VALID_PATH_KEYS` relocates *down* into charter; `test_layer_rules.py` folded into the relocation commit.
- **DDD + tiered rigour** ✅ — charter mission-type schema = core domain (high rigour, exhaustive tests); CLI/dashboard display = glue (lighter).
- **ATDD-first / red-first** ✅ — SC-001/SC-002 land as issue-pinned regression repros RED through the pre-existing entry point before the fix (ADR 2026-07-17-1).
- **Terminology** ✅ — Mission canon; name the *placement* `routing` sense (C-002), distinct from #3830's dispatch sense.

No violations requiring Complexity Tracking. `path_conventions` is a new field but is a migration of an existing load-bearing concept, not a new authority.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-type-canonical-source-01M302V9/
├── spec.md                 # done
├── plan.md                 # this file
├── issue-matrix.json       # #3831/#4088 targets + cross-links
├── tracer-*.md             # approach / design-decisions / tooling-friction
└── tasks.md + tasks/       # /spec-kitty.tasks output
```
(No `data-model.md`/`quickstart.md`/`contracts/` — not applicable to this internal refactor; the ADR is the design record.)

### Source Code (repository root)

```
src/charter/
├── offering/missions/models.py         # MissionType / ResolvedMissionType (+ new path_conventions field)
├── offering/artifact_kinds.py          # (mission-type doctrine artifact schema, if slot lives here)
├── activation/mission_type_profiles.py # resolve_mission_type_context / resolve_layered_mission_types
└── <new home for VALID_PATH_KEYS>      # relocated frozenset + path-convention validator

src/specify_cli/
├── mission.py                          # RETIRE Mission/MissionConfig/_mission_path_by_name/get_mission_by_name/
│                                       #   get_mission_for_feature fallback/discover_missions; KEEP get_mission_type
├── config/path_conventions.py          # repoint VALID_PATH_KEYS import to charter
├── acceptance/{__init__.py,summary_core.py}  # read expected_artifacts / path_conventions from charter
├── core/worktree.py                    # sparse-checkout artifact inventory from charter/dossier
├── validators/paths.py                 # path_conventions from charter
├── dashboard/handlers/features.py      # retire/degrade domain/version display
├── cli/commands/mission_type.py        # rewire panel to charter; REMOVE the partial-#3831 band-aid
└── upgrade/migrations/                  # new migration: paths->slot, templates->dirs, overrides->canonical home

docs/adr/3.x/2026-09-20-*-canonical-mission-type-source.md   # ADR (FR-009)
docs/changelog/CHANGELOG.md                                  # [Unreleased] entry

tests/
├── <fixtures>/                          # org-activated custom mission type consumer project + override tier
├── specify_cli/... , tests/charter/... , tests/doctrine/... , tests/dossier/...  # repros + parity
```

**Structure Decision**: single project; canonical mission-type source owned by `charter`, consumed by `specify_cli`. The mission-dir/`mission.yaml` reader in `specify_cli/mission.py` is strangled; `get_mission_type` (already charter-clean) is retained.

## Complexity Tracking

No constitution violations to justify. Watch item: `cli/commands/mission_type.py` is the single largest consumer (panel over many `.config.*` fields) — extract per-field helpers to keep complexity ≤15 when rewiring.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (fixtures + red-first repros for #3831/#4088)  ── root
   └─> WP02 (path_conventions slot + VALID_PATH_KEYS -> charter/offering/missions/models.py + ADR)
              [pack-manifest regen fold]
        └─> WP03 (consumer rewire onto charter/dossier — ATOMIC per module:
                    acceptance/__init__.py (artifact reads + get_mission_for_feature + Mission import),
                    core/worktree.py sparse-checkout inventory,
                    path readers summary_core.py + validators/paths.py [need WP02 slot])
                    [dossier/accept golden-shard folds]
             └─> WP04 (retire the legacy mission.py resolver: get_mission_by_name/get_mission_for_feature/
                    _mission_path_by_name/discover_missions/list_available_missions/_packaged_missions_dir;
                    rewire display consumers dashboard/handlers/features.py + cli/commands/mission_type.py
                    (REMOVE the partial-#3831 band-aid); typeless template default PRESERVED,
                    typed-unknown surfaced; rewrite/delete the ~14 test files importing retired symbols)
                    [FOLD: FR-010 reader-invariant gate test_mission_type_reader_invariants.py +
                     mission_type_reader_allowlist.yaml — the allowlist exempts the retired lines by
                     number, so it MUST update in this commit]
                  └─> WP05 (migration via upgrade + doctor audit: paths->slot, templates->dirs,
                        .kittify/overrides/missions/ -> .kittify/doctrine/mission_types/)
                       └─> WP06 (docs/CHANGELOG + docs-index/freshness + terminology guard)
```

### Work Distribution

- **Sequential (single_branch topology)**: WP01 → WP02 → WP03 → WP04 → WP05 → WP06. Lanes would collapse by write-scope (shared charter + specify_cli surfaces), so single_branch is deliberate. Per-commit greenness is the binding constraint (this repo lands commits individually), so each WP fully rewires the modules it touches — no module is left half-migrated across a WP boundary.
- **Agent assignments**: implement = sonnet (profile-loaded python-pedro); review = opus (reviewer-renata). Each WP dispatched via `spec-kitty implement WP##`.

### Coordination Points

- **Gate-companion folds** (same commit as the surface they guard):
  - **WP04**: `tests/architectural/test_mission_type_reader_invariants.py` + `mission_type_reader_allowlist.yaml` (FR-010) — the load-bearing one; the allowlist exempts `mission.py`'s now-retired coalesce/fallback *by line number*.
  - **WP03**: dossier/accept golden shards (`tests/dossier/*`, `tests/specify_cli/acceptance/test_missing_artifacts_from_config.py`).
  - **WP02**: pack-manifest regen (`spec-kitty doctrine regenerate-graph`) for the net-new `path_conventions` doctrine field. (`test_layer_rules.py` will NOT fire on the downward `VALID_PATH_KEYS` relocation — kept green by construction, not relied on as a catch.)
- **Byte-for-byte built-in parity** (NFR-001): WP03/WP04 keep software-dev/research/documentation expected-artifact + convention sets identical — verified by golden shards before merge.
- **Retirement blast radius (WP04)**: ~14 test files import `get_mission_for_feature`/`get_mission_by_name`/`list_available_missions` (e.g. `tests/git_ops/test_worktree.py`, `tests/test_dashboard/test_api_handler.py`, `tests/cross_cutting/misc/test_acceptance_support.py`, `tests/specify_cli/cli/commands/test_selector_resolution.py`, `tests/charter/test_pack_manager.py`) — all rewritten/deleted in the WP04 commit.
