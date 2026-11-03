# Research — #6966, corpus reality check red

## Grounding (done before any planning artifact)

Reproduction attempts, all from a clean tree:

| Checkout shape | Commit | Result |
| --- | --- | --- |
| Standalone clone, primary checkout | `9aed3a8012` (current `main` at the time) | `870 passed, 5 skipped` — green |
| Standalone clone, primary checkout | `7bc7b6964e` (the commit in the report) | `812 passed, 5 skipped` — green |
| `git worktree add` — a linked worktree of a clone | `7bc7b6964e` | `8 failed, 804 passed, 5 skipped` |
| `git worktree add` — a linked worktree of a clone | `9aed3a8012` | 5 of the 8 named tests fail |

`main`'s own `tests (corpus-blocking)` job (the job that owns this module — *not*
`tests (contract tools)`, which `--ignore`s it: `.github/workflows/ci-router.yml` line 1480)
is green on six consecutive `main` pushes on 2026-11-02.

**Conclusion 1:** the corpus has not drifted from the oracle. The report's reading
("the corpus oracle and the dogfood corpus have drifted apart on `main` itself") is wrong.
**Conclusion 2:** the red is real, and it is a property of the *checkout shape*, not of the corpus.

## Root cause

`tests/contract/test_mission_status_reality.py:79`:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
```

The Mission resolver does not answer with the checkout root. For a Mission whose stored topology is
coord-less or un-backfilled, `candidate_feature_dir_for_mission` resolves **PRIMARY**
(`src/specify_cli/missions/_read_path_resolver.py:1314`, documented at length: "A mission whose stored
topology is coord-less (`SINGLE_BRANCH` / `LANES`) therefore resolves PRIMARY"). The primary worktree is
the first entry of `git worktree list --porcelain`.

So in a linked worktree the check enumerates `kitty-specs/` from the worktree and reads every Mission
from the primary worktree's copy. Measured on `9aed3a8012` in `<scratch>/wt-main`, with the resolver's
answer printed:

```
DIAG-OUTSIDE name= 002-lightweight-pypi-release outcome= <worktree>/kitty-specs/002-...
DIAG-OUTSIDE name= 003-auto-protect-agent  outcome= <worktree>/kitty-specs/003-...
...
DIAG-SCAN-500 mission= 002-lightweight-pypi-release err= ScanUnreadable('ReadDirOutsideRoot') root= <scratch>/wt-main
```

Two readers then disagree about that same condition:

| Reader | File | Outside `repo_root` |
| --- | --- | --- |
| drift scan | `tests/contract/_mission_status_drift.py::resolve_scan_dir` | raises `ReadDirOutsideRoot` → `500 drift_scan_unreadable` for the **whole** report (AD-10) |
| Project read | `tests/contract/_mission_status_projection.py`/`_mission_status_project.py::read_dir_of` | falls back to the Mission's own directory with a third reason `outside root` |

Downstream, that produces exactly the reported reds: `KeyError: 'findings'` (five tests index a body
that is a refusal envelope — the symptom #5927 recorded), `project fallbacks: only the reader has [...]`
(the invented third reason the oracle never derives), and the `DriftReport` schema failure.

## Decision

Fix the **root**, once: resolve the corpus root to the repository's primary worktree root, falling back
to the given path when git cannot answer. Do not touch the readers (D-4 in `plan.md`): their behaviour is
contract behaviour, and a reader that re-derives a Mission's directory to agree with the oracle would be
a second read-path authority.

## Prior art / references

- #5927 — the same three symptoms, still open. Its `KeyError: 'findings'` and "drift read answers 500"
  are this root, not a payload change.
- #6915 / `2bb498de00` — the pinned contract bundle and tools; unrelated to this red (the same tests are
  green in a primary checkout before and after it).
- `git worktree list --porcelain` is already the oracle's own read
  (`tests/contract/_mission_status_oracles.py::worktree_branches`), so the helper reuses the same seam
  (`run_git`) rather than adding a new one.

## Open questions (resolved in the plan)

- Should the readers be changed instead? No — see D-4.
- Cost of the lookup? One `git` call per test process, at import (D-3).
