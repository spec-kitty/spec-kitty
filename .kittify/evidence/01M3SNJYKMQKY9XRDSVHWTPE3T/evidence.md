# Review Q: #5353 slice-3 follow-up (test-quality-scan precision)

Reviewer: reviewer-renata (independent). Branch `issue-5353-q-followup` @ 1994c7f8 (on origin/main).
Op: 01M3SNJYKMQKY9XRDSVHWTPE3T.

## Verdict: APPROVE-WITH-NITS

The fix does what the ledger row asks (2.8 / 2.9). The two slice-3 false positives are gone, the tests
are behavioural (they drive `main()` and read `tests.json`), and every requested break turns them red
except the `ast.parse` exclusion (see F2). Recall costs more than the tests/cli sample shows (F1).

## Findings (by severity)

### F1 (medium): new false-negative class for `literal-source-scan`, the `/ "src" /` path-join form
`packs/internal/assets/test-quality-scan.py:325-335` (`_names_source_path`) only accepts a string
constant that contains `src/`, or a `Path(...)` call whose own unparse matches `_SOURCE_PATH`. The
most common way the repo spells a source path is
`Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "x.py"`. There the `Path(...)` node is
only `Path(__file__)` and no constant contains `src/`, so the test is no longer flagged. The old
text regex caught it because the whole line was on one string.

Scanning all of `tests/` (old scanner, then new): 6493 flagged tests become 6469. `literal-source-scan`
loses 26 tests and gains 6. `skip-or-xfail` loses 15.
In 8 of the 26 lost tests the body joins `/ 'src'`. Among them are clear R4 true positives:
- `tests/auth/test_session.py::test_no_hardcoded_90_days_in_session_module`
  (reads `src/specify_cli/auth/session.py` and asserts `"days=90" not in text`)
- `tests/specify_cli/test_mid8_contract_sensitive_routing.py::test_no_inline_mid8_slices_remain_after_routing`
- `tests/audit/test_no_legacy_path_literals.py::test_no_legacy_path_literals_in_cli_commands`
- `tests/test_template/test_asset_generator.py::test_bundled_software_dev_templates_have_descriptions`

The implementer's tests/cli measurement (116 to 114) is correct, but tests/cli contains none of these tests.
**Fix:** in `_names_source_path`, also accept a `BinOp(Div)` chain that has a `Constant("src")` operand
followed by a package constant (`specify_cli|charter|runtime|kernel|glossary|mission_runtime`). Pin it
with a `_PLANTED` row:
`text = (Path(__file__).parents[2] / 'src' / 'specify_cli' / 'x.py').read_text(); assert 'guard(' in text`.

### F2 (low-medium): two new branches have no test oracle (surviving mutants)
- M3: deleting `and not _parses_ast(fn)` (line 318) leaves all 37 tests green. No `_NOT_FLAGGED` row reads
  src and parses it with `ast`. The exclusion was already untested on main, but this PR rewrote it as a new
  helper (`_parses_ast`, line 356).
- M4: making `_prose_nodes` return an empty set (line 338) leaves all 37 tests green. The slice-3 look-alike
  names `src/` only in a *comment*, and a comment is never in the AST, so the docstring and assert-message
  exclusion is never exercised.

**Fix:** add `_NOT_FLAGGED` rows for both:
- `ast.parse(Path('src/x.py').read_text())` followed by a structural `in` assert.
- A fixture read whose `src/` appears only in the docstring or the assert message.

### F3 (low): `_prose_nodes` treats any first expression statement as the docstring
`test-quality-scan.py:340-341` checks `isinstance(fn.body[0], ast.Expr)`, not for a string `Constant`. A test
whose first statement is `check('src/specify_cli/x.py')` has that literal ignored.
Probe: `first_stmt_expr_src_only` was flagged by the old scanner and is not flagged by the new one.
**Fix:** require `isinstance(fn.body[0].value, ast.Constant) and isinstance(fn.body[0].value.value, str)`.

### F4 (low): marker aliases are no longer seen by `skip-or-xfail`
`_skip_if_root = pytest.mark.skipif(...)` followed by `@_skip_if_root` is now not flagged. This affects 4 tests in
`tests/specify_cli/upgrade/test_skill_update_external_symlinks.py`. Those 4 are root/permission guards, so losing
them is harmless. It is still a blind spot. The other 11 lost `skip-or-xfail` flags are genuine look-alikes
(parametrize ids "skipped" or "skip").

### F5 (nit): `Path(...)` branch still uses the loose `_SOURCE_PATH` regex
`Path("packs/built-in/.../charter/prompt.md")` matches `charter`. This produces a new flag on
`tests/specify_cli/cli/commands/test_charter_generate_autotrack.py::test_charter_template_uses_safe_commit_command`
(it reads a pack prompt, not `src/`). The old scanner had the same class; the new scanner also sees multi-line
`Path(` calls.

### F6 (nit, process): fix and tests land in one commit
The protocol asks for product-fix commits before test commits. The red proof (old scanner plus new tests: 3 failed,
34 passed) is recorded in `red-proofs-q.md`, so this is not a blocker.

## Checks that passed
- `git diff origin/main...HEAD -- src/` is empty. Only the internal asset, its test and the Op file changed.
- The trailers are present. ruff check, ruff format --check, C901 and mypy are clean on both files.
  There is no new noqa or type-ignore. Line 303 is long but under the 164 limit.
- The tests drive the CLI entry point and parse the `tests.json` output. They do not mock the scanner.
- A changelog entry is not needed: the asset is internal-pack maintainer tooling and does not ship.

## Planted breaks re-run (target: tests/doctrine/assets/test_test_quality_scan.py)
| Mutation | Result | Failing test | Assertion line |
|---|---|---|---|
| M1: text match `pytest\.(skip\|xfail)\(` on seg, added back | RED, 1 failed | `test_look_alike_is_not_flagged[test_label_mentions_skip]` | :160 |
| M2: `_names_source_path` requirement dropped | RED, 3 failed | `[test_local_full_copy_...]`, `[test_reads_fixture_not_source]`, `[test_reads_tests_fixture]` | :160 |
| M3: `ast.parse` exclusion dropped | **GREEN, survives** | none | see F2 |
| M4 (own): prose exclusion dropped | **GREEN, survives** | none | see F2 |
| M5 (own): skipif platform guard dropped | RED, 1 failed | `[test_posix_only]` | :160 |
| M6 (own): builtin `open()` read dropped | RED, 1 failed | `test_planted_...[literal-source-scan1]` | :150 |
| M7 (own): decorator text `"skip" in unparse` added back | RED, 2 failed | `[test_drill_outcome_color]`, `[test_posix_only]` | :160 |

After each mutation the file was restored and `git status` was clean.

## Tests run
- Gates: `tests/doctrine/assets/test_test_quality_scan.py`, `tests/cross_cutting/packaging/test_packaging_safety.py`,
  `tests/architectural/test_pack_manifest_no_author_edit.py`, `test_ruff_pytest_style_baseline.py`,
  `test_ruff_format_exclude_ratchet.py`: 60 passed (286 s, load average about 18).
- make test-fast equivalent (venv python, PYTHONPATH set to the worktree's src, same dirs, markers and `-n auto --dist loadfile`):
  it reached 99% with 0 F and 0 E, then hit the 30-minute background cap under load average ~20 before the summary line printed.
  The diff does not touch any test-fast directory.
- Recall comparison: a scratch harness (`scratchpad/q/cmp.py`) ran the old and new scanner over tests/cli (116 to 114 flagged tests;
  exactly the 2 claimed tests lost) and over all of tests/ (6493 to 6469, see F1).
