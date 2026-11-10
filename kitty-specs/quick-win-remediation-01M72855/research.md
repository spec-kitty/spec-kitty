# Research: Quick-win remediation

Phase 0 output. Sources: two read-only grounding briefs (researcher-robbie profile) that reproduced every defect on `main` @ `9518fb7154` without prototyping a fix; the `spec-kitty-events` rulings (`service/command-cli/README.md` "Deliberate divergences from core", `LedgerLineDecoder.java`, `FactValues.java`, `TasksFiles.java`, installed `spec_kitty_events` 11.3.0 `persistence.py`); operator decisions of 2026-11-10 on the issues. Baselines: the targeted status/roster tests (222 passed) and the glossary/meta tests (215 passed, 1 skipped) are green on the base.

No `[NEEDS CLARIFICATION]` remains. Each decision below is also a resolved Decision Moment (ids in spec.md and in the plan decisions below).

## #7439 — line framing and JSON-limit errors

- **Decision**: one private splitter in `status/store.py` ending rows only at LF, CRLF or lone CR, used at `:397`, `:670`, `:800`; one private decode helper catching `(ValueError, RecursionError)` used at `:400`, `:563`, `:675`, `:773`, mapped per caller (strict → `StoreError`, lenient → skip, seeding → `ValueError`).
- **Rationale**: `str.splitlines()` also splits on VT, FF, FS, GS, RS, U+0085, U+2028, U+2029, which RFC 8259 allows unescaped in strings; `json.loads` raises plain `ValueError` (4300-digit limit) and `RecursionError`, which escape the documented `StoreError` contract. Reproduced: `read_events` refuses a valid U+2028 row; `read_events_lenient` drops it silently; all readers leak `ValueError`/`RecursionError`. Converges on the events framing rule and decision 16, and lets the events side retire its R24 divergence.
- **Alternatives considered**: LF-only splitting (rejected: `read_events` reads through universal newlines, so it would only change the git-text path and add a second divergence); fixing every JSONL reader in the repo (rejected for this mission: C-003; follow-up issue).

## #7441 — writer byte rule

- **Decision**: `allow_nan=False` with `ValueError` → `StoreError` naming the event; temp file opened with `newline="\n"`.
- **Rationale**: reproduced `{"evidence": {"x": Infinity, "y": NaN}}` output; on Windows the text-mode temp file rewrites the whole log with CRLF while observers are told LF bytes. With `ensure_ascii` already default, the result equals `spec_kitty_events.persistence.serialize_record`.
- **Alternatives considered**: write bytes (larger diff); a Windows-only CI test (needs `ci-windows.yml` registration; kept as a portable byte pin instead, with an `os.fdopen` spy as the red test).

## #7440 — mixed naive/aware session pair

- **Decision**: drop both session timestamps, emit no duration.
- **Rationale**: the docstring already promises "malformed → removed silently"; reproduced `TypeError` aborts status writes and silently loses decision events (`decision_log.py:261` catches `Exception`).
- **Alternatives considered**: normalise naive to UTC (rejected: invents a timezone). Parity note: the events write service refuses the pair at its request boundary (decision 9); different layer, recorded in the PR.

## #7443 — one WP task-file locator

- **Decision**: new `core/wp_task_files.py` with one public matcher (R26: case-insensitive id, `(?:[-_.]|\.md$)` tail, README excluded case-insensitively), used by the dependency guard, the roster and the WP view; non-regular matches fail closed in the gate readers.
- **Rationale**: reproduced `tasks/wp02-x.md` found by the roster but not the dependency guard, so dependencies read as "none"; a directory `tasks/WP03-dir.md` returned as WP03's file. Core placement respects layer direction (status → core). A new module avoids touching emit's lazy `subtask_rows` import.
- **Alternatives considered**: make only `emit._match_wp_files` case-insensitive (rejected: keeps three copies, the issue asks for one); place the matcher in `subtask_rows.py` (viable, rejected for coupling emit and view to the roster module).

## #7442 — list-only subtask roster

- **Decision**: accept `str` and non-bool `int`; refuse everything else, and over-limit ints, with a typed `SubtaskRosterResolutionError` subclass naming the WP file, entry and expected form; the WP view catches it and shows an empty list; Mission 058 repaired once.
- **Rationale**: operator decision 2026-11-10 (issue comment); events R25 and R29. Reproduced map/bool/float/date coerced via `str()`; a >4300-digit hex int escapes as raw `ValueError` because normalisation runs outside the `try`. Corpus scan: 19,139 entries, 28 maps, all in Mission 058 (six files).
- **Alternatives considered**: read `id` from maps (rejected by the operator; two shapes, diverges from R25); validate only in `authored_subtask_roster` (rejected: two rules); a migration (rejected: in-repo dogfood data, not consumer projects).
- **Consequence recorded in spec**: `mark-status` refuses Mission-wide while any WP holds a refused roster (`tasks_mark_status.py:418-420` surfaces the error text, which carries the remedy).

## #7445 — BOM in meta.json (Option A)

- **Decision**: `load_meta` and `parse_meta_file` default to `utf-8-sig`; `kernel/meta_decode.py` unchanged.
- **Rationale**: operator decision 2026-11-10. The issue's pointer (`meta_decode.py:76-79`) is not where `load_meta` loses the BOM: `_parse_meta_text` reads text with `utf-8` and passes a `str` that `json.loads` rejects. Strictly widening; non-BOM files decode identically.
- **Alternatives considered**: Option B, make the kernel decoder tolerant (one policy, but widens the L1 contract and retires `bom_tolerant`; follow-up).

## #7463 — glossary conflict rescan

- **Decision**: hoist the known-id set above the resolved-event loop and add each appended id.
- **Rationale**: measured quadratic growth (500 → 5.8 ms, 4000 → 553 ms). A bare hoist breaks de-duplication (3 repeated resolved events would give 3, today 1).
- **Alternatives considered**: a wall-clock or ratio performance test (rejected: flakiness policy; timings go in the PR body).

## Plan-phase decisions (resolved Decision Moments)

- WP split: `01M728CKC0DPRXWJFWT641A05Z`
- Topology settlement by size, real dependencies only: `01M728CNY28WDPTR69B6VWQZ00`
- Locator home `core/wp_task_files.py`: `01M728CRFH19TBCFK799KSKQTR`
- Roster gate/view contract: `01M728CV22TSYQXCPBNTY4WH2P`
- Red-first test locations: `01M728CXM5W3Q2WAW7VTAFMWJN`

## Overlap with open PR #7490

PR #7490 touches `status/emit.py` at `:1003-1030` and `:1110-1130` only; this mission edits `_match_wp_files` (`:591-607`) and its callers (`:384`, `:618`). Disjoint hunks; whichever lands second rebases. No other shared file. `tests/architectural/dead_symbol_allowlist.yaml` is edited by #7490; this mission plans no edit to it.

## Supply chain

No dependency is added, upgraded or removed. `DIRECTIVE_051` controls: not applicable.
