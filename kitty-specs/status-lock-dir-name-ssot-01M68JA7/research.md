# Research — status-lock directory name single-source (#6516)

Discovery for `status-lock-dir-name-ssot-01M68JA7`. Recorded before the plan; the
plan step extends this file rather than replacing it.

## Evidence

| Fact | Where |
| --- | --- |
| The literal under test | `src/specify_cli/status/locking.py:65` — `_NON_GIT_LOCK_HOME = ".spec-kitty"` |
| Its only consumer | `locking.py:_git_common_dir` — the third branch of the non-git fallback, `Path(repo_root / _NON_GIT_LOCK_HOME)` |
| Why it exists | #6367 (`12d3f5f9fc`): taking a status lock in a bare non-git tree used to mint `<root>/.kittify`, turning every sibling `tmp_path` into a fake project for later `locate_project_root` walks. The fallback must create **no** project or repository marker. |
| Why the gate is green today | #6582 (`88e6589871`) appended `src/specify_cli/status/locking.py` to `_HOME_LITERAL_ALLOWLIST` in `tests/audit/test_no_legacy_path_literals.py` to clear a nightly escalation. Issue #6516 says explicitly: "Do not allowlist it blindly." |
| Guard internals | `_BARE_SPEC_KITTY_LITERAL = re.compile(r"""['"]\.spec-kitty['"]""")`; `_scan_global_state_for_home_literal(root, allowlist)` scans `src/specify_cli` + `src/kernel`; `test_home_literal_guard_is_non_vacuous` scans with `frozenset()` to prove the matcher bites |
| The name is already owned | `specify_cli.paths.windows_paths.get_runtime_root()` computes the runtime state root; on POSIX/fallback it is `Path.home() / ".spec-kitty"`. That module is the allowlisted keystone ("the ONE place the default home is computed") and is a documented leaf (no imports of `specify_cli.auth`/`tracker`/kernel subsystems). |
| The same directory name, second copy | `src/specify_cli/review/lock.py:36` — `LOCK_DIR = ".spec-kitty"` (worktree-local review lock; also allowlisted). Re-exported: `cli/commands/agent/workflow.py` imports it to `exclude_from_git_index`. |
| Behaviour pins | `tests/status/test_lock_fallback_never_mints_marker.py` (three fallback branches + end-to-end walk), `tests/status/test_locking_reentrancy_migration.py:116`, `tests/git_ops/test_atomic_status_commits_unit.py` |
| Doctrine | Tactic `architectural-gate-non-vacuity`: keep the sanctioned owner separate from grandfathered exceptions; prefer draining exceptions; a concrete floor, a self-mutation test and (aspirationally) a routed-count floor keep the gate honest. Tactic `acceptance-criteria-non-vacuity`: same-fixture positive controls, half-by-half proof. |

## Decisions

**D1 — the fallback stays repository-local; the directory *name* moves.** The
literal names `<repo_root>/.spec-kitty`, not the user-global home. Pointing it at
`get_runtime_root().base` (what the gate's failure text suggests, and the
shortest reading of "route it through the resolver") would move lock state out of
the tree being locked, put it in the user's home for throwaway non-git trees, and
serialise unrelated bare trees whose mission-directory name collides — a
behaviour change #6367 had just settled the other way, pinned by three tests.
So the *location* is a hard constraint (spec C-001) and the *name procurement* is
the defect: it is typed a second time in a global-state module.

**D2 — the owner is the existing path authority, not a new module.** The gate
already sanctions exactly one place that computes the runtime state default:
`src/specify_cli/paths/windows_paths.py`. Naming the directory *name* there (and
using it in `get_runtime_root()`'s own branches) keeps the allowlist from
growing: `status/locking.py` and `review/lock.py` both leave it. A new
`core/constants.py` owner would have to be allowlisted itself — a second
exemption for the same string, which is the pattern the tactic calls debt.

**D3 — drain both exemptions, not one.** `review/lock.py` hand-rolls the same
name the same way; converting only `status/locking.py` would leave a
"canonical owner + one grandfathered sibling" split, and would be the first
finding of any review round. Both conversions are value-identical (`".spec-kitty"`
stays the name), so no test assertion changes.

**D4 — pin the exemption out of existence.** Beyond removing the entry, add a
guard assertion that an allowlist-bypassed scan (`frozenset()`) reports no
`src/specify_cli/status/locking.py:` violation. That is the self-mutation half of
the gate tactic: re-adding the literal *and* the allowlist entry still goes red.

**D5 — the CI-routing half is deferred.** Issue #6516's second gap (a
`src/specify_cli/status/**` diff does not route `tests/audit/**` per PR — the
reason #6367's PR never saw the gate) lives in `.github/ci-router.yml` path
groups and `.github/ci-module-registry.yml` module rows. A new per-PR audit lane
is a cost decision for the maintainer, and the registry edit is census-gated.
Filed as a follow-up; named in the PR's `## Deferred` section.

## Open questions (settled before planning)

- ~~Does `review/lock.py` stay in scope?~~ Yes (D3); the constant keeps its public
  name `LOCK_DIR` so the three test files and `workflow.py` that import it are
  unaffected.
- ~~Is a behavioural test needed for the new dispatch?~~ No new branch is added;
  the changed lines are module-level constants and their two `get_runtime_root()`
  uses, covered by the existing runtime-root tests. The behavioural pins that
  matter (lock location, no-marker walk) exist and stay unmodified.
