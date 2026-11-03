# Mission Specification: A refusal notice that names a repair the operator can actually perform

**Mission Branch**: `tracked-meta-unanswerable-git-01M6GRFF`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#7131 — "Tracked-meta refusal gives an unusable checkout remedy when Git cannot answer". Related, already landed: #6673 (the refusal itself), #7075/#7055 (the unusable-anchor test fixture). Guidance from the operator brief: extend, never duplicate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator whose Git cannot answer is told so, and told what to fix (Priority: P1)

A `kitty-specs/<mission>/meta.json` is gone from the working tree. The operator runs an upgrade
(`spec-kitty upgrade` — the `2.0.6` consistency sweep, the `3.2.0a4` lifecycle normalization or the
`3.2.6rc1` runtime-state cutover). Git cannot answer at all for that checkout: its `HEAD` points at a
gitdir that does not exist, the checkout is owned by another user and git refuses the ownership, or
`GIT_DIR`/`GIT_WORK_TREE` name somewhere else.

Today the seam refuses — correctly and fail-closed, with the stable
`TRACKED_META_UNAVAILABLE` code and no identity, seed or metadata write — but the notice claims the
file "is missing from the working tree" and prescribes `git checkout -- <path>`. Git never
established that the path is tracked, and that command fails for exactly the same reason the
classification failed. The operator is sent round a loop they cannot break.

**Why this priority**: the refusal is the safety net for every identity-writing upgrade seam. A
refusal whose remedy is unusable is a support ticket: the operator has no next action, and the
tempting improvisation (delete `meta.json`, re-run) is the identity fork the refusal exists to
prevent.

**Independent Test**: through the pre-existing entry point
(`classify_missing_tracked_meta`, which every seam calls, and `cutover_mission` for the end-to-end
shape), build a Mission directory whose `.git` anchor is unusable, assert the refusal is unchanged
(`refuse is True`, code `TRACKED_META_UNAVAILABLE`, nothing written), and assert the notice names the
repository-access repair class and no longer offers `git checkout --`.

**Acceptance Scenarios**:

1. **Given** a Mission whose tracked `meta.json` is absent and whose `.git` anchor git cannot follow,
   **When** a seam classifies it, **Then** it refuses with `TRACKED_META_UNAVAILABLE` and the notice
   says the repository cannot be read and that whether the path is tracked is unknown — never that
   the tracked file "is missing".
2. **Given** the same state, **When** the operator reads the notice, **Then** it names the repair
   class (fix the repository layout or environment; run `git status` in the checkout to see git's own
   cause) and does not offer `git checkout -- <path>`, which cannot succeed.
3. **Given** a checkout git refuses for **ownership** reasons, **When** a seam classifies it, **Then**
   the notice names ownership as the cause and says trusting the repository is a deliberate operator
   decision scoped to that checkout — it never tells the operator to add a wildcard `safe.directory`
   and never changes one itself.
4. **Given** a usable repository whose committed content for the path cannot be produced, **When** a
   seam classifies it, **Then** the notice names a repository-object repair (`git fsck`) rather than
   a checkout.
5. **Given** a readable repository that really does hold a usable `meta.json`, **When** a seam
   classifies it, **Then** the existing restore-or-rebuild behaviour and its `git checkout --` remedy
   are unchanged (positive control: the new cause branches cannot swallow the working path).

---

### User Story 2 - The cause is carried, not guessed from the message text (Priority: P2)

The classifier that answers "what does git hold for this path" already knows *why* it could not
answer: it either failed to identify the repository, failed to read the committed object, or was
refused on ownership grounds. That cause is carried as data on the classifier's result and the
notice renders it, so the notice module never re-parses git's message text and a second
classification authority cannot appear.

**Why this priority**: without it the notice has to re-derive the cause from stderr, which is how
this defect class recurs. It is P2 because US1 is the operator-visible value and this is what keeps
it honest.

**Independent Test**: `read_tracked_meta` returns the cause on its `TrackedMeta` result for each of
the three shapes, and the notice module contains no stderr parsing of its own for these causes.

**Acceptance Scenarios**:

1. **Given** an unusable `.git` anchor, **When** `read_tracked_meta` answers, **Then** the result
   carries the repository cause and `unavailable is True`.
2. **Given** a repository whose committed blob for the path cannot be read, **When**
   `read_tracked_meta` answers, **Then** the result carries the committed-content cause.
3. **Given** a git that refuses the checkout's ownership, **When** `read_tracked_meta` answers,
   **Then** the result carries the ownership cause.
4. **Given** any of the above, **When** the notice is rendered, **Then** no unsanitised git stderr
   (paths, hosts, credentials in a URL, environment values) appears in it.

---

### Edge Cases

- **Git is not installed at all.** `run_git` reports `not_run`; the existing answer ("nothing is
  tracked here", `unavailable=False`) is correct and must not gain a cause — the seam's normal
  pre-identity repair applies and no notice is owed.
- **Git times out.** Already re-raised, never degraded. Unchanged.
- **A `.git` anchor exists but the path genuinely is not tracked** (a pre-identity Mission inside a
  real repository). Prefix resolution succeeds, so no cause is set and the seam repairs as today.
- **Index-only, staged-differs and corrupt** keep their own, already-distinct notices; the new
  branches must sit beside them, not replace them.
- **A present `meta.json` that lost its `mission_id`** (`tracked_meta_refusal`) shares the refusal
  path: its lead sentence stays true ("has lost its mission_id") while the repository cause tail
  changes. Both leads must read correctly against all three causes.
- **Machine-local paths in the notice.** The notice prints project-relative paths only, as today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Cause is carried on the classifier result | As a maintainer, I want `read_tracked_meta` to carry why git could not answer so that the notice renders a cause instead of re-parsing stderr. | High | Open | [build] | no — the cause field is read by the notice branches and asserted per cause |
| FR-002 | Refusal and code are preserved | As an operator, I want the refusal, the `TRACKED_META_UNAVAILABLE` code and the no-write guarantee unchanged so that the safety net still holds. | High | Open | [ratchet] | no — paired with the existing refusal assertions on the same fixtures |
| FR-003 | Unreadable repository notice | As an operator, I want the notice to say git cannot read this repository and that the tracked state is unknown so that I stop looking for a file to restore. | High | Open | [build] | no — asserted against a real unusable `.git` anchor |
| FR-004 | Repair class, not a dead remedy | As an operator, I want the notice to name the repair class for each cause and never offer `git checkout --` where it cannot work. | High | Open | [build] | no — asserted per cause |
| FR-005 | Ownership trust is an operator decision | As a maintainer, I want the notice to name ownership as the cause and scope any trust decision to that checkout so that no wildcard trust is suggested or performed. | High | Open | [build] | no — asserted on the ownership notice text |
| FR-006 | Committed-content repair | As an operator whose object store is damaged, I want a repair (`git fsck`) rather than a checkout so that I fix the actual fault. | Medium | Open | [build] | no — asserted on the committed-content notice text |
| FR-007 | Working paths unchanged | As a user with a healthy checkout, I want the restore-or-rebuild behaviour and its notice unchanged so that a good Mission is still repaired without ceremony. | High | Open | [ratchet] | no — positive control on the same module |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No stderr leakage | No notice renders git stderr verbatim; only a curated cause phrase and the project-relative path appear. Asserted by a test that seeds distinctive stderr text and asserts it is absent. | Security | High | Open |
| NFR-002 | Classification stays pure | `read_tracked_meta` and the notice keep their current purity: no writes, no ownership-config change, no network. Asserted by running them over a fixture with a read-only failure and checking the working tree and git config are untouched. | Reliability | High | Open |
| NFR-003 | Fast-tier budget | The added coverage keeps the module's existing `pytest.mark.unit` / `pytest.mark.fast` posture and adds no more than three new test functions plus the strengthened existing ones. | Performance | Medium | Open |
| NFR-004 | Complexity ceiling | Every touched function stays within the repository's `max-complexity = 15`, with the per-cause text in module constants rather than a nested conditional. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fail-closed refusal preserved | The mission may change diagnosis only. A refusal must never become a repair, and no identity, seed or metadata write may be introduced on any of these paths. | Technical | High | Open |
| C-002 | One notice authority | The text lives once in `src/specify_cli/upgrade/tracked_meta_notice.py`; consumers keep rendering `MissingTrackedMeta.notice` and must not grow their own wording. | Technical | High | Open |
| C-003 | No ownership-policy weakening | The mission adds no `safe.directory` write, no `*` trust and no unconditional trust command. Any trust action is named as a decision the operator makes for one checkout. | Regulatory | High | Open |
| C-004 | Extend #6673, do not re-open it | `TrackedMeta`'s existing flags (`index_only`, `corrupt`, `staged_differs`), their notices and their codes stay as they are. | Technical | High | Open |
| C-005 | Shared ownership predicate, one owner | The "git refused on ownership" predicate already exists in `src/specify_cli/core/git_preflight.py`; the mission reuses one owner rather than adding a second copy. | Technical | Medium | Open |

### Key Entities

- **`TrackedMeta`**: the classifier's answer to "what does git hold for this Mission's `meta.json`". Gains one optional *unreadable* cause (repository / ownership / committed content) that is set only when `unavailable` is true; every existing field keeps its meaning.
- **`MissingTrackedMeta`**: the operator-facing notice plus refusal flag and stable code. Its `notice` text gains three cause-specific tails; `refuse` and `code` are untouched.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every one of the three causes, a test asserts the refusal is preserved (flag, code, nothing written) and that the notice contains no `git checkout --` — [build] · no-op passable: no
- **SC-002**: The healthy-path tests in `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` and the cutover placement suite keep passing unchanged — [ratchet] · no-op passable: no
- **SC-003**: Operator-facing prose introduces no stderr text: the leakage assertion passes — [build] · no-op passable: no
- **SC-004**: The touched modules pass `ruff check`, `ruff format --check`, `mypy` and their own test files with zero new failures — [ratchet] · no-op passable: no
