# Data Model: CI down-route of prose-only .py diffs

This mission is behavioral CI wiring, not persistent data. The "entities" are the
in-memory values that flow through classification and routing.

## Entity: FileVerdict

The classification of one changed `.py` file.

| Field | Type | Meaning |
|-------|------|---------|
| `path` | str | repo-relative path of the changed `.py` |
| `is_prose_only` | bool | true only on *proof* of comment/docstring-only change |
| `reason` | str (enum-ish) | why not prose-only, for logging: `code_diff`, `type_comment`, `noqa_pragma`, `doctest`, `parse_error`, `no_base`, `unknown` |

**Invariants**:
- `is_prose_only == True` ⟹ base and head parse cleanly, their docstring-stripped
  `ast.dump(include_attributes=False)` are equal, their `# type:`/`# noqa`/`# pragma`
  token sets are equal, and no changed docstring contains a `>>>` doctest prompt.
- Any exception or unknown condition ⟹ `is_prose_only == False` (fail-closed).

## Entity: PRProseVerdict (aggregate)

The all-or-nothing decision for the whole PR.

| Field | Type | Meaning |
|-------|------|---------|
| `prose_only` | bool | true only when every changed file is a proven prose-only `.py` OR an existing doc/corpus path |
| `changed_paths` | list[str] | the raw changed-path set |
| `reduced_paths` | list[str] | `changed_paths` minus proven prose-only `.py` (fed to `select_modules`) |

**Invariants** (corrected per research R2):
- Safety is **structural in the wiring**, not a classifier implication: every
  down-routable `if:` keeps its existing gate ANDed with `prose_only != 'true'`, so
  `prose_only` can only *subtract* an already-selected code lane and can never defeat
  the FR-004 `unmatched` catch-all. `prose_only == True` is NOT assumed to imply "no
  unmapped src present" (the original R2 claim, retracted).
- `prose_only == True` ⟹ `reduced_paths` contains no `src/**.py` or `tests/**.py`
  that carries real code (the classifier proved each dropped `.py` prose-only).
- The verdict is monotonic-safe: it can only *remove* the module matrix / arch
  battery / code shards and *add* the docs lane; it never removes an always-on lane.

## Value transitions (control flow)

```
raw changed paths
   │
   ├─ ci-modules.yml: reduced_paths = drop(proven prose-only .py) → select_modules → module matrix (skipped when empty)
   │
   └─ ci-router.yml `changes` job: prose_only = aggregate verdict (git blobs base..head)
          ├─ architectural-heavy.if   &&= prose_only != true       (skip battery when prose-only)
          ├─ tests-<code>.if          &&= prose_only != true       (skip code shards when prose-only)
          └─ tests-docs.if            ||= prose_only == true        (positive docs/help-drift enablement)
```

## Lane sets (the observable contract, pinned by the golden test)

| PR shape | module matrix | arch battery | code shards | tests-docs | always-on (ruff/terminology/…) |
|----------|:---:|:---:|:---:|:---:|:---:|
| proven prose-only `.py` (only) | ✗ | ✗ | ✗ | ✓ | ✓ |
| any real code / mixed / unprovable | ✓ (today) | ✓ (today) | ✓ (today) | as today | ✓ |
