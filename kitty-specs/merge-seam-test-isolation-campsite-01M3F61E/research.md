# Research: Merge-seam placement, test-isolation sweep & model-slot verdict

Phase 0 for mission `merge-seam-test-isolation-campsite-01M3F61E`. Grounded on `main` `da6d0af97e` (branch head `8295fba284`). Two profile-loaded opus researchers (architect-alphonso for #5119, python-pedro for #5118) plus orchestrator grounding for #5117. Supporting artefacts live in `research/` beside this file.

| Artefact | What it is |
|---|---|
| `research/global_state_scan_prototype.py` | FR-007 detector prototype (471 sites / 155 files / 278 keys; 3.9 s over 3353 files; 0 parse failures). Run from repo root. |
| `research/global_state_sites_classified.tsv` | Every site: file, qualname, line, kind, form, fix class, token line. Line numbers are navigation only. |
| `research/assign_shards.py` / `research/sweep_shards.tsv` | Deterministic file → sweep-shard assignment (disjoint file sets). |
| `research/merge_cli_rule_probe.py` | FR-005 probe: RED today with exactly `specify_cli/merge/git_probes.py:667`. |

---

## R1 — Blob-reader dedup (FR-001, #5119)

- **Decision**: Keep `merge/git_probes.py::_read_git_blob_bytes` (L605–622) as the single reader; delete `merge/bookkeeping_projection.py::_git_show_blob_bytes` (L484–499) and its now-unused `import subprocess` (L16); extend the existing `bookkeeping_projection → git_probes` import (L28); fix the git_probes docstring (L609) that cites the deleted copy.
- **Rationale**: Bodies are byte-identical (only parameter name `repo_root`/`main_repo` and docstring differ). The import edge already runs projection → probes. Callers: projection L537, L555, L597–602; probes L716, L717, L722. No test references or patches either name.
- **Pins**: `tests/architectural/test_destructive_op_routing.py:172` (`git_probes.py:236:reset_hard`) does **not** shift (all edits below L236). `tool_artifact_enrolment/inventory.md:44–48` rows are navigation-only (header says never compared) — refresh for tidiness only.
- **Alternatives**: move the reader to a new `git` utility module — rejected (adds a third location; projection already imports probes).

## R2 — Driver-body relocation (FR-002/003/004, #5119)

- **Decision**: New single module `src/specify_cli/merge/drivers.py` holding the file-level body of all six registered drivers + their helpers + serialization, with this contract:
  - `class MergeDriverError(Exception)` (path and row-matrix errors subclass it); bodies translate foreign errors (`EventLogMergeError`, `AcceptanceMatrixParseError`, `json.JSONDecodeError`) to `MergeDriverError(str(exc)) from exc` so stderr stays byte-identical. Internal helpers keep raising what they raise today (their tests stay valid). Do **not** broaden catches (traces' `UnicodeDecodeError` propagates today — keep it).
  - `@dataclass(frozen=True) class MergeDriverOutcome: notice: str | None = None` (review-cycle's stdout notice).
  - `run_<kind>_driver(base: str, ours: str, theirs: str) -> MergeDriverOutcome` for event-log, meta, traces, issue-matrix, acceptance-matrix, review-cycle; each begins with the existing path hardening (`_resolve_merge_driver_paths_or_exit` logic, now raising).
  - `MERGE_DRIVER_BODIES: Mapping[str, MergeDriverBody]` keyed by the command name (`merge-driver-meta`, …) — 6 keys.
- **Per-driver facts** (current `cli/commands/merge_driver.py` lines):

  | Driver | Typer fn | Reconcile | Serialization | Caught |
  |---|---|---|---|---|
  | event-log | L149 | `status.merge_event_log_files` (writes JSONL sort_keys + "\n") | by status | `EventLogMergeError` |
  | meta | L277 | `reconcile_meta_payloads(_load_json_object×2)` (base unused) | `_META_JSON_KWARGS` + "\n" | `JSONDecodeError`, `EventLogMergeError` |
  | traces | L525 | `_drop_stale_theirs_trace_blocks` → `union_trace_texts` | as-is | — |
  | issue-matrix | L849 | 3-way row reconcile | `indent=2, sort_keys=True` + "\n" | `RowMatrixMergeError`, `AcceptanceMatrixParseError` |
  | acceptance-matrix | L941 | 3-way row reconcile | `indent=2` + "\n" (**no** sort_keys — preserve asymmetry) | same |
  | review-cycle | L1019 | identical → write ours; else "\n"-joined conflict markers | stdout notice, exit 0 | — |

- **CLI shell**: same module path and the same six function names/signatures (so `cli/commands/__init__.py:341 _register_merge_driver` and `tests/cli/test_lazy_command_module_imports.py` are untouched; C-001 holds). Each shell: `_run(body, base, ours, theirs)` → on `MergeDriverError` echo to stderr + `typer.Exit(1)`; echo `outcome.notice` to stdout if set. Do **not** touch `merge/__init__.py` or `cli/commands/__init__.py` (version-bump rule; lazy imports).
- **Resolver** (`git_probes.py:657–677`): keep the registry lookup + `_DRIVER_COMMAND_PATTERN` (event-log has 2 specs under one config key); replace `getattr(<typer module>, …)` with `MERGE_DRIVER_BODIES.get(match.group(1))` via a **function-local** `from specify_cli.merge.drivers import MERGE_DRIVER_BODIES` (keeps L236 fixed, zero import-time cost). In `driver_replay_expected_bytes` (L728–733) keep the fail-closed `except Exception`, fix the stale `typer.Exit` comment. Benign side effect: replay no longer prints review-cycle's notice.
- **Completeness guard**: table keys == command names derived from `lanes/merge.py:60–123 _MERGE_DRIVERS` == `merge-driver-*` keys in `cli/commands/__init__.py:637–642 _COMMAND_REGISTRARS`.
- **Import cost**: `merge_driver` + `specify_cli.merge` 215 modules / 0.46 s vs 192 / 0.47 s today; no cycle.
- **Alternatives**: (a) relocate only the pure reconcilers (issue's literal ask) — rejected by the post-spec squad: serialization would stay in the CLI, so replay would re-serialize (second authority, byte-drift risk). (b) `merge/drivers/` package — deferred: a second structural change inside a behavior-preserving move; one module keeps the move reviewable with `--color-moved`. (c) `lanes/` home — rejected: `lanes/merge.py` owns the registry, not reconciliation.

## R3 — Merge → CLI-command-layer rule (FR-005, #5119)

- **Decision**: Extend `tests/architectural/test_layer_rules.py` (not a new guard file). Today's collector (L219–248) sees function-local imports (`ast.walk`) but **not** relative imports (`level == 0` only), **not** `importlib`/`__import__`/`find_spec` literal-string imports, and resolves `from specify_cli.cli import commands` only to `specify_cli.cli`. Add: relative-import resolution from the file's package; generalized `from X import sub` expansion; literal-string dynamic-import calls (never bare strings — `merge/_constants.py:21` logger name `"specify_cli.cli.commands.merge"` must not match). Introduce a site-level collector `(rel, lineno, qualname, module)` and make the old collector its projection (one collector). Verified: `runtime`/`mission_runtime` have no relative/dynamic `specify_cli` imports, so their ledgers are unchanged.
- **New `TestMergeCliBoundary`**: any `specify_cli.cli` / `specify_cli.cli.*` import from `specify_cli/merge/` other than `specify_cli.cli.console` fails; named ledger `_MERGE_CLI_CONSOLE_IMPORTERS` = {done_bookkeeping, ordering, forecast, push_preflight, git_probes, preflight, executor} with a stale-entry guard (shrink-only by construction). Findings deduplicated per site. Self-mutation: plant each form (module-level and function-local `import`, `from … import`, `from specify_cli.cli import commands`, `from ..cli.commands import merge_driver`, `import_module(...)`, `__import__(...)`) into a temp `specify_cli/merge/` module; negative controls: the console import and the logger string.
- **Registry**: the `_baselines.yaml` count row is **deferred** (C-002/C-007 — ratchet-owned file).
- **Alternatives**: bespoke `test_merge_no_cli_import.py` — rejected (parallel authority to the layer ledger); pytestarch `LayerRule` — rejected (both packages sit under `specify_cli`, below pytestarch's layer granularity).

## R4 — Pins and importers to re-point (#5119)

- **Re-point imports to `merge/drivers.py`**: `tests/merge/test_squash_reconcilers_2709.py:15`, `tests/merge/test_gate_artifact_merge_drivers_2804.py:46`, `tests/merge/test_merge_driver_meta_diagnosability.py:25`, `tests/acceptance/test_issue_3231…:35`, pure-logic symbols at `tests/merge/test_traces_driver_section_union_4894.py:42`, `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py:31`, `_load_json_object` at `tests/merge/test_merge_driver_wrappers_2709.py:22`. **Must fix**: `monkeypatch` target `merge_driver.merge_event_log_files` at `test_merge_driver_wrappers_2709.py:85` (AttributeError after move).
- **Keep** (shell tests): shell imports in `test_merge_driver_wrappers_2709.py`, `…4894.py:65`, `tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py:49` (its stdout pin at L475 stays valid), `tests/architectural/test_merge_reconciliation_class_guard.py:505`, `tests/cli/test_lazy_command_module_imports.py:122/140/155`.
- **Do not edit**: `tests/release/coverage_breadth_baseline.json:2131` — dated snapshot (`produced_at_commit 576801bc`), only non-emptiness gated (`test_coverage_breadth.py:283–285`); editing falsifies provenance. `docs/plans/engineering-notes/coord-splitbrain-rootcause.md:55` — historical.
- **Re-pin (C-002 exception)**: `tests/architectural/test_inline_meta_read_gate.py:1118` → `merge/drivers.py`, and assert the qualname exists (else vacuous).
- **Docstrings/comments**: `upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py:21–23`, `lanes/merge.py:109–112` (comment only; registry `name` unchanged), `merge/executor.py:2460`, `acceptance/matrix.py:193`, test docstrings `test_repro_5038.py:28`, `test_bookkeeping_projection_seam.py:168`, `…4894:4,15,24`, `…2804:5`, `…3231:11`, `test_matrix_marker_reject.py:10`, `test_issue_matrix_json_migration_completeness.py:111`, `class_guard:277`.

## R5 — Golden characterisation (NFR-001, #5119)

- **Decision**: cases at `tests/merge/merge_driver_goldens/<command>/<case>/{O,A,B,expected_A,case.json}` (`case.json`: exit code, stdout, stderr with tmp dir normalized to `<TMP>`, absent-file flags); ≥3 cases per driver + 1 path-injection case each. Test `tests/merge/test_merge_driver_goldens.py` with two legs: subprocess (`sys.executable -m specify_cli merge-driver-X O A B`, `PYTHONPATH=src`, temp `HOME` — startup writes agent dirs into HOME; avoids a stale installed `spec-kitty`) and in-process (`_resolve_registered_driver_callable(config_key)`; bytes on success, "raised" on failure — works pre- and post-move). Plus an "all six resolve in replay" test (today only traces is covered by `test_bookkeeping_projection_seam.py:202–318`).
- **Ordering**: goldens captured and committed green **before** the move; the move's diff over the goldens dir must be empty.
- **Placement**: `tests/merge` — the per-PR merge shard runs it (`ci-module-registry.yml:13–32` does not run `tests/specify_cli/cli`), giving diff-cover on the moved lines.

## R6 — Census detector & allowlist (FR-006..009, #5118)

- **House pattern**: detector module `tests/architectural/_global_state_scan.py` (root-parameterized, like `_destructive_op_census.py`/`_home_pin_scan.py`); gate `tests/architectural/test_no_manual_global_state_mutation.py` with self-mutation via planted files in `tmp_path`, a scanned-files floor, a drop-one-row test, and a YAML allowlist.
- **Keys**: `specify_cli.contracts.anchoring` `_build_qualname_map` + `code_tokens_by_line` built once per file (per-site `composite_key` re-parses). Rows keyed (file, qualname, kind) + exact count. No line keys (the `file:line:op` shape of `_destructive_op_census` is exactly what FR-008 forbids).
- **Hard constraint**: `test_home_pin_seam_no_second_copy.py` bans `ast.parse` and `NodeVisitor` subclasses in any module importing `_home_pin_scan`. The detector reuses `home.find_write_sites(tree, key=home.NEEDLE)` for the SPEC_KITTY_HOME exclusion, parses with `home.parse_module` (propagates `SyntaxError` → parse failure fails the gate), and uses plain `ast.walk`. `test_home_pin_verdict_seam.py` adds signals for modules importing the scanner (census/baseline + `.yaml` path literals, hash calls, `==`/`<=` over census/baseline/discovered/exempt) → keep allowlist I/O and comparison in the **gate** file (which does not import `_home_pin_scan`), and name the allowlist dir `global_state_allowlist/` (no "census"/"baseline").
- **Existing-gate ownership**: `patch.dict(sys.modules …)` (`test_no_sys_modules_patch_dict.py`) — the detector never flags `patch.dict`, so no overlap by construction. `_home_pin_scan` owns only SPEC_KITTY_HOME writes via `setenv`, `environ[k]=`, `.setdefault` — deletes/pops of that key are **not** owned and stay flagged. The 3-site delta (474 → 471) is exactly those owned writes.
- **Coverage** (prototype): aliases (`import os as _o`, `from os import chdir, environ as E, putenv`, `from sys import path, argv, modules`, flow-insensitive `env = os.environ`); forms: mutating calls, `[]=`, slice-store, `del`, rebind/augassign, `setattr(sys|os, …)`; never flags `monkeypatch.*`, `MonkeyPatch.context`, `contextlib.chdir`, reads. 10/10 planted forms caught. No aliased/indirect forms exist in today's tree.
- **Census** (471 sites, 155 files, 278 keys): cwd 273 (all `os.chdir`); sys.path 66 (all `.insert`); os.environ 61 (33 `[]=`, 15 `.pop`, 11 `.setdefault`, 2 `.update`); sys.modules 56 (37 `[]=`, 9 `del`, 9 `.pop`, 1 `.update`); sys.argv 15 (rebinds).
- **Runtime**: 3.9 s full tree (parse floor 2.1 s) — within NFR-005 (<10 s).

## R7 — Fix classification (FR-006, #5118)

| Class | Sites | Replacement |
|---|---|---|
| A — `monkeypatch.*` | 170 | incl. helpers injecting `sys.modules` (pass `monkeypatch` in; `patch.dict(sys.modules)` is banned) |
| A — autouse fixture | 8 | module-level `os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK")` → autouse `monkeypatch.setenv` (product reads per call, not at import) |
| B — `contextlib.chdir` | 160 | mostly `_invoke*`/`_run*` helpers `getcwd → chdir → try: CliRunner.invoke → finally chdir` |
| B — `mock.patch.dict(os.environ)` / `patch.object(sys, "argv")` | 34 | block-scoped env/argv helpers |
| C — `MonkeyPatch.context()` | 1 | root `conftest.py` session-scoped `test_venv` |
| D1 — delete redundant import-time insert | 50 | pytest rootdir-prepend (`tests/__init__.py` exists) + `pythonpath = src` already cover `_REPO_ROOT`/`src`/`_WORKTREE_SRC`/`Path.cwd()/"src"` inserts (22 are un-undone inserts in research test bodies) |
| D2 — canonical package import | 5 | `src/specify_cli` inserted for bare `import gitignore_manager` (gives the module a second identity) → import `specify_cli.gitignore_manager` |
| D3 — canonical `scripts.*` import | 6 | `scripts/docs` is a package; `scripts`, `scripts/release` namespace packages — verify bare sibling imports per file |
| E1 — process bootstrap | 6 | allowlist (`pytest_configure`, `_apply_home_env`) |
| E2 — subprocess/multiprocessing entry | 15 | allowlist (audit CLIs, `lease_revocation_chain_runner`, `write_observer`, `bench_chokepoint`, spawn workers `_event_mutant_worker`, `_sc004_worker`, `_run_ensure` — child-local state) |
| E3 — leak sentinel | 2 | allowlist (`_isolated_worker_home` snapshot/restore) |
| E4 — deferred-01M3EW3Z | 14 | allowlist (3 ratchet-owned files) |

- **Projected allowlist**: 37 sites (7.8%) vs NFR-003 cap 95 (20%). Per-class caps: E1 6, E2 15, E3 2, E4 14.
- **Risks**: `sys.modules` deletions needing parent-attr handling (14 sites: secure_storage/platform_split, `_restore_modules` helpers, bytecode_heal/bytecode_doctor `_purge_pkg_modules`, both `import_paths` shim-gone tests, context_lifecycle, runtime_bridge_documentation_composition, adapter_contract); thread-pool timeouts (2876, `test_plantuml_invoke`, `record_analysis`) — cwd is process-wide either way; `monkeypatch.chdir` restores only at teardown (use `contextlib.chdir` where mid-test restore matters). No site file asserts cwd after the product runs.

## R8 — Gate/sweep ordering without a hotspot baseline (C-006, #5118)

- **Decision**: WP01 commit A lands the gate + empty allowlist — **RED** through its entry point naming 471 sites. Commit B adds permanent `global_state_allowlist/<shard>.yaml` files (one per sweep WP: `transitional-sweep` rows with exact counts + justified E1–E3 rows for that shard's files) + `deferred-01M3EW3Z.yaml` (E4); the gate goes green and asserts every row lives in the shard whose file set it owns (per `research/sweep_shards.tsv`). Each sweep WP drains **only its own shard's** transitional rows — exact counts track progress, no cross-lane conflicts. The Seal WP adds a separate sealed-invariant test (no transitional rows; frozen per-class caps) — separate file so no two WPs own the gate. *(Amended at tasks: shards permanent, not deleted; `surface_resolution_audit/**` is ratchet-owned → E4, giving E2 13 / E4 16.)*
- **Alternatives**: gate lands last (after sweep) — rejected (no red-first; sweep unguarded); single baseline file — rejected (8 parallel lanes contending on one file).

## R9 — `model` slot (FR-010/011, #5117)

- **Canonical source**: `src/charter/offering/agent_profiles/schema_models.py:217` `preferred_model: str | None = Field(default=None, alias="model")` (mirrored by `profile.py:266`). `agent-profile.schema.yaml` is generated by `scripts/generate_schemas.py`; `--check` is gated by `tests/doctrine/test_schema_generation_integrity.py` (and `tests/doctrine/agent_profiles/test_schema_generation.py`).
- **Decision**: add `description=` to the `schema_models.py` field (consumer-authored routing preference; built-in profiles deliberately omit it; consumed by the dispatch routing advisory), regenerate. Extend `tests/doctrine/test_agent_profile_model_field.py` with a disk → `AgentProfileRepository` → `specify_cli/invocation/executor.py:75 _compute_recommendation` test (patch the catalog `load()` to a fixed catalog) asserting a profile-preference candidate with the authored id; mutation proof: dropping the alias fails it.
- **Already covered (not duplicated)**: alias/mapping (`test_agent_profile_model_field.py`), evaluator candidate emission (`tests/doctrine/test_model_task_routing_evaluator.py::test_advisory_emits_both_catalog_and_profile_candidates_with_provenance`).
- **Left alone**: `_inert_slots_baseline.yaml:277` (`model: delete-the-declaration, provisional`) — ratchet WP05 deletes it (C-002/C-003).

## Supply chain

No dependency is added, upgraded or removed. The supply-chain adversarial-evidence pass is not applicable.
