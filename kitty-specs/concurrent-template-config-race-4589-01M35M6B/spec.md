# Mission Specification: Concurrent create_mission_core TemplateConfigurationError race

**Mission Branch**: `fix/concurrent-template-config-race-4589`
**Created**: 2026-09-22
**Status**: Draft
**Input**: GitHub issue [spec-kitty/spec-kitty#4589](https://github.com/spec-kitty/spec-kitty/issues/4589) — `test_concurrent_creates_no_collision: TemplateConfigurationError under concurrent create_mission_core (1/688 flake-suspect)`

## Origin & Framing

`tests/core/test_mission_creation_identity.py::test_concurrent_creates_no_collision`
failed once in CI (1/688, 2026-09-16, on PR #4585's head, run
[35075011666](https://github.com/spec-kitty/spec-kitty/actions/runs/35075011666))
with:

```
TemplateConfigurationError("Template configuration for mission type 'software-dev'
and artifact kind 'spec' is missing the requested mapping key.")
```

raised from inside a `threading.Thread` pair during concurrent
`create_mission_core` calls. `main` was green at the time; the failing test
imports only `specify_cli.core.mission_creation.create_mission_core`, unrelated
to PR #4585's actual diff (`src/specify_cli/status/work_package_lifecycle.py`
and its tests only) — hence "flake-suspect," not a PR regression.

**This is a *suspected* latent production-side thread-safety defect — not
yet empirically reproduced, and the causal mechanism itself is an unproven
hypothesis (see CL-002).** Prior investigation (readiness pass, cited
below) ran 0/300 cold-subprocess reruns of the real test and 0/2000
`Barrier`-synchronized, cache-cleared in-process trials without reproducing
the race naturally. The mission's job is therefore to (a) determine, through
research, whether the suspected mechanism is real, and (b) close it by
construction with a deterministic, non-natural-timing regression test —
never to "wait for it to flake again."

## Clarifications

This section is binding. A reviewer must be able to check the squad's work
against it without re-deriving anything from the issue or from chat history.

### CL-001 — Operator decision: fix production (Option A)

The operator has decided this mission takes **Option A: fix production**, not
"quarantine as flaky" and not "make the test deterministic while leaving a
production race in place." Concretely:

- Make cache population concurrency-safe — a per-key lock and/or stop sharing
  the module-level YAML instance across threads (exact mechanism is a plan-phase
  decision informed by research, not prescribed here).
- Add a **deterministic** regression test using `threading.Barrier` plus
  explicit `cache_clear()` calls — not a luck-based/flaky natural-timing test.
- The GitHub issue gets relabelled `type:fix` (from `type:flake`) — but the
  **orchestrator** performs that relabel at PR time, not any mission agent.
  This spec records the decision; it is not an instruction for a mission
  agent to call the GitHub API to change the label.

### CL-002 — The causal theory is a hypothesis, not a proven mechanism

The YAML-singleton-corruption-drops-a-template-key causal chain below is a
**hypothesis** carried into this mission from the readiness pass, not a
confirmed root cause. It has never been observed to fire under natural
concurrent load (0/300 cold-subprocess reruns, 0/2000 Barrier-synchronized
cache-cleared in-process trials). The plan phase MUST include research that
examines this hypothesis on its merits — including whether `ruamel.yaml`'s
`YAML(typ="safe")` instance actually shares or mutates load-time state across
threads when `.load()` is called concurrently from two threads on two
different `step.yaml` files, and whether `functools.cache`'s documented
locking behavior (it does serialize *cache-hit* reads, but does **not**
serialize concurrent *cache-miss* execution of the wrapped function body) is
sufficient by itself to explain a dropped `template_set` key. Do not treat the
hypothesis as established; state open questions and resolve them in
`research.md`, or explicitly carry them forward as open risks in `plan.md` if
they cannot be resolved before planning must proceed.

### CL-003 — Red-first-by-construction, not natural reproduction

Because the race was never naturally reproduced, any regression test this
mission adds must be honest about what it demonstrates. It is **not** a claim
of natural reproduction under load. It is a test that forces the unsafe
interleaving **by construction** — e.g., a monkeypatched load hook (or
equivalent instrumentation seam) plus a `threading.Barrier` that pins two
threads mid-cache-miss so the interleaving the hypothesis describes is
guaranteed to occur — and that:

- **FAILS on current (pre-fix) code**, demonstrating the unsafe interleaving
  is real and reachable through the production code path.
- **PASSES after the fix**, demonstrating the fix closes that specific
  interleaving.

**Severity-4 bar (explicit, binding):** a "red-first" test that still PASSES
with the fix reverted is a severity-4 finding. It proves nothing — it is
indistinguishable from a test that never touched the real defect. Any
implementation or review step that produces such a test has not satisfied
this mission's acceptance criteria, regardless of how the test reads.

### CL-004 — ATDD-first (C-011) and test-remediation discipline (Standing Order 4)

- A failing-first test is committed **before** the production fix, as a
  distinct commit (charter C-011). This is a functional requirement of this
  mission (see FR-004), not a plan-phase suggestion.
- Reproduce red-first through the **pre-existing entry point**
  (`create_mission_core`, exercised via
  `tests/core/test_mission_creation_identity.py` or an equivalent
  integration-level path that goes through the real resolver/repository
  chain) where at all possible — not a synthetic unit test that pokes at
  `_resolve_all_for_mission_type_cached` or `_YAML` directly and never
  proves the production entry point is affected. If a purely internal
  seam turns out to be unavoidable (e.g., because forcing the interleave
  requires monkeypatching a private loader hook), the test must still
  invoke `create_mission_core` (or the resolver path it drives) as the
  outer call, with the monkeypatch confined to forcing the timing, not to
  replacing the code path under test.
- Never retry-to-green. A bounded-retry "fix" that papers over timing
  (e.g., wrapping `create_mission_core` in a retry loop, adding a sleep,
  or increasing thread-start jitter to make the race statistically rarer)
  is explicitly **not acceptable** for this mission. The fix must remove the
  unsafe interleaving, not make it less likely to be observed.

### CL-005 — Fresh baseline, not the stale #3284 numbers

Issue #3284 ("main full suite has 23 untracked failures and 2 errors after
bootstrap prewarm") is **CLOSED**. Its stale "23 known-red on main" baseline
does not apply to this mission. Before making any change, this mission must
capture its **own** fresh baseline: run the targeted test surface (at minimum
`tests/core/test_mission_creation_identity.py`, plus any other suites the plan
phase scopes in) at the mission's scaffold commit — before either the
red-first test commit (CL-004) or the production-fix commit has landed on
`planning_base_branch` — and record the result. If pre-existing failures are
found that are unrelated to this mission's change, filing a GitHub issue for
them is the **orchestrator's** job, not any mission agent's — this spec
states that explicitly so the plan
phase does not schedule a mission agent to open tracker issues for unrelated
pre-existing red.

### CL-006 — Silent-success is prohibited

On every failure path, the fixed code must raise `TemplateConfigurationError`
(or an equivalent explicit, typed exception) with a reason string precise
enough to diagnose. It must never return `None`, an empty mapping, or a
partial/silently-degraded `template_set` in place of raising. This applies to
both the existing raise sites inside `resolve_configured_template` in
`src/specify_cli/runtime/resolver.py` (function defined at line 440;
`TemplateConfigurationError` construction around lines 474–526) and any new
cache/lock code this mission adds — including, but not limited to, a lock
timeout, a corrupted-cache detection, or a retry-exhaustion path, should any
of those specifically be introduced — must raise, not degrade, on any
failure encountered during cache population (see CL-008: the approved
design introduces none of those three named mechanisms, but the
raise-not-degrade requirement applies to whatever failure the approved
design's own code can actually produce, not only to those three).

### CL-007 — Reflexivity: mission creation is the machinery this mission runs on

`create_mission_core` and the template/step resolution chain it depends on
are the very machinery that scaffolded this mission (see Step 1's scaffold
command and the resulting `meta.json`/`spec.md`). This mission must state
explicitly, and the plan/implementation must confirm:

- **In-flight missions are expected to be unaffected.** The defect and its
  fix are in-process cache behavior only (per-process `functools.cache`
  memoization and a shared in-process YAML loader instance). Nothing in the
  suspected defect or its fix touches on-disk mission state, `meta.json`
  schema, or any persisted mission-metadata contract.
- **No contract or schema move is implied by the fix.** A per-key lock and/or
  no-longer-sharing a YAML instance across threads changes nothing about the
  on-disk `step.yaml` format, the `MissionType`/`MissionStep` schemas, or the
  `template_set` mapping's shape — only the concurrency safety of how those
  in-memory structures are built and cached.

### CL-008 — Operator amendment: SC-006 corrected to a satisfiable silent-success guard (2026-09-23)

On 2026-09-23 the operator amended **SC-006** (Success Criteria). The
original SC-006 required a dedicated test to force one of three named
failure conditions — a lock-timeout, a corrupted-cache condition, or a
retry-exhaustion condition — in the new concurrency-safety code, and to
assert that condition raises rather than silently degrades. A prior
plan-round review (finding **PLAN-FRESH4-DEBBIE-001**, severity 4,
`reviews/plan.fresh-4-debbie.yaml`) established that the approved plan
design (§6b, a single-flight blocking-lock design built on an ordinary
`threading.Lock` — no acquisition timeout, no corrupted-cache detection, and
no retry logic) contains **none** of those three conditions. There is no
production code path in the approved design that could raise on a lock
timeout, a corrupted cache, or exhausted retries, so the original SC-006
could never be satisfied by any implementation of that design — it named a
test obligation the code has no way to exercise.

**What changed:** SC-006 now requires a satisfiable silent-success guard
instead: an exception raised during cache population (from any source, not
limited to the three originally-named mechanisms — e.g., a fault injected
into the step-loader or mission-type loader) must propagate to the caller
unchanged, nothing partial may be cached as a result, and the next call
after the fault must re-attempt population and succeed. The underlying
prohibition on silent success (CL-006, FR-006) is unchanged; only the test
mechanism SC-006 requires to verify it has been corrected to match the
approved design, instead of describing mechanisms the design does not
contain.

## Readiness Findings (cited, file:line-verified on this checkout)

These findings come from the readiness pass that opened this mission. Each
has been re-verified against the current checkout (commit reachable from
`fix/concurrent-template-config-race-4589`, scaffolded from `main`) before
being restated here; they are the starting point for research, not a
substitute for it (see CL-002).

- `src/charter/offering/missions/mission_step_repository.py:72` —
  `_YAML = YAML(typ="safe")`, a module-level singleton shared across
  threads, carrying an unverified inline comment claiming it is
  "thread-safe for reads."
- `src/charter/offering/missions/mission_step_repository.py:446` —
  `@functools.cache` decorates `_resolve_all_for_mission_type_cached`.
  `functools.cache`/`lru_cache` serializes access to the cache dict itself
  but does **not** serialize execution of the wrapped function body on a
  cache miss — two threads that miss concurrently can both run the cache-miss
  body (including any use of the shared `_YAML` instance) at the same time.
- `src/charter/offering/missions/mission_type_repository.py:68-101` —
  `MissionTypeRepository.default()` is itself `@functools.cache`-memoized
  (line 68) and its docstring documents a `cache_clear()` test seam (NFR-007
  contract) that must survive this mission's changes.
- `src/charter/offering/missions/mission_step_repository.py:324-333` —
  `MissionStepRepository.cache_clear()`, a public `@staticmethod` test seam
  (NFR-003 contract) that internally calls the private
  `_resolve_all_for_mission_type_cached.cache_clear()` — never call the
  private function's `.cache_clear()` directly from outside the module (its
  own docstring at lines 464-465 forbids it). Its docstring carries the same
  "production never mutates the bundled `mission-steps/` tree mid-process,
  so the cache is safe there" cache-safety argument as
  `mission_type_repository.py:68-101`; the plan phase must explicitly confirm
  this still holds after the fix, or consciously revise it with rationale.
- `src/charter/offering/missions/step_projection.py:105-126` —
  `project_template_set()` builds the `template_set` mapping from a single
  traversal of `iter_template_refs(steps)`; if a step's parse is corrupted or
  incomplete when this runs, the resulting mapping can silently omit a key
  without the caller receiving any signal that something went wrong.
- `src/specify_cli/runtime/resolver.py:499-505` — the resolver raises
  `TemplateConfigurationError(..., reason="is missing the requested mapping
  key.")` when `template_set.get(artifact_kind)` returns `None`. This is the
  exact exception and reason string observed in the CI failure; it is the
  **symptom's exit point**, not the defect's origin — the origin is presumed
  to be earlier, in the cache/template-set construction path above.

**Candidate blast radius** (confirmed to exist on this checkout by `ls`; do
not cite paths that do not exist here):

- `src/charter/offering/missions/mission_step_repository.py` (primary
  suspect: shared YAML singleton + cache-miss race)
- `src/charter/offering/missions/mission_type_repository.py` (downstream
  memoized consumer; carries its own `cache_clear()` seam)
- `src/charter/offering/missions/step_projection.py` (produces the
  `template_set` mapping; a source of a silently-dropped key if a step parse
  is corrupted mid-race)
- `src/charter/activation/resolver.py` (activation-side resolver; confirmed
  present on this checkout — scope its involvement during plan-phase
  research, not assumed here)
- `src/specify_cli/runtime/resolver.py` (symptom's raise site)
- `tests/core/test_mission_creation_identity.py` (the failing test and its
  neighbors; also the ATDD entry point per CL-004)

These files carry NFR-002/NFR-003/CL-001-style cache-contract docstrings
(see the `mission_type_repository.py:68-101` `default()` docstring, which
documents both an NFR-007 memoization contract and a `cache_clear()` test
seam used by other tests, and the `mission_step_repository.py:324-333`
`MissionStepRepository.cache_clear()` docstring, which documents the
parallel NFR-003 contract for the mission-steps cache) and `cache_clear()`
test seams used elsewhere in the suite. **This mission must preserve those
contracts and seams** — the fix must not remove or weaken `cache_clear()`,
must not de-memoize `MissionTypeRepository.default()` or
`_resolve_all_for_mission_type_cached()` as a shortcut past the concurrency
problem, and must keep the documented "production never mutates the bundled
trees mid-process" cache-safety argument intact in both files (or explicitly
and consciously revise it, with rationale, if research shows it no longer
holds).

**Corrected path note (charter "canonical sources, never improvise" / spec
overlay rule — verify every cited path against the live checkout):** the
readiness brief's phrasing "`src/doctrine/missions/` holds only the Python
package, not mission data" describes a path that **does not exist** on this
checkout — `src/doctrine/` has no `missions/` subdirectory at all. The actual
Python package implementing mission-step/mission-type resolution is
`src/charter/offering/missions/` (confirmed above). Similarly, the
`mission-tracer-files` doctrine procedure's own prose cites
`src/doctrine/templates/mission-tracer-files/`, but the templates actually
live at `src/charter/offering/templates/mission-tracer-files/` (confirmed
present, used to seed this mission's tracer stubs — see Tracer Files below).
Downstream plan/implementation work must cite the real, `ls`-verified paths,
not the stale ones in older prose.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer trusts that concurrent mission creation cannot corrupt template resolution (Priority: P1)

As a Spec Kitty maintainer running the CI suite (or a user running
`spec-kitty agent mission create` concurrently, e.g. two automation agents
provisioning missions at the same time), I want `create_mission_core` to
resolve mission-type template configuration correctly under concurrent load,
so that mission creation never intermittently raises
`TemplateConfigurationError` for a mission type/artifact-kind pair that is, in
fact, correctly configured.

**Why this priority**: This is the mission's entire reason to exist — a
latent thread-safety defect in the machinery every mission (including this
one) is scaffolded through. Left unfixed, it corrodes trust in a rare,
hard-to-reproduce way that erodes confidence in "main is green."

**Independent Test**: Run the new deterministic regression test (CL-003):
it fails on `fix/concurrent-template-config-race-4589`'s pre-fix commit and
passes after the fix commit, with no reliance on natural timing.

**Acceptance Scenarios**:

1. **Given** the commit on this mission's branch where the red-first
   regression test has just been committed but the production-fix commit
   has not yet landed (per CL-004's commit-ordering intent — the
   test-first commit, not a fixed pre-mission baseline; `planning_base_branch`
   is this mission's own single working branch and accumulates both commits),
   **When** the new Barrier-synchronized, instrumented regression test is run
   at that commit, **Then** it fails, demonstrating the forced interleaving
   reaches the unsafe code path (falsifiable: if it passes at that commit,
   the test is invalid per the CL-003 severity-4 bar).
2. **Given** the post-fix code, **When** the same regression test is run,
   **Then** it passes (falsifiable: if it still fails, the fix did not close
   the interleaving the test forces).
3. **Given** the pre-existing `test_concurrent_creates_no_collision` test,
   **When** run repeatedly (e.g., the readiness pass's 300-cold-subprocess-run
   protocol) both before and after the fix, **Then** it continues to pass at
   the same or better rate — the fix must not regress the existing natural
   test (falsifiable: any new natural failure introduced by the fix is a
   regression).

---

### User Story 2 - A reviewer can verify the fix without re-deriving the mission's decisions (Priority: P2)

As a reviewer (human or squad agent) auditing this mission's PR, I want the
spec's Clarifications section to state the operator's binding decisions,
the hypothesis-not-proven caveat, the red-first-by-construction bar, and the
reflexivity/silent-success/baseline statements explicitly, so that I can
check the implementation against a written bar instead of reconstructing
intent from the GitHub issue and mission chat history.

**Why this priority**: Prevents review drift on a mission whose defect was
never naturally observed — without an explicit bar, "looks fixed" becomes
the de facto acceptance criterion, which the charter's Standing Order 4
explicitly forbids.

**Independent Test**: A reviewer with only this spec.md and the PR diff (no
access to the original issue triage or prior chat) can determine whether the
regression test satisfies CL-003 and whether the fix preserves the
`cache_clear()` seams named in CL-001/Readiness Findings.

**Acceptance Scenarios**:

1. **Given** this spec's Clarifications section, **When** a reviewer checks
   the PR's regression test against CL-003, **Then** the reviewer can confirm
   red-before/green-after without needing to ask the implementer what the
   test "really" proves (falsifiable: if the reviewer must ask the
   implementer to explain what the test demonstrates, or must re-derive the
   red/green commits themselves because the PR does not make them checkable,
   this scenario has failed).
2. **Given** this spec's CL-007 reflexivity statement, **When** a reviewer
   checks the diff, **Then** the reviewer can confirm no on-disk schema,
   `meta.json` contract, or persisted mission-metadata format changed
   (falsifiable: any diff hunk touching the `step.yaml` format, the
   `MissionType`/`MissionStep` schemas, or the `meta.json` shape fails this
   scenario).

---

### User Story 3 - A future mission does not rediscover this as "still flaky" (Priority: P3)

As a future maintainer investigating a similar CI flake, I want this
mission's fresh baseline (CL-005) and research findings (CL-002) captured and
traceable, so that a subsequent investigation is not forced to re-run the
same 300/2000-trial reproduction sweep from scratch.

**Why this priority**: Lower priority than shipping the fix, but the charter's
tracer-files and research-citation doctrine exist precisely to prevent
re-derivation waste across missions.

**Independent Test**: `research.md` (or the plan's research notes) and the
tracer files record what was tried, what reproduced (or didn't), and why —
readable by a future mission without re-running the sweep.

**Acceptance Scenarios**:

1. **Given** this mission's research artifacts, **When** a future mission
   investigates a similar flake, **Then** it can find, in `research.md` (or
   the plan's research notes) and the tracer files, an explicit record of
   the hypothesis tested, the reproduction protocol used (e.g., the N
   cold-subprocess reruns and M Barrier-synchronized trial counts), and the
   result, without re-running any part of the sweep (falsifiable: if
   answering requires re-running the reproduction protocol or asking this
   mission's original authors, this scenario has failed).

### Edge Cases

- What happens when two threads request the **same** mission type and
  artifact kind concurrently (not just different mission slugs, as the
  existing test covers)? The fix must not introduce a deadlock or a
  correctness gap in this narrower, arguably higher-contention case.
- What happens when a lock (if the fix uses one) is held across an I/O-bound
  YAML parse and the underlying file is on a slow or contended filesystem
  (e.g., a network-mounted worktree)? The fix must not turn a rare race into
  a routine serialization bottleneck that violates the charter's < 2s CLI
  operation NFR.
- How does the system behave if `cache_clear()` is called concurrently with
  an in-flight cache-miss population (a test-seam scenario, not just a
  production scenario)? The existing `cache_clear()` test seams (used
  elsewhere in the suite) must not be broken or made non-deterministic by
  whatever locking mechanism is introduced.
- What happens if the forced-interleave regression test's instrumentation
  hook (monkeypatch) itself leaks between tests (e.g., a module-level patch
  that is not torn down)? The test must clean up after itself so it does not
  destabilize unrelated tests in the same session/process.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Research the causal hypothesis before fixing | As a mission implementer, I want the plan phase to investigate (not assume) whether the YAML-singleton-corruption theory explains the observed `TemplateConfigurationError`, including ruamel.yaml's actual thread-sharing behavior and functools.cache's cache-miss concurrency semantics, so that the fix targets a verified mechanism rather than a guess. | High | Open |
| FR-002 | Make template/step cache population concurrency-safe | As a maintainer, I want concurrent `create_mission_core` calls to never race on shared cache/YAML-loader state, so that `TemplateConfigurationError` is never raised for a correctly-configured mission type/artifact-kind pair. | High | Open |
| FR-003 | Preserve existing cache-contract seams | As a test author relying on `MissionTypeRepository.default.cache_clear()` and `MissionStepRepository.cache_clear()` (mission_step_repository.py:324-333) — the public seam that internally calls the private `_resolve_all_for_mission_type_cached.cache_clear()`, which must never be called directly from outside the module per that private function's own docstring — I want those seams to keep working exactly as documented (NFR-002/NFR-003/NFR-007 contracts), so that unrelated tests that depend on cache-clearing are not broken by this fix. | High | Open |
| FR-004 | Land a red-first, Barrier-synchronized regression test before the fix | As a reviewer, I want a deterministic, by-construction regression test committed before the production fix commit, so that red→green is directly demonstrable (ATDD, charter C-011). | High | Open |
| FR-005 | Reproduce through the pre-existing entry point | As a reviewer, I want the regression test to exercise `create_mission_core` (or the resolver path it drives) as its outer call, so that the test proves the production entry point is affected, not just an internal helper. | High | Open |
| FR-006 | Fail loudly on every cache/lock error path | As a maintainer, I want any exception encountered during cache population in the fix's new lock/cache code (e.g., a lock timeout, a corrupted-cache detection, or a retry-exhaustion path — if any such mechanism is ever introduced; the approved design (CL-008) introduces none of the three) to propagate as `TemplateConfigurationError` (or an equivalent explicit exception), never to return `None` or a partial template mapping, and never to leave a partial result cached for a subsequent call to inherit. | High | Open |
| FR-007 | Capture a fresh baseline before changing code | As a reviewer, I want this mission's own before/after test run recorded (not issue #3284's stale numbers), so that any pre-existing failure is correctly attributed. | Medium | Open |
| FR-008 | Record the operator's decision and the hypothesis caveat in the spec | As a reviewer, I want CL-001 through CL-007 present and substantively unchanged through plan/tasks/implement, so that downstream agents do not need to re-derive the decision from the GitHub issue. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No natural-timing-only regression test | The new regression test must force the unsafe interleaving deterministically (Barrier + instrumented hook or equivalent); a test whose pass/fail depends on natural OS thread scheduling alone does not satisfy FR-004. Falsifiable: run the new test 50 times in a row — it must produce the same red/green verdict every time relative to the code under test. | Reliability | High | Open |
| NFR-002 | No CLI performance regression | `spec-kitty agent mission create` (or an equivalent single-threaded `create_mission_core` call) must still complete in under 2 seconds for a typical project after the fix, per the charter's existing CLI performance standard. Falsifiable: time a single-threaded mission-create call before and after; a regression beyond the 2s bar fails this requirement. | Performance | Medium | Open |
| NFR-003 | Cache-clear seam determinism preserved | `MissionTypeRepository.default.cache_clear()` and `MissionStepRepository.cache_clear()` (mission_step_repository.py:324-333 — the public `@staticmethod` wrapper; it internally calls the private `_resolve_all_for_mission_type_cached.cache_clear()`, which that private function's own docstring forbids calling directly from outside the module) must remain synchronous, side-effect-free w.r.t. any new lock state (i.e., clearing the cache must not leave a lock held or in an inconsistent state), and must be callable repeatedly without error. Falsifiable: a test that calls `MissionStepRepository.cache_clear()` mid-population and asserts no deadlock/exception. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|-----------|----------|--------|
| C-001 | No on-disk schema or contract changes | This fix is in-process cache/concurrency behavior only. No `step.yaml` format, `MissionType`/`MissionStep` schema, `meta.json` contract, or persisted mission-metadata shape may change (CL-007). | Technical | High | Open |
| C-002 | No retry-to-green | The fix may not rely on retries, sleeps, or jitter to reduce the *observed* frequency of the race; it must remove the unsafe interleaving (CL-004, Standing Order 4). | Technical | High | Open |
| C-003 | Orchestrator-only GitHub actions | This mission's agents must not attempt to relabel the GitHub issue or file new tracker issues for unrelated pre-existing failures; both are the orchestrator's responsibility (CL-001, CL-005). | Process | Medium | Open |
| C-004 | Cite only checkout-verified paths | Any path named in plan/tasks/implementation artifacts must be verified to exist on the checkout with `ls` (or equivalent) before being cited, per the "canonical sources, never improvise" governing principle and this spec's own corrected-path note. | Process | Medium | Open |

### Key Entities

- **MissionStepRepository / `_YAML` singleton**: the module-level
  `ruamel.yaml.YAML(typ="safe")` instance in
  `src/charter/offering/missions/mission_step_repository.py` used to parse
  `step.yaml` files; central suspect for cross-thread state sharing.
- **`_resolve_all_for_mission_type_cached`**: the `functools.cache`-memoized
  function (line 446 of the same file) whose cache-miss body is the
  candidate race window.
- **`MissionTypeRepository.default()`**: the memoized repository singleton
  (`mission_type_repository.py:68-101`) that depends on the above and carries
  its own documented `cache_clear()` test seam.
- **`template_set`**: the `dict[str, str]` mapping from artifact kind (e.g.
  `"spec"`) to template filename, projected by `project_template_set()` in
  `step_projection.py`; a missing key here is the proximate cause of the
  observed `TemplateConfigurationError`.
- **`TemplateConfigurationError`**: the typed exception raised by
  `src/specify_cli/runtime/resolver.py` when template resolution fails; the
  symptom's exit point, not its origin.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deterministic, Barrier-synchronized regression test exists
  that fails on the pre-fix commit and passes on the post-fix commit (not a
  natural-timing test) — verified by running it against both commits.
- **SC-002**: The pre-existing `test_concurrent_creates_no_collision` test
  passes at least as reliably after the fix as the fresh baseline recorded
  before the fix (CL-005), across a repeated-run protocol comparable to the
  readiness pass's (e.g., N cold-subprocess reruns with zero failures on
  both sides, or an equal-or-better rate if any pre-existing flakiness is
  found and documented).
- **SC-003**: `MissionTypeRepository.default.cache_clear()` and
  `MissionStepRepository.cache_clear()` (mission_step_repository.py:324-333
  — the public `@staticmethod` wrapper; it internally calls the private
  `_resolve_all_for_mission_type_cached.cache_clear()`, which that private
  function's own docstring forbids calling directly from outside the
  module) remain present, callable, and behave per their existing
  NFR-002/NFR-003/NFR-007 docstring contracts — verified by the existing
  tests that depend on these seams continuing to pass unmodified (or
  modified only if the contract itself intentionally changed, with
  rationale recorded).
- **SC-004**: Single-threaded `create_mission_core` (or equivalent
  `spec-kitty agent mission create`) completes in under 2 seconds after the
  fix, matching the charter's existing CLI performance standard.
- **SC-005**: The GitHub issue #4589 is relabelled `type:fix` by the
  orchestrator at PR time (not by a mission agent) once the fix and its
  regression test are accepted.
- **SC-006**: An exception raised during cache population (e.g., a fault
  injected into the step-loader or mission-type loader) propagates to the
  caller unchanged — never converted into `None`, an empty mapping, or a
  partial `template_set` — and nothing partial is cached as a result of that
  failed population, so the next call re-attempts population and succeeds
  rather than being poisoned by the prior failure (CL-006, FR-006, CL-008) —
  verified by a test that fails if either (a) the propagation is replaced
  with a silent-degrade return, or (b) the failed population is cached, i.e.,
  a second call made after the fault does not re-attempt population.
