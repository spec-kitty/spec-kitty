---
work_package_id: WP05
title: S1 read door and declared sources
dependencies:
- WP01
- WP04
requirement_refs:
- FR-001
- FR-003
- FR-061
- NFR-001
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 2 - S1 one status read contract
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/read_surface.py
- tests/status/test_read_surface_door.py
- tests/specify_cli/cli/commands/agent/test_context_resolve_primary_partition.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/read_surface.py
- src/specify_cli/coordination/surface_resolver.py
- tests/status/test_read_surface_door.py
- tests/specify_cli/cli/commands/agent/test_context_resolve_primary_partition.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 - S1 read door and declared sources

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP05 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

One entry point `resolve_status_read(repo_root, mission, *, owned=None) -> StatusReadSurface` with a declared source per topology (FR-001, FR-003, FR-061, NFR-001):

- `WRITE_CHECKOUT` for `single_branch`, `lanes` and provisional Missions;
- `COORD_WORKTREE` for `coord` / `lanes_with_coord` with a materialized coordination worktree;
- `COORD_BRANCH_REF` when that worktree is empty or unmaterialized;
- the declared pre-seed `WRITE_CHECKOUT` fallback (with `fallback_reason`) when the coordination branch exists but has no log yet;
- `CoordinationBranchDeleted` when the branch is gone;
- `CONSOLIDATED_TARGET` once consolidated.

Acceptance (User Story 1 scenario 1): a coordination Mission whose coordination worktree is absent reports its 3 committed events, never an empty history or the repository root checkout's copy. A ref-sourced read spawns at most one git object-read subprocess per Mission per command (NFR-001). FR-061: `spec-kitty agent context resolve --json` (`mission_dir`) and `check-prerequisites --paths-only` report the PRIMARY-partition location.

## Context & Constraints

- Read: WP01 ADR `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`; `research.md` R-1, R-2, R-6 (PRIMARY placement); `data-model.md` §2 (exact value-object shapes and invariants); spec FR-001 to FR-004, FR-061.
- Builds on WP04: the normalization helper (`canonical_status_read_root`) and the typed ref reader (`RefRead`, `StatusSurfaceRefUnreadable`) in `coordination/status_service.py`. Reuse them; do not add a second reader.
- The write side already reads the ref in the unmaterialized state (`status_transition._read_contract_from_transaction_target`); align with it.
- `_empty_coord_surface`'s loud repository-root fallback is removed (reversal recorded by WP01; it was `coord-artifact-single-home-01M3V4BE#FR-017`/`#C-002`).
- Layering: `src/specify_cli/status/` is adapter layer; `mission_runtime` stays inside its outbound ledger and gets no new `specify_cli` import. Respect `tests/architectural/test_cold_import_status_boundary.py` (function-local imports where needed).
- FR-061 placement: the read door returns the topic branch location for PRIMARY reads of a `topology_source: default` Mission (via `meta.mission_branch`). The write-side placement arm in `mission_runtime/resolution.py` is WP14's (sequenced after WP06); here you only read. If `agent context resolve` / `check-prerequisites` compute `mission_dir` elsewhere, route them through the door or the placement seam with a minimal out-of-map hunk and record it.
- Red-first (C-011): tests committed before implementation.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T024 - Red-first acceptance tests

In `tests/status/test_read_surface_door.py` (real git fixtures via `tests/integration/coord_topology_fixture.py`):

- `test_unmaterialized_coord_reads_branch_events`: `lanes_with_coord`, 3 committed coordination events, a stale write-checkout copy, coordination worktree removed -> 3 events, `source == COORD_BRANCH_REF`.
- `test_empty_coord_worktree_reads_branch`: worktree present but empty -> branch events.
- `test_preseed_window_declares_write_checkout_source`: branch exists, no log -> `WRITE_CHECKOUT` with non-empty `fallback_reason`.
- `test_owned_checkout_unmaterialized_reads_ref_not_raises`.
- `test_ref_read_spawns_one_subprocess` (NFR-001): count `subprocess` invocations of `git cat-file` with a monkeypatched runner.
- `test_never_returns_nonexistent_path`: across the WP04 matrix cells, `surface.path` is None or exists, and is never inside a registered lane checkout.

In `tests/specify_cli/cli/commands/agent/test_context_resolve_primary_partition.py` (FR-061, orchestrator requirement):

- `test_context_resolve_mission_dir_is_primary_partition_location`: for a `topology_source: default` Mission held on its topic branch, `spec-kitty agent context resolve --action tasks --mission <h> --json` reports `mission_dir` at the PRIMARY-partition location (the write checkout on the topic branch), and `spec-kitty agent mission check-prerequisites --json --paths-only --mission <h>` agrees.
- Positive control: an explicit `--topology lanes_with_coord` Mission reports today's location (`target_branch` placement).
- Note: the post-settlement case (root checkout back on `create_return_branch`) is pinned in WP14; mark that variant `xfail(strict=True, reason="WP14 settlement")` only if you add it here, otherwise leave it to WP14.

Flip the WP04 matrix cells marked `# changes in WP05 (FR-003)` in the same red-first commit.

### Subtask T025 - Value objects

- New `src/specify_cli/status/read_surface.py`: `StatusReadSource(StrEnum)` and frozen `StatusReadSurface` exactly as in data-model §2 (`topology`, `source`, `mission_dir_name`, `path`, `repo_root`, `ref`, `fallback_reason`). Validate invariants in `__post_init__` (exactly one of `path`/`ref`; `fallback_reason` only with a coordination topology and `WRITE_CHECKOUT`).

### Subtask T026 - Source selection

- `resolve_status_read(repo_root, mission, *, owned=None)`: normalize the root (WP04 helper); read stored topology and `topology_source` from `meta.json`; classify the coordination state (materialized / empty / unmaterialized / deleted) with the existing resolver probes; pick the source per the table above; consolidated Missions -> `CONSOLIDATED_TARGET`.
- Keep each function <= 15 complexity: one classifier per axis, one mapping table.

### Subtask T027 - Batched ref reader and read functions

- `read_status_events(surface)`, `read_status_stream(surface)`, `materialize_status(surface)` (read only; writers stay on the write seam).
- `COORD_BRANCH_REF`: one `git cat-file --batch` subprocess per Mission per command, fed `refs/heads/<coord>:kitty-specs/<dir>/status.events.jsonl` (and `status.json` if needed in the same batch). ABSENT -> empty; any failure -> `StatusSurfaceRefUnreadable`.
- No new dependency (R-12).

### Subtask T028 - Resolver delegates; drop the loud fallback

- `coordination/surface_resolver.py`: `resolve_status_surface_with_anchor` delegates to the door (returns the path form for existing callers until WP06/WP07 migrate them); remove `_empty_coord_surface`'s repository-root fallback.
- Update docstrings to say the door is canonical.

### Subtask T029 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/status/test_read_surface_door.py tests/status/test_status_read_matrix.py tests/specify_cli/cli/commands/agent/test_context_resolve_primary_partition.py -q
uv run --frozen pytest tests/status tests/coordination tests/mission_runtime tests/specify_cli/status -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "context or prerequisites"   # out-of-matrix dir: run it here
uv run --frozen pytest tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_read_surface_placement_guard.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict src/specify_cli/status/read_surface.py src/specify_cli/coordination/surface_resolver.py
```

Complexity <= 15; no new suppressions; never `make test-full` or a bare `tests/architectural/` sweep. If a standing gate goes red because it blesses the old body, do NOT edit it here: that amendment is WP07's. Record the red in your summary.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP05] ...**`, naming `traces/tooling-friction.md`, `traces/approach.md` or `traces/design-decisions.md`); the orchestrator appends them.

## Risks & Mitigations

- Standing gates naming `resolve_status_surface_with_anchor` as canonical may fail: coordinate with WP07; keep the old function as a delegating shim until then.
- Subprocess count regressions: the NFR-001 test guards it.

## Review Guidance

- One door, declared sources, invariants enforced; one subprocess per ref read; FR-061 resolver-path tests present with positive control; red-first ordering visible in history.

## Definition of Done

- T024-T029 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T024 T025 T026 T027 T028 T029 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP05 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
