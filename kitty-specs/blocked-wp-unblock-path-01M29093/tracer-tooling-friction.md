# Mission tracer — tooling friction (blocked-wp-unblock-path-01M29093, #3937)

Append-only friction ledger for this mission. Feeds the next mission / tracker.

## F1 — Global agent-command sync races across sibling clones (#2627 class)
- **Where**: every non-`next` CLI invocation runs `ensure_global_agent_commands()` (`src/specify_cli/__init__.py:147`), which raises `RuntimeError: Global asset input changed: ~/.kittify/cache/slash_commands-assets.json` when a concurrent session regenerates the shared global cache.
- **Trigger**: a parallel Spec Kitty session in a SIBLING clone (P0 work) shares `~/.kittify/cache/`; its regeneration invalidated this session's cache mid-run.
- **Impact**: intermittent hard crashes of `spec-commit`, `record-analysis`, `implement` (the workspace allocator). Cost ~1 retry each.
- **Workaround used**: (a) `spec-kitty next …` takes the `_is_next_invocation` fast-path that SKIPS the gate — race-immune; (b) for non-`next` verbs, a bounded retry loop rides through (the gate self-heals by regenerating when not mid-race).
- **Suggested fix**: the gate should treat "input changed" as "regenerate", not "raise" — refusing on a benign concurrent regeneration is fail-closed against a non-error. Cross-ref #2627.

## F2 — Lane allocation leaves planning artifacts uncommitted with auto-commit off; next WP's validate-planning-state then refuses
- **Where**: `spec-kitty implement WP01` (workspace allocator) wrote `base_branch`/`base_commit` into the WP01 prompt frontmatter (+ meta.json/status churn) but did NOT commit it (project default auto-commit off). Allocating WP02 then failed its "Planning artifacts not committed" gate citing the WP01 prompt file.
- **Impact**: had to manually commit the lane-a allocation churn before WP02 could allocate.
- **Workaround**: commit the allocation churn, then allocate the next lane with `--auto-commit`.
- **Observation**: the allocator mutating a *different* WP's planning artifact as a side effect of allocation is surprising; a per-lane allocation should either auto-commit its own metadata write or not leave a cross-WP artifact dirty.

## F3 — coord topology on a 2-WP bug fix
- The mission was auto-created with `topology: coord`; status.events.jsonl churns on every transition and must be committed on the primary partition. For a small fix this is heavier than a flat/LANES topology would be. (Noted, not blocking.)
