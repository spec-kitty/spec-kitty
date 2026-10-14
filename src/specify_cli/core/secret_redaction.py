"""Fail-closed secret redaction for governed ``SPEC_KITTY_*`` env-var rendering.

Contract: ``kitty-specs/operator-config-ergonomics-01M04YK8/contracts/
provenance-and-channel.md`` C-SEC-1 -- a var NOT on the printable-var
allowlist below (e.g. ``SPEC_KITTY_SAAS_TOKEN``) must never appear BY VALUE
in ``doctor``/``sync status``/logs; only its name and presence may be
reported. This is the single authority every such rendering surface routes
through (starting with the env-file doctor sibling, T019) -- a var never
seen before (new, untriaged, or simply misspelled) is redacted by default,
because :func:`redact` is an ALLOWLIST, not a denylist: absence from
``_PRINTABLE_VARS`` is what triggers redaction, not presence on some
"known secret" list. That is the fail-closed property.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

__all__ = ["RedactedVar", "redact"]

#: Names safe to render BY VALUE. Deliberately conservative: a name is only
#: added here after confirming it can never carry a credential, token, or
#: other secret payload. Everything else -- including a name that merely
#: *looks* harmless -- is redacted (fail-closed, C-SEC-1). This allowlist is
#: intentionally narrower than the full ``SPEC_KITTY_*`` vocabulary; process-
#: internal/derived vars (e.g. ``SPEC_KITTY_CLI_VERSION``,
#: ``SPEC_KITTY_WORKTREE_PATH``) are simply never routed through this
#: module's callers, so they need no explicit denial here.
_PRINTABLE_VARS: frozenset[str] = frozenset(
    {
        "SPEC_KITTY_HOME",
        "SPEC_KITTY_TEMPLATE_ROOT",
        "SPEC_KITTY_NON_INTERACTIVE",
        "SPEC_KITTY_FORCE_INTERACTIVE",
        "SPEC_KITTY_SKIP_PRE_REVIEW_GATE",
        "SPEC_KITTY_NO_BANNER",
        "SPEC_KITTY_NO_NAG",
        "SPEC_KITTY_NO_UPGRADE_CHECK",
    }
)


@dataclass(frozen=True)
class RedactedVar:
    """One governed var's redacted rendering: name + presence, value only when allowlisted.

    Attributes:
        name: The environment variable name.
        present: Whether *mapping* (the caller's ``redact()`` input) carried
            this name at all.
        value: The variable's value, but ONLY when ``name`` is on
            :data:`_PRINTABLE_VARS` AND ``present`` is True. ``None`` in
            every other case -- including a present-but-non-allowlisted var,
            which is exactly the case this module exists to protect (C-SEC-1).
    """

    name: str
    present: bool
    value: str | None


def redact(mapping: Mapping[str, str]) -> list[RedactedVar]:
    """Render *mapping* fail-closed: only allowlisted names carry a value.

    Every key in *mapping* becomes one :class:`RedactedVar` with
    ``present=True``. A key on :data:`_PRINTABLE_VARS` carries its real
    value; every other key -- allowlisted or not, known-secret or simply
    untriaged -- carries ``value=None``. Order is preserved from *mapping*
    (insertion order, matching a caller's own dict/env iteration).

    Args:
        mapping: Governed var name -> raw value (e.g. a merged env-file tier
            or a slice of ``os.environ``).

    Returns:
        One :class:`RedactedVar` per entry in *mapping*, values redacted
        per the allowlist above.
    """
    return [
        RedactedVar(name=name, present=True, value=value if name in _PRINTABLE_VARS else None)
        for name, value in mapping.items()
    ]
