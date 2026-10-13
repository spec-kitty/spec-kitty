# Plan phase: orchestrator ruling and operator decisions (2026-10-10)

## Orchestrator ruling: one bounded fix and verify round

The plan phase halted under the early-stop rule (R6). After round 3, seven findings at severity 3 or
higher survived: PLAN-FRESH3-001 to 005 (`reviews/plan-fresh-r3.yaml`) and PLAN-NEW3-001 and 002
(`reviews/plan-verify-r3.yaml`).

Each finding has one concrete remediation stated in its review file, and none of them reopens an
operator decision. Under the operator's standing rule for remedy-obvious HALTs, the orchestrator
grants ONE further fix and verify round without asking the operator. If anything at severity 2 or
higher survives that round, or a finding turns out to need a design choice, the phase halts and
goes to the operator.

## Operator decisions on the plan escalations (section 14)

- **E-1, AC-9b Host refusals.** Split the expectation. A Host value the filter can see is refused
  with 403 `request_refused`. A malformed Host value that the container rejects itself keeps the
  container's 400. The spec fixes the list of values that get 400. Both kinds are refused before
  any read. No custom container valve.
- **E-4, release job.** Ship it in this mission. Extend AC-15a with the tag pattern, the job `if:`,
  `contents: write` on that job only, tag-aware concurrency, and a tag pattern disjoint from
  `v*.*.*` and `contract-*-v*.*.*`, as plan section 12 specifies. The maintainer cuts the first
  tag.
- **E-10, nightly exemptions.** None. The nightly fails on any Java/Python difference and names
  the Mission and the class. D-Q1 and AC-8c are unchanged.
- **E-11, the OpenAPI document.** Contract-first. The running service serves the committed
  `contracts/mission-status` OpenAPI document as it stands, bundled at build time, at a fixed path
  under `/api/v1/`. springdoc does not generate or serve a document at runtime, and the spec
  drops or re-scopes springdoc to match (FR-009, C-001, C-004). The issue text gets a one-line
  correction, which the orchestrator makes with the operator's consent.

The other escalations (E-2, E-3, E-5 to E-9, E-12, E-13) keep the interim behaviour the plan
states. The PR records E-5, the last workflow slot, and E-9, the check is not required.

## Operator authorization (2026-10-10)

Second plan HALT: one further round for PLAN-NEW4-001 (delete `contractdoc`, tests under `adapter/in/http`) and PLAN-NEW4-002 (spec clause), remedies chosen by the operator.
