# Common Failure Signatures

Known failure patterns for Spec Kitty 2.0.11+ installations with deterministic
recovery steps.

---

## 1. Missing Skill Root

**Symptom:** Agent cannot find skills; `spec-kitty doctor skills --json` reports
missing skill files. Slash commands that reference skills fail with "skill not found" or
similar errors.

**Cause:** `spec-kitty init` was run before the skill pack was available, or the
skill root directory was manually deleted.

**Recovery:**

```bash
spec-kitty doctor skills --fix
```

If the skill root directory is entirely absent, re-initialize:

```bash
spec-kitty init . --ai <agent>
```

---

## 2. Missing Wrapper Root

**Symptom:** Slash commands (e.g., `/spec-kitty.implement`) are not found by the
agent. The agent does not recognize any `spec-kitty.*` commands.

**Cause:** The agent's wrapper directory was deleted, or `spec-kitty init` was
interrupted before wrapper files were written.

**Recovery:**

```bash
spec-kitty doctor skills --fix
```

This regenerates wrapper files for all configured agents.

---

## 3. Manifest Drift

**Symptom:** `spec-kitty doctor skills --json` reports drifted skill files. The
hash of one or more installed files does not match the manifest.

**Cause:** Managed skill files were manually edited after installation. This is
expected if a user intentionally customized a skill file, but may also indicate
accidental edits or merge conflicts.

**Recovery:**

```bash
spec-kitty doctor skills --fix
```

This overwrites drifted files with canonical content from the skill registry and
updates manifest hashes. Any local edits will be lost.

---

## 4. Runtime Not Found

**Symptom:** "next is blocked", "runtime can't find missions", or a status command
reports that `.kittify/` is missing.

**Cause:** The `.kittify/` directory was deleted, the repository was freshly
cloned without running init, or the user is in a subdirectory.

**Recovery:**

1. Ensure you are in the repository root:
   ```bash
   cd "$(git rev-parse --show-toplevel)"
   ```

2. Re-initialize:
   ```bash
   spec-kitty init . --ai <agent>
   ```

---

## 5. Stale Agent Configuration

**Symptom:** `spec-kitty agent config status` shows orphaned agent directories
(directories exist on disk but are not listed in `config.yaml`), or configured
agents are missing their directories.

**Cause:** Agents were added or removed by manually editing the filesystem
instead of using `spec-kitty agent config add/remove` commands.

**Recovery:**

```bash
# Check current state
spec-kitty agent config status

# Sync filesystem with config (removes orphaned, creates missing)
spec-kitty agent config sync
```

---

## 6. Corrupted Config File

**Symptom:** `spec-kitty` commands fail with YAML parse errors referencing
`.kittify/config.yaml`.

**Cause:** The config file was manually edited and contains invalid YAML, or a
write was interrupted mid-operation.

**Recovery:**

1. Back up the corrupted file:
   ```bash
   cp .kittify/config.yaml .kittify/config.yaml.bak
   ```

2. Remove and re-initialize:
   ```bash
   rm .kittify/config.yaml
   spec-kitty init . --ai <agent>
   ```

3. Restore any custom settings from the backup if needed.

---

## 7. Worktree Linkage Broken

**Symptom:** `spec-kitty implement` fails with "worktree not found" or git
reports detached worktree references.

**Cause:** A worktree directory was moved or deleted without using
`git worktree remove`. The `.git/worktrees/` metadata is stale.

**Recovery:**

```bash
# List current worktrees
git worktree list

# Prune stale worktree references
git worktree prune

# Re-create the worktree if needed
spec-kitty implement WP01
```

---

## 8. Shared Package Import Resolves As Namespace Package

**Symptom:** Test collection or CLI startup fails with:

```text
ImportError: cannot import name 'normalize_event_id' from 'spec_kitty_events' (unknown location)
```

Diagnostic command:

```bash
python - <<'PY'
import spec_kitty_events

print(repr(getattr(spec_kitty_events, "__file__", None)))
print(spec_kitty_events.__path__)
PY
```

Broken output shows `None _NamespacePath(...)`. Healthy output points at
`spec_kitty_events/__init__.py`.

**Cause:** The local Python environment contains a partially removed or
mismatched `spec-kitty-events` install. Python treats the leftover
`spec_kitty_events/` directory as a PEP 420 namespace package, so top-level
re-exports from `__init__.py` are unavailable.

**Recovery:**

For the project venv:

```bash
uv sync --reinstall-package spec-kitty-events
```

For a global or Homebrew Python interpreter, remove stale package files before
reinstalling:

```bash
python -m pip uninstall -y spec-kitty-events
python - <<'PY'
from pathlib import Path
import site

for root in map(Path, site.getsitepackages()):
    for path in root.glob("spec_kitty_events*"):
        print(path)
PY
```

After inspecting the printed `site-packages` paths, delete the stale
`spec_kitty_events/` directory and `spec_kitty_events-*.dist-info`, then run:

```bash
python -m pip install --force-reinstall "spec-kitty-events>=6.0.0,<7.0.0"
```

Do not bypass this by importing private submodules from Spec Kitty code. The
CLI intentionally consumes the public top-level `spec_kitty_events` contract.
