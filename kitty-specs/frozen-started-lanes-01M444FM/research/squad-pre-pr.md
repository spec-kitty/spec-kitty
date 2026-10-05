# Pre-PR squad: findings and dispositions

**Cast:**
- `reviewer-renata` (correctness): READY, with folds;
- `architect-alphonso` (regression risk): FOLD FIRST;
- `reviewer-renata` (test quality): READY, with LOW folds.

| # | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| 1 | MED | regression | Refuses when the coordination worktree is unmaterialized even though nothing started; origin/main succeeds | changed: read the committed coordination-branch status log read-only; refuse only when it is unreadable |
| 2 | MED | correctness | A freeze-induced lane dependency cycle surfaces only after the status writes (or as a generic error under validate-only) | accepted: the preflight re-raises `LaneDependencyCycleError` before the first write, with its existing envelope |
| 3 | LOW | correctness | The refusal prefix claims a lane change for `status_unreadable` | accepted: reason-specific prefix |
| 4 | LOW | correctness | `_missing_status_surface_cause` maps only `StatusReadPathNotFound` | accepted: also maps `ValueError` / `FileNotFoundError` |
| 5 | INFO/LOW | correctness, regression | `--validate-only` now reads `lanes.json`; the CHANGELOG omits some reasons and the new rule value | accepted: CHANGELOG completed; noted in the PR body |
| 6 | LOW | test quality | Private-helper imports across test modules, duplicate `_invoke`, timeout above `pytest.ini`, repeated commit args, slow coordination tests, test `type: ignore`, patches started outside an `ExitStack` | accepted: test tidy commit |
| 7 | INFO | test quality | The red-first evidence for the pre-consolidate fold lives only in the commit message (same commit) | accepted as is: the mutation check confirms the tests catch the defect |
