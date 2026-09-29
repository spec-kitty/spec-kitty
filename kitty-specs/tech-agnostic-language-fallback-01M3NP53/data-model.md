# Data model — tech-agnostic-language-fallback-01M3NP53

## Active project languages (`catalog.languages`, resolved by `infer_repo_languages`)

| State | Stored form | Meaning | Admits language-scoped artifacts | Context |
|---|---|---|---|---|
| no signal | field absent / null | nothing declared | all (legacy behaviour) | no Languages line, no advisory |
| admit none | `[]` (hand-edited only) | explicit empty | none | unchanged |
| recognised | `[python, …]` | recognised languages | overlapping only | `Languages: …` |
| **unknown (new)** | `[unknown]` | declared but unrecognised | none (unscoped still load) | `Languages: unknown` + one advisory |

Invariants:
- `unknown` is never combined with a recognised language by the compiler (recognised wins).
- `unknown` is reserved: an artifact may not declare `applies_to_languages: [unknown]` (validator rejects).
- A hand-edited `[python, unknown]` resolves without error; python artifacts still load.
- Transitions: only `charter generate --from-interview` may move a compiled value to a different state from the interview; runtime reads never do.

## Dead-code gate outcome (mission review)

| Outcome | Gate result | Finding type | Code | Verdict effect |
|---|---|---|---|---|
| scanned, clean | pass | — | — | pass |
| scanned, unreferenced symbols | fail (as today) | `dead_code` | — | pass_with_notes |
| undeterminable (git missing/failed, unreadable source, empty corpus) | fail | `dead_code_undeterminable` | `MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE` | fail |
| **not applicable (new)** | skip | `dead_code_not_applicable` | `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE` | pass_with_notes |

Not-applicable finding fields: `type`, `diagnostic_code`, `unsupported_extensions` (comma-joined, sorted), `excluded_test_paths` (count), `reason`, `remediation`.

Mixed change set: scanned outcome for the supported subset + a not-applicable note for the remainder (console note; the gate result follows the scan).
