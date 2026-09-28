---
work_package_id: WP02
title: Register carve-out entry and add non-vacuous conflict-marker guard + shrink-only ratchet
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-4957-archived-conflict-markers
merge_target_branch: issue-4957-archived-conflict-markers
branch_strategy: Planning artifacts for this mission were generated on issue-4957-archived-conflict-markers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4957-archived-conflict-markers unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-audit-archived-missions-conflict-markers-4957-01M3G1GP
base_commit: d42f3c938135664d331730ed2c2db454ade78a3d
created_at: '2026-09-27T03:23:31.764138+00:00'
subtasks:
- T002
- T003
- T004
- T005
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- tests/architectural/test_archive_root_byte_identical.py
role: implementer
tags: []
tracker_refs: []
---

# WP02: Register carve-out entry and add non-vacuous conflict-marker guard + shrink-only ratchet

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

In `tests/architectural/test_archive_root_byte_identical.py`: (1) register
WP01's repaired path as the fourth `_OPERATOR_SANCTIONED_CORRECTIONS` entry so
the always-on `archive-freeze` job passes on this mission's own PR (FR-002),
and (2) add five new, separately-failing test functions that close the
conflict-marker defect class by construction — a non-vacuous guard, its
self-mutation positive control, a shrink-only exemption ratchet, that
ratchet's own positive control, and a fail-closed leg (FR-003–FR-008,
NFR-001–NFR-003) — plus post the FR-009 informational comment on GitHub issue
#4956 as this WP's PR-closing step (IC-03).

## Context

**Depends on WP01.** This WP's carve-out entry (FR-002) and its real-tree
guard assertion (`test_no_conflict_markers_in_tracked_files`, FR-003) are only
meaningful once WP01's repair has landed — plan.md's own IC-02 sequencing note
states: "the guard's real-tree pass (FR-003 scenario 1) is only true once
IC-01's repair has landed." This WP does **not** execute in the same lane as
WP01: `lanes.json` places WP01 in `lane-planning` (the repo-root checkout —
the mission's real PR-source branch) and this WP in a distinct lane,
`lane-a`, joined only by the `dependencies: [WP01]` / `depends_on_lanes` edge.
That edge gates only **when this WP can be claimed** — the CLI's
dependency-readiness check refuses to let this WP be claimed/implemented
until WP01 reaches `approved`/`done` — so by the time this WP is actually
implemented, WP01's repair is always already present in the tree. There is no
independent merge-and-gate checkpoint between the two lanes, because there is
no code-level checkpoint of any kind governing WP01's own commit reaching the
real branch: the only real gate, `_assert_mission_terminal_ready`
(`src/specify_cli/merge/executor.py:461-521`), is a **mission-wide**
precondition — it is evaluated once over `run.all_wp_ids` (every WP in the
mission, WP01 and this WP together, not scoped to lane-a alone) early in a
single `spec-kitty merge` invocation (after the review-artifact consistency
gate and merge-state setup/load, but strictly before `_phase_merge_lanes`,
the first lane-consolidating phase). It gates local lane consolidation only — it never runs against, and never gates, a
`git push origin` or `gh pr create` — it does not, and cannot, protect WP01's
already-landed commit from being pushed to origin or opened as a PR before
this WP exists. **Operative
discipline (binding, since no gate enforces it — see WP01's Context for the
full mechanism): do NOT push the mission branch
(`issue-4957-archived-conflict-markers`) to origin, and do NOT open or update
a pull request from it, until BOTH WP01 and this WP have reached
`approved`/`done`.**

**Why this WP owns the carve-out entry, not WP01.** `_OPERATOR_SANCTIONED_CORRECTIONS`
lives in `tests/architectural/test_archive_root_byte_identical.py`, a
`tests/` path. This repo's `tasks-finalize` ownership validation bans a
`code_change` WP from owning any `kitty-specs/` path and (symmetrically) does
not exempt a `tests/`-owning WP for planning-artifact treatment — so the
carve-out registration, which is conceptually part of IC-01 (plan.md pairs it
with the repair as "must land together"), had to move into this WP rather
than WP01's. `plan_concern_refs` for this WP therefore lists `IC-01` (the
carve-out half) in addition to `IC-02` (the guard) and `IC-03` (the tracker
comment).

**PR shape.** This WP is the second (and final) WP of this mission; it does
not open its own PR. **This mission ships as exactly one PR onto `main`, per
plan.md Section G**: *"One PR for this whole mission. This is the sk-hub
default (`sk-implement` doctrine: one PR per mission unless the mission is
large enough to need a per-WP split). C-002's blast radius (two files, five
new test functions, one repaired archive file, one tracker comment) is far
too small to justify splitting into multiple PRs or even multiple WPs beyond
what `/spec-kitty.tasks` decomposes IC-01/IC-02/IC-03 into for tracking
purposes — the PR itself is singular."* (`tasks.md` is generated by
`finalize-tasks` from `wps.yaml` with no free-text header slot for this
statement — this WP prompt file and plan.md Section G are the artifacts of
record for PR shape; see this mission's `tracer-tooling-friction.md` for that
gap.)

**Chokepoint callout.** `tests/architectural/test_archive_root_byte_identical.py`
backs the **always-on `archive-freeze` CI job** (`.github/workflows/ci-router.yml`,
job block starting line 489, invoking this exact file by name at line 502) —
a shared gate every PR in this repository goes through, not a path-filtered
shard. This same file, and specifically the exact mechanism this WP extends
(`_OPERATOR_SANCTIONED_CORRECTIONS`), is what **GitHub issue #4956** will
later touch: #4956 removes the whole carve-out mechanism (all four entries,
this WP's included) once every correction is baseline on `main` (C-003). Treat
this file with the care due a shared chokepoint: do not weaken the freeze for
any path beyond this WP's one new entry, and do not assume you are the last
mission to touch this mechanism.

**Do NOT spawn sub-agents.** Implement every subtask below yourself,
sequentially, in this one WP. (This mission previously incurred an incident
class where forked sub-agents inherited an entire WP brief and raced commits
against each other — do not repeat that pattern here.)

**Red-first discipline (Standing Order #4 / #5, charter.md).** Each of the
five new test functions below (T003–T007) is its own separately-failing
red-first proof — write it, confirm it fails for the reason stated (missing
helper/constant, or a real assertion failure), then make it pass. None of the
five is folded into another; the sixth spec.md scenario (the independently-
counted `N`-file floor with a binary fixture, User Story 2 Acceptance
Scenario 5) is folded into T003's test body as an additional assertion, per
plan.md Section B — not a seventh test function.

**Baseline (re-run at the end, NFR-001 closing verification):**

```
pytest tests/architectural/test_archive_root_byte_identical.py tests/git_ops/test_git.py tests/upgrade/preview_support/test_public_witnesses.py
→ 48 passed, 0 failed   (main @ 46ea5bd7f, before any change in this mission;
                          test_no_preexisting_archived_file_was_modified alone: 1.99s)
```

## Subtask T002: Register the fourth `_OPERATOR_SANCTIONED_CORRECTIONS` entry (FR-002)

**Purpose**: Add the WP01-repaired path as a fourth, explicitly-commented entry
in the existing carve-out frozenset, following the exact pattern of the three
existing entries, so `archive-freeze` passes on this mission's diff.

**Steps**:
1. Open `tests/architectural/test_archive_root_byte_identical.py`. Confirm
   `_OPERATOR_SANCTIONED_CORRECTIONS` still opens at line 150 and holds
   exactly three entries (lines 152–154) before editing; re-read live if the
   line numbers have drifted.
2. Add a fourth comment block immediately above the frozenset, following the
   two-existing-comment-block pattern (one #4936-precedent block, one
   #4972 two-entry block) exactly:
   - Name the path:
     `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
   - State the defect: unresolved git conflict markers (`<<<<<<< HEAD` …
     `=======` … `>>>>>>>`) committed to the archived file, surfaced by
     mission #4957 (this mission), the same defect class the #4880/#4936
     precedent and #4972 landings addressed.
   - State the resolution: the markers were resolved to the `HEAD` side
     (the lineage confirmed an ancestor of `main` via `git merge-base
     --is-ancestor df2dac046 main`); the losing `5eda48f7` side (confirmed
     **not** an ancestor of `main`) was deleted along with the markers.
   - Include the same "Follow-up: once this correction is in main's baseline,
     this entry is dead weight and should be removed" line the other three
     entries carry, citing #4956 (the issue that removes the whole
     mechanism — C-003).
3. Add the path as a fourth string literal inside the `frozenset({...})` call,
   alongside the three existing entries — do not reformat or reorder the
   existing three.
4. Do not touch `_APPEND_ONLY_SPINE_EXCEPTIONS` or any other module-level
   constant in this subtask.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (comment
block + one frozenset entry, ~15 lines added).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py::test_no_preexisting_archived_file_was_modified`
passes once both this entry and WP01's repair are present in the tree — they
are: WP01's repair is a prerequisite this WP's dependency gate already
enforces (this WP cannot be claimed until WP01 reaches `approved`/`done`), so
WP01's commit is always present by the time this WP's own commits land, even
though the two commits sit in different lanes rather than one sequential
lane history. Every other archived-root path remains subject to the freeze
unchanged (spec.md User Story 3 Acceptance Scenario 2).

## Subtask T003: `test_no_conflict_markers_in_tracked_files` — the real-tree negative control (FR-003/FR-004)

**Purpose**: Add the always-on guard: enumerate tracked files, scan each for
conflict-marker lines, fail on any hit outside the exemption allowlist, and
tie the self-reported scanned-file count to ground truth (not merely
non-empty).

**Steps**:
1. Add a new, narrowly-scoped helper `_enumerate_tracked_files(root: Path =
   REPO_ROOT) -> list[str]` in the same file. It runs `git -C <root> ls-files`
   and returns the tracked relative paths. Apply the same three env vars
   `_git_bytes` applies unconditionally (`GIT_NO_REPLACE_OBJECTS=1`,
   `GIT_OPTIONAL_LOCKS=0`, `SPEC_KITTY_ENABLE_SAAS_SYNC=0`) on every call this
   helper makes, with no conditional branching — mirroring `_git_bytes`'s own
   unconditional-application precedent (it applies these vars even to its own
   pure-read call sites). **Do not modify or touch `_run_git`/`_git_bytes`
   themselves** — this is a genuinely new helper, used only by this guard's
   tests, not a change to the file's ~10 existing call sites of those two
   helpers.
2. Add a module-level exemption allowlist constant near
   `_OPERATOR_SANCTIONED_CORRECTIONS` (shape mirrors `_APPEND_ONLY_SPINE_EXCEPTIONS`):
   ```python
   _CONFLICT_MARKER_SCAN_EXEMPTIONS: frozenset[str] = frozenset({"tests/git_ops/test_git.py"})
   ```
   with a comment stating this is the one legitimate exemption — the
   intentional `conflict_content` fixture in `test_conflict_marker_parsing`
   (`tests/git_ops/test_git.py:452–457`) that exercises `GitVCS` marker
   parsing, not real corruption.
3. Add a small, reusable scan helper (called by this test and by T004, not
   duplicated logic) that: takes a root path, an iterable of tracked relative
   paths, and an exemption set; for each non-exempted path, reads the file
   and checks each line against the anchored regex `^(<<<<<<<|>>>>>>>) `
   (trailing space required — not a bare `^=======$`, per spec.md
   Clarification (d)); on a per-file binary/decode failure, skip that file
   (log it, do not raise) but still count it toward the enumerated-file
   floor; returns both the list of `(path, line_no)` violations and the
   count of files enumerated.
4. Write `test_no_conflict_markers_in_tracked_files`:
   - Call `_enumerate_tracked_files(REPO_ROOT)` and the scan helper against
     the real tree with `_CONFLICT_MARKER_SCAN_EXEMPTIONS`.
   - Assert zero violations outside the allowlist.
   - Assert the scan helper's self-reported scanned-file count is both
     non-empty **and** exactly equal to `len(_enumerate_tracked_files(REPO_ROOT))`
     for that same invocation (FR-004's ground-truth tie).
   - Fold in the sixth spec.md scenario (User Story 2 Acceptance Scenario 5)
     as an additional assertion in this same test body: git-init a throwaway
     repo under `tmp_path`, commit a small fixture subtree of `N`
     independently-counted tracked files with zero conflict-marker lines,
     including one deliberately non-UTF-8 binary file, call the same
     `_enumerate_tracked_files`/scan helper pair with `root=tmp_path_repo`,
     and assert the reported scanned-file count equals `N` exactly (not
     merely non-empty) and that the binary file did not raise or get silently
     dropped from the floor.
5. This WP cannot even be claimed until WP01 has reached `approved`/`done`
   (the dependency gate), so WP01's repair is **already present** in the live
   working tree by the time this test is written — the pre-repair corruption
   cannot be observed live, and expecting the live tree to still show it would
   be self-contradictory. Instead, produce the red-first proof by inspecting
   the file at WP01's parent commit:
   ```bash
   git show <WP01-commit>^:kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md \
     | grep -nE '^(<<<<<<<|>>>>>>>) '
   ```
   (substitute the actual commit that carries WP01's repair; `<sha>^` names
   its parent, i.e. the pre-repair blob) and confirm it matches at the
   pre-repair lines (758 and 773) — this proves the guard's **regex pattern**
   would have matched the corruption before WP01 landed. Then write and run
   `test_no_conflict_markers_in_tracked_files` against the live (already-
   repaired) tree and confirm it passes.

   **Why this grep-only proxy is sufficient here, and deliberately narrow.**
   This `git show ... | grep` check only confirms the marker pattern is
   textually present in the historical blob — it does not exercise
   `test_no_conflict_markers_in_tracked_files` itself (its exemption-list
   handling, encoding, and floor-count logic) against known-bad input, so on
   its own it would not prove the actual guard *function*, as written, would
   have failed on that tree. That is accepted for this specific step because a
   live corrupted tree structurally cannot exist at WP02's authorship time:
   this WP cannot even be claimed until WP01's repair has already landed
   (the dependency gate), so there is no way to run the real test function
   against genuinely-corrupted, currently-tracked content — this step's grep
   is a necessarily-historical textual proxy standing in for what would
   otherwise be a live red-first run. The real red-first proof that the guard
   **function** itself (not just the regex) works correctly on corrupted
   input is provided instead by Subtask T004
   (`test_conflict_marker_guard_self_mutation_catches_synthetic_marker`),
   which plants a synthetic marker in a fresh fixture and exercises the
   actual guard function end-to-end for **detection and line-identification
   only**. T004 does **not** cover exemption-list handling: every fixture
   file T004 plants a marker into is constructed outside
   `_CONFLICT_MARKER_SCAN_EXEMPTIONS` (T004 step 2), so T004 never
   constructs a case where a marker-containing file IS on the exemption
   list and never exercises the guard's exemption-skip path at all.
   The guard's exemption-skip correctness is instead covered
   **incidentally** by this very step's own real-tree run of
   `test_no_conflict_markers_in_tracked_files`: the one entry on
   `_CONFLICT_MARKER_SCAN_EXEMPTIONS`, `tests/git_ops/test_git.py`, already
   contains a literal `<<<<<<< HEAD` / `>>>>>>> branch` fixture string
   inside `test_conflict_marker_parsing`'s `conflict_content` literal
   (`tests/git_ops/test_git.py:453/457`) — content that exists there for an
   unrelated purpose (exercising `GitVCS`'s own marker parsing), not to
   prove this guard's exemption-skip behavior. Because that file sits on
   the exemption list, this step's real-tree scan passing with zero
   violations, despite that marker-shaped content being present in a
   scanned, tracked file, is only possible if the exemption skip actually
   works — so this step's own run is what incidentally proves exemption-
   skip correctness, riding on a fixture in a different file that exists
   for an unrelated reason and could change shape later, not a dedicated,
   intentional positive assertion. Read this step's grep as a
   regex-pattern confirmation only, and read T004 as covering detection
   and line-identification only; neither this step nor T004 gives the
   exemption-list path a dedicated positive proof of its own — that
   remains a gap for a future WP to close if judged necessary, not
   something to misattribute to T004 here.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (new
helper functions + one new test function, ~80–100 lines).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py -k test_no_conflict_markers_in_tracked_files -v`
passes after WP01's repair is present in the working tree; fails (regex match
found) if run against a tree still carrying the corruption.

## Subtask T004: `test_conflict_marker_guard_self_mutation_catches_synthetic_marker` — the guard's own positive control (FR-006)

**Purpose**: Prove `test_no_conflict_markers_in_tracked_files`'s pass on the
real tree is a real negative, not a probe that cannot see anything — the
guard's non-vacuity proof required by Standing Order #5.

**Steps**:
1. Using `tmp_path`, git-init a throwaway repo, commit one small fixture file
   whose content does **not** match the guard's regex, and confirm the scan
   helper (T003) reports zero violations against it.
2. Plant a synthetic line matching `^(<<<<<<<|>>>>>>>) ` into that fixture
   file, outside `_CONFLICT_MARKER_SCAN_EXEMPTIONS`, commit the change, and
   assert the scan helper now reports exactly one violation identifying that
   file's path and the correct line number.
3. Remove the synthetic line, re-commit, and assert the scan helper reports
   zero violations again — both the "catches it" and "stops catching it once
   removed" halves live in this one test.
4. Call the shared scan helper from T003 — do not duplicate its logic.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (one new
test function, ~40–50 lines).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py -k test_conflict_marker_guard_self_mutation_catches_synthetic_marker -v`
fails if the scan helper does not yet exist (import/attribute error counts as
red); passes once the helper correctly detects the planted marker and clears
once it is removed.

## Subtask T005: `test_conflict_marker_exemption_allowlist_is_shrink_only` — the shrink-only ratchet (FR-005/NFR-003)

**Purpose**: Enforce that `_CONFLICT_MARKER_SCAN_EXEMPTIONS` can shrink but
never silently grow beyond this mission's landed baseline — new enforcement
for this exemption set (no such test exists today for
`_APPEND_ONLY_SPINE_EXCEPTIONS`, confirmed via `grep -rn
_APPEND_ONLY_SPINE_EXCEPTIONS tests/` showing only its definition and one use
site).

**Steps**:
1. Add a small, shared comparator helper (used by this test and by T006, not
   copy-pasted) that takes a candidate frozenset and a baseline frozenset and
   asserts the candidate is a subset of the baseline (shrink-only:
   `candidate <= baseline`), raising/failing with the specific unexpected
   entries named if not.
2. Write `test_conflict_marker_exemption_allowlist_is_shrink_only`: call the
   comparator with the **live** `_CONFLICT_MARKER_SCAN_EXEMPTIONS` against
   the literal baseline `{"tests/git_ops/test_git.py"}` (this mission's
   landed set). Assert it passes (the live set equals — a subset in both
   directions of — the baseline).
3. This test intentionally does **not** register the exemption set in
   `tests/architectural/_baselines.yaml` — per spec.md Clarification (k), that
   centralized mechanism requires editing `test_ratchet_baselines.py` as a
   third file, which conflicts with C-002's two-file blast radius. This is a
   deliberate, documented deviation, not a silent bypass; do not "fix" it by
   adding a third file to this mission's scope.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (one new
test function + one shared comparator helper, ~30–40 lines).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py -k test_conflict_marker_exemption_allowlist_is_shrink_only -v`
fails before `_CONFLICT_MARKER_SCAN_EXEMPTIONS` exists (`NameError`/import
failure); passes once it is defined as exactly `{"tests/git_ops/test_git.py"}`.

## Subtask T006: `test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control` — the ratchet's own positive control (FR-008)

**Purpose**: A **distinct** test from T005 — prove the shrink-only comparator
(shared with T005) actually detects growth, so T005's pass is a real negative
rather than a check that would pass identically before any growth occurred.
This is the ratchet mechanism's own non-vacuity proof, not interchangeable
with T004 (which is the marker-scan guard's positive control, a different
mechanism).

**Steps**:
1. Construct a fixture-augmented allowlist: the real
   `_CONFLICT_MARKER_SCAN_EXEMPTIONS` plus one spurious extra path beyond the
   landed baseline (e.g. `"some/spurious/extra/path.py"`).
2. Call the **same shared comparator helper** T005 uses, with the augmented
   fixture as the candidate and the literal baseline `{"tests/git_ops/test_git.py"}`
   as the baseline argument.
3. Assert the comparator fails/raises, and that its failure message identifies
   the specific spurious entry (`"some/spurious/extra/path.py"`) as the
   unexpected growth.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (one new
test function, ~25–35 lines).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py -k test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control -v`
fails if the comparator helper does not yet raise/assert on growth (i.e., if
it only ever passes); passes once the comparator correctly flags the
fixture's spurious extra entry.

## Subtask T007: `test_conflict_marker_guard_fails_closed_on_enumeration_failure` — the fail-closed leg (FR-007/NFR-002)

**Purpose**: Prove the guard raises/fails — never silently passes — when file
enumeration itself fails, distinct from T003–T006, which all assume
enumeration succeeds.

**Steps**:
1. Using `monkeypatch`, patch the `_enumerate_tracked_files` helper's
   underlying `git ls-files` subprocess call to raise (simulating "git
   unavailable" / a non-zero return code) and assert the guard's real-tree
   invocation raises or fails the test rather than silently reporting zero
   conflict markers as a pass.
2. Separately, patch it to return an empty result where a non-empty one is
   expected (FR-004's floor), and assert the guard fails/raises in this case
   too rather than treating an unexpectedly empty enumeration as "clean."
3. Scope this test to the **enumeration** failure mode only — a per-file
   binary/decode failure during content scan (already covered by T003's
   fixture-subtree binary-file assertion) is explicitly a different, non-fatal
   code path (Edge Cases in spec.md) and is not what this test exercises.

**Files**: `tests/architectural/test_archive_root_byte_identical.py` (one new
test function, ~30–40 lines).

**Validation**: `pytest tests/architectural/test_archive_root_byte_identical.py -k test_conflict_marker_guard_fails_closed_on_enumeration_failure -v`
fails if the guard's enumeration call silently swallows the injected error;
passes once the guard's enumeration path is written to raise/fail on both
injected conditions.

## Subtask T008: Post the FR-009 informational comment on GitHub issue #4956, and resolve the mission's issue-matrix (IC-03, PR-closing step)

**Purpose**: Correct the stale single-entry, wrong-line-number body of issue
#4956 with an accurate, current starting point for whoever picks it up next —
a tracker action, not a file change, executed as this WP's (and this
mission's) PR-closing step, after T002–T007 have landed and this file's
final, four-entry membership and current exemption-check line reference are
known. This subtask also resolves all six rows of this mission's
`issue-matrix.json` (step 5 below) — a second, distinct gating requirement
that must clear to a non-`unknown` verdict on every row before either this WP
or WP01 can reach `for_review`/`approved`, since the approval/done-transition
validator hard-blocks on any `unknown` row for the whole mission.

**Steps**:
1. Confirm, on the final state of this lane (after T002 has landed), the
   exact current line number of the exemption-check clause inside
   `test_no_preexisting_archived_file_was_modified` — spec.md/plan.md cite
   **line 728** (`if not path.startswith(_ARCHIVE_ROOTS) or path in
   _APPEND_ONLY_SPINE_EXCEPTIONS or path in _OPERATOR_SANCTIONED_CORRECTIONS:`);
   re-verify it has not drifted due to this WP's own additions before citing
   it in the comment (T002's addition is *above* this clause in the file and
   will shift it — recompute, do not assume 728 still holds after T002's
   edit).
2. Enumerate the full, current four-entry `_OPERATOR_SANCTIONED_CORRECTIONS`
   membership: the #4936-precedent `status.json` entry, the two #4972
   `status.json` entries, and this mission's fourth WP01-path entry.
3. Post the comment: `gh issue comment 4956 --body "..."` (per `CLAUDE.md`'s
   GitHub CLI auth guidance — `unset GITHUB_TOKEN && gh issue comment 4956
   --body "..."` if a token-scope error appears). The comment body must:
   - Enumerate all four `_OPERATOR_SANCTIONED_CORRECTIONS` entries by path.
   - State the correct, current exemption-check clause line reference
     (re-verified per step 1, not assumed to be 728).
   - Explicitly state this is an **informational correction only**, posted
     from mission #4957, and that it does **not** claim or commit to closing
     #4956 (C-003 — that cleanup is out of scope for this mission).
4. This is the mission's PR-closing step, not a mid-implementation action —
   perform it after T002–T007 are done and verified, immediately before or
   as part of marking this WP for review.
5. **Resolve all six issue-matrix rows.** `issue-matrix.json` carries
   #4928, #4936, #4954, #4956, #4957, and #4972, all still at the gating
   `unknown` scaffold placeholder — the approval/done-transition validator
   (`_issue_matrix_approval_blocker`) hard-blocks the whole mission's
   `for_review`/`approved`/`done` transitions on any `unknown` row, so this
   must clear before this WP (or WP01) requests review. For each row, run:
   ```bash
   spec-kitty agent issue-verdict --mission audit-archived-missions-conflict-markers-4957-01M3G1GP \
     --issue <#NNNN> --verdict <verdict> --actor <your-actor-id> \
     --evidence-ref "<evidence>"
   ```
   `--actor` is required by the current CLI (identify yourself, e.g.
   `python-pedro` or your session's actor id). Re-check
   `spec-kitty agent issue-verdict --help` for the exact flags and the valid
   `--verdict` enum before running any of these — do not guess. Suggested
   verdict per row:
   - `#4957` → `fixed` — this mission's own issue. `_validate_structured_issue_matrix`
     only requires `--evidence-ref` to be non-empty for the `fixed` verdict —
     it does not require the reference to already be a real PR link — so set a
     concrete, non-empty placeholder now, e.g.:
     `--evidence-ref "mission audit-archived-missions-conflict-markers-4957-01M3G1GP; PR not yet opened — will be updated with the PR link once opened, per this mission's push-after-both-WPs-approved discipline"`.
     The `issue-verdict` call is idempotent and can — and should — be re-run
     with the real PR link once the PR exists, as part of the PR-opening step
     (after both WPs are approved/done), not before approval.
   - `#4936` → `not-applicable` — cited only as the originating precedent for
     the `_OPERATOR_SANCTIONED_CORRECTIONS` mechanism; no work is owed to
     #4936 by this mission. `--evidence-ref`: one line stating that.
   - `#4972` → `not-applicable` — cited only as the second precedent landing
     that extended the same carve-out mechanism; no work is owed to #4972 by
     this mission. `--evidence-ref`: one line stating that.
   - `#4928` → `not-applicable` — cited only as context/precedent in
     spec.md/plan.md prose; no work is owed to #4928 by this mission.
     `--evidence-ref`: one line stating that.
   - `#4954` → `not-applicable` — spec.md Clarification (e) cites #4954
     (ledger SK-249) as the precedent that originated the carve-out
     mechanism, and separately notes that #4954's closing note calls for a
     commit-time (pre-commit-hook) prevention that this mission deliberately
     does not implement (this mission's guard is CI-time, not commit-time) —
     this mission neither fixes nor verifies a fix for #4954, so
     `not-applicable` fits better than `verified-already-fixed`.
   - `#4956` → `deferred-with-followup`, with `--evidence-ref` naming the
     #4956 follow-up itself (e.g. `"Follow-up: #4956"` or its issue link) —
     consistent with C-003's explicit deferral: the whole
     `_OPERATOR_SANCTIONED_CORRECTIONS` mechanism, including this WP's new
     fourth entry, is removed once every correction is baseline on `main`,
     and this WP's own step-3 comment on #4956 is the concrete follow-up
     evidence. The CLI requires `--evidence-ref` to contain a `#NNN` or a
     `Follow-up:` substring for this verdict — the example above satisfies
     that.

**Files**: none for step 1–4 (tracker-only action; does not expand C-002's
two-file blast radius). Step 5 writes mission state to `issue-matrix.json`,
but only through `spec-kitty agent issue-verdict` — never by hand-editing
that file.

**Validation**: `gh issue view 4956 --comments` (or the GitHub web UI) shows
the new comment with the correct four-entry enumeration and line reference,
and its disclaimer text. Separately, confirm all six issue-matrix rows
(#4928, #4936, #4954, #4956, #4957, #4972) carry a genuine non-`unknown`
**verdict** — via `spec-kitty agent tasks status` or by reading
`issue-matrix.json` — before this WP or WP01 requests `for_review`/`approved`.
This requirement is about the verdict field, not evidence-completeness: for
#4957 specifically, the verdict (`fixed`) must be set now, but its
`--evidence-ref` content is allowed to be the placeholder described above and
updated later (at the PR-opening step) — it does not need to already contain
a real PR link before either WP is approved.

## Definition of Done

Carried verbatim-consistent from plan.md Sections B–D (five separately-failing
red-first proofs, none folded into another):

- [ ] **T002 — carve-out entry (FR-002)**: `_OPERATOR_SANCTIONED_CORRECTIONS`
  holds a fourth, explicitly-commented entry for WP01's repaired path,
  following the exact pattern of the three existing entries.
- [ ] **`test_no_conflict_markers_in_tracked_files` (FR-003/FR-004)** — the
  real-tree negative control: passes with a non-empty, ground-truth-tied
  scanned-file count; the folded `N`-file fixture-subtree assertion (with a
  binary file) also passes.
- [ ] **`test_conflict_marker_guard_self_mutation_catches_synthetic_marker`
  (FR-006)** — the marker-scan guard's own positive control: fails when a
  synthetic marker is planted in a non-exempted fixture, passes once removed.
- [ ] **`test_conflict_marker_exemption_allowlist_is_shrink_only`
  (FR-005/NFR-003)** — the shrink-only ratchet: the live exemption set equals
  exactly `{"tests/git_ops/test_git.py"}`.
- [ ] **`test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control`
  (FR-008)** — the ratchet's own positive control, distinct from the guard's
  (FR-006): fails when the exemption set is fixture-augmented with a spurious
  entry beyond baseline.
- [ ] **`test_conflict_marker_guard_fails_closed_on_enumeration_failure`
  (FR-007/NFR-002)** — the fail-closed leg: raises/fails on both a
  monkeypatched enumeration-raise and an unexpectedly-empty enumeration
  result, in both cases rather than silently passing.
- [ ] **T008 — IC-03 tracker comment (FR-009)**: posted on GitHub issue #4956,
  enumerating the full four-entry membership and the correct current
  exemption-check line reference, with the informational-only disclaimer.
- [ ] **T008 step 5 — issue-matrix resolved (all six rows)**: `#4928`,
  `#4936`, `#4954`, `#4956`, `#4957`, and `#4972` each carry a genuine
  non-`unknown` **verdict** in `issue-matrix.json`, set via `spec-kitty agent
  issue-verdict` (never hand-edited) — confirmed before this WP or WP01
  requests `for_review`/`approved`. For #4957, the verdict itself (`fixed`)
  must be set now; its `--evidence-ref` is allowed to be the concrete
  placeholder described in T008 step 5 and re-run with the real PR link once
  the PR exists — evidence-completeness for that one row is not a precondition
  of approval.
- [ ] **NFR-001 closing verification**: re-run `pytest
  tests/architectural/test_archive_root_byte_identical.py -q` after all five
  new test functions are green; record the wall-clock delta against the
  1.99s (this file alone) / 276.09s (three-file baseline) figures in the PR
  body.
- [ ] **SC-002 re-run**: `pytest tests/architectural/test_archive_root_byte_identical.py
  tests/git_ops/test_git.py tests/upgrade/preview_support/test_public_witnesses.py`
  meets or exceeds the 48-passed/0-failed baseline with zero new failures
  attributable to this diff.
- [ ] Per-subtask completion is recorded via `spec-kitty agent tasks
  mark-status <Txxx> --status done` for each of T002–T008 (event-sourced —
  not hand-ticked checkboxes above).

**Gate set** (carried verbatim-consistent from plan.md Section C — same gates
marked Yes, same reasons, no invented or dropped gates):

| Gate | Applies? | Why |
|---|---|---|
| ruff lint + `ruff format --check` | Yes | Always-on, whole-repo; the new test functions must satisfy both. |
| `uv lock --check` | Yes (trivially) | Always-on; this mission adds no dependency, so it passes unchanged. |
| import-linter (banned API / TID251) | Yes (trivially) | Always-on; the new `_enumerate_tracked_files` helper is added in the same file (existing `_run_git`/`_git_bytes` left untouched), adding no new import crossing a boundary. |
| `spec-kitty regen --check` | Yes (trivially) | Always-on; `test_archive_root_byte_identical.py` is confirmed not a regen-manifest target — hand-editing it is not "hand-patching a generated file." |
| terminology guard (`test_no_legacy_terminology.py`) | Yes (trivially) | Always-on; no `ceremony`/`status-writing` terms introduced. |
| layer rules / pyproject shape | Yes (trivially) | Always-on; no import-direction or package-shape change. |
| **archive-freeze** (`test_archive_root_byte_identical.py -q`) | **Yes — central** | Always-on; this IS the job whose invoked file gains the carve-out entry (T002) and the new guard tests (T003–T007). |
| `architectural-heavy` job | **No** | Its `if:` condition does not fire for this diff's paths; even if it ran, it explicitly `--deselect`s `test_archive_root_byte_identical.py`. |
| `tests (corpus)` (`tests-corpus` job) | **Yes** | Path filter includes `kitty-specs/**/tasks/**` (WP01's file); `tests/architectural/**` itself is out-of-matrix (see next row) but the corpus job's path trigger still fires on this mission's diff via WP01's path. |
| per-module shards (`ci-modules.yml`) | No | Neither `tests/architectural/**` nor `kitty-specs/**` is claimed by any module row; `tests/architectural` is explicitly listed under `out_of_matrix_test_dirs`. |
| **diff-cover ≥90% (changed critical-path lines)** | **No — does not bind** | Neither of this mission's two files matches any `CRITICAL_PATHS` entry; the scored diff is empty, so diff-cover passes vacuously-but-legitimately (not because 90% coverage was achieved — pytest-cov never measures `tests/` files at all; correctness is proven by the tests running and the self-mutation positive controls, not a coverage percentage). |
| `packs.yml` | No | No `packs/` path touched. |
| commit-msg / markdownlint | No (never fail) | Both run `\|\| true`; listed for completeness, not treated as gates. |
| wheel build + `clean-install-verification` | Yes (trivially) | Always-on; no packaging-relevant change. |

Explicitly NOT gates (per plan.md Section C, overriding stale overlay lists):
commitlint (prints only), markdownlint-as-enforced (runs `|| true`),
Bandit/pip-audit (run in no workflow), mypy (runs in no workflow for this
diff's files), any named "kernel 90%"/"mission-loader ≥90%" coverage floor
(no such floors exist), SonarCloud `sonar-pr` (continue-on-error, reported not
required).

## Risks

- **Shared chokepoint**: `tests/architectural/test_archive_root_byte_identical.py`
  backs the always-on `archive-freeze` job every PR in this repo goes through,
  and is the exact mechanism GitHub issue #4956 will later touch (removing
  all four `_OPERATOR_SANCTIONED_CORRECTIONS` entries and the mechanism
  itself). A mistake here does not just affect this mission — it affects
  every subsequent PR's `archive-freeze` run until fixed. Do not weaken the
  freeze for any path beyond this WP's one new carve-out entry.
- **Line-number drift from T002's own edit**: T002 adds ~15 lines above the
  line-728 exemption-check clause referenced by T008 and by spec.md/plan.md —
  recompute the actual current line number before citing it in the #4956
  comment (T008), do not assume it stays at 728.
- **Five distinct test functions, none foldable**: resist the temptation to
  merge T004 into T003, or T006 into T005 — Standing Order #5 requires each
  leg (concrete floor, self-mutation, shrink-only allowlist, and that
  allowlist's own positive control) as a separately-failing proof; folding
  any two together defeats the "gate-unmask cannot self-validate" requirement
  the charter names.
- **`_baselines.yaml` is deliberately not touched** (spec.md Clarification
  (k)) — do not "fix" this by registering the new exemption set there; that
  would add a third file and violate C-002's two-file blast radius.

## Reviewer Guidance

- Confirm all five new test functions are distinct `def test_*` bodies (not
  folded), each independently runnable via `pytest … -k <name>`.
- Confirm T003's real-tree assertion passes only once WP01's repair is
  present in the tree (WP01's commit lives in a different lane, `lane-planning`,
  reached before this WP could even be claimed — not "this lane's history";
  see Context) — i.e., confirm the red-first proof was actually observed via
  the pre-WP01-commit inspection T003 step 5 describes, not skipped.
- Confirm T004 and T006 are genuinely different positive controls: T004
  proves the marker-scan guard (T003) is a real negative; T006 proves the
  shrink-only ratchet (T005) is a real negative. They exercise different
  mechanisms and must not be collapsed into one test.
- Confirm T007 covers both the "enumeration raises" and "enumeration returns
  empty" failure modes, and does **not** conflate this with T003's per-file
  binary/decode-skip handling (a different, non-fatal code path).
- Confirm T008's #4956 comment was actually posted (not merely described in
  the PR body) and states the current, re-verified line number and full
  four-entry membership, with the informational-only disclaimer.
- Confirm all six issue-matrix rows (#4928, #4936, #4954, #4956, #4957,
  #4972) carry a non-`unknown` verdict, set via `spec-kitty agent
  issue-verdict` (never a hand-edit of `issue-matrix.json`) — this blocks
  `for_review`/`approved`/`done` for the whole mission, including WP01, so it
  must be clear before approving either WP.
- Re-run the SC-002 baseline command and confirm pass count ≥48 with zero new
  failures attributable to this diff.

Implementation command:

```bash
spec-kitty agent action implement WP02 --agent claude
```
