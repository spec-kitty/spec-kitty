---
work_package_id: WP05
title: Documentation
dependencies:
- WP04
requirement_refs:
- C-002
planning_base_branch: issue-7566-path-conventions-per-type
merge_target_branch: issue-7566-path-conventions-per-type
branch_strategy: Planning artifacts for this mission were generated on issue-7566-path-conventions-per-type. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7566-path-conventions-per-type unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
phase: Phase 3 - Polish
history:
- at: '2026-11-20T07:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7566-path-conventions-per-type.added.md
execution_mode: planning_artifact
owned_files:
- docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md
- docs/guides/how-to/missions/accept-and-merge.md
- docs/changelog/unreleased/7566-path-conventions-per-type.added.md
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Documentation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

Record status moves as `claude::scribe-sally` (no model name).

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address all feedback before completion.

## Markdown Formatting

Wrap HTML/XML tags in backticks; use language identifiers in code blocks.

## Objectives & Success Criteria

- ADR `2026-08-28-1` gets an `## Amendment 2026-11-20: per-mission-type sections and narrow waivers (#7566, #7748)` that states:
  - the new precedence order;
  - the roster rule and the fail-closed cases;
  - that `deliverables` stays excluded inside sections;
  - the remedy order;
  - both waivers, and that metadata stays strict;
  - that orchestrator-api offers no per-run waiver.

  Update the frontmatter `updated:` field.
- The how-to `docs/guides/how-to/missions/accept-and-merge.md` shows the per-type form first (an open-packs-style example), keeps the flat form, presents the waivers, and demotes the mission.yaml copy to a last resort.
- A changelog fragment `docs/changelog/unreleased/7566-path-conventions-per-type.added.md` follows `docs/changelog/unreleased/README.md`.

## Context & Constraints

- Read `docs/changelog/unreleased/README.md` for the fragment format; look at `7512-path-convention-text-no-mkdir.fixed.md` as an example.
- Plain, concise wording. Use "Mission", never "feature".
- The behaviour to describe is in `kitty-specs/path-conventions-per-type-01M7VRQM/contracts/`.
- After editing the ADR, check whether a docs gate needs regeneration (`docs/development/docs-retrieval-index.yaml`, ADR era tables). If one fails in CI, regenerate it with the documented command; do not hand-edit generated files.

## Branch Strategy

- **Planning base branch**: `issue-7566-path-conventions-per-type`
- **Merge target branch**: `issue-7566-path-conventions-per-type`
- Implement with `spec-kitty agent action implement WP05 --agent claude --mission path-conventions-per-type-01M7VRQM`.

## Subtasks & Detailed Guidance

### Subtask T020 – ADR amendment

Append the amendment at the end of the ADR (after the #7512 amendment). Include a YAML example of the per-type form and the four-step precedence list from `contracts/precedence-contract.md`.

### Subtask T021 – How-to update

In the path-conventions section of `accept-and-merge.md`:
1. **Remap for one mission type** (first): the per-type YAML example.
2. **Remap for every mission type**: the existing flat example.
3. **Waive only the path check**: the per-run flag and the `meta.json` declaration, and that metadata stays strict.
4. `--lenient`: the broad escape (keep the existing sentence about the metadata checks).
5. **Last resort**: the mission.yaml copy, noting it freezes the definition.

### Subtask T022 – Changelog fragment

One fragment (the `added` section) covering the per-type sections, the waivers and the remedy order. Reference #7566 and #7748.

Validate:

```bash
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
```

## Review Guidance

- The docs match the implemented text and flags exactly (flag names, field names).

## Progress & Status

`spec-kitty agent tasks mark-status T020 T021 T022 --status done --mission path-conventions-per-type-01M7VRQM`.
