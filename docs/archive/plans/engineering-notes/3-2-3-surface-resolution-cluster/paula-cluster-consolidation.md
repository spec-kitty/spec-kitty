---
title: Paula Patterns — 3.2.3 Cluster Investigation
description: Paula Patterns' cluster investigation of the 3.2.3 surface-resolution regressions, naming the recurring duplication shape and the canonical consolidation.
doc_status: deprecated
updated: '2026-06-26'
---
# Paula Patterns — 3.2.3 Cluster Investigation

**Profile applied:** `paula-patterns` (found at `src/doctrine/agent_profiles/built-in/paula-patterns.agent.yaml`)

---

## 0. Issue Summaries (from `gh issue view`)

| # | Title | Root class |
|---|-------|------------|
| 2122 | accept-gate `collect_feature_summary` breaks for mid8 handle | handle-vs-slug at 2 sites |
| 2120 | `close --discard` silently no-ops on coord-topology missions | surface resolver picks coord, not primary, in teardown path |
| 2119 | retrospectives captured only into ephemeral coord branch | `canonical_record_path` → `resolve_feature_dir_for_slug` → coord worktree on coord missions |
| 2112 | `spec-kitty` doesn't see its own config after `init non-interactive-demo-project` | `resolve_canonical_root` / `assert_initialized` sees CWD ≠ initialized git root |
| 2116 | `tasks.py` body-thinning + coord-skip consolidation (#2058 follow-on) | tech-debt, not a surface-resolution bug |

---

## 1. The Handle→Slug + Coord-vs-Primary Surface Resolution Pattern (#2122 class)

### Confirmed buggy sites (handle passed as slug to `resolve_planning_read_dir`)

| Site | File : line | Symptom |
|------|-------------|---------|
| `_wp_tasks_read_dir(repo_root, feature)` → `resolve_planning_read_dir(repo_root, feature, kind=WORK_PACKAGE_TASK)` | `src/specify_cli/acceptance/__init__.py:859` | `feature` may be a bare mid8 handle — `resolve_planning_read_dir` calls `primary_feature_dir_for_mission(repo_root, mission_slug)` which is slug-blind → `kitty-specs/<mid8>/tasks` literal path, never exists → `AcceptanceError` |
| `_planning_read_dir(repo_root, feature)` → `resolve_planning_read_dir(repo_root, feature, kind=kinds[SPEC_FILE])` | `src/specify_cli/acceptance/__init__.py:823` | same: `feature` (the caller-supplied handle) forwarded into the slug-only `primary_feature_dir_for_mission` primitive on the PRIMARY arm |

Both are called from `collect_feature_summary` (`acceptance/__init__.py:1211`) and `normalize_feature_encoding` (`acceptance/__init__.py:613`), which receive a raw `feature` string from the CLI accept gate without first canonicalizing the handle.

The **root cause** is that `resolve_planning_read_dir` on its PRIMARY arm calls `primary_feature_dir_for_mission(repo_root, mission_slug)` (`_read_path_resolver.py:1306`), which is a topology-blind path composition — it does **not** invoke the handle resolver. So a bare mid8 `01ABCDEF` is joined literally as `kitty-specs/01ABCDEF/`, which never exists.

### Other gate-read sites with the same handle-vs-slug risk

`resolve_planning_read_dir` itself does NOT canonicalize the handle before the PRIMARY arm fires. Every caller that passes an operator-facing `--mission <handle>` directly to it is vulnerable:

| Caller | File : line | Passes handle? |
|--------|-------------|----------------|
| `research.py:_plan_dir` | `src/specify_cli/cli/commands/research.py:106,121` | passes `mission_slug` arg from CLI — handle if typed as mid8 |
| `agent/tasks.py` | `src/specify_cli/cli/commands/agent/tasks.py:658, 2501` | passes feature from CLI arg |
| `agent/mission.py:_planning_read_dir` | `src/specify_cli/cli/commands/agent/mission.py:1167` | passes `mission_slug` from CLI arg |
| `tasks_materialization.py` | `src/specify_cli/cli/commands/agent/tasks_materialization.py:105` | passes `feature` from context |

The `agent/mission.py` version adds an important local wrapper (`_planning_read_dir`) that is used at multiple call sites (`:1358`, `:1410`, `:2309`, `:2311`). All of these share the same handle-exposure risk whenever the operator typed a bare mid8 or ULID.

**N+1 site outside the 3 tickets**: `research.py` at lines 106 and 121 passes `mission_slug` (the raw CLI argument) through `resolve_planning_read_dir`. If the operator invokes `spec-kitty research --mission <mid8>`, the planning-dir read silently misses the real directory on the PRIMARY arm.

---

## 2. Teardown / Retrospective Coord-Surface Pattern (#2120 / #2119)

### #2120 — `close --discard` teardown

The bug is at `mission_type.py:595`:
```python
feature_dir = resolve_feature_dir_for_mission(repo_root, mission_slug)
```

`resolve_feature_dir_for_mission` routes through `resolve_action_context(action="tasks")` which is coord-aware — it returns the coordination worktree's mission dir (`.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/`) when the coord worktree is materialized. That dir has **no `meta.json`** (meta lives on primary). So `_read_mission_mid8(meta_path)` returns `""`, and `_teardown_coordination_worktree` early-returns at `if not mid8_value: return`.

The code then re-keys the slug from `feature_dir.name` (line 607) — which extracts the coord worktree's mission dir name, not the primary slug. The `_delete_lane_branches` and `_remove_lane_worktrees` then operate on what they compute to be correct names but the mid8 is `""` so teardown is silent.

**Fix per ticket**: redirect `close_cmd`'s discard path to `primary_feature_dir_for_mission` (the same fix `reopen` already uses at `_resolve_mission_handle` → `primary_feature_dir_for_mission` fallback). Ordering bug (B): delete coord worktree before deleting the branch it has checked out.

### #2119 — retrospective durable home

At `retrospective/writer.py:48`:
```python
feature_dir: Path = resolve_feature_dir_for_slug(repo_root, mission_slug)
return feature_dir / "retrospective.yaml"
```

`resolve_feature_dir_for_slug` is coord-topology-aware — it returns the coord worktree path for a coord-topology mission. So `retrospective.yaml` is written into `.worktrees/<slug>-<mid8>-coord/kitty-specs/...retrospective.yaml`, which is the ephemeral coord branch. After teardown this file is gone or the coord branch cannot be deleted because the worktree still has it checked out.

The ticket asks to write to a **durable location** (`.kittify/missions/<mission_id>/retrospective.yaml` or the primary `kitty-specs/<slug>/retrospective.yaml`). The existing `_legacy_record_path` in `writer.py:52` correctly uses `.kittify/missions/<id>/...` (gitignored), which is durable. The canonical write path needs to target the **primary** mission dir, not the coord-aware resolver.

### Terminal-artifact sites that write to the coord surface

| Site | File : line | Artifact | Writes to coord? |
|------|-------------|----------|-----------------|
| `canonical_record_path` → `resolve_feature_dir_for_slug` | `retrospective/writer.py:46-49` | `retrospective.yaml` | YES — coord-aware resolver |
| `_resolve_mission_id` in retrospective_terminus | `post_merge/retrospective_terminus.py:112` | (ID probe only) | reads coord feature_dir via local resolution |
| `close_cmd` meta_path | `cli/commands/mission_type.py:609` | reads `meta.json` from coord feature_dir | YES — coord dir lacks meta.json |

---

## 3. Consolidation Verdict

### ONE root operation duplicated at N sites? YES — with a precise seam gap

The recurring failure class is: **"callers pass a raw operator handle (mid8/ULID/numeric prefix) into a function that only accepts a canonical slug OR passes the coord-aware resolved dir into code that needs the primary dir"**. This is two distinct sub-patterns of the same boundary leak:

**Sub-pattern A (handle-as-slug):** `resolve_planning_read_dir` + `primary_feature_dir_for_mission` lack a handle-canonicalization step. Fix: insert `_canonicalize_handle` (already exists in `_read_path_resolver`) before the PRIMARY arm in `resolve_planning_read_dir`, or canonicalize at caller level before passing.

**Sub-pattern B (coord-surface for primary-only operations):** `close_cmd`, `canonical_record_path` (retrospective writer), and any other terminal-artifact write use coord-aware resolution where they need the primary checkout. Fix: use `primary_feature_dir_for_mission` for teardown identity and artifact persistence, parallel to how `reopen` already does.

**Can ONE fix close #2122 + #2120 + #2119 together?** Partially. A single `resolve_planning_read_dir` handle-canonicalization step closes #2122 and the N+1 research.py exposure. A single "use `primary_feature_dir_for_mission` for terminal/durable operations" rule closes both #2120 and #2119 (retrospective durable home). These are two separate 1-line-each fixes at two seams, not one.

### N+1 site outside the 3 tickets

- **`research.py:106,121`** (`cli/commands/research.py`) — passes raw `mission_slug` CLI arg through `resolve_planning_read_dir`. Same handle-as-slug exposure as #2122 for `spec-kitty research --mission <mid8>`.
- **`agent/mission.py:_planning_read_dir` (lines 1358, 1410, 2309, 2311)** — similar, but through a local wrapper that re-exports to multiple callers; single fix at the wrapper propagates to all 4 call sites.

---

## 4. #2112 (Repo Root) — Same Class or Separate?

**Separate.** The `SPEC_KITTY_REPO_NOT_INITIALIZED` error arises when `assert_initialized` calls `resolve_canonical_root(Path.cwd())` and gets a root that has no `.kittify/config.yaml`. The issue reporter's `init non-interactive-demo-project` created a subdirectory `non-interactive-demo-project/` with its own `.kittify/`, but then ran `spec-kitty specify request.md` from **the parent directory** (where no `.kittify/` exists). The resolved git root (the parent) has no `config.yaml`.

This is NOT a coord-surface-resolution bug — it is a CWD mismatch + the Tier 2 `locate_project_root` walk finding the parent git root before the child's `.kittify/`. It relates to the historical tension between `locate_project_root` (which requires `.kittify/`) and `resolve_canonical_root` (which resolves the git root first). When the operator is outside the initialized child directory, both functions correctly report "not initialized" from the parent's perspective.

**Likely genuine UX issue**: `init <name>` creates `<name>/` and should tell the operator to `cd <name>/` before running subsequent commands. Not a surface-resolution duplication.

---

## 5. #2116 (tasks.py tech-debt) — Separate

Pure tech-debt: body thinning + coord-skip consolidation in the router. Not a surface-resolution duplication bug. The coord-skip (`_skip_target_branch_commit` / `_protected_branch_status_commit_error`) is a router-contract change affecting callers — deferred by design in PR #2114.

---

## 6. Summary Inventory Table

| Site | File : line | Bug class | Ticket |
|------|-------------|-----------|--------|
| `_wp_tasks_read_dir` | `acceptance/__init__.py:859` | handle-as-slug in `resolve_planning_read_dir` | #2122 |
| `_planning_read_dir` | `acceptance/__init__.py:823` | handle-as-slug in `resolve_planning_read_dir` | #2122 |
| `close_cmd` resolution | `cli/commands/mission_type.py:595` | coord-aware resolver used for teardown (needs primary) | #2120 |
| `close_cmd` meta_path | `cli/commands/mission_type.py:609` | reads `meta.json` from coord dir (no `meta.json` there) | #2120 |
| `canonical_record_path` | `retrospective/writer.py:46-49` | writes retro into coord-aware dir (ephemeral) | #2119 |
| `research.py` planning dir | `cli/commands/research.py:106,121` | handle-as-slug in `resolve_planning_read_dir` | N+1 (unlisted) |
| `agent/mission.py _planning_read_dir` | `cli/commands/agent/mission.py:1167` | handle-as-slug in `resolve_planning_read_dir` wrapper | N+1 (unlisted) |
| `#2112 repo-root` | `workspace/assert_initialized.py:94` + `core/paths.py locate_project_root` | CWD outside initialized child dir — separate class | #2112 |
| `#2116 tasks.py tech-debt` | `cli/commands/agent/tasks.py` | body thinning + router-contract, not surface-resolution | #2116 |

---

## 7. Release Decision Summary (paula synthesis)

**Pattern A (handle-as-slug):** #2122 is the confirmed P1 regression with a red test. Fix: canonicalize the handle to slug BEFORE passing into `resolve_planning_read_dir`'s PRIMARY arm. The same fix closes the N+1 `research.py` and `agent/mission.py` exposures. All three share the same 1-line seam insertion.

**Pattern B (coord-surface for primary-needed ops):** #2120 + #2119 share the same ownership mistake — coord-aware resolver used where the primary checkout is required for teardown and durable persistence. Fix: use `primary_feature_dir_for_mission` at both sites. Ordering fix (#2120-B) is a separate 3-line swap.

**#2112:** UX + CWD issue, not surface-resolution. Likely a doc/diagnostic fix (tell operator to `cd <name>/` after `init <name>`). Low-risk.

**#2116:** Deferred tech-debt. Not a 3.2.3 blocker.

**Smallest safe 3.2.3 release action:** Fix handle canonicalization in `_wp_tasks_read_dir` and `_planning_read_dir` in `acceptance/__init__.py` (confirmed red test guard), redirect `close_cmd`'s discard path to `primary_feature_dir_for_mission`, fix worktree/branch ordering in `_delete_lane_branches`/`_teardown_coordination_worktree`, and redirect `canonical_record_path` to `primary_feature_dir_for_mission`. The `research.py` / `agent/mission.py` N+1 should be addressed in the same pass (same fix, same seam).

**Long-term architecture action:** Add a handle-canonicalization step at the `resolve_planning_read_dir` entry point (before the PRIMARY arm), so ALL callers become safe regardless of what handle they pass. Filed as follow-on; the release fix at the acceptance callers is the immediate safe action.
