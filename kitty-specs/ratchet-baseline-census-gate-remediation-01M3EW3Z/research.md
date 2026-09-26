# Phase 0 design research: ratchet, baseline and census gate remediation

Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z` · spec rev 2 · HEAD `3717c7ea`
Author: Architect Alphonso (read-only; no repo edits). Scratch probes live in this `squad/` directory:
`ban_probe.py`, `census_probe.py`, `census_rekey.py` (+ `census-rekey-map.csv`), `dirty_probe.py`,
`fr015_probe*.py`.

## 0. Governance applied

- **Profile `architect-alphonso`.** I designed and decided, and wrote no implementation code. Every decision
  below records its rationale and the alternatives I rejected (success definition: decisions traceable to FRs
  and actionable by implementers). Handoff goes to the planner and implementers.
- **Directives (profile refs 001, 003, 031, 032, 041, 043, 044, 051, plus the charter plan set).**
  - DIR-041 (content anchoring, never line anchoring) drives areas A–C.
  - DIRECTIVE_044 (single authority) drives C-004's unification of the census qualname.
  - DIRECTIVE_043 (floors and non-vacuity) drives the NFR-002 floors and self-mutation design.
  - DIRECTIVE_003 (decision records) sets the format of this document.
- **Charter Standing Orders applied:**
  - #4: red-first. Every WP names a behavioural RED on the planning base, and no tombstone tests.
  - #5: architectural-gate non-vacuity. Every ban gets a floor and self-mutation through the real scan function.
  - #6: canonical sources. I reused the `_ratchet_keys` substrate and the #2620 tracer catalog format.
  - #7: git discipline. Pyproject and baseline hotspots are sequenced.
  - #8: mission hygiene. The issue matrix and follow-ups are handled.
  - I also applied RECONCILE_CHANGE_SCOPE_TENSIONS (campsite work only on touched files) and C-011 ATDD-first.
- **Tactics.** `dependency-hygiene` shaped the WP dependency graph. `development-bdd` gave each WP its acceptance test as a Given/When/Then.
- **Canonical-source check.** I re-derived every count on HEAD rather than trusting the grounding. Where the
  grounding or spec was wrong, §8 records it as an erratum.

---

## A. Positional-anchor ban widening (FR-001..FR-003, NFR-002, NFR-004)

### A1. Where the widened predicate lives
**Decision.** The predicate lives entirely in `tests/architectural/test_ratchet_positional_anchor_ban.py`. It is a new test-local predicate family. Do not touch `specify_cli.contracts.anchoring.is_file_line_anchor`.

**Rationale.**
- `is_file_line_anchor` (`src/specify_cli/contracts/anchoring.py:295-316`) is production code.
- It is consumed by the Contract Registry validator (`src/specify_cli/contracts/registry.py:297,328`), re-exported by `src/specify_cli/contracts/__init__.py:30`, and pinned by `tests/specify_cli/contracts/test_registry.py:181-183`.
- Widening it to accept the `path:N:op` suffix changes registry validation, which breaches C-005.
- FR-002 already says "predicate owned by the ban's test module".

**Alternatives rejected.**
- A new `src/` helper, rejected by C-005.
- A shared `tests/architectural/_positional_anchor_predicates.py`, which adds a module with a single consumer (YAGNI). Only the ban and its own tests call it.

### A2. Scan restructuring (exact edits)
The walker `_iter_architectural_python_files` (L615-624) already sees every `tests/architectural/**/*.py`. The holes are in the arms, not the walker. Edits:

1. **Remove the context gate.**
   - Delete L571-572 (`if not _imports_ratchet_substrate(tree): return []`) in `_raw_file_line_tuple_seed_violations` (L559-592).
   - Delete `_imports_ratchet_substrate` (L512-529), `_RATCHET_SUBSTRATE_MODULES` and `_RATCHET_SUBSTRATE_NAMES` (L117-130). They have no other consumer.
   - Rewrite the module docstring paragraph at L33-50, which documents the scoping as intent.
2. **Widen the path element.** Add `_is_pathish_element(node)`. It accepts:
   - a path-ish str literal (the existing `_is_pathish_string_literal`, L532-545);
   - `Path|PurePath|PurePosixPath|PureWindowsPath(<pathish>)`, with a Name or Attribute callee resolved through the existing `_call_func_name` (L190);
   - a `/` `BinOp` with any path-ish leaf.
3. **Widen the tuple shape.**
   - Replace `_is_raw_file_line_tuple` (L548-556) with `_is_file_line_tuple(node)`: an `ast.Tuple` with ≥2 elts, `_is_pathish_element(elts[0])`, and any later elt a bare int literal (`type(value) is int`, which excludes bool).
   - This covers `(path, int)`, `(Path(...), int)` and `(path, qualname, int)`.
   - The detail string must stop assuming `path_node`/`line_node` are `Constant`s (L583-584). Use `ast.unparse(node)`.
4. **New embedded-key arm.** `_seed_embedded_line_key_violations` flags any str constant in a seed container that whole-matches
   `_EMBEDDED_LINE_KEY_RE = re.compile(r"^(?:[A-Z]+:)?[^\s:]+\.[A-Za-z0-9]+:\d+(?::\S*)?$")`.
   - Whole-string anchoring and `\S` keep prose evidence green, for example `"decision.py:401; empty stdout"` (`test_json_contract_enumeration.py:217/231`).
   - This arm subsumes the old `is_file_line_anchor` arm (`_seed_string_line_anchor_violations`, L329-349). Keep the old arm too; it is cheap and it pins the registry-predicate parity. I recommend the replacement only if review asks for less surface.
5. **New keyword-record arm.** Flag a `Call` in a seed container that carries a keyword in `{"line","lineno","line_no","file_line","fileline"}` bound to an int literal.
   - This mirrors `FORBIDDEN_POSITIONAL_FIELDS` (`anchoring.py:285-287`).
   - `occurrence=` is deliberately absent, per the module docstring's FR-014 carve-out.
6. **Class-body seeds.** Extend `_module_level_seed_containers` (L279-298) to also walk each `ClassDef.body`, so a class-attribute allowlist cannot evade the ban.
7. **Text arm (FR-001, exemption text files).**
   - Add `_iter_architectural_text_files()`, which returns `sorted(_ARCH_ROOT.rglob("*.txt"))` (20 files on HEAD).
   - Add `_scan_text_source(text, relpath)`, which flags every non-blank, non-`#` line that whole-matches `_EMBEDDED_LINE_KEY_RE`. The optional `[A-Z]+:` prefix catches the clock gate's `CALL:<path>:<line>` shape (`_exemptions/__init__.py:62-70`).
8. **Wire it together.**
   - `_scan_python_source` (L595-607) composes the six arms.
   - The standing gate `test_no_int_line_sink_in_architectural_python_seeds` (L677-698) keeps its name and assertion.
   - A sibling `test_no_positional_anchor_in_architectural_text_files` runs the text arm.
   - Both filter findings through the FR-003 exemption set (A4).
9. **Explicitly out of scope.** Record these in the docstring, each with a negative fixture:
   - `{path: int}` dicts. The probe flagged 13 false positives in `test_timing_coverage_invariant.py::BASELINE_FUNCTIONAL_ASSERTIONS`, where the ints are counts.
   - Function-local containers.
   - The two SHA-pinned or non-authoritative YAMLs: `census/spec_kitty_home_pin_anchor.yaml` and `charter_path_literal_allowlist.yaml`.
   - The dormant `tests/runtime/_bridge_oracle.py:602`, which is outside the scan universe.

   Renata's `"x.py#L12"` shape has 0 occurrences; add it only if it appears.

**Probe evidence** (`squad/ban_probe.py`, run through the real ban helpers on HEAD, 1.42 s):

| file | symbol | arm | hits |
|---|---|---|---:|
| test_built_in_location_authority.py | `_KNOWN_JOIN_ALLOWLIST` | tuple (`Path(...)`) | 6 |
| test_kernel_no_doctrine_import.py | `_PRE_EXISTING_EXEMPTIONS` | tuple | 2 |
| test_destructive_op_routing.py | `_ALLOWLIST` | embedded | 22 |
| test_mutation_ownership_routing.py | `_ALLOWLIST` | embedded | 56 |
| test_overwrite_ownership_routing.py | `_ALLOWLIST` | embedded | 2 |
| `_exemptions/os-detect-ban-{deferred,mypy-narrowing,sanctioned-raw}.txt` | lines | text | 3+2+1 |
| **total** | | | **94** |

There were no other hits once the dict arm was excluded. The 94-row RED is real, and the per-symbol breakdown (6/2/22/56/2/6) must be what the RED commit prints. Do not assert a hard-coded constant (Renata LOW).

### A3. Existing tests that are inverted, not deleted (FR-001, tactic `delete-the-assertion-not-the-test`)
| HEAD test | Becomes |
|---|---|
| `TestImportsRatchetSubstrate` (L862-879, 4 tests) | `TestFileLineTupleArmIsImportAgnostic`. Same 4 import-shaped fixtures, each now carrying a `("x.py", 12)` seed. All 4 assert ≥1 finding. `test_ignores_non_substrate_file` becomes `test_flags_raw_tuple_in_non_substrate_file` (the inversion). |
| `TestIsRawFileLineTuple.test_rejects_three_tuple` (L906) | `test_flags_path_qualname_int_three_tuple`, same literal, inverted |
| `test_ct7_raw_tuple_in_non_substrate_file_stays_green` (L1086-1102) | `test_ct7_raw_tuple_in_non_substrate_file_is_flagged`, same fixture, asserts 2 findings |
| `test_ct7_real_3206_import_lineno_exemption_stays_green` (L1105-1120) | `test_real_kernel_gate_has_no_unexempted_line_pin`. It scans the real `test_kernel_no_doctrine_import.py` and asserts that its findings are all covered by FR-003 rows. Interim: 2 findings, both exempted. After the FR-005 WP: `[]`. |

New fixtures, each calling `_scan_python_source` or `_scan_text_source`, which are the functions the standing gate calls:
- `Path("src/a.py"), 12` tuple, flagged;
- `Path("a") / "b.py"`, flagged;
- class-attribute allowlist, flagged;
- `Entry(path="a.py", lineno=3)`, flagged;
- `{"src/x.py:98:reset_hard": "r"}`, flagged;
- `CALL:src/x.py:12` text line, flagged;
- negatives stay green: `("label", 3)`, `{"cmd": "decision.py:401; empty stdout"}`, a `ContentDescriptor(..., occurrence=0, ...)` call, a `CensusKey(..., occurrence=1)` call, the `BASELINE_FUNCTIONAL_ASSERTIONS` shape, and a `path::qualname::op#0` string.

### A4. FR-003 per-site exemption list
**Decision.** `_POSITIONAL_ANCHOR_EXEMPTIONS: frozenset[tuple[str, str, str, str]]` holds rows of `(relpath, symbol_or_txt_filename, site_literal, reason)`.
- `site_literal` is `ast.unparse(node)` for a Python site, or the stripped line for a text site.
- The row therefore names **one site by content**, not a line.
- The list lives in the ban module. The ban excludes its own file from its own scan (`_GUARD_FILE`, L103, L615-624), so the rows cannot self-flag.

**Lifecycle.** This design relies on the mission landing as one PR (C-006), so interim states never reach `main`.
1. **Ban WP (interim).** The first commit carries the widened arms with an empty list: RED, 94 findings. The second commit adds the 94 per-site rows (reason: `"#5085 interim — migrated by WPxx"`), giving GREEN.
   - `test_positional_anchor_exemptions_are_exact`: the set of live findings covered by a row must equal the set of rows whose site still produces a finding. A finding with no row FAILS (growth). A row with no finding only **warns** during the interim, so migration WPs can land in parallel without editing the ban file.
2. **Closeout WP.**
   - Deletes every row and pins `assert _POSITIONAL_ANCHOR_EXEMPTIONS == frozenset()` (exact-set equality, FR-003 / SC-001).
   - Flips the row-without-finding path from warn to **fail**, keeping the generic check for any future row.
   - Its RED-first is exactly this pin: RED while 94 rows remain.

**Alternatives rejected.**
- Symbol-granular rows, 5 rows exempting 88 sites (Renata CRITICAL: unbounded).
- `(relpath, symbol, site_count)` rows: bounded, but not "per-site" as FR-003 words it.
- Ordering the ban WP last: its first commit would be green on its lane base, which breaks C-001.
- Letting every migration WP edit the ban file: this violates single-file ownership and forces 5-way sequencing.

### A5. Floors and self-mutation (NFR-002)
Floors use the planning-base count minus retirements. Deleting `rekey_inventory.py` removes 1 file.
- Python files scanned ≥ **262** (263 on HEAD). This replaces `> 50` at L668-674.
- Text files scanned ≥ **20**.
- Exemption-file entry lines inspected ≥ **6**. The os-detect entries survive as content lines.

Load-bearing proofs:
- There is one test per arm (tuple, embedded, keyword, text). Each monkeypatches that arm's predicate to always-False, and the planted fixture then yields 0. This proves the real scan path uses the arm.
- The existing planted tests L945-1066 stay.

NFR-004 is measured, not asserted: take `pytest --durations=0` on the ban file and record it in the PR (1.4 s on the probe; no wall-clock assertion, per the flakiness policy).

### A6. YAML arm
`_YAML_ALLOWLISTS` (L140-143) loses `resolution_gate_allowlist.yaml` in the closeout WP, together with the file deletion (FR-012; see E3). Add a floor, `len(_YAML_ALLOWLISTS) >= 1`, to `test_non_vacuity_real_compliant_yamls_stay_green` (L1137).

---

## B. Content-identity migration of hand-curated allowlists (FR-004, FR-005, FR-007, os-detect)

### B1. The shared substrate usage
**Decision.** Add one small test helper, `tests/architectural/_content_identity.py`. It declares `__all__` (charter C-007). It is owned by the join WP (the first consumer) and depends only on `_ratchet_keys`:

```python
def resolve_allowlist(descriptors: Iterable[ContentDescriptor], source_for: Callable[[str], str]
                      ) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]
    # resolved multiset + [(descriptor, reason)] for DescriptorResolutionError (0 or >1 candidates)
def partition_findings(findings: Iterable[tuple[CompositeKey, T]], allowed: Counter[CompositeKey]
                       ) -> tuple[list[T], Counter[CompositeKey]]
    # (unexpected, unused) — MULTISET: one entry suppresses at most one finding with that key
def with_blank_line_at_top(source: str) -> str
def with_probe_above_statement(source: str, lineno: int) -> str
    # inserts "# drift-probe\n<indent>pass\n" above the innermost ast.stmt containing lineno,
    # at that statement's col_offset (safe inside multi-line expressions)
```

**Why a multiset.** `composite_key` strips strings, so identical token lines collide.
- Probe: `neutrality/lint.py:379` and `:380` both tokenize to `roots . extend ( _iter_mission_scan_roots ( repo_root / / / ) )` inside `_default_scan_roots`.
- A set-based match would let the one allowlisted entry also bless a future `"built-in"` join on line 380.
- A `Counter` closes this widening hole (Renata HIGH).

**Stale rule (FR-007).** An entry is stale if either:
- (a) it fails `resolve_descriptor`'s exactly-one rule (`_ratchet_keys.py:223-234`); or
- (b) its resolved key is not the key of a live finding, i.e. it suppresses nothing. This is `unused` above, and it is stronger than `descriptor_still_live`, which only checks resolution.

The stale test also asserts `checked == len(allowlist) >= <floor>`, so it cannot pass vacuously over an empty list.

**Keying includes `rel_path`.** The exemplar `test_trio_seam_only.py:533-547` narrows keys to `(qualname, token_line)` without `rel_path`. This design keeps the full `CompositeKey`, so identical qualname and token pairs in two files cannot cross-bless.

**Alternatives rejected.**
- Import-time `resolve_descriptor` (the exemplar pattern, `test_trio_seam_only.py:528-530`). A stale entry then becomes a collection error that takes out the whole module, instead of a named failing test. Instead, resolve lazily inside a `functools.cache`d accessor.
- Per-gate copy-paste of the partition logic, which violates DIRECTIVE_044.

### B2. `_KNOWN_JOIN_ALLOWLIST` (`test_built_in_location_authority.py:138-265`)
New shape: `_KNOWN_JOIN_SITES: tuple[ContentDescriptor, ...]`. It has 4 entries; the 2 dead ones (`kernel/paths.py:88`, `runtime/home.py:79`) are deleted. The FRESHENED and RE-PINNED comment archaeology (L143-262) collapses into the rationale fields. Resolution was verified with `_candidate_lines` on HEAD:

| rel_path | qualname | token_substring | occurrence |
|---|---|---|---|
| `src/charter/activation/kind_vocabulary.py` | `_org_scan_dirs` | `legacy = flat /` | None |
| `src/charter/activation/neutrality/lint.py` | `_default_scan_roots` | `_iter_mission_scan_roots ( repo_root / / /` | **0** (lines 379 and 380 are token-identical) |
| `src/specify_cli/template/manager.py` | `copy_specify_base_from_local` | `missions_src = repo_root /` | None |
| `src/specify_cli/template/manager.py` | `get_local_repo_root._is_template_root` | `return ( path /` | None |

- **Matching.** `test_no_builtin_path_joins_outside_pack_paths_authority` (L371-399) builds its findings as `((rel, *composite_key(entry.source, lineno)), lineno)` from `src_source_tree` (`SourceFile.source`, `conftest.py:38-43`). It replaces L395's `(rel, lineno) not in _KNOWN_JOIN_ALLOWLIST` with `partition_findings`.
- **Tests:**
  - `test_join_allowlist_entries_each_suppress_a_live_join` (FR-007, fail). RED on base, because 2 entries are dead.
  - `test_join_allowlist_survives_line_drift` (NFR-001; see B5).
  - `test_new_join_at_formerly_pinned_line_is_caught`. It inserts a `root / "built-in"` join into `src/kernel/paths.py` source at old line 88, in memory, and asserts the gate reports it (Renata LOW).
- The module docstring at L107-110 ("allowlisted by exact (file, lineno)") is rewritten.

### B3. Kernel `_PRE_EXISTING_EXEMPTIONS` (`test_kernel_no_doctrine_import.py:127-132`)
Refactor `_scan_file(path, relative_to)` (L182-199) into `_scan_source(source, rel)` plus a thin path wrapper, so drift probes run in memory. `collect_forbidden_vocabulary`'s public signature is unchanged.

New `_PRE_EXISTING_EXEMPTIONS: tuple[ContentDescriptor, ...]`, with `rel_path` in the gate's src-relative form (`kernel/schema_utils.py`):

| qualname | token_substring | resolves to |
|---|---|---|
| `_resolve_schema_path` | `files (` | L88 `resource = files ( )` |
| `_resolve_schema_path` | `parent . parent / / /` | L97 |

Changes:
- `test_kernel_holds_no_doctrine_or_specify_cli_vocabulary` (L214-234) uses `partition_findings`.
- `test_pre_existing_exemption_is_still_a_real_violation` (L244-259) keeps its name (inverted-not-deleted) and now asserts `unused == Counter()` and that all resolve.
- The #3206 coordination comment: #3206's AC "remove the two entries" becomes "delete the two descriptors". This is order-independent.

### B4. os-detect exemptions (`_os_detection_exemptions.py`, `_exemptions/os-detect-ban-*.txt`)
**New line shape:** `<repo-rel path>::<qualname>::<token_substring>[::<occurrence>]`.
- Parse with `split("::", 3)`. The token substrings may contain `:` (e.g. `if sys . platform == :`) but never `::`.
- `load_os_detection_exemptions() -> frozenset[ContentDescriptor]`. The rationale is the source filename, so the per-owner-file semantics are kept.
- The 6 rows, all verified to resolve uniquely:

| file | rel_path | qualname | token_substring |
|---|---|---|---|
| deferred | `src/specify_cli/__init__.py` | `ensure_executable_scripts` | `if os . name ==` |
| deferred | `src/specify_cli/__init__.py` | `main` | `if sys . platform ==` |
| deferred | `src/specify_cli/paths/windows_paths.py` | `_current_platform` | `sys . platform . startswith (` |
| mypy-narrowing | `src/kernel/locks.py` | `_os_lock` | `if sys . platform ==` |
| mypy-narrowing | `src/kernel/locks.py` | `_os_unlock` | `if sys . platform ==` |
| sanctioned-raw | `src/kernel/locks.py` | `<module>` | `if sys . platform ==` |

Gate changes in `test_os_detection_ban.py`:
- `collect_violations` (L49-55) gains a keyed variant. `test_no_banned_os_detection_outside_the_door` (L80-103) partitions by `CompositeKey`, and its failure message (L100-101) now prints the content line to add.
- `test_every_exemption_entry_is_a_real_violation` (L106-117) stays fail-on-stale (FR-007) using `unused`.
- `test_stale_exemption_removal_reds_the_gate` (L120-163) is inverted, not deleted. It writes the planted exemption in the new content shape (`offender.py::<module>::if sys . platform ==`) and keeps both directions.
- The re-pin archaeology comments in the three `.txt` files are deleted.
- `_lock_ban_exemptions.py` and the clock `CALL:` loader keep their line shape at **0 entries**. The widened text arm now refuses any future line-pinned entry, so both gates are shrink-only at zero. Record this in the tracer, with a note that any future need gets the same content shape.

### B5. Drift test (NFR-001, SC-002), per gate
Each migrated gate owns `test_<gate>_survives_line_drift`, parametrized over **every distinct file its allowlist references**. The parameter count is asserted equal to that set: join 3, kernel 1, os-detect 3, destructive 17, overwrite 2, mutation 23, so the total is **49 files** (derivable from `census-rekey-map.csv` plus B2–B4). For each file, and for mutations (i) `with_blank_line_at_top` and (ii) `with_probe_above_statement` at every exempted site:
- recompute the gate's `(unexpected, suppressed)` identity sets through the gate's **real** key and partition functions;
- assert both sets are identical to the unmutated run (not just "still green").

These are the RED-first tests of each migration WP. On base, line-keyed matching loses every suppressed site under mutation (i).

Alternative rejected: one cross-gate `test_allowlist_drift_tolerance.py`. It would be owned by the closeout WP, which removes red-first from the migration WPs and forces a shared hotspot.

---

## C. Census migration (FR-006, C-004, collisions)

### C1. Key design
**Decision.** Identity is `CensusKey(NamedTuple)` with fields `rel`, `qualname`, `token_line`, `op` and `occurrence`.
- `(qualname, token_line)` comes from `_ratchet_keys.composite_key(source, lineno)`, the canonical substrate.
- `occurrence` is the 0-based ordinal among live findings that share `(rel, qualname, token_line, op)`, ordered by `lineno` (AST source order).

**Rationale.**
- The spec's Key Entities defines identity as "path + qualname + token + occurrence". This is that, built from `composite_key`, which is exactly C-004.
- The `(qualname, op)`-only alternative collides heavily: 28 of 80 entries fall into 11 groups. The token line absorbs almost all of that: re-derived on HEAD (`census_rekey.py`), only **3 of 80** entries need `occurrence=1`:
  - `lanes/merge.py::_merge_branch_into` `merge_abort` (L1199);
  - `m_0_10_8_fix_memory_structure.py::FixMemoryStructureMigration.apply` `wt_memory . unlink ( )` (L205);
  - the same function's `wt_agents . unlink ( )` (L230).
- The key is drift-stable because line shifts change neither qualname nor tokens nor relative order.
- It is **not widening**:
  - adding a second identical op in an exempted function yields a new key (`occurrence` +1), so the gate FAILS;
  - editing an exempted op's arguments changes `token_line`, so the old key goes stale (warn) and the new key is unexpected (FAIL).

**Known weakness (documented, accepted).**
- Tokens strip strings, so argv lists tokenize thinly (e.g. `"[ , , ] ,"`).
- Deleting an earlier same-key op shifts ordinals, so a rationale can re-attach to its twin. Both sites were exempted anyway, and the census stays warn-on-stale.

**Rendering.**
- Allowlist literals use keyword form: `CensusKey(rel="…", qualname="…", token_line="…", op="…", occurrence=0): "rationale"`. Keywords keep the rows readable and are safe under the A2 keyword arm (`occurrence` is not a line keyword).
- The failure message shows `rel::qualname::op#occ (line N) tokens=…`. The line number is diagnostic only.

**Alternatives rejected.**
- `rel::qualname::op#ordinal` strings with no token. This drifts on nothing, but silently keeps blessing a changed argument, and it contradicts the Key Entities definition.
- `ContentDescriptor`s resolved per entry. `resolve_descriptor` returns a `CompositeKey` without the occurrence, so same-token twins collapse. Resolving at import would also turn a vanished site into a hard error, breaking the documented census warn-on-stale contract.

### C2. `_destructive_op_census.py` changes (shared helper → full `tests/architectural/` run)
- **Delete** the tree-based `enclosing_qualname` (L148-180). It is a second qualname algorithm (C-004).
  - Re-export `enclosing_qualname` from `_ratchet_keys` (signature `(source, lineno)`).
  - Probes: all 80 census sites plus all 10 dirty-predicate sites resolve **identically** under both algorithms (`census_probe.py`, `dirty_probe.py`). Unification is behaviour-preserving on HEAD.
- **Add** `parse_with_source(path) -> tuple[str, ast.Module] | None`. Keep `parse`.
- **Add** `CensusKey` and `census_keys(rel, source, hits: Iterable[tuple[int, str]]) -> dict[CensusKey, int]` (key → lineno, used for diagnostics).
- **Generalize** `diff_against_allowlist` (L189-200) and `drop_one_entry` (L214-221) over `Hashable` keys (`TypeVar K`). Keep the WARN-on-stale docstring (L14-18, L195-197) unchanged. Add one sentence explaining why content keys make warn-on-stale safe: a dead content key cannot re-bind to a new site.
- **Call sites** (8 key builders and parse sites):

| file | site | change |
|---|---|---|
| destructive | `_flatten` L146-147 | `census_keys` over each file's source |
| destructive | `rsplit(":", 2)` L286 | `{k.rel for k in _ALLOWLIST}` |
| destructive | `_status_porcelain_hits` L349-362 | `enclosing_qualname(source, lineno)` via `parse_with_source` (`_KNOWN_DIRTY_PREDICATES` unchanged) |
| mutation | `_flatten` L227-228; research-prefix check L526-546 (`key.rel.startswith`); `rsplit` L552; literal re-builder L641; diagnostics test L771-779 | as above |
| overwrite | `_flatten` L255-256; `rsplit` L360; re-builder L436; diagnostics test L612-620 | as above |

- `destructive_op_allowlist: 56` (`_baselines.yaml`, registered as `len(test_mutation_ownership_routing._ALLOWLIST)`, `test_ratchet_baselines.py:465-469/627-631`) is **unchanged**. The mapping is 1:1 per site, so all 56 keys stay distinct. The census WPs are forbidden to touch `_baselines.yaml`.
- **Stale policy stays WARN** (FR-007, the census half). The spec's resolution of Debbie's and Priti's flag is recorded in the tracer.

### C3. Mapping artefact and equivalence proof
- **Artefact.** `kitty-specs/<mission>/census-rekey-map.csv`, with columns `gate, old_key, rel, qualname, token_line, op, occurrence, rationale_sha256`. 80 rows; the prototype is `squad/census-rekey-map.csv`.
- **Proof.** `kitty-specs/<mission>/research/census_rekey_equivalence.py`. It is a mission artefact, excluded from ruff via `ruff.toml` `kitty-specs/*/research/**`, and is **not** a committed test: a test would have to hold the 80 old line keys, which the widened ban forbids.
  1. At the planning-base SHA, load the old `_ALLOWLIST`s via `git show <base>:<file>` and compute the old exempted site set `{(rel, lineno)}`.
  2. At the WP head, resolve every new `CensusKey` through `census_keys` over live source to `(rel, lineno)`.
  3. Assert the sets are equal, that the mapping is a bijection, and that `rationale_sha256` matches per site.

  C-005 guarantees `src/` is byte-identical, so `(rel, lineno)` is a valid shared site identity across the two SHAs. The command and output go in the PR and the tracer.
- **Mutation proof (Renata HIGH).** Plant a duplicate of an exempted op into an in-memory copy of an exempted function and assert the gate FAILS. Plant a changed argument and assert FAIL plus a stale warning.

---

## D. Baseline enforcement (FR-011) and inert-slot retirement (FR-010, #3962)

### D1. Current structure
- `test_growing_an_allowlist_above_baseline_fails` (L328-486) and `test_growth_fails_shrinkage_warns` (L489-651) each hold a **local, duplicated** comparison table:
  - `per_category_attrs` (L342-350 and L507-515);
  - `single_baselines` (L365-467 and L530-630), 13 rows.
- `test_no_unregistered_baseline_keys_are_added` (L654-690) checks top-level keys only.
- `_baselines.yaml` has 23 leaves. Comparison-consumed: 21. Of those, `category_1` (L43) is derived via `_category_baseline` (L190-202), so its growth arm is a no-op, and `skip_marker_blocks` (L237) is advisory via `record_property` (L205-240). Read by nothing: `unassigned_entries` (L284) and `masking_suppressions` (L298).

**New finding.** `category_1` is not really decorative. `test_decorative_category_1_yaml_matches_frozenset` (L712-725) pins YAML == `len(frozenset)` by equality. So every new auto-discovered migration still reds the suite, meaning the FR-004 "toll drain" of mission `frozen-baseline-toll-reduction` never actually removed the toll.

### D2. Derive the enforced leaves from the comparison table
**Decision.** Hoist the two local tables into **one** module-level table that both arms iterate:

```python
@dataclass(frozen=True)
class _SizeRatchet:
    section: str; leaf: str; module: str; attr: str
_SIZE_RATCHETS: tuple[_SizeRatchet, ...] = (... 6 no-dead-module categories (2..7) + 13 single rows ...)
_REQUIRED_TOP_LEVEL_KEYS = frozenset(r.section for r in _SIZE_RATCHETS)  # derived, was hand list L125-140
```

- The growth arm (`current > yaml[section][leaf]` gives a failure) and the shrink arm iterate `_SIZE_RATCHETS`. This removes the "register in BOTH lists" drift hazard that L668 and L688 warn about.
- `_enforced_leaves() = {(r.section, r.leaf) for r in _SIZE_RATCHETS}`.
- A leaf is **enforced** iff it has a row here. By construction, every row is compared by the growth arm with a failing `>`, which is the FR-011 definition.
- `_yaml_leaves(data) = {(top, sub) for top, sec in data.items() for sub in sec}`. Also assert that every top-level value is a mapping.

**New tests:**
1. `test_every_baseline_leaf_is_enforced_by_a_size_ratchet`: `_yaml_leaves(data) == _enforced_leaves()`, both directions, with a message naming the unenforced and the missing leaves.
   - **RED-first on base.** The first commit hoists the tables without changing behaviour and flags derived or advisory rows as non-enforcing. It names exactly `test_no_dead_modules.category_1_auto_discovered_migrations`, `test_example_round_trip.skip_marker_blocks`, `test_no_inert_schema_slots.unassigned_entries` and `test_no_inert_schema_slots.masking_suppressions`.
2. `test_leaf_drift_detects_planted_unenforced_leaf`: a synthetic dict with an extra leaf, run through the same `_leaf_drift` pure helper, yields exactly that leaf (self-mutation).
3. `test_lowering_an_enforced_leaf_below_live_fails` (US2-AS4), parametrized over `_SIZE_RATCHETS` (19 ids, with a floor of `len(_SIZE_RATCHETS) >= 19`):
   - monkeypatch `_load_baselines` to return a deep copy with that leaf set to `live - 1`, then assert `test_growing_an_allowlist_above_baseline_fails()` raises and names `attr`;
   - for `known_ungated_files` (live 0), inflate the attr to `_synthetic_frozenset(leaf + 1)` instead;
   - this proves each row reads *its* leaf.

**Alternative rejected.** A hand-maintained `(top, sub)` registry, the extension Priti suggested for `_REQUIRED_TOP_LEVEL_KEYS`. It is satisfiable by listing the dead keys (Renata CRITICAL fake (b)).

### D3. `category_1` and `skip_marker_blocks`: remove (recommended)
- **`category_1`.** Delete:
  - the YAML leaf (L43);
  - `category_1` from `_REQUIRED_NO_DEAD_MODULES_CATEGORIES` (L154-165);
  - `_CATEGORY_1_YAML_KEY` and `_CATEGORY_1_ATTR` (L180-181) and `_category_baseline`;
  - `test_decorative_category_1_yaml_matches_frozenset`, `test_category_1_derived_baseline_absorbs_growth` and `test_category_1_derived_baseline_absorbs_shrink` (L712-770).

  NFR-006 surviving enforcer: `test_no_dead_modules.py::test_no_new_dead_modules_under_src` (L788) fails on any unlisted importer-less migration. Growth of `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS` is therefore already a visible diff. The size pin was a pure double charge. Mutation proof: add a synthetic importer-less migration module name to the scan in a tmp copy, and the survivor reds.
- **`skip_marker_blocks`.** Delete:
  - the YAML leaf (L237);
  - `_emit_skip_marker_delta` and `_SKIP_MARKER_*_PROP` (L186-240);
  - `test_skip_marker_growth_is_recorded_not_failed`, `test_skip_marker_shrink_is_recorded` and `test_skip_marker_live_count_never_blocks` (L887-935).

  Surviving enforcer: the per-block `_SKIP_MARKER_RE` gate in `tests/contract/test_example_round_trip.py`. The docstring at L219-226 itself calls the count "intentionally NOT machine-enforced". Edit only the comment at `tests/contract/test_example_round_trip.py:584-587`. Keep `_SKIP_MARKED_BLOCKS` and its self-test at `:803-808`.

**Alternative.** Make them enforcing: register `category_1` with equality, or re-add the `skip_marker_blocks` hard fail. This restores tolls that two prior missions deliberately drained, against epic #5104. Rejected.

After this WP, `_baselines.yaml` has **19 leaves**, and `_REQUIRED_TOP_LEVEL_KEYS` derives to the same 12 sections. The `BaselinesFile` pydantic fields (L113-116) still hold.

### D4. Inert-slot retirement: exact deletions
- **`_inert_slots.py`** (791 lines; about -330). Delete:
  - `ALLOWLIST` (L73) and its use at L348;
  - `UNASSIGNED_OWNER`, `_MISSION_OWNER_PREFIX`, `_MISSIONS_DIR`, `_EVENT_LOG` (L416-419);
  - `MAX_UNASSIGNED_ENTRIES` (L419-431);
  - `COMPLETED_LANES` (L456-460);
  - `_mission_exists`, `_mission_work_packages`, `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners` (L557-633);
  - `CODE_ONLY_VERDICTS`, `_GENUINE_PRODUCER`, `MAX_MASKING_SUPPRESSIONS` (L644-664);
  - `_CODE_ONLY_KEY`, `CodeOnlySuppression`, `_parse_code_only`, `load_code_only_record`, `code_only_drift`, `CODE_ONLY_SUPPRESSIONS` (L666-753);
  - `find_code_only_suppressions` and `code_producer_writes` (L364-407);
  - `MINIMUM_*_BASELINE_ENTRIES_STILL_FOUND` (L790-791);
  - `BaselineEntry.owner` and `.provisional`; `Baseline.mission`; the provisional rule in `_parse_entry` (L509-515);
  - `from specify_cli.status.reducer import materialize_snapshot` (L35);
  - the matching `__all__` rows (L37-71).
- **Keep and wire `MINIMUM_SCHEMA_SLOT_NAMES = 150` and `MINIMUM_MODEL_SLOT_NAMES = 120`** (live: 176 and 138). Add `test_live_scan_meets_per_walk_floors` using `scanned_slots` and `is_schema_declared`. This replaces the weak `assert found` (`test_no_inert_schema_slots.py:64`) with calibrated floors: charter §5 non-vacuity at no new-machinery cost.
- **`_inert_slots_baseline.yaml`.** Delete:
  - top-level `mission:`;
  - `owner:` and `provisional:` from all 38 rows;
  - rows `styleguide-references` and `model` (both `agent-profile.schema.yaml`; verified cleared on HEAD), leaving **36 rows**;
  - the `code_only_suppressions:` section (from about L376);
  - the header prose at L30 and L70 and the L429 comment.
- **`_baselines.yaml`.** Set `baseline_entries: 38 → 36` with a justification. Delete `unassigned_entries` and `masking_suppressions` and their comment blocks (L279-298), and fix the stale L265 comment.
- Fix the prose at `test_reference_enum_ratchet.py:192`.
- Keep the name `test_live_tree_has_no_new_inert_slots`, which is referenced by `test_gate_remedy_presence.py:174`.
- **Preconditions (FR-019(b), Renata MEDIUM).** Before this WP deletes `code_only_drift`, the operator files the silent-`model` issue with the detector's reproduction:
  - slot `model` @ `src/charter/offering/schemas/agent-profile.schema.yaml`;
  - suppressed by `Field(..., alias="model")` at `agent_profiles/profile.py:266` and `schema_models.py:217`.
- The spec's invariant line should acknowledge that the owner anti-weasel invariant was already lost in #3285 and is now formally abandoned (Renata INFO).

---

## E. Retirements (FR-008, FR-009, FR-012)

### E1. `tests/architectural/surface_resolution_audit/`: retire the whole directory
**Decision.** `git mv audit.py ../_surface_resolution_scan.py` (preserves blame), strip it to the scanner half, and delete the rest of the directory. Delete:
- `rekey_inventory.py`
- `inventory.md`
- `RULESET.md` (fold its rule list into the new module docstring)
- `audited-surfaces.md`
- `write_candidate_classification.yaml` (0 readers, confirmed)

**Kept surface** in `_surface_resolution_scan.py`, which is everything `test_single_mission_surface_resolver.py:163-182` and its tmp-tree monkeypatches (about L634) use:
- `SRC_SPECIFY_CLI`, `SRC_MISSION_RUNTIME`, `_normalize_token`, `_composite_from_file`, `CompositeKey`;
- `_RESOLVER_SOURCE_STEMS`, `_SELECTION_SEAM_STEMS`, `RESOLVER_CALLS`, `TOPOLOGY_BLIND_CALLS`, `SELECTION_READ_CALLS`, `ALL_BLESSED_CALLS`, `SLUG_NAMES`, `KITTY_SPECS_NAMES`;
- `ResolutionRow`, `_rel`, `_names_in`, `_slug_on_right`, `_contains_kitty_specs`, `_find_blessed_calls_in_seam`, `_find_raw_bypasses`, `_audit_file`, `discover_rows`, `SelectionRow`, `_find_selection_calls`, `discover_selection_callsites`, `ALLOWLISTED_SELECTION_CALLSITES`.

**Deleted from audit.py:**
- `INVENTORY_PATH`, `KNOWN_CANDIDATE_FILES`, `VALID_DISPOSITIONS`;
- `_unwrap`, `_collect_table`, `_parse_inventory_rows`, `_parse_selection_rows`, `_composite_from_locator`, `_inventory_composites`, `check_undercount`, `check_overcount`, `_fail`, `_resolution_checks`, `_selection_checks`, `main` and `if __name__` (L477-808);
- the `sys.path` bootstrap and `# noqa: E402` (L75-88), which are no longer needed once it is a normal package module.

**Rationale.**
- Deleting the directory removes every agent-facing trap in one stroke: the "re-run the recorded converter" instruction at `inventory.md:34` and `rekey_inventory.py:11-14,205-209`, and the `RULESET.md:6` instruction to run `audit.py`.
- It retires the `importlib`-by-path loading hack (`test_single_mission_surface_resolver.py:163-172`), which becomes `from tests.architectural import _surface_resolution_scan as _scan`. Monkeypatching module attributes keeps working.
- The new module must pass `ruff format` (it leaves the exclude list).

**Alternative.** Keep `audit.py` in place, stripped. That leaves a directory named "audit" containing no audit, the path-loading hack, and the format exclusion. Rejected.

### E2. FR-009 reference edits (live surfaces only)
**Exclusions.** "Live" excludes `kitty-specs/**`, `docs/reports/**`, `docs/archive/**`, `.kittify/evidence/**`, `CHANGELOG.md` and `docs/plans/engineering-notes/**` (historical).

- `pyproject.toml:954-955`: delete both `[tool.ruff.format].exclude` entries. `test_ruff_format_enforcement.py::test_formatter_debt_exclude_only_names_live_files` requires this, and `_BASELINE_EXCLUDE_COUNT` (2808, a `<=` ceiling) is unaffected.
- `test_single_mission_surface_resolver.py`:
  - L19 and L92-97 docstrings;
  - L163-182 import;
  - L204-207 comment (it also cites the long-retired `test_resolution_authority_gates.py` and "inventory.md's WP08 hand-edit note");
  - L508 failure message ("Run `python …/audit.py`") → "call `_surface_resolution_scan.discover_rows()`".
- `_ratchet_keys.py:49,124` docstrings (doc-only, but this is the shared substrate, so run the full `tests/architectural/`).
- `test_no_worktree_name_guess.py:155` comment.
- Not needed, correcting a post-spec claim: `untrusted_path_audit/inventory.md:76` and `:210` and `test_untrusted_path_containment.py:240` refer to the **sibling** `untrusted_path_audit/` directory's own files.
- **Red-first for this pure-deletion WP (a C-001 gap).** No committed gate detects the defect: its gate was deleted by #3285. Tombstone tests are forbidden. The evidence is therefore non-committed and goes in the WP tracer:
  - on base, `python audit.py` exits 1 (8+8);
  - on base, `rekey_inventory.py --check` reports STALE;
  - the FR-009 token search (`rekey_inventory|_render_inventory|_parse_inventory_rows|surface_resolution_audit|audited-surfaces|write_candidate_classification`) has hits on base and 0 live hits after.

  The committed acceptance test is the survivor, `test_single_mission_surface_resolver.py` (8 tests), staying green. **Needs operator confirmation** that this satisfies C-001 for a deletion-only WP.

### E3. FR-012: `resolution_gate_allowlist.yaml`
- It has no consumer gate (`test_resolution_authority_gates.py` is gone). Its only reader is the ban's YAML arm, which scans it rather than consuming it.
- Its caps `canonicalizer_baseline: 3` and `coord_authority_baseline: 3` are dead (the #3026 class).
- **Delete it in the closeout WP**, which owns the ban file, and drop it from `_YAML_ALLOWLISTS` (A6).
- **References:**
  - ban docstring L51-57;
  - `test_no_read_side_bypass.py:867,906` (prose);
  - `test_inline_meta_read_gate.py:14` (prose);
  - `docs/development/reference/read-side-seam-classification.md:529`;
  - **`src/specify_cli/status/aggregate.py:543` (a comment in `src/`).**
- **Operator decision needed:** SC-003 says "0 references … in live docs, tests, **source**", but C-005's first clause confines changes to non-`src/` paths.
  - I recommend allowing comment-only `src/` edits, proven behaviour-neutral by `ast.dump` equality of old and new module ASTs (recorded in the PR).
  - Otherwise, leave the comment and list it as a residual in the tracer.
- Other `test_resolution_authority_gates.py` references (docs, ADR, `_review_cycle_reconcile_doctor.py:240`) predate this mission. They are **not** in scope for SC-003; mention them as a follow-up only.

---

## F. Parity remediation (FR-013..FR-017)

### F1. FR-013: `tests/next/test_internal_runtime_parity.py`
- **Convert** `test_no_rich_or_typer_imports_in_internal_package` (L118-139). It now uses `_RUNTIME_PACKAGE = <repo>/src/runtime/next/_internal_runtime` and a pure `_rich_typer_import_offenders(root) -> list` that walks `ast.Import`/`ImportFrom`, replacing the line-prefix match that misses `import os, typer`.
  - Floor: `root.is_dir()` and `len(py_files) >= 16` (the planning-base count; a missing directory or an empty target FAILS).
  - Scope stays `_internal_runtime` only, because `src/runtime/next/runtime_bridge_retrospective.py:158` imports `rich.prompt`.
- **Tests:**
  - `test_rich_typer_ban_fails_on_missing_or_empty_target` (tmp_path);
  - `test_rich_typer_ban_flags_planted_import` (tmp file containing `import typer`; asserts the offender is named);
  - `test_rich_typer_ban_inspects_live_runtime_package`. This is the **red-first**: on base the ban inspects 0 files, which is a behavioural red and not an ImportError.
- **Retire:**
  - `test_no_spec_kitty_runtime_imports_in_internal_package` (L89). Survivor: `test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package` (L56-57, `_PRODUCTION_ROOTS` includes `src/runtime`), which carries a planted self-test at L47-49.
  - `test_public_surface_matches_contract` (L142) and `test_submodule_surface_matches_contract` (L161). Positive shape pins; the second pins the private `engine._read_snapshot`.
  - NFR-006 reason for these: `__all__`/`hasattr` equality pins shape, and the behaviour is covered by `test_internalized_runtime_matches_upstream_snapshot`'s replay through `next_step`/`start_mission_run`.
  - Mutation: renaming `_read_snapshot` reds only the retired test, and the golden stays green, which demonstrates it pinned shape.
- Relabel the golden's docstring: "characterization golden", not "upstream parity".

### F2. FR-014: `tests/status/test_parity.py` (740 LOC) → delete the file
- **Retire:**
  - `TestBackportReadiness` (L75-190). Reason: `specify_cli.sync` is deleted, and `test_no_retired_subsystems.py:28` is the canonical guard.
  - `TestPhaseCap::test_phase_module_deleted` (L200). A tombstone, the same class #3285 retired.
- **Relocate into `tests/status/test_transitions.py`** as a new `TestTransitionMatrixInvariants`:
  - `test_all_canonical_lanes_in_enum`, `test_all_enum_values_in_canonical_lanes`, `test_transition_pairs_use_canonical_lanes`, `test_no_self_transitions_in_matrix`, `test_terminal_lanes_have_no_outbound_transitions` (L695-740).
  - Not currently duplicated there; existing coverage is only `test_terminal_lanes` L46 and the baseline matrix L627.
- **Relocate into `tests/status/test_reducer.py`:** `TestFullEventLogParity`'s realistic-log fixture plus `test_realistic_log_produces_expected_summary` and `test_realistic_log_json_roundtrip_stable` (L549-690), and the unique `test_sorted_keys_in_json_output` (L373).
- **Retire as duplicates** (named survivors in `test_reducer.py`):

| retired | survivor |
|---|---|
| same-events-identical | `test_byte_identical_across_reduce_calls` :465 |
| order-independence | `test_reduce_out_of_order_events` :177 |
| dedup | `test_reduce_deduplication` :211 |
| byte-identical | `test_byte_identical_output` :425 |
| empty | `test_reduce_empty_events` :102 |
| force-count | `test_reduce_force_count_tracked` :280 |
| rollback | `test_in_review_to_in_progress_rollback_beats_concurrent_approval` :315 |

- **Mutation proofs** (PR record; they must red both the retired test and its survivor or relocated test):
  - shuffle the reducer sort key;
  - add a `done→planned` matrix row;
  - add a self-transition.
- `pyproject.toml:2553`: remove the entry in the same commit. `test_reducer.py` and `test_transitions.py` stay format-excluded (L2555, L2562). Keep their unformatted style to avoid `test_every_exclude_entry_still_genuinely_reformats` flipping; coordinate with #4506.
- `tests/cross_branch/test_parity.py` is **not** in FR-014. It gets a verdict row (consolidate, deferred) in FR-018 plus a follow-up; do not expand scope.

### F3. FR-015: `tests/charter/test_context_parity.py`. **Feasible under C-005** (prototyped)
`squad/fr015_probe2.py` ran `build_charter_context` in a git-initialised tmp project with **zero `unittest.mock.patch` and no private calls**, and all four markers held:
- `first_load True`;
- `directive:DIRECTIVE_998` plus `Cause: missing_artifact`;
- the `_LONG_BODY_NEEDLE` was swapped;
- `section:terminology-canon` was present.

Mechanism:
1. **Public env knob.** `SPEC_KITTY_PACKS_ROOT=<tmp>/packs` (`kernel.paths.get_built_in_pack_root`, `pack_paths.py:18`). `<tmp>/packs/built-in` mirrors the real `packs/built-in` with per-child symlinks, except:
   - `directives/`, which is an **empty real directory** (this replaces both `built_in_dir` patches and the `resolve_doctrine_root` patch);
   - `agent_profiles/`, a real directory holding symlinks to every real profile plus one on-disk `parity-fixture-agent.agent.yaml` (this replaces the private `_activation_aware_profile_map` patch).
2. **No cache reset needed.** `_ACTIVATION_AWARE_PROFILE_MAPS` is keyed by `repo_root`, which is a unique `tmp_path`, so the private `_reset_agent_profile_cache` call goes.
3. **Control.** Without the knob, the real catalog turns the cause into `typo_suspected` (suggestion `DIRECTIVE_049`). This proves the empty-directives mirror is load-bearing, and it doubles as the "mutating the fixture changes the outcome" AS.

Specifics:
- Author the fixture profile as literal YAML in the test (a public data format), not via `model_dump`.
- Rename to `tests/charter/test_context_bootstrap_markers.py` (not format-excluded, so it must be formatted).
- Delete the relocation-changelog comment (L195-230).
- **Risks the WP must verify:**
  - Windows CI: `ci-windows.yml` is live. Use a `_mirror_packs(tmp)` helper that tries `symlink_to` and falls back to `shutil.copytree` per child (about 1-2 s).
  - Process-wide caches keyed only by process. Run `pytest tests/charter tests/doctrine -p no:randomly` in one process, before and after, and confirm no order-dependence.
  - If either fails, **defer FR-015** per the spec assumption (C-005) and file a `src/` seam follow-up. Never re-patch privates.
- **Red-first:** `test_context_markers_use_no_private_patch_targets`. It walks the module's AST for `patch(`/`monkeypatch.setattr` targets containing a `_`-prefixed segment and asserts none. RED on base (4 private targets). This is an AS-backed behavioural check (Renata MEDIUM), not a tombstone.

### F4. FR-016: residue in kept suites (exact edits)
- `tests/missions/test_surface_resolution_equivalence.py`:
  - delete `_apply_xfail` (L578+), the `xfail_reason` column of `_MATRIX` (L488-575), the stale RED/GREEN table (L36-108) and the L444-486 comment;
  - keep `_assert_equivalent` and the matrix;
  - add `test_equivalence_detects_planted_divergence` (monkeypatch one entry point to return primary, and the matrix reds).
- `tests/architectural/test_execution_context_parity.py`:
  - delete the xfail→WP docstring map (L110-160, L1397-1413; there are 0 `mark.xfail` left);
  - delete the `missing_seams` half of `test_no_feature_dir_anchored_status_event_reads` (L2193-2198), a positive name pin;
  - keep the negative ban.
- `tests/review/test_transition_gate_parity.py`: delete `test_wp09_hook_landmine_disposition_is_documented_accurately` (L280), a test of its own docstring.
- `tests/architectural/test_docs_cli_reference_parity.py`: delete `test_retired_check_residual_option_is_absent` (L205-213), a retired-name tombstone costing about 72 s.
- **Format note.** All four files are format-excluded (pyproject L1798, L977, L1899, L970). Edits must keep them "still genuinely reformats".
- **Red-first:** the planted-divergence test only strengthens a suite, so it is green on base. For a pure-deletion WP use the E2 pattern: tracer evidence, including the mutation showing each retired test could not fail, or names shape.
  - Fold FR-016 into the FR-013 WP, whose converted ban provides a genuine red.

### F5. FR-017: split `tests/runtime/test_bridge_parity.py`
**Verified facts:**
- The P0 block is L1401-1862: **13 functions, 14 nodes** (`test_review_reject_redispatches_implement_coord_family` is parametrized over `_MissionTopology` ×2).
- No P0 test takes the module-scoped `ledger_results` oracle fixture (L1120-1144), and none uses `_bridge_oracle` symbols (AST closure probe; the `canonical` hit was a docstring word).

**Mechanics:**
- **New support module** `tests/runtime/_next_mission_scaffold.py`, with `__all__` and public names. It moves the helper closure the P0 block needs:
  - `_init_git_repo` L70, `_commit_all` L80, `_seed_wp_lane` L85, `_write_wp_task_files` L105, `_add_wp_files` L132, `_write_spec_md` L140, `_provision_mission_type_activations` L148, `scaffold_software_dev` L182, `advance_to_step` L284;
  - the late golden-path imports L321-326 (`MissionTopology`, `_golden_create_mission`, `_golden_init_git_repo`, `_golden_materialize_coord_worktree`);
  - `scaffold_coord_software_dev` L329, `_reject_wp_on_status_surface` L370.

  The oracle module re-imports them from the scaffold, so there are no duplicates.
- **New test module** `tests/runtime/test_next_board_authority.py` (behaviour-named, formatted, `pytestmark = [integration, git_repo]`). It holds the 13 P0 functions plus the 2 fail-closed direct-call tests (L1383-1400). Those two are not oracle-dependent, and leaving them behind would make the oracle not "retirable in isolation". Result: **15 functions / 16 nodes**.
  - Scaffold fixtures stay function-scoped (`tmp_path`).
  - **No `_bridge_oracle` import and no module-scoped fixture.**
- **Oracle module** `test_bridge_parity.py` keeps L1120-1330: 10 nodes, assertion count unchanged (C-002).
- **Acceptance** (the red-first, which is RED on base because the module does not exist; supplement with PR evidence):
  1. the collected node-ID set of the new module equals the 16 base node IDs (diffed in the PR);
  2. `test_board_authority_module_does_not_import_the_oracle`, an AST check that the module and its scaffold import nothing from `tests.runtime._bridge_oracle` and declare no module-scoped fixture;
  3. `pytest tests/runtime/test_next_board_authority.py --durations=0` finishes in under 60 s (NFR-004; about 48 s measured by Debbie, so tight headroom. Record the figure, never assert it).
- Replace the `bridge:NNNN` anchors in `_bridge_oracle.py` (e.g. :448, :465, :518) with symbol names (a campsite cleanup; comments only).
- Update the comment reference at `tests/next/test_finalized_task_routing.py:269` (`test_no_advancing_path_emits_unauthorized_step` moved) and `tests/runtime/fixtures/bridge/README.md`.
- Coordinate with #2560.

### F6. FR-018 verdict catalog
- **Canonical format:** #2620's catalog in `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-design-decisions.md:20`, with columns `suite | category | pins invariant or shape? | CaaCS churn | verdict | note`.
- Record it in this mission's `kitty-specs/<mission>/tracer-design-decisions.md`, seeded by the `mission-tracer-files` procedure.
- **Completeness is machine-checked in the PR by a script.** Its module set must equal `find tests -name '*parity*.py' -o -name '*equivalence*.py'` on the planning base, minus the 4 `_support/coverage_safety` helpers, giving **45 rows**. Churn columns are `all/src/mass/pcm/pcsrc` with the git window stated.

---

## G. WP slicing

### G1. Shared hotspots and how they are sequenced
| hotspot | touched by | resolution |
|---|---|---|
| `test_ratchet_positional_anchor_ban.py` | ban widening; closeout (empty the exemptions, YAML arm) | owned by WP01; WP12 depends on WP01 (sequenced) |
| `pyproject.toml` format-exclude | WP07 (L954-955), WP09 (L2553) | WP09 depends on WP07 (same lane) |
| `_baselines.yaml` / `test_ratchet_baselines.py` | WP06 only | census WPs (WP04/WP05) forbidden to touch them (the count of 56 is preserved) |
| `_destructive_op_census.py` | WP04 (shared helper) | WP05 depends on WP04 |
| `_content_identity.py` | WP02 creates it | WP03, WP04 depend on WP02 |
| `_ratchet_keys.py` | WP07 (docstrings only) | single owner; full arch run |

### G2. WP table (12 WPs)
| WP | Title | FRs / NFRs | Owned files | Deps | Size | Red-first acceptance test (RED on base → GREEN) |
|---|---|---|---|---|---|---|
| WP01 | Widen positional-anchor ban + interim per-site exemptions | FR-001, FR-002, FR-003 (interim), NFR-002, NFR-004 | `test_ratchet_positional_anchor_ban.py` | — | M | `test_no_int_line_sink_in_architectural_python_seeds` + `test_no_positional_anchor_in_architectural_text_files`, widened: 94 findings (6/2/22/56/2 + 6 txt), then GREEN via 94 exact per-site rows. Includes the 4 inverted tests (A3) and the arm-disable self-mutations |
| WP02 | Content-identity helper + join allowlist migration | FR-004, FR-007 (join), NFR-001 (join), NFR-003 | new `_content_identity.py`, new `test_content_identity.py`, `test_built_in_location_authority.py` | — | S | `test_join_allowlist_survives_line_drift` (3 files) and `test_join_allowlist_entries_each_suppress_a_live_join` (RED: 2 dead) |
| WP03 | Kernel + os-detect exemption migration | FR-005, FR-007, NFR-001 | `test_kernel_no_doctrine_import.py`, `_os_detection_exemptions.py`, `_exemptions/os-detect-ban-*.txt` (5), `test_os_detection_ban.py` | WP02 | S | `test_kernel_exemptions_survive_line_drift` and `test_os_detection_exemptions_survive_line_drift` (4 files) |
| WP04 | Census substrate + destructive + overwrite re-key | FR-006 (24 keys), C-004, NFR-001 | `_destructive_op_census.py`, `test_destructive_op_routing.py`, `test_overwrite_ownership_routing.py`, `kitty-specs/…/census-rekey-map.csv` (destructive and overwrite rows), `research/census_rekey_equivalence.py` | WP02 | M | `test_destructive_census_survives_line_drift` (17 files), `test_overwrite_census_survives_line_drift` (2), `test_second_identical_op_in_exempted_function_fails` |
| WP05 | Mutation census re-key | FR-006 (56 keys) | `test_mutation_ownership_routing.py`, CSV mutation rows | WP04 | M | `test_mutation_census_survives_line_drift` (23 files); equivalence script output = 80/80 identical sites; the count of 56 is unchanged |
| WP06 | Baseline leaf enforcement + inert-slot retirement (#3962) | FR-010, FR-011, NFR-003 | `test_ratchet_baselines.py`, `_baselines.yaml`, `_inert_slots.py`, `_inert_slots_baseline.yaml`, `test_no_inert_schema_slots.py`, comment edits in `test_reference_enum_ratchet.py` and `tests/contract/test_example_round_trip.py` | FR-019(b) issue filed first (operator) | M | `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` (RED names 4 leaves), then the delete; `test_lowering_an_enforced_leaf_below_live_fails` ×19; `test_live_scan_meets_per_walk_floors` |
| WP07 | Surface-resolution converter retirement | FR-008, FR-009 | `surface_resolution_audit/*` → `_surface_resolution_scan.py`, `test_single_mission_surface_resolver.py`, `_ratchet_keys.py` (docstrings), `test_no_worktree_name_guess.py` (comment), `pyproject.toml` L954-955 | — | S | Deletion WP: tracer evidence (`audit.py` exit 1, `--check` STALE, token search count >0 → 0); survivor `test_single_mission_surface_resolver.py` 8/8 green (C-001 deletion-WP ruling needed) |
| WP08 | Runtime-parity ban + parity residue | FR-013, FR-016 | `tests/next/test_internal_runtime_parity.py`, `tests/missions/test_surface_resolution_equivalence.py`, `tests/architectural/test_execution_context_parity.py`, `tests/review/test_transition_gate_parity.py`, `tests/architectural/test_docs_cli_reference_parity.py` | — | S/M | `test_rich_typer_ban_inspects_live_runtime_package` (RED: 0 files inspected) + missing/empty/planted tests; `test_equivalence_detects_planted_divergence` |
| WP09 | Status parity retirement and relocation | FR-014, NFR-006 | `tests/status/test_parity.py` (delete), `tests/status/test_reducer.py`, `tests/status/test_transitions.py`, `pyproject.toml` L2553 | WP07 (pyproject serialization) | M | Relocated `TestTransitionMatrixInvariants::test_no_self_transitions_in_matrix` etc., each driven RED by the recorded mutations (self-transition, `done→planned`, sort-key shuffle) before relocation lands |
| WP10 | Context parity conversion (or deferral) | FR-015 | `tests/charter/test_context_parity.py` → `test_context_bootstrap_markers.py` | — | M | `test_context_markers_use_no_private_patch_targets` (RED: 4 private targets); the no-knob control shows `typo_suspected` |
| WP11 | Bridge parity split | FR-017, C-002, NFR-004 | new `tests/runtime/_next_mission_scaffold.py`, new `tests/runtime/test_next_board_authority.py`, `tests/runtime/test_bridge_parity.py`, `tests/runtime/_bridge_oracle.py` (comments), `tests/next/test_finalized_task_routing.py` (comment), `tests/runtime/fixtures/bridge/README.md` | — | M | `test_board_authority_module_does_not_import_the_oracle` + node-ID set equality (16) |
| WP12 | Closeout: empty the exemptions, retire orphan gate data, verdicts, follow-ups, matrix | FR-003 (final), FR-012, FR-018, FR-019, FR-020, SC-001/005/006 | `test_ratchet_positional_anchor_ban.py`, delete `resolution_gate_allowlist.yaml`, `test_no_read_side_bypass.py` / `test_inline_meta_read_gate.py` (prose), `docs/development/reference/read-side-seam-classification.md`, (`src/specify_cli/status/aggregate.py:543` comment, if ruled), tracer files, issue matrix | WP01, WP02, WP03, WP05 (and all others, for the catalog) | S | `test_positional_anchor_exemptions_are_pinned_empty` (`== frozenset()`; RED with 94 rows) |

**Lanes (parallel):**
- **L1:** WP01 → WP12.
- **L2:** WP02 → WP03.
- **L3:** WP02 → WP04 → WP05.
- **L4:** WP06.
- **L5:** WP07 → WP09.
- **L6:** WP08.
- **L7:** WP10.
- **L8:** WP11.

WP12 joins all lanes. Critical path: WP02 → WP04 → WP05 → WP12.

### G3. Blast-radius commands per WP (plus `make test-fast` for every WP, and `ruff check` / `ruff format --check .` / `mypy <changed>`)
- **WP01:** `pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_trio_seam_only.py tests/specify_cli/contracts/ -q --durations=0`
- **WP02:** `pytest tests/architectural/test_content_identity.py tests/architectural/test_built_in_location_authority.py tests/doctrine/test_built_in_location_authority.py -q`
- **WP03:** `pytest tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/test_os_detection_ban.py tests/architectural/test_lock*ban*.py -q`
- **WP04 and WP05** (shared helper, cross-cutting):
  - `pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_ratchet_baselines.py -q`
  - then **`pytest tests/architectural/ -n auto --dist loadfile`**
  - then `python kitty-specs/<mission>/research/census_rekey_equivalence.py --base 3717c7ea`
- **WP06** (`_baselines.yaml`, cross-cutting):
  - `pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_no_inert_schema_slots.py tests/architectural/test_reference_enum_ratchet.py tests/architectural/test_no_dead_modules.py tests/architectural/test_gate_remedy_presence.py tests/contract/test_example_round_trip.py -q`
  - then the full `tests/architectural/`
- **WP07** (`pyproject.toml`, cross-cutting):
  - `pytest tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_ruff_format_exclude_ratchet.py -q`
  - then the full `tests/architectural/`
- **WP08:** `pytest tests/next/ tests/missions/test_surface_resolution_equivalence.py tests/architectural/test_execution_context_parity.py tests/review/test_transition_gate_parity.py tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_shared_package_boundary.py -q`
- **WP09:**
  - `pytest tests/status/ tests/architectural/test_no_retired_subsystems.py -q`
  - `pytest tests/architectural/test_ruff_format_*.py -q`
- **WP10:** `pytest tests/charter/ tests/doctrine/ -q -p no:randomly` (cache order check); also `-n auto --dist loadfile`
- **WP11:**
  - `pytest tests/runtime/test_next_board_authority.py --durations=0 -q`
  - `pytest tests/runtime/test_bridge_parity.py tests/runtime/test_bridge_decide_next.py tests/next/ -q` (the oracle takes about 440 s)
- **WP12:**
  - `pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_no_legacy_terminology.py -q`
  - then the full `tests/architectural/` (final)

---

## 8. Errata and open decisions for the operator

**Errata**
1. **Spec FR-006 swaps the counts.** It says "destructive-op (56), mutation (22)"; on HEAD the destructive `_ALLOWLIST` has **22** and the mutation one has **56**. `destructive_op_allowlist: 56` is the *mutation* gate's baseline key.
2. **Spec FR-013..FR-018 numbering differs from Priti's WP table**, which is shifted by one (e.g. her FR-013 is the spec's FR-014). This design uses the spec's numbering.
3. **Post-spec claim that `untrusted_path_audit/inventory.md:76` references the retired inventory is false:** it is that directory's own row.

**Decisions**
- **D-OP-1 (census key).** `CensusKey` = composite key + op + occurrence. Only 3/80 entries need `occurrence=1`.
- **D-OP-2 (`category_1` and `skip_marker_blocks`).** Remove them, not enforce them. `category_1`'s equality pin shows the earlier toll drain was illusory.
- **D-OP-3 (comment-only `src/` edits under C-005, for SC-003).** Recommend allowing them, with AST-equality proof.
- **D-OP-4 (C-001 for deletion-only WP07).** Tracer evidence plus a green survivor, with no tombstones.
- **D-OP-5 (FR-015).** Feasible; defer only if the Windows or cache-order checks fail.
- **D-OP-6 (the text arm makes the clock and lock-ban `CALL:`/`path:line` exemption shapes unusable at 0 entries).** Intended: those gates are shrink-only at zero.
- **Follow-ups beyond FR-019:**
  - `tests/contract/test_next_no_unknown_state.py:40` has the same vacuous rglob of the deleted `src/specify_cli/next`;
  - consolidate `tests/cross_branch/test_parity.py`;
  - stale `test_resolution_authority_gates.py` references in docs, ADR and `src/`.
