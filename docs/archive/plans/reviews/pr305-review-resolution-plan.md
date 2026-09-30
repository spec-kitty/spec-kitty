---
title: 'PR #305 Review Resolution Plan'
description: 'Resolution plan for the PR #305 review (specs 046/048/054): the agreed approach to the critical and major issues the review identified.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Per-PR review working note for PR #305 (agent-profile-implementation); the agent-profile system shipped as mission `045-agent-profile-system` (#136 / #1975). Content preserved as an audit-trail record.

# PR #305 Review Resolution Plan

**Context**: A prior code review of PR #305 (specs 046, 048, 054) identified two
critical and several major issues. This document records the agreed resolution approach and
the concrete implementation plan for both tracks.

**Branch**: `feature/agent-profile-implementation` (057)
**Date**: 2026-03-25
**Architect**: Architect Alphonso (profile: `architect`)

---

## Issues to Resolve

| ID | Issue | Severity | Track |
|----|-------|----------|-------|
| C1 | `doctrine` imports `specify_cli` — violates stated dependency direction | Critical | Track 2 |
| C2 | CI coverage/mypy does not include `src/doctrine/` | Critical | Track 1 |
| M1 | 8 bare `except Exception:` in `_default_shipped_dir()` methods | Major | Track 1 |
| M2 | `_PLURALS`/`_PATTERNS` dicts re-allocated on every property access | Major | Track 1 |
| M3 | `resolve_doctrine_root()` fallback chain has no logging | Minor | Track 1 |
| M4 | `except Exception: pass` in `context.py` YAML/JSON parsers | Major | Track 1 |
| 241 | `--mission` naming collision in `create-mission` command | Design gap | Track 1 |

---

## Track 1 — Boyscouting PR

**Form**: Single PR, 6 independent commits. No mission spec required.

### Commit 1 — CI: add `src/doctrine` to mypy and missing coverage jobs

**File**: `.github/workflows/ci-quality.yml`

- Mypy invocation (line ~268): add `src/doctrine`
  ```bash
  # Before
  python -m mypy --strict src/specify_cli src/charter
  # After
  python -m mypy --strict src/specify_cli src/charter src/doctrine
  ```
- Integration, slow, and e2e test steps: add `--cov=src/doctrine`
- Fast tests already include `--cov=src/doctrine` — no change needed

---

### Commit 2 — M1: narrow `except Exception` in `_default_shipped_dir()` (8 files)

**Files** (identical change in all 8):
```
src/doctrine/agent_profiles/repository.py
src/doctrine/directives/repository.py
src/doctrine/mission_step_contracts/repository.py
src/doctrine/paradigms/repository.py
src/doctrine/procedures/repository.py
src/doctrine/styleguides/repository.py
src/doctrine/tactics/repository.py
src/doctrine/toolguides/repository.py
```

**Change**: Replace `except Exception:` with `except (ModuleNotFoundError, TypeError):` in each
`_default_shipped_dir()` method. Matches the same reasoning used in `resolve_doctrine_root()`:
`importlib.resources.files()` raises exactly these two types on failure.

---

### Commit 3 — M2: hoist `_PLURALS`/`_PATTERNS` to module-level constants

**File**: `src/doctrine/artifact_kinds.py`

Both dicts are currently re-created on every property access. Move them to module-level
constants above the class. Properties become single-line lookups. No logic change.

```python
# Before (inside properties — re-allocated on every call)
@property
def plural(self) -> str:
    _PLURALS: dict[str, str] = {"directive": "directives", ...}
    return _PLURALS[self.value]

# After (module-level — allocated once)
_PLURALS: dict[str, str] = {"directive": "directives", ...}
_PATTERNS: dict[str, str] = {"directive": "*.directive.yaml", ...}

class ArtifactKind(StrEnum):
    @property
    def plural(self) -> str:
        return _PLURALS[self.value]
```

---

### Commit 4 — M3: add `logging.debug()` to `resolve_doctrine_root()` fallback chain

**Files**: `src/specify_cli/charter/catalog.py` and `src/charter/catalog.py`

Add `import logging` and `log = logging.getLogger(__name__)`. Insert debug calls at each
fallback step:

```python
# After importlib attempt fails:
log.debug("doctrine: importlib.resources lookup failed, trying dev layout")

# After dev layout succeeds:
log.debug("doctrine: resolved via dev layout at %s", dev_root)

# After package asset fallback (charter/catalog.py only):
log.debug("doctrine: resolved via package asset root fallback")
```

---

### Commit 5 — M4: narrow `except Exception:` in `context.py` YAML/JSON parsers

**Files**: `src/specify_cli/charter/context.py` and `src/charter/context.py`

Two locations in each file:

| Location | Guard target | Replace with |
|----------|-------------|--------------|
| `_load_references` — YAML parse | ruamel.yaml parse + file read | `except (YAMLError, UnicodeDecodeError, OSError):` |
| `_load_state` — JSON parse | `json.loads` + file read | `except (json.JSONDecodeError, UnicodeDecodeError, OSError):` |

Add `from ruamel.yaml import YAMLError` to import blocks. `json` is already imported.

---

### Commit 6 — #241: rename `create-mission --mission` to `--mission-type`

**File**: `src/specify_cli/cli/commands/agent/feature.py`

The `create-mission` command uses `--mission` to mean "mission type" (e.g., `software-dev`,
`documentation`). All other commands use `--mission` for "feature slug". This is the surviving
naming collision from issue #241.

**Change**:
- Add `--mission-type` as canonical parameter
- Keep `--mission` as `hidden=True` deprecated alias, emitting the same deprecation warning
  pattern established in WP01
- Add `_resolve_mission_type(mission_type, mission)` helper in `_flag_utils.py` alongside
  the existing `resolve_mission_or_feature()`

---

## Track 2 — Architectural Fix PR

**Form**: Targeted PR with ADR. No full mission spec. Sequential commits.

**Problem**: `src/doctrine/missions/primitives.py` and `glossary_hook.py` import from
`specify_cli.glossary.*`, violating the rule that `doctrine` has no dependency on
`specify_cli`. The two files need different solutions:

| File | Problem | Solution |
|------|---------|---------|
| `primitives.py` | Imports 4 data types from `specify_cli.glossary.*` | Option A: move types to `doctrine/shared/` |
| `glossary_hook.py` | Imports `GlossaryAwarePrimitiveRunner` — a rich orchestration class that cannot move to doctrine | Lazy imports: defer specify_cli import to call time |

**Decision**: Option A (move types into doctrine). `src/kernel/` was available as a fallback
but is not needed — these types have natural ownership in doctrine.

---

### Step 0 — Write the ADR (first commit)

**File**: `docs/adr/2.x/2026-03-XX-glossary-type-ownership.md`

Documents:
- Glossary primitive types are owned by `doctrine`, re-exported by `specify_cli`
- `glossary_hook.py` remains in `doctrine/missions/` as an intentional bridge but defers
  specify_cli imports to call time — the only sanctioned use of lazy cross-boundary imports
- Rejected: moving `GlossaryAwarePrimitiveRunner` to doctrine (too deeply coupled to
  specify_cli middleware)
- `src/kernel/` was available (Option C) but not needed for these types

---

### Step 1 — Create `src/doctrine/shared/glossary_types.py`

Collect all types in dependency order. All dependencies are stdlib only.

```python
# src/doctrine/shared/glossary_types.py
"""Glossary primitive types owned by doctrine, consumed by specify_cli."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum

# Moved from specify_cli.glossary.scope
class GlossaryScope(StrEnum): ...

# Moved from specify_cli.glossary.strictness
class Strictness(StrEnum):
    OFF = "off"
    MEDIUM = "medium"
    MAX = "max"

# Moved from specify_cli.glossary.extraction
@dataclass(frozen=True)
class ExtractedTerm:
    surface: str
    source: str
    confidence: float
    original: str = ""

# Moved from specify_cli.glossary.models (nested types first)
@dataclass(frozen=True)
class TermSurface: ...
class ConflictType(StrEnum): ...
class Severity(StrEnum): ...
@dataclass
class SenseRef: ...
@dataclass
class SemanticConflict: ...

# Moved from specify_cli.glossary.checkpoint
@dataclass(frozen=True)
class ScopeRef:
    scope: GlossaryScope
    version_id: str
```

Update `src/doctrine/shared/__init__.py` to re-export all new types.
No changes to `src/doctrine/pyproject.toml` — all stdlib, no new dependencies.

---

### Step 2 — Update `doctrine/missions/primitives.py` imports

```python
# Before (4 specify_cli imports)
from specify_cli.glossary.checkpoint import ScopeRef
from specify_cli.glossary.extraction import ExtractedTerm
from specify_cli.glossary.models import SemanticConflict
from specify_cli.glossary.strictness import Strictness

# After (single doctrine import)
from doctrine.shared.glossary_types import (
    ExtractedTerm,
    SemanticConflict,
    ScopeRef,
    Strictness,
)
```

No other changes to the file body.

---

### Step 3 — Convert `doctrine/missions/glossary_hook.py` to lazy imports

`GlossaryAwarePrimitiveRunner` and `read_glossary_check_metadata` orchestrate specify_cli's
full glossary pipeline and cannot move to doctrine. Move their imports inside the function body:

```python
# Module level — OK after Step 2
from doctrine.shared.glossary_types import Strictness

def execute_with_glossary(
    ...,
    runtime_strictness: Strictness | None = None,
    ...,
) -> Any:
    # Lazy import: specify_cli dependency deferred to call time (see ADR-XX)
    from specify_cli.glossary.attachment import (
        GlossaryAwarePrimitiveRunner,
        read_glossary_check_metadata,
    )
    ...
```

Add module docstring: `"""Bridge module: defers specify_cli imports to call time. See ADR-XX."""`

---

### Step 4 — Add backward-compat re-exports in `specify_cli/glossary/`

The 30–40 usages of these types throughout `specify_cli.glossary.*` must continue to work
without any call-site changes. Replace each class definition with a re-export:

| File | Change |
|------|--------|
| `specify_cli/glossary/strictness.py` | Replace `Strictness` class def with `from doctrine.shared.glossary_types import Strictness` |
| `specify_cli/glossary/extraction.py` | Replace `ExtractedTerm` class def with re-export |
| `specify_cli/glossary/models.py` | Replace `TermSurface`, `ConflictType`, `Severity`, `SenseRef`, `SemanticConflict` with re-exports |
| `specify_cli/glossary/scope.py` | Replace `GlossaryScope` class def with re-export |
| `specify_cli/glossary/checkpoint.py` | Replace `ScopeRef` class def with re-export |

All existing `from specify_cli.glossary.X import Y` call sites continue to work unchanged.

---

### Step 5 — Boundary isolation test

Add `tests/doctrine/test_isolation.py`:

```python
"""Verify doctrine can be imported without pulling in specify_cli."""
import subprocess
import sys

def test_doctrine_does_not_import_specify_cli(tmp_path):
    """doctrine.missions.primitives must import cleanly without specify_cli on PYTHONPATH."""
    src_root = Path(__file__).parents[2] / "src"
    result = subprocess.run(
        [sys.executable, "-c", "import doctrine; import doctrine.missions.primitives"],
        env={
            **os.environ,
            "PYTHONPATH": str(src_root / "doctrine") + os.pathsep + str(src_root / "kernel"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"doctrine imported specify_cli at module load time:\n{result.stderr}"
    )
```

---

### Commit Sequence for Track 2

```
1. docs: ADR — glossary type ownership (doctrine owns, specify_cli re-exports)
2. feat(doctrine): create doctrine/shared/glossary_types.py with moved types
3. fix(doctrine): update doctrine/shared/__init__.py exports
4. fix(doctrine): update primitives.py to import from doctrine.shared
5. fix(doctrine): convert glossary_hook.py to lazy specify_cli imports
6. fix(specify_cli): add re-exports in glossary/{strictness,extraction,models,scope,checkpoint}.py
7. test: add doctrine isolation test (import without specify_cli)
```

Each commit must stay green: `ruff check`, `mypy --strict`, `pytest tests/doctrine/`.

---

## Sequencing Between Tracks

```
Track 1 (boyscouting PR)
  └── merge to mission branch

Track 2 (architectural fix PR)
  └── merge to mission branch

PR #305 ready for final review → merge to develop
```

Track 1 and Track 2 are independent of each other and can be worked in parallel.
Neither blocks the other. Both must land before PR #305 moves out of draft.

---

## What This Does NOT Address

- **#327 — Doctrine-mission compiler**: Separate feature, backlog after PR #305 merges.
- **Skills/doctrine mission boundary**: Part of #327 planning.
- **`charter/compiler.py` and `interview.py` test coverage gap**: Flagged for a
  follow-on spec; not a PR #305 blocker.
