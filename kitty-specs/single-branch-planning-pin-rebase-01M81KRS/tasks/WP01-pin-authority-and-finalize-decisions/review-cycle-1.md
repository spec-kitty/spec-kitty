---
affected_files: []
cycle_number: 1
mission_slug: single-branch-planning-pin-rebase-01M81KRS
reproduction_command:
reviewed_at: '2026-11-22T13:57:19Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 1: changes requested

Reviewer: `claude::reviewer-renata`. Review range `078a607bd302..f3213d3665a2` (implementation commit `f134aeba`).

Most of WP01 is sound. The fix for the #7793 root cause (a WP that ever left `planned` means execution has begun) is correct. The patch-id primitive and its refusal codes are correct, the derivation anchor is correct, and both re-pinned tests in `test_finalize_tasks_commit_surface.py` were genuinely stale. Three findings below block approval. Each comes with a reproduction.

## Blocking

### B1. An explicit `--refresh-planning-commit` keeps `planning_commit_derived: true`

Every `--refresh-planning-commit` writes through `_commit_planning_pin_refresh_locked` (`mission_finalize_planning_pin.py`, about line 906). That function reads the existing manifest and sets only `planning_commit_sha = plan.new_sha`. A marker that was `True` stays `True`. The operator-chosen pin is then treated as derived and frozen against every later automatic refresh. That contradicts research R4 ("an explicit `--refresh-planning-commit` replaces it and clears the marker") and the contract row.

Reproduction: derive a pin (the `_blank_recorded_pin` fixture, then a plain finalize), then run `finalize-tasks --refresh-planning-commit`. Result: the sha changed and `planning_commit_derived` is still `True`. Fix: clear the marker on that write path, and add a red-first test. The plain-finalize path is fine, because `compute_and_write_lanes` takes the flag explicitly.

### B2. The patch-id follow can choose the target branch's copy and widen the window to the target's work

Suppose the planning commit's change is already upstream, for example cherry-picked or landed on `main` through a separate PR. `git rebase` then drops the Mission's copy as already applied. `follow_pin_by_patch_id` scans `merge-base(pin, tip)..tip`, which includes the upstream commits. It finds exactly one match, the upstream copy, and returns it. The new window `upstream_copy..mission_branch` then contains every target commit made after that copy. The window guard passes because it only checks that owned work is kept, never that the window was widened. Target work that matches `owned_files` would count as the WP's implementation evidence. The check fails open, and it undoes the point of #7297 item 2 and SC-004.

Reproduction (plain git):

1. Commit `base` on `main`.
2. On `mission`: commit `planning` (adds `kitty-specs/m/tasks/WP01.md`), then `impl` (`src/a.py`).
3. On `main`: cherry-pick `planning` with a different committer date, then commit `src/b.py`.
4. Run `git rebase main` on `mission`. Git skips `planning` as already applied.

Then `follow_pin_by_patch_id(P, "mission")` returns `main`'s cherry-picked copy, and `git diff --name-only <it>..mission` lists both `src/a.py` and `src/b.py`.

Requested fix:

- **Minted branch** (pin line ≠ target): accept a candidate only when it is not reachable from `target_branch`. In practice, scan `merge-base(target_branch, tip)..tip`. When the only match is on the target, refuse `PLANNING_PIN_NO_PATCH_ID_MATCH`, or use a new code.
- **Commit-to-target**: spec-kitty cannot see the upstream the rebase used. Either find a sound rule, or record this as a named residual in the ADR amendment (WP02) with a strict `xfail`.

Cover the minted case with a red-first test.

### B3. SC-004 is not demonstrated red-first

`test_minted_mission_refresh_no_longer_dead_ends` already passes on base: I ran the new tests against `4a6b8cc4` with WP01's test files. So it does not show that the minted refresh ever refused `PLANNING_REFRESH_FAIL_CLOSED` on this path, or that it is fixed now. T005 also promised a shape-B row asserting that the window excludes `main`-only commits after a rebase onto a newer `main`, and no test asserts that. Add that row and witness it red on base. If the old refusal cannot be reproduced through the real CLI, say so in the tracer and drop the claim from the commit message.

### B4. `tests/architectural/test_no_dead_symbols.py` is red on this branch (2 failed)

The diff adds public symbols with no other `src/` caller:

- `mission_finalize_pin_window`: `OrphanFollow`, `PATCH_ID_AMBIGUOUS`, `PinLine`, `mission_owned_patterns`
- `planning_base`: `PatchIdFollow`, `PatchIdMiss`

It also leaves `planning_base::mission_wp_tasks_pathspec` without a caller. The result is that `test_no_public_symbol_in_all_is_unimported` and `test_m11c_gate_reads_the_widened_section_it_is_given` both fail. CI's cross-cutting lane would go red. Fix it in the gate's preferred order: drop the names from `__all__`, make them private, or delete them (`mission_wp_tasks_pathspec`). Do not use the allowlist.

## Non-blocking (fold here or route to WP02 as noted)

- **N1. Doctor rebuild (WP02 owns `migration/mission_state.py`).** `_rebuilt_planning_commit` returns `derived=True`, but its `compute_and_write_lanes` call never passes `planning_commit_derived`. A pin derived by the doctor rebuild (#7210) is therefore not marked and not frozen. Research R4 states the opposite ("set when finalize (or the doctor rebuild) derives the pin"). The rebuild also derives on `target_branch`, not on `pin_branch_line`. For a minted `single_branch` Mission whose tasks exist only on the Mission branch, derivation finds nothing and falls back to the target tip. Either fix the R4 text in this WP, or make sure WP02 folds both points and tests them in `test_doctor_rebuild_derived_pin_7210.py`. Same gap: `tasks_finalize.py` (`--skip-lanes` style) captures on `st.target_branch`, not on the pin line.
- **N2.** `window_keeps_owned_work` checks the union of all WPs' owned files. The move-task and consolidation gates are per-WP. The docstring says the guard "cannot disagree with them", but a candidate that keeps WP02's change and drops WP01's would pass the guard and fail the gate. That cannot happen with today's two candidates (the tip, or the rebased copy at the same relative position). Either make the check per-WP or correct the docstring.
- **N3.** (Dead helper: see B4.) The `planning_base` module docstring (line 4) still calls `resolve_planning_base_commit` "the one authority" for a base read from git, but finalize and the doctor now use `_last_appearance_base`. Update the docstring, and remove the dead helper or allowlist it with a reason.
- **N4.** The pin line reads `meta.mission_branch`. The window tip (`single_branch_evidence_window`) reads `lanes.json` `mission_branch`, which `_preserved_mission_branch` keeps even after landing clears `meta.mission_branch`. They agree in normal operation. Name the post-landing divergence in the ADR amendment.
- **N5. Nightly-only disclosure.** `tests/integration` and `tests/specify_cli/cli/commands` are both `out_of_matrix_test_dirs`. The new integration file, `test_finalize_pin_decisions_7297.py` and the commit-surface tests run only in the nightly. Only `tests/lanes/**` runs per PR. Disclose this in the PR body.
- **N6.** The recorded review range's pathspec covers only `owned_files`, so `lanes/models.py`, `lanes/compute_and_persist.py`, `mission_finalize_lanes.py` and the new `mission_finalize_pin_window.py` do not appear in it. I reviewed them from `git show f134aeba`. Leeway is fine (no other WP owns them), but list them in the PR.

## Verified sound

- **"Ever left planned".** Non-migration moves only, read from the same surface. It is conservative for `blocked`, forced and canceled WPs: they read as begun, which goes to the preserve path rather than re-capturing.
- **Patch-id refusals.** An empty diff gives `no_patch_id`, two copies give `ambiguous`, a git error refuses. The primitive never falls back to the tip.
- **Re-pinned tests are not green-washing.** The `resolve_planning_base_commit` monkeypatch target became wiring-stale when derivation moved to `_last_appearance_base`. The reason and text assertions follow the intended #7297 item 3 behaviour (DIRECTIVE_041: stale, so re-pin).
- **Marker shape.** It is serialized only when `True` and read strictly with `is True`. The golden contract passes. `topology_settlement` and the restamp migration do not rebuild the manifest from a dict, so they do not drop the key.
- **Pending point 1 (pin line = mission branch for capture, refresh and derivation).** Correct on the merits. The window is `pin..mission_branch`. A pin captured on the target sits below the fork point and stays an ancestor after a rebase onto a newer target, so the target's commits would enter the window. Capture and refresh need the same line as derivation, not only derivation.
- **Pending point 2 (marker instead of a stateless rule).** The claim holds: on a direct history the timely pin captured by finalize equals the derived base (the parent of the tasks commit), so a stateless rule also froze timely pins and turned R17 red. The marker is the right shape, with B1 and N1 fixed.
