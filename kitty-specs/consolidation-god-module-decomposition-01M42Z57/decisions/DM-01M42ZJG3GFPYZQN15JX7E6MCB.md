# Decision Moment `01M42ZJG3GFPYZQN15JX7E6MCB`

- **Mission:** `consolidation-god-module-decomposition-01M42Z57`
- **Origin flow:** `specify`
- **Slot key:** `specify.structure.mission_number_home`
- **Input key:** `mission_number_home`
- **Status:** `resolved`
- **Created:** `2026-10-04T08:13:03.472924+00:00`
- **Resolved:** `2026-10-04T08:13:23.804071+00:00`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Where does the mission_number bake cluster from ordering.py go, given mission_number.py is a stdlib-only leaf imported by the merge-driver body module?

## Options

- Turn mission_number.py into a package: leaf predicate stays in __init__, cluster in mission_number/bake.py
- Move the cluster into mission_number.py itself (breaks the leaf contract)
- New sibling module number_assignment.py
- Other

## Final answer

Package: consolidation/mission_number/__init__.py keeps the stdlib-only predicate verbatim; the bake cluster moves to consolidation/mission_number/bake.py. Honours #2600's 'into mission_number' target and the leaf contract drivers.py relies on (code-grounding §1.3). Decided under the brief's delegation ('confirm or adjust after grounding; record the reasoning in plan.md').

## Rationale

_(none)_

## Change log

- `2026-10-04T08:13:03.472924+00:00` — opened
- `2026-10-04T08:13:23.804071+00:00` — resolved (final_answer="Package: consolidation/mission_number/__init__.py keeps the stdlib-only predicate verbatim; the bake cluster moves to consolidation/mission_number/bake.py. Honours #2600's 'into mission_number' target and the leaf contract drivers.py relies on (code-grounding §1.3). Decided under the brief's delegation ('confirm or adjust after grounding; record the reasoning in plan.md').")
