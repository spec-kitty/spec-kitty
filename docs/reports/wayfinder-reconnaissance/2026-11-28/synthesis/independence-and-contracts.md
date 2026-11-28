---
doc_status: draft
updated: '2026-11-28'
---

# Independence and contracts

Synthesis S-B, measure M04. This page fills the independence matrix and lists the contract surfaces. It assigns no hypothesis verdict.

Supporting tables:

- [independence-matrix.csv](independence-matrix.csv): 70 cells (14 rows by 5 dimensions), each with the declared value, my cell, the investigator's cell, finding ids and the basis.
- [contract-surfaces.csv](contract-surfaces.csv): 13 contract surfaces with versioning, pins, reverse pins and consumers.
- `evidence/D1/independence-matrix.csv` and `evidence/D2/independence-matrix.csv`: the investigators' matrices. `evidence/D1/revision-table.csv`: the 33 pin and lock surfaces.

## 1. How the cells are filled

The five dimensions are those of ruling R3: logical, contract, source, distribution, deployment. Repository separation or a separate process does not establish independence, and in-process composition does not preclude it.

| Cell value | Meaning here |
|---|---|
| established | The count shows no bypass, or an executed test passed |
| partly | The owner or interface exists and carries part of the traffic, or the test passed in one direction only |
| not established | No such interface, or the capability has no separate form on that dimension |
| not claimed | A record declines the dimension, or names it only as a future plan |
| not assessable | Blocked, or not measured. The cell says which |
| not applicable | The dimension has no meaning for the subject (a library has no process; a document is not a runtime unit) |

"Declared" comes from A1's catalogue (recorded-intent, document-claim). Where intent is silent I give the observed state and mark it "intent silent"; such cells do not count toward a verdict under the pre-registration.

M04 names twelve capabilities. Two are split because two workstreams measured two different things under one name: events contracts (Python package, Java bundles) and charter offering (Python in core, Java service). Charter activation merges D1's row with D2's "as served" row.

## 2. The matrix

| Capability | Logical | Contract | Source | Distribution | Deployment |
|---|---|---|---|---|---|
| Charter activation | partly | partly | not established (intent silent) | not claimed | not claimed at head |
| Charter offering, Python in core | partly | partly | not assessable (not measured) | not claimed | not claimed at head |
| Charter service, Java | not established at head | partly | partly | established | established as a unit |
| Events contracts, Python package | partly | partly | partly | established | not applicable |
| Events contracts, Java bundles | partly | partly | partly | established | not applicable |
| Status ledger and reducer | partly | partly | partly (intent silent) | not separate (intent silent) | in-process (intent silent) |
| Events read service | partly | partly | partly | established; build not assessable | established |
| Events write service | not established at head | partly | not assessable | partly | partly |
| Mission state machine | partly | partly | partly (intent silent) | partly | not claimed |
| Work-package state machine | partly (disputed) | partly | not established (intent silent) | not separate (intent silent) | in-process (intent silent) |
| Packs | partly | partly | partly | partly | not applicable |
| Glossary | partly | not assessable | not assessable | not separate (intent silent) | in-process (intent silent) |
| Tracker client | established | partly | partly | established | not applicable |
| doc-kitty | established | partly | established, static only | partly | not applicable |

Finding ids per cell are in the CSV. The main ones per row:

| Capability | Findings |
|---|---|
| Charter activation | F-D1-011, F-D1-015, F-B3-011, F-D2-004, F-D2-016, F-A1-012, F-A1-013 |
| Charter offering and service | F-D1-015, F-D1-021, F-B3-003, F-D2-001, F-D2-004, F-D2-006, F-D2-013, F-D2-016, F-D2-017 |
| Events contracts | F-D1-003, F-D1-008, F-D1-009, F-D1-010, F-D1-012, F-D1-013, F-D2-003, F-D2-005, F-D2-009 |
| Status ledger and reducer | F-D1-011, F-D1-016, F-D1-020, F-B3-012, F-D2-014, F-G1-009 |
| Read and write services | F-D2-002, F-D2-003, F-D2-008, F-D2-011, F-D2-012, F-D2-014, F-D2-015, F-D2-017 |
| State machines | F-D1-024, F-D1-025, F-D1-012, F-D2-015, F-E1-028 |
| Packs | F-D1-021, F-D1-022, F-D1-023, F-D1-001, F-B2-026, F-B1-027 |
| Glossary, tracker, doc-kitty | F-D1-027, F-D1-017, F-B1-024, F-D1-028, F-B2-019, F-B2-021 |

## 3. Cells where recorded intent claims independence

43 of the 70 cells have a declared claim. Their observed values:

| Observed | Cells | Which |
|---|---|---|
| established | 10 | charter service distribution and deployment; events Python distribution; events bundles distribution; read service distribution and deployment; tracker logical and distribution; doc-kitty logical and source |
| partly | 29 | see the CSV |
| not established | 2 | charter service logical; write service logical |
| not assessable | 2 | charter offering source (not measured); write service source (no consumer sends writes) |

Notes for whoever applies the pre-registered criteria to these counts:

- Both "not established" cells are claims that the records themselves tie to a cutover that has not happened. The charter service is to become the owner of offering reads in one switch (approved 2026-10-19). The write service is to become the one event writer (approved 2026-10-22), with its pin "pending". At head core's Python does both jobs (F-D2-017, executed). D2 classifies these as unsupported by design at this stage, on the basis of text in the repositories (F-D2-022). Whether a claim that is an approved plan counts as "recorded intent claims independence" at head is a reading the criteria do not settle.
- Of the 10 established cells, 7 rest on executed evidence. Tracker logical and doc-kitty source rest on static evidence only (F-D1-017, F-B2-019, F-B2-021); doc-kitty logical rests on static evidence plus a run from an isolated clone (F-D1-009). The read service build from source is not assessable (HTTP 429, a coverage limit); its established distribution cell rests on the released artefact (F-D2-003).
- Per dimension, claimed cells read established / partly / not established / not assessable: logical 2 / 8 / 2 / 0; contract 0 / 11 / 0 / 0; source 1 / 6 / 0 / 2; distribution 5 / 3 / 0 / 0; deployment 2 / 1 / 0 / 0. On the contract dimension no claimed cell is established.

## 4. What sits behind the "partly" cells

Four patterns account for most of them. Each is observed; none is a cause.

**A door exists and most traffic goes around it.** `charter.activation.api`: 39 of 101 consumer files use it and 80 import behind it (F-D1-015). `specify_cli.status`: 43 of 245 module pairs name a submodule (F-B3-012). Status files: 10 of 20 sampled files outside the owner do file I/O on them (F-D1-011). The counter-cases are `mission_runtime` (213 of 213 importers use the root) and the tracker boundary (0 bypass files) (F-B3-012, F-D1-017).

**A responsibility has more than one implementation, tied by a pin to an old revision.** The lane machine exists in core, in the events Python package and in the Java write service; the mirrors are checked against core commit `512567ee`, 4,369 commits behind head (F-D1-012, F-D2-015). Pack validation exists in four places (F-D2-016). The mission-status projection exists twice and agreed byte for byte here (F-D2-014, executed), which is the one case where agreement was measured at the released revision.

**A contract is published, and its input side is not.** The read service serves a contract with goldens. What it reads is core's on-disk layout: 10 items with no machine-readable schema (F-D2-008). The released bundles cite core source files as the origin of their properties (F-D2-009).

**Version tolerance was exercised at one point only.** Core's ranges for events and tracker each admit exactly one published version, equal to the lock (F-D1-003). Lowest and highest coincide, so scenario AS-11 was run at a single combination, which passed (F-D1-013). Outside the release line: an unreleased events build passes 12 of 13 seam files (F-D1-030, exploratory); read service rc.2 meets rc.1's fixtures (F-D2-011); open-packs head fails against charter service rc.1 and passes against rc.3 (F-D2-013).

## 5. Seams tested for a second implementation (M04e)

| Seam | Test | Result | Finding |
|---|---|---|---|
| Status produce seam | A stub handler registered from outside | 2 of 2 events received, 0 consumer files edited | F-D1-016, executed |
| Packs resolution | A second tree through `SPEC_KITTY_PACKS_ROOT` | Accepted, 0 consumer files edited | F-D1-018, executed |
| Read service | rc.2 binary in place of rc.1 | 53 of 53 requests pass | F-D2-011, executed |
| Write service launcher | Released rc.2 behind core's launcher in a rehearsal | Starts, handshake and health pass; no write is sent | F-D2-012, executed |
| `charter.offering.api` | none tried | not assessed | F-D1-015 |
| Tracker adapter | none tried | not assessed | F-D1-017 |

Scenario AS-01 (charter internals change without consumer change) therefore has no executed evidence. The static evidence is that the seam exports concrete classes and no abstract type, and that 11 files import behind the facades.

## 6. Absence tests (M04f)

Three of three ran and passed: the CLI without the optional services wheel; packs resolution offline from the cache and from the wheel; status read from files with no service (F-D1-020). A status write in a disposable project spawned only git processes (F-D2-017). No consumer was found that requires a Java service in-process; open-packs requires the charter service as a separate process (F-D2-018).

## 7. Contract surfaces

| Surface | Owner | Versioning | Core's pin | Reverse pin or coupling | Other consumers |
|---|---|---|---|---|---|
| `spec_kitty_events` | events | SemVer, PyPI | range admits one version; lock | events pins a core commit for CI oracles | 6 of 9 supplementary repositories |
| `spec_kitty_tracker` | tracker | SemVer, PyPI | range admits one version; lock | none | none found |
| mission-status contract | events | `service-v*`; version string reads SNAPSHOT | tag, commit, 8 digests; CI only | bundle cites 38 core files | doc-kitty, as an approved plan |
| mission-write contract | events | `service-v*` | none at head | bundle cites 5 core files; launch text in both repositories | none |
| charter service contract | charter | `contract-charter-v*`, separate from the service line | none | charter pins an open-packs commit and a core commit | open-packs |
| packs contract | charter | `contract-packs-v*` | none; core has its own 8 schemas | none | doc-kitty, open-packs |
| `charter.offering.api`, `charter.activation.api` | core | none, in-tree | not applicable | records disagree on who may import the first | core only |
| status produce seam | core | none | not applicable | none | none registered |
| status files on disk | core | none found | not applicable | defined in three code bases | Java read and write services |
| orchestrator-api | core | `CONTRACT_VERSION` 1.31.0 with a history ledger | not applicable | none | spec-kitty-orchestrator, spec-kitty-mcp |
| pack trees | open-packs | per-pack version; commit pins | commit and tree digest | open-packs records its seed commit of core | charter, doc-kitty |
| doc-toolkit | doc-kitty | SemVer tags | git commit | none | three other sites, three versions |

Observations on versioning (all observed, evidence kind in the CSV):

- Three version lines exist in the charter repository (service, charter contract, packs contract) and two in events (`v*`, `service-v*`) (F-D2-006, F-D2-005).
- The released events bundles carry `1.0.0-SNAPSHOT`; the charter service rc.3 reports `0.2.0-SNAPSHOT` while its contract reads `0.2.0-rc.3` (F-D2-005, F-D2-019). D2 found no recorded statement on whether this is intended (F-D2-022).
- The orchestrator API removed a verb inside version 1.6.0 with no ledger entry; two consumers gate on a minimum version and still name the verb (F-F-007, F-F-008; interpretation F-F-028).
- In both repositories with an OpenAPI contract the breaking-change check ran with no baseline to compare against (F-E3-015, exploratory; claim read, artefact not opened).
- `requires_core` on the pack pin is checked when the pin is bumped, not at run time (F-D1-023).

Existing external consumers of a published contract, in total: open-packs and doc-kitty for the charter-side contracts; spec-kitty-orchestrator and spec-kitty-mcp for the orchestrator API; six supplementary repositories for the events Python package. None of nine supplementary repositories references a Java service contract (F-D2-007).

## 8. Disagreements kept

| Subject | One reading | Other reading | Kept |
|---|---|---|---|
| Charter activation, logical | D1: established (1 outside literal, no I/O) | D2: not established for the served form; A1: three authority statements | "partly"; both shown |
| Work-package state machine, logical | D1: not established (two definitions in two repositories) | S-B: partly (one named origin; declared, tested mirrors) | "partly (disputed)" |
| Not-pursued dimensions | D1: "not established" | Brief for this synthesis: "not claimed" | "not claimed"; D1's observed value is in the CSV |
| Layer-rule dynamic import | B1: recorded by the rule's docstring | G2: the one row in no ledger | both, see [dependency-models.md](dependency-models.md) |

## 9. Limits

- Events Java was never built. Every events cell at head is static; the executed cells rest on released binaries.
- No stub was tried behind `charter.offering.api` or the tracker adapter. The glossary had no seam census.
- Charter activation as served rests on one probe of one binary.
- The hosted deployment of the charter service, Windows and macOS binaries, build attestation and a registry install of the doc-toolkit were not exercised.
- D1 states that its "by design" classifications rest on text in the repository at head and were not traced to an ADR decision.
