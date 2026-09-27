---
work_package_id: WP04
title: Merge → CLI-command-layer rule and driver-body relocation (#5119)
dependencies:
- WP02
- WP03
requirement_refs:
- C-001
- C-002
- C-008
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-006
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: 4c56cebf719c58e58a2cf122ab4b4b32786957b9
created_at: '2026-09-26T17:41:50.084413+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 2 - Merge seam relocation
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- src/specify_cli/merge/drivers.py
- tests/merge/test_merge_drivers.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/drivers.py
- src/specify_cli/merge/git_probes.py
- src/specify_cli/cli/commands/merge_driver.py
- src/specify_cli/merge/executor.py
- src/specify_cli/lanes/merge.py
- src/specify_cli/acceptance/matrix.py
- src/specify_cli/upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py
- tests/architectural/test_layer_rules.py
- tests/architectural/test_inline_meta_read_gate.py
- tests/architectural/test_merge_reconciliation_class_guard.py
- tests/architectural/test_issue_matrix_json_migration_completeness.py
- tests/merge/test_merge_drivers.py
- tests/merge/test_squash_reconcilers_2709.py
- tests/merge/test_gate_artifact_merge_drivers_2804.py
- tests/merge/test_merge_driver_meta_diagnosability.py
- tests/merge/test_traces_driver_section_union_4894.py
- tests/merge/test_merge_driver_wrappers_2709.py
- tests/merge/test_bookkeeping_projection_seam.py
- tests/specify_cli/cli/commands/test_row_aware_merge_driver.py
- tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py
- tests/specify_cli/acceptance/test_matrix_marker_reject.py
- tests/acceptance/test_issue_3231_scaffold_pending_poisons_acceptance.py
- tests/terminus/test_repro_5038.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Merge → CLI-command-layer rule and driver-body relocation (#5119)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (read `packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` — Governing Principles (single canonical authority, architectural alignment) and standing orders 4–5 (red-first; non-vacuous gates).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Issue **#5119** (NOTE part — placement). Today `merge/git_probes.py:667` does a function-local `from specify_cli.cli.commands import merge_driver` so the merge integrity gate's in-process driver replay can call merge-driver logic living in the CLI command layer. Fix the placement: the file-level body of **all six** registered merge drivers moves into the merge domain, and both callers (git's subprocess entrypoint and the in-process replay) execute the **same** body.

Done when:

1. **Rule, red-first** (FR-005, C-006): `tests/architectural/test_layer_rules.py` has a `TestMergeCliBoundary` that fails when any `specify_cli/merge/**` module imports `specify_cli.cli` / `specify_cli.cli.*` other than `specify_cli.cli.console` — in module-level, function-local, relative, submodule (`from specify_cli.cli import commands`) and literal-string dynamic (`importlib.import_module`/`__import__`/`find_spec`) forms. It was committed RED **before** the move, naming exactly `specify_cli/merge/git_probes.py:667`, and is GREEN after.
2. `src/specify_cli/merge/drivers.py` holds six driver bodies + `MergeDriverError` + `MergeDriverOutcome` + `MERGE_DRIVER_BODIES` per `contracts/merge-driver-body.md` (FR-002).
3. `src/specify_cli/cli/commands/merge_driver.py` is a thin shell: same module path, same six public function names and Typer signatures; each only calls its body, echoes a `MergeDriverError` to stderr + `typer.Exit(1)`, echoes `outcome.notice` to stdout (FR-003, C-001).
4. `git_probes._resolve_registered_driver_callable` resolves from `MERGE_DRIVER_BODIES` (function-local import); no merge module imports `specify_cli.cli.commands` (FR-004, SC-001).
5. WP03's goldens pass **unchanged**: `git diff <WP-base> -- tests/merge/merge_driver_goldens/ tests/merge/test_merge_driver_goldens.py` is empty (NFR-001, SC-006).
6. Completeness: `MERGE_DRIVER_BODIES` keys == commands derived from `lanes.merge._MERGE_DRIVERS` == the `merge-driver-*` keys of `cli/commands/__init__.py::_COMMAND_REGISTRARS` (6).
7. Every moved/new branch is exercised by focused tests (diff-cover ≥90% on `drivers.py`); every function ≤ complexity 15; ruff, ruff format, mypy clean; full `tests/architectural/` green (modulo classified pre-existing reds).

Requirement refs: **FR-002, FR-003, FR-004, FR-005, C-001, C-002, C-008**, NFR-001, NFR-006.

- **No manual global-state mutation in new/changed tests** (the census gate is not in this lane until consolidation): no hand writes to `os.environ` / cwd / `sys.path` / `sys.modules` / `sys.argv` — use `monkeypatch.*` / `contextlib.chdir` / `mock.patch.*`. Verify zero sites for your changed test files: `.venv/bin/python kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research/global_state_scan_prototype.py | grep -E '<your test files>'` (expect no output) — record it in the Activity Log.

## Context & Constraints

- Spec: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` (User Story 1, FR-002..FR-005, C-001, C-002, C-008, Edge Cases pin list).
- Research: `research.md` **R2** (per-driver facts), **R3** (rule design), **R4** (pin/importer inventory), **R5** (goldens). Contract: `contracts/merge-driver-body.md`. Probe: `research/merge_cli_rule_probe.py` (reproduces the RED finding).
- **C-002 approved exception (operator scoping decision 2026-09-26)**: `tests/architectural/test_inline_meta_read_gate.py` is owned by in-flight ratchet mission `01M3EW3Z` (its WP13). This WP is authorised to re-pin **only** the single merge-driver path pin in that file (~L1115-1119). No other edit to that file. Whichever mission lands second rebases.
- Other ratchet-owned files are **off-limits**: `_baselines.yaml`, `test_ratchet_baselines.py`, `test_ratchet_positional_anchor_ban.py`, `_ratchet_keys.py`, `_destructive_op_census.py`, `test_destructive_op_routing.py`. So: **no** `_baselines.yaml` row for the console ledger (C-007 deferral) — the named ledger + stale guard is the shrink-only mechanism.
- **Census pin**: `test_destructive_op_routing.py:172` keys `git_probes.py:236:reset_hard` by line. Make **no edit at or above line 236** of `git_probes.py`; all edits here are ≥ L600 (resolver, docstring, comment).
- **Never edit** `src/specify_cli/merge/__init__.py` or `src/specify_cli/cli/commands/__init__.py` (the `__init__` rule forces a version bump; the command registrar and lazy-import tests rely on them unchanged).
- **Scope (C-008)**: merge domain only. The same upward leak exists in `status/doctor.py` → `cli.commands.review` and `tasks/` → `cli.commands`; do not fix them — list them in the Activity Log as follow-up.
- WP02 (dependency) removed the bookkeeping blob-reader copy; WP03 (dependency) added the goldens. Rebase/start from a base containing both.
- Hand-off from WP02: fix the stale `git_probes.py` docstring (~L609) of `_read_git_blob_bytes` that still refers to the deleted `bookkeeping_projection._git_show_blob_bytes` copy — done in T018.

## Branch Strategy

- **Strategy**: lane-based execution from `lanes.json`.
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- Prepare the workspace ONLY via `.venv/bin/spec-kitty agent action implement WP04 --agent claude` (dependencies WP02 + WP03 must be approved first). Work inside the printed lane worktree.
- **Commit order is part of the deliverable**: (1) T014+T015 rule commit — RED; (2) the move (T016–T018) — rule turns GREEN; (3) T019–T020; (4) T021 verification fixes. Never squash the RED commit into the move.

## Subtasks & Detailed Guidance

### Subtask T014 – Site-level import collector (one collector, more forms)

- **Purpose**: The existing collector cannot see the forms the new rule must catch; extend it once so every boundary test benefits (single authority, C-007).
- **Facts** (`tests/architectural/test_layer_rules.py`): `_collect_specify_cli_imports(root)` (L219-248) walks `ast.walk` (so function-local imports ARE seen) but: handles `ImportFrom` only when `node.level == 0` (relative imports invisible); expands `from X import sub` into submodules only for the bare `specify_cli` root (so `from specify_cli.cli import commands` yields just `specify_cli.cli`); ignores `importlib.import_module("…")` / `__import__("…")` / `importlib.util.find_spec("…")`. Consumers: `TestRuntimeBoundary` (L405-415), `TestMissionRuntimeBoundary` (L605+), `TestRuntimeSpecifyCliLedger` (L681+, incl. the form-bypass parametrization L693-745).
- **Steps**:
  1. Add `_collect_specify_cli_import_sites(root) -> list[ImportSite]` where `ImportSite` is a frozen dataclass `(rel: str, lineno: int, qualname: str, module: str)`. Compute the enclosing qualname with a small parent-map walk (or reuse `specify_cli.contracts.anchoring` helpers if they fit — check `_build_qualname_map`).
  2. Resolve **relative** imports from the file's package: for `rel = "specify_cli/merge/git_probes.py"`, `from ..cli.commands import merge_driver` → `specify_cli.cli.commands`, then expand the imported name if it is a real submodule on disk (`…/merge_driver.py` or package dir) → `specify_cli.cli.commands.merge_driver`.
  3. Generalise submodule expansion to every `from <specify_cli pkg> import <name>`: when `<pkg>/<name>` exists as a module or package on disk (under `_SRC`, so tests can monkeypatch `_SRC`), yield `<pkg>.<name>`; otherwise yield `<pkg>`. Keep the bare-root behavior identical.
  4. Dynamic imports: a `Call` whose func is `importlib.import_module`, `import_module` (imported name), `__import__`, `importlib.util.find_spec` or `find_spec`, with a **string literal first argument** that is a `specify_cli` module → yield it. **Never** match bare strings elsewhere (`src/specify_cli/merge/_constants.py:21` has `getLogger("specify_cli.cli.commands.merge")` — must NOT be reported).
  5. Re-implement `_collect_specify_cli_imports(root)` as the projection `[(s.rel, s.module) for s in sites]` so every existing consumer keeps its exact signature.
  6. Prove no ledger churn: run `TestRuntimeBoundary`, `TestMissionRuntimeBoundary`, `TestRuntimeSpecifyCliLedger` — their allowlists must still match exactly (research verified runtime/mission_runtime have no relative/dynamic specify_cli imports; if a newly visible edge appears, STOP and report rather than widening a ledger).
- **Files**: `tests/architectural/test_layer_rules.py`.
- **Notes**: Keep each helper ≤15 complexity (split relative-resolution, submodule-expansion and dynamic-call detection into separate functions). Fully type-annotated.

### Subtask T015 – `TestMergeCliBoundary` + console ledger + self-mutation (commit RED)

- **Purpose**: FR-005 — the boundary exists and bites *before* the fix.
- **Steps**:
  1. `_MERGE_ROOT = _SRC / "specify_cli" / "merge"`; `_MERGE_CLI_CONSOLE_IMPORTERS: frozenset[str]` = the 7 files importing `specify_cli.cli.console` today: `specify_cli/merge/{done_bookkeeping,ordering,forecast,push_preflight,git_probes,preflight,executor}.py` (re-verify with `grep -rn "specify_cli.cli" src/specify_cli/merge/`).
  2. `class TestMergeCliBoundary` with:
     - `test_merge_does_not_import_cli_command_layer`: offenders = sites under `_MERGE_ROOT` whose module is `specify_cli.cli` or starts with `specify_cli.cli.` and is **not** exactly `specify_cli.cli.console`; dedupe per `(rel, lineno, module-prefix)`; message lists `rel:lineno qualname -> module`. On today's tree it must fail naming `specify_cli/merge/git_probes.py:667` (the collector yields `specify_cli.cli.commands` and `…merge_driver` for that one line — dedupe so the failure names the site once).
     - `test_console_importers_within_ledger`: files importing `specify_cli.cli.console` ⊆ ledger.
     - `test_console_ledger_has_no_stale_entries`: every ledger file still imports it (shrink-only by construction).
     - `test_boundary_catches_every_import_form` (parametrized, the self-mutation): write a temp tree with `specify_cli/merge/probe.py` and `specify_cli/cli/commands/merge_driver.py` stubs (mirror L693-745's `monkeypatch.setattr(sys.modules[__name__], "_SRC", tmp_path)` pattern); forms: module-level and function-local × {`import specify_cli.cli.commands.merge_driver`, `from specify_cli.cli.commands import merge_driver`, `from specify_cli.cli import commands`, `from ..cli.commands import merge_driver`, `importlib.import_module("specify_cli.cli.commands.merge_driver")`, `__import__("specify_cli.cli.commands")`}; each must be reported.
     - Negative controls (must NOT be reported): `from specify_cli.cli.console import console` (only ledger-checked), `logging.getLogger("specify_cli.cli.commands.merge")`.
  3. Run it: the first test is RED naming `git_probes.py:667`; everything else green. Commit **this state** on its own: `test(merge): red merge -> cli.commands boundary rule (#5119)`. Paste the failing assertion into the Activity Log (red-first evidence).
- **Files**: `tests/architectural/test_layer_rules.py`.
- **Notes**: No `_baselines.yaml` row (ratchet-owned; C-007 deferral) — say so in a comment next to the ledger.

### Subtask T016 – Create `src/specify_cli/merge/drivers.py`

- **Purpose**: FR-002 — one owner for merge-driver logic and output format.
- **Steps** (a behavior-preserving move; review with `git diff --color-moved`):
  1. Move from `cli/commands/merge_driver.py` into `merge/drivers.py`: `MergeDriverPathError` (L104) — now subclassing `MergeDriverError`; `_resolve_merge_driver_paths` (L109); `_blob_meta_error`, `_load_json_object`, `_union_acceptance_history`, `reconcile_meta_payloads`, `_META_JSON_KWARGS`; all trace helpers/regexes (`_TRACE_*`, `_match_trace_fence`, `_split_trace_blocks`, `union_trace_texts`, `_trace_block_key`, `_trace_block_dedup_key`, `_iter_trace_blocks_with_ordinal`, `_index_trace_blocks_by_key`, `_drop_stale_theirs_trace_blocks`); `RowMatrixMergeError` (L566, now subclassing `MergeDriverError`), `_parse_json_document`, conflict-marker constants, `_merge_field`, `_merge_row_fields`, `_reconcile_*`, `_canonicalize_*`, `_issue_row_key`, `reconcile_issue_matrix_documents`, `_row_key_field`, `_reconcile_identity_fields`, `reconcile_acceptance_matrix_documents`; and the file-level logic of each Typer function (L149, L277, L525, L849, L941, L1019).
  2. Add per contract:
     ```python
     class MergeDriverError(Exception): """str(exc) is the exact stderr text."""
     @dataclass(frozen=True)
     class MergeDriverOutcome:
         notice: str | None = None
     MergeDriverBody = Callable[[str, str, str], MergeDriverOutcome]
     def run_event_log_driver(base: str, ours: str, theirs: str) -> MergeDriverOutcome: ...
     # run_meta_driver, run_traces_driver, run_issue_matrix_driver,
     # run_acceptance_matrix_driver, run_review_cycle_driver
     MERGE_DRIVER_BODIES: Mapping[str, MergeDriverBody] = MappingProxyType({
         "merge-driver-event-log": run_event_log_driver, ... })  # 6 keys
     ```
  3. Each body: path hardening first (`_resolve_merge_driver_paths`, raising `MergeDriverPathError`); then the exact reconcile + serialization it does today (event-log delegates to `status.merge_event_log_files`; meta writes `_META_JSON_KWARGS` + `"\n"`; issue-matrix `indent=2, sort_keys=True` + `"\n"`; acceptance-matrix `indent=2` + `"\n"` **without** sort_keys; traces as returned; review-cycle identical→ours else conflict markers `"\n"`-joined + `notice`).
  4. Error translation, byte-identical stderr: wrap exactly the exceptions each Typer function catches today (`EventLogMergeError`, `json.JSONDecodeError`, `AcceptanceMatrixParseError`, `RowMatrixMergeError`) as `raise MergeDriverError(str(exc)) from exc` — **unless** it is already a `MergeDriverError` subclass (re-raise as-is). Do **not** broaden: e.g. traces' `UnicodeDecodeError` propagates today — keep it propagating.
  5. `drivers.py` must not import `typer` or anything under `specify_cli.cli`.
- **Files**: `src/specify_cli/merge/drivers.py` (new).
- **Notes**: `merge_event_log_files` **must** be imported by name at module level in `drivers.py` (`from specify_cli.status import merge_event_log_files`) so the re-targeted `monkeypatch` in `test_merge_driver_wrappers_2709.py` hits it. If a cycle forces a function-local import, the test must instead patch `specify_cli.status.merge_event_log_files` — and in either case assert the stub is actually called. For any other cycle (`specify_cli.merge` ↔ `acceptance`), use a function-local import inside the body and note why. Keep functions ≤15 complexity (the move must not merge functions).

### Subtask T017 – Thin CLI shell

- **Purpose**: FR-003 / C-001 — CLI adapter holds no reconciliation or serialization.
- **Steps**:
  1. Keep `src/specify_cli/cli/commands/merge_driver.py` with the six functions `merge_driver_event_log`, `merge_driver_meta`, `merge_driver_traces`, `merge_driver_issue_matrix`, `merge_driver_acceptance_matrix`, `merge_driver_review_cycle` — identical names, parameters, `typer.Argument(..., metavar=...)` declarations and docstrings' first lines (the registrar at `cli/commands/__init__.py:341-349` binds them by attribute).
  2. One private helper: `_run(body: MergeDriverBody, base: str, ours: str, theirs: str) -> None` → `try: outcome = body(base, ours, theirs) except MergeDriverError as exc: typer.echo(str(exc), err=True); raise typer.Exit(1) from exc`; `if outcome.notice: typer.echo(outcome.notice)`. Exit 0 otherwise.
  3. Decide whether to keep backward-compatible re-exports of the moved pure functions in the CLI module. **Do not** (it would recreate a second import path/authority); instead re-point the importers (T020). `tests/cli/test_lazy_command_module_imports.py` must stay green untouched (module name unchanged).
  4. Remove now-dead imports from the shell.
- **Files**: `src/specify_cli/cli/commands/merge_driver.py`.

### Subtask T018 – Resolver → `MERGE_DRIVER_BODIES`; docstring hand-off from WP02

- **Purpose**: FR-004 — replay and subprocess share one body; the rule turns GREEN.
- **Steps** (`src/specify_cli/merge/git_probes.py`, edits only ≥ L600):
  1. `_resolve_registered_driver_callable` (L657-679): replace the function-local `from specify_cli.cli.commands import merge_driver as _merge_driver_module` with a function-local `from specify_cli.merge.drivers import MERGE_DRIVER_BODIES`; keep the registry lookup + `_DRIVER_COMMAND_PATTERN` match (L602); `driver = MERGE_DRIVER_BODIES.get(match.group(1))`; keep the `GitProbeError` messages; change the return annotation to the body type (`Callable[[str, str, str], MergeDriverOutcome]` — import the type under `TYPE_CHECKING` to keep import time flat). Update its docstring (it names `cli.commands.merge_driver`).
  2. `driver_replay_expected_bytes` (L682-735): keep the fail-closed `except Exception`; fix the comment `(typer.Exit, RowMatrixMergeError, ...)` → `(MergeDriverError, ...)`. Behavior note (benign, record it): replay no longer prints review-cycle's stdout notice — only the CLI shell does.
  3. **WP02 hand-off**: fix `_read_git_blob_bytes`'s docstring (~L609) so it no longer mentions the deleted `bookkeeping_projection` copy (it is now the single reader, reused by `bookkeeping_projection`).
  4. Verify `TestMergeCliBoundary` is GREEN and `test_destructive_op_routing.py` still green (L236 untouched).
- **Files**: `src/specify_cli/merge/git_probes.py`.

### Subtask T019 – Completeness + focused unit tests for `drivers.py`

- **Purpose**: Sonar new-code / diff-cover ≥90% and a structural guard against a 7th driver drifting.
- **Steps** (`tests/merge/test_merge_drivers.py`, markers `unit`/`fast` where no subprocess):
  1. Completeness: `set(MERGE_DRIVER_BODIES)` == `{m.group(1) for spec in _MERGE_DRIVERS if (m := _DRIVER_COMMAND_PATTERN.match(spec.command))}` == `{k for k in _COMMAND_REGISTRARS if k.startswith("merge-driver-")}` (import `_COMMAND_REGISTRARS` from `specify_cli.cli.commands` inside the test — tests may import CLI).
  2. Per body: success path writes expected bytes (tiny inputs; complement, don't duplicate, WP03's goldens); the error-wrapping branch (`EventLogMergeError`/`JSONDecodeError`/`AcceptanceMatrixParseError` → `MergeDriverError` with identical `str`, `__cause__` set); path-injection → `MergeDriverPathError` (a `MergeDriverError`); review-cycle returns `notice` on collision and `None` on identical.
  3. Shell: `CliRunner` over `specify_cli.cli.commands.merge_driver` (or call the Typer app) proving `MergeDriverError` → exit 1 + stderr text, notice → stdout.
  4. Pin the non-broadened catch: `with pytest.raises(UnicodeDecodeError): run_traces_driver(...)` on non-UTF-8 input (it propagates today; the shell must not turn it into exit 1).
  5. `drivers.py` imports no `typer` / `specify_cli.cli` (cheap AST assertion — complements T015 without duplicating it; keep it to `typer` only if T015 already covers `specify_cli.cli`).
- **Files**: `tests/merge/test_merge_drivers.py` (new).

### Subtask T020 – Re-point importers, re-pin the inline-meta gate, docstrings

- **Purpose**: Leave no importer, patch target or pin pointing at moved code; no vacuous checks.
- **Re-point imports of moved pure-logic symbols** to `specify_cli.merge.drivers` (verify each line first):
  - `tests/merge/test_squash_reconcilers_2709.py:~15`, `tests/merge/test_gate_artifact_merge_drivers_2804.py:~46`, `tests/merge/test_merge_driver_meta_diagnosability.py:~25`, `tests/acceptance/test_issue_3231_scaffold_pending_poisons_acceptance.py:~35`, pure-logic symbols in `tests/merge/test_traces_driver_section_union_4894.py:~42` and `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py:~31`, `_load_json_object` in `tests/merge/test_merge_driver_wrappers_2709.py:~22`.
  - **Must fix**: the `monkeypatch` target `merge_driver.merge_event_log_files` at `tests/merge/test_merge_driver_wrappers_2709.py:~85` → patch where the body now looks it up (`specify_cli.merge.drivers.merge_event_log_files` if imported by name there). An unfixed target raises `AttributeError` or, worse, silently patches nothing — assert the patched stub is actually called.
- **Keep** (they test the shell): shell imports in `test_merge_driver_wrappers_2709.py`, `test_traces_driver_section_union_4894.py:~65` (subprocess string), `tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py:~49` (stdout pin ~L475 stays valid), `tests/architectural/test_merge_reconciliation_class_guard.py:~505`, `tests/cli/test_lazy_command_module_imports.py` (untouched).
- **Re-pin (C-002 approved exception)**: `tests/architectural/test_inline_meta_read_gate.py:~1115-1119`: change the `rel_path.endswith("cli/commands/merge_driver.py")` filter to `"merge/drivers.py"` AND add an assertion that `_parse_json_document` exists as a function in `src/specify_cli/merge/drivers.py` (AST lookup) — without it the check is vacuous (an empty list passes). Touch nothing else in that file.
- **Do NOT edit**: `tests/release/coverage_breadth_baseline.json` (dated provenance snapshot); `docs/plans/engineering-notes/coord-splitbrain-rootcause.md` (historical).
- **Docstrings/comments** (text only): `src/specify_cli/upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py:~21-23` (point at `merge/drivers.py::run_review_cycle_driver`; correct the "refuses fail-closed" wording only if it contradicts the golden behavior — conflict markers written, exit 0), `src/specify_cli/lanes/merge.py:~109-112` (comment only; registry `name`/`command` unchanged), `src/specify_cli/merge/executor.py:~2460` (wrong path `merge/merge_driver.py`), `src/specify_cli/acceptance/matrix.py:~193`, test docstrings: `tests/terminus/test_repro_5038.py:~28`, `tests/merge/test_bookkeeping_projection_seam.py:~168`, `tests/merge/test_traces_driver_section_union_4894.py:~4,15,24`, `tests/merge/test_gate_artifact_merge_drivers_2804.py:~5`, `tests/acceptance/test_issue_3231…:~11`, `tests/specify_cli/acceptance/test_matrix_marker_reject.py:~10`, `tests/architectural/test_issue_matrix_json_migration_completeness.py:~111`, `tests/architectural/test_merge_reconciliation_class_guard.py:~277`.
- Final sweep: `grep -rn "cli.commands.merge_driver\|cli/commands/merge_driver" src tests docs --include="*.py"` — every remaining hit must be a legitimate shell reference.

### Subtask T021 – Verification

- **Stack the lane first**: a multi-dependency lane is cut at the mission base, not at a merge of its dependencies. Before verifying, bring in the WP02 and WP03 lane tips (cherry-pick their commits in order WP02, WP03 onto this lane — files are disjoint) so the goldens and the deduped reader are present; record the stacked SHAs.
- **Steps** (record every command + counts in the Activity Log):
  1. Goldens unchanged and green: `git diff <WP base> -- tests/merge/merge_driver_goldens tests/merge/test_merge_driver_goldens.py` empty; `.venv/bin/python -m pytest tests/merge/test_merge_driver_goldens.py -q`.
  2. Merge + driver suites: `.venv/bin/python -m pytest tests/merge tests/specify_cli/cli/commands/test_row_aware_merge_driver.py tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py tests/terminus tests/acceptance tests/specify_cli/acceptance tests/cli/test_lazy_command_module_imports.py -q -n auto --dist loadfile`.
  3. Full architectural (the move changes a scanned directory): `.venv/bin/python -m pytest tests/architectural/ -q -n auto --dist loadfile`. Classify every red against the WP base (CLAUDE.md baseline-red gotcha) before touching it.
  4. `make test-fast`.
  5. Quality: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `.venv/bin/python -m mypy src/specify_cli/merge/drivers.py src/specify_cli/merge/git_probes.py src/specify_cli/cli/commands/merge_driver.py tests/merge/test_merge_drivers.py`, `uv run --frozen ruff check --select C901 src/specify_cli/merge/drivers.py`.
  6. Import cost sanity: `.venv/bin/python -X importtime -c "import specify_cli.cli.commands.merge_driver" 2>&1 | tail -1` before/after (research: ~0.46 s; flag >10% growth).
  7. Coverage of the new module: `.venv/bin/python -m pytest tests/merge -q --cov=specify_cli.merge.drivers --cov-report=term-missing` ≥90%.
  8. Terminology guard: `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
  9. **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`); do not commit them from the lane — the orchestrator commits them in the lifecycle trail.

## Test Strategy

Red-first is mandatory (C-006): the T015 commit must show `TestMergeCliBoundary::test_merge_does_not_import_cli_command_layer` failing on `specify_cli/merge/git_probes.py:667`, and the T018 commit turns it green. Behavior preservation is proven by WP03's goldens (unchanged) plus the existing merge-driver suites. New branches get focused tests in `tests/merge/test_merge_drivers.py` in the same commit that introduces them.

## Risks & Mitigations

- **stderr drift** → wrap with `str(exc)` only; never reformat messages; goldens compare stderr.
- **Broadened catch** (a previously propagating error now exits 1) → wrap only today's caught types; goldens + a traces `UnicodeDecodeError` test pin it.
- **Census pin shift** → no edits at/above `git_probes.py:236`.
- **Collector change widens other ledgers** → T014 step 6; stop and report on any new runtime/mission_runtime edge.
- **Silent patch miss** (`monkeypatch` target) → assert the stub is called.
- **Vacuous re-pin** → qualname-existence assertion in the inline-meta gate.
- **Cycle / import-time regression** → function-local imports; importtime check.
- **Collision with ratchet WP13** on `test_inline_meta_read_gate.py` → keep the edit to the one pin block so the rebase is trivial.

## Review Guidance

- Verify the RED commit exists and precedes the move; the failure names exactly `git_probes.py:667`.
- `git diff --color-moved` shows the reconcilers moved verbatim; the only new logic is the body wrappers, `_run`, error wrapping and the table.
- Contract check against `contracts/merge-driver-body.md` (6 keys, no typer/cli import in `drivers.py`, shell unchanged in names/signatures).
- Goldens diff empty; full `tests/architectural/` run recorded; **mypy** + ruff + format clean; complexity ≤15.
- Only the approved pin changed in `test_inline_meta_read_gate.py`; no ratchet-owned file touched; no `__init__.py` touched.
- Activity Log lists the C-008 follow-ups (`status/doctor.py`, `tasks/`) and the benign review-cycle notice side effect.
- **No CHANGELOG entry**: internal refactor — C-001 holds, no user-facing change, no `__init__.py` touched. Do not reject for a missing CHANGELOG entry.
- Keep the `test_inline_meta_read_gate.py` hunk minimal (one pin block) so a rebase over ratchet WP13 stays trivial.
- **Tracer append** evidence: dated 1–3 sentence entries in the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` for anything non-obvious (the orchestrator commits them in the lifecycle trail).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T16:40:00Z – system – Prompt created. Includes WP02's git_probes docstring hand-off (T018 step 3) and the C-002 approved re-pin of test_inline_meta_read_gate.py.
- 2026-09-26T18:52:00Z – claude – All subtasks (T014-T021) complete. Commits on lane-d: 69efa911c1 (T014+T015, RED naming exactly `specify_cli/merge/git_probes.py:667`), 88276c856b (T016-T018, rule turns GREEN — 19 TestMergeCliBoundary passed), 4fee327f97 (T019+T020 — 19 test_merge_drivers.py tests, 97% coverage on drivers.py; re-pointed every importer), fdf991b19c (T021 fixups). Goldens unchanged (`git diff <RED-commit> -- tests/merge/merge_driver_goldens tests/merge/test_merge_driver_goldens.py` empty; 59/59 green throughout). Full `tests/architectural/`: 2892 passed, 4 skipped, 2 xfailed, 0 failed. mypy --strict / ruff check / ruff format --check clean on every touched file (two pre-existing-debt files, executor.py and git_probes.py, keep unrelated pre-existing unformatted hunks far from any #5119 edit, confirmed already unformatted at the WP02+WP03 base commit). Import cost +6.5% (under the 10% flag threshold). C-008 follow-ups (documented, not fixed — out of scope): the same merge->cli.commands upward-leak shape also exists in `status/doctor.py` -> `cli.commands.review` and `tasks/` -> `cli.commands`. Benign side effect (documented in T018's commit): the in-process driver replay (`git_probes.driver_replay_expected_bytes`) no longer prints the review-cycle driver's stdout collision notice during replay — only the real CLI shell (`cli/commands/merge_driver.py`) echoes it now, since the notice travels through `MergeDriverOutcome.notice` rather than a direct `typer.echo` call inside the body. Two tooling-friction items worth flagging for the mission tracer: (1) `tests/architectural/test_completion_manifest_freshness.py` pins the FULL multi-paragraph docstring of every Typer command as committed shell-completion help text — shortening a moved command's docstring to "just the first line" (which C-001's own wording seemed to permit) silently reds this gate; the two shell docstrings (`merge_driver_traces`, `merge_driver_review_cycle`) were restored byte-identical. (2) two separate line-number census pins in this file's blast radius (`git_probes.py:236:reset_hard` and four `lanes/merge.py` destructive-op entries) were nearly broken by ordinary content-only comment edits that changed line COUNT rather than line content — both were fixed via same-line-count substitutions and are worth a structural note for future WPs touching either file.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP04 --to <status>` to change WP status.
