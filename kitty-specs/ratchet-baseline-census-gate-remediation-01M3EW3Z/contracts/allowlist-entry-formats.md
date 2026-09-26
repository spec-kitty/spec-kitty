# Contract: content-identity allowlist entry formats

**Mission**: ratchet-baseline-census-gate-remediation-01M3EW3Z · **Status**: landed (WP01–WP04, WP13)
**Audience**: maintainers and agents adding an exemption to a `tests/architectural/` gate.

This mission has no external API. Its one interface contract is internal: the shapes an
architectural gate accepts as an allowlist or exemption entry. Every shape identifies a source
construct by **content**; a line number is never identity (FR-001..FR-007, SC-001).

## 1. Descriptor line (hand-curated allowlists, `_exemptions/*.txt`)

```
<repo-relative path>::<qualname>::<token_substring>[::<occurrence>]
```

- Rendered and parsed only by `tests/architectural/_content_identity.py`
  (`render_descriptor_line` / `parse_descriptor_line`); matched only by `resolve_allowlist` +
  `partition_findings` (single matching authority, plan D-OP-9).
- `occurrence` is optional and 0-based; it disambiguates identical `(qualname, token)` sites in one file.
- One entry suppresses **at most one** live finding (multiset semantics).
- **Stale entry = gate failure** (plan D-OP-8).
- A `path:line` row is rejected at load with a `ValueError` naming the file.

Used by: join allowlist, kernel/doctrine import exemptions, os-detect / lock-ban / clock `CALL:` exemption files.

## 2. `CensusKey` literal (census allowlists)

```python
CensusKey(rel="...", qualname="...", token_line="...", op="...", op_ordinal=0): "rationale"
```

- Defined in `tests/architectural/_destructive_op_census.py`; `(qualname, token_line)` comes from
  `_ratchet_keys.composite_key` (C-004, one identity mechanism).
- `op_ordinal` is the 0-based ordinal among live hits sharing `(rel, qualname, token_line, op)`, in
  source order. A second identical op in an exempted function becomes unexpected and fails the gate.
- **Stale entry = warning only** (documented census contract, plan D-OP-8).
- Failure output renders `rel::qualname::op#ordinal (line N) tokens=...`; the line is a diagnostic
  locator only and must never be pasted into an allowlist.

Used by: destructive-op (22), mutation (56), overwrite (2) census gates. Equivalence with the
pre-mission line keys is proven by `research/census_rekey_equivalence.py` over `census-rekey-map.csv`.

## 3. Positional-anchor ban (enforcement of this contract)

`tests/architectural/test_ratchet_positional_anchor_ban.py` rejects any line-pinned entry shape
(`(path, int)` tuples incl. `Path(...)`, `path:line[:suffix]` keys, line-keyword records,
`path:line` text lines) anywhere under `tests/architectural/`. Its exemption set is pinned to
`frozenset()` (FR-003, WP13).
