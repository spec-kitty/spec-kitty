# Data model: Docsite publication rules, llms.txt and render parity

| Element | Source of truth | Consumers |
|---|---|---|
| Excluded folders | `_dockitty_contract.EXCLUDED_FOLDERS` → `dockitty-contract.json.exclude` | doc-kitty `exclude`, gates, built-site check |
| Draft-only folders | `_dockitty_contract.DRAFT_FOLDERS` (each page there must be `doc_status: draft`) | contract check, built-site check |
| Unpublished routes | `unpublished_routes(docs_root)` = excluded ∪ not `is_published` | built-site check, #6933 redirect generator |
| Version stance | `_dockitty_contract.LLMS_STANCE` → `dockitty-contract.json.llmsStance` | `site/src/pages/llms.txt.ts`, built-site check |
| Feeds per section | `docs/_meta/sections.yaml` `feeds` | doc-kitty, built-site check (llms surface) |

Invariant: a route is on a built surface only if it is published (and, for `llms.txt`/agent index, its section feeds include `llms`/`agent`).
