---
doc_status: draft
updated: '2026-11-28'
---

# Pre-registration

This file fixes what will be measured, on which revisions, against which thresholds, before any measurement is taken for the record. It is submitted to the human architect for approval. After approval its commit SHA is recorded in every finding, and any departure from it is filed as a deviation (section 12).

Nothing here is a finding. The hypotheses H01 to H08 and the scenarios AS-01 to AS-12 come from the design brief of 2026-11-28 and are treated as hypotheses and proposals.

## 1. Revision model

Every finding names a revision and its kind.

| Kind | Meaning | Used for |
|---|---|---|
| `head` | `origin/main` of a repository on 2026-11-28 | The development architecture of that repository |
| `core-pin` | The revision of another repository that core at `head` composes | What core actually integrates |
| `released` | A published artefact (PyPI wheel, service release asset) | The architecture of the supported distribution |
| `historical` | A fixed earlier revision of core (section 2) | Evolution measures |

Head revisions:

| Repository | `head` |
|---|---|
| `spec-kitty` (core) | `5c4fc5a79de1c1c299ab221ca26e5555c68ef533` |
| `spec-kitty-charter` | `06cdfbe94856e8d24eca350c63d2a7b47bb9f13a` |
| `spec-kitty-events` | `646e330b896b96d7a11f53b34aa3d0c0baa69a05` |
| `spec-kitty-open-packs` | `f9a557510dc7ff04597a0b8aba87f736e25f785e` |
| `doc-kitty` | `1acc49fbe209436d3c1666a86e8b3960ee19e5ac` |

Integration pins read from core at `head`:

| Surface | File in core | Pinned to |
|---|---|---|
| Built-in pack | `packs/built-in.source.yaml` | open-packs `a79c36318b7a506ca2ab26d74705c5e3e406004f`, `requires_core >=4.0.0rc7,<5` |
| Internal pack | `packs/internal.source.yaml` | open-packs `ecda7b00c789006bedcec4e2a8aadf75aa5b03f8` |
| Events read service | `pins/read-service.source.yaml` | events tag `service-v0.1.0-rc.1`, commit `2f5e03948b5262185d15e45019fe14fbc473b9b5` |
| Events Python package | `pyproject.toml`, `uv.lock` | range `>=11.3.0,<12`, locked `11.3.0` |
| Tracker Python package | `pyproject.toml`, `uv.lock` | range `>=0.5.2,<0.6`, locked `0.5.2` |
| Services companion wheel | `pyproject.toml` | `spec-kitty-services==4.0.0rc9` (workspace member) |

Released artefacts known so far: `spec-kitty-cli` 3.2.7 (stable) and 4.0.0rc8 (pre-release) on PyPI; core `head` is 4.0.0rc9, not published. The complete pin and lock surface, including the reverse pins held by `spec-kitty-open-packs` and the charter repository, is the first deliverable of workstream D and is recorded before other workstreams cite a `core-pin` or `released` revision.

Environment recorded with every executed evidence item: tool name and version, Python or JDK version, the command, its exit code, and the SHA-256 of the raw output file.

## 2. Measurement points and windows

### 2.1 Fixed historical revisions of core

Chosen from tags and landmark commits, before normalised measurement.

| Point | Revision | Date | Why this point |
|---|---|---|---|
| P0 | `5a66b2a20a` (v0.11.0) | 2026-01-16 | Before the events dependency, the reducer, the `next` loop and the doctrine stack were added |
| P1 | `40e5209a57` (v3.2.0) | 2026-06-16 | Start of the 3.2.x point-release line |
| P2 | tag `v3.2.5` | 2026-07-08 | Inside the 3.2.x line |
| P3a | `614c52cb38` | 2026-09-04 | Last commit of the public line before the convergence |
| P3b | `f57b06dd87` | 2026-09-05 | Last commit of the EXPERIMENTAL line before the convergence |
| P4 | `d4c5af7d8f` (v4.0.0rc1) | 2026-09-13 | First release candidate after the convergence |
| P5 | `cc58393e0a` (v4.0.0rc5) | 2026-10-02 | Mid-series release candidate |
| P6 | `d58e78335b` | 2026-10-14 | Removal of the hosted surfaces |
| P7 | `5c4fc5a79d` | 2026-11-28 | `head` |

In addition, a monthly series is taken at the last commit of each calendar month from 2026-01 to 2026-11. For 2026-08 and 2026-09 both lines are measured.

### 2.2 The maintenance window

The window that H01 refers to is **not fixed here**. Under ruling R6 the architect supplies it, as two dates or two revisions, independently of any agent-participation figure.

To keep the window from being chosen with the outcome in view:

- the full series of section 2.1 is computed regardless of the window;
- the architect's window is recorded in this folder before any series is disclosed to the architect;
- the H01 comparison is then read off the series at the nearest measured points on or before each boundary;
- results for every other pair of adjacent points are reported as exploratory.

### 2.3 Discontinuities

These are handled by rule, not by judgement at analysis time.

- **Convergence.** The merge `2554bd13ad` (2026-09-05) joined two lines that ran in parallel from 2026-08-19. It is a structural discontinuity. No trend is drawn across it. Its effect is reported on its own as the difference between P3a, P3b and the merge result.
- **Bulk commits.** A commit touching more than 500 files is excluded from per-commit measures and listed.
- **Non-code commits.** A commit touching only `docs/`, `kitty-specs/` or `.kittify/` is excluded from code measures and counted separately.
- **Issue numbers.** `#N` references belong to four trackers over time. Each reference is qualified by line and date before it is followed.
- **Extracted repositories.** The charter repository has no core history, and Events imported some core history. Cross-repository change is joined by time, issue and pull request, never by file path. Imported commits are counted once.
- **Renames.** A rename map is built first (for example `doctrine` to `charter/offering`) and applied to every historical revision.

## 3. Components

The unit of structural measurement in core Python is the component: each top-level package (`kernel`, `charter`, `glossary`, `runtime`, `mission_runtime`, `specify_cli`) and each second-level subpackage of `specify_cli` and `charter`. For the Java repositories it is the Gradle module. For doc-kitty it is the workspace package.

The intended model has two tiers, and they are never merged:

- **Enforced.** The package set in `pyproject.toml` together with the `landscape` fixture and `tests/architectural/test_layer_rules.py` in core; ArchUnit rules and the module dependency allowlist in the Java repositories.
- **Documented.** The responsibility catalogue that workstream A extracts from charters, ADRs and architecture documents. It is finished and frozen before workstream B's observed graph is released to anyone.

Where no intended model exists for a unit, the result is "no intended model", not "aligned".

## 4. Evidence kinds and views

| Evidence kind | Meaning | May support |
|---|---|---|
| `executed` | A command was run and its output kept | any view |
| `static-derived` | Computed from source at a revision without running it | observed |
| `history-derived` | Computed from version-control or tracker history | observed |
| `document-claim` | A document at a revision says something | intended, planned or proposed only |

A document's description of the implementation, including the project's own lists of known residuals, is a `document-claim`. It never supports an `observed` finding by itself.

Views: `recorded-intent`, `observed`, `approved-plan`, `proposed`. The design brief is `proposed`.

## 5. Verdicts

Workstreams report measurements and observations. They give no verdict on a hypothesis and do not receive the hypothesis text (section 11.1).

The synthesis assigns one of four verdicts per hypothesis, from the criteria in section 6 only:

- **supported**: the support criterion is met;
- **contradicted**: the contradiction criterion is met;
- **inconclusive**: neither is met, or the measures disagree;
- **not assessable**: the measurement could not be taken (blocked build, missing access, no subject). This is never read as support.

The adversarial review may overturn a verdict. Both are reported.

A verdict on deterioration says nothing about cause. Causal sub-measures are marked as such and can at most be "consistent with" or "not consistent with" an explanation.

## 6. Pre-registered measures

Seed for every random sample: `20261128`. Every count is reported with its population and sampling frame.

### H01. Local fixes eroded orthogonality

*Deterioration measures*, at every point of section 2.1:

- **M01a** Cross-component import edges per thousand lines of Python source.
- **M01b** Share of modules that sit in an import cycle of more than one module, and the size of the largest cycle relative to all modules. Reported twice: all imports, and imports executed at module load only (excluding `TYPE_CHECKING` blocks and imports inside functions).
- **M01c** Per code commit: number of components touched (median and 90th percentile), per month.
- **M01d** Share of code commits per month that touch two or more components.

*Criteria*, comparing the window's end to its start:

- contradicted: M01a and M01b (load-time variant) are both at or below the start value plus 10%, and M01d did not rise by more than 5 percentage points;
- supported: at least two of M01a, M01b, M01d rose by 25% or more (M01d: 10 points or more);
- otherwise inconclusive.

*Controls*: the same comparison for the window before and the window after; `spec-kitty-events` over the same months as a sibling series.

*Causal sub-measures* (ruling R6; reported apart from the verdict above):

- **M01e** Every code commit is classified by fixed rules into capability growth, corrective maintenance, restructuring, compatibility work, convergence activity or other. The rules use the commit prefix, the paths touched and cherry-pick trailers, and are written down before classification. A seeded sample of 50 commits is classified by hand to report the classifier's error.
- **M01f** New cross-component edges introduced per thousand changed lines, by class and by window.
- **M01g** Review intensity per window: share of sampled changes with a recorded review by someone other than the author. Sample of 40 per window; reported as not assessable for periods whose tracker is not accessible.
- Authorship by human or agent is recorded but is not a measure of supervision.

*Disclosure*: raw, un-normalised M01b counts at several of these points were seen by the coordinator during grounding.

### H02. Mission-local acceptance misses ecosystem regressions

- **M02a** Frame: commits on core `main` from 2026-09-07 to 2026-11-28 whose subject marks a fix and whose diff touches two or more components, a pin or lock file, or a contract file. Seeded sample of 30. For each: the change that introduced the defect, whether that change belonged to a Mission that passed acceptance, and how the defect was detected: an automated gate before reaching `main`, an automated run after reaching `main`, or a person.
- **M02b** Comparator: the same for a seeded sample of 30 fixes confined to one component.
- A fix whose introducing change cannot be traced stays in the denominator as "untraceable".

*Criteria*:

- contradicted: at least 70% of M02a were stopped by an automated gate before reaching `main`;
- supported: at least 50% of M02a reached `main` after passing their Mission's acceptance and were then detected by a person or a later, unrelated run; and that rate exceeds M02b's by 15 points or more;
- otherwise inconclusive. If more than a third are untraceable: not assessable.

### H03. Conceptual boundaries exceed implementation boundaries

- **M03a** Against the enforced tier: number of observed dependencies that violate it and are not recorded in a ledger, baseline or allowlist; and the number of recorded exceptions.
- **M03b** Against the documented tier: share of observed cross-component edges that correspond to a documented relationship.
- **M03c** Share of source lines in units with no intended model. Reported, not scored.
- Core Python, charter Java and events Java are reported separately.

*Criteria* (core Python decides; the Java results qualify):

- contradicted: M03a shows no unrecorded violation and fewer than 25 recorded exceptions, and M03b is 90% or more;
- supported: any unrecorded violation of the enforced tier, or more than 100 recorded exceptions, or M03b below 70%;
- otherwise inconclusive.

### H04. Extraction has not consistently achieved independence

The measure is the independence matrix **M04**: one row per capability, one column per dimension of ruling R3 (logical, contract, source, distribution, deployment). Capabilities: charter activation, charter offering, events contracts, status ledger and reducer, events read service, events write service, mission state machine, work-package state machine, packs, glossary, tracker client, doc-kitty.

Each cell is filled from two sources kept side by side:

- **Declared**: what recorded intent claims for that cell (claimed, explicitly not pursued, or silent).
- **Observed**: established, partly established, not established, or not assessable.

Tests behind the observed column, run in disposable environments only:

- **M04a** Install the released artefact alone in a clean environment and run its own packaged checks.
- **M04b** Build the repository alone from a clean clone.
- **M04c** Count consumer references that bypass the public surface (private names, internal modules, file paths into another component's tree, shared mutable files).
- **M04d** Install core against the lowest and the highest version its declared range admits and run the consumer-facing checks of that boundary.
- **M04e** Where a seam exists, check whether a second implementation or a stub can stand behind it without editing a consumer.
- **M04f** Check whether the capability runs with its consumers absent, and whether its consumers run with it absent, where recorded intent says they should.

*Criteria*, counted only over cells where recorded intent claims independence:

- contradicted: every claimed cell is observed as established, by executed evidence;
- supported: a claimed cell is observed as not established for two or more capabilities;
- one capability only: inconclusive, reported as partial;
- a blocked test makes its cell not assessable.

Cells where intent is silent or the dimension is explicitly not pursued are reported for the architect and do not count toward the verdict.

### H05. Compatibility sediment accumulated

- **M05a** Population of transitional constructs, built only from machine-readable sources: baseline, ledger and allowlist files of the architectural tests, the superseded-migrations table, strict expected-failure markers, shim and legacy-reader modules, and their equivalents in the other four repositories.
- **M05b** For each ledger: entries added and removed between 2026-09-07 and 2026-11-28.
- **M05c** Share of entries that carry a tracking reference or a retirement condition.
- **M05d** Age of entries. Reported, not scored.

*Criteria*:

- contradicted: at least 70% of ledgers are flat or shrinking, and at least 70% of entries carry a reference or retirement condition;
- supported: fewer than 40% on either measure;
- otherwise inconclusive.

### H06. Architectural knowledge is fragmented

Twenty questions, fixed here. An answering agent receives only the documentation trees, READMEs and charters of the five repositories. It answers each question and cites one source. A second agent, which has the code, checks each answer and searches for a second source that contradicts the first. The run is repeated with the agent-guidance files (`CLAUDE.md`, `AGENTS.md`) added, to show how much rests on them.

1. Which packages in core may import the charter package, and what may it import?
2. Which component orders work-package status events, and by what key?
3. What is the authoritative source of a work package's current state?
4. Which repository owns the source of the built-in pack, and how does core obtain it?
5. Who owns the event contract schemas, and how are they versioned and released?
6. Which component is authoritative for charter activation state?
7. Through which public interface does core read the charter offering?
8. Does the CLI start a long-running service? Which one, with what lifecycle?
9. What is the supported way for an external system to drive a Mission?
10. How is a Mission identified, and what may be used to look one up?
11. Which source prevails when architecture documents disagree?
12. How does a new version of the events package reach a core release?
13. What does the core wheel ship, and what is deliberately left out?
14. Which mission types exist, and where is a mission type's state machine defined?
15. Where are status events published for outside consumers, and is there a default transport?
16. What is doc-kitty's role towards the documentation of the other repositories?
17. What decides which tool and model carry out a work package, and where is that recorded?
18. How is an architectural exception recorded, approved and retired?
19. What happens to an in-flight Mission when the process is interrupted?
20. Which capabilities are planned to change owner or location, and where is the approved plan?

*Criteria* (first run):

- contradicted: 16 or more answered from one authoritative source, correct against the code, with no contradicting source found;
- supported: 10 or fewer;
- otherwise inconclusive.

*Disclosure*: the coordinator wrote the questions after reading the core `CLAUDE.md`.

### H07. Execution infrastructure is comparatively immature

Fifteen execution responsibilities, fixed here: resource identity, context preparation, workspace provisioning, dispatch, model and profile selection, lifecycle supervision, cancellation, handover, evidence collection, event publication, reconciliation after interruption, permissions, human attachment, dependency eligibility, acceptance.

- **M07a** For each: where it sits (core runtime, external tool, human operations, external coordination, another component) and its state (verified by execution, present but unverified, specified only, missing, delegated by recorded intent, out of scope by recorded intent).
- **M07b** Comparator: the same rubric applied to the same number of mission-coordination responsibilities (work-package eligibility, dependency gating, state transitions, review, acceptance, consolidation and so on), listed before classification.
- **M07c** Supplementary: a log of the accommodations this investigation needed. Marked as a single case.

*Criteria*, over responsibilities that recorded intent places inside the ecosystem:

- contradicted: the verified share for execution is within 20 points of the verified share for coordination;
- supported: it is 30 points or more below;
- otherwise inconclusive.

Responsibilities delegated or out of scope by recorded intent are excluded from the shares and reported separately. Absence of a prospective component is not counted as a defect (ruling R5).

### H08. Technology-agnostic invariants are viable

Six candidate invariants from the brief: no new cycles; no private cross-component access; no reverse dependency on core; no CLI concern inside domain logic; no state mutation or ledger access outside the owning component; independent build, install and test.

- **M08** For each invariant, two agents write a check against the same revisions. One sees only public contracts, schemas and package metadata. The other sees the implementation. The checks are run on core Python and on one Java repository.

*Criteria*:

- contradicted: for four or more invariants, the contract-only check cannot be written or gives a different result from the implementation-aware check;
- supported: for five or more, both checks can be written and agree, in both languages;
- otherwise inconclusive.

This tests whether such invariants can be expressed and checked. It is not a test of Wayfinder, which does not exist. Scenario AS-10 is assessed at the desk only and labelled so.

## 7. Pre-registered experiment

**PX-01. Can a research Mission reach its end through the documented surface?** In a disposable clone of core at `head`, create a `research` Mission and advance it with the documented commands only. Record the first step that cannot be passed, the guard that refuses, and whether any documented command produces what the guard waits for. Outcomes: completes; stalls at a guard with no documented producer; stalls for another reason; could not be run. No workaround is attempted and nothing is repaired.

## 8. Acceptance scenarios

The scenarios are proposals. Each is classified, not passed or failed.

| Scenario | Treatment |
|---|---|
| AS-01 Charter internals change without consumer change | Verifiable now, through M04c and M04e |
| AS-02 An external runner records and retrieves evidence without the CLI | Partly verifiable: reading through the read service; writing depends on a service not yet pinned |
| AS-03 A new state-machine configuration needs no unrelated change | Verifiable now, by tracing what adding a mission type touched historically |
| AS-04 A new tool adapter preserves mission semantics | Verifiable now, by tracing what adding a supported agent touched |
| AS-05 Standalone installation provides declared capabilities | Verifiable now, M04a |
| AS-06 An unauthorised dependency is rejected | Verifiable now, workstream E mutations |
| AS-07 A temporary exception stays attributable and bounded | Verifiable now, M05 |
| AS-08 An interrupted assignment stays identifiable and recoverable | Partly verifiable, for the responsibilities core holds; otherwise desk |
| AS-09 A lost projection is reconstructable | Verifiable now, by deleting derived state in a disposable copy |
| AS-10 Wayfinder unavailability does not disrupt operations | Desk only |
| AS-11 A compatible release does not force lockstep upgrades | Verifiable now, M04d |
| AS-12 Mission acceptance does not conceal ecosystem violations | Verifiable now, M02 and workstream E |

## 9. Exploratory observations

Anything observed outside sections 6 and 7 is welcome and is filed with `prereg: exploratory`. It may raise a new hypothesis. It is never counted toward a verdict in section 6 and never described as pre-registered.

## 10. Workstreams

| | Scope | Owns | Profiles (loaded) | Model |
|---|---|---|---|---|
| A | Intent: responsibilities, decisions and supersession, source authority, terminology | Component catalogue, decision timeline, the documented tier of section 3, the prospective-term map | `curator-carla`, `lexical-larry` | Opus |
| B | Structure: imports, direction, cycles, private access, shared state; Python and Java | Observed dependency model, M01a, M01b, M03 | `architect-alphonso`, `paula-patterns` | Fable |
| C | Evolution: series, change coupling, corrective chains, the convergence | M01c to M01g, M02, the convergence report | `researcher-robbie`, `debugger-debbie` | Fable |
| C′ | Blind replication of C's M01 and M02 measures | An independent result set | `analyst-annie` | Opus |
| D | Contracts and independence; the pin and lock surface; packaging | M04, the revision table, development versus distribution | `architect-alphonso`, `python-pedro` and `java-jenny` for builds | Fable |
| E | Assurance: gates, CI as an assurance surface, exceptions; controlled mutations | M05, gate inventory, mutation detection, PX-01 | `reviewer-renata` (gate runner), `debugger-debbie` (mutation author) | Fable |
| F | Execution: responsibility allocation | M07 | `analyst-annie`, `architect-alphonso` | Opus |
| G | Invariant expressibility | M08 | two agents on `architect-alphonso`, isolated | Fable and Opus |
| H06 run | The twenty questions | H06 answers and checks | `researcher-robbie` (answers), `reviewer-renata` (checks) | Opus and Fable |
| Synthesis | Deliverables 1 to 12, verdicts | The report | `synthesizer-sam`, `diagram-daisy` | Fable |
| Review | Independent challenge | The review | `reviewer-renata`, `lexical-larry`, one lens that authored nothing | Fable |

Bounds:

- A is capped at 60 findings. ADRs are indexed in full and read in depth by seeded sample; the Mission archive in `kitty-specs/` is sampled, never read whole.
- E has a budget of 24 mutations: six each of private import, reverse dependency, ownership bypass, incompatible contract. The mutation author works from the intended model only and does not see the gate inventory. Mutated copies live outside every repository and are deleted.
- No whole-suite test run. Named gate files and packaged checks only.
- A owns the decision timeline; C consumes it. B takes the intended model from the architectural tests and does not judge them; E does.

## 11. Controls

### 11.1 Dispatch

- A workstream receives its measures, scope, revisions and this file's sections 1 to 4. It does not receive the hypotheses, the brief's list of failure modes, or another workstream's output.
- Each agent loads its profile through the CLI before work and states what it applied.

### 11.2 Finding record

One YAML file per finding. The architect's proposed format, with additions marked `+`.

```yaml
finding_id: F-B-001
workstream: structural-analysis
hypotheses: []            # filled by the synthesis, not the investigator
classification: observation   # observation | interpretation | hypothesis | recommendation
view: observed            # + recorded-intent | observed | approved-plan | proposed
prereg:                   # +
  measure: M03a           #   or "exploratory"
  deviation: null
subject:
  component: charter
  repository: spec-kitty/spec-kitty
  revision: "<sha>"
  revision_kind: head     # + head | core-pin | released | historical
claim: "<specific, bounded>"
evidence:
  - id: E1
    kind: static-derived  # + executed | static-derived | history-derived | document-claim
    reference: "<artefact path>"
    method: "<reproduction command>"
    sha256: "<of the artefact>"   # +
    exit_code: 0                  # +
    environment: "<tool versions>" # +
    observed_at: "<UTC>"          # +
scope:                    # +
  covered: ""
  not_covered: ""
  population: null
  sample: null
  seed: null
interpretation: null      # null on observations
derived_from: []          # + finding ids; required on interpretations and recommendations
counterevidence: []
disconfirmation:          # + the search made for the opposite, and its result
  search: ""
  result: ""
relations: []             # + supports | contradicts | duplicates | refines, with target id
confidence: high
analyst:                  # +
  profile: ""
  model: ""
verification:             # +
  status: unverified      # unverified | reproduced | not-reproduced | refuted
  by: null
quality_attributes: []
candidate_invariants: []
open_questions: []
```

Rules:

- An interpretation or recommendation cites finding ids, never repository text. A fact it needs is filed as an observation first.
- A record with empty `counterevidence` and no logged disconfirmation search is rejected.
- A hash mismatch on reproduction voids the finding until it is re-observed.
- Raw artefacts are committed beside the findings as `.txt`, `.json`, `.csv`, `.md` and `.yaml`. No Python files are added under `docs/`; analysis scripts are stored as `.txt`.

### 11.3 Replication and reproduction

- C′ runs on a different model with a different profile, sees only the measure definitions, and its output is sealed until C has finished. A measure counts as replicated when the two results differ by 10% or less.
- The review reproduces every finding a verdict rests on, plus a seeded 20% of the rest, at least five per workstream, and reports the reproduction rate.

### 11.4 Synthesis and review

- The synthesis receives the observation records, their raw artefacts and this file. Interpretations and confidence are removed mechanically before hand-over and released only after the synthesis has drafted its own reading.
- The reviewer derives its own claim from the raw artefacts of each sampled finding before reading the investigator's claim.
- The coordinator does not paraphrase findings into prompts, does not remove duplicates or inconclusive results before review, does not repair an investigator's command while keeping its result, and does not tell the reviewer which findings matter.

### 11.5 Outside observer

The prediction packet (`02-prediction-packet.md`) is given to the outside observer before any finding. Its predictions are recorded in this folder with a timestamp before substantive findings are disclosed.

## 12. Deviations from this pre-registration

A measure that cannot be taken as written is not silently adapted. The workstream stops that measure, files a deviation record (what, why, what was done instead) and the measure's results carry the deviation in every finding. A threshold is never changed after its measurement has been seen.

## 13. Coverage limits known before the start

- Events Java: static analysis only while its Gradle build is blocked by dependency retrieval. Any executed check that becomes possible is added and marked.
- Repositories outside the five are covered only as far as [03-access-requirements.md](03-access-requirements.md) is granted.
- Trackers of the periods before 2026-09-07 are in archived repositories; review-intensity and corrective-chain measures for those periods depend on access.
- History before 2026-01 serves as baseline only.
