# Mission Specification: Python interpreter surface honesty

**Mission Branch**: `claude/project-thread-hjiqjz`
**Created**: 2026-09-27
**Status**: Draft
**Input**: GitHub issue #3189 ("no pytest job runs above Python 3.12, so interpreter-divergence defects are invisible to the gate"), its full comment thread (the #4866 residue and the #5244 validation-run evidence), and the operator steer: "Run the entire mission e2e, with brownfield pointcuts."

## Intent Summary

- **Primary actor**: a Spec Kitty user or maintainer running the CLI on any Python interpreter that `requires-python` admits (today 3.11, 3.12, 3.13 and 3.14).
- **Trigger**: the interpreter changes a standard-library behaviour the code relies on. The confirmed case is Python 3.13's change to non-strict `Path.resolve()`: a symlink loop no longer raises, so the path comes back as if it had resolved.
- **Desired outcome**: the same input produces the same verdict on every admitted interpreter. Security and fail-closed guards in particular never flip from "refuse" to "allow" because of the interpreter. The Python versions the package declares match the ones CI actually exercises, and a guard stops the two from drifting apart again.
- **Invariant that must always hold**: a path that cannot be resolved (for example a symlink loop) is never treated as contained, complete or valid, whatever the interpreter.
- **Sequencing**: the declared-versus-tested guard and the advisory 3.14 job edit the same workflow and helpers as open PR #5244, so they land after it. The divergence fixes (FR-001 to FR-005) do not depend on it and ship first.
- **Boundary**: the nightly 3.13 job reshape (sharding) is owned by #5244 / #4951 and is out of scope. The 17 reds that also fail on 3.11 and 3.12 are drift on `main`, not interpreter divergence, and are out of scope.
- **Discovery mode**: brief-intake from the issue thread. The operator asked for an end-to-end run, so discovery was minimised. The one open scope fork (the 3.14 strategy) is recorded as Decision Moment `01M3JCYVZ6TBD6HZZF4CDEHRBE`. Work proceeds on the recommended option until the operator answers.

## Reproduction evidence (2026-09-27, `main` @ `f8aa22fe`)

The 19 node IDs reported red on 3.13 (the 3 residual from #4866 plus the 28 from #5244's validation run, several since rewritten on `main`) were re-run on local 3.11.15, 3.12.3 and 3.13.12 venvs built with `uv sync --frozen --all-extras`:

| Class | Count | Evidence |
|---|---|---|
| Real 3.13 divergence (red on 3.13 only) | 2 | `tests/dashboard/test_artifact_containment.py::…::test_unresolvable_path_is_not_contained`; `tests/specify_cli/tool_surface/providers/test_command_skills.py::test_wp04_dispatch_config_observation_boundary[loop]` |
| Red on 3.11, 3.12 and 3.13 alike | 17 | Drift on `main`, not divergence. Out of scope, listed in the PR. |
| Context-sensitive, passes in isolation on every interpreter | 1 | `test_glossary_validate.py::…::test_human_output_shows_valid` (line wrap in a parallel run) |

`uv sync --frozen --all-extras --python 3.14` succeeds (CPython 3.14.7), so a 3.14 leg is feasible.

The root cause of both real divergences was confirmed directly: for a two-link symlink loop, `Path.resolve()` raises `RuntimeError` on 3.11 but returns the unresolved path on 3.13. `Path.resolve(strict=True)` raises `RuntimeError` on 3.11 and `OSError(ELOOP)` on 3.13.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Containment guards refuse symlink loops on every interpreter (Priority: P1)

A dashboard user whose mission artifact directory contains a symlink loop asks for the artifact listing or an artifact file. On 3.11 and 3.12 the containment guard refuses the path. On 3.13 and later it must refuse it too, rather than treating the loop as contained and passing it on to a file read.

**Why this priority**: this is a fail-closed security guard that silently weakens on newer interpreters. It is the confirmed, highest-impact divergence.

**Independent Test**: build a symlink loop inside a mission artifact directory and call the canonical containment seam and the dashboard guard. Both refuse on every interpreter in the matrix.

**Acceptance Scenarios**:

1. **Given** a two-link symlink loop inside an artifact directory, **When** the containment guard checks it on 3.11, 3.12, 3.13 or 3.14, **Then** it answers "not contained" without raising out of the request handler.
2. **Given** an ordinary file inside the artifact directory (same fixture), **When** the guard checks it, **Then** it answers "contained" (positive control).
3. **Given** a path that does not exist yet under the root, **When** the canonical seam resolves it, **Then** it still resolves non-strictly and is judged by location, exactly as today (no regression for not-yet-created paths).

### User Story 2 - Command-skill input observation treats a symlink loop as broken on every interpreter (Priority: P1)

A maintainer whose `.kittify/config.yaml` is a self-referencing symlink runs a command-skills assessment. On 3.11 the assessment reports the input as broken, with a diagnostic and no effects. On 3.13 it must do the same instead of reporting "complete".

**Why this priority**: this is the second confirmed divergence, and the same stdlib change causes it.

**Independent Test**: the existing `test_wp04_dispatch_config_observation_boundary[loop]` passes on every interpreter.

**Acceptance Scenarios**:

1. **Given** `.kittify/config.yaml` is a self-loop symlink, **When** the command-skills provider assesses it, **Then** the assessment is incomplete, carries a diagnostic, and plans no effects, on every interpreter.
2. **Given** a regular symlink to a real config (same parametrised test), **When** assessed, **Then** it is complete with effects (positive control).
3. **Given** a genuine programmer `RuntimeError` in the renderer, **When** assessed, **Then** it still escapes unchanged (existing `test_wp04_dispatch_does_not_hide_programmer_runtime_error`).

### User Story 3 - One interpreter-invariant way to resolve a path, enforced (Priority: P2)

A contributor writing a new containment or observation guard uses the canonical loop-aware resolution primitive. An architectural gate stops new code from hand-rolling its own interpreter-specific loop translation.

**Why this priority**: it closes the defect class by construction (DIRECTIVE_043) rather than patching two call sites.

**Independent Test**: the gate test fails when a synthetic offender that translates `ELOOP` by hand is added outside the primitive's module (self-mutation test), and passes on the real tree.

**Acceptance Scenarios**:

1. **Given** the primitive and a symlink loop, **When** called on any interpreter, **Then** it raises `OSError` with `errno == ELOOP`.
2. **Given** a missing path or a dangling symlink, **When** called, **Then** it returns the same result non-strict `Path.resolve()` returns.
3. **Given** a module outside the primitive that references `errno.ELOOP` together with `RuntimeError` translation, **When** the gate runs, **Then** it fails and names the file.

### User Story 4 - Declared and tested interpreter surfaces agree (Priority: P2, follow-up after #5244)

A release reviewer reading `pyproject.toml` sees trove classifiers that name exactly the Python minor versions a CI pytest job runs on and gates. The newest admitted interpreter (3.14), which is not yet claimed, still gets an advisory signal, so divergence surfaces before a user reports it.

**Why this priority**: this is the issue's stated done-bar ("make the tested surface and the declared surface agree").

**Independent Test**: a guard test derives the set of interpreters CI's workflows run pytest on and compares it with the classifier set. Mutating either side (adding a classifier, removing a matrix version) turns it red.

**Acceptance Scenarios**:

1. **Given** the committed workflows and `pyproject.toml`, **When** the guard runs, **Then** every `Programming Language :: Python :: 3.X` classifier corresponds to at least one gating CI pytest job on 3.X, and every gating pytest interpreter has a classifier.
2. **Given** the advisory newest-interpreter job, **When** the guard runs, **Then** that interpreter is recognised as advisory (not claimed) and does not require a classifier.
3. **Given** the advisory job's suite is red on its interpreter, **When** the nightly runs, **Then** the red is reported (visible in the job summary) but does not fail the nightly or open a P0 escalation.

### Edge Cases

- A symlink loop in an **intermediate** path component (not the final one) must also be refused.
- A **dangling** (non-looping) symlink must keep today's non-strict behaviour: it resolves to its target's location.
- Resolution raising for **other** OS reasons (permission denied on an intermediate directory, `NotADirectoryError`) keeps today's non-strict fallback rather than becoming a new failure mode.
- Windows: `ELOOP` handling must not break on a host where symlink creation is unavailable. Tests that create symlinks skip there, as the existing symlink tests already do.
- The #5244 shard split may land before or after this mission. The guard and the advisory job must not depend on the `interpreter-matrix` job's exact name or shape.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Interpreter-invariant loop-aware resolution primitive | As a contributor, I want one canonical path-resolution primitive that raises `OSError(ELOOP)` for a symlink loop on every interpreter and otherwise matches non-strict `Path.resolve()`, so that guards built on it behave the same on 3.11–3.14. | High | Open | [build] | no — the regression test asserts `OSError`/`ELOOP` on a loop; on unfixed code it is `RuntimeError` (3.11/3.12) or no exception (3.13+) |
| FR-002 | Containment seams refuse symlink loops with their documented refusal | As a dashboard user, I want `ensure_within_directory` and `ensure_within_any` to refuse a symlink loop on every interpreter by raising their documented `ValueError` refusal (not a leaked `RuntimeError` on 3.11/3.12, not an acceptance on 3.13+), so that every caller, including the dashboard artifact guard, fails closed the same way. Each existing caller is audited for the new refusal. | High | Open | [build] | no — paired with a same-fixture positive control (an ordinary contained file is accepted) |
| FR-003 | Command-skill input observation treats a loop as broken everywhere | As a maintainer, I want the command-skills input observation to classify a symlink-loop config as broken on every interpreter, so that the assessment never reports "complete" for an unreadable input. | High | Open | [build] | no — the `[loop]` case is red on 3.13 today; `[regular-link]` in the same parametrisation is the positive control |
| FR-004 | Enumerated loop-sensitive guards migrated | As a user, I want the guards the brownfield scout confirmed to change their symlink-loop verdict between 3.11/3.12 and 3.13+ to reach one verdict on every interpreter via the primitive: `coordination/atomic_write.py` confinement (`_confine_path_to_worktree`, `_resolve_confined_artifact_path`), `skills/command_installer.py::_ensure_project_confined`, `decisions/ownership.py` (`_mission_dirs`, `_read_ledger`), `charter/offering/drg/org_pack_config.py::resolve_relative_path_within_root`, `charter/activation/synthesizer/path_guard.py::PathGuard._assert_allowed`, `upgrade/skill_update.py::is_external_symlink`, `analysis_report.py::_relativize_or_raise`, `tracker/saas_client.py` project-root resolution. Landing folds added two sites the WP04 gate and the pre-PR squad showed do diverge: `invocation/writer.normalise_ref` (3.13+ recorded a lexically normalised loop path instead of the raw ref) and `cli/commands/safe_commit_cmd.py` file arguments (3.13+ committed a looping symlink pair that 3.11 refused). Sites confirmed identical on every interpreter (`m_0_10_8_fix_memory_structure`, `mission.get_active_mission`, `dashboard/handlers/static.py`) are excluded and allowlisted with reasons. | Medium | Open | [build] | no — each migrated site gets a real-loop test that is red on at least one interpreter before the change |
| FR-005 | Hand-rolled loop handling around resolution is gated | As a maintainer, I want an architectural gate that flags any `except RuntimeError` or `ELOOP` handler whose try-body calls `resolve`/`realpath`, outside the primitive's module, with a reasoned shrink-only allowlist, a non-vacuity floor (the scanner sees at least one primitive call site and a minimum number of `resolve` call sites) and a self-mutation test, so that new guards reuse the primitive. `O_NOFOLLOW` `ELOOP` checks (a different meaning) are out of the predicate. Scope, stated honestly: this gate blocks hand-rolled loop translation; it does not detect the wider resolve-then-contain shape (`try: p.resolve() except OSError` then `relative_to`, about 88 functions), which is a recorded follow-up. | Medium | Open | [build] | no — the self-mutation test injects an offender and asserts the gate fails |

### Sequenced after #5244 (not requirements of this mission's work packages)

The post-spec squad (findings F1, F2) showed that the next two items edit the same workflow jobs and reuse the same workflow-parsing helpers as open PR #5244. They land in a follow-up stacked on #5244, not in this mission. They are recorded here so the design the squad agreed is not lost. They are deliberately not declared as requirement rows.

- **Declared-versus-tested interpreter guard**: As a release reviewer, I want a guard test asserting that the classifier set equals the set of minor versions a *gating* CI pytest job runs on, so that the declared surface cannot silently outgrow the tested one. The effective interpreter is derived in order `--python`, then setup-uv `python-version`/`UV_PYTHON`, then the sync pin, then `.python-version`. *Gating* means a merge-blocking per-PR job, or a nightly job that escalates a P0 and feeds the release gate. *Advisory* means a literal job-level `continue-on-error: true` with no escalation. The guard builds on #5244's workflow helpers rather than adding a second parser, so it lands after #5244.
- **Advisory newest-interpreter signal**: As a maintainer, I want a non-blocking nightly pytest job on the newest interpreter `requires-python` admits but the classifiers do not yet claim (3.14), so that divergence surfaces early without gating releases. The job has job-level `continue-on-error: true` (literal), never calls `nightly_escalation.py`, reports its verdict via `$GITHUB_STEP_SUMMARY` and a `::warning`, keeps the `${VAR:-1}` exit sentinel, uses a job key outside the `interpreter-matrix*` namespace, and runs a named subset sized to fit its timeout. It lands after #5244, and is subject to Decision Moment `01M3JCYVZ6TBD6HZZF4CDEHRBE`.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Interpreter parity of the fixed tests | The FR-001–FR-004 regression tests pass on 3.11, 3.12, 3.13 and 3.14 locally, recorded with commands and counts in the PR. | Reliability | High | Open |
| NFR-002 | Primitive cost | The primitive adds at most one extra `stat` call per resolution on the non-loop path, the same probe 3.11/3.12 `pathlib` already performs internally. Justified in the plan by reasoning, not by a syscall-counting test (counts differ across interpreters for unrelated reasons). | Performance | Medium | Open |
| NFR-003 | Advisory job budget (follow-up after #5244) | The advisory job runs a named subset sized from #5244's measured shard timings to finish within its timeout. The PR states that the subset does not cover the full suite. | Performance | Medium | Open |
| NFR-004 | Quality gates | New code passes `ruff check`, `ruff format --check` and `mypy --strict` with zero new suppressions, and every changed function stays at complexity 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not reshape the 3.13 nightly job; sequence after #5244 | The `interpreter-matrix` job and its sharding are owned by #5244 / #4951. This mission must not edit that job's body, and its new guard must hold whether that job is one leg or six shards. | Technical | High | Open |
| C-002 | Out-of-scope reds | The 17 tests red on 3.11, 3.12 and 3.13 alike are not interpreter divergence. They are not fixed here and are listed in the PR as honest pre-existing reds. | Technical | High | Open |
| C-003 | No upper bound without the operator | `requires-python` gets no upper bound unless the operator picks that option on the Decision Moment. | Business | Medium | Open |
| C-004 | Kernel stays a leaf | The primitive lives in `src/kernel/` and imports nothing from `specify_cli`, `charter`, `runtime`, `glossary` or `mission_runtime`. | Technical | High | Open |
| C-005 | No full heavy suites in mission work | Validation runs targeted files and specific named architectural gates only (`NO_FULL_HEAVY_SUITES_IN_MISSION`). The one-off fast/unit interpreter measurement used for scoping is reproduction evidence, not mission validation. | Technical | High | Open |

### Key Entities

- **Loop-aware resolution primitive**: the single interpreter-invariant way to resolve a path. It resolves non-strictly, except that a symlink loop always raises `OSError(ELOOP)`.
- **Declared interpreter surface**: the `requires-python` floor plus the `Programming Language :: Python :: 3.X` classifiers in `pyproject.toml`.
- **Tested interpreter surface**: the set of Python minor versions on which a CI pytest job runs, split into *gating* (a red fails the run or escalates) and *advisory* (reported only).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The 2 confirmed 3.13-only reds pass on 3.13 and 3.14 and still pass on 3.11 and 3.12. — [build] · no-op passable: no
- **SC-002**: Every loop-sensitive site the brownfield scout confirms produces the same verdict for a symlink loop on 3.11 and on 3.13+. — [build] · no-op passable: no
- **SC-003**: A synthetic hand-rolled loop handler added under `src/` turns the architectural gate red, and the migrated tree is green. — [build] · no-op passable: no
- **SC-004**: The 3.14 fast/unit measurement is recorded, and every 3.14-only red is either fixed in this mission (when it belongs to the FR-001 class) or listed in the PR as a follow-up with evidence. — [build] · no-op passable: no

## Assumptions

- Python 3.14 is the newest interpreter `requires-python` admits today. 3.15 is not released.
- The per-PR module matrix runs on 3.11 (`.python-version`), the router jobs on 3.12, and the nightly lane on 3.13. The guard derives this from the workflows rather than hardcoding it.
- `os.path.realpath` and `Path.resolve()` share the loop semantics per interpreter, so fixing the primitive covers both spellings where call sites migrate.
