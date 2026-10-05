# Data model: rollback anchor authority

## `ConsolidationState` (`.kittify/runtime/merge/<mission_id>/state.json`)

Existing fields this mission relies on (unchanged meaning):

| Field | Type | Meaning |
|---|---|---|
| `pre_mutation_refs` | `dict[str, str]` | Branch → SHA snapshot, captured once per record, never recaptured. |
| `post_mutation_refs` | `dict[str, str]` | Branch → SHA this attempt left a run-movable branch at; the CAS expected value of a restore. |
| `restore_targets` | `dict[str, str]` | Branch → SHA a restore moves the branch to. |
| `snapshot_lane_branches` | `list[str]` | Report-only lane branches (never run-movable). |

New fields. All are optional on load (absent → default), and an older binary ignores them:

| Field | Type | Default | Malformed → | Written by | Cleared by |
|---|---|---|---|---|---|
| `unsettled_refs` | `list[str]` | `[]` | every run-movable branch (fail closed) | `begin_attempt` (all run-movable branches, when it explains every branch); `rollback_to_snapshot` (re-adds every NOT_RESTORED run-movable branch) | per branch: a RESTORED / ALREADY_AT_SNAPSHOT / KEPT_BY_OPERATOR rollback outcome; the target: a reconciliation PASS |
| `advance_intents` | `dict[str, list[str]]` | `{}` | `{}` (fail closed: no proof) | the span's advance sink, before each CAS write: `[base, new₁, …]` (a new advance whose old SHA equals the chain's last entry extends the chain; otherwise it starts a new chain `[old, new]`) | per branch by the phase recorder (recorded or rejected); all by `begin_attempt` and on a full restore |
| `released_refs` | `dict[str, str]` | `{}` | `{}` | `consolidate --abort --release-branch` (branch → live SHA at release time) | full restore / record clear |
| `release_reasons` | `dict[str, str]` | `{}` | `{}` | same | same |

## Derived values (rollback authority)

Given a run-movable branch *b* with snapshot *S*, live tip *L*, restore target *T* = `restore_targets.get(b, S)` and recorded post *P* = `post_mutation_refs.get(b)`:

- **Expected tip** *E* = *P* if recorded, else *T*.
- **Effective post** = *L* if `advance_intents[b]` is a chain whose base is *E* and whose later entries contain *L* (a provable advance of this run). Otherwise it is *P*.
- **Own pre-claim moves** (`own_moves`): branch → `(before, after)`, the tips immediately before and after this process's own pre-claim steps (operator attestations, coord-strand heal), only for a branch whose tip changed across them. `begin_attempt` judges such a branch by `before` only while *L* = `after`; otherwise the ordinary classification below applies.
- **Classification at `begin_attempt`**:
  - *L* ∈ {*T*, effective post} → explained; the target stays *T*, and the post is carried when *L* is the effective post.
  - otherwise, *b* is not unsettled → a move between attempts on a settled branch; the target becomes *L* and the post is dropped (today's A2 rule).
  - otherwise → **unexplained**: the target stays *T*, there is no post, and the claim refuses `UNEXPLAINED_BRANCH_MOVE`. Nothing in the record changes.
- **Phase recorder** (FR-011): at phase entry, capture *L₀* and *E₀* per branch. At exit, record *L* as the post only if *L* ≠ *L₀* **and** *L₀* = *E₀*. Otherwise leave *P* untouched (a foreign interleave), so a rollback reports `NOT_RESTORED`.
- **Rollback outcome** (`_rollback_branch`): the existing logic with the effective post in place of *P*. A NOT_RESTORED result (not a missing branch) where `released_refs[b] == L` becomes **KEPT_BY_OPERATOR**. This is an OK kind, but it is not a restore.

## Lifecycle of `unsettled_refs` for one branch

```
settled --begin_attempt(all explained)--> unsettled
unsettled --rollback RESTORED/ALREADY_AT_SNAPSHOT/KEPT_BY_OPERATOR--> settled
unsettled --reconciliation PASS (target only)--> settled
unsettled --rollback NOT_RESTORED--> unsettled
unsettled --SIGKILL / orderly exit--> unsettled (orderly exit is NOT settling)
```

## Error codes

- `UNEXPLAINED_BRANCH_MOVE`: a re-run or `--resume` refuses before the coord-strand heal, the operator attestations and the claim. The message names each branch with its restore target and live SHA, says that nothing was changed and the record is kept, and offers non-destructive remedies:
  1. inspect `git log <restore-target>..<live>`;
  2. if the commits should not stay, move the branch yourself (no recipe is printed); spec-kitty never moves a commit it cannot prove is its own;
  3. to keep them, `spec-kitty consolidate --abort --release-branch <b> --release-reason "..."`, with the warning that a release keeps every listed commit.

  Exit 1.
- `RELEASE_BRANCH_INVALID`: `--release-branch` without `--abort` or without `--release-reason`, or naming a branch that is not a snapshotted run-movable branch. Nothing changes. Exit 2.
