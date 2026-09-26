---
work_package_id: WP03
title: 'Capability + fan-out: gateway method gates, resolve_* pre-cache check, adapters, runtime producer, live-work, routes'
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-006
- NFR-001
- NFR-003
- C-004
- C-005
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 1 - Capability + fan-out
history:
- timestamp: '2026-09-26T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: python-pedro
authoritative_surface: src/specify_cli/zeitgeist_client/
create_intent:
- tests/zeitgeist_client/test_drain_capability.py
- tests/status/test_drain_fanout.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/zeitgeist_client/resolution.py
- src/specify_cli/status/adapters.py
- src/specify_cli/events/runtime_moments.py
- src/specify_cli/live_work/**
- src/specify_cli/retrospective/lifecycle_events.py
- src/specify_cli/cli/commands/routes.py
- src/specify_cli/cli/commands/live_work.py
- tests/zeitgeist_client/test_drain_capability.py
- tests/status/test_drain_fanout.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Capability + fan-out: gateway method gates, resolve_* pre-cache check, adapters, runtime producer, live-work, routes

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Gate every SaaS-capability and fan-out/producer/live-work automatic egress path behind the drain
posture WP01 defines, so that with drain off nothing is sent, no cached credential is read, and no
worker thread is spawned — while drain on reproduces today's behaviour byte-for-byte. Also gate the
one operator-typed command in this WP's surface (`spec-kitty routes`) that can mint a capability.

## Context

This mission (`hosted-opt-in-drain-ledger-01M3FFEV`) reverses the always-on hosted drain: nothing
may leave the machine unless the repository (`hosted.drain` in `.kittify/config.yaml`) **and** the
developer (`[hosted] drain` in the runtime-root `config.toml`) both opt in (FR-001–FR-003). WP01
(dependency, already merged into your branch when you start) ships
`src/specify_cli/core/hosted_posture.py` with:

- `drain_posture(project_root: Path | None = None) -> DrainPosture` — effective boolean + per-scope
  provenance, fail-closed on any parse failure.
- `require_drain(context: str) -> None` — raises `DrainDisabled` with a one-line reason when the
  effective posture is off; a no-op when it is on. Read per call, never frozen at import.
- `DrainDisabled(RuntimeError)` — carries the human-readable reason (`str(exc)`).
- A guidance constant used ≥3× by CLI/MCP surfaces:
  `"Live drain is off (<reason>). Enable with: spec-kitty moments drain on [--repo]"` — check the
  exact exported name (e.g. `DRAIN_GUIDANCE_TEMPLATE`) in `hosted_posture.py` and reuse it verbatim;
  do not hand-roll a second copy of this string (Sonar S1192).
- Autouse `drain_on` fixtures (drain forced **on**) plus a paired `drain_off` fixture in
  `tests/zeitgeist_client/conftest.py`, `tests/status/conftest.py` and
  `tests/specify_cli/live_work/conftest.py` — WP01 chose "on" as the autouse default so that the
  ~55–60 existing tests across these trees, written before this mission, keep passing unmodified;
  you opt a test **into** the drain-off behaviour explicitly with `drain_off`.

Sibling WP02 (parallel, also depends on WP01 only) gates the relay opener
(`zeitgeist_client/budget.py::NoRedirects.build`) and the CLI/MCP-facing subscription commands. This
WP (WP03) gates the **other** egress family: the SaaS capability gateway, the three status fan-out
wrappers, the runtime-moment producer, live-work publishing, and the one minting CLI command
(`routes`) in this WP's ownership. WP04 (downstream, depends on WP02+WP03+WP05) writes the
non-vacuous architectural gate and the {ledger}×{drain} integration matrix over both WPs' edges —
you are not responsible for that test file, but your gate calls are exactly what it will assert
against, so name your `require_drain(...)` context strings clearly (`"capability"` is specified
below; do not invent a different string per call site).

**Squad-superseding decisions that apply here (plan.md "Post-plan squad folds", read in full before
starting — F-2 in particular supersedes the original D2 table for this WP):**

- **F-2 (gateway gate placement).** Gate inside `SaasCapabilityGateway.check_repo_admission` and
  `mint_capability`, **not** `__init__`. The constructor must stay ungated because tests build a
  gateway with the `_http=` seam (an injected fake `httpx.Client`) and then assert on the gated
  methods; gating `__init__` would break that seam and also gate object construction that itself
  makes no network call.
- **F-2.** `resolve_credentials`, `resolve_focus_capability` (and therefore the `resolve_focus_lease`
  composite that calls it) return `None` **before** any cache read (`credentials.load` /
  `cached_answer`) when drain is off, and log a debug reason of exactly `drain-off` (distinguishable
  from the existing "no relay credentials" / "no canonical identity" debug reasons — see #4322,
  cross-linked in Reviewer Guidance).
- **F-2.** `spec-kitty routes` is drain-gated as well as endpoint-gated, because it can mint; when
  drain is off it must print "Live drain is off…", not attempt the gateway call and surface a raw
  traceback or a misleading "Team Kitty unreachable".
- **F-3 (projection hook, not this WP's file set — informational only).** `refresh_execution_projection`
  is WP05's responsibility; do not add it here. `emit.py`/`coordination/status_transition.py` are
  WP05-owned files.
- **C-004 (layering).** `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.
  `src/specify_cli/events/runtime_moments.py` lives in `specify_cli`, so importing
  `specify_cli.core.hosted_posture` from it is fine. Do **not** touch anything under
  `src/runtime/next/_internal_runtime/` (e.g. `events.py`) — the producer's `_publish`/
  `_publish_journalled` methods already live in `specify_cli.events`, which is where your change
  goes.
- **C-002 (sync stays dead).** Do not read or reuse `SPEC_KITTY_ENABLE_SAAS_SYNC`,
  `SPEC_KITTY_SYNC_*`, or introduce any new `SYNC_`/`SAAS_`/`TEAMSPACE` identifier. The existing
  `moment_handlers_disabled_reason()` kill-switch check (`core/env.py`, read at import in
  `status/adapters.py:384` and per-call elsewhere) is a **narrower**, not the drain gate — it stays
  exactly where it is; drain composes with it, never replaces it.
- **C-005 (#4311 coupling).** A live-publish retry (present or future) must sit behind the same
  drain gate; drain-off is a clean, silent skip, never a diagnostic-as-error. None of the fan-out
  functions you touch may start raising where they did not before.

## Subtasks

### Subtask T011: ATDD red-first — write the failing drain tests first

**Purpose**: Lock in every behaviour this WP must produce as executable tests *before* touching
production code (charter ATDD-first discipline). Land this as a separate, first commit so the
red→green delta is visible in review.

**Steps**:
1. Create `tests/zeitgeist_client/test_drain_capability.py`. Using the `drain_off` fixture from
   WP01's `tests/zeitgeist_client/conftest.py`, assert:
   - `SaasCapabilityGateway(base_url, token, _http=<fake>).check_repo_admission(...)` raises
     `DrainDisabled` and the fake `_http` client records **zero** calls (constructing the gateway
     itself must still succeed — the `_http=` seam is not gated).
   - The same for `.mint_capability(...)`.
   - `resolution.resolve_credentials(cwd)`, `resolution.resolve_focus_capability(cwd)`, and
     `resolution.resolve_focus_lease(cwd)` all return `None` with drain off, *and* that the
     underlying credential store is never read — patch `specify_cli.zeitgeist_client.credentials.load`
     (and `cached_answer` if it is a separate seam) with a `Mock` and assert `assert_not_called()`.
   - Caplog captures a debug record containing the literal token `drain-off` for each of the three
     `resolve_*` calls.
   - An **already-cached** credential (write one via the store's own `set`/`store` helper first)
     plus `drain_off` still yields `None` and no cache read observably drives any further action —
     this is spec.md US1-AS2 ("developer was previously logged in and holds a cached relay
     credential ... drain is off ... the cached credential is not used and nothing is sent").
   - With the paired `drain_on` fixture (or simply not applying `drain_off`, since WP01's autouse
     default is on), the same calls behave exactly as they do on `main` today (a green baseline
     regression guard, not new behaviour).
2. Create `tests/status/test_drain_fanout.py`. Using `drain_off` from
   `tests/status/conftest.py`, assert for each of `fire_saas_fanout`, `fire_resolved_binding_fanout`,
   `fire_lifecycle_saas_fanout`:
   - Register a spy handler via the module's existing registration seam
     (`ensure_zeitgeist_moment_handlers` / the handler-list append your test can reach — follow the
     pattern the existing `tests/status/` fan-out tests already use for handler registration/reset).
   - Call the `fire_*` function with representative kwargs and assert the spy handler is **never**
     invoked and no thread is spawned (inspect `threading.active_count()` before/after, or patch the
     bounded-runner seam `_run_fanout_handler_bounded` with a `Mock` and assert `assert_not_called()`).
   - With `drain_on`, the spy **is** called exactly once per fire (unchanged baseline).
3. In the same file (or a clearly named sibling test module under `tests/status/` if the runtime
   producer's own conftest differs), assert the runtime moment producer
   (`specify_cli.events.runtime_moments.RuntimeMomentProducer`) publishes nothing under `drain_off`:
   patch `find_run_journal`/`latest_matching_record` (or `fire_lifecycle_saas_fanout` itself) with a
   `Mock` and assert it is never reached/called when `_publish` runs with drain off.
4. Extend (or add alongside) `tests/specify_cli/live_work/` coverage — using
   `tests/specify_cli/live_work/conftest.py`'s `drain_off` — asserting: `publish_observations(...)`
   returns a `PublishReport` whose every entry is dropped with a reason naming drain (not "no relay
   credentials"), `resolution.resolve_credentials` is never called (patch and assert
   `assert_not_called()`); `authored._publish(...)` raises its typed `AuthoredMessageError` (not an
   unguarded `DrainDisabled`) naming drain in the message; and
   `retrospective.lifecycle_events._fanout_live_work_retrospective` returns without calling
   `publish_observations` (patch it and assert `assert_not_called()`).
5. Add one test to `tests/cli/commands/` (an existing test module for `routes` if one exists, else a
   focused addition) asserting `spec-kitty routes` with drain off prints "Live drain is off" (not a
   traceback, not "Team Kitty unreachable") and exits 0 or the same non-error code the "no
   accessible route" branch already uses — check the existing `_fail`/exit-code convention in
   `cli/commands/routes.py` and match it rather than inventing a new one.
6. Run the whole new set: every test above MUST fail (red) against the current `main` tree, because
   `hosted_posture` gate calls do not exist yet in this WP's files. Commit this file set alone —
   `git commit` with a message naming it ATDD red — before starting T012.

**Files**: `tests/zeitgeist_client/test_drain_capability.py` (new, ~150 lines),
`tests/status/test_drain_fanout.py` (new, ~120 lines), plus small additions under
`tests/specify_cli/live_work/` and `tests/cli/commands/`.

**Validation**: `pytest tests/zeitgeist_client/test_drain_capability.py tests/status/test_drain_fanout.py -q`
shows every new test failing for the *expected* reason (no gate raised / handler still called),
not an import error or fixture-not-found error. Fix fixture wiring (confirm WP01's `drain_off`
fixture name and import path) before treating a failure as "correctly red".

---

### Subtask T012: Gate `resolution.py` — gateway methods and the three `resolve_*` pre-cache checks

**Purpose**: Close the two vectors R1 in research.md names: an ungated `SaasCapabilityGateway` HTTP
call, and a cached-credential read that happens before any drain check.

**Steps**:
1. Import `from specify_cli.core.hosted_posture import DrainDisabled, require_drain` (adjust to the
   real exported names from WP01 — read `src/specify_cli/core/hosted_posture.py` first; the plan's
   working names are `drain_posture()`, `require_drain(context: str) -> None`, `DrainDisabled`).
2. In `SaasCapabilityGateway.check_repo_admission` (currently `~185-206` — the method opening the
   `try: resp = self._http.get(...)` block) and `mint_capability` (currently `~213-241` — the
   `try: resp = self._http.post(...)` block), add `require_drain("capability")` as the **first**
   statement in each method body, before any `self._http` call. Do **not** add it to `__init__`
   (F-2 — the `_http=` test seam and gateway construction stay ungated).
3. In `resolve_credentials` (currently `~571`), add the drain check immediately after the function's
   own docstring/argument handling and **before** the `cached_answer(...)` call (currently around
   `~625-628`). On drain off: `logger.debug("zeitgeist credentials: drain-off (%s)", cwd_str)` then
   `return None`. Use the literal substring `drain-off` in the debug message so T011's caplog
   assertion matches.
4. In `resolve_focus_capability` (currently `~647`), add the identical check before its own
   `credentials.load(repo=key)` call (currently `~698`) — note this function derives `key` via
   `repo_identity.origin_url`/`repo_slug_and_host` first; keep those calls (they raise no network
   I/O, only local git reads) but gate before the `credentials.load` line specifically, since that is
   the actual cache/store read this closes. Use the same `drain-off` debug substring.
5. `resolve_focus_lease` (currently `~758`) calls `resolve_focus_capability` first and returns
   `None` immediately when that returns `None` — no separate gate needed here; verify this by
   tracing the call, and add a one-line comment noting it inherits the gate rather than duplicating
   `require_drain`.
6. Do not change `_default_gateway`, `cached_answer`, `_same_scope`, `store_key`, or any dataclass
   shape — this subtask only adds early-return gates.

**Files**: `src/specify_cli/zeitgeist_client/resolution.py` (modified, ~6 new lines across 4 sites).

**Validation**: T011's `test_drain_capability.py` assertions for `check_repo_admission`,
`mint_capability`, `resolve_credentials`, `resolve_focus_capability`, and `resolve_focus_lease` all
turn green. Re-run with `drain_on` (or no override) and confirm the pre-existing
`tests/zeitgeist_client/` suite for this module is unaffected (same pass count as on `main`).

---

### Subtask T013: Gate `status/adapters.py` — the three fan-out functions, per call

**Purpose**: Stop `fire_saas_fanout`, `fire_resolved_binding_fanout`, and `fire_lifecycle_saas_fanout`
from spawning a handler thread when drain is off, without touching the existing import-time
kill-switch registration gate.

**Steps**:
1. Import `require_drain`/`DrainDisabled` (or a boolean-returning `drain_posture(...).enabled` check
   — pick whichever reads more naturally at a call site that must stay silent, not raise; a `try/except
   DrainDisabled: return` wrapping the whole function body, or a leading
   `if not drain_posture().enabled: return` are both acceptable — match whichever idiom WP01's own
   docstring/tests recommend).
2. Add the check as the **first statement** in `fire_saas_fanout` (currently `~263`), before the
   existing `_fanout_force`/`logger.info` breadcrumb call — so a drain-off invocation logs nothing
   and loops over zero handlers, never touching `_run_fanout_handler_bounded`. Keep the breadcrumb
   log call for the drain-**on** path exactly as it is today.
3. Repeat for `fire_resolved_binding_fanout` (currently `~319`) and `fire_lifecycle_saas_fanout`
   (currently `~355`), each as the first statement in the function body.
4. **Do not touch** the module-level import-time gate at the bottom of the file
   (`if moment_handlers_disabled_reason() is None: ensure_zeitgeist_moment_handlers()`, currently
   `~384-385`). That gate controls whether a *handler is registered at all* (the
   `SPEC_KITTY_NO_MOMENT_HANDLERS` / `SPEC_KITTY_SYNC_DISABLE` narrower); drain is evaluated **per
   call**, independently, inside each `fire_*` function — the two gates compose (either one silences
   fan-out) and neither replaces the other.
5. Add a one-line comment at each new gate noting it composes with, and does not replace, the
   import-time kill-switch gate — a future reader must not "simplify" this into one check.

**Files**: `src/specify_cli/status/adapters.py` (modified, ~9 new lines across 3 sites).

**Validation**: T011's `test_drain_fanout.py` turns green for all three functions under `drain_off`
and stays green (unchanged behaviour) under `drain_on`. Confirm
`tests/status/test_adapters*.py` (or wherever the existing fan-out suite lives) still passes at the
same count.

---

### Subtask T014: Skip the runtime-moment producer when drain is off

**Purpose**: Avoid the journal lookup and the `fire_lifecycle_saas_fanout` call entirely when drain
is off — the producer would otherwise still spend NFR-003's "no wasted work" budget on
`find_run_journal`/`latest_matching_record` even though the downstream fan-out (gated in T013)
would drop the frame anyway.

**Steps**:
1. In `src/specify_cli/events/runtime_moments.py`, add the drain check inside `_publish` (currently
   `~211-218`), as the first statement inside the `try:` block (or immediately before it, matching
   whichever placement keeps the existing `except Exception` warning-log behaviour for genuine
   failures distinct from the deliberate skip — a deliberate drain-off skip should **not** log a
   warning; only unexpected failures should).
2. On drain off, return silently (optionally `logger.debug(...)` at debug level, not warning) without
   calling `_publish_journalled` at all.
3. **Do not** modify `_publish_journalled` itself, `find_run_journal`, `latest_matching_record`, or
   any other function in this module beyond `_publish`.
4. **C-004 guard, explicit**: do not add any import, edge, or call from `src/runtime/next/_internal_runtime/**`
   into `specify_cli`. This module (`specify_cli/events/runtime_moments.py`) already lives on the
   `specify_cli` side of the layering line, and the gate you add here calls `specify_cli.core.hosted_posture`
   — both are within the same layer; you are not creating a new `runtime -> specify_cli` edge because
   you are not touching anything under `src/runtime/` at all in this subtask.

**Files**: `src/specify_cli/events/runtime_moments.py` (modified, ~4 new lines).

**Validation**: T011's producer test turns green (journal lookup functions never called under
`drain_off`). `tests/specify_cli/events/test_runtime_moments_unit.py` still passes unmodified at the
same count — this is the file T016 re-runs to confirm no regression.

---

### Subtask T015: Live-work publisher/authored, retrospective frames, hook, and `routes` command

**Purpose**: Give an accurate, drain-specific drop/error reason at each live-work and CLI surface
this WP owns, rather than relying only on the indirect silence T012's `resolve_credentials` gate
already produces (which would otherwise report a misleading "no relay credentials" reason).

**Steps**:
1. **`src/specify_cli/live_work/publisher.py`** (`publish_observations`, the `try: credential = ...`
   block currently `~239-247`): before calling `resolution.resolve_credentials(...)`, check drain
   posture; if off, append `(payload_id(observation.kind), "drain off")` to `report.dropped` for
   every `observation in pending`, `logger.debug("live-work frames not published: drain off")`, and
   `return report` — mirroring the existing "no relay credentials" branch's shape but with an
   accurate reason string and without allocating a `repo_identity.Deadline()` or importing
   `resolution` at all when drain is off (skip both imports in the drain-off branch if that reads
   cleanly, or leave the imports and just short-circuit before the `Deadline()` call — either is
   fine as long as `resolve_credentials` is never invoked).
2. **`src/specify_cli/live_work/authored.py`** (`_publish`, currently `~380-410`): before calling
   `resolution.resolve_credentials(...)`, check drain posture; if off, raise
   `AuthoredMessageError("not_admitted", "live drain is off — an authored message produces nothing anywhere until it is enabled with `spec-kitty moments drain on`")`
   (match the existing `AuthoredMessageError` two-arg constructor shape exactly — check its actual
   signature in `authored.py` and reuse the same code/message pattern as the neighbouring
   `"not_admitted"` raise). This keeps the "operator waiting for an honest answer" contract
   `_publish`'s own docstring describes, but distinguishes a drain-off refusal from a genuine
   not-admitted answer.
3. **`src/specify_cli/retrospective/lifecycle_events.py`** (`_fanout_live_work_retrospective`,
   currently `~628-680`): add the drain check immediately after the existing
   `if moment_handlers_disabled_reason() is not None: return` line (currently `~653-654`), before
   `resolve_bindings(repo_root)` — same non-raising, `except Exception` — wrapped posture this
   function already has; a drain-off skip is not an exception, so an explicit early `return` is
   correct rather than relying on the outer `try/except`.
4. **`src/specify_cli/cli/commands/live_work.py`** (`_run_hook`, currently `~92-96`): add the drain
   check immediately after the existing
   `if moment_handlers_disabled_reason() is not None: return` block, before `get_adapter(harness)` —
   this avoids reading stdin and parsing the harness payload at all when drain is off, consistent
   with NFR-003's "no wasted work" intent, and keeps the hook's exit-0 guarantee (a drain-off skip is
   not an error).
5. **`src/specify_cli/cli/commands/routes.py`** (`routes()`, currently `~139-152`): wrap the
   `stored = resolution.resolve_credentials(os.getcwd(), gateway=gateway)` call (the genuine
   cache-miss branch, currently around `~147`) in a `try/except DrainDisabled as exc:` that prints
   the shared guidance line (import it from `hosted_posture`, do not hand-roll a second copy) via
   `console.print` and exits with the same code the existing "no accessible route" branch uses
   (check `_print_routes`'s negative-answer branch and `_fail`'s convention; a drain-off refusal is
   an environmental non-answer, not necessarily a hard failure — match whichever the existing tests
   in T011 expect). Import `DrainDisabled` from `specify_cli.core.hosted_posture`.

**Files**: `src/specify_cli/live_work/publisher.py`, `src/specify_cli/live_work/authored.py`,
`src/specify_cli/retrospective/lifecycle_events.py`, `src/specify_cli/cli/commands/live_work.py`,
`src/specify_cli/cli/commands/routes.py` (all modified, ~5-10 lines each).

**Validation**: All T011 live-work and `routes` assertions turn green. Manually trace one path end
to end with drain off: `spec-kitty live-work hook claude < payload.json` exits 0 with no observation
parsed; `spec-kitty routes` prints the guidance line and does not raise.

---

### Subtask T016: Full validation pass

**Purpose**: Confirm the whole WP is green, non-regressive, and clean under the project's static
gates before handing off to review.

**Steps**:
1. Run the WP's own new/changed test files first, verbose:
   ```bash
   pytest tests/zeitgeist_client/ tests/status/ tests/specify_cli/live_work/ \
     tests/specify_cli/events/test_runtime_moments_unit.py \
     tests/cli/commands/test_routes_command.py \
     tests/specify_cli/cli/commands/test_live_work.py -q
   ```
   Record the exact pass/fail counts. If `test_routes_command.py` or `test_live_work.py` do not
   exist under those exact names, locate the real test module covering `cli/commands/routes.py` and
   `cli/commands/live_work.py` with `grep -rl "routes\b" tests/cli/ --include="*.py"` /
   `grep -rl "live_work" tests/specify_cli/cli/ --include="*.py"` and run those instead — note the
   substitution in your PR's "Tests run" section.
2. Run `ruff check .` and `uv run --frozen ruff format --check .` over the touched files (or the
   whole repo, per CLAUDE.md's formatter-gate note) — 0 issues.
3. Run `mypy` over the touched files — 0 issues. Do not add `# type: ignore`; fix the type instead.
4. Run `make test-fast` for the baseline tier.
5. Cross-link **#4322** in your PR description near the `resolve_credentials`/`resolve_focus_capability`
   debug-reason work (T012) — that issue tracks the broader "distinguish why a resolver returned
   `None`" debt this WP's `drain-off` debug reason is one instance of; note in the PR that this WP
   adds one more distinguishable reason but does not close #4322 itself.
6. Before treating any red as yours, apply the baseline-red gotcha from CLAUDE.md: check the same
   test against the merge-base to rule out a pre-existing known-P0 red.

**Files**: none (validation only).

**Validation**: All commands above pass; counts recorded in the PR body under "Tests run".

## Definition of Done

- [ ] T011's tests exist, were committed as a separate red-first commit, and are now green.
- [ ] `SaasCapabilityGateway.check_repo_admission` and `.mint_capability` raise `DrainDisabled`
      before any `self._http` call when drain is off; the constructor (`__init__`, `_http=` seam)
      is unchanged and ungated.
- [ ] `resolve_credentials`, `resolve_focus_capability`, `resolve_focus_lease` return `None` before
      any cache/credential-store read when drain is off, logging a `drain-off` debug reason; an
      already-cached credential plus drain-off still yields nothing sent (US1-AS2).
- [ ] `fire_saas_fanout`, `fire_resolved_binding_fanout`, `fire_lifecycle_saas_fanout` spawn no
      thread and call no handler when drain is off; the import-time
      `moment_handlers_disabled_reason()` registration gate is untouched and still composes with
      the new per-call gate.
- [ ] The runtime-moment producer (`events/runtime_moments.py::_publish`) publishes nothing under
      drain-off, without touching `src/runtime/**` (C-004 verified — no new `runtime -> specify_cli`
      import edge introduced).
- [ ] `live_work` publisher/authored, the retrospective live-work frame, and the `live-work hook`
      CLI command all skip cleanly under drain-off, with an accurate "drain off" reason surfaced
      where a reason is reported at all.
- [ ] `spec-kitty routes` prints "Live drain is off…" (not a traceback, not "Team Kitty
      unreachable") under drain-off, and behaves exactly as it does on `main` under drain-on.
- [ ] `ruff check .`, `ruff format --check .`, and `mypy` report 0 issues on every file this WP
      touched.
- [ ] `make test-fast` passes; the full test list from T016 step 1 passes; counts are recorded in
      the PR body.
- [ ] Every `spec-kitty agent tasks mark-status <Txxx> --status done` event for T011–T016 has been
      recorded.

## Risks

- **Gating `__init__` by mistake (F-2 regression risk).** The original plan text (D2) said to gate
  `SaasCapabilityGateway.__init__`; the post-plan squad fold (F-2) explicitly moved the gate into
  `check_repo_admission`/`mint_capability` to preserve the `_http=` test seam. If you gate
  `__init__`, every existing test that constructs a gateway with a fake `_http` to then assert on a
  *specific* method's behaviour will break, and the object-construction path (which makes no network
  call) will be needlessly gated. Follow F-2, not the earlier D2 table, for this call site.
- **Double-gating vs. silent divergence between adapters.py's two gates.** The import-time
  kill-switch gate and the new per-call drain gate must compose (either can silence fan-out), not
  replace each other. Removing the import-time gate, or making the new gate conditional on it,
  would regress the existing `SPEC_KITTY_NO_MOMENT_HANDLERS`/`SPEC_KITTY_SYNC_DISABLE` narrower
  behaviour edge cases already covered by existing tests.
- **Misleading drop reasons.** `resolve_credentials` already returns `None` when drain is off
  (T012), so `publish_observations` would silently report "no relay credentials (repo not admitted)"
  even though the real reason is drain. T015's explicit early check exists specifically to avoid
  this operator-facing misdiagnosis — do not skip it as "redundant" with T012's gate.
- **C-004 layering violation.** It is easy to reach for a runtime-side hook when touching the
  runtime-moment producer. Confirm with `grep -rn "specify_cli" src/runtime/next/_internal_runtime/`
  before and after your change that the hit count is unchanged (this producer already lives in
  `specify_cli.events`, not `src/runtime`).
- **Line numbers drift.** Every `~NNN` reference in this prompt is a pointer verified against the
  live tree at the time this WP was written, not a guarantee — re-read each target function before
  editing, since WP02 (parallel, disjoint files) and WP01 (dependency, already merged) may have
  shifted surrounding line counts slightly.

## Reviewer Guidance

- Confirm the ATDD red-first commit is present and separate from the implementation commits (charter
  Quality & Tech-Debt Standing Orders — red-first discipline).
- Verify `SaasCapabilityGateway.__init__` is untouched — diff it explicitly; this is the single most
  likely F-2 regression.
- Verify the `drain-off` debug-reason string is a literal, distinguishable substring in
  `resolve_credentials`/`resolve_focus_capability` logging, and cross-link **#4322** (the broader
  "why did resolution return None" diagnostics debt) in the PR rather than treating this WP as
  closing it.
- Verify the import-time `moment_handlers_disabled_reason()` gate in `status/adapters.py` is
  byte-identical to `main` (only the new per-call early-returns were added inside the three `fire_*`
  functions).
- Verify no file under `src/runtime/next/_internal_runtime/` was touched (C-004); a
  `git diff --stat main... -- src/runtime/` should be empty for this WP's branch.
- Verify NFR-001/NFR-003 by spot-checking one of T011's tests actually patches the credential-store
  read (not just the network call) and asserts `assert_not_called()` — a test that only checks "no
  HTTP request" without also checking "no cache/keyring read" would pass while leaving the
  cached-credential vector (US1-AS2) open.
- Verify `spec-kitty routes` under drain-off does not regress the existing "no accessible route
  found" (negative-cache) UX — the two must be distinguishable outputs, not collapsed into one
  message.

## Implementation Command

```bash
spec-kitty agent action implement WP03 --agent claude
```
