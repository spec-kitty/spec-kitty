---
work_package_id: WP01
title: Status Doctor Log Errors
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-5924-status-doctor-corrupt-log
merge_target_branch: issue-5924-status-doctor-corrupt-log
branch_strategy: Planning artifacts for this mission were generated on issue-5924-status-doctor-corrupt-log. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5924-status-doctor-corrupt-log unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Bounded status-doctor fix
history:
- at: '2026-10-11T14:28:14Z'
  actor: planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_doctor_log_errors.py
execution_mode: code_change
owned_files:
- src/specify_cli/status/doctor.py
- src/specify_cli/status/store.py
- tests/status/test_store.py
- tests/status/test_doctor.py
- tests/status/test_doctor_log_errors.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5924'
---

# Work Package Prompt: WP01 – Status Doctor Log Errors

## Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load **implementer-ivan** before parsing the rest.
Run checkout `.venv/bin/spec-kitty agent profile show implementer-ivan`.
Load scoped implement charter context; do not use ambient rc6 CLI.

- **Profile**: implementer-ivan
- **Role**: implementer
- **Agent/tool**: pi
- **Issue owner**: Ivan-Melck, assigned/claimed by parent operator.

## Important: Review Feedback

Read any event-log review_ref before implementation/rework.
Address all rejection findings and record canonical progress notes.
Do not edit status, lane or history by hand in this prompt.

## Review Feedback

No review yet at planning. Actual feedback belongs to the status event log.

## Objectives & Success Criteria

Deliver #5924 only: corrupt/unreadable status.events.jsonl produces ERROR,
unhealthy result and actionable truthful diagnostics, with/without status.json.
Existing run_doctor and text/JSON CLI must not falsely pass or crash.
Preserve exact log/snapshot bytes and missing-file state.
Preserve accepted mixed event families and legitimate health checks.
See spec.md FR-001–FR-006, SC-001–SC-004 and all mapped constraints.

## Context & Constraints

Read `.kittify/charter/charter.md` and these resolved Mission artifacts:
`kitty-specs/status-doctor-corrupt-log-01M4NN6K/spec.md`, `plan.md`, `tasks.md`,
`research.md`, `reasons-canvas.md`, `data-model.md`, `contracts/status-doctor.md`,
`quickstart.md` (artifact filenames relative to the same Mission directory).

Parent verified canonical store.read_events delegates annotation-aware parser;
JSON/non-object/schema/unknown-kind errors already retain physical row lines,
including preceding blanks. Parent then witnessed malformed annotation delta=[]
escaping as AttributeError, not StoreError. Approved store.py fold: add AttributeError
only to existing exception tuple around InnerStateChanged.from_dict, preserving line;
direct test_store.py and doctor malformed delta/subtasks regressions mandatory.
Note overlap with PR #5953; no broader reader/model refactor.
No doctor-local parse loop, broad exception-to-empty fallback or new abstraction.
Skip reviewer-self-approval on log failure too: it reads status.events.jsonl.
Catch exactly StoreError/OSError/UnicodeError at the canonical log-read boundary.
No decision-doctor edits (see #5304 for context only), reducers or schemas.
No CLI-adapter/dependency/version changes or automatic repair.

## Branch Strategy

Canonical finalize-tasks populates branch fields; do not guess/rewrite them.
Current/planning base/mission target: issue-5924-status-doctor-corrupt-log.
Topology: single_branch; sequential write checkout returned by implement resolver.
There is no lane worktree or dependency merge for this topology.
GitHub PR target: main. Never merge/consolidate or push main.
Leave eventual approved/accepted Mission pending PR integration.

After parent readiness analysis and dispatch only:

```bash
.venv/bin/spec-kitty agent action implement WP01 --agent pi --mission status-doctor-corrupt-log-01M4NN6K
```

Use the returned workspace; planner has not called this command.

## Subtasks & Detailed Guidance

### Subtask T001 – Campsite and Baseline Review

**Purpose**: Keep baseline/environment findings separate from product changes.

- Inspect only owned surfaces before functional edits.
- Preserve existing tests and source authority; identify any touched-area smell.
- If no enabler is needed, record a concise no-enabler conclusion.
- Any tidy step must be local, behavior-preserving, distinct and independently green.
- Store scope is only approved annotation normalization; no CLI/reducer/unrelated edits.
- Parent baseline doctor.py tests: 55 passed.
- Parent make test-fast: 2501 passed, 5 skipped, one stale retired dashboard pyc failure.
- Environment report: https://github.com/spec-kitty/spec-kitty/issues/6050.
- Parent removed only verified generated pyc and empty retired directories.
- Then named test_no_retired_subsystems.py: 12 passed; no source changes.
- Formatter baseline: 3623 files green; strict mypy doctor.py green.
- Do not call this a full post-cleanup fast-suite pass or rerun while parent tests run.

**Files**: doctor.py and existing status doctor tests (inspection).
**Parallel?** No.
**Validation**: Evidence classified, scope unchanged; no test duplication.

### Subtask T002 – Failing-First Acceptance Test Commit

**Purpose**: Pin both live reported failures through real entry points before fix.

- Author tests in test_doctor.py or optional focused test_doctor_log_errors.py.
- Use real TemporaryDirectory/pytest tmp_path Mission fixtures.
- Malformed JSON + no snapshot must return ERROR/unhealthy, not healthy=True.
- Same log + valid snapshot must return ERROR, not StoreError traceback.
- Call existing run_doctor, and existing CLI runner for text/JSON paths.
- Record actual RED commands/results and pre-fix commit SHA.
- Commit tests as a separate failing-first commit **before any production fix**.
- Use canonical targeted code-commit surface selected by parent; no blanket staging.
- If regression marker is needed for the transitional RED commit, it is temporary.
- Execute the RED test explicitly: marker/deselection is not proof of reproduction.
- Final fix must remove marker and pass as normal regression coverage.
- Same-fixture repaired-history controls prove diagnosis can see healthy authority.
- Preserve existing tests rather than replacing unique coverage with a smoke test.

- Add direct canonical read_events failing tests for malformed annotation delta/subtasks,
  plus doctor tests, before the approved store tuple addition.

**Files**: owned test files only at this stage.
**Parallel?** No; production edits wait for RED commit.
**Validation**: Reviewer can observe failing-first SHA preceding production SHA.

### Subtask T003 – Canonical Read Failure Becomes a Finding

**Purpose**: Prevent snapshot gating/fallback from hiding corrupt authority.

- Strictly read canonical event log independently of snapshot before dependent checks.
- Translate exactly StoreError/OSError/UnicodeError into an actionable ERROR Finding.
- Include resolved log path and actual exception reason.
- Use canonical physical 1-based record line where supplied; no guessed I/O line.
- No duplicate parser and no general except Exception for this diagnosis boundary.
- Snapshot presence cannot bypass canonical readability check.
- On failure suppress log-dependent initialization/backfill/drift/membership advice.
- Skip check_reviewer_self_approval along with every other log-dependent check.
- Continue independent issue-matrix, sparse-checkout and frontmatter checks.
- Add AttributeError only to the existing store annotation decoder catch tuple;
  this converts witnessed malformed delta/subtasks into physical-line StoreError.
- Preserve successful path's accepted mixed-event reduction/check semantics.
- Keep the local implementation readable, typed and ≤15 complexity per function.
- Avoid repeated non-trivial diagnostic literals and inert exception handlers.
- Do not call materialize/write/repair helpers from doctor.

**Files**: doctor.py and approved tuple addition in store.py only.
**Parallel?** No.
**Validation**: Both T002 snapshot cases turn GREEN through production path.

### Subtask T004 – Complete Failure Matrix and Healthy Controls

**Purpose**: Close the approved class rather than only one JSON example.

- Five classes × snapshot absent/present: invalid JSON, non-object JSON,
  schema-invalid record, invalid UTF-8 and filesystem read failure.
- Add malformed record after accepted rows and blank rows to prove physical location.
- Include valid annotation envelope with delta=[] and malformed nested subtasks,
  asserting canonical StoreError + physical line and doctor ERROR (no AttributeError).
- Include unknown event kind as schema/dispatch corruption coverage where applicable.
- Decode errors need actual reason/path; location only if reader truthfully exposes it.
- Use filesystem-boundary OSError injection for deterministic I/O under privileged users.
- Do not mock the parser/reducer/run_doctor to manufacture desired outcomes.
- Text and JSON CLI assert exit 1, visible ERROR, JSON healthy false, no traceback.
- Recovery: preserve evidence, restore trusted history/fix access, rerun doctor.
- Assert no blind deletion/automatic repair/materialize-only/backfill-only advice.
- Assert all existing log/snapshot bytes and missing-file states unchanged.
- Pair with repaired readable fixture; prove no corruption finding on valid variant.
- Accepted controls: mixed lifecycle/status/annotation, blanks, missing/empty/blank-only.
- Keep real drift and WP prompt/event membership reconciliation controls.
- Include corrupt history plus independent frontmatter/issue/sparse failure to prove
  independent checks continue while dependent suggestions are suppressed.
- Remove transitional regression markers in the fix commit.

**Files**: owned status test files.
**Parallel?** No.
**Validation**: FR-001–FR-006 and ten negative combinations plus controls pass.

### Subtask T005 – Targeted Validation and Self-Review

**Purpose**: Establish actual scoped safety and quality evidence.

Run serially; include every changed/new focused test file:

```bash
.venv/bin/python -m pytest tests/status/test_doctor.py tests/status/test_store.py -q
# If created:
.venv/bin/python -m pytest tests/status/test_doctor_log_errors.py -q
.venv/bin/python -m pytest tests/status -m '(fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not timing and not windows_ci and not platform_darwin' -q
make test-fast
.venv/bin/ruff check src/specify_cli/status/doctor.py tests/status/test_doctor.py
.venv/bin/ruff format --check --force-exclude src/specify_cli/status/doctor.py tests/status/test_doctor.py
.venv/bin/mypy --strict src/specify_cli/status/doctor.py src/specify_cli/status/store.py
make format-check
```

- Add store.py/test_store.py and focused new tests to lint/format checks; maintain typed helpers.
- Record changed-line coverage ≥90%, command/passed/failed/skipped counts and diagnostics.
- Run specific named architectural/prose gate only when implicated, not directory sweep.
- No make test-full, full architectural/e2e/performance/stress/timing suites.
- No duplicate concurrent runs, retries-to-green, ignores or xfails hiding fixed behavior.
- Classify/report unrelated failures per charter, not silent accepted red.
- Review actual complete diff for unexpected files, misleading actions and mutation calls.

**Files**: owned files; result evidence through canonical progress/tracer helpers.
**Parallel?** No.
**Validation**: Targeted tests, typing, lint and formatting green, evidence truthful.

### Subtask T006 – Independent Review Handoff

**Purpose**: Make bounded work objectively reviewable before PR-only delivery.

- Hand off exact RED test commit, fix commit and final diff to independent reviewer.
- Reviewer is a distinct profile/session, not implementer self-approval.
- Provide five-class matrix, both snapshot halves and repaired positive controls.
- Reviewer verifies expected exceptions only and canonical reader retained;
  store diff only approved annotation decoder tuple addition with direct regressions.
- Verify independent checks survive failures and no misleading dependent advice.
- Verify exact bytes, physical location, CLI exit/output and normal drift/reconciliation.
- Fold findings, rerun impacted targeted checks and return for review.
- Parent records issue verdict only when truly fixed and acceptance evidence exists.
- Parent opens PR targeting main; implementation agent never merges/consolidates.
- Leave approved/accepted Mission pending PR integration, not fictional merged status.

**Files**: No new product files; review/progress via canonical helpers.
**Parallel?** Independent review may inspect a fixed diff, no competing product writer.
**Validation**: Independent review evidence and no publication/merge beyond PR scope.

## Test Strategy

See T002/T004/T005; acceptance tests are mandatory, not optional in this Mission.
Tests call real run_doctor/CLI and canonical accepted-fixture builders.
Each snapshot branch independently fails pre-fix; final normal tests prove both.
No-op-passable preservation/healthy requirements have same-fixture positive controls.
If multiple local fix parts exist, prove each part's absence reintroduces its failure.

## Risks & Mitigations

Snapshot mask/crash → half-by-half tests; wrong row → physical blank-row fixture.
Mixed-event false rejection → accepted canonical controls; I/O privilege → boundary injection.
Broad catches → inspect exact except types; evidence loss → byte/absence assertions.
Scope drift → only owned files, store tuple addition only, no decision/reducer changes.

## Review Guidance and Definition of Done

All requirement refs mapped, red→green order verified, all targeted checks reported.
No temporary regression marker remains; no destructive recommendation or traceback.
Independent reviewer checks actual full diff against REASONS Safeguards and spec.
No approval is inferred from planner artifacts or existing baseline greens.
No merge/consolidation, main push or claim of PR integration.

## Progress & Status

Use `agent tasks add-history WP01 --mission status-doctor-corrupt-log-01M4NN6K`
and `agent tasks mark-status`/status transitions with the explicit Mission handle.
Completion/status/history live only in status.events.jsonl, never hand-edited here.
