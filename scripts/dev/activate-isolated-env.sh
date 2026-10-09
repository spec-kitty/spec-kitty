#!/usr/bin/env bash
# Activate an isolated Spec Kitty development environment (a "Shadow Clone").
#
# SOURCE this file — do NOT execute it:
#     source scripts/dev/activate-isolated-env.sh
#
# It rewires the CURRENT shell so that, for the rest of the session, `spec-kitty`
# resolves to THIS clone's virtualenv and all runtime state (queue.db, sync
# daemon, event journal, auth, gate-locks, trackers) lands in a clone-local
# root instead of the shared, machine-global ~/.spec-kitty. Nothing here leaks
# into the machine-global installation or into sibling clones.
#
# The script binds the current Git checkout, even when sourced from another
# worktree. Outside Git, it falls back to its own location. Undo with:
#     deactivate_spec_kitty
#
# See docs/development/getting-started/isolated-dev-environments.md for the full rationale.

# --- resolve this checkout's root (works when sourced from bash or zsh) ------
if [ -n "${BASH_SOURCE:-}" ]; then
  _spk_script="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  # In zsh, %N expands to the path of the file currently being sourced.
  _spk_script="${(%):-%N}"
else
  _spk_script="$0"
fi
_spk_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$_spk_root" ]; then
  _spk_root="$(cd "$(dirname "$_spk_script")/../.." && pwd)"
fi
unset _spk_script

# --- idempotency: re-sourcing for the same clone is a no-op refresh ----------
if [ "${SPEC_KITTY_ISOLATED_ENV:-}" = "$_spk_root" ]; then
  echo "spec-kitty isolated env already active for this clone: $_spk_root"
  unset _spk_root
  return 0 2>/dev/null || exit 0
fi

# --- guardrail: the virtualenv must exist ------------------------------------
if [ ! -d "$_spk_root/.venv" ]; then
  echo "spec-kitty: no .venv found at $_spk_root" >&2
  echo "  Create it first — see docs/development/getting-started/isolated-dev-environments.md" >&2
  unset _spk_root
  return 1 2>/dev/null || exit 1
fi
if [ ! -f "$_spk_root/.venv/bin/spec-kitty" ] || [ ! -x "$_spk_root/.venv/bin/spec-kitty" ]; then
  echo "spec-kitty: no executable spec-kitty CLI found at $_spk_root/.venv/bin/spec-kitty" >&2
  echo "  Install this checkout first — see docs/development/getting-started/isolated-dev-environments.md" >&2
  unset _spk_root
  return 1 2>/dev/null || exit 1
fi

# --- capture prior shell state so deactivate can restore it exactly ----------
# __UNSET__ is a sentinel meaning "the variable was not set before activation".
export _SPK_ISO_PREV_PATH="$PATH"
export _SPK_ISO_PREV_HOME="${SPEC_KITTY_HOME:-__UNSET__}"
export _SPK_ISO_PREV_VENV="${VIRTUAL_ENV:-__UNSET__}"

# --- activate this clone's virtualenv ----------------------------------------
export VIRTUAL_ENV="$_spk_root/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# --- clone-local runtime-state root ------------------------------------------
# SPEC_KITTY_HOME is used verbatim as the runtime base (see
# src/kernel/paths.py and src/specify_cli/paths/windows_paths.py).
export SPEC_KITTY_HOME="$_spk_root/.spec-kitty-home"
mkdir -p "$SPEC_KITTY_HOME"

# --- session marker ----------------------------------------------------------
export SPEC_KITTY_ISOLATED_ENV="$_spk_root"

echo "spec-kitty isolated env ACTIVE"
echo "  clone : $_spk_root"
echo "  venv  : $VIRTUAL_ENV"
echo "  state : $SPEC_KITTY_HOME"
echo "  cli   : $(command -v spec-kitty)"
echo "  undo  : deactivate_spec_kitty"

unset _spk_root

# --- teardown ----------------------------------------------------------------
deactivate_spec_kitty() {
  if [ -z "${SPEC_KITTY_ISOLATED_ENV:-}" ]; then
    echo "spec-kitty isolated env is not active" >&2
    return 1
  fi
  export PATH="${_SPK_ISO_PREV_PATH:-$PATH}"
  if [ "${_SPK_ISO_PREV_HOME:-__UNSET__}" = "__UNSET__" ]; then
    unset SPEC_KITTY_HOME
  else
    export SPEC_KITTY_HOME="$_SPK_ISO_PREV_HOME"
  fi
  if [ "${_SPK_ISO_PREV_VENV:-__UNSET__}" = "__UNSET__" ]; then
    unset VIRTUAL_ENV
  else
    export VIRTUAL_ENV="$_SPK_ISO_PREV_VENV"
  fi
  unset SPEC_KITTY_ISOLATED_ENV _SPK_ISO_PREV_PATH _SPK_ISO_PREV_HOME _SPK_ISO_PREV_VENV
  echo "spec-kitty isolated env deactivated"
  unset -f deactivate_spec_kitty 2>/dev/null || true
}
