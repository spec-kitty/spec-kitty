---
name: spk-start-first-feature
description: "Guide a first Spec Kitty feature from setup through specify, plan, tasks, implementation, review, accept, merge, and retrospective."
---

# spk-start-first-feature

Use this skill when a user wants to start their first Spec Kitty mission or
feature and needs the end-to-end path.

## Workflow

1. Verify install and agent surface with `spk-admin-setup-doctor` if commands or
   skills are missing.
2. Create or select the mission with `/spec-kitty.specify`.
3. Build the plan with `/spec-kitty.plan`.
4. Produce work packages with `/spec-kitty.tasks` or the outline/packages/finalize
   split when the project uses staged task authoring.
5. Advance work with `spk-run-next`.
6. Drive implementation/review loops with `spk-run-implement-review`.
7. Close with `spk-gate-accept`, then `spk-gate-consolidate`.
8. Finish post-merge checks with `spk-gate-mission-review` and
   `spk-gate-retrospective`.

## Guardrails

- Keep the user on one mission until a blocker requires a different route.
- Treat generated runtime prompt files as authoritative for the current action.
- Do not skip review, accept, or merge gates just because implementation appears
  complete.
