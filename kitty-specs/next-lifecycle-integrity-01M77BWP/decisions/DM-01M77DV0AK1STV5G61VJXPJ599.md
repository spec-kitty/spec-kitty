# Decision Moment `01M77DV0AK1STV5G61VJXPJ599`

- **Mission:** `next-lifecycle-integrity-01M77BWP`
- **Origin flow:** `specify`
- **Slot key:** `specify.next.finished_board_state_map`
- **Input key:** `specify.next.finished_board_state_map`
- **Status:** `resolved`
- **Created:** `2026-11-12T08:26:25.491818+00:00`
- **Resolved:** `2026-11-12T08:26:27.600228+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Per-state mapping of the blocked-with-remedy ruling

## Options

- as mapped
- accepted -> terminal
- single code

## Final answer

accepted -> terminal

## Rationale

Operator ruling 2026-11-12: board finished and not accepted -> kind=blocked, new error_code MISSION_AWAITING_ACCEPTANCE, remediation spec-kitty accept; accepted (board still finished) or landed -> existing kind=terminal. No step row recorded, run not advanced. No-WP and research/custom missions unchanged.

## Change log

- `2026-11-12T08:26:25.491818+00:00` - opened
- `2026-11-12T08:26:27.600228+00:00` - resolved (final_answer="accepted -> terminal")
