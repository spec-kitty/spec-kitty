# PowerShell Syntax Guide for AI Agents

**⚠️ READ THIS if you are working in a PowerShell environment**

This guide helps AI agents use correct PowerShell syntax when working with spec-kitty workflows.

---

## Quick Reference: Bash vs PowerShell

| Task | ❌ Bash (WRONG) | ✅ PowerShell (CORRECT) |
|------|-----------------|-------------------------|
| **Command chaining** | `cmd1 && cmd2` | `cmd1; cmd2` |
| **Cmdlet parameters** (not `spec-kitty` flags) | `ls --recurse` | `Get-ChildItem -Recurse` |
| **Environment variable** | `$VAR_NAME` | `$env:VAR_NAME` |
| **Current directory** | `pwd` | `Get-Location` (or `pwd` alias) |
| **List files** | `ls -la` | `Get-ChildItem` (or `ls` alias) |
| **File exists check** | `[ -f file.txt ]` | `Test-Path file.txt` |
| **Directory separator** | `/path/to/file` | `\path\to\file` |
| **Home directory** | `~/projects` | `$HOME\projects` |

---

## Location Verification (PowerShell)

**Check your current location:**

```powershell
Get-Location
git branch --show-current
```

**Expected for mission worktrees:**

- Location: `C:\Users\...\project\.worktrees\001-mission-name`
- Branch: `001-mission-name` (NOT `main`)

---

## Running Spec-Kitty Commands (PowerShell)

### Using the spec-kitty CLI

Spec-kitty uses a Python CLI that works across all platforms. There are no
PowerShell wrapper scripts: call the CLI directly, with its normal
double-dash flags, from PowerShell exactly as you would from Bash.

**Common commands:**

- `spec-kitty agent mission create <slug> --json` - Create a new mission
- `spec-kitty verify-setup` - Check environment and paths
- `spec-kitty agent action implement <WPID> --agent <name> --mission <handle>` - Start implementing a work package (moves it to `in_progress`)
- `spec-kitty agent action review <WPID> --agent <name> --mission <handle>` - Start reviewing a work package
- `spec-kitty agent tasks move-task <WPID> --to for_review --mission <handle>` - Complete implementation (move to review)
- `spec-kitty consolidate` - Consolidate completed mission

### Parameter Naming Convention

CLI flags keep their double-dash spelling on every shell (`--json`,
`--mission`, `--include-tasks`). PowerShell's PascalCase `-Param` convention
applies only to PowerShell cmdlets and your own functions, never to
`spec-kitty` flags.

### Examples

**Create a mission:**

```powershell
spec-kitty agent mission create "user-authentication" `
  --friendly-name "User Authentication" `
  --json
```

**Check prerequisites:**

```powershell
spec-kitty agent mission check-prerequisites --json --include-tasks --mission <handle>
```

**Move task to review (after implementation):**

```powershell
spec-kitty agent tasks move-task WP01 --to for_review --mission <handle> --note "Ready for review"
```

---

## Common Mistakes to Avoid

### ❌ Don't Use Bash Operators

```powershell
# WRONG:
cd worktrees && pwd

# CORRECT:
cd worktrees; Get-Location
```

### ❌ Don't Use Bash-Style Parameters on Cmdlets

```powershell
# WRONG (cmdlets take PascalCase parameters):
Get-ChildItem --recurse --filter *.md

# CORRECT:
Get-ChildItem -Recurse -Filter *.md

# The spec-kitty CLI is not a cmdlet: keep its double-dash flags.
spec-kitty agent tasks status --json
```

### Path Separators in PowerShell

PowerShell on Windows uses backslashes for native paths:

```powershell
# WRONG (Unix-style paths on Windows):
cd ./.kittify/memory

# CORRECT (Windows-style paths):
cd .\.kittify\memory
```

Note: Git commands work with forward slashes, but native PowerShell file operations expect backslashes. The spec-kitty CLI handles this automatically.

---

## Environment Variables

**Setting variables:**

```powershell
$env:SPEC_KITTY_TEMPLATE_ROOT = "C:\path\to\spec-kitty"
```

**Reading variables:**

```powershell
echo $env:SPEC_KITTY_TEMPLATE_ROOT
```

**Checking if set:**

```powershell
if ($env:SPEC_KITTY_TEMPLATE_ROOT) {
    Write-Host "Variable is set"
}
```

---

## File Operations

**Check if file exists:**

```powershell
if (Test-Path "spec.md") {
    Write-Host "Spec exists"
}
```

**Read file:**

```powershell
$content = Get-Content "spec.md" -Raw
```

**Create directory:**

```powershell
New-Item -ItemType Directory -Path "tasks\planned" -Force
```

---

## Workflow Tips

1. **Always use full parameter names** in scripts (not abbreviations)
2. **Use semicolons** to chain commands, not `&&` or `||`
3. **Backslashes** for local paths, forward slashes OK for git operations
4. **$PID** contains current PowerShell process ID (use for --shell-pid)
5. **Tab completion** works for parameter names in PowerShell

---

## When to Use What

**Use PowerShell syntax when:**

- You're in a Windows PowerShell or `pwsh` terminal

**Use Bash syntax when:**

- You're in a bash/zsh/fish terminal

**Using spec-kitty commands:**
All spec-kitty commands work the same way on PowerShell and Bash:

```powershell
spec-kitty agent action implement WP01 --agent claude --mission <handle>  # Moves to in_progress
spec-kitty agent tasks move-task WP01 --to for_review --mission <handle>  # Completion step
spec-kitty verify-setup
spec-kitty agent tasks status
```

The CLI is cross-platform and handles path differences automatically.

---

## Debugging PowerShell Issues

**Common errors and solutions:**

1. **"Parameter cannot be found that matches parameter name"**
   - You used bash-style parameters (`--json`)
   - Fix: Use PowerShell style (`-Json`)

2. **"The term '&&' is not recognized"**
   - You used bash command chaining
   - Fix: Use semicolon (`;`) instead

3. **"Cannot find path"**
   - You used forward slashes in PowerShell path
   - Fix: Use backslashes (`\`) for local paths

4. **"Unable to import mission module"**
   - Python can't find specify_cli package
   - Check: `pip show spec-kitty-cli`
   - Fix: Reinstall or check virtual environment

---

**For full spec-kitty documentation, see the main templates and README.**
