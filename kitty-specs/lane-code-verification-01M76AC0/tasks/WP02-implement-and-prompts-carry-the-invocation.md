---
work_package_id: WP02
title: Implement and prompts carry the invocation
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-005
- NFR-002
- SC-001
- SC-003
planning_base_branch: fix/7547-lane-code-verification
merge_target_branch: fix/7547-lane-code-verification
branch_strategy: Planning artifacts for this mission were generated on fix/7547-lane-code-verification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7547-lane-code-verification unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Surfaces
history:
- at: '2026-11-12T05:35:56Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/lane_test_invocation.py
create_intent:
- src/specify_cli/review/lane_test_invocation.py
- tests/agent/test_implement_lane_invocation.py
- tests/review/test_lane_test_invocation_adapter.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/lane_test_invocation.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/agent/test_implement_lane_invocation.py
- tests/agent/test_build_implement_prompt_lines.py
- tests/review/test_lane_test_invocation_adapter.py
- tests/specify_cli/cli/commands/test_implement_characterization.py
- tests/specify_cli/cli/commands/test_implement_phases.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Implement and prompts carry the invocation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement` and read `CLAUDE.md` and `.kittify/charter/charter.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`).
- Address every item; record progress with `spec-kitty agent tasks add-history WP02 --mission lane-code-verification-01M76AC0 --note "..."`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

- `spec-kitty implement WP## --json` returns a new key `lane_test_invocation` (shape in
  `contracts/lane-test-invocation.md`, probe included); every existing key unchanged.
- The human output prints a "Lane test invocation" block beside the existing FR-006
  `export` block: `cd`, `unset …`, `export …`, the declared command (or "no
  review.test_command configured"), and the probe line (`probe: verified — pkg → src/pkg/…`,
  or `foreign`/`unverified` with the reason, printed as a warning for `foreign`).
- `spec-kitty agent action implement` and `… review` prompts contain the same block for
  lane-backed and write-checkout work packages (re-derived and re-probed at render time,
  never read from a stored copy).
- Planning-lane workspaces (`lane_id is None`): key is `null`, no block.
- Requirements: FR-001, FR-005, NFR-002, SC-001, SC-003.

## Context & Constraints

- Read `plan.md` §Design and `research.md` (squad dispositions A6/T9: the invocation is
  never persisted; `WorkspaceContext` is NOT changed; `implement_support.py` is NOT touched
  — open PR #7562 edits it).
- One adapter, one authority for the command: create
  `src/specify_cli/review/lane_test_invocation.py` with
  `lane_test_invocation_for(root: Path, *, config_root: Path, mission_slug: str | None, lane_id: str | None, probe: bool = True) -> LaneTestInvocation`:
  reads the template through `review.baseline._get_test_command(config_root)` (the single
  `review.test_command` authority, C-002; first check
  `tests/architectural/test_cli_error_surface_seam.py` ~L137 and
  `tests/architectural/_baselines.yaml` ~L370, which pin raw-read sites of that function — if
  a new caller trips them, route through `DeclaredCommandScopeSource` or reuse an existing
  sanctioned reader instead of growing a baseline), builds with WP01's
  `build_lane_test_invocation`, and (when `probe`) attaches `probe_lane_imports(...)`.
  `config_root` is the repository root checkout (the config authority, as the gate's
  `_mt_config_authority_root` does), never the lane. WP04 reuses this adapter.
- Complexity: `build_implement_prompt_lines` is at 9 and the banner is near its limit; add
  the block through one extracted renderer `render_lane_test_invocation_lines(invocation) -> list[str]`
  (in the adapter module, so implement banner and prompts share wording) and call it.
- Terminology: "repository root checkout", "lane", "Mission"; no `feature`.

## Branch Strategy

- **Planning base branch**: `fix/7547-lane-code-verification` · **Merge target branch**: `fix/7547-lane-code-verification`
- Worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T006 – Red tests through the implement CLI and prompt builders (commit first)

- **Files**: `tests/agent/test_implement_lane_invocation.py` (new; `tests/agent` is in the
  CI matrix, unlike `tests/specify_cli/cli/commands/`), `tests/review/test_lane_test_invocation_adapter.py` (new),
  edits in `tests/agent/test_build_implement_prompt_lines.py`.
- **Planted-change test (SC-001)**: reuse the implement harness of
  `tests/specify_cli/cli/commands/test_implement_characterization.py` (~L255
  `implement_cli`, real git + worktree, ≈1.4 s; import its fixtures or factor a tiny local
  copy — do not edit that file for this). Seed the project with
  `src/pkg/__init__.py` (`V = 1`), a `review.test_command` in `.kittify/config.yaml`, and a
  `root/.venv` built with `python -m venv --without-pip` plus a `.pth` → `root/src`; put
  `root/.venv/bin` first on `PATH` (monkeypatch). Run `implement WP01 --json`; assert the
  `lane_test_invocation` key exists, `probe.status == "verified"`, `cwd` is the lane.
  Plant `V = 2` in the lane; start a child **with the JSON's cwd and environment**
  (`base env − env_unset + env_set`) that prints `pkg.V` and spawns a grandchild doing the
  same → `2` and `2`. Same fixture: the root venv interpreter with the inherited env from
  the lane prints `1`.
- **JSON shape**: assert all pre-existing keys still present with the same values (NFR-002).
- **Planning lane**: key is `None`.
- **Prompts (SC-003)**: unit-test `build_implement_prompt_lines` and
  `build_review_prompt_lines` with a lane `ResolvedWorkspace` → the rendered text contains
  the invocation's cwd, command and probe status; a planning-lane workspace renders no
  block. Then one end-to-end check through `workflow.app` implement + review using the
  harness in `tests/agent/test_workflow_review_lane_gate.py` (~L122-160,
  `_prompt_path_from_output`): same lane path and status in both prompts (status will be
  `unverified` there because that harness fakes `.git`; that is fine — assert presence).
- **Adapter**: `review.test_command` unset → `command is None`, probe still attached.

### Subtask T007 – The adapter module

- Implement `lane_test_invocation_for` and `render_lane_test_invocation_lines` as above.
  `__all__` both. The renderer outputs plain strings (no Rich markup), e.g.:

```
🧪 LANE TEST INVOCATION (run tests exactly like this):
   cd <cwd>
   unset PYTHONPATH UV_PROJECT_ENVIRONMENT VIRTUAL_ENV
   export SPEC_KITTY_TEST_DB_NAME=…
   export PYTHONPATH=<cwd>/src
   <command>            # or: (no review.test_command configured)
   probe: verified — pkg → src/pkg/__init__.py
```

  For `foreign`: `probe: FOREIGN — pkg loads from <origin>, outside this lane. Fix the
  lane's environment before trusting any test result.` For `unverified`: `probe:
  unverified — <reason>`. Paths shown relative to `cwd` when inside it.

### Subtask T008 – `implement` JSON and banner; goldens

- `cli/commands/implement.py`: in the JSON payload builder (~L231-249) add
  `"lane_test_invocation": invocation.to_dict() if invocation else None`; in
  `_print_workspace_ready_banner` (~L269-316) print the renderer's lines for the lane and
  `single_branch` write-checkout branches (not planning). Build the invocation once per
  command and pass it to both (avoid two probes). Use `result.workspace_path`/lane id and
  the resolved mission slug.
- Update the two exact-shape goldens, each gaining only the new key, as part of the red
  commit (they go red first): `tests/specify_cli/cli/commands/test_implement_characterization.py`
  (~L1039-1051) and `tests/specify_cli/cli/commands/test_implement_phases.py` (~L286-299).
  If a `SimpleNamespace`/`MagicMock` result reaches the builder in those tests, make the
  payload code tolerate it the way `lane_test_env` already does (getattr + isinstance).

### Subtask T009 – Prompt blocks

- In `workflow_executor.py`, append `render_lane_test_invocation_lines(...)` after the
  `📍 WORKING DIRECTORY` block in both builders when `workspace.lane_id` is a real lane or
  the workspace is a write checkout; build the invocation from `workspace.worktree_path`,
  `mission_slug`, `workspace.lane_id`, `config_root=repo_root` (check which root is the
  repository root checkout in each builder — `main_repo_root` in review).
- Replace the review prompt's bare "Read code, run tests, check against requirements" hint
  line only if needed; keep existing lines otherwise (parity/snapshot tests).
- Guard the whole block: an exception from the adapter must not break prompt rendering —
  render `probe: unverified — <error>` instead (fail-open, mirrors the topology block).

## Test Strategy

```bash
uv run --frozen python -m pytest tests/agent/test_implement_lane_invocation.py tests/agent/test_build_implement_prompt_lines.py tests/review/test_lane_test_invocation_adapter.py tests/agent/test_workflow_review_lane_gate.py -q
# out-of-matrix (nightly-only) dirs: run and record counts
uv run --frozen python -m pytest tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/test_implement_phases.py tests/specify_cli/cli/commands/test_implement_writeside.py -q
uv run --frozen python -m pytest tests/architectural/test_trio_seam_only.py tests/architectural/test_commit_recipe_strings.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_execution_context_parity.py tests/architectural/test_cli_error_surface_seam.py -q
uv run --frozen ruff check <changed files>; uv run --frozen ruff format --check --force-exclude <changed files>; uv run --frozen mypy <changed src files>
```

## Risks & Mitigations

- Probe cost on every prompt render: 5 s cap, typically ~0.1 s.
- `implement.py` has high churn (53 commits / 90 days): keep hunks small.
- Gate on raw config reads (`test_cli_error_surface_seam.py`): resolve as described above,
  never by adding an allowlist entry.

## Review Guidance

- Planted-change test: verify both the positive (lane, `2`) and negative (root, `1`) runs
  use the same fixture, and that a grandchild process is covered.
- `implement --json`: every old key unchanged (diff the golden).
- No change to `implement_support.py`, `workspace/context.py` or the allocator.

## Activity Log

- 2026-11-12T05:35:56Z – system – Prompt generated via /spec-kitty.tasks
