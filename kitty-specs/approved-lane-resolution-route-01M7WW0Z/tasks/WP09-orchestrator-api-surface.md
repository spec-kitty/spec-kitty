---
work_package_id: WP09
title: orchestrator-api surface
dependencies:
- WP05
- WP07
requirement_refs:
- FR-004
- FR-001
- C-007
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: b61f303b619e61b5d05dcaf0f804b202b895cff8
created_at: '2026-11-25T17:36:26.986099+00:00'
subtasks:
- T044
- T045
- T046
phase: Phase 3 - Surfaces and proof
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent:
- tests/orchestrator_api/test_consolidate_mission_resolution_merge.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/orchestrator_api/envelope.py
- tests/orchestrator_api/test_consolidate_mission_resolution_merge.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
- docs/api/orchestrator-api.md
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 - orchestrator-api surface

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

`orchestrator-api consolidate-mission` carries the two new behaviours of this Mission through its existing doors, with its contract bumped:

1. **FR-004 / C-007**: an unreviewed resolution merge on an approved code lane is refused before the first lane is consolidated, with the `PREFLIGHT_FAILED` envelope, `data.preflight_error_code == "RESOLUTION_MERGE_UNREVIEWED"` (when it is the first code) and the code in `data.preflight_error_codes`. No branch moves. `CONTRACT_VERSION` goes from `1.29.0` to `1.30.0`, with a changelog comment in `envelope.py` in the existing style.
2. **FR-001 (C-006 one renderer)**: when a lane is stale during `consolidate-mission`, the remedy text in `data.errors` is the approved-lane route WP07 renders (send back, `implement --incorporate <sibling>`, resolve, for_review, independent approval, re-run), because this caller passes `approved_wp_ids` (and the sibling lanes where known) into `consolidate_lane_into_mission`.

Done means: envelope tests for the new code and version, a stale-remedy text test via the orchestrator path, no change for missions without these shapes, and the user-facing contract page (`docs/api/orchestrator-api.md`: version line, 1.30.0 history bullet, `RESOLUTION_MERGE_UNREVIEWED` preflight row) and the operator-skill contract reference updated, with a test that the page's version line equals `CONTRACT_VERSION`, and `tests/specify_cli/orchestrator_api/test_contract_version.py` re-pinned to 1.30.0.

## Context & Constraints

Read before coding:

- `.kittify/charter/charter.md`, then `spec-kitty charter context --action implement`.
- `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (FR-001, FR-004, C-006, C-007, Edge Case "orchestrator-api consolidate-mission"), `research.md` (R-10), `contracts/refusal-codes.md` (orchestrator section), `contracts/stale-remedy.md`.
- WP05's landed code: `BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED` and its placement inside `_approved_bound_verdict`, which `approved_bound_refusal` (`src/specify_cli/consolidation/reconciliation_bound.py:403-446`) already calls. So the refusal reaches this path with no new call.
- WP07's landed code: the new keyword arguments of `lanes/consolidation.consolidate_lane_into_mission` (`approved_wp_ids: frozenset[str] | None = None`, `done_wp_ids`, `sibling_candidates: Sequence[SiblingCandidate] = ()`) and the one public sibling helper `lanes.consolidation.sibling_candidates_before(...)` (WP07 Context). Read the landed signatures before T045.

Integrity invariants:

- **C-002**: `consolidate-mission` has no attestation flag (unchanged). Do not add one, and do not soften the refusal.
- **C-006**: one renderer for the stale remedy (`lanes/stale_check`), one bound verdict (`approved_bound_refusal`), one code extractor (`approved_bound.refusal_codes`). No second wording in this module.
- **C-007**: a new refusal code on `orchestrator-api` bumps the contract version and is listed in its documented preflight codes.
- **Fail closed (NFR-002)**: a git probe error during the bound check (for example git < 2.36 for the remerge probe) must not let the lanes merge. Today `GitProbeError` is a `RuntimeError` and `consolidate_mission` envelopes it as a failure (`orchestrator_api/consolidation.py:1109`, `except RuntimeError as exc`); keep that, and add a test.
- This path has **no rollback door** (#5722): every refusal must happen before the first `consolidate_lane_into_mission` call. The new code satisfies that because the bound check runs in `_refuse_post_approval_lane_content` (`:755`), before the lane loop (`:790-796`).

Current code (HEAD of the planning base), `src/specify_cli/orchestrator_api/consolidation.py`:

- `ApprovedBoundRefused` (`:103-110`), a `CodedPreflightRefused`, enveloped as `PREFLIGHT_FAILED` with `error_code` / `error_codes`.
- `_orchestrator_refusal_text` (`:569-579`): adds the "no attestation flag" note only when the text names `--attest-approved-reviewed`. The new code's text does not, so no note.
- `_refuse_post_approval_lane_content` (`:582-618`): calls `approved_bound_refusal(..., coord_base_ref=target_tip, excluded_window_base=target_tip)` and `refusal_codes(refusal)`. `refusal_codes` iterates `BoundRefusalCode` (`approved_bound.py:204-212`), so the new member is extracted with no edit here.
- `_execute_lane_merge` (`:672-820`): computes `excluded_canceled_wp_ids` (`:742`), runs the merge gates, the bound refusal (`:755`), captures `lane_tips = _lane_tips(...)` (`:757`, pre-mutation lane tips), then loops lanes calling `consolidate_lane_into_mission(main_repo_root, mission_slug, lane.lane_id, lanes_manifest)` (`:793`) and raises `RuntimeError("; ".join(lane_result.errors))` on failure (`:794-795`). The stale remedy reaches the envelope through those errors (`lanes/consolidation.py:342-349`: `"Lane <id> is stale: overlapping files [...]. <remediation>"`).
- `_follow_own_auto_rebase` (`:423-437`) follows this call's own auto-rebase move for the cleanup; WP02's record makes those merges recognisable to WP05 on a later run. No change here.

`src/specify_cli/orchestrator_api/envelope.py`: the version history comment block ends with 1.29.0 (`:223-229`); `CONTRACT_VERSION = "1.29.0"` (`:230`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on fix/approved-lane-resolution-route; completed changes must merge back into fix/approved-lane-resolution-route.
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP09 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T044 - Red envelope tests

- **Purpose**: pin the orchestrator surface of FR-004 and FR-001 through the real `spec-kitty orchestrator-api` CLI over real git.
- **Files**: `tests/orchestrator_api/test_consolidate_mission_resolution_merge.py` (new).
- **Model**: copy the harness of `tests/orchestrator_api/test_consolidate_mission_post_approval.py` (`_consolidate_mission`, `_envelope`, `_build` for `"lanes"` and `"coord"`, `ref_shas`, `flat`, `blob_present_at`). Do not edit that file.
- **Fixture for FR-004**: `build_post_approval_coord_mission` / `build_post_approval_lanes_mission` (`tests/terminus/post_approval_support.py`), then add a hand merge with own content on lane-a: the shape of `_add_evil_merge` in `tests/consolidation/test_approved_bound_residuals.py:41-56` (a `commit-tree` merge of the lane tip and the Mission branch tip whose tree adds `LATE_PATH`). Copy the few lines into your test module (that test module is WP05's; do not import a private helper from it).
- **Tests (red at base: the code and version do not exist)**:
  1. `test_unreviewed_resolution_merge_is_refused_before_any_lane_merges[lanes|coord]`: assert `returncode != 0`, `envelope["success"] is False`, `envelope["error_code"] == "PREFLIGHT_FAILED"`, `data["preflight_error_code"] == "RESOLUTION_MERGE_UNREVIEWED"`, the code in `data["preflight_error_codes"]`, the merge's short SHA in `data["errors"]`, no "no attestation flag" note, `ref_shas(mission)` unchanged, `LATE_PATH` absent from the target and the Mission branch.
  2. `test_contract_version_is_1_30_0`: `orchestrator-api contract-version` reports `1.30.0` (and `envelope.CONTRACT_VERSION == "1.30.0"`). The existing tests that read `CONTRACT_VERSION` symbolically (`tests/agent/test_envelope_unit.py`, `tests/agent/test_orchestrator_commands_integration.py:383`) must stay green.
  3. `test_two_codes_keep_first_code_first`: a mission with a `LANE_MOVED_AFTER_APPROVAL` commit on lane-b and an unreviewed merge on lane-a: `preflight_error_codes` lists both, and `preflight_error_code` is the first one the text names (WP05 renders the new block last; assert the order you observe and that it equals `refusal_codes(text)`).
  4. `test_probe_error_does_not_merge`: monkeypatching is not possible across a subprocess; instead run in-process through the Typer app if a harness exists (`tests/consolidation/characterization_support.run_in_process` runs `spec-kitty` in process), or call `_refuse_post_approval_lane_content` directly with `merge_own_changed_paths` patched to raise `GitProbeError`. Assert an exception (no return) and no ref moved.
  5. `test_control_clean_merge_consolidates`: a merge with no own content (merge the Mission branch tip with no edit) is not refused by the new code; the mission consolidates (or, if it fails for an unrelated reason, the envelope does not carry the new code).
  6. Stale remedy (FR-001) tests: see T045.
- **Validation**: record the red output (codes seen, version) in the WP history.

### Subtask T045 - Pass `approved_wp_ids` (and siblings where known) into `consolidate_lane_into_mission`

- **Purpose**: one stale-remedy renderer for both callers (C-006). Without `approved_wp_ids` the renderer keeps today's text, which tells the operator to run `agent action implement <WP>` alone; that command refuses an approved work package (#7754).
- **Files**: `src/specify_cli/orchestrator_api/consolidation.py`.
- **Steps**:
  1. Compute the approved work packages once, before the lane loop: the work packages of non-fully-canceled lanes whose reduced status lane is `approved` or `done`, excluding `excluded_canceled_wp_ids`. Use the same reader the claim uses: `materialize_snapshot(mission_dir).work_packages` and the membership set `_APPROVED_MEMBERSHIP_LANES` (`consolidation/reconciliation_kernel.py`). If that set is private, read it through the public module WP05/WP07 use (check the landed `phase_advance` derivation from `run.approved_wp_set` for the canonical rule and mirror its meaning, not its code). Do not invent a third definition of "approved".
  2. Siblings: call WP07's public helper `specify_cli.lanes.consolidation.sibling_candidates_before(lanes_manifest, lane.lane_id, integrated_lane_ids=<lanes already consolidated or skipped as integrated in this call>, pre_run_tips=<lane_tips keyed by lane branch>)` (WP07 Context fixes this name and signature; this path has the pre-run tips in `lane_tips`, `:757`), and pass the result as `sibling_candidates=`. Do not re-implement the order or filter here. If the landed name or signature differs from WP07's prompt, stop and report to the runner (WP07 owns it) rather than writing a local copy.
  3. Pass the values as keyword arguments to `consolidate_lane_into_mission` at `:793`. Keep the call order and the `lane_fully_canceled` skip unchanged.
  4. Keep `_execute_lane_merge` at complexity <= 15: extract `_approved_wp_ids_for_remedy(...)` (and `_sibling_lanes_for(...)` if needed), each with a direct unit test.
- **Tests (red first)**:
  - Unit: spy on `consolidate_lane_into_mission` (monkeypatch the name this module imports) and assert it receives `approved_wp_ids` equal to the approved, non-canceled work packages; a canceled work package is never passed.
  - Integration: a two-lane Mission where both approved lanes edit adjacent hunks of one shared file, so the second lane is stale and its auto-rebase conflicts. Prefer the fixture builder WP07 landed (for example in `tests/lanes/` or a terminus support module); if none is importable without editing another WP's file, build a minimal one in your test module with `build_post_approval_lanes_mission` plus two conflicting commits (assert the conflict as a fixture precondition, `git merge-tree --write-tree` exits 1). Assert the envelope's `data.errors` contains `move-task <WP> --to in_progress`, `--incorporate`, the sibling lane id (when siblings are passed), and does NOT contain `git merge` or `cd .worktrees` (the #7285 A-10 rule), nor a bare `agent action implement <WP>` without `--incorporate`.
  - Control: with `approved_wp_ids` empty (a planning-only path never reaches this loop; simulate by calling the renderer with `None`), today's text is unchanged. WP07 owns the renderer test; here assert only that this caller passes non-empty ids for approved lanes.
- **Note**: this path has no rollback; earlier lanes stay consolidated into the Mission branch when a later lane is stale, so the sibling content is still on the Mission branch. The remedy is still the re-review route (C-006: same text). Re-running is `orchestrator-api consolidate-mission` for an orchestrator; the shared remedy names `spec-kitty consolidate`; do not fork the wording here, record the observation for WP13.

### Subtask T046 - Bump the contract version and list the code

- **Purpose**: C-007.
- **Files**: `src/specify_cli/orchestrator_api/envelope.py`; the code list in `src/specify_cli/orchestrator_api/consolidation.py` docstrings where codes are enumerated (`_refuse_post_approval_lane_content`, `:582-590`).
- **Steps**:
  1. Add a `# 1.30.0:` comment block after the 1.29.0 block (`envelope.py:223-229`) in the same style: what can newly refuse (`consolidate-mission` before it consolidates any lane, when a merge on an approved code lane carries its own content and no review approval of the lane reaches it, #5604), the envelope (`PREFLIGHT_FAILED`, `data.preflight_error_code` / `preflight_error_codes` = `RESOLUTION_MERGE_UNREVIEWED`), why a minor bump (a call that answered `success: true` now refuses; no field or `error_code` removed or renamed). Mention that the stale-lane failure text changed for approved lanes (text only, no new field).
  2. Set `CONTRACT_VERSION = "1.30.0"`.
  3. Update the `_refuse_post_approval_lane_content` docstring to list the codes it can carry.
  4. **REQUIRED: the user-facing contract page** `docs/api/orchestrator-api.md` (owned by this WP): change the version line `CONTRACT_VERSION: 1.29.0` (`:34`) to `1.30.0`; add a 1.30.0 bullet to the version history list (`:273` region) in the house style (what newly refuses, the envelope, why a minor bump, the approved-lane stale text change); add a `RESOLUTION_MERGE_UNREVIEWED` row to the preflight code table (`:1185-1196` region) with its meaning and remedy (send back, incorporate/resolve, independent re-review, re-run).
  5. **REQUIRED: the operator-skill contract reference** `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` (owned by this WP): add the `RESOLUTION_MERGE_UNREVIEWED` row in the preflight/evidence code table (`:340-365` region) with its contract version (1.30.0), and update any current-version line it carries. Editing `src/charter/offering/` means running `tests/architectural/test_no_legacy_terminology.py` (CLAUDE.md), which is in the Test Strategy.
  6. **Re-pin the hard-coded version test** `tests/specify_cli/orchestrator_api/test_contract_version.py` (owned by this WP): `test_contract_version_response_reports_the_current_contract_version` (`:91-97`) asserts `"1.29.0"` literally for `api_version` and `contract_version`; the bump turns it red. Re-pin both literals to `"1.30.0"` (Standing Order 5: re-pin, never delete; keep the literal so the test still catches an accidental bump). This directory is in the per-PR matrix.
- **Tests**:
  - `test_contract_version_is_1_30_0` (T044 #2) is the red test for this subtask.
  - Grep for literal version strings before and after the bump: `grep -rn "1\.29\.0" src tests --include="*.py"`. Only comments and docstrings that describe history may keep `1.29.0` (for example `tests/terminus/test_consolidate_skip_worktree_checkout.py:11,74`). The one known test that hard-codes the current version is `tests/specify_cli/orchestrator_api/test_contract_version.py:97-98` (re-pinned in step 6). Any other hard-coded current-version assertion found by the grep: stop and report it to the runner (it is out of map).
  - `test_doc_contract_version_matches_envelope` (new, in `tests/orchestrator_api/test_consolidate_mission_resolution_merge.py`): read `docs/api/orchestrator-api.md`, extract the version from the `CONTRACT_VERSION` line under "## Contract Version" with a regex, and assert it equals `envelope.CONTRACT_VERSION`; also assert the page names `RESOLUTION_MERGE_UNREVIEWED` and contains a `1.30.0` history entry. Red at the base (the page says 1.29.0 and has no row). This makes the doc edit non-skippable.
  - `orchestrator-api contract-version --provider-version 0.1.0` still succeeds (`MIN_PROVIDER_VERSION` unchanged).
- **Edge cases**:
  - Only one bump for this Mission. WP07's stale-text change rides on the same 1.30.0 entry (text only); do not bump twice.
  - If another Mission bumped the version on the planning base before you land (rebase conflict on `CONTRACT_VERSION`), take the next minor after the base's value and record it; never reuse a version number.
- **Validation**: `uv run --frozen pytest tests/contract/test_orchestrator_api.py -q` (the error-code prose guard reads only the anchored `error_code` region, not preflight sub-codes; it must stay green), plus `tests/agent/test_envelope_unit.py`, `tests/specify_cli/orchestrator_api/test_contract_version.py` (re-pinned, green) and the new doc-version test.
- **Definition of Done for T046** (all required): `CONTRACT_VERSION == "1.30.0"` with its history comment; `docs/api/orchestrator-api.md` version line, 1.30.0 history bullet and `RESOLUTION_MERGE_UNREVIEWED` preflight row; the operator-skill contract reference row; `test_contract_version.py` re-pinned; the doc-version test green.

## Binding scope ruling (operator, 2026-11-25, DM-01M88RZDBP57ZTYJHC5NP0ZH4R; rebase ruling DM-01M88RZ308V571DYGPKD17ZWDA). It supersedes the conflicting steps above.

- **No sibling helper.** WP07 adds no `sibling_candidates_before`, no `SiblingCandidate` and no new sibling keywords on `consolidate_lane_into_mission`.
  - The orchestrator path (`orchestrator_api/consolidation.py:794`) already gets main's #7755 sibling naming, and WP07's `--incorporate` refresh step, through `consolidate_lane_into_mission` -> `_explain_stale`. Do not compute or pass siblings here.
  - The stale-remedy text test through the orchestrator path asserts the same lines as the CLI path (C-006: one renderer).
- **Contract version.** After the rebase, main's `CONTRACT_VERSION` is already `1.30.0`, so this WP bumps it to `1.31.0`, not `1.30.0`. Every `1.30.0` in this prompt's version steps means `1.31.0`:
  - the `# 1.31.0:` comment block after main's 1.30.0 block;
  - the docs page version line and its history bullet;
  - the operator-skill reference;
  - `test_contract_version_is_1_31_0`;
  - the re-pin of `test_contract_version.py`;
  - the docs-equals-envelope test.

  Read the value from the base first. If it is not `1.30.0`, stop and report.

## Test Strategy

```bash
uv run --frozen pytest tests/orchestrator_api/test_consolidate_mission_resolution_merge.py -q
# blast radius of orchestrator_api/consolidation.py and envelope.py
uv run --frozen pytest tests/orchestrator_api/ -q
uv run --frozen pytest tests/agent/test_envelope_unit.py tests/contract/test_orchestrator_api.py tests/specify_cli/orchestrator_api/ -q
uv run --frozen pytest tests/agent/test_orchestrator_commands_integration.py -q -k "contract or version"
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

Quality gates (zero findings, no new suppressions, complexity <= 15):

```bash
uv run --frozen ruff check src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/orchestrator_api/envelope.py tests/orchestrator_api/test_consolidate_mission_resolution_merge.py tests/specify_cli/orchestrator_api/test_contract_version.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/orchestrator_api/envelope.py tests/orchestrator_api/test_consolidate_mission_resolution_merge.py tests/specify_cli/orchestrator_api/test_contract_version.py
uv run --frozen mypy src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/orchestrator_api/envelope.py tests/orchestrator_api/test_consolidate_mission_resolution_merge.py
```

Tracer notes: record friction, approach and design notes with `spec-kitty agent tasks add-history WP09 --note "<trace: ...>" --mission approved-lane-resolution-route-01M7WW0Z`. This code WP cannot own `kitty-specs/traces/`.

## Risks & Mitigations

- **A refusal after the first lane merge** would strand a half-consolidated Mission (no rollback door). Mitigation: the code comes only from the pre-loop bound check; test 1 asserts `ref_shas` unchanged.
- **A second definition of "approved"** for the remedy. Mitigation: reuse the claim's membership rule; unit test with a canceled work package.
- **Sibling naming unavailable** on this path. Mitigation: pass what is known; record the gap; the remedy still prints the route with the send-back and re-run steps.
- **Contract drift in docs**: the page and the skill reference are owned here and their edits are required (T046 steps 4-5); the doc-version test pins the version line to `CONTRACT_VERSION`.
- **Version-sensitive tests elsewhere**: grep `1.29.0` across `tests/` and `src/` before and after; only symbolic uses should remain.

## Review Guidance

- Envelope shape: `PREFLIGHT_FAILED`, `preflight_error_code(s)`, no attestation note, no ref moved (renata MEDIUM on FR-004: orchestrator-api acceptance scenario).
- `CONTRACT_VERSION` is `1.30.0`, with a history comment in the house style (C-007; daphne MEDIUM 8).
- The stale remedy via this path is the approved-lane route: assert the presence of each command, not just "no forbidden text" (renata MEDIUM on FR-001: zero commands must not pass).
- No `git merge`, no `cd .worktrees`, no bare `implement <WP>` for an approved lane (A-10 kept).
- No new attestation flag; no second wording; no edit outside the owned files.
- The doc page's version line, 1.30.0 history bullet and `RESOLUTION_MERGE_UNREVIEWED` row, and the skill reference row, are present; the doc-version test passes; `test_contract_version.py` is re-pinned (not deleted).
- Siblings come from WP07's `sibling_candidates_before`, not a local copy.
- Ruff, format (`--force-exclude`) and mypy clean on owned files.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) - never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
