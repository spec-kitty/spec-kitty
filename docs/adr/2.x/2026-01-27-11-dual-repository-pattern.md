---
title: Dual-Repository Pattern for Private spec-kitty-events Dependency
description: Keeps the shared events library in its own private repository, consumed as a commit-pinned git dependency, so CI stays autonomous and the CLI repo stays public.
status: Accepted
date: '2026-01-27'
doc_status: active
kind: ADR
updated: '2026-01-27T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty is transitioning from a local-only CLI tool to a distributed SaaS platform on the **2.x branch** (see ADR-12: Two-Branch Strategy). The event sourcing library (`spec-kitty-events`) built in Feature 003 must be shared between:
- **spec-kitty CLI (2.x branch)** (public repository, private dependency during dev)
- **spec-kitty Django** (future SaaS backend, private)

The library provides Lamport clocks, CRDT merge rules, and conflict detection - solving the Last-Write-Wins data loss problem discovered in Feature 002.

**Branch Context:**
- **1.x/main branch**: Local-only CLI, NO spec-kitty-events dependency (YAML activity logs)
- **2.x branch**: SaaS transformation, HAS spec-kitty-events dependency (event sourcing)
- **Why separate**: Architectures are incompatible (cannot coexist in single branch)

**Constraints:**
- spec-kitty is PUBLIC (GitHub + PyPI)
- spec-kitty-events is PRIVATE (MVP phase, will open source later)
- Solo maintainer (no team coordination overhead)
- CI/CD must work autonomously (no laptop dependency)
- **2.x branch only** - This dependency applies ONLY to 2.x (SaaS transformation); 1.x/main remains dependency-free (local-only CLI)

**Question:** How do we structure repositories and manage the private dependency for the 2.x branch while keeping 1.x simple?

## Decision Drivers

- **CI/CD autonomy** - Builds must work without developer's laptop
- **Deterministic builds** - Same code every time (no "works on my machine")
- **Private during MVP** - Events library hidden until stable
- **PyPI compatibility** - Public users can install spec-kitty-cli
- **Future open source path** - Clean transition when events goes public
- **Solo developer simplicity** - No complex infrastructure overhead

## Considered Options

- **Option 1:** Dual-repository with Git dependency + commit pinning
- **Option 2:** Monorepo (single repository for both)
- **Option 3:** Git submodule
- **Option 4:** Private PyPI index (Gemfury, AWS CodeArtifact)
- **Option 5:** Vendoring from day 1

## Decision Outcome

**Chosen option:** "Dual-repository with Git dependency + commit pinning", because it:
- Enables CI/CD autonomy (no laptop needed)
- Provides deterministic builds (commit hash = exact behavior)
- Keeps events private while CLI is public
- Requires no infrastructure (no private PyPI)
- Has clean path to open source (just remove vendoring step)

### Consequences

**IMPORTANT**: This pattern applies to the **2.x branch only**. The 1.x/main branch remains dependency-free (local-only tool). See ADR-12 for branch strategy.

#### Positive

- **CI/CD autonomy** - Deploy key + Git dependency = fully automated builds (2.x branch)
- **Deterministic** - Commit hash pinning guarantees same behavior
- **Explicit integration points** - You control when events updates land
- **Private during MVP** - Events stays hidden, CLI remains public on PyPI
- **Clean transition** - Remove vendoring when events goes public
- **Shared library** - CLI (2.x) and Django use same logic (no code duplication)
- **1.x unaffected** - Main branch stays simple (no private dependencies)

#### Negative

- **Manual commit updates** - Each events change requires updating pyproject.toml
- **SSH key management** - Deploy key needs rotation every 12 months
- **Vendoring complexity** - PyPI release requires vendor script
- **Two-repo coordination** - Feature branches must be manually synchronized

#### Neutral

- **No local pip -e** - Forces rigorous workflow but slows rapid iteration
- **Git dependency size** - Clones full repo history (but small <5MB)

### Confirmation

**Validation signals:**
- CI builds pass without manual intervention (autonomy achieved)
- No "works on my machine" bugs (determinism achieved)
- PyPI users can install without GitHub access (vendoring works)
- Clean transition when events goes public (no major refactor)

**Confidence level:** High - Similar to how many open source projects handle private/vendored dependencies during development.

## Pros and Cons of the Options

### Option 1: Dual-Repository + Git Dependency

**CHOSEN OPTION** - Implemented on 2.x branch only.

Git dependency in pyproject.toml with commit hash pinning:
```toml
# In pyproject.toml (2.x branch only)
spec-kitty-events = { git = "ssh://git@github.com/Priivacy-ai/spec-kitty-events.git", rev = "abc1234..." }
```

**Branch-Specific Implementation:**
- **2.x branch**: Has Git dependency (event sourcing architecture)
- **1.x/main branch**: NO dependency (local-only, YAML logs)
- **Why separate**: Per ADR-12, architectures are incompatible (cannot coexist)

**Pros:**

- CI/CD works autonomously (no local paths) - 2.x branch
- Deterministic builds (exact commit hash)
- No infrastructure costs ($0/month)
- Forces explicit integration points (good discipline)
- Clean path to open source
- **1.x simplicity preserved** - Main branch stays dependency-free

**Cons:**

- Manual commit hash updates (2.x branch maintenance)
- SSH deploy key setup required (one-time per repo)
- Vendoring step for PyPI releases (deferred to 2.x release feature)
- Two-repo branch coordination (2.x feature branches only)

### Option 2: Monorepo

Single repository with both CLI and events as packages.

**Pros:**

- Single clone, easier local dev
- Atomic commits across components
- No Git dependency complications

**Cons:**

- ❌ **Cannot make events private while keeping CLI public** (deal-breaker)
- All contributors see events code (violates privacy requirement)
- Release complexity (two packages from one repo)

### Option 3: Git Submodule

Events as submodule in `external/spec-kitty-events/`.

**Pros:**

- Explicit version pinning (commit in .gitmodules)
- No SSH setup for CI (submodule handles it)

**Cons:**

- ❌ Complex developer onboarding (`git submodule update --init`)
- Easy to forget `git submodule update` (silent breakage)
- Path dependency breaks CI without submodule
- Still requires vendoring for PyPI

### Option 4: Private PyPI Index

Host spec-kitty-events on private PyPI (Gemfury, AWS CodeArtifact).

**Pros:**

- Standard pip/poetry workflow (no Git deps)
- Version ranges and semantic versioning
- Good for larger teams

**Cons:**

- ❌ Infrastructure overhead (setup + maintenance)
- ❌ Cost ($50-200/month hosted, $0-500/month AWS)
- ❌ Auth setup for CI and developers
- ❌ Overkill for solo developer

### Option 5: Vendoring from Day 1

Copy events code into `src/specify_cli/_vendored/events/`.

**Pros:**

- Zero external dependencies
- Works on PyPI without complications

**Cons:**

- ❌ Loses version control for events
- ❌ Hard to sync changes between CLI and Django
- ❌ No shared test suite (divergence risk)
- ❌ Violates DRY (code duplication)

## More Information

**Implementation details:**

**Branch-Specific Application (CRITICAL):**
- **2.x branch**: Git dependency with spec-kitty-events (implemented in Feature 025)
  - Location: `pyproject.toml` on 2.x branch
  - Created: 2026-01-27 (branch created from main at v0.13.7)
  - Installs: `poetry install` on 2.x requires SSH access to spec-kitty-events

- **1.x/main branch**: NO dependency on spec-kitty-events (local-only, YAML logs)
  - Location: `pyproject.toml` on main does NOT include spec-kitty-events
  - Installs: `poetry install` on main works without SSH key
  - Future: main becomes 1.x maintenance branch (no event sourcing)

- **Why separate**: Per ADR-12, branches have incompatible architectures (event sourcing vs YAML logs)

**Git Dependency Configuration (2.x branch only):**
- File: `pyproject.toml` (2.x branch)
- Format: `spec-kitty-events = { git = "ssh://git@github.com/Priivacy-ai/spec-kitty-events.git", rev = "<commit-hash>" }`
- Commit pinning: MUST use full 40-char hash (NOT branch name, NOT "main")
- Deploy key: GitHub Settings > Deploy Keys (read-only to spec-kitty-events)
- Secret name: `SPEC_KITTY_EVENTS_DEPLOY_KEY`
- CI workflow: `.github/workflows/ci.yml` on 2.x branch (SSH setup before pip install)

**PyPI Release Strategy (2.x branch, future):**
- Vendoring script: `scripts/vendor_and_release.py` (deferred to "2.x Release Preparation" feature, NOT Feature 025)
- Why needed: PyPI users don't have GitHub access to private repo
- Process: Vendor events library into CLI → build wheel → publish to PyPI
- When: Not until 2.x approaches beta/stable release

**Documentation:**
- Charter: `.kittify/memory/charter.md` (Architecture: Private Dependency Pattern, lines 46-132)
- ADR-12: `architecture/2.x/adr/2026-01-27-12-two-branch-strategy-for-saas-transformation.md`
- Setup guide: `docs/development/ssh-deploy-keys.md` (created in Feature 025 WP01 T002)
- Dependency updates: `CONTRIBUTING.md` (documented in Feature 025 WP08 T044)

**Related decisions:**
- **ADR-12**: Two-Branch Strategy for SaaS Transformation (defines why 2.x branch exists and why it's separate from main)
- Feature 001: SaaS Transformation Research (validated 4-phase roadmap)
- Feature 002: Event Log Storage Research (identified LWW flaw requiring event sourcing)
- Feature 003: Event Log Library (built spec-kitty-events v0.1.0-alpha in separate repo)
- Feature 025: CLI Event Log Integration (implements this ADR on 2.x branch)

**Branch workflow:**
```bash
# For 2.x development (event sourcing features):
git checkout 2.x
poetry install  # Requires SSH access to spec-kitty-events

# For 1.x maintenance (stable fixes):
git checkout main
poetry install  # No private dependencies, works immediately
```

**Future considerations:**
- Open source events library when stable (6+ months, no major bugs)
- Consider private PyPI if team grows beyond solo developer
- Alternatively, merge to monorepo if privacy requirement relaxes

**Code references:**
- spec-kitty-events: https://github.com/Priivacy-ai/spec-kitty-events (private)
- pyproject.toml: Git dependency declaration
- .github/workflows/: CI configuration with deploy key setup
