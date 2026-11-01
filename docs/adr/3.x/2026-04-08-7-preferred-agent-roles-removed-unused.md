---
title: 'ADR 7 (2026-04-08): Preferred Agent Roles Removed as Unused Concept'
description: 'Deletes the never-called preferred implementer and reviewer selection API, and migrates the orphaned selection block out of existing config.yaml files.'
status: Accepted
date: '2026-04-08'
doc_status: active
kind: ADR
updated: '2026-04-08T00:00:00Z'
---

## Context and Problem Statement

`spec-kitty init` supported a preference system for routing work to specific AI agents:

* `--preferred-implementer` (`init.py:735`, `init.py:911–937`): Prompted the user to select their preferred AI agent for implementation tasks (e.g., "Claude", "Codex", "Gemini").
* `--preferred-reviewer` (`init.py:736`, `init.py:949–967`): Similarly prompted for a preferred reviewer agent.

These preferences were stored in `AgentSelectionConfig`, serialized to `.kittify/config.yaml` under an `agents.selection` block, and loaded at startup by `load_agent_config()`.

### The Audit Finding

During the code audit for feature 076, a systematic search was conducted for all call sites of the methods that would act on these preferences:

```
select_implementer()  — defined in core/agent_config.py:57–72
select_reviewer()     — defined in core/agent_config.py:75–99
```

**Result: neither method is called anywhere in the codebase.** Not from any CLI command, not from any migration, not from any runtime code, not from any test that exercises actual routing. The `agent config` management CLI (see ADR-6) does not expose either field. The preference data is written to `config.yaml` and read back into memory during startup — and then never consulted.

This means: every developer who answered the "preferred implementer" prompt during `spec-kitty init` provided data that was silently discarded. The system was collecting user preferences and doing nothing with them.

### Pre-Existing Bug Discovered During Audit

The same audit revealed a related data loss bug in `load_agent_config()`:

```python
# Buggy pre-076 code:
agents_data = config_data.get("agents", {})   # Always reads "agents" key
```

Migration `m_2_0_1` had previously renamed the config key from `agents` to `tools`. After that migration ran, `load_agent_config()` silently read from an empty dict (because "agents" no longer existed) and returned default values — losing all agent configuration for projects that had been upgraded. This bug was discovered and fixed in WP01 by reading `tools` first with a fallback to `agents` for pre-migration projects.

The preference audit and the key-rename bug were discovered in the same code path, confirming that the agent config subsystem had not been exercised by any meaningful test coverage.

## Decision Drivers

* **No speculative features:** Implementing a routing system for `select_implementer()` / `select_reviewer()` requires a specification that does not exist. Building the implementation would be speculative.
* **Remove the data collection antipattern:** Collecting user input and silently ignoring it is a user experience failure. If the preference system is not implemented, the prompts should not exist.
* **Reduce the `AgentConfig` dataclass surface:** Removing `AgentSelectionConfig` simplifies serialization, deserialization, documentation, and testing.
* **Clean up config.yaml:** Existing `config.yaml` files contain an `agents.selection` block that will never be read. A migration should remove it to keep configs clean.

## Considered Options

* **Option A: Remove the entire preference layer (chosen)**
* **Option B: Implement the routing feature using the existing preference storage**
* **Option C: Deprecate with a warning, remove in a future release**

## Decision Outcome

**Chosen option: Option A — Remove `AgentSelectionConfig`, `select_implementer()`, `select_reviewer()`, and all `selection` serialization. A cleanup migration removes the orphaned data from existing `config.yaml` files.**

### What Is Removed

| Removed artifact | Location | Notes |
|-----------------|----------|-------|
| `AgentSelectionConfig` dataclass | `core/agent_config.py:28–37` | Entire class deleted |
| `select_implementer()` method | `core/agent_config.py:57–72` | Never called; deleted |
| `select_reviewer()` method | `core/agent_config.py:75–99` | Never called; deleted |
| `selection` block in `save_agent_config()` | `core/agent_config.py:195–196` | No longer written |
| `selection` block in `load_agent_config()` | `core/agent_config.py:158–162` | No longer read |
| `--preferred-implementer` flag | `init.py:735, 911–937` | Flag and selection stage removed |
| `--preferred-reviewer` flag | `init.py:736, 949–967` | Flag and selection stage removed |

### Cleanup Migration 3.2.1

`m_3_2_1_remove_selection_config.py` strips the `agents.selection` block from existing `.kittify/config.yaml` files:

```python
def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
    config_path = project_path / ".kittify" / "config.yaml"
    if not config_path.exists():
        return MigrationResult.skipped("No config.yaml found")

    # Load, strip selection block, write back
    data = yaml.safe_load(config_path.read_text())
    agents = data.get("agents", data.get("tools", {}))
    if "selection" in agents:
        del agents["selection"]
        if not dry_run:
            config_path.write_text(yaml.dump(data))
        return MigrationResult.success("Removed agents.selection block")

    return MigrationResult.skipped("No selection block found")
```

### The Key-Rename Bug Fix (WP01)

The `load_agent_config()` fix is documented here for completeness:

```python
# Before (buggy): only reads "agents" key, silent data loss after m_2_0_1 renames to "tools"
agents_data = config_data.get("agents", {})

# After (fixed): reads "tools" first (current), falls back to "agents" (pre-migration)
agents_data = config_data.get("tools", config_data.get("agents", {}))
```

This fix is in WP01 but is architecturally related to the preference system audit. The preference data was subject to the same silent data loss: after `m_2_0_1` ran, the `selection` block under `agents` was inaccessible because the key had been renamed to `tools`. The data was collected, then silently lost on upgrade, then the methods that would read it were never called anyway.

### Consequences

#### Positive

* `spec-kitty init` no longer prompts for preferences that have no effect.
* `AgentConfig` dataclass is simpler; `core/agent_config.py` is shorter.
* `config.yaml` files are cleaner; no orphaned `selection` block.
* The codebase honestly represents what it can do: no silent data collection.
* Tests for the preference system (which were testing dead code) are removed.

#### Negative

* If a routing feature is implemented in the future, the preference storage must be re-introduced. The data model is not preserved as a placeholder.
* Developers who explicitly set preferences via `--preferred-implementer` had those preferences silently ignored anyway; removing the option makes the situation transparent rather than creating a new loss.

#### Neutral

* The `AgentConfig` class still exists; only the `selection` subfield and its two methods are removed.
* The `agent config add/remove/list` CLI commands (from ADR-6) are unaffected.

### Confirmation

Correct behavior is confirmed when: `spec-kitty init --help` does not list `--preferred-implementer` or `--preferred-reviewer`; `AgentSelectionConfig` does not appear anywhere in `core/agent_config.py`; and `spec-kitty upgrade` on a project with an existing `agents.selection` block removes that block without touching other config values. All three conditions are covered by the test suite.

## Pros and Cons of the Options

### Option A: Remove the entire preference layer (chosen)

Delete `AgentSelectionConfig`, both methods, all serialization, both flags. Cleanup migration removes orphaned config data.

**Pros:**
* Honest codebase: no data is collected that isn't used.
* Simpler `AgentConfig` surface.
* No prompts for non-functional choices.
* Cleanup migration removes orphaned config data from existing projects.

**Cons:**
* If routing is implemented in the future, preference storage must be re-added.

### Option B: Implement the routing feature

Keep `AgentSelectionConfig` and the preference storage, and implement actual routing logic so that `select_implementer()` and `select_reviewer()` are called from the workflow commands.

**Pros:**
* Realizes the intended value of the preference system.
* No data model churn (no removal + re-addition cycle).

**Cons:**
* No specification exists for how routing should work. What happens when the preferred agent is unavailable? How does routing interact with the lane model? How are conflicting preferences resolved across projects?
* Implementing an undocumented feature design adds speculative surface area.
* Feature 076's scope is explicitly limited to cleanup. Implementing a new orchestration capability is out of scope.

**Why Rejected:** Speculative implementation without a specification is a known cause of architectural debt. The routing concept should be specified properly as a future feature before any implementation work begins.

### Option C: Deprecate with a warning, remove in a future release

Print a deprecation notice when `--preferred-implementer` or `--preferred-reviewer` is passed. Remove the flags in a subsequent release.

**Pros:**
* Standard deprecation practice; gives users advance notice.

**Cons:**
* The flags collect data that has never been acted upon. There are no users depending on routing behavior (because routing never existed). Deprecating a non-functional feature is noise.
* The data is subject to silent loss due to the `m_2_0_1` key rename bug. Some users' data was already lost. Deprecation implies users have something to migrate; they do not.
* Extends the presence of dead code for at least one release cycle.

**Why Rejected:** Deprecation is appropriate for functional features with users. Deprecating a data collection prompt that was never connected to any behavior misleads users into thinking there was something to lose. Immediate removal is cleaner and more honest.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — FR-017 (`preferred_implementer` and `preferred_reviewer` removed from data model), FR-018 (`select_implementer()` and `select_reviewer()` methods removed), FR-019 (`AgentSelectionConfig` removed entirely), FR-020 (cleanup migration strips orphaned keys from `config.yaml`)
* **Related ADR:** ADR-6 (2026-01-23-6) — Config-driven agent management (the broader `AgentConfig` model that `AgentSelectionConfig` was a subcomponent of)
* **Code locations:**
  * `src/specify_cli/core/agent_config.py` — `AgentSelectionConfig`, `select_implementer()`, `select_reviewer()`, serialization blocks
  * `src/specify_cli/init.py:735–736, 911–967` — `--preferred-implementer` and `--preferred-reviewer` flag definitions and selection stage
  * `src/specify_cli/upgrade/migrations/m_3_2_1_remove_selection_config.py` — cleanup migration (new)
