# Implementation Plan: Corpus reality check resolves the repository root, not the checkout root

**Branch**: `issue-6966-corpus-reality-root` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/corpus-reality-root-primary-worktree-01M6ER45/spec.md`

## Summary

`tests/contract/test_mission_status_reality.py` derives its repository root from the checkout it is
imported from (`Path(__file__).resolve().parents[2]`). The Mission resolver, by contrast, answers each
Mission's read directory from the **primary worktree** of the repository. From a linked worktree the
corpus check therefore enumerates one tree and reads Missions out of another, and two readers in the
same corpus react differently to that: the drift reader refuses the whole report with
`500 drift_scan_unreadable`, while the Project reader invents an `outside root` fallback the oracle
never derives. Both are reported as corpus drift; neither is drift.

The fix is one root decision, taken once, at the entry point of the corpus check: resolve the corpus
root to the repository's primary worktree root (first `worktree` entry of
`git worktree list --porcelain`), and keep the given path when git cannot answer. No reader, no
assertion, no floor, no ceiling and no skip changes.

## Technical Context

**Language/Version**: Python 3.11 (`tests/contract`, pytest, no runtime code change)
**Primary Dependencies**: `pytest`; the reference readers under `tests/contract/_mission_status_*.py`;
`git` via `subprocess` (already used by `_mission_status_oracles.run_git`)
**Storage**: the committed dogfood corpus (`kitty-specs/`, `kitty-ops/`)
**Testing**: `uv run pytest tests/contract/test_mission_status_reality.py -m "corpus and not windows_ci"`
from both a primary checkout and a linked worktree of the same commit
**Target Platform**: Linux/macOS developer hosts and the `tests (corpus-blocking)` CI job (ubuntu-24.04)
**Project Type**: single project (test infrastructure only)
**Performance Goals**: at most one additional `git worktree list --porcelain` per test process; none
per test
**Constraints**: no `src/` change; no gate weakened; the primary worktree is read-only
**Scale/Scope**: 2 files under `tests/contract/`, one docs note, one changelog fragment

## Charter Check

| Gate | Applies | How this plan satisfies it |
| --- | --- | --- |
| Single canonical authority | yes | One owner for the root decision (`oracles.primary_worktree_root`), called from one place (the module's `REPO_ROOT`). The readers keep trusting the resolver (C-001); no second read-path derivation appears. |
| ATDD-first / red-first | yes | The pinning test is written and seen red before the helper exists, through the pre-existing entry point (the module's `REPO_ROOT` and the real `git worktree list`). |
| No duplicate authority | yes | The worktree listing is not re-implemented: the helper reuses `oracles.run_git`, the module's existing git seam. |
| Locality of change / smallest viable diff | yes | Two files, one new function, one changed expression, one new test. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | yes | Only the corpus-marked reality module plus the two routing/pin modules that name it. |
| Pre-existing Failure Reporting Rule | yes | The linked-worktree red is reproduced on `main` before any change and is the subject, not accepted baseline; #6966 and #5927 already record it. |

## Design Decisions

- **D-1 — The root is a property of the repository, not of the checkout.** `git worktree list
  --porcelain` lists the primary worktree first; its root is the tree the resolver, the corpus and the
  oracle all mean. `Path.resolve()` normalises both sides, matching the readers' existing resolved-path
  comparisons.
- **D-2 — Fail soft, never silently wrong.** When git is absent, the directory is not a repository, or
  the listing fails (non-zero exit, `OSError`, `subprocess.SubprocessError`), the helper answers the
  given path. On such a host there is no worktree layout to get wrong, and the module must still import
  and collect: `REPO_ROOT` is evaluated at import time.
- **D-3 — One call, at import.** `REPO_ROOT` is a module constant used by parametrisation and by the
  oracle helpers, so the lookup cannot be a fixture. It is evaluated once per test process.
- **D-4 — Do not fix the readers.** `resolve_scan_dir`'s 500 for a read directory outside the checkout
  root is contract behaviour (`AD-10`: a read the scan cannot do its job without is refused, never
  partly answered) and `read_dir_of`'s fallback mirrors the v1 reads. Changing either is a contract
  change with its own mutation catalogue; the mixed tree, not the readers, is the defect.
- **D-5 — The trade-off is stated, not hidden.** From a linked worktree the check now reads the
  primary worktree's corpus. That is the tree the resolver names, and it is what CI (a primary
  checkout) always reads; the docs note says so, and the changelog fragment says so.

## Project Structure

### Documentation (this mission)

```
kitty-specs/corpus-reality-root-primary-worktree-01M6ER45/
├── spec.md
├── plan.md              # this file
└── tasks/               # work packages (/spec-kitty.tasks)
```

### Source Code (repository root)

```
tests/contract/
├── _mission_status_oracles.py    # + primary_worktree_root(repo_root)  (the one owner)
└── test_mission_status_reality.py# REPO_ROOT = oracles.primary_worktree_root(...)  + the pinning test

docs/development/reference/ci-gate-mechanics.md   # which tree the reality check reads
docs/changelog/unreleased/<pr>.internal.md        # the changelog fragment
```

## Risks

- **R-1 — Reading the wrong tree from a worktree.** A developer testing an uncommitted corpus change
  from a linked worktree will check the primary worktree's corpus instead. Mitigated by the docs note
  and the changelog text; the alternative (a reader that re-derives a directory to agree with itself)
  is a worse contract violation.
- **R-2 — Import-time subprocess.** `REPO_ROOT` is import-time by necessity (see D-3); the failure
  modes above all degrade to the given path rather than raising, and the cost is one process per
  test process.
- **R-3 — Shared-machine churn.** The primary worktree of a worktree checkout is a tree another process
  may be writing to. The module's existing tree-write guard still runs first, and no new write is added.

## Testing Strategy

1. **Red-first pin (FR-002, FR-003, SC-003)** — a new test builds a real repository in `tmp_path` with a
   linked worktree and asserts `primary_worktree_root` answers the primary root from **both** paths, and
   the given path for a directory git cannot answer for. Run before the helper exists: `AttributeError`,
   then green.
2. **Behavioural proof (FR-001, SC-001)** — `git worktree add --detach <tmp> origin/main`, sync packs,
   run the corpus-marked reality suite inside the worktree; before the change 5 named tests fail with
   `KeyError: 'findings'` / `project fallbacks`, after it they pass.
3. **No-weakening proof (NFR-002, SC-002)** — the same suite from the primary checkout keeps
   `870 passed, 5 skipped`, and `git diff` on the module shows only the one root expression plus the new
   test.
4. **Routed cheaply** — `tests/ci/test_contracts_routing.py` (the module's home) and the corpus suite;
   no heavy, e2e or architectural battery is needed for a test-only root expression.
