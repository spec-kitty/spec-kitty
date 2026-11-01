---
work_package_id: WP01
title: Scoped load, lazy lineage, sole-door accessor
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-007
- C-001
- C-002
- C-003
- NFR-004
- SC-004
planning_base_branch: issue-6917-sentinel-scoped-profile-read
merge_target_branch: issue-6917-sentinel-scoped-profile-read
branch_strategy: Planning artifacts for this mission were generated on issue-6917-sentinel-scoped-profile-read. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6917-sentinel-scoped-profile-read unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Charter layer scoped sentinel read
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/
create_intent:
- tests/charter/test_agent_profile_scoped_load.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/charter/offering/agent_profiles/repository.py
- src/charter/offering/service.py
- src/charter/activation/resolver.py
- src/charter/activation/active_charter_service_builder.py
- tests/charter/test_agent_profile_scoped_load.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Scoped load, lazy lineage, sole-door accessor

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- `AgentProfileRepository` accepts an opt-in, keyword-only `only_ids` scope that loads only the
  documents able to supply those ids, through the repository's existing pipeline.
- The shipped lineage graph is parsed on first lineage use, not in the constructor (#6462 restored).
- `CharterOfferingService.agent_profile_sentinels(ids)`, `ActiveCharterService.agent_profile_sentinels(ids)`
  and `build_agent_profile_sentinels(repo_root, ids)` exist and agree with the full repository.
- A two-id lookup parses at most three shipped profile documents and no lineage graph.
- The four sole-door architectural gates stay green with zero new exclusions.
- The default (`only_ids=None`) load is byte-identical to `main`.

## Context & Constraints

- Read first: `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/spec.md`,
  `research.md` (decisions D1–D4), `data-model.md`, `contracts/agent-profile-sentinels.md`.
- Charter rules that bind this WP: single canonical authority (one parser, no raw-YAML reader),
  architectural alignment (construction stays in exempt files), ATDD-first (red test first).
- `sentinel` is structural: no activation key may gate it. That is why the light builder skips
  `PackContext`; keep the config-read fail-closed behaviour that the layer resolution performs.
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: run targeted suites, not the full matrix.

## Branch Strategy

- **Strategy**: feature-branch (single_branch mission)
- **Planning base branch**: `issue-6917-sentinel-scoped-profile-read`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T001 – Red-first scoped-loader parity test

- **Purpose**: pin the contract before the implementation exists.
- **Steps**: create `tests/charter/test_agent_profile_scoped_load.py` with:
  1. parity over the shipped catalogue: for every id in `packs/built-in/agent_profiles/*.agent.yaml`,
     the scoped answer equals `AgentProfileRepository(...).get(id).sentinel`;
  2. a project overlay of `human-in-charge` that only extends the description keeps `sentinel` true,
     while one declaring `sentinel: false` flips it (same fixture, both assertions);
  3. a language-scoped profile is absent from the scoped mapping exactly as `get()` returns `None`
     under the same `active_languages`;
  4. an unknown id is absent, and the default unscoped load still returns the full catalogue.
- **Files**: `tests/charter/test_agent_profile_scoped_load.py` (new).
- **Notes**: use `tmp_path` pack fixtures; do not touch the real `packs/` tree. Mark the module
  `pytest.mark.fast` (and `charter`/`corpus` where the existing profile tests do).

### T002 – `only_ids` scope in `AgentProfileRepository`

- **Purpose**: one opt-in scope on the existing loader instead of a second profile reader.
- **Steps**: add keyword-only `only_ids: Collection[str] | None = None`; normalise to a frozenset of
  non-empty strings; in `_load_layer`, when scoped, restrict the scan to files whose name is
  `<profile-id>.agent.yaml` for a requested id (built-in layer too, so overlay merges still find the
  base). Document: default `None` = unchanged; the scope is for read-only single-field lookups; ids
  resolve by the file convention. Do not change `_parse_profile_from_file`, `_merge_profiles`, the
  skip diagnostics or the language filter.
- **Files**: `src/charter/offering/agent_profiles/repository.py`.
- **Notes**: the built-in layer must load the requested ids even when only an org/project file names
  them, otherwise an overlay that omits `sentinel` would fail validation instead of inheriting.

### T003 – Lazy lineage graph

- **Purpose**: a profile-map reader must not parse the 358-node shipped DRG (0.54 s measured).
- **Steps**: restore `self._drg: DRGGraph | None = drg` plus a `_graph()` accessor that builds on
  first use; route `_lineage_parent`, the `graph` property and `profile_channel_reached` through it.
  An explicit `drg=` stays authoritative; the `DRGLoadError` empty-graph degradation moves inside
  the accessor with its docstring rationale (cite #6462). Add to the test module a case proving a
  scoped load and a plain `get()`/`list_all()` never call `load_built_in_graph`, while a lineage call
  does.
- **Files**: `src/charter/offering/agent_profiles/repository.py`,
  `tests/charter/test_agent_profile_scoped_load.py`.

### T004 – Offering-service accessor

- **Purpose**: let the offering layer answer the scoped question from the same layer directories it
  already derives.
- **Steps**: add `CharterOfferingService.agent_profile_sentinels(self, profile_ids: Iterable[str]) -> dict[str, bool]`:
  build a scoped `AgentProfileRepository` with the same `org_dirs`/`project_dir`/`active_languages`
  it uses for `agent_profiles` (honouring `_agent_profile_overlay_dir`), then return
  `{pid: bool(profile and profile.sentinel)}` for the distinct non-empty ids. Do not cache it in
  `_cache` (ids vary per caller).
- **Files**: `src/charter/offering/service.py`.

### T005 – Sole-door accessor and light builder

- **Purpose**: give `specify_cli` exactly one sanctioned, cheap entry point.
- **Steps**: add `ActiveCharterService.agent_profile_sentinels(ids)` in
  `src/charter/activation/resolver.py` delegating to `self._inner.agent_profile_sentinels(ids)`, with
  a docstring recording the pinned semantics (structural, not activation-gated; extends the FR-001
  accessor contract; the surface decision from `contracts/agent-profile-sentinels.md`). Add
  `build_agent_profile_sentinels(repo_root, profile_ids)` to
  `src/charter/activation/active_charter_service_builder.py`: resolve project/org roots via the same
  helpers, build the inner service through `_build_offering_service` (the one raw-service
  construction site), and return the mapping **without** `PackContext`.
- **Files**: `src/charter/activation/resolver.py`,
  `src/charter/activation/active_charter_service_builder.py`.

## Test Strategy

```bash
uv run pytest tests/charter/test_agent_profile_scoped_load.py -q
uv run pytest tests/charter_offering/test_human_in_charge_profile.py -q
uv run pytest tests/architectural/test_charter_sole_door_agent_profile_repository.py \
              tests/architectural/test_charter_sole_door_offering_service.py \
              tests/architectural/test_charter_sole_door_inner_reacharound.py \
              tests/architectural/test_charter_sole_door_resolver_imports.py -q
uv run ruff check src/charter tests/charter/test_agent_profile_scoped_load.py
uv run mypy src/charter/offering/agent_profiles/repository.py src/charter/activation/resolver.py
```

Type discipline: `charter/offering` is mypy-checked in CI; keep annotations complete (no new
`Any` leaks) and run the project's configured mypy invocation for the touched modules.

## Risks & Mitigations

- **Scope leaking into the default load** → explicit test that the unscoped load is unchanged.
- **Overlay merge losing the built-in base** → built-in layer is scoped to the same ids.
- **Gate 1/2 census** → every new construction stays in exempt files; run the gates.
- **Nothing outside the class may read `._drg`** → `grep -rn '\._drg\b' src tests`.

## Review Guidance

- Confirm no second profile reader/parser was added and that the default path is untouched.
- Confirm the accessor never consults `PackContext`.
- Confirm the lazy graph keeps an explicit `drg=` authoritative and does not change lineage results.

## Progress & Status

Start by running `spec-kitty agent action implement WP01 --agent pi:deepseek-v4.1-flash-1017:python-pedro`
from the repository root, and record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.
