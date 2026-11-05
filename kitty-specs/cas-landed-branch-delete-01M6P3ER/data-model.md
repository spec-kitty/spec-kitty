# Phase 1 Data Model — expected tip and delete outcomes

**Mission**: `cas-landed-branch-delete-01M6P3ER`

## Value objects

| Name | Shape | Meaning |
| --- | --- | --- |
| `expected_tip` | `str | None` (40-hex commit SHA) | The commit whose absorption into `origin/<primary>` the prune proved. The compare-and-swap old value. Required under `LANDED_INTENT`; unused by every other intent. |
| `PruneOutcome.refusal` | existing `str` codes | Unchanged vocabulary. The two new guard codes are mapped into it (below). |

`expected_tip` is exactly the prune's `WorktreeVerdict.tip`, which
`_still_landed_refusal` has just re-checked is still the branch tip at
assess-time.

## Guard refusal codes

| Code | Emitted when | Operator-facing at the prune |
| --- | --- | --- |
| `BRANCH_TIP_MOVED` (new) | the branch no longer points at `expected_tip` when the delete runs (pre-check or CAS refusal) | `BRANCH_MOVED` |
| `BRANCH_CHECKED_OUT` (new) | a worktree has the branch checked out when the CAS runs | `BRANCH_IN_OTHER_WORKTREE` |
| `BRANCH_DELETE_REFUSED_BY_GIT` (new) | git refused the CAS for another reason | `BRANCH_DELETE_FAILED` (the prune's existing catch) |
| `DESTRUCTIVE_OP_ONLY_COPY` (existing) | the keep-record could not be written; nothing deleted | unchanged |
| `BRANCH_HAS_UNIQUE_COMMITS` (existing) | the no-intent path still refuses unique commits | unchanged (other callers) |

`ValueError` (not a refusal code) is raised for `LANDED_INTENT` without
`expected_tip`, and for an unknown intent — a programming error, before any git
call.

## Branch-delete state machine (LANDED, with `expected_tip`)

```
[prune proved tip absorbed]
        │  worktree removed (guarded_worktree_remove, force=False)
        ▼
  read ref ── None ─────────────────────────────► no-op (branch already gone)
        │
        ├── != expected_tip ───────────────────► BRANCH_MOVED, keep branch
        ▼
  checked out in another worktree? ── yes ──────► BRANCH_IN_OTHER_WORKTREE
        ▼
  tip reachable from another local branch/tag?
        ├── no  → write refs/spec-kitty/discarded/<branch> at expected_tip
        │         (create-only; failure → DESTRUCTIVE_OP_ONLY_COPY, keep branch)
        └── yes → no record
        ▼
  delete_branch_ref(ref, expected_tip)   # git update-ref -d <ref> <expected>
        ├── ok ────────────────────────────────► deleted; kept_ref = record (if written)
        └── ref moved ─────────────────────────► BRANCH_TIP_MOVED → BRANCH_MOVED, keep branch
```

Invariants:

1. The ref is deleted **only** while it holds `expected_tip`; the check and the
   delete are one git operation.
2. A keep-record is written **before** the delete, never after.
3. A refusal leaves the ref exactly as found (the branch, and any commit added
   to it, stays reachable).
4. A refused CAS may leave the create-only keep-record for `expected_tip`
   behind. Harmless; the branch still holds its own tip.
5. No behaviour change for `operator_intent in {None, FORCE_RECREATE, DISCARD}`.

## Non-goals

- No change to `WorktreeVerdict`, `WorktreeAssessment`, `PruneOutcome` fields,
  the JSON shape or the recreate-command text.
- No change to `ref_advance.delete_branch_ref` itself.
