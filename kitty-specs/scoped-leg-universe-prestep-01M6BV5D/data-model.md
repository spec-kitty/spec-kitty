# Data model — scoped leg universe pre-step

Three entities, all sets of repository-relative paths. No persistence beyond the
existing keyed store, which this mission does not change.

## Selected-gates file

The newline-separated list of the gate files one scoped heavy leg will run.

| Field | Type | Rules |
| --- | --- | --- |
| gate path | repository-relative posix string, one per line | must be a path the diff's scan scopes selected for this leg; blank lines ignored; a duplicate is the same gate |
| whole file | `frozenset[str]` after parsing | order carries no meaning; an empty file is an empty set, never "everything" |
| location | any absolute path the CI runner can read (`$RUNNER_TEMP/battery-scope-gates.txt` on CI) | the file lives outside the checkout, so it never makes the checkout dirty for the universe store |

Lifecycle: written by `scripts.ci.battery_scope.output_lines` (the `scope` step) →
named by `steps.scope.outputs.gates_file` → read by the battery plug-in for the
running leg and by the decision's `consumers` command. A whole-leg run writes no
list at all (`gates_file=` empty), which is "no restriction", not "no gates".

## Universe consumer set

`scripts.ci.collect_universe_prestep.universe_consumers()` — the test files under
`tests/architectural/` whose source calls `collect_universe()` (AST scan; the store's
own contract test is excluded because it fakes the collector). Today:

- `tests/architectural/test_fast_tier_marker_completeness.py`
- `tests/architectural/test_same_tier_uniqueness.py`

The set is derived from the tree, never hand-written; a new consumer joins it by
calling the collector.

## Leg

One `--battery-part` of the `architectural-heavy` job (`1/2` or `2/2`), whose files are
`battery_part_files(part)` — the partition computed from the committed registry and
timings. Its *effective* scope is:

```
effective(leg) = part_files(leg)                                  if no gates file
               = part_files(leg) ∩ read_selected_gates(file)       if a gates file is named
```

The decision is `effective(leg) ∩ universe_consumers() ≠ ∅`.

## Invariants

1. `effective(leg) ⊆ part_files(leg)` — the intersection can only narrow, never widen.
2. An unreadable gates file yields no answer (exit 1), never an empty set — emptiness
   is a legitimate answer only when the file was read and holds nothing of the leg.
3. The collected universe is unchanged: a leg that collects still collects the whole
   test tree, so the consuming gates keep comparing across the whole suite.
