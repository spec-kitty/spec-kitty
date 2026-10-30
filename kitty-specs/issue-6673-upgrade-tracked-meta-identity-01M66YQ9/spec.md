# Mission Specification: Upgrade never re-mints a Mission identity that git already holds

**Mission Branch**: `issue-6673-upgrade-tracked-meta-identity`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6673 (refs #6669, #6627). Found by the post-specify adversarial review of the #6669/#6668 Mission and confirmed by running the code.

## Intent Summary

- **Primary actor:** a project owner whose `kitty-specs/<slug>/meta.json` is tracked by git but absent from the working tree — an accidental `rm`, a sparse/partial checkout, or a `git rm` that was never committed.
- **Trigger:** they run `spec-kitty upgrade` (`--yes`) on a project that still has the `2.0.6` and `3.2.0a4` migrations pending (the upgrade path from an older Spec Kitty; on a project that already records those migrations as settled they do not run and it changes nothing — see Out of Scope).
- **Today:** the update treats the folder as an identity-less Mission. `2.0.6_residue_safe_consistency_sweep` writes a baseline `meta.json` rebuilt from the directory name, and `3.2.0a4_normalize_mission_lifecycle` then mints a **fresh** ULID into it. Reproduced on current `main`: committed `mission_id: 01REALMISZZZZZZZZZZZZZZZZZ`, `rm kitty-specs/<slug>/meta.json`, `spec-kitty upgrade --yes` → the working tree got `01M66YHMT428T99C8H860FJ2YH`. One `git add -A` later and the Mission has a second identity in history; every event, lane and status row keyed on the old `mission_id` is orphaned.
- **Desired outcome:** a Mission's identity is never invented while git holds one. The upgrade either rebuilds the `meta.json` from the content git holds (so the Mission keeps the identity its history uses), or — when that content cannot be read — leaves the Mission alone and says exactly how to put it back.
- **Rule that must always hold:** after an upgrade, no Mission's `mission_id` differs from the `mission_id` git holds for it, and no Mission folder that git tracks a `meta.json` for is left carrying a `meta.json` that git never had.

**Boundary.** This mission changes every `upgrade` seam that can write a `meta.json` for a Mission whose tracked copy is absent from the working tree, and the identity backfill they call. Three seams do: the `2.0.6` consistency sweep's baseline repair, the `3.2.0a4` lifecycle normalization's identity backfill, and the `3.2.6rc1` runtime-state cutover, whose phase flip writes a one-key `meta.json` stub when the file is missing (proven on current `main` with a scratch repository). The `doctor mission-state --fix` repair (`migration/mission_state.py`) is a different entry point with its own contract (it rebuilds state from the event log, and `upgrade` no longer runs it — #5811/#6543); it is out of scope here and gets a follow-up reference rather than a second fix.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deleted tracked `meta.json` comes back with its own identity (Priority: P1)

A project owner is on an older Spec Kitty, so the `2.0.6` sweep and the `3.2.0a4` normalization are both pending. A Mission's `meta.json` is committed, but the file is missing from the working tree (an accidental `rm`). They run `spec-kitty upgrade --yes`. The upgrade takes the Mission's metadata from the copy git holds, writes it back, and the Mission keeps the ULID its history uses.

**Why this priority**: this is the reported defect (#6673), and it silently forks a Mission's identity: every later `git add -A` commits the second identity.

**Independent Test**: in a scratch git repository holding one committed Mission, record the pre-run commit SHA, delete the Mission's `meta.json` from the working tree, run the real `upgrade --yes` CLI in-process, and assert that the file is back and that the `mission_id` equals `git show <pre-run-sha>:kitty-specs/<slug>/meta.json`'s. (The upgrade auto-commits, so `HEAD` after the run is not a safe baseline.)

**Acceptance Scenarios**:

1. **Given** a committed Mission whose `meta.json` is tracked, **When** its working-tree `meta.json` is deleted and the owner runs `spec-kitty upgrade --yes`, **Then** the file exists again and its `mission_id` is the tracked one (not a fresh ULID).
2. **Given** the same fixture, **When** the upgrade finishes, **Then** it reports that the tracked `meta.json` was missing from the working tree and where it came from, and the `mission_id` in the upgraded `meta.json` is the only identity the Mission ever had.
3. **Given** a Mission whose `meta.json` was restored this way, **When** the owner runs `spec-kitty upgrade --yes` again, **Then** nothing under `kitty-specs/` changes and the identity is still the tracked one.
4. **Given** a working tree whose `meta.json` exists but has lost its `mission_id` (an earlier build wrote a baseline over it, uncommitted), and whose tracked copy still holds the id, **When** the owner runs the upgrade, **Then** the present copy regains the tracked `mission_id` instead of a freshly minted one.

---

### User Story 2 - An unreadable tracked `meta.json` is refused, not fabricated (Priority: P1)

The tracked `meta.json` exists in git, but its content cannot be read (the committed blob is not valid JSON, or git cannot produce it). The upgrade refuses to treat the folder as an identity-less Mission: it writes no `meta.json` for it, mints nothing, and names the exact command that puts the tracked file back.

**Why this priority**: the refusal is the other half of the same invariant. "Restore" and "refuse" must be the only two outcomes; a degraded read must never fall through to the fabricating path.

**Independent Test**: with the same scratch-repository fixture, commit a `meta.json` whose bytes are not a JSON object, delete the working-tree copy, run `upgrade --yes`, and assert that no `meta.json` was written for that Mission by **any** migration in the run (the phase flip included), that the output carries the actionable restore command, and that no ULID was minted into the folder.

**Acceptance Scenarios**:

1. **Given** a Mission whose tracked `meta.json` is corrupt in git and absent on disk, **When** the owner runs `spec-kitty upgrade --yes`, **Then** no `meta.json` is written for that Mission and no new identity appears anywhere under its folder.
2. **Given** that run, **When** the owner reads the upgrade output, **Then** it names the Mission's `meta.json` path and the `git checkout -- <path>` command that restores it.
3. **Given** a `meta.json` that git tracks only in the index (staged, never committed) and that is missing from the working tree, **When** the owner runs the upgrade, **Then** the refusal text says exactly that — the file is in the index, not in a commit — instead of claiming git holds no copy.

---

### User Story 3 - A pre-identity Mission is still repaired (Priority: P2)

A pre-identity Mission is tracked by `spec.md` only; its `meta.json` was never committed. The upgrade still writes a baseline `meta.json` and backfills an identity, exactly as before.

**Why this priority**: the fix keys on "git holds a `meta.json` for this path". If that test is too broad it turns the legitimate legacy repair into a refusal, which would be a worse regression than the defect.

**Independent Test**: the committed-legacy-Mission control from the #6669 fixture (tracked `spec.md`, no `meta.json`, tracked `tasks/doing/` lane file) still gets a `mission_id` and its lane file flattened after the upgrade.

**Acceptance Scenarios**:

1. **Given** a Mission with a tracked `spec.md` and no `meta.json` in the working tree or in git, **When** the owner runs `spec-kitty upgrade --yes`, **Then** a baseline `meta.json` is written and a `mission_id` is minted for it, as today.
2. **Given** the same command on a repository whose `HEAD` is still unborn (a brand-new project), **When** a Mission lacks a `meta.json` on disk and git has no commit to read it from, **Then** the update does not refuse: it repairs the folder the way it did before this mission.

---

### Edge Cases

- **Residue folder:** a `kitty-specs/<name>/` folder that git does not recognise as a Mission keeps its #6627/#6669 behaviour (no `meta.json`, no identity, one notice) — this mission must not weaken that.
- **`meta.json` staged but never committed, then deleted:** git tracks the path in the index while `HEAD` holds no copy. The identity in git is not history's identity, so the update refuses with the restore command instead of minting (the same refusal branch as User Story 2), and the notice says the copy is in the index.
- **Present but identity-less `meta.json`:** a working-tree copy that parses but has no `mission_id`, while the tracked copy has one, regains the tracked `mission_id`; every other field of the present copy is left alone.
- **Runtime-state cutover:** the phase flip must not create a `meta.json` for a Mission the sweep refused; a Mission whose `meta.json` is absent from disk and tracked is not cut over at all.
- **The Mission's `meta.json` is present on disk:** untouched; the tracked content is only consulted when the working-tree copy is absent.
- **Nested checkout (a project inside a larger repository):** the tracked copy is read for the project's own path, not for a same-named path elsewhere.
- **No git, or a folder outside a work tree:** nothing is tracked, so the pre-existing repair applies unchanged.
- **Worktrees:** a Mission folder inside a lane worktree is judged against that worktree's own git view.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Restore the tracked identity | As a project owner, I want the upgrade to take a missing `meta.json` from git so that the Mission keeps the identity its history uses. | High | Open | [build] | no |
| FR-002 | Never mint over a tracked identity | As a maintainer, I want the upgrade's identity-minting seams to refuse to write an identity when git already holds one for that Mission — including when the working-tree copy has lost it — so that no second identity is ever created. | High | Open | [build] | no |
| FR-003 | Refuse an unreadable tracked meta | As a project owner, I want the upgrade to skip a Mission whose tracked `meta.json` cannot be read, and to name the command that restores it so that I can fix it myself. | High | Open | [build] | no |
| FR-004 | Keep repairing pre-identity Missions | As a maintainer, I want a Mission with no `meta.json` anywhere in git to be repaired exactly as before so that the legacy upgrade path does not regress. | High | Open | [ratchet] | no — paired with FR-001/FR-003 on one fixture (the same run must restore one Mission and still backfill another) |
| FR-005 | Tell the owner the file came from git | As a project owner, I want the upgrade output to say that a tracked `meta.json` was missing from the working tree and was rebuilt from git so that an undone deletion is never silent. | Medium | Open | [build] | no |
| FR-006 | Identity backfill refuses a tracked-but-absent meta | As an operator, I want `backfill_mission` to skip and explain instead of minting when the `meta.json` it is asked to repair is tracked but absent on disk so that no second entry point can fork an identity. | Medium | Open | [build] | no |
| FR-007 | One reader owns the answer | As a maintainer, I want exactly one function to answer "what does git hold for this Mission's `meta.json`" so that the sweep, the normalization, the cutover and the backfill cannot drift apart. | Medium | Open | [build] | no |
| FR-008 | The cutover leaves a refused Mission alone | As a maintainer, I want the runtime-state cutover to skip a Mission whose tracked `meta.json` is absent from the working tree, so that no migration in the upgrade run writes a `meta.json` git never had for it. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Extra git reads stay bounded | A Mission whose `meta.json` is on disk costs zero extra git reads. For an affected Mission the extra reads are O(1) per seam, never O(files); on a healthy project the upgrade issues no new git read at all. | Performance | High | Open |
| NFR-002 | Failure is honest | A git failure while reading the tracked copy never turns into a minted identity; it becomes either the refusal branch (FR-003) or, when git cannot read the path at all and tracks nothing, the pre-existing repair (FR-004). No `except` handler swallows the error into a fabricated value, and a git timeout is re-raised rather than degraded (the `probe_tracked_mission_paths` policy). | Reliability | High | Open |
| NFR-003 | No new warnings on healthy projects | On a project whose Missions all have their `meta.json` on disk, the upgrade emits no new warning lines and changes no file under `kitty-specs/`. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Shipped migrations stay byte-frozen | `2.0.6_consistency_sweep` and every other shipped migration module is not edited (its bytes are its `content_hash`); the fix lands in live shared helpers and in the residue-safe successor. | Technical | High | Open |
| C-002 | `meta.json` keeps one writer | All writes still go through `mission_metadata.write_meta` under the Mission write lock; the new reader is read-only. | Technical | High | Open |
| C-003 | Kernel git stays the path owner | The tracked-copy read asks `kernel.git` (`blob_at`, `is_tracked`) and never builds a path-listing argv or splits git output itself. | Technical | High | Open |
| C-004 | `doctor mission-state --fix` is out of scope | The mission-state repair's identity derivation is a different entry point (not run by `upgrade` since #5811); this mission does not change it and records the remaining gap as a follow-up. | Technical | Medium | Open |
| C-005 | Seams are primed before any write | A path whose git read can fail (timeout) is read once per run for every affected Mission *before* the first repair write, so a mid-walk timeout cannot abort after earlier Missions were repaired (the #6669 successors' priming rule). | Technical | High | Open |

### Key Entities *(include if the mission involves data)*

- **Tracked `meta.json`**: the copy of a Mission's metadata that git holds for the Mission's path — the index copy when the path is staged, else `HEAD`'s. It is the authority on `mission_id` when the working tree has lost the file.
- **Mission identity (`mission_id`)**: the immutable ULID that keys a Mission's events, lanes and status rows. Writing a second one does not rename the Mission; it forks it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reproduction fixture, the `mission_id` after `upgrade --yes` equals the one `git show <pre-run-sha>:kitty-specs/<slug>/meta.json` holds, for every fixture shape (deleted, sparse-style skip-worktree) — [build] · no-op passable: no
- **SC-002**: On the unreadable-committed-meta fixture, zero `meta.json` files are written for that Mission by any migration in the run, and the output contains its restore command — [build] · no-op passable: no
- **SC-003**: The committed-legacy-Mission control (tracked `spec.md`, no `meta.json` in git) still receives a `mission_id` in the same upgrade run — [ratchet] · no-op passable: no — positive control for SC-002 on the same fixture
- **SC-004**: On a project with no missing `meta.json`, the upgrade's warning output and `kitty-specs/` file set are identical to the current `main` behaviour — [ratchet] · no-op passable: no
- **SC-005**: Every changed line of the fix is covered by a test (the diff-cover gate stays at or above its 90% floor) — [ratchet] · no-op passable: no

## Out of Scope

- The `doctor mission-state --fix` / `migrate normalize-mission` repair (`migration/mission_state.py::_canonicalize_meta`), which derives a deterministic identity when a folder has no metadata at all. Different entry point, different contract (C-004).
- Sparse-checkout repair itself (`spec-kitty doctor sparse-checkout --fix`) and any change to where git stores what.
- Residue classification (#6627/#6669): this mission only has to leave it alone.
- Automatic commits: the fix does not change what the upgrade auto-commits, beyond not writing a fabricated `meta.json` in the first place.
- An always-run preflight notice on a project whose `2.0.6`/`3.2.0a4` migrations are already settled: on such a project nothing writes a `meta.json` for the missing one, so the Mission is not damaged and stays silent. Restoring it there is a `git checkout -- <path>` the operator already has. If the maintainers want a `doctor` check for it, that is a follow-up, not this fix.
