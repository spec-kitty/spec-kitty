# Mission Specification: Plugin-owned surfaces report truthfully

**Mission Branch**: `issue-6493-plugin-owned-surfaces-report-truthfully`
**Created**: 2026-10-31
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6493 — "Plugin-installed projects: init, agent config and doctor report 'not set up', and following their advice writes duplicate command surfaces"

## Problem and grounding

On a project whose command surfaces are supplied outside the CLI (for example by a
harness plugin), `.kittify/config.yaml` states that Spec Kitty manages no agent
surfaces — `agents.available: []`. #6494 gave that stated-empty list its meaning:
"no Spec Kitty-managed agents". The three setup and diagnostic surfaces did not
follow that ruling, so a project that is deliberately set up is reported as broken
and the recovery advice writes a second copy of every command:

| Command | Reports today on `origin/main` @ `35318ef51c` | Truth |
| --- | --- | --- |
| `spec-kitty agent config list` | `No agents configured.` + `Run 'spec-kitty init' or use 'spec-kitty agent config add' to add agents.` | The project states no CLI-managed agents; adding one installs a second copy of surfaces the plugin already supplies. |
| `spec-kitty init` (re-run) | `Already initialized. Agent skill surfaces were verified on this re-run: missing per-agent skill roots were restored.` | Nothing was verified or restored — the CLI manages no agent surfaces. |
| `spec-kitty init --ai claude` (re-run) | exits 1: `Initialization incomplete: Requested agents are not configured. Run: spec-kitty agent config add claude` | The project is set up; the stated list wins, and following the advice duplicates surfaces. |
| `spec-kitty doctor skills` | `Command Skills: all manifest entries healthy (0 file(s))` | Nothing was checked; "healthy" over zero files is vacuous. |
| `spec-kitty doctor tool-surfaces` | `Tool Surfaces: all surfaces healthy (0 checked)` | Nothing was checked. |
| `spec-kitty doctor command-files` | `Command Files: all files healthy` | Nothing was checked. |

The legacy shape is the mirror-image lie: a `.kittify/config.yaml` with **no**
agent list at all falls back to every agent (#6501), yet `agent config list` also
prints `No agents configured.` for it.

**Out of scope (deferred to #6472).** A project that *lists* an agent whose
command skills are absent because a plugin supplies them at harness level. Telling
that shape apart from a genuinely broken clone-local delivery (#4425) needs the
per-harness ownership record that #6472 owns. This mission invents no ownership
record; it makes the state the CLI can already distinguish truthful, which is the
prerequisite for #6472.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A project that states no CLI-managed agents is reported as set up (Priority: P1)

An operator installs Spec Kitty as a harness plugin, keeps `.kittify/config.yaml`
in the repository with `agents.available: []`, and runs the CLI's own setup and
diagnostic commands. Every one of them recognises the project as set up and says
what is actually true instead of pointing at a second install.

**Why this priority**: This is the defect the issue reports. The advice currently
printed is destructive in effect — following it duplicates every command surface
the user already has.

**Independent Test**: In a project whose `.kittify/config.yaml` states
`agents.available: []`, run `agent config list`, `init`, `init --ai claude`,
`doctor skills`, `doctor tool-surfaces` and `doctor command-files`; assert each
output names the stated no-CLI-managed state, none recommends `init` /
`agent config add` as a repair, and `init --ai claude` exits 0 without writing a
command-skill file.

**Acceptance Scenarios**:

1. **Given** a project whose config states `agents.available: []`, **When**
   `spec-kitty agent config list` runs, **Then** it reports that the CLI manages no
   agent surfaces for this project and does not tell the user to run `init` or
   `agent config add` to fix it.
2. **Given** the same project, **When** `spec-kitty init` re-runs, **Then** it
   exits 0, does not claim skill surfaces were verified or restored, and says the
   CLI manages no agent surfaces here.
3. **Given** the same project, **When** `spec-kitty init --ai claude` re-runs,
   **Then** it exits 0, installs nothing, and says the stated agent list wins over
   the flag.
4. **Given** the same project, **When** `doctor skills`,
   `doctor tool-surfaces` or `doctor command-files` runs, **Then** each says there
   are no CLI-managed surfaces to check instead of claiming they are all healthy.

### User Story 2 - A legacy config with no agent list is described as what it is (Priority: P2)

A pre-#6501 project has no agent list at all. The CLI treats every supported agent
as available for it, so the report must say that rather than "no agents
configured".

**Why this priority**: Same report-truthfulness defect, mirror image; leaving it
would keep `agent config list`'s first line false for a second population of
projects and would make the new "no CLI-managed agents" wording ambiguous.

**Independent Test**: With `.kittify/config.yaml` containing only
`agents: {auto_commit: true}` (no `available` key), `agent config list` names the
legacy all-agents fallback.

**Acceptance Scenarios**:

1. **Given** a config with no `available` key, **When**
   `spec-kitty agent config list` runs, **Then** it says there is no stated agent
   list and that the CLI treats every supported agent as available.

### Edge Cases

- `agents.available: [claude]` but claude's command skills are missing: **unchanged
  behaviour** — that is a real clone-local gap (#4425) and init must keep exiting 1
  with the sync recovery command. A test pins this so the new no-CLI-managed branch
  cannot swallow it.
- A config that is unreadable or not a mapping: unchanged — `AgentConfigError`
  still stops `agent config list`, `init` and `doctor skills` with the named remedy
  (#6494).
- `doctor skills --fix` and `doctor tool-surfaces --fix` in the stated-empty shape:
  no repair is attempted and nothing is written.
- `--json`: existing envelopes keep their keys and values; the "nothing to check"
  wording is human-output only, and `configured_agents: []` already carries the
  machine-readable fact.
- `agent config add <agent>` in the stated-empty project still works and is
  unchanged: it is how an operator deliberately hands a surface to the CLI.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One shared predicate for the stated-empty shape | As an implementer, I want a single named predicate for "this project states no CLI-managed agents" so that init, agent config and doctor cannot drift apart. | High | Open | [build] | no |
| FR-002 | `agent config list` reports both empty shapes truthfully | As an operator, I want `agent config list` to say "no CLI-managed agents" (stated empty) or "no stated list; every agent is available" (legacy) instead of "No agents configured", so that neither state is reported as a broken setup. | High | Open | [build] | no |
| FR-003 | `init` re-run claims no verification it did not do | As an operator of a stated-empty project, I want `init` to exit 0 and say the CLI manages no agent surfaces here, so that I am not told surfaces were verified or restored when nothing was. | High | Open | [build] | no |
| FR-004 | `init --ai <agent>` respects the stated list | As an operator, I want `init --ai claude` on a stated-empty project to exit 0, install nothing and explain that the stated list wins, so that a run of habit does not turn into an error that prescribes a duplicate install. | High | Open | [build] | no |
| FR-005 | Doctor surface checks stop claiming vacuous health | As an operator, I want `doctor skills`, `doctor tool-surfaces` and `doctor command-files` to say there is nothing CLI-managed to check in a stated-empty project instead of "all healthy (0 …)", so that a green line only ever describes a real check. | High | Open | [build] | no |
| FR-006 | No recovery advice writes a second copy | As an operator, I want no stated-empty-project output to present `init` / `agent config add` as the repair for a problem, so that following the CLI's advice can never install a duplicate of the plugin's surfaces. *(A neutral, conditional note that adding an agent hands ownership to the CLI is allowed.)* | High | Open | [build] | no |
| FR-007 | Genuine clone-local gaps keep failing | As a maintainer, I want `init` to keep exiting 1 with the sync recovery command when a *listed* agent's command skills are missing, so that the #4425 diagnosis is not weakened by the new branch. | High | Open | [ratchet] | no — paired on the same fixture with the stated-empty row |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Reports stay fast | Each of the six commands completes in under 2 s on a fixture project, adding no new I/O beyond the existing `config.yaml` read. | Performance | Medium | Open |
| NFR-002 | Machine output unchanged | `agent config list`, `doctor skills --json`, `doctor tool-surfaces --json` and `doctor command-files --json` keep every existing key and value; no new key is added for the stated-empty fact (the existing empty `configured_agents` already carries it). | Compatibility | High | Open |
| NFR-003 | Exit codes preserved | `doctor skills` / `tool-surfaces` / `command-files` keep exiting 0 for the stated-empty project (nothing is wrong); `init` re-runs exit 0; `agent config list` exits 0. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No ownership record invented | The mission adds no `.kittify/config.yaml` schema, no plugin-detection probe and no harness registry; the per-harness ownership record stays with #6472. | Technical | High | Open |
| C-002 | Source-of-truth for the predicate | The predicate reads `AgentConfig.explicit_agent_list` (#6494), not a re-parse of YAML, so a stale second reader cannot appear. | Technical | High | Open |
| C-003 | Single-authority wording | Each new message is emitted from one place per command; no message is duplicated across the human and JSON paths. | Technical | Medium | Open |

### Key Entities

- **Stated-empty agent list**: `agents.available: []` present in `.kittify/config.yaml`; means "no CLI-managed agents" (#6494).
- **Legacy absent agent list**: no `available` key; means "every supported agent is available" (#6501).
- **CLI-managed agent**: an agent key in the stated `available` list whose surfaces the CLI installs, syncs and checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the stated-empty fixture, all six commands name the no-CLI-managed state and none of the six outputs contains `No agents configured`, `Run 'spec-kitty init'`, `agent config add` as a repair, `all manifest entries healthy`, `all surfaces healthy` or `all files healthy`. — [build] · no-op passable: no
- **SC-002**: `init --ai claude` on the stated-empty fixture exits 0 and leaves the set of command-skill files on disk byte-identical to the pre-run tree. — [build] · no-op passable: no
- **SC-003**: The same fixture with `available: [claude]` still exits 1 from `init` with the sync recovery command, proving the stated-empty branch did not swallow the #4425 diagnosis. — [ratchet] · no-op passable: no
- **SC-004**: `doctor skills --json` on the stated-empty fixture returns exactly the same keys as before the change (test asserts the key set). — [ratchet] · no-op passable: no
