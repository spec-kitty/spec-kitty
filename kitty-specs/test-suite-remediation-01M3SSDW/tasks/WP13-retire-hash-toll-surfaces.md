---
work_package_id: WP13
title: Retire the hash-toll surfaces
dependencies:
- WP12
requirement_refs:
- FR-009
- FR-011
- NFR-005
- C-001
- C-002
- C-007
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 45c69c47037eb79d08df5a6256aac318624dec2c
created_at: '2026-09-30T23:17:48.535252+00:00'
subtasks:
- T061
- T062
- T063
- T064
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_symbol_key.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/_symbol_key.py
- tests/unit/test_symbol_key.py
- tests/architectural/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – Retire the hash-toll surfaces

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
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

- **FR-009 (IC-11)**: Delete what existed only to maintain persisted body hashes.
  - **`SymbolKey.source_module`**: a provenance-only field, whose only reader was the old gate's provenance guards (removed in WP12) and the refresh helper (retired in WP12).
  - **Its G1–G6 guard tests** in `tests/unit/test_symbol_key.py`: 25 `source_module` references.
- **Correct the stale docstrings** in `_symbol_key.py`:
  - the module header "re-key the 394-entry allow-list";
  - the body-sensitivity section, `:47-52` ("editing a dead symbol's body changes its key and produces a false-red until the allow-list entry is refreshed");
  - the `SymbolKey` G1–G6 paragraph.
- **Correct the stale scope claim** in `tests/architectural/README.md:48`.
- **Keep `tests/unit/test_symbol_key.py`'s `assert len(index) == 400`** (`:644`). `tests/architectural/test_timing_coverage_invariant.py:338` pins it **verbatim**.
- **C-002**: The deleted guard tests pin a field that no longer exists. The covering guard for "provenance data never re-enters the allowlist" is WP11's loader rule L5 (M12 plant `source_module:` → `AllowlistSchemaError`), and it must go red.
- **Grep gate (field and import usage, not the bare word; F-01)**: `rg -n "\.source_module\b|source_module=" src tests scripts` returns nothing, and `rg -n "import .*_refresh_dead_symbol_hashes|from tests\.architectural\._refresh_dead_symbol_hashes" tests scripts` returns nothing.
  - WP11's loader and its M12 test may legitimately contain the forbidden-key literal (e.g. a scratch YAML plant carrying the retired provenance key).
  - WP12's gate docstring may name the retired helper in prose.
  - Neither is field usage, so neither is a hit.

## Context & Constraints

- Read first: `plan.md` IC-11 (as re-cut here) and the RK-1 ruling; `research/dead-symbol-rekey.md` §4 (ADR consequences), §8.1 and §8.5.2; `contracts/dead-symbol-allowlist.md` §1 (L5).
- **Re-cut from plan IC-11**:
  - The refresh helper and its 17 tests were retired **in WP12**, because they imported gate internals WP12 removes.
  - `docs/development/reference/ci-gate-mechanics.md` moved to **WP15**, which owns every `docs/` edit and the regenerated docs indexes.
  - This WP owns only the three files in its frontmatter.
- `tests/architectural/_symbol_key.py` is **format-excluded**: edit it without `ruff format`. `tests/unit/test_symbol_key.py` is not excluded.
- `SymbolKey` itself **stays**. `_resolve_final_key`, `classify_collisions`, `key_tier` and auto-exempt condition (1) still use it at runtime (G5, keyability). Remove only the `source_module` field. Keep `as_tuple` if anything still calls it; `git grep` first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`. This WP depends on WP12. Start with:

```bash
spec-kitty agent action implement WP13 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Never run `tests/architectural/` as a directory, never `make test-full`, and no heavy suites. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
4. **Quality (NFR-005).** `uv run --frozen ruff check` on the two Python files, and `ruff format --check tests/unit/test_symbol_key.py`. Delete imports that become unused (e.g. `field` from `dataclasses`, if nothing else uses it). Add no new `noqa`.
5. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
6. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits.

### Additional mission-wide rules (analysis folds)

- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1).** If an unmasked or converted test exposes a **new** product defect, never re-mask it.
  - If the fix fits this WP: make it red-first, as a failing test commit followed by a **separate** `fix(...)` commit touching only the product file(s). It is a sanctioned out-of-map `src/` edit: record a one-line rationale in your WP notes, file an issue (`gh issue create`) and add its issue-matrix row (`spec-kitty agent issue-verdict ... --verdict fixed`). The "`git diff --stat src/` must be empty" rule is lifted for exactly that commit.
  - Otherwise: mark the test `xfail(strict=True, reason="<newly filed open issue>")` and tell the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T061 – Grep gate and the C-002 covering-guard proof

- **Purpose**: A grep-gated deletion (plan IC-11). Confirm that nothing outside this WP's files still reads `source_module`, and prove the covering guard bites before deleting the G1–G6 tests.
- **Steps**:
  1. `rg -n "\.source_module\b|source_module=" src tests scripts` must show hits **only** in `tests/architectural/_symbol_key.py` and `tests/unit/test_symbol_key.py`. Any other hit is a real field user that WP12 left behind; stop and report.
     - Bare-word mentions elsewhere are expected and **not** a stop condition: the WP11 loader's and M12's forbidden-key literals, and prose.
     - Run `rg -n "source_module" src tests scripts` once for information only, and list the non-usage hits in the evidence.
  2. `rg -n "import .*_refresh_dead_symbol_hashes|from tests\.architectural\._refresh_dead_symbol_hashes" tests scripts` must return nothing (WP12 deleted the helper). Prose mentions in your owned files are fixed in T062/T064; `docs/` mentions belong to WP15.
  3. **C-002 proof**: write a scratch YAML (in the scratchpad) that is WP11's minimal valid document plus `source_module: pkg.x` on one entry. `load_allowlist(<scratch>)` raises `AllowlistSchemaError` naming L5. Also run WP11's M12 test node for the unknown-key plant: `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q -k unknown`. Record both.

### Subtask T062 – `_symbol_key.py`: remove `SymbolKey.source_module`; correct the docstrings

- **Files**: `tests/architectural/_symbol_key.py` (format-excluded).
- **Anchors**:
  - the module docstring `:1-8` ("re-key the 394-entry dead-symbol allow-list…");
  - the "Body-sensitivity (deliberate, tested)" section at `:47-52`;
  - the `SymbolKey` dataclass at `:90-120`: the docstring paragraph at `:98-108` about `source_module` and G1–G6, and the field at `:114`.
- **Steps**:
  1. Delete the `source_module` field and its docstring paragraph.
  2. Rewrite the module docstring header. `SymbolKey` is now **runtime-only**: it serves keyability and auto-exempt condition (1) in `test_no_dead_symbols.py`. The persisted allowlist identity is `(module, name)` in `dead_symbol_allowlist.yaml` (see the ADR in `docs/adr/4.x/`, dead-symbol allowlist identity). No body hash is persisted.
  3. Rewrite the "Body-sensitivity" section. A body edit changes the **runtime** content key, but no persisted allowlist entry depends on it, so a body edit costs 0 edits (FR-009 / SC-003). Delete the "false-red until the allow-list entry is refreshed" and "intentional price" sentences.
  4. Keep the lazy import of `_find_facade_lazy_dict_name` / `_resolve_relative_module` (`:397`) unchanged.
  5. `git grep -n "as_tuple" -- tests`: if `SymbolKey.as_tuple` has no remaining caller outside its own unit tests, leave it (not in scope), and note it as a follow-up candidate in the evidence. Do not widen the WP.
- **Edge cases**: The dataclass is `frozen=True`. Removing a defaulted trailing field does not break positional construction elsewhere, but `git grep -n "SymbolKey(" -- tests` to be sure.

### Subtask T063 – `tests/unit/test_symbol_key.py`: remove the G1–G6 guards; keep `== 400`

- **Files**: `tests/unit/test_symbol_key.py`.
- **Anchors**:
  - the section header "G1-G6 -- source_module non-goal guards (#3552 WP01)" at `:662`;
  - the tests `test_source_module_is_non_comparing` (`:668`), `…_ignored_by_equality_content_tier` (`:677`), `…_ignored_by_equality_collision_tier` (`:685`), `…_ignored_by_hash_and_frozenset_membership` (`:698`), `…_does_not_escalate_content_tier` (`:711`), `…_excluded_from_as_tuple_content_and_collision_tier` (`:733`) and `…_does_not_affect_body_hash_and_resolver_key_has_none` (`:744-764`);
  - **keep** `:644`: `assert len(index) == 400  # 200 modules * 2 symbols each`.
- **Steps**:
  1. Delete the G1–G6 section. Scan every deleted test for an assertion that is **not** about `source_module`, e.g. "`as_tuple()` returns the 2-tuple for content tier" in `:733`, or "a resolver-minted key hashes identically" in `:744`. If one is still meaningful for the runtime `SymbolKey`, keep it as a small test without `source_module`, and record it.
  2. `rg -n "source_module" tests/unit/test_symbol_key.py` must return nothing.
  3. `rg -n "len\(index\) == 400" tests/unit/test_symbol_key.py` must return exactly 1.
  4. Run:
     ```bash
     uv run --frozen pytest tests/unit/test_symbol_key.py tests/architectural/test_timing_coverage_invariant.py -n0 -q
     ```
     Both must be green. The invariant pins the `== 400` text.
- **Parallel?**: Yes, alongside T062 after T061.

### Subtask T064 – `tests/architectural/README.md` scope claim; evidence

- **Files**: `tests/architectural/README.md`.
- **Anchor**: `:48`, "**`test_no_dead_symbols.py`** — Walks `__all__` on every module in `src/charter/` and `src/kernel/`; asserts every exported name has at least one external caller." This is stale:
  - the gate walks **every** `src/**/*.py` module;
  - its scope is `__all__` ∪ public module-level names (#470);
  - exemptions come from `dead_symbol_allowlist.yaml`, by `(module, name)`, plus structural auto-exemptions.
- **Steps**:
  1. Rewrite the bullet to the true scope in one or two sentences, and mention the YAML allowlist and the loader.
  2. If the README lists `_refresh_dead_symbol_hashes.py` or `test_refresh_dead_symbol_hashes.py` anywhere, remove those lines.
  3. **Campsite (F-15)**: `README.md:83` cites a nonexistent `spec-kitty doctor ratchet`. Replace it with the real way to inspect ratchet state, i.e. run `tests/architectural/test_ratchet_baselines.py` by name, or delete the sentence. Verify first with `spec-kitty doctor --help`.
  4. The full named-file run (Test Strategy), then `make test-fast`.
  5. **Evidence records**:
     - **EV-IC11-01**: RETIRE of G1–G6. Covering guard: the L5 plant is red, and the subject (the field) is deleted;
     - **EV-IC11-02**: grep-gate output;
     - **EV-IC11-03**: the timing invariant green with `== 400` retained;
     - the RK-1 note: the executed-test count drops by the number of deleted G-tests.

## Test Strategy

```bash
uv run --frozen pytest tests/unit/test_symbol_key.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q
uv run --frozen ruff check tests/architectural/_symbol_key.py tests/unit/test_symbol_key.py
uv run --frozen ruff format --check tests/unit/test_symbol_key.py
make test-fast
```

## Risks & Mitigations

- **Dropping a still-meaningful runtime assertion** along with the G-tests. Scan each test (T063 step 1).
- **The pinned `== 400`** must survive verbatim; the timing invariant enforces it.
- **A hidden `source_module` user**: the T061 grep gate catches it before any deletion.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- `rg -n "\.source_module\b|source_module=" src tests scripts` → empty, and `rg -n "import .*_refresh_dead_symbol_hashes|from tests\.architectural\._refresh_dead_symbol_hashes" tests scripts` → empty. Bare-word literals in the WP11 loader and its tests are expected (F-01).
- `len(index) == 400` is still present, and `test_timing_coverage_invariant.py` is green.
- The docstrings no longer describe body-hash re-pins as the price of the design.
- The L5 plant is red (the C-002 covering guard).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T061 T062 T063 T064 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP13 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
