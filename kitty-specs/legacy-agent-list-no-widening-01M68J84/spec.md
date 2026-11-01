# Mission Specification: A legacy agent list resolves to the agents the project has, never the whole registry

**Mission Branch**: `issue-6501-legacy-agent-list-no-widening` (planning base and merge target)
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6501 — a missing `.kittify/config.yaml`, or one with no `agents` section, makes migrations and doctor act on every agent folder."

Issue: #6501 (whole). Split out of #6494 by operator triage on 2026-10-19; #6494 owns the explicit
empty list (`available: []`), which is already fixed on `main` (`0356bbdcb7`). The corrupt/unreadable
config case also already fails closed there and is out of scope here.

## Intent Summary (confirmed 2026-10-31)

- **Primary actor**: an operator who upgrades, repairs or diagnoses a project created before agent
  selection was recorded in `.kittify/config.yaml`.
- **Trigger**: the project's `.kittify/config.yaml` is absent, or it carries an `agents` (or legacy
  `tools`) section with no `available` list — the "no stated list" shape. Any of the 27 upgrade
  migrations, `doctor`, shim generation or `.gitignore` repair then asks
  `get_agent_dirs_for_project()` / `ignored_agent_keys()` which agents are in play.
- **Today**: the helper returns the whole `AGENT_DIRS` registry (12 slash-command agents). So a
  project that only ever had `.claude/` gets `.github/prompts`, `.gemini/commands`, `.cursor/commands`
  and the rest rewritten or recreated, and `doctor` audits command files for agents the project
  does not have. That is a silent misread of "no list" as "every agent".
- **Desired outcome**: "no stated list" resolves to the agents whose command surface is already
  **present in the project** (the observed set), and the read says so out loud: one warning naming
  `.kittify/config.yaml`, the `agents.available` key and the remedy. The helper never widens beyond
  what the project already has, and never invents a surface that was not there.
- **Domain terms**: *agent key* (a key in `AI_CHOICES`, e.g. `claude`); *agent directory*
  (`AGENT_DIRS` entry, e.g. `(".claude", "commands")`); *project surface* — the project-local managed
  directory `<agent_root>/<subdir>` (`.claude/commands`); *stated list* — an `available` key present
  in the config (`[]` included); *no stated list* — config absent, no `agents`/`tools` section, or a
  section without `available`; *observed set* — the agent keys whose project surface exists.
- **Why not a hard refusal**: the ADR that introduced this fallback
  (`docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md`) requires that legacy projects keep
  working on upgrade. Refusing the read would abort `spec-kitty upgrade` mid-migration chain for
  exactly the population this issue is about, and the chain calls the helper *before* any new
  migration could record the list. The observed set keeps legacy repair working (a stale
  `.claude/commands` is still migrated) while removing the widening.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A legacy project only has its own agent surfaces touched (Priority: P1)

An operator on a project created before agent selection was recorded upgrades it. The project has
`.claude/commands/` and nothing else; `.kittify/config.yaml` has no `available` list. The migrations
rewrite the Claude command files and leave every other agent directory alone — they are not created,
not rewritten, not reported by `doctor`.

**Why this priority**: it is the reported defect (#6501). Widening writes into directories the user
never chose, which is the "surprise directory recreation" the config-driven ADR set out to end.

**Independent Test**: build a project whose only agent directory is `.claude/commands`, with a config
that has no `available` list, and assert the helper returns exactly `[(".claude", "commands")]` and
that a migration/doctor read of the project reports no other agent.

**Acceptance Scenarios**:

1. **Given** a project with `.claude/commands/` and a `.kittify/config.yaml` that has no `agents`
   section, **When** the agent list is read, **Then** only `(".claude", "commands")` is returned.
2. **Given** the same project, **When** the read happens, **Then** one warning names
   `.kittify/config.yaml`, `agents.available` and the remedy (`spec-kitty agent config`).
3. **Given** a project with no `.kittify/config.yaml` at all but a `.cursor/commands/` directory,
   **When** the agent list is read, **Then** only `(".cursor", "commands")` is returned.
4. **Given** a project with no agent directory at all and no stated list, **When** the agent list is
   read, **Then** the result is empty and the same warning is emitted — no surface is invented.

---

### User Story 2 - A stated list keeps its exact meaning (Priority: P1)

An operator with `available: [claude]`, or `available: []`, gets exactly what they stated. The change
does not soften the #6494 empty-list rule, does not resurrect the corrupt-config fallback, and a
project that states a list never sees the legacy warning.

**Why this priority**: the fix must be a narrowing of one branch, not a rewrite of the seam. A
regression here would undo #6494.

**Independent Test**: the pre-existing explicit-list and explicit-empty-list tests keep passing
unchanged, and no warning is emitted for either.

**Acceptance Scenarios**:

1. **Given** `agents.available: [claude]` and a `.cursor/commands/` directory on disk, **When** the
   agent list is read, **Then** only `.claude` is returned.
2. **Given** `agents.available: []`, **When** the agent list is read, **Then** the result is empty.
3. **Given** a corrupt `.kittify/config.yaml`, **When** the agent list is read, **Then** it raises
   `AgentConfigError` naming the remedy (unchanged behaviour).

---

### User Story 3 - The documented default matches the code (Priority: P2)

An operator reading the configuration reference learns what "no `available` list" means without
guessing: the agents present in the project are treated as in use, the warning tells them how to
record the list explicitly, and the behaviour does not reach beyond the project.

**Why this priority**: the defect is partly a documentation defect — `docs/api/configuration.md`
currently promises "the full slash-command agent set", which the code is changing.

**Independent Test**: `docs/api/configuration.md` describes the observed-set default and the remedy;
`docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with `(#6501)`.

**Acceptance Scenarios**:

1. **Given** the configuration reference, **When** the reader looks up the legacy fallback, **Then**
   it states the observed-set rule, the warning, and how to record the list.
2. **Given** the changelog, **When** the reader looks under `[Unreleased]`, **Then** one entry leads
   with the impact and cites `(#6501)`.

---

### Edge Cases

- `.github/` exists for CI but `.github/prompts/` does not: the project surface is the
  `<root>/<subdir>` directory, so Copilot is not treated as in use by a CI-only `.github/`.
- An agent's project surface is absent because commands are user-global (post-3.1.2 projects): such a
  project records an explicit list at `init`, so the legacy branch does not apply; if it does (a
  hand-written config), the warning names the remedy and nothing is invented.
- The `.gitignore` repair path (`ignored_agent_keys`) deliberately keeps its broader rule: over-
  ignoring generated files is harmless (it only keeps untracked files out of `git status`), whereas
  over-*acting* rewrites user files. This asymmetry is documented in code so a later reader does not
  "fix" it into consistency.
- Repeated reads (27 migrations) must not turn the warning into an error or a prompt; it is
  idempotent log output.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | No-list read resolves to the observed set | As an operator on a legacy project, I want the agent list read to return only the agents whose project surface exists, so that migrations and `doctor` never touch an agent folder the project does not have. | High | Open | [build] | no |
| FR-002 | The no-list read says what it did | As an operator, I want one warning naming `.kittify/config.yaml`, `agents.available` and the remedy when the list is absent, so that the default is never a silent misread. | High | Open | [build] | no |
| FR-003 | Empty observation returns no agents | As an operator on a project with no agent surface, I want the legacy read to return nothing rather than invent twelve surfaces. | High | Open | [build] | no |
| FR-004 | A stated list is untouched | As an operator who stated `available`, I want the read to return exactly that list, with no legacy warning. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture |
| FR-005 | The documented default matches the code | As an operator, I want `docs/api/configuration.md` to describe the observed-set default and how to record the list explicitly, so that the documented contract and the code agree. | Medium | Open | [build] | no |
| FR-006 | The changelog states the user-facing change | As a maintainer, I want an `[Unreleased]` changelog entry with before/after and `(#6501)`, so that the behaviour change is visible at release time. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic, home-independent read | The legacy branch resolves only project-local paths: identical project trees must give identical results on any machine, with no read of `$HOME` or user-global command directories. | Reliability | High | Open |
| NFR-002 | Bounded warning volume | The warning is emitted once per read (log only), no more than one line per call, so a 27-migration upgrade produces bounded output and never raises or prompts. | Reliability | Medium | Open |
| NFR-003 | Changed-line coverage | The changed lines of `src/specify_cli/agent_utils/directories.py` are covered at or above the CI diff-cover gate (90%) by the mission's tests. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No refusal on the upgrade path | The legacy read must not raise: the ADR requires legacy projects to keep upgrading, and the migration chain calls this helper before any list could be recorded. | Technical | High | Open |
| C-002 | One source of truth for agent directories | The observed set is filtered from the existing `AGENT_DIRS` / `AGENT_DIR_TO_KEY` registries; no second agent list is introduced. | Technical | High | Open |
| C-003 | #6494 semantics preserved | `explicit_agent_list`, the empty-list rule, and the fail-closed corrupt-config path keep their current behaviour and tests. | Technical | High | Open |

### Key Entities

- **AgentConfig**: the loaded `.kittify/config.yaml` view — `available` (stated list), `auto_commit`,
  `lint_on_edit`, and `explicit_agent_list` (whether `available` is stated). Its `explicit_agent_list`
  flag is what separates "stated empty" from "not stated"; this mission consumes it, it does not
  change it.
- **Observed set**: the agent keys from `AGENT_DIRS` whose project surface directory exists. Derived
  per read; never persisted by this mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a project whose only agent directory is `.claude/commands`, the agent list read
  returns exactly one entry, for both legacy shapes (no config file; config without an agents
  section). — [build] · no-op passable: no
- **SC-002**: A `doctor` slash-command audit and a representative upgrade migration, run on that
  project, report no agent other than `claude`. — [build] · no-op passable: no
- **SC-003**: `available: []` and `available: [<key>]` reads are byte-identical to `main`, and no
  legacy warning is emitted for either. — [ratchet] · no-op passable: no
- **SC-004**: The changed lines pass the CI diff-cover gate, and the touched documentation is fresh
  (`check_docs_freshness --ci`, errors=0). — [build] · no-op passable: no
