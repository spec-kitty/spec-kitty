---
work_package_id: WP02
title: 'Relay edges: offer DRAIN_DISABLED, stream/history gates, drill, relay CLI and MCP guidance'
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- NFR-003
- C-005
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/zeitgeist_client/
create_intent:
- tests/zeitgeist_client/test_drain_relay_edges.py
- tests/cli/commands/test_zeitgeist_drain_guidance.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/zeitgeist_client/transport.py
- src/specify_cli/zeitgeist_client/filtered_stream.py
- src/specify_cli/zeitgeist_client/history.py
- src/specify_cli/zeitgeist_client/operability.py
- src/specify_cli/zeitgeist_client/mcp_stdio.py
- src/specify_cli/cli/commands/zeitgeist.py
- tests/zeitgeist_client/test_drain_relay_edges.py
- tests/cli/commands/test_zeitgeist_drain_guidance.py
role: implementer
tags: []
tracker_refs: []
---

# WP02: Relay edges — offer DRAIN_DISABLED, stream/history gates, drill, relay CLI and MCP guidance

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Gate every relay network edge owned by this WP — the control-channel `offer()`, the SSE
snapshot/watch stream, and the retained-history fetch — behind `hosted_posture.require_drain`
(or an equivalent pre-flight check), so that with drain off none of them opens a socket, spawns
a worker thread, or spends a credential read. Map the resulting `DrainDisabled` /
`OfferOutcome.DRAIN_DISABLED` signal to one clean guidance line everywhere a human or an agent
would otherwise see a network error or a raw traceback: the relay CLI subcommands, the MCP relay
tools, and the operability timeout drill.

## Context

This mission (`hosted-opt-in-drain-ledger-01M3FFEV`) makes every automatic hosted interaction
opt-in. WP01 (this WP's only dependency) lands the posture core in
`src/specify_cli/core/hosted_posture.py`: `drain_posture()`, `require_drain(context: str) ->
None` (raises `DrainDisabled(RuntimeError)` carrying a one-sentence human reason), a module-level
guidance-line constant, and autouse `drain_on` / `drain_off` fixtures wired into
`tests/zeitgeist_client/conftest.py` (WP01 also wires `tests/status/conftest.py` and
`tests/specify_cli/live_work/conftest.py`, which are out of this WP's scope). Read
`src/specify_cli/core/hosted_posture.py` before writing any test in this WP — it is the single
source of truth for the exception type, the `require_drain` signature and the guidance text; do
not re-derive or duplicate that text here.

**Plan sections that govern this WP** (`plan.md`; the "Post-plan squad folds" section
supersedes earlier plan text where the two disagree — this WP prompt already reflects the
fold):

- **F-1 (M1) relay gate placement** is the authoritative shape for this WP:
  - `budget.py` stays **stdlib-only** — it gets **no** `specify_cli.core` import, ever. Do not
    touch `budget.py` in this WP; `run_with_deadline`/`NoRedirects.build`/`OFFER_BUDGET_S` are
    untouched (`src/specify_cli/zeitgeist_client/budget.py:4-9` states the stdlib-only-port
    constraint explicitly).
  - The gate for `offer()` lives in `transport.ZeitgeistClient.offer`, **before**
    `budget.run_with_deadline` (currently around `transport.py:380-392` — verify the exact line
    against the live file, since line numbers drift). It returns a **new**
    `OfferOutcome.DRAIN_DISABLED` member so that no worker thread is spawned and the result is
    never misclassified as `DROPPED_UNREACHABLE`.
  - The gate for `filtered_stream.py`'s `seed_from_snapshot`/`watch` (around lines 253 and
    452-459 — they call `budget.NoRedirects.build()` directly) and `history.py`'s
    `read_history` (around line 191, the `budget.NoRedirects.build().open(...)` call) **raises**
    `DrainDisabled` at the top of the method, before any opener is built.
  - `operability.timeout_drill` reports `skipped: drain off` rather than a vacuous pass or a
    misleading fail.
  - Relay CLI commands map `OfferOutcome.DRAIN_DISABLED` / `DrainDisabled` to the one-line
    guidance from `hosted_posture`.
  - Cross-link: **#4737** names the same misdiagnosis class this WP closes (a clean skip being
    reported as a network failure) — cite it in review notes, do not resolve it separately.
- **Contract** (`contracts/hosted-posture.md`): "Drain off ⇒ `NoRedirects.build` and
  `SaasCapabilityGateway()` raise `DrainDisabled`; ... fan-out and producers return silently."
  and "CLI surfaces map `DrainDisabled` to one line: `Live drain is off (<reason>). Enable with:
  spec-kitty moments drain on [--repo]`." — reuse that exact guidance text/constant from
  `hosted_posture`, do not hand-roll a second copy of it (Sonar S1192 — the constant is already
  used ≥3× across this WP's files).
- **spec.md**: FR-004 (drain gates every automatic hosted egress, before any network or
  credential access), FR-005 (drain gates live subscriptions: `zeitgeist status/watch/activity/
  read/inbox`, history, and MCP equivalents — refuse with guidance, no live subscription
  established), FR-006 (drain off never degrades local work — every local command exits exactly
  as it would without hosted features), NFR-003 (0 network attempts, 0 credential-store/keyring
  reads with drain off; the gate reads at most 2 config files — that budget is spent inside
  `hosted_posture`, not duplicated here), C-005 (any live-publish retry, present or future, sits
  behind the same drain gate; drain-off is a clean skip, never a diagnostic-as-error).
- **research.md** / **data-model.md**: read them for the `DrainPosture`/`DrainDisabled` shape
  and the enumerated relay egress inventory if present, to confirm you are not missing an edge
  this WP owns.

**What this WP does NOT own** (do not touch these files even if the gate looks similar):
`resolution.py` (`SaasCapabilityGateway`, `resolve_credentials`, `resolve_focus_*` — WP03),
`status/adapters.py`, `events/runtime_moments.py`, `live_work/**`, `retrospective/
lifecycle_events.py`, `cli/commands/routes.py`, `cli/commands/live_work.py` (all WP03),
`status/views.py`, `status/emit.py`, `coordination/status_transition.py` (WP05), and the
architectural gate `tests/architectural/test_hosted_drain_gate.py` (WP04, which depends on this
WP). Stay inside `owned_files` above; a small, well-justified out-of-map edit is acceptable only
with a one-line rationale in the PR.

**Dependency**: WP01 must be merged/available before you start — `hosted_posture.require_drain`,
`hosted_posture.DrainDisabled`, and the `drain_on`/`drain_off` fixtures in
`tests/zeitgeist_client/conftest.py` are load-bearing imports for every subtask below. If WP01's
module shape differs from what this prompt describes, trust the live file over this prompt and
note the drift in your PR.

## Subtask T006: ATDD red-first — `tests/zeitgeist_client/test_drain_relay_edges.py`

**Purpose**: Write the failing acceptance tests first, in their own commit, before any
production-code change in T007-T009. This is the mission's ATDD-first discipline (C-011) and the
charter's red-first standing order — do not skip the red commit even though the target file is
new.

**Steps**:
1. Create `tests/zeitgeist_client/test_drain_relay_edges.py`. Import `hosted_posture` from
   `specify_cli.core.hosted_posture` and use the `drain_on`/`drain_off` fixtures WP01 wired into
   `tests/zeitgeist_client/conftest.py` (read that conftest first — confirm the fixture names and
   whether they are autouse or opt-in via a parameter).
2. **`offer()` gate, drain off**: construct a `transport.ZeitgeistClient` with a throwaway
   `ClientConfig` (mirror `operability._drill_config`'s shape — a fake `relay_url`/`token`, no
   real credential). Call `.offer("presence.publish", {...})` (or `.presence("command")`) under
   `drain_off`. Assert:
   - The result's `outcome` is the new `OfferOutcome.DRAIN_DISABLED`.
   - `elapsed_s == 0.0` (no network attempt was timed).
   - Patch `budget.run_with_deadline` (via `monkeypatch.setattr` on the `transport` module's
     imported name) to raise `AssertionError` if called, and patch `budget.NoRedirects.build` the
     same way — both must show **zero calls**.
   - No thread is spawned: assert `threading.active_count()` does not increase across the call
     (or patch `threading.Thread` in `transport`'s import surface and assert it is never
     constructed for this path — `run_with_deadline` is the only thread constructor on this path,
     so asserting it is never called already covers this; pick one assertion style and be
     explicit about which).
3. **`filtered_stream` gate, drain off**: build a `FilteredStream` with a throwaway
   `TeamStreamConfig`. Call `seed_from_snapshot(timeout_s=1.0)` and separately iterate one item
   from `watch(idle_timeout_s=1.0)` (wrap the generator's first `next()` in
   `pytest.raises(hosted_posture.DrainDisabled)`, since `watch` is a generator — the gate must
   fire before the generator's body runs any I/O, i.e. on first advance). Assert both raise
   `DrainDisabled`, and that `budget.NoRedirects.build` is never called (monkeypatch it to raise
   `AssertionError` if invoked, same technique as above).
4. **`history.read_history` gate, drain off**: call `history.read_history("host/owner/repo")`
   under `drain_off`. Assert it raises `DrainDisabled` **before** `credentials.load` is consulted
   — monkeypatch `history.credentials.load` to raise `AssertionError` if called, proving the gate
   sits ahead of the credential read (this is the concrete NFR-003 "0 credential-store reads"
   assertion for this file). Also assert `budget.NoRedirects.build`/`run_with_deadline` are never
   called.
5. **Drain-on parity**: repeat the `offer()` case under `drain_on` against a fake local HTTP
   server or a monkeypatched `budget.run_with_deadline` that returns a canned `DeadlineOutcome`
   (200, `b"{}"`) — assert the outcome is `OfferOutcome.SENT` (or whatever the canned status
   implies) and behaviour is byte-for-byte what it was before this WP (no regression). Do the
   same for `filtered_stream`/`history` at the level of "the gate does not fire and the method
   proceeds to build an opener" (mock the opener/response so the test does not need a real
   socket).
6. Run the new file: it MUST fail red at this point (`OfferOutcome.DRAIN_DISABLED` does not exist
   yet, `require_drain` is not called by production code yet). Commit this file alone with a
   message that names it as the red commit (e.g. `test(zeitgeist_client): red — drain gates the
   relay edges (WP02/T006)`).

**Files**: `tests/zeitgeist_client/test_drain_relay_edges.py` (new, ~180-240 lines).

**Validation**: `.venv/bin/python -m pytest tests/zeitgeist_client/test_drain_relay_edges.py -v`
shows every new test failing for the *expected* reason (missing enum member / gate not yet
present) — not an import error or a fixture-not-found error. Fix conftest/fixture issues before
moving on; a red test that fails for the wrong reason is not a valid ATDD baseline.

## Subtask T007: `transport.py` — `offer()` gate + `OfferOutcome.DRAIN_DISABLED`

**Purpose**: Make the `offer()` path itself refuse before any network attempt or thread spawn
when drain is off, without importing `specify_cli.core` into the stdlib-only `budget.py`.

**Steps**:
1. In `src/specify_cli/zeitgeist_client/transport.py`, add `DRAIN_DISABLED = "drain_disabled"`
   as a new member of `OfferOutcome` (a `StrEnum`), placed and documented alongside the existing
   members (`SENT`, `REJECTED`, `THROTTLED`, `DROPPED_BUDGET`, `DROPPED_UNREACHABLE`,
   `REFUSED_LOCAL`) with a one-line docstring comment matching their style, e.g. `# drain is off
   — refused before any network attempt (spec-kitty#4971)`.
2. Add the import `from specify_cli.core.hosted_posture import DrainDisabled, require_drain` (or
   the exact names WP01 exports — confirm against the live module) to `transport.py`. This is
   the correct layer for the import: `transport.py` is `specify_cli.zeitgeist_client`, which is
   downstream of `specify_cli.core` in the enforced dependency direction; `budget.py` is the one
   file in this package that must stay import-free of `specify_cli.core` (F-1/M1), and this
   subtask does not touch it.
3. In `ZeitgeistClient.offer`, insert the gate **immediately after** the existing
   `sanitizer.assert_clean(args)` try/except block (which already returns `REFUSED_LOCAL` before
   any network attempt) and **before** the `envelope = {...}` / `body = json.dumps(...)` /
   `budget.run_with_deadline(_post, ...)` sequence. Concretely:
   ```python
   try:
       require_drain("relay")
   except DrainDisabled:
       return OfferResult(outcome=OfferOutcome.DRAIN_DISABLED, request_id=request_id, elapsed_s=0.0)
   ```
   Locate the exact insertion point by reading the live `offer()` body — the prompt's line
   numbers (~380-392) are an approximation; anchor on the `sanitizer.assert_clean` block and the
   `envelope = {` line, not on line numbers.
4. Verify no other path inside `offer()` builds an opener or spawns a thread before this check —
   `request_id` generation/validation and `sanitizer.assert_clean` are pure/local and may stay
   ahead of the gate (they raise `ValueError`/return `REFUSED_LOCAL` with no network cost either
   way); everything from `envelope = {...}` onward must be strictly after the gate.
5. Do **not** modify `budget.py` in this subtask (or anywhere in this WP). If you find yourself
   tempted to move `OFFER_BUDGET_S` or add a hook there, stop — the gate belongs in `transport.py`
   only.
6. Confirm `OfferOutcome.DRAIN_DISABLED` is a distinct value from `DROPPED_UNREACHABLE` (FR-004's
   "before any network or credential access" + F-1's "never misclassified as
   DROPPED_UNREACHABLE") — any caller/logger reasoning about drop causes must treat it as a
   clean, expected skip, not an error.

**Files**: `src/specify_cli/zeitgeist_client/transport.py` (modify, +~15 lines).

**Validation**: Re-run `tests/zeitgeist_client/test_drain_relay_edges.py::*offer*` — the drain-off
assertions (outcome, `elapsed_s == 0.0`, zero calls to `run_with_deadline`/`NoRedirects.build`)
now pass; the drain-on parity assertions are unaffected (byte-identical `SENT`/`REJECTED`/etc.
behaviour). `ruff check src/specify_cli/zeitgeist_client/transport.py` and `mypy` on the same file
report 0 issues.

## Subtask T008: `filtered_stream.py` + `history.py` — pre-flight `require_drain`

**Purpose**: Gate the SSE snapshot/watch stream and the retained-history fetch at the top of each
network method, ahead of `budget.NoRedirects.build()`/credential resolution.

**Steps**:
1. In `src/specify_cli/zeitgeist_client/filtered_stream.py`, add
   `from specify_cli.core.hosted_posture import require_drain` (module-level import, alongside
   the existing `from . import budget, own_filter` line).
2. In `FilteredStream.seed_from_snapshot` (currently around line 251-253, right before
   `url = self._filter_own_url(...)` / `opener = budget.NoRedirects.build()`), add
   `require_drain("relay")` as the **first statement** in the method body — before the docstring's
   described behaviour begins any work. Let `DrainDisabled` propagate uncaught (do not catch it
   here); callers of `seed_from_snapshot` already propagate connection faults unchanged per its
   own docstring, so an uncaught `DrainDisabled` is consistent with that contract.
3. In `FilteredStream.watch` (currently around line 452-459, the generator method), add
   `require_drain("relay")` as the first statement **inside the generator body**, before
   `seed = _validated_seed_window(seed_window_s)`. Because `watch` is a generator function, the
   check only fires on the caller's first `next()`/iteration — confirm your T006 test asserts
   against that (advance the generator once, in a `pytest.raises` block, rather than asserting on
   the bare call to `watch(...)` which only constructs the generator object without running any
   of its body).
4. In `src/specify_cli/zeitgeist_client/history.py`, add the same import, and insert
   `require_drain("relay")` as the first statement of `read_history` (currently around line
   143-150, the function's docstring; the check must run before the existing validation of
   `filter_own`/`window_s`/`timeout_s`/`since` arguments is a judgment call — prefer running it
   **first**, ahead of even the argument validation, so a drain-off caller never needs valid
   arguments to get a clean, cheap refusal), and strictly before `credentials.load(repo=repo)` —
   this is the concrete "before any cache or keyring read" requirement from the contract and
   NFR-003.
5. Do not add a `try`/`except DrainDisabled` wrapper inside any of these three methods —
   `DrainDisabled` is meant to propagate to the caller (the CLI/MCP layer in T009 is where it
   gets translated to guidance); catching and swallowing it here would silently change behaviour
   for any caller that does not go through this WP's CLI/MCP surfaces.

**Files**: `src/specify_cli/zeitgeist_client/filtered_stream.py` (modify, +~6 lines),
`src/specify_cli/zeitgeist_client/history.py` (modify, +~4 lines).

**Validation**: The T006 `filtered_stream`/`history` drain-off assertions now pass, including the
"credential read never happens" assertion for `history.read_history`. The drain-on parity
assertions for both files still pass unchanged. `ruff check` + `mypy` on both files report 0
issues.

## Subtask T009: Drill, relay CLI and MCP guidance mapping

**Purpose**: Make every human- or agent-facing surface this WP owns turn `DrainDisabled` /
`OfferOutcome.DRAIN_DISABLED` into one clean line instead of a network error, a traceback, or a
misleading pass/fail.

**Steps**:
1. **`operability.py` — `timeout_drill`** (currently around lines 350-362): `timeout_drill` calls
   `client.presence("command")`, which now returns `OfferOutcome.DRAIN_DISABLED` under drain-off
   instead of a real drop. Read `TimeoutDrillResult`'s current shape (`outcome: str`, `offer:
   OfferSignal`, `drop: DropSignal`) and `OfferSignal.from_result`/`DropSignal.from_result`
   before changing anything. Add handling so that when the offer's outcome is
   `OfferOutcome.DRAIN_DISABLED`, `timeout_drill` returns `outcome="skipped: drain off"` (a
   distinct string, not `"pass"` or `"fail"` — a vacuous pass would misreport "the drop-no-retry
   contract holds" when no drop was actually exercised). Decide, and document inline, whether
   `OfferSignal`/`DropSignal` need a new case or whether the top-level `outcome` string alone
   carries this distinction — prefer the smallest change that keeps `RotationDrillResult`'s
   sibling shape (which already has its own `"pass"`-only convention) undisturbed. If a JSON/CLI
   report renders `TimeoutDrillResult.outcome`, verify it renders the new string legibly (no
   crash on an unrecognized value).
2. **`mcp_stdio.py` relay tools** (`zeitgeist_status`, `zeitgeist_watch`, `zeitgeist_send`,
   `zeitgeist_reply` — roughly lines 206-390): these currently let
   `subscription.NotCheckedOut`/connection faults propagate uncaught so FastMCP turns them into a
   tool-error result (see the module docstring's rationale). Do the same for `DrainDisabled`:
   do **not** add a broad `try/except Exception` — let `DrainDisabled` (raised inside
   `subscription.status`/`agent_watch`/`live_work.authored.send`/`reply`, which call down into
   this WP's gated `filtered_stream`/`history`/`transport` functions) propagate uncaught, so
   FastMCP reports a tool error carrying `DrainDisabled`'s one-line message. Read the module
   docstring's existing "propagate uncaught" convention (around lines 46-54 and 77-80) and match
   it exactly — this is consistency, not a new mechanism. If any of these four tool functions
   currently wraps the call in a broader `try/except` block that would swallow `DrainDisabled`
   silently into a generic error, narrow that except clause to exclude `DrainDisabled` (or
   `RuntimeError` if that is too broad already) so the message reaches the caller intact.
3. **`cli/commands/zeitgeist.py` — every relay subcommand** (`status`, `watch`, `activity`,
   `read`, `inbox`, `send`, `reply`, `outbox approve`): add one shared helper, e.g.
   `_report_drain_disabled(exc: DrainDisabled) -> None`, near the existing `_report_not_checked_out`
   / `_report_connection_fault` helpers (lines ~130-144), that prints the guidance line (reuse
   `hosted_posture`'s guidance constant verbatim — do not hand-roll the wording) via
   `console.print(str(exc), markup=False)` or the module's existing console helper, matching the
   style of the sibling `_report_*` helpers. Wire it into each subcommand's existing
   `try/except` chain:
   - `status` (~line 240-274): catch `DrainDisabled` and call the helper, then **return** (exit
     0) — `status` is a read/diagnostic command and the plan/contract call for it to exit 0.
   - `watch`, `activity`, `read`, `inbox`, `send`, `reply`, `outbox approve` (`outbox_approve`
     around line 733): catch `DrainDisabled`, call the helper, then `raise typer.Exit(1) from
     None` — these are action/subscription commands and exit non-zero, matching how they already
     handle `subscription.NotCheckedOut`/`AuthoredMessageError` (exit 1, no traceback).
   - Match the exact ordering/precedence these commands already use for `moments.MomentsDisabled`
     (which exits 0) versus `subscription.NotCheckedOut`/`ValueError`/connection faults (which
     exit 1) — add the new `except DrainDisabled` clause in a position that does not shadow or
     get shadowed by an existing broader `except` clause (e.g. a bare `except Exception`, if any
     exists nearby — there should not be one, but verify).
   - Also add the "status prints the drain line first" behaviour called for by plan D5/spec
     FR-007: when drain is off, `zeitgeist status`'s normal (non-error) output path — i.e. even
     when the command otherwise succeeds because it never needed to check drain for a pure local
     read — is out of this WP's scope if it requires touching `moments.py`/`hosted_posture`
     reporting internals owned by WP01/WP08; confine this WP strictly to catching
     `DrainDisabled` raised by the gated calls added in T007/T008. Do not implement the
     `moments drain status` command surface here — that is WP08.
4. Confirm no relay subcommand or MCP tool now produces a raw Python traceback for a drain-off
   invocation — every path in scope resolves to either the one-line guidance (CLI) or a
   structured tool-error message (MCP), matching FR-012's "never a traceback" standard applied to
   the drain case.

**Files**: `src/specify_cli/zeitgeist_client/operability.py` (modify, +~10 lines),
`src/specify_cli/zeitgeist_client/mcp_stdio.py` (modify, +~5-10 lines, likely just narrowing an
except clause or none at all if nothing currently swallows exceptions), `src/specify_cli/cli/
commands/zeitgeist.py` (modify, +~30-40 lines across the shared helper and its call sites).

**Validation**: New file `tests/cli/commands/test_zeitgeist_drain_guidance.py` (typer
`CliRunner`) exercises `status`, `watch`, `activity`, `read`, `inbox`, `send`, `reply`, `outbox
approve` under `drain_off`: assert each prints exactly one guidance line (no traceback, no stack
frame text), `status` exits 0, every other command exits 1. Add at least one direct unit test for
`operability.timeout_drill` under `drain_off` asserting `outcome == "skipped: drain off"`. Add at
least one MCP-level test (build the server per the existing MCP test pattern in this repo, call
`zeitgeist_status`/`zeitgeist_watch` under `drain_off`) asserting the call raises/returns a tool
error carrying the drain guidance text rather than a connection-fault message.

## Subtask T010: Validation — targeted tests, lint, type-check, fast tier

**Purpose**: Prove the whole WP is green in isolation and inside its blast radius before handing
it to review, per the project's test policy.

**Steps**:
1. Run the two new/changed test files directly first, to get a fast red/green signal:
   ```bash
   .venv/bin/python -m pytest tests/zeitgeist_client/test_drain_relay_edges.py \
     tests/cli/commands/test_zeitgeist_drain_guidance.py -v
   ```
2. Run the **full owning-subsystem directories** per CLAUDE.md's blast-radius rule (this WP
   touches `zeitgeist_client/` and `cli/commands/`):
   ```bash
   .venv/bin/python -m pytest tests/zeitgeist_client/ -q
   .venv/bin/python -m pytest tests/cli/commands/test_zeitgeist*.py -q
   ```
   Investigate and fix any regression in the existing `tests/zeitgeist_client/` suite this WP's
   changes caused (e.g. an existing test asserting `offer()`'s old drain-agnostic behaviour needs
   a `drain_on` fixture applied, since drain now defaults to off in an unconfigured test
   environment — WP01's `drain_on` fixture is meant to be applied wherever an existing test
   exercised a code path this WP now gates; confirm with WP01's conftest wiring which test
   modules already get it via autouse versus which need an explicit fixture request).
3. Run lint, format-check, and type-check on every file this WP touched:
   ```bash
   ruff check src/specify_cli/zeitgeist_client/transport.py \
     src/specify_cli/zeitgeist_client/filtered_stream.py \
     src/specify_cli/zeitgeist_client/history.py \
     src/specify_cli/zeitgeist_client/operability.py \
     src/specify_cli/zeitgeist_client/mcp_stdio.py \
     src/specify_cli/cli/commands/zeitgeist.py \
     tests/zeitgeist_client/test_drain_relay_edges.py \
     tests/cli/commands/test_zeitgeist_drain_guidance.py
   ruff format --check <the same file list>
   mypy <the same src/ file list>
   ```
4. Run the shared fast tier:
   ```bash
   make test-fast
   ```
5. Record every command run and its pass/fail counts under the PR's *Tests run* section,
   following the baseline-red gotcha in CLAUDE.md: classify any failure that is not yours (a
   pre-existing known-P0 red, a CI-environment-only failure, a stale install/venv symptom) before
   attributing it to this WP, and confirm a suspected pre-existing red is also red on
   `upstream/main`/the merge-base before excluding it.
6. In the PR description, cite **#4737** as the cross-linked issue this WP closes the
   misdiagnosis class for (a clean drain-off skip previously reading as a network failure), per
   the plan's F-1 note.

**Files**: none new — verification only.

**Validation**: All listed commands pass (0 failures attributable to this WP); `ruff`, `ruff
format --check`, and `mypy` report 0 issues on every touched file; `make test-fast` is green (or
any red is classified per the baseline-red gotcha and noted, not silently ignored).

## Definition of Done

- `OfferOutcome.DRAIN_DISABLED` exists in `transport.py` and is returned by `offer()` before any
  call to `budget.run_with_deadline`/`budget.NoRedirects.build` when drain is off; `elapsed_s ==
  0.0` for that outcome.
- `budget.py` carries no import of `specify_cli.core` (or any other `specify_cli` package) —
  verify with `grep -n "^import\|^from" src/specify_cli/zeitgeist_client/budget.py` before
  closing this WP.
- `FilteredStream.seed_from_snapshot` and `FilteredStream.watch` raise `DrainDisabled` before
  constructing an opener, when drain is off.
- `history.read_history` raises `DrainDisabled` before `credentials.load` is called, when drain
  is off.
- `operability.timeout_drill` reports a distinct `"skipped: drain off"` outcome under drain-off,
  never a false `"pass"` or `"fail"`.
- Every relay CLI subcommand this WP owns (`status`, `watch`, `activity`, `read`, `inbox`,
  `send`, `reply`, `outbox approve`) prints exactly one guidance line and exits with the
  documented code (0 for `status`, 1 for the rest) under drain-off — no traceback.
- Every relay MCP tool this WP owns (`zeitgeist_status`, `zeitgeist_watch`, `zeitgeist_send`,
  `zeitgeist_reply`) surfaces `DrainDisabled` as a structured tool-error, not a swallowed generic
  error, under drain-off.
- `tests/zeitgeist_client/test_drain_relay_edges.py` and `tests/cli/commands/
  test_zeitgeist_drain_guidance.py` exist, were red before the corresponding production change
  and are green after it (committed separately per ATDD-first).
- Drain-on behaviour for every gated function is unchanged (parity assertions pass).
- `ruff check`, `ruff format --check`, and `mypy` report 0 issues on every file this WP touched.
- `tests/zeitgeist_client/` and `tests/cli/commands/test_zeitgeist*.py` pass in full; `make
  test-fast` passes (or reds are classified per the baseline-red gotcha).
- Each subtask (T006-T010) has a `spec-kitty agent tasks mark-status <Txxx> --status done`
  event-sourced record — a ticked checkbox in this file is not sufficient evidence.

## Risks

- **Generator-timing risk in `FilteredStream.watch`**: the gate must fire on the first `next()`
  of the generator, not at the point `watch(...)` is called (which only constructs the generator
  object and runs no body code). A test that only calls `watch(...)` without advancing it will
  pass even if the gate is missing — silently vacuous. Mitigation: the T006 steps above make this
  explicit; do not shortcut it.
- **Line-number drift**: every line number cited in this prompt and in plan.md's F-1 fold (e.g.
  "transport.py ~380-392", "filtered_stream.py ~253, ~457", "history.py ~191") is approximate and
  may have shifted since the plan was written. Anchor every edit on the named function/statement
  (`sanitizer.assert_clean`, `budget.NoRedirects.build()`, `credentials.load(repo=repo)`), never
  on the line number alone.
- **Misclassifying `DrainDisabled` as an error in the MCP layer**: if a future refactor adds a
  broad `except Exception` around one of the four relay MCP tools, `DrainDisabled` would be
  swallowed into a generic error message and lose its guidance text. Mitigation: keep the
  "propagate uncaught" pattern this module already documents for `NotCheckedOut`, and call this
  out explicitly in the PR so reviewers watch for it.
- **`budget.py` import boundary regression**: it is tempting to centralize the gate inside
  `budget.NoRedirects.build()` itself (one place, covers every caller) — but that file must stay
  stdlib-only per F-1/M1 and the module's own constraint. Adding the check per-caller (as this
  prompt specifies) is more files touched but preserves the layering constraint; do not
  "simplify" this by importing `specify_cli.core` into `budget.py`.
- **Drill outcome string compatibility**: `"skipped: drain off"` is a new string value for
  `TimeoutDrillResult.outcome`, which was previously only `"pass"`/`"fail"`. Any existing
  caller/test that pattern-matches on those two literals needs updating — grep for
  `TimeoutDrillResult` and `outcome ==` across `src/` and `tests/` before finishing this subtask.
- **Cross-link #4737 misread as "resolve separately"**: the plan cites #4737 as the same
  misdiagnosis class this WP already closes by construction (drain-off returning a clean,
  distinct outcome instead of `DROPPED_UNREACHABLE`/a network-error-shaped message) — do not open
  new work against it; cite it as closed by this WP's change in the PR.

## Reviewer Guidance

- Confirm the gate really sits **before** any network primitive in all three production files —
  read `offer()`, `seed_from_snapshot()`, `watch()`, and `read_history()` end to end and trace
  every path from entry to the first socket-touching call, not just the diff hunk.
- Confirm `budget.py` was not touched and carries no new import — this is an explicit, named
  constraint (F-1/M1), not a style preference.
- Confirm the `FilteredStream.watch` generator test actually advances the generator (calls
  `next()` or iterates) rather than only calling `watch(...)` and asserting nothing — a test that
  never advances the generator would pass trivially regardless of whether the gate exists.
- Confirm `history.read_history`'s gate sits strictly before `credentials.load(repo=repo)` — this
  is the file's own concrete instance of the mission's "0 credential-store reads" NFR, and it is
  easy to accidentally place the gate after argument validation but after the credential load too
  if the diff is skimmed.
- Confirm no relay CLI subcommand or MCP tool in this WP's scope produces a raw traceback under
  drain-off — run each command manually with `SPEC_KITTY_HOME` pointed at a tmp dir with no
  `[hosted] drain` configured and no `hosted.drain` key in `.kittify/config.yaml`, and read the
  actual terminal output.
- Confirm the guidance text used in the CLI helper is the **same constant** `hosted_posture`
  exports for the operator surface (WP08 will build `moments drain [on|off|status]` against the
  same text) — a second, slightly different wording here would violate Sonar S1192 and confuse an
  operator who sees two different phrasings for the same condition.
- Confirm drain-on parity: every existing test in `tests/zeitgeist_client/` that exercised
  `offer()`/`seed_from_snapshot()`/`watch()`/`read_history()` before this WP still passes,
  applying the `drain_on` fixture where the conftest wiring requires it explicitly (rather than
  relying on autouse everywhere).
- Confirm the ATDD-first commit history: the test file(s) landed in their own commit before the
  production-code commits, and were genuinely red (not red for an unrelated import error) at that
  point.
- Confirm `spec-kitty agent tasks mark-status` records exist for T006-T010, not just a checked box
  in this markdown file.

## Implementation Command

```bash
spec-kitty agent action implement WP02 --agent claude
```
