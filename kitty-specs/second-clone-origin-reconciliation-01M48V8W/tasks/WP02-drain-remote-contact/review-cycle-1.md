---
affected_files: []
cycle_number: 1
mission_slug: second-clone-origin-reconciliation-01M48V8W
reproduction_command:
reviewed_at: '2026-10-06T17:20:38Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (cycle 1)

Reviewer: reviewer-renata (claude). Verdict: changes requested. One blocking security item; the rest of the WP is sound.

## Blocking

1. **[MEDIUM, security] `src/specify_cli/doctrine/sources/git_source.py:246-258` (`GitSource._clone`) - a timed-out clone can print the credentialed URL.**
   `kernel.git.runner.run_git` turns `subprocess.TimeoutExpired` into `GitCommandError(stderr=str(exc), timed_out=True)`. `str(TimeoutExpired)` is `Command '['git', 'clone', '<url>', '<dest>']' timed out after 120 seconds`, i.e. it carries the full argv, URL included. `_clone` returns `_redact_git_tokens(exc.stderr.strip())`, and `_redact_git_tokens` only strips the `oauth2:<token>@` form the source injects itself. A URL the operator configured with its own userinfo (`https://user:PAT@host/org/pack.git`) reaches `FetchResult.errors` verbatim. Reproduced:
   ```
   GitCommandError(argv=..., stderr=str(TimeoutExpired(cmd=['git','clone','https://user:hunter2@github.com/acme/p.git','/tmp/x'], timeout=120)), timed_out=True)
   -> _redact_git_tokens(exc.stderr) == "Command '['git', 'clone', 'https://user:hunter2@github.com/acme/p.git', '/tmp/x']' timed out after 120 seconds"
   ```
   Before this WP the clone had no timeout, so that text could not be produced; git's own stderr hides URL userinfo. This is a regression introduced here, and the docstring ("never the exception text, which would carry the credentialed URL in its argv") claims the opposite of what the code does.
   **Fix:** never echo `exc.stderr` when `exc.timed_out` (or `exc.not_run`). Return a fixed message such as `"git clone timed out"` (same for `_fetch_tags`, `"git fetch timed out"`, for consistency even though its argv has no URL).
   **Test:** `test_git_source_clone_timeout_reports_through_the_error_path_without_the_credentialed_url` plants `stderr=""`, which is not the shape `run_git` produces, so it cannot observe the leak (blind probe). Build the planted error the way `run_git` does (`stderr=str(subprocess.TimeoutExpired(cmd=["git", "clone", url, dest], timeout=120))`), use a URL with operator userinfo (`https://user:secret@...`) and the injected-token form, and assert neither `secret` nor the token appears in `result.errors`. Confirm the test is red against the current `_clone`.

## Non-blocking (fix if cheap, otherwise note in the PR)

2. **[LOW] `tests/architectural/_remote_contact_census.py:40,80` - the registration skip-list is matched by method name only.** Any attribute call named `command` / `callback` / `add_parser` / `add_argument` / `add_typer` is skipped wholesale, so `self.callback(root, "fetch", "origin")` or `runner.command(root, "fetch")` (positional-string wrapper form) is not reported (verified with `census_source`). A list literal inside such a call is still caught by the walk. Narrow the skip to calls whose first resolved positional is the verb AND which take no other positional strings, or limit it to the known receivers (`app`, `*_app`, `parser`, `subparsers`), or at minimum document it next to the other accepted blind spots and add a planted test pinning the documented behaviour.
3. **[LOW] census blind spots not documented:** a shell-string argv (`subprocess.run("git fetch origin", shell=True)`, `"git fetch".split()`) and `git remote update` / `remote prune` / `remote set-head -a` (which contact the remote) are not detected. None exists in `src/` today (grep confirmed). Add one line to the census module docstring naming them as accepted blind spots, so the gate's limits are explicit.
4. **[INFO] behaviour deltas that are acceptable but should be named in the PR body:** `push_preflight` fetch now uses `--no-tags` (no caller reads tags after the refresh; `check_push_safety` uses only the tracking ref), drops `--quiet`, and drops the `stdout` fallback for the error detail; the doctrine clone/fetch now add SSH `BatchMode` (an interactive passphrase prompt for an SSH pack URL now fails instead of asking) and a 120 s / 15 s bound; `protection_policy`'s `remote show origin` is now bounded at 5 s.

## Verified OK

- Gate non-vacuity: `test_remote_contact_owner.py` green; planting a raw `["git","-C",...,"fetch","origin"]` and `_run(["remote","show","origin"])` in `protection_policy.py` (temp worktree) turned `test_no_remote_contact_outside_kernel_git` red naming both lines. No allowlist variable. Floor is a concrete `1250` against 1389 scanned files. Planted forms cover `-C`, `-c -C`, wrappers (`_run`, `_git`, `run_git`, `deadline.run`), constant indirection, `remote show -n` negative control, owner-bypass positive control.
- `push_preflight`: state strings, `no_tracking_branch` on failure, left/right orientation, `attempted=False` no-remote path, `remote_name="origin"` and `_resolve_tracking_branch` unchanged.
- `protection_policy` parsing identical; `remote_probes` HIT/CLEAN_MISS/ERROR semantics identical; the two removed `_no_prompt_env` tests are covered by `tests/kernel/test_git_remote.py::test_no_prompt_env_defaults` / `test_no_prompt_env_preserves_existing_ssh_command`.
- #4969 resolvers: origin-only ref names unchanged; non-origin remote tested; `tests/terminus/test_repro_4969.py` green.
- `tests/git/test_protection_config_honoring.py`: the same 2 failures on base `a23fc7d6` and on HEAD (pre-existing).
