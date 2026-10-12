# Defect diagnosis — #5903: `safe_commit` silently commits hook-staged paths

> Disciplined defect diagnosis (Charter Standing Order 4, `DIRECTIVE_041`/`DIRECTIVE_034`).
> Reproduced RED-FIRST through the pre-existing entry point before any fix.
> Mission: `safe-commit-hook-staged-paths-01M4RKV7`. Base: `origin/main` @ `8a911083`.

## 1. Witnessed reproduction (live evidence)

A pre-commit hook that stages files itself (`git add -u`, as formatter / lint-staged-style hooks
do) sweeps the operator's **unstaged** tracked edits into a `safe_commit` commit. During
`git commit --only -- <paths>` git points `GIT_INDEX_FILE` at its own temporary index while the
hook runs, so the hook's `git add -u` stages every modified tracked file into the commit being
built. The commit then carries files the operation never wrote, `safe_commit` returns success
(exit 0), and the operator's real index is left staging a revert of the swept edit (`git status`
shows `MM`).

Harness (library-level, all three routes): `research/` fixtures build a repo with a `git add -u`
pre-commit hook, `tool.txt` (the file the operation writes) and `operator.txt` (an unstaged
in-progress edit), then call `safe_commit` on each route. Equivalent to #5903's CLI repro
(`spec-kitty safe-commit tool.txt -m "tool commit"`).

```text
===== ROUTE: --only  safe_commit(paths=(tool.txt,)) =====
  returned CommitResult (exit-0 success)
  committed paths : ['operator.txt', 'tool.txt']
  requested paths : ['tool.txt']
  git status -s   : 'MM operator.txt'
  :operator.txt   : 'v1'        # real index stages a REVERT of the operator's draft
  VERDICT         : RED (extra paths swept in: ['operator.txt']); reported-success-silently=True

===== ROUTE: FR-022  safe_commit(paths=(tool.txt,), index_deletions=(untrack.txt,)) =====
  returned CommitResult (exit-0 success)
  committed paths : ['operator.txt', 'tool.txt', 'untrack.txt']
  requested paths : ['tool.txt', 'untrack.txt']
  git status -s   : 'MM operator.txt\n?? untrack.txt'
  :operator.txt   : 'v1'
  VERDICT         : RED (extra paths swept in: ['operator.txt']); reported-success-silently=True

===== ROUTE: expected-parent control  safe_commit(..., expected_parent_sha=HEAD) =====
  returned CommitResult (exit-0 success)
  committed paths : ['tool.txt']
  requested paths : ['tool.txt']
  VERDICT         : GREEN (no extra paths); reported-success-silently=False
```

Both affected routes are RED; the expected-parent route is the GREEN negative control — it rebuilds
the commit tree from the requested paths only, so a hook's extra staging is dropped.

## 2. Responsibility map — `src/specify_cli/git/commit_helpers.py`

| Symbol | Lines (base) | Role | Post-landing check today |
|--------|--------------|------|--------------------------|
| `safe_commit(...)` | 1616–1897 | Public entry. Routes to FR-022 (`index_deletions`), expected-parent (`expected_parent_sha`), or the default `--only` path. | **None** on the `--only` success path (1891–1897): returns immediately after the commit. |
| `_run_commit_capture_sha(...)` | 904–954 | Runs `git commit --only -- <paths>`; the hook runs against git's temp index here. | — |
| `_commit_with_index_deletions(...)` | 1037–1080 | FR-022 temp-index route: commits from a temp index seeded from HEAD under its own `GIT_INDEX_FILE`; the hook runs against that temp index. | Calls `_sync_real_index_after_commit([*requested, *deletions])` only — the swept extra paths are **not** synced and **not** checked. |
| `_sync_real_index_after_commit(...)` | 1018–1034 | `git reset -q HEAD -- <paths>` to make the real index match the new HEAD for the named paths, then raises `SafeCommitIndexResidue` if residue remains. | The pattern to reuse for the index re-sync. |
| `_safe_commit_with_expected_parent(...)` / `_build_expected_parent_tree(...)` | 1362–1460 / 1164–1209 | Expected-parent route: runs hooks against a candidate index, then **rebuilds the tree from the requested paths only** → extra hook-staged paths are dropped. | Correct by construction — the negative control. **Do not change.** |

### Existing "landed, but" reporting to mirror

- `SafeCommitRecoveryFailed` (283–316): base for "the commit path ran but caller staging could not
  be restored"; carries `unrecovered_paths`, `orphan_stash_ref`, `commit_sha`. `error_code =
  "SAFE_COMMIT_RECOVERY_FAILED"`.
- `SafeCommitIndexResidue(SafeCommitRecoveryFailed)` (419–445): FR-022 "the commit DID land
  (`commit_sha`) but the real index still stages a committed path". `error_code =
  "SAFE_COMMIT_INDEX_RESIDUE"`. **This is the exact shape the new error mirrors**: a
  `SafeCommitRecoveryFailed` subclass that sets `commit_sha` and names the offending paths, so
  callers that flatten a plain `SafeCommitError` into "not committed" instead re-raise and report
  the commit DID land.

**Planned new error:** `SafeCommitUnrequestedPaths(SafeCommitRecoveryFailed)`, `error_code =
"SAFE_COMMIT_UNREQUESTED_PATHS"`, carrying `commit_sha` + the extra paths. Raised only after HEAD
moved, after re-syncing the operator's real index for the extra paths.

## 3. Every `safe_commit` caller and how it surfaces "DID land" today

The "DID land" decision is **not** keyed on `SafeCommitIndexResidue` anywhere. Every surface keys on
the base class + a set `commit_sha` — so a new `SafeCommitRecoveryFailed` subclass that sets
`commit_sha` inherits correct handling with **no per-caller change**:

| Caller | Surface | "DID land" predicate |
|--------|---------|----------------------|
| `upgrade/autocommit.py:561` (`commit_touched_checkout`) | re-raises `SafeCommitRecoveryFailed` instead of flattening to "commit manually" | `except SafeCommitRecoveryFailed: raise` |
| `cli/commands/upgrade.py:1211` (`_render_safe_commit_recovery_failed`) + `:1301` | renders "Commit {sha} DID land" | `f"...DID land." if exc.commit_sha else "No commit landed."` |
| `coordination/status_transition.py:546` | keeps a landed commit's artifacts | `isinstance(exc, SafeCommitRecoveryFailed) and exc.commit_sha is not None` |
| `coordination/transaction.py:966` | skips surgical rollback after a landed commit | `isinstance(exc.__cause__, SafeCommitRecoveryFailed) and exc.__cause__.commit_sha is not None` |
| `consolidation/phase_bookkeeping.py:756` | keeps bookkeeping after landed commit | `isinstance(exc, SafeCommitRecoveryFailed) and exc.commit_sha is not None` |
| `consolidation/phase_teardown.py:168` | treats landed flatten commit as success | `except SafeCommitRecoveryFailed as exc: if exc.commit_sha is None: warn` |
| `cli/commands/agent/workflow.py:311` (`_safe_commit_recovery_commit_sha`) | walks `__cause__` chain for the landed SHA | `isinstance(current, SafeCommitRecoveryFailed) and current.commit_sha is not None` |
| `events/decision_log.py:273` | logs and preserves the already-written event line | `except SafeCommitError as exc: logger.warning(...)` (base-class catch; names the error incl. extra paths) |

**Conclusion:** FR-006 is a `[folded]` requirement — satisfied by subclassing `SafeCommitRecoveryFailed`
with `commit_sha` set. A confirming test asserts the shared predicate holds for the new class.

## 4. Contract surface + mirrors + parity gate(s)

`SAFE_COMMIT_INDEX_RESIDUE` is registered in, and only in:

1. `src/specify_cli/core/upstream_contract.json` — `allowed_error_codes` (line 147).
2. `docs/contracts/upstream-3.0.0-shape.json` — same list, kept **JSON-equal** to (1).
3. `src/specify_cli/orchestrator_api/envelope.py` — the `CONTRACT_VERSION` changelog comment
   (1.14.0 added the three #5443 codes) + `CONTRACT_VERSION = "1.14.0"`.
4. `tests/contract/test_orchestrator_api.py` — the parity gate.

Gates that enforce contract/mirror parity:

- `tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed`
  walks **every** `SafeCommitError` descendant and asserts `emitted <= allowed_error_codes`. A new
  subclass whose code is absent from `allowed_error_codes` fails here. (Non-vacuous: it also asserts
  known codes are present.)
- `tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
  asserts the vendored `upstream_contract.json` is JSON-equal to `docs/contracts/upstream-3.0.0-shape.json`
  — both mirrors must gain the code identically.
- `tests/specify_cli/orchestrator_api/test_contract_version.py::test_contract_version_response_reports_1_14_0`
  + `test_changelog_comment_names_all_design_verbs` pin `CONTRACT_VERSION` and the changelog comment.
  Registering a new verb-reachable error code is a minor bump (precedent: 1.13.0 `STATUS_LOCK_HELD`,
  1.14.0 the three #5443 safe-commit codes) → bump to **1.15.0** + a changelog-comment line, and
  update the pinning test.

## 5. Invariants to preserve

- **Expected-parent route unchanged** (C-002): it is already correct and is the negative control.
- **Clean (no-hook) `safe_commit` byte-identical** (FR-004): the check only reads `git diff-tree`
  and compares sets on success; it mutates the index and raises **only** when an extra path is
  present, so a hook-free commit returns the same `CommitResult` with the same tree.
- **Hooks still run** (NFR-002): no `--no-verify`; the check is strictly post-landing.
- **Single canonical authority** (C-001): the new code is defined once in `upstream_contract.json`
  with mirrors updated in the same change.
- **Out of scope** (per #5903): a hook that runs `git stash` against the temp index — leave it;
  note as a follow-up if adjacent code is touched.
