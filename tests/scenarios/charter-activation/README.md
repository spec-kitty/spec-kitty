# Charter-activation scenarios — proposed contracts, not ratified

Audience: QA/core reviewers of [spec-kitty-qa#801](https://github.com/spec-kitty/spec-kitty-qa/issues/801).
Updated: 2026-10-18.

These 5 feature files / 22 scenarios describe activation lifecycle outcomes ahead of the charter
extraction. Their source remains here in core, alongside the existing offering suite under
[`../charter/`](../charter/); QA owns the proposed promise tie-in and review. The extraction has
two sibling seams, `charter.offering.api` and `charter.activation.api` (ADR 2026-10-12-2, #6099).

## Review surfaces

- [PROMISES.md](PROMISES.md): **17 candidate activation IDs**, authority references, five held
  cases without new activation IDs, and the human decisions still required. **Not ratified.**
- [BINDINGS.md](BINDINGS.md): one row per scenario, current exact-one-step-match counts, concrete
  positive/negative controls, proposed binding priority and real blockers. **No execution claimed.**
- [RESEARCH.md](RESEARCH.md): grounding, corrected ambiguities, historical authority limits,
  ownership exclusions and identity changes.

There are still **no `@promise:` tags**: proposing an ID does not authorize its ratification.
All scenarios retain `@wip`, owner and since metadata. All four common Background steps match,
but no scenario-specific outcome vocabulary is bound yet. A green per-PR syntax/tag/binding-shape
check therefore does not prove these activation scenarios execute or pass. The proposal's focused
consistency test checks its row coverage/count claims; it is not a substitute for acceptance runs.

## Consumer outcome families

| Folder | Scope and review posture |
| --- | --- |
| `turning-governance-on-and-off/` | Effective adoption/retirement; preserving an unrestricted set when one existing rule is explicitly adopted; unknown-ID refusal without changing saved/effective governance. |
| `turning-off-keeps-the-rest-sound/` | Cascade-specific shared-reference safety and refusal to retire from an unrestricted kind. Not a universal ban on directly retiring referenced governance. |
| `brings-what-it-depends-on/` | All-reference/scoped/no-cascade adoption and visible template/asset exclusion. Warning is not dependency enforcement. Exact reference-relation authority needs ratifier review. |
| `provisioning-governance-packs/` | Three proposed activation outcomes for pack mission types/profiles and explicit restrictions; four acquisition/composition drafts held for ownership/authority review. No installer specification is silently created. |
| `the-default-governance-profile/` | Ordinary unrestricted defaults, actual selected-skill adoption, ordinary pack extension and the scoped minimal preset; maintainer-only opt-in held for policy review. |

## Before binding or promoting

The default Background does not establish that an offered artifact is inactive. Per-scenario
starting sets must be witnessed: absent ordinary-kind keys are unrestricted, an explicit empty
selection is not absence, skills have a required-only default, and mission types use a separate
ledger. Restrictions and unrestricted provisioning are two different cases, not contradictory
universal promises. The minimal preset restricts only the keys it governs.

Adoption/retirement must drive the real public lifecycle and observe the governed effect. A list
of config IDs, a fresh-project synthesize seed, a fabricated result or a stub assertion cannot
stand in for that effect. The per-scenario table spells out the stronger profile/mission/tool
witnesses and no-op controls.

QA/core still need to implement the agreed bindings and capture real results after human contract
review. Bind all agreed cases; a genuine product-red must be tied to a real defect and execution
evidence, not an undefined step. No WIP is removed by this proposal.

## Boundaries

No manual QA page or legacy executor is moved/retired. No existing offering guarantee is reminted:
selection overlay, broken-charter refusal and namespace grammar stay offering-owned; offered-but-
unrequired skill absence stays `PR-CHARTER-GOVERNANCE-001`. The skill scenario here now witnesses
an adoption transition instead of repeating that absence assertion.

Action-scoped context remains deliberately deferred. Broader plan/commit atomicity is not added
as a duplicate of the offering broken-charter contract. The candidate `PR-*` identifiers are core
contract-ledger proposals, not QA `PP-*` Product Promise pages or a silent namespace migration.
The operator-authorized human ratifier is still to be named; the operator merges.
