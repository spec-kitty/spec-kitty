---
work_package_id: WP02
title: Drain every remote contact into the owner; census gate
dependencies:
- WP01
requirement_refs:
- FR-013
- FR-016
- C-004
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:12:09.987060+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Foundation
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_remote_contact_owner.py
- tests/architectural/_remote_contact_census.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/git/remote_probes.py
- src/specify_cli/consolidation/push_preflight.py
- src/specify_cli/git/protection_policy.py
- src/specify_cli/doctrine/sources/git_source.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/workspace/context.py
- tests/architectural/test_remote_contact_owner.py
- tests/architectural/_remote_contact_census.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Drain every remote contact into the owner; census gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

After this WP, no file in `src/` outside `src/kernel/git/` runs a remote-contacting git command (`fetch`, `ls-remote`, `pull`, `clone`, `remote show` without `-n`). `push` is out of scope (FR-015). An architectural gate with an EMPTY allowlist proves it (FR-013, C-004, SC-005), and the two #4969 ref builders share `kernel.git.remote.tracking_ref` (FR-016).

Every public behaviour of the drained modules stays byte-identical: existing tests for `remote_probes`, `push_preflight`, `protection_policy`, doctrine sources and implement base resolution pass unchanged.

## Context & Constraints

- Read `kitty-specs/second-clone-origin-reconciliation-01M48V8W/{plan.md,research.md (R-9),contracts/kernel-git-remote.md}` and `traces/design-decisions.md`.
- WP01 delivered `kernel.git.remote` (`no_prompt_env`, `resolve_remote`, `tracking_ref`, `remote_heads`, `fetch_branches`, `divergence`, `describe_remote_head`, `clone_repository`, `fetch_tags`, `RemoteUnreachable`, timeouts).
- Today's sites (post-plan squad census, verify yourself): `doctrine/sources/git_source.py:88` (clone), `:146` (fetch --tags), `git/remote_probes.py:129` (ls-remote), `consolidation/push_preflight.py:194` (fetch, multi-line argv list), `git/protection_policy.py:467` (`_run(["remote","show","origin"])`).
- Ownership-map leeway: if a WP01 kernel function needs an API gap fixed to keep a drained module byte-identical, make an ADDITIVE-ONLY edit to `src/kernel/git/remote.py` (+ a kernel test) and record a one-line rationale in the Activity Log; never change an existing signature WP03 depends on.
- Interim arch reds: `test_no_dead_symbols` for kernel names only WP03 uses (if any) stays red until WP03 lands — document, do not paper over.
- C-007: do NOT touch `consolidation/rollback.py`, `git/ref_advance.py`, `coordination/status_surface_guard.py`.
- `src/specify_cli/workspace/context.py` is owned here ONLY for `resolve_lane_base_ref` (#4969): a one-function edit; touch nothing else in that file.
- Charter Standing Order #5: non-vacuous gate = concrete scanned-file floor + a planted violation per argv form that must fail + an owner-bypass positive control.

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP02`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T007 — Census gate first (red)

1. Read `tests/architectural/_git_path_listing_census.py`, `_destructive_op_census.py` and `test_git_path_listing_owner.py`. Reuse their helpers (`iter_py_files`, `parse`, `module_string_constants`, `resolve_token`, `argv_tokens`, `ordered_subsequence`, `scan_planted_source`, `src_files`, `_call_tokens` / `_argv_kinds`, `OWNER_ROOT`) — do NOT write a new AST walker.
2. `tests/architectural/_remote_contact_census.py`: a `classify_argv(tokens) -> str | None` returning `fetch` / `ls-remote` / `pull` / `clone` / `remote-show` (only when `remote` is followed by `show` and no `-n`), and a `census()` over `src/` excluding `OWNER_ROOT = src/kernel/git/`. It must catch argv lists with a leading `"git"`, with `-C <dir>` before the subcommand, and argv passed WITHOUT `"git"` to wrappers (`_run([...])`, `_git(...)`, `run_git(cwd, "fetch", ...)`, `deadline.run`).
3. `tests/architectural/test_remote_contact_owner.py`:
   - `test_no_remote_contact_outside_kernel_git` — census hits == `[]` (EMPTY allowlist; there is no allowlist constant at all).
   - `test_census_scans_enough_files` — floor (count today's scanned files, set floor slightly below, e.g. 90%).
   - one planted-source test per argv form (fetch, ls-remote, pull, clone, remote show, `-C` form, wrapper form) → must be detected.
   - `test_remote_show_dash_n_is_not_contact` — planted `remote show -n origin` NOT flagged.
   - owner-bypass positive control: running the census with the owner exclusion disabled finds ≥ 1 hit inside `src/kernel/git/remote.py`.
4. Run: the main test must FAIL listing the 5 sites. Commit (red).

### T008 — `remote_probes` on the kernel

- `_no_prompt_env` → import `kernel.git.remote.no_prompt_env` (delete the local copy and `_DEFAULT_SSH_COMMAND`; keep a module alias only if a test imports the private name — check `tests/specify_cli/git/test_remote_probes.py`; if so, update the test import rather than keeping a shim).
- `_ls_remote_heads(repo, remote, branch)` → `remote_heads(repo, remote, [branch], timeout=_LS_REMOTE_TIMEOUT_SECONDS)`: hit → `True`, `{}` → `False`, `RemoteUnreachable` → `None`. `_configured_remotes` stays a local config read (it is not a remote contact) — leave it or move to `run_git`.
- Docstring: state that `RemoteLookup` is built from `remote_heads` outcomes, that its all-remotes EXISTENCE semantics are deliberately distinct from the freshness rule (FR-017), and that the per-process `_CACHE` is never consulted for freshness (a fetch in the same process can make it stale).

### T009 — `push_preflight` on the kernel

- The fetch at `:160-200` → `fetch_branches(repo, remote, [target], timeout=FETCH_TIMEOUT)`; map `RemoteUnreachable` to the SAME `TargetBranchRefreshStatus` failure payload as today (read the current error handling carefully; messages must not change). The `attempted=False, success=True` no-remote semantics stay.
- The ahead/behind computation at `:248-275` → `divergence(repo, local, tracking)` (one `--left-right` call); the four state strings, `no_tracking_branch` on error, and left/right orientation stay identical.
- Keep `remote_name="origin"` default and `_resolve_tracking_branch` (`@{upstream}` → `origin/<b>`) UNCHANGED — residual recorded in the ADR (FR-015).
- Leave the `*Sync*` identifiers as they are (spec Out of Scope); do not rename public names.

### T010 — `protection_policy` + doctrine `git_source`

- `protection_policy.py:467`: replace `_run(["remote","show","origin"])` with `describe_remote_head(repo, "origin")`; same parsing result, same `None` on failure. This also gives it a timeout and no-prompt env it lacked.
- `doctrine/sources/git_source.py:88` (clone) and `:146` (fetch --tags origin) → `clone_repository` / `fetch_tags` with the same flags. It sets `GIT_TERMINAL_PROMPT=0` itself today (`:247`) — the kernel env supersedes it; keep any other env it passes. Check `tests/specify_cli/doctrine/test_sources.py` (or grep `git_source`) still passes.

### T011 — #4969 ref builders

- `workspace/context.py::resolve_lane_base_ref`: `origin_ref = tracking_ref(resolve_remote(repo_root, lane_branch) or "origin", lane_branch)`; keep the existence check and the `fallback_base` return. Behaviour for an `origin`-only repo is identical.
- `lanes/implement_support.py` (~:933-990, `resolve_base_ref`): it builds the short `origin/<base>`; switch to `tracking_ref(...)` + the same ancestry rule. Keep the returned effective ref NAME form the callers and tests expect (if callers/tests assert `origin/<x>`, return the short form derived from the resolved remote, i.e. `f"{remote}/{base}"`; do not change user-visible strings).
- Run `tests/terminus/test_repro_4969.py` and the implement_support tests.

### T012 — Gate green, affected tests

```bash
.venv/bin/python -m pytest -q tests/architectural/test_remote_contact_owner.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py
.venv/bin/python -m pytest -q tests/specify_cli/git/test_remote_probes.py tests/consolidation/test_push_preflight.py tests/consolidation/test_target_branch_preflight.py
.venv/bin/python -m pytest -q tests/terminus/test_repro_4969.py tests/specify_cli/lanes/test_lane_base_seam.py
.venv/bin/python -m pytest -q $(grep -rl "protection_policy\|git_source\|implement_support\|resolve_lane_base_ref" tests --include=*.py | sort -u | tr '\n' ' ')
.venv/bin/python -m pytest -q tests/architectural/test_no_dead_symbols.py   # kernel.git.remote names now have callers except those WP03 adds (resolve_remote may already be used here)
.venv/bin/ruff check <changed files> && .venv/bin/ruff format --check --force-exclude <changed files> && .venv/bin/mypy <changed src files>
```

## Definition of Done

- [ ] Census test committed red first, then green with no allowlist.
- [ ] Every planted form detected; `remote show -n` not flagged; owner-bypass control finds kernel hits.
- [ ] Drained modules' existing tests pass unchanged (or only import-path updates for moved private helpers, each justified).
- [ ] No behaviour change in push safety (FR-015).

## Risks

- `push_preflight` tests mock `_git` with fixed call sequences — moving the fetch changes the seam; update mocks to patch `kernel.git.remote` functions instead, without weakening assertions.
- doctrine clone flags (depth/branch) must be byte-identical.

## Reviewer Guidance

Run the census with one site reverted (e.g. re-add a raw fetch) and confirm red. Confirm the gate has no allowlist variable. Diff the push_preflight state strings.

## Activity Log

- 2026-10-06 — prompt generated.
