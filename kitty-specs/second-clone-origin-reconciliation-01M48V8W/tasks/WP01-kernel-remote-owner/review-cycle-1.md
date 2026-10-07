---
affected_files: []
cycle_number: 1
mission_slug: second-clone-origin-reconciliation-01M48V8W
reproduction_command:
reviewed_at: '2026-10-06T15:45:01Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback — cycle 1 (reviewer-renata)

Verdict: **changes requested**. The contract surface, layering, `__all__`, FR-017 order, `divergence`
orientation, path scoping and the red-first ordering are all good (red confirmed: commit `1722934f`
alone fails collection with `ImportError: cannot import name 'remote' from 'kernel.git'`). There are
three blocking problems: one production defect and two tests that cannot fail.

## Blocking

1. **[HIGH] `src/kernel/git/remote.py:230`: `clone_repository` changes path semantics, so it does not "mirror git_source exactly".**
   `cwd = dest.parent if dest.parent.is_dir() else Path.cwd()` runs `git clone <url> <dest>` from
   `dest.parent`, but passes `str(dest)` and `url` unchanged. When either is relative, it now resolves
   against `dest.parent` instead of the process cwd that `git_source._run_git` uses today (no `cwd=`).
   Reproduced in a scratch dir:
   - `clone_repository('src.git', Path('packs/.tmp-x'))` → exit 128, `fatal: repository 'src.git' does not exist`. Today's argv succeeds.
   - `clone_repository('/abs/src.git', Path('packs/.tmp-y'))` → exit **0**, but the clone lands in `packs/packs/.tmp-y`. `git_source._promote` would then try to move a directory that does not exist.

   WP02's swap must be behaviour-preserving, and this is not.
   **Fix:** drop the heuristic and run in `Path.cwd()`, which is exactly what git_source inherits.
   Do not resolve `dest`/`url` yourself either, because a relative URL must keep its current meaning.
   Add a test that clones with a relative `url` and a relative `dest` (`monkeypatch.chdir(tmp_path)`) and asserts the clone is at `tmp_path / dest`.

2. **[HIGH] `tests/kernel/test_git_remote.py:154-165`: the NFR-002 no-prompt test is vacuous, which breaks the binding squad fold.**
   Mutation: remove `env=no_prompt_env()` from `_contact` (`remote.py:128`), and all 28 tests stay green.
   There are three causes:
   - (a) The env assertions call `no_prompt_env()` directly, not the env the production path passes to git.
   - (b) `isolated_git_env` (`tests/terminus/two_clone_support.py:46`) already exports `GIT_TERMINAL_PROMPT=0` process-wide, so a prompt is refused even without the module's env.
   - (c) `ssh://git@127.0.0.1:1` is refused at TCP connect, before any auth or prompt.

   **Fix:** observe the production path. For example, set `GIT_SSH_COMMAND` to a tiny fake-ssh script under `tmp_path` that writes its argv and `GIT_TERMINAL_PROMPT` to a file and exits 255. Then call `remote_heads` on an `ssh://` remote and assert:
   - `RemoteUnreachable` is raised;
   - the recorded argv contains `-o BatchMode=yes`;
   - the recorded `GIT_TERMINAL_PROMPT` is `0`.

   In that test, do NOT pre-export `GIT_TERMINAL_PROMPT`: `monkeypatch.delenv` it after `isolated_git_env`, or make the helper's export optional. Re-run the mutation above and confirm the test goes red. Note it in the Activity Log.

3. **[MEDIUM] `remote.py:128` / `remote.py:201`: no test exercises a timeout (NFR-001), so the bound is unpinned.**
   Mutations that survive (28/28 green):
   - removing `timeout=timeout` from `_contact`;
   - removing both `env=` and `timeout=` from `describe_remote_head`.

   **Fix:** use the same fake-ssh approach with a script that sleeps (e.g. `sleep 30`). Call `remote_heads(..., timeout=1.0)` and `fetch_branches(..., timeout=1.0)`, and assert:
   - `RemoteUnreachable` is raised with `.timed_out is True`;
   - elapsed time is `< 2 × timeout`.

   Add one `describe_remote_head(..., timeout=1.0)` case that asserts `None` within the bound. Confirm each test goes red under its mutation.

## Non-blocking (fix if cheap, otherwise note for WP02)

4. **[LOW] `remote.py:224-236` (for the WP02 hand-off): `clone_repository`/`fetch_tags` now add `GIT_SSH_COMMAND … BatchMode=yes` and a finite timeout.**
   git_source today sets only `GIT_TERMINAL_PROMPT=0` and has no timeout. Both changes are intended (NFR-001/002), but they are behaviour changes:
   - a passphrase-protected ssh key without an agent now fails instead of prompting;
   - a timeout *raises* `GitCommandError` even with `check=False`.

   State both in the docstrings so WP02 catches the exception and keeps git_source's `_error_result` path (and redaction).

5. **[LOW] Deviations not recorded.** Dropping `--no-write-fetch-head` is fine: it needs git ≥ 2.29, and writing FETCH_HEAD is harmless. `describe_remote_head` returning `None` on any failure matches `protection_policy._remote_default_branch`. Record both deviations in the WP Activity Log, together with the red run and the test counts. The Activity Log currently has only "prompt generated".

## Evidence (commands run)
- Red: tests-only commit `1722934f` in a temp worktree → `pytest tests/kernel/test_git_remote.py` → 1 collection error (ImportError). Temp worktree removed afterwards.
- `pytest -q tests/kernel/test_git_remote.py tests/kernel/test_git_listing.py` → 72 passed.
- `pytest -q tests/architectural/test_layer_rules.py` → 74 passed.
- `ruff check` / `ruff format --check --force-exclude` / `ruff --select C901` on the changed files → clean. `mypy src/kernel/git/remote.py src/kernel/git/__init__.py` → no issues.
- Mutations M1 (no env in `_contact`), M2 (no timeout in `_contact`), M3 (no env/timeout in `describe_remote_head`) → 28/28 green each, which proves findings 2 and 3.
