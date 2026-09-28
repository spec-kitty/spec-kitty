# Design decisions — squad-doctrine-single-owner-01M3KBP7

- 2026-09-28: Consumer-safe deletion is done by migration, not by a graceful-degrade test. The charter compiler fails closed on an unknown activated id; see the `m_3_2_6_retire_rtk_search_tooling` precedent.
- 2026-09-28: DIRECTIVE_001 → paula-scout moves from `requires` to `suggests`. The scout tactic is recurrence-only and expensive.
- 2026-09-28: The procedure does not reserve a section for the #5221 disposition contract. Shipped doctrine gets no placeholder prose.
- 2026-09-28: Post-spec squad (doctrine-daphne, reviewer-renata) changed the design. Procedure/tactic YAML `references` cannot mint `suggests` or `refines` toward a procedure or tactic, so FR-005/008/012 use curated extractor edges. The lens guard keeps the activation-subset check. The migration logic becomes a shared helper reused by the rtk migration.
