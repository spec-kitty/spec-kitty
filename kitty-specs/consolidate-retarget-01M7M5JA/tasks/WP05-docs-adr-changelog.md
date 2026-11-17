---
work_package_id: WP05
title: Docs, ADR amendment, changelog
dependencies:
- WP03
requirement_refs:
- C-007
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
phase: Phase 4 - Docs
history:
- at: '2026-11-17T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7692-consolidate-retarget.added.md
execution_mode: planning_artifact
owned_files:
- docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
- docs/guides/how-to/missions/merge-mission.md
- docs/changelog/unreleased/7692-consolidate-retarget.added.md
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Docs, ADR amendment, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Any review feedback is your TODO list.

---

## Objectives & Success Criteria

- ADR `2026-09-19-1` gains an **Amendment 2026-11-17 (#7692)** that records:
  - the run record's new `retarget` field and its lifecycle (created before the claim, `committed` after the record commits, kept with `committed=False` by a full-restore re-baseline, cleared by `--abort`);
  - that the retarget record commits are undone ONLY by the one rollback authority (restoring the new target and the Mission branch to their snapshot tips);
  - that the claim's status surface follows the effective target on a retarget;
  - the residual: a kill between the record commits and the `committed` persist resumes as `UNEXPLAINED_BRANCH_MOVE`. This is the same residual as the primary-tree mission-number bake. The remedy is `--abort --release-branch`.
- The merge-mission how-to's `--target` section documents `--retarget` / `--retarget-reason`, the refusals (`RETARGET_RECORD_UNWRITABLE`, `PROTECTED_BRANCH_REFUSED`, `RETARGET_RESUME_MISMATCH`), the scope (explicit `lanes` / `lanes_with_coord` Missions; default-topology Missions before their landing are refused), that orchestrator-api cannot retarget, and abort/resume behaviour.
- A changelog fragment in the `added` section.
- The doc checkers pass with 0 errors.

## Context & Constraints

- Read `spec.md`, `plan.md` D3–D10, `research.md`, `contracts/cli-retarget.md` and `quickstart.md`.
- Follow the existing amendment style in the ADR (search it for `Amendment`) and the changelog fragment rules in `docs/changelog/unreleased/README.md`. Use the existing #5783 fragment as the shape reference: `docs/changelog/unreleased/5783-target-override-recorded-target-unwritable.fixed.md`.
- Terminology: Mission, consolidate, landing, recorded target. Never say "feature". Use "merge" only for git merges.
- Plain, short sentences. Write for an operator.

## Branch Strategy

- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

`spec-kitty agent action implement WP05 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T022 – ADR amendment

Add the amendment at the end of `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`, after the existing amendments, and in their format. Cover the bullets in the Objectives. State that no gate allowlist was added, and that `_SPAN_PHASES` gained `_phase_retarget_record` (the first mutation of a retarget run).

### Subtask T023 – Merge-mission how-to [P]

In `docs/guides/how-to/missions/merge-mission.md`, extend the `--target` section that #7688 wrote: "When the recorded target cannot be written". Add a subsection "Retarget the Mission" with:
- the quickstart command sequence;
- what gets recorded;
- the refusals table;
- a scope note;
- abort and resume behaviour.

Keep the existing text; update only the remedy sentence so it names `--retarget`.

### Subtask T024 – Changelog fragment [P]

Create `docs/changelog/unreleased/7692-consolidate-retarget.added.md`. Write one short paragraph: `spec-kitty consolidate --target <branch> --retarget` makes the branch the Mission's recorded target and lands every write there. Then the codes, then the scope.

## Test Strategy

```
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -n0 -q
```

## Risks & Mitigations

- Doc drift from the code: re-read WP03's merged code before writing. The amendment must describe what was built.

## Review Guidance

- The amendment matches the code.
- The residual is stated plainly.
- The checkers pass.

## Progress & Status

`spec-kitty agent tasks add-history WP05 --note "..."`.
