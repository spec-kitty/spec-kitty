---
work_package_id: WP01
title: One public builder for the runtime discovery context
dependencies: []
requirement_refs:
- FR-004
- FR-005
- NFR-002
- SC-002
planning_base_branch: issue-6745-workaround-audit-and-removal
merge_target_branch: issue-6745-workaround-audit-and-removal
branch_strategy: Planning artifacts for this mission were generated on issue-6745-workaround-audit-and-removal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6745-workaround-audit-and-removal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-workaround-audit-and-removal-01M68ZKV
base_commit: 600bfb70fa17cbe1b3d99c74c741fa22cfd6e6b4
created_at: '2026-10-31T12:47:46.563879+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Seam consolidation
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-31T12:50:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/specify_cli/mission_loader/command.py
- tests/runtime/test_bridge_io.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6745'
---

# Work Package Prompt: WP01 – One public builder for the runtime discovery context

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Issue #6745, finding **S7** (`research.md` §4): `src/specify_cli/mission_loader/command.py`
keeps a byte-identical copy of the runtime's `DiscoveryContext` constructor, and its own
docstring says why — "the runtime bridge's helper is module-private; we duplicate the
construction here so this module does not depend on a private surface". Mission
`up-org-template-fsm-01M06F9K` then had to wire the org tier into both copies by hand (its
DEC-006 calls them "independently-duplicated production wiring sites"). That is a workaround
for a missing seam, and the cause is fixed by publishing the seam.

Delivered state:

- `runtime.next.runtime_bridge_io.build_discovery_context(repo_root)` is the one public
  builder; the `_`-prefixed copy is gone from the io seam.
- `specify_cli.mission_loader.command` imports it and defines no constructor of its own.
- A patch-point test proves `run_custom_mission` observes the seam (so the test cannot pass
  vacuously while a copy exists elsewhere).

- **FR-004 / FR-005**: one builder, the loader keeps none.
- **NFR-002**: byte-identical context for a repo without org packs (existing tests unchanged).
- **SC-002**: a patch on the seam is observed by `mission run`.

## Context & Constraints

- Read first: `kitty-specs/workaround-audit-and-removal-01M68ZKV/research.md` §4 row S7 and
  §5 decisions D1–D3; `plan.md` IC-01; `.kittify/charter/charter.md` (single canonical
  authority; DIRECTIVE_024 locality of change; DIRECTIVE_041 test only for real behaviour).
- The two constructors today:
  - `src/runtime/next/runtime_bridge_io.py:445-470` (`_build_discovery_context`), called from
    `:648`, `:705`, `:767`, `:815`.
  - `src/specify_cli/mission_loader/command.py:206-235` (`_build_discovery_context`), called
    from `:103`.
- Both build `DiscoveryContext(project_dir=repo_root, builtin_roots=[resolve_builtin_missions_root()],
  org_roots=list(resolve_pack_chain(repo_root, strict=False, quiet=True)))`. They are identical;
  keep that exact expression.
- **Do not wrap `resolve_pack_chain` in a `try/except`**: `OrgPackSubdirEscapeError` and
  `OrgPackEnvVarUnsetError` must propagate (mission `up-org-template-fsm-01M06F9K` DEC-005 /
  NFR-001, pinned by `tests/runtime/test_bridge_io.py::test_build_discovery_context_propagates_org_pack_subdir_escape_error`).
- `DiscoveryContext` must stay imported in `command.py` for the `discovery_context:
  DiscoveryContext | None = None` parameter type.
- `tests/runtime/test_bridge_io.py::_SEAM_OWNED_NAMES` is the non-vacuity pin for the io
  cluster's symbol ownership (`tests/runtime/test_bridge_no_compat_delegates.py` is the paired
  gate). Renaming without updating the list fails that gate loudly — which is correct, so
  update it in the same commit.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-6745-workaround-audit-and-removal`;
  completed changes merge back into it unless the human redirects the landing branch.
- **Planning base branch**: `issue-6745-workaround-audit-and-removal`
- **Merge target branch**: `issue-6745-workaround-audit-and-removal`

## Subtasks & Detailed Guidance

### Subtask T001 – Seam patch-point test, red first

- **Purpose**: prove the copy is gone in a way that cannot pass vacuously.
- **Steps**: In `tests/runtime/test_bridge_io.py`, add a test in the existing "seam
  patch-point" style (section 3 of that module's docstring): patch
  `runtime.next.runtime_bridge_io.build_discovery_context` with a sentinel-returning fake,
  call `specify_cli.mission_loader.command.run_custom_mission(...)` **without**
  `discovery_context=`, and assert the fake ran (and the sentinel reached validation). Also
  assert `not hasattr(command_module, "_build_discovery_context")`.
- **Files**: `tests/runtime/test_bridge_io.py`.
- **Note**: pick the smallest existing fixture in that file (or `tests/integration/test_mission_run_command.py`
  patterns) so the test needs no mission on disk; a validation failure envelope is an
  acceptable terminal state as long as the sentinel context was consumed.

### Subtask T002 – Publish `build_discovery_context`

- **Purpose**: the seam the loader needs.
- **Steps**: rename `_build_discovery_context` to `build_discovery_context` in
  `src/runtime/next/runtime_bridge_io.py`; update its four internal call sites; keep the
  docstring (drop the "module-private" framing; state that `mission run` shares it).
- **Files**: `src/runtime/next/runtime_bridge_io.py`.
- **Do not**: add an alias `_build_discovery_context = build_discovery_context` — a second
  name is the thing this WP removes.

### Subtask T003 – Delete the loader's copy

- **Purpose**: remove the duplicated authority.
- **Steps**: delete `specify_cli/mission_loader/command.py`'s `_build_discovery_context`
  (lines ~206-235); import `build_discovery_context` from `runtime.next.runtime_bridge_io`
  next to the existing `resolve_builtin_missions_root` import; update the two docstring
  references (`:98` "mirroring the runtime bridge", `:102` "defaults to
  :func:`_build_discovery_context`") to name the public seam. Drop imports that become unused
  (`resolve_builtin_missions_root` if only the deleted function used it — check first).
- **Files**: `src/specify_cli/mission_loader/command.py`.

### Subtask T004 – Update seam-owned names and constructor tests

- **Purpose**: keep the non-vacuity pins honest.
- **Steps**: in `tests/runtime/test_bridge_io.py`, replace `_build_discovery_context` with
  `build_discovery_context` in `_SEAM_OWNED_NAMES` and in the four
  `test_build_discovery_context_*` tests. Leave their assertions unchanged: they still prove
  the org tier is populated and errors propagate.
- **Files**: `tests/runtime/test_bridge_io.py`.

### Subtask T005 – Focused verification

- **Steps** (from the repo root, `uv run`):
  - `uv run pytest tests/runtime/test_bridge_io.py tests/runtime/test_bridge_no_compat_delegates.py tests/integration/test_mission_run_command.py -q`
  - `uv run pytest tests/architectural/test_doctrine_census.py tests/architectural/test_runtime_charter_doctrine_boundary.py -q`
  - `uv run ruff check src/runtime/next/runtime_bridge_io.py src/specify_cli/mission_loader/command.py tests/runtime/test_bridge_io.py`
  - `uv run mypy src/runtime/next/runtime_bridge_io.py src/specify_cli/mission_loader/command.py`
- **Never** run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- `grep -rn "_build_discovery_context" src/` returns nothing.
- `grep -rn "DiscoveryContext(" src/` returns only the two documented bare fallbacks
  (`runtime/next/_internal_runtime/discovery.py`, `.../engine.py`), which have no `repo_root`
  and are explicitly out of scope (DEC-006).
- The new patch-point test fails before T002/T003 and passes after.
- Focused suites, ruff and mypy are green; no test deleted.

## Risks & Mitigations

- **Gate coupling**: `_SEAM_OWNED_NAMES` is asserted by a non-vacuity test and mirrored by
  `test_bridge_no_compat_delegates.py`; update both surfaces in one commit.
- **Import cycle**: `command.py` already imports from `runtime.next.runtime_bridge_io`; adding
  one more name does not create a new edge.
- **Behaviour drift**: keep the exact `DiscoveryContext(...)` expression; do not "improve"
  `strict=False, quiet=True` in passing (that would change `mission run` behaviour).

## Reviewer Guidance

- Confirm there is exactly one repo-rooted construction and that the loader consumes the seam.
- Confirm no `try/except` was added around `resolve_pack_chain`.
- Confirm the seam-owned list names the public symbol and that
  `tests/runtime/test_bridge_no_compat_delegates.py` is green.
