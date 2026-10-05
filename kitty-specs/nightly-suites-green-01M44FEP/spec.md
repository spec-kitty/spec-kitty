# Mission Specification: Nightly suites green on main

**Mission Branch**: `issue-5611-5419-nightly-green`
**Created**: 2026-10-05
**Status**: Draft
**Input**: Operator brief for issues #5611, #5419, #5614 and #5708: the nightly suites green on `main`, with the performance budgets robust to runner speed and the commit-recipe gate caught per pull request. One mission, one pull request.

## Why

The release workflow only publishes when the nightly run for the tagged commit is green. On `main` @ `9adc68803f` four nightly jobs are red, for three unrelated reasons. Each is fixed here at its structural cause. Grounding evidence for every claim below is in [research/code-grounding.md](research/code-grounding.md).

| Track | Nightly job | Cause |
|---|---|---|
| A | integration + next | A coordination Mission whose primary directory is the bare slug cannot be consolidated onto a protected target (#5651, tracked by #5611). |
| B | performance | Three budget tests compare a wall-clock median against an absolute 2.5 s; the shared runner measured 2.52 to 2.59 s (#5419, #5614). |
| C | interpreter shard 3, out-of-matrix | The commit-recipe gate flags CLI help text, and no per-pull-request job runs that gate (#5708). |

## Domain Language

| Term | Meaning here | Avoid |
|---|---|---|
| Bare-slug coordination Mission | A coordination-topology Mission whose primary directory is `kitty-specs/<slug>` while its coordination branch and coordination directory use the composed `<slug>-<mid8>` name. | "legacy mission" |
| Coordination directory | The Mission's directory inside the coordination worktree, holding lifecycle records (status event log, status snapshot). | bare "coord dir" without saying which worktree |
| PRIMARY partition / COORD partition | The two commit destinations the commit router groups Mission files into. | bare "primary" (also means the Primary Branch) |
| Directory alias set | The exact pair of directory names that belong to one Mission: its primary directory name and its composed coordination directory name. | prefix or suffix matching |
| Start-up floor | The time one fresh interpreter needs to start the CLI and exit, measured in the same test run as the command under test. | "baseline" (also used for allowlist baselines) |
| Runner-relative measure | A result expressed against a quantity measured in the same run on the same machine, so machine speed cancels out. | "budget" without saying absolute or relative |
| Recipe | A printed command line an operator is expected to copy and run. | any string that mentions a command name |
| Per-pull-request home | A CI job that runs on the pull request that introduces a change. | "per-PR shard" when the job is not a module shard |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A bare-slug coordination Mission consolidates onto a protected target (Priority: P1)

An operator finishes a coordination-topology Mission whose primary directory is the bare slug and runs `spec-kitty consolidate` with a protected branch as the target. The consolidation lands and the coordination branch, worktree and marker are torn down.

**Why this priority**: It is a regression from a shape the product documents as genuine, it is the only remaining red in the nightly integration job, and that job gates the release.

**Independent Test**: Run the existing reproduction `test_bare_slug_coord_mission_consolidates_onto_a_protected_target` with the real bookkeeping commit (not a mock of it); it exits 0 with the Mission's work on the target, exactly one Mission directory holding the complete event log including the `done` event, a clean root checkout and no coordination worktree left.

**Acceptance Scenarios**:

1. **Given** a bare-slug coordination Mission with all work packages approved and a protected target, **When** the operator runs `spec-kitty consolidate`, **Then** it exits 0, the target carries the Mission's content, and the coordination branch and worktree are gone.
2. **Given** the same Mission, **When** consolidate seeds the coordination directory, **Then** the status files it writes are committed on the coordination branch and none is left untracked in the coordination worktree.
3. **Given** a Mission whose primary directory already carries the composed name, **When** it is consolidated, **Then** behaviour is unchanged from today.
6. **Given** a bare-slug coordination Mission that consolidated, **When** the operator lists the Mission directories on the target, **Then** there is exactly one, the primary one, and its status event log is complete.
4. **Given** a target that carries status files under a directory name that belongs to a different Mission, **When** the reconciliation gate runs, **Then** it still fails on that content.
5. **Given** a consolidation where the coordination seed commit could not be applied, **When** the entry preflight runs, **Then** consolidate stops before any branch moves, names the refused seed commit as the cause, and says the seeded files are kept for the retry, not a generic dirty-worktree remedy.

---

### User Story 2 - Performance tests do not fail because the runner is slow (Priority: P1)

A maintainer reads the nightly performance job. It is red only when owned-checkout commands or CLI start-up became slower relative to the same machine in the same run, and green when the runner was merely slow that night.

**Why this priority**: The job is P0-escalated, has been red on 4 of the last 6 nightlies without any product regression, and gates the release.

**Independent Test**: Run the three owned-checkout tests under artificial CPU load and confirm they pass; run them with a planted slowdown in the measured commands and confirm they fail.

**Acceptance Scenarios**:

1. **Given** an unchanged product, **When** the owned-checkout performance tests run on a machine under heavy CPU load, **Then** they pass.
2. **Given** a planted slowdown of the owned-checkout commands only, **When** the tests run, **Then** they fail and the message names the measured value and the limit.
3. **Given** a planted slowdown of CLI start-up itself, **When** the start-up test runs, **Then** it fails.
4. **Given** a change that makes an owned-checkout command spawn more git subprocesses, **When** the pull request's CI runs, **Then** a deterministic test fails on that pull request.
5. **Given** any start-up or owned-checkout limit, **When** a maintainer looks for its value, **Then** it is defined in exactly one place.

---

### User Story 3 - A printed commit recipe is caught on the pull request that adds it (Priority: P2)

A contributor adds a string to the CLI source. If it is a copy-paste `git commit` recipe, a pull-request job fails. If it is help text or a log line that merely mentions `git commit`, nothing fails.

**Why this priority**: The gate is red on `main` for a false positive, which reds two nightly jobs; and the gate only ran nightly, so the introducing pull request stayed green.

**Independent Test**: Run the gate on the current tree (green), then plant a recipe-shaped string in a source file and confirm both that the gate fails and that the pull-request job selection includes the gate for that file.

**Acceptance Scenarios**:

1. **Given** the current source tree including the repeated `-m` help text, **When** the recipe gate runs, **Then** it passes.
2. **Given** each of the 11 recipes that existed before the renderer conversion, **When** the gate's classifier is applied to them, **Then** each is still flagged.
3. **Given** a recipe-shaped string planted in any CLI source file, **When** pull-request CI selects jobs for that change, **Then** a selected job runs the gate and the gate fails.
4. **Given** the allowlist, **When** the gate runs, **Then** it holds only entries that the classifier still flags.

### Edge Cases

- A Mission slug that itself ends in eight characters resembling a mid8: the alias set is built from recorded identity, never inferred from the name.
- A bare-slug Mission whose `meta.json` cannot be read or has no `mission_id`: no alias is derived, and the existing fail-closed behaviour applies.
- The coordination directory exists but holds only seeded status files and no `meta.json`: teardown still resolves the Mission's identity.
- A performance run where the start-up floor is noisy: the floor is a median of several interleaved samples, not a single shot.
- Two source trees sharing one CLI home directory distort start-up timings; measurements use an isolated home.
- A recipe written with an ellipsis or without flags (`git add ... && git commit ...`): still flagged.
- A recipe inside an f-string with interpolated parts: still flagged.
- Prose that mentions `git commit` in passing: not flagged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Bare-slug consolidation lands | As an operator, I want a bare-slug coordination Mission to consolidate onto a protected target with exit 0 and a full coordination teardown, so that a documented Mission shape is not stuck. | High | Open | [build] | no |
| FR-002 | Seeded status files are committed | As an operator, I want every status file consolidate seeds into the coordination worktree to be committed on the coordination branch whenever the seed commit is applied, so that the worktree is not left with untracked status files on this path. | High | Open | [build] | no |
| FR-003 | One directory alias authority | As a maintainer, I want one place that answers "which directory names belong to this Mission" from recorded identity, resolved once per run and passed to its consumers, so that the failure layers are fixed by one rule. A consumer is converted only when a test proves it: reverting that consumer alone turns a test red. | High | Open | [build] | no: the reproduction, running the real bookkeeping commit, is the proof for each converted consumer |
| FR-004 | Alias is exact and limited to coordination records | As a maintainer, I want the alias set to contain only the Mission's own primary and composed names, and the composed name to count as bookkeeping only for coordination record kinds, so that nothing else slips past the reconciliation gate. | High | Open | [build] | no: negative controls on the same fixture, each still treated as content: `<slug>-<different mid8>/status.json`, `<slug>-<mid8>-x/status.json`, `<other>-<mid8>/status.json`, `<slug>-<mid8>/spec.md`, `<slug>-<mid8>/src/x.py`, and a slug that ends in eight identifier-like characters with no recorded identity |
| FR-005 | Canonical Missions unchanged | As an operator, I want Missions whose primary directory already carries the composed name to behave exactly as before, including not treating their bare stem as an alias. | High | Open | [ratchet] | yes: paired with FR-001 on the same fixture family and pinned by the existing sibling test |
| FR-006 | Refused seed commit stops consolidate with its real cause | As an operator, I want consolidate to stop with exit 1 and `Error code: COORD_SEED_COMMIT_REFUSED.` when the coordination seed commit was refused, naming the seeded files and saying they are kept so that re-running retries the commit. The refusal is read from a structured field on the seed report, not from warning text. | Medium | Open | [build] | no: triggered through the CLI by a commit hook that rejects the seed commit |
| FR-007 | Owned-checkout tests are runner-relative | As a maintainer, I want the three owned-checkout performance tests to assert a measure relative to a start-up floor taken in the same run, with interleaved samples and medians, so that runner speed does not decide the result. | High | Open | [build] | no: paired with a throttled run in which the previous absolute assertion is red and the relative one is green |
| FR-008 | The relative limit is evidence-based | As a maintainer, I want the relative limit chosen from recorded nightly data and local load and planted-regression measurements, with its headroom over the largest clean value (1.51 in the grounding data) stated and those figures written down, so that the limit is not a guess. | High | Open | [build] | no |
| FR-009 | Planted slowdown turns the test red | As a maintainer, I want a committed test that plants CPU-bound extra work (so it scales with the machine) inside the spawned CLI process from the test side, with no product hook, and expects the relative assertion to fail, so that the new measure is proven non-vacuous. | High | Open | [build] | no |
| FR-010 | Start-up regression signal is kept | As a maintainer, I want CLI start-up itself guarded by a median measured against a fixed interpreter workload taken in the same run, covering the bare start-up test and the warm second-call test, so that the rewrite does not drop the cold-start signal and no absolute wall-clock limit remains for start-up. | High | Open | [build] | no: paired with planted start-up work that turns it red |
| FR-011 | Deterministic per-pull-request proxy | As a contributor, I want the number of git subprocesses each owned-checkout command spawns pinned by a test in a directory that a pull-request job runs, counted in-process and pinned only after at least three agreeing samples, so that extra work is caught without a clock. | Medium | Open | [build] | no: paired with a planted extra call, and a job-selection dry run showing the test is selected |
| FR-012 | One authority for start-up limits | As a maintainer, I want every start-up and owned-checkout limit and the shared measuring helper defined once in the existing performance helper module, with a check that no other test file defines a start-up limit. | Medium | Open | [build] | no |
| FR-013 | Scanner classifies by recipe shape | As a contributor, I want the recipe gate to flag a string when `git commit` (including `git -C <dir> commit` and `git -c <key>=<value> commit`) is followed by a flag, a quote, a placeholder, a `$` expansion, a path, a shell operator (`&&`, `;`, a pipe, a line continuation) or the end of a string, line or backtick span, or when the same string also contains `git add`; and not to flag any other mention. | High | Open | [build] | no |
| FR-014 | Historical recipes stay flagged | As a maintainer, I want every one of the 11 recipes that existed before the renderer conversion still flagged by the new classifier, proven by fixtures copied verbatim from the tree before commit `3e09226fb4`. | High | Open | [ratchet] | yes: paired with the FR-013 prose and help-text negatives in the same fixture set |
| FR-015 | Allowlist holds only live hits | As a maintainer, I want the allowlist reduced to the entries the classifier still flags, with the stale-entry check still enforced. | Medium | Open | [build] | no |
| FR-016 | The gate runs per pull request | As a contributor, I want the recipe gate to run in a job that pull-request CI selects for a change to any file under `src/specify_cli/`, reached through the existing job-selection authority and not a one-off workflow edit. | High | Open | [build] | no: proven by a planted break and the job-selection dry run |
| FR-017 | Decision records | As a maintainer, I want the Track A alias ruling and the Track B runner-relative budget policy recorded as architecture decisions, and the flakiness guidance updated to match. | Medium | Open | [build] | no |
| FR-018 | Reproduction becomes a fixed-bug regression test | As a maintainer, I want the #5651 reproduction to keep its `regression` marker and have its docstring rewritten from "open, red on purpose" to what it now pins. | Medium | Open | [build] | no |
| FR-019 | One directory on the target | As an operator, I want a consolidated bare-slug coordination Mission to leave exactly one Mission directory on the target, the primary one, holding the complete status event log, with no composed-name directory beside it. | High | Open | [build] | no: the reproduction, running the real bookkeeping commit, asserts the directory listing and the event set (including `done`) on the target |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Robust to runner speed | With the product unchanged, the rewritten performance tests pass on the shared CI runner class: the measured ratios from at least two nightly runs dispatched on the mission branch sit under their limits, and each limit's headroom over the largest ratio observed there is recorded. Locally, one throttled run in which the previous absolute assertion fails and the relative one passes is the positive control. (Operator ruling 2026-10-05: calibrate on CI, not with long local series.) | Reliability | High | Open |
| NFR-002 | Sensitive to a real regression | The committed planted-work test fails the relative assertion, with the planted cost asserted to be between 0.3 and 0.7 of the start-up floor, in a local run and in the dispatched nightly runs. | Reliability | High | Open |
| NFR-003 | Performance-suite cost stays bounded | The owned-checkout tests, their fixture and the planted-regression test together take at most 90 s on the idle development machine (28.6 s today without floor samples), with the sample counts stated in the plan. | Performance | Medium | Open |
| NFR-004 | Recipe gate stays cheap | The moved recipe gate file runs in under 15 s on the development machine (about 6 s today). | Performance | Medium | Open |
| NFR-005 | Code quality | New and changed code passes `ruff check`, the formatter check and `mypy` with zero findings, with cyclomatic complexity at most 15 per function and new branches covered by tests in the same change. | Maintainability | High | Open |
| NFR-006 | No regression in the owning suites | Every test file and gate file named in research/code-grounding.md sections 3.7, 4.6 and 5.6 passes on the mission branch, except a test that also fails on the base commit `9adc68803f` for a cause unrelated to this mission; 0 such exceptions are expected. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Files owned by running missions | Do not edit the paths listed in research/code-grounding.md section 6. The one exception, by operator ruling of 2026-10-05, is the body of the `_is_bookkeeping` function in `consolidation/reconciliation.py`: its signature and call sites stay as they are, and the approved-claim bound in that file is not touched. If a root cause turns out to sit in another listed path, stop and report. | Technical | High | Open |
| C-002 | Fix at the seam | Track A is fixed in the product at the partition, bookkeeping, projection and teardown seams, on the callee side. The reproduction's fixture data and assertions are not weakened to make it pass. Replacing a mock of in-repository product code with the real code path is allowed (operator ruling 2026-10-05). | Technical | High | Open |
| C-003 | No loosening without evidence | No assertion, pin, allowlist or budget is loosened without measured data or the introducing commit cited in the pull request. | Business | High | Open |
| C-004 | No new size or ratchet gates | The mission adds no size gate and no shrink-only ratchet. Moving an existing gate and pinning exact counts are allowed. | Business | High | Open |
| C-005 | Red first | Each defect is reproduced red through its existing entry point before the fix; tidy-first enabler commits precede the red test. For Track B, where the base is green on a fast machine, "red" means the previous absolute assertion failing at the NFR-001 throttle level, together with the cited nightly result. | Business | High | Open |
| C-006 | Canonical routing only | Per-pull-request coverage is obtained through the existing job-selection authority and registry, never a one-off workflow edit. | Technical | High | Open |
| C-007 | Out of scope | #5638 and #5644 (different mechanism), promotion of the `tests/specify_cli/cli/commands` tree to a per-pull-request shard (#4374 / #4732), a lane for `tests/regression/` (#5652), product cold-start import cost, and the sibling bare-slug anchors listed in research/code-grounding.md section 3.6 (including the second classifier caller in the acceptance package) are cross-referenced or filed as follow-ups, not changed here. | Business | Medium | Open |
| C-008 | Separate lanes | Tracks A, B and C are delivered as separate work packages in separate lanes with no shared source or test files. The changelog entry and the decision-record index are written by one closing work package. | Technical | Medium | Open |
| C-009 | Heavy suites | No whole-repository run (`make test-full`) at any point. Full-directory runs of the owning directories and nightly selections happen once, at closeout, by operator request in the brief; implementers and reviewers run named files only. | Business | Medium | Open |
| C-010 | Issue priorities | Issue priorities are not changed. | Business | Low | Open |
| C-011 | Scan scope unchanged | The recipe gate keeps scanning `src/specify_cli/` only. Widening it to other source packages is a follow-up. | Technical | Low | Open |

### Key Entities

- **Directory alias set**: the pair {primary directory name, composed coordination directory name} for one Mission, derived from the Mission's recorded identity.
- **Start-up floor**: the median time of several fresh CLI starts that do no Mission work, taken interleaved with the measured command.
- **Relative limit**: the largest allowed value of the measured command's median against the start-up floor, with its supporting data.
- **Recipe classifier**: the rule that decides whether a source string is a copy-paste commit recipe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the mission branch, the five tests that are red in nightly run 37225822329 (one integration, three performance, one recipe gate) pass, and the four nightly selections show no failure that is green on the base commit. — [build] · no-op passable: no
- **SC-002**: A bare-slug coordination Mission consolidates onto a protected target in one command with exit 0, leaves no coordination worktree, and leaves exactly 1 Mission directory on the target with the complete event log. — [build] · no-op passable: no
- **SC-003**: The performance tests pass in at least two nightly runs dispatched on the mission branch, with their measured ratios recorded and under the limits, and the planted-work test turns the relative assertion red in the same runs. — [build] · no-op passable: no
- **SC-004**: A recipe-shaped string planted in CLI source fails a job that pull-request CI selects for that change; the current tree passes. — [build] · no-op passable: no
- **SC-005**: The recipe allowlist shrinks from 14 entries to the number the classifier still flags (2 in the grounding replay), with all 11 historical recipes still flagged. — [build] · no-op passable: no
- **SC-006**: Start-up and owned-checkout limits are defined in exactly 1 module, and a check fails if a test file defines its own. — [build] · no-op passable: no
- **SC-007**: A nightly run triggered on the pull-request branch is linked in the pull request, with the four previously red jobs green. — [build] · no-op passable: no

## Assumptions

- The operator's brief and the three rulings of 2026-10-05 (alias authority; fold the landed records into one directory; move the gate; calibrate the performance limits on CI) stand as the confirmed intent; no further discovery interview was held, at the operator's instruction.
- #5668 has no branch yet; the edit to `_is_bookkeeping` is limited to consuming the alias authority so a later rebase against #5668 stays small.
- `--version` may not be a clean start-up floor (it loaded more modules than the owned commands in the grounding probe). The plan phase verifies the floor command before the limit is calibrated.
- #5611 and #5419 close automatically on the next green nightly on `main`; this mission closes #5614 and #5708 and fixes #5651.
- The pull request is opened as a draft and marked ready once green, as the brief directs.
