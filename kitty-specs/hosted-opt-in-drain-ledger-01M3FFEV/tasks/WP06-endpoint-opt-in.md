---
work_package_id: "WP06"
title: "Endpoint opt-in: no packaged fallback in resolver, explicit vs automatic caller split"
dependencies: []
requirement_refs: [FR-011, FR-012, C-006]
subtasks: [T026, T027, T028, T029, T030]
owned_files:
  - "src/specify_cli/auth/config.py"
  - "src/specify_cli/auth/server_target.py"
  - "src/specify_cli/auth/flows/**"
  - "src/specify_cli/auth/token_manager.py"
  - "src/specify_cli/auth/http/transport.py"
  - "src/specify_cli/cli/commands/_auth_saas_target.py"
  - "src/specify_cli/cli/commands/_auth_login.py"
  - "src/specify_cli/cli/commands/_auth_logout.py"
  - "src/specify_cli/cli/commands/_auth_doctor.py"
  - "src/specify_cli/saas_client/auth.py"
  - "src/specify_cli/tracker/saas_client.py"
  - "src/specify_cli/tracker/saas_readiness.py"
  - "src/specify_cli/tracker/egress_verdict.py"
  - "tests/auth/**"
  - "tests/cli/commands/test_auth_*.py"
  - "tests/cli/test_auth_saas_target_cleanup.py"
authoritative_surface: "src/specify_cli/auth/"
execution_mode: "code_change"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: "claude-sonnet-5"
---

# WP06: Endpoint opt-in — no packaged fallback in resolver, explicit vs automatic caller split

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Reverse #3980 D-5: remove the packaged live-endpoint fallback (`PACKAGED_DEFAULT`) from
`auth/server_target.py` and `auth/config.py::get_saas_base_url()` so a fresh install resolves the
hosted endpoint **only** from `SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url` (FR-011).
Split every caller of the resolver into **explicit** (raises `HostedEndpointUnconfigured` with
setup guidance, never a traceback) and **automatic/best-effort** (uses a new `_or_none` helper and
stays silent) per FR-012, and re-pin the ~21-file test blast radius that today asserts the packaged
default.

## Context

This WP is independent of WP01–WP05 (`dependencies: []`) — it touches only the auth/tracker
endpoint-resolution surface, disjoint from the drain/ledger posture work. WP07 depends on WP06: it
owns the migration (`m_4_0_0_retired_hosted_target.py`, D-6 session-issuer backfill) and the
remaining out-of-map test re-pins this WP does not own.

Key design decisions from `plan.md` D4, corrected by the **post-plan squad fold F-5/F-7 (m4)** —
**F-5/F-7 supersede D4's literal text where they conflict, and this WP follows the fold, not the
superseded D4 wording**:

- **Keep the `DEFAULT_HOSTED_SAAS_URL` name.** D4's own text called for renaming it to
  `CANONICAL_HOSTED_SAAS_URL`; F-7 (m4) overrides that: *"Keep the `DEFAULT_HOSTED_SAAS_URL` name.
  Only its fallback role goes, which reduces churn."* Do **not** rename the constant, its module
  docstring reference, or any of `is_canonical_hosted_url` / `is_noncanonical_first_party_url` /
  `is_retired_first_party_url`, which key off it purely as the *identity* of the first-party host
  (unrelated to its former fallback role). Only `get_saas_base_url()`'s fallback behaviour changes.
- **Resolver shape (F-5).** `resolve_server_target()` raises `HostedEndpointUnconfigured` (a new
  `ConfigurationError` subclass — see `auth/errors.py::ConfigurationError`) when neither source
  names a target. A new `resolve_server_target_or_none() -> ResolvedServerTarget | None` sibling
  returns `None` in that case instead of raising, for automatic/best-effort callers.
  `resolved_server_url` stays `str` on `ResolvedServerTarget` — there is **no** `UNCONFIGURED` enum
  member added to that dataclass; `data-model.md` was corrected on this point. Remove
  `OverrideMode.PACKAGED_DEFAULT` entirely (it becomes unreachable).
- **Guidance text is a module constant** (Sonar S1192, used ≥3×): exactly
  `"No hosted endpoint configured. Set SPEC_KITTY_SAAS_URL or [sync].server_url in <runtime-root>/config.toml."`
  with `<runtime-root>` substituted for the resolved absolute path from
  `specify_cli.paths.get_runtime_root().base` (spec.md Assumptions: "the guidance output prints the
  resolved absolute path").
- **C-006**: keep the `config.toml [sync].server_url` key name — do not rename it (D-4, out of
  scope).
- **R-2** (spec.md): `.kittify/saas-auth.json` `saas_url` (with its own token) and a
  `SPEC_KITTY_SAAS_URL` value sourced from a committed `.kitty.env` file both remain *explicit*
  operator configuration of the endpoint — this WP does not touch how those are read, only proves
  (with tests) that they are unaffected by removing the packaged fallback.

## Subtask T026: ATDD red-first — endpoint-unconfigured behaviour across every explicit/automatic surface

**Purpose**: Write the failing acceptance tests first, in their own commit, that pin down the whole
FR-011/FR-012/US4 contract before any resolver code changes. This is the red-first discipline the
charter's Quality & Tech-Debt Standing Orders require.

**Steps**:
1. In a new or extended test module under `tests/auth/` (e.g. `tests/auth/test_endpoint_opt_in.py`,
   new file — does not collide with any `owned_files` glob of another WP), write tests asserting,
   with no `SPEC_KITTY_SAAS_URL` set, no runtime-root `config.toml` `[sync].server_url`, and no
   `.kittify/saas-auth.json`:
   - `resolve_server_target()` raises `HostedEndpointUnconfigured`, a subclass of
     `specify_cli.auth.errors.ConfigurationError`.
   - The raised message names both `SPEC_KITTY_SAAS_URL` and the resolved absolute runtime-root
     `config.toml` path (use `specify_cli.paths.get_runtime_root().base / "config.toml"` in the
     test's own expected-string construction — never hardcode a path substring that would break
     under `SPEC_KITTY_HOME`).
   - `resolve_server_target_or_none()` returns `None` (no exception).
   - `get_saas_base_url()` raises the same `HostedEndpointUnconfigured` (it delegates through the
     resolver's config precedence now — see T027 for the exact composition).
2. Add CLI-level tests (extend `tests/cli/commands/test_auth_*.py` or add a new
   `tests/cli/commands/test_auth_endpoint_unconfigured.py`):
   - `spec-kitty auth login` with no endpoint configured exits non-zero, prints the guidance line,
     and makes **no** HTTP call (assert via a monkeypatched/forbidden `httpx`/transport call, or by
     asserting the command returns before any flow object is constructed).
   - `spec-kitty auth status` prints `"No hosted endpoint configured…"` (or the exact guidance
     text — match what T027 implements) with **no traceback** — today `_auth_saas_target.py:60-62`
     only catches `ServerTargetSplitBrainError`, so this assertion is the regression pin for that
     gap.
3. Add a test proving the **configured** path is unchanged: with `SPEC_KITTY_SAAS_URL` set (or
   `[sync].server_url` in a fixture-built runtime-root `config.toml`), `resolve_server_target()`
   returns the configured value, and the split-brain guard (`ServerTargetSplitBrainError`) still
   fires exactly as before when env and config disagree without a whole-process override — pin this
   with a small regression test reusing the existing split-brain fixture pattern in
   `tests/auth/test_server_target.py`.
4. Run this new test file/module and confirm it is **red** (fails against the current
   `PACKAGED_DEFAULT`-returning resolver) before touching implementation code.
5. Commit this red test file on its own, separate from the implementation commit in T027 —
   "Separate commit first" per the task brief; use a message like
   `test(auth): red-first pin for endpoint opt-in (FR-011/FR-012)`.

**Files**: `tests/auth/test_endpoint_opt_in.py` (new, ~120–160 lines),
`tests/cli/commands/test_auth_endpoint_unconfigured.py` (new, ~60–90 lines) or an addition to an
existing `test_auth_*.py` file.

**Validation**: `pytest tests/auth/test_endpoint_opt_in.py tests/cli/commands/test_auth_endpoint_unconfigured.py -v`
shows the new tests **failing** (red) before T027, and the commit for this subtask contains only
test files (no `src/` changes).

## Subtask T027: Resolver and config rewrite — remove the packaged fallback

**Purpose**: Implement the endpoint opt-in resolver shape (F-5) so the T026 tests go green: no
packaged default, `HostedEndpointUnconfigured` for explicit resolution, `_or_none` for automatic
resolution.

**Steps**:
1. `src/specify_cli/auth/config.py`:
   - Rewrite the module docstring (lines 1–13): replace the "the packaged default IS the target"
     framing with the opt-in model — env override or `config.toml`-configured target only; no
     built-in live address; a fresh install without configuration raises guidance. Reference this
     mission and FR-011/FR-012, and note the reversal of #3980 D-5 per US4.
   - **Keep `DEFAULT_HOSTED_SAAS_URL = "https://team.spec-kitty.ai"` under its current name** (F-7
     m4) — do not rename it. Update its docstring comment (currently lines 23–29) to describe it as
     the first-party host **identity** used by `is_canonical_hosted_url` /
     `is_noncanonical_first_party_url`, no longer a resolution fallback.
   - Rewrite `get_saas_base_url()` (~lines 123–150): it must no longer return
     `DEFAULT_HOSTED_SAAS_URL` when the env override is absent. Route it through the same
     no-fallback precedence as the resolver — either delegate to
     `specify_cli.auth.server_target.resolve_server_target().resolved_server_url` (careful: this
     would add a config.toml read where today's `get_saas_base_url()` is env-only; check every
     caller's expectation — `_targets_configured_saas()` in `auth/http/transport.py` and the two
     OAuth-flow constructors below already tolerate/expect an exception here, so widening its
     precedence to include `config.toml` is safe and arguably more correct) or keep it strictly
     env-only and raise `HostedEndpointUnconfigured` when the env override is unset. **Pick the
     strictly-env-only option** to keep this function's contract narrow and match its existing
     docstring ("env override or ... "); update the docstring to drop "packaged default" and state
     it raises `HostedEndpointUnconfigured` when `SPEC_KITTY_SAAS_URL` is unset. Do not change its
     token-path fencing warning (the paragraph about `refresh.py`/`token_manager.py` bypassing this
     accessor) — that guidance is unaffected by this change.
   - Add the guidance-text module constant (used ≥3×, Sonar S1192):
     ```python
     ENDPOINT_UNCONFIGURED_GUIDANCE = (
         "No hosted endpoint configured. Set SPEC_KITTY_SAAS_URL or "
         "[sync].server_url in {config_path}config.toml."
     )
     ```
     (or an equivalent single-source template) — reused by both `get_saas_base_url()` and
     `server_target.py`'s explicit resolver. Resolve `{config_path}` from
     `specify_cli.paths.get_runtime_root().base` at raise time (not import time — the runtime root
     can be `SPEC_KITTY_HOME`-overridden per invocation).
2. `src/specify_cli/auth/server_target.py`:
   - Import `ConfigurationError` from `specify_cli.auth.errors` and define:
     ```python
     class HostedEndpointUnconfigured(ConfigurationError):
         """Raised when neither SPEC_KITTY_SAAS_URL nor config.toml [sync].server_url names a hosted endpoint."""
     ```
   - Remove `OverrideMode.PACKAGED_DEFAULT` from the `OverrideMode` `StrEnum`.
   - Rewrite `_classify_override` (~lines 147–186): the `env_server_url is None and
     configured_server_url is None` branch no longer returns
     `(OverrideMode.PACKAGED_DEFAULT, DEFAULT_HOSTED_SAAS_URL)`. Instead, change the function's
     return type to `tuple[OverrideMode, str | None]` and return `(OverrideMode.NONE, None)` for
     that branch (or introduce a sentinel — pick whichever keeps `resolve_server_target`'s new
     unconfigured branch simplest; document the choice in a short comment), and have
     `resolve_server_target()` raise `HostedEndpointUnconfigured` immediately when the classified
     `resolved_server_url` is `None`, before constructing `ResolvedServerTarget` (whose
     `resolved_server_url` field stays `str`, never `None`, per F-5 — an unconfigured resolution
     never reaches that constructor call).
   - Add:
     ```python
     def resolve_server_target_or_none(*, process_wide_override: bool = True) -> ResolvedServerTarget | None:
         """Like resolve_server_target, but returns None instead of raising HostedEndpointUnconfigured.

         ServerTargetSplitBrainError still propagates — an ambiguous env/config
         disagreement is not "unconfigured", it is a real ambiguity a caller
         must not silently swallow (C-005/#4311 coupling: a future retry must
         not paper over a split-brain).
         """
         try:
             return resolve_server_target(process_wide_override=process_wide_override)
         except HostedEndpointUnconfigured:
             return None
     ```
   - Update the module docstring (lines 1–22) and `resolve_server_target`'s own docstring
     (~lines 226–239) to drop every "packaged default" / "opt-in era... resolves to the packaged
     launch host" claim and describe the raise-on-unconfigured contract instead. Update
     `_source_name_for_target`'s `"the default endpoint"` fallback branch (~line 269) — it is now
     unreachable from `resolve_server_target` (which raises before returning an unconfigured
     target) but is still called from display code that might hold a stale `ResolvedServerTarget`;
     leave the branch but note in a comment that it is dead for now, or remove it if nothing
     references it — verify with a repo-wide grep for `"the default endpoint"`.
   - `resolve_token_endpoint` / `_issuer_target_decision`: no signature change needed — they call
     `resolve_server_target(process_wide_override=False)` internally and will now propagate
     `HostedEndpointUnconfigured` (a `ConfigurationError`) instead of resolving to the packaged
     default. This is an explicit-caller path (token-bearing flows), so this propagation is
     correct per FR-012; confirm callers (T028) either handle it or are acceptable to let it
     propagate (all of `refresh.py`, `token_manager.py`, `websocket/token_provisioning.py`,
     `auth/flows/revoke.py` are explicit, user-triggered operations).

**Files**: `src/specify_cli/auth/config.py` (~40 lines changed), `src/specify_cli/auth/server_target.py`
(~60 lines changed).

**Validation**: The T026 red tests for `resolve_server_target`, `resolve_server_target_or_none`,
and `get_saas_base_url` go green. `ruff check` and `mypy` clean on both files.

## Subtask T028: Caller census — classify every consumer explicit vs automatic

**Purpose**: Walk every caller of `get_saas_base_url`, `resolve_server_target`, and
`resolve_token_endpoint` and make each one either propagate `HostedEndpointUnconfigured` with
guidance (explicit) or switch to `resolve_server_target_or_none()` / already-tolerant broad
`except` (automatic). Produce the classification table below as a comment block or short section at
the top of this WP's own test module (`tests/auth/test_endpoint_opt_in.py`) so reviewers can check
it against the diff — this table is the authoritative census artifact for this subtask.

**Steps**: verify and, where needed, change each of the 14 call sites below:

| # | File / call site | Today's shape | Classification | Action |
|---|---|---|---|---|
| 1 | `cli/commands/_auth_saas_target.py:61` `print_saas_endpoint()` | catches only `ServerTargetSplitBrainError` | **Explicit** (interactive status/whoami) | Add an `except HostedEndpointUnconfigured` branch printing `"No hosted endpoint configured…"` (the guidance text) instead of the resolved-URL line; return `None`, same as the split-brain branch. This closes the traceback risk research.md R4 names at these exact lines. |
| 2 | `cli/commands/_auth_login.py:113` `resolve_server_target()` | already wrapped in `except ConfigurationError` (dead code today — `resolve_server_target` never raised `ConfigurationError` before this WP; #4053 called the branch dead for a different reason) | **Explicit** | No code change needed — `HostedEndpointUnconfigured` is a `ConfigurationError` subclass, so the existing `except ConfigurationError` branch now becomes live and prints the guidance + exits 1. Add a regression test proving this (T026 covers `auth login`). Update the stale docstring/comment above it that says "the resolver fails closed... when neither source names a server" only in the historical/#179 sense — reword to state the current behaviour plainly. |
| 3 | `tracker/saas_client.py:330` `SaaSTrackerClient.__init__` | unguarded `resolve_server_target(process_wide_override=False).resolved_server_url` | **Explicit** (construction-time, mirrors the existing `project_root` resolution failure pattern a few lines above at `~314`) | Wrap in `try/except HostedEndpointUnconfigured as exc: raise SaaSTrackerClientError(str(exc), error_code="hosted_endpoint_unconfigured") from exc` — same shape as the `project_root_resolution_failed` guard already in this constructor. This is the "becomes a guarded error" instruction from plan.md D4. |
| 4 | `tracker/saas_readiness.py:195` `_probe_host_config()` | `except ServerTargetSplitBrainError: raise` / `except Exception: return None` | **Automatic** (already tolerant) | No code change — the existing broad `except Exception` already catches `HostedEndpointUnconfigured` and returns `None`. Add a verification test asserting this explicitly (not just via the broad-except's incidental coverage). |
| 5 | `saas_client/auth.py:342` `_resolved_server_target()` / `:360` `_server_target_url()` | both already `except Exception` / documented "any resolution trouble degrades to ''" | **Automatic** (already tolerant) | No code change — verification test only. |
| 6 | `cli/commands/_auth_doctor.py:436` (best-effort mismatch pre-check) | `except Exception: return None` | **Automatic** (already tolerant) | No code change — verification test only. |
| 7 | `cli/commands/_auth_doctor.py:474` `_check_server_session()` | `except ServerTargetSplitBrainError` then `except Exception: return ServerSessionStatus(active=False, error="SaaS URL not configured")` | **Automatic** (already tolerant, and its fallback message is already exactly right for this case) | No code change — verification test only; note the message is coincidentally already correct. |
| 8 | `cli/commands/_auth_logout.py:113` `_print_issuer_mismatch_warning()` via `resolve_token_endpoint(session)` | catches `IssuerTargetMismatchError`, `ServerTargetSplitBrainError`; no catch for a bare `ConfigurationError`/`HostedEndpointUnconfigured` | **Explicit** (interactive logout) | Add `except HostedEndpointUnconfigured` alongside the existing two, printing the same "revocation skipped" framing with the guidance text, so a logout on a machine whose endpoint became unconfigured (e.g. post-migration, see WP07) never tracebacks. |
| 9 | `auth/flows/revoke.py:54` `RevokeFlow.revoke()` via `resolve_token_endpoint(session)` | `except (IssuerTargetMismatchError, ServerTargetSplitBrainError): return RevokeOutcome.ISSUER_MISMATCH` | **Explicit**, but internal to an async, never-raises flow | Add `HostedEndpointUnconfigured` to that except tuple (folds into the same `ISSUER_MISMATCH`-shaped outcome — the caller (#8) already renders it via `resolve_token_endpoint` re-derivation, so no new `RevokeOutcome` member is needed; just widen the tuple so `revoke()` keeps its "never raises" contract). |
| 10 | `auth/token_manager.py:455,618` via `resolve_token_endpoint` | propagates whatever `resolve_token_endpoint` raises | **Explicit** (interactive refresh/session paths, called from CLI commands that already handle `ConfigurationError`-family exceptions at their own boundary) | Verify (do not silently swallow) — confirm each of the two call sites' own callers already handle a `ConfigurationError`-shaped exception with guidance; if a gap is found, add a narrow `except HostedEndpointUnconfigured` there instead of widening `token_manager.py`'s own contract. |
| 11 | `auth/flows/refresh.py:106` `resolve_token_endpoint(None)` | propagates | **Explicit** | Verify caller-side handling (refresh is triggered from `token_manager.py`, already covered by #10's check). |
| 12 | `auth/websocket/token_provisioning.py:112` `resolve_token_endpoint(session)` | propagates | **Explicit** | Verify caller-side handling; this path is reached from the device/websocket login flow, which already has explicit error handling at its CLI boundary — add a targeted test rather than new except clauses if none is needed. |
| 13 | `auth/http/transport.py:304` `_targets_configured_saas()` via `get_saas_base_url()` | `except Exception: return False` | **Automatic** (already tolerant) | No code change — verification test only. |
| 14 | `auth/flows/authorization_code.py:97` / `auth/flows/device_code.py:96` `get_saas_base_url()` fallback when `saas_base_url` param is `None` | unguarded, but **dead in practice**: `_auth_login.py` always passes `saas_base_url=saas_url` (the already-resolved target) at every construction site (lines ~222, ~281, ~323) | **Explicit**, dead-path-in-login | No code change — this is public constructor API for a caller that does not pre-resolve; if unconfigured it now raises `HostedEndpointUnconfigured` (correct, since it is an explicit-auth-flow entry point), which is a behaviour improvement over silently defaulting. Add a small direct-construction unit test (bypassing `_auth_login.py`) proving the raise. |

Also record, as a **one-line out-of-map note** (not an owned edit) in this WP's PR description and
at the top of the test module: `zeitgeist_client/resolution.py::_default_gateway` (owned by WP03)
was greped and found **not** to call `get_saas_base_url`, `resolve_server_target`, or
`resolve_token_endpoint` directly — it resolves its own gateway config independently. No action
needed from WP06; flag this finding for the WP03 implementer/reviewer to confirm it does not
separately assume a packaged default anywhere else in that module.

**Files**: the 14 files above, ~5–15 lines changed each where an action is listed (items 1, 3, 8, 9
require real code changes; items 4–7, 13, 14 are verification-only).

**Validation**: `spec-kitty auth login`/`logout`/`status`/`whoami`/`doctor`, the tracker client
constructor, and every flow above have at least one direct test exercising the
endpoint-unconfigured path and asserting no traceback (explicit) or silent `None`/tolerant fallback
(automatic), matching the table's classification exactly.

## Subtask T029: Re-pin the packaged-default test blast radius (R-2, DIRECTIVE_041)

**Purpose**: research.md R4 counts ~21 files / ~93 assertions of the packaged default across
`tests/auth/`, `tests/tracker/test_server_target_fail_closed.py`,
`tests/cli/commands/test_auth_*.py`, and the migration test. Judge each one individually — never
delete a valid behavioural assertion; re-pin only the ones that specifically assert the now-retired
`PACKAGED_DEFAULT`/fallback behaviour.

**Steps**:
1. `grep -rn "DEFAULT_HOSTED_SAAS_URL\|PACKAGED_DEFAULT" tests/auth/ tests/cli/commands/test_auth_*.py tests/cli/test_auth_saas_target_cleanup.py` to enumerate every hit inside this WP's `owned_files`. Known hits from the pre-work grep: `tests/auth/test_config.py`, `tests/auth/test_server_target.py`, `tests/auth/test_device_code_flow.py`, `tests/auth/test_authorization_code_flow.py`, `tests/auth/test_refresh_issuer_target.py`, `tests/auth/test_issuer_target_helper.py`.
2. For each hit, judge:
   - **Stale (re-pin)**: a test that asserts "with nothing configured, the resolved URL equals
     `DEFAULT_HOSTED_SAAS_URL`" or asserts `OverrideMode.PACKAGED_DEFAULT` — rewrite to assert
     `HostedEndpointUnconfigured` is raised (or `resolve_server_target_or_none()` returns `None`,
     matching whichever function the test exercises).
   - **Still valid**: a test that uses `DEFAULT_HOSTED_SAAS_URL` merely as a *value* to feed into
     `is_canonical_hosted_url`/`is_noncanonical_first_party_url`/`is_retired_first_party_url`, or
     as an explicitly-configured env/config value in a fixture (not asserting it is the *fallback*)
     — leave unchanged. Since the constant's name and identity role are unchanged (F-7 m4), most of
     these should need no edit.
3. Add new tests (do not just repurpose old ones) for the two R-2 sources staying explicit and
   unaffected by removing the fallback:
   - `.kittify/saas-auth.json` with a `saas_url` field and its own token still resolves without
     raising `HostedEndpointUnconfigured` (`saas_client/auth.py`'s own endpoint path, or wherever
     this WP's owned files read it — confirm with a grep of `saas-auth.json` reads inside
     `owned_files`; if the read lives in a file WP06 does not own, add the test in
     `tests/cli/test_auth_saas_target_cleanup.py`, which this WP does own, instead).
   - A `SPEC_KITTY_SAAS_URL` value sourced from a `.kitty.env` file (not a real env var) still
     resolves explicitly — reuse whatever `.kitty.env` fixture harness already exists in
     `tests/auth/` or `tests/cli/`; if none exists, build a minimal one (write a `.kitty.env` file
     to a temp dir, invoke the env-loading entry point the repo already uses for `.kitty.env`, then
     call `resolve_server_target()`).
4. Update `tests/cli/test_auth_saas_target_cleanup.py` for the same packaged-default assumptions if
   it makes any (check with the same grep in step 1 — it appeared in the owned_files list
   specifically because this file's name suggests it manages saas-target state cleanup around
   tests, and may reset/assert a default).

**Files**: the ~6 confirmed hit files above plus `tests/cli/test_auth_saas_target_cleanup.py`
(~10–40 lines changed per file, additive new tests where noted).

**Validation**: `pytest tests/auth/ tests/cli/test_auth_saas_target_cleanup.py -v` — every
previously-packaged-default-asserting test now asserts the opt-in behaviour; every
still-valid identity/canonical-URL test is untouched and still green.

## Subtask T030: Full validation sweep

**Purpose**: Confirm the whole endpoint-opt-in surface is green, typed, formatted, and that the
architectural egress-consent boundary still holds, and hand off a precise list of any red tests
that fall outside this WP's `owned_files` to WP07.

**Steps**:
1. Run the WP06-owned test surfaces:
   ```bash
   pytest tests/auth/ -v
   pytest tests/cli/commands/test_auth_login.py tests/cli/commands/test_auth_logout.py \
          tests/cli/commands/test_auth_status.py tests/cli/commands/test_auth_whoami.py \
          tests/cli/commands/test_auth_doctor.py -v   # match the actual test_auth_* filenames present
   pytest tests/cli/test_auth_saas_target_cleanup.py -v
   pytest tests/tracker/ -v
   pytest tests/specify_cli/saas_client/ -v
   ```
2. Run the architectural egress boundary, focused on the issuer-target allowlist sections research.md
   and plan.md F-7 reference:
   ```bash
   pytest tests/architectural/test_egress_consent_boundary.py -v
   ```
   Confirm no new allowlist entries are needed for `HostedEndpointUnconfigured` — it is raised
   *before* any network attempt, so it should not touch the allowlist at all; if the test suite
   disagrees, investigate rather than widen the allowlist.
3. Attempt `tests/zeitgeist_client/test_resolution.py` (owned by WP03, not this WP) purely as a
   read-only sanity check per the task brief — do not edit it. Record whether it is green or red in
   the PR description; if red, it is WP03's concern (per the out-of-map note in T028), not WP06's.
4. Quality gates on every file this WP touched:
   ```bash
   ruff check src/specify_cli/auth src/specify_cli/tracker src/specify_cli/saas_client \
              src/specify_cli/cli/commands/_auth_saas_target.py \
              src/specify_cli/cli/commands/_auth_login.py \
              src/specify_cli/cli/commands/_auth_logout.py \
              src/specify_cli/cli/commands/_auth_doctor.py tests/auth tests/cli/commands
   ruff format --check src/specify_cli/auth src/specify_cli/tracker src/specify_cli/saas_client tests/auth
   mypy src/specify_cli/auth src/specify_cli/tracker src/specify_cli/saas_client
   ```
5. `make test-fast`.
6. Compute and note in the PR the **out-of-map residual**: per the task brief, `tests/tracker/test_server_target_fail_closed.py`, `tests/specify_cli/saas_client/**` (beyond what step 1 already exercises as WP06-owned via its own `owned_files` glob — reconcile: `tests/specify_cli/saas_client/**` is listed as WP07's to re-pin per `wps.yaml`, even though `src/specify_cli/saas_client/auth.py` is WP06-owned; this WP may leave `tests/specify_cli/saas_client/**` and `tests/integration/test_spec_kitty_home_cli.py` red **only if** WP07 lands in the same lane sequence immediately after — name exactly which assertions in those files are red and why (expected: they assert the old packaged-default/migration-rewrite behaviour that WP07's migration change also touches) so WP07's implementer has a precise starting list instead of rediscovering it.

**Files**: no new files; command execution and PR-description bookkeeping only.

**Validation**: All WP06-owned test directories green; `ruff`/`mypy`/format clean; `make test-fast`
passing; the out-of-map residual list is written down (in the PR body) with file names and a
one-line reason for each.

## Definition of Done

- `DEFAULT_HOSTED_SAAS_URL` keeps its name in `auth/config.py` (F-7 m4) and its docstring is
  updated to describe it as a host-identity constant, not a fallback.
- `get_saas_base_url()` raises `HostedEndpointUnconfigured` when `SPEC_KITTY_SAAS_URL` is unset;
  it never returns `DEFAULT_HOSTED_SAAS_URL` as a silent fallback.
- `OverrideMode.PACKAGED_DEFAULT` is removed from `server_target.py`; `_classify_override` never
  produces a packaged-default resolution.
- `resolve_server_target()` raises `HostedEndpointUnconfigured(ConfigurationError)` with guidance
  naming `SPEC_KITTY_SAAS_URL` and the resolved absolute runtime-root `config.toml` path, when
  unconfigured; the split-brain guard (`ServerTargetSplitBrainError`) is unaffected and still
  fires on a genuine env/config disagreement.
- `resolve_server_target_or_none()` exists and returns `None` on the same unconfigured condition,
  while still propagating `ServerTargetSplitBrainError`.
- `ResolvedServerTarget.resolved_server_url` stays typed `str` (no `None`/`UNCONFIGURED` member
  added).
- All 14 caller sites in the T028 census are classified and, where the table lists an action,
  updated; the remainder carry a verification test proving the existing tolerant behaviour.
- `spec-kitty auth login` with no endpoint configured exits non-zero with the guidance line and
  makes no network call (US4 AS1).
- `spec-kitty auth status` (and `whoami`) print `"No hosted endpoint configured…"` with no
  traceback (US4 AS2; closes the `_auth_saas_target.py:60-62` gap named in research.md R4).
- With an endpoint configured via env or config, behaviour is unchanged from today, including
  precedence (env > config) and the split-brain guard (US4 AS3).
- The ~6 confirmed stale test files are re-pinned to the opt-in model; no valid behavioural
  assertion is deleted; two new tests cover R-2 (`.kittify/saas-auth.json` and `.kitty.env`-sourced
  `SPEC_KITTY_SAAS_URL` as explicit sources).
- `ruff check`, `ruff format --check`, and `mypy` report 0 issues on every touched file.
- The out-of-map residual for WP07 is named precisely in the PR body.

## Risks

- **`auth status` traceback risk (research.md R4, spec.md US4 AS2)** — the primary risk this WP
  exists to close. Mitigation: T026's red-first test pins the exact "no traceback" assertion before
  any implementation change, and T028 item 1 adds the missing `except HostedEndpointUnconfigured`
  branch to `_auth_saas_target.py::print_saas_endpoint()`.
- **Token refresh on already-logged-in machines** — a machine that authenticated while a packaged
  default (or a now-removed config value) was in effect could hit `HostedEndpointUnconfigured` on
  its next refresh if the endpoint becomes unconfigured later. The **D-6 session-issuer backfill**
  that prevents this (via the migration) is explicitly **out of scope for WP06** and owned by WP07
  (`plan.md` F-6). This WP must not attempt the backfill itself — only ensure the refresh path
  (`token_manager.py`, `refresh.py`) raises cleanly with guidance rather than a traceback when it
  does occur, so WP07's migration has a clean explicit-error contract to backfill against.
  Cross-reference in the PR description so a reviewer does not mistake WP06's silence on migration
  as an oversight.
- **Precedence regression in `get_saas_base_url()`** — choosing the strictly-env-only shape (T027
  step 1) versus routing through the full resolver changes which config sources it consults.
  Mitigation: T026's tests exercise both the env-only path and confirm no caller of
  `get_saas_base_url()` expects `config.toml [sync].server_url` to feed it (only
  `resolve_server_target()`/`resolve_token_endpoint()` callers expect that precedence) — verify
  this assumption against the T028 census before finalizing.
- **Sonar S1192 (repeated guidance string)** — mitigated by the single module constant in
  `auth/config.py`, reused by `server_target.py` rather than a second literal.
- **Overlap with WP07's `owned_files`** — `tests/specify_cli/saas_client/**` and
  `tests/integration/test_spec_kitty_home_cli.py` are WP07-owned per `wps.yaml`, but
  `src/specify_cli/saas_client/auth.py` is WP06-owned; a change to `auth.py`'s behaviour can turn
  WP07-owned tests red. Mitigation: T030 step 6 names the residual precisely instead of silently
  leaving it for someone to rediscover.

## Reviewer Guidance

- Confirm `DEFAULT_HOSTED_SAAS_URL` was **not** renamed anywhere (grep the whole diff for
  `CANONICAL_HOSTED_SAAS_URL` — it must not appear; that was D4's original, now-superseded
  instruction per F-7 m4).
- Confirm `HostedEndpointUnconfigured` is a `ConfigurationError` subclass (not a bare
  `RuntimeError` or a new unrelated hierarchy root) — this is what makes `_auth_login.py`'s
  pre-existing `except ConfigurationError` branch come alive for free.
- Confirm `ResolvedServerTarget.resolved_server_url` is still declared `str`, not `str | None`, and
  that no code path constructs it with `None`.
- Walk the T028 census table against the actual diff: every "Action" cell should correspond to a
  real, visible change; every "No code change" cell should correspond to a new verification test,
  not silence.
- Confirm no traceback reaches the terminal for `auth login`, `auth status`, `auth whoami`,
  `auth logout`, and `auth doctor` when run with `SPEC_KITTY_SAAS_URL` unset and no `config.toml`
  — actually run these commands in a scratch `SPEC_KITTY_HOME`, don't just trust the tests.
  guidance text; verify the tests actually construct that path via `get_runtime_root()` and not a
  hardcoded string.
- Check that the split-brain guard (`ServerTargetSplitBrainError`) tests were not accidentally
  weakened while touching `_classify_override` — split-brain and unconfigured are two distinct
  failure modes and must stay distinguishable in tests and in the exception hierarchy
  (`ServerTargetSplitBrainError` is not a `ConfigurationError` subclass; it stays its own
  `RuntimeError`).
- Verify the out-of-map residual note for WP07 is present and specific (file names + reasons), not
  a vague "some tests may fail."
- Confirm C-002 (no new `SYNC_`/`SAAS_`/`TEAMSPACE` identifiers) and C-006 (`[sync].server_url` key
  name unchanged) both hold in the diff.

## Implementation Command

```bash
spec-kitty agent action implement WP06 --agent claude
```
