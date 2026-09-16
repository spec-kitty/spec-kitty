---
work_package_id: WP02
title: '4b: reactive stale-running sweep backstop'
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- NFR-003
- NFR-004
planning_base_branch: fix/ci-terminal-cancel-verdict
merge_target_branch: fix/ci-terminal-cancel-verdict
branch_strategy: Planning artifacts for this mission were generated on fix/ci-terminal-cancel-verdict. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-terminal-cancel-verdict unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-terminal-cancel-verdict-01M2NC7Z
base_commit: b048d613ad50bb3ee61af58e653415c9586075d8
created_at: '2026-09-16T17:43:15.925913+00:00'
subtasks:
- T006
- T007
- T008
- T009
history:
- at: '2026-09-16T17:37:36Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/stale_running_sweep.py
- tests/ci/test_stale_running_sweep.py
- .github/workflows/ci-stale-running-sweep.yml
execution_mode: code_change
owned_files:
- scripts/ci/stale_running_sweep.py
- tests/ci/test_stale_running_sweep.py
- .github/workflows/ci-stale-running-sweep.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ci-terminal-cancel-verdict-01M2NC7Z --json`). Apply + state what you applied. Force `PYTHONPATH=$(pwd)/src` on every pytest.

## Objective
Build the 4b reactive **stale-running sweep** backstop: a scheduled workflow that detects any head whose latest `[ci]` verdict is `running` while its required runs are all terminal (the cancelled-reporter / cancelled-main wedge 4a cannot reach), and surfaces it as an idempotent `[ci-sweep]` watch item — **never** auto-releasing the head, posting a `[ci] <state>` verdict, editing the reporter's comments, or re-triggering CI.

**Operator-ratified design:** host = a NEW dedicated `.github/workflows/ci-stale-running-sweep.yml` (schedule + workflow_dispatch); surface = a de-duplicated `[ci-sweep]` watch comment on the affected PR + a `::warning::` annotation.

Read first: `../spec.md` (US3, FR-007/008), `../research.md` (D-05), `../data-model.md` (find_stale_running + SW-1/2/3), `../contracts/terminal-cancel.contract.md`. Template for the pure/edge shape: `scripts/ci/select_source_artifacts.py` and `scripts/ci/source_eligibility.py` (pure decision, gh at the edge, injected JSON). You may IMPORT read-only from `scripts/ci/fleet_verdict.py` (the `[ci] <state> @<head>` recognition regex, the `GitHub` client) — do NOT edit fleet_verdict.py.

## Subtasks

### T006 — Red-first detector tests (write FIRST)
`tests/ci/test_stale_running_sweep.py`: cover `find_stale_running(...)` (pure) —
- STALE: a head whose latest `[ci]` verdict is `running @<sha>` AND all required runs are `status=="completed"` (incl. one `cancelled`) → flagged.
- NOT stale: latest verdict is terminal (green/red/infra-error) → not flagged (reporter already released).
- NOT stale: a required run still `in_progress`/`queued` → not flagged (evidence pending) — SW-3 fail-closed.
- IDEMPOTENT (SW-2): given an existing `[ci-sweep]` marker/fingerprint for the head, the surface decision yields "already-flagged, no repost".
Watch them fail (module absent).

### T007 — Implement the pure detector + edge main()
`scripts/ci/stale_running_sweep.py`: `find_stale_running(candidates) -> list[StaleHead]` per data-model (pure, no I/O). `main()`: `gh` at the edge lists open PRs (+ the `main` head), their latest `[ci]` comment, and required runs; for each stale head, post/update ONE de-duplicated `[ci-sweep]`-namespaced watch comment (NOT a `[ci] <state> @head` verdict) + print a `::warning::`. Idempotent by an embedded fingerprint marker. NEVER: post `[ci] <state>`, edit/delete reporter comments, re-trigger CI, or auto-release (C-003/FR-008/SW-1).

### T008 — The scheduled workflow
`.github/workflows/ci-stale-running-sweep.yml`: `on: schedule (a reasonable cron, e.g. every few hours) + workflow_dispatch`; minimal `permissions:` (`pull-requests: write`, `contents: read`, `issues: read` as needed — least privilege for the watch comment); a single job that checks out and runs `python3 scripts/ci/stale_running_sweep.py`. Keep it OUT of ci-nightly.yml.

### T009 — Wiring guard + gates
Add to `tests/ci/test_stale_running_sweep.py` an execution-grounded wiring guard: load `ci-stale-running-sweep.yml`, assert the run step invokes `scripts/ci/stale_running_sweep.py` (not inline logic). Gates: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/test_stale_running_sweep.py -q`; `tests/ci/ -q`; `ruff check .`; `ruff format --check .`; `mypy scripts/ci/stale_running_sweep.py`; download `actionlint` and run it on the new workflow, paste RAW output (do NOT self-report "0"); `tests/architectural/test_no_legacy_terminology.py`.

## Branch Strategy
Planning/base + merge target: `fix/ci-terminal-cancel-verdict`. Independent write-scope → own lane, parallel with WP01. Enter via `spec-kitty implement WP02`.

## Definition of Done (non-fakeable)
- `find_stale_running` is pure, red-first tested across stale / not-stale-terminal / not-stale-in-flight / idempotent.
- The sweep surfaces ONLY (idempotent `[ci-sweep]` comment + annotation); it never posts `[ci] <state>`, edits reporter comments, re-triggers, or auto-releases (assert the negative in tests where feasible).
- The new workflow is minimal-permission, schedule+dispatch, and invokes the shipped module (execution-grounded wiring guard).
- ruff + format + mypy + terminology clean; `actionlint` RAW output pasted; tests/ci green.

## Risks / reviewer guidance
- **Authority creep (highest):** confirm the sweep can NEVER release the head or post a `[ci] <state>` verdict — it is a backstop, not the reporter (C-003). Reject any code path that edits the reporter's comments or re-triggers CI.
- **False watch items:** fail-closed on partial evidence (a run still in-flight must NOT be flagged).
- **Idempotency:** a second scheduled run must not spam the PR.
- Do NOT edit `fleet_verdict.py` (import only).
