---
work_package_id: WP02
title: From-scratch child environments
dependencies:
- WP01
requirement_refs:
- FR-004
- NFR-001
- C-001
- SC-003
planning_base_branch: issue-7076-test-harness-temp-ceiling
merge_target_branch: issue-7076-test-harness-temp-ceiling
branch_strategy: Planning artifacts for this mission were generated on issue-7076-test-harness-temp-ceiling. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7076-test-harness-temp-ceiling unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Story work
history:
- at: '2026-11-03T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/unit/test_harness_child_env.py
execution_mode: code_change
model: ''
owned_files:
- tests/unit/test_harness_child_env.py
- tests/upgrade/preview_support/process.py
- tests/scripts/test_activate_isolated_env.py
- tests/charter_offering/conftest_pack_remote.py
- tests/kernel/git/test_remote_fetch_commit_subtree.py
- tests/cross_cutting/packaging/test_sdist_offline_wheel.py
- tests/consolidation/test_bake_commit_scope_meta_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – From-scratch child environments

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- Each of the six sites that build a child environment from an allowlist, or copy the environment
  and strip `GIT_*`, carries the harness `GIT_CEILING_DIRECTORIES`.
- A site that already pins its own temp root (`preview_support.child_environment` →
  `<sandbox>/tmp`) keeps it; it gains the ceiling and nothing else.
- A per-test narrowing (`monkeypatch.setenv("GIT_CEILING_DIRECTORIES", <tmp_path>)`) is what the
  child inherits, not the run-wide value.
- Nothing else comes back from `GIT_*`: credentials, `GIT_DIR`, `GIT_WORK_TREE`, config
  overrides and prompts stay stripped.

## Context & Constraints

- `tests/_support/temp_root.py::harness_env` (WP01) is the single place the policy lives. Import
  it; do not re-list the variables at each site.
- Why `GIT_CEILING_DIRECTORIES` is the exception to the strips: it is a *discovery boundary*, not
  git config, credentials or a repository selector. A child without it can walk out of the test's
  tree into whatever encloses it — the failure #7022/#7056 exist to prevent.
- The ceiling is a `os.pathsep`-joined list whose leading empty entry is meaningful to git. Never
  re-parse or normalise it: copy the string verbatim.

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7076-test-harness-temp-ceiling`
- **Merge target branch**: `issue-7076-test-harness-temp-ceiling` (the operator merges; no push
  to `main`)

## Subtasks & Detailed Guidance

### T005 — Red first: the six sites drop the ceiling

Create `tests/unit/test_harness_child_env.py` (`unit`, `fast`). Import each helper and assert the
variable is present and equals the harness value, with `monkeypatch.setenv` providing a known
value first:

| Site | Helper |
| --- | --- |
| `tests/upgrade/preview_support/process.py` | `child_environment(sandbox)` |
| `tests/scripts/test_activate_isolated_env.py` | `_clean_env()` |
| `tests/charter_offering/conftest_pack_remote.py` | `_env()` |
| `tests/kernel/git/test_remote_fetch_commit_subtree.py` | `_env()` |
| `tests/cross_cutting/packaging/test_sdist_offline_wheel.py` | `_offline_env(shim_dir)` |
| `tests/consolidation/test_bake_commit_scope_meta_only.py` | `_hermetic_env` (fixture — drive it through `pytest`'s fixture request or exercise the same strip/restore via a direct call; do not duplicate the fixture's body in the test) |

Also assert the negative: with no ceiling in `os.environ`, the helpers do not invent one.

On `main` all six fail — that is the red.

### T006 — The five from-scratch helpers

- `child_environment`: it already sets `TMPDIR`/`TMP`/`TEMP` to `sandbox/tmp`. Add only
  `GIT_CEILING_DIRECTORIES` from `harness_env()`. Keep `TEMP_ROOT_VARS` ownership local to it —
  tests in `tests/upgrade` snapshot `Path(env["TMPDIR"])`, and that must stay `sandbox/tmp`.
- The four `_env`/`_clean_env` helpers: after the existing strip/filter, merge `harness_env()`.
  For the three that filter `not key.startswith("GIT_")`, the merge must come *after* the filter.

### T007 — The `GIT_*`-stripping fixture

`tests/consolidation/test_bake_commit_scope_meta_only.py::_hermetic_env` deletes every `GIT_*`
and `SPEC_KITTY_*` variable. Restore `GIT_CEILING_DIRECTORIES` from the harness (capture the
value before the loop, `monkeypatch.setenv` it after). Everything else stays deleted.

## Review Guidance

- Does any site now leak more than the ceiling (e.g. by merging all of `os.environ`)?
- Is the per-test narrowing inherited rather than the run-wide value?
- Do the six modules still pass, and does `tests/upgrade` still see `sandbox/tmp` as its temp root?

## Definition of Done

- T005's test was red before T006/T007, green after.
- `uv run pytest tests/unit/test_harness_child_env.py tests/scripts/test_activate_isolated_env.py tests/kernel/git/test_remote_fetch_commit_subtree.py -q` green.
- `uv run pytest tests/charter_offering -q -k pack_remote` and the `tests/upgrade` preview tests
  that use `child_environment` green (targeted selection; no full heavy suite).
