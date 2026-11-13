# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude · The moves ledger now reads a later entry into a route as superseding that route's earlier move away (8 folders went README -> index in #3914/#6928 and back in #6939). Self-moves stay refused as cycles; a return to a route with no page is refused by site_redirects. An index rename needs no baseline entry and no redirect key (moves_ledger.is_index_rename).

2026-11-12 · claude · Commit trailers: what lands on issue-6939-readme-rename-and-audit is the hand-squashed, ordered set authored at closeout (tests, rename, links and readers, audit, gate, ADR, changelog, mission record), as the retire-docfx Mission landed on main. The individual WP commits are not rewritten; each squashed commit is signed and carries both Co-Authored-By lines and the Claude-Session trailer.

2026-11-13 · claude · Follow-up (not fixed here): freshen_adr_inventory.prune_dangling_rows writes earlier eras before it refuses a later era whose only landing page is a retired index.md, so a refusal can leave a partial prune. tests/docs/test_section_index_basename.py keeps index.md out of docs/, so it is hypothetical today; a fix would check every era before writing any.

2026-11-13 · claude · WP02: check_docs_freshness.py is not extended. It orchestrates the generated-surface checks and no CI job runs it; the inventory is a report, not a gate, so it is a sibling module (scripts/docs/staleness_audit.py), and the retired-surface gate runs where it is enforced (docs-lint). The inventory is not committed under docs/ (its git-history field changes with every docs commit); a snapshot lives in the Mission's audit/ folder. Commands are read from code spans and fences only, so prose like 'the spec-kitty project' names none.

2026-11-13 · claude · WP02 review cycle 1: the inventory refuses a shallow clone (its graft commit dated 61 pages); the snapshot was regenerated after git fetch --unshallow (about 7 minutes on the full history). Retired slash commands (HISTORICAL_COMMANDS minus CANONICAL_COMMANDS: checklist, clarify, constitution, dashboard, merge, profile-context) became surfaces; the burn-down grew to 89 pairs on 58 pages before landing, and a frozen landing set in the test now lets it only shrink. The architectural gate's own lists were left unchanged: its RETIRED_CLI_PREFIXES lacks the #6164 CLI commands (auth, issue-search, live-work, moments, routes, zeitgeist), which the docs layer covers; reported to the coordinator, not changed.

2026-11-13 · claude · WP02 review cycle 2: leaving the burn-down is one-way. The gate itself (docs-lint) and its test require the burn-down's pair count to equal test_retired_surface_gate.burn_down in tests/architectural/_baselines.yaml, so a drain lowers the baseline in the same pull request and a drained pair put back is above it. The shared ratchet mechanism is unchanged (it still fails only on growth, for every key); the landing-set subset check stays. The gate and the inventory scan one text (staleness_audit.published_text): the body plus title and description read through the YAML loader.
