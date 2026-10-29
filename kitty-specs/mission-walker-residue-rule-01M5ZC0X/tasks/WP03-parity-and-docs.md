---
work_package_id: WP03
title: Parity test, changelog and docs
dependencies:
- WP01
- WP02
requirement_refs:
- FR-007
- FR-009
planning_base_branch: issue-5875-mission-walker-is-mission-dir
merge_target_branch: issue-5875-mission-walker-is-mission-dir
branch_strategy: Planning artifacts for this mission were generated on issue-5875-mission-walker-is-mission-dir. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5875-mission-walker-is-mission-dir unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Parity and docs
history:
- at: '2026-10-27T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/context/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/context/test_is_mission_dir.py
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
- docs/migrations/mission-id-canonical-identity.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Parity test, changelog and docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- FR-007: one parity case in `tests/context/test_is_mission_dir.py` proves that on one git-repo fixture, the set listed by `list_missions_for_selection` = the agent `_list_feature_spec_candidates` slugs = `doctor identity` non-residue slugs = `audit_mission_types` slugs. The fixture holds a committed Mission, an uncommitted Mission with an id, a tracked id-less legacy `meta.json`, an untracked id-less `meta.json`, spec.md-only folders (tracked and untracked) and a lock-only folder. It also asserts the expected set explicitly, so that a parity that is "equal but wrong" fails.
- FR-009: a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry, following that file's existing style. It is a behaviour change: `kitty-specs/` folders with only a `spec.md` (or an untracked `meta.json` without a `mission_id`) are no longer listed or auto-selected as Missions. `doctor identity` reports them in a new `residue` state with a remedy, and `doctor mission-type` no longer reports them as `typeless`. Refs #5875.
- Docs: `docs/api/cli-commands.md` (`doctor identity` states, `--fail-on`) and `docs/migrations/mission-id-canonical-identity.md` (if it lists the states) mention `residue` and its remedy.

## Context & Constraints

- Read `../spec.md`, `../data-model.md` (the parity table), `../contracts/doctor-identity-residue.md`.
- Use the `repo` fixture style that already exists in `tests/context/test_is_mission_dir.py`.
- Terminology: "Mission". Prose style: short, plain sentences, matching the changelog's neighbouring entries.

## Branch Strategy

Planning branch `issue-5875-mission-walker-is-mission-dir`, final merge target the same branch. The topology is `single_branch`: work in the repository root checkout. Commit on that branch. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.

## Subtasks & Detailed Guidance

### Subtask T011 – Parity case
As above. Prove it red-first: temporarily revert one walker (for example `git stash` the WP01 change in a scratch copy, or monkeypatch the predicate to the old rule) and check that the test fails. Record how in the Activity Log. Do not commit the revert.

### Subtask T012 – Changelog
Add the `[Unreleased]` entry under the right subsection (Changed or Fixed, following the file's conventions).

### Subtask T013 – Docs
Update the state lists. Then run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` and any docs gate that covers these files (`grep -rl "cli-commands.md" tests/`).

## Test Strategy

`uv run --frozen pytest tests/context -q` and the docs gates found in T013. Record counts.

## Review Guidance

Reviewer: confirm the parity test asserts the explicit expected set and fails under the old rule, and that the changelog wording is accurate.

## Activity Log

- 2026-10-27T19:20:00Z – system – Prompt created.
- 2026-10-27T21:00:00Z – claude (python-pedro, implementer) – T011: added `test_walkers_agree_on_the_mission_set` (git fixture: committed Mission, uncommitted Mission with id, tracked id-less legacy meta.json, untracked id-less meta.json, tracked and untracked spec.md-only, lock-only, a README.md) and `test_walkers_agree_on_a_non_git_root` to `tests/context/test_is_mission_dir.py`. Each asserts selection == agent candidates == `audit_repo(..., residue_aware=True)` non-residue == `audit_mission_types` == an explicit expected set; the git case also pins the residue set. Red-first: a throwaway test (not committed) monkeypatched `mission_resolver.is_selectable_mission_dir` to the old "spec.md or meta.json exists" rule; the parity case failed (selection gained the spec.md-only and untracked id-less folders). Commit 5ec9d481.
- 2026-10-27T21:00:00Z – claude (python-pedro, implementer) – T012/T013: changelog `[Unreleased]` Changed entry (passes `check_changelog_style`, under 900 chars); `docs/api/cli-commands.md` `doctor identity` block refreshed from live help (no HELP-DRIFT); `residue` added to the state list in `docs/migrations/mission-id-canonical-identity.md`. Note: that guide's state list and JSON examples (`ok`/`conflict`, `status`/`total`) predate the current `doctor identity` output; left as is (out of scope). Commit d24bf314.
- Tests: `pytest tests/context` 99 passed; `test_no_legacy_terminology.py` + `test_docs_cli_reference_parity.py` + `tests/docs/test_changelog_style.py` 255 passed; ruff, `ruff format --check --force-exclude`, mypy clean on the test file.
