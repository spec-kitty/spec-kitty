# Decision Moment `01M66YN6J1ESJ2CYE5J3BJGQHJ`

- **Mission:** `route-kitty-specs-walkers-through-the-mission-predicate`
- **Origin flow:** `specify`
- **Step id:** `specify.success_criteria`
- **Input key:** `success_criteria`
- **Status:** `resolved`
- **Created:** `2026-10-30T17:45:24.801833+00:00`
- **Resolved:** `2026-10-30T17:46:48.824189+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How will we know this Mission is successful?

## Options

_(none)_

## Final answer

Every one of the six walkers decides per child through is_selectable_mission_dir (one git probe per walk at most), so a residue folder never appears as a Mission in any of them; doctor topology no longer prints residue rows with 'meta.json not found'; each changed walker has a test with a residue child and a selectable Mission that would fail on a walker-local rule; and an architectural gate fails if any of the six loses the predicate call.

## Rationale

_(none)_

## Change log

- `2026-10-30T17:45:24.801833+00:00` — opened
- `2026-10-30T17:46:48.824189+00:00` — resolved (final_answer="Every one of the six walkers decides per child through is_selectable_mission_dir (one git probe per walk at most), so a residue folder never appears as a Mission in any of them; doctor topology no longer prints residue rows with 'meta.json not found'; each changed walker has a test with a residue child and a selectable Mission that would fail on a walker-local rule; and an architectural gate fails if any of the six loses the predicate call.")
