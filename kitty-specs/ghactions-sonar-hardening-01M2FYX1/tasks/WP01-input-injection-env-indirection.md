---
work_package_id: WP01
title: S7630 input-injection env-indirection in module-tests.yml
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- NFR-003
planning_base_branch: fix/ghactions-sonar-hardening
merge_target_branch: fix/ghactions-sonar-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/ghactions-sonar-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ghactions-sonar-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ghactions-sonar-hardening-01M2FYX1
base_commit: 74574b3421f2c725a406b51f1506202e39bc9f7e
created_at: '2026-09-14T12:50:43.090370+00:00'
subtasks:
- T001
- T002
history:
- created by /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/module-tests.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load your profile before anything else: `spec-kitty agent profile show implementer-ivan`.

## Objective
Close the S7630 script-injection class in `.github/workflows/module-tests.yml` (9 findings) by
routing every `${{ inputs.* }}` interpolation that currently appears inside a `run:` block through
a step-level `env:` variable referenced as `"$VAR"` — **behavior-identical** (FR-001, NFR-001).

## Context
Sonar S7630: "inputs.X is vulnerable to script injection: values of inputs are provided by whoever
triggers the workflow." The fix pattern (GitHub's own guidance):
```yaml
      - name: ...
        env:
          SHARD: ${{ inputs.shard }}
        run: |
          echo "$SHARD"        # was: echo "${{ inputs.shard }}"
```
The interpolation moves from the shell body (where it is injectable) into `env:` (where it is a
plain value). The command, args, and result are unchanged.

## Guidance per subtask
### T001 — Convert all 9 S7630 sites
- Pull the exact lines: `curl -s "https://sonarcloud.io/api/issues/search?componentKeys=spec-kitty_spec-kitty&rules=githubactions:S7630&resolved=false&ps=200" | python3 -c "import sys,json;[print(i['component'].split(':')[-1], i.get('line'), '::', i['message']) for i in json.load(sys.stdin)['issues'] if 'module-tests' in i['component']]"`
- For each, add an `env:` mapping to the owning step and replace the in-`run:` `${{ inputs.X }}` with `"$UPPER_VAR"`.
- **JSON-argv trap**: `inputs.test_dirs` and `inputs.cov_target` feed a heredoc `python3 -c`/`python3 - <<PY` script as argv. Round-trip through `env:` so JSON quoting survives — verify the arg still parses (the bin-packing/coverage split must be unchanged). Prefer passing via `env:` and reading `os.environ` in the script when the value is consumed by Python, rather than shell-interpolating into argv.
### T002 — Validate
- `actionlint .github/workflows/module-tests.yml` (or `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/module-tests.yml'))"`) clean.
- Diff-review: confirm each edit is behavior-identical (same command executed, same arg values). No new steps, no changed conditions.

## Branch Strategy
Planning/base + merge target: `fix/ghactions-sonar-hardening`. Enter the resolved lane workspace from lanes.json.

## Definition of Done
- All 9 S7630 module-tests.yml sites use `env:`-indirection (FR-001); YAML valid (NFR-003); behavior-identical (NFR-001); no edits outside module-tests.yml.

## Risks / reviewer guidance
- **Reviewer**: confirm every converted site runs the SAME command with the SAME value; the JSON-argv sites (`test_dirs`, `cov_target`) must still parse — this is the top trap.
