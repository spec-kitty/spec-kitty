---
work_package_id: WP02
title: Changelog entry for the schema/authority parity fix
dependencies:
- WP01
requirement_refs:
- FR-001
- C-001
planning_base_branch: issue-6556-charter-yaml-activation-key-parity
merge_target_branch: issue-6556-charter-yaml-activation-key-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6556-charter-yaml-activation-key-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6556-charter-yaml-activation-key-parity unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - User-facing notes
history:
- at: '2026-10-30T23:22:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/doctrine-kinds.md
role: communicator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Changelog entry for the schema/authority parity fix

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `communicator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- One `[Unreleased]` → `### Fixed` bullet in `docs/changelog/CHANGELOG.md` that leads with the
  impact in bold, carries `(#6556)`, gives a before/after a reader can act on, and stays
  under 1,200 characters (FR-001, C-001).
- No stale doc sentence left claiming the schema rejects keys it now accepts (T007).

## Context & Constraints

- Root `CHANGELOG.md` is a **symlink** to `docs/changelog/CHANGELOG.md` — edit the latter.
- The audience is an operator or a caller of the charter API, not a maintainer reading the
  diff: say what they can now do (schema-validate a `charter.yaml` that carries legal
  activation keys), and name the three keys that were rejected, because those names appear in
  their own `charter.yaml`.
- Do not re-document the activation ledger (#6496 already did) and do not describe
  `activated_assets` as missing — it is deliberately not an activation key (C-001).
- Keep the entry in the established house style: `- **<impact lead>** (#6556). **Before:** …
  **After:** … **What to do:** …` is optional; before/after is required.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on main; completed changes must merge back into main. Execution happens in the lane worktree `finalize-tasks` computes; never build a workspace path by hand.
- **Planning base branch**: main
- **Merge target branch**: main

## Subtasks & Detailed Guidance

### Subtask T006 – Add the `[Unreleased]` Fixed entry

- **Purpose**: record the user-facing effect of WP01.
- **Steps**:
  1. Open `docs/changelog/CHANGELOG.md`, find `## [Unreleased] - 4.0.0rc8`, and add the bullet
     under its `### Fixed` section (create that section only if it is absent, mirroring the
     existing heading style).
  2. Write impact first: a caller can now schema-validate a legitimate `charter.yaml`;
     before, `CharterYaml` rejected `activated_skills`, `activated_glossary_packs` and
     `activated_anti_patterns` — keys the activation writer itself writes — with
     `extra_forbidden`, so the model could not be used as the `charter.yaml` schema.
  3. Finish with what a reader does about it: nothing for the common case (no on-disk change);
     a caller that worked around the missing fields can drop the workaround.
  4. Keep it under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: No.
- **Notes**: parallel agents also edit this file — keep the bullet self-contained and, when
  rebasing, keep both sides' entries.

### Subtask T007 – Correct only what the change makes false

- **Purpose**: leave the docs truthful without re-documenting the feature.
- **Steps**:
  1. `grep -n "activated_assets\|CharterYaml" docs/architecture/doctrine-kinds.md` and read the
     matching sentences.
  2. If (and only if) a sentence claims the model or schema rejects keys it now accepts,
     correct that sentence. Do not rewrite the page, and do not add a `CharterYaml` tutorial.
  3. If the page changed, run `uv run python -m scripts.docs.check_docs_freshness --ci` and
     expect `errors=0`; if the page did not change, say so in your progress note instead of
     running unrelated regeneration.
- **Files**: `docs/architecture/doctrine-kinds.md` (only if needed).
- **Parallel?**: No.
- **Notes**: `docs/api/` reference pages are generated — do not hand-edit them.

## Test Strategy

- No behavioural tests for this WP. Verify the markdown renders (headings intact, bullet in the
  right section) and, if a doc page changed, the freshness check above.
- The PR-body validator (`python packs/internal/assets/validate-pr-body.py`) belongs to the
  PR step, not here.

## Risks & Mitigations

- **Over-long or internal-sounding entry** → cut to the reader's decision: what changed, what
  they must do (usually nothing).
- **Changelog conflict with a parallel agent** → keep the entry self-contained and in
  `[Unreleased]`; resolve rebase conflicts by keeping both sides' bullets.
- **Doc churn** → change one sentence or none.

## Review Guidance

- The bullet names the issue, the three keys, and the before/after, and is under 1,200
  characters.
- Nothing in the entry contradicts #6496 (activation lives in
  `.kittify/charter/activation.yaml` for migrated projects).
- No unrelated doc edits.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
