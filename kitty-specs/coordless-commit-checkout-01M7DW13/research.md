# Research: coordless-commit-checkout-01M7DW13

The full grounding (reproductions on `d7cedd7e`, root causes, invariants, architectural gates,
similar-surfaces and tracked-issues squads) is committed before the spec at
`docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`.
Slice 1 research is reused from `kitty-specs/checkout-verdict-agreement-01M7B1GG/research.md`.

## Decisions

- **Decision:** coordination-less checkout = seam `write_dir(STATUS_STATE).surface_root` when the
  ref is the seam's `write_target(STATUS_STATE).ref`, else the repository root checkout.
  **Rationale:** #7615 made the seam the one checkout authority; the read door agrees with it.
  **Alternatives:** keep the holder probe (rejected: (a) writes land where reads never look).
- **Decision:** refuse up front with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` when that
  checkout does not hold the ref. **Rationale:** operator ruling Q8 option a for shape (b); for
  (a) and the lane-holder row the seam checkout can never hold the ref (git allows one holder),
  so routing there can only fail, late. **Alternatives:** late `SafeCommitHeadMismatch` (rows
  written then rolled back), keep holder routing for (a). Decision Moment `01M7DW21P5D4WNVCGC6ARASAV3`.
- **Decision:** review claim commits the status pair only. **Rationale:** precedent #5673
  (implement claim); the claim writes no WP-file byte. **Alternatives:** a content check before
  the PRIMARY transaction in `_commit_via_coordination_transaction` (wider, deferred).
- **Decision:** `commit_idempotent` catches only `SafeCommitStagedTreeUnchanged`. **Rationale:**
  PR #7639 pattern; typed signal, raised only on the index authority. **Alternatives:** make the
  pending check fail closed (rejected: would mask real errors).
