---
work_package_id: WP01
title: Classifier taxonomy — new PRIMARY kinds + entries
dependencies: []
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-013
- NFR-001
- NFR-003
- C-002
- C-005
planning_base_branch: fix/artifact-none-single-meaning
merge_target_branch: fix/artifact-none-single-meaning
branch_strategy: Planning artifacts for this mission were generated on fix/artifact-none-single-meaning. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/artifact-none-single-meaning unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-artifact-none-single-meaning-01M5365S
base_commit: b7b2a2f6d29f3122085bbe254800343b9f337219
created_at: '2026-10-17T05:17:40.449634+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Classification
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- tests/mission_runtime/test_artifact_none_classification.py
execution_mode: code_change
model: ''
owned_files:
- src/mission_runtime/artifacts.py
- tests/mission_runtime/test_artifact_none_classification.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Classifier taxonomy — new PRIMARY kinds + entries

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`) before parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Classify every mission file that currently falls through to `None`, with an honest
kind in the PRIMARY partition, in the single file→kind authority
`src/mission_runtime/artifacts.py`. Done when:

- Four new `MissionArtifactKind` members exist, all in `_PRIMARY_ARTIFACT_KINDS`.
- Every path in the data-model table resolves to its assigned kind and
  `is_primary_artifact_kind` is true; the four excluded paths still resolve to `None`.
- `assert_partition_invariant()` passes (P-1 total + disjoint) with the new members.
- `mission_file_basenames_for_kind` stays honest for every kind (FR-013).
- No new `# noqa` / `# type: ignore` / Sonar suppression; complexity ≤ 15.

Requirements: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010,
FR-011, FR-013, NFR-001, NFR-003, C-002, C-005.

## Context & Constraints

- Authority: `src/mission_runtime/artifacts.py` — `MissionArtifactKind` (enum),
  `_MISSION_FILE_KIND_BY_BASENAME` (basename→kind), `_COORD_RESIDUE_DIRS`
  (first-segment dir→kind, any depth), `_PRIMARY_ARTIFACT_KINDS` /
  `_PLACEMENT_ARTIFACT_KINDS`, `assert_partition_invariant`,
  `mission_file_basenames_for_kind` (inverse map, built from the basename dict only).
- The authoritative path→kind→partition table is in
  [data-model.md](../data-model.md). Follow it exactly.
- `MissionArtifactKind` is the mission-runtime enum — **distinct** from the charter
  `ArtifactKind`. Do not touch `src/charter/`.
- Honest-kind doctrine (the enum's own CONTRACT/REVIEW_CYCLE comments): do not map a
  basename to a kind that would make `mission_file_basenames_for_kind` lie. The new
  families earn their own kinds for exactly this reason.
- This WP is independent of WP02 (no dependency either way).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Execution worktrees are allocated per lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T001 – Add four PRIMARY MissionArtifactKind members

- **Purpose**: give the research-mission deliverables, the bulk-edit map, the plan goals, and the documentation release record honest kinds.
- **Steps**: In `MissionArtifactKind`, add, each with a short docstring comment in the module's established style (reference this mission + #5697, and the one-kind-per-family decision):
  - `RESEARCH_OUTPUT = "research_output"` — research-mission deliverables (findings/report/methodology/synthesis/literature-review); PRIMARY; distinct from the sw-dev `research.md` planning note (`RESEARCH`).
  - `OCCURRENCE_MAP = "occurrence_map"` — the bulk-edit occurrence classification map; PRIMARY.
  - `MISSION_GOALS = "mission_goals"` — the plan mission's `goals.md`; PRIMARY.
  - `RELEASE_RECORD = "release_record"` — the documentation publish handoff `release.md`; PRIMARY.
- **Files**: `src/mission_runtime/artifacts.py`.
- **Validation**: enum imports cleanly; values are snake_case and unique.

### Subtask T002 – Add the four members to _PRIMARY_ARTIFACT_KINDS

- **Purpose**: every new kind lands in the PRIMARY partition (C-002) and keeps P-1 total.
- **Steps**: add the four members to the `_PRIMARY_ARTIFACT_KINDS` frozenset with a one-line comment. Do NOT add anything to `_PLACEMENT_ARTIFACT_KINDS`.
- **Files**: `src/mission_runtime/artifacts.py`.
- **Validation**: `assert_partition_invariant()` passes.

### Subtask T003 – Add basename classifier entries

- **Purpose**: classify the single-segment mission files.
- **Steps**: add to `_MISSION_FILE_KIND_BY_BASENAME`, each with a brief comment:
  - `findings.md`, `report.md`, `methodology.md`, `synthesis.md`, `literature-review.md` → `RESEARCH_OUTPUT`.
  - `gap-analysis.md`, `audit-report.md` → `ANALYSIS_REPORT` (reuse; existing PRIMARY kind).
  - `occurrence_map.yaml` → `OCCURRENCE_MAP`.
  - `goals.md` → `MISSION_GOALS`.
  - `release.md` → `RELEASE_RECORD`.
  - `meta.json` → `PRIMARY_METADATA` (closes the path-only classifier gap; `PRIMARY_METADATA` is already PRIMARY).
- **Files**: `src/mission_runtime/artifacts.py`.
- **Validation**: `kind_for_mission_file("kitty-specs/m/<name>", mission_slug="m")` returns the mapped kind for each.
- **Watch-out (meta.json) — confirm each of these, record in history**: adding `meta.json → PRIMARY_METADATA` changes what path-only consumers see. Verify non-regressive:
  - `bookkeeping_projection`: already skips `meta.json` by basename (`status_and_primary_basenames`) and the two-way meta driver is unaffected — unchanged.
  - **`src/specify_cli/coordination/commit_router.py::_translate_to_owning_surface` (~1576–1582)**: today `kind_for_mission_file(meta.json) is None` → raises `PATH_UNROUTABLE`. After PRIMARY_METADATA it resolves a PRIMARY write dir instead. Safe ONLY because `meta.json` is PRIMARY-partitioned and never reaches the coord staging path — confirm that holds.
  - **`src/specify_cli/cli/commands/safe_commit_cmd.py::_first_recognized_kind` (~310–312)**: a `meta.json`-only commit flips from the None→generic-fallback path to `_resolve_mission_aware_target` (mission-aware PRIMARY). This is what FR-009 intends — verify it is non-regressive for a real mission meta write (`mission_number` bake / phase flip).
  - **`tests/mission_runtime/test_self_bookkeeping_allowlist.py::test_meta_json_is_self_bookkeeping`**: `is_self_bookkeeping_churn` is a SEPARATE allowlist authority (not `kind_for_mission_file`), so it should stay green — confirm it does.

### Subtask T004 – Add research/ dir entry to _COORD_RESIDUE_DIRS

- **Purpose**: classify the whole `research/` subtree (any depth) as RESEARCH in one entry — mirrors `contracts`/`decisions`.
- **Steps**: add `"research": MissionArtifactKind.RESEARCH` to `_COORD_RESIDUE_DIRS` with a comment noting it is PRIMARY (directory-anchored; nothing under `research/` is coordination-owned). Note the accepted edge case: a pathological `research/meta.json` / `research/mission-events.jsonl` misplacement classifies RESEARCH; this is low-harm because the dirty-state gates treat those as real dirt independently — do NOT add a filename-exclusion leg.
- **Files**: `src/mission_runtime/artifacts.py`.
- **Validation**: `kind_for_mission_file("kitty-specs/m/research/notes.md", mission_slug="m")` → `RESEARCH`; `.../research/x.py` → `RESEARCH`.

### Subtask T005 – Classification + invariant + inverse-map tests (red→green)

- **Purpose**: pin the new taxonomy and the invariants.
- **Steps**: create `tests/mission_runtime/test_artifact_none_classification.py`:
  - Parametrized: for each newly classified path assert `kind_for_mission_file(...)` equals the expected kind AND `is_primary_artifact_kind(kind)` is true. Include at least one nested `research/**` path and one `research/*.py`.
  - Parametrized negative control (FR-011): `lint-report.json`, `docs/x.md`, `answers.yaml`, `mission-events.jsonl` each classify to `None` — paired in the same test as a positively-classified path so the assertion is non-vacuous.
  - A wrong-`mission_slug` case still returns `None`.
  - `assert_partition_invariant()` passes (FR-010).
  - Inverse-map honesty (FR-013): `mission_file_basenames_for_kind(RESEARCH_OUTPUT)` equals exactly the five deliverable basenames; `mission_file_basenames_for_kind(ANALYSIS_REPORT)` includes `analysis-report.md`, `gap-analysis.md`, `audit-report.md`; the new single-member kinds map to exactly their one basename.
  - Run RED first where it is a genuine behaviour change (the classification cases fail on current main), then GREEN after T001–T004. Record the RED run in a history note.
- **Files**: `tests/mission_runtime/test_artifact_none_classification.py`.
- **Validation**: `.venv/bin/python -m pytest tests/mission_runtime/test_artifact_none_classification.py -q` green after the change.

### Subtask T006 – Blast-radius sweep of the new members

- **Purpose**: a new enum member must not silently break an exhaustiveness consumer.
- **Steps**: with codegraph or grep, check consumers of `MissionArtifactKind` for any exhaustive `match`/switch or kind-list that must learn the four new members, AND for membership-driven sets whose BEHAVIOUR flips for the reused kinds. Record a change-or-no-change decision + rationale for each in a history note. The specific sites the grounding review flagged (do NOT skip these):
  - `src/mission_runtime/resolution.py` `_E2_CONSOLIDATED_ELIGIBLE_KINDS` (~202–210): it is DERIVED as `frozenset(_PRIMARY_ARTIFACT_KINDS | {...})`, so it auto-absorbs the 4 new members. **Confirm this; do NOT widen it by hand.**
  - `src/mission_runtime/artifacts.py` `artifact_home_for` + `assert_partition_invariant`: both key on the frozenset → sufficient via membership alone.
  - **`src/specify_cli/lanes/auto_rebase.py` `_AUTO_REBASE_MANAGED_LAYOUT_KINDS` (~117) = `{LANE_STATE, WORK_PACKAGE_TASK, ANALYSIS_REPORT}`.** FR-005 reuses `ANALYSIS_REPORT` for `gap-analysis.md`/`audit-report.md`, which are ALREADY in this set. So those two files flip from None (auto-rebase Manual-halt on conflict) to deterministic take-theirs. Direction is consistent (an analysis report handled like an analysis report) — **decide + record** (expected: accept, no code change), do not discover it later.
  - **`src/specify_cli/consolidation/planning_recency.py` (~75–77)**: `if kind is None or not is_primary_artifact_kind(kind): return False`. Every newly-classified PRIMARY path (research/**, gap-analysis, goals, release, deliverables, meta.json) flips from "not a recency subject" to a planning-recency subject. **Decide + record** (expected: accept — a target-newer planning/research file engaging the recency check is correct).
  - `acceptance/__init__.py::_accept_planning_artifact_kinds` (~1190): a fixed 6-doc read-map with a primary-only invariant guard — the new kinds do NOT belong in it and do not break it. Confirm.
  - The new kinds are PRIMARY and planning-authored (RESEARCH/CHECKLIST precedent); only extend a consumer if non-vacuously required.
- **Files**: `src/mission_runtime/artifacts.py` (only if a consumer there needs it; otherwise none — the flips above are expected-accept).
- **Validation**: `.venv/bin/python -m pytest tests/mission_runtime/ -q` green; history note records each decision.

## Test Strategy

Run only the owned/affected module tests foreground (not a broad sweep):
`.venv/bin/python -m pytest tests/mission_runtime/ -q`. The orchestrator runs
the wider blast radius.

## Definition of Done

- T001–T006 complete; all `tests/mission_runtime/` green.
- `ruff check src/mission_runtime/artifacts.py` and `ruff format --check --force-exclude src/mission_runtime/artifacts.py tests/mission_runtime/test_artifact_none_classification.py` clean.
- `assert_partition_invariant()` passes; inverse map honest.
- No suppression added; complexity ≤ 15.
- History note records the meta.json consumer check (T003) and the blast-radius decisions (T006).

## Risks & Reviewer Guidance

- **Reviewer**: confirm every new member is in `_PRIMARY_ARTIFACT_KINDS` only; confirm the negative-control test is non-vacuous (paired with a positive); confirm `meta.json`→`PRIMARY_METADATA` broke no consumer; confirm no filename-exclusion leg was added for the `research/` edge case.
- **Risk**: an overlooked exhaustiveness switch. Mitigated by T006 + the module test sweep.
