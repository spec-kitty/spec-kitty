---
work_package_id: WP06
title: Structural enumeration and placeholder guards
dependencies:
- WP03
- WP04
- WP05
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-004
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 325aa2113f0903c6d020aa4e2dacfa539db21d70
created_at: '2026-09-16T21:45:42.268339+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
- T031
phase: Phase 3 - Class-closure gates
history:
- at: '2026-09-16T20:02:57Z'
  actor: codex
  action: Prompt generated via mission tasks workflow
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_cli_boundary_contract_enumeration.py
execution_mode: code_change
owned_files:
- tests/architectural/test_cli_boundary_contract_enumeration.py
tags: []
tracker_refs:
- '#4532'
- '#4533'
- '#4597'
- '#4598'
- '#4600'
- '#4601'
- '#4643'
- '#4646'
---

# Work Package Prompt: WP06 – Structural enumeration and placeholder guards

## Objective

Turn the mission’s fixes into durable class guards: structurally enumerate `--json` Typer options, enforce parseability for the explicit allow-list and canonical shape for adopted commands, cover empty-success fixtures, and prove that none of the five bare callbacks leaks framework placeholder objects.

## Context and authoritative decisions

- Read `contracts/enumeration-gate-contract.md` and post-plan Amendment B before coding.
- First action is discovery/triage, not writing a guessed allow-list.
- Discover options structurally through the Typer app tree; parameter-name grep is insufficient.
- Classifications are exactly: `adopted-shape`, `already-parseable`, `non-parseable-deferred`.
- Parse allow-list is adopted plus verified-already-parseable. Known non-parseable surfaces such as events are recorded and excluded so this bounded mission can finish deterministically.
- Adopted error drivers additionally enforce canonical shape and exit fidelity.
- Empty drivers are an explicit extensible fixture list.
- The placeholder guard is behavioral/output-based over all five `invoke_without_command=True` callbacks; do not add an AST binding-style rule.

## Branch strategy

- Planning base / final merge target: `fix/cli-boundary-robustness`.
- This is a terminal lane after WP03, WP04, and WP05; runtime resolves the worktree from `lanes.json`.
- Start with: `spec-kitty agent action implement WP06 --agent <name>`
- WP01 has disjoint ownership but its outcomes are included in final mission verification.

## Owned-file boundary

Create only `tests/architectural/test_cli_boundary_contract_enumeration.py`. The plan allowed extending the existing console-seam gate **or** adding a new file; this package chooses the new file to keep ownership disjoint. Do not edit source to make the gate pass—reject upstream WPs with precise evidence instead.

## Subtasks and detailed guidance

### T026 – Structural discovery and triage

Walk the real Typer application/registered command tree. Identify any boolean option whose declaration exposes the `--json` flag, independent of whether its Python parameter is named `json_output`, `output_json`, or `json`.

Build reviewable discovery records containing enough identity to drive the command (command path, callback, option metadata). Classify the live surface by actually probing error behavior where deterministic.

Requirements:

- aliases/registrations are not silently collapsed when their behavior differs;
- a new structurally discovered command cannot disappear from the audit;
- discovery does not rely solely on source text or file naming;
- test diagnostics print a useful command identity.

### T027 – Parse allow-list and adopted-shape error gate

Encode explicit, reviewed classification data in the test module. For each parse-allow-list command, use a deterministic outside-project or equivalent generic error driver and assert `json.loads(stdout)` succeeds.

For adopted commands from WP03–WP05 additionally assert:

- object with `ok is False`;
- `error` is an object;
- non-empty string `code` and `message`;
- no extra prose in stdout;
- JSON exit equals the paired non-JSON condition.

Do not demand the canonical shape of verified legacy commands this mission did not adopt.

### T028 – Empty-path fixture gate

Create an explicit, data-driven, extensible fixture list for meaningful empty paths, beginning with agent task status on a zero-WP mission. Each case specifies setup, invocation, and expected empty collection fields/shape.

Assert:

- exit 0;
- raw stdout parseability;
- command-normal success payload with empty collections;
- no `error` key;
- no prose contamination or traceback.

Keep setup isolated and deterministic; avoid network, user home, or global repository dependence.

### T029 – Five-callback placeholder guard

Parameterize public no-subcommand invocations corresponding to:

- root `__init__.py` callback;
- both `migrate_cmd.py` invoke-without-command callbacks;
- `context.py`;
- `charter/list_cmd.py`.

Assert combined stdout/stderr contains none of `OptionInfo`, `ArgumentInfo`, `typer.models.OptionInfo`, object repr fragments, or equivalent sentinel leakage. Provide the minimum valid fixture/context each callback needs to reach observable behavior.

This is behavioral. Do not inspect AST/default syntax and do not forbid safe `Annotated[...] = <real default>` declarations.

### T030 – Deferred classification and diagnostics

Represent known non-parseable commands explicitly with rationale/follow-up identity so reviewers can distinguish bounded deferral from accidental omission. The gate should fail usefully when:

- a newly discovered command lacks classification;
- an allow-listed command stops parsing;
- an adopted command changes envelope shape;
- a deferred classification no longer matches discovery identity.

Do not auto-add new commands to the deferred set. A human must triage them.

### T031 – Mission-wide verification

After the architectural file is green, run the mission’s combined gates:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_cli_boundary_contract_enumeration.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_cli_console_single_seam.py -q
make test-fast
ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy -p specify_cli
pytest tests/architectural/test_no_legacy_terminology.py
```

Also re-run the issue-pinned files from WP01 and WP03–WP05. Record counts and any environment-only skip clearly.

## Test design guidance

- Prefer immutable dataclass/tuple case records over many ad hoc tests.
- Keep command-specific fixture setup in named factories so failures identify the contract arm.
- Use raw `result.stdout` for JSON parsing; do not strip prose into validity.
- Compare non-JSON/JSON exit codes from paired invocations rather than a global expected value.
- Prevent test collection from mutating the real environment or requiring an installed user config.

## Definition of done

- Structural discovery covers every registered boolean `--json` option.
- Every discovered command has an explicit classification.
- Parse allow-list is 100% parseable on driven cases.
- Adopted commands satisfy canonical error shape, streams, and paired exit codes.
- Empty fixtures are valid success payloads at exit zero.
- All five invoke-without-command callbacks are free of placeholder repr.
- Full mission quality gates pass without source changes in this WP.

## Risks and mitigations

- **Brittle command bootstrapping**: centralize fixture factories and use actual app registration.
- **False universal claim**: enforce the ratified allow-list boundary and keep deferred cases visible.
- **Alias undercount**: key records by public command path, not callback object alone.
- **Permanent red gate**: triage live behavior first; never include known unowned failures in the allow-list.
- **Silent scope creep**: this test-only WP reports upstream defects rather than fixing source.

## Reviewer guidance

Start by reviewing discovery coverage and the classification diff. Confirm deferred cases are explicit, not broad patterns. Verify adopted versus parse-only assertions differ correctly, empty status has no error key, exit codes are paired rather than hard-coded, and all five callback families are present.

## Classification record requirements

Each public command-path record should make review possible without reading discovery internals:

- public command tuple/path;
- resolved callback identity;
- discovered `--json` option metadata;
- classification;
- error-driver factory identifier;
- whether canonical adopted shape is required;
- optional empty-driver factory;
- deferred rationale/follow-up identity when excluded.

## Gate behavior matrix

| Classification | Discovered | Parse error arm | Canonical shape | Empty arm |
|---|---:|---:|---:|---:|
| adopted-shape | yes | required | required | when fixture listed |
| already-parseable | yes | required | not required | when fixture listed |
| non-parseable-deferred | yes | explicitly excluded | not required | not required unless separately verified |
| unclassified new command | yes | gate fails for triage | n/a | n/a |

## Failure-message quality

A failing parameter must state:

- public command path;
- classification;
- driven condition;
- exit code;
- raw stdout excerpt;
- stderr excerpt when relevant;
- whether failure was parse, shape, stream, exit, or discovery drift.

This is essential because one gate may cover dozens of registrations.

## Evidence to retain

- Count of structurally discovered public command paths.
- Count in each classification.
- Explicit list of deferred paths and linked follow-up.
- Count of adopted error drivers and empty fixtures.
- Five callback case identities.
- Full architectural, fast-suite, Ruff, format, mypy, and terminology results.

## Self-review checklist

- [ ] Discovery inspects Typer option declarations, not names alone.
- [ ] Aliases are keyed by public path.
- [ ] No newly discovered path is auto-deferred.
- [ ] Parse-only legacy cases are not shape-policed.
- [ ] Adopted cases compare paired exit codes.
- [ ] Empty cases require success data without `error`.
- [ ] All five callback families are present.
- [ ] The WP changed no source file.

## Activity log

### 2026-09-16 – Prompt generated

Post-plan Amendment B is encoded as the first subtask and as a deterministic classification contract.
