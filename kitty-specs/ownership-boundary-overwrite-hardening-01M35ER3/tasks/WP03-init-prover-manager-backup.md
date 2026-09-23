---
work_package_id: WP03
title: '#4931 init prover run_created re-wire + manager backup-before-overwrite'
dependencies: []
requirement_refs:
- FR-001
- FR-005
- NFR-001
- NFR-002
- C-002
- C-003
- C-004
planning_base_branch: issue-4931-ownership-boundary-overwrite-hardening
merge_target_branch: issue-4931-ownership-boundary-overwrite-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-4931-ownership-boundary-overwrite-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4931-ownership-boundary-overwrite-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-overwrite-hardening-01M35ER3
base_commit: 638e27d2fe4885511dc2b5597d8b65ff42292310
created_at: '2026-09-22T21:41:57.752999+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
history:
- at: '2026-09-22T21:15:00Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/init.py
create_intent:
- tests/cli/test_init_templates_preservation.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/init.py
- src/specify_cli/template/manager.py
- tests/test_template/test_manager.py
- tests/cli/test_init_templates_preservation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ownership-boundary-overwrite-hardening-01M35ER3 --json`). Apply the resolved initialization, boundaries, directives, and tactics, then state which you applied. Force `PYTHONPATH=$(pwd)/src` for pytest; use `.venv/bin/python -m pytest` (never a bare `uv run`). This WP is **P0** (#4931) — a silent, unrecoverable deletion on the first command every user runs.

## Objective

Fix BOTH #4931 destroyers with their DISTINCT correct mechanisms (do not conflate the seams). `init` on a project with no `.kittify/config.yaml` deletes a user-authored `.kittify/templates/` tree (an active resolver LEGACY tier) with no backup, exit 0. There are two destroyers:
1. **Removal seam** (universally reached): `init.py` cleanup proves `.kittify/templates` package-owned by PATH NAME (`ManagedPathProver(managed_relpaths={".kittify/templates", ...})`), so the routed guard removes it.
2. **Overwrite seam** (full-copy path only): `template/manager.py` `shutil.rmtree(templates_dest)` then `copytree`, unguarded.

Read first: `../spec.md` (FR-001, US1), `../plan.md` (Design → FR-001 two mechanisms), `../traces/design-decisions.md` (D5). Read `gh issue view 4931` for the four-arm repro. A ready repro script is at the session scratchpad `…/scratchpad/repro_4931.sh` (isolated HOME/XDG; does not touch this tree).

## Frozen boundaries (do NOT touch)

- `tests/architectural/test_mutation_ownership_routing.py` — **owned by WP02**. Your `init.py` edits WILL shift its line-pinned allowlist (e.g. the `init.py:1596:shutil.rmtree` entry); WP02 depends on you and re-pins it. Do NOT edit that gate. Your targeted test surface is init + manager tests, not `tests/architectural/`.
- `asset_preservation/provers.py` — the `run_created` branch (`:166`) already exists; you CONFIGURE it from `init.py`, you do not modify `provers.py`.
- #4907's `agent/config.py` `.claude/commands/` rmtree — OUT of scope (claimed). Your audit sweep (T013) REPORTS other by-name shortcuts; it does not fix #4907.

## Subtasks

### T010 — RED-first #4931 regression (write FIRST, watch it fail)
Create `tests/cli/test_init_templates_preservation.py`, `@pytest.mark.regression`, docstring-pin `#4931`. RED assertions through the pre-existing `init` entry point in an isolated HOME + disposable repo:
- **guard path**: seed a unique-content `.kittify/templates/spec-template.md`, no `config.yaml`, run `init --ai claude --non-interactive`; assert the file (or a `.kittify/.backup-*` copy) still exists afterwards.
- **full-copy LOCAL path**: exercise `copy_specify_base_from_local`; assert a pre-existing templates file is backed up, not destroyed.
- **full-copy PACKAGE path (the pip default) — MUST be exercised explicitly**: call `copy_specify_base_from_package` DIRECTLY (do not rely on the test HOME's path resolution — inside a spec-kitty checkout `get_local_repo_root()` resolves to the LOCAL path, so the package destroyer would never run and the P0 bug would hide). Assert a pre-existing operator `templates/` is preserved/backed up.
All three MUST be RED on the base. Also assert the CONTROL: a genuinely run-created templates tree IS still cleaned (US1 #3), and `command-templates` is still preserved.

### T011 — Re-wire the `init.py` cleanup prover (removal seam)
At `init.py:~1573`, stop declaring `.kittify/templates` in `managed_relpaths` (name is not proof — C-002). Instead pass the templates/scratch dirs in `run_created=` ONLY for paths this specific invocation created — derive the set from the actual create/bootstrap step, not unconditionally. A pre-existing user tree then proves `None` → the guard preserves/archives it with the same "not package-owned — left in place" diagnostic `command-templates` already prints. Keep `.kittify/.scratch` handling correct (it too must be `run_created`, not by-name, unless it is genuinely always this-run scratch — justify whichever you choose).

### T012 — `manager.py` backup-before-overwrite (overwrite seam) — BOTH functions [P]
`templates/` is unprotected in BOTH full-copy functions (`memory/`+`missions/` already back up in both). Fix BOTH:
- `copy_specify_base_from_local:117-120`: before `shutil.rmtree(templates_dest)` + `copytree`, call `back_up_operator_subtrees(specify_root, ["templates"])` — the in-file `memory/` precedent (`:107`, #4759).
- `copy_specify_base_from_package:193` (**the pip-installed default `init`**): pass `preserve_existing=True` to the `copy_package_tree(templates_resource, templates_dest, ...)` call — exactly as `memory/` does at `:179`. This routes through `back_up_operator_subtrees` at `:156` instead of the raw `rmtree` at `:158`.
Do NOT route either through `guard_destructive_removal` (that models an overwrite as a removal — NFR-003). Missing the package path leaves the P0 destroyer live on the most common consumer path.

### T013 — Audit sweep (report only)
Grep every `guard_destructive_removal` call site (the 10 upgrade migrations + `skills/installer.py` + `init.py`) for other `managed_relpaths`-by-name shortcuts that could prove a user-authorable path owned by name. Record findings in your review notes / PR body (a bulleted list of `file:line` + whether it is a real risk). Do NOT fix #4907's `agent/config.py`; if the sweep finds it, name it as the claimed sibling and leave it.

### T014 — Unit/functional tests
In `tests/test_template/test_manager.py` add cases proving BOTH `copy_specify_base_from_local` AND `copy_specify_base_from_package` back up a pre-existing operator `templates/` before overwrite (assert the backup exists and the operator bytes survive). Round out `test_init_templates_preservation.py` with the `probe_cfgdel` arm (config.yaml removed) and the run-created-still-cleaned control.

## Definition of Done

- T010 RED on base, GREEN at final commit (both destroyers); record evidence.
- `run_created` is true ONLY for this-invocation-created dirs (R3) — reviewer verifies a pre-existing tree is preserved AND a genuinely-created one is still cleaned.
- Audit-sweep findings recorded (T013).
- `ruff`/`ruff format`/`mypy --strict` clean; complexity ≤15; no new suppressions.
- Targeted tests: `tests/cli/test_init_templates_preservation.py tests/test_template/ tests/cli/test_init_backup_then_proceed.py` (+ any init test module) — record commands + counts. Do NOT run `tests/architectural/` (WP02 owns the gate reconciliation).

## Reviewer guidance

Verify the two mechanisms are distinct and correct: init.py = provenance (`run_created`), manager.py = `back_up_operator_subtrees` / `preserve_existing=True`. **Verify BOTH manager full-copy functions are fixed** — reject if only `copy_specify_base_from_local` was patched and the pip-default `copy_specify_base_from_package:193` still destroys (the T010 package-path arm must have been RED on base and exercised the package function DIRECTLY, not whichever path the test HOME resolved). Reject if manager.py was forced through the removal chokepoint, or if `run_created` is populated unconditionally (which would re-arm the deletion). Confirm the WP did not edit the arch gate.
