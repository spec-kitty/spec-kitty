---
work_package_id: WP03
title: Oracle and contract tests on the bundle
dependencies:
- WP02
requirement_refs:
- FR-007
- NFR-005
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Consumers
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_payloads.py
- tests/contract/_mission_status_detail.py
- tests/contract/test_mission_status_payloads.py
- tests/contract/test_mission_status_detail.py
- tests/contract/test_mission_status_drift.py
- tests/contract/test_mission_status_ops.py
- tests/contract/test_mission_status_project.py
- tests/contract/test_mission_status_reality.py
- tests/contract/test_mission_status_artifacts.py
- tests/contract/test_mission_write_contract.py
- tests/architectural/test_scenario_contract.py
- scripts/ci/mission_status_corpus_compare.py
- tests/ci/test_mission_status_corpus_compare.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP03 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

The Python oracle (`tests/contract/_mission_status_*`), the mission-status and mission-write contract tests, the scenario contract and the nightly corpus script read the pinned `contract-bundles` and `contract-tools` instead of `contracts/`. Requirement: FR-007 (and FR-010 for the scenario contract tool). Decision D-5: `contract_resolver.resolve(bundle/<module>)` equals `resolve(contracts/<module>)` for both modules (verified at planning).

## Subtasks

### T011 — Oracle loading

- `_mission_status_payloads.py:554-563` `load_contract_tools(mp, repo_root)`: read the tools from `contract_tools_dir()` (WP02 reader). Keep the signature if callers pass `repo_root` (the corpus script does); add a `tools_root: Path | None = None` override instead of breaking it.
- `:112` reads `contracts/mission-status/schemas/WpId.yaml` (pattern, maxLength): read the `WpId`-titled node from the resolved bundle instead. Add one helper, e.g. `bundled_schema(title: str, module: str = "mission-status") -> dict` (resolve the bundle once, index by `title` like `_schema_nodes` does), in `_mission_status_payloads.py`.
- Every `Contract(tools, MODULE_DIR)` call site passes `contract_bundle_dir("mission-status")`.
- `_mission_status_detail.py:78` `_SCHEMAS` (RelativeReference, Workspace.properties, ReviewCycle.properties, ReviewVerdict.enum): use `bundled_schema`.

### T012 — Mission-status tests

For each file, replace `MODULE_DIR`/`SCHEMA_DIR`/`schemas/<X>.yaml` reads with `contract_bundle_dir(...)`/`bundled_schema(...)`:
- `test_mission_status_detail.py` :42, :103; `test_mission_status_drift.py` :48-49, :140, :1302 (DriftKind enum); `test_mission_status_ops.py` :40, :119, :1128 (OpsInvocation description); `test_mission_status_reality.py` :80, :173, :1066 (ReviewVerdict enum); `test_mission_status_artifacts.py` :269 (ArtifactPath maxLength), :290.
- `test_mission_status_project.py` :42-43, :474, :701, :746: **:701 reads the raw `Project.yaml`**, which differs from the inlined bundle node. Read what it asserts; if it asserts a property that survives inlining (e.g. required keys), assert it on the bundled node; if it asserts the source file shape itself, it tests the source layout → delete that one test and note it as a residual in the PR (D-6).
- `test_mission_status_payloads.py` :59, :858, :1090: `:1090` globs `examples/{title}.*.yaml`; switch to the schema node's `examples` list (the bundle keeps them, grounding §0). Make sure the test still validates each example and still fails on zero examples.
- Before each edit, run the file once (green baseline), after each edit run it again. Commit per file group.

### T013 — Mission-write contract

`test_mission_write_contract.py` :33-35, :54, :92, :295, :330:
- `MODULE_DIR` → `contract_bundle_dir("mission-write")`; tools → `contract_tools_dir()`.
- Examples read by file name (`:92`, `:295` `WriteRefusal.*.yaml`): re-key by schema title and index into the node's `examples` list. Keep `tests/contract/fixtures/mission_write_refusal_parity.yaml` (core-owned inventory) as is.
- `:330` reads `openapi.yaml` without the resolver and asserts six paths and `1.0.0-SNAPSHOT`; it passes on the bundle — keep it, point it at the bundle.

### T014 — Scenario contract [P]

`tests/architectural/test_scenario_contract.py:253` loads `contracts/tools/codeowners_check.py` → `contract_tools_dir() / "codeowners_check.py"`. Run the file.

### T015 — Corpus script [P]

- `scripts/ci/mission_status_corpus_compare.py`: the tools come from `tools_root or repo_root/contracts/tools` (`:315-328`). Add a CLI flag `--tools-root` (default: resolve via `scripts/sync_services.py`'s `extras_root(repo_root, "read-service", "contract_tools") / "contracts" / "tools"`; the script already bootstraps `sys.path` to the repo root). Keep the no-exemption rules (E-10) untouched.
- Extend `tests/ci/test_mission_status_corpus_compare.py` for the new flag and default (planted tools dir).
- Live proof: start the pinned binary (`$(python scripts/sync_services.py …)`; the native file is `cached_path` of the host asset — `make sync-services` first) with `--mission-status.project-root=$PWD --mission-status.port=8787`, run the script, expect `compared N Missions: … 0 rows not equal`, stop the process by PID. Record the line.

## Validation

```bash
uv run --frozen pytest tests/contract/test_mission_status_{payloads,detail,drift,ops,project,reality,artifacts}.py tests/contract/test_mission_write_contract.py tests/architectural/test_scenario_contract.py tests/ci/test_mission_status_corpus_compare.py -q -n 4 --dist loadfile
```
Then the same with `contracts/` moved aside (`mv contracts /tmp/contracts.bak`, keep `contracts/fixtures` in place), then restore. Ruff/format/mypy on changed files.

## Definition of Done
- No changed file reads `contracts/mission-*` or `contracts/tools`.
- Every assertion keeps its meaning (reviewer checks each re-keyed example loop still fails on empty input).
