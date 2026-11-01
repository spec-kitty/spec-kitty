---
work_package_id: WP03
title: The CLI window, the coded refusal and the changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-005
- SC-003
- SC-004
planning_base_branch: issue-6719-activation-writes-under-synthesis-lock
merge_target_branch: issue-6719-activation-writes-under-synthesis-lock
branch_strategy: Planning artifacts for this mission were generated on issue-6719-activation-writes-under-synthesis-lock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6719-activation-writes-under-synthesis-lock unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - Command surface and docs
history:
- at: '2026-10-31T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/deactivate.py
- docs/changelog/CHANGELOG.md
- docs/api/charter-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – The CLI window, the coded refusal and the changelog

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

`charter activate` and `charter deactivate` (positional, cascade, `--preset`, and `--json`) must hold one
activation window, and a lock they cannot acquire must surface as the coded refusal
`CHARTER_SYNTHESIS_LOCK_HELD` / `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` (exit 1, nothing written) in both text and
the `--json` error envelope. Then document the user-facing change.

## Context

- `activate.py` and `deactivate.py` already funnel refusals through `CodedRefusal` → `render_refusal` →
  `render_coded_error` (see `config_refusal`, `_deactivation_refusal`, `render_refusal`). Reuse that seam; do
  not print ad hoc.
- `emit_change_report_json` renders a `CodedRefusal` raised inside `build()` as the canonical error envelope —
  so converting the lock errors at the window boundary is enough for `--json`.
- The lock errors carry `.code` and `.body` (`KittyInternalConsistencyError`); map them straight through.
- `_activate_preset` → `_plan_and_apply_preset` currently handles `PresetApplicationError`,
  `ActiveCharterConfigError`, `PresetFormatError`; it needs the same treatment.

## Subtasks

### T009 — positional `activate` / `deactivate`

Add a small helper in `activate.py` (imported by `deactivate.py`, as it already imports the refusals):

```python
@contextlib.contextmanager
def activation_write_window(repo_root: Path) -> Iterator[None]:
    """Hold the run-wide charter synthesis lock across this command's activation writes (#6719)."""
    try:
        with synthesis_lock(repo_root):
            yield
    except (SynthesisLockHeldError, SynthesisLockUnavailableError) as exc:
        raise CodedRefusal(exc.code, exc.body) from exc
```

Use it around `_activation_change_report`'s body (after the read-only preflight, so a preflight refusal does
not need the lock) and around `_deactivation_change_report`'s write section. Cascade child writes happen
inside that window. `commit_project_registration` and the change-report assembly stay inside (they are
downstream of the write).

### T010 — `--preset` and `--json`

Wrap `_plan_and_apply_preset`'s validate → plan → apply in the same window and render the `CodedRefusal`
there (it is the one path with no `CodedRefusal` handler today). Confirm the `--json` positional path emits
`{"error": {"code": "CHARTER_SYNTHESIS_LOCK_HELD", ...}}` via `emit_change_report_json`, and that exit code is 1
for both commands.

### T011 — changelog

`docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink — edit the real file) under `[Unreleased]`:
a bold, impact-first lead with `(#6719)`, then before/after and the refusal code. Under 1,200 characters.
Follow the file's existing entry shape exactly.

### T012 — docs (`docs/api/charter-commands.md`)

Two places state today's behaviour and both become wrong with this change; update them:

1. The synthesis-lock paragraph (`## charter synthesize`, near "One writing synthesis run holds the
   worktree's synthesis lock at a time") currently says `charter activate`/`deactivate`, presets and the
   interview *save their change, skip the restamp and warn* while a synthesis run holds the lock — which is
   exactly the unlocked write #6719 removes. Replace it with: the activation writes take the same lock for
   their whole read-modify-write, and a held lock refuses with `CHARTER_SYNTHESIS_LOCK_HELD` after the bounded
   wait, writing nothing.
2. The activation-ledger section (`## Activation and the activation ledger`) gains one sentence naming the
   same rule, plus the migration's manifest stamp (a migrating project cannot drop a concurrent synthesis
   entry).

## Definition of Done

- `uv run pytest tests/charter/activation/test_activation_writes_under_synthesis_lock.py -q` fully green,
  including the CLI refusal assertions and `--json`.
- Manual check recorded in the PR: hold the lock from another process/thread (or run a long
  `charter synthesize`), run `spec-kitty charter deactivate <kind> <id>`, see the coded refusal and no write.
- The existing `charter activate`/`deactivate` suites stay green:
  `uv run pytest tests/charter -k "activate or deactivate or cascade or preset" -q`.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 (only regenerate the docs surface
  your diff changes; do not rebuild the whole CLI reference — do not change CLI help text in this WP).

## Risks

- Wrapping too much (e.g. the recompile/reproject post-steps) widens the lock for no benefit and risks a nested
  synthesis deadlock in `--resynthesize`; keep the post-write compile outside the window and note why in a
  comment (C-004).
- The window must not change the order of writes or the existing refusal codes: a `precondition_changed`
  regression must still read as such, not as a lock refusal.

## Reviewer guidance

Confirm the refusal codes come from the exception (never invented), that `--json` keeps one document on stdout
with exit 1, that the window covers the whole RMW, and that the changelog entry names #6719 with the
before/after.
