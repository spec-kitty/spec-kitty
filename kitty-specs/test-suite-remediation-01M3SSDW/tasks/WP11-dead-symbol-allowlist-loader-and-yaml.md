---
work_package_id: WP11
title: Dead-symbol allowlist loader and YAML migration
dependencies:
- WP10
requirement_refs:
- FR-009
- FR-011
- NFR-005
- C-001
- C-003
- C-007
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: b5d180ac7199301ac72181e0aa0e25590d46c4dd
created_at: '2026-09-30T21:23:24.747085+00:00'
subtasks:
- T050
- T051
- T052
- T053
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_dead_symbol_allowlist.py
create_intent:
- tests/architectural/_dead_symbol_allowlist.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/test_dead_symbol_allowlist_loader.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- tests/architectural/_dead_symbol_allowlist.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/test_dead_symbol_allowlist_loader.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Dead-symbol allowlist loader and YAML migration

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

- **FR-009 / DIRECTIVE_044**: The exemption data moves out of the 4,824-line gate file into a **schema-validated YAML file**, `tests/architectural/dead_symbol_allowlist.yaml`. It is read by a **pure, schema-enforcing loader**, `tests/architectural/_dead_symbol_allowlist.py`, which implements rules L1–L10 of `contracts/dead-symbol-allowlist.md` §1.
- The **#470 widened grandfather list** (91 `"module::Name"` strings) folds into the same file, as `widened_grandfathered_470` (R2, D-12). The result is one exemption authority per gate.
- **Migration**: 293 allowlist entries (from 294 literals; the duplicate `check_push_safety` collapses) plus 91 widened entries, with identity `(module, name)`.
  - **`module_path` wins over `source_module`** (the `merge_three_layers` trap: `charter.drg` wins over `charter.offering.drg.merge`).
  - Category ids are the existing constant names, lower-cased, with the leading underscore dropped: `_CATEGORY_A_SLICE_F_DEFERRED` → `category_a_slice_f_deferred` (RK-4).
  - The 9 empty tombstone categories are **not** migrated.
- **Data-level parity** is proven by a **scratchpad** check, not a committed test. The YAML key set must equal `{(k.module_path or k.source_module, k.bare_name) for k in _SYMBOL_ALLOWLIST}`, and the widened set must be equal too.
- **M12** (the loader schema battery) is committed in a new `tests/architectural/test_dead_symbol_allowlist_loader.py`. The contract places M12 "in the gate", but it exercises only the loader. Hosting it next to the loader keeps WP11 and WP12 file-disjoint.
- **The gate is NOT switched here** (WP12 does that). After this WP, the YAML is committed but not yet read by the gate. That is a transient state inside the mission chain.

## Context & Constraints

- Read first: `contracts/dead-symbol-allowlist.md` §0–§1 and §4; `data-model.md` §1 (every field rule, the in-memory model and the exports); `research/dead-symbol-rekey.md` §4, §6 and §8.4; `plan.md` IC-10 and the RK-4 / RK-6 rulings.
- **The seam surface is fixed by WP10.** Read `tests/architectural/test_dead_symbol_allowlist_contract.py` (landed by WP10) and implement these **exact** names:
  - `ALLOWLIST_PATH`;
  - `load_allowlist(path: Path = ALLOWLIST_PATH) -> DeadSymbolAllowlist`;
  - `AllowlistSchemaError(ValueError)`;
  - `StaleVerdict`: a `StrEnum` whose members `INVALID`, `GONE`, `REVIVED`, `SUPERSEDED` and `MOOT` have upper-case values;
  - `DeadSymbolKey(module, name)`: frozen, with `__str__` giving `module::name`;
  - `DeadSymbolAllowlist`, with `.keys: frozenset[DeadSymbolKey]` and `.widened_qualified: frozenset[str]`;
  - `SYMBOL_ALLOWLIST: frozenset[DeadSymbolKey]` and `WIDENED_SCOPE_GRANDFATHERED_470: frozenset[str]`, both loaded at import.

  Also provide `AllowlistCategory`, `AllowlistEntry` and `WidenedEntry`, per data-model §1.4.
- The loader is **pure**: no import of `src/`, no corpus walk, no network. It uses PyYAML (`yaml`), which is already a test dependency; see `_baselines.yaml`'s loader in `test_ratchet_baselines.py` for house style.
- **Never add** a `line:`, `body_hash:` or `source_module:` field. There is no inline escape marker (contract §1). `test_ratchet_positional_anchor_ban.py` must stay green, but it does **not** guard this file: its YAML arm scans only `_YAML_ALLOWLISTS = ("inline_meta_read_allowlist.yaml",)` (`:166`). The real guards are loader rules L2 and L5 plus M12, and the evidence must name those, not the anchor ban (F-12).
- The allowlist **size lives only** in `_baselines.yaml` (WP14), never inside the YAML data (the `inline_meta_read` three-authority anti-pattern).
- Precedent YAML allowlists beside `_baselines.yaml`: `inline_meta_read_allowlist.yaml`, `charter_path_literal_allowlist.yaml`, `mission_type_reader_allowlist.yaml`, `requirement_id_pattern_allowlist.yaml`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`. This WP depends on WP10; the resolver bases its workspace on WP10's lane. Start with:

```bash
spec-kitty agent action implement WP11 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Never run `tests/architectural/` as a directory, never `make test-full`, and no heavy suites. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **The converter is scratchpad-only (contract §4).** It is never committed as a tool.
4. **Evidence.** Write data-model §4 YAML records, plus the converter summary and the data-parity output, into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Quality (NFR-005).** Run `uv run --frozen ruff check`, `uv run --frozen ruff format --check` and `uv run --frozen mypy tests/architectural/_dead_symbol_allowlist.py` on the new Python files. **Zero findings.** Keep complexity ≤ 15 per function: split validation into one small function per rule family. Hoist repeated literals such as error-rule ids and key names into constants (S1192). Add no `noqa` or `type: ignore`.
6. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-opus-5-5`.
7. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
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
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. This WP's new or rewritten typed modules also run `uv run --frozen mypy tests/architectural/_dead_symbol_allowlist.py tests/architectural/test_dead_symbol_allowlist_loader.py`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T050 – The loader module (L1–L10)

- **Purpose**: One authority that turns free comments into enforced fields: a required rationale, a required issue where the category demands one, whole-file uniqueness and no tombstones.
- **Files**: `tests/architectural/_dead_symbol_allowlist.py` (new).
- **Steps**:
  1. **Types** (frozen dataclasses; data-model §1.4):
     - `DeadSymbolKey(module: str, name: str)`, with `__str__` returning `f"{self.module}::{self.name}"`;
     - `AllowlistCategory(id, rationale, requires_issue, target: str | None)`;
     - `AllowlistEntry(key, category, rationale: str | None, issue: str | None)`, with an `effective_rationale(categories)` helper or property;
     - `WidenedEntry(key, note: str | None)`;
     - `DeadSymbolAllowlist(categories: Mapping[str, AllowlistCategory], entries: tuple[AllowlistEntry, ...], widened_entries: tuple[WidenedEntry, ...], widened_rationale: str, widened_issue: str)`, with the properties `keys` and `widened_qualified`.
     - `StaleVerdict(StrEnum)`. The docstring and a `__all__` comment say: "shared verdict vocabulary; assigned only by the gate; no loader rule depends on it" (F-16). It lives here so that the import graph stays gate → loader, with the loader as a pure leaf.
  2. **L1/L3, the duplicate-key-rejecting loader**: subclass `yaml.SafeLoader` and override the mapping construction so it raises on a repeated key at **any** level (PyYAML silently keeps the last one). Raise `AllowlistSchemaError`, naming the file, the key and the location pointer.
  3. **L2**: the top level is a mapping with **exactly** `{schema_version, categories, entries, widened_grandfathered_470}`.
  4. **L4**: `schema_version == 1`, and it must be an `int`, not a `bool`.
  5. **L5**: unknown keys are rejected in categories, entries, the widened section and widened entries. The allowed sets are:
     - categories: `rationale`, `requires_issue`, `target`;
     - entries: `module`, `name`, `category`, `rationale`, `issue`;
     - widened: `rationale`, `issue`, `entries`;
     - widened entries: `module`, `name`, `note`.

     This automatically refuses `line`, `body_hash` and the retired provenance field. In prose and docstrings, say "the retired provenance field" rather than its identifier. A forbidden-key literal inside an M12 plant is fine: WP13's grep gate matches field **usage** only (`\.source_module\b|source_module=`).
  6. **L6**: every category `rationale` is a non-empty stripped `str`. An entry `rationale`, if present, is non-empty.
  7. **L7**:
     - `category` must be declared;
     - `requires_issue` must be a real `bool`;
     - if it is `True`, then `issue` must be present and match `^(#\d+|[\w.-]+/[\w.-]+#\d+)$`;
     - any `issue` that is present must match the pattern;
     - the widened `issue` is required and must match too.
  8. **L8**: `(module, name)` is unique across `entries` ∪ `widened_grandfathered_470.entries`. The error names **both** locations (e.g. `entries[12]` and `widened_grandfathered_470.entries[3]`).
  9. **L9**: every declared category has at least one entry, so there are no tombstones.
  10. **L10**: `module` matches `^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$` under `re.ASCII`, and `name.isidentifier()` holds with no `.` in it.
  11. **Category-id rule** (data-model §1.2): the keys match `^category_[a-z0-9_]+$`.
  12. **Errors**: `AllowlistSchemaError(ValueError)`. The message is `f"{path}: {pointer}: [{rule}] {detail}"`, e.g. `dead_symbol_allowlist.yaml: entries[41].issue: [L7] …`.
  13. **Import-time constants**: `ALLOWLIST_PATH = Path(__file__).with_name("dead_symbol_allowlist.yaml")`; `ALLOWLIST: DeadSymbolAllowlist = load_allowlist()` (the **single** parse, public; WP12 evaluates both sections from it, F-05); `SYMBOL_ALLOWLIST = ALLOWLIST.keys`; `WIDENED_SCOPE_GRANDFATHERED_470 = ALLOWLIST.widened_qualified`. The last two are views of the one parse, not a second read.
  14. Declare `__all__` with the public names, including `ALLOWLIST`.
- **Edge cases**:
  - `entries: []` is allowed only when fully burned down (data-model §1.2). **Decided (analysis B4):** an empty `entries` requires an empty `categories` mapping, so L9 holds vacuously. The "categories non-empty" rule applies only while entries exist. Document this in the loader docstring and cover it with one M12 case: `entries: []` plus a non-empty `categories` raises L9.
  - Because the constants are loaded at import, a schema error fails collection loudly, which is intended.

### Subtask T051 – Scratchpad converter → `dead_symbol_allowlist.yaml`

- **Purpose**: A mechanical, reviewable migration of the 293 entries and 91 widened entries (contract §4 step 2).
- **Files**: `tests/architectural/dead_symbol_allowlist.yaml` (new). The converter script lives **only** in your session scratchpad.
- **Steps**:
  1. Write `convert_allowlist.py` in the scratchpad. It imports `tests.architectural.test_no_dead_symbols as g`, which is still the old gate on this lane.
  2. **Entries**: for each `(const_name, keys)` in `g._category_frozensets().items()`, **skip empty** frozensets (the 9 tombstones). For each `SymbolKey`:
     - `module = key.module_path if key.module_path is not None else key.source_module`. **`module_path` wins.** Assert `module` is not `None`; all 275 content-tier entries carry `source_module`.
     - `name = key.bare_name`.
     - `category = const_name.lstrip("_").lower()`.
  3. **Rationales** (best-effort, then hand-review): use `tokenize` over `test_no_dead_symbols.py`.
     - The comment block immediately above each category constant (e.g. `:130-152` for category A) becomes the **category** rationale. It must be non-empty; if a block is missing, synthesize a one-line rationale from the nearest header comment and flag it for review.
     - A comment run immediately above an individual `SymbolKey(...)`, or its trailing `# module::Name` comment, becomes the **entry** rationale. Strip the `module::Name` prefix and "Hash re-pinned…" toll notes; those are history, not rationale.
     - Extract `#NNNN` references into `issue` when exactly one issue is clearly the tracker for that entry. **Never fabricate an issue.**
  4. **`requires_issue`**: set `true` **only** for categories where every migrated entry carries an extracted issue **and** the category's historical rule demanded one (the FR-303 "category B" rule). Otherwise set `false`, and record every category-B entry without an issue as a gap in the evidence (a follow-up, not a fabricated issue).
  5. **Widened**: split each `g._WIDENED_SCOPE_GRANDFATHERED_470` string on `::`. Carry its per-entry comment as `note` where one exists. The section `rationale` comes from the comment block at `test_no_dead_symbols.py:3617-3631`, and `issue: "#633"`.
  6. **Dedup**: the duplicate `check_push_safety` (`:1329-1334`) collapses to one entry. Assert the final count is `293`, and record "294 literals → 293 members" in the evidence.
  7. **Emit** the YAML deterministically: a header comment pointing to `_dead_symbol_allowlist.py` and the ADR (WP15; name it generically, e.g. "see docs/adr/4.x (dead-symbol allowlist identity)"); categories in source order; entries sorted by `(category order, module, name)`; `yaml.safe_dump(..., sort_keys=False, allow_unicode=True, width=100)`, or a hand-rolled emitter if you need comments. **No line numbers anywhere.**
  8. Hand-review the diff for garbled rationales, and fix them in the YAML directly.
- **Edge cases**:
  - **`merge_three_layers`**: confirm the YAML has `module: charter.drg`, not `charter.offering.drg.merge`.
  - 18 module_path-tier entries: confirm each maps to its `module_path`.

### Subtask T052 – `test_dead_symbol_allowlist_loader.py`: M12 plus real-file invariants

> **Commit order (C-011, D1 reading).** Write this test file **first** and commit it **before** the T050 loader implementation, as a separate failing-first commit: `test(architectural): M12 schema battery for the dead-symbol allowlist loader (red) (#5346)`. At that commit each test is RED on its own (analysis N2, same standard as WP10): import the loader **inside each test body** (or through a small helper each test calls), never at module scope, so collection succeeds and every test fails individually with `ModuleNotFoundError: tests.architectural._dead_symbol_allowlist`. A collection-level error is not an acceptable red. Then commit the loader (T050) and the YAML (T051); the file goes GREEN. Record both SHAs.

- **Purpose**: Committed coverage for the loader. M12 replaces the gate's cross-category duplicate guards (`:2506`/`:2537`, deleted by WP12) and closes the intra-category blind spot.
- **Files**: `tests/architectural/test_dead_symbol_allowlist_loader.py` (new). Add `pytestmark = [pytest.mark.architectural]`.
- **Steps**:
  1. A helper `_minimal(**overrides) -> dict` that builds a valid document, plus `_dump(tmp_path, doc_or_text) -> Path`. Duplicate-key plants need **raw text**, because a dict cannot hold duplicate keys.
  2. **M12**: parametrize over one plant each. Every plant raises `AllowlistSchemaError`, and the message names the rule id and the location:
     - a duplicate `(module, name)` in the same category (L8);
     - the same in different categories (L8);
     - the same across `entries` and widened (L8);
     - an undeclared category (L7);
     - an empty category rationale (L6);
     - an empty entry rationale (L6);
     - `requires_issue: true` with no `issue` (L7);
     - a malformed `issue` (L7);
     - `requires_issue: "yes"`, a non-bool (L7);
     - a duplicate category key, as raw text (L3);
     - a duplicate top-level key, as raw text (L3);
     - an unknown key `line: 12` (L5);
     - an unknown key `body_hash` (L5);
     - a tombstone category with no entries (L9);
     - `schema_version: 2` (L4);
     - a missing top-level section (L2);
     - a bad module path `specify_cli..x` (L10);
     - a dotted name `a.b` (L10);
     - a bad category id `cat_x` (the category-id pattern).
  3. **A valid minimal document loads**, and `keys` / `widened_qualified` have the expected content and types (`frozenset[DeadSymbolKey]` and `frozenset[str]`).
  4. **Real-file invariants** (not parity; these must survive WP12):
     - `load_allowlist()` succeeds;
     - `SYMBOL_ALLOWLIST` and `WIDENED_SCOPE_GRANDFATHERED_470` are non-empty frozensets of the right element types;
     - `len(SYMBOL_ALLOWLIST) == len(ALLOWLIST.entries)`, i.e. no silent dedupe;
     - no entry carries a forbidden key (implied by L5, but assert it on the raw document too).

     **Do not** assert 293 or 91; the size lives only in `_baselines.yaml` (WP14).
  5. Run it: all green.
- **Parallel?**: No. The test file is written and committed FIRST, before T050 and T051 (C-011 commit order above; analysis N1). It goes green once T050 and T051 land.

### Subtask T053 – Data-level parity (scratchpad), quality gates, evidence

- **Purpose**: Prove the YAML is a lossless re-encoding of today's constants **before** WP12 switches the gate to it.
- **Steps**:
  1. **Scratchpad parity check**, which is not committed:
     ```python
     from tests.architectural import test_no_dead_symbols as g
     from tests.architectural import _dead_symbol_allowlist as a
     old = {(k.module_path or k.source_module, k.bare_name) for k in g._SYMBOL_ALLOWLIST}
     new = {(k.module, k.name) for k in a.SYMBOL_ALLOWLIST}
     assert old == new and len(new) == 293
     assert set(g._WIDENED_SCOPE_GRANDFATHERED_470) == set(a.WIDENED_SCOPE_GRANDFATHERED_470) and len(a.WIDENED_SCOPE_GRANDFATHERED_470) == 91
     # category parity: old owning category (lower-cased, "_" stripped) == new entry.category for every key
     ```
     Record the output. If the counts differ because the base moved, record both, and re-take WP10's snapshot at WP12.
  2. **Gates** (by file):
     ```bash
     uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_dead_symbols.py -n0 -q
     ```
     `test_no_dead_symbols.py` is still the old gate and must still be GREEN. The new YAML is inert to it.
  3. `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q`: now each test should fail on `AttributeError: … _evaluate_allowlist` (the loader exists; the gate seam does not). Record this progression.
  4. Run ruff, format and mypy on the two new Python files. `make test-fast` once.
  5. **Evidence records**:
     - **EV-IC10a-01**: the converter summary (literal count 294, member count 293, tombstones dropped 9, `merge_three_layers` module check, the `requires_issue` decisions and gaps);
     - **EV-IC10a-02**: the data-parity output;
     - **EV-IC10a-03**: the M12 run.
- **Commits, in order**:
  1. `test(architectural): M12 schema battery for the dead-symbol allowlist loader (red) (#5346)`, the T052 test file only, RED;
  2. `test(architectural): schema-enforcing dead-symbol allowlist loader (#5346)`, T050;
  3. `test(architectural): migrate dead-symbol allowlist to (module, name) YAML incl. #470 widened list (#5346)`, T051, which turns the loader tests GREEN.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q
uv run --frozen pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_dead_symbols.py -n0 -q
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q     # still RED (gate seam missing) — expected
uv run --frozen ruff check tests/architectural/_dead_symbol_allowlist.py tests/architectural/test_dead_symbol_allowlist_loader.py
uv run --frozen ruff format --check tests/architectural/_dead_symbol_allowlist.py tests/architectural/test_dead_symbol_allowlist_loader.py
uv run --frozen mypy tests/architectural/_dead_symbol_allowlist.py
make test-fast
```

If `mypy` on a `tests/` path reports configuration or import-resolution problems rather than code findings (for example missing `types-PyYAML` stubs), record the exact output and ask the orchestrator. Do not add ignores.

## Risks & Mitigations

- **The `merge_three_layers` trap.** Prefer `module_path` whenever it is set, and check that entry by hand.
- **PyYAML silent duplicate-key merge.** The custom loader handles it, and the M12 raw-text plants prove it.
- **Rationale quality.** Best-effort extraction plus hand-review. Garbled or empty rationales fail L6 at import, which is loud and good.
- **The WP10 contract tests stay strict-xfail on this WP's hand-off.** That is expected; WP12 removes the markers. If any of them XPASSes here, the loader alone already satisfied a contract WP12 was meant to deliver. Stop and report it; do not remove the marker yourself.

## Definition of Done (C-011)

- **C-011 (D1 reading, `traces/design-decisions.md`)**: the loader tests (`tests/architectural/test_dead_symbol_allowlist_loader.py`, the M12 battery plus the valid-document and real-file tests) are committed **failing-first**, in a separate commit **before** the loader implementation. They are RED at that commit (`ModuleNotFoundError` for the loader) and GREEN at this WP's final commit. Record both commit SHAs.

## Review Guidance

- Spot-check 10 random YAML entries against the old literals: the module, name and category are right.
- `merge_three_layers` → `charter.drg`.
- No `line`, `body_hash` or `source_module` keys.
- M12 covers every rule id L2–L10 plus the category-id pattern.
- The data-parity output shows 293 / 91 and equality.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-opus-5-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T050 T051 T052 T053 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP11 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```

> **Rule A, notification step (analysis N7).** If you take the FR-005 fix route, say so in your final report (defect, commit SHA, new issue number, sanctioned out-of-map `src/` path), so the orchestrator can record the issue-matrix row and check that no other lane owns that file.
