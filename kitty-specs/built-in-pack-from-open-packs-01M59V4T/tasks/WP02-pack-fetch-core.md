---
work_package_id: WP02
title: 'pack_fetch core: sparse fetch at SHA, cache, digest verify, atomic place'
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-004
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: b293c4db2f93dde294368e6d30b37fef55cc448e
created_at: '2026-10-19T12:27:50.024373+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T043
- T044
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/pack_fetch.py
create_intent:
- src/charter/offering/packs/pack_fetch.py
- tests/charter_offering/test_pack_fetch.py
- tests/charter_offering/conftest_pack_remote.py
- tests/kernel/git/test_remote_fetch_commit_subtree.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/offering/packs/pack_fetch.py
- tests/charter_offering/test_pack_fetch.py
- tests/charter_offering/conftest_pack_remote.py
- src/kernel/git/remote.py
- tests/kernel/git/test_remote_fetch_commit_subtree.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – pack_fetch core: sparse fetch at SHA, cache, digest verify, atomic place

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Build the one fetch/cache/verify core that the sync script, the hatch hook and the pin-bump helper all call.

Requirements: FR-003, FR-004, NFR-001, NFR-002, NFR-004.

## Context

- Research R-5: `git init` in the cache dir, `git fetch --depth 1 --filter=blob:none <repo> <sha>`, sparse checkout of `<subtree>`, digest check, then copy into `packs/<pack>` via a staging dir and rename.
- Research R-6 / DM 01M59V55Z62T4BM8Z8KRNFKQ63: offline uses the cache, else `PACK_SYNC_UNAVAILABLE` naming `make sync-packs`.
- Cache: `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<sha>/<subtree>` (data-model.md).
- Error codes: `contracts/sync-cli.md` (`PACK_DIGEST_MISMATCH`, `PACK_COMMIT_UNRESOLVABLE`, `PACK_SYNC_UNAVAILABLE`, `PACK_TREE_STALE`).
- The existing private helpers `pack_vendor.py:86 _fetch_subtree`, `:100 _copy_tree`, `:125 _swap_in` show the current clone/swap approach; this WP replaces them with a shared core (WP06 then rewires pack_vendor).
- The repository URL comes only from the pin (DIRECTIVE_051 note in plan.md). Do not read a URL from the environment.
- Layer: `charter.offering.packs` may use `kernel` only. `tests/architectural/test_remote_contact_owner.py` forbids `fetch`/`clone`/`ls-remote` argv outside `src/kernel/git/` with NO allowlist, so `pack_fetch` MUST NOT spawn git itself: it calls only the kernel primitive `fetch_commit_subtree` added in T043 (`src/kernel/git/remote.py` today has `remote_heads`, `fetch_branches`, `clone_repository`, `fetch_tags`, no SHA/subtree fetch).

Dependencies: Depends on WP01.

## Subtasks

### T006: Local bare-repo fixture

- **Purpose**: Local bare-repo fixture.
- **Steps**: Create `tests/charter_offering/conftest_pack_remote.py` (import it from the test module as a plugin or fixture module): build a bare git repo in `tmp_path` with a `built-in/` and a `packs/built-in/` subtree, return `(url, sha, digest)`. Use `file://` URLs so `--filter` works.
- **Edge cases / notes**: Set `uploadpack.allowFilter` and `uploadpack.allowAnySHA1InWant` on the bare repo; set `GIT_CONFIG_NOSYSTEM`.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T007: Red tests for every outcome

- **Purpose**: Red tests for every outcome.
- **Steps**: `test_pack_fetch.py`: fresh sync places the tree and the digest matches; second sync is a cache hit (no git call, assert via a spy); digest mismatch raises `PackSyncError(code=PACK_DIGEST_MISMATCH)` and leaves the previous `packs/<pack>` intact; unknown SHA raises `PACK_COMMIT_UNRESOLVABLE`; offline with no cache raises `PACK_SYNC_UNAVAILABLE` whose message contains `make sync-packs`; both subtree layouts work.
- **Edge cases / notes**: Mark fast/unit. Keep each test under a second with the local repo.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T043: Kernel primitive `fetch_commit_subtree`

- **Purpose**: Put the SHA/subtree fetch in the one module the remote-contact gate allows.
- **Steps**: Red first: `tests/kernel/git/test_remote_fetch_commit_subtree.py` against a real `file://` bare repo. Implement `fetch_commit_subtree(url, sha, subtree, dest, *, timeout)` in `src/kernel/git/remote.py`: `no_prompt_env`, `--` before URL and SHA, URL must be `https://` or `file://` and must not start with `-` (else raise), `git init` + `fetch --depth 1 --filter=blob:none` + sparse checkout of `<subtree>`, fallback to a plain `--depth 1` fetch when `--filter` is refused (test with `uploadpack.allowFilter=false`). `pack_fetch` calls only this primitive.
- **Edge cases / notes**: No bare/broad `except`. Run `tests/architectural/test_remote_contact_owner.py` file-scoped: zero hits.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T008: Implement `fetch_to_cache(pin, *, offline, cache_root)`

- **Purpose**: Implement `fetch_to_cache(pin, *, offline, cache_root)`.
- **Steps**: Resolve cache dir; if a valid cached tree exists (digest matches), return it. Else (unless offline) run the git sequence into a temp dir inside the cache root, verify the digest, then rename into `<sha>/<subtree>`. A cached tree whose digest fails is deleted and refetched.
- **Edge cases / notes**: Map git's 'not our ref'/'couldn't find remote ref' stderr to `PACK_COMMIT_UNRESOLVABLE`, network failures to `PACK_SYNC_UNAVAILABLE` when no cache exists.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T009: Implement `place_pack(cached, dest)` and `check_pack(pin, dest)`

- **Purpose**: Implement `place_pack(cached, dest)` and `check_pack(pin, dest)`.
- **Steps**: Copy into `dest.parent/.<name>.staging-<pid>`, then remove old and `os.replace`. `check_pack` returns OK/STALE/MISSING without network (for `--check` and the hatch sdist path).
- **Edge cases / notes**: Windows: `os.replace` onto an existing dir fails; rename old aside first, then remove it. No symlinks (NFR-004).
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T010: `PackSyncError` with stable codes

- **Purpose**: `PackSyncError` with stable codes.
- **Steps**: One exception class carrying `code` and an actionable message; codes as module constants (Sonar S1192).
- **Edge cases / notes**: Message names the pin path and the remedy.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T044: Integrity, symlink and swap hardening

- **Purpose**: Make placement tamper-evident and interruption-safe (B3, A5).
- **Steps**: (a) `place_pack` re-hashes the staged copy and refuses on mismatch; test poisons the cache after a hit and expects `PACK_DIGEST_MISMATCH` with `dest` unchanged. (b) `check_pack` re-hashes on every call and never trusts a marker file. (c) Refuse fetched trees containing symlinks or paths outside `<subtree>` (fixture commit with a symlink raises `PackSyncError`). (d) Windows-safe swap: stage in a sibling staging dir, retry the rename with bounded retries, and on an interrupted swap restore the aside copy at the next run (test with an injected failure between aside-rename and final rename). (e) Every error code is driven by real git against a `file://` bare repo, a missing SHA or an unreachable URL: no mocks and no stderr monkeypatching.
- **Edge cases / notes**: No bare/broad `except`.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `src/charter/offering/packs/pack_fetch.py`
- `tests/charter_offering/test_pack_fetch.py`
- `tests/charter_offering/conftest_pack_remote.py`
- `src/kernel/git/remote.py`
- `tests/kernel/git/test_remote_fetch_commit_subtree.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/charter_offering/test_pack_fetch.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- `src/kernel/git/remote.py` gains `fetch_commit_subtree(url, sha, subtree, dest, *, timeout)`; `pack_fetch` spawns no git itself; `tests/architectural/test_remote_contact_owner.py` passes with zero hits (no allowlist entry).
- `place_pack` re-hashes the staged copy and refuses on mismatch; a test that poisons the cache after a hit yields `PACK_DIGEST_MISMATCH` with `dest` unchanged; `check_pack` re-hashes every call and never trusts a marker.
- Fetched trees containing symlinks or paths outside `<subtree>` are refused (fixture commit with a symlink raises).
- Every error code is driven by real git (`file://` bare repo, missing SHA, unreachable URL); no mocks or stderr monkeypatching; no bare/broad `except`; the `--filter`-refused fallback is exercised with `uploadpack.allowFilter=false`.
- Interrupted swap restores the aside copy on the next run (injected-failure test); Windows rename retried via staging dir.
- Requirements FR-003, FR-004, NFR-001, NFR-002, NFR-004 demonstrably covered by a test or gate.

## Risks

git version differences in partial-clone support; fall back to a full `--depth 1` fetch when `--filter` is refused. Cache poisoning is covered by verifying the digest on every cache read.

## Reviewer guidance

Verify no tree is ever left in place after a digest mismatch, the URL comes only from the pin, and subprocess calls use argument lists. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP02 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
