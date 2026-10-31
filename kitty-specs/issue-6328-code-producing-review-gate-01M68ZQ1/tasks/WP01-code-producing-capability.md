---
work_package_id: WP01
title: The code_producing capability and its public accessor
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-004
- SC-005
planning_base_branch: issue-6328-code-producing-review-gate
merge_target_branch: issue-6328-code-producing-review-gate
branch_strategy: Planning artifacts for this mission were generated on issue-6328-code-producing-review-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6328-code-producing-review-gate unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_code_producing_capability.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/missions/models.py
- src/charter/activation/mission_type_profiles.py
- src/charter/activation/api.py
- tests/charter/test_code_producing_capability.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The `code_producing` capability and its public accessor

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission issue-6328-code-producing-review-gate-01M68ZQ1`) and address every item before handing back.

## Objectives & Success Criteria

Add the `code_producing` capability to a resolved charter-offering mission type, with
one owning built-in default map, one resolver and one public accessor — modelled
exactly on the `requires_substantive_spec` capability that `#6315` already shipped.

This is the `#6327` prerequisite for `#6328`. It is deliberately minimal: the
consumer in WP02 is the only reader. Do not add other consumers, and do not
re-key any other `software-dev` comparison in `src/` (see "Out of scope").

Done means:

- `MissionType` accepts and documents `code_producing: bool | None = None` (FR-001).
- `BUILTIN_CODE_PRODUCING` maps `software-dev → True`, `research`/`documentation`/`plan → False` (FR-002); an undeclared custom type resolves `False` (FR-003).
- `ResolvedMissionType.code_producing` is a memoised lazily-resolved facet, `False` for the neutral bundle (FR-004 / NFR-002).
- `charter.activation.api.code_producing_for(repo_root, mission_type) -> bool` exists, is in both `__all__`s, and never raises (FR-005 / NFR-001).
- There is exactly one built-in list; nothing anywhere else enumerates code-producing types (NFR-004).

## Context

**Spec**: `kitty-specs/issue-6328-code-producing-review-gate-01M68ZQ1/spec.md` (FR-001..FR-005, NFR-001, NFR-002, NFR-004, SC-005).
**Plan**: same directory, plan.md § "Design / D1" and the IC-01 concern.
**Data model**: same directory, data-model.md — the tri-state rule and the precedence chain are normative.

Read these three existing implementations before writing anything; they are the
pattern to copy, not to reinvent:

1. `src/charter/offering/missions/models.py` — the `MissionType` model and the
   `requires_substantive_spec: bool | None = None` field with its docstring
   paragraph. The model is `ConfigDict(frozen=True, extra="forbid")`.
2. `src/charter/activation/mission_type_profiles.py` — `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`,
   the `_requires_substantive_spec_thunk` field, the `requires_substantive_spec`
   `cached_property`, `_resolve_requires_substantive_spec`, and
   `requires_substantive_spec_for`.
3. `src/charter/activation/api.py` — the public re-export list (`__all__` around
   line 301) and the import block around line 53.

## Detailed guidance per subtask

### T001 — Write the failing tests first

Create `tests/charter/test_code_producing_capability.py`. It must fail before T002-T004.
Cover, at minimum:

- **Built-in defaults (FR-002)**: parametrised over
  `[("software-dev", True), ("research", False), ("documentation", False), ("plan", False)]`,
  assert both `resolve_mission_type_context(repo, mission_type=mt).code_producing`
  and `code_producing_for(repo, mt)`.
- **Declared value wins (FR-001 / FR-003)**: a custom org-layer type declaring
  `code_producing: true` resolves `True`, one declaring `false` resolves `False`,
  and one declaring nothing resolves `False`. Use the fixture pattern from
  `tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py`
  (`test_resume_probe_custom_type_requiring_substantive_spec_fails_thin_spec`):
  build an org pack dir with `mission_types/<id>.yaml` plus
  `missions/<id>/mission-runtime.yaml`, patch
  `charter.activation.mission_type_profiles.existing_mission_types` and
  `charter.activation.pack_context.PackContext.from_config`, and
  `resolve_layered_mission_types.cache_clear()` in a `finally`. That test is the
  exact precedent; mirror its shape rather than inventing a new harness.
- **Neutral bundle (FR-004)**: the typeless bundle's `code_producing` is `False`
  and does not raise.
- **Resolution failure (NFR-001)**: with the resolver patched to raise,
  `code_producing_for(repo, "software-dev")` returns `True` and
  `code_producing_for(repo, "qa")` returns `False` — i.e. it falls back to the
  built-in map and never propagates the exception.
- **Laziness (NFR-002)**: with
  `charter.activation.mission_type_profiles.resolve_layered_mission_types` wrapped
  in a counting spy, reading only `action_sequence` from
  `resolve_mission_type_context(...)` performs no additional call, while reading
  `.code_producing` performs exactly the deferred one (and a second read performs
  none, because it is memoised).

Do not weaken an existing test to make this fit. If the counting spy turns out to be
impractical because the roster is already memoised on `resolve_layered_mission_types`
itself, say so in the WP review hand-off and prove laziness the practical way
(construct the bundle, assert `_code_producing_thunk is not None`, read twice,
assert the thunk fired once via a small counter on a hand-built bundle). Record
whichever route you took in the PR body.

### T002 — The DTO field (FR-001)

In `src/charter/offering/missions/models.py`:

```python
    code_producing: bool | None = None
```

placed immediately after `requires_substantive_spec`, plus a docstring paragraph in
`MissionType`'s "Fields" section in the same voice as the neighbouring
`requires_substantive_spec` paragraph: what it means, that `None` means undeclared
and defers to `BUILTIN_CODE_PRODUCING` in `charter.activation.mission_type_profiles`,
and that the default for an undeclared custom type is the conservative `False`.

Do **not** add a validator: `bool | None` is already enforced by pydantic, and a
"must be bool" validator would duplicate the type.

### T003 — The map, the facet and the resolver (FR-002 / FR-003 / FR-004)

In `src/charter/activation/mission_type_profiles.py`:

1. `BUILTIN_CODE_PRODUCING: Mapping[str, bool] = MappingProxyType({...})` directly
   below `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`, with the same leading comment shape
   ("Built-in defaults for the … capability. A type's own declared value wins; a
   custom type that declares nothing is conservatively `False`."). Use the
   `MISSION_TYPE_*` constants? **No** — the sibling map uses bare string literals
   and this map lives in the `charter.*` package which does not import
   `specify_cli.core.constants`. Match the sibling exactly (bare literals); that
   keeps one style in the file.
2. On `ResolvedMissionType`: a `_code_producing_thunk: Callable[[], bool] | None`
   field (same `field(default=None, repr=False, compare=False)` shape and the same
   "Deferred resolver for …" comment) and:

   ```python
   @cached_property
   def code_producing(self) -> bool:
       """Authored capability (lazy, memoised; see :data:`BUILTIN_CODE_PRODUCING`)."""
       if self._code_producing_thunk is None:
           return False
       return self._code_producing_thunk()
   ```

3. `_resolve_code_producing(mission_type, *, is_registered, pack_context) -> bool` —
   a near-exact copy of `_resolve_requires_substantive_spec`: declared value from
   `resolve_layered_mission_types(dirs, pack_context).get(mission_type)`, else
   `BUILTIN_CODE_PRODUCING.get(mission_type, False)`.
4. Populate `_code_producing_thunk=lambda: _resolve_code_producing(type_key, is_registered=is_registered, pack_context=pack_context)`
   at the single `ResolvedMissionType(...)` construction site, beside
   `_requires_substantive_spec_thunk`.
5. Do **not** touch `_neutral_context()`'s signature; the `None` thunk already
   yields `False`.

### T004 — The public accessor (FR-005)

In the same module:

```python
def code_producing_for(repo_root: Path, mission_type: str) -> bool:
    """Public: whether *mission_type* produces committed code (resolve + fallback)."""
```

Copy `requires_substantive_spec_for`'s structure and its comment about the
resolve-then-built-in-fallback contract. The `except Exception` breadth and the
`# noqa: BLE001` are deliberate and must be copied, not narrowed: a probe must not
crash. Update the module `__all__` (both the private and the public accessor, in the
same order the sibling pair appears).

Then in `src/charter/activation/api.py`: import `code_producing_for` beside
`requires_substantive_spec_for` (line ~53) and add `"code_producing_for"` to
`__all__` (line ~301). Keep the alphabetical/positional placement the file already
uses.

### T005 — Laziness proof (NFR-002)

Whichever route T001 settled on, make sure the suite contains an assertion that a
caller reading only `action_sequence` does not pay for the capability, and that a
repeated `.code_producing` read is memoised.

### T006 — Resolution-failure proof (NFR-001)

The fallback test from T001: patch `resolve_mission_type_context` (as imported in
`mission_type_profiles`) to raise, and assert `code_producing_for` returns the
built-in default instead of raising. This is the contract the consumer in WP02
relies on; it is not optional.

## Out of scope — do not do these

- Do **not** change `_validate_ready_for_review` or anything under `specify_cli/` —
  that is WP02, and doing it here would make WP02's red-first proof impossible.
- Do **not** re-key `src/runtime/next/runtime_bridge_io.py`'s template-tier order or
  `src/runtime/next/runtime_bridge.py`'s step-graph guard; those are separate
  `#6315` follow-ups.
- Do **not** author `code_producing:` into any built-in YAML mission-type descriptor.
  The built-in defaults live in the map; setting it in YAML as well would create the
  second source of truth NFR-004 forbids.
- Do **not** touch `src/specify_cli/lanes/for_review_gate.py` or the `single_branch`
  gates (`#6715` / `#5939`).

## Test strategy

```bash
uv run pytest tests/charter/test_code_producing_capability.py -v
uv run pytest tests/charter/ -q            # no regression in the neighbours
uv run ruff check src/charter tests/charter
uv run ruff format --check src/charter tests/charter
uv run mypy src/charter/activation/mission_type_profiles.py src/charter/offering/missions/models.py
```

The narrow mypy config may report the `charter.*` graph as skipped; that is
expected — record the actual output rather than claiming a clean run you did not
get.

## Definition of Done

- [ ] The new test file fails before the implementation and passes after, with the
      red run captured in the hand-off (command + first failure line).
- [ ] All six subtasks land inside the `owned_files` list. If you must touch a file
      outside it, stop and record a one-line rationale in the hand-off instead of
      silently widening.
- [ ] `code_producing_for` is reachable as `charter.activation.api.code_producing_for`
      and appears in both `__all__`s.
- [ ] No new eager read on the `action_sequence` hot path; the facet is a
      `cached_property` behind a thunk.
- [ ] No second list of code-producing types anywhere.
- [ ] `ruff check` and `ruff format --check` clean on the touched paths.
- [ ] The `#6715`/`#5939` gate modules are untouched.

## Risks & reviewer guidance

- **The tri-state is load-bearing.** Collapsing `None` to `False` in the DTO loses
  the ability for the built-in map to supply `True` for `software-dev`; a reviewer
  should reject any attempt to give the field a `False` default.
- **`extra="forbid"` on `MissionType`.** The field must be declared before any test
  YAML sets it, otherwise pydantic raises at load. This is intended fail-loud
  behaviour, not a bug to work around.
- **Laziness.** The single most likely regression is accidentally reading the roster
  during construction. Reviewer: check that `_resolve_code_producing` is only ever
  reached through the thunk.
- **Do not narrow the `except Exception`.** It mirrors the shipped sibling and the
  WP02 consumer's fail-safe behaviour depends on it.
