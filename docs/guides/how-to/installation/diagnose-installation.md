---
title: Diagnose Installation Problems
description: 'How to diagnose installation problems with Spec Kitty 3.2: When Spec Kitty stops working -- skills go missing, slash commands vanish, or the runtime reports.'
doc_status: active
updated: '2026-06-14'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
- docs/guides/how-to/collaboration/manage-agents.md
---
# Diagnose Installation Problems

When Spec Kitty stops working -- skills go missing, slash commands vanish, or
the runtime reports errors -- use this guide to identify the problem and recover.

## Run the diagnostic command

Start every investigation with `doctor skills`:

```bash
spec-kitty doctor skills --json
```

The JSON output reports command-skill coverage, drift, gaps, stale entries, and
orphaned managed files. Treat `error` issues as blockers and `warning` issues
as repair candidates.

To get machine-readable output for scripting or agent consumption:

```bash
spec-kitty doctor skills --json
```

For general project status, use:

```bash
spec-kitty agent tasks status
```

---

## Common failure patterns

Below are the nine most frequent failure states, each with its symptoms,
root cause, and recovery steps.

### 1. Missing skill root

**Symptoms:**
- Agent reports "skill not found" when running slash commands.
- `spec-kitty doctor skills --json` lists missing skill files.

**Cause:**  The skill root directory for your agent was deleted, or
`spec-kitty init` ran before the current skill pack was available.

**Recovery:**

```bash
spec-kitty init . --ai <your-agent>
```

This regenerates the skill root and all skill files from the canonical
registry.

---

### 2. Missing wrapper root

**Symptoms:**
- Slash commands like `/spec-kitty.implement` are not recognized by the agent.
- The agent's command palette shows no `spec-kitty.*` entries.

**Cause:**  The agent's wrapper directory (e.g., `.claude/commands/`) was
deleted or `spec-kitty init` was interrupted before wrapper files were written.

**Recovery:**

```bash
spec-kitty agent config sync --create-missing
```

This regenerates wrapper files for every configured agent.

---

### 3. Manifest drift

**Symptoms:**
- `spec-kitty doctor skills --json` reports one or more drifted skill files.
- Hash mismatches appear in the verification output.

**Cause:**  Managed skill files under `.kittify/skills-manifest.json` were
edited by hand after installation.  This can also happen when merge conflicts
leave partially resolved content in skill files.

**Recovery:**

```bash
spec-kitty upgrade
```

This overwrites drifted files with canonical content and updates the manifest
hashes.  Any local edits will be lost -- if you have intentional customizations,
back them up first.

---

### 4. Runtime not found

**Symptoms:**
- A status or doctor command reports `.kittify/` is missing.
- Errors like "next is blocked" or "runtime can't find missions" appear.

**Cause:**  The `.kittify/` directory was deleted, the repo was freshly cloned
without running init, or the shell is in a subdirectory rather than the
repository root.

**Recovery:**

1. Navigate to the repository root:

   ```bash
   cd "$(git rev-parse --show-toplevel)"
   ```

2. Re-initialize:

   ```bash
   spec-kitty init . --ai <your-agent>
   ```

---

### 5. Stale agent configuration

**Symptoms:**
- `spec-kitty agent config status` shows "Orphaned" directories (present on
  disk but not listed in `config.yaml`).
- Configured agents show "Missing" directories.

**Cause:**  Agents were added or removed by directly editing the filesystem
instead of using `spec-kitty agent config add` / `remove`.

**Recovery:**

```bash
# Inspect current state
spec-kitty agent config status

# Sync the filesystem with config.yaml
spec-kitty agent config sync
```

See the [safety warning about --remove-orphaned](#safety-warning---remove-orphaned-and-shared-directories)
below before running sync with orphan removal.

---

### 6. Corrupted config file

**Symptoms:**
- Any `spec-kitty` command fails with a YAML parse error referencing
  `.kittify/config.yaml`.

**Cause:**  The config file was hand-edited and now contains invalid YAML, or a
write operation was interrupted mid-file.

**Recovery:**

1. Back up the corrupted file:

   ```bash
   cp .kittify/config.yaml .kittify/config.yaml.bak
   ```

2. Remove the corrupt file and re-initialize:

   ```bash
   rm .kittify/config.yaml
   spec-kitty init . --ai <your-agent>
   ```

3. If you had custom settings (e.g., a non-default agent list), restore them
   from the backup by comparing `.kittify/config.yaml.bak` with the freshly
   generated file.

---

### 7. Worktree linkage broken

**Symptoms:**
- `spec-kitty implement` fails with "worktree not found".
- `git worktree list` shows entries pointing to directories that no longer
  exist.

**Cause:**  A worktree directory was moved or deleted without running
`git worktree remove`.  The stale metadata in `.git/worktrees/` confuses both
Git and Spec Kitty.

**Recovery:**

```bash
# List current worktrees and identify stale entries
git worktree list

# Prune stale references
git worktree prune

# Re-create the worktree if needed
spec-kitty agent action implement WP01 --agent <name>
```

---

### 8. Shared package imports resolve as a namespace package

**Symptoms:**

- `pytest` fails during collection before any tests run.
- The traceback contains an error like:

  ```text
  ImportError: cannot import name 'normalize_event_id' from 'spec_kitty_events' (unknown location)
  ```

- The affected package reports `__file__` as `None`:

  ```bash
  python -c 'import spec_kitty_events as e; print(repr(getattr(e, "__file__", None))); print(e.__path__)'
  ```

  Broken output looks like:

  ```text
  None _NamespacePath([.../site-packages/spec_kitty_events])
  ```

**Cause:**  Python is resolving `spec_kitty_events` as a PEP 420 implicit
namespace package instead of a normal package. This usually means an earlier
install was partially removed: submodule files remain on disk, but
`spec_kitty_events/__init__.py` or the matching `.dist-info/` metadata is
missing, stale, or mismatched. In that state, top-level re-exports such as
`normalize_event_id` are unavailable even when the installed wheel normally
provides them.

**Recovery:**

For a project virtual environment managed by `uv`, reinstall the dependency:

```bash
uv sync --reinstall-package spec-kitty-events
```

For the affected Python interpreter, remove the stale package directory and
metadata before reinstalling:

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

Inspect the printed paths. They should be under the affected interpreter's
`site-packages`. Then remove the stale package directory and metadata:

```bash
rm -rf /path/to/site-packages/spec_kitty_events \
       /path/to/site-packages/spec_kitty_events-*.dist-info
python -m pip install --force-reinstall "spec-kitty-events>=6.0.0,<7.0.0"
```

Re-run the diagnostic check. Healthy output includes a real `__init__.py` path:

```text
'.../site-packages/spec_kitty_events/__init__.py' [...]
```

Do not work around this by changing Spec Kitty imports to
`spec_kitty_events.models`. The CLI intentionally consumes the public top-level
`spec_kitty_events` surface, and the consumer contract tests pin that surface.

## Safety warning: --remove-orphaned and shared directories

The `spec-kitty agent config sync --remove-orphaned` command (which is the
default behavior of `sync`) deletes the **entire parent directory** of an
orphaned agent, not just the agent subdirectory.

This is dangerous for agents whose directory is shared with other tools:

| Agent | Agent subdirectory | Parent directory | Also used by |
|-------|--------------------|------------------|--------------|
| GitHub Copilot | `.github/prompts/` | `.github/` | CI workflows, issue templates, dependabot config |

**Example of the hazard:**

If `copilot` is orphaned (not in `config.yaml` but `.github/` exists on disk),
running `sync --remove-orphaned` deletes the entire `.github/` directory --
including your GitHub Actions workflows, issue templates, and any other
`.github/` contents.

**Safe alternatives:**

1. **Manually delete only the agent subdirectory** instead of using
   `--remove-orphaned`:

   ```bash
   rm -rf .github/prompts/
   ```

2. **Keep the orphaned directory** by passing `--keep-orphaned`:

   ```bash
   spec-kitty agent config sync --keep-orphaned
   ```

3. **Add the agent to your config** so it is no longer considered orphaned:

   ```bash
   spec-kitty agent config add copilot
   ```

Always run `spec-kitty agent config status` first to see which directories
would be affected before executing a sync with orphan removal.

---

## Quick-reference recovery table

| Problem | Recovery command |
|---------|----------------|
| Missing skill files | `spec-kitty agent config sync --create-missing` |
| Missing wrapper root | `spec-kitty agent config sync --create-missing` |
| Missing skill root | `spec-kitty init . --ai <your-agent>` |
| Manifest drift | `spec-kitty upgrade` |
| Runtime not found | `cd "$(git rev-parse --show-toplevel)" && spec-kitty init . --ai <your-agent>` |
| Stale agent config | `spec-kitty agent config sync` |
| Corrupted config | `cp .kittify/config.yaml .kittify/config.yaml.bak && rm .kittify/config.yaml && spec-kitty init . --ai <your-agent>` |
| Broken worktree | `git worktree prune && spec-kitty agent action implement WP01 --agent <name>` |

## See Also

- [Install & Upgrade](install-spec-kitty.md) -- initial installation steps
- [Manage Agents](../collaboration/manage-agents.md) -- add, remove, and sync agent directories
