---
work_package_id: WP04
title: Changelog and docs
dependencies:
- WP02
- WP03
requirement_refs:
- FR-002
- FR-003
planning_base_branch: issue-6743-pack-file-name-collision-diagnostic
merge_target_branch: issue-6743-pack-file-name-collision-diagnostic
branch_strategy: Planning artifacts for this mission were generated on issue-6743-pack-file-name-collision-diagnostic. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6743-pack-file-name-collision-diagnostic unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
phase: Phase 4 - Polish
history:
- at: '2026-10-30T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/charter-commands.md
- docs/api/cli-commands.md
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
role: documenter
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Changelog and docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the profile in the frontmatter
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `documenter`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log before starting; address every item and
record it with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

An operator or pack author finds the new `file_name_collision` error where they
already look: the changelog, the two command references, and the org-pack how-to.

Done when:

- `docs/changelog/CHANGELOG.md` has one `[Unreleased]` entry: bold impact-first
  lead ending in `(#6743)`, then `**Before:**` / `**After:**`, under 1,200 characters.
- `docs/api/charter-commands.md` (the `charter pack validate` section) lists
  `file_name_collision` among the error categories and says what to do.
- `docs/api/cli-commands.md` (`spec-kitty charter pack validate`, and the
  `doctor charter-packs` section) mentions the finding and the
  `org_drg.file_name_collisions` JSON key.
- `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` tells the author,
  in the validate step, that a reused file name with a different id is an error
  and to rename one of the files.
- `uv run python -m scripts.docs.docs_index --write` and
  `uv run python -m scripts.docs.check_docs_freshness --ci` report
  `errors=0` if a docs index changed; `tests/architectural/test_no_legacy_terminology.py`
  passes.

## Context & Constraints

- Spec FR-002 / FR-003; C-003 (error severity, no opt-in — say so, and say why a
  deliberate override is unaffected: the override keeps the same id).
- Plan DD-5. The shipped wording comes from WP02/WP03 — read the final message
  text from a real run before writing docs; do not invent a synonym.
- Do not restate the doctrine pack-tier rules; link them.
- Keep the changelog entry in the `[Unreleased]` section, newest first.

## Branch Strategy

- Planning base and merge target: `issue-6743-pack-file-name-collision-diagnostic`.
- Execute in the lane worktree allocated by
  `spec-kitty agent action implement WP04 --agent python-pedro --mission pack-file-name-collision-diagnostic-01M66YTQ`.

## Subtasks & Detailed Guidance

### Subtask T013 – Changelog entry

- **Purpose**: the entry the release notes are built from.
- **Steps**: add one bullet under `## [Unreleased]` in `docs/changelog/CHANGELOG.md`
  (the root `CHANGELOG.md` is a symlink to it — do not create a second file). Bold
  lead, `(#6743)`, `**Before:**`, `**After:**`, under 1,200 characters, no
  machine-local paths.
- **Files**: `docs/changelog/CHANGELOG.md`

### Subtask T014 – Command references

- **Purpose**: the reference pages operators grep.
- **Steps**: update the `charter pack validate` category list in
  `docs/api/charter-commands.md`; update the `doctor charter-packs` JSON key list in
  `docs/api/cli-commands.md` with `org_drg.file_name_collisions` and its record
  shape (`kind`, `file_name`, `declarations[{layer, declared_id, path}]`).
- **Files**: `docs/api/charter-commands.md`, `docs/api/cli-commands.md`
- **Parallel?**: yes with T015.

### Subtask T015 – Org-pack how-to

- **Purpose**: the author-facing warning at the point where they name files.
- **Steps**: one short paragraph in the validate step of
  `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`.
- **Files**: `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`
- **Parallel?**: yes with T014.

### Subtask T016 – Mission records

- **Purpose**: keep the tracer and issue records honest.
- **Steps**: append one `design-decisions` tracer entry with the final wording and
  one `tooling-friction` entry if the docs pass hit anything; confirm the issue
  matrix row for #6743 exists (`spec-kitty agent issue-verdict` is run by the
  orchestrator at wrap-up — do not invent a verdict here).
- **Files**: `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/traces/` (via the CLI)

## Test Strategy

```bash
uv run python -m scripts.docs.check_docs_freshness --ci     # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
python packs/internal/assets/validate-pr-body.py <pr-body.md>   # later, at PR time
```

## Risks & Mitigations

- Changelog conflicts with concurrent missions → keep both sides when rebasing.
- Docs drift from the shipped message → copy the wording from the actual command run.

## Review Guidance

- Does the entry lead with the user-visible impact and cite `#6743`?
- Do the docs say "error" and "rename one of the files"?
- Was the docs index regenerated rather than hand-edited?

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP04 --to <status>`
