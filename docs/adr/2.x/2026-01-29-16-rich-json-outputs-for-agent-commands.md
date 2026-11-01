---
title: Rich JSON Outputs for Agent Commands
description: Expands agent-facing JSON with commit hashes and touched-file lists so an agent can confirm what actually happened instead of inferring it from a dirty tree.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-29'
---

## Context and Problem Statement

Agents rely on JSON output from spec-kitty commands to determine next actions. However, the outputs were too vague, causing confusion when unrelated files were dirty.

**Real example from ~/tmp:**
```
Agent: Run finalize-tasks
Output: {"result": "success", "updated_wp_count": 0}

Agent: Did the commit happen? Let me check...
Git status: Shows 41 deleted template files (UNRELATED)
Agent: Must have failed! Let me commit again...
Git: "nothing to commit" for kitty-specs/
Agent: 🤔 Confused - did my commit work or not?
```

**Root cause:** Vague JSON output didn't confirm:
- Did the commit actually happen?
- What was the commit hash (for verification)?
- Which files were committed?
- Why are there dirty files (related or unrelated)?

**Question:** Should agent commands provide **explicit verification data** in JSON output instead of vague status messages?

## Decision Drivers

- **Agent decision-making** - LLMs need explicit confirmation, not implicit success
- **Debugging** - Agents should be able to verify operations succeeded
- **Unrelated dirty files** - Common in repos (templates, config, experimental code)
- **Idempotency** - Agents should know when operation already completed
- **Verification** - Agents should check results without re-running operations

## Considered Options

- **Option 1:** Rich JSON with commit_hash, commit_created, files_committed
- **Option 2:** Verbose mode flag (--verbose adds details)
- **Option 3:** Separate verify command (spec-kitty verify finalize-tasks)
- **Option 4:** Status quo (vague "success" message)

## Decision Outcome

**Chosen option:** "Option 1: Rich JSON outputs", because:
- Explicit confirmation (commit_created: true/false)
- Verifiable (commit_hash for git verification)
- Clear (files_committed lists what changed)
- No extra commands needed (all in one response)
- Prevents redundant operations (agent checks commit_created)

### Consequences

#### Positive

- **Explicit confirmation** - commit_created: true means commit happened
- **Verifiable results** - commit_hash for git rev-parse verification
- **Clear scope** - files_committed shows exactly what changed
- **Prevents confusion** - Unrelated dirty files don't mislead agent
- **Idempotency check** - commit_created: false means already done
- **Debugging-friendly** - JSON contains all info needed to verify operation

#### Negative

- **Larger JSON payloads** - More fields (commit_hash is 40 chars, files_committed is array)
- **Breaking change** - Agents relying on old schema need updates
- **Not all commands updated** - Only finalize-tasks enhanced so far (more work needed)
- **Complexity** - More logic to populate additional fields

#### Neutral

- **Backward compatibility** - Old fields still present (result, updated_wp_count)
- **JSON only** - Human output unchanged (separate logic)
- **Optional fields** - commit_hash can be null if no commit created
- **Extensible pattern** - Can apply to other commands (move-task, mark-status)

### Confirmation

We validated this decision by:
- ✅ 6 tests for finalize-tasks JSON output
- ✅ Test simulating ~/tmp scenario (unrelated dirty files)
- ✅ commit_created prevents redundant commits
- ✅ commit_hash enables verification
- ✅ files_committed provides clarity on scope

## Pros and Cons of the Options

### Option 1: Rich JSON outputs (CHOSEN)

Add commit_hash, commit_created, files_committed to JSON response.

**Pros:**
- Explicit: Agent knows if commit happened
- Verifiable: Can check git rev-parse HEAD = commit_hash
- Clear scope: files_committed lists what changed
- One response: All info in JSON (no follow-up needed)
- Prevents confusion: Distinguishes related from unrelated changes

**Cons:**
- Larger JSON: More data to transmit
- Breaking change: Requires agent updates
- Code complexity: More fields to populate

### Option 2: Verbose mode flag

Add --verbose flag to include details.

**Pros:**
- Opt-in: Agents choose verbosity level
- No breaking change: Default behavior unchanged
- Smaller default response

**Cons:**
- Agents must know to use --verbose
- Two modes to maintain
- Still doesn't prevent confusion (agent might not use it)

### Option 3: Separate verify command

Add spec-kitty verify finalize-tasks to check results.

**Pros:**
- Separation of concerns
- No changes to existing command

**Cons:**
- Two commands instead of one
- Agent must know to run verify
- Duplicates logic (finalize-tasks knows what it did)
- Slower (extra command execution)

### Option 4: Status quo

Keep vague "success" message.

**Pros:**
- No changes needed
- Minimal JSON payload

**Cons:**
- Agents get confused by unrelated dirty files
- No verification mechanism
- Cannot distinguish "already done" from "just done"
- Poor debugging experience

## More Information

**Implementation:**
- `src/specify_cli/cli/commands/agent/feature.py::finalize_tasks()` (enhanced)
- JSON schema:
  ```json
  {
    "result": "success",
    "commit_created": true,           // NEW: Explicit boolean
    "commit_hash": "5030c9c98d...",  // NEW: Verification SHA
    "files_committed": [              // NEW: Scope clarity
      "kitty-specs/.../tasks.md",
      "kitty-specs/.../WP01.md",
      ...
    ],
    "updated_wp_count": 2             // Original field
  }
  ```

**Tests:**
- `tests/integration/test_finalize_tasks_json_output.py` (6 tests)
- test_json_output_prevents_agent_confusion - Simulates ~/tmp scenario

**Template Updates:**
- `src/specify_cli/missions/software-dev/command-templates/tasks.md`
- Added: "DO NOT commit after finalize-tasks (commits automatically)"
- Added: "Check commit_created and commit_hash from JSON"

**Future Enhancements:**
- Apply to move-task, mark-status (status commit confirmations)
- Apply to implement (worktree creation confirmation)
- Apply to merge (merge commit hash and files)

**Related ADRs:**
- ADR-15: Merge-First Suggestion (reduces need for auto-merge, but this improves fallback UX)

**Version:** 0.13.8 improvement (agent UX enhancement)

**Pattern:** "Explicit Confirmation over Implicit Success" - Agents need verification data, not vague status
