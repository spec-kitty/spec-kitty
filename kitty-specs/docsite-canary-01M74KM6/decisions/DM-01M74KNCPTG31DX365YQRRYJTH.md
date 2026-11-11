# Decision Moment `01M74KNCPTG31DX365YQRRYJTH`

- **Mission:** `docsite-canary-01M74KM6`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.probe-classes`
- **Input key:** `probe_url_classes`
- **Status:** `resolved`
- **Created:** `2026-11-11T06:10:29.722824+00:00`
- **Resolved:** `2026-11-11T06:10:31.932495+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which URL classes does the probe check, and how is the sample chosen?

## Options

_(none)_

## Final answer

Derived from the committed ledgers (url-baseline.txt, moves.yaml, legacy-redirects.json), never a hand list: one .html key to its own page, one moved-chain key, one live dir/index.html (rule 3), one dir/README.html, one directory URL, plus the site root, /llms.txt and one retired /kitty-specs/ route expected 404. Stubs must name the map's target and the target must serve 200. Answered from the operator brief.

## Rationale

_(none)_

## Change log

- `2026-11-11T06:10:29.722824+00:00` - opened
- `2026-11-11T06:10:31.932495+00:00` - resolved (final_answer="Derived from the committed ledgers (url-baseline.txt, moves.yaml, legacy-redirects.json), never a hand list: one .html key to its own page, one moved-chain key, one live dir/index.html (rule 3), one dir/README.html, one directory URL, plus the site root, /llms.txt and one retired /kitty-specs/ route expected 404. Stubs must name the map's target and the target must serve 200. Answered from the operator brief.")
