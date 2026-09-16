# Contract: Terminal-Cancel Verdict (4a) + Stale-Running Sweep (4b)

## 4a — `scripts/ci/fleet_verdict.py`

- `classify(runs, labels) -> str` gains `infra-error` per the precedence in `data-model.md` (rule 4, inserted between the incomplete check and the green line). The `:95` green line, the dedup guard (`:325-331`), and the recognition regex (`:323`, already lists `infra-error`) are **unchanged**.
- `comment_body(...)` adds one plain-language line when `state=="infra-error"`: a required run was cancelled (infra/timeout kill), not a code failure; re-run to release the head.
- `classify` docstring names `infra-error`.
- `scripts/ci/fleet_main.py` is **not edited** (reuses `classify`); its P0 gate stays `state != "red"` so `infra-error` opens no incident.

### 4a test obligations (red-first on today's code)
1. `test_terminal_cancel_reposts_and_is_not_suppressed` — full `report()`: seed latest bot comment `[ci] running @HEAD`, one required gate `completed/cancelled`; assert today `not api.posts`, after-fix `api.posts[0]["body"].startswith("[ci] infra-error @HEAD")`. (template `:242`)
2. flip `test_fleet_verdict.py:175` `("completed","cancelled","running")`→`infra-error`; keep `:176` `skipped→running`.
3. flip `test_fleet_verdict.py:319` `("cancelled","running")`→`("cancelled","infra-error")`.
4. `test_cancel_among_pending_runs_stays_running` — `{cancelled, in_progress}` and `{cancelled, None}` → running (INV-2).
5. `test_failure_and_cancel_is_red` (INV-3); `test_deferred_not_overridden_by_cancel` (INV-4); `test_all_success_green_never_infra` (INV-1).
6. migrate `test_fleet_main.py:109` — `cancelled→infra-error` + `not api.mutations` (no P0); `skipped`/`None→running`.
7. `test_infra_error_tip_appended_to_open_incident_does_not_escalate`.

## 4b — `scripts/ci/stale_running_sweep.py` (new) + `.github/workflows/ci-stale-running-sweep.yml` (new)

- `find_stale_running(...) -> list[StaleHead]` per `data-model.md` — pure, no I/O.
- `main()`: `gh` at the edge (list open PRs + `[ci]` comments + required runs; `main` head); surface = idempotent `[ci-sweep]` watch comment + `::warning::`. NEVER a `[ci] <state>` verdict, never edits reporter comments, never re-triggers.
- Workflow: `on: schedule + workflow_dispatch`; invokes `python3 scripts/ci/stale_running_sweep.py`.

### 4b test obligations
1. red-first detector: stale detected (latest running + all runs terminal); NOT stale (latest terminal); NOT stale (a run in_progress); fail-closed on partial evidence.
2. idempotency: second run against an already-flagged head yields no duplicate surface.
3. execution-grounded wiring guard: the workflow step invokes `scripts/ci/stale_running_sweep.py`.

## Frozen (assert unchanged)

```yaml
# round-trip: skip: illustrative contract anchors, not a parseable mission artifact
frozen:
  - path: scripts/ci/router_gate.py          # separate unrelated classify (C-001)
  - path: scripts/ci/fleet_verdict.py
    parts: ["dedup running-guard ~:325-331", "recognition regex ~:323", "green line ~:95"]
  - path: .github/workflows/ci-fleet-verdict.yml   # Stage-1 concurrency levers (C-002)
```
