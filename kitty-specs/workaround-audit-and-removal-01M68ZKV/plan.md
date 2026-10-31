# Implementation Plan: Audit and remove special-case workarounds

**Branch**: `issue-6745-workaround-audit-and-removal` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/workaround-audit-and-removal-01M68ZKV/spec.md`
**Input**: Mission specification from `kitty-specs/workaround-audit-and-removal-01M68ZKV/spec.md`, grounded in `research.md` (§4 ledger, §5 decisions).

## Summary

Issue #6745 asks for a written audit method plus a disposition per suspect, so the
"just make it work" bias stops recurring. This Mission delivers the method and the
disposition ledger as one developer-docs page, and — per the operator's extension —
removes a bounded, well-evidenced pair of workarounds in the same PR: one
*workaround for a missing seam* (a byte-identical `DiscoveryContext` constructor kept
alive because the runtime builder was private) and one *workaround for a test double*
(the composition reading its executor result through `getattr` defaults and a length
tolerance). Everything else the audit confirmed stays out of this PR with a named
reason, and the two confirmed workarounds that need an operator decision or a larger
refactor get child issues.

## Technical Context

**Language/Version**: Python 3.11 (repo `pyproject.toml`, `requires-python >=3.11`)
**Primary Dependencies**: stdlib + pydantic v2 (`DiscoveryContext` is a `BaseModel`), pytest, ruff, mypy; no new dependency
**Storage**: N/A (filesystem only: `packs/`, `kitty-specs/`, `.kittify/`)
**Testing**: pytest. Focused suites only (charter `NO_FULL_HEAVY_SUITES_IN_MISSION`): `tests/runtime/test_bridge_io.py`, `tests/specify_cli/next/test_runtime_bridge_composition.py`, `tests/integration/test_mission_run_command.py`, plus the architectural seam tests that pin the io cluster's names.
**Target Platform**: Linux/macOS CLI (`spec-kitty`), and the packaged wheel
**Project Type**: single project — `src/runtime/**` (runtime) and `src/specify_cli/**` (CLI)
**Performance Goals**: no runtime cost change; the change removes two function calls' worth of duplication and one `getattr` chain
**Constraints**: no behaviour change on the canonical path; `OrgPackSubdirEscapeError` / `OrgPackEnvVarUnsetError` must still propagate from discovery (DEC-005/NFR-001 of `up-org-template-fsm-01M06F9K`); no new tolerance, no new gate, no new doctrine in `packs/built-in/`
**Scale/Scope**: ~6 production files, ~4 test files, 1 new docs page, 1 changelog entry; well under the 200-line bound in NFR-004

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | IC-01 leaves one `DiscoveryContext` builder; IC-02 leaves one reader of `StepContractExecutionResult`. Both remove a second authority rather than adding one. |
| Standing Order #2 (campsite cleaning) | The removals are in the surfaces the mission touches; no drive-by refactor outside them. |
| Standing Order #5 (architectural gate discipline, prefer empty allowlist) | No baseline entry is added or grown. No new gate: the existing seam non-vacuity list gains the renamed public name. |
| Standing Order #6 (canonical sources) | The audit page cites file:line and issue evidence; it does not restate doctrine. |
| DIRECTIVE_024 (locality of change) | Rename in place, delete in place; no module moves. |
| DIRECTIVE_025 (Boy Scout) | The two deleted workarounds are the tidy-first work of this mission. |
| ATDD-first / DIRECTIVE_034 (test-first bug fixing) | The only behaviour-adjacent change (IC-02) rewrites its pinning test in the same commit; the seam test for IC-01 is written before the deletion. |
| DIRECTIVE_041 (test only for real behaviour) | One new assertion (the loader observes the seam) and one rewritten test; no test deleted. |
| Doctrine pack tiers | The audit page is a developer doc; the proposed process guard is filed as a tracker issue for the operator, never added to `packs/built-in/` (C-004). |
| Pre-existing Failure Reporting Rule | #6798, #6801, #6816, #5927 are cited in the PR's `## Deferred` as reds outside this diff. |

No violations; **Complexity Tracking** is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/workaround-audit-and-removal-01M68ZKV/
├── plan.md              # This file
├── research.md          # Phase 0 (discovery + plan extension)
├── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created here)
└── (no data-model.md, contracts/, quickstart.md: a refactor with no data model,
     no external interface, and no runnable quickstart beyond the focused suites —
     recorded as `"contracts": "none"` + `contracts_rationale` in meta.json)
```

### Source Code (repository root)

```
src/
├── runtime/next/
│   ├── runtime_bridge_io.py            # IC-01: the one public discovery-context builder
│   └── runtime_bridge_composition.py   # IC-02: read the executor result contract directly
└── specify_cli/
    ├── mission_loader/command.py       # IC-01: delete the duplicate constructor
    └── (unchanged) ownership/validation.py, lanes/implement_support.py — child issues

tests/
├── runtime/test_bridge_io.py                       # IC-01: seam name + patch-point test
├── specify_cli/next/test_runtime_bridge_composition.py  # IC-02: contract assertion
└── integration/test_mission_run_command.py         # IC-01: unchanged (still green)

docs/
├── development/how-to/auditing-special-case-workarounds.md  # the audit method + ledger
├── development/how-to/index.md                              # index row
└── changelog/CHANGELOG.md                                   # [Unreleased] entry
```

**Structure Decision**: single project. The change stays inside the two existing
packages that already own these seams (`src/runtime/next/**` for the bridge, io seam and
composition; `src/specify_cli/mission_loader/**` for the `mission run` CLI), plus the
developer-docs tree.

## Complexity Tracking

Empty — no charter violation to justify.

## Implementation Concern Map

### IC-01 — One public builder for the runtime discovery context

- **Purpose**: Delete the duplicated `DiscoveryContext` constructor in the mission
  loader and publish the runtime's builder instead, so the org tier (and anything else
  added to the context) is wired once and cannot be wired into one copy and missed in
  the other.
- **Relevant requirements**: FR-004, FR-005, NFR-002.
- **Affected surfaces**: `src/runtime/next/runtime_bridge_io.py` (`_build_discovery_context`
  → public `build_discovery_context`; its internal callers at `:648,:705,:767,:815`),
  `src/specify_cli/mission_loader/command.py` (delete `_build_discovery_context`, import
  the seam; update the two docstring references at `:98` and `:102`),
  `tests/runtime/test_bridge_io.py` (`_SEAM_OWNED_NAMES` and the four
  `_build_discovery_context` tests, plus one new patch-point test).
- **Sequencing/depends-on**: none.
- **Risks**: the seam-owned-name list is itself the non-vacuity pin for an
  architecture gate (`tests/runtime/test_bridge_no_compat_delegates.py` pins that the
  bridge keeps no forwarder) — the rename must update the list in the same commit or
  that gate fails loudly (which is the desired failure). The move must not wrap
  `resolve_pack_chain` in a `try/except` (DEC-005). `DiscoveryContext` stays imported in
  the loader for the `discovery_context=` parameter type.

### IC-02 — Composition reads the executor contract instead of tolerating doubles

- **Purpose**: Remove the `getattr` defaults and the `len()` tolerance that exist only
  so `MagicMock` results flow through, and rewrite the test that pins the tolerance so
  no test keeps it alive.
- **Relevant requirements**: FR-006, FR-007, NFR-001.
- **Affected surfaces**: `src/runtime/next/runtime_bridge_composition.py:615-645`;
  `tests/specify_cli/next/test_runtime_bridge_composition.py`
  (`test_dispatch_handles_non_sized_invocation_ids_and_returns_guard_failures` at
  `:641-676`, and the two comment blocks that explain the removed rationale).
- **Sequencing/depends-on**: none (independent of IC-01; different modules).
- **Risks**: the rewritten test must keep its guard-failure coverage (it asserts a
  guard failure is *returned* while the invocation chain is logged); only the
  `object()`-shaped premise changes. All other fakes in that file already set real
  `invocation_ids` tuples and stay green.

### IC-03 — The audit method and its ledger on one docs page

- **Purpose**: Make the audit repeatable and auditable: heuristics, time-box, the four
  classifications, and a disposition row per suspect (issue #6745's six, plus the four
  the audit added), each with an evidence pointer and either "removed here" or a child
  issue number.
- **Relevant requirements**: FR-001, FR-002, FR-003, C-002, C-004.
- **Affected surfaces**: new `docs/development/how-to/auditing-special-case-workarounds.md`;
  `docs/development/how-to/index.md` (add the row); `docs/changelog/CHANGELOG.md`.
- **Sequencing/depends-on**: can be written first (it is the ledger that motivates
  IC-01/IC-02) but its "removed here" rows must match what actually lands, so it is
  finalised after IC-01/IC-02.
- **Risks**: `docs/development/how-to/index.md` regeneration must not be done with the
  full `docs/api/cli-commands.md` rebuild (shared machine state); only
  `scripts.docs.check_docs_freshness --ci` and the docs index write for this tree.
