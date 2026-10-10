# Decision Moment `01M4JXGQ2JKGZPMNMY0H62NMSN`

- **Mission:** `org-pack-chain-authority-01M4JXF5`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.loader-seam`
- **Input key:** `loader_seam_5956`
- **Status:** `resolved`
- **Created:** `2026-10-10T12:44:58.834135+00:00`
- **Resolved:** `2026-10-10T12:45:00.480242+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Include the #5956 Mission-type requirement-kinds loader seam (model + load_requirement_kinds through the chain, fail-closed), or defer it?

## Options

- Include the loader seam only (not gate handlers/glossary/grammar)
- Defer/scope out

## Final answer

Include the loader seam ONLY: a RequirementKind/RequirementKindDeclaration model plus load_requirement_kinds() that resolves requirement-kinds.yaml through the same chain (built-in -> org full-chain last-wins -> project tier, project wins) with whole-file override and fail-closed on invalid/missing. The #5956 gate handlers, glossary terms, and grammar integration are out of scope.

## Rationale

_(none)_

## Change log

- `2026-10-10T12:44:58.834135+00:00` — opened
- `2026-10-10T12:45:00.480242+00:00` — resolved (final_answer="Include the loader seam ONLY: a RequirementKind/RequirementKindDeclaration model plus load_requirement_kinds() that resolves requirement-kinds.yaml through the same chain (built-in -> org full-chain last-wins -> project tier, project wins) with whole-file override and fail-closed on invalid/missing. The #5956 gate handlers, glossary terms, and grammar integration are out of scope.")
