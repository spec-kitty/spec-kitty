# Contract: `next` envelope additions (additive)

updated: 2026-11-12

- **New key `next_command` (string).** It appears only when set, so existing payloads stay byte-identical.
  - On an advancing call, it is set on the gate's `blocked` answers (`MISSION_AWAITING_ACCEPTANCE`, `BOARD_STEP_NOT_DISPATCHABLE`).
  - On a read-only call, it is set on every envelope, except two: a pending, answerable decision, and a landed Mission.
  - A first `decision_required` on an untouched run also carries the advance command, because it is not answerable yet.
- **New `error_code` values on `kind=blocked`:** `MISSION_AWAITING_ACCEPTANCE` and `BOARD_STEP_NOT_DISPATCHABLE`.
- **`kind=terminal`** is now also returned for a software-dev Mission with a finished board and a fresh acceptance. This is an existing kind used in a new situation.
- **Invariant, enforced at construction:** `question` is non-null ⇔ `decision_id` is non-null, and when they are set, `options` or `input_key` is present.
- **Scope:** software-dev Missions only. Other Mission families are unchanged.
- **Unchanged:**
  - every existing key, kind and `mission_state` value;
  - `remediation`, which still means the materialization report;
  - the exit-code mapping per kind (the orchestrator-api still reports `blocked` as `RUNTIME_NEXT_FAILED`).
