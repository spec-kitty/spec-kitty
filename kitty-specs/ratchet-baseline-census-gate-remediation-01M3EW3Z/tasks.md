# Work Packages: Ratchet, baseline & census gate remediation

**Inputs**: Design documents from `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/` (spec.md, plan.md rev 2, research.md, data-model.md, quickstart.md, research/*)
**Prerequisites**: plan.md (rev 2, 13 WPs), spec.md (rev 2 + errata)

**Tests**: Required. Every code WP lands a failing-first acceptance test (C-001); deletion-only WPs follow D-OP-4.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

**Prompt Files**: `tasks/WPxx-*.md` (flat). Deep implementation detail lives in the prompt files.

## Dependency overview

- Lanes: WP01; WP02 → {WP03, WP04}; WP05 → WP06; WP07; WP08; WP09; WP10; WP11; WP12 (planning artifact). WP13 depends on all.
- Critical path: WP02 → WP04 → WP13.
- Sequenced out-of-map edits: `test_ratchet_positional_anchor_ban.py` (WP01 owns; WP13 edits), `_baselines.yaml` (WP06 owns; WP05 edits its inert leaves first), `pyproject.toml` format-exclude (WP07, WP09 remove their own lines; WP13 drains the rest).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Widen the Python arms of the positional-anchor ban | WP01 | |
| T002 | Add the text-file arm and its standing gate | WP01 | |
| T003 | Invert the context-gate tests and add the fixture matrix | WP01 | |
| T004 | Record the 94-finding RED; add 94 per-site exemption rows + exactness test | WP01 | |
| T005 | Floors and per-arm self-mutation proofs | WP01 | |
| T006 | Docstring rewrite, durations record, quality gates | WP01 | |
| T007 | Red-first join acceptance tests (stale + drift) | WP02 | |
| T008 | Create `_content_identity.py` and `test_content_identity.py` | WP02 | [P] |
| T009 | Migrate the join allowlist to 4 content descriptors | WP02 | |
| T010 | Non-widening join proofs and docstring rewrite | WP02 | |
| T011 | Validation, tracer, quality gates | WP02 | |
| T012 | Red-first kernel/os-detect drift and loader-rejection tests | WP03 | |
| T013 | Migrate the kernel exemptions | WP03 | |
| T014 | Migrate the os-detect loader, `.txt` rows and gate | WP03 | |
| T015 | Retarget the lock-ban and clock `CALL:` loaders | WP03 | |
| T016 | Validation, tracer, quality gates | WP03 | |
| T017 | Red-first census drift tests and non-widening guards | WP04 | |
| T018 | Unify the qualname algorithm; add `CensusKey` and `census_keys` | WP04 | |
| T019 | Delegate the census partitioner to `_content_identity` | WP04 | |
| T020 | Re-key/equivalence script and `census-rekey-map.csv` | WP04 | [P] |
| T021 | Re-key the destructive-op gate (22) | WP04 | |
| T022 | Re-key the overwrite gate (2) | WP04 | |
| T023 | Re-key the mutation gate (56) | WP04 | |
| T024 | Non-widening, ordinal and diagnostics proofs | WP04 | |
| T025 | 80/80 equivalence proof | WP04 | |
| T026 | Full architectural run and quality gates | WP04 | |
| T027 | Record D-OP-4 red-first evidence on base (0 callers, stale-row warning, #5117 reproduction) | WP05 | [P] |
| T028 | Delete dead machinery in `_inert_slots.py` | WP05 | |
| T029 | Prune `_inert_slots_baseline.yaml` + parser (36 rows) | WP05 | |
| T030 | Sequenced `_baselines.yaml` inert-leaf edit + `test_reference_enum_ratchet.py` prose | WP05 | |
| T031 | Wire per-walk floors with self-mutation; token search; evidence | WP05 | |
| T032 | RED first: `_SIZE_RATCHETS` table, leaf helpers, leaf-enforcement test | WP06 | |
| T033 | Rewire growth and shrink arms onto `_SIZE_RATCHETS` | WP06 | |
| T034 | Derive hand-kept key lists; retire grandfather set | WP06 | |
| T035 | Remove `category_1` leaf + machinery; survivor proof; ADR bullet | WP06 | |
| T036 | Remove `skip_marker_blocks` leaf + machinery; round-trip comments | WP06 | |
| T037 | Lower-below-live mutations, planted-leaf self-mutation, floors | WP06 | |
| T038 | Record D-OP-4 red-first evidence (audit exit 1, STALE, token count) | WP07 | [P] |
| T039 | `git mv` audit.py → `_surface_resolution_scan.py`, strip, pyproject L954 | WP07 | |
| T040 | Delete remaining `surface_resolution_audit/` files, pyproject L955 | WP07 | |
| T041 | Rewire survivor `test_single_mission_surface_resolver.py` | WP07 | |
| T042 | FR-009 reference edits, path-qualified token search 0, validation | WP07 | |
| T043 | RED first: floor/missing/planted tests for both vacuous scans | WP08 | [P] |
| T044 | Convert rich/typer ban onto live `_internal_runtime` | WP08 | |
| T045 | Retire duplicate ban + surface pins; relabel golden | WP08 | |
| T046 | Retarget `test_next_no_unknown_state` runtime scan + planted placeholder | WP08 | |
| T047 | FR-016 residue in surface-resolution equivalence + planted divergence | WP08 | |
| T048 | FR-016 residue in three parity suites; validation | WP08 | |
| T049 | Mutation matrix M1–M10 and disposition evidence (tracer) | WP09 | |
| T050 | Relocate unique determinism tests into test_reducer.py; retire duplicates (incl. L407/L660) | WP09 | [P] |
| T051 | Transition-matrix dispositions (duplicates retired; lane↔enum relocated only if no survivor) | WP09 | [P] |
| T052 | Delete tests/status/test_parity.py and its pyproject exclude line | WP09 | |
| T053 | NFR-006 tracer record and blast-radius validation | WP09 | |
| T054 | Red-first src-coupling AST scan (8 offenders on base) and self-mutation test | WP10 | |
| T055 | Copied SPEC_KITTY_PACKS_ROOT mirror and on-disk fixture profile | WP10 | |
| T056 | Convert marker tests; pack-root and control assertions; cache-order check | WP10 | |
| T057 | Rename to test_context_bootstrap_markers.py; update references (AST proof for src comment) | WP10 | |
| T058 | Blast radius, tracer, deferral record | WP10 | |
| T059 | Base node-ID capture and red-first oracle-independence guard | WP11 | |
| T060 | Verbatim move of helper closure into _next_mission_scaffold.py | WP11 | |
| T061 | Verbatim move of 15 P0/fail-closed test functions | WP11 | |
| T062 | Format commit, then public-name rename commit | WP11 | |
| T063 | Update test_finalized_task_routing.py and fixtures/bridge/README.md references | WP11 | |
| T064 | Node-ID/oracle-identity/setup-plan/durations evidence | WP11 | |
| T065 | Red-first parity_catalog_check.py (45-module set equality) | WP12 | |
| T066 | Author research/parity-verdicts.md (45 rows, #2620 format) | WP12 | |
| T067 | Tracer pointer and WP13 reconciliation hand-off | WP12 | |
| T068 | Red-first test_positional_anchor_exemptions_are_pinned_empty | WP13 | |
| T069 | Empty exemptions; warn→fail flip with self-mutation | WP13 | |
| T070 | Retire resolution_gate_allowlist.yaml and update references (FR-012) | WP13 | |
| T071 | Format-exclude drain for AST-changed excluded files | WP13 | |
| T072 | FR-019(d) and out-of-scope follow-up issues; verify #5116–#5118 | WP13 | [P] |
| T073 | Issue-matrix rows via spec-kitty agent issue-verdict | WP13 | [P] |
| T074 | Final integration sweep | WP13 | |
| T075 | SC-001..SC-006 verification and tracer assess | WP13 | |

---

## WP01 – Widen positional-anchor ban + interim per-site exemptions

**Summary**
- **Goal**: close the positional-anchor ban's three blind spots (substrate-import gate, `Path(...)` path elements, `path:line[:op]` keys) plus keyword records, class-body seeds and `_exemptions/*.txt` lines, then land GREEN through 94 exact per-site interim exemption rows (FR-001, FR-002, FR-003 interim, NFR-002, NFR-004).
- **Priority**: P1 (US1; unblocks the SC-001 pin in WP13).
- **Independent test**: with an empty exemption set the widened standing gates report 94 findings (6 / 2 / 22 / 56 / 2 / 6); with the rows they pass; a planted `(Path("a.py"), 12)`, `{"x.py:9:op": "r"}`, `Entry(path=..., lineno=3)`, class-attribute tuple or `CALL:x.py:12` text line is flagged, and each arm-disable self-mutation turns its plant green.

**Subtasks**
T001 Widen the Python arms: drop the import gate, add path-ish element, file-line tuple, embedded-key, keyword-record and class-body arms; carry symbol + site on findings (WP01)
T002 Add the text-file arm and `test_no_positional_anchor_in_architectural_text_files` (WP01)
T003 Invert the four context-gate tests and add the positive/negative fixture matrix (WP01)
T004 Record the 94-finding RED, then add the 94 one-line per-site exemption rows and `test_positional_anchor_exemptions_are_exact` (WP01)
T005 Floors (≥ 262 py files, ≥ 20 txt files, ≥ 6 entry lines) and per-arm self-mutation proofs (WP01)
T006 Rewrite the module docstring, record `--durations=0`, run quality gates (WP01)

**Implementation sketch**: commit 1 = widened arms + inverted tests + empty exemption set (RED, 94); commit 2 = generated rows (GREEN); commit 3 = floors, self-mutations, docstring. All predicates stay in the ban module (C-005: `is_file_line_anchor` untouched). File is format-excluded (pyproject L1019): no `ruff format`.

**Dependencies**: none.

**Risks**: false positives from widened arms (fix predicate, never exempt); rows over 164 chars (module constants); escape-hatch `# diagnostic-locator` abuse (forbidden); exact-set interplay with parallel lanes (row-without-finding only warns until WP13).

**Estimated prompt size**: ~265 lines.

**Prompt file**: [tasks/WP01-widen-positional-anchor-ban.md](tasks/WP01-widen-positional-anchor-ban.md)

## WP02 – Content-identity matching authority + join allowlist

**Summary**
- **Goal**: create `tests/architectural/_content_identity.py`, the single multiset matcher and descriptor-line serialiser for content-keyed allowlists (D-OP-9), and migrate `_KNOWN_JOIN_ALLOWLIST` (6 line pins) to 4 `ContentDescriptor`s, deleting the 2 dead entries (FR-004, FR-007, NFR-001, NFR-003).
- **Priority**: P1 (critical path WP02 → WP04 → WP13; WP03 also depends on it).
- **Independent test**: `test_join_allowlist_entries_each_suppress_a_live_join` is RED on base naming `src/kernel/paths.py:88` and `src/specify_cli/runtime/home.py:79` and GREEN after; `test_join_allowlist_survives_line_drift` (3 derived files, both mutations) keeps `(unexpected, suppressed)` identical; a new join planted at old `kernel/paths.py:88` is reported.

**Subtasks**
T007 Red-first join acceptance tests (stale entries + line drift) through an extracted gate seam (WP02)
T008 Create `_content_identity.py` (resolve, multiset partition, drift mutators, descriptor-line render/parse) and `test_content_identity.py` (WP02)
T009 Migrate the join allowlist to 4 lazily resolved `ContentDescriptor`s matched by `partition_findings` (WP02)
T010 Non-widening proofs (new join at formerly pinned line; duplicated key) and docstring rewrite (WP02)
T011 Validation, tracer record of non-adopter matchers, quality gates (WP02)

**Implementation sketch**: commit 1 = acceptance tests only (RED); commit 2 = helper + unit tests; commit 3 = migration + proofs. Counter-based partition keyed on full `(rel_path, qualname, token_line)`; stale = unresolvable or suppresses nothing (fail). Resolve lazily behind `functools.cache`.

**Dependencies**: none.

**Risks**: becoming an eighth matcher (docstring claims authority, lists non-adopters for FR-019(d)); set semantics reopening the `neutrality/lint.py` 379/380 widening hole; import-time resolution turning a stale entry into a collection error.

**Estimated prompt size**: ~260 lines.

**Prompt file**: [tasks/WP02-content-identity-authority-and-join-allowlist.md](tasks/WP02-content-identity-authority-and-join-allowlist.md)

## WP03 – Kernel + os-detect exemptions; retarget lock-ban/clock loaders

**Summary**
- **Goal**: migrate the 2 kernel `_PRE_EXISTING_EXEMPTIONS` tuples and the 6 `path:line` rows in `_exemptions/os-detect-ban-*.txt` to content identity, and retarget the lock-ban and clock `CALL:` loaders to the same content shape at zero entries so no loader accepts or teaches `path:line` (FR-005, FR-007, NFR-001, D-OP-6).
- **Priority**: P2.
- **Independent test**: `test_kernel_exemptions_survive_line_drift` (1 file) and `test_os_detection_exemptions_survive_line_drift` (3 files) keep `(unexpected, suppressed)` identical under both mutations; each of the three loaders raises `ValueError` on a `path:line` line; stale entries fail with `checked >= 2` / `>= 6`.

**Subtasks**
T012 Red-first tests: kernel and os-detect drift tests plus three loader-rejects-line-pin tests (WP03)
T013 Migrate the kernel exemptions to two descriptors; invert the real-violation test (WP03)
T014 Migrate the os-detect loader, the three `.txt` files and the gate; invert the stale-removal test (WP03)
T015 Retarget the lock-ban and clock `CALL:` loaders and their gates to the content shape (WP03)
T016 Validation, tracer (#3206, #4727, D-OP-6, residual no-follow loader), quality gates (WP03)

**Implementation sketch**: one RED commit, then one commit each for kernel, os-detect and the loader retarget. Everything parses/renders/partitions through WP02's `_content_identity`. `_exemptions/__init__.py` and `test_clock_call_ban.py` are format-excluded (no `ruff format`).

**Dependencies**: WP02.

**Risks**: three private parsers (use the shared pair only); clock loader globbing every `*.txt` (prefix filter must ignore content lines); weakening the inverted stale-removal tests; `test_clock_import_ban.py` (not owned) must stay green unchanged.

**Estimated prompt size**: ~255 lines.

**Prompt file**: [tasks/WP03-kernel-os-detect-exemptions-and-loader-retarget.md](tasks/WP03-kernel-os-detect-exemptions-and-loader-retarget.md)

## WP04 – Census re-key (all 80) on _content_identity + composite key

**Summary**
- **Goal**: re-key the 80 `rel:lineno:op` census keys (destructive 22, mutation 56, overwrite 2) to `CensusKey(rel, qualname, token_line, op, op_ordinal)`, delete the census helper's own qualname algorithm (C-004), delegate `diff_against_allowlist` to `partition_findings`, keep warn-on-stale, and prove 80/80 site equivalence against planning base `3717c7ea` (FR-006, C-004, NFR-001).
- **Priority**: P1 (critical path; largest WP, size L).
- **Independent test**: `test_{destructive,overwrite,mutation}_census_survives_line_drift` (15 / 2 / 21 derived files) RED on base and GREEN after; a second identical op in an exempted function fails; a token-changing argument edit fails and warns stale; `census_rekey_equivalence.py --base 3717c7ea` reports 80/80, a bijection and equal rationale hashes; mutation `_ALLOWLIST` still has 56 entries.

**Subtasks**
T017 Red-first census drift tests and non-widening guards through extracted gate seams (WP04)
T018 Delete the census `enclosing_qualname`, re-export the canonical one, add `parse_with_source`, `CensusKey`, `census_keys`; fix all callers in the same commit (WP04)
T019 Delegate `diff_against_allowlist` / `drop_one_entry` generically to `_content_identity.partition_findings` (WP04)
T020 Write the re-key/equivalence script and generate `census-rekey-map.csv` (mission artefacts, planning surface) (WP04)
T021 Re-key the destructive-op gate (22 keys) (WP04)
T022 Re-key the overwrite gate (2 keys) (WP04)
T023 Re-key the mutation gate (56 keys), including the research.py prefix guard and literal re-builder (WP04)
T024 Non-widening, ordinal and diagnostics proofs; baseline coupling check (WP04)
T025 Run the 80/80 equivalence proof and record it in PR and tracer (WP04)
T026 Full `tests/architectural/` run, blast radius, quality gates, campsite (WP04)

**Implementation sketch**: four lane commits (RED → helper → destructive+overwrite → mutation). Allowlist literals are generated in keyword form with rationales copied verbatim. CSV and equivalence script are mission artefacts written outside the lane (code_change WPs cannot own `kitty-specs/`).

**Dependencies**: WP02.

**Risks**: widening via a weak key (guarded by ordinal + token-line tests); laundering coincidental blessings (equivalence against base, not head); rationale drift (hash check); `_baselines.yaml` coupling (keep a 56-entry mapping, never edit the YAML); review load (staged commits, generated literals).

**Estimated prompt size**: ~305 lines.

**Prompt file**: [tasks/WP04-census-rekey-content-identity.md](tasks/WP04-census-rekey-content-identity.md)

---

Subtask Index rows:

---

## WP05 – Inert-slot retirement (#3026, #3962)

**Summary**
- **Goal**: retire the dead inert-slot machinery that #3285 orphaned (FR-010, DM-01M3EW4PB6).
  - Remove the uncalled caps, owner predicates and code-only suppression record from `_inert_slots.py`, along with its `materialize_snapshot` src import.
  - Drop `owner`/`provisional`/`mission` data and the 2 stale rows (`styleguide-references`, `model`) from `_inert_slots_baseline.yaml`, taking it from 38 to 36 rows.
  - Delete the `unassigned_entries` and `masking_suppressions` leaves from `_baselines.yaml` and set `baseline_entries` from 38 to 36. This is a sequenced edit into the WP06-owned file.
  - Wire the calibrated per-walk floors (150 schema names, 120 model names).
- **Priority**: P2 (US2). It unblocks WP06.
- **Independent test**:
  - `pytest tests/architectural/test_no_inert_schema_slots.py -q -rw` passes with no "baseline shrank" warning; on base the warning names `styleguide-references, model`.
  - The retired-token search returns 0 live hits.
  - `test_walk_floors_fail_on_a_collapsed_walk` reds both walks through the real `scanned_slots`.

**Subtasks**
T027 Record D-OP-4 red-first evidence on base (0 callers, stale-row warning, #5117 reproduction) (WP05)
T028 Delete dead machinery in `_inert_slots.py` (caps, owner predicates, code-only record, src import) (WP05)
T029 Prune `_inert_slots_baseline.yaml` + parser (36 rows, no owner/provisional/mission/code_only; reject retired keys) (WP05)
T030 Sequenced `_baselines.yaml` edit (38→36, delete 2 inert leaves) + `test_reference_enum_ratchet.py:192` prose (WP05)
T031 Wire per-walk floors with self-mutation; token search 0; green evidence (WP05)

**Implementation sketch**: gather base evidence and confirm #5117, then do the atomic parser+YAML+module prune (T028+T029 in one commit), then the `_baselines.yaml` block edit, then the floors test and the final token search.

**Dependencies**: none (#5117 filed as the FR-019(b) precondition).

**Risks**:
- The import-time `load_baseline()` breaks if the parser and YAML diverge. Land T028 and T029 atomically.
- The only `model` detector is lost unless #5117 carries its reproduction.
- The excluded test file must not become format-clean.

**Estimated prompt size**: ~290 lines

**Prompt file**: [tasks/WP05-inert-slot-retirement.md](tasks/WP05-inert-slot-retirement.md)

## WP06 – Baseline leaf enforcement

**Summary**
- **Goal**: the charter ratchet refuses any `_baselines.yaml` leaf that no comparison enforces (FR-011, NFR-003).
  - Hoist one `_SIZE_RATCHETS` table (19 rows) and make both arms iterate it.
  - Derive `_REQUIRED_TOP_LEVEL_KEYS` and `_REQUIRED_NO_DEAD_MODULES_CATEGORIES` from it, and retire the grandfather set.
  - Remove the derived `category_1` and advisory `skip_marker_blocks` leaves (D-OP-2).
  - Prove every row reads its own leaf by lowering each to live − 1.
- **Priority**: P1 (US2, SC-004).
- **Independent test**:
  - `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` is RED first. On the lane base it names 2 leaves; on the planning-base YAML, 4.
  - `test_lowering_an_enforced_leaf_below_live_fails` has 19 ids, all red-capable.
  - Planting a leaf fails and names it.

**Subtasks**
T032 RED first: `_SizeRatchet`/`_SIZE_RATCHETS`, `_enforced_leaves`/`_yaml_leaves`/`_leaf_drift`, leaf-enforcement test (WP06)
T033 Rewire growth and shrink arms onto `_SIZE_RATCHETS` via `_size_comparisons` (WP06)
T034 Derive hand-kept key lists; retire `_GRANDFATHERED_UNREGISTERED_KEYS`; fold unregistered-key tests (WP06)
T035 Remove `category_1` leaf + derived machinery/tests; survivor mutation proof; ADR bullet supersession (WP06)
T036 Remove `skip_marker_blocks` leaf + advisory machinery/tests; round-trip comment edits (WP06)
T037 Lower-below-live mutation tests (19), planted-leaf self-mutation, table floor, shrink-only proof (WP06)

**Implementation sketch**: a red-first table and test commit, then a pure rewire, then the derived registries, then the two leaf removals with NFR-006 survivors, then the mutation tests.

**Dependencies**: WP05, the sequenced `_baselines.yaml` inert-leaf edit.

**Risks**:
- The rewire could silently drop a row. The 19-id lowering test and the unchanged arm tests guard against this.
- Fast-tier import hygiene: never import the round-trip corpus at module scope.
- Cross-lane coupling on `len(test_mutation_ownership_routing._ALLOWLIST)` with WP04.
- The excluded file must not become format-clean.

**Estimated prompt size**: ~330 lines

**Prompt file**: [tasks/WP06-baseline-leaf-enforcement.md](tasks/WP06-baseline-leaf-enforcement.md)

## WP07 – Surface-resolution converter retirement

**Summary**
- **Goal**: retire the orphaned converter, inventory and audit entry point (FR-008, FR-009, DM-01M3EW4J8E).
  - `git mv` `audit.py` to `tests/architectural/_surface_resolution_scan.py`, stripped to the scanner functions the survivor uses. Fix the `_REPO_ROOT` depth and import `CompositeKey` from `_ratchet_keys`.
  - Delete the rest of `surface_resolution_audit/`.
  - Rewire `test_single_mission_surface_resolver.py` to a normal import.
  - Fix the FR-009 references, including the dangling `untrusted_path_audit/inventory.md:76` cross-reference.
  - Remove its own two pyproject format-exclude lines.
- **Priority**: P1 (US2, #3011 is P1).
- **Independent test**:
  - The survivor `test_single_mission_surface_resolver.py` has the same 8 node IDs, all green.
  - The path-qualified token search (`surface_resolution_audit|rekey_inventory|write_candidate_classification`) finds hits on base and 0 after.
  - `test_untrusted_path_containment.py` stays green.

**Subtasks**
T038 Record D-OP-4 red-first evidence (audit exit 1, `--check` STALE, base token count, survivor 8/8) (WP07)
T039 `git mv` audit.py → `_surface_resolution_scan.py`, strip to scanner, fix root depth, drop bootstrap/noqa, pyproject L954 (WP07)
T040 Delete rekey_inventory.py, inventory.md, RULESET.md, audited-surfaces.md, write_candidate_classification.yaml; pyproject L955 (WP07)
T041 Rewire the survivor to a normal import; fix its docstrings, floor comment and failure messages (WP07)
T042 FR-009 references (`_ratchet_keys.py`, `test_no_worktree_name_guess.py:155`, `untrusted_path_audit/inventory.md:76`), token search 0, validation (WP07)

**Implementation sketch**: record evidence, then do move + strip + rewire + pyproject line in one green step, then delete the remaining files with their pyproject line, then the reference edits and the final search.

**Dependencies**: none.

**Risks**:
- A wrong `_REPO_ROOT` depth makes the scan silently empty. The survivor's floor of 15 catches it.
- A pyproject entry could point at a moved or deleted file mid-series. Remove each line in the same commit as its file.
- The `untrusted_path_audit/inventory.md` table is parsed, so edit the rationale cell only.

**Estimated prompt size**: ~300 lines

**Prompt file**: [tasks/WP07-surface-resolution-converter-retirement.md](tasks/WP07-surface-resolution-converter-retirement.md)

## WP08 – Runtime-parity bans, parity residue and next-no-unknown-state scan

**Summary**
- **Goal**: make the runtime-parity bans non-vacuous and remove stale parity residue (FR-013, FR-016).
  - Convert the rich/typer ban to an AST helper over the live `src/runtime/next/_internal_runtime` (floor ≥ 16).
  - Retire the duplicate `spec_kitty_runtime` ban and the two surface-shape pins, with NFR-006 evidence.
  - Fix the vacuous `src/specify_cli/next` rglob in `tests/contract/test_next_no_unknown_state.py:40`, retargeting it to `src/runtime/next` (floor ≥ 31).
  - Remove dead strict-xfail machinery, stale docstrings, the name-only `missing_seams` arm, the self-referential docstring test and the `--check-residual` tombstone.
- **Priority**: P2 (US3, SC-005).
- **Independent test**:
  - `test_rich_typer_ban_inspects_live_runtime_package` and `test_runtime_placeholder_scan_inspects_live_source` are RED on base (0 files inspected).
  - The missing, empty and planted tests fail or flag through the real helpers.
  - `test_equivalence_detects_planted_divergence` reds `_assert_equivalent`.

**Subtasks**
T043 RED first: hoist current targets, add AST/placeholder helpers and floor/missing/planted tests (WP08)
T044 Convert rich/typer ban onto live `_internal_runtime` (AST, floor ≥ 16, load-bearing proof) (WP08)
T045 Retire duplicate spec_kitty_runtime ban + 2 surface pins (NFR-006 survivor/mutation); relabel golden docstring (WP08)
T046 Retarget `test_next_no_unknown_state` runtime scan to `src/runtime/next` (floor ≥ 31) + planted placeholder (WP08)
T047 FR-016 residue in `test_surface_resolution_equivalence.py` + planted-divergence test (WP08)
T048 FR-016 residue in execution-context, transition-gate and docs-CLI parity suites; tracer record; validation (WP08)

**Implementation sketch**: a red-first commit with floor tests, then retarget both scans, then the retirements with evidence, then the residue deletions in four format-excluded files (not reformatted).

**Dependencies**: none.

**Risks**:
- Six format-excluded files must not become format-clean; escalate if one does.
- Floors are pinned to planning-base counts, so a deliberate future shrink needs a one-line edit.
- The rich/typer scope must stay `_internal_runtime`, because `runtime_bridge_retrospective.py:158` is sanctioned.

**Estimated prompt size**: ~320 lines

**Prompt file**: [tasks/WP08-runtime-parity-bans-and-residue.md](tasks/WP08-runtime-parity-bans-and-residue.md)

---

Subtask Index rows:

---

## WP09 – Status parity retirement and relocation

**Summary**: Delete `tests/status/test_parity.py` (740 LOC of 0.1x cross-branch scaffold) so that no live invariant is lost (FR-014, NFR-006). Each of the 21 test functions gets a disposition:
- **retire (duplicate)**, naming the survivor and a mutation that turns both tests red;
- **retire (scaffold)**, citing the reason plus a mutation;
- **relocate**, into `test_reducer.py` or `test_transitions.py`, but only where no survivor exists.

The five transition-matrix tests are presumed duplicates of `test_transitions.py`. That presumption is confirmed by mutations M2–M6 before any test is retired. The WP also removes its own `pyproject.toml` format-exclude line.
**Priority**: P2 (US3).
**Independent test**: `pytest tests/status/ tests/architectural/test_no_retired_subsystems.py` is green after deletion. The recorded mutation matrix M1–M10 reds each named survivor or relocated test. Red-first follows D-OP-4 (tracer evidence, no tombstones).

**Subtasks**
T049 Mutation matrix M1–M10 on the planning base; record the disposition evidence via tracer-append (WP09)
T050 Relocate `test_sorted_keys_in_json_output` and the realistic-log fixture plus 2 tests into `test_reducer.py`; retire the determinism duplicates, including dispositions for L407 and L660 (WP09)
T051 Transition-matrix dispositions: retire as duplicates with named survivors; relocate the lane↔enum checks into `TestConstants` only if M5/M6 find no survivor (WP09)
T052 `git rm tests/status/test_parity.py` and remove its pyproject exclude line in the same commit; retire the backport/phase scaffold with cited survivors (WP09)
T053 NFR-006 tracer record and blast-radius validation, including the full `tests/architectural/` run (WP09)

**Implementation sketch**: run the mutation matrix → relocate unique tests in the existing unformatted style → delete the file plus its exclude line → record everything in the tracer.
**Dependencies**: none. The pyproject hunk is about 1,600 lines away from WP07's, so it needs no sequencing.
**Risks**: a mutation leaking into a commit (check `git diff src/` is empty); the lane-enum tests being treated as duplicates by mistake (M5/M6 decide); relocated code becoming format-clean and flipping the exclude ratchet; #4506 landing mid-mission.
**Estimated prompt size**: ~259 lines.
**Prompt**: [tasks/WP09-status-parity-retirement.md](tasks/WP09-status-parity-retirement.md)

## WP10 – Context parity conversion to an on-disk packs fixture

**Summary**: Convert `tests/charter/test_context_parity.py` from patching `src/` internals to a copied `SPEC_KITTY_PACKS_ROOT` packs mirror, with an empty `directives/` and an on-disk fixture profile, driven through the public entry points. Then rename it to `test_context_bootstrap_markers.py` (FR-015, D-OP-5, D-OP-10).
**Priority**: P2 (US3).
**Independent test**: `test_context_markers_use_no_src_patch_targets`. It is RED on base with 8 offenders (6 `patch(` sites plus 2 private calls) and GREEN with 0. The four behavioural markers hold, and a control shows a real directives mirror changes the miss cause.

**Subtasks**
T054 Red-first AST scan `_src_coupling_offenders`, forbidding all first-party patch targets and private calls, plus a planted self-mutation test (WP10)
T055 `_mirror_packs` copy fixture (never symlink) and the on-disk `parity-fixture-agent.agent.yaml` (WP10)
T056 Convert the marker tests; add the pack-root-under-`tmp_path`/no-`UserWarning` assertion and the fixture-mutation control; run the two-order cache check (WP10)
T057 `git mv` to `test_context_bootstrap_markers.py`; update 4 references, including the `context_contract.py` comment with a D-OP-3 AST-equality proof (WP10)
T058 Blast radius, tracer record, and the deferral decision record (WP10)

**Implementation sketch**: red-first scan → mirror fixture → drop every patch while keeping the assertions byte-identical → rename in its own commit → format.
**Dependencies**: none.
**Risks**: process-wide caches (checked in both orders); #3251 fail-open masking a broken mirror (the positive `missing_artifact` and pack-root assertions guard this); scan evasion through aliases (planted alias case). If the markers cannot be reproduced without `src/` patches, defer FR-015; never re-patch privates.
**Estimated prompt size**: ~276 lines.
**Prompt**: [tasks/WP10-context-parity-conversion.md](tasks/WP10-context-parity-conversion.md)

## WP11 – Bridge parity split: P0 board-authority tests out of the oracle module

**Summary**: Move the 13 P0 board-authority tests and the 2 fail-closed direct-call tests (15 functions, 16 nodes) from `tests/runtime/test_bridge_parity.py` into the new `tests/runtime/test_next_board_authority.py`. Their helper closure moves into the new `tests/runtime/_next_mission_scaffold.py`. The oracle module keeps 8 nodes, and the oracle stays untouched (FR-017, C-002, NFR-004).
**Priority**: P2 (US3).
**Independent test**: `test_board_authority_module_does_not_import_the_oracle` is RED on base (fewer than 15 test functions) and GREEN after the move. Node-ID set equality (`func[param]`) holds: 16 in the new module, 8 in the oracle. `--setup-plan` shows no `ledger_results`, and the module runs in under 60 s (recorded, not asserted).

**Subtasks**
T059 Capture the base node-ID sets; add the red-first guard module with `_oracle_coupling_offenders` and a planted self-mutation test (WP11)
T060 Verbatim move of the helper closure into `_next_mission_scaffold.py` (hoisting the imports drops 2 `noqa: E402`); the oracle re-imports from it (WP11)
T061 Verbatim move of the 15 test functions and `_assert_reason_has_runnable_recovery_command` (same "move" commit as T060) (WP11)
T062 Commit 2: `ruff format` the new modules; commit 3: rename helpers to public names and update call sites (WP11)
T063 Update references in `tests/next/test_finalized_task_routing.py:269` and `tests/runtime/fixtures/bridge/README.md` (WP11)
T064 Evidence: node-ID diffs, oracle byte-identity, `--setup-plan`, durations, tracer entries (WP11)

**Implementation sketch**: red-first guard → move (1 commit) → format (1 commit) → rename (1 commit) → references → evidence.
**Dependencies**: none.
**Risks**: an unreadable ~1.6k-line diff (mitigated by 3 commits plus `--color-moved`); hidden fixture dependencies (`--setup-plan`); renames touching oracle assertions (a C-002 breach, so revert). `_bridge_oracle.py` is not edited; its `bridge:NNNN` anchors are deferred to #5116.
**Estimated prompt size**: ~288 lines.
**Prompt**: [tasks/WP11-bridge-parity-split.md](tasks/WP11-bridge-parity-split.md)

## WP12 – Parity verdict catalog (#2631 sweep, 45 modules)

**Summary**: A planning artifact that records a verdict for every module in the #2631 parity/equivalence sweep. The sweep is 49 `find` hits minus the 4 `_support/coverage_safety` helpers, giving 45 modules. The catalog lives at `kitty-specs/<mission>/research/parity-verdicts.md` in #2620 format, with churn (`all/src/mass/pcm/pcsrc`) and an NFR-006 survivor column. A `tracer-append` pointer records it (FR-018).
**Priority**: P2 (US3).
**Independent test**: `research/parity_catalog_check.py --base 3717c7ea` exits non-zero on base (no catalog) and prints `45/45 OK` at WP end. It checks set equality against `git ls-tree`, and that row shape and survivors are present.

**Subtasks**
T065 Red-first stdlib checker `parity_catalog_check.py` (set equality against `git ls-tree 3717c7ea`, row-shape and survivor checks) (WP12)
T066 Author `parity-verdicts.md`: 35 keep rows plus 10 acted-on or deferred rows, each with a named owning WP and survivor (WP12)
T067 Tracer pointer entry, and a reconciliation section handed to WP13 (WP12)

**Implementation sketch**: checker first → catalog from the grounding Part 2 data (a shallow clone, so the churn provenance is cited) → tracer pointer.
**Dependencies**: none. WP13 reconciles the WP08–WP11 rows against the landed code.
**Risks**: unreproducible churn numbers (cite provenance and the command); verdict drift if WP10 defers (the owning-WP column plus WP13 reconciliation catch this); scope creep into consolidating the deferred rows.
**Estimated prompt size**: ~229 lines.
**Prompt**: [tasks/WP12-parity-verdict-catalog.md](tasks/WP12-parity-verdict-catalog.md)

## WP13 – Closeout: pin exemptions empty, retire orphan gate data, format-exclude drain, follow-ups, issue matrix

**Summary**: The mission closeout. It covers:
- pinning `_POSITIONAL_ANCHOR_EXEMPTIONS == frozenset()` and flipping stale rows from warn to fail (FR-003 final, SC-001);
- retiring `tests/architectural/resolution_gate_allowlist.yaml` and its references, including a D-OP-3 comment-only edit to `src/specify_cli/status/aggregate.py:543` (FR-012);
- `ruff format`ting every format-excluded file this mission rewrote and removing their exclude lines in one commit;
- filing the FR-019(d) follow-up for the remaining hand-rolled matchers and verifying #5116/#5117/#5118;
- adding issue-matrix rows via `spec-kitty agent issue-verdict` for #2631, #2972, #3011, #3026, #3962 and #5085 (FR-020, SC-006);
- the final full sweep.

**Priority**: P1 (it gates the mission PR).
**Independent test**: `test_positional_anchor_exemptions_are_pinned_empty` is RED with 94 rows and GREEN with `frozenset()`. The full `tests/architectural/` run, `make test-fast` and `census_rekey_equivalence.py --base 3717c7ea` are green. SC-001..SC-006 are evidenced in the tracer.

**Subtasks**
T068 Red-first `test_positional_anchor_exemptions_are_pinned_empty` (after confirming 0 live findings remain) (WP13)
T069 Empty the exemption set; flip row-without-finding from warn to fail, with a self-mutation test; NFR-003/NFR-004 records (WP13)
T070 FR-012: delete `resolution_gate_allowlist.yaml`, add a `_YAML_ALLOWLISTS` floor, update prose/docs/`aggregate.py` comment with an AST proof, run the orphan-data audit (WP13)
T071 Format-exclude drain: format each AST-changed excluded file and remove its line, in one formatter-only commit (WP13)
T072 File the FR-019(d) follow-up plus the plan's out-of-scope follow-ups; verify #5116/#5117/#5118 (WP13)
T073 Issue-matrix rows via `spec-kitty agent issue-verdict`; close referenced-but-missing gaps; record the FR-020 campsite (WP13)
T074 Final integration sweep (full `tests/architectural/`, `make test-fast`, integration list, equivalence script) (WP13)
T075 SC-001..SC-006 verification, WP12 catalog reconciliation via the tracer, tracer assess step (WP13)

**Implementation sketch**: pin red → empty and flip → retire orphan YAML → formatter-only drain → tracker work → matrix → sweep → SC evidence.
**Dependencies**: WP01, WP02, WP03, WP04, WP05, WP06, WP07, WP08, WP09, WP10, WP11, WP12.
**Risks**: a migration WP leaving a live finding (stop and report, never delete that row); formatting hiding behaviour edits (a formatter-only commit plus `git diff -w`); #4506 landing mid-closeout (re-derive candidates via AST comparison); issue-matrix classification surprises (use `not-applicable`, never hand-edit); C-005 breach (AST proof mandatory).
**Estimated prompt size**: ~335 lines.
**Prompt**: [tasks/WP13-closeout.md](tasks/WP13-closeout.md)

---
