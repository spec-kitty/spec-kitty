# Enumeration Contract — Documented orchestrator error codes

The interface this Mission adds is not a new command or payload: it is the rule that
both prose surfaces which enumerate `orchestrator_api.allowed_error_codes` must stay
exactly equal to it. This file is that contract. The two surfaces implement it, and
`tests/contract/test_orchestrator_api.py::TestProseErrorCodeEnumerations` enforces it.

## Authority

`orchestrator_api.allowed_error_codes` in `src/specify_cli/core/upstream_contract.json`
is the only authority. The guard reads it at test time through the
`orchestrator_api_contract` fixture (`importlib.resources` on `specify_cli.core`); no
test, doc or contract here keeps a second copy of the code set.

## Surfaces

| Surface | Kind | Entries |
|---|---|---|
| `docs/api/orchestrator-api.md` → `## Error Codes` | `bullets` | `- \`CODE\`` list items |
| `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` → `## Error Code Summary` | `table` | `\| \`CODE\` \| ... \|` rows |

## Region

Each surface carries exactly one anchor pair, as literal HTML-comment lines:

```
<!-- orchestrator-error-codes:begin -->
<!-- orchestrator-error-codes:end -->
```

Everything between the anchors is the enumeration; nothing outside them is read. A
heading may not sit inside the region. Anchors are never placed inside a fenced code
block.

## Parse rules

- **bullets** — a line contributes the code in its *leading* backticked token only
  (`^- \`CODE\``). A parenthetical annotation may mention other codes without adding an
  entry.
- **table** — a row contributes the code in its *first* cell only
  (`^\| \`CODE\` \|`). The header row and the separator row are skipped; a description
  cell may mention other codes without adding an entry.
- Blank lines and HTML comments inside the region are ignored. Any other line is a
  parse failure naming its line number and text: the region must not absorb prose the
  guard cannot read.

## Invariants (each fail-closed)

| ID | Invariant | On violation |
|---|---|---|
| ENUM-1 | Each surface's set equals `allowed_error_codes` | Fail, naming the surface and the sorted `missing` / `unexpected` lists |
| ENUM-2 | No code appears twice in one surface | Fail, naming the surface and the duplicated codes |
| ENUM-3 | Exactly one `begin` and one `end` anchor per surface, in that order | Fail, naming the surface and the expected anchor |
| ENUM-4 | A parsed region holds at least one entry | Fail: an empty region cannot agree with the contract |
| ENUM-5 | Every non-entry line inside the region is rejected | Fail, naming the line number and text |

There is no skip path: a surface whose anchor disappears, whose region parses to zero
entries, or whose region gains unreadable prose fails rather than passing vacuously.

## Out of scope

`data.preflight_error_code`, `data.teardown_error_code` and the origin-freshness codes
ride inside `data`, are not `allowed_error_codes` entries, and change on their own
schedule. Their tables stay outside the anchors and are not checked here. Contract
version-history bullets and per-verb "Error codes:" narrative are narrative, not
enumerations, and are not re-synced by this Mission.

## Verification

- `uv run pytest tests/contract/test_orchestrator_api.py -q -k prose`
- Half-by-half: reverting either surface alone fails naming that surface's missing
  codes (22 for the API reference, 23 for the skill table).
