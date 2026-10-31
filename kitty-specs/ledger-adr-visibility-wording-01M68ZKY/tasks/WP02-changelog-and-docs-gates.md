---
work_package_id: WP02
title: Changelog and docs gates
dependencies:
- WP01
requirement_refs:
- NFR-001
- NFR-002
- SC-003
planning_base_branch: issue-6362-adr-visibility-wording
merge_target_branch: issue-6362-adr-visibility-wording
branch_strategy: Planning artifacts for this mission were generated on issue-6362-adr-visibility-wording. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6362-adr-visibility-wording unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
phase: Phase 2 - Documentation
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Changelog and docs gates

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting.

---

## Objectives & Success Criteria

Record the documentation change under `[Unreleased]` and prove the docs gates for the edited page
are green.

Done when:

- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry: bold impact-first lead with
  `(#6362)`, then before/after, under 1,200 characters, matching the surrounding entries' style.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`.
- The ADR spelling/structural checks covering `docs/adr/**` pass with no new allowlist entries.
- The results (counts, errors=0) are recorded in the WP history note.

## Context & Constraints

- The reconciled ADR is WP01's deliverable; read the final §5 and #E before writing the entry.
- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md` — edit the file, never replace
  the symlink.
- Do not rebuild the whole CLI reference (shared machine state on this host); verify with the
  freshness check instead.
- Any pre-existing red (for example the known main reds #6801, #6816, #5927, #6798) is cited in the
  PR's `## Deferred`, never worked around.

## Branch Strategy

- **Strategy**: single-branch mission; planning base and merge target are the same branch.
- **Planning base branch**: `issue-6362-adr-visibility-wording`
- **Merge target branch**: `issue-6362-adr-visibility-wording`

> Populated by `finalize-tasks`.

## Subtasks & Detailed Guidance

### T007 – Changelog entry

- **Purpose**: A decision-record correction must be discoverable for anyone who read the old ADR.
- **Steps**: Add a bullet at the top of `[Unreleased]`. Lead with the impact in bold, e.g.
  **"The accepted migration-ledger ADR now names the read surface that shipped" (#6362)**; then
  *Before:* §5 and the #E deliverable named a `doctor migrations` sub-surface and an
  `upgrade --list-applied` flag that were never built; *After:* both name
  `spec-kitty migrate ledger [--json]` and its single pending source, with the old proposal kept as
  marked history. Stay under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes, with T008.
- **Notes**: Follow the existing bullet shape — bold lead, `(#issue)`, then before/after prose.

### T008 – Docs gates

- **Steps**:
  ```bash
  uv run python -m scripts.docs.check_docs_freshness --ci
  uv run python -m scripts.docs.check_spelling --pass all
  uv run pytest tests/docs/test_docs_structural_lint.py tests/docs/test_changelog_style.py -q
  ```
  Record every result in the WP history note.
- **Files**: n/a
- **Parallel?**: No.
- **Notes**: If a reported error is unrelated and pre-exists on `origin/main`, name the existing
  issue and cite it in the PR's `## Deferred`; do not disable or relax the gate.

## Test Strategy

Documentation-only WP: the checks are the docs freshness gate, spelling for the edited page, and
the changelog-style test. No new code tests.

## Risks & Mitigations

- Over-long changelog entry → keep it under 1,200 characters and impact-first.
- Stale index after WP01 → the freshness gate names `DOCS-INDEX-DRIFT`; fix by re-running
  `uv run python -m scripts.docs.docs_index --write` (owned by WP01) rather than hand-editing YAML.

## Review Guidance

- The entry leads with what changed for a reader of the ADR, not with process.
- The commands named in the changelog exist (`spec-kitty migrate ledger`, `--json`).
- No claim exceeds what WP01 changed.

## Progress & Status

- First: `spec-kitty agent action implement WP02 --agent <name> --mission ledger-adr-visibility-wording-01M68ZKY`
- Record progress with `spec-kitty agent tasks add-history WP02 --note "…"`.
