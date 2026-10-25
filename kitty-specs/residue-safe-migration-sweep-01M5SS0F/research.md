# Research: Residue-safe migration sweep and fabricated-identity audit

Grounding came from two squads: the alignment and scope squad, and the post-specify adversarial review. Both read and probed `main` @ 3d6754b8, and their probes ran with `.venv/bin/python -I` in temporary git repositories.

## R-01 Successor selection on existing projects

- **Decision**: a successor's `detect()` returns False when its predecessor is settled. "Settled" uses the same view selection uses: a `success` record in the predecessor's partition (`registry.migration_settled`), or pending settlement by first ledger adoption (`adoption_settled_ids`).
- **Rationale**: a new migration id is unrecorded, so ledger-diff selects it on every ledger-era project. Without the gate, every project would re-run the whole sweep. A ledger-reading `detect()` has precedent in `m_4_0_0rc6_charter_pack_cutover._is_first_application` and `m_3_1_1_charter_rename`. Using the selection view keeps `upgrade --dry-run` and the live run in agreement. The dry run writes no adoption backfill, so a raw ledger read would preview a re-sweep the live run never does.
- **Alternatives considered**: recording a no-op `success` (misreports "applied"); editing the adoption backfill (frozen, NFR-001); no gate at all (re-sweeps every project).

## R-02 Successor placement

- **Decision**: each successor goes immediately after its predecessor in `order_manifest.txt`, with the same `target_version` and a `# tie:` annotation.
- **Rationale**: later steps read what the predecessor wrote. `3.0.0_canonical_context` (via `migration/runner._discover_features`) and `3.2.0a4_normalize_mission_lifecycle` need 2.0.6's baseline `meta.json`. `4.0.0rc8_retire_stale_mission_template_forks` expects 2.0.6's runtime-asset move. `test_migration_order_manifest.py` accepts ties. The #6589 supersession test requires only that the successor comes after the superseded id.
- **Alternatives considered**: a 4.0.0rc8 slot at the end (breaks the 3.0.0 and 3.2.0a4 inputs for pre-2.0.6 projects).

## R-03 How each successor reuses the frozen module

- **Decision**:
  - **0.9.0 and 0.9.1**: subclass the shipped class and override the per-folder predicates (`_is_legacy_format` / `_has_remaining_lane_dirs` and the walkers that call them), so every writer stays in the frozen module.
  - **2.0.6 and 3.1.1**: the per-folder walk is a module-level function, so their successors re-implement `detect()`/`apply()` over a residue-filtered walk. 2.0.6 calls the frozen helpers (`_migrate_runtime_assets`, `_cleanup_legacy_worktree_assets`, `_has_legacy_worktree_assets`, `_feature_requires_repair`, `_repair_feature`, `check_stale_legacy_assets`). 3.1.1 calls `_needs_normalisation` and keeps its own snapshot write.
- **Rationale**: importing a shipped module does not change its bytes, and `m_3_2_0a4_safe_globalize_commands` already imports from a shipped module. The decorator is cached, so a subclass import does not register the parent twice.
- **Risk**: 3.1.1's write lives inline in `apply()`. Its successor's write is a new write site, so check `test_status_events_writes_gate.py`, `test_mutation_ownership_routing.py`, `test_generated_writer.py` and `test_byte_identity_mapping.py`, and add a rationale entry only if a gate fires.

## R-04 Git-aware mode

- **Decision**: git-aware mode applies when git can run and `tracked_mission_paths(repo_root)` is non-empty. A `GitCommandError` with `not_run`, a non-work-tree, an ignored `kitty-specs/`, or an untracked project nested in a parent repo all fall back to the file-presence rule.
- **Rationale**: operator ruling (2026-10-25). The adversarial review confirmed that a nested untracked project and an ignored `kitty-specs/` both yield an empty tracked set while `_git_prefix` succeeds, so "git can run" alone is not enough.
- **Accepted cost (operator ruling)**: in git-aware mode, committed or uncommitted pre-identity folders with only `tasks/` and `tasks.md` become residue. The notice gives a working remedy.

## R-05 Reproduction shapes still reachable after the narrow fix

- **Finding**: with only the rule and 2.0.6 filtered, two shapes still change under a real upgrade. `3.1.1` rewrites a stray `status.json`, and `0.9.0` moves `tasks/doing/WP01-x.md`. This is why the operator extended the scope to supersede 0.9.0, 0.9.1 and 3.1.1.

## R-06 Worktrees

- **Finding**: `_worktrees_to_upgrade` (`upgrade/runner.py:128-159`, #5457) drops every integrating worktree (lane, coordination, `kitty/mission-*`, detached HEAD). Only non-integrating `.worktrees/*` are upgraded, and each reads `MigrationLedger(worktree)`. The 0.9.x migrations also walk `.worktrees/*/kitty-specs` themselves; the subclass override covers those folders, with `repo_root` set to the worktree.

## R-07 Doctor finding signals

- **Signal 1** is an allow-list (`meta.json`, `status.json`, `status.events.jsonl`, `decisions/`, `*.lock`), and it needs `meta.json` to be git-tracked. A deny-list reading would have matched the real Mission `issue-6164-remove-hosted-from-core`.
- **Signal 2** compares slug-derived fields from a shared helper. Blank means `""`, `null` or absent; a numeric prefix matches as either `"007"` or `7` (after 3.2.0a4 normalization `mission_number` is an int).
- **Signal 3** uses `mission_runtime.identity.mid8_from_slug` (Crockford). It does not use `resolve_mid8`, which always returns the declared prefix. Of the 644 slugs, 76 carry no mid8 and can never match.
- **Corpus**: signal 2 alone matches 5 folders, signal 3 alone matches 1, and all three together match 0.

## R-08 Notice collapse

- **Decision (DM 01M5SVE8QC28KRAZM25PR2N4PT)**: steps emit the same `RESIDUE_NOTICE`, and the runner collapses repeats per folder per run.

## R-09 Known residuals

- C-006: a pre-ledger project with the predecessor recorded `failed` or `skipped` above its version gets the successor settled by adoption, so the retry is lost.
- #6673: a Mission whose tracked `meta.json` is missing on disk gets a fresh identity (not residue; out of scope).
- The doctor's signal 1 misses a fabricated folder that also kept a stray `tasks/`.

## Supply chain

No dependency is added, upgraded or removed; DIRECTIVE_051 controls are not triggered.
