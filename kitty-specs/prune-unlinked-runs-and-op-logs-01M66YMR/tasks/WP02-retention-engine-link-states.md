---
work_package_id: WP02
title: 'Retention engine: linked, unlinked and unknown'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- C-005
- C-006
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6739-prune-unlinked-runs-and-op-logs
merge_target_branch: issue-6739-prune-unlinked-runs-and-op-logs
branch_strategy: Planning artifacts for this mission were generated on issue-6739-prune-unlinked-runs-and-op-logs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6739-prune-unlinked-runs-and-op-logs unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - User Stories 1-3 (MVP)
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/state/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/state/retention.py
# The Op roster (recorded + open ids from one pass) is owned by the Op record
# module; WP02 extends the file WP01 created rather than duplicating the rule.
- src/specify_cli/invocation/writer.py
- tests/core/test_event_log_retention.py
- tests/cli/commands/test_doctor_event_logs.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Retention engine: linked, unlinked and unknown

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the
status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code
blocks: ````python`, ````bash`.

---

## Objectives & Success Criteria

Make `scan_retention` (and therefore `doctor event-logs`) able to reclaim the two
families the issue names, without touching the protection the operator ruled for:

1. an old run whose run-index entry is gone but whose snapshot records its Mission by
   slug becomes a normal candidate (or is kept as `Mission is open`);
2. an old run that records no Mission identity at all becomes a candidate
   `past retention; no Mission recorded`;
3. an old Op-scoped glossary log follows its Op: candidate `past retention; Op
   completed` when the Op is closed, kept `Op is open` while it is open, candidate
   `past retention; no Op recorded` when no record exists;
4. a run whose **recorded** Mission identity this checkout cannot resolve stays kept
   as `Mission not found`, and an ambiguous identity stays kept (`DS-L2`).

Done when the engine and command test files are green, `mypy --strict` and `ruff` are
clean on `src/specify_cli/state/retention.py`, and the red-first commits precede the
implementation commits.

## Context & Constraints

- Read first: `spec.md` (FR-001 … FR-012), `plan.md` (IC-02, IC-03),
  `data-model.md` (link states, verdict order, reason vocabulary) and
  `research.md` (decisions D1–D7).
- **The identity rule does not widen.** A recorded `mission_id` is the only runtime
  identity; a slug is read only from a record that carries no `mission_id`. The
  production writer's snapshot carries neither at the top level, so `inputs.mission_slug`
  is that snapshot's slug record — apply it there and nowhere else.
- **Unreadable is unknown, not unlinked.** A snapshot that is missing, not JSON, or not
  an object must keep reading as `Mission not found` (fail safe). So must an identity
  claimed by two Mission directories.
- Verdict order is fixed: `keep_runs` → `max_age_days` → link state → work over →
  lock → candidate. Keep the existing expense order: link lookups only for items past
  both limits.
- The registry drives which surfaces are scanned (`_select_collectors`,
  `RetentionPolicyDriftError`); do not add a surface or bypass the drift gate.
- Reader side only (C-004): no event-log append door, no lock file created in a
  preview. Deletion keeps using `_delete_run` (runs) and `_delete_locked_log`
  (glossary logs, including Op logs).
- `__all__` stays as it is: the new reason and kind constants are module names read by
  the tests and by the engine, exactly like the existing `REASON_*` names.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on
  `issue-6739-prune-unlinked-runs-and-op-logs`; completed changes merge back into
  `issue-6739-prune-unlinked-runs-and-op-logs`.
- **Planning base branch**: `issue-6739-prune-unlinked-runs-and-op-logs`
- **Merge target branch**: `issue-6739-prune-unlinked-runs-and-op-logs`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T005 – Split the pinned "resolves nowhere" test

- **Purpose**: the current test bundles four shapes under one expectation. Two change,
  two must stay pinned; splitting them keeps the protection visible and prevents a
  later regression from quietly widening it.
- **Steps**: in `tests/core/test_event_log_retention.py`, split
  `test_run_whose_mission_resolves_nowhere_is_kept` into:
  - a test that keeps the **recorded unknown** shapes kept (`unknown` id, ambiguous
    identity) — see `test_a_mission_id_shared_by_two_mission_dirs_is_ambiguous_and_not_found`;
  - a test that keeps the **unreadable snapshot** shape kept;
  - a test that asserts the new expectation for the **anonymous** run (no identity
    recorded anywhere) and the **unindexed** run whose snapshot records the slug.
- **Files**: `tests/core/test_event_log_retention.py`
- **Parallel?**: No — same file as T006/T007; write the three tests as one red-first
  commit if that keeps the diff readable.
- **Notes**: do not delete any shape from the fixture. The `_run(...)` helper already
  writes `inputs: {"mission_slug": slug}`, which is exactly the production shape; keep
  it that way.

### Subtask T006 – Red-first: a run linked only by its snapshot slug

- **Purpose**: pin User Story 1's main case.
- **Steps**: add a test that starts a run with the real writer
  (`runtime.next.runtime_bridge_io.get_or_start_run`), removes its run-index entry,
  ages the directory past `max_age_days`, and asserts:
  - against a merged Mission: candidate with `REASON_COMPLETED` and `mission` set to
    that Mission, and `apply_retention` deletes the directory;
  - against an open Mission: kept with `REASON_MISSION_OPEN`.
  Include the same-fixture positive control required by the non-vacuity tactic: the
  unknown-identity run from T005 stays kept in the same scan.
- **Files**: `tests/core/test_event_log_retention.py`
- **Parallel?**: No.
- **Notes**: `_set_age` after every write, so the fixture's newest mtime is what the
  test intends. `LIMITS_NO_KEEP` (keep_runs=0) keeps the ranking out of the way.

### Subtask T007 – Red-first: the Op-log family

- **Purpose**: pin User Story 2 and the ranking rule of User Story 3.
- **Steps**: add engine tests (and one command-level test in
  `tests/cli/commands/test_doctor_event_logs.py` only if the payload shape needs it):
  - a `profile-invocation-<id>` log whose Op record carries a `completed` event is a
    candidate with `kind == "op_log"` and reason `past retention; Op completed`;
  - the same with the closure on `kitty-ops/op-closures.jsonl` instead;
  - an open Op's log is kept with `Op is open`;
  - a log whose Op has no record is a candidate `past retention; no Op recorded`;
  - `_cli` / `_renderer` logs stay out of the report;
  - with `keep_runs: 1`, one Mission log and several Op logs, each family's rank is
    computed within itself (the Mission log is not pushed out by newer Op logs);
  - `apply_retention` deletes the completed Op's log and leaves the Op record, the
    closure spine and `kitty-ops/ops-index.jsonl` byte-identical;
  - an Op log that carries a `StepCheckpointed` row is kept while its Op is open,
    because that row is a live glossary resume point (C-006).
- **Files**: `tests/core/test_event_log_retention.py`,
  `tests/cli/commands/test_doctor_event_logs.py`
- **Parallel?**: No.
- **Notes**: write the Op records with the same shape the writer produces
  (`{"event": "started", ...}` then `{"event": "completed", ...}`), and commit them
  into the fixture's git repo where the existing fixture commits `kitty-ops/`, so a
  "tracked files never change" assertion still means something.

### Subtask T008 – Implement the link state and the unlinked verdict

- **Purpose**: give the verdict rule the third state it is missing.
- **Steps**: in `src/specify_cli/state/retention.py`:
  - add the link vocabulary (module-level constants, e.g. `LINK_OWNED`,
    `LINK_UNLINKED`, `LINK_UNKNOWN`) and put the link state on the scanned unit next
    to `feature_dir`;
  - rewrite the run link resolution so a snapshot with no top-level identity falls
    back to `inputs.mission_slug` (only then), and returns `unknown` for an unreadable
    snapshot, an unresolvable id/slug, or disagreeing index entries, and `unlinked`
    only when nothing is recorded anywhere;
  - extend the ledger verdict: `unknown` → kept `Mission not found`; `unlinked` →
    candidate with the family's unlinked reason; owned → the existing
    work-over/lock/candidate ladder;
  - add the new reason constants (`past retention; no Mission recorded`,
    `past retention; Op completed`, `past retention; no Op recorded`, `Op is open`).
- **Files**: `src/specify_cli/state/retention.py`
- **Parallel?**: No.
- **Notes**: keep `_mission_of_record` for index entries (they carry no `inputs`), and
  do not let the snapshot fallback read `inputs.mission_slug` for a record that already
  has a `mission_id` — that is the C-001 boundary. Mission logs keep their current
  behaviour (`unlinked` never applies: a log stem always names a Mission identity).

### Subtask T009 – Implement the Op-log family

- **Purpose**: collect, rank and delete `profile-invocation-<id>.events.jsonl`.
- **Steps**:
  - add `KIND_OP_LOG = "op_log"` and collect Op logs in their own collector over the
    same glossary directory and registry surface (`glossary_fallback_events`), so the
    drift gate keeps working and `keep_runs` ranks them among themselves;
  - recognise the `profile-invocation-` prefix before the Mission-stem lookup; keep
    the `_`-prefix, symlink and non-file exclusions exactly as they are;
  - read `open_invocation_ids(repo_root)` **once** per scan (WP01) and mark each Op
    log's link: open → kept `Op is open`, closed → candidate `past retention; Op
    completed`, no record → candidate `past retention; no Op recorded`;
  - reuse `_delete_locked_log` through the `_DELETERS` entry for
    `glossary_fallback_events` — the file lives inside the same deletable root, so
    `_assert_deletable` needs no change.
- **Files**: `src/specify_cli/state/retention.py`
- **Parallel?**: No.
- **Notes**: an Op log's `mission` stays `null` in the report. If the collector table
  cannot express two collectors over one registry surface without tripping
  `_select_collectors`, adjust the drift check minimally and add a test that the drift
  gate still rejects an uncollected surface — do not weaken it.

### Subtask T010 – Update docstrings and the #6739 residual note

- **Purpose**: the module narrative currently documents the old rule, including the
  residual that this mission retires.
- **Steps**: update the module docstring's verdict summary; update `_delete_run`'s
  "Residual" paragraph (the leftover empty run directory that "later scans keep as
  `Mission not found` (tracked with #6739)" is now age-pruned) and its
  "Trade-off" paragraph if the wording refers to the old rule; update
  `_run_mission`/`_read_snapshot_mission` docstrings for the slug fallback.
- **Files**: `src/specify_cli/state/retention.py`
- **Parallel?**: Yes (prose only) — but land it in the same WP.
- **Notes**: do not cite the mission slug in code; cite the issue and the ADR the way
  the existing comments do.

### Subtask T012 – Red-first: the command renders the new vocabulary

- **Purpose**: pin what the operator actually sees; the human report groups kept items
  by reason and lists candidates with their reason.
- **Steps**: in `tests/cli/commands/test_doctor_event_logs.py` (this WP owns that file)
  build a fixture with an old open Op's log and an old closed Op's log, invoke the real
  Typer app, and assert:
  - the rendered output contains `Op is open` and the closed Op's log path under the
    candidates section;
  - the `--json` payload carries `kind: "op_log"` with the matching reasons.
- **Files**: `tests/cli/commands/test_doctor_event_logs.py`
- **Parallel?**: No — same file as the engine assertions.
- **Notes**: fail first for the right reason. If it already passes because the
  renderer prints reasons generically, keep it — it is still the pin that the new
  values reach the human report, and say so in the WP history.

### Subtask T013 – Scale assertion (NFR-001, SC-005)

- **Purpose**: the performance threshold in the spec must be verifiable, not asserted
  in prose.
- **Steps**: add a test that builds 1,000 `kitty-ops/*.jsonl` records and 1,000
  glossary logs (Mixture of Op-scoped and `_cli` names), takes the tree digest, times
  one `scan_retention` and asserts it completes under 2 s and leaves the tree
  unchanged. Mark it so it runs in the fast unit suite (the repository's
  `@pytest.mark.unit` / `@pytest.mark.fast` pair) and keep the fixture writes cheap
  (write files directly, do not touch each one twice).
- **Files**: `tests/core/test_event_log_retention.py`
- **Parallel?**: Yes (independent of the rendering test).
- **Notes**: if 2 s is not reachable on this machine, report the measured number and
  the dominant cost in the WP history and in the PR body rather than silently
  relaxing the threshold.

### Subtask T011 – Verify

- **Purpose**: prove the WP is green.
- **Steps**:
  ```bash
  uv run pytest tests/core/test_event_log_retention.py tests/cli/commands/test_doctor_event_logs.py -q
  uv run mypy --strict src/specify_cli/state/retention.py
  uv run ruff check src/specify_cli/state/retention.py tests/core/test_event_log_retention.py tests/cli/commands/test_doctor_event_logs.py
  ```
- **Files**: none.
- **Parallel?**: No.
- **Notes**: also re-run `tests/specify_cli/invocation/test_doctor_ops.py` to prove WP01
  is still green after the engine change.

## Test Strategy

Red first (charter C-011): T005–T007 are committed before T008/T009. The reviewer
checks the new assertions fail on the WP base and pass at the head. Every assertion
that a new candidate appears is paired on the same fixture with an item that must stay
kept, so a change that makes nothing eligible cannot pass.

## Risks & Mitigations

- **Identity widening.** Reading `inputs.mission_slug` for a record that has a
  `mission_id` would silently merge two Missions' runs. Guard it with a test.
- **Unreadable snapshot read as unlinked.** That would delete runs of Missions on
  another branch. The T005 split keeps the pin.
- **Ranking regression.** Giving Op logs their own collector is what keeps
  `keep_runs` per family; a shared rank would push Mission logs out. Pinned by T007.
- **Deleting an Op log with a live resume point.** Only closed Ops are eligible, and
  only past `max_age_days`; `glossary.checkpoint.load_checkpoint` resumes inside its
  own invocation, so no live checkpoint is reachable.
- **Drift gate.** If the collector table changes shape, run the drift tests before
  assuming the gate still fails closed.

## Review Guidance

- Diff the verdict ladder against `data-model.md`'s table line by line.
- Confirm `inputs.mission_slug` is read only when no identity is recorded.
- Confirm the Op-log collector reads the open set once per scan (no per-item probe).
- Confirm nothing in the diff writes: no `append_event`, no lock-file creation in a
  preview, no index rewrite outside `_delete_run`.
- Confirm the red-first commits precede the implementation commits, and that the
  unchanged `Mission not found` protections are still asserted.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) —
never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission prune-unlinked-runs-and-op-logs-01M66YMR`
