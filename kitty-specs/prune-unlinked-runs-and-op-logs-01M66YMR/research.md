# Research — prune unlinked runs and Op-scoped glossary logs (#6739)

Discovery findings for `spec-kitty doctor event-logs` (#6610). Written on the
mission branch `issue-6739-prune-unlinked-runs-and-op-logs`, base
`origin/main@512567eee7`.

## Reproduction on current main (no supersession)

A throwaway project (`git init`; one merged Mission `001-done-mission`, one open
Mission `002-open-mission`; `.kittify/config.yaml` with `keep_runs: 0`,
`max_age_days: 30`), every file aged 90 days:

| Item | Shape | `doctor event-logs --json` today |
| --- | --- | --- |
| `.kittify/runtime/runs/<run>` | `state.json` carries `mission_id: null`, `mission_slug: null`, `inputs.mission_slug: "001-done-mission"`; **no** `feature-runs.json` entry | kept, `Mission not found` |
| `.kittify/runtime/runs/<run>` | `state.json` names no Mission at all; no index entry | kept, `Mission not found` |
| `.kittify/events/glossary/profile-invocation-<id>.events.jsonl` | the Op's `kitty-ops/<id>.jsonl` records a `completed` event | kept, `Mission not found` |
| `.kittify/events/glossary/profile-invocation-<id>.events.jsonl` | the Op's record has only `started` (Op still open) | kept, `Mission not found` |

Nothing is ever a candidate: `candidates: []`. The defect is live, and
`git log -S` shows no commit that touches it; `src/specify_cli/state/retention.py`
still carries `tracked with #6739` for the leftover-run residual. No ADR or
changelog entry supersedes the issue.

## Where the two families come from

- **Unlinked runs.** `runtime.next.runtime_bridge_io.get_or_start_run` writes a
  run snapshot with no Mission identity at the top level; the slug lives only in
  `state["inputs"]["mission_slug"]`. `next` links the run to its Mission through
  the run index (`feature-runs.json`). `retention._run_mission` reads the index
  entry first and falls back to the snapshot's **top-level**
  `mission_id`/`mission_slug` — never `inputs.mission_slug` — so a run whose index
  entry was replaced or removed resolves no Mission and is kept forever.
- **Op-scoped glossary logs.** `glossary.chokepoint` writes
  `.kittify/events/glossary/profile-invocation-<id>.events.jsonl` with
  `mission_id = profile-invocation-<id>`. `retention._collect_glossary_logs`
  resolves the log stem as a Mission id, so these match no Mission and are kept
  forever. In a real project they are most of the directory.

## The gap in the verdict rule

`_ledger_verdict` treats "no Mission resolved" as one state and keeps it. That is
correct for a *recorded* Mission identity this checkout does not know (operator
ruling 2026-10-23: a Mission on another branch is protected, `FR-008`), and wrong
for an item that names **nothing** at all — those have no owner whose state could
protect them, and no rule ever makes them eligible.

## Decisions

- **D1 — the snapshot's `inputs.mission_slug` is a legitimate link, not a
  relaxation.** The identity rule (`retention._mission_of_record`) is: a recorded
  `mission_id` is the only identity, and a slug is read only from a record that
  carries no `mission_id`. The production snapshot carries no `mission_id`, so
  reading its slug — from `mission_slug` or, when that is empty, from
  `inputs.mission_slug` — applies the existing rule rather than widening it. A
  linked run then follows its Mission's lifecycle exactly as an indexed one does.
- **D2 — "unlinked" is its own verdict.** An item that names no Mission (run) or
  no Op (log) is judged on age alone once it is outside the newest `keep_runs` of
  its kind: `past retention; no Mission recorded` (run) and
  `past retention; no Op recorded` (Op log). This retires the residual documented
  in `_delete_run` (a leftover empty run directory no rule could ever remove).
- **D3 — a recorded but unknown Mission keeps its protection.** `Mission not
  found` still keeps a run whose recorded `mission_id`/slug this checkout does not
  know, or resolves ambiguously. `DS-L2` (no first-match-wins) is untouched.
- **D4 — an Op log is protected by its Op's state.** An Op is open while its
  `kitty-ops/<id>.jsonl` record exists, carries no `completed` event, and is not
  on the closure spine `kitty-ops/op-closures.jsonl` — the predicate
  `specify_cli.doctor.ops.list_orphan_ops` already encodes. Open → kept,
  `Op is open`. Closed → eligible on age, `past retention; Op completed`. No
  record at all → unlinked, `past retention; no Op recorded`.
- **D5 — one owner for "is this Op open".** Promotion candidate: today the
  predicate is private to `doctor/ops.py` (`_has_completed_event` plus
  `invocation.writer.closed_invocation_ids`). A second copy in `state/retention.py`
  would be a second source of truth for what closes an Op, so the predicate moves
  next to the record it reads (`specify_cli/invocation/writer.py`) and
  `doctor/ops.list_orphan_ops` keeps its behaviour by calling it.
- **D6 — Op logs rank among themselves.** `kind` gains `op_log`; `keep_runs` keeps
  protecting the newest N of *each* kind, so a flood of Op logs cannot push a
  Mission's log out of the newest N.
- **D7 — locks and preview/apply parity are unchanged.** Lock probes still run
  only for items past both limits; `--apply` re-checks the lock and reports
  `lock held`; the preview reports exactly what `--apply` would delete.

## Evidence

- `src/specify_cli/state/retention.py` — `_read_snapshot_mission`,
  `_run_mission`, `_collect_glossary_logs`, `_ledger_verdict`, `_delete_run`
  (residual note naming #6739).
- `src/runtime/next/runtime_bridge_io.py` — `get_or_start_run`'s snapshot shape;
  `tests/core/test_event_log_retention.py::test_a_run_started_by_the_real_writer_becomes_a_candidate`
  asserts `(mission_id, mission_slug) == (None, None)` for a real run.
- `src/glossary/chokepoint.py` — `_build_event_context` writes
  `mission_id = profile-invocation-<invocation_id>`.
- `src/specify_cli/doctor/ops.py` — `list_orphan_ops`, `_NON_OP_JSONL`,
  `_has_completed_event`; `src/specify_cli/invocation/writer.py` —
  `closed_invocation_ids`, `kitty-ops` record layout.
- `src/glossary/checkpoint.py::load_checkpoint` scans every
  `.kittify/events/glossary/*.events.jsonl` for `StepCheckpointed`. Deleting a
  log only after its owner's work is over (and only past `max_age_days`) keeps
  every live resume point: a checkpoint is resumed inside its own invocation.
- ADR 2026-10-13-2 D-3 (local tier and `ledger.retention`), #6610, #5212,
  operator ruling 2026-10-28 (Op index out of scope) and 2026-10-23 (protect
  unknown Missions).

## Open questions

- None blocking. Two residuals are accepted and documented in the spec: an Op
  whose record lives in another checkout (#6682 owned-checkout custody) reads as
  "no Op recorded" here, and a run whose only recorded identity is a slug that no
  Mission directory in this checkout carries stays protected as `Mission not
  found` (D3). Both are age-gated behind `keep_runs` and `max_age_days` only in
  the first case; the second keeps the operator ruling intact.
