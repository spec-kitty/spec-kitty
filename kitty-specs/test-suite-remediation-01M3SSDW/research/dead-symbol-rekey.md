# Research: Dead-Symbol Allowlist Re-key (FR-009) and Architectural-Gate Brownfield Scout

> **Lens:** architect-alphonso. I am the design lens for FR-009 (the dead-symbol allowlist re-key) and the brownfield scout for the architectural gates in `test-suite-remediation-01M3SSDW` (#5346 under #5353). I only write this file. Nothing here is implemented.
>
> **Base:** `issue-5353-test-suite-remediation` at `732f445a1e` (upstream/main `74373ec95a`). Every count below was measured on this tree. `tests/architectural/test_no_dead_symbols.py` and `test_refresh_dead_symbol_hashes.py` both pass here: **52 passed in 229.65 s**.

## 0. Decision in one paragraph

Re-key every dead-symbol allowlist entry to **`(module, name)`**:
- `module` is the dotted module whose `__all__` declares the name. It is the same locus the gate already evaluates (`mod_dotted`).
- `name` is the bare module-level name.

Move the entries out of the test source into a **schema-validated YAML file**, `tests/architectural/dead_symbol_allowlist.yaml`, beside `_baselines.yaml`.

Drop the persisted `body_hash` completely. The hash machinery (`resolve_symbol_key`, `classify_collisions`, `key_tier`) stays **at runtime only**, for two narrow jobs:
- a keyability precondition: an allowlisted name must bind something real;
- the existing collision guard on the re-export auto-exempt.

No hash value is ever stored again, so no body edit can force a test edit.

The migration is a proven **bijection**: 293 entries map to exactly 293 live `(module, name)` locations, with no entry covering more than one location and no location unmatched. The migration therefore has an exact parity check.

The claimed benefit of the content tier, relocation-proofness, is **already gone** in practice. Since #3552, `test_every_content_tier_source_module_is_live_and_declares_symbol` forces a `source_module=` edit on every move. The re-key loses nothing that is still live.

**An ADR is warranted.** This changes the identity model of a C-007 enforcement-canon gate and reverses two recorded decisions: D-1 of `relocation-hardened-dead-code-scanners-01KX958P`, and the refresh-helper design of `frozen-baseline-toll-reduction-01M0A42D`.

---

## 1. Current mechanism (end to end)

| Stage | Where | What it does |
|---|---|---|
| Symbol collection | `test_no_dead_symbols.py:3102` `_walk_modules` | Walks every `src/**/*.py` and returns:<br>• `all_literal_decls`: the static `__all__` of each module. **656 modules, 3,922 names.**<br>• `decls`: `__all__` ∪ public module-level names (#470 widening). **1,303 modules, 7,868 names.**<br>• `corpus`: `CorpusModule(tree, source, containing_pkg)`. |
| Caller search | `:3149` `_imports_by_target` plus detectors (a) through (e) | Builds the `per_symbol[target_module] -> {names}` edge map from these sources:<br>• `from X import name`<br>• module-attribute access `:2674`<br>• `getattr` strings `:2704`<br>• facade lazy dicts `:2766`<br>• call-bound dynamic accessors `:3200`<br>`_symbol_has_caller` (`:3233`) accepts a caller that imports from:<br>• the declaring module;<br>• its parent package;<br>• any submodule. |
| Identity (today) | `_symbol_key.py:90` `SymbolKey`, `:417` `resolve_symbol_key`, `:521` `key_tier`, `:496` `classify_collisions` | Each `__all__` name resolves to one of three outcomes:<br>• **content tier** `(bare_name, body_hash)`, which is location-free;<br>• **module_path tier** `(bare_name, module_path, body_hash)`, used only when ≥2 live `__all__` locations share name and hash (a live collision);<br>• **`None`**, meaning un-keyable, fail-closed.<br>`body_hash` is the sha256 of the `code_tokens_by_line` token lines of the definition span (`:204`), or of a single import alias (`:263`). The line structure is part of the hashed text. |
| Allowlist | `:153`–`:2289`, `_SYMBOL_ALLOWLIST` union at `:2296` | 42 `_CATEGORY_*` frozensets, of which 33 are non-empty and **9 are empty tombstones**. **294 `SymbolKey(...)` literals**, which collapse to **293 set members**: one intra-category duplicate is silently deduped (see §8.4). Of the 293:<br>• **275 content-tier** entries, all carrying `source_module=`;<br>• **18 module_path-tier** entries. |
| Exemption check | `:3471` `_compute_offenders`, `:3506` | 1. `final_key in allowlist`.<br>2. Otherwise T013 auto-exempt (`:3442`):<br>&nbsp;&nbsp;• migration class;<br>&nbsp;&nbsp;• Typer sub-app;<br>&nbsp;&nbsp;• Typer command;<br>&nbsp;&nbsp;• re-export shim. Condition (1), "content-tier only", is at `:3429`.<br>3. Otherwise a real caller.<br>4. Otherwise the symbol is an offender. |
| Stale: gained a caller | `:3517` `_compute_stale` | The key still resolves and is still allowlisted, and the symbol now has a caller. The entry is reported stale. |
| Dangling: key orphaned | `:3555` `_compute_dangling` | • A content-tier entry dangles when no live location matches `(name, hash)`.<br>• A module_path-tier entry dangles when the module no longer declares the name.<br>• "One-signal" suppression (`:3604`): a dangling content entry is hidden when the offender list names the same `bare_name`. This is the body-edit path, and it surfaces as a **fresh offender**. |
| Provenance guards | `:2408`, `:2425` | Every content-tier entry must carry `source_module=`. That module must declare the name in the live corpus. **This is what makes a move cost an edit today.** |
| Duplicate guards | `:2506`, `:2537` | These catch cross-category duplicates only. Frozenset union hides intra-category duplicates. |
| Widened grandfather | `:3632` `_WIDENED_SCOPE_GRANDFATHERED_470` | **91 plain `"module::Name"` strings.** This is a second exemption list for the same gate, **already keyed the way this design proposes**. It has its own stale logic at `:3773`. |
| Refresh helper | `_refresh_dead_symbol_hashes.py` | Rewrites a `body_hash` literal in place only when exactly one still-dead candidate survives `module_path`/`source_module` narrowing. Otherwise it refuses with DANGLING, AMBIGUOUS, UNRECOVERABLE or NEEDS_MODULE_PATH. It never appends. `main()` (`:453`) edits `test_no_dead_symbols.py` in place. |

### What the body hash actually buys today

| Claimed property | Verdict on this tree |
|---|---|
| **Relocation-proof identity** (D-1). A pure move keeps the key. | **Vestigial.** The key survives a move, but the FR-007 integrity guard (`:2425`) reds until `source_module=` is edited. The history confirms it: `f5c15f9f88` (merge→consolidate rename) edited 28 `source_module` values, `e72f8b8a0b` edited 26, `676a649e94` edited 24. A move costs **one edit per entry** today, the same as under `(module, name)`. |
| **Disambiguating same-named symbols.** Stops the `ArtifactKind`-style byte-identical re-export from re-blinding T004. | **Self-inflicted.** The collision problem exists only because the content key is location-free. `(module, name)` is unique per location by construction, because an `__all__` is a set. A rogue identical sibling in another module has a different key and is caught with no collision logic. The 18 module_path-tier entries are exactly this workaround. |
| **"The exempted thing changed, so re-justify."** | **Not exercised.** Every sampled re-pin re-pinned mechanically and left the rationale untouched, typically with a comment like "Hash re-pinned … (same entry, same symbol)". `639aa2febc` is one example. Nobody re-justified anything. The hash is not even formatter-stable: `2641f6b181` ("Restore Ruff format cleanliness") re-pinned `DeclaredCommandScopeSource` because ruff joined a 3-line call onto 1 line. `body_hash` joins token *lines* with `\n` (`_symbol_key.py:213`). |

---

## 2. Refresh-commit history, classified

I classified every non-merge commit that changed the allowlist mechanically. For each commit, I diffed the parsed `SymbolKey` sets of the parent and the child and paired entries by identity. The script is in the session scratchpad only.

**Lifetime:** 202 non-merge commits, of which 173 touch allowlist entries.

**Since the `source_module` backfill (`0188aee2c7`, 2026-08-18), excluding that commit:** 78 commits touched the allowlist.

| Change kind | Entries | Commits containing it | Forced by |
|---|---:|---:|---|
| **Body-edit re-pin** (same name and module, new hash) | **57** | **41 (53%)** | Behaviour-neutral production edits. **25 commits (32%) did nothing else to the allowlist.** |
| Move (same hash, new `source_module`) | 132 | 5 | Package renames or splits |
| New dead symbol added | 67 | 20 | Real new exemptions (legitimate) |
| Entry removed | 137 | 32 | Debt paid down (the 2026-09-30 dead-code sweep dominates), or wiring |

### Sample of 11 commits

| Commit | Date | Forced by | Class |
|---|---|---|---|
| `639aa2febc` | 09-30 | `append_lifecycle_event` gained an optional parameter. Comment: "same entry, same symbol". | body edit (toll) |
| `5ae9a41887` | 09-29 | A `Divergence` field was added (#5046). "body_hash refreshed again". | body edit (toll) |
| `61a8af3077` | 09-27 | A duplicate blob reader was collapsed (#5119). | body edit (toll) |
| `f5c15f9f88` | 09-27 | `merge` → `consolidate` package rename. | move, 28 edits |
| `fb046369b0` | 09-26 | "test(landing): re-pin dead-symbols + census baselines". | body edit (landing toll) |
| `8b769edeec` | 09-24 | "re-key Divergence dead-symbol hash after the squash-blob field". | body edit (landing toll) |
| `532cccf063` | 09-24 | 8 intentional terminus residuals allowlisted. | new dead symbol (legitimate) |
| `6bb119d0d0` | 09-30 | Domain-A dead-code sweep: 10 entries removed, 1 re-pinned. | removal (debt paid) plus toll |
| `2641f6b181` | 09-02 | A **ruff reflow**, with no semantic change at all. | body edit (toll, formatter-induced) |
| `cbbd48fa92` | 09-01 | "Fix CI-red: refresh stale dead-symbol allowlist hash". | body edit that escaped to CI |
| `e72f8b8a0b` | 08-29 | Charter activation two-module split. | move, 26 edits |

Planners already route around the toll. `kitty-specs/terminus-safety-invariant-01M2XFT7/tasks/WP03-…md:70` instructs the implementer to check whether the three hash-pinned functions were touched, and to re-pin in the same commit.

**Conclusion.** Body-edit re-pins are the single most frequent allowlist change: 41 of 78 commits. They are pure toll: 0 of the sampled re-pins changed a rationale. The re-key removes this whole class. Moves remain an edit under every candidate design, and the spec's edge case requires that anyway.

---

## 3. Options and decision

| # | Key | Body edit (NFR-003: 0 edits) | New dead symbol reds | Deleted or revived reported stale | Rename or move | Relocation-proof (D-1) | Collision machinery | Verdict |
|---|---|---|---|---|---|---|---|---|
| A | **`(module, name)`**, where `module` is the `__all__`-declaring module | **Yes, 0 edits** | Yes. Its key is simply absent from the set. | Yes: gone means the key is not in `all_literal_decls`; revived means it has a caller or is auto-exempt. | Old key stale plus new offender. Both are named, and a move gets a same-name hint. | Lost on paper. **No practical loss**, because a move already costs an edit (§1). | **Not needed for identity.** Kept only for the re-export auto-exempt condition. | **CHOSEN** |
| B | `(module_path, qualname)` | Same as A | Same as A | Same as A | Same as A | Same as A | Same as A | Same as A in practice. The gate only covers module-level names, so `qualname == name`. Calling it "qualname" would promise nested-symbol coverage the gate lacks. Reject the name, keep the shape. |
| C | `(bare_name, source_module)` plus rename detection via a stored advisory hash | 0 edits for the gate verdict | Yes | Yes | Rename hint via the hash | Same as A | Keeps a stored hash | **Rejected.** A stored hash that nothing enforces rots silently and invites "just refresh it". The spec's edge case only needs a rename to be *reported*; old-key stale plus new-name offender already names both ends. |
| D | Externalised YAML keyed on qualname | This is a *location* choice, not a key. Orthogonal to A/B/C. | — | — | — | — | — | Adopted as the data location for A (see §4). |
| E | Keep `(name, body_hash)`; make the hash advisory; the refresh helper runs automatically | Still one edit (the helper rewrites the source) | Yes | Partly. A body edit still collides with the "dangling" logic. | Unchanged | Kept on paper | Kept, including 18 escalated entries | **Rejected.** It fails NFR-003 and SC-003, because the helper's output is a test-source edit. `01M0A42D` already tried this (SC-002 was "one helper invocation"), and 57 re-pins happened afterwards. |

### Why A does not re-open the defects the content tier was built to close

| Guard | Why it holds under A |
|---|---|
| **T004 re-blinding** (same-name fan-out, byte-identical siblings) | Each location has its own key. `bite_c` and `bite_i` stay green without escalation logic, because a rogue sibling's `(module, name)` is never in the set. |
| **T006 fail-closed** (un-keyable names) | Kept explicitly. An entry exempts a symbol **only if** `resolve_symbol_key(...) is not None`, i.e. the name binds a real definition, alias or facade. An `__all__ = ['Ghost']` name stays an offender even when allowlisted, and the entry is reported invalid. `bite_f` is preserved. |
| **T013 auto-exempt disjointness** | Unchanged. The re-export auto-exempt keeps condition (1) `final_key.module_path is None` (`:3429`), computed live. Parity requires this. Dropping it would silently auto-exempt collision re-exports, which is a weakening **and** would red the disjointness test. It stays as an out-of-scope follow-up. |

### Exact staleness semantics under A

An entry is reported by exactly one rule. Rules are checked in this order:

1. **INVALID** when `(module, name)` is declared in `__all__` but `resolve_symbol_key` returns `None`. The entry cannot exempt an un-keyable name.
2. **GONE** when `name ∉ all_literal_decls.get(module, ∅)`. This covers four cases: deleted, renamed, moved, or dropped from `__all__`.
   - Message hint: if the offender list contains `X::name` for some other module `X`, add "probably moved to `X` — update `module:`".
   - A rename surfaces as GONE(old) plus an offender naming the new name. That satisfies the spec edge case: the gate reports it and does not pass silently.
3. **REVIVED** when the name is declared and `_symbol_has_caller(...)` is true.
4. **SUPERSEDED** when the name is declared and `_is_auto_exempt(...)` is true. Today this is a separate test (`:4438`); fold it into the same stale report.
5. **MOOT** when `module ∈ star_targets`. The offender pass skips the module, so the entry exempts nothing. Today such an entry lingers silently: it is not dangling (the content key still resolves) and not stale (the module is skipped). This is **stricter than today**. On this tree there are 0 star targets, so there is no day-one red.

The T016 "one-signal" suppression (`:3604`) is **deleted**. Its only purpose was to hide the body-edit double-flag, and that case no longer exists.

---

## 4. Data location and ADR

**Location.** Put the data in `tests/architectural/dead_symbol_allowlist.yaml`, loaded by a new `tests/architectural/_dead_symbol_allowlist.py`, following the house convention for `_`-prefixed scaffolding.

Reasons:
1. The spec's diagnosis is "exemption data held in the test source". The 4,824-line gate file co-changes with 516 src files because data edits and logic edits share one file. Separating them lets gate-logic history mean gate-logic change.
2. There is precedent: `inline_meta_read_allowlist.yaml`, `charter_path_literal_allowlist.yaml`, `mission_type_reader_allowlist.yaml` and `requirement_id_pattern_allowlist.yaml` all live beside `_baselines.yaml`.
3. Rationales become structured fields rather than free comments, so a loader can **enforce** FR-303 (rationale required; an issue required for category B).
4. The positional-anchor ban explicitly allows `module::Name` keys (`test_ratchet_positional_anchor_ban.py:11-14`). **Do not add a `line:` field.** The ban would not flag it, but it re-invites drift.

Proposed shape (the plan should confirm it):

```yaml
schema_version: 1
categories:            # declared once; rationale/target at category level
  a_slice_f_deferred: {rationale: "...", target: "0 by Slice G"}
  b_grandfathered_legacy: {rationale: "...", requires_issue: true}
entries:
  - module: specify_cli.dashboard.server
    name: BackgroundPortReportError
    category: a_slice_f_deferred
    rationale: "#577: deliberately exported typed failure contract ..."
    issue: "#577"
```

Loader rules (all fail at import):
- unknown keys are rejected;
- `(module, name)` must be unique across the **whole file**, which fixes the intra-category blind spot;
- `category` must be declared;
- `rationale` must be non-empty;
- an `issue` is required where the category demands one;
- categories with no entries are rejected, so no tombstones.

`test_no_dead_symbols._SYMBOL_ALLOWLIST` stays a module attribute: a `frozenset[DeadSymbolKey]` loaded at import. That keeps the fallback at `test_p1_planted_regression.py:257` (`isinstance(... , frozenset)`) and any `len()` consumer working.

**Size ratchet (the charter-drift fix, recommended).**
- The charter's Burn-down Policy (a) (`charter.md:638-640`) says every mutable architectural allowlist is capped in `_baselines.yaml`.
- The dead-symbol allowlist currently has **no growth cap**. `01M0A42D` FR-005 deleted the *inert* key, and `test_ratchet_baselines.py:566` now forbids re-adding it without a real row.
- Add one `_SIZE_RATCHETS` row, `test_no_dead_symbols.allowlist_entries -> _SYMBOL_ALLOWLIST`, with baseline 293.
- The count lives **only** in `_baselines.yaml`. Do not also put it in the YAML data file: `inline_meta_read` shows that three copies of one count is the failure mode (§8.2).
- This row trips `test_ratchet_baselines.py:618` `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 15`, itself an exact-count pin of the FR-007 class. Convert it to a floor in the same change, not a bump to 16.
- If the operator judges the growth toll unwelcome, this is separable. Record it as a plan decision.

**ADR: yes.** File it at `docs/adr/4.x/`, where new ADRs land. Suggested title: *"Dead-symbol allowlist identity is `(module, name)`; body hashes are runtime-only."*

The ADR should cover:
- **Context.**
  - D-1 and the 01M0A42D refresh helper;
  - 57 re-pins in 41 of 78 commits since 2026-08-18;
  - relocation-proofness forfeited in practice by the FR-007 guard;
  - the formatter-induced re-pin `2641f6b181`.
- **Decision.**
  - Identity is `(module, name)`, where `module` is the `__all__`-declaring module.
  - The data moves to YAML.
  - Body hashes are never persisted.
  - The runtime hash is kept only for the keyability precondition and the re-export auto-exempt collision guard.
  - The refresh helper is retired.
  - A size-ratchet row is added.
- **Consequences, positive.**
  - A body edit costs 0 edits.
  - Collision escalation is gone, along with its 18 module_path-tier entries.
  - Intra-category duplicates become detectable.
  - The gate file stops co-changing with src.
  - Charter Burn-down (a) is honoured.
- **Consequences, negative and accepted.**
  - A move or rename costs one YAML edit. This is the same as today, and it is now explicit.
  - `bite_b`, `bite_g`'s body-edit arm and `bite_j`'s relocation arm are deliberately **inverted or retired**; they encoded the old contract.
  - `_symbol_key.SymbolKey.source_module` and its G1–G6 guards are deleted.
- **Supersedes:** D-1 (in part: persisted identity only), 01M0A42D FR-001/FR-002 (the helper), and #3552 FR-006/FR-007 (source_module guards).
- **Non-goals:**
  - changing the caller detectors;
  - changing the widened #470 scope;
  - removing auto-exempt condition (1).
- **Related:** `2026-09-14-1-census-floor-ratchet-adjudication.md`. It is the precedent for adjudicating toll ratchets per ratchet.

---

## 5. Non-vacuity plan (DIRECTIVE_043 / `architectural-gate-non-vacuity`)

### Concrete floor

The floor sits on the **scanned corpus**, not on the allowlist, because the allowlist's goal state is 0.
- `sum(len(v) for v in all_literal_decls.values()) >= 3500`; the live value is 3,922.
- `len(all_literal_decls) >= 600`; the live value is 656.

Together these stop a broken walker from passing vacuously. The stale check adds a second line of non-vacuity: if the walker returned nothing, all 293 entries would report GONE.

### Self-mutation tests

All of these go through the production `_compute_offenders` / `_compute_stale` path with synthetic corpora, following the existing C-007 practice.

| # | Plant | Expect | Replaces or keeps |
|---|---|---|---|
| M1 | An allowlisted dead `Baz = 1`, whose body is then edited to `Baz = 2` | offenders `[]`, stale `[]` | **Inverts** `bite_g` (`:4748-4767`), which asserts the body edit is an offender. **This is the FR-009 acceptance test and SC-003.** |
| M2 | A new dead `New` in an allowlisted module | offender `m::New` | Keeps `test_gate_still_flags_a_truly_dead_symbol` (`:4391`) and `test_p1_planted_regression.py:180` |
| M3 | Allowlist `(a, Shared)`; `b::Shared` is dead with a different body | offender `b::Shared` | `bite_c` |
| M4 | Allowlist `(sanctioned, GateDecision)`; a byte-identical `rogue::GateDecision` | offender `rogue::GateDecision`, with **no** escalation involved | `bite_i`, simplified |
| M5 | An allowlisted symbol that gains a direct caller | stale REVIVED | `bite_d` (content arm) |
| M6 | An allowlisted symbol that is deleted | stale GONE | `bite_g` dangling arms |
| M7 | An allowlisted symbol that is renamed `Old` → `New` and is still dead | stale GONE `(m, Old)` plus offender `m::New` | **New.** This is the "planted rename is reported" case. |
| M8 | An allowlisted symbol moved `a` → `b` and still dead | stale GONE `(a, N)` with a "moved to b" hint, plus offender `b::N` | **New.** Supersedes `bite_b` and the relocation arm of `bite_j`. |
| M9 | `__all__ = ['Ghost']`, allowlisted | offender `Ghost` plus entry INVALID | `bite_f` |
| M10 | An allowlisted name removed from `__all__` (the symbol still exists) | stale GONE | **New** |
| M11 | Authority-parse check: point the loader at a scratch YAML (a) missing one live entry and (b) with one bogus entry | (a) an offender naming it; (b) stale naming it | **New.** Required by the tactic's authority-parse step: the gate must read the file, not a cached copy. |
| M12 | A scratch YAML with a duplicate `(module, name)` (same or different category), an undeclared category, an empty rationale, or a category-B entry with no issue | the loader raises | Replaces `:2506`/`:2537`, and closes §8.4 |
| M13 | The corpus floor, with the walker monkeypatched to return ¼ of the modules | the floor assertion reds | **New** |

**Keep, rebased onto the new key:**
- `bite_e`;
- `bite_k`, which becomes "every entry is keyable" (M9 at corpus scale);
- `test_auto_exempt_disjoint_from_hand_allowlist`, which becomes stale SUPERSEDED;
- the #470 widened tests `:3932-4134`, which are untouched;
- the dynamic-accessor tests `:4169-4389`, which are untouched.

---

## 6. Migration plan (293 entries, lossless)

**Measured inventory:**
- 294 literals, which dedupe to 293 set members;
- 275 content-tier entries (all with `source_module`) and 18 module_path-tier entries;
- 33 non-empty categories and 9 empty ones.

**Parity result, measured now:**
- the live `__all__` locations exempted by the current allowlist number **exactly 293**;
- **293 distinct entries** match, **0** entries match more than one location, and **0** entries match nothing;
- for **all 275** content-tier entries, `source_module` equals the exempted location;
- for **all 18** module_path-tier entries, `module_path` equals the location;
- **0** exempted symbols have a caller or are auto-exempt, so there is no latent staleness.

The mapping is a bijection, so the conversion is mechanical:
- content-tier: `(source_module, bare_name)`;
- module_path-tier: `(module_path, bare_name)`.

One trap: `merge_three_layers` has `module_path="charter.drg"` but `source_module="charter.offering.drg.merge"`. **`module_path` wins**, because it is the `__all__`-declaring locus the gate evaluates. The converter must prefer `module_path` whenever it is set.

**Procedure** (a single commit with red-first ordering; see the WP split):
1. **Before** changing any code, snapshot `OLD = {(mod, name) for every live __all__ location whose _resolve_final_key(...) ∈ _SYMBOL_ALLOWLIST}` and the category membership `{(mod, name): category}`. Write both as sorted JSON to `kitty-specs/test-suite-remediation-01M3SSDW/evidence/dead-symbol-parity/before.json`.
2. Run a one-shot converter from the scratchpad; it is never committed as a tool. It emits the YAML. Rationale text comes from the comment block immediately above each `SymbolKey(...)` and the trailing `# module::Name` comment. A comment shared by a block of entries becomes the category rationale. Deliver the rationales best-effort, then hand-review them in the diff.
3. After the switch, compute `NEW` the same way through the new path and write `after.json`.
4. **Parity assertion:** `before.json == after.json` must hold byte-for-byte on the sorted `(module, name, category)` tuples, and `len == 293`. Also check that the offender list and the stale list are both `[]` before and after. Record the command and its output in the evidence record (FR-011).
5. Planted-break proof for the retirement of the refresh helper (C-002): plant a new dead `__all__` symbol. The **new** M2 path and `test_p1_planted_regression` must both go red. Revert, and record the result.
6. Fold the duplicate `check_push_safety` at `test_no_dead_symbols.py:1329-1334` into one entry. It is recorded as the reason `literals (294) ≠ members (293)`.

---

## 7. Proposed work-package split and file ownership

Everything is sequenced red-first. Ownership is disjoint so the WPs can lane cleanly.

| WP | Purpose | Owns | Depends |
|---|---|---|---|
| **WP-A — ATDD pins** | Commit M1, M7, M8 and M11 **red** against today's gate. M1 must red, because today a body edit is an offender. Also commit the parity-snapshot script and `before.json`. | new `tests/architectural/test_dead_symbol_allowlist_contract.py`; `kitty-specs/.../evidence/dead-symbol-parity/` | none |
| **WP-B — Re-key and externalise** | Add the loader and the YAML. Switch `_compute_offenders`, stale and dangling to `(module, name)` with the INVALID, GONE, REVIVED, SUPERSEDED and MOOT rules. Delete T016 suppression, the `_CATEGORY_*` literals, the `source_module` guards and the duplicate guards (M12 replaces them). Rewrite the `bite_*` battery (M2–M10, M12, M13). Take the `after.json` parity. WP-A goes green. | `tests/architectural/test_no_dead_symbols.py`, `_dead_symbol_allowlist.py` (new), `dead_symbol_allowlist.yaml` (new), `test_p1_planted_regression.py:180-213` (SymbolKey → new key) | WP-A |
| **WP-C — Retire the hash toll surfaces** | Delete `_refresh_dead_symbol_hashes.py` and `test_refresh_dead_symbol_hashes.py` (17 tests), citing the planted-break proof as the covering guard (C-002). Remove `SymbolKey.source_module` and its G-guards from `_symbol_key.py` and `tests/unit/test_symbol_key.py` (25 references). **Keep** `test_symbol_key.py:644` `len(index) == 400`, which `test_timing_coverage_invariant.py:338` pins verbatim (§8.5). Update docs: `docs/development/reference/ci-gate-mechanics.md:186-192` (the "Renaming a symbol…" section is now wrong); the `_symbol_key.py:47-52` body-sensitivity docstring; the module docstring of `test_no_dead_symbols.py`; `tests/architectural/README.md:48` (stale scope claim, a campsite fix). | the listed files | WP-B |
| **WP-D — Size ratchet and ADR** | Add the `_SIZE_RATCHETS` row plus the `_baselines.yaml` leaf `test_no_dead_symbols.allowlist_entries: 293`. Convert the `test_ratchet_baselines.py:618` `== 15` pin to a floor (FR-007 class). Update the planted leaf at `:566`, which currently plants `test_no_dead_symbols` as *unenforced*; it must plant a different section. Write the ADR in `docs/adr/4.x/`. Add a CHANGELOG entry. | `test_ratchet_baselines.py`, `_baselines.yaml`, the ADR, `CHANGELOG.md` | WP-B; separable if the operator declines the ratchet |
| *(optional)* **WP-E — Unify the #470 grandfather** | Move `_WIDENED_SCOPE_GRANDFATHERED_470` (91 `"module::Name"` strings, already the same key shape) into the same YAML under `widened:`, with the same loader and the same parity procedure. This removes the second exemption authority in one gate. | `test_no_dead_symbols.py:3632-3737`, the YAML | WP-B. Recommended; defer only if WP-B is already large. |

**Blast radius to run, as named files only (C-001):**
- `tests/architectural/test_no_dead_symbols.py` (≈230 s today; it should get faster once the persisted-hash path is gone);
- `tests/architectural/test_dead_symbol_allowlist_contract.py`;
- `tests/architectural/test_p1_planted_regression.py`;
- `tests/architectural/test_shape_guard_membership.py`;
- `tests/architectural/test_ratchet_baselines.py`;
- `tests/architectural/test_timing_coverage_invariant.py`;
- `tests/architectural/test_ratchet_positional_anchor_ban.py`;
- `tests/unit/test_symbol_key.py`;
- `make test-fast`.

Never run the `tests/architectural/` directory as a whole.

---

## 8. Brownfield map: sibling gates and cross-cutting risks

### 8.1 Body-hash and `SymbolKey` consumers

Only these files hold the dead-symbol hash identity: `_symbol_key.py`, `_refresh_dead_symbol_hashes.py`, `test_refresh_dead_symbol_hashes.py`, `test_no_dead_symbols.py`, `test_p1_planted_regression.py:36-213`, and `tests/unit/test_symbol_key.py`. No other gate persists `body_hash`.

The **content-fingerprint cousin** is `test_inline_meta_read_gate.py`. It uses the key `(file, qualname, token)` at `:90-99`, where `token` is the `code_tokens_by_line` string of the *violating line*. That token *is* the violation, so a changed token really is a changed violation. **Leave it keyed as it is.** It is not the same toll: 2 entries, and the line is the subject.

### 8.2 Exact-count and parallel-authority pins found on the way (FR-007 / FR-010 candidates)

| Anchor | Pin | Issue |
|---|---|---|
| `test_inline_meta_read_gate.py:75` `INLINE_META_READ_FLOOR = 2` + `inline_meta_read_allowlist.yaml:19` `inline_meta_read_baseline: 2` + `:965-971` `len(allowlist) == INLINE_META_READ_FLOOR` | One debt count held in **three authorities** | Parallel authority (DIRECTIVE_044). `:971` uses a *name*, not a literal, as its right-hand side, so a census that matches only `len(x) == <int literal>` **misses it**. |
| `test_ratchet_baselines.py:618` `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` | Exact count of a live derived collection | FR-007 class. WP-D trips it. Convert it to a floor (`>= 15`) plus the existing duplicate check at `:612-613`. |
| `test_ratchet_baselines.py:611` `len(_SIZE_RATCHETS) >= 19` | Floor | Already the invariant form. Keep. |
| `test_timing_coverage_invariant.py:386` `len(BASELINE_FUNCTIONAL_ASSERTIONS) == 62` | Exact count of a frozen evidence table | Frozen by design (a canonical-commit snapshot). The FR-010 census should baseline it, not convert it. |
| `test_no_dead_modules.py:124-627` | Nine `_CATEGORY_*` frozensets of module-path strings, capped by `_SIZE_RATCHETS` | No hash and no exact-count pin. Same key shape as the proposed design. **No change needed.** It is the model the dead-symbol gate should converge on. |

### 8.3 Parallel-authority risks

1. **Refresh helper vs gate.** `_refresh_dead_symbol_hashes.main()` (`:466-469`) computes still-dead over the **widened** `decls`, but the gate checks the allowlist against `all_literal_decls` (`test_no_dead_symbols.py:3860`). Two authorities disagree on scope. The disagreement is benign today, because `module_path` narrowing hides it. It is moot once WP-C retires the helper.
2. **Two exemption lists in one gate:** `_SYMBOL_ALLOWLIST` (SymbolKey) and `_WIDENED_SCOPE_GRANDFATHERED_470` (`"module::Name"`). They have different key types and different stale logic. Once the dead-symbol list uses `(module, name)`, the stated reason for keeping them apart disappears. That reason was that content keys coincidentally collide with widened names (`:3815-3829`); `(module, name)` keys cannot collide. WP-E unifies them.
3. **The charter says one thing and the ratchet another.** Burn-down (a) (`charter.md:638`) versus the absence of any dead-symbol row, with `test_ratchet_baselines.py:559-570` actively forbidding the inert key. WP-D reconciles them with a *real* row.
4. **The C-007 enforcement canon is pinned in three places:**
   - `test_shape_guard_membership.py:54-55`;
   - `shape_guard_membership.yaml:37`;
   - `_p1_census_oracle.py:62-66` together with `test_p1_planted_regression.py` `_ENFORCEMENT_GATE_NAMES`.

   The re-key keeps the gate file name, the `architectural` marker and real `assert`s inside `test_*` functions, so all three stay satisfied. **Do not rename `test_no_dead_symbols.py`.**

### 8.4 Whack-a-field risks

- **Intra-category duplicates are invisible today.** `check_push_safety` is listed twice at `:1329-1334`, and the frozenset union dedupes it. The cross-category gate at `:2506` cannot see it. The loader's whole-file uniqueness (M12) closes the class; a per-category patch would not.
- **Empty tombstone categories.** Nine `frozenset()` categories exist only to carry retirement comments. Deleting them is safe: nothing reads them, and `_category_frozensets` treats them as empty. They should not be migrated.
- **`merge_three_layers` provenance split** (`module_path` ≠ `source_module`). The converter must key on `module_path` (§6). A naive "`source_module` first" converter would shift the exemption to the origin module, and `charter.drg::merge_three_layers` would go red.

### 8.5 FR-010 census gate: what it must coexist with

1. **Precedent risk (high).** ADR `docs/adr/3.x/2026-09-14-1-census-floor-ratchet-adjudication.md:151-180, 288-292` **retired** `test_golden_count_ban`:
   - 0 real catches in its lifetime;
   - 13 whole-tree re-freezes;
   - 387 annotation sites;
   - a classifier bug that taxed honest dynamic-result cardinality asserts (`f54c14e945`).

   Its consequence at `:419` reads: *"a future `len(X) == N` regrowth is caught by review rather than CI. Accepted."* FR-010 reverses that consequence, so it **needs its own ADR that amends 2026-09-14-1**. It must also be scoped narrowly enough to avoid the recorded failure: only **live module-level collections**, never cardinality of results or fixtures.
2. **`test_timing_coverage_invariant.py` protects exact-count asserts verbatim.** `BASELINE_FUNCTIONAL_ASSERTIONS` (`:160-360`) requires texts such as `"len(results) == 200"`, `"len(report.missions) == 204"` and `tests/unit/test_symbol_key.py: "len(index) == 400"` to keep existing. The census must **not** flag these (they are fixture-size, not live-collection). Any conversion of a listed file also reds this invariant. The census and this invariant must share one definition of "live collection pin".
3. **Right-hand sides that are names** (`len(x) == FLOOR_CONST`, e.g. `test_inline_meta_read_gate.py:971`). The census must resolve module-level integer constants or it is trivially evaded. This is the same laundering class that `test_ratchet_positional_anchor_ban.py` closed for line seeds with #2564.
4. **One baseline authority.** The census baseline belongs in `_baselines.yaml` as a `_SIZE_RATCHETS` row, not in a new JSON file. `_golden_count_baseline.json` was criticised as "a second baseline authority" (ADR `:178-180`).
5. **Scanner infrastructure.** Reuse `_ast_scan.parse_file` and the fail-closed-on-unparseable pattern (`80ba82941f`), as the positional-anchor ban does, so the NFR-002 budget (< 5 s) is reachable.

---

## 9. Risks, and how the plan proves the C-007 gate is not weakened

| Risk | Mitigation and proof |
|---|---|
| The re-key silently exempts a different set of symbols. | The §6 bijection parity: `before.json == after.json` on `(module, name, category)`, 293 rows, with offenders and stale both `[]` on both sides. It is recorded as evidence. |
| Byte-identical sibling re-blinding (T004). | M3/M4 on the production path, plus structural uniqueness of `(module, name)`. |
| Un-keyable names become exemptable. | The keyability precondition (rule 1, INVALID) and M9. |
| The auto-exempt set widens. | Auto-exempt condition (1) is unchanged, and the disjointness check is folded into stale SUPERSEDED. The parity check covers it: any drift makes an entry SUPERSEDED, which reds. |
| The gate reads a stale or cached authority. | M11 (a scratch-YAML flip) and M13 (corpus floor). |
| Growth becomes cheaper, because YAML is easier to append to than code. | The WP-D size ratchet. Growth then needs a visible `_baselines.yaml` diff, per Burn-down (a). The loader enforces rationale and issue. |
| `test_symbol_key.py` edits trip the timing coverage invariant. | WP-C keeps `:644`. Run `test_timing_coverage_invariant.py` by name. |
| The FR-010 census conflicts with retired-gate precedent. | §8.5.1: a separate ADR, and narrow scope. This is outside FR-009's WPs. |
| A move or rename now reds "more loudly". | That is intended by the spec's edge case. The move hint names the fix, and the cost equals today's `source_module` edit. |
| The runtime cost does not fall. | Hashing still runs for auto-exempt condition (1) and keyability: `classify_collisions` takes about 5.6 s and resolution about 5.5 s on this tree. That is acceptable, and the budget is unchanged. Simplifying condition (1) is a follow-up, not FR-009. |

## 10. Open decisions for `/spec-kitty.plan`

1. Is the WP-D size ratchet in scope? I recommend yes; it restores charter Burn-down (a).
2. Is WP-E (the #470 grandfather unification) in scope? I recommend yes if WP-B lands small.
3. The YAML file name and the category-id vocabulary: keep the `_CATEGORY_` suffixes in lower-case, or re-slug them.
4. Where the FR-010 ADR lives relative to 2026-09-14-1: amend it, or supersede it in part.
