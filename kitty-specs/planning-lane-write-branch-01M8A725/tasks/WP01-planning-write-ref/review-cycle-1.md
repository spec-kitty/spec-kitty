---
affected_files: []
cycle_number: 1
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-25T21:57:02Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review (claude::reviewer-renata): REJECT

Commit reviewed: e6dd59d5 on kitty/mission-planning-lane-write-branch-01M8A725-lane-a.
Verified clean: 16/16 tests pass; ruff, `ruff format --check --force-exclude`, C901 and mypy clean; imports into specify_cli stay function-local; placement `_default_mission_facts` is unchanged in behaviour.
The out-of-map `mission_runtime/__init__.py` export and surface pin are justified: MR-1/MR-2 forbid importing the submodule from outside the package, and precedent 2c1caf39 shipped the same kind of change with no version bump. Not a finding.

## Findings

1. [HIGH] src/specify_cli/coordination/planning_commit.py `planning_lane_write_ref` (the `mission_branch_name(mission_slug)` line): the missing-meta probe builds the LEGACY branch name (no mission_id), not the Mission's real branch. For a modern slug without an embedded mid8 (for example `kernel-clock-single-door`, which exists in kitty-specs/), `mission_branch_name` gives `kitty/mission-kernel-clock-single-door`, but the real branch is `kitty/mission-kernel-clock-single-door-<mid8>`. The probe then finds no branch and returns the target with on_mission_branch=False. With the coordination worktree removed, that is a silent fallback to the target, which NFR-002 forbids. The WP said to read the branch from `lanes.json` `mission_branch`. The tests hide this because `_SLUG = "fx-01M8AAAA"` and `_MISSION_BRANCH = f"kitty/mission-{_SLUG}"` are exactly the legacy form.
   Recommendation: read `mission_branch` from `lanes.json`, or compose it with `mission_branch_name_required` and the recorded mission_id. An unreadable lanes.json must fail closed. Add a test whose slug does not embed a mid8 and whose real branch carries one.

2. [MEDIUM] src/mission_runtime/resolution.py `planning_write_ref`: the public reader that is documented as raising returns the target silently when meta.json is absent (`meta_found=False`). The NFR-002 decision for that case lives one layer up, in `planning_lane_write_ref`. The docstring also tells consumers to call `mission_runtime.planning_write_ref`, so a WP04 or WP05 consumer that follows it skips the probe and gets the silent target. The 4th field (`meta_found`) also departs from data-model.md (3 fields) and from the WP DoD.
   Recommendation: make the docstring say that every consumer outside placement must go through `planning_lane_write_ref` / `planning_lane_target`, and that `meta_found=False` is not an answer on its own. Record `meta_found` in data-model.md, or make the refusal in one place.

3. [MEDIUM] tests/mission_runtime/test_planning_write_ref.py `test_an_unreadable_landing_record_reads_as_not_landed`: the test is vacuous. The monkeypatch does take effect (the function-local `from .landing import mission_has_landed` reads the module attribute at call time). But the meta has no `merged_at`, so the real `mission_has_landed` already returns False, and the test passes with or without the patch. No unreadable landing record is exercised, and the downstream fail-closed consequence that T001 asked for is not tested.
   Recommendation: write `merged_at` and make the record really unreadable (for example a corrupt `status.events.jsonl` that raises StoreError in `is_mission_merged`), with no monkeypatch. Assert `landed=False` and `branch == Mission branch`.

4. [LOW] src/specify_cli/coordination/planning_commit.py `_branch_exists`: `PlanningWriteRefUnavailable(branch, ...)` passes the branch where `mission_slug` is expected, so the message reads "...of Mission 'kitty/mission-...'". This GitCommandError leg is also untested, because the fail-closed test patches only `tree_entry`.
   Recommendation: pass `mission_slug` and add a test for the rev-parse leg.

5. [LOW] src/mission_runtime/resolution.py `planning_write_ref` (the `on_mission_branch = ...` line): this line restates the predicate of `default_mission_primary_ref`, which gives a second copy of the rule (C-004 drift risk).
   Recommendation: one pure helper that returns both the branch and whether the default rule picked it, used by both.

6. [LOW] docs/adr/4.x/2026-11-06-3-...md, Amendment 2026-11-25, "Fail closed" bullet: "only a Mission with no meta.json anywhere keeps the target (legacy)". Until finding 1 is fixed this is not true (see the slug case above).
   Recommendation: fix the code, or make the ADR state how the Mission branch is identified (lanes.json mission_branch).
