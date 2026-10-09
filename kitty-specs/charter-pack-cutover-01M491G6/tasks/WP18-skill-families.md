---
work_package_id: WP18
title: Skill families
dependencies:
- WP12
requirement_refs:
- FR-008
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: a7e9f9e4bcdd20bd93322885aee71a1ad9633b90
created_at: '2026-10-07T19:49:05.793671+00:00'
subtasks:
- T088
- T089
- T090
- T091
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: src/charter/offering/skills/
create_intent:
- src/charter/offering/skills/spk-charter-governance
- src/charter/offering/skills/spk-charter-glossary
- src/charter/offering/skills/spk-charter-profile-load
- src/charter/offering/skills/spk-charter-spdd-reasons
- src/charter/offering/skills/spk-practice-bulk-edit
- src/charter/offering/skills/spk-practice-semantic-compression
- src/charter/offering/skills/spk-practice-show-me
- docs/api/skills/spk-charter-profile-load.md
- tests/specify_cli/skills/test_retired_charter_skills.py
execution_mode: code_change
owned_files:
- src/charter/offering/skills/spk-doctrine-charter/**
- src/charter/offering/skills/spk-doctrine-glossary/**
- src/charter/offering/skills/spk-doctrine-profile-load/**
- src/charter/offering/skills/spk-doctrine-spdd-reasons/**
- src/charter/offering/skills/spk-doctrine-bulk-edit/**
- src/charter/offering/skills/spk-doctrine-semantic-compression/**
- src/charter/offering/skills/spk-doctrine-show-me/**
- src/charter/offering/skills/spec-kitty-charter-doctrine/**
- src/charter/offering/skills/spec-kitty-glossary-context/**
- src/charter/offering/skills/spec-kitty-bulk-edit-classification/**
- src/charter/offering/skills/spec-kitty-spdd-reasons/**
- src/charter/offering/skills/ad-hoc-profile-load/**
- src/charter/offering/skills/spk-charter-governance/**
- src/charter/offering/skills/spk-charter-glossary/**
- src/charter/offering/skills/spk-charter-profile-load/**
- src/charter/offering/skills/spk-charter-spdd-reasons/**
- src/charter/offering/skills/spk-practice-bulk-edit/**
- src/charter/offering/skills/spk-practice-semantic-compression/**
- src/charter/offering/skills/spk-practice-show-me/**
- src/specify_cli/skills/retired.py
- src/charter/offering/skills/README.md
- src/charter/offering/skills/spec-kitty-mission-review/SKILL.md
- src/charter/offering/skills/spec-kitty/SKILL.md
- src/charter/offering/skills/spk-admin-agent-config/SKILL.md
- src/charter/offering/skills/spk-meta-skill-map/SKILL.md
- src/charter/offering/skills/spk-meta-skill-map/references/spk-skill-map.md
- src/charter/offering/skills/spk-meta-skill-authoring/SKILL.md
- src/charter/offering/skills/spk-mission-documentation/SKILL.md
- src/charter/offering/skills/spk-mission-plan/SKILL.md
- src/charter/offering/skills/spk-mission-specify/SKILL.md
- src/charter/offering/skills/spk-start-command-map/references/command-map.md
- src/charter/offering/skills/spk-start-here/SKILL.md
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_kittify_profile_handoff.py
- packs/built-in/missions/documentation/templates/task-prompt-template.md
- packs/built-in/missions/research/templates/task-prompt-template.md
- packs/built-in/missions/software-dev/templates/task-prompt-template.md
- packs/built-in/missions/mission-steps/plan/plan/prompt.md
- packs/built-in/missions/mission-steps/plan/specify/prompt.md
- packs/built-in/missions/mission-steps/software-dev/charter/prompt.md
- packs/built-in/missions/mission-steps/software-dev/implement/prompt.md
- packs/built-in/missions/mission-steps/software-dev/plan/prompt.md
- packs/built-in/missions/mission-steps/software-dev/review/prompt.md
- packs/built-in/missions/mission-steps/software-dev/specify/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-packages/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md
- packs/built-in/tactics/reviewer-implementer-role-separation.tactic.yaml
- packs/built-in/toolguides/CONTEXTIVE.md
- docs/api/skills/index.md
- docs/api/skills/spk-doctrine-profile-load.md
- docs/api/skills/spk-charter-profile-load.md
- docs/api/skills/spk-meta-skill-map.md
- docs/api/skills/spk-start-here.md
- docs/api/toc.yml
- docs/api/bulk-edit-gate.md
- docs/api/agent_profiles/curator-carla.md
- docs/api/agent_profiles/debugger-debbie.md
- docs/api/agent_profiles/designer-dagmar.md
- docs/api/agent_profiles/doctrine-daphne.md
- docs/api/agent_profiles/frontend-freddy.md
- docs/api/agent_profiles/generic-agent.md
- docs/api/agent_profiles/human-in-charge.md
- docs/api/agent_profiles/index.md
- docs/api/agent_profiles/node-norris.md
- docs/api/agent_profiles/randy-reducer.md
- docs/api/agent_profiles/retrospective-facilitator.md
- docs/architecture/profile-load-reliability.md
- docs/architecture/spdd-reasons.md
- docs/development/page-inventory.yaml
- docs/guides/how-to/harnesses/amazon-q.md
- docs/guides/how-to/harnesses/augment.md
- docs/guides/how-to/harnesses/claude-code.md
- docs/guides/how-to/harnesses/codex.md
- docs/guides/how-to/harnesses/copilot.md
- docs/guides/how-to/harnesses/cursor.md
- docs/guides/how-to/harnesses/gemini.md
- docs/guides/how-to/harnesses/kilocode.md
- docs/guides/how-to/harnesses/kiro.md
- docs/guides/how-to/harnesses/opencode.md
- docs/guides/how-to/harnesses/pi-tui.md
- docs/guides/how-to/harnesses/qwen.md
- docs/guides/how-to/harnesses/windsurf.md
- tests/architectural/test_docs_cli_reference_parity.py
- tests/docs/test_charter_selection_key_teaching.py
- tests/specify_cli/skills/test_retired_charter_skills.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP18 – Skill families

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(This WP renames that very skill to `spk-charter-profile-load`, and edits this sentence in the source template.)

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

FR-008, as ruled in OD-7 (the five backing skills only; the rest of the `spec-kitty-*` layer is follow-up #5830):

| New skill | Built from (folded in, then deleted) |
|---|---|
| `spk-charter-governance` | `spk-doctrine-charter` + `spec-kitty-charter-doctrine` |
| `spk-charter-glossary` | `spk-doctrine-glossary` + `spec-kitty-glossary-context` |
| `spk-charter-profile-load` | `spk-doctrine-profile-load` + `ad-hoc-profile-load` |
| `spk-charter-spdd-reasons` | `spk-doctrine-spdd-reasons` + `spec-kitty-spdd-reasons` |
| `spk-practice-bulk-edit` | `spk-doctrine-bulk-edit` + `spec-kitty-bulk-edit-classification` |
| `spk-practice-semantic-compression` | `spk-doctrine-semantic-compression` |
| `spk-practice-show-me` | `spk-doctrine-show-me` |

(Mapping and moves: `occurrence_map.yaml` `moves:` FR-008 block.) Done means:

- The seven new directories exist under `src/charter/offering/skills/` (the SOURCE; agent copies are generated and git-ignored here); the twelve old directories are gone (C-001: no alias skill, no "Legacy Alias" section, no redirect stub).
- `spec-kitty-constitution-doctrine` is also added to `RETIRED_CANONICAL_SKILL_NAMES` (WP10 stops `m_3_1_1_charter_rename` from renaming it into the retired `spec-kitty-charter-doctrine`, so an old global copy would otherwise linger).
- All thirteen retired names (the twelve FR-008 names plus `spec-kitty-constitution-doctrine`; orchestrator ruling FI-S4) are in `RETIRED_CANONICAL_SKILL_NAMES` (`src/specify_cli/skills/retired.py`), so user-global roots drop them on the next CLI run (`runtime/agent_skills.py:196-206`), and the upgrade finalizer's manifest reconciliation retires project-root copies.
- No living surface (skills, both packs' sources, living docs, `src/`) names a removed skill; derived files are regenerated, not hand-edited.
- `doctrine-daphne` is untouched (C-004).
- WP01 acceptance tests marked `pending_until("WP18")` (FR-008, US4 scenario 1, and `test_fr012_installed_removed_skills`, the installed-skill removal through `spec-kitty upgrade`, which can pass only once the sources are gone) go red → green.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; `spec.md` FR-008, OD-7, C-001, C-003, C-004, C-008 ("FR-008 before FR-018"); `research/runtime-seams.md` §5 (retirement mechanics: global roots by name, project roots by manifest, hash-matched removal step in the cutover migration) and §1.5 (migrations that read skill sources); `occurrence_map.yaml` FR-008 moves; `plan.md` design decision 7.
- **CLAUDE.md template rule**: edit SOURCE files only (`src/charter/offering/skills/`, `packs/built-in/missions/...`); never edit `.claude/`, `.agents/`, etc. They are regenerated by `spec-kitty upgrade` / `spec-kitty agent config sync`. Ignore `.claude/worktrees/agent-*` entirely.
- **Upstream you rely on**: WP12's cutover migration (T063) removes installed copies of removed skills (manifested, or unmanifested when the content hash matches a shipped version; edited copies kept and reported). WP10 neutralised `m_2_1_2_fix_glossary_context_skill` (it reads `spec-kitty-glossary-context/SKILL.md`, which you delete) and made `m_3_1_1_charter_rename` stop recreating `spec-kitty-charter-doctrine`. Verify both before deleting directories:
  ```bash
  rg -n "spec-kitty-glossary-context|spec-kitty-charter-doctrine" src/specify_cli/upgrade/migrations/
  ```
  Any remaining **read** of a deleted skill source in a migration that is not a recorded no-op is a blocker: report it; do not patch WP10's migrations here.
- **WP12 consistency**: open the WP12 cutover-migration module (`src/specify_cli/upgrade/migrations/m_*charter_pack_cutover*.py` and its snapshot/data module). Confirm the list of removed skill names it acts on equals the thirteen names above (WP12's `REMOVED_SKILL_NAMES` has all thirteen) and that its hash set covers the **shipped** versions of the twelve that had shipped sources. If WP12 embedded a different list, record the mismatch and raise it with the orchestrator; do not fork a second list.
- Pack tiers (C-003): only consumer-facing guidance goes in `packs/built-in`; after any pack edit run `spec-kitty charter pack regenerate-graph`.
- Prose inside the skills you fold: apply the FR-018 forbidden-token list (`spec.md` "FR-018 closed lists") to text you touch (e.g. "doctrine pack" → "Charter Pack", `.kittify/doctrine` → `.kittify/charter-packs`). Python symbol names quoted in skill prose (`DoctrineService`, `doctrine_service_builder`) are renamed later by WP19/WP20; leave them, and note it in the Activity Log for WP22's final prose sweep.

## Branch Strategy

- **Strategy**: lane per `lanes.json` (filled by finalize)
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first commit (C-006 / C-011)

```bash
rg -n 'pending_until\("WP18"\)' tests/acceptance/charter_pack_cutover/
```

These are WP01 T008's skills cases (FR-008; US4 scenario 1: after upgrade, `spk-charter-*`/`spk-practice-*` present, no removed name in project or user-global roots, no orphan manifest entries). Also `test_fr012_installed_removed_skills` in `test_upgrade_migration.py` (manifested and hash-equal installed copies removed through `spec-kitty upgrade`, edited copy kept and reported): WP12 built the removal step, but the finalizer reinstalled the skills until this WP deleted their sources. Remove only the markers; run; confirm red; commit `test(acceptance): unmark WP18 FR-008 tests (red) (#3732)`.

## Subtasks & Detailed Guidance

### Subtask T088 – Skill renames and folds (seven `spk-*`, five folded)

- **Purpose**: one skill per capability, named in the charter vocabulary (FR-008).
- **Steps** (one commit per new skill keeps review tractable):
  1. For each row of the table, `git mv` the **richer** source into the new directory so history follows the content:
     - governance: `git mv src/charter/offering/skills/spec-kitty-charter-doctrine src/charter/offering/skills/spk-charter-governance` (870-line `SKILL.md` plus `references/doctrine-artifact-structure.md`, `references/charter-command-map.md`); then merge the 21-line `spk-doctrine-charter/SKILL.md` flow into the top of the new `SKILL.md` and `git rm -r` the thin directory.
     - glossary: `spec-kitty-glossary-context` (342 + 2 references) → `spk-charter-glossary`; merge `spk-doctrine-glossary` (24).
     - profile-load: `spk-doctrine-profile-load` (41 + `references/profile-load-mechanics.md`) → `spk-charter-profile-load`; merge the trigger phrases from `ad-hoc-profile-load/SKILL.md` (38; "act as the architect", "load the reviewer profile", …) into the description; delete `ad-hoc-profile-load`.
     - spdd-reasons: `spec-kitty-spdd-reasons` (178) → `spk-charter-spdd-reasons`; merge `spk-doctrine-spdd-reasons` (20).
     - bulk-edit: `spec-kitty-bulk-edit-classification` (358) → `spk-practice-bulk-edit`; merge `spk-doctrine-bulk-edit` (24).
     - `spk-doctrine-semantic-compression` → `spk-practice-semantic-compression` (rename only).
     - `spk-doctrine-show-me` → `spk-practice-show-me` (rename only; keeps `assets/` and `references/`, including the byte-pinned `MERMAID_DIAGRAMMING.md` / `PLANTUML_DIAGRAMMING.md`).
  2. In every new `SKILL.md`: frontmatter `name:` equals the directory name; one `description:` that keeps the union of trigger phrases (agents select skills by description, so do not lose triggers from either source) and the "Does NOT handle" boundaries; delete every "Legacy Alias" / "compatibility alias" section (e.g. `spk-doctrine-charter/SKILL.md` "## Legacy Alias", `ad-hoc-profile-load` "This is the compatibility alias…"). Rename the reference file `references/doctrine-artifact-structure.md` only if its name is tier sense (record the decision).
  3. Cross-references between the folded skills (e.g. governance pointing at `spec-kitty-glossary-context`) become the new names.
  4. Apply the FR-018 forbidden-token cleanup to the prose you fold (see Context).
  5. Do not touch `doctrine-daphne` (agent profile, C-004) or any other `spec-kitty-*` skill directory except to repoint references (T089).
- **Files**: the 19 skill directory globs in `owned_files`.
- **Parallel?**: The seven folds are independent of each other.
- **Notes**: the skill registry discovers directories under the skills root (`src/specify_cli/skills/registry.py`); a directory without a valid `SKILL.md` frontmatter breaks discovery. Validate after each fold with `uv run pytest tests/doctrine/test_spk_skill_pack.py -q` (after T091 updates it) or a quick `SkillRegistry.from_package().discover_skills()` listing.
- **Validation**: [ ] `ls src/charter/offering/skills | rg 'spk-doctrine-|charter-doctrine|glossary-context|bulk-edit-classification|spec-kitty-spdd-reasons|ad-hoc-profile-load'` is empty; [ ] seven new directories present with matching `name:`.

### Subtask T089 – `RETIRED_CANONICAL_SKILL_NAMES`; skill manifests; references in prompts/skills

- **Purpose**: removed names disappear from every installed root and every living reference.
- **Steps**:
  1. `src/specify_cli/skills/retired.py`: add all thirteen names (the twelve plus `spec-kitty-constitution-doctrine`) to `RETIRED_CANONICAL_SKILL_NAMES` with a comment `# Renamed/folded by #3732 (FR-008): spk-charter-* / spk-practice-*.` Keep the frozenset sorted by group as today.
  2. Project roots: the upgrade finalizer (`upgrade/assessment.py:121-139` → `assess_skill_installation(..., retire=True)`) retires manifested entries the catalog no longer expects; WP12 covers unmanifested hash-matched copies. Confirm end-to-end in a temp project (the WP01 US4 acceptance test does this; run it).
  3. `m_3_2_0rc35_spk_skill_pack.py:151` filters `RETIRED_CANONICAL_SKILL_NAMES` out of the preserved manifest; adding names here is the intended effect. Run `tests/upgrade/migrations/test_m_3_2_0rc35_spk_skill_pack.py`.
  4. `src/specify_cli/upgrade/migrations/m_3_2_0rc35_kittify_profile_handoff.py:78,87,101` writes text naming `/ad-hoc-profile-load` into consumer prompts. Read its `detect()`/`apply()` first: if idempotence keys on a heading or marker, update the literal to `/spk-charter-profile-load` (body edit; `migration_id` unchanged per the occurrence-map exception). If it keys on the full block text, changing it would re-apply on already-migrated projects: then leave the literal, record the finding, and raise it with the orchestrator (the cutover migration may need to rewrite the stale skill name in consumer overrides). Do not guess.
  5. Repoint every reference (listed in `owned_files`), replacing each removed name with its new name and `spk-doctrine-*` family mentions with `spk-charter-*` / `spk-practice-*`:
     - skills: `skills/README.md` (table rows l.~130), `spec-kitty/SKILL.md`, `spec-kitty-mission-review/SKILL.md`, `spk-admin-agent-config/SKILL.md`, `spk-meta-skill-map/SKILL.md` (family list l.27, l.40) and `references/spk-skill-map.md`, `spk-meta-skill-authoring/SKILL.md` (family list l.23: replace `doctrine` with `charter` and add `practice`), `spk-mission-{documentation,plan,specify}/SKILL.md`, `spk-start-command-map/references/command-map.md`, `spk-start-here/SKILL.md`.
     - pack sources: the three `task-prompt-template.md` files ("Use the `/ad-hoc-profile-load` skill…" → `/spk-charter-profile-load`), the nine mission-step `prompt.md` files, `tactics/reviewer-implementer-role-separation.tactic.yaml`, `toolguides/CONTEXTIVE.md`.
     - src prose, not owned (one-line follow-ups; log them): `src/charter/activation/synthesizer/errors.py:11` (WP03), `src/specify_cli/cli/commands/charter/_synthesis.py:186` (WP03), `src/specify_cli/cli/commands/charter/synthesize.py:139` (WP03), `docs/api/cli-commands.md` (generated, unowned; it embeds the synthesize help: regenerate it, step T090.5).
     - docs: `docs/api/skills/index.md` (the "## spk-doctrine-*" section l.95-104 becomes two families), `git mv docs/api/skills/spk-doctrine-profile-load.md docs/api/skills/spk-charter-profile-load.md` (update its frontmatter title/description), `docs/api/skills/{spk-meta-skill-map,spk-start-here}.md`, `docs/api/toc.yml:50-51`, `docs/development/page-inventory.yaml:1499`, `docs/api/bulk-edit-gate.md`, the eleven `docs/api/agent_profiles/*.md` pages ("see the `ad-hoc-profile-load` skill"), `docs/architecture/{profile-load-reliability,spdd-reasons}.md`, the thirteen `docs/guides/how-to/harnesses/*.md` pages.
  6. "Skill manifests": the in-repo indexes above (skills README table, skill map, docs index/toc/page inventory) are the manifests to keep consistent. `.kittify/command-skills-manifest.json` is unaffected (none of the twelve is a command skill, research §5).
- **Files**: as listed.
- **Parallel?**: After T088 (names must exist).
- **Notes**: C-002: leave `docs/adr/**`, `docs/archive/**`, `docs/plans/**`, released changelog sections and `.kittify/migrations/**` untouched even though they name the old skills.
- **Validation**:
  ```bash
  rg -n "spk-doctrine-|spec-kitty-charter-doctrine|spec-kitty-glossary-context|spec-kitty-bulk-edit-classification|spec-kitty-spdd-reasons|ad-hoc-profile-load" \
     src packs docs AGENTS.md -g '!docs/adr/**' -g '!docs/archive/**' -g '!docs/plans/**' -g '!docs/changelog/**' -g '!docs/reports/**'
  ```
  returns only `src/specify_cli/skills/retired.py`, the WP12 cutover migration module, and (until regenerated in T090) generated files.

### Subtask T090 – Regenerate derived files

- **Purpose**: generated surfaces follow the sources; never hand-edit them.
- **Steps**:
  1. Command baselines and skill snapshots: `uv run spec-kitty regen` then `uv run spec-kitty regen --check` (rewrites `tests/specify_cli/regression/_twelve_agent_baseline/**` and `tests/specify_cli/skills/__snapshots__/**` from the edited prompt sources).
  2. Completion manifest: `python -m specify_cli.completion --regenerate` (the synthesize help text names the governance skill). Shared generated file: regenerate on any rebase conflict.
  3. Built-in pack manifest: `uv run spec-kitty charter pack regenerate-graph` (WP15's home) after the pack edits; `--check` must exit 0.
  4. Retrieval index: `python scripts/docs/docs_index.py --write` (`docs/development/docs-retrieval-index.yaml` header says so); commit the result.
  5. CLI reference: if `docs/api/cli-commands.md` embeds generated help that changed, refresh it with `scripts/docs/build_cli_reference.py` (check its usage); it has no owner; log the regeneration.
- **Files**: generated outputs, none of them in `owned_files` (tasks.md: generated files have no owner; regenerate, never hand-merge).
- **Parallel?**: After T089.
- **Validation**: [ ] `uv run spec-kitty regen --check` and `uv run spec-kitty charter pack regenerate-graph --check` exit 0; [ ] `uv run pytest tests/architectural/test_completion_manifest_freshness.py -q` passes.

### Subtask T091 – Tests; flip FR-008 xfails

- **Purpose**: pin the new families and the retirement.
- **Steps**:
  1. (`tests/doctrine/**` is owned by WP23, which moves the directory; these three edits are logged follow-ups. If WP23 has already moved the directory, edit the files at their new path.) `tests/doctrine/test_spk_skill_pack.py`: the expected name set (l.22-28 `spk-doctrine-*`, l.60 `spec-kitty-charter-doctrine`, l.187-205 alias assertions) becomes the seven new names; delete assertions that the alias skill points at the canonical one (no alias exists). `tests/doctrine/test_spdd_reasons_skill.py`, `test_spk_show_me_skill.py`: new paths.
  2. `tests/architectural/test_no_dead_doctrine_paths.py:254-265`: byte-pinned asset paths move to `spk-practice-show-me/assets/…` (NFR-002 gate; keep its allowlist unchanged or shrinking).
  3. `tests/architectural/test_docs_cli_reference_parity.py:17,221-225`: the profile-subcommand guard reads `ad-hoc-profile-load/SKILL.md`; point it at `spk-charter-profile-load/SKILL.md` (and keep it non-vacuous: assert the file exists).
  4. `tests/docs/test_charter_selection_key_teaching.py:10`: path → `spk-charter-governance/SKILL.md`.
  5. New `tests/specify_cli/skills/test_retired_charter_skills.py`: (a) the thirteen names are in `RETIRED_CANONICAL_SKILL_NAMES`; (b) none of them exists in the shipped registry (`SkillRegistry.from_package()`), and all seven new names do; (c) in a temp HOME with a global skill root holding `spk-doctrine-charter/` and `spec-kitty-glossary-context/`, `assess_global_agent_skills` (`runtime/agent_skills.py`) marks both for retirement while an unrelated custom skill is preserved (positive control). Mark `fast`.
  6. Not owned, follow-ups if they fail: `tests/specify_cli/upgrade/test_skill_update_external_symlinks.py` (drives the neutralised glossary-context migration; WP10 owns that change), `tests/upgrade/test_charter_rename_migration.py` (WP10), `tests/specify_cli/tool_surface/providers/test_managed_skills.py` (WP17).
  7. Run the WP18 acceptance tests: green. Commit `feat(skills)!: spk-charter-* and spk-practice-* families (#3732)`.
- **Validation**: [ ] `rg -n 'pending_until\("WP18"\)' tests` empty.

## Test Strategy

```bash
make test-fast
uv run pytest tests/acceptance/charter_pack_cutover/ -q          # WP18-marked tests at least
uv run pytest tests/charter/ tests/doctrine/ -q                  # src/charter/offering/** changed
uv run pytest tests/specify_cli/skills/ tests/runtime/test_upgrade_preview_bootstrap.py \
              tests/upgrade/migrations/test_m_3_2_0rc35_spk_skill_pack.py tests/docs/test_charter_selection_key_teaching.py -q
uv run pytest tests/architectural/test_no_dead_doctrine_paths.py \
              tests/architectural/test_docs_cli_reference_parity.py \
              tests/architectural/test_completion_manifest_freshness.py \
              tests/architectural/test_pack_manifest_no_author_edit.py \
              tests/architectural/test_skill_catalog_seam.py \
              tests/architectural/test_no_legacy_terminology.py -q
uv run spec-kitty regen --check
uv run spec-kitty charter pack regenerate-graph --check
uv run ruff check src tests && uv run ruff format --check --force-exclude <touched .py files>
uv run mypy src/specify_cli/skills/retired.py src/specify_cli/upgrade/migrations/m_3_2_0rc35_kittify_profile_handoff.py src/charter/activation/synthesizer/errors.py
```

Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **A migration still reads a deleted skill source** → discovery-wide or apply-time failure. Mitigation: the Context grep before deleting; WP10 owns the fix.
- **Lost trigger phrases** make agents stop selecting a skill. Mitigation: union of descriptions; reviewer diffs old vs new frontmatter.
- **Edited consumer copies**: WP12 keeps them and reports; do not add removal logic here (research §5 decision b).
- **Generated-file conflicts with WP16/WP22 lanes**: regenerate, never merge by hand.
- **Docs overlap with WP22** (living docs prose): you change skill names only; leave broader prose to WP22.

## Review Guidance

- Red-on-base → green-on-final for the WP18 acceptance tests.
- Seven directories present, twelve gone; no alias/redirect skill; `name:` equals directory; descriptions keep both sources' triggers.
- Retired list contains exactly the twelve FR-008 names plus `spec-kitty-constitution-doctrine` (thirteen); WP12's migration list matches (recorded).
- Validation grep in T089 is clean; regen/pack/completion checks exit 0.
- `doctrine-daphne` and historical roots untouched.
- Follow-up edits outside `owned_files` logged.

## Definition of Done

- [ ] Red-first commit, then green.
- [ ] Folds done with history-preserving moves; old directories deleted.
- [ ] `RETIRED_CANONICAL_SKILL_NAMES` extended; references repointed across skills, pack sources, docs and src prose.
- [ ] Derived files regenerated with their `--check` modes green.
- [ ] New retirement test added; touched tests updated.
- [ ] Commands above run and recorded; ruff/format/mypy clean; terminology gate green.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (`date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

## Carry-over from WP12 (approved)

- WP12's cutover skills step (`src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py`) deliberately skips any removed-skill name the installed catalog still ships; each name starts being removed once you delete its source. `test_fr012_installed_removed_skills` (acceptance) should turn green when the sources are gone — flip it as part of your red-first.
- `test_frozen_hashes_match_the_shipped_sources` skips itself once the sources are gone (expected).
- Edited installed copies keep their skills-manifest entries; confirm the finalizer's reconciliation does not then archive/remove them in a way that contradicts US4 (edited copies are kept and reported). Record the outcome.
