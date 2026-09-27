# Data Model — Consolidate terminology (#3080)

This mission is a terminology rename; it introduces no new persisted entity and changes no
serialized schema. The "entities" below are the conceptual objects the rename touches.

## Renamed entities

- **ConsolidationState** (was `MergeState`) — the in-memory/persisted record of consolidation
  progress (wp_order, completed_wps, current_wp, has_pending_conflicts, strategy, timestamps).
  - Persisted to `state.json` under `.kittify/runtime/merge/<mission_id>/` — **filename & dir frozen**.
  - `strategy` field name and its `"merge"`/`"squash"`/`"rebase"` **values are frozen** (Sense-B git-strategy contract).
  - **No re-export alias** (post-plan A3): no external consumer imports a renamed symbol — `orchestrator_api` imports only `MergeStrategy` (frozen) + the private `_run_lane_based_merge` (repointed); `saas_client`/`zeitgeist_client` import none. All importers are repointed. A code-level alias would contradict the clean-rename posture. NFR-002 → shim count is **none**.
  - **Blast radius (corrected):** `tests/merge/` = 72 files; 129 test files reference `specify_cli.merge`; 51 reference `MergeState`. The rename is one atomic WP (write-scope collision — cannot split).

- **Consolidation command** (was `merge` command) — `spec-kitty consolidate`, carrying the full former
  flag set (`--resume/--abort/--dry-run/--keep-branch/--keep-worktree/--mission/--feature/--target`).
  - `spec-kitty merge` removed → hidden migration-error stub (C-004).

## Frozen wire-keys (unchanged; enumerated so the implementer never renames them)

| Key/value | Location | Why frozen |
|---|---|---|
| `baseline_merge_commit` | mission `meta.json` | Phase-derivation input (`lifecycle_phase.py:237-239`); renaming split-brains routing across versions |
| `MergeStrategy` / `"merge"` value | `merge/config.py`, `state.json` | git-strategy serialized contract (Sense B) |
| `state.json` filename | `.kittify/runtime/merge/<id>/` | renaming strands in-flight resumable consolidations |
| merge-driver config | `.gitattributes`/git-config | literal git plumbing (Sense B) |

## Classification artifact

- **occurrence_map.yaml** — the per-category / per-path bulk-edit classification (8 categories +
  exceptions) the runtime diff-check gate enforces at review time. Sole authority for which
  occurrence is rename vs keep.
