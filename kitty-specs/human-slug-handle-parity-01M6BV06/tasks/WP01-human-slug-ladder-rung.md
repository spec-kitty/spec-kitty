---
work_package_id: WP01
title: The identity resolver's human-slug rung
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
planning_base_branch: issue-6278-human-slug-handle-parity
merge_target_branch: issue-6278-human-slug-handle-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6278-human-slug-handle-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6278-human-slug-handle-parity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-human-slug-handle-parity-01M6BV06
base_commit: e2689fa73f08a40db9daa2c9592e4df74058842e
created_at: '2026-11-01T15:23:27.838784+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - The resolver
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/context/mission_resolver.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/context/mission_resolver.py
- tests/context/test_mission_resolver.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6278'
---

# Work Package Prompt: WP01 – The identity resolver's human-slug rung

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: claude

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission human-slug-handle-parity-01M6BV06`) and address every item before handing back.

## Objectives & Success Criteria

`specify_cli/context/mission_resolver.py::resolve_mission` is the single identity resolver every
`--mission` selector except the read-path fold reaches. Its priority-4 rung ("human slug without
prefix") compares `strip_numeric_prefix(mission_slug) == handle`, and `strip_numeric_prefix` removes
only a leading `NNN-`. A Mission created today is `<human-slug>-<mid8>`, so `smoke-test` never
matches `smoke-test-01M6BTQX` — and `implement WP01 --mission smoke-test` exits 2 with "No mission
found" for a Mission that `agent tasks status --mission smoke-test` resolved one command earlier
(#6278).

This WP makes that rung fold the trailing mid8 as well, under three conditions the spec fixes:

- **Fold only this Mission's own mid8** (FR-002). `ResolvedMission.mid8` is `mission_id[:8]`;
  `smoke-test-01M6BTQX` whose `mission_id` starts `01ZZZZZZ` keeps `smoke-test-01M6BTQX` as its
  human slug, so `smoke-test` still does not resolve to it.
- **Two Missions sharing a human slug still fail loudly** (FR-003) with `AmbiguousHandleError` and
  the full candidate list. Route the new matching through the existing `_resolve_or_raise`; do not
  write a second ambiguity check.
- **No other rung changes** (NFR-002): full ULID, mid8, exact-directory, legacy `NNN-` human slug
  and numeric-prefix all answer exactly as before. The fold belongs in `_resolve_from_index`, the
  one ladder shared by `FsMissionResolver` and `FakeMissionResolver` (C-001), and adds no
  `meta.json` read (NFR-001 — compare indexed fields only).

Success: `resolve_mission("smoke-test", repo_root)` on a fixture whose only Mission is
`kitty-specs/smoke-test-01M6BTQX` (mission_id `01M6BTQX…`) returns that Mission; the same call on a
fixture whose `mission_id` starts `01ZZZZZZ` raises `MissionNotFoundError`; on a fixture holding
`smoke-test-01AAAAAA` and `smoke-test-01BBBBBB` it raises `AmbiguousHandleError` naming both.

## Context

Read first, in this order:

1. `src/specify_cli/context/mission_resolver.py` — the module docstring's priority list (points 3–5),
   `_resolve_from_index`, `_resolve_or_raise`, `ResolvedMission`.
2. `src/specify_cli/lanes/branch_naming.py::_human_slug_for_mid8_branch` — the same rule, already
   applied when composing branch names ("strip the embedded mid8 only when it matches mission_id's
   mid8; mismatched mid8 is not stripped"). **Do not import it**: `branch_naming` sits above
   `context/` and the import would invert the layer. Share the rule, not the symbol.
3. `kitty-specs/human-slug-handle-parity-01M6BV06/spec.md` (FR-001..FR-005, the Edge Cases) and
   `research.md` (D1–D5).

`strip_numeric_prefix` is already imported at the top of the module. Keep the helper you add
module-private (for example `_human_slug_for_index_entry`) — the dead-symbol gate and the
`__all__` convention (C-007) expect no new exported name.

## Subtasks

### T001 — Failing rows in `tests/context/test_mission_resolver.py` (red first)

Add rows to the existing `TestResolveMission`-style suite using the file's own `_make_mission`
helper. Write them **before** T002 and confirm they fail for the right reason
(`MissionNotFoundError` for the resolvable handle; the other two rows pass only after the fix
relaxes the rung — see below).

- `smoke-test-01M6BTQX` with `mission_id` `01M6BTQX…` (mid8 == the tail): `resolve_mission("smoke-test")`
  returns it. Red today.
- The same directory with a `mission_id` starting `01ZZZZZZ`: `resolve_mission("smoke-test")` raises
  `MissionNotFoundError`, and `resolve_mission("smoke-test-01M6BTQX")` still returns it. This is the
  positive control that the fold is guarded, not a blanket suffix strip.
- `smoke-test-01AAAAAA` (mid8 `01AAAAAA`) + `smoke-test-01BBBBBB` (mid8 `01BBBBBB`):
  `AmbiguousHandleError`, with both composed slugs in the candidates and the handle
  `smoke-test` in the message.
- A composed slug whose mid8 tail is not at the end (`01M6BTQX-smoke`) keeps its whole slug as its
  human slug, so `01M6BTQX-smoke` resolves and `smoke` does not.

Keep the file's existing markers (`pytest.mark.unit`, `pytest.mark.fast`) and its ID constants
style.

### T002 — Fold the mid8 in the priority-4 rung

In `_resolve_from_index`, replace the priority-4 comparison with a comparison against the
Mission's human slug, computed from indexed fields:

```
human = strip_numeric_prefix(m.mission_slug)
suffix = f"-{m.mid8}"
if human.endswith(suffix): human = human[:-len(suffix)]      # only this Mission's own mid8
```

Keep every other line of the ladder (including the `_is_numeric_prefix` guard and the fall-through
to priority 5) exactly as it is, and keep the `_resolve_or_raise` call so ambiguity stays loud.

Update the wording that now describes the wrong thing:

- module docstring priority 4 ("Human slug without prefix (e.g. `foo-bar`)") — name the mid8 suite and
  the own-mid8 guard;
- `_resolve_from_index`'s docstring priority list and its `AmbiguousHandleError` /
  `MissionNotFoundError` notes;
- `resolve_mission`'s docstring if it repeats the rung;
- the `_resolve_exact_directory` note that refers to "another Mission at priority 4 or 5", only if
  the sentence becomes untrue (it should not).

Do not touch `_resolve_exact_directory`, `_build_index`, the adapters, or the selection helpers.

### T003 — Prove the other rungs are unchanged

Run the whole existing file plus the resolver-adjacent suites and record the result in the WP
hand-back:

```
uv run pytest tests/context/test_mission_resolver.py tests/context/test_mission_resolver_exact_directory.py tests/specify_cli/context/test_mission_resolver_port.py -q
```

Every pre-existing row must stay green untouched — that is NFR-002's proof. If any existing test
encodes the old "`foo-bar` only" behaviour in a way that now legitimately changes, say so explicitly
in the hand-back rather than silently rewriting it; a behaviour change outside the human-slug rung
is a defect in this WP, not a test to update.

## Definition of Done

- The four new rows exist and are red before T002, green after it (show both runs in the hand-back).
- `git diff` touches only `mission_resolver.py` and `tests/context/test_mission_resolver.py`.
- `uv run ruff check src/specify_cli/context/mission_resolver.py tests/context/test_mission_resolver.py`
  and `uv run mypy src/specify_cli/context/mission_resolver.py` are clean.
- The two architectural gates this can trip are green:
  `uv run pytest tests/architectural/test_no_dead_symbols.py -q` and the docstring/`__all__`
  check that covers `mission_resolver.py`.
- No `TODO`, no skipped test, no `xfail`, no assertion loosened to accommodate the fix.
