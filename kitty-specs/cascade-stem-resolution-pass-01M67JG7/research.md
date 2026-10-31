# Research — where the `[cascade]` case's time actually goes (#6777)

All numbers from this clone, `origin/main` at `512567eee7`, host `llama-ramen`, 20
concurrent agent workloads (load average 18–22 during the runs). The host is shared, so
every conclusion below rests on more than one measurement plus a profiler, not on a
single wall clock.

## Protocol

1. Baseline the case as CI runs it: `uv run --frozen pytest
   tests/charter/activation/test_stored_spelling_6527.py::test_writer_stores_stems_only
   -q --timeout=0 --durations=0`.
2. Reproduce the writer outside pytest, with `ActiveCharterManager.activate` wrapped to
   count and time every call (`_project(tmp_path)` + `_cascade(root)`, the module's own
   fixture and writer).
3. Attribute cost with `cProfile` over the same scripted run.
4. Test each candidate cause by re-running (2) with a single change monkeypatched in, so
   the delta is attributable.

## Measurement 1 — baseline (pytest, `--timeout=0`)

```
70.90s call     test_writer_stores_stems_only[cascade]
26.60s setup    test_writer_stores_stems_only[activate-declared-id]   # one-off session venv build
 3.45s call     test_writer_stores_stems_only[activate-urn]
 ...
10 passed in 111.83s
```

The `[cascade]` case is 20–40× its siblings. The 26.6 s setup is a one-off session
fixture (test venv bootstrap), not the case.

## Measurement 2 — scripted writer, instrumented

```
total cascade writer: 80.30s over 114 activate() calls
sum of activate(): 58.01s   median 0.528s   slowest tactic:refactoring-strangler-fig 7.26s
```

So ~58 s is inside 114 per-target `ActiveCharterManager.activate()` calls. Kinds reached:
directive, paradigm, procedure, styleguide, tactic, toolguide — the DRG closure of
`directive:DIRECTIVE_001` under `--cascade all` is 114 artifacts. That closure is
*designed* behaviour, not an accident.

## Measurement 3 — cProfile attribution

```
CALL COUNTS: activate=114, list_available_detailed=126, IdentityIndex.build=6
303.3 s total (profiler overhead ~3.7×)

299.2 s  _activate_cascade_targets
213.9 s  ActiveCharterManager.activate            (114 calls)
165.1 s  list_available_detailed                  (126 calls)
164.5 s  _declared_id                             (9735 calls, one ruamel load per file)
 87.0 s  _CascadeIds.config_id -> resolve_config_id -> _read_id  (121 calls, 5309 id reads, 5028 of them artifact-file parses)
```

Two independent redundancies, both of them *repeated reads of the same immutable files*:

* **Per-target catalog scan** — every `activate()` rescans its kind's whole doctrine tree
  and parses ~77 files just to learn the available ids (`list_available_detailed`).
* **Per-target stem resolution** — every cascade target's DRG URN is mapped to a config
  stem with a *fresh* `ResolutionPass`, i.e. a fresh catalog walk and fresh parse of every
  artifact file (5309 parses for 121 lookups).

## Measurement 4 — attributing each cause

Scripted writer, same fixture, one monkeypatch at a time:

| Mode | Writer cost |
|---|---|
| baseline | 80.30 s |
| one shared `ResolutionPass` for the cascade's lookups | **49.78 s** |
| … plus a memo on the per-target catalog scan (upper bound, not proposed) | **13.41 s** |

The shared pass alone removes 30 s (38%) with **no behaviour change**: `ResolutionPass`
memoises layer scans and artifact id reads and returns the same ids. It is exactly the fix
#5526 applied to the three *render* loops — with the note "each doctrine artifact file is
parsed once per loop instead of once per URN". The activation loop was the one site #5526
did not reach, because `activate.py` creates its pass *after* the loop (`activate.py:525`)
where only the render path can see it.

## Why not "tier it and move on"

The repo's flakiness policy (docs/development/testing/testing-flakiness.md) is "tune budget
gates, fix correctness flakes at the root", and `pytest.ini` calls the 240 s value "a
runaway-hang backstop, not a per-test budget". The case does not assert a budget; it is
simply carrying avoidable work. Raising its budget (what #6776 did as an interim crutch)
would hide the redundancy rather than remove it — and would also hide a genuine product
regression: the same redundancy is an ~80 s `charter activate --cascade all`.

## Why not the rest (deferred)

The remaining 30 s is the per-target `list_available_detailed` scan (~36 s of the
baseline). Removing it needs a batch activation seam on `ActiveCharterManager` (compute
availability once per kind, then commit N ids), which changes a public per-artifact
contract and its per-target warning/deny semantics. That is a maintainer decision, so it
is filed as a follow-up issue and named in the PR's `## Deferred` section. The mission
instead removes the redundancy that has an existing, blessed seam and pins it so it cannot
come back.

## Baseline for the guards

`ResolutionPass` instances created per cascade run: **121** before the fix (one per URN
lookup), **1** after. Artifact files parsed for URN resolution: proportional to targets
before, bounded after. Both are counted, not timed, so the guards are deterministic on a
loaded host.
