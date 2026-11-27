---
work_package_id: WP11
title: '#7497 canceled content via a re-approved dependency lane'
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: 2c1a56fe6a9e857846650f6cfad7279b6eff15b1
created_at: '2026-11-20T17:56:09.654207+00:00'
subtasks:
- T040
- T041
- T042
- T043
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_canceled_via_reapproved_dependency.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_canceled.py
- src/specify_cli/consolidation/reconciliation_kernel.py
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_canceled_via_reapproved_dependency.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 - #7497 canceled content via a re-approved dependency lane

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Prove, red first, whether canceled content can land through a re-approved dependency lane (#7497), and close it if it can. Advertising re-approval as the route (this Mission) must not open a bypass for canceled work.

The shape (spec US8, FR-011):

1. lane A (`lane-a`, `WP01`) approved;
2. lane C (`lane-b`, `WP02`) cut from A, then **fully canceled** with operator provenance;
3. C merged into A (`git merge --no-ff`);
4. A re-approved by an **unforced, independent** review approval whose `lane_head` stamp descends from that merge;
5. a **fresh** `consolidate`.

Expected verdict: refused with `CANCELED_REACHABLE_VIA_DEPENDENCY`, naming C's content. Control: the same lanes where A was NOT re-approved over C's merge keep today's verdict (`LANE_MOVED_AFTER_APPROVAL` on lane-a, pinned by `tests/consolidation/test_resume_frozen_anchors.py:161-185` on the resume path).

Two outcomes, both acceptable, decided by the red-first run:

- **Red at the base** (expected by the squads): fix it in this WP (T041), keep the test, prove it with a mutation check (T043). FR-011 Delivery stays `[build]`.
- **Green at the base**: keep the test as a `[ratchet]` pin, record the evidence for closing #7497 in the WP history (T042), and still run the mutation check (T043) so the pin is not vacuous.

## Context & Constraints

Read before coding:

- `.kittify/charter/charter.md`, then `spec-kitty charter context --action implement`.
- `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (US8, FR-011), `plan.md` (IC-07), `research.md` (R-09), squad 2 renata HIGH on FR-011 (harness retired, green branch, vacuous fixtures) and architect "FR-011" section.
- ADR `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (the (g) pin and the operator ruling that the fresh-run flip is "not an FR-015 verdict").

Integrity invariants:

- **C-001**: never attribute canceled content because an approval reaches it. A re-approval reviews the approved WP's own work; it cannot un-cancel another lane's work.
- **C-002**: no attestation, flag or record lifts the result. `--attest-canceled-superseded` keeps its narrow existing meaning (it lifts only the `no_stamp` refusal, `reconciliation_canceled.py:400-441`).
- **C-006**: one closed-world anchor authority (`reconciliation_kernel._closed_world_anchors`), one canceled-dependency resolution (`_resolve_canceled_dependency_lanes`). Fix inside them; do not add a parallel canceled-content axis.
- **Fail closed (NFR-002)**: any git probe error in a new computation shrinks what is exempt or refuses; it never exempts more.
- **Shrinking direction only**: a fix may only make more of C's commits count as C's own (canceled) work. It must never move an approved lane's own commits into the canceled set (that would refuse the control).

Current code (HEAD of the planning base):

- `src/specify_cli/consolidation/reconciliation_kernel.py:214-261` `_closed_world_anchors(lanes_manifest, lane, target_base, *, excluded_canceled_wp_ids, frozen_tips)`: for lane C the anchors are the LIVE tips of C's non-planning, non-fully-canceled dependency lanes (A) plus the target base. Shared by the closed world, the canceled-lane readers, the approved bound and the approved-reviewed attestation (comment at `:212-213`): do not change its meaning for the other consumers.
- `src/specify_cli/consolidation/reconciliation_canceled.py`
  - `_fully_canceled_lane_commits` (`:294-323`) and `_fully_canceled_lane_own_commits` (`:326-343`): C's own commits = `lane_own_commits(repo, coord_base_ref, C's tip commits, _closed_world_anchors(C))`. Once A merges C, A's live tip reaches every C commit, so C's own set is EMPTY and nothing is subtracted or judged (the hypothesis of research R-09).
  - `_carrier_spines` (`:378-389`): a carrier is an approved, not fully canceled lane whose **first-parent spine** contains a canceled own commit. A `git merge --no-ff` of C into A puts C's commits behind the merge's second parent, NOT on A's first-parent spine. So even with C's own commits restored, A may not count as a carrier, and `CANCELED_REACHABLE_VIA_DEPENDENCY` would not be produced; the verdict could instead be an un-attributable FAIL (squash: `_authoring_merges` does not trust C's tip as a root because C is not approved, `reconciliation_authorship.py:364-392`) or a PASS (merge strategy: C's commits counted as A's approved SHAs). Find out which, in T040.
  - `_resolve_canceled_dependency_lanes` (`:514-552`): the resolution the claim calls first (`reconciliation_claim.py:285-298`).
- `src/specify_cli/consolidation/wp_attribution.py:786-792` `lane_own_commits` and `:658-673` `first_governed_open_stamp` (read-only use for the anchor fix). This file is in this WP's `owned_files` ONLY as leeway for the carrier fix (T041 step 3, `canceled_spine_content`, `:967`); no other WP owns it. Any edit there is limited to what the carrier fix needs, is listed in history with its rationale, and leaves `lane_own_commits` and `first_governed_open_stamp` unchanged.
- **Do not change `reconciliation_kernel._lane_first_parent_spine`** (`reconciliation_kernel.py:313-326`) in any way (signature, meaning, or its tolerance of an unresolvable range): it is the gate's spine reader, and WP05's claim/gate agreement test and WP04's dropped-merge sink depend on it.
- Fixture builder: `tests/consolidation/resume_frozen_anchors_support.py:157-171` `build_canceled_lane_on_approved_dependency(tmp_path)` returns a `ShapeMission` (coordination topology): lane-a/WP01 approved, lane-b/WP02 depends on lane-a and is canceled with operator provenance. Helpers: `characterization_support.lane_checkout`, `cs._git`, `cs.run_in_process`, `cs.consolidate_args`, `fixture_phase`, `require` (fixture work never asserts; it raises `FixturePrecondition`). The transitions: `tests/terminus/mixed_lane_support.transition` and `tests/terminus/canceled_dependency_support._approve` / `ACTOR` / `REVIEWER` (unforced, distinct reviewer), applied to `mission.coord_mission()`.
- The issue text names `tests/consolidation/test_reconciliation_intended_verdicts.py`; that file was retired (ADR 2026-11-08-2). Do not recreate it.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on fix/approved-lane-resolution-route; completed changes must merge back into fix/approved-lane-resolution-route.
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP11 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T040 - Red-first test with asserted preconditions

- **Purpose**: a test that cannot pass vacuously (renata HIGH on FR-011: C not fully canceled, merge not reached by A's new stamp, a forced re-approval, or C's blob equal to approved content would each make it green for the wrong reason).
- **Files**: `tests/consolidation/test_canceled_via_reapproved_dependency_7497.py` (new).
- **Steps**:
  1. Build: `mission = build_canceled_lane_on_approved_dependency(tmp_path)`.
  2. Inside `fixture_phase()`: in `cs.lane_checkout(mission, mission.lane_branches["WP01"])` run `git merge -q --no-ff --no-edit <lane-b branch>` (exactly what the (g) pin does at `test_resume_frozen_anchors.py:174-175`).
  3. Re-approve WP01 through the production shell, unforced, by distinct actors: `transition(coord, "WP01", "in_progress", actor=ACTOR, review_ref="review-WP01-rework")`, then `_approve(coord, "WP01", reference="review-WP01-reapproved")` (which does `for_review` by `ACTOR`, `in_review` by `REVIEWER`, `approved` by `REVIEWER` with an approved `ReviewResult`). If `approved -> in_progress` is refused by a guard, record the guard and use the sanctioned send-back command semantics (`approved_bound.move_back_command`), never `force=True` (a forced approval does not restamp, #5721).
  4. Preconditions, each with `require(...)` (not `assert`), so a broken fixture ERRORS instead of passing:
     - WP02 is canceled with operator provenance and lane-b is fully canceled (`lane_fully_canceled`);
     - C's canceled blob (`src/pkg/wp02.py` at lane-b's tip) is reachable from lane-a's tip, and differs from every blob an approved lane authored (read the path at lane-a's first approval stamp: absent or different);
     - WP01's newest approval is an unforced review approval whose `lane_head` stamp descends from the merge commit (`git merge-base --is-ancestor <merge> <stamp>`), read with `approved_bound.approval_stamp(events, "WP01")`;
     - no `consolidate` record exists (fresh run).
  5. Act: `result = cs.run_in_process(mission, ["consolidate", "--mission", mission.slug, "--yes"])` (in process, so T043 can patch).
  6. Assert: `result.exit_code != 0`; `CANCELED_REACHABLE_VIA_DEPENDENCY` in the output; the output names `WP02` / lane-b and the canceled path; the target does not carry C's blob afterwards (whatever the rollback did, `blob_present_at` on the target is False).
  7. Control test: same build WITHOUT step 3 (A not re-approved). Assert today's verdict: refused with `LANE_MOVED_AFTER_APPROVAL` naming lane-a (as the (g) pin does on resume). This must stay green before and after the fix.
  8. Run it at the base. Record in the WP history the exact exit code, codes and divergence fields (`CellResult` exposes them, `characterization_support.py:265-294`). That record decides T041 versus T042.
- **Parallel?**: no; T041/T042 depend on its outcome.

### Subtask T041 - If red: anchor C on A as of before A incorporated C

- **Purpose**: restore C's own commits so the canceled-dependency axis can judge them, without disturbing any other consumer of `_closed_world_anchors`.
- **Files**: `src/specify_cli/consolidation/reconciliation_canceled.py` (preferred) and, only if a shared helper is needed, `src/specify_cli/consolidation/reconciliation_kernel.py`.
- **Steps**:
  1. Diagnose first, with the T040 record: is C's own set empty (anchor problem), is A missing from `_carrier_spines` (first-parent problem), or both? Write a focused unit test for each mechanism you confirm (call `_fully_canceled_lane_own_commits` and `_carrier_spines` directly on the built repo).
  2. Anchor fix (research R-09): for a fully-canceled lane C, anchor each approved dependency lane A not at its live tip but at **A as it was before it first incorporated C**. Pitfall: `git merge-base A C` after A merged C IS C's tip, so a plain merge-base is wrong. A sound definition: walk A's first-parent spine from `coord_base_ref` (oldest first); the anchor is the first parent of the earliest merge on that spine whose non-first parent reaches a commit of C that A's previous spine commit does not reach; if A never merged C, keep A's live (or frozen, FR-015) tip, so every Mission without this shape is unchanged. Implement it as a small helper (for example `_dependency_anchor_before_incorporating(repo, coord_base_ref, dep_tip, canceled_tip)`) used only by `_fully_canceled_lane_own_commits`. Keep `_closed_world_anchors` itself unchanged for its other consumers.
  3. Carrier fix (only if T040 shows A is not a carrier): a lane that reaches a canceled own commit through ANY parent of its spine carries it. Options: widen `_carrier_spines` to treat a merge on the spine whose second parent reaches a canceled own commit as carrying it, or compute the carrier set from full reachability (`commits_in_range`). Whatever you choose, `canceled_spine_content` (`wp_attribution.py:967`) must still be able to resolve the content. Preferred: pass it a spine that includes the merged-in canceled commits, from `reconciliation_canceled.py`. If that is not enough, adjust `canceled_spine_content` itself under the recorded leeway (Context): only the carrier walk, with a direct unit test, and its existing tests green. Never relax the expected code; if even that does not yield `CANCELED_REACHABLE_VIA_DEPENDENCY`, record why the verdict is a different code and stop for an operator ruling (see the next step).
  4. If after the anchor fix the verdict is a FAIL with a different code (for example an un-attributable blob naming C's path) rather than `CANCELED_REACHABLE_VIA_DEPENDENCY`: the content still does not land, but the spec names the code. Record the evidence and raise it with the orchestrator before changing the expected code; do not silently relax the test.
  5. Fail closed: any `GitProbeError` in the new helper falls back to the live anchor only if that shrinks the exempt set; otherwise let it propagate (the claim builder turns it into a pre-mutation refusal). Simplest correct rule: on a probe error, anchor nothing for A (exempt less), never more.
  6. Complexity <= 15 per function; each new helper gets a direct unit test (Sonar new-code coverage).
- **Edge cases**:
  - C merged into A, then A merged C again later: the earliest incorporation decides.
  - A fast-forwarded C (no `--no-ff`): C's commits are on A's first-parent spine; the walk finds no merge; then the anchor should be the last A spine commit before the first C commit. Cover it with a test or record it as a residual.
  - `--resume` (frozen tips, FR-015): the helper must respect `frozen_tips` exactly as `_closed_world_anchors` does; add one assertion on a frozen-tip input.
  - Planning lanes and fully canceled dependency lanes are not anchors today; keep that.

### Subtask T042 - If green at the base: ratchet pin and #7497 evidence

- **Purpose**: a green-at-base result must still prove something.
- **Steps**:
  1. Keep T040's test as is, with its preconditions. Rename nothing; add a module docstring stating that the shape is closed at the base and why (name the mechanism you observed: which axis refused, which code).
  2. Record in the WP history: the base commit, the observed exit code and codes, and the statement "FR-011 is a ratchet pin; #7497 can be closed with this evidence". The operator closes the issue; do not close it from this WP. Note for the issue matrix that FR-011 Delivery changes to `[ratchet]`.
  3. Still do T043.
  4. Evidence to capture for the issue (paste into the history note, short): the fixture's commit graph (`git log --graph --oneline --all` trimmed to the lanes), WP01's newest approval event (`to_lane`, `force`, `lane_head`), the run's exit code, and the divergence fields from `CellResult`.
  5. Decide whether the pin belongs beside the (g) pin: the (g) pin covers the resume path without re-approval; yours covers the fresh run with re-approval. Cross-reference them in both docstrings only through your own file (do not edit `test_resume_frozen_anchors.py`, it is not owned).
- **Note**: if the test is green only because a different, earlier refusal fires (for example WP05's `RESOLUTION_MERGE_UNREVIEWED` after it lands, or `LANE_MOVED_AFTER_APPROVAL`), it is NOT green for this shape: the merge precedes the re-approval, so neither should fire. Investigate before choosing T042.

### Subtask T043 - Mutation check

- **Purpose**: show the test fails when the protection is removed (renata: "disabling the canceled-dependency subtraction turns the test red").
- **Steps**:
  1. In a scratch run (not committed), monkeypatch the protection off: for the fix path, patch your new anchor helper to return the live tip (the old behaviour); for the green path, patch `_resolve_canceled_dependency_lanes` to return `_CanceledDependencyResolution()` (nothing subtracted, no content). Run T040's test; it must fail.
  2. Also invert one precondition (re-approve with `force=True`, which does not restamp): the precondition `require` must raise.
  3. Optionally keep the mutation as a permanent test (`test_protection_is_load_bearing`) using `monkeypatch` on the in-process run; preferred if it runs under 30 s.
  4. Record both outcomes in the WP history.
- **Expected outcomes**:

  | Mutation | Expected result |
  |---|---|
  | protection off (helper returns the live tip, or the resolution subtracts nothing) | T040's main test FAILS (canceled content is not refused, or refused with another code) |
  | re-approval forced (`force=True`) | the `require` on the stamp raises `FixturePrecondition` (test ERRORS) |
  | merge skipped | the `require` on reachability of C's blob raises |
  | control test with protection off | unchanged (the control does not depend on the fix) |

- **Edge cases**: a mutation that makes the run crash (traceback) is not a valid red; the failure must be the assertion on the verdict. If the in-process runner swallows the exception, read `CellResult.output` and the exit code.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_canceled_via_reapproved_dependency_7497.py -q
# blast radius of reconciliation_canceled.py / reconciliation_kernel.py
uv run --frozen pytest tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_canceled_dependency_lane.py -q
grep -rln "_fully_canceled_lane\|_carrier_spines\|_closed_world_anchors\|CANCELED_REACHABLE_VIA_DEPENDENCY" tests/ --include="*.py"   # run every consolidation and terminus file it lists
uv run --frozen pytest tests/terminus/ -q -k "canceled_dependency"
uv run --frozen pytest tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_refusal_precedence_matrix_windows.py -q
uv run --frozen pytest tests/architectural/test_layer_rules.py -q
make test-fast
```

Quality gates (zero findings, no new suppressions, complexity <= 15):

```bash
uv run --frozen ruff check src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation_kernel.py src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_canceled_via_reapproved_dependency_7497.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation_kernel.py src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_canceled_via_reapproved_dependency_7497.py
uv run --frozen mypy src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation_kernel.py src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_canceled_via_reapproved_dependency_7497.py
```

Tracer notes: record the T040 result, the mechanism diagnosis, the chosen anchor definition and any residual with `spec-kitty agent tasks add-history WP11 --note "<trace: ...>" --mission approved-lane-resolution-route-01M7WW0Z` (this code WP cannot own `kitty-specs/traces/`).

## Risks & Mitigations

- **Vacuous green**: mitigated by `require` preconditions and the T043 mutation check.
- **Refusing a legitimate Mission**: an anchor that is too early moves A's own approved commits (fast-forwarded into C at C's cut) into C's own set. Mitigated by the control test and by keeping the live anchor for every Mission where A never incorporated C.
- **Shared anchor authority**: `_closed_world_anchors` serves four consumers; changing it changes the approved bound and the attestation. Mitigated by a C-only helper in `reconciliation_canceled.py`.
- **First-parent carrier blind spot**: may keep the expected code from appearing even after the anchor fix. Mitigated by diagnosing in T041 step 1 and escalating rather than relaxing the expectation.
- **Interaction with WP05**: after WP05, a merge on lane-a not reached by lane-a's own stamp would refuse with `RESOLUTION_MERGE_UNREVIEWED`. In this shape the re-approval reaches the merge, so it must not fire; if it does, the fixture is wrong.

## Review Guidance

- Harness: the test uses `build_canceled_lane_on_approved_dependency`, not the retired intended-verdicts corpus (renata HIGH on FR-011, issue 1).
- Preconditions use `require` and cover all four vacuity routes: C fully canceled, the stamp descends from the merge, the re-approval is unforced and by a distinct reviewer, C's blob differs from approved content (issue 3).
- The expected code is pinned exactly (`CANCELED_REACHABLE_VIA_DEPENDENCY`), not "refused or excluded" (issue 4).
- The green branch, if taken, is explicit: ratchet pin plus recorded evidence (issue 2).
- A mutation check was run and recorded (or is a permanent test).
- `_closed_world_anchors` semantics are unchanged for its other consumers; the control keeps today's verdict.
- `_lane_first_parent_spine` is byte-identical in the diff. Any `wp_attribution.py` edit is confined to the carrier walk of `canceled_spine_content`, listed in history with its rationale and a direct unit test.
- Ruff, format (`--force-exclude`) and mypy clean on the owned files; complexity <= 15.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) - never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
