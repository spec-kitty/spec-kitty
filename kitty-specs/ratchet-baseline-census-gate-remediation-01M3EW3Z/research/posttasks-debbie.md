# Post-tasks squad — Debugger Debbie (lens: code-truth) — WP01..WP07

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z`. HEAD `dac86aa2`. Read-only on the repo; scratch probes are in `squad/dbg/`.
Governance applied: profile `debugger-debbie`. I used its falsify/trace discipline: every claim is tested against live code, and I only report a claim when a probe or grep either confirms it or shows it wrong. I also loaded `charter context --action tasks`: DIRECTIVE_041/043 (content anchoring, gate non-vacuity), DIRECTIVE_044 (single authority), Standing Order #4 (red-first) and Standing Order #5 (floors).
`git diff 3717c7ea HEAD -- src tests` and `git diff 2fd2dcc5 HEAD -- src tests` are both empty, so the prompt anchors are valid on HEAD.

## Findings

[MEDIUM] WP03 T015 step 3 — the clock loader retarget "parses via parse_descriptor_line". Verdict: PARTIAL, because a coupling to a file WP03 does not own is missing.
The unowned `tests/architectural/test_clock_import_ban.py:155-163` monkeypatches `tests.architectural._exemptions._iter_exemption_lines` with a `list[str]` fake and then calls `load_import_exemptions()`. T014 step 1 and T015 step 1 change `_iter_exemption_lines` to return `(filename, line)` pairs so that the rationale can be the filename. If the implementer mirrors that change in `_exemptions/__init__.py`, the unowned test breaks. The prompt names only the `load_call_exemptions() == frozenset()` coupling (L241-250). The "stop and report" clause in T015.5 only mitigates this after the fact.
Fix: state that the clock `_iter_exemption_lines -> list[str]` shape is frozen, and cite `test_clock_import_ban.py:155-163`. If the rationale needs the filename, add a separate iterator.

[LOW] WP02 T007.3 — "On base this is RED for every file". Verdict: FALSE for 2 of the 5 parameters on base.
The drift test is parametrized over the files the allowlist references. On base that is 5 files, because the 2 dead entries count. `src/kernel/paths.py` and `src/specify_cli/runtime/home.py` contain no join (probe: the live join set lacks both). A blank-line mutation of either file leaves `(unexpected, suppressed)` identical, so those 2 parameters are GREEN on base.
Fix: say RED for the 3 live files. The dead 2 are covered by the stale test.

[LOW] WP04 Context "Known, accepted weakness" — "8 of the 22 destructive keys have argv-only token lines". Verdict: FALSE (off by one).
The probe found 7 token lines made only of punctuation (`[ , , ] ,` ×5, `[ , , , ] ,` ×2). 19 of the 22 start with `[`.
Fix: say 7.

[LOW] WP07 T038.4 / T042.4 — the path-qualified search "must return 0". Verdict: PARTIAL.
The grep walks `.` and excludes neither `.venv` nor `.mypy_cache` nor `.pytest_cache`. All three have 0 hits today. However, mypy writes `.mypy_cache/**/surface_resolution_audit/audit.data.json` whenever it checks the old module, and that JSON would be a false hit.
Fix: add `--exclude-dir={.venv,.mypy_cache,.pytest_cache,.ruff_cache}`.

[LOW] WP07 T039.4 — anchors "KNOWN_CANDIDATE_FILES about L471-481", "L65 parents[3]" and "INVENTORY_PATH L69". Verdict: PARTIAL.
The actual lines are L479, L66 and L70. Every symbol exists, and none of the kept functions uses a deleted symbol (`KNOWN_CANDIDATE_FILES` is used only by `main()` at L777).
Fix: optional. Re-anchor, or leave as is, since the prompt says to locate by symbol.

[INFO] WP01 T001.5 — the keyword set "mirrors FORBIDDEN_POSITIONAL_FIELDS". Verdict: PARTIAL.
The production set also contains `file` (`anchoring.py:285-287`). Omitting it is correct, because `file` is not an int-bound field. Say "minus `file`".

[INFO] WP04 T020 — the `op_ordinal` vs `occurrence` rename. Verdict: TRUE.
`data-model.md` contradicts itself (L31 uses `op_ordinal`, L40 uses `occurrence`). The prompt already handles this.

[INFO] WP02/03/04 — `with_probe_above_statement`.
My naive implementation of the helper's spec (insert above the innermost `ast.stmt` at its `col_offset`) parses cleanly at all 92 exempted sites: 80 census, 4 join, 2 kernel and 6 os-detect. The spec never mentions `elif` or decorator lines, where inserting at `col_offset` would break syntax.
Fix: add one unit test for each case in T008.

## Verified TRUE (evidence)

- **WP01**
  - An independent re-implementation of the widened arms, reusing the ban's own helpers, finds exactly **94** sites on HEAD. The breakdown is join 6 / kernel 2 / destructive 22 / mutation 56 / overwrite 2 / txt 3+2+1, with no extra hits. It ran in 1.18 s.
  - Floors: 263 Python files (≥262 holds after WP07 −1 and WP02 +2), 20 text files, and exactly 6 inspected entry lines.
  - All L-anchors match within ±3: L111-130, 164-173, 190, 279, 329, 367, 512-529, 532-556, 559-592 (guard at 571), 595-607, 615-624, 668-674, 862-907, 945-1066, 1086-1120, 1137. pyproject L1019 is correct.
  - Negative fixtures stay green under both regexes: the prose `decision.py:401;…`, `src/a.py::f::reset_hard#0`, `IMPORT:src/x.py` and WP03's content line. `CALL:src/x.py:12` is flagged.
  - `_imports_ratchet_substrate` has no consumer outside the ban file.
  - The longest estimated exemption row is 134 chars, so rows fit the 164-char limit.
- **WP02**
  - The dead entries are exactly `kernel/paths.py:88` (`if is_windows():`) and `runtime/home.py:79`.
  - All 4 descriptors resolve uniquely.
  - lint.py lines 379 and 380 have identical composite keys.
  - The planted join at line 88 is detected.
  - The non-adopter anchors are correct: trio L528, sole_door L587, surface L389-403, read_side L796/946, and audit.py L507/530.
- **WP03**
  - All 8 descriptors resolve.
  - The kernel gate finds 2 violations (lines 88/97) and the os-detect gate finds 7 (including the door).
  - The loaders accept `path:line` on base, so the rejection tests are RED for the stated reason.
  - pyproject L938 and L964 are correct.
- **WP04**
  - Counts are 22/56/2 with distinct `rel` counts 15/21/2.
  - Exactly 3 sites have `op_ordinal=1`: `merge.py:1199`, and `m_0_10_8…:205/230`.
  - `enclosing_qualname` agrees across the two algorithms at 0/80 mismatches.
  - `_baselines.yaml:446` is 56, and `test_ratchet_baselines` L464-467 and L626-629 are correct.
- **WP05**
  - The symbol grep returns 0 callers.
  - pytest gives 3 passed and 1 warning, "…shrank; delete cleared ledger rows: styleguide-references, model".
  - The detector prints the `model` suppression.
  - The baseline has 38 rows, with 38 `owner:` lines and 10 `provisional:` lines. Walk sizes are 176 schema and 138 model.
  - The token search hits only WP05-owned files.
  - `test_gate_remedy_presence.py:174` is correct.
- **WP06**
  - The YAML has 23 leaves in 12 sections. The arms enforce 6+13=19 rows.
  - Unenforced leaves are {cat_1, skip_marker_blocks, unassigned_entries, masking_suppressions}.
  - `known_ungated_files` is 0 live, and cat_3 is 0 live against 2 in the YAML.
  - `_SKIP_MARKER_RE` is at L308, and `test_no_new_dead_modules_under_src` is at L788. ADR L114-115 is correct.
- **WP07**
  - `audit.py` exits 1 with 8 missing and 8 ghost rows.
  - `rekey_inventory --check` prints STALE.
  - The survivor collects 8 tests.
  - The base search hits are exactly the listed ones.
  - The `inventory.md:76` rationale is column 7.
  - pyproject L954, 955, 948 and 1013 are correct.
- **Ownership:** no `owned_files` overlap exists across WP01-WP13. The out-of-map edits are all declared and sequenced: WP05→`_baselines.yaml` (WP06 depends on WP05), WP07/WP09→pyproject hunks, and WP13→ban file and pyproject.
- **Commands:** every cited test path exists or is in `create_intent`. The existing blast radius collects 390 tests with no errors, and the gate suites pass (149 passed). `tracer-append` accepts `approach` and `design-decisions`.

## Verdict
**PASS with minor fixes.** No blockers. Fold the MEDIUM finding (WP03 clock iterator shape) before implement. The LOW findings are prompt-accuracy edits.
