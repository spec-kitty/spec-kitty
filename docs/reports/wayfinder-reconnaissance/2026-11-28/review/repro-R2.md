---
doc_status: draft
updated: '2026-11-28'
---

# Reproduction review R2: workstreams B1, B2, B3, D1, D2

Reviewer R2, profile `python-pedro`. The profile is an implementer profile (write code, run the full quality gate). The envelope forbids both; the envelope won. Charter context for the `review` action was loaded.

Per finding the order was: card, raw artefacts and SHA-256, own claim written to `logs-R2/own-claims-before-findings.txt`, then the finding record. The table is `repro-R2-results.csv`; raw output is in `logs-R2/`.

## 1. Reproduction rate

Sample: 48 findings (21 decisive, 27 seeded). All 157 evidence references on the 48 cards were checked: 148 point to artefacts and all 148 SHA-256 values match; 9 are document references into repositories. All 264 manifest rows of the five workstreams match their files.

| Outcome | All (48) | Decisive (21) | Seeded (27) |
|---|---|---|---|
| reproduced | 41 (85.4%) | 19 (90.5%) | 22 (81.5%) |
| reproduced with difference | 6 (12.5%) | 2 (9.5%) | 4 (14.8%) |
| claim wider than evidence | 1 (2.1%) | 0 | 1 (3.7%) |
| not reproduced | 0 | 0 | 0 |
| mislabelled view or evidence kind | 0 | 0 | 0 |
| could not reproduce | 0 | 0 | 0 |

| Workstream | Decisive reproduced | Seeded reproduced | Other |
|---|---|---|---|
| B1 | 4 of 4 | 4 of 5 | 1 seeded with difference |
| B2 | none sampled | 6 of 7 | 1 seeded with difference |
| B3 | 2 of 2 | 5 of 5 | none |
| D1 | 5 of 7 | 4 of 5 | 2 decisive and 1 seeded with difference |
| D2 | 8 of 8 | 3 of 5 | 1 seeded with difference, 1 seeded wider than evidence |

How each was checked: 17 of 48 by re-running a command or an equivalent probe; 31 of 48 by my own derivation from the repository at the stated revision or by recomputation from the raw artefact. Four of the 31 rest on the investigator's logs alone (F-D1-009, F-D1-014, F-D2-001 and the jdeps part of F-B2-003); they count as reproduced from the raw artefact, not as re-executed.

The B1 and B3 results do not depend on the investigators' code. I wrote a separate AST extractor and ran it on five revisions (head, P1, the 2026-06 month end, P3a, P3b). Modules, physical lines, module edges, load-time edges, cross-component edges and strongly connected components are equal to `evidence/B1/series.csv` at every one of the five, except one cross-component edge at P1 (1,677 against 1,678).

## 2. Findings with a difference

Both values are given. None changes a number that a decisive finding carries as its measure.

**F-D1-026 (decisive, reproduced with difference).** Own re-run on the same 12 seeded Missions of 816: 12 of 12 rebuilt, 0 of 12 byte-identical, 0 lane differences in 80 work packages. Equal to the claim. Two points differ.

- The claim lists the differences as added or filled fields. In my run, 4 of 12 Missions (19 of 80 work packages) also have a key that exists in both files and changes value (`agent`, `shell_pid`, `shell_pid_created_at`). Example: `agent` is `claude::python-pedro` in the committed file and `claude::reviewer-renata` in the rebuilt one. Log: `d1-026-difference-kinds-own.txt`.
- The disconfirmation says the Mission on which `agent status validate` reports drift is "outside the sample". It is `mission-base-window-bound-01M78XB4`, which is row 7 of the sample. My run of `validate` on the committed file names WP03, WP04 and WP05, not WP05 alone.

**F-D1-024 (decisive, reproduced with difference).** The literal `software-dev` in 80 of 1,490 Python files: equal. "research or documentation": 41 in the claim, 45 by my quoted-literal match. The claim places mission types in the built-in pack only; at head core also holds four `mission.yaml` files under `src/specify_cli/missions/`.

**F-B1-025 (seeded).** Claim: eight entries in the scratch home after five commands. Mine: six entries after two commands (`.agents`, `.claude`, `.kilocode`, `.kittify`, `.qwen`, `.spec-kitty-cold-install`); no `.cursor`, no `.local`. `--version` alone wrote nothing; `agent profile list` wrote all six and exited 1 outside a repository.

**F-B2-034 (seeded, interpretation).** It says cross-module reach is bounded by rules "that run in one module's test task". Its own sources say two modules for the charter repository (F-B2-005) and four for events (F-B2-011).

**F-D1-011 (seeded).** Status-file literals outside `specify_cli/status/`: 65 files with the investigator's anchored pattern, 71 with an unanchored match of `status.json`. The seeded samples are the seeded draws.

**F-D2-019 (seeded).** Point (d) says "the 8 releases listed". The artefact and my own query list 7 releases; the charter repository has 8 tags.

## 3. Claim wider than evidence

**F-D2-021 (seeded, interpretation).** "7 established" of 25 cells reproduces only if four qualified cells count as established: one distribution cell reads "established for the released artefact; build from a clean clone not assessable", and three deployment cells read "established as a unit", two of them "started by a user or CI only". With qualified cells apart the tally is 3 established without qualification, 4 established with a stated limit, 12 partly, 3 not established, 3 not assessable. "Distribution is established in 4 of 5 rows" includes the cell whose build could not be tried.

## 4. Points a reader of the decisive findings needs

These are not failed reproductions. They limit what the reproduced numbers can carry.

1. **F-B1-010, the layer gate was not executed by B1; it has been executed since.** B1 declares that the pytestarch rules never ran (exit 137). D1 ran the file (80 passed, `evidence/D1/m04e-core-gates-head.txt`) and so did I, alone, in a clone at head: 80 passed, exit 0 (`b1-010-d1-015-layer-rules-run.txt`). The static zero and the executed gate now agree.
2. **F-B1-011, the unit of "recorded exception".** The same four ledgers are 48 entries, 144 module edges, 228 import statements or 330 imported names. All four numbers are in the record. Any threshold on "recorded exceptions" gives a different reading by unit.
3. **F-B3-002, the unit of M03b.** 24.7% of 656 edges at component granularity; 78.6% of 14 pairs and 91.2% of weight at top-level granularity. 465 of 656 edges lie where the documented table has no row at all. The finding reports both; F-B3-013 says the granularity decides the value. I confirm that from my own edge set.
4. **F-B3-011, which door.** "0 of 15 through `charter.offering.api`" is exact. The docstring of that module at head says `specify_cli` must not import it and names the `charter.*` facades as the sanctioned importers. The finding says so. The zero is a count, not a count of breaches.
5. **F-D1-003, M04d has one point.** One published version per range. "Lowest and highest" could not be distinguished; the finding says so.
6. **F-D2-008, scope of "no schema".** No schema for the on-disk inputs under `contracts/`: confirmed by my search. The PyPI package ships `status_transition_payload.schema.json`, and `contracts/mission-status` describes the response side. The claim is limited to `contracts/` and holds as written.
7. **H01 window, read from my own series.** M01a rises from 6.651 (2026-06 month end, raw) to 7.541 (P3a) and 7.598 (P3b): plus 13.4% and plus 14.2%. Load-time cyclic modules: 9 of 1,061, then 9 of 1,311 and 9 of 1,251. I state the values; the verdict is not mine.

## 5. Disconfirmation searches

Every one of the 48 records carries a search and a result. For the 21 decisive findings I ran a search of my own.

- Opposite found, in part: F-D1-026 (see section 2).
- Qualification found: F-D2-008 (item 6), F-B1-010 (one string-literal dynamic import `charter -> glossary` lies outside the rule graph; it is in the finding's disconfirmation and not in its count).
- Nothing found against: F-B1-001, F-B1-004, F-B1-011, F-B3-002, F-B3-011, F-D1-003, F-D1-008, F-D1-015, F-D1-021 (no pack at open-packs head is accepted by the rc8 wheel: 0 of 19), F-D1-024, F-D1-025 (no later agent addition; later mission definition files exist up to 2026-04-27, no later mission type), F-D2-003, F-D2-004, F-D2-011, F-D2-012, F-D2-013, F-D2-016, F-D2-017 (no caller of the launcher outside `cli/commands/service.py`).

## 6. Deviations the workstreams did not declare

- **D1.** The "outside the sample" statement in F-D1-026 (section 2). F-D1-025 gives committer dates without saying so.
- **D2.** The manifest command for the replay does not give the directory level of the smoke goldens. One level up the script still exits 0 and reports 21 compared and 12 unavailable, not 33 compared. The charter native run log calls its config root "the 19 pack directories"; the service needs `<root>/packs/<name>/`, and the flat layout answers 200 with 0 packs. Both reproduce once the layout is found.
- **B2.** `events-py-public-surface.json` carries `units_named_in_docs: 25` while the claim (and my count) is 21 of 44. The claim is right; the artefact field is not explained.
- **B1, B3.** None found beyond what their reports declare. The B3 exposure to the B1 aggregate and to the first 29 edge rows is declared in the rules file and in every finding.

Sampling: every seeded sample I could test is the seeded draw (B1 12 of 139; D1 20 of 65, 15 of 30, 13 of 26, and 12 of 816). The frame of 816 Missions reproduces (816 of 857 directories).

Measures asked and not delivered: none found for B1, B2, B3. D1 and D2 mark the cells they could not test (no stub behind `charter.offering.api`; events Java build). Both are declared.

## 7. What I could not check

- **Events Java build.** One capped attempt: `BUILD FAILED`, HTTP 429 from Maven Central (`d2-002-events-gradle-single-attempt.txt`). Coverage limit. Events Java stays static only.
- **Charter Gradle build and jdeps.** Not re-run (3 to 15 minutes per task on a shared host). F-D2-001 and the jdeps half of F-B2-003 rest on the investigators' logs; my import scan gives the same 37 edges and no cycle.
- **Head wheel and the 3.2.7 pack-validation runs** of F-D1-021, the head-wheel smoke of F-D1-008, the no-services-wheel case of F-D1-020: read from artefacts.
- **Hand judgements** (the 12 shared-path sites of F-B1-016, the 48 file classifications of F-D1-011, the row statuses of F-B3-007): tallies recomputed, judgements not re-made.
- **Build attestation**: the attestation host is unreachable from here, as D2 reports.
- **Other platforms and the jars** of the native binaries: digests only.

## 8. My own deviations

- For core I used the interpreter of the existing synced environment with a `--shared` clone at head, not a fresh environment. `src/`, `tests/`, `pyproject.toml`, `packs/` and `pins/` at the checked-out branch are identical to head (empty diff). Bytecode writing was off; nothing outside `review/` changed in `/home/user`.
- The header of `b1-010-d1-015-layer-rules-run.txt` prints `-n0`; the run used `-p no:xdist`.
- A background JVM check and one Gradle attempt overlapped (parallelism 2, heaps capped at 1 GB).
- Two commands failed as first written and were corrected; both attempts are in the logs (`b2-021-029-own.txt`, `d2-004-charter-rc3-native-own.txt`).
- One exploratory observation of my own, a single case: for `mission-base-window-bound-01M78XB4`, `materialize` over the existing committed `status.json` gives a file without `implementer_of_record`, while delete-then-materialize keeps it (`d1-026-difference-kinds-own.txt`). Not generalised.
