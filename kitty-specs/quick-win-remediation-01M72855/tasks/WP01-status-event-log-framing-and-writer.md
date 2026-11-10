---
work_package_id: WP01
title: 'Status event log: line framing, writer bytes, session sanitising'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-015
- FR-016
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- C-004
- SC-001
- SC-002
planning_base_branch: fix/quick-win-remediation
merge_target_branch: fix/quick-win-remediation
branch_strategy: Planning artifacts for this mission were generated on fix/quick-win-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/quick-win-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Independent fixes
history:
- at: '2026-11-10T08:19:33Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/store.py
create_intent:
- tests/status/test_store_line_framing.py
- docs/changelog/unreleased/7439-status-log-line-framing.fixed.md
- docs/changelog/unreleased/7440-sanitizer-mixed-session-pair.fixed.md
- docs/changelog/unreleased/7441-status-log-writer-bytes.fixed.md
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/specify_cli/status/store.py
- src/specify_cli/events/sanitizer.py
- tests/status/test_store_line_framing.py
- tests/status/test_store.py
- tests/specify_cli/events/test_sanitizer.py
- docs/changelog/unreleased/7439-status-log-line-framing.fixed.md
- docs/changelog/unreleased/7440-sanitizer-mixed-session-pair.fixed.md
- docs/changelog/unreleased/7441-status-log-writer-bytes.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Status event log: line framing, writer bytes, session sanitising

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

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

Fix three issues in the status event-log store and the event sanitiser, each red-first:

- **#7439** — every text reader in `src/specify_cli/status/store.py` ends a row only at LF, CRLF or a lone CR (never at VT, FF, FS, GS, RS, U+0085, U+2028, U+2029), and a row that breaks a JSON limit (integer > 4300 digits, very deep nesting) surfaces as the reader's documented error type, never as a raw `ValueError` / `RecursionError`. (FR-001, FR-002)
- **#7441** — `serialize_event_line` refuses NaN / ±Infinity with `StoreError` and writes nothing; `append_raw_rows_atomic` writes LF line endings on every OS. (FR-003, FR-004)
- **#7440** — `sanitize_event_for_log` drops both session timestamps and emits no `session_duration_s` when exactly one is naive, instead of raising `TypeError`. (FR-005)
- Every input these functions accept today keeps reading/writing exactly as before (FR-015).

Done means: the new tests fail on the planning base and pass on the WP tip; three `.fixed.md` fragments exist; ruff, ruff format and mypy are clean on touched files with no new `noqa` / `type: ignore`.

## Context & Constraints

- Spec: `kitty-specs/quick-win-remediation-01M72855/spec.md` (User Stories 1–3, FR-001…FR-005, FR-015, C-001, C-003).
- Plan: `kitty-specs/quick-win-remediation-01M72855/plan.md` (IC-01, IC-02, IC-03; WP01 validation commands).
- Research / data model: `research.md` (#7439, #7441, #7440 sections) and `data-model.md` ("Status event log row", "Sanitised event session fields").
- Charter: `.kittify/charter/charter.md` — ATDD-first (test commit before fix commit), smallest viable diff, no full heavy suites.
- **Contract anchors (spec-kitty-events; converge to these, do not change them)**: a line ends at LF, a CR before LF is tolerated; JSON nesting cap 256 / integer cap 4300 digits (decision 16); the byte rule is `json.dumps(record, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"` (`spec_kitty_events/persistence.py` `serialize_record`); the events write service refuses a mixed naive/aware session pair at its request boundary (decision 9) — core's sanitiser *drops* it instead (different layer; note this in the PR, no contract change).
- **Scope fence (C-003)**: only `store.py` readers change for #7439. The same `splitlines()` defect elsewhere (`status/event_log_merge.py:61`, `status/lifecycle_events.py:248,1112`, `coordination/status_service.py:535,540`, `consolidation/bookkeeping_projection.py:238,1232`, `status/migrate_lifecycle_envelope.py:227`) is a follow-up issue — do not touch those files.
- **No change** to blank-line skipping, `strip()`, partition rules, the torn-tail repair (`existing += "\n"`), or any `append_*` public name (`tests/architectural/test_status_unsafe_allowlist.py` pins the `append_*` surface).
- `store.py` is a scoped mypy-debt entry (`tests/architectural/test_mypy_scoped_typing_debt.py`, #6051): your changes must not add new mypy findings.
- Do not run `make test-fast`, `make test-full`, or any bare test directory.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`. Start with:
> `spec-kitty agent action implement WP01 --agent claude --mission quick-win-remediation-01M72855`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tests for row framing and JSON-limit errors (#7439)

- **Purpose**: pin the reported reader behaviour through the real public readers before any fix.
- **Steps**:
  1. Create `tests/status/test_store_line_framing.py` with `pytestmark = [pytest.mark.unit, pytest.mark.fast]` (no git fixture; use `tmp_path` as `feature_dir` and write `status.events.jsonl` directly). Look at `tests/status/test_store.py` for a minimal valid lane-event row shape (e.g. near `test_blank_lines_skipped`, `:471`) and reuse its field set; build rows with `json.dumps(row, ensure_ascii=False)` so the separator characters appear raw in the file.
  2. Parametrise over the eight separators `"\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "` placed inside a string field (`reason`). Two rows per log (the special one plus an ordinary one) so the test proves both are read.
  3. Assert through each public reader: `read_events` (count 2, `reason` intact), `read_event_stream` (transitions count 2), `read_events_from_text(feature_dir, text)` and `read_event_stream_from_text(...)` (git-text path), `read_events_lenient` (count 2), `read_events_raw` (count 2 — this one already passes; keep it as the same-fixture positive control), and `seed_scratch_event_log(scratch_dir, raw_bytes)` followed by `read_events_raw(scratch_dir)` (count 2).
  4. Line-break cases: rows separated by `"\r\n"` and by a lone `"\r"` through `read_events_from_text` / `read_event_stream_from_text` → each row read once (CRLF passes today via `strip()`; lone CR passes today too — they are regression pins).
  5. JSON-limit cases: one row carrying an extra field whose value is a 4301-digit JSON integer (written into the line text directly: `"x": 1` followed by 4300 zeros), and one row with nesting depth 100 000 (`"[" * 100_000 + "]" * 100_000` as a field value written as raw text). Assert: `read_events`, `read_event_stream`, `read_events_from_text`, `read_events_raw` raise `StoreError` whose message starts with `Invalid JSON on line 1`; `read_events_lenient` returns the other rows and skips this one (put a valid row on line 2); `seed_scratch_event_log` raises `ValueError` (its documented type) and not `RecursionError`.
- **Expected red on base**: separator cases fail for every reader except `read_events_raw`; limit cases fail with raw `ValueError`/`RecursionError`. Run the file on the base, record the red count in the WP history (`spec-kitty agent tasks add-history WP01 --note "T001 red: N failed"`), commit the test alone (`test(status): pin event-log row framing and JSON-limit errors (#7439)`).
- **Files**: `tests/status/test_store_line_framing.py` (new).
- **Parallel?**: No.
- **Notes**: deep nesting can be slow to build; 100 000 is what the issue reproduced — if the test takes > 2 s locally use the smallest depth that still raises `RecursionError` on the base (find it by reading CPython's default recursion limit, ~1000 frames; 10 000 is ample).

### Subtask T002 – One shared line splitter + one decode helper in `store.py`

- **Purpose**: one framing rule and one error-mapping rule for every reader in the module.
- **Steps**:
  1. Add a private iterator, e.g. `_jsonl_lines(text: str) -> Iterator[tuple[int, str]]`, yielding `(1-based physical line number, line)` and splitting only on `\r\n`, `\n`, `\r` (in that precedence, so `\r\n` is one break). A compiled pattern such as `re.compile(r"\r\n|\n|\r")` with `split` is fine; keep it module-private. Line numbers must stay identical to today's for LF-only logs.
  2. Add a private decode helper, e.g. `_decode_json_line(line: str) -> object`, that calls `json.loads` and lets the caller map failures. Simplest shape: catch `(ValueError, RecursionError)` in one place and raise a small private exception (or return a sentinel) that each caller maps — choose whatever keeps every caller ≤ complexity 15 and avoids duplicating the `except` tuple. `json.JSONDecodeError` is a `ValueError` subclass, so the tuple covers it.
  3. Wire the five sites (verify line numbers on your checkout; they were correct at `9518fb7154`):
     - `seed_scratch_event_log` (`:383-404`): use the splitter on `raw.decode("utf-8")`; on decode failure raise `ValueError` (documented type; keep the message naming the line).
     - `read_events_raw` (`:544-570`): it already iterates the file in text mode (universal newlines, correct framing); only route its `json.loads` through the helper so limit errors become `StoreError(f"Invalid JSON on line {n}: …")`.
     - `_partition_event_stream_from_text` (`:648-700`): replace `content.splitlines()` with the splitter; route decode through the helper → `StoreError` with the same message shape.
     - `_lenient_lane_event` (`:770-781`): route decode through the helper; any failure → `None` (skip).
     - `read_events_lenient` (`:785-801`): replace `text.splitlines()` with the splitter.
  4. Update the docstrings of the touched readers only where they describe framing or error types (keep them short).
- **Files**: `src/specify_cli/status/store.py`.
- **Parallel?**: No (depends on T001).
- **Notes**: Do **not** switch to LF-only splitting: `read_events` reads through `Path.read_text` (universal newlines), so LF-only would only change the git-text path. A lone CR is a row break in core and not in the Java decoder — accepted, documented divergence (a lone CR cannot appear inside a valid JSON row). Commit: `fix(status): split event-log rows only at line breaks; map JSON limits to StoreError (#7439)`.

### Subtask T003 – Red-first tests for the writer byte rule (#7441)

- **Purpose**: pin NaN refusal, LF writes and byte parity before the fix.
- **Steps** (same new test file, a separate test class/section):
  1. **NaN refusal**: write one valid event with `append_events_atomic` (or `append_raw_rows_atomic` with a valid row), snapshot the file bytes, then call `append_raw_rows_atomic(path, [row_with_evidence_inf])` where `evidence = {"x": float("inf")}`; assert `StoreError` is raised, the message names the event (`wp_id` and/or `event_id`), and the file bytes are unchanged. Repeat for `float("nan")` and `float("-inf")`. Also assert `serialize_event_line(row_with_nan)` raises `StoreError` directly.
  2. **Same-fixture positive control**: the same row with `evidence = {"x": 1.5}` appends and reads back.
  3. **LF temp file (red on Linux)**: monkeypatch `specify_cli.status.store.os.fdopen` with a spy that records its kwargs and delegates to the real `os.fdopen`; append one row; assert the write call received `newline="\n"`. (CPython on Linux never writes CRLF, so the spy is the only red-first proof; this mirrors the plan decision `01M728CXM5W3Q2WAW7VTAFMWJN`.) Make sure you assert on the **write** open, not the `_read_text_without_following_symlinks` read open (`:444`), e.g. by filtering on mode `"w"`.
  4. **Portable byte pin**: after an append, `b"\r\n" not in path.read_bytes()`.
  5. **Parity pin**: for a JSON-native event row, `serialize_event_line(row) + "\n"` equals `spec_kitty_events.persistence.serialize_record(sanitize_event_for_log(row))` — check the exact public name/signature in the installed package first (`.venv/lib/python*/site-packages/spec_kitty_events/persistence.py`, around `:185-196`); if it serialises a different input shape, compare against `json.dumps(sanitized, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"` and cite the events function in a comment. This pin passes on base (ensure_ascii is already default) — it is a ratchet, label it so in the docstring.
- **Expected red on base**: NaN tests (no exception today) and the fdopen spy (no `newline` kwarg). Commit the tests alone: `test(status): pin writer byte rule — non-finite refusal, LF writes (#7441)`.
- **Files**: `tests/status/test_store_line_framing.py`.

### Subtask T004 – Writer fix (#7441)

- **Purpose**: emit only contract bytes.
- **Steps**:
  1. `serialize_event_line` (`:293-300`): `json.dumps(sanitize_event_for_log(event_dict), sort_keys=True, allow_nan=False)`; catch the `ValueError` and raise `StoreError(f"Refusing to write event {ident}: non-finite number (NaN/Infinity) is not valid JSON")` from it, where `ident` is built from `event_dict.get("event_id")` / `event_dict.get("wp_id")` when present. Keep it small (a tiny private helper for `ident` is fine).
  2. `append_raw_rows_atomic` (`:333-381`): `os.fdopen(fd, "w", encoding="utf-8", newline="\n")` (precedent: `src/specify_cli/policy/hook_installer.py:169`). Because `additions` is computed at `:360` **before** `tempfile.mkstemp`, a refusal raises before any temp file exists — confirm by reading, do not restructure.
  3. Check the other caller of `serialize_event_line`: `src/specify_cli/migration/mission_state.py:1575` (`_canonical_line`, used by `doctor mission-state --fix`). It will now raise `StoreError` for a lane row with a non-finite float — fail-closed, rare; do not change that file (not owned); mention it in the #7441 fragment.
- **Files**: `src/specify_cli/status/store.py`.
- **Notes**: Commit: `fix(status): refuse non-finite numbers and write LF event logs on every OS (#7441)`.

### Subtask T005 – Sanitiser mixed naive/aware session pair (#7440)

- **Purpose**: no `TypeError` from the duration subtraction.
- **Steps**:
  1. Red test in `tests/specify_cli/events/test_sanitizer.py` next to the timestamp edge cases (`:184-219`, file is `unit, fast`): (a) naive `session_started_at="2026-01-01T10:00:00"` + aware `session_ended_at="2026-01-01T10:05:00+00:00"` → no exception, neither key present, no `session_duration_s`; (b) the reverse pairing; (c) same-fixture positive control: two naive timestamps → `session_duration_s == 300` (unchanged behaviour); two aware → 300. Run red, commit alone: `test(events): pin mixed naive/aware session pair handling (#7440)`.
  2. Fix in `src/specify_cli/events/sanitizer.py` (`:97-116`): after both parses, if both are not `None` and `(started.tzinfo is None) != (ended.tzinfo is None)`, log one `logger.debug` line in the existing style ("mixed naive/aware session pair — fields removed") and skip the duration. Do **not** normalise naive values to UTC. Update the docstring bullets (`:72-84` and `:140-148`) to say a mixed pair is treated as malformed.
  3. Commit: `fix(events): drop a mixed naive/aware session pair instead of raising (#7440)`.
- **Files**: `src/specify_cli/events/sanitizer.py`, `tests/specify_cli/events/test_sanitizer.py`.
- **Parallel?**: Yes (independent file from T001–T004).
- **Notes**: production callers — `status/store.py` `serialize_event_line` (every status write) and `events/decision_log.py:261` (which today swallows the `TypeError` and loses the decision event). `tests/specify_cli/status/test_store_sanitized.py` covers the store path; run it.

### Subtask T006 – Changelog fragments, validation, tracer

- **Steps**:
  1. Write three fragments in `docs/changelog/unreleased/` following `docs/changelog/unreleased/README.md` (one bullet each, `**Before:** … **After:** …`, cite the issue):
     - `7439-status-log-line-framing.fixed.md` — rows holding U+2028 & co. read as one event; JSON-limit rows refuse with the store error.
     - `7440-sanitizer-mixed-session-pair.fixed.md` — a naive/aware session pair no longer aborts a status write or loses a decision event; both timestamps are dropped.
     - `7441-status-log-writer-bytes.fixed.md` — non-finite numbers refuse with nothing written; LF on Windows (note the one-time CRLF→LF rewrite and that `doctor mission-state --fix` refuses to re-serialise a historical non-finite row).
  2. Run the style checks: `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
  3. Run the targeted tests and gates (Test Strategy below); record exact commands and pass/fail counts with `spec-kitty agent tasks add-history WP01 --note "..."`.
  4. Append tracer entries as things happen (not at the end): `spec-kitty agent tracer-append --mission quick-win-remediation-01M72855 --category <tooling-friction|approach|design-decisions> --actor "<agent:model:profile>" --entry "**[YYYY-MM-DD][implement] Short symptom.** 1-3 sentences."` — at least one design-decisions entry for the splitter/decode-helper shape.
  5. Commit: `docs(changelog): fragments for #7439 #7440 #7441`.

## Test Strategy

Red-first per issue (T001→T002, T003→T004, T005 test→fix). Targeted runs only:

```bash
.venv/bin/python -m pytest -q tests/status/test_store_line_framing.py tests/status/test_store.py \
  tests/specify_cli/status/test_store_sanitized.py tests/specify_cli/events/test_sanitizer.py \
  tests/migration/test_repair_row_parity.py tests/status/test_reducer_recovery_integrity.py \
  tests/status/test_writer_serialization.py tests/audit/test_shape_registry_status_json_parity.py
.venv/bin/python -m pytest -q tests/architectural/test_status_events_writes_gate.py \
  tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_ledger_floor.py \
  tests/architectural/test_mypy_scoped_typing_debt.py tests/architectural/test_untrusted_path_containment.py
ruff check src/specify_cli/status/store.py src/specify_cli/events/sanitizer.py tests/status/test_store_line_framing.py tests/specify_cli/events/test_sanitizer.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/status/store.py src/specify_cli/events/sanitizer.py tests/status/test_store_line_framing.py tests/specify_cli/events/test_sanitizer.py
uv run --frozen mypy src/specify_cli/status/store.py src/specify_cli/events/sanitizer.py
```

Baseline on `9518fb7154`: the existing files above were green (222 passed across the status/roster set). A red you did not cause: classify per CLAUDE.md "baseline-red gotcha" before touching it.

## Risks & Mitigations

- **Git-text paths keep `\r\n`** (`git show` output is not newline-translated) → the splitter treats `\r\n` as one break; T001 step 4 pins it.
- **Lone CR divergence from the Java decoder** → accepted and documented in the #7439 PR note; do not "fix" by going LF-only.
- **Historical NaN rows** still read (`json.loads` accepts `NaN`), but re-serialisation refuses → fragment says so.
- **Complexity ceiling 15** (Ruff C901 / Sonar S3776) → keep the mapping in the helper, not repeated `except` blocks.
- **Overlap**: open PR #7490 does not touch these files.

## Review Guidance

- Red→green: check out the T001 / T003 / T005-test commits alone on the planning base and confirm the new tests fail for the stated reason; confirm green on the WP tip.
- Half-by-half (compound fix #7439): reverting only the splitter must turn the separator cases red; reverting only the decode helper must turn the limit cases red.
- Confirm no other module was edited for #7439 (C-003) and no `append_*` name changed.
- Confirm the fdopen spy asserts the write open, and that a refused append leaves the file byte-identical.
- Confirm ruff, ruff format (`--force-exclude`) and mypy were run on the touched files and are clean.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
