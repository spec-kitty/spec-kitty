# #5085 grounding: the positional-anchor ban's scope hole

**Profile:** Analyst Annie (read-only requirements grounding; I made no repo edits).
**HEAD:** `34f19c6f`. **Sources:** issue #5085 and its triage comment (verified by the reporter at `43520a31`), #3206, closed #2077 (PR #2556).
**Evidence method:** a hand-written AST sweep (`scratchpad/sweep.py`) and a widened-predicate probe that imports the real ban helpers (`scratchpad/probe.py`). Neither is committed.

---

## 1. How the ban selects files and which shapes it detects

File: `tests/architectural/test_ratchet_positional_anchor_ban.py`.

**Which files it walks.** `_iter_architectural_python_files()` (L615-624) walks **every** `tests/architectural/**/*.py` file except the guard itself. So the scan does see every file. The hole is not in the walker. It is in **one arm's context gate** and in **two predicate shapes**.

**The four Python arms** are composed by `_scan_python_source` (L595-607):

| Arm | Lines | Detects | Scope |
|---|---|---|---|
| `_call_arg_line_sink_violations` | L301-326 | an int literal passed as the 2nd argument of `composite_key(...)`/`composite_key_from_file(...)`, or used as a subscript/`.get()` key on `code_tokens_by_line(...)` | all files |
| `_seed_string_line_anchor_violations` | L329-349 | a `"path:NNN"` string in a module-level seed container, via `is_file_line_anchor` (`src/specify_cli/contracts/anchoring.py:295-316`) | all files, but **only strings ending in `:\d+$`** (`_TRAILING_LINE_RE`, anchoring.py:290) |
| `_seed_tuple_laundering_violations` | L466-509 | a `(rel, int, ...)` seed row unpacked by a loop into `composite_key*`'s 2nd argument (#2564) | all files |
| `_raw_file_line_tuple_seed_violations` | L559-592 | a raw 2-tuple `(pathish-str-literal, int)` in a module-level seed container (CT7/#2853) | **only if `_imports_ratchet_substrate(tree)`** (L571-572) |

**The context gate.** `_imports_ratchet_substrate` (L512-529) returns True only when the file has an `ImportFrom` of `tests.architectural._ratchet_keys` or `specify_cli.contracts.anchoring`, or imports one of the names in `_RATCHET_SUBSTRATE_NAMES` (L117-130). The gate exists so that #3206's exemption in `test_kernel_no_doctrine_import.py` stays green (rationale at L111-116, L34-50, L566-569).

**Hole 2: the tuple shape is too narrow.** `_is_raw_file_line_tuple` (L548-556) requires the first element to be a **string literal** (`_is_pathish_string_literal`, L532-545). A `(Path("x.py"), 273)` row is an `ast.Call`, so it never matches, even inside a substrate-importing file.

**Hole 3: the embedded-string shape evades the check.** `is_file_line_anchor` only matches `path:N` at the end of a string. A key like `"src/x.py:98:reset_hard"` (path, line, then an op suffix) is line-pinned but ends in `:reset_hard`, so it is never flagged. The issue and the triage comment do not mention this hole.

**YAML arm.** L140-143 and L701-714 scan only 2 of the ~10 architectural YAML/JSON seeds (see §2c).

**Tests that encode the hole as intended behaviour** (they must be inverted or rewritten):
- `TestImportsRatchetSubstrate.test_ignores_non_substrate_file` (L876-879)
- `test_ct7_raw_tuple_in_non_substrate_file_stays_green` (L1086-1102)
- `test_ct7_real_3206_import_lineno_exemption_stays_green` (L1105-1120). It asserts the real kernel file produces zero findings.

**Baseline today:** the ban plus the 5 gates below give **105 passed**.

## 2. Exhaustive sweep

The sweep looked at every module-level `Assign`/`AnnAssign` whose value is a container (tuple, list, set, dict, or a `frozenset`/`set`/`dict` call). It looked for three things: a tuple with a path-ish element (string literal, `Path(...)` or a `/` BinOp) plus an int; a dict mapping a path to an int; and embedded `file.ext:N` strings. It ran over `tests/**` and was cross-checked with an annotation grep.

### 2a. Line-pinned authoritative comparands (in scope)

| file:line | symbol | shape | entries | scanned by the ban today? |
|---|---|---|---|---|
| `tests/architectural/test_built_in_location_authority.py:138-265` | `_KNOWN_JOIN_ALLOWLIST` | `frozenset[tuple[Path,int]]`; compared by exact `(rel, lineno)` at L395 | 6 (**2 dead**, see below) | **No.** The file has no substrate import (imports at L113-121) **and** the element is `Path(...)` |
| `tests/architectural/test_kernel_no_doctrine_import.py:127-132` | `_PRE_EXISTING_EXEMPTIONS` | `frozenset{(str,int)}`: `("kernel/schema_utils.py", 88)`, `(…, 97)`; consumed at L232 | 2 | **No** (context gate). This is #3206's exemption, and it already has a staleness check (L245-259) |
| `tests/architectural/test_destructive_op_routing.py:158-256` | `_ALLOWLIST` | `dict[str,str]` keyed `"rel:lineno:op"` (built at L147, diffed at L265) | 22 | **No** (the `:op` suffix evades `is_file_line_anchor`) |
| `tests/architectural/test_mutation_ownership_routing.py:238-442` | `_ALLOWLIST` | same `"rel:lineno:op"` (L228, L507, L641) | 56 | **No** |
| `tests/architectural/test_overwrite_ownership_routing.py:267-283` | `_ALLOWLIST` | same (L256, L340, L436) | 2 | **No** |

The three string-keyed gates share `tests/architectural/_destructive_op_census.py` (`diff_against_allowlist` L189, `drop_one_entry` L214, `enclosing_qualname` L148). Their comments already record re-pins, for example "Re-pinned from :239" in the destructive gate after #5001/#5020.

**Status of `_KNOWN_JOIN_ALLOWLIST`: confirmed live on HEAD, and worse than the issue says.** Its comments record 7 FRESHENED and 4 RE-PINNED events (L143-178, L218-262). The live AST check (`_find_builtin_joins` against HEAD) gives:
- `kind_vocabulary.py:273`: live, `('_org_scan_dirs', 'legacy = flat /')`
- `manager.py:161`: live, `('copy_specify_base_from_local', 'missions_src = repo_root / / /')`
- `manager.py:304`: live, `('get_local_repo_root._is_template_root', …)`
- `neutrality/lint.py:379`: live, `('_default_scan_roots', …)`
- **`src/kernel/paths.py:88` is dead.** The line is now `if is_windows():` and the file has zero live joins.
- **`src/specify_cli/runtime/home.py:79` is dead.** The line is now `for tok in tokens:` and the file has zero live joins.

The gate has no staleness or shrink-only check (tests at L377, L411, L450 only), so the two dead entries are **latent wildcards**: a new join that lands on exactly those lines would pass silently. This is a second defect in the same allowlist, beyond the line-drift friction.

### 2b. Near-misses that are not line pins (no action; the widened predicate must not flag them)

| file:line | symbol | why it is not a line pin |
|---|---|---|
| `test_json_contract_enumeration.py:217` / `:231` | `TOTAL_RESULT_EVIDENCE` (7), `DEFERRED` (64) | Free-prose evidence values such as `"decision.py:401; empty stdout; …"`. They are diagnostic and never compared. `EMB` regex: `^[^\s:]+\.\w+:\d+(:\|$)`. **Risk:** a naive "contains `.py:N`" widening *would* flag them, so the widened string predicate must anchor on the whole key or string. |
| `test_json_contract_enumeration.py:98,148` | `ADOPTED`, `PARSEABLE` | The int is an exit code |
| `test_timing_coverage_invariant.py:159` | `BASELINE_FUNCTIONAL_ASSERTIONS` (62) | `{path: {expr: count}}`; the ints are counts |
| `test_lifted_root_meta_fail_closed_census.py:90` | `_ACCOUNTED_SITES` | `(path, qualname) -> (count, reason)`; already qualname-keyed |
| `test_lane_allocation_single_seam.py:33` | `_CREATION_PARENT_ARG` | The int is an argument index |
| `_gate_coverage.py:142` | `_COLLECT_OK_CODES` | Exit codes |

### 2c. Adjacent findings outside the Python arm (record them; not required for #5085)

- `tests/architectural/census/spec_kitty_home_pin_anchor.yaml` has 40 `lineno:` fields. It is generated and SHA-pinned (`resolved_at_sha`), carries a composite `key`, and is not in the YAML arm's list.
- `charter_path_literal_allowlist.yaml` has 50 `line:` fields, documented as NON-AUTHORITATIVE (header L8-12). These would pass the YAML rule anyway.
- Outside `tests/architectural/`, `tests/runtime/_bridge_oracle.py:602` `KNOWN_DECISION_SITES: frozenset[int]` pins 29 bare line numbers of `runtime_bridge.py`. It is **already deactivated** as fragile (`tests/runtime/test_bridge_parity.py:1282-1294`). Out of scope, but it belongs to the same class; mention it in the PR.
- The sweep found no other module-level line-pinned seeds anywhere under `tests/`.

## 3. The substrate and an exemplar migration

- **Primitives** (`src/specify_cli/contracts/anchoring.py`): `code_tokens_by_line` L87, `enclosing_qualname` L182, `composite_key` L234, `composite_key_from_file` L270, `is_file_line_anchor` L295, `has_diagnostic_locator_marker` L332 (`# diagnostic-locator`). `is_file_line_anchor` is **also used by production code**, `src/specify_cli/contracts/registry.py`. Do not widen it for the `path:N:op` shape; add a separate predicate in the ban test.
- **Descriptor layer** (`tests/architectural/_ratchet_keys.py`, a re-export shim plus resolver): `ContentDescriptor(rel_path, qualname, token_substring, occurrence, rationale)` L95; `resolve_descriptor` L223 (exactly-one, otherwise raises); `descriptor_still_live` L237; `assert_descriptor_unique_within_qualname` L254.
- **Exemplar migration:** `tests/architectural/test_trio_seam_only.py:430-587` (#2564). The flow is:
  1. `_IO_ALLOWLIST_SITES: tuple[ContentDescriptor, ...]` (L449).
  2. It is resolved once at import time into `_IO_ALLOWLIST_SEEDED_KEYS` (L528-530). A mis-authored descriptor raises at import.
  3. It is narrowed to `(qualname, token_line) -> rationale` (L533-547).
  4. Live findings are keyed via `composite_key(source, violation.lineno)` (L555).

  Sibling precedents named at L444-447: `_ALLOWLISTED_RAW_JOINS` (`test_single_mission_surface_resolver.py`) and `_ALLOW_LIST_SEED` (`test_no_write_side_rederivation.py`). The ban pins the migrated shape with `test_io_allowlist_sites_carry_no_bare_int_element` (L1166-1185).
- **What that looks like for the location-authority gate:** the 4 live entries become `ContentDescriptor`s. For example, `rel_path="charter/activation/kind_vocabulary.py"`, `qualname="_org_scan_dirs"`, `token_substring="legacy = flat /"`. `SourceFile` already carries `.source` (`tests/architectural/conftest.py:38-43`), so L395 changes to `composite_key(entry.source, lineno) in allowlisted_keys`, keyed per file. **Drop the 2 dead entries.** Add a staleness twin using `descriptor_still_live`, mirroring kernel L245-259.

## 4. How this relates to #3206

- #3206 (P2, `status:triage`, design decision pending among 3 options) removes `_PRE_EXISTING_EXEMPTIONS` entirely. The issue text says lines 88/96; HEAD has **88/97** after the S2a relocation (docstring L110-126).
- Once the context gate is removed, those 2 tuples come into the ban's scope. **The ordering is independent**, so #5085 must not block on #3206. Recommended handling, in preference order:
  1. **Migrate the 2 tuples to `ContentDescriptor`** in #5085. This is cheap: `collect_forbidden_vocabulary` returns `(rel, lineno, detail)`, so key on `composite_key`. The file's existing staleness check keeps working. #3206 later deletes the descriptors instead of the tuples, which is a trivial textual conflict.
  2. Or list them in the ban's new enumerated exemption list with `rationale="retired by #3206"`, plus a drift guard that fails once the symbol disappears, so the exemption list shrinks itself.
- Either way, **rewrite ban L1086-1120**. Their premise (scope by context) is exactly the hole being closed. Post a coordination comment on #3206 noting that its acceptance line "remove the two entries" then also means "remove the descriptors / the exemption-list row".

## 5. Design

### 5a. Widening the predicate (all inside `test_ratchet_positional_anchor_ban.py`)

1. **Remove the context gate** in `_raw_file_line_tuple_seed_violations` (delete L571-572). Keep `_imports_ratchet_substrate` only if other code still needs it; otherwise delete it together with its test class, L862-879.
2. **Widen the path element:** `_is_pathish_path_element(node)` accepts a path-ish string literal, **or** a call to `Path`/`PurePath`/`PurePosixPath` (Name or Attribute callee) whose first argument is a path-ish string literal. Optional: a `/` BinOp whose leaves are all string literals.
3. **Add a new arm for embedded line-in-key strings:** a module-level seed container string (dict key or element) that matches `^<pathish>:\d+:<suffix>$`. Anchor it on the whole string so the prose evidence in §2b is not flagged. The prose strings contain `; ` and spaces, so a `\S+` whole-match excludes them. Keep this arm separate from `is_file_line_anchor` because the production registry uses that function.
4. **Enumerated exemptions:** add `_POSITIONAL_ANCHOR_EXEMPTIONS: tuple[tuple[str, str, str], ...]` of `(relpath, symbol, rationale+issue)`, matched by the module-level binding name, not by line. Add a drift test: each row's file and symbol still exist **and** still produce a finding. That makes the list shrink-only and non-vacuous, in the style of the existing FR-014 test at L722-737. The target at merge is an empty list, or at most the #3206 row.
5. **Failure message:** include the migration how-to. Point at the `ContentDescriptor` exemplar (`test_trio_seam_only.py:449`) and `contracts/descriptor-resolver.md`, and mention `# diagnostic-locator` for genuinely non-authoritative ints.

### 5b. Non-vacuity and self-mutation tests (new, in the same file)

- `test_widened_arm_flags_path_call_tuple_in_non_substrate_file`: plant `import ast\nfrom pathlib import Path\n_X: frozenset[tuple[Path,int]] = frozenset({(Path("src/a.py"), 12)})` and assert exactly 1 finding.
- `test_widened_arm_flags_str_int_tuple_in_non_substrate_file`: the #3206 shape, now **red** (this inverts L1086-1102).
- `test_embedded_line_key_arm_flags_path_line_op_string`: `_ALLOWLIST = {"src/x.py:98:reset_hard": "r"}` gives 1 finding.
- `test_embedded_line_key_arm_ignores_prose_evidence`: `{"cmd": "decision.py:401; empty stdout"}` gives 0 findings.
- `test_label_int_pair_still_green`: `("label", 3)` and `(Path-less, count)` give 0 findings. This guards against false positives.
- **Self-mutation:** monkeypatch the path predicate to `lambda n: False` and assert that the planted fixtures go green. That proves the arm is load-bearing, which is the NFR-004 discipline. Alternatively, reuse `drop_one_entry`-style shrink proofs.
- **Location-authority acceptance (triage AC2):** `test_location_allowlist_survives_blank_line_insertion`. Take the real `kind_vocabulary.py` source, insert `"\n"` above `_org_scan_dirs`, and assert that the gate's offender filter still returns `[]` for that file. Also add a staleness twin that fails when a descriptor resolves to zero or more than one live join.

### 5c. RED-first acceptance test

- **Name:** `test_no_positional_anchor_in_any_architectural_seed` (or strengthen the existing `test_no_int_line_sink_in_architectural_python_seeds`, L677-698, once the predicate is widened; it keeps its name and its assertion `not violations`).
- **File:** `tests/architectural/test_ratchet_positional_anchor_ban.py`.
- **Assertion:** after the widening, scanning the real tree yields `violations == []`, and there is no exemption row without an issue reference.
- **Confirmed red on HEAD:** `scratchpad/probe.py` ran the widened predicates through the real module's helpers. The baseline arms had 0 hits. The widened arms had **88 hits**:
  - `_KNOWN_JOIN_ALLOWLIST`: 6 rows (L181, 187, 213, 234, 255, 263)
  - kernel `_PRE_EXISTING_EXEMPTIONS`: 2 rows (L129, 130)
  - destructive `_ALLOWLIST`: 22 keys
  - mutation `_ALLOWLIST`: 56 keys
  - overwrite `_ALLOWLIST`: 2 keys

  If the `path:N:op` arm is deferred (see ambiguity Q1), the red set is 8.

### 5d. Migration plan per hit

| Hit | Plan |
|---|---|
| `_KNOWN_JOIN_ALLOWLIST` (6) | Convert the 4 live entries to `ContentDescriptor`, resolved at import time. **Delete** `kernel/paths.py:88` and `runtime/home.py:79` (dead). Add a staleness twin. Also delete the FRESHENED/RE-PINNED comment archaeology, since it becomes meaningless. |
| kernel `_PRE_EXISTING_EXEMPTIONS` (2) | `ContentDescriptor` (qualnames from `src/kernel/schema_utils.py` around L88/L97), or an exemption row naming #3206 (§4) |
| destructive/mutation/overwrite `_ALLOWLIST` (80) | Change the key builder from `f"{rel}:{lineno}:{op}"` to `f"{rel}::{qualname}::{token_line}::{op}"`, using `_destructive_op_census.enclosing_qualname` (already present) plus `code_tokens_by_line`. Then regenerate the 80 keys **mechanically** with a one-shot script and review them. Watch for **collisions**: two identical ops in the same qualname need an `occurrence` ordinal, or `ContentDescriptor`. `drop_one_entry` and `rsplit(":", 2)` (destructive L286, mutation L552, overwrite L360) must change to the new separator. |

### 5e. Blast-radius commands

```
.venv/bin/python -m pytest -q tests/architectural/test_ratchet_positional_anchor_ban.py \
  tests/architectural/test_built_in_location_authority.py tests/architectural/test_kernel_no_doctrine_import.py \
  tests/architectural/test_destructive_op_routing.py tests/architectural/test_mutation_ownership_routing.py \
  tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_trio_seam_only.py
.venv/bin/python -m pytest -q tests/specify_cli/contracts/          # anchoring/registry, if anchoring.py is touched
.venv/bin/python -m pytest -q tests/doctrine/test_built_in_location_authority.py
make test-fast
ruff check tests/architectural && ruff format --check tests/architectural
```

Run the full `tests/architectural/` suite **only** if a shared helper (`_destructive_op_census.py`, `_ratchet_keys.py`, `conftest.py`) changes. That helper is shared by several gates, which is the charter's cross-cutting criterion. The HEAD baseline for the 6 main files is 105 passed.

### 5f. WP-sized scope

- **WP01 (S):** widen the ban (context gate removed, `Path(...)` element, exemption list plus drift test, rewrite L862-879 and L1086-1120, add the fixtures in §5b). It stays red against HEAD until WP02 lands. Either land WP01 and WP02 in the same lane, or temporarily enumerate the hits as exemptions and shrink the list in WP02. **Do not** use `xfail`.
- **WP02 (S):** migrate `_KNOWN_JOIN_ALLOWLIST` (4 descriptors, drop 2 dead entries), add the staleness twin and the blank-line acceptance test, and migrate or enumerate the kernel exemption. This closes the issue as written.
- **WP03 (M), optional or separate:** add the `path:N:op` arm and migrate the 80 keys in the three destructive-census gates plus `_destructive_op_census.py`. It splits cleanly: one shared-helper change, then 3 per-gate migrations. It can land later behind a temporary enumerated exemption for the 3 symbols.

WP01 and WP02 are small, about 1 day. WP03 is mechanical but review-heavy, since 80 rationales must be re-keyed.

## 6. Operator ambiguities

1. **Is the `"rel:lineno:op"` string shape in scope?** It affects 80 keys across 3 gates. The issue title says "(Path, int)"; the triage comment says "every module-level allow-list", but only names tuple shapes. Options: include it (WP03), or file a sibling issue under epic #5104 and enumerate the 3 symbols as time-boxed exemptions.
2. **#3206 exemption:** migrate it to `ContentDescriptor` now, or keep it as an enumerated exemption until #3206 lands? I recommend migrating.
3. **Scan universe:** `tests/architectural/` only (as proposed), or also other gate-like directories? The sweep found nothing module-level outside it except the dormant `tests/runtime/_bridge_oracle.py:602`.
4. **YAML arm:** should it also widen to every YAML/JSON seed under `tests/architectural/`? That would reach `census/spec_kitty_home_pin_anchor.yaml` `lineno` (40 generated, SHA-pinned rows). I recommend keeping it out of scope and noting it.
5. **The 2 dead entries:** delete them silently as part of the migration, or record them as a separate finding? They are latent wildcards, not only line-drift friction.
6. **Key granularity for the census gates:** `(rel, qualname, token_line, op)` vs `ContentDescriptor`. The composite string is cheaper and fits `diff_against_allowlist`; `ContentDescriptor` gives the import-time uniqueness check.
