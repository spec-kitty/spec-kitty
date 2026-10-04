# Data model: Consolidation god-module decomposition

No persisted data changes (C-001). Two in-memory shapes matter.

## `_MergeRunState` (moves to `consolidation/run_state.py`, unchanged)

The mutable record threaded through every phase helper (INV-3). Fields and
defaults are byte-identical; only its module changes. `_CoordCheckpoint`
moves with it (forward-referenced in a field annotation).

## `ConsolidateOptions` (new, `cli/commands/consolidate.py`)

Frozen dataclass; one field per `consolidate` CLI option, default equal to the
CLI default (never a `typer.OptionInfo`):

| Field | Type | Default |
|---|---|---|
| strategy | `MergeStrategy \| None` | `None` |
| delete_branch | `bool \| None` | `None` |
| remove_worktree | `bool \| None` | `None` |
| push | `bool` | `False` |
| target_branch | `str \| None` | `None` |
| dry_run | `bool` | `False` |
| json_output | `bool` | `False` |
| mission | `str \| None` | `None` |
| resume | `bool` | `False` |
| abort | `bool` | `False` |
| context_token | `str \| None` | `None` |
| keep_workspace | `bool` | `False` |
| allow_sparse_checkout | `bool` | `False` |
| yes | `bool` | `False` |
| skip_review_artifact_check | `bool` | `False` |
| note | `str \| None` | `None` |
| skip_lanes | `bool` | `False` |
| attest_canceled_superseded | `list[str] \| None` | `None` |
| attest_reason | `str \| None` | `None` |
