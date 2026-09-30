---
title: 'Test Plan — PR #305 (feature/agent-profile-implementation)'
description: 'Test plan for PR #305 (agent-profile-implementation): the test scope, approach, and coverage targets recorded in a field-table format.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Per-PR review working note for PR #305 (agent-profile-implementation); the agent-profile system shipped as mission `045-agent-profile-system` (#136 / #1975). Content preserved as an audit-trail record.

# Test Plan — PR #305 (feature/agent-profile-implementation)

| Field | Value |
|---|---|
| PR | #305 |
| Branch | `feature/agent-profile-implementation` |
| Date | 2026-03-25 |
| Scope | Agent profile infrastructure, doctrine stack, kernel refactor, flag renames |

---

## 1. Automated test gate (run first)

Run the full suite and confirm no regressions before any manual steps.

```bash
rtk pytest tests/ -q --timeout=30
```

**Expected:** 0 failures. Known skips are acceptable. The following test modules
are the most directly relevant and must all pass:

| Test module | What it guards |
|---|---|
| `tests/specify_cli/cli/commands/test_bare_feature_flag.py` | No bare legacy alias flags anywhere in CLI/orchestrator/argparse surfaces |
| `tests/specify_cli/cli/commands/test_mission_flag_rename.py` | `--mission` slug selector present on all expected commands |
| `tests/specify_cli/cli/commands/test_mission_type_flag_rename.py` | `--mission-type` present on 5 type-selection commands; old `--mission` raises exit 1 |
| `tests/agent/test_json_envelope_contract_integration.py` | Orchestrator API envelope shape and USAGE_ERROR paths |
| `tests/doctrine/` (all) | Agent profile models, repository, schema validation, reference graph, cycle detection |
| `tests/kernel/` (all) | `kernel.paths`, `kernel.glossary_runner`, `kernel.glossary_types` zero-dep floor |
| `tests/specify_cli/cli/commands/` (all) | CLI command surface including mission.py current subcommand |
| `tests/specify_cli/scripts/` (all, if present) | tasks_cli.py argparse surface |

---

## 2. Flag rename — `--mission-type` (issue #241, group A)

Five commands had their mission-type selector flag renamed from `--mission` to
`--mission-type`. Verify each command individually.

### 2.1 Affected commands

| Command | How to invoke |
|---|---|
| `spec-kitty specify` | `spec-kitty specify --help` |
| `spec-kitty plan` | `spec-kitty plan --help` |
| `spec-kitty tasks` | `spec-kitty tasks --help` |
| `spec-kitty research` | `spec-kitty research --help` |
| (5th command — check `test_mission_type_flag_rename.py` for full list) | |

### 2.2 `--help` spot-checks

For each command, run `spec-kitty <cmd> --help` and verify:

- `--mission-type` appears in the option list
- `--mission` does **not** appear as a type-selector option (it should only appear as slug selector on other commands, not these)

### 2.3 Hard error on old `--mission` alias

```bash
spec-kitty specify --mission software-dev --name test-feature
```

**Expected:** exits non-zero with a clear error message stating `--mission` has
been renamed to `--mission-type`. Must NOT silently accept the old flag.

### 2.4 New flag works

```bash
spec-kitty specify --mission-type software-dev --help
# (or any other valid invocation with --mission-type)
```

**Expected:** accepted without error.

---

## 3. Flag rename — canonical `--mission` with hidden legacy alias (issue #241, group B)

All remaining CLI commands that previously used the legacy slug selector now
expose `--mission` as primary and keep the old alias hidden and deprecated.

### 3.1 `--help` does NOT show the legacy alias

For each of the following commands, run `<cmd> --help` and confirm the legacy
alias does **not** appear in the visible option list:

```bash
spec-kitty validate-tasks --help
spec-kitty mission current --help
spec-kitty orchestrator-api mission-state --help
spec-kitty orchestrator-api list-ready --help
spec-kitty orchestrator-api start-implementation --help
spec-kitty orchestrator-api start-review --help
spec-kitty orchestrator-api transition --help
spec-kitty orchestrator-api append-history --help
spec-kitty orchestrator-api accept-mission --help
spec-kitty orchestrator-api merge-mission --help
```

Also for the argparse surface (tasks_cli):
```bash
python -m specify_cli.scripts.tasks.tasks_cli status --help
python -m specify_cli.scripts.tasks.tasks_cli verify --help
python -m specify_cli.scripts.tasks.tasks_cli accept --help
python -m specify_cli.scripts.tasks.tasks_cli merge --help
```

**Expected for all:** legacy alias absent; `--mission` present.

### 3.2 Legacy alias still accepted (backward compat)

For any of the Typer commands above, exercise the hidden legacy alias via the
dedicated migration doc examples and confirm it behaves identically to
`--mission <slug>`. A `DeprecationWarning` may be emitted but the command must
not fail.

```bash
spec-kitty validate-tasks --mission 999-nonexistent 2>&1
# Expected: error about mission not found, NOT an "unknown option" error
```

### 3.3 `validate_tasks.py` body fix

This was a bug where `mission_slug_arg` (the resolved value from
`resolve_mission_or_feature`) was computed but the body used the raw `feature`
param. To verify the fix worked:

```bash
# From within a kitty-specs mission directory:
spec-kitty validate-tasks
# Expected: auto-detects the feature slug from cwd — does NOT crash or
# silently use None as the slug.
```

### 3.4 `mission current` command

```bash
spec-kitty mission current --help
# Expected: --mission (-m) present; --mission absent from visible output

spec-kitty mission current --mission <existing-slug>
# Expected: shows current mission for that feature slug

spec-kitty mission current --mission <existing-slug>
# Expected: same result as --mission (deprecated alias accepted)
```

### 3.5 tasks_cli argparse surface

```bash
# Verify --mission is the canonical flag:
python -m specify_cli.scripts.tasks.tasks_cli status --mission <slug>
python -m specify_cli.scripts.tasks.tasks_cli verify --mission <slug>

# Verify --mission still works as alias:
python -m specify_cli.scripts.tasks.tasks_cli status --mission <slug>
# Expected: identical behaviour to --mission
```

---

## 4. Orchestrator API — JSON envelope contract

### 4.1 Missing `--mission` returns structured USAGE_ERROR

```bash
spec-kitty orchestrator-api mission-state
```

**Expected JSON envelope:**
```json
{
  "success": false,
  "error_code": "USAGE_ERROR",
  "command": "orchestrator-api.mission-state",
  "data": { "message": "... --mission is required ..." }
}
```

Key assertions:
- `success` is `false`
- `error_code` is `"USAGE_ERROR"`
- `command` is `"orchestrator-api.mission-state"` (not `"unknown"` — command is now
  identified even when `--mission` is omitted, because the param is Optional)
- `data.message` contains `"--mission"`

### 4.2 Same check for `list-ready`

```bash
spec-kitty orchestrator-api list-ready
```

**Expected:** same envelope shape, `command` = `"orchestrator-api.list-ready"`.

### 4.3 `--mission` alias works on orchestrator API

```bash
spec-kitty orchestrator-api mission-state --mission <slug>
# Expected: same result as --mission <slug>
```

---

## 5. Kernel refactor — `kernel.paths` and `kernel.glossary_runner`

### 5.1 Backward-compat re-export shim

```python
# In a Python shell or quick script:
from specify_cli.runtime.home import get_kittify_home, get_package_asset_root
print(get_kittify_home())
print(get_package_asset_root())
```

**Expected:** both return valid `Path` objects without `ImportError`. The shim at
`specify_cli/runtime/home.py` must delegate to `kernel.paths` transparently.

### 5.2 Direct `kernel` imports work

```python
from kernel.paths import get_kittify_home, get_package_asset_root
from kernel.glossary_runner import register, get_runner, GlossaryRunnerProtocol
from kernel.glossary_types import GlossaryPrimitiveValue
```

**Expected:** all import cleanly. `kernel` has zero external dependencies — verify:

```bash
pip show kernel | grep Requires
# Expected: Requires: (empty or only stdlib)
```

### 5.3 No cross-boundary imports from `kernel`

```bash
rtk grep -r "from specify_cli" src/kernel/
rtk grep -r "from doctrine" src/kernel/
rtk grep -r "from charter" src/kernel/
```

**Expected:** zero results. `kernel` must import from nothing outside stdlib.

---

## 6. Agent profile infrastructure (WP02–WP08, feature 057)

### 6.1 Schema validation

```bash
rtk pytest tests/doctrine/test_agent_profile*.py -v
```

**Expected:** all pass. Validates that `agent-profile.schema.yaml` correctly
accepts valid profiles and rejects profiles with missing `purpose`, bad
`priority` values, etc.

### 6.2 Profile repository — shipped profiles exist

```python
from doctrine.agent_profiles.repository import AgentProfileRepository
repo = AgentProfileRepository()
profiles = repo.list()
assert len(profiles) == 7
names = {p.id for p in profiles}
assert names == {"architect", "curator", "designer", "implementer",
                 "planner", "researcher", "reviewer"}
```

### 6.3 Profile-aware resolver

```bash
rtk pytest tests/doctrine/test_profile_resolver*.py -v 2>/dev/null || \
rtk pytest tests/ -k "profile" -v --tb=short
```

**Expected:** tests covering profile injection into context resolution all pass.

### 6.4 `spec-kitty init` deploys agent profiles

In a temporary directory:
```bash
mkdir /tmp/test-sk-init && cd /tmp/test-sk-init && git init
spec-kitty init --ai claude --name "test-project"
ls .claude/commands/
```

**Expected:** command templates are present. Profile deployment does not break
init for any supported agent.

### 6.5 Agent profile suggestion in task templates

Check that WP task templates include agent profile role hints. Open any
generated WP file (e.g. `kitty-specs/<mission>/tasks/WP01-*.md`) after running
`spec-kitty tasks` and verify the template contains a profile suggestion line
(e.g. `Suggested agent profile: implementer`).

---

## 7. Charter defaults and init-time doctrine integration

### 7.1 Charter defaults injected at init

```bash
cd /tmp/test-sk-init  # from section 6.4 above
cat .kittify/charter/charter.yaml 2>/dev/null || \
    echo "not yet generated — run: spec-kitty charter generate"
spec-kitty charter generate
cat .kittify/charter/charter.yaml
```

**Expected:** file exists and contains valid governance YAML. No crash.

### 7.2 Charter context bootstrap works

```bash
spec-kitty charter context --action implement
```

**Expected:** outputs governance context text (depth-2 on first call).
Second call:
```bash
spec-kitty charter context --action implement
```
**Expected:** depth-1 (compact) output — shorter than first call.

---

## 8. Diamond dependency merge fix

This fix ensures that when merging a feature whose dependency graph has
diamond shapes (A→B, A→C, B→D, C→D), the ancestor-skipped WPs (D visited
twice) are correctly marked done rather than left in a wrong lane.

### 8.1 Automated coverage

```bash
rtk pytest tests/ -k "diamond" -v --tb=short
```

**Expected:** all diamond-related tests pass.

### 8.2 Manual smoke (if a diamond fixture is available)

If a test fixture with a diamond dependency graph exists:
```bash
spec-kitty agent tasks list-tasks --lane done
# After merge: all WPs that were skipped via the diamond path should be "done"
```

---

## 9. Critical bug fixes (C1, C2, C3)

### 9.1 C1 — kwarg mismatch

The original bug caused a `TypeError` at runtime when calling a function with
the wrong keyword argument name. Verify it's gone:

```bash
rtk pytest tests/ -k "C1 or kwarg" -v --tb=short 2>/dev/null
# Or: run the full test suite and confirm no TypeError tracebacks
```

### 9.2 C2 — variable reuse

A variable was being reused inside a conditional block, clobbering an outer
value. Verify via:

```bash
rtk pytest tests/ -k "C2 or variable_reuse" -v --tb=short 2>/dev/null
```

### 9.3 C3 — dashboard retry loop

The dashboard had an infinite retry loop on startup failure. Verify:

```bash
# Start dashboard in a directory without a valid project (should fail fast):
timeout 5 spec-kitty dashboard 2>&1 | head -5
# Expected: exits within 5 seconds with an error message, NOT an infinite loop
```

---

## 10. `--mission-type` hard error regression guard

This is the highest-risk flag rename. A user passing the old `--mission` flag on
a type-selection command MUST get a hard error, not a silent pass.

```bash
# Each of the 5 type-selection commands:
spec-kitty specify --mission software-dev 2>&1; echo "exit: $?"
```

**Expected:** `exit: 1` with an explicit error message. If any command exits 0
or silently ignores the flag, that is a regression.

---

## 11. Ruff / lint gate

No new lint violations introduced by this PR.

```bash
python -m ruff check src/ tests/
```

**Expected:** violation count must not exceed the count on `main`. All violations
in the diff are pre-existing (C901 complexity, B904 exception chaining — these
are tracked in `docs/development/linting-cutoff-policy.md`).

---

## Summary checklist

| # | Area | Automated | Manual |
|---|---|---|---|
| 2 | `--mission-type` rename (5 commands) | `test_mission_type_flag_rename.py` | `--help` + hard error check |
| 3 | canonical mission flag + hidden legacy alias (remaining commands) | `test_bare_feature_flag.py` + `test_mission_flag_rename.py` | `--help` + compat checks |
| 4 | Orchestrator API JSON envelope | `test_json_envelope_contract_integration.py` | Manual envelope shape check |
| 5 | Kernel refactor | `tests/kernel/` | Import smoke + zero-dep check |
| 6 | Agent profile infrastructure | `tests/doctrine/` | `spec-kitty init` + profile count |
| 7 | Charter defaults | `tests/charter/` | `charter generate` + `context` |
| 8 | Diamond dependency merge | `tests/` `-k diamond` | n/a if fixture present |
| 9 | C1/C2/C3 bug fixes | Covered in general test suite | Dashboard timeout check |
| 10 | `--mission-type` hard error guard | `test_mission_type_flag_rename.py` | Manual invocation |
| 11 | Lint gate | `ruff check` in CI | n/a |
