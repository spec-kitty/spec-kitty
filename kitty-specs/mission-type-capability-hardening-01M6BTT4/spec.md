# Mission Specification: Harden the mission-type capability contract

**Mission Branch**: `issue-6330-run-dir-threading`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue [#6330](https://github.com/spec-kitty/spec-kitty/issues/6330) — "Harden the mission-type capability contract: run_dir threading, substantive-gate except, wp_driven parity". Refs #6315 (merged, PR #6332), parent #2721.

## Intent Summary (confirmed)

- **Primary actor**: a maintainer operating a **custom (non-built-in) mission type** whose family declares work-package iteration in its frozen runtime DAG.
- **Trigger**: three non-blocking hardening items the #6315 adversarial squad raised against the capability contract that landed there. None re-opens a built-in regression (software-dev / research / documentation / plan stay byte-identical); each is a narrow fail-open or an unobservable failure in the custom-type path.
- **Desired outcome**: (1) the runtime threads the in-hand `run_dir` into `gather_artifact_presence` so the `wp_driven` fact no longer re-resolves the run from `feature_dir.name` (a value `AGENTS.md` explicitly says is *not* a mission handle); (2) the `requires_substantive_spec` resolution stays non-crashing but its fail-open becomes **observable**; (3) the charter-side `wp_driven` facet is pinned as **advisory** with the frozen runtime DAG authoritative, proven by a curated-away parity test.
- **Invariants**:
  - `wp_driven` remains decided by the single kernel rule (`kernel.mission_runtime_shape.step_ids_declare_wp_iteration`) on **runtime** input; the charter DTO value stays advisory for CLI/external consumers.
  - A guard that cannot resolve its facts still fails the way it does today (fail-closed for registered families; the documented neutral degrade for unregistered ones). No new exception escapes a guard.
  - No built-in mission type's guard result or composed-dispatch payload changes.

### Grounding on `main` @ `287a226cfe`

| Item | Owning site today | State |
|---|---|---|
| 1. `run_dir` not threaded | `runtime_bridge_composition._dispatch_via_composition` / `_check_composed_action_guard`, `runtime_bridge._check_cli_guards`, `runtime_bridge_io.gather_artifact_presence` → `_wp_driven_fact` | `run_dir` is a parameter of `gather_artifact_presence` but **no production caller passes it**; the fact falls back to `_resolve_run_dir_for_mission(repo_root, feature_dir.name)` and returns `False` on any selector error — the WP-advance guard is then skipped for a custom WP-driven family (the exact hole #6315 closed, re-opened whenever the run does not resolve from the directory name). |
| 2. silent broad `except` | `charter.activation.mission_type_profiles.requires_substantive_spec_for` (`:1042-1055`), reached through the `charter.activation.api` seam by the resume probe (`mission_check_prerequisites._requires_substantive_spec`) | `except Exception: return builtin_default` with **no log**; a type that authored `requires_substantive_spec: true` and whose resolution transiently throws is silently downgraded to `False`, so a stub spec passes. |
| 3. unpinned advisory facet | `charter.activation.mission_type_profiles.ResolvedMissionType.wp_driven` (`:708`) vs `runtime_bridge_io.mission_declares_wp_iteration` | The DTO derives `wp_driven` from curated `action_sequence`; the guard reads the frozen DAG. They agree for every built-in; a curated-away custom type would diverge, and nothing states which side wins or pins it. |

Not superseded: no merged PR, changelog entry, or ADR under `docs/adr/` claims any of the three; #6331 (the sibling capability-offering seam) touches the offering surface, not these three sites. Reproduced by static inspection (as recorded in the issue's triage comment) and by a red test per item (see FR-001..FR-003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A custom WP-driven family keeps the WP-advance guard when the run is in hand but the directory name is not a handle (Priority: P1)

As a maintainer running `next` against a custom mission, the composed/dispatch guard holds at `implement`/`review` while work packages are pending because it reads the run the caller already resolved — never a re-resolution from a directory name.

**Why this priority**: this is the actual fail-open; the other two are observability and contract clarity.

**Independent Test**: scaffold an activated custom family whose frozen DAG declares `implement`, point `feature_dir` at a planning directory whose *name* is not the mission handle, pass the real `run_dir`, and assert the composed guard still returns the pending-WP failure.

**Acceptance Scenarios**:

1. **Given** a custom WP-driven family with a pending WP and a `feature_dir` whose name is not the mission slug, **When** `_check_composed_action_guard(..., run_dir=<real run>)` runs, **Then** it returns the WP-advance failure (`Not all work packages have required status …`) instead of degrading to no failures.
2. **Given** the same fixture, **When** the fact is gathered through the production dispatch path (`_dispatch_via_composition` → guard), **Then** the run directory the caller holds is what decides `wp_driven` (`run_dir=` is forwarded, no `feature_dir.name` re-resolution happens).
3. **Given** a custom family whose frozen DAG does **not** declare `implement`, **When** the guard runs with a `run_dir`, **Then** it still does not gate (no new false positive).
4. **Given** `_check_cli_guards` (the legacy CLI guard path) invoked with `run_dir=`, **When** the family is WP-driven, **Then** it uses the same threaded run directory.
5. **Given** a caller that threads no `run_dir` (existing direct test/CLI callers), **When** the fact is gathered, **Then** the read-only fallback still resolves from an **explicitly supplied** mission slug — never implicitly from `feature_dir.name`.

### User Story 2 - A resolution failure on `requires_substantive_spec` is observable (Priority: P2)

As a maintainer debugging why a stub spec passed, I see a warning naming the mission type and the error when its declared capability could not be resolved, instead of the value silently collapsing to the built-in default.

**Why this priority**: it turns a silent fail-open into a diagnosable one without changing the non-crashing contract.

**Independent Test**: patch the resolver to raise, call the public seam, and assert (a) the call still returns the built-in default and does not raise, and (b) a WARNING naming the mission type and the exception is logged.

**Acceptance Scenarios**:

1. **Given** a registered type whose resolution raises, **When** `requires_substantive_spec_for` runs, **Then** it returns the built-in default **and** logs at WARNING with the type key and the failure.
2. **Given** a healthy resolution, **When** the seam runs, **Then** no warning is logged (positive control on the same fixture family).
3. **Given** the resume probe `_requires_substantive_spec`, **When** resolution fails, **Then** the probe still returns a bool and does not crash.

### User Story 3 - The advisory `wp_driven` facet cannot drift silently from the guard (Priority: P2)

As a consumer of `ResolvedMissionType.wp_driven` I can read that it is advisory and that the frozen runtime DAG is authoritative, and a curated-away type is pinned by a test proving the guard still follows the DAG.

**Why this priority**: prevents a future "fix the DTO and the guard together" change from picking the wrong authority.

**Independent Test**: build a custom type whose `action_sequence` omits `implement` while its frozen DAG declares it; assert the DTO reports `wp_driven is False` (advisory) **and** the guard gates with the pending-WP failure (DAG authoritative).

**Acceptance Scenarios**:

1. **Given** a curated-away custom type, **When** the DTO is resolved, **Then** `wp_driven` reflects `action_sequence` (advisory) as documented.
2. **Given** the same type and mission, **When** the composed guard runs with the run directory, **Then** `wp_driven` is taken from the frozen DAG and the guard gates.
3. **Given** the DTO field, **When** a reader opens the dataclass, **Then** the docstring states the facet is advisory and names the frozen DAG as authoritative.

### Edge Cases

- `run_dir` belongs to a different mission than `feature_dir` → out of scope for this mission; the caller already resolved both from the same `DecideNextContext`, and a mismatch is not silently "fixed" here (documented on the new parameter).
- `run_dir` exists but `mission_template_frozen.yaml` is missing/unreadable → `mission_declares_wp_iteration` already returns `False` (fail-closed); unchanged.
- Both `run_dir` and an explicit `mission_slug` supplied → `run_dir` wins; the slug is only the fallback.
- Resolution failure for a type that never declared the capability → still the built-in default (today's behaviour), now logged once at WARNING.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Thread `run_dir` into the presence fact | As a maintainer, I want the guard to read the run the caller already resolved so a WP-driven custom family is never fail-open on a directory-name miss. | High | Open | [build] | no — red test renames the planning dir; a no-op change keeps returning `[]` |
| FR-002 | Observable `requires_substantive_spec` fail-open | As a maintainer, I want a WARNING when the declared capability cannot be resolved so a silent downgrade to the built-in default is diagnosable. | High | Open | [build] | no — the red test asserts the log record, which a no-op change never emits |
| FR-003 | Pin the advisory `wp_driven` contract | As a consumer, I want the DTO documented as advisory and a curated-away parity test proving the frozen DAG stays authoritative. | Medium | Open | [build] | no — the curated-away fixture does not exist today |
| FR-004 | Keep built-in behaviour byte-identical | As a maintainer, I want the four built-in types' guard results and composed dispatch unchanged, so this hardening carries no regression risk. | High | Open | [ratchet] | no — the existing guard tests are the positive control and must stay green |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new disk read on the hot path | Threading `run_dir` must not add a `feature-runs.json`/selector read where the caller already holds the run; the resolved-fallback path is reached only when no `run_dir` is supplied. | Performance | High | Open |
| NFR-002 | No exception escapes a guard | Every new failure path (logging, docstring-only contract) keeps `_check_cli_guards` / `_check_composed_action_guard` / the resume probe non-raising exactly as today. | Reliability | High | Open |
| NFR-003 | Changed-line coverage | New branches and the new fallback signature are covered by tests in this mission's diff (diff-cover ≥ 90% on changed lines). | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One kernel rule | `wp_driven` stays `step_ids_declare_wp_iteration`; the fix moves the *input* (which run is read), never the rule or a second definition. | Technical | High | Open |
| C-002 | Public seams only | The resume probe keeps reaching activation through `charter.activation.api`; the boundary gate forbids a new external reach into `charter.activation` internals. | Technical | High | Open |
| C-003 | No gate weakening | No CI gate, guard, or existing test is skipped, xfailed, or relaxed to land this. | Process | High | Open |

### Key Entities

- **`ArtifactPresenceSnapshot.wp_driven`**: plain fact on the gathered snapshot; the only input the cores guard reads for the custom-family WP gate.
- **`ResolvedMissionType.wp_driven`**: advisory charter-side facet derived from `action_sequence`; consumed by CLI/external readers, never by the guard.
- **`requires_substantive_spec`**: capability that gates the resume probe's substantive-spec check; resolved lazily, fail-open to a built-in default.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the planning directory renamed away from the mission slug, the composed guard returns the pending-WP failure for a custom WP-driven family — [build] · no-op passable: no
- **SC-002**: A raising `requires_substantive_spec` resolution logs exactly one WARNING naming the type and still returns the built-in default — [build] · no-op passable: no
- **SC-003**: A curated-away custom type shows DTO `wp_driven=False` while the guard still gates from the frozen DAG — [build] · no-op passable: no
- **SC-004**: Every existing guard/presence test for the four built-in types passes unchanged — [ratchet] · no-op passable: no
