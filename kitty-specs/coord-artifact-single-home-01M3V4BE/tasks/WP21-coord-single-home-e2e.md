---
work_package_id: WP21
title: End-to-end single-home invariant over the coordination workflow
dependencies:
- WP06
- WP16
- WP17
- WP18
- WP19
- WP20
requirement_refs:
- FR-015
- SC-001
- SC-002
- NFR-002
- FR-009b
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-02T17:15:09.755464+00:00'
subtasks:
- T111
- T112
- T113
- T114
- T119
phase: Phase 7 - Gates and end-to-end
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/test_coord_single_home_workflow.py
create_intent:
- tests/integration/test_coord_single_home_workflow.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/integration/test_coord_single_home_workflow.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP21 – End-to-end single-home invariant over the coordination workflow

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Deliver ONE end-to-end test file proving the single-home invariant across a whole coordination-routed Mission lifecycle (FR-015, SC-001, SC-002). The run covers both coordination topologies and includes a moved-merge-base variant that reproduces #5440's headline consolidation symptom.

Done means `tests/integration/test_coord_single_home_workflow.py`:

- Drives the **production CLI** through: create → `agent decision open`/`resolve` → tracer append → `spec-commit` → `setup-plan` → `finalize-tasks` → `agent action implement WP01` → `move-task` to approved → `accept` → `consolidate`.
- Is parametrized over `coord` and `lanes_with_coord`, created through the production create path.
- Asserts, before consolidation:
  - **0 commits** in `creation_base..target` touch a COORD-partition path of the Mission;
  - **exactly 1** status log;
  - **every decision present**;
  - a **strictly increasing logical clock**;
  - **no event id twice** in one log (NFR-002).
- Asserts that **consolidation succeeds**, in both the linear variant and the moved-merge-base variant, with no `TARGET_BRANCH_CONTENT_CONFLICT`.
- Is green on this WP's final commit, and was run locally **as this single file only**, with the command, duration and counts recorded for the PR.

This WP writes tests only. If the e2e exposes a product defect, it is reported to the owning WP's lane, not patched here.

## Context & Constraints

- **Spec**:
  - FR-015 (the e2e invariant, both topologies, moved-merge-base variant);
  - SC-001 (0 COORD commits on the target before consolidation, and consolidation succeeds);
  - SC-002 (1 status log with 100% of decision events, clock never restarts);
  - NFR-002 (zero record loss, no duplicate id);
  - C-006 (no heavy suites locally; integration is CI-owned);
  - Assumptions: the linear `TARGET_BRANCH_CONTENT_CONFLICT` did not reproduce, so the moved-merge-base variant is the closest reproduction.
- **Plan**: IC-16. It depends on IC-03 through IC-12 and on IC-18. It is the only e2e file, run alone, never the e2e directory.
- **Research**: D19 (scope and assertions), D20 (the remote-only refusal is out of this flow), D21 (consolidation now materializes or seeds in its unlocked pre-phase).
- **Data model**: §1 (the partition table: which paths are COORD; `decisions/DM-*.md` and `index.json` are PRIMARY after WP12) and §6 (the lifecycle).
- **Reference tests to model on** (read their setup, do not copy blindly):
  - `tests/integration/test_coord_unprotected_lifecycle_loop.py` (CLI-driven coord lifecycle; `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`);
  - `tests/integration/test_accept_matrix_coord_partition.py`;
  - `tests/integration/coord_topology_fixture.py`.
  - WP02's factory `tests/_factories/coord_mission.py` provides `make_coord_mission` and the probes `event_ids`, `lamports`, `commits_touching` and `coord_tree_has`.
- **Important topology finding** (verified in `test_coord_unprotected_lifecycle_loop.py`'s docstring and `cli/commands/agent/mission_create.py::_resolve_default_topology_phase`): `--pr-bound` on an **unprotected** primary branch **defaults to `lanes`**, not `coord`. So the `coord` parametrization must pass `--topology coord` explicitly together with `--pr-bound --start-branch <topic>`, exactly as research.md's NFR-001 bench commands do. Alternatively, set the primary up as protected; then only `--pr-bound --start-branch` is needed. Either way, **assert `meta.json`'s `topology` equals the requested value** before anything else, or the whole test could pass vacuously on a `lanes` Mission.
- **Charter**: load `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`. Relevant rules: ATDD / live evidence (Standing Order 4) and no heavy suites (Agent Operating Discipline).
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: say Mission, never feature. Here `consolidate` is **local lane consolidation** into the local target branch. It is never a publish to origin; never push.
- **Brownfield scout (binding read)**: before coding, read `## WP21` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP21 --agent claude`. Consume the resolved workspace path.
- This WP owns one new file and shares nothing, so it gets its own lane. Its base stacks every functional lane through its dependencies; the transitive closure covers WP01-WP20.
- **Stale-install note**: the test shells out to `spec-kitty` (`merge-driver-*`, CLI subprocesses). Inside the lane worktree, ensure the CLI under test is that worktree's code (`uv run --frozen spec-kitty ...`, or invoke `python -m specify_cli` from the worktree venv). Otherwise you test a stale install (CLAUDE.md gotcha 3).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T111 – Scaffold the e2e file: markers, CLI driver, parametrization, creation base

- **Purpose**: A reliable harness, so that T112/T113 assertions are about the invariant, not about fixture flakiness.
- **Steps**:
  1. Create `tests/integration/test_coord_single_home_workflow.py`:
     - `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`. Both markers are registered in `pytest.ini`; check `pytest.ini` before adding any marker.
     - Add a module docstring stating FR-015 / SC-001 / SC-002 / NFR-002, the "run this file alone" rule, and why `--topology coord` is explicit.
  2. Add a `_run(repo, *args, expect_ok=True) -> CompletedProcess` helper running the CLI with `cwd=repo` and the isolated HOME the test suite already provides (per-worker HOME isolation, WP04 of an earlier mission; reuse the repo's conftest fixtures and never touch the real `~/.spec-kitty`). On failure, include stdout and stderr in the assertion message.
  3. Fresh repository: `git init -b main`, set user email and name, make an initial commit, run `spec-kitty init . --ai claude --non-interactive`, and commit. Mirror quickstart §0 and research's NFR-001 setup; reuse WP02's factory if it exposes a "fresh initialized repo" helper.
  4. Parametrize `topology` over:
     - `("coord", ["--topology", "coord", "--pr-bound", "--start-branch", "topic"])`
     - `("lanes_with_coord", ["--topology", "lanes_with_coord"])`, created from a topic branch.

     Record `creation_base = git rev-parse HEAD` of the target branch immediately before create. Read `mission_slug`, `coordination_branch` and `target_branch` from `agent mission create ... --branch-strategy already-confirmed --json`.
  5. Guard assertions straight after create:
     - `meta.json` `topology` equals the parameter;
     - the coordination worktree exists (eager materialization, WP06);
     - `coord_tree_has(repo, coordination_branch, f"kitty-specs/{dir}/status.events.jsonl")`.
  6. Add a helper `_coord_paths_touched(repo, rev_range) -> list[str]`: list paths changed by each commit in the range (`git log --name-only --format= <range> -- kitty-specs/<dir>/`), then keep those whose `kind_for_mission_file` is a COORD kind. Import the taxonomy (`mission_runtime.artifacts`) instead of hard-coding filenames, because the ledger is PRIMARY now and hard-coding would drift.
- **Files**: the new test file only.
- **Validation**: the scaffold alone (create and guards) passes for both parameters.
- **Edge cases**:
  - Without `origin/HEAD`, primary-branch detection falls back to the current branch (CLAUDE.md "Create-time topology" caveat). Run create from the branch the parametrization intends.
  - Keep subprocess timeouts generous but bounded (for example 120 s per call).

### Subtask T112 – Linear flow and the single-home assertions

- **Purpose**: Exercise every writer family through its CLI entry point, in order, and assert the invariant once at the end, before consolidation and after.
- **Steps**:
  1. Drive, asserting exit code 0 for each step:
     - `spec-kitty agent decision open --mission <M> --flow specify --slot-key s.a --input-key a --question "A?" --json`, then the matching `resolve` (`spec-kitty agent decision resolve ... --json`; check `--help` for the exact flags);
     - tracer append through the production CLI `spec-kitty agent tracer-append --mission <M> --category approach --entry "..." --actor e2e --json` (registered under `spec-kitty agent`; options verified with `--help`). Only if the CLI needs fixture state the test cannot provide, fall back to the library `append_tracer_finding` (`src/specify_cli/retrospective/tracer_writer.py:227`), and record why in the Activity Log;
     - a second `decision open` (slot `s.b`);
     - `spec-kitty spec-commit --mission <M> -m "spec batch" <spec.md> <decisions/index.json> <traces/approach.md> <status.events.jsonl> --json`;
     - `spec-kitty agent mission setup-plan --mission <M> --json` (write a minimal `plan.md` first if the command needs it);
     - write a minimal `tasks.md` and `tasks/WP01-*.md` (one WP owning one file), then `spec-kitty agent mission finalize-tasks --mission <M> --json`;
     - satisfy the implement gate: `analysis-report.md` is required (`analysis_report_required` in `cli/commands/agent/workflow.py`), so create it the way other integration tests do;
     - `spec-kitty agent action implement WP01 --agent e2e --json`, make a trivial code commit in the lane workspace, then `spec-kitty agent tasks move-task WP01 --to for_review` → `in_review` → `approved` (use `--force`/`--actor` flags as other lifecycle tests do);
     - `spec-kitty accept --mission <M> --json`. Accept needs lanes and a passing acceptance matrix (see `tests/specify_cli/cli/commands/test_accept_residual_partition.py` fixtures and the #4891 pattern).
  2. **Before** `consolidate`, assert:
     - `_coord_paths_touched(repo, f"{creation_base}..{target_branch}") == []` (SC-001);
     - `meta.json` IS in that range's history (the positive control from FR-001);
     - exactly one `status.events.jsonl` for the Mission across the repository root checkout and the coordination worktree. The root copy must be absent or byte-equal to its committed state with no new events; the cleanest form is "only the coordination copy has events after create";
     - every decision id opened (both) appears in the status log's `Decision*` events and in `decisions/index.json` on the PRIMARY partition;
     - the logical clock is strictly increasing over the coordination log's events. Read the field from the actual event shape: research names `event_lamport`, and the lifecycle envelope uses `lamport_clock` (`status/lifecycle_events.py:464`). Pick whichever the events carry, and assert the field exists so the check cannot pass vacuously;
     - no event id appears twice in the log (NFR-002).
  3. Run `spec-kitty consolidate --mission <M>` (local; never `--push`). Assert exit 0; `meta.json`, `spec.md` and the ledger land on the local target branch; the Mission's lanes are absorbed.
  4. **After** consolidation, re-assert the "every decision present" and "no duplicate ids" checks on the target branch's projected copies, where the bookkeeping projection writes them.
- **Files**: the test file.
- **Validation**: green for both parameters.
- **Edge cases**:
  - If a step fails because a WP's behaviour regressed, capture the full CLI output in the failure message. That output is the evidence handed back to the owning lane.
  - Do not weaken an assertion to green it.

### Subtask T113 – Moved-merge-base variant (#5440 headline)

- **Purpose**: #5440 reported `TARGET_BRANCH_CONTENT_CONFLICT` at consolidation. It did not reproduce on a linear flow, so this variant moves the merge base, as spec FR-015 requires.
- **Steps**:
  1. Factor T112's flow into a `_drive_flow(repo, topology, *, mid_flight_hook=None)` helper.
  2. Variant hook, run after `implement WP01` and before `accept`: on the target branch's checkout (the repository root checkout), commit an unrelated file (`docs/unrelated.md`). Then make the Mission absorb it: lane rebase or merge per the repository's normal flow (`spec-kitty` auto-rebase, or `git merge` of the target into the lane, whichever the lifecycle tests use). The goal is a merge base that differs from `creation_base`.
  3. Assert:
     - consolidation exits 0;
     - the output does not contain `TARGET_BRANCH_CONTENT_CONFLICT` (the constant is imported in `src/specify_cli/consolidation/forecast.py`; import the constant rather than the literal);
     - `docs/unrelated.md` and the Mission's PRIMARY files are both on the target;
     - the T112 invariant assertions still hold.
  4. Parametrize as `variant in ("linear", "moved_merge_base")` × topology: 4 cases.
- **Files**: the test file.
- **Validation**: all 4 cases green.
- **Edge cases**:
  - The unrelated commit must not touch `kitty-specs/`, or it would become a genuine content conflict.
  - If consolidation runs a `--dry-run` forecast first, assert the forecast is clean too.

### Subtask T114 – Local run, NFR-002 closure and evidence for the PR

- **Purpose**: Integration runs in CI nightly, not per PR (memory: integration-per-PR ruled "stay nightly"), so the local run is the PR's evidence.
- **Steps**:
  1. Run ONLY this file:
     `uv run --frozen pytest tests/integration/test_coord_single_home_workflow.py -q -p no:randomly`.
     Also run `--durations=10` once to record cost.
  2. Record in the activity log: the command, pass/fail counts, wall time, and the environment (git version ≥ 2.38, needed for squash-absorption detection).
  3. Do a non-vacuity self-check, local only, no commit:
     - temporarily make `_coord_paths_touched` return a planted COORD path and confirm the SC-001 assertion fails;
     - temporarily duplicate one event line in the coordination log before the duplicate-id check and confirm it fails.

     Note both in the activity log.
  4. Run `ruff check`, `ruff format --check` and `mypy --strict` on the file.
- **Files**: the test file (plus the activity log entry in this prompt).
- **Validation**: green; evidence recorded.
- **Edge cases**:
  - Never run `tests/integration/` as a directory or `tests/e2e/` (C-006).
  - If the run is flaky, fix the root cause (`testing-flakiness.md`); never retry to green.
- **SC-001 non-vacuity (post-tasks squad R-m6)**: in a throwaway run (not committed as a test case, or as a clearly named self-check test), plant a real commit touching a COORD path (e.g. `kitty-specs/<dir>/status.events.jsonl`) on the target branch inside `creation_base..target`. Confirm the history probe catches it (the assertion goes red). Record the output in the activity log.

### Subtask T119 – Fresh-clone decision durability and ledger commit points (US4.8, FR-009b)

- **Purpose**: post-tasks squad R-M1. US4.8 / FR-009b require that a fresh clone of a post-fix Mission, mid-flight, finds every decision, and that the existing PRIMARY-partition committers commit an uncommitted ledger on the target branch. No earlier WP proves this end to end.
- **Steps**:
  1. In the same e2e file (both parametrizations), after `decision open`/`resolve` on the post-fix Mission, commit the ledger through the normal path: `spec-commit` ~~(or `setup-plan`, which commits planning files)~~ (struck in round 4: committers are spec-commit and accept only, `plan.scope.ledger-committers`).
  2. Separately assert the ledger commit point **through `spec-commit` and `accept` only** (operator decision G1, `plan.scope.ledger-committers`). Leave a new decision's ledger files uncommitted, then run `accept` (and, in a separate leg, `spec-commit`). Assert with `git log -1 --name-only <target>` that the target branch tip now holds `decisions/index.json` and the new `DM-*.md`.
  3. `git clone <repo> <tmp>/clone` (no coordination worktree). In the clone, run `spec-kitty agent decision verify --mission <M> --json` and `spec-kitty doctor decisions --mission <M> --json`. Assert that every decision id opened in the source repository is found, that verify is clean (not forked), and that doctor reports `ledger.state == "primary"`.
- **Files**: `tests/integration/test_coord_single_home_workflow.py`.
- **Validation**: green on the final tree. Record the decision-id sets (source vs clone) in the activity log.
- **Edge cases**: the clone has no coordination worktree. Reads must work from refs (WP17's detector is read-only), and the CLI must not materialize anything for a read.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **G1 (operator decision; `plan.scope.ledger-committers`)**: FR-009b's committers are **spec-commit and accept only**. T119 step 2 asserts the ledger commit point through `spec-commit` and `accept` (WP16) **only**.
  - Leave a new decision's ledger uncommitted, then run `accept`, and separately `spec-commit`. Each time, `git log -1 --name-only <target>` must show `decisions/index.json` and the new `DM-*.md`.
  - The earlier "setup-plan or finalize-tasks" alternative and the "defect for the owning WP" routing are **removed**.
- **Red evidence (analyze C2; REQUIRED, not optional)**: the SC-001 history probe and the single-log assertion **MUST be shown RED on this WP's planning base**. Run this file against the pre-Mission product code (a worktree of `issue-5440-coord-artifact-single-home` at its planning base, i.e. without the lanes' code, via `PYTHONPATH=<that worktree>/src` or by installing it), and paste the red output into the activity log. This supersedes any "optional" wording in Review Guidance.
- **Cross-check**: `_collect_finalize_artifacts` lists the root-checkout `status.events.jsonl` / `status.json`. If WP15 leaked them, SC-001 catches it; report that to WP15's owner (the orchestrator).
- **Optional extra hook**: open a decision on the target branch mid-flight, to exercise WP11's driver and WP12's recency fix together. This is new scope, so do it **only with explicit operator sign-off**; otherwise list it as a suggestion.
- Run the CLI as `uv run --frozen spec-kitty` from the lane worktree (stale-install gotcha), with `-p no:randomly --durations=10`.

## Targeted test surface

```bash
uv run --frozen pytest tests/integration/test_coord_single_home_workflow.py -q
make test-fast
```

Re-run the two WP02 factory self-tests (when you rely on new factory behaviour) (`tests/coordination/test_coord_mission_factory.py`) if you rely on new factory behaviour.

**Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).** Record commands and counts in the activity log for the PR's *Tests run* section.

Baseline-red gotcha (CLAUDE.md): classify any red before acting on it: a pre-existing P0, a CI environment issue (auth, `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`), a stale install (`pip install -e .`), or a stale venv (`uv sync --frozen --all-extras`).

## Quality gates

- C901 ≤ 15 per helper (NFR-004). Split the flow driver into step helpers.
- `ruff check`, `ruff format --check` and `mypy --strict` clean on the new file (NFR-005).
- No `xfail` and no `skip` except the repository's standard platform skips (for example, POSIX-only hooks), with a reason.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5440 #5519

## Definition of Done

- T111-T114 done; 4 parametrized cases green locally; evidence recorded.
- The topology guard proves both Missions really are coordination-routed.
- Invariant assertions cover SC-001, SC-002 and NFR-002, each with a non-vacuity self-check noted.
- No product code changed. Any product defect found is reported to the orchestrator with CLI output.
- T119: fresh-clone decision durability and the ledger commit point are asserted (US4.8, FR-009b); the SC-001 probe is proven non-vacuous (R-m6).

## Risks & Mitigations

- **Vacuous `coord` run** (a pr-bound default to `lanes`). Mitigated by explicit `--topology coord` and the `meta.json` topology assertion.
- **Fixture fragility** across accept, analysis and lanes gates. Mitigated by reusing existing integration fixture patterns and failing with full CLI output.
- **Long runtime.** It is a single file with 4 cases, marked `integration` and owned by CI nightly. Record the duration.
- **Stale CLI install.** Mitigated by invoking the lane worktree's own code.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies:
  - the file is GREEN on this WP's final commit;
  - the invariants are non-vacuous. Ask for, or re-run, the planted-failure self-checks from T114.
- This WP's "red" is the defect it guards. ~~Optionally~~ **Required (analyze C2)**: check against the planning base / pre-Mission code that the SC-001 history probe and the single-log assertion fail there (create seeds the target at base). Note that the full flow may not run end to end at base.
- Confirm:
  - topology guards;
  - the moved-merge-base variant really moves the merge base (inspect `git merge-base`);
  - no `--push`;
  - only this file was run locally.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T18:17:25Z – cursor – shell_pid=1515053 – Committed e1a49f9d9e. Full file: 29 passed in 197s (4 e2e cases + 25 self-checks); ruff check/format and mypy --strict clean. RED at planning base c833721eb3 (PYTHONPATH=<base>/src; copy of file+factory): (1) SC-001: AssertionError 'COORD paths committed on topic before consolidation: [9a0937e283 kitty-specs/e2e-01M3YX0C/status.events.jsonl]' (both topologies); (2) single-log: AssertionError 'status logs on disk: [root kitty-specs/.../status.events.jsonl, .worktrees/...-coord/.../status.events.jsonl]' (both topologies); (3) ledger commit point: 'ledger still dirty after a spec-commit'. BLOCKED: T119 accept leg is red against the product (accept exits 1 with git_dirty on decisions/index.json + new DM-*.md instead of committing the ledger). Not moving to for_review.
- 2026-10-02T18:35:19Z – cursor – shell_pid=1542362 – Orchestrator ruling: accept must commit an uncommitted PRIMARY ledger. Dirty gate no longer blocks those paths. Commits ed9eef9dd3 (fix + unit tests: gate via specify_cli/acceptance/ledger_dirt.py, DECISION_LEDGER taxonomy, current mission only; residual scan now also picks up the untracked new DM-*.md) and 1404842433 (e2e accept leg). e2e file + new unit test: 40 passed. Blast radius (accept subsystem + trio/accept arch gates + trio characterization): 553 passed, 1 skipped.
