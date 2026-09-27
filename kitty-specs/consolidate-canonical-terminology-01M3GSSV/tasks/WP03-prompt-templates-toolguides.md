---
work_package_id: WP03
title: Prompt templates + toolguides
dependencies:
- WP01
requirement_refs:
- C-003
- C-005
- C-006
- FR-007
- NFR-004
planning_base_branch: feat/consolidate-canonical-terminology
merge_target_branch: feat/consolidate-canonical-terminology
branch_strategy: Planning artifacts for this mission were generated on feat/consolidate-canonical-terminology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidate-canonical-terminology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-canonical-terminology-01M3GSSV
base_commit: eb4b0424dea6a615b4c49b3a5de4bf376ddf1121
created_at: '2026-09-27T11:35:56.149316+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Consumer doctrine templates
history:
- at: '2026-09-27T07:39:01Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: packs/built-in/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- packs/built-in/missions/mission-steps/software-dev/accept/prompt.md
- packs/built-in/missions/mission-steps/software-dev/specify/prompt.md
- packs/built-in/toolguides/POWERSHELL_SYNTAX.md
- packs/built-in/directives/045-prs-only-and-read-intent.directive.yaml
- packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Prompt templates + toolguides

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!** Check the `review_ref` field (`spec-kitty agent tasks status`) and address all feedback before completion.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Convert lane-consolidation-sense `spec-kitty merge`→`spec-kitty consolidate` in the `packs/**`
prompt templates, toolguides, and doctrine files, classifying **each site** against
`occurrence_map.yaml`. Leave git-merge/publish senses verbatim.

Complete when:

- The owned packs/ files carry `spec-kitty consolidate` for the lane-consolidation sense; no active lane-consolidation-sense `spec-kitty merge` remains in them. *(FR-007)*
- git-merge/branch-integration and publish prose in the same files is untouched (C-003).
- Quality gates green: `pytest tests/architectural/test_no_legacy_terminology.py` (the ratchet WP01 added scans `packs/`); `ruff format --check .` where applicable. *(NFR-004)*

## Context & Constraints

- **Authoritative reads**: `.kittify/charter/charter.md`, [`plan.md`](../plan.md) (IC-05), [`spec.md`](../spec.md) FR-007, [`occurrence_map.yaml`](../occurrence_map.yaml).
- **`occurrence_map.yaml` is the classification authority (C-001).** These are `user_facing_strings: manual_review` sites — classify each occurrence: only the **lane-consolidation sense** (fold the lanes / accept-and-consolidate) becomes `consolidate`. A `git merge` command or a "publish/PR to origin" phrase stays verbatim (C-003).
- **C-005 — edit source, not generated copies.** `packs/built-in/**` are the SOURCE templates; the 13 agent copies regenerate via `spec-kitty upgrade` (WP02 owns the regeneration run). Never hand-edit `.claude/**` etc. here.
- **C-006 — immutable history untouched.** Do NOT touch `kitty-specs/**`, `docs/adr/**`, or `docs/changelog/**`.
- **Boundary**: this WP owns only the listed `packs/**` files. `src/**`, `tests/**`, generated agent dirs, `docs/**` belong to other WPs.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: `feat/consolidate-canonical-terminology`
- **Merge target branch**: `feat/consolidate-canonical-terminology`

## Subtasks & Detailed Guidance

### T020 – Mission-step prompts
- **Purpose**: The software-dev accept/specify step prompts name the canonical command (FR-007).
- **Steps**: In `packs/built-in/missions/mission-steps/software-dev/accept/prompt.md` convert the lane-consolidation-sense `spec-kitty merge` at :105 and :120. In `specify/prompt.md` convert :591. Confirm each is Sense 1 before editing.

### T021 – [P] Toolguide
- **Purpose**: `packs/built-in/toolguides/POWERSHELL_SYNTAX.md:54` shows a lane-consolidation `spec-kitty merge` example.
- **Steps**: Convert to `spec-kitty consolidate` if the surrounding example is lane consolidation (verify against occurrence_map).

### T022 – [P] Other packs/ doctrine sites
- **Purpose**: Grep found two more packs/ files carrying `spec-kitty merge`: `directives/045-prs-only-and-read-intent.directive.yaml` and `procedures/mission-wrap-up-sequence.procedure.yaml`.
- **Steps**: Classify each occurrence. The mission-wrap-up sequence and PR-intent directive describe the lane-consolidation step → convert. If any hit is a git-merge/publish reference, leave verbatim and note the classification. Re-grep `packs/` for any residual `spec-kitty merge` you may own.

### T023 – [P] Per-site classification confirm
- **Purpose**: DIRECTIVE_035 discipline — no unclassified edit.
- **Steps**: For every converted line, record its occurrence_map classification (Sense 1 lane consolidation). Confirm no git-merge (`git merge`, merge-driver, merge commit/conflict) or publish phrasing was swept.

## Test Strategy

- `pytest tests/architectural/test_no_legacy_terminology.py -q` — the WP01 ratchet scans `packs/`; expect green over the converted files (≈0.1 s).
- Grep the owned files for residual lane-consolidation-sense `spec-kitty merge` (expect none) and for surviving `git merge`/publish lines (expect intact).
- Record commands + counts in the PR *Tests run* section.

## Risks & Mitigations

- **Sweeping a git-merge/publish sense** → occurrence_map `manual_review` per site; C-003.
- **Missing a template that regenerates stale agent guidance** → re-grep the whole `packs/` tree for `spec-kitty merge`; convert every Sense-1 hit you own.
- **Editing a generated copy** → sources only; WP02 runs the regeneration.

## Review Guidance

- Confirm each converted line is Sense 1 (lane consolidation), with its occurrence_map classification cited.
- Confirm no `git merge` / merge-driver / publish line was altered.
- Confirm only the listed `packs/**` files changed (no `src/`, `tests/`, `docs/`, or generated agent dirs).

## Activity Log

> **CRITICAL**: chronological order, APPEND at the END.

- 2026-09-27T07:39:01Z – system – Prompt created.
