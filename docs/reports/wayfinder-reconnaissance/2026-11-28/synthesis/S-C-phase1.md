---
doc_status: draft
updated: '2026-11-28'
---

# S-C phase 1: evidence-first reading

Synthesis S-C, profile `architect-alphonso`. Written before `findings/`, `workstream-reports/` and `synthesis/sealed/` were opened.

## 1. What this reading rests on

- All 393 rows of `synthesis/input/observations-index.csv`: every claim of G1, G2, A1, A2, E1, E2, E3, D1, D2, F, B1, B2, B3, H06a and H06b read in full; C, C2 and CX read in shortened form.
- Raw artefacts opened: `evidence/G1/core-head-summary.json`, `core-head-I5-summary.txt`, `core-I6-build-A-archive-copy.txt`; `evidence/G2/invariant-results.csv`; `evidence/A1/source-authority-map.csv`, `approved-plans-vs-proposals.csv`, `recorded-contradictions.csv`; `evidence/E1/governance-chain.csv`, `ledger-sample-30.csv`; `evidence/F/prospective-operations-matrix.csv`; `evidence/D1/revision-table.csv`; `evidence/H06b/checks.csv`.
- The rulings, the pre-registration, the approval record, the coordinator's notes and the design brief (PDF, 7 pages).
- The consolidated documents of S-A and S-B under `synthesis/`, as my brief allows.

**Limit on blindness.** The consolidated documents were finished after their authors' phase 2. They name a few investigator readings (for example F-B1-026, F-E1-035). I met those names before my own phase 2. I did not open the records themselves in phase 1.

**Envelope against profile.** The profile's verbs include "design" and "decide". Under the envelope I consolidate and lay out options; the architect decides. The envelope wins.

**Synthesis-run check.** `src/charter/offering/api.py` in the local checkout (`23ea4709af`, the research branch, not `head`) states in its docstring that code under `src/specify_cli/` must not import `charter.offering.api` and that the `charter.*` facades are the sanctioned importers. A grep for the module name under `src/` finds importers only inside `src/charter` (10 files). This agrees with F-D1-015 and F-B3-011.

## 2. Quality attributes, first reading

The brief proposes five groups (proposed view). What the observations say about each (observed view unless marked):

| Attribute | What was measured | First reading |
|---|---|---|
| Modularity, independent evolvability | M01, M03, M04; F-B1-001 to F-B1-020, F-B3-002, F-D1-015 | Direction between the six packages is enforced and holds (F-B1-010). Inside `specify_cli` there is no recorded model for 90.7% of its lines (F-B1-013). Doors exist but most traffic goes round them under recorded baselines (F-D1-015, F-G2-003). |
| Interoperability, integrity | F-D2-003 to F-D2-016, F-E3-005, F-E3-015 | Released services answer their contracts (F-D2-003, F-D2-004). Ten formats are defined on both sides of a boundary with no shared schema (F-D2-010). Compatibility checks pass without a baseline to compare against (F-E3-015). |
| Recoverability, observability | F-D1-026, F-F-017, F-F-011 | Lane state is rebuilt from the event log, 12 of 12 (F-D1-026). Recovery exists per holder. No holder records what an executor process was doing (F-F-017). |
| Composability, testability | F-D1-008, F-D1-014, F-G2-011, F-B1-022 | Released artefacts install alone. Core's tests cannot run against the installed wheel (F-D1-014). A source checkout does not import without a fetched pack tree (F-B1-022). |
| Deployability, authority integrity | F-D2-017, F-F-010, F-E1-004 | No service is started by core at `head`. A declared execution policy is recorded and not observable (F-F-010). Every `main` ruleset has a bypass actor (F-E1-004). |

One attribute the brief does not name stands out in the records and observations: **knowledge integrity** (is a statement about the architecture current, and does it say whether it is intent, plan or fact). F-A1-005 to F-A1-025, F-A1-018, F-A1-019, F-H06b-013.

## 3. Candidate invariants, first reading

G1 (contract-only) and G2 (implementation-aware) wrote twelve checks each. My reading of the pairs, from the claim texts and `invariant-results.csv`:

| | Core Python | Charter Java |
|---|---|---|
| I1 no new cycles | Both ran. "New" has no shared meaning: G1 substituted the previous wheel as baseline (F-G1-001); G2 used the two ledgers and found one unledgered dynamic edge (F-G2-001). | Both ran and agree: no new cycle (F-G1-002, F-G2-002). |
| I2 no private access | G1 reports 593 breaking entries from rules it derived from public statements (F-G1-003). G2 reports 0 new against the recorded baselines (F-G2-003). Opposite verdicts on the same imports. | Both find the same 6 imports (F-G1-004, F-G2-004). |
| I3 no reverse dependency | Same two packages, same direction; G1 cannot tell a recorded exception from an unrecorded one (F-G1-005); G2 finds all inside ledgers (F-G2-005). | 0 and 0 (F-G1-006, F-G2-006). |
| I4 no CLI concern in domain | 9 references in 5 modules against 8 sites in 4 files (F-G1-007, F-G2-007). Neither can judge `specify_cli`, because no record says which of its parts are domain. | 0 and 0 (F-G1-008, F-G2-008). |
| I5 state mutation by owner only | G1: check runs, gives no pass or fail (F-G1-009). G2: needs the allowlists and hand reading (F-G2-009). | Partial for both; hand reading needed (F-G1-010, F-G2-010). |
| I6 independent build, install, test | Both: build fails without the pack tree, install and smoke pass (F-G1-011, F-G2-011). | G1 lost to memory; G2 builds and passes 16,177 tests (F-G1-012, F-G2-012). |

Inference, mine: the split is not Python against Java. It is whether the **intended model and its exceptions are published where a contract-only reader can see them**. In charter the ring rules and the module table are published prose that both agents could code. In core the exceptions that make "new" and "private" decidable live in test files (F-G2-015), which the contract-only agent was told not to read. One G1 rule (R2, F-G1-003) also coded the offering door the wrong way round, because the public statement it read is ambiguous and the precise rule sits in a docstring (synthesis-run check above; F-B3-011 records three statements on that door).

The mutation run is a second, independent probe of the same invariants: reverse dependency 5 of 6 detected, private access 3 of 6, ownership bypass 3 of 5 assessable, incompatible contract 5 of 6 with none caught by a version or compatibility check (F-E3-002 to F-E3-005, F-E3-015). The undetected ones share causes: dynamic import (F-E3-008), underscore names of a package with no declared surface (F-E3-007), a library with no rule on what it may import (F-E3-010), no baseline for a contract (F-E3-013), a compile-time constant invisible to bytecode analysis (F-E3-009).

## 4. What a knowledge model would have to answer, first reading

Needs I read off the observations, before looking at the brief's design in detail:

1. **Which statement is in force.** 521 decision records; status field unreliable (26 Proposed, 4 in force by merge; F-A1-019); in-place amendment on 63% of 4.x core ADRs (F-A1-018); six ADR identifiers reused (F-A1-028); 25 recorded contradictions (`recorded-contradictions.csv`), 6 of 10 supersession chains crossing repositories (F-A1-027).
2. **Who decides across repositories.** No ecosystem-wide precedence (F-A1-003); decision authority itself recorded two ways (F-A1-005).
3. **What the components are.** Three decompositions of core (F-A1-030); 40 named components (F-A1-029); 9 units with no recorded internal structure (F-A1-031).
4. **What each word means.** 17 of 38 inventory terms have no glossary entry; 18 multi-sense terms not disambiguated; one file with three names in three repositories (F-A2-001, F-A2-005, F-A2-006).
5. **Which revision a statement is about.** Pins lag heads by 53 to 4,369 commits (F-D1-002); four consumers pin four different open-packs commits; the pinned and the head pack graphs differ in shape (F-B2-023, F-D1-023).
6. **Where an exception is, who owns it, when it ends.** 75 ledgers; owner on 2 of 30 sampled entries (F-E1-025); 13 of 19 ledger files without a baseline leaf (F-E1-023).
7. **Which rule is checked by what.** 6 of 12 sampled rules end at a step instruction with no gate (F-E1-014); 0 of 13 acceptance checks look beyond the Mission's repository (F-E1-032); one cross-repository relation (core against the charter service) has no check (F-E1-008).

Evidence against a need for a new repository: much of this already exists in machine-readable form in core (ledgers, baselines, the enforced pair, pin files with digests, an ADR index, a glossary with multi-sense entries). The gap I see is cross-repository and in keeping statements current, not an absence of artefacts.

## 5. Open decisions, first list

- Present claim or approved plan when counting H04 (hypothesis-assessment, sensitivity).
- The H01 window (provisional).
- Charter: source and distribution of the Python implementation against the brief's "complete Charter extraction"; activation authority after cutover (F-A1-013); owner of activation logic (F-A1-012).
- Events: reducer ordering (F-A1-014); the write service as sole writer (approved plan, pin pending, F-D2-020); the reverse pin of core (F-D1-012).
- Packs: compatibility with the as-is CLI ended on the packs side (F-A1-015, F-D1-021).
- Which decision process binds core (F-A1-005).
- Execution: where starting, stopping and attaching belong (F-F-001, F-F-012, F-F-024); fleet-kitty's standing (F-F-019).
- `spec-kitty-go`: cited, not attached.
- Whether findings become tracker issues (deviation D-3).

## 6. Limits

- C, C2, CX read in shortened form; I rely on S-A's tables for H01 and H02.
- I did not re-run any G check. I opened summaries and results, not every per-row CSV.
- Events Java is static only throughout.
