# Mission Specification: Nightly reds B (2026-10-04)

**Mission Branch**: `kitty/nightly-reds-b-2026-10-04`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief: make the stress (#5610), integration (#5611) and integration-slice (#5612) nightly suites green for a reason that can be named, or prove a red is intentional. Evidence run: https://github.com/spec-kitty/spec-kitty/actions/runs/37177460494 (head `b2c466d7d1`, no newer nightly as of 2026-10-04).

Root-cause evidence for every row lives in [`research/nightly-red-memo.md`](research/nightly-red-memo.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The nightly stress suite proves concurrent status emits again (Priority: P1)

A maintainer reading the nightly sees the stress suite exercise 20 concurrent bookkeeping transactions against a coordination Mission shaped the way `mission create` shapes one, and pass.

**Why this priority**: the stress suite is the only proof that the per-Mission status lock serializes real OS processes; while its fixture is malformed it proves nothing.

**Independent Test**: run `tests/stress/test_concurrent_emits.py`; both tests pass, and the fixture's `mid8` equals `mission_id[:8]` with a `meta.json` that declares the coordination branch.

**Acceptance Scenarios**:

1. **Given** a repository with a coordination branch and a Mission `meta.json` declaring it, **When** 20 processes each run `acquire → append_event → commit`, **Then** all 20 succeed and the event log holds 20 unique valid events.

---

### User Story 2 - Integration oracles track the coordination single-home contract (Priority: P1)

A maintainer sees the integration suite pin the coordination single-home behavior that commit `5b5699e50` shipped on purpose (create seeds the coordination status log; the executor resolves its STATUS directory through the write accessor; the shared read-handle canonicalizer adds two `get_main_repo_root` reads), instead of the pre-change behavior.

**Why this priority**: these three tests went red on the nightly the day the change landed; until they are re-pinned they hide any real regression in the same seams.

**Independent Test**: run the three named integration node ids; they pass and each still asserts the guarantee it protected (surface placement, coordination-aware STATUS directory, exact post-mint ledger).

**Acceptance Scenarios**:

1. **Given** a COORD Mission created by `create_mission_core`, **When** the golden-path test inspects the coordination status log, **Then** it finds the seeded log already committed rather than committing an empty one itself.
2. **Given** a coordination Mission with a husk worktree, **When** the executor resolves its STATUS directory, **Then** the spy on the write accessor captures the coordination directory and `read_dir(STATUS_STATE)` is not called.
3. **Given** an owned finalize, **When** post-mint `get_main_repo_root` reads are counted, **Then** they equal the re-pinned exact ledger.

---

### User Story 3 - `agent config sync --create-missing` restores a missing Mistral Vibe pointer (Priority: P1)

An operator whose `.vibe/config.toml` pointer is missing runs the recovery command that `init` recommends and gets the pointer back, without the pinned command-skill manifest being rewritten.

**Why this priority**: it is a user-visible product regression; the documented recovery command silently does nothing.

**Independent Test**: `tests/init/test_init_idempotent.py::test_initialized_clone_vibe_pointer_recovery_and_repeat` passes, and the manifest-pinning tests in `tests/specify_cli/cli/commands/test_agent_config.py` still pass.

**Acceptance Scenarios**:

1. **Given** an initialized clone with the vibe skills installed and `.vibe/config.toml` deleted, **When** the operator runs `spec-kitty agent config sync --create-missing --keep-orphaned`, **Then** `.vibe/config.toml` exists again and a repeat run reports no changes.

---

### User Story 4 - The nightly integration slice runs in the environment it was written for (Priority: P2)

A maintainer sees the integration slice pass on the runner: the corpus-recovery suite can read its pinned historical commit, the repo-root status-guard self-test parses pytest's CI-mode summary lines, and the `implement --recover --json` characterization runs against a materialized coordination worktree.

**Why this priority**: these reds are harness defects first surfaced by the new slice; they do not indicate product breakage but they mask any real signal from the slice.

**Independent Test**: run the named node ids with `CI=true` and from a `--depth 1` clone where relevant.

**Acceptance Scenarios**:

1. **Given** the nightly `integration-slice` job, **When** it checks out the repository, **Then** it fetches full history, like every other job that runs the corpus-recovery suite.
2. **Given** `CI=true` in the environment, **When** the status-guard self-test parses the nested pytest summary, **Then** an `ERROR <nodeid> - <message>` line counts as an error for that node id.
3. **Given** a coordination Mission whose coordination worktree is materialized, **When** `implement --recover --json` runs with no crashed sessions, **Then** it exits 0 with the success envelope.

### Edge Cases

- A coordination Mission whose PRIMARY dir is a bare slug (no `-<mid8>` suffix): out of scope here; see C-004 and the memo.
- A summary line without the CI-mode message suffix (local runs) must still parse.
- A repeat `agent config sync` after the pointer is restored must not report a change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Stress fixture is a well-formed coordination Mission | As a maintainer, I want the concurrent-emit stress fixture to declare its coordination branch in `meta.json` and use `mid8 == mission_id[:8]` so that the stress suite exercises the real coordination write path. | High | Open | [ratchet] | no |
| FR-002 | Golden-path oracle accepts the create-time coordination seed | As a maintainer, I want the placement golden-path COORD case to assert the seeded coordination status log instead of committing an empty one so that it pins the intended create-time seed. | High | Open | [ratchet] | no |
| FR-003 | Executor STATUS directory is observed through the write accessor | As a maintainer, I want the coordination-read residuals proof to spy on `write_dir(STATUS_STATE)` and assert `read_dir(STATUS_STATE)` is not used so that it still proves the STATUS leg stays coordination-aware. | High | Open | [ratchet] | no |
| FR-004 | Owned-finalize ledger re-pinned to the shared canonicalizer | As a maintainer, I want the exact post-mint `get_main_repo_root` ledger to carry the two reads the shared read-handle canonicalizer added, with a dated rationale, so that the ledger stays exact. | High | Open | [ratchet] | no |
| FR-005 | Vibe pointer recovery | As an operator, I want `agent config sync --create-missing` to restore a missing `.vibe/config.toml` for an already-installed vibe agent so that the recovery `init` recommends works. | High | Open | [build] | no |
| FR-006 | Recover characterization runs on a materialized coordination worktree | As a maintainer, I want the `implement --recover --json` coordination characterization to use a materialized coordination worktree, as `mission create` produces, so that it characterizes the success envelope rather than the intended fail-closed refusal. | Medium | Open | [ratchet] | no |
| FR-007 | Status-guard self-test parses CI-mode summary lines | As a maintainer, I want the nested-pytest summary parser to accept the ` - <message>` suffix pytest appends when `CI` is set so that the self-test holds on CI runners. | Medium | Open | [ratchet] | no |
| FR-008 | Integration slice checks out full history | As a maintainer, I want the nightly `integration-slice` job to fetch full history so that the corpus-recovery suite can archive its pinned historical commit. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No weakened checks | Zero added retries, skips, xfails, deselections, timeout or budget changes; every pre-existing assertion is kept (only stale literals change, each with a rationale). | Reliability | High | Open |
| NFR-002 | Red-first evidence | Every repaired node id is shown red on `skupstream/main` (`bc8d53d09`) and green on the branch, with commands and counts recorded. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not touch PR #5617's files | No change to any file PR #5617 modifies (notably `tests/_support/shared_build_artifacts.py`). | Technical | High | Open |
| C-002 | Targeted runs only | Tests run by named node id or file, foreground; no directory-wide, nightly-wide or `make test-full` runs. | Technical | High | Open |
| C-003 | No suite-wide harness rework | Anything #5353-sized is reported, not done. | Technical | High | Open |
| C-004 | Bare-slug coordination consolidate is reported, not changed | The `test_explicit_delete_override_still_reachable` red (a coordination Mission whose primary dir lacks the `-<mid8>` suffix cannot consolidate onto a protected target since `5b5699e50`) needs a design decision across the commit router and the reconciliation gate; it stays red and is reported. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/stress/test_concurrent_emits.py` passes 2/2 (red 1/2 on base). — [ratchet] · no-op passable: no
- **SC-002**: The three coordination single-home integration node ids pass (red on base). — [ratchet] · no-op passable: no
- **SC-003**: All 12 integration-slice node ids from run 37177460494 pass locally under the nightly's conditions (`CI=true`; full history for the corpus suite). — [ratchet] · no-op passable: no
