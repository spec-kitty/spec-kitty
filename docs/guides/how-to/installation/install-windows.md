---
title: Install Spec Kitty on Windows
description: Install the Spec Kitty 3.2 CLI on Windows 10 or 11 with PowerShell, pipx, uv, or a virtual environment.
doc_status: active
updated: '2026-10-03'
type: how-to
related:
- docs/guides/how-to/installation/install-linux.md
- docs/guides/how-to/installation/install-macos.md
- docs/guides/how-to/installation/non-interactive-init.md
- docs/guides/how-to/installation/upgrade-cli.md
- docs/guides/how-to/collaboration/worktrees-with-mcp-agents.md
audience: docs/context/audience/external/project-owner.md
os: windows
---
# Install Spec Kitty on Windows

Install the `spec-kitty` CLI on Windows 10 or Windows 11. PowerShell is recommended; CMD works too.

> The PyPI distribution is named **`spec-kitty-cli`**; the binary it installs is **`spec-kitty`**. WSL is **not required**.

## Prerequisites

- Windows 10 21H2 or newer (Windows 11 preferred).
- **Python 3.11, 3.12 or 3.13 from [python.org](https://www.python.org/downloads/windows/).** Spec Kitty is tested on these three versions. **Do not install Python from the Microsoft Store**, and do not follow the Store prompt that appears when you type `python` on a fresh Windows install. See [Get Python from python.org, not the Microsoft Store](#get-python-from-pythonorg-not-the-microsoft-store).
- Optional: install [Windows Terminal](https://aka.ms/terminal) for a nicer shell experience.

## Get Python from python.org, not the Microsoft Store

python.org offers two ways to install Python on Windows. Either works with Spec Kitty.

**Option A: Python install manager (python.org's current recommendation).** Download **Python install manager** from [python.org/downloads/windows](https://www.python.org/downloads/windows/) and run it. Then install a version Spec Kitty is tested on. The manager's default is the newest Python, which may be newer than 3.13:

```powershell
py install 3.13
py list
```

**Option B: the per-version installer.** From the same page, download **Windows installer (64-bit)** for a Python 3.13 release. During install, tick **"Add python.exe to PATH"** and keep **"py launcher"** selected. python.org deprecated this installer in Python 3.14 and will not produce it for Python 3.16 or later.

Verify in a **new** PowerShell window:

```powershell
py -3.13 -c "import sys; print(sys.version); print(sys.executable)"
```

On Windows the `py` launcher is the canonical way to invoke a specific Python:

```powershell
py -3.13 --version
py -3.13 -m pip --version
```

### Check that your Python is not from the Microsoft Store

The python.org install manager is an MSIX package, so it also lives under `%LOCALAPPDATA%\Microsoft\WindowsApps`. Checking the install path is therefore not enough to tell python.org from the Store. Check the package publisher ID instead:

```powershell
Get-AppxPackage *Python* | Select-Object Name, PackageFamilyName
```

| `PackageFamilyName` ends in | Source | What to do |
| --- | --- | --- |
| `_3847v3x7pw1km` | python.org (Python install manager) | Nothing. This is the supported install. |
| `_qbz5n2kfra8p0` | Microsoft Store (the Store install manager, or a Store `Python.3.x` package) | Uninstall it from **Settings → Apps → Installed apps**, then install from python.org as above. |
| *(no Python rows)* | python.org per-version installer, or no Python at all | Run `py -0p`. Paths under `%LOCALAPPDATA%\Programs\Python\` or `%ProgramFiles%\Python…` are python.org installs. |

If `where.exe python` lists only `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe` and `py` is not found, you have the Windows **App execution alias** stub, not a real Python. Running it opens the Microsoft Store. Turn the stub off (see [Troubleshooting](#troubleshooting)) and install from python.org.

## Method 1: pipx (recommended for global tool install)

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Open a **new** PowerShell window (so the updated PATH is picked up), then:

```powershell
pipx install spec-kitty-cli
spec-kitty --version
```

## Method 2: uv tool

Install `uv` via PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new shell, then:

```powershell
uv tool install spec-kitty-cli
spec-kitty --version
```

## Method 3: pip in a venv (contributor path)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1     # PowerShell
# or:
.venv\Scripts\activate.bat     # CMD

pip install spec-kitty-cli
spec-kitty --version
```

If PowerShell refuses to run `Activate.ps1` due to execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Deactivate the venv with `deactivate`.

## Verification

```powershell
spec-kitty --version
# spec-kitty-cli version 3.2.x
```

```powershell
spec-kitty --help
spec-kitty doctor       # post-install health check (in an initialized project)
```

## PATH considerations on Windows

`pipx` and `uv tool` typically install shims into:

- `%USERPROFILE%\.local\bin`

If `spec-kitty` is "command not found":

**Option A — let pipx fix PATH for you:**

```powershell
pipx ensurepath
```

Then close and reopen PowerShell.

**Option B — add the directory manually:**

1. Open **Settings → System → About → Advanced system settings → Environment Variables**.
2. Under **User variables**, select `Path → Edit → New`.
3. Add `%USERPROFILE%\.local\bin`.
4. Open a new PowerShell window.

**Option C — temporary, for the current session only:**

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
```

### PowerShell vs CMD

- **PowerShell** is the recommended shell. Use `Activate.ps1` for venvs and the install commands above as written.
- **CMD** works for invoking `spec-kitty` once installed, but use `Scripts\activate.bat` instead of `Activate.ps1` to enter a venv.

### `py` launcher vs `python`

The Windows `py` launcher picks the right Python version even when several are installed:

```powershell
py -3.13 -m pip install --upgrade pip
py -3.13 -m pipx install spec-kitty-cli
```

Plain `python` may resolve to the Microsoft Store stub on a fresh install. `py` resolves to a real Python when one is installed from python.org, and is not found otherwise.

## Troubleshooting

**`spec-kitty` is "not recognized as the name of a cmdlet"** — PATH issue. Run `pipx ensurepath`, open a new PowerShell window, then `where.exe spec-kitty` to confirm where it lives.

**`SSL: CERTIFICATE_VERIFY_FAILED` during `pip install`** — Your Python install is too old. Reinstall Python 3.13 from python.org.

**The Microsoft Store opens, or "Python was not found; run without arguments to install from the Microsoft Store" appears, when you run `python`** — This is the App execution alias stub, not a Python install. Do not install from the Store. Open **Settings → Apps → Advanced app settings → App execution aliases**, turn off the **App Installer** entries for `python.exe` and `python3.exe`, install Python from python.org (see [above](#get-python-from-pythonorg-not-the-microsoft-store)), then open a new shell.

**Python came from the Microsoft Store** — `Get-AppxPackage *Python*` shows a `PackageFamilyName` ending in `_qbz5n2kfra8p0`. Uninstall it from **Settings → Apps → Installed apps**, install from python.org, then reinstall Spec Kitty (`pipx install spec-kitty-cli`) so it uses the new Python.

**Antivirus blocks installs** — Corporate antivirus sometimes quarantines Python wheels. Whitelist the cache directory pipx prints when it errors.

## Next steps

- [Initialize a project](non-interactive-init.md)
- [Upgrade the CLI](upgrade-cli.md)
- [Keep MCP Agents in the Worktree](../collaboration/worktrees-with-mcp-agents.md)
- [macOS install guide](install-macos.md)
- [Linux install guide](install-linux.md)
- [Pip vs pipx vs uv — which to choose](../../../architecture/pip-vs-pipx-vs-uv.md)
