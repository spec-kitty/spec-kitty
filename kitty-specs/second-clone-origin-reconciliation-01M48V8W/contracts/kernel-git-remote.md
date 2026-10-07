# Contract: `kernel.git.remote`

Foundation layer; knows refs and remotes, never Missions, lanes or status. Every function is bounded and non-prompting (`GIT_TERMINAL_PROMPT=0`, SSH `BatchMode=yes`, caller's `GIT_SSH_COMMAND` preserved).

- `no_prompt_env(base: Mapping[str,str] | None = None) -> dict[str,str]`
- `resolve_remote(cwd: Path, branch: str) -> str | None` — FR-017 rule; local config reads only.
- `tracking_ref(remote: str, branch: str) -> str` — `refs/remotes/<remote>/<branch>`.
- `remote_heads(cwd, remote, branches: Sequence[str], *, timeout=LS_REMOTE_TIMEOUT) -> dict[str, str]` — branch → sha for the listed ones; raises `RemoteUnreachable` on any failure/timeout.
- `fetch_branches(cwd, remote, branches, *, timeout=FETCH_TIMEOUT) -> None` — `fetch --no-tags` with explicit `+refs/heads/b:refs/remotes/r/b` refspecs; never writes `refs/heads`; raises `RemoteUnreachable`.
- `divergence(cwd, local: str, remote_ref: str, *, paths=()) -> Divergence(ahead, behind)` — one `rev-list --left-right --count local...remote_ref [-- paths]`; `ahead` meaningful only unscoped. Also serves `push_preflight.inspect_target_branch_sync`.
- `describe_remote_head(cwd, remote, *, timeout) -> str | None` — the `remote show` default-branch probe used by `protection_policy`.
- `clone_repository(...)` / `fetch_tags(...)` — thin bounded wrappers for `doctrine.sources.git_source` (census closure, not freshness reuse).
- No separate runner: every function calls `kernel.git.runner.run_git(..., env=no_prompt_env(), timeout=...)`.
- Errors: `RemoteUnreachable(GitCommandError)` carries remote, argv and stderr summary.
- Timeouts: `LS_REMOTE_TIMEOUT = 5.0`, `FETCH_TIMEOUT = 15.0` (NFR-001).
