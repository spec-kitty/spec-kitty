---
doc_status: draft
updated: '2026-11-28'
---

# Assurance gaps

Synthesis S-A. What the existing gates check and do not check, the results of the controlled mutations per class, and how the sampled cross-component fixes were detected. Sources: E1, E2, E3, C, C2, CX, B1, B2, D1, G2.

All statements are in the **observed** view at `head` unless marked. "Gap" here means an area where no check was observed to fire. It is not a statement that a defect exists, and nothing here proposes a change.

## 1. What exists

| Repository | Gate rows inventoried | Required checks to land on `main` |
|---|---|---|
| spec-kitty (core) | 347 (310 architectural test files, 37 others) | 3: "Clean install verification", "router gate", "CI Modules gate" |
| spec-kitty-charter | 62 | 1: "gate" |
| spec-kitty-events | 55 | 4: "acceptance", "service-gate", "cross-repo-harness-tests", "docs-build" |
| spec-kitty-open-packs | 8 | 2: "Validate packs gate", "Charter service validation" |
| doc-kitty | 9 | 1: "ci-ok" |

Findings: F-E1-001, F-E1-004 (static and executed against live rulesets on 2026-11-28).

- Core's 310 architectural gate files are sorted by a file-name rule into: boundary 135, CI integrity 47, test hygiene 32, contract 21, docs and records 20, import direction 18, terminology 15, packaging 12, other 10 (F-E1-001).
- 39 of the 310 run on every pull request. The other 271 run in a job that is selected when a code path group or a declared scan scope changes, and nightly. All these jobs feed the required "router gate" (F-E1-002). For each of the 15 core mutation diffs, the selection script answered "the whole battery" (F-E3-017).
- 65 of the 310 read an exceptions file or a capped in-code allowlist (F-E1-003).
- In all five repositories the pull-request rule requires 0 approving reviews. Every ruleset on a `main` branch lists a bypass actor with mode "always" (F-E1-004). Not read: organisation-level rulesets, the identity of the bypass actors.

## 2. What the gates check, and where they stop

### 2.1 Structure inside core

| Area | Checked | Not checked |
|---|---|---|
| Direction between the six top-level packages | Yes; 0 unrecorded violations; 48 ledger entries for 228 upward imports (F-B1-010, F-B1-011) | Dynamic imports: the rule's docstring says so, and one such import crosses a forbidden pair (F-B1-012, F-G2-001) |
| Structure inside a top-level package | Two rules (`consolidation`, `ref_advance`) in the layer gate; door rules for charter activation, the charter offering and status in other gate files (F-B1-013, F-G2-003) | 92.8% of source lines sit in units with no stated internal model in the enforced tier as the brief defined it (F-B1-013). Other gate files were not inventoried rule by rule |
| Private names across packages | Only for `spec_kitty_events` and `spec_kitty_tracker` (F-E3-007) | Underscore names of core's own packages: 131 rows across top-level packages, no counterpart gate (F-G2-003) |
| Command-line libraries in lower layers | A console-importer ledger for `consolidation` (F-B1-011) | `rich` or `typer` imports in `charter`, `glossary`, `runtime` (F-G2-007) |
| Writers of the status event log | Two shrink-only allowlists with different mechanisms and no shared module (F-G2-014) | A write through the kernel pin writer; no gate names it (F-E3-012) |
| Type checking | Two pytest files run `mypy` for named modules; a Makefile target names 2 files | No workflow invokes `mypy`; 3 errors in `status/reducer.py` at baseline (F-E1-013, F-E3-001, F-E3-018) |

### 2.2 Across repositories

- 15 cross-repository check relations exist. 2 are required on every pull request, 5 are required only when a path group selects them, 2 run per pull request without being required, 5 run on a schedule. For core against the charter service **no check exists**: core holds no charter pin (F-E1-008).
- The checks validate against pins, not heads. Distance from pin to head on 2026-11-28: core's built-in pack pin 665 commits, internal pack pin 646, charter's open-packs pin 344, open-packs' charter pin 178, core's read-service pin 114, the core commit pinned by events 4,369, the events harness pin 599 (F-E1-009, F-D1-002; exploratory).
- The events required check "cross-repo-harness-tests" installs `spec-kitty-cli==3.2.0rc22` and a harness commit of 2026-05-21. On a pull request from a fork it is skipped, which reports as success (F-E1-010).
- The events packaged conformance suite is invoked by no workflow, Makefile target or pytest setting; 17 test files with "conformance" in the name do run per pull request (F-E1-012). The agent guide that names the command is a document-claim from a secondary source.
- Core's seam tests cannot be pointed at an installed wheel; they exercise the source tree (F-D1-014).
- The built-in pack tree is digest-verified at build, sync and pin-bump time and not at CLI run time (F-D1-019; exploratory).
- 11 curated per-pull-request checks in core post a result that is not among the three required contexts, among them the packs gate, the diff-coverage gate and the shared-package drift check (F-E1-005). Whether a red non-required check blocks in practice was not sampled.
- 1,383 of 4,369 tracked test files (31.7%, an upper bound) sit in directories outside the per-change matrix and run nightly (F-E1-007).

### 2.3 Contracts

- In both repositories that hold an OpenAPI contract the breaking-change check ran and passed without comparing anything, because no baseline exists: charter printed "No released baseline"; events printed `NO_BASELINE_INITIAL_VERSION` (F-E3-013, F-E3-015; exploratory but executed).
- Of 6 incompatible-contract mutations, none was detected by a compatibility or version check. The 5 detections came from behaviour tests, example validation and content-drift checks (F-E3-005, F-E3-015).
- `contracts/tools/example_check.py` in events detected one mutation and is invoked by no workflow, Makefile target, Gradle file, script or test (F-E3-014).
- The orchestrator API removed a verb inside version 1.6.0 with no entry in its version ledger; two consumers that gate on a minimum version still name the removed verb (F-F-007, F-F-008).

### 2.4 From rule to gate

Of 12 rules sampled by seed (6 from the charter's architecture sections, 6 directives bound for review): 4 chains reach a recorded exception path, 1 ends at a gate with no exception path, 6 end at the step instruction with no gate, 1 grants a permission. The charter context for an action lists all 50 directives by id; none of the 6 sampled architecture rule texts occurs in it (F-E1-014, F-E1-015). The other 77 rules of the two frames were not traced.

### 2.5 Acceptance at Mission level

- The accept path runs 13 checks. All read the Mission's own artefacts, its status events, or the tree and remote of the same repository. 0 of 13 read another repository, a pin file, a lockfile, another component's contract or an architectural gate result (F-E1-032).
- The mission review command runs four gates and states in its source that it runs no Python tests. The accept and review prompts name no other repository, pin, lockfile, contract bundle or architectural gate (F-E1-033).
- A research Mission cannot pass its third step with documented commands (PX-01; F-E1-028 to F-E1-030).

This is a statement of scope, not of fault. No record read places ecosystem checks inside Mission acceptance (inference; absence was not searched exhaustively).

## 3. Controlled mutations

Method. E2 wrote 24 patches from the intended model, blind to every test and gate. E3 froze a gate set, then applied each patch in a disposable clone. A detection counts only if the failure is attributable to the mutation.

### 3.1 Per class

| Class | Total | Assessable | Detected | By a per-change gate | Not detected | Not assessable |
|---|---|---|---|---|---|---|
| PI, private import | 6 | 6 | 3 | 3 | M-PI-3, M-PI-5, M-PI-6 | none |
| RD, reverse dependency | 6 | 6 | 5 | 5 | M-RD-4 | none |
| OB, ownership bypass | 6 | 5 | 3 | 3 | M-OB-2, M-OB-4 | M-OB-5 (events Java, build blocked) |
| IC, incompatible contract | 6 | 6 | 5 | 4 (1 by a tool no workflow runs) | M-IC-2 | Gradle side of M-IC-3 |
| All | 24 | 23 | 16 | 15 | 7 | 1 |

By subtlety: blatant 7 of 8, moderate 4 of 8, subtle 5 of 7 assessable. By repository: core 11 of 15, charter 2 of 4, events 2 of 3 assessable, open-packs 1 of 1. 15 of 16 detecting failures name the violation. Read from `evidence/E3/detection-counts.txt` and `detection.csv` (F-E3-002 to F-E3-006).

### 3.2 The seven undetected, with the author's view of the rule (E2 against E3)

| Mutation | What it does | Why no gate fired (E3) | Was the rule clear (E2) |
|---|---|---|---|
| M-PI-3 | Function-body import of an underscore function of `runtime.next._internal_runtime` | No gate restricts underscore names of core packages (F-E3-007) | Ambiguous: production code already imports that package; only the underscore convention is broken (F-E2-002) |
| M-PI-5 | `importlib.import_module` of a private charter module | The covering gate scans static import nodes and says dynamic imports are invisible (F-E3-008) | Partly ambiguous |
| M-PI-6 | Java import used only for a compile-time constant | ArchUnit reads compiled classes; the constant is inlined (F-E3-009). Checkstyle was not run | Clear |
| M-RD-4 | Events library imports `specify_cli` in a function | Nothing in events scans the library for imports of another distribution (F-E3-010) | Partly ambiguous: the rule is stated for the services, implied for the package (F-E2-006) |
| M-OB-2 | Direct rewrite of `activation.yaml` | Not in the frozen 66 files; **a per-change battery file outside the frozen set does fail and names it** (F-E3-011) | Clear |
| M-OB-4 | Resolver calls the kernel pin writer | No architectural gate names that function (F-E3-012) | Clear |
| M-IC-2 | Optional request property made required | Compatibility check has no baseline (F-E3-013) | Partly ambiguous: "without a version change" has no direct meaning on a SNAPSHOT contract (F-E2-004) |

Reading across the two workstreams (inference):

- 3 of the 7 undetected mutations violate a rule the author found clear (M-PI-6, M-OB-2, M-OB-4). M-OB-2 would be caught by per-change CI. That leaves 2 clear-rule mutations with no observed detection: one Java constant import and one pin write.
- 4 of the 7 sit on rules the author found ambiguous or partly so. For these, "undetected" may reflect an unstated rule as much as a missing gate.
- Two mutations on rules the author judged not clean were detected anyway: M-RD-3 (one more upward import beside 138) by the ledger, and M-OB-6 (append through a public primitive) by the writes gate (F-E2-003, F-E2-005, F-E3-003, F-E3-004).
- No mutation was written for the `charter context --json` payload, whose contract module calls itself a tracking contract (F-E2-007).

### 3.3 Limits on the mutation result

- The frozen set held 66 of 310 architectural files; 244 were not run, although per-change CI would run all of them. Detection in core is therefore a **lower bound**. One of the four core misses is known to be caught outside the set (F-E3-017).
- Outside the frozen set, the dead-symbol gate failed for all 4 core mutations the set missed, each time naming the uncalled new function, not the violation. 11 of 15 core patches add an uncalled function, so part of the detection a real run would show is a side effect of patch shape (F-E3-016; exploratory).
- Declared breaches: 13 core mutations were applied in one batch and attributed by the file each failure names; the three with no failure were re-run alone. Workers 4 instead of 2.
- The 4 Java patches were syntax-checked with `javac` only by their author. E2 saw file names under the charter test tree (declared).
- Mutations cover six cases per class. They are not a sample of real changes.
- Events Java: not assessable (HTTP 429). A coverage limit.

## 4. Detection routes of sampled cross-component fixes (M02)

History-derived, converged line, 2026-09-07 to 2026-11-28. Two independent samples of 30 from frames of 666 (C) and 698 (C2); they share 4 commits.

| Route | M02a, C | M02a, C2 | M02b, C | M02b, C2 |
|---|---|---|---|---|
| Automated check before the change reached `main` | 1 | 2 | 3 | 5 |
| Automated run after it reached `main` | 0 | 0 | 1 | 1 |
| A person | 22 | 16 | 8 | 8 |
| Detector not named | 7 | 11 | 18 | 16 |
| Not a defect fix | 0 | 1 | 0 | 0 |

Findings: F-C-019, F-C-020, F-C2-018, F-C2-020, F-CX-008.

- Origin replicates: in both runs 13 of 30 cross-component fixes and 21 of 30 single-component fixes corrected something introduced in the same pull request, which never reached `main`.
- Detection does not replicate at the 10% rule (a person: 22 against 16). The direction agrees: an automated check is the named detector for 1 or 2 of 30 cross-component fixes.
- In C, all 15 cross-component defects that had reached `main` were found by a person: issues, a maintainer ruling, review squads. C2 names 11 issue reports among its 16 (F-C-019, F-C2-018).
- "A person" is read from text. The text often does not say whether a reviewer was a person or an agent review squad (F-C-019).
- The "not named" rows are mostly pre-merge folds whose message names no detector. They could hide automated detections; the samples cannot tell (F-C-033, low confidence; F-C2-033).

What this shows: for the sampled fixes whose detector is named, detection after the fact by people dominates, more so for cross-component fixes. What it does not show: the rate at which gates stop defects that never become a fix commit. A gate that blocks a change before any commit leaves no trace in this frame.

## 5. Exceptions as an assurance surface

- The charter's burn-down policy says a baseline entry names an issue, an owner and a drain date. Of 24 non-zero leaves, 16 name an issue, 5 an owner, 3 a date, 2 all three (F-E1-022).
- The same policy says every mutable architectural allowlist is governed by a baseline leaf. 6 of 19 non-empty ledger files have one; the other 13 state shrink-only or generated semantics in their own header (F-E1-023).
- In a seeded sample of 30 ledger entries: rationale 30, retirement condition 22, owner 2, approval record 1, all four 0 (F-E1-025).
- No repository records who approves an allowlist entry other than through review of the pull request (F-E1-024).
- Caps moved both ways over the range: raised by 44 in total, lowered by 164 (F-E1-019).

## 6. Summary

| Gap observed | Evidence | Strength |
|---|---|---|
| Dynamic imports are invisible to the import-direction gates | F-B1-012, F-E3-008 | Executed, stated by the gates themselves |
| No gate on private names between core's own packages | F-E3-007, F-G2-003 | Executed; rule itself ambiguous (E2) |
| Contract compatibility checks compare against no baseline | F-E3-013, F-E3-015 | Executed in two repositories |
| Events library is not scanned for imports of core | F-E3-010 | Executed; rule implied only |
| No check between core and the charter service | F-E1-008 | Static |
| Cross-repository checks run against pins hundreds of commits behind head | F-E1-009, F-D1-002 | History-derived; whether those commits matter was not tested |
| Mission acceptance reads only the Mission's own repository | F-E1-032, F-E1-033 | Static |
| Half of the sampled rules end at an instruction with no gate | F-E1-014 | Sample of 12 |
| Exception entries rarely carry an owner | F-E1-022, F-E1-025 | Static, samples of 24 and 30 |

Against a reading of weak assurance: reverse dependencies were detected in 5 of 6 cases including function-body and type-only imports; ownership bypass of the status log and migration ledger was detected in 3 of 3 core cases that targeted them; 15 of 16 detections name the violation; the enforced tier shows 0 unrecorded violations; ledgers that existed in September are 24 of 27 flat or shrinking.

## Not covered

- 244 architectural gate files were not executed against the mutations.
- Checkstyle and the remaining `verifyAll` tasks in charter; every Gradle task in events.
- Review practice: whether reviewers apply ungated rules cannot be read from the repositories.
- Gates in the supplementary repositories.
