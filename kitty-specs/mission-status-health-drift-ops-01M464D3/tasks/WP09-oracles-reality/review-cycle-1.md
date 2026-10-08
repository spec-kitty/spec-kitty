---
affected_files: []
cycle_number: 1
mission_slug: mission-status-health-drift-ops-01M464D3
reproduction_command:
reviewed_at: '2026-10-07T08:06:54Z'
reviewer_agent: user
wp_id: WP09
---

# WP09 review cycle 1: changes requested

Full review: scratchpad `c12-wp09-review.md`.

1. **Timed bound on a patched path (NFR-001/NFR-009, AC-CROSS 4: "resolver included").** The timed run executes under the autouse `identity_index_is_walked_once` patch, which caches the resolver's `_build_index`. Restore the original `_build_index` inside the timed block of `execute_corpus_run`, so the asserted 120 s bounds measure the production path. Add a plant that refuses a patched timed run (it must fail if the patch is active during timing). Assert this in the module, not only in the hand-off.
2. **After the WP03 rework lands** (the Project read no longer raises on a non-UTF-8 `status.json`), drop the `undecodable=False` workaround in `dho_repo`, so the payload-control fixture includes the undecodable Mission again.
3. Severity 1, optional: the AST independence test misses an obfuscated `importlib.import_module("..._mission_status_" + "ops")`. Close it cheaply if you can (for example, flag any `importlib` use in the oracle module).

Gates: the module online and offline from a scratch clone of the primary checkout, timed figures quoted unpatched, the ruff pair, and the battery fast leg.
