---
title: 'Architecture: Centralized Feature Detection'
description: Prior-design record of the v0.14.0 centralized mission-selection (feature detection) design, superseded by mission 083's canonical mission_id identity model.
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/migrations/mission-id-canonical-identity.md
---
# Architecture: Centralized Feature Detection

**Status**: Implemented (v0.14.0); superseded in part by mission `083-mission-id-canonical-identity-migration`.
**Author**: System Architecture
**Last Updated**: 2026-01-27

> **Note (mission 083+):** This document describes the v0.14.0 feature-detection
> cleanup. It is retained for historical context. The canonical selector as of
> mission `083-mission-id-canonical-identity-migration` is `mission_id` (a ULID),
> resolved through `spec-kitty agent context resolve --mission <handle>`, which
> accepts `mission_id`, `mid8`, or `mission_slug` and returns a structured error
> on ambiguity. Numeric prefixes like `020-feature-a` are **display-only metadata**
> — they are never used for identity or routing. See the
> [mission identity migration runbook](../../migrations/mission-id-canonical-identity.md).

## Problem Statement

Prior to v0.14.0, the spec-kitty codebase had **10 different implementations** of feature detection scattered across multiple modules. This led to:

1. **Non-deterministic behavior**: Commands used "highest numbered" heuristics, causing agents to select the wrong feature when multiple features existed
2. **Inconsistent APIs**: Different modules returned different types (string, Path, tuple, Optional)
3. **Duplicate code**: Exact duplicates existed in multiple files
4. **Poor error messages**: No clear guidance when detection failed
5. **High maintenance burden**: Bugs needed fixing in 10 places

### Specific Bug Example

**Scenario**: User has features `020-feature-a` and `021-feature-b` in `kitty-specs/`. Agent runs `/spec-kitty.plan` to create a plan for feature 020.

**Old Behavior** (v0.13.x):
```python
# core/paths.py used "highest numbered" heuristic
candidates = [(20, "020-feature-a"), (21, "021-feature-b")]
_, slug = max(candidates, key=lambda item: item[0])
return "021-feature-b"  # Wrong! Selects 021 instead of 020
```

**New Behavior** (v0.14.0+):
```python
# core/feature_detection.py is deterministic
if len(features) > 1:
    raise MultipleFeaturesError(
        "Multiple features found, use --mission flag"
    )
```

## Solution: Centralized Feature Detection Module

### Design Principles

1. **Single Source of Truth**: One canonical implementation in `core/feature_detection.py`
2. **Deterministic by Default**: No guessing or heuristics
3. **Explicit When Ambiguous**: Clear error messages guide users to the canonical `--mission` flag
4. **Flexible Modes**: Strict (raise errors) vs lenient (return None)
5. **Rich Results**: FeatureContext dataclass with all relevant information
6. **Well-Tested**: Comprehensive unit and integration tests

### Priority Order

The detection follows a strict priority order:

1. **Explicit `--mission` parameter** (highest priority)
   - User explicitly specifies: `--mission 020-my-feature`
   - Always wins over auto-detection

2. **`SPECIFY_FEATURE` environment variable**
   - Set by user or CI/CD: `export SPECIFY_FEATURE=020-my-feature`
   - Useful for scripting

3. **Git branch name**
   - Pattern: `###-feature-name` or `###-feature-name-WP##`
   - Strips `-WP##` suffix for worktree branches
   - Example: `020-my-feature-lane-a` → `020-my-feature`

4. **Current directory path**
   - Walks up tree looking for `###-feature-name` pattern
   - Handles both `kitty-specs/###-feature-name/` and `.worktrees/###-feature-name-WP##/`

5. **Single feature auto-detect**
   - Only if exactly one feature exists in `kitty-specs/`
   - Disabled with `allow_single_auto=False`

6. **Error with guidance**
   - If multiple features exist and no context: clear error with list of options
   - Error message includes examples of how to specify explicitly

## Architecture

### Core Types

```python
@dataclass
class FeatureContext:
    """Rich result from feature detection."""
    slug: str                    # e.g., "020-my-feature"
    number: str                  # e.g., "020"
    name: str                    # e.g., "my-feature"
    directory: Path              # e.g., Path("kitty-specs/020-my-feature")
    detection_method: str        # e.g., "git_branch", "env_var", "explicit"
```

### Core Functions

```python
def detect_feature(
    repo_root: Path,
    *,
    explicit_feature: str | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mode: Literal["strict", "lenient"] = "strict",
    allow_single_auto: bool = True,
) -> FeatureContext | None:
    """Unified feature detection with configurable behavior."""
```

**Modes**:
- **Strict** (default): Raises `FeatureDetectionError` when detection fails
- **Lenient**: Returns `None` when detection fails (for UI convenience)

**Simplified Wrappers**:
```python
def detect_feature_slug(repo_root: Path, **kwargs) -> str:
    """Returns just the slug string (always strict mode)."""

def detect_feature_directory(repo_root: Path, **kwargs) -> Path:
    """Returns just the directory Path (always strict mode)."""
```

### Error Types

```python
class FeatureDetectionError(Exception):
    """Base exception for feature detection failures."""

class MultipleFeaturesError(FeatureDetectionError):
    """Multiple features exist and no context clarifies which."""
    features: list[str]  # List of detected feature slugs

class NoFeatureFoundError(FeatureDetectionError):
    """No features found in kitty-specs/."""
```

## Migration Strategy

### Phase 1: Create Centralized Module (Non-Breaking)

1. Created `core/feature_detection.py` with new unified implementation
2. Added comprehensive unit tests (32 tests)
3. No existing code changed - purely additive

### Phase 2: Migrate Commands

Replaced 10 scattered implementations with imports from centralized module:

**High-Priority (Agent Commands)**:
- `agent/feature.py` (setup-plan)
- `agent/context.py` (update-context)
- `agent/workflow.py` (implement, review)
- `agent/tasks.py` (all task commands)

**Medium-Priority**:
- `implement.py` (detect_feature_context)
- `acceptance.py` (detect_feature_slug)
- `mission.py` (_detect_current_feature)
- `orchestrator_api/commands.py` (feature resolution for host API commands)

### Phase 3: Cleanup

- Removed duplicate from `acceptance_support.py`
- Deprecated `find_feature_slug()` in `core/paths.py`
- Updated `agent_utils/status.py`

### Phase 4: Template Updates

- Updated `plan.md` template with mission detection instructions
- Created migration to regenerate all 12 agent templates
- Agents now pass `--mission` explicitly to avoid auto-detection

## Breaking Changes

### Removed "Highest Numbered" Fallback

**Old Behavior** (v0.13.x):
```bash
$ cd /repo  # Has 020-feature-a and 021-feature-b
$ spec-kitty implement WP01
# Automatically selected 021-feature-b (highest numbered)
```

**New Behavior** (v0.14.0+):
```bash
$ cd /repo  # Has 020-feature-a and 021-feature-b
$ spec-kitty implement WP01
Error: Multiple features found (2), cannot auto-detect:
  - 020-feature-a
  - 021-feature-b

Please specify explicitly using:
  --mission <mission-slug>  (e.g., --mission 020-feature-a)
  SPECIFY_FEATURE=<feature-slug>  (environment variable)
  Or run from inside a feature directory or worktree
```

### Impact Assessment

**Users Affected**: ~5% (those with multiple features who relied on auto-detection)

**Mitigation**:
1. Clear error message with guidance
2. Multiple ways to specify (`--mission`, env var, directory context)
3. Documentation updated with examples

**Benefits**:
- Correct feature always selected (prevents wrong feature bug)
- Explicit is better than implicit
- Better user experience overall (no silent failures)

## Usage Patterns

### For Command-Line Tools

```python
from specify_cli.core.feature_detection import detect_feature, FeatureDetectionError

try:
    ctx = detect_feature(
        repo_root,
        explicit_feature=feature_flag,  # From --mission parameter
        cwd=Path.cwd(),
        mode="strict"  # Raise error if ambiguous
    )
    print(f"Using feature: {ctx.slug}")
except FeatureDetectionError as e:
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(1)
```

### For UI/Dashboard (Lenient Mode)

```python
from specify_cli.core.feature_detection import detect_feature

# Try to auto-detect, but don't fail if ambiguous
ctx = detect_feature(
    repo_root,
    cwd=Path.cwd(),
    mode="lenient"  # Return None instead of raising
)

if ctx:
    show_kanban_board(ctx.slug)
else:
    show_feature_selector()  # Let user choose
```

### For Backward-Compatible Wrappers

```python
from specify_cli.core.feature_detection import (
    detect_feature_slug as centralized_detect_feature_slug,
    FeatureDetectionError,
)

def detect_feature_slug(repo_root: Path, **kwargs) -> str:
    """Backward-compatible wrapper."""
    try:
        return centralized_detect_feature_slug(repo_root, **kwargs)
    except FeatureDetectionError as e:
        # Convert to module-specific exception for compatibility
        raise AcceptanceError(str(e)) from e
```

## Testing Strategy

### Unit Tests (32 tests)

**Core detection scenarios**:
- Explicit parameter (highest priority)
- Environment variable
- Git branch name (with/without WP suffix)
- Current directory path
- Single feature auto-detect
- Multiple features (strict vs lenient)
- No features found
- Invalid slug format

**Priority order tests**:
- Explicit > env var > git branch > cwd > single auto
- Verify lower priorities skipped when higher priority succeeds

**Error message quality**:
- Multiple features error lists all options
- Error messages mention the canonical `--mission` flag
- Error messages provide examples

### Integration Tests (13 tests)

**No orphaned implementations**:
- Grep validation for old function names
- Import analysis verifies centralized usage
- No "highest numbered" heuristics remain

**Backward compatibility**:
- acceptance.py maintains compatible API
- implement.py returns same tuple format
- Error types converted appropriately

**Command validation**:
- All agent commands accept the canonical mission selector
- Commands call centralized detection
- Error handling works correctly

## Performance

### Benchmarks

**Detection time**: <10ms (single feature, git branch)
**Worst case**: <50ms (multiple features, error with list)

**Comparison to v0.13.x**:
- No performance regression
- Slightly faster due to early exits in priority chain

## Future Enhancements

### Potential Improvements

1. **Caching**: Cache detection results per process
   - Use case: Multiple commands in single session
   - Complexity: Low
   - Benefit: Marginal (detection already fast)

2. **Config-based defaults**: Allow `.kittify/config.yaml` to specify default feature
   - Use case: Projects that mostly work on one feature
   - Complexity: Medium
   - Benefit: Convenience for specific workflows

3. **Fuzzy matching**: Suggest features when user typos slug
   - Use case: `--mission 20-my-feature` → "Did you mean 020-my-feature?"
   - Complexity: Low
   - Benefit: Better UX

4. **MRU (Most Recently Used)**: Track which feature was used last
   - Use case: Auto-select last used feature if ambiguous
   - Complexity: Medium
   - Benefit: Convenience (but less explicit)
   - Concern: Could reintroduce non-determinism

## References

This page is the prior-design record of v0.14.0's centralized feature detection. The runtime
module and its test files (`src/specify_cli/core/feature_detection.py`,
`tests/specify_cli/core/test_feature_detection.py`,
`tests/specify_cli/test_feature_detection_integration.py`) were removed in the Canonical
Context Architecture Cleanup (#347); the surfaces that survive today are:

- **Migration**: `src/specify_cli/upgrade/migrations/m_0_14_0_centralized_feature_detection.py`
- **Original Issue**: #025-cli-event-log-integration (Feature 025, WP01)

## Lessons Learned

### What Worked Well

1. **Single source of truth**: Eliminated duplicate code and inconsistencies
2. **Comprehensive testing first**: 32 unit tests before migration prevented regressions
3. **Gradual migration**: Non-breaking addition first, then migrate gradually
4. **Clear error messages**: Users know exactly what to do when detection fails

### Challenges

1. **Backward compatibility**: Needed wrappers in multiple modules
2. **Test false positives**: Integration tests initially flagged legitimate wrappers
3. **Template propagation**: Updating 12 agent templates required careful migration

### Best Practices

1. **Design for testability**: Dependency injection (cwd, env parameters) enables testing
2. **Fail fast with guidance**: Better to error explicitly than silently do wrong thing
3. **Provide escape hatches**: Multiple ways to specify (flag, env var, context)
4. **Document trade-offs**: Clear explanation of breaking changes and alternatives

## Related ADRs

- **ADR-TBD**: Feature Detection Centralization (this document)
- **ADR-12**: Two-Branch Strategy for SaaS Transformation (context on feature management)

---

**Document History**:
- 2026-01-27: Initial version documenting v0.14.0 centralized feature detection
