# Contract: per-surface commit outcome

**Home:** `src/specify_cli/coordination/commit_outcome.py` (new): `PathFate`, `SurfaceOutcome`, `render_commit_outcome`, `commit_outcome_payload`. `CommitRouterResult` (`commit_router.py:174-205`) gains `surfaces`.
**Requirements:** FR-006, FR-007, FR-007a, FR-007b, FR-005; SC-003.

## Types

```python
@dataclass(frozen=True)
class PathFate:
    path: str                 # as the caller passed it (repo-relative)
    reason: str               # see "Reason codes"
    owning_path: str | None = None

@dataclass(frozen=True)
class SurfaceOutcome:
    surface: Literal["primary", "coordination"]
    branch: str
    status: Literal["committed", "unchanged", "refused", "error"]
    commit_hash: str | None
    committed: tuple[str, ...] = ()
    skipped: tuple[PathFate, ...] = ()
    refused: tuple[PathFate, ...] = ()
    diagnostic: str | None = None

# CommitRouterResult: existing fields unchanged + 
    surfaces: tuple[SurfaceOutcome, ...] = ()
```

## Rules

1. `surfaces` has one entry per partition group the request touched, in the order PRIMARY then coordination.
2. **Owning surface.** A COORD record passed by its repository-root path is judged on its coordination copy. A dirty coordination copy is committed; a clean one is `unchanged`. Otherwise it is listed in `refused` with a named reason. It never lands in `skipped` while the owning copy is dirty.
3. `skipped` holds only genuine no-ops: clean on the owning surface, or `COORD_RECORD_IN_ROOT_CHECKOUT` (a root-checkout copy of a COORD record that is never committed to the target branch).
4. **Legacy fields.** The top-level `status`, `placement_ref`, `commit_hash`, `diagnostic` and `reason` keep today's caller-surface selection (`_merge_group_results`, L802-844). `commit_hashes` keeps its union.
5. **Exit-code rule for consumers.** Exit non-zero if any surface is `refused` or `error`. `skipped` and `unchanged` exit 0 and are rendered.
6. Every consumer renders through `render_commit_outcome` (text) or `commit_outcome_payload` (JSON). No consumer formats surface outcomes by hand. A test pins the consumer list from research D8.

## Reason codes

| Code | List | Meaning | New or existing |
|------|------|---------|-----------------|
| `no_op_already_committed` | skipped | owning copy clean | existing (`_REASON_ALREADY_COMMITTED`, L166) |
| `no_op_no_changes` | skipped | nothing staged | existing (L167) |
| `COORD_RECORD_IN_ROOT_CHECKOUT` | skipped | a COORD record dirty only in the repository root checkout; never committed to the target branch | new |
| `PROTECTED_BRANCH_REFUSED` | refused | destination ref is protected | existing (`coordination/types.py:90`) |
| `STATUS_LOCK_HELD` | refused | status lock held by another writer | new code (maps `FeatureStatusLockTimeoutError`) |
| `COORDINATION_BRANCH_DELETED` | refused | coordination branch missing | existing |
| `COORDINATION_WORKTREE_UNMATERIALIZED` | refused | coordination branch exists only on the remote (#4970 parity), surfaced from `write_dir` | existing |
| `COORD_SEED_FORK_REFUSED` | refused | establishing the coordination surface found a forked log (`contracts/seed.md`) | new |
| `PATH_UNROUTABLE` | refused | path outside the Mission, or kind not classifiable | new |
| `WRONG_SURFACE` | refused | today's `no_op_wrong_surface` situation | existing semantics; new name in `surfaces` only |

## JSON shape changes (additive, backward compatible)

**spec-commit** (`spec_commit_cmd.py::_payload`, L70-95): the existing keys are unchanged (`result`, `success`, `committed`, `placement_ref`, `commit_hash`, `error`, `diagnostic`, `reason`, `error_code`). New keys:

```json
{
  "surfaces": [
    {"surface": "primary", "branch": "topic", "status": "committed", "commit_hash": "abc…",
     "committed": ["kitty-specs/m/spec.md", "kitty-specs/m/decisions/index.json"], "skipped": [], "refused": []},
    {"surface": "coordination", "branch": "kitty/mission-m-01ABCDEF", "status": "committed", "commit_hash": "def…",
     "committed": ["kitty-specs/m/traces/approach.md", "kitty-specs/m/status.events.jsonl"], "skipped": [], "refused": []}
  ],
  "arguments": [
    {"path": "kitty-specs/m/spec.md", "fate": "committed", "surface": "primary"},
    {"path": "kitty-specs/m/status.events.jsonl", "fate": "committed", "surface": "coordination"}
  ]
}
```

`arguments` lists every input path exactly once, with `fate` one of `committed`, `unchanged`, `skipped` or `refused`, plus `reason` when not committed (FR-007a). `success` becomes `false` when any surface is `refused` or `error`.

**accept** (`--json`): adds `residual_commit: {"surfaces": [...]}`.
**finalize-tasks** (`--json`): adds `commit_surfaces: [...]` beside the existing `commit_hashes` (emitted at `mission_finalize.py:3746`). It also adds `planning_commit_refresh: {status: "refreshed" | "preserved" | "kept_with_warning", recorded, candidate, pin_class, reason}`.
  - `kept_with_warning` (exit 0) applies only when the **automatic** refresh cannot prove a safe advance for a non-orphan pin (`FOREIGN`/`INDETERMINATE`; ruling Q6).
  - An **orphaned** pin keeps failing closed before any write with the existing error envelope (#4827, `test_plain_finalize_fails_closed_on_orphaned_pin`); this field is not emitted then.
  - An explicit `--refresh-planning-commit` keeps its existing refusals, which also fail (research D16).
**retrospect, setup-plan, record-analysis:** add `surfaces` to their existing commit payloads.
**implement receipts** (`{"commits": [...]}`, `workflow.py:837`): every entry carries a non-null `sha` (FR-013).

**Text** (one line per surface, then one line per refused or skipped path):

```text
✓ primary (topic): committed abc1234 — 2 files
✗ coordination (kitty/mission-m-01ABCDEF): refused — status.events.jsonl: STATUS_LOCK_HELD
```

## Compatibility

- No existing key is removed or retyped. An old consumer reading only the top-level fields sees today's values.
- `success` can now be `false` where it was `true` before. That happens exactly when a surface was refused, which is the defect being fixed.
