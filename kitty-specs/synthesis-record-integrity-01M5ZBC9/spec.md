# Mission Specification: Synthesis record integrity

**Mission Branch**: `issue-6453-synthesis-record-integrity`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Remediation mission M2 — issues #6453, #6455, #6456 (triage corrections of 2026-10-19 applied). Phase 0 grounding: [research.md](research.md).

## Intent Summary (confirmed 2026-10-27)

- **Primary actor:** an operator or agent running `spec-kitty charter synthesize` or `spec-kitty charter resynthesize` in a project.
- **Trigger and outcome:** a synthesis run writes the project overlay, the synthesis manifest and the created-artifacts record. After this mission, two runs in the same worktree never interleave their writes, an unreadable record tells the operator how to repair it without losing removal memory, and a full run leaves the stored directive link of every artifact it did not regenerate in place.
- **Invariant:** an artifact the operator removed from an activation list stays removed across concurrent synthesis runs; synthesis never re-adds it. (A `charter activate`/`deactivate` racing a synthesis run is a residual tracked in #6719.)
- **Operator decisions:** run-wide lock per worktree, placed in the git common dir (DM `01M5ZBD3K8FQQZ2KFANYVMX0JZ`); a held lock is waited on for about 10 seconds, then the run refuses with a named code and writes nothing (DM `01M5ZBERXGAS37DZCNTPG1WMC0`); a full run strips a legacy `applies` edge only from artifacts it regenerated (DM `01M5ZBDAH1Z51X0W35XMMYPHTY`); `restamp_bundle_hash` also takes the lock, and the other activation writers are filed as #6719 (DM `01M5ZCGGF4N7SWFM9MZF8Y4SBF`).
- **Review squad (post-spec, 2026-10-27):** architect and reviewer findings folded into this revision (lock span, #6443 dead-edge filter, re-pinned tests, injectable timeout, deterministic race, residual scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent synthesis runs never lose created-artifact entries (Priority: P1)

Two synthesis runs start together in one worktree (for example an agent's `charter resynthesize` and an operator's `charter synthesize`). Today each reads the created-artifacts record, merges its own ids and writes it back, so the later write drops the other run's ids. A dropped id lets a later run treat that artifact as new and append it to an activation list the operator had narrowed.

**Why this priority**: it is the only defect of the three that can undo an operator's removal.

**Independent Test**: two writers race on the record; afterwards it holds the union of both runs' ids.

**Acceptance Scenarios**:

1. **Given** a record holding `t1`, **When** two runs record `t2` and `t3` concurrently, **Then** the record holds `t1`, `t2` and `t3`.
2. **Given** another process or thread holds the synthesis lock, **When** a run in the same worktree starts and the lock stays held past the bounded wait, **Then** the run exits non-zero with `CHARTER_SYNTHESIS_LOCK_HELD`, names the lock file, and leaves the overlay, manifest, record and directive files byte-identical (with `--json`, the failure envelope carries the code). Positive control: the same fixture with the lock free succeeds and writes.
3. **Given** an operator removed `t2` from `activated_tactics`, **When** concurrent runs then regenerate `t2`, **Then** `t2` is not re-appended.
4. **Given** a `--dry-run` (or `resynthesize --list-topics`), **When** another run holds the lock, **Then** it completes without waiting (it writes nothing and takes no lock).
5. **Given** a run holding the synthesis lock, **When** `restamp_bundle_hash` runs elsewhere in the same worktree, **Then** it waits for the lock instead of overwriting the manifest the run is writing; if the lock stays held past the bounded wait, the caller's change is kept, the restamp is skipped and one warning line says so (operator decision 2026-10-27, pre-merge squad).

---

### User Story 2 - An unreadable record tells the operator how to repair it safely (Priority: P2)

The record is corrupted (for example by a merge conflict). The run warns that nothing was appended. Today the warning gives no repair step, and deleting the file, the obvious way out, makes synthesis forget which artifacts it created and re-add those the operator removed.

**Why this priority**: a bounded, loud diagnostic gap; the operator can still recover by hand.

**Independent Test**: a run against a malformed record prints the warning; the test pins the file name, the repair step and the deletion caution.

**Acceptance Scenarios**:

1. **Given** a malformed `.kittify/charter/synthesized-artifacts.yaml`, **When** a synthesis run reaches the activation append, **Then** the warning names the file, says to restore it from version control or repair its YAML while keeping its ids, and says that deleting it makes synthesis re-add removed artifacts.
2. **Given** a malformed legacy `.kittify/charter/synthesized-tactics.yaml`, **When** the same run happens, **Then** the warning names that file with the same guidance.

---

### User Story 3 - A full run keeps the stored link of artifacts it did not regenerate (Priority: P2)

A project carries a synthesized tactic or styleguide with a legacy `applies` edge to its directive. A full `charter synthesize` run regenerates other artifacts. Today it strips that edge anyway and reports "legacy applies edge replaced by suggests", although no `suggests` edge was written. Delivery does not change (triage correction), but the stored directive link is lost and the notice is false.

**Why this priority**: graph-integrity and honest reporting; no delivery change.

**Independent Test**: a full-run merge over an overlay with a legacy edge on an artifact the run did not regenerate keeps that edge, and the strip report does not list it.

**Acceptance Scenarios**:

1. **Given** synthesized tactic `T` with a legacy `applies` edge and a full run that does not regenerate `T`, **When** the run merges the overlay, **Then** `T`'s `applies` edge is still present and the run reports no strip for `T`.
2. **Given** the same project, **When** a run regenerates `T`, **Then** the legacy edge is stripped, the stamped `suggests` edge is written, and the notice lists the strip.
3. **Given** a synthesized styleguide with a legacy `applies` edge it did not regenerate, **When** a full run happens, **Then** the edge stays (the same rule holds for every reach-only kind).
4. **Given** the dead project-intent `requires --> mission_type:*` edge (#6443) on a `PROJECT_*` directive the full run did NOT regenerate, **When** the run merges the overlay, **Then** that edge is still stripped and reported (today's behaviour, unchanged).
5. **Given** a kept legacy edge on a non-regenerated artifact, **When** a `--prune` run happens, **Then** the edge is pruned with its node as ordinary non-regenerated content, not reported as "replaced by suggests".

### Edge Cases

- Outside a git repository the lock falls back to `.kittify/runtime/locks/charter-synthesis.lock` (a git-ignored runtime directory); a run still serializes.
- A kept legacy edge whose target directive no longer exists is reported as a `preserved_dangling_endpoint` conflict (non-blocking) instead of being silently stripped.
- A symlinked worktree root resolves to the same lock as its target.
- A git that cannot be invoked: the run refuses rather than writing unlocked.
- A record write nested inside a run that already holds the lock does not deadlock (the lock is re-entrant for the holding thread).
- A crashed run (process killed while holding the lock) leaves the lock file behind: the OS lock is released with the process, so the next run proceeds.
- Two worktrees of one repository synthesize at once: each has its own lock and its own files, so neither waits on the other.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record read-merge-write is serialized | As an operator, I want concurrent runs' created-artifact ids all kept so that an artifact I removed is never re-added. (#6453) | High | Open | [build] | no — the two-writer race test is red on today's code |
| FR-002 | One run-wide synthesis lock per worktree | As an operator, I want every writing synthesize or resynthesize run held under one lock from just after the charter soundness check to the end of the command (legacy directive convergence, fresh-project seed, overlay, manifest, record, activation append) so that two runs never interleave their writes; read-only modes (`--dry-run`, `--dry-run-evidence`, `--list-topics`) take no lock. (#6453) | High | Open | [build] | no — a lock held by another thread must refuse the run; positive control: lock free, run writes |
| FR-003 | Bounded wait, then a named refusal | As an operator, I want a run that cannot get the lock within the configured wait (default 10 seconds) to exit non-zero with `CHARTER_SYNTHESIS_LOCK_HELD`, naming the lock file, and write nothing so that I know another run is in progress. (#6453) | High | Open | [build] | no — paired with FR-002 on the same held-lock fixture |
| FR-004 | Removed artifacts stay removed under concurrency | As an operator, I want an artifact I removed to stay removed after concurrent synthesis runs regenerate it. (#6453) | High | Open | [build] | no — paired with FR-001's race fixture |
| FR-005 | Unreadable-record warning gives a repair step | As an operator, I want the warning to name the file and tell me to restore it from version control or repair its YAML while keeping its ids. (#6455) | Medium | Open | [build] | no — the pinned text is absent today |
| FR-006 | Warning cautions against deleting the record | As an operator, I want the warning to say that deleting the file makes synthesis re-add artifacts I removed. (#6455) | Medium | Open | [build] | no — the pinned text is absent today |
| FR-007 | Full run keeps legacy edges of non-regenerated artifacts | As an operator, I want a full (preserve-mode) run to leave the legacy `applies` edge of a synthesized artifact it did not regenerate in place so that the stored directive link is not lost. (#6456) | Medium | Open | [build] | no — today's full run strips it (pinned by existing tests) |
| FR-008 | Strip notice only lists what was replaced | As an operator, I want the "replaced by suggests" notice (`stripped_legacy_edges`) and the reconciliation delta's stripped refs to list only edges the run actually replaced. (#6456) | Medium | Open | [build] | no — today it lists the non-regenerated edge |
| FR-009 | Regenerated artifacts still migrate | As an operator, I want a regenerated artifact's legacy edge still stripped and replaced by its `suggests` edge. (#6456) | Medium | Open | [ratchet] | yes — positive control for FR-007 on the same fixture |
| FR-010 | Dead mission-type edge still stripped on a full run | As an operator, I want a full run to keep stripping the dead `PROJECT_* --requires--> mission_type:*` edge (#6443) even when that directive was not regenerated. (#6456) | Medium | Open | [ratchet] | yes — green on the pre-fix code; meaningful paired with FR-007 on the same full-run fixture, where it goes red if the #6456 filter leaks into the dead-edge check |
| FR-011 | Bundle restamp waits for synthesis | As an operator, I want `restamp_bundle_hash` (run by `charter activate`, presets and org charter changes) to take the synthesis lock so that it never overwrites a manifest a synthesis run is writing. (#6453) | Medium | Open | [build] | no — a lock held by another thread must make the restamp wait/refuse |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded lock wait | A contended run gives up within the configured wait + 1 s (default wait 10 s, a module constant; the CLI test injects 0.2 s). | Reliability | High | Open |
| NFR-002 | No change to agent delivery | `reach_only_ids` returns the same set for a fixture with a kept legacy edge as for the same fixture with that edge stripped (legacy `applies` edges never make an artifact reach-only). | Reliability | High | Open |
| NFR-003 | Code quality gates | Every touched function stays at cyclomatic complexity ≤ 15; ruff, `ruff format` and mypy report zero issues on touched files; diff coverage ≥ 90 %. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical lock primitive | Locking goes through `kernel.locks` (`machine_file_lock`); no raw `fcntl`/`msvcrt`/`filelock` (gate `test_lock_primitive_ban.py`). | Technical | High | Open |
| C-002 | Charter layer ownership | The lock lives in `charter.activation` (stays in core per ADR 2026-10-16-1, Amendment 2026-10-19) and is reached from `specify_cli` only through `charter.activation.api`. | Technical | High | Open |
| C-003 | No new repair command | No `doctor` check or `--repair` mode for the record (triage of #6455). | Business | Medium | Open |
| C-004 | Build on #6454 | Keep #6454's fail-closed manifest fallback (`SynthesisMembershipUnreadableError`) unchanged. | Technical | High | Open |
| C-005 | No successor edge | Do not write a `suggests` edge for an artifact the run did not regenerate (operator decision; a stamped one would change delivery). | Technical | High | Open |
| C-006 | Residual writers out of scope | The activation-ledger migration's manifest stamp and `charter activate`/`deactivate` config writes stay unlocked here; tracked in #6719. | Technical | Medium | Open |

### Key Entities

- **Created-artifacts record**: `.kittify/charter/synthesized-artifacts.yaml` (plus the read-only legacy `.kittify/charter/synthesized-tactics.yaml`); every reach-only artifact id synthesis has ever created, per kind. Its memory is what keeps an operator's removal in force.
- **Synthesis lock**: one lock file per worktree (keyed on the resolved worktree root) in the git common dir; held for a writing synthesis run and by `restamp_bundle_hash`.
- **Legacy `applies` edge**: a `<tactic|styleguide> --applies--> <directive>` edge on a synthesized reach-only artifact, from before #6404 linked these FROM the directive with a stamped `suggests` edge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a deterministic two-writer interleaving, 0 created-artifact ids are lost (today 1 of 3 is lost). — [build] · no-op passable: no
- **SC-002**: A run facing a lock held by another thread exits non-zero within the configured wait + 1 s and leaves the overlay, manifest, record and directive files byte-identical. — [build] · no-op passable: no
- **SC-003**: The unreadable-record warning contains the file path, a restore-or-repair step and the deletion caution. — [build] · no-op passable: no
- **SC-004**: After a full run, 100 % of non-regenerated synthesized artifacts that had a legacy `applies` edge still have it, and none of them appears in the strip notice. — [build] · no-op passable: no

## Assumptions

- Holding the lock across adapter generation is acceptable: the generated adapter only reads files, and synthesis is an operator-paced action. `charter activate --resynthesize` runs `charter synthesize` in-process, so it is covered.
- A worktree's charter files are per worktree, so a per-worktree lock (keyed on the worktree root) is sufficient.

## Out of Scope

- #6631 (commit reminder omits `synthesized-artifacts.yaml`) — same command, separate issue.
- Locking `charter activate`/`deactivate` config writes and the activation-ledger migration's manifest stamp: Follow-up: #6719 (under epic #6518).
