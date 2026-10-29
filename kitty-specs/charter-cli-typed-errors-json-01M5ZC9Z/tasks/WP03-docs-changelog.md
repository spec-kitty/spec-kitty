---
work_package_id: WP03
title: Documentation and CHANGELOG
dependencies:
- WP01
- WP02
requirement_refs:
- FR-012
- C-001
- C-002
- C-006
planning_base_branch: issue-6557-charter-cli-typed-errors-json
merge_target_branch: issue-6557-charter-cli-typed-errors-json
branch_strategy: Planning artifacts for this mission were generated on issue-6557-charter-cli-typed-errors-json. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6557-charter-cli-typed-errors-json unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
phase: Phase 3 - Docs
history:
- at: '2026-10-27T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Documentation and CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every item first.

---

## Objectives & Success Criteria

- `docs/api/charter-commands.md` documents, for `charter status`, `charter activate` (positional) and
  `charter deactivate`: the `--json` success payloads, the `activation` block, the canonical error envelope and
  the local code table — each with `schema_version: "1.0.0"` and an explicit note that these are **local**
  shapes and codes, not the spec-kitty-charter activation contract (mapping held by #6518: #6520, #6521, #6524).
- `docs/changelog/CHANGELOG.md` `[Unreleased]` gets an entry covering #6557 (Fixed), the `--json` additions
  and activation block (Added, "Refs #6525, #6526 — local slice"), and a **Changed (breaking)** note:
  `charter status --json` errors now use `{ok:false, error:{code,message}}` instead of `{result, success, error}`.
- Every JSON example in the docs is byte-for-byte consistent (modulo placeholders) with the WP01/WP02 snapshot files.

Requirements: FR-012, C-001, C-002, C-006.

## Context & Constraints

- Sources of truth: `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/contracts/cli-json.md`, `data-model.md`, and the snapshot files
  `tests/specify_cli/cli/commands/charter/snapshots/activation_json/*.json`, `.../status_activation/*.json` (code is the source of truth; docs mirror shipped behaviour).
- Charter writing doctrine: audience = software-engineer / automation-agent; keep the page's Divio type (Reference) and update its `updated:` date.
- Existing doc sections: `docs/api/charter-commands.md` ~L280-290 (status) and ~L548 (preset JSON).
- Terminology: Mission (never "feature"); never write bare "routing".

## Branch Strategy

- **Planning base / merge target**: `issue-6557-charter-cli-typed-errors-json`.

## Subtasks & Detailed Guidance

### Subtask T013 – Reference docs

- Add/extend sections in `docs/api/charter-commands.md`:
  1. `charter status --json`: new `activation` block table (field, type, meaning), with the `null` vs `[]` distinction for `selected`, the `required[].in_force` rule (an explicit allow list that omits an org-required id keeps it out of force; a deny never removes it), and the `activation.error` form.
  2. `charter activate KIND ID --json` / `charter deactivate KIND ID --json`: payload table + cascade report table + one example each (copy from snapshots).
  3. Error envelope + local code table (from `contracts/cli-json.md`), exit codes, "usage errors stay exit 2 and are not JSON".
- Update the page's `updated:` frontmatter date to the commit date.

### Subtask T014 – CHANGELOG

- Under `## [Unreleased]` in `docs/changelog/CHANGELOG.md`, follow the file's existing heading style (Added / Changed / Fixed). Reference `#6557` (Fixes), `#6525`/`#6526` (local slice; integration under #6518).

### Subtask T015 – Cross-check

- Diff each docs JSON example against the snapshot files; run `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/quickstart.md` in a scratch project and confirm the outputs match the docs.
- Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` and any docs lint the repo runs on `docs/` changes (check `.github/workflows` for a docs check and run its command locally).

## Review Guidance

- Docs match snapshots; local-vs-contract disclaimer present; breaking change called out; issue refs do not claim to close #6525/#6526.

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "..."` · `spec-kitty agent tasks move-task WP03 --to <status>`
