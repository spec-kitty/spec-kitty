---
affected_files: []
cycle_number: 2
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T13:51:50Z'
reviewer_agent: claude-reviewer
wp_id: WP09
---

# WP09 review feedback — cycle 2 (reviewer-renata)

Verdict: CHANGES REQUESTED. One mechanical blocker. The substance of cycle 2 is correct and closes both cycle-1 blockers.

I ran 9 mutations against `.github/workflows/packs.yml`, and every one is now caught:
- M1, M2, M6: the corpus job `if:` inverted, narrowed to `corpus`, or using `&&`.
- M3, M5, M7: the manifest `if:` inverted, narrowed to `built_in`, or duplicated to `built_in || built_in`.
- M4: `pull_request` renamed in the selection guard.
- M8: the zero-SHA check flipped.
- M9: `push` dropped from the `corpus` output fold.

I reverted the file afterwards, and it is byte-clean.

## Blocking

1. **tests/release/pinning_rule_inventory.json — the inventory is stale, so the WP's own Test Strategy check goes red.**
   - Problem: commit 3a9808dda9 adds 6 import lines (`itertools`, `os`, `shutil`, `subprocess`, `sys`, `from tests.ci.test_ci_module_wiring import _eval_gh_if`) to `tests/architectural/test_ci_corpus_trigger_completeness.py`. That shifts the pinned rule `test_ci_corpus_trigger_completeness.py::_CI_QUALITY` from line 49 to line 55. The inventory still records `"lines": [49]`.
   - Two checks fail as a result:
     - `uv run --frozen python scripts/ci/derive_pinning_inventory.py --check` reports "pinning_rule_inventory.json is stale".
     - `uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py` fails `test_inventory_is_reproducible_by_rerunning_the_derivation` (1 failed, 4 passed).
   - Both are green at 3a9808dda9~1, so the red comes from this commit.
   - Required fix: run `uv run --frozen python scripts/ci/derive_pinning_inventory.py`. The only expected diff is `49` → `55` on the `_CI_QUALITY` row: no disposition change, and no `disposition: null`. Commit that change, then confirm `--check` and `tests/release/test_pinning_inventory_fresh.py` are green.

## Non-blocking

2. Importing `_eval_gh_if` from `tests/ci/test_ci_module_wiring.py` is acceptable:
   - There are about 130 precedents of `from tests.<x>.test_<y> import` in the tree.
   - The imported module is side-effect-free at import.
   - Collection does not duplicate: the file collects 21 items, and runs in both orders and under `-n 2 --dist loadfile` give 39 passed.
   - If a third consumer appears, promote the evaluator to a shared helper module, for example `tests/ci/_gh_if.py`.
3. The marker tier is right. The file is `architectural`, not `fast`, so a git subprocess is allowed under the `fast` marker definition, and about 64 other architectural files use `subprocess`. The whole file runs in about 1.5 s, and every test takes under 1 s.
4. Hermeticity: `_run_selection_step`'s `git commit` inherits the global git config through `HOME`. A developer with `commit.gpgsign=true` or a global hook could see a spurious failure. Consider `-c commit.gpgsign=false` or `GIT_CONFIG_GLOBAL=/dev/null` for the throwaway repo.
5. `mypy --strict` on the file: the 3 errors at lines 59, 64 and 288 are pre-existing and identical at cycle 1. The import now also pulls in 4 pre-existing errors from `tests/ci/test_ci_module_wiring.py`. No new code introduces an error.
