---
work_package_id: WP07
title: Migration opt-in (retired target delete + D-6 session backfill) and remaining default-URL test re-pins
dependencies:
- WP06
requirement_refs:
- FR-013
- FR-011
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T031
- T032
- T033
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_hosted_endpoint_session_backfill.py
- tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0_retired_hosted_target.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_hosted_endpoint_session_backfill.py
- tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py
- tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py
- tests/tracker/test_server_target_fail_closed.py
- tests/specify_cli/saas_client/**
- tests/integration/test_spec_kitty_home_cli.py
role: implementer
tags: []
tracker_refs: []
---

# WP07 — Migration opt-in (retired target delete + D-6 session backfill) and remaining default-URL test re-pins

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Flip `m_4_0_0_retired_hosted_target.py`'s handling of the retired `app.spec-kitty.ai` value from
"rewrite to the packaged default" to "delete the key and tell the operator to configure an
endpoint" (FR-013), add a **new** sibling migration that backfills `[sync].server_url` from a
stored session's `issuer_url` when no endpoint is configured (D-6 / F-6), and re-pin every
remaining test in this WP's ownership that still asserts the retired "packaged default" fallback
WP06 removed (FR-011).

## Context

WP06 removed the packaged fallback from the resolver: `resolve_server_target()` now raises
`HostedEndpointUnconfigured` (a `ConfigurationError`) instead of silently binding
`DEFAULT_HOSTED_SAAS_URL` when neither `SPEC_KITTY_SAAS_URL` nor `[sync].server_url` is set.
`DEFAULT_HOSTED_SAAS_URL` is **kept as a name** (plan.md F-7 supersedes the earlier D4 text that
proposed renaming it to `CANONICAL_HOSTED_SAAS_URL`) — it stays the identity of the first-party
host, used by `is_canonical_hosted_url` and noncanonical warnings, and by anything that names the
live address explicitly. Only its role as an *implicit fallback* is gone.

This WP has two independent halves:

1. **The existing migration's behaviour changes (FR-013 / R-4).** Today, when a machine's saved
   `[sync].server_url` is exactly the retired first-party host `app.spec-kitty.ai`, the migration
   rewrites it to `DEFAULT_HOSTED_SAAS_URL` ("https://team.spec-kitty.ai"). Post-WP06, rewriting to
   a live address defeats the whole opt-in model — a machine that never asked for a hosted target
   would be silently pointed at one. Spec US4-AS4 scenario 4 and FR-013 require the stale key to be
   **deleted**, not rewritten, with guidance telling the operator to configure an endpoint
   explicitly. Spec R-4 / plan.md D4 confirm the companion invariant this WP must NOT touch: a
   machine whose config already carries the *canonical* value `team.spec-kitty.ai` (written by an
   earlier run of this same migration, before this WP's change) is left exactly as-is — that value
   is now explicit, opt-in configuration, and drain still defaults to off, so no automatic traffic
   results from it.
2. **A new decision, D-6 (plan.md F-6), needs new code.** When no endpoint is configured (neither
   env nor `[sync].server_url`) and a stored auth session carries a non-null `issuer_url`, the
   upgrade should backfill `[sync].server_url` from that `issuer_url`. A prior successful login is
   treated as explicit opt-in to that endpoint — drain itself stays off regardless (drain is a
   separate two-scope consent from WP01, untouched by this WP).

**Why D-6 needs a NEW migration module, not an edit to `m_4_0_0_retired_hosted_target.py`.** The
existing migration's `target_version` is pinned to `"4.0.0rc1"`, which has already shipped
(`docs/changelog/CHANGELOG.md` documents `[4.0.0rc1]` as released, and the installed package is
now `4.0.0rc5` per `pyproject.toml`). The upgrade runner records a migration as applied **per
project, keyed by `migration_id`**, and unconditionally skips it on every later run once recorded
(`src/specify_cli/upgrade/runner.py::_apply_migration`, `if metadata.has_migration(migration.migration_id): return ... "skipped"`).
Any project that already ran `4_0_0_retired_hosted_target` successfully in an earlier rc would
therefore **never** re-evaluate new logic added to that same migration's `apply()` — the D-6
backfill would be silently inert for every machine that already upgraded once. A new migration
module gets a fresh `migration_id`, so it is evaluated (and, if needed, applied) on every project's
next upgrade regardless of what that project already recorded for the retired-target migration.
Auto-discovery needs no manual registration list: `auto_discover_migrations()`
(`src/specify_cli/upgrade/migrations/__init__.py`) globs `m_*.py` and imports every match, firing
each module's `@MigrationRegistry.register` decorator on import.

The `apply()`/`detect()` split, the machine-scoped (not project-scoped) home-config path
resolution, and the atomic load-mutate-dump write pattern are already established by the existing
migration (`home_config_path()`, `_load_home_config()`, `atomic_write`) — the new migration reuses
that shape rather than reinventing it.

Downstream (WP08, docs/ADR) narrates this reversal of the #3980-era "packaged default" decision;
this WP's job is the code and the tests that prove it, not the doc.

## Subtask T031: ATDD red-first — migration behaviour tests

**Purpose**: Write failing tests first for both migration changes, per the mission's red-first
discipline, before touching `m_4_0_0_retired_hosted_target.py` or adding the new module.

**Steps**:
1. Read `src/specify_cli/auth/session.py` (`StoredSession`, `issuer_url: str | None`), the session
   store/loader it is read through (grep `tests/auth/**` and `src/specify_cli/auth/session*.py` /
   `token_manager.py` for how a session is loaded from disk — this WP does not invent a new session
   store, it reads the existing one read-only), and `src/specify_cli/auth/errors.py` for the
   `issuer_url` field shape already in play. **Never log or print token material** — only
   `issuer_url` (a bare URL, no secret) is read; DIRECTIVE_050 governs credential handling. Confirm
   the session loader used here does not require live network or a keyring read for a file-backed
   session fixture (NFR-003 adjacency — this migration must not introduce a network or keyring
   dependency at upgrade time).
2. In `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py`, rewrite the existing
   apply-path assertions for the **delete** behaviour (the old "rewrite to canonical" tests in
   `TestApply` — `test_apply_rewrites_retired_target_to_canonical`,
   `test_apply_preserves_unrelated_configuration`, `test_apply_is_idempotent` — are the ones to
   replace/adjust; do not delete `TestDetect`, which is unaffected):
   - `apply()` on a config whose `[sync].server_url` is the retired host **deletes** the
     `server_url` key from the `sync` table (table itself stays if other `sync` keys remain;
     removed entirely only if `server_url` was its sole key — confirm which behaviour is intended
     and assert it explicitly either way) and returns a `MigrationResult` whose `changes_made`
     names the deletion and points the operator at `SPEC_KITTY_SAAS_URL` /
     `[sync].server_url` (reuse or extend the guidance-text module constant this WP touches — see
     T032).
   - Unrelated keys/tables (`poll_interval`, `[telemetry]`, `[ui]`) survive byte-for-byte-semantic
     as today (`test_apply_preserves_unrelated_configuration` stays, only the target-value
     assertion changes from "== DEFAULT_HOSTED_SAAS_URL" to "server_url absent").
   - Idempotent: a second `apply()` after the key is gone is a no-op recording "nothing to
     migrate", identical in shape to the current `test_apply_is_idempotent`.
   - Add a new **R-4 non-regression test**: a config whose `[sync].server_url` is already
     `team.spec-kitty.ai` (the canonical value, as written by a *prior* run of the pre-WP07
     migration) is left completely untouched by `detect()` (`False`) and `apply()` (no-op,
     unmodified file) — `is_retired_first_party_url("https://team.spec-kitty.ai")` must be `False`
     (confirm this already holds by reading `auth/config.py`; write the test regardless as an
     explicit regression guard for R-4).
   - Update `test_migration_is_registered`, `test_target_version_does_not_exceed_package_version`,
     `test_chain_selects_migration_from_pre_4_upgrade` only if the migration's identity (`MIGRATION_ID`,
     `target_version`) changes — it should not; this migration keeps its existing ID/version, only
     `apply()`'s effect changes.
3. Add a new test module (or a clearly separated test class in a new file next to the existing one
   — match whatever module name T031/T032 picks for the new migration, e.g.
   `tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py`) covering D-6:
   - `detect()` is `True` only when: no `SPEC_KITTY_SAAS_URL` env, no `[sync].server_url` in
     config (or a config that fails to parse — treat unparseable as "not configured" but do
     **not** clobber the file), AND a stored session file exists with a non-null `issuer_url`.
   - `apply()` writes `[sync].server_url = <issuer_url>` into `config.toml`, preserving every
     other key/table (same load-mutate-dump/atomic-write discipline as the sibling migration).
   - `apply()` is a no-op when an endpoint is already configured (env OR config) — the explicit
     value wins, D-6 never overwrites it.
   - `apply()` is a no-op when no session file exists, or the session's `issuer_url` is `None`.
   - Drain stays off after the backfill: assert nothing this migration touches writes to the
     `[moments]` drain keys (WP01's posture files) — a backfilled endpoint is not a backfilled
     drain consent.
   - Idempotent: a second `apply()` after the backfill is a no-op.
   - Registration: the new migration is discovered by `MigrationRegistry` (mirrors
     `test_migration_is_registered`) and its `target_version` does not exceed the installed
     package version (mirrors `test_target_version_does_not_exceed_package_version`) — pin
     `target_version` to the current installed package version.
4. Confirm `TARGET_VERSION` for the new migration. Read `pyproject.toml`'s `version` field (see
   `test_target_version_does_not_exceed_package_version`'s pattern:
   `Version(migration.target_version) <= Version(<installed package version>)`); pin the new
   migration to that exact string (do not guess — read it from `pyproject.toml` at write time),
   following the established precedent (`m_3_2_6rc3_lint_report_gitignore_backfill.py`,
   `m_4_0_0_retired_hosted_target.py`) of pinning a migration's `target_version` to the
   already-shipping rc so it is selected via `MigrationRegistry.get_applicable`'s
   `target == from_v and detect()` branch for every machine already on that version, and via the
   normal `from_v < target <= to_v` window for anything upgrading from older versions.
5. Run both test files — everything new should fail red against the pre-change migration code and
   the not-yet-created new module; the R-4 non-regression test should already pass (it documents
   existing behaviour). Commit this red state separately, before T032 (per mission-wide red-first
   discipline).

**Files**: `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py` (edit, ~250–320
lines after edits), new `tests/specify_cli/upgrade/migrations/test_<new_migration_slug>.py`
(~150–200 lines).

**Validation**: `pytest tests/specify_cli/upgrade/migrations/ -k "retired_hosted_target or <new_migration_slug>" -q` — new/changed assertions red, everything else green; commit as a standalone red-first commit.

## Subtask T032: Implement the migration changes

**Purpose**: Make T031's tests pass — flip the existing migration to delete-and-guide, and add the
new sibling migration for the D-6 backfill.

**Steps**:
1. In `src/specify_cli/upgrade/migrations/m_4_0_0_retired_hosted_target.py`:
   - Rewrite the module docstring's opening paragraph: it currently documents "rewrite the retired
     ... target" and asserts the pre-WP06/D-5-reversal world as settled fact ("promoted
     `https://team.spec-kitty.ai` to the packaged default", "the machine's *saved* target is the
     canonical one"). Update it to describe the delete-and-guide behaviour this WP ships (FR-013):
     the retired value is removed, not replaced, because there is no packaged default to replace
     it with post-WP06; guidance points the operator at `SPEC_KITTY_SAAS_URL` /
     `[sync].server_url`. Preserve the parts of the docstring that remain true unchanged: the
     hostname-exact match via `is_retired_first_party_url`, "everything else in `config.toml` is
     preserved", "machine-scoped, not project-scoped", the `target_version` pin rationale.
   - Add the guidance-text module constant referenced in plan.md D4 (used ≥3× — Sonar S1192):
     `"No hosted endpoint configured. Set SPEC_KITTY_SAAS_URL or [sync].server_url in <runtime-root>/config.toml."`
     If `auth/server_target.py` (WP06) already defines this exact constant, import and reuse it
     instead of duplicating the string — check WP06's `HostedEndpointUnconfigured` guidance text
     before adding a second copy.
   - Change `apply()`: instead of `sync_table[_SERVER_URL_KEY] = DEFAULT_HOSTED_SAAS_URL`, delete
     `_SERVER_URL_KEY` from `sync_table` (`del sync_table[_SERVER_URL_KEY]` or `.pop(...)`). If the
     `sync` table becomes empty, decide (and document in the docstring/comment) whether to drop the
     now-empty table or leave it — prefer leaving an empty `[sync]` table in place over introducing
     TOML-shape churn beyond the one key, unless T031's tests require otherwise.
   - Update `changes_made` messages to reflect deletion + guidance instead of rewrite (e.g.
     `f"removed retired config.toml sync.server_url {stale_value}; {_GUIDANCE_TEXT}"`).
   - Remove the now-unused `DEFAULT_HOSTED_SAAS_URL` import if nothing else in the module needs it
     (the `description` class attribute referenced it for the rewrite target — update that text
     too, since it no longer describes a rewrite-to-canonical).
   - `MIGRATION_ID` and `target_version` stay unchanged — this is the same migration, changed
     behaviour, not a new one (unlike the D-6 backfill below).
2. Create the new sibling migration module (name it for what it does, e.g.
   `m_4_0_0rc5_hosted_endpoint_session_backfill.py` — match whatever `TARGET_VERSION` T031 pinned
   in the filename per the existing `m_<version>_<slug>.py` convention):
   - `MIGRATION_ID` distinct from every existing ID (grep `src/specify_cli/upgrade/migrations/*.py`
     for `migration_id = ` to confirm no collision — `MigrationRegistry.register` raises on
     duplicates).
   - `detect(project_path)`: machine-scoped like its sibling (`del project_path`); read the same
     `home_config_path()` this WP's other migration exposes (import it, do not duplicate the
     runtime-root resolution) plus `os.environ.get("SPEC_KITTY_SAAS_URL")` to establish
     "unconfigured", then read the stored session file for a non-null `issuer_url`. Read-only:
     never mutate the session file, never log its contents (DIRECTIVE_050).
   - `can_apply()` mirrors the sibling's `(bool, reason)` contract.
   - `apply()`: load-mutate-dump the same `config.toml`, writing `[sync].server_url = issuer_url`
     only when still unconfigured at apply time (re-check, do not trust a stale `detect()` result —
     matches the existing sibling's own re-derivation pattern in `apply()`). Atomic write via
     `kernel.atomic.atomic_write`, same as the sibling. Unparseable/missing config or session is a
     no-op, never a hard failure (matches `_load_home_config`'s fail-open-to-no-op contract for
     files this migration cannot safely understand).
   - `runs_on_worktrees = False` (machine-scoped, same reasoning as the sibling).
   - Docstring: state D-6 plainly — "a prior successful login counts as explicit opt-in to that
     endpoint; this migration does not touch drain posture, which stays off by default
     independently (WP01)."
   - Register via `@MigrationRegistry.register`; no manual registration list to update
     (auto-discovery globs `m_*.py`).
3. Run `pytest tests/specify_cli/upgrade/migrations/ -q` — both files green.
4. `ruff check`, `ruff format --check`, `mypy` on both new/changed source files — zero issues.

**Files**: `src/specify_cli/upgrade/migrations/m_4_0_0_retired_hosted_target.py` (edit, ~180–210
lines), new `src/specify_cli/upgrade/migrations/m_<pinned_version>_hosted_endpoint_session_backfill.py`
(~150–200 lines, mirroring the sibling's structure and comment density).

**Validation**: `pytest tests/specify_cli/upgrade/migrations/ -q`; `ruff check src/specify_cli/upgrade/migrations/`; `ruff format --check src/specify_cli/upgrade/migrations/`; `mypy src/specify_cli/upgrade/migrations/m_4_0_0_retired_hosted_target.py src/specify_cli/upgrade/migrations/m_<pinned_version>_hosted_endpoint_session_backfill.py`.

## Subtask T033: Re-pin remaining default-URL tests (this WP's ownership)

**Purpose**: WP06 removed the packaged fallback from the resolver; every test that still asserts
"unconfigured resolves to `DEFAULT_HOSTED_SAAS_URL`" for the files this WP owns is now testing
retired behaviour and must be re-pinned to the opt-in contract (raises
`HostedEndpointUnconfigured`, or resolves `None` via `resolve_server_target_or_none()`), per
DIRECTIVE_041 (judge each test: stale assumption → re-pin; genuine product gap → fix product, do
not paper over it).

**Steps**:
1. `tests/tracker/test_server_target_fail_closed.py`:
   - `test_saas_client_construction_without_host_binds_packaged_default` (~line 65): today asserts
     `client._base_url == DEFAULT_HOSTED_SAAS_URL` when unconfigured. Judge: this is exactly the
     packaged-fallback behaviour WP06 retired. Re-pin to assert construction now raises
     `HostedEndpointUnconfigured` (or whatever WP06's `SaaSTrackerClient` construction contract
     became — read `tracker/saas_client.py` post-WP06 before writing the assertion; plan.md D4
     says "`tracker/saas_client.py` construction becomes a guarded error"). Rename the test to
     drop "binds_packaged_default" language (it now asserts the opposite).
   - `test_evaluate_readiness_without_host_resolves_packaged_default` (~line 75): same judgment —
     read `tracker/saas_readiness.py` post-WP06 (plan.md D4: "`saas_readiness.py` ...already
     tolerate errors, so they only need a verification test") and re-pin to the actual
     unconfigured-readiness outcome (likely `MISSING_HOST_CONFIG`-shaped again, since the
     "resolves the packaged default" premise the docstring cites is gone). Update the test's
     docstring, which currently narrates the now-retired `#3980` behaviour as current fact.
   - Grep the rest of the file for any other `DEFAULT_HOSTED_SAAS_URL`/packaged-default assertions
     this WP owns and re-pin each on the same judgment.
2. `tests/specify_cli/saas_client/**`:
   - `test_client.py` lines ~138, ~283, ~314: each asserts `ctx.saas_url == DEFAULT_HOSTED_SAAS_URL`
     for an unconfigured context. Read the surrounding test to see whether it is *specifically*
     testing "what happens when unconfigured" (re-pin to the raise/`None` contract) or merely using
     an unconfigured fixture as convenient setup for something else (in which case, configure it
     explicitly instead of relying on the retired fallback, so the test keeps testing what it meant
     to test).
   - `test_held_token_non_demotion.py`: `_LEGIT_ISSUER = "https://team.spec-kitty.ai"` is a fixture
     constant, not a fallback assertion — leave it if the session/token logic under test does not
     depend on the packaged-fallback resolver path; if any assertion in the file does depend on
     unconfigured-resolves-to-default, re-pin it the same way as above. State the disposition
     explicitly in the PR even if "no change needed."
   - `test_decision_widen_ownership_3111.py`: grep for `DEFAULT_HOSTED_SAAS_URL`/packaged-default
     assertions; re-pin any found, same judgment.
3. `tests/integration/test_spec_kitty_home_cli.py` (~lines 111, 126): asserts
   `target.resolved_server_url == "https://team.spec-kitty.ai"` for an unconfigured
   `SPEC_KITTY_HOME`. Re-pin to the opt-in contract — construct the resolution call so it either
   asserts the raise, or explicitly configures an endpoint first and asserts that value is honored
   (whichever the surrounding test intent calls for; read the full test before choosing).
4. **Sweep the rest of the tree for leftover fallback assertions not owned by WP06's own
   `owned_files`.** WP06 owns `tests/auth/**`, `tests/cli/commands/test_auth_*.py`,
   `tests/cli/test_auth_saas_target_cleanup.py` — do not touch those (WP06's responsibility). Run:
   ```
   grep -rln "DEFAULT_HOSTED_SAAS_URL\|team\.spec-kitty\.ai\|PACKAGED_DEFAULT" tests/ \
     --include="*.py" | sort
   ```
   Cross-reference the result against WP06's `owned_files` and this WP's `owned_files`. For every
   hit in neither list, list it explicitly in the PR description under a "leftover fallback
   assertions found outside WP06/WP07 ownership" heading with a disposition (leave as legitimate
   fixture constant / flag as a gap for a follow-up issue) — do not silently edit files this WP
   does not own; file the gap instead (CLAUDE.md "Use Canonical Sources" — trace and report,
   don't improvise a fix outside scope).
5. Run the full validation sweep listed below.

**Files**: `tests/tracker/test_server_target_fail_closed.py` (edit, targeted),
`tests/specify_cli/saas_client/test_client.py`,
`tests/specify_cli/saas_client/test_held_token_non_demotion.py`,
`tests/specify_cli/saas_client/test_decision_widen_ownership_3111.py` (edit only where the grep
sweep finds a hit), `tests/integration/test_spec_kitty_home_cli.py` (edit, targeted).

**Validation**:
```
pytest tests/tracker/test_server_target_fail_closed.py tests/specify_cli/saas_client/ \
  tests/integration/test_spec_kitty_home_cli.py tests/specify_cli/upgrade/ -q
ruff check tests/tracker/test_server_target_fail_closed.py tests/specify_cli/saas_client/ \
  tests/integration/test_spec_kitty_home_cli.py tests/specify_cli/upgrade/
ruff format --check tests/tracker/test_server_target_fail_closed.py tests/specify_cli/saas_client/ \
  tests/integration/test_spec_kitty_home_cli.py tests/specify_cli/upgrade/
make test-fast
```

## Definition of Done

- `m_4_0_0_retired_hosted_target.py` deletes (never rewrites) a retired `app.spec-kitty.ai`
  `[sync].server_url`, emits operator guidance naming `SPEC_KITTY_SAAS_URL` /
  `[sync].server_url`, preserves every unrelated key/table, and remains idempotent (FR-013).
- A machine whose config already carries the canonical `team.spec-kitty.ai` value is left
  completely untouched by both migrations (R-4 non-regression, explicitly tested).
- A new sibling migration backfills `[sync].server_url` from a stored session's `issuer_url` only
  when no endpoint is configured, never overwrites an explicit value, never touches drain posture,
  and is idempotent (D-6 / F-6).
- The new migration has its own `migration_id`, is auto-discovered, does not collide with any
  existing ID, and its `target_version` does not exceed the installed package version.
- All T031 red tests pass green after T032; the red-first commit and the implementation commit are
  separate commits.
- `tests/tracker/test_server_target_fail_closed.py`, `tests/specify_cli/saas_client/**`, and
  `tests/integration/test_spec_kitty_home_cli.py` no longer assert the retired packaged-fallback
  resolution for unconfigured hosts; each re-pin is justified (DIRECTIVE_041) not just silenced.
- A sweep for `DEFAULT_HOSTED_SAAS_URL` / `team.spec-kitty.ai` / `PACKAGED_DEFAULT` across `tests/`
  is recorded in the PR with a disposition for every hit outside WP06's and this WP's ownership.
- `spec-kitty agent tasks mark-status <Txxx> --status done` recorded for T031, T032, T033.
- Zero `ruff`, `ruff format --check`, and `mypy` issues on touched files; `make test-fast` plus this
  WP's blast-radius directories (`tests/specify_cli/upgrade/`, `tests/tracker/`,
  `tests/specify_cli/saas_client/`, `tests/integration/`) pass, with exact commands and
  passed/failed counts recorded under the PR's *Tests run* section.

## Risks

- **Retrofitting D-6 onto the existing migration instead of a new one would be silently inert** for
  every project that already recorded `4_0_0_retired_hosted_target` as applied
  (`metadata.has_migration`). Mitigation: this WP mints a new `migration_id` specifically to avoid
  that trap — do not collapse the two into one module under time pressure.
- **Session-file read touching credential material.** The backfill only reads `issuer_url`, never
  a token. Mitigation: keep the read scoped to the typed session model's `issuer_url` field, never
  log the raw session payload, and add a test asserting no token value appears in any
  `MigrationResult.changes_made`/warning string.
- **Empty `[sync]` table after deletion** could change TOML round-trip shape in a way a downstream
  reader does not expect (e.g. a resolver code path that assumes `sync_table` is always non-empty
  once present). Mitigation: T031 tests the empty-table case explicitly; verify no other caller in
  `src/specify_cli/auth/` chokes on a present-but-empty `[sync]` table before deciding to leave it
  versus dropping it.
- **Re-pinning `tests/specify_cli/saas_client/**` too broadly** risks masking a genuine WP06
  regression as "expected new behaviour." Mitigation: judge each hit individually per DIRECTIVE_041
  and read the surrounding test's intent before changing its assertion, rather than doing a
  find-and-replace of `DEFAULT_HOSTED_SAAS_URL` across the file.
- **Migration ordering on a single upgrade run.** If a machine both has a retired
  `app.spec-kitty.ai` value AND a session with `issuer_url` set, the two migrations could interact
  (the delete migration removes the key; the backfill migration then sees "unconfigured" and writes
  the session's `issuer_url`). Confirm via `MigrationRegistry.get_applicable`'s ordering (sorted by
  `target_version`) that the delete-migration's `target_version` sorts before (or is independent
  of) the backfill migration's, and add an integration-style test exercising both in sequence
  within one upgrade run to confirm the end state is "backfilled from session," not "stuck deleted."

## Reviewer Guidance

- Confirm the new migration module truly is a **new** `MIGRATION_ID`/module, not an edit that
  reuses `4_0_0_retired_hosted_target`'s ID — this is the single most important structural check
  for this WP, given the already-applied-migration skip trap explained in Context.
- Confirm `apply()` on the existing migration **deletes**, not rewrites-to-canonical — re-read the
  diff against FR-013 and US4-AS4 scenario 4 line by line; a leftover
  `sync_table[_SERVER_URL_KEY] = DEFAULT_HOSTED_SAAS_URL` anywhere is the exact bug this WP exists
  to fix.
- Confirm the R-4 non-regression case (`team.spec-kitty.ai` already configured) is asserted
  untouched by both migrations, not just the retired-value path.
- Confirm the session-issuer backfill never logs or surfaces token material, and never turns drain
  on as a side effect.
- Confirm every re-pinned test in T033 carries a one-line rationale (in the test docstring or the
  PR body) for why the old assertion was stale rather than a real regression, per DIRECTIVE_041.
- Confirm the T033 sweep for leftover `DEFAULT_HOSTED_SAAS_URL`/`team.spec-kitty.ai` hits outside
  WP06/WP07 ownership is present in the PR with an explicit disposition per hit, not silently
  dropped.
- Confirm red-first: the T031 commit predates the T032 implementation commit in the branch history.

## Implementation Command

```bash
spec-kitty agent action implement WP07 --agent claude
```
