# Research — Coord Reads Fail Closed

Grounded by a profile-loaded blast-radius audit on `main` (`d6533ea419`); all file:line verified. No dependency changes → **Supply-Chain / Adversarial-Evidence: N/A**.

## Premise correction (audit)

The seam raises **today only on `CoordState.DELETED`** (via `CoordinationBranchDeleted`, #4403). `EMPTY` / `UNMATERIALIZED` / `NONE` all fall through to `return TopologySurface.PRIMARY, None` (`resolution.py:1967`) — the empty-PRIMARY substitution. The original spec text ("already raises on NONE") was wrong; corrected in spec.md.

`CoordState` (`missions/_read_path_resolver.py:256-281`): `UNMATERIALIZED` = coord root absent **AND** declared `coordination_branch` still in git (fresh clone / removed worktree / CI); `DELETED` = coord root absent AND branch gone; `EMPTY` = coord root exists but mission dir absent; `NONE` = no coord topology; `MATERIALIZED` = coord dir present.

## The two bugs sit at DIFFERENT states — one unifying principle

**Principle:** a coord-topology read resolves to the **authoritative partition** or fails closed — it never silently returns empty-PRIMARY (unmaterialised) nor reads a PRIMARY-partition artifact through the status-only coord husk (materialised).

### Finding A (#4959) — UNMATERIALIZED → seam raises. **Decision: seam-level (DM-01M38VWD).**
- Extend `_classify_artifact_surface` (`resolution.py:1947-1967`): on `CoordState.UNMATERIALIZED` for a coord-partition kind, **raise** a new sibling error instead of returning empty-PRIMARY. Keep `DELETED`→`CoordinationBranchDeleted` and `MATERIALIZED`→COORD unchanged.
- **New exception:** `CoordinationWorktreeUnmaterialized(StatusReadPathNotFound)` in `coordination/surface_resolver.py` (its natural home, **additive** — does NOT touch `_coord_branch_exists`, so C-002 holds). Subclassing `StatusReadPathNotFound` means existing catchers absorb it; its `next_step` points at **materialise** (not flatten — that message would be false for UNMATERIALIZED).
- **Tracer surface (`retrospective/tracer_writer.py`):** `_read_current_coord_content` (`:144-170`) currently catches `_NO_EXISTING_CONTENT_EXCEPTIONS` (incl. `StatusReadPathNotFound`) → returns `""` → writer clobbers from `_default_header` (`:251-252`). **Fix:** narrow the catch so a coord-topology unresolved/unmaterialised read **propagates** (fail closed), and treat `UnicodeDecodeError` on an existing file as **refuse** (corruption ≠ "no content"). A genuinely-absent file on a *resolved* surface still returns empty (legitimate first write).
- **Alternatives rejected:** reuse `CoordinationBranchDeleted` (its flatten `next_step` is false for UNMATERIALIZED); reader-level only (rejected by DM-01M38VWD — doesn't close the class).

### Finding B (#4966) — MATERIALIZED husk → resolve `meta.json` to PRIMARY. **Decision: partition-correctness at the reader.**
- The coord worktree is a **status-only husk** (`coherence.py:168` + CHANGELOG: holds `status.events.jsonl`/`status.json` "and nothing else"). `decisions/service.py::_mission_dir` (`:215`) locates the feature dir via `read_dir(STATUS_STATE)` — a COORD kind → the husk → then reads `meta.json` there → absent → `MISSION_NOT_FOUND`.
- **`meta.json` is `PRIMARY_METADATA`** — a PRIMARY-partition kind that "only ever lives on the PRIMARY checkout" (`resolution.py:886`, `artifacts.py:169`) and short-circuits to PRIMARY before any probe. **Fix:** `_resolve_mission_id` / `_mission_dir` must resolve `meta.json` via **PRIMARY_METADATA** resolution, not `STATUS_STATE`, so it agrees with the authoritative ledger `acceptance/__init__.py::_has_blocking_clarification_marker` (`:666`) already reads (`load_index(file_path.parent)` = the PRIMARY spec dir). This ends the split-brain: `accept` and the decision service read the same partition.
- **Correct the wrong docstring** (`decisions/service.py:157-167`) that claims a materialised coord worktree carries `meta.json` — it does not (adjudicated: `coherence.py` + the QA repro win).
- This is NOT a seam-raise case (the state is MATERIALIZED, which correctly returns COORD); it is a reader using the wrong partition kind to locate a PRIMARY artifact.

## Blast-radius / degrader policy (audit-derived; no operator DM — the #4966 bug blocked the CLI decision path, logged in tracer-tooling-friction)

The seam raise is scoped to **coord-partition reads only** — PRIMARY-partition `read_dir` calls short-circuit before any probe (`resolution.py:1928-1929`) and can never raise. Coord kinds: `ACCEPTANCE_MATRIX, ISSUE_MATRIX, STATUS_STATE, DECISION_LOG, TRACER_FILE, REVIEW_CYCLE, DECISION_LEDGER`.

- **Only `UNMATERIALIZED` starts raising** (the fresh-clone/CI defect). `EMPTY` (coord root exists, mission dir absent) and `NONE` (no coord topology) keep returning primary — they are not the reported defect and changing them widens scope; noted in Deferred.
- **Sanctioned read-only degraders keep degrading:** `mission_runtime/read_dir_degrade.py` and `review/cycle.py:294` already `except StatusReadPathNotFound` and substitute — they absorb the new sibling and continue. Correct: they are non-destructive reads (NFR-002 no-regression); C-003 retention only bites read→write (tracer) and split-brain (decisions).
- **Already-safe catchers** (no change): `status/aggregate.py:357`, `agent/status.py:180/219`, `merge/executor.py:2543`, `mission_finalize.py:2090/2626`, `retrospective/generator.py:281`, `worktree_topology.py:182`, `_review_cycle_reconcile_doctor.py:276`.
- **No-catch coord `STATUS_STATE` readers (~25)** newly propagate the raise = **desired fail-loud**. Each must be regression-checked to land at a sane boundary (not a raw traceback). Highest-value verification targets: `decisions/service.py`, `decisions/emit.py:88`, `acceptance/__init__.py:964`, `agent_utils/status.py`, `workspace/context.py`, `lanes/recovery.py`, `agent_tasks_ports.py`.

## Scope guard (C-002) — confirmed

`_coordination_doctor.py` / `surface_resolver._coord_branch_exists` do NOT traverse the placement read seam (they use `resolve_planning_read_dir`). The mission touches `resolution.py` + `tracer_writer.py` + `decisions/service.py` + the audited callers; the **one additive touch** of `surface_resolver.py` is the new sibling exception class (does not alter `_coord_branch_exists`). #4979/#4950 surface untouched.

## Dogfooding note

`#4966` is live enough that `spec-kitty agent decision open` failed with `MISSION_NOT_FOUND` during THIS mission's own plan phase (coord worktree materialised → husk lacks `meta.json`). First-hand evidence for the #4966 acceptance test; see `tracer-tooling-friction.md`.
