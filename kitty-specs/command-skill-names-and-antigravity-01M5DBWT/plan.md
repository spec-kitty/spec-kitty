# Implementation Plan: Spec-conformant command skill names + Antigravity skills delivery

**Branch**: `issue-6475-6470-command-skill-names` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/spec.md`

Branch contract: the current branch, the planning/base branch and the merge target are all
`issue-6475-6470-command-skill-names` (`branch_matches_target: true`), topology `single_branch`.
The finished branch is rebuilt fresh from `origin/main` for the PR.

## Summary

Rename the generated command skills from `spec-kitty.<cmd>` to `spec-kitty-<cmd>` behind one
naming authority, migrate installed projects with an ownership-proven rename, deliver the command
skills to Antigravity and retire its dead `.agent/workflows` surface (project and home folder),
scope the home-folder command writer to configured agents, and keep every generated or shipped
`SKILL.md` inside the Agent Skills specification, verified in CI by the reference validator.

## Engineering Alignment (operator rulings + planning answers)

Recorded decisions (decision `01M5DBXJ05DSF4322SXVPNPZZ1` plus two planning answers, 2026-10-20):

1. **Name** `spec-kitty-<cmd>`, produced by one authority (`skills/command_skill_names.py`, a
   dependency-free leaf like `_agent_roster.py`). Uniqueness is asserted at build time against the
   shipped charter skills (`src/charter/offering/skills/*`) and `RETIRED_CANONICAL_SKILL_NAMES`.
   Ownership and orphan detection are keyed on the manifest and the explicit command set, never a
   prefix (the new prefix `spec-kitty-` is shared with nine shipped charter skills).
2. **Clean break.** A migration renames installed skills (C-005). Slash-command files of the 13
   command agents keep their dotted names (C-001, #6471).
3. **Invocation prose (planning answer A).** Pack sources keep `/spec-kitty.<cmd>`, which is right
   for slash agents. The command-skill renderer rewrites known `/spec-kitty.<cmd>` and
   `$spec-kitty.<cmd>` tokens to the skill name in skill bodies, one rewrite authority. The
   open-packs PR fixes only text that names the skill itself.
4. **`builtin:` targets (planning answer B).** Pack-skill validation accepts
   `builtin:spec-kitty.<cmd>` as an input alias and `builtin:spec-kitty-<cmd>` as canonical;
   rendered text always names `spec-kitty-<cmd>`.
5. **Antigravity** joins the command-skill roster and leaves the slash-command registries
   (`AGENT_COMMAND_CONFIG`, `AGENT_DIRS`, `AGENT_DIR_TO_KEY`); its skill-root config row stays.
6. **Home-folder writer.** Startup passes the configured agent keys of the current project (none
   outside a project) instead of the full fleet; `~/.agent/workflows` is never written; owned
   `spec-kitty.*.md` there are removed on startup using the writer's existing ownership proofs
   (inventory entry, or the `spec-kitty-command-version` marker), never name alone.
7. **Frontmatter per target.** Shared root `.agents/skills/` gets only spec fields
   (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`); non-spec keys
   move under `metadata` as strings. Native roots (`.claude/skills`, `.github/skills`,
   `.cursor/skills`, `.qwen/skills`, `.kilocode/skills`) keep Claude-style keys.
8. **Validator.** PyPI `skills-ref` (Apache-2.0, anthropics/agentskills; console script
   `agentskills`) runs in a new always-on `ci-router.yml` job over the shipped skill tree and a
   freshly generated project; an in-repo pure-Python check mirrors the same rules in unit tests so
   the rules are also enforced without network.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing). CI-only: `skills-ref==0.1.1`
(not added to `pyproject.toml`; run via `uvx --from skills-ref==0.1.1 agentskills`).
**Storage**: JSON manifests (`.kittify/command-skills-manifest.json`, `.kittify/skills-manifest.json`,
`~/.kittify/cache/slash_commands-assets.json`)
**Testing**: pytest; red-first `@pytest.mark.p0_repro(issue=6475)` / `(issue=6470)` reproductions
through `spec-kitty init` (CliRunner) on the base commit, converted to ordinary tests by the fix.
**Target Platform**: Linux, macOS, Windows 10+
**Project Type**: single (CLI)
**Performance Goals**: NFR-003 — startup writer +≤50 ms warm.
**Constraints**: C-001..C-006; complexity ≤15; ruff/format/mypy clean.
**Scale/Scope**: ~14 src modules, 2 migrations, ~120 test files and ~145 docs mention the dotted
form (classified in `occurrence_map.yaml`).

## Charter Check

- Single canonical authority — one naming module, one invocation-rewrite function, one frontmatter
  projection function. PASS by design; an architectural test pins "no other composer of the name".
- User Customization Preservation — every deletion is manifest/hash or marker proven via
  `asset_preservation.guard_destructive_removal` / `AssetPreparation.retire`; prefix matching is
  removed from orphan detection. PASS.
- ATDD / red-first — P0 repros committed RED before the fixes. PASS.
- Migration ledger — `order_manifest.txt` entries with `# tie:` annotations; config-aware; no
  mkdir. PASS.
- Pack source home — open-packs edited upstream, pin bumped via `charter pack vendor`. PASS.
- NO_FULL_HEAVY_SUITES_IN_MISSION — only targeted files + named gates. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/command-skill-names-and-antigravity-01M5DBWT/
├── spec.md, plan.md, research.md, data-model.md, occurrence_map.yaml
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
└── tasks.md + tasks/ (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/skills/command_skill_names.py      # NEW naming + invocation-rewrite authority
src/specify_cli/skills/skill_frontmatter.py        # NEW per-target frontmatter projection + spec rules
src/specify_cli/skills/{command_renderer,command_installer,pack_skill_renderer,
                        _user_input_block,_agent_roster,retired,installer}.py
src/specify_cli/skills/data/skills-manifest.schema.json
src/specify_cli/tool_surface/providers/command_skills.py
src/specify_cli/cli/commands/{init.py,_command_surface_doctor.py,agent/config.py}
src/specify_cli/core/config.py, agent_utils/directories.py, tool_surface/profiles/capability_matrix.py
src/specify_cli/runtime/agent_commands.py, src/specify_cli/__init__.py (startup scope)
src/charter/offering/pack_skills/{models,validation}.py, charter/activation/skill_preparation.py
src/charter/offering/skills/{spec-kitty-implement-review,spk-charter-profile-load}/SKILL.md
src/charter/offering/skills/spec-kitty-setup-doctor/references/agent-path-matrix.md
src/specify_cli/upgrade/migrations/m_4_0_0rc8_command_skill_hyphen_names.py   # NEW
src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py # NEW
src/specify_cli/upgrade/migrations/order_manifest.txt
scripts/ci/validate_agent_skills.py (NEW) + .github/workflows/ci-router.yml job
docs/adr/4.x/2026-10-20-1-command-skills-use-spec-conformant-names.md (NEW, amends 2026-04-07-1)
```

**Structure Decision**: single project; new logic lands in two new leaf modules under
`specify_cli/skills/` so every producer imports one authority.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Naming authority and rename

- **Purpose**: one module owns `command_skill_name(cmd)`, `command_skill_rel_path(cmd)`,
  `parse_command_skill_rel_path(rel)` (accepting only the canonical form; a separate
  `parse_legacy_command_skill_rel_path` for the dotted form), `LEGACY_COMMAND_SKILL_PREFIX`, the
  build-time uniqueness assertion, and `rewrite_command_invocations(text)`.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-017, FR-012 (name part).
- **Affected surfaces**: command_renderer:368/488, command_installer:306/327/376/710/1253-1271,
  providers/command_skills.py:62/66/410/430, init.py:98/175-253/729-737/1384-1420,
  pack_skill_renderer:27/46/128/131-136, _user_input_block:26, retired.py, manifest schema
  pattern (accept both while legacy entries exist), `_COMMAND_SKILL_AGENTS` in init.py derived
  from the roster.
- **Sequencing/depends-on**: none.
- **Risks**: shared prefix with charter skills (orphan scan must use the explicit set); snapshot
  tests and ~50 test files construct the path; plugin bundles derive names from installer paths
  (auto-follow; `MIN_SKILL_COUNT` unchanged).

### IC-02 — Rename migration, doctor flag and new-invocation notice

- **Purpose**: migration `4.0.0rc8_command_skill_hyphen_names` installs the canonical skills for
  configured command-skill agents (via `command_installer.install`), removes each manifest-owned,
  hash-matching legacy `spec-kitty.<cmd>/SKILL.md` (and the folder only when it becomes empty)
  through `guard_destructive_removal` + `ManifestProver`, drops the dotted manifest keys, keeps
  edited/unowned folders with a warning; doctor skills reports leftover legacy folders; init and
  upgrade print the new invocation.
- **Relevant requirements**: FR-005, FR-006, FR-007, NFR-001, NFR-002.
- **Affected surfaces**: new migration, order_manifest.txt, `_command_surface_doctor.py`,
  `command_installer.verify` (`legacy` list), upgrade report, init next-steps.
- **Sequencing/depends-on**: IC-01.
- **Risks**: historical migrations (`m_3_2_0rc35_pi_letta_backfill`) still check dotted paths and
  would re-install; they must read the canonical path through the naming authority or become
  no-ops after the rename (do not edit shipped behaviour beyond the path lookup; drift is
  audit-only — prefer making their `detect()` use the authority only if they would otherwise
  re-run; they are already ledger-settled on upgraded projects).

### IC-03 — Antigravity command delivery and project workflows retirement

- **Purpose**: add `antigravity` to the roster; remove it from slash-command registries; capability
  matrix and path matrix wording; migration `4.0.0rc8_retire_antigravity_workflows` removes owned
  `spec-kitty.*.md` from `.agent/workflows` (marker-or-manifest proven, canonical command names
  only), never the directory or foreign files, and installs the command skills when antigravity is
  configured.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-018 (path matrix).
- **Affected surfaces**: `_agent_roster.py`, `core/config.py`, `agent_utils/directories.py`,
  `agent/config.py` ordering, `capability_matrix.py`, `agent-path-matrix.md`, init token/panel,
  `test_config_registry.py` invariants.
- **Sequencing/depends-on**: IC-01.
- **Risks**: `runtime/doctor.py` KeyError if `.agent` stays in `AGENT_DIRS`; AI_CHOICES and
  `gitignore_manager` rows stay (`.agent/skills/` still a root).

### IC-04 — Home-folder writer scope and `~/.agent/workflows` cleanup

- **Purpose**: startup calls `ensure_global_agent_commands(agent_keys=<configured slash agents>)`;
  the freshness pre-check works for scoped key sets (stamp records keys; matches when the requested
  set equals or is a subset of a healthy stamped set); a startup cleanup removes owned
  `spec-kitty.*.md` from `~/.agent/workflows` through the inventory / marker proof.
- **Relevant requirements**: FR-011, NFR-003.
- **Affected surfaces**: `runtime/agent_commands.py`, `specify_cli/__init__.py:146-155`,
  freshness/startup tests, performance test.
- **Sequencing/depends-on**: IC-03 (antigravity out of `AGENT_COMMAND_CONFIG`).
- **Risks**: performance budget; startup outside a project; concurrency lock semantics unchanged.

### IC-05 — Spec-conformant frontmatter, limits and validator

- **Purpose**: `skill_frontmatter.project_for_root(skill_md, native=bool)` moves non-spec keys under
  `metadata` for shared roots; command skills render spec-only frontmatter; pack skill rendering is
  per root; charter skill install applies the projection per root; pack validation enforces
  rendered name ≤64 and description (with Triggers suffix) ≤1024; `scripts/ci/validate_agent_skills.py`
  + ci-router job run `skills-ref`.
- **Relevant requirements**: FR-012, FR-013, FR-014, FR-015.
- **Affected surfaces**: command_renderer `to_skill_md`, pack_skill_renderer `_frontmatter`,
  installer `_expected_project_entries` / global projection, catalog staging, pack_skills
  models/validation, skill_preparation, ci-router.yml + router-gate needs + CI wiring tests.
- **Sequencing/depends-on**: IC-01.
- **Risks**: installer refuses differing bytes for one path across agents (projection must be
  keyed on the root, not the agent); strictyaml rejects flow style.

### IC-06 — Docs, ADR, agent tables, changelog, open-packs

- **Purpose**: ADR amending 2026-04-07-1; CLAUDE.md/AGENTS.md agent tables (Antigravity moves to
  the skills table); docs occurrences per the occurrence map; changelog; open-packs README fix and
  pin bump.
- **Relevant requirements**: FR-006 (release note), FR-016, FR-018.
- **Sequencing/depends-on**: IC-01..IC-05.
- **Risks**: docs freshness checker; terminology guard.

## Post-plan squad dispositions (2026-10-20)

Two profile-loaded reviewers (architect-alphonso, reviewer-renata). Every finding was accepted;
the amendments below override the concern text above where they disagree.

| # | Finding | Disposition |
|---|---------|-------------|
| A-B1 / R-B1 | After the rename, `prepare_commands(prune=True)` treats dotted entries as retired and `remove_entry` drift-deletes edited files (DERIVED/IGNORED gate) on `init`, `doctor skills --fix`, `agent config`, provider repair. | The naming authority classifies paths as canonical / legacy / other. The installer owns legacy handling: owned + hash-equal → delete (folder only if then empty); edited → keep, drop entry, emit a `legacy_kept` disposition with warning; never the drift-delete branch. The migration calls the installer, so there is one rule (FR-020). Ruling 2 already requires keep-edited, so no new operator decision. Fix `prune_stale`'s docstring. |
| A-B2 / R-M1 | Rename effect is outside VCS; committed ledger would settle teammates' clones. | `clone_local_effect = True`; `detect()` exact (legacy entry or legacy folder present); `apply()` idempotent; missing/corrupt manifest → success + warning, legacy folders left for doctor. |
| A-M1 / R-m2 | `m_3_2_0rc35_kittify_profile_handoff` patches dotted implement/review in place; `pi_letta_backfill` re-detects. | Do not edit historical migrations (DIRECTIVE_044). The rename's ownership proof also accepts bytes equal to the current render under the legacy name; a handoff-patched file that matches neither is kept with the warning (conservative; doctor reports it). Recorded in design-decisions. |
| A-M2 | A second frontmatter authority would make the verifier and the global `~/.agents/skills` writer disagree. | Extend `ensure_skill_frontmatter` into the root-aware projection (single module `skills/skill_frontmatter.py`, re-exported); thread root into `verifier._expected_content_hash` and `runtime/agent_skills._prepare_skill_tree`; architectural test: only that module strips/moves frontmatter keys. |
| A-M3 | Pack skills render once, copied per root. | `render_pack_skill` stays neutral; projection applied in `installer._expected_project_entries` keyed on the root. Native primary roots are `.claude/skills`, `.qwen/skills`, `.kilocode/skills` only. |
| A-M4 | Plugin bundles reuse the shared-root bytes. | Claude bundle applies the native projection; Codex/Copilot keep the spec projection; per-bundle frontmatter assertions. |
| A-M5 | Agent-dependent rewrite breaks `shared_content_conflict`. | `rewrite_command_invocations` is agent-independent: `/spec-kitty.<cmd>` and `$spec-kitty.<cmd>` → `/spec-kitty-<cmd>` / `$spec-kitty-<cmd>` (token sigil kept, name changed) for canonical commands only; `init._agent_command_token` derives from the naming authority. |
| A-M6 / R-m1 | Adding dotted names to retired sets re-arms `m_3_2_0rc45` and the global retire. | New `LEGACY_COMMAND_SKILL_NAMES` in the naming authority; the existing retired sets are untouched (FR-017 reworded). |
| A-M7 / R-M5 | Scoped home writer loses the fast path; cleanup never triggers. | Freshness stamp records per-key health; scoped calls write it; short-circuit when every requested key matches version+signature and is healthy; stamp carries a `retired_surfaces_cleaned` schema field so the first run on new code builds and cleans; `()` outside a project means "none", never "all". `agent config add <slash agent>` triggers that agent's write. |
| A-M8 / R-M5 | Home cleanup proof. | `AssetPreparation.retire()` (inventory proof) on `spec-kitty.*.md` children of a hard-coded `~/.agent/workflows`, probed with `role="destination_probe"`; a pre-inventory file is removed only on exact current-version marker + byte equality with a render from a frozen private antigravity config row; never the different-version predecessor branch; refuse a symlinked directory. |
| A-M9 / R-M3 | More `AGENT_COMMAND_CONFIG` consumers; `get_agent_dirs_for_project` loses `.agent`. | List them in the Antigravity WP (regen.py, assessment.py, rewrite_shims.py, shims/generator.py, surface_presence.py, agent/config.py, _command_surface_doctor.py). One `configured_slash_agents()` filter. Workflows migration gates on `get_configured_agents()` and a hard-coded retired path (C-003 deviation, rationale recorded); never mkdir. |
| A-M10 | Older CLI fails on a hyphen manifest. | Accept as clean break; release note + ADR; tighten pattern to canonical grammar while also accepting the legacy form for reading. |
| R-M2 | No proof for project workflows; FR-009 already passes. | Operator ruling 2026-10-20: archive (move to `.kittify/backups/antigravity-workflows/`) on exact marker line + historical command name + regular file; FR-009 relabelled `[ratchet]`. |
| R-M4 | Guard is lexical; symlinked dirs escape. | Refuse when `.agent`, `.agent/workflows` (or `~/.agent/workflows`) is a symlink or resolves outside its root; fixture. |
| R-M6 | One user folder at a canonical path fails the batch. | Operator ruling 2026-10-20: skip that path with a warning; `doctor skills` reports it; acceptance scenario in `tests/scenarios/init/` (FR-019). |
| R-M7 / R-m6 | Upgrade tests vacuous; red evidence lost on rebuild. | Fixtures strip the ledger row, seed prior-release dotted bytes + manifest, assert the migration's own record and warning; P0 repros assert literals, not the authority; red run captured with `SPEC_KITTY_RUN_P0_REPRO=1` and the red commit kept as the first commit of the rebuilt branch. |
| A-m1 | Uniqueness source set. | Build from `resolve_builtin_skill_catalog()` + built-in pack skills + retired + legacy sets. |
| A-m2 | Shipped `argument-hint`. | Source unchanged; projection moves it under `metadata` in shared roots; CI validates projected output. |
| A-m3 | `is_projected_skills_path` changes meaning. | Accept legacy paths for deletions only; listed in IC-01. |
| A-m4 / R-m4 / R-m5 | Duplicate commands in mixed harnesses; `runs_on_worktrees`; doctor never feeds `--fix` deletion by name. | ADR note; declare `runs_on_worktrees=True`; doctor legacy report is read-only. |
