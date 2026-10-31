---
work_package_id: WP02
title: Changelog entry for the contract-version single source
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T005
phase: Phase 2 - Record
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
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

# Work Package Prompt: WP02 – Changelog entry for the contract-version single source

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or
any user-defined profile), and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `scribe-sally` (documentarian)
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Record the #6578 change in `docs/changelog/CHANGELOG.md` under `[Unreleased]`, in the repository's
enforced style, so a maintainer can see that the orchestrator-api contract version now has one source
of truth in the test suite and that a reintroduced literal fails a fast gate.

Done when:

1. The entry sits under `[Unreleased]`, under the category heading the neighbouring test/CI entries
   use (not a new heading).
2. It leads with a bold, impact-first sentence and carries `(#6578, CI)`.
3. It has **Before:** and **After:**, stays under 1,200 characters, and describes the code that
   actually landed — including the guard test's filename and the fact that no product behaviour
   changed.
4. The changelog style gate passes.

## Context & Constraints

- Spec: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/spec.md`
- Plan: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/plan.md`
- WP01 is the change being recorded: two test modules, no production code.
- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the target.
- Style: `docs/development/how-to/review-gates.md#changelog-update-and-style`. Peer examples of the
  test/CI shape: the neighbouring "QL gate" / "network" entries in the same section — one sentence of impact,
  **Before:**, **After:**, **What to do:**.

## Branch Strategy

- **Strategy**: single_branch mission (`meta.json` `topology: single_branch`, `target_branch: main`).
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T005 – The `[Unreleased]` entry

- **Purpose**: The change is maintainer-facing (a new gate and a removed duplicate pin), and this
  repository records test/CI-only changes in the changelog (see the neighbouring entries in that section).
- **Steps**:
  1. Read WP01's final diff (`git show --stat` on the WP01 commit, or `git diff` before WP02 starts)
     so the entry describes the landed code, not this plan.
  2. Add the entry under `[Unreleased]`, in the category heading the neighbouring CI/test entries
     use.
  3. Wording shape (adapt to the real diff; do not copy verbatim):
     ```markdown
     - **The orchestrator-api contract version has one source of truth in the test suite** (#6578, CI). **Before:** `tests/orchestrator_api/test_origin_freshness_envelopes.py` compared the emitted envelope to a hand-written `_CONTRACT_VERSION` literal, re-pinned eleven times (1.11.0 → 1.21.0), and #6578 was filed when it had been left one bump stale. **After:** the two refusal tests read the exported `envelope.CONTRACT_VERSION`, and a fast test in `tests/specify_cli/orchestrator_api/test_contract_version.py` fails — naming `path:line` — when any other test module spells a contract version. No product behaviour changes. **What to do:** nothing.
     ```
  4. Verify the style gate and length:
     ```bash
     uv run --frozen python -m pytest tests/docs/test_changelog_style.py -q   # if that is the gate's path
     ```
     Locate the actual gate first with `grep -rl "Unreleased" tests/docs tests/architectural 2>/dev/null`
     and run whichever test enforces the changelog style; do not invent a path.
  5. Keep the entry under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: No.
- **Notes**: Do not add a docs page: no page describes this pin. Say so in the PR body so the
  reviewer does not look for one.

## Test Strategy

- Run the repository's changelog style gate (locate it as in T005 step 4) — it must pass.
- `markdownlint` is enforced on this file in CI; keep line shape consistent with neighbours
  (single-line bullet, no trailing spaces).

## Risks & Mitigations

- **Wrong category heading** — copy the heading of the entry directly above; the style guard refuses
  unknown headings.
- **Describing an intention** — write from the merged diff.
- **Overclaiming** — no product behaviour changes in this mission; say that explicitly.

## Review Guidance

Reviewers check: the heading matches its neighbours; the entry carries `(#6578, CI)`; **Before:** and
**After:** are both present; the guard test's file name is right; the entry is under 1,200
characters; the style gate passes; no other file changed.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`) — never in this
prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
