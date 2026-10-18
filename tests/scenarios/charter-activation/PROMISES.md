# Charter-activation contract proposal

**Status: PROPOSED — NOT RATIFIED**

**Ratifier: not assigned**

Updated: 2026-10-18. Audience: QA and core reviewers deciding QA issue #801.

This is a proposed promise→scenario→authority ledger, not the offering suite's frozen-contract
index. The identifiers below are review candidates only. **No `@promise:` tags have been added,
no Product Promise has been ratified, and no WIP tag has been removed.** An operator-authorized
human must approve the contract wording, ownership and authority before these IDs become tags.

All 22 source scenarios have a disposition in [BINDINGS.md](BINDINGS.md), including the five
held without a new activation ID. Its step-match counts are static binding observations, not
execution results. Read [RESEARCH.md](RESEARCH.md) for the correction trail and unresolved
questions. The source revision reviewed is `0746bec30cbb473329d9a02333bafada716ecfd7`.

## Authority key and precedence

The historical mission specifications below retain their checked-in Draft/Proposed labels. We
cite their relevant requirements as traceability, **not** as new ratification and not as authority
to restore superseded commands, kind inventories, file layouts or default-list seeding. Accepted
ADRs and recorded later rulings take precedence. Code/tests corroborate a witness; they do not
by themselves turn an implementation detail into a consumer promise.

| Key | Source | Relevant scope |
| --- | --- | --- |
| A | [Activation-layer specification](../../../kitty-specs/charter-pack-activation-layer-01KSYE4V/spec.md) | FR-004/005/006/007/008, FR-014/017/018/019/027, FR-031–034/038/039, C-005: lifecycle, filtering and shared cascade safety. |
| B | [Activation-surface unification specification](../../../kitty-specs/unify-charter-activation-surfaces-01KX5SJ9/spec.md) | FR-001–004; first-run absent-key edge case, NFR-004 and C-005. No manual answers edit is part of successful activation. |
| C | [Charter-pack cutover specification](../../../kitty-specs/charter-pack-cutover-01M491G6/spec.md) | FR-001–004, FR-015 and FR-019; distinguishes preset-governed keys, effective sets and the mission-type ledger. FR-015's promotion callers are not a substitute for testing single-artifact activation. |
| D | [Accepted offering/preset ADR, 2026-10-06-2](../../../docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md) | Decisions 1–3 and amendment 6: offering versus active charter, default/minimal presets and customization protection. |
| E | [Historical activate contract](../../../kitty-specs/charter-pack-activation-layer-01KSYE4V/contracts/charter-activate-cli.md) | Behavior 2, 6, 7 and 9: unknown ID refusal and explicit cascade scope/reporting. Its shipped-default-list seeding is superseded by B/C/D. |
| F | [Historical deactivate contract](../../../kitty-specs/charter-pack-activation-layer-01KSYE4V/contracts/charter-deactivate-cli.md) | Behavior 3 and 6, Shared Artifact Protection. Its literal upgrade-to-initialize remedy is not adopted here. |
| G | [Kind-filtered cascade specification](../../../kitty-specs/cascade-asset-silent-drop-01M0RME0/spec.md) | FR-001/002/003/008 and C-001/C-006: report reached templates/assets without independently activating them. Its cited 2026-08-20-1 ADR is absent in this checkout; see the authority gap below. |
| H | [Accepted pack-skill ADR, 2026-09-27-1](../../../docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md) | Activation through the public lifecycle projects selected skills into project-local configured tools; not a new namespace or absence promise. |

## Proposed activation-distinct promises

The case references below resolve to the exact scenario identities in BINDINGS.md. These are
consumer outcomes, not byte-for-byte command output or configuration layout contracts. Every row
is **proposed, WIP, not executed**; no row is declared bound-and-green.

| Candidate ID | Proposed consumer guarantee | Authority | Case |
| --- | --- | --- | --- |
| `PR-CHARTER-ACTIVATION-001` | Adopting an available rule that was explicitly out of force puts it in force. | A FR-004/031–034/038/039; B FR-001–004. | A01 |
| `PR-CHARTER-ACTIVATION-002` | Retiring an explicitly chosen, non-required rule takes it out of force. | A FR-005/031–034; B FR-004. | A02 |
| `PR-CHARTER-ACTIVATION-003` | Explicitly adopting a rule from an unrestricted set does not silently drop the other effective rules. | B first-run edge case, NFR-004/C-005; current preservation witness in `test_activation_preserves_effective_4253.py`. C FR-015 supports related promotion behavior, not this command alone. | A03 |
| `PR-CHARTER-ACTIVATION-004` | An unknown artifact ID within a valid kind is refused, leaving effective governance and saved choices unchanged. | E Behavior 2; AGENTS.md activation-engine validation-before-commit rule; current validation/commit evidence. Not the broken-charter contract. | A04 |
| `PR-CHARTER-ACTIVATION-005` | Cascade retirement removes its selected source but keeps a referenced rule still shared by another active choice, naming the surviving reference. | A FR-008/C-005; F Behavior 6 and Shared Artifact Protection. This is cascade-candidate safety, not a ban on explicit direct retirement. | A05 |
| `PR-CHARTER-ACTIVATION-006` | Retiring a rule from an unrestricted kind refuses without inventing a restrictive set, and explains how to establish explicit control. | F Behavior 3, with its obsolete literal upgrade remedy excluded; current absent-versus-empty semantics. | A06 |
| `PR-CHARTER-ACTIVATION-007` | Explicit all-reference adoption brings the selected profile and its referenced activatable governance into force. | A FR-007; E Behavior 7. The exact `requires`/`suggests` relation-set question remains open below. | A07 |
| `PR-CHARTER-ACTIVATION-008` | Scoped adoption brings referenced artifacts of the selected kinds into force, leaves initially inactive out-of-scope references inactive, and identifies them. | A FR-007/Journey 4; E Behavior 7/9. It does not activate an entire kind's catalogue. | A08 |
| `PR-CHARTER-ACTIVATION-009` | Adoption without cascade succeeds for the profile, leaves explicitly excluded references out of force, and explains what was omitted and how to bring it. | A FR-006; E Behavior 6. Warning is not dependency enforcement. | A09 |
| `PR-CHARTER-ACTIVATION-010` | Cascade names each reached template/asset as not independently activatable while still activating an ordinary referenced target. | G FR-001/002/003/008, C-001/C-006. Exclusion is not failure to resolve or use those artifacts. | A10 |
| `PR-CHARTER-ACTIVATION-011` | Adopting an available pack-provided mission type makes that previously unavailable-to-run type usable with the steps its pack defines. | A FR-004/014/027; D Decisions 1–3. Mission types use their separate activation ledger, not an absent artifact-kind default. | A15 |
| `PR-CHARTER-ACTIVATION-012` | Adopting an available but explicitly excluded pack profile makes work assigned to it governed by that profile. | A FR-017/018/019/034; B FR-004; D Decision 1. Presence in a list alone is not the work-effect witness. | A16 |
| `PR-CHARTER-ACTIVATION-013` | Making a non-requiring pack available does not widen the project's explicit restrictions, nor remove governance already in force. | A FR-031–034/038/039; B FR-001; D Decision 1. Scope excludes a new org-required union, already offering-owned. | A17 |
| `PR-CHARTER-ACTIVATION-014` | Under an unrestricted ordinary-kind default, an available ordinary rule applies without individual adoption. | D Decision 2; C FR-002/003; `ArtifactKind.effective_when_absent` corroborates the per-kind scope. This says nothing about absent mission-type ledgers or unconfigured packs. | A18 |
| `PR-CHARTER-ACTIVATION-015` | Adopting one offered, unrequired shareable command projects that choice into the configured project tool without adopting its unselected sibling. | H Activation and Project scope; D Decision 1. This is the lifecycle transition, not a second claim of offering-owned default skill absence. | A19 |
| `PR-CHARTER-ACTIVATION-016` | Making another ordinary rule available extends an unrestricted default without removing the rules already effective. | D Decisions 1/2; C FR-015 effective-set scope; current whole-offering resolution evidence. No new skill-absence guarantee is asserted. | A20 |
| `PR-CHARTER-ACTIVATION-017` | Adopting the built-in minimal baseline selects its curated directives/tactics while leaving the other kinds it does not govern unrestricted. | D Decision 2; C FR-001/002/019; built-in `minimal` preset data. Org-required additions remain independent constraints. | A22 |

## Held without new activation IDs

| Cases | Reason and proposed disposition |
| --- | --- |
| A11 filesystem provisioning; A12 published-reference fetch/pinning | Offering/acquisition, not activation. Retain the drafts as WIP for explicit ownership/authority review; do not mint activation promises or treat #3504's release-time re-vendoring as a runtime installer guarantee. #5243 still tracks a canonical external pack lifecycle. |
| A13 missing-pack refusal | Retain as a WIP witness candidate for the real #4984 fail-open defect. Choose a governed consumer rather than `doctor` alone, which already diagnoses absence. Do not call a defect report itself ratification of a new activation promise. |
| A14 supply-order layering | Retain for offering-composition ownership review. Limit the scenario to same-layout collisions: the chain specification explicitly preserves a different flat-layout precedence for mixed-layout collisions. No unconditional last-pack-wins activation guarantee is proposed. |
| A21 maintainer-only opt-in | Retain for packaging/init policy review against the accepted internal-pack ADR and #3505. The open seeding-policy issue is not evidence that every possible maintainer-only artifact universally requires a new activation verb. |

No held scenario is deleted, silently mapped to a weaker check, or promoted to gating.

## Offering-owned facts that this proposal does not remint

Selection overlay remains `PR-CHARTER-GOVERNANCE-002`; broken-charter refusal remains
`PR-CHARTER-REFUSAL-003`; namespace/reserved-prefix validation remains
`PR-CHARTER-SHARING-003`. Default offered-but-unrequired skill absence remains
`PR-CHARTER-GOVERNANCE-001`. The old skill-absence draft is replaced by A19's actual adoption
transition; ordinary pack extension A20 no longer repeats the skill-absence assertion. See the
[offering ledger](../charter/PROMISES.md).

## Ratifier decisions, not agent approvals

1. Approve, amend or reject the 17 candidate consumer contracts and their scenario corrections.
   Name an authorized QA ratifier; authoring this proposal does not provide that authority.
2. Decide where the five held cases belong. Recommendation: preserve the source drafts and
   commission a separate offering/acquisition/policy review, without expanding this activation
   contract into an installer specification.
3. Confirm the exact DRG reference-relation authority for A07: current `cascade.py` traverses
   `requires`/`suggests`, but the historical `FR-014` citation is unrelated and the referenced
   `2026-08-20-1` ADR is missing here. Recover the decision record or explicitly approve the
   relation-set contract before freezing it. This gap does not authorize hard-coded per-kind logic.

After approval, apply the approved `@promise` tags and record the real ratifier/review reference.
Bind the real witness for every agreed case, including documented red-for-a-real-defect cases;
remove WIP only through QA/core review with actual execution evidence. Do not interpret a stub,
undefined step or absent fixture as an acceptable product red.

## Relationship to QA Product Promises

These proposed `PR-CHARTER-ACTIVATION-*` identifiers follow the existing core **contract-ledger**
namespace. They do not mint `PP-*` pages or enter QA's private Product Promise index. Any later
PP verification plan/mapping must name the reviewed scenario digest and authority separately;
its product-authority ratification is a different act. No namespace rename or equivalence is
silently decided by this proposal.

Plan/commit atomicity for a broken charter is already offering-owned; this proposal does not add
a duplicate atomicity scenario. Action-scoped context remains deliberately deferred: it needs
its own outcome and authority review, not a byte-for-byte `context` output check.
