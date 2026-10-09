---
work_package_id: WP16
title: Remove the `spec-kitty doctrine` group
dependencies:
- WP13
- WP15
requirement_refs:
- FR-007
- C-001
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: 2d5e5c6ea7dfbbf235ce59d892753228c12ba24b
created_at: '2026-10-08T06:13:37.391337+00:00'
subtasks:
- T080
- T081
- T082
phase: Phase 4 - Removal (no aliases, no shims)
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/__init__.py
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/regen.py
- src/charter/offering/shared/scoping.py
- src/charter/offering/drg/migration/hand_authored_overlay.py
- src/charter/offering/schemas/agent-profile.schema.yaml
- scripts/generate_schemas.py
- packs/built-in/tactics/common-docs-find.tactic.yaml
- packs/built-in/tactics/common-docs-write.tactic.yaml
- packs/built-in/agent_profiles/doctrine-daphne.agent.yaml
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/development/how-to/create-a-doctrine-artifact.md
- docs/architecture/doctrine-kinds.md
- docs/development/reference/ci-gate-mechanics.md
- docs/development/reference/terminology-exemptions.md
- tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py
- tests/architectural/test_lifted_cli_doctrine_retirement.py
- tests/architectural/test_lifted_cli_doctrine_charter_cr02_compat.py
- tests/specify_cli/cli/test_doctrine_charter_cr02_compat.py
- tests/specify_cli/cli/test_doctrine_cli_removed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 – Remove the `spec-kitty doctrine` group

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(If WP18 has already landed, the skill is named `spk-charter-profile-load`; use whichever exists in your checkout.)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty doctrine` stops existing (FR-007, OD-3). After this WP:

- `spec-kitty doctrine` and every former leaf (`fetch`, `new`, `validate`, `org init`, `org validate`, `pack validate`, `pack assemble`, `regenerate-graph`, `asset list`, `asset path`, `mission-type list`) exit **2** through Typer's unknown-command path. No hidden alias, no hint, no redirect (C-001, OD-3).
- `src/specify_cli/cli/commands/doctrine.py` is deleted; nothing in `src/` or `tests/` imports it.
- The #4836 guidance gate (`tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py`) is rewritten as a **removed-command gate**: no `spec-kitty doctrine` invocation remains on any living surface (src text including docstrings and comments, shipped skills, both packs, living docs, CI workflows, `Makefile`, `AGENTS.md`). It closes with **no allowlist** (NFR-002).
- `test_lifted_cli_doctrine_retirement.py` asserts the group is gone (it is named in NFR-002); the CR-02 compat gate and its source copy are deleted with the shim they test (NFR-002).
- The WP01 acceptance tests marked `pending_until("WP16")` (FR-007 and the SC-004 "old spelling exits 2" cases) go from red to green.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`; mission `spec.md` (FR-006, FR-007, OD-3, C-001, NFR-002, C-008 "FR-006 before FR-007"); `contracts/cli.md` (command map: every "Before" spelling exits 2); `research/runtime-seams.md` §4 (the group, its leaves and every in-repo caller); `tasks.md` (per-WP test policy, mechanical-follow-up rule).
- **Upstream state you rely on.** WP15 moved every leaf to its `charter` home (T075/T076), moved `charter consistency-check`, renamed `doctor doctrine` → `doctor charter-packs`, and fixed the in-repo callers it owns (`.github/workflows/packs.yml`, `Makefile`, the pack-manifest `generated_by` constant, `AGENTS.md`, `packs/internal/**`, remediation strings). WP13 removed `charter pack apply`. Before starting, confirm with `spec-kitty agent tasks status` that WP13 and WP15 are `done`/`approved`, and confirm `src/specify_cli/cli/commands/charter/_app.py` no longer imports from `specify_cli.cli.commands.doctrine` (today it does, at line 27: `from specify_cli.cli.commands.doctrine import fetch, new, org_app, validate`). If it still does, WP15 is incomplete: stop and report.
- **C-001**: deleted things are deleted. No `hidden=True` stub, no root callback hint, no `doctrine` entry left in `_REGISTRARS`, no re-export module.
- **C-004**: `doctrine-daphne` keeps its id and name; only its stale command reference changes (see T081 note).
- **Mechanical follow-up edits** outside `owned_files` are allowed only in files owned by an already-completed upstream WP (tasks.md rule). Log each such file in the Activity Log with a one-line rationale. Expected ones are named per subtask below.
- Code style: ruff + mypy clean, `ruff format --check --force-exclude`, complexity ≤ 15, no new suppressions.

## Branch Strategy

- **Strategy**: lane per `lanes.json` (filled by finalize)
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first commit (C-006 / C-011)

Your **first commit** removes the `pending_until("WP16")` markers from the WP01 acceptance tests you own and nothing else:

```bash
rg -n 'pending_until\("WP16"\)' tests/acceptance/charter_pack_cutover/
```

These are the CLI-surface cases written by WP01 T006 for FR-007 (and the SC-004 old-spelling-exits-2 half). Run them and confirm they fail (the group is still registered). Commit as `test(acceptance): unmark WP16 FR-007 tests (red) (#3732)`. Do not edit the assertions: the acceptance criteria are WP01's (C-006). If a test is wrong, report it; do not redefine it.

## Subtasks & Detailed Guidance

### Subtask T080 – Delete the `doctrine` group and its command modules

- **Purpose**: one command surface (FR-007). Every leaf already has a `charter` home (FR-006, WP15), so the group is now pure wiring.
- **Steps**:
  1. Inventory what still reaches the module:
     ```bash
     rg -n "commands\.doctrine\b|commands import doctrine|from \. import doctrine|doctrine_module|doctrine_app" src tests
     rg -n "_doctrine_asset" src tests
     ```
  2. `src/specify_cli/cli/commands/__init__.py`: delete `_register_doctrine` (today l.234-251, including the CR-02 comment block), its entry in the registrar tuple (l.573) and the `"doctrine": _register_doctrine` key in the lazy registrar map (l.628). Verify no other table (lazy-command name list, help ordering) still names `"doctrine"`: `rg -n '"doctrine"' src/specify_cli/cli src/specify_cli/__init__.py`.
  3. Delete `src/specify_cli/cli/commands/doctrine.py` with `git rm`. The file is listed in WP03's `owned_files` (it repointed the `new` scaffold write root, `doctrine.py:650`); WP03 is upstream and done, so the deletion is a logged follow-up, not an ownership conflict.
  4. `src/specify_cli/cli/commands/_doctrine_asset.py`: if WP15 left it in place and its only consumer was the `doctrine asset` group, delete it too; if WP15 already moved its handlers under `charter/`, it is gone. If it is still imported by a `charter pack asset` home, leave it (WP21 renames it). Record which case applied.
  5. Remove every config entry that names the deleted files (these files are not owned here; they are mechanical follow-ups, log each):
     - `pyproject.toml` `[tool.ruff.format].exclude`: `"src/specify_cli/cli/commands/doctrine.py"` (l.523) and, if deleted, `_doctrine_asset.py`; also any `tests/...` exclude entries for test files you delete (`tests/cli/test_doctrine_commands.py` l.1130, `tests/specify_cli/cli/commands/test_doctrine_*.py` l.1869-1871) — `test_every_exclude_entry_exists_on_disk` fails otherwise. The ratchet count only shrinks.
     - `tests/release/coverage_breadth_baseline.json` entries for `src/specify_cli/cli/commands/doctrine.py` (l.2079) and `_doctrine_asset.py` (l.1711) if deleted.
     - `tests/architectural/test_runtime_charter_doctrine_boundary.py:130` lazy-baseline row `("src/specify_cli/cli/commands/doctrine.py", "charter.offering.drg.migration.hand_authored_overlay")` and l.116 for `_doctrine_asset.py` if deleted (shrink only; owned by WP05).
     - `tests/architectural/test_no_dead_cli_paths.py:496-504` (`_doctrine_asset.py` entry) if deleted.
     - `tests/architectural/test_doctrine_census.py:107` reason text naming `cli/commands/doctrine.py`: repoint to the WP15 home of `regenerate-graph`.
     - `tests/architectural/test_json_contract_enumeration.py:596` monkeypatches `specify_cli.cli.commands.doctrine._doctrine_root`; repoint to the WP15 home or drop the case if its command left the JSON contract.
  6. Regenerate the completion manifest: `python -m specify_cli.completion --regenerate` (removes the hidden `doctrine` group entry). `src/specify_cli/_completion_manifest.json` is a generated file other WPs also regenerate: never hand-edit it; on a rebase conflict, re-run the generator.
- **Files**: `src/specify_cli/cli/commands/__init__.py`, `src/specify_cli/cli/commands/doctrine.py` (deleted); follow-ups listed above.
- **Parallel?**: No (T081 and T082 build on it).
- **Notes**: Typer's unknown-command path exits 2 with "No such command 'doctrine'". Do not add a root-level hint (OD-3 ruled bare unknown-command). If the CLI root has a fuzzy "did you mean" helper, make sure it does not resurrect `doctrine` as a suggestion target.
- **Validation**:
  - [ ] `uv run spec-kitty doctrine --help; echo $?` prints Typer's unknown-command error and `2`.
  - [ ] `rg -n "commands\.doctrine\b" src` is empty.
  - [ ] `uv run pytest tests/architectural/test_completion_manifest_freshness.py -q` passes.

### Subtask T081 – Rewrite the #4836 guidance gate as a removed-command gate

- **Purpose**: today's gate (`tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py`) derives a "migrated" set by comparing handler identity between `charter_app` and `doctrine_app`; it imports `specify_cli.cli.commands.doctrine` (l.34) and lets doctrine-only commands through. Both premises die with the group. The new gate forbids **any** `spec-kitty doctrine` invocation on living surfaces.
- **Steps** (keep the file name: NFR-002 names it):
  1. Rewrite the module docstring: the group was removed in #3732 (FR-007); guidance must name the `charter` home from the FR-006 table; no allowlist.
  2. Remove the `doctrine_app` import and `_migrated_doctrine_commands`. Replace with a **closed literal** of former leaves and groups, since the group can no longer be introspected:
     `_REMOVED = ("fetch", "new", "validate", "org", "pack", "regenerate-graph", "asset", "mission-type")`.
  3. Patterns (compile once, module level):
     - `spec-kitty doctrine` followed by anything or end of token (`r"spec-kitty doctrine\b"`) — this is the FR-018 forbidden token, so prose such as "spec-kitty doctrine framework" (today in `scripts/generate_schemas.py:531` and the generated `agent-profile.schema.yaml:5`) is also flagged.
     - the bare backticked / RST form of a removed leaf: ``r"`{1,2}doctrine (" + "|".join(_REMOVED) + r")\b"`` (catches `` `doctrine asset list` `` and ``` ``doctrine validate`` ```).
  4. Scan scope:
     - Text files (`.md`, `.yaml`, `.yml`, `.txt`, `.toml`, `.json`) under `src/charter/offering/skills`, `src/charter/offering` (schemas, READMEs), `packs/`, `docs/`, `.github/workflows/`, plus the single files `Makefile`, `AGENTS.md`, `README.md`.
     - **Every `.py` file under `src/` and `scripts/`, full text** (string literals, docstrings and comments). The old gate skipped docstrings because they "describe the deprecated group"; that group no longer exists, so any mention is stale guidance.
     - Exclusions (scope, not allowlist), each with a one-line reason in a comment: `FORBIDDEN_SCAN_ROOTS` from `tests/_support/terminology_scope.py` (covers `docs/migrations/`, `docs/adr/`, `docs/archive/`, `kitty-specs/`, `.kittify/`, `tests/`); `docs/plans/`; `docs/changelog/` (released sections and the FR-017 Unreleased Before/After quote the old spelling; the section-aware treatment is FR-018's, WP25); `docs/development/docs-retrieval-index.yaml` (generated from pages that include historical ADRs); the cutover migration module, matched by the glob `src/specify_cli/upgrade/migrations/m_*charter_pack_cutover*.py` (occurrence map exception: it must spell legacy literals).
     - `docs/api/cli-commands.md` is **no longer excluded**: it is a generated file with no owner (tasks.md); you regenerate it in this subtask so its `doctrine` section disappears.
  5. Keep the non-vacuity floor (`_MIN_FILES_SCANNED`, today 800; the widened scope scans more, so re-measure and set the floor to the measured count rounded down to the nearest 100). Keep and adapt the self-tests:
     - planted `spec-kitty doctrine fetch …` in markdown is flagged;
     - planted bare `` `doctrine asset list` `` is flagged;
     - planted `spec-kitty doctrine regenerate-graph` (formerly *allowed* as doctrine-only) is now flagged;
     - planted invocation inside a Python **docstring** and inside a **comment** is flagged;
     - `doctrine-daphne` and prose such as "doctrine artifacts" are **not** flagged (no false positives on C-004 / content sense);
     - a positive control that ties the closed list to reality: for each name in `_REMOVED`, `CliRunner().invoke(app, ["doctrine", name, "--help"])` exits 2, and `CliRunner().invoke(app, ["doctrine", "--help"])` exits 2.
  6. Fix every living occurrence the gate reports. Expected residue at WP16 start (re-measure; WP15 owns several):
     ```bash
     rg -n "spec-kitty doctrine\b|\`{1,2}doctrine (fetch|new|validate|org|pack|regenerate-graph|asset|mission-type)\b" \
        src scripts packs docs .github Makefile AGENTS.md README.md \
        -g '!docs/adr/**' -g '!docs/plans/**' -g '!docs/archive/**' -g '!docs/changelog/**' -g '!docs/migrations/**' -g '!docs/reports/**'
     ```
     Owned here (rewrite to the FR-006 home; keep surrounding prose; change only the command spelling unless the sentence describes the removed group):
     - `src/specify_cli/cli/commands/mission_type.py:1695` → `spec-kitty charter mission-type list --include-inactive`.
     - `src/specify_cli/cli/commands/regen.py:17` → `spec-kitty charter pack regenerate-graph`.
     - `src/charter/offering/drg/migration/hand_authored_overlay.py:22,2027` → `spec-kitty charter pack regenerate-graph` (and the `:mod:` reference to the WP15 module that now hosts the handler).
     - `src/charter/offering/shared/scoping.py:18,26,88` (``doctrine validate``) → ``charter validate``.
     - `scripts/generate_schemas.py:531` "…for spec-kitty doctrine framework" → reword (e.g. "…for the Spec Kitty charter offering"); then regenerate `src/charter/offering/schemas/agent-profile.schema.yaml` with the generator (do not hand-edit; check the generator's own freshness test still passes).
     - `packs/built-in/tactics/common-docs-find.tactic.yaml:27,49`, `common-docs-write.tactic.yaml:54,60` → `spec-kitty charter pack regenerate-graph [--check]`.
     - `packs/built-in/agent_profiles/doctrine-daphne.agent.yaml:114` → `spec-kitty charter pack regenerate-graph`. The occurrence map lists this file as `do_not_change` for C-004 (id and name); its reason does not cover a stale command reference. Change only that line, keep id/name, and record the decision in the Activity Log.
     - `docs/api/cli-commands.md` (generated, unowned): regenerate it with `uv run --frozen python scripts/docs/build_cli_reference.py` after the group is deleted; if text outside the generated help blocks still names `spec-kitty doctrine` (36 hits today), rewrite it to the `charter` homes and log it as a generated-file change; then run `uv run pytest tests/architectural/test_docs_cli_reference_parity.py -q` and the CLI-reference freshness check (`python scripts/docs/check_cli_reference_freshness.py` or its test).
     - `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` (8), `docs/development/how-to/create-a-doctrine-artifact.md` (3), `docs/architecture/doctrine-kinds.md:149,150,175`, `docs/development/reference/ci-gate-mechanics.md:748`: command spellings only (titles and broader prose are WP22's).
     - `docs/development/reference/terminology-exemptions.md:229`: rewrite the paragraph that documents this gate to describe the removed-command gate and its exclusions.
     Not owned (mechanical follow-ups if WP15 left any; log them): `src/specify_cli/cli/commands/charter/mission_type.py:8,208,218`, `src/charter/offering/artifact_kinds.py:416`, `src/specify_cli/_completion_manifest.json` (regenerate), `packs/internal/**`, `.github/workflows/packs.yml`, `Makefile:47`, `AGENTS.md`.
  7. Packs were edited: run `uv run spec-kitty charter pack regenerate-graph` (WP15's home) and commit the regenerated `packs/built-in/pack-manifest.yaml` (generated; never hand-edit; `tests/architectural/test_pack_manifest_no_author_edit.py`). Then `uv run spec-kitty charter pack regenerate-graph --check` exits 0.
- **Files**: the gate file; the owned src/docs/packs files above.
- **Parallel?**: After T080 (the positive control needs the group gone).
- **Notes**: Keep the gate's helpers small (complexity ≤ 15): one `_offenders(text)`, one `_scanned_files()`, one `_is_excluded(rel)`. Do not add an allowlist structure; NFR-002 says it closes empty.
- **Validation**:
  - [ ] `uv run pytest tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py -q` passes, scanning ≥ the recorded floor.
  - [ ] Temporarily re-adding one planted line to a scanned doc makes it fail (do it locally; do not commit).

### Subtask T082 – Delete group tests; flip FR-007 xfails

- **Purpose**: tests of the deleted group go with it (C-001, NFR-002); retirement gates assert the new truth.
- **Steps**:
  1. `tests/architectural/test_lifted_cli_doctrine_retirement.py`: keep the file (NFR-002 names it). Replace `test_doctrine_group_is_registered` with `test_doctrine_group_is_unknown_command` asserting `exit_code == 2` and "No such command" in the output for `["doctrine"]` and `["doctrine", "--help"]`; parametrize over every former leaf path from the FR-006 table (`["doctrine","fetch"]`, `["doctrine","org","validate"]`, `["doctrine","pack","assemble"]`, `["doctrine","regenerate-graph","--check"]`, `["doctrine","asset","list"]`, `["doctrine","mission-type","list"]`, …) asserting exit 2. Keep the `curate`/`promote` cases but tighten them to `== 2`. Update the docstring (the "parent group must stay registered" sentence is now false).
  2. `tests/specify_cli/cli/test_doctrine_cli_removed.py` (the out-of-matrix source copy): make it match the lifted gate, or delete it if nothing references it (`rg -n test_doctrine_cli_removed .github tests/architectural`); record the choice.
  3. Delete `tests/architectural/test_lifted_cli_doctrine_charter_cr02_compat.py` and `tests/specify_cli/cli/test_doctrine_charter_cr02_compat.py` (NFR-002: deleted with the CR-02 shim). Their second test, `test_charter_group_canonical_routes`, checks `charter mission-type list` tags `activated` rows: first confirm the same assertion exists in `tests/cli/test_charter_mission_type_commands.py` (or WP15's tests); if it does not, move that one test there as a logged follow-up before deleting. Update the roster prose in `.github/ci-module-registry.yml:488-495` ("8 always-on architectural gates" → 7, drop the file name) and remove the file's row from `.github/ci-shard-timings.json` if the timing gate requires existing files (check `rg -n ci-shard-timings tests/architectural`). Both are follow-ups (log them).
  4. Residual tests still importing the deleted module after WP15 (re-run the T080 inventory over `tests/`). Today these import `specify_cli.cli.commands.doctrine`: `tests/cli/test_doctrine_commands.py`, `tests/cli/test_doctrine_org_commands.py`, `tests/cli/test_json_output_seam_e2e.py`, `tests/cli/test_mission_type_malformed_yaml_cli_boundary.py`, `tests/cli/test_charter_mission_type_commands.py`, `tests/docs/test_asset_howto.py`, `tests/charter/test_project_registration.py`, `tests/doctrine/drg/{test_extractor_asset,test_org_fragment_validation,test_regen_roundtrip,test_kind_mapping_totality}.py`, `tests/doctrine/test_doctrine_validate_lang_guard.py`, `tests/specify_cli/cli/commands/{test_charter_authoring,test_cli_boundary_mission_types,test_doctrine_asset,test_doctrine_new,test_doctrine_regenerate_graph,test_doctrine_validate}.py`, `tests/specify_cli/doctrine/test_config.py`, `tests/specify_cli/doctrine/test_pack_validator.py`. WP15 T079 should have repointed those that test a moved handler. For anything left: if the test exercises behaviour that now lives under a `charter` home, repoint it there (logged follow-up); if it only proves the `doctrine` spelling works, delete it. Never keep a test that invokes `["doctrine", …]` expecting success.
  5. Run the WP16 acceptance tests and confirm green. Commit: `feat(cli)!: remove the spec-kitty doctrine group (#3732)`.
- **Files**: the four owned test files; follow-ups as listed.
- **Parallel?**: No.
- **Validation**:
  - [ ] `rg -n '\["doctrine"' tests | rg -v 'exit_code == 2|unknown'` shows nothing expecting success.
  - [ ] `rg -n 'pending_until\("WP16"\)' tests` is empty.

## Test Strategy

Run before every push (record commands and pass/fail counts in the Activity Log and the PR *Tests run* section):

```bash
make test-fast
uv run pytest tests/acceptance/charter_pack_cutover/ -q -k "FR_007 or FR-007 or SC_004 or SC-004"   # adjust -k to WP01's ids; or run the WP16-marked file(s)
uv run pytest tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py \
              tests/architectural/test_lifted_cli_doctrine_retirement.py \
              tests/architectural/test_completion_manifest_freshness.py \
              tests/architectural/test_docs_cli_reference_parity.py \
              tests/architectural/test_runtime_charter_doctrine_boundary.py \
              tests/architectural/test_doctrine_census.py \
              tests/architectural/test_json_contract_enumeration.py \
              tests/architectural/test_no_dead_cli_paths.py \
              tests/architectural/test_ruff_format_exclude_ratchet.py \
              tests/architectural/test_pack_manifest_no_author_edit.py \
              tests/architectural/test_no_legacy_terminology.py -q
uv run pytest tests/cli/ tests/specify_cli/cli/ -q        # touched-module tests (the CLI tree)
uv run pytest tests/charter/ tests/doctrine/ -q           # src/charter/offering/** changed (scoping, overlay, schema)
uv run spec-kitty charter pack regenerate-graph --check
uv run ruff check src scripts tests
uv run ruff format --check --force-exclude <every touched .py file>
uv run mypy src/specify_cli/cli/commands/__init__.py src/specify_cli/cli/commands/mission_type.py src/specify_cli/cli/commands/regen.py src/charter/offering/shared/scoping.py src/charter/offering/drg/migration/hand_authored_overlay.py scripts/generate_schemas.py
```

Never run bare `tests/architectural/` or `make test-full`. Classify any unrelated red per the CLAUDE.md baseline-red gotcha.

## Risks & Mitigations

- **A hidden importer breaks collection.** Mitigation: the T080 inventory over `src` and `tests` before deleting; `uv run pytest --collect-only -q tests/cli tests/specify_cli tests/doctrine tests/docs tests/charter` after.
- **CI calls the old spelling.** WP15 owns `.github/workflows/packs.yml`; re-grep `.github/` and fail fast if anything remains.
- **Gate false positives on content-sense prose.** The patterns require `spec-kitty doctrine` or a backticked `doctrine <removed leaf>`; the self-tests pin that `doctrine-daphne` and "doctrine artifacts" pass.
- **Generated-file churn across lanes** (`_completion_manifest.json`, `pack-manifest.yaml`, `cli-commands.md` help blocks): regenerate, never merge by hand.
- **Overlap with WP22 docs prose.** You change command spellings only; leave titles, file names and wider wording to WP22.

## Review Guidance

- Red-on-base → green-on-final: check out the planning base, run the WP16 acceptance tests (strict xfail, i.e. failing behaviour); on this WP's head they pass with no `pending_until("WP16")` left.
- `spec-kitty doctrine` and each FR-006 leaf exit 2; `rg -n '_register_doctrine|commands\.doctrine\b' src` is empty; no `hidden=True` replacement.
- The rewritten gate imports nothing from the deleted module, scans docstrings and comments, keeps a floor and the planted self-tests, and has **no allowlist**; its exclusions are scope roots with reasons.
- CR-02 compat tests deleted (both copies); the retirement gate asserts exit 2.
- Every out-of-owned-file edit is logged with a rationale; `doctrine-daphne` id/name unchanged.
- mypy and `ruff format --check --force-exclude` ran clean on touched sources.

## Definition of Done

- [ ] First commit unmarks WP16 acceptance tests (red); later commits make them green.
- [ ] `doctrine.py` deleted; registrar entries removed; completion manifest regenerated.
- [ ] Removed-command gate rewritten and green with no allowlist; all living invocations fixed.
- [ ] CR-02 compat tests deleted; retirement gate inverted; residual group tests repointed or deleted.
- [ ] Pack manifest regenerated after pack edits; `regenerate-graph --check` exits 0.
- [ ] Test commands above run and recorded; ruff, format, mypy clean; `test_no_legacy_terminology.py` green.
- [ ] Commits reference #3732; nothing pushed to `main`.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-08T07:40:00Z – claude (python-pedro) – Red-first (28c8eb39): removed the WP16 pending_until markers (test_cli_surface._FR007_PENDING emptied; the three NFR-002 GateRows cr02/lifted-retirement/guidance set to pending=None, WP16 entry dropped from _GATE_PENDING). No assertion changed. Base: 15 failed, 286 passed, 1 skipped, 52 xfailed (12 FR-007 old-spelling rows + 3 NFR-002 gate rows). f3b03eb9 drops the then-unused pending_until import.
- 2026-10-08T08:30:00Z – claude – T080/T082 (d630c568): deleted src/specify_cli/cli/commands/doctrine.py and _register_doctrine (+ registrar tuple entry, lazy-map key); `spec-kitty doctrine` and every leaf exit 2 "No such command 'doctrine'" (Click's own "Did you mean 'doctor'?" suffix only; nothing resurrects doctrine). _doctrine_asset.py was already moved by WP15 (charter/pack_asset.py), nothing to delete. Completion manifest regenerated. Retirement gate inverted (15 former spellings incl. curate/promote, exit 2 + "No such command"; root --help control). test_doctrine_cli_removed.py deleted (source copy; no CI/arch reference). Both CR-02 compat tests deleted; test_charter_group_canonical_routes moved to tests/cli/test_charter_mission_type_commands.py as test_charter_mission_type_list_tags_activated_and_inactive_rows (no equivalent existed).
- 2026-10-08T09:30:00Z – claude – T081 (dda79f11): guidance gate rewritten as removed-command gate, no allowlist, closed _REMOVED list, full-text scan of src/ and scripts/ .py, floor 2500 (2552 measured), planted self-tests + positive CLI control. Local mutation check: appending a `spec-kitty doctrine fetch` line to create-an-org-doctrine-pack.md turns the gate red (not committed). docs/api/cli-commands.md (python -m scripts.docs.build_cli_reference) and docs-retrieval-index.yaml (python -m scripts.docs.docs_index --write) regenerated; agent-profile.schema.yaml regenerated (scripts/generate_schemas.py); pack-manifest.yaml regenerated (spec-kitty charter pack regenerate-graph; --check clean).
- doctrine-daphne decision: changed only line 114 (`spec-kitty doctrine regenerate-graph` -> `spec-kitty charter pack regenerate-graph`); profile-id and name unchanged (C-004). The occurrence-map exception covers id/name only and its reason says a stale command follows the categories; the no-allowlist gate cannot close otherwise. tests/doctrine/agent_profiles/test_doctrine_daphne_canonical_structure.py required-rule string updated to match. Deviation from the orchestrator note that WP22 owns this line: WP16 owned_files lists the file and T081 step 6 names the line.
- test_asset_howto root cause: commit 280b3587 (WP02, "project-layer READ sites resolve through kernel.charter_pack_paths") moved the project pack root to .kittify/charter-packs/, but the how-to (create-a-doctrine-artifact.md Step A/B) and the test still placed the asset under .kittify/doctrine/assets/, so `asset path team-release-checklist` found no project-tier asset ("Unknown asset id"). Fix: asset section paths -> .kittify/charter-packs/assets/; the test now lifts the documented `mkdir -p` directory from the doc and asserts it equals kernel project_pack_path(project, "assets"), then runs `charter pack asset path`.
- Out-of-ownership edits (mechanical, logged):
  - src/specify_cli/cli/commands/charter/authoring.py (WP15): `charter fetch` remedy now "No org charter packs configured." + "Add an entry to the charter_packs.org.packs list in .kittify/config.yaml."; comment spellings `charter new`.
  - src/specify_cli/charter_packs/snapshot.py: source-type/url errors name charter_packs.org.packs[] (same fetch flow, same stale key).
  - src/specify_cli/cli/commands/charter/pack_tooling.py (WP15): _built_in_pack_root docstring cites charter.pack_paths.built_in_root (facade over charter.offering.pack_paths) and packs/built-in.
  - src/charter/activation/kind_vocabulary.py, src/charter/offering/artifact_kinds.py: comments name charter/authoring.py / `charter new`.
  - pyproject.toml (format-exclude doctrine.py entry), tests/release/coverage_breadth_baseline.json (doctrine.py row), .github/ci-module-registry.yml (roster prose 8 -> 7 gates, cr02 file dropped). .github/ci-shard-timings.json left as recorded run artefact (no gate requires existing files).
  - Tests repointed to charter_app: tests/cli/{test_doctrine_commands,test_doctrine_org_commands,test_json_output_seam_e2e,test_mission_type_malformed_yaml_cli_boundary,test_charter_mission_type_commands}, tests/charter/packs/{test_org_charter_hooks,test_pack_validator}, tests/doctrine/{test_doctrine_validate_lang_guard,drg/test_org_fragment_validation}, tests/specify_cli/cli/commands/{test_doctrine_new,test_doctrine_asset,test_doctrine_validate,test_doctrine_regenerate_graph,test_cli_boundary_mission_types,test_charter_authoring,charter/test_charter_pack_asset,charter/test_charter_pack_tooling}, tests/specify_cli/charter_packs/test_fetch_cli, tests/architectural/{test_no_shipped_layer_label,test_json_contract_enumeration (doctrine rows dropped),test_doctrine_census (reason text)}, tests/docs/{test_asset_howto,test_asset_resolution_wheel}, tests/specify_cli/cli/test_no_visible_feature_alias (comments). Parity-only tests dropped: test_authoring_surface_preserves_options, test_deprecation_names_remaining_surfaces, doctrine-vs-charter JSON equality in test_charter_pack_asset and test_cli_boundary_mission_types (replaced by a schema check).
  - Comment/docstring spellings in tests/{charter/test_cascade,doctrine/_builtin_inventory,doctrine/test_pack_relocation_preflight,doctrine/drg/migration/test_extractor_projection,doctrine/drg/test_sharded_layout,reporting/_asset_loader}.py.
- Base-red (red at 28c8eb39 too, not caused here): test_doctrine_census::test_no_reached_file_is_orphaned (WP15's charter/pack_asset.py + pack_tooling.py are owned by no 01KZPDSR migration WP); test_no_dead_cli_paths::test_project_tier_graph_path_would_false_red_without_its_discriminator; test_ruff_format_exclude_ratchet::test_every_exclude_entry_still_genuinely_reformats (4 already-formatted entries, none mine); tests/release/test_pinning_inventory_fresh (line drift in test_workflow_coherence.py); tests/docs/test_module_docstring_doc_refs (docs/migrations/charter-pack-cutover.md not yet written, WP24); 4 tests/specify_cli/cli/commands/test_upgrade_command.py version-check tests (environment).

## Carry-over from WP15 (approved pending review)

- Delete `src/specify_cli/cli/commands/doctrine.py` (now a thin registrar re-registering the moved handlers) and its registrations; remove the WP16-marked FR-007 rows' markers; drop the `doctrine *` entries in `tests/architectural/test_json_contract_enumeration.py` (charter spellings already present).
- Callers still invoking the `doctrine` app: `tests/.../test_no_shipped_layer_label.py:~196`, `tests/cli/test_doctrine_*`, `test_doctrine_*.py` suites — repoint to the charter homes or delete if they only tested the deprecated group.
- Step 0: `charter fetch`'s "No org doctrine packs configured" remedy (now in `charter/authoring.py`) tells operators to add a `doctrine.org.packs` block, which WP14 removed — point it at `charter_packs.org.packs[]`; grep tests for the string.
- From WP15 review: `tests/docs/test_asset_howto.py` still regex-matches `spec-kitty doctrine asset path` and invokes `doctrine_app`; repoint to `charter pack asset path` / `charter_app`. It was ALSO red at WP15's base (7f7cf5e4) with "Unknown asset id: team-release-checklist" — root-cause that (find which earlier WP broke asset resolution or the how-to fixture) and fix it; record the cause.
- `_built_in_pack_root` docstring (charter/pack_tooling.py) cites `charter.offering.pack_paths.built_in_root` but the code imports `charter.pack_paths` — fix.
