"""Ambient-warning de-duplication + scoped rendering (#3971).

The charter-preflight advisory channel surfaces *ambient* warnings —
conditions of the surrounding project state (an uninitialized charter, a
legacy ``charter.md``-only bundle, ...) that change governance behaviour
without blocking the command. Before #3971 that channel had no
de-duplication at either layer: a result could carry the same warning
string more than once, and the stderr emission seam
(:func:`specify_cli.charter_runtime.preflight.hook.emit_advisory_warnings`)
re-printed every entry on every call, so an operator whose command run
touched the hook repeatedly was flooded with duplicate ``Warning:`` lines,
each stripped of the scope (consumer + repo root) that says where the
condition holds.

This module is the single authority for both halves of the #3971 fix:

* :func:`dedupe_warnings` — stable-order, first-occurrence de-duplication
  of a warnings list. Applied where the list is born (the runner's
  advisory-result construction), so every consumer — the stderr seam, the
  dashboard's persisted banner, the JSON contract — sees a duplicate-free
  list without each having to re-filter.
* :func:`render_ambient_warning` — one-line rendering of the single
  surfaced instance with its scope attached. The concrete remedy stays
  part of the warning text itself (both ambient warning constants end in
  an exact recovery command); ``tests/…/test_preflight_ambient_warning.py``
  guards that every warning surfaced through this channel keeps one.
* :data:`_SURFACED` + :func:`warning_already_surfaced` /
  :func:`record_surfaced` / :func:`_reset_surfaced_for_testing` — the
  process-lifetime latch that makes each distinct ambient warning print at
  most once per command run (one CLI invocation = one process). This
  mirrors the ``retrospective.deprecation._EMITTED`` one-warn-per-process
  precedent; tests that exercise the advisory pathway MUST reset the latch
  between cases via :func:`_reset_surfaced_for_testing`.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "dedupe_warnings",
    "record_surfaced",
    "render_ambient_warning",
    "warning_already_surfaced",
]


#: Process-lifetime guard (#3971): each distinct ambient warning (identity =
#: the exact warning text) is surfaced at most once per command run. One CLI
#: invocation is one process, so this is exactly the "show each once across a
#: command run" budget. Module-level mutable state, same shape as
#: ``retrospective.deprecation._EMITTED``.
_SURFACED: set[str] = set()

#: Suffix appended to the single surfaced instance. Names the consumer that
#: ran preflight and the repo root the condition was computed against — the
#: two facts an operator needs to know *where* the ambient condition holds —
#: and states that the warning is advisory, so it is never mistaken for a
#: block. Kept as one constant (Sonar S1192): the renderer is its only user.
_SCOPE_SUFFIX = " (scope: charter preflight, consumer '{consumer}', repo root '{repo}'; advisory only — the command continues; shown once per command run)"


def dedupe_warnings(warnings: list[str]) -> list[str]:
    """Return *warnings* without duplicates, keeping first-occurrence order.

    Identity is the exact warning text: two entries with the same text name
    the same ambient condition, so the second adds no information. Order is
    preserved so layer-ordered producers stay layer-ordered.
    """
    seen: set[str] = set()
    deduped: list[str] = []
    for text in warnings:
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def warning_already_surfaced(text: str) -> bool:
    """Return True iff *text* was already surfaced in this command run."""
    return text in _SURFACED


def record_surfaced(text: str) -> None:
    """Mark *text* as surfaced for the rest of this command run."""
    _SURFACED.add(text)


def render_ambient_warning(
    text: str,
    *,
    consumer: str,
    repo_root: Path | None,
) -> str:
    """Render the single surfaced ambient-warning instance with its scope.

    The line keeps the historical ``Warning: <text>`` prefix (existing
    consumers match on that substring) and appends the scope suffix naming
    the consumer and repo root. The concrete remedy is carried by the
    warning text itself — every ambient warning surfaced through this
    channel ends in an exact recovery command.
    """
    repo = str(repo_root) if repo_root is not None else "<unresolved>"
    return f"Warning: {text}{_SCOPE_SUFFIX.format(consumer=consumer, repo=repo)}"


def _reset_surfaced_for_testing() -> None:
    """Clear the surfaced latch so tests can re-exercise the emission path.

    Underscore-private on purpose: the symbol-level dead-code gate
    (#470) scopes every *public* module-level name, and this helper has no
    ``src/`` caller by design — production must never reset the latch (a
    fresh CLI process starts empty by construction), only test fixtures
    do. Mirrors ``retrospective.deprecation.reset_emitted_for_testing``
    in intent, privatized so it never needs allowlist debt.
    """
    _SURFACED.clear()
