---
title: Set Up Codex for Spec Kitty
description: Configure Codex CLI to load Spec Kitty project-local agent skills from `.agents/skills/`.
doc_status: active
updated: '2026-10-21'
type: how-to
audience: docs/context/audience/external/project-owner.md
---
# Set Up Codex for Spec Kitty

Codex CLI uses Spec Kitty's project-local agent skills. Spec Kitty installs one
skill package per command under `.agents/skills/spec-kitty-<command>/SKILL.md`.

Use this guide when an existing project does not show `$spec-kitty-*` skills in
Codex, or when you want a small launcher that enters the repo and activates the
local Python environment before starting Codex.

## Prerequisites

- You are working in the `spec-kitty` repository root.
- `codex` is installed and available on your `PATH`.
- Spec Kitty has been initialized or synced for Codex:

```bash
spec-kitty init --ai codex
# or, for an existing project
spec-kitty agent config add codex
spec-kitty agent config sync
```

## Verify the skill packages

Confirm the generated skills exist:

```bash
ls .agents/skills/
ls .agents/skills/spec-kitty-specify/SKILL.md
```

Codex should expose these as `$spec-kitty-<command>` skills, for example:

```text
$spec-kitty-specify
$spec-kitty-plan
$spec-kitty-tasks
$spec-kitty-implement
```

If the packages are missing, regenerate them:

```bash
spec-kitty agent config sync
```

## Optional launcher

Create `scripts/tool_configs/kitty-cdx.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

CODEX_BIN="$(type -P codex || true)"
if [[ -z "${CODEX_BIN}" ]]; then
  echo "codex executable was not found in PATH" >&2
  exit 127
fi

cd "${REPO_ROOT}"

if [[ -f ".venv/bin/activate" ]]; then
  set +u
  . ".venv/bin/activate"
  set -u
fi

exec "${CODEX_BIN}" "$@"
```

Make it executable:

```bash
chmod +x scripts/tool_configs/kitty-cdx.sh
```

Add a shell alias:

```bash
alias kitty_cdx='/path/to/spec-kitty/scripts/tool_configs/kitty-cdx.sh'
```

## Windows launcher

Create `scripts/tool_configs/kitty-cdx.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

$CodexCommand = Get-Command codex -CommandType Application -ErrorAction Stop
$CodexPath = $CodexCommand.Source

Set-Location $RepoRoot

$activate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    . $activate
}

& $CodexPath @args
```

Add a `kitty_cdx` function in your PowerShell profile:

```powershell
function kitty_cdx {
    & "C:\path\to\spec-kitty\scripts\tool_configs\kitty-cdx.ps1" @args
}
```

Reload your profile:

```powershell
. $PROFILE
```

## Troubleshooting

- **Codex does not show `$spec-kitty-*` skills.**
  Run `spec-kitty agent config sync`, confirm `.agents/skills/spec-kitty-*/SKILL.md`
  exists, and restart Codex.
- **Only old prompt-style commands appear.**
  Refresh the project with `spec-kitty upgrade --project` and re-run
  `spec-kitty agent config sync`.
- **Launcher cannot find `codex`.**
  Install Codex CLI or put its binary on `PATH`, then re-run `kitty_cdx`.
