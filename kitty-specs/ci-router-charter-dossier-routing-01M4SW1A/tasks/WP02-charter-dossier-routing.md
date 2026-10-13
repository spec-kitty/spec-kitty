---
work_package_id: WP02
title: Charter leg + dossier module + measured timings
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-6125-ci-router-charter-dossier-routing
merge_target_branch: issue-6125-ci-router-charter-dossier-routing
branch_strategy: Planning artifacts for this mission were generated on issue-6125-ci-router-charter-dossier-routing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6125-ci-router-charter-dossier-routing unless the human explicitly redirects the landing branch.
subtasks:
- T003
- T004
- T005
- T006
phase: Phase 2 - Routing change
history:
- at: '2026-10-13T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/release/ci_retirement_scrub.json
- .github/ci-module-registry.yml
- .github/workflows/ci-router.yml
- .github/ci-shard-timings.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Charter leg + dossier module + measured timings

## Objectives & Success Criteria

- `select_modules(manifest)` ⊇ `{charter, dossier}` for all four manifests (turns WP01 green).
- `dossier` is a real registry module with `test_dirs` `[tests/dossier, tests/specify_cli/dossier]`;
  a `src/specify_cli/dossier/**` edit routes to `dossier` without forcing run-all.
- Registry / scrub / router-filter stay **verbatim in lockstep** (NFR-001); the claim-once,
  bijection, verbatim, two-authority, and measured-timings guards are green.
- `.github/ci-shard-timings.json` carries a **real measured** `dossier` capture (FR-005).

## Context & Constraints

- Grounding + guard map: `research/code-grounding.md`. Flagged deviation from the brief recorded in
  `traces/design-decisions.md` (router verbatim guard forces the glob into scrub/registry roots too;
  the file-specific glob is harmless — the `ci` group precedent carries non-src roots).
- C-001 router verbatim: ordered-equal across all three authorities. C-002: file-specific glob only.
  C-003: no product code. NFR-002: no new size/length ratchet.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T003 – Charter leg (commit 1)

- **Purpose**: Make a manifest edit select the `charter` module.
- **Steps**: Append `packs/built-in/missions/**/expected-artifacts.yaml` (ordered, last) to the
  `charter` group `roots` in `tests/release/ci_retirement_scrub.json`, the `charter` row `roots` in
  `.github/ci-module-registry.yml`, and the `charter` filter group in
  `.github/workflows/ci-router.yml`.
- **Files**: the three authorities.

### Subtask T004 – Dossier scrub group + registry row + out-of-matrix release (commit 2)

- **Steps**:
  - `tests/release/ci_retirement_scrub.json`: add group `dossier`,
    `roots: ["src/specify_cli/dossier/**", "packs/built-in/missions/**/expected-artifacts.yaml"]`,
    `cov_targets: ["specify_cli.dossier"]`, `census_evidence: "known-live"`.
  - `.github/ci-module-registry.yml`: add the `dossier` row (roots/cov_targets **verbatim** from
    scrub, `tier: standard`, `test_dirs: [tests/dossier, tests/specify_cli/dossier]`, provisional
    `shard_count: 1`); remove `tests/dossier` and `tests/specify_cli/dossier` from
    `out_of_matrix_test_dirs`.

### Subtask T005 – Dossier router wiring (commit 2, with T004)

- **Steps** in `.github/workflows/ci-router.yml`: add the `dossier` filter group (globs **verbatim**
  the scrub roots); add the `dossier` `changes.outputs` line (same shape as peer src-backed groups);
  add `dossier` to the `unmatched` for-loop; OR `needs.changes.outputs.dossier == 'true'` into the
  `architectural-heavy` `if:`.

### Subtask T006 – Measured shard timings (commit 3)

- **Steps**: `python scripts/ci/capture_shard_timings.py --module dossier --write` (real serial
  capture); confirm `module_test_count[dossier] == len(module_test_durations[dossier])`; set the
  registry `shard_count` to the measured value so inter-shard skew ≤ 20% (shard_count 1 trivially
  passes). Commit the timings + the final `shard_count`.

## Test Strategy

- `make test-fast` + the specific named gates (NOT a `tests/architectural/` sweep):
  `test_gate_selection_authority.py`, `test_module_shard_registry.py`, `test_retirement_scrub.py`,
  `test_out_of_matrix_evidence.py`, `test_ci_router_transcription_guards.py`,
  `test_ci_quality_path_filters.py`, `test_ci_corpus_trigger_completeness.py`,
  `tests/ci/test_ci_module_wiring.py`, the WP01 parity gate, plus `tests/dossier` +
  `tests/specify_cli/dossier` (prove the newly-routed module green).
- `ruff check` + `ruff format --check --force-exclude` on changed files; mypy-clean new code.

## Risks & Mitigations

- Verbatim guard list-equality → ordered-append everywhere.
- Claim-once guard → remove the two dirs from `out_of_matrix_test_dirs` in the same commit.
- Shard-timings strict check → measured capture; the registry row must exist before capture runs.

## Review Guidance

- Verify the three authorities are byte-verbatim for `charter` and `dossier`; the dirs are claimed
  once; the parity gate is green; `tests/dossier` + `tests/specify_cli/dossier` pass; the timings are
  measured (provenance `producer == scripts/ci/capture_shard_timings.py`).

## Progress & Status

Progress/status live in `status.events.jsonl` (`spec-kitty agent tasks ...`).
