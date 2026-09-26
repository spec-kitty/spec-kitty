# Contract: `spec-kitty merge --dry-run` coordination-read refusal (FR-008)

**Trigger**: `spec-kitty merge --dry-run [--json]` on a mission whose coordination partition cannot be read:

- `CoordinationWorktreeUnmaterialized`: the coordination branch exists, but its worktree is not checked out.
- `CoordinationBranchDeleted`: the declared coordination branch is gone.

**Exit code**: `1`. No traceback is printed.

## Human mode

```
Error: <str(exc)>
Merge aborted before any state change. <remediation>
```

The same wording is used by the real (non-dry-run) merge path. It comes from a single source: `render_coord_read_refusal` / `coord_read_refusal_remediation` in `src/specify_cli/merge/executor.py`.

| Exception | Remediation |
|---|---|
| `CoordinationWorktreeUnmaterialized` | "Materialize the coordination worktree, then re-run spec-kitty merge." |
| `CoordinationBranchDeleted` | "Recover the mission's status authority, then re-run spec-kitty merge." |

## JSON mode (`--json`)

Stdout is exactly one JSON document:

```json
{
  "spec_kitty_version": "<version>",
  "error": "<str(exc)>",
  "error_code": "COORDINATION_WORKTREE_UNMATERIALIZED | COORDINATION_BRANCH_DELETED",
  "remediation": "<remediation sentence>"
}
```

- `spec_kitty_version` and `error` match the existing dry-run error document shape.
- `error_code` and `remediation` are additive fields.

**Pinned by**: `tests/merge/test_nightly_remediation_merge_defects.py` (human + JSON × both exceptions).
