---
title: Auto-Discover Migrations from Filesystem
description: Discovers upgrade migrations by scanning the package at import time, eliminating the forgotten registration line that repeatedly blocked releases at the CI gate.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-30'
---

## Context and Problem Statement

**The recurring problem:**
Every release, we encountered this workflow:
1. Developer creates new migration file: `m_X_Y_Z_name.py`
2. Developer decorates with `@MigrationRegistry.register`
3. **Developer forgets** to add `from . import m_X_Y_Z_name` to `__init__.py`
4. CI test fails: "Migration registry incomplete! Found N files but only N-1 registered"
5. Release blocked until manual import added

**Why this keeps happening:**
- Two-step process: Create file + Edit **init**.py
- **init**.py is far from the migration file in editor
- Easy to forget second step when focused on migration logic
- No IDE autocomplete reminder
- Error only caught at release time (not during development)

**Impact:**
- **Every release** blocked on this issue
- Developer frustration ("we forget every fucking time")
- Wasted time adding manual imports
- Brittle architecture relying on human memory

**Current architecture (broken):**
```python
# migrations/__init__.py
from . import m_0_2_0_specify_to_kittify
from . import m_0_4_8_gitignore_agents
# ... 35 manual imports
from . import m_0_14_0_centralized_feature_detection  # ← Forgot this!
```

**Question:** Should migrations be auto-discovered from the filesystem instead of requiring manual imports?

## Decision Drivers

- **Eliminate recurring failure** - This issue blocks EVERY release
- **Single responsibility** - Creating a migration should be one step, not two
- **Fail-fast** - Errors should surface during development, not at release
- **Developer experience** - Reduce cognitive load and manual bookkeeping
- **Standard practice** - Most migration systems auto-discover (Django, Alembic, etc.)
- **Backward compatibility** - Existing migrations and tests must continue working
- **Performance** - Auto-discovery must be fast (<1 second)

## Considered Options

- **Option 1:** Auto-discovery using pkgutil + importlib (filesystem scan)
- **Option 2:** Code generation (auto-update **init**.py on migration creation)
- **Option 3:** Status quo + better documentation/reminders
- **Option 4:** Pre-commit hook to validate **init**.py

## Decision Outcome

**Chosen option:** "Option 1: Auto-discovery using pkgutil + importlib", because:
- **Zero manual steps** - Create migration file, done
- **Impossible to forget** - No second step to forget
- **Fast** - Filesystem scan + dynamic import takes <100ms
- **Standard pattern** - Same approach as Django migrations
- **Testable** - Easy to verify all migrations discovered
- **Backwards compatible** - Existing @register decorators still work

### Consequences

#### Positive

- **No more release blockers** - Migrations auto-discovered, no manual imports
- **Single-step workflow** - Create m_*.py file, auto-registered
- **Better developer experience** - Focus on migration logic, not bookkeeping
- **Fail-fast** - Import errors surface immediately, not at release
- **Standard architecture** - Aligns with Django, Alembic, and other migration systems
- **Reduced code** - 43 lines of manual imports → 52 lines of auto-discovery (but scales to infinite migrations)

#### Negative

- **Slightly slower startup** - Must scan directory and import modules (adds ~50ms)
- **Module reload needed** - After `MigrationRegistry.clear()` in tests, must call `auto_discover_migrations()`
- **Potential import errors** - Broken migration files fail loudly (but this is good!)
- **Less explicit** - Can't see list of migrations in **init**.py (but registry provides this)

#### Neutral

- **Naming convention enforced** - Only `m_*.py` files auto-discovered
- **Import-time execution** - Auto-discovery runs when migrations module imported
- **Test isolation** - Tests must call `auto_discover_migrations()` after `clear()`

### Confirmation

We validated this decision by:
- ✅ Auto-discovery finds all 35 existing migrations
- ✅ 13 comprehensive tests covering discovery, performance, edge cases
- ✅ Migration registry completeness test passes
- ✅ Backwards compatible with manual @register decorators
- ✅ Performance < 100ms (measured in test_auto_discovery_performance)
- ✅ Handles import errors gracefully (logs warning, continues)
- ✅ Idempotent (can call multiple times safely)

## Pros and Cons of the Options

### Option 1: Auto-discovery using pkgutil + importlib (CHOSEN)

Scan `migrations/` directory at runtime, dynamically import all `m_*.py` files.

**Pros:**
- Zero manual steps (just create file)
- Impossible to forget registration
- Standard pattern (Django, Alembic use this)
- Fast (<100ms)
- Testable and verifiable
- Scales to infinite migrations (no manual list)
- Fail-fast (import errors surface immediately)

**Cons:**
- Slightly slower startup (~50ms overhead)
- Module reload needed after clear() in tests
- Less explicit (can't see migration list in **init**.py)
- Potential import errors (but good - catches broken migrations early)

### Option 2: Code generation (auto-update **init**.py)

Generate **init**.py automatically when migration created (e.g., via CLI command).

**Pros:**
- Explicit migration list visible in **init**.py
- No runtime scanning overhead
- Familiar pattern (explicit imports)

**Cons:**
- Still two-step process (create migration, run codegen)
- Can forget to run codegen command
- Codegen complexity (when to run? pre-commit hook?)
- Diff noise (every migration adds line to **init**.py)
- Doesn't solve core problem (still manual step)

### Option 3: Status quo + better documentation

Keep manual imports, add reminders in docs and CI.

**Pros:**
- No code changes needed
- Explicit migration list in **init**.py
- No performance overhead

**Cons:**
- **Doesn't solve the problem** - Still requires human memory
- Still blocks releases (proven track record)
- Documentation doesn't prevent mistakes
- Developer frustration persists
- Wasted time on every release

### Option 4: Pre-commit hook validation

Git hook that checks **init**.py matches filesystem before commit.

**Pros:**
- Catches errors before commit
- No runtime overhead
- Fails early in development

**Cons:**
- Still requires manual import (doesn't eliminate problem)
- Pre-commit hooks can be skipped (`--no-verify`)
- Adds setup complexity for contributors
- Doesn't prevent the mistake, just catches it earlier

## More Information

**Implementation:**
- `src/specify_cli/upgrade/migrations/__init__.py` - Auto-discovery function
- `tests/specify_cli/upgrade/test_auto_discovery.py` - 13 comprehensive tests

**Auto-Discovery Logic:**
```python
def auto_discover_migrations() -> None:
    """Scan migrations/ directory and import all m_*.py files."""
    migrations_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(migrations_dir)]):
        module_name = module_info.name

        if module_name.startswith("m_") or module_name == "base":
            module_full_name = f"{__name__}.{module_name}"

            if module_full_name in sys.modules:
                # Reload to re-execute @register decorators (for tests)
                importlib.reload(sys.modules[module_full_name])
            else:
                # Fresh import
                importlib.import_module(f".{module_name}", package=__name__)
```

**Key Features:**
1. **Filesystem scan** - Uses `pkgutil.iter_modules()` to find all modules
2. **Pattern matching** - Only imports `m_*.py` files (migration naming convention)
3. **Module reload** - Handles test isolation (after `MigrationRegistry.clear()`)
4. **Graceful errors** - Logs import failures but continues (fail-fast for broken migrations)
5. **Module-level call** - Runs automatically when migrations package imported

**Developer Workflow (Before):**
```bash
# Step 1: Create migration
touch src/specify_cli/upgrade/migrations/m_0_15_0_my_feature.py
# Write migration class with @MigrationRegistry.register

# Step 2: Edit __init__.py (EASY TO FORGET!)
vim src/specify_cli/upgrade/migrations/__init__.py
# Add: from . import m_0_15_0_my_feature

# Step 3: Test
pytest
# ❌ Fails if you forgot step 2!
```

**Developer Workflow (After):**
```bash
# Step 1: Create migration
touch src/specify_cli/upgrade/migrations/m_0_15_0_my_feature.py
# Write migration class with @MigrationRegistry.register

# That's it! Auto-discovered on next import.
pytest
# ✅ Passes - migration auto-discovered
```

**Test Isolation Pattern:**
```python
def test_my_migration():
    # Clear registry for isolation
    MigrationRegistry.clear()

    # Re-discover migrations (now includes reload logic)
    auto_discover_migrations()

    # Test migration
    assert MigrationRegistry.get_by_id("my_migration") is not None
```

**Performance Benchmarks:**
- Auto-discovery: ~50-80ms (35 migrations)
- Manual imports: ~20-30ms (35 migrations)
- Overhead: ~30-50ms (acceptable for CLI tool)

**Error Handling:**
```python
# If a migration has import errors, it logs a warning:
Warning: Failed to import migration module m_broken: SyntaxError ...

# Then the migration registry validation catches it:
Error: Migration m_broken exists but failed to register
```

**Related Changes:**
- Removed 43 lines of manual imports from `migrations/__init__.py`
- Added `auto_discover_migrations()` function (52 lines)
- Added 13 comprehensive tests (`test_auto_discovery.py`)
- Updated `test_migration_robustness.py` to verify discovery completeness

**Migration Naming Convention:**
- Pattern: `m_<major>_<minor>_<patch>_<description>.py`
- Example: `m_0_13_20_auto_discover.py`
- Auto-discovery only imports files matching `m_*.py`

**Related ADRs:**
- None (this is a new pattern for spec-kitty)

**Inspiration from:**
- Django migrations (`django.db.migrations.loader.MigrationLoader`)
- Alembic migrations (`alembic.script.ScriptDirectory`)

**Version:** 0.13.20 (bugfix/architectural improvement)

**Real-world validation:**
- 0.13.20 release preparation: Migration registry incomplete (m_0_14_0 forgotten)
- Post-fix: All 35 migrations auto-discovered without manual imports
- No regressions in existing tests (1841 passed)
