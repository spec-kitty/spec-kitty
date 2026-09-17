# Decision Moment `01M2NQDWFQ6HY5A8A90VQ0E69H`

- **Mission:** `cli-boundary-robustness-01M2NQCB`
- **Origin flow:** `specify`
- **Slot key:** `specify.json-contract.envelope-and-streams`
- **Input key:** `json_envelope_contract`
- **Status:** `resolved`
- **Created:** `2026-09-16T18:24:54.263313+00:00`
- **Resolved:** `2026-09-16T18:28:54.703797+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Canonical --json machine contract (D1 envelope + D2 exit code + D3 stream discipline): honor the existing test-frozen #4242 precedent across all --json surfaces?

## Options

- Honor #4242 frozen precedent (ok:false/error{code,message} on errors; success-with-empty-collections on empty exit-0; exit code equals non-json exit incl. exit 2 for not_in_project; stdout JSON-only, prose to stderr)
- Define a new/different envelope contract
- Other

## Final answer

Honor the test-frozen #4242 precedent across all --json surfaces. D1: errors emit {"ok":false,"error":{"code":<stable slug>,"message":<human>}}; empty-but-success (exit 0) paths emit the domain's normal success envelope with empty collections (no stray error key). D2: a --json error path's exit code equals its non-json exit code (incl. exit 2 for not_in_project per NFR-001). D3: --json => stdout is JSON-only on every exit path; human prose goes to stderr.

## Rationale

_(none)_

## Change log

- `2026-09-16T18:24:54.263313+00:00` — opened
- `2026-09-16T18:28:54.703797+00:00` — resolved (final_answer="Honor the test-frozen #4242 precedent across all --json surfaces. D1: errors emit {"ok":false,"error":{"code":<stable slug>,"message":<human>}}; empty-but-success (exit 0) paths emit the domain's normal success envelope with empty collections (no stray error key). D2: a --json error path's exit code equals its non-json exit code (incl. exit 2 for not_in_project per NFR-001). D3: --json => stdout is JSON-only on every exit path; human prose goes to stderr.")
