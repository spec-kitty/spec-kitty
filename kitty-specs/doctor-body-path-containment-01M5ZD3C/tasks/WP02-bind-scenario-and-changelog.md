---
work_package_id: WP02
title: Bind PR-CHARTER-SHARING-004 and record the fix
dependencies:
- WP01
requirement_refs:
- FR-006
- SC-003
planning_base_branch: issue-6418-doctor-body-path-containment
merge_target_branch: issue-6418-doctor-body-path-containment
branch_strategy: Planning artifacts for this mission were generated on issue-6418-doctor-body-path-containment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6418-doctor-body-path-containment unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-body-path-containment-01M5ZD3C
base_commit: 8a68f3171c001a382b724351074efa18c06dcc7b
created_at: '2026-10-27T20:28:50.488805+00:00'
subtasks:
- T007
- T008
- T009
history:
- at: '2026-10-27T19:40:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/scenarios/charter/
create_intent: []
execution_mode: code_change
owned_files:
- tests/scenarios/charter/share-governance-safely/share-governance-safely.feature
- tests/scenarios/charter/PROMISES.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Bind PR-CHARTER-SHARING-004 and record the fix

## ⚡ Do This First: Load Agent Profile

Load **`python-pedro`** (implementer) with the `/spk-charter-profile-load` skill before reading anything else. The review runs under `reviewer-renata`.

## Objective

Make the consumer promise PR-CHARTER-SHARING-004 ("A shared asset that reaches outside its pack is not accepted as sound") gate again, now that WP01 makes `doctor charter-packs` exit non-zero on it, and record the fix in the changelog. Spec: FR-006, SC-003.

## Branch Strategy

Planning base and merge target: `issue-6418-doctor-body-path-containment`. Worktree per the lane in `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission doctor-body-path-containment-01M5ZD3C
```

## Subtasks

### T007 — Scenario tags

**File**: `tests/scenarios/charter/share-governance-safely/share-governance-safely.feature`.

- On the `@promise:PR-CHARTER-SHARING-004` scenario, remove `@wip @wip-owner:stijn-dejongh @wip-since:2026-10-18 @defect:6418` (keep `@promise:...`).
- Update the header comment block (lines ~14–19): drop the PR-CHARTER-SHARING-004 `@wip` bullet; PR-CHARTER-SHARING-002 stays `@wip`.
- Check how other bound scenarios in this file are tagged (for example SHARING-001/003) and match them exactly. Read `tests/scenarios/README*` or the tag gate under `tests/architectural/` (`grep -rl "wip-owner" tests/architectural`) to see whether removing `@wip` needs any other ledger update, and do it.
- The step `CharterSteps` asserts a non-zero exit, which WP01 delivers. Do **not** edit Java steps (outside ownership; not needed).

### T008 — PROMISES.md

**File**: `tests/scenarios/charter/PROMISES.md`.

- PR-CHARTER-SHARING-004 row: set Offering authority to the shared containment primitive behind `AssetPathEscapeError` (`resolve_relative_path_within_root`, `src/charter/offering/drg/org_pack_config.py`), checked on authored fragment nodes by `doctor charter-packs` (`find_org_body_path_escapes`, `src/charter/activation/drg_activation.py`), and set Binding to `bound`.
- Update any summary count or "binding status" prose further down that mentions SHARING-004 or #6418.

### T009 — Changelog

**File**: `docs/changelog/CHANGELOG.md`, `[Unreleased]` → `### Fixed` (find the existing heading; do not add a second one).

One entry in the house style (bold lead sentence, **Before:** / **After:**, then the issue in parentheses):

- **`doctor charter-packs` no longer reports a team pack healthy when a node in its graph fragment points outside the pack** (#6418). **Before:** a `drg/fragment.yaml` node whose `body_path` was absolute or climbed out with `..` passed with exit 0 and `errors: []`. **After:** each such node is named in `org_drg.errors`, in the new `org_drg.body_path_escapes` list (`pack`, `node`, `kind`, `body_path`, `reason`) and in the human output, and the command exits 1. A `body_path` inside the pack, even one whose file is missing, is still accepted. Nodes discovered from artifact files keep their own checks; `charter org validate` and `charter status` are unchanged.

Run the changelog style guard (`grep -rl "conflict-marker" tests/ scripts/` to find it) on the result.

## Test commands

```bash
uv run --frozen pytest tests/architectural/ -q -k "scenario or promise or wip or changelog" -p no:cacheprovider
# plus the specific gate files found in T007/T009
```

## Definition of Done

- No `@wip`/`@defect:6418` on SHARING-004; PROMISES.md says `bound`; the changelog entry is present under Fixed.
- The scenario/promise/changelog gates are green.

## Risks / reviewer guidance

- Making the scenario gating before WP01 lands would turn CI red. WP02 depends on WP01.
- Do not touch SHARING-002 (`@wip` pending #6137).
