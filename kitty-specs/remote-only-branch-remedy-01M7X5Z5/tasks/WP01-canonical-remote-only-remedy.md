---
work_package_id: WP01
title: Canonical remote-only remedy
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-002
- C-004
- C-005
- SC-001
- SC-003
planning_base_branch: issue-5287-remote-only-coord-remedy
merge_target_branch: issue-5287-remote-only-coord-remedy
branch_strategy: Planning artifacts for this mission were generated on issue-5287-remote-only-coord-remedy. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5287-remote-only-coord-remedy unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-11-20T19:14:47Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- src/mission_runtime/coord_remedy.py
- tests/mission_runtime/test_coord_remedy.py
- tests/specify_cli/coordination/test_remote_only_remedy_5287.py
execution_mode: code_change
model: ''
owned_files:
- src/mission_runtime/coord_remedy.py
- src/mission_runtime/write_target_degrade.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- tests/mission_runtime/test_coord_remedy.py
- tests/specify_cli/coordination/test_remote_only_remedy_5287.py
- tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py
- tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
- tests/specify_cli/cli/commands/test_doctor_coordination.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Canonical remote-only remedy

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

One builder, in `src/mission_runtime/coord_remedy.py`, composes the canonical remote-only remedy. The three surfaces that print a remote-only remedy today use it and print the identical steps:

1. `CoordinationWorktreeUnmaterialized._compose_next_step` (remote arm), `src/specify_cli/coordination/surface_resolver.py:357-417` — relayed by ~20 commands including `spec-kitty materialize`.
2. `_coord_worktree_missing_remote_only_steps`, `src/specify_cli/cli/commands/_coordination_doctor.py:511-535` (used by the `COORDINATION_WORKTREE_MISSING` finding and the `--fix` warning).
3. The remote-only refusal in `assert_coord_write_materialized`, `src/mission_runtime/write_target_degrade.py:~276-292`.

Done when: FR-001..FR-005 hold, SC-001 and SC-003 are measured by tests, all touched tests are green, and `test_layer_rules.py` is green with no ledger growth.

## Context & Constraints

- Spec: `kitty-specs/remote-only-branch-remedy-01M7X5Z5/spec.md`; plan, research, data model alongside.
- Operator default (binding): one canonical form — `git fetch <remote> <b>` then `git branch <b> <remote>/<b>`, then `spec-kitty doctor coordination --mission <slug> --fix`; skip the fetch line when the tracking ref exists; RESOLVED remote, never hard-coded `origin`; remove "has not fetched".
- Layering: `mission_runtime` may import `kernel`; it must NOT import `specify_cli` in the new module. `specify_cli` imports the builder downward. Do not touch `tests/architectural/test_layer_rules.py`'s ledger.
- No network (ADR 2026-10-06-3): use only `kernel.git.remote.resolve_remote`, `tracking_ref`, `configured_remotes`, and local `rev-parse` (via `kernel.git`'s runner). Never `ls-remote`/`fetch`.
- Out of scope: `coordination/policy.py::_missing_destination_remedy` (#7726), the status read door (WP02), #5936, #7449.
- Terminology: no "sync"; say "remote-only branch".
- `src/mission_runtime/` is not under the `__all__` rule (that binds `src/charter/` and `src/kernel/`), but declare `__all__` anyway for clarity.

## Branch Strategy

- **Strategy**: single_branch (settled at finalize)
- **Planning base branch**: issue-5287-remote-only-coord-remedy
- **Merge target branch**: issue-5287-remote-only-coord-remedy
- Execution workspace comes from `lanes.json`; run `spec-kitty agent action implement WP01 --agent claude --mission remote-only-branch-remedy-01M7X5Z5`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first ATDD for R3

**Purpose**: pin the user-observable truth before any code.

**Steps**: create `tests/specify_cli/coordination/test_remote_only_remedy_5287.py`. Build `make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="absent", remote_only=True)` (its only remote is named `coord-remote` and the tracking ref `refs/remotes/coord-remote/<b>` exists). Build the refusal through the pre-existing entry point `CoordinationWorktreeUnmaterialized.for_mission(...)` and assert on `next_step`:
- contains `branch <b> coord-remote/<b>`;
- contains `spec-kitty doctor coordination --mission <slug> --fix`;
- does not contain `has not fetched`, `not yet fetched`, or `origin` as a remote word (check `" origin"` / `"origin/"` absent);
- does not contain a `fetch` step (tracking ref present);
- a second case deletes `refs/remotes/coord-remote/<b>` (`git update-ref -d`) and asserts a `fetch coord-remote <b>` step precedes the `branch` step. Note: once the tracking ref is gone, `_coord_branch_exists` may reach the remote lookup; the fixture's bare remote is local, so that still answers HIT.

Mark the module `pytestmark = pytest.mark.fast` only if the file's sibling tests use markers that way; check `tests/specify_cli/coordination/` conventions first. Commit this test alone first (it must be red on the base).

### Subtask T002 – Builder module

**Purpose**: the single owner of the text (FR-001/2/3).

**API** (see `data-model.md`):

```python
@dataclass(frozen=True)
class RemoteOnlyBranch:
    branch: str
    remote: str | None
    tracking_ref_present: bool
    remotes: tuple[str, ...]

def remote_only_branch(repo_root: Path, branch: str) -> RemoteOnlyBranch: ...
def remote_only_steps(facts: RemoteOnlyBranch, repo_root: Path, follow_up: str) -> str: ...
def coordination_doctor_command(mission_slug: str) -> str: ...  # "spec-kitty doctor coordination --mission <slug> --fix"
```

- `remote_only_branch`: `remote = resolve_remote(repo_root, branch)`; `remotes = tuple(configured_remotes(repo_root))`; `present(r)` = `git rev-parse --verify --quiet refs/remotes/<r>/<branch>` exits 0 (use `kernel.git`'s `run_git(..., check=False)`; read its signature first). If `remote` is set and `present(remote)` → done. Else if exactly one configured remote `r` has `present(r)` → use it with `tracking_ref_present=True`. Else keep `remote` (may be None) with `tracking_ref_present=False`. Any `OSError`/git failure → treat as not present (the text then includes the fetch step, which is always safe).
- `remote_only_steps`: renders exactly
  `Run in order: `git -C <root> fetch <remote> <b>`, then `git -C <root> branch <b> <remote>/<b>`, then `<follow_up>`.`
  dropping the first clause (and its trailing ", then ") when `tracking_ref_present`. When `remote is None`, render the literal `<remote>` and append ` (<remote> is one of: a, b)` — or ` (no remote is configured; add one with `git remote add <name> <url>`)` when `remotes` is empty.
- Unit tests in `tests/mission_runtime/test_coord_remedy.py`: pure-render cases (tracking present/absent, ambiguous with/without remotes) need no git; resolution cases use small `git init` repos with `git remote add` and `git update-ref refs/remotes/<r>/<b> HEAD`: one remote not named origin; origin among several; several without origin and no tracking ref (None); resolved remote lacks tracking ref but another remote has it.

### Subtask T003 – Unmaterialized refusal → builder

In `_compose_next_step`, replace the remote arm's hand-written text (lines ~394-405) with a short lead sentence plus the builder steps, e.g.:
`The coordination branch '<b>' declared in meta.json exists only on a remote: this checkout has no local branch for it, so its coordination worktree cannot be materialized. <steps> Keep the `coordination_branch` key in meta.json as-is — the branch is not lost.`
Keep the local-head arm unchanged. Update the docstring (#5287). Import the builder lazily or at module top (check for import cycles: `mission_runtime` imports `specify_cli` lazily in places; the new module must not).

### Subtask T004 – Doctor → builder

`_coord_worktree_missing_remote_only_steps(repo_root, mission_slug, coord_branch)` keeps its name and signature and returns `remote_only_steps(remote_only_branch(repo_root, coord_branch), repo_root, coordination_doctor_command(mission_slug))`. Update the docstring (it currently says the write-degrade site cannot share it — now both share the builder).

### Subtask T005 – Write refusal → builder

In `write_target_degrade.py`, the remote-only `ActionContextError` message keeps its lead ("Refusing a terminus WRITE … (#4970).") and its error code, and replaces the hand-written "`git fetch`, create the local branch …" sentence with "Materialize the coordination surface first. " + builder steps + "; or check out <b> locally before retrying." Keep the existing error code constant.

### Subtask T006 – Parity + re-pins

- Parity test (in `test_remote_only_remedy_5287.py`): on the same fixture, the doctor finding's `next_step` (`_check_coordination_worktree_health`), the refusal's `next_step`, and the write refusal's message all contain the identical builder string `remote_only_steps(remote_only_branch(root, b), root, coordination_doctor_command(slug))`. Find how `test_coordination_remedy_5113.py` drives the write refusal and the doctor finding and reuse that path.
- Re-pin (judge each test, do not blindly rewrite): `tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py:221,261` assert `git fetch origin <b>`; `tests/specify_cli/cli/commands/test_coordination_remedy_5113.py:352,443,519` split the branch step; `tests/specify_cli/cli/commands/test_doctor_coordination.py:850` asserts `branch <b> origin/<b>`. These fixtures use `origin`, so most keep holding with the `-C <root>` form; update only what the new canonical text genuinely changes and keep the intent of each assertion.

## Test Strategy

Run (record counts):
```bash
.venv/bin/python -m pytest tests/mission_runtime/test_coord_remedy.py tests/specify_cli/coordination/test_remote_only_remedy_5287.py tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py tests/specify_cli/cli/commands/test_coordination_remedy_5113.py tests/specify_cli/cli/commands/test_doctor_coordination.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_materialize.py tests/mission_runtime/test_write_target_degrade_selfmat.py tests/coordination/test_materialize_coord_surface.py -q -n auto --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_remote_contact_owner.py -q
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched> && uv run --frozen mypy <touched src>
```

## Definition of Done

- T001 committed red first, then green.
- One builder; no remote-only remedy text left hand-written in the three sites; no `has not fetched`; no hard-coded `origin` in those remedies.
- Tests and gates above green; ruff/format/mypy clean.

## Risks

- Import cycle when `surface_resolver` imports `mission_runtime.coord_remedy` at module top: import lazily inside `_compose_next_step` if needed.
- `-C <root>` in texts changes substrings older tests match.

## Reviewer Guidance

Verify T001 was red on the base; check the parity test compares against the builder output, not a copied literal; confirm `coord_remedy.py` imports only stdlib + `kernel`.
