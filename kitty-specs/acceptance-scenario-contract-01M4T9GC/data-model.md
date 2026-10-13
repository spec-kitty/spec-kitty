# Data model

## Scenario (read by the per-PR check)
- `file`, `line`, `name`, `keyword` (`Scenario` | `Scenario Outline`)
- `tags`: own tags plus inherited Feature and Rule tags
- `steps`: ordered `(keyword, text, line)`; `And`/`But`/`*` resolve to the previous keyword; outline steps are expanded per `Examples` row (Background steps are prepended)

## Step definition
- `keyword` (`Given` | `When` | `Then`), `expression` (Cucumber expression), `source` (`file:line`), compiled `regex`
- Matching ignores the keyword, as Cucumber does.

## Tag vocabulary
| Form | Rule |
|------|------|
| `@promise:<id>` | `<id>` matches `[A-Za-z0-9][A-Za-z0-9._-]*`; not repeated on one scenario |
| `@wip` | requires `@wip-owner:<handle>` and `@wip-since:<YYYY-MM-DD>` (valid date) |
| `@wip-owner:<handle>` | handle matches `[A-Za-z0-9][A-Za-z0-9._-]*` |
| `@manual` | none |
| `@defect:<issue>` | positive integer |
| `@qa:<ref>` | identifier character set |
| `@<bare>` | bare tag `[A-Za-z0-9][A-Za-z0-9_-]*`, no `:` |
| anything else with `:` | unknown prefixed tag → error |

## Pass
`gating` (filter `not @wip and not @manual`, may not be empty) or `wip` (filter `@wip`, may be empty).

## Evidence bundle (`evidence.json`, schema in `contracts/evidence.schema.json`)
`schema_version` (1), `commit_sha`, `cli_version`, `os`, `run_url` (nullable), `passes.<pass>` = `{outcome: passed|failed|missing, tests, failures, errors, skipped, results: {allure, cucumber, junit}}`.
