# Implementation Plan: Concurrent `create_mission_core` TemplateConfigurationError race

**Branch**: `fix/concurrent-template-config-race-4589` | **Date**: 2026-09-23
**Spec**: `kitty-specs/concurrent-template-config-race-4589-01M35M6B/spec.md`
**Research**: `kitty-specs/concurrent-template-config-race-4589-01M35M6B/research.md`

This plan honours every Clarification (CL-001..CL-007), Functional/
Non-Functional Requirement, Constraint, and Success Criterion in `spec.md`
explicitly and does not soften or re-derive any of the operator's binding
decisions. Every path cited below has been verified with `ls`/`grep`/`Read`
against this checkout during this planning pass (C-004).

## Summary

Two module-level `ruamel.yaml.YAML(typ="safe")` singletons —
`_YAML` (`src/charter/offering/missions/mission_step_repository.py:72`) and
`_LAYERED_YAML` (`src/charter/offering/missions/mission_type_repository.py:318`,
found in this mission's own plan-phase research, not named in `spec.md`'s
Readiness Findings) — are shared across every thread and every call for the
life of the process. `research.md` confirms, by reading the installed
`ruamel.yaml` source and this project's actual (C-extension-free) dependency
resolution, that `YAML.load()` mutates cross-call cached parser state
(`self.reader.stream`, `self.tags`) with no locking. Both singletons feed
`functools.cache`-wrapped functions
(`_resolve_all_for_mission_type_cached`, `resolve_layered_mission_types`)
whose unbounded cache-miss path (confirmed from CPython's own `functools.py`)
never serializes concurrent execution of the wrapped body. The two facts
compose: two threads racing a cache miss can corrupt each other's YAML parse
on the shared instance, `_load_step_yaml`'s blanket `except Exception: return
None` (`mission_step_repository.py:134`) turns that into a silently dropped
`MissionStep`, and a dropped step that carried the `template:` ref for
`artifact_kind="spec"` produces exactly the observed
`TemplateConfigurationError(reason="is missing the requested mapping key")`
at `src/specify_cli/runtime/resolver.py:499`.

The fix (Option A, CL-001): eliminate the shared, non-thread-safe YAML state
at both singleton sites (thread-local `YAML` instances — no lock needed,
because there is no shared object left to race on) and add a per-key lock
around each cache's miss path (defense against redundant concurrent work and
against `functools.cache`'s own lock-free cache-dict write racing on a
result). A deterministic, `threading.Barrier` + monkeypatch-forced regression
test proves the fix closes the exact interleaving identified in
`research.md`, committed before the fix per CL-004/ATDD (C-011).

**Swallow-vs-raise asymmetry at the two fix sites, and why it does not
change the fix's contract:** `_load_step_yaml`'s cache-miss body (primary
site) swallows every parse exception via a blanket
`except Exception: return None` (`mission_step_repository.py:134-135`),
which is the exact mechanism that turns corruption into the observed
`TemplateConfigurationError` symptom. `_load_layered_mission_type_file`
(second site) only catches `ruamel.yaml.error.YAMLError` and re-raises it as
a named `ValueError` (`mission_type_repository.py:388-391`); any other
corrupted-but-not-`YAMLError` outcome (e.g. a parse that "succeeds" on
garbled reader/scanner state and produces wrong-but-syntactically-valid
data) is not swallowed there and propagates as whatever exception
`MissionType.model_validate`/the id-mismatch check raises. **What
corrupted-parse behavior is actually expected/observed at the second site
pre-fix is an open question this plan does not resolve by static analysis
alone** — it is exactly what the second-site (`SECOND_SITE`) case of the
red-first regression test (Section 8, obligation OBL-1) must establish
empirically, the same way that test's primary-site (`PRIMARY_SITE`) case
establishes the swallow-path outcome for the first site. Whichever way
`SECOND_SITE`'s pre-fix RED run actually fails (a raised `ValueError`/
`pydantic.ValidationError` bubbling up uncaught, a silently wrong roster
entry — guaranteed to be caught by OBL-1's explicit,
per-thread-captured content-correctness assertion rather than assumed to
fail some other way — or something else), the fix itself does not depend on
the answer:
6a/6b at both sites, and the raise-never-degrade contract (CL-006/FR-006,
Section 6c "Both fix sites raise, never degrade"), are intended to hold
identically at both sites regardless of which pre-fix failure shape the
second site's corrupted-parse race actually takes.

## Research summary

See `research.md` in full. Bottom line, restated for plan-readers who have
not opened it: **both halves of CL-002's hypothesis are independently
confirmed by direct source reading** — (a) `YAML(typ="safe")`'s `.load()`
mutates cross-call cached reader/scanner/parser/composer state with no
synchronization, confirmed live on this checkout (`CParser is None`, no
`ruamel.yaml.clib` in `uv.lock`, so the vulnerable pure-Python path is what
actually runs); (b) `functools.cache`'s unbounded cache-miss path has no
lock at all around the wrapped call. **Round-4 nit fix (arbiter, sev 1):**
`research.md` and round-3 of this plan cited the pure-Python fallback
implementation at `functools.py:549-562`; the interpreter this checkout
actually runs uses the C `_functools` accelerator, confirmed live —
`functools._lru_cache_wrapper is _functools._lru_cache_wrapper` evaluates
`True` in this checkout's `.venv` — so `functools.cache`'s real runtime
type is `_functools`'s C `_lru_cache_wrapper`, not the pure-Python class
`functools.py` itself defines as a fallback for interpreters built without
the accelerator. The conclusion this plan and `research.md` draw from the
pure-Python source is unchanged by this correction: CPython's C
accelerator implements the identical unbounded-cache contract (no lock
around the wrapped call on a miss; the cache dict is written only after
the wrapped call returns) — the pure-Python module is a behavior-preserving
fallback, not a different algorithm, and CPython's own test suite holds
both implementations to the same contract. Neither fact alone explains a
dropped key;
together they do. Research also found a **second, previously uncatalogued**
instance of the identical defect shape (`_LAYERED_YAML` /
`resolve_layered_mission_types`, reachable eagerly from
`create_mission_core` via `_resolve_action_slot`), and definitively ruled
`src/charter/activation/resolver.py` **out** of scope (its `template_set` is
an unrelated charter-selection scalar, confirmed by direct read — this
resolves `spec.md`'s open "scope its involvement" instruction).

**Open risk carried forward** (CL-002's "resolve or carry forward as risk"):
the research pass is static/source-level, not a live-witnessed reproduction.
The red-first regression test (Test strategy, below) is what will
empirically confirm the mechanism by construction; if that test does not, in
fact, fail pre-fix, the static analysis above — however well-evidenced — has
not been validated as the actual production mechanism, and the WP must stop
and re-investigate rather than treat a passing "red-first" test as proof
(CL-003 severity-4 bar).

## 1. Seam

This change lands entirely inside the `charter/offering/missions`
doctrine-data package:

- `src/charter/offering/missions/mission_step_repository.py` — the `_YAML`
  singleton (line 72) and `_resolve_all_for_mission_type_cached` (lines
  446-470). **Primary fix site.**
- `src/charter/offering/missions/mission_type_repository.py` — the
  `_LAYERED_YAML` singleton (line 318) and `resolve_layered_mission_types`
  (lines 477-601). **Second fix site**, found in this mission's own
  research (not in `spec.md`'s Readiness Findings), same defect shape.
- `src/charter/offering/missions/step_projection.py` — read-only in this
  plan; `project_template_set`/`iter_template_refs` are pure functions with
  no shared state and need no change. Included in the seam because a test
  may need to assert on its output shape, not because it is modified.

**`src/charter/activation/resolver.py` is NOT in scope**, resolving
`spec.md`'s open candidate-blast-radius question. Confirmed by direct read
in `research.md` ("Ruled out / out of scope"): its `template_set` is the
charter-selection scalar (e.g. `"software-dev-default"`), an unrelated
domain object per `step_projection.py`'s own scope-fence docstring
(lines 21-30). It imports nothing from `mission_step_repository.py` /
`step_projection.py` and shares no code path with this defect.

`src/charter/activation/mission_type_profiles.py` is **read but not
modified** — it is the call site (`_resolve_template_set_slot`,
`_resolve_action_slot`) that reaches into the two fix sites above; fixing
the two singletons closes the race for every caller, including this one,
with no change needed at the call site itself.

No CLI command reaches past a service/repository seam into kernel
internals for this fix. **This fix's own diff does not add, remove, or
modify any `src/kernel/**` file or import.** The traced
`create_mission_core` → `resolve_mission_type_context` →
`_resolve_template_set_slot`/`_resolve_action_slot` →
`MissionStepRepository`/`MissionTypeRepository` chain does contain two
pre-existing reads of `src/kernel/` primitives —
`src/specify_cli/core/mission_creation.py:48`
(`from kernel.clock import now_utc_iso`) and
`src/charter/offering/missions/repository.py:13`
(`from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN`) — but both are
legitimate, already-in-place service-to-kernel-primitives imports, unrelated
to and untouched by this change (confirmed by the call-chain trace in
`research.md`).

**A recurring but currently dormant instance of the same singleton
anti-pattern, acknowledged and out of scope:** three other module-level,
unsynchronized `YAML(typ="safe")` singletons exist in this same
`offering`/`activation` package tree —
`src/charter/activation/neutrality/lint.py:66` (`_YAML`, consumed by
`_load_banned_terms`), `src/charter/offering/agent_profiles/operating_procedures.py:41`
(`_YAML`, consumed by `collect_operating_procedure_entries`), and
`src/charter/offering/drg/migration/extractor.py:51` (`_yaml`) — sharing the
first half of this mission's defect shape (a shared, non-thread-safe `YAML`
instance reused across every call). None of their current callers run under
`ThreadPoolExecutor`/`threading.Thread` in this checkout today, and none
feeds a `functools.cache`-wrapped consumer, so none is a live concurrency
defect right now; per the charter's smallest-viable-diff discipline this
mission does not extract a shared thread-local-YAML helper or otherwise
touch these three sites. Recorded here (and Section 12) so a follow-up
tracker issue is the next step if any of them ever grows a threaded or
memoized caller, rather than this anti-pattern silently reappearing.

## 2. Generated artifacts

**This fix touches no generated artifact.** No doctrine schema
regeneration, no Contextive glossary change, no agent command copy. The
change is Python source only, inside `src/charter/offering/missions/`. It
does not edit anything under `packs/built-in/` or `packs/internal/`, so the
pack-manifest regen gate (`spec-kitty doctrine regenerate-graph`) is not
triggered and does not need to run.

## 3. Contracts

None of the following move: doctrine schemas (`MissionStep`/`MissionType`
Pydantic models in `.../missions/models.py` — unmodified), mission step
contracts, action indices, the orchestrator-api surface, or the vendored
`spec-kitty-events` package. Per CL-007/C-001, the fix only changes the
**concurrency safety** of how already-in-memory structures are built and
cached — it does not change what `MissionStep`, `MissionType`, or
`template_set` *are* or *look like*, only guarantees that building them
under concurrent load no longer corrupts the process. `step.yaml`'s on-disk
format, the `MissionType`/`MissionStep` schema shapes, and `meta.json` are
untouched.

## 4. Migration chain

This mission does **not** touch the upgrade/migration chain
(`src/specify_cli/upgrade/migrations/`). There is no on-disk format change
to migrate old projects toward — the defect and its fix are entirely
in-process (per-`spec-kitty`-invocation) cache/concurrency behavior, per
CL-007.

## 5. Cache-contract preservation (FR-003/NFR-003)

`MissionTypeRepository.default.cache_clear()` and
`MissionStepRepository.cache_clear()` (`mission_step_repository.py:323-333`
— the public `@staticmethod` wrapper that internally calls the private
`_resolve_all_for_mission_type_cached.cache_clear()`, which that private
function's own docstring, lines 464-466, forbids calling directly from
outside the module) remain present, callable, synchronous, and **unchanged
in signature and observable behavior**. Concretely:

**Two same-named-looking but deliberately independent cache-clear seams
(do not conflate them — Section 9's shared, single `_cold_cache()` helper,
used by every test obligation in Section 8 that races either fix site,
names both explicitly):**
`MissionTypeRepository.default.cache_clear()`
clears only `default()`'s own, separate, `cls`-keyed built-in-repository
cache; it does **not** touch `resolve_layered_mission_types`'s cache. The
seam that clears `resolve_layered_mission_types`'s cache (Section 1's
second fix site, raced by every Section 8 test's `SECOND_SITE` case) is the
sibling staticmethod `MissionTypeRepository.cache_clear()` — no `.default`
— per that staticmethod's own docstring at
`mission_type_repository.py:188-206` ("The two caches are deliberately
independent"). Any test that needs a cold `resolve_layered_mission_types`
cache before racing it must call `MissionTypeRepository.cache_clear()`,
not `MissionTypeRepository.default.cache_clear()`, which would leave that
specific cache warm.

- The chosen fix mechanism (Section 6) adds **no new lock that
  `cache_clear()` needs to know about, acquire, or release.** The per-key
  locks introduced live in a *separate* module-level structure (a plain
  `dict[key, threading.Lock]` guarded by one small bootstrap lock, Section
  6b) that `cache_clear()` never touches. `cache_clear()` continues to
  do exactly one thing: call `functools.cache`'s own `.cache_clear()` on the
  wrapped function, which only empties that function's internal cache dict
  — an operation that has never taken, and will continue to never take, any
  lock this fix introduces. This claim is unchanged by the Section 6b
  single-flight redesign below (round 4, ARB-001/DEBBIE-001): the per-key
  `Lock` objects are reused, never rebuilt or torn down, across any number
  of `cache_clear()` calls, so `cache_clear()` needs no new awareness of
  them regardless of exactly where around the cached call each `Lock` is
  held.
- **Edge case — `cache_clear()` racing an in-flight cache-miss population**:
  if thread A is mid-population (holding `_lock_for(key)` for the full
  duration of its call into the `@functools.cache`-wrapped function —
  Section 6b now takes the lock *around* that whole call, not only inside
  the miss body, so this is true whether A is still walking the filesystem
  or has already returned and is about to have its result written into the
  cache) when thread B calls `MissionStepRepository.cache_clear()`, B's call
  clears the **data** cache dict immediately and returns (it never blocks on
  A's lock — it does not acquire it, because it does not touch the per-key
  lock structure at all). A's in-flight call completes normally and writes
  its result into `cache[key] = result` per `functools.cache`'s own
  unbounded-path logic — into what is, by then, a *freshly emptied*
  cache dict. The net effect is benign: the next caller for that key gets a
  cache miss again (A's write landed in the just-cleared dict, so it is
  present again after A finishes) or, in the tightest possible interleaving,
  A's write is the only entry present — either way, no deadlock, no
  exception, no corruption. This satisfies NFR-003's falsifiable test ("a
  test that calls `MissionStepRepository.cache_clear()` mid-population and
  asserts no deadlock/exception") — see Section 8, obligation OBL-5.
- Both files' existing "production never mutates the bundled trees
  mid-process" cache-safety argument (`mission_type_repository.py:84-88`,
  `mission_step_repository.py:326-331`) **still holds** after this fix: it
  was always an argument about the *filesystem* not changing under a
  running process, which this fix does not touch or need to revisit — the
  new argument this fix adds is a *narrower*, additional one (the in-memory
  YAML-parsing state doesn't need to be shared to be efficient), which is
  additive, not a revision of the existing one.

## 6. Fix mechanism (FR-002)

Two changes, one per singleton, identical shape, informed directly by
`research.md`'s conclusion that (a) the shared YAML instance's cross-call
state is the corrupting mechanism and (b) `functools.cache`'s cache-miss
path is what creates the opportunity for two threads to reach that shared
state at the same time:

### 6a. Thread-local YAML instances (removes the shared mutable state)

Replace each module-level singleton —

```python
_YAML = YAML(typ="safe")                      # mission_step_repository.py:72
_LAYERED_YAML = YAML(typ="safe")              # mission_type_repository.py:318
```

— with a `threading.local()`-backed accessor that hands each thread its own
private `YAML(typ="safe")` instance, built once per thread and reused by
that thread only (mirrors `MissionTypeRepository._load`'s own
already-thread-safe pattern at `mission_type_repository.py:160`, which
constructs a fresh `_yaml = YAML(typ="safe")` — the difference here is
*per-thread*, not *per-call*, reuse, to avoid rebuilding a `YAML` object on
every single `_load_step_yaml`/`_load_layered_mission_type_file` call, which
would be wasteful given how many step files a single `resolve_all_for_mission_type`
walk can touch). Concretely, a small module-level helper such as:

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

replacing every `_YAML.load(...)` / `_LAYERED_YAML.load(...)` call site with
`_get_yaml().load(...)`. This is the primary fix: with no object shared
across threads, there is nothing left to race on, and **no lock is needed
for this half of the fix at all** — each thread's reader/scanner/parser/
composer/tags state is private to that thread for the process's whole
lifetime, at zero synchronization cost on every read (satisfies NFR-002,
Section 7).

### 6b. Single-flight per-key lock around each cache's call (closes the redundant-population / cache-poisoning window)

**Round-4 rewrite** (`reviews/plan.ruling.md`, DEBBIE-001/ARCH-003 merged
with ARB-001, reopening PLAN-VERIFY-003): the round-3 design below acquired
`_lock_for(key)` **inside** the `functools.cache`-wrapped body, with no
re-check under the lock. `functools.cache`'s miss path stores the result
only *after* the wrapped body returns (Section 7's nit on which
implementation runs is orthogonal to this: both the pure-Python fallback and
the C `_functools` accelerator this project's interpreter actually runs
share that property). With the lock only inside the body, two threads that
both observe a cache miss before either has stored a result would each
acquire the lock **in turn** and each **independently run the full walk** —
the lock serializes the two walks so neither corrupts the other (post-6a),
but it does not stop the second walk from happening at all. The count is 2,
not 1, so the design's own stated property ("closes the redundant-work
window") did not hold, and no test could tell "6b present" from "6b
reverted" (the arbiter's own re-derivation, `reviews/plan.ruling.md`
"PLAN-FRESH3-DEBBIE-001" ruling).

**The fix: move the lock to wrap the whole cached call, not just the miss
body, so a losing thread's call becomes a functools.cache *hit* instead of a
second, independent walk.**

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

`_resolve_all_for_mission_type_cached` and `_resolve_layered_mission_types_cached`
keep their `@functools.cache` decorator and their bodies unchanged in shape
(still the plain, single uncached walk — Section 5's `cache_clear()`
contract is untouched by this move, since it only ever calls the
`@functools.cache` wrapper's own `.cache_clear()`). What changes is the
**call site**: every caller reaches the cached function only through a
thin wrapper that holds `_lock_for(key)` for the duration of the call:

```python
def resolve_all_for_mission_type(
    self, mission_type_id: str, pack_context: _PackContextLike | None = None,
) -> dict[str, MissionStep]:
    key = (self._builtin_root, mission_type_id, pack_context)
    with _lock_for(key):
        return _resolve_all_for_mission_type_cached(
            self._builtin_root, mission_type_id, pack_context
        )
```

**Second-site structural note (do not blur the two sites' shapes — the
recurring smell this ruling names):** unlike the primary site, which
already has a public, uncached entry point (`resolve_all_for_mission_type`)
distinct from its cached implementation, `resolve_layered_mission_types`
today **is itself** the `@functools.cache`-decorated, publicly-named
(`__all__`-exported, `mission_type_repository.py:23`) function `_resolve_action_slot`
calls directly. Mirroring 6a's own precedent (renaming the walk loop to a
new `_resolve_layered_mission_types_uncached`, Section 9's binding note),
the SAME split must happen here: the currently-cached function is renamed
to a private cached name (e.g. `_resolve_layered_mission_types_cached`),
and `resolve_layered_mission_types` becomes the public, lock-wrapping entry
point every caller (including `_resolve_action_slot` and any future
caller) keeps using unchanged by name — mirroring the primary site's shape
exactly, at the cost of one internal rename (the previously-public cached
function becomes the new private `_resolve_layered_mission_types_cached`
name) plus the `.cache_clear`/`.cache_info`/`.cache_parameters`
attribute-forwarding bindings detailed just below: no `__all__` change and
no import-site update, since the public name `resolve_layered_mission_types`
is preserved unchanged and every existing caller keeps working as-is.
Keyed on `(mission_types_dirs, pack_context)` — see Section 8a's fact table
for why that key shape means the *default* case at this site is already
same-key, not the narrow case.

**Preserving the public `.cache_clear()`/`.cache_info()` seam across the
split (PLAN-FRESH4-ARCH-001, sev 4; PLAN-FRESH5-001, sev 4):** unlike the
primary site, where `MissionStepRepository.cache_clear()` has always
called the private `_resolve_all_for_mission_type_cached.cache_clear()`
(so no public name's `.cache_clear()` attribute is being taken away by
this fix), the second site's public name `resolve_layered_mission_types`
is itself, today, the `@functools.cache`-decorated callable — so it is the
thing that currently carries `.cache_clear()`, `.cache_info()`, and
`.cache_parameters()`, and 12 call sites across three test files
call `resolve_layered_mission_types.cache_clear()` directly (13 including
the one `.cache_info()` call site below)
(`tests/charter/test_mission_type_path_layout_ssot.py`,
`tests/doctrine/missions/test_mission_type_repository.py`,
`tests/charter/test_charter_import_time_io.py`),
`MissionTypeRepository.cache_clear()`'s own body
(`mission_type_repository.py:207`) also calls it directly, and
`tests/charter/test_charter_import_time_io.py`'s in-subprocess
`_IMPORT_SPY_SCRIPT` (live call at `test_charter_import_time_io.py:231`,
`layered_info = resolve_layered_mission_types.cache_info()`) calls
`.cache_info()` directly on the same public name to assert NFR-004's
"never called at charter-module import time" bound. Splitting the name
without more would silently strip `.cache_clear`/`.cache_info` from the
public `resolve_layered_mission_types` name — `functools.cache`'s
`.cache_clear()`, `.cache_info()`, and `.cache_parameters()` only exist on
the decorated callable itself, and after the rename the decorated callable
is `_resolve_layered_mission_types_cached`, not the public wrapper; a
`.cache_info()` call against the post-split public wrapper without this
forwarding would raise `AttributeError`, turning the currently-green
`test_charter_import_time_io.py` red for a reason unrelated to the NFR-004
property it exists to guard. **Binding requirement:** the new public
`resolve_layered_mission_types` wrapper must expose `.cache_clear`,
`.cache_info`, and `.cache_parameters` attributes that forward to
`_resolve_layered_mission_types_cached`'s own — i.e. every public
attribute a `functools.cache`-decorated callable exposes, not `.cache_clear`
alone — bound immediately after the wrapper's own definition. Three
explicit binding lines are used, not `functools.update_wrapper`: that
helper copies `__wrapped__`/`__doc__`/`__name__`/`__module__`/`__dict__`
metadata, never `cache_clear`/`cache_info`/`cache_parameters` (those are
attributes `functools.cache` itself sets on the decorated callable, not
part of `__wrapped__`-style metadata), so it would not close this gap even
if used —

```python
def resolve_layered_mission_types(
    mission_types_dirs: tuple[Path, ...],
    pack_context: _PackContextLike | None,
) -> dict[str, MissionType]:
    key = (mission_types_dirs, pack_context)
    with _lock_for(key):
        return _resolve_layered_mission_types_cached(mission_types_dirs, pack_context)


resolve_layered_mission_types.cache_clear = _resolve_layered_mission_types_cached.cache_clear
resolve_layered_mission_types.cache_info = _resolve_layered_mission_types_cached.cache_info
resolve_layered_mission_types.cache_parameters = _resolve_layered_mission_types_cached.cache_parameters
```

— so every existing direct call site, including
`MissionTypeRepository.cache_clear()`'s own body and
`test_charter_import_time_io.py`'s `.cache_info()` call, keeps working
unchanged, with **zero test-file edits**. This is mechanism (a) of the
finding's two options, chosen over mechanism (b) (repointing >=3 test
files' calls to `MissionTypeRepository.cache_clear()`) precisely because
it keeps Section 5's "no new `cache_clear()` coupling" claim and Section
14's "confined to ... one test file" scope claim literally true:
`MissionTypeRepository.cache_clear()`'s own body
(`mission_type_repository.py:207`,
`resolve_layered_mission_types.cache_clear()`) needs **no change** under
this fix, since it already calls the still-public name, and that name's
`.cache_clear`/`.cache_info`/`.cache_parameters` attributes now forward
correctly. This fix's own test-verification list explicitly includes
`tests/charter/test_charter_import_time_io.py` (Section 14, production-fix
commit step) — re-run to confirm the forwarded `.cache_info()` seam is
exercised and green, not left to the module-suite run alone to discover.

**Why this delivers "exactly one population per key per cold episode"
(the property 6b must guarantee):** two threads racing a cold miss for the
same key both call `resolve_all_for_mission_type`. The first to acquire
`_lock_for(key)` calls the cached function while holding the lock: this is
a genuine miss, so it runs the walk, and `functools.cache`'s own wrapper
stores `cache[key] = result` **before that call returns and before the
lock is released** (the store happens inside the same call the lock wraps,
not after it). The second thread blocks on the same lock until the first
releases it; when it then acquires the lock and makes its own call into the
cached function, `functools.cache`'s dict already has `key` — its own fast
path (`cache_get(key, sentinel)`) returns the first thread's result
directly, without ever calling the walk body again. **Population count is
provably 1, not 2, for any number of racing threads on the same key** — not
just for two.

**Reconciling §7's "a warm hit never touches a lock" claim (round-3
text) — revised, not preserved verbatim, with the reason recorded here per
charter Directive 003:** an alternative design exists that keeps a warm hit
from ever touching the lock at all — a "re-check under the lock" using a
private, per-key result cache the miss body consults after acquiring the
lock. That design was drafted and rejected during this rewrite: it needs a
companion structure (tracking "population in flight" / "population just
settled") that is **not** the same dict `functools.cache` itself writes,
and there is an unavoidable window between "the lock-holding thread's
companion-structure update" and "`functools.cache`'s own dict write" during
which a third, brand-new thread could observe neither and start a second,
redundant walk — closing that window correctly requires the companion
structure to be cleared by `cache_clear()` too, which reopens exactly the
"`cache_clear()` needs to know about a new lock/structure" coupling Section
5 exists to avoid. The design adopted above has no such window (the lock
covers the *entire* call, including `functools.cache`'s own dict write, so
there is never a race between "populated" and "visible") and needs no new
`cache_clear()` coupling. Its cost is that every call — including a later,
completely uncontended warm hit — now acquires `_lock_for(key)`, not just a
cold miss. Section 7 re-derives NFR-002 under this honest premise (a warm
hit's lock acquisition is uncontended and costs on the order of 100ns,
several orders of magnitude below the filesystem-walk-plus-YAML-parse cost
a cold miss already pays) rather than claiming zero lock contact for warm
hits.

The `_locks` dict itself is intentionally **never cleared** by
`cache_clear()` (Section 5) — leftover `threading.Lock` objects for keys no
longer in the data cache are harmless (a `Lock` costs nothing to leave
around, and reusing the same `Lock` object across a `cache_clear()` boundary
is safe: an unheld `Lock` has no memory of what it used to guard).

### 6c. Both fix sites raise, never degrade (CL-006/FR-006)

**Resolved exception design (one concrete decision, not an either/or):**
this mission defines exactly **one** new exception class,
`MissionCacheLockError(ValueError)`, owned by
`src/charter/offering/missions/` — defined in
`mission_step_repository.py` (the primary fix site) alongside its
`_lock_for`/thread-local-YAML additions (Section 6a/6b), following the
same local-typed-exception pattern already established in this package
(`MalformedManifestError(Exception)` at `repository.py:39`,
`ActionIndexError(ValueError)` at `action_index.py:12` — both module-local,
neither imported from `specify_cli`). `mission_type_repository.py` imports
`MissionCacheLockError` from `.mission_step_repository`, mirroring the
import it already has for that module
(`from .mission_step_repository import MissionStepRepository,
_PackContextLike`, `mission_type_repository.py:12`) — so both fix sites'
new lock/cache-error raise paths (Section 6b's `_lock_for`-adjacent code
at both singleton sites) raise this **same** exception type, never two
different ones.

**`TemplateConfigurationError` is never imported into `src/charter/**`.**
It is defined at `src/specify_cli/runtime/resolver.py:71`
(`class TemplateConfigurationError(ValueError)`) — one layer above
`src/charter/**` in this project's documented dependency direction
(`kernel <- doctrine <- charter <- glossary/runtime <- specify_cli`, per
`tests/architectural/test_charter_no_specify_cli_import.py:3-5`). Raising
it from inside `mission_step_repository.py` or `mission_type_repository.py`
(both under `src/charter/`) would require a `charter -> specify_cli` import
edge, which `tests/architectural/test_charter_no_specify_cli_import.py`'s
`test_charter_never_imports_specify_cli`
(`tests/architectural/test_charter_no_specify_cli_import.py:89-103`)
asserts never exists, at any scope — an always-on, PR-blocking gate (the
`architectural-heavy` job, Section 11). If a caller above the
charter/specify_cli boundary ever needs to surface this failure to a
consumer as `TemplateConfigurationError`, that translation belongs on the
**specify_cli side** of the boundary (e.g. in
`src/charter/activation/mission_type_profiles.py`'s caller once control
returns to `specify_cli`, or in `src/specify_cli/runtime/resolver.py`
itself) — never inside `src/charter/**`. This mission's own fix sites only
ever raise `MissionCacheLockError`; they do not need to perform that
translation themselves.

If either lock acquisition needs a bound (see Section 7 — this plan does
**not** add a blocking-forever wait; see the timeout discussion there), the
timeout path raises `MissionCacheLockError`, never returns `None`, an empty
dict, or a partial result. This is a purely additive requirement on the
*new* code this mission writes; it does not touch the existing
`resolve_configured_template` raise sites in
`src/specify_cli/runtime/resolver.py:474-531`, which already satisfy
CL-006 with `TemplateConfigurationError` and are left unmodified.

## 7. Performance (NFR-002)

**Round-4 rewrite** (`reviews/plan.ruling.md`, PLAN-FRESH3-ARCH-002, sev 3):
the round-3 text below claimed one shared key shape ("`mission_type_id` +
`pack_context`") for both fix sites and concluded that "different mission
types never contend" at both. Neither half of that claim is accurate at the
second site — the two sites' key shapes and contention surfaces are
different, and the arbiter's own re-derivation from source
(`mission_type_profiles.py:952-953`) is restated here rather than merely
asserted. This section is re-derived **per site**, using the fact table in
Section 8a (also relied on by the test obligations).

### Per-site key shape and contention surface

- **PRIMARY_SITE** (`_resolve_all_for_mission_type_cached`, key
  `(builtin_root, mission_type_id, pack_context)`,
  `mission_step_repository.py:446-450`): `builtin_root` is fixed per
  process; two concurrent `create_mission_core` calls therefore share a key
  **only when both `mission_type_id` and `pack_context` match** — i.e. two
  concurrent creates of the *same* mission type in the *same* project.
  Different mission types (the common shape of "two agents provisioning
  missions concurrently", spec.md User Story 1) get different keys and
  proceed with **zero** lock contention between them, because Section 6b's
  lock is keyed identically to the cache. This part of the round-3
  conclusion is correct and is restated, not revised.
- **SECOND_SITE** (`resolve_layered_mission_types`, key
  `(mission_types_dirs, pack_context)`, `mission_type_repository.py:477-481`):
  `_resolve_action_slot` — the **only** production caller reachable from
  `create_mission_core` — always resolves and passes the identical fixed
  `mission_types_dirs = (MissionTemplateRepository.default_missions_root()
  / "mission_types",)` regardless of which mission type is being created
  (`mission_type_profiles.py:952-953`). So **every** concurrent
  `create_mission_core` call within one project (one `pack_context`) shares
  **one** key, whatever mission type each call is creating. Same-key
  contention is the *default* at this site, not a narrow edge case — the
  round-3 text's "the narrower same-key case" framing for this site
  (round-3 §8b) was the same error ARCH-002 names.

### Re-derived NFR-002 conclusion, per site

- **PRIMARY_SITE**: unchanged from round 3. A cold miss serializes only
  same-mission-type-same-project racers, for the duration of one
  filesystem walk plus YAML parse (typically single-digit milliseconds on
  local disk for the built-in tree's step count); a process resolves at
  most a handful of distinct mission types and warms almost immediately.
  Contention here is genuinely rare.
- **SECOND_SITE**: contention on the shared key is the default whenever
  `create_mission_core` calls race *within one process*, but the practical
  cost stays bounded for three independent reasons, stated honestly rather
  than reusing the primary site's "rare" framing:
  1. **The walk is small and fixed-size.** The built-in layer alone is 4
     YAML files today (`documentation`, `plan`, `research`, `software-dev`);
     org/project layers add at most a handful more in a typical project.
     One walk costs the same order of magnitude as the primary site's.
  2. **The key warms after the first population, for the rest of the
     process.** Per this mission's own reflexivity framing (CL-007) and the
     one-process-per-CLI-invocation model `resolve_layered_mission_types`'s
     own docstring documents (`mission_type_repository.py`, "Cache safety
     boundary" section), a single `spec-kitty` CLI invocation resolves this
     key at most once unless it spawns concurrent threads itself. The
     *only* process shape where this site's contention is observable at all
     is the exact concurrent-creation scenario this mission exists to fix
     (spec.md User Story 1, `test_concurrent_creates_no_collision`'s own
     shape) — and there, the serialization cost is paid **at most once**
     per process lifetime (the first concurrent cold race), never on every
     call.
  3. **The serialized cost is one walk, not N walks.** Without Section 6b,
     N racing threads would each pay the walk cost independently (N walks);
     with it, N racing threads pay one walk plus (N-1) uncontended-after-
     the-fact lock acquisitions once the leader has finished — strictly
     cheaper than the pre-fix, unsynchronized-but-still-redundant behavior,
     not a new bottleneck relative to it.
  **Conclusion, re-derived on the correct premise:** NFR-002's <2s
  single-threaded budget is unaffected at this site (a single-threaded
  invocation never contends — there is only ever one caller). For the
  concurrent-creation case, this site's default same-key contention is
  bounded to one small walk's duration, paid at most once per process, and
  is strictly better than the pre-fix redundant-work behavior it replaces —
  so the *substance* of "no NFR-002 regression" still holds, but not on the
  round-3 premise that this site's same-key case is rare; it holds because
  the case, though the *default*, is cheap and bounded.

Per the Edge Cases in `spec.md` ("a lock held across an I/O-bound YAML parse
on slow filesystem... must not turn a rare race into a routine
serialization bottleneck"): this plan does **not** add a lock-acquisition
timeout that would itself need a raise path for the *common* case — a
bounded wait that fires under normal I/O latency would violate C-002's
no-retry/no-bounded-degradation spirit by turning ordinary slow-disk I/O
into a manufactured failure.

**CL-008 amendment, restated here for §7's own reasoning:** SC-006
originally asked for a test forcing a lock-timeout, corrupted-cache, or
retry-exhaustion condition — none of which this design introduces (the
paragraph above confirms it: an ordinary blocking `Lock.acquire()`, no
timeout, no corruption-detection, no retry). `reviews/plan.fresh-4-debbie.yaml`
(PLAN-FRESH4-DEBBIE-001) established there was therefore no production
code path any test could force to exercise a raise. The operator amended
SC-006 (CL-008) to a satisfiable property instead: an exception raised
during cache population — from any source, e.g. a fault injected into the
step-loader or mission-type loader — propagates to the caller unchanged,
nothing partial is cached as a result, and the next call re-attempts
population and succeeds. The amended SC-006 obligation (Section 8, OBL-3)
exercises this via **fault injection directly into a site's
cache-population path** (the step-loader/mission-type-loader, or another
point in that site's walk that is not itself inside the loader's own
swallow catch — Section 8a's fact table; the concrete injection point is
WP-level, Section 9), not via any lock/cache-error seam Section 6b adds —
this plan defines no lock-timeout/corruption/retry raise path for OBL-3 to
force in the first place.

**This property holds by construction, independent of 6a/6b, at both
sites — stated honestly rather than assumed:** `functools.cache` never
stores a result for a call whose body raises (it only writes
`cache[key] = result` after the wrapped call returns normally), and
neither 6a (the thread-local YAML accessor) nor 6b (the
`with _lock_for(key): return _cached_fn(...)` wrapper) adds any
catch-and-degrade branch anywhere on either site's population path — a
`with` block around a raising call does not suppress the exception, it
only releases the lock on the way out. So the amended SC-006's
propagate/no-partial-cache/successful-retry property is already true at
Base (pre-fix), and stays true after 6a and/or 6b land. OBL-3 is therefore
a **construction-invariant regression guard**, not a test that
distinguishes 6a/6b's presence from absence the way OBL-1/OBL-2 do — its
value is catching a *future* implementation mistake (most plausibly a
defensive `try/except` accidentally added around 6b's lock-wrapped call)
that would silently degrade instead of raising, exactly the falsifiability
clause CL-008/SC-006 itself names ("fails if either (a) the propagation is
replaced with a silent-degrade return, or (b) the failed population is
cached"). Section 8b/8c restate this per-obligation.

**A warm hit's lock touch, honestly stated (Section 6b's reconciliation):**
under the round-4 single-flight design, every call — including a later,
completely uncontended warm hit at either site — acquires `_lock_for(key)`.
This is a deliberate, documented trade-off (Section 6b), not an oversight:
an uncontended `threading.Lock.acquire()`/`.release()` pair costs on the
order of 100 nanoseconds in CPython, several orders of magnitude below the
millisecond-scale filesystem-walk-plus-YAML-parse cost a cold miss already
pays, and immeasurably below the 2-second CLI budget.

Single-threaded `create_mission_core` stays under 2 seconds at both sites:
the added per-key-lock acquisition on a single-threaded run is always
uncontended, and the thread-local YAML swap has identical per-call cost to
the existing shared instance (same `YAML(typ="safe")` construction, just
once per thread instead of once per process — for a single-threaded CLI
invocation this is one construction either way). The existing test suite
already demonstrates this margin: `tests/core/test_mission_creation_identity.py`'s
4 tests (including two `create_mission_core` calls in
`test_concurrent_creates_no_collision` alone) complete in 0.90s total in
this checkout (Section 10, Baseline) — orders of magnitude under the 2s
per-call bar. The implementation WP should still add or reuse an explicit
single-call timing assertion per NFR-002's falsifiable bar, rather than
relying solely on this aggregate baseline number as post-fix proof.

## 8. Test strategy (per FR/AC) — test obligations, not harness mechanics

**Round-4 rewrite** (`reviews/plan.ruling.md`, "Global ruling: §8 becomes
obligations; mechanics move to tasks as binding notes"). Every changed
behaviour still gets a test that fails when reverted — that discipline is
unchanged. What changes is altitude: this section states **what must be
true, and why, per site** (the per-site fact table, the test obligation
table, the revert matrix, and binding constraints on any harness). It does
**not** state harness mechanics — dotted patch-target paths, dataclass
field values, barrier choreography, predicates, or the ruamel hook choice.
Those move to Section 9, "Binding notes for tasks," as WP-level directives.
The ruling's own diagnosis (`reviews/plan.ruling.md`, "Recurrence
diagnosis") is why: three rounds of patching mechanics inside the plan kept
creating new review surface without fixing the underlying gap, which was
always the **per-site facts** the mechanics consumed, not the mechanics
themselves.

This rewrite also fixes ARB-001/DEBBIE-001/ARCH-003 (the round-3 `8f`
obligation could not tell "6b present" from "6b reverted," because
round-3's §6b design ran the uncached walk twice under contention — see
Section 6b) and ARB-002 (round-3's `8b` raced the SAME key while pausing a
thread mid-walk, which — combined with either the round-3 or the round-4
§6b lock design — would deadlock or false-red once the fix landed, because
the paused thread holds the per-key lock across the barrier the other
thread needs). The obligation table below states explicitly, per test,
which fix half it isolates, and restructures the "6a proof" obligation to
race **distinct** cache keys — a configuration Section 6b's per-key lock
structurally cannot serialize — so it can never deadlock against 6b and
still exercises the shared-`YAML`-instance corruption 6a exists to close
(both sites' pre-fix singletons are global, unkeyed by cache key, so a
distinct-key race is just as vulnerable pre-fix as a same-key race).

### 8a. Per-site fact table

One row per fact, one column per site. Every obligation below cites this
table rather than restating these facts inline.

| Fact | PRIMARY_SITE (`mission_step_repository.py`) | SECOND_SITE (`mission_type_repository.py`) |
|---|---|---|
| Cache key shape | `(builtin_root, mission_type_id, pack_context)` — a 3-tuple (`_resolve_all_for_mission_type_cached`, `mission_step_repository.py:446-450`) | `(mission_types_dirs, pack_context)` — a 2-tuple (`resolve_layered_mission_types`, `mission_type_repository.py:477-481`) |
| Do concurrent `create_mission_core` calls in one project share this key? | Only when both `mission_type_id` **and** `pack_context` match (two concurrent creates of the *same* mission type). Different mission types get different keys and never contend (Section 7). | **Yes, by default.** `_resolve_action_slot` always passes the identical, fixed `mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)` (`mission_type_profiles.py:952-953`) regardless of mission type, so every concurrent `create_mission_core` call within one project (one `pack_context`) shares **one** key. Only calls from distinct `pack_context`s (different projects) get distinct keys (Section 7, ARCH-002). |
| What does one cache-miss population contain? | The **whole** `_resolve_all_for_mission_type_uncached` walk (`mission_step_repository.py:335-364`) — every `step_id` across built-in + org + project layers for one mission type (every `step.yaml` that mission type has), never one file. | The **whole** per-key walk (the full body of `resolve_layered_mission_types`, `mission_type_repository.py:580-601` — the `index` init, the always-executed `mission_types_dirs` loop, and the `pack_context` org/project branch, over `mission_types_dirs` + org + project layers) — every `*.yaml` file `scan_mission_types_dir` finds in every scanned layer (4 built-in files today, sorted: `documentation.yaml`, `plan.yaml`, `research.yaml`, `software-dev.yaml`), never one file. DEBBIE-001/ARCH-003 (round 3): the round-3 plan named `_load_layered_mission_type_file` — a per-file function called once per `*.yaml` — as this site's "cache-miss body." That was wrong; the unit `functools.cache` actually memoizes is the walk, not the per-file loader (Section 9's binding note names the corrected counting unit). |
| Loader's catch semantics | `_load_step_yaml` swallows **every** exception (`except Exception: return None`, `mission_step_repository.py:132-135`) — a corrupted parse is silently dropped as a missing step, never re-raised. | `_load_layered_mission_type_file` catches only `ruamel.yaml.error.YAMLError`, re-raising it as a named `ValueError` (`mission_type_repository.py:388-391`); any other corrupted-but-not-`YAMLError` outcome propagates uncaught (whatever `MissionType.model_validate`/the id-mismatch check raises), or, if the garbled parse happens to still validate with wrong-but-valid fields, raises nothing at all. |
| Site's own cache-clear seam | `MissionStepRepository.cache_clear()` (staticmethod, `mission_step_repository.py:323-333`) → `_resolve_all_for_mission_type_cached.cache_clear()`. | `MissionTypeRepository.cache_clear()` (staticmethod, **not** `.default`, `mission_type_repository.py:188-206`) → `resolve_layered_mission_types.cache_clear()`. Deliberately independent from `MissionTypeRepository.default.cache_clear()` (Section 5). |
| Other unguarded users of the site's YAML instance | None found in `src/`: the only caller of `MissionStepRepository.resolve()`/`_load_step_yaml` in this checkout is `_resolve_all_for_mission_type_uncached` itself (`mission_step_repository.py:361`) — already inside the cached/locked path. | `src/charter/activation/pack_manager.py:1014`, inside `CharterPackManager.list_available_detailed`'s mission-type branch, calls `scan_mission_types_dir(scan_dir)` **directly** — bypassing `resolve_layered_mission_types` (and therefore both `functools.cache` and Section 6b's per-key lock) entirely, reaching `_load_layered_mission_type_file` → the shared YAML accessor unguarded by anything this mission's fix adds (ARB-002 point 2). Noted here, and named again in OBL-1's second-site construction below as an alternate/backup 6a-proof path — reaching this site through `pack_manager` is *also* a configuration Section 6b's lock structurally cannot guard, since it never goes near `_lock_for` at all. |

### 8b. Test obligation table

One row per test (mapping the round-3 `8b`/`8c`/`8d`/`8e`/`8f` letters onto
obligations, per the ruling's disposition).

| Test | Traces (AC/FR/NFR/SC) | Observable property asserted | Fix half isolated | Why RED at the red-first commit, per site | Revert-cell state |
|---|---|---|---|---|---|
| **OBL-1** — forced-interleave content-correctness, **distinct** cache keys ("6a proof") — was `8b` | FR-002/FR-004/FR-005, CL-003/CL-004, SC-001, User Story 1 AC1/AC2 | Two threads racing **distinct** cache keys at one site, driven through `create_mission_core` (PRIMARY_SITE) or the resolver path it drives (SECOND_SITE — CL-004's "or the resolver path it drives," required here per the WP caution below), never corrupt each other's captured result. | **6a** (thread-local YAML). Section 6b's per-key lock structurally cannot serialize this race (distinct keys → distinct `Lock` objects → no contention), so this obligation is unreachable by 6b alone — it isolates 6a. | PRIMARY_SITE: pre-fix, both threads' `.load()` calls share `_YAML` regardless of their distinct `mission_type_id` (research.md Q(a)); the "paused" thread's own captured `resolve_all_for_mission_type(...)` result, reached via `create_mission_core`, is corrupted or raises. SECOND_SITE: pre-fix, both threads' `.load()` calls share `_LAYERED_YAML` regardless of their distinct `pack_context`; the "paused" thread's own captured roster result is corrupted or raises. Both sites' swallow-vs-raise asymmetry (8a fact table) means the exact pre-fix failure shape differs (a dropped step vs. a raised `ValueError`/silently-wrong `MissionType` field) — the content-correctness assertion (field-by-field against a known-good reference, per-thread-captured, never a post-join re-read of the now-memoized cache) catches all shapes at both sites. | **Base**: red at both sites. **6a+6b**: green at both sites. **6a reverted, 6b kept**: red at both sites — 6b's lock never engages for a distinct-key race, so the corruption is unmasked exactly as pre-fix. **6b reverted, 6a kept**: green at both sites — 6a alone already removes the only shared mutable object. |
| **OBL-2** — redundant-population count, **same** cache key ("6b proof") — was `8f` | FR-002 (defense-in-depth), spec.md Edge Cases ("same mission type and artifact kind concurrently"), SC-001 | Two threads racing the **identical** cache key cause the per-key walk unit (8a fact table: the whole walk, never a per-file helper) to execute exactly once, never twice. | **6b** (single-flight per-key lock). Not distinguishable from a passing correctness test once 6a is present (redundant execution is wasteful, not corrupting, post-6a) — this is the only test that can tell "6b present" from "6b silently reverted." | Both sites: pre-fix, nothing serializes the two threads (no lock exists yet), so the walk unit runs twice — red in the trivial "the seam does not exist yet" sense (OBL-3 is no longer a same-sense comparison here — see OBL-3's own row: it is green at Base, not red), not because it demonstrates the corruption race (that is OBL-1's job). | **Base**: red at both sites (trivially — no lock exists). **6a+6b**: green at both sites, count == 1. **6a reverted, 6b kept**: green at both sites — 6b still serializes to exactly one population regardless of 6a's presence; the *result* may be corrupt (OBL-1's concern), but the *count* stays 1, which is exactly why OBL-1, not OBL-2, is the 6a-revert proof (ARB-002). **6b reverted, 6a kept**: red at both sites, count == 2. |
| **OBL-3** — amended-SC-006 raise-not-degrade regression guard — was `8c` | FR-006, CL-006, SC-006 (as amended by CL-008, 2026-09-23) | A fault injected into a site's cache-population path — the step-loader/mission-type-loader, or another point in that site's walk that is not itself inside the loader's own swallow catch (Section 8a fact table; concrete seam is WP-level, Section 9) — driven through `create_mission_core`, (1) propagates to the caller unchanged, never converted to `None`/empty/partial, (2) leaves nothing partial cached, and (3) a subsequent call re-attempts population and succeeds. Replacing the propagation with a silent-degrade return, or leaving the failed population cached, makes the assertion fail (CL-008's own falsifiability clause). | **None.** This is a construction-invariant property, not a fix-isolating one: `functools.cache` never stores a result for a call whose body raises, and neither 6a nor 6b adds a catch-and-degrade branch anywhere on either site's population path (a `with _lock_for(key):` block does not suppress an exception raised inside it). The property already holds at Base and continues to hold identically once 6a and/or 6b land — OBL-3 does not distinguish "6a present" from "6a absent," or "6b present" from "6b absent," the way OBL-1/OBL-2 do. | **Not red at the red-first commit — green from Base onward, at both sites**, since the fault-injection point named above (unlike OBL-1's/OBL-2's targets) is an already-existing function, unchanged by either 6a's rename/accessor swap or 6b's lock-wrapper/split, so the test needs no new production seam to run. Committed alongside the red obligations for review-diff cohesion (Section 14), as a falsifiable regression guard against a future implementation mistake (e.g. a defensive `try/except` accidentally added around 6b's lock-wrapped call), never as evidence of the corruption race. | **Base**: green at both sites (the property already holds — no fix code required). **6a+6b**: green at both sites (still holds — neither half adds a swallow). **6a reverted, 6b kept**: green at both sites (unaffected — the property does not depend on 6a). **6b reverted, 6a kept**: green at both sites (unaffected — the property does not depend on 6b's lock wrapper existing; the pre-split `resolve_layered_mission_types`/`_resolve_all_for_mission_type_cached` already don't swallow either). |
| **OBL-4** — existing natural test must not regress — was `8d` | AC3/SC-002, NFR-001 (no new natural-timing test added in its place) | `test_concurrent_creates_no_collision` keeps passing, unmodified, both before and after the fix. | None specifically — a sanity net over both halves together, not a revert-discipline instrument. | Already green pre-fix (Section 10 baseline); this test's job is to *stay* green, never to turn red first. | **Base**: green. **6a+6b**: green. Either half reverted: still green — research.md's own reproduction protocol (0/300 cold-subprocess reruns, 0/2000 Barrier-synchronized cache-cleared in-process trials) is exactly why this test cannot be relied on for revert discipline. |
| **OBL-5** — `cache_clear()` mid-population, no deadlock — was `8e` | NFR-003, spec.md Edge Cases | Calling the site's own `cache_clear()` while a population is in flight neither deadlocks nor raises, and the in-flight population still completes with a correct result once released (Section 5's edge-case walkthrough). | 6b (the per-key lock exists) interacting correctly with Section 5's cache-clear contract. | Both sites: not meaningfully checkable pre-fix (no lock exists to interact with `cache_clear()`); included in the red-first commit for review-diff cohesion (Section 14), not because it demonstrates the production race. | **Base**: not applicable (seam absent). **6a+6b**: green at both sites, no deadlock. **6a reverted, 6b kept**: green (Section 5's walkthrough does not depend on 6a). **6b reverted, 6a kept**: not applicable (nothing to race). |

**OBL-1's second-site construction, and the WP caution behind it (ARB-002
point 3):** a distinct-`pack_context` race at SECOND_SITE cannot be driven
through two concurrent calls to the existing `_run_create` test helper,
because `_patched_mission_creation_context` patches process-global targets
via `unittest.mock.patch` (`tests/core/test_mission_creation_identity.py:54-70`)
— unsafe for two distinct project roots racing in two threads. CL-004
explicitly allows driving "the resolver path [`create_mission_core`]
drives" as the outer call when a purely internal seam is unavoidable; here
it is `resolve_mission_type_context`/`_resolve_action_slot` (the same
function `create_mission_core` calls), invoked directly from two threads
with two distinct `pack_context`s (e.g. two `tmp_path`-rooted projects).
This still satisfies the "outer call, monkeypatch confined to timing"
discipline — the monkeypatch forces the pause, it does not replace the
resolver call itself. The `pack_manager.py:1014` path (8a fact table) is a
noted alternate construction for the same obligation, not required unless
the resolver-path construction proves unworkable in the WP.

### 8c. Revert matrix

| State | Required result |
|---|---|
| Base | OBL-1 red at both sites (the 6a-revert-proof race, distinct keys); OBL-2 red at both sites for the trivial "seam absent" reason (Section 14 states which reds are load-bearing and which are trivial); **OBL-3 already green at both sites** — the amended-SC-006 propagate/no-partial-cache property holds by construction before 6a/6b land (Section 8b) |
| 6a+6b applied | OBL-1 through OBL-5 all green, both sites, no deadlock |
| 6a reverted, 6b kept | OBL-1 red at both sites — 6b's lock never engages for a distinct-key race, so the corruption 6a exists to close is unmasked; OBL-2, OBL-3, OBL-4, OBL-5 unaffected (still green) |
| 6b reverted, 6a kept | OBL-2 red at both sites — the redundant-population count becomes 2; OBL-1, OBL-3, OBL-4, OBL-5 unaffected (still green) — OBL-3 does not depend on 6b's lock wrapper existing (Section 8b) |

6a **is** reachable outside Section 6b's lock at both sites under the
chosen 6b design (OBL-1's distinct-key construction), so no fallback to a
lock-avoiding path is structurally required — but `pack_manager.py:1014`
(8a fact table) is named as the alternate/backup SECOND_SITE construction
per the ruling's own naming of it as a candidate, in case the
resolver-path-direct construction proves unworkable during implementation.

### 8d. Binding constraints on any harness

Stated as constraints, not code — the concrete predicates, patch targets,
and fixture shapes that satisfy them are WP-level (Section 9):

1. The pin that distinguishes the "paused" thread's target from the
   "uncontended" thread's target is by **file identity**, inside the
   shared load window — never dependent on call order or iteration order
   (DEBBIE-002; the primary site's own walk iterates an unsorted `set`,
   `mission_step_repository.py:344,360`, so iteration order is not a valid
   pin there).
2. The timing seam exists, unedited, at **both** the red commit and the
   green commit (DEBBIE-002) — the pre-fix module-level singletons
   (`_YAML`/`_LAYERED_YAML`) do not exist post-6a, so the seam must be
   something invariant across both commits (Section 9 names the candidate).
3. No lock is held across a barrier the other thread needs (ARB-002) — the
   6a-proof obligation (OBL-1) races distinct keys precisely so this can
   never arise; a same-key pause-while-holding-the-lock construction is
   never used for a 6a-revert proof.
4. Teardown is function-scoped (a `pytest` `monkeypatch` fixture,
   auto-reverted) — never a bare module-level patch left in place (spec.md
   Edge Cases, "the test must clean up after itself").
5. The count any test asserts guards a count of **populations** (the whole
   per-key walk unit, 8a fact table), never a count of per-file loader
   calls (DEBBIE-001/ARCH-003).
6. NFR-001 determinism is verified across **separate processes with
   varied `PYTHONHASHSEED`**, not a single in-process loop over one hash
   seed (DEBBIE-002 — the primary site's unsorted-`set` walk order depends
   on the per-process hash seed, so an in-process 50-rep loop would not
   detect a verdict that varies across seeds).
7. CL-004's outer-call rule holds: PRIMARY_SITE and SECOND_SITE's
   default (same-`pack_context`) obligations drive through
   `create_mission_core`; SECOND_SITE's distinct-`pack_context` OBL-1
   construction drives the resolver path directly, per the WP caution in
   Section 8b (the ruling's ARB-002 WP-caution exception to the outer-call
   rule).

## 9. Binding notes for tasks

Harness mechanics that used to live in Section 8 (round 3) live here
instead, as WP-level directives — they are not plan-level review surface
(`reviews/plan.ruling.md`, "Global ruling," item 6). Tasks/WP authors bind
these to the obligations in Section 8.

**Counting unit, per site (DEBBIE-001/ARCH-003):** OBL-2's "exactly once"
assertion must instrument and count invocations of the whole per-key walk
unit — `_resolve_all_for_mission_type_uncached` at PRIMARY_SITE (already
correctly named, unchanged), and, at SECOND_SITE, a **new** name for the
walk body currently inline in `resolve_layered_mission_types`
(`mission_type_repository.py:580-601` — the full function body: `index`
init, the always-executed `mission_types_dirs` loop, the `pack_context`
branch, and the return) — e.g. extracting it as
`_resolve_layered_mission_types_uncached(mission_types_dirs,
pack_context)`, mirroring the primary site's own uncached/cached split.
Counting `_load_layered_mission_type_file` invocations is wrong (it runs
once per `*.yaml` file — 4 today — inside a single population) and must
not be used.

**Timing seam, surviving both commits (DEBBIE-002):** the pre-fix patch
target `_YAML.load`/`_LAYERED_YAML.load` (a module-level instance
attribute) does not exist post-6a (replaced by a thread-local accessor).
A seam that survives both commits unedited must patch something invariant
across the rewrite — the WP's spike (required before the red commit,
per DEBBIE-002's disposition) should evaluate a **class-level** hook on
`ruamel.yaml.main.YAML` itself (both the pre-fix singleton and the
post-fix thread-local instance are instances of the same class), combined
with a **path-aware** predicate at the call sites that do not change name
across the fix — `_load_step_yaml(step_file)` /
`_load_layered_mission_type_file(yaml_file, ...)` both keep their name and
their `Path` argument pre- and post-fix, so a predicate keyed on that
`Path` (not on call order, not on raw `.load()` text content, which
carries no file identity) is the stable pin DEBBIE-002 requires. The pause
itself must land strictly inside the shared instance's load window — after
`self.reader.stream` is assigned, before composition completes
(`research.md`'s traced mechanism) — which is a deeper hook than
`YAML.load` itself (e.g. inside `YAML.get_constructor_parser` or the
reader/composer chain it returns); the exact hook is the WP spike's
output, not fixed here.

**Cross-process/hash-seed determinism (NFR-001):** the "run 50 times, same
verdict" falsifiable check runs as N separate subprocess (or
`pytest-xdist` worker) invocations with varied `PYTHONHASHSEED`, not one
in-process loop — a single process keeps one hash seed for its lifetime
and cannot detect a verdict that depends on the primary site's unsorted-
`set` iteration order.

**OBL-3's fault-injection seam, per site (amended SC-006/CL-008):**
Section 8b/8c state the property at plan-level ("a fault injected into a
site's cache-population path... that is not itself inside the loader's
own swallow catch"); the concrete seam is WP-level. At SECOND_SITE, the
loader itself already propagates (`_load_layered_mission_type_file`
catches only `YAMLError`, re-raising as `ValueError`; Section 8a fact
table), so patching `_load_layered_mission_type_file` (or
`MissionType.model_validate`, which it calls unguarded) to raise a
distinct forced exception is a direct, real construction. At PRIMARY_SITE,
`_load_step_yaml`'s own `except Exception: return None` swallows
everything raised inside it, so the fault must be injected **outside**
that function — e.g. patching `_add_step_ids_from_dir`
(`mission_step_repository.py:163-169`, called from
`_resolve_all_for_mission_type_uncached` with no surrounding try/except)
to raise, which is unchanged by both 6a (touches only the YAML
singleton/accessor) and 6b (touches only the call site, not this
step-id-collection helper) — a stable pin across the red and green
commits, per DEBBIE-002's "the seam survives both commits" constraint
(Section 8d item 2).

**Illustrative sketch (non-normative — WPs may implement differently, so
long as Section 8's obligations and Section 8d's constraints hold):**

```python
@dataclass(frozen=True)
class _FixSiteCase:
    site_id: str  # "primary" | "second"
    site_cache_clear: str          # this site's own cache-clearing staticmethod (OBL-5)
    walk_unit: str                 # the whole per-key walk (OBL-2's counting target — see above, never a per-file helper)
    distinct_key_race: tuple[str, str]   # OBL-1: two distinct keys at this site
    same_key_race: str                    # OBL-2: one key, raced by two threads


PRIMARY_SITE = _FixSiteCase(
    site_id="primary",
    site_cache_clear="MissionStepRepository.cache_clear",
    walk_unit="MissionStepRepository._resolve_all_for_mission_type_uncached",
    distinct_key_race=("software-dev", "documentation"),  # two mission_type_ids, same pack_context
    same_key_race="software-dev",
)
SECOND_SITE = _FixSiteCase(
    site_id="second",
    site_cache_clear="MissionTypeRepository.cache_clear",  # NOT .default -- Section 5
    walk_unit="charter.offering.missions.mission_type_repository._resolve_layered_mission_types_uncached",
    distinct_key_race=("project-a", "project-b"),  # two distinct pack_contexts, driven via the resolver path directly (Section 8b WP caution)
    same_key_race="default-project",
)


def _cold_cache() -> None:
    MissionStepRepository.cache_clear()
    MissionTypeRepository.default.cache_clear()
    MissionTypeRepository.cache_clear()  # no `.default` -- Section 5's second,
                                          # independent seam; every obligation
                                          # that races SECOND_SITE needs this
                                          # cache provably cold too.
```

**No lock held across a barrier the other thread needs (restated as a
binding constraint here, tied to the ARB-002 fix):** any WP harness that
pauses a thread mid-walk while that thread holds `_lock_for(key)` must
never pair it with another thread racing the *same* key — that pairing is
reserved for OBL-2 (which does not need a long pause: a `threading.Barrier`
ensuring simultaneous entry is sufficient, since the single-flight design,
Section 6b, resolves a same-key race cleanly without deadlock). OBL-1's
distinct-key construction is the only place a long monkeypatch-forced pause
mid-walk is used, and it is safe by construction because the other thread
never contends for the paused thread's lock.

## 10. Baseline (CL-005)

**Round-4 update** (`reviews/plan.ruling.md`, PLAN-FRESH3-ARCH-001): round
3's baseline covered only `tests/core` and `tests/missions` because round
3's Gate Set (old Section 10) named only two selected modules
(`missions`/`core_misc`). Section 11 below corrects the module list to the
five `select_modules` actually returns; this section extends the baseline
to cover every one of those five modules' `test_dirs`.

**Branch/baseline discipline confirmed before running anything**: this
checkout's HEAD (`6390fcf51`) sits on the mission's own working branch,
with only `kitty-specs/` changed since the mission's pre-change scaffold
commit —

```
$ git diff --stat 288aef2f9 -- src tests
```

— returns **empty**. So the current checkout *is* the pre-change baseline
for `src`/`tests`; the runs below were executed directly here, with no
worktree and no HEAD movement, per this round's instructions.

Captured fresh, at this mission's own scaffold commit (`288aef2f9`, HEAD at
research/plan time, `spec.md` committed, **zero code changes** yet) — not
issue #3284's stale numbers, which do not apply to this mission.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest \
    tests/core/test_mission_creation_identity.py -q
....                                                                     [100%]
4 passed in 0.90s
```

Due-diligence runs, scoped to every `test_dirs` entry of the five modules
Section 11's `select_modules` run actually selects (`missions`, `core_misc`,
`charter`, `unit`, `specify_cli_runtime`):

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/missions -q
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 67%]
........................................................................ [ 90%]
...............................                                          [100%]
319 passed, 3 warnings in 21.57s
```
(The 3 warnings are pre-existing `DeprecationWarning`s about a legacy
`mission.yaml` asset path unrelated to this mission's YAML-concurrency
defect — not failures. `missions` has no explicit `test_dirs` row, so this
is its canonical mirror.)

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/core -q \
    --ignore=tests/core/test_upgrade_probe_and_notifier.py
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 68%]
..............................................................ss........ [ 91%]
..........................                                               [100%]
312 passed, 2 skipped in 11.13s
```
(`tests/core/test_upgrade_probe_and_notifier.py` was excluded because it
fails to *collect* under a plain `uv run --frozen pytest` invocation —
`ModuleNotFoundError: No module named 'respx'`. `respx` is declared in
`pyproject.toml:107`/`uv.lock:2499` under the `test` extra, which this ad
hoc baseline invocation did not install (`--frozen` alone, no `--extra test`
/ `--all-extras`). This is an environment-invocation scoping detail, not a
code failure, not attributable to this mission, and unrelated to the YAML/
cache-concurrency defect. `tests/core` is one of `core_misc`'s several
`test_dirs`.)

**Round-5 extension (PLAN-FRESH3-ARCH-001 residual, sev 2,
`reviews/plan.verify-4.yaml`): the remaining eight `core_misc`
`test_dirs`.** `core_misc`'s registry row (`.github/ci-module-registry.yml:232-243`)
lists **nine** `test_dirs`, not one; round 4's baseline above ran only
`tests/core`. Re-confirmed before running anything further —

```
$ git diff --stat 288aef2f9 -- src tests
```

— still returns **empty**, so this checkout remains the pre-change
baseline. This checkout's `.venv` was also missing the `test` extra (the
`build` package — the exact cause of the three `test_packaging_parity.py`
setup errors recorded above); it was installed once, in this checkout, via
`uv sync --frozen --extra test` (no bare `uv run` was used for anything
else this round; every run below invokes `.venv/bin/python -m pytest`
directly, same `env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1` prefix as
above for consistency). Each of the eight directories below was confirmed
to exist via `ls` before running:

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/core -q
544 passed, 1 skipped in 4.85s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/coordination -q
181 passed in 6.11s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/coordination -q
395 passed, 10 skipped in 26.04s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/decisions -q
17 passed in 5.17s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/doctrine_synthesizer -q
131 passed in 1.00s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/tool_surface -q
1098 passed, 3 warnings in 1009.74s (0:16:49)
```
Zero failures. The 3 warnings are pre-existing (`LegacyOrgPackDoctrineKeyWarning`
on a legacy `.kittify/config.yaml` key, and `DoctrineLayerCollisionWarning`
on an intentional org-overlay-precedence fixture) — unrelated to this
mission's YAML/cache-concurrency surface, not failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/asset_preservation -q
26 passed in 0.43s
```
Zero failures.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/zeitgeist_client -q
821 passed, 16 skipped, 1 warning in 105.91s (0:01:45)
```
Zero failures. The 1 warning is a pre-existing pydantic-settings
`IncompleteFieldDefinitionWarning` on an unrelated `lifespan` field,
unconnected to this mission's surface.

All eight directories are clean. `core_misc`'s baseline is now **9/9
`test_dirs` covered**, closing the PLAN-FRESH3-ARCH-001 residual gap
(`reviews/plan.verify-4.yaml`).

**`test_packaging_parity.py` re-run, post-`test`-extra-sync:**

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 .venv/bin/python -m pytest tests/doctrine/test_packaging_parity.py -q
3 passed in 21.90s
```
The three setup errors recorded above were exactly the missing-`build`-
package environment gap they were diagnosed as: installing the `test`
extra clears them with no other change and no code touched (this mission
still shows **zero** `src`/`tests` diff against `288aef2f9`). Read together
with the `tests/doctrine` run above, `tests/doctrine`'s true baseline is
**3204 passed** (the 3201 recorded above plus these 3), 13 skipped, 0
errors — not the "3 errors" figure the round-4 text recorded, which
reflected only the un-synced `.venv` that ad hoc invocation started with,
not a real or attributable failure.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/doctrine -q
3201 passed, 13 skipped, 90 warnings, 3 errors in 307.78s (0:05:07)
```
Three errors, all at fixture **setup** (not from any test body) in
`tests/doctrine/test_packaging_parity.py` (`test_wheel_ships_built_in_packs_at_exact_parity`,
`test_sdist_ships_built_in_packs_at_exact_parity`,
`test_clean_venv_install_imports_and_resolves_built_in`) — each fails with
`subprocess.CalledProcessError` from the shared `built_artifacts` fixture
running `python -m build --outdir ...`. Confirmed directly:

```
$ .venv/bin/python -m build --outdir /tmp/manual-check .
<checkout>/.venv/bin/python: No module named build
```

The `build` PEP 517 frontend package is not installed in this checkout's
`.venv` — a pre-existing environment-provisioning gap (an optional/test-only
tool this ad hoc invocation never installed), unrelated to the
`src/charter/offering/missions/**` YAML/cache-concurrency surface this
mission touches, and pre-existing (this checkout has made no code changes
yet, per the empty `git diff --stat 288aef2f9` above). `tests/doctrine` is
one of `charter`'s two `test_dirs` (the other is `tests/charter`, below);
`tests/doctrine/missions/` also holds `test_mission_step_resolver.py` and
`test_mission_type_repository.py` — the dedicated suites for both this
mission's fix sites, including `TestLayeredMissionTypesCacheKeyAndClear.test_same_key_is_a_cache_hit`
(`tests/doctrine/missions/test_mission_type_repository.py:660`), which pins
SECOND_SITE's documented cache-staleness contract (`mission_type_repository.py`,
"Cache safety boundary" docstring) — a contract Section 6b's redesign must
not disturb (verified by inspection: the single-flight lock changes only
*when* `functools.cache`'s own dict is written, never *whether* a
same-key second call is a hit, so this test's own assertion — `second is
first` — is unaffected).

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/charter -q
2942 passed, 22 skipped, 73 warnings in 888.95s (0:14:48)
```
Zero failures. `tests/charter` is `charter`'s other `test_dirs` entry.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/unit -q
496 passed, 1 warning in 10.25s
```
Zero failures. `tests/unit` is the `unit` module's sole `test_dirs` entry —
its roots include `src/charter/offering/missions/**`, which is why
`select_modules` (Section 11) selects it.

```
$ env -u FORCE_COLOR NO_COLOR=1 PWHEADLESS=1 uv run --frozen pytest tests/specify_cli/runtime -q
90 passed, 1 warning in 19.12s
```
Zero failures. `tests/specify_cli/runtime` is the `specify_cli_runtime`
module's sole `test_dirs` entry — same reason as `unit` above.

**Every module `select_modules` selects has been run at the pre-change
baseline, and — per the round-5 extension above — every one of
`core_misc`'s nine `test_dirs` is now individually covered, not just
`tests/core`. Re-running `test_packaging_parity.py` after installing the
missing `test` extra clears all three of its setup errors (3 passed, 0
errors); there is no remaining pre-existing red anywhere in this
baseline** — stated plainly per CL-005's instruction not to invent hedging
when a baseline is clean, and not to attribute pre-existing red to this
mission where none survives. The three setup errors were always an
environment-provisioning gap (the `build` package, absent from this
checkout's un-synced `.venv`), never a code defect; per C-003, no tracker
issue is warranted for it now that installing the extra confirms this. If
the implementation phase's own fuller run (post-fix, across the same
surfaces) turns up any *other* unrelated red, the same rule applies.

## 11. Gate set

Derived directly from `.github/ci-module-registry.yml` (read in full,
810 lines) and `.github/workflows/ci-aggregate.yml`/`ci-router.yml`/
`ci-quality.yml`/`sonar.yml` (read directly, not summarized secondhand).

**Round-4 fix** (`reviews/plan.ruling.md`, PLAN-FRESH3-ARCH-001, sev 4): the
round-3 module list below was wrong on two counts. It named only two
selected modules (`missions`, `core_misc`) and explicitly said `charter`
was "NOT selected" — but `charter`'s own roots (`src/charter/**`,
`ci-module-registry.yml:143-160`) plainly include
`src/charter/offering/missions/**`, and this very section's own
`architectural-heavy` gate reasoning (below, unchanged) already says that
job fires "because `needs.changes.outputs.charter == 'true'`" — a direct
self-contradiction the arbiter caught. The module list is now derived by
**actually running** the registry's own selection authority, read-only,
against this mission's changed-file set, rather than reasoning about it by
hand:

```
$ uv run --frozen python3 -c "
from scripts.ci.gate_selection import select_modules
changed = [
    'src/charter/offering/missions/mission_step_repository.py',
    'src/charter/offering/missions/mission_type_repository.py',
    'tests/core/test_mission_creation_identity.py',
]
print(sorted(select_modules(changed)))
"
['charter', 'core_misc', 'missions', 'specify_cli_runtime', 'unit']
```

**Five modules selected**, all confirmed against their registry rows
(`.github/ci-module-registry.yml`):

- **`missions`** (`:27-39`) — roots include
  `src/charter/offering/missions/**` explicitly. No explicit `test_dirs`
  row, so its canonical test mirror is `tests/missions` (319 tests, all
  passing per Section 10). `shard_count: 1`.
- **`core_misc`** (`:207-...`) — an aggregate module whose roots also
  include `src/charter/offering/**` (broader than, and overlapping with,
  `missions`' own narrower root — `scripts/ci/gate_selection.py:297`'s own
  comment acknowledges "overlapping glob ownership between groups" as
  accepted and intentional, not a bug to route around). `test_dirs`
  includes `tests/core`, where the new test obligations (Section 8) and the
  failing-test's ATDD entry point live. `shard_count: 5`.
- **`charter`** (`:143-160`, roots `src/charter/**` broadly, `test_dirs:
  tests/charter, tests/doctrine`) — **selected**, not "NOT selected" as
  round 3 said. `src/charter/offering/missions/**` is a subset of
  `src/charter/**`. `shard_count: 5`. Baseline: Section 10 (`tests/charter`
  2942 passed/22 skipped; `tests/doctrine` 3204 passed/13 skipped/0
  errors).
- **`unit`** (`:244-267`) — a TEST-INVENTORY module whose roots are a
  verbatim copy of surfaces other rows already own, including
  `src/charter/offering/missions/**`; `test_dirs: tests/unit`. **Not named
  at all in the round-3 list.** `shard_count: 1`. Baseline: Section 10 (496
  passed).
- **`specify_cli_runtime`** (`:269-285`) — same TEST-INVENTORY shape, roots
  include `src/charter/offering/missions/**`; `test_dirs:
  tests/specify_cli/runtime` (no `tests/specify_cli_runtime` mirror exists,
  so this row is load-bearing for module-tests.yml's directory lookup).
  **Not named at all in the round-3 list.** `shard_count: 1`. Baseline:
  Section 10 (90 passed).

**Confirmed NOT selected:**

- **`next`** (`:80-90`, roots `src/specify_cli/runtime/**`, `shard_count:
  2`) — unchanged from round 3. `spec.md`'s candidate blast radius names
  `src/specify_cli/runtime/resolver.py` as the symptom's raise site, but
  this plan (Section 1/6) makes no change there — the existing
  `TemplateConfigurationError` raise sites in `resolve_configured_template`
  are preserved unmodified, per CL-006's own framing ("this applies to both
  the existing raise sites ... and any new cache/lock code"; the existing
  ones already satisfy the requirement). If implementation discovers a need
  to touch `resolver.py` after all, the `next` gate becomes selected and
  this plan's WP scope must be revised to say so explicitly. This is
  confirmed by the `select_modules` run above too: `next` is absent from
  its output.

**Enforced CI gates and why each does or doesn't apply**, read directly
from the workflows (not assumed from any prior brief):

- **`diff-cover` PR gate** (`ci-aggregate.yml:263-369`, job named
  `"diff-cover PR gate (>=90% changed critical-path lines)"`) — this is the
  real, enforced, >=90%-changed-critical-path-lines coverage gate. **Note
  for the record**: the hub's gate table names this gate by two older
  aliases ("kernel 90% floor" / "mission loader coverage gate"); reading
  `ci-aggregate.yml` directly shows the actual mechanism is this one
  `diff-cover` job (installing `diff-cover==10.3.0`, scoring the PR diff
  against reconciled per-module coverage XML). **Applies** — every line
  this mission's fix commits changes is a changed critical-path line by
  construction.
- **`import-linter` (TID251 banned-API lint)** (`ci-router.yml:420-433`,
  `ruff check --select TID251 .`) — **always runs, applies.** This fix adds
  no banned import; `threading` and `functools` are already used
  extensively elsewhere in `src/`.
- **`uv-lock` (`uv lock --check`)** (`ci-router.yml:409-418`) — **does not
  need to pass a *new* check specific to this PR** because this fix adds no
  dependency and changes no `pyproject.toml`/`uv.lock` entry; the existing,
  already-committed lockfile stays valid. (The job still runs per its own
  `on:` trigger — it is simply unaffected by this diff.)
- **`markdownlint`** (`ci-router.yml:401-407`) — runs on `**/*.md`
  (`plan.md`, `research.md`, and `spec.md` already committed, all `.md`),
  but its own step is `npx --yes markdownlint-cli2 "**/*.md" || true` —
  **the `|| true` makes this job unconditionally non-blocking**, whatever
  it finds. Named here for completeness, not treated as an enforced gate.
- **`commit-msg` ("commit message lint")** (`ci-router.yml:391-399`) — its
  actual step body is `git log --format=%s origin/${{ github.base_ref ||
  'main' }}..HEAD || true`, i.e. it prints commit subjects and always
  succeeds. **This is not an enforced commitlint check in this checkout** —
  named here because the task brief assumed a "commitlint" gate exists;
  direct read of `ci-router.yml` shows no tool actually validates commit
  message format, only a non-blocking log dump. Stated as a finding, not
  papered over.
- **`architectural-heavy` ("architectural battery (heavy, code-scoped)")**
  (`ci-router.yml:510-560`) — **applies and is load-bearing for this
  mission.** Its `if:` condition (`ci-router.yml:528`,
  `needs.changes.outputs.charter == 'true'`, one arm of the OR-of-every-
  src-backed-filter-group at `ci-router.yml:515-536`) evaluates `true` for
  this diff, because it lands entirely under `src/charter/**`
  (`src/charter/offering/missions/**`, Section 1) — consistent with, not
  contradicting, the corrected module list above: `charter` **is**
  selected (round-4 fix), so this `if:` clause firing on
  `needs.changes.outputs.charter == 'true'` is exactly what the module list
  now says should happen, closing the round-3 self-contradiction the
  arbiter flagged. The `unit` and `specify_cli_runtime` outputs are also
  both arms of the same OR-of-every-src-backed-filter-group condition
  (`ci-router.yml:515-536`), so this job would have fired on this diff even
  without the `charter` correction. The job runs the full
  `tests/architectural` tree (`ci-router.yml:554` onward), deselecting only
  four unrelated files (`test_no_legacy_terminology.py`,
  `test_layer_rules.py`, `test_pyproject_shape.py`,
  `test_archive_root_byte_identical.py`) — **`tests/architectural/test_charter_no_specify_cli_import.py`
  is not among the deselected files, so it runs.** That test
  (`test_charter_never_imports_specify_cli`,
  `tests/architectural/test_charter_no_specify_cli_import.py:89-103`,
  docstring's binding direction statement at lines 3-5) is directly
  load-bearing here given Section 6c's exception-design decision (below):
  the new exception class this mission introduces must stay inside
  `src/charter/**` and never import `specify_cli`, or this gate fails the
  PR. `router-gate`'s own `needs:` list (`ci-router.yml:699-717`) includes
  `architectural-heavy` under an `if: always() && !cancelled()` aggregation,
  so a failed or timed-out `architectural-heavy` run fails `router-gate`.
- **Bandit + pip-audit** — **searched for and not found anywhere in
  `.github/workflows/*.yml` in this checkout** (`grep -rln "bandit"
  .github/` and `grep -rln "pip-audit|pip_audit" .github/` both return no
  matches). This directly contradicts an assumption in the task brief that
  these run "always" — stated here as a verified finding rather than
  invented or silently assumed. If a security-scanning gate exists under a
  different name or a non-workflow mechanism (e.g., a scheduled job outside
  `.github/workflows/`, or a third-party GitHub App with no workflow file),
  it was not discovered by this search; this plan does not claim one exists
  where direct evidence shows none.
- **SonarCloud** — confirmed via direct read of `.github/workflows/sonar.yml`
  (`on: schedule` / `workflow_dispatch` only, explicit comment "no
  `pull_request` trigger, so it structurally cannot enter any PR ... gated
  to `schedule`/`workflow_dispatch` only") and `ci-quality.yml` (has a
  `pull_request` trigger but its jobs are `lint`/`build-wheel`/
  `clean-install-verification`/`uv-lock-check`/`quality-gate` — no Sonar
  step). **SonarCloud does not run on this PR.** No Sonar verdict is
  promised for this mission's PR.
- **Per-module test matrix** (`missions`, `core_misc`, `charter`, `unit`,
  `specify_cli_runtime`, above) — the real enforced correctness gate for
  this change; all five are fully green in the pre-fix baseline (Section
  10 — there is no remaining pre-existing red anywhere in this baseline,
  per Section 10's round-5 correction) and must stay green (plus the new
  red→green obligations, Section 8) post-fix.

## 12. Campsite-clean (Standing Order 2)

Re-reading the exact lines this fix is about to touch
(`mission_step_repository.py:68-73` around the `_YAML` singleton and its
misleading "thread-safe for reads" comment; `mission_type_repository.py:
316-318` around `_LAYERED_YAML`) for genuine, domain-matched pre-existing
debt on those specific lines: **none found worth folding as a distinct
campsite-clean commit.** The surrounding code (both singleton declarations,
both `_load_step_yaml`/`_load_layered_mission_type_file` call sites) is
otherwise well-documented and structurally sound; the "thread-safe for
reads" comment at `mission_step_repository.py:69` is not itself a
pre-existing *defect* to clean up separately — it is the exact
misconception this mission's own fix corrects in place, so rewriting it is
part of the functional change (Section 6), not a preceding, distinct,
behaviour-preserving campsite-clean step. Saying so explicitly rather than
inventing a busywork commit: **no campsite-clean commit is planned for this
mission.**

The three dormant, out-of-scope `YAML(typ="safe")` singletons named in
Section 1 (`lint.py:66`, `operating_procedures.py:41`, `extractor.py:51`)
are a *different* surface from the lines this mission touches, so they are
not folded in here either — named for the record as debt this mission
observed but consciously left unfrozen (no current threaded/memoized
caller makes them live), not silently missed.

## 13. Tracer files

`kitty-specs/concurrent-template-config-race-4589-01M35M6B/traces/{approach,design-decisions,tooling-friction}.md`
were seeded during the spec phase (2026-09-22 entries already present,
covering the Option-A decision, the corrected `src/doctrine/` → 
`src/charter/offering/` path citations, and the mission-slug/ULID-suffix
tooling note). This plan **references, does not re-seed** them.
Implementation will **append** new entries as it proceeds (e.g., what the
forced-interleave monkeypatch construction actually looked like once built,
any friction hitting the exact Barrier-pinned window, and the final
red-commit/green-commit SHAs) — never replace or renumber the existing
entries.

## 14. Commit phasing

**Round-4 update**: test names below match the round-4 obligation table
(Section 8b) — OBL-1 through OBL-5, not the round-3 `8b`/`8c`/`8e`/`8f`
letters. One PR to `main` (the sk overlay default), in this order:

1. ~~Campsite-clean commit~~ — **skipped** per Section 12 (no genuine debt
   found on the touched lines).
2. **Red-first failing test commit** (CL-004): OBL-1 (the distinct-key,
   forced-interleave 6a-proof, both `PRIMARY_SITE` and `SECOND_SITE`
   cases), OBL-2 (the same-key, redundant-population-count 6b-proof, both
   cases), and OBL-3 (the amended-SC-006 raise-not-degrade regression
   guard, both cases), committed against pre-fix code. OBL-1 is verified
   RED for both cases through the real forced interleave — this is the
   load-bearing red, the one that demonstrates the production race. OBL-2
   is verified RED only in the trivial "the seam this test patches does
   not exist yet" sense (Section 8b's own note) — it is not itself a
   race-detection test, and its red-first status at this commit is real
   but not evidence of the corruption mechanism. **OBL-3 is already GREEN
   at this commit, not red** (Section 8b/8c): the amended SC-006's
   propagate/no-partial-cache/successful-retry property holds by
   construction before 6a/6b land, so OBL-3 is committed alongside the red
   obligations for review-diff cohesion, not because it is red-first — it
   is a falsifiable regression guard (CL-008), not evidence of the
   corruption mechanism.
3. **Production-fix commit(s)**: the thread-local YAML accessor (Section
   6a) + single-flight per-key lock (Section 6b) at both sites, plus the
   new `MissionCacheLockError` exception class (Section 6c), verified the
   same tests now GREEN for both cases, plus OBL-5 (the
   `cache_clear()`-mid-population test, both cases), OBL-4 (the existing
   `test_concurrent_creates_no_collision`), `tests/charter/test_charter_import_time_io.py`
   (PLAN-FRESH5-001: confirms the second site's forwarded
   `.cache_clear`/`.cache_info`/`.cache_parameters` seam, Section 6b, stays
   green under its live `.cache_info()` call), and all five selected
   modules' full suites (Section 10/11) still green.
4. **Doc/tracer updates**: tracer-file appends (Section 13) and any
   research/plan corrections discovered during implementation.

This mission ships as **one PR to `main`**. The diff stays reviewable in one
sitting: two singleton replacements + two single-flight-lock-guarded cache
call sites + one new exception class + five test obligations (Section 8b),
each covering both fix sites by construction, all confined to three files
in one package plus one test file. If implementation later discovers the
second fix site needs materially different handling than mirrored here, or
that `resolver.py` needs a change after all (Section 11's `next`-gate
caveat), that is a signal to flag for a possible split — not a silent scope
expansion.

## 15. Human-in-Charge approval

**None needed.** No production secrets, no production Upsun deployment, no
live Stripe integration are touched by this change, and this repository (the
spec-kitty CLI/doctrine tooling itself) does not carry any of those surfaces
in the first place — stated here for completeness per the pipeline's own
requirement, not because any such surface exists to approve.
