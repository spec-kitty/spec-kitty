---
work_package_id: WP04
title: Init backup-then-proceed
dependencies: []
requirement_refs:
- FR-006
- FR-007
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/cli/test_init_backup_then_proceed.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/init.py
- src/specify_cli/template/manager.py
- tests/cli/test_init_backup_then_proceed.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (+ `charter context --action implement`); apply and state.

## Objective
Make `spec-kitty init` **never destroy operator-authored `.kittify/` content**. When it finds
operator missions/memory but no `config.yaml`, back them up to a timestamped
`.kittify/.backup-<ts>/` before scaffolding — at **every** destructive site — and report the path.

## Context
- Operator decision (governed DM `01M2ZQ1G…`): **back-up-then-proceed** (not refuse, not merge).
- Destructive sites (all must be covered — a single-site fix is fakeable):
  - `template/manager.py::copy_package_tree` (`if dest.exists(): shutil.rmtree(dest)`)
  - `template/manager.py::copy_specify_base_from_local` (rmtree of `memory`/`templates`/`missions`)
  - the `shutil.rmtree` site in `cli/commands/init.py`
- The idempotency gate keys only on `.kittify/config.yaml` presence → a `.kittify/` missing only that file is treated as blank.
- **Independent** WP — no lock/kernel dependency; runs in parallel from day 1.
- Vocabulary (C-006): this persistent, operator-reported backup is **distinct** from `template_render/pipeline.py`'s transactional `.bak-{nonce}` (removed on success). Do not reuse that helper; name this one clearly.
- See `../research.md` D6.

## Subtasks

### T013 — Backup helper
- Add a single "back up operator-authored `.kittify/` content to `.kittify/.backup-<UTC-timestamp>/`, then proceed" helper. Timestamp + uniqueness so two re-inits in the same second do not collide/overwrite. Report the backup path to the user.

### T014 — Route every destructive site through it
- Replace each unconditional `shutil.rmtree` at the three sites with the backup helper for operator-authored subtrees (`missions/`, `memory/`). Regenerable scaffold (`templates/`) may still be replaced.

### T015 — Broaden the idempotency gate
- The "already initialized" predicate must detect operator content (populated `missions/`/`memory/`), not rely solely on `config.yaml`.

### T016 — Red-first per-site survival + collision + gate tests
- For **each** of the 3 destructive sites, trigger **that site directly** (construct its precondition or call the function directly — a single end-to-end `init` only fires one site per state, so one init call cannot cover all three): create `.kittify/missions/<c>/…` + `.kittify/memory/<n>` with known bytes and no `config.yaml`; assert the content is present in a reported `.kittify/.backup-<ts>/` and nothing was deleted. Red-first (fails today).
- **Same-second collision test** (spec edge case): two consecutive re-inits within the same second → **two distinct** backups, neither overwritten (guards against a bare-timestamp implementation).
- **FR-007 predicate test**: a direct assertion that the "already initialized" check treats a populated `.kittify/` (missions/memory present, no config.yaml) as initialized — not blank.

## Branch Strategy
Base/merge `fix/local-write-safety`. No dependencies — implement any time: `spec-kitty agent action implement WP04 --agent claude`.

## Definition of Done (non-fakeable)
- Operator `missions/`+`memory/` bytes survive (backed up, path reported) with `config.yaml` absent, asserted by **directly triggering each** destructive site (≥3) — reject a test that only asserts "init exits 1" or covers one site (SC-003).
- Gate no longer treats a populated `.kittify/` as blank — proven by a direct predicate test (FR-007).
- Same-second re-inits produce two distinct backups (collision test present).
- **Red-first evidence**: PR "Tests run" includes the failing-on-current-code output for the survival tests.
- ruff + mypy clean; complexity ≤15.

## Risks & Reviewer Guidance
- **Risk**: fixing one rmtree and leaving the others. Reviewer: confirm all three sites route through the helper (grep `shutil.rmtree` in the diff's modules).
- **Risk**: a divergent third "backup" concept. Reviewer: confirm this backup is distinct from and does not entangle the template-render transactional swap.
