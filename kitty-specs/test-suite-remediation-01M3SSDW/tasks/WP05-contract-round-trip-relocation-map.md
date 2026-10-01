---
work_package_id: WP05
title: Contract round-trip relocation map
dependencies: []
requirement_refs:
- FR-004
- FR-011
- NFR-001
- NFR-004
- NFR-005
- C-001
- C-006
- C-007
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 6b06d1dc0fde10b79a2083dd934a278b417f7d72
created_at: '2026-09-30T21:15:52.035861+00:00'
subtasks:
- T021
- T022
- T023
phase: Phase 1 - Masked greens
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_module_relocations.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/contract/test_example_round_trip.py
- tests/contract/_module_relocations.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Contract round-trip relocation map

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

- **FR-004 (masked-greens row 16)**: The 10 contract round-trip cases that skip forever now run.
  - They skip today because the archived contract docs name modules that were relocated long ago:
    - `doctrine.drg.*` → `charter.offering.drg.*`;
    - `specify_cli.next._internal_runtime.*` → `runtime.next._internal_runtime.*`;
    - `charter.scope` → `charter.activation.scope`;
    - `charter.schemas` → `charter.activation.schemas`.
  - The target is **29 round-trip cases passing, 32 passed in total including the 3 map self-tests, 0 skipped**. Today it is 19 passed, 10 skipped.
- A module absent under **both** its historical and canonical names **fails**, naming both. `except ImportError: pytest.skip` and the `hasattr` skip are removed.
- A self-test guarantees the map has no dead rows: every target is importable, and every key is referenced by at least one archived contract.
- **FR-011**: planted-break records. **NFR-001**: executed count ≥ before + 10.
- **C-006**: archived contracts under `kitty-specs/` are immutable. The map is test-side only.

## Context & Constraints

- Read first: `plan.md` IC-05; `research.md` D-9; `research/masked-greens.md` row 16; `quickstart.md` §FR-004 (Break #11).
- **Files**:
  - `tests/contract/test_example_round_trip.py` is **format-excluded**. Edit it without `ruff format`.
  - `tests/contract/_module_relocations.py` is new and **not** excluded, so it must pass `ruff format --check`.
- **Anchors in `test_example_round_trip.py`**:
  - `import importlib` at `:63`;
  - `test_contract_example_round_trip` at `:596-700`, with `importlib.import_module(module_dotted)` at `:640-641`;
  - the `except ImportError` → `pytest.skip(...)` at `:642-654`;
  - the `hasattr` → `pytest.skip(...)` at `:656-663`.
- `tests/architectural/test_ratchet_baselines.py` (read-only here; WP14 owns it) references this module through `_ROUND_TRIP_CONTRACT_MODULE` and runs `test_fast_collection_does_not_import_round_trip_corpus`. Run it by name so you know your new import does not break that test.
- Do not change `_LEGACY_CONTRACT_ALLOWLIST` or its baseline leaf (`legacy_contract_allowlist: 151`).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP05 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **Planted breaks never land (C-007).** Scratch edits only; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**: before, the case SKIPS; after, it FAILS naming the module.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP05 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" tests/contract/test_example_round_trip.py tests/contract/_module_relocations.py`. The only surviving skips are the explicit `# round-trip: skip: <reason>` marker semantics, which carry a reason by construction.
6. **Quality (NFR-005).** `uv run --frozen ruff check` on both files and `uv run --frozen ruff format --check tests/contract/_module_relocations.py`. The new module is fully typed (`Mapping[str, str]`, typed functions). Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md).
9. **Commit trailers.** End every commit with:
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
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. This WP's new or rewritten typed modules also run `uv run --frozen mypy tests/contract/_module_relocations.py` (the new typed module). Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T021 – Create `tests/contract/_module_relocations.py`

- **Purpose**: A single, test-side authority for "archived contract module name → canonical module name". The archived contracts cannot be edited (C-006), so the mapping has to live on the test side.
- **Files**: `tests/contract/_module_relocations.py` (new).
- **Steps**:
  1. **Baseline**: `uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs` should show 19 passed and 10 skipped. Copy the 10 skip reasons into your notes; they name the missing modules.
  2. Create the module with a docstring that explains C-006 and the four relocations:
     ```python
     """Historical -> canonical module relocations for archived contract examples (C-006)."""

     from __future__ import annotations

     import importlib
     from collections.abc import Mapping
     from types import ModuleType
     from typing import Final

     HISTORICAL_TO_CANONICAL: Final[Mapping[str, str]] = {
         "specify_cli.next._internal_runtime": "runtime.next._internal_runtime",
         "doctrine.drg": "charter.offering.drg",
         "charter.schemas": "charter.activation.schemas",
         "charter.scope": "charter.activation.scope",
     }

     def canonical_module_name(historical: str) -> str | None: ...
     def import_contract_module(dotted: str) -> ModuleType: ...
     ```
  3. `canonical_module_name`: return the rewritten dotted path using the **longest matching prefix first**. Match on whole dotted segments only: `charter.scope` must not match `charter.scoped`. Sort the keys by length, descending, and match `dotted == key or dotted.startswith(key + ".")`. Return `None` when nothing matches.
  4. `import_contract_module`: try `importlib.import_module(dotted)`. On `ImportError`, try the canonical rewrite. If the rewrite also fails, raise an `ImportError` whose message names **both** names (e.g. `"neither 'doctrine.drg.models' nor canonical 'charter.offering.drg.models' is importable: <exc>"`). If **no** relocation row matches, the message names the historical module and says "no relocation row matches". Chain it with `from exc` in both cases.
  5. Verify the four canonical targets exist before committing:
     ```bash
     uv run --frozen python -c "import runtime.next._internal_runtime, charter.offering.drg, charter.activation.scope, charter.activation.schemas"
     ```
     If a target differs from the table above (e.g. a further move), use the real canonical path and note it in the evidence. The 10 skip reasons from step 1 are the authority for the keys.
- **Edge cases**:
  - Keep the functions simple (complexity well below 15). No caching is needed.
  - Name the module with a leading underscore so pytest never collects it as a test module.

### Subtask T022 – Route the round-trip through the map; fail on absence

- **Purpose**: Replace the permanent skips with honest execution, and make a missing model a loud failure.
- **Files**: `tests/contract/test_example_round_trip.py` (format-excluded).
- **Steps**:
  1. Import the resolver: `from tests.contract._module_relocations import import_contract_module`. Check that other test modules import `tests.contract` this way; `tests/contract/conftest.py` exists, and `tests` is a package.
  2. Replace the `try: module = importlib.import_module(module_dotted) except ImportError: pytest.skip(...)` block (`:640-654`) with:
     ```python
     try:
         module = import_contract_module(module_dotted)
     except ImportError as exc:
         pytest.fail(f"'{contract_label}': pydantic_model module is not importable: {exc}")
     ```
     Delete the "Slice F ATDD pattern … Skip (don't fail)" comment block; it is stale because those WPs landed long ago.
  3. Replace the `hasattr` skip (`:656-663`) with `pytest.fail(...)` naming the module and the missing class. That is the same masking pattern; a missing class on a relocated module is a real contract drift.
  4. Remove the `importlib` import if it becomes unused.
  5. Run `uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs`. Expect **29 passed, 0 skipped** at this step (verified in scratch by the research lens); T023 adds 3 self-tests, which brings it to 32.
     - If a case now FAILS on `model_validate`, the archived example and the live model have drifted. That is a real finding. Do **not** re-mask it. Classify it:
       - a stale example: the map cannot fix it, so record it and ask the orchestrator (the archived contract cannot be edited);
       - a product defect: follow FR-005 (a new issue plus a strict xfail) and report it.
- **Edge cases**: The parametrize ids come from contract labels. Do not change the discovery functions (`_discover_examples`, `_collect_*`).

### Subtask T023 – Map self-test, planted breaks, evidence

- **Purpose**: Stop the map rotting (a dead row) or lying (a row whose target does not exist), and prove the new form reds (FR-011).
- **Files**: `tests/contract/test_example_round_trip.py`. Add the self-tests next to the other unit tests at the bottom of the file (`:702+`).
- **Steps**:
  1. Add `test_module_relocation_targets_are_importable`: every value of `HISTORICAL_TO_CANONICAL` imports.
  2. Add `test_module_relocation_keys_are_referenced_by_an_archived_contract`: build the set of `model_path` module prefixes from `_discover_examples()` (the same discovery the parametrized test uses) and assert that every map key is a whole-segment prefix of at least one of them. A dead row fails, naming the key.
  3. Add `test_canonical_module_name_prefers_longest_prefix`: a pure unit test with a synthetic map or the real map. A nested module resolves deterministically, a non-matching name returns `None`, and `charter.scoped` does not match `charter.scope`.
  4. **Planted breaks** (scratch; revert with `git checkout -- tests/contract/_module_relocations.py`):
     - **Break #11**: delete the `doctrine.drg` row. The affected round-trip cases **FAIL** and name both module names; the old form SKIPPED. The self-test `…_are_referenced_…` still passes, because it checks the rows that exist.
     - **Dead row**: add `"nonexistent.module": "charter.offering.drg"`. The referenced-by-a-contract self-test goes RED.
     - **Product break**: rename a field on a `charter.offering.drg.models` class used by a contract example (scratch edit of `src/charter/offering/drg/models.py`; revert with `git checkout -- src/charter/offering/drg/models.py`). The round-trip goes RED on `model_validate`.
  5. **NFR-001 counts**: 19 executed and 10 skipped before; **32** executed (29 round-trip cases plus 3 self-tests) and 0 skipped after.
  6. Run `tests/architectural/test_ratchet_baselines.py` by name (read-only). `test_fast_collection_does_not_import_round_trip_corpus` stays green.
  7. `make test-fast` once.
- **Evidence records**: MG-16 (CONVERT): before and after counts plus the three plants.

## Test Strategy

```bash
uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -q -rs
uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q
uv run --frozen ruff check tests/contract/test_example_round_trip.py tests/contract/_module_relocations.py
uv run --frozen ruff format --check tests/contract/_module_relocations.py
make test-fast
```

## Risks & Mitigations

- **Prefix ambiguity.** Match longest prefix first, on whole segments only. The unit test pins this.
- **A relocated module that was also renamed at the class level.** The `hasattr` failure names it. Do not add class-level aliases to the map unless an example demands one, and report it if one does.
- **Collection-time cost.** The map module is tiny and imports lazily. `test_fast_collection_does_not_import_round_trip_corpus` guards collection cost.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- `-rs` shows **32 passed** (29 round-trip cases plus 3 map self-tests) and 0 skipped.
- No `pytest.skip` remains on the import or `hasattr` path.
- Re-run Break #11 yourself: the failure message names both module names.
- The map has exactly the rows that the 10 former skips need, with no speculative rows.

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
spec-kitty agent tasks mark-status T021 T022 T023 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP05 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
