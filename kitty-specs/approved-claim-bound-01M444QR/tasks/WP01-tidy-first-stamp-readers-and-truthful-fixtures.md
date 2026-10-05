---
work_package_id: WP01
title: 'Tidy-first: stamp readers and truthful approval fixtures'
dependencies: []
requirement_refs:
- FR-014
- C-007
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T19:27:00.255765+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Enablers
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/wp_attribution.py
- src/specify_cli/consolidation/canceled_attestation.py
- tests/terminus/conftest.py
- tests/terminus/lanes_fixture.py
- tests/consolidation/test_reconciliation.py
- tests/consolidation/_divergent_shapes.py
- tests/consolidation/test_approved_content_presence.py
- tests/consolidation/test_executor_phase_boundary.py
- tests/consolidation/test_canceled_content_benchmark.py
- tests/consolidation/test_canceled_dependency_lane.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Tidy-first: stamp readers and truthful approval fixtures

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

Behaviour-preserving preparation (DIRECTIVE_025, tidy-first). No product behaviour changes in this work package.

- The two stamp readers in `wp_attribution.py` are public and are the only code that reads `policy_metadata["lane_head"]` on the consolidation side.
- The shared consolidation test fixtures record approvals **after** the lane commits exist, each with the real lane tip as its `lane_head` stamp. A test can now express "a commit made after approval".
- `tests/consolidation/` and `tests/terminus/` pass before and after, with the same counts except for the one test deleted in T005.

Implementation command: `.venv/bin/spec-kitty agent action implement WP01 --agent implementer --mission approved-claim-bound-01M444QR`

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

### Subtask T001 – Make the stamp readers public

- **Purpose**: the approved-bound resolver (WP02) must reuse the existing readers, not copy them (charter: single canonical authority).
- **Steps**:
  1. In `src/specify_cli/consolidation/wp_attribution.py` rename `_stamp_of` to `stamp_of` and `_is_migration_event` to `is_migration_event`. Update every use in the module.
  2. Rename `_lane_exempt_commits` to `lane_exempt_commits` the same way (WP02 reuses it). `tests/consolidation/test_canceled_dependency_lane.py` imports the private name: update that import.
  3. Add the three names to `__all__`. Give `stamp_of` a one-line docstring: it returns the `lane_head` stamp of one event, or `None`.
  4. Search for other users of the private names: `grep -rn "_stamp_of\|_is_migration_event\|_lane_exempt_commits" src tests`. Update them.
- **Files**: `src/specify_cli/consolidation/wp_attribution.py`.
- **Notes**: no logic change. If `tests/architectural/test_no_dead_symbols.py` covers this package, T002 gives `stamp_of` and `is_migration_event` their `src/` callers. Check `tests/architectural/dead_symbol_allowlist.yaml` is not needed.

### Subtask T002 – Fold the inline stamp read in `canceled_attestation.py`

- **Purpose**: `attestation_stamps` reads `policy_metadata.get(LANE_HEAD_KEY)` inline and repeats the migration-actor test. That is a second reader.
- **Steps**:
  1. In `attestation_stamps` replace the inline read with `stamp_of(event)`.
  2. Replace both `actor_identity_str(event.actor).startswith(MIGRATION_ACTOR_PREFIX)` expressions (in `is_canceled_superseded_attestation` and `attestation_stamps`) with `is_migration_event(event)`.
  3. Remove imports that became unused.
  4. `ATTESTATION_KEY` is defined in this module but is not in `__all__`. Add it to `__all__` (WP02 imports it; one definition of the key).
- **Files**: `src/specify_cli/consolidation/canceled_attestation.py`.
- **Validation**: `tests/consolidation/test_canceled_attestation.py` and `tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py` pass unchanged.

### Subtask T003 – Restamp the terminus fixtures

- **Purpose**: the builders write the approval log before any lane commit exists and with no `policy_metadata` (`tests/terminus/conftest.py`, `_approve_events` and its call sites in `build_coord_mission`, `build_coord_mission_mixed_lane`, `build_coord_mission_shared_file`; `tests/terminus/lanes_fixture.py::build_lanes_mission`). After WP02 an unstamped approval refuses, so about 35 test files would break.
- **Steps**:
  1. Read how the already-stamped builders do it: `build_coord_mission_mixed_lane_canceled` in `conftest.py` and `_stamped` in `lanes_fixture.py`.
  2. Reorder each unstamped builder so the approval events are written after the lane branches and their commits exist, and give every lifecycle event of a lane-mapped work package `policy_metadata={"lane_head": <real tip of its lane at that moment>}`. For a lane with several work packages, stamp each approval with the lane tip that exists when that work package's content has been committed.
  3. Keep the builders' public signatures and return values. Tests that call them must not need edits.
  4. `tests/terminus/canceled_dependency_support.py::strip_lane_head_stamps` stays the single explicit way to build an unstamped mission. Do not add a "stamped=False" switch to the builders.
  5. Update the docstring of `approved_shas_from_lane_tips`: say that it reads the lane tips, and that this equals the approved content only because the product refuses a lane that moved after approval.
- **Files**: `tests/terminus/conftest.py`, `tests/terminus/lanes_fixture.py`.
- **Notes**: where the coordination branch holds the status log, the events must still be committed where the builders commit them today; only the order and the stamps change. Some tests add lane commits after calling the builder (for example the squash content tests). List those you find in the Activity Log: after WP02 they are post-approval commits, and WP02 decides per test whether the test must approve again or is asserting a refusal.

### Subtask T004 – Restamp the consolidation unit-test builders

- **Purpose**: same as T003 for `tests/consolidation/`.
- **Steps**:
  1. `tests/consolidation/test_reconciliation.py`: `_event` and `_build_mission`, `_build_mixed_lane_mission`, `_build_shared_file_lanes`. Write the approval events after the lane commits, stamped with the real tips.
  2. Check each of `_divergent_shapes.py`, `test_approved_content_presence.py`, `test_executor_phase_boundary.py`, `test_canceled_content_benchmark.py`: does it build a real claim through `build_approved_wp_set` with unstamped approvals? If yes, restamp it the same way. If it stubs the claim, leave it and say so in the Activity Log.
  3. Also check, and record what you found: `test_executor_terminus_integrity.py`, `test_refuse_restores_target.py`, `test_claim_integrity_refusal.py`, `tests/integration/test_merge_cluster_coord_read.py`, `tests/cli/commands/test_merge_strategy.py`. If one builds a real claim from unstamped approvals, restamp it (out-of-map edit, one-line rationale in the Activity Log).
- **Files**: the files above.

### Subtask T005 – Remove the self-comparison test and prove the suite is unchanged

- **Purpose**: `test_reconciliation.py` has a test (near line 2675 at grounding time) that compares the claim to the collectors it is built from. It can never fail. Remove it.
- **Steps**:
  1. Before any edit, record the baseline: `.venv/bin/python -m pytest tests/consolidation tests/terminus -q -n auto --dist loadfile -p no:cacheprovider` (counts of passed, failed, xfailed, skipped).
  2. Delete the self-comparison test. Do not touch the "claim equals the lane tips" test or the "non-mixed lane never reads events" test: WP02 owns those decisions.
  3. Re-run the same command. The counts must match the baseline minus the one deleted test. Record both runs in the Activity Log.
- **Files**: `tests/consolidation/test_reconciliation.py`.

## Test Strategy

- Baseline and final run of `tests/consolidation tests/terminus` (command in T005).
- `.venv/bin/python -m pytest tests/status/test_lane_head.py tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py -q`.
- No new test is added by this work package.

## Risks & Mitigations

- **A builder reorder changes what a test asserts.** Mitigation: signatures and return values stay; run the two directories before and after.
- **A baseline red that is not yours.** Classify it per the CLAUDE.md baseline-red gotcha (run it on `issue-5668-approved-claim-bound` without your change) and record it; do not fix it here.
- **Hidden unstamped builders.** `grep -rn "to_lane.*approved\|\"approved\"" tests/consolidation tests/terminus | grep -v lane_head` helps find hand-built approval events.

## Review Guidance

- No file under `src/` changes behaviour: the diff there is three renames, one fold and one `__all__` entry.
- Every restamped builder stamps the real lane tip, taken from git, never a constant.
- No builder gained a switch that produces unstamped approvals.
- The before and after test counts are in the Activity Log.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
