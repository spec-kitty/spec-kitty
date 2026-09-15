---
work_package_id: WP06
title: Cross-track synthesis + green consolidation (FR-009)
dependencies:
- WP02
- WP04
- WP05
requirement_refs:
- FR-009
- NFR-003
- NFR-004
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T11:59:10.324942+00:00'
subtasks:
- T014
- T015
history:
- created by /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/architecture/
create_intent:
- docs/architecture/post-merge-partition-authority.md
execution_mode: code_change
model: sonnet
owned_files:
- docs/architecture/post-merge-partition-authority.md
- CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Cross-track synthesis + green consolidation (FR-009)

## ⚡ Do This First: Load Agent Profile

- **Profile**: `architect-alphonso` (structure / seams / synthesis)
- **Role**: `implementer`

---

## Objectives & Success Criteria

Deliver the operator-requested cross-track root-cause synthesis and consolidate both tracks green.

- SC: `docs/architecture/post-merge-partition-authority.md` maps the write authority (Track A) and read authority (Track B) onto one "authoritative content per artifact per surface" model, names both seams, and gives a defended shared-vs-disjoint verdict (SC-005).
- SC: combined regression green — both red-first tests pass, and the preserved #2709/#2804/#3981 suites pass (SC-004).
- SC: NFR-003 complexity census on all touched functions ≤15; CHANGELOG entries for #3942, #4090 (+#4091 disposition).

## Context & Constraints

This is the only cross-track join and the FR-009 deliverable (the operator's stated reason for one mission). Record, for the epic owners:
- **#2907**: D-A1 drives squash conflict resolution off `mission_runtime.kind_for_mission_file` — the #2709 "target-newer canonical state is reconciled not replaced" principle extended from meta *fields* to primary-artifact-kind *files*. Note the dead `merge/conflict_resolver.py` disposition (competing `ConflictType` taxonomy to retire).
- **#2160**: D-B1 chooses "override the stale husk on primary" over "freshen the husk" — a coord-authority decision for the epic owner to ratify; keeps the single canonical post-merge authority on PRIMARY.
- **Shared root**: both are "what is authoritative post-merge, and on which surface" — Track A the write half (bytes-per-artifact), Track B the read half (surface-per-reader). State whether a single unifying seam exists (the classifier + partition doctrine) or they are genuinely disjoint-but-thematically-shared (the squad's finding).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T014 – FR-009 synthesis doc
- **Steps**: Write `docs/architecture/post-merge-partition-authority.md` per the Context above. Follow `docs/architecture/README.md` conventions. Keep description length within the docs SEO gate (50–180 chars) if a front-matter description is required.

### Subtask T015 – Consolidation + census + CHANGELOG
- **Steps**: Run the combined regression (both red-first tests + preserved suites). Run the NFR-003 complexity census (`ruff check` C901 on touched files). Add CHANGELOG entries for #3942 and #4090, plus the #4091 disposition (fix or verified-already-fixed per WP05).

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest \
  tests/merge/test_squash_target_newer_planning_3942.py \
  tests/merge/test_planning_recency_helper.py \
  tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py \
  tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py \
  tests/merge/test_event_count_union_4091.py \
  tests/merge/test_squash_reconcilers_2709.py \
  tests/merge/test_gate_artifact_merge_drivers_2804.py \
  -q -p no:cacheprovider
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci || true
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Risks & Mitigations
- **Docs gates**: description-length (50–180) + freshness are CI gates — run them locally and regenerate rollups if the new doc requires an inventory entry.
- **Synthesis as filler**: the doc must cite both seams and give a defended verdict, not restate the spec.

## Review Guidance
- Confirm the synthesis cites both seams + the epic notes (#2907/#2160) and gives a shared-vs-disjoint verdict.
- Confirm the full combined regression is green and CHANGELOG covers all three issues.

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
