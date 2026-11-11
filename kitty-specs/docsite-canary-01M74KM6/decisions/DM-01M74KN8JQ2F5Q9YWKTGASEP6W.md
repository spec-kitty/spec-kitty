# Decision Moment `01M74KN8JQ2F5Q9YWKTGASEP6W`

- **Mission:** `docsite-canary-01M74KM6`
- **Origin flow:** `specify`
- **Slot key:** `specify.scenario.actor-trigger`
- **Input key:** `scenario_actor_trigger`
- **Status:** `resolved`
- **Created:** `2026-11-11T06:10:25.495441+00:00`
- **Resolved:** `2026-11-11T06:10:27.597651+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Who starts the canary, when, and what must it prove?

## Options

_(none)_

## Final answer

The operator dispatches docs-pages.yml from main with canary=true in an announced window with docs merges frozen. The run builds the doc-kitty site through the shared docs-site-build.yml (D-11), deploys it to Pages, probes a ledger-derived sample of D-13 URL classes on https://docs.spec-kitty.ai, then always rebuilds and redeploys DocFX and fails the run if the probe failed. Answered from the operator brief for #6938 PR A.

## Rationale

_(none)_

## Change log

- `2026-11-11T06:10:25.495441+00:00` - opened
- `2026-11-11T06:10:27.597651+00:00` - resolved (final_answer="The operator dispatches docs-pages.yml from main with canary=true in an announced window with docs merges frozen. The run builds the doc-kitty site through the shared docs-site-build.yml (D-11), deploys it to Pages, probes a ledger-derived sample of D-13 URL classes on https://docs.spec-kitty.ai, then always rebuilds and redeploys DocFX and fails the run if the probe failed. Answered from the operator brief for #6938 PR A.")
