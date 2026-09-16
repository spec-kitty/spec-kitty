---
work_package_id: WP01
title: '4a: infra-error terminal-cancel class in the shared classifier'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: fix/ci-terminal-cancel-verdict
merge_target_branch: fix/ci-terminal-cancel-verdict
branch_strategy: Planning artifacts for this mission were generated on fix/ci-terminal-cancel-verdict. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-terminal-cancel-verdict unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-terminal-cancel-verdict-01M2NC7Z
base_commit: b97f37ba7565cfc3bdac79e7f8c0fc412b4537f0
created_at: '2026-09-16T17:42:04.308557+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- at: '2026-09-16T17:37:36Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent: []
execution_mode: code_change
owned_files:
- scripts/ci/fleet_verdict.py
- tests/ci/test_fleet_verdict.py
- tests/ci/test_fleet_main.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ci-terminal-cancel-verdict-01M2NC7Z --json`). Apply + state what you applied. Force `PYTHONPATH=$(pwd)/src` on every pytest. The Bash tool runs zsh — never pass a multi-file var unquoted.

## Objective
Add a terminal-cancel verdict class `infra-error` to `classify()` in `scripts/ci/fleet_verdict.py` so a fully-terminal required set with a cancelled run (no red) yields `infra-error` — a never-green, never-premature class that the dedup running-guard does NOT suppress, releasing the PR head. `fleet_main.py` reuses `classify` so the main path is coherent for free (only its TEST migrates).

Read first: `../spec.md`, `../research.md` (D-02 precedence, D-03 release mechanism, D-04 main coherence, D-06 tests), `../data-model.md` (precedence table + INV-1..5), `../contracts/terminal-cancel.contract.md`. The fake `API` harness is `tests/ci/test_fleet_verdict.py:58-97`; the release-test template is `test_fleet_verdict.py:242` (`test_running_ledger_does_not_suppress_a_terminal_verdict`).

## ⚠️ Frozen (do NOT modify)
- `scripts/ci/router_gate.py` — a SEPARATE unrelated `classify` (name collision only). C-001.
- `fleet_verdict.py` dedup running-guard (~:325-331), recognition regex (~:323, already lists infra-error), and the green line (~:95). C-002/C-004.
- `.github/workflows/ci-fleet-verdict.yml` — Stage-1 concurrency levers. `scripts/ci/fleet_main.py` — NO code edit (reuses classify; only its test changes).

## Subtasks

### T001 — Red-first tests for classify precedence + release (write FIRST, watch fail)
In `tests/ci/test_fleet_verdict.py` add/flip:
- `test_terminal_cancel_reposts_and_is_not_suppressed` (THE release pin, mirror :242): seed `api.comments=[{"body": f"[ci] running @{HEAD}", "user":{"type":"Bot"}}]`, make one required gate `completed/cancelled` (keep ci-modules/aggregate resolvable), call `report(...)`; assert TODAY `not api.posts` (running-guard suppresses), and post-fix `api.posts[0]["body"].startswith(f"[ci] infra-error @{HEAD}")`.
- Flip pinned `:175` `("completed","cancelled","running")` → `("completed","cancelled","infra-error")`; KEEP `:176` `("completed","skipped","running")`.
- Flip pinned `:319` param `("cancelled","running")` → `("cancelled","infra-error")`.
- `test_cancel_among_pending_runs_stays_running` (INV-2): `classify({g: completed/cancelled, h: {status:"in_progress"}}, set())=="running"` AND `classify({g: completed/cancelled, h: None}, set())=="running"`.
- `test_failure_and_cancel_is_red` (INV-3): `{failure, cancelled}` → "red". `test_deferred_not_overridden_by_cancel` (INV-4): `{cancelled}` + `{"pr:skip-ci"}` → "running". `test_all_success_green_never_infra` (INV-1): all-success → "green".
- `test_infra_error_tip_appended_to_open_incident_does_not_escalate` (fleet_main): an open red incident whose tip now observes infra-error appends a comment, incident stays open, priority unchanged.
Run: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/test_fleet_verdict.py -q` → expect reds. (If ModuleNotFoundError coverage/pytestarch → `uv sync --frozen --all-extras` first; category-4 false red.)

### T002 — Implement the infra-error branch in classify()
Insert between the incomplete check (~:93-94) and the green line (~:95):
```python
if all(r.get("status") == "completed" for r in present) and any(r.get("conclusion") == "cancelled" for r in present):
    return "infra-error"
```
This sits AFTER red (:89), AFTER deferred (:91), AFTER incomplete (:93); the `all(...completed)` conjunct prevents premature-fire; keyed on `cancelled` so skipped→running and timed_out→red are unchanged. Do NOT alter :95.

### T003 — comment_body infra-error line + docstring (FR-006)
In `comment_body` (~:279-281) add, when `state=="infra-error"`, one plain-language line: a required run was cancelled (infra/timeout kill), not a code failure — re-run to release the head. Update the `classify` docstring (:87) to name infra-error ("…never green; a terminally-cancelled required run is infra-error, never green, always released").

### T004 — Migrate test_fleet_main.py (main coherence)
In `tests/ci/test_fleet_main.py` the test at ~:109 pins `["cancelled","skipped",None]` all → `state=="running"`. Split: `cancelled` → `state=="infra-error"` AND `not api.mutations` (NO P0 opened — fleet_main.py:121 gate is `state != "red"`); `skipped`/`None` → `running` (no P0). Do NOT edit fleet_main.py itself.

### T005 — Gates (record commands + counts)
`PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py -q`; `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/ -q` (blast radius); `uv run --frozen ruff check .`; `uv run --frozen ruff format --check .` (SEPARATE); `uv run --frozen mypy scripts/ci/fleet_verdict.py`; `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.

## Branch Strategy
Planning/base + merge target: `fix/ci-terminal-cancel-verdict` (→ local main, then PR to upstream/main; operator merges). Enter workspace via `spec-kitty implement WP01`.

## Definition of Done (non-fakeable)
- The release test EXERCISES the full `report()` suppression path (not a bare classify assertion) and proves a fresh `[ci] infra-error @head` posts; red-first then green.
- All 5 invariants (INV-1..5) tested; pinned `:175`/`:319` flipped; `:176` skipped→running kept; `test_fleet_main.py:109` migrated (cancelled→infra-error + no P0).
- Green line `:95`, dedup guard/regex, router_gate.py, ci-fleet-verdict.yml, fleet_main.py code all UNCHANGED (verify `git show --stat`).
- ruff + format + mypy + terminology clean; tests/ci green.

## Risks / reviewer guidance
- **Precedence (highest):** confirm the infra-error branch is after red/deferred/incomplete and gated on `all present completed` — a `{cancelled, in_progress}` set MUST stay running (reviewer caught this). Confirm `{failure, cancelled}` → red (no infra-wash).
- **Never-green:** infra-error must require ≥1 cancelled; green path untouched.
- **Fakeable test:** reject a bare `classify(...)=="infra-error"` as the release proof — require the full report() path asserting the POST.
