---
work_package_id: WP02
title: 'Approved bound: red-first reproduction and claim-time refusal'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-008
- FR-009
- FR-010
- FR-013
- NFR-001
- NFR-004
- C-002
- C-003
- C-005
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T19:56:59.921127+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Core fix
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/approved_bound.py
- tests/consolidation/test_approved_bound.py
- tests/terminus/post_approval_support.py
- tests/terminus/test_post_approval_commit_refused.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/approved_bound.py
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/git_probes.py
- tests/consolidation/test_approved_bound.py
- tests/terminus/post_approval_support.py
- tests/terminus/test_post_approval_commit_refused.py
- tests/consolidation/test_canceled_content_residuals.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Approved bound: red-first reproduction and claim-time refusal

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task.** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status --mission approved-claim-bound-01M444QR`). If this work package was returned from review, every feedback item is part of your work.

---

## Objectives & Success Criteria

The defect of issue 5668 is closed at claim time.

- A regression test drives `spec-kitty consolidate` on a mission with a post-approval commit, for lanes and coordination topologies and for squash and merge strategies. It is committed **red** as the first commit of this work package (charter ATDD-first, Standing Order 4).
- `consolidate` refuses before any branch moves with `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING` or `APPROVAL_STAMP_NOT_ON_LANE` (texts in `contracts/consolidate-refusals.md`).
- Tool-made lane movement (merges from a dependency lane, the mission branch or the target; bookkeeping-only commits; a later approval on the same lane; a resumed run) is not refused.
- Two public functions in `reconciliation.py` (`approved_bound_refusal`, `lane_tips_moved_refusal`) and two run-state fields exist for the parallel work packages WP03 and WP05 to call; they add nothing to these files.
- Existing refusals keep their codes, texts and precedence; the #5330 strict xfails keep their state.

Implementation command: `.venv/bin/spec-kitty agent action implement WP02 --agent implementer --mission approved-claim-bound-01M444QR`

## Context & Constraints

Read first, in this order:

1. `.kittify/charter/charter.md` (binding) and `spec-kitty charter context --action implement --json`.
2. `kitty-specs/approved-claim-bound-01M444QR/spec.md`, `plan.md` (sections D-1 to D-6), `research.md`, `data-model.md`, `contracts/consolidate-refusals.md`.
3. `kitty-specs/approved-claim-bound-01M444QR/research/code-grounding.md` for file and line references. Line numbers were taken at `9adc68803f`; re-locate by symbol name (`codegraph explore "<symbol>"`).

Rules that bind every work package of this mission:

- **CLI binary**: always `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest`. The bare `spec-kitty` on PATH is a stale install. Never `uv run`.
- **No heavy suites**: never `make test-full`, never a bare `tests/architectural/` run. Run the files named in this prompt.
- **Test economy**: each new test must pin one distinct behaviour. No test per helper, no duplicate of an existing pin. Prefer extending a parametrized test over adding a sibling.
- **Quality**: `ruff check` and `mypy --strict` clean on changed files, complexity <= 15, no new `# noqa` or `# type: ignore`. Format check: `uv run --frozen ruff format --check --force-exclude <changed files>`.
- **Status imports**: import status symbols only through the `specify_cli.status` facade. Git reads go through `consolidation/git_probes.py`; do not shell out to git directly from new consolidation code.
- **Byte-identity**: no existing refusal code or text changes. New texts are additions.
- **No fail-open**: an absent approval stamp is never replaced by the lane tip, in product code or by a test switch (spec C-003).
- **Terminology**: Mission and work package; `--mission`, never `--feature`.
- **Commits**: conventional messages; every commit ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model or tool identifiers in commit messages.
- **Tracers**: do not edit `kitty-specs/approved-claim-bound-01M444QR/tracers/*.md` in a lane worktree (parallel lanes would conflict). Put tooling friction and unplanned design decisions in this prompt's Activity Log and in your hand-back report; the orchestrator records them.

## Branch Strategy

- **Strategy**: see `branch_strategy` in the frontmatter (written by `finalize-tasks`)
- **Planning base branch**: issue-5668-approved-claim-bound
- **Merge target branch**: issue-5668-approved-claim-bound

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` resolves, do not construct it.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first reproduction through the CLI

- **Purpose**: witness the bug through the pre-existing entry point before fixing it.
- **Steps**:
  1. Create `tests/terminus/post_approval_support.py`. Build on `tests/terminus/canceled_dependency_support.py` (`_commit_in`, `_approve`, the real `allocate_lane_worktree`, `mixed_lane_support.transition`, which is the production transactional transition shell, so stamps come from the real probe) and on `lanes_fixture.py` for the LANES topology. Provide one builder per topology that returns a mission with two lanes (WP01 on one, WP02 on the other), each implemented, reviewed and approved through real transitions, and these helpers: `add_post_approval_commit(mission, lane="lane-a", path="src/alpha/late.py", content="UNREVIEWED = True\n")` committing on that lane's branch; `strip_approval_stamps(mission, wp_id)` removing the `lane_head` stamp from that work package's `approved` events (reuse `canceled_dependency_support.strip_lane_head_stamps` if it fits); `rework_and_reapprove(mission, wp_id)` built on `canceled_dependency_support._reopen_and_finish_wp01(final="approved")`. **This file is frozen after this work package**: WP03, WP04, WP05 and WP07 run in parallel lanes and only import it. If `mixed_lane_support.transition` does not work for a LANES mission with no coordination branch (not verified at planning time), stamp the LANES fixture the way `lanes_fixture._stamped` does, with the real lane tips, and say so in the module docstring.
  2. Create `tests/terminus/test_post_approval_commit_refused.py`, parametrized over `topology in ("lanes", "coord")` and `strategy in ("squash", "merge")`, modelled on `tests/terminus/test_canceled_dependency_fast_forward_verdicts.py` (`_STRATEGIES`, `_consolidate`, `run_terminus` from `tests/terminus/conftest.py`, which runs `python -m specify_cli consolidate` as a subprocess).
  3. Each cell asserts, on one fixture: (a) **positive control**: a twin mission with no late commit consolidates with exit 0, prints "Reconciliation verified" and has the approved file on the target; (b) with the late commit: exit code non-zero, the output contains `LANE_MOVED_AFTER_APPROVAL`, the short SHA of the late commit and `WP01`, the output does not contain "Reconciliation verified", the target, mission and (coordination topology) coordination branch tips equal their pre-run tips (NFR-004), and `git show <target>:src/alpha/late.py` fails.
  3a. One more test in the same file (spec US3 scenario 4), one topology and the default strategy: `rework_and_reapprove` WP01, then `consolidate` exits 0 and the rework content is on the target. It is green before the fix and must stay green.
  4. Markers: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]`. Not `p0_repro` (a plugin deselects it outside the nightly) and not `slow` unless a cell exceeds 30 seconds.
  5. Run it: the four refusing cells must fail because `consolidate` exits 0 and `late.py` is on the target. Commit only the two new test files: `test(consolidation): reproduce post-approval commit landing under a verified banner`. Paste the failing output summary into the Activity Log.
- **Files**: the two new test files.
- **Notes**: known gap, state it in the module docstring: no harness drives `implement` and the review transitions through the CLI; the transitions use the in-process production shell, the consolidation is a real subprocess.

### Subtask T007 – `approved_bound.py`: the approval-stamp reader

- **Purpose**: one function answers "which commit did review approve for this work package".
- **Steps**:
  1. Create `src/specify_cli/consolidation/approved_bound.py` with a module docstring that states the rule and names plan D-1 and D-2.
  2. Constants: import `ATTESTATION_KEY` from `canceled_attestation` (exported by WP01); do not redefine it. WP01 left `ATTESTATION_KEY` and `lane_exempt_commits` out of their modules' `__all__` because the dead-symbol gate (`tests/architectural/test_no_dead_symbols.py`) needs a `src/` caller: add each to `__all__` in the commit that first imports it, and run that gate. Add `APPROVED_REVIEWED = "approved_reviewed"` (the attestation value WP04 will record) and `ATTEST_APPROVED_FLAG = "--attest-approved-reviewed"`.
  3. `approval_stamp(events: Sequence[StatusEvent], wp_id: str) -> str | None`: walk the events in append order; for events of `wp_id` that are not migration events (`is_migration_event`), remember `stamp_of(event)` when `event.to_lane == "approved"` or when `(event.policy_metadata or {}).get(ATTESTATION_KEY) == APPROVED_REVIEWED`. Return the last remembered value. An approval event with no stamp makes the result `None` (the latest approval decides; an older stamped approval must not shine through a newer unstamped one).
  4. The `approved -> done` event is never read: its `to_lane` is `done` and it carries no attestation.
- **Files**: `src/specify_cli/consolidation/approved_bound.py`.

### Subtask T008 – `approved_bound.py`: the lane check

- **Purpose**: decide, for one code lane, whether its tip is within what review approved (plan D-2).
- **Steps**:
  1. Types: `class BoundRefusalCode(StrEnum)` with `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING`, `APPROVAL_STAMP_NOT_ON_LANE`; a frozen dataclass `BoundRefusal(code, lane_id, branch, wp_ids, commits=(), path=None, stamp=None)` with a `render()` method that returns the text from `contracts/consolidate-refusals.md`, starting with `"<CODE>: "` like the existing `APPROVED_CONTENT_MISSING` clause in `reconciliation.py`.
  2. `check_lane(repo_root, *, events, lane_id, branch, approved_wp_ids, canceled_wp_ids, claim_base, anchors, is_bookkeeping) -> BoundRefusal | None`:
     - for each approved work package: `approval_stamp`; if `None`, return `APPROVAL_STAMP_MISSING` naming all such work packages of the lane;
     - covered points = the approval stamps, plus for each canceled work package of the lane the stamp of its latest non-migration event (skip when it has none);
     - each **approval** stamp must satisfy `sha_reachable_from(repo_root, stamp, branch)` (a commit is its own ancestor), else `APPROVAL_STAMP_NOT_ON_LANE`. A canceled work package's covered point that is not on the lane is simply dropped;
     - candidates = commits reachable from the lane tip and from none of the covered points and not from `claim_base`. Add a probe to `git_probes.py` only if none fits; `commits_in_range` handles one exclusion, so you may need `commits_excluding(repo_root, tip, excluded_refs)` (`git rev-list tip --not a b c`), fail-closed like its siblings (raises `GitProbeError`). If you add a probe, run `tests/architectural/test_destructive_op_routing.py` (it pins lines of `git_probes.py`). Walk the **full** range, never the first-parent spine: a late commit that arrives through a merge from a branch that is not an anchor must be found;
     - drop merge commits (`is_merge_commit`), drop commits in `lane_exempt_commits(repo_root, claim_base, anchors)` (public since WP01), drop commits whose changed paths (`changed_paths_of`) are all bookkeeping;
     - if any remain: `LANE_MOVED_AFTER_APPROVAL` with up to three commits (newest first) and one offending path.
  3. Keep `check_lane` at complexity <= 15: extract `_covered_points`, `_content_commits_beyond` as pure helpers.
- **Files**: `src/specify_cli/consolidation/approved_bound.py`.
- **Notes**: a `GitProbeError` propagates. `phase_claim._capture_reconciliation_claim` already turns it into a fail-closed refusal.

### Subtask T009 – Wire the check into the claim builder

- **Purpose**: refuse before the first mutation (plan D-3).
- **Steps**:
  1. Add one **public** function to `reconciliation.py`, with exactly this signature (WP03 and WP05 call it from parallel lanes and must not redefine it):
     ```python
     def approved_bound_refusal(
         repo_root: Path,
         feature_dir: Path,
         lanes_manifest: LanesManifest,
         *,
         coord_base_ref: str,
         excluded_canceled_wp_ids: Iterable[str] = (),
         excluded_window_base: str | None = None,
         event_log: _ClaimEventLog | None = None,
     ) -> str | None: ...
     ```
     It reads the Lamport snapshot for membership exactly as `build_approved_wp_set` does (when called from the builder, pass what the builder already resolved through a private helper so nothing is read twice). In `build_approved_wp_set`, after the mixed-lane and canceled-dependency resolution (their refusals keep precedence) and before the collectors, call it with the builder's `event_log` and, if it returns text, return `_refusal_claim(...)` with it.
  2. `approved_bound_refusal` iterates the lanes of the manifest and skips: planning lanes (`is_planning_lane`), a `single_branch` authorship window (`sb_window` is set), lanes that are fully canceled (`lane_fully_canceled`), lanes with no work package in `_APPROVED_MEMBERSHIP_LANES`. For the rest it calls `approved_bound.check_lane` with: the lane branch from `_lane_branch_for`; `claim_base=coord_base_ref`; anchors = `_closed_world_anchors(lanes_manifest, lane, excluded_window_base, excluded_canceled_wp_ids=...)` plus the mission branch **resolved to a SHA now** (at claim time the mission branch has not yet received this run's lane merges; on a resume it holds the lanes an earlier attempt consolidated, which is what makes the tool's own merge into a stale lane exempt); `is_bookkeeping` = the same `functools.partial(_is_bookkeeping, ...)` the mixed-lane resolver builds. Join several refusals with `"; "` in lane order.
  3. Events: read them through the existing `_ClaimEventLog` instance that `build_approved_wp_set` already creates, so the log is read at most once per claim. If the read fails (`event_log.read()` is `None`), refuse with this text (the existing `unreadable(...)` helper returns a mixed-lane `Unattributable` worded for a canceled work package, which does not fit): `the status event log could not be read, so the approvals of lane <lane_id> cannot be bounded to what was reviewed. Recovery: repair or restore status.events.jsonl, then re-run`. Never skip the check when the log is unreadable.
  4. Add the three codes as module constants next to `APPROVED_CONTENT_MISSING`, or re-export them from `approved_bound`; one definition only.
  5. Update the `build_approved_wp_set` docstring bullet "approved commit SHAs come from lane-branch git tips ... (never status rows)": the collectors still read the lane branch, and the lane check in front of them refuses a lane whose tip is beyond the approval stamps.
  6. Update the `_resolve_mixed_lane_canceled_content` docstring sentence "a non-mixed mission never pays the read": every claim with a code lane now reads the log once.
  7. Second public function, for the gate (WP03 calls it; define it here so no parallel lane adds it):
     ```python
     def lane_tips_moved_refusal(
         repo_root: Path,
         lanes_manifest: LanesManifest,
         *,
         validated_tips: Mapping[str, str],
         anchor_shas: Sequence[str],
         planning_prefix: str | None,
     ) -> str | None: ...
     ```
     For each lane branch in `validated_tips` that still exists: the commits reachable from the live tip and not from its validated tip, any other lane's validated tip or any of `anchor_shas`; drop merge commits and bookkeeping-only commits; anything left is `LANE_MOVED_AFTER_APPROVAL` (same rendering, naming the lane's approved work packages). It reads no events: the stamps were checked at claim time, and this asks only "did content arrive on a lane since then". Every reference it excludes is a SHA captured before this run mutated anything, never a live branch name: at gate time the live mission branch already contains every merged lane commit, so a live name would exempt the very commit this check exists to find.
  8. In `phase_claim._capture_reconciliation_claim`, after the claim passed its integrity check, record on the run state (new fields on `_MergeRunState` in `run_state.py`): `validated_lane_tips: dict[str, str]` (branch name to tip SHA for every lane the check covered, resolved at this moment) and `bound_anchor_shas: tuple[str, ...]` (the mission branch, the target and, when present, the coordination base, each resolved to a SHA at this moment). In-memory fields are enough: the gate runs in the same process, and a resume recomputes them in its own claim phase.
  9. Run T006: all cells must pass. Then run the issue's own reproducer if you want a second witness (`kitty-specs/{MS}/quickstart.md`).
- **Files**: `src/specify_cli/consolidation/reconciliation.py`.
- **Notes**: `reconciliation.py` is large; add the wiring function near `_resolve_mixed_lane_canceled_content`, and keep new logic in `approved_bound.py`.

### Subtask T010 – Unit tests for the bound

- **Purpose**: pin the rule where it lives. One test per distinct behaviour; build small real git repos with the helpers already used in `tests/consolidation/test_wp_attribution.py`.
- **Cases** (`tests/consolidation/test_approved_bound.py`):
  1. `approval_stamp`: latest approval wins after a rework cycle; a migration event is ignored; the `approved -> done` restamp is ignored; an attestation event (`policy_metadata.attestation == "approved_reviewed"`, any `to_lane`) supplies the stamp; a `done` work package with no `approved` event yields `None`. Use one parametrized test.
  2. `check_lane` refuses with each of the three codes and names what the contract says it names.
  3. FR-009 movements, each paired with a refusing control on the same repo: a merge from a dependency lane; a merge from the mission branch (the resume case: the tool's own auto-rebase merge); a merge from the target; a commit touching only `kitty-specs/<slug>/` bookkeeping; two work packages approved one after the other on one lane. After each passing assertion, add one content commit and assert `LANE_MOVED_AFTER_APPROVAL`. One more refusing case: a content commit that reaches the lane only through a merge from a branch that is not an anchor (a first-parent walk would miss it).
  4. A mixed lane: a canceled work package's commits made after the approved work package's approval are not reported, a commit after the cancel is.
  5. Through `build_approved_wp_set` (the production path), one parametrized test: a planning lane and a `single_branch` window are skipped; a rewritten lane (approval stamp no longer an ancestor of the tip) yields a refusal claim with `APPROVAL_STAMP_NOT_ON_LANE`; an unreadable event log yields a refusal claim with the T009 text.
  6. `lane_tips_moved_refusal`: a content commit after the validated tip refuses; a merge of another lane's validated tip, or of an anchor SHA, does not.
- **Files**: `tests/consolidation/test_approved_bound.py`.

### Subtask T011 – Reconcile the tests that pinned the old premise

- **Purpose**: keep the suite honest without weakening it.
- **Steps**:
  1. `tests/consolidation/test_reconciliation.py::test_mixed_lane_wiring_non_mixed_lane_never_reads_events` pins "a non-mixed lane never reads events". Rewrite it to pin the new bound: a claim reads the event log exactly once (this is the NFR-001 test; count the reads through the same seam the old test used). Out-of-map edit (WP01 owns the file); record the rationale.
  2. `test_build_claim_sources_shas_from_lane_tips` stays true (the collectors still read the tips); leave it. T006 and T010 already pin the refusing side.
  3. Run `tests/consolidation/test_canceled_content_residuals.py`. The four strict xfails and the two "outside windows" wording tests (near lines 378 and 450 at grounding time) must keep their state, because on a mixed lane the existing refusals fire first and a canceled work package's latest stamp is a covered point. If one flips, stop and decide: either the rule is wrong (fix `check_lane`), or the flip is correct; in the second case change the marker, write the reason in the test's docstring and in the Activity Log.
  4. Tests that move a lane after a builder approved it. WP01 found about thirty (its hand-back lists them): in `tests/terminus/` the tests that call `plant_canceled_commit` or edit a lane after the builder returns (`test_repro_4945`, `test_repro_4977`, `test_repro_4981`, `test_repro_5001_bookkeeping_overexclusion`, `test_repro_5022`, `test_repro_5038`, `test_resume_phantom_only`, `test_rollback_restores_refs`, `test_terminus_reconciliation_property`, `test_claim_refusal_before_mutation`, `test_fixture_mixed_lane_canceled`), `tests/consolidation/test_executor_terminus_integrity.py::test_squash_axis_attributes_on_real_coord_production_merge`, and thirteen tests in `tests/consolidation/test_reconciliation.py` whose callers add the edit commits after `_build_shared_file_lanes` (and similar) returned. Two files still hand-build unstamped approvals with `_approve_events` and run a real consolidate: `tests/terminus/test_consolidate_preserves_local_files.py`, `tests/terminus/test_protected_target_preflight.py`.
     - Run the two directories first and work from the actual failures, not from the list.
     - Fix them centrally: add ONE helper next to the builders (`tests/terminus/conftest.py`, and the equivalent in `test_reconciliation.py`) that re-records the lifecycle stamps of the lane-mapped work packages at the lanes' current tips (the truthful statement "this is what was reviewed"), and call it in each affected test after the lane-moving step, or inside the shared lane-moving helper (`plant_canceled_commit` and friends) when every caller needs it. Where a test's subject is exactly "content arrived after approval" (it expects a refusal or a FAIL), do not restamp: check that it still gets its existing verdict, because on a mixed lane the existing refusals fire first.
     - Never weaken the product rule, never add a product switch, never mark a test xfail or skip to get through.
     - These are out-of-map edits in test files (WP01 owns the builders, the test files are unowned); record them in the Activity Log. If, after the central helper, more than fifteen individual test functions still need hand edits, stop and hand back with the list.
  5. Run `tests/consolidation/test_canceled_content_benchmark.py`; it must stay within its budget.
- **Files**: `tests/consolidation/test_reconciliation.py` (out-of-map), `tests/consolidation/test_canceled_content_residuals.py` (only if a marker changes).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/terminus/test_post_approval_commit_refused.py tests/consolidation/test_approved_bound.py -q
.venv/bin/python -m pytest tests/consolidation tests/terminus -q -n auto --dist loadfile -p no:cacheprovider
.venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_claim_integrity_refusal.py tests/consolidation/test_refuse_restores_target.py tests/status/test_lane_head.py -q
.venv/bin/python -m pytest tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_coord_read_residuals_closeout.py tests/architectural/test_exemption_registry_ratchet.py -q
uv run --frozen mypy --strict src/specify_cli/consolidation/approved_bound.py src/specify_cli/consolidation/reconciliation.py   # or the repository's configured mypy command
```

Record every command with its passed, failed and xfailed counts in the Activity Log.

## Risks & Mitigations

- **False refusal on `--resume`.** The tool merges the mission branch into a stale lane during consolidation. Those are merge commits whose content is reachable from the mission branch anchor. Covered by a T010 case; if a terminus resume test goes red, look there first.
- **Mixed lanes.** Do not let the new check report a canceled work package's commits. If an existing mixed-lane test changes verdict or wording, the covered-points rule is wrong.
- **Tests that commit after approval.** Many terminus tests may add lane content after the builder approved. Fix the fixture use, not the rule.
- **Cold import.** `reconciliation.py` is import-light; import `approved_bound` the way sibling consolidation modules are imported there and re-run the cold-import gate.

## Review Guidance

- The first commit of the lane is the red test, and the Activity Log shows it failing for the right reason (exit 0, late file on the target).
- The refusal fires before the snapshot: target, mission and coordination branches are at their pre-run tips, and `test_single_rollback_authority.py` is untouched.
- `approval_stamp` never falls back to the lane tip or to the `done` stamp.
- No existing refusal text changed (`git diff` on the string literals of `reconciliation.py` and `wp_attribution.py`).
- The #5330 xfails kept their state, or a flip carries a written reason.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
