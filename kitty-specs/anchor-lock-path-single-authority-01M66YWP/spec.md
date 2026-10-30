# Mission Specification: One kernel helper for anchor-keyed lock paths

**Mission Branch**: `issue-6727-anchor-lock-paths`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue #6727 — "Extract one kernel helper for anchor-keyed lock paths (event-log, synthesis and status locks repeat the digest/common-dir logic)". Follow-up from the pre-merge architecture review of Mission `synthesis-record-integrity-01M5ZBC9` (#6453).

## Intent Summary (confirmed)

Confirmed intent comes from the issue body and its acceptance criterion, plus the
operator's instruction for this run ("extract one kernel helper and route all three
through it, keeping each lock's behaviour and error handling identical — a
single-authority consolidation, so pin the shared behaviour with tests that fail if the
helper's contract drifts"). The interactive discovery interview is satisfied by that
recorded intent; no `[NEEDS CLARIFICATION]` markers remain.

- **Primary actor:** a maintainer of a lock family (event-log append, charter synthesis, Mission
  status) who must place a lock where every worktree and every process of one repository
  agrees, and the Java write-service author (#6193) who must compute the same event-log lock
  name.
- **Trigger:** a change to the anchor-keyed lock-path rule (identity normalisation, digest,
  directory) that today must be made in three modules, and has already been copy-pasted once
  on purpose (`synthesis_lock.py`, #6453).
- **Desired outcome:** one kernel helper owns "digest of the resolved, case-normalised anchor
  under `<git-common-dir>/spec-kitty-locks/…`"; all three families call it; each family keeps
  its own non-git fallback, its own error type and its own byte-identical lock file name.
- **Rule / invariant:** for one resolved anchor, the lock file a family produces before and
  after this change is the same path, byte for byte; and no module outside
  `src/kernel/locks.py` derives an anchor digest for a lock file name.
- **Boundary:** the three families named in the issue. The two status lock builders that are
  *not* anchor-keyed (`feature_status_lock_path`, keyed by Mission directory name;
  `project_event_log_lock`, keyed by a fixed sentinel) and the fixed-name lock files of
  `specify_cli.review.verdict_commit_queue` and `specify_cli.design.receipts` are out of
  scope: they have no digest rule to share. No lock file is renamed and no migration is added.

Bulk-edit determination: **not a bulk edit.** No existing identifier, path, key, label or
term changes; the change adds one helper and rewires three call sites, each keeping its
output identical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One rule, three families (Priority: P1)

A maintainer needs the event-log append, the charter synthesis run and the Mission checkout
claim to agree on where a lock anchored at a path lives. Today each module resolves the
anchor, `os.path.normcase`s it, digests it and joins the lock directory itself, so a change
to the rule (a different normalisation, algorithm, truncation or directory) is three edits
that can silently disagree. After the change there is one helper, and the three family
functions are one call plus their own policy.

**Why this priority**: this is the issue's defect (DIRECTIVE_044, one canonical source) and
the acceptance criterion.

**Independent Test**: call `kernel.locks.anchored_lock_path` directly for each of the three
shapes and compare with the literal path the family produces; the families' existing tests
also pin their paths and must stay green unchanged.

**Acceptance Scenarios**:

1. **Given** a git repository, **When** `event_log_lock_path(log)` and
   `synthesis_lock_path(repo)` are called for one anchor, **Then** both names carry the same
   sha256[:32] digest and differ only by subdirectory (`event-logs` / `charter-synthesis`).
2. **Given** a git repository, **When** `_checkout_claim_lock_path(checkout)` is called,
   **Then** the name is `__checkout-<sha1[:16]>__.status.lock` exactly as before, and
   `_is_checkout_claim_lock_key` still accepts it.
3. **Given** the helper, **When** the anchor is outside a git repository or git cannot be
   invoked, **Then** the helper raises the `kernel.git_topology` error and each family keeps
   its current outcome: event-log and synthesis refuse with their own error type; the status
   claim lock degrades to its non-git home and never raises.

### User Story 2 - The contract cannot drift back (Priority: P1)

A reviewer or a future contributor must be able to change the rule in one place and be told
when a fourth copy appears. The shared behaviour is pinned by value, not by implementation:
literal digests for each shape, the cross-family equality of the digest for one anchor, and
a source-shape gate that fails when a module outside `kernel/locks.py` derives an anchor
digest to name a lock file.

**Why this priority**: a consolidation without a drift guard decays back into copies; the
issue asks for exactly this protection.

**Independent Test**: on the base commit the new contract tests and the gate fail (the
helper does not exist, and the gate names the three copies); after the change they pass.
Re-introducing one hand-rolled copy makes the gate fail again.

**Acceptance Scenarios**:

1. **Given** the helper, **When** a caller passes an unknown digest algorithm or a digest
   length outside 1..64, **Then** the helper raises `ValueError` instead of minting a name it
   cannot reproduce.
2. **Given** the helper is called with an explicit common dir, **When** `git rev-parse` is
   made to raise, **Then** the call still returns the expected path (no git probe).
3. **Given** a module under `src/` that is not `kernel/locks.py`, **When** it names a file
   under `LOCK_DIRECTORY` and also digests a path, **Then** the source-shape gate fails.

### Edge Cases

- **Anchor is a file that does not exist yet.** The event-log anchor is the log path, created
  by the append. `kernel.git_topology._probe_dir` only normalises an *existing* file, so the
  probe must run in the anchor's parent. The helper therefore takes the probe directory
  explicitly and the event-log family passes `anchor.resolve().parent`; behaviour for a
  not-yet-created log is unchanged (`tests/kernel/test_event_log_append.py` covers appends to
  new logs).
- **Symlinked checkout or linked worktree.** All three families resolve the anchor before
  digesting and probe the canonical common dir; existing tests
  (`test_symlinked_root_resolves_to_same_lock_path`,
  `test_lock_path_is_shared_by_every_worktree_of_one_repository`) pin this and must stay green.
- **Relative anchor / different working directory.** Resolution happens inside the helper, so
  the path does not depend on the process CWD (pinned by
  `test_lock_path_does_not_depend_on_the_working_directory`).
- **Windows.** `os.path.normcase` is the identity on POSIX and lower-cases plus
  backslash-normalises on Windows; the digest is UTF-8 over the normcased string. The
  existing golden test is POSIX-only for that reason; the helper keeps the same expression.
- **A caller that already resolved and degraded the common dir.** It passes `common_dir=`, and
  the helper performs no git probe, so the status family's historical degrade
  (`.git` → `.kittify` → `.spec-kitty`) is preserved without the helper knowing about it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One owner of the rule | As a maintainer, I want `kernel.locks.anchored_lock_path(anchor, *, common_dir, probe_dir, subdirectory, prefix, suffix, digest_algorithm, digest_hex_length)` to own resolve → `normcase` → digest → `<common dir>/spec-kitty-locks[/<subdir>]/<prefix><digest><suffix>`, with a documented `__all__` export, so that one place decides the anchored lock path. | High | Open | build | no |
| FR-002 | Event-log lock routes through it | As a maintainer, I want `kernel.event_log_append.event_log_lock_path` to call the helper (probe in the anchor's parent, subdir `event-logs`, sha256[:32]) and to keep its sibling `<anchor>.event-log.lock` fallback and its `EventLogLockUnavailableError` refusal, so that its path and its refusals are unchanged. | High | Open | build | no |
| FR-003 | Synthesis lock routes through it | As a maintainer, I want `charter.activation.synthesizer.synthesis_lock.synthesis_lock_path` to call the helper (probe the root, subdir `charter-synthesis`, sha256[:32]) and to keep its `<root>/.kittify/runtime/locks/charter-synthesis.lock` fallback and its `SynthesisLockUnavailableError` refusal, so that its path and its refusals are unchanged. | High | Open | build | no |
| FR-004 | Checkout-claim lock routes through it | As a maintainer, I want `specify_cli.status.locking._checkout_claim_lock_path` to call the helper with `digest_algorithm="sha1"`, `digest_hex_length=16`, `prefix="__checkout-"`, `suffix="__.status.lock"` and its own degraded common dir, so that its lock file name stays byte-identical (no migration, `_is_checkout_claim_lock_key` unchanged) and its never-raise degrade is preserved. | High | Open | build | no |
| FR-005 | Contract pinned by value | As a reviewer, I want tests that assert the literal path for each of the three shapes, the same digest for one anchor across the event-log and synthesis shapes, the sha1/16 shape, no git probe when `common_dir` is given, the probe directory being the one passed, and `ValueError` on a bad algorithm or length, so that a drift in the helper or in a caller fails CI. | High | Open | build | no |
| FR-006 | No fourth copy | As a maintainer, I want a source-shape gate that fails when a module under `src/` other than `kernel/locks.py` both names a file under `LOCK_DIRECTORY` and digests a path, so that a hand-rolled copy is caught by CI instead of by review. | High | Open | build | no |
| FR-007 | Non-anchor locks say why | As a reader, I want the docstrings of `feature_status_lock_path`, `project_event_log_lock`, `event_log_lock_path`, `synthesis_lock_path` and the helper to name the single owner and, where a builder does not use it, to say why (not anchor-keyed / different naming rule), so that the next reader does not re-open the question. | Medium | Open | build | no |
| FR-008 | Docs name the owner | As a maintainer or the Java write-service author (#6193), I want `docs/architecture/event-ledger-writers-and-readers.md` and `docs/development/reference/lock-interop-spike.md` to point at `kernel.locks.anchored_lock_path` as the one implementation of the rule, with the contract text (sha256 of `normcase(resolved)` under `spec-kitty-locks/event-logs`) unchanged, so that the documented contract and the code have one named owner. | Medium | Open | build | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour preservation | Every existing assertion about these three lock paths stays green **unchanged**: zero edits to `tests/kernel/test_event_log_append.py`, `tests/charter/synthesizer/test_synthesis_lock.py`, `tests/status/test_checkout_claim_lock.py` and `tests/status/test_journal_lock_unification.py` (baseline 66 passed, 2 skipped), so a red there is a behaviour change, not a test adjustment. | Reliability | High | Open |
| NFR-002 | No new probe cost | A lock-path call performs at most one `git rev-parse` (through the existing `lru_cache`d `git_common_dir`) and zero when `common_dir` is given; no new subprocess, network or filesystem write is added to a lock-path computation. | Performance | High | Open |
| NFR-003 | Quality gates | Touched code passes `ruff check`, `ruff format --check` and `mypy` with no new `# type: ignore`; cyclomatic complexity stays at or below 15 (`anchored_lock_path` is a single linear function); diff coverage on changed lines is at least 90%. | Maintainability | High | Open |
| NFR-004 | Kernel tier integrity | `kernel.locks` keeps only stdlib and intra-kernel imports (adding `kernel.git_topology` is allowed; `charter`/`specify_cli` imports are not), so the kernel stays the lowest tier. | Architecture | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Lock names are frozen | No lock file name or path may change: the event-log golden digest `5d011f83a018c89fa185a10c696c8293` and the checkout-claim `__checkout-<sha1[:16]>__.status.lock` name are contract. No lock migration, no re-lock. | Technical | High | Open |
| C-002 | Blast radius | Only `src/kernel/locks.py`, the three family modules, the new/changed tests and the two doc pages listed in FR-008 are touched. `feature_status_lock_path`, `project_event_log_lock`, `review/verdict_commit_queue.py` and `design/receipts.py` keep their current construction. | Technical | High | Open |
| C-003 | Fallbacks stay with their family | The non-git fallback and the git-unavailable policy of each family stay in that family; the helper propagates `kernel.git_topology` errors rather than deciding. | Technical | High | Open |
| C-004 | `__all__` convention | `kernel.locks.__all__` gains the new symbol, and it has at least one caller under `src/` (the three families), as `tests/architectural/test_no_dead_symbols.py` requires. | Technical | Medium | Open |
| C-005 | No changelog entry | The change is internal: no user- or operator-visible behaviour, lock name, error code or message changes, so no `[Unreleased]` entry is added (the `docs/changelog/CHANGELOG.md` style is user-facing). The reason is recorded in `plan.md` and the PR body. | Business | Medium | Open |
| C-006 | Terminology | Say "Mission", never "feature", in new prose; use the existing vocabulary ("anchor", "lock family", "common dir") rather than inventing synonyms. | Business | Medium | Open |

### Key Entities

- **Anchor**: the path a lock family keys on — a log, a log family directory, a worktree root,
  or a write checkout. Its resolved, case-normalised form is the digest input.
- **Lock family**: one `<subdir>`/name shape under `<git-common-dir>/spec-kitty-locks/`, with
  its own fallback and refusal policy (`event-logs`, `charter-synthesis`, `__checkout-…__.status.lock`).
- **Common dir**: the repository `.git` shared by a checkout and all its worktrees, resolved by
  `kernel.git_topology.git_common_dir`; a family may supply it already degraded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the base commit `512567ee`, the new contract tests and the source-shape gate fail (helper absent; gate names three copies); on the branch head they pass. — build · no-op passable: no
- **SC-002**: The four existing family test modules are green with zero edits (≥66 passed, 2 skipped) and the three family path functions produce byte-identical paths before and after the change. — build · no-op passable: no
- **SC-003**: Re-adding one hand-rolled copy of the digest-and-join in a family module makes the FR-006 gate fail, and deleting the helper call in any family leaves that family's own test red. — build · no-op passable: no
- **SC-004**: Diff coverage on changed lines is at least 90%, and `ruff`, `ruff format --check` and `mypy` are clean on the touched files. — build · no-op passable: no
