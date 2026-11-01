---
title: Vendor spec-kitty-events Library Instead of External PyPI Dependency
description: Vendors the events library into the CLI because PyPI refuses direct git dependencies, trading repository purity for a package that can actually be published.
status: Accepted
date: '2026-01-31'
doc_status: active
kind: ADR
updated: '2026-01-31T00:00:00Z'
---

## Context and Problem Statement

During the 0.13.20 release, PyPI rejected the package upload because `spec-kitty-events` was specified as a direct Git dependency:

```toml
"spec-kitty-events @ git+ssh://git@github.com/Priivacy-ai/spec-kitty-events.git@fc332dda..."
```

PyPI's policy prohibits direct Git dependencies because:
- They cannot be resolved reliably by pip
- They may point to private repositories
- They lack proper semantic versioning
- They bypass PyPI's security and trust mechanisms

This blocked the release process, requiring an immediate decision on how to handle the `spec-kitty-events` dependency.

## Decision Drivers

- **Release urgency**: 0.13.20 needs to ship immediately with ADR-18 fixes
- **Package complexity**: Maintaining two separate PyPI packages adds overhead
- **Distribution simplicity**: Users prefer single `pip install` command
- **Future extensibility**: Events library will be used extensively in future features
- **Development workflow**: Events code is tightly coupled to spec-kitty internals
- **PyPI policy compliance**: Must eliminate Git dependencies to publish

## Considered Options

1. **Publish spec-kitty-events as separate PyPI package**
2. **Vendor spec-kitty-events into spec-kitty** (CHOSEN)
3. **Make spec-kitty-events an optional dependency**

## Decision Outcome

**Chosen option:** "Vendor spec-kitty-events into spec-kitty", because it provides the simplest distribution model, eliminates the need to maintain two PyPI packages, and ensures all users get the events functionality without extra installation steps.

### Implementation

- Copied `spec-kitty-events/src/spec_kitty_events/` to `spec-kitty/src/specify_cli/spec_kitty_events/`
- Converted all imports to relative imports (`.models`, `.storage`, etc.)
- Removed Git dependency from `pyproject.toml`
- Added `python-ulid>=1.1.0` dependency (required by events library)
- Updated `adapter.py` to import from vendored location: `from specify_cli.spec_kitty_events import ...`

### Consequences

#### Positive

- **Single package distribution**: Users install one package (`spec-kitty-cli`), get all functionality
- **No PyPI publishing overhead**: Don't need to maintain, version, and publish two packages
- **No dependency resolution issues**: Everything bundled together, no version conflicts
- **Faster releases**: Changes to events code don't require coordinated releases
- **Simplified CI/CD**: One release workflow, one set of credentials
- **Better for private development**: Can iterate on events without public API commitments

#### Negative

- **Larger package size**: Adds ~30KB to distribution (negligible)
- **Tighter coupling**: Events library can't be used independently by other projects
- **Harder to extract later**: If we need to separate it, requires migration
- **Duplicates pydantic dependency**: Both spec-kitty and events use pydantic (but same version range)

#### Neutral

- **Code organization**: Events code lives in `specify_cli/spec_kitty_events/` subdirectory
- **Import paths change**: From `spec_kitty_events` to `specify_cli.spec_kitty_events`
- **Version coupling**: Events version (0.1.0-alpha) now tied to spec-kitty version

### Confirmation

Success metrics:
- ✅ 0.13.20 published to PyPI without errors
- ✅ All 1,886 tests passing in CI
- ✅ `pip install spec-kitty-cli` works without additional setup
- ✅ Events functionality works via adapter layer
- ✅ No import errors from vendored module

Confidence level: **High** - This is standard practice for Python packages that include tightly-coupled utilities.

## Pros and Cons of the Options

### Publish spec-kitty-events as separate PyPI package

**Pros:**

- Independent versioning - can release events updates without spec-kitty release
- Reusable by other projects - events library available to ecosystem
- Cleaner separation of concerns - clear API boundary between packages
- Smaller individual packages - users who don't need events can skip it

**Cons:**

- **Doubled maintenance burden** - must maintain two PyPI projects, two release workflows, two sets of credentials
- **Coordinated releases required** - breaking changes in events require synchronized releases
- **User friction** - two `pip install` commands or complex dependency specification
- **Version compatibility complexity** - must document which spec-kitty versions work with which events versions
- **CI/CD complexity** - need SSH deploy keys or publish events first for every CI run

### Vendor spec-kitty-events into spec-kitty (CHOSEN)

**Pros:**

- **Single package distribution** - `pip install spec-kitty-cli` gets everything
- **Simplified maintenance** - one release workflow, one version number
- **No dependency resolution** - everything bundled, no version conflicts
- **Faster iteration** - change events code without public API stability concerns
- **Immediate PyPI compliance** - eliminates Git dependency issue

**Cons:**

- Larger package size - adds ~30KB (negligible for modern systems)
- Not independently reusable - other projects can't use events library
- Tighter coupling - events changes require spec-kitty release
- Harder to extract later - would require migration if we need separation

### Make spec-kitty-events an optional dependency

**Pros:**

- Users can choose whether to install events functionality
- Keeps package size minimal for users who don't need events
- Optional extras pattern (`pip install spec-kitty-cli[events]`) is standard

**Cons:**

- **Doesn't solve PyPI issue** - optional dependencies still can't be Git URLs
- Feature detection complexity - need runtime checks for events availability
- User confusion - "which features need events?" not obvious
- Testing complexity - must test both with and without events installed
- Documentation burden - must explain optional installation clearly

## More Information

**Related Decisions:**
- Feature 025 (CLI Event Log Integration) - Introduced dependency on spec-kitty-events
- ADR-18 (Merged Single-Parent Dependency Detection) - Shipped in 0.13.20 alongside this change

**References:**
- PyPI Core Metadata Specification: https://packaging.python.org/specifications/core-metadata
- PEP 440 (Version Identification): https://peps.python.org/pep-0440/
- Original spec-kitty-events repo: https://github.com/Priivacy-ai/spec-kitty-events (now archived/vendored)

**Implementation:**
- Commits: 879d812d (vendor code), 0dcd7c0b (fix imports)
- Release: v0.13.20
- Files affected: `src/specify_cli/spec_kitty_events/`, `pyproject.toml`, `src/specify_cli/events/adapter.py`

**Alternatives rejected:**
- Forking events library to separate PyPI package
- Using git submodules (still wouldn't solve PyPI issue)
- Implementing events functionality directly in spec-kitty (duplicates mature code)
