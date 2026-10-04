---
title: 'ADR: a Mission waives the contracts/ deliverable with a meta.json declaration'
description: 'Strict accept keeps contracts/ required unless meta.json declares "contracts": "none" with a non-empty contracts_rationale, read by one fail-closed helper.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-04'
---

**Status:** Accepted

**Date:** 2026-10-04

**Deciders:** Stijn Dejongh (owner). Operator triage ruling on #5298 (2026-09-28) and the waiver-shape ruling in the Mission brief (2026-10-04).

**Technical Story:** [#5298](https://github.com/spec-kitty/spec-kitty/issues/5298), Mission `friction-remediation-01M43DRV` (WP02). Parent [#2017](https://github.com/spec-kitty/spec-kitty/issues/2017).

---

## Context and Problem Statement

The software-dev Mission type declares `paths.deliverables: "contracts/"` in `packs/built-in/missions/software-dev/mission.yaml`. Strict `spec-kitty accept` turns a missing `contracts/` into a blocking path-convention violation (`acceptance/summary_core.py::evaluate_path_conventions`).

Many legitimate software-dev Missions define no interfaces: test remediation, refactors and docs-adjacent fixes. The operator ruled that roughly a third of Missions hit this. Their only escapes were:

- `accept --lenient`, which downgrades every path convention, not just this one;
- an empty `contracts/` placeholder, which #1892 called unintended.

The same file lists `contracts/` under `artifacts.optional`. That is a separate question (is the artifact expected to exist?) and does not settle whether the deliverable convention applies.

## Decision

A Mission declares that it defines no interface contracts in its `meta.json`:

```json
{
  "contracts": "none",
  "contracts_rationale": "Test-drift remediation; this Mission defines no interfaces."
}
```

- **One authority.** `specify_cli.core.paths.read_contracts_waiver_from_meta` is the only reader. It is a thin adapter over `load_meta_fail_closed`, like `read_retention_from_meta`. There is no spec-frontmatter or plan-frontmatter source, so no second, disagreeing declaration can exist.
- **Fail-closed.** Each of the following is NOT a waiver: any `contracts` value other than the exact string `"none"` (including `null`, booleans and other casing), and a missing, blank or non-string `contracts_rationale`. Such a declaration keeps the requirement in force and produces a warning naming the problem. A corrupt `meta.json` raises `MissionMetaReadError`, as every fail-closed meta read does.
- **Where it applies.** `evaluate_path_conventions` remains the only caller of `validate_mission_paths` (gated by `test_lifted_root_validate_mission_paths_single_caller.py`). It passes the waived token down as `waived_artifact_tokens`. The validator skips a declared path only when that path is a mission-artifact path. A build or repository path (`src/`, `tests/`, `docs/`) can never be waived.
- **Auditable.** An honoured waiver's rationale is surfaced in the accept warnings ("contracts/ requirement waived by meta.json (contracts: none): …"). A malformed waiver's warning is attached to the blocking violation text.
- The field is consulted only when `contracts` is both a declared path convention and a declared mission artifact (the case the validator can waive), so accept never claims a waiver it did not apply.

The fields are recorded in `MissionMetaOptional` (`src/specify_cli/mission_metadata.py`). The software-dev plan prompt (`packs/built-in/missions/mission-steps/software-dev/plan/prompt.md`) tells the planning agent to write the two fields when the Mission defines no interfaces. No CLI flag mints them yet.

## Considered Options

1. **Treat `deliverables` as satisfied when the artifact is declared optional.** Rejected by the operator ruling. It silently makes `contracts/` optional for every software-dev Mission, with no explicit, auditable statement that this Mission defines no interfaces.
2. **Per-Mission declaration in plan or spec frontmatter.** Rejected. A planning-document field would be a second source of truth beside `meta.json`, which already carries Mission-level policy flags (`retain_branches`, `commit_to_target`).
3. **Per-Mission declaration in `meta.json` (chosen).** Explicit and auditable, read by one helper, and consistent with the existing flat policy fields.

## Consequences

- A no-interface Mission passes strict `accept` without `--lenient` and without a placeholder directory.
- `contracts/` stays required by default; an unwaived or malformed Mission still blocks.
- A waived `contracts/` is also dropped from the "Optional artifacts missing" warning: the Mission declared it absent on purpose, and the waiver note already says so.
- **Follow-up candidate, not in scope:** a `mission create` / `setup-plan` flag to mint the waiver.
