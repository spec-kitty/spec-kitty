---
work_package_id: WP25
title: Vocabulary gate, reachability pins, gate closeout
dependencies:
- WP22
- WP23
- WP24
requirement_refs:
- FR-014
- FR-018
- NFR-002
- SC-003
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
subtasks:
- T111
- T112
- T113
- T114
phase: Phase 6 - Messaging and closeout
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: tests/architectural/test_retired_charter_vocabulary.py
create_intent:
- tests/architectural/test_retired_charter_vocabulary.py
execution_mode: code_change
owned_files:
- tests/architectural/test_retired_charter_vocabulary.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP25 – Vocabulary gate, reachability pins, gate closeout

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `reviewer-renata`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(WP18 retires `ad-hoc-profile-load`; use `spk-charter-profile-load`.)

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

The mission's last package: it makes the cutover impossible to regress and proves every gate closed.

1. **FR-018 / SC-003**: `tests/architectural/test_retired_charter_vocabulary.py` forbids the spec's closed token list on the closed living surfaces outside the closed historical roots; it scans at least the base-recorded file floor; it has a planted-token self-test per token; its allowlist is empty except entries for the C-004 identifiers. It finds 0 tokens.
2. **FR-014**: every stale pin in the reachability test module (`_ACTION_UNREACHABLE_*`, `_PROFILE_*`, `_SPREAD`) is re-asserted against the `default` preset or deleted, each deletion listed with its reason (#5323 item 2).
3. **NFR-002**: the named gates close with empty allowlists; `test_lifted_cli_doctrine_charter_cr02_compat.py` is gone with its shim.
4. **Final traceability**: no `pending_until` marker remains in `tests/acceptance/charter_pack_cutover/`; the whole acceptance suite is green.

## Context & Constraints

- Spec: FR-014, FR-018 (and its "FR-018 closed lists"), NFR-002, SC-003, C-002, C-004, C-008 ("FR-008 before FR-018"). Testability squad `research/postspec-squad-testability.md` §D (gate shape, non-vacuity). Runtime seams §5 (exclude `.claude/worktrees/agent-*`; agent copies are git-ignored except the four tracked `spec-kitty-standalone.md` files).
- Model the gate on `tests/architectural/test_no_legacy_terminology.py` (NUL-delimited `git grep`, fragment-built tokens so the gate does not flag itself, path-based exclusions only, `pytestmark = [architectural, git_repo, docs_scoped]`) and `tests/architectural/test_charter_kind_vocabulary_single_authority.py` (non-vacuity floor, `test_allowlist_is_empty`).
- WP24 contract: the CHANGELOG Unreleased Before/After entries have a bold headline starting with **`Charter pack cutover:`**. Those entries, and only those, are exempt in the Unreleased section (they become a released section at publish). Read the Unreleased section with `scripts.release.validate_release.unreleased_section` and parse entries with `scripts.docs.check_changelog_style.parse_section` (the same parser the style guard uses, so the two cannot disagree).
- **Ownership.** WP25 owns only the new gate file. Everything else it touches belongs to a completed upstream WP: the acceptance suite (WP01), the reachability module (moved by WP23 to `tests/charter_offering/drg/test_reachability.py`), the NFR-002 gates (WP03, WP05, WP16, WP21 and others). The tasks.md follow-up rule covers mechanical renames; the edits here are closeout edits: log each file with its rationale, keep each edit minimal, and point the reviewer at them.
- **No allowlist growth.** If a hit cannot be fixed and does not fall in a spec-listed historical root, stop and escalate (see T111 step 5). Do not add an exemption the spec does not list.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes must merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- **Lane**: from `lanes.json` (filled by finalize).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Never push to `main`. Commit per subtask (`test(architectural): retired charter vocabulary gate (#3732)`, `test(drg): re-assert reachability pins against the default preset (#3732)`, …).

## Subtasks & Detailed Guidance

### Red first (C-006 / C-011) — first commit

1. `grep -rn 'pending_until("WP25")' tests/acceptance/charter_pack_cutover/`. WP01 assigns WP25: `test_fr014_reachability_pins_reasserted_or_recorded` (`test_rename_skills_glossary.py`: finds the module by glob `tests/**/drg/test_reachability.py`; no pin references `default.yaml` / `default_pack` / `charter_pack_registry`; every deleted pin listed with a reason under a module-docstring section titled exactly `Deleted pins (FR-014)`), `test_fr018_vocabulary_gate_zero_findings_over_floor` and `test_fr018_planted_token_detected` (`test_gates_latency_messaging.py`), the remaining `test_nfr002_gates_close_empty` rows (FR-016 allowlist empty, FR-018 allowlist only C-004 names, `test_no_dead_doctrine_paths` and kind-vocabulary allowlists empty), and `test_traceability_no_pending_markers_remain` (`test_traceability.py`).
   **These tests import the gate modules by file path and call names in them.** Read them before writing the gate and implement exactly the names they use (scan function, token tuple, allowlist, floor constant). If a name they need conflicts with this prompt, the test wins (C-006).
2. Remove the markers only; run them; record red; commit `test(acceptance): drop WP25 xfail markers (#3732)`.

### Subtask T111 – FR-018 vocabulary gate (closed token and root lists, floor, planted tests)

- **Purpose**: the retired vocabulary cannot come back on a living surface (FR-018, SC-003).
- **Steps**:
  1. **Tokens** (spec, verbatim; build each from fragments in the source):
     - prose tokens, case-insensitive substring: `doctrine pack`, `spec-kitty doctrine`, `doctrine.org.packs`, `.kittify/doctrine`, `charter pack apply`, `Pack Default Charter`, `default charter pack`, `specify_cli.doctrine`, `doctor doctrine`, `--doctrine-mode`;
     - the skill prefix `spk-doctrine-` (covers the seven `spk-doctrine-*` ids) and the five folded skill ids `spec-kitty-charter-doctrine`, `spec-kitty-glossary-context`, `spec-kitty-bulk-edit-classification`, `spec-kitty-spdd-reasons`, `ad-hoc-profile-load` (case-sensitive; not preceded or followed by `[A-Za-z0-9-]`);
     - identifier tokens, case-sensitive, on identifier boundaries (`(?<![A-Za-z0-9_])…(?![A-Za-z0-9_])`): `organisation_packs`, `accompanies_doctrine_pack`, `CharterPackManager`, `CharterPackConfigError`, `CHARTER_PACK_CONFIG_INVALID`, `BUILTIN_PACKS`, `doctrine_mode`, `doctrine_skill`, `doctrine_pack_id` (OD-1 renamed it).
     The boundary rule matters: recorded migration ids such as `2.1.2_fix_charter_doctrine_skill` must not match `doctrine_skill`. Record the matching rules in the module docstring. Cross-check the list against spec FR-018 and FR-008 at write time; the list is closed: no additions, no omissions.
  2. **Living surfaces** (tracked files only, via `git ls-files -z`): `src/**`, `packs/**`, `docs/**`, `.github/workflows/**`, `Makefile`, `AGENTS.md` (CLAUDE.md is its symlink; scan the target once), and the tracked generated agent copies (`git ls-files .cursor .gemini .github/prompts .opencode .claude .agents .codex` — at base only four `spec-kitty-standalone.md` files). Shipped skills live under `src/charter/offering/skills/`, so `src/**` covers them. Text files only (skip binary by a NUL-byte check).
  3. **Historical roots** (closed; path-based, never content-based): other missions' `kitty-specs/` (not in scope anyway), `docs/adr/**`, `docs/reports/**`, `docs/archive/**`, `docs/plans/**`, `.kittify/evidence/**`, `.kittify/migrations/**`, every prefix in `tests/_support/terminology_scope.py` `FORBIDDEN_SCAN_ROOTS` (import it; it includes `docs/migrations/` and `packs/built-in/glossary_packs/`), released changelog content (section-aware: in `docs/changelog/CHANGELOG.md` everything outside `## [Unreleased]` is released; inside it, exempt only entries whose headline starts `Charter pack cutover:`; every other file under `docs/changelog/` must be the notes of a released version — list them explicitly and assert each list member exists), and, **by file** (spec FR-018 "Historical roots", verbatim): the cutover migration modules (`m_*charter_pack_cutover*.py` and its `_charter_pack_cutover_*` helpers: `_charter_pack_cutover_report.py`, `_charter_pack_cutover_snapshots.py`, `_charter_pack_cutover_resets.py`, `_charter_pack_cutover_skills.py`) and the legacy-state predicate module (`src/specify_cli/migration/legacy_charter_layout.py`).
     **Tombstone files** (spec FR-018, verbatim; their job is to name retired things; exempt by file, each with its reason in the gate): `src/specify_cli/skills/retired.py` (`RETIRED_CANONICAL_SKILL_NAMES`), `src/charter/offering/packs/retired_fields.py`, `src/specify_cli/upgrade/metadata.py`, and every pre-existing `src/specify_cli/upgrade/migrations/m_*.py` module (historical migrations; their `migration_id`s are recorded in consumer projects).
     The gate's exemption list equals spec FR-018 exactly: no addition, no omission (WP01's `test_fr018_*` checks it).
  4. **Non-vacuity**:
     - File floor: WP01 recorded it at base as a **literal** (`FR018_FLOOR` in `tests/acceptance/charter_pack_cutover/_requirements.py`, with the base SHA). Use that literal; never derive the floor from this gate's own scope function (that would be circular). Subtract only the in-scope files this mission deleted (`git diff --name-only --diff-filter=D <base-sha>..HEAD`, scoped); pin the result as `_FILE_FLOOR` with the SHA and the command in a comment; assert `scanned >= _FILE_FLOOR` and that every living root contributed at least one file.
     - Planted self-tests, one per token (`pytest.mark.parametrize` over the token tuple): write a file containing the token under a synthetic living path (for example `src/x.py`, `docs/guide.md`) into `tmp_path`, run the scan on that synthetic tree (make the scanner take a repo root and a path list so tests need no git), assert exactly that token is reported. Add negative controls: the same token under `docs/adr/` is not reported; in a synthetic CHANGELOG it is reported in a plain Unreleased entry, not reported in a released section or in a `Charter pack cutover:` entry; `2.1.2_fix_charter_doctrine_skill` is not reported for `doctrine_skill`.
     - `_ALLOWLIST: frozenset[...] = frozenset()` (composite key path + token), with `test_allowlist_is_empty_except_c004` asserting every entry names `doctrine-daphne` or `DIRECTIVE_039`. At landing it should be empty: neither C-004 name contains a token.
  5. **Run it on the live tree.** For every hit:
     - prose or identifier still in the retired sense → fix it in place (a closeout follow-up in the owner's file; log it);
     - the spec already exempts the retired-name registries by file (step 3: `retired.py`, `retired_fields.py`, `metadata.py`, the pre-existing `m_*.py`, the cutover helpers, the predicate module); no escalation for those.
     - a hit **outside** those files that must spell the old name to do its job → **stop and escalate** with file, line and reason, and wait for a ruling. Do not invent an exemption and do not obfuscate a literal to dodge the gate.
     Record the final scanned count and 0 hits in the Activity Log.
- **Files**: `tests/architectural/test_retired_charter_vocabulary.py`; follow-ups logged.
- **Parallel?**: No (T113 and T114 read its result).
- **Notes**: keep every function at complexity ≤ 15; type everything (`mypy --strict`); no `# noqa` / `# type: ignore`. Mark it `architectural`, `git_repo`, `docs_scoped` like the terminology gate, and check `tests/architectural/_gate_coverage.py` / the roster gates accept a new architectural test file (add it where the rosters require; logged follow-up).
- **Validation**:
  - [ ] 0 hits on the live tree; scanned ≥ `_FILE_FLOOR`.
  - [ ] Each planted test goes red when its token is removed from the token tuple (try one locally, record).
  - [ ] Allowlist empty (or only C-004 entries).

### Subtask T112 – Reachability pins re-asserted or deleted with reasons

- **Purpose**: #5323 item 2: the pins in the reachability module are not asserted by any test and were stale (FR-014).
- **Steps**:
  1. File: `tests/charter_offering/drg/test_reachability.py` (it was `tests/doctrine/drg/test_reachability.py`, 1,293 lines at base). Inventory every module-level pin constant whose name starts `_ACTION_UNREACHABLE_`, `_PROFILE_` or is `_SPREAD`: name, size, and every reference (`git grep -n "<NAME>" tests/`). Record which are referenced by a test assertion and which are not.
  2. The pins were measured against this repository's activation store (`_activated()` → `charter_activated_urns(_REPO_ROOT)`, `_raw_activated_map()`), which held the drifted `default.yaml` lists. After WP11/WP12 migrated this repository, the per-kind keys are absent (the `default` preset: every built-in artifact effective). Measure each pin under that state with the module's own helpers (they call `resolve_context` and the canonical traversal helpers; do not reimplement the walk).
  3. For each pin decide:
     - **Re-assert**: the pin still expresses a meaningful invariant under the `default` preset. Add a test asserting `measured == pin`, and update the pin to the measured value **with a ledger row per member that entered or left** (the module's "NFR-002 REVIEW-GATE NOTE (D18)" requires a per-member ledger; a pasted value without a ledger row is a reject).
     - **Delete**: the pin cannot hold or no longer means anything (for example an "activated-only" set when nothing is activation-filtered). Remove the constant and any helper only it used; list it with its reason.
  4. Put the decision table in the module docstring under a section titled exactly `Deleted pins (FR-014)` (the acceptance test parses that title; list every deleted pin with its reason there, and the re-asserted pins with their asserting test) and copy it to the Activity Log. FR-014 is satisfied only by an explicit list. No remaining pin may reference `default.yaml`, `default_pack` or `charter_pack_registry`, even in a comment.
  5. Run the module and its owning subsystem directories.
- **Files**: `tests/charter_offering/drg/test_reachability.py` (closeout follow-up in a WP23-owned file; logged); the wiring ledger it cites lives in `docs/plans/**` (historical root: do not edit; cite it).
- **Parallel?**: Yes, with T111.
- **Validation**:
  - [ ] Every pin is either asserted by a test or deleted with a reason.
  - [ ] The WP25 FR-014 acceptance test is green.

### Subtask T113 – NFR-002 gate closeout (empty allowlists; shim tests deleted)

- **Purpose**: prove each named gate closes empty, not just that it passes.
- **Steps**: for each gate, find its exemption structures (allowlists, baselines, exempt sets, "TICKETED" maps), check they are empty or justified by the spec, and run it. Record a table (gate, structure, size at base, size now, result).
  - `tests/architectural/test_doctrine_census.py`: `EXEMPT_MANAGEMENT_SURFACE` must be empty and the old package absent (WP05). `TICKETED_BASELINE` (a "ratchet allowlist, #3179", two entries at base naming `_doctrine_collect.py` and `cli/commands/doctrine.py` consumers): re-measure its consumers after WP15/WP16/WP21. If entries remain, route the consumer through a charter facade (`charter.drg` / `charter.packs`) so the map empties; if that is more than a small repoint, stop and escalate instead of declaring NFR-002 met.
  - `tests/architectural/test_lifted_cli_doctrine_retirement.py`: the group-registration test now asserts the group is absent (WP16); no allowlist.
  - The #4836 guidance gate (`test_no_deprecated_doctrine_command_in_guidance.py`, or the removed-command gate WP16 rewrote it into; find it with `git grep -ln "4836" tests/architectural`): no allowlist; it covers every removed command.
  - `tests/architectural/test_no_dead_doctrine_paths.py`: "no violation allowlist"; check its wholesale scope-outs are path classes, not violations.
  - `tests/architectural/test_charter_kind_vocabulary_single_authority.py`: `_ALLOWLIST` empty (its own test).
  - `tests/architectural/test_charter_pack_path_authority.py` (FR-016, WP03): allowlist empty.
  - `tests/architectural/test_retired_charter_vocabulary.py` (FR-018): T111.
  - `tests/architectural/test_lifted_cli_doctrine_charter_cr02_compat.py`: deleted (WP16). `git grep -n "cr02_compat" -- . ':!kitty-specs' ':!docs/adr' ':!docs/reports'` → nothing (rosters such as `.github/ci-module-registry.yml:494` and `ci-shard-timings.json` included).
  - `tests/architectural/test_runtime_charter_doctrine_boundary.py`: `_EXEMPT_SUBPACKAGE` gone; `_LAZY_BASELINE_ALLOWLIST` not larger than at base (`git show <base-sha>:<path>` to compare).
- **Files**: none owned; any fix is a logged closeout follow-up.
- **Parallel?**: After T111.
- **Validation**: [ ] table complete; [ ] every gate green with empty exemption structures.

### Subtask T114 – Final traceability: zero `pending_until` markers remain

- **Purpose**: C-006 closes: every acceptance test the mission defined is a plain, green test.
- **Steps**:
  1. `git grep -n "pending_until(" -- tests/acceptance/charter_pack_cutover` → only the helper's definition (and its own unit test, if any).
  2. WP01 already wrote the permanent guard `test_traceability_no_pending_markers_remain` (strict xfail for WP25; you removed its marker in the red-first commit). It goes green once the last marker is gone. Keep the `pending_until` helper and its self-tests only if `test_every_pending_marker_names_a_real_wp` or the helper self-tests still need it; otherwise delete it with its self-tests (dead code under `tests/architectural/test_no_dead_modules.py`). Record the decision.
  3. Run the whole acceptance suite: `uv run --frozen pytest tests/acceptance/charter_pack_cutover -q` → all pass, 0 xfail, 0 xpass. Record counts.
  4. Final sweep for the whole mission, recorded in the Activity Log: `git grep -n "tests/doctrine\b" -- . ':!kitty-specs' ':!docs/adr' ':!docs/plans' ':!docs/reports' ':!docs/archive' ':!docs/changelog' ':!.kittify'` → nothing (WP23 may have left `docs/context/charter.md` for WP24; fix as a follow-up); `git grep -n "2026-08-22-2"` over living surfaces → nothing.
- **Files**: acceptance-suite files (WP01-owned; logged).
- **Validation**: [ ] 0 markers; [ ] suite green with 0 xfail.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q
uv run --frozen pytest tests/architectural/test_retired_charter_vocabulary.py \
  tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_doctrine_census.py \
  tests/architectural/test_lifted_cli_doctrine_retirement.py tests/architectural/test_no_dead_doctrine_paths.py \
  tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_runtime_charter_doctrine_boundary.py \
  tests/architectural/test_no_legacy_terminology.py tests/architectural/test_no_dead_modules.py -q
uv run --frozen pytest $(git grep -ln "4836" -- "tests/architectural/test_*.py") -q   # includes the removed-command guidance gate
uv run --frozen pytest tests/charter_offering/drg/test_reachability.py -q
uv run --frozen pytest tests/charter tests/charter_offering -q -m "fast or unit"
ls tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py \
   tests/architectural/test_ci_collection_completeness.py 2>/dev/null | xargs -r uv run --frozen pytest -q
uv run --frozen mypy --strict tests/architectural/test_retired_charter_vocabulary.py
uv run --frozen ruff check tests/architectural/test_retired_charter_vocabulary.py tests/charter_offering/drg/test_reachability.py
uv run --frozen ruff format --check --force-exclude tests/architectural/test_retired_charter_vocabulary.py tests/charter_offering/drg/test_reachability.py
```

Never run bare `tests/architectural/` or `make test-full` (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **Vacuous gate**: wrong scope returns zero files. Mitigation: floor, per-root non-empty check, planted tests per token.
- **Over-matching**: substrings in migration ids or unrelated identifiers. Mitigation: identifier-boundary rule plus negative controls.
- **Spec gap on legitimate registries**: escalate (T111 step 5) instead of allowlisting.
- **Pinned values pasted without review**: the D18 ledger rule; reviewer compares ledger rows to the diff.

## Review Guidance

- Red after the first commit, green at the end, assertions unchanged.
- Read the token tuple against spec FR-018 word for word; read the root lists against the spec's historical roots and living surfaces.
- Delete one token from the tuple locally: its planted test must fail. Plant one token in a scratch living file: the gate must fail.
- Check `_FILE_FLOOR` provenance (base SHA, commands) and that the allowlist is empty.
- Check the reachability decision table: every pin listed; each re-asserted pin has ledger rows; each deletion has a reason.
- Check the NFR-002 table and that `cr02_compat` is gone everywhere.
- Check 0 `pending_until` markers and the full acceptance suite green.

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

## Carry-over from WP21

- Remove the dead `parents[3]/doctrine/skills` fallbacks in 7 migrations (listed in `FILE_EXEMPTIONS` of `tests/architectural/test_charter_pack_path_authority.py`) and drain those exemptions plus the remaining path-allowlist entries you own.
- Gate bug (silent non-check): `tests/architectural/test_charter_facades_reexport_offering.py` `_IDENTITY_REQUIRED_ORIGINS` still keys on the top-level package `"doctrine"`, which no longer exists, so re-exports originating in `charter.offering` are never identity-checked. Fix the key, show the gate red on a planted non-identical re-export, then green.
- From WP22: `doctrine_mode` in `docs/api/batch-api-contract.md:~912-913` — apply the orchestrator ruling in research/posttasks-fold-decisions.md (WP22 section). ~28 src docstring/comment "doctrine pack" hits (kind_vocabulary, org_charter, pack_manager, org_pack_config, pack_assembler, pack_validator, spdd activation, yaml_utils); `docs/development/reference/coverage-signals.md` lists a `doctrine` top-level package; packs/internal docs-lint config `doctrine_artifact: src/doctrine/` (config data — decide stale vs kept); `docs/convergence/**` historical ledgers (confirm exempt).
- From WP23: `src/specify_cli/dossier/manifest.py:~20` cites a test file that never existed; fixture dir `tests/charter_offering/.../mission_type_canonical/project_override/canonical/.kittify/doctrine/` still uses the retired project home; test files/classes outside the moved tree still named for the retired `doctor doctrine` command (`tests/specify_cli/test_doctor_doctrine.py`, `tests/specify_cli/cli/commands/test_doctor_doctrine_{integrity,org_layer,collisions,selections}.py`, `tests/cli/test_doctor_doctrine_selections_snapshot.py`, `TestDoctorDoctrineCommand`); `render_profile_suggested_doctrine` (content sense? decide) and the "doctrine/…" template origin string asserted by `test_origin_format_matches_doctrine_path`; WP20/WP21 test-name carry-overs not done by WP23 (`test_doctrine_service_*`, `test_action_doctrine_bundle_*`, `tests/charter/test_compact.py`, `_DOCTRINE_ROOT` in `tests/charter/test_cascade.py`, `*_across_entry_points`) — rename per FR-018 or record a reasoned exemption.
- From WP24: FR-018 gate needs file exemptions for `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` and the glossary seed's deprecated entries (ruling recorded in research/posttasks-fold-decisions.md); repoint `docs/context/charter.md:~463` (`tests/doctrine/test_relation_doc_parity.py` → `tests/charter_offering/...`) once WP23 is in your lane; superseded `docs/migrations/relocate-builtin-doctrine-packs.md` stays historical.
