---
work_package_id: WP03
title: Created-artifacts record integrity
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- C-003
- C-004
- SC-001
- SC-003
- NFR-003
planning_base_branch: issue-6453-synthesis-record-integrity
merge_target_branch: issue-6453-synthesis-record-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-6453-synthesis-record-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6453-synthesis-record-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesis-record-integrity-01M5ZBC9
base_commit: 63ee573e13f02bed62b7455b4cb27f0deffd5fe5
created_at: '2026-10-27T20:31:50.378395+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Remediation
history:
- at: '2026-10-27T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/reach_only.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
- docs/api/charter-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Created-artifacts record integrity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission synthesis-record-integrity-01M5ZBC9`).
- Address all feedback before your work is complete; record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- #6453 (FR-001, FR-004): the read-merge-write of `.kittify/charter/synthesized-artifacts.yaml` in `append_synthesized_activations` runs under `synthesis_lock` (from WP02), so two concurrent writers never lose an id and a removed artifact stays removed.
- #6455 (FR-005, FR-006): the unreadable-record warning keeps its `{path} is unreadable` prefix, says nothing was added to an activation list, tells the operator to restore the file from version control (`git checkout -- <path>`, or from an earlier commit) or repair its YAML keeping every listed id, and warns that deleting the file makes synthesis forget which artifacts it created and re-add ones the operator removed. Per triage: no `doctor` check, no `--repair` (C-003). Keep #6454's fail-closed fallback unchanged (C-004).

## Context & Constraints

- Spec US1/US2, FR-001/004/005/006; plan IC-02 (record wrapper) and IC-03.
- `src/charter/activation/synthesizer/reach_only.py` (origin/main `581b5c46`): `_UNREADABLE_RECORD_WARNING` `:56-58`; `_load_record_file` `:84-94` (missing file = empty); `_read_record` `:104-113` (legacy `synthesized-tactics.yaml` unioned); `_write_record` `:116-120`; `append_synthesized_activations` `:243-293` (read `:265`, warning `:266-267`, record write via `_record()` `:277-289`, `restamp_bundle_hash` `:290-292`).
- Existing assertions that must stay green: `tests/charter/synthesizer/test_synthesize_activation_append.py:174-183` and `tests/charter/synthesizer/test_styleguide_reach_only.py:420` (`is unreadable` substring).
- Complexity: `append_synthesized_activations` is near the ceiling; take the lock in a thin wrapper (rename the body to a private `_append_synthesized_activations_locked`, or wrap with `with synthesis_lock(repo_root):` at the top) without adding branches.
- Import `synthesis_lock` from `charter.activation.synthesizer.synthesis_lock` (same package; not via `api`).

## Branch Strategy

- **Planning base branch**: issue-6453-synthesis-record-integrity
- **Merge target branch**: issue-6453-synthesis-record-integrity

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first race test

- Through the real entry point `append_synthesized_activations(root, {"tactic": [s]})`, two threads, record starts `{t1}`, writers add `t2` and `t3`. For FR-001, neutralize the config path (`_activation_write_target` → `None`, `_manifest_slugs` → empty) via `monkeypatch` so only the record is written.
- **Red-first commit** (against today's code): a `threading.Barrier(2, timeout=5)` after `_read_record` (wrap it) shows `t2` or `t3` lost. Commit it as `xfail(strict=True)` is NOT acceptable as the final state; the red commit may be a plain failing test.
- **After T012**: replace the barrier with a deterministic handshake that works with the lock: writer A pauses inside `_write_record` on `Event a_may_write` (wait with timeout); writer B's first failed `kernel.locks._LockCore.try_lock_once` (wrap the method via monkeypatch to set `b_blocked` when it returns False) sets `a_may_write`; join both with timeouts; assert the record is `{t1,t2,t3}` (FR-001). Add FR-004 with a REAL explicit `activated_tactics` config (do NOT stub `_activation_write_target`; a stub makes the re-append unobservable): `t2` recorded but removed from the list by the operator; concurrent runs regenerating `t2` leave it absent from `activated_tactics` after both threads finish (positive control: a never-recorded `t4` IS appended).
- Every wait has a timeout so a regression fails, never hangs.

### Subtask T012 – Lock the read-merge-write

- Wrap the WHOLE body of `append_synthesized_activations` in `synthesis_lock(repo_root)` (the `_eligible` calls at `:258-260` already read deny state); the nested `restamp_bundle_hash` is re-entrant after WP02. Move the body to a private helper so the public function stays a thin wrapper. Docstring: say the record's read-merge-write is serialized across synthesis runs (#6453).

### Subtask T013 – Warning

- Red-first: extend/add a test in `test_synthesize_activation_append.py` (malformed `synthesized-artifacts.yaml`, e.g. `": :"` or a non-mapping) asserting the warning contains the path, `is unreadable`, a `git checkout --` restore hint, "keep" the ids wording, and the deletion caution (re-adds removed artifacts). Then rewrite `_UNREADABLE_RECORD_WARNING`. Keep it one message; suggested shape:
  `"{path} is unreadable; no synthesized artifact was added to an activation list. Restore it from version control (`git checkout -- {path}`, or from an earlier commit) or fix its YAML by hand, keeping every listed id. Do not delete it: synthesis would forget which artifacts it created and add back ones you removed. To activate one artifact now, run `spec-kitty charter activate <kind> <id>`."`
  The `{path}` passed today is the path from `_UnreadableRecordError` (posix string). Make sure the message is correct when the offending file is the legacy record.

### Subtask T014 – Legacy record path

- Malformed `.kittify/charter/synthesized-tactics.yaml` (current record absent/valid): the warning names the legacy file with the same guidance (exercises `_read_record`'s legacy branch).

### Subtask T015 – Docs

- `docs/api/charter-commands.md`: fix `:199-200` and `:249`, which say re-synthesis replaces legacy `applies` edges on every synthesized artifact (now: only artifacts the run regenerated; others keep the edge until regenerated, #6456). Document the `CHARTER_SYNTHESIS_LOCK_HELD` refusal (one writing synthesis run per worktree; wait ~10 s, then refuse; `--dry-run`/`--dry-run-evidence`/`--list-topics` take no lock, #6453) and the unreadable-record repair guidance (restore or repair, never delete, #6455). Run `uv run python -m scripts.docs.check_docs_freshness --ci` if it covers the page.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/test_synthesize_activation_append.py tests/charter/synthesizer/test_styleguide_reach_only.py tests/charter/synthesizer/ -q
uv run --frozen ruff check src/charter/activation/synthesizer/reach_only.py tests/charter/synthesizer/test_synthesize_activation_append.py
uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy src/charter/activation/synthesizer/reach_only.py
```

## Risks & Mitigations

- Barrier test hangs once the lock works → only in the red-first commit; replaced by the Event handshake.
- Patching `_LockCore.try_lock_once` reaches into a private kernel class: keep it test-local via `monkeypatch`, and assert the spy fired (non-vacuity).

## Review Guidance

- Red-first commit shows the lost id; final test is deterministic (no sleeps) and non-vacuous (spy fired).
- Warning keeps the `is unreadable` prefix and contains repair + deletion caution.
- #6454 fallback untouched.

## Progress & Status

Use `spec-kitty agent tasks add-history WP03 --note "..."`, `mark-status`, and `spec-kitty agent tasks status`.
