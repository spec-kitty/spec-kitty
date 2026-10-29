---
work_package_id: WP06
title: '#6271 landing follow-ups'
dependencies: []
requirement_refs:
- FR-015
- FR-016
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: fc96086d13f16790f25c2e9dd6525dece8472aa4
created_at: '2026-10-27T19:00:06.755008+00:00'
subtasks:
- T024
- T025
- T026
phase: Phase 1 - Foundations
history:
- at: '2026-10-27T19:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/validate.py
create_intent:
- tests/status/test_validate_seed_predicate_6271.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/validate.py
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/test_wall_clock_claim_p0_repro.py
- tests/status/test_validate_seed_predicate_6271.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – #6271 landing follow-ups

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item and record each change with `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Objectives & Success Criteria

Resolves issue #6271 (folded into this mission by the operator on 2026-10-27), together with WP05's changelog citation fix.

- `validate_timestamp_continuity` (`src/specify_cli/status/validate.py:~190-242`) skips reconstruction seeds through the shared `specify_cli.status.is_migration_actor` predicate instead of its own `str(actor).startswith("migration:")` check, so a structured (dict) actor whose tool is `migration:…` is recognised the same way the reducer recognises it (FR-015). The local `_RECONSTRUCTION_SEED_ACTOR_PREFIX` constant goes away if nothing else uses it (grep first).
- Every code/test docstring that cites the diary-reducer fix as `spec-kitty-events#101` names it correctly: the fix is spec-kitty-events **PR #102**, the defect is **issue #101** (FR-016). Sites on origin/main: `src/specify_cli/status/validate.py:209`, `src/specify_cli/consolidation/reconciliation.py:30` and `:1480`, `tests/consolidation/test_wall_clock_claim_p0_repro.py:4`. The changelog site belongs to WP05.
- Behaviour otherwise unchanged: these remain warnings; `validate` still passes on the same logs.

## Context & Constraints

- Triage on #6271 (2026-10-19): name both with their correct meaning (issue #101, PR #102); do not replace every `#101` blindly. Suggested wording: "spec-kitty-events PR #102 (fixing issue #101)".
- `is_migration_actor` lives in `src/specify_cli/status/models.py` and is exported from `specify_cli.status`; it accepts `ActorField | None`. `validate_timestamp_continuity` receives raw event dicts, so the `actor` value may be a string or a dict; pass it straight through (a dict is projected through `actor_identity_str`). Guard against a non-`str`/`dict` value by treating it as not a seed.
- WP02 (parallel) widens `decode_actor` and touches `status/models.py`; this WP only *calls* `is_migration_actor` and must not edit `models.py`.
- `reconciliation.py` is large and owned by consolidation; edit only the two docstring lines.

## Branch Strategy

- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

```bash
spec-kitty agent action implement WP06 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T024 – Red-first test

- **File**: `tests/status/test_validate_seed_predicate_6271.py` (new).
- Build a small list of event dicts for one WP: a normal transition `planned -> claimed`, then a seed transition whose `actor` is the dict `{"tool": "migration:backfill", "role": None, "profile": None, "model": None}` with a `from_lane` that does NOT match the running lane, then a normal transition. Assert `validate_timestamp_continuity(events)` returns no finding for the seed event (RED today: the string check does not see the dict). Add a control: the same seed with a plain string actor `"migration:backfill"` is also skipped (green before and after), and a non-seed dict actor with a mismatched `from_lane` IS flagged.
- Commit alone first: `test(status): seed check must see structured migration actors (#6271)`.

### Subtask T025 – Shared predicate

- Replace the string check with `if is_migration_actor(_actor_or_none(event.get("actor"))): continue`, or inline the type guard; keep complexity ≤ 15 (the function is close; extracting the per-event skip test into a small helper is fine).
- Remove `_RECONSTRUCTION_SEED_ACTOR_PREFIX` if unused; update the docstring sentence that mentions reconstruction seeds to point at the shared predicate.

### Subtask T026 – Citations [P]

- Edit the four docstring sites listed above.
- `git grep -n "spec-kitty-events#101"` afterwards in `src/` and `tests/` must show no remaining fix citation; any remaining `#101` must clearly mean the issue.

## Test Strategy

```bash
/home/user/spec-kitty/.venv/bin/python -m pytest tests/status/test_validate_seed_predicate_6271.py tests/status/test_doctor.py tests/consolidation/test_wall_clock_claim_p0_repro.py -q
/home/user/spec-kitty/.venv/bin/python -m pytest tests/status -q -k "validate or continuity"
/home/user/spec-kitty/.venv/bin/ruff check <touched>; /home/user/spec-kitty/.venv/bin/ruff format --check --force-exclude <touched>
/home/user/spec-kitty/.venv/bin/mypy src/specify_cli/status/validate.py
```

## Risks & Mitigations

- None material: warning-only check; docstrings only in consolidation.

## Review Guidance

- Red-first commit precedes the fix; only docstrings change in `reconciliation.py`; citations name PR #102 and issue #101 correctly.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP06 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T024 --status done`.
