# Contract: `next` envelope additions (additive)

- **New key `next_command` (string).**
  - It appears only when set, so existing payloads stay byte-identical.
  - Advancing `next`: set only on the finished-board `blocked` answer (`MISSION_AWAITING_ACCEPTANCE`).
  - Read-only `next`: set on every envelope that carries no pending decision, unless the Mission has landed.
- **New `error_code` value `MISSION_AWAITING_ACCEPTANCE`** on `kind=blocked`.
- **`kind=terminal` on an accepted Mission with a finished board.** This is an existing kind in a new situation.
- **Query invariant:** `question` is non-null iff `decision_id` and `options` are present.
- **Unchanged:**
  - every existing key, kind and `mission_state` value;
  - `remediation` (it keeps its materialization-report meaning);
  - the exit-code mapping per kind.
