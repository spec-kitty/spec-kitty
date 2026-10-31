---
work_package_id: WP02
title: Caller convergence and the divergence guard
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-005
- FR-006
- FR-007
- FR-011
- SC-001
- SC-003
planning_base_branch: issue-6488-per-user-locations-single-authority
merge_target_branch: issue-6488-per-user-locations-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6488-per-user-locations-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6488-per-user-locations-single-authority unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Convergence
history:
- timestamp: '2026-10-31T08:55:00Z'
  agent: python-pedro
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/charter/offering/packs/
create_intent:
- tests/kernel/test_user_dirs_convergence.py
execution_mode: code_change
owned_files:
- src/charter/offering/packs/pack_fetch.py
- src/kernel/service_artifacts.py
- src/runtime/next/_runtime_pkg_notice.py
- src/specify_cli/compat/cache.py
- src/specify_cli/compat/config.py
- src/specify_cli/core/upgrade_notifier.py
- tests/charter_offering/test_pack_fetch_cache_root.py
- tests/core/test_upgrade_probe_and_notifier.py
- tests/kernel/test_service_artifacts.py
- tests/kernel/test_user_dirs_convergence.py
- tests/next/test_runtime_pkg_notice_unit.py
- tests/specify_cli/compat/test_config.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Caller convergence and the divergence guard

## Objective

Every production caller resolves through WP01's authority, and one test makes a future
divergence impossible to merge unnoticed.

Read: `data-model.md` ("Entity: Caller", Invariant C1) and `research.md` D1, D7.

## The six callers

| Caller | Kind | Subpath |
|---|---|---|
| `specify_cli/core/upgrade_notifier.py::_default_cache_path` | cache | `upgrade-check.json` |
| `specify_cli/compat/cache.py::_resolve_cache_dir` | cache | `upgrade-nag.json` |
| `charter/offering/packs/pack_fetch.py::default_cache_root` | cache | `open-packs` |
| `kernel/service_artifacts.py::default_cache_root` | cache | `services` |
| `runtime/next/_runtime_pkg_notice.py::_marker_path` | state | `.spec-kitty-runtime-cutover-notice-shown` |
| `specify_cli/compat/config.py::_resolve_config_dir` | config | `upgrade.yaml` |

Each edit is a call-site substitution: `user_cache_dir() / "spec-kitty" / X` becomes
`user_cache_dir() / X`. Do not change any caller's own logic, error handling or file name.

## Red-first (T005)

Write `tests/kernel/test_user_dirs_convergence.py` first and watch it fail on the pre-fix
tree. It must:

1. parametrise over the three faked platforms;
2. resolve all six callers once per platform and assert each resolved path is
   `authority_dir(kind) / <its subpath>`, i.e. equality with the authority, not a
   hard-coded copy of the path;
3. fail with a message that names the divergent caller(s) and the two paths.

Keep a positive control in the same fixture: the same six callers resolve to six distinct
paths under one tree (proving the probe can observe agreement, not just absence).

## Fallback deletion (T007)

`specify_cli/compat/cache.py::_resolve_cache_dir` and
`specify_cli/compat/config.py::_resolve_config_dir` carry `try: from platformdirs import …`
/ `except ImportError:` fallbacks that cannot run — `platformdirs>=4.9.2` is a hard
dependency (`pyproject.toml:63`). Delete both fallbacks and the imports they alone use
(`sys`, and `kernel.paths.is_windows` where it becomes unused — check the whole module
first: `compat/cache.py` uses `is_windows` at another site). Retarget
`tests/specify_cli/compat/test_config.py` so it no longer assumes the fallback exists.

## Docstrings (T008)

`runtime/next/_runtime_pkg_notice.py::_marker_path` says `platformdirs` while the code calls
`kernel.user_dirs.user_state_dir`; after this WP the statement is true, so say precisely
which directory and which rule. `NagCache.default`'s docstring lists a fallback ladder that
no longer exists — replace it with the one-line rule.

## Validation

```bash
uv run pytest tests/kernel/test_user_dirs_convergence.py -q   # the guard
uv run pytest tests/core/test_upgrade_probe_and_notifier.py \
              tests/next/test_runtime_pkg_notice_unit.py \
              tests/charter_offering/test_pack_fetch_cache_root.py \
              tests/kernel/test_service_artifacts.py \
              tests/specify_cli/compat/test_config.py -q
uv run ruff check src/charter/offering/packs/pack_fetch.py src/kernel/service_artifacts.py \
  src/runtime/next/_runtime_pkg_notice.py src/specify_cli/core/upgrade_notifier.py \
  src/specify_cli/compat/cache.py src/specify_cli/compat/config.py
```

## Definition of done

- Six callers, one rule; no caller composes the app segment itself.
- No unreachable `ImportError` fallback left in `compat/cache.py` or `compat/config.py`.
- Convergence guard red first, green after; the five per-caller pin tests updated, not
  deleted (they still pin each caller's leaf path).
- Docstrings match the code.
