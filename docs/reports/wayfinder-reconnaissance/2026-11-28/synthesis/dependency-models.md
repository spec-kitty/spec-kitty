---
doc_status: draft
updated: '2026-11-28'
---

# Dependency models: intended and observed

Synthesis S-B. The intended model is recorded-intent (document-claim, workstream A1). The observed model is static-derived or executed (B1, B2, B3, D1, D2). They are shown side by side and never merged.

Edge lists:

- [dependency-edges.csv](dependency-edges.csv): 49 rows, intended relation beside observed state, with the evidence file for each.
- `evidence/B1/component-edges-head.csv` (656 component edges), `evidence/B1/layer-edges-head.csv` (14 package edges), `evidence/B3/edge-classification-full.csv` (the same 656 edges with their category).
- `evidence/B2/charter-jdeps-module-edges.csv`, `events-static-main-module-edges.csv`, `openpacks-head-packs-edges.csv`, `xrepo-pin-matrix.csv`.
- `evidence/D1/revision-table.csv` (33 pin and lock surfaces), `evidence/A1/documented-relationships.csv` (72 recorded relationships).

## 1. The intended model has two tiers

| Tier | Content | Source |
|---|---|---|
| Enforced | `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`; two shrink-only ledgers that list which `specify_cli` subpackages `runtime` and `mission_runtime` may import; two rules inside `specify_cli` (consolidation, `ref_advance`) | F-A1-031, F-B1-010, F-B1-011 |
| Documented | 72 relationships: 26 must-not-depend, 17 consumes-contract, 12 may-depend, 12 pins, 2 ships, 2 must-not-ship, 1 oracle-parity. 23 are recorded as enforced by a named test, 49 are documented only | F-A1-031 |

Nine units have no recorded internal structure or only a partial one, among them `kernel`, `glossary`, `runtime`, the orchestrator API and the `specify_cli` subpackages beyond four bounded modules (F-A1-031). For those the result is "no intended model", not "aligned".

## 2. Core Python at head

### 2.1 Between the six packages

| From | To | Intended | Observed module edges (all / load time) |
|---|---|---|---|
| kernel | any | forbidden | 0 |
| charter | kernel | allowed | 124 / 122 |
| charter | glossary, runtime, mission_runtime, specify_cli | forbidden | 0 static; 1 string-literal dynamic import into glossary |
| glossary | charter, kernel | allowed | 3 / 1 and 9 / 9 |
| runtime | kernel, charter | allowed by the chain | 26 / 25 and 20 / 11 |
| runtime | mission_runtime | no record | 13 / 11 |
| runtime | specify_cli | forbidden except ledger | 98 / 50 |
| mission_runtime | kernel | allowed by the chain | 8 / 8 |
| mission_runtime | specify_cli | forbidden except ledger | 30 / 1 |
| specify_cli | kernel, charter, mission_runtime, runtime, glossary | allowed | 595, 424, 200, 40, 15 |

Source: `layer-edges-head.csv`, F-B1-009. Static-derived.

What the comparison shows:

- **No unrecorded violation of the enforced tier.** (observed) 0 of 8,332 module edges break a stated rule, by B1's static check and by the gate's own collector functions executed in a clone (F-B1-010). The pytestarch rule assertions themselves did not run for B1 or G1 (memory limit). E3 reports the layer-rule file passing with 80 tests when run alone (F-E3-007, claim read). D1 reports the same (F-D1-027).
- **Recorded exceptions: 48 ledger entries.** (observed) They stand for 228 upward import statements from `runtime` and `mission_runtime` into `specify_cli`. Both ledgers sit exactly at their cap. No entry is stale (F-B1-011).
- **One import outside the rule's reach.** (observed) `charter.offering` loads `glossary.attachment` through a string literal. The rule covers the static graph and its docstring says this import is outside it (F-B1-012). G2 counts it as the one upward row in no ledger and as a `charter`/`glossary` cycle (F-G2-001). B1 counts it as recorded by the docstring. Both are reported; which reading applies is a matter of what "recorded" means for measure M03a.
- **The two lower layers are not below `specify_cli` in the import graph.** (interpretation, F-B1-026, which I adopt) 19 of 36 `runtime` files and 6 of 16 `mission_runtime` files import `specify_cli` (F-D1-027). 29 of 30 `mission_runtime` edges and 48 of 98 `runtime` edges into `specify_cli` exist only inside functions or type-checking blocks. The order holds at load time for `mission_runtime` and half holds for `runtime`. The ledgers record this state.

### 2.2 Below the six packages

| Measure | Value | Finding |
|---|---|---|
| Components and component edges | 74 and 656 (466 at load time) | F-B1-006 |
| Components in a cycle, all imports | 62 of 74; one cycle of 60 | F-B1-007 |
| Components in a cycle, load time | 50 of 74; one cycle of 48 | F-B1-007 |
| Modules in a load-time cycle | 10 of 1,490, in 2 cycles, neither crossing a component | F-B1-004 |
| Component edges matching a documented relationship | 162 of 656 (24.7%); at top level 11 of 14 (78.6%) | F-B3-001, F-B3-002 |
| Component edges on pairs no record speaks to | 465 of 656 (70.9%) | F-B3-006 |
| Source lines in units with no stated internal model | 487,284 of 524,936 (92.8%) | F-B1-013 |
| Cross-component imported names marked private | 734 of 10,427 | F-B1-014 |
| Exception sites naming a class from another component | 1,651 of 3,770 (43.8%) | F-B1-018 |
| Modules outside the CLI adapter importing a CLI library | 59 of 1,296 | F-B1-020 |

All static-derived, head. Cautions:

- The share that matches a documented relationship depends mostly on granularity: 78.6% at six packages, 24.7% at 74 components (F-B3-009; interpretation F-B3-013, which I adopt). The records speak at package level and the import weight lies inside `specify_cli`.
- B3 saw 29 rows of the edge table before fixing its mapping rules (declared breach). The category counts depend on that mapping.

### 2.3 Named doors

| Door | Recorded rule | Observed use |
|---|---|---|
| `mission_runtime` package root | consumers import the root only | 213 of 213 importing modules (F-B3-012) |
| `specify_cli.status` package root | status internals are forbidden outside Mission Management | 202 of 245 module pairs use the root; 43 name a submodule; "internals" is not mapped (F-B3-012) |
| `charter.activation.api` | the only door from `specify_cli` | 38 of 256 module pairs; 80 of 101 files import behind it (F-B3-011, F-D1-015) |
| `charter.offering.api` | three differing records | 0 importers outside `charter`; consumers use `charter.*` facades; 11 files import `charter.offering.*` directly under a ratchet (F-B3-011, F-D1-015) |
| `spec_kitty_events`, `spec_kitty_tracker` public imports | public surface only | 125 of 127 names in a declared export list, 0 private (F-D1-010) |

B1 counts 27 core modules importing `spec_kitty_events`, B2 counts 25 files, D1 counts 29 files for events and tracker together. The differences are of unit (module records against files) and were not reconciled by any workstream.

### 2.4 Shared files

Paths under `.kittify/` and `kitty-specs/` are built in 57 of 74 components; 82 of 185 path keys are built in two or more components (F-B1-016). For the status event log, three counts exist under three definitions: 14 components build the path (B1); 65 files outside the owning package hold the literal, and 10 of 20 sampled do file I/O themselves (F-D1-011); 128 non-owner files name it and 34 also hold a write primitive (F-G1-009). B1's own check of its write label found 6 of 12 sampled sites to be writes at the path, so the write counts are upper bounds. Two separate allowlists govern writes outside the store and share no module (F-G2-014). No intended model at file level was found beyond "the event log is the sole authority".

## 3. The Java repositories and doc-kitty at head

| Repository | Intended (enforced) | Observed |
|---|---|---|
| spec-kitty-charter | 92 ArchUnit rules, a dependency allowlist on 2 modules, a no-library convention on 4 | 0 violations; 136 architecture tests passed; 44 module edges, no module cycle; 2 package cycles inside `packs`; 9 exemption lines (F-B2-003, F-B2-004, F-B2-005). 2.8% of lines in modules no rule names (F-B2-006) |
| spec-kitty-events, Java | 35 ArchUnit rules | Static only: 0 violating edges of 127 checked; 5 module edges, no cycle; 4 recorded exceptions (F-B2-009, F-B2-011). Rules not executed: the build was blocked |
| spec-kitty-events, Python | none | 204 module edges; no import-time module cycle; one unit-level cycle (F-B2-015). No structural rule (F-B2-012) |
| doc-kitty | none between packages; 3 point guards | 2 package edges, no cycle, 15 of 15 imports through the exports map (F-B2-019, F-B2-020) |
| spec-kitty-open-packs | none recorded as a rule | 41 `depends_on` edges, no cycle, none from built-in level to org level (F-B2-023) |

In both Java repositories the finer structure is held by test-time rules, not by the language's module system: no `module-info.java` exists (F-B2-007, F-B2-013; interpretation F-B2-034, adopted).

## 4. Across repositories

### 4.1 Intended

- Core consumes events and tracker as released PyPI packages by range and lock; no vendoring (core charter). A programme rule that says "exact git SHA, never PyPI" is still live in two other records (F-A1-007).
- Core pins the built-in and internal pack trees by commit, and the events read service by tag for CI only. Pins for the write service and the charter service are approved and pending (F-A1-033).
- The events services never need core to build or run; a test-only core pin is recorded (F-A1-031).
- open-packs pins a charter release; a core release is never a gate for pack work (F-A1-015).
- doc-kitty reads producers' published contracts only (F-A1-003).

### 4.2 Observed pin graph

Eleven directed pin edges among the five repositories, with two two-node cycles: core and events, charter and open-packs (F-B2-027). doc-kitty is depended on by the other four.

| Holder | Target | Mechanism | Behind target head |
|---|---|---|---|
| core | open-packs built-in | commit and tree digest | 665 commits, 25 days; not an ancestor of main |
| core | open-packs internal | commit and tree digest | 646 commits, 35 days |
| core | events read service | tag, commit, 8 asset digests | 114 commits; one release behind |
| core | events Python package | range and lock | 278 commits past the released tag |
| core | doc-kitty toolkit | git commit | 144 commits |
| open-packs | charter service | commit, tag, 2 jar digests | 178 commits |
| charter | open-packs | commit and tree digests | 344 commits |
| events | core | commit (CI oracles) | 4,369 commits |
| charter | core | commit constant in a corpus script | 5,111 commits |
| doc-kitty | charter packs contract | tag, commit, 7 file digests | 182 commits |
| doc-kitty | open-packs | commit (test corpus) | 53 commits |

Source: F-D1-001, F-D1-002, F-B2-025, F-B2-026. "Commits behind" counts commits, not behaviour change. Four consumers of open-packs trees pin four different commits, with three digest algorithms (F-D1-004).

### 4.3 Couplings that are not pins

| Coupling | Observed | Intended |
|---|---|---|
| Java services read core's project files | 10 input items, no machine-readable schema (F-D2-008) | The records name the ledger as the publication seam; no input contract for the layout was found |
| Formats defined on both sides of a service boundary | 10, among them the status event row, reducer ordering, lane rules, `meta.json`, the lock protocol (F-D2-010) | Oracle parity is recorded for the reducer only |
| Events contract bundles cite core source files | 317 and 182 citation lines (F-D2-009) | Not recorded |
| Events package mirrors core's lane machine at a pinned core commit | F-D1-012 | "Services never depend on core" (events charter); a test-only pin is recorded |
| Pack artifact schemas in core and in the charter repository | 8 kinds, 1 pair equal by property names, no pin between them (F-B2-031) | Charter repository canonical (charter ADR-0015); core's copy until cutover |
| OpenAPI building blocks in charter and events | 5 identical files, 2 same-named and different (F-B2-030) | Not recorded |
| One open-packs internal pack asset imports core `kernel.clock` | F-B2-033 | Not recorded |

### 4.4 A relation with no check

Fifteen cross-repository check relations exist in the workflows. For core against the charter service there is none: core holds no charter pin and no core workflow names the charter repository (F-E1-008). This matches the pending plan. The divergence between core's Python offering and the Java service is tracked only on the charter side (118 register entries, 111 open; F-D2-016, document-claim).

## 5. Head, core-pin and released

| Surface | Head of the other repository | What core at head composes | Released CLI |
|---|---|---|---|
| Events Python | 11.5.0, unpublished | 11.3.0, the only version the range admits (F-D1-003) | rc8: same; 3.2.7: events 6.x (F-D1-006) |
| Tracker | 0.5.2 | 0.5.2, the only version admitted | rc8: same; 3.2.7: tracker 0.4.x |
| Built-in pack | 5-file pack over six member packs, version 5.7.0 | 505-file single pack, version 1.0.0 (F-D1-023) | rc8: same commit; 3.2.7: 502 files in-tree, no pin |
| Pack validity under core's validator | 0 of 19 packs accepted | 5 of 5 accepted (F-D1-021, executed) | rc8: same result; 3.2.7: no such command |
| Read service | rc.2 released | rc.1 pinned | rc8: same pin; 3.2.7: none |
| Write service, charter service | rc.2 and rc.3 released | not pinned | not pinned |

Reading. (my inference from F-D1-021, F-D1-023, F-A1-015) The architecture at open-packs head and the one core composes have already separated: core is fixed to a pack shape that open-packs head no longer produces, and open-packs records that this is deliberate. Whether core follows is the approved cutover plan. This is a difference between development heads and the supported distribution, not a defect in either.

## 6. Development architecture and supported distribution

| Aspect | Source checkout | Installed wheel |
|---|---|---|
| Built-in pack | Must be fetched first; without it 811 of 1,490 modules fail to import (F-B1-022, F-D1-007) | Shipped inside the wheel; no fetch (F-D1-007) |
| Build | The build hook fetches from open-packs or needs a warm cache (F-B1-021); a non-git source copy fails (F-G1-011, F-G2-011) | Not applicable |
| Dependency versions | Exact, hashed, from `uv.lock` | Resolved from ranges; the lock is not shipped (F-D1-005) |
| Internal pack | Fetched, loaded as an org pack | Not shipped (F-D1-005) |
| Pack integrity | Verified at build, sync and pin bump | Not verified at run time; a modified tree was accepted (F-D1-019, exploratory) |
| Tests | Run against the source tree | The seam tests refuse an installed wheel (F-D1-014) |
| Service binaries | Fetched for conformance tests | None shipped; `service status` reports no pinned service (F-D1-020) |

The built-in pack is a load-time dependency of the Python package in both forms (interpretation F-B1-027); the wheel satisfies it by packaging.

## 7. Not covered

- The import graph of an installed wheel. All core graph measures are on the source tree at head.
- Events Java by execution. Dynamic imports with computed names. Run-time composition in the Java services.
- Pins in release assets, third-party action pins, npm lockfiles, and pins in the supplementary repositories (F-D1-001, F-B2-025).
