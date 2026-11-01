---
title: Install Spec Kitty on macOS
description: Install the Spec Kitty 3.2 CLI on macOS with pipx, uv, or a virtual environment and verify the command works.
doc_status: active
updated: '2026-06-03'
type: how-to
related:
- guides/how-to/installation/install-linux
- guides/how-to/installation/install-windows
- guides/how-to/installation/non-interactive-init
- guides/how-to/installation/upgrade-cli
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
os: macos
---
# Install Spec Kitty on macOS

Install the `spec-kitty` CLI on macOS using your preferred Python tooling. Three install methods are covered; pick one.

> The PyPI distribution is named **`spec-kitty-cli`**; the binary it installs is **`spec-kitty`**.

## Prerequisites

- macOS 12 (Monterey) or newer.
- **Python 3.11+**. Verify with:

  ```bash
  python3 --version
  ```

  If you see `Python 3.10.x` or older, install a newer Python:

  ```bash
  brew install python@3.12
  ```

  Or use [pyenv](https://github.com/pyenv/pyenv) / the [official installer](https://www.python.org/downloads/macos/).

- Optional but recommended: **Homebrew** for installing `pipx` or `uv`.

## Method 1: pipx (recommended for global tool install)

`pipx` installs each Python application into its own isolated virtual environment and exposes its console scripts on your PATH. This is the safest default on a Mac where the system Python is managed by Apple or Homebrew.

```bash
brew install pipx
pipx ensurepath
pipx install spec-kitty-cli
```

Open a new shell so the PATH change takes effect, then verify:

```bash
spec-kitty --version
# spec-kitty-cli version 3.2.x
```

## Method 2: uv tool

[`uv`](https://docs.astral.sh/uv/) installs Python tools into per-tool venvs similarly to `pipx`, but faster.

```bash
brew install uv
uv tool install spec-kitty-cli
spec-kitty --version
```

If `uv` was installed via the Astral installer instead of Homebrew, its binary directory may be `~/.cargo/bin` or `~/.local/bin`. Make sure that directory is on your PATH (see below).

## Method 3: pip in a venv (contributor path)

Use this only when you are intentionally managing the Python environment yourself (for example, inside a clone of the spec-kitty repository).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install spec-kitty-cli
spec-kitty --version
```

`spec-kitty` is only on your PATH while the venv is activated. Deactivate with `deactivate`.

> Direct `pip install spec-kitty-cli` against a system Python on macOS may succeed today but is not recommended — Homebrew Python and Apple Python both treat themselves as externally managed environments. Prefer pipx or uv tool.

## Verification

Regardless of method, the verification step is identical:

```bash
spec-kitty --version
```

You should see output similar to:

```
spec-kitty-cli version 3.2.0
```

Then probe further:

```bash
spec-kitty --help
spec-kitty doctor          # post-install health check (in an initialized project)
```

## PATH considerations on macOS

Both `pipx` and `uv tool` install the `spec-kitty` script under `~/.local/bin` by default. If `spec-kitty` is "command not found" after install, your shell PATH is the problem.

**zsh (default on macOS 10.15+):**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
exec zsh
```

**bash:**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
exec bash -l
```

If you installed `uv` via the Astral installer, you may also need `~/.cargo/bin` on your PATH; the installer prints the exact line to add.

To make `pipx` itself update PATH for you the first time:

```bash
pipx ensurepath
```

## Troubleshooting

**`spec-kitty: command not found`** — Your shell cannot see the install directory. Re-run `pipx ensurepath` (or add `~/.local/bin` to `PATH` as shown above) and open a new terminal.

**`SSL: CERTIFICATE_VERIFY_FAILED` during install** — Usually means an old Python install. Use `python3 --version` to confirm you have 3.11+ and reinstall Python from python.org or Homebrew so the bundled certificates are current.

**`externally-managed-environment` error from `pip`** — You ran `pip install` against system Python. Switch to pipx or create a venv first.

**Apple Silicon vs Intel** — `spec-kitty-cli` is pure Python, so the same wheel works on both architectures. If `pip` builds from source, ensure Xcode command-line tools are installed: `xcode-select --install`.

## Next steps

- [Initialize a project](non-interactive-init.md)
- [Upgrade the CLI](upgrade-cli.md)
- [Linux install guide](install-linux.md)
- [Windows install guide](install-windows.md)
- [Pip vs pipx vs uv — which to choose](../../../architecture/pip-vs-pipx-vs-uv.md)
