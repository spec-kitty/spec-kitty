---
work_package_id: WP03
title: Mission metadata loads a BOM-prefixed meta.json
dependencies: []
requirement_refs:
- FR-013
- FR-015
- FR-016
- NFR-002
- NFR-003
- NFR-004
- C-002
- C-004
- SC-005
planning_base_branch: fix/quick-win-remediation
merge_target_branch: fix/quick-win-remediation
branch_strategy: Planning artifacts for this mission were generated on fix/quick-win-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/quick-win-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
phase: Phase 1 - Independent fixes
history:
- at: '2026-11-10T08:19:33Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/mission_metadata.py
create_intent:
- docs/changelog/unreleased/7445-load-meta-accepts-bom.fixed.md
execution_mode: code_change
model: glm-5.3
owned_files:
- src/specify_cli/mission_metadata.py
- tests/specify_cli/test_mission_metadata.py
- docs/changelog/unreleased/7445-load-meta-accepts-bom.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Mission metadata loads a BOM-prefixed meta.json

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

**#7445, operator decision 2026-11-10, Option A.** A `meta.json` saved with a UTF-8 byte-order mark (BOM, bytes `EF BB BF`) must load like the same file without it through the canonical loader `load_meta` (every `on_malformed` mode) and through `parse_meta_file`. Today the canonical loader raises `ValueError` ("Unexpected UTF-8 BOM"), and callers that pass `on_malformed="none"` (e.g. `status/emit.py` `_load_mission_id`) get `None`, so the Mission becomes invisible. (FR-013, SC-005)

Done means:
- `load_meta(d)` and `load_meta(d, on_malformed="none")` and `parse_meta_file(path)` return the mapping for a BOM-prefixed file.
- `load_meta_strict(d, bom_tolerant=False)` still returns `{}` for that file (negative control, unchanged).
- A non-BOM file decodes byte-identically to today (FR-015).
- The kernel decoder `src/kernel/meta_decode.py` is **not** changed (C-002).
- Fragment written; ruff / format / mypy clean; no `noqa` / `type: ignore`.

## Context & Constraints

- Spec: `kitty-specs/quick-win-remediation-01M72855/spec.md` (User Story 6, FR-013, FR-015, C-002).
- Plan: `plan.md` IC-07. Research: `research.md` "#7445". Decision `01M72871WDH3GYMFKTAHRZFJ14`.
- **Where the BOM is lost**: not in `kernel/meta_decode.py:76-79` as the issue suggests. `load_meta` (`src/specify_cli/mission_metadata.py:336`) and `parse_meta_file` (`:459`) default `encoding=_UTF8`; `_parse_meta_text` reads the file as text with that encoding and passes a `str` (still starting with U+FEFF) to the L1 decoder, whose `json.loads` rejects it. Changing the two defaults to `_UTF8_SIG` (defined at `:46`) fixes it; `utf-8-sig` decodes a file without a BOM exactly like `utf-8`.
- **Do not touch**: `load_meta_strict` (`:749-770`) — it already passes `_UTF8_SIG if bom_tolerant else _UTF8`; keep `bom_tolerant=False` meaning "reject"; `kernel/meta_decode.py`; any other module.
- **Census gates**: do not add a `load_meta` call site or an inline `json.loads` meta read — `tests/architectural/test_inline_meta_read_gate.py` and `tests/architectural/test_lifted_root_meta_fail_closed_census.py` count them. A test file calling `load_meta` is fine (check the gate's scope if it complains).
- Known residual (documented follow-up, do not fix): `coordination/planning_commit.py`, `git/ref_advance.py`, `cli/commands/agent/mission_finalize.py` and the charter activation readers still reject a BOM'd `meta.json`; a read-modify-write through `write_meta` drops the BOM.
- No `make test-fast`, no `make test-full`, no bare directories.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`. Start with:
> `spec-kitty agent action implement WP03 --agent opencode --mission quick-win-remediation-01M72855`

## Subtasks & Detailed Guidance

### Subtask T014 – Red-first BOM tests

- **Purpose**: pin the reported symptom through the canonical reader and one real caller.
- **Steps**:
  1. In `tests/specify_cli/test_mission_metadata.py` (`unit, fast`), in the "Contract (a)" section next to `test_contract_a_non_utf8_bytes_raise_malformed_value_error` (`:106`), add tests that write `json.dumps(_valid_meta(), ensure_ascii=False)` with `encoding="utf-8-sig"` (this prepends the BOM; the file already does this at `:152`) and assert:
     - `load_meta(tmp_path) == meta`
     - `load_meta(tmp_path, on_malformed="none") == meta` (the invisibility symptom)
     - `parse_meta_file(tmp_path / META_FILENAME) == meta`
     - same-fixture control: the same `meta` written **without** a BOM (`encoding="utf-8"`) returns the identical mapping from all three calls.
  2. One symptom-level test through a real caller: `from specify_cli.status.emit import _load_mission_id` and assert it returns `meta["mission_id"]` for the BOM-prefixed file (base: `None`). Make sure `_valid_meta()` contains a `mission_id` (check its definition near the top of the file; if it does not, build the dict inline with a 26-char ULID-shaped id).
  3. Keep `test_contract_b_bom_intolerant_when_disabled` (`:159`) untouched — it is the negative control proving tolerance is not unconditional.
  4. Run on the base (expect the new tests red), record the count with `spec-kitty agent tasks add-history WP03 --note "T014 red: N failed"`, commit the tests alone: `test(meta): pin BOM-prefixed meta.json loading (#7445)`.
- **Files**: `tests/specify_cli/test_mission_metadata.py`.

### Subtask T015 – Change the two defaults; refresh stale wording

- **Steps**:
  1. `src/specify_cli/mission_metadata.py`: `load_meta(..., encoding: str = _UTF8_SIG)` (`:341`) and `parse_meta_file(..., encoding: str = _UTF8_SIG)` (`:463`).
  2. Update the docstrings/comments that now read wrong:
     - `_UTF8_SIG` comment (`:46`, "BOM-tolerant decode preserved from contract (b)") → say it is the default decode of the canonical readers (#7445).
     - `load_meta` docstring "Strict (b)" bullet (`:351-354`): drop "Combine with `encoding="utf-8-sig"` for the BOM-tolerant decode…" (it is now the default); and the `encoding` arg line (`:367`) → "Decode encoding (default `utf-8-sig`: a UTF-8 BOM is tolerated). Pass `"utf-8"` to reject a BOM."
     - `parse_meta_file` `encoding` arg line (`:478`) similarly.
  3. Run T014's tests → green; run the whole test file and `tests/tasks/test_tasks_support.py` (its `test_bom_encoded_meta_returns_dict` at `:358` covers the adapter — must stay green).
  4. Commit: `fix(meta): load_meta and parse_meta_file accept a UTF-8 BOM (#7445)`.

### Subtask T016 – Fragment, validation, tracer

- **Steps**:
  1. `docs/changelog/unreleased/7445-load-meta-accepts-bom.fixed.md` — one bullet per `docs/changelog/unreleased/README.md`: **Before:** a `meta.json` saved with a UTF-8 byte-order mark made the Mission invisible to status commands or failed with "Malformed JSON". **After:** it loads like the same file without one (#7445). Keep it user-facing.
  2. `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
  3. Run the Test Strategy commands; record commands + counts via `add-history`.
  4. Tracer: one `design-decisions` entry (Option A, defaults only, kernel untouched) via `spec-kitty agent tracer-append --mission quick-win-remediation-01M72855 --category design-decisions --actor "<agent:model:profile>" --entry "**[YYYY-MM-DD][implement] ...**"`; a `tooling-friction` entry if anything slowed you down.
  5. Commit: `docs(changelog): fragment for #7445`.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/specify_cli/test_mission_metadata.py tests/tasks/test_tasks_support.py tests/kernel/test_meta_decode.py
.venv/bin/python -m pytest -q tests/architectural/test_meta_decode_l1.py tests/architectural/test_inline_meta_read_gate.py \
  tests/architectural/test_lifted_root_meta_fail_closed_census.py tests/architectural/test_meta_decoder_comparator_singletons.py \
  tests/architectural/test_no_legacy_terminology.py
ruff check src/specify_cli/mission_metadata.py tests/specify_cli/test_mission_metadata.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/mission_metadata.py tests/specify_cli/test_mission_metadata.py
uv run --frozen mypy src/specify_cli/mission_metadata.py
```

Baseline (base `9518fb7154`): the glossary + meta test subset was 215 passed, 1 skipped.

## Risks & Mitigations

- `load_meta` has 150+ callers; the change only widens what they accept (a BOM file now parses) — no caller's accepted set shrinks.
- Two BOM policies remain in the codebase (canonical loader tolerant, L1/planning-commit strict) — documented residual; do not expand scope.

## Review Guidance

- Red on the base / green on the tip for the T014 tests; the negative control at `:159` unchanged and green.
- Diff touches only the two defaults and the stale wording in `mission_metadata.py`; `kernel/meta_decode.py` untouched.
- Census gates green (no new `load_meta` / `json.loads` site in `src/`).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
