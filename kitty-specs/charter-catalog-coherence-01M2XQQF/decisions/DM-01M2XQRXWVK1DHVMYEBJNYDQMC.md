# Decision Moment `01M2XQRXWVK1DHVMYEBJNYDQMC`

- **Mission:** `charter-catalog-coherence-01M2XQQF`
- **Origin flow:** `specify`
- **Slot key:** `specify.activate.catalog-coherence-default`
- **Input key:** `activate_catalog_coherence_default`
- **Status:** `resolved`
- **Created:** `2026-09-19T21:04:51.611213+00:00`
- **Resolved:** `2026-09-19T21:05:05.511905+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a maintainer activates a single built-in charter directive, should the compiled catalog.references stay coherent by default (recompile as part of activate, with an opt-out for the fast config-only write), or should coherence remain opt-in behind an explicit flag?

## Options

- Coherent-by-construction: activate recompiles the catalog by default, config-only becomes an explicit opt-out
- Keep config-only default: coherence stays opt-in behind a flag
- Other

## Final answer

Coherent-by-construction: activate/deactivate recompile catalog.references by default via the single compile_charter authority (the pack apply --compile explicit-repo_root pattern); the fast config-only write becomes an explicit opt-out flag. Orchestrator decision under delegated mission autonomy, backed by the architecture lens — the config-only default is the direct cause of the #2524 dangler, and the default recompile is fast (it is what the background references-refresh heal already runs).

## Rationale

_(none)_

## Change log

- `2026-09-19T21:04:51.611213+00:00` — opened
- `2026-09-19T21:05:05.511905+00:00` — resolved (final_answer="Coherent-by-construction: activate/deactivate recompile catalog.references by default via the single compile_charter authority (the pack apply --compile explicit-repo_root pattern); the fast config-only write becomes an explicit opt-out flag. Orchestrator decision under delegated mission autonomy, backed by the architecture lens — the config-only default is the direct cause of the #2524 dangler, and the default recompile is fast (it is what the background references-refresh heal already runs).")
