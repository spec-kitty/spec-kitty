# Research: setup-plan commits its lifecycle events on coordination Missions

## Code grounding (main @ 1890a6c)

- `mission_setup_plan._emit_lifecycle_phase_markers` appends `SpecifyCompleted` and `PlanStarted` to `feature_dir`; `_commit_plan_if_substantive` appends `PlanCompleted` to `feature_dir`. On every topology `feature_dir` is the PRIMARY Mission directory.
- `_lifecycle_log_for_plan_commit` returns the log only when the topology does not route through coordination, so on a coordination Mission the three events stay uncommitted in the repository root checkout (PR #7562, Deferred section).
- The other lifecycle writers already place through the coordination surface: create (`mission_creation_events._commit_coord_create_events`, `commit_for_mission(kind=STATUS_STATE)`) and finalize-tasks (`_emit_tasks_started`, `mission_finalize_bootstrap` WPCreated / TasksCompleted via `write_dir(STATUS_STATE)`).
- `doctor coordination` (`_coordination_doctor.run_coordination_health`) iterates the coordination Missions and emits `DoctorFinding`s; `warning` exits 0, `error` exits 1.

## Decisions

### D1 — Place through `write_dir(STATUS_STATE)`

- **Decision**: setup-plan resolves `placement_seam(repo_root, slug, owned=owned).write_dir(STATUS_STATE)` once and passes its `path` to every `emit_artifact_phase` call.
- **Rationale**: the single write-location authority for status records; finalize already uses it (WP15 T080). On non-coordination topologies it returns the same directory as today, so NFR-002 holds by construction.
- **Alternatives**: a hand-built coordination worktree path (rejected: a second authority, forbidden by the write-side re-derivation gate).

### D2 — Resolve the write location outside the best-effort `try`

- **Decision**: the `write_dir` call happens before the `try/except` that guards the emission.
- **Rationale**: a named write-location refusal must fail setup-plan closed, never degrade to a debug log while the events are written nowhere (finalize WP15 cycle 2, B3).

### D3 — One coordination commit at the end of the run

- **Decision**: on a coordination Mission, after the plan commit (or the scaffold-only / blocked return), setup-plan calls `commit_for_mission(..., files=(log,), kind=STATUS_STATE)` once.
- **Rationale**: NFR-001 (at most one commit); the router answers `unchanged` when nothing is new, so re-runs make no empty commit. Mirrors create.
- **Alternatives**: two commits (after PlanStarted and after PlanCompleted), rejected by NFR-001; folding the log into the plan commit, rejected because the plan lives on the Mission branch and the log on the coordination branch.

### D4 — Fail loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`

- **Decision**: a router result other than `committed` / `unchanged` makes setup-plan exit 1 with `error_code: SETUP_PLAN_LIFECYCLE_UNCOMMITTED`, naming the events and the router diagnostic. A plan commit that already landed is kept and reported.
- **Rationale**: operator ruling (fail loud, #7792 precedent) and FR-004.

### D5 — Stranded events are a doctor coordination warning

- **Decision**: a per-Mission helper compares the lifecycle events (`SpecifyCompleted`, `PlanStarted`, `PlanCompleted`) in the repository root checkout log with the coordination log, keyed by event type (the Mission is fixed per log). Any present only in the former yields a `warning` finding (exit 0) with a stable `error_code`; `--fix` never acts on it. An unreadable log yields a warning naming it, never a crash.
- **Rationale**: operator rulings 1A and the alignment answer (warning, exit 0); C-002.

## Open items

None. The default-Mission-before-settlement question is tracked in #7827 (C-001).
