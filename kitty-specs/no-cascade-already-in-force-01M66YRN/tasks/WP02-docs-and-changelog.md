---
work_package_id: WP02
title: Document the already-in-force note and the new JSON field
dependencies:
- WP01
requirement_refs:
- FR-008
- C-002
planning_base_branch: issue-6742-no-cascade-already-in-force
merge_target_branch: issue-6742-no-cascade-already-in-force
branch_strategy: Planning artifacts for this mission were generated on issue-6742-no-cascade-already-in-force. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6742-no-cascade-already-in-force unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/api/
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

# Work Package Prompt: WP02 – Document the already-in-force note and the new JSON field

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`). Address all of it before claiming completion.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Make the operator-facing documentation and the changelog match WP01's behaviour:

1. `docs/api/charter-commands.md` — the no-cascade section explains the note and when the
   warning still applies; the change-report table documents
   `referenced_already_in_force`; the worked example that shows the three referenced
   artifacts in `referenced_not_cascaded` is corrected (its fixture leaves the
   `procedure`/`styleguide`/`tactic` artifacts in force, so they belong in the new key).
2. `docs/changelog/CHANGELOG.md` — one `[Unreleased]` entry: bold impact-first lead with
   `(#6742)`, before/after, under 1,200 characters.
3. `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`.

## Context & Constraints

- The live contract is `docs/api/charter-commands.md`. The
  `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/contracts/cli-json.md` file is a
  closed mission's historical artifact — **do not edit it**.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file under
  `docs/changelog/`.
- Copy the note text from WP01's implementation exactly; do not paraphrase the punctuation.
- Keep the documentation writing in the repository's style: short declarative sentences,
  no marketing voice, tables for field contracts.

## Branch Strategy

- **Strategy**: single branch — `issue-6742-no-cascade-already-in-force`
- **Planning base branch**: `issue-6742-no-cascade-already-in-force`
- **Merge target branch**: `issue-6742-no-cascade-already-in-force`

## Subtasks & Detailed Guidance

### Subtask T007 – Update the `charter activate` CLI reference

- **Purpose**: a reader of the reference must be able to predict the output.
- **Steps**:
  1. In the "Without `--cascade`" prose (`docs/api/charter-commands.md`, around the
     `Warning: referenced kind/id is deactivated and was not activated.` paragraph), add the
     note form:
     `Note: referenced kind/id is already in force (<reason>); not added by this command.`
     with `<reason>` being `no explicit list` or `listed in activated_<plural>`, and state
     the two rules: the warning stays for a kind with an explicit list that omits the
     artifact, and for a deactivated artifact; the `--cascade` hint only appears when
     something is still not in force.
  2. In the change-report table, add a row for
     `referenced_already_in_force` | `[ArtifactRef]` | Without `--cascade`: the referenced
     artifacts the project's activation state already admits, which the `Note: … is already
     in force` lines name; `[]` with `--cascade`.
  3. Amend the existing `referenced_not_cascaded` row's meaning: skipped **and** deactivated
     references that are not in force (the `Warning: referenced …` lines).
  4. Amend the prose paragraph under the table ("`referenced_not_cascaded` lists the
     artifacts that were skipped and those that are deactivated") so it names the new key
     and states that an artifact appears in at most one of the two lists.
  5. Fix the worked example `charter activate directive p-dir --no-compile --json`: its
     project has no `activated_procedures` / `activated_styleguides` / `activated_tactics`
     keys (check `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`,
     which the example mirrors), so those three artifacts move to
     `referenced_already_in_force` and `referenced_not_cascaded` becomes `[]`. Regenerate
     the shown payload rather than hand-editing it — run the command against the same
     fixture and paste the real output.
- **Files**: `docs/api/charter-commands.md`
- **Notes**: keep the surrounding examples' formatting (`json` fences, two-space indent).

### Subtask T008 – Add the `[Unreleased]` changelog entry

- **Purpose**: user-facing change, so it needs an entry.
- **Steps**:
  1. Under `## [Unreleased]` in `docs/changelog/CHANGELOG.md`, add a bullet:
     bold impact-first lead, then **Before**/**After** in the established style, then the
     `(#6742)` reference.
  2. Content: an artifact that is already in force is no longer reported as "was not
     activated"; the note names it as in force with the reason; the warning and the
     `--cascade` hint stay for artifacts that really are not in force; `--json` gains
     `referenced_already_in_force`.
  3. Keep it under 1,200 characters and match the neighbouring entries' shape.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: `tests/`-level changelog guards may check the entry's shape
  (`(#NNNN)` present, length). Run them if they exist locally.

### Subtask T009 – Run the docs freshness check

- **Purpose**: docs gates are part of CI.
- **Steps**:
  1. `uv run python -m scripts.docs.check_docs_freshness --ci` — expect `errors=0`.
  2. If T007/T008 added no new page and no ADR, `docs_index --write` and
     `freshen_adr_inventory` are not needed; run them only if the check says so.
  3. `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` if the change
     introduces new terminology (it should not).
- **Files**: n/a (verification)

## Test Strategy

- `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`).
- Markdown lint runs in CI; keep tables well-formed and lines under the configured width.

## Risks & Mitigations

- **Example drift**: hand-edited JSON examples rot. Regenerate the payload from the real
  fixture and paste it.
- **Changelog length**: the guard rejects over-long entries; count characters.
- **Duplicate contract**: do not restate the JSON schema in two documents; point at the
  change-report table.

## Review Guidance

- The note text in the docs matches the implementation byte for byte.
- Both `referenced_*` list semantics are unambiguous, and the "at most one list"
  invariant is stated.
- The changelog lead is impact-first and carries `(#6742)`.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in
this file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
