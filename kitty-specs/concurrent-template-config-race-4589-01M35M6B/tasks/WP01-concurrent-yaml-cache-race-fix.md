---
work_package_id: WP01
title: 'Concurrent YAML/cache race: thread-local instances + single-flight lock at both fix sites'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
planning_base_branch: fix/concurrent-template-config-race-4589
merge_target_branch: fix/concurrent-template-config-race-4589
branch_strategy: Planning artifacts for this mission were generated on fix/concurrent-template-config-race-4589. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/concurrent-template-config-race-4589 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
history: []
agent_profile: implementer-ivan
authoritative_surface: src/charter/offering/missions/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/missions/mission_step_repository.py
- src/charter/offering/missions/mission_type_repository.py
- tests/core/test_mission_creation_identity.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Concurrent YAML/cache race: thread-local instances + single-flight lock at both fix sites

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Close a latent thread-safety defect in mission-type/mission-step cache population — two module-level `ruamel.yaml.YAML(typ="safe")` singletons shared across threads with no locking, feeding `functools.cache`-wrapped functions whose cache-miss path is not serialized — by (1) landing a red-first regression test pair (OBL-1, OBL-2) plus a green-at-Base construction-invariant regression guard (OBL-3, no synchronization needed), OBL-2 driven via `threading.Barrier` for simultaneous entry and OBL-1 via a monkeypatch-forced pause, committed together for review-diff cohesion, proving the defect is real and reachable through `create_mission_core`, then (2) fixing both sites with thread-local YAML instances (6a) plus a single-flight per-key lock (6b) plus one new typed exception (6c), verified against a four-cell revert matrix and the full gate set.

## Context

**Why this WP exists.** `tests/core/test_mission_creation_identity.py::test_concurrent_creates_no_collision` flaked once in CI with `TemplateConfigurationError`. Research (see `research.md`, and `plan.md` Summary/Research-summary sections) confirmed the mechanism: `_YAML` (`src/charter/offering/missions/mission_step_repository.py:72`) and `_LAYERED_YAML` (`src/charter/offering/missions/mission_type_repository.py:318`) are process-lifetime singletons whose `.load()` mutates cross-call reader/scanner/parser/composer state with no synchronization; `functools.cache`'s cache-miss path never serializes the wrapped body. Two threads racing a cache miss can corrupt each other's parse; `_load_step_yaml`'s blanket `except Exception: return None` silently drops a `MissionStep`; a dropped step carrying a `template:` ref produces the observed error.

**This is the ONLY work package for this mission.** Per `plan.md` §14 ("confined to three files in one package plus one test file", commit phasing explicitly names one production-fix step and calls the whole sequence a single-PR flow), the diff is small and single-concern: two singleton replacements, two single-flight-lock-guarded call sites, one new exception class, five test obligations covering both sites. A structural WP split (owned-files conflict, or a real parallelization boundary that doesn't cut across the red→green ATDD contract) was checked for and not found — the fix sites share one lock helper (`_lock_for`) and one exception class, and splitting the red-first test commit from the fix commit across two WPs would break the single-lane ATDD ordering C-011 requires. The orchestrator also confirmed, before this WP was authored, that the 7 currently-open PRs on `spec-kitty/spec-kitty` do not touch `charter/offering/missions`, `mission_step_repository.py`, `mission_type_repository.py`, or `test_mission_creation_identity.py` — no write-scope overlap with any in-flight PR.

**Campsite-clean: NONE planned for this WP.** `plan.md` §12 re-read the exact touched lines and found no genuine pre-existing debt worth a distinct commit — the "thread-safe for reads" comment at `mission_step_repository.py:69` is the misconception this fix corrects in place, not separate debt. Do not open a campsite-clean subtask or commit.

**Reflexivity (CL-007).** This is in-process cache/concurrency behavior only. No `step.yaml` format, `MissionType`/`MissionStep` schema, or `meta.json` shape may change (C-001). Your own mission's `meta.json`/scaffold already ran through the machinery you are fixing — that is expected and unaffected.

### The two fix sites (plan.md §1)

- **PRIMARY_SITE** — `src/charter/offering/missions/mission_step_repository.py`: `_YAML` singleton (line 72), `_resolve_all_for_mission_type_cached` (lines 446-470), `_resolve_all_for_mission_type_uncached` (lines 335-364), `_load_step_yaml` (swallows all exceptions, lines 132-135), `_add_step_ids_from_dir` (lines 163-169, no surrounding try/except), `MissionStepRepository.cache_clear()` (staticmethod, lines 323-333).
- **SECOND_SITE** — `src/charter/offering/missions/mission_type_repository.py`: `_LAYERED_YAML` singleton (line 318), `resolve_layered_mission_types` (currently itself the `@functools.cache`-decorated, `__all__`-exported function, lines 477-601), `_load_layered_mission_type_file` (catches only `YAMLError`, re-raises as `ValueError`, lines 388-391), `MissionTypeRepository.cache_clear()` (staticmethod, NOT `.default`, lines 188-206).
- **OUT OF SCOPE**: `src/charter/activation/resolver.py` (unrelated charter-selection scalar), `src/charter/offering/missions/step_projection.py` (read-only, pure functions, no change needed), `src/specify_cli/runtime/resolver.py` (existing raise sites already satisfy CL-006, left unmodified), three other dormant `YAML(typ="safe")` singletons named in plan.md §1 (`lint.py:66`, `operating_procedures.py:41`, `extractor.py:51` — none has a threaded or memoized caller today; do not touch them).

### 6a — thread-local YAML instances (plan.md §6a)

Replace each module-level singleton with a `threading.local()`-backed accessor, one per file:

```python
_yaml_local = threading.local()

def _get_yaml() -> YAML:
    try:
        return _yaml_local.instance
    except AttributeError:
        instance = YAML(typ="safe")
        _yaml_local.instance = instance
        return instance
```

Replace every `_YAML.load(...)` / `_LAYERED_YAML.load(...)` call with `_get_yaml().load(...)`. No lock is needed for this half — each thread's parser state is private to that thread for the process's lifetime.

### 6b — single-flight per-key lock around the WHOLE cached call (plan.md §6b — round-4 design, binding)

**Do not** put the lock inside the `functools.cache`-wrapped body (round-3's design; the arbiter rejected it — see `reviews/plan.ruling.md` PLAN-FRESH3-DEBBIE-001/ARB-001: a lock only inside the body lets two threads each independently run the walk, count is 2 not 1). The lock must wrap the **entire** cached call so a losing thread's call becomes a `functools.cache` *hit*, not a second walk:

```python
_locks_guard = threading.Lock()
_locks: dict[tuple, threading.Lock] = {}

def _lock_for(key: tuple) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock
```

**PRIMARY_SITE** already has a public/cached split (`resolve_all_for_mission_type` / `_resolve_all_for_mission_type_cached`) — wrap the public entry point:

```python
def resolve_all_for_mission_type(self, mission_type_id, pack_context=None):
    key = (self._builtin_root, mission_type_id, pack_context)
    with _lock_for(key):
        return _resolve_all_for_mission_type_cached(self._builtin_root, mission_type_id, pack_context)
```

**SECOND_SITE has no such split today** — `resolve_layered_mission_types` IS the `@functools.cache`-decorated, `__all__`-exported function. You must create one: rename the current cached function to a new private name `_resolve_layered_mission_types_cached`, and make `resolve_layered_mission_types` the public lock-wrapping wrapper, same shape as PRIMARY_SITE:

```python
def resolve_layered_mission_types(mission_types_dirs, pack_context):
    key = (mission_types_dirs, pack_context)
    with _lock_for(key):
        return _resolve_layered_mission_types_cached(mission_types_dirs, pack_context)

resolve_layered_mission_types.cache_clear = _resolve_layered_mission_types_cached.cache_clear
resolve_layered_mission_types.cache_info = _resolve_layered_mission_types_cached.cache_info
resolve_layered_mission_types.cache_parameters = _resolve_layered_mission_types_cached.cache_parameters
```

**Binding requirement — do NOT use `functools.update_wrapper`.** It copies `__wrapped__`/`__doc__`/`__name__`/`__module__`/`__dict__`, never `cache_clear`/`cache_info`/`cache_parameters` (those are attributes `functools.cache` itself sets on the decorated callable). Use the three explicit binding lines shown above. **14 existing call sites depend on this**: 12 direct `.cache_clear()` calls across `tests/charter/test_mission_type_path_layout_ssot.py`, `tests/doctrine/missions/test_mission_type_repository.py`, `tests/charter/test_charter_import_time_io.py`, plus `MissionTypeRepository.cache_clear()`'s own body (`mission_type_repository.py:207`), plus one `.cache_info()` call inside `tests/charter/test_charter_import_time_io.py`'s in-subprocess `_IMPORT_SPY_SCRIPT` (line ~231) that asserts NFR-004's "never called at charter-module import time" bound (12 + 1 + 1 = 14). **Re-run `tests/charter/test_charter_import_time_io.py` explicitly** after this split — it is the file the mission's binding instructions single out by name; it must stay green.

Also extract the walk body currently inline in `resolve_layered_mission_types` into a **new** `_resolve_layered_mission_types_uncached(mission_types_dirs, pack_context)` (mirrors PRIMARY_SITE's own uncached/cached split) — this is the unit OBL-2 must count invocations of (see below); `_resolve_layered_mission_types_cached` then just calls it under `@functools.cache`.

**Per-site key shapes (plan.md §7/§8a — bind your test constructions to these, do not invent your own):**

| | PRIMARY_SITE | SECOND_SITE |
|---|---|---|
| Cache key | `(builtin_root, mission_type_id, pack_context)` — 3-tuple | `(mission_types_dirs, pack_context)` — 2-tuple |
| Do concurrent `create_mission_core` calls in one project share a key? | Only when `mission_type_id` AND `pack_context` both match | **Yes, by default** — `_resolve_action_slot` always passes the identical fixed `mission_types_dirs`, so every concurrent create in one project (one `pack_context`) shares ONE key regardless of mission type |
| What does one population contain? | The WHOLE `_resolve_all_for_mission_type_uncached` walk — every `step_id` across built-in+org+project layers for one mission type | The WHOLE per-key walk — every `*.yaml` file across every scanned layer (4 built-in files today: `documentation`, `plan`, `research`, `software-dev`) |
| Loader catch semantics | `_load_step_yaml` swallows EVERY exception (`except Exception: return None`) | `_load_layered_mission_type_file` catches only `YAMLError`→`ValueError`; anything else propagates uncaught |
| Site's own cache-clear seam | `MissionStepRepository.cache_clear()` | `MissionTypeRepository.cache_clear()` (NOT `.default` — that clears a *different*, independent cache; see plan.md §5) |
| Other unguarded users of the shared YAML instance | None in `src/` (only caller is the cached path itself) | `src/charter/activation/pack_manager.py:1014` calls `scan_mission_types_dir` directly, bypassing the cache/lock entirely — named as an alternate/backup construction for OBL-1's second-site 6a-proof if the resolver-path-direct construction proves unworkable |

### 6c — one new exception, raise-never-degrade (plan.md §6c)

Define `MissionCacheLockError(ValueError)` in `mission_step_repository.py` (the primary fix site — owned by `src/charter/offering/missions/`), following the existing local-typed-exception pattern (`MalformedManifestError`, `ActionIndexError` — both module-local, neither imports `specify_cli`). Import it into `mission_type_repository.py` (mirroring the existing `from .mission_step_repository import MissionStepRepository, _PackContextLike` import at line 12). **Never import `TemplateConfigurationError` into `src/charter/**`** — it lives at `src/specify_cli/runtime/resolver.py:71`, one layer above the enforced dependency direction (`kernel <- charter <- glossary/runtime <- specify_cli`); `tests/architectural/test_charter_no_specify_cli_import.py::test_charter_never_imports_specify_cli` is an always-on, PR-blocking gate that fires on this exact violation. This plan's design introduces no lock-timeout/corrupted-cache/retry-exhaustion path (CL-008 amendment — the operator corrected SC-006 for exactly this reason), so `MissionCacheLockError` has no forced call site from 6a/6b alone; define it for completeness/future-proofing per the plan's decision, and ensure nothing in your new code swallows an exception instead of letting it propagate (OBL-3, below).

### Test obligations — full table (plan.md §8b, transcribed, binding)

Five obligations, OBL-1 through OBL-5, each covering **both** sites (10 concrete test cases minimum). Do not invent a 6th or drop one.

| Test | Traces | Observable property | Fix half isolated | Revert-cell behavior |
|---|---|---|---|---|
| **OBL-1** — forced-interleave content-correctness, **distinct** cache keys | FR-002/FR-004/FR-005, CL-003/CL-004, SC-001, US1 AC1/AC2 | Two threads racing **distinct** keys at one site, driven through `create_mission_core` (PRIMARY_SITE) or the resolver path it drives (SECOND_SITE), never corrupt each other's captured result. Assert field-by-field against a known-good reference, per-thread-captured — never a post-join re-read of the now-memoized cache. | **6a**. 6b's per-key lock structurally cannot serialize a distinct-key race (different keys → different `Lock` objects → no contention), so this test is unreachable by 6b alone. | Base: RED both sites. 6a+6b: GREEN both sites. 6a reverted/6b kept: RED both sites (6b's lock never engages). 6b reverted/6a kept: GREEN both sites (6a alone removes the shared object). |
| **OBL-2** — redundant-population COUNT, **same** cache key | FR-002, spec.md Edge Cases, SC-001 | Two threads racing the IDENTICAL key, entering via a `threading.Barrier` for simultaneous entry (no long pause needed), cause the per-key walk unit to execute exactly ONCE, never twice. Count `_resolve_all_for_mission_type_uncached` invocations at PRIMARY_SITE; count the NEW `_resolve_layered_mission_types_uncached` invocations at SECOND_SITE. **Counting `_load_layered_mission_type_file` is WRONG** — it runs once per file (4x per population). | **6b**. Not distinguishable from a passing correctness test once 6a is present — the only test that can tell "6b present" from "6b silently reverted." | Base: RED both sites (trivially — no lock seam exists yet). 6a+6b: GREEN both sites, count==1. 6a reverted/6b kept: GREEN both sites, count stays 1 (6b alone still serializes to one population; the *result* may be corrupt, which is OBL-1's concern, not OBL-2's). 6b reverted/6a kept: RED both sites, count==2. |
| **OBL-3** — amended-SC-006 raise-not-degrade regression guard | FR-006, CL-006, SC-006 (as amended by CL-008) | A fault injected into a site's cache-population path (1) propagates to the caller unchanged, never converted to `None`/empty/partial, (2) leaves nothing partial cached, (3) a subsequent call re-attempts and succeeds. | **None** — construction-invariant. `functools.cache` never stores a result for a raising call; neither 6a nor 6b adds a catch-and-degrade branch (a `with _lock_for(key):` block does not suppress an exception raised inside it). | **ALREADY GREEN AT BASE, both sites — this is NOT red-first.** Committed alongside the red obligations for review-diff cohesion only. Stays green through every revert cell. |
| **OBL-4** — existing natural test unmodified | AC3/SC-002, NFR-001 | `test_concurrent_creates_no_collision` (already exists, `tests/core/test_mission_creation_identity.py` line ~132) keeps passing, unmodified, before and after. | None — sanity net, not a revert-discipline instrument (research.md: 0/300 cold-subprocess reruns naturally reproduce the race). | Green in every cell including every revert. Do not modify this test's body. |
| **OBL-5** — `cache_clear()` mid-population, no deadlock | NFR-003, spec.md Edge Cases | Calling the site's own `cache_clear()` while a population is in flight neither deadlocks nor raises; the in-flight population still completes with a correct result once released. | 6b interacting correctly with the cache-clear contract. | Not applicable pre-fix (no lock exists at Base to test). Green post-fix, both sites. 6a reverted/6b kept: green. 6b reverted/6a kept: **run and green, trivially** — with 6b's lock reverted, `cache_clear()` has nothing to race against a population in flight, so no deadlock is structurally possible and this cell's assertion is vacuously satisfiable; still run it and record the result. |

### Revert matrix (plan.md §8c — the Definition of Done must verify all four rows)

| State | Required result |
|---|---|
| Base (current HEAD, no fix code) | OBL-1 red both sites; OBL-2 red both sites (trivial "seam absent" reason); **OBL-3 already green both sites** |
| 6a+6b applied | OBL-1 through OBL-5 all green, both sites, no deadlock |
| 6a reverted, 6b kept | OBL-1 red both sites; OBL-2/3/4/5 unaffected (still green) |
| 6b reverted, 6a kept | OBL-2 red both sites (count becomes 2); OBL-1/3/4 unaffected (still green); OBL-5 still green, run and trivially satisfied — with 6b's lock gone, `cache_clear()` has nothing to race against a population in flight, so no deadlock is possible and this cell's assertion is vacuous but still asserted |

### Binding constraints on any harness (plan.md §8d — transcribed verbatim in substance, do not weaken)

1. The pin distinguishing the "paused" thread's target is by **file identity** inside the shared load window — never call order or iteration order (PRIMARY_SITE's walk iterates an unsorted `set`, so iteration order is not a valid pin there).
2. The timing seam must exist, **unedited**, at both the red commit and the green commit. `_YAML.load`/`_LAYERED_YAML.load` (module-level instance attrs) don't exist post-6a. Plan §9 names the candidate: a **class-level hook on `ruamel.yaml.main.YAML` itself** (both the pre-fix singleton and the post-fix thread-local instance are instances of the same class), combined with a **path-aware predicate** at `_load_step_yaml(step_file)` / `_load_layered_mission_type_file(yaml_file, ...)` — both keep their name and `Path` argument pre- and post-fix. The pause must land strictly inside the shared instance's load window — **after `self.reader.stream` is assigned, before composition completes**. The exact hook (e.g. inside `YAML.get_constructor_parser` or the reader/composer chain it returns) is your spike's output (Subtask T001), not fixed by the plan.
3. No lock is held across a barrier the other thread needs — OBL-1's distinct-key construction is safe by construction; **never pair a long paused-while-holding-the-lock thread with another thread racing the SAME key** (that pairing belongs only to OBL-2, which needs only a `threading.Barrier` for simultaneous entry, not a long pause).
4. Teardown is function-scoped (pytest `monkeypatch`, auto-reverted) — never a bare module-level patch left in place.
5. The count OBL-2 asserts guards **populations** (the whole per-key walk unit), never per-file loader calls.
6. NFR-001 determinism verified across **SEPARATE PROCESSES with varied `PYTHONHASHSEED`**, not one in-process loop (a single process keeps one hash seed for its life; PRIMARY_SITE's unsorted-set order depends on it).
7. CL-004's outer-call rule: PRIMARY_SITE's and SECOND_SITE's default (same-`pack_context`) obligations drive through `create_mission_core`. SECOND_SITE's OBL-1 distinct-`pack_context` construction drives `resolve_mission_type_context`/`_resolve_action_slot` **directly** — NOT through the existing `_run_create`/`_patched_mission_creation_context` test helper (`tests/core/test_mission_creation_identity.py:54-70`), which uses process-global `unittest.mock.patch`, unsafe for two distinct project roots racing in two threads. This is the ONE place the outer-call rule is deliberately relaxed (plan.md §8b's WP caution, ARB-002 point 3) — the monkeypatch still only forces the pause, it never replaces the resolver call itself.

### OBL-3's fault-injection seam, per site (plan.md §9)

- **SECOND_SITE**: the loader already propagates (`_load_layered_mission_type_file` catches only `YAMLError`, re-raises as `ValueError`). Patch `_load_layered_mission_type_file` (or `MissionType.model_validate`, which it calls unguarded) to raise a distinct forced exception — a direct, real construction.
- **PRIMARY_SITE**: `_load_step_yaml` swallows everything, so inject **OUTSIDE** it — patch `_add_step_ids_from_dir` (`mission_step_repository.py:163-169`, called from `_resolve_all_for_mission_type_uncached` with no surrounding try/except) to raise. This target is unchanged by both 6a (touches only the YAML singleton/accessor) and 6b (touches only the call site) — a stable pin across the red and green commits.

### Illustrative, NON-NORMATIVE sketch (plan.md §9 — you are free to build differently as long as §8's obligations and §8d's constraints hold)

```python
@dataclass(frozen=True)
class _FixSiteCase:
    site_id: str
    site_cache_clear: str
    walk_unit: str
    distinct_key_race: tuple[str, str]
    same_key_race: str

PRIMARY_SITE = _FixSiteCase(
    site_id="primary",
    site_cache_clear="MissionStepRepository.cache_clear",
    walk_unit="MissionStepRepository._resolve_all_for_mission_type_uncached",
    distinct_key_race=("software-dev", "documentation"),
    same_key_race="software-dev",
)
SECOND_SITE = _FixSiteCase(
    site_id="second",
    site_cache_clear="MissionTypeRepository.cache_clear",  # NOT .default
    walk_unit="charter.offering.missions.mission_type_repository._resolve_layered_mission_types_uncached",
    distinct_key_race=("project-a", "project-b"),  # two distinct pack_contexts, via resolver path directly
    same_key_race="default-project",
)

def _cold_cache() -> None:
    MissionStepRepository.cache_clear()
    MissionTypeRepository.default.cache_clear()
    MissionTypeRepository.cache_clear()  # Section 5's second, independent seam
```

Label this sketch non-normative if you reference it in your own test code comments — it is a starting shape, not a contract.

### Gate set and baseline (plan.md §10/§11 — verified, not guessed)

Five CI modules select for this diff, confirmed by actually running `scripts.ci.gate_selection.select_modules`: **missions, core_misc, charter, unit, specify_cli_runtime**. All five are fully green at baseline commit `288aef2f9`. Do not trust a hardcoded "current HEAD" hash for this claim — more commits (chore/tracer/tasks commits) land on this mission branch between tasks-authoring and implementation time, so any specific HEAD hash cited here will go stale. Instead, **re-run `git diff --stat 288aef2f9 -- src tests` at implementation time and confirm it is empty**; as long as that diff is empty, `288aef2f9` remains the valid baseline regardless of what the current HEAD hash actually is. You must re-run, post-fix, and require green:

- `tests/missions` (319 passed baseline)
- `tests/core` plus the other 8 `core_misc` test_dirs: `tests/specify_cli/core`, `tests/coordination`, `tests/specify_cli/coordination`, `tests/decisions`, `tests/doctrine_synthesizer`, `tests/specify_cli/tool_surface`, `tests/specify_cli/asset_preservation`, `tests/zeitgeist_client`
- `tests/charter` and `tests/doctrine` (`tests/doctrine/missions/test_mission_step_resolver.py` and `test_mission_type_repository.py` — including `TestLayeredMissionTypesCacheKeyAndClear.test_same_key_is_a_cache_hit` at line 660 — are the dedicated suites for both fix sites and must stay green)
- `tests/unit`
- `tests/specify_cli/runtime`
- `tests/charter/test_charter_import_time_io.py` specifically re-run to confirm the forwarded `.cache_info()` seam on the SECOND_SITE public wrapper stays green

Use `.venv/bin/python -m pytest` (this checkout's `.venv` has the `test` extra synced) — **never bare `pytest`, never `~/.local/bin`**. NFR-002: single-threaded `create_mission_core` (or `spec-kitty agent mission create`) must stay under 2 seconds after the fix.

### Commit phasing (plan.md §14 — binding structure for this WP's own commits)

One PR to `main` eventually (not this WP's job — the WP lands its commits on this mission's own branch). Inside this WP, in order:

1. ~~Campsite-clean~~ — skipped (§12, see Context above).
2. **Red-first failing-test commit** (charter C-011 ATDD-first): OBL-1 + OBL-2 + OBL-3 (both sites each), committed against pre-fix code via `spec-kitty safe-commit`. Own commit, separate from and before the fix. OBL-1 is the load-bearing red. OBL-2 is red only in the trivial "seam absent" sense. **State explicitly in the commit message or PR-facing notes that OBL-3 is already green at this commit** — never claim it red-first.
3. **Production-fix commit(s)**: 6a + 6b (both sites) + 6c, verified the SAME tests now green for both sites, plus OBL-5, OBL-4 (still green, unmodified), `tests/charter/test_charter_import_time_io.py`, and all five gate-set modules' full suites green.
4. **Doc/tracer commit**: append (never replace/renumber) entries to `kitty-specs/concurrent-template-config-race-4589-01M35M6B/traces/{approach,design-decisions,tooling-friction}.md`.

---

### Subtask T001: Spike the timing seam and confirm OBL-3's fault-injection seam

**Purpose**: Before writing any test, establish the concrete, working timing-pause hook required by binding constraint 2 above, and confirm the two OBL-3 fault-injection points actually propagate as expected pre-fix.

**Steps**:
1. Prototype a class-level hook on `ruamel.yaml.main.YAML` (or the reader/composer chain `YAML.get_constructor_parser` returns) that can pause execution strictly between `self.reader.stream` assignment and composition completion, combined with a path-aware predicate keyed on the `Path` argument passed to `_load_step_yaml`/`_load_layered_mission_type_file`. Verify empirically (a throwaway script or `python -c` session against this checkout) that the pause actually lands where research.md's traced mechanism requires — not merely "before or after `.load()`", which the round-3 arbiter finding (DEBBIE-002) rejected.
2. Confirm the hook target is invariant across the pre-fix and post-fix code shape: `_load_step_yaml(step_file)` and `_load_layered_mission_type_file(yaml_file, ...)` must keep their name and `Path` argument through your own 6a/6b changes (verify this holds once you draft 6a in T003, or at minimum verify by inspection now that your planned 6a change does not alter either function's signature).
3. Confirm the OBL-3 fault-injection points work as described: patch `_add_step_ids_from_dir` (PRIMARY_SITE) and `_load_layered_mission_type_file`/`MissionType.model_validate` (SECOND_SITE) to raise, and confirm — by a scratch/throwaway run against the CURRENT pre-fix code — that the exception propagates uncaught through `resolve_all_for_mission_type` / `resolve_layered_mission_types` to the caller, is never converted to `None`/partial, and nothing is cached (a second call after the fault re-attempts and succeeds once the patch is removed).
4. Do not commit any throwaway spike script; fold the working hook directly into T002's test module.

**Files**: none committed by this subtask (spike only).
**Validation**: You can articulate, in your own words, exactly where the pause lands (which ruamel internal call, which attribute state at pause time) and why it survives both the red and green commits; you have empirically observed both OBL-3 fault points propagate pre-fix.

### Subtask T002: Write and commit the red-first test pair plus the green-at-Base OBL-3 guard (OBL-1 + OBL-2 + OBL-3, both sites)

**Purpose**: Land the ATDD red-first commit (C-011) — OBL-1 and OBL-2 red-first, plus OBL-3 (already green at Base, a regression guard, not red-first evidence) committed alongside them for review-diff cohesion — each covering PRIMARY_SITE and SECOND_SITE, added to the existing `tests/core/test_mission_creation_identity.py` (it already holds OBL-4's `test_concurrent_creates_no_collision` at line ~132 — this matches plan.md §14's "confined to ... one test file" claim literally). Only create a new sibling test file, with `create_intent` declared, if you hit a concrete technical reason this file cannot hold the new tests, and state that reason in your commit/PR notes.

**Steps**:
1. Using T001's timing hook, write OBL-1's PRIMARY_SITE case: two threads racing **distinct** `mission_type_id`s (e.g. `software-dev`, `documentation`) through `create_mission_core`, one paused mid-load via the file-identity pin, asserting the paused thread's own captured result is correct (field-by-field against a known-good reference), never corrupted.
2. Write OBL-1's SECOND_SITE case: two threads racing **distinct** `pack_context`s (e.g. two `tmp_path`-rooted projects), driven **directly** through `resolve_mission_type_context`/`_resolve_action_slot` per binding constraint 7 (NOT through `_run_create`). If this construction proves unworkable, fall back to the noted alternate: driving through `pack_manager.py:1014`'s direct `scan_mission_types_dir` call, which also bypasses the lock entirely.
3. Write OBL-2's PRIMARY_SITE and SECOND_SITE cases: two threads racing the **same** key, synchronized via `threading.Barrier` for simultaneous entry (no long pause), instrumenting/counting invocations of `_resolve_all_for_mission_type_uncached` (PRIMARY_SITE) and the new `_resolve_layered_mission_types_uncached` you will extract in T004 (SECOND_SITE — since this function does not exist pre-fix, write OBL-2's SECOND_SITE assertion against whatever currently constitutes "the walk," e.g. instrument the inline walk body's entry today, and note in a comment that T004 will make the counted symbol exist by name; the count must still assert `== 1` post-fix and the test must fail pre-fix for the trivial "no lock exists" reason).
4. Write OBL-3's PRIMARY_SITE and SECOND_SITE cases per the fault-injection seams above. **These must pass immediately, against current pre-fix code** — do not treat a passing OBL-3 as a bug in your test; it is the plan's documented, deliberate green-at-Base obligation.
5. Ensure every new test uses function-scoped `pytest` `monkeypatch` for all patches (binding constraint 4) and starts with every cache it races provably cold (call the site's own `cache_clear()` seam(s) — `MissionStepRepository.cache_clear()`, `MissionTypeRepository.cache_clear()` (NOT `.default`) — before racing).
6. Run the new tests against current HEAD and confirm: OBL-1 RED both sites, OBL-2 RED both sites (trivial reason), OBL-3 GREEN both sites, OBL-4 (existing, untouched) still GREEN.
7. Commit via `spec-kitty safe-commit` as its own commit, separate from and before any production code change. State plainly in the commit message that OBL-3 is committed green (regression guard, not red-first).

**Files**: `tests/core/test_mission_creation_identity.py` (extended, +~250-400 lines of new test code and helpers).
**Validation**: `env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_identity.py -v` shows OBL-1/OBL-2 new tests FAILING, OBL-3/OBL-4 PASSING, at this commit.

### Subtask T003: Implement 6a at both sites (thread-local YAML accessor)

**Purpose**: Remove the shared mutable YAML state — the primary fix, per plan.md §6a.

**Steps**:
1. In `mission_step_repository.py`: replace `_YAML = YAML(typ="safe")` (line 72) with `_yaml_local = threading.local()` and a `_get_yaml() -> YAML` helper as shown in Context above. Replace every `_YAML.load(...)` call site with `_get_yaml().load(...)`.
2. In `mission_type_repository.py`: replace `_LAYERED_YAML = YAML(typ="safe")` (line 318) with the same pattern (a second, independent `_yaml_local`/`_get_yaml` pair — do not share the thread-local object across the two modules; each site gets its own).
3. Remove or correct the stale "thread-safe for reads" comment near the old singleton declarations (this is the functional correction, per plan.md §12 — not a separate campsite-clean step).
4. Do not change either `_load_step_yaml(step_file)`'s or `_load_layered_mission_type_file(yaml_file, ...)`'s name or `Path` argument — T001/T002's timing seam depends on both surviving unedited.
5. Run OBL-1 both sites: expect GREEN now. Run OBL-2 both sites: still RED (6b not yet implemented) — this is expected and correct per the revert matrix's "6a reverted, 6b kept" is the mirror image; at this exact intermediate point you are at "6a kept, 6b not yet present," which the revert matrix does not name directly, but OBL-2 staying red here is consistent with the "6b reverted, 6a kept" row.

**Files**: `mission_step_repository.py` (~15-25 line diff), `mission_type_repository.py` (~15-25 line diff).
**Validation**: OBL-1 green both sites; OBL-4 still green; no other test in the two files' dedicated suites regresses (`tests/doctrine/missions/test_mission_step_resolver.py`, `tests/doctrine/missions/test_mission_type_repository.py`).

### Subtask T004: Implement 6b at both sites (single-flight lock, public/private split, attribute forwarding)

**Purpose**: Close the redundant-population window with a per-key lock that wraps the entire cached call — the round-4 design plan.md §6b requires, not the rejected round-3 inside-the-body design.

**Steps**:
1. Add the shared `_locks_guard`/`_locks`/`_lock_for(key)` helper to `mission_step_repository.py` (module-level, alongside 6a's additions and 6c's exception — see T005).
2. Wrap `resolve_all_for_mission_type` (PRIMARY_SITE's already-existing public entry point) with `with _lock_for(key): return _resolve_all_for_mission_type_cached(...)`, keyed on `(self._builtin_root, mission_type_id, pack_context)`.
3. At SECOND_SITE, perform the required split: rename the current `@functools.cache`-decorated `resolve_layered_mission_types` body to a new private `_resolve_layered_mission_types_cached`. Extract the walk (the `index` init, the always-executed `mission_types_dirs` loop, the `pack_context` org/project branch, and the return) into a new `_resolve_layered_mission_types_uncached(mission_types_dirs, pack_context)`, called by `_resolve_layered_mission_types_cached` under `@functools.cache`. Make `resolve_layered_mission_types` the new public lock-wrapping wrapper (same name, same signature, so `__all__` and every import site is unchanged), keyed on `(mission_types_dirs, pack_context)`, importing `_lock_for` from `mission_step_repository`.
4. Bind `.cache_clear`, `.cache_info`, `.cache_parameters` on the new public `resolve_layered_mission_types` wrapper via three explicit assignment lines forwarding to `_resolve_layered_mission_types_cached`'s own attributes — **not** `functools.update_wrapper`.
5. Confirm `MissionTypeRepository.cache_clear()`'s own body (line ~207) needs **no change** — it already calls `resolve_layered_mission_types.cache_clear()`, which now forwards correctly.
6. Run OBL-2 both sites: expect GREEN, count==1. Run OBL-1 both sites: still GREEN (6a is unaffected by this change). Run OBL-5 both sites (write these test cases now if not already present from T002 — OBL-5 was listed as part of T002's obligations in the fact table but its concrete implementation depends on 6b existing; if you deferred OBL-5's test body to this subtask, write it now: call the site's `cache_clear()` from one thread while another is mid-population — via the same timing hook — and assert no deadlock/exception, and the in-flight population still completes correctly).
7. Re-run `tests/charter/test_charter_import_time_io.py` explicitly and confirm it stays green — this is the file the mission's binding instructions single out by name for the forwarded `.cache_info()` seam.
8. Re-run `tests/doctrine/missions/test_mission_type_repository.py::TestLayeredMissionTypesCacheKeyAndClear::test_same_key_is_a_cache_hit` explicitly and confirm it stays green — the single-flight lock changes only *when* `functools.cache`'s dict is written, never *whether* a same-key second call is a hit.

**Files**: `mission_step_repository.py` (adds `_locks_guard`/`_locks`/`_lock_for`, wraps `resolve_all_for_mission_type`), `mission_type_repository.py` (adds the public/private split, the lock wrap, the three forwarding lines), `tests/core/test_mission_creation_identity.py` (OBL-5 bodies, if deferred from T002).
**Validation**: OBL-1 through OBL-5 all green, both sites; `test_charter_import_time_io.py` green; `test_same_key_is_a_cache_hit` green.

### Subtask T005: Implement 6c — `MissionCacheLockError` exception, charter-boundary-safe

**Purpose**: One new exception class satisfying CL-006's raise-never-degrade contract without violating the `charter -> specify_cli` import-direction gate.

**Steps**:
1. Define `class MissionCacheLockError(ValueError): ...` in `mission_step_repository.py`, alongside `MalformedManifestError`/`ActionIndexError`'s existing pattern in this package — no docstring copy-paste, write one specific to this class's purpose (raised by lock/cache-population code in this package on an unrecoverable population failure; never returns `None`/partial).
2. Import it into `mission_type_repository.py`: `from .mission_step_repository import MissionCacheLockError` (add to the existing import line that already pulls `MissionStepRepository, _PackContextLike` from the same module, or add a new import line — either is fine as long as it's a relative, intra-package import).
3. Confirm by grep that neither file imports anything from `specify_cli` — run `grep -n "specify_cli" src/charter/offering/missions/mission_step_repository.py src/charter/offering/missions/mission_type_repository.py` and confirm no match (or only match inside a comment/docstring that is not a live import).
4. Run `tests/architectural/test_charter_no_specify_cli_import.py::test_charter_never_imports_specify_cli` explicitly and confirm green.
5. Confirm no code path in 6a/6b catches an exception and returns a degraded value instead of propagating it or raising `MissionCacheLockError` — re-run OBL-3 both sites and confirm still green (it should not have changed shape).

**Files**: `mission_step_repository.py` (+~10 lines, the exception class), `mission_type_repository.py` (+1 import line).
**Validation**: `tests/architectural/test_charter_no_specify_cli_import.py` green; OBL-3 still green both sites.

### Subtask T006: Verify the full revert matrix, OBL-4/OBL-5, all five gate-set modules, NFR-002 timing, NFR-001 cross-process determinism; commit the production fix

**Purpose**: Prove the fix is both necessary and sufficient by mechanically reverting each half and re-running the obligation suite, then land the production-fix commit.

**Steps**:
1. With 6a+6b+6c fully applied: run OBL-1 through OBL-5 at both sites — all green, no deadlock. Run OBL-4 (`test_concurrent_creates_no_collision`) — still green, unmodified.
2. Temporarily revert only 6a (restore the shared singleton, keep the 6b lock code in place — e.g. via a local git stash of just the 6a hunks, or a scratch checkout; do not leave this reverted state committed). Re-run OBL-1 both sites: expect RED. Re-run OBL-2/3/4/5: expect unaffected (still green). Record the result, then restore 6a.
3. Temporarily revert only 6b (restore the lock-free call sites, keep 6a's thread-local accessor). Re-run OBL-2 both sites: expect RED, count==2. Re-run OBL-1/3/4: expect unaffected (still green). Re-run OBL-5 both sites: expect GREEN, run and trivially satisfied — with 6b's lock reverted, `cache_clear()` has nothing to race against a population in flight, so no deadlock is structurally possible; still execute it and record the result, do not skip it. Record the result, then restore 6b.
4. Confirm the Base-state cells (OBL-1 red, OBL-2 red-trivial, OBL-3 already-green) match what you observed in T002, before any fix code existed — cite the git SHA of the red-first commit for this claim rather than re-deriving it.
5. Time a single-threaded `create_mission_core` call (or `spec-kitty agent mission create`) explicitly, before and after the fix, and confirm it stays under 2 seconds (NFR-002). Use or extend an existing timing assertion if one exists in the test suite; otherwise add a minimal one.
6. Verify NFR-001's cross-process/varied-`PYTHONHASHSEED` determinism (binding constraint 6, above) — this is a SEPARATE check from T002's in-process red/green verification and MUST NOT be satisfied by a single in-process loop. Run OBL-1's PRIMARY_SITE and SECOND_SITE test cases as N (e.g. 10-50, or at least 50 total invocations across varied seeds — tracking spec.md NFR-001's literal "run the new test 50 times in a row" falsifiable bar) separate `python -m pytest` subprocess invocations, with `PYTHONHASHSEED` explicitly varied across runs — loop over several distinct fixed seed values (e.g. `0`, `1`, `42`, `12345`) plus at least one invocation with `PYTHONHASHSEED` unset/`random` — and confirm an identical verdict (GREEN, post-fix, on the applied-fix code) across every single invocation. Record the exact seeds and invocation count used in the production-fix commit message (step 9 below) or in `traces/tooling-friction.md` (T007 appends the permanent record).
7. Run the full gate-set suites and require green, using `.venv/bin/python -m pytest` (never bare `pytest`):
   - `tests/missions` — expect 319+ passed
   - `tests/core` (all of it, not just the identity test file) plus the 8 other `core_misc` test_dirs: `tests/specify_cli/core`, `tests/coordination`, `tests/specify_cli/coordination`, `tests/decisions`, `tests/doctrine_synthesizer`, `tests/specify_cli/tool_surface`, `tests/specify_cli/asset_preservation`, `tests/zeitgeist_client`
   - `tests/charter` and `tests/doctrine` (both `charter` module test_dirs)
   - `tests/unit`
   - `tests/specify_cli/runtime`
   - `tests/charter/test_charter_import_time_io.py` (re-run individually and named explicitly in your validation notes)
8. Classify any red you did not expect per AGENTS.md's baseline-red gotcha (pre-existing P0 / CI-environment / stale-install / stale-venv) before treating it as yours — but per plan.md §10, this baseline was fully clean at scaffold time, so any new red here is very likely yours to fix, not to explain away.
9. Commit the production fix (6a+6b+6c across both files) as its own commit (or a small number of tightly-scoped commits), separate from the red-first test commit. The commit message must state: which tests are now green, that all five gate-set modules were run and are green, that `test_charter_import_time_io.py` was verified explicitly, and the NFR-001 multi-seed/multi-process seeds and invocation count used in step 6.

**Files**: none new — this subtask is verification plus the commit action over T003/T004/T005's changes.
**Validation**: revert matrix's four rows all match plan.md §8c exactly; NFR-002 timing assertion passes; NFR-001 cross-process/varied-`PYTHONHASHSEED` determinism confirmed identical (GREEN) across every one of N separate subprocess invocations; all five gate-set modules green; production-fix commit exists with a clear message.

### Subtask T007: Append mission tracer files (out-of-map edit, rationale below)

**Purpose**: Record what the forced-interleave monkeypatch construction actually looked like once built, any friction hitting the exact pause window, and the final red-commit/green-commit SHAs — per charter Standing Order 3 and plan.md §13.

**Steps**:
1. Read the existing entries in `kitty-specs/concurrent-template-config-race-4589-01M35M6B/traces/approach.md`, `design-decisions.md`, and `tooling-friction.md` (already seeded at the spec phase, 2026-09-22 entries present).
2. **Append** (never replace, never renumber) new entries covering: the concrete timing-seam hook you built in T001 and where exactly it lands relative to `self.reader.stream`/composition; any friction getting the file-identity pin to work without depending on call/iteration order; the final red-first commit SHA (from T002) and the final green/production-fix commit SHA (from T006); any deviation from the plan's illustrative `_FixSiteCase` sketch and why.
3. Commit this as the final, separate doc/tracer commit per plan.md §14 step 4.

**Files**: `kitty-specs/concurrent-template-config-race-4589-01M35M6B/traces/approach.md`, `design-decisions.md`, `tooling-friction.md` — appended only.

**Rationale for this out-of-map edit (required per the tasks-packages ownership rule):** these tracer files live under `kitty-specs/`, which a `code_change` WP must never list in `owned_files` (it would be rejected by `finalize-tasks --validate-only` with `INVALID_WP_OWNED_FILES_KITTY_SPECS`). This is a small, well-justified, append-only edit explicitly required by the plan's own commit-phasing (§14 step 4) and the charter's mission-tracer-files standing order — not a scope expansion, and not something a separate `planning_artifact` WP would meaningfully parallelize against, since it only makes sense after T001-T006's real content exists to record.

**Validation**: `git log --oneline` on this mission's branch shows three (or a small number of tightly-scoped) new commits in order: red-first test commit, production-fix commit(s), doc/tracer commit; the tracer files show new entries appended after the existing 2026-09-22 ones, none removed or renumbered.

## Definition of Done

- [ ] T001: timing-pause hook empirically verified to land strictly inside the shared YAML instance's load window (after `reader.stream` assignment, before composition completes); OBL-3's two fault-injection points confirmed to propagate pre-fix.
- [ ] T002: OBL-1 (both sites) RED at Base through the real forced interleave; OBL-2 (both sites) RED at Base for the trivial "seam absent" reason; OBL-3 (both sites) GREEN at Base and explicitly documented as not-red-first; OBL-4 unmodified and still green; red-first commit landed via `spec-kitty safe-commit`, separate from and before any fix code.
- [ ] T003: 6a implemented at both sites; OBL-1 green both sites; no shared mutable YAML instance remains at either site; `_load_step_yaml`/`_load_layered_mission_type_file` names and `Path` arguments unchanged.
- [ ] T004: 6b implemented at both sites with the lock wrapping the ENTIRE cached call (not just the miss body); SECOND_SITE's public/private split completed with `.cache_clear`/`.cache_info`/`.cache_parameters` forwarded via three explicit assignments (not `functools.update_wrapper`); OBL-2 green both sites, count==1; OBL-5 green both sites; `tests/charter/test_charter_import_time_io.py` and `test_same_key_is_a_cache_hit` both explicitly re-run and green.
- [ ] T005: `MissionCacheLockError(ValueError)` defined in `mission_step_repository.py`, imported (not redefined) in `mission_type_repository.py`; `tests/architectural/test_charter_no_specify_cli_import.py` green; no swallow-and-degrade branch added anywhere; OBL-3 still green both sites.
- [ ] T006: full revert matrix verified against all four cells exactly as tabulated above (both sites, each cell); OBL-4 still green unmodified; NFR-002 single-threaded timing under 2s confirmed before and after; NFR-001 determinism confirmed across N (e.g. 10-50, or at least 50 total invocations across varied seeds — tracking spec.md NFR-001's literal "50 times in a row" bar) separate subprocess `python -m pytest` invocations of OBL-1 (both sites) with `PYTHONHASHSEED` varied across runs, identical (GREEN) verdict in every invocation, seeds/counts recorded; all five gate-set modules (`missions`, `core_misc`'s 9 test_dirs, `charter`'s 2 test_dirs, `unit`, `specify_cli_runtime`) green via `.venv/bin/python -m pytest`; production-fix commit landed.
- [ ] T007: tracer files appended (not replaced/renumbered) with real construction details, friction, and both commit SHAs; doc/tracer commit landed.
- [ ] No `step.yaml` format, `MissionType`/`MissionStep` schema, or `meta.json` shape changed anywhere in the diff (C-001).
- [ ] No retry/sleep/jitter introduced anywhere as a "fix" for the race (C-002).
- [ ] No GitHub relabeling or new tracker-issue filing performed by this WP (C-003 — orchestrator-only).
- [ ] Every path cited in your own commit messages/notes verified to exist on this checkout (C-004).

Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.

## Risks

- **Timing-seam fragility (highest risk).** The class-level `ruamel.yaml.main.YAML` hook plus path-aware predicate is a spike output, not a fixed recipe — if the exact internal call sequence differs from research.md's traced mechanism, the pause may land in the wrong place and produce a false-red or false-green OBL-1. Mitigate by empirically verifying the pause location in T001 before writing any assertion logic in T002, and by re-verifying it survives 6a's rewrite unedited (binding constraint 2).
- **SECOND_SITE's 14 call-site dependency on `.cache_clear`/`.cache_info`/`.cache_parameters`.** Forgetting the three explicit forwarding assignments (or using `functools.update_wrapper` instead) will silently break `tests/charter/test_charter_import_time_io.py` (2 `.cache_clear()` + 1 `.cache_info()` call) and 11 other call sites — 10 other `.cache_clear()` calls across `tests/charter/test_mission_type_path_layout_ssot.py` (2) and `tests/doctrine/missions/test_mission_type_repository.py` (8), plus `MissionTypeRepository.cache_clear()`'s own body call (`mission_type_repository.py:207`) — with `AttributeError`. Mitigate by re-running that file explicitly and by name, not relying on it surfacing incidentally in a broader charter-module run.
- **Deadlock risk in OBL-1's SECOND_SITE construction.** If OBL-1 accidentally races the SAME key while pausing a thread mid-walk (instead of distinct `pack_context`s), the post-fix lock will deadlock the test. Mitigate by keeping OBL-1 strictly distinct-key at both sites (binding constraint 3) and reserving same-key racing for OBL-2's Barrier-only (no long pause) construction.
- **`_resolve_action_slot`'s fixed `mission_types_dirs` makes SECOND_SITE's default case same-key.** A naive "different mission types never contend" assumption (round-3's error, corrected in plan.md §7) could lead to writing OBL-2's SECOND_SITE case as if it were a rare edge case rather than the *default* concurrent-create shape. Use the per-site key-shape table above, not intuition.
- **Baseline-red misattribution.** If any of the five gate-set modules shows unexpected red during T006, follow AGENTS.md's classification protocol before assuming it's pre-existing — this mission's baseline (plan.md §10) was fully clean, so a new red here is very likely attributable to this WP's own change.

## Reviewer Guidance

- Verify the revert matrix was actually executed (not merely asserted) — ask for the git SHAs or local evidence of each of the four cells, especially the two "half reverted" cells, which are easy to skip.
- Confirm OBL-3 is explicitly documented as green-at-Base in the red-first commit's message/PR notes — a reviewer should reject a claim that OBL-3 is "red-first" as a severity finding per CL-003's own severity-4 bar (a red-first test that stays green when it shouldn't, or is mischaracterized, undermines the whole ATDD claim).
- Confirm the lock in 6b wraps the ENTIRE cached call, not just the miss body — re-read the diff at both `resolve_all_for_mission_type` and the new `resolve_layered_mission_types` wrapper and check the `with _lock_for(key):` block's indentation actually encloses the call into the `@functools.cache`-decorated function, not just a portion of the miss logic.
- Confirm no `functools.update_wrapper` was used for the SECOND_SITE split, and that all three attributes (`cache_clear`, `cache_info`, `cache_parameters`) are forwarded, not just `cache_clear`.
- Confirm `tests/architectural/test_charter_no_specify_cli_import.py` passes and that `grep -rn "specify_cli" src/charter/offering/missions/mission_step_repository.py src/charter/offering/missions/mission_type_repository.py` shows no live import.
- Confirm the tracer-file commit only appends, never edits or removes, the existing 2026-09-22 entries.
- Confirm no on-disk schema, `meta.json` shape, or `step.yaml` format changed anywhere in the diff (C-001) — this should be a pure concurrency-safety change.
- Confirm NFR-001's cross-process/varied-`PYTHONHASHSEED` determinism check (T006 step 6) was actually EXECUTED, not merely asserted — ask for the specific seeds used, the invocation count (N, expected e.g. 10-50 or at least 50 total invocations across varied seeds, tracking spec.md NFR-001's literal "50 times in a row" bar), and evidence (command output, commit-message note, or `traces/tooling-friction.md` entry) that OBL-1 was run as N separate `python -m pytest` subprocess invocations with `PYTHONHASHSEED` varied, not a single in-process loop; reject a claim of NFR-001 compliance backed only by T002's ordinary in-process red/green run.

Implement with: `spec-kitty agent action implement WP01 --agent claude`
