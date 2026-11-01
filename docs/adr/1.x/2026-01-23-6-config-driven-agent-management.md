---
title: 'ADR 6: Config-Driven Agent Management'
description: Makes .kittify/config.yaml the single source of truth for which AI agents a project supports, so upgrades stop resurrecting directories the user deleted.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-23'
---

## Context

Spec-kitty supports 12 AI agents (Claude, Copilot, Gemini, Cursor, Qwen, OpenCode, Windsurf, Codex, Kilocode, Augment, Roo, Amazon Q), each with their own slash command directories (`.claude/commands/`, `.github/prompts/`, etc.). Prior to this decision, there was a fundamental architectural flaw in how agent directories were managed:

### The Problem

1. **Dual Source of Truth (Conflicting)**
   - `.kittify/config.yaml` tracked `available` agents (user's selection from init)
   - Filesystem presence indicated which agents exist
   - Migrations used hardcoded `AGENT_DIRS` list (ignored config)
   - These three sources often conflicted

2. **Migrations Recreated Deleted Agents**
   ```python
   # OLD (broken) behavior:
   if not agent_dir.exists():
       agent_dir.mkdir(parents=True)  # Recreates deleted dirs
   ```
   Users deleted unwanted agent directories, but migrations recreated them on upgrade.

3. **No Official Agent Management**
   - No CLI commands to add/remove agents after `spec-kitty init`
   - Users had to manually delete directories + edit config.yaml
   - Undocumented, error-prone, non-discoverable

4. **Code Duplication**
   - `AGENT_DIRS` list duplicated across 8 migrations
   - Risk of inconsistency if one migration updated but others didn't

### Real-World Impact

```bash
# User workflow that failed:
spec-kitty init myproject --ai opencode  # Select only opencode
cd myproject
rm -rf .claude .codex .gemini  # Delete unwanted agents
spec-kitty upgrade  # BUG: Recreated all deleted agents!
```

User reported: *"I only want opencode, but every upgrade recreates 11 agent directories I don't use."*

## Decision

**We make `.kittify/config.yaml` the single source of truth for agent configuration, and provide official CLI commands for agent management.**

### Architectural Changes

#### 1. Single Source of Truth: config.yaml

**Before:**
- Filesystem presence = source of truth
- config.yaml ignored by migrations

**After:**
- **config.yaml is canonical**
- Filesystem is *derived* from config
- Migrations read config, respect user's selection

#### 2. Centralized AGENT_DIRS

**Before:**
```python
# Duplicated in 8 files:
AGENT_DIRS = [
    (".claude", "commands"),
    # ... 12 agents
]
```

**After:**
```python
# m_0_9_1_complete_lane_migration.py (canonical source)
AGENT_DIRS = [...]  # Defined once
AGENT_DIR_TO_KEY = {
    ".claude": "claude",
    ".github": "copilot",  # Special mapping
    # ...
}

def get_agent_dirs_for_project(project_path: Path) -> list:
    """Get agent dirs respecting config.yaml."""
    config = load_agent_config(project_path)
    if not config.available:
        return list(AGENT_DIRS)  # Legacy fallback

    # Filter to only configured agents
    return [
        (root, subdir) for root, subdir in AGENT_DIRS
        if AGENT_DIR_TO_KEY[root] in config.available
    ]

# All 8 migrations import this:
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project
```

#### 3. Official Agent Management CLI

```bash
# New commands:
spec-kitty agent config list      # Show configured agents
spec-kitty agent config add <agents>   # Add agents to project
spec-kitty agent config remove <agents>  # Remove agents from project
spec-kitty agent config status    # Show configured vs present (orphaned)
spec-kitty agent config sync      # Sync filesystem with config
```

**Implementation:**
- Creates/deletes agent directories
- Updates config.yaml atomically
- Copies mission templates on add
- Validates agent keys

#### 4. Config-Aware Migrations

**Updated 8 migrations:**
- `m_0_10_1_populate_slash_commands.py`
- `m_0_10_2_update_slash_commands.py`
- `m_0_10_6_workflow_simplification.py`
- `m_0_10_14_update_implement_slash_command.py`
- `m_0_11_1_improved_workflow_templates.py`
- `m_0_11_1_update_implement_slash_command.py`
- `m_0_11_2_improved_workflow_templates.py`
- `m_0_11_3_workflow_agent_flag.py`

**Pattern:**
```python
def apply(self, project_path: Path, dry_run: bool = False):
    # OLD:
    for agent_root, subdir in self.AGENT_DIRS:  # All 12 hardcoded

    # NEW:
    agent_dirs = get_agent_dirs_for_project(project_path)  # Config-aware
    for agent_root, subdir in agent_dirs:
        agent_dir = project_path / agent_root / subdir
        if not agent_dir.exists():
            continue  # Respect deletions (don't recreate)
```

## Consequences

### Positive

1. **User Experience**
   - Migrations respect user's agent selection
   - Official, discoverable agent management commands
   - No more surprise directory recreation

2. **Correctness**
   - Single source of truth eliminates conflicts
   - config.yaml explicitly tracks user intent
   - Migrations honor deletions

3. **Maintainability**
   - AGENT_DIRS defined once (DRY principle)
   - Easier to add new agents (update in one place)
   - Clear ownership: config.yaml owns agent selection

4. **Backward Compatibility**
   - Legacy projects without config fallback to all agents
   - Existing workflows unchanged
   - Graceful degradation

### Negative

1. **Migration Complexity**
   - Migrations now have conditional logic (config-aware)
   - Must handle legacy projects (no config.yaml)
   - Fallback paths increase code complexity

2. **Testing Burden**
   - Must test with/without config.yaml
   - Must test config-aware filtering
   - Integration tests for upgrade path

3. **Documentation Overhead**
   - Users need to learn new commands
   - Migration guide for 0.11.0 users
   - ADR to explain architectural decision

### Risks

1. **Fallback Behavior**
   - If config.yaml missing or corrupt, defaults to all 12 agents
   - Could recreate deleted agents if config lost
   - **Mitigation:** Repair command to regenerate config

2. **Partial Migration**
   - Some migrations updated, others not (if incomplete)
   - Could lead to inconsistent behavior
   - **Mitigation:** All 8 migrations updated atomically

## Alternatives Considered

### Alternative 1: Filesystem-Only (Status Quo)

**Approach:** Keep filesystem presence as source of truth, ignore config.yaml.

**Pros:**
- Simple, no conditional logic
- Self-documenting (directory exists = agent enabled)

**Cons:**
- No way to distinguish "never had" from "deleted"
- Migrations must either recreate all or skip all
- User deletions not respected

**Why Rejected:** Breaks user expectations when upgrades recreate deleted agents.

### Alternative 2: Dual Tracking (Config + Manifest)

**Approach:** Maintain both config.yaml and `.kittify/agents.json` manifest.

**Pros:**
- Explicit tracking of initialization state
- Can distinguish "never added" from "removed"

**Cons:**
- Overengineering - config.yaml already exists
- Two files to keep in sync
- More failure modes (what if they diverge?)

**Why Rejected:** config.yaml already tracks `available` agents; adding a second file is unnecessary complexity.

### Alternative 3: Implicit Detection (Heuristics)

**Approach:** Detect user intent from directory names, gitignore patterns, etc.

**Pros:**
- No config file needed
- Works without explicit tracking

**Cons:**
- Fragile (heuristics can be wrong)
- Hard to debug when detection fails
- User intent not explicit

**Why Rejected:** Implicit behavior is confusing and error-prone.

## Implementation Notes

### Agent Key Mapping

Some agents have special directory mappings:

| Agent Key | Directory | Reason |
|-----------|-----------|--------|
| `copilot` | `.github` | GitHub Copilot uses .github/prompts |
| `auggie` | `.augment` | Shorter config key |
| `q` | `.amazonq` | Amazon Q branding |

**Mapping:**
```python
AGENT_DIR_TO_KEY = {
    ".github": "copilot",
    ".augment": "auggie",
    ".amazonq": "q",
    # ... standard mappings (key = dir.lstrip("."))
}
```

### Legacy Project Support

Projects without config.yaml fall back to all 12 agents:

```python
def get_agent_dirs_for_project(project_path: Path):
    try:
        config = load_agent_config(project_path)
        if not config.available:
            return list(AGENT_DIRS)  # Fallback for empty config
        return filter_by_config(config.available)
    except Exception:
        return list(AGENT_DIRS)  # Fallback for missing/corrupt config
```

This ensures existing projects don't break on upgrade.

## Testing

**Unit Tests (20 tests):**
- `tests/specify_cli/cli/commands/test_agent_config.py`
- Tests all CLI commands (list, add, remove, status, sync)
- Tests special agent key mappings
- Tests error handling

**Integration Tests (11 tests):**
- `tests/specify_cli/test_agent_config_migration.py`
- Tests `get_agent_dirs_for_project()` helper
- Tests migration respects config
- Tests migration doesn't recreate deleted agents
- Tests legacy project fallback
- Tests dry-run behavior

## Related Decisions

- **ADR 2:** Explicit base branch tracking (similar config-driven approach)
- **ADR 3:** Centralized workspace context storage (single source of truth pattern)

## References

- Issue: *"Migrations recreate deleted agent directories"*
- PR: *"fix: Agent management architecture - config-driven migrations & CLI commands"*
- Plan: `/UPGRADE_AGENT_DIRECTORY_RECREATION_ISSUE.md`
- Commit: `b74536b`
