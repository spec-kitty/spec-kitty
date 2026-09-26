---
work_package_id: "WP08"
title: "Operator surface (moments drain), ADR, docs, changelog"
dependencies: ["WP02", "WP03", "WP05", "WP07"]
requirement_refs: ["FR-007", "FR-014", "FR-015"]
subtasks: ["T034", "T035", "T036", "T037"]
owned_files:
  - "src/specify_cli/cli/commands/moments.py"
  - "tests/cli/commands/test_moments_drain.py"
  - "docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md"
  - "docs/api/configuration.md"
  - "docs/api/environment-variables.md"
  - "docs/context/team-kitty.md"
  - "docs/changelog/CHANGELOG.md"
authoritative_surface: "src/specify_cli/cli/commands/moments.py"
execution_mode: "code_change"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: "claude-sonnet-5"
---

# WP08: Operator surface (moments drain), ADR, docs, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Give the operator a visible, one-command way to inspect and set the two-scope drain posture
(`spec-kitty moments drain on|off|status`), and land the governance record for the whole mission:
the ADR reversing #3980 D-5, plus the configuration/environment-variable/Team-Kitty-context docs
and the changelog entry that bring the docs in line with the opt-in model this mission ships.

## Context

This is the last WP in the mission (depends on WP02 relay edges, WP03 capability/fan-out, WP05
ledger, and WP07 migration+endpoint-opt-in re-pins) because its CLI surface reports the posture
those WPs implement, and its docs/ADR describe behavior that must already exist in code. By the
time this WP runs:

- `core/hosted_posture.py` (WP01) exposes `drain_posture()` / `ledger_posture()` /
  `set_personal_drain(bool, *, home=None)` / `set_repo_drain(bool, *, project_root=None)`, and a
  `DrainPosture` dataclass carrying the effective boolean plus **per-scope provenance**: repository
  value + source file, personal value + source file, and whether an env narrower overrode it.
- `core/toml_table.py` (WP01) is the shared atomic-TOML-table rewrite helper, extracted from
  `zeitgeist_client.moments.write_agents_mode` (plan §F-7 m3) — reuse it for the personal-scope
  writer rather than hand-rolling a second TOML round-trip.
- WP02/WP03 wire the actual gates (`DrainDisabled`, `OfferOutcome.DRAIN_DISABLED`, the one-line CLI
  guidance `Live drain is off (<reason>). Enable with: spec-kitty moments drain on [--repo]`
  documented in `contracts/hosted-posture.md`); this WP's `moments drain status` surfaces the same
  posture object, it does not recompute it.
- WP07 removes the packaged hosted-endpoint default and finishes the auth/tracker re-pins.

**Governing decisions from spec.md and plan.md** (do not relitigate — record and implement them):

- **D-1**: drain lives in *both* `.kittify/config.yaml` (`hosted.drain`, repository opt-in) and the
  developer's runtime-root `config.toml` (`[hosted] drain`, personal activation, D-5). Effective
  drain requires both on; either off/absent ⇒ off.
- **D-2**: the ledger flag (`ledger.projection` in `.kittify/config.yaml`, default on) only gates
  automatic refresh of the gitignored execution-state projection — never the lane ledger, its
  commit, the committed status snapshot, the decision ledger, the run journal, or invocation
  records (the "ledger floor", FR-010).
- **D-3 / FR-012**: explicit hosted commands stop with setup guidance naming
  `SPEC_KITTY_SAAS_URL` and `config.toml [sync].server_url` when no endpoint is configured;
  automatic paths stay silent.
- **D-4 / C-006**: `[sync].server_url` keeps its name — do not rename it here.
- **D-5**: the personal activation file is the **runtime-root** `config.toml`
  (`~/.spec-kitty/config.toml` on POSIX, `SPEC_KITTY_HOME`-overridable) — *not*
  `~/.kittify/config.toml`, which is where `[moments]` already lives. `moments drain status` must
  print the resolved absolute path of every file it reads, including this one (plan §F-7 minors:
  "prints all four hosted-posture files").
- **R-1**: no environment variable can *enable* drain in either scope; env only narrows
  (`SPEC_KITTY_NO_MOMENT_HANDLERS`, `SPEC_KITTY_SYNC_DISABLE`, `[moments] agents = "off"` still win
  when drain is on). Say this plainly in `drain on`'s help text.
- **R-4**: machines that already have `team.spec-kitty.ai` from the earlier migration keep it as an
  explicit value; drain still defaults off, so no automatic traffic follows from that alone.
- **FR-014 / research.md R4**: the ADR this WP writes is the *first* record of the D-5 (#3980)
  reversal — mission `team-kitty-launch-defaults-01M1XJ4Y` WP01 planned a
  `2026-09-07-1-packaged-hosted-target-default.md` ADR that was **never written**. Do not assume
  that file exists or try to amend it; this WP's ADR is the sole record covering both the original
  packaged-default decision being reversed and the new two-scope drain consent model.

**Terminology discipline** (Terminology Canon in `CLAUDE.md`, and the "sync is dead" doctrine in
`docs/context/team-kitty.md`): never call this feature "sync", never introduce a
`SYNC_`/`SAAS_`/`TEAMSPACE_` identifier (C-002), and use "Mission" not "feature" throughout every
doc and code comment you touch.

**Read before writing code:**
- `src/specify_cli/cli/commands/moments.py` (existing pattern to extend — `moments_app`,
  `_resolve_scope`, `_REPO_SCOPE_OPTION`, `_print_effective`, the `off`/`on`/`status` commands).
- `src/specify_cli/cli/commands/__init__.py` lines ~372–380 (`_register_moments` — the `moments_app`
  Typer sub-app is already registered under the top-level `spec-kitty moments` group; you are
  adding a `drain` sub-typer/command group to that *same* `moments_app`, not creating a new
  top-level command).
- `tests/conftest.py` for the `canonical_home` fixture (isolated `SPEC_KITTY_HOME` for tests).
- `kitty-specs/hosted-opt-in-drain-ledger-01M3FFEV/contracts/hosted-posture.md` for the exact
  truth table and the one-line guidance string.
- `docs/adr/3.x/index.md` and `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md` for the ADR
  frontmatter/section convention (title/description/status/date frontmatter; `## Context and
  Problem Statement`, `## Decision`, `## Consequences`).

### Subtask T034: ATDD red-first — `tests/cli/commands/test_moments_drain.py`

**Purpose**: Write the failing acceptance tests for `spec-kitty moments drain on|off|status` first,
committed as their own commit before any implementation, per the charter's red-first discipline.

**Steps**:
1. Create `tests/cli/commands/test_moments_drain.py` using `typer.testing.CliRunner` against the
   registered `spec-kitty` app (follow the existing pattern in
   `tests/cli/commands/test_moments*.py` if present, otherwise mirror
   `tests/cli/commands/test_auth_*.py` for CliRunner wiring).
2. Use the `canonical_home` fixture from `tests/conftest.py` to isolate `SPEC_KITTY_HOME` per test
   — never write into the real developer home. Use `tmp_path` for the per-repo checkout (a
   `.kittify/` marker directory) where `--repo` behavior is under test.
3. Cover:
   - `spec-kitty moments drain on` (no `--repo`) writes `[hosted] drain = true` to the
     **runtime-root** `config.toml` under the isolated `SPEC_KITTY_HOME` — assert the file path
     printed matches `get_runtime_root() / "config.toml"` (import the same resolver production
     code uses) and assert the on-disk TOML round-trips with every other existing key untouched
     (write a pre-existing unrelated key first, assert it survives).
   - `spec-kitty moments drain on --repo` writes `hosted.drain: true` to
     `<repo>/.kittify/config.yaml`, preserving other existing top-level keys in that YAML file.
   - `spec-kitty moments drain off` / `off --repo` write `false` the same way.
   - `spec-kitty moments drain status` (plain) prints: the effective posture (on/off), the
     repository scope's value and source file, the personal scope's value and source file, any
     active narrowers found (e.g. `SPEC_KITTY_NO_MOMENT_HANDLERS`, `SPEC_KITTY_SYNC_DISABLE`,
     `[moments] agents = "off"`), and **all four hosted-posture files** by absolute path even when
     some do not exist yet (repo `.kittify/config.yaml`, repo `.kittify/config.toml` if used by
     `[moments]`, global `~/.kittify/config.toml`, runtime-root `config.toml`) — see plan.md §F-7
     minors and `contracts/hosted-posture.md`.
   - `spec-kitty moments drain status --json` emits a JSON object with equivalent fields (posture,
     per-scope value+source, narrowers, files) — assert via `json.loads(result.stdout)`, not
     substring matching.
   - Help text: `spec-kitty moments drain --help` (or `on --help`) states, verbatim in spirit, that
     "both [scopes] must be on" for drain to be effective, and that no environment variable can
     enable it.
   - One test asserting the exact one-line guidance string from `contracts/hosted-posture.md`
     appears somewhere reachable from `status` output when drain is off (either directly, or by
     asserting the constant string used by `status` matches the one WP02/WP03 map `DrainDisabled`
     to — cross-check `hosted_posture.py`'s exported guidance constant if WP01 defines one; do not
     hand-duplicate the string in two places).
4. Run the new test file — it MUST fail (no `drain` subcommand exists yet). Commit this file alone
   with a message like `test(WP08): red — moments drain CLI (T034)` before starting T035.

**Files**: `tests/cli/commands/test_moments_drain.py` (new, ~150–220 lines).
**Validation**: `pytest tests/cli/commands/test_moments_drain.py -v` — every test fails with
`NoSuchOption`/`AttributeError`-style errors (missing command), not import errors. Commit as a
standalone red commit.

### Subtask T035: Implement `moments drain` in `cli/commands/moments.py`

**Purpose**: Make T034 green by adding a `drain` command group to the existing `moments_app`,
reading/writing through `core.hosted_posture` (never a second config reader/writer, matching this
module's existing "never a second config reader or writer" discipline stated in its module
docstring).

**Steps**:
1. In `src/specify_cli/cli/commands/moments.py`, add a nested Typer app or three flat commands
   under a `drain` sub-group on `moments_app` (`spec-kitty moments drain on|off|status`), following
   the existing `off`/`on`/`status` command style already in this file (reuse `_REPO_SCOPE_OPTION`,
   `_JSON_OPTION`, and `_resolve_scope` where they fit; add module-level constants instead of
   duplicating literals if a string like the guidance line or a help sentence would otherwise
   appear ≥3 times — Sonar S1192 / project style).
2. `drain on` / `drain off`:
   - Without `--repo`: call `hosted_posture.set_personal_drain(True|False)` (WP01 API) — writes to
     the runtime-root `config.toml` via the shared `core/toml_table.py` atomic rewrite helper.
     Print the written path and the effective posture afterward (same "write, then re-read and
     print effective" idiom as the existing `off`/`on` commands in this file).
   - With `--repo`: resolve `project_root` the same way `_resolve_scope` does for the existing
     commands (error if no `.kittify/` checkout found), then call
     `hosted_posture.set_repo_drain(True|False, project_root=project_root)` — writes
     `hosted.drain` into `.kittify/config.yaml`, preserving every other top-level key (ruamel.yaml
     round-trip per C-003, not a rewrite-from-scratch).
   - Help text (`typer.Argument`/docstring) states plainly: drain is effective only when **both**
     the repository and personal scopes are on, and that no environment variable can turn it on
     (R-1) — env only narrows.
3. `drain status [--json]`:
   - Call `hosted_posture.drain_posture()` (and `ledger_posture()` if useful context) to get the
     `DrainPosture` object with per-scope provenance.
   - Human-readable output: effective on/off; `repository: <bool> (source=<path or "absent">)`;
     `personal: <bool> (source=<path or "absent">)`; any active narrower names; then all four
     hosted-posture file **absolute paths** (existing or not), one per line, labelled by scope.
   - `--json`: emit the equivalent as a JSON object via `console.emit_json` (same idiom as the
     existing `status` command in this file).
   - Keep this function's complexity ≤15 (ruff C901/Sonar S3776 ceiling per `CLAUDE.md`) — extract
     a small `_render_drain_status_human(posture)` / `_drain_status_dict(posture)` helper pair if
     the single function would otherwise branch too much; add focused unit coverage for each
     helper (Sonar new-code-coverage expectation).
4. Register any new sub-typer the same way the existing `moments_app` is already registered in
   `cli/commands/__init__.py::_register_moments` — if you add `drain` as a nested `typer.Typer()`
   rather than flat commands on `moments_app`, wire it with `moments_app.add_typer(drain_app,
   name="drain")` inside `moments.py` itself; do not touch `_register_moments` unless the top-level
   `moments` help string needs updating to mention drain (a one-line addition is fine).
5. Run `tests/cli/commands/test_moments_drain.py` until green. Then run the wider
   `tests/cli/commands/test_moments*.py` suite to confirm the existing `off`/`on`/`status` commands
   are unaffected.

**Files**: `src/specify_cli/cli/commands/moments.py` (modified, +80–150 lines).
**Validation**: `pytest tests/cli/commands/test_moments_drain.py tests/cli/commands/test_moments*.py -v`
all green; `ruff check src/specify_cli/cli/commands/moments.py`, `mypy` on the same file, zero
issues.

### Subtask T036: ADR — `docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md`

**Purpose**: Write the governance record for the whole mission: the reversal of #3980's packaged
hosted-endpoint default (D-5) and the new two-scope drain consent model, filling the gap research.md
R4 identified (the ADR mission `team-kitty-launch-defaults-01M1XJ4Y` WP01 planned for this reversal,
`2026-09-07-1-packaged-hosted-target-default.md`, was never written).

**Steps**:
1. Read `docs/adr/3.x/index.md` for the naming convention (`YYYY-MM-DD-N-descriptive-title.md`) and
   `docs/adr/3.x/2026-09-26-1-ci-coverage-honesty.md` for the frontmatter shape (`title`,
   `description`, `status: Accepted`, `date`) and section order (`## Context and Problem
   Statement`, `## Decision`, `## Consequences`).
2. Write `docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md` with:
   - **Frontmatter**: `title: 'ADR: hosted interaction is opt-in, twice, with no packaged
     endpoint'` (or similar), `description` summarizing the reversal + consent model,
     `status: Accepted`, `date: '2026-09-26'`.
   - **Context and Problem Statement**: the server-frozen period (#4971), the operator directive of
     2026-09-23 to stop shipping a hard-coded live endpoint, and — explicitly — that the D-5
     packaged-default ADR planned by mission `team-kitty-launch-defaults-01M1XJ4Y` WP01 was never
     written, so this is the first record covering both the original decision and its reversal.
   - **Decision**: record D-1 through D-6 verbatim in spirit (two-scope drain: repo
     `.kittify/config.yaml` `hosted.drain` + personal runtime-root `config.toml` `[hosted] drain`,
     both required; ledger flag gates only the derived projection, never the lane/decision ledgers;
     explicit-vs-automatic guidance split; keep `[sync].server_url`'s name; personal file is
     runtime-root `config.toml` not `~/.kittify/config.toml`) and R-1 through R-4 (no env can
     enable drain; `.kittify/saas-auth.json` / `.kitty.env`-sourced `SPEC_KITTY_SAAS_URL` count as
     explicit configuration, never as drain-enablement; drain gates all relay traffic including
     operator-typed relay commands, but not auth/tracker; migrated `team.spec-kitty.ai` values are
     kept as explicit, drain still defaults off).
   - **Consequences**: no packaged hosted endpoint (a fresh install talks to no server, C-007
     scope note on what "zero network" excludes — the PyPI upgrade-check notice stays out of
     scope, it already has `SPEC_KITTY_NO_UPGRADE_CHECK`); the #4311 coupling (C-005) — any future
     live-publish retry must sit behind the same drain gate, drain-off is a clean skip never a
     diagnostic-as-error; forward-reference the follow-up to rename `[sync].server_url` (D-4, out
     of scope here).
3. Run `python -m scripts.docs.freshen_adr_inventory docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md`
   from the repository root (not the `scripts/docs/...py` file-path form — it fails with
   `ModuleNotFoundError` per the index page's own warning) to update the page-inventory lockfile
   and add the new row to `docs/adr/3.x/index.md`'s table.
4. If the generated index row's summary line needs hand-editing for accuracy, edit it directly in
   `docs/adr/3.x/index.md` afterward — do not fight the generator, just correct its output.

**Files**: `docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md` (new, ~90–150 lines);
`docs/adr/3.x/index.md` (modified — new row, generated then possibly hand-corrected).
**Validation**: the freshen script runs clean; the new ADR file parses with the same frontmatter
schema as its neighbors (compare keys against `2026-09-26-1-ci-coverage-honesty.md`).

### Subtask T037: Docs + changelog

**Purpose**: Bring `docs/api/configuration.md`, `docs/api/environment-variables.md`,
`docs/context/team-kitty.md`, and `docs/changelog/CHANGELOG.md` in line with the shipped opt-in
model, per FR-015.

**Steps**:
1. **`docs/api/configuration.md`** — add a new `hosted:` section (documenting
   `.kittify/config.yaml`'s `hosted.drain` key: type bool, default absent/off, "repository opt-in;
   effective only combined with the personal activation — see `spec-kitty moments drain`") and a
   new `ledger:` section (`ledger.projection`: type bool, default `true`, "gates only the automatic
   refresh of the derived, gitignored execution-state projection; never the lane ledger, the
   decision ledger, or the committed status snapshot — see FR-010"). Cross-link the new ADR
   (`docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md`) and `docs/context/team-kitty.md` in
   the `related:` frontmatter list, matching this file's existing pattern of relative links to
   `docs/adr/3.x/...`.
2. **`docs/api/environment-variables.md`**:
   - `### SPEC_KITTY_SAAS_URL` (currently ~line 206): change the opening line from "Override the
     packaged default Spec Kitty SaaS base URL (`https://team.spec-kitty.ai`, #3980 — the env var
     is a dev/self-host override, not a requirement)" to something like "Configures the hosted
     endpoint; there is no built-in default (#4971) — set this or `config.toml [sync].server_url`
     before any explicit hosted command will do anything other than print setup guidance." Keep
     the rest of the section (precedence rules, scope note) intact except where it references "the
     packaged default" — reword those to "no built-in default" / "an explicitly configured
     endpoint".
   - Summary table row (currently ~line 569): `| \`SPEC_KITTY_SAAS_URL\` | Configures the hosted
     endpoint; no built-in default | \`https://spec-kitty-dev.example.internal\` |`.
   - Do not touch `SPEC_KITTY_ENABLE_SAAS_SYNC`'s own row/section wording beyond what's strictly
     needed for consistency — its rename/retirement is explicitly out of scope for this mission
     (see spec.md "Out of scope").
3. **`docs/context/team-kitty.md`**:
   - Remove the sentence "There is no client-side opt-in, no consent grant, no offline queue, and
     no daemon." (currently line ~33) — that claim is now false; drain *is* a client-side opt-in
     (two scopes). Replace with something like: "There is no offline queue and no daemon. There is
     a client-side opt-in: a moment is published only when both the repository
     (`.kittify/config.yaml` `hosted.drain`) and the developer's personal runtime-root
     `config.toml` `[hosted] drain` are on — see `spec-kitty moments drain status`."
   - Add a short new `## Drain: the client-side opt-in` (or similar) section right after "The
     one-paragraph model", explaining the two-scope model, that env vars can only narrow never
     enable (R-1), and pointing at `contracts/hosted-posture.md`'s truth table and the ADR from
     T036 for the full decision record.
   - Add a small vocabulary-table row or note distinguishing "drain" (this mission's canonical term
     for automatic outbound hosted interaction) from any residual "sync" wording, reinforcing the
     "sync is dead" section already in this file.
4. **`docs/changelog/CHANGELOG.md`** — add one entry under the existing `## [Unreleased] - 4.0.0rc5`
   → `### Changed` section (do not create a new `## [Unreleased]` heading; the file already has
   one — insert your bullet into its existing `### Changed` list), matching the file's exact shape:
   a bold one-line summary, the issue reference `(#4971)`, then **Before:** / **After:** paragraphs.
   For example (adapt wording, keep the shape):
   ```markdown
   - **Hosted interaction (moments, presence, capability minting, relay) is now off by default and requires an explicit, two-scope opt-in; there is no packaged hosted endpoint** (#4971). **Before:** the CLI shipped a hard-coded live SaaS default (`https://team.spec-kitty.ai`, #3980) and automatically fanned status/lifecycle/runtime moments out to it whenever an endpoint resolved, with no per-developer or per-repository consent step. **After:** live drain requires both the repository (`.kittify/config.yaml` `hosted.drain`) and the developer's personal runtime-root `config.toml` (`[hosted] drain`) to be on — `spec-kitty moments drain on|off|status` manages both; no environment variable can enable drain, only narrow it; a fresh install resolves no hosted endpoint at all (`SPEC_KITTY_SAAS_URL` or `config.toml [sync].server_url` only) and every explicit hosted command stops with setup guidance instead of a traceback when unconfigured; the local execution-state projection continues to refresh automatically (`ledger.projection`, default on) with zero effect on the lane ledger, the decision ledger, or the committed status snapshot. See `docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md`.
   ```
5. **Frontmatter freshness**: bump `updated:` to `'2026-09-26'` in every doc file you actually
   modified in this subtask (`configuration.md`, `environment-variables.md`, `team-kitty.md`); the
   changelog file's own `updated:` frontmatter is already `'2026-09-26'` (confirm, bump only if
   your edit lands on a later date).
6. Run, in order:
   - `PYTHONPATH=. python scripts/docs/check_docs_freshness.py --ci` (confirm this exact invocation
     path/flag against the script's own `--help`/argparse if it has drifted; fix any freshness
     finding on the files you touched — do not suppress).
   - `pytest tests/architectural/test_no_legacy_terminology.py` — must stay green; you introduced
     no `ceremony`/`status-writing` wording and used "status commit" only where canonical.
   - A manual terminology pass over every file you touched in T036/T037: no `Feature`/`feature*`
     for the domain object (use "Mission"), no new `SYNC_`/`SAAS_`/`TEAMSPACE_` identifiers, never
     call drain "sync".
   - `ruff check .` / `ruff format --check .` / `mypy` over the touched Python file
     (`moments.py`) and the new test file — zero issues.
   - `pytest tests/cli/commands/test_moments*.py -v` — full green, including T034's new file.

**Files**: `docs/api/configuration.md`, `docs/api/environment-variables.md`,
`docs/context/team-kitty.md`, `docs/changelog/CHANGELOG.md` (all modified).
**Validation**: all four checks in step 6 pass; a reviewer reading only `team-kitty.md` and the new
ADR can correctly describe the two-scope opt-in model without reading source.

## Definition of Done

- `tests/cli/commands/test_moments_drain.py` exists, was committed red-first (T034), and is green
  after T035's implementation.
- `spec-kitty moments drain on|off [--repo]` writes the correct file/key per D-1/D-5 and preserves
  every other key in the file it rewrites.
- `spec-kitty moments drain status [--json]` reports effective posture, both scopes' values and
  source files, active narrowers, and all four hosted-posture file paths (plan §F-7 minors).
- Help text states plainly that both scopes must be on and that no env var can enable drain (R-1).
- `docs/adr/3.x/2026-09-26-2-hosted-interaction-opt-in.md` exists, follows the 3.x ADR convention,
  records D-1..D-6 and R-1..R-4, explicitly notes the never-written prior ADR gap (research.md R4),
  and is indexed via `freshen_adr_inventory` in `docs/adr/3.x/index.md`.
- `docs/api/configuration.md` has new `hosted:`/`ledger:` sections; `docs/api/environment-variables.md`'s
  `SPEC_KITTY_SAAS_URL` section and summary-table row read "no built-in default", not "packaged
  default"; `docs/context/team-kitty.md` no longer claims "no client-side opt-in" and instead
  documents the drain model; `docs/changelog/CHANGELOG.md` carries one `### Changed` entry in the
  file's exact shape, with `(#4971)` and Before:/After:.
- Every touched doc's `updated:` frontmatter is `2026-09-26` (or later, if genuinely edited later).
- `check_docs_freshness.py --ci`, `test_no_legacy_terminology.py`, ruff/format/mypy, and
  `tests/cli/commands/test_moments*.py` all pass.
- Per-subtask completion is recorded via `spec-kitty agent tasks mark-status <Txxx> --status done`
  for T034–T037 (event-sourced; not a manual checkbox).

## Risks

- **Duplicating the guidance string or the truth-table logic** instead of reusing WP01's
  `hosted_posture.DrainPosture`/guidance constant risks two sources of truth for the same sentence
  drifting apart. Mitigation: import and reuse; if WP01 did not export a guidance constant, raise
  that as a blocking dependency gap rather than hand-copying the string from `contracts/hosted-posture.md`.
- **Writing to the wrong personal-scope file.** `[moments]` already lives in
  `~/.kittify/config.toml`; the new personal drain key belongs in the **different** runtime-root
  `config.toml` (D-5). A copy-paste from the existing `moments.py` `on`/`off` commands will target
  the wrong file unless the resolver call is swapped deliberately. Mitigation: T034's tests assert
  the exact resolved path via the same production resolver, not a hardcoded string.
  - **ADR scope creep.** It is tempting to also write the D-4 rename ADR or re-litigate #4311 here.
  Mitigation: this ADR records only what shipped in this mission; explicitly forward-reference the
  D-4 rename and #4311 coupling as follow-ups, per spec.md's own "Out of scope" section.
- **Changelog entry placed under a new heading.** The repo convention is one live `[Unreleased]`
  section; creating a second one silently forks changelog history. Mitigation: read the file first
  (already done in this prompt's research) and insert only a new bullet into the existing
  `### Changed` list.
- **Complexity creep in `drain status`.** Rendering four file paths, two scopes, and narrowers in
  both human and JSON form can exceed the complexity-15 ceiling if written as one function.
  Mitigation: extract `_drain_status_dict()` and reuse it for both `--json` and the human renderer.

## Reviewer Guidance

- Confirm T034 was actually committed as a separate red commit before T035's implementation commit
  (check git log for this WP's branch) — this is the charter's red-first discipline, not optional
  ceremony.
- Verify `moments drain on` (no `--repo`) writes to the **runtime-root** `config.toml`, not
  `~/.kittify/config.toml` — this is the single easiest mistake to make in this WP (see Risks).
- Verify no new `SYNC_`/`SAAS_`/`TEAMSPACE_` identifier was introduced anywhere, and that "sync" is
  never used to describe drain in any doc or help string touched here.
- Verify `docs/adr/3.x/index.md` actually gained a new row (via the freshen script, not by hand,
  unless the script's own output needed a factual correction) and that the ADR frontmatter matches
  its neighbors' schema.
- Verify the CHANGELOG entry lands inside the existing `## [Unreleased] - 4.0.0rc5` → `### Changed`
  block, not a new top-level section.
- Spot-check that `docs/context/team-kitty.md`'s removed sentence is actually gone (not merely
  softened) and that the replacement text accurately reflects the two-scope model rather than
  overclaiming (e.g., do not claim server-side consent changed — C-001, no server change was made).
- Confirm `moments drain status`'s narrower detection genuinely reads
  `SPEC_KITTY_NO_MOMENT_HANDLERS` / `SPEC_KITTY_SYNC_DISABLE` / `[moments] agents` rather than a
  hardcoded "none" placeholder — this is the one part of FR-007 easy to stub out and forget.

Implement with:

```bash
spec-kitty agent action implement WP08 --agent claude
```
