---
work_package_id: WP08
title: 'Census closure: widen the routing gate to config.py (FR-013)'
dependencies:
- WP02
requirement_refs:
- FR-013
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: bba6054dc227abeb4ca3551b97a3b1851dc31c80
created_at: '2026-09-22T19:22:25.609655+00:00'
subtasks:
- T027
- T028
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_mutation_ownership_routing.py
create_intent: []
execution_mode: code_change
model: claude-sonnet
owned_files:
- tests/architectural/test_mutation_ownership_routing.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (profile YAML), then return. Depends on
**WP02** — do not start until `cli/commands/agent/config.py` is routed + literal-free (only the
allowlisted empty-only `:142 rmdir` remains).

## Objective

Close the removal defect class by construction (charter Standing Order #5): widen the existing
non-vacuous census gate `tests/architectural/test_mutation_ownership_routing.py` to cover
`cli/commands/agent/config.py`, keeping shrink-only + set-equality + self-mutation invariants.
This is the LAST WP. It only touches the arch test — no source.

## Ground truth (verified on main@d57619a900)

- `_module_set()` (~:94): scans `cli/commands/init.py` + all `upgrade/migrations/*.py`.
- `_ROUTED_MODULES` pinned frozenset (~:423): init.py + named migrations. `test_pinned_routed_module_set_is_complete` asserts LIVE == PINNED **set-equality** (route-without-pin fails AND pin-without-route fails).
- `_CLASSIFIER_ATTRS` (~:115): removal family only (`rmtree/move/unlink/remove/rmdir`); the overwrite family (`os.replace`/rename) is deliberately EXCLUDED (deferred to #4901 — out of scope here).
- `config.py`'s `rmtree`/`unlink` already fit the current removal vocabulary; `list.remove`/`shutil.copy2` are NOT classifier-flagged (no false positives).

## Subtasks

### T027 — [RED FIRST] Self-mutation both directions
Extend the gate's self-mutation tests to prove non-vacuity for the new module:
- Planting an un-routed raw `rmtree`/`unlink` in `config.py` (simulated in the test's fixture/AST harness) FAILS the gate.
- Narrowing the pinned routed set to omit `config.py` FAILS the completeness (set-equality) assertion.
- A vanished censused site WARNS (shrink-only), not fails.
Confirm these are RED before the widening edit (i.e. the gate would not currently catch an un-routed config.py op because config.py isn't scanned).

### T028 — Three synchronized edits
1. Add `cli/commands/agent/config.py` to the scanned `_module_set()`.
2. Add `"cli/commands/agent/config.py"` to the pinned `_ROUTED_MODULES` frozenset (satisfies set-equality now that WP02 routed it).
3. Add ONE rationalized, shrink-only allowlist entry for `config.py:<line> Path.rmdir` (empty-only prune after the guard) — mirror the existing empty-only-rmdir category with a one-line rationale.
- Do NOT add the overwrite family or any other module; do NOT weaken shrink-only or the op-vocabulary exhaustiveness self-test.

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Depends on **WP02**. Worktree per lane from `lanes.json`.

## Definition of Done

- Gate passes with config.py routed (WP02) + pinned; fails on a planted un-routed op and on a narrowed routed set (self-mutation both directions).
- Shrink-only ratchet + op-vocabulary exhaustiveness intact; overwrite family still excluded (#4901 untouched).
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_mutation_ownership_routing.py -q` — record counts. (This is the one cross-cutting arch change; a broader `tests/architectural/` sweep is the CI's job, not local.)

## Reviewer guidance (reviewer-renata, opus)

- Non-vacuous: the added coverage genuinely catches an un-routed config.py op (self-mutation proves it).
- Exactly three edits; no allowlist growth beyond the single rationalized `:142 rmdir`; no overwrite-family scope creep.
