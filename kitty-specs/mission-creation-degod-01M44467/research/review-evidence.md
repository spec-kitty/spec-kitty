# Review evidence: planted breaks, census, proofs

Implementers cannot edit `kitty-specs/` (code WPs), and the WP prompt files under `tasks/` feed the analysis-freshness hash. The orchestrator therefore records each WP's planted-break evidence and measurements here, as the implementer and reviewer reported them.

## WP02 — CLI golden cells and topology fallback pin (commit 2fac9a5ea, lane-b)

All breaks were applied temporarily in `src/` and reverted; `src/` is clean.

| Break | One-line change | Red tests |
|---|---|---|
| A | `_resolve_default_topology_phase`: `resolve_primary_branch(repo_root, bias=False)` | `default_no_origin_head_non_common`, fallback pin |
| B | `coord_topology_reachable`: `and` → `or` | `default_pr_bound_unprotected_topic`, 4 truth-table rows |
| D | owned default → `LANES` | `default_owned_checkout` |
| E | primary default → `LANES` | `default_primary_with_origin_head`, `default_no_origin_head_non_common`, fallback pin |
| F | one character in the `--commit-to-target` refusal message | `refusal_commit_to_target_with_lanes` |
| G | owned refusal error code renamed | `owned_not_a_worktree_refusal` |
| H | duplicate error code renamed | `coord_duplicate_refusal` |

Observations:
- With no `origin/HEAD`, on `feat-x` with `main` present: `resolve_primary_branch(repo)` gives `feat-x`, while `bias=False` gives `main`. The derived default is `coord` (follow-up: #5707).
- `ProtectionPolicy` protects `main`/`master` by default when there is no `protection:` block, so "unprotected" needs an explicit `protected_branches: []`.

## WP04 — Patch census baseline (lane base f0f3daa55, commit 3f115936f)

- Static façade total: **277 sites, 33 files, 13 names** (246 `patch`, 31 `setattr`):
  - `is_worktree_context` 72
  - `locate_project_root` 45
  - `is_git_repo` 44
  - `get_current_branch` 42
  - `_commit_feature_file` 41
  - `ULID` 11
  - `create_mission_core` 7
  - `preflight_commit` 5
  - `safe_commit` 4
  - `_commit_create_scaffold` 2
  - `now_utc_iso` 2
  - `_consume_pending_origin_if_present` 1
  - `subprocess.run` 1
- Source namespace (42-file covering set): 28 sites over 11 modules. Stdlib bucket (42 files): 12.
- Unresolved: 59 over the whole tree, of which 29 are flagged as possibly family-targeting. 26 of those are loop-driven `patch(k, v)` in `test_feature_finalize_bootstrap.py`.
- Runtime over the covering set: 515 collected, 513 passed, 2 skipped. **841 applications**: family 618, other namespace 159, source 52, stdlib 12. 288 tests carry patches.

## WP03 — Uncovered branches and invariants (commit 63e11bb9f, lane-c)

20 tests; all green on the unchanged base, all 20 red on their planted break. Façade names patched by fault injection: `ULID`, `build_mission_created_payload`, `_commit_create_scaffold` (all with `raising=True`). The full git-applyable patches follow.

### R1a
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -574,3 +574,3 @@
         dirty.append(str(entry.path))
-    if dirty:
+    if False and dirty:
         raise MissionCreationError(
### R1b
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -571,3 +571,3 @@
     for entry in status_entries(write_root, untracked=None):
-        if any(owned.overlaps(entry.path) for owned in owned_paths):
+        if False:
             continue
### R2
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -604,3 +604,3 @@
     )
-    if create_result.returncode != 0:
+    if False:
         detail = (create_result.stderr or create_result.stdout or "").strip()
### R3
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1490,3 +1490,3 @@
         corroborated = classify_topology(meta.get("coordination_branch") or None, has_lanes=False)
-        if corroborated is not topology:
+        if False:
             raise MissionCreationError(
### R4
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1687,3 +1687,2 @@
             or persisted_created.get("aggregate_type") != "Mission"
-            or persisted_created.get("payload") != expected_created_payload
         ):
### R5
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1955,3 +1955,3 @@
     )
-    if result.status not in (STATUS_COMMITTED, STATUS_UNCHANGED):
+    if False:
         raise MissionCreationError(
### R6a
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1780,3 +1780,3 @@
     except _BOOTSTRAP_META_COMMIT_SKIPS as exc:
-        scaffold_commit_skipped = True
+        raise
         logger.info(
### R6b
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1821,3 +1821,3 @@
         except _BOOTSTRAP_META_COMMIT_SKIPS as exc:
-            scaffold_commit_skipped = True
+            raise
             logger.info(
### R7
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -425,3 +425,3 @@
         if candidate_meta is None:
-            return (name, candidate_mid8)  # fail closed: missing meta.json
+            continue  # planted break
 
### R8
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -378,3 +378,3 @@
     except StoreError:
-        return False
+        return True
 
### R9
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -666,3 +666,3 @@
         # "task-list-api-01ABCDEF").
-        if name != mission_slug and not re.fullmatch(re.escape(mission_slug) + r"-[0-9A-Za-z]{8}", name):
+        if not name.startswith(mission_slug):
             continue
### R10
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -762,4 +762,2 @@
         )
-        return
-    if ctx.pre_seed_coord_tip is None:
         return
### I1
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -805,2 +805,11 @@
     """
+    # 2. Delete only the coordination branches that appeared during this create.
+    orphaned = _list_coordination_branches(repo_root) - pre_existing_coordination_branches
+    for branch in sorted(orphaned):
+        subprocess.run(
+            ["git", "-C", str(repo_root), "branch", "-D", branch],
+            capture_output=True,
+            text=True,
+            check=False,
+        )
     # 1. Restore the operator's checkout first (a checked-out branch cannot be
@@ -849,11 +858,2 @@
         _rollback_coordination_surface(coord_rollback)
-    # 2. Delete only the coordination branches that appeared during this create.
-    orphaned = _list_coordination_branches(repo_root) - pre_existing_coordination_branches
-    for branch in sorted(orphaned):
-        subprocess.run(
-            ["git", "-C", str(repo_root), "branch", "-D", branch],
-            capture_output=True,
-            text=True,
-            check=False,
-        )
 
### I2a
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -745,2 +745,9 @@
             shutil.rmtree(coord_mission_dir)
+    if ctx.coordination_branch_created:
+        subprocess.run(
+            ["git", "-C", str(repo_root), "branch", "-D", ctx.coordination_branch],
+            capture_output=True,
+            text=True,
+            check=False,
+        )
     with contextlib.suppress(Exception):
@@ -756,8 +763,2 @@
     if ctx.coordination_branch_created:
-        subprocess.run(
-            ["git", "-C", str(repo_root), "branch", "-D", ctx.coordination_branch],
-            capture_output=True,
-            text=True,
-            check=False,
-        )
         return
### I2b
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -742,5 +742,2 @@
     coord_mission_dir = coord_feature_dir(repo_root, ctx.mission_slug_formatted, ctx.mid8)
-    if coord_mission_dir.exists():
-        with contextlib.suppress(OSError):
-            shutil.rmtree(coord_mission_dir)
     with contextlib.suppress(Exception):
@@ -749,2 +746,5 @@
         teardown_coordination_topology(repo_root, ctx.mission_slug_formatted, ctx.mid8, persist=False, check_ledger=False)
+    if coord_mission_dir.exists():
+        with contextlib.suppress(OSError):
+            shutil.rmtree(coord_mission_dir)
     subprocess.run(
### I3
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -2211,3 +2211,2 @@
 
-    _refuse_live_duplicate(write_root, mission_slug, mission, allow_duplicate)
 
@@ -2264,2 +2263,3 @@
     )
+    _refuse_live_duplicate(write_root, mission_slug, mission, allow_duplicate)
     if meta_build.minted_mission_branch is not None:
### I4
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -2275,3 +2275,3 @@
         # readable yet), never a hand-built CommitTarget.
-        create_time_target = resolve_create_time_write_target(meta_build.minted_mission_branch)
+        pass
 
### I5
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1315,3 +1315,3 @@
         + (() if is_coordination_routed else (feature_dir / "status.events.jsonl",))
-        + (feature_dir / "tasks" / "README.md", feature_dir / "tasks" / ".gitkeep")
+        + (feature_dir / "tasks" / "README.md", feature_dir / "tasks" / ".gitkeep", feature_dir / "spec.md")
     )
### I6
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1808,3 +1808,3 @@
 
-    if origin_binding_succeeded:
+    if False:
         meta_file = scaffold.feature_dir / "meta.json"
### I7
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1441,3 +1441,3 @@
     # the value was knowable (#3474).
-    meta.setdefault("mid8", mid8)
+    meta.setdefault("mid8", mission_id[-8:])
     meta.setdefault("mission_number", None)  # JSON null — pre-merge missions have no number

## WP01 — Core golden matrix (commits 8d49f5d24, 87d29411e, lane-a)

58 cells: 41 success (flat 15, coord 11, protected/owned 15) and 17 refusal (the 13 SC-001 cells, 2 malformed-config cells, 2 failed-create restore cells driven by a real failing pre-commit hook). `base_commit` is f0f3daa55; serial regen is reproducible; `git diff f0f3daa55 HEAD -- src/` is empty. Wall time 12.2 s warm, 24.7 s cold (`-n 4`). `--cov-branch` of `mission_creation.py` under the golden run: 85% (557 statements, 62 missed; 174 branches, 35 partial). The implementer's report follows.

# WP01 planted breaks (each applied alone to src/specify_cli/core/mission_creation.py at f0f3daa55, matrix run -n4, reverted with git checkout -- src/)

## capture key: message — 1 red test(s)

Failing cells: refusals/detached_head

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..8521e406e 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1101,7 +1101,7 @@ def _resolve_create_roots(
 
     current_branch = get_current_branch(write_root)
     if not current_branch or current_branch == "HEAD":
-        raise MissionCreationError("Must be on a branch to create missions (detached HEAD detected).")
+        raise MissionCreationError("Must be on a branch to create mission (detached HEAD detected).")
 
     return _CreateRoots(
         repository_root=resolved_root,
```

## capture key: meta — 6 red test(s)

Failing cells: coord/coord/retention, coord/lanes_with_coord/retention, flat/lanes/retention, flat/single_branch/retention, protected/protected/coord/retention, protected/protected/single_branch/retention

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..4c2658749 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1452,7 +1452,7 @@ def _build_create_meta(
     if pr_bound:
         meta["pr_bound"] = True
     if retain_branches:
-        meta["retain_branches"] = True
+        pass
     if retain_worktrees:
         meta["retain_worktrees"] = True
     # #5100 FR-008 (WP08): mirrors the retention pattern above -- mint ONLY
```

## capture key: branches — 9 red test(s)

Failing cells: protected/configured_non_primary/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention, refusals/failed_create_restore/protected_mint, refusals/mission_branch_exists, refusals/protected_recreate

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..cfb57b0af 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -580,7 +580,7 @@ def _mint_protected_single_branch_mission_branch(
             "discard them, then retry."
         )
 
-    branch_name = mission_branch_name(mission_slug_formatted, mission_id=mission_id)
+    branch_name = mission_branch_name(mission_slug_formatted, mission_id=mission_id).replace("kitty/mission-", "kitty/minted-", 1)
     exists = (
         subprocess.run(
             ["git", "-C", str(write_root), "rev-parse", "--verify", f"refs/heads/{branch_name}"],
```

## capture key: status_log — 15 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes_with_coord/plain, refusals/failed_create_restore/coord

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..a8f4ca627 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -2035,7 +2035,7 @@ def _seed_coord_surface_for_create(
     if owned is not None:
         return _CoordCreateSeed(status_dir=None, rollback_ctx=rollback_ctx)
     location: WriteLocation = placement_seam(resolved_root, mission_slug_formatted, owned=None).write_dir(MissionArtifactKind.STATUS_STATE)
-    return _CoordCreateSeed(status_dir=location.path, rollback_ctx=rollback_ctx)
+    return _CoordCreateSeed(status_dir=None, rollback_ctx=rollback_ctx)
 
 
 def _create_mission_core_impl(
```

## capture key: new_commits — 44 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, flat/lanes/abandoned_prior_recreate, flat/lanes/documentation, flat/lanes/plain, flat/lanes/pr_bound, flat/lanes/retention, flat/lanes/same_slug_other_type, flat/lanes/summary, flat/lanes/target_not_checked_out, flat/single_branch/commit_to_target, flat/single_branch/documentation, flat/single_branch/plain, flat/single_branch/pr_bound, flat/single_branch/retention, flat/single_branch/summary, flat/single_branch/target_not_checked_out, protected/configured_non_primary/single_branch, protected/owned/coord, protected/owned/lanes, protected/owned/lanes_with_coord, protected/owned/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes/plain, protected/protected/lanes_with_coord/plain, protected/protected/single_branch/commit_to_target, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention, refusals/failed_create_restore/protected_mint, refusals/live_duplicate, refusals/protected_recreate

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..96965d19c 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1768,7 +1768,7 @@ def _commit_create_scaffold(
     """
     scaffold_commit_skipped = False
     try:
-        _commit_feature_file(
+        (lambda *a, **k: None)(
             scaffold.scaffold_paths,
             mission_slug_formatted,
             "scaffold",
```

## capture key: head — 1 red test(s)

Failing cells: refusals/failed_create_restore/protected_mint

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..ecea25ce2 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -807,7 +807,7 @@ def _restore_git_state_after_failed_create(
     #    deleted).
     if original_branch is not None:
         current = get_current_branch(repo_root)
-        if current is not None and current != original_branch:
+        if False:
             subprocess.run(
                 ["git", "-C", str(repo_root), "checkout", original_branch],
                 capture_output=True,
```

## capture key: meta_key_order — 41 red test(s)

Failing cells: coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, flat/lanes/abandoned_prior_recreate, flat/lanes/plain, flat/lanes/pr_bound, flat/lanes/retention, flat/lanes/same_slug_other_type, flat/lanes/summary, flat/lanes/target_not_checked_out, flat/single_branch/commit_to_target, flat/single_branch/plain, flat/single_branch/pr_bound, flat/single_branch/retention, flat/single_branch/summary, flat/single_branch/target_not_checked_out, protected/configured_non_primary/single_branch, protected/owned/coord, protected/owned/lanes, protected/owned/lanes_with_coord, protected/owned/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes/plain, protected/protected/lanes_with_coord/plain, protected/protected/single_branch/commit_to_target, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention, refusals/failed_create_restore/coord, refusals/failed_create_restore/protected_mint, refusals/live_duplicate, refusals/protected_recreate

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..041ac8f7c 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1508,7 +1508,7 @@ def _build_create_meta(
 
     from specify_cli.mission_metadata import set_documentation_state, write_meta
 
-    write_meta(feature_dir, meta)
+    (feature_dir / "meta.json").write_text(__import__("json").dumps(meta, indent=2) + "\n", encoding="utf-8")
 
     if mission == "documentation":
         meta.setdefault(_META_KEY_MISSION_TYPE, "documentation")
```

## capture key: worktrees — 15 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes_with_coord/plain, refusals/failed_create_restore/coord

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..2d7870537 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -2032,7 +2032,7 @@ def _seed_coord_surface_for_create(
     )
     if coord_rollback_holder is not None:
         coord_rollback_holder.append(rollback_ctx)
-    if owned is not None:
+    if True:
         return _CoordCreateSeed(status_dir=None, rollback_ctx=rollback_ctx)
     location: WriteLocation = placement_seam(resolved_root, mission_slug_formatted, owned=None).write_dir(MissionArtifactKind.STATUS_STATE)
     return _CoordCreateSeed(status_dir=location.path, rollback_ctx=rollback_ctx)
```

## capture key: porcelain — 37 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, flat/lanes/abandoned_prior_recreate, flat/lanes/documentation, flat/lanes/plain, flat/lanes/pr_bound, flat/lanes/retention, flat/lanes/same_slug_other_type, flat/lanes/summary, flat/single_branch/commit_to_target, flat/single_branch/documentation, flat/single_branch/plain, flat/single_branch/pr_bound, flat/single_branch/retention, flat/single_branch/summary, protected/configured_non_primary/single_branch, protected/owned/coord, protected/owned/lanes, protected/owned/lanes_with_coord, protected/owned/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/single_branch/commit_to_target, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention, refusals/live_duplicate, refusals/protected_recreate

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..f02a71d84 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1313,7 +1313,7 @@ def _scaffold_mission_dir(
     scaffold_paths = (
         (feature_dir / "meta.json",)
         + (() if is_coordination_routed else (feature_dir / "status.events.jsonl",))
-        + (feature_dir / "tasks" / "README.md", feature_dir / "tasks" / ".gitkeep")
+        + (feature_dir / "tasks" / "README.md",)
     )
     # Validate before scaffold writes using the same authority as safe_commit.
     # Main permits these bootstrap refusals and discloses the uncommitted
```

## capture key: tree — 49 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, flat/lanes/abandoned_prior_recreate, flat/lanes/documentation, flat/lanes/plain, flat/lanes/pr_bound, flat/lanes/retention, flat/lanes/same_slug_other_type, flat/lanes/summary, flat/lanes/target_not_checked_out, flat/single_branch/commit_to_target, flat/single_branch/documentation, flat/single_branch/plain, flat/single_branch/pr_bound, flat/single_branch/retention, flat/single_branch/summary, flat/single_branch/target_not_checked_out, protected/configured_non_primary/single_branch, protected/owned/coord, protected/owned/lanes, protected/owned/lanes_with_coord, protected/owned/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes/plain, protected/protected/lanes_with_coord/plain, protected/protected/single_branch/commit_to_target, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention, refusals/dirty_checkout_protected_mint, refusals/failed_create_restore/coord, refusals/failed_create_restore/protected_mint, refusals/live_duplicate, refusals/mission_branch_exists, refusals/protected_recreate, refusals/protected_target_without_commit, refusals/refused_mint_orphan_retry

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..322f82548 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1335,7 +1335,6 @@ def _scaffold_mission_dir(
     feature_dir.mkdir(parents=True, exist_ok=True)
 
     (feature_dir / "checklists").mkdir(exist_ok=True)
-    (feature_dir / "research").mkdir(exist_ok=True)
     tasks_dir = feature_dir / "tasks"
     tasks_dir.mkdir(exist_ok=True)
 
```

## capture key: exc_type — 1 red test(s)

Failing cells: refusals/detached_head

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..7fef8677f 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1101,7 +1101,7 @@ def _resolve_create_roots(
 
     current_branch = get_current_branch(write_root)
     if not current_branch or current_branch == "HEAD":
-        raise MissionCreationError("Must be on a branch to create missions (detached HEAD detected).")
+        raise RuntimeError("Must be on a branch to create missions (detached HEAD detected).")
 
     return _CreateRoots(
         repository_root=resolved_root,
```

## capture key: error_code — 1 red test(s)

Failing cells: refusals/mission_branch_exists

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..f6dd0df5e 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -451,7 +451,7 @@ class MissionBranchExistsError(MissionCreationError):
     branch), and silently checking it out would corrupt the mission's history.
     """
 
-    error_code: str = "MISSION_BRANCH_EXISTS"
+    error_code: str = "MISSION_BRANCH_EXIST"
 
 
 def _refuse_target_without_commit(write_root: Path, target_branch: str) -> None:
```

## capture key: result_fields — 41 red test(s)

Failing cells: coord/coord/documentation, coord/coord/force_recreate, coord/coord/plain, coord/coord/pr_bound, coord/coord/retention, coord/coord/summary, coord/lanes_with_coord/documentation, coord/lanes_with_coord/plain, coord/lanes_with_coord/pr_bound, coord/lanes_with_coord/retention, coord/lanes_with_coord/summary, flat/lanes/abandoned_prior_recreate, flat/lanes/documentation, flat/lanes/plain, flat/lanes/pr_bound, flat/lanes/retention, flat/lanes/same_slug_other_type, flat/lanes/summary, flat/lanes/target_not_checked_out, flat/single_branch/commit_to_target, flat/single_branch/documentation, flat/single_branch/plain, flat/single_branch/pr_bound, flat/single_branch/retention, flat/single_branch/summary, flat/single_branch/target_not_checked_out, protected/configured_non_primary/single_branch, protected/owned/coord, protected/owned/lanes, protected/owned/lanes_with_coord, protected/owned/single_branch, protected/primary_no_origin_head/single_branch, protected/primary_unconfigured/single_branch, protected/protected/coord/plain, protected/protected/coord/retention, protected/protected/lanes/plain, protected/protected/lanes_with_coord/plain, protected/protected/single_branch/commit_to_target, protected/protected/single_branch/plain, protected/protected/single_branch/pr_bound, protected/protected/single_branch/retention

```diff
diff --git a/src/specify_cli/core/mission_creation.py b/src/specify_cli/core/mission_creation.py
index 5de86b2d7..01103dc51 100644
--- a/src/specify_cli/core/mission_creation.py
+++ b/src/specify_cli/core/mission_creation.py
@@ -1877,7 +1877,7 @@ def _build_create_result(
     created_files = [scaffold.spec_file, meta_file, scaffold.tasks_readme]
     if is_coordination_routed:
         created_files.append(log_path)
-    uncommitted_files = [scaffold.spec_file]
+    uncommitted_files: list[Path] = []
     if commit_outcome.scaffold_commit_skipped:
         # The coordination log already committed separately (unconditionally,
         # outside the target scaffold commit's own bootstrap-skip handling,
```

## WP01 cycle 2 — harness freeze point

- Cycle 2 (commit `3e652523b`, lane-a) captures full commit messages (`%B`), watches the other repo in `owned_root_mismatch`, and fixes the flat docstring count.
- Trailer break: dropping `Spec-Kitty-Coordination-Seed` from the "record mission creation" commit (`mission_creation.py:1947` on the base) turns 14 cells red. The implementer and the reviewer each reproduced it.
- **NFR-001 freeze commit: `3e652523b`.** From here on, `git diff 3e652523b -- tests/core/golden tests/core/_mission_create_golden.py tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/golden tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/_support/git_template tests/_factories/__init__.py` must be empty on every later WP.

## WP05 — Pure decision cores (commits aea6dd089, a048a8ccd, 61dd4c56c, lane-c)

14 cores in `mission_creation_decisions.py`, each wired in place. The GIT_TRACE probe sequence is identical before and after the wiring for the success cell and the three refusal cells. The implementer's planted-break record follows.

# WP05 planted breaks (each reverted; never committed)

## target_is_protected

['47 failed, 123 passed in 21.60s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..4112e1450 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -85,7 +85,7 @@ def target_is_protected(policy: ProtectedTargetPolicy, target_branch: str, prima
     *primary_for_protection* is the Primary Branch resolved with ``bias=False``
     (follow-up #5707).
     """
-    return bool(policy.is_protected_target(target_branch, primary_branch=primary_for_protection))
+    return not bool(policy.is_protected_target(target_branch, primary_branch=primary_for_protection))
 
 
 def protected_mint_applies(
```

Failing (47):
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[plain-single_branch]
- tests/core/test_mission_create_protected_single_branch.py::test_protected_target_mints_and_checks_out_mission_branch
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[pr_bound-single_branch]
- tests/core/test_mission_create_protected_single_branch.py::test_existing_mission_branch_name_refuses_create
- tests/core/test_mission_create_protected_single_branch.py::test_recreate_of_existing_mission_reports_mission_already_exists
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[retention-single_branch]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_owned_checkout]
- tests/core/test_mission_creation_golden_refusals.py::test_mission_branch_exists
- tests/core/test_mission_create_protected_single_branch.py::test_unprotected_target_no_mint
- tests/core/test_mission_creation_golden_refusals.py::test_dirty_checkout_protected_mint
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[documentation-single_branch]
- tests/core/test_mission_creation_golden_refusals.py::test_protected_target_without_commit
- tests/core/test_mission_create_protected_single_branch.py::test_status_transition_commits_to_mission_branch_not_target
- tests/core/test_mission_create_protected_single_branch.py::test_implement_wrong_branch_refused_naming_mission_branch
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[summary-single_branch]
- tests/core/test_mission_create_protected_single_branch.py::test_minted_mission_branch_not_classified_by_recovery_or_doctor
- tests/core/test_mission_create_protected_single_branch.py::test_protected_mint_applies_only_to_a_protected_single_branch_mint[MissionTopology.SINGLE_BRANCH-False-main-True]
- tests/core/test_mission_create_protected_single_branch.py::test_protected_mint_applies_only_to_a_protected_single_branch_mint[MissionTopology.SINGLE_BRANCH-False-feature-x-False]
- tests/core/test_mission_creation_golden_refusals.py::test_protected_recreate
- tests/core/test_mission_creation_golden_refusals.py::test_refused_mint_orphan_retry
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[owned_success]
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_protected_mint
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_dirty_refusal]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_success]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/retention]
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row1_dirty_checkout_outside_scaffold_refuses_mint
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/pr_bound]
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row1_untracked_files_inside_own_scaffold_are_not_dirt
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row2_checkout_b_failure_raises_typed_error
- tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row3_topology_corroboration_failure_refuses
- tests/core/test_mission_creation_golden_protected.py::test_primary_unconfigured
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[single_branch]
- tests/core/test_mission_creation_golden_protected.py::test_primary_no_origin_head
- tests/core/test_mission_creation_golden_protected.py::test_configured_non_primary
- tests/core/test_mission_creation_invariants.py::test_inv1_failed_create_restores_checkout_then_deletes_minted_branch
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[single_branch]
- tests/core/test_mission_creation_invariants.py::test_inv3_mission_already_exists_precedes_dirty_mint_refusal
- tests/core/test_mission_creation_invariants.py::test_inv4_scaffold_commit_lands_on_minted_branch_not_target
- tests/core/test_mission_create_checkout_restore.py::test_failed_create_restores_owned_checkout_ref_and_index
- tests/core/test_mission_creation_probe_order.py::test_success_cell_probe_order
- tests/core/test_mission_creation_probe_order.py::test_target_without_commit_stops_at_target_probe
- tests/core/test_mission_creation_probe_order.py::test_dirty_checkout_stops_at_status_probe
- tests/core/test_mission_creation_probe_order.py::test_branch_exists_stops_at_branch_probe
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[main]
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[feature-x]
- tests/core/test_mission_create_protected_single_branch.py::test_create_human_output_announces_the_checkout_switch

## protected_mint_applies

['36 failed, 134 passed in 21.71s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..c6fda6b37 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -103,7 +103,7 @@ def protected_mint_applies(
         return False
     if commit_to_target is None:
         return None
-    if commit_to_target:
+    if not commit_to_target:
         return False
     return target_protected
 
```

Failing (36):
- tests/core/test_mission_create_protected_single_branch.py::test_protected_target_mints_and_checks_out_mission_branch
- tests/core/test_mission_creation_golden_refusals.py::test_mission_branch_exists
- tests/core/test_mission_create_protected_single_branch.py::test_commit_to_target_flag_skips_mint
- tests/core/test_mission_creation_golden_refusals.py::test_dirty_checkout_protected_mint
- tests/core/test_mission_creation_golden_refusals.py::test_protected_target_without_commit
- tests/core/test_mission_create_protected_single_branch.py::test_existing_mission_branch_name_refuses_create
- tests/core/test_mission_create_protected_single_branch.py::test_recreate_of_existing_mission_reports_mission_already_exists
- tests/core/test_mission_create_protected_single_branch.py::test_status_transition_commits_to_mission_branch_not_target
- tests/core/test_mission_create_protected_single_branch.py::test_implement_wrong_branch_refused_naming_mission_branch
- tests/core/test_mission_creation_golden_refusals.py::test_protected_recreate
- tests/core/test_mission_create_protected_single_branch.py::test_minted_mission_branch_not_classified_by_recovery_or_doctor
- tests/core/test_mission_create_protected_single_branch.py::test_protected_mint_applies_only_to_a_protected_single_branch_mint[MissionTopology.SINGLE_BRANCH-False-main-True]
- tests/core/test_mission_creation_golden_refusals.py::test_refused_mint_orphan_retry
- tests/core/test_mission_create_protected_single_branch.py::test_protected_mint_applies_only_to_a_protected_single_branch_mint[MissionTopology.SINGLE_BRANCH-True-main-False]
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_protected_mint
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/commit_to_target]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/retention]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_dirty_refusal]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/pr_bound]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_success]
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row1_dirty_checkout_outside_scaffold_refuses_mint
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row2_checkout_b_failure_raises_typed_error
- tests/core/test_mission_creation_golden_protected.py::test_primary_unconfigured
- tests/core/test_mission_creation_golden_protected.py::test_primary_no_origin_head
- tests/core/test_mission_creation_golden_protected.py::test_configured_non_primary
- tests/core/test_mission_creation_invariants.py::test_inv1_failed_create_restores_checkout_then_deletes_minted_branch
- tests/core/test_mission_creation_invariants.py::test_inv3_mission_already_exists_precedes_dirty_mint_refusal
- tests/core/test_mission_creation_invariants.py::test_inv4_scaffold_commit_lands_on_minted_branch_not_target
- tests/core/test_mission_creation_probe_order.py::test_success_cell_probe_order
- tests/core/test_mission_creation_probe_order.py::test_target_without_commit_stops_at_target_probe
- tests/core/test_mission_creation_probe_order.py::test_dirty_checkout_stops_at_status_probe
- tests/core/test_mission_creation_probe_order.py::test_branch_exists_stops_at_branch_probe
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[main]
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[feature-x]
- tests/core/test_mission_create_protected_single_branch.py::test_create_human_output_announces_the_checkout_switch

## decide_protected_mint

['36 failed, 134 passed in 21.77s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..d5b905a70 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -183,7 +183,7 @@ def decide_protected_mint(facts: ProtectedMintFacts) -> ProtectedMintDecision |
         )
     if facts.branch_name is None or facts.branch_exists is None:
         return None
-    if facts.branch_exists:
+    if not facts.branch_exists:
         return Refuse(
             "branch_exists",
             f"Mission branch {facts.branch_name!r} already exists. Choose a "
```

Failing (36):
- tests/core/test_mission_create_protected_single_branch.py::test_protected_target_mints_and_checks_out_mission_branch
- tests/core/test_mission_creation_golden_refusals.py::test_mission_branch_exists
- tests/core/test_mission_create_protected_single_branch.py::test_existing_mission_branch_name_refuses_create
- tests/core/test_mission_create_protected_single_branch.py::test_recreate_of_existing_mission_reports_mission_already_exists
- tests/core/test_mission_create_protected_single_branch.py::test_status_transition_commits_to_mission_branch_not_target
- tests/core/test_mission_create_protected_single_branch.py::test_implement_wrong_branch_refused_naming_mission_branch
- tests/core/test_mission_create_protected_single_branch.py::test_minted_mission_branch_not_classified_by_recovery_or_doctor
- tests/core/test_mission_creation_golden_refusals.py::test_protected_recreate
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_protected_mint
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/retention]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/pr_bound]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_success]
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row1_untracked_files_inside_own_scaffold_are_not_dirt
- tests/core/test_mission_creation_branch_coverage.py::TestProtectedMintBranches::test_row2_checkout_b_failure_raises_typed_error
- tests/core/test_mission_creation_golden_protected.py::test_primary_unconfigured
- tests/core/test_mission_creation_golden_protected.py::test_primary_no_origin_head
- tests/core/test_mission_creation_golden_protected.py::test_configured_non_primary
- tests/core/test_mission_creation_invariants.py::test_inv1_failed_create_restores_checkout_then_deletes_minted_branch
- tests/core/test_mission_creation_invariants.py::test_inv4_scaffold_commit_lands_on_minted_branch_not_target
- tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033
- tests/core/test_mission_create_idempotency_guard.py::test_genesis_prior_auto_allows_recreate_with_no_flag
- tests/core/test_mission_create_idempotency_guard.py::test_canceled_only_prior_auto_allows_recreate_with_no_flag
- tests/core/test_mission_create_idempotency_guard.py::test_allow_duplicate_true_creates_second_live_mission
- tests/core/test_mission_create_idempotency_guard.py::test_same_slug_different_mission_type_is_allowed
- tests/specify_cli/test_mission_create_retention.py::test_both_retention_flags_mint_true_into_meta
- tests/core/test_mission_create_idempotency_guard.py::test_corrupt_prior_meta_json_fails_closed_and_refuses
- tests/core/test_mission_creation_probe_order.py::test_success_cell_probe_order
- tests/specify_cli/test_mission_create_retention.py::test_neither_flag_leaves_both_fields_absent
- tests/specify_cli/test_mission_create_retention.py::test_only_retain_branches_flag_present_leaves_worktrees_absent
- tests/specify_cli/test_mission_create_retention.py::test_only_retain_worktrees_flag_present_leaves_branches_absent
- tests/specify_cli/test_mission_create_retention.py::test_load_meta_fail_closed_round_trips_minted_true_values
- tests/core/test_mission_creation_probe_order.py::test_branch_exists_stops_at_branch_probe
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[main]
- tests/core/test_mission_create_protected_single_branch.py::test_create_json_reports_the_minted_checkout_branch[feature-x]
- tests/core/test_mission_create_protected_single_branch.py::test_create_human_output_announces_the_checkout_switch

## is_coordination_routed

['31 failed, 139 passed in 29.39s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..ae816f3cc 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -205,7 +205,7 @@ def is_coordination_routed(*, mints_coordination: bool, owned: bool) -> bool:
     (the topology authority). An owned create is never coordination-routed
     (INV-COORD-HOME residual): its status log stays in the owned checkout.
     """
-    return mints_coordination and not owned
+    return mints_coordination and owned
 
 
 # ---------------------------------------------------------------------------
```

Failing (31):
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[coord_success]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_no_origin_head_non_common]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_on_primary]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_protected_primary]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_topic_default_protection]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_primary_with_origin_head]
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_coord
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/retention]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes_with_coord/plain]
- tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row5_coordination_commit_failure_rolls_back_coord_surface
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-lanes_with_coord]
- tests/core/test_mission_creation_invariants.py::test_inv2_coordination_rollback_clears_dir_then_tears_down_then_deletes_branch
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-coord]
- tests/core/test_mission_creation_invariants.py::test_inv2_coordination_rollback_tears_down_worktree_before_deleting_branch
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_force_recreate
- tests/core/test_mission_create_coord_seed_rollback.py::test_protected_primary_still_seeds_coordination_surface
- tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_after_seed_removes_worktree_and_branch
- tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted
- tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[inside_write_dir_seed]
- tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[commit_coord_create_events]

## meta_flag_patch

['50 failed, 120 passed in 27.14s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..b08b84238 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -227,7 +227,7 @@ def meta_flag_patch(
     """
     flags = {
         "pr_bound": pr_bound,
-        "retain_branches": retain_branches,
+        "retain_branches": not retain_branches,
         "retain_worktrees": retain_worktrees,
         "commit_to_target": commit_to_target,
     }
```

Failing (50):
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[plain-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[plain-lanes]
- tests/core/test_mission_creation_golden_refusals.py::test_live_duplicate
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[pr_bound-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[pr_bound-lanes]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[retention-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[retention-lanes]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[documentation-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[documentation-lanes]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[summary-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[summary-lanes]
- tests/core/test_mission_creation_golden_flat.py::test_single_branch_commit_to_target_unprotected
- tests/core/test_mission_creation_golden_refusals.py::test_protected_recreate
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_protected_mint
- tests/core/test_mission_creation_golden_flat.py::test_abandoned_prior_recreate
- tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_coord
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/commit_to_target]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/retention]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/pr_bound]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/plain]
- tests/core/test_mission_creation_golden_flat.py::test_same_slug_other_type
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[single_branch]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/retention]
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[lanes]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes_with_coord/plain]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-coord]
- tests/core/test_mission_creation_golden_protected.py::test_primary_unconfigured
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-lanes_with_coord]
- tests/core/test_mission_creation_golden_protected.py::test_primary_no_origin_head
- tests/core/test_mission_creation_golden_protected.py::test_configured_non_primary
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[single_branch]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-lanes_with_coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[lanes]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_force_recreate
- tests/specify_cli/test_mission_create_retention.py::test_both_retention_flags_mint_true_into_meta
- tests/specify_cli/test_mission_create_retention.py::test_neither_flag_leaves_both_fields_absent
- tests/specify_cli/test_mission_create_retention.py::test_only_retain_branches_flag_present_leaves_worktrees_absent
- tests/specify_cli/test_mission_create_retention.py::test_only_retain_worktrees_flag_present_leaves_branches_absent
- tests/specify_cli/test_mission_create_retention.py::test_load_meta_fail_closed_round_trips_minted_true_values

## candidate_name_matches

['7 failed, 163 passed in 27.89s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..7ec1d9c17 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -247,7 +247,7 @@ def candidate_name_matches(name: str, base_slug: str) -> tuple[bool, str]:
     """
     suffix_pattern = re.compile(re.escape(base_slug) + _MID8_DIR_SUFFIX_PATTERN + "$")
     match = suffix_pattern.fullmatch(name)
-    if name != base_slug and match is None:
+    if name != base_slug and match is not None:
         return False, ""
     return True, match.group(1) if match is not None else ""
 
```

Failing (7):
- tests/core/test_mission_creation_golden_refusals.py::test_live_duplicate
- tests/core/test_mission_creation_golden_refusals.py::test_refused_mint_orphan_retry
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_coord_duplicate_refusal
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row7_duplicate_scan_fails_closed_on_missing_meta
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row8_abandonment_read_failure_treats_prior_as_live
- tests/core/test_mission_creation_invariants.py::test_inv3_mission_already_exists_precedes_dirty_mint_refusal
- tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033

## is_same_mission_type

['7 failed, 163 passed in 27.42s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..25749483e 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -254,7 +254,7 @@ def candidate_name_matches(name: str, base_slug: str) -> tuple[bool, str]:
 
 def is_same_mission_type(candidate_meta: Mapping[str, object], mission_type: str) -> bool:
     """True when the candidate's ``mission_type`` (default ``software-dev``) is *mission_type*."""
-    return str(candidate_meta.get("mission_type") or _DEFAULT_MISSION_TYPE) == mission_type
+    return str(candidate_meta.get("mission_type") or _DEFAULT_MISSION_TYPE) != mission_type
 
 
 def is_abandoned(
```

Failing (7):
- tests/core/test_mission_creation_golden_refusals.py::test_live_duplicate
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_coord_duplicate_refusal
- tests/core/test_mission_creation_golden_flat.py::test_same_slug_other_type
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row8_abandonment_read_failure_treats_prior_as_live
- tests/core/test_mission_creation_invariants.py::test_inv3_mission_already_exists_precedes_dirty_mint_refusal
- tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033
- tests/core/test_mission_create_idempotency_guard.py::test_same_slug_different_mission_type_is_allowed

## is_abandoned

['8 failed, 162 passed in 27.45s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..172ad16a2 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -277,7 +277,7 @@ def is_abandoned(
         return False
     if spec_tracked is None:
         return None
-    return not spec_tracked
+    return spec_tracked
 
 
 # ---------------------------------------------------------------------------
```

Failing (8):
- tests/core/test_mission_creation_golden_refusals.py::test_live_duplicate
- tests/core/test_mission_creation_golden_refusals.py::test_protected_recreate
- tests/core/test_mission_creation_golden_flat.py::test_abandoned_prior_recreate
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_coord_duplicate_refusal
- tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row3_topology_corroboration_failure_refuses
- tests/core/test_mission_creation_invariants.py::test_inv3_mission_already_exists_precedes_dirty_mint_refusal
- tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033
- tests/core/test_mission_create_idempotency_guard.py::test_genesis_prior_auto_allows_recreate_with_no_flag

## orphan_scaffold_candidates

['6 failed, 164 passed in 26.90s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..a74726832 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -297,7 +297,7 @@ def orphan_scaffold_candidates(
     never a same-prefixed neighbour ("task-list" must not match
     "task-list-api-01ABCDEF").
     """
-    return tuple(name for name in sorted(post_names - pre_names) if name == mission_slug or re.fullmatch(re.escape(mission_slug) + r"-[0-9A-Za-z]{8}", name))
+    return tuple(name for name in sorted(pre_names - post_names) if name == mission_slug or re.fullmatch(re.escape(mission_slug) + r"-[0-9A-Za-z]{8}", name))
 
 
 def plan_orphan_scaffold_removal(
```

Failing (6):
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row9_orphan_planning_skips_same_prefix_neighbour
- tests/core/test_mission_create_scaffold_rollback.py::test_failed_create_leaves_no_orphan_scaffold[orphan-check]
- tests/core/test_mission_create_scaffold_rollback.py::test_failed_create_leaves_no_orphan_scaffold[068-orphan-check]
- tests/core/test_mission_creation_invariants.py::test_inv1_failed_create_restores_checkout_then_deletes_minted_branch
- tests/core/test_mission_create_scaffold_rollback.py::test_retry_after_failure_yields_exactly_one_mission
- tests/core/test_mission_create_scaffold_rollback.py::test_rollback_preserves_a_pre_existing_mission

## plan_orphan_scaffold_removal

['8 failed, 162 passed in 27.18s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..28ac4a95b 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -309,7 +309,7 @@ def plan_orphan_scaffold_removal(
 ) -> tuple[str, ...]:
     """The candidate scaffolds a failed create may delete: those git does not track."""
     candidates = orphan_scaffold_candidates(post_names=post_names, pre_names=pre_names, mission_slug=mission_slug)
-    return tuple(name for name in candidates if name not in tracked)
+    return tuple(name for name in candidates if name in tracked)
 
 
 @dataclass(frozen=True, slots=True)
```

Failing (8):
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row9_orphan_planning_skips_same_prefix_neighbour
- tests/core/test_mission_creation_invariants.py::test_inv1_failed_create_restores_checkout_then_deletes_minted_branch
- tests/core/test_mission_create_scaffold_rollback.py::test_failed_create_leaves_no_orphan_scaffold[orphan-check]
- tests/core/test_mission_create_scaffold_rollback.py::test_failed_create_leaves_no_orphan_scaffold[068-orphan-check]
- tests/core/test_mission_create_scaffold_rollback.py::test_retry_after_failure_yields_exactly_one_mission
- tests/core/test_mission_create_scaffold_rollback.py::test_rollback_preserves_a_pre_existing_mission
- tests/core/test_mission_create_scaffold_rollback.py::test_rollback_never_deletes_tracked_content
- tests/core/test_mission_create_scaffold_rollback.py::test_tracking_probe_launch_failure_preserves_scaffold

## coord_rollback_needs_current_tip

['1 failed, 169 passed in 26.27s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..c1329f28e 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -332,7 +332,7 @@ class Noop:
 
 def coord_rollback_needs_current_tip(*, created: bool, pre_seed_tip: str | None) -> bool:
     """True when :func:`coord_rollback_action` depends on the branch's current tip."""
-    return not created and pre_seed_tip is not None
+    return False
 
 
 def coord_rollback_action(
```

Failing (1):
- tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted

## coord_rollback_action

['3 failed, 167 passed in 27.42s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..05ca217ec 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -347,7 +347,7 @@ def coord_rollback_action(
     CAS-reset to its own pre-create tip when it moved, never deleted (it may
     belong to another mission's history). An unreadable tip is left alone.
     """
-    if created:
+    if not created:
         return Delete()
     if pre_seed_tip is None:
         return Noop()
```

Failing (3):
- tests/core/test_mission_creation_branch_coverage.py::TestDuplicateAndRollbackBranches::test_row10_coord_rollback_without_anchor_leaves_reused_branch_alone
- tests/core/test_mission_creation_invariants.py::test_inv2_coordination_rollback_tears_down_worktree_before_deleting_branch
- tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted

## classify_scaffold_commit_failure

['13 failed, 157 passed in 26.83s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..e0fec6fde 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -375,7 +375,7 @@ class CommitFailureKind(Enum):
 def classify_scaffold_commit_failure(kind: CommitFailureKind) -> Literal["skip", "already_exists", "raise"]:
     """Skip a disclosed bootstrap refusal, type the duplicate signature, raise the rest (FR-001)."""
     if kind is CommitFailureKind.BOOTSTRAP_REFUSAL:
-        return "skip"
+        return "raise"
     if kind is CommitFailureKind.STAGED_TREE_UNCHANGED:
         return "already_exists"
     return "raise"
```

Failing (13):
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[coord_success]
- tests/core/test_mission_create_protected_single_branch.py::test_lanes_topology_protected_target_unchanged
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_primary_with_origin_head]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_coord_duplicate_refusal
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/retention]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes_with_coord/plain]
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[single_branch]
- tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row6_scaffold_commit_bootstrap_skip_on_protected_target
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[lanes]
- tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row6_origin_binding_commit_bootstrap_skip
- tests/core/test_mission_create_coord_seed_rollback.py::test_protected_primary_still_seeds_coordination_surface

## created_file_sets

['53 failed, 117 passed in 26.14s']

```diff
diff --git a/src/specify_cli/core/mission_creation_decisions.py b/src/specify_cli/core/mission_creation_decisions.py
index fc25cb01f..5aa14ad84 100644
--- a/src/specify_cli/core/mission_creation_decisions.py
+++ b/src/specify_cli/core/mission_creation_decisions.py
@@ -398,7 +398,7 @@ def created_file_sets(
     scaffold.
     """
     created_files = [spec_file, meta_file, tasks_readme]
-    if coordination_routed:
+    if not coordination_routed:
         created_files.append(log_path)
     uncommitted_files = [spec_file]
     if scaffold_commit_skipped:
```

Failing (53):
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[plain-single_branch]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[coord_success]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[plain-lanes]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_no_origin_head_non_common]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[pr_bound-single_branch]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_non_primary_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[pr_bound-lanes]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_owned_checkout]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[retention-single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[retention-lanes]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_on_primary]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[documentation-single_branch]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_protected_primary]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[documentation-lanes]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[summary-single_branch]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_topic_default_protection]
- tests/core/test_mission_creation_golden_flat.py::test_flat_create[summary-lanes]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_pr_bound_unprotected_topic]
- tests/core/test_mission_creation_golden_flat.py::test_single_branch_commit_to_target_unprotected
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[default_primary_with_origin_head]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[flat_lanes_success]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[owned_success]
- tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py::test_cli_golden_cell[protected_single_branch_success]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/commit_to_target]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/retention]
- tests/core/test_mission_creation_golden_flat.py::test_abandoned_prior_recreate
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/pr_bound]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/plain]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[coord/retention]
- tests/core/test_mission_creation_golden_protected.py::test_protected_primary[lanes_with_coord/plain]
- tests/core/test_mission_creation_golden_protected.py::test_primary_unconfigured
- tests/core/test_mission_creation_golden_protected.py::test_primary_no_origin_head
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-coord]
- tests/core/test_mission_creation_golden_protected.py::test_configured_non_primary
- tests/core/test_mission_creation_golden_flat.py::test_same_slug_other_type
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[single_branch]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[plain-lanes_with_coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[single_branch]
- tests/core/test_mission_creation_golden_flat.py::test_target_not_checked_out[lanes]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[lanes]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[pr_bound-lanes_with_coord]
- tests/core/test_mission_creation_golden_protected.py::test_owned_checkout[lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[retention-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[documentation-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_create[summary-lanes_with_coord]
- tests/core/test_mission_creation_golden_coord.py::test_coord_force_recreate

## WP06 — Verbatim module split (commits 5ce86995f, df657a37b, 318a102f6, c83e29ef2, lane-c)

Façade 2,421 → 649 lines; 10 leaf modules. Exactly-once: 58/59 AST-identical (deviation: the `logger` binding, same logger object). All six gate re-pins have a planted removal. One out-of-map edit: `docs/development/page-inventory.yaml` (one row for the new docs page; the freshness check requires it). Carried mypy finding: `mission_creation_protected_mint.py:76` "Returning Any" (introduced in WP05; fixed in WP07). Implementer evidence follows.

# WP06 evidence (#5634)

## Exactly-once proof (T026; script /tmp/claude-0/-home-user-spec-kitty/2799d0a2-d598-577c-b077-f68d631cfcdf/scratchpad/wp06/proof.py, base 61dd4c56c)
```
base top-level names: 59
deviations: ["logger: defined in ['mission_creation_commit', 'mission_creation_events']"]
names only in family: []
assignment:
  mission_creation 2
  mission_creation_commit 6
  mission_creation_duplicates 4
  mission_creation_errors 5
  mission_creation_events 4
  mission_creation_identity 4
  mission_creation_meta 4
  mission_creation_protected_mint 11
  mission_creation_rollback 10
  mission_creation_roots 2
  mission_creation_scaffold 6
```
Deviation: logger — base façade `logging.getLogger(__name__)`; now `logging.getLogger("specify_cli.core.mission_creation")` in the commit and events leaves (same logger object); the façade re-exports the commit leaf's (needed because a façade-local unread logger tripped test_no_dead_symbols).

## Split script
/tmp/claude-0/-home-user-spec-kitty/2799d0a2-d598-577c-b077-f68d631cfcdf/scratchpad/wp06/split.py (throwaway, not committed)

## Per-gate planted removal (fold 4)
```diff
diff --git a/src/specify_cli/core/mission_creation_duplicates.py b/src/specify_cli/core/mission_creation_duplicates.py
index a0dc66759..674bd6350 100644
--- a/src/specify_cli/core/mission_creation_duplicates.py
+++ b/src/specify_cli/core/mission_creation_duplicates.py
@@ -26,7 +26,7 @@ from specify_cli.lanes.branch_naming import (
 from specify_cli.core.mission_creation_errors import MissionAlreadyExistsError
 
 
-def _list_mission_scaffolds(repo_root: Path) -> frozenset[str]:
+def _list_mission_scaffolds_planted(repo_root: Path) -> frozenset[str]:
     """Return the mission directory names currently under ``kitty-specs/``.
 
     Mirrors :func:`_list_coordination_branches`: diffing this before vs after a
diff --git a/src/specify_cli/core/mission_creation_events.py b/src/specify_cli/core/mission_creation_events.py
index 7f7cdf3f6..18dcb6f59 100644
--- a/src/specify_cli/core/mission_creation_events.py
+++ b/src/specify_cli/core/mission_creation_events.py
@@ -31,7 +31,7 @@ from specify_cli.core.mission_creation_rollback import _CoordCreateRollbackConte
 logger = logging.getLogger("specify_cli.core.mission_creation")
 
 
-def _emit_create_events(
+def _emit_create_events_planted(
     *,
     feature_dir: Path,
     mission_slug_formatted: str,
diff --git a/src/specify_cli/core/mission_creation_identity.py b/src/specify_cli/core/mission_creation_identity.py
index be319908a..17be44b7d 100644
--- a/src/specify_cli/core/mission_creation_identity.py
+++ b/src/specify_cli/core/mission_creation_identity.py
@@ -8,6 +8,8 @@ function another ``mission_creation*`` module owns, goes through a lazy in-funct
 
 from __future__ import annotations
 
+# planted: specify_cli.tracker
+
 import re
 from dataclasses import dataclass
 
diff --git a/src/specify_cli/core/mission_creation_rollback.py b/src/specify_cli/core/mission_creation_rollback.py
index 586585e62..ec00ad44f 100644
--- a/src/specify_cli/core/mission_creation_rollback.py
+++ b/src/specify_cli/core/mission_creation_rollback.py
@@ -71,6 +71,7 @@ def _list_coordination_branches(repo_root: Path) -> frozenset[str]:
 
 
 def _rev_parse_or_none(repo_root: Path, ref: str) -> str | None:
+    _planted = repo_root.parent.parent
     """Return ``ref``'s commit SHA in ``repo_root``, or ``None`` on any failure."""
     result = subprocess.run(
         ["git", "-C", str(repo_root), "rev-parse", ref],
diff --git a/src/specify_cli/core/mission_creation_roots.py b/src/specify_cli/core/mission_creation_roots.py
index 31dc54901..983adb1a2 100644
--- a/src/specify_cli/core/mission_creation_roots.py
+++ b/src/specify_cli/core/mission_creation_roots.py
@@ -94,7 +94,7 @@ def _resolve_create_roots(
     # linked checkouts can have different HEAD states in the same repository.
     if has_unborn_head(write_root):
         raise MissionCreationError(
-            "This checkout has no commits yet, so Spec Kitty cannot commit the mission scaffold.\n\n"
+            "This checkout has no commit yet, so Spec Kitty cannot commit the mission scaffold.\n\n"
             "Make an initial commit first, then create the mission:\n"
             "  git commit --allow-empty -m 'Initial commit'\n\n"
             "If the repository already has files staged, commit those instead."
diff --git a/src/specify_cli/core/mission_creation_scaffold.py b/src/specify_cli/core/mission_creation_scaffold.py
index 999816fb6..d8320ca1a 100644
--- a/src/specify_cli/core/mission_creation_scaffold.py
+++ b/src/specify_cli/core/mission_creation_scaffold.py
@@ -195,7 +195,7 @@ def _scaffold_mission_dir(
     """
     from specify_cli.core import mission_creation as _mc
 
-    feature_dir = write_root / KITTY_SPECS_DIR / mission_slug_formatted
+    feature_dir = write_root.joinpath(KITTY_SPECS_DIR, mission_slug_formatted)
     _mc._refuse_protected_recreate(
         write_root,
         feature_dir,
```

Gate 1 (surface resolver, scaffold plant alone): collection error
```
DescriptorResolutionError: descriptor ContentDescriptor(rel_path='specify_cli/core/mission_creation_scaffold.py', qualname='_scaffold_mission_dir', ...) resolved to 0 finding(s) (need exactly 1)
ERROR tests/architectural/test_single_mission_surface_resolver.py (collection)
```
Gates 2a/2b/3/4/5 (other plants together):
```
E   AssertionError: Stale COORD writer census pair(s) (no live definition): src/specify_cli/core/mission_creation_events.py::_emit_create_events. Re-point the census at the function that now holds the write; never delete it to green.
E   assert not [('src/specify_cli/core/mission_creation_events.py', '_emit_create_events')]
E     src/specify_cli/core/mission_creation_rollback.py:74 [root_walk] _planted = repo_root . parent . parent
E   assert not ['src/specify_cli/core/mission_creation_rollback.py:74 [root_walk] _planted = repo_root . parent . parent']
E   AssertionError: Raw kitty-specs enumeration bypasses MissionResolver; route the read through the resolver or document a distinct corpus walk: {'src/specify_cli/core/mission_creation_duplicates.py': [(38, 'iterdir')]}
E   assert not {'src/specify_cli/core/mission_creation_duplicates.py': [(38, 'iterdir')]}
E   AssertionError: Allowlist entries with no matching source hit (stale, remove them): [('core/mission_creation_roots.py', 'has no commits yet')]
E   assert not [('core/mission_creation_roots.py', 'has no commits yet')]
E   AssertionError: Leak #1 still present in mission_creation.py — INTEGRATION imports found: ['specify_cli.tracker']
E   assert not ['specify_cli.tracker']
FAILED tests/architectural/test_no_write_side_rederivation.py::test_coord_writer_census_floor_is_live
FAILED tests/architectural/test_no_write_side_rederivation.py::test_adopted_modules_have_no_write_side_rederivation
FAILED tests/architectural/test_mission_resolver_walker_gate.py::test_no_unsanctioned_raw_kitty_specs_enumeration_in_src
FAILED tests/specify_cli/cli/commands/test_commit_recipes.py::test_allowlist_has_no_stale_entries
FAILED tests/core/test_adapters.py::test_mission_creation_has_no_integration_imports
5 failed in 12.15s
```
Gate 6 (mission_type_reader_allowlist.yaml): census-only entry; mission_creation* are not in IN_SCOPE_READER_MODULES, so no check consumes it and no planted removal can red it (Appendix C [LOW]). N/A.

## mypy baseline
protected_mint.py:76 no-any-return is the verbatim-moved base façade line 508 error (base reproduces it: mypy on 61dd4c56c mission_creation.py -> line 508). Cause: follow_imports=skip for specify_cli.* makes mission_creation_decisions.target_is_protected Any (WP05). Fix: a pyproject [[tool.mypy.overrides]] follow_imports=normal for specify_cli.core.mission_creation_decisions (not an owned file).

## Final validation
Combined session (42 covering files + golden/CLI golden/fallback + WP03 + probe-order + decisions/purity + family/source + patch_census self-test + 19 gate files + redirect spine), -n 4 --dist loadfile:
FAILED tests/specify_cli/cli/commands/test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src
1 failed, 1430 passed, 10 skipped, 2 xfailed, 8 warnings in 202.23s (0:03:22)
(the one failure is baseline-red #5705: cli/commands/_commit_message.py, unrelated)
make test-fast equivalent (.venv python):
2275 passed, 8 skipped, 4 warnings in 233.56s (0:03:53)
Frozen set: git diff 61dd4c56c -- <frozen paths> is empty.

## WP07 — Seam cleanups + review folds (commits 39d984d06, 7c201f9cc, 0564d97c9, 1db7f2c8e, 7ae8769a9, 4cda05b74, d69a6df3d, lane-c)

Correction to the plan's assumption: the golden malformed-config (wrong-shape protection) cell does NOT detect resolving protection early, because `preflight_commit` raises the same `ProtectionConfigError` first and the mint never runs in that cell. The GIT_TRACE probe-order tests (6 red under the plant) are the guard. T036 was skipped: `_build_create_result` already computed the file sets before the fan-out. One out-of-map test-helper edit: `tests/core/test_mission_creation_decomposition.py` drops the removed `write_root` kwarg (no assertion changed). Implementer evidence follows.

# WP07 evidence

## F1 (39d984d06) mypy no-any-return
Planted: revert the typed local -> `mission_creation_protected_mint.py:76: error: Returning Any from function declared to return "bool" [no-any-return]` (the base state).

## F2 gate split
Plant A (drop the override guard):
```
-    if protected_mint_applies(topology, read_commit_to_target(meta), None) is False:
-        return None
```
-> FAILED tests/core/test_mission_create_protected_single_branch.py::test_commit_to_target_flag_skips_mint
-> FAILED tests/core/test_mission_creation_golden_protected.py::test_protected_primary[single_branch/commit_to_target]
Plant B (read the override before the topology guard: `_ctt = read_commit_to_target(meta)` first)
-> FAILED tests/core/test_mission_creation_family.py::test_mint_gate_never_reads_the_override_off_single_branch[lanes|coord|lanes_with_coord]

## T034 mint from orchestrator
Plant (write meta before the mint):
```
+    _write_create_meta(scaffold.feature_dir, meta_build.meta, mission)
     minted_mission_branch = _mint_protected_branch_for_topology(...)
-    _write_create_meta(scaffold.feature_dir, meta_build.meta, mission)
```
-> 14 failed: golden_protected test_protected_primary[single_branch/plain|retention|pr_bound], test_primary_unconfigured, test_primary_no_origin_head, test_configured_non_primary; golden_refusals test_mission_branch_exists, test_dirty_checkout_protected_mint, test_protected_target_without_commit, test_protected_recreate, test_refused_mint_orphan_retry, test_failed_create_restore_protected_mint; protected_single_branch test_status_transition_commits_to_mission_branch_not_target, test_implement_wrong_branch_refused_naming_mission_branch
Validation before commit: 402 passed, 8 skipped (family/decomposition/decisions/purity/source/golden*/cli golden/fallback/branch_coverage/invariants/probe_order/protected_single_branch/topology/policy_git_paths)

## T033 protection probe
GIT_TRACE once-proof (tests/core/test_mission_creation_probe_order.py::test_idempotent_recreate_resolves_protection_once):
path = SINGLE_BRANCH re-create on unprotected `topic` with planted genesis meta.json at kitty-specs/probe-recreate-<mid8>/.
Before T033 (captured at 7c201f9cc with temporary rev-parse --sq-quote markers around the resolver):
guard: `symbolic-ref --quiet --short refs/remotes/origin/HEAD` (ProtectionPolicy.resolve) + `symbolic-ref refs/remotes/origin/HEAD` (resolve_primary_branch); mint: the same pair again (indices 17-18).
After T033: the sequence equals the before-sequence minus exactly indices 17-18; `symbolic-ref refs/remotes/origin/HEAD` count == 1; PATH-shim flag for it == [False] (the guard, which has always run before the write).
Fresh create (no meta.json), protected main and unprotected topic: one resolution, after the scaffold write (shim flag [True]).
Pre-T033 run of the new test: FAILED test_idempotent_recreate_resolves_protection_once (sequence had the extra pair).

Plant A (mint not given the shared probe: drop `protection=protection` from the mint call)
-> FAILED tests/core/test_mission_creation_probe_order.py::test_idempotent_recreate_resolves_protection_once
Plant B (early resolution: `protection.is_protected(planning_branch)` right after making the probe, before the scaffold write)
-> FAILED probe_order::test_success_cell_probe_order, ::test_target_without_commit_stops_at_target_probe, ::test_dirty_checkout_stops_at_status_probe, ::test_branch_exists_stops_at_branch_probe, ::test_fresh_create_resolves_protection_once_after_the_scaffold_write[protected_main|unprotected_topic]
FINDING: the golden malformed_config_protection_shape cell stays GREEN under plant B. In that cell ProtectionConfigError
is raised by preflight_commit (_scaffold_mission_dir -> commit_helpers.preflight_commit -> _mission_scoped_policies ->
ProtectionPolicy.resolve), before any write, and the mint never runs; an earlier resolution raises the same error with
the same (empty) residue. The golden cell is therefore not the net for early resolution; the GIT_TRACE/PATH-shim tests are.
Unit tests: family::test_protection_probe_resolves_lazily_and_once, ::test_protection_probe_does_not_cache_a_failed_resolution, ::test_target_is_protected_wrapper_uses_a_one_shot_probe
Validation: 407 passed + probe_order 7 passed, 8 skipped.

## T035 rollback journal
No test passes `_coord_rollback_holder` (grep tests/: 0 hits) -> renamed to `_rollback_journal`, no list adapter.
Plant (wrapper ignores the journal):
```
-                coord_rollback=rollback_journal.coord,
+                coord_rollback=None,
```
-> FAILED tests/core/test_mission_creation_invariants.py::test_inv2_coordination_rollback_clears_dir_then_tears_down_then_deletes_branch
-> FAILED tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row5_coordination_commit_failure_rolls_back_coord_surface
-> FAILED tests/core/test_mission_creation_golden_refusals.py::test_failed_create_restore_coord
Unit: family::test_rollback_journal_records_the_first_coordination_surface. Validation: 409 passed, 8 skipped.

## T036 fan-out split: NO-OP
_build_create_result (mission_creation_commit.py) already computes created_file_sets(...) (the pure WP05 core) and
only then calls fanout_lifecycle_event_hosted for each event: the fan-out is already a separate effect after the
pure sets. Skipped per the WP ("If the fan-out is already a separate call, this subtask is a no-op").

## T037 structural checks (tests/core/test_mission_creation_family.py section 9)
Checks: test_coordination_routed_predicate_is_defined_once_and_never_inlined, test_meta_builder_never_calls_the_mint,
test_orchestrator_calls_the_mint_between_meta_build_and_write.
Planted controls (in-memory mutation): inline `topology in (COORD, LANES_WITH_COORD)` in scaffold; inline `is COORD or is LANES_WITH_COORD`;
second `is_coordination_routed` def in events; `_mc._mint_protected_branch_for_topology(...)` in `_build_create_meta`;
`_write_create_meta` before the mint in the orchestrator; `protection.is_protected(planning_branch)` in the orchestrator. All flagged.

## F3 routing hardening (tests/core/test_mission_creation_family.py)
New rules: alias-resolved reads + routed set (with planted tree included); Rule D `<module alias>.<routed|patched|foreign>`;
Rule B on aliased imports of foreign functions; Rule A on imports of any patched name under any alias; sys.modules access.
Controls (all planted in mission_creation_roots, in memory):
- test_planted_control_flags_a_module_alias_attribute_of_a_routed_name (`import specify_cli.core.git_ops as _g; _g.get_current_branch`)
- test_planted_control_flags_a_dotted_module_attribute_of_a_routed_name (`import specify_cli.core.git_ops; specify_cli.core.git_ops.get_current_branch`)
- test_planted_control_flags_an_aliased_import_of_a_foreign_function (`_refuse_live_duplicate as _rld`)
- test_planted_control_flags_a_read_of_an_aliased_foreign_function (`_list_mission_scaffolds as _lms; _lms(...)`)
- test_planted_control_flags_an_aliased_import_of_a_patched_but_unread_name[ULID|_emit_create_events|_commit_create_scaffold|_commit_coord_create_events|create_mission_core]
- test_planted_control_flags_an_aliased_read_of_a_newly_patched_name (`has_unborn_head as _hub`, patched += has_unborn_head)
- test_planted_control_flags_sys_modules_access_to_the_facade
Routed set unchanged; allowlist empty; all leaves clean.

## Final validation (HEAD d69a6df3d)
- frozen paths: `git diff c83e29ef2 -- tests/core/golden tests/core/_mission_create_golden.py tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/golden tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py tests/_support/git_template tests/_factories/__init__.py kitty-specs` -> empty
- covering set (42 files, -n 4 --dist loadfile): 513 passed, 2 skipped
- family/decisions/purity/source/probe_order + golden_* + CLI golden + fallback + branch_coverage + invariants + decomposition + protected_single_branch + topology + policy_git_paths + gates (no_dead_symbols, no_write_side_rederivation, single_mission_surface_resolver, core/test_adapters): 567 passed, 8 skipped
- make test-fast equivalent (.venv python, -n 4): 2275 passed, 8 skipped
- mypy: all 12 src/specify_cli/core/mission_creation*.py "no issues"
- ruff check src/specify_cli/core tests/core: clean; C901 (<=15): clean; ruff format --check --force-exclude on changed .py: clean
- complexity: _build_create_meta 5 (ruff mccabe), _write_create_meta 3, _create_mission_core_impl 4

## WP08 — Environment patch stack retired (commits df3f192eb..911547b66, lane-c)

Façade static sites 285 → 90; NFR-004 runtime budget applications 670 → 201 (515 collected tests). Open tension, handed to WP09 by orchestrator decision: 8 `get_current_branch` sites in test_feature_creation (2), test_mission_creation_fire_once (2) and test_mission_creation_specify_started (4) assert outcomes that exist only because the patch fakes `main` on a `master` checkout. Ruling: re-pin onto real `main` in WP09; each new expected value must reproduce on the unchanged base commit f0f3daa55, which proves it is pre-existing real behaviour and not a refactor artefact. Logged per C-005. Out-of-map edit: the census self-test sanity floor in `tests/_support/test_patch_census.py` was lowered (≥270 → ≥80) because the migration reduces the count by design. Implementer evidence follows.

# WP08 evidence

## T039 locate_project_root coverage-context proof (baseline d69a6df3d, before any edit)
```
COVERAGE_FILE=$SP/.coverage.lpr PWHEADLESS=1 .venv/bin/python -m pytest $(cat lpr-files.txt) --cov=specify_cli.core --cov-context=test --cov-report= -q -n 4 --dist loadfile -p no:randomly  # 171 passed
python ctx_query.py .coverage.lpr mission_creation.py:269 mission_creation_roots.py:66 mission_creation_roots.py:63
src/specify_cli/core/mission_creation.py:269 -> 3 contexts
    tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_blocks_create_feature_from_worktree_with_worktrees_fallback_hint|run
    tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_errors_when_project_root_not_found_human|run
    tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_errors_when_project_root_not_found_json|run
src/specify_cli/core/mission_creation_roots.py:66 -> 2 contexts
    tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_errors_when_project_root_not_found_human|run
    tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_errors_when_project_root_not_found_json|run
total contexts measured: 150
```
files: tests/agent/test_agent_feature.py tests/agent/test_create_feature_branch_unit.py tests/core/test_mission_creation_identity.py tests/core/test_mission_creation_topology.py tests/core/test_mission_creation_unborn_head.py tests/integration/test_issue_4863_merge_abort_no_state.py tests/integration/test_specify_plan_commit_boundary.py tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py tests/specify_cli/cli/commands/agent/test_mission_create.py tests/specify_cli/core/test_feature_creation.py tests/specify_cli/core/test_mission_creation_fire_once.py tests/specify_cli/core/test_mission_creation_placement.py tests/specify_cli/core/test_mission_creation_specify_started.py tests/_factories/test_make_mission_parity.py

## Planted break P1 (baseline, d69a6df3d): every create sees a branch the repo does not have
```diff
--- a/src/specify_cli/core/mission_creation_roots.py
+++ b/src/specify_cli/core/mission_creation_roots.py
     current_branch = _mc.get_current_branch(write_root)
+    current_branch = f"{current_branch}-planted" if current_branch else current_branch  # PLANTED-BREAK
```
`python plant.py <tree> P1 apply; pytest $(cat covering.txt) -n 4 --dist loadfile -p no:randomly -rf -o addopts=""`
base: 62 failed, 451 passed, 2 skipped (per-file list in P1-base.txt)

## T038 is_worktree_context — failing-first pair P2 (drop the worktree refusal)
```diff
-        if not allow_worktree_context and _mc.is_worktree_context(cwd):
+        if False and not allow_worktree_context and _mc.is_worktree_context(cwd):
```
`pytest <6 guard ids> -p no:xdist -p no:randomly -o addopts=""`
- base (patched to True): 5 failed, 1 passed — test_create_feature_rejects_worktree_context PASSED under the break (vacuous: `exit_code != 0` was satisfied by the missing git repo).
- after (real `git worktree add` cwd, no patch): 6 failed — all six guards red, including the formerly vacuous one.
Guards: decomposition::test_worktree_context_without_allow_flag_is_refused, feature_creation::test_worktree_context_raises,
parity::test_create_mission_core_worktree_guard_default_still_blocks, create_feature_branch_unit::test_create_feature_rejects_worktree_context,
agent_feature::test_blocks_create_feature_from_worktree_with_{main_repo_hint,worktrees_fallback_hint}.
Retired (dead): test_coordination_doctor.py x2 — create passes allow_worktree_context=True, `not allow_worktree_context and ...` short-circuits before the patched call.
Covering set + family + WP03 after T038: 621 passed, 10 skipped (8 = family "does not log" parametrized skips, pre-existing).

## T039 locate_project_root — factory CLI-path consumers (baseline)
`COVERAGE_FILE=.coverage.factory pytest tests/integration/test_coord_single_home_workflow.py tests/coordination/test_coord_mission_factory.py tests/core/test_mission_creation_decomposition.py --cov=specify_cli.core --cov-context=test -n 4` -> 119 passed
mission_creation.py:269 -> 0 contexts; mission_creation_roots.py:66 -> 0 contexts (roots.py:63 -> 72 contexts, i.e. the creates ran).
Retired per file (sites): coord_mission.py 1, create_feature_branch_unit 1, identity 1, topology 1, unborn_head 1, 4863 1, specify_plan_commit_boundary 1,
coord_topology_no_strand 1, test_mission_create 11, test_feature_creation 15, fire_once 2, placement 3, specify_started 4 (=43). Moved: agent_feature 2.

## T039 failing-first pair P5 (the "no project root" refusal is lost)
```diff
-            resolved_root = _mc.locate_project_root()
+            resolved_root = (_mc.locate_project_root() or Path.cwd())  # PLANTED-BREAK
```
base (core lookup patched to None): 2 failed / after (real lookup from bare tmp_path): 2 failed
(test_errors_when_project_root_not_found_{json,human}). Covering set after T039: 695 passed, 10 skipped (incl. factory consumers).

## T040 is_git_repo — guard re-proof, planted break P3 (drop the roots-leaf check)
```diff
-    if not _mc.is_git_repo(resolved_root):      # base
+    if False and not _mc.is_git_repo(resolved_root):
-    if not is_git_repo(resolved_root):           # after (de-routed)
+    if False and not is_git_repo(resolved_root):
```
`pytest decomposition::test_not_a_git_repo_raises feature_creation::test_not_git_repo_raises agent_feature::...::test_handles_git_errors -p no:xdist`
base: 3 failed / after: 3 failed. The covering guard test_not_a_git_repo_raises goes red (as required).
Retired (redundant, real repo answers True): 37 sites (feature_creation 15, test_mission_create 8, specify_started 4, fire_once 2,
identity/topology/unborn_head/4863/specify_plan/coord_no_strand 1 each); test_handles_git_errors False patch on a bare dir (real answers False).
Rewritten onto real repos (were faking a repo that did not exist): create_feature_branch_unit x2 sites, agent_feature x4 success tests,
feature_creation::test_not_git_repo_raises (real non-git dir).
Covering set + family + WP03 after T040: 621 passed, 10 skipped.

## T041 get_current_branch
P4 (drop the detached-HEAD refusal): `if False and (not current_branch or current_branch == "HEAD"):`
base: 2 failed, 1 passed (create_feature_branch_unit::test_create_feature_rejects_detached_head PASSED under the break — vacuous: no git repo)
after: 3 failed (all three guards red; the CLI guard now on a real `git checkout --detach` and asserting "detached HEAD").
P1 lane vs base: identical failure set (62 failed / 451 passed both), per-file counts equal.
REPORTED TENSION (not fixed, C-005): feature_creation::{test_happy_path_creates_directory_and_returns_result, test_result_created_files_populated},
fire_once::{test_mission_created_fanout_fires_exactly_once, test_mission_created_resume_does_not_double_fire},
specify_started::{appends_mission_created_and_specify_started, payload_references_spec_md, is_idempotent} (+ template_configuration_failure shares the fixture).
On real `main` they fail: status.events.jsonl not in feature_dir (it is on the coordination surface), created_files 4 != 3, MissionCreated rows 0.
Probe (base code): bare `git init` + fake 'main' -> meta.coordination_branch=kitty/mission-probe-… but `git branch -a` = [master] (branch never created), events in feature_dir.
Real `-b main` -> coordination branch exists, events not in feature_dir. 8 sites kept + annotated; get_current_branch stays routed.

## C-005 log (interaction -> behaviour replacements)
- tests/core/test_mission_creation_family.py::test_is_worktree_context_patch_intercepts_the_roots_leaf — `len(seen) == 1` (fake was called) → replaced by test_now_utc_iso_patch_intercepts_the_meta_leaf: `build.meta["created_at"] == <patched value>` (behavioural effect of a still-routed patch). The worktree-guard behaviour itself is pinned by 6 real-worktree guards (P2 pair).
- tests/agent/test_agent_feature.py::test_blocks_create_feature_from_worktree_with_* — Path.cwd + is_worktree_context mocks → real linked worktree / real .worktrees dir; output assertions unchanged.
- Strengthened (added, nothing removed): create_feature_branch_unit::test_create_feature_rejects_worktree_context (+"worktree" in output, no scaffold), ::test_create_feature_rejects_detached_head (+"detached HEAD"), feature_creation::test_worktree_context_raises / test_not_git_repo_raises (+no scaffold), test_detached_head_raises (match "branch" → "detached HEAD"), decomposition::test_worktree_context_without_allow_flag_is_refused (+no scaffold).

## T042 routing / rebind fold
Planted break: `_import_bound_names` returning `bound` only (rebind detection off) → both new controls red
(test_planted_control_flags_a_two_step_rebind_of_an_imported_module[False-function-local], [True-module-level]); restored → green.

## Census
Static façade (whole tree): 285 -> 90. Four names: is_worktree_context 73->0, locate_project_root 45->0, is_git_repo 44->0, get_current_branch 43->9 (8 tension + family intercept pin). now_utc_iso 2->3 (new meta-leaf intercept pin).
Source-namespace (whole tree) 242 -> 242; covering-set (42 files) 32 -> 32. Stdlib whole tree 454 -> 452 (Path.cwd mocks gone); covering 12 -> 10. Family-targeting unresolved: 0 -> 0.
Runtime over covering set (pytest -p tests._support.patch_census, 515 collected both): family bucket 618 -> 149; NFR-004 budget (family+source) 670 -> 201; total 841 -> 370; tests with patches 288 -> 232; max per test 50 -> 25.
By name (all namespaces): is_worktree_context 210->0, locate_project_root 217->120 (remainder = CLI namespace), get_current_branch 115->39, is_git_repo 89->3 (non-family).

## Validation
- covering set + family + WP03 (branch_coverage, invariants): 621 passed, 10 skipped (8 family "does not log" skips + 2 pre-existing)
- golden (4) + CLI golden + topology_fallback + decisions + purity + probe_order + family + tests/_support + coord factory consumers: 649 passed, 10 skipped, 1 failed (sanity floor) -> fixed: test_patch_census 62 passed
- fast tier (make test-fast dirs/markers via .venv python, -n 4): 2275 passed, 8 skipped
- ruff check + ruff format --check --force-exclude on changed files: clean; mypy mission_creation_roots.py: clean
- freeze set: git diff d69a6df3d -- <freeze set + WP03 files + kitty-specs> empty

## WP09 — Final migration and census (commits 076583738, ae5c409d2, 477a191ee, lane-c)

Final NFR-004 census (HEAD tool; fixed file set = 42 covering + 23 mission-touched = 65 files; base re-measured on f0f3daa55): (a) family static 182 → 10 (≤15 PASS); (a)+(b) static 214 → 38 (≤40 PASS); runtime (a)+(b) 569 → 77 (−86.5%, ≥70% PASS); stdlib 12/12 → 10/11 (outside budget); unresolved family-targeting 0. Routed set is now {build_mission_created_payload}. Out-of-map edits: tests/_support/test_patch_census.py (R2: count floor replaced by three fixed known-site invariants) and docs/api/mission-creation-internals.md (private identity inputs). Implementer evidence follows.

# WP09 evidence (lane-c; commits 076583738 R1, ae5c409d2 T043-T046/R2/R3, 477a191ee docs)

## Identity / clock seam (T044): Option B
`mission_creation_identity._mint_mission_id()` mints; `create_mission_core` (signature unchanged, C-006) delegates to
private `_create_mission_core_failure_atomic(..., _mission_id=None, _created_at=None)` (the former wrapper body) ->
`_create_mission_core_impl(..., _mission_id, _created_at)` -> `_build_create_meta(..., created_at=None)` (reads
kernel.clock.now_utc_iso when None, setdefault semantics unchanged). Option A rejected: one patch site per
determinism test (~7) + 7 create_mission_core stubs would exceed the (a) <= 15 budget. Facade keeps `ULID as ULID`
and `now_utc_iso` re-exports (no attribute removed from _FROZEN_FACADE_ATTRIBUTES); a future facade patch of either
is flagged by the routing check (patched & read by a leaf -> must route). NOT recorded in traces/design-decisions.md
(kitty-specs is off limits for this WP) -- orchestrator to copy.

## Per-name disposition (static family sites; base f0f3daa55 -> WP08 end 911547b66 -> final 477a191ee)
| name | base | WP08 | final | disposition | proof |
|---|---:|---:|---:|---|---|
| _commit_feature_file | 34 | 42 | 0 | dodges removed (real commit / disclosed skip); faults -> real pre-commit / commit-msg hooks | PB_A, PB_B |
| ULID | 11 | 12 | 0 | Option B identity input / derived from real mint / unneeded pins removed | PB_F, PB_N, PB_O, PB_E |
| get_current_branch | 20 | 9 | 0 | R1 real main (8); family pin retired with de-route | R1 base run, PB_K, PB_G |
| preflight_commit | 5 | 5 | 0 | real preflight on real repos | PB_F, PB_M |
| safe_commit | 4 | 4 | 0 | real safe_commit; placement reads the real refusal log | PB_D, PB_M |
| now_utc_iso | 2 | 3 | 0 | `_created_at` / `created_at` input; family pin -> unpatched injection test | parity PB_P |
| _commit_create_scaffold | 2 | 3 | 1 | coord_seed x2 -> real hook; invariants inv1 KEPT (disposable refusal cannot escape the real scaffold commit -- it is classified a skip -- so no real route) | PB_A, PB_E |
| _consume_pending_origin_if_present | 1 | 1 | 0 | real core.adapters pending-origin registry | PB_B |
| _commit_coord_create_events | 1 | 1 | 0 | R3: real hook refusing kitty/mission-* commits (new test test_rollback_covers_a_failed_coordination_commit) | PB_E |
| _emit_create_events | 1 | 1 | 1 | R3: KEPT (no real reproduction of a failure between seed and coordination commit) | PB_E |
| build_mission_created_payload | 0 | 1 | 1 | WP03 row 4 KEPT (no real route to a payload drift); the one routed name left | PB_O-file |
| subprocess.run (stdlib via facade) | 1 | 1 | 0 | T046: PATH without git (real launch failure) | PB_H |
| create_mission_core | 7 | 7 | 7 | KEPT: CLI stubs of the lazily imported public core | - |
| is_worktree_context / locate_project_root / is_git_repo | 93 | 0 | 0 | WP08 | - |
| **total (a)** | **182** | **90** | **10** | | |

De-routed in leaves (Rule C, routing set now {build_mission_created_payload}): get_current_branch (roots, commit,
rollback), now_utc_iso (meta), preflight_commit (scaffold), safe_commit/_commit_feature_file/_consume_pending_origin
(commit). Family pins test_now_utc_iso_/get_current_branch_/commit_feature_file_patch_intercepts_* retired with their
names; planted routing controls re-pointed (events leaf `_mc.build_mission_created_payload`, or patched set + name).
WP03 fault injections: branch_coverage row3 ULID -> `_mission_id`; row4 kept; invariants inv1 kept.
(b) sites removed: protected_single_branch resolve_primary_branch x5 (real repo answers main). default_topology_matrix
kept (2 b-sites, decision-level truth table).

## FINAL census (HEAD tool tests/_support/patch_census.py, fixed set = 42 covering + 23 mission-touched = 65 files)
| metric | base f0f3daa55 (re-measured) | final 477a191ee | budget | result |
|---|---:|---:|---|---|
| (a) family sites, whole tree | 182 | 10 | <= 15 | PASS |
| (b) source sites, 65 files | 32 | 28 | - | |
| (a)+(b) static | 214 | 38 | <= 40 | PASS |
| runtime (a)+(b) applications | 569 | 77 | >= 70% drop | PASS (-86.5%) |
| runtime family / source | 517 / 52 | 24 / 53 | | |
| stdlib bucket static (65 files) / runtime | 12 / 12 | 10 / 11 | outside | |
| collected tests (runtime run) | 637 (1 fail, pre-existing) | 1040 (1 fail, same) | | |
| unresolved family-targeting | 0 | 0 | | |
WP04 original grounding for reference: 277 sites (origin/main 9adc6880, count_patches2), WP08 end 90 / runtime 201 over 42 files.
Pre-existing red in both runs: tests/specify_cli/cli/commands/test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src
(hit in cli/commands/_commit_message.py; red on f0f3daa55 too; not this WP).
Commands: static `python -c 'wp09_patch_census.main()' --report --tests-root <tree>/tests --files-from fixedset.txt` (HEAD
copy); runtime `SPEC_KITTY_PATCH_CENSUS_OUT=... pytest <65 files present> -p tests._support.<plugin> -n 4 --dist loadfile`
(base: HEAD plugin copied into base tests/_support so it derives base src); merge `--runtime`.

## R1 (C-005, verified on f0f3daa55: rewritten files 28 passed on base, 28 on HEAD)
- feature_creation::test_happy_path_creates_directory_and_returns_result -- status log in feature_dir exists -> not in feature_dir; coord log (created_files) exists and is the only file committed on the coordination branch; coordination_branch_created True
- feature_creation::test_result_created_files_populated -- len==3 {spec,meta,README} -> exactly [.gitkeep, README.md, meta.json, spec.md, status.events.jsonl] + uncommitted [.gitkeep, README.md, meta.json, spec.md]
- fire_once::test_mission_created_fanout_fires_exactly_once / ::resume_does_not_double_fire -- log path feature_dir -> coordination log from created_files; counts (1/1) unchanged
- specify_started::appends_mission_created_and_specify_started / ::payload_references_spec_md -- same log re-point, values unchanged
- specify_started::is_idempotent -- replay into feature_dir -> into the coordination log's dir; values unchanged
- specify_started::template_configuration_failure -- unchanged + no .worktrees
No expected value differed between base and HEAD.

## C-005 log (interaction -> behaviour)
- feature_creation::test_meta_json_commit_noop_does_not_raise -- commit_mock.called -> real scaffold commit is HEAD (subject "Add scaffold for", meta.json in it, only spec.md uncommitted)
- feature_creation::..._hard_failure_raises_for_documentation_mission, checkout_restore::..._hard_failure_raises_and_restores_git_state / _message_names_step_and_git_error -- raising mock -> real pre-commit hook; same message/step/restore asserts
- checkout_restore::..._empty_changeset_surfaces_typed_already_exists -- mock raising SafeCommitStagedTreeUnchanged -> real duplicate identity (allow_duplicate, LANES); `__cause__ is boom` -> isinstance SafeCommitStagedTreeUnchanged
- fanout_commit_boundary::test_hard_commit_failure_* -- mock -> commit-msg hook; ::test_origin_commit_failure_* -- `calls == [scaffold, origin]` (mock) -> commit-msg hook record of the two real commit attempts; bind via real registry
- coord_seed::rollback_after_seed / reset_not_delete -- in-mock non-vacuity probes -> hook-recorded probes (worktree present / coord tip moved)
- placement x3 -- captured CommitTarget.ref -> real safe_commit refusal naming the destination ("expected 'design/coord-target'" / "protected branch 'main'") + checkout tip unchanged
- agent_feature x4 -- TEST_MISSION_ID pin -> real mint read back; + meta mid8 == mission_id[:8]
- parity override -- mission_id == frozen const -> valid ULID, mid8 == id[:8], slug == override-mission-<mid8>
- verbs duplicate -- frozen id/clock removed (guard keys on slug+type); + no second scaffold dir
- contract T004 -- 25 full creates -> 25 seam mints (format, unique, ordered) + 1 e2e create (mid8 derivation)
- scaffold_rollback tracking probe -- global subprocess.run raising OSError -> PATH without git
Nothing retired in test_agent_feature.py: its create tests became patch-free (stronger than retiring); golden CLI overlap unchanged.

## Sleeps removed
decomposition 1.1 s x2, idempotency_guard `_cross_mid8_bucket` 1.1 s x4 calls, scaffold_rollback 0.3 s -> injected later/distinct `_mission_id`.
`rg "time\.sleep\(1\.1\)" tests/` in covering set: none (identity 0.01 s thread-interleave sleeps are not identity collisions, kept).

## Family -> e2e smoke (unpatched)
1 flat/unprotected: checkout_restore::test_meta_json_commit_empty_changeset_surfaces_typed_already_exists (LANES, real commits); golden_flat
2 protected single_branch: protected_single_branch::test_create_json_reports_the_minted_checkout_branch (real CLI)
3 coord: feature_creation::test_happy_path_creates_directory_and_returns_result; coord_seed::test_protected_primary_still_seeds_coordination_surface
4 owned: agent_feature::TestCreateFeatureCommand::test_owned_checkout_creates_mission_in_real_linked_worktree
5 refusals/rollback: idempotency_guard::test_second_live_duplicate_create_is_refused_4033; coord_seed::test_rollback_covers_a_failed_coordination_commit
6 default topology: test_mission_create_topology_fallback.py (frozen golden)

## Failing-first pairs (fold 5): plant.py / runbreaks.sh in scratchpad; before = 911547b66 tests+src, after = 477a191ee
PB_A_scaffold_hard_failure_swallowed before: 4 failed, 36 passed in 105.53s (0:01:45)
PB_A_scaffold_hard_failure_swallowed after: 6 failed, 34 passed in 110.03s (0:01:50)
PB_B_origin_commit_failure_swallowed before: 1 failed, 4 passed in 4.09s
PB_B_origin_commit_failure_swallowed after: 1 failed, 4 passed in 4.45s
PB_C_empty_changeset_untyped before: 1 failed, 6 passed in 4.33s
PB_C_empty_changeset_untyped after: 1 failed, 6 passed in 4.44s
PB_D_destination_from_checkout before: 2 failed, 1 passed in 3.72s
PB_D_destination_from_checkout after: 2 failed, 1 passed in 3.70s
PB_E_coord_rollback_skipped before: 5 failed, 1 passed in 4.61s
PB_E_coord_rollback_skipped after: 5 failed, 1 passed in 4.63s
PB_F_mid8_misderived before: 9 failed, 68 passed, 8 warnings in 8.05s
PB_F_mid8_misderived after: 10 failed, 67 passed, 8 warnings in 8.01s
PB_G_fanout_twice before: 2 failed in 3.13s
PB_G_fanout_twice after: 2 failed in 3.77s
PB_H_tracking_probe_permits_delete before: 2 failed, 6 passed in 5.08s
PB_H_tracking_probe_permits_delete after: 2 failed, 6 passed in 4.74s
PB_I_duplicate_guard_off before: 2 failed, 67 passed in 16.13s
PB_I_duplicate_guard_off after: 3 failed, 66 passed in 14.29s
PB_K_specify_started_dropped before: 3 failed, 1 passed in 3.23s
PB_K_specify_started_dropped after: 3 failed, 1 passed in 3.76s
PB_M_target_branch_ignored before: 5 failed, 26 passed in 7.39s
PB_M_target_branch_ignored after: 7 failed, 24 passed in 7.86s
PB_N_branch_exists_untyped before: 1 failed, 27 passed in 25.57s
PB_N_branch_exists_untyped after: 1 failed, 27 passed in 26.24s
PB_O_corroboration_off before: 1 failed, 11 passed in 5.53s
PB_O_corroboration_off after: 1 failed, 11 passed in 5.20s
PB_P_factory_forks_schema before: 1 failed, 3 passed in 81.61s (0:01:21)
PB_P_factory_forks_schema after: 1 failed, 3 passed in 81.12s (0:01:21)
PB_Q_census_drops_string_targets before: 28 failed, 34 passed in 103.76s (0:01:43)
PB_Q_census_drops_string_targets after: 28 failed, 34 passed in 119.15s (0:01:59)

### failed nodes per break/tree
## PB_A_scaffold_hard_failure_swallowed.after
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_after_seed_removes_worktree_and_branch
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_hard_failure_raises_and_restores_git_state
tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted
tests/core/test_mission_creation_fanout_commit_boundary.py::test_hard_commit_failure_does_not_fanout_discarded_creation
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_hard_failure_message_names_step_and_git_error
tests/specify_cli/core/test_feature_creation.py::test_meta_json_commit_hard_failure_raises_for_documentation_mission
## PB_A_scaffold_hard_failure_swallowed.before
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_hard_failure_raises_and_restores_git_state
tests/core/test_mission_creation_fanout_commit_boundary.py::test_hard_commit_failure_does_not_fanout_discarded_creation
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_hard_failure_message_names_step_and_git_error
tests/specify_cli/core/test_feature_creation.py::test_meta_json_commit_hard_failure_raises_for_documentation_mission
## PB_B_origin_commit_failure_swallowed.after
tests/core/test_mission_creation_fanout_commit_boundary.py::test_origin_commit_failure_preserves_evidence_without_creation_fanout
## PB_B_origin_commit_failure_swallowed.before
tests/core/test_mission_creation_fanout_commit_boundary.py::test_origin_commit_failure_preserves_evidence_without_creation_fanout
## PB_C_empty_changeset_untyped.after
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_empty_changeset_surfaces_typed_already_exists
## PB_C_empty_changeset_untyped.before
tests/core/test_mission_create_checkout_restore.py::test_meta_json_commit_empty_changeset_surfaces_typed_already_exists
## PB_D_destination_from_checkout.after
tests/specify_cli/core/test_mission_creation_placement.py::test_meta_commit_destination_comes_from_seam_not_checkout
tests/specify_cli/core/test_mission_creation_placement.py::test_non_coord_single_branch_meta_commit_still_targets_target_branch
## PB_D_destination_from_checkout.before
tests/specify_cli/core/test_mission_creation_placement.py::test_meta_commit_destination_comes_from_seam_not_checkout
tests/specify_cli/core/test_mission_creation_placement.py::test_non_coord_single_branch_meta_commit_still_targets_target_branch
## PB_E_coord_rollback_skipped.after
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_after_seed_removes_worktree_and_branch
tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[inside_write_dir_seed]
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[emit_create_events]
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_a_failed_coordination_commit
## PB_E_coord_rollback_skipped.before
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_after_seed_removes_worktree_and_branch
tests/core/test_mission_create_coord_seed_rollback.py::test_preexisting_coordination_branch_is_reset_not_deleted
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[inside_write_dir_seed]
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[emit_create_events]
tests/core/test_mission_create_coord_seed_rollback.py::test_rollback_covers_every_seed_injection_point[commit_coord_create_events]
## PB_F_mid8_misderived.after
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_with_json_output
tests/core/test_slug_validator_unit.py::TestCreateMissionCoreSlugValidation::test_digit_prefix_slug_accepted
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_with_human_output
tests/contract/test_mission_id_creation_contract.py::test_t001_distinct_mission_ids_across_back_to_back_creations
tests/contract/test_mission_id_creation_contract.py::test_t002_creation_succeeds_with_network_blocked
tests/_factories/test_make_mission_parity.py::test_make_mission_applies_explicit_overrides_on_production_shaped_meta
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_allows_feature_creation_from_any_branch
tests/contract/test_mission_id_creation_contract.py::test_t003_mission_id_is_valid_ulid_and_immutable
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_on_primary_branch
tests/contract/test_mission_id_creation_contract.py::test_t004_hundred_sequential_creations_all_distinct
## PB_F_mid8_misderived.before
tests/contract/test_mission_id_creation_contract.py::test_t001_distinct_mission_ids_across_back_to_back_creations
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_with_json_output
tests/core/test_slug_validator_unit.py::TestCreateMissionCoreSlugValidation::test_digit_prefix_slug_accepted
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_with_human_output
tests/contract/test_mission_id_creation_contract.py::test_t002_creation_succeeds_with_network_blocked
tests/contract/test_mission_id_creation_contract.py::test_t003_mission_id_is_valid_ulid_and_immutable
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_allows_feature_creation_from_any_branch
tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_creates_feature_on_primary_branch
tests/contract/test_mission_id_creation_contract.py::test_t004_hundred_sequential_creations_all_distinct
## PB_G_fanout_twice.after
tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_fanout_fires_exactly_once
tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_resume_does_not_double_fire
## PB_G_fanout_twice.before
tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_fanout_fires_exactly_once
tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_resume_does_not_double_fire
## PB_H_tracking_probe_permits_delete.after
tests/core/test_mission_create_scaffold_rollback.py::test_rollback_never_deletes_tracked_content
tests/core/test_mission_create_scaffold_rollback.py::test_tracking_probe_launch_failure_preserves_scaffold
## PB_H_tracking_probe_permits_delete.before
tests/core/test_mission_create_scaffold_rollback.py::test_rollback_never_deletes_tracked_content
tests/core/test_mission_create_scaffold_rollback.py::test_tracking_probe_launch_failure_preserves_scaffold
## PB_I_duplicate_guard_off.after
tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033
tests/core/test_mission_creation_decomposition.py::test_live_duplicate_raises_already_exists
tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py::test_specify_twice_for_same_slug_fails_closed_with_structured_error
## PB_I_duplicate_guard_off.before
tests/core/test_mission_create_idempotency_guard.py::test_second_live_duplicate_create_is_refused_4033
tests/core/test_mission_creation_decomposition.py::test_live_duplicate_raises_already_exists
## PB_K_specify_started_dropped.after
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_appends_mission_created_and_specify_started
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_specify_started_payload_references_spec_md
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_specify_started_is_idempotent
## PB_K_specify_started_dropped.before
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_appends_mission_created_and_specify_started
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_specify_started_payload_references_spec_md
tests/specify_cli/core/test_mission_creation_specify_started.py::test_mission_create_specify_started_is_idempotent
## PB_M_target_branch_ignored.after
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_current_branch_2x
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_current_branch_master
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_custom_branch
tests/agent/test_create_feature_branch_unit.py::test_create_feature_2x_wins_even_when_main_coexists
tests/specify_cli/core/test_feature_creation.py::test_target_branch_defaults_to_current
tests/specify_cli/core/test_feature_creation.py::test_meta_json_commit_noop_does_not_raise
tests/specify_cli/core/test_feature_creation.py::test_meta_json_commit_hard_failure_raises_for_documentation_mission
## PB_M_target_branch_ignored.before
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_current_branch_2x
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_current_branch_master
tests/agent/test_create_feature_branch_unit.py::test_create_feature_records_custom_branch
tests/agent/test_create_feature_branch_unit.py::test_create_feature_2x_wins_even_when_main_coexists
tests/specify_cli/core/test_feature_creation.py::test_target_branch_defaults_to_current
## PB_N_branch_exists_untyped.after
tests/core/test_mission_create_protected_single_branch.py::test_existing_mission_branch_name_refuses_create
## PB_N_branch_exists_untyped.before
tests/core/test_mission_create_protected_single_branch.py::test_existing_mission_branch_name_refuses_create
## PB_O_corroboration_off.after
tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row3_topology_corroboration_failure_refuses
## PB_O_corroboration_off.before
tests/core/test_mission_creation_branch_coverage.py::TestMetaAndEventBranches::test_row3_topology_corroboration_failure_refuses
## PB_P_factory_forks_schema.after
tests/_factories/test_make_mission_parity.py::test_make_mission_meta_is_byte_identical_to_direct_core_call
## PB_P_factory_forks_schema.before
tests/_factories/test_make_mission_parity.py::test_make_mission_meta_is_byte_identical_to_direct_core_call
## PB_Q_census_drops_string_targets.after
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[string_literal]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[fstring_over_constant]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[string_concat]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[monkeypatch_setattr_string]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[attribute_chain]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[monkeypatch_delattr_string]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[mocker_patch]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[alias_dunder_name_fstring]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[future_sibling_module]
tests/_support/test_patch_census.py::test_by_name_by_file_and_by_namespace_helpers
tests/_support/test_patch_census.py::test_unrelated_module_patch_is_not_counted
tests/_support/test_patch_census.py::test_same_name_on_unrelated_module_is_not_family_and_needs_read_names
tests/_support/test_patch_census.py::test_laundered_source_namespace_stdlib_and_process_global_patches_are_bucketed
tests/_support/test_patch_census.py::test_restricted_to_limits_the_report_to_an_explicit_file_list
tests/_support/test_patch_census.py::test_loop_over_literal_family_targets_resolves_to_sites_and_unresolved_loop_over_family_is_suspect
tests/_support/test_patch_census.py::test_unresolved_loop_over_family_literal_is_a_suspect
tests/_support/test_patch_census.py::test_parametrized_literal_targets_resolve_per_row
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest.mock import patch as p-p("{F}.aliased_patch")-expected0]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest import mock as um-um.patch("{F}.aliased_mod")-expected1]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest import mock as um\nalias = um.patch-alias("{F}.reassigned")-expected6]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[-mocker.patch("{F}.mocker_direct")-expected7]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[-mp = mocker\n    mp.patch("{F}.mocker_alias")-expected8]
tests/_support/test_patch_census.py::test_function_local_alias_import_is_scoped_and_client_patch_is_still_ignored
tests/_support/test_patch_census.py::test_family_prefix_requires_a_name_boundary
tests/_support/test_patch_census.py::test_patched_names_on_returns_first_chain_segments_for_exactly_that_module
tests/_support/test_patch_census.py::test_patched_names_on_never_returns_placeholders
tests/_support/test_patch_census.py::test_cli_report_text_and_json_and_files_from
tests/_support/test_patch_census.py::test_repository_scan_finds_the_known_permanent_facade_sites
## PB_Q_census_drops_string_targets.before
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[string_literal]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[fstring_over_constant]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[string_concat]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[monkeypatch_setattr_string]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[attribute_chain]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[monkeypatch_delattr_string]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[mocker_patch]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[alias_dunder_name_fstring]
tests/_support/test_patch_census.py::test_each_supported_form_is_counted_exactly_once_per_site[future_sibling_module]
tests/_support/test_patch_census.py::test_by_name_by_file_and_by_namespace_helpers
tests/_support/test_patch_census.py::test_unrelated_module_patch_is_not_counted
tests/_support/test_patch_census.py::test_same_name_on_unrelated_module_is_not_family_and_needs_read_names
tests/_support/test_patch_census.py::test_laundered_source_namespace_stdlib_and_process_global_patches_are_bucketed
tests/_support/test_patch_census.py::test_restricted_to_limits_the_report_to_an_explicit_file_list
tests/_support/test_patch_census.py::test_loop_over_literal_family_targets_resolves_to_sites_and_unresolved_loop_over_family_is_suspect
tests/_support/test_patch_census.py::test_unresolved_loop_over_family_literal_is_a_suspect
tests/_support/test_patch_census.py::test_parametrized_literal_targets_resolve_per_row
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest.mock import patch as p-p("{F}.aliased_patch")-expected0]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest import mock as um-um.patch("{F}.aliased_mod")-expected1]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[from unittest import mock as um\nalias = um.patch-alias("{F}.reassigned")-expected6]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[-mocker.patch("{F}.mocker_direct")-expected7]
tests/_support/test_patch_census.py::test_aliased_patch_and_mock_bindings_are_counted[-mp = mocker\n    mp.patch("{F}.mocker_alias")-expected8]
tests/_support/test_patch_census.py::test_function_local_alias_import_is_scoped_and_client_patch_is_still_ignored
tests/_support/test_patch_census.py::test_family_prefix_requires_a_name_boundary
tests/_support/test_patch_census.py::test_patched_names_on_returns_first_chain_segments_for_exactly_that_module
tests/_support/test_patch_census.py::test_patched_names_on_never_returns_placeholders
tests/_support/test_patch_census.py::test_cli_report_text_and_json_and_files_from
tests/_support/test_patch_census.py::test_repository_facade_sites_meet_the_sanity_floor

### plant.py
```python
"""plant.py <tree> <variant before|after> <break> apply|revert"""
import sys
from pathlib import Path
tree, variant, name, action = sys.argv[1:5]
C = "src/specify_cli/core/"
B = {
 "PB_A_scaffold_hard_failure_swallowed": [(C+"mission_creation_commit.py", '        if outcome == "raise":\n            raise RuntimeError(', '        if outcome == "raise" and False:  # PLANTED\n            raise RuntimeError(')],
 "PB_B_origin_commit_failure_swallowed": [(C+"mission_creation_commit.py", '        except Exception as exc:\n            raise RuntimeError(f"origin-ticket binding commit failed: {exc}") from exc', '        except Exception as exc:  # PLANTED\n            pass')],
 "PB_C_empty_changeset_untyped": [(C+"mission_creation_commit.py", '        if outcome == "already_exists":', '        if outcome == "already_exists" and False:  # PLANTED')],
 "PB_D_destination_from_checkout": [(C+"mission_creation_commit.py", "    seam_target = create_time_target if create_time_target is not None else", {"before": "    seam_target = CommitTarget(ref=_mc.get_current_branch(repo_root) or '')  # PLANTED\n    _unused = create_time_target if create_time_target is not None else", "after": "    seam_target = CommitTarget(ref=get_current_branch(repo_root) or '')  # PLANTED\n    _unused = create_time_target if create_time_target is not None else"})],
 "PB_E_coord_rollback_skipped": [(C+"mission_creation.py", "                coord_rollback=rollback_journal.coord,", "                coord_rollback=None,  # PLANTED")],
 "PB_F_mid8_misderived": [(C+"mission_creation.py", '    mid8 = resolve_mid8("", mission_id=mission_id)', '    mid8 = resolve_mid8("", mission_id=mission_id)[::-1]  # PLANTED')],
 "PB_G_fanout_twice": [(C+"mission_creation_commit.py", "        fanout_lifecycle_event_hosted(created_event, log_path=log_path)\n", "        fanout_lifecycle_event_hosted(created_event, log_path=log_path)\n        fanout_lifecycle_event_hosted(created_event, log_path=log_path)  # PLANTED\n")],
 "PB_H_tracking_probe_permits_delete": [(C+"mission_creation_rollback.py", "        return bool(tracked_paths(repo_root, pathspecs=(str(path),)))", "        return False and bool(tracked_paths(repo_root, pathspecs=(str(path),)))  # PLANTED")],
 "PB_I_duplicate_guard_off": [(C+"mission_creation_duplicates.py", "    if allow_duplicate:\n        return\n    effective_mission_type", "    if True:  # PLANTED\n        return\n    effective_mission_type")],
 "PB_K_specify_started_dropped": [(C+"mission_creation_events.py", "            event_type=SPECIFY_STARTED,\n", "            event_type=SPECIFY_STARTED + '_PLANTED',\n")],
 "PB_M_target_branch_ignored": [(C+"mission_creation.py", "    planning_branch = target_branch if target_branch else current_branch", '    planning_branch = target_branch if target_branch else "main"  # PLANTED')],
 "PB_N_branch_exists_untyped": [(C+"mission_creation_protected_mint.py", '    if decision.kind == "branch_exists":', '    if decision.kind == "branch_exists" and False:  # PLANTED')],
 "PB_O_corroboration_off": [(C+"mission_creation_meta.py", "        if corroborated is not topology:", "        if corroborated is not topology and False:  # PLANTED")],
 "PB_Q_census_drops_string_targets": [("tests/_support/patch_census.py", "        if _DOTTED.match(text):\n            self._emit_dotted(node, text, form)", "        if False and _DOTTED.match(text):  # PLANTED\n            self._emit_dotted(node, text, form)")],
 "PB_P_factory_forks_schema": [("tests/_factories/__init__.py", "    return create_mission_core(repo_root, mission_slug, topology=topology, **overrides)", '    return create_mission_core(repo_root, mission_slug, topology=topology, **{**overrides, "pr_bound": True})  # PLANTED')],
}
for rel, old, new in B[name]:
    if isinstance(new, dict): new = new[variant]
    p = Path(tree) / rel; s = p.read_text()
    if action == "apply":
        assert old in s, (rel, old[:60]); p.write_text(s.replace(old, new, 1))
    else:
        assert new in s, (rel, "not planted"); p.write_text(s.replace(new, old, 1))
print(action, name, variant)
```

## Static census text (base / WP08 / final)
```
=== /tmp/claude-0/-home-user-spec-kitty/2799d0a2-d598-577c-b077-f68d631cfcdf/scratchpad/base-f0f3
STATIC PATCH CENSUS (reporting tool, not a gate)

family facade sites (bucket a, whole tree): 182
  files: 32   distinct names: 15
  forms: {'patch': 149, 'setattr': 33}
  by name:
      48  is_worktree_context
      34  _commit_feature_file
      24  locate_project_root
      21  is_git_repo
      20  get_current_branch
      11  ULID
       7  create_mission_core
       5  preflight_commit
       4  safe_commit
       2  _commit_create_scaffold
       2  now_utc_iso
       1  _commit_coord_create_events
       1  _consume_pending_origin_if_present
       1  _emit_create_events
       1  subprocess.run
  by namespace:
     182  specify_cli.core.mission_creation
  by file:
      46  tests/specify_cli/cli/commands/agent/test_mission_create.py
      32  tests/agent/test_agent_feature.py
      11  tests/specify_cli/core/test_feature_creation.py
      10  tests/agent/test_create_feature_branch_unit.py
       9  tests/specify_cli/core/test_mission_creation_placement.py
       6  tests/core/test_mission_create_coord_seed_rollback.py
       5  tests/core/test_mission_creation_identity.py
       5  tests/core/test_mission_creation_topology.py
       5  tests/integration/test_issue_4863_merge_abort_no_state.py
       5  tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
       4  tests/_factories/test_make_mission_parity.py
       4  tests/contract/test_mission_id_creation_contract.py
       4  tests/core/test_mission_creation_unborn_head.py
       4  tests/integration/test_specify_plan_commit_boundary.py
       4  tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
       3  tests/core/test_mission_create_checkout_restore.py
       3  tests/core/test_mission_creation_decomposition.py
       3  tests/core/test_mission_creation_fanout_commit_boundary.py
       2  tests/_factories/coord_mission.py
       2  tests/core/test_mission_create_protected_single_branch.py
       2  tests/specify_cli/cli/commands/test_coordination_doctor.py
       2  tests/specify_cli/cli/commands/test_selector_resolution.py
       2  tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
       1  tests/core/test_mission_create_coord_status_placement.py
       1  tests/core/test_mission_create_coord_status_seed.py
    ... 7 more
whole tree, other buckets: source 241, stdlib 426, unrelated-namespace same-name 996

source-namespace sites (bucket b, 65-file list): 32
  by namespace:
       8  specify_cli.core.git_ops
       5  charter.activation.mission_type_profiles
       4  specify_cli.lanes.branch_naming
       4  specify_cli.mission_metadata
       3  specify_cli.status
       2  specify_cli.missions._create
       2  specify_cli.runtime.resolver
       1  specify_cli.coordination.commit_router
       1  specify_cli.coordination.teardown
       1  specify_cli.core.paths
       1  specify_cli.git.protection_policy
  by name:
       8  resolve_primary_branch
       5  resolve_mission_type_context
       4  resolve_mid8
       4  write_meta
       3  emit_mission_created_local
       2  ensure_coordination_branch
       2  resolve_configured_template
       1  ProtectionPolicy.resolve
       1  commit_for_mission
       1  load_meta_fail_closed
       1  teardown_coordination_topology

stdlib process-global sites (own bucket, outside NFR-004; 65-file list): 12
      10  check_output
       2  Path.cwd
same-name patches on unrelated namespaces (not budgeted; 65-file list): 108

unresolved patch targets (whole tree): 47; that may target the family: 0
=== /tmp/claude-0/-home-user-spec-kitty/2799d0a2-d598-577c-b077-f68d631cfcdf/scratchpad/before-9115
STATIC PATCH CENSUS (reporting tool, not a gate)

family facade sites (bucket a, whole tree): 90
  files: 26   distinct names: 13
  forms: {'setattr': 29, 'patch': 61}
  by name:
      42  _commit_feature_file
      12  ULID
       9  get_current_branch
       7  create_mission_core
       5  preflight_commit
       4  safe_commit
       3  _commit_create_scaffold
       3  now_utc_iso
       1  _commit_coord_create_events
       1  _consume_pending_origin_if_present
       1  _emit_create_events
       1  build_mission_created_payload
       1  subprocess.run
  by namespace:
      90  specify_cli.core.mission_creation
  by file:
      15  tests/specify_cli/core/test_feature_creation.py
      12  tests/agent/test_agent_feature.py
       8  tests/specify_cli/cli/commands/agent/test_mission_create.py
       7  tests/specify_cli/core/test_mission_creation_specify_started.py
       5  tests/core/test_mission_create_coord_seed_rollback.py
       5  tests/specify_cli/core/test_mission_creation_fire_once.py
       4  tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
       3  tests/core/test_mission_create_checkout_restore.py
       3  tests/core/test_mission_creation_family.py
       3  tests/core/test_mission_creation_fanout_commit_boundary.py
       3  tests/specify_cli/core/test_mission_creation_placement.py
       2  tests/_factories/test_make_mission_parity.py
       2  tests/agent/test_create_feature_branch_unit.py
       2  tests/contract/test_mission_id_creation_contract.py
       2  tests/core/test_mission_create_protected_single_branch.py
       2  tests/core/test_mission_creation_branch_coverage.py
       2  tests/specify_cli/cli/commands/test_selector_resolution.py
       2  tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
       1  tests/core/test_mission_create_scaffold_rollback.py
       1  tests/core/test_mission_creation_identity.py
       1  tests/core/test_mission_creation_invariants.py
       1  tests/core/test_mission_creation_topology.py
       1  tests/core/test_slug_validator_unit.py
       1  tests/integration/test_issue_4863_merge_abort_no_state.py
       1  tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
    ... 1 more
whole tree, other buckets: source 242, stdlib 452, unrelated-namespace same-name 998

source-namespace sites (bucket b, 65-file list): 33
  by namespace:
       9  specify_cli.core.git_ops
       5  charter.activation.mission_type_profiles
       4  specify_cli.lanes.branch_naming
       4  specify_cli.mission_metadata
       3  specify_cli.status
       2  specify_cli.missions._create
       2  specify_cli.runtime.resolver
       1  specify_cli.coordination.commit_router
       1  specify_cli.coordination.teardown
       1  specify_cli.core.paths
       1  specify_cli.git.protection_policy
  by name:
       9  resolve_primary_branch
       5  resolve_mission_type_context
       4  resolve_mid8
       4  write_meta
       3  emit_mission_created_local
       2  ensure_coordination_branch
       2  resolve_configured_template
       1  ProtectionPolicy.resolve
       1  commit_for_mission
       1  load_meta_fail_closed
       1  teardown_coordination_topology

stdlib process-global sites (own bucket, outside NFR-004; 65-file list): 10
      10  check_output
same-name patches on unrelated namespaces (not budgeted; 65-file list): 108

unresolved patch targets (whole tree): 47; that may target the family: 0
=== /home/user/spec-kitty/.worktrees/mission-creation-degod-01M44467-lane-c
STATIC PATCH CENSUS (reporting tool, not a gate)

family facade sites (bucket a, whole tree): 10
  files: 6   distinct names: 4
  forms: {'setattr': 8, 'patch': 2}
  by name:
       7  create_mission_core
       1  _commit_create_scaffold
       1  _emit_create_events
       1  build_mission_created_payload
  by namespace:
      10  specify_cli.core.mission_creation
  by file:
       4  tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
       2  tests/specify_cli/cli/commands/test_selector_resolution.py
       1  tests/core/test_mission_create_coord_seed_rollback.py
       1  tests/core/test_mission_creation_branch_coverage.py
       1  tests/core/test_mission_creation_invariants.py
       1  tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py
whole tree, other buckets: source 237, stdlib 452, unrelated-namespace same-name 998

source-namespace sites (bucket b, 65-file list): 28
  by namespace:
       5  charter.activation.mission_type_profiles
       4  specify_cli.core.git_ops
       4  specify_cli.lanes.branch_naming
       4  specify_cli.mission_metadata
       3  specify_cli.status
       2  specify_cli.missions._create
       2  specify_cli.runtime.resolver
       1  specify_cli.coordination.commit_router
       1  specify_cli.coordination.teardown
       1  specify_cli.core.paths
       1  specify_cli.git.protection_policy
  by name:
       5  resolve_mission_type_context
       4  resolve_mid8
       4  resolve_primary_branch
       4  write_meta
       3  emit_mission_created_local
       2  ensure_coordination_branch
       2  resolve_configured_template
       1  ProtectionPolicy.resolve
       1  commit_for_mission
       1  load_meta_fail_closed
       1  teardown_coordination_topology

stdlib process-global sites (own bucket, outside NFR-004; 65-file list): 10
      10  check_output
same-name patches on unrelated namespaces (not budgeted; 65-file list): 108

unresolved patch targets (whole tree): 47; that may target the family: 0
```
## Runtime base
```
RUNTIME PATCH APPLICATIONS
collected tests: 637   outcomes: {'call:passed': 634, 'call:skipped': 2, 'call:failed': 1}
NFR-004 budget applications (family + source): 569
applications total (all buckets, informational): 740   by bucket: {'family': 517, 'namespace_other': 159, 'source': 52, 'stdlib': 12}
tests with patches: 279   max in one test: 50
  by name:
     195  locate_project_root
     185  is_worktree_context
      92  get_current_branch
      85  _commit_feature_file
      65  is_git_repo
      15  resolve_primary_branch
      12  ULID
      10  check_output
      10  preflight_commit
       9  create_mission_core
       9  safe_commit
       8  ProtectionPolicy.resolve
       7  write_meta
       6  resolve_mission_type_context
       4  emit_mission_created_local
       4  resolve_mid8
       3  now_utc_iso
       3  resolve_configured_template
       3  tracked_paths
       2  Path.cwd
       2  _commit_create_scaffold
       2  ensure_coordination_branch
       2  status_entries
       1  _commit_coord_create_events
       1  _consume_pending_origin_if_present
    ... 5 more
```
## Runtime final
```
RUNTIME PATCH APPLICATIONS
collected tests: 1040   outcomes: {'call:passed': 1029, 'call:skipped': 10, 'call:failed': 1}
NFR-004 budget applications (family + source): 77
applications total (all buckets, informational): 247   by bucket: {'namespace_other': 159, 'source': 53, 'family': 24, 'stdlib': 11}
tests with patches: 180   max in one test: 13
  by name:
     121  locate_project_root
      32  get_current_branch
      13  resolve_primary_branch
      11  ProtectionPolicy.resolve
      10  check_output
      10  create_mission_core
       7  write_meta
       6  resolve_mission_type_context
       4  emit_mission_created_local
       4  is_git_repo
       4  resolve_mid8
       3  resolve_configured_template
       3  tracked_paths
       2  <module>
       2  ensure_coordination_branch
       2  safe_commit
       2  status_entries
       1  ULID
       1  _commit_create_scaffold
       1  _emit_create_events
       1  build_mission_created_payload
       1  commit_for_mission
       1  is_worktree_context
       1  load_meta_fail_closed
       1  now_utc_iso
    ... 3 more
```

## Validation
- validation set (42 covering + WP03 + golden x4 + CLI golden + topology_fallback + family/decisions/purity/probe_order + tests/_support + dead-symbols + patch-targets-live + changed files; 58 paths): 1157 passed, 12 skipped
- post-format: fixed-set runtime run 1029 passed, 10 skipped, 1 pre-existing fail (commit_recipes); gates rerun (no_dead_symbols, tasks_patch_targets_live, tests/_support, decisions, purity, probe_order): 450 passed, 2 skipped
- fast tier (make test-fast dirs/markers via .venv python, -n 4): 2275 passed, 8 skipped
- ruff check + ruff format --check --force-exclude on changed files: clean; mypy changed src (7 files): clean
- freeze set `git diff 911547b66 -- <freeze set> kitty-specs`: empty
- out-of-map edits: tests/_support/test_patch_census.py (R2, sanctioned), docs/api/mission-creation-internals.md (identity seam paragraph, routing example)

## WP09 census correction (reviewer, binding over the implementer's base numbers above)

The implementer re-measured the base on a f0f3daa55 tree that still had the three rewritten R1 test files copied in, so its base column is too low. The reviewer re-ran the same HEAD tool on a clean f0f3daa55 over the same 65-file fixed set:

| Measure | Base (clean f0f3daa55) | Final (HEAD) | NFR-004 budget |
|---|---|---|---|
| (a) family static sites | **279** | **10** | ≤ 15: PASS |
| (a)+(b) static sites | **311** | **38** | ≤ 40: PASS |
| Runtime (a)+(b) applications | **670** (637 collected) | **77** | ≥ 70% drop: PASS (−88.5%) |
| Unresolved family-targeting | 0 | 0 | — |

Corrected per-name base values include `_commit_feature_file` 41, `get_current_branch` 42 and `is_worktree_context` 72, which match the WP04 baseline. The PR must use these numbers.

## Closeout — development-assist test verdicts (commits 4b89ca8f5, 30b1e7481, lane-c)

| Test asset | Verdict | Reason |
|---|---|---|
| Golden matrix (harness, 4 modules, 4 snapshots) | keep | Regression net for create behaviour; regenerate only for an intended behaviour change (follow-up: #5676, #5704) |
| CLI golden + snapshot | keep | Pins the command surface |
| Topology fallback pin | keep | Decision-level pin for follow-up: #5707 |
| Branch coverage + invariants | keep | Real-repo tests of real behaviour, covered nowhere else |
| Decisions, purity, probe-order tests | keep | Unit tests of the pure cores, plus permanent structural guards |
| Family checks + source helper | keep | Public-surface, routing, cycle and logger guards. Section 5 "unexpected definitions" may resist future refactors; candidate for the suite-wide audit, not weakened |
| Patch census + self-test | keep | Reporting tool, not a gate |

Mission labels on added lines: 196 → 21 (the 21 remaining belong to other missions or are test data). No issue-named test file was added.

**Independent proof that behaviour is byte-identical:** a serial golden regeneration (`SPEC_KITTY_REGEN_GOLDEN=1 -n0`) on the final code reproduced every one of the 75 cells identically; only the `base_commit` stamps changed (restored afterwards).
