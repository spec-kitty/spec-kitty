---
work_package_id: WP02
title: Spec template labels, specify guidance, parser + gate pins
dependencies: []
requirement_refs:
- C-003
- C-004
- C-007
- FR-001
- FR-002
- FR-003
- FR-004
- FR-009
- NFR-001
- NFR-004
planning_base_branch: claude/research-squad-remediation-mission-fvdk93
merge_target_branch: claude/research-squad-remediation-mission-fvdk93
branch_strategy: Planning artifacts for this mission were generated on claude/research-squad-remediation-mission-fvdk93. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/research-squad-remediation-mission-fvdk93 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-criterion-labels-positive-controls-01M3EWRT
base_commit: c799a96aec4e24121332eaeb3167c8b9913310e3
created_at: '2026-09-26T13:15:37.239988+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Template
history:
- at: '2026-09-26T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/software-dev/templates/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- packs/built-in/missions/software-dev/templates/spec-template.md
- packs/built-in/missions/mission-steps/software-dev/specify/prompt.md
- tests/specify_cli/test_requirement_mapping.py
- tests/specify_cli/missions/test_substantive_gate_formats.py
- tests/specify_cli/regression/_twelve_agent_baseline/**
- tests/specify_cli/skills/__snapshots__/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Spec template labels, specify guidance, parser + gate pins

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

- Software-dev spec template FR table gains trailing `Delivery` and `No-op passable?` columns, a legend, and one filled
  example; success criteria get a trailing suffix. (FR-001, FR-002)
- A labelled row stays declared and yields the same functional set through the production coverage path as its
  unlabelled twin; the same fixture's mis-placed-label row is not declared. (FR-003)
- The live scaffold stays non-substantive and declares exactly the placeholder ids it declared before; the same
  scaffold with Title/User Story filled is substantive (control). (FR-004)
- The specify prompt asks for the label and mark on each FR row and success criterion. (FR-009)

## Context & Constraints

- Read `kitty-specs/criterion-labels-positive-controls-01M3EWRT/{spec.md,plan.md,research.md,research/*.md}`.
- **C-004**: never place a label inside/before the requirement-id cell; no inline labels on FR bullets/headings; do NOT
  widen `src/specify_cli/requirement_mapping.py` patterns (the first-id-per-line `break` is load-bearing).
- **C-006**: the tactic `acceptance-criteria-non-vacuity` (WP01) is the only definition. The legend points to it and may
  carry one short gloss line explicitly marked "summary of tactic acceptance-criteria-non-vacuity".
- **C-007**: the filled example's id must not be declared by the parser — use `FR-EXAMPLE` (the id group is
  `(FR|NFR|C)-\d+`). Place it in the Requirements legend (the HTML comment block is fine; the parser does not strip
  comments, which is exactly why the id must be non-matching).
- No production code change is expected: `_substantive.py` reads only Title + User Story (`take_columns=2`). If a test
  shows otherwise, stop and record it — do not widen scope silently.
- Do not edit `.kittify/overrides/**` (WP03).

## Branch Strategy

- **Planning base branch**: `claude/research-squad-remediation-mission-fvdk93`
- **Merge target branch**: `claude/research-squad-remediation-mission-fvdk93`
- Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP02 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T007 – Parser + coverage tests (red-first where possible)

- **File**: `tests/specify_cli/test_requirement_mapping.py` — new class `TestDeliveryLabelledRequirementRows`.
- **One fixture** (module constant) with the new header and two rows:
  `| FR-001 | Title | story | High | Open | [build] | no |` and `| FR-002 [ratchet] | Title | story | High | Open | | |`.
  - Assert `FR-001` declared, `FR-002` **not** declared (same text ⇒ positive control per the new tactic).
- **Twin fixture**: the same spec without the two trailing columns. Assert `parse_requirement_ids_from_spec_md` gives
  identical `functional` sets for labelled vs twin (labelled rows only, excluding the mis-placed one).
- **Production path**: also drive the coverage computation the `map-requirements` / `finalize-tasks` commands use —
  find it from `src/specify_cli/cli/commands/agent/tasks_map_requirements.py` (look for how `unmapped_functional` is
  computed; `compute_coverage` in `requirement_mapping.py`) and assert labelled vs twin give the same unmapped set for
  the same WP refs. Prefer the function the command calls over a re-implementation.
- Also a row with a trailing label column that **cites** another id (`[folded] (FR-001)`) must not create a bare-prose
  finding (`find_bare_prose_requirement_ids`).

### Subtask T008 – Live-template substantive-gate tests

- **File**: `tests/specify_cli/missions/test_substantive_gate_formats.py`.
- Read the **live** template `packs/built-in/missions/software-dev/templates/spec-template.md` (repo-root relative, not
  the override) and assert:
  1. `is_substantive(<template text>, "spec")` (check the exact signature at `src/specify_cli/missions/_substantive.py:865`) is False.
  2. Positive control on the same fixture: replace the first FR row's Title and User Story with real text (leave the
     label placeholders) ⇒ substantive True.
  3. Declared id set of the template equals the frozen expected set (`FR-001..003`, `NFR-001..003`, `C-001..003`) — the
     `FR-EXAMPLE` row adds nothing.
- Write these before T009; (1) and (3) will already pass (ratchet) — that is expected and honest (spec marks FR-004
  `[ratchet]`, no-op passable `yes`); (2) is the control. Note this in the Activity Log.

### Subtask T009 – Template edit

- Header: `| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |`; placeholder rows end
  `| [build/ratchet/folded] | [yes/no] |`.
- Add the legend under `## Requirements` (inside or next to the ACTION REQUIRED comment): labels, no-op mark, what `yes`
  obliges, the pointer to the tactic + fetch command, and the filled example row with `FR-EXAMPLE`
  (e.g. a refusal criterion marked `yes — paired with a same-fixture positive control`).
- Success criteria bullets: append `— [build/ratchet/folded] · no-op passable: [yes/no]` guidance.
- NFR/C tables unchanged.

### Subtask T010 – Specify prompt guidance [P]

- `packs/built-in/missions/mission-steps/software-dev/specify/prompt.md` step 6 ("Generate separated requirement
  tables") and the Success Criteria Guidelines: add the label + mark instruction and the placement rule (trailing
  columns only). Add checklist line "Every FR row and success criterion carries a delivery label and no-op mark" to the
  quality checklist block in that prompt.

### Subtask T011 – Snapshot baselines

- `PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/regression/ tests/specify_cli/skills/ -q`, then rerun without the
  flag; inspect the snapshot diff — only the new guidance lines may change.

### Subtask T012 – NFR-001 corpus check

- Before editing (on the lane base) and after: dump declared-id sets for every `kitty-specs/*/spec.md` and diff
  (expect empty — parser untouched). Run `pytest tests/architectural/test_bare_prose_corpus_ratchet.py` with no baseline
  bump. Record both in the Activity Log.

## Test Strategy

```bash
source .venv/bin/activate
pytest tests/specify_cli/test_requirement_mapping.py tests/specify_cli/missions/test_substantive_gate_formats.py -q
pytest tests/specify_cli/regression/ tests/specify_cli/skills/ tests/integration/test_specify_plan_commit_boundary.py -q
pytest tests/architectural/test_bare_prose_corpus_ratchet.py tests/architectural/test_no_legacy_terminology.py tests/doctrine/test_generic_artifact_language_bias.py -q
ruff check <changed test files> && ruff format --check <changed test files> && mypy <changed test files>
```

## Definition of Done

- All tests above green; snapshot diff limited to the new guidance; corpus diff empty; Activity Log records RED/ratchet status per test.

## Risks & Mitigations

- `FR-EXAMPLE` accidentally matching a pattern → T008 (3) guards it.
- Language-bias test scanning template wording → run `tests/doctrine/test_generic_artifact_language_bias.py`.

## Review Guidance

- Is every new absence assertion paired with a control on the same fixture? Is the coverage claim proven through the
  command's own function, not only the helper?

## Activity Log
