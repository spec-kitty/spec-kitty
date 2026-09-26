# Data Model: Terminus Reconciliation Attribution Integrity

The mission's only data-model change is to the reconciliation claim. No storage schema changes.

## Entity: `ApprovedWpCommitSet` (`src/specify_cli/merge/reconciliation.py`)

Frozen dataclass — the claim the gate attributes the merged tree against.

| Field | Type | Role | Change |
|-------|------|------|--------|
| `approved` | `Mapping[str, tuple[str,...]]` | approved WP → lane-tip SHAs | unchanged |
| `excluded_shas` | `frozenset[str]` | canceled commits that must not land | **WP2**: narrowed by subtracting approved first-parent authorship |
| `excluded_patch_ids` | `frozenset[str]` | canceled patch-ids (cherry-pick catch) | **WP2**: narrowed likewise |
| `excluded_window_base` | `str \| None` | window base for excluded/closed-world axes | unchanged |
| `authored_shas` | `frozenset[str]` | approved lanes' first-parent SHAs | consumed by WP2 (subtraction source) |
| `authored_patch_ids` | `frozenset[str]` | approved lanes' first-parent patch-ids | consumed by WP2 |
| `authored_blobs` | `frozenset[tuple[str,str]]` | FINAL (path, blob) per approved lane | unchanged (add/modify authority) |
| **`authored_deletions`** | **`frozenset[str]`** | **paths the approved lanes' first-parent spine ends by deleting** | **NEW (WP1)** |
| `enforce_closed_world` | `bool` | gates the closed-world axes | unchanged |
| `verify_reachability` | `bool` | False for squash | unchanged |
| `mission_slug` / `planning_prefix` | `str \| None` | bookkeeping-path anchoring | unchanged |

### `authored_deletions` semantics (WP1)

- A path P ∈ `authored_deletions` iff, walking an approved lane's first-parent spine newest→oldest, the FIRST (newest) commit that touches P **deletes** P (no blob at that commit).
- A path added-then-deleted within a lane → present in `authored_deletions` (final state deleted).
- A path deleted-then-re-added within a lane → NOT in `authored_deletions` (final state present; it is in `authored_blobs`).
- Union across approved lanes (matches `authored_blobs`), sound under the disjoint-write-scope invariant (C-004).

## Producer chain

```
_final_authored_deletions(repo_root, first_parent_shas) -> set[str]   # NEW sibling of _final_authored_blobs
        │
        ▼
_collect_authored(...) -> (authored_shas, authored_patch_ids, authored_blobs, authored_deletions)  # return tuple grows
        │
        ▼
build_approved_wp_set(...)  # threads authored_deletions onto ApprovedWpCommitSet;
                            # also threads authored_shas/authored_patch_ids into _collect_excluded (WP2)
```

## Consumer axes

- `_unattributable_content_squash` (WP1): for a `D` path, unattributable unless `path in authored_deletions` or `_is_bookkeeping_path`.
- `_collect_excluded` (WP2): `excluded_shas ← lane_tips − authored_shas`; `excluded_patch_ids ← lane_patch_ids − authored_patch_ids` for mixed lanes.
- `_verify_squash_content` / resume path (WP3): unchanged axis; resume gains a completed-state short-circuit.
- `projected_content_matches_target` (WP4): precision on legitimately-non-landing coord-partition paths (not an `ApprovedWpCommitSet` change — a projection-proof change).

## Invariants

- **INV-1 (fail-closed data-loss)**: an unattributable add/modify OR deletion FAILs + CAS-reverts.
- **INV-2 (excluded safety)**: canceled code not on any approved first-parent spine stays excluded (#4977).
- **INV-3 (disjoint write-scope)**: each content path is authored by exactly one approved lane; the 3-way case is the known boundary (kept xfail).
