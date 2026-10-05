# Tracer: Design Decisions

Mission: `mission-status-contract-1-1-01M42XJC` (#5625). Operator rulings on #5625.

- **CL-1** Additive through new operations only; minor 1.1.0; four gaps deferred.
- **CL-2** Baseline and sequencing: branch from `main`; the reality check builds on merged #5581.
- **CL-3** Artifact content is a JSON envelope, bounded (256 KiB), redacted (`[path]`, `[email]`),
  refused loudly (413, 415).
- **CL-4** Owned files carry a change state `changed`, `unchanged`, `unknown`, derived with git
  against the lane branch; `unknown` without a worktree.
- **CL-5 (2026-10-04)** AD-5 to AD-22 acknowledged (AD-15, AD-16 included); FR-015 contract-tools
  extension acknowledged; OQ-2 closed (keep AD-18); OQ-5 and OQ-6 closed (refusal codes via
  `WorkPackageDetailRefusal`); glob rule is exactly the repository's owned-files matcher
  (`_matches_any_glob` == `_mt_matches_owned_file`); a `WP*.md` with unparseable frontmatter is
  skipped as bootstrap does; AD-21 lists the detail's 500 `source_unreadable`.

## Plan phase decisions (2026-10-04; evidence in research.md)

- **D-P1 OQ-1.** The deferred-gaps record is a fifth heading `### Deferred to the next major version` inside the
  1.1.0 entry; `structure_check` accepts it unchanged (R-1). A committed test closes two weaknesses of the
  existing checks (file-wide heading presence; `provisional_check` joins every Provisional section).
- **D-P2 OQ-4.** Caps stay 1000 entries and 262,144 bytes (largest Mission tree 126 files; 2 of 15,561 files over
  the size cap) (R-2).
- **D-P3 Matcher.** The reader reproduces the owned-files matcher and a parity test calls both private copies;
  not "call", for the AD-18 reason (R-3).
- **D-P4 Rename seam.** A public seam exists: `kernel.git.changed_paths(..., renames=False)` lists both names;
  no `src/` change and no operator decision (R-4).
- **D-P5 Placement.** No new job. The reality extension runs in `tests (corpus-blocking)`; the reader and tool
  tests run in `tests (contract tools)`. New modules need two registrations outside the spec's slice file set
  (OD-1).
- **D-P6 Duplicate work package ids.** The first file in byte order of the file name is the work package's file
  (4 ids in one Mission); the universe is 3,193 distinct ids (OD-3).
- **D-P7 Tooling home of the predicate.** `malformed_artifact_path` lives in `leak_scan.py` (inside the slice
  file set) and is imported by the reader; `leak_patterns.py` would be the better home and is outside the set.
- **Operator decisions raised:** OD-1 (new test modules and their two registrations), OD-2 (required-example
  manifest in the tool fixtures or in the test), OD-3 (confirm the duplicate-id rule). See plan.md.

## Plan fix decisions (2026-10-04; evidence in research.md R-13 to R-15)

- **OD-4 (new, open).** How the raw-text pass of `leak_scan` treats a legitimate artifact path with an at sign: scope
  the text pass (recommended; verified on a scratch copy, R-14) or keep such names out of every file under `contracts/`.
- **ACK-1 (new, open).** The live baseline test is red locally until the tag; it is isolated in its own module (or
  distinct ids under OD-1 Y). Departs from FR-017 items 1 and 5 as worded; the Contracts workflow cannot run before the
  pull request, so the spec's accepted red is a local-only expectation.
- **D-P4 sharpened.** `changed_paths` returns `GitPath` objects (converted with `as_posix()`); `ValueError` and
  `GitCommandError` both give `unknown`; the manifest's `target_branch` must pass the branch pattern and not start with `-`.
- **D-P6 sharpened.** The authored file is the first regular, non-symlink entry for an id; the prompt file stays the
  spec's name-keyed definition; symlinks and directories are skipped like unparseable files.
- **D-P8 sharpened.** The readable invariant is checked against an independent byte-level oracle; the by-construction
  equality is a labelled wiring guard.
- **Planted kinds.** 25 kinds: 22 red-first, 3 regression controls (content and title kinds are already detected today).
- **OD-1 priced.** Option X selects the `architectural-heavy` battery through `packs.yml` and the registry file, needs a
  single writer for one physical line, and reads the scope check with two extra paths.

## Plan fix after the fresh sweep, round 2 (2026-10-04; evidence in plan.md and the commands named there)

- **OD-1 Y sharpened (still open).** Under Y there is no committed live baseline test: a live id in the examples module
  would inherit that module's `fast` marker, which the nightly `fast or unit` run selects on a shallow, tag-less
  checkout. The comparison against the tag is a recorded command at W-7 instead.
- **OD-2 X priced (still open).** X adds a third path outside the slice file set
  (`contracts/tools/fixtures/example_check/required_examples.json`), a scope reading and an acknowledgement.
- **OD-4 counts corrected (still open).** `values_strict=333` and `values_human=8137` hold for the scanner edit alone;
  with the ten strict names the scan reads 518 and 7952 (scratch copy).
- **ACK-1 widened (open).** (a) local red until the tag; (b) the live module is `contract` and `corpus` only and is red in
  any clone without the tag, with a fetch recipe in its message; (c) its retirement belongs to the 1.1.0 release Mission.
- **D-P4 sharpened.** `OSError`, `SubprocessError` and `ValueError` from `get_current_branch` and `git_merge_base` give
  `unknown`; `changed_paths` gets an explicit timeout; the two seams without a timeout are an accepted residual.
- **D-P3 sharpened.** The parity test wraps the single pattern as a tuple and as a list for the two private signatures.
- **Write scope.** IC-01 no longer owns `tracer-approach.md`; IC-09 is `planning_artifact`; tracer records come from the
  orchestrator (A-9).

## Round 3 plan fixes (fresh sweep, PLAN-FRESH2-001 to 010)

- **OD-1 is now three options (still open).** X (four modules, live test, ACK-1), X-pure (three pure modules, no live test,
  six registrations, no ACK-1, comparison at W-7) and Y. ACK-1 is item (6) of X's cost list and void under X-pure and Y.
  The recommendation is X-pure, with the margin against Y stated as narrow; the operator decides.
- **ACK-1 (c) has an owner and a hook.** Issue #5625 (checklist line in the D-0 claim comment), owner the Human-in-Charge
  unless named otherwise at D-0, exit the first of the 1.1.0 release commit and the next contract-changing Mission; if no
  release Mission is opened the owner deletes the module, its `--deselect` and its registry row.
- **Lane consolidation is a wrap-up step.** W-1 (i) accept, (ii) `spec-kitty consolidate` onto the local Mission branch,
  (iii) the checks; accept precedes consolidate (the tooling's order), and each step names the tree it reads.
- **The scope function takes name-status entries** with allowed data that carries the admitted statuses (`A` under the
  new-files prefix, `M` for the named existing files), so an edit of an existing schema file is reported.
- **The detail module drops `fast`** (it drives real git); the artifacts and 1.1 proof modules keep it.
- **Final fresh-sweep round (plan, add-only correction).** The plan text is now written for OD-1 X-pure (three pure
  modules, six registrations, IC-05 after IC-07), with the live module and ACK-1 as the X-only addition; every count and
  edge names X-family (X or X-pure), X only or Y. Consolidation is two hops (lane branches into
  `kitty/mission-<slug>` from `lanes.json`, then that branch into the `meta.json` target branch, which is HEAD);
  the recommended strategy is `rebase` (squash would flatten the per-work-package red-first commits), and W-5 under
  squash splits one tree by path. The issue-matrix row is set on `issue-matrix.json` through
  `spec-kitty agent issue-verdict`, add-only, after checking the finalisation scaffold. Option Y's cost now includes the
  detail git tests inheriting the payloads module's `fast` marker (or changing that marker). OD-1 to OD-4 and ACK-1 stay open.

## Operator decisions (2026-10-04, add-only)

- **OD-1 = X-pure.** Three new pure test modules; six registrations (three `--deselect` entries in `.github/workflows/packs.yml`,
  three rows in `tests/architectural/test_ci_corpus_trigger_completeness.py`); no live baseline test, so ACK-1 does not
  apply (void). Decided by the operator 2026-10-04.
- **OD-2 = Y.** The example-required guard lives in-test. Decided by the operator 2026-10-04.
- **OD-3.** Duplicate work package ids: the first regular work package file in byte order serves; documented in the
  contract. Decided by the operator 2026-10-04.
- **OD-4.** `leak_scan`'s text pass is scoped so path-name fields are checked by the artifact-path rule (AD-19), not the
  e-mail pattern; the prototype's proof that the real tree still scans clean is kept. Decided by the operator 2026-10-04.
- The earlier lines in this file that call OD-1 to OD-4 and ACK-1 "open" are superseded by this section.

## Tasks phase, squad round 1 fixes (2026-10-04, add-only)

Decisions applied to the tasks-phase artifacts (prompt bodies, `tasks.md`, `plan.md`, `quickstart.md`, the contract note);
`wps.yaml`, prompt frontmatter and the status records were not touched.

- **(a) Architectural battery (TASKS-VERIFY-001, -002).** The operator's brief requires WP05, WP06 and WP07 to pass both
  architectural battery parts exactly as `ci-router.yml` runs them; the charter permits a local run on an explicit operator
  request, and that brief is such a request, for these two parts and these three work packages only. The implementer runs
  `architectural-fast` and both `architectural-heavy` shards (`1/2`, `2/2`) before the approval request and records the
  output in the hand-off; the reviewer re-runs or verifies it; CI keeps the final word. The prompts keep the CI command
  blocks verbatim and add three runnable invocations (matrix placeholders resolved, `.venv/bin/python -m pytest` in place
  of `uv run --frozen python -m pytest`, junit files to a scratch directory, one-time `uv sync` by the orchestrator).
- **(b) No split of WP05 or WP06 (TASKS-DECOMP-001, -002).** A split needs a re-finalisation (lane and status churn). One
  pull request per Mission, one sequential lane, one commit per subtask with the red-first commit first are the review
  slices. Sizes corrected from the subtask sums (WP05 about 2,260 lines, WP06 about 1,900 to 2,000); seams named in `tasks.md`.
- **(c) JVM replay earlier (TASKS-ORDER-002).** The contract tree is final once WP04 is approved: the JVM replay runs then
  (step J-1, before WP05 is dispatched) and again at W-2 for the CHANGELOG-only delta (`plan.md` W-2 and P-10, `tasks.md`).
- **(d) W-5 leading commit (TASKS-ORDER-001).** `plan.md` W-5 gains a leading planning-artifacts and status-log commit built
  by path, with `status.events.jsonl` compared byte for byte before and after and the add-only check re-run on it.
- **(e) Lane edge rule (TASKS-ORDER-005).** The "to be observed" hedge is replaced by the verified rule: claiming merges only
  approved dependency-lane tips (`_approved_dependency_lane_refs`, `check_claim_ancestry` in `implement_support.py`), so
  WP01 is not gated by `lane-b`. Friction F-31 stays as the record; first dispatch is a confirmation only.
- **(f) Dispatch order (TASKS-ORDER-003).** WP08 before WP07 is recommended (WP08 carries the budget, oracle and floor
  unknowns); both orders are legal.
- **(g) Registration timing (TASKS-DECOMP-003, TASKS-ORDER-004, TASKS-VERIFY-005).** The registration pair is committed with
  the module-creating red-first commit of WP05, WP06 and WP07; the red-first test content is still first. The registry gates
  are green on that commit; only the new reader or proof tests are the intended red. A skeleton module in the red-first
  commit (T023, T031) makes each test fail on its own assertion (TASKS-VERIFY-007).
- **(h) Plan edits.** Minimal and add-only in spirit: a "Decided reading" note under the operator decisions, D-P7 and the
  AC-CONTENT row reworded so OD-4 reads as chosen, the "X only" convention restricted to the unchosen OD-1 and OD-2 options,
  and no committed contract example holds an at-sign path (WP03, WP04, contract note, `plan.md`). The quickstart no longer
  runs the nonexistent live module; the extras constant is `EXTRA_ALLOWED_REGISTRATIONS` and the unused OD-2 constant is gone.
- **Other.** The FLOORS fields move to WP08 (TASKS-DECOMP-010); WP04 writes the OD-3 duplicate-id rule into the published
  contract text (TASKS-COVER-005); success-criterion, FR and C-003 mapping notes added in `tasks.md` without changing
  frontmatter (TASKS-DECOMP-007, TASKS-COVER-002, -003, -004); each prompt carries a "Decisions honoured" line (TASKS-COVER-001).

**Tasks phase, fresh-sweep fix round 2 (add-only).** Step J-1 now refers to the single mechanism (a) list in plan W-2 (only `breaking-change --baseline-root` and the release dry run wait for the tag or final CHANGELOG), names the rejection-transition reopen route for a defect in approved WP03 or WP04, and is a stated dispatch precondition of WP05. Plan IC-08 Sequencing records that the tasks phase recommends IC-08 before IC-05 (both orders legal). WP07 T038 states the two trees (planning base: all assertions red; lane start: version assertion the green control). The WP05, WP06 and WP07 battery legs now say: run from the lane workspace root, in the background up to the CI timeout, and that the four deselected files run in their own jobs or gate lists, so "complete battery" is no longer claimed.

- **Tasks phase, final round (2026-10-04).** (1) The WP07 lane start is the tip of the preceding approved work package in lane-a (WP06, or WP08 when dispatched first), not the WP04 tip. (2) The tag-less release dry run is part of the J-1 replay (`release-dry-run` needs only `validate-bundle`; WP03's skeleton heading exists); only `breaking-change --baseline-root` waits for the tag or final CHANGELOG, so plan W-2 stands unchanged; the JVM-case count is measured at J-1 time. (3) Battery legs run detached with an exit-code file and are polled in the foreground; a missing exit-code file is never a pass. (4) The tasks.md Gates paragraph now names the four deselected files and the archive-freeze job.

## Operator request: local architectural battery runs (2026-10-04)

The charter forbids local full architectural-battery sweeps unless the operator explicitly requests them. The operator explicitly requested them for WP05, WP06 and WP07: the fast part and both heavy shards, with the command lines copied verbatim from `ci-router.yml`. Until now the tasks phase had inferred this from the orchestrator's brief; this entry is the actual request.

The operator also confirmed, as orchestrator calls:
- WP05 and WP06 stay unsplit;
- dispatch WP08 before WP07;
- the J-1 JVM/contract replay runs after WP04 is approved;
- W-5 starts with the planning-artifacts and status-log commit.

## WP03 contract notes (2026-10-04)

- **The `ArtifactPath` pattern** begins with a lookahead that rejects line breaks. A character-class exclusion alone is not enough, because `$` in both Python and Java accepts a trailing LF.
- **The break set** follows `str.splitlines`: LF, CR, VT, FF, FS, GS, RS, NEL, U+2028 and U+2029, written with escapes.
- **`ArtifactRefusal`** requires `code` only, as the contract note says. (`StreamRefusal` also requires `detail`.)
- **The 1.1.0-SNAPSHOT CHANGELOG** has a draft Provisional section so that `provisional_check` passes. WP07 finalises that list, adds the #5533 line and fills in the Deferred section.
- **Tooling friction:** `run_negative_cases.py` failed twice with an intermittent `FileExistsError` while copying a plant's `_shared` tree into a fresh `--work` directory, then passed. This needs a look before the wrap-up.

## Operator decision: ArtifactKind values are snake_case (2026-10-04)

The J-1 JVM replay (contracts.yml lint job, vacuum ruleset `contracts/lint/ruleset.yaml` rule `enum-case`) refused the kebab-case `ArtifactKind` values that FR-004 specified. The Python gates do not run this lint. Operator ruling: rename to snake_case, matching every other enum of the contract, rather than exempt `ArtifactKind` from the rule. The values are now `review_cycle`, `work_package_prompt`, `data_model` and `analysis_report`; the other eight are unchanged and the classifier order is unchanged. File names (`review-cycle-<N>.md`, `data-model.md`, `analysis-report.md`) are not kinds and do not change. Spec FR-004, the data model's classifier and the operations-and-schemas table were edited; analyze was re-run; WP03 was reopened by a rejection transition to apply the rename to the schema, examples and enum pins.

## J-1 result (2026-10-04)

First J-1 replay (on the WP04 tip b0ab5c12b) failed one step: the vacuum `enum-case` lint on the kebab-case `ArtifactKind` values (class a). Fixed by the snake_case rename above (WP03 cycle 3, f01849aa6). The repeated J-1 replay on the lane tip passed every JVM job of `contracts.yml`: the bundle with JVM validation and the Java view, the tamper plant, the TypeScript client smoke, resolver parity, the lint (0 violations) and its plants, the tag-less release dry run, and `negative-tests` with no skip tags (127 of 127). `breaking_check --baseline-root` against the 1.0 baseline: breaking=0. Replay note: the tamper check needs a TMPDIR whose ancestors hold no `.git`. The contract tree is final for the readers; WP05 may be dispatched.

## WP05 approval notes (2026-10-04)

- New public names in the test-side reader: `ReaderContext(repo_root, tools, fs=REAL_FS, mission_dirs=None)`, `read_content`, `list_artifacts`, `artifact_references`, `resolve_mission(ctx, id)`, `index_missions(repo_root)`, `path_sort_key`, `read_file`, `prompt_file_name`; `ContractTools.scan`; `Fingerprint.directories`. `index_missions` reads `meta.json` directly and matches `resolve_mission_identity` on all 548 real Mission directories (zero divergence).
- Conformance confirmed by review: the case-sensitive media type (AD-11), the over-cap `readable` decided from the `lstat` size (AD-7), and the `\S*` widening of host-path redaction (data model, Redaction; fail-safe, it can consume a trailing delimiter).
- Wrap-up fold list: pin the order of decision (credential check before redaction) and a nested `research.md` classed `other`; both reverts survive the current tests.
- Found: `contracts/tools/leak_patterns.py` `EMAIL_PATTERN` (pre-existing, from #5558) backtracks quadratically on a long token without whitespace (0.14 s at 16 KiB, 2.0 s at 64 KiB, 28 s at 256 KiB). It does not affect the contract's guarantees; NFR-002 bounds bytes, not time. Routing pending an operator decision.

## Operator decision: fix EMAIL_PATTERN in this mission (2026-10-04)

The quadratic backtracking in `contracts/tools/leak_patterns.py` `EMAIL_PATTERN` (pre-existing, from #5558) is fixed in this mission, as one single-purpose commit: the pattern becomes linear with identical matches (a leading negative lookbehind on the first alternative, or an equivalent), plus a timed regression test on a long token without whitespace and a differential test showing identical matches on the existing corpus. It lands after WP06 is approved, as an orchestrator-routed fold-in on lane-a with its own independent review, before the wrap-up. NFR-007 holds (no `src/` change).

## WP06 approval notes and WP08 guidance (2026-10-04)

The WP06 review approved the detail reader and found three wording defects in the spec. Each is amended in `spec.md` as wording only; no requirement changes.

**Amendments**
- AD-20: the two glob matchers are not identical. `_mt_matches_owned_file` normalises a backslash and one leading `./`; `_matches_any_glob` does not. The text now says they agree on every path git produces, and that the two divergences (a leading `./`, a backslash) lie outside what git yields; the parity test bounds both. The reader follows data-model rule 3.
- AD-13 (and FR-005 line 390, the fixture list and AC-DETAIL twins): an unparseable review-cycle file nulls only `reviewedAt` and `reviewer`. `verdict`, `feedbackReference` and `artifactPath` follow their own FR-005 rules, so a readable file or an event verdict is not hidden.
- FR-021 and AC-DETAIL (the work package corpus check): "empty skip list" is replaced by a named refused list. The corpus holds a Mission whose source the product refuses (a legacy `lanes.json` with `feature_slug` and no `mission_slug`; `read_lanes_json` raises `CorruptLanesError`, so by FR-006 its work packages answer 500 `source_unreadable`). The wording is general and names no Mission. The "empty skip list" wording for the Mission and file walks (FR-021 listing check) is unchanged.

**WP08 requirements (ruling a)**
- Count the refused work packages as examined-as-refused: `examined + refused == discovered`, where `refused` is a named refused list, not a skip list.
- Derive the refused list by an independent scan (a `lanes.json` with `feature_slug` and no `mission_slug`), not through the reader under test.
- Fail on any 500 outside the list, and on a stale entry (a listed Mission that answers 200, or a pinned count that differs from that Mission's whole work package count).
- Set the numeric floors on the 200 count so they exclude the refused work packages.
- Today: 9 work packages of the Mission `064-complete-mission-identity-cutover`.

**Subtask attribution (ruling b)**: a Subtask table row is attributed by a `WP` cell after the title cell (as in the sample row `| T001 | title | WP01 | [P] |`); without such a cell, by the enclosing work package section. A row in WP01's section that names WP02 belongs to WP02.

**Contracts edit (ruling c)**: the `ReviewCycle` schema description fix ("reviewedAt and reviewer are null; the other members follow their own rules") is a `contracts/` edit, description only. It is routed to an orchestrator fold-in on lane-a and is covered by the planned W-2 JVM rerun.

## Contracts fold-ins approved (2026-10-04)

- `EMAIL_PATTERN` (operator decision above): `contracts/tools/leak_patterns.py` gains `email_matches` and `redact_emails`. They give the old pattern's exact spans and redaction output in linear time. An independent fuzzer found 0 differences in 900,000 adversarial and 960,799 exhaustive strings, and every 256 KiB adversarial input takes at most 0.02 s. `EMAIL_PATTERN` itself is marked detection-only and guarded by a test. Both redaction callers have a glued-address test that fails on a revert to the old substitution. A lookbehind-only pattern was rejected, because it left the second address of a glued pair of addresses unredacted.
- The `ReviewCycle` description now says only `reviewedAt` and `reviewer` are null for an unparseable cycle file (FR-005, AD-13). It is description-only: breaking=0. The W-2 JVM rerun covers it.

## Close-out record (2026-10-05, WP09; add-only; source: the named review reports)

- **D-P14 Examination oracle independence (WP08 review, cycles 1 and 2).** The corpus oracle decides a file from its bytes alone
  and a test (AST based) asserts that the oracle neither calls nor imports the reader. The guard stops accidental coupling only; a
  deliberate bypass (an alias import, an attribute lookup by string) is not caught, which the reviewer accepted at severity 1 to 2.
- **D-P15 Floors are plan-time values (WP08 review, cycle 1).** A floor is not re-pinned because a re-measurement lies above it.
  The code floors stay 8300, 290 and 72 against measurements of 8,734, 303 and 79. The contract note D is unchanged; a test pins every
  new floor at or above its plan-time value and rejects a floor field without a pin.
- **D-P16 Non-comparable Missions (WP08 review).** Verdict comparison against the v1 payload is skipped only when the read
  directories differ; the count of such Missions is asserted to be 0 on the corpus, so a skip cannot hide a Mission.
- **D-P17 Subtask roster of a legacy Mission (WP08 implementer, WP08 review F7).** The oracle states v1's rule (each item
  stringified), so the detail agrees with v1 for the six work packages of one archived Mission that write subtasks as mappings.
  Both surfaces carry the quirk.
- **D-P18 Refused-list scan (WP06 ruling (a), WP08).** The refused list is derived by reading the lanes files as JSON directly (a
  file with the old slug key and no mission slug key), not through the reader under test; the pinned count must equal that
  Mission's whole work package count (9 today).
- **D-P19 Review-cycle pointer pattern (WP04 review, cycle 1).** The `feedbackReference` pattern is never wider than the
  repository's pointer validator; a differential test over valid and invalid pointers pins this; `Workspace.planningBranch` is
  bounded at 255 characters.
- **D-P20 Artifact path line breaks (WP02 review, cycle 1).** A line break or control character in an artifact-path value is
  malformed (the structured pass), and the text pass masks only single-line scalars; the reverse order of those two would let a
  host path or address hide in a block scalar.
- **D-P21 Redaction callers use the linear email redactor (fold-in review).** `redact_emails` and `email_matches` give the old
  pattern's exact spans and output; the retained pattern is detection only. A text guard (not complete: it misses aliases and the
  `re.<function>` forms) plus two per-caller glued-pair tests protect it. The widening of the guard is on the wrap-up fold list.
- **D-P22 Cycle 3 of WP03 (J-1).** The snake_case rename touches kind values only; file names, the `review-cycle://` scheme and
  pointer patterns do not change. The lint reports only the first offending enum value, so a single-value rename is caught on
  rerun only (tool behaviour).
- **Review findings left open for the wrap-up fold** (none fixed here; the open fold list is the record): credential check
  before redaction pinned in the artifact reader tests (WP05 F1); nested research file classed other (WP05 F2); email-pattern
  guard forms (fold-in S2 residual); CHANGELOG wording on enumeration case and the terminology scan exemption (WP07, both
  severity 2); Subtask cell rule wording (WP06 (b), severity 1).
- **Residual risks accepted by review, recorded:** the two git seams without a timeout (D-P4 residual); the `\S*` widening of host
  path redaction can consume a trailing delimiter (fail safe); media type matching is case sensitive (AD-11 silent on case).

## Operator ruling 2026-10-05: no new contract version

- **Ruling.** The Mission Status contract is still unreleased on `main` (`info.version: 1.0.0-SNAPSHOT`, never tagged). The additions of this Mission go into the SAME release as the previous API changes, with no new version number.
- **Consequences.** There is no 1.1.0. `info.version` stays `1.0.0-SNAPSHOT`. The CHANGELOG additions merge into the existing `1.0.0-SNAPSHOT` section (no new version heading). The "minor-version proof" becomes an "additive proof against the contract tree on `main`" with no version-bump assertion (no 1.1.0, 1.0.1 or 2.0.0 cases). No release tag is needed: W-6 rebases onto upstream `main` without a tag, W-7 compares against the main tree (`aef7cc967` or the current `origin/main`), and the live baseline test (already void under OD-1 = X-pure) stays void, with ACK-1. "1.1" remains the working name of this slice (Mission slug, issue title, test module name), not a version.
- **Tooling fact behind the proof design.** `breaking_check.py` fails any bundle change against a baseline carrying the same `info.version` (`BUNDLE_CHANGED_VERSION_SAME`, spike row in research R-7). The `--baseline-root` run therefore uses a scratch copy of the main tree with a lowered `info.version` and asserts the `counts:` line (`baselines=1`, `breaking=0`); a permanent test asserts the tree's `info.version` equals the baseline's.
- **Amended artifacts.** spec.md (summary, CL-1, CL-2, AD-16 and its table row, user story 3, FR-017, FR-018, FR-020 wording, AC-VERSION, A-4, dependencies, Out of Scope, SC-002, SC-007, traceability), plan.md (ruling banner, D-0, IC-05, IC-09, D-P10, D-P11, W-1 to W-7, P-5, P-9, P-10, P-12), data-model.md, contracts/tool-extension-and-reader.md, contracts/operations-and-schemas.md, quickstart.md, and a supersession note at the head of research.md. The `tasks/WP*.md` files and `tasks.md` were not edited; their contradictions are listed for the WP07 rework brief.
