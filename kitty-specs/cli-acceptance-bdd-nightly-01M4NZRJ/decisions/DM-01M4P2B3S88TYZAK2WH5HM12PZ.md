# Decision Moment `01M4P2B3S88TYZAK2WH5HM12PZ`

- **Mission:** `cli-acceptance-bdd-nightly-01M4NZRJ`
- **Origin flow:** `plan`
- **Slot key:** `plan.supply-chain.gradle-pin-guard`
- **Input key:** `gradle_pin_guard_scope`
- **Status:** `resolved`
- **Created:** `2026-10-11T18:07:01.416071+00:00`
- **Resolved:** `2026-10-11T18:07:59.657120+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

NFR-003 wants acceptance-jvm Gradle pin-drift guarded, but the shared guard contracts/tools/gradle_pin_check.py only scans contracts* paths. How should acceptance-jvm pins be guarded?

## Options

- Generalize the shared gradle_pin_check.py to also scan acceptance-jvm
- Give acceptance-jvm its own pin-check script
- Accept unguarded pin-drift in v1, file a follow-up

## Final answer

Generalize the shared guard: extend contracts/tools/gradle_pin_check.py so it also scans acceptance-jvm/ (build.gradle, pins.json, verification-metadata.xml) and the acceptance-bdd nightly job's gradle-version input, keeping one canonical pin-drift authority (GRADLE_PIN_MISMATCH). Update its unit tests under tests/contract/ accordingly. Fully satisfies NFR-003.

## Rationale

_(none)_

## Change log

- `2026-10-11T18:07:01.416071+00:00` — opened
- `2026-10-11T18:07:59.657120+00:00` — resolved (final_answer="Generalize the shared guard: extend contracts/tools/gradle_pin_check.py so it also scans acceptance-jvm/ (build.gradle, pins.json, verification-metadata.xml) and the acceptance-bdd nightly job's gradle-version input, keeping one canonical pin-drift authority (GRADLE_PIN_MISMATCH). Update its unit tests under tests/contract/ accordingly. Fully satisfies NFR-003.")
