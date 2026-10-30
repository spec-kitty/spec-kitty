# Phase 0 Research — chain gate classifier (#6732)

**Mission**: `chain-gate-subscript-name-pairing-01M66YGY`
**Base**: `main@512567ee` (canonical remote `origin` = `https://github.com/spec-kitty/spec-kitty`)

## Decision 1 — The issue still reproduces on current `main`

Reproduced through the gate's own scanner (`_scan_source`), not a reimplementation:

```text
$ uv run python -c "import sys; sys.path.insert(0,'tests/architectural'); \
  import test_org_pack_chain_single_authority as m; print(m._scan_source(src,'p.py'))"

false-negative subscript     -> []                       # roots-only chain assembled by hand, gate silent
false-positive name dictcomp -> [Hit('p.py', 2, 'registry.packs comprehension assembling roots')]
```

Both behaviours are wrong against the rule the module docstring states ("Code that needs
pack NAMES ... legitimately reads the pack registry"). Evidence recorded before any edit.

**Alternatives considered for the repro**: importing the module's helpers (chosen — the
production entry point is `_scan_source`, and `census()` needs a file on disk); running the
whole gate (rejected — it is green today, so it cannot show either defect); a new test
helper (rejected — a helper that only the new tests call would be helper-only
non-vacuity).

## Decision 2 — Not superseded

- `git log -S"enumerate" -- tests/architectural/test_org_pack_chain_single_authority.py`
  and `-S"DictComp"` return only the two missions that created the gate (#6006, #6012).
  No commit after them touched the loop or comprehension classifier.
- The issue's parent #6418 landed as PR #6756 (merged); it worked around the false
  positive with a `for` loop rather than fixing the classifier, and `src/charter/activation/drg_activation.py`
  keeps that workaround note at line 196.
- No `[Unreleased]` changelog entry mentions this gate's classifier.
- Issue state: OPEN, no assignees, no comments, no labels before this mission claimed it.

## Decision 3 — The real tree already exercises the name-keyed subscript idiom

`src/charter/activation/drg_activation.py::_org_pack_roots_by_name` (in scope, not the
owner, not the offering tier) contains:

```python
for pack in load_pack_registry(repo_root).packs:
    roots[pack.name] = pack.effective_root(repo_root)
```

So the two halves of the fix are not symmetric in risk:

- Treating *any* subscript assignment as a collector **without** judging the key would make
  the live census red on this file. The key-based pairing test is therefore load-bearing on
  real code, not only on a planted fixture.
- Exempting a name-keyed `DictComp` cannot weaken the live census, because the live tree has
  no such comprehension; the planted fixtures are the only guard there, so a wrong-direction
  fixture pair is required.

This is recorded because it changes the review question: the subscript rule has a
production-path positive control, the dict-comprehension rule needs a same-fixture negative.

## Decision 4 — Where the boundary sits for each idiom

The gate's Rule 2 is "roots-only collection is a violation; anything name-paired is not".
Applying it per idiom:

| Idiom | Pairing evidence | Verdict |
| --- | --- | --- |
| `for p in packs: roots.append(p.effective_root(r))` | none | violation (existing) |
| `for p in packs: n.append(p.name); roots.append(p.effective_root(r))` | collected name | non-violation (existing) |
| `for i, p in enumerate(packs): roots[i] = p.effective_root(r)` | subscript key `i` — not a name | **violation (new)** |
| `for p in packs: roots[p.name] = p.effective_root(r)` | subscript key `p.name` | **non-violation (new)** |
| `[p.effective_root(r) for p in packs]` | none | violation (existing) |
| `{p.name: p.effective_root(r) for p in packs}` | key carries the name | **non-violation (new)** |
| `{p.effective_root(r): p.name for p in packs}` | name only in the value; the key *is* the root | **violation (new)** |

The last row is the deliberate asymmetry: a `DictComp` whose key is the bare root is a
roots-only mapping regardless of what its value carries, so the exemption keys on the
`DictComp` key, not on "the comprehension mentions `*.name` somewhere".

For loops the asymmetry is narrower: pairing stays **loop-wide over the loop's collections**
(the `append`/`add`/`extend` arguments, as the existing `paired-loop` fixture pins) and the
subscript key joins that evidence set; it is never judged over the whole loop body, so a
loop that merely mentions a name elsewhere is still a violation.

## Decision 5 — `enumerate(...)` unwrapping is part of the same defect

The reported false-negative loop is `for i, p in enumerate(reg.packs)`, so the loop's `iter`
is a `Call`, not the `packs` attribute. `_is_packs_iter` must unwrap a single-argument call
whose first argument is `<registry>.packs`. Without that, adding the subscript collector
alone would still miss the reported line. Both changes are asserted by one fixture
(FR-003), which is why the fix is proven half-by-half (SC-004): reverting the unwrap leaves
the fixture clean, reverting the subscript rule leaves it clean.

## Decision 6 — Non-vacuity plan (Standing Order #5)

- Floor: `test_census_scans_enough_files` (`_SCANNED_FILE_FLOOR = 1200`) stays.
- Self-mutation: each new rule gets a planted violation *and* a planted non-violation on the
  same idiom, so a mutation in either direction reds (widening the exemption reds the
  violation fixture; narrowing it reds the non-violation fixture).
- The existing owner-bypass control and the empty-allowlist assertion are unchanged.
- The pre-fix classifier is the mutation proof: the new violation fixtures must fail on
  `main@512567ee`, and the new non-violation fixtures must also fail there (the dict
  comprehension one does, per Decision 1; the name-keyed subscript one passes today and
  would fail if the fix were over-widened — it is the guard on FR-002, not a red-first test).

## Decision 7 — Scope and blast radius

Only `tests/architectural/test_org_pack_chain_single_authority.py` changes in the product.
`src/` is untouched, so the only other change is the changelog entry. The gate is
registered in CI through the architectural shard (`tests/architectural/**`), not through a
per-file allowlist; no CI config change is needed.
