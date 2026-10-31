# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude-code/opus · New non-src router group charter_activation (.kittify/charter/charter.yaml, .kittify/charter/activation.yaml, packs/internal.source.yaml) rather than appending them to the charter filter group: the transcription guard requires a group's router globs to equal its scrub roots verbatim, and the charter group is the charter *source* subsystem (#6334 refused the append). packs/internal/** is untracked since #6451, so the pin lockfile is the live trigger.

2026-10-31 · claude-code/opus · Fan-out cannot join GROUP_MODULE_FANOUT/FANOUT_GROUPS: derive_group_module_fanout reads the committed consumer census, which records only resolved src/** imports and packs/built-in/missions/** runtime reads, so a .kittify/pin group derives an empty set and tests/ci/test_fanout_derivation.py requires every FANOUT_GROUPS member to derive >=1 module. Follows the CLI_COMMAND_MODULE_FANOUT precedent: a hand-authored non-census fan-out table consumed by the same select_modules entry point.

2026-10-31 · claude-code/opus · src/kernel/activation_ledger_store.py reaches the charter shard by adding the file verbatim to the charter scrub group roots (and, per the verbatim-consumption guard, the registry charter row): overlapping src ownership is already the scrub's documented shape (core_misc/unit/execution_context each own src/specify_cli/status/**), and a src file cannot live in the new non-src group without dragging that group into the FR-004 unmatched union.

2026-10-31 · claude-code/opus · Development-assist test verdict for the one test module this mission added (tests/ci/test_charter_activation_routing.py): KEEP, and it is already named after the contract it guards (the charter-activation routing contract), not after the issue. Rationale per DIRECTIVE_041: every assertion pins a standing CI-routing invariant (the activation store / internal pack pin select the charter shard; the group stays non-src; the ledger floor keeps its kernel roots) that a future router edit can silently break, and the revert rows make each pin falsifiable. Nothing was characterization debris, so nothing is retired or split.
