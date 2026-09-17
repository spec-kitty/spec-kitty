---
work_package_id: WP01
title: Startup config-read robustness and sibling folds
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-012
- NFR-002
- NFR-003
- NFR-005
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T20:20:10.083384+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Independent boundary foundations
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/bootstrap/test_cli_boundary_config_4600.py
execution_mode: code_change
owned_files:
- src/specify_cli/bootstrap/env_file.py
- src/charter/activation/consistency_check.py
- src/specify_cli/runtime/doctor.py
- src/specify_cli/core/worktree.py
- src/specify_cli/core/vcs/git.py
- src/specify_cli/core/git_ops.py
- tests/specify_cli/bootstrap/test_cli_boundary_config_4600.py
tags: []
tracker_refs:
- '#4600'
---

# Work Package Prompt: WP01 – Startup config-read robustness and sibling folds

## Objective

Preserve the operator's repair path when `.kittify/config.yaml` is unreadable. The earliest import-time pointer read must fail soft so `--version` and `doctor` can start, while the explicitly scoped sibling reads must produce controlled domain behavior rather than a raw decode traceback. This is the independently shippable P0 slice.

## Context and authoritative decisions

- Read `spec.md` US1, FR-001/FR-004, C-004/C-009, and the config-read entity in `data-model.md`.
- Decision 3 in `research.md` partitions behavior by **read site**, not by command allow-list.
- `bootstrap/env_file.py` must remain stdlib+kernel import-pure; never import CLI/Rich helpers there and never read `os.environ` at import time.
- The command layer owns actionable loud messages. The import-time pointer reader merely returns no value when bytes cannot decode.
- Fold only the sibling sites named in the plan. Do not absorb state-file robustness issues #4642/#4637.
- Follow ATDD: commit the failing acceptance test before implementation. The reviewer must be able to run it against the planning-base commit and see the original failure.

## Branch strategy

- Planning base: `fix/cli-boundary-robustness`
- Final merge target: `fix/cli-boundary-robustness`
- Runtime creates one worktree per computed lane from `lanes.json`; do not invent a manual branch or worktree.
- Start with: `spec-kitty agent action implement WP01 --agent <name>`

## Owned-file boundary

Modify only the files declared in frontmatter. The new issue-pinned test file is intentional. Do not edit mission planning artifacts, shared JSON code, or other tests. If an acceptance assertion truly requires another file, stop and request an ownership change rather than crossing lanes.

## Subtasks and detailed guidance

### T001 – RED: issue-pinned #4600 entry-point regressions

Create `tests/specify_cli/bootstrap/test_cli_boundary_config_4600.py` and drive the pre-existing CLI entry point in an initialized temporary project whose `.kittify/config.yaml` contains invalid UTF-8 bytes.

Cover at minimum:

- `spec-kitty --version` exits 0 and prints a version.
- `spec-kitty doctor` reaches a domain-level result instead of failing during import.
- No stream contains `Traceback`, `UnicodeDecodeError`, or an internal exception repr.
- A valid-config control still behaves as before.
- Mark the #4600 acceptance case with `@pytest.mark.regression` and include the issue number in its name/docstring.

Prove the test is red on the base mechanism before changing source. Avoid testing a private helper alone: the defect occurs before normal flag parsing, so the subprocess/installed-entry route is load-bearing.

### T002 – Fail soft at the import-time pointer read

In `src/specify_cli/bootstrap/env_file.py`, inspect the pointer-read site identified in the plan and widen the existing `OSError` guard to include `UnicodeDecodeError`, matching the nearby `_read_tier` precedent.

Required invariants:

- Invalid encoding returns the existing no-value/fallback outcome.
- No warning or actionable command prose is emitted from this import-time layer.
- Healthy UTF-8 parsing is unchanged.
- Imports remain within the existing bootstrap purity allowance.
- Do not replace the narrow tuple with `Exception` or catch YAML/domain errors unrelated to decoding.

### T003 – Harden scoped sibling config/version reads

Apply surgical guards at the two plan-owned sibling sites:

- `src/charter/activation/consistency_check.py`: contain unreadable/non-UTF-8 config-mapping loads and return the existing structured consistency outcome rather than raising.
- `runtime/doctor.py`: open the runtime version file with an explicit encoding and convert unreadable/decode failures into the doctor domain's existing finding/skip mechanism.

Add cases to the owned test file that exercise observable behavior where practical. Preserve the fail-loud command-layer responsibility: do not make genuine content-required reads silently look valid.

### T004 – Campsite encoding for git metadata

Add explicit `encoding="utf-8"` (and only the platform-safe error handling already prescribed by surrounding code) to the scoped text reads in:

- `core/worktree.py`
- `core/vcs/git.py`
- `core/git_ops.py`

This is a campsite fold, not a refactor. Do not restructure git resolution, alter subprocess behavior, or absorb path/traversal issue #2899.

### T005 – Healthy path and latency proof

Finish the acceptance matrix:

- Valid `.kittify/config.yaml` keeps `--version` and representative normal-command behavior unchanged.
- Typical valid-project startup/command completion is below the two-second NFR budget using a lightweight, non-flaky measurement with generous platform-aware setup exclusion.
- Bootstrap import-purity coverage remains green.
- No corrupt-config case emits a traceback.

Avoid asserting an unrealistically tight microbenchmark. The requirement is a gross regression guard, not nanosecond benchmarking.

## Test strategy

Run focused coverage first, then the relevant existing guards:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/bootstrap/test_cli_boundary_config_4600.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/bootstrap/ tests/charter/test_consistency_check.py tests/runtime/test_doctor_unit.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_bootstrap_import_purity.py -q
```

Before handoff also run Ruff on owned files and the repository-required format/type gates described in `quickstart.md` when practical.

## Definition of done

- #4600 red-first evidence exists through the real entry point.
- `--version` and `doctor` survive invalid UTF-8 configuration with no traceback.
- Scoped sibling reads cannot surface raw decode failures.
- Healthy behavior and the two-second budget are protected.
- No import-purity or owned-file violation occurred.
- Tests, Ruff, format, and relevant type checks are green.

## Risks and mitigations

- **Over-broad suppression**: only catch the byte/OS failures appropriate to each read site.
- **Layer inversion**: keep command messaging out of bootstrap.
- **Flaky performance assertion**: measure the intended command interval and use the charter's two-second threshold, not a tighter local observation.
- **Cross-platform decoding**: always pass an explicit encoding at newly touched text reads.

## Reviewer guidance

Review red-on-base/green-on-head evidence first. Then verify the import-time exception tuple is narrow, the test uses the CLI entry point, bootstrap imports did not expand, and sibling behavior reports domain outcomes rather than silently validating corrupt content.

## Acceptance matrix

| Read site / invocation | Invalid bytes | Expected exit/outcome | Forbidden outcome |
|---|---|---|---|
| import-time config pointer + `--version` | non-UTF-8 | exit 0, version visible | import traceback |
| import-time config pointer + `doctor` | non-UTF-8 | domain-level result | decode exception class |
| consistency config mapping | non-UTF-8/unreadable | structured check result | uncaught read error |
| runtime version lock | non-UTF-8/unreadable | doctor finding/skip | raw traceback |
| all scoped reads | valid UTF-8 | historical behavior | silent loss of data |

## Implementation evidence to retain

- The base commit/hash used to demonstrate the regression test failing.
- The failing assertion/trace showing the pre-fix import-time crash.
- The implementation commit where the same issue-pinned test turns green.
- Focused pytest command and result counts.
- Import-purity guard result.
- Measured valid-project command duration and what setup time was excluded.
- Ruff, format, and mypy outcomes for the final head.

## Explicit non-goals

- Do not classify commands into config-optional/config-required allow-lists.
- Do not change YAML schema validation or charter activation semantics.
- Do not repair malformed per-mission state files.
- Do not redesign git subprocess handling.
- Do not emit command UX from bootstrap.
- Do not add dependencies or change package versions.

## Self-review checklist

- [ ] The red-first test invokes the actual CLI boundary.
- [ ] The import-time catch is limited to `OSError` and `UnicodeDecodeError`.
- [ ] No new bootstrap transitive dependency was introduced.
- [ ] Every newly touched text read has an explicit encoding.
- [ ] Corrupt inputs never look like valid parsed configuration.
- [ ] No traceback or decode-class name appears to the operator.
- [ ] Healthy commands remain below the two-second budget.
- [ ] Only frontmatter-owned files changed.

## Activity log

### 2026-09-16 – Prompt generated

Six-package decomposition and owned-file boundary copied from the approved implementation plan.
