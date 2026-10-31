---
work_package_id: WP01
title: The system actor authority and the reader invariants
dependencies: []
requirement_refs:
- FR-001
- FR-008
- FR-011
- FR-012
- NFR-001
- NFR-002
- C-001
- C-006
- SC-003
- SC-004
planning_base_branch: issue-6722-system-status-actor
merge_target_branch: issue-6722-system-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6722-system-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6722-system-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-system-status-actor-01M67HTR
base_commit: 2b85289cdd6472c1e91c3f5d21e4ebdaa6561ffa
created_at: '2026-10-30T23:51:44.758368+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Authority
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_system_actor_6722.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/status/actor.py
- src/specify_cli/status/models.py
- src/specify_cli/status/__init__.py
- tests/status/test_system_actor_6722.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The system actor authority and the reader invariants

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `src/specify_cli/status/actor.py` gains exactly one enum member (`ActorRole.SYSTEM`) and one
  builder (`build_system_actor(tool) -> {"tool": tool, "role": "system", "profile": None, "model": None}`).
- The builder is the single authority: it takes only `tool`, and it never routes the identity
  through `parse_agent_boundary_string`.
- `tests/status/test_system_actor_6722.py` proves the builder contract, the two decoders
  (`specify_cli.status.models.decode_actor` and `spec_kitty_events.diary.decode_actor`), the
  reader-invariant matrix, and a mixed-shape reduction.

Success: FR-001, FR-008, FR-011, FR-012; NFR-001, NFR-002; C-001, C-006.

## Context & Constraints

- Read: `kitty-specs/system-status-actor-01M67HTR/spec.md` § Decision, `data-model.md`,
  `contracts/system-actor.md` §1 §3.
- `ActorField = str | dict[str, str | None]` already exists (`status/models.py:166`); the dict
  actor needs no plumbing.
- `spec_kitty_events >= 11.3.0,<12` (`pyproject.toml:80`). Its `diary.decode_actor` does not
  enumerate `role`; the pin must be a test, not a comment.
- Do **not** change `build_status_actor`, `compose_status_actor`, `actor_from_option`,
  `role_for_hop`, `role_for_wp`, `actor_identity_str` or `actor_full_identity`. #6400/#6715
  pinned them; this mission consumes them.
- Do **not** add a fifth actor key (`profile_source` is #6721).

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6722-system-status-actor`; completed
  changes merge back into it. Execution worktrees are allocated per computed lane from
  `lanes.json`.
- **Planning base branch**: `issue-6722-system-status-actor`
- **Merge target branch**: `issue-6722-system-status-actor`

## Subtasks & Detailed Guidance

### T001 – Add the role value and the builder

- **Purpose**: one place that knows the system shape.
- **Steps**: add `SYSTEM = "system"` to `ActorRole`; add `build_system_actor(tool: str)`; add both
  to `__all__`; export through `status/__init__.py` next to `build_status_actor` and add the name
  to that module's `__all__` (the repository's `__all__` convention).
- **Files**: `src/specify_cli/status/actor.py`, `src/specify_cli/status/__init__.py`.
- **Notes**: a blank `tool` raises `ValueError` — an actor that names nobody must be refused, not
  recorded. The docstring must say why the value is not parsed and why `profile`/`model` are
  literals.

### T002 – Name the system shape where the field is declared

- **Purpose**: a reader of `models.py` must not have to find `actor.py` to learn that
  `role: "system"` is legal.
- **Steps**: extend the `ActorField` / `decode_actor` docstrings: the accepted dict shapes are the
  written 4-key (now used by agent, operator *and* system writers) and the read-only 5-key.
  State that `role ∈ {implementer, reviewer, system}` and that `ActorRole` is the only authority.
- **Files**: `src/specify_cli/status/models.py` (docstrings only; **no logic change**).

### T003 – Red-first: the builder contract

- **Purpose**: prove the shape and the "nothing invented" guarantee.
- **Steps**: write the tests first and observe them fail (`ImportError`/`AttributeError` on the
  base) before T001. Cover: exactly four keys in `{role, profile, tool, model}`; `role == "system"`;
  `profile is None` and `model is None`; `tool` returned whole for `claude`, for `merge`, and for
  `migration:backfill_runtime_state` (the colon-carrying case that a compact parse would split);
  blank/whitespace `tool` raises `ValueError`; `ActorRole.SYSTEM == "system"` and the enum has
  exactly the three members.
- **Files**: `tests/status/test_system_actor_6722.py`.

### T004 – Red-first: the decoder pin

- **Purpose**: catch a future events release that enumerates `role`, here rather than at a user's log.
- **Steps**: assert `specify_cli.status.models.decode_actor(system)` returns an equal dict; assert
  `spec_kitty_events.diary.decode_actor(system)` does the same; assert a round-trip through
  `StatusEvent.to_dict()` / `StatusEvent.from_dict()` preserves the actor (build the event with
  `build_system_actor`, serialize, parse, compare); assert the 5-key shape is still refused by the
  **package** decoder while the CLI decoder accepts it (the #6721 gate, unchanged).
- **Files**: `tests/status/test_system_actor_6722.py`.

### T005 – Red-first: the reader invariants and the mixed-shape reduction

- **Purpose**: the load-bearing proof that the shape never decides a verdict.
- **Steps**: for both shapes of the same identity (`"migration:backfill_runtime_state"` as a string
  and built), assert identical answers from `actor_identity_str`, `is_migration_actor`, the
  reducer's seed arm (reduce a two-event log whose only claim is the seed), and
  `validate_timestamp_continuity`'s exemption. Then build two logs that differ only in seed shape
  and assert the reduced snapshots are equal, key for key.
- **Files**: `tests/status/test_system_actor_6722.py`.
- **Notes**: construct events directly; do **not** call a writer (WP02–WP04 own those). Keep the
  test module under ~400 lines by using a small event factory.

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_system_actor_6722.py -q
uv run --frozen pytest tests/status -q
uv run --frozen ruff check src/specify_cli/status tests/status/test_system_actor_6722.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/status/actor.py src/specify_cli/status/models.py src/specify_cli/status/__init__.py tests/status/test_system_actor_6722.py
uv run --frozen mypy src/specify_cli/status/actor.py src/specify_cli/status/models.py
```

Record the exact commands and pass/fail counts in the PR body. Red-first evidence: the T003–T005
modules failing on the base commit, with the counts.

## Risks & Mitigations

- **The builder starts parsing the identity.** A `migration:` tool would become `tool="migration"`,
  which silently un-seeds every seed. T003's colon case is the guard.
- **A new role value leaks into `role_for_hop`.** Any hop written with `role: "system"` would be
  wrong. Keep the hop functions untouched; T003 pins the enum's three members only.

## Review Guidance

- Does `build_system_actor` take a role, profile or model argument? It must not.
- Is any reader (`actor_identity_str`, `is_migration_actor`, the reducer, the projection helpers)
  modified? It must not be.
- Does the mixed-shape test compare reduced snapshots (the real proof), or only `actor_identity_str`
  (a proxy)? Only the former proves the readers did not move.

## Progress & Status

Progress, history and status live in the status event log — never in this file.

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
