# IC-10 — Re-key and externalise the dead-symbol allowlist + #470 fold (WP11 + WP12)

Per tasks.md closeout step 1, this concern merges WP11's reported evidence (scratchpad
`WP11-evidence.md`: loader + YAML migration, lane tip `cbe7d3278a`) with WP12's reported
evidence (scratchpad `wp12/WP12-evidence.md`: gate re-key + bite battery, excluding the
refresh-helper retirement, which is recorded under IC-11), and both WPs' full approval notes
(`status.events.jsonl`, `review_ref: auto-approval:WP11:20260930` and
`auto-approval:WP12:20260930` — considerably more itemized than the one-line
`review-cycle-1.md` files).

## WP11 — loader + YAML migration

C-011 progression: red `be1c6288eb`, loader `cd6f4289a7`, YAML (green) `cbe7d3278a`.

```yaml
id: EV-IC10a-01
item: FR-009 / T051 converter summary
kind: NO-OP
planted_break: {target: null, description: "migration record, no break", reverted: true}
command: "uv run --frozen python <scratchpad>/convert_allowlist.py <scratchpad>/wp11_allowlist_draft.yaml <scratchpad>/wp11_converter_summary.json (scratchpad-only; + convert_overrides.py hand-review table)"
results:
  literal_count: 294
  member_count: 293          # "294 literals -> 293 members": duplicate specify_cli.consolidation.push_preflight::check_push_safety collapsed
  non_empty_categories: 33
  tombstones_dropped: 9
  widened_entries: 91        # section issue "#633"; 2 per-entry notes carried
  merge_three_layers: "module: charter.drg (module_path wins over charter.offering.drg.merge)"
  module_path_tier_entries: "18/18 mapped to module_path"
  entry_rationales: 52
  entry_issues: 6             # #577, #798, #2761 x2, #5001 x2
  requires_issue: "false for all 33 categories"
  category_b_issue_coverage: {category_b_grandfathered_legacy: "2/149", category_b_t001_unblinded: "0/6"}
  category_b_gaps: 153
  forbidden_keys_in_yaml: 0   # no line / body_hash / source_module
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP11:20260930): "Independent AST cross-check
  of base b5d180ac71 gate: 294 SymbolKey literals -> 293 keys, 0 module/name/category
  mismatches vs YAML, 9 tombstones dropped, 10 random spot-checks correct; 6 extracted issues
  each trace to an adjacent base comment" — the converter's literal/member/tombstone/issue
  counts reproduced independently via a separate AST cross-check. `kind: NO-OP` — not counted
  toward the SC-005 tally. Converter never committed (contract §4).
```

```yaml
id: EV-IC10a-02
item: FR-009 / T053 data-level parity vs WP10 before.json
kind: NO-OP
planted_break: {target: null, description: "parity record, no break", reverted: true}
command: "uv run --frozen python <scratchpad>/wp11_parity.py <scratchpad>/before.json   # at lane tip cbe7d3278a"
results:
  allowlist: "old {(module_path or source_module, bare_name)} = 293, YAML keys = 293, equal=True"
  widened_470: "old 91, YAML 91, equal=True"
  category_parity: "293 entries, 0 mismatches"
  row_digest: "before=ca7087fe74af006129fbc1d8f47f5087a2d26fe2ea60baeaf2e63ed25dcc3d9b after=ca7087fe74af006129fbc1d8f47f5087a2d26fe2ea60baeaf2e63ed25dcc3d9b"
  wp10_form_digest: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1 reproduced from the YAML rows -- equal=True"
  base: "before.json base_sha=68f7418bb4; no rebase, counts unchanged (293/91)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "Parity: wp11_parity.py vs before.json -> allowlist
  293/293 equal, widened 91/91 equal, category parity 0 mismatches, merge_three_layers ->
  charter.drg, 18/18 module_path-tier mapped, row digest equal, WP10 digest c86703f3 MATCH"
  — reproduced independently, matching every figure in this record exactly. `kind: NO-OP` —
  not counted toward the SC-005 tally. Offenders/stale 'after' is WP12's (gate not switched here).
```

```yaml
id: EV-IC10a-03
item: M12 (loader schema battery) run + C-011 progression
kind: FIX
planted_break: {target: null, description: "see EV-IC10a-04..09 for per-rule planted breaks", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q"
results:
  at_be1c6288eb_red_commit: "47 failed; 47 x ModuleNotFoundError: No module named 'tests.architectural._dead_symbol_allowlist'"
  at_cd6f4289a7_loader_commit: "47 failed; each AllowlistSchemaError (YAML not yet committed)"
  at_cbe7d3278a_yaml_commit: "47 passed"
  clean_tree: pass
reviewer_rerun: false
notes: "M12 covers L1-L10 + category-id rules; see per-rule records EV-IC10a-04..09 below."
```

```yaml
id: EV-IC10a-04
item: "M12 / L8 (_check_unique::early-return)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "insert `return` at the top of _check_unique (L8 disabled)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "pass -- the old gate cannot see an intra-category duplicate"
  new_form_under_break: "fail -- 4 failed, 43 passed: dup-same-category, dup-cross-category, dup-entries-and-widened, dup-within-widened"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "L8 _check_unique early-return -> 4 failed/43 passed
  (matches EV-04)" — exactly this record's planted break, reproduced independently
  (47 passed after revert). Tallied in evidence/README.md.
```

```yaml
id: EV-IC10a-05
item: "M12 / L3 (_UniqueKeyLoader.construct_mapping::skip-duplicate-check)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "return super().construct_mapping(...) before the duplicate-key loop (L3 disabled)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "pass -- plain yaml.safe_load accepts all three raw-text plants (last value silently wins)"
  new_form_under_break: "fail -- 3 failed, 44 passed: dup-category-key, dup-entry-field, dup-top-level-key"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "L3 skip dup loop -> 3 failed/44 passed (matches EV-05)"
  — exactly this record's planted break, reproduced independently (47 passed after revert).
  Tallied in evidence/README.md.
```

```yaml
id: EV-IC10a-11
item: "M12 / L7 (requires_issue w/o issue — reviewer-authored plant, no corresponding WP11-reported record)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "disable the L7 check (requires_issue true with no issue field accepted)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  new_form_under_break: "fail -- 1 failed, 46 passed: requires-issue-without-issue"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: true
notes: >
  This record did not exist in WP11's own evidence file (which itemized L8, L3, L9, L5, L6
  and L4 only, EV-IC10a-04..09); it is added here solely because the reviewer's approval note
  (auto-approval:WP11:20260930) describes running it directly: "NEW L7 required_by disabled
  -> 1 failed/46 passed (requires-issue-without-issue)". The L7 schema rule itself is part of
  WP11's own reported M12 coverage list (`EV-IC10a-03`'s notes: "L7 (undeclared category,
  requires_issue w/o issue, malformed issue x2, requires_issue non-bool, widened issue
  missing/malformed)"), so this is the reviewer independently proving a rule WP11 already
  claimed to cover, not inventing new scope. Tallied in evidence/README.md.
```

```yaml
id: EV-IC10a-06
item: "M12 / L9 (_check_no_tombstones::early-return)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "insert `return` at the top of _check_no_tombstones (L9 disabled)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "pass -- the old gate keeps 9 empty frozenset() tombstone categories green"
  new_form_under_break: "fail -- 2 failed, 45 passed: tombstone-category, empty-entries-with-categories"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: false
```

```yaml
id: EV-IC10a-07
item: "M12 / L5 (_check_record_keys::drop-unknown-key-check)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "`if unknown:` -> `if False:` (unknown keys accepted)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "n/a -- no schema existed; test_ratchet_positional_anchor_ban.py does not scan this file"
  new_form_under_break: "fail -- 5 failed, 42 passed: unknown-key-line, unknown-key-body-hash, unknown-key-retired-provenance, unknown-category-key, unknown-widened-key"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: false
```

```yaml
id: EV-IC10a-08
item: "M12 / L6 (_require_text::accept-whitespace)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "drop the `not value.strip()` check (blank rationale accepted)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "n/a -- rationales were free comments, never enforced"
  new_form_under_break: "fail -- 3 failed, 44 passed: empty-category-rationale, empty-entry-rationale, empty-widened-rationale"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: false
```

```yaml
id: EV-IC10a-09
item: "M12 / L4 (_check_top_level::accept-bool-version)"
kind: FIX
planted_break: {target: tests/architectural/_dead_symbol_allowlist.py, description: "drop `type(version) is not int` (schema_version: true accepted, since True == 1)", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -p no:cacheprovider"
results:
  old_form_under_break: "n/a -- no schema version existed"
  new_form_under_break: "fail -- 1 failed, 46 passed: schema-version-bool"
  clean_tree: "pass -- 47 passed after revert"
reviewer_rerun: false
```

```yaml
id: EV-IC10a-10
item: "WP10 contract progression (test_dead_symbol_allowlist_contract.py)"
kind: NO-OP
planted_break: {target: null, description: "progression record", reverted: true}
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q -rxX ; same with --runxfail"
results:
  strict_xfail: "4 xfailed, 0 XPASS (M1, M7, M8, M11)"
  underlying_reason_runxfail: "4 x AttributeError: _evaluate_allowlist (was ModuleNotFoundError before WP11) -- loader exists, gate seam is WP12's"
reviewer_rerun: false
```

WP11 tests run (lane tip `cbe7d3278a`): named-file run 197 passed; contract file 4 xfailed;
ruff/format/mypy 0 findings (C901 clean); `make test-fast` 2169 passed, 5 skipped; `git diff
--stat src/` empty before every commit.

---

## WP12 — gate re-key + bite battery (excluding refresh-helper retirement, recorded under IC-11)

Commits on `kitty/mission-test-suite-remediation-01M3SSDW-lane-l`: `407d57b0f3` (retire the
hash refresh helper, IC-11) and `78ff67177c` (re-key the gate to (module, name) + bite battery).

Out-of-map notes (sanctioned): removed only the strict-xfail marker in
`test_dead_symbol_allowlist_contract.py` (10 deleted lines, 0 added — WP12 depends on WP10,
no parallel collision); trimmed stale line-number refs from one YAML rationale (substance
kept, no base drift per T054).

```yaml
id: EV-IC10b-00
item: "T054 (re-take before.json)"
kind: NO-OP
command: "PYTHONPATH=. uv run --frozen python <scratch>/parity_before.py > <scratch>/before_wp12.json; uv run --frozen python <scratch>/wp11_parity.py <scratch>/before_wp12.json"
results:
  parity_digest_wp10: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
  parity_digest_wp12_rerun: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
  counts: {allowlist: 293, widened_470: 91}
  diff_vs_wp10_before_json: "only base_sha differs (68f7418bb4 -> b534f4247a)"
reviewer_rerun: false
notes: "base unchanged since WP10; YAML not regenerated."
```

```yaml
id: EV-IC10b-01
item: "FR-009 parity (T060.1)"
kind: FIX
command: "PYTHONPATH=. uv run --frozen python <scratch>/parity_after.py <scratch>/before_wp12.json > <scratch>/after.json"
results:
  before_digest: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
  after_digest: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
  counts_before: {allowlist: 293, widened_470: 91}
  counts_after: {allowlist: 293, widened_470: 91}
  offenders: "[] both sides"
  stale: "[] both sides"
  star_targets_on_tree: 0
reviewer_rerun: false
notes: "Committed at closeout as evidence/dead-symbol-parity/{before-wp12,after}.json."
```

```yaml
id: EV-IC10b-02
item: "SC-003 / quickstart Break #19 (FR-009, NFR-003)"
kind: FIX
planted_break:
  target: "src/specify_cli/status/lifecycle_events.py::append_lifecycle_event"
  description: "rename local `envelope` -> `persisted_envelope` (same plant as WP10's EV-IC09-02, now rerun against the re-keyed gate)"
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported -n0 -q"
results:
  old_form_under_break: "fail -- '- specify_cli.status.lifecycle_events::append_lifecycle_event' (1 failed in 81.93s, run against the pre-rekey base worktree)"
  new_form_under_break: "pass -- 2 passed (gate + p1 node), 0 allowlist edits"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP12:20260930): "SC-003 envelope->persisted_envelope
  old RED (append_lifecycle_event offender) / new GREEN 36p" — exactly this record's planted
  break, reproduced independently against both the old and the re-keyed gate. Resolves WP10's
  EV-IC09-02 'pending' line: the re-keyed (module, name) gate is GREEN under the same plant
  that reds the old gate. Tallied in evidence/README.md.
```

```yaml
id: EV-IC10b-03
item: "C-002 covering guard for retiring _refresh_dead_symbol_hashes.py; quickstart Break #20 / M2 at real-tree scale"
kind: RETIRE
planted_break:
  target: "src/specify_cli/dashboard/server.py"
  description: 'add "PlantedDead5346" to __all__ plus `PlantedDead5346 = 1` (a new dead __all__ symbol in an allowlisted module)'
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported tests/architectural/test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate -n0 -q"
covering_guard:
  node_id: "tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported"
  under_break: fail   # names "specify_cli.dashboard.server::PlantedDead5346" (new gate); old gate also fail, same name
results:
  p1_synthetic_plant_under_break: "pass -- test_planted_dead_symbol_still_red_by_dead_symbol_gate green: _compute_offenders path live"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "new dead PlantedDeadR5346 in sparse_checkout_remediation
  both RED, named" — an independent variant of this record's covering-guard proof (a
  different allowlisted module/symbol pair than the WP's own PlantedDead5346 in
  dashboard/server.py, same invariant: a new dead `__all__` symbol is caught by both the old
  and the new gate). Tallied in evidence/README.md. This is the C-002 covering guard for
  retiring tests/architectural/_refresh_dead_symbol_hashes.py and
  test_refresh_dead_symbol_hashes.py (17 tests) — recorded in full under IC-11. Retired-file
  refs: only each other (git grep refresh_dead_symbol); prose refs left for WP15
  docs/development/reference/ci-gate-mechanics.md:190 and WP13 tests/architectural/README.md:48.
```

```yaml
id: EV-IC10b-04
item: "quickstart Break #21 (REVIVED)"
kind: FIX
planted_break:
  target: "src/specify_cli/status/lifecycle_events.py"
  description: "append `from specify_cli.dashboard.server import BackgroundPortReportError` (allowlisted symbol gains a src caller)"
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported -n0 -q"
results:
  old_form_under_break: "fail -- 'Stale _SYMBOL_ALLOWLIST entries ... - specify_cli.dashboard.server::BackgroundPortReportError'"
  new_form_under_break: "fail -- '- specify_cli.dashboard.server::BackgroundPortReportError [REVIVED] the symbol has a caller again; delete the entry'"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "REVIVED (STEP_USER_DECLINED imported from api_types): old
  stale / new [REVIVED]" — an independent variant of this record's REVIVED proof (a different
  allowlisted symbol than the WP's own BackgroundPortReportError, same invariant: an
  allowlisted symbol that regains a caller is reported [REVIVED] by the new gate, where the
  old gate only reported it stale). Tallied in evidence/README.md.
```

```yaml
id: EV-IC10b-05
item: "WP10 ATDD contract (M1, M7, M8, M11) chain-level GREEN (C-011 D1)"
kind: FIX
command: "uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py ... -n0 -q -rA"
results:
  before_lane_head_b534f4247a_markers_present: "4 xfailed (strict, raises=(ImportError, AttributeError))"
  after_78ff67177c_markers_removed: "4 PASSED: test_m1_body_edit_of_allowlisted_dead_symbol_stays_green, test_m7_rename_reports_gone_and_new_offender, test_m8_move_reports_gone_with_moved_hint_and_new_offender, test_m11_gate_reads_the_allowlist_file_it_is_given"
  diff_of_contract_file: "10 deletions, 0 insertions (marker definition + 4 decorators)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "C-011: contract M1/M7/M8/M11 PASSED (0 xfail)" — this
  record's chain-level GREEN result, reproduced independently. Tallied in evidence/README.md.
```

```yaml
id: EV-IC10b-06
item: "M11(c) widened authority parse (F-05)"
kind: FIX
planted_break:
  target: "tests/architectural/test_no_dead_symbols.py::_apply_widened_scope_exemptions"
  description: "read the import-time global _WIDENED_SCOPE_GRANDFATHERED_470 instead of the grandfathered parameter (the pre-F-05 shape)"
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_m11c_gate_reads_the_widened_section_it_is_given -n0 -q"
results:
  old_form_under_break: "n/a -- no widened authority-parse test existed"
  new_form_under_break: "fail -- assert [] == ['charter.activation._io::load_charter_bytes']"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "MUTATIONS: _apply_widened_scope_exemptions reading
  _WIDENED_SCOPE_GRANDFATHERED_470 -> M11c RED (assert [] ==
  ['charter.activation._io::load_charter_bytes'])" — exactly this record's planted break and
  result, reproduced independently. Tallied in evidence/README.md.
```

```yaml
id: EV-IC10b-07
item: "G1 keyability precondition (M9 / p1 G1 control)"
kind: FIX
planted_break:
  target: "tests/architectural/test_no_dead_symbols.py::_compute_offenders"
  description: "drop `final_key is not None and` from the allowlist exemption"
  reverted: true
command: "pytest ...::test_bite_f_undecidable_key_fails_closed ...::test_gate_still_flags_a_truly_dead_symbol tests/architectural/test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate -n0 -q"
results:
  new_form_under_break: "fail -- 3 failed: assert [] == ['synthetic.ghostmod::Ghost'], assert [] == ['synthetic.d...everImported']"
  clean_tree: pass
reviewer_rerun: false
```

```yaml
id: EV-IC10b-08
item: 'GONE "probably moved to" hint (M8)'
kind: FIX
planted_break:
  target: "tests/architectural/test_no_dead_symbols.py::_gone_hint"
  description: "always return the plain GONE hint"
  reverted: true
command: "pytest tests/architectural/test_dead_symbol_allowlist_contract.py::test_m8_move_reports_gone_with_moved_hint_and_new_offender tests/architectural/test_no_dead_symbols.py::test_gone_hint_names_every_candidate_new_home -n0 -q"
results:
  new_form_under_break: 'fail -- 2 failed ("probably moved to `pkg.b`" not in hint)'
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "move STEP_VERIFY_CLEAN sparse->dashboard.server: old
  real-tree GREEN (relocation-proof), provenance guard RED / new [GONE] probably moved to +
  offender" — an independent variant of this record's "moved" proof (a different symbol than
  the WP's own `pkg.a`/`pkg.b` fixture pair, same invariant: a genuinely moved symbol gets the
  "probably moved to X" hint from the new gate). Tallied in evidence/README.md.
```

```yaml
id: EV-IC10b-09
item: "M13 corpus floor (§2.1 non-vacuity)"
kind: FIX
planted_break:
  target: "tests/architectural/test_no_dead_symbols.py::_corpus_floor_shortfall"
  description: "return [] unconditionally (vacuous floor)"
  reverted: true
command: "pytest tests/architectural/test_no_dead_symbols.py::test_m13_corpus_floor_reds_on_a_quarter_of_the_modules -n0 -q"
results:
  new_form_under_break: "fail -- assert 0 == 2"
  clean_tree: pass
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "M13 on truncated copy, no walker monkeypatch" —
  confirms this record's non-vacuity mechanism independently. Tallied in evidence/README.md.
  M13 drives a truncated COPY of _real_tree_inputs().all_literal_decls (first quarter of 656
  modules); no walker monkeypatch (F-06).
```

```yaml
id: EV-IC10b-11
item: "reviewer's own expanded adversarial battery (old gate vs. new gate), beyond the WP-reported quickstart breaks"
kind: NO-OP
command: "full test_no_dead_symbols.py, old gate in a scratch base worktree vs. the new gate, each plant reverted, git diff --stat src/ empty after each"
results:
  control: "old 35 passed / new 36 passed"
  gone_bibtex_pattern: "BIBTEX_PATTERN def+__all__ deleted -- old dangling / new [GONE]"
  annassign_dead: "PLANTED_ANN5346:int (AnnAssign form) -- both RED, named"
  rename_with_false_red_control: "APA_PATTERN->APA_PATTERN_RENAMED -- old dangling+offender (plus a false-red is_apa_format body-edit control) / new [GONE] APA_PATTERN + offender APA_PATTERN_RENAMED"
  byte_identical_twin: "STEP_USER_DECLINED duplicated byte-identically in dashboard.server -- old flags rogue AND the allowlisted original (false red) / new flags rogue only"
  star_import_moot: "star import of sparse_checkout_remediation + dead PlantedStarDead5346 -- old GREEN (MISS) / new RED 7x [MOOT] (new dead name in a star target, unnamed by both -- pre-existing skip, non-goal)"
  dropped_from_all: "STEP_SPARSE_DISABLE dropped from __all__ -- old dangling / new [GONE]"
  ghost_invalid: "def of STEP_USER_DECLINED deleted, kept in __all__ -- both offender, new additionally flags [INVALID] + bite_k red"
  classifier_battery: "no-SUPERSEDED/no-MOOT/no-INVALID/no-REVIVED/stale-over-empty-keys/exempt-by-name-only each individually killed (1-5 battery failures)"
reviewer_rerun: true
notes: >
  Quoted verbatim from the approval note (auto-approval:WP12:20260930), which describes 11
  adversarial plants total (old gate vs. new gate). Several map directly onto this IC's own
  recorded items (SC-003 -> EV-IC10b-02; the new-dead-symbol covering guard ->
  EV-IC10b-03/EV-IC11-00; REVIVED -> EV-IC10b-04; the move/GONE-hint case -> EV-IC10b-08) and
  are cross-referenced there. The remainder — the plain GONE case (no "moved to" hint
  available), the AnnAssign form, the rename-with-false-red-control, the byte-identical-twin
  (bite_i), the star-import MOOT case, the dropped-from-`__all__` case, and the
  ghost/INVALID+bite_k case — exercise battery tests from the "Battery map" section below
  (M4/bite_i, M6, M9/bite_k, MOOT handling) that were never given their own per-test evidence
  id in WP12's own `wp12/WP12-evidence.md`. They are consolidated here, as `kind: NO-OP`
  (verification only, not a separate WP-reported inventory item), rather than invented as
  individual FIX/RETIRE records — not counted toward the SC-005 tally, but recorded so none
  of the reviewer's reported work is lost.
```

## Battery map (contract §3, as reported)

M2 (rebased: DeadSymbolKey allowlist control, G1 un-keyable control, new dead `New` beside
allowlisted name), M3 (rebased: same-name fan-out), M4 (byte-identical rogue sibling, no
key_tier/escalation), M5 (wired allowlisted symbol reports revived), M6 (deleted allowlisted
symbol reports gone, new), M9 (undecidable key fails closed + corpus-scale keyability),
M10 (name dropped from `__all__` reports gone, new), M11(c) (widened section authority, new),
M13 (corpus floor, new); kept: bite_e, auto-exempt disjointness, widened #470 tests, the
dynamic-accessor tests; retired: bite_b/bite_g/bite_j (single-alias relocation arm)/the two
content-tier/source-module guards/the duplicate-category guard (now in loader's L8/M12).

## Wall time (F-07, as reported)

`test_no_dead_symbols.py` alone: before (`b534f4247a`) 35 passed in 110.44s; after
(`78ff67177c`) 36 passed in 109.80s (one real walk per session, was 6).
