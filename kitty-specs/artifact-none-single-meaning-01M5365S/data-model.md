# Data Model: One meaning for an unclassified mission artifact (#5697)

This mission changes a classification taxonomy, so the "data model" is the
authoritative **path → kind → partition** table (the change's real contract) and
the invariants that bind it. There are no persisted schema changes.

## Entities

### MissionArtifactKind (enum, `src/mission_runtime/artifacts.py`)

Gains four new members, all PRIMARY:

| New member | Value | Classifies |
|------------|-------|------------|
| `RESEARCH_OUTPUT` | `research_output` | `findings.md`, `report.md`, `methodology.md`, `synthesis.md`, `literature-review.md` |
| `OCCURRENCE_MAP` | `occurrence_map` | `occurrence_map.yaml` |
| `MISSION_GOALS` | `mission_goals` | `goals.md` |
| `RELEASE_RECORD` | `release_record` | `release.md` |

### Classifier maps (`src/mission_runtime/artifacts.py`)

- `_MISSION_FILE_KIND_BY_BASENAME`: gains `findings.md`, `report.md`, `methodology.md`, `synthesis.md`, `literature-review.md` → `RESEARCH_OUTPUT`; `gap-analysis.md`, `audit-report.md` → `ANALYSIS_REPORT`; `occurrence_map.yaml` → `OCCURRENCE_MAP`; `goals.md` → `MISSION_GOALS`; `release.md` → `RELEASE_RECORD`; `meta.json` → `PRIMARY_METADATA`.
- `_COORD_RESIDUE_DIRS`: gains `research` → `RESEARCH` (dir-anchored, any depth — mirrors `contracts`/`decisions`).

### Partition frozensets

- `_PRIMARY_ARTIFACT_KINDS`: gains the four new members. `_PLACEMENT_ARTIFACT_KINDS` is unchanged. Every classified file is PRIMARY (C-002).

## Authoritative classification table (post-change)

| Path / dir (under `kitty-specs/<slug>/`) | Kind | Partition | Change |
|---|---|---|---|
| `research/**` (subtree) | RESEARCH | PRIMARY | **new** (dir-anchored) |
| `findings.md` | RESEARCH_OUTPUT | PRIMARY | **new** |
| `report.md` | RESEARCH_OUTPUT | PRIMARY | **new** |
| `methodology.md` | RESEARCH_OUTPUT | PRIMARY | **new** |
| `synthesis.md` | RESEARCH_OUTPUT | PRIMARY | **new** |
| `literature-review.md` | RESEARCH_OUTPUT | PRIMARY | **new** |
| `gap-analysis.md` | ANALYSIS_REPORT | PRIMARY | **new** (reuse) |
| `audit-report.md` | ANALYSIS_REPORT | PRIMARY | **new** (reuse) |
| `occurrence_map.yaml` | OCCURRENCE_MAP | PRIMARY | **new** |
| `goals.md` | MISSION_GOALS | PRIMARY | **new** |
| `release.md` | RELEASE_RECORD | PRIMARY | **new** |
| `meta.json` (mission root) | PRIMARY_METADATA | PRIMARY | **new** (gap close) |
| `lint-report.json` | None | — | unchanged (excluded; `.kittify/`) |
| `docs/**` | None | — | unchanged (excluded; repo root) |
| `answers.yaml` | None | — | unchanged (excluded; `.kittify/`) |
| `mission-events.jsonl` | None | — | unchanged (excluded; #5669) |
| spec.md / plan.md / data-model.md / research.md / quickstart.md / tasks.md / wps.yaml / lanes.json / contracts/** / decisions/** / tasks/** / checklists/** / analysis-report.md / retrospective.yaml | (existing) | PRIMARY | unchanged |
| status.{events.jsonl,json} / issue-matrix.{md,json} / acceptance-matrix.json / decisions.events.jsonl / traces/** / tasks/<wp>/review-cycle-*.md | (existing) | COORD | unchanged |

## Invariants

- **P-1 (partition total + disjoint)**: `_PRIMARY_ARTIFACT_KINDS` and `_PLACEMENT_ARTIFACT_KINDS` are disjoint and jointly cover every `MissionArtifactKind` member. `assert_partition_invariant` must pass with the four new members (all added to PRIMARY).
- **Inverse-map honesty (FR-013)**: `mission_file_basenames_for_kind(kind)` returns exactly the basenames mapped to `kind` in `_MISSION_FILE_KIND_BY_BASENAME` — no basename is mapped to a kind that misdescribes it.
- **One meaning for None (NFR-002)**: `kind_for_mission_file(path) is None` is interpreted by exactly one authority (`is_coordination_kind_file → not-coord`); no consumer branches locally on `None → coord`.
- **Coordination carry-forward preserved (NFR-004)**: the projection still carries `traces/**`, `decisions.events.jsonl`, and `tasks/<wp>/review-cycle-*.md` forward (they classify to coord kinds → `is_coordination_kind_file` True).

## State transitions

None. Classification is a pure function of the path (and optional `mission_slug`).
