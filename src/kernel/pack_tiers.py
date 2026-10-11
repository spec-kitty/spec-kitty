"""Single authority for the Charter Pack tier token (#5825 / #5961 / #6048).

The tier token historically carried two spellings: ``"built-in"`` (the
tier-token sense -- also the on-disk ``packs/built-in/`` directory name) and
``"builtin"`` (a parallel provenance/layer/rank vocabulary). This module is the
one place that names the **tier token**, with a single canonical spelling,
``"built-in"`` (hyphenated), matching the on-disk directory. ``kernel`` is the
only layer importable by every other layer, so the authority lives here and is
re-exported / consumed downward by ``charter`` and ``specify_cli``:

    kernel  <-  charter  <-  specify_cli

Unified provenance spelling (#6048, FR-019). The artifact *provenance/layer*
value emitted by ``charter.offering.base.BaseArtifactRepository`` (and the
agent-profile / pack-skill repositories) is now the **same** canonical
``"built-in"`` spelling this module owns -- the former no-hyphen ``"builtin"``
spelling was folded onto this authority. Every provenance/layer display
(``_LAYER_RANK``, ``_TIER_RANK``, the ``_charter_pack_health`` layer-order
tuple, the dispatch routing frozenset, the pack-skill ``Tier`` alias) now
*derives* from :data:`PACK_TIERS` / :data:`PackTier` / :data:`BUILT_IN` rather
than restating a hand-authored token, so the single-authority gate
(``tests/architectural/test_pack_tier_token_single_authority.py``) keeps an
empty allowlist and catches any hand-authored restatement in either spelling.
The fold changes the serialized provenance spelling; it is a non-migrated
value -- the one persisted carrier
(``.kittify/agent_profiles_manifest.json`` ``source_layer``) is validated as a
non-empty string and regenerated each projection, so it self-heals with no
consumer data migration (NFR-001).

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
#: on-disk ``packs/built-in/`` directory name (consumed by ``kernel.paths``),
#: so a tier token used as a directory segment resolves unchanged.
BUILT_IN: Final = "built-in"

#: The org tier token.
ORG: Final = "org"

#: The project tier token.
PROJECT: Final = "project"

#: The Charter Pack tiers in precedence order (built-in < org < project). The
#: tuple INDEX is the precedence rank, so this is the single ordering authority
#: -- no separate rank map is declared here. The live provenance rank maps
#: (``agent_profiles``/``pack_skills`` ``_LAYER_RANK``/``_TIER_RANK``) now
#: derive their ranks from this tuple's index (#6048), so there is one ordering
#: authority for both the tier token and the artifact provenance layer.
PACK_TIERS: Final[tuple[str, str, str]] = (BUILT_IN, ORG, PROJECT)

#: The tier-token type alias. A ``Literal`` cannot consume a runtime tuple, so
#: its members are spelled here -- this module is the one place the single-
#: authority gate (``tests/architectural/test_pack_tier_token_single_authority.py``)
#: permits a hand-authored tier-token literal.
PackTier = Literal["built-in", "org", "project"]
