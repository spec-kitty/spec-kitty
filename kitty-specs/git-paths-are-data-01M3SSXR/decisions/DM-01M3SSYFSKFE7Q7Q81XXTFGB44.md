# Decision Moment `01M3SSYFSKFE7Q7Q81XXTFGB44`

- **Mission:** `git-paths-are-data-01M3SSXR`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.plumbing-query-home`
- **Input key:** `plumbing_query_home`
- **Status:** `resolved`
- **Created:** `2026-09-30T18:41:35.027473+00:00`
- **Resolved:** `2026-09-30T18:41:53.573775+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

ref_advance must import zero specify_cli (NFR-004). Where do the queries it needs live?

## Options

- Typed path queries live in kernel/git (status entries, tree paths, changed paths); specify_cli/core/vcs holds the domain-level queries for specify_cli callers
- Relax NFR-004 so ref_advance may import specify_cli/core/vcs
- Other

## Final answer

Typed path queries live in kernel/git (status entries, tree paths, changed paths); specify_cli/core/vcs holds the domain-level queries for specify_cli callers

## Rationale

_(none)_

## Change log

- `2026-09-30T18:41:35.027473+00:00` — opened
- `2026-09-30T18:41:53.573775+00:00` — resolved (final_answer="Typed path queries live in kernel/git (status entries, tree paths, changed paths); specify_cli/core/vcs holds the domain-level queries for specify_cli callers")
