---
work_package_id: WP01
title: WP-scoped ownership attribution mechanism
dependencies: []
requirement_refs:
- C-001
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
planning_base_branch: issue-5007-dirty-tree-guard-wp-scoped
merge_target_branch: issue-5007-dirty-tree-guard-wp-scoped
branch_strategy: Planning artifacts for this mission were generated on issue-5007-dirty-tree-guard-wp-scoped. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5007-dirty-tree-guard-wp-scoped unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-dirty-tree-guard-wp-scoped-01M3M3TT
base_commit: cc471ad044b7879282d9f850ef19b973effd56c1
created_at: '2026-09-28T16:44:05.595202+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-09-28T15:25:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/dirty_classifier.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/review/dirty_classifier.py
- tests/review/test_dirty_classifier.py
- tests/specify_cli/cli/commands/agent/test_tasks.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – WP-scoped ownership attribution mechanism

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
this work package's `task_type` and `authoritative_surface`.

Mission: `dirty-tree-guard-wp-scoped-01M3M3TT` (GitHub issue `spec-kitty/spec-kitty#5007`). Read
`../spec.md` and `../plan.md` in full before writing any code — plan.md's Design Approach and
Decisions section (a), (c), (d) and Implementation Concern Map (IC-01) is the authoritative
mechanism description; this prompt summarizes it, it does not replace it.

---

## ⛔ Mission-level pre-implement gate — check this before claiming this WP

Per spec.md Constraint C-002 and plan.md Design Decision (b): the whole mission's implement phase
(both WP01 and WP02) must not start until sibling mission `lane-history-safe-handoff-5151-01M3JR6R`
(issue #5151)'s own WP02 has **landed OR been reviewed/approved on its own branch** — spec.md's own
minimum bar, because WP02 (this mission's WP02, IC-02) shares the exact same two files as #5151's
WP02. (An earlier draft of this gate stated a stricter, unauthorized "merged to `main`" bar; this
was corrected per operator ruling 2026-09-28, which restored spec.md's original
"landed-or-approved" bar.) WP01 itself has **no file overlap** with #5151's WP02, but since WP02
depends on WP01 and this mission ships as one PR, do not start implementing WP01 either until the
precondition is confirmed. Verify with one of:

1. `spec-kitty agent tasks status --mission lane-history-safe-handoff-5151-01M3JR6R --json` — WP02
   lane is `approved`, `done`, or otherwise landed on `main`;
2. `gh pr view <PR#> --json state,mergedAt,reviewDecision` on #5151's WP02 PR — `state == "MERGED"`
   or `reviewDecision == "APPROVED"`;
3. `git log main --oneline -- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` shows
   a commit plausibly matching WP02's described change.

If none confirms WP02 has landed or been reviewed/approved, **stop and report** — do not proceed
with implementation.

---

## Objective

Give `classify_dirty_paths` a real per-path ownership answer, replacing the never-read `wp_id`
parameter's dead-letter status in `_is_benign`, so a dirty path provably owned by a *different* WP's
`kitty-specs/<mission_slug>/tasks/<WPxx>-*/` directory is recognised as benign — while a WP's own
residue and any truly unattributable path keep blocking, unchanged. Deliver this test-first: the
first commit is a failing ATDD reproduction of all three concretely-reported occurrences through the
real `move-task` CLI entry point, shown RED before any implementation code exists (charter C-011).

**`src/specify_cli/review/dirty_classifier.py` is shared `move-task` guard infrastructure that every
currently-running mission's `move-task` depends on** (spec.md § Compatibility & Reflexivity), not
only the missions that reported this defect — this WP's regex/logic change is compatibility-relevant
mission-wide, not a low-stakes, single-mission edit. The concrete proof obligation for "no
previously-benign path becomes newly-blocking" is T003's
`test_no_previously_benign_path_becomes_blocking` regression test, not merely one more unit test
among the others.

## Context

**Root cause** (spec.md Overview): `src/specify_cli/review/dirty_classifier.py::_is_benign(path,
wp_id)` accepts `wp_id` but never reads it — every non-benign dirty path blocks `move-task` for
*every* WP regardless of who produced it. Three independently reported, concretely reproduced
occurrences share this root cause: **#5151 ask 3** (a non-`.md` script under another WP's task
directory blocked an unrelated WP's transition), **#5159 item 4** (another WP's uncommitted
`review-cycle` directory blocked `move-task --to approved`), and **kentonium3's corroboration**
(pinned build `spec-kitty-cli 4.0.0rc3` — a `move-task` verdict writes an untracked
`review-cycle-N.md`, and git reports a wholly-untracked WP subdirectory as the bare directory path,
no filename, which the *next* WP's transition then trips over).

**C-001 — the ownership module is out of bounds.** Do NOT use or extend
`src/specify_cli/ownership/` (`owned_files` frontmatter-driven ownership). The "kitty-specs
ownership ban" in `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md:223` forbids a
`code_change` WP from listing any `kitty-specs/` path in `owned_files`
(`INVALID_WP_OWNED_FILES_KITTY_SPECS`), and since nearly every WP is `code_change`, that module is
structurally unable to answer "which WP owns this `kitty-specs/` path." The mechanism is the
pre-existing, topology-independent directory-naming convention
(`kitty-specs/<slug>/tasks/<WPxx>-*/` → owned by `WPxx`), already partially implemented in
`_is_review_handoff_survivor_path`'s `wp_task_pattern`.

**Seam placement is binding (plan.md Design Decision (f)):** `dirty_classifier.py` (the review/
service) owns ALL ownership-attribution logic — the regex, `owning_wp_for_path`, and
`classify_dirty_paths`'s integration of it. The CLI layer (WP02's surface) only ever *consumes* this
via a direct submodule import — never reimplements the regex. Do not add `owning_wp_for_path` to
`src/specify_cli/review/__init__.py` — it is consumed only via a direct import from
`specify_cli.review.dirty_classifier`, mirroring how `tasks_parsing_validation.py:289` already
imports `classify_dirty_paths` the same way.

**Do NOT spawn sub-agents.** Implement every subtask below yourself, sequentially, in this one WP
(prior-incident precedent: forked sub-agents inheriting a whole WP brief and racing commits against
each other).

**Baseline** (re-confirm before your first commit):

```bash
.venv/bin/python -m pytest tests/review/test_dirty_classifier.py tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py -q
```

Expected: **77 passed, 0 failed, 0 errors** (matches `main@af847be71`; plan.md Baseline section). If
your count differs, stop and report — do not assume it is pre-existing without checking the base per
`CLAUDE.md`'s baseline-red gotcha.

---

## Subtask T001: RED-first ATDD reproduction through `move-task` (FR-009, SC-001)

**Purpose**: Per charter ATDD-first (C-011), commit a failing test — **before any implementation
commit** — that reproduces all three concretely-reported occurrences through the real,
public `move-task` CLI entry point (`spec-kitty agent tasks move-task`, exercised via
`specify_cli.cli.commands.agent.tasks` in `tests/specify_cli/cli/commands/agent/test_tasks.py`, not
a synthetic unit-level shortcut). This is the mission's headline red-first proof (plan.md Validation
Strategy step 1).

**Steps**:
1. Read `tests/specify_cli/cli/commands/agent/test_tasks.py`'s existing `move-task` test fixtures
   (e.g. `test_move_task_lane_chain_uses_canonical_status_events`,
   `test_move_task_for_review_without_agent_uses_assigned_actor`) to match the file's existing
   fixture/harness conventions (how a mission dir, `lanes.json`, `status.events.jsonl`, and a git
   repo under `tmp_path` are constructed) rather than inventing a new harness style.
2. Add ONE new test — e.g. `test_move_task_ignores_other_wp_residue_and_attributes_own_residue` (or
   split into up to three focused tests if that reads more clearly given the existing file's style;
   your call, but keep them in the same commit) — that constructs a git-tracked mission fixture with
   dirty paths reproducing, in one scenario each:
   - **#5151 ask 3**: a non-`.md` file (e.g. a `.py` script) under a *different* WP's
     `kitty-specs/<slug>/tasks/WPxx-*/` directory, wholly uncommitted, while moving a *different* WP
     (e.g. WP01). Assert the transition **succeeds** (no refusal) — currently (pre-fix) it wrongly
     refuses.
   - **#5159 item 4**: a `review-cycle` directory under a *different* WP's task directory,
     uncommitted, while moving `--to approved` for a different WP. Assert the transition
     **succeeds** — currently it wrongly refuses.
   - **kentonium3's Friction 2**: a *wholly untracked* WP task subdirectory (e.g.
     `kitty-specs/<slug>/tasks/WP02-foo/` with one new `review-cycle-1.md` inside, and the parent
     `kitty-specs/<slug>/tasks/` directory already tracked, so `git status --porcelain` reports the
     bare directory path — verify this shape empirically in your fixture, do not assume it), while
     moving a different WP (e.g. WP01, `--to for_review`). Assert the transition **succeeds**.
3. Add one companion, same-fixture **positive control** (spec.md AC3 / FR-007): a dirty path under
   the *moving* WP's own task directory (not its `.md` task file, which is already benign — a
   different residue file, e.g. `scratch.md` or a non-task file) still **blocks** the transition.
4. Run the new test(s) now, before touching `dirty_classifier.py` at all, and confirm they FAIL for
   the right reason (the transition is wrongly refused, or wrongly succeeds for the positive
   control) — this is your RED proof. Commit this test file change alone, as the WP's first commit,
   with a message stating it is RED-first per charter C-011.
5. Do not implement T002 yet — leave these tests RED until T002 lands, then re-run to confirm GREEN
   (T004).

**Files**: `tests/specify_cli/cli/commands/agent/test_tasks.py` (new test(s), ~80–150 lines
depending on how you split the three scenarios).

**Validation**: `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_tasks.py -k "ignores_other_wp or own_residue" -v` — RED now (before T002), GREEN after T002 lands (confirmed
in T004).

---

## Subtask T002: `owning_wp_for_path` + tightened `wp_task_pattern` + `classify_dirty_paths` integration (FR-001–004, FR-006–008, C-001, PLAN-ARCH-001)

**Purpose**: The core mechanism. Add the new ownership-lookup helper, close the adversarial-review-
found over-match in the pre-existing `wp_task_pattern`, and wire the two together inside
`classify_dirty_paths`.

**Steps**:
1. In `src/specify_cli/review/dirty_classifier.py`, add (near `_is_benign`, after
   `_is_review_handoff_survivor_path`) a new **public** (no leading underscore — deliberately
   consumed cross-module) function:

   ```python
   def owning_wp_for_path(path: str, mission_slug: str) -> str | None:
       """Return the WP id that owns *path* by directory/file-naming convention, or None.

       Generalizes the flat `.md`-only convention `_is_review_handoff_survivor_path`'s
       `wp_task_pattern` implements to also cover:
       - any file nested under a WP's task directory, any extension (FR-002)
       - the WP task directory reported as a bare, wholly-untracked path (FR-003)

       Scoped to `mission_slug` (FR-008): a same-numbered WP under a different
       mission's `kitty-specs/<other-slug>/tasks/` tree never matches.
       """
       normalised = to_posix(path).strip()
       pattern = re.compile(
           rf"^kitty-specs/{re.escape(mission_slug)}/tasks/WP(\d+)-[^/]+(?:\.md|/.*)$"
       )
       match = pattern.match(normalised)
       return f"WP{match.group(1)}" if match else None
   ```

   `mission_slug` is interpolated via `re.escape` (not a `[^/]+` wildcard) so FR-008's
   mission-scoping holds regardless of caller. `to_posix` is already imported in this module.

2. **Companion fix (PLAN-ARCH-001, HIGH severity, required by adversarial plan review) — tighten
   `_is_review_handoff_survivor_path`'s `wp_task_pattern`.** The pre-existing pattern —
   `re.compile(r"kitty-specs/[^/]+/tasks/WP\d+-.+\.md$")` — already matches ANY nested `.md` file
   under ANY WP directory in ANY mission, because `.+` is not `/`-anchored and Python's `.` matches
   `/` by default. This silently short-circuits `_is_benign` to `True` for a nested own-directory
   `.md` path (spec.md AC3) or a nested cross-mission `.md` path (FR-008) *before*
   `owning_wp_for_path` is ever consulted. Fix by tightening the character class:

   ```python
   # before (over-matches nested/cross-mission `.md` paths):
   wp_task_pattern = re.compile(r"kitty-specs/[^/]+/tasks/WP\d+-.+\.md$")
   # after — `[^/]+` cannot cross a `/`, so only a FLAT `tasks/WPxx-*.md` file matches:
   wp_task_pattern = re.compile(r"kitty-specs/[^/]+/tasks/WP\d+-[^/]+\.md$")
   ```

   This one-character-class change (`.+` → `[^/]+`) is sufficient on its own to close both gaps:
   once nested paths can no longer match `wp_task_pattern` at all, they fall through to
   `owning_wp_for_path` unchanged and resolve correctly there. Do **not** also anchor the
   mission-slug segment here — `owning_wp_for_path`'s own `re.escape(mission_slug)` anchoring
   already handles FR-008 once the nested path reaches it. **Do not modify `_is_benign`'s own
   signature or body** — only this one regex literal inside the function it calls.

3. Edit `classify_dirty_paths` to consult `owning_wp_for_path` as a second step, only for paths not
   already benign under the existing (now-tightened) `_is_benign` check:

   ```python
   def classify_dirty_paths(
       dirty_paths: list[str],
       wp_id: str,
       mission_slug: str,
       wp_slug: str | None = None,
   ) -> tuple[list[str], list[str]]:
       blocking, benign = [], []
       for path in dirty_paths:
           if not path:
               continue
           if _is_benign(path, wp_id):
               benign.append(path)
               continue
           owner = owning_wp_for_path(path, mission_slug)
           if owner is not None and owner != wp_id:
               benign.append(path)   # FR-001/002/003 — provably another WP's residue
           else:
               blocking.append(path)  # owner == wp_id (FR-007) or owner is None (FR-004)
       return blocking, benign
   ```

   Preserve the existing `(blocking, benign)` 2-tuple return shape exactly — three call sites
   (`tasks_parsing_validation.py`, this module's own docstring example,
   `tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py`) unpack it and must keep working
   unmodified. Update the module docstring's usage example only if it drifts from this shape (it
   should not, since the shape is unchanged).

4. Do NOT change `_is_benign`'s signature or body beyond the one regex literal edited in step 2 — it
   has direct callers outside `classify_dirty_paths` (the kitty-ops-orphan counter-contract in
   `tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py`, and three wp_id-blind pinned tests
   in `test_dirty_classifier.py`) that must stay green unmodified (plan.md Design Decision (c)).

**Files**: `src/specify_cli/review/dirty_classifier.py` (new `owning_wp_for_path` function, one
tightened regex literal, `classify_dirty_paths`'s loop body edited — ~40–60 lines changed/added).

**Validation**: run T001's test(s) again — they should now be GREEN. Do not yet run the full
targeted surface (T004 does that once T003's unit coverage also exists).

---

## Subtask T003: Unit coverage in `test_dirty_classifier.py` (FR-001–004, FR-006–008, PLAN-ARCH-001, Compatibility)

**Purpose**: Direct, fast unit-level coverage for `owning_wp_for_path` and
`classify_dirty_paths`'s new branch — narrower and faster-to-run than T001's ATDD test, covering
every FR individually plus the two PLAN-ARCH-001 regression tests and the explicit no-new-blocking
compatibility regression.

**Steps**: Add the following test functions to `tests/review/test_dirty_classifier.py`, following
the existing file's `_classify(paths, wp_id=..., mission_slug=...)` helper convention (do not
invent a second helper):

1. **FR-001/FR-002 (cross-WP directory file benign, extension-independent)**: a non-`.md` file
   nested under a *different* WP's task directory (e.g.
   `kitty-specs/066-test/tasks/WP02-foo/script.py`) classifies as `benign` when checking WP01.
2. **FR-003 (bare wholly-untracked directory path)**: the bare directory path itself (e.g.
   `kitty-specs/066-test/tasks/WP02-foo/`, trailing slash, no filename) classifies as `benign` when
   checking WP01.
3. **FR-004 (unattributable still blocks, fail-closed) — paired with FR-001's positive control in
   the SAME test module**: a stray path matching no WP directory at all (e.g.
   `kitty-specs/066-test/some-stray-file.txt`) classifies as `blocking` for every `wp_id` tried.
4. **FR-007 (own-directory non-task-file residue still blocks)**: a non-`.md`, non-task file nested
   under the *moving* WP's own task directory (e.g.
   `kitty-specs/066-test/tasks/WP01-foo/scratch.py`) classifies as `blocking` when checking WP01.
5. **FR-008 (mission-scoped ownership)**: a path under a *different* mission's
   `kitty-specs/<other-slug>/tasks/WP01-foo/x.md` classifies as `blocking` (or at minimum
   non-`benign`) when the caller's `mission_slug` is the *current* mission's slug, not
   `<other-slug>`.
6. **`test_own_directory_nested_md_file_still_blocks` (PLAN-ARCH-001)**: assert spec.md's own
   literal AC3 path, `kitty-specs/<slug>/tasks/WP01-foo/scratch.md`, resolves to `blocking` when
   WP01 is the WP being moved — the exact path the un-tightened `wp_task_pattern` would have wrongly
   classified `benign`.
7. **`test_cross_mission_nested_md_file_still_blocks` (PLAN-ARCH-001)**: assert a companion FR-008
   case, `kitty-specs/<other-slug>/tasks/WP01-foo/x.md`, resolves to `blocking` (or at minimum
   non-`benign`) when the caller's `mission_slug` is a *different* mission — proving the tightened
   `wp_task_pattern` no longer lets a nested cross-mission `.md` path reach `benign` before
   `owning_wp_for_path`'s own mission-scoping is even consulted.
8. **`test_no_previously_benign_path_becomes_blocking` (Compatibility & Reflexivity, plan.md Design
   Decision (d))**: run `classify_dirty_paths` over the full set of paths every *existing*
   benign-classification test in this file already exercises (status artifacts, `.kittify/` paths,
   `lanes.json`, root `tasks.md`, both same- and other-WP flat task `.md` files, `meta.json`) across
   a representative sweep of `wp_id` values, and assert every one is still routed to `benign` after
   this mission's change — a single, explicit "benign only ever grows, never shrinks" assertion.
9. **Mutation/failure controls (plan.md Validation Strategy "Mutation and failure controls"),
   include as additional assertions inside the tests above rather than new standalone tests where
   natural**: mutate a cross-WP directory-residue path's extension (`.py` → `.md` → no extension) —
   stays `benign` in every case; mutate the moving WP's own directory to contain a non-task-file —
   stays `blocking`; mutate `mission_slug` to a sibling mission's slug for an otherwise-matching
   path — `owning_wp_for_path` returns `None`.

**Files**: `tests/review/test_dirty_classifier.py` (approx. 9–12 new test functions, ~150–200
lines).

**Validation**: `.venv/bin/python -m pytest tests/review/test_dirty_classifier.py -v` — every
existing test still passes unmodified; every new test passes.

---

## Subtask T004: Confirm GREEN — full targeted surface + counter-contract file (SC-001, SC-002, SC-003)

**Purpose**: Prove T001's ATDD reproduction is now GREEN, T003's unit coverage is GREEN, and no
pre-existing test (including the counter-contract file this WP does not edit) regressed.

**Steps**:
1. Re-run T001's ATDD test(s) and confirm GREEN (they were RED in T001, before T002 existed).
2. Run the full targeted surface:
   ```bash
   .venv/bin/python -m pytest tests/review/test_dirty_classifier.py tests/specify_cli/cli/commands/agent/test_tasks.py tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py -q
   ```
   Confirm zero failures. `test_accept_dirty_kitty_ops.py` is **run only, not edited** — its
   `_is_benign` counter-contracts must stay green unmodified (they will, since `_is_benign`'s
   signature/body is unchanged beyond the one regex literal).
3. Run the owning-module fast tier: `.venv/bin/python -m pytest tests/review/ -q`.
4. `ruff check src/specify_cli/review/dirty_classifier.py tests/review/test_dirty_classifier.py
   tests/specify_cli/cli/commands/agent/test_tasks.py` and `ruff format --check` the same files.
5. Do NOT run `tests/architectural/` in full or `make test-full` locally — CI's architectural-heavy
   battery covers this diff's paths (see tasks.md's Gate set section, sourced from plan.md's Gate
   Statement).
6. Record the exact commands and pass counts for the PR body (mirrors plan.md Baseline's 77-passed
   figure — your new/edited-test run count will differ; record both).

**Files**: none (verification only).

**Validation**: all commands above exit 0 with the expected pass counts and zero failures/errors.

---

## Definition of Done

- [ ] T001: ATDD test(s) in `test_tasks.py` reproducing all three concretely-reported occurrences
  through the real `move-task` entry point — committed RED-first (own commit, before any
  implementation code), confirmed RED at commit time.
- [ ] T002: `owning_wp_for_path` added; `wp_task_pattern` tightened (PLAN-ARCH-001);
  `classify_dirty_paths` integration lands; `_is_benign`'s signature/body otherwise unchanged; the
  `(blocking, benign)` 2-tuple return shape unchanged.
- [ ] T003: unit coverage added for FR-001/002/003/004/007/008, both PLAN-ARCH-001 regression
  tests, and the no-new-blocking compatibility regression test — all existing tests in the file
  pass unmodified in substance (SC-002).
- [ ] T004: T001's tests confirmed GREEN; full targeted surface + owning module fast tier + ruff all
  pass; counter-contract file (`test_accept_dirty_kitty_ops.py`) confirmed green, unedited.
- [ ] Per-subtask completion recorded via `spec-kitty agent tasks mark-status T001 T002 T003 T004
  --status done` (event-sourced, not hand-ticked boxes above).
- [ ] Reviewer has verified, via `git log`, that this WP's first commit was RED on
  `issue-5007-dirty-tree-guard-wp-scoped` and GREEN at the WP's final commit (charter C-011).

## Risks

- The combined regex must not over-match a bare flat non-`.md` file directly in `tasks/` (not
  inside a WP subdirectory) as WP-owned — the `(?:\.md|/.*)` alternation does not match a bare
  `tasks/WP01-foo.py` with no subdirectory. Covered by an explicit negative-control test in T003.
- **(resolved by adversarial plan review, PLAN-ARCH-001)** — see T002 step 2 and T003 tests 6–7 for
  the full mechanism and its regression coverage. Do not skip these two tests; they are the proof
  this defect is actually closed, not merely described.
- NFR-001 (guard stays fast): the added regex compile-and-match is O(1) per dirty path, no new I/O
  or subprocess calls — no perf-sensitive change here, but avoid recompiling the regex per-call in a
  hot loop if you restructure beyond what's shown above (compiling inside `owning_wp_for_path` per
  call, as shown, is acceptable — it matches the existing `_is_review_handoff_survivor_path`
  pattern's own per-call compile style; do not "optimize" this into a module-level constant unless
  you also update the mirrored precedent, which is out of this WP's scope).

## Reviewer Guidance

- Confirm T001's ATDD test(s) actually go through the public `move-task` CLI path (e.g.
  `specify_cli.cli.commands.agent.tasks`), not a synthetic call directly into
  `classify_dirty_paths` — the ATDD contract requires the real entry point.
- Confirm the RED→GREEN sequence via `git log`: T001's commit exists and is provably RED against
  the WP's `planning_base_branch` (or against a checkout before T002's commit), then GREEN at the
  WP's final commit.
- Confirm `_is_benign`'s signature and body are unchanged except the one regex-literal tightening
  inside `_is_review_handoff_survivor_path` — no ownership logic was folded into `_is_benign`
  itself (plan.md Design Decision (a)'s "Rejected alternative").
- Confirm `owning_wp_for_path` is NOT added to `src/specify_cli/review/__init__.py` — it stays a
  direct-submodule-import-only helper (plan.md Design Decision (f); WP02 will consume it this way).
- Confirm no `src/specify_cli/ownership/` file is touched (C-001) and no `.kittify/`/`lanes.json`
  file is touched.
- Confirm `test_accept_dirty_kitty_ops.py` was run (not edited) and stays green.
- Confirm the two PLAN-ARCH-001 regression tests (`test_own_directory_nested_md_file_still_blocks`,
  `test_cross_mission_nested_md_file_still_blocks`) exist and pass — these are the proof the
  adversarial-review-found gap is actually closed.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude
```
