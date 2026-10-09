---
work_package_id: WP02
title: ADR + docs for the run-dir writer model
dependencies:
- WP01
requirement_refs:
- FR-005
planning_base_branch: issue-5854-serialise-next
merge_target_branch: issue-5854-serialise-next
branch_strategy: Planning artifacts for this mission were generated on issue-5854-serialise-next. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5854-serialise-next unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Documentation
history:
- at: '2026-10-08T19:39:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-08-1-serialise-run-dir-advance.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-08-1-serialise-run-dir-advance.md
- docs/architecture/runtime-loop.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – ADR + docs for the run-dir writer model

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Record the cross-process run-dir writer model as a decision record and state the
shipped guarantee where the multi-agent loop is advertised; add a changelog entry.

- A short, well-formed 4.x ADR documents the run-cursor lock resource, the
  index-released-before-run-dir ordering invariant, the commit-span-only hold, the
  expected-step compare-and-swap, and the contention-→`blocked` ruling.
- `docs/architecture/runtime-loop.md` states the serialisation guarantee where it
  currently advertises "multiple agents … in parallel".
- A CHANGELOG `[Unreleased]` entry names the fix and closes #5854, #5682.

## Context & Constraints

- Depends on **WP01** — document the behavior WP01 ships, not a proposal.
- Source of truth: `kitty-specs/serialise-next-advance-01M4EF16/research.md`
  (adjudicated design + squad dispositions) and `plan.md`.
- ADR cross-references (doctrine note): cite ADR
  `docs/adr/2.x/2026-02-17-1-*` (the canonical `next` contract — the `blocked`
  reuse) and note the `run_index` lock (`src/runtime/next/run_index.py`, #5389) as
  the same-primitive precedent (it shipped ADR-less).
- Follow the ADR template/shape already used in `docs/adr/4.x/`. Confirm the
  filename's date-and-number prefix does not collide with an existing 4.x ADR; if
  `2026-10-08-1-...` is taken, bump the sequence number and update `owned_files`
  via a one-line rationale.
- Divio: the ADR is an Explanation/decision record; the runtime-loop update is
  Reference. Keep an `updated: YYYY-MM-DD` date on any page that carries one.
- Terminology: "Mission"/"run cursor"; never `feature*`.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T009 – Write the 4.x ADR

- **Files**: `docs/adr/4.x/2026-10-08-1-serialise-run-dir-advance.md` (new).
- **Steps**: record Context (the #5854/#5682 races), Decision (expected-step CAS
  folded into `StaleAdvancePlan`; a per-run-dir `kernel.locks` lock around the
  commit RMW, span excludes executor dispatch; engine path refuses via the existing
  `blocked` contract; unique snapshot temp), Consequences (contention/stale →
  `blocked`; #5112 livelock named as a residual; executor exactly-once out of
  scope), and the two cross-references above.

### Subtask T010 – Update the runtime-loop doc [P]

- **Files**: `docs/architecture/runtime-loop.md`.
- **Steps**: where it says agents run "in parallel", add the shipped guarantee:
  advancing a given run is serialised; overlapping advances do not both mutate the
  cursor — a stale/contended advance is refused (`blocked`). Keep it short.

### Subtask T011 – CHANGELOG entry [P]

- **Files**: `docs/changelog/CHANGELOG.md`.
- **Steps**: add an `[Unreleased]` entry (follow the file's existing style/gate):
  "Serialise concurrent `spec-kitty next` on one run; refuse a stale advance
  instead of silently completing or re-planning it (#5854, #5682)."

## Test Strategy

- No code tests. Run the docs gates the repo enforces on changed files:
  `pytest tests/docs/test_changelog_style.py` (and any ADR/doc freshness check the
  repo runs) must pass. Confirm `ruff format --check` is not implicated (Markdown).

## Risks & Mitigations

- ADR filename collision → verify the sequence number against existing 4.x ADRs.
- Over-long ADR → keep it to the decision; link research.md for detail.

## Review Guidance

- ADR present, well-formed, cross-referenced; runtime-loop names the guarantee;
  changelog style gate passes; no `feature*` wording.

## Activity Log

- 2026-10-08T19:39:08Z – system – Prompt created.
