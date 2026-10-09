---
title: Isolated Dev Environments (Shadow Clones)
description: 'Run several standalone spec-kitty checkouts on one machine without cross-mission pollution: a clone-local venv plus a clone-local runtime-state root, machine-global CLI intact.'
doc_status: active
updated: '2026-10-09'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/how-to/local-overrides.md
- docs/development/contributing.md
- docs/context/execution.md
---
# Isolated Dev Environments (Shadow Clones)

Working on spec-kitty often means running the CLI **against a checkout while you
are editing that same checkout's source**. When you keep more than one checkout
on a machine — a stable primary plus one or more experiment branches — two of
them can quietly interfere with each other. This guide sets up a **Shadow
Clone**: a standalone spec-kitty checkout whose CLI *and* runtime state are
pinned to itself, so nothing it does leaks into the machine-global install or
into sibling clones.

This is the non-containerised option. It is chosen deliberately for speed and
low overhead; a container gives stronger isolation but costs startup time and
disk on every invocation. If you need hard OS-level isolation, containerise
instead — this guide is for the fast, everyday case.

## The two things that actually leak

Isolation has exactly two axes. Miss either one and the clones are still
entangled.

| Axis | What leaks if unisolated | The lever |
|------|--------------------------|-----------|
| **Code** — which `spec-kitty` runs | `spec-kitty` on your `PATH` resolves to the *machine-global* binary, so it runs global code against the clone's files. Edits to the clone's `src/` have no effect until the global install is rebuilt. | A clone-local `.venv` (editable install) placed **first** on `PATH`. |
| **State** — where the CLI reads/writes | With `SPEC_KITTY_HOME` unset, every clone shares one runtime-state root at `~/.spec-kitty` — auth tokens (`auth/`), `config.toml`, tracker credentials and stores, and the pre-review gate locks (`gate-locks/`). One clone's gate lock or tracker state then affects another clone's work. | Point `SPEC_KITTY_HOME` at a clone-local directory. |

`SPEC_KITTY_HOME` is the single environment variable that redirects the runtime
state. When set, it is used **verbatim** as the state root (it is *not* suffixed
with `.spec-kitty`), and it redirects both resolvers the codebase relies on —
`get_runtime_root()` (runtime state) and `get_kittify_home()` (asset home). See
[`src/kernel/paths.py`](../../../src/kernel/paths.py) and
[`src/specify_cli/paths/windows_paths.py`](../../../src/specify_cli/paths/windows_paths.py).

> The parallel test suite isolates itself the same way — each `pytest-xdist`
> worker gets its own `HOME`/`SPEC_KITTY_HOME` so a run never touches the real
> `~/.spec-kitty`. A Shadow Clone applies that discipline to interactive
> sessions.

## Mental model: primary vs. shadow

- **Primary checkout** — your stable clone. Its build backs the
  **machine-global** `spec-kitty` you use everywhere *outside* a Shadow Clone.
  When no Shadow Clone is active, the machine-global CLI is what runs.
- **Shadow Clone** — any additional isolated checkout. Inside its session, a
  clone-local `.venv` and a clone-local state root take over; outside, nothing
  changed.

A Git worktree (including one under `.worktrees/`) can use the same isolation:
create its own `.venv`, then activate from inside that worktree. If its older
branch lacks the helper, source the helper from a checkout that has it by
absolute path. It still binds the current worktree.

The rest of this guide keeps those two intact at the same time: the global CLI
stays the default everywhere, and each Shadow Clone overrides it only for the
shell session you activate.

## One-time machine setup (the global CLI)

Do this once, from your **primary** checkout, so that `spec-kitty` works from
any directory that is *not* an activated Shadow Clone. Two supported shapes:

**A. Snapshot from source (recommended default).** Install the primary
checkout's build into an isolated app environment with
[`pipx`](https://pipx.pypa.io/). This gives you a global `spec-kitty` that is
your fork's code rather than the published PyPI release, without putting the
primary checkout's `.venv` on your `PATH`:

```bash
# from the primary checkout root
pipx install --force .
```

Re-run that command whenever you want the global CLI to pick up new primary-
checkout changes. It is a **snapshot**, not a live link: editing the primary
checkout's source does not change the global CLI until you reinstall.

**B. Live editable link.** If you want the global CLI to always track the
primary checkout's working tree, install it editable into a dedicated
environment instead:

```bash
# from the primary checkout root
pipx install --force --editable .
```

Either way, confirm the global resolves as expected from a neutral directory:

```bash
cd ~   # anywhere that is not a Shadow Clone
command -v spec-kitty     # -> ~/.local/bin/spec-kitty (the pipx shim)
spec-kitty --version
```

> Keep the primary checkout's own `.venv` for running its tests, but do **not**
> add it to your shell's default `PATH`. The global shim is the machine default;
> the primary `.venv` is just how you test the primary checkout.

## Per-clone setup (each Shadow Clone)

For every additional checkout you want to isolate:

### 1. Create the clone-local virtualenv (editable install + dev extras)

Use the project's canonical install — the same command
[`contributing.md`](../contributing.md) prescribes. From the clone root it creates
`.venv`, installs the clone **editable** (so the CLI always runs the clone's live
`src/`), and pulls in the dev extras — the `test` and `lint` optional-dependency
groups (`pytest`, `pytest-xdist`, `ruff`, `mypy`, …) plus the `dev` dependency
group — resolved from the committed `uv.lock`:

```bash
# from the Shadow Clone root
uv sync --frozen --all-extras
```

Do **not** skip the dev extras: a Shadow Clone you cannot run the test suite,
`ruff`, or `mypy` in is a half-isolated clone that still forces you back to
another checkout to validate a change. `uv sync` installs them by default here,
so a correctly set-up clone is self-sufficient.

> **No `uv`?** Install it (<https://docs.astral.sh/uv/>), or fall back to the
> stdlib path — but install the extras explicitly so the clone stays
> self-sufficient:
> ```bash
> python3.11 -m venv .venv          # match the project's supported Python (3.11+)
> .venv/bin/python -m pip install -e '.[test,lint]'
> ```
> Playwright's browser (for `tests/ui/`) is never committed; install it once per
> clone when you need the UI e2e tests: `.venv/bin/playwright install chromium`.

Verify the clone-local CLI and dev tools run the clone's code:

```bash
.venv/bin/spec-kitty --version
.venv/bin/pytest --version && .venv/bin/ruff --version && .venv/bin/mypy --version
```

`.venv/` is already git-ignored, so this never becomes a committed artefact.

### 2. Activate the isolated environment for your session

A committed, path-agnostic helper does both axes at once — prepends the clone's
`.venv/bin` to `PATH` and points `SPEC_KITTY_HOME` at a clone-local state root.
**Source** it (do not execute it); it works from both `bash` and `zsh`:

```bash
# from the Shadow Clone root
source scripts/dev/activate-isolated-env.sh
```

It prints what it bound and how to undo it:

```
spec-kitty isolated env ACTIVE
  clone : <clone-root>
  venv  : <clone-root>/.venv
  state : <clone-root>/.spec-kitty-home
  cli   : <clone-root>/.venv/bin/spec-kitty
  undo  : deactivate_spec_kitty
```

The helper derives the root from the current Git checkout, falling back to its
own location outside Git. The clone-local state root
(`.spec-kitty-home/`) is git-ignored.

To restore the shell to the machine-global CLI and unset the overrides:

```bash
deactivate_spec_kitty
```

### 3. Verify the isolation

With the environment active:

```bash
command -v spec-kitty          # -> <clone-root>/.venv/bin/spec-kitty
echo "$SPEC_KITTY_HOME"        # -> <clone-root>/.spec-kitty-home
spec-kitty agent tasks status  # any command now writes only under .spec-kitty-home/
ls .spec-kitty-home            # clone-local runtime state (auth/, gate-locks/, ...) appears here
```

Confirm the machine-global root is untouched — nothing new should appear under
`~/.spec-kitty` as a result of commands run inside the Shadow Clone.
The isolated state root starts without a login session. Before a hosted sync or
tracker call that needs authentication, run `spec-kitty auth login` inside the
activated Shadow Clone.

## Optional: auto-activate with direnv

Sourcing by hand is reliable but easy to forget. If you use
[`direnv`](https://direnv.net/), drop an `.envrc` at each clone root so the
environment activates on `cd` and deactivates when you leave:

```bash
# <clone-root>/.envrc
source scripts/dev/activate-isolated-env.sh
```

Then `direnv allow` once per clone. `direnv` is optional and is **not** a
project dependency; the sourced helper remains the baseline that needs nothing
installed. If you commit an `.envrc`, keep it path-agnostic (as above) so it
works in any clone.

## What is (and is not) isolated

**Isolated per clone once activated:**

- Which `spec-kitty` binary runs (clone `.venv`, editable → live `src/`).
- Runtime state under `SPEC_KITTY_HOME`: auth, config, tracker credentials
  and stores, and gate-locks. (A `queue.db` or `sync-daemon` file under an old
  `~/.spec-kitty` is inert residue from the retired sync transport.)

**Deliberately *not* isolated:**

- The machine-global `spec-kitty` — it stays your default everywhere outside an
  activated Shadow Clone. Setting up a Shadow Clone never rewrites it.
- Anything a command reaches over the network (a hosted Team Kitty or tracker backend is
  shared infrastructure regardless of local state). Isolation here is about
  *local* runtime state, not remote services.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `spec-kitty` still resolves to `~/.local/bin/...` after activating | The helper was executed, not sourced, so the exports never reached your shell. | `source scripts/dev/activate-isolated-env.sh` (note the leading `source`). |
| `no .venv found at <root>` | The clone-local virtualenv was not created yet. | Run step 1 (create `.venv` + `pip install -e .`). |
| `no executable spec-kitty CLI found at <root>/.venv/bin/spec-kitty` | The checkout's `.venv` does not contain the Spec Kitty CLI. | Install this checkout with step 1, then activate again. |
| A hosted sync or tracker call says `Not authenticated` | This Shadow Clone has its own empty auth store. | Run `spec-kitty auth login` inside the activated Shadow Clone. |
| Edits to the clone's `src/` have no effect | The active CLI is the machine-global one, or the `.venv` install is not editable. | Activate the env; reinstall with `pip install -e .`. |
| A gate lock, tracker binding, or login seems to come from another clone | `SPEC_KITTY_HOME` was unset, so the shared `~/.spec-kitty` was in play. | Activate the env; confirm `echo "$SPEC_KITTY_HOME"` points inside the clone. |
| State appeared under `~/.spec-kitty` while working in a clone | A command ran before activation. | Deactivate/reactivate; run clone commands only inside an activated session. |

## Related

- [Local overrides for cross-package development](../how-to/local-overrides.md) — editable
  installs of sibling packages (`-events`/`-tracker`) and why committed
  `[tool.uv.sources]` path overrides are prohibited.
- [Contributing to Spec Kitty](../contributing.md) — developer setup and the test
  workflow.
- Glossary: **Shadow Clone (Isolated Dev Environment)** in
  [`docs/context/execution.md`](../../context/execution.md#shadow-clone-isolated-dev-environment).
