---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T12:31:37Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review — cycle 1: CHANGES REQUESTED (one small blocking fix)

Reviewer: reviewer-renata. Everything else in WP07 passes: red→green (19 failed/7 passed at 815907b3 → 26 passed at HEAD; the post-red test edits only make the whitespace handling more robust); reconciler (DIRECTIVE_052, tidy-first carve-out, tie-break, enforcement unchanged, agrees with the charter); DIRECTIVE_025 → DIRECTIVE_030; review-tactic layering; boring-code-review styleguide; in-house moves and internal fragment; targeted suites (602 passed, 2 expected-red; tension/consistency/provenance ratchet 41 passed).

## Blocking: the locality-of-change fold drops normative content and DRG delivery edges

The WP's check is: "evidence gate fully in avoid-gold-plating, nothing normative lost". The 5/7 checklist and the 3+ real-failures threshold moved correctly. The deleted tactic also carried the following, and none of it survives in `packs/built-in/tactics/avoid-gold-plating.tactic.yaml`. None of it is recorded in the Handoff-to-WP09 either, which the delivery-risk rule requires.

1. **Its references, which were its only DRG edges to the owning directives** (`tactic.graph.yaml:927-938`):
   - `DIRECTIVE_024`: "practical application protocol for Directive 024". DIRECTIVE_024 is one of the three rules the charter's "Reconciling change-scope tensions" section names. After the fold, no tactic applies it.
   - `DIRECTIVE_001`: an expanded-scope change must pass the architectural integrity check. The deleted step "Cross-check against architectural principles" also said that a change conflicting with an existing ADR must propose to supersede it or be rejected.
   - `DIRECTIVE_003`: the accept/reject rationale must be documented. The deleted step "Accept or reject with documented rationale" recorded the problem evidence, the severity, the alternatives, and the do-nothing baseline together with why it was rejected or accepted.
2. **Failure mode "complexity creep"**: each small addition looks reasonable, but they add up, so the gate applies to small changes too. This scope statement is now gone.

### Fix (small; stays inside owned_files)
- In `avoid-gold-plating.tactic.yaml`, add `references` to `DIRECTIVE_024`, `DIRECTIVE_001` and `DIRECTIVE_003`. Carry the `when` text over from the deleted tactic. Per the epic rule, reference these owners instead of restating their rules.
- Extend the evidence-gate step with one sentence each:
  - record the accept/reject decision, with the do-nothing baseline and the alternatives considered (→ DIRECTIVE_003);
  - an added complexity that conflicts with an ADR must propose to supersede that ADR or be rejected (→ DIRECTIVE_001);
  - the gate applies to small additions too (complexity creep).
- Add a pin to `tests/doctrine/test_change_scope_review_single_owner.py`: avoid-gold-plating references DIRECTIVE_024, DIRECTIVE_001 and DIRECTIVE_003.
- Update the Handoff-to-WP09: the successor edges `tactic:avoid-gold-plating → directive:DIRECTIVE_024/001/003` replace the deleted locality edges.

## Non-blocking (fix if touching the files anyway)
- `easy-to-change.tactic.yaml`, "Assess abstraction debt": the parenthetical "(avoid-gold-plating already references this tactic ... avoid a two-tactic reference cycle)" explains how the graph was authored. It is not doctrine, so drop it.
- `code-review-incremental.tactic.yaml`: "do not restate the step here" appears inside a description that does restate the step in one line. Keep the one-line summary so the tactic stays usable on its own, and drop that clause.
- The old incremental taxonomy's "architectural boundaries" risk class is intentionally subsumed by the intent-first taxonomy (per the WP). Acceptable.
