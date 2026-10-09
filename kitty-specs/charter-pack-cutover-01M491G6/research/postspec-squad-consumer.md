# Post-spec review: consumer lens (charter-pack-cutover-01M491G6)

Reviewer profile: doctrine-daphne (curator). Read-only review of `kitty-specs/charter-pack-cutover-01M491G6/spec.md` at 01476e16 on `issue-3732-charter-pack-rename`, against ADR 2026-10-06-1, `docs/context/charter.md`, the CLAUDE.md Pack Tiers section, `packs/internal/` and the live code.

Severity counts: 4 blocker, 8 should-fix, 5 owner-question, 3 nit.

---

## Blockers

### B1. `doctrine_pack_id` is a persisted, `extra="forbid"` key the spec never mentions
- **Where:** FR-010, FR-012, SC-003, Bulk edit declaration ("serialized keys **are** renamed").
- **Evidence:** `ActivationEntry` (`src/charter/activation/activations.py:217`, `model_config = ConfigDict(extra="forbid")`) carries `doctrine_pack_id`. It is persisted in two places:
  - the project's `charter.yaml` `governance.activations`;
  - every org pack's `org-charter.yaml` `activations:` (`OrgCharterPolicy.activations`, `src/specify_cli/doctrine/org_charter.py:175`).

  It is also the dedup identity key `_activation_identity_key`. Its special value `project` names the `.kittify/doctrine/` layer.
- **Impact:** The spec can go either way, and both are unspecified:
  - **Rename it:** FR-012 must rewrite `charter.yaml`. Every third-party `org-charter.yaml` that uses activations then fails validation, and no migration touches fetched packs.
  - **Keep it:** SC-003 / NFR-002 need a named exemption.
- **Proposed change:** Add `doctrine_pack_id` explicitly to the occurrence rules, as either "renamed to `charter_pack_id`" or "kept, exempted". If renamed:
  - FR-012 rewrites `charter.yaml` activations;
  - FR-018 (see S3) covers the pack-side break;
  - the `org-charter.yaml` `schema_version` is bumped so `charter pack validate` can say what changed.

### B2. Removing `default.yaml` and the preset registry breaks the rc35 migration in the upgrade chain
- **Where:** FR-005, FR-012.
- **Evidence:** `src/specify_cli/upgrade/migrations/m_3_2_0rc35_default_charter_pack.py` does two things that FR-005 deletes:
  - it imports `specify_cli.charter_pack_registry` (l.49);
  - it reads `src/charter/activation/packs/default.yaml` (l.67–76) and returns `errors=["default.yaml not found ..."]` when that file is missing (l.152–156).
- **Impact:** A project older than rc35 that upgrades across this release either:
  - hits an import error or a migration error; or
  - if the rc35 migration were kept alive, gets written the very stale lists that the new migration then has to reset.
- **Proposed change:** Add to FR-005/FR-012:
  - the rc35 migration is retired (a no-op that records itself applied);
  - the new migration carries the stale lists as frozen data inside the migration, because the source file is deleted (see S6);
  - a fixture upgrades from a pre-rc35 project shape in one `spec-kitty upgrade`.

### B3. An org preset cannot reference built-in artifacts under the stated edge case
- **Where:** Edge Cases ("A preset that names an artifact the pack does not ship: activation fails"), FR-004, US1-3.
- **Impact:** A realistic org preset ("our baseline") is mostly built-in directives and tactics plus a few org ones. With pack-local resolution, FR-004's org presets are close to unusable.
- **Unspecified:** The spec also leaves three related points open:
  - what an absent kind in an org preset means (all built-in? all built-in plus all org?);
  - whether a preset can lower an org's `required_<kind>` (it must not);
  - whether a preset carries context-scoped activations (registry entries) or `selected_<kind>`.
- **Proposed change:**
  - Define the reference scope: ids resolve against the whole offering, optionally pack-qualified as `<pack>:<id>`. The failure case becomes "an id no pack in the offering ships".
  - Add an FR stating that preset application is unioned with the org `required_<kind>`.
  - Define what absent means per kind in a non-built-in preset.

### B4. The preset file format is not specified anywhere a pack author can read
- **Where:** FR-002, FR-004, FR-016 ("the presets directory"), Key Entities, and the edge case about the public-packs repo.
- **Missing:** The spec never gives:
  - the directory name;
  - the file naming (`presets/<name>.yaml`?);
  - the schema (per-kind `activated_<kind>` keys? `mission_type_activations`? absent vs `[]` semantics, which matter given the three-state `activated_<kind>` model);
  - a name grammar;
  - versioning.

  The sidecar repository's authors have nothing to write against. `charter pack validate` is only promised to validate "exactly as `doctrine pack validate` did" (US3-1), which by definition does not know presets.
- **Proposed change:** Add FR-019:
  - a documented preset schema (a schema file in `src/charter/offering/schemas/` plus a reference doc page);
  - `charter pack validate` and `charter org validate` reject a malformed preset and an unresolvable id, with the file and the id named;
  - `charter org init` scaffolds an example `presets/` file.

  Amend US3-1 to "validates as before **plus** presets".

---

## Should-fix

### S1. FR-012's migration inventory is incomplete and partly stale
- **Where:** FR-012, US2, NFR-001.
- **Persisted consumer-state items that name the old vocabulary or path, and whether FR-012 covers them:**

| Item | Evidence | Covered? |
|---|---|---|
| `config.yaml` `doctrine.org.packs[]` | `org_pack_config.py:56-57` | yes |
| `config.yaml` single-pack `doctrine.org.{local_path,subdir,source_type,url,ref}`, auto-named `"default"` | `_build_legacy_single_pack`, `org_pack_config.py:684`; `_LEGACY_DEFAULT_PACK_NAME = "default"` | **no**. The migration must give it an explicit name. "default" also collides with the preset name (`--pack default` vs `--preset default`). |
| `config.yaml` top-level `organisation_packs[]` | `org_pack_config.py:453,509` | **no** (see Q2) |
| `charter.yaml` `governance.doctrine` | `sync.py:244` | yes (US2) |
| standalone legacy `governance.yaml` | folded by `m_unify_charter_activation_finalize` with the same compat | **implicit**. Once FR-011 deletes `apply_legacy_governance_selection_key_compat`, that older migration loses its helper. State it. |
| `.kittify/charter/interview/answers.yaml` top-level `doctrine:` | only `scripts/migrate_charter_interview_answers.py`, not an upgrade migration | **no** |
| `.kittify/doctrine/` and every subdir: `directive/ tactic/ styleguide/ procedure/ agent_profiles/ mission_step_contracts/ mission_types/<t>/governance-profile.yaml overlays/ skills/ graph.yaml` | `mission_type_profile_repository.py:52`, `catalog.py:60`, `project_registration.py:297`, `kind_vocabulary.py:295` | "move" covers it generically; the subdirs should be listed for the fixture |
| `.kittify/charter/synthesis-manifest.yaml` `artifacts[].path` (prefix `.kittify/doctrine`) | `synthesizer/manifest.py:38,58` | **no**. After the move, `charter bundle validate` / provenance checks (`bundle.py:66,274-336`) see orphaned paths. |
| `.kittify/charter/provenance/*` sidecars keyed to `.kittify/doctrine/...` paths | `bundle.py:309-336` | **no** |
| `.kittify/skills-manifest.json` `source_ref` for project pack skills (`.kittify/doctrine/skills/...`) | `skills/manifest.py:43` | **no**. Pack-skill drift fires after the move. |
| stale `activated_<kind>` lists in `config.yaml` **or** in `charter.yaml` via the INV-2 `charter:` pointer | glossary `activated_<kind>` | **ambiguous**. Name both locations. |
| installed skill copies `spk-doctrine-*`, `spec-kitty-charter-doctrine`, `spec-kitty-glossary-context`, `spec-kitty-bulk-edit-classification`, `spec-kitty-spdd-reasons`, `ad-hoc-profile-load` in **project and user-global** roots | `m_3_0_3_globalize_skill_pack`; `~/.claude/skills` on this machine holds all of them | **partial**: FR-008 says "regenerated". Edited copies are preserved by the installer's prune, and global roots are not named. |
| `.kittify/command-skills-manifest.json` / `.agents/skills/spec-kitty.*` entries | `command_installer.py:392` | **implicit** in FR-008 |
| generated agent command files citing `spk-doctrine-*` / `spec-kitty doctrine` | source prompts `packs/built-in/missions/mission-steps/{software-dev,plan}/{specify,plan,charter}/prompt.md` | yes, via regeneration (FR-008/FR-010). Say so explicitly. |
| `.gitignore` patterns for `.kittify/doctrine/**` with negations | this repo `.gitignore:103-112` | **no**. After the move, `.kittify/charter-packs/graph.yaml`, `mission_types/` and so on become untracked and committable. |

- **Also stale:** FR-012 says "including this repository's own `doctrine.org.packs`", but `.kittify/config.yaml:31` already uses `charter_packs.org.packs`. What this repo actually needs migrated is `.kittify/doctrine/{directive,overlays,procedure,tactic}` and its `.gitignore`.
- **Proposed change:**
  - Turn FR-012 into an inventory table: item, old form, new form, and action (rename / move / rewrite path / reset / remove / report).
  - Add the missing rows.
  - Extend NFR-001's fixture list: single-pack legacy, pointer-chased `charter.yaml`, synthesized artifacts with provenance, project pack skills, an edited installed skill copy.
  - Require a dry-run report, per `docs/migrations/migration-and-shim-rules.md` §3.

### S2. In-flight missions and worktrees are not addressed
- **Where:** FR-011, FR-012, Edge Cases.
- **Evidence:** `spec-kitty upgrade` rewrites the checkout it runs in. Lane worktrees, the coordination worktree and other branches keep `.kittify/doctrine/` and the legacy keys.
- **Impact:**
  - Under FR-011, every charter command run inside a lane fails with "run spec-kitty upgrade".
  - A later `consolidate` can re-introduce `.kittify/doctrine/` onto the target.
- **Proposed change:** Add an edge case plus a requirement covering three points:
  - The migration refuses, or warns and lists, while missions have live lane or coordination worktrees.
  - Or the unmigrated-project error, raised inside a worktree, names the remedy: upgrade, then rebase or merge the lane.
  - A fixture consolidates a lane created before the upgrade.

### S3. Nobody rewrites a third-party pack, and the spec gives authors no compatibility statement
- **Where:** FR-005, FR-006, FR-010, Assumptions.
- **Evidence:**
  - `PackDescriptor` is `extra="forbid"` (`src/specify_cli/doctrine/pack_descriptor.py:50`). Once `accompanies_doctrine_pack` is deleted, any `pack.yaml` still carrying it fails to load.
  - Pack prose embeds retired commands. Worked example `packs/internal/`:
    - `skills/report-debrief.skill.md:16` (`spec-kitty doctrine asset path`);
    - `toolguides/test-quality-triage.toolguide.yaml:21`;
    - `toolguides/TEST_QUALITY_TRIAGE.md:36`;
    - `procedures/test-suite-quality-assessment.procedure.yaml:47`;
    - `procedures/executive-debrief-generation.procedure.yaml:47`;
    - `README.md` (calls itself an "org-tier doctrine pack" throughout).
  - Built-in content needs the same pass, for example `procedures/onboard-external-agent-to-pack.procedure.yaml` and `agent_profiles/doctrine-daphne.agent.yaml`.
  - The internal pack's `org-charter.yaml` and `drg/fragment.yaml` need no key change; only comments and prose change.
  - CLAUDE.md's Pack Tiers section says "run `spec-kitty doctrine regenerate-graph`".
- **Impact:** A fetched pack's procedures keep telling agents to run a command that no longer exists. The upgrade migration never sees that pack.
- **Proposed change:** Add FR-018 "Pack-format compatibility":
  - (a) a short pack-format change statement (removed descriptor field, new `presets/`, any key renamed under B1);
  - (b) `charter pack validate` / `charter org validate` reject the retired descriptor field and report retired command spellings in pack prose with a message naming the replacement. This is a validation diagnostic, not a shim, so C-001 holds;
  - (c) `packs/internal/` and the CLAUDE.md Pack Tiers text are updated in this mission as the worked example, then the pack-manifest regen gate is run (C-003 still holds: nothing moves tiers).

  FR-006 must also **name** the new homes for `asset` and `regenerate-graph`. Pack authors write those commands into procedures, so "a `charter` home" is not enough.

### S4. The command Before/After is incomplete
- **Where:** FR-006, FR-007, SC-004.
- **Evidence:** Live CLI lists commands the spec does not map:
  - `doctrine fetch`, `doctrine new`, `doctrine validate`, `doctrine org` (already duplicated under `charter`);
  - `doctrine mission-type`.

  It also leaves three overlaps open:
  - `charter org validate` vs the new `charter pack validate`: two validators for pack authors, with no ruling on which is canonical;
  - `spec-kitty doctor doctrine` (+ `--json`, `_render_doctrine_pack`) is a consumer-visible "doctrine" command that FR-007 does not cover;
  - `charter pack path <name>` silently changes its argument from a preset name to a pack name.
- **Proposed change:** Put the full Before/After table in the spec, either as an FR-006 appendix or by reference to a named section. Cover every `doctrine *` leaf, `doctor doctrine`, the `charter pack path` argument change and any JSON output keys that are renamed.

### S5. Messaging is not a requirement
- **Where:** Assumptions, Edge Cases.
- **Evidence:** The changelog Before/After appears only in an assumption and an edge case. There is no FR and no SC for it, and no `docs/migrations/` runbook requirement.
- **Existing runbooks that will describe a removed surface:**
  - `docs/migrations/doctrine-local-overlay-to-org-layer.md`;
  - `docs/migrations/relocate-builtin-doctrine-packs.md`.

  They need to be classified as historical or updated.
- **Proposed change:** Add FR-017, delivering:
  - (a) CHANGELOG Unreleased Before/After for commands, skills, config keys, directories, the descriptor field and JSON keys;
  - (b) a runbook `docs/migrations/charter-pack-cutover.md` covering operators, pack authors and saved scripts;
  - (c) an upgrade summary printed by the migration: moved, rewritten, reset, and left-for-review items, including the "stale list plus one customisation" report from the edge cases;
  - (d) the FR-011 error text naming both `spec-kitty upgrade` and the runbook.

### S6. "Equals the stale `default.yaml`" is not well-defined
- **Where:** FR-012, US2-2, NFR-001.
- **Evidence:**
  - `default.yaml` is deleted by FR-005, so the migration needs its contents frozen as data.
  - Projects wrote it at different releases (rc35 migration, `charter pack apply default`), possibly with different contents. This clone is shallow, so the history could not be counted.
  - The comparison unit is also unstated: the whole set across kinds, or per kind.
  - Projects with `minimal` applied are not addressed.
- **Proposed change:**
  - Specify that the migration embeds every released `default.yaml` snapshot.
  - Specify the comparison per kind.
  - State explicitly that a `minimal`-equal list is kept, and reported as "matches preset minimal".

### S7. Glossary: collisions left by FR-013
- **Where:** FR-013, Domain Language.
- **Evidence:** In `docs/context/charter.md`:
  - The `charter` entry's "Do NOT use when" (l.31) still prescribes **Active Charter artifact / Inactive Charter artifact** and **Pack Default Charter**, citing the missing ADR 2026-08-22-2. "Active Charter artifact" and the new "active charter" differ only by a suffix and capitalisation.
  - **Charter Selection** (l.179, "the project-level selection layer that activates and narrows ...", `.kittify/charter/`) overlaps **active charter**.
  - **Doctrine Catalog** (l.192, "registry of all available ...") overlaps **charter offering**.
  - **Doctrine Pack**, **Doctrine Pack ID** and **Activation Registry** (tuple names `doctrine_pack_id`) and **Organization Tier** ("org doctrine packs") all describe the retired shape, with `doctrine.org.packs` and `.kittify/doctrine/`.
  - "Activation" is now overloaded three ways: activation preset, Activation Registry/Context, `activated_<kind>`.
  - **Charter Bundle** has no entry in `docs/context/` even though the spec calls it "unchanged".
- **Proposed change:** FR-013 should enumerate:
  - retire or redirect Doctrine Pack, Doctrine Pack ID and Doctrine Catalog;
  - define how Charter Selection relates to active charter, or retire it in favour of active charter;
  - rewrite the `charter` "Do NOT use when" cell;
  - add a "Do NOT use when" to activation preset that distinguishes it from Activation Registry;
  - add a Charter Bundle entry.

### S8. Undefined: what `.kittify/charter-packs/` is
- **Where:** FR-012, FR-016, US1, US3-3.
- **Questions the spec leaves open:**
  - Is the project layer itself a Charter Pack (id `project`, the special `doctrine_pack_id` value)?
  - Can it ship presets?
  - Does `charter pack list` show it?
- **Why it matters:** The directory name is plural, but the content is one project layer, so operators will guess.
- **Proposed change:** One sentence in Key Entities and an acceptance scenario on US3-3.

---

## Owner questions

- **Q1 (C-001 boundary):** Is a root-level unknown-command hint ("`spec-kitty doctrine` was removed in X; see docs/migrations/charter-pack-cutover.md") an alias or redirect stub?
  - It is not a registered command and does no work, so it is arguably messaging, not compatibility.
  - Registering a hidden `doctrine` group that prints an error clearly *is* a stub.
  - The spec should record the ruling either way. I did not decide it.
- **Q2:** Is the `organisation_packs` legacy flat key part of this cutover?
  - It is a read-side fallback in the same parser (`org_pack_config.py:509`).
  - Leaving it contradicts "one supported shape" (FR-011).
- **Q3:** Applying a preset replaces the active charter (US1-2: "equals the preset"), so it silently drops an operator's customised lists. Should it:
  - require `--yes` or show a diff first;
  - and record the applied preset name, so `charter list` can "show it" (US1-1)? Recording it would be new persisted state.
- **Q4:** The ADR §5 folds "the rest of that layer" of `spec-kitty-*` skills (git-workflow, runtime-next, mission-system, ...), but FR-008 says only "the older `spec-kitty-*` **charter** skills". Which scope applies?
- **Q5:** Should the migration use `git mv` (staged rename) or a plain filesystem move? This affects how consumers commit the result, and the dry-run wording.

## Nits

- **N1:** US4-1 checks "freshly upgraded project" skills only. Add the user-global skill root, which is where this machine actually holds `spk-doctrine-*`.
- **N2:** The `doctor shim-registry` entries for the removed compat layers (if any are registered) should be drained in the same change, so `doctor shim-registry` stays green.
- **N3:** Consumers' existing generated `.kittify/charter/charter.md` prose keeps "doctrine" wording. State that it is not rewritten, or that `charter generate` refreshes it, so SC-003 is not read as covering consumer files.
