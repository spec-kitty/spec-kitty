---
work_package_id: "WP01"
title: "Posture core: drain + ledger posture reader, personal writer, test harness fixtures"
dependencies: []
requirement_refs: ["FR-001", "FR-002", "FR-003", "FR-008", "C-002", "C-003"]
subtasks: ["T001", "T002", "T003", "T004", "T005"]
owned_files:
  - "src/specify_cli/core/hosted_posture.py"
  - "src/specify_cli/core/toml_table.py"
  - "src/specify_cli/zeitgeist_client/moments.py"
  - "tests/specify_cli/core/test_hosted_posture.py"
  - "tests/specify_cli/core/test_toml_table.py"
  - "tests/zeitgeist_client/conftest.py"
  - "tests/status/conftest.py"
  - "tests/specify_cli/live_work/conftest.py"
authoritative_surface: "src/specify_cli/core/"
execution_mode: "code_change"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: "claude-sonnet-5"
---

# WP01 — Posture core: drain + ledger posture reader, personal writer, test harness fixtures

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the single pure posture reader `src/specify_cli/core/hosted_posture.py` — `drain_posture()`,
`ledger_posture()`, `require_drain()`, `DrainDisabled`, and the personal-activation writer
`set_personal_drain()` / `set_repo_drain()` — plus a shared atomic TOML-table rewrite helper
extracted from `zeitgeist_client/moments.py`, and the inert test-harness fixtures downstream WPs
depend on. This WP defines the vocabulary (`DrainPosture`, `LedgerPosture`, `DrainDisabled`) that
every other WP in this mission imports; nothing in this WP wires an enforcement edge.

## Context

This is the mission's foundation WP (plan.md D1, revised split table). Per the **Post-plan squad
folds** section of `plan.md` — which supersedes the earlier plan body wherever the two disagree —
this WP owns exactly:

- The posture reader and its two dataclasses (F-1..F-6 assume these types exist).
- The shared TOML-table writer (F-7 minors: "the personal writer reuses a shared atomic TOML table
  rewrite extracted from `moments.write_agents_mode`").
- The drain-posture test fixtures other lanes' test suites need immediately, even though **nothing
  consults posture yet** at WP01 time (F-8).

**Downstream consumers** (not built here, but shaped by what this WP exports):
- WP02 (relay edges) and WP03 (capability + fan-out) call `require_drain()` / `drain_posture()`.
- WP05 (ledger) calls `ledger_posture()`.
- WP04 (arch gate + integration matrix) asserts both postures compose correctly across relay and
  fan-out.
- WP08 (operator surface) calls `set_personal_drain()` / `set_repo_drain()` from
  `spec-kitty moments drain on/off [--repo]`.

**Key design decisions this WP must honor (spec.md, contracts/hosted-posture.md, plan.md):**

- **R-1 (spec.md, plan.md D1)**: no environment variable can *enable* drain in either scope. Only
  `.kittify/config.yaml` → `hosted.drain` (repo) and `<runtime-root>/config.toml` → `[hosted] drain`
  (personal) can turn a scope on. Env vars may only **narrow** (force off) via
  `core/env.py::moment_handlers_disabled_reason()`.
- **Effective drain** (contracts/hosted-posture.md truth table): `enabled == (repo is True and
  personal is True and no env narrower is set)`. Any other combination is off, with a reason naming
  the scope or narrower responsible.
- **Fail-closed parsing** (spec.md Edge Cases, data-model.md): an unparseable config file, or a
  present-but-non-boolean value, counts as **off** for drain (never truthiness-coerced) and as the
  **default (True)** for ledger — both emit exactly one warning per file per process, never a crash.
- **`.kitty.env` / `SPECIFY_REPO_ROOT` redirect cannot enable personal scope** (R-1, spec.md Edge
  Cases: "A committed `.kitty.env` sets any drain-looking environment variable ⇒ ignored"). The
  personal file path is resolved from `specify_cli.paths.get_runtime_root().base`
  (`~/.spec-kitty`, or `SPEC_KITTY_HOME` when set) — never from any repo-relative or `.kitty.env`
  source — so redirecting the repo root cannot make an attacker-controlled directory supply the
  personal activation.
- **No caching (F-7, m1)**: both readers open their two small files on every call. No mtime cache,
  no frozen-at-import value (spec.md Edge Cases: "Drain toggled between two commands in one shell").
- **Repo root resolution (F-7, m3)**: use `specify_cli.core.paths.locate_project_root()` — the
  canonical worktree-aware resolver already used by `moments.locate_repo_root` — not a raw
  `.kittify/` walk.
- **Ledger floor (FR-010, D3 arch guard)**: `ledger_posture` must never be imported from
  `status/store.py`, `status/reducer.py`, `coordination/transaction.py`,
  `coordination/status_transition.py` (except the hook call WP05 adds), `decisions/`, or
  `events/decision_log.py`. This WP does not add any of those imports; keep the module free of them
  so the WP04 arch gate has nothing to catch here.

## Subtask T001: ATDD red-first — failing acceptance tests pinning the contract

**Purpose**: Charter C-011 requires ATDD-first: write and commit failing tests against the contract
*before* `hosted_posture.py` exists, so the first green run is driven by real implementation, not
retrofitted around it.

**Steps**:
1. Create `tests/specify_cli/core/test_hosted_posture.py`. Import `drain_posture`, `ledger_posture`,
   `require_drain`, `DrainDisabled`, `DrainPosture`, `LedgerPosture`, `set_personal_drain`,
   `set_repo_drain` from `specify_cli.core.hosted_posture` — these imports will fail (module does
   not exist yet); that failure **is** the red state. Do not stub the module to make imports pass.
2. Write tests against the truth table in `contracts/hosted-posture.md` verbatim:
   - `repo=True, personal=True, no narrower` → `enabled=True`.
   - `repo=True, personal=True, narrower set` → `enabled=False`, reason names the narrower.
   - `repo=True, personal in {False, absent, invalid}` → `enabled=False`, reason names the personal
     scope.
   - `repo in {False, absent, invalid}, personal=anything` → `enabled=False`, reason names the
     repository scope.
   Build each fixture by writing real files under an isolated `tmp_path` repo (`.kittify/config.yaml`)
   and an isolated `SPEC_KITTY_HOME` (`config.toml`) — do not monkeypatch `drain_posture` itself in
   this file; it is the unit under test.
3. Test **R-1** directly: set an environment variable that looks like it could enable drain (e.g. a
   made-up `SPEC_KITTY_HOSTED_DRAIN=1`, and separately `SPEC_KITTY_SAAS_URL` via a `.kitty.env`-style
   redirect of `SPECIFY_REPO_ROOT`) and assert the effective posture is unchanged — still driven only
   by the two files. Confirm no such env var is even read by asserting posture is identical whether
   the var is set or unset, given the same file contents.
4. Test parse-error and non-bool handling for **both** files independently: malformed YAML in
   `.kittify/config.yaml`, malformed TOML in `config.toml`, `hosted.drain: "yes"` (string, not bool),
   `hosted.drain: 1` (int, not bool) — every case yields `enabled=False` for drain. Assert a warning
   is emitted (`pytest.warns` or caplog) exactly once per call in these cases, and confirm no
   exception propagates.
5. Test the narrowers force off even when both scopes are on: monkeypatch
   `specify_cli.core.env.moment_handlers_disabled_reason` to return a reason string, with repo and
   personal both `True` on disk; assert `enabled=False` and the reason surfaces the narrower's text.
6. Test `ledger_posture`: default `True` when the key is absent; `False` when `ledger.projection:
   false`; default `True` (with a warning) when the value is present but non-boolean (e.g. a string).
7. Test `require_drain("some-context")`: raises `DrainDisabled` (a `RuntimeError` subclass) carrying
   a human-readable message when drain is off; returns `None` (no raise) when drain is on.
8. Run `pytest tests/specify_cli/core/test_hosted_posture.py` and confirm every test fails with a
   collection/import error (module not found) — this is the expected red state.
9. Commit this file alone, before writing any implementation:
   `git add tests/specify_cli/core/test_hosted_posture.py && git commit -m "test(core): red — pin hosted-posture contract before implementation"`.

**Files**: `tests/specify_cli/core/test_hosted_posture.py` (new, ~220–280 lines).

**Validation**: `pytest tests/specify_cli/core/test_hosted_posture.py` fails at collection (import
error) before T003 lands, and the commit exists in `git log` as a standalone red commit.

## Subtask T002: Extract shared atomic TOML-table rewrite

**Purpose**: `zeitgeist_client/moments.py::write_agents_mode` (lines ~372–412) already implements a
correct load–mutate–dump–atomic-rename cycle for a single TOML table key. Extract the generic
mechanics into `src/specify_cli/core/toml_table.py` so `hosted_posture.py`'s personal-drain writer
(T003) does not duplicate it, and `moments.py` keeps working unchanged (behaviour-preserving
refactor, not a rewrite).

**Steps**:
1. Read the current `write_agents_mode` body in
   `src/specify_cli/zeitgeist_client/moments.py:372-412` to confirm the exact sequence: read the
   file with `tomllib.load`, tolerate `FileNotFoundError | tomllib.TOMLDecodeError | OSError` by
   starting from `{}`, coerce the existing table to `dict`, set one key, write the whole document
   with `tomli_w.dump` to a `path.with_suffix(path.suffix + ".tmp")` sibling, then
   `tmp_path.replace(path)` (atomic on POSIX and Windows same-volume) after `path.parent.mkdir(parents=True, exist_ok=True)`.
2. Create `src/specify_cli/core/toml_table.py` with a single public function, e.g.:
   ```python
   def write_toml_table_key(
       path: Path,
       *,
       table: str,
       key: str,
       value: Any,
   ) -> Path:
       """Persist ``[table] key = value`` to ``path``, preserving every other
       key and table in the document, via an atomic load-mutate-dump-rename
       cycle. Returns ``path``. A missing or unparseable file starts from an
       empty document (never raises)."""
   ```
   Preserve the exact tolerance list (`FileNotFoundError, tomllib.TOMLDecodeError, OSError`), the
   `.tmp` suffix convention, `mkdir(parents=True, exist_ok=True)`, and the same-volume atomic
   `replace`. Declare `__all__ = ["write_toml_table_key"]`.
3. Rewrite `moments.py::write_agents_mode` to call `write_toml_table_key(path, table=CONFIG_SECTION,
   key="agents", value=mode.value)` in place of its inline body, keeping its own `scope` ⇒ `path`
   resolution (`repo_config_path` / `global_config_path`) and its return-path contract unchanged.
   Do not change `write_agents_mode`'s public signature or docstring contract.
4. `moments.py` must not gain an import cycle: `core/toml_table.py` has no dependency on
   `zeitgeist_client`, so the import direction is `moments.py -> core.toml_table`, consistent with
   the existing `moments.py -> core.paths` lazy import at `locate_repo_root`.

**Files**: `src/specify_cli/core/toml_table.py` (new, ~45–65 lines);
`src/specify_cli/zeitgeist_client/moments.py` (modified, `write_agents_mode` body only, net ~-25/+5
lines).

**Validation**: `pytest tests/zeitgeist_client -k moments` (or the specific moments test module —
locate it with `grep -rl "write_agents_mode" tests/` if the name differs) passes unchanged; add
`tests/specify_cli/core/test_toml_table.py` covering: fresh file creation, preserving unrelated
tables and keys, overwriting an existing key, and tolerating a corrupt existing file (falls back to
`{}` rather than raising).

## Subtask T003: Implement `src/specify_cli/core/hosted_posture.py`

**Purpose**: The single pure posture reader plus the two dataclasses, the guard function, the
personal/repo writers, and the exception type — the module every other WP imports.

**Steps**:
1. Create `src/specify_cli/core/hosted_posture.py`. Module-level `__all__` listing every public
   name: `DrainPosture`, `LedgerPosture`, `DrainDisabled`, `drain_posture`, `ledger_posture`,
   `require_drain`, `set_personal_drain`, `set_repo_drain`, plus the guidance-line constant (name it
   `DRAIN_GUIDANCE_LINE`, matching contracts/hosted-posture.md's CLI text verbatim: `"Live drain is
   off (<reason>). Enable with: spec-kitty moments drain on [--repo]"` — format the `<reason>` slot
   with `DrainPosture.reason` at the call site or via `.format()`, and keep the message a module
   constant per the CLAUDE.md Sonar S1192 rule since WP02/WP03/WP08 will all reference it).
2. Define the frozen dataclasses per `data-model.md`:
   ```python
   @dataclass(frozen=True)
   class DrainPosture:
       enabled: bool
       repo_value: bool | None
       repo_source: str
       personal_value: bool | None
       personal_source: str
       narrowed_by: str | None
       reason: str

   @dataclass(frozen=True)
   class LedgerPosture:
       enabled: bool
       source: str
   ```
   Invariant to hold in `drain_posture`'s construction (not a runtime-checked `__post_init__` —
   just build it correctly): `enabled == (repo_value is True and personal_value is True and
   narrowed_by is None)`.
3. Define `DrainDisabled(RuntimeError)` — a plain subclass carrying the human-readable message as
   its sole `args[0]`; no extra fields needed (edges will format their own context into the message
   they raise, or reuse `DRAIN_GUIDANCE_LINE.format(reason=posture.reason)`).
4. Implement `drain_posture(project_root: Path | None = None) -> DrainPosture`:
   - Resolve the repo root via `specify_cli.core.paths.locate_project_root(project_root)` when
     `project_root` is `None`, else use `project_root` directly (accepting an already-known root
     lets edge callers that have already resolved it avoid a second walk).
   - Read `.kittify/config.yaml` → `hosted.drain` with a YAML loader consistent with existing
     `.kittify/config.yaml` section-loading patterns in this codebase (check
     `src/specify_cli/context/resolver.py` or `src/specify_cli/config/path_conventions.py` for the
     established reader, and reuse that pattern rather than inventing a new YAML entry point;
     `ruamel.yaml` `YAML(typ="safe")` load is acceptable for a read-only path). A missing file,
     missing key, missing `.kittify/` directory, or unparseable YAML yields `repo_value=None` — treat
     as off, `repo_source` names the path checked. A non-bool value also yields off, with one
     `warnings.warn(...)` call.
   - Read `<runtime-root>/config.toml` → `[hosted] drain` using `tomllib.load` directly (matching
     `moments.py::_read_section`'s tolerance: `FileNotFoundError | IsADirectoryError |
     PermissionError | OSError` ⇒ unset, `tomllib.TOMLDecodeError` ⇒ unset + one warning). Resolve the
     path via `specify_cli.paths.windows_paths.get_runtime_root().base / "config.toml"` — re-export
     or import that helper directly; do **not** duplicate its platform logic.
   - Fold in the env narrower: call `specify_cli.core.env.moment_handlers_disabled_reason()`. If it
     returns a non-`None` reason, set `narrowed_by` to that reason regardless of the two file values.
   - Compute `enabled` and `reason` per the truth table in `contracts/hosted-posture.md`: narrower
     wins first (reason = narrower text), else repo-off wins (reason names repo scope/source), else
     personal-off wins (reason names personal scope/source), else enabled with a reason confirming
     both scopes are on.
   - **No caching**: every call re-reads both files. Do not memoize on `project_root` or mtime.
5. Implement `ledger_posture(project_root: Path | None = None) -> LedgerPosture`:
   - Same repo-root resolution as `drain_posture`.
   - Read `.kittify/config.yaml` → `ledger.projection`; default `True` when absent, missing file, or
     missing `.kittify/`. A parse error or non-bool value also keeps the default `True` and warns
     once. Populate `source` with the file path (or a literal `"default"` string when nothing was
     read).
6. Implement `require_drain(context: str) -> None`: call `drain_posture()` (repo root auto-resolved
   from CWD — edges call this from within an already-repo-rooted process) and raise `DrainDisabled`
   formatted with `context` and the posture's `reason` when `enabled` is `False`; return `None`
   otherwise. Keep this function trivial — it exists so WP02/WP03 have one call site per edge instead
   of re-deriving the posture and the guidance text each time.
7. Implement `set_personal_drain(enabled: bool) -> Path`: resolve
   `get_runtime_root().base / "config.toml"` and call
   `core.toml_table.write_toml_table_key(path, table="hosted", key="drain", value=enabled)` (from
   T002); return the written path.
8. Implement `set_repo_drain(project_root: Path, enabled: bool) -> Path`: ruamel round-trip of
   `project_root / ".kittify" / "config.yaml"`. Load with `YAML(typ="rt")` +
   `preserve_quotes=True` (matching the house convention in `kernel/yaml_io.py::serialize_mapping`)
   so comments and existing keys survive; set `document["hosted"]["drain"] = enabled` (creating the
   `hosted` mapping if absent); dump back atomically — reuse `kernel.yaml_io.write_mapping_atomic`
   if the round-trip document type it accepts (`Mapping[str, Any]`, including `CommentedMap`) fits,
   otherwise write via `YAML(typ="rt").dump` to a temp file + `os.replace` matching the same atomic
   pattern as T002's TOML writer. Return the written path. A missing `.kittify/config.yaml` starts
   from an empty mapping (create the file rather than raising) — `.kittify/` must already exist for
   this to be a Spec Kitty repo; do not create `.kittify/` itself.
9. Keep function bodies at or under complexity 15 (CLAUDE.md ceiling): split repo-YAML-reading,
   personal-TOML-reading, and truth-table resolution into small private helpers
   (`_read_repo_drain_key`, `_read_personal_drain_key`, `_resolve_drain_posture`) rather than one long
   `drain_posture` body. Run `ruff check src/specify_cli/core/hosted_posture.py` to confirm C901 is
   clean.
10. `mypy --strict src/specify_cli/core/hosted_posture.py` must report zero issues. Type every
    public function fully; no bare `Any` return types on the public surface.

**Files**: `src/specify_cli/core/hosted_posture.py` (new, ~180–240 lines).

**Validation**: `pytest tests/specify_cli/core/test_hosted_posture.py` (from T001) passes fully —
this is the ATDD green commit, made as its own commit separate from T001's red commit:
`git commit -m "feat(core): implement hosted drain + ledger posture reader"`. Then
`mypy --strict src/specify_cli/core/hosted_posture.py` and `ruff check
src/specify_cli/core/hosted_posture.py` both report zero issues.

## Subtask T004: Test harness fixtures (F-8)

**Purpose**: Downstream WPs (WP02 relay edges, WP03 capability + fan-out) will call
`require_drain()`/`drain_posture()` at every hosted network edge. Roughly 40 existing relay and
fan-out tests currently assume hosted calls proceed unimpeded; once WP02/WP03 land, those tests
would start failing unless drain is pinned enabled in their fixtures. This subtask lands that
pinning **now**, ahead of the edges that will consult it, so WP02/WP03 land green rather than
red-then-fixed. At WP01 time these fixtures are inert (`hosted_posture.drain_posture` exists but no
call site reads it outside WP01's own tests) — that is expected and correct; do not try to prove
they "do something" yet.

**Steps**:
1. In `tests/zeitgeist_client/conftest.py`, add an **autouse** fixture named `drain_on` that
   monkeypatches `specify_cli.core.hosted_posture.drain_posture` to return an enabled
   `DrainPosture` (construct one directly: `DrainPosture(enabled=True, repo_value=True,
   repo_source="test", personal_value=True, personal_source="test", narrowed_by=None,
   reason="drain enabled (test fixture)")`), so existing relay tests keep passing once WP02 gates
   `NoRedirects.build` behind `require_drain`. Also add a non-autouse `drain_off` fixture (same
   monkeypatch, `enabled=False`, a representative `reason`) for the small number of tests that will
   assert drain-off behaviour directly in WP02/WP03/WP04.
2. Repeat the same two fixtures (`drain_on` autouse, `drain_off` opt-in) in
   `tests/status/conftest.py`, so WP03's fan-out gating in `status/adapters.py` does not break the
   existing status fan-out test suite.
3. Create `tests/specify_cli/live_work/conftest.py` (new file — confirm with
   `ls tests/specify_cli/live_work/` whether a conftest already exists there; if `live_work` tests
   currently live under a different path, e.g. `tests/live_work/`, use `grep -rl "live_work"
   tests/ --include=conftest.py` to find the right location and create the fixture there instead,
   matching wps.yaml's stated path as closely as the real tree allows) with the same `drain_on`
   autouse / `drain_off` opt-in pair, so WP03's live-work publish/authored gating does not break that
   suite either.
4. **Do not write any config file into `SPEC_KITTY_HOME` from these autouse fixtures.** Per
   `tests/conftest.py`'s `canonical_home` fixture contract and the `_home_pin_scan.py` guard: these
   fixtures monkeypatch the `drain_posture` **function** directly (a pure Python monkeypatch), never
   `os.environ["SPEC_KITTY_HOME"]`, never a file under a runtime-root path, and never call
   `set_personal_drain`/`set_repo_drain`. A fixture that materialized `config.toml` under
   `SPEC_KITTY_HOME` would collide with `canonical_home`'s single-owner contract and could be flagged
   by the home-pin scanner as an undeclared home-touching limb.
5. Each new conftest fixture needs a short docstring stating explicitly: "Inert at WP01 time — no
   call site in this codebase yet consults `drain_posture` outside its own unit tests; this fixture
   exists so WP02/WP03/WP05's edge-gating lands without re-pinning ~40 pre-existing tests in the
   same PRs." This is documentation for the next reader (and for the WP04 reviewer), not a test
   assertion.
6. Confirm the fixture is reachable: write one throwaway smoke assertion per conftest file (or reuse
   an existing trivial test in that directory) that imports the fixture by name and asserts
   `hosted_posture.drain_posture().enabled is True` under `drain_on`, then remove the throwaway once
   confirmed working, OR keep a minimal permanent smoke test — implementer's choice, but the fixture
   must be proven to actually patch the right import path (patch
   `specify_cli.core.hosted_posture.drain_posture`, not a local alias, since WP02/WP03 will import
   the module and call `hosted_posture.drain_posture(...)` — confirm the patch target matches how
   WP02/WP03's plan.md D2 table describes each call site).

**Files**: `tests/zeitgeist_client/conftest.py` (modified, +~25 lines);
`tests/status/conftest.py` (modified, +~25 lines);
`tests/specify_cli/live_work/conftest.py` (new or modified, ~25–35 lines, path confirmed against the
live tree per step 3).

**Validation**: the full pre-existing suites in `tests/zeitgeist_client/` and `tests/status/` still
pass unchanged after adding the autouse fixture (it changes nothing yet, since nothing consults
`drain_posture` outside this WP's own tests). `grep -rn "drain_posture\|drain_on\|drain_off"
tests/zeitgeist_client/conftest.py tests/status/conftest.py tests/specify_cli/live_work/conftest.py`
confirms all three files carry the fixtures.

## Subtask T005: Validation

**Purpose**: Confirm the WP is complete, isolated, and does not regress anything outside its owned
files before handing off to WP02/WP03/WP05/WP08.

**Steps**:
1. Run the targeted new/changed test modules:
   `pytest tests/specify_cli/core/test_hosted_posture.py tests/specify_cli/core/test_toml_table.py -v`.
2. Run the moments-specific tests to confirm T002's refactor is behaviour-preserving:
   locate them with `grep -rl "write_agents_mode\|MomentSettings" tests/zeitgeist_client/
   --include="*.py"` and run that module (or the whole `tests/zeitgeist_client/` directory if the
   moments tests are not cleanly separable).
3. Run the two conftest-bearing suites in full to confirm the new autouse fixtures introduce no
   regression: `pytest tests/zeitgeist_client tests/status -q` (and the live_work suite at whatever
   path T004 step 3 confirmed).
4. `ruff check src/specify_cli/core/hosted_posture.py src/specify_cli/core/toml_table.py
   src/specify_cli/zeitgeist_client/moments.py` — zero issues.
5. `ruff format --check src/specify_cli/core/hosted_posture.py src/specify_cli/core/toml_table.py
   src/specify_cli/zeitgeist_client/moments.py tests/specify_cli/core/test_hosted_posture.py
   tests/specify_cli/core/test_toml_table.py` — zero diffs; run `ruff format <files>` if it flags
   anything, then re-check.
6. `mypy --strict src/specify_cli/core/hosted_posture.py src/specify_cli/core/toml_table.py` — zero
   issues. (Do not add `--strict` scope creep to `moments.py`'s existing typing baseline beyond the
   lines T002 touches.)
7. `make test-fast` as the shared baseline (`tests/unit tests/status tests/cli
   tests/specify_cli/runtime`), applying the baseline-red gotcha from CLAUDE.md: attribute any red
   result to pre-existing known-P0s, CI-environment config, or a stale venv/install before treating
   it as caused by this WP's diff.
8. Record every command run and its passed/failed counts under this WP's PR "Tests run" section
   (per CLAUDE.md's test policy) — this WP does not open its own PR (WPs land through the mission's
   lane-based merge), but the same command+count record belongs in the WP's status/implementation
   note so WP04's arch-gate reviewer and the eventual mission PR can cite it.

**Files**: none (validation only — no new files).

**Validation**: all commands in steps 1–7 pass (or every deviation is attributed per the
baseline-red gotcha and noted explicitly, never silently folded).

## Definition of Done

- `tests/specify_cli/core/test_hosted_posture.py` exists, was committed **before** any
  implementation file (a standalone red commit precedes the green implementation commit — verify
  with `git log --oneline -- tests/specify_cli/core/test_hosted_posture.py
  src/specify_cli/core/hosted_posture.py`), and every test in it passes against the finished
  implementation.
- `src/specify_cli/core/hosted_posture.py` exports `DrainPosture`, `LedgerPosture`, `DrainDisabled`,
  `drain_posture`, `ledger_posture`, `require_drain`, `set_personal_drain`, `set_repo_drain`, and
  `DRAIN_GUIDANCE_LINE` via `__all__`; `mypy --strict` and `ruff check` are both clean on it.
- `src/specify_cli/core/toml_table.py` exists with `write_toml_table_key` extracted from
  `moments.py::write_agents_mode`, and `moments.py` calls it instead of duplicating the atomic
  rewrite; the moments test suite is unchanged in behaviour.
- No environment variable, `.kitty.env` entry, or `SPECIFY_REPO_ROOT` redirect can flip either
  drain scope on — proven by a dedicated test in T001, not just asserted in prose.
- Parse errors and non-boolean values fail closed for drain (off) and fail to the documented default
  for ledger (on), each with exactly one warning, never an unhandled exception.
- `drain_on`/`drain_off` fixtures exist in `tests/zeitgeist_client/conftest.py`,
  `tests/status/conftest.py`, and the live_work test tree's conftest, each documented as currently
  inert, and none of them write into `SPEC_KITTY_HOME` or otherwise collide with the
  `canonical_home` single-owner contract.
- `ledger_posture` and `drain_posture` are not imported, directly or transitively through this WP's
  own new files, from `status/store.py`, `status/reducer.py`, `coordination/transaction.py`,
  `coordination/status_transition.py`, `decisions/`, or `events/decision_log.py` (this WP does not
  touch those files at all, so this should hold trivially — confirm with
  `grep -rn "hosted_posture" src/specify_cli/status/store.py src/specify_cli/status/reducer.py
  src/specify_cli/coordination/transaction.py src/specify_cli/coordination/status_transition.py
  src/specify_cli/decisions/ src/specify_cli/events/decision_log.py` returning nothing).
- `make test-fast` plus every targeted/blast-radius command in T005 is run and its exact
  command + pass/fail counts are recorded.

## Risks

- **Wrong config-loading pattern for `.kittify/config.yaml`.** The codebase has several YAML
  section-reading conventions; picking an inconsistent one for `hosted.drain`/`ledger.projection`
  would create a second de facto config-loading pattern (violates C-003, "reuse the existing
  config-loading patterns; no new config file format"). Mitigation: T003 step 4 explicitly directs
  the implementer to locate and match the established reader before writing a new one.
- **Personal-file path drift.** D-5 requires the personal activation in the **runtime root**
  (`~/.spec-kitty`, `specify_cli.paths.windows_paths.get_runtime_root()`), not
  `kernel.paths.get_kittify_home()` (`~/.kittify`, where `[moments]` lives). These are two genuinely
  different directories on POSIX. Getting this wrong silently breaks R-1's isolation guarantee, since
  the wrong home might be more easily redirected. Mitigation: T003 step 4 names the exact function
  and rejects reuse of `moments.py`'s `global_config_path`.
- **Fixture patch target mismatch.** If T004's fixtures monkeypatch a different import path than the
  one WP02/WP03 actually call (e.g. patching `hosted_posture.drain_posture` when an edge does
  `from specify_cli.core.hosted_posture import drain_posture` and calls the bound local name), the
  fixture silently does nothing and WP02/WP03 will discover ~40 test failures despite this WP
  "passing." Mitigation: T004 step 6 requires a proof-of-patch smoke check, and WP02/WP03's own
  authors should re-verify the patch target against their actual call-site import style once
  written.
- **Complexity/mypy churn on the truth-table function.** Five inputs (repo value/source, personal
  value/source, narrower) collapsing to one reason string is exactly the kind of function that drifts
  toward the C901=15 ceiling. Mitigation: T003 step 9 requires splitting into small named helpers
  up front rather than refactoring under a red `ruff check` later.

## Reviewer Guidance

- Confirm the git history shows a **separate red commit** for
  `tests/specify_cli/core/test_hosted_posture.py` before the implementation commit — this is a
  charter C-011 (ATDD-first) hard requirement, not a style preference.
- Re-derive the truth table from `contracts/hosted-posture.md` yourself against the test file; do
  not just check that tests pass — check that the four rows are each represented by at least one
  test, plus the parse-error/non-bool/narrower edge cases from spec.md's Edge Cases section.
- Verify the personal-drain path is genuinely `specify_cli.paths.windows_paths.get_runtime_root().base
  / "config.toml"` and not `kernel.paths.get_kittify_home()` — grep the implementation for which
  function it calls.
- Verify `write_toml_table_key` is a faithful, behaviour-preserving extraction: diff the old
  `write_agents_mode` body against the new call-through, and confirm the moments test suite result is
  unchanged (same tests, same pass count, before and after).
- Verify the new conftest fixtures do not write anything under `SPEC_KITTY_HOME` — read them, don't
  just trust the docstring.
- Verify no new import edge from this WP's files into `status/store.py`, `status/reducer.py`,
  `coordination/transaction.py`, `coordination/status_transition.py`, `decisions/`, or
  `events/decision_log.py` — this WP shouldn't touch those at all.
- Confirm `mypy --strict` and `ruff check`/`ruff format --check` are clean on every new/modified file
  in this WP, and that the recorded `make test-fast` + targeted command output is present and
  legible.

## Implementation

```bash
spec-kitty agent action implement WP01 --agent claude
```
