# Mission Specification: Local Write-Safety Hardening

**Mission Branch**: `fix/local-write-safety`
**Created**: 2026-09-20
**Status**: Draft
**Input**: Close a family of local write-safety defects surfaced by cold-start QA and two adversarial squads: symlink-hijack file truncation via shared-temp paths (#4756, #4721), lost concurrent decision records (#4757), destruction of operator-authored `.kittify/` content on re-init (#4759), credential/prompt files briefly world-readable and symlink-hijackable (#4812, #4760, #4721), and a hand-rolled lock outside the canonical authority (#4811).

**Source tickets**: #4756 (P0), #4757 (P0), #4721 (P1), #4759 (P1), #4760 (P2), #4811 (P3), #4812 (P3).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No command can be tricked into destroying an unrelated file (Priority: P1)

An operator runs Spec Kitty on a shared multi-user machine. Another local user has pre-planted a symlink at a predictable path Spec Kitty writes to (a lock, the cold-install sentinel, the prompt temp dir, a credential temp file, or the mission-state lock). Spec Kitty must not follow that symlink and truncate/overwrite the target; it must refuse the unsafe operation.

**Why this priority**: P1 — local privilege/data-destruction (#4756, #4721). A routine command silently zeroing a victim-writable file and reporting success is the highest-severity item.

**Independent Test**: For **each** path in the surface individually, plant a symlink pointing at a file with known bytes, run the operation, and assert the target's bytes are unchanged **and** the command exits non-zero.

**Acceptance Scenarios**:

1. **Given** a symlink planted at the cold-install lock path pointing at a victim file, **When** the operator runs `spec-kitty init`, **Then** the victim's bytes are unchanged and the command refuses (does not exit 0).
2. **Given** a symlink planted at the prompt temp path (#4721) or a credential temp path (#4812/#4760), **When** that path is written, **Then** the write refuses to follow the symlink and the pointed-at file is untouched.
3. **Given** the shared-temp coordination and prompt locations, **When** any other local user can predict/pre-create them, **Then** Spec Kitty no longer places a writable/truncatable file there under a cross-user-guessable name.

---

### User Story 2 - Concurrent mission activity never loses decision records (Priority: P1)

Several agents advance the same mission at once, opening/resolving decision points concurrently. Every decision in the event log must also appear in the decision index; the two must never silently disagree.

**Why this priority**: P1 — data-integrity (#4757). A dropped index entry corrupts decision history with no error and no repair path today.

**Independent Test**: A **red-first, barrier-synchronized** concurrency proof — N=8 workers released simultaneously, repeated across iterations, that demonstrably fails without the fix — asserts the index has exactly 8 entries matching 8 event-log records. Separately, seed a diverged corpus (log=8, index=5) and assert the repair path rebuilds the index to 8.

**Acceptance Scenarios**:

1. **Given** 8 barrier-synchronized concurrent decision opens with distinct keys, **When** they complete, **Then** the index contains all 8 entries, each 1:1 with a decision-opened event, across repeated runs.
2. **Given** a mission whose index has fewer entries than its decision event log, **When** the operator runs the repair path, **Then** the index is rebuilt from the event log and the two agree (and the repair is a safe no-op when they already agree).

---

### User Story 3 - Shared temp/prompt paths are per-user and confidential (Priority: P1)

Prompt files and cold-install coordination currently live at world-shared, predictable paths under the system temp dir, readable by other local users and pre-plantable. They must live under a per-user root, be created owner-only, and never be world-readable even briefly.

**Why this priority**: P1 — #4721 combines the symlink hazard of US1 with cross-user DoS and information disclosure (prompt content, and 0644-then-chmod credential windows). It outranks the P3 siblings.

**Independent Test**: Assert the prompt temp directory and cold-install sentinel resolve under the per-user runtime root (`~/.spec-kitty`), the runtime root is `0700`, and no prompt/credential file is ever observable at a mode broader than `0600`.

**Acceptance Scenarios**:

1. **Given** any prompt-writing command, **When** it creates its temp directory, **Then** the directory resolves under `~/.spec-kitty` (not world-shared temp) and is owner-only.
2. **Given** a credential or prompt file is written, **When** its mode is inspected at any instant, **Then** it is never broader than `0600` (created restricted, not chmod'ed after a world-readable window).

---

### User Story 4 - Re-running init never destroys operator-authored content (Priority: P2)

An operator has custom missions and memory notes under `.kittify/` but `config.yaml` is absent. Re-running `spec-kitty init` must not delete that content at **any** of its destructive-removal sites — it must back it up first and report where.

**Why this priority**: P2 — data-safety (#4759). Destroys operator work silently, but needs a specific precondition.

**Independent Test**: For **each** init destructive-removal site (≥3), create operator-authored `missions/`+`memory/` with known bytes and no `config.yaml`, run that path, and assert the content is present in a reported backup location (nothing deleted).

**Acceptance Scenarios**:

1. **Given** a `.kittify/` with operator `missions/`+`memory/` but no `config.yaml`, **When** init re-runs, **Then** that content is moved to a timestamped `.kittify/.backup-<timestamp>/` before scaffolding and the backup path is reported.
2. **Given** the same state, **When** init completes, **Then** no operator-authored file is removed without a recoverable backup at any destructive site, and init does not treat the project as blank solely because `config.yaml` is missing.

---

### User Story 5 - Credential writes are safe by construction across all transports (Priority: P2)

Every credential-writing path (hosted/Zeitgeist and tracker) must create its file owner-only and symlink-safe — never world-readable, never following a planted symlink.

**Why this priority**: P2 — closes the "credential 0600-by-construction" class fully (#4812 P3 + #4760 P2). Zeitgeist and auth are already correct; tracker (0644-then-chmod) and the zeitgeist temp-write (no O_NOFOLLOW) are the remaining holdouts.

**Independent Test**: For both the Zeitgeist and tracker credential paths, assert the file is created at mode `≤0600` (no post-hoc chmod window) and a planted symlink at the temp/target path is refused.

**Acceptance Scenarios**:

1. **Given** a credential write on either transport, **When** the file is created, **Then** it is owner-only from creation with no world-readable window.
2. **Given** a symlink planted at a credential temp path, **When** credentials are written, **Then** the write refuses to follow it.

---

### User Story 6 - The mission-state lock is canonical and safe (Priority: P3)

The mission-state migration lock must be symlink-safe and go through the one canonical locking authority rather than a hand-rolled primitive.

**Why this priority**: P3 — class-closure (#4811); lower risk (user-owned dir) but a canonical-source violation and latent instance.

**Independent Test**: Assert the mission-state lock is acquired through the canonical locking authority and does not follow a symlink at the lock path.

**Acceptance Scenarios**:

1. **Given** the mission-state migration lock, **When** acquired, **Then** it routes through the canonical locking authority and does not follow a symlink.

### Edge Cases

- Lock path already exists as a **regular** legitimate lock file (normal re-acquisition) → must keep working; the symlink guard must not break ordinary reuse.
- **Windows**, where the no-follow flag is unavailable → degrade safely to current semantics without regressing existing lock tests (see NFR-001 POSIX scoping).
- Init backup target `.kittify/.backup-<timestamp>/` already exists (two re-inits in one second) → must not collide/overwrite an earlier backup.
- Decision-index repair against an already-agreeing index → safe no-op.
- Only some of `missions/`/`memory/`/`templates/` present on re-init → operator-authored subtrees preserved; regenerable scaffold (`templates/`) may be replaced.
- Tests for relocated paths must use the **isolated per-worker HOME**, never the real `~/.spec-kitty`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Symlink-safe lock acquisition | Lock acquisition must never follow a symlink at the lock path, so no command can be induced to write through or truncate an unrelated file. (Source: #4756) | High | Open |
| FR-002 | Cold-install coordination per-user | Cold-install coordination must resolve under the per-user runtime root, not a world-shared cross-user-predictable temp location. (Source: #4756) | High | Open |
| FR-003 | Hijack attempts fail closed | A detected symlink-hijack attempt must abort with a clear error, never silently succeed. (Source: #4756, #4721) | High | Open |
| FR-004 | Decision RMW serialized at service level | Concurrent decision opens/resolves must be serialized across the full service-level read-modify-write of the index (not merely the store write), so no entry is dropped and the index always agrees with the event log. (Source: #4757) | High | Open |
| FR-005 | Decision-index repair from event log | An operator can rebuild a diverged decision index from the authoritative event log; repair is a safe no-op when they already agree. (Source: #4757) | High | Open |
| FR-006 | Init preserves operator content at every site | Every init destructive-removal site that can delete operator-authored `missions/`/`memory/` must back that content up (timestamped `.kittify/.backup-<ts>/`, reported) before scaffolding — never rmtree it. (Source: #4759) | High | Open |
| FR-007 | Init detects operator content beyond config.yaml | The "already initialized" check must recognize operator-authored content, not rely solely on `config.yaml`. (Source: #4759) | High | Open |
| FR-008 | Mission-state lock canonical and safe | The mission-state lock must be symlink-safe and route through the canonical locking authority. (Source: #4811) | Low | Open |
| FR-009 | Credential writes safe by construction | Credential files on all transports (Zeitgeist and tracker) must be created owner-only (`≤0600`, no post-hoc chmod window) and symlink-safe. (Source: #4812, #4760) | Medium | Open |
| FR-010 | Prompt temp dir per-user and confidential | Prompt temp files must resolve under the per-user runtime root, be symlink-safe, and never be world-readable. (Source: #4721) | High | Open |
| FR-011 | Single owner of the runtime root | The per-user runtime root (`~/.spec-kitty`) must be created/owned `0700` by a single canonical creator, not left order-dependent across callers. (Source: #4756, #4760, #4721) | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No cross-user write-through (POSIX) | On POSIX shared hosts, across the full surface (lock / cold-install sentinel / mission-state lock / credential temp-writes / prompt temp), a symlink planted by another local user yields 0 successful truncations or write-throughs. Windows degrades to current semantics (residual risk accepted; the class is POSIX shared-temp). | Security | High | Open |
| NFR-002 | Concurrency loss-free (proven) | Under a red-first, barrier-synchronized N=8 concurrent decision-open proof repeated across iterations, the index retains all 8 entries matching 8 event-log records (1:1); 0 dropped. The proof must fail without the fix. | Reliability | High | Open |
| NFR-003 | No silent operator-content loss | 100% of operator-authored `missions/`/`memory/` bytes recoverable from a reported backup after any init re-run, at every destructive site; 0 silent deletions. | Reliability | High | Open |
| NFR-004 | Lock-authority compatibility | The change to the canonical locking authority preserves all existing lock-consumer behaviors and lock re-acquisition on POSIX and Windows; the lock-primitive ban gate and all lock-consumer tests remain green. | Compatibility | High | Open |
| NFR-005 | Credential/prompt confidentiality | No credential or prompt file is observable at a mode broader than `0600` at any instant of its lifetime (created restricted, never chmod'ed down after a world-readable window). | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical locking authority | Locking must route through the single canonical locking authority; no new or preserved hand-rolled lock primitives. | Technical | High | Open |
| C-002 | Sequencing with PR #4813 | FR-008 (#4811) shares `migration/mission_state.py` with in-flight PR #4813 and must be based on post-#4813 `main` (hard). FR-005's repair surface must mirror the doctor structure #4813 establishes (soft alignment); FR-005's store lock + reconciler core share no file with #4813 and may proceed now. | Technical | High | Open |
| C-003 | Lock file persistence preserved | Lock files persist across acquisitions; the symlink guard must not be implemented via exclusive-create-and-unlink or anything that breaks legitimate lock re-acquisition. | Technical | High | Open |
| C-004 | One canonical no-follow-open helper | Symlink-safe opens across the credential/mission-state/prompt/sentinel sites should route through a single canonical helper (kernel-level), not hand-rolled `O_NOFOLLOW` per site (canonical-sources / DIRECTIVE_044). | Technical | Medium | Open |
| C-005 | Reuse existing parent-chmod | The runtime-root `0700` guarantee should reuse the canonical lock authority's existing parent-directory chmod rather than introduce a competing `mkdir(0700)`. | Technical | Medium | Open |
| C-006 | Distinct backup vocabulary | FR-006's persistent, operator-reported `.kittify/.backup-<ts>/` must not be conflated with the template-render pipeline's transactional, removed-on-success backup; keep the concepts distinct and named. | Technical | Low | Open |

### Non-Goals *(explicitly out of scope — named so they are not mistaken for in-scope)*

- **#3960** (lockless rollback truncate on coord fallback), **#4003** (`git/ref_advance.py` meta.json raw reads bypass the fail-closed reader), **#2627** (concurrent skills-sync startup race), **#4182** (Windows `os.open` lacks `O_BINARY`) — adjacent classes (lockless write / bypass-canonical-reader / concurrency / os.open flags) on different surfaces; excluded to avoid over-widening.
- **#4305** (`core/file_lock.py` S3516) — likely stale (that file moved to `kernel/locks.py`); flag to triage, not in scope.
- **Pre-existing already-correct hand-rolled `O_NOFOLLOW` sites** (~7: `charter/activation/charter_yaml_io.py`, `coordination/atomic_write.py`, `invocation/writer.py`, `session_presence/writers/markdown_rules.py`, `status/store.py`, `tool_surface/bundles/projection.py`, `upgrade/migrations/m_3_2_8_provision_kitty_env.py`) — these are correct guards, not defects; this mission does not convert them. A codebase-wide "no hand-rolled `O_NOFOLLOW` outside `kernel.no_follow`" ban-gate for true class-closure is a separate deferred item.
- **Auth credential writers** (`auth/secure_storage/file_fallback.py` session-blob/salt, `auth/session_hot_path.py`) — deliberately out of the credential-0600 class: the session blob is AES-GCM ciphertext, the salt is non-secret, and read-side `0600` verification is enforced (NFR-013). The class in scope is the plaintext-secret transports (zeitgeist + tracker).

### Key Entities

- **Machine lock / lock sentinel**: cross-process lock file; must be symlink-safe and, for cold-install, per-user rather than world-shared.
- **Decision index vs decision event log**: the append-only event log is authoritative; the index is a derived projection that must never silently disagree.
- **Operator-authored `.kittify/` content**: custom missions (`missions/`) and memory notes (`memory/`) — must survive re-init via backup.
- **Per-user runtime root (`~/.spec-kitty`)**: single-owner `0700` home for locks, sentinels, prompt temp, and credentials.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For **each** path individually (lock, cold-install sentinel, mission-state lock, Zeitgeist + tracker credential temp, prompt temp), a planted symlink leaves the pointed-at file's bytes unchanged and the command exits non-zero — 0 successful truncations on POSIX.
- **SC-002**: A red-first, barrier-synchronized N=8 concurrent-decision-open proof (repeated) yields an index with exactly 8 entries equal to 8 decision-opened events; a seeded divergence (index=5, log=8) heals to 8==8, and repair on an agreeing corpus is a no-op.
- **SC-003**: After init re-runs over operator `missions/`+`memory/` with `config.yaml` absent, at **every** destructive site (≥3), 100% of that content is present in a reported backup and 0 files are deleted without a recoverable backup.
- **SC-004**: All existing lock-consumer tests (auth, checkout, status, merge, review) and the lock-primitive ban gate remain green on POSIX and Windows after the shared locking-authority change.
- **SC-005**: No credential or prompt file is ever observable at a mode broader than `0600`; `~/.spec-kitty` is `0700`.
- **SC-006**: The cold-install sentinel and prompt temp directory resolve to a per-user path under `$HOME` — either under the runtime root (`~/.spec-kitty`) or a dedicated sibling sharing its parent (e.g. `~/.spec-kitty-cold-install`, kept a sibling so the sentinel's own directory creation is not observed as drift in the managed runtime-root tree) — created `0700`, asserted on the resolved path; never under a world-shared/cross-user-guessable temp location.

## Assumptions

- **A1**: The FR-005 decision-index repair surfaces as a `spec-kitty doctor` subcommand (rebuild index from events), mirroring the `_mission_state_doctor.py` extraction PR #4813 establishes (a new `_decisions_doctor.py`).
- **A2**: The symlink guard uses a no-follow open (platform-guarded to a safe no-op on Windows). Exclusive-create is deliberately **not** added to the shared lock open (breaks legitimate re-acquisition — see C-003).
- **A3**: The cold-install sentinel and prompt temp dir relocate to the per-user runtime root (`~/.spec-kitty`, `0700`), reusing the canonical lock authority's parent-chmod (C-005) rather than a hand-rolled `mkdir`.
- **A4**: A single canonical kernel no-follow-open helper is factored by the #4756 work and consumed by the credential, mission-state, prompt, and sentinel sites (C-004). The architect confirms this factoring at plan; if declined, each site's independence is called out with the hand-rolled-pattern smell noted.

## Work Package Dependency Graph *(planning guidance, finalized at /tasks)*

```
WP01 #4756  kernel no-follow (open_fd + force_release) + canonical helper (C-004) + Windows-noop
            deps: none  — FOUNDATION, lands first, full lock-consumer blast-radius + ban-gate tests
WP01b #4756 cold-install sentinel → ~/.spec-kitty(0700)  [optional split of WP01]
            deps: WP01
WP02 #4757  service-level RMW lock + reconciler + doctor subcommand
            deps: WP01 (hard, inherits no-follow) ; #4813 (soft, mirror doctor pattern — core may start now)
WP03 #4759  init/template backup-then-proceed at every destructive site
            deps: none  — fully parallel
WP04 #4811  mission_state lock → canonical authority
            deps: WP01 (hard, needs hardened primitive) ; #4813 (hard, same file, base post-#4813 main)
WP05 #4812+#4760  credential write-safety (Zeitgeist + tracker): 0600-by-construction + no-follow
            deps: WP01 (via C-004 shared helper)
WP06 #4721  prompt temp dir per-user + no-follow + non-world-readable (+ DoS/info-disclosure facets)
            deps: WP01 (via C-004 shared helper)
```
