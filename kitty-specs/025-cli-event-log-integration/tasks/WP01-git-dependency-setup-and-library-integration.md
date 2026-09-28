---
work_package_id: WP01
title: Git Dependency Setup & Library Integration
dependencies: []
base_branch: 2.x
base_commit: 1e55c89f5fd0f33da7cf4f7b50c68ed65ce742ba
created_at: '2026-01-28T05:30:29.926530+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 0 - Foundation & Dependency Integration
history:
- timestamp: '2026-01-27T00:00:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
- timestamp: '2026-01-28T06:00:00Z'
  action: Review feedback acknowledged and addressed
  agent: claude-sonnet-4.5
  note: Fixed Issue 1 (base_branch metadata) and Issue 2 (CLI entry point check)
authoritative_surface: ''
execution_mode: code_change
mission_id: 01KN2371WQDXDMVSFB0KMF95K1
owned_files:
- docs/development/ssh-deploy-keys.md
- docs/development/ssh-deploy-keys.md\n
- src/specify_cli/cli/app.py
- src/specify_cli/events/__init__.py
- src/specify_cli/events/adapter.py
- src/specify_cli/events/store.py
wp_code: WP01
---

# Work Package Prompt: WP01 – Git Dependency Setup & Library Integration

## ⚠️ IMPORTANT: Review Feedback Status

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_status` field above. If it says `has_feedback`, scroll to the **Review Feedback** section immediately.
- **You must address all feedback** before your work is complete.
- **Mark as acknowledged**: When you understand the feedback, update `review_status: acknowledged`.
- **Report progress**: Update the Activity Log as you address each feedback item.

---

## Review Feedback

**Reviewed by**: Robert Douglass
**Status**: ❌ Changes Requested
**Date**: 2026-01-29

**Issue 1 (critical): Branch base is still not 2.x**
`git merge-base --is-ancestor 2.x HEAD` returns exit code 1 in the WP01 worktree, so the implementation is still not based on `2.x`. This violates the WP constraint and blocks approval.

**How to fix**: Recreate or rebase the WP01 branch on top of `2.x` and re-apply the WP01 commits. Example:
- `git checkout 2.x && git pull`
- `git checkout -b 025-cli-event-log-integration-WP01-2x`
- `git cherry-pick <WP01 commits>` (or `git rebase --onto 2.x <old-base> 025-cli-event-log-integration-WP01`)
- Verify: `git merge-base --is-ancestor 2.x HEAD`

Then update WP metadata base commit to match the new base.


## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

**Primary Goal**: Integrate spec-kitty-events library as a Git dependency with commit pinning per ADR-11 (Dual-Repository Pattern).

**Success Criteria**:
- ✅ `pyproject.toml` declares spec-kitty-events with SSH Git URL and commit hash pinning
- ✅ Fresh clone + `pip install -e .` successfully installs spec-kitty-events library
- ✅ CI/CD pipeline (GitHub Actions) uses SSH deploy key to access private repository
- ✅ Import adapter layer provides clean interface to library types
- ✅ Clear error message with setup instructions if library installation fails

**Priority**: P0 (blocks all other work packages)

**User Story**: US6 - Git Dependency Integration with Commit Pinning

**Independent Test**:
```bash
# Fresh environment
git clone <spec-kitty-repo> /tmp/spec-kitty-test
cd /tmp/spec-kitty-test
git checkout 2.x
pip install -e .

# Should succeed and allow import
python -c "from specify_cli.events.adapter import EventAdapter; print('OK')"
```

---

## Context & Constraints

### ⚠️ CRITICAL: Target Branch

**This work package MUST be implemented on the `2.x` branch (NOT main).**

If the 2.x branch doesn't exist yet, create it NOW:
```bash
git checkout main
git checkout -b 2.x
git push origin 2.x
```

**Verify you're on 2.x before implementing**:
```bash
git branch --show-current  # Must output: 2.x
```

**Why**: 2.x is a greenfield branch incompatible with main (v0.13.x). Per ADR-12, main will become the 1.x maintenance branch (YAML logs). This feature implements events-only architecture on 2.x.

**DO NOT**:
- ❌ Implement on main branch
- ❌ Modify existing code on main
- ❌ Create worktrees from main

### Prerequisites

- **Spec-kitty-events repository**: https://github.com/Priivacy-ai/spec-kitty-events (PRIVATE)
- **Constitution**: `.kittify/memory/constitution.md` - Architecture: Private Dependency Pattern section
- **ADR-11**: `architecture/adrs/2026-01-27-11-dual-repository-pattern.md`
- **ADR-12**: `architecture/adrs/2026-01-27-12-two-branch-strategy-for-saas-transformation.md`
- **Planning decision**: Commit pinning required (not `rev="main"`) for deterministic builds

### Architectural Constraints

**From Constitution (lines 59-132)**:
- MUST use SSH Git URL for private repo access
- MUST use commit hash pinning (not branch names)
- MUST configure SSH deploy key for CI/CD
- MUST NOT commit with local `pip -e ../spec-kitty-events` path dependency

**From Plan (Technical Context)**:
- Library provides: Lamport clocks, CRDT merge rules, event storage adapters
- Adapter layer needed: Translate between library types and CLI types
- Target branch: 2.x only (no 1.x compatibility)

### Key Technical Decisions

1. **Commit Pinning** (Planning Q2 decision): Use specific commit hash, update explicitly
2. **SSH vs HTTPS**: SSH required for CI autonomy (HTTPS would need PAT tokens)
3. **Adapter Pattern**: CLI types wrap library types (loose coupling for future flexibility)

---

## Subtasks & Detailed Guidance

### Subtask T001 – Add spec-kitty-events Git dependency to pyproject.toml

**Purpose**: Declare the library as a Git dependency with commit hash pinning for deterministic builds.

**Steps**:

1. **Get latest commit hash from spec-kitty-events**:
   ```bash
   # Clone the library repo locally (temporary)
   git clone git@github.com:Priivacy-ai/spec-kitty-events.git /tmp/spec-kitty-events
   cd /tmp/spec-kitty-events
   git log -1 --format="%H"  # Copy this commit hash
   ```

2. **Update pyproject.toml**:
   ```toml
   [tool.poetry.dependencies]
   python = "^3.11"
   # ... existing dependencies
   spec-kitty-events = { git = "ssh://git@github.com/Priivacy-ai/spec-kitty-events.git", rev = "abc1234567890..." }
   ```

   **Critical**:
   - Use SSH URL format: `ssh://git@github.com/...` (NOT `https://`)
   - Use `rev` parameter with full commit hash (NOT `branch="main"`)
   - Pin to exact commit (e.g., `rev = "a1b2c3d4e5f6..."`, 40 characters)

3. **Update poetry.lock**:
   ```bash
   poetry lock --no-update
   ```

   This regenerates `poetry.lock` with the new dependency pinned.

4. **Test installation locally**:
   ```bash
   poetry install
   python -c "import spec_kitty_events; print(spec_kitty_events.__version__)"
   ```

**Files**:
- `pyproject.toml` (modify: add spec-kitty-events dependency)
- `poetry.lock` (regenerate via `poetry lock`)

**Validation**:
- [ ] `pyproject.toml` contains SSH Git URL (NOT https)
- [ ] `rev` parameter uses full 40-character commit hash (NOT branch name)
- [ ] `poetry install` succeeds without errors
- [ ] Library imports successfully: `from spec_kitty_events import Event`

**Edge Cases**:
- If poetry.lock merge conflicts occur: Run `poetry lock --no-update` to regenerate
- If SSH key not configured locally: Will fail here (expected), document in T002

---

### Subtask T002 – Document SSH deploy key setup for CI/CD

**Purpose**: Provide clear instructions for configuring SSH deploy keys so CI can access private repo.

**Steps**:

1. **Create documentation file**:
   ```bash
   # Location: docs/development/ssh-deploy-keys.md (new file)
   ```

2. **Write SSH key generation instructions**:
   ```markdown
   # SSH Deploy Key Setup for CI/CD

   ## Purpose

   Spec-kitty depends on the private `spec-kitty-events` library. CI/CD (GitHub Actions) needs an SSH deploy key to clone this repository during builds.

   ## Setup Steps (One-Time)

   ### 1. Generate SSH Key Pair

   ```bash
   ssh-keygen -t ed25519 -C "spec-kitty-ci-deploy-key" -f spec-kitty-events-deploy-key -N ""
   ```

   This creates two files:
   - `spec-kitty-events-deploy-key` (private key - for GitHub Actions secret)
   - `spec-kitty-events-deploy-key.pub` (public key - for spec-kitty-events repo)

   ### 2. Add Public Key to spec-kitty-events Repository

   1. Go to https://github.com/Priivacy-ai/spec-kitty-events/settings/keys
   2. Click "Add deploy key"
   3. Title: "spec-kitty CI/CD Read-Only"
   4. Key: Paste contents of `spec-kitty-events-deploy-key.pub`
   5. **Important**: Leave "Allow write access" UNCHECKED (read-only)
   6. Click "Add key"

   ### 3. Add Private Key to spec-kitty Repository Secrets

   1. Go to https://github.com/Priivacy-ai/spec-kitty/settings/secrets/actions
   2. Click "New repository secret"
   3. Name: `SPEC_KITTY_EVENTS_DEPLOY_KEY`
   4. Value: Paste contents of `spec-kitty-events-deploy-key` (PRIVATE key, entire file)
   5. Click "Add secret"

   ### 4. Delete Local Key Files (Security)

   ```bash
   rm spec-kitty-events-deploy-key spec-kitty-events-deploy-key.pub
   ```

   ## Verification

   After setup, GitHub Actions can access spec-kitty-events. Test by triggering a workflow run (see `.github/workflows/ci.yml`).

   ## Troubleshooting

   **Error: "Permission denied (publickey)"**
   - Check that public key was added to spec-kitty-events repo (Step 2)
   - Check that private key secret name matches exactly: `SPEC_KITTY_EVENTS_DEPLOY_KEY`

   **Error: "Could not read from remote repository"**
   - Verify SSH URL in pyproject.toml uses `ssh://git@github.com/...` format
   - Verify deploy key has read access to spec-kitty-events repository

   ## Key Rotation

   **Rotate every 12 months or immediately if compromised.**

   Follow the same steps above to generate new keys, then:
   1. Add new public key to spec-kitty-events (don't remove old key yet)
   2. Update secret in spec-kitty with new private key
   3. Trigger a test build to verify new key works
   4. Remove old public key from spec-kitty-events
   ```

3. **Reference in CONTRIBUTING.md**:
   Add a link in `CONTRIBUTING.md` under "Development Setup":
   ```markdown
   ### Private Dependencies

   Spec-kitty depends on the private [spec-kitty-events](https://github.com/Priivacy-ai/spec-kitty-events) library. For CI/CD setup, see [SSH Deploy Keys documentation](docs/development/ssh-deploy-keys.md).

   For local development, ensure you have SSH access to the repository.
   ```

**Files**:
- `docs/development/ssh-deploy-keys.md` (new file, ~80 lines)
- `CONTRIBUTING.md` (modify: add link to SSH deploy key docs)

**Validation**:
- [ ] Documentation includes key generation command
- [ ] Instructions for adding public key to spec-kitty-events repo
- [ ] Instructions for adding private key to GitHub Actions secrets
- [ ] Secret name documented as `SPEC_KITTY_EVENTS_DEPLOY_KEY`
- [ ] Security note about deleting local key files after upload

**Parallel?**: Yes - can proceed in parallel with T001

---

### Subtask T003 – Update GitHub Actions workflow to use SSH deploy key

**Purpose**: Configure CI/CD pipeline to use the SSH deploy key for accessing private spec-kitty-events repository.

**Steps**:

1. **Locate workflow file**:
   ```bash
   # .github/workflows/ci.yml (or test.yml, whichever runs pip install)
   ```

2. **Add SSH setup step BEFORE pip install**:
   ```yaml
   # In .github/workflows/ci.yml (or equivalent)

   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         # ... existing checkout step

         - name: Setup SSH for private repository access
           run: |
             mkdir -p ~/.ssh
             echo "${{ secrets.SPEC_KITTY_EVENTS_DEPLOY_KEY }}" > ~/.ssh/id_ed25519
             chmod 600 ~/.ssh/id_ed25519
             ssh-keyscan github.com >> ~/.ssh/known_hosts
           shell: bash

         # ... existing Python setup step

         - name: Install dependencies
           run: |
             pip install poetry
             poetry install
   ```

   **Critical Details**:
   - SSH key must be written to `~/.ssh/id_ed25519` (default SSH key location)
   - Permissions must be `600` (read/write for owner only, SSH requirement)
   - `ssh-keyscan github.com` adds GitHub's host key to known_hosts (prevents interactive prompt)
   - Must run BEFORE `poetry install` step

3. **Add workflow comment documentation**:
   ```yaml
   - name: Setup SSH for private repository access
     # Purpose: spec-kitty depends on private spec-kitty-events library.
     # Uses SSH deploy key stored in GitHub Actions secrets.
     # See docs/development/ssh-deploy-keys.md for setup instructions.
     run: |
       # ... SSH setup commands
   ```

4. **Test the workflow**:
   - Commit changes and push to 2.x branch
   - Monitor GitHub Actions run: https://github.com/Priivacy-ai/spec-kitty/actions
   - Verify "Install dependencies" step succeeds

**Files**:
- `.github/workflows/ci.yml` (or equivalent workflow file - modify)

**Validation**:
- [ ] SSH setup step runs BEFORE pip install
- [ ] Secret name matches documentation: `SPEC_KITTY_EVENTS_DEPLOY_KEY`
- [ ] SSH key written to `~/.ssh/id_ed25519`
- [ ] File permissions set to `600`
- [ ] GitHub's host key added to `~/.ssh/known_hosts`
- [ ] CI build succeeds and installs spec-kitty-events

**Edge Cases**:
- If workflow uses matrix strategy (multiple Python versions): SSH setup must be in each job
- If multiple workflows exist: Update all workflows that run `poetry install`

---

### Subtask T004 – Create import adapter layer for spec-kitty-events library

**Purpose**: Provide a clean interface between spec-kitty-events library types and CLI types, enabling loose coupling.

**Steps**:

1. **Create adapter module**:
   ```bash
   # src/specify_cli/events/adapter.py (new file)
   ```

2. **Implement EventAdapter class**:
   ```python
   """
   Adapter layer for spec-kitty-events library.

   Translates between library types and CLI types, providing loose coupling
   for future flexibility.
   """
   from dataclasses import dataclass
   from datetime import datetime, timezone
   from typing import Any

   # Import from spec-kitty-events library
   try:
       from spec_kitty_events import Event as LibEvent
       from spec_kitty_events import LamportClock as LibClock
       HAS_LIBRARY = True
   except ImportError:
       HAS_LIBRARY = False
       LibEvent = None  # type: ignore
       LibClock = None  # type: ignore


   @dataclass
   class Event:
       """CLI representation of an event (wraps library Event)."""
       event_id: str
       event_type: str
       event_version: int
       lamport_clock: int
       entity_id: str
       entity_type: str
       timestamp: str
       actor: str
       causation_id: str | None
       correlation_id: str | None
       payload: dict[str, Any]

       @classmethod
       def from_lib_event(cls, lib_event: Any) -> "Event":
           """Convert library Event to CLI Event."""
           if not HAS_LIBRARY:
               raise RuntimeError("spec-kitty-events library not installed")

           # Extract fields from library event
           # (Assuming library has similar field names - adjust as needed)
           return cls(
               event_id=str(lib_event.id),
               event_type=lib_event.type,
               event_version=1,  # CLI uses version 1
               lamport_clock=lib_event.clock,
               entity_id=lib_event.entity_id,
               entity_type=lib_event.entity_type or "Unknown",
               timestamp=lib_event.timestamp or datetime.now(timezone.utc).isoformat(),
               actor=lib_event.actor or "unknown",
               causation_id=lib_event.causation_id,
               correlation_id=lib_event.correlation_id,
               payload=lib_event.data or {},
           )

       def to_lib_event(self) -> Any:
           """Convert CLI Event to library Event."""
           if not HAS_LIBRARY:
               raise RuntimeError("spec-kitty-events library not installed")

           # Create library event from CLI fields
           return LibEvent(
               id=self.event_id,
               type=self.event_type,
               clock=self.lamport_clock,
               entity_id=self.entity_id,
               entity_type=self.entity_type,
               timestamp=self.timestamp,
               actor=self.actor,
               causation_id=self.causation_id,
               correlation_id=self.correlation_id,
               data=self.payload,
           )


   @dataclass
   class LamportClock:
       """CLI representation of Lamport clock (wraps library LamportClock)."""
       value: int
       last_updated: str

       def tick(self) -> int:
           """Increment clock and return new value."""
           self.value += 1
           self.last_updated = datetime.now(timezone.utc).isoformat()
           return self.value

       def update(self, remote_clock: int) -> int:
           """Update clock to max(local, remote) + 1."""
           self.value = max(self.value, remote_clock) + 1
           self.last_updated = datetime.now(timezone.utc).isoformat()
           return self.value

       @classmethod
       def from_lib_clock(cls, lib_clock: Any) -> "LamportClock":
           """Convert library LamportClock to CLI LamportClock."""
           if not HAS_LIBRARY:
               raise RuntimeError("spec-kitty-events library not installed")

           return cls(
               value=lib_clock.value,
               last_updated=lib_clock.last_updated or datetime.now(timezone.utc).isoformat(),
           )

       def to_lib_clock(self) -> Any:
           """Convert CLI LamportClock to library LamportClock."""
           if not HAS_LIBRARY:
               raise RuntimeError("spec-kitty-events library not installed")

           return LibClock(
               value=self.value,
               last_updated=self.last_updated,
           )


   class EventAdapter:
       """Main adapter for spec-kitty-events library integration."""

       @staticmethod
       def check_library_available() -> bool:
           """Check if spec-kitty-events library is available."""
           return HAS_LIBRARY

       @staticmethod
       def get_missing_library_error() -> str:
           """Get error message for missing library with setup instructions."""
           return (
               "spec-kitty-events library not installed.\n\n"
               "This library is required for event log functionality.\n\n"
               "Setup instructions:\n"
               "1. Ensure you have SSH access to https://github.com/Priivacy-ai/spec-kitty-events\n"
               "2. Run: pip install -e .\n\n"
               "For CI/CD setup, see: docs/development/ssh-deploy-keys.md\n"
           )
   ```

3. **Create adapter __init__.py**:
   ```python
   # src/specify_cli/events/__init__.py
   """Event log integration package."""

   from .adapter import Event, LamportClock, EventAdapter, HAS_LIBRARY

   __all__ = ["Event", "LamportClock", "EventAdapter", "HAS_LIBRARY"]
   ```

**Files**:
- `src/specify_cli/events/adapter.py` (new file, ~150 lines)
- `src/specify_cli/events/__init__.py` (new file, ~5 lines)

**Validation**:
- [ ] Adapter provides Event and LamportClock classes matching CLI schema (data-model.md)
- [ ] `from_lib_event()` and `to_lib_event()` methods translate between types
- [ ] `HAS_LIBRARY` flag indicates if library is available
- [ ] Clear error message if library missing (with setup instructions)
- [ ] Import succeeds: `from specify_cli.events import Event, LamportClock`

**Edge Cases**:
- Library API changes: Adapter shields CLI code from changes (update only adapter)
- Library not installed: Gracefully handled via HAS_LIBRARY check (error message shown)

**Parallel?**: No - depends on T001 (library must be in pyproject.toml first)

---

### Subtask T005 – Add graceful error handling for missing library

**Purpose**: Provide clear, actionable error message if spec-kitty-events library fails to install.

**Steps**:

1. **Add startup check in CLI entry point**:
   ```python
   # src/specify_cli/cli/app.py (or main.py - wherever CLI initializes)

   from specify_cli.events import EventAdapter

   # At module level (runs on import)
   if not EventAdapter.check_library_available():
       import sys
       print(EventAdapter.get_missing_library_error(), file=sys.stderr)
       sys.exit(1)
   ```

   **Note**: This is aggressive (exits immediately), suitable for 2.x greenfield approach. For gradual rollout, you'd use warnings instead.

2. **Add error handling in EventStore initialization**:
   ```python
   # src/specify_cli/events/store.py (will be created in WP02, but stub for now)

   from specify_cli.events import EventAdapter

   class EventStore:
       def __init__(self, repo_root):
           if not EventAdapter.check_library_available():
               raise RuntimeError(EventAdapter.get_missing_library_error())
           # ... rest of initialization
   ```

3. **Test error message**:
   ```bash
   # Temporarily uninstall library
   pip uninstall spec-kitty-events -y

   # Try to run CLI
   spec-kitty --version

   # Should show clear error with setup instructions
   # Then reinstall: pip install -e .
   ```

**Files**:
- `src/specify_cli/cli/app.py` (modify: add library check)
- `src/specify_cli/events/store.py` (create stub with library check)

**Validation**:
- [ ] CLI shows clear error if library missing (not cryptic ImportError)
- [ ] Error message includes setup instructions
- [ ] Error references docs/development/ssh-deploy-keys.md
- [ ] CLI exits gracefully (not with Python traceback)

**Edge Cases**:
- Library installed but import fails (corrupted install): Shows same error, advises reinstall
- Library version mismatch (future): Could add version check in T004 adapter

**Parallel?**: No - depends on T004 (EventAdapter must exist)

---

## Test Strategy

**No separate test files required** (constitution: tests not explicitly requested).

**Validation approach**:
1. **T001**: Local test - `poetry install` succeeds, library imports
2. **T002**: Documentation review - clear, complete instructions
3. **T003**: CI test - GitHub Actions build succeeds after SSH setup
4. **T004**: Import test - `from specify_cli.events import Event` works
5. **T005**: Error test - Uninstall library, verify clear error message

**Integration test** (covers all subtasks):
```bash
# Fresh environment (e.g., Docker container or VM)
git clone git@github.com:Priivacy-ai/spec-kitty.git /tmp/spec-kitty-test
cd /tmp/spec-kitty-test
git checkout 2.x
pip install -e .

# Should succeed (requires SSH access to spec-kitty-events)
python -c "from specify_cli.events import Event, LamportClock; print('OK')"

# Verify error handling
pip uninstall spec-kitty-events -y
python -c "from specify_cli.events import EventAdapter; print(EventAdapter.get_missing_library_error())"
```

---

## Risks & Mitigations

### Risk 1: SSH deploy key not configured in CI

**Symptom**: GitHub Actions fails with "Permission denied (publickey)"

**Mitigation**:
- T002 provides clear setup instructions
- T003 includes verification step (trigger workflow run)
- T005 error message guides developers to documentation

### Risk 2: Library API changes break integration

**Impact**: Adapter layer (T004) breaks when library updated

**Mitigation**:
- Commit pinning (T001) prevents unexpected breakage
- Adapter pattern (T004) isolates changes to single file
- Document update process in T002 (update commit hash, test, commit)

### Risk 3: Local development without SSH access

**Symptom**: Developers without GitHub SSH keys can't install library locally

**Mitigation**:
- T002 documents SSH key setup for developers
- T005 provides clear error with instructions
- Alternative: Use HTTPS with PAT (not implemented, requires token management)

---

## Definition of Done Checklist

- [ ] T001: pyproject.toml contains SSH Git URL with commit pinning
- [ ] T001: `poetry install` succeeds locally
- [ ] T002: SSH deploy key documentation written (docs/development/ssh-deploy-keys.md)
- [ ] T002: CONTRIBUTING.md references SSH deploy key docs
- [ ] T003: GitHub Actions workflow includes SSH setup step
- [ ] T003: CI build succeeds and installs spec-kitty-events
- [ ] T004: EventAdapter provides Event and LamportClock types
- [ ] T004: Import succeeds: `from specify_cli.events import Event`
- [ ] T005: Clear error message if library missing (not Python traceback)
- [ ] All subtasks completed and validated per independent tests

---

## Review Guidance

**Key Acceptance Checkpoints**:

1. **T001 - Dependency Declaration**:
   - ✓ SSH URL format (`ssh://git@github.com/...`)
   - ✓ Commit hash pinning (40 characters, not branch name)
   - ✓ `poetry lock` regenerated successfully

2. **T002 - Documentation Quality**:
   - ✓ Instructions are clear and complete (can follow without prior knowledge)
   - ✓ Secret name documented correctly (`SPEC_KITTY_EVENTS_DEPLOY_KEY`)
   - ✓ Security considerations included (delete local keys after upload)

3. **T003 - CI Configuration**:
   - ✓ SSH setup runs BEFORE pip install
   - ✓ File permissions correct (600 for private key)
   - ✓ GitHub Actions build succeeds (green check)

4. **T004 - Adapter Design**:
   - ✓ Clean separation between library types and CLI types
   - ✓ Translation methods (`from_lib_event`, `to_lib_event`) implemented
   - ✓ Imports work: `from specify_cli.events import Event`

5. **T005 - Error Handling**:
   - ✓ Error message is clear and actionable (not cryptic)
   - ✓ References documentation (docs/development/ssh-deploy-keys.md)
   - ✓ CLI exits gracefully (no Python traceback)

**Reviewers should**:
- Clone fresh and test `pip install -e .` (verifies T001, T003)
- Read T002 documentation and confirm clarity
- Check T004 adapter matches data-model.md Event schema
- Uninstall library and verify T005 error message

---

## Activity Log

- 2026-01-27T00:00:00Z – system – lane=planned – Prompt created via /spec-kitty.tasks

---
- 2026-01-28T05:35:40Z – unknown – shell_pid=42305 – lane=for_review – Ready for review: All 5 subtasks completed (T001-T005). Library integrated with SSH Git dependency, CI/CD configured, adapter layer created, error handling implemented. Commit: 071910e
- 2026-01-28T05:44:10Z – codex – shell_pid=46237 – lane=doing – Started review via workflow command
- 2026-01-28T05:46:47Z – codex – shell_pid=46237 – lane=planned – Moved to planned
- 2026-01-28T05:56:15Z – codex – shell_pid=46237 – lane=doing – Moved to doing
- 2026-01-28T06:09:50Z – claude-sonnet-4.5 – shell_pid=53191 – lane=for_review – Moved to for_review
- 2026-01-28T06:10:47Z – codex – shell_pid=46237 – lane=doing – Started review via workflow command
- 2026-01-28T06:11:53Z – codex – shell_pid=46237 – lane=planned – Moved to planned
- 2026-01-28T06:13:51Z – codex – shell_pid=46237 – lane=for_review – Moved to for_review
- 2026-01-29T07:45:50Z – codex – shell_pid=46237 – lane=doing – Started review via workflow command
- 2026-01-29T07:46:05Z – codex – shell_pid=46237 – lane=planned – Moved to planned
- 2026-01-30T06:47:16Z – claude-reviewer – shell_pid=25272 – lane=doing – Started review via workflow command
- 2026-01-30T06:48:50Z – claude-reviewer – shell_pid=25272 – lane=done – Review passed: All 5 subtasks complete. Implementation verified on 2.x branch.

## Implementation Command

Since this WP has no dependencies, implement directly from main:

```bash
spec-kitty implement WP01
```

This will create workspace: `.worktrees/025-cli-event-log-integration-WP01/`
