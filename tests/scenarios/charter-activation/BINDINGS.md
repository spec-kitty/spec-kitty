# Per-scenario binding and WIP disposition — QA #801

Updated: 2026-10-18. Audience: the QA/core reviewers and engineer implementing the accepted
witnesses. This is a **proposal**, not approval to remove WIP or a record of passing executions.

## What was actually checked

The canonical `scripts.ci.scenario_contract` reader/Java-step matcher was run against the source
in this proposal and `acceptance-jvm/src/test/java/kitty/acceptance/steps/`. **None of these 22
scenarios is fully bound.** In every row, the four matched steps are the common project /
interview / generation / synthesis Background only. No scenario-specific outcome step currently
matches. Bound/total counts include that Background and mean **exactly one matching definition**,
not successful execution. The focused `test_charter_activation_proposal.py` test rechecks the
counts and one-to-one row coverage; the full contract check still applies to the whole tree.

Every source scenario retains its existing `@wip`, `@wip-owner` and `@wip-since` tags. Those name
the current draft owner/date, not approval, execution evidence or the newly authorized ratifier.
No `@promise` tags are applied before human review of [PROMISES.md](PROMISES.md).

## Status meanings

- **READY-TO-BIND**: a grounded outcome with concrete controls; an engineer must implement a real
  black-box fixture/Act/assertion. A missing Java step is engineering work, **not** an acceptable
  product-red reason and not evidence of a defect.
- **AUTHORITY-REVIEW**: the generic behavior is grounded, but a stronger proposed detail needs
  the decision record recovered or human approval before the contract is frozen.
- **HOLD-OFFERING / HOLD-POLICY**: retained draft whose ownership/scope must be decided outside
  activation ratification; not silently removed or mapped to a weaker activation check.
- **HOLD-DEFECT-WITNESS**: a real issue reports the target defect, but the candidate still needs
  a bound reproduction at a governed consumer. It is **not** declared reproduced at this revision.

All rows are presently **WIP / unexecuted**. Candidate IDs are unratified references to the
proposal; `—` means no new activation promise is proposed for that case.

| Case | Scenario ref (relative to this folder) | Candidate | Bound/total | Proposed disposition | Required witness / blocker |
| --- | --- | --- | --- | --- | --- |
| A01 | `turning-governance-on-and-off/turning-governance-on-and-off.feature#Adopting a rule puts it in force` | `PR-CHARTER-ACTIVATION-001` | 4/9 | READY-TO-BIND | Establish a real explicit subset via the activation CLI, with an available non-required rule excluded; compare effective membership before/after adopting it. No direct writes to activation state to manufacture the fixture. |
| A02 | `turning-governance-on-and-off/turning-governance-on-and-off.feature#Retiring a rule takes it out of force` | `PR-CHARTER-ACTIVATION-002` | 4/9 | READY-TO-BIND | Start with a non-required rule effective in an explicit set; retire through the CLI and verify consumer absence, not merely config-list removal. The absent-versus-present control defeats an always-refusing/no-op implementation. |
| A03 | `turning-governance-on-and-off/turning-governance-on-and-off.feature#Explicitly adopting a rule preserves the unrestricted rules already in force` | `PR-CHARTER-ACTIVATION-003` | 4/8 | READY-TO-BIND | Initialize/apply the real default preset, record at least two effective rules, explicitly adopt one already-effective rule, and compare the entire effective before-set against after. Do not invent an additional rule outside an already-unrestricted catalogue. |
| A04 | `turning-governance-on-and-off/turning-governance-on-and-off.feature#Naming governance that does not exist changes nothing` | `PR-CHARTER-ACTIVATION-004` | 4/9 | READY-TO-BIND | Use an unknown ID in a valid kind on a valid charter; snapshot saved activation choices plus effective membership, retain the non-zero Act and actionable reason, and prove both views unchanged. Not the broken-charter fixture. |
| A05 | `turning-off-keeps-the-rest-sound/turning-off-keeps-the-rest-sound.feature#Governance still relied on by another active choice is kept, and the reason is named` | `PR-CHARTER-ACTIVATION-005` | 4/9 | READY-TO-BIND | Author two same-kind choices A/B that both reference rule R; activate all via CLI. Cascade-retire A; prove A gone, B and R remain, and B is named as the reason. No-op retirement must fail. |
| A06 | `turning-off-keeps-the-rest-sound/turning-off-keeps-the-rest-sound.feature#Retiring a kind of governance the project never controlled is refused with the way forward` | `PR-CHARTER-ACTIVATION-006` | 4/10 | READY-TO-BIND | Witness an absent ordinary-kind key through the default CLI path, not explicit empty selection. Refusal must retain effective governance and saved choices and name a current way to establish explicit control; do not pin the obsolete upgrade hint. |
| A07 | `brings-what-it-depends-on/brings-what-it-depends-on.feature#Adopting a choice can bring its required and suggested governance in one step` | `PR-CHARTER-ACTIVATION-007` | 4/8 | AUTHORITY-REVIEW | Author distinct requires and suggests edges plus an unrelated same-kind control; start profile/targets explicitly inactive. Prove both referenced targets become effective and the unrelated one does not. Recover/approve the exact relation-set authority before freezing this stronger detail. |
| A08 | `brings-what-it-depends-on/brings-what-it-depends-on.feature#The author can limit how far adoption reaches` | `PR-CHARTER-ACTIVATION-008` | 4/12 | READY-TO-BIND | Use references in at least two kinds plus an unrelated artifact in a selected kind, all explicitly inactive beforehand. Activate with selected scope; test source/selected targets active, unrelated same-kind and excluded targets still inactive, and named skipped references. Activating the whole selected kind must fail this control. |
| A09 | `brings-what-it-depends-on/brings-what-it-depends-on.feature#Adopting a choice on its own tells the author what was left behind` | `PR-CHARTER-ACTIVATION-009` | 4/10 | READY-TO-BIND | Retain the no-cascade Act result and its actionable reference report, then probe effective sets: profile active, referenced targets still inactive. A warning is not a promise to reject the incomplete dependency set. |
| A10 | `brings-what-it-depends-on/brings-what-it-depends-on.feature#Adoption reports templates and assets as not independently activatable` | `PR-CHARTER-ACTIVATION-010` | 4/9 | READY-TO-BIND | Author one activatable tactic and both non-activatable kinds in one reference fixture. Verify real tactic activation and per-ID/kind exclusion reporting for template/asset. Do not stub them as unresolved, and do not treat widening cascade scope as their remedy. |
| A11 | `provisioning-governance-packs/provisioning-governance-packs.feature#A pack supplied by a filesystem location is provisioned and its catalogue becomes available` | — | 4/8 | HOLD-OFFERING | Review acquisition/provenance ownership first. Use a disposable authored pack and supported registry configuration, then demonstrate its distinctive content and provenance through a public consumer. #5243 is not satisfied by fabricating a completed install receipt. |
| A12 | `provisioning-governance-packs/provisioning-governance-packs.feature#A pack supplied by a published reference is fetched and provisioned the same way` | — | 4/8 | HOLD-OFFERING | Review source/version/pinning authority and #5243 first. A later fixture should fetch a local disposable git reference without credentials/remote network and compare the retrieved immutable identity; release-time re-vendoring #3504 is not this runtime guarantee. |
| A13 | `provisioning-governance-packs/provisioning-governance-packs.feature#A pack the system cannot resolve is refused, not treated as empty` | — | 4/9 | HOLD-DEFECT-WITNESS | #4984 reports governed consumers failing open. Build a valid-to-missing pack pair at context/dispatch or another agreed governed consumer; assert refusal before governed work, not merely doctor reporting unhealthy. No current reproduction or green result is claimed. |
| A14 | `provisioning-governance-packs/provisioning-governance-packs.feature#Several packs are layered in the order they were supplied` | — | 4/9 | HOLD-OFFERING | Review composition ownership. Use two same-layout packs with a distinctive colliding rule body and prove later-declared content wins. Mixed-layout precedence is explicitly outside this draft; presence of both IDs is too weak a witness. |
| A15 | `provisioning-governance-packs/provisioning-governance-packs.feature#Activating a mission type from a pack makes it a choice the project can run` | `PR-CHARTER-ACTIVATION-011` | 4/9 | READY-TO-BIND | Author a pack mission type with distinctive steps; show it available but not runnable under the current mission-type ledger. Activate through CLI, start a disposable mission of that type and inspect its real step sequence. Listing alone is insufficient. |
| A16 | `provisioning-governance-packs/provisioning-governance-packs.feature#Activating an agent profile from a pack makes it apply to the work` | `PR-CHARTER-ACTIVATION-012` | 4/9 | READY-TO-BIND | Author a non-required profile with a distinctive governance marker, initially available but excluded. Activate via CLI and start/resolve work actually assigned to it; witness its governance effect, not just its name in an effective list. |
| A17 | `provisioning-governance-packs/provisioning-governance-packs.feature#Provisioning a pack respects the project's existing restrictions` | `PR-CHARTER-ACTIVATION-013` | 4/10 | READY-TO-BIND | Establish explicit same-kind restrictions through public activation before registering another non-requiring pack. New content becomes available but not effective; previously effective content remains. Org-required overlay is deliberately excluded. |
| A18 | `the-default-governance-profile/the-default-governance-profile.feature#Before choosing anything, ordinary governance follows the unrestricted default` | `PR-CHARTER-ACTIVATION-014` | 4/9 | READY-TO-BIND | Use an ordinary artifact kind following its absent-key default, show an individually unselected rule available/effective, and distinguish this from skills, mission types and an unconfigured internal pack. Background defaults alone are not proof of the state. |
| A19 | `the-default-governance-profile/the-default-governance-profile.feature#Adopting a shareable command brings it into force without adopting its sibling` | `PR-CHARTER-ACTIVATION-015` | 4/11 | READY-TO-BIND | Author two valid namespaced project-tool skills with no required entries. Both available/neither effective or projected before; adopt one, verify its project-local projection plus effective membership, and keep the sibling inactive AND unprojected afterward. Installing both skills must fail this control. No namespace-grammar or generic default-absence promise is reminted. |
| A20 | `the-default-governance-profile/the-default-governance-profile.feature#Provisioning ordinary governance extends an unrestricted default` | `PR-CHARTER-ACTIVATION-016` | 4/9 | READY-TO-BIND | Start with an unrestricted ordinary kind and record its effective rules. Register a resolved pack adding a distinct rule; prove new rule available/effective and old rules retained. Do not add a duplicate offered-skill-absence assertion. |
| A21 | `the-default-governance-profile/the-default-governance-profile.feature#Maintainer-only governance is never in force unless the project opts in` | — | 4/8 | HOLD-POLICY | Internal-pack packaging separation is accepted, but #3505 still asks how first-party init opt-in/seeding works. Get a scoped consumer/init policy decision and supported opt-in witness; do not infer universal activation semantics from an unconfigured pack's absence. |
| A22 | `the-default-governance-profile/the-default-governance-profile.feature#A project can start from a small curated baseline instead of everything` | `PR-CHARTER-ACTIVATION-017` | 4/10 | READY-TO-BIND | Start unrestricted with known extra directives/tactics effective. Apply the real built-in minimal preset through CLI, compare governed selections (allow independent org requirements), and verify a known open-kind artifact remains effective. Literal preset lists are data, not a second hand-copied baseline. |

## Fixture and promotion rules

Reuse the common Arrange/Assume/Act/Assert library and acceptance driver. Author user-owned pack
files and supported user configuration; use public commands to establish activation state. Do not
write generated charter/reference/activation state directly to manufacture a passing lifecycle.
Keep the existing redirected HOME/runtime/XDG and project-local tool roots; no real credentials,
operator workspace or remote service is a fixture. Preserve the Act's result before a later list
or context probe overwrites the scenario's last result.

The expected adoption witness is an actual effective-state transition, using the existing public
`charter list` versus `charter list --all` views where suitable. Pack/profile/mission/tool effects
need their stronger consumer witnesses above. Membership cannot substitute for execution of a
mission type's declared steps or application of a profile to assigned work.

After human scope/contract review, implement the agreed witnesses. Bind real cases even when a
known product defect makes them red, documenting the defect and actual execution result. Leave
a scenario WIP only for an explicit unresolved fixture/seam/authority reason. **This proposal does
not complete that binding work or the ratification requested by #801.** QA/core review and real
execution evidence precede any gating promotion. No manual QA page, legacy executor, existing
offering contract or other repository is changed or retired here.
