# Feature Specification: Legacy doctor audits report what they did not check

**Mission**: legacy-doctor-empty-audit-truthful-01M68WJ9
**Mission ID**: 01M68WJ9PT51PG0WTGAP1GWE12
**Created**: 2026-10-31
**Status**: Draft
**Issue**: [#6891](https://github.com/spec-kitty/spec-kitty/issues/6891)
**Target branch**: main (PR branch `issue-6891-legacy-doctor-empty-audit-truthful`)

## Summary

`doctor` lies about a legacy project. When `.kittify/config.yaml` has **no**
`agents.available` list — the every-agent fallback (#6501) — two of its audits
derive their examined set from `config.available`, which is empty, and then
report health over the empty set:

```
$ spec-kitty doctor skills          # legacy: agents: {auto_commit: true}
Command Skills: all manifest entries healthy (0 file(s))     # exit 0

$ spec-kitty doctor tool-surfaces
Tool Surfaces: all surfaces healthy (0 checked)              # exit 0
```

Both lines assert that what they looked at is healthy. They looked at nothing.
That is worse than a missing check: an operator reads "all … healthy" on a
project whose agent surfaces were never examined, and the sibling
`doctor command-files`, on the same tree, reports real findings and exits 1.

**Reproduction (current `main`, `6f73b2a98e`).** A legacy fixture —
`.kittify/config.yaml` containing only `agents: {auto_commit: true}`, a
`.claude/commands/` tree written by an old init (stale `spec-kitty.*.md`
bodies), no `.agents/skills` manifest — gives the two lines above at exit 0,
while `doctor command-files` on the same fixture reports 112 findings at exit 1.
Transcripts: `research/repro-*.txt`.

**Root cause.** The examined set is `config.available`:

- `_load_command_skill_state` (`_command_surface_doctor.py`) computes
  `configured_agents = sorted(set(config.available) & supported)` → `[]`, so no
  agent's command skills and no slash commands are checked, and the summary
  prints `all manifest entries healthy (len(manifest.entries))` — `0`.
- `_configured_tool_keys` → `[]`, so `run_tool_surfaces` is handed no tools, the
  report has zero surfaces, and `_print_tool_surface_human` prints
  `all surfaces healthy (0 checked)`.

The audits are structurally correct; only their *summary* confuses "checked,
healthy" with "nothing examined".

**The change (issue's first option, "its own truthful summary").** An audit that
examined nothing stops claiming health and names why: the project states no
agent list, so the CLI cannot tell which surfaces to verify, and no agent
surface was checked. The alternative (widening the audit to all supported
agents) is rejected: on a legacy project that only uses one tool it turns a
false green into a storm of false reds, and which harness owns which surface is
#6472's decision.

## User Scenarios & Testing

### Primary scenario — a legacy project is not told it is healthy

1. Operator has a project whose `.kittify/config.yaml` predates the agent list
   (only `agents.auto_commit`, no `available`), with real surface drift on disk.
2. They run `spec-kitty doctor skills`.
3. Instead of `all manifest entries healthy (0 file(s))`, they read a line that
   says the project states no agent list, that every agent is therefore
   available, that **no agent surface was checked**, and that the check needs a
   stated agent list to say anything about surfaces. Exit stays 0 (nothing found
   is not a finding, and the command's documented exit contract does not change).
4. `spec-kitty doctor tool-surfaces` says the same thing in its own words
   (`no surfaces examined`), instead of `all surfaces healthy (0 checked)`.

### Positive control — a stated list still reports real health

- The same fixture with `agents.available: [codex]` and `command_installer.install`
  run still prints `all manifest entries healthy (N file(s))` with `N > 0`, and
  a project with a stated list and a deleted managed file still exits 1 with the
  gap named. The truthful line must be reachable **only** when nothing was
  examined; it must not swallow a real result.

### Non-regression — the plugin-owned (stated-empty) shape

- `agents.available: []` (stated empty, #6494) is #6493/#6894's shape. This
  Mission does not change its wording or its decisions; if #6894 has landed by
  the time this Mission is implemented, its stated-empty line is reused rather
  than duplicated. The invariant this Mission adds — never claim health over
  zero examined surfaces — must hold for every empty examined set, whatever the
  reason.

### Edge cases

- **Legacy project that does have examined content.** A legacy project with a
  populated `.agents/skills` manifest, or with on-disk canonical/legacy folders,
  is already examined (`verify()` scans those regardless of config). Real
  findings keep winning: the truthful "nothing checked" line may appear only
  when the report is otherwise empty, never in place of a finding.
- **`--fix` in the legacy shape.** Nothing is installed (no agent is known to
  install for). The report must not claim it repaired anything, must not
  recommend installing surfaces, and must print the same truthful line.
- **The stated-empty shape is not this Mission's to change.** `available: []`
  keeps its current text until #6493 / PR #6894 lands (C-001); FR-001/FR-002 are
  therefore scoped to the *legacy* shape, not to every empty examined set.
- **Unreadable config.** Still the documented `config_error` envelope at exit 2
  (`_configured_tool_keys_or_exit`, `_load_skills_state_or_exit`) — unchanged.
- **`--json` consumers.** Every existing key keeps its meaning; the truthful
  wording is a human report line, and the zero counts the JSON already carries
  (`entries`, `summary.surfaces`) remain the machine-readable signal.

## Domain Language

| Term | Meaning in this Mission | Do not read as |
|------|-------------------------|----------------|
| **legacy shape** | `.kittify/config.yaml` with no `agents.available` key: the CLI treats every supported agent as available (#6501). | "no agents" |
| **stated-empty shape** | `agents.available: []`: the project states the CLI manages no agents (#6494). Owned by #6493 / PR #6894. | legacy, or "unconfigured" |
| **examined set** | The surfaces an audit actually inspected in this run (manifest entries it verified, surfaces `run_tool_surfaces` collected). | "configured agents" |
| **health claim** | A summary line asserting `all … healthy`. Legal only when the examined set is non-empty. | a status or exit code |

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `doctor skills` summary never claims health over an empty examined set **in the legacy shape** | As a legacy-project operator, I want the command-skills summary to say it checked nothing and why, so that I do not believe a zero-file check covered my agent surfaces. | High | Open | [build] | no — a no-op keeps printing `all manifest entries healthy (0 file(s))` |
| FR-002 | `doctor tool-surfaces` summary never claims health over zero checked surfaces **in the legacy shape** | As a legacy-project operator, I want the tool-surface summary to say no surface was examined because no agent list is stated, so that exit 0 is not read as "my surfaces are fine". | High | Open | [build] | no — a no-op keeps printing `all surfaces healthy (0 checked)` |
| FR-003 | The truthful line names the cause and the gap | As an operator, I want the line to say the project states no agent list (every agent is available), that nothing was checked, and that it cannot tell which surfaces to verify — without prescribing an install. | High | Open | [build] | no — naming the cause is the whole deliverable |
| FR-004 | A non-empty examined set keeps its existing summary | As a maintainer, I want stated-list projects to keep `all … healthy (N …)` / real findings / the documented exit codes, so the fix cannot hide a real result. | High | Open | [ratchet] | yes — paired on the same fixture with FR-001/FR-002's negative assertion |
| FR-005 | `--json` envelopes keep their exact keys | As a script consumer, I want no key added, renamed or removed, so my parsing keeps working; the zero counts already in the payload are the machine-readable truth. | Medium | Open | [ratchet] | yes — pinned by the existing key assertions plus a new explicit set-equality test per command |
| FR-006 | No added config read and no new config predicate | As a maintainer, I want the empty-examined decision to reuse the `AgentConfig` the command already loads (and the existing `explicit_agent_list` reader), so the truth has one source and this change adds no YAML parse. | Medium | Open | [build] | no — a `load_agent_config` count above the recorded baseline fails the test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Exit-code contract unchanged | `doctor skills` and `doctor tool-surfaces` keep `0` ok / `1` issues / `2` not-in-project or bad config; a nothing-examined report stays exit `0` for all shapes (legacy, stated-empty, no config file). | Reliability | High | Open |
| NFR-002 | Zero added config reads | `load_agent_config` call count per invocation is unchanged from the recorded `6f73b2a98e` baseline — `doctor skills` = 3, `doctor tool-surfaces` = 1 (measured with the loader wrapped; `research/load-counts.txt`) — so no added parse, no second YAML read and no cost growth. | Performance | Medium | Open |
| NFR-003 | No new surface | Zero new CLI commands, flags, or options; zero new third-party dependencies; the change stays inside the command-surface doctor cluster and its tests. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Legacy shape only; do not re-decide stated-empty | #6493 / PR #6894 owns the stated-empty wording and the `no_cli_managed_agents` predicate. This Mission must not change that shape's decisions; if it has landed, reuse its line instead of duplicating a second wording for the same cause. | Technical | High | Active |
| C-002 | No surface-install advice for the legacy shape | The truthful line must not tell a no-agent-list project to install or add agents: for a project whose surfaces a plugin provides, "install the CLI's copies" is #6493's duplicate-surface harm. Name the state and the gap; prescribe nothing. | Business | High | Active |
| C-003 | `doctor command-files` unchanged | It already reports a real finding for the legacy shape (no tool folder) and is out of scope; its output must not change. | Technical | Medium | Active |
| C-004 | No gate weakened | No test is skipped, xfailed or relaxed to make this land; pre-existing reds (#6798, #6801, #6816, #5927) are cited, never papered over. | Process | High | Active |
| C-005 | Red-first through the production entry point | Both defects get failing tests through `CliRunner` on the real `doctor` app (`skills`, `tool-surfaces`) before the source change; a helper-only test does not satisfy this. | Technical | High | Active |

## Key Entities

- **`AgentConfig`** (`specify_cli.core.agent_config`) — already carries
  `available` and `explicit_agent_list`; the empty-examined decision reads it,
  it does not re-parse YAML.
- **Command-skill state tuple** (`_load_command_skill_state`) — the one place
  that knows both the configured agents and the loaded config; it grows the
  knowledge needed for the truthful line, not a second loader.
- **`VerifyReport`** (`command_installer`) — the examined-then-compared result;
  "nothing examined" means an empty report over an empty manifest.
- **`ToolSurfaceOutcome.report.summary.surfaces`** — the tool-surface examined
  count whose zero is today printed as health.

## Success Criteria

- **SC-001**: On the legacy fixture (config with only `agents: {auto_commit: true}`, a real `.claude/commands` tree, no manifest), `doctor skills` and `doctor tool-surfaces` both print a line naming the absent agent list, stating that no surface was checked, and containing no `all … healthy` claim; both exit 0. — [build] · no-op passable: no
- **SC-002**: On the same fixture with `agents.available: [codex]` and command skills installed, `doctor skills` still prints `all manifest entries healthy` with a non-zero count (positive control), and a deleted managed file still exits 1 naming the gap. — [ratchet] · no-op passable: yes — the fixture's positive half guards the negative half
- **SC-003**: `doctor skills --json` and `doctor tool-surfaces --json` return exactly the key set they return on `6f73b2a98e` for the same fixture. — [ratchet] · no-op passable: yes — pinned by an explicit set-equality assertion per command
- **SC-004**: Reverting either half of the fix (skills line, tool-surfaces line) turns its own test red and leaves the other green — a half-fix cannot pass. — [ratchet] · no-op passable: no

## Resolved Decisions

- **Name it; do not widen the audit (issue's two options).** Widening to the
  every-agent fallback would examine 20 tools a legacy project does not use and
  emit false reds; naming the gap is honest, cheap, and forward-compatible with
  #6472's ownership record. (Issue text offers both; recorded here so review
  does not re-open it.)
- **Exit code stays 0.** `doctor`'s contract is 0 ok / 1 issues; "nothing to
  check" is not an issue. Honesty is carried by the line, not by a new failure
  mode that would break scripts and CI on legacy projects.
- **Human-only wording.** The line is a human report line; JSON keeps its exact
  keys (and would otherwise force a contract change on #6894's overlapping PR).

## Assumptions

- A legacy project that is genuinely healthy is not the target: it is
  indistinguishable from a legacy project with drift the audit cannot see, which
  is exactly why the line must not claim health.
- `command_installer.verify()` already scans on-disk canonical/legacy folders
  regardless of config, so the surviving config-independent checks keep finding
  real leftovers in the legacy shape (verified in `research/repro-3.txt`).

## Out of Scope

- The stated-empty shape's wording and predicate (#6493 / PR #6894).
- Widening any audit to the every-agent fallback, and per-harness surface
  ownership (#6472).
- `doctor command-files` (C-003) and every other `doctor` subcommand.
- Any new `--json` key, flag or command.
