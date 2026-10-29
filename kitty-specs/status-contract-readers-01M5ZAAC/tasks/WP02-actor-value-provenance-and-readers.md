---
work_package_id: WP02
title: Actor value, provenance and readers
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-012
- FR-013
- FR-014
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-006
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: 847f31922e351a1114a5173bb6d213dd36488d19
created_at: '2026-10-27T18:48:41.477188+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Foundations
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/actor.py
- tests/status/test_status_actor.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/actor.py
- src/specify_cli/status/models.py
- src/specify_cli/status/resolved_binding.py
- src/specify_cli/status/emit.py
- src/specify_cli/status/__init__.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/status/test_status_actor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Actor value, provenance and readers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item and record each change with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## ⚠️ Phase split (operator decision 2026-10-27) — overrides the sections below

`spec-kitty-events` 11.0.0's `diary.decode_actor` (every status read) accepts only `{tool, role, profile, model}`. In this mission, writers emit that **4-key** structured actor; `profile` comes only from the dispatch invocation, `--profile`, or the compact `--agent` profile segment, else `null`. **No WP-frontmatter fill and no `profile_source` on the wire** (deferred to a follow-up, spec C-006). Wherever the text below mentions `planned_profile_for_wp`, `planned_profile=`, `profile_source` or `wp_frontmatter` on a *written* actor, drop it; expected actors in tests are 4-key dicts. Every other instruction stands.

**WP02 rework (cycle on the existing lane commits):**
- Keep: `ProfileSource` (in `models.py`), `decode_actor` accepting exactly the 4-key or the 5-key set, `actor_full_identity` dropping a `wp_frontmatter` profile (reader side, unit-tested), `ActorRole`, `role_for_hop`.
- Change: `build_status_actor` returns the 4-key dict; profile = binding profile, else agent-string profile, else null.
- Remove from this PR (no production caller once the fill is deferred; the follow-up restores them from the parked patch `/tmp/claude-0/-home-user-spec-kitty/d3b825e4-52d0-5999-8fef-1f1dd41bdb8f/scratchpad/t010-emit-delegation.patch` and git history): `planned_profile_for_wp`, the frontmatter branch of `resolve_profile` (drop `resolve_profile` if only `build_status_actor` needs it), `ResolvedBinding.profile_source`, its stamping in `_resolve_dispatch_binding`, and the matching assertions added to `tests/specify_cli/status/test_resolved_binding_linkage.py`.
- Land T010: `build_resolved_actor` / `build_self_asserting_actor` delegate to `build_status_actor` (now behaviour-preserving: same 4 keys, same values). The existing suites that went red with the 5-key delegation must be green.

## Objectives & Success Criteria

Foundation for issue #6400. No write path changes behaviour in this WP (WP03-05 wire them); this WP delivers the value, readers and identity rule, all unit-tested.

- New pure module `src/specify_cli/status/actor.py` builds `{tool, role, profile, profile_source, model}`.
- `decode_actor` accepts exactly: a string, the legacy 4-key dict, or the 5-key dict; refuses everything else (FR-012).
- `actor_full_identity` ignores a profile whose `profile_source` is `wp_frontmatter` (FR-013); identities of every legacy shape are unchanged (C-004).
- `actor_identity_str` and `work_package_lifecycle._actor_key` stay tool-based (FR-014) — do not edit them.
- `ResolvedBinding` carries `profile_source` (`invocation` or `flag`), stamped by `_resolve_dispatch_binding`; `ResolvedBinding.to_delta` output is unchanged.
- `build_resolved_actor` / `build_self_asserting_actor` (status/emit.py) become thin delegates to the new builder, so there is one actor-building authority.

## Context & Constraints

- Spec FR-004..FR-006, FR-012..FR-014; plan D-2..D-6; data-model.md; contracts/status-actor.md.
- Operator decisions (Decision Moments in `kitty-specs/status-contract-readers-01M5ZAAC/decisions/`): `profile_source` values `invocation | flag | agent_string | wp_frontmatter | null`; frontmatter fills excluded from identity.
- #6715 (independence gate, in flight) reuses `actor_full_identity` and promises no identity change on existing logs. Our change must keep every legacy identity byte-identical.
- `decode_actor`'s strict key check exists to stop silent `repr` flattening (earlier mission FR-015). Accept exactly two key sets, never "any superset".
- `_resolve_dispatch_binding` (`src/specify_cli/cli/commands/agent/workflow.py:1482`) must keep "never reads frontmatter" (C-007 / INV-6): the frontmatter fill happens in the actor builder, not in the binding.

## Branch Strategy

- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

```bash
spec-kitty agent action implement WP02 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first unit tests

- **File**: `tests/status/test_status_actor.py` (new). RED on the base (ImportError on `specify_cli.status.actor`, and the 5-key decode raises).
- **Cases**:
  - `resolve_profile` order (parametrize): invocation binding wins over flag, agent string and frontmatter; flag binding over agent string and frontmatter; agent string over frontmatter; frontmatter alone → `wp_frontmatter`; nothing → `(None, None)`. Empty strings count as absent.
  - `role_for_hop(from_lane, to_lane)` table (data-model.md "Role per hop"), including `in_review → planned`, `in_review → in_progress`, `in_review → blocked`, `in_progress → for_review`, `planned → claimed`, `for_review → in_review`, `approved → done`, and lane aliases (`doing`).
  - `build_status_actor` returns exactly the five keys; `profile_source is None` iff `profile is None`; `tool` is the bare tool parsed from a compact `--agent` (`"claude:opus:python-pedro:implementer"` → `tool="claude"`, `model="opus"`, `profile="python-pedro"`, `profile_source="agent_string"`); a binding model wins over the agent-string model; `tool` falls back to the given default (e.g. `"user"`).
  - `decode_actor`: accepts the 5-key dict (round trip equal), the 4-key dict, strings; refuses 3-key, 6-key, unknown `profile_source`, `profile_source` set with `profile` null and the reverse, non-string values.
  - `actor_full_identity`: 5-key with `wp_frontmatter` → `"claude::"` style identity without profile; same with `flag` → profile included; 4-key and string inputs return exactly what the base returns (copy two or three cases from `tests/status/test_actor_identity_reconciliation_4665.py` as ratchets).
  - `planned_profile_for_wp(feature_dir, "WP01")`: reads `agent_profile` from a WP file in `feature_dir/tasks/`; returns `None` for a missing file, missing key, empty value or unparseable frontmatter (never raises).
- Commit alone first: `test(status): pin the structured status actor (#6400)`.

### Subtask T006 – `status/actor.py`

- **Contents** (keep each function ≤ complexity 15, fully typed, module `__all__` not required but harmless):
  - `class ProfileSource(StrEnum)`: `INVOCATION="invocation"`, `FLAG="flag"`, `AGENT_STRING="agent_string"`, `WP_FRONTMATTER="wp_frontmatter"`.
  - `class ActorRole(StrEnum)`: `IMPLEMENTER="implementer"`, `REVIEWER="reviewer"` (reuse an existing role constant if `status` already defines one — grep `"reviewer"` constants in `status/review_roles.py`/`emit.py` first; do not create a duplicate authority).
  - `def role_for_hop(from_lane: str | Lane | None, to_lane: str | Lane) -> str`: resolve aliases via `status.transitions.resolve_lane_alias`; reviewer if `to_lane in {in_review, approved, done}` or `from_lane == in_review`; else implementer.
  - `def resolve_profile(*, binding: ResolvedBinding | None, agent_profile_segment: str | None, planned_profile: str | None) -> tuple[str | None, str | None]` using `binding.profile_source` for the binding case.
  - `def build_status_actor(*, role: str, agent: str | None, fallback_tool: str | None, binding: ResolvedBinding | None, planned_profile: str | None) -> dict[str, str | None]`: parse `agent` with `models.parse_agent_boundary_string` (only when truthy; a `ValueError` for an empty tool segment propagates as today); `model = binding.model or agent_model`.
  - `def planned_profile_for_wp(feature_dir: Path, wp_id: str) -> str | None`: locate the WP file (`feature_dir / "tasks" / f"{wp_id}-*.md"` glob, first match, or reuse an existing locator such as `task_utils.support.locate_work_package` if it accepts a feature dir without heavy imports), read via `status.wp_metadata.read_wp_frontmatter`, return `metadata.agent_profile or None`; catch only the concrete read/parse errors (`OSError`, `ValueError`, the frontmatter error type), never bare `except`.
- Avoid import cycles: `actor.py` may import `status.models`, `status.resolved_binding`, `status.transitions`; `status/emit.py` imports `actor.py`, not the reverse.

### Subtask T007 – Widen `decode_actor` [P]

- `src/specify_cli/status/models.py:155-195`. Accept key set `{role, profile, tool, model}` or `{role, profile, profile_source, tool, model}`. Validate `profile_source` ∈ `ProfileSource` values or `None`, and `(profile is None) == (profile_source is None)` when the key is present. Keep the dict copy (never return the input object). Update `ActorField` docs and `_STRUCTURED_ACTOR_FIELDS` comment. Type stays `dict[str, str | None]`.
- If `ProfileSource` import into `models.py` would create a cycle (`actor.py` imports `models`), define the allowed values tuple in `models.py` and have `ProfileSource` assert parity in a test, or define `ProfileSource` in `models.py` and re-export from `actor.py`. Pick one authority and test it.

### Subtask T008 – `actor_full_identity` [P]

- `src/specify_cli/status/models.py:255`. For a dict actor, blank the profile part when `actor.get("profile_source") == "wp_frontmatter"`. Strings and dicts without the key: unchanged. Docstring: one sentence citing the operator decision (frontmatter is planned, not proven).

### Subtask T009 – Binding provenance

- `src/specify_cli/status/resolved_binding.py`: add `profile_source: str | None = None` to the frozen dataclass; **exclude** it from `to_delta` and from any equality/serialization the reducer reads (check `to_delta`, `from_*` helpers and `test_resolved_binding_*` tests).
- `workflow.py::_resolve_dispatch_binding`: set `profile_source="invocation"` when `invocation_id` resolved the profile, `"flag"` when only `--profile` was given, `None` when `resolved_profile is None`.
- Run `tests/specify_cli/status/test_resolved_binding_*.py` and `tests/specify_cli/status/test_verdict_keeps_review_binding_6630.py`.

### Subtask T010 – Delegation and exports

- `status/emit.py:1366-1450`: `build_resolved_actor(role, tool, binding, self_profile, self_model)` and `build_self_asserting_actor(role, agent, fallback_tool, binding)` keep their signatures (callers in WP03/WP04 files still use them until wired) but gain an optional keyword `planned_profile: str | None = None` and return the 5-key dict built by `actor.build_status_actor` (or `actor.resolve_profile` for `build_resolved_actor`, mapping `self_profile` to `agent_string`). Existing callers therefore start emitting `profile_source` on the transitions they already structure — that is intended; update the docstrings.
- Check `emit_resolved_binding` (`ResolvedBindingEmit.structured_actor`) uses the delegate.
- Export `ProfileSource`, `role_for_hop`, `build_status_actor`, `planned_profile_for_wp` from `specify_cli/status/__init__.py` (follow its lazy/explicit export style and `__all__`).
- Run tests that assert the old 4-key structured actor and update the expected dicts to include `profile_source` where they were asserting the structured actor's exact value: `tests/status/test_emit.py`, `tests/status/test_actor_boundary_normalize.py`, `tests/specify_cli/status/test_resolved_binding_fanout.py`, `tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py`, `tests/contract/test_mission_status_payloads.py`. These are outside `owned_files`; editing an expected value there is a justified out-of-map edit — list each file in a history note. Do not weaken an assertion; only add the new key with its correct value.

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_status_actor.py -q
uv run --frozen pytest tests/status tests/specify_cli/status tests/unit/status -q -p no:randomly
uv run --frozen pytest tests/contract/test_mission_status_payloads.py tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py -q
uv run --frozen ruff check <touched files>; uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/specify_cli/status/actor.py src/specify_cli/status/models.py src/specify_cli/status/resolved_binding.py src/specify_cli/status/emit.py
```

## Risks & Mitigations

- Read API projection (`contracts/mission-status`): `Actor.yaml` copies `tool/role/profile` field by field; an extra stored key is ignored. Run `tests/contract/` mission-status tests to prove it.
- Reducer: the snapshot actor slot uses `actor_identity_str` (tool) — unchanged.

## Review Guidance

- Red-first commit precedes implementation.
- `decode_actor` refuses 6-key and malformed dicts; legacy identities unchanged.
- No frontmatter read inside `_resolve_dispatch_binding`.
- One builder: no other module assembles a `{tool, role, profile, ...}` dict literal (grep `"role":` in `src/specify_cli/status` and `cli/commands/agent`).

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP02 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T005 --status done`.
