# Tracer: Approach

Mission: `mission-status-contract-1-1-01M42XJC` (#5625).

## Plan of attack (spec phase)

1. Additive contract slice only: three new operations (work-package detail, artifact listing,
   artifact content) and their schemas, version 1.1.0; v1 operations and schemas unchanged.
2. The reference reader and synthetic-repository tests live in the test tree beside the
   #5581 projector; the Mission branch is brought level with `main` before the plan.
3. `changeState` uses the repository's existing owned-files matching, unchanged, pinned by a
   parity test over every FR-022 glob case.
4. Open for the plan phase: OQ-1 and OQ-4; the rename-names seam for FR-007 rule 2.

## Plan phase (2026-10-04)

- **A-1 Plan run.** `spec-kitty plan --mission mission-status-contract-1-1-01M42XJC --json` scaffolded `plan.md`
  (`scaffold_only: true`); the plan, `research.md`, `data-model.md`, `quickstart.md` and `contracts/` were then
  written by hand from the measurements in research R-1 to R-12. The command was not re-run after the plan
  was filled, because its second call auto-commits and the orchestrator owns commits.
- **A-2 Measure before deciding.** Every decision the plan settles has a command that was run: the structure
  check on a scratch CHANGELOG (R-1), the corpus caps (R-2), both matcher copies on 19 cases (R-3), the rename
  seam on a scratch repository (R-4), the reality check once (R-5), the placement gates on a scratch repository
  with a planted module (R-6), the minor-version recipe with `--baseline-root` and the pinned `oasdiff` (R-7).
- **A-3 Shape.** One pull request. Concerns in order: a behaviour-preserving campsite commit, the tooling
  extension and the two contract slices (sequential on the shared files), the readers, the corpus extension,
  the proof module; then the wrap-up (accept, cleanup, aggregate squad, compaction, rebase onto the release
  commit, draft PR). The 1.0.0 tag is needed only from the wrap-up on (R-7).
- **A-4 Floors.** Pinned below the merged-tree measurement by one stated rule (95 percent, two significant
  figures; anomaly classes by name). Three facts the spec did not know are in the plan: 3,193 distinct work
  package ids in 3,197 files (four duplicate ids in one Mission), a public rename seam, and two registrations
  that any new corpus-marked test module needs outside the slice file set.

## Plan fix after the confirmed plan findings (2026-10-04)

- **A-5 Lanes follow the dependency graph.** Two lanes only: lane T (tool extension, then the two contract slices) and
  lane R (baseline, readers, proof modules, corpus extension). Every cross-lane dependency is a declared work package
  dependency with a named merge (M1 before the artifact reader, M2 before the detail reader). No lane runs two work
  packages at once. All registrations of new test modules are written by lane R only.
- **A-6 Front-load the corpus and the external unknown.** The artifact and detail readers each end with a thin corpus
  smoke; the release tag is requested at implement start; the JVM-only contract checks get a shake-out step before
  the aggregate squad because the Contracts workflow cannot run before the pull request.
- **A-7 Evidence is final only after the rebase.** Compaction and the rebase onto the release commit change the tree
  after the aggregate squad, so only the post-rebase evidence step is cited as final.

## Plan fix after the fresh sweep, round 2 (2026-10-04)

- **A-8 Lanes are computed from write scopes (supersedes A-5).** A-5 described two lanes (T and R) with merge points M1
  and M2 following the dependency graph. `compute_lanes` does not do that: it unions every pair of code work packages
  whose `owned_files` overlap, and a dependency only becomes an edge between lanes. Run on the planned write scopes
  (explicit files, no directory globs) it gives, under OD-1 X, one lane for IC-02 alone, one lane for IC-01, IC-03 to
  IC-08, and `lane-planning` for IC-09 (which needs `execution_mode: planning_artifact` set explicitly). The tooling
  merges the approved tip of a dependency lane into the dependent lane's worktree, so the plan has no manual merge point.
  Under OD-1 Y the plan's own dependencies make the lane graph cyclic unless IC-05 depends on IC-04 only. The one real
  parallel window is IC-01 beside IC-02. Tasks finalisation prints the real manifest and the orchestrator compares it.
- **A-9 Records have one writer.** No code work package writes under `kitty-specs/`. What a work package must record
  (contract-note refinements, the D-P3 fallback, the IC-01 baseline, friction) is reported in its hand-off; the
  orchestrator appends it add-only between dispatches, and IC-09 appends the close-out assessment.
- **A-10 Scope is proven on the real diff.** The scope function is run over `git diff --name-only` of the branch against
  its merge base, with the add-only check of the Mission directory, at W-1 and W-7 (quickstart); planted lists alone
  prove the function, not the branch.
- **A-11 Tracker duties have an owner.** The claim and assignment at D-0, the issue-matrix verdicts (set before the first approval; W-1 only moves `#5625` to a terminal verdict) and the closing
  comment after the draft PR belong to the orchestrator (or the operator), not to a work package.

## Round 3 plan fixes (fresh sweep)

- **A-12 Correction to the evidence range.** The evidence ledger runs R-1 to R-15, not R-1 to R-12 as A-1 states; R-13 to
  R-15 were added at the plan fixes. A-10 now reads the scope function over `git diff --name-status` (statuses matter),
  after lane consolidation (W-1 ii), from the repository root.

## Close-out evidence, pre-tag and pre-rebase (2026-10-05, WP09)

Scope of this entry. Every figure below is **pre-tag and pre-rebase**: it was taken on the lane tips before consolidation,
before history compaction and before the rebase onto the 1.0.0 release commit, and the `contract-mission-status-v1.0.0` tag
did not exist. The final evidence is wrap-up step W-7. Each figure comes from the named work package's independent review
report (a reviewer re-ran the commands) or from the J-1 replay report; nothing here is a figure I measured myself.
Every commit named was checked with `git cat-file -t` and is a commit object.

### Per work package (review reports)

- **WP01 baseline and campsite** (lane-a tip `0d8f2f710`, 2 files, +21/-14). Behaviour-preserving: the shared git-init and
  commit helper argv are identical to the originals. Corpus selection `corpus and not windows_ci`: reality 577 passed plus
  payloads 157 passed, 734 together, matching the plan's baseline arithmetic. Revert experiment (git-init argument spoiled):
  5 failed, 3 setup errors, restored. The implementer's baseline table was not supplied to the reviewer, so only the unit counts
  were re-checked; the CI job records were not re-verified. `ruff check` and `ruff format --check .` clean (3103 files).
- **WP02 tool extension** (base `aef7cc967`). Cycle 1 rejected at severity 3: an embedded line break in an artifact-path value
  hid a home path or address from the text pass. Cycle 2 approved after a red-first fix; seven revert experiments, all killed, and an
  eighth whose revert is masked (the structured pass catches it, severity 1). `run_negative_cases`: 127
  cases, 94 ran, 33 skipped by tag (jvm, vacuum, oasdiff; pre-existing), 0 failed. Three contract tool modules: 228 passed.
  `mypy --strict contracts/tools/*.py` clean.
- **WP03 contract slice A** (three cycles; final tip `f01849aa6`, first approval tip `9758a5cd5`). Additive only:
  `breaking_check --baseline-root` against a `git archive` of `aef7cc967`: breaking=0. Exhaustive code-point scan of the
  path predicate against the schema pattern: 0 mismatches. Cycle 3 is the snake_case rename of `ArtifactKind` after J-1 (below);
  it touched 10 files, 24 lines, kind values only. After it: `pytest tests/contract -n 4` 2,299 passed; ten contract checks exit 0
  (examples 74/74, enums 7 with 43 values); four revert experiments all killed; a planted kebab-case value gives lint exit 1.
- **WP04 contract slice B** (cycle 1 `9e43b1acc` to `18a72eacc`, rejected at severity 3; fixes `a86f9f122`, `b0ab5c12b`, approved).
  The rejection: the `ReviewCycle` pointer pattern was wider than the repository's own pointer validator, so a traversal-shaped
  pointer was schema-valid. Fixed with a differential test; the reviewer's 28 adversarial cases found the schema wider in none.
  `Workspace.planningBranch` gained a 255 character bound. Five revert experiments in cycle 1, all killed. `breaking_check`
  breaking=0. Two architectural reds in the cycle 2 run, both environmental (below).
- **WP05 artifact reader foundation** (commits from `95d532ebd`, approved first time). No `src/` diff. Registration pair present.
  Architectural battery as `ci-router.yml` runs it: fast 786 passed, 1 skipped; heavy 1/2 1,601 passed, 2 failed; heavy 2/2
  1,239 passed. Tool-job selection 1,395 passed, 37 skipped. Seven revert experiments: five killed, two survived (to be folded at
  wrap-up). Reader timing: the all-Missions examination test takes 21 s.
- **WP06 detail reader** (commits from `a49f5bb94`, last `93e66b395`, approved first time). No `src/` or `contracts/` diff.
  Battery: fast 786 passed, 1 skipped; heavy 1/2 1,601 passed, 2 failed, 2 xfailed; heavy 2/2 1,239 passed; the four
  deselected prose-job files 204 passed. Tool-job selection 1,634 passed, 37 skipped. Ten of ten reviewer revert experiments killed.
  Matcher parity: the 18-case glob table agrees across the reader and both private repository copies; exactly two documented
  divergences (a leading `./`, a backslash), both outside what git emits.
- **WP07 version, CHANGELOG, proof module** (six commits, approved first time). Proof module 119 passed in 11 s; seven reviewer
  revert experiments, all killed. Battery: fast 786; heavy 1/2 1,601 passed and 2 failed; heavy 2/2 1,239; prose-job files 204.
  Tool-job selection 1,767 passed, 37 skipped. **`--baseline-root` recipe result:** `breaking_check --baseline-root` over a
  `git archive` of `aef7cc967` with oasdiff 1.32.1 gives `baselines=1 breaking=0 provisional_changes=0`; the in-tree minor-proof
  tests use a scratch baseline built from the candidate, so this recipe is the authentic proof of the minor bump.
- **WP08 reality-check extension** (commits `6d08826ec`, `79b63757c`, `dd3d853bb`; cycle 2 fix `483ca1d65`; approved after one
  rejection at severity 3 twice over: credential-before-redaction order unpinned, and three floors loosened without need).
  **Corpus job timing:** the local run of the reality and payloads selection took 1 m 27 s wall clock (87.3 s), 776 passed at the
  review (86.5 s) and 796 passed after cycle 2 (86.9 s), against the plan's 91 s measurement for 577 tests. With the CI factor of
  about two this predicts roughly 3 minutes, under the 6 minute re-plan threshold. The refused-list mechanics hold:
  examined plus refused equals discovered (3,193 plus 9 equals 3,202). Fifteen floors are pinned in a test that rejects any new
  unpinned floor.
- **Fold-ins on lane-a** (operator decision): a linear-time email matcher (`91f3d45ae`, `10c7e1857`, `f022c1106`, follow-up
  `eb6478bb4`) and the description-only `ReviewCycle` wording fix (`23fc80819`). Rejected once at severity 4 (no test sent a
  glued pair of addresses through either redaction caller), approved on re-verification. Independent fuzzing: 0 differences in
  900,000 adversarial and 960,799 exhaustive strings; every 256 KiB input at most 0.02 s; `breaking_check` breaking=0;
  `pytest tests/contract` 2,697 passed.

### J-1 replay (contracts workflow, JVM jobs)

First replay on the WP04 tip `b0ab5c12b`: one red, class a, the vacuum `enum-case` rule refusing the kebab-case `ArtifactKind`
values (the Python gates do not run this lint). Operator ruling: rename to snake_case; WP03 reopened through a rejection
transition and approved at cycle 3. Replay on `f01849aa6`: every JVM job exit 0, lint 0 violations (was 1), `negative-tests`
with no skip tags 127 of 127, tamper plant detected, client smoke 105 files and 0 warnings, tag-less release dry run exit 0.
Two non-defects: the tamper check needs a temporary directory whose ancestors hold no `.git` (class b: a stray repository at the
system temporary root), and `breaking_check --root` without a baseline reports `NO_BASELINE_NOT_INITIAL` until the tag exists
(class c, expected, local only per plan).

### Baseline classification of the reds seen in battery runs

Two architectural reds appear in the heavy 1/2 shard of every battery run (WP04 cycle 2, WP05, WP06, WP07), always the same
two, never touching a diff that has any `src/` or architectural change: the graph regeneration byte-identity test (it shells out
to the user-level installed CLI, which crashes: a defect of the installed CLI) and the accept-stamp idempotency
test (the placement port resolves to the stray repository at the system temporary root). Both are environmental and
pre-existing; neither is introduced by this Mission. CI keeps the final word on the battery.

### Close-out assessment

**What held.**
- Additive-only design: breaking=0 against the 1.0 baseline at every approval, and no `src/` change in any work package
  (NFR-007).
- Measure before deciding (A-2): the decisions made on measurements (caps, matcher parity, rename seam, placement gates, timing)
  survived implementation; the corpus job came in at about a third of the re-plan threshold.
- One writer for records (A-9) and the single-writer chain for the two registrations (WP05, WP06, WP07): no merge conflict on
  the one physical `packs.yml` line.
- Per-work-package independent review with the reviewer's own revert experiments: it found the severity-3 and severity-4
  defects below that the implementers' tests had not pinned.

**What the plan got wrong or sharpened.**
- The kebab-case `ArtifactKind` values specified by FR-004 failed a lint the Python gates never run; only the J-1 replay (placed
  before WP05 by the tasks phase, decision (c)) found it, and it cost one WP03 reopen. The earlier placement of the replay paid for itself.
- The spec said the work package corpus check has an empty skip list; the corpus holds a Mission whose lanes file the product
  refuses, so the wording became a named refused list (9 work packages of one archived Mission, a legacy lanes file without a mission slug that the product's reader rejects).
- Two matcher copies are not identical (AD-20 wording corrected), and the unparseable review-cycle wording (AD-13) over-nulled
  members; both are wording amendments, no requirement changed.
- Three plan-time floors were nearly re-pinned downward by an implementer on a re-measurement that had not moved them below plan;
  the review caught it. Floors fixed at plan time stay fixed unless a measurement falls under them.
- A quadratic-time pattern in the shared leak tool, pre-existing from an earlier Mission, surfaced through the reader's redaction
  and was fixed in this Mission by operator decision.
- A legacy Mission's mapping-form subtasks are served as stringified mappings by v1 and by the 1.1 detail reader alike
  (FR-021 requires agreement).

**Lane outcome versus the plan.** The finalised manifest matched the plan's A-8 expectation: lane-b held WP02 alone; lane-a held
WP01, WP03, WP04, WP05, WP06, WP07 and WP08 in dependency order; `lane-planning` holds this work package. The tooling merged
approved dependency-lane tips into lane-a without a manual merge point (merge cbd13b82d, lane-b into lane-a). The one real parallel window the plan named (WP01 beside WP02) was available; the reports used here do not say whether it was used. The only departure from the plan's sequence was WP08 before WP07, which the tasks phase had
recommended. WP03 was reopened once and WP02, WP04 and WP08 once each by rejection transition, all through the CLI route.

**Open at close, to be folded at wrap-up** (the open fold list; none is fixed by this work package): pin the credential-before-
redaction order in the artifact reader tests; pin a nested research file classed as other; widen the email-pattern guard to the
`re.<function>` forms; reword the CHANGELOG clause "like every enumeration of this contract" (the lifecycle event types are
PascalCase); narrow the terminology scan's exemption to symbol names; optionally add the Subtask cell-attribution rule to its
`x-derived` wording; two strict-mypy `no-any-return` sites in test modules (pre-existing, CI does not run mypy); squash the
ruff-red commit `10c7e1857` with its fix `f022c1106` at compaction. All `contracts/` text edits are covered by the planned W-2
JVM rerun.
