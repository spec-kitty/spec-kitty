# Decision Moment `01M72871WDH3GYMFKTAHRZFJ14`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.meta.bom-policy`
- **Input key:** `meta_bom`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:56.685132+00:00`
- **Resolved:** `2026-11-10T08:11:58.000404+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7445: how should mission meta.json loading treat a UTF-8 byte-order mark?

## Options

- Option A: load_meta and parse_meta_file read with utf-8-sig; kernel decode_meta unchanged
- Option B: make the kernel decoder BOM-tolerant
- Other

## Final answer

Option A (operator decision 2026-11-10): load_meta and parse_meta_file decode meta.json with utf-8-sig, so a BOM-prefixed file reads like the same file without one; strictly widening, non-BOM files decode identically. kernel decode_meta is not changed; load_meta_strict(bom_tolerant=False) stays the negative control. The remaining BOM-rejecting readers (planning_commit, ref_advance, mission_finalize, charter activation) are a documented residual and a follow-up.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:56.685132+00:00` - opened
- `2026-11-10T08:11:58.000404+00:00` - resolved (final_answer="Option A (operator decision 2026-11-10): load_meta and parse_meta_file decode meta.json with utf-8-sig, so a BOM-prefixed file reads like the same file without one; strictly widening, non-BOM files decode identically. kernel decode_meta is not changed; load_meta_strict(bom_tolerant=False) stays the negative control. The remaining BOM-rejecting readers (planning_commit, ref_advance, mission_finalize, charter activation) are a documented residual and a follow-up.")
