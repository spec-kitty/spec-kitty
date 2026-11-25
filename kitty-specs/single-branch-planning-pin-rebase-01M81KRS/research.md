# Research: single_branch planning pin across a rebase

All findings come from reproductions run on `main` at f8fee580 through the real CLI (the #5939 integration harness, `tests/integration/test_5939_single_branch_autowalk_guards.py::_setup_mission`), plus a code read.

## R1. The two single_branch shapes

- **Shape A, commit-to-target** (`mission_branch` = `target_branch`, an unprotected topic branch). The pin is the topic tip at finalize, a commit on the Mission's own line. A `git rebase main` orphans it. `implement` names `--refresh-planning-commit --allow-orphaned`, which re-pins to the tip (`_resolve_refresh_planning_commit_decision`, :374-386). The window `tip..tip` is then empty, and `move-task --to for_review` refuses `SINGLE_BRANCH_IMPLEMENTATION_MISSING`. **This is #7793, reproduced exactly.**
- **Shape B, minted branch** (default topology, or explicit `single_branch` on a protected `main`). Finalize's planning branch is `target_branch` (`_resolve_target_branch`), so the pin is **`main`'s tip** at finalize, below the mission branch's fork point. After a rebase onto a newer `main` the pin stays an ancestor, but the window `pin..mission_branch` gains every new `main` commit. Unrelated `main` content touching `owned_files` would pass a hollow WP (#7297 item 4, concrete). `--refresh-planning-commit` refuses `PLANNING_REFRESH_FAIL_CLOSED` ("lanes.json does not resolve to the planning target branch"), because the placement seam writes `lanes.json` on the mission branch (#7297 item 2: the dead end).

**Decision**: one resolver, `planning_base.pin_branch_line(meta, target_branch)`. It returns `meta.mission_branch` for a stored `single_branch` Mission that records one, otherwise `target_branch`. Capture, the explicit refresh (including the compare-and-swap tip check and the destination check) and derivation all use it. **Rationale**: the window's tip is `mission_branch`, so its base must sit on the same line. **Alternatives**: derivation-only (the literal ruling) leaves shape B's refresh dead end and the too-early pin; rejected pending the dispatcher's confirmation (recorded in spec Assumptions). **Existing Missions**: a recorded pin is never rewritten by this change (C-002). The new line applies at the next capture or explicit refresh.

## R2. Following an orphaned pin by patch-id

**Decision**: `planning_base.follow_pin_by_patch_id(repo, pin, tip)` takes `patch_id_of(pin)` and scans `rev-list merge-base(pin, tip)..tip`. It returns the single commit with an equal non-empty patch-id. Otherwise it returns a typed miss: `no_patch_id` (an empty-diff pin, e.g. a merge or an empty commit), `no_match` or `ambiguous`. A git error refuses. **Rationale**: a rebase rewrites SHAs but keeps each commit's change. The rebased copy of the planning commit is exactly where the window should start (operator ruling). **Bound**: the range is the Mission's own commits plus the new upstream commits; one patch-id per commit (NFR-001).

**Scope**: applied on the explicit `--allow-orphaned` re-pin of a `single_branch` Mission. Lane Missions keep the #4827 re-pin to the tip (C-003): their lanes are cut from the pin, and the allocator merge semantics are out of scope.

## R3. Never empty the window

**Decision**: before writing any `single_branch` re-pin or refresh candidate, compare the evidence paths (`wp_evidence.evidence_paths`) of the old window and the candidate window against the union of every work package's `owned_files`. If the old window holds an owned change and the candidate's does not, the re-pin refuses (`PLANNING_PIN_WOULD_EMPTY_WINDOW`) and the automatic refresh keeps the pin with a warning. **Rationale**: this is the operator's "never lands on a tip that empties the window", stated as the evidence the gate itself reads, so it cannot disagree with `move-task`.

## R4. Derived pin freeze (#7297 item 1)

**Decision (revised during WP01)**: a persisted marker. `lanes.json` gains `planning_commit_derived: true`, written only when true so every other `lanes.json` is byte-identical. It is set when finalize derives the pin and carried by every decision that keeps the recorded pin. The `doctor mission-state --fix` rebuild (`mission_state._rebuilt_planning_commit`) and the `tasks_finalize` capture do not set it yet, and both still derive or capture on `target_branch` rather than the pin line; WP02 folds both (review N1). On the automatic path an ADVANCED pin with the marker is preserved; an explicit `--refresh-planning-commit` replaces it and clears the marker. **Why revised**: the first, stateless design (recorded == base derived now) also froze *timely* pins. On a direct history the derived base equals the tip a timely finalize records, which broke the R17 rule that a genuine planning amendment refreshes a pin (`test_finalize_refreshes_planning_commit_sha_by_default` went red). For `single_branch`, the R3 guard additionally stops any automatic refresh that would strand committed work.

## R5. Derivation anchor (#7297 items 4 and 5)

**Decision**: anchor on any file under `kitty-specs/<slug>/tasks/` (not only `WP*.md`), on the first-parent line of the pin branch line, and take the **last** time the directory went from absent to present (a re-add after a full removal), rather than the first-ever touch. Implementation: walk `git log --first-parent --format=%H --name-status -- <tasks dir>` oldest-first and track presence. **Item 5**: non-`WP*` task files renamed to `WP*` are covered because the directory is anchored, not the name. **Residuals** (kept in the ADR): WP files committed before unrelated work, and a topic cut after tasks reached `main`. A derived base cannot tell those apart from ordinary history; the R3 guard does not apply to a first derivation.

## R4b. Execution has begun

**Decision**: `_execution_has_begun` is also true when any work package ever left `planned` (a non-migration transition in the log). **Rationale**: the #7793 operator path runs finalize while the rejected WP sits in `planned`. The old "current lane" test read that as "never run", so finalize took the pre-execution branch and re-captured the tip with no orphan check, emptying the window. This is topology-neutral: a rejected lane Mission gets the begun-path protections (preserve, orphan fail-closed) too.

## R2b. An upstream copy of the planning commit (review B2)

**Decision**: a patch-id match reachable from the target branch or the primary branch (`resolve_primary_branch`, no feature bias), less the pin line itself, is never the Mission's copy. When the planning change also landed upstream, the rebase drops the Mission's copy as already applied, and pinning the upstream copy would count every later upstream commit as the Mission's work. Only upstream matches → refuse `PLANNING_PIN_NO_PATCH_ID_MATCH`, naming the upstream. **Residual** (ADR, WP02): an upstream that is neither the target nor the primary branch (a rebase onto some other branch carrying the planning change) is not recognised.

## R6. Messages (#7297 items 3 and 6)

- Finalize: the INDETERMINATE branch with `recorded=None`, a resolved tip and nothing derivable gets `refusal_reason="no_pin_underivable"`. The text names `spec-kitty agent mission finalize-tasks --refresh-planning-commit` as the next step. `indeterminate_tip_uncapturable` is kept only when the tip really is `None`, and its text no longer prints a tip it says it could not resolve.
- `move-task`: the `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` remedy names the re-pin route (`--refresh-planning-commit`, and `--allow-orphaned` after a rebase) instead of a bare "run finalize-tasks".
- Doctor: a rebuild whose pin stays `None` warns (`lanes_rebuilt_pin_unset`). Both warnings name `finalize-tasks --refresh-planning-commit` as the next step.
