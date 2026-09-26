# Decision Moment `01M35C3V2KNMH4NHEHGEVFRF14`

- **Mission:** `windows-upgrade-mode-fidelity-01M35C25`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.followsymlinks-sweep`
- **Input key:** `followsymlinks_sweep_scope`
- **Status:** `resolved`
- **Created:** `2026-09-22T20:15:01.715555+00:00`
- **Resolved:** `2026-09-22T20:15:50.809390+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the #4923 fix close the whole follow_symlinks-on-Windows class (all installer.py sites + a shared host-aware helper + an arch gate), or only the proven crash site (:981)?

## Options

- close-the-class (all sites + helper + gate)
- proven crash site only
- Other

## Final answer

close-the-class: make all installer.py follow_symlinks sites (:174/:963/:969/:981) host-safe via a shared kernel helper, plus a non-vacuous architectural gate against new unguarded call-sites (Standing Order #5)

## Rationale

_(none)_

## Change log

- `2026-09-22T20:15:01.715555+00:00` — opened
- `2026-09-22T20:15:50.809390+00:00` — resolved (final_answer="close-the-class: make all installer.py follow_symlinks sites (:174/:963/:969/:981) host-safe via a shared kernel helper, plus a non-vacuous architectural gate against new unguarded call-sites (Standing Order #5)")
