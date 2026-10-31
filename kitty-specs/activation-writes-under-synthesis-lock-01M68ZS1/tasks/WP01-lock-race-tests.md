---
work_package_id: WP01
title: Two-writer and refusal tests for the activation writes
dependencies: []
requirement_refs:
- FR-006
- NFR-002
- SC-001
- SC-002
- SC-003
- SC-004
- NFR-003
planning_base_branch: issue-6719-activation-writes-under-synthesis-lock
merge_target_branch: issue-6719-activation-writes-under-synthesis-lock
branch_strategy: Planning artifacts for this mission were generated on issue-6719-activation-writes-under-synthesis-lock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6719-activation-writes-under-synthesis-lock unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-activation-writes-under-synthesis-lock-01M68ZS1
base_commit: 142f48edd6d0d114b7ba9ed9ce86d6837dc31309
created_at: '2026-10-31T12:51:53.586407+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Tests first
history:
- at: '2026-10-31T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/activation/
create_intent:
- tests/charter/activation/test_activation_writes_under_synthesis_lock.py
execution_mode: code_change
model: ''
owned_files:
- tests/charter/activation/test_activation_writes_under_synthesis_lock.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Two-writer and refusal tests for the activation writes

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your profile:

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Write the red-first tests for #6719 in a **single new module**,
`tests/charter/activation/test_activation_writes_under_synthesis_lock.py`. Each test must fail on the current
tree (before WP02/WP03 land) for the *right* reason, and pass once the four write seams and the two CLI
commands take the run-wide synthesis lock.

The two acceptance criteria of the issue are the two two-writer tests (T001, T002); T003 is the behavioural
pin for the refusal path.

## Context

- The lock already exists: `charter.activation.synthesizer.synthesis_lock.synthesis_lock(repo_root)` (#6453).
  It is per-worktree, re-entrant per thread, bounded (10 s default, read at call time from
  `_SYNTHESIS_LOCK_TIMEOUT_S`), and raises `SynthesisLockHeldError` (code `CHARTER_SYNTHESIS_LOCK_HELD`) /
  `SynthesisLockUnavailableError` (`CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`).
- Precedent to copy: `tests/charter/synthesizer/test_synthesize_activation_append.py::_Handshake` (pause the
  first writer at its write; wait until the second provably fails a non-blocking lock attempt) and
  `tests/charter/synthesizer/test_synthesis_lock.py::hold_from_other_thread`.
- Fixtures: `tests/charter/test_activate_restamps_bundle_hash.py::_project` (migrated-shape project with a real
  synthesis manifest) and `tests/_factories/activation_ledger.py::seed_activation_ledger` /
  `read_activation_ledger`.
- The reproduction is recorded in `<mission_dir>/research.md` §E-01: on `main` the deactivate loses with
  `ValueError('precondition_changed: .../activation.yaml')` and no `deactivated_directives` entry.

## Subtasks

### T001 — deactivate vs synthesis append (two-writer, deterministic)

Seed a migrated project (charter pointer + ledger with `activated_directives: [001-architectural-integrity-standard]`
and `activated_tactics: [existing-tactic]`). Two threads:

- writer D: `ActiveCharterManager().deactivate(ProjectContext(repo_root=repo), kind="directive", artifact_id="001-architectural-integrity-standard")`
- writer S: `append_synthesized_activations(repo, {"tactic": ["new-tactic"]})`

Pause whichever writer reaches its write first (monkeypatch that writer's own seam name so only it pauses:
`charter.activation.pack_manager.commit_plan` for D, and for S a seam inside
`charter.activation.synthesizer.reach_only`), wait until the other thread **provably** waits on the synthesis
lock (`monkeypatch` `kernel.locks._LockCore.try_lock_once` to record a `False` result, never a `sleep`), then
let the paused writer proceed.

Assertions: no writer raised; the ledger has the deny entry (`deactivated_directives == ["001-architectural-integrity-standard"]`)
**and** `new-tactic` in `activated_tactics` (the positive control that stops the test passing by writing nothing).

### T002 — migration manifest stamp vs a concurrent synthesis manifest write

Project with a stampable synthesis manifest (use `_project`). Writer M: `apply_ledger_migration(repo, plan_ledger_migration(repo))`.
Writer S: a synthesis run's manifest write — read `synthesis-manifest.yaml`, add one artifact entry, recompute
`compute_bundle_content_hash`, `finalize_manifest`, write — performed **inside `synthesis_lock(repo)`**, which
is what `charter synthesize` holds for its whole run (say so in a comment; do not invent a lock-free writer).

Pause M between its manifest read (`_stampable_manifest`) and its write, wait for S to provably wait on the
lock, continue. Assertion: the artifact S added is still in the manifest after M finished, and the manifest
still validates (`load_yaml`). Before the fix S writes first and M's stale document drops the entry.

### T003 — the refusal path

With another thread holding the lock (`hold_from_other_thread`-style helper, or a `threading.Thread` entering
`synthesis_lock`), and `monkeypatch.setattr(charter.activation.synthesizer.synthesis_lock, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)`:

- `charter activate directive <available-id>` → `CHARTER_SYNTHESIS_LOCK_HELD`, exit 1, activation files byte-identical;
- `charter deactivate directive 001-architectural-integrity-standard` → same;
- `charter activate --pack built-in --preset <preset>` → same;
- `apply_ledger_migration` → same coded error;
- `--json` variants → the same code in the error envelope.

Use `typer.testing.CliRunner` against `specify_cli.cli.commands.charter.charter_app`.

## Test strategy

- Mark the module `pytest.mark.integration` (real git repo + real lock) and `pytest.mark.git_repo` if the lock
  placement needs a git repository; `tmp_path` projects only.
- Every thread join has a hard timeout and asserts `not thread.is_alive()`; a hang must fail, not block CI.
- No sleeps as synchronisation; only `Event.wait` on real signals with a timeout.
- Keep the module under ~350 lines; share the fixtures at module level.

## Definition of Done

- The three tests exist and **fail on the unfixed tree** (T001/T002 with `precondition_changed` / a dropped
  entry, T003 with the command succeeding while the lock is held). Record the pre-fix failure output in the WP
  review note (and in the PR's `## Tests run`).
- After WP02/WP03 land, all three pass.
- `uv run pytest tests/charter/activation/test_activation_writes_under_synthesis_lock.py -q` is green post-fix,
  and `uv run ruff check` / `uv run ruff format --check` pass on the new file.

## Risks

- A handshake that pauses a *lock holder* while the other writer runs deadlocks once the fix lands — pause at
  the write and release as soon as contention is observed, never hold the lock while waiting for the peer.
- `_project` seeds a legacy `activated_directives` key in `charter.yaml` (a warning is printed); if that
  obscures the assertion, seed the ledger and drop the legacy key from the fixture copy.

## Reviewer guidance

Check the tests are not vacuous: each asserts a positive control (the other writer's effect is present), the
lock contention is proven rather than timed, and no test weakens or skips an existing gate.
