"""Canonical environment-variable truthy parsing — the single authority.

Every ``SPEC_KITTY_*`` on/off flag reader delegates here so the truthy grammar
is defined exactly once. Truthy tokens (case-insensitive, surrounding
whitespace stripped): ``1``, ``true``, ``yes``, ``y``, ``on``. Everything else
— including ``None`` and the empty string — is falsy.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping

__all__ = [
    "PRE_REVIEW_GATE_SKIP_ENV_VAR",
    "is_interactive",
    "is_truthy",
    "pre_review_gate_skip_reason",
]

# Private: the canonical truthy grammar is an implementation detail of
# ``is_truthy`` — callers use the function, never the set (keeps a single public
# surface + satisfies the symbol-level dead-code gate).
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "y", "on"})

#: The pre-review regression gate's own process-wide opt-out (#3980): the gate
#: reads only this name (plus its per-invocation ``--skip-pre-review-gate`` flag).
PRE_REVIEW_GATE_SKIP_ENV_VAR = "SPEC_KITTY_SKIP_PRE_REVIEW_GATE"


def is_truthy(value: str | None) -> bool:
    """Return True iff ``value`` is a recognized truthy token (see module docstring)."""
    if value is None:
        return False
    return value.strip().casefold() in _TRUTHY_VALUES


def is_interactive() -> bool:
    """Return True iff the caller may block on a human at the terminal.

    The single authority for the non-interactive contract. Decision matrix,
    highest priority first:

      1. ``SPEC_KITTY_FORCE_INTERACTIVE`` truthy -> True (escape hatch).
      2. ``SPEC_KITTY_NON_INTERACTIVE`` truthy   -> False (how agents/CI drive us).
      3. Otherwise: ``sys.stdin.isatty()``.

    The single authority for **prompt-gating**: any surface about to block on a
    human — ``typer.prompt``, ``input()``, ``typer.confirm``, a keystroke read —
    must consult this first. Prompting when this returns False is the #2876 class
    of defect: in an agent harness with an open-but-silent stdin pipe, the prompt
    blocks forever. (`init`, `merge` preflight, `intake`, and `doctor` all route
    through this — #2912.)

    This is distinct from using ``stdin`` as a *data channel*: code that reads a
    piped payload (e.g. a harness hook JSON on stdin) legitimately checks
    ``sys.stdin.isatty()`` directly, because "is there piped input?" is a
    different question from "may I prompt?" and must not be swayed by
    ``SPEC_KITTY_FORCE_INTERACTIVE`` / ``NON_INTERACTIVE``.

    Tests monkeypatch ``sys.stdin`` or ``os.environ`` rather than relying on the
    real shell.
    """
    if is_truthy(os.environ.get("SPEC_KITTY_FORCE_INTERACTIVE")):
        return True
    if is_truthy(os.environ.get("SPEC_KITTY_NON_INTERACTIVE")):
        return False
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, ValueError):  # pragma: no cover - defensive
        return False


def pre_review_gate_skip_reason(environ: Mapping[str, str] | None = None) -> str | None:
    """Return why the pre-review regression gate should be skipped, or ``None`` to run it.

    #3980: the gate's process-wide opt-out is its own name,
    ``SPEC_KITTY_SKIP_PRE_REVIEW_GATE``. ``environ`` defaults to ``os.environ``.
    """
    env: Mapping[str, str] = os.environ if environ is None else environ
    if is_truthy(env.get(PRE_REVIEW_GATE_SKIP_ENV_VAR)):
        return f"{PRE_REVIEW_GATE_SKIP_ENV_VAR} is set"
    return None
