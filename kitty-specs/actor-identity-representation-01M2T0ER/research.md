# Research: Coord/lane actor-identity representation cluster

Phase 0 output. No unresolved `[NEEDS CLARIFICATION]` markers. No new dependencies are added
or upgraded, so the supply-chain install-safety directive (DIRECTIVE_051) is **not triggered**;
recorded here explicitly so silence is not mistaken for an unexamined default.

## Decision 1 — Reconcile the two identity representations in the CLI-local comparison layer

- **Decision**: Make the structured-dict actor and the compact-string actor compare EQUAL on the
  impl-claim identity key by reconciling inside `work_package_lifecycle._actor_key` (CLI-owned),
  projecting a compact `tool:model:profile:role` string down to the same tool-scoped key a dict
  already yields. The key stays a **bare string**.
- **Rationale**: The impl-claim gate (`_actors_compatible`) is deliberately tool-scoped and
  role-blind, and the generic-actor allowance (`existing_key in GENERIC_IMPLEMENTATION_ACTORS`) is
  a bare-string membership test. Reconciling here fixes #4665's self-conflict without touching the
  byte-identical shared projection (C-005) and without breaking the generic-actor `in` test.
- **Alternatives considered**:
  - *Canonicalize `actor_identity_str` so string→dict project equal by collapsing the string to
    bare tool.* Rejected: the projection is byte-identical to the upstream reducer copy and the
    reduced `actor` slot is written upstream; editing it locally splits the projection brain
    (C-005) and reaches into a read-only external contract (C-001).
  - *Fold role/profile into a full-tuple identity key.* Rejected: (a) breaks the bare-string
    generic-actor membership test; (b) a dict actor may carry `model=None` where the compact
    string carries `gpt-6`, so a full-tuple key would make one agent's two representations compare
    UNEQUAL — reintroducing #4665; (c) reviewer-vs-implementer distinctness is already a separate
    concern (see Decision 2), so the key does not need to carry role.
  - *Make `implement.py`'s workspace-create claim emit the same structured dict as
    `workflow_executor`.* Viable and complementary (source-side symmetry); WP01 may adopt it in
    addition to the comparison-layer fix if it is the smaller diff, but the comparison-layer
    reconciliation is the load-bearing guarantee because two emit sites can drift again.

## Decision 2 — Keep reviewer-vs-implementer distinctness on the review-claim role channel

- **Decision**: Do not encode role distinctness into the impl-claim identity key. The
  reviewer-vs-implementer collision is enforced by `review_claim_decision` (the role channel).
- **Rationale**: Verified in code — the impl-claim key never consulted role; the review seam does.
  NFR-002's matrix therefore asserts equality on the key AND refusal on the review seam, as two
  separate invariants. This also surfaces a latent weakness: `review_claim_decision` degrades to
  ALLOW when the reduced `role` slot is stale/None, which ties into Decision 3.
- **Alternatives considered**: enforcing role in the identity key (rejected, Decision 1).

## Decision 3 — #4673 is fixed CLI-side on the rejection-release/ownership path; reducer stays upstream

- **Decision**: Fix the CLI-owned mechanism (a) — the rejection path re-stamping the reviewer as
  owner via `_mt_emit_runtime_state`/`_build_claim_review_override` — so a rejection genuinely
  releases the claim and a subsequent fix-mode claim records the new implementer. Reconcile the
  three ownership authorities (transition `actor`, runtime `agent`, sticky `role` — C-006) so the
  move-task gate and the claim/review gates agree on the owner. Do NOT edit the shared reducer.
- **Rationale**: Operator decision (recorded). Mechanism (b) — the shared reducer's two-pass fold
  ordering in `spec-kitty-events` — is a read-only external contract (C-001). The CLI fix is
  expected to resolve the observed defect; FR-007/US3-AC4 make the outcome honest via live
  re-verification rather than an assumed green.
- **Alternatives considered**: a coordinated cross-repo `spec-kitty-events` fix + version bump
  (operator explicitly declined for this mission; deferred to a scoped upstream follow-up if the
  residual still bites).

## Decision 4 — #4670 fixed at a single completion-command render seam + an event-log resolver

- **Decision**: Thread the resolved reviewer identity through a single render helper (or an
  enumerated-site regression asserting every generated `--to approved/rejected` command carries the
  resolved `--agent`), AND resolve the active claimed reviewer from the event log when an
  agent-driven completion omits `--agent` (the load-bearing backstop). Preserve genuine human
  approvals as a distinct case.
- **Rationale**: The completion command is emitted by ≥5 independent f-strings; patching one leaves
  the others wrong. The event-log resolver makes the fix survive even when the generated text is
  bypassed. Reuses the already-closed #2861 compact parser / resolved-actor pattern.
- **Alternatives considered**: patching only the report text (rejected — the issue explicitly
  forbids it; leaves the actor default `st.agent or "user"` intact).

## Decision 5 — #3029 folds as the representation half only, re-verified live first

- **Decision**: Make `move-task --agent` persist the acting identity into the reduced ownership
  slot; re-verify the live path on the base first (the "no agent key" symptom is partially stale —
  `emit.py:269` now threads `agent` on the claim fold). If already green, land a characterization
  regression + evidence and close #3029.
- **Rationale**: Operator decision + finder-squad convergence; same reduced-owner slot as #4673.
- **Alternatives considered**: #3029's own alternatives (drop the flag; demote the accept gate) and
  its #2993 precondition — explicitly out of scope (C-004).

## Adversarial evidence log (post-spec squad — per contracts/adversarial-evidence-contract.md convention)

Two profile-loaded lenses (reviewer-renata quality/testability; paula-patterns fix-direction,
code-verified) challenged the spec. Dispositions:

| Finding | Disposition |
|---------|-------------|
| NFR-002 pinned role-preservation to the wrong seam (identity key vs role channel) | **changed** — NFR-002/C-002 rewritten; matrix rows split by seam |
| Ownership is 3 authorities, not 2; described but unconstrained | **changed** — added C-006; US3 test asserts named slots |
| FR-007/SC-003 asserted unconditional green despite upstream dependency | **changed** — FR-007/US3-AC4/SC-003 hedged on live re-verification |
| Generic-actor resume allowance had no FR/AC and tension with C-003 | **changed** — added FR-010; clarified C-003 |
| NFR-003 baseline SHA inconsistency + #3029 already-green contradiction | **changed** — reconciled to `0f5973a639`; carved out #3029 characterization case |
| FR-009 orphan (no SC); FR-003 metadata not in SC | **changed** — added SC-005; SC-001 now asserts metadata retention |
| C-005 ↔ C-001 latent contradiction (align both but cannot edit upstream) | **changed** — C-005 made prescriptive: projection stays byte-identical, reconcile in CLI layer |
| #4670 render whack-a-field unbounded | **changed** — FR-004 AC pushes single render helper / enumerated-site regression |
| US2 tested approval only; evidence-retention unasserted; blocked/canceled unscoped | **changed** — added rejection AC, evidence-retention AC, blocked/canceled scope-out |

No contested finding was silently dropped.
