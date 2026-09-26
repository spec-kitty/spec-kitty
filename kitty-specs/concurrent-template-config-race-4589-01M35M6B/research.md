# Research: Concurrent `create_mission_core` TemplateConfigurationError race

**Mission**: `concurrent-template-config-race-4589-01M35M6B`
**Scope**: CL-002 — resolve, on the merits, whether the YAML-singleton +
`functools.cache` cache-miss race hypothesis is a real, reachable mechanism.
Every claim below is cited to a specific file:line on this checkout
(`<checkout>`) or to the installed `.venv`
package source, verified by direct read in this research pass (2026-09-23).

## Bottom line

**Both halves of the hypothesis are independently confirmed by direct source
reading, and neither is sufficient alone — they are jointly necessary.**

1. `ruamel.yaml`'s `YAML(typ="safe")` instance genuinely shares and mutates
   load-time parser state across calls to `.load()`, and this project's
   installed dependency graph uses the exact code path where that sharing is
   exploitable (the pure-Python parser; the C accelerator is not installed).
   The module-level singleton's inline comment ("thread-safe for reads") is
   **false** as a general claim about `.load()`.
2. `functools.cache` (== `functools.lru_cache(maxsize=None)`) has **no
   locking at all** in its unbounded form — not even around the cache dict —
   so on a cache miss, two threads calling the wrapped function with the
   same or different keys execute the function body fully concurrently.
   This is what *creates the opportunity* for two `.load()` calls to
   interleave on the shared YAML instance; by itself, without a shared
   mutable object in the call path, concurrent cache-miss execution would be
   harmless (redundant work, not corruption).
3. Combining (1) and (2): two concurrent cache-miss executions of
   `_resolve_all_for_mission_type_cached` (or, separately, of
   `resolve_layered_mission_types` — see the second, previously
   uncatalogued instance below) can each call into a **shared** `YAML`
   object's `.load()` at overlapping times. One call's `self.reader.stream`
   assignment can be silently overwritten by the other's before the first
   call has finished consuming it, corrupting or exception-ing that parse.
   `_load_step_yaml`'s blanket `except Exception: return None`
   (`mission_step_repository.py:134`) turns that corruption into a silently
   dropped step — which, if the dropped step carries the `template` ref for
   `artifact_kind="spec"`, produces exactly the observed
   `TemplateConfigurationError(reason="is missing the requested mapping
   key")`.

**What remains open** (carried into `plan.md` as risk, per CL-002's
"resolve or carry forward" instruction): this pass is a *static* analysis. I
did not, in this research step, run a monkeypatch+`Barrier`-forced trial that
witnesses the corruption live — that is exactly the job of the red-first
regression test this mission's implementation phase must build (CL-003/
FR-004), because a natural-timing reproduction is not an acceptance bar here.
The static evidence below is strong enough that I do not consider the
causal mechanism "unproven" in the way CL-002 frames it; but "mechanistically
sound" and "empirically witnessed under construction" are different claims,
and only the second is what the regression test will establish.

---

## Question (a): Does the shared `YAML(typ="safe")` instance mutate
load-time state across threads?

### Where the state lives

`.venv/lib/python3.11/site-packages/ruamel/yaml/main.py`, class `YAML`
(defined at line 56):

- `__init__` (57–201) sets many plain instance attributes
  (`self.typ`, `self.doc_infos = []` at line 186, etc.) and does **not**
  pre-build a reader/scanner/parser/composer/constructor; those are built
  lazily.
- The lazy builders are `@property` getters using a `hasattr`/`setattr`
  memoization idiom — build once, cache on `self`, reuse forever:
  - `reader` property, lines 203–209: `self._reader = self.Reader(None,
    loader=self)` on first access, then returns the **same** `self._reader`
    on every subsequent access.
  - `scanner` property, 211–219: same pattern, `self._scanner`.
  - `parser` property, 221–240: same pattern, `self._parser` (for the
    non-C-accelerated case).
  - `composer` property, 242–247: same pattern, `self._composer`.
  - `constructor` property, ~249 onward: same pattern, `self._constructor`.

  So a single `YAML` instance builds **one** reader, **one** scanner, **one**
  parser, **one** composer, **one** constructor object for its entire
  process lifetime, and every `.load()` call reuses those same objects.

### What `.load()` does with that shared state

`main.py:438–461` (`def load`):
```
438  def load(self, stream: Union[Path, StreamTextType]) -> Any:
...
450      self.doc_infos.append(DocInfo(requested_version=version(self.version)))
451      self.tags = {}
452      constructor, parser = self.get_constructor_parser(stream)
453      try:
454          return constructor.get_single_data()
455      finally:
456          parser.dispose()
457          for comp in ('reader', 'scanner'):
458              try:
459                  getattr(getattr(self, '_' + comp), f'reset_{comp}')()
460              except AttributeError:
461                  pass
```
- Line 450: appends to the **shared** `self.doc_infos` list on every call.
- Line 451: **resets** the shared instance attribute `self.tags` at the
  start of every call — a second thread's concurrent `.load()` can reset
  this out from under an in-flight call.
- Line 452: `get_constructor_parser(stream)` — see below; this is where the
  actual per-call stream gets wired into (or bypasses) the shared objects.
- Lines 457–461: at the *end* of the call, it reaches into the cached
  `self._reader`/`self._scanner` and calls their `reset_reader`/
  `reset_scanner` methods — i.e., the teardown path *also* mutates the same
  shared objects a concurrent in-flight call is still using.

`main.py:489–542` (`def get_constructor_parser`) is the decisive method —
it branches on whether the C parser (`CParser`) is available:

```
498  if self.Parser is not CParser:
499      if self.Reader is None:
500          self.Reader = ruamel.yaml.reader.Reader
501      if self.Scanner is None:
502          self.Scanner = ruamel.yaml.scanner.Scanner
503      self.reader.stream = stream          # <-- mutates the SHARED cached reader
    else:
        ...similar branches at 505-514, all assigning `self.reader.stream = stream`
        on the shared, cached `self.reader` property object...
    else:  # combined C-level reader/scanner/parser (line 515-541)
        ...
        loader = XLoader(stream)             # <-- a FRESH object, per call
        self._stream = stream
        self._scanner = loader
        return loader, loader
542  return self.constructor, self.parser    # <-- the SHARED cached objects
```

**This is the crux, and it is environment-dependent**: if the C accelerator
(`CParser`, from the `ruamel.yaml.clib` extension module) is installed, each
`.load()` call builds a brand-new `XLoader` object (line 539) and the
`load()` method's local `constructor`/`parser` variables reference that
fresh, per-call object directly — not the cached `self.reader`/`self.parser`
property state at all. In that configuration the specific race described
here would not manifest through this exact route (though `self.tags` and
`self.doc_infos` are still shared and reset per-call, which is not race-free
either — just not the smoking-gun route below).

If the C accelerator is **not** installed (`CParser is None`), the code
takes the `if self.Parser is not CParser:` branch and does
`self.reader.stream = stream` at line 503 — an in-place mutation of the
**one shared, cross-call, cross-thread `self._reader` object's `.stream`
attribute** — then returns `self.constructor, self.parser`, i.e. the **same
shared, cached constructor and parser objects**, at line 542. Those shared
objects then drive `constructor.get_single_data()` back in `load()` (line
454), reading token-by-token from `self.reader.stream` throughout the
*entire* parse (not just once at the start).

### Confirmed: this checkout uses the vulnerable (pure-Python) path

```
$ .venv/bin/python3 -c "from ruamel.yaml.main import CParser; print(CParser)"
None
```

`pyproject.toml:66` pins `"ruamel.yaml>=0.18.0"` with no `[clib]` extra, and
`uv.lock` (lines 2251–2256, 2413, 2501) resolves only the plain
`ruamel-yaml` wheel — no `ruamel.yaml.clib` C-extension package appears
anywhere in the lock file's dependency graph. So `CParser is None` is not an
accident of my local environment; it is what this project's declared
dependency set always resolves to, in CI and for every consumer. **The
vulnerable, shared-mutable-state code path (`self.reader.stream = stream`
on a cross-call cached reader) is the path this project actually executes,
unconditionally.**

### Consequence for a concurrent interleave

If thread A calls `.load()` on the shared `_YAML` instance and sets
`self.reader.stream = content_A`, and before A's scanner/parser/composer/
constructor chain finishes consuming `content_A`, thread B's concurrent
`.load()` call reassigns `self.reader.stream = content_B`, then A's
still-in-flight read calls (which read repeatedly from `self.reader.stream`
throughout the whole document, not just once) start reading `content_B`'s
bytes into what is nominally A's parse. Depending on exactly where in the
scan the swap lands, this produces one of:

- a `ruamel.yaml.error.YAMLError` subtype (malformed token stream) —
  caught by `_load_step_yaml`'s `except Exception: return None`
  (`mission_step_repository.py:134`), silently dropping that step;
- a syntactically valid but **semantically wrong** dict (e.g., a partial
  merge of two files' content) — which either fails the `isinstance(raw,
  dict)` check (also swallowed, same outcome) or, more insidiously, *passes*
  as a dict but is missing the `template:` key the real file had, which
  `MissionStep.model_validate` may accept (the field is optional) —
  producing a `MissionStep` **silently missing its template ref**, which
  `iter_template_refs`/`project_template_set` (`step_projection.py:142–162`,
  `105–126`) then simply excludes from the projected `template_set`
  mapping, again with no exception raised anywhere.

Either way, the drop is **silent** at the point it happens — it only
surfaces later, at `resolve_configured_template`
(`src/specify_cli/runtime/resolver.py:497–503`), as
`TemplateConfigurationError(reason="is missing the requested mapping key")`
— the exact symptom from the CI failure cited in `spec.md`.

**Verdict on question (a): YES**, confirmed by direct source read plus a
confirmed dependency-resolution check on this checkout. The inline comment
at `mission_step_repository.py:69` ("module-level singleton — thread-safe
for reads") is incorrect: `.load()` is not a read-only operation on the
`YAML` instance: it mutates `self.tags`, `self.doc_infos`, and (in the
pure-Python path this project actually uses) `self.reader.stream`, on every
call, with zero synchronization.

---

## Question (b): Is `functools.cache`'s cache-miss concurrency gap
sufficient by itself, or does it require the YAML-sharing mechanism too?

### What `functools.cache` actually does under the hood

`functools.cache` is `functools.lru_cache(maxsize=None)`
(`functools.py:651` in the installed CPython 3.11.15 stdlib delegates to
`lru_cache`). Reading `_lru_cache_wrapper`
(`<uv-python-3.11>/lib/python3.11/functools.py:525`),
the **unbounded** case (`maxsize is None`, which is exactly our case) takes
a distinct, simpler branch with **no lock at all**:

```python
549  elif maxsize is None:
550      def wrapper(*args, **kwds):
551          nonlocal hits, misses
552          key = make_key(args, kwds, typed)
553          result = cache_get(key, sentinel)     # <-- plain dict.get(), no lock
554          if result is not sentinel:
555              hits += 1
556              return result
557          misses += 1
558          result = user_function(*args, **kwds)  # <-- unlocked call
559          cache[key] = result                    # <-- plain dict write, no lock
560          return result
```
(The bounded case, `else:` at line 564, *does* take an `RLock()` — but only
around the dict/linked-list bookkeeping, lines 570 and 585, never around
`user_function(*args, **kwds)` itself at line 584.)

So in **neither** case does `functools.cache`/`lru_cache` ever serialize
*execution of the wrapped function body*. For our unbounded case there is
not even a lock around the cache dict — CPython's GIL keeps the dict itself
from becoming internally corrupted, but nothing prevents two threads from
both observing a cache miss for the same key and both running
`user_function` to completion concurrently, with the second one's
`cache[key] = result` simply overwriting the first's.

### Is this sufficient by itself?

**No — and this checkout confirms why not.** `_resolve_all_for_mission_type_cached`
(`mission_step_repository.py:446–470`) constructs a **brand-new**
`MissionStepRepository(builtin_root)` instance on every call (line
468–470) — the repository object itself carries no cross-call mutable
state, and `resolve_all_for_mission_type`'s uncached body
(`_resolve_all_for_mission_type_uncached`, lines 335–365) only touches
`self._builtin_root` (read-only), local sets/dicts, and the filesystem. If
two threads race a cache miss for the *same* key here and the only shared
object were this repository's own machinery, both calls would independently
walk the filesystem and independently build two (presumably identical, both
correct) `dict[str, MissionStep]` results — wasteful, but not corrupting.
**The one piece of state that *is* shared across every call, every thread,
every key, for the lifetime of the process, is the module-level `_YAML`
singleton** (`mission_step_repository.py:72`), reached via
`resolve()` → `_resolve_builtin_layer`/`_resolve_org_layer`/
`_resolve_project_layer` → `_load_step_yaml()` → `_YAML.load(...)`
(`mission_step_repository.py:98–160`, the `_YAML.load` call at line 133).

So: `functools.cache`'s lock-free cache-miss path is the *opportunity*
(it is what allows two threads to be inside `_resolve_all_for_mission_type_uncached`
— and therefore inside `_load_step_yaml` — at the same instant); the shared,
non-reentrant `_YAML` instance is the *mechanism* that turns that
opportunity into actual data corruption. Remove either ingredient and the
defect closes: a locked cache-miss body would serialize the two calls (no
overlap, no race); a thread-local or per-call `YAML` instance would give
each concurrent call its own private reader/scanner/parser/composer/tags
state (no shared mutation, no lock needed at all). **Both halves of CL-002's
question are real; neither is sufficient alone; they are jointly necessary
and jointly sufficient.**

### Cache-poisoning consequence (a corollary worth flagging for the fix design)

Because the corrupted/incomplete result is what gets written into
`cache[key] = result` (`functools.py:561` for the unbounded path used here),
a single lost race does not just affect the two concurrent callers — it
**poisons the cache for the rest of the process**, since every later call
with the same key (e.g., a later, single-threaded mission creation of the
same mission type, later in the same test session or CLI process) returns
the same wrong, cached `dict[str, MissionStep]` with no further chance to
self-correct. This raises the stakes of the fix beyond "fix the race, worst
case is one flaky failure" — an unlucky race can make *every subsequent*
`create_mission_core` call in that process fail the same way, which is
consistent with `spec.md`'s framing of this as corroding trust in
"main is green" rather than a one-off blip.

---

## A second, previously uncatalogued instance of the identical defect shape

`spec.md`'s Readiness Findings section names only the step-level singleton
`_YAML` (`mission_step_repository.py:72`). Tracing the actual
`create_mission_core` call chain in this research pass surfaced a **second,
independent instance of the exact same defect shape**, in the sibling file:

- `src/charter/offering/missions/mission_type_repository.py:318`:
  `_LAYERED_YAML = YAML(typ="safe")` — a second module-level singleton,
  used by `_load_layered_mission_type_file` (line 389:
  `_LAYERED_YAML.load(yaml_file.read_text(...))`).
- `_load_layered_mission_type_file` is called from `scan_mission_types_dir`
  (line 408), which is called from `resolve_layered_mission_types`
  (line 477), which is **also `@functools.cache`-decorated** (line 477,
  unbounded — same unlocked cache-miss behavior as above).
- `resolve_layered_mission_types` is called from
  `src/charter/activation/mission_type_profiles.py`'s `_resolve_action_slot`
  (confirmed by direct grep + read: `_resolve_action_slot` at line 893
  imports `resolve_layered_mission_types` at line 948 and calls it at line
  953).
- `_resolve_action_slot` is called **eagerly** (not lazily/thunked) from
  `resolve_mission_type_context` at
  `src/charter/activation/mission_type_profiles.py:662–667`, to compute
  `action_sequence` — which runs on **every** `create_mission_core` call,
  unconditionally, on the same hot path the failing test exercises.

**This means the identical race — shared `YAML` singleton feeding a
`functools.cache`-wrapped cache-miss body — exists twice in this codebase,
in two sibling files, on two different (step-level vs. mission-type-roster
-level) caches, and both are reachable from `create_mission_core`'s hot
path.** A fix that only touches `mission_step_repository.py`'s `_YAML`
would leave `mission_type_repository.py`'s `_LAYERED_YAML` (and
`resolve_layered_mission_types`'s cache-miss body) with the identical
unfixed defect shape. `plan.md`'s fix-mechanism section addresses both.

(Note: `MissionTypeRepository._load`'s own YAML use, at
`mission_type_repository.py:160`, constructs a **fresh** `_yaml =
YAML(typ="safe")` **inside** the method body on every call — this one is
already safe by construction, since nothing is shared across calls. It is
not part of the defect; it is evidence, by contrast, of what "no sharing"
looks like in this same file, and a template for how the fix can shape the
other two call sites.)

---

## Ruled out / out of scope

- **`src/charter/activation/resolver.py`** (spec.md's "candidate blast
  radius" entry marked "confirmed present ... scope its involvement during
  plan-phase research, not assumed"): read in full around its
  `template_set` usage (`resolver.py:635, 889–908, 915–982`). Its
  `template_set` is the **charter-selection scalar** (e.g.
  `"software-dev-default"`, a string naming which template *set* a project
  activated), resolved from `.kittify/charter/charter.yaml` via
  `_resolve_template_set_selection`/`load_doctrine_catalog`/
  `DoctrineCatalog.template_sets` — an entirely different domain object
  from the per-mission-type `dict[artifact_key, template_file]` mapping this
  mission's defect concerns. `step_projection.py`'s own module docstring
  (lines 24–30) explicitly fences this off: *"the unrelated
  charter/project `charter.offering.template_set` scalar (`charter/resolver.py`
  ...) is a different domain object entirely. This module must never
  import from, or reference, that scalar surface."* Confirmed by reading
  `resolver.py` directly: it never imports or calls
  `MissionStepRepository`, `_YAML`, `project_template_set`, or anything in
  `mission_step_repository.py`/`step_projection.py`. **Verdict: NOT in
  scope.** This resolves spec.md's open scoping question definitively.
- **`src/kernel/**`**: not read in detail, but no caller in the traced chain
  (`create_mission_core` → `resolve_mission_type_context` →
  `_resolve_template_set_slot`/`_resolve_action_slot` →
  `MissionStepRepository`/`mission_type_repository`) touches `src/kernel/`
  at any point. Not in scope.

---

## Sources consulted (this pass)

- `.venv/lib/python3.11/site-packages/ruamel/yaml/main.py` (installed
  ruamel.yaml 0.19.1) — `YAML.__init__`, `.reader`/`.scanner`/`.parser`/
  `.composer`/`.constructor` properties, `.load()`, `.get_constructor_parser()`.
- `<uv-python-3.11>/lib/python3.11/functools.py`
  — `lru_cache`/`_lru_cache_wrapper`, both the unbounded and bounded
  branches.
- `pyproject.toml:66`, `uv.lock:2251-2256,2413,2501` — confirms no
  `ruamel.yaml.clib` C-accelerator dependency; confirmed live with
  `.venv/bin/python3 -c "from ruamel.yaml.main import CParser; print(CParser)"`
  → `None`.
- `src/charter/offering/missions/mission_step_repository.py` (full file,
  470 lines) — `_YAML` singleton (72), `_load_step_yaml` (98–160),
  `resolve`/`resolve_all_for_mission_type` (238–365),
  `_resolve_all_for_mission_type_cached` (446–470).
- `src/charter/offering/missions/mission_type_repository.py` (full file,
  601 lines) — `MissionTypeRepository._load`'s per-call fresh YAML (160),
  `_LAYERED_YAML` singleton (318), `_load_layered_mission_type_file` (351–405),
  `scan_mission_types_dir` (408–474), `resolve_layered_mission_types`
  (477–601).
- `src/charter/offering/missions/step_projection.py` (full file, 162
  lines) — `project_template_set`/`iter_template_refs` (105–162), the
  charter-scalar scope-fence docstring (24–30).
- `src/charter/activation/mission_type_profiles.py` (relevant sections:
  370–470, 640–960, 1120–1195) — `ResolvedMissionType.template_set`
  cached_property (452–456) and its `_template_set_thunk` wiring
  (679–681), `_resolve_template_set_slot` (1135–1191),
  `_resolve_action_slot` (893–960) and its eager call site in
  `resolve_mission_type_context` (662–667).
- `src/charter/activation/resolver.py` (relevant sections: 880–982) —
  `_resolve_template_set_selection`/`resolve_project_governance`, confirmed
  unrelated domain object.
- `src/specify_cli/runtime/resolver.py:440–531` — `resolve_configured_template`,
  the `TemplateConfigurationError` raise sites (confirms spec.md's citation).
- `src/specify_cli/core/mission_creation.py:934–966` — confirms
  `create_mission_core`'s real call chain into `resolve_mission_type_context`
  and `resolve_configured_template`.
- `tests/core/test_mission_creation_identity.py:120–159` — the existing
  `test_concurrent_creates_no_collision` test and its two-thread harness,
  the ATDD entry point per CL-004.
