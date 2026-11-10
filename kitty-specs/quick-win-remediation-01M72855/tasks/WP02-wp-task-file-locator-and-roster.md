---
work_package_id: WP02
title: 'WP task-file facts: one locator, list-only roster'
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-015
- FR-016
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-005
- C-007
- SC-002
- SC-003
planning_base_branch: fix/quick-win-remediation
merge_target_branch: fix/quick-win-remediation
branch_strategy: Planning artifacts for this mission were generated on fix/quick-win-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/quick-win-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 1 - Independent fixes
history:
- at: '2026-11-10T08:19:33Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- src/specify_cli/core/wp_task_files.py
- tests/specify_cli/core/test_wp_task_files.py
- docs/changelog/unreleased/7442-subtask-roster-list-only.fixed.md
- docs/changelog/unreleased/7443-wp-task-file-locator.fixed.md
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/specify_cli/core/wp_task_files.py
- src/specify_cli/core/subtask_rows.py
- src/specify_cli/status/emit.py
- src/specify_cli/status/wp_view.py
- tests/specify_cli/core/test_wp_task_files.py
- tests/status/test_dependency_guard.py
- tests/specify_cli/core/test_subtask_rows_snapshot.py
- tests/specify_cli/status/test_reconstruct_wp_view.py
- tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py
- tests/architectural/test_archive_root_byte_identical.py
- docs/changelog/unreleased/7442-subtask-roster-list-only.fixed.md
- docs/changelog/unreleased/7443-wp-task-file-locator.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – WP task-file facts: one locator, list-only roster

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

Two issues on the facts read from a WP's task file, red-first:

- **#7443** — one locator, one case rule, regular files only. The dependency guard (`status/emit.py`), the subtask roster (`core/subtask_rows.py`) and the WP view (`status/wp_view.py`) all locate `tasks/<WP id>…md` through one new core matcher: WP id matched case-insensitively, tail `(?:[-_.]|\.md$)`, `readme.md` excluded case-insensitively (spec-kitty-events R26). A match that is not a regular file makes the gate readers refuse; the read-only view and phase-1 mirror treat it as "no file". (FR-006, FR-007)
- **#7442** — the roster accepts only task ids: `str`, and `int` that is not `bool`. Anything else (mapping, list, float, date/datetime, `None`, `bool`) and an `int` too long to convert (> 4300 digits) refuses with a `SubtaskRosterResolutionError` (typed subclass) naming the WP file, the entry position, its type, and the expected form (`- T001`). The WP view shows an empty authored subtask list for such a WP instead of crashing; `mark-status` refuses for the whole Mission with a message naming the file and the remedy. (FR-008…FR-011) Operator decision 2026-11-10.
- **Mission 058 enablement** — add the dated `_OPERATOR_SANCTIONED_CORRECTIONS` entry so WP05 can repair Mission 058's six WP files (FR-012 / C-005).
- Accepted inputs keep working (FR-015): `WP02-x.md` names, `str` / `int` ids, unambiguous single files.

## Context & Constraints

- Spec: `kitty-specs/quick-win-remediation-01M72855/spec.md` (User Stories 4–5, FR-006…FR-011, FR-015, C-005, C-007).
- Plan: `plan.md` IC-04, IC-05, IC-06; decisions `01M728CRFH19TBCFK799KSKQTR` (locator home), `01M728CV22TSYQXCPBNTY4WH2P` (roster gate/view contract), `01M7286ZAMNZ9S1E0CA4MZNG27` (map-form refusal), `01M7286WQY7NYXCPNDH0S72M7N` (locator rule).
- Data model: `data-model.md` sections "WP task file" and "Subtask roster entry" are the acceptance tables — implement exactly those outcomes.
- **Layer direction (C-007)**: the new module lives in `src/specify_cli/core/` and imports only stdlib + `kernel._safe_re` (the regex wrapper `core/subtask_rows.py` already uses). `core` must not import `status` at module scope (see the lazy-import comment in `authored_subtask_roster`, `subtask_rows.py:~308`). `status/emit.py` and `status/wp_view.py` may import the new core module at module scope (status → core is allowed).
- **`emit.py` scope**: edit only `_match_wp_files` (`:591-607`) and its two call sites — `_declared_dependencies` (`:384`) and `_find_wp_file` (`:618`). Open PR #7490 edits `emit.py` at `:1003-1030` and `:1110-1130`; stay out of those hunks.
- **Out of scope (follow-up)**: the other locators with their own case rules — `core/dependency_graph.py:157`, `task_utils/support.py:607`, `workspace/context.py:600`. Do not touch them.
- **Not changed**: `cli/commands/agent/tasks_mark_status.py` — it already prints `Cannot determine which work package owns the subtasks: {exc}` (`:418-420`) and `owning_wp_from_authored_roster` (`:954`) already catches `SubtaskRosterResolutionError` (advisory). Your error message must therefore carry the remedy itself.
- Tests under `tests/specify_cli/cli/commands/` are out-of-matrix (nightly only, `.github/ci-module-registry.yml`): your local run of `test_mark_status_authored_roster.py` is the only per-PR evidence — record it.
- No `make test-fast`, no `make test-full`, no bare test directories.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`. Start with:
> `spec-kitty agent action implement WP02 --agent claude --mission quick-win-remediation-01M72855`

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first locator tests (#7443)

- **Purpose**: pin the split case rule and the non-regular-file defect through each production reader.
- **Steps**:
  1. `tests/status/test_dependency_guard.py` (`unit, fast`; see the `test_declared_dependencies_*` class at `:308-374` for fixtures): (a) a Mission whose only WP02 file is `tasks/wp02-x.md` declaring `dependencies: [WP01]` → `_declared_dependencies(feature_dir, "WP02")` returns `("WP01",)` (base: `()` — red); same-fixture control: the uppercase twin `WP02-x.md` returns the same. (b) a directory `tasks/WP03-dir.md` as the only match → reading WP03's dependencies raises `TransitionError` naming the path (base: probably `FrontmatterError`/`IsADirectoryError`, or a silent read — record what it does). (c) `WP02-a.md` + `wp02-b.md` → ambiguous `TransitionError` (new outcome, fail-closed). If the claim path is cheap to drive (`tests/specify_cli/core/test_claim_preconditions.py`, `tests/specify_cli/cli/commands/agent/test_status_wp_dependencies.py`), add one test that an attempted `planned → claimed` of a lowercase-named WP with an unfinished dependency is refused — that is the user-visible defect (SC-003).
  2. `tests/specify_cli/core/test_subtask_rows_snapshot.py` (next to `test_missing_wp_file_fails_closed` `:200`, `test_ambiguous_wp_files_fail_closed` `:206`): a directory `tasks/WP03-dir.md` → `authored_subtask_roster` raises `SubtaskRosterResolutionError` mentioning "not a regular file" (base: returns the directory → read error with a different message, or wrong behaviour — pin the new message); `tasks/README.md` and `tasks/readme.md` never match.
  3. `tests/specify_cli/status/test_reconstruct_wp_view.py`: a directory match → the view's authored group is empty (no crash); a lowercase `wp02-x.md` → authored fields are read.
  4. Run on the base, record the red count, commit the tests alone: `test(core): pin one WP task-file rule across dependency guard, roster and view (#7443)`.
- **Files**: the three test files above (+ the optional claim test in `test_dependency_guard.py`).

### Subtask T008 – New `core/wp_task_files.py`

- **Purpose**: the single authority for "which files in `tasks/` belong to this WP".
- **Steps**:
  1. Create `src/specify_cli/core/wp_task_files.py` with a short module docstring (cite #7443 and spec-kitty-events R26) and:
     - `WP_FILE_SEP = r"(?:[-_.]|\.md$)"` (public, so `subtask_rows.authored_roster_owner_map`'s prefix match at `:345` can reuse it instead of its own copy).
     - `match_wp_task_files(feature_dir: Path, wp_id: str) -> list[Path]`: returns every `tasks/*.md` entry whose **name** matches `^<re.escape(wp_id)><WP_FILE_SEP>` case-insensitively, excluding `readme.md` case-insensitively; returns `[]` when `tasks/` does not exist. It does **not** filter non-regular entries — callers decide (a directory match must be visible so the gate can refuse rather than silently report "no file").
     - Optionally a tiny helper `non_regular(matches) -> list[Path]` (`[p for p in matches if not p.is_file()]`) if it removes duplication in callers; `Path.is_file()` follows a symlink to a file and rejects a dangling link and a directory.
     - Sort the result (`sorted(...)`) so error messages are deterministic.
  2. `tests/specify_cli/core/test_wp_task_files.py` (`unit, fast`): exact-id, `WP04.md`, `WP04-slug.md`, `WP04_slug.md`, `WP04.x.md`, not `WP04b.md`, lowercase `wp04-x.md`, mixed `Wp04-x.md`, `README.md` / `readme.md` / `ReadMe.md` excluded, missing `tasks/` → `[]`, a directory match is returned (callers decide). These give Sonar new-code coverage for the module.
- **Files**: `src/specify_cli/core/wp_task_files.py` (new), `tests/specify_cli/core/test_wp_task_files.py` (new).

### Subtask T009 – Rewire the three locators

- **Steps**:
  1. `core/subtask_rows.py` `_locate_wp_file` (`:258-287`): use `match_wp_task_files`; keep the existing missing / ambiguous messages; add: if the single match is not a regular file → `SubtaskRosterResolutionError(f"Cannot resolve subtask roster for {wp_id}: {path.name} is not a regular file")`. Decide and document the order when there are several matches and one is a directory: "ambiguous" is fine (still fail-closed). Replace the module's `_WP_FILE_SEP` with the imported `WP_FILE_SEP` (and drop the "kept in lockstep by convention… out of scope" comment at `:46-50`, which this WP resolves).
  2. `status/emit.py` `_match_wp_files` (`:591-607`): delegate to `match_wp_task_files` (keep the name as a thin delegate so the two call sites and their docstrings stay put, or replace the two call sites — prefer the delegate, smaller diff). In `_declared_dependencies` (`:384-397`), a non-regular single match must raise the same "unresolvable" `TransitionError` path as ambiguity (message: `… {name} is not a regular file`). In `_find_wp_file` (`:618`), a non-regular match collapses to `None` (phase-1 mirror skips quietly, like ambiguity).
  3. `status/wp_view.py` `_locate_wp_metadata` (`:227-262`): use `match_wp_task_files`; `None` when not exactly one regular file. Remove the module's duplicate `_WP_FILE_SEP` (`:61-63`) and its now-unused `re` import if nothing else uses it (check).
  4. Run T007's tests → green. Commit: `fix(core): one case-insensitive, regular-file-only WP task-file locator (#7443)`.
- **Notes**: `tests/architectural/test_no_dead_symbols.py` — `core.subtask_rows` has entries in `tests/architectural/dead_symbol_allowlist.yaml`; do not edit that allowlist (open PR #7490 edits it). The new public names have `src` callers, so no allowlist entry is needed. Run the gate.

### Subtask T010 – Red-first roster tests (#7442)

- **Steps**:
  1. `tests/specify_cli/core/test_subtask_rows_snapshot.py` (near `test_malformed_wp_file_fails_closed` `:218` and `test_authored_subtask_roster_reads_frontmatter` `:314`), parametrised over WP frontmatter `subtasks:` bodies:
     - `- id: T001\n  title: x` (mapping), `- [T001]` (list), `- 1.5` (float), `- 2026-01-01` (YAML date), `- true` (bool), `- null` / `- ~` (None) → `authored_subtask_roster` raises `SubtaskRosterResolutionError`; the message contains the WP file name, the entry position (1-based), and the expected form text (e.g. `as a list of task ids, e.g. - T001`).
     - an integer entry longer than 4300 decimal digits (write it as a hex literal, `0x` + many `f`, so YAML parses an `int` the file can hold; or a plain 4301-digit integer) → `SubtaskRosterResolutionError`, **not** `ValueError` (base: raw `ValueError` escapes — red).
     - Same-fixture positive controls: `- T001` and `- 7` → `["T001", "7"]` (unchanged).
  2. `tests/specify_cli/status/test_reconstruct_wp_view.py`: a WP with a mapping entry → `reconstruct_wp_view(...)` returns, `authored.subtasks == ()`, other authored fields still populated (base: shows the `str()` of the map — red).
  3. `tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py` (FR-011, production path): a Mission with `WP01` (good roster) and `WP02` (mapping entry); running `mark-status T001 --status done` through the real command (follow the CliRunner/invocation pattern in `tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py`) exits 1 with output containing `Cannot determine which work package owns the subtasks`, the WP02 file name and the list-form remedy; nothing is written to the event log. If driving the CLI needs a heavy fixture, the next-best production entry is `authored_roster_owner_map(feature_dir)` raising with the file name — note the choice in the WP history.
  4. **`for_review` gate, production path (FR-008, analysis finding C1)**: add one test that drives the real `for_review` door with a map-shaped WP — either `move-task WP0N --to for_review` through the command (`tasks_move_task.py:~1449` → `tasks_shared._check_unchecked_subtasks` → `authored_subtask_roster`) or the emit transition pipeline (`transition_pipeline.py:~168` → `emit._infer_subtasks_complete`), whichever has the lighter existing fixture (look for existing `for_review` subtask-gate tests, e.g. `tests/specify_cli/cli/commands/agent/test_check_unchecked_subtasks_snapshot_source.py`, and place the test in a file you own, such as `test_mark_status_authored_roster.py` or `test_subtask_rows_snapshot.py`). Assert the transition is refused (non-zero exit / raised error), nothing is appended to the event log, and the surfaced text names the WP file and the list form. Base behaviour: the map is coerced and the gate reports an unmatchable junk id instead — red. Neither door catches `SubtaskRosterResolutionError` today (only `tasks_mark_status.py` does): if the refusal surfaces as a raw traceback, keep the test asserting the error type and message, record "for_review door renders the roster refusal as a traceback" in the WP history as a reviewer-visible finding, and do **not** edit the unowned door files.
  5. Run red, commit alone: `test(core): pin list-only subtask roster entries and the view/mark-status consequences (#7442)`.

### Subtask T011 – One roster-entry rule + typed error

- **Steps**:
  1. In `core/subtask_rows.py` add `class SubtaskRosterEntryError(SubtaskRosterResolutionError)` ("an authored `subtasks:` entry is not a task id").
  2. Rewrite `normalize_authored_subtask_roster` (`:365-374`): for each entry (enumerate from 1) — `bool` → refuse; `int` → `str(raw)` inside `try` (catch `ValueError` from the int-to-str digit limit → refuse); `str` → `strip()` as today; anything else → refuse. Refusal message, e.g. `f"subtasks: entry {pos} is a {type_label} ({preview}); author subtasks: as a list of task ids, e.g. - T001"` — keep `preview` short (`repr(raw)[:60]`), and keep de-dup/order behaviour identical for accepted entries. Keep complexity ≤ 15 (a small `_entry_task_id(raw, pos) -> str` helper is the natural extraction).
  3. `authored_subtask_roster` (`:289-330`): move the `normalize_authored_subtask_roster(metadata.subtasks)` call **inside** the existing `try`, and add an `except SubtaskRosterEntryError as exc: raise SubtaskRosterEntryError(f"Cannot resolve subtask roster for {wp_id}: {wp_file.name}: {exc}") from exc` **before** the generic `except SubtaskRosterResolutionError: raise`. Update its docstring ("coerced to str" → the accepted entry types and the refusal).
  4. `status/wp_view.py` `_authored_group` (`:207-224`): wrap the normalise call; on `SubtaskRosterEntryError` use `subtasks=()`. Update its docstring (it already documents tolerating an unparsable authored source).
  5. `authored_roster_owner_map` (`:329-357`) already prefixes `path.name` when re-raising — verify the final mark-status message reads well (file name, entry, remedy) and is not doubled awkwardly; adjust only the wording inside `subtask_rows.py`.
  6. Run T010 tests → green; re-run T007's. Commit: `fix(core): refuse non-id subtask roster entries with a remedy (#7442)`.
- **Notes**: `WPMetadata.subtasks` is `list[Any]` (`status/wp_metadata.py:268`) — do not change the model (not owned; the gate is the refusal point). Python `bool` is an `int` subclass: test `type(raw) is bool` / `isinstance(raw, bool)` **before** the `int` branch.

### Subtask T012 – Sanctioned archive correction for Mission 058

- **Steps**:
  1. In `tests/architectural/test_archive_root_byte_identical.py`, replace `_OPERATOR_SANCTIONED_CORRECTIONS: frozenset[str] = frozenset()` (`:137`) with a `frozenset({...})` of exactly these six paths, preceded by a dated comment in the style the block above asks for:
     ```
     # 2026-11-10 operator decision on #7442 (mission quick-win-remediation-01M72855):
     # Mission 058's WP files author `subtasks:` as maps (`- id: TNNN / title / status`),
     # which the list-only roster rule now refuses; WP05 rewrites the 28 entries as plain
     # task ids. Remove these entries in a follow-up once the PR is on main.
     ```
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP01-restore-command-templates.md`
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP02-registry-and-generator.md`
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP03-init-hybrid-install.md`
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP04-consumer-migration.md`
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP05-deploy-to-consumers.md`
     - `kitty-specs/058-hybrid-prompt-and-shim-agent-surface/tasks/WP06-tests-and-validation.md`
  2. Change nothing else in that file. Run it (needs a fetched `main` ref: `git fetch origin main` if it reports no merge base). Commit: `test(architectural): sanction the Mission 058 roster correction (#7442)`.
- **Notes**: this is priced debt per charter Standing Order #5 (owner: operator; exit: removal follow-up after merge, named in the PR body).

### Subtask T013 – Fragments, validation, tracer

- **Steps**:
  1. Fragments in `docs/changelog/unreleased/` (format per its `README.md`):
     - `7443-wp-task-file-locator.fixed.md` — a lowercase task file's dependencies are now honoured; a directory named like a task file is refused instead of read.
     - `7442-subtask-roster-list-only.fixed.md` — a `subtasks:` entry that is not a task id now refuses with the WP file and the expected list form instead of silently blocking `for_review` forever; state that `mark-status` refuses for the whole Mission until the file is fixed.
  2. Style checks: `uv run --frozen python -m scripts.docs.check_changelog_style`, `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
  3. Targeted tests + gates (Test Strategy). Note: after T011 Mission 058's rosters refuse until WP05 lands; `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` reads real Missions — run it and record the result. If it goes red **only** because of Mission 058, record that in the WP history as expected-until-WP05 (do not edit 058 here; WP05 owns it).
  4. Tracer entries at the moment they happen (`spec-kitty agent tracer-append --mission quick-win-remediation-01M72855 --category ... --actor ... --entry ...`), at least one design-decisions entry for the typed error / view tolerance.
  5. Commit: `docs(changelog): fragments for #7442 #7443`.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/specify_cli/core/test_wp_task_files.py tests/status/test_dependency_guard.py \
  tests/specify_cli/core/test_subtask_rows_snapshot.py tests/specify_cli/status/test_reconstruct_wp_view.py \
  tests/specify_cli/status/test_wp_metadata.py tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py \
  tests/specify_cli/cli/commands/agent/test_status_wp_dependencies.py tests/specify_cli/core/test_claim_preconditions.py \
  tests/specify_cli/migration/test_dogfood_corpus_backfilled.py
.venv/bin/python -m pytest -q tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_archive_root_byte_identical.py
ruff check <touched src and test files>
uv run --frozen ruff format --check --force-exclude <touched src and test files>
uv run --frozen mypy src/specify_cli/core/wp_task_files.py src/specify_cli/core/subtask_rows.py src/specify_cli/status/emit.py src/specify_cli/status/wp_view.py
```

Also grep for other callers that relied on `str()` coercion before finishing: `grep -rn "normalize_authored_subtask_roster\|authored_subtask_roster" src/` (known: `status/emit.py:~523` lazy import in `_infer_subtasks_complete`, `cli/commands/agent/tasks_shared.py:518`, `tasks_mark_status.py`, `tasks_move_task_executor.py:385`). Each must either catch `SubtaskRosterResolutionError` already or fail closed legibly — read, do not change unowned files; if one would crash with a traceback, record it as a finding in the WP history and tell the reviewer.

## Risks & Mitigations

- **Mission-wide mark-status refusal** — intended (FR-011); the message must carry the remedy.
- **Case-insensitive ambiguity** (`WP02-a.md` + `wp02-b.md`) — refuses; the corpus has no lowercase `wp` task file.
- **Phase-1 mirror** may now find a lowercase file and write `lane` into it — it edits only an existing `lane` key; low risk.
- **Window between WP02 and WP05** — Mission 058 rosters refuse; WP05 follows immediately and both land in one PR (C-005).
- **#7490 rebase** — disjoint `emit.py` hunks.

## Review Guidance

- Red→green per issue (T007 and T010 commits red on the base, green on the tip).
- Half-by-half for #7443: reverting only the case-insensitive flag turns the lowercase tests red; reverting only the regular-file check turns the directory tests red.
- One rule: confirm no second copy of the separator or the case rule remains in `subtask_rows.py`, `emit.py` or `wp_view.py`, and that `core/wp_task_files.py` imports nothing from `status`.
- The sanctioned-correction entry names exactly six paths with the dated comment, and nothing else in the archive gate changed.
- `bool` is refused even though it is an `int`.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
