---
title: Pip vs pipx vs uv — which installer should you use?
description: "Choosing a Python installer for the Spec Kitty CLI: pipx by default, uv tool for uv teams, pip in a venv for contributors, and why per-tool isolation and PEP 668 matter."
doc_status: active
updated: '2026-06-03'
type: explanation
audience: end-users
---
# Pip vs pipx vs uv — which installer should you use?

Spec Kitty supports installing the CLI with three Python tools: `pip`, `pipx`, and `uv tool`. They are not interchangeable. This page explains the difference and recommends the right choice for your situation.

## The short answer

| You are… | Use |
|---|---|
| An end user who wants `spec-kitty` on your PATH | **pipx** (or **uv tool**) |
| A team standardizing on `uv` | **uv tool** |
| A contributor working inside a clone of `spec-kitty` | **pip in a venv** |
| Anyone else | **pipx** |

## Overview of each tool

### pip

`pip` is the standard Python package installer. It installs into whatever Python environment you tell it to — system Python, a venv, conda, etc. It does **not** create isolation for you; it installs alongside everything else in that environment.

Use cases:

- Installing dependencies into an explicit virtual environment you manage.
- CI/CD images with a dedicated Python.
- Contributing to a Python project that you have cloned.

### pipx

[`pipx`](https://pipx.pypa.io/) is built on top of `pip` and `venv`. It installs each Python **application** (anything that exposes console scripts) into its own dedicated venv, then symlinks the script onto your PATH. You get isolation per-tool without managing venvs yourself.

Use cases:

- Installing CLI applications globally, with isolation.
- Running occasional one-shot tools with `pipx run`.
- Any modern Linux distro with PEP 668 `externally-managed-environment` rules.

### uv tool

[`uv`](https://docs.astral.sh/uv/) is a fast, Rust-based Python toolchain. Its `uv tool` subcommand is conceptually similar to `pipx` — install applications into isolated venvs, expose their scripts — but it uses uv's parallel resolver and aggressive caching, so installs and upgrades are much faster.

Use cases:

- You already use `uv` for project dependency management and want one tool for everything.
- Speed matters (CI cold-installs, frequent reinstalls).
- You want lockfile-like reproducibility for tool installs.

## Comparison

| Tool | Isolation | Speed | Reproducibility | Cross-platform | Recommended for |
|------|-----------|-------|-----------------|-----------------|-----------------|
| **pip** (system) | None (shared env) | Medium | Manual | macOS / Linux / Windows | Avoid for global tools |
| **pip** (venv) | Per-venv | Medium | Manual via `requirements.txt` | macOS / Linux / Windows | Contributors, CI |
| **pipx** | Per-tool venv (automatic) | Medium | Pin via `==` | macOS / Linux / Windows | Default for global tool install |
| **uv tool** | Per-tool venv (automatic) | Fast | Pin via `==`; uv caches resolutions | macOS / Linux / Windows | Teams standardizing on uv |

### Why isolation matters

When you `pip install spec-kitty-cli` into a system Python, the install shares site-packages with every other Python program on the machine. A future `pip install some-other-tool` can silently upgrade a dependency that breaks spec-kitty. With `pipx` or `uv tool`, each tool has its own venv, so dependency conflicts cannot happen.

This is also why modern distributions (Ubuntu 24.04, Debian 12, Fedora) refuse `pip install` against system Python — PEP 668 declares those interpreters externally managed, and direct installs corrupt the OS.

### Why contributors use pip in a venv

If you are working **on** Spec Kitty (not just with it), you clone the repository and install in editable mode:

```bash
git clone https://github.com/spec-kitty/spec-kitty
cd spec-kitty
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Editable mode (`-e .`) means edits to `src/specify_cli/` are picked up immediately. Neither `pipx` nor `uv tool` are designed for that workflow — they are about installing finished applications.

## Common quirks

### pip

- Direct installs against modern system Python fail with `externally-managed-environment`. This is correct behavior — switch to pipx, uv tool, or a venv.
- `pip install --user` puts scripts in `~/.local/bin`, which may not be on PATH.
- `pip install --upgrade` upgrades to the latest matching version, but does not remove obsolete dependencies. Use `pip-autoremove` or a fresh venv if cleanliness matters.

### pipx

- The shim directory (`~/.local/bin`) must be on PATH. `pipx ensurepath` handles this once.
- `pipx upgrade spec-kitty-cli` only sees PyPI; for git installs, use `pipx install --force`.
- `pipx reinstall` is occasionally needed after major Python upgrades (3.11 → 3.12) so the tool venv uses the new interpreter.

### uv tool

- The shim directory varies by installer (Astral installer uses `~/.local/bin` in current releases; older installers used `~/.cargo/bin`). Verify with `uv tool dir --bin`.
- `uv tool` and `pipx` cannot manage the same installation — pick one tool per machine for `spec-kitty-cli`.
- `uv tool upgrade <name>` requires the tool to have been originally installed via `uv tool install`.

## Recommendation

For most users, **pipx** is the right default. It is:

- Officially blessed by the Python packaging ecosystem.
- Available on every major distribution.
- Self-contained — `pipx install spec-kitty-cli` is one command.

If your team has already standardized on uv, prefer `uv tool install spec-kitty-cli` so all your Python tooling lives in the same place.

Only fall back to `pip in a venv` when you are managing the venv intentionally (contributors, CI/CD, special interpreters).

## See also

- [Install on macOS](../guides/how-to/installation/install-macos.md)
- [Install on Linux](../guides/how-to/installation/install-linux.md)
- [Install on Windows](../guides/how-to/installation/install-windows.md)
- [Upgrade the CLI](../guides/how-to/installation/upgrade-cli.md)
- [pipx docs](https://pipx.pypa.io/)
- [uv docs](https://docs.astral.sh/uv/)
- [PEP 668: externally managed environments](https://peps.python.org/pep-0668/)
