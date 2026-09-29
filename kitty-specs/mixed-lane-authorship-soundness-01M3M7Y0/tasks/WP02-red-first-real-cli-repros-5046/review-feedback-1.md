# WP02 review feedback, round 1 (reviewer-renata)

## What was verified (reviewer re-run on lane-b head ad466fc3)
- `tests/terminus/test_repro_5046.py`: 4 failed. Each fails on the first assertion, `result.returncode != 0`, with exit 0 observed. The output shows the merge went through and printed "Reconciliation verified". No builder errors. The RED is for the correct reason.
- `tests/terminus/test_repro_5046_controls.py`: 6 passed. `tests/terminus/test_repro_5018.py`: 1 passed.
- ruff check, ruff format --check and mypy on both files: clean. No xfail or skip. Markers match test_repro_5018.

The mechanics are good. The problems are in what the future-green assertions actually pin.

## Issue 1 (BLOCKER): T007 Shape B is not the SC-007 shape, and the docstring claim about it is false
The spec (T007, SC-007, plan D-3) describes Shape B as follows: WP01 modifies `shared.py` from v0 (the mission-base content) to v1, then the canceled WP02 writes it back to exactly **v0**. The point is that a naive "compare with the mission base" check would see that the canceled state equals the base, drop the finding, and ship the undo.
The test does not build this. `shared.py` does not exist at the mission base: the builder seeds no base files, and `survivor_before` creates it. WP02 then writes `"SHARED = 'wp02 restored v0'"`, a brand-new content that matches no base state. A naive mission-base check would still flag this path. So Shape B tests the same thing as T006's modify, and it does not guard residual R1 for the revert case. The docstring says "A naive ... check would find both paths equal to the ... starting state". That is true for Shape A only.
**Fix:** the canceled final content of `shared.py` must be byte-identical to its mission-base content. That needs a mission-base seed (see Issue 2).

## Issue 2 (BLOCKER): the T006 "exists at base" modify and delete shapes are not built
T006 requires modifying `src/pkg/shared.py` **(exists at base)** and deleting `src/pkg/legacy.py` **(exists at base)**. The test instead seeds both through `survivor_before`, so WP01 authors them on the lane. As a result, T006's modify and delete are survivor-undone variants, and the plain US1 shapes (the canceled WP modifies or deletes a file that pre-dates the mission) are never pinned. The superseded control is affected in the same way: its "modify" of `shared.py` is really an add.
`build_coord_mission_mixed_lane_canceled` has no `extra_base_files` parameter, even though its `PlantedChange` docstring refers to one. `_init_fixture_repo` already supports it. Your WP prompt says: "If the builder cannot express a shape, request a WP01 change". Do not silently substitute a different shape.
**Fix:** raise a WP01 change request to thread `extra_base_files` through the builder. Then rebuild T006 (base-seeded `shared.py` and `legacy.py`, no `survivor_before` for them), T007 Shape B (base v0, then survivor v1, then canceled back to v0) and the superseded control (base-seeded `shared.py`). Keep the current survivor-seeded T006 variant too if you want it: it is valid extra coverage.

## Issue 3 (MAJOR): the lane and WP02 assertions are vacuous
`"lane-a" in flat` is already true on a **successful** run ("Lanes: lane-a", "Checking and merging lane-a..."). In T008, `"WP02" in flat` is always true ("Skipping WP02 (canceled with provenance ...)"). As written, these assertions do not check that the **verdict** names the lane (NFR-003).
**Fix:** bind them to the verdict text. For example, take the substring that starts at `Reconciliation FAILED` / `Reconciliation refused (fail-closed)` and assert `lane-a`, `WP02` and the recovery step inside that slice.

## Issue 4 (MINOR): the recovery substring is brittle against backticks
The existing verdicts render "re-run `spec-kitty consolidate --resume`" with literal backticks, and contract C4 also writes the recovery step in backticks. `"re-run spec-kitty consolidate"` will not match "re-run `spec-kitty consolidate`". Strip backticks in `_collapse` (or match on a regex) so that a correct WP05 is not falsely red.

## Issue 5 (MINOR): the path and wording are not bound together
Each path and each wording (`carries canceled WP02's change` / `deleted by canceled WP02`) is asserted independently. Consider asserting per path that its expected wording sits next to it: deletion wording for `legacy.py` and `survivor.py`, change wording for `wp02_new.py` and `shared.py`. Otherwise a gate that mislabels a path could still pass.

## Issue 6 (BLOCKER, process): T010 activity log is missing
The WP02 Activity Log contains only "Prompt created". T010 requires, for each T006–T008 test, the failing assertion line **and** evidence that `blob_present_at(...)` is True for a canceled path. Right now the tests stop at the exit assertion, so no run records the canceled content landing. Add the matrix, including a one-off observation that the canceled path is on the target after the exit-0 run.

## Anti-pattern checklist
1 dead code N/A (tests only) · 2 synthetic fixture PASS (real CLI) · 3 silent return N/A · 4 FR coverage FAIL (FR-005/SC-007 revert shape not actually pinned, Issues 1–2) · 5 frozen surface PASS (src/, integration and conftest untouched) · 6 locked decision PASS · 7 shared-file ownership PASS · 8 fragility N/A
