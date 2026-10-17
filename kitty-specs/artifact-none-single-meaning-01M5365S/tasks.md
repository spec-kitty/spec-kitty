# Tasks: One meaning for an unclassified mission artifact (#5697)

**Mission**: `artifact-none-single-meaning-01M5365S`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Data model**: [data-model.md](./data-model.md)

Three work packages. WP01 (classifier taxonomy) and WP02 (the one-meaning
predicate fix) are independent and parallel; WP03 (docs/CHANGELOG) depends on
both. WP02 is the load-bearing #5697 fix and could ship alone; WP01 is the
honest-taxonomy follow-through.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add four PRIMARY `MissionArtifactKind` members | WP01 |  |
| T002 | Add the four members to `_PRIMARY_ARTIFACT_KINDS` | WP01 |  |
| T003 | Add basename classifier entries (research-outputs, analysis reports, occurrence-map, goals, release, meta.json) | WP01 |  |
| T004 | Add `research → RESEARCH` to `_COORD_RESIDUE_DIRS` (dir-anchored) | WP01 |  |
| T005 | Classification + partition-invariant + inverse-map tests (red→green) | WP01 |  |
| T006 | Blast-radius sweep of the new members (exhaustiveness, E2 list, inverse map) | WP01 |  |
| T007 | Red-first repro: projection refuses byte-identical unclassified `research/**` (FR-001/FR-012) | WP02 |  |
| T008 | Red-first repro: workflow partition sends an unclassified path to coord (FR-002) | WP02 |  |
| T009 | Route `_post_checkpoint_mission_paths` through `is_coordination_kind_file` | WP02 |  |
| T010 | Route `_partition_paths_by_primary_kind` through `is_coordination_kind_file` | WP02 |  |
| T011 | Verify carry-forward (NFR-004) + demote transitional repros to focused unit tests | WP02 |  |
| T012 | NFR-002 architectural guard: no local `None → coord` re-derivation | WP02 |  |
| T013 | `[Unreleased]` CHANGELOG entry (#5697) | WP03 |  |
| T014 | Update artifact-placement docs to state the one meaning of `None` + new kinds | WP03 |  |
| T015 | Docs freshness + terminology gates (regenerate index only if a page is added) | WP03 |  |

---

## WP01 — Classifier taxonomy (new PRIMARY kinds + entries)

- **Goal**: every mission file that currently classifies to `None` gets an honest kind in the PRIMARY partition; the partition stays total + disjoint and the inverse basename map stays honest.
- **Priority**: P2 (honest-taxonomy follow-through; not the refuse fix).
- **Independent test**: `kind_for_mission_file` returns the assigned kind (and `is_primary_artifact_kind` is true) for every newly classified path, `None` for the four excluded paths, and `assert_partition_invariant()` passes.
- **Prompt**: [tasks/WP01-classifier-taxonomy.md](./tasks/WP01-classifier-taxonomy.md)

Included subtasks: T001, T002, T003, T004, T005, T006

---

## WP02 — One meaning for an unclassified kind (predicate fix)

- **Goal**: route the squash projection and the workflow commit partition through the single `is_coordination_kind_file` authority so `None` means "not-coord" everywhere; the #5697 refuse is gone.
- **Priority**: P1 (the reported defect; load-bearing).
- **Independent test**: the #5697 regression repro (byte-identical unclassified `research/**`) is RED before the fix and GREEN after; `traces/` still projects; the architectural guard finds zero local `None → coord` branches.
- **Prompt**: [tasks/WP02-one-meaning-for-none.md](./tasks/WP02-one-meaning-for-none.md)

Included subtasks: T007, T008, T009, T010, T011, T012

---

## WP03 — Docs & CHANGELOG

- **Goal**: record the user-facing change and the one-meaning rule in the canonical docs.
- **Priority**: P3 (polish; depends on WP01 + WP02).
- **Independent test**: `scripts/docs/check_docs_freshness.py --ci` reports 0 errors and `tests/architectural/test_no_legacy_terminology.py` passes.
- **Dependencies**: WP01, WP02.
- **Prompt**: [tasks/WP03-docs-changelog.md](./tasks/WP03-docs-changelog.md)

Included subtasks: T013, T014, T015
