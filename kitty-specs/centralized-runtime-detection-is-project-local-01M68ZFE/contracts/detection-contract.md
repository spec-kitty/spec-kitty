# Contract: `uses_centralized_runtime(project_path) -> bool`

Mission: `centralized-runtime-detection-is-project-local-01M68ZFE` · Issue #6551
Owner: `src/specify_cli/upgrade/compat.py` (the single answer; C-002)

This predicate answers one question: **does *this project* use the 2.x centralized
runtime model, where missions live in the global runtime and project-local
missions are therefore optional?** It is consumed by exactly two call sites,
`0.6.7_ensure_missions.detect()` and `0.12.0_documentation_mission.detect()`.

## Truth table

`S` = a readable `.kittify/metadata.yaml` whose `version` parses as `>= 2.0.0`.
`H` = `~/.kittify/cache/version.lock` exists (`global_runtime_configured()`).
`K` = the project has `.kittify/`. `W` = the path has `kitty-specs/`.

| project stamp | `H` | `K` | `W` | answer | why |
| --- | --- | --- | --- | --- | --- |
| `S` (>= 2.0.0) | any | any | any | `True` | the project says it is 2.x; the home is irrelevant (#6551) |
| parseable `< 2.0.0` | any | any | any | `False` | a datable legacy project keeps its repair |
| present, unparseable or non-string | any | any | any | `False` | undatable is not evidence of 2.x (fail closed) |
| absent | `H` | `K` present | any | `False` | ambiguous metadata-less repo keeps the legacy repairs |
| absent | `H` | `K` absent | `W` | `True` | metadata-less worktree, runtime-managed |
| absent | `not H` | any | any | `False` | no project stamp and no bootstrapped home |

The only row this contract changes relative to the pre-#6551 code is row 1 with
`not H`: it answered `False` there, which is how a 4.x project on a fresh machine
gained 22 frozen mission overrides.

## Invariants

1. **Pure**: no writes, no bootstrap, no `ensure_runtime()`. Reading the answer
   never creates `~/.kittify` or touches the project (NFR-002).
2. **Deterministic per commit**: for a project carrying a readable stamp, the
   answer does not depend on the machine or the operator's home. That is what
   makes a `skipped` ledger record idempotent under ledger-diff re-evaluation
   (ADR `2026-10-17-1` §3, C-001).
3. **One owner**: no second predicate may answer the same question (C-002).

## Proof

- `tests/upgrade/test_compat.py` — rows 1, 2, 3, 4, 5 (`fast` tier).
- `tests/upgrade/test_upgrade_empty_home_noop.py` — rows 1 and 2 at the
  production entry point: a converged 4.x project under an empty home commits
  nothing, and a 1.9.0 project under the same empty home still receives the
  missions (`integration` + `git_repo`).
