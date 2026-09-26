---
work_package_id: WP01
title: Torn-read escalation to the serialization point (red-first → fix)
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- C-005
- C-006
- C-007
- C-008
- C-009
- C-010
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-3998-startup-assess-cold-concurrency
merge_target_branch: issue-3998-startup-assess-cold-concurrency
branch_strategy: Planning artifacts for this mission were generated on issue-3998-startup-assess-cold-concurrency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3998-startup-assess-cold-concurrency unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-startup-assess-cold-concurrency-01M3EQ9S
base_commit: 81b835441bd4d34a4e6d2a2ce557356d569ed633
created_at: '2026-09-26T11:53:50.377769+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Fix
history:
- at: '2026-09-26T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/
create_intent:
- tests/runtime/test_startup_torn_read_escalation.py
- tests/runtime/test_build_serialized.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/runtime/asset_preparation.py
- src/specify_cli/runtime/bootstrap.py
- src/specify_cli/runtime/agent_commands.py
- src/specify_cli/runtime/agent_skills.py
- tests/runtime/test_startup_torn_read_escalation.py
- tests/runtime/test_build_serialized.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Torn-read escalation to the serialization point (red-first → fix)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. (CLI equivalent: `.venv/bin/spec-kitty profiles show python-pedro`.)

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the implement-action doctrine: `spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission startup-assess-cold-concurrency-01M3EQ9S`) or the Activity Log below. If this WP came back from review, the feedback items are your TODO list.

---

## Objectives & Success Criteria

Fix GitHub #3998. Today, a **torn read** on an owner's **unlocked assessment** is terminal. A torn read is `AssetPreparation.observe()` seeing the same path in two states within one pass, raised as `ValueError("Asset changed during preparation: <path>")`. Today's failure path:

1. `retry_torn_read` re-races the concurrent writer three times without waiting.
2. `incomplete()` then collapses the error into the generic `global_assets_unavailable` diagnostic.
3. `ensure_*` raises a bare `RuntimeError`, and the CLI prints a Rich traceback.

It crashes 1–5 of 16–32 concurrent commands on a fresh shared home.

Done means all of the following hold:

- **Destination tear escalates.** A destination-role torn read on the unlocked pass makes the owner acquire its **serialization point**, which is exactly the lock set `recheck_assets` acquires, and rebuild once under it. The command then converges and runs.
- **Some tears stay terminal.** These are: a torn read under the serialization point, a re-entrant one (lock paths already in `_HELD_LOCKS`), and any source-role torn read.
- **Terminal failures render cleanly.** They surface as `StartupAssetError(GuardedReadError, RuntimeError)`, which `_run_app_with_error_hook` renders at exit 1 with no traceback.
- **The warm path is unchanged.** It takes 1 assessment and 0 lock acquisitions per owner.
- **Red-first order holds.** The red-first regression test is committed **red** before any production change, and flipped to a functional test at the end.

Acceptance: spec FR-001..FR-008, NFR-002..NFR-004, C-001..C-010. Contract: `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/contracts/startup-asset-escalation.md`.

## ⚠️ Post-tasks squad folds (BINDING — these supersede any conflicting text below)

A post-tasks anti-laziness lens and a brownfield scout lens were run against HEAD `b613284884`. Both verified T001 goes RED on base for all three owners, and both confirmed that `events --help` triggers `ensure_runtime`, because the Click group callback runs before the subcommand's `--help`.

1. **Never nest serialization points (C-005, stronger).** In `build_serialized`, a `TornReadError` is terminal if `_HELD_LOCKS.get()` is **non-empty at all**, not only the subset case.
   - Rationale: all three owners share one cold-install sentinel, because their anchors are the same (HOME's parent). `machine_file_lock` is non-reentrant, so a nested escalation would self-deadlock on the sentinel. Batch paths also take owner locks in sorted order, so a cross-owner escalation risks lock-order inversion.
   - Add a unit test: `_HELD_LOCKS` holding an *unrelated* path → terminal, and 0 lock calls.
2. **Complexity ceiling.** `assess_global_agent_commands` is already at complexity **15**, because ruff counts its nested `_build`. The swap at `agent_commands.py:718` must add **zero** branches. All logic goes in `build_serialized` / `incomplete`. Run `ruff check --select C901` on it before committing.
3. **`StartupAssetError` construction (T006).**
   - Pass `path` as `str(p)` or `None`, never a `Path`. `_guarded_read_error_json_payload` (`src/specify_cli/__init__.py:437`) does `json.dumps` and would raise `TypeError`, bringing a traceback back under `--json`.
   - Construct it as `StartupAssetError(reason, path=..., reason=reason)` so `args[0]` is set too.
   - `reason = f"{owner_key}: " + "; ".join(messages) + <next step>`, so the owner is named (FR-005 / US3.1).
   - The JSON envelope emits only `error` / `kind` / `path`. Do **not** add `code` to it and do not add a renderer. Keep `code` as a Python attribute only.
4. **T008 CLI test must go through the real hook.** `CliRunner` bypasses `_run_app_with_error_hook`, and `main_callback` reads `sys.argv`. Proceed as follows:
   - Monkeypatch `sys.argv = ["spec-kitty", "events", "--help"]` (append `"--json"` for the JSON case).
   - Call `specify_cli._run_app_with_error_hook(specify_cli._get_app(), json_mode=...)` under `pytest.raises(SystemExit)` with code 1. Verify the exact app-getter name in `__init__.py`.
   - Do **not** call `main()`, because its logging bootstrap mutates global handlers.
   - Assert using capsys:
     - **text:** stderr is exactly one line starting with `Error:`, contains `runtime_bootstrap` and the path, and has no `Traceback`.
     - **json:** `json.loads(<entire stdout>)` gives `kind == "StartupAssetError"`. Whole-stdout parsing also pins FR-008's stdout silence.
5. **T001 injection details.**
   - Alternate starting from `absent` for each fresh preparation. If the first inventory observation returns `file`, `__init__` calls `read_bytes()` on a nonexistent file. That produces an `OSError`, which surfaces as `global_assets_unavailable` for the wrong reason.
   - Keep fixture *sources* outside the kittify home, so source-role stickiness does not reclassify the tear as `asset_source_drift`.
   - Import `FileState` from `specify_cli.tool_surface.operations`, with no `# type: ignore`.
   - Use `fake_package_assets` and a **trimmed** command template dir and agent set. With the real templates, the commands param takes about 15 s, and reading `packs/built-in` trips the corpus-marker guard. If a param still takes more than about 1 s, drop `fast` for it.
   - Strengthen the step-4 assertions: the inventory is observed exactly **2** times before the first lock call (one unlocked build, NFR-003), and the recorded lock list equals `[_cold_install_sentinel(anchor)]`.
6. **Additional falsifiers.**
   - **T007.13 (FR-002, C-003):** with the T001 injection, call `bootstrap.assess_runtime()` and `asset_preparation.assess_global_assets(runtime=False, commands=False)` directly. Assert `.complete`, and spy on `_GlobalAssetPreparation.include` to prove it is called exactly **1** time.
   - **T007.9 warm spy (replaces the assess_* counting):** count `AssetPreparation.__init__` invocations. Expect runtime = 1, skills = 1, and commands = 0 (the freshness short-circuit builds nothing), with `machine_file_lock` = 0.
   - **T007.8 C-008:** compare the recorded lock lists in two states:
     - cold, expecting `[sentinel]`;
     - after touching `prepared.lock_path`, expecting `[lock_path]`.

     The fake `build` raises `TornReadError(role="destination_probe", lock_paths=prepared.lock_paths, anchor=prepared.anchor)` once. Assert concrete lists, not "the `_serialize_owner` set" (circular).
   - **T008.3 source drift:** use `fake_package_assets`. Tear `<pkg_root>/AGENTS.md`, which is observed at bootstrap's `observe(source)` and again at `source(source)`, alternating **two different `file` digests** (never `absent`, or the owner just skips it). Expect code `asset_source_drift` and 0 lock calls.
   - **T008.4 (US3.3):** write `{}` to the runtime inventory. `ensure_runtime()` raises `StartupAssetError` with code `global_assets_unavailable`, and `machine_file_lock` gets 0 calls (no waiting).
7. **Facts corrected.**
   - `asset_preparation` has **no** module `_LOG`. Use `logger if logger is not None else logging.getLogger(__name__)`, as `apply_with_reassess` does.
   - It also has **no** `__all__`, and you must not add one: the dead-symbol gate exempts same-module-used names only when they are absent from `__all__`.
   - Line numbers: `finish` ~:432, `check_assets` ~:754.
   - The CLI's log handler sits at WARNING, so the INFO wait line is invisible by default. That matches the `converged_log_message` precedent. Assert it with caplog on the owner logger's name.
8. **Second owner-lock site (R-1).** `_apply_retained_assets` (~ap.py:1135) creates and then locks the owner lock itself during a cold apply. This is the documented cold-create exception. Do **not** route it through `_serialize_owner`, which would double-lock it. Add a one-line comment there that points at R-1.
9. **Existing guards must stay green unchanged:** `tests/runtime/test_generic_asset_scope.py` (C-004/C-006) and the home-pin census (fixtures use `SPEC_KITTY_HOME=<home>/.kittify`, never `tmp_path/"home"` itself).
10. **PR note (for the orchestrator):** `migrate_cmd.py:180` has no handler. It changes from a traceback to a clean exit 1. That is a behaviour improvement.

## Context & Constraints

Read first, in this order:
- `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/spec.md`: especially the Domain Language table. Use "serialization point", "owner lock" and "cold-install sentinel" precisely, never bare "the lock".
- `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/plan.md`: the Design section and its flowchart.
- `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/research.md`: decisions D-1..D-8 and why the alternatives were rejected.
- `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/data-model.md` and `contracts/startup-asset-escalation.md`.
- `.kittify/charter/charter.md`: red-first (ADR 2026-07-17-1), tidy-first campsite cleaning, complexity ≤ 15, no suppressions.

Code map (line numbers are from planning base `87838d091c`; re-grep before editing):

- `src/specify_cli/runtime/asset_preparation.py`
  - `node_state` (~:50)
  - `_observation` (~:158): directories drop `mtime` and compare `(dev, ino)`
  - `AssetPreparation.__init__` (~:173): `lock_path = cache/lock_name`; the inventory is observed at ~:186
  - `observe` (~:205-241): the torn-read raise is at ~:237-238, and source-role stickiness follows it
  - `finish` (~:456): builds `PreparedAssets(..., self.lock_path, self.root.path, ...)`
  - `incomplete` (~:468)
  - `_TORN_READ_RETRY_ATTEMPTS` / `_TORN_READ_MESSAGE_PREFIX` / `retry_torn_read` (~:478-514)
  - `_GlobalAssetPreparation.include` (~:517): must run once, outside the retried build
  - `assess_global_assets` (~:618)
  - `check_assets` (~:780)
  - `_cold_install_sentinel` (~:834)
  - `recheck_assets` (~:892-952): **the lock-set block to extract is ~:932-952**
  - `apply_with_reassess` (~:955)
- `src/specify_cli/runtime/bootstrap.py`: `assess_runtime` (~:130-171, the `retry_torn_read` call at ~:166) and `ensure_runtime` (~:174-222, raises at ~:214-215 and ~:221-222).
- `src/specify_cli/runtime/agent_commands.py`: `assess_global_agent_commands` (~:590-723, the `retry_torn_read` call at ~:718) and `_apply_command_assessment` (~:753-773, raises at ~:760-761 and ~:772-773).
- `src/specify_cli/runtime/agent_skills.py`: `assess_global_agent_skills` (~:167-247, the call at ~:242) and `ensure_global_agent_skills` (~:250-275, raises at ~:264-265 and ~:274-275).
- `src/kernel/errors.py`: the `GuardedReadError` base (`path=`, `reason=` kwargs; `__str__` returns `reason`).
- `src/specify_cli/__init__.py`: `main_callback` (~:140-160) calls `ensure_runtime()` and the other `ensure_*`. `_run_app_with_error_hook` (~:451) catches `GuardedReadError` and prints either one `Error: …` line to stderr or JSON, then exits 1.

Hard constraints:
- **C-001:** never relax source drift. A source-role torn read is refused with **no** lock and **no** retry.
- **C-002:** the warm path stays lock-free. The first `build()` runs with no lock.
- **C-003:** `_batch.include()` stays *after* `build_serialized(...)` and runs once.
- **C-004:** do not touch `check_assets`'s "Global asset input changed" gate.
- **C-005:** if a tear's lock paths are already held, it is terminal and never blocks.
- **C-008:** one serialization authority, `_serialize_owner`, used by both `recheck_assets` and `build_serialized`.
- **C-009:** never read owner lock bytes (#4703).
- **C-010:** reuse the `GuardedReadError` hook.
- **No suppressions:** no `# noqa` / `# type: ignore` to get green. Fix the code. The repo's existing narrowly justified ones stay as they are.
- **Out of scope (do not touch):** the `managed_skills` paired composition, the skills installer's cross-family "observations disagree" `ValueError` (keep it a plain `ValueError`), and agent install fan-out.

## Branch Strategy

- **Strategy**: lane worktree per `lanes.json` (created by `spec-kitty implement WP01`).
- **Planning base branch**: `issue-3998-startup-assess-cold-concurrency`
- **Merge target branch**: `issue-3998-startup-assess-cold-concurrency`
- Work only in the resolved lane worktree. The `.venv` lives at the **main checkout root**; lane worktrees have none. Run tests as `PYTHONPATH=$(pwd)/src <repo>/.venv/bin/python -m pytest …`. Never use the global `spec-kitty` binary to exercise lane code, because it resolves the main checkout's `src`. Never use a bare `uv run`, which destroys the hand-built venv.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first issue-pinned regression test (commit RED)

- **Purpose:** prove the defect through the **pre-existing entry points** before any fix (ADR 2026-07-17-1, C-007, FR-006).
- **File:** `tests/runtime/test_startup_torn_read_escalation.py` (new).
- **Steps:**
  1. Module docstring citing #3998. Mark it `pytestmark = [pytest.mark.unit, pytest.mark.fast]`, and put `@pytest.mark.regression` on the pinned test(s).
  2. Fixtures: a cold `HOME` + `SPEC_KITTY_HOME=<home>/.kittify` (mirror `fake_home` in `tests/runtime/test_generic_asset_scope.py:63`), `fake_package_assets` (same file, ~:71) for the runtime owner, and `fake_skill_registry` (same file, ~:98) for the skills owner. For the commands owner, follow the setup in `tests/runtime/test_generic_asset_scope.py`'s `TestNonRuntimeOwnerConcurrentColdHomeInterleave` commands case, and `tests/specify_cli/runtime/test_agent_commands.py`, to point command rendering at a small template set and agent dirs under the fake `HOME`.
  3. Injection happens **at leaf I/O only**, never by patching `assess_*`, `retry_torn_read`, `build_serialized` or any new helper:
     - Wrap `specify_cli.runtime.asset_preparation.node_state`. While `peer["active"]` is true and `path == <owner inventory>`, return alternately `FileState("absent")` and a `FileState("file", sha256=<changing digest>, mode=0o644)`. That tears **every** unlocked build.
     - Wrap `specify_cli.runtime.asset_preparation.machine_file_lock` so that it sets `peer["active"] = False`, then delegates to the real primitive. This models "the writer has finished by the time I hold its lock".
     - A verified scratch prototype of exactly this lives at `<scratch>/align/test_red_probe.py` (the runtime owner only; its `_prototype_*` half is NOT to be copied).
     - Owner inventories are `<kittify_home>/cache/<owner>-assets.json`, with owner keys `runtime_bootstrap`, `slash_commands` and `global_skills`. Confirm each owner's `AssetPreparation(...)` cache dir by reading the call site. Do not guess.
  4. Parametrize over the three owners, `runtime` → `bootstrap.ensure_runtime()`, `commands` → `agent_commands.ensure_global_agent_commands()`, `skills` → `agent_skills.ensure_global_agent_skills()`, and assert that the call **does not raise** and the owner's inventory ends up a real file.
  5. Run it on the planning base and confirm it is **RED for all three params** with the exact production failure `Asset changed during preparation`. Paste the failing summary lines into the Activity Log.
  6. Commit it alone: `test(runtime): red-first repro — unlocked torn read crashes startup (#3998)`.
- **Notes:** the commands owner has a freshness short-circuit (`_freshness_short_circuit`, agent_commands.py ~:604). On a cold home it must not short-circuit. If it does, your fixture is not cold.

### Subtask T002 – Tidy-first: extract `_serialize_owner`

- **Purpose:** create the single serialization authority (C-008, research D-2) as a **behaviour-preserving** step before the functional change (Standing Order 2).
- **Steps:**
  1. In `asset_preparation.py`, add `@contextmanager def _serialize_owner(lock_paths: tuple[Path, ...], anchor: Path) -> Iterator[None]` whose body is the `ExitStack` block from `recheck_assets`, moved verbatim:
     - `cold = any(not path.exists() for path in lock_paths)`
     - if cold, enter `machine_file_lock(_cold_install_sentinel(anchor), blocking=True)`
     - enter `machine_file_lock(path, blocking=True)` for each existing path
     - set the `_HELD_LOCKS` token, and reset it in `finally`
  2. Rewrite `recheck_assets` to `with _serialize_owner(prepared.lock_paths, prepared.anchor): yield check_assets(assessment)`. Keep its early returns (no effects / not prepared / already held) exactly as they are, and move the relevant docstring paragraphs so none are lost.
  3. Run `tests/runtime/` (excluding your new red file) and confirm it is green and unchanged.
  4. Commit: `refactor(runtime): extract _serialize_owner from recheck_assets (tidy-first, #3998)`.
- **Notes:** `machine_file_lock` must stay a module-global lookup in `asset_preparation` so tests can patch it there (kernel.locks G6 seam).

### Subtask T003 – `TornReadError`

- **Purpose:** give the torn read a typed identity that carries its serialization identity (FR-003, research D-3).
- **Steps:**
  1. Define `class TornReadError(ValueError)` with keyword attributes `path: Path`, `role: ObservationRole`, `lock_paths: tuple[Path, ...]` and `anchor: Path`. `str()` must equal `f"Asset changed during preparation: {path}"`, which keeps `TORN_READ_SIGNAL` and existing message assertions valid. Add it to `__all__` if the module declares one.
  2. In `observe()`, replace the bare `raise ValueError(...)` at the torn-read site with `raise TornReadError(path=path, role=<effective role>, lock_paths=(self.lock_path,), anchor=self.root.path)`.
     - **Effective role:** `"source_read"` if `previous.role == "source_read"` or the incoming `role == "source_read"`, else `"destination_probe"`. This mirrors the stickiness rule a few lines below.
  3. Do **not** change `_GlobalAssetPreparation`'s cross-family "observations disagree" raise. It stays a plain `ValueError` (C-006).

### Subtask T004 – `build_serialized` replaces `retry_torn_read`; INFO signal

- **Purpose:** one unlocked attempt, then escalate once to the serialization point (FR-001/002/004/008, NFR-003, research D-1/D-4/D-5).
- **Steps:**
  1. Implement `def build_serialized(build: Callable[[], _T], *, logger: logging.Logger | None = None) -> _T` per `contracts/startup-asset-escalation.md` P1–P6:
     ```python
     try:
         return build()
     except TornReadError as exc:
         if exc.role == "source_read" or set(exc.lock_paths) <= _HELD_LOCKS.get():
             raise
         (logger or _LOG).info("%s", _waiting_message(exc))  # never contains "Error"
         with _serialize_owner(exc.lock_paths, exc.anchor):
             return build()
     ```
     Keep complexity well under 15. Extract `_is_terminal_torn_read(exc)` if it helps readability.
  2. Delete `retry_torn_read`, `_TORN_READ_RETRY_ATTEMPTS` and `_TORN_READ_MESSAGE_PREFIX`. Grep `src/` and `tests/` for any remaining reference; the dead-symbol gate must stay green.
  3. The docstring records the tradeoff (plan R-4): owner assessments reached outside startup (`skills/installer.py`, `tool_surface/providers/slash_commands.py`) may now block briefly on a concurrent installer after a destination torn read. This is intended.
  4. The operator signal is one INFO line, for example `"%s assets are being installed by another spec-kitty process; waiting for it to finish, then re-checking"`. It must not contain "Error" (the #3998 reproducer greps `Error`).

### Subtask T005 – `incomplete()` codes and owner swaps

- **Steps:**
  1. `incomplete(owner, root, error)` produces these diagnostic codes:
     - `"asset_source_drift"` for a `TornReadError` with a source role
     - `"asset_torn_read"` for any other `TornReadError`
     - unchanged `"global_assets_unavailable"` for everything else

     Messages are `str(error)`, unchanged.
  2. In `bootstrap.py`, `agent_commands.py` and `agent_skills.py`, replace `retry_torn_read(_build)` with `build_serialized(_build, logger=logger)`, using each module's own logger (they already have one; verify). Update the imports and keep the `# #4017 rescope` comments accurate (they reference the retry). `_batch.include(...)` stays after the call.
  3. Verify that the skills startup path (`ensure_global_agent_skills` → `assess_global_assets(runtime=False, commands=False)` → `assess_global_agent_skills(_batch=batch)`) escalates inside the owner's `_build`, *before* `include()`.

### Subtask T006 – `StartupAssetError` at the startup entry points

- **Purpose:** FR-005 / C-010. Remove the traceback by reusing the existing presentation seam.
- **Steps:**
  1. In `asset_preparation.py`, define `class StartupAssetError(GuardedReadError, RuntimeError)` (import `GuardedReadError` from `kernel.errors`; the direction `kernel <- specify_cli` is allowed). Give it a `code: str` attribute. Add a small helper, e.g. `startup_asset_error(owner_key, diagnostics) -> StartupAssetError`:
     - `reason` = the joined diagnostic messages plus a next step (for example: "…; another spec-kitty process may still be installing — re-run the command, and if it persists remove the partially written Spec Kitty home and re-run").
     - `path` = the path when exactly one diagnostic names one; parse only from the typed exception if you carry it, otherwise leave it `None`.
     - `code` = the first diagnostic's code.
  2. Replace the six bare `raise RuntimeError("; ".join(...))` sites (two each in `ensure_runtime`, `_apply_command_assessment` and `ensure_global_agent_skills`) with `raise startup_asset_error(...)`.
  3. `except RuntimeError` callers keep matching (for example `init.py`, `migrate_cmd.py`, `tests/specify_cli/runtime/test_agent_commands.py:180,:890` and `tests/runtime/test_windows_self_held_lock_read.py:181`). Confirm with grep that no caller catches by exact `type(...) is RuntimeError`.
  4. Check the JSON path: `_guarded_read_error_json_payload` in `src/specify_cli/__init__.py`. Make sure the payload includes something useful (it may already use `path`/`reason`). Do **not** add a new renderer.

### Subtask T007 – Primitive and invariant unit tests

- **File:** `tests/runtime/test_build_serialized.py` (new), `pytestmark = [pytest.mark.unit, pytest.mark.fast]`.
- **Tests** (each names the requirement it pins):
  1. **Clean first pass:** `build` is called once, and a spy on `asset_preparation.machine_file_lock` records 0 calls (P1, C-002).
  2. **Destination tear then success:** `build` is called twice, the lock spy records exactly the `_serialize_owner` set, and there is exactly one INFO record without "Error" (P2, FR-008, NFR-003).
  3. **Tear on both attempts:** `TornReadError` propagates after exactly 2 builds (FR-004).
  4. **Re-entrant:** with `_HELD_LOCKS` pre-set to the lock paths, the error propagates after 1 build and the lock spy records 0 calls. Use a timeout-free assertion; never actually block (C-005, P4).
  5. **Source-role tear:** propagates after 1 build with 0 lock calls (C-001, P3).
  6. **Non-torn errors:** a `ValueError("x")` and an `OSError` each propagate after 1 build (P5).
  7. **`_HELD_LOCKS` restored** after both return and raise (P6).
  8. **C-008 lock-set identity:** for a real cold-home runtime assessment (`assess_runtime()`, prepared), spy on `machine_file_lock` for (a) `recheck_assets(assessment)` and (b) `build_serialized` triggered by a `TornReadError` carrying `prepared.lock_paths` / `prepared.anchor`. Assert that the two ordered path lists are equal.
  9. **Warm-path spy (NFR-002, SC-003):** materialize a home via `ensure_runtime()`, then spy `assess_runtime` via the module attribute used by `ensure_runtime`, plus `machine_file_lock`. A second `ensure_runtime()` gives 1 assess and 0 locks. Do the same for commands and skills, where feasible, with the fixtures from T001.
  10. **Windows (C-009):** reuse `_mandatory_lock_read_simulation` from `tests/runtime/test_windows_self_held_lock_read.py` (import or replicate minimally). The escalation path over a warm owner lock never reads lock bytes.
  11. **Ancestor directory:** observe a directory as an ancestor, create a child under it, then observe again. No `TornReadError` (the spec Assumption / D-6 safety).
  12. **`incomplete()` codes:** a `TornReadError` with destination role gives `asset_torn_read`, one with source role gives `asset_source_drift`, and a plain `ValueError` gives `global_assets_unavailable`.

### Subtask T008 – Flip regression → functional; no-traceback CLI test

- **Steps:**
  1. The T001 test is now green. Remove `@pytest.mark.regression`, keep the test as the functional proof, and update its docstring to say it pins the fixed convergence.
  2. Add `test_torn_read_under_serialization_is_terminal_without_traceback`: the peer never finishes (the lock wrapper does not clear the flag). Assert all of the following:
     - `ensure_runtime()` raises `StartupAssetError` that `isinstance(..., RuntimeError)`, with code `asset_torn_read`.
     - Through the real CLI error hook (`typer.testing.CliRunner` or `_run_app_with_error_hook` in-process on the top-level app with a cheap command such as `events --help`): exit code 1, stderr has exactly one `Error:` line, and the output contains no `Traceback`.
     - The same run with `--json` gives one JSON object.

     Read how `main_callback` gates `ensure_runtime` first (some commands skip it).
  3. Add `test_source_drift_torn_read_refused_without_waiting`: inject the alternating state on a **source** path and assert that it raises with code `asset_source_drift` and `machine_file_lock` is never called.

### Subtask T009 – Blast radius, re-pin audit, gates

- **Run:**
  - `make test-fast`, from the main checkout against the lane via `PYTHONPATH`, or the equivalent targeted command.
  - `tests/runtime/` and `tests/specify_cli/runtime/` in full.
  - Every file from `grep -rl "asset_preparation\|ensure_runtime\|ensure_global_agent_commands\|ensure_global_agent_skills\|assess_global_assets\|retry_torn_read" tests/`.
  - `tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py`.
- **Re-pin audit (DIRECTIVE_041):** any test asserting the old retry count, `_TORN_READ_MESSAGE_PREFIX` or `retry_torn_read` is re-pinned to the new behaviour (a stale test gets re-pinned; never delete a valid assertion). Record each one in the Activity Log.
- **Gates:** `ruff check`, `ruff format --check` and `mypy --strict` on the touched files: 0 issues. Complexity ≤ 15 (`ruff check --select C901`).
- **Baseline reds:** classify any red per the CLAUDE.md baseline-red gotcha by running the same test on the planning base via `PYTHONPATH`. Only reds that are red on the lane and green on the base are yours.
- Record commands and pass/fail counts in the Activity Log.

## Test Strategy

This work is required (FR-006/FR-007), so tests are mandatory. Commands (from the lane worktree):

```bash
PY=<repo>/.venv/bin/python
PYTHONPATH=$(pwd)/src PWHEADLESS=1 $PY -m pytest tests/runtime/test_startup_torn_read_escalation.py tests/runtime/test_build_serialized.py -q
PYTHONPATH=$(pwd)/src PWHEADLESS=1 $PY -m pytest tests/runtime tests/specify_cli/runtime -q -p no:cacheprovider
PYTHONPATH=$(pwd)/src $PY -m mypy --strict src/specify_cli/runtime/asset_preparation.py src/specify_cli/runtime/bootstrap.py src/specify_cli/runtime/agent_commands.py src/specify_cli/runtime/agent_skills.py
$PY -m ruff check src/specify_cli/runtime tests/runtime && $PY -m ruff format --check src/specify_cli/runtime tests/runtime
```

## Risks & Mitigations

- **Self-deadlock** on a nested or re-entrant path: guard on `_HELD_LOCKS` before locking (test 4).
- **Second lock authority:** `_serialize_owner` is the only lock-set code, and the C-008 test pins it.
- **Warm regression:** the first build runs unlocked, pinned by the spy test.
- **Hiding source drift:** source-role tears are terminal with no lock (test 5, T008.3).
- **Test fakes too thick** (vacuous red-first): inject only at `node_state` / `machine_file_lock`. A reviewer will reject patches of `assess_*` or of the helper.
- **Commit order:** the reviewer verifies T001's commit is red on the planning base and that T002 is behaviour-preserving. Keep them as separate commits, in order.

## Review Guidance

- Verify red→green: check out the T001 commit's parent (the planning base) and confirm the entry-point test fails with `Asset changed during preparation` for all 3 owners. At WP tip it passes.
- Verify that `recheck_assets` and `build_serialized` both route through `_serialize_owner` (grep). The only other owner-lock `machine_file_lock` site allowed is the documented cold-create exception in `_apply_retained_assets` (R-1).
- Verify that a non-empty `_HELD_LOCKS` makes any torn read terminal (fold 1).
- Verify that `retry_torn_read` and friends are gone, with no dead code.
- Verify that the warm-path spy test exists and asserts 0 locks.
- Verify `StartupAssetError` MRO (`GuardedReadError`, `RuntimeError`) and the CLI no-traceback test in text and `--json`.
- Verify mypy --strict, ruff, format and complexity output in the Activity Log.

## Activity Log

- 2026-09-26T12:10:00Z – system – Prompt created.
- 2026-09-26T13:40:00Z – claude-sonnet-5 (python-pedro) – T001: red-first test committed alone (a20797b6da). RED on the planning base for all 3 owners: `RuntimeError: Asset changed during preparation: …/{runtime_bootstrap,slash_commands,global_skills}-assets.json` (3 failed in 0.56s). It turns GREEN at cf6abb2306 (build_serialized).
- 2026-09-26T13:40:00Z – claude-sonnet-5 (python-pedro) – T002–T009 done. The commits are 96eb2a01b2 (tidy-first _serialize_owner), 44845a1260 (TornReadError), cf6abb2306 (build_serialized + owner swaps + incomplete codes + R-1 comment), 250adb2afe (StartupAssetError), 8cee323e66 (primitive tests), 469db75571 (flip regression → functional; terminal/source-drift CLI tests), and 5f4fa69ac1 (isolate the `_get_app()` `_APP` cache in the CLI-hook tests).
  - Tests: the targeted pair passes 28. `tests/runtime` + `tests/specify_cli/runtime` pass 1151, with 2 skipped and 0 failed. The make test-fast equivalent gives 2045 passed, 5 skipped and 3 failed. Those 3 are in `tests/cli/commands/test_charter_json_error_contract.py`, where "Refusing charter write from linked git worktree" is an artifact of running from a worktree. The grep blast radius gives 357 passed, 21 skipped and 3 failed. All 3 are also red on the base 81b835441b and are tracked in #4916.
  - Architectural spot checks (dead symbols / layer rules / terminology) pass 179.
  - ruff, ruff format and mypy --strict are clean. C901 is ≤15, and `assess_global_agent_commands` gained no branches.
  - Re-pin audit: nothing needed re-pinning. There are no out-of-map edits.
  - Deviation: `StartupAssetError.path` stays None, because `Diagnostic` carries no path. The path is still in the rendered message.
- 2026-09-26T13:45:00Z – claude (orchestrator) – Independently re-verified that the 3 skills-installer reds are red on the true base (worktree at 81b835441b: 3 failed, 88 passed) and are listed in open #4916. Moved to for_review.
- 2026-09-26T15:30:00Z – claude-sonnet-5 (python-pedro) – Review cycle 1 remediation: 81542ec482, 38b90b7597, 8a3f2f7fee, 6b005a1c71.
  - Blocking items 1–6: US3.3 test; 2 inventory observations before the first lock plus a sentinel-first assertion (a mutation probe with an extra unlocked retry now goes RED `4 == 2`); concrete C-008 lists for cold and warm; concrete T007.2 list; skills-path T007.13 with escalation asserted; all 8 suppressions removed.
  - Non-blocking folds 7–9: the INFO line is asserted on the owner logger; the hint depends on the error code; stderr is empty in `--json` mode.
  - Tests: the two new files pass 33. `tests/runtime` + `tests/specify_cli/runtime` give 1156 passed, 2 skipped. Combined `mypy --strict` over 4 src and 2 test files reports 0 errors (18 before). ruff, format and C901 are clean.
- 2026-09-26T15:35:00Z – claude (orchestrator) – Verified the combined mypy run is clean and the diff has no new suppressions. Moved to for_review (cycle 2).
