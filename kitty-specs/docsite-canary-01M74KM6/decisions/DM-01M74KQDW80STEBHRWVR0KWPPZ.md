# Decision Moment `01M74KQDW80STEBHRWVR0KWPPZ`

- **Mission:** `docsite-canary-01M74KM6`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.restore-ordering`
- **Input key:** `restore_ordering`
- **Status:** `resolved`
- **Created:** `2026-11-11T06:11:36.456534+00:00`
- **Resolved:** `2026-11-11T06:11:38.406976+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the canary order its jobs so DocFX is always restored and the default path stays unchanged?

## Options

_(none)_

## Final answer

The DocFX build job is untouched and builds in parallel; the canary publishes only after both the shared doc-kitty build and the DocFX build succeeded; the probe runs after the canary publish; the existing deploy job waits on the probe and runs on !cancelled() || canary, so it republishes DocFX whatever the probe said, while its default-path semantics are equivalent. Brief-derived engineering decision.

## Rationale

_(none)_

## Change log

- `2026-11-11T06:11:36.456534+00:00` - opened
- `2026-11-11T06:11:38.406976+00:00` - resolved (final_answer="The DocFX build job is untouched and builds in parallel; the canary publishes only after both the shared doc-kitty build and the DocFX build succeeded; the probe runs after the canary publish; the existing deploy job waits on the probe and runs on !cancelled() || canary, so it republishes DocFX whatever the probe said, while its default-path semantics are equivalent. Brief-derived engineering decision.")
