---
title: 'tests/sync/ process-global and thread-seam inventory (#3115)'
description: 'FR-006: a narrowed inventory of process-global mutable state and thread-spawning seams in the tests/sync/ cone, with reset-seam and dependence classification.'
doc_status: deprecated
updated: '2026-09-08'
audience: docs/context/audience/internal/system-architect.md
type: reference
related:
- docs/development/testing/testing-parallel.md
- docs/development/reference/read-side-seam-classification.md
---

# The `tests/sync/` process-global and thread-seam inventory

> **Deprecated record.** The `tests/sync/` cone this page inventories was deleted with
> the local sync transport (Convergence #3881, 2026-09-05); every `src/specify_cli/sync/`
> path below is the pre-Convergence tree. The page is retained as the historical record
> of the #3115 inventory, not as a live map.

This is the map, not the answer. It carries no attribution for `#3115`'s sync-half
leak hunt and needs none: FR-005's leak guard (`tests/sync/conftest.py`, WP05) is
scoped to watch every entry below, and FR-007's synthetic-vs-real probe decision
consumes it, whether or not the underlying attribution ever converges (H4).

**Revision note (post-review)**: this revision responds to an independent review
that rejected the first draft on three HIGH findings, four MEDIUM, and two LOW —
summarized in [Review response](#review-response) at the end of this page. The
dependence vocabulary (`depends` / `does not depend` / `undetermined`) is
unchanged from the first draft; a coordinator note claiming otherwise was itself
mistaken and is not acted on here.

**Scope**: the `tests/sync/` cone only (`tests/sync/**/*.py`). The CLI cone
(`tests/cli/`) is out of scope — its render-width defect has a measured
non-global cause (`docs/development/testing-parallel.md#reproducing-3115-the-folded-uuid-render-width-defect`),
and re-deriving that here would re-answer a settled question.

**Process-global**, for this inventory, means module-level mutable state whose
lifetime is the worker process: singletons, registries, caches,
import-time-bound paths, memo sets, **live threads**, `os.environ`, and the
CWD.

## Method

1. An AST walk (`ast.parse` + inspection of each module's top-level `body`)
   over every `tests/sync/**/*.py` file found every module-level `Assign` /
   `AnnAssign` statement: **296 total bindings** across 138 files.
2. **Mechanical discriminator (re-derived this revision, `ast.literal_eval`)**:
   for every binding whose target name is not `pytestmark`, the RHS was run
   through `ast.literal_eval`.
   - **Succeeds, immutable type** (`str`, `int`, `float`, `bool`, `None`,
     `bytes`, a tuple/frozenset of only immutable elements) → excluded:
     **121** bindings.
   - **Succeeds, mutable type** (`list`, `dict`, `set`) → a literal mutable
     container → **included**: **7** bindings, all containers.
   - **Fails** (the RHS is a call, attribute access, f-string, comprehension,
     binary op, or contains a name reference) → **35** bindings; each was
     read individually and classified by its actual runtime type/shape, not
     by the fact that it isn't literal syntax. Of the 35:
     - **7** are a **mutable container** built via a non-literal expression
       (a comprehension, or a literal container with one non-literal
       sub-expression such as a name reference or `+`-concatenation) →
       included;
     - **9** are a **path resolved from `__file__` / `Path(...).resolve()` /
       division at import time** → included as *import-time-bound path*
       regardless of `Path`'s own immutability, because the hazard this
       category names is the fixed, process-lifetime-shared filesystem
       location, not object mutability;
     - **16** are a **computed-but-immutable value** — a `str` built by
       concatenation, slicing, `"".join(...)`, or an f-string; a
       `uuid.UUID(...)`; a compiled `re.compile(...)` pattern; a
       `frozenset(...)` call; a `tuple(...)` call over a generator of
       strings; a `Path(...)` built from a string literal (not `__file__`) →
       excluded. The exemplar the first draft cited for "frozen literal
       constants", `PRESERVED_COLUMNS`
       (`tests/sync/test_journal_identity_backfill_3030.py:316`), belongs
       here — it is a `tuple(...)` call over a generator, not literal
       syntax. The first draft's exclusion was correct; the reason it gave
       was not — this revision excludes it as *an immutable tuple*, not as
       *a literal*.
     - the remaining **3** of the 35 are the module-level `CliRunner()`
       instances already tracked as their own entries (E17–E19) — not
       double-counted here.
   - **`pytestmark` (133 bindings) is a deliberate carve-out**, not run
     through the discriminator above: it is pytest's own collection-time
     marker mechanism, assigned exactly once per module (bare mark or a list
     form, `pytestmark = [pytest.mark.fast]`), and never reassigned or
     mutated afterward — verified with
     `grep -rnE 'pytestmark\s*(\.append|\.extend|\+=|\[.*\]\s*=)' tests/sync --include="*.py"`
     (zero hits) before relying on that claim rather than asserting it.
   - **Reconciliation**: `133 (pytestmark) + 121 (literal immutable) + 7
     (literal mutable) + 35 (nonliteral) = 296`. Of the 35 nonliteral: `16`
     mutable-or-path (`7` containers `+ 9` paths) `+ 16` computed-immutable
     `+ 3` already-tracked `= 35`. Included total: `7` (literal-mutable
     containers) `+ 7` (nonliteral containers) `+ 9` (nonliteral paths) =
     **23** new entries. Excluded total: `133 + 121 + 16 = 270`. Already
     tracked: `3`. `270 + 23 + 3 = 296`. ✓
3. A `grep -rn "Thread("` over the same tree found every worker-process
   thread-construction call site; each hit was read in context to tell a
   real `threading.Thread(...)` from a thread constructed inside a **string
   template destined for a spawned subprocess** (one such false-positive,
   `_daemon_harness.py:132`, confirmed correct by the reviewer and kept
   excluded) and from a thread the test only *observes* by patching
   `threading.Thread` itself (`test_issue_598_hang_fixes.py:467`, now
   entered — see
   [Thread-spawning seams](#thread-spawning-seams--test-cone-worker-process-threads)).
   **Method limit, stated rather than silently accepted**: a `grep` scoped to
   `tests/` structurally cannot see a thread spawned by `src/` code the tests
   merely *call into* — this revision extends discovery to
   `src/specify_cli/sync/background.py`'s two thread/timer seams
   (`BackgroundSyncService.stop`'s final-sync thread, `:444`, and
   `_schedule_next_sync`'s self-rescheduling `threading.Timer`, `:528`),
   both reachable from `tests/sync/test_issue_598_hang_fixes.py:445-476`. It
   does **not** claim to have walked every `src/` module reachable from every
   test in the cone — that would require a call-graph tool this WP does not
   have, not a bigger grep — so the discovery boundary for `src/`-side
   threads remains: `daemon.py` (handed to this WP already-identified) and
   `background.py` (added this revision because a specific review finding
   named the exact reachable lines). A future revision that wants a
   *complete* `src/`-side thread census should say so explicitly rather than
   inherit this one's boundary silently.
4. **Dependence methodology — corrected this revision.** The first draft's
   rule was "no file in this row imports or is imported by `saas_client.py`"
   — import-graph disjointness. The review correctly rejected this:
   process-global leakage (a live thread, a raw `os.environ` write, a shared
   singleton) is coupling through the **operating-system process**, which
   requires no import edge between polluter and victim. The review's own
   control case proves the rule wrong on contact —
   `tests/specify_cli/invocation/test_propagator_consent_gate_3030.py`'s
   `wiring` fixture leaks via `reset_adapters()` and a raw `os.environ`
   write whose victims do not import it either, and the leak is real.

   **The corrected rule traces `test_429_respects_retry_after`'s actual
   executed call path** and asks, for each entry, whether that path reads or
   writes the entry — never whether an import edge exists. The call path,
   read directly from source (`src/specify_cli/tracker/saas_client.py`,
   read-only for this WP):

   - `client` fixture → `SaaSTrackerClient(credential_store=..., sync_config=mock_sync_config, timeout=5.0)`
     → `_compat_init` (installed by `tracker/conftest.py`'s autouse
     `_patch_saas_token_bridges`) → real `SaaSTrackerClient.__init__`
     (`:234-247`): `self._base_url = self._sync_config.resolve_runtime_target().resolved_server_url`
     — `self._sync_config` **is the mock**, so this reads a hardcoded
     `MagicMock` return value, never `os.environ` or a real `SyncConfig`.
   - `client._request_with_retry("GET", ...)` → `self._request(...)`
     (`:294-373`) → **the one real, unmocked chokepoint on this test's
     path**: `project_egress_refusal(self._project_root)`
     (`src/specify_cli/egress.py`, formerly `src/specify_cli/tracker/egress_consent.py:147-190`
     — relocated by #3110) → (permits) →
     `resolve_egress_consent(Path(project_root))`
     (`src/specify_cli/invocation/adapters.py:148-185`) → the registered
     module-global `_egress_consent_resolver(path)` (`adapters.py:81`,
     populated once per worker process by `register_default_handlers()`,
     called at the bottom of `specify_cli/sync/__init__.py:429` — module
     bodies execute once per process, so this fires on the *first* import of
     `specify_cli.sync` anywhere in the worker, not per-test) → then
     `_fetch_access_token_sync()` / `_current_team_slug_sync()` (both
     **patched fakes**, installed by the same autouse fixture) → then
     `httpx.Client(...)` (**mocked** via `@patch(".../httpx.Client")`).
   - Back in `_request_with_retry`'s 429 branch (`:421-429`):
     `envelope = _parse_error_envelope(response)` (pure function over the
     mocked response body) → `time.sleep(float(wait_seconds))`
     (**mocked**, `@patch(".../time.sleep")`) → a second mocked request.
   - The assertion is `mock_sleep.assert_called_once_with(3.0)` — a call-args
     assertion on a `MagicMock`, not a real-timing or real-socket assertion.

   So the **only** state outside the test's own mocks that this path reads
   is: (a) the filesystem — the `.kittify/config.yaml` `_consenting_project_root()`
   writes under `tmp_path` (`tracker/conftest.py:131-153`), and (b) the
   registered `_egress_consent_resolver` singleton. Neither is `os.environ`,
   a lock, a port, or the CWD (`project_egress_refusal`'s own docstring,
   `egress_consent.py:158-159`, now `specify_cli/egress.py` per #3110, states the checkout is resolved from an
   explicit `project_root`, "never the process's current working
   directory"). **An entry is `does not depend` only when it is proven not
   to touch (a) or (b), or any lock/port/env-var this path reads — not
   merely absent from an import graph.** Where a real intersection with (a)
   or (b) exists (as it does for the token-bridge/`__init__`-patching
   autouse fixture), the verdict is `depends`, stated with both limbs of the
   mechanism (see the corrected E22 row). Where the check cannot be
   completed with the evidence available under this WP's no-pytest
   constraint, the verdict is `undetermined`, not a guess.

   **Validated against the control case**: `_egress_consent_resolver` is
   *exactly* the singleton the control case's `reset_adapters()` leak
   clears. `grep -rln "reset_adapters\|_egress_consent_resolver\|register_egress_consent_resolver" tests/sync --include="*.py"`
   returns **zero files** — nothing in the 138-module `tests/sync/` cone
   touches that resolver slot (the leak lives in a different test directory
   entirely, `tests/specify_cli/invocation/`). This is not the same claim as
   "no import edge" — it is "the one unmocked chokepoint this test's path
   reaches is provably untouched by anything in scope," which is falsifiable
   evidence the control case's own leak does not contradict (the control
   case's leaking file *does* touch that chokepoint; every file checked
   in-scope here does not).

## Input count

**138 modules scanned** (every `.py` file under `tests/sync/`, including
`tests/sync/tracker/`, `__init__.py`, and both `conftest.py` files). Of
those, **29 files** contribute at least one in-scope entry below (up from 14
in the first draft — the 15 added files are a direct consequence of
re-deriving the exclusion with `ast.literal_eval`, and of the `os.environ`/CWD
sweep). **53 entries total** (up from 22). The remaining **109 files** carry
no module-level assignment that meets the process-global-mutable-state
definition once `pytestmark` and genuinely-immutable computed values are
excluded by the stated discriminator (see
[Excluded](#excluded--module-level-constants-re-derived-discriminator)).

Four `src/` modules are cited by symbol below without being independently
walked wholesale — they are **read-only for this WP**. Two were handed to
this WP already-derived (`src/specify_cli/sync/daemon.py`,
`src/specify_cli/tracker/saas_client.py`); two more are added this revision
because specific review findings named exact reachable lines
(`src/specify_cli/sync/runtime.py`, `src/specify_cli/sync/background.py`).
`src/specify_cli/invocation/adapters.py` and `src/specify_cli/sync/__init__.py`
are additionally **read and cited** (not entered as inventory rows — they sit
outside both the `tests/sync/` cone and the four named `src/` files) because
tracing `test_429`'s real call path through them is what the corrected
dependence methodology in [Method](#method) required.

## Legend — the four mandatory values

1. **Module and symbol** — the file and the function/class/fixture that owns
   the construct.
2. **Reset seam**: `reset seam: <name>` (a named mechanism unconditionally
   restores/tears the construct down), `no reset seam` (cleanup exists but is
   not guaranteed — e.g. a bare `join(timeout=N)` with no check that the join
   actually completed, or a raw `os.environ` write with no matching
   `monkeypatch` teardown), or `not reachable` (there is nothing to reset: a
   frozen or computed-immutable value, or a bounded synchronous loop that is
   not a spawned thread).
3. **Who calls that seam** — the fixture/test/framework hook that invokes the
   reset mechanism, or `nobody` when the classification is `no reset seam` /
   `not reachable`.
4. **Dependence** — whether `test_429_respects_retry_after`'s outcome
   depends on the entry: `depends` / `does not depend` / `undetermined`, with
   the evidence, established per the corrected methodology in
   [Method](#method) (process-path tracing, not import-graph disjointness).
   **This column is stamped — read the stamp directly below before relying on
   any value in it.**

> **⚠ Verdict-column stamp (`#3136`) — unverified, and falsified in the direction
> that matters.** This stamp is deliberately a blockquote inside the Legend
> section and **not** its own heading: `docs/development/3-2-docs-retrieval-index.yaml`
> indexes this page by its body headings (`scripts/docs/docs_index.py:184-196`
> builds each row's `anchors` from `scan_headings(body)`), and
> `check_docs_freshness.py`'s `_check_docs_index_drift` (`:767-813`) reds
> `DOCS-INDEX-DRIFT` at `severity="error"` on any new heading until that generated
> index is regenerated — a file this work package does not own. A heading here
> would trade a documentation note for a red gate.
>
> **Scope: the `Dependence` column only.** The `#`, `Module : symbol`,
> `Reset seam` and `Caller` fields of every row are **untouched by this stamp and
> remain load-bearing**. `tests/sync/_leak_guard.py` resolves **29** distinct
> row-ids from this page at runtime, by row-id, via `_WatchedGlobal.inventory_id`
> (`:47`); all 29 still resolve to exactly one row each. No row-id, row order,
> table header or column count was changed.
>
> **What is stamped, and why.** All **53** `Dependence` verdicts (`E1`–`E53`,
> contiguous) were derived against a single reference node,
> `test_429_respects_retry_after` — Legend item 4 above, defined by
> [Method](#method) §4 — **at a time when that node had never exhibited the
> failure**. That premise no longer holds:
>
> - The node is a confirmed victim on PR #3209's `fast-tests-sync` shard. PR #3209
>   is pinned by **head SHA `5e98c2bb7`**
>   (`5e98c2bb752f9ef6484eafc6411afedfd395f957`), never by branch name — the branch
>   moved twice (`96494e5ec` → `783c137d7` → `5e98c2bb7`), so the name is not a
>   reproducible handle. `[UNVERIFIED]`: that SHA was confirmed `2026-08-05` and has
>   not been re-verified since.
> - Independently of PR #3209, **three** census nodes failed **simultaneously** on
>   pristine `main` at `98198e980` — job `92278529393`, `3 failed, 2113 passed,
>   11 skipped, 2 warnings in 100.79s`. The failure is topology-and-timing
>   dependent, not composition dependent, so no shard composition confines it.
>
> The column is therefore **falsified**, not merely **unverified**. Each verdict
> reasons from the outcome of a node that was taken to be stable; that node's
> outcome is not stable. A stamp reading only "unverified" would understate it.
> Treat every `Dependence` value here as **unverified input** and re-derive it
> against the failing nodes before relying on it.
>
> **Rows this mission (`#3136`) re-derived: none. The depended-on set is empty —
> zero rows.** Stated as a number so it cannot be read as coverage. This is a
> derivation, not an assumption:
>
> - `#3136`'s fix is a module-local alias seam in
>   `src/specify_cli/tracker/saas_client.py` plus the retargeting of that module's
>   patch sites. Its correctness is expressed entirely by a static mechanism
>   predicate over patch targets. It never reads this page.
> - Measured: the fix's own surfaces cite **0** row-ids from this inventory. The one
>   genuine citation inside a file the fix touches
>   (`tests/sync/tracker/test_saas_client.py:723`, naming `E24`/`E25`) sits in a
>   **docstring** — documentary corroboration of a past leak observation, not
>   something the fix's behaviour rests on.
> - `E15` — **not depended on**, but invalidated in the *opposite* direction: the fix
>   changes the surface this row's surrounding prose measured. See the correction
>   under [`saas_client.py` — measured negative](#saas_clientpy--measured-negative).
> - `E22` — this page's only `depends` row. It is a **shared precondition** of the
>   reference node (it is what lets the `client` fixture construct at all, and what
>   supplies a consenting `project_root`), not something the fix's correctness rests
>   on. The three attributes it rebinds on the `saas_client` module object
>   (`_fetch_access_token_sync`, `_current_team_slug_sync`, `_force_refresh_sync`)
>   are **disjoint** from the names the alias seam adds, so the seam neither relies
>   on it nor disturbs it. Dependence, not adjacency, is the test — and this is
>   adjacency.
>
> **Name collision — two different `WP06`s.** `E22`'s own text warns that "WP06
> inherits only limb 1 if this row is read carelessly; both limbs are load-bearing",
> and the `saas_client.py` section below likewise names a "WP06". Both mean
> **`#3115`'s WP06** — a different work package from the **`#3136` WP06** that wrote
> this stamp. Do not conflate them.

## Thread-spawning seams — test cone (worker-process threads)

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E1 | `tests/sync/_daemon_harness.py::DaemonHarness.spawn_plain` (`Thread(..., daemon=True)`, `:303`) | `reset seam: DaemonHarness.shutdown()` (`:381-389`; joins with `timeout=3.0`, then clears `_servers`) | `sync_harness` fixture (`tests/sync/test_daemon_cleanup_boundary.py:174-179`, `yield`+teardown), `harness` fixture (`tests/sync/test_daemon_orphan_classification.py:73-111`, `try/finally`), `harness_1071` fixture (`tests/sync/test_issue_1071_singleton_reconfirmation.py:112-143`, `try/finally`) | does not depend — this construct never touches `_egress_consent_resolver` or the consenting-project filesystem path; it is confined to daemon-internal `HTTPServer`/port state, which `_request_with_retry`'s call path (Method §4) never reads |
| E2 | `tests/sync/_daemon_harness.py::DaemonHarness.spawn_daemon` (real subprocess, not a thread — `subprocess.Popen`-backed, `:224`) | `reset seam: DaemonHarness.shutdown()` (terminates the subprocess via `_terminate_proc`, `:378`) | same three fixtures as E1 | does not depend — same evidence as E1 |
| E3 | `tests/sync/test_daemon.py` (two non-daemon threads calling `daemon.ensure_sync_daemon_running`, `:116-117`) | `no reset seam` — `t1.join(timeout=5); t2.join(timeout=5)` with no follow-up `is_alive()` check; a join that times out leaves the thread running past the test | nobody | does not depend — same evidence pattern |
| E4 | `tests/sync/test_daemon_cleanup_boundary.py::_spawn_http_server` (`Thread(..., daemon=True)`, `:145`) | `reset seam: _stop_http_server` via `dashboard_listener` / `third_party_listener` fixtures (`:182-203`, `yield` then unconditional stop) | those two fixtures | does not depend — same evidence pattern |
| E5 | `tests/sync/test_daemon_self_retirement.py` (harness thread, daemon=True, `:311`) | `reset seam:` inline — the test snapshots `threading.enumerate()` before spawning, joins the harness thread (`timeout=2.0`), and asserts the post-run thread diff is empty (`leaked = {...}; assert not leaked`, `:322-325`) — the test polices its own cleanliness | the test itself | does not depend — same evidence pattern |
| E6 | `tests/sync/test_diagnostic_dedup.py` (thread pool, `:66`) | `no reset seam` — `thread.join(timeout=5)` for each, no post-hoc `is_alive()` check | nobody | does not depend — same evidence pattern |
| E7 | `tests/sync/test_edge_cases.py` (two thread pools, `:226`, `:276`) | `reset seam:` unconditional `t.join()` with **no timeout** — the test body blocks until every thread finishes (barring an actual deadlock, which would hang the test rather than leak a thread past it) | the test body itself | does not depend — same evidence pattern |
| E8 | `tests/sync/test_issue_598_hang_fixes.py::test_stop_when_lock_held_skips_final_sync` (daemon thread, `:319`) | `reset seam:` explicit `release.set()` then `t.join(timeout=2)` (`:337-338`) | the test itself | does not depend — same evidence pattern |
| E9 | `tests/sync/test_orphan_sweep.py::_spawn_plain_server` / local `_DaemonHarness` (`Thread(..., daemon=True)`, `:135`; harness class `:149-234`) | `reset seam: _DaemonHarness.shutdown()` (`:233-238`) via the `harness` fixture's `try/finally` (`:242-244`) | `harness` fixture | does not depend — same evidence pattern |
| E10 | `tests/sync/test_runtime.py` (10-thread pool exercising `get_runtime()` singleton thread-safety, `:580`) | `no reset seam` — `t.join(timeout=5)` per thread, no post-hoc `is_alive()` check | nobody | does not depend — this pool touches `specify_cli.sync.runtime._runtime` (see E26 below), confined to `runtime.py`'s own lock, never `_egress_consent_resolver` or the filesystem consent path |
| E23 | `tests/sync/test_issue_598_hang_fixes.py::test_stop_final_sync_thread_is_daemon` — `TrackingThread(real_thread)` patched over `specify_cli.sync.background.threading.Thread` (`:467-470`), causing `svc.stop()` to spawn one real worker-process thread (`:471-476`) — **added this revision (Medium finding: the 13th `Thread(` hit)** | `reset seam:` the `with patch(...)` context manager (`:470`) guarantees `threading.Thread` itself is restored on exit; the spawned thread instance's own lifecycle is governed by `BackgroundSyncService.stop()`'s bounded `join(timeout=5)` + `is_alive()` diagnostic (see E24 below) — not independently joined by the test itself | nobody joins the spawned thread directly (only the patch itself is guaranteed-restored) | does not depend — same `background.py` reasoning as E24/E25 below |

A `Thread(...)` construction found inside `_daemon_harness.py:132` was
**excluded**: it is text inside `_build_wedged_daemon_shape_script`, a Python
source template written to be executed by a **spawned subprocess**, not
constructed in the worker process itself. Counting it as a worker-process
thread-seam would have been the grep-shaped mistake this inventory exists to
avoid. The review confirmed this exclusion as correct.

## Known src-side thread/sleep seams — `daemon.py` (read-only, cited not re-derived)

Per the mission's own note, these are handed to this WP already-identified
and are **not** re-derived independently; line numbers were spot-checked
against this revision.

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E11 | `src/specify_cli/sync/daemon.py` — `shutdown_server` thread inside the stop-handler (`threading.Thread(target=shutdown_server, ...).start()`, `~:587`) + its `time.sleep(0.01)` loop body (`~:584`) | `no reset seam` — nothing in `tests/sync/conftest.py` snapshots or reaps the live-thread set today; that mechanism is FR-007's deliverable, not yet built | nobody | does not depend — `daemon.py` is never imported, directly or transitively, by `saas_client.py` / `test_saas_client.py` / `tracker/conftest.py` (`grep -n "daemon" ...` returns zero, reproduced in Method), and its threads touch only daemon-internal ports/locks/`HTTPServer` state, never `_egress_consent_resolver` or the filesystem consent path `_request`'s call chain (Method §4) actually reads |
| E12 | `src/specify_cli/sync/daemon.py` — thread named `"spec-kitty-sync-runtime-start"` (`~:767`) | `no reset seam` (same reason as E11) | nobody | does not depend — same evidence |
| E13 | `src/specify_cli/sync/daemon.py` — `_shutdown_off_thread` spawned from the SIGTERM/SIGINT handler (`~:828`) | `no reset seam` (same reason) | nobody | does not depend — same evidence |
| E14 | `src/specify_cli/sync/daemon.py` — the daemon-stop poll loop's `time.sleep(0.05)` (`~:1382`) | `not reachable` — this is a bounded synchronous poll inside the *calling* thread (it blocks the caller until the deadline or the daemon dies); it is not a spawned thread and has no independent lifetime to reset | nobody | does not depend — same evidence |

## `src/`-side thread/timer seams — `background.py` (added this revision, Medium finding)

The first draft's thread discovery was `grep`-scoped to `tests/` and
therefore structurally could not see a thread spawned by `src/` code the
tests merely call into. `tests/sync/test_issue_598_hang_fixes.py:445-476`
reaches `BackgroundSyncService.stop()`, which owns two such seams (see the
method-limit note in [Method](#method) for why this pair is added and the
boundary is not claimed complete beyond it).

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E24 | `src/specify_cli/sync/background.py::BackgroundSyncService.stop` — the final-sync thread (`threading.Thread(target=self._guarded_final_sync, daemon=True)`, `:444`) | `no reset seam` — `sync_thread.join(timeout=_STOP_SYNC_TIMEOUT_SECONDS)` (`:456`; `_STOP_SYNC_TIMEOUT_SECONDS = 5`, `:50`) followed by an `is_alive()` check that only emits a diagnostic (`:457-462`) — detects and reports, does not force-terminate or guarantee the thread is gone | nobody forces the reap; `stop()` itself is called by `reset_sync_service()` and directly by several `tests/sync/test_issue_598_hang_fixes.py` tests | does not depend — `background.py` is never imported by `saas_client.py`/`test_saas_client.py`/`tracker/conftest.py` (confirmed by the same `grep -n "daemon"`-style check extended to `"background"`, zero hits), and this thread's only shared state is `background.py`'s own `_lock`/`_timer`, never `_egress_consent_resolver` or the filesystem consent path |
| E25 | `src/specify_cli/sync/background.py::BackgroundSyncService._schedule_next_sync` — the self-rescheduling `threading.Timer` (`self._timer = threading.Timer(interval, self._on_timer)`, `:528`) | `reset seam: BackgroundSyncService.stop()` cancels it unconditionally when set (`self._timer.cancel(); self._timer = None`, `:413-415`) | `reset_sync_service()` (`background.py:901`, calls `.stop()`), direct `svc.stop()` calls in `test_issue_598_hang_fixes.py`, and `TestSingletonAccessor.teardown_method`'s exception fallback (`tests/sync/test_background.py:320-329`, manual `._timer.cancel()`) | does not depend — same evidence as E24 |

## `saas_client.py` — measured negative

`src/specify_cli/tracker/saas_client.py`'s entire module-level assignment
surface is **exactly two names** (confirmed by an AST walk of its own
`tree.body`, not a re-derivation from the mission's note — both a
verification and a citation):

```
36 _SESSION_EXPIRED_MESSAGE
39 _UNAUTHENTICATED_CATEGORY
```

> **⚠ Correction (`#3136`) — the enumeration above is short by one, and was
> already short at the time it was written.** Re-running this section's own stated
> method (an `ast` walk of the module's `tree.body`, collecting every
> `Assign`/`AnnAssign` bound to a `Name`) against `98198e980` — the baseline
> commit, *before* any `#3136` change — yields **three** module-level names, not
> two:
>
> ```
> 36 _SESSION_EXPIRED_MESSAGE
> 39 _UNAUTHENTICATED_CATEGORY
> 51 TRACKER_EGRESS_IDENTIFIER_KINDS
> ```
>
> `TRACKER_EGRESS_IDENTIFIER_KINDS` (`:51`) is missing from the list above and
> from the "exactly two names" claim, and the "**Independently confirmed by
> review**" line below repeats the same count — two parties agreed on a number the
> method they both cite does not produce. This is a measured falsehood, not a
> disagreement about scope.
>
> **What survives.** The *conclusion* holds: the third name is a frozen `str`
> literal, not a retry/backoff value, so "no leaked module-global retry/backoff
> value exists in `saas_client.py`" is still true. Only the **count** and the
> **enumeration** were wrong, and with them the claim that this is an *exhaustive*
> surface measurement.
>
> **What `#3136` changes.** `#3136`'s `FR-010` alias seam adds **three further**
> module-level assignments to this same module — `_sleep`, `_monotonic`,
> `_randbelow`, bound by assignment so that patch decorators can retarget onto
> them. Once that lands the surface is **six** names, three of them deliberately
> rebindable. `E15`'s `not reachable` classification rests on the enumeration
> above, so the row is **invalidated by `#3136`'s own fix and must be re-derived,
> not merely stamped**. `E15`'s `Dependence` verdict is separately covered by the
> verdict-column stamp, which is the blockquote inside
> [Legend — the four mandatory values](#legend--the-four-mandatory-values);
> this correction is about the row's *premise*, which is a different defect.

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E15 | `src/specify_cli/tracker/saas_client.py::_SESSION_EXPIRED_MESSAGE` (`:36`), `::_UNAUTHENTICATED_CATEGORY` (`:39`) | `not reachable` — both are frozen string literals, assigned once at import, never reassigned anywhere in the module | nobody | does not depend — `test_429_respects_retry_after` exercises the 429 branch of `_request_with_retry`, never the 401 branch that reads `_SESSION_EXPIRED_MESSAGE` |
| E16 | `src/specify_cli/tracker/saas_client.py` — retry/backoff state in `_request_with_retry` (429 handling) and `_poll_operation` (`delay`, `cap`, `total_timeout`, `start`, `:461-468`) | `not reachable` — **structurally impossible to leak as a module global**: these are function-local variables, never promoted to module scope; there is nothing here for a reset seam to watch | nobody | does not depend |

**This closes a hypothesis WP06 would otherwise spend budget on**: "a leaked
module-global retry/backoff value" cannot be the sync-half cause in
`saas_client.py`, because no such module global exists. Recorded as a
measured negative, not an absence of looking. **Independently confirmed by
review**: exactly two module-level assignments, backoff function-local.

## Two canonical sync singletons — added this revision (HIGH finding)

Missed in the first draft. Both are textbook FR-006 rows — process-lifetime
singletons with an existing named reset function — and both are mutated
*directly*, bypassing the reset function, from inside the `tests/sync/` cone.
**WP05's guard is scoped to this inventory, so an entry omitted here is a
global the guard will never watch.**

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E26 | `src/specify_cli/sync/runtime.py::_runtime` (`:580`, `SyncRuntime \| None`, guarded by `_runtime_lock`) | `reset seam: reset_runtime()` (`:604-609`; stops the runtime if set, then clears it) | `tests/sync/test_lifecycle_readiness.py:315`, `tests/sync/test_sync_e2e_integration.py:95,99` call `reset_runtime()` directly; **bypassed** via direct mutation with a local `try/finally` restore at `tests/sync/test_daemon_owner_record.py:225,268,298` (`runtime_mod._runtime = ...`, each site restores `original_runtime` in its own `finally`) | does not depend — `runtime.py` is never imported by `saas_client.py`/`test_saas_client.py`/`tracker/conftest.py`; `_runtime`'s only synchronization is its own `_runtime_lock`, never `_egress_consent_resolver` or the filesystem consent path `_request`'s call chain reads |
| E27 | `src/specify_cli/sync/background.py::_service` (`:868`, `BackgroundSyncService \| None`, guarded by `_service_lock`) | `reset seam: reset_sync_service()` (`background.py:901+`; stops the service, then clears it) | `TestSingletonAccessor.teardown_method` (`tests/sync/test_background.py:317-330`) calls it on the primary path; **bypassed** on the fallback path (`.stop()` raised) via direct `_bg._service = None` at `:330`, after manually setting `_running = False` and cancelling `_timer` in the same block | does not depend — same evidence as E26 |

## Module-level `CliRunner()` instances

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E17 | `tests/sync/test_sync_logged_out_recovery.py::runner` (`CliRunner()`, `:30`) | `no reset seam` — one instance constructed at import, reused across every test function in the file, never torn down or replaced between tests | nobody | does not depend — this name is referenced in exactly one file (`grep -rl` confirms), never imported elsewhere, so it is unreachable from `test_429`'s executed call path regardless of process-level coupling |
| E18 | `tests/sync/test_sync_status_boundary_check.py::runner` (`CliRunner()`, `:30`) | `no reset seam` (same reason) | nobody | does not depend — same reachability argument |
| E19 | `tests/sync/tracker/test_tracker_discovery_integration.py::cli_runner` (`CliRunner()`, `:26`) | `no reset seam` (same reason) | nobody | does not depend — distinct object, never referenced by `test_saas_client.py` |

## `conftest.py` autouse fixtures — reset-seam providers, and two load-bearing dependences

`tests/sync/conftest.py` applies to the whole cone, including
`tests/sync/tracker/`; `tests/sync/tracker/conftest.py` applies additionally
to everything under `tracker/`.

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E20 | `tests/sync/conftest.py::_isolate_pre_review_gate_sync_toggles` (autouse, `:140-169`) — unsets `SYNC_DISABLE_ENV_VARS` from `os.environ` before every test | `reset seam: _isolate_pre_review_gate_sync_toggles` (`monkeypatch.delenv`, auto-restored per test) | pytest itself (`autouse=True`, applies to every test under `tests/sync/`, `tracker/` included) | does not depend — traced directly against `_request_with_retry`'s and `_request`'s bodies (Method §4): neither reads `SYNC_DISABLE_ENV_VARS`, `is_sync_enabled_for_checkout`, or any `os.environ` key; the one real chokepoint on the path is `project_egress_refusal`/`_egress_consent_resolver`, which also reads no env var (`egress_consent.py:147-190`, now `specify_cli/egress.py` per #3110, has zero `os.environ`/`getenv` references) |
| E21 | `tests/sync/conftest.py::_consented_checkout_by_default` (autouse, `:194-259`) — `monkeypatch.setattr`s `is_sync_enabled_for_checkout` (batch/runtime) and `EventEmitter._project_consents_to_capture` | `reset seam: _consented_checkout_by_default` (`monkeypatch.setattr`, auto-restored) | pytest itself (`autouse=True`) | does not depend — the patched symbols are never invoked in `_request_with_retry`'s call graph; `SaaSTrackerClient` does not import `EventEmitter` or the batch/runtime consent predicates |
| E22 | `tests/sync/tracker/conftest.py::_patch_saas_token_bridges` (autouse, `:55-174`) — `monkeypatch.setattr`s `saas_client._fetch_access_token_sync`, `_current_team_slug_sync`, `_force_refresh_sync`, `AuthClient` (added `raising=False`), and `SaaSTrackerClient.__init__` itself (`_compat_init`) | `reset seam: _patch_saas_token_bridges` (`monkeypatch.setattr` × 5, auto-restored per test; function-scoped) | pytest itself (`autouse=True`, applies to every test under `tests/sync/tracker/`) | **depends — two independent limbs (expanded this revision, was understated)**. **Limb 1**: `SaaSTrackerClient.__init__` in production no longer accepts a `credential_store=` kwarg (per this fixture's own module docstring, `tests/sync/tracker/conftest.py:1-25`); the `client` fixture constructs `SaaSTrackerClient(credential_store=..., sync_config=..., timeout=5.0)` (`test_saas_client.py:109-115`). Without `_compat_init` (`:155-172`), that construction raises `TypeError` before the test body runs. **Limb 2**: `_compat_init` also injects `project_root=_consenting_project_root()` (`:163-167`) whenever the caller omits it, and `_consenting_project_root()` writes a real `.kittify/config.yaml` with `sync: enabled: true` (`:129-153`). Per the fixture's own docstring, `SaaSTrackerClient` now "refuses every request unless it has been told which project owns the data, and that project consents" — this is the `project_egress_refusal` chokepoint traced in Method §4. Without this second limb the `client` fixture would construct an unattributed, refusing client, and `_request_with_retry` would raise `TrackerEgressRefusedError` before reaching the mocked `httpx.Client`/`time.sleep` at all. **WP06 inherits only limb 1 if this row is read carelessly; both limbs are load-bearing.** |

## Mutable containers and import-time-bound paths in test fixture data — added this revision (HIGH finding)

Re-derived with the `ast.literal_eval` discriminator (Method §2). All 23
entries below are pure module-level test-fixture data — every symbol was
verified confined to exactly one file
(`grep -rl '\b<symbol>\b' tests/sync --include="*.py"` returns exactly one
path for each) and, for the mutable-container rows, verified to have **zero**
in-place mutation call sites in that file
(`grep -nE '<symbol>\s*(\.append|\.update|\.pop|\.clear|\.extend|\.add|\.remove|\[[^]]*\]\s*=)'`
— zero hits for every row). None is reachable from `test_429`'s executed call
path: it is not a Python object any of that path's modules import, and it
carries no OS-level side channel (no thread, no env var, no socket).

**Mutable containers** (`no reset seam` — the type permits in-place mutation
and nothing snapshots or restores it; none is currently mutated by anything
in its own file, so there is no *observed* leak, only an unwatched hazard):

| # | Module : symbol | Dependence |
|---|---|---|
| E28 | `tests/sync/test_consent_field_fault_3030.py::_UNUSABLE_ENABLED` (`:184`, `list[tuple[str, str]]`, built with a name-reference sub-expression so `literal_eval` fails even though the runtime type is `list`) | does not depend |
| E29 | `tests/sync/test_consent_field_fault_3030.py::_UNUSABLE_UUID` (`:364`, `list[tuple[str, str]]`) | does not depend |
| E30 | `tests/sync/test_consent_write_refusal_3030.py::_WRITER_IDS` (`:269`, `list`, built via a list comprehension) | does not depend |
| E31 | `tests/sync/test_daemon_intent_gate.py::ALLOWED_CALL_SITES` (`:230`, `set[str]`, literal set) | does not depend |
| E32 | `tests/sync/test_event_emission.py::_DONE_EVIDENCE` (`:86`, `dict[str, object]`; a nested `"a" * 40` sub-expression is why `literal_eval` fails on an otherwise-dict-literal structure) | does not depend |
| E33 | `tests/sync/test_history_import_pipeline.py::_LEGACY_WP_SPECS` (`:51`, `list[tuple]`, literal) | does not depend |
| E34 | `tests/sync/test_history_import_pipeline.py::_PREFIXED_WP_SPECS` (`:59`, `list[tuple]`, literal) | does not depend |
| E35 | `tests/sync/test_history_import_scan.py::_LEGACY_WP_SPECS` (`:230`, `list[tuple]`, literal — a same-named but independently-defined sibling of E33, not shared with `test_history_import_pipeline.py`; the two files' only cross-import is two unrelated helper functions, `:32-35`) | does not depend |
| E36 | `tests/sync/test_history_import_scan.py::_PREFIXED_WP_SPECS` (`:304`, `list[tuple]`, references `_PREFIXED_SLUG` so `literal_eval` fails) | does not depend |
| E37 | `tests/sync/test_mission_created_payload_parity.py::_FACTS` (`:33`, `dict[str, Any]`, literal) | does not depend |
| E38 | `tests/sync/tracker/test_origin_consumer.py::_DUMMY_META` (`:39`, `dict[str, Any]`, literal) | does not depend — same-directory as `test_saas_client.py` but confirmed confined to its own file |
| E39 | `tests/sync/tracker/test_saas_client_consent_gate_3030.py::_IDENTITY_PAYLOAD` (`:445`, `dict[str, Any]`) | does not depend — same-directory as `test_saas_client.py`; confirmed confined to its own file (not imported by `test_saas_client.py`) |
| E40 | `tests/sync/tracker/test_saas_client_consent_gate_3030.py::ENDPOINT_CALLS` (`:456`, `dict[str, Any]` of lambdas) | does not depend — same reasoning as E39 |
| E41 | `tests/sync/tracker/test_saas_client_discovery.py::PROJECT_IDENTITY` (`:81`, `dict[str, Any]`, literal) | does not depend |

**Import-time-bound paths** (`not reachable` — each is assigned exactly once
at import time via `Path(__file__).resolve()`/`tempfile.gettempdir()` plus
division, never reassigned afterward; the hazard this category names is a
fixed, process-lifetime-shared filesystem location, not in-place mutation of
the `Path`/`str` object itself):

| # | Module : symbol | Dependence |
|---|---|---|
| E42 | `tests/sync/test_daemon_cleanup_boundary.py::_DASHBOARD_PROJECT_PATH` (`:87`, `str(Path(tempfile.gettempdir()) / "test-boundary-project")`) — **added this revision (Medium finding)**: `test_daemon_cleanup_boundary.py` already contributes E4, but this constant was its own separate symbol, previously missing its own row | does not depend |
| E43 | `tests/sync/test_daemon_intent_gate.py::_THIS_FILE` (`:224`, `Path(__file__).resolve()`) | does not depend |
| E44 | `tests/sync/test_daemon_intent_gate.py::REPO_ROOT` (`:225`, derived from `_THIS_FILE`) | does not depend |
| E45 | `tests/sync/test_daemon_intent_gate.py::SRC_ROOT` (`:226`, derived from `REPO_ROOT`) | does not depend |
| E46 | `tests/sync/test_daemon_singleton_reaper_consolidation.py::_SRC_ROOT` (`:45`, `Path(__file__).resolve().parents[2] / "src" / "specify_cli"`) | does not depend |
| E47 | `tests/sync/test_history_import_synthesize.py::_REPO_ROOT` (`:36`, `Path(__file__).resolve().parents[2]`) | does not depend |
| E48 | `tests/sync/test_history_import_synthesize.py::_SPECS` (`:37`, derived from `_REPO_ROOT`) | does not depend |
| E49 | `tests/sync/test_history_import_synthesize.py::_LEGACY` (`:38`, derived from `_SPECS`) | does not depend |
| E50 | `tests/sync/test_history_import_synthesize.py::_PREFIXED` (`:39`, derived from `_SPECS`) | does not depend |

## `os.environ` and CWD mutation sites — added this revision (Medium finding)

The first draft had zero entries in two of its own eight named process-global
categories. Found by `grep -n 'os\.environ\['`/`os\.chdir\(` across the cone.

| # | Module : symbol | Reset seam | Caller | Dependence |
|---|---|---|---|---|
| E51 | `tests/sync/test_target_authority.py` — raw `os.environ["SPEC_KITTY_SAAS_URL"] = ...` writes (`:72, :158, :167, :177, :195, :211, :243`, 7 sites) | `no reset seam` — these are direct `os.environ[...] =` writes, not `monkeypatch.setenv`, so pytest's `monkeypatch` teardown never reverts them; the value is only **incidentally** cleared at the *start* of the next test that happens to use the `target_root` fixture (`:38-51`, `monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)`) — that is a side effect of the next test's setup, not a guaranteed teardown for this leak | nobody dedicated; `target_root`'s `monkeypatch.delenv` incidentally clears it, but only for tests that use that fixture, and only at their own setup | does not depend — `test_429`'s `client` fixture uses `mock_sync_config` (`test_saas_client.py:97-106`), a `MagicMock` whose `resolve_runtime_target.return_value.resolved_server_url` is hardcoded; `_base_url` (`saas_client.py:247`) is assigned from that mock's return value and never reads `os.environ["SPEC_KITTY_SAAS_URL"]` when the config is mocked |
| E52 | `tests/sync/test_target_authority_wiring.py` — raw `os.environ["SPEC_KITTY_SAAS_URL"] = ...` writes (`:115, :134, :180, :201, :224, :255`, 6 sites) | `no reset seam` (same mechanism as E51) | same as E51 | does not depend — same evidence as E51 |
| E53 | `tests/sync/test_capture_gate_project_identity_3030.py` — `os.chdir(cwd)` / `os.chdir(original)` pair (`:279`, `:290`) | `reset seam: manual try/finally: os.chdir(original)` (`:277-290`) | the test itself | does not depend — `project_egress_refusal`'s own docstring (`egress_consent.py:158-159`) states the checkout is resolved from an explicit `project_root`, "never the process's current working directory"; `test_429`'s `client` fixture supplies `project_root` explicitly via `_consenting_project_root()` (`tracker/conftest.py:131-153`), never derived from CWD |

## Excluded — module-level constants (re-derived discriminator)

Across the 138 scanned modules, module-level `Assign`/`AnnAssign` statements
were classified with `ast.literal_eval` as the mechanical discriminator
(Method §2), **not** by eyeballing which ones "look like" constants (the
first draft's method, which the review correctly found was falsified by its
own stated approach). Final split of all 296 bindings:

| Category | Count | Disposition |
|---|---|---|
| `pytestmark` (framework carve-out, verified never mutated) | 133 | excluded |
| `literal_eval` succeeds, immutable type | 121 | excluded |
| `literal_eval` succeeds, mutable type (`list`/`dict`/`set`) | 7 | included (E31, E33, E34, E35, E37, E38, E41) |
| `literal_eval` fails, mutable container by inspection | 7 | included (E28, E29, E30, E32, E36, E39, E40) |
| `literal_eval` fails, import-time-bound path by inspection | 9 | included (E42–E50) |
| `literal_eval` fails, computed but immutable by inspection | 16 | excluded |
| `literal_eval` fails, already tracked elsewhere (`CliRunner()` instances) | 3 | already counted (E17–E19) |
| **Total** | **296** | 270 excluded, 23 newly included, 3 already tracked |

The 16 "computed but immutable" exclusions, named individually so the
category is auditable rather than asserted: `_DUMMY_HASH` (×2 files, `"a" *
64`, `str`), `AUTO`/`MANUAL` (`test_config_background_daemon.py:15-16`, enum
member aliases), `_IDENT` (`test_consent_field_fault_3030.py:69`, f-string,
`str`), `_ULID_RE` (`test_emitter_mission_id.py:28`, `re.compile(...)`,
opaque immutable pattern object), `VALID_HASH`
(`test_events_namespace.py:27`, `str`), `_KNOWN_UUID`
(`test_history_import_identity.py:27`, `uuid.UUID(...)`, immutable/hashable),
`_PROJECT_UUID` (`test_history_import_synthesize.py:42`, same), `PRESERVED_COLUMNS`
(`test_journal_identity_backfill_3030.py:316`, `tuple(...)` over a generator
of strings — **the first draft's mis-labeled exemplar**, correctly excluded
but for the right reason this time: an immutable `tuple`, not "a frozen
literal"), `_MID8` (`test_lint_report_staging.py:165`, string slice, `str`),
`RETIRED_DRAIN_NAMES` (`test_no_queue_drain_constructed_3030.py:29`,
`frozenset(...)`, immutable by construction), `_DEFINING_MODULE`
(`test_no_queue_drain_constructed_3030.py:32`, `Path("specify_cli/sync/batch.py")`
— built from a **string literal**, not `__file__`, so it is a symbolic label
with a fixed value regardless of where the test runs, not an
import-time-bound *location*; kept distinct from the `Path(__file__)...` rows
above for that reason), `_TRUNCATED_RECORD`
(`test_owner_record_unreadable_3030.py:160`, string concatenation, `str`),
`_VALID_REFUSAL` (`test_routing.py:453`, `"\n".join(...)`, `str`),
`MISSION_SLUG` (`tracker/test_saas_client_consent_gate_3030.py:48`, f-string,
`str`).

## Cross-cone reference (not an in-scope entry)

The mission's designated control case —
`tests/specify_cli/invocation/test_propagator_consent_gate_3030.py`'s
`wiring` fixture, the known `reset_adapters()` leak — is **outside** the
`tests/sync/` cone. It is the answer WP05's leak guard is validated against
(control-your-diagnostic discipline), recorded here by reference only; it is
not counted in the totals below.

**This revision traces the mechanism precisely rather than citing it by
name only**: the control case clears
`src/specify_cli/invocation/adapters.py::_egress_consent_resolver` (via
`reset_adapters()` not being called) and additionally raw-sets
`os.environ["SPEC_KITTY_SYNC_MINIMAL_IMPORT"]` at `:102` of that file. Both
mechanisms were used in [Method §4](#method) to validate this revision's
corrected dependence rule: `_egress_consent_resolver` is the one real
chokepoint `test_429`'s own call path reaches, and
`grep -rln "reset_adapters\|_egress_consent_resolver\|register_egress_consent_resolver" tests/sync --include="*.py"`
confirms nothing in this cone touches it — the control case's leak lives
entirely in a different test directory.

## Per-bucket counts

**138 modules scanned; 29 files contribute an in-scope entry; 53 entries
total** (11 test-cone thread seams E1–E10 + E23, 4 known `daemon.py` seams
E11–E14, 2 `background.py` src-side thread/timer seams E24–E25, 2
`saas_client.py` measured negatives E15–E16, 2 canonical sync singletons
E26–E27, 3 `CliRunner` instances E17–E19, 3 `conftest.py` autouse fixtures
E20–E22, 14 mutable-container fixture-data entries E28–E41, 9
import-time-bound-path entries E42–E50, 3 `os.environ`/CWD mutation sites
E51–E53).

**Reset-seam classification** (53 entries):

| Bucket | Count | Entries |
|---|---|---|
| `reset seam: <name>` | 14 | E1, E2, E4, E5, E7, E8, E9, E20, E21, E22, E25, E26, E27, E53 |
| `no reset seam` | 27 | E3, E6, E10, E11, E12, E13, E17, E18, E19, E23, E24, E28, E29, E30, E31, E32, E33, E34, E35, E36, E37, E38, E39, E40, E41, E51, E52 |
| `not reachable` | 12 | E14, E15, E16, E42, E43, E44, E45, E46, E47, E48, E49, E50 |

`14 + 27 + 12 = 53`. ✓

**Dependence classification** (53 entries):

| Bucket | Count | Entries |
|---|---|---|
| `depends` | 1 | E22 (now recorded with both load-bearing limbs) |
| `does not depend` | 52 | all others |
| `undetermined` | 0 | — |

No entry is `undetermined`: every dependence verdict cites either a direct
read of `_request_with_retry`'s/`_request`'s/`project_egress_refusal`'s
bodies, a direct read of the `client` fixture's construction path, or a
reachability grep with zero hits — all now framed against the corrected,
process-path-tracing methodology (Method §4), not the import-graph rule the
review invalidated. Where those checks were inconclusive this inventory
would say `undetermined` rather than guess — none were, including after the
corrected methodology was applied to the 14 thread/singleton entries the
review specifically challenged.

## Review response

Independent review rejected the first draft on three HIGH findings, four
MEDIUM, and two LOW. Response, in the review's own order:

- **Vocabulary**: no change. The reviewer's coordinator note claiming this
  inventory should use `measured-yes`/`measured-no`/`unmeasured` was itself
  in error — `spec.md:555` and the WP file specify `depends` / `does not
  depend` / `undetermined`, which is what was used throughout. Nothing
  renamed.
- **HIGH 1 (exclusion falsified by the stated method)**: re-derived with
  `ast.literal_eval` as the explicit mechanical discriminator (Method §2).
  35 non-literal + 7 literal-but-mutable bindings were individually
  inspected; 23 are now entered (E28–E50), 16 remain excluded for a
  precisely-stated reason each, 3 were already tracked. `PRESERVED_COLUMNS`
  is kept as the discussion example, corrected to "excluded because it is an
  immutable `tuple`", not "excluded because it is a frozen literal."
- **HIGH 2 (two missing canonical singletons)**: `runtime.py::_runtime` and
  `background.py::_service` added as E26/E27, with their existing reset
  functions and the direct-mutation bypass sites the review named.
- **HIGH 3 (dependence evidence didn't support the verdict)**: the
  import-graph-disjointness rule is retired. The corrected rule (Method §4)
  traces `test_429`'s actual unmocked call path through `_request` →
  `project_egress_refusal` → `_egress_consent_resolver`, the one real
  chokepoint, and validates the rule against the control case by confirming
  the `tests/sync/` cone never touches that resolver. Every `does not
  depend` entry's evidence cell now cites this trace rather than an import
  check alone. No entry moved to `undetermined`; the corrected evidence
  supports every existing verdict.
- **MEDIUM 1 (`os.environ`/CWD had zero entries)**: added E51–E53.
- **MEDIUM 2 (13th `Thread(` hit unaccounted)**: added E23.
- **MEDIUM 3 (thread discovery was `tests/`-only)**: the method limit is now
  stated explicitly (Method §3), and extended to `background.py`'s two
  reachable seams (E24–E25).
- **MEDIUM 4 (`_DASHBOARD_PROJECT_PATH` uncounted)**: added as E42.
- **LOW 1 (`pytestmark` count predicate unstated)**: re-derived as **133**
  (not the first draft's 116), with the predicate stated (`ast.parse` + a
  top-level `tree.body` scan for `Assign`/`AnnAssign` nodes targeting
  `pytestmark`) and corroborated by
  `grep -rlE "^pytestmark" tests/sync --include="*.py" | wc -l` (also 133).
- **LOW 2 (E22 understated)**: both load-bearing limbs are now recorded
  (kwarg compatibility **and** consenting-project-root injection).

Confirmed sound by review and left unchanged: the `_daemon_harness.py:132`
subprocess-template exclusion, and the `saas_client.py` measured negative
(E15/E16).
