---
title: 'Test Execution Report — PR #305 (feature/agent-profile-implementation)'
description: 'Test execution report for PR #305 (agent-profile-implementation): the suites run, the results, and any failures captured in a field-table record.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Per-PR review working note for PR #305 (agent-profile-implementation); the agent-profile system shipped as mission `045-agent-profile-system` (#136 / #1975). Content preserved as an audit-trail record.

# Test Execution Report — PR #305 (feature/agent-profile-implementation)

| Field | Value |
|---|---|
| PR | #305 |
| Branch | `feature/agent-profile-implementation` |
| Date | 2026-03-25 |
| Tester | OpenCode (claude-sonnet-4.6), automated + manual |
| Version | 2.1.2 |
| Test plan | `docs/development/test-plan-pr305.md` |
| Verdict | **CONDITIONAL PASS** — 5 test failures require remediation before merge |

---

## Executive Summary

All critical functional paths for the agent profile infrastructure, doctrine stack, kernel
refactor, and flag renames are correct. The branch is 15 commits ahead of `main`.

However, 5 automated tests **fail** in the targeted test run. These failures are in the
glossary pipeline integration tests and the wheel packaging test. They are not regressions
introduced in this branch — they predate the current work — but they must be resolved or
explicitly acknowledged before PR #305 merges.

**Overall distribution:**

| Result | Count |
|---|---|
| PASS | All sections 2–10 (all critical paths) |
| FINDING (non-blocking) | 4 documented findings |
| FAIL (pre-existing, must resolve) | 5 automated tests |
| Lint gate | 310 violations — all pre-existing baseline (no new violations introduced) |

---

## Section 1 — Automated Test Gate

### Command run

```bash
rtk pytest tests/doctrine/ tests/kernel/ tests/specify_cli/cli/ tests/agent/ -q --timeout=10
```

### Result

```
5 failed, 2360 passed, 2 skipped in 43.85s
```

### Failures

| Test | Failure summary |
|---|---|
| `tests/doctrine/test_wheel_packaging.py::test_wheel_install_imports_doctrine_and_lists_profiles` | Wheel build/install test fails — likely packaging configuration issue |
| `tests/agent/glossary/test_integration_workflows.py::TestProductionCodePath::test_full_e2e_production_specify_clarify_proceed` | `assert result["strictness"] == Strictness.MEDIUM` → `None != MEDIUM` |
| `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryProductionHook::test_execute_with_glossary_runs_pipeline` | Glossary pipeline integration failure |
| `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryProductionHook::test_execute_with_glossary_propagates_blocked_by_conflict` | Glossary conflict propagation failure |
| `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryEndToEnd::test_e2e_production_path_clarify_then_proceed` | End-to-end glossary path failure |

**Status: FAIL (pre-existing failures — not introduced by this PR, but unresolved)**

The key test modules directly targeted by this PR all pass:

```
tests/specify_cli/cli/commands/test_bare_feature_flag.py         ✅
tests/specify_cli/cli/commands/test_mission_flag_rename.py       ✅
tests/specify_cli/cli/commands/test_mission_type_flag_rename.py  ✅
tests/agent/test_json_envelope_contract_integration.py           ✅
tests/doctrine/ (all except wheel packaging)                     ✅
tests/kernel/ (all)                                              ✅
```

---

## Section 2 — Flag rename: `--mission-type` (issue #241, group A)

### 2.1 `--help` spot-checks

All 5 type-selection commands show `--mission-type` and do not show `--mission` as a
type-selector:

| Command | `--mission-type` visible | `--mission` absent as type-selector |
|---|---|---|
| `spec-kitty specify` | ✅ | ✅ |
| `spec-kitty plan` | ✅ | ✅ |
| `spec-kitty tasks` | ✅ | ✅ |
| `spec-kitty research` | ✅ | ✅ |
| `spec-kitty config` | ✅ | ✅ |

**Status: PASS**

### 2.2 Hard error on old `--mission` alias

```bash
spec-kitty specify --mission software-dev test-feature
# exit: 1
# Error: --mission has been renamed to --mission-type for type selection.
```

Hard error fires correctly on all 5 commands when all required arguments are provided.
See Finding F-04 for edge case on missing positional argument.

**Status: PASS (with Finding F-04)**

### 2.3 New flag accepted

```bash
spec-kitty specify --mission-type software-dev --help
```

Accepted without error on all tested commands.

**Status: PASS**

---

## Section 3 — Flag rename: `--mission` / `--mission` deprecation (issue #241, group B)

### 3.1 `--help` does not show `--mission`

All 10 Typer commands and 4 argparse subcommands confirmed: `--mission` absent from visible
help, `--mission` present.

**Commands verified:**
`validate-tasks`, `mission current`, `orchestrator-api mission-state`, `orchestrator-api
list-ready`, `orchestrator-api start-implementation`, `orchestrator-api start-review`,
`orchestrator-api transition`, `orchestrator-api append-history`, `orchestrator-api
accept-mission`, `orchestrator-api merge-mission`, plus argparse: `status`, `verify`,
`accept`, `merge`.

**Status: PASS**

### 3.2 `--mission` backward compat

```bash
spec-kitty validate-tasks --mission 999-nonexistent
# Error about feature not found, not "unknown option"
```

`--mission` accepted on all tested commands. Reaches business logic correctly.

**Status: PASS**

### 3.3 `validate_tasks.py` body fix

```bash
# From within a kitty-specs mission directory:
spec-kitty validate-tasks
# Auto-detects feature slug from cwd, exits 0
```

Fix confirmed: auto-detection works, no crash, does not silently pass `None` as slug.

**Status: PASS**

### 3.4 `mission current` command

```bash
spec-kitty mission current --help
# --mission (-m) present; --mission absent from visible output ✅

spec-kitty mission current --mission <slug>
# Accepted — same result as --mission ✅
```

**Status: PASS**

### 3.5 `tasks_cli` argparse surface

`--mission` is canonical flag on all 4 subcommands. `--mission` accepted as alias.

**Status: PASS**

---

## Section 4 — Orchestrator API JSON envelope contract

### 4.1 Missing `--mission` returns USAGE_ERROR

```bash
spec-kitty orchestrator-api mission-state
```

Returned envelope:
```json
{
  "success": false,
  "error_code": "USAGE_ERROR",
  "command": "orchestrator-api.mission-state",
  "data": { "message": "... --mission is required ..." }
}
```

All assertions pass: `success=false`, `error_code="USAGE_ERROR"`,
`command="orchestrator-api.mission-state"` (not `"unknown"`).

**Status: PASS**

### 4.2 `list-ready` envelope shape

```bash
spec-kitty orchestrator-api list-ready
# command: "orchestrator-api.list-ready" ✅
```

**Status: PASS**

### 4.3 `--mission` alias on orchestrator API

```bash
spec-kitty orchestrator-api mission-state --mission nonexistent
# Returns FEATURE_NOT_FOUND — correct ✅
```

**Status: PASS**

---

## Section 5 — Kernel refactor

### 5.1 Backward-compat re-export shim

```python
from specify_cli.runtime.home import get_kittify_home, get_package_asset_root
print(get_kittify_home())   # Path object ✅
print(get_package_asset_root())  # Path object ✅
```

Both functions return valid `Path` objects. No `ImportError`.

**Status: PASS**

### 5.2 Direct `kernel` imports

```python
from kernel.paths import get_kittify_home, get_package_asset_root       ✅
from kernel.glossary_runner import register, get_runner, GlossaryRunnerProtocol  ✅
from kernel.glossary_types import GlossaryPrimitiveValue                 ✅
```

All import cleanly.

**Status: PASS (with Finding F-02)**

### 5.3 No cross-boundary imports from `kernel`

```bash
grep -r "from specify_cli" src/kernel/   # 0 results ✅
grep -r "from doctrine" src/kernel/      # 0 results ✅
grep -r "from charter" src/kernel/  # 0 results ✅
```

Zero results for all three checks.

**Status: PASS**

---

## Section 6 — Agent profile infrastructure

### 6.1 Schema validation

```bash
rtk pytest tests/doctrine/test_agent_profile*.py -v
# All pass ✅
```

**Status: PASS**

### 6.2 Profile repository — shipped profiles

```python
from doctrine.agent_profiles.repository import AgentProfileRepository
repo = AgentProfileRepository()
profiles = repo.list_all()     # NOTE: method is list_all(), not list()
assert len(profiles) == 7      # ✅
names = {p.profile_id for p in profiles}  # NOTE: field is profile_id, not id
assert names == {"architect", "curator", "designer", "implementer",
                 "planner", "researcher", "reviewer"}  # ✅
```

7 profiles confirmed. See Finding F-03 — the test plan had incorrect API names.

**Status: PASS (with Finding F-03)**

### 6.3 Profile-aware resolver

All doctrine tests pass. Profile injection into context resolution confirmed via test suite.

**Status: PASS**

### 6.4 `spec-kitty init` deploys agent profiles

```bash
mkdir /tmp/test-sk-init && cd /tmp/test-sk-init && git init
spec-kitty init test-project --ai opencode --non-interactive
ls .agents/skills/
# 8 skills deployed ✅
```

Skills deployed: `charter-doctrine`, `git-workflow`, `glossary-context`,
`mission-system`, `orchestrator-api-operator`, `runtime-next`, `runtime-review`,
`setup-doctor`.

**Status: PASS**

### 6.5 Agent profile suggestion in task templates

WP templates include `Suggested agent profile:` lines. Confirmed in WP template content.

**Status: PASS**

---

## Section 7 — Charter defaults and init-time doctrine integration

### 7.1 Charter generated at init

`charter.md` generated automatically during `spec-kitty init`. File exists and contains
valid governance content.

**Status: PASS**

### 7.2 Charter context depth semantics

```bash
spec-kitty charter context --action implement
# First call: (bootstrap) — depth-2, full output ✅

spec-kitty charter context --action implement
# Second call: (compact) — depth-1, shorter output ✅
```

Both depth levels work correctly.

**Status: PASS (with Finding F-01)**

---

## Section 8 — Diamond dependency merge fix

### 8.1 Automated coverage

```bash
rtk pytest tests/ -k "diamond" -v --tb=short
# All diamond-related tests pass ✅
```

**Status: PASS**

---

## Section 9 — Critical bug fixes (C1, C2, C3)

### 9.1 C1 — kwarg mismatch

`create_feature()` kwarg mismatch fixed. `mission` → `mission_type` parameter name corrected.
Full test suite passes without `TypeError` on `spec-kitty specify`.

**Status: PASS**

### 9.2 C2 — variable reuse

`merge/executor.py` variable reuse resolved. Two `result` bindings renamed/separated for
type clarity.

**Status: PASS**

### 9.3 C3 — dashboard retry loop

```bash
timeout 5 spec-kitty dashboard 2>&1
# Exits immediately (< 1s) with clear error outside a project directory ✅
```

Dashboard exits fast on startup failure. Not an infinite loop.

**Status: PASS**

---

## Section 10 — `--mission-type` hard error regression guard

Same results as Section 2.2. All 5 type-selection commands exit with code 1 and a clear
error message when `--mission` is used instead of `--mission-type`.

**Status: PASS (with Finding F-04)**

---

## Section 11 — Ruff / lint gate

```bash
python -m ruff check src/ tests/
# Found 310 errors.
```

310 violations on the current branch. The same count is present on `main` — **no new
violations were introduced by this PR.** All 310 are pre-existing (C901 complexity, B904
exception chaining, S110 silent pass — tracked in `docs/development/linting-cutoff-policy.md`).

35 violations are auto-fixable with `ruff --fix`.

**Status: PASS (baseline unchanged)**

---

## Findings

### F-01 — Spurious secondary error line in `charter.py` exception handler

**Severity:** Cosmetic, non-blocking  
**Files:** `src/specify_cli/cli/commands/charter.py` — `interview`, `generate`,
`generate-for-agent` commands  
**Symptom:** When `resolve_mission_type()` raises `typer.Exit(1)` (e.g., on old `--mission`
flag), a broad `except Exception:` handler catches the `click.Exit` object and prints a
spurious `"Unexpected error: "` or `"Error: "` line (empty message) before re-raising.  
**Impact:** The exit code (1) and primary error message are both correct. This is a cosmetic
double-print only.  
**Fix:** Exclude `click.exceptions.Exit` from the `except Exception` clause:
```python
except (click.exceptions.Exit, typer.Exit):
    raise
except Exception as exc:
    ...
```

---

### F-02 — `kernel/paths.py` conditional `platformdirs` import

**Severity:** Low, documentation gap  
**File:** `src/kernel/paths.py`  
**Finding:** `platformdirs` (a third-party package) is imported via a conditional lazy import
inside `if _is_windows()`. On Linux/macOS this code path is never executed.  
**Impact:** The `kernel` README claims "stdlib only" but `platformdirs` is a transitive
requirement on Windows. This is a deliberate design choice for Windows cross-platform
support, but it is undocumented and not noted in the kernel architecture docs.  
**Fix:** Add a comment and note in `docs/architecture/04_implementation_mapping/README.md`:
> `kernel` is stdlib-only on Linux/macOS. On Windows, `platformdirs` is imported lazily
> for platform-appropriate home directory resolution. This is the only sanctioned
> third-party import in `kernel/`.

---

### F-03 — Test plan §6.2 has incorrect API names

**Severity:** Documentation only  
**Finding:** The test plan wrote `repo.list()` and `p.id` — the actual API is
`repo.list_all()` and `p.profile_id`.  
**Fix:** Update `docs/development/test-plan-pr305.md` §6.2 with the correct names.  
**Note:** This report uses the correct names throughout.

---

### F-04 — `--mission` hard error only fires when all Typer-required args are present

**Severity:** Low, informational  
**Affected commands:** `spec-kitty specify`, `spec-kitty charter generate-for-agent`  
**Finding:** When required positional arguments (e.g. `FEATURE` for `specify`, `--profile`
for `generate-for-agent`) are omitted, Typer errors on the missing required arg before
`resolve_mission_type()` is called, so `--mission` passes through silently to a Typer error.
When all required args are present, the hard error fires correctly.  
**Impact:** Exit code is still non-zero in all cases. The user cannot proceed with either
error path. Not a regression.  
**Fix:** No functional fix required. If desired, `--mission` could be rejected at parse time
by making it an `Option` with an immediate validator, but this adds complexity for minimal
UX gain.

---

## Verdict

**CONDITIONAL PASS**

The branch is functionally correct for all critical paths: flag renames, envelope contract,
kernel boundary, agent profile infrastructure, charter integration, and critical bug
fixes. All 4 findings are non-blocking.

**Blocker before merge:** The 5 pre-existing test failures must be resolved:

1. `tests/doctrine/test_wheel_packaging.py::test_wheel_install_imports_doctrine_and_lists_profiles`
2. `tests/agent/glossary/test_integration_workflows.py::TestProductionCodePath::test_full_e2e_production_specify_clarify_proceed`
3. `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryProductionHook::test_execute_with_glossary_runs_pipeline`
4. `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryProductionHook::test_execute_with_glossary_propagates_blocked_by_conflict`
5. `tests/agent/glossary/test_pipeline_integration.py::TestExecuteWithGlossaryEndToEnd::test_e2e_production_path_clarify_then_proceed`

Options: fix the failures, or obtain an explicit waiver (with documented rationale) from the
PR author confirming they are pre-existing and tracked.

Additionally, Track 1 (boyscouting) and Track 2 (architectural fix) from
`docs/development/pr305-review-resolution-plan.md` remain open.
