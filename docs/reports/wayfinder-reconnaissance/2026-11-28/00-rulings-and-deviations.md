---
doc_status: draft
updated: '2026-11-28'
---

# Rulings, deviations and prior exposure

This file records what the human architect ruled on 2026-11-28, which charter rules the investigation departs from with that authority, and what the coordinator had already seen before the pre-registration was written.

## 1. Rulings of the human architect

| # | Subject | Ruling |
|---|---|---|
| R1 | Storage | Additive-only documentation under `docs/reports/wayfinder-reconnaissance/2026-11-28/` on the research branch. No existing product documentation or implementation is modified. |
| R2 | Mission vehicle | The hybrid vehicle is approved in principle (see section 2). The suspected research-mission completion defect is an investigation finding, to be verified in a disposable environment if feasible. It is not an implementation assignment. |
| R3 | Independence | Replacing an implementation behind an interface and extracting a capability are not contradictory. Independence is assessed on five separate dimensions (section 3). Repository separation, service extraction or network communication do not establish independence, and in-process composition does not preclude it. |
| R4 | Four views | Recorded historical intent, observed implementation, proposed future direction and approved target architecture are kept apart. The design brief contains proposals. A conflict between a recorded decision and a proposal informs a later decision; it is not an implementation violation. |
| R5 | Terminology | Kira, HUD, Operations Deck and similar concepts describe a prospective consumption context. Their absence from the repositories is not a deficiency. Paperclip is a comparison only. Ecosystem terms are kept, and prospective concepts are mapped to them. |
| R6 | Maintenance window | Agent involvement is not a proxy for supervision. Capability growth, corrective maintenance, review intensity, convergence activity and compatibility work are separated. The hypothesis concerns sustained local optimisation without sufficient system-wide architectural governance, whoever made the changes. The convergence is a structural discontinuity and is investigated separately. The architect confirms the window independently of agent-participation figures. |
| R7 | Execution | Workstream F investigates where execution responsibilities sit (core runtime, external tools, human operations, external coordination, other components) and whether each is absent, delegated, specified but unimplemented, or intentionally out of scope. The accommodations this investigation needed are supplementary evidence, not to be generalised without corroboration. Desk assessment of H08 and AS-10 is acceptable and is never presented as empirical verification. |
| R8 | Revision model | The head / core-pin / released distinction is approved. Integration and dependency versions are recorded. Where meaningful, the development architecture is distinguished from the architecture of the supported distribution. |
| R9 | Method | Neutral dispatch, evidence-first synthesis, independent review, separation of mutation author and gate runner, and reproduction sampling are approved. Pre-registered measurements are kept apart from exploratory observations. Evidence of deterioration is kept apart from evidence for a cause. |
| R10 | Controls | A blind replication of workstream C under a different model. A redacted prediction packet for the outside observer, whose predictions are recorded before any substantive finding is disclosed. |
| R11 | Coverage | The Charter and Events Java implementations are in scope for structure and contracts. Static analysis of Events is acceptable while dependency retrieval blocks its build. Inaccessible repositories and blocked builds are recorded and are never evidence of an architectural defect. |
| R12 | Authority | Non-remedial. No production implementation change is authorised. The purpose is evidence for the design of Wayfinder, not a defence of its preliminary design. |

## 2. Authorised deviations

Each deviation is authorised by the human architect in the role the charter calls human in charge, for this investigation only.

### D-1. Mission-sized work run outside the mission runtime

- **Rule departed from.** The built-in directive on Op and Mission boundaries (`packs/built-in/directives/053-*.yaml`) treats Mission-sized work run as a chain of Ops as non-compliant. This work is Mission-sized: it spans several sittings, splits into workstreams, needs a review gate and must be resumable.
- **What is done instead.** One `research` Mission, created with `--topology single_branch` and the research branch as its target, holds the specification, the plan and this pre-registration. The workstreams run as subagents that each load their agent profile. They do not advance through `spec-kitty next`.
- **Rationale.** Grounding read the research mission's step guards in `src/runtime/next/` and found readers of two event kinds with no writer and no CLI command that produces them. If that holds, a research Mission cannot reach its end through the documented surface, and working around it by writing the event log by hand would breach the canonical-sources rule. The suspected defect is itself in scope as pre-registered experiment PX-01.
- **Consequences accepted.** The Mission will not reach `done` through the runtime. Work-package status events, lane worktrees and the review gates of the runtime are not exercised. Review independence is provided by the method in the pre-registration instead.
- **Retirement.** The deviation ends when the investigation is handed back.

### D-2. Research branch, no pull request

- **Rule departed from.** The charter's collaboration strategy asks for an `issue-<n>-<slug>` branch and a draft pull request.
- **What is done instead.** Work is committed to the designated branch `claude/spec-kitty-arch-reconnaissance-fdeicj` and pushed there. No pull request is opened and nothing is merged by the investigation.
- **Rationale.** The architect designated the branch and asked for no pull request until asked. Whether these reports ever reach `main` is the architect's decision.

### D-3. Pre-existing failures are recorded, not filed

- **Rule departed from.** The charter's pre-existing failure reporting rule asks for a tracker issue per pre-existing failure found.
- **What is done instead.** Such failures are recorded as findings in this folder. No issue is opened by the investigation.
- **Rationale.** The mandate is read-only and non-remedial. The architect decides which findings become tracker issues.

### D-4. Profiles cast by declared focus, not all architects

- **Departure from the brief, not the charter.** The brief asks for architect profiles on every workstream. The charter's squad procedure asks for casting by each profile's declared focus. The cast in the pre-registration follows the charter.

## 3. The five independence dimensions

Every capability is assessed on each dimension separately. A capability can be independent on one and coupled on another, and a declared decision not to pursue a dimension is recorded as such.

| Dimension | Question |
|---|---|
| Logical | Is there one named owner of the responsibility, with a boundary that other components respect? |
| Contract | Do consumers reach the capability only through an explicit, versioned public interface? |
| Source | Can the implementation change, or be replaced, without editing its consumers? |
| Distribution | Can it be built, versioned, released and installed on its own? |
| Deployment | Can it run as its own process or unit, and does anything require that it does? |

### Reassessment of the grounding claim on Charter

Grounding reported that the brief's phrase "complete Charter extraction" contradicts the recorded direction. Under ruling R3 that claim is withdrawn in its general form:

- A frozen seam (`charter.offering.api`) with a replacement implementation behind it serves contract and source independence. It is compatible with the proposed direction.
- What remains as a recorded, narrower statement: the core charter and its ADRs say that no Python moves to `spec-kitty-charter`, and that the earlier decision to extract the charter into its own repository is superseded. That is a decision about the source and distribution dimensions of the Python implementation. Whether it conflicts with the proposed direction depends on what the proposal means for those two dimensions. This is listed as an open decision for the architect, not as a deviation.
- The same applies to Events: contracts and Java services are in `spec-kitty-events`; the status reducer and the ledger files stay in core. The investigation measures each dimension as found and judges nothing by where the code sits.

## 4. Prior exposure

The pre-registration is not fully blind. Before it was written:

- The grounding squad measured raw import-graph counts (modules, edges, modules in cycles) at eleven revisions of core, without normalisation. The coordinator has read them. The architect has not been shown them, and they are withheld from the prediction packet.
- Grounding ran the Events packaged conformance suite against the PyPI wheel, ran the doc-kitty validators against the other repositories, and counted architectural tests, ratchet baselines and ADRs.
- The coordinator has read the core `CLAUDE.md`, which describes many known residuals in the project's own words.
- The grounding squad proposed a candidate maintenance window from history shape and agent-participation figures. Under ruling R6 that proposal has no standing; the window is the architect's to give.

The thresholds in the pre-registration were set from the hypothesis wording and the reviewer's proposals, not tuned to these figures. Where a threshold could have been informed by them, the pre-registration says so. The grounding notes are kept and will be committed as raw material with the evidence.
