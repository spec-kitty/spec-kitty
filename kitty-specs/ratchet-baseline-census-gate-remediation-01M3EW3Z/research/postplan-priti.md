# Post-plan brownfield squad — planner-priti lens (foldable issues, deprecations, LOC/sizing)

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z` · HEAD `5940b8ca` (only mission artefacts changed since planning base `3717c7ea`, so research line refs still hold) · READ-ONLY.

## Governance applied
- **Profile `planner-priti`:** I worked in decomposition, sequencing, risk and prioritisation modes. Boundaries: no code, and no architectural decisions; design questions go to the architect as recommendations. Directive ref 003.
- **`charter context --action plan`:**
  - DIRECTIVE_044, single canonical authority. Used for the FR-019 ordering finding and the identity-mechanism note.
  - DIRECTIVE_041/043, test-remediation and gate discipline. Used for red-first and non-vacuity.
  - RECONCILE_CHANGE_SCOPE_TENSIONS. Used for the fold/ignore calls on campsite versus scope creep.
  - DIRECTIVE_045/046, git and PR discipline. Used for the one-PR interim state and the pyproject hunks.
  - Pre-existing-failure reporting rule.
  - No tactics resolved for `plan` (tactic IDs: none).

## Findings

[HIGH] plan.md WP table (WP06 deps) + WP12 (FR-019) — **ordering contradiction**
- WP06's precondition is "FR-019(b) issue filed", but FR-019 is owned by WP12, which depends on *all* WPs including WP06.
- As written, WP06 can never start.
- **Recommendation:** move FR-019(a/b/c) filing out of WP12 into an operator pre-step, either a WP00 or a "before implement" item in tasks.md. Keep only the check that the issues exist (SC-006) in WP12.

[HIGH] WP06 — **> 600 changed lines, and two unrelated concerns**
- Estimate: `_inert_slots.py` −330; `_inert_slots_baseline.yaml` −~200 (owner/provisional on 38 rows plus the `code_only_suppressions` section); `test_ratchet_baselines.py` hoist −~200 duplicated tables / +~110 table / +~120 new tests / −~100 category_1 and skip_marker tests; `_baselines.yaml` −~40.
- Total ≈ +250 / −950, about 1.2k diff lines.
- It mixes FR-011 (a new enforcement design) with FR-010 (a deletion).
- **Recommendation:** split it and put FR-011 first:
  - **WP06a (FR-011):** hoist `_SIZE_RATCHETS`; `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` RED names 4 leaves; delete the 4 leaves plus the category_1/skip_marker code and tests. The two inert leaves have no readers, so deleting only their YAML is behaviour-free. **No FR-019(b) dependency.** About ±500.
  - **WP06b (FR-010):** retire the inert-slot machinery, the stale rows, `baseline_entries 38→36` and the per-walk floors. It is a D-OP-4 deletion WP, depends on WP06a (same `_baselines.yaml`, same lane) and is the only part gated on FR-019(b). About −650.
- This unblocks FR-011 on day 1 and keeps the #3285-class risk (losing the `model` detector) isolated.

[MEDIUM] WP01 — **sizing about 650–750 changed lines, borderline**
- Estimate: arms and widening +~200 / −~60; 4 inversions ±~60; ~12 new fixtures +~120; floors and per-arm self-mutations +~80; 94 interim rows.
- The rows are +94 if each row is one line (the ban file is format-excluded, pyproject L1019, so single-line rows are allowed), or up to +~560 if they are written multi-line.
- WP12 then deletes the same rows.
- **Recommendation:** keep the WP whole, since it is cohesive, but mandate **one line per row** and a stable sort, so the WP01 and WP12 diffs are ~±94 each.
- Optional alternative for the architect: drop D-OP-7's interim rows by taking WP01's red-first from the new planted-fixture tests, which are RED on base because the arms do not exist, and make WP01 depend on WP02/WP03/WP05.
  - This removes about 190 lines of churn and the interim warn-path.
  - It costs one M WP on the critical path.
  - Record the choice in tracer-design-decisions either way.

[MEDIUM] pyproject.toml format-exclude hotspot is **under-declared**
- The plan names only WP07 (L954-955) and WP09 (L2553). The following are also format-excluded and edited by other lanes:
  - WP01 (ban file, L1019);
  - WP06 (`test_ratchet_baselines.py` L1018, `test_no_inert_schema_slots.py` L1005);
  - WP08 (`test_internal_runtime_parity.py` L1809, plus the 4 F4 files);
  - WP11 (`test_bridge_parity.py` L1909).
- If an edit leaves one of these files format-clean, `test_every_exclude_entry_still_genuinely_reformats` goes red, and that lane must edit pyproject too. L1018 and L1019 (WP06 and WP01) are adjacent, so removing both in parallel lanes causes a merge conflict.
- Conversely, the WP07→WP09 dependency exists only for pyproject, and its hunks are about 1,600 lines apart, so they merge cleanly. That dependency is unnecessary serialization.
- **Recommendation:**
  - Every WP that edits an excluded file owns its own exclude line in `owned_files`.
  - Add the rule "keep excluded files unformatted; if one becomes clean, remove its own line only".
  - Serialize WP01 and WP06 on pyproject, or forbid removing L1018/L1019.
  - Drop WP07→WP09, or keep it only as lane grouping.

[MEDIUM] #4506 (drain ruff-format exclude, 2.5k-file reformat) — **COORDINATE, live collision risk**
- PR #4808 was closed as stale, and the issue was re-claimed by the factory dispatcher on 2026-09-22 (label `status:claimed`).
- If it lands mid-mission, every format-excluded file this mission edits conflicts: WP01, WP06, WP08 (5 files), WP09, WP11.
- **Recommendation:** the operator comments on #4506 asking to land before this mission's lanes branch, or to hold until this mission's PR merges. Record this in the tracer. Do not fold it (format-only sweep, different epic, #1928).

[MEDIUM] WP11 — **about 1.6k diff lines, mechanical but hard to review**
- About 780 moved lines: helpers L70-370 and the P0 block L1383-1862.
- The target modules are *not* format-excluded, so the moved code is also reformatted.
- Renaming helpers to public names ripples into the residual oracle call sites.
- **Recommendation:** do not split, because each half would need its own ~440 s oracle run. Instead mandate three commits:
  1. a verbatim move;
  2. `ruff format` of the new modules;
  3. the rename.
- The PR carries `git diff --color-moved` evidence plus the 16-node set diff.
- Consider keeping the original helper names in the scaffold, or aliasing them, to shrink the oracle-side churn.

[LOW] WP12 — **"S" is optimistic, and it mixes code with operator/doc work**
- It covers: deleting 94 rows and pinning empty, deleting the YAML and editing prose, the 45-row FR-018 verdict catalog, the matrix, #2972 campsite work, and the optional `aggregate.py` comment.
- **Recommendation:**
  - Keep WP12 for the code closeout (FR-003 final and FR-012).
  - Move the FR-018 catalog to an early parallel docs WP. Its data is research output and does not need the other WPs finished; only its final verdict column is confirmed at WP12.
  - Mark FR-020 matrix rows as an operator task.

[LOW] WP05 — an unlisted rewrite
- `test_mutation_ownership_routing.py:103` `_RESEARCH_PY_ALLOWLIST_PREFIX = "…/research.py:"` and its guard at :533-545 rely on the `path:line:op` key shape.
- **Recommendation:** name it in WP05 and convert it to a `CensusKey.rel` check.
- Sizing is otherwise fine: the allowlist block is L238-442 (205 lines), about ±250, plus a drift test.

[LOW] WP05 ↔ WP06 — cross-lane semantic coupling (the #1979 class)
- `test_ratchet_baselines.py:464-467, 626-629` read `len(test_mutation_ownership_routing._ALLOWLIST)`.
- If WP05 changes the container type while WP06's new `test_lowering_an_enforced_leaf_below_live_fails` inflates attrs via `_synthetic_frozenset`, both are green in their own lanes but can diverge after merge.
- **Recommendation:** WP05 keeps `_ALLOWLIST` a sized mapping of 56 entries, and the integration run after consolidation must include `test_ratchet_baselines.py` (it already does in G3).

[LOW] WP10 — #3251(3) (`SPEC_KITTY_PACKS_ROOT` set-but-invalid falls through to the installed packs rather than failing closed)
- A broken mirror, for example after a symlink failure on Windows, silently resolves the real catalog.
- The research control shows the *no-knob* case yields `typo_suspected`. The with-knob test must assert `missing_artifact` positively, which it does, and should also assert that the resolved pack root is under `tmp_path`.
- This is not a deprecation: the knob is canonical per closed #3494. If #3251(3) later flips to fail-closed, a valid mirror is unaffected.

[INFO] C-004 "one identity mechanism"
- `_symbol_key.py` (732 LOC) and `_symbol_identity.py` are separate identity mechanisms for the dead-symbol scanner.
- **Recommendation:** scope C-004's wording to "allowlist/census gates in this mission" so a reviewer does not read the mission as failing C-004.

[INFO] Other WPs are within bounds
- WP02: about +350/−60.
- WP03: about +200/−40.
- WP04: about +500/−100, plus the CSV and the script.
- WP07: about −1.54k, a pure deletion of the audit directory (808+274+144+129+114+68), plus a small scanner move.
- WP08: about ±450 across 5 files; it mixes FR-013 and FR-016, which is justified because FR-016 borrows FR-013's red.
- WP09: −740 / +~220 relocated.
- WP10: about +350/−428, one file.

## Q4: `tests/contract/test_next_no_unknown_state.py:40` → **FOLD into WP08**
- The scan target is `src/specify_cli/next`. `rglob` over the missing directory yields 0 files, so the test can never fail. This is the same defect class as FR-013.
- It is the **only** such scan: `grep` for `specify_cli/next` finds only history strings and docstrings otherwise.
- The fix is about +30/−5:
  - retarget to `src/runtime/next` (confirm that the placeholder emitter lives there);
  - add the `is_dir()` + ≥N-files floor;
  - add a planted-placeholder test.
- Its red-first is behavioural: 0 files inspected on base.
- WP08 already owns the analogous change and runs `tests/next/`. Add `tests/contract/test_next_no_unknown_state.py` to its owned files and blast radius.
- Leaving it as a follow-up contradicts SC-005 ("0 parity bans pass when their scan target is empty") in spirit, and costs a separate PR for about 35 lines.

## Q1: Foldable-issue search (OPEN issues; semantic search was rate-limited twice, backfilled with `list_issues` over the 200 most recently updated open issues and sub-issue reads of #5104/#5106/#5107)
| Issue | Verdict | Reason |
|---|---|---|
| #3962 inert-slots owner gate | FOLD (already) → WP06b | same deletion |
| #2560 runtime_bridge degod query slice | COORDINATE (WP11) | P2 backlog, unassigned. It touches `src/runtime/next/runtime_bridge.py`, not the tests; risk is only that the P0 tests' import surface moves. Post a one-line heads-up and do not fold (src change, C-005) |
| #4506 ruff-format drain | COORDINATE (all WPs editing excluded files) | see MEDIUM above; re-claimed and could land mid-mission |
| #3206 kernel/schema_utils exemption | COORDINATE (WP03) | its AC "remove two entries" becomes "delete two descriptors"; src decoupling is out of C-005 |
| #4727 route `windows_paths._current_platform()` | COORDINATE (WP03) | new hit. It owns the `os-detect-ban-deferred.txt` entry that WP03 migrates, so its AC "entry removed" becomes "descriptor removed". It is a src change; do not fold |
| #2633 delete runtime_bridge delegates | COORDINATE (C-002) | gates the oracle retirement follow-up |
| #5061 positive controls for refusal/absence criteria (#5107) | COORDINATE / cite | NFR-002 is an instance; cite it in the tracer, no work |
| #5068 ATDD "red for the intended reason" (#5107) | COORDINATE / cite | every WP's red-first evidence should record the RED failure text (e.g. WP01's 6/2/22/56/2/6 breakdown) |
| #1979 shared contract pinned outside owned_files (#5106) | COORDINATE | the WP05↔WP06 coupling above is an instance; the integration run covers it |
| #3043 read-bypass primitive absent from gate census/classification ledger | IGNORE (note) | WP12 edits `read-side-seam-classification.md` prose only; different defect |
| #3461 tautological drift test (shape_registry) | IGNORE | same vacuity class, different subsystem; C-003 scope discipline |
| #2986 runtime→doctrine ratchet misses function-local imports | IGNORE | `_LAZY_BASELINE_ALLOWLIST` is (path, module) pairs, not line-pinned; WP06's `_SIZE_RATCHETS` must keep its leaf row |
| #4986 post-merge review passes without issue matrix | IGNORE | stale/silent-pass test outside the gate family |
| #4874 clean-merge parity integration fixtures fail | IGNORE | not in the `*parity*`/`*equivalence*` sweep (merge safety tests); pre-existing red |
| #3487 sole-door gate exclusion | IGNORE | path/construct exclusion, not line-pinned |
| #4361 P1 planted-regression oracle count | IGNORE | dead-symbol scanner family |
| #3251 PACKS_ROOT fail-closed decision | COORDINATE (WP10, LOW) | see LOW above |
| #3026 / #3011 / #5085 / #2631 / #2972 | in scope | per spec |
| #2023, #4901, #4365, #4392, #2625 | IGNORE | closed |

No open hits for: `_baselines.yaml`, `resolution_gate_allowlist`, `test_resolution_authority_gates`, status `test_parity`, context parity, `test_next_no_unknown_state`, bridge oracle split (only #2631), overwrite/mutation ownership census (#4901 closed), os-detect exemptions (only #4727). There is a residual miss risk because of the rate limits: 200 of 857 open issues were title-scanned.

## Q2: Deprecation check
- `_ratchet_keys` (`composite_key`/`ContentDescriptor`/`resolve_descriptor`): no open deprecation or removal. It is the substrate #5085 names. OK.
- `test_trio_seam_only` pattern: exemplar only; the research already rejects its import-time resolve. No deprecation issue. OK.
- `SPEC_KITTY_PACKS_ROOT`: canonical (closed #3494). #3251(3) may later change the set-but-invalid behaviour; WP10 is safe with a valid mirror plus a positive control.
- `is_file_line_anchor` (production): untouched per A1. OK.
- `test_ruff_format_exclude_ratchet` / `test_ruff_format_enforcement` (used in WP07/WP09 blast radius): **slated for retirement by #4506**. If #4506 lands first, drop them from the blast radius and remove the exclude-line edits entirely.
- `src/specify_cli/next`: deleted (confirmed absent), which drives the Q4 fold.

## Verdict
**PASS WITH CHANGES.**
1. Fix the FR-019 ↔ WP06 ordering deadlock (HIGH).
2. Split WP06 into FR-011-first and FR-010 parts (HIGH).
3. Declare per-WP ownership of the pyproject exclude lines and coordinate #4506 (MEDIUM).
4. Fold `test_next_no_unknown_state.py:40` into WP08.

Everything else is advisory. This takes the plan from 12 to 13 WPs; the critical path is unchanged (WP02→WP04→WP05→WP12).
