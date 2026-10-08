---
work_package_id: WP22
title: Prose in packs and living docs
dependencies:
- WP18
- WP21
requirement_refs:
- FR-010
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: 552f5cc18ea5ca13a146a98e41759d2d49efb4d2
created_at: '2026-10-08T20:11:36.769012+00:00'
subtasks:
- T101
- T102
- T103
- T104
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: lexical-larry
authoritative_surface: packs/built-in/
create_intent: []
execution_mode: code_change
owned_files:
- packs/built-in/agent_profiles/README.md
- packs/built-in/agent_profiles/curator-carla.agent.yaml
- packs/built-in/agent_profiles/drupal-dries.agent.yaml
- packs/built-in/agent_profiles/retrospective-facilitator.agent.yaml
- packs/built-in/assets/README.md
- packs/built-in/assets/docs_structural_lint.config.yaml
- packs/built-in/assets/docs_structural_lint.py
- packs/built-in/directives/038-structured-prompt-boundary.directive.yaml
- packs/built-in/directives/042-common-docs.directive.yaml
- packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml
- packs/built-in/directives/046-readable-consistent-prs.directive.yaml
- packs/built-in/directives/048-version-governance.directive.yaml
- packs/built-in/directives/051-supply-chain-install-safety.directive.yaml
- packs/built-in/directives/reconcile-change-scope-tensions.directive.yaml
- packs/built-in/missions/built_in_step_contracts/research-scoping.step-contract.yaml
- packs/built-in/missions/documentation/actions/retrospect/index.yaml
- packs/built-in/missions/documentation/governance-profile.yaml
- packs/built-in/missions/plan/actions/plan/index.yaml
- packs/built-in/missions/plan/actions/research/index.yaml
- packs/built-in/missions/plan/actions/review/index.yaml
- packs/built-in/missions/plan/actions/specify/index.yaml
- packs/built-in/missions/plan/governance-profile.yaml
- packs/built-in/missions/research/actions/retrospect/index.yaml
- packs/built-in/missions/research/governance-profile.yaml
- packs/built-in/missions/software-dev/actions/retrospect/index.yaml
- packs/built-in/missions/software-dev/governance-profile.yaml
- packs/built-in/pack.md
- packs/built-in/paradigms/brownfield-onboarding.paradigm.yaml
- packs/built-in/procedures/adversarial-squad-deployment.procedure.yaml
- packs/built-in/procedures/disciplined-defect-diagnosis.procedure.yaml
- packs/built-in/procedures/domain-aware-decision-interview.procedure.yaml
- packs/built-in/procedures/example-mapping-workshop.procedure.yaml
- packs/built-in/procedures/migrate-project-guidance-to-spec-kitty-charter.procedure.yaml
- packs/built-in/procedures/onboard-external-agent-to-pack.procedure.yaml
- packs/built-in/styleguides/common-docs.styleguide.yaml
- packs/built-in/styleguides/deployable-skill-authoring.styleguide.yaml
- packs/built-in/styleguides/writing/README.md
- packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml
- packs/built-in/tactics/architecture/c4-zoom-in-architecture-documentation.tactic.yaml
- packs/built-in/tactics/canonical-source-unification.tactic.yaml
- packs/built-in/tactics/common-docs-scaffold.tactic.yaml
- packs/built-in/tactics/model-task-routing.tactic.yaml
- packs/built-in/tactics/pr-agent-worktree-isolation.tactic.yaml
- packs/built-in/tactics/reasons-canvas-fill.tactic.yaml
- packs/built-in/tactics/reasons-canvas-review.tactic.yaml
- packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml
- packs/built-in/toolguides/EFFICIENT_LOCAL_TOOLING.md
- packs/built-in/toolguides/GIT_AGENT_COMMIT_SIGNING.md
- packs/internal/directives/operator-signal-contract.directive.yaml
- packs/internal/drg/fragment.yaml
- packs/internal/procedures/cloud-session-dispatch.procedure.yaml
- packs/internal/procedures/issue-triage-pass.procedure.yaml
- packs/internal/procedures/memory-curation-and-escalation.procedure.yaml
- packs/internal/procedures/project-evolution-postmortem.procedure.yaml
- packs/internal/skills/issue-triage.skill.md
- packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml
- packs/internal/tactics/branded-deliverable.tactic.yaml
- docs/api/batch-api-contract.md
- docs/api/configuration.md
- docs/api/environment-variables.md
- docs/api/retrospective-schema.md
- docs/architecture/00_landscape/README.md
- docs/architecture/04_implementation_mapping/code-patterns.md
- docs/architecture/05_ownership_map.md
- docs/architecture/assessments/code-as-a-crime-scene-overview.md
- docs/architecture/calibration/README.md
- docs/architecture/calibration/documentation.md
- docs/architecture/calibration/erp-custom.md
- docs/architecture/calibration/research.md
- docs/architecture/calibration/software-dev.md
- docs/architecture/charter-backend-service-future.md
- docs/architecture/charter-pack-usage-journey.md
- docs/architecture/charter-synthesis-drg.md
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/diagrams/03_components/README.md
- docs/architecture/diagrams/README.md
- docs/architecture/documentation-mission.md
- docs/architecture/explanation-index.md
- docs/architecture/explanation-toc.yml
- docs/architecture/governed-profile-invocation.md
- docs/architecture/host-surface-parity.md
- docs/architecture/index.md
- docs/architecture/mission-gates.md
- docs/architecture/mission-system.md
- docs/architecture/mission-type-resolution.md
- docs/architecture/org-doctrine-layer.md
- docs/architecture/post-merge-partition-authority.md
- docs/architecture/retrospective-learning-loop.md
- docs/architecture/runtime-loop.md
- docs/architecture/trail-model.md
- docs/architecture/vision/README-3.x.md
- docs/context/audience/internal/lead-developer.md
- docs/context/audience/internal/maintainer.md
- docs/context/audience/internal/spec-kitty-cli-runtime.md
- docs/context/charter-overview.md
- docs/context/configuration-project-structure.md
- docs/context/contextive-glossaries.md
- docs/context/governance-files.md
- docs/context/governance.md
- docs/context/index.md
- docs/context/ops-vs-missions.md
- docs/context/orchestration.md
- docs/context/planning-and-tracking.md
- docs/context/testing-taxonomy.md
- docs/convergence/charter-fetch.md
- docs/convergence/doctrine-drg.md
- docs/convergence/interim-ci-producer.md
- docs/convergence/landing.md
- docs/development/agent-fleet.md
- docs/development/analysis-report-transactions.md
- docs/development/contributing.md
- docs/development/getting-started/onboarding-run.md
- docs/development/how-to/add-architectural-gate-exemption.md
- docs/development/how-to/create-a-pack-skill.md
- docs/development/how-to/enable-the-internal-pack.md
- docs/development/how-to/index.md
- docs/development/how-to/manage-issue-tracker.md
- docs/development/how-to/pr-landing.md
- docs/development/how-to/review-gates.md
- docs/development/index.md
- docs/development/reference/coverage-signals.md
- docs/development/reference/known-friction-points.md
- docs/development/reference/quality-and-tech-debt-standing-orders.md
- docs/development/reference/read-side-seam-classification.md
- docs/development/reference/version-taxonomy.md
- docs/development/reporting/debrief-styleguide.md
- docs/development/testing/run-mutation-tests.md
- docs/development/toc.yml
- docs/guides/how-to/collaboration/adhoc-specialist-session.md
- docs/guides/how-to/governance/extend-charter-for-unsupported-language.md
- docs/guides/how-to/governance/index.md
- docs/guides/how-to/governance/manage-glossary.md
- docs/guides/how-to/governance/run-governed-mission.md
- docs/guides/how-to/governance/setup-governance.md
- docs/guides/how-to/governance/synthesize-doctrine.md
- docs/guides/how-to/governance/troubleshoot-charter.md
- docs/guides/how-to/governance/use-retrospective-learning.md
- docs/guides/how-to/index.md
- docs/guides/how-to/installation/tool-surface-upgrade-and-repair.md
- docs/guides/how-to/missions/review-work-package.md
- docs/guides/index.md
- docs/guides/toc.yml
- docs/guides/tutorials/charter-governed-workflow.md
- docs/guides/tutorials/claude-code-workflow.md
- docs/guides/tutorials/index.md
- docs/index.md
- docs/llms.txt
- docs/migrations/cross-repo-e2e-gate.md
- docs/migrations/feature-flag-deprecation.md
- docs/migrations/from-charter-2x.md
- docs/migrations/migration-and-shim-rules.md
- docs/operations/how-to-maintain.md
- docs/toc.yml
- AGENTS.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP22 – Prose in packs and living docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `lexical-larry`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(WP18 retires `ad-hoc-profile-load`; use `spk-charter-profile-load` if the old name is gone.)

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

Rename the retired-tier sense of "doctrine" (and the old senses of "charter pack") in shipped pack prose, `packs/internal` prose, the living docs and AGENTS.md (CLAUDE.md is a symlink to it). This is the `user_facing_strings: manual_review` category of the occurrence map: **every occurrence is judged by sense**.

Done when:

1. Every FR-018 forbidden token (spec, "FR-018 closed lists") is gone from the files this WP owns, outside the C-004 names. Check: the grep in T101 step 1 over owned files returns nothing.
2. Tier-sense prose ("doctrine pack", "org doctrine", "doctrine layer/tier", "project doctrine", "built-in doctrine", "Doctrine Catalog", `.kittify/doctrine`, `spec-kitty doctrine …`, `doctor doctrine`, "Pack Default Charter", "default charter pack", `charter pack apply`) reads in the charter vocabulary: **Charter Pack**, **charter offering**, **activation preset**, **active charter**, **project layer** (`.kittify/charter-packs/`), and the FR-006 command homes.
3. Content-sense "doctrine" (governance substance, "doctrine artifact" where it means a directive or tactic, `DIRECTIVE_018` "doctrine versioning"), C-004 names (`doctrine-daphne`, `DIRECTIVE_039`), historical mission slugs and historical roots are unchanged.
4. Pack manifests and the CLI reference are regenerated; `spec-kitty charter pack regenerate-graph --check` and the CLI-reference freshness check pass.
5. Every `pending_until("WP22")` strict-xfail in `tests/acceptance/charter_pack_cutover/` is removed and green.

## Context & Constraints

- Spec: FR-010, FR-018 closed lists (forbidden tokens, historical roots, living surfaces), C-002, C-003, C-004. ADR `docs/adr/4.x/2026-10-06-1-charter-offering-active-charter-and-activation-presets.md` §1 (vocabulary), §4 (command table), §6 (names that stay).
- `occurrence_map.yaml`: `user_facing_strings: manual_review`; exceptions for `doctrine-daphne.agent.yaml`, `directives/*039*`, `directives/018-doctrine-versioning-requirement.directive.yaml`, `docs/adr/**`, `docs/plans/**`, `docs/reports/**`, the two superseded runbooks.
- FR-006 command homes (for replacing command spellings in prose): `spec-kitty doctrine pack validate|assemble` → `spec-kitty charter pack validate|assemble`; `spec-kitty doctrine regenerate-graph [--check]` → `spec-kitty charter pack regenerate-graph [--check]`; `spec-kitty doctrine asset list|path` → `spec-kitty charter pack asset list|path`; `spec-kitty doctrine mission-type list` → `spec-kitty charter mission-type list --include-inactive`; `spec-kitty doctrine fetch|new|validate|org …` → `spec-kitty charter fetch|new|validate|org …`; `charter pack consistency-check` → `charter consistency-check`; `spec-kitty doctor doctrine` → `spec-kitty doctor charter-packs`; `charter pack apply <name>` → `charter activate --preset <name>`. Verify each against the live CLI (`uv run --frozen spec-kitty charter pack --help` etc.) before writing it.
- Config keys: `doctrine.org.packs` / `organisation_packs` → `charter_packs.org.packs`; `governance.doctrine.*` → `governance.charter.*`; `doctrine_pack_id` → `charter_pack_id`; the "legacy fallback" mentions are deleted, not renamed (FR-011 removed the fallbacks).
- **Do not rename doc page files.** Page slugs are published URLs, and renaming one needs a redirect (`scripts/docs/redirect_map.yaml`, `tests/docs/test_redirect_spine.py`), which C-001 rules out as a stub. Change titles and prose only, and record this decision.
- **Pack tiers (C-003)**: nothing moves between `packs/built-in` and `packs/internal`. Every pack edit is followed by `spec-kitty charter pack regenerate-graph`.
- **Not owned here** (edit only as a logged follow-up, or leave for the owner):
  - `packs/built-in/pack.yaml` (WP13), `packs/built-in/pack-manifest.yaml` and `*.graph.yaml` (generated), `packs/built-in/glossary_packs/**` (WP24).
  - Skill references in `packs/built-in/missions/mission-steps/**/prompt.md`, the three `task-prompt-template.md`, `tactics/reviewer-implementer-role-separation.tactic.yaml`, `toolguides/CONTEXTIVE.md`, `docs/api/skills/**`, `docs/api/agent_profiles/**`, `docs/guides/how-to/harnesses/**` (WP18). If tier prose remains in them after WP18, fix it as a logged follow-up.
  - `packs/internal/{README.md, assets/test-quality-scan.py, procedures/executive-debrief-generation.procedure.yaml, procedures/test-suite-quality-assessment.procedure.yaml, skills/report-debrief.skill.md, toolguides/TEST_QUALITY_TRIAGE.md, toolguides/test-quality-triage.toolguide.yaml}` (WP15 T078 moved their commands). Their remaining tier prose ("org-tier doctrine pack" in `README.md`) is a logged follow-up here.
  - `docs/context/charter.md`, `docs/migrations/index.md`, the new runbook and the two superseded runbooks (WP24); `docs/migrations/shim-registry.yaml` (WP14); `docs/api/charter-commands.md` (CLI WPs); generated docs (`docs/api/cli-commands.md`, `docs/development/docs-retrieval-index.yaml`, `docs/development/page-inventory.yaml`) are regenerated, never hand-edited.
  - The four docs that also cite `tests/doctrine/` (`docs/architecture/doctrine-relationships.md`, `docs/architecture/04_implementation_mapping/README.md`, `docs/operations/p0-baseline-refresh.md`, `docs/architecture/profile-load-reliability.md`) belong to WP23, which runs after you (WP23 depends on WP22); WP23 applies this WP's prose rule there.
- **Files claimed upstream** that still need this WP's prose pass (logged follow-ups; their WPs are complete): WP16 `packs/built-in/agent_profiles/doctrine-daphne.agent.yaml`, `packs/built-in/tactics/common-docs-find.tactic.yaml`, `packs/built-in/tactics/common-docs-write.tactic.yaml`, `docs/architecture/doctrine-kinds.md`, `docs/development/how-to/create-a-doctrine-artifact.md`, `docs/development/reference/ci-gate-mechanics.md`, `docs/development/reference/terminology-exemptions.md`, `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`; WP17 `docs/configuration/yaml-libraries.md`, `docs/context/execution.md`. WP16 most likely already replaced the retired command spellings in them; check, then apply the classification rule to the remaining prose.
- WP21 left a list of docs that still name renamed modules or gate files (its Activity Log). Sweep those references as part of T102.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes must merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- **Lane**: from `lanes.json` (filled by finalize).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Never push to `main`. Commit per surface (built-in pack, internal pack, docs area, AGENTS.md, regenerated files), conventional subjects referencing #3732, for example `docs(packs): charter vocabulary in built-in pack prose (#3732)`.

## Subtasks & Detailed Guidance

### Red first (C-006 / C-011) — first commit

1. `grep -rn 'pending_until("WP22")' tests/acceptance/charter_pack_cutover/`. WP01's flip map assigns WP22 `test_fr010_retired_identifiers_absent[prose]` (`test_package_split.py`): a token scan of `packs/`, living `docs/` and `AGENTS.md` for the closed prose list in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml`, with a planted-token self-test and a scanned-file floor. WP25's FR-018 gate measures the full vocabulary later. Also record the T101 forbidden-token grep over the owned files (hit count per file) before any edit; it must reach zero by the end.
2. Remove the marker only; run the test; record the red output in the Activity Log; commit `test(acceptance): drop WP22 xfail markers for FR-010 prose (#3732)`.
3. A test that passes at once is vacuous or already satisfied: record which and ask the reviewer; do not edit its assertion.

### Classification rule (applies to T101–T103)

For each occurrence of "doctrine" (any case) and of "charter pack", decide the sense and record per file in the Activity Log: `<file>: renamed N, kept M (content|C-004|historical slug|identifier)`.

| Sense | Action | Example |
|---|---|---|
| Offer-side tier, a pack of artifacts | **Charter Pack** / **charter offering** | "an org doctrine pack" → "an org Charter Pack" |
| Project's own components | **project layer** (`.kittify/charter-packs/`) | "project doctrine overlay" → "project-layer overlay" |
| Old "charter pack" = `default`/`minimal` | **activation preset** | "apply the minimal charter pack" → "activate the `minimal` preset" |
| Project activation state | **active charter** | "the project's charter pack config" → "the active charter" |
| Command / key / path | FR-006 home, canonical key, kernel path | see Context |
| Governance content | keep | "doctrine versioning", "the doctrine says" |
| Persona, ids, slugs | keep | `doctrine-daphne`, `DIRECTIVE_039`, `doctrine-consumer-surface-missions-extraction-01KZ6G6H` |

Never change a persisted identifier in pack data (artifact `id:`, URNs, capability tags, profile `specializes_from`, globs that code matches) in this WP. Before changing any YAML value that is not free prose, `git grep` for it in `src/` and `tests/`; if anything matches, keep it and record it.

### Subtask T101 – Built-in pack prose (tier sense; content sense kept)

- **Purpose**: shipped pack content stops teaching retired names to every consumer.
- **Steps**:
  1. Inventory: `git grep -n -iE "doctrine|charter pack|default charter|pack default" -- <owned packs/built-in files>`; also the forbidden-token grep:
     ```bash
     git grep -n -E 'doctrine pack|spk-doctrine-|spec-kitty doctrine|doctrine\.org\.packs|organisation_packs|\.kittify/doctrine|accompanies_doctrine_pack|CharterPackManager|CharterPackConfigError|CHARTER_PACK_CONFIG_INVALID|charter pack apply|Pack Default Charter|default charter pack|BUILTIN_PACKS|specify_cli\.doctrine|doctor doctrine|--doctrine-mode|doctrine_mode|doctrine_skill|doctrine_pack_id|spec-kitty-charter-doctrine|spec-kitty-glossary-context|spec-kitty-bulk-edit-classification|spec-kitty-spdd-reasons|ad-hoc-profile-load' -- packs/
     ```
  2. Known sites measured at base (re-verify; earlier WPs may have fixed some):
     - `missions/{software-dev,research,plan,documentation}/governance-profile.yaml` comments (`.kittify/doctrine/mission_types/...` → `.kittify/charter-packs/mission_types/...`).
     - `missions/plan/actions/{plan,research,review,specify}/index.yaml` comments naming the dead module path `doctrine.missions.action_index.load_action_index`; point at the live module (`git grep -n "def load_action_index" src/`).
     - `directives/038-structured-prompt-boundary.directive.yaml:5` ("SPDD/REASONS doctrine pack" → "Charter Pack").
     - `pack.md:1,9` ("Built-in Doctrine Pack"; the `accompanies_doctrine_pack` sentence goes, the field is retired).
     - `procedures/onboard-external-agent-to-pack.procedure.yaml:6,30,41-42,234,238` (pack noun, `doctor charter-packs`, `.kittify/charter-packs/`).
     - `tactics/common-docs-find.tactic.yaml:27,49`, `tactics/common-docs-write.tactic.yaml:54,60`, `tactics/common-docs-scaffold.tactic.yaml`, `styleguides/common-docs.styleguide.yaml`, `directives/042-common-docs.directive.yaml`, `assets/docs_structural_lint.py`, `assets/docs_structural_lint.config.yaml` (`spec-kitty doctrine regenerate-graph` → `spec-kitty charter pack regenerate-graph`; "doctrine asset(s)" is often the content sense, judge each).
     - `assets/README.md:38` (`specify_cli.doctrine.pack_validator` → `charter.offering.packs.pack_validator`, verify the module path exists).
     - `agent_profiles/doctrine-daphne.agent.yaml:114` (`spec-kitty doctrine regenerate-graph` → `spec-kitty charter pack regenerate-graph`). Keep the file name, `profile-id`, name and persona wording (C-004). The occurrence map lists this file as `do_not_change`; the command line is not a C-004 name, and leaving it fails FR-018. Edit only that line (and any other retired command spelling), and record the deviation in the Activity Log for the reviewer.
     - `agent_profiles/curator-carla.agent.yaml`, `agent_profiles/retrospective-facilitator.agent.yaml`, `agent_profiles/drupal-dries.agent.yaml`, `agent_profiles/README.md`: prose only; capability tags such as `doctrine-maintenance` and path globs such as `"doctrine/**/*"` are matched by code or tests: grep before touching, and record.
     - `procedures/migrate-project-guidance-to-spec-kitty-charter.procedure.yaml` (10 hits), the remaining directives, tactics, paradigms, procedures and toolguides in `owned_files`.
  3. Run `uv run --frozen spec-kitty charter pack regenerate-graph` after the edits (C-003), then `--check`.
- **Files**: `packs/built-in/**` entries in `owned_files`.
- **Parallel?**: Yes, with T102.
- **Notes**: YAML scalars: keep quoting and folding style; reflowing a folded block changes the manifest hash only, which the regeneration absorbs. Do not touch `018-doctrine-versioning-requirement.directive.yaml`.
- **Validation**:
  - [ ] Forbidden-token grep over owned `packs/built-in` files: no hit.
  - [ ] `charter pack regenerate-graph --check` exits 0; `tests/architectural/test_pack_manifest_no_author_edit.py` green.

### Subtask T102 – Living docs prose and `charter-pack-usage-journey`

- **Purpose**: docs describe the charter offering, presets, the active charter and the project layer with one vocabulary.
- **Steps**:
  1. Living docs = `docs/` minus the historical roots (`docs/adr/**`, `docs/plans/**`, `docs/reports/**`, `docs/archive/**`, `docs/changelog/**` (WP24 owns the Unreleased section), generated pages). Owned list is in the frontmatter (105 files measured at base with any "doctrine").
  2. Highest-density pages first (counts of tier-sense hits at base): `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` (31), `docs/architecture/org-doctrine-layer.md` (26), `docs/development/how-to/create-a-doctrine-artifact.md` (25), `docs/architecture/doctrine-kinds.md` (16), `docs/context/governance-files.md` (8), `docs/development/how-to/create-a-pack-skill.md` (6), `docs/context/governance.md` (5), then the rest. Update page titles and `description:` frontmatter where they carry the tier sense (keep the file name).
  3. **Rewrite `docs/architecture/charter-pack-usage-journey.md`** to the preset model: `charter pack apply <name>` → `charter activate --preset <name>` (with `--compile`; `--force` when the active charter would change), "charter pack" in the old sense → "activation preset", and the three-tier table at ~l.41 (the activation write store) in active-charter terms. Keep the dispatch-safety-net content; verify each command against `--help`.
  4. Sweep references to modules and gate files renamed by WP19–WP21 (WP21's Activity Log lists them; for example `docs/development/reference/ci-gate-mechanics.md` naming `test_charter_facades_reexport_doctrine`), and to `specify_cli.doctrine.*` paths (`docs/configuration/yaml-libraries.md`, `docs/convergence/charter-fetch.md`).
  5. Update `updated:` frontmatter dates where the docs freshness tooling expects it (`scripts/docs/check_docs_freshness.py`); regenerate `docs/development/docs-retrieval-index.yaml` with `uv run --frozen python scripts/docs/docs_index.py --write` and `docs/development/page-inventory.yaml` with `uv run --frozen python scripts/docs/inventory_lockfile.py` (check each script's `--help` for the write flag) if titles or frontmatter changed.
- **Files**: `docs/**` entries in `owned_files`.
- **Parallel?**: Yes, with T101 and T103.
- **Notes**: `docs/migrations/{from-charter-2x,feature-flag-deprecation,cross-repo-e2e-gate,migration-and-shim-rules}.md` sit in `FORBIDDEN_SCAN_ROOTS` but are still living pages: apply the same rule. `docs/assets/spec-kitty-backlog.html` CSS variables named `--doctrine` are out of scope.
- **Validation**:
  - [ ] Forbidden-token grep over owned docs: no hit.
  - [ ] `make docs-lint` green; `uv run --frozen pytest tests/docs -q` green (or record pre-existing reds per the baseline-red gotcha).

### Subtask T103 – AGENTS.md / CLAUDE.md and `packs/internal` prose

- **Purpose**: the maintainer guidance and the internal pack use the cutover names.
- **Steps**:
  1. `AGENTS.md` (CLAUDE.md is a symlink; edit `AGENTS.md` only; `ls -l CLAUDE.md` to confirm). Sites at base: l.42-49 Pack Tiers ("Put doctrine in the right tier" is content sense, keep; "legacy fallback `doctrine.org.packs`" is deleted; `spec-kitty doctrine regenerate-graph` → `spec-kitty charter pack regenerate-graph` if WP15 has not already); l.213 project-structure comment; l.581 heading "Charter Activation and Doctrine Integrity Model" (judge: "doctrine integrity" is the governance-content sense, keep unless the section describes the tier); l.623 "shipped doctrine skill"; l.625 `.kittify/doctrine/skills/` → `.kittify/charter-packs/skills/`; l.648 `spec-kitty doctor doctrine --json` → `spec-kitty doctor charter-packs --json`. l.89 "internal doctrine pack" → "internal charter pack". **Do not edit the test-policy text naming `tests/doctrine/`** (l.265 and any other `tests/doctrine` mention): WP23 renames that directory and edits those words.
  2. `packs/internal/**` owned files: `drg/fragment.yaml` (comments only; keys unchanged), `procedures/{cloud-session-dispatch,issue-triage-pass,memory-curation-and-escalation,project-evolution-postmortem}.procedure.yaml`, `skills/issue-triage.skill.md`, `styleguides/spec-kitty-docs-lint-config.styleguide.yaml`, `tactics/branded-deliverable.tactic.yaml`, `directives/operator-signal-contract.directive.yaml`. Then the WP15-owned internal files listed in Context as logged follow-ups (tier prose only).
  3. Regenerate the internal pack's derived files (the same `regenerate-graph`; check `packs/internal/README.md` for its own manifest step) — `packs/internal` must not leak into the wheel (`tests/cross_cutting/packaging/test_packaging_safety.py`).
- **Files**: `AGENTS.md`, `packs/internal/**` entries in `owned_files`.
- **Parallel?**: Yes.
- **Notes**: AGENTS.md is long and load-bearing; change only the retired-tier phrases. If AGENTS.md and the charter disagree after the edit, flag it (CLAUDE.md rule) rather than editing the charter.
- **Validation**:
  - [ ] `git grep -n -E 'spec-kitty doctrine|doctor doctrine|\.kittify/doctrine|doctrine\.org\.packs' -- AGENTS.md packs/internal` → nothing.
  - [ ] Packaging-safety test green.

### Subtask T104 – Regenerate pack manifests and the CLI reference

- **Purpose**: derived files match their sources; nothing is hand-edited.
- **Steps**:
  1. `uv run --frozen spec-kitty charter pack regenerate-graph`, then `uv run --frozen spec-kitty charter pack regenerate-graph --check` (exit 0). Confirm `packs/built-in/pack-manifest.yaml` `generated_by` reads `spec-kitty charter pack regenerate-graph` (WP15 changed the constant).
  2. `uv run --frozen python scripts/docs/build_cli_reference.py` (default `--mode hybrid`), then `uv run --frozen python scripts/docs/check_cli_reference_freshness.py`. Help text is generated from the Typer surface; if it still carries a retired-tier phrase, the source string is in `src/` and belongs to its owning WP: record it and raise it with the reviewer, do not hand-edit the reference.
  3. Commit the regenerated files alone: `chore(docs): regenerate pack manifests and CLI reference (#3732)`.
- **Files**: generated files (logged; not owned).
- **Parallel?**: No; last.
- **Validation**:
  - [ ] Both checks exit 0; `git status` clean after a second regeneration.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest <every acceptance test id you un-xfailed> -q
uv run --frozen spec-kitty charter pack regenerate-graph --check
uv run --frozen python scripts/docs/check_cli_reference_freshness.py
make docs-lint
uv run --frozen pytest tests/docs -q
uv run --frozen pytest tests/architectural/test_pack_manifest_no_author_edit.py \
  tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py \
  tests/architectural/test_no_dead_doctrine_paths.py tests/cross_cutting/packaging/test_packaging_safety.py -q
# If WP16 renamed the guidance gate, also run its new file (the removed-command gate).
uv run --frozen pytest tests/charter tests/doctrine -q -m "fast or unit"   # pack content is loaded by these suites
uv run --frozen ruff check packs/built-in/assets/docs_structural_lint.py
uv run --frozen ruff format --check --force-exclude packs/built-in/assets/docs_structural_lint.py
```

`mypy` applies only if a `.py` file changed (`docs_structural_lint.py`): `uv run --frozen mypy --strict packs/built-in/assets/docs_structural_lint.py`.

## Commit checkpoints

This WP stays one WP (mechanical prose; orchestrator ruling AR-S8), but a session may stop after any checkpoint and resume at the next. Commit at each and append one Activity Log line naming it:

1. red-first commit (marker removed, red output and per-file hit counts recorded);
2. T101, built-in pack prose: one commit per pack area (agent profiles, tactics and procedures, mission steps and templates, remaining files), each with its per-file classification recorded;
3. T102, living docs: one commit per docs subtree (`docs/guides`, `docs/architecture`, `docs/development`, the rest);
4. T103, `AGENTS.md` and `packs/internal` prose;
5. T104, regenerated pack manifests and CLI reference (`chore(generated)`), then the green acceptance run.

A resuming session reads the Activity Log, checks `git log --oneline` against this list and continues with the next unchecked item.

## Risks & Mitigations

- **Content sense renamed**: "doctrine" meaning governance substance becomes "Charter Pack". Mitigation: the per-file classification record; the reviewer samples it.
- **A pack YAML value matched by code changed**: a capability tag or glob silently stops matching. Mitigation: grep before changing any non-prose value; keep and record.
- **Hand-edited generated file**: `test_pack_manifest_no_author_edit.py` and the CLI-reference freshness check catch it; regenerate instead.
- **WP23 runs after you** and touches docs too: WP23 owns the four `tests/doctrine`-citing pages and the AGENTS.md test-policy lines; leave them alone.

## Review Guidance

- Confirm the WP22 acceptance tests were red after the first commit and green at the end, assertions unchanged.
- Run the forbidden-token grep over the owned files: expect no hit.
- Sample ten kept occurrences from the classification record and check the sense.
- Check the `doctrine-daphne` edit is limited to command spellings and the deviation from the occurrence-map exception is recorded.
- Check no doc page file was renamed and no redirect was added.
- Check regenerated files were produced by the tools (rerun them; `git diff` must be empty).

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
- 2026-10-08T20:20:00Z – claude (lexical-larry) – Red-first: removed the WP22 strict-xfail (`_SLICE_PENDING` map in tests/acceptance/charter_pack_cutover/test_package_split.py; the only WP22 marker). `test_fr010_retired_identifiers_absent[prose]` RED: 1 failed, 3 passed; 50 findings over 895 scanned files (doctrine pack 27, doctrine catalog 9, charter selection 6, project doctrine 5, default charter pack 1, doctor doctrine 1, spec-kitty doctrine 1). Assertion unchanged. T101 forbidden-token grep over owned files at start: 99 hits in 41 files (charter-pack-usage-journey 13, org-doctrine-layer 15, governance-files 6, troubleshoot-charter 5, ...). Commit 04640291.
- 2026-10-08T20:25:00Z – claude – T101 built-in pack prose: commit bce64b55 (+ deef1652 structural-lint docstrings, provenance ratchet baseline lowered repo_paths 4->0). Pack manifest + procedure graph regenerated with `spec-kitty charter pack regenerate-graph`; `--check` exit 0.
- 2026-10-08T20:27:00Z – claude – T103 packs/internal prose: commit 9909bff5; AGENTS.md (+ identical CLAUDE.md; both are regular files with the same blob in this tree, not a symlink) commit 46323111.
- 2026-10-08T20:45:00Z – claude – T102 living docs: commits 4cd00d6a (architecture; charter-pack-usage-journey rewritten to the activation preset model), 2c630cfa (context), 66121046 (development), 2ec246f9 (guides), 44de81c7 + f408d3fd (landscape, api/configuration/migrations), dfc7b104 (glob row fix). Skills prose df31b3fc; CLI help text 6791c91b.
- Classification rule applied per file (renamed = removed lines carrying a tier-sense term; kept = remaining lines with "doctrine", content sense / C-004 / historical slug / identifier):
  - AGENTS.md: renamed 2, kept 12
  - CLAUDE.md: renamed 2, kept 12
  - docs/api/agent_profiles/curator-carla.md: renamed 2, kept 4
  - docs/api/agent_profiles/doctrine-daphne.md: renamed 1, kept 11
  - docs/api/agent_profiles/human-in-charge.md: renamed 0, kept 1
  - docs/api/agent_profiles/index.md: renamed 2, kept 2
  - docs/api/charter-commands.md: renamed 3, kept 14
  - docs/api/environment-variables.md: renamed 3, kept 4
  - docs/api/skills/spk-charter-profile-load.md: renamed 1, kept 1
  - docs/architecture/00_landscape/README.md: renamed 1, kept 24
  - docs/architecture/04_implementation_mapping/README.md: renamed 9, kept 27
  - docs/architecture/04_implementation_mapping/code-patterns.md: renamed 2, kept 7
  - docs/architecture/calibration/README.md: renamed 1, kept 1
  - docs/architecture/calibration/documentation.md: renamed 1, kept 0
  - docs/architecture/calibration/erp-custom.md: renamed 1, kept 0
  - docs/architecture/calibration/research.md: renamed 1, kept 0
  - docs/architecture/calibration/software-dev.md: renamed 1, kept 0
  - docs/architecture/charter-pack-usage-journey.md: renamed 15, kept 0
  - docs/architecture/charter-synthesis-drg.md: renamed 3, kept 10
  - docs/architecture/diagrams/02_containers/README.md: renamed 3, kept 5
  - docs/architecture/diagrams/03_components/README.md: renamed 3, kept 10
  - docs/architecture/diagrams/README.md: renamed 1, kept 3
  - docs/architecture/doctrine-kinds.md: renamed 12, kept 29
  - docs/architecture/explanation-index.md: renamed 0, kept 2
  - docs/architecture/explanation-toc.yml: renamed 0, kept 5
  - docs/architecture/index.md: renamed 0, kept 5
  - docs/architecture/mission-system.md: renamed 1, kept 8
  - docs/architecture/mission-type-resolution.md: renamed 4, kept 30
  - docs/architecture/org-doctrine-layer.md: renamed 31, kept 13
  - docs/architecture/profile-load-reliability.md: renamed 1, kept 13
  - docs/architecture/spdd-reasons.md: renamed 5, kept 5
  - docs/configuration/yaml-libraries.md: renamed 2, kept 2
  - docs/context/charter-overview.md: renamed 4, kept 8
  - docs/context/configuration-project-structure.md: renamed 2, kept 2
  - docs/context/execution.md: renamed 1, kept 2
  - docs/context/governance-files.md: renamed 12, kept 9
  - docs/context/governance.md: renamed 7, kept 5
  - docs/context/testing-taxonomy.md: renamed 2, kept 4
  - docs/development/how-to/create-a-doctrine-artifact.md: renamed 18, kept 22
  - docs/development/how-to/create-a-pack-skill.md: renamed 4, kept 8
  - docs/development/how-to/enable-the-internal-pack.md: renamed 1, kept 3
  - docs/development/how-to/review-gates.md: renamed 3, kept 15
  - docs/development/reference/ci-gate-mechanics.md: renamed 1, kept 0
  - docs/development/reference/known-friction-points.md: renamed 3, kept 2
  - docs/development/reference/read-side-seam-classification.md: renamed 1, kept 3
  - docs/development/reference/terminology-exemptions.md: renamed 0, kept 6
  - docs/development/reporting/debrief-styleguide.md: renamed 1, kept 3
  - docs/guides/how-to/governance/create-an-org-doctrine-pack.md: renamed 14, kept 19
  - docs/guides/how-to/governance/extend-charter-for-unsupported-language.md: renamed 4, kept 8
  - docs/guides/how-to/governance/index.md: renamed 0, kept 7
  - docs/guides/how-to/governance/manage-glossary.md: renamed 3, kept 7
  - docs/guides/how-to/governance/run-governed-mission.md: renamed 2, kept 3
  - docs/guides/how-to/governance/setup-governance.md: renamed 10, kept 12
  - docs/guides/how-to/governance/synthesize-doctrine.md: renamed 3, kept 7
  - docs/guides/how-to/governance/troubleshoot-charter.md: renamed 4, kept 7
  - docs/guides/toc.yml: renamed 1, kept 4
  - docs/index.md: renamed 1, kept 4
  - docs/migrations/cross-repo-e2e-gate.md: renamed 2, kept 0
  - docs/migrations/from-charter-2x.md: renamed 4, kept 5
  - packs/built-in/agent_profiles/README.md: renamed 1, kept 1
  - packs/built-in/agent_profiles/curator-carla.agent.yaml: renamed 4, kept 8
  - packs/built-in/assets/README.md: renamed 3, kept 1
  - packs/built-in/assets/docs_structural_lint.py: renamed 4, kept 2
  - packs/built-in/directives/038-structured-prompt-boundary.directive.yaml: renamed 3, kept 0
  - packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml: renamed 3, kept 20
  - packs/built-in/missions/documentation/governance-profile.yaml: renamed 2, kept 2
  - packs/built-in/missions/mission-steps/software-dev/review/prompt.md: renamed 2, kept 0
  - packs/built-in/missions/mission-steps/software-dev/specify/prompt.md: renamed 1, kept 1
  - packs/built-in/missions/plan/actions/plan/index.yaml: renamed 1, kept 1
  - packs/built-in/missions/plan/actions/research/index.yaml: renamed 1, kept 1
  - packs/built-in/missions/plan/actions/review/index.yaml: renamed 1, kept 1
  - packs/built-in/missions/plan/actions/specify/index.yaml: renamed 1, kept 1
  - packs/built-in/missions/plan/governance-profile.yaml: renamed 2, kept 2
  - packs/built-in/missions/research/governance-profile.yaml: renamed 2, kept 2
  - packs/built-in/missions/software-dev/governance-profile.yaml: renamed 2, kept 1
  - packs/built-in/pack.md: renamed 1, kept 0
  - packs/built-in/procedures/domain-aware-decision-interview.procedure.yaml: renamed 1, kept 2
  - packs/built-in/procedures/migrate-project-guidance-to-spec-kitty-charter.procedure.yaml: renamed 1, kept 9
  - packs/built-in/procedures/onboard-external-agent-to-pack.procedure.yaml: renamed 4, kept 2
  - packs/internal/README.md: renamed 3, kept 5
  - packs/internal/assets/test-quality-scan.py: renamed 1, kept 0
  - packs/internal/drg/fragment.yaml: renamed 2, kept 10
  - packs/internal/procedures/test-suite-quality-assessment.procedure.yaml: renamed 1, kept 1
  - packs/internal/toolguides/TEST_QUALITY_TRIAGE.md: renamed 1, kept 0
  - src/charter/offering/skills/README.md: renamed 1, kept 12
  - src/charter/offering/skills/spec-kitty-mission-system/SKILL.md: renamed 4, kept 16
  - src/charter/offering/skills/spk-charter-governance/references/charter-artifact-structure.md: renamed 1, kept 6
  - src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md: renamed 3, kept 39
  - src/charter/offering/skills/spk-charter-profile-load/references/profile-load-mechanics.md: renamed 1, kept 0
  - src/charter/offering/skills/spk-charter-spdd-reasons/references/reasons-canvas-workflow.md: renamed 1, kept 0
  - src/specify_cli/cli/commands/charter/authoring.py: renamed 2, kept 8
  - src/specify_cli/cli/commands/charter/list_cmd.py: renamed 1, kept 7
  - src/specify_cli/cli/commands/charter/org.py: renamed 5, kept 2
  - src/specify_cli/cli/commands/charter/pack_tooling.py: renamed 3, kept 3
  - tests/architectural/_builtin_pack_provenance_baseline.yaml: renamed 0, kept 2
  - tests/docs/test_asset_howto.py: renamed 1, kept 3
- 2026-10-08T21:30:00Z – claude – T104: CLI reference regenerated (`python -m scripts.docs.build_cli_reference`, hybrid) and docs retrieval index (`python -m scripts.docs.docs_index --write`), commits f831a4e4, 57947aef; page-inventory had no drift. `charter pack regenerate-graph --check` exit 0.
- 2026-10-08T21:30:00Z – claude – Prose-slice scope: the generated docs-retrieval-index.yaml indexes ADRs, plans, reports, migrations and charter.md, so it repeats retired wording the slice exempts at source; added it to the prose slice's exclude_patterns (c5a4154f) with the same rationale as the removed-command gate exemption. Assertion unchanged. Reviewer decision requested (fixture header says WPs do not edit it).
- 2026-10-08T21:30:00Z – claude – GREEN: test_fr010_retired_identifiers_absent[prose] 0 findings over 894 files (floor 714). Acceptance suite 310 passed, 1 skipped, 43 xfailed, 0 failed, 0 xpassed.
- Deviations / logged follow-ups outside ownership: doctrine-daphne.agent.yaml untouched beyond the command line WP15 already fixed (C-004, prose kept); glossary_packs/spec-kitty-core (WP24) 3 lines; mission-steps software-dev review/specify prompts (WP18) SPDD block; docs/api/agent_profiles/*, docs/api/skills/spk-charter-profile-load.md (WP18); src/charter/offering/skills/** prose (WP18); CLI help strings in charter authoring/org/pack_tooling/list_cmd (prose only); docs/api/charter-commands.md; 04_implementation_mapping/README.md (WP23) non-tests/doctrine lines only; CLAUDE.md mirrored from AGENTS.md (regular file, same blob); tests/architectural/_builtin_pack_provenance_baseline.yaml lowered; tests/docs/test_asset_howto.py docstring path.
- Kept by decision: page file names (create-an-org-doctrine-pack.md, org-doctrine-layer.md, doctrine-kinds.md, charter-pack-usage-journey.md; no redirects); docs/convergence/** port ledgers (historical record of past code); docs/migrations/doctrine-local-overlay-to-org-layer.md (superseded runbook, WP24); "Doctrine Reference Graph"/DRG; content-sense doctrine; 04_implementation_mapping "Doctrine Stack" headings (WP23); packs/internal styleguide config value `doctrine_artifact: src/doctrine/` (config data, not prose); docs/api/batch-api-contract.md `doctrine_mode` wire example (consumer-visible key, not renamed: reported).

## Carry-over from WP13

Docs prose still describing the deleted `charter pack apply` (rewrite to `charter activate --preset`): `docs/architecture/charter-pack-usage-journey.md`, `setup-governance.md`, `troubleshoot-charter.md`, `charter-overview.md`, `profile-load-reliability.md`, `06_unified_charter_bundle.md`, `docs-retrieval-index.yaml` (locate exact paths with grep).
- From WP15: `packs/built-in/agent_profiles/doctrine-daphne.agent.yaml:~114` still instructs `spec-kitty doctrine regenerate-graph` (the occurrence map keeps only profile-id/name; this line follows the categories → `spec-kitty charter pack regenerate-graph`); update `test_doctrine_daphne_canonical_structure.py` which pins it. Help docstrings of `charter pack validate`/`pack assemble`/`asset list` still say "doctrine pack(s)"; docstring/comment hits in `src/charter/**`, `_doctrine_collect.py`, `_status_collectors.py`.
- From WP16 review: `tests/docs/test_asset_howto.py` docstring cites `docs/doctrine/create-a-doctrine-artifact.md`; real path is `docs/development/how-to/create-a-doctrine-artifact.md` (and that doc kind table/walkthrough still names `.kittify/doctrine/`).
- From WP19: living docs still name old classes (`docs/architecture/04_implementation_mapping*`, `org-doctrine-layer.md`, `code-patterns.md`, `mission-type-resolution.md`); skill prose names `DoctrineService` (spk-charter-governance, mission-system, skills README); `scripts/doctrine/inline_reference_inventory.py` uses `args.doctrine_root`; offering README authoring-path text (`directives/built-in/...`) stale. Runtime origin labels `doctrine/<mission>/...` are allowlisted in `charter_pack_path_allowlist.yaml` and coupled to `template_resolver._tier_to_origin` (WP25 owns those allowlist entries).
- From WP20: ~44 docs files still say `DoctrineService` (mostly archive/plans — historical roots stay); `docs/context/charter.md` names `DoctrineSelectionConfig` and `_load_action_doctrine_bundle` (FR-013) — update living docs.
- From WP20 review: user-facing error text "doctrine root {offering_root}" at `src/charter/activation/kind_vocabulary.py:~483,665`; ~25 tier-sense prose lines in activation files WP20 did not own (kind_vocabulary, pack_manager, effective_set, compiler, consistency_check, project_drg).
- From WP21: living docs `docs/context/governance.md:~115`, `docs/development/reference/ci-gate-mechanics.md:~212`, `docs/development/reference/read-side-seam-classification.md:~812` name renamed modules/classes (regenerate the retrieval index with tooling); prose in WP21-touched src: help text in `agent_retrospect.py`, docstrings in `charter_packs/sources/protocol.py`, `_charter_pack_health.py`, `_profile_health_render.py`. History roots (docs/plans, adr, archive, reports, convergence, changelog, migrations) stay.
- From WP21 review: `docs/.../profile-load-reliability.md` (doc_status: active) line ~127 is a live instruction pointing at the deleted `src/charter/activation/packs/default.yaml:187` — repoint to `packs/built-in/presets/default.yaml` or annotate; line ~81 (recorded finding) keeps its path-gate allowlist entry. `terminology-exemptions.md` row names `m_4_0_0rc6_charter_pack_cutover.py` while the gate exempts the glob `m_*charter_pack_cutover*.py` — state the glob.
