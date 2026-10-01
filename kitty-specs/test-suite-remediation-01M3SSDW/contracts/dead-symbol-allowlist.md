# Contract: dead-symbol allowlist loader and gate (FR-009)

**Owners**:
- IC-09: the ATDD pins M1, M7, M8 and M11, in `tests/architectural/test_dead_symbol_allowlist_contract.py`;
- IC-10: the loader, the YAML, the gate rewrite, and M2–M6, M9, M10, M12 and M13 in the rebased `bite_*` battery of `tests/architectural/test_no_dead_symbols.py`;
- IC-12: the size cap.

**Schema**: [data-model.md §1](../data-model.md#1-testsarchitecturaldead_symbol_allowlistyaml).

**Decision record**: the new ADR in `docs/adr/4.x/` (IC-12). It partially supersedes D-1 of `relocation-hardened-dead-code-scanners-01KX958P`.

## 0. Non-goals

- Changing the caller detectors (the `from`-import, module-attribute, `getattr`-string, facade and dynamic-accessor edges).
- Changing the #470 widened scope or its stale semantics.
- Removing auto-exempt condition (1), `final_key.module_path is None`.
- Renaming `tests/architectural/test_no_dead_symbols.py`. It stays in the C-007 enforcement canon, pinned by `test_shape_guard_membership.py`, `shape_guard_membership.yaml` and `_p1_census_oracle.py`.
- Adding a census gate (C-008).

## 1. Loader contract: `tests/architectural/_dead_symbol_allowlist.py`

`load_allowlist(path: Path = ALLOWLIST_PATH) -> DeadSymbolAllowlist` has these properties:
- **Pure.** It does not import `src/`, walk the corpus or touch the network.
- **Import-time use.** The module constants `SYMBOL_ALLOWLIST` and `WIDENED_SCOPE_GRANDFATHERED_470` call it at import, so any schema error fails collection loudly.
- **Errors.** On any violation it raises `AllowlistSchemaError(ValueError)`. The message names the file, a location pointer (e.g. `entries[41].issue`) and the rule id.

| Rule | Requirement |
|---|---|
| L1 | The file exists and parses as YAML through a `yaml.SafeLoader` subclass. |
| L2 | The top level is a mapping with **exactly** the keys `schema_version`, `categories`, `entries` and `widened_grandfathered_470`. |
| L3 | **Duplicate mapping keys are rejected at every level.** PyYAML's default silently keeps the last one, which would hide a duplicate category. |
| L4 | `schema_version == 1`. |
| L5 | Unknown keys are rejected in categories, entries and the widened section and its entries. |
| L6 | Every category `rationale` is a non-empty string. An entry `rationale`, if present, is non-empty. The effective rationale (the entry's, or else its category's) is never empty. |
| L7 | `entries[].category` names a declared category. If that category has `requires_issue: true`, then `issue` is present and matches `^(#\d+\|[\w.-]+/[\w.-]+#\d+)$`. `requires_issue` is a real bool. |
| L8 | `(module, name)` is unique across `entries` ∪ `widened_grandfathered_470.entries`. The error names both locations. |
| L9 | Every declared category has at least one entry. There are no tombstones. |
| L10 | `module` is a dotted ASCII identifier path, and `name` satisfies `str.isidentifier()` and contains no `.`. |

The loader must not accept `line`, `body_hash` or `source_module` keys (L5 covers this). It must also not define an inline escape marker.

## 2. Gate contract: `tests/architectural/test_no_dead_symbols.py`

The terms used below:
- `all_literal_decls[m]` is the static `__all__` of module `m`;
- `K(m, n) = DeadSymbolKey(m, n)`;
- `A` is the loaded allowlist.

| Rule | Requirement |
|---|---|
| G1 Exemption | An `__all__` symbol `(m, n)` is exempted by the allowlist **iff** `K(m, n) ∈ A.keys` **and** `resolve_symbol_key(...)` for it is not `None`. The lookup key is never a hash. |
| G2 Offender | A symbol with no caller, no G1 exemption and no auto-exemption is an offender, printed as `m::n`. |
| G3 Stale | Every entry gets exactly one verdict, in the order INVALID → GONE → REVIVED → SUPERSEDED → MOOT (data-model §1.5). Any verdict other than *live* fails and prints `m::n [VERDICT] <hint>`. GONE adds a "probably moved to `X`" hint when an offender `X::n` exists. |
| G4 Widened | The widened list is `A.widened_qualified`, with the current `_apply_widened_scope_exemptions` / `_compute_widened_stale` behaviour unchanged. |
| G5 Auto-exempt | The T013 auto-exempt keeps condition (1), computed live through `resolve_symbol_key` / `classify_collisions`. That is the only surviving use of hashing, together with the G1 keyability check. |
| G6 Removed | These are deleted: the T016 one-signal suppression; the `source_module` provenance guards (today `:2408`, `:2425`); the cross-category duplicate guards (today `:2506`, `:2537`, replaced by L8); all `_CATEGORY_*` literals; the module_path-tier escalation entries. |
| G7 Injection | The offender and stale computations take the allowlist as a parameter (`allowlist: DeadSymbolAllowlist`). The real-tree tests pass `load_allowlist(ALLOWLIST_PATH)`. M11 passes a scratch copy. The corpus walk is session-cached, so M11 adds **no** second full walk. |
| G8 Compatibility | `_SYMBOL_ALLOWLIST` (a `frozenset[DeadSymbolKey]`) and `_WIDENED_SCOPE_GRANDFATHERED_470` (a `frozenset[str]`) remain module attributes. So `test_p1_planted_regression.py:257`'s `isinstance(..., frozenset)` fallback and `len()` consumers keep working. |

### 2.1 Non-vacuity floor

The floor is on the scanned corpus, not on the allowlist, whose goal state is 0. It is asserted in the real-tree test:

```python
assert sum(len(v) for v in all_literal_decls.values()) >= 3500   # live: 3,922 names
assert len(all_literal_decls) >= 600                              # live: 656 modules
```

The stale check is a second line of defence: a walker that returned nothing would report every entry GONE.

### 2.2 Growth cap (IC-12)

`_SizeRatchet("test_no_dead_symbols", "allowlist_entries", "tests.architectural._dead_symbol_allowlist", "SYMBOL_ALLOWLIST")` has the leaf `_baselines.yaml: test_no_dead_symbols.allowlist_entries`, set to the live count at landing. Growth above it fails, and shrinkage warns (Burn-down (a)). The count is held **only** in `_baselines.yaml`, never in the YAML data.

## 3. Self-mutation battery (DIRECTIVE_043, `architectural-gate-non-vacuity`)

Every case goes through the production `_compute_offenders` / stale path, over synthetic corpora or scratch YAML. "Stale X" means the G3 verdict X.

| # | Plant | Expect | Lives in | Replaces or keeps |
|---|---|---|---|---|
| M1 | Allowlisted dead `m::Baz = 1`, whose body is then edited to `Baz = 2` | offenders `[]`, stale `[]` | contract file (IC-09) | **Inverts** `bite_g`'s body-edit arm. This is the FR-009 acceptance test (SC-003). |
| M2 | A new dead `New` in an allowlisted module | offender `m::New` | gate (IC-10) | keeps `test_gate_still_flags_a_truly_dead_symbol`; `test_p1_planted_regression.py:180` |
| M3 | Allowlist `(a, Shared)`, while `b::Shared` is dead with a different body | offender `b::Shared` | gate | `bite_c` |
| M4 | Allowlist `(sanctioned, GateDecision)`, plus a byte-identical `rogue::GateDecision` | offender `rogue::GateDecision`, with no escalation logic involved | gate | `bite_i`, simplified |
| M5 | An allowlisted symbol gains a direct caller | stale REVIVED | gate | `bite_d` (content arm) |
| M6 | An allowlisted symbol is deleted | stale GONE | gate | `bite_g`'s dangling arms |
| M7 | Rename `Old` → `New`, still dead | stale GONE `(m, Old)` **and** offender `m::New` | contract file (IC-09) | **New**: "a rename is reported, not silently passed" (spec Edge Case 5) |
| M8 | Move `a::N` → `b::N`, still dead | stale GONE `(a, N)` with a "probably moved to `b`" hint, **and** offender `b::N` | contract file (IC-09) | **New**. Supersedes `bite_b` and `bite_j`'s relocation arm. |
| M9 | `__all__ = ['Ghost']`, allowlisted | offender `m::Ghost` **and** stale INVALID | gate | `bite_f` |
| M10 | An allowlisted name removed from `__all__`, with the symbol still defined | stale GONE | gate | **New** |
| M11 | Authority parse: a scratch YAML (a) missing one live entry, and (b) carrying one bogus entry, run over the **real** cached corpus | (a) an offender naming the removed entry; (b) stale GONE naming the bogus entry | contract file (IC-09) | **New**. It proves the gate reads the file it claims to read. |
| M12 | Scratch YAMLs, one plant each: a duplicate `(module, name)` in the same category; the same in different categories; the same across `entries` and `widened`; an undeclared category; an empty rationale; `requires_issue` with no `issue`; a duplicate category key; an unknown key; a tombstone category | `AllowlistSchemaError` naming the rule (L3/L5/L6/L7/L8/L9) | gate | replaces `:2506` and `:2537`, and closes the intra-category blind spot (`check_push_safety` ×2) |
| M13 | The walker monkeypatched to return a quarter of the modules | the §2.1 floor assertion goes red | gate | **New** |

Also **kept**, rebased onto `DeadSymbolKey`:
- `bite_e`;
- `bite_k`, now "every entry is keyable": M9 at corpus scale, i.e. no INVALID on the real tree;
- the auto-exempt disjointness check, now folded into stale SUPERSEDED;
- the #470 widened tests;
- the dynamic-accessor tests.

**Deliberately retired**, with the reason recorded in the ADR: `bite_b`, `bite_g`'s body-edit arm and `bite_j`'s relocation arm. They encoded the old identity contract. M1, M7 and M8 replace them.

**ATDD rule for IC-09.** The contract tests import the new seam **inside** each test body. The file collects today, and each test is RED individually, failing on its assertion or on the missing seam, until IC-10 lands. A module-scope import that errors at collection is not an acceptable red.

## 4. Migration and parity protocol (IC-09 → IC-10)

1. **Before (IC-09).** Snapshot `{(module, name, category)}` for every live `__all__` location whose `_resolve_final_key(...)` is in today's `_SYMBOL_ALLOWLIST`, plus the widened set, plus the offenders and stale lists (both `[]`), into `evidence/dead-symbol-parity/before.json`.
2. **Convert (IC-10).** Run the scratchpad-only converter; it is never committed. For each `SymbolKey`:
   - the module is `module_path` if set, else `source_module`. **`module_path` wins** (the `merge_three_layers` trap: `charter.drg` over `charter.offering.drg.merge`);
   - the category is the enclosing constant's name, lower-cased, without the leading underscore;
   - the rationale is the entry's own comment, if any. The block comment becomes the category rationale.

   The widened strings split on `::`. The duplicate `check_push_safety` collapses to one entry. The 9 empty categories are dropped.
3. **After (IC-10).** Take the same snapshot through the new path into `after.json`.
4. **Assert parity.** `before.json` and `after.json` are equal on `allowlist`, `widened_470`, `offenders` and `stale`. The counts are 293 and 91 on today's base; re-take `before` if the mission rebases.
5. **Record.** Put the commands and outputs in `evidence/IC-10-*.md`.

## 5. Acceptance mapping

| Spec item | Proven by |
|---|---|
| US2 AC-1 / SC-003 / NFR-003 (a body edit needs 0 edits) | M1, plus the IC-09 real-tree plant: red before, green after |
| US2 AC-2 (a newly dead symbol reds and is named) | M2, M3, M4 |
| US2 AC-3 (a deleted or revived entry is reported stale) | M5, M6, M10 |
| Edge Case 5 (a rename or move is reported) | M7, M8 |
| FR-009 fail-closed on un-keyable names | M9 |
| DIRECTIVE_043 non-vacuity | the §2.1 floor, M11, M13 |
| C-003 shrink-only | the §2.2 cap (IC-12); L8 and M12 stop silent duplication |
