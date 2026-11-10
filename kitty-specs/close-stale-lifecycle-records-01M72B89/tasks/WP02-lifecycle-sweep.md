---
work_package_id: WP02
title: The lifecycle sweep in doctor ops --close-stale
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-002
- NFR-003
- C-001
- C-003
- C-005
- SC-001
- SC-002
- SC-003
planning_base_branch: feat/7346-close-stale-lifecycle-records
merge_target_branch: feat/7346-close-stale-lifecycle-records
branch_strategy: Planning artifacts for this mission were generated on feat/7346-close-stale-lifecycle-records. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7346-close-stale-lifecycle-records unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Sweep
history:
- at: '2026-11-10T09:29:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/doctor/
create_intent:
- src/specify_cli/invocation/trail_commit.py
- tests/specify_cli/invocation/test_doctor_ops_lifecycle_7346.py
- docs/changelog/unreleased/7346-close-stale-lifecycle-records.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctor/ops.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/invocation/op_commit_policy.py
- src/specify_cli/invocation/executor.py
- src/specify_cli/invocation/trail_commit.py
- tests/specify_cli/invocation/test_doctor_ops_lifecycle_7346.py
- tests/specify_cli/invocation/cli/test_doctor_ops_cli.py
- tests/specify_cli/invocation/test_op_commit_policy.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- docs/context/ops-vs-missions.md
- docs/architecture/trail-model.md
- docs/api/cli-commands.md
- docs/changelog/unreleased/7346-close-stale-lifecycle-records.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The lifecycle sweep in doctor ops --close-stale

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- `spec-kitty doctor ops --close-stale [--threshold N]` closes every orphaned lifecycle record whose `started` record is older than N hours (all at `0`, and any whose `at` cannot be read), in every checkout, by writing an `abandoned` record (WP01's `write_abandoned_completion`).
- Each checkout's new closure files are committed in one commit on its current branch, with the #6410 skip rules applied to the lifecycle path and a protected-branch refusal reported, never bypassed.
- Mission status, `meta.json` and work package files are untouched.
- The JSON report gains `lifecycle_records` (contract `kitty-specs/close-stale-lifecycle-records-01M72B89/contracts/doctor-ops-lifecycle-sweep.md`); every existing key keeps its Op-only meaning.
- A fresh orphan left open makes the sweep exit 1, as a fresh Op does.
- The docs say lifecycle records have a close route.

## Context & Constraints

- Spec FR-003, FR-004, FR-006 to FR-010, NFR-002, NFR-003, C-001, C-003, C-005; data model and contract in the Mission directory.
- Current sweep: `src/specify_cli/doctor/ops.py:193-283` (`close_stale_ops`, complexity 11), `SweepReport` :140-164 (the JSON is a frozen contract except for additive keys; `closure_spine` is the precedent), checkout scan `_checkouts` / `scan_op_records` :64-107.
- CLI: `src/specify_cli/cli/commands/doctor.py` `ops` :1040-1090, `_run_ops_sweep` :990-1037, `_print_sweep_commit_summary` :940-971. `doctor.py` is a hot god-module: add functions, do not grow existing ones past complexity 15.
- Commit seam today: `ProfileInvocationExecutor._commit_op_record` (`src/specify_cli/invocation/executor.py:1078-1153`) and `_op_commit_kwargs` (:1155-1176); skip rules in `src/specify_cli/invocation/op_commit_policy.py` (`OP_RECORD_PATH_RE`, `probe_primary_tracking`, `op_commit_skip_reason`).
- Gates: `tests/architectural/test_event_log_writes_gate.py`, `test_archive_root_byte_identical.py`, `test_json_contract_enumeration.py` (`"doctor ops"` report mode only), `test_timing_coverage_invariant.py` (pins `report.swept` counts in `test_doctor_ops.py`; keep `swept` Op-only), `test_docs_cli_reference_parity.py`, `test_no_dead_symbols.py`.
- Out-of-matrix golden: `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py:385-389` pins the `ops` help text; update it with the help change and run it locally.
- Charter: red-first commit; complexity ≤ 15; ruff, format (`--force-exclude`) and mypy clean; no suppressions.

## Branch Strategy

- **Strategy**: single_branch.
- **Planning base branch**: `feat/7346-close-stale-lifecycle-records`
- **Merge target branch**: `feat/7346-close-stale-lifecycle-records`
- Start with `spec-kitty agent action implement WP02 --agent claude --profile python-pedro --mission close-stale-lifecycle-records-01M72B89` once WP01 is approved.

---

## Subtasks & Detailed Guidance

### Subtask T006 – Failing tests first

Create `tests/specify_cli/invocation/test_doctor_ops_lifecycle_7346.py` (real git repositories in `tmp_path`, `pytest.mark.git_repo`), reusing the fixtures of `tests/specify_cli/invocation/test_doctor_ops.py` and `test_doctor_ops_worktrees.py` where they fit:

1. A stale orphan (`write_started` with `at` 48 h ago) and a fresh one (1 h ago): `close_stale_lifecycle_records(repo, threshold_hours=24, now=...)` writes exactly one `abandoned` record (for the stale one), with reason `abandoned by doctor ops --close-stale (older than 24h)`; the fresh one is an entry with `action_taken == "none"`.
2. `threshold_hours=0` closes both.
3. A second run writes nothing new (NFR-002).
4. Every file outside `kitty-ops/` is byte-identical before and after (FR-004), including a Mission's `status.events.jsonl` and `meta.json` seeded in the fixture.
5. Commit: on an unprotected branch whose primary branch tracks `kitty-ops/lifecycle/*.json`, one commit lands containing exactly the new closure files, entries report `commit == "committed"`; when `kitty-ops/` is ignored, entries report `skipped:<reason>` and no commit lands; on a protected branch (configure protection the way `test_op_commit_attribution.py` / `test_doctor_ops.py` do) entries report `not_committed:protected branch '<b>'` and the files stay written.
6. A stale orphan in a linked worktree is closed and committed in that worktree, not in the repository root checkout (FR-007).
7. CLI (`tests/specify_cli/invocation/cli/test_doctor_ops_cli.py`): the `--json` key set gains `lifecycle_records` (update the pinned set at :75), the exit code is 1 with a fresh lifecycle orphan left and 0 when everything stale was closed and nothing fresh remains.

Confirm red, commit the tests alone: `test(doctor): pin the lifecycle sweep of doctor ops --close-stale (#7346)`.

### Subtask T007 – Commit-or-skip rules per record kind

In `op_commit_policy.py`:
- Add `LIFECYCLE_RECORD_PATH_RE = re.compile(r"(?:^|/)kitty-ops/lifecycle/[0-9A-HJKMNP-TV-Z]{26}\.json$")`.
- Give `primary_tracks_op_records` / `probe_primary_tracking` a `record_re` parameter (default `OP_RECORD_PATH_RE`), so the lifecycle sweep asks whether the primary branch tracks lifecycle records. Keep the Op behavior and messages byte-identical.
- Make the "tracks no ... records" skip message name the record kind (Op records vs lifecycle records) without changing the Op wording.
- Tests in `tests/specify_cli/invocation/test_op_commit_policy.py` for the lifecycle pattern.

### Subtask T008 – One trail commit helper

Create `src/specify_cli/invocation/trail_commit.py` with:

```python
def commit_trail_paths(
    *, repo_root: Path, record_root: Path, paths: Sequence[Path], message: str, explicit_trailer: str | None = None
) -> OpCommitOutcome:
```

Move into it, unchanged, what `_commit_op_record` does after choosing the path and message: current branch / work-tree probe, detached HEAD refusal, co-author trailer resolution (`resolve_co_author_trailer`, `InvalidCoAuthor` → refusal), `safe_commit` with the `_op_commit_kwargs` arguments (`GuardCapability.STANDARD`), and the `ProtectedBranchRefused` → `refusal="protected branch '<b>'"` mapping. Leave the #6410 skip decision with the caller (it differs per record kind). `ProfileInvocationExecutor._commit_op_record` and `op_write_refusal` then call it / share `_op_commit_kwargs` through it. `OpCommitOutcome` stays where it is (import it). Every existing Op-commit test must stay green unchanged (`test_op_commit_attribution.py`, `test_doctor_ops.py`, executor tests).

### Subtask T009 – The sweep

In `src/specify_cli/doctor/ops.py`:
- `SweepLifecycleEntry` dataclass with the contract fields and `to_dict()`.
- `SweepReport.lifecycle_records: list[SweepLifecycleEntry]`, added to `to_dict()` as `"lifecycle_records"`, and `has_errors` / a `lifecycle_fresh` count considered by the CLI exit code (do not change `swept` or `skipped_fresh`, which stay Op-only).
- `close_stale_lifecycle_records(repo_root, *, threshold_hours, now) -> list[SweepLifecycleEntry]`: for each checkout from `_checkouts(repo_root)`, `read_lifecycle_records(checkout)`, `find_orphans`, `unpaired_started(group)` (WP01), age from the record's `at` (reuse `_age_hours` on its ISO string), write `write_abandoned_completion` for stale ones, collect the written paths, then one `commit_trail_paths` per checkout (skip decided by `op_commit_skip_reason` with the lifecycle tracking probe), and stamp each entry's `commit`. A per-record write error is recorded on its entry; the sweep continues.
- Keep every function ≤ 15 complexity: split read/decide/write/commit into helpers.
- Unreadable checkouts: reuse the existing `unreadable_checkouts` reporting where a lifecycle read fails.

### Subtask T010 – The CLI

In `doctor.py`:
- `_run_ops_sweep` calls `close_stale_lifecycle_records` after `close_stale_ops` and attaches the entries to the report (or let `doctor.ops` expose one `close_stale(...)` that runs both; choose the smaller diff).
- Exit 1 also when a lifecycle entry has an error or a fresh lifecycle orphan remains.
- Human output: a second table "Lifecycle records" (action id, Mission, work package, started, age, action, commit) printed by a new helper, and a one-line commit summary.
- Help: `--close-stale` → `Close open Ops and work-package lifecycle records older than --threshold as abandoned (closed_by=doctor_sweep)`; the command docstring names lifecycle records. Update the golden at `test_doctor_cli_surface_golden.py:385-389`.

### Subtask T011 – Docs

- `docs/context/ops-vs-missions.md:113`: replace "There is no close command for lifecycle records" with the sweep route.
- `docs/architecture/trail-model.md` (lifecycle section): the `abandoned` phase, written and committed by the sweep, add-only.
- Regenerate `docs/api/cli-commands.md` with `uv run --frozen python -m scripts.docs.build_cli_reference` (never hand-edit) and run `tests/architectural/test_docs_cli_reference_parity.py`.
- Changelog fragment `docs/changelog/unreleased/7346-close-stale-lifecycle-records.fixed.md` (format: `docs/changelog/unreleased/README.md`), checked with `scripts.docs.check_changelog_style` and `scripts.docs.check_spelling --pass unreleased`.

---

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/invocation/ tests/specify_cli/next/test_next_invocation_lifecycle_seam.py tests/cli/test_doctor_default_run.py tests/specify_cli/session_presence/test_open_ops.py tests/architectural/test_event_log_writes_gate.py tests/architectural/test_archive_root_byte_identical.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py -q -p no:cacheprovider -n 6 --dist loadfile
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_lifecycle_read_seam_migration.py tests/integration/test_next_lifecycle_records.py -q -p no:cacheprovider   # out of matrix
make test-fast
```

`test_doctor_ops.py::test_sweep_real_closes_against_large_spine_under_2s` is already red on main (#5052): classify it, do not chase it.

## Definition of Done

- T006 red commit first; green at the end.
- `doctor ops --close-stale --threshold 0` on this repository's own `kitty-ops/lifecycle/` (in a scratch clone) closes the 123 orphans and `doctor invocation-pairing` then reports 0 (SC-001); report the numbers in the WP history.
- ruff, format and mypy clean; complexity ≤ 15 everywhere touched.

## Risks

- The executor refactor (T008) must be behavior-preserving; run the executor and Op-commit tests before and after.
- `doctor.py` hot file: keep hunks small.
- The perf budget (NFR-003): measure `close_stale_lifecycle_records` over ~1,650 records with no orphans.

## Reviewer Guidance

- No second commit implementation: the Op sweep and the lifecycle sweep share `commit_trail_paths`.
- The JSON keeps every existing key's meaning; `lifecycle_records` is additive.
- Mission files byte-identical (the FR-004 test is non-vacuous: it seeds Mission files).
- The protected-branch path never uses an override.
