---
work_package_id: WP02
title: Seed init scenarios + corpus layout
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- SC-002
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: 8cfbe6d27efb28d5ba3ac42725691a549bfa4567
created_at: '2026-10-11T18:26:55.004895+00:00'
subtasks:
- T004
- T005
- T006
- T007
phase: Phase 2 - Scenarios
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: analyst-annie
authoritative_surface: tests/scenarios/
create_intent:
- tests/scenarios/init/init.feature
execution_mode: code_change
model: ''
owned_files:
- tests/scenarios/**
role: analyst
tags: []
task_type: specify
tracker_refs: []
---

# Work Package Prompt: WP02 – Seed init scenarios + corpus layout

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `analyst-annie`
- **Role**: `analyst`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Create the `tests/scenarios/<area>/` corpus layout and author the **two bound, untagged** seed
`init` scenarios, drawn verbatim from the promises in `src/specify_cli/cli/commands/init_help.py`.

Done when:
- `tests/scenarios/init/init.feature` exists with two valid Gherkin scenarios.
- Each scenario pins existing `init` behaviour (a **ratchet**) AND carries a **same-fixture positive control**, so a no-op change cannot pass it.
- Both scenarios are untagged (so they run in the gating nightly); no `@wip`/`@manual`.
- The step phrasing is one a `CliProcessDriver`-backed step layer (WP04) can bind.

## Context & Constraints

- **Source of truth for the promises** — `src/specify_cli/cli/commands/init_help.py` (`INIT_COMMAND_DOC`):
  - Idempotent restore: *"Re-running init in an already-initialized directory is idempotent for project state: it verifies the configured agents' skill surfaces, additively restoring missing per-agent skill roots (e.g. .claude/skills/) through the canonical installer…"*
  - No git: *"Creates project files only. Does not initialize a git repository. Does not create any commits."* + *"init never touches git state regardless of flags."*
- **Black-box**: scenarios describe CLI behaviour observable from outside — files on disk, exit codes, `--json` output, git state. Never reference Python internals.
- These `.feature` files MUST be git-tracked before/with WP07 (the ci-router `scenarios` glob asserts a live path).
- Spec refs: FR-002, FR-003, FR-004, SC-002. Non-vacuity tactic: `acceptance-criteria-non-vacuity`.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T004 – Create the `tests/scenarios/init/` area

- **Purpose**: Establish the conventional corpus layout `tests/scenarios/<area>/`.
- **Steps**: Create `tests/scenarios/init/`. Keep the layout minimal — a single `init.feature` for now. Do not add a promise-index or any tag-validation machinery (out of core scope).
- **Files**: `tests/scenarios/init/` (+ `init.feature` in T005/T006).

### Subtask T005 – Scenario: re-running init keeps project state, restores only missing skill roots

- **Purpose**: Ratchet the idempotent-restore promise (FR-003).
- **Steps**: Author a `Scenario` whose shape is:
  - **Given** an already-initialized project (an `init` has been run for some agents),
  - **And** one per-agent skill root (e.g. `.claude/skills/`) has been deleted while another is left in place, and some other project state marker exists,
  - **When** `spec-kitty init` is re-run,
  - **Then** the deleted skill root is restored (positive control — the probe observably sees restoration),
  - **And** the already-present skill root and the other project-state marker are byte-identical (the "keeps project state" assertion),
  - so a no-op `init` that restored nothing would FAIL the restore assertion.
- **Notes**: bound + untagged. Use `--non-interactive --ai <agents>` for determinism (the harness in WP04 supplies the env).

### Subtask T006 – Scenario: init never runs git init or commits

- **Purpose**: Ratchet the no-git promise (FR-004).
- **Steps**: Author a `Scenario`:
  - **Given** a working directory (the harness provides a temp git repo; use a sub-path that is NOT itself a repo for the "no new `.git`" check),
  - **When** `spec-kitty init` runs,
  - **Then** project files ARE created (`.kittify/` and agent surfaces exist — positive control proving `init` observably did work),
  - **And** the surrounding repository's HEAD and commit count are unchanged, and no new `.git` directory was created by `init`,
  - so a no-op `init` would fail the "files created" control and a git-touching `init` would fail the unchanged-HEAD assertion.
- **Notes**: bound + untagged.

### Subtask T007 – [P] Align the Gherkin step vocabulary

- **Purpose**: Make the steps bindable by WP04 without rework.
- **Steps**: Use a small, consistent step vocabulary (e.g. `Given an initialized project for agents "<agents>"`, `When I run "spec-kitty <args>"`, `Then the directory "<path>" exists`, `Then the repository has no new commits`). Keep step text declarative and reusable across both scenarios.
- **Notes**: WP04 depends on this WP and will bind exactly these steps — keep them stable and minimal.

## Risks & Mitigations

- **Vacuous ratchet**: every unchanged/absent assertion is paired with a positive control on the same fixture (deleted-root-restored; files-created). A reviewer must be able to see that a no-op would fail.
- **Over-specified output**: assert on structural facts (file exists, HEAD unchanged, `--json` field present), not exact human-text, so the scenario is stable cross-OS.

## Review Guidance

- Confirm both scenarios are valid Gherkin, untagged, faithful to `init_help.py`, and each has a same-fixture positive control that a no-op change would fail.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP02 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP02 --to <status>`

## Activity Log

- 2026-10-11T18:43:08Z – implement-command – shell_pid=3041821 – T004-T007: created tests/scenarios/init/init.feature with two bound, untagged ratchet scenarios drawn verbatim from init_help.py promises; each has a same-fixture positive control (deleted .claude/skills restored while .agents/skills+.kittify/config.yaml stay byte-identical; app/.kittify+app/.claude created while surrounding HEAD/commit-count unchanged and no app/.git). Grounded all paths/exit codes against real 4.0.0rc7 init in an isolated scratch env. Declarative, black-box, WP04-bindable step vocabulary.
