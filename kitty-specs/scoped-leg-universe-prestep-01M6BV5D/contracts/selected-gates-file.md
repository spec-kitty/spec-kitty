# Contract: the selected-gates file

One file, one format, two readers. Mission
`scoped-leg-universe-prestep-01M6BV5D` (issue #7001) adds the second reader; the
format itself is #6994's.

## Format

```
tests/architectural/test_dead_builtin_doc_paths.py
tests/architectural/test_no_stale_charter_path_literals.py
```

- One repository-relative path per line, as `scripts.ci.battery_scope select` writes it
  (`f"{gate}\n" for gate in sorted(gates)`).
- Blank lines and surrounding whitespace are ignored; a repeated path is one gate.
- The path set is unordered. An *empty* file is an empty selection, never "no
  restriction".
- "No restriction" is expressed by naming no file at all (the workflow writes
  `gates_file=` for a whole-leg run), not by an empty file.

## Writer

`python -m scripts.ci.battery_scope select --base <sha> --head <sha> --battery-part
<part> --out <path>` — prints the `$GITHUB_OUTPUT` lines and writes the file.
`scripts.ci.battery_scope.write_selected_gates` is the one writer function; the CI
`scope` step has already run before anything reads the file.

## Readers

| Reader | How it names the file | Unset / empty | Named file missing | Empty file |
| --- | --- | --- | --- | --- |
| `battery_partition_plugin.read_gates_file` (restricts the running leg) | `$SK_BATTERY_GATES_FILE` | whole part | `pytest.UsageError` (fails closed) | part files ∩ ∅ → the plug-in refuses a leg with nothing to run |
| `collect_universe_prestep consumers` (decides the pre-step) | `--gates-file <path>`, default `$SK_BATTERY_GATES_FILE` | whole part (today's answer) | exit 1, no answer on stdout | `false` — no selected gate of this leg consumes the universe |

Both readers parse through `scripts.ci.battery_scope.read_selected_gates`, so a change
to the format lands in one function. A round-trip test writes a file through the writer
and asserts both readers resolve the same set, blank lines and duplicates included.

## Why the decision may narrow but the collection may not

The file describes *which gates a leg runs*. The universe describes *the whole test
tree*, and the gates that consume it compare across the whole suite
(`test_fast_tier_marker_completeness.py`, `test_same_tier_uniqueness.py`). So the file
is a valid input to "does this leg need the universe?" and an invalid input to "which
tests should the universe contain?".

## Precedence

When both are present, `--gates-file` wins over `$SK_BATTERY_GATES_FILE`; the variable is only
the default for an omitted option. The plug-in has no option, so it always uses the variable.
CI passes the option explicitly and never exports the variable into the `select` step.
