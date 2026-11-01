---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: plugin-owned-surfaces-report-truthfully-01M68JAV
mission_id: 01M68JAVG00ZFKFA08NR2VN880
generated_at: '2026-10-31T08:55:25.230089+00:00'
analyzer_agent: python-pedro
input_artifacts:
  spec.md:
    path: kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/spec.md
    sha256: 00cb1b1157bb8a4ddff69462fb8217ece79ca282e8dc6ca51350c54877db3e1b
  plan.md:
    path: kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/plan.md
    sha256: 4ffaea7022ab7dddc103f99117b543876ddbcac03b20105124ac52a7590087a9
  tasks.md:
    path: kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/tasks.md
    sha256: a1775b059da32197f25d142afdd781c51150bade0d79de387ca50fb036e6f48e
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  low: 3
  critical: 0
  medium: 2
  info: 0
findings:
- id: A-1
  severity: medium
  category: inconsistency
  summary: "FR-006's 'no repair advice' rule and the legacy-shape line both mention `spec-kitty init`; the line names it as how to state a list, not as a repair. Wording is reviewed against FR-006 in T003."
- id: A-2
  severity: medium
  category: underspecification
  summary: "SC-002's 'byte-identical' proof needs a defined snapshot: assert the sorted (path, sha256) list of the command-skill roots and the skills manifest, not the whole tree, so an unrelated gitignored write cannot flake it."
- id: A-3
  severity: low
  category: coverage
  summary: "FR-005 widens the issue's three commands to include `doctor command-files`; same vacuous-health class, one print statement, documented in the spec Problem table row 6."
- id: A-4
  severity: low
  category: inconsistency
  summary: '`no_cli_managed_agents` is a negative predicate; a positive name plus a negation at each of three call sites would duplicate the condition. Recorded, no change.'
- id: A-5
  severity: low
  category: underspecification
  summary: "T005 says 'human output only' but `doctor skills --fix` can write; T001 pins a writes-nothing assertion for the stated-empty shape and T005 wording now says so."
---
# Analysis Report: plugin-owned-surfaces-report-truthfully-01M68JAV

Scope: consistency across `spec.md`, `plan.md`, `tasks.md` (1 WP) and the charter.
Run 2026-10-31 before implementation. Non-remediating pass.

## Summary

- Requirements: 7 FR, 3 NFR, 3 C, 4 SC. Tasks: 1 WP, 6 subtasks.
- Coverage: every FR/NFR/constraint is reachable from at least one subtask;
  no subtask maps to nothing (T006 carries NFR-001/NFR-002 verification and the
  changelog obligation).
- Findings: **2 MEDIUM, 3 LOW, 0 CRITICAL**. No charter violation.

## Findings

### A-1 (MEDIUM) — FR-006's "no repair advice" collides with the legacy branch wording

FR-006 forbids presenting `init` / `agent config add` as *the repair for a
problem*. The legacy shape (T003) legitimately wants to tell the reader that
`spec-kitty init` states the list. Fix in wording, not in requirement: the legacy
line says the CLI *treats every agent as available* and names `init` as the way to
state a list — it is not a repair for a broken project. T003 already words it that
way; recorded so the reviewer checks it explicitly.

### A-2 (MEDIUM) — SC-002's "byte-identical command-skill tree" needs a defined snapshot

`init --ai claude` also touches `.gitignore` (via `GitignoreManager.protect_all_agents`
only when it repairs) and `kitty-ops`-free surfaces. The assertion must snapshot the
set of files under the command-skill roots (`.agents/skills/`) plus the manifest
file, not the whole tree, or an unrelated gitignored write would flake it. Action
carried into T001: snapshot a sorted (path, sha256) list of the skill roots.

### A-3 (LOW) — `doctor command-files` truthfulness is not in the issue body

FR-005 adds `doctor command-files` to the three reported commands. It is the same
vacuous-health class, one print statement, and leaving it out would make the suite
inconsistent; recorded here so the reviewer sees the scope widening is deliberate
and spec-sanctioned (spec Problem table row 6).

### A-4 (LOW) — The predicate's name is a negative

`no_cli_managed_agents(config)` reads as a predicate about the project, which is
what callers need (`if no_cli_managed_agents(config):`). No change; recorded
because a positive name (`config.states_agent_list`) plus a negation at each call
site would put the same condition in three places.

### A-5 (LOW) — T005 says "human output only" but `doctor skills --fix` writes

`--fix` in the stated-empty shape must not install anything. T001 covers it with a
"writes nothing" assertion; T005's wording is corrected to say so explicitly.

## Coverage matrix

| Requirement | Subtasks |
| --- | --- |
| FR-001 | T002 |
| FR-002 | T003, T001 |
| FR-003 | T004, T001 |
| FR-004 | T004, T001 |
| FR-005 | T005, T001 |
| FR-006 | T003, T004, T005 (wording reviewed against FR-006) |
| FR-007 | T001 (ratchet), T004 |
| NFR-001 | T006 (no new I/O: predicate is a field read) |
| NFR-002 | T001 (JSON key set), T005 |
| NFR-003 | T001 (exit codes) |
| C-001 | T002 (no schema/probe), plan Risks |
| C-002 | T002 |
| C-003 | T003–T005 (one message per command) |
| SC-001..SC-004 | T001, T006 |

## Charter alignment

- Single canonical authority: one predicate, one message per command — pass.
- ATDD-first: T001 precedes T002–T005 in the WP — pass.
- User Customization Preservation: no mutating flow changed; `init --ai` in this
  shape writes nothing — pass.
- No ownership record invented (C-001) — pass; #6472 cited as the deferred owner.

## Verdict

Proceed to implementation. A-1/A-2 are wording/assertion details inside the WP;
A-3 scope widening is documented; A-4/A-5 are recorded, no action.

