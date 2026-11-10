---
work_package_id: WP01
title: The abandoned lifecycle phase
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- NFR-001
- C-002
- C-004
planning_base_branch: feat/7346-close-stale-lifecycle-records
merge_target_branch: feat/7346-close-stale-lifecycle-records
branch_strategy: Planning artifacts for this mission were generated on feat/7346-close-stale-lifecycle-records. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7346-close-stale-lifecycle-records unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-10T09:29:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/invocation/
create_intent:
- tests/specify_cli/invocation/test_lifecycle_abandoned_7346.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/invocation/record.py
- src/specify_cli/invocation/lifecycle.py
- tests/specify_cli/invocation/test_lifecycle_abandoned_7346.py
- docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The abandoned lifecycle phase

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
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- `abandoned` is a valid lifecycle record phase: it serializes, parses back, and a reader no longer skips it.
- Pairing counts `abandoned` as a completion everywhere: `LifecycleGroup.completions`, `is_orphan`, `compute_pairing_rate`, `doctor_orphan_report`, `find_latest_unpaired_started`.
- The unpaired tail of a group is computed by one helper, used by every caller that needs it (two copies today).
- `write_abandoned_completion(repo_root, *, started, reason, at=None)` writes one `abandoned` record through `append_lifecycle_record` and returns the written path.
- ADR 2026-11-01-2 carries an amendment that names the new phase and its writer.

## Context & Constraints

- Spec: `kitty-specs/close-stale-lifecycle-records-01M72B89/spec.md` (FR-001, FR-002, FR-005, NFR-001, C-002, C-004).
- Plan, data model and research in the same directory. The operator ruled for a NEW phase (Decision Moment `01M72B8Z4FQ7J02B2HJ0ZNTC25`); do not fall back to `failed` with a reason.
- ADR `docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md`: one file per record, created once, never rewritten or removed.
- The lifecycle writes gate `tests/architectural/test_event_log_writes_gate.py` pins exactly one locked caller of `append_event_log_lines` in `lifecycle.py`. Write through `append_lifecycle_record`; add no raw append.
- Pairing stays keyed on `(mission_id, canonical_action_id)` (C-004).
- Charter: ATDD-first, red-first commit before implementation; complexity ≤ 15; mypy and ruff clean; no suppressions.

## Branch Strategy

- **Strategy**: single_branch (settled at finalize; two work packages).
- **Planning base branch**: `feat/7346-close-stale-lifecycle-records`
- **Merge target branch**: `feat/7346-close-stale-lifecycle-records`
- Work runs in the write checkout on the Mission branch `kitty/mission-close-stale-lifecycle-records-01M72B89`; `lanes.json` names the one repo-root lane. Start with:

  ```bash
  spec-kitty agent action implement WP01 --agent claude --profile python-pedro --mission close-stale-lifecycle-records-01M72B89
  ```

---

## Subtasks & Detailed Guidance

### Subtask T001 – Failing tests first

**Purpose**: pin the behavior before writing code (charter ATDD-first; Standing Order 4).

**Steps**: create `tests/specify_cli/invocation/test_lifecycle_abandoned_7346.py` (`pytestmark = pytest.mark.unit`) with:

1. `ProfileInvocationRecord.from_dict({... "phase": "abandoned" ...})` parses, and `to_dict()` round-trips `phase`, `reason` and `metadata`.
2. A group `[started]` plus an `abandoned` record of the same `(mission_id, canonical_action_id)` is not an orphan (`find_orphans` returns nothing).
3. `compute_pairing_rate([started, abandoned])` is `1.0`.
4. `find_latest_unpaired_started([started, abandoned])` is `None`; with a second `started` it returns that second one.
5. `doctor_orphan_report(tmp_path)` over files written by `write_started` then `write_abandoned_completion` reports `orphan_count == 0`.
6. `write_abandoned_completion(tmp_path, started=..., reason="abandoned by doctor ops --close-stale (older than 24h)")`:
   - returns a path under `kitty-ops/lifecycle/`;
   - the file holds one line whose `phase` is `abandoned`, whose `canonical_action_id`, `agent`, `mission_id` and `wp_id` equal the started record's, whose `reason` is the given reason, and whose `metadata` is `{"closed_by": "doctor_sweep"}`;
   - no other file under `kitty-ops/lifecycle/` changed (snapshot bytes before and after).
7. `read_lifecycle_records` returns the `abandoned` record (it is not skipped).

Run them and confirm they fail for the right reason (unknown phase, missing function), then commit the tests alone: `test(lifecycle): pin the abandoned lifecycle phase (#7346)`.

### Subtask T002 – The contract value

**Steps**:
1. `src/specify_cli/invocation/record.py:242`: `ProfileInvocationPhase = Literal["started", "completed", "failed", "abandoned"]`.
2. `from_dict` (:307): accept the four values; update the error text to name all four.
3. Update the class docstring: a `started` record is paired by exactly one `completed`, `failed` or `abandoned` record; `abandoned` means the doctor sweep closed it, not the action.

### Subtask T003 – One completion predicate, one unpaired tail

**Steps**:
1. In `src/specify_cli/invocation/lifecycle.py` add a module constant `COMPLETION_PHASES: frozenset[str] = frozenset({"completed", "failed", "abandoned"})` and use it in `LifecycleGroup.completions` (:210) and `compute_pairing_rate` (:302). `grep -rn '"completed", "failed"' src` must then find nothing.
2. Add a public `unpaired_started(group: LifecycleGroup) -> tuple[ProfileInvocationRecord, ...]`: the last `deficit` started records, empty when the group is balanced. Replace the inline slices in `find_latest_unpaired_started` (:276-277) and `doctor_orphan_report` (:337-338) with it.
3. Add it to `__all__` if the module declares one (it does not today; the dead-symbol gate covers only `charter`/`kernel`). It must have a caller in `src/` (it will: both functions above, and WP02's sweep).
4. Update the module docstring "Pairing semantics" to name `abandoned`.

### Subtask T004 – The abandoned writer

**Steps**: add beside `write_paired_completion`:

```python
#: ``metadata`` stamped on a record the doctor sweep writes.
ABANDONED_BY_DOCTOR_SWEEP: dict[str, str] = {"closed_by": "doctor_sweep"}

def write_abandoned_completion(
    repo_root: Path,
    *,
    started: ProfileInvocationRecord,
    reason: str,
    at: datetime | None = None,
) -> Path:
    """Append an ``abandoned`` record paired with ``started``; return its file path (#7346)."""
```

- Copy `canonical_action_id`, `agent`, `mission_id`, `wp_id` verbatim (FR-011 of the lifecycle contract: never recompute the id).
- Refuse a `started` argument whose phase is not `started` (`ValueError`).
- Write through `append_lifecycle_record` and return its path. Keep `write_paired_completion` unchanged: it still refuses anything other than `completed`/`failed` from `next` (the sweep is the only `abandoned` writer).

### Subtask T005 – The ADR amendment

**Steps**: append to `docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md` an `## Amendment 2026-11-10: an abandoned record closes a stale lifecycle record (#7346)` section (Reader / Problem / Decision / Consequences, plain language):
- the new phase and what it means (closed by `doctor ops --close-stale`, not the action's result);
- the second writer (`write_abandoned_completion`), still through the one locked append, still one new file, never a rewrite;
- pairing counts it as a completion;
- an older CLI skips the record and keeps reporting the orphan (accepted, operator ruling);
- the `updated:` frontmatter date.

Run `tests/docs/test_adr_content_invariance.py` and `tests/docs/test_docs_structural_lint.py`.

---

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/invocation/test_lifecycle_abandoned_7346.py tests/specify_cli/invocation/test_lifecycle_pairing.py tests/specify_cli/invocation/test_lifecycle_per_record.py tests/specify_cli/invocation/test_locked_lifecycle_and_propagation.py tests/specify_cli/next/test_next_invocation_lifecycle_seam.py tests/architectural/test_event_log_writes_gate.py tests/architectural/test_archive_root_byte_identical.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_structural_lint.py -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_lifecycle_read_seam_migration.py -q -p no:cacheprovider   # out of matrix: run locally
.venv/bin/ruff check src/specify_cli/invocation/ && .venv/bin/ruff format --check --force-exclude src/specify_cli/invocation/record.py src/specify_cli/invocation/lifecycle.py
.venv/bin/mypy src/specify_cli/invocation/record.py src/specify_cli/invocation/lifecycle.py
```

## Definition of Done

- T001 tests committed red first, green at the end.
- No `("completed", "failed")` literal left in `src/`.
- The ADR amendment reads plainly and passes the docs gates.
- ruff, format and mypy clean; complexity ≤ 15.

## Risks

- `pair_previous_lifecycle_record` (`runtime/next/next_invocation_lifecycle.py:138`) pairs `next --result` with `find_latest_unpaired_started`. After this WP, a swept record is no longer unpaired, so `next` cannot pair with it. That is intended; the seam test must stay green.

## Reviewer Guidance

- Check every completion count reads `COMPLETION_PHASES` and every unpaired tail reads `unpaired_started`.
- Check the writer appends a new file only (snapshot test) and copies the canonical id verbatim.
- Check the red commit precedes the implementation commit.
