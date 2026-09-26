---
work_package_id: WP03
title: Kernel + os-detect exemptions; retarget lock-ban/clock loaders
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-007
- NFR-001
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Hand-curated migrations
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_os_detection_exemptions.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_kernel_no_doctrine_import.py
- tests/architectural/_os_detection_exemptions.py
- tests/architectural/_exemptions/os-detect-ban-*.txt
- tests/architectural/test_os_detection_ban.py
- tests/architectural/_lock_ban_exemptions.py
- tests/architectural/_exemptions/lock-ban-*.txt
- tests/architectural/test_lock_primitive_ban.py
- tests/architectural/_exemptions/__init__.py
- tests/architectural/test_clock_call_ban.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Kernel + os-detect exemptions; retarget lock-ban/clock loaders

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load `spec-kitty charter context --action implement --json`. Binding here: DIRECTIVE_041/DIR-041 (content anchoring), DIRECTIVE_044 (use WP02's `_content_identity` as the only matcher and serialiser), DIRECTIVE_043 / Standing Order #5 (non-vacuity), Standing Order #4 (red-first), tactic `delete-the-assertion-not-the-test` (invert, never delete).

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

1. **Kernel gate (FR-005)**: `_PRE_EXISTING_EXEMPTIONS` in `test_kernel_no_doctrine_import.py` (two `("kernel/schema_utils.py", 88/97)` tuples) becomes two `ContentDescriptor`s matched through `_content_identity.partition_findings`; stale entries fail (FR-007).
2. **os-detect gate (FR-007, SC-001)**: the 6 `path:line` rows in `_exemptions/os-detect-ban-{deferred,mypy-narrowing,sanctioned-raw}.txt` become content lines `<rel>::<qualname>::<token_substring>[::<occurrence>]`, parsed by WP02's `parse_descriptor_line`; the gate partitions by composite key; stale entries fail.
3. **Loader retarget (D-OP-6, Paula post-plan Q4)**: the lock-ban loader (`_lock_ban_exemptions.py`) and the clock `CALL:` loader (`_exemptions/__init__.py`) stop teaching and accepting the `path:line` shape. Both parse the same content form (clock: `CALL:<rel>::<qualname>::<token_substring>[::<occurrence>]`); both stay at **0 entries**; a `path:line` line is rejected with a named error.
4. **Drift tolerance (NFR-001)**: `test_kernel_exemptions_survive_line_drift` (1 file) and `test_os_detection_exemptions_survive_line_drift` (3 files), each parametrized over the files its exemptions reference (count asserted equal to the derived set), prove `(unexpected, suppressed)` sets are identical under both drift mutations.
5. All of the above are RED on the planning base in the first lane commit and GREEN at the end.

## Context & Constraints

- **Depends on WP02**: `tests/architectural/_content_identity.py` provides `resolve_allowlist`, `partition_findings`, `with_blank_line_at_top`, `with_probe_above_statement`, `render_descriptor_line`, `parse_descriptor_line`. Import them; do not re-implement any of them (DIRECTIVE_044). If WP02 is not on your base yet, stop and rebase onto it (`spec-kitty implement WP03` resolves the lane).
- **Read**: `spec.md` (FR-005, FR-007, NFR-001, SC-001; edge case on #3206), `plan.md` rev 2 (D-OP-6, D-OP-8; External coordination #3206, #4727), `research.md` §B3, §B4, §B5, `research/postplan-paula.md` Q4 MEDIUM (loaders still teach the line shape), `research/postspec-priti.md` (os-detect rows the sweep missed), `research/postspec-renata.md`.
- **Verified content identities** (each resolves uniquely via `resolve_descriptor` on HEAD `2fd2dcc5`):

  | gate / file | rel_path | qualname | token_substring | resolved token line |
  |---|---|---|---|---|
  | kernel | `kernel/schema_utils.py` (src-relative, the gate's form) | `_resolve_schema_path` | `files (` | `resource = files ( )` (L88) |
  | kernel | `kernel/schema_utils.py` | `_resolve_schema_path` | `parent . parent / / /` | `return Path ( __file__ ) . resolve ( ) . parent . parent / / / / filename` (L97) |
  | os-detect-ban-deferred.txt | `src/specify_cli/__init__.py` | `ensure_executable_scripts` | `if os . name ==` | L353 |
  | os-detect-ban-deferred.txt | `src/specify_cli/__init__.py` | `main` | `if sys . platform ==` | L521 |
  | os-detect-ban-deferred.txt | `src/specify_cli/paths/windows_paths.py` | `_current_platform` | `sys . platform . startswith (` | L163 |
  | os-detect-ban-mypy-narrowing.txt | `src/kernel/locks.py` | `_os_lock` | `if sys . platform ==` | L222 |
  | os-detect-ban-mypy-narrowing.txt | `src/kernel/locks.py` | `_os_unlock` | `if sys . platform ==` | L234 |
  | os-detect-ban-sanctioned-raw.txt | `src/kernel/locks.py` | `<module>` | `if sys . platform ==` | L96 |

  The kernel gate currently finds exactly 2 violations (one per line); the os-detect gate finds 7 (the 6 above plus the door `src/kernel/paths.py`, which the gate skips by construction).
- **Kernel rel form**: `collect_forbidden_vocabulary` reports paths relative to `src/` (`kernel/schema_utils.py`). The descriptor's `rel_path` uses that same form; `source_for` must read `_SRC / rel`. Keep `collect_forbidden_vocabulary`'s public signature unchanged.
- **Format-exclude rule**: `tests/architectural/_exemptions/__init__.py` (pyproject L938) and `tests/architectural/test_clock_call_ban.py` (L964) are in `[tool.ruff.format].exclude`. Do not run `ruff format` on them and do not remove their exclude lines (WP13 does); keep their existing style and confirm `test_every_exclude_entry_still_genuinely_reformats` stays green. Your other files are not excluded and must pass `ruff format --check`.
- **Not owned, must stay green unchanged**: `tests/architectural/test_clock_import_ban.py` (it calls `load_call_exemptions()` and asserts `== frozenset()`; that keeps working if the loader returns `frozenset[ContentDescriptor]`). `tests/architectural/test_no_follow_symlinks_apply_ban.py` has its own inline `path:line` loader for `_exemptions/no_follow_symlinks_apply.txt`, already pinned empty by an equality assertion; it is out of this WP's scope. Record it in the tracer as a residual line-shaped loader for WP13's FR-019(d) follow-up.
- **Coordination (record, do not act on src)**: #3206's acceptance criterion "remove the two entries" becomes "delete the two descriptors"; #4727 owns the `windows_paths._current_platform` row, whose acceptance "entry removed" becomes "descriptor line removed". Record both in the tracer; the operator posts the tracker comments.
- **C-005**: no `src/` edit. **C-006**: commit in your lane; never push or merge.
- **WP01 interaction**: WP01's interim rows for the kernel tuples and the six os-detect lines become finding-less after this WP and only warn; do not edit the ban file.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

Commit plan: **commit 1 = T012 alone (RED)**; commit 2 = T013; commit 3 = T014; commit 4 = T015; T016 is validation.

### Subtask T012 – Red-first acceptance tests (commit 1, RED)

- **Purpose**: C-001. Show on the planning base that the kernel and os-detect exemptions do not survive line drift and that the three loaders accept the banned `path:line` shape.
- **Steps**:
  1. **Kernel drift**: refactor `_scan_file(path, relative_to)` (L177-196) into `_scan_source(source, rel) -> list[tuple[str, int, str]]` plus a thin path wrapper (behaviour-preserving test-code extraction; allowed in the RED commit). Add a seam `_kernel_partition(sources: Mapping[str, str])` returning `(unexpected, suppressed)` with the **current** `(rel, lineno) not in _PRE_EXISTING_EXEMPTIONS` matching. Add `test_kernel_exemptions_survive_line_drift`, parametrized over the files referenced by the exemptions (derived; count asserted), applying a blank line at the top of the file in memory and asserting both sets are identical. RED on base.
  2. **os-detect drift**: add a seam `_os_detection_partition(sources)` in `test_os_detection_ban.py` with the current `(relpath, lineno) not in exemptions` matching, running the real `scan.find_os_detection_violations(ast.parse(source))` per file. Add `test_os_detection_exemptions_survive_line_drift` over the 3 referenced files (derived; count asserted). RED on base.
  3. **Loader shape rejection**: add `test_os_detection_loader_rejects_line_pinned_entry`, `test_lock_ban_loader_rejects_line_pinned_entry` and `test_clock_call_loader_rejects_line_pinned_entry`. Each monkeypatches the module's `_iter_exemption_lines` to return one `path:line` line (`src/x.py:12`; clock: `CALL:src/x.py:12`) and asserts the loader raises `ValueError` naming the line. RED on base (the loaders accept it).
  4. Run them, capture the failure text, record it with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category approach --actor <you> --entry "WP03 RED: ..."`, commit alone.
- **Files**: `test_kernel_no_doctrine_import.py`, `test_os_detection_ban.py`, `test_lock_primitive_ban.py`, `test_clock_call_ban.py`.
- **Notes**: use the inline blank-line mutation in this commit if you prefer; T013/T014 switch to WP02's mutators and add the probe mutation.

### Subtask T013 – Migrate the kernel exemptions (commit 2)

- **Purpose**: FR-005, FR-007 (fail on stale).
- **Steps**:
  1. Replace `_PRE_EXISTING_EXEMPTIONS` (L127-132) with `tuple[ContentDescriptor, ...]` holding the two kernel descriptors from the table. Move the #3206 rationale from the comment block above it (L91-126) into each descriptor's `rationale`, and state the #3206 exit: "delete these two descriptors".
  2. Findings become `((rel, *composite_key(source, lineno)), (rel, lineno, detail))`. `test_kernel_holds_no_doctrine_or_specify_cli_vocabulary` (L217-241) uses `partition_findings` with the lazily resolved allowlist (`functools.cache`d accessor over `resolve_allowlist(..., source_for=lambda rel: (_SRC / rel).read_text(...))`).
  3. Invert, do not delete, `test_pre_existing_exemption_is_still_a_real_violation` (L244-259): keep its name; it now asserts no resolution error, `unused == Counter()`, and `checked == len(_PRE_EXISTING_EXEMPTIONS) >= 2`.
  4. Switch the drift test to `with_blank_line_at_top` and add `with_probe_above_statement` at both exempted sites.
  5. Update the module docstring and the gate's docstring ("filters out exactly one already-tracked … site", L226-230) to describe descriptor identity.
- **Files**: `tests/architectural/test_kernel_no_doctrine_import.py`.
- **Validation**: `test_walker_catches_in_function_call_argument` and `test_walker_ignores_docstrings_and_prose` stay green unchanged.

### Subtask T014 – Migrate the os-detect exemptions (commit 3)

- **Purpose**: SC-001 (text files) and FR-007 for the os-detect gate.
- **Steps**:
  1. `_os_detection_exemptions.py`: `load_os_detection_exemptions() -> frozenset[ContentDescriptor]` built with `parse_descriptor_line(line, rationale=<source filename>)` so per-owner-file semantics survive. `_iter_exemption_lines` must return `(filename, line)` pairs (or equivalent) so the rationale is the file. A `path:line` line raises `ValueError` naming file and line (via the parser). If this changes `_iter_exemption_lines`' return shape, update only the monkeypatch plumbing of T012's rejection test and of `test_stale_exemption_removal_reds_the_gate`; their assertions must not change. Rewrite the module docstring's "`<repo-relative path>:<line>`" paragraph (L13-14) to the content form.
  2. Rewrite the three `.txt` files: replace the 6 `path:line` rows with the 6 content lines from the table (use `render_descriptor_line` to produce them). Delete the re-pin archaeology comments (the "re-pinned", "line-number drift fix" and ":128 -> :163" notes); keep each file's policy header (why the sites are deferred / permanent) and the #4727 reference. `os-detect-ban-wp03.txt` and `os-detect-ban-wp04.txt` stay empty of entries; update any header text that teaches the `path:line` shape.
  3. `test_os_detection_ban.py`: build keyed findings `((relpath, *composite_key(source, lineno)), (relpath, lineno))` (read each scanned file's source once), partition against the resolved exemptions. `test_no_banned_os_detection_outside_the_door` (L80-103) keeps the door skip; its failure message (L96-101) now prints, for each violation, the exact content line to add (`render_descriptor_line` of a descriptor built from the finding's composite key) instead of `<path>:<line>`.
  4. `test_every_exemption_entry_is_a_real_violation` (L106-117) stays fail-on-stale using resolution errors plus `unused`, and asserts `checked == len(exemptions) >= 6`.
  5. Invert `test_stale_exemption_removal_reds_the_gate` (L120-163): keep both directions, but write the planted exemption in the content shape (`offender.py::<module>::if sys . platform ==`) and resolve it against the planted source under the monkeypatched `scan.REPO_ROOT`.
  6. Switch the drift test to WP02's mutators; add the probe mutation at all 6 sites.
- **Files**: `_os_detection_exemptions.py`, `_exemptions/os-detect-ban-*.txt`, `test_os_detection_ban.py`.
- **Validation**: the planted-idiom tests (L166-267) stay green unchanged; the WP01 ban's text arm reports no line pin in any `os-detect-ban-*.txt`.

### Subtask T015 – Retarget the lock-ban and clock `CALL:` loaders (commit 4)

- **Purpose**: D-OP-6 + Paula Q4. After WP01 the widened ban refuses any `path:line` exemption line, but these loaders still document and parse that shape; a future author would get a red with no sanctioned form. Give both the content form at zero entries.
- **Steps**:
  1. `_lock_ban_exemptions.py`: same change as T014 step 1 (`frozenset[ContentDescriptor]` via `parse_descriptor_line`; rationale = filename; `path:line` rejected). Update its docstring (L12-13). Update the `lock-ban-wp04.txt` / `lock-ban-wp05.txt` headers only where they teach the line shape; they stay empty of entries.
  2. `test_lock_primitive_ban.py`: `test_no_banned_raw_lock_usage_outside_the_door` (L82-104) and `test_every_exemption_entry_is_a_real_violation` (L107-118) partition by composite key like T014; the failure message prints the content line to add. Invert `test_stale_exemption_removal_reds_the_gate` (L121-163) to the content shape.
  3. `_exemptions/__init__.py` (clock): keep `IMPORT:<path>` (file granularity, no line). `load_call_exemptions() -> frozenset[ContentDescriptor]` parses `CALL:<rel>::<qualname>::<token_substring>[::<occurrence>]` via `parse_descriptor_line` after stripping the prefix; a `CALL:<path>:<line>` line raises `ValueError`. Update the docstring (L14-26) to the content shape and explain why (call-site granularity is preserved by content identity, and it survives line drift).
  4. `test_clock_call_ban.py`: `test_no_banned_wall_clock_call_outside_the_door` (L81-109) and `test_every_call_exemption_entry_is_a_real_violation` (L112-123) partition by `(relpath, *composite_key(source, violation.line))`; the failure message (L101-103) teaches `CALL:<rel>::<qualname>::<token_substring>`. Invert `test_stale_exemption_removal_reds_the_gate` (L126-184) to write a `CALL:offender.py::<module>::datetime . now (` line.
  5. Confirm `test_clock_import_ban.py` (not owned) still passes unchanged; if it cannot, stop and report rather than editing it.
- **Files**: `_lock_ban_exemptions.py`, `_exemptions/lock-ban-*.txt`, `test_lock_primitive_ban.py`, `_exemptions/__init__.py`, `test_clock_call_ban.py`.
- **Notes**: the clock and lock-ban gates remain zero-tolerance in practice; this subtask changes the sanctioned shape, not the entry count. Keep format-excluded files unformatted.

### Subtask T016 – Validation, tracer, quality gates

- **Purpose**: Evidence and hygiene.
- **Steps**:
  1. Run the blast radius and quality gates below; confirm every T012 test is GREEN.
  2. Tracer (`--category design-decisions`): the #3206 and #4727 acceptance-criteria rewording; D-OP-6 (clock/lock-ban shrink-only at zero with the content shape as the only sanctioned form); the residual `no_follow_symlinks_apply.txt` inline loader.
  3. Confirm with the WP01 ban on your base (if present) that no line pin remains in your files: `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q` (WP01 rows for your sites only warn).
- **Files**: none new.

## Test Strategy

Tests are required.

```bash
.venv/bin/python -m pytest tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/test_os_detection_ban.py tests/architectural/test_lock_primitive_ban.py tests/architectural/test_clock_call_ban.py tests/architectural/test_clock_import_ban.py tests/architectural/test_no_follow_symlinks_apply_ban.py tests/architectural/test_content_identity.py -q
.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q
make test-fast
uv run --frozen ruff check tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/_os_detection_exemptions.py tests/architectural/test_os_detection_ban.py tests/architectural/_lock_ban_exemptions.py tests/architectural/test_lock_primitive_ban.py tests/architectural/_exemptions/__init__.py tests/architectural/test_clock_call_ban.py
uv run --frozen ruff format --check tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/_os_detection_exemptions.py tests/architectural/test_os_detection_ban.py tests/architectural/_lock_ban_exemptions.py tests/architectural/test_lock_primitive_ban.py
uv run --frozen mypy tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/_os_detection_exemptions.py tests/architectural/test_os_detection_ban.py tests/architectural/_lock_ban_exemptions.py tests/architectural/test_lock_primitive_ban.py tests/architectural/_exemptions/__init__.py tests/architectural/test_clock_call_ban.py
```

(`_exemptions/__init__.py` and `test_clock_call_ban.py` are format-excluded: ruff check and mypy only.)

Pre-existing failure rule: classify any red that is also red on the planning base; if pre-existing, file (or find) a GitHub issue before continuing and cite it in the PR.

Campsite (FR-020): #2972 findings (S5778 / S5779 / S8997) only in the test files you edit; record before/after, zero is acceptable.

## Risks & Mitigations

- **Parser divergence**: three loaders each parsing their own content shape is the split-brain Paula flagged. Use only `parse_descriptor_line` / `render_descriptor_line`.
- **Clock loader globs every `*.txt`** in `_exemptions/`, including os-detect and lock-ban files. Its `CALL:`/`IMPORT:` prefix filter must keep ignoring non-prefixed content lines (the os-detect content lines start with `src/`).
- **Stale-test weakening**: the inverted stale-removal tests must still prove both directions (exempted → green, exemption removed → red) through the real detector.
- **Multiple findings on one line**: each kernel and os-detect site produces exactly one finding today, so one descriptor suppresses one finding. If a future edit adds a second forbidden literal on the same line, the multiset correctly fails it.
- **Format-excluded files**: never reformat `_exemptions/__init__.py` or `test_clock_call_ban.py`.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`):

- The first lane commit contains only the RED tests (plus behaviour-preserving seam extraction) and fails for the intended reasons (drift mismatch; loader accepts `path:line`).
- Stale detection requires "suppresses a live finding" and asserts `checked == len(...) >=` 2 (kernel) / 6 (os-detect).
- Drift tests are parametrized over a derived file set with the count asserted, use both mutations, and compare the full `(unexpected, suppressed)` sets.
- `test_pre_existing_exemption_is_still_a_real_violation` and the three `test_stale_exemption_removal_reds_the_gate` tests keep their names (inverted, not deleted).
- No loader or `.txt` file still documents or accepts the `path:line` shape; the widened WP01 ban (if on base) reports 0 line pins in your files.
- Only `_content_identity` is used for parsing, rendering and partitioning; no local copy.
- Format-excluded files were not reformatted; `test_clock_import_ban.py`, `src/`, `pyproject.toml` and the ban file are untouched.
- ruff check, ruff format --check (non-excluded files) and mypy are clean.

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
