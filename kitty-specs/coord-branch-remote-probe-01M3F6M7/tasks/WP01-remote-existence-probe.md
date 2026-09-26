---
work_package_id: WP01
title: Remote-existence probe + shared tri-state remote-lookup primitive (#4979)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- NFR-001
- NFR-002
- C-001
- C-002
planning_base_branch: issue-4979-coord-branch-remote-probe
merge_target_branch: issue-4979-coord-branch-remote-probe
branch_strategy: Planning artifacts for this mission were generated on issue-4979-coord-branch-remote-probe. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4979-coord-branch-remote-probe unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-branch-remote-probe-01M3F6M7
base_commit: 4d083c4012c02c586b81bc7e6f1b9602b6b1546e
created_at: '2026-09-26T16:11:22.427557+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - remote-existence probe (root)
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/coordination/
create_intent:
- src/specify_cli/git/remote_probes.py
- tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py
- tests/specify_cli/git/test_remote_probes.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/git/remote_probes.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/cli/commands/mission_type.py
- tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py
- tests/specify_cli/git/test_remote_probes.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4979'
---

# Work Package Prompt: WP01 — Remote-existence probe + shared primitive

## ⚡ Do This First: Load Agent Profile

Use the `/spk-doctrine-profile-load` (or `/ad-hoc-profile-load`) skill to load the agent
profile in the frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` and run
`spec-kitty charter context --action implement --json`.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Fix issue **#4979** at its source: the single canonical branch-existence probe
`_coord_branch_exists` (`src/specify_cli/coordination/surface_resolver.py:548`) decides
"coordination branch never-created/deleted" from only the local head plus already-fetched
`refs/remotes/*` refs (the #2614 residual). On a `git clone --single-branch -b main`,
`--depth 1` CI checkout, or a pruned-origin clone, neither ref exists though the branch lives
on origin, so the probe reports "absent" — driving the coord read-path refusal, the doctor
`COORDINATION_WORKTREE_NEVER_CREATED` finding, and (via WP03) the flatten propagation.

- **SC-001 (#4979, FR-001):** `_coord_branch_exists` returns `True` for a coordination branch
  present only on a remote. Proven RED-first (T001): in a single-branch clone whose origin
  holds `kitty/mission-<slug>`, the OLD probe returns `False` (→ `status emit` refused with
  the deleted-branch error / doctor emits NEVER_CREATED); the NEW probe returns `True`.
- **SC (FR-003) tri-state:** `git ls-remote --heads` outcomes are discriminated:
  MATCH ⇒ present; reachable CLEAN-MISS (exit 0, empty) across all remotes ⇒ absent;
  ERROR/TIMEOUT/OSError ⇒ fail-closed present; **ZERO remotes configured ⇒ retain local
  authority (missing local head ⇒ absent)** — the origin-less DELETED tests
  (`tests/specify_cli/coordination/test_coord_never_created.py`,
  `tests/specify_cli/migration/test_backfill_topology.py` T007) stay GREEN.
- **SC (FR-002):** a branch gone from every reachable remote AND locally still reports absent
  (genuine-deletion/flatten path preserved).
- **SC (NFR-001):** the ls-remote round-trip runs ONLY after the `_roots_own_checkout` guard,
  the local-head check, and the `refs/remotes/` scan all miss; a regression pins "no ls-remote
  when refs/remotes hits". The lookup is **memoized per-process** keyed `(repo_root, branch)`
  (single-branch/CI coord reads never materialize the worktree, so the probe would otherwise
  fire the network on every coord read in one invocation).
- **SC (NFR-002):** the network call passes a bounded `timeout=` (~5s), catches
  `subprocess.TimeoutExpired`, and sets `GIT_TERMINAL_PROMPT=0` + SSH `BatchMode` so a
  private-origin credential prompt can never block the CLI.
- **SC (C-001):** ONE shared tri-state primitive is extracted (new
  `src/specify_cli/git/remote_probes.py`, or an existing git-helper module if one fits its
  boundary — confirm first) returning `{HIT, CLEAN_MISS, ERROR, NO_REMOTE}`. Both
  `_coord_branch_exists` (fail-toward-present) AND the existing duplicate `_branch_resolvable`
  (`src/specify_cli/cli/commands/mission_type.py:1292`, fail-toward-false) consume it — no
  third parallel probe. Refactoring `_branch_resolvable` onto it also fixes its missing
  `timeout=` hang.
- **SC (FR-006):** the remote-only guidance branches on local-head vs remote-only —
  `CoordinationBranchDeleted.next_step` (surface_resolver.py:212) and the doctor hint tell a
  remote-only checkout to `git fetch origin <coord_branch>` (or fix `remote.origin.fetch`)
  FIRST, never "flatten" and never a `git worktree add` that fails on an unfetched ref. The
  genuine-deletion guidance is preserved for the truly-absent case.
- **SC (FR-007):** verify the coord READ path for a remote-only branch raises
  `CoordinationWorktreeUnmaterialized` (materialize/fetch recovery) — NOT a silent substitution
  of the empty primary surface (the #4959 clobber class). Trace `_resolve_status_surface_dir`
  (`src/specify_cli/mission_runtime/resolution.py:~1285`) for this site.
- New/changed code: complexity ≤ 15, focused tests for every new branch, ruff + ruff format +
  mypy --strict clean on touched files.

## Context & Constraints

- **C-001 — single canonical primitive.** A second remote probe already ships
  (`_branch_resolvable`). Extract ONE shared tri-state lookup; do not add a third. The idiom to
  lift (enumerate `git remote` → `git ls-remote --heads <remote> <branch>`) is already in
  `mission_type.py:1313-1325` — but it has NO timeout (add it in the shared primitive).
- **C-002 — write-gate strictness (do NOT touch).** `_coord_branch_is_local_head`
  (surface_resolver.py:610) and `coord_branch_has_committed_artifact` (:634) MUST stay
  LOCAL-strict (`refs/heads/` only). A remote-only branch must remain "not a local head" so the
  WRITE self-materialization gate (`mission_runtime/write_target_degrade.py:221`) keeps
  refusing. Prove unchanged via `tests/mission_runtime/test_write_target_degrade_selfmat.py`.
- **Ordering invariant (F7).** The ls-remote probe sits AFTER `_roots_own_checkout` (:570) and
  AFTER the local-head + `refs/remotes/` fast paths (:575-607). Never ls-remote a stranger's
  remotes; full clones pay zero network.
- **Three consumers of `_coord_branch_exists`** all benefit from "remote-only ⇒ present":
  `missions/_read_path_resolver.py:~320` (read → `CoordState.DELETED`),
  `cli/commands/_coordination_doctor.py:~501` (doctor NEVER_CREATED),
  `migration/backfill_topology.py:~220` (skip-flatten). WP01 blast radius MUST include the
  backfill tests.
- ATDD red-first (DIRECTIVE_034/041, C-003/C-011): T001's regression is the first commit,
  RED through the pre-existing entry point (prefer the real CLI `agent status emit` refusal or
  the doctor finding; a direct `_coord_branch_exists` unit assertion is the corroborating
  unit test, not the sole contract). Marked `@pytest.mark.regression` and pinned `#4979`;
  after green it stays as a focused regression (it exercises the real vector).

## Implementation Sketch

1. **T001 (RED):** build a fixture — a coord mission pushed to a bare origin, then a
   `git clone --single-branch -b main` (and a pruned-origin variant) so neither
   `refs/heads/<coord>` nor `refs/remotes/*/<coord>` exists while `git ls-remote origin` lists
   it. Reuse the coord+bare-origin fixture idiom from `tests/terminus/test_repro_4969.py:50` and
   the origin-less builder `_make_git_repo` in `test_coord_never_created.py:50`. Assert the
   deleted-branch path fires (RED). Add the read-path fail-closed assertion (FR-007).
2. **T002:** write the shared primitive (`remote_probes.py`): `remote_branch_lookup(repo_root,
   branch) -> RemoteLookup` enum/dataclass `{HIT, CLEAN_MISS, ERROR, NO_REMOTE}`. Enumerate
   `git remote`; per remote `git ls-remote --heads <remote> <branch>` with `timeout≈5`, env
   `GIT_TERMINAL_PROMPT=0` + `GIT_SSH_COMMAND=ssh -o BatchMode=yes`. Memoize per-process by
   `(repo_root, branch)`. Unit tests for each outcome (`tests/specify_cli/git/test_remote_probes.py`).
3. **T003:** in `_coord_branch_exists`, after the existing fast paths, consult the primitive:
   `HIT|ERROR ⇒ True`, `CLEAN_MISS|NO_REMOTE ⇒ False`. Pin "no ls-remote when refs/remotes hits".
4. **T004:** refactor `_branch_resolvable` onto the primitive (local-head OR `HIT`), fail-toward-false.
5. **T005:** branch the guidance (FR-006); verify FR-007 read-path raise.
6. **T006:** run the blast radius, ruff/format/mypy on touched files, append tracers.

## Validation (targeted test surface — record commands + counts in review)

```
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/coordination/ \
  tests/specify_cli/git/ \
  tests/missions/ \
  tests/specify_cli/migration/test_backfill_topology.py \
  tests/specify_cli/migration/test_backfill_topology_mission_scope.py \
  tests/mission_runtime/test_write_target_degrade_selfmat.py \
  tests/specify_cli/cli/commands/test_mission_type.py -q
.venv/bin/python -m ruff check <touched files> && .venv/bin/python -m ruff format --check <touched files>
.venv/bin/python -m mypy <touched files>
```
Plus `make test-fast` as the baseline. Append findings to `tracers/`.
