---
work_package_id: WP03
title: Guidance, docs and changelog for org pack registration
dependencies:
- WP02
requirement_refs:
- FR-011
- SC-004
- C-005
planning_base_branch: issue-6267-charter-org-pack-registration
merge_target_branch: issue-6267-charter-org-pack-registration
branch_strategy: Planning artifacts for this mission were generated on issue-6267-charter-org-pack-registration. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6267-charter-org-pack-registration unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-org-pack-registration-01M6BTTJ
base_commit: 5016fc657ed34493ba2a31dc5c9628f4e4ce549f
created_at: '2026-11-01T19:31:32.395648+00:00'
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 3 - Polish and cross-cutting
history:
- at: '2026-11-01T15:20:00Z'
  actor: planner-priti
  action: 'Prompt generated via planning artifacts for #6267'
agent_profile: scribe-sally
authoritative_surface: docs/guides/how-to/governance/create-an-org-doctrine-pack.md
create_intent: []
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/cli/commands/charter/authoring.py
- docs/api/cli-commands.md
- docs/api/charter-commands.md
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/changelog/CHANGELOG.md
role: documentarian
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Guidance, docs and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

No documented flow tells a user to hand-edit `charter_packs.org.packs` any more: `charter fetch`'s
empty-registry message, the org-pack how-to and the CLI reference all name
`spec-kitty charter org add` / `remove`. The change is recorded in the changelog and the docs
freshness gate is green.

## Context & Constraints

- Spec: `kitty-specs/charter-org-pack-registration-01M6BTTJ/spec.md` (FR-011, SC-004, C-005).
- `docs/changelog/CHANGELOG.md` is the canonical changelog (root `CHANGELOG.md` is a symlink to it);
  entries live under `[Unreleased]`, lead with a bold impact-first sentence carrying `(#6267)`, then
  before/after, under 1,200 characters.
- `docs/api/cli-commands.md` is generated inside a `<!-- BEGIN GENERATED -->` envelope. Regenerate
  ONLY the touched command sections: build to a temp file with
  `uv run python -m scripts.docs.build_cli_reference --output /tmp/cli-ref.md --dry-run` and splice
  the `## spec-kitty charter org add` / `## spec-kitty charter org remove` sections. A whole-file
  rebuild races the shared CLI asset cache other agents on this host are rewriting.

## Branch Strategy

- **Strategy**: `issue-6267-charter-org-pack-registration`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T013 – `charter fetch` guidance

- **Steps**: in `src/specify_cli/cli/commands/charter/authoring.py`, change the "No org charter packs
  configured." hint from "Add an entry to the `charter_packs.org.packs` list in
  .kittify/config.yaml." to name `spec-kitty charter org add <name> --local-path <dir>`, keeping the
  existing sentence about the config key as the shape reference.

### Subtask T014 – CLI reference

- **Steps**: add the two new sections to `docs/api/cli-commands.md` (generated text, spliced), and add
  an `org` row to the subcommand table in `docs/api/charter-commands.md` pointing at the new command
  reference.

### Subtask T015 – Org-pack how-to

- **Steps**: rewrite Step 8 ("Configure consumers") of
  `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` so the primary path is the command;
  keep the YAML block as the shape reference and the field table as-is; keep the env-var section
  (`local_path` stored verbatim) and note that the command never expands or rewrites it; bump the
  page's `updated:` frontmatter date.

### Subtask T016 – Changelog

- **Steps**: add one `[Unreleased]` bullet under the CLI/charter area with `(#6267)`.

## Test Strategy

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run python -m scripts.docs.check_cli_reference_freshness
uv run python -m scripts.docs.check_changelog_style
uv run pytest tests/cli/test_charter_org_registration.py -q
```

## Risks & Mitigations

- Docs/code drift → the flag list in the doc is copied from the live `--help` output, not from this
  prompt.
- Full-reference rebuild churn → targeted splice, verified by the freshness checker.

## Review Guidance

- Every command spelling in prose must exist in `--help`.
- Confirm the changelog entry is under 1,200 characters and names the issue.
