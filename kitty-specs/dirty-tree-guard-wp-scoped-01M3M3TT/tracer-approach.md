# Tracer: Approach

Seeded at mission planning (spec phase), 2026-09-28.

## Scoping approach

The GitHub issue's original body described two frictions: a mission-wide issue-matrix approval
gate, and review-cycle artifacts blocking WP transitions in the primary checkout. Before writing
anything, I read the issue's comments in chronological order with `gh issue view 5007 --repo
spec-kitty/spec-kitty --comments` (not just the body) to see how the scope evolved:

1. A groom-sweep comment verified the mission-wide issue-matrix gate (`_issue_matrix_approval_blocker`)
   matches "friction 1" and promoted the issue to `status:ready`, adding a note that "friction 2
   ... is also in scope for the implementer picking this up."
2. `kentonium3` then corroborated friction 2 with a concrete, environment-tagged reproduction
   (pinned build `4.0.0rc3`): a `move-task` verdict writes an untracked `review-cycle-N.md`
   record that blocks the *next* WP's transition.
3. Maintainer `stijn-dejongh` then posted a **triage comment explicitly re-scoping the issue**:
   "this issue is now the canonical home for the 'dirty-tree guard is not WP-scoped' fix
   (operator ruling)." This comment names a precise root cause (`_is_benign`'s unused `wp_id`
   parameter, `_validate_research_artifacts`'s hardcoded misattribution), folds in two other
   occurrences (#5151 ask 3, #5159 item 4) by name, and states the acceptance criteria. It does
   **not** mention the issue-matrix gate at all.

Per the dispatch brief's explicit instruction, and because it is chronologically the latest and
most specific maintainer ruling, I followed stijn's triage comment as the operative scope and
treated the earlier groom-sweep's "friction 2 is also in scope" note as superseded (it was
written before stijn's comment existed and used "friction 2" to mean something adjacent but not
identical — the triage comment reframes the whole issue around the WP-scoping root cause, which
subsumes kentonium3's Friction 2 report as one of three concrete occurrences rather than as a
second, separate friction alongside the issue-matrix gate).

**What I scoped in**: the WP-scoped ownership fix to `dirty_classifier.py` and
`tasks_parsing_validation.py`'s refusal-message construction, covering all three named
occurrences (#5151 ask 3, #5159 item 4, kentonium3's review-cycle-N.md report) as one root
cause.

**What I scoped out, and why**:
- The mission-wide issue-matrix gate — not part of the re-scoped issue per stijn's ruling.
- `#5159`'s items 1-3 — stijn's comment names only item 4.
- The `ownership/` (`owned_files`) module as a mechanism — ruled out explicitly in Constraints
  (C-001) because of the "kitty-specs ownership ban" in
  `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md:223`
  (`INVALID_WP_OWNED_FILES_KITTY_SPECS`), which makes that module structurally unable to answer
  ownership questions for `kitty-specs/` paths on `code_change` WPs (nearly every WP).
- SK-249's `record-analysis` preflight — same guard *family*, different command and different
  root cause; not conflated with this mission's fix (see spec's Related History section).

## Verification method

I did not take the readiness report's or the issue's claims on faith. Before writing FRs I:
- Read `src/specify_cli/review/dirty_classifier.py` directly and confirmed `_is_benign(path,
  wp_id)` never references `wp_id` in its body.
- Read `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` and confirmed the
  unconditional `f"... owned by {wp_id}:"` guidance string.
- Read the "kitty-specs ownership ban" directly in `prompt.md` and skimmed
  `src/specify_cli/ownership/` to confirm it is frontmatter/`owned_files`-driven, not
  path-convention-driven.
- Ran a small sandbox git repository to confirm, empirically, that `git status --porcelain`
  reports a wholly-untracked WP task subdirectory as the bare directory path (trailing slash, no
  filename) rather than the individual new file inside it — this is the concrete mechanism behind
  kentonium3's Friction 2 report and is now Edge Case + FR-003 in the spec. Also confirmed with a
  small Python regex check that the *existing* `wp_task_pattern` in `_is_review_handoff_survivor_path`
  already (accidentally) matches nested `.md` paths under a WP directory because `.` matches `/`
  in Python `re` by default — so the true gap for the `.md`-suffixed nested case is narrower than
  it first appears, while the non-`.md` (#5151 ask 3) and wholly-untracked-directory
  (kentonium3) cases are the real, verified gaps. This distinction is recorded in the spec's
  Edge Cases and is left for the plan phase to resolve mechanically.
- Grepped `SPEC-KITTY-LEDGER.md` directly for SK-114, SK-115, SK-223, SK-249 (noting there are
  two separately-numbered SK-249 entries in the ledger, a known duplicate-numbering issue per
  standing operator guidance — I read and cited the one on-topic for this guard family, at line
  13919, "record-analysis's dirty-tree preflight makes the documented analyze fix-loop
  uncompletable by a fixer seat", not the unrelated historical-preservation-gate entry at line
  838 that happens to share the same heading number).

## Plan phase, 2026-09-28

Approach at plan time: read `src/specify_cli/review/dirty_classifier.py` and
`tasks_parsing_validation.py` in full again (not from memory of the spec-authoring pass) to confirm
the exact current shape of `_is_benign`, `_is_review_handoff_survivor_path`, `classify_dirty_paths`,
and `_validate_research_artifacts` before committing to a mechanism. Also read the sibling mission's
(`lane-history-safe-handoff-5151-01M3JR6R`, issue #5151) `plan.md` and WP02 prompt directly
(read-only, in that mission's own checkout — nothing written or run there) to verify #5151's own
account of what WP02 does and does not touch, rather than relying on this mission's spec.md's
paraphrase of it. Confirmed independently: WP02's `owned_files` list the same file and two test
files this mission touches, its target function is `_check_kitty_specs_contamination` (not
`_validate_research_artifacts`), and #5151's plan.md states in its own words that "dirty-root
ownership... was transferred to #5007" — matching spec.md's account, no drift found.

Also confirmed, by direct grep, that `_is_benign` has exactly one production caller
(`classify_dirty_paths`) and is otherwise only invoked directly by test code — this shaped Design
Decision (a): the new ownership logic is added as a second step inside `classify_dirty_paths`,
not folded into `_is_benign`, so `_is_benign`'s existing direct callers (a kitty-ops orphan
counter-contract in `tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py`, and three
wp_id-blind tests in `tests/review/test_dirty_classifier.py`) are provably unaffected.

Checked `.github/ci-module-registry.yml` and `.github/workflows/ci-router.yml` directly (not
trusting the dispatch brief's summary alone) to confirm the architectural-heavy battery's `if:`
condition actually ORs in the `review` and `execution_context` change-filters that this mission's
diff triggers, and to confirm the `execution_context` module's registered `test_dirs` (it is an
aggregate module with no single `tests/{module}` mirror). Both matched the brief exactly.

## WP01 implement phase, 2026-09-28

Worked in the lane worktree `.worktrees/dirty-tree-guard-wp-scoped-01M3M3TT-lane-a` (branch
`kitty/mission-dirty-tree-guard-wp-scoped-01M3M3TT-lane-a`), per the canonical `implement` command's
own instruction. Built a lane-local `.venv` via `uv sync --frozen --all-extras` (no `.venv` existed
in the fresh worktree) and confirmed `import specify_cli` resolved into the worktree's own `src/`
before trusting any test run.

For T001's ATDD test, read `_validate_research_artifacts` (`tasks_parsing_validation.py`) directly
to confirm it shells out to a REAL `subprocess.run(["git", "status", "--porcelain", ...])` against
`main_repo_root` — not a synthetic call — so the WP's "through the real move-task CLI entry point"
requirement meant the test fixture needed a genuinely git-initialized `tmp_path`, not this test
file's usual mocked-`subprocess.run` convention. Found the existing git-repo-building convention in
`tests/conftest.py` (`run(["git", "init"], cwd=repo)` + `git config user.name/email`, imported from
`tests/utils.py`) and reused it rather than inventing a new pattern. Confirmed empirically (not
assumed) that `_validate_ready_for_review`'s Check 2 (software-dev worktree validation) is gated
purely on the FEATURE's `mission_type` (from `meta.json`, absent here → neutral `""`), independent
of a WP's own `execution_mode` frontmatter — so a real lane worktree/`resolve_workspace_for_wp` never
needed to be constructed for this fixture; only `_check_unchecked_subtasks` needed patching away
(an unrelated subtask-completeness gate).

Discovered mid-fixture-construction (not assumed) that `_commit_tracked_wp_dir`'s repo-wide
`git add .` would silently swallow an earlier step's untracked residue file if called after writing
it — reordered both T001 tests to commit every WP's ancestor directory FIRST, then add all
untracked residue files afterward. The resulting RED output for
`test_move_task_still_blocks_own_directory_residue_same_fixture` (pre-fix) also independently
surfaced the PLAN-ARCH-001 defect live: the un-tightened `wp_task_pattern`'s `.+` matched the
nested `WP01-foo/scratch.md` as a flat-file benign match, and my own-residue positive-control
assertion failed with the WRONG file (a cross-WP file) reported as the sole blocker — direct
empirical confirmation of the exact adversarial-review finding plan.md T002 fixes, not merely a
recitation of it.

## WP02 (honest per-path refusal attribution)

The WP prompt's T007 step 3 assumed the pre-existing
`test_validate_research_artifacts_blocks_research_commit_format` fixture (a single blocking path
`kitty-specs/demo/data-model.md`, a mission-root file) would still resolve to `"owned by WP01"`
under the new per-line attribution. It does not: `_attribute_blocking_path` must consume the real
`owning_wp_for_path` as-is (never reimplement or extend its regex — seam placement is binding per
plan.md Design Decision (f)), and that function's pattern only recognizes paths nested under a
WP's own `kitty-specs/<mission_slug>/tasks/WP<n>-*/` directory. A mission-root file like
`data-model.md` never matches that pattern regardless of which WP is moving, so it genuinely
resolves to "not attributable" — which is the *correct*, honest behavior FR-005 asks for, not a
bug. Rather than weaken the test's assertion to match an untrue claim, the fixture path was
changed to `kitty-specs/demo/tasks/WP01-demo/data-model.md` (genuinely under WP01's own task
directory), preserving the test's original "single path, owned by WP01" intent while keeping the
assertion honest. This also avoids duplicating the new RED-first
`test_validate_research_artifacts_unattributable_path_not_owned_by_moving_wp` test's scenario,
which already covers the mission-root/unattributable case. Flagged explicitly rather than silently
"fixed" per the fix-briefs-point-at-feedback discipline — the WP author's assumption was wrong
about this one fixture, not the design.

## Pre-merge fix round, 2026-09-28 (PR-TESTS-001)

Confirmed pre-merge finding PR-TESTS-001 (severity 3, `route-to-fix`) observed that #5159 item 4,
one of the three occurrences FR-009 requires reproduced, was specifically reported against
`move-task --to approved` — but the new end-to-end coverage in `test_tasks.py` only ever invoked
`--to for_review`. Added
`test_move_task_to_approved_ignores_other_wp_uncommitted_review_cycle_dir` in the same file,
reusing the existing real-git fixture helpers (`_init_real_git_mission_repo`,
`_commit_tracked_wp_dir`, `_porcelain_paths`) rather than duplicating them, and reaching `approved`
legitimately via the same composite `in_progress` -> `for_review` -> `in_review` -> `approved` move
the pre-existing `test_move_task_direct_approval_without_agent_uses_hop_specific_actors` test
already exercises (no `--agent`, self-review fallback to the operator). Verified RED-under-revert:
reversing only `src/specify_cli/review/dirty_classifier.py`'s diff against `af847be71` made the new
test fail with `ImportError: cannot import name 'owning_wp_for_path'` (exit_code assertion failure),
confirming the test genuinely depends on the fix rather than passing vacuously; re-applying the
diff restored GREEN. Also updated plan.md and tasks.md's stale "#5151 WP02 hold" prose to record
the operator's 2026-09-28 (later same day) ruling that lifted the implement-phase hold outright,
per spec.md's C-002 superseding update and Clarifications Q1 — kept the prior wording as
"Superseded:" history rather than deleting it.

## Pre-merge fix round, 2026-09-28 (PR-FRESH-001)

Confirmed pre-merge finding PR-FRESH-001 (severity 4, `route-to-fix`): `git status --porcelain`
reports a staged/detected rename as one composite line, `R  old -> new`, and the guard in
`tasks_parsing_validation.py` passed that composite string into `classify_dirty_paths` unsplit.
Two bugs shared the same root cause (neither regex was anchored/bounded against an embedded
` -> ` rename descriptor): Bug A (pre-existing) — `_is_review_handoff_survivor_path`'s
`wp_task_pattern` used `.search()` with no `^` anchor, so a composite whose *trailing* side
happened to look like a flat `tasks/WPxx-*.md` file resolved benign for every WP regardless of
what the *old* side was. Bug B (introduced by this diff's own `owning_wp_for_path`) — its
`(?:\.md|/.*)$` alternation's `.*` absorbed the rename arrow and the new path whole, so a rename
whose *old* side matched a different WP's directory resolved ownership from that old path's
prefix alone, even when the *new* side landed inside the moving WP's own directory — silently
passing the moving WP's own residue (FR-007 / Clarifications Q2 violation).

Fixed at two layers, per the finding's own remediation ("and/or"): (1) `_validate_research_artifacts`
now splits a rename-form porcelain line into its `(old, new)` component paths at the parsing
boundary, before either string reaches the classifier — an entry blocks if EITHER side would block
for the moving WP, and is benign only when BOTH sides are individually benign; the renamed
`_attribute_blocking_entry` helper checks both sides so a rename into the moving WP's own
directory is honestly reported `owned by {wp_id}` even when the old side belongs to someone else
(never hiding what the moving WP owns). (2) `wp_task_pattern` now uses `.fullmatch()` (Bug A) and
`owning_wp_for_path` explicitly rejects any candidate containing `" -> "` or a second
`"kitty-specs/"` occurrence before running its regex (Bug B) — defense-in-depth for any caller that
reaches these helpers directly with a composite string, independent of the parser-level split.
`classify_dirty_paths`'s `(blocking, benign)` 2-tuple return shape is unchanged.

RED-first: added 5 unit tests in `tests/review/test_dirty_classifier.py` reproducing Bug A and
Bug B directly against `_is_review_handoff_survivor_path`, `owning_wp_for_path`, and
`classify_dirty_paths` (using the finding's own composite examples), plus one end-to-end test in
`test_tasks.py` (`test_move_task_refuses_real_git_rename_into_own_directory`) using a REAL
`git mv` (reusing the existing `_init_real_git_mission_repo` / `_commit_tracked_wp_dir` /
`_porcelain_paths` helpers) to rename a file from a different WP's tracked directory into WP01's
own tracked directory — verified this fails pre-fix (`exit_code == 0`, wrongly waved through) and
passes post-fix (refused, `"owned by WP01"` in the guidance). Verified RED-under-revert: reversing
only the fix commit's `src/` diff made all 6 new tests fail on behavioral assertions (not import
errors); re-applying restored GREEN with no other tracked changes.

## Pre-merge fix round, 2026-09-28 (PR-FRESH2-001)

Confirmed pre-merge finding PR-FRESH2-001 (severity 3, `route-to-fix`): `_attribute_blocking_entry`
(introduced by the PR-FRESH-001 fix round above) re-derived ownership by calling
`owning_wp_for_path` on BOTH sides of a rename entry independently, without ever consulting
`_is_benign` or the blocking set `classify_dirty_paths` had already computed for that same call.
`classify_dirty_paths` checks `_is_benign` first and only falls through to `owning_wp_for_path`
when a side is not already benign-exempted (self-bookkeeping churn such as `meta.json`, or any
WP's flat `tasks/WPxx-*.md` task file) — but `_attribute_blocking_entry` skipped that gate
entirely. So a rename whose blocking reason was one genuinely unattributable side (e.g.
`mystery.py`) could still render `"owned by WP01"` whenever its OTHER, benign-exempted side (a
`meta.json`, or WP01's own flat task file) merely happened to sit under WP01's own task directory
by naming convention — diverging from `classify_dirty_paths`'s own blocking/benign partition,
exactly what spec.md's Key Entities section forbids for FR-005.

Fixed per the finding's own remediation: `_attribute_blocking_entry` now takes the same
`blocking_set` `_validate_research_artifacts` already computed from `classify_dirty_paths`'s
return value, and only calls `owning_wp_for_path` on the side(s) of an entry that are themselves
members of that set — a benign-exempted side is never considered for ownership, regardless of
where it happens to sit. `classify_dirty_paths`'s `(blocking, benign)` 2-tuple return shape,
`owning_wp_for_path`'s `count("kitty-specs/") > 1` guard, and `_check_kitty_specs_contamination`
are all unchanged (PR-FRESH2-002 was refuted — left as-is).

RED-first: added 3 tests in `test_tasks_parsing_validation.py`, exercised end-to-end through
`_validate_research_artifacts` with the REAL (unmocked) `classify_dirty_paths` /
`owning_wp_for_path` / `_is_benign` so the divergence actually manifests — both of the finding's
own repro shapes (`mystery.py -> WP01-mine/meta.json`, and `mystery.py -> WP01-mine.md`, the flat
own-task-file variant) asserting the guidance says `"not attributable to a specific work package"`,
never `"owned by WP01"`; plus one control (a rename from a DIFFERENT WP's directory into WP01's
own directory — the now-fixed PR-FRESH-001 Bug B shape) asserting the correctly-owned case still
renders `"owned by WP01"`, guarding against an overcorrection that would flatten every rename
entry to unattributable. Verified RED-under-revert: reversing only the fix commit's `src/` diff
(between the RED and FIX commits) made the two misattribution tests fail on the same
`"owned by WP01"` behavioral assertion the live repro showed; re-applying restored GREEN with no
other tracked changes.
