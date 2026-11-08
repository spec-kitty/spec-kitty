# Approach — consolidation-window-provenance-01M6Y84D

Running log of approach changes (procedure `mission-tracer-files`).

- **[2026-11-08][plan] Four strict phases on one PR.** Pin and decide (characterization corpus, refusal-precedence matrix, surface pin, `RECONCILIATION_FAMILY` guard, Proposed ADR) → record and unify inputs (`policy_metadata.wp_window` capture, one `ClaimInputs` constructor, zero verdict change) → behaviour-preserving split of `reconciliation.py` behind a facade → red-first behaviour changes (lane windows with fallback and gap report, #5048(b), resume frozen dependency tips, forecast excluded-set alignment). Source: operator-confirmed Engineering Alignment.
- **[2026-11-08][plan] Behaviour changes land after the split, not before.** The squad (architect-alphonso) recommended deferring all behaviour changes to follow-up Missions; the operator kept four bounded ones in scope, so they are ordered last and each one flips only its pre-pinned strict `xfail` corpus scenario.
- **[2026-11-08][plan] Implementer routing by model tier.** Pins, pure moves and patch retargeting are routed to cheaper implementer models (oracle = corpus + surface pin + guard). The ADR, capture probe, `ClaimInputs` and lane-window adoption go to top-tier models (see plan.md Implementation Concern Map).
