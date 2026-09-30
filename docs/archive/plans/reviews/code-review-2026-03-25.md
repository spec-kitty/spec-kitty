---
title: Code Review — 2026-03-25
description: "Code-review record dated 2026-03-25: the reviewed scope, the findings, and their dispositions captured in the review's field table."
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Per-PR review working note for PR #305 (agent-profile-implementation); the agent-profile system shipped as mission `045-agent-profile-system` (#136 / #1975). Content preserved as an audit-trail record.

# Code Review — 2026-03-25

| Field | Value |
|---|---|
| Version | 2.1.2 |
| Date | 2026-03-25 |
| Reviewer | OpenCode (claude-sonnet-4.6) |
| Scope | Full source tree (`src/`) against `architecture/2.x` |
| Tools | ruff, mypy --strict, pytest, manual architectural trace |

---

## Summary

| Severity | Count | Category |
|---|---|---|
| Critical | 3 | Real bugs: dropped kwarg, type mismatch, dashboard blocking retry loop |
| High | 14 | Broken `__all__` exports, undefined names, None-dereference |
| Medium | ~104 | Lost tracebacks (65), complexity violations (39) |
| Low / Style | 823 | Auto-fixable: deprecated typing, f-string, unused imports |
| Architecture | 5 | Boundary violations (4 documented, 1 undocumented) |
| Canon | 5+ | `Feature` terminology in non-deprecated user-facing surfaces |

---

## 1. Critical Bugs

### C1 — Dropped `--mission` argument on `spec-kitty specify`

**File:** `src/specify_cli/cli/commands/lifecycle.py:33`

```python
# Current — WRONG
agent_feature.create_feature(mission_slug=slug, mission=mission, json_output=json_output)
```

`create_feature` (defined at `cli/commands/agent/feature.py:501`) has no `mission` kwarg.
Its parameters are `mission_type` and `mission_legacy`.

The result: every call to `spec-kitty specify --mission <type>` silently drops the mission
type. The feature is created with no mission type, falling back to whatever default the
resolver provides. mypy confirms: `error: Unexpected keyword argument "mission" for
"create_feature"`.

### C2 — Type mismatch in `merge/executor.py`

**File:** `src/specify_cli/merge/executor.py:596–614`

```python
# Line 596 — no text=True → CompletedProcess[bytes]
result = subprocess.run(["git", "rev-parse", ...], capture_output=True, check=False)

# Line 606 — REASSIGNS to text=True → CompletedProcess[str]
result = subprocess.run(["git", "status", "--porcelain"], ..., text=True, encoding="utf-8")

# Line 614 — reads .stdout as str, but variable declared as CompletedProcess[bytes]
if result.stdout.strip():
```

Both runs reuse the same `result` variable. The first run is typed as `CompletedProcess[bytes]`
by mypy, the second reassigns it to `CompletedProcess[str]`. The `.stdout.strip()` call on
line 614 operates on the second (str) result and works at runtime, but the type contract is
broken and the variable reuse obscures which result is being checked where.

### C3 — Dashboard retry loop blocks on dead process; test timeout

**File:** `src/specify_cli/dashboard/lifecycle.py:364–369`

```python
retry_delays = [0.1] * 10 + [0.25] * 40 + [0.5] * 20  # ~20 seconds total
for delay in retry_delays:
    if _check_dashboard_health(port, project_dir_resolved, token):
        ...
        return url, port, True
    time.sleep(delay)
```

The process liveness check (`_is_process_alive(pid)`) only runs *after* the full 20-second
retry loop completes. When the dashboard process dies immediately after startup, the loop
still runs to completion before reporting failure.

This causes the failing test
`test_health_timeout_with_dead_process_still_fails` to time out (>10 s) inside
`time.sleep`. It also means real users wait 20 seconds before seeing a startup failure.

---

## 2. High Severity

### H1 — Broken `__all__` exports in `glossary/models.py`

**Files:** `src/specify_cli/glossary/models.py` and 7 downstream modules

`models.py` does not export `SemanticConflict`, `Severity`, `ConflictType`, `SenseRef`, or
`TermSurface` via `__all__`. mypy reports `attr-defined` errors propagating through:

- `glossary/strictness.py` (3 errors)
- `glossary/scope.py` (1 error)
- `glossary/checkpoint.py` (1 error)
- `glossary/exceptions.py` (2 errors)
- `glossary/resolution.py` (1 error)
- `glossary/pipeline.py` (3 errors)
- `glossary/conflict.py` (5 errors, including `Name "models.SemanticConflict" is not defined`)
- `glossary/attachment.py` (1 error)
- `glossary/__init__.py` (9 errors)

The entire glossary subsystem has broken type exports. In strict mypy this is 27 errors
from a single missing `__all__`.

### H2 — Undefined names (F821/F822)

| File | Name | Risk |
|---|---|---|
| `cli/commands/agent/tasks.py:726` | `Any` used in `"Any \| None"` annotation | `NameError` if annotation evaluated at runtime |
| `cli/commands/sync.py:39` | `timedelta` in `"timedelta"` annotation | Same risk |
| `core/agent_config.py:26` | `Path` used in annotation without import | Same risk |
| `scripts/tasks/acceptance_support.py:55–66` | `__all__` declares 10 names populated by `globals().update()` | Breaks static analysis; any downstream `from acceptance_support import *` is opaque |

### H3 — Potential None dereference

**File:** `src/specify_cli/merge/status_resolver.py:492`

Expression type is `str | None`, variable type is `str`. No None-guard before use. mypy:
`error: Incompatible types in assignment`.

---

## 3. Medium Severity

### M1 — Lost exception tracebacks (65 instances, B904)

Every CLI command error handler pattern across `cli/commands/` raises `typer.Exit(1)` bare
inside an `except` block:

```python
except SomeError as exc:
    console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1)   # loses exc as __cause__
```

The original exception is not chained. When a user reports an error with a log, the
traceback has no cause chain to `exc`. Use `raise typer.Exit(1) from exc` or
`raise typer.Exit(1) from None` (if intentional suppression).

### M2 — Cyclomatic complexity violations (39 functions, C901)

The project threshold is 15. Worst offenders:

| Function | Complexity | File |
|---|---|---|
| `merge` | 75 | `cli/commands/agent/feature.py` |
| `run_enhanced_verify` | 68 | `verify_enhanced.py` |
| `move_task` | 63 | `cli/commands/agent/tasks.py` |
| `implement` (workflow) | 57 | `cli/commands/agent/workflow.py` |
| `merge_workspace_per_wp` | 49 | `cli/commands/agent/feature.py` |
| `map_requirements` | 47 | `requirement_mapping.py` |
| `execute_merge` | 36 | `merge/executor.py` |
| `review` | 32 | `cli/commands/agent/workflow.py` |
| `implement` (cmd) | 31 | `cli/commands/implement.py` |
| `status` | 30 | `cli/commands/agent/workflow.py` |

`merge` at complexity 75 is effectively untestable by mutation testing. The `mutmut` config
does not cover `cli/commands/agent/feature.py`, meaning regressions in merge semantics are
undetected by the mutation gate.

### M3 — Silent `try/except/pass` (30 instances, S110)

Notable cases:

- `cli/commands/agent/feature.py:749` — auto-commit failure is silently swallowed. A failed
  commit produces no observable signal to the caller.
- `cli/commands/accept.py:32` — event emission failure suppressed entirely.

---

## 4. Low / Style (Auto-fixable)

| Rule | Count | Category |
|---|---|---|
| UP045 | 186 | `Optional[X]` → `X \| None` |
| UP006 | 134 | `List[X]`, `Dict[X,Y]` → `list[X]`, `dict[X,Y]` |
| F541 | 109 | f-strings without placeholders (`f"Progress: "`) |
| F401 | 85 | Unused imports |
| UP035 | 43 | Deprecated `typing` imports |
| UP017 | 36 | `timezone.utc` → `datetime.UTC` |
| SIM10x | 33 | Collapsible conditions, reimplemented builtins |
| UP037 | 10 | Quoted annotations |

All 592 flagged as `[*]` are auto-fixable with `ruff --fix src/`.

Additionally, `manifest.py:92` contains a logic error:

```python
if not in_frontmatter and in_frontmatter == False:
```

The second clause is a tautology of the first. The condition is equivalent to
`if not in_frontmatter`. This is either dead code or a miswritten transition guard.

---

## 5. Architecture Divergences vs. `architecture/2.x`

Four divergences are already documented in `docs/architecture/04_implementation_mapping/README.md`.
One is not.

### DIV-1 — CLI bypasses Control Plane → Orchestration boundary (documented)

`lifecycle.py:33` calls `agent_feature.create_feature()` directly from the Control Plane
layer without routing through Orchestration. Multiple handlers in `cli/commands/agent/feature.py`
write directly to `kitty-specs/` without going through `status/emit.py`.

### DIV-2 — Kitty-core and Orchestration both write `kitty-specs/` (documented)

Planning artifacts (spec.md, plan.md, meta.json) are written directly at lines 600–810 of
`cli/commands/agent/feature.py`, bypassing the Event Store interface contract.

### DIV-3 — Connector concept is implicit (documented)

No formal `Connector` interface. Current "adapter" is a rendered markdown template. No
dispatch mechanism abstraction exists for SDK, shell, or remote API alternatives.

### DIV-4 — Dashboard reads filesystem directly (documented)

`dashboard/scanner.py` reads WP frontmatter directly rather than querying through the
Event Store interface.

### DIV-5 — `doctrine` has undocumented reverse dependency on `specify_cli` (NOT documented)

The `architecture/2.x` documents state `doctrine` has "zero dependency on `specify_cli`".
This is false:

- `src/doctrine/missions/glossary_hook.py:83` lazy-imports
  `from specify_cli.glossary.attachment import GlossaryAwarePrimitiveRunner` at call time.
- `src/charter/catalog.py:25` lazy-imports
  `from specify_cli.runtime.home import get_package_asset_root` at call time.

The `glossary_hook.py` case is partially addressed in ADR `2026-03-25-1-glossary-type-ownership`
and `pr305-review-resolution-plan.md` (Track 2), but the fix is not yet merged. The
`charter/catalog.py` reverse dependency has no ADR and is not mentioned in the
implementation mapping.

---

## 6. Terminology Canon Violations

Per `AGENTS.md`: canonical term is **Mission**; `Feature` is prohibited in non-deprecated
user-facing language.

Active violations in user-visible help strings:

| File | Line | Violation |
|---|---|---|
| `cli/commands/lifecycle.py` | 27 | `help="Feature name or slug (e.g., user-authentication)"` |
| `cli/commands/agent/feature.py` | 49 | `help="Feature lifecycle commands for AI agents"` |
| `cli/commands/agent/feature.py` | 503 | `help="Feature slug (e.g., 'user-auth')"` |
| `cli/commands/research.py` | 44 | `tracker.add("feature", ...)` — internal label, surfaces to users |
| `cli/commands/implement.py` | 563 | Example slug `"001-my-feature"` in `--mission` help — perpetuates the term |

---

## 7. Security Notes

| Rule | File | Assessment |
|---|---|---|
| S608 | `sync/queue.py:442,461,517,523` | False positive — parameterised `?` placeholders are safe. Add `# noqa: S608` with justification comment. |
| S310 | `dashboard/lifecycle.py:146,231,460,475,482` | All target `http://127.0.0.1:<port>` — localhost only, low risk. `httpx` (already a dependency) would be a cleaner replacement. |
| S108 | `dossier/tests/test_api.py`, `test_indexer.py` | Hardcoded `/tmp/` in tests — non-portable on Windows. Use `tmp_path` pytest fixture. |

---

## 8. mypy Quarantine Scope

The `[tool.mypy.overrides] ignore_errors = true` block in `pyproject.toml` covers 74 modules —
the majority of production `specify_cli` code. Strict mode is effectively inactive for most
of the codebase. The quarantine comment says "Transitional", but the list has grown with
recent features (e.g., `mission_v1`, `dossier`, `orchestrator_api`) rather than shrinking.

---

## Test Results

```
1701 passed, 7 skipped, 18 xfailed, 90 warnings
1 FAILED: test_health_timeout_with_dead_process_still_fails (C3 above)
```

90 warnings include 18 `DeprecationWarning: --mission is deprecated; use --mission instead`
triggered by tests that still use the deprecated `--mission` flag.
