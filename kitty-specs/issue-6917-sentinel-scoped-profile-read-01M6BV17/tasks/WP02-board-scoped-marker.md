---
work_package_id: WP02
title: Board reads only the profiles it names
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6917-sentinel-scoped-profile-read
merge_target_branch: issue-6917-sentinel-scoped-profile-read
branch_strategy: Planning artifacts for this mission were generated on issue-6917-sentinel-scoped-profile-read. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6917-sentinel-scoped-profile-read unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Board wiring
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/charter/test_tasks_status_sentinel_scope_6917.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/cli/commands/agent/tasks_status_cmd.py
- tests/charter/test_tasks_status_sentinel_scope_6917.py
- tests/charter_offering/test_human_in_charge_profile.py
- tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Board reads only the profiles it names

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (implementer) before starting.

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in `spec-kitty agent tasks status` and resolve any feedback first.

## Objectives & Success Criteria

- A board render performs at most one agent-profile read, for the distinct ids its rows name.
- The 👤 marker text is identical to `main` for every row that shows it today.
- The census test fails on unmodified `src` (26 shipped profile documents parsed) and passes here
  (≤ 3 for a two-profile board; 0 for an empty board).
- Activation deny/narrowing parity holds; unknown/empty ids stay markerless and error-free;
  a malformed `.kittify/config.yaml` still fails closed.

## Context & Constraints

- Read first: WP01's code (`build_agent_profile_sentinels`), `contracts/agent-profile-sentinels.md`,
  `spec.md` acceptance scenarios.
- `_get_hic_marker` keeps its name and its `tasks.py` re-export: `tests/specify_cli/cli/commands/agent/test_tasks_status_cmd_seam.py`
  patches it by name and eight production call sites pass the lookup in.
- No behaviour change for a row with a falsy/`None`/non-`str` `agent_profile`.

## Branch Strategy

- **Strategy**: feature-branch (single_branch mission)
- **Planning base branch**: `issue-6917-sentinel-scoped-profile-read`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T006 – Red-first census and marker acceptance test

- **Purpose**: prove the issue is solved, through the production entry point.
- **Steps**: create `tests/charter/test_tasks_status_sentinel_scope_6917.py`:
  1. **Census**: instrument agent-profile parsing (wrap `charter.offering.agent_profiles.repository.parse_shipped_yaml`
     and `ruamel.yaml.YAML.load`-based project-layer reads, or count via a monkeypatched loader seam)
     while invoking the real `agent tasks status` command (`CliRunner`) on a `tmp_path` project whose
     mission has two claimed WPs (`human-in-charge` and a normal profile). Assert the count is ≤ the
     number of distinct ids and specifically < 26; assert the board text still contains `👤 `.
  2. **Positive control**: the same fixture through the full `AgentProfileRepository` parses the whole
     catalogue — proving the counter can see documents when they are parsed.
  3. **Empty board**: nothing claimed ⇒ zero profile documents parsed.
  4. **Unknown id**: a row naming a profile no layer ships renders without marker and without error.
- **Files**: `tests/charter/test_tasks_status_sentinel_scope_6917.py` (new).
- **Notes**: build the fixture project with `.kittify/config.yaml`, a charter pack with the two
  profiles, and a mission with two work-package files; follow existing CLI-invocation fixtures in
  `tests/specify_cli/cli/commands/agent/`.

### T007 – One scoped lookup per render

- **Purpose**: remove the service + catalogue build from the render.
- **Steps**: in `tasks_status_cmd.py`, replace the `profile_repo: ProfileLookup | None` plumbing with a
  `Mapping[str, bool]` (or `None`) built once in `_st_render_human` from the distinct non-empty
  `agent_profile` ids across `by_lane`; use `build_agent_profile_sentinels(_st_config_root(st), ids)`
  inside the existing lazy guard (`_needs_profile_lookup`). Change `_get_hic_marker` to take
  `sentinels: Mapping[str, bool] | None = None`, keep the self-resolving fallback (one scoped call
  for that single id), and update the eight call sites to pass the mapping. Delete the now-unused
  `ProfileLookup` alias and rewrite the long comment blocks to the new rationale (structural read,
  no activation service, no catalogue), citing #6917.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_status_cmd.py`.
- **Notes**: keep the `except ImportError` narrow degrade, and keep every other exception
  propagating to `_do_status` for the structured error path (NFR-003).

### T008 – Update the structural-marker ratchets

- **Purpose**: keep deny/narrowing parity tests exercising the production path.
- **Steps**: update `tests/charter_offering/test_human_in_charge_profile.py` (its "pre-built repo"
  case becomes a pre-built mapping/accessor case; drop the repository-parameter shape it no longer
  covers) and `tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py` where it calls
  `_get_hic_marker`. Keep the assertions identical in intent: 👤 survives a deny entry and a narrowed
  `activated_agent_profiles`; non-sentinel and unknown ids render nothing.
- **Files**: `tests/charter_offering/test_human_in_charge_profile.py`,
  `tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py`.

### T009 – Empty-board and unknown-id proof

- **Purpose**: keep the historical degrade semantics.
- **Steps**: cover in T006's module: empty board (no read at all), unknown id (no marker, no raise),
  and a malformed `.kittify/config.yaml` still producing the structured `status_failed` error rather
  than a markerless board.
- **Files**: `tests/charter/test_tasks_status_sentinel_scope_6917.py`.

## Test Strategy

```bash
uv run pytest tests/charter/test_tasks_status_sentinel_scope_6917.py -q
uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_status_cmd_seam.py -q
uv run pytest tests/specify_cli/charter_runtime/test_cli_readers_honour_deny.py \
              tests/charter_offering/test_human_in_charge_profile.py -q
uv run ruff check src/specify_cli/cli/commands/agent/tasks_status_cmd.py
uv run mypy src/specify_cli/cli/commands/agent/tasks_status_cmd.py
```

## Risks & Mitigations

- **Census test measuring the wrong thing** → pair it with the positive control on the same fixture
  and assert the marker text in the same run.
- **Marker drift** → deny/narrowing ratchets from T008.
- **Fail-closed regression** → the malformed-config case in T009.

## Review Guidance

- Confirm one read per render, ids taken from the rendered rows only, and no service build.
- Confirm the error contract is unchanged: only `ImportError` degrades.

## Progress & Status

Claim with `spec-kitty agent action implement WP02 --agent pi:deepseek-v4.1-flash-1017:python-pedro`;
record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.
