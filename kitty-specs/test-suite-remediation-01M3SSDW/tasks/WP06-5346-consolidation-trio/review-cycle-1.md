---
affected_files: []
cycle_number: 1
mission_slug: test-suite-remediation-01M3SSDW
reproduction_command:
reviewed_at: '2026-09-30T21:56:25Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (reviewer-renata), cycle 1

Rows 3 and 4 are approved as-is. Row 6 needs one small fold. Everything else is sound, and I re-ran it (see "Verified" at the end).

## Issue 1 (blocking): row 6 silently drops the `mission_branch` threading contract, and no guard covers it

**What happened.**
- The old `assert_called_once_with(..., mission_branch="kitty/mission-m", ...)` pins were copy pins on the *signature*.
- They were also the **only** guard that `_pre_mutation_safety_preflight_with_recovery` threads `lanes_manifest.mission_branch` into both callees.
- The new identity form (`call_args.args[0] is exc`) drops that value check. No kept assertion and no named covering guard replaces it.

That makes it a de-facto partial RETIRE of a live contract without a C-002 covering guard. `mission_branch` is load-bearing. Both callees pass it to `classify_resume_dirty_remedy(main_repo, lane_branch=mission_branch)`:
- it decides the behind-own-HEAD remedy;
- on the recover path, it gates an **in-place recovery** (#4997).

**Reviewer plant (reproduce).** At each call site in `executor.py`, replace `mission_branch=lanes_manifest.mission_branch` with `mission_branch=lanes_manifest.target_branch`:
- `:4060` (`_recover_behind_head_primary_on_resume`);
- `:4066` and `:4077` (`_report_pre_mutation_refusal`).

| Tests run under the plant | Result |
|---|---|
| NEW form: `test_behind_head_recovery_coverage.py` + `test_user_meta_json_dirty_4933.py` + `tests/architectural/test_destructive_op_routing.py` | **66 passed** (the defect is invisible) |
| e2e: `tests/terminus/test_repro_4997.py`, `tests/terminus/test_resume_phantom_only.py`, `tests/consolidation/test_behind_head_remedy.py` | **9 passed** (invisible there too) |
| OLD form (base file): plant at `:4060` alone | red, 1 failed (`:309`) |
| OLD form (base file): plant at `:4066` alone | red, 3 failed |

This is a gap in the planning prescription (pin-inventory §2.1 row 6 kept only `base_sha`), not implementer negligence. The gate still has to hold it: the mission must not trade a copy pin for a blind spot.

**Fix (small; still M2-neutral).** Assert the value by keyword lookup, not the full signature, so an extra defaulted kwarg still passes:
1. In `test_preflight_with_recovery_recovers_and_retries_successfully` (`:309`), add:
   `assert mock_recover.call_args.kwargs["mission_branch"] == "kitty/mission-m"`
2. On the first report path, in either `test_preflight_with_recovery_reports_and_exits_when_not_recovered` or the threading test, add:
   `assert mock_report.call_args.kwargs["mission_branch"] == "kitty/mission-m"`
3. On the second report path (`exc_after`), in `test_preflight_with_recovery_reports_and_exits_when_still_refused_after_recovery`, add the same `mission_branch` kwarg assertion.

Better still, use the manifest's value (`manifest.mission_branch`) rather than repeating the literal. The fixture `_manifest_and_retention()` sets `target_branch="main"` and `mission_branch="kitty/mission-m"`, so a `target_branch` mis-thread is discriminated.

**Evidence to add (FR-011, rule B).**
- **Violation:** the `mission_branch=lanes_manifest.target_branch` plant at each of `:4060`, `:4066` and `:4077`, one at a time. Each goes RED on its new assertion.
- **Neutral:** re-run the M2 neutral plant (`strategy=None` passed at all three call sites). It stays GREEN with 0 test edits.
- Revert, and confirm `git diff --stat src/` is empty.

## Non-blocking notes
- `base_sha` threading on the **second** report call site (`:4077`, the `exc_after` path) is unguarded in both old and new form: the old pin only saw `None`, because no `state.json` existed. It is not a regression from this WP. If you want it, a persisted-sha variant of the still-refused-after-recovery test closes it. It is optional and out of row scope.
- Row 4: leaving the loose disjunction on the surfacing message is correctly justified in EV-IC06-04 (prose, not a constant). Agreed.

## Verified (my re-runs, all plants reverted, tree clean)
- **Diff scope:** `49c48466f7` touches exactly the 3 owned test files. No `src/`, no committed plant.
- **Row 3:**
  - Violation (`_created_lane_worktree` returns `…-PLANT`): the covering guard `test_created_lane_worktree_matches_real_allocator_output` is RED (1 failed), and the retired class (extracted from base) is GREEN (2 passed).
  - Neutral (`worktree_dir_name` → `f"{slug}--{lane}"`): the guard is GREEN (1 passed), and the retired class is RED (2 failed). It was a toll. RK-1 drop sanctioned.
- **Row 4:** Violation A (`if not wrote: return None`) turns the renamed test RED at `assert result == 1` (None == 1). The docstring names the 4900 refusal guard.
- **Row 6:**
  - Threading plant (`base_sha=None` at `:4066`): the kept assertion is RED (1 failed, 20 passed).
  - M2 neutral plant: the new form is GREEN (21 passed). The old form is RED (6 failed), and GREEN again after reverting `src`.
- **Named-file run** (6 files): 130 passed.
- **ruff check:** all passed. **ruff format --check:** 3 files already formatted. Skip-hygiene grep: 0 hits. No stale references to the renamed or retired names.
