---
work_package_id: WP01
title: 'Posture core: drain + ledger posture reader, personal writer, root test-harness fixture'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- C-002
- C-003
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- src/specify_cli/core/hosted_posture.py
- src/specify_cli/core/toml_table.py
- tests/specify_cli/core/test_hosted_posture.py
- tests/specify_cli/core/test_toml_table.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/hosted_posture.py
- src/specify_cli/core/toml_table.py
- src/specify_cli/zeitgeist_client/moments.py
- tests/specify_cli/core/test_hosted_posture.py
- tests/specify_cli/core/test_toml_table.py
- tests/conftest.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Posture core: drain + ledger posture reader, personal writer, root test-harness fixture

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
extracted from `zeitgeist_client/moments.py`, and the ONE root-level autouse drain fixture in
`tests/conftest.py` (plus the `real_drain_posture` opt-out marker and a `drain_off` fixture) that
every downstream WP's test suite depends on. This WP defines the vocabulary (`DrainPosture`, `LedgerPosture`, `DrainDisabled`) that
every other WP in this mission imports; nothing in this WP wires an enforcement edge.

## Context

This is the mission's foundation WP (plan.md D1, revised split table). Per the **Post-plan squad
folds** section of `plan.md` — which supersedes the earlier plan body wherever the two disagree —
this WP owns exactly:

- The posture reader and its two dataclasses (F-1..F-6 assume these types exist).
- The shared TOML-table writer (F-7 minors: "the personal writer reuses a shared atomic TOML table
  rewrite extracted from `moments.write_agents_mode`").
- The root drain-posture test fixture every test in the suite runs under (post-tasks fold O1,
  superseding F-8's three per-directory conftests), even though **nothing consults posture yet**
  at WP01 time.

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
- **No caching (F-7, m1)**: both readers open their two small files on every call (NFR-003: at
  most 2 config files per posture evaluation). No mtime cache, no frozen-at-import value (spec.md
  Edge Cases: "Drain toggled between two commands in one shell").
- **Lazy `ruamel.yaml` import**: `drain_posture()` sits on the hot path of every lane transition;
  import `ruamel.yaml` inside the repo-key reader (after the `.kittify/config.yaml` existence
  check), never at module top level, so a repo without the file pays no YAML import cost.
- **Call-site style (fixture effectiveness)**: downstream call sites must reach the reader through
  the module attribute (`from specify_cli.core import hosted_posture` → `hosted_posture.drain_posture()`)
  or through `require_drain(...)` (which resolves `drain_posture` from module globals at call time).
  A `from specify_cli.core.hosted_posture import drain_posture` local binding would bypass the root
  fixture's monkeypatch. State this in the module docstring.
- **Strict personal writer (post-tasks fold D7)**: the runtime-root `config.toml` also carries
  `[sync].server_url` (the hosted endpoint). `set_personal_drain` must **refuse** (raise, write
  nothing) when that file exists but is unparseable, rather than start from an empty document and
  silently drop the endpoint.
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
   this file; it is the unit under test. Mark these tests `@pytest.mark.real_drain_posture` (class-
   or function-level, so T004 step 6's proof-of-patch tests can live in the same file without it)
   so the root autouse fixture from T004 does not replace the reader under test.
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
7a. **D7 strict writer**: (i) with a pre-existing runtime-root `config.toml` holding `[sync]
   server_url = "https://example.test"` plus another table, call `set_personal_drain(True)` then
   `set_personal_drain(False)` and assert `[sync].server_url` and the other table survive both
   toggles unchanged; (ii) with an unparseable `config.toml`, assert `set_personal_drain(True)`
   raises a typed error (pick and document one — e.g. re-raise `tomllib.TOMLDecodeError`, or a
   small `ValueError` subclass named in `__all__` and caught by WP08's CLI) and the file's bytes are
   unchanged afterwards.
8. Run `pytest tests/specify_cli/core/test_hosted_posture.py` and confirm every test fails with a
   collection/import error (module not found) — this is the expected red state.
9. Commit this file alone, before writing any implementation:
   `git add tests/specify_cli/core/test_hosted_posture.py && git commit -m "test(core): red — pin hosted-posture contract before implementation"`.

**Files**: `tests/specify_cli/core/test_hosted_posture.py` (new, ~240–300 lines).

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
   Add a keyword-only `strict: bool = False` parameter (D7): with `strict=False` (the default, used
   by `moments.write_agents_mode`) behaviour is byte-identical to today; with `strict=True` a
   present-but-unparseable file (`tomllib.TOMLDecodeError`) or an unreadable one (`OSError` other
   than `FileNotFoundError`) raises and nothing is written. Only `FileNotFoundError` starts from
   `{}` in strict mode.
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
tables and keys, overwriting an existing key, tolerating a corrupt existing file with the default
`strict=False` (falls back to `{}` rather than raising — today's `moments` behaviour), and
`strict=True` raising on a corrupt file with its bytes unchanged.

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
     `ruamel.yaml` `YAML(typ="safe")` load is acceptable for a read-only path; import it **lazily**
     inside this helper, after the file-exists check). A missing file,
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
   `core.toml_table.write_toml_table_key(path, table="hosted", key="drain", value=enabled, strict=True)`
   (from T002; `strict=True` per D7 — never clobber an unparseable file that also carries
   `[sync].server_url`); return the written path.
8. Implement `set_repo_drain(project_root: Path, enabled: bool) -> Path` (this exact signature —
   WP08 calls it as `set_repo_drain(project_root, enabled)`): ruamel round-trip of
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
11. **Non-test caller map (S1)** — every public name this WP adds must gain a non-test `src/`
    caller before the mission merges (`tests/architectural/test_no_dead_symbols.py`). Record this
    map in the module docstring so a reviewer can check it: `write_toml_table_key` →
    `zeitgeist_client/moments.py` + this module (WP01); `require_drain`, `DrainDisabled`,
    `DRAIN_GUIDANCE_LINE` → `cli/commands/zeitgeist.py`, `zeitgeist_client/transport.py` (WP02);
    `drain_posture` → `status/adapters.py`, `cli/commands/routes.py` (WP03); `ledger_posture` →
    `status/emit.py` (WP05); `set_personal_drain`, `set_repo_drain`, `DrainPosture`,
    `LedgerPosture` (and D7's error type, if one is added) → `cli/commands/moments.py` (WP08).

**Files**: `src/specify_cli/core/hosted_posture.py` (new, ~180–240 lines).

**Validation**: `pytest tests/specify_cli/core/test_hosted_posture.py` (from T001) passes fully —
this is the ATDD green commit, made as its own commit separate from T001's red commit:
`git commit -m "feat(core): implement hosted drain + ledger posture reader"`. Then
`mypy --strict src/specify_cli/core/hosted_posture.py` and `ruff check
src/specify_cli/core/hosted_posture.py` both report zero issues.

## Subtask T004: Root test-harness fixture (post-tasks fold O1, supersedes F-8's per-directory conftests)

**Purpose**: Downstream WPs gate every hosted edge and automatic path on drain. Once they land, any
existing test in the suite that exercises a now-gated path (status fan-out, relay, live-work,
runtime moments, widen prereqs, decisions …) would flip red unless drain is pinned enabled. Three
per-directory conftests (the F-8 plan) would miss every test outside those three directories, so
this WP lands ONE root-level autouse fixture in `tests/conftest.py` now, ahead of the edges that
will consult it. At WP01 time it is inert (nothing outside WP01's own tests reads
`drain_posture`) — that is expected.

**Steps**:
1. In `tests/conftest.py`, add an **autouse**, function-scoped fixture (e.g. `_drain_posture_enabled`)
   that monkeypatches the module attribute `specify_cli.core.hosted_posture.drain_posture` to
   return an enabled `DrainPosture(enabled=True, repo_value=True, repo_source="test",
   personal_value=True, personal_source="test", narrowed_by=None, reason="drain enabled (test
   fixture)")`. Import `specify_cli.core.hosted_posture` lazily inside the fixture body so
   collection cost stays flat.
2. **Opt-out marker**: when the requesting test carries the `real_drain_posture` marker
   (`request.node.get_closest_marker("real_drain_posture")`), the fixture does nothing, so the real
   file-based reader runs. Register the marker in the **existing** `pytest_configure` in
   `tests/conftest.py` via `config.addinivalue_line("markers", "real_drain_posture: opt out of the
   autouse drain-enabled fixture; the real file-based drain_posture reader runs")` — the same
   pattern as `real_worktree_detection`. Do **not** edit `pytest.ini`.
3. Add a non-autouse `drain_off` fixture in `tests/conftest.py` that re-patches the same attribute
   with an off posture (`enabled=False`, `repo_value=None`, a representative `reason`, e.g.
   `"repository scope is off (test fixture)"`). It must win over the autouse fixture regardless of
   fixture ordering (depend on the autouse fixture by name inside `drain_off`, then re-patch).
4. **Do not write any config file into `SPEC_KITTY_HOME`** from these fixtures: they monkeypatch the
   `drain_posture` function only — never `os.environ["SPEC_KITTY_HOME"]`, never a file under a
   runtime-root path, never `set_personal_drain`/`set_repo_drain` — so they cannot collide with
   `canonical_home`'s single-owner contract or the `_home_pin_scan.py` guard.
5. Docstrings: state that the fixture is inert at WP01 time and exists so WP02/WP03/WP05's
   gating lands without re-pinning pre-existing tests; name the `real_drain_posture` marker
   (WP01's posture tests and WP04's real-default and matrix tests use it) and the `drain_off`
   fixture.
6. Prove the patch target: in `tests/specify_cli/core/test_hosted_posture.py`, add two small tests
   **without** the marker: one asserting `hosted_posture.drain_posture().enabled is True` and
   `hosted_posture.require_drain("x")` does not raise under the autouse fixture; one asserting both
   flip under `drain_off`.

**Files**: `tests/conftest.py` (modified, +~45 lines); small additions to
`tests/specify_cli/core/test_hosted_posture.py`.

**Validation**: `pytest tests/specify_cli/core/test_hosted_posture.py -v` green (marker-gated tests
use the real reader; the proof-of-patch tests see the fixture). Because `tests/conftest.py` is
cross-cutting (CLAUDE.md blast-radius rule 3), T005 also runs `tests/architectural/` in full.

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
3. Run the suites the root fixture most directly affects to confirm it introduces no regression:
   `pytest tests/zeitgeist_client tests/status tests/specify_cli/live_work -q`.
3a. `tests/conftest.py` is cross-cutting ⇒ run `pytest tests/architectural/ -q` in full (it
   includes `tests/architectural/test_no_dead_symbols.py`). At WP01 time the dead-symbol gate is
   **expected** to flag the symbols whose callers land in later WPs (T003 step 11's map); record
   that exact list as "in-flight, caller in WP0x" — do not allowlist them and do not add fake
   callers. Classify every other red per the baseline-red gotcha.
4. `ruff check src/specify_cli/core/hosted_posture.py src/specify_cli/core/toml_table.py
   src/specify_cli/zeitgeist_client/moments.py` — zero issues.
5. `ruff format --check src/specify_cli/core/hosted_posture.py src/specify_cli/core/toml_table.py
   src/specify_cli/zeitgeist_client/moments.py tests/specify_cli/core/test_hosted_posture.py
   tests/specify_cli/core/test_toml_table.py tests/conftest.py` — zero diffs; run `ruff format <files>` if it flags
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
- One root autouse drain-enabled fixture, the `real_drain_posture` opt-out marker (registered in
  `tests/conftest.py::pytest_configure`, not `pytest.ini`) and a `drain_off` fixture exist in
  `tests/conftest.py`, proven to patch `specify_cli.core.hosted_posture.drain_posture`, and none of
  them writes into `SPEC_KITTY_HOME` or collides with the `canonical_home` single-owner contract.
- `set_personal_drain` refuses to overwrite an unparseable runtime-root `config.toml` (bytes
  unchanged) and preserves `[sync]` across drain toggles (D7), proven by tests.
- `tests/architectural/` was run in full (cross-cutting `tests/conftest.py`); the in-flight
  dead-symbol list is recorded.
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
- **Fixture patch target mismatch.** If a downstream edge does
  `from specify_cli.core.hosted_posture import drain_posture` and calls the bound local name, the
  root fixture's module-attribute patch silently does nothing for that call site. Mitigation: the
  call-site style rule in Context (module attribute or `require_drain` only), the proof-of-patch
  tests in T004 step 6, and WP04's arch gate (which matches `require_drain`/`drain_posture` calls).
- **Root fixture scope.** An autouse fixture in `tests/conftest.py` touches every test. Keep it a
  pure monkeypatch with a lazy import (no I/O), and run `tests/architectural/` in full.
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
- Verify the root fixture in `tests/conftest.py` does not write anything under `SPEC_KITTY_HOME`
  — read it, don't just trust the docstring — and that `real_drain_posture` is registered in
  `pytest_configure`, not `pytest.ini`.
- Verify `set_personal_drain` uses `strict=True` and that `write_toml_table_key`'s default stays
  byte-compatible with the old `write_agents_mode` behaviour.
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
