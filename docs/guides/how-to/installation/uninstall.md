---
title: Uninstall Spec Kitty
description: 'How to uninstall spec kitty with Spec Kitty 3.2: Remove the spec-kitty CLI and, optionally, the project files it generated. This page also covers rollback.'
doc_status: active
updated: '2026-06-12'
type: how-to
related:
- guides/how-to/installation/install-macos
- guides/how-to/installation/upgrade-cli
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
---
# Uninstall Spec Kitty

Remove the `spec-kitty` CLI and, optionally, the project files it generated. This page also covers rollback from a failed upgrade.

## Uninstall the CLI

Pick the section that matches how you installed.

### pipx

```bash
pipx uninstall spec-kitty-cli
```

To remove the pipx-managed Python interpreter and venv entirely:

```bash
pipx uninstall spec-kitty-cli
rm -rf ~/.local/share/pipx/venvs/spec-kitty-cli   # safety: pipx should already handle this
```

### uv tool

```bash
uv tool uninstall spec-kitty-cli
```

To clear cached wheels and tool data:

```bash
uv cache clean
```

### pip in a venv

```bash
# Inside the activated venv:
pip uninstall spec-kitty-cli
```

If the venv only existed for spec-kitty, remove the whole venv:

```bash
deactivate
rm -rf .venv
```

### Verify removal

```bash
spec-kitty --version
# command not found
```

If `spec-kitty` is still on your PATH after uninstall, you likely have a second installation. `which -a spec-kitty` (POSIX) or `where.exe spec-kitty` (Windows) shows every match.

## Remove generated project files

A project initialized with `spec-kitty init` contains generated agent and scaffold directories, plus mission history. Decide carefully what to remove.

### Safe to remove (generated, no user data)

```bash
rm -rf .kittify/          # project scaffold and config
rm -rf .claude/           # agent command directory (one per configured agent)
rm -rf .codex/            # legacy Codex root (only present on installs that predate Agent Skills)
rm -rf .gemini/
rm -rf .agents/skills/    # codex/vibe skill packages
# ... and any other configured agent directory listed in .kittify/config.yaml
```

Spec Kitty also adds entries to your `.gitignore` and `.claudeignore`. Remove the `# spec-kitty` block if you want a clean ignore file.

### Caution: contains your work

```bash
kitty-specs/              # mission specs, plans, status events — YOUR work
architecture/             # ADRs and architectural docs
docs/                     # documentation you authored
```

**Do not blindly delete `kitty-specs/`** — it holds every mission spec, work-package definition, status event log, and merge artifact. If you genuinely want to remove Spec Kitty from a repo but keep history, **archive instead of delete**:

```bash
tar czf kitty-specs-archive-$(date +%Y%m%d).tgz kitty-specs/
git rm -r kitty-specs/
git commit -m "chore: archive spec-kitty mission history"
```

### `.worktrees/` cleanup

If any execution lanes are still on disk, remove them before deleting the rest:

```bash
spec-kitty agent worktrees prune    # safe cleanup of finished lanes
# fallback for stuck worktrees:
git worktree list
git worktree remove .worktrees/<name>
```

## Rollback from a failed upgrade

If a CLI upgrade or project migration left you in a bad state, roll back in two steps.

### 1. Reinstall the previous CLI version

```bash
# pipx
pipx install --force spec-kitty-cli==<previous-version>

# uv tool
uv tool install --force spec-kitty-cli==<previous-version>

# pip in venv
pip install --force-reinstall 'spec-kitty-cli==<previous-version>'
```

Verify:

```bash
spec-kitty --version
```

### 2. Restore project files

Most spec-kitty-managed paths are version-controlled, so `git` is your rollback tool:

```bash
cd /path/to/project
git restore .kittify/ .claude/ .agents/skills/ .gemini/    # whichever changed
git status                                          # confirm clean
```

If the failed upgrade was committed already:

```bash
git revert <upgrade-commit-sha>
```

`kitty-specs/` artifacts are version-controlled and should be left alone during rollback — they belong to your project, not to the spec-kitty install.

## Reinstall later

Uninstalling does not lock you out. To reinstall:

```bash
pipx install spec-kitty-cli
cd /path/to/project
spec-kitty init . --ai claude   # idempotent; re-creates agent dirs only for configured agents
```

If `kitty-specs/` is still in the repo, your mission history reappears automatically.

## Troubleshooting

**`spec-kitty` is still on PATH after uninstall** — A second install exists elsewhere. `which -a spec-kitty` lists every match.

**`.kittify/config.yaml` still references uninstalled agents** — Edit via `spec-kitty agent config remove <key>` before uninstalling, or simply delete `.kittify/` when removing the project.

**I deleted `kitty-specs/` by mistake** — `git restore kitty-specs/` if it was version-controlled. If not, check `.git/objects` or your backups; spec-kitty does not keep a separate copy.

## Next steps

- [Reinstall spec-kitty](install-macos.md)
- [Upgrade the CLI](upgrade-cli.md)
- [Init lifecycle reference](../../../api/init-lifecycle.md)
