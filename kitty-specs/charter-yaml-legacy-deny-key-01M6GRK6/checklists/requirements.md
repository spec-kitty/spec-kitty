# Specification Quality Checklist: A legacy `deactivated_<kind>` key on `charter.yaml`

**Created**: 2026-11-03 · **Feature**: [spec.md](../spec.md)

## Content Quality
- [x] Focused on the outcome (the contract question #6855 defers is decided and pinned)
- [x] Code-surface anchors are appropriate for a pydantic-model + activation-layer change
- [x] All mandatory sections completed
- [x] The rejected side of the decision (accepting the key) is recorded with its evidence, not
      silently dropped

## Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers (the ADR and the preceding mission decide the contract)
- [x] Requirements testable and unambiguous; FR/NFR/C separated; IDs unique
- [x] Status values present; NFRs measurable (0 new emitted keys, 0 module-level imports into
      the writer layer, O(1) prefix scan, pre-existing tests unmodified)
- [x] Success criteria measurable and outcome-framed (SC-001..SC-004)
- [x] Scenarios and edge cases (unknown deny kind, `deactivated_assets`, non-string keys, the
      all-allow-keys document, the import graph)
- [x] Scope bounded: one validator, two docstrings, one test block; no writer, ledger,
      migration or compiler change, no emitted-byte change
- [x] Dependencies and assumptions identified (ADR 2026-10-19-1 C-003; `DENY_KEYS` as the deny
      vocabulary; `schemas` must not import the writer layer)

## Feature Readiness
- [x] FRs map to SC-001..SC-004
- [x] The design fork (declare the fields vs refuse with a named message) is recorded as a
      decision with the rejected alternative and why (research.md R5, plan.md D1)
- [x] No implementation leakage beyond the necessary model/test anchors: the spec states the
      contract, the plan holds the validator shape

## Notes
- The issue's option 1 ("the model accepts and reports") is rejected, not deferred: ADR
  2026-10-19-1 Decision 1 (C-003) is operator-authored, and a declared field would be emitted
  by `charter.activation.compiler` into every generated charter. The operator asked to be told
  when backward compatibility conflicts with a deliberate strictness decision; the evidence is
  one-sided for strictness and is recorded in the spec's "Which side" section.
