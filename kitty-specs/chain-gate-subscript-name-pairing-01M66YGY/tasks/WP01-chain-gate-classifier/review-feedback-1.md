# WP01 review feedback — round 1 (reviewer-renata)

Verdict: **reject, one blocking finding.** The classifier change is correct and the
red-first evidence holds; the gap is a test-coverage hole inside the new branch.

## F1 (blocking) — the `DictComp` value check is never exercised

`_comprehension_collects_bare_roots` now ends with

```python
return _is_bare_root(node.key) or _is_bare_root(node.value)
```

The only fixtures that reach this line are:

- `name-keyed-dict-comprehension` → returns earlier via `_carries_name(node.key)`;
- `root-keyed-dict-comprehension` → short-circuits on `_is_bare_root(node.key)`, so
  `_is_bare_root(node.value)` is never evaluated.

That leaves the "key is neither a name nor a root, but the value is a bare root" case
unpinned — exactly the case that tells the exemption apart from a blanket
"mentions a name anywhere" exemption. A future edit that drops the `or
_is_bare_root(node.value)` half would leave every fixture green and re-open the
false negative for `{i: p.effective_root(r) for i, p in enumerate(packs)}`.

**Required:** plant the index-keyed violation fixture
`{i: p.effective_root(r) for i, p in enumerate(load_pack_registry(r).packs)}` in
`test_planted_violation_is_reported` with the `registry.packs comprehension assembling
roots` kind. Keep it on the same idiom as the two dict-comprehension fixtures so the
three-way split (name key → clean, root key → red, other key + root value → red) is
readable as one block.

## Checked and fine (no action)

- `enumerate(...)` unwrapping matches the issue's reported line; `enumerate(packs, 1)`
  and `sorted(packs)` are also seen through (verified in-session).
- Pairing is still judged over collected values, so the existing `paired-loop` and
  `pair-comprehension` non-violations keep their meaning; the new evidence is only the
  subscript key.
- Over-widening the subscript rule to "any subscript assignment is a collector" reds the
  live census at `src/charter/activation/drg_activation.py:198`, which is the production
  positive control for FR-002. Confirmed.
- Live census over `src/` is empty as shipped; allowlist stays empty; floor and
  owner-bypass control unchanged.
- Changelog entry is 842 characters, impact-first, with before/after.
- Docstring matches the implemented rule.
- `ruff check`, `ruff format --check`, `mypy`, `check_docs_freshness --ci` (errors=0) clean.
