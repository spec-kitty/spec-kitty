# Decision Moment `01M81KHZ4FKVTT364ETW1Z23GB`

- **Mission:** `lane-cleanup-landing-proof-01M81KHJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.proof.setaside`
- **Input key:** `setaside_rule`
- **Status:** `resolved`
- **Created:** `2026-11-22T12:26:36.047810+00:00`
- **Resolved:** `2026-11-22T12:26:53.904100+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which tool-written Mission files may the landing proof set aside, and on what evidence?

## Options

_(none)_

## Final answer

Operator ruling 2026-11-22 (Ancestor blob + keep-code, relayed by the dispatcher, ledger R68): status.events.jsonl keeps its line-containment check; status.json, meta.json and tasks/WP*.md of the lane's own Mission are set aside only when the lane's blob is an ancestor version of the target's copy (the lane never authored it). Never trust a merge-tree or merge-driver result on kitty-specs/**. Everything else fails closed.

## Rationale

_(none)_

## Change log

- `2026-11-22T12:26:36.047810+00:00` - opened
- `2026-11-22T12:26:53.904100+00:00` - resolved (final_answer="Operator ruling 2026-11-22 (Ancestor blob + keep-code, relayed by the dispatcher, ledger R68): status.events.jsonl keeps its line-containment check; status.json, meta.json and tasks/WP*.md of the lane's own Mission are set aside only when the lane's blob is an ancestor version of the target's copy (the lane never authored it). Never trust a merge-tree or merge-driver result on kitty-specs/**. Everything else fails closed.")
