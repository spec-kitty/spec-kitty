---
work_package_id: WP24
title: Glossary, changelog and runbook
dependencies:
- WP22
requirement_refs:
- FR-013
- FR-017
- SC-005
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: 3dfdc7e9afa63e8b5edcb2a1b1b15069c8c8461a
created_at: '2026-10-08T22:24:39.041741+00:00'
subtasks:
- T107
- T108
- T109
- T110
- T115
phase: Phase 6 - Messaging and closeout
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/context/charter.md
create_intent:
- docs/migrations/charter-pack-cutover.md
execution_mode: code_change
owned_files:
- docs/context/charter.md
- .kittify/glossaries/spec_kitty_core.yaml
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- docs/changelog/CHANGELOG.md
- docs/migrations/charter-pack-cutover.md
- docs/migrations/doctrine-local-overlay-to-org-layer.md
- docs/migrations/relocate-builtin-doctrine-packs.md
- docs/migrations/index.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP24 – Glossary, changelog and runbook

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(WP18 retires `ad-hoc-profile-load`; use `spk-charter-profile-load` if the old name is gone. For the glossary work, also load `spk-charter-glossary`, or `spk-doctrine-glossary` if WP18 has not landed.)

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

1. **FR-013**: `docs/context/charter.md` defines charter offering, Charter Pack, activation preset, active charter, project layer and Charter Bundle; retires Doctrine Pack, Doctrine Pack ID, Doctrine Catalog and Charter Selection; rewrites the `charter` entry's "Do NOT use when"; amends the "active" guard (ADR 2026-10-06-1 §1); and no living surface cites the missing ADR `2026-08-22-2`.
2. **FR-017 / SC-005**: the CHANGELOG `## [Unreleased]` section has a Before/After for every removed command, skill, config key, directory, descriptor field and JSON code; the runbook `docs/migrations/charter-pack-cutover.md` exists for operators, pack authors and saved scripts; the two superseded runbooks are marked historical. **Never bump the version.**
3. Every `pending_until("WP24")` strict-xfail in `tests/acceptance/charter_pack_cutover/` (FR-013, FR-017, SC-005) is removed and green.
4. `make docs-lint` (changelog style guard and spelling) and the glossary gates are green.

## Context & Constraints

- Spec: FR-013, FR-017, SC-005, FR-018 (closed lists), C-002, C-003, Domain Language table, owner decisions OD-1..OD-8. ADR `docs/adr/4.x/2026-10-06-1-charter-offering-active-charter-and-activation-presets.md` (§1 vocabulary and the "active" amendment, §4 command table, §5 skills, §7 cutover, Amendment rulings 1-10). Do not edit the ADR (C-002).
- Contracts in this mission: `contracts/cli.md` (command map, `LEGACY_CHARTER_STATE` text), `contracts/errors.md` (codes), `contracts/upgrade-migration.md` (what the upgrade does and reports), `data-model.md` (preset, active charter, renamed identities), `quickstart.md`.
- Consumer squad `research/postspec-squad-consumer.md` S5 (messaging) and **S7 (glossary collisions)**: enumerates what each glossary entry must do. Runtime seams `research/runtime-seams.md` §2 (worktrees: merge the upgraded target into a lane, never rebase; a rebase loses the approval stamp, `APPROVAL_STAMP_NOT_ON_LANE`).
- **Glossary authorities**: three files carry glossary content: the seed `.kittify/glossaries/spec_kitty_core.yaml` (authority 1), the built-in pack `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (authority 2), and `docs/context/charter.md` (authority 3). `tests/architectural/test_glossary_authority_parity.py` and `test_glossary_pack_parity.py` gate the seed/pack join and the governing term; keep them green. The pack edit needs `spec-kitty charter pack regenerate-graph` (C-003).
- **FR-018 interaction (read before writing)**: `docs/context/charter.md` and the CHANGELOG Unreleased section are *living surfaces* for the WP25 vocabulary gate, whose allowlist closes empty. The seed (`.kittify/`), the glossary pack (`packs/built-in/glossary_packs/`) and `docs/migrations/` are exempt roots (`tests/_support/terminology_scope.py` `FORBIDDEN_SCAN_ROOTS`). Therefore:
  - Retire the old terms in `docs/context/charter.md` by **removing** their entries (and the `Pack Default Charter` / `Active Charter artifact` phrases from the `charter` entry), and record them as `status: deprecated` (with `replaced_by`/definition naming the new term; follow the seed's existing schema) in the seed and the pack. The new entries in `charter.md` may say what they replace only through the exempt glossary data, not by spelling a forbidden token. The forbidden tokens are listed in spec "FR-018 closed lists"; treat `doctrine pack`, `Pack Default Charter`, `default charter pack`, `charter pack apply`, `spec-kitty doctrine` and `doctor doctrine` case-insensitively.
  - The CHANGELOG Before/After must name the old spellings (SC-005). WP25's gate exempts exactly the Unreleased entries whose bold headline starts with the fixed prefix **`Charter pack cutover:`**. Use that prefix for every Before/After entry and for no other entry. Any other Unreleased entry must not contain a forbidden token.
  - If a WP01 FR-013 acceptance test requires a redirect entry that spells a forbidden token, stop and raise it with the reviewer (FR-013 and FR-018 then conflict); do not weaken either test.
- Other WPs' files: inbound links to removed anchors (`charter.md#doctrine-pack`, `#doctrine-pack-id`, `#doctrine-catalog`, `#charter-selection`) live in docs owned by WP22 (upstream, merged): fix them as logged follow-ups. The ADR citations in `src/charter/activation/__init__.py:9` and `src/charter/activation/drg_activation.py:11` (WP20-owned) are logged follow-ups too.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes must merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- **Lane**: from `lanes.json` (filled by finalize).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Never push to `main`. Commit per subtask, conventional subjects referencing #3732 (`docs(glossary): …`, `docs(changelog): …`, `docs(migrations): …`).

## Subtasks & Detailed Guidance

### Red first (C-006 / C-011) — first commit

1. `grep -rn 'pending_until("WP24")' tests/acceptance/charter_pack_cutover/`. WP01 assigns WP24: `test_fr013_retired_terms_redirected` (Doctrine Pack, Doctrine Pack ID, Doctrine Catalog and Charter Selection retired or redirected; the `charter` entry's "Do NOT use when" rewritten; the "active" guard amended), `test_fr013_glossary_defines_terms` and `test_fr013_no_living_citation_of_missing_adr` (`test_rename_skills_glossary.py`); `test_fr017_changelog_before_after_lists_every_removed_name` (the Unreleased section names every row of `contracts/cli.md` and `contracts/errors.md`, the twelve skill names, the config keys, `.kittify/doctrine/`, `accompanies_doctrine_pack`) and `test_fr017_runbook_and_historical_banners` (`test_gates_latency_messaging.py`).
2. Remove the markers only; run them; record red; commit `test(acceptance): drop WP24 xfail markers for FR-013/FR-017 (#3732)`.
3. Read what each test asserts before writing content: the tests are the done-condition (C-006), this prompt is guidance.

### Subtask T107 – Glossary terms, retirements and the "active" guard; ADR 2026-08-22-2 citations

- **Purpose**: one canonical definition per term (FR-013); the three-meaning split is visible to readers.
- **Steps**:
  1. In `docs/context/charter.md`, add six entries in the file's table format (Definition / Context / Status / Applicable to / Location / Related terms / **Do NOT use when**), placed near `### charter`:
     - **Charter offering**: everything offered to a project: the Charter Packs it can draw from, plus the project layer. Location `src/charter/offering/`, `packs/`. Do NOT use when: the project's activated set (active charter).
     - **Charter Pack**: a distributable bundle of charter components (artifacts and DRG edges) with optional activation presets (`presets/<name>.yaml`); an org pack may enforce activations (`required_<kind>` in `org-charter.yaml`). Identity `charter_pack_id`. Do NOT use when: a named starting point (activation preset) or the project's state (active charter).
     - **Activation preset**: a named set of activations a Charter Pack ships, applied with `spec-kitty charter activate [--pack <pack>] --preset <name>` (replace semantics; `--force` to overwrite customised keys). Built-in: `default` (no per-kind restriction plus the built-in mission types), `minimal`. **Do NOT use when**: a context-scoped activation entry (that is the [Activation Registry](#activation-registry)); a single artifact's state.
     - **Active charter**: what a project has activated: its `activated_<kind>` keys, `activated_kinds` and `mission_type_activations`, in `.kittify/config.yaml` or the pointed `charter.yaml`; read with `spec-kitty charter list --json`. **The "active" guard (amended, ADR 2026-10-06-1 §1)**: "active"/"inactive" alone still describe one artifact ("an active directive"); "active charter" names the project's activated set as a whole; never call the `.kittify/charter/` tree "active".
     - **Project layer**: the project's own charter components under `.kittify/charter-packs/` (one flat root; `charter_pack_id` `project`); part of the offering; ships no presets; listed by `charter pack list` as `project`.
     - **Charter Bundle**: the materialised `.kittify/charter/` tree (charter.md, synthesis manifest, DRG cache, provenance). Unchanged meaning.
  2. Rewrite the `### charter` entry's "Do NOT use when" cell (l.31 at base): point to Charter Bundle, Charter Pack, activation preset, active charter, the `src/charter/` package and the `spec-kitty charter` CLI group; drop the `Pack Default Charter` and `Active Charter artifact` phrasing and the "current implementation still calls …" sentence; update its Related terms.
  3. Remove `### Charter Selection` (l.179), `### Doctrine Catalog` (l.192), `### Doctrine Pack` (l.316), `### Doctrine Pack ID` (l.330). Update `### Activation Registry` (l.292: tuple field `charter_pack_id`; add a "Do NOT use when" that distinguishes it from activation preset), `### Organization Tier` (l.614: Charter Packs, `charter_packs.org.packs`, `.kittify/charter-packs/`), `### Doctrine Domain` (l.36; content sense: keep the term, fix the location/tier wording if it says "doctrine pack") and every "Related terms" link to a removed anchor. Fix inbound anchors elsewhere: `git grep -n "charter.md#\(doctrine-pack\|doctrine-pack-id\|doctrine-catalog\|charter-selection\)" -- docs packs src` (logged follow-ups).
  4. Seed and pack: add the six terms (canonical) and mark `Doctrine Pack`, `Doctrine Pack ID`, `Doctrine Catalog`, `Charter Selection`, `Pack Default Charter` as deprecated with their replacements, using the schema the seed already uses for deprecated terms: the `ceremony commit` entry (seed ~l.80) has `definition: "DEPRECATED. Replaced by `status commit`. …"`, `status: deprecated`, and the canonical `status commit` entry lists it under `synonyms_to_avoid` (~l.519). Do the same: each retired term gets a `DEPRECATED. Replaced by <new term>.` definition, and each new canonical term lists the retired surfaces in `synonyms_to_avoid`. Fix the "doctrine pack artifact" definitions (seed ~l.669/680, pack ~l.761/772) to "Charter Pack artifact". Keep seed and pack in parity.
  5. Citations: `git grep -n "2026-08-22-2" -- . ':!kitty-specs' ':!docs/adr' ':!.kittify/evidence'` → repoint each living citation to ADR `2026-10-06-1` (and the right section) or drop it when the claim no longer holds. Expect `docs/context/charter.md` (2, removed with the rewrites), `src/charter/activation/__init__.py:9`, `src/charter/activation/drg_activation.py:11`.
  6. Regenerate: `uv run --frozen spec-kitty charter pack regenerate-graph` then `--check`.
- **Files**: `docs/context/charter.md`, the seed, the pack; logged follow-ups.
- **Parallel?**: Yes, with T108/T109.
- **Notes**: the glossary pipeline resolves terms from the seed and the pack; the testability squad asked that the new terms "resolve through the glossary pipeline" (check the WP01 test for the exact call). Use `spec-kitty glossary` commands if they exist (`uv run --frozen spec-kitty glossary --help`) to confirm resolution.
- **Validation**:
  - [ ] Six terms present in all three authorities; four retired terms absent from `charter.md`, deprecated in seed and pack.
  - [ ] `git grep -n "2026-08-22-2"` over living surfaces → nothing.
  - [ ] Glossary parity gates green; `regenerate-graph --check` exit 0.

### Subtask T108 – Changelog Unreleased Before/After

- **Purpose**: every removed name has a stated replacement where operators read release notes (FR-017, SC-005).
- **Steps**:
  1. Read `scripts/docs/check_changelog_style.py`: Unreleased allows only `### Breaking`, `### Upgrade Notes`, `### Added`, `### Changed`, `### Fixed`, `### Internal`, in that order; each entry starts `- **<headline>**`; Breaking/Changed/Fixed entries need `**Before:**` (and `**After:**`) unless very short; entries cap at 1,200 characters (each nested item counted separately); requirement ids (`FR-…`, `NFR-…`, `C-…`), ULIDs and `.kittify/evidence/` paths are banned; use `- ` bullets only. No tables.
  2. Add `### Breaking` entries (create the heading above `### Upgrade Notes` if absent), each headline starting `Charter pack cutover:` and citing `(#3732)`, each with **Before:**/**After:** and nested `- \`old\` → \`new\`` items:
     - Commands (from `contracts/cli.md`): the whole `spec-kitty doctrine` group and each leaf with its `charter` home; `charter pack apply` → `charter activate --preset`; `charter pack path <preset>` → `charter pack path <pack> [--preset]`; `charter pack consistency-check` → `charter consistency-check`; `doctor doctrine` → `doctor charter-packs` (JSON keys unchanged); tracker `--doctrine-mode` → `--ownership-mode`. State that old spellings fail as unknown commands (exit 2).
     - Skills: the seven `spk-doctrine-*` → `spk-charter-*` / `spk-practice-*` names and the five folded `spec-kitty-*`/`ad-hoc-profile-load` skills (ADR §5), plus the retired `spec-kitty-constitution-doctrine`; old copies are removed from project and user-global skill roots.
     - Config keys: `doctrine.org.packs` and the single-pack `doctrine.org.{local_path,…}` form, `organisation_packs` → `charter_packs.org.packs`; `governance.doctrine.*` → `governance.charter.*`; tracker `doctrine` → `ownership`; `doctrine_pack_id` → `charter_pack_id`; interview answers `doctrine:` key.
     - Directories: `.kittify/doctrine/` → `.kittify/charter-packs/`; `src/charter/activation/packs/` presets → `packs/built-in/presets/`.
     - Descriptor field: `accompanies_doctrine_pack` rejected (`RETIRED_PACK_FIELD`); `org-charter.yaml` `schema_version` bump.
     - JSON codes and output: `CHARTER_PACK_CONFIG_INVALID` → `ACTIVE_CHARTER_CONFIG_INVALID`; new `LEGACY_CHARTER_STATE`, `DEFAULT_PRESET_MISSING`, `PRESET_NOT_FOUND`, `PACK_NOT_FOUND`, `PRESET_ID_UNRESOLVED`, `PRESET_WOULD_OVERWRITE`, `PRESET_INVALID`, `RESYNTHESIS_FAILED`, `RETIRED_PACK_FIELD`; `doctrine_mode` output key removed.
     - Tool surfaces: `spec-kitty doctor tool-surfaces --kind doctrine-skill` → `--kind charter-skill`; the `ToolSurfaceKind` value and surface-id segment `doctrine_skill` → `charter_skill`.
     - `charter pack list --json` shape (breaking): preset rows → one row per pack, `{"packs": [{"name", "tier", "root", "presets": [...]}]}` (`contracts/cli.md` "`--json` shapes").
     - State surface name `project_doctrine_graph` → `project_pack_graph` (printed by `doctor`).
     - Built-in pack manifest `generated_by`: `spec-kitty doctrine regenerate-graph` → `spec-kitty charter pack regenerate-graph`.
     Verify every new name against the live CLI and code (`--help`, `git grep`) before writing it.
  3. Add `### Upgrade Notes` entry `Charter pack cutover: run spec-kitty upgrade once …` (#3732): what the migration does (moves, rewrites, resets, kept-for-review report; `[]` lists reset with the key to restore; the `minimal` kind gate removed), that unmigrated projects fail with `LEGACY_CHARTER_STATE`, lanes merge the upgraded target (never rebase), and a link to `../migrations/charter-pack-cutover.md`.
  4. Add `### Added` entries for presets (`charter activate --preset`, `charter pack list` packs+presets, `presets/` in packs) — these name only new things, so no `Charter pack cutover:` prefix is needed unless they cite a retired name.
  5. Reword existing Unreleased entries that spell a retired token so they describe the post-cutover surface (at base: the #4836 entries under Changed/Fixed naming `spec-kitty doctor doctrine` and `spec-kitty doctrine validate|fetch`, and the #5538 entry naming `spec-kitty doctrine pack validate`). Keep their issue refs and meaning; these changes ship in the same release, so the new names are the accurate ones.
  6. `make docs-lint` (runs `check_changelog_style` and the spelling check). Do not touch released sections (C-002). Do not change the `## [Unreleased] - 4.0.0rc6` heading or `pyproject.toml` version.
- **Files**: `docs/changelog/CHANGELOG.md` (`CHANGELOG.md` at the root is a symlink).
- **Parallel?**: Yes.
- **Validation**:
  - [ ] Every item of SC-005's list appears with its replacement (check against `contracts/cli.md`, `contracts/errors.md`, ADR §5, spec FR-012 inventory).
  - [ ] Changelog style guard: 0 errors. Only `Charter pack cutover:` entries contain forbidden tokens.

### Subtask T109 – Runbook `docs/migrations/charter-pack-cutover.md`; historical banners

- **Purpose**: one page that tells each audience what to do (FR-017), named by the FR-011 error text.
- **Steps**:
  1. Create the runbook with the frontmatter shape of `docs/migrations/shared-package-boundary-cutover.md` (`title`, `description`, `doc_status: active`, `updated`), plus `audience:` if the docs lint requires it. Sections:
     - **What changed** (one paragraph; link ADR 2026-10-06-1).
     - **Operators**: `spec-kitty upgrade --dry-run`, read the summary (moved / rewritten / reset / kept for review), `spec-kitty upgrade`, commit the result (plain filesystem move; uncommitted edits are carried over); what each report class means; restoring a deliberate `[]` (the summary names file and key); the removed `minimal` kind gate; the collision refusal when both `.kittify/doctrine/` and `.kittify/charter-packs/` hold a path with different content; Windows locked files; the `LEGACY_CHARTER_STATE` error and its exempt commands (`upgrade`, `init`, `--version`, `--help`, the git merge drivers and the hook entry points; `contracts/cli.md`).
     - **Missions in flight**: upgrade the repository root; then **merge** the target branch into each lane, never rebase (a rebase moves the lane past its approval stamp and `spec-kitty consolidate` refuses with `APPROVAL_STAMP_NOT_ON_LANE`); or finish and consolidate the Mission before upgrading. The upgrade skips worktrees.
     - **Choosing a starting point**: `charter pack list`, `charter activate --preset minimal|default [--force]`, `--pack <org-pack> --preset <name>` (from `quickstart.md`).
     - **Pack authors**: delete `accompanies_doctrine_pack` from `pack.yaml`; rename `doctrine_pack_id` to `charter_pack_id` in `org-charter.yaml` and bump its `schema_version` (state the number from WP17's change); add `presets/<name>.yaml` (schema summary from `contracts/activation-preset.schema.yaml`); validate with `spec-kitty charter pack validate`; regenerate with `spec-kitty charter pack regenerate-graph`; replace retired command spellings in your procedures and skills.
     - **Saved scripts**: the full command map (table allowed here) from `contracts/cli.md`, the skill map, config keys, JSON codes.
  2. Banners on the two superseded runbooks (`doctrine-local-overlay-to-org-layer.md`, `relocate-builtin-doctrine-packs.md`): set `doc_status: superseded`, bump `updated`, and add directly under the title a quote banner in the style of `docs/architecture/05_ownership_map.md`: "> **Superseded; kept as a historical record.** … The current path is [Charter pack cutover](charter-pack-cutover.md)." Change nothing else in those pages (occurrence map: banner only).
  3. `docs/migrations/index.md`: list the runbook under "Current 3.2 migrations" (first item), and move the two superseded runbooks to "Historical and internal runbooks".
  4. Regenerate the docs indexes if frontmatter changed: `uv run --frozen python scripts/docs/docs_index.py --write`, `uv run --frozen python scripts/docs/inventory_lockfile.py` (check `--help`); these generated files are not owned here: log them.
  5. Confirm the FR-011 error text (WP14, `contracts/cli.md`) names `docs/migrations/charter-pack-cutover.md` exactly: `git grep -n "charter-pack-cutover.md" -- src`.
- **Files**: the four `docs/migrations/` files in `owned_files`.
- **Parallel?**: Yes.
- **Validation**:
  - [ ] Runbook covers operators, pack authors, saved scripts; lane guidance says merge, not rebase.
  - [ ] `make docs-lint` and `uv run --frozen pytest tests/docs -q` green.

### Subtask T110 – Flip FR-013/FR-017 xfails

- **Purpose**: close the loop on the acceptance tests.
- **Steps**: run every test un-xfailed in the red-first commit; all must be green. Paste the red output (from the first commit) and the green output (final) side by side in the Activity Log, by test id.
- **Validation**: [ ] all WP24 acceptance tests green; [ ] no assertion changed.

### Subtask T115 – Draft the public-packs sidecar PR (OD-2)

- **Purpose**: OD-2 (amendment ruling 2) says the public-packs sidecar repository receives a PR. This WP drafts it; the orchestrator opens it after this mission merges (no push to another repository from this WP).
- **Steps**:
  1. Write the draft into this prompt's Activity Log as one entry with a fenced block (no new repository file: a living-surface file would spell retired tokens, and `kitty-specs/` paths cannot be owned files). The draft holds a PR title and description (what changed in Spec Kitty, why the sidecar must change, a link to the runbook `docs/migrations/charter-pack-cutover.md`), and the exact changes as unified-diff blocks or file-by-file instructions:
     - every `pack.yaml`: delete `accompanies_doctrine_pack` (rejected with `RETIRED_PACK_FIELD`);
     - every `org-charter.yaml`: `doctrine_pack_id` → `charter_pack_id`, and the new `schema_version` (the number WP17 chose);
     - any retired command spelling in the sidecar's procedures or READMEs → the `contracts/cli.md` replacement.
  2. Read the sidecar's current files to make the draft concrete (`spec-kitty charter fetch` into a temp project, or the repository URL named in `docs/guides/how-to/governance/`); record the commit you read.
  3. Add one line to the mission PR body hand-off: "Sidecar PR drafted in the WP24 Activity Log; the orchestrator opens it after merge."
- **Files**: none (the draft lives in the Activity Log).
- **Parallel?**: Yes, after T109 (it links the runbook).
- **Validation**: [ ] every descriptor and org-charter change the cutover forces on pack authors is in the draft; [ ] the draft names the runbook.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest <every acceptance test id you un-xfailed> -q
make docs-lint
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen pytest tests/docs -q
uv run --frozen pytest tests/architectural/test_glossary_authority_parity.py tests/architectural/test_glossary_pack_parity.py \
  tests/architectural/test_no_legacy_terminology.py tests/architectural/test_pack_manifest_no_author_edit.py -q
uv run --frozen pytest tests/glossary -q
uv run --frozen pytest tests/charter tests/charter_offering -q -m "fast or unit"   # pack data changed (use tests/doctrine if WP23 has not merged)
uv run --frozen spec-kitty charter pack regenerate-graph --check
```

No Python source is owned here; if a follow-up touches `src/charter/activation/__init__.py` or `drg_activation.py`, run `uv run --frozen mypy --strict` and `uv run --frozen ruff format --check --force-exclude` on them.

## Risks & Mitigations

- **FR-013 vs FR-018**: a retired-term entry in `charter.md` trips the vocabulary gate. Mitigation: retire by removal in `charter.md`, deprecate in the exempt seed/pack; raise any test conflict.
- **Changelog style guard**: tables or over-long entries fail `docs-lint`. Mitigation: one entry per category with nested items; check length.
- **A replacement name that does not exist**: verify each against `--help` and the code.
- **Glossary parity drift** between seed and pack: edit both in one commit; run the parity gates.

## Review Guidance

- Red after the first commit, green at the end, assertions unchanged.
- Check SC-005 completeness item by item against `contracts/cli.md`, `contracts/errors.md`, ADR §5 and the spec FR-012 inventory.
- Check only `Charter pack cutover:` entries spell retired tokens; check no released section changed; check the version did not change.
- Read the runbook as an operator with a lane in `approved`: the merge-not-rebase instruction must be unambiguous.
- Check the superseded runbooks changed only in frontmatter and banner.

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

## Carry-over from WP08/WP09 reviews

- CHANGELOG Before/After must list `DefaultCharterPackMissingError` → `DefaultPresetMissingError` (`DEFAULT_PRESET_MISSING`), the deletion of `src/charter/activation/default_pack.py`, and the owner-approved codes `PRESET_INVALID` and `RESYNTHESIS_FAILED`.
- `src/specify_cli/provisioning/__init__.py` changed in WP09 (docstring, `__all__`): covered by the Unreleased changelog entry; no version bump (mission rule).
- From WP18 review: projects already migrated by `m_3_2_0rc35_kittify_profile_handoff` keep the old `/ad-hoc-profile-load` text in their prompt overrides (the migration is marker-gated and is not re-applied). The runbook must tell operators to replace it with `/spk-charter-profile-load` (or name the follow-up issue if a migration is added).
- From WP14: the changelog/runbook must state these consumer-visible removals: the nested org-pack layout `<pack>/doctrine/<plural>/<layer>` and the repo-root `doctrine/` fallback are no longer read (org packs outside the project must be flattened by their maintainers; the upgrade cannot convert them); the single-pack form `charter_packs.org.local_path` is gone (use `packs[]`); tracker `doctrine` ownership key, `--doctrine-mode` and the `doctrine_mode` JSON key are removed; `ActiveCharterConfigError` text now reads `CODE: body`; the CLI-root `LEGACY_CHARTER_STATE` gate and its exempt commands.
- From WP15: `docs/migrations/doctrine-local-overlay-to-org-layer.md` needs the historical banner (occurrence map); `CLAUDE.md` and `AGENTS.md` are separate files with identical content — keep both in sync.
- From WP19: user-visible warning text "Doctrine override:" → "Artifact override:"; renamed public Python names (DoctrineService→CharterOfferingService / ActiveCharterService, BaseDoctrineRepository→BaseArtifactRepository, DoctrineLayerCollisionWarning→ArtifactLayerCollisionWarning, DoctrineArtifactLoadError→ArtifactLoadError, DoctrineResolutionCycleError→ArtifactResolutionCycleError) for the Before/After table.
- From WP20: JSON key `charter consistency-check --json` `missing_from_doctrine` → `missing_from_offering`; compact governance label "Doctrine layer root:" → "Project layer root:"; renamed modules `doctrine_service_builder` → `active_charter_service_builder`, `action_doctrine_bundle` → `action_governance_bundle`, `_doctrine_paths` → `_project_root_candidates`; `DoctrineSelectionConfig` → `GovernanceCharterConfig`, `DoctrineCatalog` → `OfferingCatalog`, `resolve_doctrine_root` → `resolve_offering_root`, `build_activation_aware_doctrine_service` → `build_active_charter_service`. `.github/CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`.
- From WP20 review: keyword `doctrine_service=` → `charter_service=` on facade-exported `compile_charter` and related functions (breaking for keyword callers); messages "Charter Pack(s) referenced ...", "Cannot locate the charter.offering root ...", "available in the built-in missions".
- From WP22: links into `docs/context/charter.md#doctrine-catalog` now have text "Charter offering" but keep the anchor — re-point them when you rename/retire that heading; superseded runbook `docs/migrations/doctrine-local-overlay-to-org-layer.md` (~20 `.kittify/doctrine` mentions) gets the historical banner only.
