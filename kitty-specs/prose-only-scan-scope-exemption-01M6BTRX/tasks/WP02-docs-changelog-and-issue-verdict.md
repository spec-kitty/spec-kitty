---
work_package_id: WP02
title: Document the exemption and resolve the issue verdict
dependencies:
- WP01
requirement_refs:
- FR-005
- C-003
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 2 - Living documentation
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/6999.changed.md
- kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/issue-matrix.json
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/unreleased/6999.changed.md
- docs/development/reference/ci-gate-mechanics.md
- kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/issue-matrix.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Document the exemption and resolve the issue verdict

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the
frontmatter (`scribe-sally`), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: implementer
- **Agent/tool**: claude

## Objectives & Success Criteria

- The changelog carries an `[Unreleased]`-destined fragment for the change
  (FR-005, SC-003).
- The CI reference describes the shipped heavy-leg selection and the prose-only
  interaction accurately, including the declared-scope limit (C-003).
- The mission's issue matrix records `#6999` as `fixed` with the WP01 evidence.

## Context & Constraints

- Read the shipped diff of WP01 first; describe what shipped, not the plan.
- Repository conventions:
  - Changelog fragments live in `docs/changelog/unreleased/<id>.<section>.md`
    (see that directory's `README.md`). `docs/changelog/CHANGELOG.md` is the
    assembled file; the root `CHANGELOG.md` is a symlink to it. Do **not** edit
    either by hand.
  - Style: a bold, impact-first lead with `(#6999)`, then before/after, under
    1,200 characters, US spelling.
  - `docs/development/reference/ci-gate-mechanics.md` is the canonical
    gate-mechanics reference; its heavy-leg table has a "When" column and the
    skip-if-green section names `prose-scan`.
- Wording must stay tied to stable names (`scan_scopes`, `prose-scan`'s
  `prose_only`, `arch_scan_scope`, `battery_scope`), not to a gate list that
  will age. State that only declared scopes are exempt (#7000 owns completeness).

## Branch Strategy

- **Strategy**: single-branch mission; this WP commits to the mission branch.
- **Planning base branch**: `kitty/mission-prose-only-scan-scope-exemption-01M6BTRX`
- **Merge target branch**: `main` (via the PR; never push `main`)

## Subtasks & Detailed Guidance

### Subtask T001 – Changelog fragment

- **Purpose**: Record the user-visible behaviour change where the release
  assembles it.
- **Steps**: Create `docs/changelog/unreleased/6999.changed.md` with one entry:
  a bold lead naming that a prose-only PR now runs the architectural gates whose
  declared scan scope it touches, then **Before:** the whole battery was
  dropped, **After:** it runs those gates only, through the scoped leg. Cite
  `(#6999)`.
- **Files**: `docs/changelog/unreleased/6999.changed.md` (new).
- **Notes**: One line, no heading. Under 1,200 characters.

### Subtask T002 – CI reference update

- **Purpose**: The reference must not describe the old subtraction.
- **Steps**: In `docs/development/reference/ci-gate-mechanics.md`:
  - The heavy-leg table row for legs 1/2 and 2/2 gains the prose exemption in
    its "When" cell: a prose-only diff that touches a declared scan scope runs
    the gates whose scope it touches (`arch_scan_scope` + `prose_only`).
  - Add a short paragraph (near the scoped-leg description or the skip-if-green
    prose note) explaining: a proven prose-only PR still skips the module matrix
    and code shards; the heavy battery now runs only the declared scan-scope
    matches; a prose-only diff that declares nothing still skips it; declared
    scopes only.
- **Files**: `docs/development/reference/ci-gate-mechanics.md`.
- **Notes**: Do not add a new page or ADR, so no docs-index regeneration is
  needed; still run the freshness check.

### Subtask T003 – Issue verdict

- **Purpose**: The mission's issue matrix must resolve the issue it fixes.
- **Steps**: After WP01 is done and its evidence exists:
  ```bash
  spec-kitty agent issue-verdict --mission prose-only-scan-scope-exemption-01M6BTRX \
    --issue "#6999" --verdict fixed --actor claude --wp WP01 \
    --evidence-ref "WP01: prose-only declared scan-scope exemption in the battery if: and select_battery_gates, pinned in tests/ci/test_battery_scope.py, test_ci_module_wiring.py, test_ci_config_battery_routing.py"
  ```
  Also mark the context-only references (`#4842`, `#6994`, `#6996`, `#7000`) as
  `not-applicable` if the matrix lists them.
- **Files**: `kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/issue-matrix.json`.
- **Notes**: Use the CLI, not a hand edit.

## Test Strategy

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
```

Plus a read-back of the rendered table row and the new paragraph.

## Risks & Mitigations

- **Stale docs**: tie the wording to the shipped code names and re-read WP01's
  diff before writing.
- **Fragment name collision**: `6999.changed.md` is keyed by issue number; if a
  future PR number replaces it, the landing pass renames it.

## Review Guidance

- The fragment's lead is impact-first and cites `(#6999)`.
- The reference no longer implies the whole battery is always subtracted for a
  prose-only PR, and still states the #4842 down-route for non-matching prose.
- `check_docs_freshness --ci` reports errors=0.

## Progress & Status

- Record subtask completion with
  `spec-kitty agent tasks mark-status T001 ... --status done`.
