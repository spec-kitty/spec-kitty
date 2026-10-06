# Data model: composition-advance-alignment

No new entities. These existing structures change in what composition-backed runs carry:

- **AdvancePlan** (`engine.AdvancePlan`, frozen pydantic). Fields: `source`, `snapshot`, `decision`, `result`, `completed_step_id`, `significance`. It is now the only advance-plan type; the adapter's `CompositionAdvancePlan` is removed.
  - Invariant: `commit_advance` commits only when the persisted snapshot equals `source`. Otherwise it raises `StaleAdvancePlan` and writes nothing.
- **MissionRunSnapshot.decisions** (`state.json`). On composition-backed runs it gains `raci:<issued step>`, `raci:<audit step>` and `significance:audit:<audit step>`, the same values the engine path records.
- **run.events.jsonl**. On composition-backed runs it gains `SignificanceEvaluated`, placed after `NextStepAutoCompleted` and before the issuance or request event.

## Commit order (both advances)

1. `NextStepAutoCompleted`, when a step completed
2. `SignificanceEvaluated`, when an audit gate was evaluated
3. One of:
   - `NextStepIssued`;
   - `DecisionInputRequested`, first occurrence only;
   - on a terminal decision with a completed step: `before_run_completed` guard, then `MissionRunCompleted`.
4. `state.json` written

After this, the composition adapter alone runs the non-blocking retrospective capture.
