---
work_package_id: WP03
title: Docs and changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-011
- C-005
planning_base_branch: issue-6754-migration-actor-cli-spoofing
merge_target_branch: issue-6754-migration-actor-cli-spoofing
branch_strategy: Planning artifacts for this mission were generated on issue-6754-migration-actor-cli-spoofing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6754-migration-actor-cli-spoofing unless the human explicitly redirects the landing branch.
base_branch: issue-6754-migration-actor-cli-spoofing
base_commit: 7a829c3eb90dd746c1ef52cf4fdfd54a1347e457
created_at: '2026-10-30T17:54:15+00:00'
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Documentation
history:
- at: '2026-10-30T17:54:15Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/architecture/status-model.md
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/architecture/status-model.md
- docs/api/agent-subcommands.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: documentation
tracker_refs: []
---

# Work Package Prompt: WP03 – Docs and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item before your work is complete and record each change with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

Records the change for the people it affects (FR-011) and states the compatibility consequence (C-005).

- `docs/architecture/status-model.md` says, in "The actor", that a `migration:` actor can only come from an in-process migration, and that a caller-supplied seed-shaped identity is refused.
- `docs/api/agent-subcommands.md` carries the final `agent status emit --actor` help text verbatim.
- `docs/changelog/CHANGELOG.md` has one `[Unreleased]` entry: bold impact-first lead with `(#6754)`, before/after, the compatibility consequence and the remedy, under 1,200 characters.

## Context & Constraints

- Spec: FR-011, C-005; plan IC-04; `quickstart.md` is the witness script the docs must agree with.
- Audience for the architecture page: a maintainer or an integrator reading the event-log contract. Audience for the changelog entry: an operator who upgrades and may have scripted `--actor`.
- **Do not rewrite ADRs.** `docs/adr/4.x/2026-10-07-3-review-lane-exit-requires-verdict-or-forced-note.md` records a past decision ("migration actors are exempt"); leave it. The new rule narrows *production*, not the exemption.
- **Do not restate doctrine**; link the architecture page. Keep the Divio quadrant the page already occupies (reference/explanation), and refresh the page's `updated:` frontmatter date if the page carries one.
- The changelog file is `docs/changelog/CHANGELOG.md`; the root `CHANGELOG.md` is a symlink to it. Edit the symlink target.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6754-migration-actor-cli-spoofing`
- **Merge target branch**: `issue-6754-migration-actor-cli-spoofing`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP03 --agent claude --mission migration-actor-cli-spoofing-01M66YYX
```

## Subtasks & Detailed Guidance

### Subtask T011 – `docs/architecture/status-model.md`

- **Where**: the "The actor" section, under "Still strings." (it already says migrations keep writing a string actor).
- **What to add** (2–4 sentences, plus one table row or bullet if it reads better):
  - A `migration:` actor means one thing: an in-process migration reconstructed that event. It is never a live decision.
  - A caller-supplied identity starting with `migration:` is **refused** by `agent status emit --actor`, the four `orchestrator-api` lifecycle verbs (as `USAGE_ERROR`) and the hidden `implement --actor`; the value is never rewritten.
  - An explicit `--agent migration:x` is *not* refused: it is parsed as the compact form, so the tool is `migration` and it is not a seed.
- Keep the existing voice and table style; no new headings.

### Subtask T012 – `docs/api/agent-subcommands.md` [P]

- **Where**: the `spec-kitty agent status emit` block, the `--actor` help line.
- **What**: copy the final help string from `src/specify_cli/cli/commands/agent/status.py` character-for-character (the file is hand-maintained from `--help` output; drift is a doc defect). If the `implement` section documents `--actor`, update it too only if WP02 changed that help text.
- Do not reformat the box-drawing block; keep the column alignment of the surrounding lines.

### Subtask T013 – `[Unreleased]` changelog entry

- **Where**: `docs/changelog/CHANGELOG.md`, directly under `## [Unreleased]` (match the existing entry format and bullet style).
- **Shape**:
  - Bold, impact-first lead sentence ending with `(#6754)`.
  - **Before:** a `--actor` beginning with `migration:` was stored verbatim and classified as a reconstruction seed, so a caller could make a live transition look like reconstruction (exempt from the review-exit note, invisible to consolidation work windows and to timestamp continuity).
  - **After:** `agent status emit --actor`, the four `orchestrator-api` lifecycle verbs and the hidden `implement --actor` refuse it (exit 1, nothing written); only in-process migrations produce a `migration:` actor. Explicit `--agent migration:x` is unchanged (tool `migration`, not a seed), recorded seeds stay seeds, and stored logs are unaffected.
  - **Compatibility:** a script that passed `--actor migration:…` now fails loudly instead of silently seeding; pass the live identity instead.
- Under 1,200 characters. Do not mention file names or internal symbols. Do not add a version number (C-001 of the charter's specify action: no version numbers in scope).

## Test Strategy

```bash
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
uv run --frozen python -m scripts.docs.docs_index --write        # only if a page was added; expect no diff otherwise
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py tests/architectural/test_docs_index_current.py -q
```

`check_docs_freshness` must report errors=0. If `docs_index --write` produces no diff for a modified page, that is expected — revert nothing.

## Risks & Mitigations

- **Stale help copy** is the likeliest defect: copy from the source file, do not retype from memory.
- **Over-claiming.** Do not say `--agent` is refused; it is not, and the asymmetry is deliberate (operator ruling 2026-10-29). Say *why* in one clause.
- **Changelog bloat.** 1,200 characters is a hard ceiling; put the detail in the architecture page and keep the entry to impact + before/after + remedy.

## Review Guidance

- Read `quickstart.md` and confirm every step of it produces what the docs now claim.
- Confirm the changelog entry leads with the user impact and cites `(#6754)`.
- Confirm no ADR was edited and no terminology regressed (`Mission`, not `Feature`).

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP03 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T011 --status done`.
