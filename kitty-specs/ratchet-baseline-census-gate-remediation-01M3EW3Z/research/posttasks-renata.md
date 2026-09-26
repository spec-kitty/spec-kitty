# Post-tasks anti-laziness squad: Reviewer Renata

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Point-cut: post-tasks. Lens: fakeable Definitions of Done and red-first integrity.
Read: spec.md, plan.md, tasks.md, tasks/WP01..WP13 (all 13 prompts). Base SHA `3717c7ea` resolves in this clone (`git cat-file -t` returns `commit`, even though the repo is shallow).

## Governance applied

- **Profile `reviewer-renata`** (`spec-kitty agent profile show reviewer-renata`). I act as a quality gate and do not implement. The directives I apply are 001, 024, 030, 032, 041 and 051. The tactics I apply are `delete-the-assertion-not-the-test`, `test-scaffolding-as-design-smell`, `test-readability-clarity-check` and `reverse-speccing`.
- **`charter context --action tasks`**:
  - DIRECTIVE_041 and DIRECTIVE_043: gate non-vacuity, a concrete floor, and self-mutation through the real scan path.
  - DIRECTIVE_044: single authority.
  - USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY.
  - ATDD-first discipline (C-011).
  - Standing Orders #4 and #5.
  - Burn-down policy (shrink-only).
- **Constraints**: this was a read-only pass. I made no repo edits.

## Overall

The prompts are unusually strong. Most WPs already name exact RED tests, concrete floors, invert-not-delete, and self-mutation through the real helper. The residual fakeability falls into four classes:

- **(a) Vacuous-equality drift tests.** Two sets that are both empty compare equal.
- **(b) Tautological "count equals derived set" companions.** The parameter set and the expected set come from the same expression.
- **(c) Evidence without a reviewer-reproducible command.** This covers scratchpad files, the planning-surface script, and hand-run mutation matrices.
- **(d) Floors that count the guard's own tests, or accept `n/a` everywhere.**

## Cross-cutting (apply to all code WPs)

- **[HIGH] ALL §Review Guidance: the RED can't be re-run mechanically.** Reviewers can't re-run the RED on the base commit today. Add this block to every prompt:
  "Reviewer RED reproduction:
  `RED=$(git log --reverse --format=%H <lane-base>..HEAD | head -1); git stash -u; git checkout $RED && <exact pytest -k command> ; git checkout -`.
  It must fail with `<expected assertion substring>`, and must not fail with an ImportError, NameError or collection error."
  Fill in the command and substring per WP. The values are listed below.
- **[HIGH] WP02/WP03/WP04 §drift tests: the drift test is vacuous-equality fakeable.** "`(unexpected, suppressed)` identical before/after" passes when both are empty. That happens if the finder, the seam, or the resolution returns nothing. It matters most for the census gates, which only warn on stale entries, so a dead scan stays green. Add this to every drift test:
  "Also assert `len(suppressed_for_file) == <number of allowlist entries whose rel_path == file>` on the unmutated run, and that the mutated run's `suppressed` has the same count."
- **[HIGH] WP02/WP03/WP04 §drift tests: the companion count test compares a set with itself.** The parameter set is derived from the allowlist, and the companion then asserts it equals the set derived from the allowlist. That is a tautology. Replace it with:
  "The parametrize list is a module constant `_DRIFT_FILES = tuple(sorted({d.rel_path for d in <allowlist>}))`. The companion test asserts `len(_DRIFT_FILES) >= N` (join 3, kernel 1, os-detect 3, destructive 15, overwrite 2, mutation 21). It also asserts that every file in `_DRIFT_FILES` has ≥1 suppressed finding on the unmutated tree."
- **[MEDIUM] WP02/WP03 §drift: descriptors resolve against disk, not the mutated source.** The descriptors are resolved through the `functools.cache` accessor, which reads the file on disk. So resolution drift, where a descriptor stops resolving or resolves twice after the mutation, is never exercised. Add:
  "The seam takes `source_for` from the same (mutated) mapping. The drift test calls `resolve_allowlist(..., source_for=mutated.__getitem__)` and bypasses the cached accessor."
- **[MEDIUM] Traceability: `requirement_refs` under-declare ownership.**
  - NFR-002 is declared only by WP01. WP05, WP08, WP10, WP11 and WP13 also implement it.
  - NFR-006 is missing from WP06 and WP08, which both retire tests.
  - The census half of FR-007 is missing from WP04.
  - NFR-003 is missing from WP05 and WP13.
  - NFR-005 is declared only by WP04.
  - No WP declares any SC.

  Add the refs so coverage can be checked mechanically.

## Per-WP findings

**WP01**
- **[MEDIUM] §T004.4: the exemption filter is a set, not a multiset.** The filter uses `(relpath, symbol, site)` set identity. Two textually identical sites in one symbol would collapse to one row, which silently re-opens "per symbol" exemption. Add: "Filtering and exactness use `collections.Counter` over `(relpath, symbol, site)`: one row suppresses exactly one finding. Add a negative fixture with two identical tuples and one row → one finding unexpected."
- **[MEDIUM] §T005.2: an arm-disable check can be defeated by an overlapping arm.** The embedded-key arm and the kept `is_file_line_anchor` arm overlap, so disabling one arm may not zero its fixture. An implementer may weaken the assertion to "count decreased". Add: "For each arm, use a fixture that only that arm catches (record in the docstring which fixtures ≥2 arms catch), and assert exactly 0 findings after the disable."
- **[LOW] §T005.1: the text-line floor is trivially met.** "≥6 entry lines" across 20 `.txt` files is satisfied with no effort. Add "≥6 entry lines across `os-detect-ban-*.txt`".
- **RED command**: `pytest tests/architectural/test_ratchet_positional_anchor_ban.py -k "no_int_line_sink_in_architectural_python_seeds or no_positional_anchor_in_architectural_text_files"`. Expected: the per-symbol breakdown 6/2/22/56/2/3/2/1.

**WP02**
- **[HIGH]** The cross-cutting drift findings apply.
- **[LOW] §T010.1: the non-widening test has no RED-on-base claim.** Add: "This test is also RED on base: the planted join at old L88 is suppressed by the `(kernel/paths.py, 88)` pin. Record it in the RED tracer entry."
- **RED command**: `pytest tests/architectural/test_built_in_location_authority.py -k "suppress_a_live_join or survives_line_drift"`. Expected: the failure names `src/kernel/paths.py` 88 and `src/specify_cli/runtime/home.py` 79.

**WP03**
- **[HIGH]** The cross-cutting drift findings apply. The kernel file set is 1, which is especially weak.
- **[LOW] §T014.2: no guard against a `path:line` row returning.** Add: "Assert via the WP01 text arm, called directly with `_scan_text_source`, that each rewritten `os-detect-ban-*.txt` yields 0 findings." Put this in the committed test, because WP01 may not be on the lane base.
- **RED command**: `pytest tests/architectural/{test_kernel_no_doctrine_import,test_os_detection_ban,test_lock_primitive_ban,test_clock_call_ban}.py -k "line_drift or rejects_line_pinned"`. Expected: drift set mismatch, plus `DID NOT RAISE ValueError` ×3.

**WP04**
- **[HIGH] §T020/T025: the equivalence proof isn't reproducible, and the script never proves it can fail.**
  - The script lives on the planning surface, is "not in lane commits", and nothing says who commits it. It also imports "the new gate modules" without saying which checkout they come from. Run from the primary checkout, it imports unmigrated gates.
  - Replace with: "`census_rekey_equivalence.py --base 3717c7ea --head-root <lane-worktree-abs-path>` inserts `<head-root>` at the front of `sys.path`. The script and CSV are committed on the planning branch before WP04 review, and the SHA is recorded in the Activity Log."
  - Add a `--self-test` mode that flips one new key's `op_ordinal`, drops one key, and swaps one rationale. It must exit non-zero for each, and its output goes in the PR, so it can be shown the script is able to fail.
- **[MEDIUM] §T017.3: the changed-argument test can be skipped per gate.** "Per gate where the op family allows it" is an escape hatch. Change it to: "in all three gates; if an op family truly cannot express a token-changing argument edit, record the reason per gate in the tracer and the reviewer must accept it."
- **[MEDIUM] Census gates have no floor.** A census gate whose finder silently scans 0 files passes with warnings only. Add a `checked == len(_ALLOWLIST)` floor ("suppressed == len(_ALLOWLIST) on the live tree") to each census gate test, or explicitly in the drift companion.
- **RED command**: `pytest tests/architectural/{test_destructive_op_routing,test_overwrite_ownership_routing,test_mutation_ownership_routing}.py -k "line_drift or changed_argument"`.

**WP05**
- **[MEDIUM] §T029.2: the new branch has no test.** "Parser rejects retired keys" appears only as a reviewer spot-check, so this is a new branch with no test (Sonar). Add: "`test_load_baseline_rejects_retired_keys(tmp_path)`: a row with `owner:`, one with `provisional:`, and a top-level `mission:` each raise `BaselineError` naming the key." This is behavioural, not a tombstone.
- **[LOW] §Review 2: the evidence order is checked by timestamps, which can be forged.** "Compare commit order with tracer timestamps" is not a real check. Replace with: "The reviewer re-runs the T027 greps and `pytest -rw` at `git worktree add <tmp> 3717c7ea`."
- **[LOW] §T031.2: the no-warning claim is asserted by eye.** Make it mechanical with `pytest tests/architectural/test_no_inert_schema_slots.py -W error::UserWarning`.

**WP06**
- **[MEDIUM] §T037.1: the match string does not pin the row's own leaf.** `match=re.escape(row.attr)` is satisfied even if a row reads a different leaf whose failure line prints the same attr. Change it to: "match both `f\"{row.section}.{row.leaf}\"` and `row.attr` in the failure line."
- **[MEDIUM] §Review 1: a row can point at a dummy attr.** A `_SIZE_RATCHETS` row pointing at a dummy attr satisfies both the leaf test and the lowering test. Add the check: "for each row, `grep -n <attr> <module file>` shows the attr consumed inside the owning gate's test function, not just defined."
- **[LOW] §T037.5: the NFR-003 check is a grep read by eye.** Replace it with: "`python -c` flattening base vs head YAML leaves; assert `head[k] <= base[k]` for every common leaf". Record the output.
- **RED command**: `pytest tests/architectural/test_ratchet_baselines.py::test_every_baseline_leaf_is_enforced_by_a_size_ratchet`. Expected: `category_1_auto_discovered_migrations` and `skip_marker_blocks`.

**WP07**
- **[LOW] §T041 Validation: the base node-ID set isn't pinned to the base.** "Diff the node IDs against the base" has no base artefact. Add: "`git worktree add <tmp> 3717c7ea`, run `pytest --collect-only -q` there, and diff." The same applies to the T038 evidence.
- **[LOW] Excluded directory not justified.** The T038 search excludes `docs/plans/engineering-notes/`. Justify why that directory is not "live docs" under SC-003, or drop the exclusion.

**WP08**
- **[MEDIUM] §Test Strategy: mypy skips three changed files.** mypy is run on 3 of the 6 changed files, but NFR-005 applies to all changed files. Add `test_execution_context_parity.py`, `test_transition_gate_parity.py` and `test_docs_cli_reference_parity.py`.
- **[MEDIUM] §T047.6: the planted-divergence test can re-implement the loop.** "Drive the same comparison loop" invites a copy of the loop inside the test. Add: "Extract `_check_cell(topology, slug, mid8, entry_points)` used by `test_entry_points_agree_per_cell` and by the planted test."
- **[LOW] §T048.3: the named survivors aren't shown to catch a re-add.** They are named for the `--check-residual` tombstone, but no mutation shows they catch a re-added option. Add: "Record a one-off where re-adding the option (visible) reds `test_visible_paths_match_reference`."
- **[LOW] plan.md is stale.** plan.md "Follow-ups outside this mission" still lists `test_next_no_unknown_state.py`. Fix plan.md so it does not contradict FR-013 and WP08.
- **RED command**: `pytest tests/next/test_internal_runtime_parity.py::test_rich_typer_ban_inspects_live_runtime_package tests/contract/test_next_no_unknown_state.py::test_runtime_placeholder_scan_inspects_live_source`. Expected: "0 files inspected" or "missing target".

**WP09**
- **[HIGH] §T049: the mutation matrix has no reproducible command.** The matrix is the WP's entire red-first evidence, yet it is hand-applied and recorded only as tracer prose. Replace with: "Commit `research/wp09_mutation_matrix.py` (a pytest plugin in the style of Debbie's `mutplug.py`, one monkeypatch per M1–M10) on the planning surface. Its output table (mutation → red node IDs) is pasted verbatim into the tracer and the PR. The reviewer re-runs it at base."

**WP10**
- **[MEDIUM] §T054.4: the RED count depends on how offenders are counted.** "8 offenders" hinges on counting: the helper flags an import and a call separately, so the "2 import+call pairs" give 4 entries, not 2. An implementer can tune dedupe until the count comes out at 8. Replace the count with an exact expected offender list (the 8 strings, spelled out) and assert on that list.
- **[LOW] §T054.3: the alias case isn't in the committed test.** It appears only under Risks. Add `from unittest import mock as m; m.patch("charter.x")` to the committed planted set.

**WP11**
- **[HIGH] §T059.3: the ≥15 floor counts the guard's own tests.** The floor counts "≥15 top-level `test_` functions in this module", and that total includes the 2 guard tests. After the move, 13 P0 tests plus 2 guards = 15 would pass with 2 P0 tests dropped. Replace with: "Assert that the set of test function names, minus the two guard tests, equals the 15 expected names hard-coded from the base capture."
- **[MEDIUM] §T064.1: the node-ID evidence depends on a scratch file.** The expected files live in `<scratch>` and can't be verified to come from the base. Add: "The reviewer regenerates the expected set: `git worktree add <tmp> <base>; pytest --collect-only -q tests/runtime/test_bridge_parity.py` there. The 16/8 split is derived from the function names."
- **[MEDIUM] US3-AS3 is only checked by hand.** "Oracle fixture not instantiated" is checked by a one-off `--setup-plan`. Add a committed test: "Run `pytest --setup-plan -q tests/runtime/test_next_board_authority.py` in a subprocess and assert `ledger_results` is absent and ≥16 nodes are planned." This is cheap because it executes nothing.

**WP12**
- **[HIGH] §T065.4: a catalog with no churn data passes.** The checker accepts `n/a (shallow)` in every churn cell, so a catalog with no churn numbers passes `45/45 OK`. That is exactly the "verdict catalog without churn numbers" fake. Add:
  "The checker parses grounding Part 2 and asserts that each row's five churn values equal the grounding values. `n/a (shallow)` is allowed only for modules absent from Part 2, and each such row needs a reason. Print the count of `n/a` rows."
- **[MEDIUM] §T065.4: the enforcer cell only has to be non-empty.** "TBD" passes today. Require the cell to contain a node ID (`::`) or `reason:` plus `mutation:`.
- **[MEDIUM] SC-005 is only nominally owned.** "0 parity bans pass when their scan target is empty" is checked only for WP08's two bans. Add a catalog column `empty-target behaviour` for rows whose category is ban/scan, filled from grounding, and have the checker require it for those rows.

**WP13**
- **[MEDIUM] §Context and §T071: WP03's rewrites are missing from the drain.** The sequenced-edit list and the drain table both omit the format-excluded files WP03 rewrites: `_exemptions/__init__.py` (L938) and `test_clock_call_ban.py` (L964). Add "WP03" to the permitted-writer list and add both rows as "format + remove". The derived rule would catch them, but the "no edits to other WPs' files" rule would block the implementer.
- **[MEDIUM] §T075.3: the SC-003 token list is missing WP06's retirements.** Add `category_1_auto_discovered_migrations`, `skip_marker_blocks`, `_GRANDFATHERED_UNREGISTERED_KEYS`, `_emit_skip_marker_delta` and `_category_baseline`. Allow-list the one ADR supersession bullet as an explained residual.
- **[MEDIUM] §T070.5: the past-tense doc option leaves a token hit.** The "past tense" option for `read-side-seam-classification.md` keeps the `resolution_gate_allowlist` token, which fails SC-003. Mandate the rewrite option.
- **[MEDIUM] §T069.5: NFR-003 per-site counting has no definition.** Define it as a script: sum the resolved exempted sites across join, kernel, os-detect, census and the inert baseline, for base and head, and print both totals. Also re-verify the WP06 shrink-only YAML comparison after consolidation.

## Cross-WP dependencies

- No undeclared hard dependency found. WP06↔WP04 (a `len()` coupling), WP01↔WP02..WP04 (rows only warn) and WP12→WP13 are handled.
- **[MEDIUM] Artefact commits have no owner.** WP04's T020 and T025 artefacts, and the proposed WP09 script, are planning-surface writes by `code_change` WPs. Name who commits them and when, so WP13 T074 can run the equivalence script at the consolidated head.

## Verdict

**CONDITIONAL PASS.** No CRITICAL findings. Before implement starts, fold these 7 HIGH findings:

1. Reviewer RED-reproduction commands (all WPs).
2. Drift non-emptiness counts (WP02, WP03, WP04).
3. The tautological drift companion (WP02, WP03, WP04).
4. A reproducible, self-testing equivalence script (WP04).
5. A reproducible mutation matrix (WP09).
6. The WP11 floor that counts its own guard tests.
7. The churn-less catalog that passes the WP12 checker.

The MEDIUM findings can be folded in the same pass, or recorded as review checks.
