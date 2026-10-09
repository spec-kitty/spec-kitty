# Implementation Plan: Every Mission-file writer takes the lock, and the runtime never cuts a log it cannot prove is its own

**Branch**: `issue-5883-mission-writer-followups` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mission-writer-followups-01M4CYWW/spec.md`

## Summary

This Mission finishes what PR #5890 started, in three areas.

1. **Every Mission-file writer goes through one lock door with one key.** `mission_write_lock` is rekeyed onto one pure, git-free key function so that every door and the status transaction resolve the same lock file for a Mission. The `meta.json`, work-package frontmatter and matrix writers then run their read-modify-write inside that door (FR-001..FR-005, FR-020). The architectural gate gains Rule 4 and closes the three documented holes (FR-006, FR-007, FR-008, FR-019).
2. **The runtime never cuts a log it cannot prove is its own.** The legacy `next` path runs the retrospective gate through the engine's existing abort-only `before_run_completed` hook, on every path including the stale-plan fallback, and the speculative capture/rollback/buffer is deleted (FR-009..FR-011).
3. **The planning flow offers every step it enforces, from the canonical template.** `next` reads runtime templates from `packs/built-in/missions` and the software-dev step order gains an analyze step guarded by an injected analysis-currency check (FR-016..FR-018). The shipped software-dev prompts and step definitions are cleaned up (FR-015, FR-022), operator text says "mission" (FR-012..FR-014), and the glossary is made consistent (FR-021).

## Engineering Alignment (confirmed by the operator, 2026-10-08, Decision Moment `01M4D0F447AFXMSGFDJ661P8A2`)

- **Rekey `mission_write_lock`.** The lock key becomes the canonical Mission key, computed once before the lock is entered. On a coordination-routed Mission with a recorded mid8, the canonical key is the coordination directory name (`coord_mission_dir_name`). Otherwise it is the Mission directory name. The status transaction and every door use the same function, so a legacy `060-test` primary directory and its `060-test-<mid8>` coordination surface lock one file.
- **Only the runtime step order moves to the pack.** `mission.yaml`, the per-type `templates/` and the Python modules stay under `src/specify_cli/missions` (#2652's later slices own them). Only the four `mission-runtime.yaml` copies are retired from `src` (C-008).
- **In-flight runs keep their frozen order.** A software-dev run started before the change keeps its frozen step order with no analyze step. Its recorded template path disappears when the `src` copy is retired, so the drift check is skipped (FR-017). The existing implement-time `analysis_report_required` refusal stays the backstop.
- **Operator change: the pack's software-dev prompts and steps are cleaned up in this Mission** (new FR-022, SC-008).
- **Operator change, 2026-10-08: the pack's Mission config must match the one the CLI runs today** (new FR-023, SC-009). Today the CLI reads `src/specify_cli/missions/<type>/{mission.yaml,mission-runtime.yaml}`, while the charter repository reads the pack copies. The pack copies diverge: `agent-profile` keys on runtime steps, `task_types` blocks, documentation `deliverables: docs/output/` vs `docs/`, a plan runtime template that does not load, and feature/mission wording. The running value wins in every case. Wording fixes go to both copies.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml; the existing `specify_cli.status.mission_write` primitive; the runtime engine `src/runtime/next/_internal_runtime/engine.py`
**Storage**: Mission files in git (`meta.json`, `tasks/WP*.md`, `issue-matrix.json`, `acceptance-matrix.json`); runtime run directory (`state.json`, `run.events.jsonl`)
**Testing**: pytest; deterministic cross-thread interleavings with injected pause points (NFR-001); red-first per ADR 2026-07-17-1 (C-006); synthetic offender + near-miss + self-mutation for every gate rule (NFR-004)
**Target Platform**: Linux, macOS, Windows
**Project Type**: single project
**Constraints**: the runtime→specify_cli ledger does not grow (C-001); one lock door (C-002); source prompts only (C-003); only `mission-runtime.yaml` moves (C-008)
**Scale/Scope**: about 40 production modules, 1 new gate rule plus three extended ones, about 15 prompt or step files, 4 glossary surfaces

## Charter Check

- **Single canonical authority.** One lock door, one key function and one runtime template per type; the `src` runtime-template copies are retired. PASS.
- **Architectural alignment.** The runtime gets the analysis-currency check injected by its `specify_cli` caller, and the ledger shrinks from 23 to 22 because both bare `import specify_cli` edges are removed (C-001). PASS.
- **ATDD / red-first.** Every "no-op passable: no" requirement has a reproduction shown failing first; compound requirements are proven part by part (C-006). PASS.
- **Gate discipline.** Empty allowlist; every rule gets a synthetic offender, a near-miss and a self-mutation proof (NFR-004). PASS.
- **Terminology canon.** FR-012..FR-014 and FR-021 are the terminology work itself. PASS.
- **Locality.** The pack cleanup (FR-022) is bounded to software-dev step files and the files they reference. Other Mission types are untouched. PASS.

## Design decisions

### D1 — Canonical Mission lock key (rekey)

`specify_cli.status.mission_write.mission_lock_key(feature_dir) -> str` is pure and git-free. It reads `meta.json` from the given directory: if the Mission is coordination-routed (`coordination_branch` recorded) and a mid8 is recorded, it returns `coord_mission_dir_name(slug, mid8)`. Otherwise it returns `feature_dir.name`.
- `mission_write_lock(feature_dir)` keys on `mission_lock_key(feature_dir)`.
- `mission_write_lock_dir(repo_root, handle)` resolves the directory with the existing read-only resolver and returns `repo_root/kitty-specs/<key>`.
- `BookkeepingTransaction`'s `_mission_specs_dir_name` (in `coordination/legacy_resolution.py`) is routed through the same function (amendment A1/A3 supersede the earlier "only a test" wording).
- The key is computed before the lock is entered and is passed down; it is never resolved inside the lock.

### D2 — Locked meta and frontmatter helpers

- `mission_metadata.locked_update_meta(feature_dir, mutate, *, repo_root=None, timeout=BOUNDED)` takes the lock, re-reads `meta.json`, applies `mutate`, and writes atomically. Every setter in FR-001 and every writer in FR-020 uses it. `set_change_mode`, `clear_coordination_metadata` and `set_purpose_summary` have no production caller and are removed, along with their dead-symbol allowlist entries and tests.
- `frontmatter.locked_update_frontmatter(wp_path, mutate, *, feature_dir, repo_root=None)` does the same for work-package frontmatter. map-requirements and the finalize flush use it.
- The finalize write-scope restore becomes a compare-and-swap: a file is restored only while its bytes still equal what finalize itself wrote.
- The lane mirror is already locked at runtime, through the emit lock or the transaction. It stays as it is, and the gate recognises both regions (D5).

### D3 — Matrix writers

- `scaffold_issue_matrix` runs its existence check and its write under `mission_write_lock`.
- The acceptance-matrix and issue-verdict helpers and the acceptance verdict guard lock through `mission_write_lock`, keyed via D1.
- The FR-005 red test is written first and must show which of the two divergences causes the failure, key or root (research R3).

### D4 — Runtime terminal gate (FR-009..FR-011)

- The legacy `_dn_advance_engine` passes `before_run_completed=retrospective.before_run_completed` to `commit_advance`.
- `engine.next_step` gains the same keyword argument, so the stale-plan and no-plan fallbacks run the gate before anything is appended.
- `_run_retrospective_learning_capture` raises the typed `MissionCompletionBlocked`. The bridge turns it into a decision that reads as a retrospective-gate refusal.
- `_dn_capture_pre_speculative_state`, `_dn_rollback_buffered_run_state`, `_BufferingRuntimeEmitter` and their tests are deleted.
- A run that is already terminal is not re-gated on a later poll, because the engine hook fires only on the transition into terminal.

### D5 — Gate extensions (FR-006..FR-008, FR-019)

- **Rule 1** also flags `open(..., "w")`, `write_text` and `write_bytes` whose target is a status or run log. It scans `src/runtime` with the run-log and run-state names. Every newly seen site is fixed: the consolidation bookkeeping projection rewrites the status log under the status lock; the lane auto-rebase's create-if-missing becomes an exclusive create. The git merge driver's output write is excluded by a stated structural rule (it writes the path git hands it).
- **Rule 2** accepts a callable passed into a lock region only if its parameter is only ever called, never stored, returned or assigned.
- **Rule 3** checks `mission_write_lock`'s first argument as well. It accepts only known Mission-directory-name expressions (`.name` of a directory, `mission_lock_key(...)`, `mission_write_lock_dir(...)`) and reports subscripts, calls and attributes containing "slug".
- **Rule 4** (new) treats these as sinks: `write_meta`, `restore_meta_text`, `write_frontmatter`, `update_fields`, and `write_text`/`write_bytes`/`atomic_write` on `meta.json` or `tasks/WP*.md`. A sink must be inside a lock region, inside a registered locked helper (D2), or inside a status-core lock region. The status-core regions are `BookkeepingTransaction` and the emit lock, recognised structurally.
- Migrations get no exemption. They write through the helpers.

### D6 — Canonical runtime templates (FR-018, NFR-006)

- The built-in tier resolves through `charter.activation.mission_type_profile_repository.builtin_missions_root()`, which `runtime` may already import. The two bare `import specify_cli` edges in `runtime_bridge_io` go away, the `""` ledger entry is removed, and the cap drops to 22.
- The four `src/specify_cli/missions/<type>/mission-runtime.yaml` copies are reconciled into the pack and deleted. The deprecation banner goes.
- **Reconciliation keeps behaviour.**
  - The pack's `plan` template takes the `src` shape, because today the pack copy does not load.
  - An `agent-profile` stays only on a step that already dispatches through composition. Discovery and documentation-accept lose theirs, so routing does not widen.
  - A per-type test asserts that the planned step sequence and the dispatch route of every step equal today's, apart from the software-dev analyze step.
- **Config parity (FR-023).** Each pack `mission.yaml` is made byte-equal to its src copy. The pack-only `task_types` and the documentation `deliverables: docs/output/` are dropped, because the CLI never ran them; the wording fixes are applied to both copies. A parity test over the four types pins `mission.yaml` equality while the src copy exists. Before a pack-only key is dropped, check whether any charter reader of the pack copy (`charter/offering/missions/repository.py`, `charter/activation/*`, `dossier/manifest.py`) consumes it; if one does, stop and raise it as an owner decision rather than dropping it. `pack-manifest.yaml` hashes are refreshed with `spec-kitty doctrine regenerate-graph`.

### D7 — Analyze step (FR-016, FR-017)

- The software-dev runtime template becomes `discovery → specify → plan → tasks → analyze → implement → review → accept`.
- A new `analyze` guard in `_evaluate_software_dev_guards` reads an injected `analysis_currency` fact. That fact is a callable passed as a keyword argument from `next_cmd.decide_next` through `decide_next` into `DecideNextContext`, so the runtime gets it without importing specify_cli. The callable wraps `analysis_report.check_analysis_report_current`.
- The callable is evaluated only when the current step is `analyze`.
- On refusal the step is re-issued with `error_code` set to `ANALYSIS_REPORT_MISSING` or `ANALYSIS_REPORT_STALE`, and `guard_failures` naming each stale input.
- The finalized-board override (`_dn_finalized_board_override`) must not jump past analyze. It gets a red test and a fix if it does (research R6).
- In-flight runs: see Engineering Alignment.

### D8 — Pack software-dev cleanup (FR-015, FR-022)

Concrete list in research R7. All edits are to source files under `packs/built-in/missions`. The provenance ratchet baseline is lowered with its refresh command, `spec-kitty doctrine regenerate-graph` is run after the `step.yaml` and action-index changes, and every pinning test listed in R7 is updated.

### D9 — Terminology and commitlint (FR-012..FR-014)

- All five commit builders say "for mission". The finalize drift check accepts the old and new subjects (FR-013).
- The CLI errors listed in R8 say "mission".
- The FR-014 scan uses `ast` over commit-message arguments and error strings.
- commitlint's planning-subject rule is extended to cover the scaffold, gap-analysis and generator-config subjects for both words. That rule rejects them today.

### D10 — Glossary (FR-021)

- topic branch is added. Mission and Mission Run are rewritten. feature branch becomes an alias of topic branch.
- The changes go to `docs/context/orchestration.md`, the YAML seed, the built-in glossary pack and the generated contextive glossary, which is regenerated.
- The seven inconsistencies listed in R9 are fixed.
- The parity tests and the regenerate-graph check run after the pack edit.

## Project Structure

```
src/specify_cli/status/mission_write.py          # mission_lock_key; mission_write_lock rekeyed (D1)
src/specify_cli/missions/_read_path_resolver.py  # mission_write_lock_dir via the key (D1)
src/specify_cli/mission_metadata.py              # locked_update_meta; setters; dead setters removed (D2)
src/specify_cli/frontmatter.py                   # locked_update_frontmatter (D2)
src/specify_cli/acceptance/__init__.py, acceptance/matrix.py, cli/commands/agent/issue_verdict.py, tasks/issue_matrix.py  # D2/D3
src/specify_cli/cli/commands/agent/tasks_map_requirements.py, mission_finalize*.py      # D2
src/specify_cli/{core/mission_creation_meta.py, tracker/origin.py, cli/commands/mission_type.py, doc_analysis/doc_state.py, consolidation/{phase_teardown,baseline}.py, consolidation/mission_number/bake.py, mission_loader/command.py, migration/*.py, upgrade/*.py}  # FR-020 writers
src/runtime/next/runtime_bridge.py, runtime_bridge_io.py, runtime_bridge_retrospective.py, runtime_bridge_cores.py, runtime_bridge_engine.py, decision.py, _internal_runtime/engine.py  # D4/D6/D7
src/specify_cli/cli/commands/next_cmd.py         # inject analysis currency (D7)
src/specify_cli/missions/*/mission-runtime.yaml  # deleted (D6)
packs/built-in/missions/{software-dev,documentation,research,plan}/mission-runtime.yaml  # reconciled (D6/D7)
packs/built-in/missions/software-dev/**, packs/built-in/missions/mission-steps/software-dev/**  # cleanup (D8)
commitlint.config.cjs; status/uninitialized_hint.py; task_utils/support.py; plan_validation.py; validate_*.py; mission_setup_plan.py; mission_finalize_planning_pin.py; core/mission_creation_commit.py  # D9
docs/context/*.md; .kittify/glossaries/spec_kitty_core.yaml; packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml; src/specify_cli/.contextive/*.yml  # D10
tests/architectural/test_mission_write_discipline.py   # Rules 1-4 (D5)
tests/architectural/test_layer_rules.py, _baselines.yaml  # ledger 23 -> 22 (D6)
```

## Implementation Concern Map

### IC-01 — Canonical lock key and meta.json writers
- **Purpose**: one key for every door; every `meta.json` read-modify-write under it.
- **Relevant requirements**: FR-001, FR-020 (meta families), US1, NFR-002, NFR-003
- **Affected surfaces**: mission_write, _read_path_resolver, mission_metadata, acceptance, the FR-020 writer modules
- **Sequencing/depends-on**: none
- **Risks**: nesting under `ensure_vcs_locked` and the acceptance guard; a subprocess holding the parent's lock waits for the bounded timeout (edge case).

### IC-02 — Frontmatter and matrix writers
- **Purpose**: map-requirements, finalize and the matrix scaffold/helpers locked.
- **Relevant requirements**: FR-002..FR-005, US2, US3
- **Affected surfaces**: tasks_map_requirements, mission_finalize*, issue_matrix, acceptance/matrix, issue_verdict
- **Sequencing/depends-on**: IC-01
- **Risks**: finalize's long in-memory window; the restore must be compare-and-swap.

### IC-03 — Gate Rules 2, 3 and 4
- **Purpose**: close the writer class by construction.
- **Relevant requirements**: FR-006, FR-007, FR-019, NFR-004
- **Affected surfaces**: tests/architectural/test_mission_write_discipline.py
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: false positives on status-core regions; must be structural, not allowlisted.

### IC-04 — Runtime terminal gate and Rule 1
- **Purpose**: the gate runs before completion on every path; the rollback is gone; Rule 1 sees whole-file rewrites and `src/runtime`.
- **Relevant requirements**: FR-008..FR-011, US5
- **Affected surfaces**: runtime_bridge*, engine, consolidation bookkeeping projection, lane auto-rebase, the gate
- **Sequencing/depends-on**: none
- **Risks**: behaviour change: an already-terminal run is not re-gated (accepted, US5-AS6).

### IC-05 — Canonical runtime templates and the analyze step
- **Purpose**: `next` reads the pack, and the analyze step is guarded.
- **Relevant requirements**: FR-016..FR-018, FR-023, NFR-006, SC-009, C-001, C-004, C-008
- **Affected surfaces**: runtime_bridge_io, runtime_bridge_cores, decision, next_cmd, pack mission-runtime.yaml files, layer-rule ledger
- **Sequencing/depends-on**: IC-04 (same runtime files)
- **Risks**: agent-profile routing widening; the finalized-board override skipping analyze; in-flight drift.

### IC-06 — Pack software-dev cleanup
- **Purpose**: prompts and step definitions match the CLI.
- **Relevant requirements**: FR-015, FR-022, SC-008, C-003
- **Affected surfaces**: packs/built-in/missions/software-dev/**, mission-steps/software-dev/**, ratchet baseline, the pinning tests in R7
- **Sequencing/depends-on**: IC-05 (prompts describe the new step)
- **Risks**: shrink-only ratchet tightness; the regenerate-graph check.

### IC-07 — Terminology and glossary
- **Purpose**: "mission" in operator text; one glossary.
- **Relevant requirements**: FR-012..FR-014, FR-021
- **Affected surfaces**: see D9 and D10
- **Sequencing/depends-on**: none
- **Risks**: goldens and fixtures that assert the old subjects.

## Complexity Tracking

None.

## Follow-ups (not in scope)

- Retiring the remaining `src/specify_cli/missions` type directories (`mission.yaml`, `templates/`): #2652 slice 2+, #2661, #4822.
- Serialising two concurrent runtime commits (#5854); git `index.lock` collisions (#5515, #5443).

## Amendments after the post-plan squad (binding; they override D1–D10 where they disagree)

### Lens A: lock key, helpers, matrix, gate

- **A1 (blocker): one key for every lock caller.** The rekey covers every per-Mission lock caller, not only `mission_write_lock`. That means every direct `feature_status_lock(root, X.name)` caller: emit `:977/:1153/:1263`, work_package_lifecycle `:312/:468`, move-task executor, mark-status, agent status, decisions emit, finalize status surface, retrospective lifecycle events and the migrations. Each passes `mission_lock_key(...)`. `BookkeepingTransaction` and `coord_status_lock` call the same function, so there is a single authority. The bare-directory coordination fixture (a `060-test` primary directory and a `060-test-<mid8>` coordination directory) is the fixture for every key test and for a lock-order test. That test runs the lifecycle path and the implement claim path on two threads and must not deadlock.
- **A2 (blocker).** `_holds_mission_lock` and `capture_rollback_point` resolve the key through `mission_lock_key`. A test covers the bare-directory coordination shape.
- **A3.** `mission_lock_key` uses the transaction's mid8 cascade (`resolve_transaction_mid8`: `meta.mid8`, then `mission_id[:8]`, then the slug tail) through one shared helper. An empty mid8 on a coordination-routed Mission makes `mission_lock_key` raise a typed error, and the transaction's trailing-dash key is fixed to use the same function.
- **A4: key stability within a hold.** The key is read from the canonical primary `meta.json` (the read-path resolver), never from a lane worktree's copy. While a thread holds a Mission lock, nested entries for the same Mission reuse the held key from a thread-local, so a writer that changes `coordination_branch` or `mid8` inside the hold never takes a second lock. A test pins this with `flatten_coordination_metadata` inside a hold.
- **A5: Rule 4 regions.** A region is a lexical `with` of a lock context manager, extended to `ExitStack.enter_context(<lock cm>)`, `<lock cm>.__enter__()` up to the matching `__exit__`, a `with <name>` whose name was assigned from a lock context manager, and `locked_acceptance_verdict_guard`.
  - A sink inside function F is accepted when F is a registered locked helper, or when every same-module call site of F sits in a region.
  - A cross-module callee whose call sites cannot all be resolved fails closed.
  - There are no class or function-name exemptions.
- **A6: Rule 3.**
  - Key arguments (`feature_status_lock`) are accepted only as `mission_lock_key(...)`.
  - Path arguments (`mission_write_lock`, `hold_mission_write_lock`) are accepted as a `mission_write_lock_dir(...)` result or a function parameter.
  - A bare `.name` is no longer accepted.
- **A7: Rules 1 and 4, target tracking.**
  - Within a function, names assigned from `EVENTS_FILENAME`, `"status.events.jsonl"`, `"meta.json"`, `META_FILENAME`, `"run.events.jsonl"` or `"state.json"` are tracked through assignments and `/` joins.
  - The sinks are truncate, `write_text`, `write_bytes`, `open(..., "w"/"x"/"r+")`, `shutil.move` onto a target, and a whole-file `os.replace`/`atomic_write` onto a target.
  - Structural non-sinks (amended after the analysis, binding): an append-only `open(..., "a")` (the engine's `_append_event`, `status/store.py`'s canonical append) and the tmp-then-`os.replace` publish of a freshly built snapshot whose content is not derived from re-reading the target (the engine's `_write_snapshot`). Each gets a near-miss test; a replace whose source was read from the target is still a sink.
  - `rebuild_state.py:777` and `migrate_lifecycle_envelope.py:250-272` are dispositioned explicitly: they are locked, or excluded by a stated structural rule.
  - Each variant gets a synthetic offender.
  - The merge-driver exclusion applies to Rule 4 as well.
- **A8: compare-and-swap restore.** Every branch of the finalize write-scope restore, rewrite and unlink alike, plus `restore_meta_text`, runs inside the lock and acts only while the current bytes equal what finalize wrote (or, for an unlink, the file finalize created). Files that changed are reported as kept.
- **A9: red tests that fail today.**
  - FR-005 uses the bare-directory coordination fixture.
  - FR-003's finalize applies its field delta to the freshly read frontmatter and body. Its red test covers a concurrent frontmatter field (a map-requirements ref) and a concurrent body note.
- **A10: FR-020 additions.**
  - New writers: `task_metadata_validation.py:178` and `implement_support.py:491` (`update_fields`).
  - The body of `set_vcs_lock` moves to the locked helper.
  - `tasks.md` becomes a Rule 4 sink.
  - Line numbers are re-derived at implement time (research line numbers are indicative).
- **A11: Rule 2 escapes.** A reference to the parameter other than as the function of a call counts as an escape. That includes passing it as an argument or keyword (`Thread(target=f)`, `submit(f)`, `partial(f)`) and capturing it in a nested def or lambda.
- **A13: matrix verdict guard ownership.** `locked_acceptance_verdict_guard` lives in `acceptance/matrix.py`, so its rekey is done in WP04 with the other matrix helpers.
- **A12: NFR-003 measurement.** Warm the `git_common_dir` cache first, then count the change in subprocess calls. `mission_write_lock_dir` stays off the hot path of a writer that already has `feature_dir`.

### Lens B — runtime, templates, analyze, config parity

- **B1 (blocker, FR-017).** Query mode (`runtime_bridge_query.py:449-450`) loads the run's frozen copy (`run_dir/mission_template_frozen.yaml`), as the ephemeral branch already does. The recorded live path is used only for the drift check. Red test: a persisted run whose recorded `src` template path no longer exists answers a bare `spec-kitty next` without `QueryModeValidationError`.
- **B2 (blocker, FR-017/FR-023/NFR-006): "what runs today" is decided per type, by what actually resolves.**
  - **Documentation and research** resolve from the user-global tier, which `ensure_runtime` overwrites from the pack at startup. So for these two types the pack `mission-runtime.yaml` is already the template that runs, including documentation's accept `agent-profile`. Their pack runtime bytes stay untouched: no wording or comment edits. A byte change would be re-copied to the global tier and would trip the drift check for in-flight runs.
  - **Software-dev and plan** resolve to the `src` copy today. Their pack copy takes the `src` content: no `agent-profile` keys beyond what `src` carries, and the loadable `plan` shape. Software-dev also gains the analyze step.
  - **Tier order is unchanged.**
  - **NFR-006/SC-009 baseline.** The baseline for each type is the template that resolves today, recorded by a test helper that runs the current resolver before the change.
  - **`mission.yaml`.** The CLI pins built-ins to `src` (`mission.py:649-663`), so `src` is what runs and the pack copy becomes byte-equal to it. `task_types` and the documentation `deliverables: docs/output/` have no reader, so dropping them changes no CLI behaviour. Wording fixes land in both copies. The charter compiler embeds the whole pack `mission.yaml` in the compiled `template-set-*.md` (`compiler.py:1992-2005`), so the charter-bundle goldens are regenerated and the change is called out in the PR.
- **B3 (blocker, D7).** `_dn_finalized_board_override` (`runtime_bridge.py:575-629`) and its query-mode twin (`runtime_bridge_query.py:98-123`) check analysis currency for software-dev before they hand out implement. When the report is missing or stale they issue `analyze` with the error code. Red tests cover both paths with a hand-run specify, plan and tasks and a finalized board.
- **B4 (D7): no caller skips the check.**
  - The currency callable is injected inside the shared `next_cmd.decide_next` wrapper, and `orchestrator_api/decision_verbs.py:712` is routed through that wrapper.
  - On the analyze step and in the board override, a missing callable fails closed with `ANALYSIS_CURRENCY_UNAVAILABLE`, never "not evaluated". data-model is amended to match.
- **B5 (D7): plumbing.**
  - The verdict is computed by the bridge only when the step is `analyze`, or when the board override would issue implement. It is stored in the snapshot's `status_facts`, so the cores module stays a pure leaf.
  - Precedence: a prompt-resolution failure's error code wins over the analysis code.
  - Tests assert that `_state_to_action("analyze")` and `_build_prompt_or_error` resolve for the new step, and that `_with_guard_failure_paths` renders the stale-input entries.
- **B6 (D4): refusal type.**
  - `MissionCompletionBlocked` keeps its real shape, `(decision: GateDecision)`.
  - One bridge-level adapter wraps every failure of the hook in one typed refusal on both the legacy and the composition paths: `MissionCompletionBlocked`, the policy error, and an arbitrary capture exception. The adapter is caught before the generic "Runtime engine error" and `_advance_failed_decision` handlers.
  - The hook signature is `Callable[[], None]`. data-model is amended to match.
- **B7 (D4).** A test pins that a terminal re-poll does not re-run the gate. The non-blocking learning capture also fires only on the transition into terminal.
- **B8 (D6).**
  - `PackRootNotFound` from `builtin_missions_root()` fails closed with a named error and is covered by a test.
  - `mission_loader/command.py:224-226` switches to the same accessor, because its `runtime/missions` root does not exist.
  - The `_baselines.yaml:22` justification text is updated.
  - The ten test files that hard-code the `src` runtime path move to the pack path in the same WP. Among them are `tests/next/test_plan_mission_runtime.py`, `tests/contract/test_plan_mission_yaml_validates.py` and `tests/specify_cli/missions/test_mission_template_consistency.py`.

### Lens C — pack cleanup, wording, glossary

- **C1 (blocker): step-contract bootstrap command.** Every built-in step contract declares `--profile` and `--tool` inputs on its bootstrap step, and the executor appends them to `spec-kitty charter context`, which refuses both options. Decision: remove those two inputs from the bootstrap step of every built-in step contract, in all Mission types, because the CLI refuses them for every type. Update `tests/doctrine/mission_step_contracts/test_shipped_contracts.py:61-70` and add a test that renders each contract's bootstrap command and parses it against the Click command. This is the one deliberate exception to the Locality claim; the PR calls it out. Adding the options to `charter context` is not in scope.
- **C2: R7 inventory additions.**
  - In the step contracts: `kitty-specs/{feature}/` (specify:47, plan:49); "Commit … to main branch" (specify:51, plan:53), reworded to the planning branch the CLI reports; "Merge later records done" (review:78, `review/guidelines.md:28`), which becomes consolidate; "Include WP ID in commit scope" (implement:64); and `move-task {wp_id}` with no `--mission` (implement:68, review:75).
  - The software-dev contracts are edited, and so is the C1 bootstrap input in every type.
- **C3: `--mission` boilerplate.** Nine prompts tell the agent to pass `--mission` to every command. They are reworded to "every command that accepts `--mission`", and `test_has_feature_flag_guidance` stays green.
- **C4: more false "next advances" claims.**
  - Fix accept:119 (there is no consolidate step), specify:504 (after tasks, `next` now issues analyze), and review:323 and implement:360 (add `--mission`).
  - "Merge" becomes "consolidate" where that is what is meant (accept:10-12, :77).
  - review:317-318 loses its hosted-sync wording.
- **C5: repo-local residue in implement.**
  - Remove the spec-kitty-repo "authority pointers" (:95-101).
  - The mandatory `.venv/bin/ruff` check becomes "the project's own lint and format commands" (:188-190).
  - `git merge-base HEAD main` uses the mission's target branch (:197).
  - The agent directory list is replaced by a pointer to `spec-kitty agent config list` (:291-295).
- **C6: analyze stays off the action sequence.** `analyze/step.yaml` keeps `in_action_sequence: false`, so no action index and no graph edge are added, and `test_softwaredev_roundtrip.py` stays as it is. The runtime template gains the step; the prompt resolves from the step directory (B5 asserts this). The tasks prompt's "undefined template" is fixed by referring to the tasks template through the existing template resolver wording, not by adding `template:` to `tasks/step.yaml`.
- **C7: more pinning tests to update in the same WP.**
  - Snapshots: the rendered `tests/specify_cli/regression/_twelve_agent_baseline/{claude,gemini}/specify.*` and `tests/specify_cli/skills/__snapshots__/codex/specify.SKILL.md`, regenerated with the repository's snapshot update flag.
  - Correction: `test_command_template_cleanliness.py:396-408` pins the tasks prompt, not analyze. The same file's `:193` limits the tasks-template fix.
  - Wording pins: `test_mission_creation_probe_order.py:107/:270`, `test_mission_creation_fanout_commit_boundary.py:164` and `tests/next/test_next_command_integration.py:556`.
- **C8: provenance ratchet.**
  - The baseline is edited by hand, entry by entry, and the diff may only lower counts. The census dump is not redirected over the file.
  - C-003 is reworded from "no `kitty-specs/` paths" to "no concrete Mission slugs, WP ids, issue numbers, requirement ids or `src/specify_cli` paths". Placeholders such as `kitty-specs/<mission>/analysis-report.md` are allowed.
  - tasks-finalize gains a baseline entry only if it is at zero.
- **C9: more "feature" sites (FR-012/FR-014).**
  - Errors to fix: `lanes/consolidation.py:273/:377`, `implement.py:379`, `implement_phases.py:145`, `task_utils/support.py:606`, `validate_tasks.py:78/:125`, `validate_encoding.py:50`, `core/mission_creation_identity.py:47`, `cli/helpers.py:437`, `mission_type.py:1666`, `mission_branch_context.py:149`.
  - Commitlint covers the "origin-ticket binding" subject as well.
  - The FR-014 scan covers every non-docstring string constant under `src/specify_cli` that contains "for feature" or starts with "Feature:", not only call arguments.
  - The error code `FEATURE_CONTEXT_UNRESOLVED` is a machine contract and stays as it is. It is filed as a follow-up.
- **C10: analyze recovery recipe.** The recipe writes the report to a path outside the checkout (the scratch or temp directory) and passes that path to `record-analysis`. Writing into the checkout makes the worktree dirty, and `record-analysis` then refuses with `DIRTY_WORKTREE`.
- **C11: glossary.** Fix `docs/context/spec-driven.md:329`. The contextive regeneration is expected to widen the `test_no_legacy_terminology` baseline diff for `orchestration.yml`; it may only shrink.
- **C12: SC-008 gate.**
  - SC-008 is a gate file, `tests/doctrine/test_software_dev_prompt_walk.py`. It extends `test_builtin_cli_command_references.py` with:
    1. checking each `--option` in the same code span against the command's Click params;
    2. scanning step-contract `command:` values rendered through `_render_declared_command`;
    3. checking each "next advances to X" claim against the runtime template order;
    4. resolving consumer paths against a `spec-kitty init` fixture, with an explicit list of placeholder forms.
  - It covers the CLI-driven implement, review, accept and tasks-finalize prompts.
- **C13.** Run `pip install -e .` (or `uv sync --frozen`) before trusting `test_doctrine_regenerate_graph_roundtrip.py`. The glossary pack is hashed, so run regenerate-graph after D10.
