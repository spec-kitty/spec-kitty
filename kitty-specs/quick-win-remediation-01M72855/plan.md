# Implementation Plan: Quick-win remediation

**Branch**: `kitty/mission-quick-win-remediation-01M72855` (Mission branch; `meta.json` `target_branch` is `fix/quick-win-remediation`, which is pull-requested to `main`) | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/quick-win-remediation-01M72855/spec.md`

## Summary

Seven reported defects, each fixed with the smallest change that converges core on the `spec-kitty-events` rulings, plus a one-off data repair of Mission 058. The work falls into four independent code clusters with disjoint files (status event log store + sanitiser; WP task-file facts; mission metadata loading; glossary conflict listing) and one data-only repair that follows the roster refusal. Every fix is red-first through the pre-existing entry point. Grounding: two read-only research briefs reproduced every defect on `main` @ `9518fb7154` (see [research.md](research.md)).

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; CI also runs newer interpreters)
**Primary Dependencies**: stdlib `json`, `os`, `re` (via `kernel._safe_re` in core), `ruamel.yaml` frontmatter reader (unchanged), `spec_kitty_events` (already a runtime import; used only as a parity reference in a test)
**Storage**: files — `status.events.jsonl` (JSON Lines), WP task files (`tasks/WP##-*.md`, YAML frontmatter), `meta.json`, glossary event log
**Testing**: pytest, red-first per WP (test commit before fix commit); targeted files only (named per WP below); `ruff check`, `ruff format --check --force-exclude`, `mypy` on touched files
**Target Platform**: Linux, macOS, Windows 10+ (the LF fix exists for Windows; proven on Linux by an `os.fdopen` spy + byte pin)
**Project Type**: single project (`src/` + `tests/`)
**Performance Goals**: glossary conflict listing linear in the event count (NFR-001); no other path gets slower (one shared splitter replaces `str.splitlines()` at three sites)
**Constraints**: no `kernel/meta_decode.py` change (C-002); no JSONL splitters outside `status/store.py` (C-003); no version bump (C-004); no wall-clock tests (C-006); core never imports status at module scope (C-007); Mission 058 edited line-wise (C-008); no `noqa`/`type: ignore` additions
**Scale/Scope**: ~8 source files, ~10 test files, 6 data files, 7 changelog fragments, 1 new core module

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | How this plan meets it |
|---|---|---|
| Single canonical authority | PASS | #7443 collapses three WP-file locators into one core matcher; #7442 keeps one roster-entry rule used by both gate and view; #7439 one splitter + one decode helper in `store.py`. |
| Architectural alignment / layer direction | PASS | New locator in `specify_cli/core/` (status → core is the allowed direction); no kernel change. |
| Standing Order #2 (campsite, smallest diff) | PASS | Fixes stay inside the named files; known same-class sites outside them are follow-up issues (listed below), not silent scope growth. |
| Standing Order #3 (tracer files) | PASS | `traces/` seeded at plan time via `spec-kitty agent tracer-append`; implementers append. |
| Standing Order #4 / ATDD-first (C-011) | PASS | Every WP's first commit is the failing test; reviewer checks red on base, green on tip. |
| Standing Order #5 (gate discipline) | PASS with priced exception | One transient `_OPERATOR_SANCTIONED_CORRECTIONS` entry (six paths) — operator-sanctioned 2026-11-10, dated comment citing #7442, owner = operator, exit = follow-up removal after merge, named in the PR body. |
| Standing Order #8 (mission hygiene) | PASS | Issue-matrix rows for all seven issues; reviewer ≠ implementer; owned files never overlap. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | PASS | Named test files and named architectural gate files only. |
| Terminology canon | PASS | "Mission", "work package"; no `feature` wording added. |
| No version numbers in scope | PASS | No `pyproject.toml` or `__init__.py` change. |

Post-design re-check: PASS (no new authority, no new allowlist beyond the priced sanctioned-correction entry).

## Project Structure

### Documentation (this mission)

```
kitty-specs/quick-win-remediation-01M72855/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: decisions, rationale, rejected alternatives
├── data-model.md        # Phase 1: entities, accepted/refused input rules
├── quickstart.md        # Phase 1: how to reproduce and verify each fix
├── traces/              # tracer files (tooling-friction, approach, design-decisions)
└── tasks.md             # /spec-kitty.tasks output
```

No `contracts/`: the Mission adds no interface; it tightens existing error contracts (`meta.json` records `"contracts": "none"` with a rationale).

### Source Code (repository root)

```
src/specify_cli/
├── status/store.py              # #7439 splitter + decode helper; #7441 allow_nan=False, newline="\n"
├── events/sanitizer.py          # #7440 mixed naive/aware pair dropped
├── core/wp_task_files.py        # NEW: one WP task-file matcher (R26 rule)        (#7443)
├── core/subtask_rows.py         # locator delegate; list-only roster entries       (#7443 #7442)
├── status/emit.py               # _match_wp_files → shared matcher (locator only)  (#7443)
├── status/wp_view.py            # shared matcher; tolerate refused roster          (#7443 #7442)
├── mission_metadata.py          # load_meta / parse_meta_file default utf-8-sig    (#7445)
└── cli/commands/glossary.py     # hoist known-id set + add                         (#7463)

tests/
├── status/test_store_line_framing.py                     # NEW (unit, fast)
├── status/test_store.py                                  # regression only if needed
├── specify_cli/events/test_sanitizer.py
├── status/test_dependency_guard.py
├── specify_cli/core/test_subtask_rows_snapshot.py
├── specify_cli/status/test_reconstruct_wp_view.py
├── specify_cli/cli/commands/agent/test_mark_status_authored_roster.py
├── architectural/test_archive_root_byte_identical.py     # sanctioned-correction entry only
├── specify_cli/test_mission_metadata.py
└── agent/cli/commands/test_glossary.py

kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP0[1-6]-*.md   # data repair
docs/changelog/unreleased/74NN-*.fixed.md                                  # one per issue
```

**Structure Decision**: single project; changes stay in the existing modules above plus one new core module.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Editing six archived Mission 058 files | The roster refusal (operator decision) makes those 28 map entries hard errors; the corpus must stay readable | Reading the `id` key from maps keeps two accepted shapes and diverges from R25; leaving 058 broken leaves a refused Mission in the repo |
| Transient archive-gate sanctioned entry | The byte-freeze gate refuses any edit to an archived file | No other sanctioned route exists; the entry is dated, cites #7442, and a follow-up removes it after merge |

## Implementation Concern Map

### IC-01 — Event-log line framing and JSON-limit errors (#7439)

- **Purpose**: every `store.py` text reader ends a row only at LF / CRLF / lone CR, and JSON-limit failures surface as the documented error.
- **Relevant requirements**: FR-001, FR-002, FR-015
- **Affected surfaces**: `src/specify_cli/status/store.py` — `seed_scratch_event_log` (`:397`), `read_events_raw` (`:563`), `_partition_event_stream_from_text` (`:670-676`), `_lenient_lane_event` (`:770-776`), `read_events_lenient` (`:800`)
- **Design**: one private line iterator `(line_number, line)` splitting on `\r\n`, `\n`, `\r` only (1-based physical lines; blank/strip rules unchanged); one private decode helper catching `(ValueError, RecursionError)` — `JSONDecodeError` is a `ValueError` — each caller maps it to its documented type: `StoreError(f"Invalid JSON on line {n}: …")` for strict readers, skip for lenient, `ValueError` for seeding.
- **Sequencing/depends-on**: none
- **Risks**: lone-CR divergence from the Java decoder (accepted, documented); git-text paths are not newline-translated, so the iterator handles `\r\n` itself. Callers: `read_status_stream` (status read door), `materialize_snapshot`, consolidation bookkeeping, `status_service`, preflight advisory — all widen only.

### IC-02 — Writer byte rule (#7441)

- **Purpose**: the writer emits only contract bytes.
- **Relevant requirements**: FR-003, FR-004, FR-015
- **Affected surfaces**: `store.py` `serialize_event_line` (`:293-300`), `append_raw_rows_atomic` (`:333-374`)
- **Design**: `json.dumps(..., sort_keys=True, allow_nan=False)`; translate the `ValueError` into `StoreError` naming `wp_id`/`event_id` when present. Additions are computed before `mkstemp`, so a refusal writes nothing. Open the temp file with `newline="\n"` (precedent `policy/hook_installer.py:169`).
- **Sequencing/depends-on**: IC-01 (same file; same WP)
- **Risks**: a historical NaN row now refuses on `doctor mission-state --fix` re-serialisation (changelog says so); Windows one-time CRLF→LF rewrite.

### IC-03 — Sanitiser mixed session pair (#7440)

- **Purpose**: no `TypeError` from the session-duration subtraction.
- **Relevant requirements**: FR-005, FR-015
- **Affected surfaces**: `src/specify_cli/events/sanitizer.py:97-116` and its docstring bullets (`:77`, `:140-144`)
- **Design**: when exactly one of the two parsed datetimes is naive, treat the pair as unparseable: drop both keys, no `session_duration_s`, `logger.debug` in the existing style. No UTC normalisation.
- **Sequencing/depends-on**: none (grouped with IC-01/02 in one WP: same writer path, tiny)
- **Risks**: parity note — the events write service refuses the pair at its request boundary (decision 9); core's sanitiser drops it. Different layers; record in PR.

### IC-04 — One WP task-file locator (#7443)

- **Purpose**: one case rule, regular files only, for the dependency guard, the roster and the WP view.
- **Relevant requirements**: FR-006, FR-007, FR-015
- **Affected surfaces**: NEW `src/specify_cli/core/wp_task_files.py`; `core/subtask_rows.py` (`_WP_FILE_SEP` `:50`, `_locate_wp_file` `:258-287`, the owner-map prefix match `:345`); `status/emit.py` (`_match_wp_files` `:591-607` and its callers `:384`, `:618` only); `status/wp_view.py` (`_WP_FILE_SEP` `:63`, `_locate_wp_metadata` `:227-250`)
- **Design**: public `match_wp_task_files(feature_dir, wp_id) -> list[Path]` returning every name match (`^<wp_id>(?:[-_.]|\.md$)`, case-insensitive, `readme.md` excluded case-insensitively). Callers fail closed on any non-regular match (`Path.is_file()` false): roster → `SubtaskRosterResolutionError("… is not a regular file")`; dependency read → unresolvable `TransitionError` (same path as ambiguous); phase-1 mirror `_find_wp_file` and the view collapse to `None`.
- **Sequencing/depends-on**: none
- **Risks**: `WP02-a.md` + `wp02-b.md` becomes ambiguous (correct; none in corpus). The phase-1 mirror may now find a lowercase file. `emit.py` shares the file (different hunks) with open PR #7490 — whichever lands second rebases. Dead-symbol gate: the new public matcher has three `src` callers; removing `_WP_FILE_SEP` from `wp_view.py` must leave no dangling reference.

### IC-05 — List-only subtask roster (#7442)

- **Purpose**: refuse non-id roster entries with a remedy instead of coercing them.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-011, FR-015
- **Affected surfaces**: `core/subtask_rows.py` (`normalize_authored_subtask_roster` `:365-374`, `authored_subtask_roster` `:289-330`); `status/wp_view.py` (`_authored_group` `:207-224`); test of mark-status refusal (`cli/commands/agent/tasks_mark_status.py:418-420` already prints the error text; no source change there)
- **Design**: accept `str` and `int` where `type(x) is not bool`; convert inside the guard so a >4300-digit int's `ValueError` becomes the typed error; any other type raises a `SubtaskRosterResolutionError` subclass naming entry position, type and the expected form (`- T001`). `authored_subtask_roster` moves the normalise call inside its `try` and re-raises with the WP file name. `_authored_group` catches the typed error and returns empty `subtasks`.
- **Sequencing/depends-on**: IC-04 (same files; same WP)
- **Risks**: Mission-wide `mark-status` refusal for any Mission holding a map entry (stated in spec, FR-011). Corpus reader `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` reads real Missions: run it in the roster WP and again after IC-06.

### IC-06 — Mission 058 roster repair + sanctioned archive correction (#7442)

- **Purpose**: keep the in-repo corpus readable under the stricter rule.
- **Relevant requirements**: FR-012, NFR-005, C-005, C-008
- **Affected surfaces**: `tests/architectural/test_archive_root_byte_identical.py` (`_OPERATOR_SANCTIONED_CORRECTIONS` `:137`, code WP); `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP01-restore-command-templates.md`, `WP02-registry-and-generator.md`, `WP03-init-hybrid-install.md`, `WP04-consumer-migration.md`, `WP05-deploy-to-consumers.md`, `WP06-tests-and-validation.md` (data WP)
- **Design**: add the six paths to `_OPERATOR_SANCTIONED_CORRECTIONS` with a dated comment (operator decision 2026-11-10, #7442, map-form roster entries the gate cannot match; remove after merge). Rewrite each three-line `- id: TNNN / title / status` entry as `- TNNN`, same order (WP01 T001–T007, WP02 T008–T011, WP03 T012–T015, WP04 T016–T018, WP05 T019–T023, WP06 T024–T028); no other byte changes; line-wise edit.
- **Sequencing/depends-on**: IC-05 (the gate entry lives with the roster WP; the data WP follows it)
- **Risks**: archive gate needs a fetched `main` ref; titles survive in 058's `tasks.md`; `test_dossier_sha_provenance.py` not involved (no SHA repointed).

### IC-07 — BOM-tolerant metadata loading (#7445, Option A)

- **Purpose**: a BOM-prefixed `meta.json` reads like the same file without one.
- **Relevant requirements**: FR-013, FR-015, C-002
- **Affected surfaces**: `src/specify_cli/mission_metadata.py` — `load_meta` default `encoding` (`:341`), `parse_meta_file` default (`:463`), stale docstrings (`load_meta` strict-(b) note, `_UTF8_SIG` comment)
- **Design**: change the two defaults from `_UTF8` to `_UTF8_SIG`; `load_meta_strict(bom_tolerant=False)` keeps passing `_UTF8` (negative control unchanged). No new `json.loads` site (inline-read gate).
- **Sequencing/depends-on**: none
- **Risks**: residual readers that still reject a BOM (`coordination/planning_commit.py`, `git/ref_advance.py`, `cli/commands/agent/mission_finalize.py`, charter activation) — documented follow-up. A read-modify-write drops the BOM.

### IC-08 — Linear glossary conflict listing (#7463)

- **Purpose**: remove the per-resolved-event rescan without changing output.
- **Relevant requirements**: FR-014, NFR-001, FR-015
- **Affected surfaces**: `src/specify_cli/cli/commands/glossary.py` `_extract_conflicts_from_events` (`:264-290`, offending line `:273`)
- **Design**: build `existing_ids` once before the resolved-event pass; `existing_ids.add(cid)` on every append (preserves de-duplication). No change to filters, order, record shape or the existing `# noqa: C901`.
- **Sequencing/depends-on**: none
- **Risks**: hoist-without-add would yield 3 conflicts for 3 repeated resolved events; the characterisation test pins 1.

## Work-package mapping (input to /spec-kitty.tasks)

| WP | Concerns | Kind | Depends on | Model tier |
|---|---|---|---|---|
| WP01 | IC-01, IC-02, IC-03 | code_change | — | Claude (strong) |
| WP02 | IC-04, IC-05, IC-06 gate entry | code_change | — | Claude (strong) |
| WP03 | IC-07 | code_change | — | cheaper tier |
| WP04 | IC-08 | code_change | — | cheaper tier |
| WP05 | IC-06 data repair | planning_artifact | WP02 | cheaper tier |

## Targeted validation (per WP)

- **WP01**: `.venv/bin/python -m pytest -q tests/status/test_store_line_framing.py tests/status/test_store.py tests/specify_cli/status/test_store_sanitized.py tests/specify_cli/events/test_sanitizer.py tests/migration/test_repair_row_parity.py tests/status/test_reducer_recovery_integrity.py tests/status/test_writer_serialization.py tests/audit/test_shape_registry_status_json_parity.py`; gates: `tests/architectural/test_status_events_writes_gate.py tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_ledger_floor.py tests/architectural/test_mypy_scoped_typing_debt.py tests/architectural/test_untrusted_path_containment.py`
- **WP02**: `.venv/bin/python -m pytest -q tests/status/test_dependency_guard.py tests/specify_cli/core/test_subtask_rows_snapshot.py tests/specify_cli/status/test_reconstruct_wp_view.py tests/specify_cli/status/test_wp_metadata.py tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py tests/specify_cli/cli/commands/agent/test_status_wp_dependencies.py tests/specify_cli/core/test_claim_preconditions.py tests/specify_cli/migration/test_dogfood_corpus_backfilled.py`; gates: `tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_archive_root_byte_identical.py`
- **WP03**: `.venv/bin/python -m pytest -q tests/specify_cli/test_mission_metadata.py tests/tasks/test_tasks_support.py tests/kernel/test_meta_decode.py`; gates: `tests/architectural/test_meta_decode_l1.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_lifted_root_meta_fail_closed_census.py tests/architectural/test_meta_decoder_comparator_singletons.py tests/architectural/test_no_legacy_terminology.py`
- **WP04**: `.venv/bin/python -m pytest -q tests/agent/cli/commands/test_glossary.py`
- **WP05**: `.venv/bin/python -m pytest -q tests/architectural/test_archive_root_byte_identical.py tests/specify_cli/migration/test_dogfood_corpus_backfilled.py tests/architectural/test_bare_prose_corpus_ratchet.py`; plus a roster read of all six 058 WPs through `authored_subtask_roster`.
- **All**: `ruff check <files>`, `uv run --frozen ruff format --check --force-exclude <files>`, `mypy <src files>`; changelog style `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

## Follow-ups (to file; out of scope)

- Follow-up: other JSONL `splitlines()` readers — `status/event_log_merge.py:61` (merge driver, first), `status/lifecycle_events.py:248,1112`, `coordination/status_service.py:535,540`, `consolidation/bookkeeping_projection.py:238,1232`, `status/migrate_lifecycle_envelope.py:227`.
- Follow-up: remaining WP-file locators with their own case rules — `core/dependency_graph.py:157`, `task_utils/support.py:607`, `workspace/context.py:600`.
- Follow-up: one BOM policy in the kernel meta decoder (Option B) and the BOM-rejecting readers.
- Follow-up: remove the Mission 058 `_OPERATOR_SANCTIONED_CORRECTIONS` entry once the PR is on `main`.
- Note (no filing): the `spec-kitty-events` R24 divergence can be retired upstream after this lands.
