---
work_package_id: WP05
title: Docs / CHANGELOG / ADR citation
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- SC-001
- SC-003
planning_base_branch: feat/builtin-revendor-pin-gate
merge_target_branch: feat/builtin-revendor-pin-gate
branch_strategy: Planning artifacts for this mission were generated on feat/builtin-revendor-pin-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/builtin-revendor-pin-gate unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
phase: Phase 2 - Documentation
history:
- at: '2026-10-17T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: sonnet
owned_files:
- docs/changelog/CHANGELOG.md
- kitty-specs/builtin-revendor-pin-gate-01M55MX7/trace/narrative.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3504'
---

# Work Package Prompt: WP05 – Docs / CHANGELOG / ADR citation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `comms-cleo`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Document what the mission shipped and close the mission narrative:

- One `[Unreleased]` CHANGELOG entry in `docs/changelog/CHANGELOG.md`: impact-first (what changed for
  a maintainer/contributor and why it matters), carrying `(#3504)`, under **1200 characters**, US
  spelling, citing ADR `2026-08-16-2`.
- Append a closing section to the mission narrative tracer.
- **No ADR amendment** — this mission implements the already-settled 2026-10-11 amendment; cite, do
  not amend (research D6).

This is a `planning_artifact` WP: every owned file is under `docs/` or `kitty-specs/`.

Success = traceability for SC-001..SC-004 in [spec.md](../spec.md).

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-05. **Research**: [research.md](../research.md) D6. **Charter**: `.kittify/charter/charter.md`.
- **Runs last** — it documents WP01..WP04, so write it after they are in the write checkout and you
  can describe the shipped behaviour accurately (code is the source of truth; the entry mirrors
  shipped behaviour — `publication-authority`, `docs-freshness-sla`).
- **CHANGELOG placement**: the `[Unreleased] - 4.0.0rc8` section already exists with a `### Fixed`
  subsection. Add an entry under the appropriate subsection — `### Added` for the new pin/vendor/gate
  capability (a new maintainer-facing guard), created if absent, ordered per Keep a Changelog. Match
  the house style of the existing bolded-lead entries (one bold lead clause, then the substance).
- **Length + spelling gates (hard)**: keep the entry under 1200 characters. Use US spelling —
  run `python -m scripts.docs.check_spelling` (or the repo's `scripts.docs.check_spelling` entry) over
  the changed CHANGELOG before finishing; it flags UK spellings on any changelog-touching change
  (memory: "codespell docs-lint flags changelog UK spellings"). Fold the one-char fixes.
- **Terminology canon**: Mission/Missions, not Feature; canonical `status commit` vocabulary only.
- **Do NOT** touch any `src/`, `.github/`, `tests/`, `pyproject.toml`, or ADR file. Owned files are
  exactly the two listed.

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout; no lane worktree)
- **Planning base branch**: feat/builtin-revendor-pin-gate
- **Merge target branch**: feat/builtin-revendor-pin-gate (PR → main)

## Subtasks & Detailed Guidance

### Subtask T013 – `[Unreleased]` CHANGELOG entry

- **Purpose**: traceability (SC-001, SC-003, SC-004).
- **Steps**:
  1. Add one impact-first entry under `[Unreleased] - 4.0.0rc8`. Cover, concisely: the committed pin
     lockfile (`packs/built-in.source.yaml` — open-packs SHA + clean-tree digest + `requires_core`);
     the new `spec-kitty charter pack vendor [--check]` command (the sanctioned way to bump the pinned
     `packs/built-in/` tree, with fail-closed verify); the per-PR drift gate that reds a PR whose
     `packs/built-in/` diverges from the pin, naming the `vendor` remedy; and release re-verification.
     Lead with the contributor-facing impact: hand-editing `packs/built-in/` now fails CI; bump the
     pin via `vendor`. Carry `(#3504)` and cite ADR `2026-08-16-2`.
  2. Keep it under 1200 characters.
  3. Run the spelling check on the changed file and fold fixes.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: No.

### Subtask T014 – Append the closing narrative

- **Purpose**: mission tracer close (Standing Order #3).
- **Steps**:
  1. Append a short closing section to
     `kitty-specs/builtin-revendor-pin-gate-01M55MX7/trace/narrative.md` recording what landed across
     WP01..WP04 (pin model + seed, vendor command, drift gate, release re-verify), any friction worth
     carrying forward, and the final state. Keep it factual and brief; do not rewrite earlier entries.
- **Files**: `kitty-specs/builtin-revendor-pin-gate-01M55MX7/trace/narrative.md`
- **Parallel?**: No.
- **Notes**: Commit the narrative append immediately — mission commands can rewrite the primary
  mission dir from coord and silently drop uncommitted tracer edits (memory: "Mission commands revert
  uncommitted tracer edits").

## Test Strategy

- No code tests. Verification: `scripts.docs.check_spelling` passes on the changed CHANGELOG; the
  entry is <1200 chars, carries `(#3504)`, cites ADR `2026-08-16-2`, and uses canonical terminology.
  If a docs-freshness/strict docs gate exists for the changelog, run it and record the result.

## Risks & Mitigations

- **UK-spelling docs-lint red**: run `check_spelling` and fold the one-char fixes before finishing.
- **Over-length entry**: trim to <1200 chars; the detail lives in the spec/ADR, not the changelog.
- **Accidental ADR amendment**: cite `2026-08-16-2`; do not edit any ADR.
- **Lost tracer append**: commit it immediately after writing.

## Review Guidance

- Confirm the entry is impact-first, <1200 chars, US spelling, `(#3504)`, cites ADR `2026-08-16-2`.
- Confirm no file outside `docs/changelog/CHANGELOG.md` and the narrative tracer changed.
- Confirm no ADR was amended.

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP05 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP05 --to <status>`
- View: `spec-kitty agent tasks status`
