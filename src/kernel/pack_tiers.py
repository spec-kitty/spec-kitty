"""Single authority for the Charter Pack tier token (#5825 / #5961).

The tier token historically carried two spellings: ``"built-in"`` (the
tier-token sense -- also the on-disk ``packs/built-in/`` directory name) and
``"builtin"`` (a parallel provenance/layer/rank vocabulary). This module is the
one place that names the **tier token**, with a single canonical spelling,
``"built-in"`` (hyphenated), matching the on-disk directory. ``kernel`` is the
only layer importable by every other layer, so the authority lives here and is
re-exported / consumed downward by ``charter`` and ``specify_cli``:

    kernel  <-  charter  <-  specify_cli

Scope note (NFR-003). This unifies the **tier token** only. The separate,
no-hyphen ``"builtin"`` *provenance/layer* value emitted by
``charter.offering.base.BaseArtifactRepository`` (and the agent-profile /
pack-skill repositories) is a persisted-and-compared value: it is serialized
into the charter context JSON and compared in-memory by many consumers, pinned
by that spelling across the test suite. It is deliberately NOT folded onto this
authority here -- respelling it would change a persisted/compared value, which
NFR-003 forbids.

Layer rule: ``kernel`` imports nothing upward (no ``charter``, ``glossary``,
``runtime`` or ``specify_cli``), so every layer can use this module. It imports
only :mod:`typing`.
"""

from __future__ import annotations

from typing import Final, Literal

__all__ = [
    "BUILT_IN",
    "ORG",
    "PACK_TIERS",
    "PROJECT",
    "PackTier",
]

#: The single canonical spelling of the built-in tier token. Matches the
#: on-disk ``packs/built-in/`` directory name (``kernel.paths._BUILT_IN_DIR_NAME``),
#: so a tier token used as a directory segment resolves unchanged.
BUILT_IN: Final = "built-in"

#: The org tier token.
ORG: Final = "org"

#: The project tier token.
PROJECT: Final = "project"

#: The Charter Pack tiers in precedence order (built-in < org < project). The
#: tuple INDEX is the precedence rank, so this is the single ordering authority
#: -- no separate rank map is declared (a ``"built-in"``-keyed rank dict would
#: have no live consumer, since the live rank maps are frozen on the ``"builtin"``
#: provenance spelling per NFR-003).
PACK_TIERS: Final[tuple[str, str, str]] = (BUILT_IN, ORG, PROJECT)

#: The tier-token type alias. A ``Literal`` cannot consume a runtime tuple, so
#: its members are spelled here -- this module is the one place the single-
#: authority gate (``tests/architectural/test_pack_tier_token_single_authority.py``)
#: permits a hand-authored tier-token literal.
PackTier = Literal["built-in", "org", "project"]
