---
work_package_id: WP01
title: Widen positional-anchor ban + interim per-site exemptions
dependencies: []
requirement_refs:
- C-001
- FR-001
- FR-002
- FR-003
- NFR-002
- NFR-004
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Ban widening
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_ratchet_positional_anchor_ban.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_ratchet_positional_anchor_ban.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Widen positional-anchor ban + interim per-site exemptions

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The binding rules for this WP are charter Standing Order #4 (red-first, never retry-to-green), #5 (architectural-gate non-vacuity: concrete floor + self-mutation through the real scan path), DIRECTIVE_041/DIR-041 (content anchoring, never line anchoring) and DIRECTIVE_043 (gate discipline).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

The positional-anchor ban (`tests/architectural/test_ratchet_positional_anchor_ban.py`) today misses 94 line-pinned allowlist entries because of three blind spots: the raw-tuple arm only fires in files that import the ratchet substrate, it only accepts a `str` path element (not `Path(...)`), and `path:line:op` census keys and `_exemptions/*.txt` lines are never inspected. This WP closes all three and lands the ban GREEN through an interim, exact, per-site exemption list that later WPs shrink and WP13 pins empty.

Done means:

1. The widened ban, run on the planning base with an **empty** exemption list, reports exactly the 94 line-pinned sites with the per-symbol breakdown **6 / 2 / 22 / 56 / 2 / 6** (join / kernel / destructive / mutation / overwrite / os-detect txt). This RED output is committed alone as the first commit and recorded verbatim (never asserted as a hard-coded constant).
2. A second commit adds `_POSITIONAL_ANCHOR_EXEMPTIONS` with exactly 94 per-site rows (one row per flagged site, identified by content, never by line) and the suite goes GREEN.
3. `test_positional_anchor_exemptions_are_exact`: a finding without a row FAILS; a row without a finding only WARNS (interim policy, so WP02–WP04 can land in parallel without editing this file).
4. The four tests that encode the old context gate are **inverted, not deleted** (tactic `delete-the-assertion-not-the-test`).
5. Every arm has a planted-violation fixture that calls `_scan_python_source` / `_scan_text_source` (the functions the standing gates call) and an arm-disable self-mutation proving the real scan path uses that arm (NFR-002).
6. Concrete floors: Python files scanned ≥ 262, text files scanned ≥ 20, exemption-file entry lines inspected ≥ 6.
7. `pytest --durations=0` on the ban file is recorded in the PR (NFR-004: < 10 s; the prototype measured 1.4–1.7 s). No wall-clock assertion.

## Context & Constraints

- **Mission**: `ratchet-baseline-census-gate-remediation-01M3EW3Z` (epic #5104, child #5085).
- **Read first**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/spec.md` (FR-001..FR-003, NFR-002, NFR-004, C-001, C-005), `plan.md` (rev 2: D-OP-6, D-OP-7; Coordination points), `research.md` §A1–§A6 (exact edits, probe evidence), `research/postspec-renata.md` (non-fakeable checks), `research/postplan-paula.md` Q2 LOW and `research/postplan-priti.md` (one line per row), `research/postplan-debbie.md` [INFO] §A2 (94 witnessed, no false positives).
- **C-005 / A1**: do **not** touch `src/specify_cli/contracts/anchoring.py::is_file_line_anchor` (production; consumed by the contract registry validator at `src/specify_cli/contracts/registry.py`, pinned by `tests/specify_cli/contracts/test_registry.py`). Every new predicate lives in the ban module itself.
- **Format-exclude rule**: this file is listed in `pyproject.toml` `[tool.ruff.format].exclude` (line 1019). Do **not** run `ruff format` on it and do not remove its exclude line; WP13 formats it and drops the line. Keep your edits in the file's existing style. After editing, `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` must stay green (the file must still need reformatting). `ruff check` (line-length 164, `E`/`W`/`C90`/`B`/`SIM`/`UP`) still applies.
- **Ownership**: you own only the ban file. WP13 later edits it (pins the list empty, drops `resolution_gate_allowlist.yaml` from `_YAML_ALLOWLISTS`) — that is a sequenced edit that depends on you. Do not touch any gate module whose allowlist you exempt; WP02 (join), WP03 (kernel, os-detect) and WP04 (census) migrate those.
- **Out of scope (record in the docstring, each with a negative fixture)**: `{path: int}` dicts (13 would-be false positives in `test_timing_coverage_invariant.py::BASELINE_FUNCTIONAL_ASSERTIONS`, ints are counts); function-local containers; the SHA-pinned / non-authoritative YAMLs `census/spec_kitty_home_pin_anchor.yaml` and `charter_path_literal_allowlist.yaml`; the dormant `tests/runtime/_bridge_oracle.py:602` (outside the scan universe). Prose strings such as `"decision.py:401; empty stdout"` (`test_json_contract_enumeration.py`) must stay green.
- **Escape hatch**: `has_diagnostic_locator_marker` (`# diagnostic-locator`) is imported from `specify_cli.contracts.anchoring` and already honoured by every arm. Do not add any new `# diagnostic-locator` marker anywhere to make the ban pass; the only permitted way to green the 94 sites is the per-site exemption list.
- **C-006 / git**: commit in your lane worktree only; never push; never merge. The interim 94 rows never reach `main` because the mission ships as one PR (D-OP-7).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

Commit plan (C-001):

- **Commit 1 (RED)**: T001 + T002 + T003 with `_POSITIONAL_ANCHOR_EXEMPTIONS = frozenset()` and the exactness test present. The standing gates fail with 94 findings.
- **Commit 2 (GREEN)**: T004 (the 94 rows).
- **Commit 3**: T005 + T006 (floors, self-mutations, docstring, measurements).

### Subtask T001 – Widen the Python arms (RED commit, part A)

- **Purpose**: Close the three Python blind spots (import gate, `Path(...)` elements, `path:line:op` keys) and the two shape gaps Renata flagged (keyword records, class-body allowlists) without touching production code.
- **Steps** (anchors verified on HEAD `2fd2dcc5`; `src/` and `tests/` are unchanged since planning base `3717c7ea`):
  1. **Remove the context gate.** In `_raw_file_line_tuple_seed_violations` (L559-592) delete the `if not _imports_ratchet_substrate(tree): return []` guard (L571-572). Delete `_imports_ratchet_substrate` (L512-529), `_RATCHET_SUBSTRATE_MODULES` and `_RATCHET_SUBSTRATE_NAMES` (L117-130) and their comment block (L111-116). Confirm with `grep -n "_imports_ratchet_substrate\|_RATCHET_SUBSTRATE" tests/` that no other consumer exists before deleting.
  2. **Widen the path element.** Add `_is_pathish_element(node) -> bool` that accepts: a path-ish string literal (reuse `_is_pathish_string_literal`, L532-545); a call to `Path`, `PurePath`, `PurePosixPath` or `PureWindowsPath` (resolve Name or Attribute callee through the existing `_call_func_name`, L190) whose first argument is itself path-ish; a `/` `ast.BinOp` with any path-ish leaf (walk both sides).
  3. **Widen the tuple shape.** Replace `_is_raw_file_line_tuple` (L548-556) with `_is_file_line_tuple(node)`: an `ast.Tuple` with ≥ 2 elements, `_is_pathish_element(elts[0])`, and any later element a bare int literal with `type(value) is int` (excludes `bool`). This covers `(path, int)`, `(Path(...), int)` and `(path, qualname, int)`. Rewrite the finding detail (L583-584) to use `ast.unparse(node)` instead of assuming both elements are `ast.Constant`.
  4. **Embedded-key arm.** Add `_EMBEDDED_LINE_KEY_RE = re.compile(r"^(?:[A-Z]+:)?[^\s:]+\.[A-Za-z0-9]+:\d+(?::\S*)?$")` and `_seed_embedded_line_key_violations(tree, source_lines, relpath)`: flag every `str` constant inside a seed container that **whole-matches** the regex. Whole-string anchoring plus `\S` keep prose evidence green. Keep the old `is_file_line_anchor` arm (`_seed_string_line_anchor_violations`, L329-349); it is cheap and pins registry-predicate parity. Deduplicate so one site is reported once (both arms can hit the same constant) — report per site, not per arm.
  5. **Keyword-record arm.** Flag an `ast.Call` inside a seed container carrying a keyword in `{"line", "lineno", "line_no", "file_line", "fileline"}` bound to a bare int literal (mirrors `FORBIDDEN_POSITIONAL_FIELDS` in `src/specify_cli/contracts/anchoring.py`). `occurrence=` and `op_ordinal=` are deliberately **not** in the set (the FR-014 carve-out; WP04's `CensusKey` uses `op_ordinal`).
  6. **Class-body seeds.** Extend `_module_level_seed_containers` (L279-298) and `_module_level_named_seed_containers` (L367-387) to also walk each top-level `ast.ClassDef.body`, so a class-attribute allowlist cannot evade the ban. Function-local containers stay out of scope.
  7. **Site identity on findings.** Extend `LineSinkViolation` (L164-173) with `symbol: str` (the seed container's bound name, or the `.txt` filename for text findings) and `site: str` (`ast.unparse(node)` for Python, the stripped line for text). `lineno` stays diagnostic only. Every arm must populate both; use `_module_level_named_seed_containers` to recover the symbol.
  8. **Wire it.** `_scan_python_source` (L595-607) composes all Python arms (call-arg sink, old string arm, embedded-key arm, laundering arm, file-line tuple arm, keyword arm).
- **Files**: `tests/architectural/test_ratchet_positional_anchor_ban.py` only.
- **Parallel?**: No (same file as T002/T003).
- **Notes**: Keep every new function ≤ complexity 15; prefer one small pure predicate per shape so each is unit-testable. Keep the walker `_iter_architectural_python_files` (L615-624) and the guard-file self-exclusion (`_GUARD_FILE`, L103) unchanged: the exemption rows you add in T004 live in this file and must not self-flag.

### Subtask T002 – Add the text-file arm and its standing gate (RED commit, part B)

- **Purpose**: FR-001 covers every `_exemptions/*.txt` file. The 6 `path:line` rows in `_exemptions/os-detect-ban-{deferred,mypy-narrowing,sanctioned-raw}.txt` (3 + 2 + 1) are authoritative exemptions today and are invisible to the ban.
- **Steps**:
  1. Add `_iter_architectural_text_files() -> list[Path]` returning `sorted(_ARCH_ROOT.rglob("*.txt"))` (20 files on HEAD, all under `_exemptions/`).
  2. Add `_scan_text_source(text: str, relpath: str) -> list[LineSinkViolation]`: for every line, strip it; skip blank lines and lines starting with `#`; flag a line that whole-matches `_EMBEDDED_LINE_KEY_RE`. The optional `[A-Z]+:` prefix catches the clock gate's `CALL:<path>:<line>` shape (`tests/architectural/_exemptions/__init__.py`), which currently has 0 entries (D-OP-6: the clock and lock-ban `path:line` shapes become unusable at zero entries by design). The `IMPORT:<path>` shape has no line number and must not match.
  3. Add `_scan_text_file(path)` (relpath from `_REPO_ROOT`) and a sibling standing gate `test_no_positional_anchor_in_architectural_text_files`, filtering findings through the same exemption set as the Python gate.
  4. Also expose an "entry lines inspected" count from the text scan (non-blank, non-comment lines seen) so T005 can floor it.
- **Files**: ban module only.
- **Validation**: `_scan_text_source("CALL:src/x.py:12\n", "t.txt")` flags one site; `"IMPORT:src/x.py"`, `"# src/x.py:12"` and `"src/x.py::main::if sys . platform =="` (WP03's content shape) produce 0.

### Subtask T003 – Invert the context-gate tests and add the fixture matrix (RED commit, part C)

- **Purpose**: The old tests encode the blind spot. Deleting them is the lazy path Renata flagged; invert them so the same fixtures now prove the hole is closed.
- **Steps** (research §A3):
  1. `TestImportsRatchetSubstrate` (L862-879, 4 tests) becomes `TestFileLineTupleArmIsImportAgnostic`: the same four import-shaped fixtures, each now carrying a `("x.py", 12)` seed; all four assert ≥ 1 finding via `_scan_python_source`. `test_ignores_non_substrate_file` becomes `test_flags_raw_tuple_in_non_substrate_file`.
  2. `TestIsRawFileLineTuple` (L896-907): rename to exercise `_is_file_line_tuple`; `test_rejects_three_tuple` (L906) becomes `test_flags_path_qualname_int_three_tuple` (same literal, inverted). Keep the str/str and label/int rejections.
  3. `test_ct7_raw_tuple_in_non_substrate_file_stays_green` (L1086-1102) becomes `test_ct7_raw_tuple_in_non_substrate_file_is_flagged`: same fixture, asserts exactly 2 findings.
  4. `test_ct7_real_3206_import_lineno_exemption_stays_green` (L1105-1120) becomes `test_real_kernel_gate_has_no_unexempted_line_pin`: scan the real `test_kernel_no_doctrine_import.py` and assert its findings are a **subset** of the sites covered by `_POSITIONAL_ANCHOR_EXEMPTIONS` (never "exactly 2": WP03 lands in a parallel lane and makes the finding set empty; Paula post-plan LOW).
  5. New planted fixtures, each through `_scan_python_source` or `_scan_text_source` (the functions the standing gates call), flagged: `(Path("src/a.py"), 12)`; `(Path("a") / "b.py", 12)`; a class-attribute allowlist `class K: ALLOW = (("a.py", 3),)`; `Entry(path="a.py", lineno=3)`; `{"src/x.py:98:reset_hard": "r"}`; text line `CALL:src/x.py:12`.
  6. Negative fixtures, 0 findings: `("label", 3)`; `{"cmd": "decision.py:401; empty stdout"}`; `ContentDescriptor(rel_path="a.py", qualname="f", token_substring="x", occurrence=0, rationale="r")`; `CensusKey(rel="a.py", qualname="f", token_line="x", op="o", op_ordinal=1)`; a `{"tests/x.py": 3}` dict and a nested `{"tests/x.py": {"test_a": 3}}` dict (the `BASELINE_FUNCTIONAL_ASSERTIONS: dict[str, dict[str, int]]` shape at `test_timing_coverage_invariant.py:159`, out of scope); a function-local `(("a.py", 3),)`; a `"src/a.py::f::reset_hard#0"` string.
- **Files**: ban module only.
- **Notes**: Keep `test_ct7_raw_file_line_tuple_seed_is_flagged`, `test_ct7_content_descriptor_form_stays_green` and `test_ct7_escape_hatch_opts_out_raw_tuple` as they are (still valid). Keep the existing planted tests at L945-1066.

### Subtask T004 – Record the RED, then land the 94 per-site exemption rows (GREEN commit)

- **Purpose**: FR-003 interim + D-OP-7. The ban lands green without editing any gate module, and every exempted site is named by content so growth is a visible diff.
- **Steps**:
  1. With commit 1 in place, run `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q -k "no_int_line_sink_in_architectural_python_seeds or no_positional_anchor_in_architectural_text_files"`. Capture the failure text. Confirm the per-symbol breakdown: `test_built_in_location_authority.py::_KNOWN_JOIN_ALLOWLIST` 6, `test_kernel_no_doctrine_import.py::_PRE_EXISTING_EXEMPTIONS` 2, `test_destructive_op_routing.py::_ALLOWLIST` 22, `test_mutation_ownership_routing.py::_ALLOWLIST` 56, `test_overwrite_ownership_routing.py::_ALLOWLIST` 2, `os-detect-ban-deferred.txt` 3, `os-detect-ban-mypy-narrowing.txt` 2, `os-detect-ban-sanctioned-raw.txt` 1 = **94**. Any other hit is either a real miss by the research (stop and report) or a false positive (fix the predicate, never exempt it). Record the breakdown with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category approach --actor <you> --entry "WP01 RED: ..."` (#5068: red for the intended reason). Commit 1 now.
  2. Add `_POSITIONAL_ANCHOR_EXEMPTIONS: frozenset[tuple[str, str, str, str]]` holding rows `(relpath, symbol_or_txt_filename, site, reason)`, exactly one row per flagged site. `site` is `ast.unparse(node)` for Python (for a census key that is the quoted string, e.g. `"'src/specify_cli/doctrine/sources/git_source.py:98:reset_hard'"`) or the stripped line for text.
  3. **One line per row, stable sort** (Priti post-plan): hoist short module constants for relpaths and reasons (e.g. `_BY_WP02 = "#5085 interim: migrated by WP02"`, `_BY_WP03`, `_BY_WP04`) so every row fits in 164 chars and no literal repeats ≥ 3 times (Sonar S1192). Reasons: join → WP02; kernel and os-detect → WP03; destructive, mutation, overwrite → WP04. Generate the rows from the RED output with a throwaway script in your scratchpad; never hand-type 94 sites.
  4. Filter both standing gates through the rows by `(relpath, symbol, site)` identity. `lineno` never participates.
  5. Add `test_positional_anchor_exemptions_are_exact`: compute all live findings (Python + text) **without** the filter; (a) any finding with no row → FAIL naming it; (b) any row with no live finding → `warnings.warn(...)` naming it (interim policy; WP13 flips this to fail and pins the set empty). Also assert every row has a non-empty reason and that rows are unique.
- **Files**: ban module only.
- **Validation**: the two standing gates and the exactness test pass; deleting any one row turns the standing gate red naming that site (do this manually once and note it in the Activity Log; do not commit it).

### Subtask T005 – Floors and per-arm self-mutation (NFR-002)

- **Purpose**: A ban that scans nothing, or whose arm is not wired into the real scan path, must go red. Renata HIGH: fixture-only tests and `>= 1` floors are fakeable.
- **Steps**:
  1. Replace `len(files) > 50` in `test_architectural_python_universe_is_nonempty` (L668-674) with `>= 262` (263 on the planning base; WP07 retires `rekey_inventory.py`). Add `test_architectural_text_universe_meets_floor`: text files `>= 20` and exemption-file entry lines inspected `>= 6` (the six os-detect rows survive as content lines after WP03).
  2. Add one arm-disable proof per new or widened arm (file-line tuple, embedded-key, keyword-record, class-body walk, text): plant the arm's fixture, assert it is flagged through `_scan_python_source` / `_scan_text_source`; then `monkeypatch.setattr` that arm's predicate (e.g. `_is_file_line_tuple`, `_EMBEDDED_LINE_KEY_RE` via a never-matching pattern, the keyword predicate, the class-body walker) to an always-false variant and assert the same planted fixture now yields 0. This proves the production scan path uses the arm.
  3. Add a floor to `test_non_vacuity_real_compliant_yamls_stay_green` (L1137): `assert len(_YAML_ALLOWLISTS) >= 1` (WP13 will drop `resolution_gate_allowlist.yaml`, leaving one).
- **Files**: ban module only.
- **Parallel?**: No.

### Subtask T006 – Docstring, measurements, quality gates

- **Purpose**: The module docstring currently documents the import-scoping as intent (L33-50: "this arm is scoped by *context*"). It must describe the widened scope, the exemption lifecycle and the out-of-scope list truthfully.
- **Steps**:
  1. Rewrite the CT7 paragraph (L34-50): the tuple arm is import-agnostic; list the shapes (str / `Path(...)` / `/` join path elements; 2- and 3-tuples; embedded `path:line[:suffix]` keys; `line=`-family keywords; class-body seeds; `_exemptions/*.txt` lines). Add the FR-003 lifecycle: interim per-site rows (WP01) → shrinking (WP02–WP04) → pinned empty (WP13). Add the out-of-scope list from "Context & Constraints" with the reason for each.
  2. Run `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q --durations=0` and record the ban's total wall time in the Activity Log and PR (NFR-004 target < 10 s). No timing assertion (flakiness policy).
  3. Run the quality gates below and fix every finding in code (no new `# noqa`, `# type: ignore` or per-file ignores).
- **Files**: ban module only.

## Test Strategy

Tests are required (ATDD, C-001). All live in `tests/architectural/test_ratchet_positional_anchor_ban.py`.

Blast radius (research §G3):

```bash
.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_trio_seam_only.py tests/specify_cli/contracts/ -q --durations=0
.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q
make test-fast
```

Quality gates (NFR-005):

```bash
uv run --frozen ruff check tests/architectural/test_ratchet_positional_anchor_ban.py
uv run --frozen mypy tests/architectural/test_ratchet_positional_anchor_ban.py
# Do NOT run ruff format on this file (pyproject format-exclude L1019; WP13 owns it).
```

Pre-existing failure rule: any failure that is also red on the planning base is not yours. Classify it (CLAUDE.md "baseline-red gotcha"), and if it is pre-existing, file a GitHub issue (or confirm one exists) before continuing, and cite it in the PR's *Tests run* section.

Campsite (FR-020): clean #2972 pytest-rule findings (S5778 / S5779 / S8997) only in this file, record each before/after in the PR; zero is acceptable.

## Risks & Mitigations

- **False positives from the widened arms** (e.g. count dicts, prose strings): the probe found none beyond the 94 once the dict arm is excluded. If the RED shows anything else, fix the predicate and add a negative fixture; never exempt a non-pin.
- **Rows that do not fit on one line**: use module constants for relpaths and reasons; generated rows, stable order.
- **Parallel lanes**: WP02–WP04 remove the pinned entries in their own lanes. Your rows then become finding-less and only warn. Do not make row-without-finding fail in this WP.
- **Escape-hatch abuse**: `# diagnostic-locator` would silently suppress a site. Adding one is forbidden in this mission.
- **Format ratchet**: the file is format-excluded; if your edits accidentally make it format-clean, `test_every_exclude_entry_still_genuinely_reformats` goes red. Keep the existing style; do not remove the exclude line (WP13 does).
- **Production predicate drift**: leave `is_file_line_anchor` untouched (C-005); the registry tests pin it.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`):

- The RED commit is the first commit on the lane and contains the widened arms with an **empty** exemption set; its failure text shows the 6/2/22/56/2/6 breakdown (no hard-coded 94 assertion anywhere).
- The exemption list is **per site** (94 rows, one per flagged literal/line), not per symbol (5 rows exempting 88 sites is the CRITICAL fake).
- The inverted tests use the **same fixtures** as before and assert ≥ 1 finding; none of the four was deleted.
- `test_real_kernel_gate_has_no_unexempted_line_pin` asserts a subset, not an equality on 2.
- Each arm has both a planted fixture through `_scan_python_source` / `_scan_text_source` and an arm-disable self-mutation that turns the fixture green; floors are the concrete numbers 262 / 20 / 6.
- Negative fixtures cover `("label", 3)`, the prose `"decision.py:401; empty stdout"`, `ContentDescriptor(..., occurrence=0, ...)`, `CensusKey(..., op_ordinal=1)` and the count-dict shape.
- `git diff` shows no new `# diagnostic-locator` marker, no change under `src/`, no edit to any gate module other than the ban file, no `pyproject.toml` change.
- mypy and ruff check pass on the file; the file was not reformatted.
- The PR records the `--durations=0` figure.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
