# Decision Moment `01M48HBCJCBVXXZNQ6JAA7SFN4`

- **Mission:** `retire-runtime-bridge-delegates-01M48H5E`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.internal-call-style`
- **Input key:** `internal_call_style`
- **Status:** `resolved`
- **Created:** `2026-10-06T11:59:57.004827+00:00`
- **Resolved:** `2026-10-06T12:00:00.125937+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Inside src/runtime/next, how does code call a seam-owned name after its delegate is deleted?

## Options

- Module-qualified on the owning seam (one patch point = the owner)
- Bare imported name
- Other

## Final answer

Module-qualified on the owning seam (seam.name) everywhere inside src/runtime/next, including the bridge's own calls to get_or_start_run/build_operational_context_for_claim. The two bridge re-exports exist only for callers outside the package. Every test that patches the bridge re-export while driving a bridge-internal path is repointed (GROUNDING hazard 1).

## Rationale

_(none)_

## Change log

- `2026-10-06T11:59:57.004827+00:00` — opened
- `2026-10-06T12:00:00.125937+00:00` — resolved (final_answer="Module-qualified on the owning seam (seam.name) everywhere inside src/runtime/next, including the bridge's own calls to get_or_start_run/build_operational_context_for_claim. The two bridge re-exports exist only for callers outside the package. Every test that patches the bridge re-export while driving a bridge-internal path is repointed (GROUNDING hazard 1).")
