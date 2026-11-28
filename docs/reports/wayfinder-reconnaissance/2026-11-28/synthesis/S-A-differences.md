---
doc_status: draft
updated: '2026-11-28'
---

# S-A differences: the synthesiser's reading against the investigators'

Phase 2 of synthesis S-A. After `S-A-phase1.md` was written, the synthesiser read the 21 held-back interpretation records (`synthesis/sealed/held-back-records.csv`), the confidence fields, and the deviation, coverage and blocked sections of all 18 workstream reports. The remaining sections of the reports were not read in full; the measure values were taken from the observation records and the raw artefacts.

No investigator gave a verdict on a hypothesis, as instructed. The differences below are therefore about readings of measures.

## 1. Where the investigators' reading and mine agree

| Investigator record | Their reading | Mine (phase 1) | Kept |
|---|---|---|---|
| F-B3-013 (medium) | M03b depends mainly on granularity; the uncovered edges lie inside one package | Same; H03 supported on M03b at component granularity, with that caveat | Both |
| F-C-032 (medium), F-C2-032 (high) | Per-commit scatter cannot be separated from commit practice; line comparisons need change units | Same; stated as a limit on M01c and M01d | Both |
| F-C-033 (low), F-C2-033 (medium) | Fix-class history mixes pre-merge folds with defects that reached `main` | Same; the H02 table separates the two | Both |
| F-C2-034 (medium) | M01g measures one review channel | Same | Both |
| F-F-027 (medium) | Core records, prepares and gates; starting, supervising and stopping are outside core or nowhere | Same; given as the strongest evidence against the H07 verdict | Both |
| F-F-028 (medium) | The orchestrator API version does not signal a verb removal | Same; deviation A3.5 | Both |
| F-E1-035 (low) | Ledger growth is mostly new gates registering existing constructs | Same direction; cited as evidence against the H05 verdict, at the investigator's low confidence | Both |
| F-D2-022 (medium) | Most service gaps are staged work that the records call pending | Same; it is why H04 stays inconclusive (section 2.1) | Both |
| F-A1-038 (medium) | Recorded intent for charter activation is not single-valued | Same; the cell is marked "contested" and kept out of the H04 count | Both |

## 2. Where they differ

### 2.1 H04: are approved-plan cells "claimed"?

- **Investigators.** D2's matrix marks logical independence "not established" for three service rows, and A1's catalogue marks the corresponding cells "claimed" (F-D2-021, F-A1-029). Applied mechanically, a claimed cell is not established for two capabilities (charter offering as served; events write service), which meets the support criterion.
- **Mine.** The write-service claim ("one writer") is an approved plan whose binding the records call pending (F-A1-033, F-D2-020). Ruling R4 keeps approved plans apart from recorded intent about the present. Counted strictly, one capability has a present claim not established.
- **Kept: mine**, verdict inconclusive (partial), with the mechanical reading stated beside it in `hypothesis-assessment.md`. Reason: the pre-registration's declared column has three values and no value for "planned"; reading a pending plan as a failed claim would mix two views. The architect may rule otherwise, and the verdict then becomes supported.
- **Changed after phase 2.** Phase 1 said no cell with a present claim was observed as not established. That was wrong. D2's row for the charter offering as served, read with the charter repository's present-tense claim of canonical ownership (charter ADR-0015 in the catalogue), is such a cell. The assessment now counts one capability instead of none. The investigators were right on this point.

### 2.2 H03: is the dynamic import a recorded exception?

- **B1** (F-B1-012): the import lies outside the graph the rule is evaluated on, and the rule's docstring says so. Unrecorded violations: 0.
- **G2** (F-G2-001): one upward edge in no recorded ledger; G2 also reports that the existing gate passes while its own check reports the import.
- **Kept: both.** The verdict does not depend on it (M03b decides). It is entry A2.1 of the deviation catalogue.

### 2.3 H08: does I3 count as "a different result"?

- **G2's reading** (F-G2-015): of 12 checks, 6 needed implementation-internal facts; core I3 is among the 6 that could be written from public metadata and the documented model.
- **G1's result** for core I3 is "violations (312)", with the note that the exception ledgers were not readable.
- **Mine.** Both agents found the same imports in the same two packages and none elsewhere. I count I3 as agreeing in substance, which leaves three invariants that differ or cannot be written, one short of the contradiction criterion.
- **Kept: mine**, verdict inconclusive, with the alternative count (four, contradicted) stated. G2's own classification supports counting I3 as writable from public information.

### 2.4 H05: what does "an entry carries a reference" mean?

- **E1's measure** (F-E1-020): a reference on the entry or its attached comment; 12.5%.
- **E1's hand sample** (F-E1-025): with the ledger header counted, a retirement condition for 22 and 16 of 30.
- **Mine.** The verdict uses the measure as taken (supported). The hand sample is reported as the strongest evidence against it. No change after phase 2.

### 2.5 F-B1-026: are the lower layers below `specify_cli`?

- **B1** (medium): the two lower layers are not below `specify_cli` in the import graph; the ledgers record that state.
- **Mine.** Agreed for `runtime` (50 of 98 upward module edges at load time). Weaker for `mission_runtime` (1 of 30 at load time). Stated in `coupling-and-deterioration.md` section 5.
- **Kept: both**, with the qualification.

### 2.6 F-B1-027: is the built-in pack a load-time dependency?

- **B1** (medium): yes; 811 of 1,490 modules fail to import without the fetched tree.
- **Mine.** Not used for any verdict in phase 1. It bears on H04 (packs, source and distribution cells are "partly") and on invariant I6, where both G agents found the same build failure. Added as context in the finding map. No verdict changes.

### 2.7 F-D1-031: cell counts

- **D1** counts 15 "not established" cells among 50. Most are in cells where the catalogue is silent or the dimension is explicitly not pursued.
- **Mine.** Those cells are reported for the architect and do not count toward the verdict, per the pre-registration. No difference in the cells themselves; I adopted D1's and D2's cell values unchanged.

### 2.8 H06a against H06b on "answered"

- **H06a** (F-H06a-021): three questions have no single answering document, among them Q11.
- **H06b** (F-H06b-013): 19 answered; Q11 meets all three conditions.
- **Kept: both.** H06b's count decides the measure, as pre-registered. The verdict holds under either.

## 3. Changes made to my documents after phase 2

| Document | Change | Why |
|---|---|---|
| `hypothesis-assessment.md`, H04 | One capability counted with a present claim not established, instead of none | D2's matrix and the catalogue's source for the charter repository's claim (section 2.1) |
| `hypothesis-assessment.md`, H05 | Added the investigator's low-confidence reading F-E1-035 as evidence against | It explains the growing ledgers |
| `hypothesis-assessment.md`, H01 | Added F-C-032 and F-C2-032 as a limit on M01c and M01d | Investigators' reading matches the data |
| `coupling-and-deterioration.md` | Section 5 cites F-B1-026 with a qualification | Section 2.5 |
| Scenario AS-11 | Phase 1 "partly" kept; F-D2-013 (open-packs passes only against its pinned charter build) cited | Read in phase 2 |

No verdict changed between phase 1 and phase 2.

## 4. Confidence fields

Twenty findings carry low confidence. Those that touch a verdict or a scenario:

| Finding | Subject | Effect on my documents |
|---|---|---|
| F-C-021, F-C2-021 | Mission acceptance of introducing changes; M02a against M02b | H02's acceptance clause rests on low-confidence data; this is one reason the verdict is inconclusive and not contradicted or supported |
| F-C-015, F-C2-015 | M01f by class | Declared not usable |
| F-C-024 | Refix chains | Reported as an upper bound |
| F-E1-021 | Age of ledger entries | Reported, not scored |
| F-G1-009, F-G1-012 | I5 core and I6 charter under the contract-only constraint | Counted as "cannot be written" and "not assessable" |
| F-A1-024, F-A2-019 | Charter service scope records; outside-term mapping | Used only in the deviation catalogue, part D |

## 5. What I did not do

- I did not re-run any workstream's measurement. Two greps were run on the core checkout, whose `src/` equals `head`: `source_documented` in `src/`, and `import_module` in `glossary_hook.py`. Both agree with the findings (synthesis-run).
- I did not read A2's records in depth; terminology is outside this brief.
- I did not open any other synthesiser's files.
