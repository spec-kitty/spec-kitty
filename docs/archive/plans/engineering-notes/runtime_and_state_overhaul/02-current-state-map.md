---
title: '02 — Current-State Map: How Execution Context Is Derived Today'
description: 'Current-state map (2026-06-03): a read-only code survey of how execution context is derived today in the rc35 tree, describing what exists not what should be.'
doc_status: deprecated
updated: '2026-06-03'
---
# 02 — Current-State Map: How Execution Context Is Derived Today

Source: read-only code survey of the rc35 working tree (2026-06-03). All `path:line` are
point-in-time. This document describes *what exists*, not *what should be*.

---

## The two resolvers that already exist (and disagree by responsibility)

Spec Kitty already has **two independent half-context resolvers**, one for reads and one for writes.
Neither is the single authority #1619 asks for; each re-derives the same identity tuple from
`meta.json`.

### Read-side: `resolve_mission_read_path` — `src/specify_cli/missions/_read_path_resolver.py:94`

Pure-path, topology-aware. Priority:
1. **Coord worktree** (`:141-148`): built only when `mid8` truthy, via
   `CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8) / "kitty-specs" / <slug>-<mid8>`. Returned if it exists.
2. **Primary checkout** (`:154-164`): `repo_root / "kitty-specs" / <dir>`, with a **fail-closed
   guard** (`:156-163`) — if a coord candidate was computable AND primary `meta.json` declares a
   `coordination_branch`, it raises `StatusReadPathNotFound` rather than return stale primary status.

Covers reads only. Does **not** cover write paths, `target_branch`, `coordination_branch`, `destination_ref`, or prompt source.

Thin wrapper consumed by the workflow command: `_canonical_status_feature_dir()` —
`src/specify_cli/cli/commands/agent/workflow.py:229` (derives `mid8` from primary `meta.json`, delegates to the resolver).

### Write-side: `BookkeepingTransaction` — `src/specify_cli/coordination/transaction.py:503`

The single chokepoint for coordination-branch **writes**. `acquire()` (`:573`):
- Normalises `destination_ref`, acquires the feature-status lock **before** worktree resolution (`:601-607`).
- `_acquire_locked()` (`:630`) branches on `_is_legacy_mission` (`:670`): legacy → resolve the
  operator's current **lane** worktree and override `destination_ref` with the lane HEAD branch
  (`:673-682`); modern → `CoordinationWorkspace.resolve()` (`:686`).
- Computes `feature_dir` + status paths **inside** the resolved worktree (`:695-702`).
- `commit()` (`:903`) commits all staged paths via `safe_commit(repo_root, worktree_root, destination_ref, …)` (`:929-935`), rolling back the event log + every `write_artifact` path on failure.

Invoked **only** via `emit_status_transition_transactional` / `DecisionGitLog` — **not** by raw `append_event`.

### The coordination topology primitive: `CoordinationWorkspace` — `src/specify_cli/coordination/workspace.py:113`

Stateless static methods; identity passed per call:
- `worktree_path()` (`:127`) → `repo_root / ".worktrees" / f"{<slug>-<mid8>}-coord"`
- `branch_name()` (`:132`) → `f"kitty/mission-{<slug>-<mid8>}"`
- `resolve()` (`:136`) → creates worktree on first call; raises `CoordinationWorkspaceBranchMismatch` (`:38`) on wrong-branch checkout; never auto-recovers.
- Sparse-exclusion (`:215-298`): `lane_sparse_checkout_patterns()` excludes `status.events.jsonl` + `status.json` so lanes **physically cannot** write the event log.

---

## The status subsystem (`src/specify_cli/status/`)

Public API in `__init__.py`. Core modules: `models.py` (`Lane`, `StatusEvent`, `TransitionRequest:343`,
`GuardContext:377`), `transitions.py` (`ALLOWED_TRANSITIONS`, `validate_transition`,
`resolve_lane_alias`), `reducer.py` (`reduce`, `materialize`), `store.py`, `emit.py`.

**Critical property:** `store.append_event()` (`:188`) and `read_events()` (`:421`) operate on
**whatever `feature_dir` they are handed** — zero topology awareness. *The caller's `feature_dir`
IS the authority decision.* This is the mechanical reason split authority is possible at all.

**Transactional emit:** `coordination/status_transition.py::emit_status_transition_transactional` (`:378`):
- `_identity_for_request()` (`:105`) canonicalizes `feature_dir`, derives `repo_root`, reads
  `coordination_branch`/`mission_id`/`mid8` from `load_meta(feature_dir)`, sets
  `destination_ref = coord_branch or _current_branch(repo_root)` (`:142`).
- `_transaction_topology_available()` (`:86`) chooses coord vs primary. If **false** → falls back to
  non-transactional `emit.emit_status_transition` which writes the **primary checkout** `feature_dir`.
- If **true** → `BookkeepingTransaction.acquire(...)` and append into `txn.feature_dir` (coord).

This is the **only** place read-vs-write divergence is reconciled internally — and only for writes.
`TransitionRequest` already carries a partial context bag (`feature_dir`, `mission_dir`,
`mission_slug`, `_legacy_mission_slug`, `repo_root`) but it is **write-only and not reused by readers**.

---

## Split-authority surfaces (per-surface derivation)

Legend: ✅ coord-aware (post-#1627) · ⚠️ raw primary / independently derived · 🔁 parallel hand-rolled resolver

| Surface | Site | Derivation | State |
|---------|------|------------|-------|
| `implement.py` dependency gate | `:749-758` | `_resolve_read_path(...)` → `reduce(read_events(...))` | ✅ (#1627 WP02) |
| `implement.py` general `feature_dir` | `:726` | raw `repo_root/"kitty-specs"/mission_slug` (used `:770,828,900,940`) | ⚠️ |
| `implement.py` commit destination | `:739` → `_status_commit_destination_branch():55` | `get_current_branch(repo_root)` — **not coord-aware** | ⚠️ |
| `workflow.py` review/claim canonical reads | `:1977,1193` | `_canonical_status_feature_dir(...)` | ✅ (#1627 WP01) |
| `workflow.py` prompt strings | `:787-793,1549-1552,1955` | corrected text | ✅ (#1627 WP01) |
| `workflow.py` review-feedback / fix-mode | `:1205` | raw `main_repo_root/"kitty-specs"/mission_slug` | ⚠️ |
| `workflow.py` dossier sync / tasks glob / sub-artifact | `:1346,1690,1707,1866,1869,2207,2341,2378,2463` | raw primary | ⚠️ |
| `workflow.py` `find_wp_file` / claimable preview | `:152-154,949` | raw primary WP-file lookup | ⚠️ |
| `runtime_bridge.py` `decide_next` | `:2242-2249` | `_resolve_read_path(...)` | ✅ (#1627 WP03) |
| `runtime_bridge.py` decision-log wrapper | `:72,90,108,121,150-167` | raw `meta.json` reads; coord `worktree_root`; `destination_ref=coord` | ✅ worktree_root (#1627 WP03), but ⚠️ re-derives meta independently |
| `runtime_bridge.py` query-mode / answer-decision | `:1924,2917,3048-3049` | raw `repo_root/"kitty-specs"/mission_slug` | ⚠️ |
| `orchestrator_api/commands.py` `_resolve_mission_dir` | `:237-257` | `resolve_mission_read_path(...)` | ✅ (#1627 WP02) |
| `orchestrator_api/commands.py` worktree paths | `:418,714` | `main_repo_root/".worktrees"/f"{slug}-{lane}"` — **legacy naming, no mid8** | ⚠️ |
| `events/decision_log.py` decisions file | `:86-88` | `worktree_root/"kitty-specs"/mission_slug/...` — **bare slug, no mid8**; correctness depends on caller | ⚠️ |
| `agent/tasks.py` move-task emit | `:1970,1986-2057` | raw `feature_dir` passed to transactional emit (redirect happens inside txn) | ⚠️ (relies on txn) |
| `agent/tasks.py` coord events path | `:768-783` | `_coord_status_events_path()` — **second parallel coord resolver** for the #1618 skip | 🔁 |
| `agent/tasks.py` status read | `:3819` | `resolve_mission_read_path(...)` w/ legacy fallback `:3829` | ✅ (#1627) |
| `agent/tasks.py` other reads | `:854,908,982,1183,2755,2966,2972,3134,3428,3701,4269` | raw primary | ⚠️ |
| `agent/status.py` materialize/show/emit/lifecycle | `:137,211,319,326,338,783` | raw `main_repo_root/"kitty-specs"/mission_slug` | ⚠️ **NOT touched by #1627** |
| `git/commit_helpers.py` `safe_commit` | `:858-865` | leaf primitive; derives nothing; head-mismatch guard | (correct by design) |

---

## Post-#1627 residue (surfaces still independently deriving context)

These would each need to consume a unified context object:

1. **`agent/status.py`** — raw primary read+materialize at `:137,211,319,326,338,783`. Reads
   stale/empty status for modern missions. **Strongest single residue candidate.**
2. **`runtime_bridge.py` query-mode / answer-decision** — `:1924,2917,3048-3049` raw (only `decide_next` was fixed).
3. **`runtime_bridge.py` decision-log meta reads** — `:78,96,110` re-derive coord branch / ULID / topology independently.
4. **`workflow.py` review-feedback / fix-mode / dossier / sub-artifact** — `:1205,1346,1690,1707,1866,1869,2207,2341,2378,2463` raw primary interleaved with coord-aware reads in the *same* functions.
5. **`workflow.py` WP-file lookup / claimable preview** — `:152-154,949`.
6. **`tasks.py` non-status reads** — `:854,908,982,1183,1732,1970,2755,2966,2972,3134,3428,3701,4269`.
7. **`implement.py`** general feature_dir + independent commit-destination picker.
8. **`orchestrator_api`** legacy worktree naming (`:418,714`).
9. **`decision_log.py`** bare-slug decisions dir.
10. Various other commands with raw `repo_root/"kitty-specs"` reads outside #1627 scope: `next_cmd.py`, `merge.py`, `mission_type.py`, `retrospect.py`, `verify.py`, `materialize.py`, `doctor.py`, `charter/*`, `agent/mission.py`.

**`Path.cwd()` mission-state entry points** (each independently locates root, then derives raw dirs):
`tasks.py:1715,1798,3784`, `status.py:199,307`, `commit_helpers.py` callers via `_resolve_feature_dir:123`, `orchestrator_api:229`, `workflow.py:1112`.

**Duplicated coord-path logic** — at least four hand-rolled copies of `_compose_mission_dir` / coord
path building: `workspace.py:68`, `_read_path_resolver.py:79`, `tasks.py:777`, `status_transition.py:82`.
Plus two parallel coord resolvers: `tasks.py:_coord_status_events_path:768` and
`runtime_bridge._resolve_coordination_branch:72`.

---

## What a `MissionExecutionContext` must absorb (field → current computing site)

| Field | Currently computed by |
|-------|----------------------|
| `primary_root` | `find_repo_root()` / `get_main_repo_root()` — `implement.py:576,716`, `workflow.py:1945`, `status.py:308,313`, `tasks.py:3785`, `orchestrator_api:225-233` |
| `current_cwd` | `Path.cwd().resolve()` — `workflow.py:1112`, `tasks.py:1715,3784`, `status.py:199,307`, `orchestrator_api:229` |
| `mission_slug` | `detect_feature_context()` / `_find_mission_slug()` / `require_explicit_feature` — `implement.py:577`, `workflow.py:1950`, `tasks.py:3791`, `status.py:316`, `execution_context.py:87` |
| `mission_id` (ULID) | `meta.json["mission_id"]` via `_identity_for_request:127`, `_resolve_mission_ulid:90`, `resolve_mission_identity` (`orchestrator_api:262`) |
| `mid8` | `mid8_from_slug(slug)` — `execution_context.py:92`, `implement.py:752`, `tasks.py:774,3814`, `decision.py:403`, `runtime_bridge.py:149`, `orchestrator_api:250`; or meta-derived; or `_mid8_for_mission_read_path` (`workflow.py:232`) |
| `target_branch` | `get_feature_target_branch` (`execution_context.py:238`), `resolve_feature_target_branch`/`resolve_target_branch` (`workflow.py:169,851`, `implement.py:737`), `_resolve_merge_target_branch` (`orchestrator_api:311`) |
| `coordination_branch` | `meta.json["coordination_branch"]` via `_identity_for_request:123`, `_resolve_coordination_branch:72`, `_declares_coordination_branch` (`_read_path_resolver.py:67`), `CoordinationWorkspace.branch_name:132` |
| `coord_worktree` | `CoordinationWorkspace.worktree_path:127` / `.resolve:136`; duplicated in `_read_path_resolver.py:143`, `tasks.py:780`, `runtime_bridge.py:150` |
| `execution_workspace` | `resolve_workspace_for_wp()` (`execution_context.py:281`, `workflow.py:1988`); raw `.worktrees/<slug>-<lane>` in `orchestrator_api:418,714` |
| `status_read_dir` | `resolve_mission_read_path` / `_canonical_status_feature_dir` (coord-aware) — many sites; **bypassed by raw primary at all residue sites** |
| `status_write_dir` | `BookkeepingTransaction.txn.feature_dir` chosen in `_acquire_locked:695-702`, gated by `_transaction_topology_available:86`; fallback writes primary |
| `destination_ref` | `_identity_for_request:142`, legacy override `transaction.py:680-681`, `_status_commit_destination_branch` (`implement.py:55`), `DecisionGitLog._destination_ref` |
| `allowed_command_cwd` | implicit — `resolve_workspace_for_wp().worktree_path`, `_ensure_target_branch_checked_out` main_root; **not a first-class value anywhere** |
| `prompt_source_dir` | **not centrally derived** — `find_wp_file:152`, `repo_root/"kitty-specs"/slug/"tasks"` (`workflow.py:1707,1866,1869`), runtime template via `_runtime_template_key`/`_workflow_runtime_template` (`runtime_bridge.py:2033-2036`) |

### Mechanical conclusion

The read resolver and the write resolver **already independently re-derive the same identity tuple**
(`repo_root, mission_slug, mid8, coord branch, coord worktree`) from `meta.json`, via ≥4 duplicated
path-builders. A context object would compute this identity **once** and expose `status_read_dir`,
`status_write_dir`, `destination_ref`, `coord_worktree`, `target_branch` as derived properties. The
fields with **no first-class home today** — `allowed_command_cwd` and `prompt_source_dir` — are the
ones most directly responsible for "agents reconcile manually" and "prompts contradict topology".
