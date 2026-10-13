---
title: 'Tracer: approach'
updated: 2026-10-13
type: explanation
mission: declaration-first-repo-root-resolution-01M4TB21
---

# Approach tracer

Sequence (tidy-first; behaviour-preserving enablers BEFORE the red-first correction):

1. **Enabler (behaviour-preserving):** introduce the typed declaration-first
   `(repo_root, target_branch, provenance)` value + resolver in a new `specify_cli.core`
   module, built on the existing public resolvers. Unit-test every branch directly.
2. **Enabler (behaviour-preserving):** route the bounded, named set of mission-scoped
   command-entry `Path.cwd()`/branch seeds through the entry; fold the hand-placed
   "never `Path.cwd()`" guards at those sites into the typed call so the invariant holds
   by construction.
3. **Behaviour correction (red-first):** a mission-scoped command whose ambient location
   disagrees with the Mission's stored declaration now resolves to the declaration (or
   fails closed). Commit the failing test first, then the fix. Negative tests witness
   that #3128 / #3328 refusals and worktree-invocation behaviour are unchanged.

Rebase cadence (Mission): onto the canonical remote's `main` after spec, after plan,
after tasks (before implement); thereafter only on a staleness notice.
Testing: `make test-fast` + touched-module test files + owning-subsystem dirs + the
specific named gate files — never the heavy suites, never `make test-full`.

## Execution record (as landed)

- **WP01** — `specify_cli/core/command_target.py` (`CommandRepoTarget`, `TargetProvenance`,
  `resolve_command_repo_target`) + `tests/specify_cli/core/test_command_target.py`. Genuine
  red-first: the unit contract was committed RED (module absent) then GREEN. 171-test gate
  sweep (entry test + `test_no_write_side_rederivation.py` + `test_layer_rules.py` +
  `test_pyproject_shape.py`) passed — ratchet green with **no allowlist change**.
- **WP02** — routed `mission_record_analysis.py` (both target-branch sites) through the
  entry; `tests/specify_cli/cli/test_command_target_routing.py` + the three record-analysis
  regression suites passed (31) — behaviour-preserving, no regression.
- **WP03** — behaviour-correction witness (`test_command_target_behaviour.py`) and
  fail-closed preservation (`test_declaration_first_failclosed_preserved.py`:
  #3128 `enforce_checkout_identity`, #3328 `resolve_checkout_identity`,
  `get_status_read_root` read contract) + deferred-scope hygiene (follow-up issue,
  changelog, Refs #2802/#5114).
