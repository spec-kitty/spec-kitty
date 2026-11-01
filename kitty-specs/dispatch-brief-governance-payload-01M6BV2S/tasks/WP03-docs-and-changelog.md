---
work_package_id: WP03
title: Document the brief flag, the profile option and the changelog entry
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
planning_base_branch: issue-6990-dispatch-brief-governance-payload
merge_target_branch: issue-6990-dispatch-brief-governance-payload
branch_strategy: Planning artifacts for this mission were generated on issue-6990-dispatch-brief-governance-payload. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6990-dispatch-brief-governance-payload unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Documentation
history:
- at: '2026-11-01T15:21:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
- docs/architecture/governed-profile-invocation.md
- src/charter/offering/skills/spec-kitty/SKILL.md
role: implementer
tags: []
task_type: documentation
tracker_refs: []
---

# Work Package Prompt: WP03 – Document the brief flag, the profile option and the changelog entry

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission dispatch-brief-governance-payload-01M6BV2S`) and address every item before handing back.

## Objectives & Success Criteria

- A user meeting `dispatch` learns that `--brief` exists, what it saves, and that
  it never replaces the first full read. Spec FR-005.
- The CLI reference help blocks for `dispatch` and `charter context` match the
  live Typer surface (`HELP-DRIFT` clean), regenerated **only** for those two
  blocks.
- A `[Unreleased]` changelog entry for #6990: bold impact-first lead with the
  issue reference, before/after, under 1,200 characters.
- `tests/architectural/test_no_legacy_terminology.py` passes (user-facing prose).

## Context

Surfaces to update, and why each one:

| Surface | What changes |
|---------|--------------|
| `docs/api/cli-commands.md` | the `spec-kitty dispatch` and `spec-kitty charter context` help blocks gain the new options |
| `docs/architecture/governed-profile-invocation.md` | it tells agents to read `governance_context_text`; add the opt-in brief mode and its fetch command |
| `src/charter/offering/skills/spec-kitty/SKILL.md` | the shipped standalone-invocation skill documents the payload field table and the "read the text, then work" contract |
| `docs/changelog/CHANGELOG.md` | `[Unreleased]` entry (#6990) |

Wording constraints that are easy to get wrong:

- `--brief` is **opt-in** and saves prompt tokens, not compute: dispatch still
  assembles governance on every call.
- It is for a re-dispatch inside a session whose full text you already read;
  the first read of a profile/action must still be the full payload (or the
  printed fetch command).
- The fetch command prints the payload's own action, which is derived from the
  request (e.g. `generate`), so quote it from the output rather than inventing an
  example action.

## Subtask T006 — Changelog

Add to the `[Unreleased]` section of `docs/changelog/CHANGELOG.md`, matching the
neighbouring entries' shape (bold impact-first lead, `(#6990)` reference,
**Before:** / **After:** prose, under 1,200 characters). The root `CHANGELOG.md`
is a symlink — edit the file under `docs/`. Run
`uv run python -m scripts.docs.check_changelog_style` if it is cheap.

## Subtask T007 — CLI reference help blocks

`scripts/docs/build_cli_reference.py` rebuilds the whole reference from the live
Typer surface, and on this shared host the global asset/command cache is written
concurrently by other agents. So:

1. Build into a scratch file (`--help` path or the builder's output option — read
   the script's argparse) and diff against `docs/api/cli-commands.md`.
2. Apply **only** the `## spec-kitty dispatch` and `## spec-kitty charter context`
   blocks from the fresh build; leave every other byte alone.
3. Verify with `SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run python -m scripts.docs.check_docs_freshness --ci`
   and require `errors=0`; `HELP-DRIFT` on the two updated commands must be gone.
4. If the full rebuild looks non-deterministic (unrelated blocks churning), keep
   the surgical edit and say so in the hand-off notes and the PR `## Deferred`.

## Subtask T008 — Architecture page and shipped skill

- `docs/architecture/governed-profile-invocation.md`: after the sentence that
  says the command returns `governance_context_text`, add a short paragraph on
  `--brief`: what it returns instead (digest + fetch command), when to use it
  (re-dispatch after the first read), and that it never suppresses the assembly
  or the Op record.
- `src/charter/offering/skills/spec-kitty/SKILL.md`: extend the response-field
  table and the "Governance context injection" steps with the brief mode. Keep
  the existing field rows intact; a test
  (`tests/charter_offering/test_spec_kitty_skill_content.py`) asserts
  `governance_context_text` is still mentioned, so do not delete that wording.
  Add the `charter context --action <a> --profile <id>` fetch command as the way
  to re-read the text.

## Subtask T009 — Gates

- `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
- `uv run pytest tests/architectural/test_docs_cli_reference_parity.py tests/charter_offering/test_spec_kitty_skill_content.py -q`
- the docs freshness command from T007, `errors=0`

## Definition of Done

- All four surfaces updated, consistent with each other and with the shipped
  options (`--help` output is the source of truth).
- `check_docs_freshness --ci` → `errors=0`; terminology guard green.
- Changelog entry under 1,200 characters with the `(#6990)` reference.

## Risks

- Copying help text by hand invites `HELP-DRIFT`; take it from a fresh build of
  the live surface.
- Over-claiming: do not say brief mode "skips governance" or "caches" anything.

## Reviewer guidance

- Check the documented fetch command actually runs and reproduces the text.
- Check the skill still tells an agent to read the text on first contact.
