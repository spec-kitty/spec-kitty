# Data Model: Remote-only branch recovery remedy

## RemoteOnlyBranch (value object, `mission_runtime.coord_remedy`)

| Field | Type | Meaning |
|-------|------|---------|
| `branch` | `str` | the branch name (no `refs/heads/`) |
| `remote` | `str \| None` | the remote judged to own it; `None` when ambiguous |
| `tracking_ref_present` | `bool` | `refs/remotes/<remote>/<branch>` exists in this clone |
| `remotes` | `tuple[str, ...]` | configured remotes (for the ambiguous rendering) |

Invariant: `tracking_ref_present` implies `remote is not None`.

Remote choice: `resolve_remote(repo_root, branch)`; if that remote has no tracking ref and exactly one configured remote does, that remote (with `tracking_ref_present=True`).

## Remedy text (pure)

`remote_only_steps(facts, repo_root, follow_up) -> str`:

`Run in order: `git -C <root> fetch <remote> <b>`, then `git -C <root> branch <b> <remote>/<b>`, then `<follow_up>`.`

- fetch step omitted when `tracking_ref_present`;
- `<remote>` rendered literally with "(one of: a, b)" when `remote is None`.

## StatusSurfaceRefRemoteOnly (error, `specify_cli.coordination.status_service`)

Subtype of `StatusSurfaceRefUnreadable`; `error_code = "STATUS_SURFACE_REF_REMOTE_ONLY"`; carries `ref`, `path`, `branch`, `remedy`; message names the branch as remote-only and ends with the remedy and the code.
