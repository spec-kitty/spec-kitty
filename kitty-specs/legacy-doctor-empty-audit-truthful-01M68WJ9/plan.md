# Implementation Plan: Legacy doctor audits report what they did not check

**Mission**: legacy-doctor-empty-audit-truthful-01M68WJ9
**Branch**: `issue-6891-legacy-doctor-empty-audit-truthful` (PR target `main`)
**Date**: 2026-10-31
**Spec**: `kitty-specs/legacy-doctor-empty-audit-truthful-01M68WJ9/spec.md`
**Research**: `kitty-specs/legacy-doctor-empty-audit-truthful-01M68WJ9/research.md`
**Issue**: #6891

## Summary

Two `doctor` summaries assert health over a surface set they never examined. In
a legacy project (`.kittify/config.yaml` with no `agents.available` list — the
#6501 every-agent fallback) the examined set is empty, because both audits
derive it from `config.available`:

- `doctor skills` → `Command Skills: all manifest entries healthy (0 file(s))`
- `doctor tool-surfaces` → `Tool Surfaces: all surfaces healthy (0 checked)`

The audits themselves are sound. The change is in the *summary*: when the
report is clean **and** nothing was examined, print the truth it can prove —
that the project states no agent list, so the CLI cannot tell which surfaces to
verify and nothing was checked — instead of a health claim. No exit code, no
`--json` key, no audit coverage and no repair behaviour changes.

## Technical Context

**Language/Version**: Python 3.11+ (repo `.python-version`), `from __future__ import annotations` style
**Primary Dependencies**: Typer + Rich (CLI surface), ruamel.yaml (`load_agent_config`), pytest
**Storage**: `.kittify/config.yaml` (read-only for this change); `.agents/skills` manifest untouched
**Testing**: `uv run pytest` with `CliRunner` on the real `doctor` app; `pytest.mark.unit`, `pytest.mark.fast`
**Target Platform**: any (pure CLI text path; no OS-specific behaviour)
**Project Type**: single project (`src/specify_cli/...`)
**Performance Goals**: zero added `load_agent_config` calls (baseline: `doctor skills` 3,
`doctor tool-surfaces` 1 — `research/load-counts.txt`)
**Constraints**: `--json` envelopes byte-identical in key set; exit-code contract
(`0` ok / `1` issues / `2` not-in-project or bad config) unchanged; no new CLI flags
**Scale/Scope**: one module (`src/specify_cli/cli/commands/_command_surface_doctor.py`),
one new test module, one changelog line, one doc sentence if a doc describes the summary

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Evidence |
| --- | --- | --- |
| ATDD-first / red-first through the pre-existing entry point (DIRECTIVE_034) | PASS | Both defects get a failing `CliRunner` test on `doctor skills` / `doctor tool-surfaces` before any source edit; transcript kept under `research/red-first-run.txt` |
| Traceability (every FR named by a WP) | PASS | WP01 declares FR-001…FR-006, SC-001…SC-004 |
| No full heavy suite in-mission (`NO_FULL_HEAVY_SUITES_IN_MISSION`) | PASS | Scoped test modules only; the PR's CI runs the full gate |
| No fake green | PASS | Exit codes untouched; no test skipped or relaxed; pre-existing reds (#6798, #6801, #6816, #5927) cited, not silenced |
| Development-assist test cleanup | PASS | No characterization or parity scaffolding is added: two behaviour tests plus one positive control, all guarding the standing "no health claim over zero examined surfaces" invariant |
| One source of truth | PASS | The empty-examined decision reads `AgentConfig.explicit_agent_list` and reuses the config the command already loaded; no second predicate, no second YAML read |
| Code rules (CC ≤ 15, one-way imports, no dead public symbols) | PASS | One new module-private helper; no public surface added, so nothing to add to `__all__` |

Post-Phase-1 re-check: unchanged (the design adds no new module, dependency, or
public symbol).

## Project Structure

### Documentation (this mission)

```
kitty-specs/legacy-doctor-empty-audit-truthful-01M68WJ9/
├── spec.md              # this mission's specification
├── plan.md              # this file
├── research.md          # grounding + code survey
├── research/            # repro transcripts, load counts, red-first run
├── tasks.md             # created by `spec-kitty tasks`
├── tasks/WP01-*.md
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/
├── _command_surface_doctor.py     # the only source file this mission edits
├── doctor.py                      # unchanged shells (delegates to the above)
└── _doctor_shared.py              # unchanged (console, resolve helpers)

tests/specify_cli/cli/commands/
├── test_doctor_legacy_no_agent_list_reports.py   # NEW: red-first + positive control
├── test_doctor_skills.py                         # existing harness (read, not edited)
└── test_doctor_cli_surface_golden.py             # existing contract pin (must stay green)

docs/
├── changelog/CHANGELOG.md         # [Unreleased] entry (#6891)
└── ...                            # only a page that documents the summary text, if any
```

**Structure Decision**: single project, single module. The change lives entirely
in the command-surface doctor cluster extracted by #2059; no new module, no new
public symbol, no import-direction change.

## Design

### The one decision: "the examined set is empty, and why"

```
examined == 0 ?
├─ no  → existing summary (healthy line with N>0, or the findings report)
└─ yes → was the emptiness caused by a stated agent list?
         ├─ no (legacy, explicit_agent_list == False) → truthful line, named by THIS mission
         └─ yes (stated empty)                          → #6493 / PR #6894's line
```

The "examined" predicates already exist and are not being redefined:

| Command | `examined == 0` means | Where it is already true |
| --- | --- | --- |
| `doctor skills` | report clean **and** `len(manifest.entries) == 0` (any on-disk leftover sets `ok=False`) | `_command_skill_payload` builds `ok`; `_assemble_skills_payload` finalizes it |
| `doctor tool-surfaces` | `report.summary.surfaces == 0` and no findings (i.e. `report.ok`) | `_print_tool_surface_human` already has both |

### Plumbing (no new config read)

- `_load_command_skill_state` already loads the `AgentConfig`; extend its
  returned state with that same `config` object (7th element) instead of
  re-loading. `_SkillState` grows the element; `_assemble_skills_payload`
  unpacks it.
- `_configured_tool_keys_or_exit` loads the config for `doctor tool-surfaces`;
  add a sibling that returns the config (keeping `_configured_tool_keys` for
  `_tool_folder_findings`), so `run_tool_surfaces_audit` passes
  `stated_agent_list` to `_print_tool_surface_human`.
- A `load_agent_config` call-count test pins the recorded baseline
  (`skills` 3, `tool-surfaces` 1).

### Wording (single definition, shared by both commands)

Summary line (subject differs, rest is one constant):

```
Command Skills: no stated agent list (every agent is available) — nothing to check
  ! 0 manifest entries and no agent surface were examined. .kittify/config.yaml states no
    agents.available list, so the CLI cannot tell which surfaces to verify.
```

```
Tool Surfaces: no stated agent list (every agent is available) — nothing to check
  ! 0 surfaces were examined. .kittify/config.yaml states no agents.available list, so the
    CLI cannot tell which surfaces to verify.
```

Rules the wording obeys (C-002): it names the state and the gap, prescribes no
install, and never says `healthy`. Colour is yellow, not green — the line is a
qualification of the audit, not a pass.

The skills payload carries the reason under a **human-only** key added to
`_HUMAN_ONLY_KEYS`, so `--json` keys stay exactly as they are today.

### Why not widen the audit

Widening to the every-agent fallback would have `doctor skills` report ~20
uninstalled agents and `doctor tool-surfaces` ~20 uninstalled tools on a project
that legitimately uses one; that trades a false green for a false red, and
claims a fact (which surfaces this checkout should own) that only #6472's
ownership record can establish. Named in the spec's Resolved Decisions.

### Overlap with open PR #6894 (#6493)

Same file, same two summary functions, adjacent branches. Mitigation: no new
predicate (reuse `explicit_agent_list`), no `--json` churn, no re-decision of
the stated-empty shape, and the state tuple grows the same `config` element the
sibling PR adds, so the second merge resolves text, not semantics.

## Complexity Tracking

No charter violations. The only added complexity is one module-private helper
and one test module; nothing is justified here because nothing is being waived.

## Implementation Concern Map

### IC-01 — Empty-examined summaries in the command-surface doctor cluster

- **Purpose**: Make the two summaries that today claim health over zero examined
  surfaces name the legacy no-agent-list state and the fact that nothing was
  checked, without changing coverage, exit codes or the JSON contract.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006,
  NFR-001, NFR-002, NFR-003, C-001, C-002, C-005
- **Affected surfaces**: `src/specify_cli/cli/commands/_command_surface_doctor.py`
  (`_print_command_skill_report`, `_assemble_skills_payload`,
  `_command_skill_payload`, `_SkillState`, `_load_command_skill_state`,
  `_configured_tool_keys*`, `run_tool_surfaces_audit`,
  `_print_tool_surface_human`, `_HUMAN_ONLY_KEYS`);
  `tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py` (new);
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none
- **Risks**: (1) the truthful line must not swallow a real finding — every test
  pairs the empty-examined assertion with a positive control on the same fixture
  (stated list, installed skills, real gap); (2) `_assemble_skills_payload` sets
  `ok` twice (command-skill payload, then the fused slash/pack/tool gate) — the
  note must be attached only after the final `ok`, or a project with a real
  slash-command gap could lose its findings to a "nothing to check" line;
  (3) `doctor skills --fix` must not claim a repair; (4) `#6894` overlap above.
