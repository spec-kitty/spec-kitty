"""Canonical exception hierarchy for Spec Kitty internal-consistency errors.

Lives in ``kernel`` because every other package (``charter``, ``doctrine``,
``specify_cli``) is allowed to depend on ``kernel`` but ``kernel`` depends on
nothing else. This breaks the import cycle that would otherwise prevent
``charter`` from referencing the base error type when ``specify_cli``'s
package init eagerly registers commands that touch ``charter`` back.

``KittyInternalConsistencyError`` is the canonical base for any error that
indicates the system detected a violated internal invariant — content that
cannot be safely processed under the project's contract (e.g. a charter file
in an ambiguous encoding), state that contradicts a declared schema, or an
artifact that cannot be reconciled with its origin.

These errors are **never** silently swallowed by ``except Exception`` in
production code. Subsystems raise specific subclasses (e.g.
``CharterEncodingError``); CLI / TUI / UI layers catch the base and render
the diagnostic uniformly so the operator sees the actual failure mode rather
than an empty result.

Attributes carried by every subclass:

- ``code``: JSON-stable diagnostic string (e.g. ``"CHARTER_ENCODING_AMBIGUOUS"``).
  Suitable for machine consumers (CI harnesses, dashboards, the cross-surface
  fixture harness in epic #992 Phase 0).
- ``body``: human-readable detail with remediation steps. Suitable for stderr,
  TUI dialogs, or a web error panel.

``GuardedReadError`` is a **separate, unrelated** base (deliberately *not* a
``KittyInternalConsistencyError`` subclass — see :class:`GuardedReadError`'s
own docstring) for the guarded-read + CLI error-presentation seam
(mission ``cli-error-surface-seam``, umbrella #2899). Both families coexist in
this module; do not merge them.
"""

from __future__ import annotations

__all__ = [
    "GuardedReadError",
    "KittyInternalConsistencyError",
]


class KittyInternalConsistencyError(Exception):
    """Base for errors indicating a violated internal invariant.

    Subsystems raise more specific subclasses; CLI/TUI/UI layers catch this
    base type to render the diagnostic uniformly. Do **not** catch in bare
    ``except Exception`` blocks in production code.
    """

    def __init__(self, code: str, body: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.body = body


class GuardedReadError(Exception):
    """Base for a read/decode failure collapsed by ``kernel.guarded_read.read_guarded``.

    The single type the global CLI error-presentation hook catches (see
    ``contracts/error-envelope.md``). Every legacy typed reader error (e.g.
    ``UnsafePathSegmentError``, ``MissionMetaReadError``, ``MetaDecodeError``)
    and every new domain-read error subclasses this via multiple inheritance
    so their existing ``except <LegacyError>`` / ``except ValueError`` call
    sites keep matching (D3 — subclass, never flat-replace).

    Plain ``Exception`` subclass, deliberately not tied to ``OSError`` — a
    re-parented legacy error also inherits ``ValueError``/``RuntimeError``
    via multiple inheritance, and an ``OSError`` base would force an
    incompatible MRO for those.

    Positional-compatible constructor: several re-parented legacy errors
    build their own message text and pass it as a single positional argument
    to ``super().__init__(...)`` — a required-kwargs signature would raise
    ``TypeError`` at every one of those call sites (and at their existing
    test constructors). ``path``/``reason`` are optional keyword-only
    attributes populated by :func:`kernel.guarded_read.read_guarded`; a
    legacy error that does not pass them leaves both ``None``, and
    :meth:`__str__` falls back to the positional ``args`` message (the
    presentation hook falls back the same way).

    Attributes:
        path: The offending file/handle, or ``None`` when not path-scoped.
        reason: The actionable human-facing message, or ``None`` when the
            subclass's own ``args`` already carries it.
    """

    def __init__(self, *args: object, path: str | None = None, reason: str | None = None) -> None:
        super().__init__(*args)
        self.path = path
        self.reason = reason

    def __str__(self) -> str:
        if self.reason is not None:
            return self.reason
        return super().__str__()
