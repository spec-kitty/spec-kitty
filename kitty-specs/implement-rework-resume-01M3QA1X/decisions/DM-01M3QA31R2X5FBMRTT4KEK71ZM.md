# Decision Moment `01M3QA31R2X5FBMRTT4KEK71ZM`

- **Mission:** `implement-rework-resume-01M3QA1X`
- **Origin flow:** `specify`
- **Step id:** `discovery`
- **Input key:** `resume_scope`
- **Status:** `resolved`
- **Created:** `2026-09-29T19:25:58.402266+00:00`
- **Resolved:** `2026-09-29T19:26:08.935229+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Who may resume an in_progress WP via implement after a reviewer's in_review→in_progress rework verdict, and does the fix cover every start_implementation_status caller?

## Options

- Implementer of record (latest_implementer_actor) only; fix at the shared start_implementation_status authority so all callers inherit it
- Only agent action implement (executor-local fix)

## Final answer

Implementer of record (latest_implementer_actor) only; fix at the shared start_implementation_status authority so all callers inherit it

## Rationale

Operator brief + #5377 Expected section: the implementer of record per latest_implementer_actor resumes without --force, an unrelated agent is still refused. Fixing the shared lifecycle authority keeps one ownership rule for agent action implement, spec-kitty implement and orchestrator-api start-implementation (single canonical authority).

## Change log

- `2026-09-29T19:25:58.402266+00:00` — opened
- `2026-09-29T19:26:08.935229+00:00` — resolved (final_answer="Implementer of record (latest_implementer_actor) only; fix at the shared start_implementation_status authority so all callers inherit it")
