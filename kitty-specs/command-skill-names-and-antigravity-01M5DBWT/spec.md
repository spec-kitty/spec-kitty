# Mission Specification: Spec-conformant command skill names + Antigravity skills delivery

**Mission Branch**: `issue-6475-6470-command-skill-names`
**Created**: 2026-10-20
**Status**: Draft
**Input**: Issues #6475 and #6470 (both P0, 4.0.0 release scope), with the operator rulings recorded in decision `01M5DBXJ05DSF4322SXVPNPZZ1`.

## Intent Summary

Spec Kitty delivers its workflow commands (specify, plan, tasks, implement, review, …) to
skills-based agent harnesses as generated Agent Skills. Today those skills are named
`spec-kitty.<cmd>`. The dot breaks the Agent Skills naming rule (lowercase letters, digits and
hyphens), so VS Code/Copilot, Cursor and OpenCode drop them without telling anyone, the
`skills-ref` validator rejects them, and skills.sh mangles them. Separately, Google Antigravity's
legacy workflows surface (`.agent/workflows`) stopped working on 2026-10-19, and Spec Kitty still
writes Antigravity's commands only there (project and home folder), so Antigravity users have no
working Spec Kitty commands.

This mission **renames the command skills from `spec-kitty.<cmd>` (old term) to
`spec-kitty-<cmd>` (new term)** for folder and `name`, with per-category rules captured in
`occurrence_map.yaml`; delivers every command to Antigravity as one of those skills; stops writing
and cleans up the dead `.agent/workflows` surfaces Spec Kitty owns; and keeps every generated
skill's frontmatter inside the Agent Skills specification.

- **Primary actor:** a developer using Spec Kitty through a skills-based harness (Codex, Vibe, Pi,
  Letta, Antigravity, and any harness that reads the shared `.agents/skills/` root).
- **Trigger:** `spec-kitty init`, `spec-kitty upgrade`, `spec-kitty agent config add`, or any CLI
  run (the home-folder writer).
- **Outcome:** every Spec Kitty command loads as a spec-valid skill in every harness that reads
  it, and invoking it by its new name works.
- **Invariant:** no mutating flow deletes or rewrites a file Spec Kitty cannot prove it owns
  (manifest entry plus unchanged content); hand-edited or foreign files are kept, with a warning.

## Domain Language

| Canonical term | Meaning | Avoid |
|----------------|---------|-------|
| Command skill | A generated Agent Skill that delivers one Spec Kitty workflow command (`spec-kitty-<cmd>/SKILL.md`). | "slash skill", "command file" |
| Slash-command file | A per-agent command file for the 13 command agents (for example `spec-kitty.specify.md`). Out of scope here (#6471). | calling these "skills" |
| Charter skill | A shipped doctrine skill such as `spec-kitty-setup-doctor` or `spk-start-here`. | — |
| Pack skill | A team skill shared through a charter pack (`<namespace>-<id>`). | — |
| Legacy dotted skill | An installed `spec-kitty.<cmd>/` command-skill folder from a release before this mission. | "old skill" without qualifier |
| Owned file | A file whose path is in a Spec Kitty manifest and whose bytes still match the recorded hash (or are recognisably Spec Kitty-generated, for the home folder). | "our file" by name pattern alone |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Command skills load in every skills harness (Priority: P1)

A developer runs `spec-kitty init --ai codex` (or any skills agent). The command skills appear as
`.agents/skills/spec-kitty-<cmd>/SKILL.md`, each with `name: spec-kitty-<cmd>` matching its folder,
and only frontmatter fields the Agent Skills specification allows. Copilot, Cursor and OpenCode,
which read the same root, load them.

**Why this priority**: Today the commands silently fail to load in several harnesses; this is the
P0 defect of #6475.

**Independent Test**: init a fresh project with a skills agent, validate every generated
`SKILL.md` against the Agent Skills rules (name grammar, name equals folder, allowed fields,
length limits).

**Acceptance Scenarios**:

1. **Given** a fresh project, **When** `spec-kitty init --ai codex` runs, **Then** every command
   skill folder is `spec-kitty-<cmd>`, its `name` equals the folder, and no `spec-kitty.<cmd>`
   folder is created.
2. **Given** generated command skills, **When** the Agent Skills validator runs over them,
   **Then** it reports zero violations.
3. **Given** a future command whose `spec-kitty-<cmd>` name would collide with a shipped charter
   skill or a retired skill name, **When** the command set is built, **Then** the build fails
   loudly rather than shipping two skills with one name.

### User Story 2 - Upgrading a project moves to the new names safely (Priority: P1)

A developer with an existing project (dotted command skills installed and recorded in
`.kittify/command-skills-manifest.json`) runs `spec-kitty upgrade`. The new `spec-kitty-<cmd>`
skills are installed, the unmodified dotted folders Spec Kitty owns are removed, the manifest
records only the new paths, and the CLI tells them the new invocation. A dotted folder the
developer edited by hand is kept, with a warning naming it.

**Why this priority**: without a migration every upgraded project ends up with two copies of each
command (one broken), or loses user edits.

**Independent Test**: seed a project with the previous release's dotted skills and manifest, edit
one of them, run the upgrade, inspect the tree, the manifest and the output.

**Acceptance Scenarios**:

1. **Given** manifest-owned, unmodified dotted skills, **When** upgrade runs, **Then** they are
   gone, the hyphenated skills exist, and the manifest has no dotted keys.
2. **Given** a hand-edited dotted skill, **When** upgrade runs, **Then** it is kept untouched, the
   manifest no longer claims it, and a warning names the path and says it is no longer managed.
3. **Given** a dotted folder that is not in the manifest (user-authored), **When** upgrade runs,
   **Then** it is not touched.
4. **Given** the upgrade already ran, **When** it runs again, **Then** nothing changes (idempotent).
5. **Given** a project where a skills agent was removed from the configuration (its directory
   deleted), **When** upgrade runs, **Then** no directory is re-created for it.
6. **Given** leftover dotted folders after upgrade, **When** `spec-kitty doctor skills` runs,
   **Then** it lists each leftover with the action to take.
7. **Given** a hand-edited dotted skill and a CLI already upgraded but `spec-kitty upgrade` not yet
   run, **When** `spec-kitty doctor skills --fix`, `spec-kitty init` or `spec-kitty agent config`
   runs, **Then** the edited file is kept with the same warning (every repair path follows the same
   rule, not only the migration).
8. **Given** a user-authored folder already at a new canonical path (for example
   `.agents/skills/spec-kitty-plan/` not recorded in the manifest), **When** `init` or `upgrade`
   installs the command skills, **Then** that one path is skipped and left untouched, every other
   command skill is installed, the command succeeds, and the output and `doctor skills` name the
   path with the remedy (operator ruling 2026-10-20). This is also an acceptance scenario in
   `tests/scenarios/init/`.
9. **Given** a teammate's clone that pulled a project already migrated elsewhere, **When** that
   clone upgrades, **Then** its own dotted skills are migrated too (the rename is recorded per
   clone, not in the committed ledger).

### User Story 3 - Antigravity users get working commands (Priority: P1)

A developer runs `spec-kitty init --ai antigravity`. Spec Kitty writes the command skills into the
shared `.agents/skills/` root that Antigravity reads and writes nothing into `.agent/workflows`.
On upgrade of an existing Antigravity project, the Spec Kitty-owned `spec-kitty.*.md` files in
`.agent/workflows` are removed and the directory and any foreign files in it are kept.

**Why this priority**: Antigravity's legacy workflows stopped working on 2026-10-19 (#6470);
Antigravity users currently have no Spec Kitty commands at all.

**Independent Test**: init with `--ai antigravity`, assert the command skills exist and no
`.agent/workflows` file exists; seed an old project with owned and foreign workflow files and
upgrade it.

**Acceptance Scenarios**:

1. **Given** a fresh project, **When** `spec-kitty init --ai antigravity` runs, **Then** every
   command skill exists under `.agents/skills/` and no `.agent/workflows` file is written.
2. **Given** an Antigravity project with Spec Kitty-written `.agent/workflows/spec-kitty.*.md` and
   a user-authored workflow in the same directory, **When** upgrade runs, **Then** only the
   Spec Kitty-generated files (exact version-marker line, a known command name, a regular file) are
   moved to `.kittify/backups/antigravity-workflows/` (archived, never deleted, operator ruling
   2026-10-20); the directory and the user file stay, and a symlinked `.agent` or
   `.agent/workflows` that leaves the project is refused.
3. **Given** the doctor and the agent path matrix, **When** a user reads them, **Then** they name
   `.agents/skills/` as Antigravity's command surface.

### User Story 4 - The home-folder writer stops spraying dead surfaces (Priority: P2)

On every CLI run, the global command writer installs slash-command files into the home folder.
It no longer writes `~/.agent/workflows`, it writes only for agents configured in the current
project, and it removes the Spec Kitty-owned `spec-kitty.*.md` files it previously left in
`~/.agent/workflows`, never the directory or other files.

**Why this priority**: the home-folder writes keep re-creating the dead Antigravity surface and
touch agent folders the user never chose (#3048 context).

**Independent Test**: run a CLI command with a temporary home folder and a project configured for
one agent; inspect which home folders were written and that owned Antigravity files are removed.

**Acceptance Scenarios**:

1. **Given** a project configured for `claude` only, **When** any CLI command runs, **Then** no
   command directory for an unconfigured agent is created in the home folder.
2. **Given** `~/.agent/workflows` holding Spec Kitty-generated files and a user file, **When** a
   CLI command runs, **Then** only the Spec Kitty-generated files are removed.

### User Story 5 - Pack skills and shipped skills stay within the spec (Priority: P2)

A team shares a pack skill with a long namespace and id. The generated skill name never exceeds
64 characters and its description never exceeds 1024 characters; an over-long declaration is
refused at validation with a clear message. Skills written to the shared `.agents/skills/` root
carry only specification fields (extras go under `metadata`); Claude-only fields
(`user-invocable`, `argument-hint`, `disable-model-invocation`) appear only in native roots that
support them. CI runs the Agent Skills validator over every generated and shipped skill.

**Why this priority**: the same silent-drop defect class, on the remaining skill producers.

**Independent Test**: validate a pack skill declaration at the boundary lengths; run the CI check
over a generated project and the shipped skill tree.

**Acceptance Scenarios**:

1. **Given** a pack skill whose rendered name would be 65 characters, **When** it is validated,
   **Then** it is refused, naming the limit.
2. **Given** the shipped and generated skills, **When** the CI validator job runs, **Then** it
   passes; **and given** a skill with a non-spec top-level field in `.agents/skills`, **Then** it
   fails.

### User Story 6 - Mission-step prompts invoke the new names (Priority: P2)

The shipped mission-step prompts (authored in `spec-kitty-open-packs`) tell agents to run
`/spec-kitty.<cmd>` or `$spec-kitty.<cmd>`. Where those refer to command skills, they use the new
`spec-kitty-<cmd>` names, and core consumes the updated pack through the documented pin bump.

**Independent Test**: grep the synced built-in pack for skill invocations of the dotted form.

### Edge Cases

- A dotted skill folder exists on disk but the manifest is missing or corrupt: the migration
  refuses to delete anything it cannot prove it owns and reports the manifest problem.
- The manifest records a dotted path whose folder is already gone: the entry is dropped, nothing
  else happens.
- A dotted folder contains extra user files beside `SKILL.md`: `SKILL.md` may be removed if owned
  and unmodified, the folder and the extra files are kept.
- Both the dotted and the hyphenated folder already exist (partial earlier run): the result is the
  same as a clean run.
- `.agent/workflows` is a symlink or contains a symlink named `spec-kitty.*.md`: nothing outside
  the project is followed or deleted.
- The home-folder writer runs with no project (outside any repository): it writes nothing for
  unconfigured agents and still performs the owned Antigravity cleanup.
- Windows path handling for every path above.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Spec-conformant command skill names | As a skills-harness user, I want every command skill folder and `name` to be `spec-kitty-<cmd>` so that every harness loads it. (#6475) | High | Open | [build] | no — a red-first p0_repro test asserts the folder/name on a fresh init |
| FR-002 | One naming authority | As a maintainer, I want the command-skill name produced by one function/constant that every producer, parser and checker uses, so that the name cannot drift between modules. | High | Open | [build] | no — an architectural test asserts no other module composes the name |
| FR-003 | Name uniqueness check | As a maintainer, I want building the command-skill set to fail if any `spec-kitty-<cmd>` equals a shipped charter skill name or a retired skill name, so that two skills never share a name. | High | Open | [build] | no — a test injects a colliding command and asserts failure |
| FR-004 | Ownership-keyed orphan detection | As a user, I want orphan/stale detection to be keyed on the manifest and the explicit command set, never on a name prefix, so that my own `spec-kitty-*` skills are never classified as Spec Kitty's. | High | Open | [build] | no — a test places a user `spec-kitty-mine` skill and asserts it is not reported or touched |
| FR-005 | Rename migration | As a user upgrading, I want a migration that installs the new command skills, removes manifest-owned unmodified dotted skills, keeps hand-edited ones with a warning, rewrites the manifest keys, is idempotent, respects the agent configuration and never creates directories, so that my project ends up with exactly one working copy of each command. (#6475) | High | Open | [build] | no — fixture seeded with prior-release bytes and one edited skill |
| FR-006 | New-invocation notice | As a user, I want `init` and `upgrade` output and the release notes to tell me the new invocation names, so that I know how to call the commands after the rename. | Medium | Open | [build] | no — output assertion on the upgrade/init path |
| FR-007 | Doctor flags leftover dotted skills | As a user, I want `spec-kitty doctor skills` to list leftover dotted command-skill folders with the remedy, so that I can clean them up. | Medium | Open | [build] | no — fixture with a kept edited dotted skill |
| FR-008 | Antigravity receives command skills | As an Antigravity user, I want `init`/`upgrade`/`agent config add antigravity` to install the command skills into `.agents/skills/`, so that every Spec Kitty command works in Antigravity. (#6470) | High | Open | [build] | no — a red-first p0_repro test asserts the command surface on `init --ai antigravity` |
| FR-009 | No project `.agent/workflows` writes | As an Antigravity user, I want Spec Kitty to keep not writing `.agent/workflows` in projects (true on the base commit since 3.1.2), so that it never targets the dead surface again. (#6470) | High | Open | [ratchet] | yes — guard only; paired with the FR-008 positive control on the same init fixture |
| FR-010 | Project workflows cleanup migration | As an upgrading Antigravity user, I want a migration that archives only Spec Kitty-generated `spec-kitty.*.md` files from `.agent/workflows` into `.kittify/backups/antigravity-workflows/`, never the directory and never foreign files, so that stale commands disappear and no edit is lost. (#6470) | High | Open | [build] | no — fixture with marked + foreign + symlinked files |
| FR-011 | Home-folder writer scoped and cleaned | As a user, I want the global writer to stop writing `~/.agent/workflows`, to write only for agents configured in the current project, and to remove only Spec Kitty-owned `spec-kitty.*.md` files from `~/.agent/workflows`, so that my home folder is not filled with dead or unwanted command files. (#6470, #3048 context) | High | Open | [build] | no — temp-home fixture |
| FR-012 | Spec-only frontmatter in the shared root | As a skills-harness user, I want skills written to `.agents/skills/` (command skills and pack skills) to carry only Agent Skills specification fields, with any extras under `metadata`, so that strict validators accept them. (#6475) | High | Open | [build] | no — validator over a generated project |
| FR-013 | Claude-only fields only in native roots | As a maintainer, I want `user-invocable`, `argument-hint` and `disable-model-invocation` emitted only into native roots that support them, so that the shared root stays spec-valid while native harnesses keep their behaviour. | Medium | Open | [build] | no — per-root frontmatter assertion |
| FR-014 | Name and description limits | As a pack author, I want pack skill validation and rendering to enforce name ≤ 64 and description ≤ 1024 characters, so that a generated skill is never silently dropped for length. (#6475) | High | Open | [build] | no — boundary tests at 64/65 and 1024/1025 |
| FR-015 | Validator in CI | As a maintainer, I want a CI check that runs the Agent Skills validator over every generated and shipped skill, so that a non-conformant skill fails the PR. (#6475) | Medium | Open | [build] | no — the check is shown failing on a seeded bad skill |
| FR-016 | Mission-step prompts use new names | As a user, I want the shipped mission-step prompts to invoke command skills by the `spec-kitty-<cmd>` name, via an open-packs change and a core pin bump, so that agents call skills that exist. | Medium | Open | [build] | no — grep of the synced pack |
| FR-017 | Legacy dotted names recorded once | As a maintainer, I want the dotted command-skill names recorded as legacy in the naming authority (not in the existing retired-skill sets, which drive other removal paths), so that every repair path classifies them the same way. | Medium | Open | [folded] | no — folded into FR-005's fixture |
| FR-019 | Canonical-path collision skipped | As a user with my own folder at a new canonical path, I want install to skip that path with a warning instead of failing the whole batch, so that init and upgrade still succeed. | High | Open | [build] | no — acceptance scenario + unit test with a user-authored `spec-kitty-plan/` |
| FR-020 | Same rule on every repair path | As a user, I want `doctor skills --fix`, `init`, `agent config` and the tool-surface repair to treat legacy dotted skills exactly as the migration does, so that running them before `upgrade` never deletes my edits. | High | Open | [build] | no — edited dotted fixture run through each path |
| FR-018 | Docs, ADR and agent tables updated | As a reader, I want the agent path matrix, the docs, `CLAUDE.md`/`AGENTS.md` agent tables and a new ADR amending 2026-04-07-1 to describe the new names and the Antigravity surface, so that docs mirror shipped behaviour. | Medium | Open | [build] | no — docs freshness/terminology checks plus review |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No loss of user edits | 0 user-edited or foreign files deleted or rewritten across every migration and writer fixture in the test suite. | Safety | High | Open |
| NFR-002 | Idempotence | A second consecutive `upgrade` run produces 0 file changes and 0 manifest changes. | Reliability | High | Open |
| NFR-003 | CLI startup cost | The home-folder writer adds no more than 50 ms to a warm CLI invocation compared with the base commit on the same machine (fast path unchanged). | Performance | Medium | Open |
| NFR-004 | Code quality gates | All new and changed code passes ruff, ruff format and mypy with 0 findings; every new function has complexity ≤ 15; diff coverage ≥ 90 %. | Maintainability | High | Open |
| NFR-005 | Cross-platform | All new path handling passes the existing Windows-marked tests and uses POSIX-normalised manifest keys. | Portability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Slash-command files unchanged | The 13 command agents' slash-command files keep their `spec-kitty.<cmd>` names (#6471 is out of scope). | Scope | High | Open |
| C-002 | Ownership proof required | No deletion without manifest ownership plus unchanged content (or, in the home folder, a recognisable Spec Kitty generation marker); name-pattern matching alone never proves ownership (charter: User Customization Preservation). | Safety | High | Open |
| C-003 | Migration ledger rules | New migrations follow the ledger model: `order_manifest.txt` entry, idempotent `apply()`, config-aware via `get_agent_dirs_for_project()`, never `mkdir` an agent directory. | Technical | High | Open |
| C-004 | Pack content authored upstream | Mission-step prompt changes are authored in `spec-kitty-open-packs` and consumed via `charter pack vendor` + `make sync-packs`; `packs/built-in/` is never edited in core. | Process | High | Open |
| C-005 | Clean break | No compatibility alias keeps the dotted command-skill names installed; the dotted names become retired. | Product | High | Open |
| C-006 | Stop on uncovered decisions | Any case not covered by the operator rulings (for example a future command name colliding with a charter skill) stops for an operator decision instead of being guessed. | Process | High | Open |

### Key Entities

- **Command-skill manifest** (`.kittify/command-skills-manifest.json`): records each managed
  command-skill path, its content hash and the agents that share it; the ownership proof for
  migration and orphan detection.
- **Command set**: the explicit list of canonical commands that become command skills.
- **Global command writer state**: what the home-folder writer has installed and how it recognises
  its own files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of generated command skills and shipped skills pass the Agent Skills validator
  (0 violations) in CI. — [build] · no-op passable: no
- **SC-002**: A fresh `init --ai antigravity` yields all 14 command skills, 0 project
  `.agent/workflows` files and 0 `~/.agent/workflows` Spec Kitty files. — [build] · no-op passable: no
- **SC-003**: Upgrading a prior-release fixture leaves exactly one copy of each of the 14 commands,
  0 dotted manifest keys, and every edited/foreign file intact. — [build] · no-op passable: no
- **SC-004**: Both P0 reproduction tests are red on the base commit and green on the mission head.
  — [build] · no-op passable: no

## Assumptions

- Antigravity reads Agent Skills from the shared `.agents/skills/` root (already declared in
  Spec Kitty's skill-root configuration). Its documentation host was unreachable from the build
  environment on 2026-10-20, so its handling of dotted names is not re-verified here; the
  hyphenated names comply with the Agent Skills rule either way.
- The `skills-ref` validator, if not installable in CI, is replaced by an equivalent in-repo
  checker that implements the same published rules, with the reason recorded in the plan.
- An older CLI cannot read a command-skill manifest written by this release (the manifest schema
  pattern changes); accepted as part of the clean break and named in the release note. The
  manifest is per-machine and untracked by default, so this bites only a downgrade.
- Projects that combine a slash-command agent with a shared `.agents/skills/` reader (for example
  codex + copilot) now see each command twice in that harness, because the skills load at last;
  recorded in the ADR, resolved by #6471.
- Codex, Vibe, Pi and Letta read the hyphenated names the same way they read the dotted ones
  (they resolve skills by folder).

## Out of Scope

- Renaming or retiring the 13 command agents' slash-command files (#6471).
- The skills.sh listing itself (#6469); this mission only removes the dotted name it mangles.
- Antigravity's announced "new workflows system" (tracked by #1646).
