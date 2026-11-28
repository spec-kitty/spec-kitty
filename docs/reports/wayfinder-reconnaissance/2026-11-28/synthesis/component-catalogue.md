---
doc_status: draft
updated: '2026-11-28'
---

# Component catalogue

Synthesis S-B. The full table is [component-catalogue.csv](component-catalogue.csv), 47 rows. This page says how to read it and what it shows. The recorded side comes from workstream A1 (`evidence/A1/component-catalogue.csv`, 40 rows, document-claim). The observed side comes from B1, B2, B3, D1, D2 and F.

## How each row is built

| Column | Content | View |
|---|---|---|
| owner_repository, responsibility_recorded | What the records say | recorded-intent |
| public_interface, consumers | What was found at the stated revision | observed |
| revision_kinds_observed | head, core-pin, released, or "not observed" | observed |
| basis | executed, static-derived, history-derived, or document-claim only | evidence kind |

A row whose basis is "document-claim only" was read from documents and never observed. That is a statement about coverage, or about a component that no longer exists or does not exist yet. It is not a deficiency.

## Counts

| Group | Rows | Ids |
|---|---|---|
| Observed by execution at least once | 26 | K01, K03 to K08, K10, K12, K13, K15, K16, K18 to K25, K27 to K29, K34, K35, K38 |
| Observed by static or history evidence only | 12 | K02, K09, K11, K14, K17, K26, K30 to K32, K36, K39, K41 |
| Read from documents only | 8 | K33, K37, K40, K42 to K46 |
| Not readable | 1 | K47 (`spec-kitty-go`, not attached; coverage limit) |

For K08 the executed part is the launcher's refusal; the launcher's intended behaviour is an approved plan. For K41 the static part is a census of one repository that found no contract reference.

Seven rows are not in A1's catalogue. They were found by observation in supplementary repositories or as seams in code: K13 status produce seam, K30 spec-kitty-mcp, K31 spec-kitty-container, K32 fleet-kitty, K33 event-router, K39 as a separate row, K47.

## What the catalogue shows

Each statement is labelled with its view.

1. **Three recorded decompositions of core.** (recorded-intent) The records describe core as eight landscape containers plus four layer packages, as four bounded modules plus an Op tier, and as the six-package enforced chain. Three of five architecture pages say the enforced chain wins on conflict; two carry no such statement (F-A1-030).

2. **Recorded names and observed units do not line up below the package level.** (observed, static-derived, head) Of 74 observed components, 51 have no counterpart in the documented relationship table below `specify_cli`. Of 72 documented relationship rows, 14 resolve to a pair of observed components and 50 name repositories, packages, services, wheels, packs or contracts (F-B3-007). One documented name, Mission Management, has no package mapping in the records read.

3. **Size is concentrated.** (observed, static-derived, head) `specify_cli` holds 77.6% of core's 524,936 source lines (F-B1-013). In the charter repository the module `packs` holds 61.5% of 124,725 Java main lines (F-B2-001).

4. **Several capabilities have more than one implementation at head.** (observed)

| Capability | Implementations | Evidence |
|---|---|---|
| Pack reading and validation | charter Java service; core Python offering; open-packs Python mirror; doc-kitty TypeScript reader | F-D2-016, static-derived and document-claim |
| Mission-status projection | Python reference in core's tests; Java read service. Both met the same goldens here | F-D2-014, executed |
| Status write rules and lane machine | core Python (runs at head); events Python `validate_transition`; Java write service | F-D1-024, F-D2-015, static-derived; agreement of the Java side not run |
| Pack artifact schemas | core YAML; charter JSON. 1 of 8 pairs match by property names | F-B2-031, static-derived |
| Mission type descriptors inside core | `src/specify_cli/missions/<type>/mission.yaml` and the pinned pack, byte-identical | F-H06b-009, claim read; artefact not opened |

5. **Components named by records with no code found.** (observed) event-router states "bootstrap" and holds no code (F-F-019). The charter seam launcher exists as a policy entry that refuses to launch (F-D2-017). Both match what the records say about their stage (F-D2-020, F-D2-022), so they are staged work, not gaps against intent.

6. **Components that code holds and core's records do not name.** (observed) fleet-kitty calls itself active and has its own dispatch, heartbeats and workers; no core document names it, while core says the SkyKitty fleet is switched off (F-F-019). Whether the two are the same thing is not recorded.

7. **Owner statements that conflict.** (recorded-intent) Charter activation has three recorded authority statements (F-A1-012, F-A1-013; interpretation F-A1-038). Pack logic is assigned to the charter repository by a ruling recorded only in open-packs (F-A1-027). doc-kitty's ADR calls the mission-status contract "core's", and the events records assign it to `spec-kitty-events` (F-A1-025). The glossary of charter terms is claimed by both core and the charter repository (F-A1-022).

## Terms

The same things carry different names across repositories. `status.events.jsonl` is the "status event log" in core, the "Status diary" in events and the "event ledger" in the charter repository (F-A2-006). The catalogue uses core's term. "Harness", "tool" and "agent" name one concept three ways in core code (F-A2-003); the catalogue says "agent tool". "Projection" has at least five unrelated senses in core and no glossary entry (F-A2-004); where this report uses it, it means the mission-status projection served by the read service.

## Limits

- A1 did not read the tracker repository's records, GitHub issues, or the supplementary repositories beyond one README.
- Events Java was never built. Rows K17, K19 and K20 at head are static.
- Consumer lists are what was found in 16 repositories. Consumers outside them are unknown.
- fleet-kitty was read at README and search level only.
