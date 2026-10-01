# Contract: `kernel.git` public API

Path arguments are literal: they go after `--` and git runs with `--literal-pathspecs`, unless the caller passes `glob=True`. The runner knows no specific command and the package contains no destructive literal (C-007). Only git-2.25 flags (C-008).

All functions take `cwd: Path` (a checkout) and keywords `env: Mapping[str, str] | None = None` and `timeout: float | None = None` (a timeout raises `GitCommandError` with `timed_out=True`). Every listing passes `-z`. A non-zero exit raises `GitCommandError` (fail closed).

| Function | Git | Returns |
|---|---|---|
| `run_git(cwd, *args, env=None, timeout=None, check=True)` | `git <args>` | `GitResult` (bytes) |
| `decode_path(raw: bytes)` | — | `str` (utf-8, surrogateescape) |
| `status_entries(cwd, *, pathspecs=(), untracked="normal", ignored=False, optional_locks=True, env=None)` | `[--no-optional-locks] status --porcelain=v1 -z [--untracked-files=<u>] [--ignored] -- <pathspecs>`; `untracked=None` omits the flag (git config decides) | `tuple[StatusEntry, ...]` |
| `tree_paths(cwd, ref, *, pathspecs=(), env=None)` | `ls-tree -r --name-only -z <ref> -- <pathspecs>` | `frozenset[GitPath]` |
| `changed_paths(cwd, *revs, cached=False, renames=False, pathspecs=(), diff_filter=None, env=None)` | `diff --name-only -z (--no-renames\|-M) [--cached] [--diff-filter=F] <revs> -- <pathspecs>` | `tuple[GitPath, ...]` (git order) |
| `changed_entries(cwd, *revs, cached=False, renames=False, pathspecs=(), env=None)` | `diff --name-status -z [--no-renames] …` | `tuple[NameStatusEntry, ...]` |
| `commit_paths(cwd, commit, *, first_parent=False, env=None)` | `show --name-only --format= -z --no-renames [--first-parent -m] <commit>` (a merge commit lists nothing without `first_parent`) | `tuple[GitPath, ...]` |
| `tracked_paths(cwd, *, pathspecs=(), env=None)` | `ls-files -z -- <pathspecs>` | `tuple[GitPath, ...]` |
| `index_entries(cwd, *, pathspecs=(), tags=False, env=None)` | `ls-files [-v] --stage -z -- <pathspecs>` | `tuple[IndexEntry, ...]` (mode, oid, stage, path, tag) |
| `numstat_entries(cwd, *revs, cached=False, pathspecs=(), env=None)` | `diff --numstat -z --no-renames [--cached] <revs> -- <pathspecs>` | `tuple[NumstatEntry, ...]` |
| `tree_entry(cwd, ref, path, *, env=None)` | `ls-tree -z <ref> -- <path>` | `TreeEntry \| None` |
| `log_paths(cwd, rev_range, *, pathspecs=(), env=None)` | `log -z --name-only --format= --no-renames <range> -- <pathspecs>` | `tuple[GitPath, ...]` |
| `is_tracked(cwd, path, *, env=None)` | `ls-files --error-unmatch -- <path>` | `bool` (exit 1 → False; other errors raise) |

Exact signatures may gain keyword options during migration (for example `ref` filters) — additive only, each with a test.
