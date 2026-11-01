---
title: Install Spec Kitty on Linux
description: Install the Spec Kitty 3.2 CLI on Linux with pipx, uv, or a virtual environment and verify the command works.
doc_status: active
updated: '2026-06-03T00:00:00Z'
related:
- docs/guides/how-to/installation/install-macos.md
- docs/guides/how-to/installation/install-windows.md
- docs/guides/how-to/installation/non-interactive-init.md
- docs/guides/how-to/installation/upgrade-cli.md
audience: docs/context/audience/external/project-owner.md
os: linux
kind: How-To
---
# Install Spec Kitty on Linux

Install the `spec-kitty` CLI on a Linux distribution using your preferred Python tooling.

> The PyPI distribution is named **`spec-kitty-cli`**; the binary it installs is **`spec-kitty`**.

## Prerequisites

- A modern Linux distribution (Ubuntu 22.04+, Debian 12+, Fedora 39+, Arch, etc.).
- **Python 3.11+**. Verify:

  ```bash
  python3 --version
  ```

  Install Python 3.11+ if needed:

  ```bash
  # Ubuntu / Debian
  sudo apt update && sudo apt install -y python3.12 python3.12-venv

  # Fedora
  sudo dnf install -y python3.12

  # Arch
  sudo pacman -S python
  ```

- On modern distros (Ubuntu 24.04, Debian 12, Fedora 39+) the system Python is "externally managed" per PEP 668. Use pipx or uv tool to avoid `--break-system-packages`.

## Method 1: pipx (recommended for global tool install)

```bash
# Ubuntu / Debian
sudo apt install -y pipx
pipx ensurepath

# Fedora
sudo dnf install -y pipx
pipx ensurepath

# Arch
sudo pacman -S python-pipx
pipx ensurepath
```

Then install Spec Kitty:

```bash
pipx install spec-kitty-cli
spec-kitty --version
```

`pipx` installs `spec-kitty` into an isolated venv and exposes it on your PATH via `~/.local/bin`.

## Method 2: uv tool

```bash
# install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# install spec-kitty
uv tool install spec-kitty-cli
spec-kitty --version
```

The Astral installer places `uv` and its tool shims under `~/.local/bin` (some older installers used `~/.cargo/bin`). Ensure that directory is on your PATH.

## Method 3: pip in a venv (contributor path)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install spec-kitty-cli
spec-kitty --version
```

`spec-kitty` is only available while the venv is activated. Run `deactivate` to leave.

> Do **not** `sudo pip install spec-kitty-cli` against system Python on Ubuntu 24.04 / Debian 12 / Fedora — modern distros block this with `externally-managed-environment`. Use pipx or uv instead.

## Verification

```bash
spec-kitty --version
# spec-kitty-cli version 3.2.x
```

Useful follow-ups:

```bash
spec-kitty --help
spec-kitty doctor      # post-install health check (in an initialized project)
```

## PATH considerations on Linux

`pipx` and `uv tool` install shims under `~/.local/bin`. If `spec-kitty` is "command not found", that directory is not on your PATH.

**bash:**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
exec bash -l
```

**zsh:**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
exec zsh
```

**fish:**

```fish
fish_add_path ~/.local/bin
```

`pipx ensurepath` will patch your rc file automatically if you skipped this.

If `uv` is in `~/.cargo/bin` instead of `~/.local/bin`, add that path too.

## Troubleshooting

**`externally-managed-environment` from `pip`** — Your distro forbids `pip install` against system Python (PEP 668). Switch to pipx or a venv. Do not use `--break-system-packages`.

**`spec-kitty: command not found`** — `~/.local/bin` (or `~/.cargo/bin`) is not on your PATH. Re-run `pipx ensurepath`, restart your shell, then `which spec-kitty`.

**`SSL: CERTIFICATE_VERIFY_FAILED`** — Usually means an outdated `ca-certificates` package. `sudo apt install --reinstall ca-certificates` (Debian/Ubuntu) or the equivalent for your distro.

**Old Python on enterprise Linux (RHEL 8, CentOS 7)** — System Python is too old. Install Python 3.11+ from your distro's modules or from [python.org source](https://www.python.org/downloads/source/), then `pipx install --python /path/to/python3.11 spec-kitty-cli`.

## Next steps

- [Initialize a project](non-interactive-init.md)
- [Upgrade the CLI](upgrade-cli.md)
- [macOS install guide](install-macos.md)
- [Windows install guide](install-windows.md)
- [Pip vs pipx vs uv — which to choose](../../../architecture/pip-vs-pipx-vs-uv.md)
