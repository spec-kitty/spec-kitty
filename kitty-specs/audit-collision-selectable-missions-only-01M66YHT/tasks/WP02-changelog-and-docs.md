---
work_package_id: WP02
title: Changelog and doc wording for the selectable-Missions collision rule
dependencies:
- WP01
requirement_refs:
- C-003
- SC-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
  - "T009"
  - "T010"
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
role: communicator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Changelog and doc wording

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in
the frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `comms-cleo`
- **Role**: `communicator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*None yet.*

---

## Objectives & Success Criteria

Tell a user, in their words, what changes for them: their audit stops reporting a
prefix collision (and selector ambiguity) between a healthy Mission and a
`kitty-specs/` leftover folder that no command can select — and real collisions
between two Missions are unchanged. Correct any doc whose wording claims residue
folders participate in those reports.

Deliver C-003, FR-005; support FR-001.

## Context & Constraints

- House style: look at the #5875 entry in `docs/changelog/CHANGELOG.md` under
  `[Unreleased]` — bold impact-first lead, `(#NNNN)`, then before/after in one
  flow, well under 1,200 characters.
- `CHANGELOG.md` at the repository root is a **symlink** to
  `docs/changelog/CHANGELOG.md`; edit the real file.
- Do **not** touch `packs/` (generated), `.claude/` or any agent copy.
- The `IDENTITY_MISSING` `backfill-identity` remedy on a `meta.json`-less folder
  is **out of scope**: #6757 asks only that the finding be kept. Do not change
  the remedy text; it is named in the PR's `## Deferred` section instead.
- No ADR: no architectural boundary moves and the read-side rule is unchanged.

## Branch Strategy

- **Strategy**: single-branch mission on `kitty/mission-audit-collision-selectable-missions-only-01M66YHT`; merge target `main` (the operator merges).
- **Planning base branch**: `kitty/mission-audit-collision-selectable-missions-only-01M66YHT`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T009 – Changelog `[Unreleased]` entry (#6757)

- **Purpose**: The user-facing record of the behaviour change.
- **Steps**:
  1. Open `docs/changelog/CHANGELOG.md`, find the `[Unreleased]` section's fix
     list, and add one bullet in the house style:
     `- **A leftover <code>kitty-specs/</code> folder no longer fakes a prefix collision on a healthy Mission** (#6757). **Before:** … **After:** …`
  2. Cover, in before/after form: (a) the audit reported `DUPLICATE_PREFIX` /
     `AMBIGUOUS_SELECTOR` on a real Mission when a folder holding only `spec.md`
     shared its numeric prefix; (b) now the two collision reports are judged on
     the Missions Mission selection can reach, so that folder cannot fake or
     silence a collision, while two real Missions sharing a prefix (and a
     pre-identity Mission with a tracked `meta.json`) are still reported; (c) the
     folder still gets `IDENTITY_MISSING`, so `doctor mission-state --audit
     --fail-on error` still exits 1 until it is resolved or removed.
  3. Keep it under 1,200 characters and end with the actionable "what to do".
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: Reference the issue as `(#6757)` exactly once, in the bold lead.

### Subtask T010 – Correct the audit collision-rule doc wording

- **Purpose**: Keep the published CLI reference honest.
- **Steps**:
  1. Read `docs/api/cli-commands.md` around the `spec-kitty doctor identity` and
     `spec-kitty doctor mission-state` sections.
  2. If any wording claims the audit's `DUPLICATE_PREFIX` / `AMBIGUOUS_SELECTOR`
     reports include non-Mission (residue) folders, correct it to say the
     collision reports are judged on selectable Missions only, while
     `IDENTITY_MISSING` still covers folders the engine counts as Missions.
  3. If the wording already matches, change nothing and record that decision in
     the WP history so the PR can say the docs were checked.
- **Files**: `docs/api/cli-commands.md`
- **Notes**: Do not regenerate any index unless you add a new doc page (this WP
  should not); if you do add one, run
  `uv run python -m scripts.docs.docs_index --write` and
  `uv run python -m scripts.docs.check_docs_freshness --ci`.

## Test Strategy

- Documentation only. Verify the symlink is intact
  (`ls -l CHANGELOG.md` → points at `docs/changelog/CHANGELOG.md`).
- If `docs/api/cli-commands.md` changes materially, run
  `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Entry overclaims that collisions are no longer reported | Say explicitly that real collisions are unchanged |
| Editing the symlink target by accident | Edit `docs/changelog/CHANGELOG.md` only |

## Review Guidance

- Confirm the entry is impact-first, names `(#6757)`, is under 1,200 characters,
  and would let a user decide what to do.
- Confirm no doc claims residue folders participate in collisions.
- Confirm no scope creep into the `backfill-identity` remedy.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
