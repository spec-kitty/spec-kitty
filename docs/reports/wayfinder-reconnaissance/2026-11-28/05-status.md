---
doc_status: draft
updated: '2026-11-28'
---

# Status of the investigation

**Interrupted on 2026-11-28.** Seven workstream agents stopped when the account's weekly usage limit was reached (reset announced for 2026-12-01 16:00 UTC). Nothing in this folder is final. No synthesis, review, evaluation or report has been started.

## Workstreams

| Workstream | State | Findings |
|---|---|---|
| A1 recorded intent | complete | 38 |
| A2 terminology | complete | 20 |
| B1 core Python structure | complete | 27 |
| B3 documented relationships against the observed graph | complete | 13 |
| C evolution and change coupling | complete | 33 |
| C2 blind replication of C | complete | 32 |
| E1 assurance inventory and experiment PX-01 | complete | 35 |
| E2 mutation author | complete | 7, with 24 patches |
| G1 invariant checks from public information | complete | 12 |
| H06a answers from documentation | complete | 21 |
| H06b check of those answers | complete | 13 |
| B2 Java services and doc-kitty structure | interrupted | partial evidence only |
| CX comparison of C and C2 | interrupted | 13 findings written, no report, unverified |
| D1 integration surface and independence, Python side | interrupted | partial evidence only |
| D2 independence of the Java services | interrupted | partial evidence only |
| E3 gate runner for the mutations | interrupted | partial evidence only |
| F allocation of execution responsibilities | interrupted | partial evidence only |
| G2 invariant checks with implementation knowledge | interrupted | 10 findings written, no report, unverified |

Files under `evidence/` and `findings/` of an interrupted workstream are unfinished and unreviewed, and their manifests are unchecked. They must not be cited until the workstream is resumed and completes.

## What is not yet measurable

- H04 (independence matrix): depends on D1 and D2.
- H07 (execution responsibilities): depends on F.
- H08 (invariant expressibility): depends on G2.
- Mutation detection and scenario AS-06: depend on E3.
- Replication status of workstream C: depends on CX.
- The Java part of H03: depends on B2.

## Known limits recorded so far

- Memory: several builds and the layer-rules gate of core were stopped by the container's memory limit while agents ran side by side. These are limits of the environment, to be re-run serially.
- Briefing gaps by the coordinator: H06b was not given the question texts; A2 was not given the definitions of the outside terms.
- Declared procedure breaches: B3 saw part of the observed graph before fixing its mapping rules; H06a had agent-guidance files in context during its documentation-only run.
- Each workstream's own deviations are in its report under `workstream-reports/`.

## To resume

Resume the seven interrupted workstreams from their briefs in `dispatch/` (their scratch work may be lost if the container was reclaimed; the briefs are sufficient to restart). Then run the two memory-blocked checks serially, then the stages in `04-approval-and-dispatch.md`: synthesis, adversarial review, post-hoc evaluation, dialectical review, report.
