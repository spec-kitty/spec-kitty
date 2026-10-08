"""Structural typing seam for charter offering artifact repositories (FR-010, NFR-005).

``charter.activation.context`` and ``charter.activation.progressive_disclosure`` both accept a
charter offering artifact repository (``DirectiveRepository``, ``TacticRepository``,
...) at several call sites, historically typed as bare ``object`` and
therefore needing ``# type: ignore[attr-defined]`` at every ``.get(...)`` /
``.get_provenance(...)`` call. :class:`ArtifactRepository` names the shape
those call sites actually rely on, so mypy can verify the calls without
suppression.

Every concrete offering repository already satisfies this Protocol
structurally, with no repository-side changes required:
:class:`charter.offering.base.BaseArtifactRepository` (the shared base class for
``DirectiveRepository``, ``TacticRepository``, ``StyleguideRepository``, and
friends) already implements ``get(item_id: str) -> T | None`` and
``get_provenance(item_id: str) -> str | None`` (``src/charter/offering/base.py``).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

__all__ = ["ArtifactRepository"]

# Covariant: T only ever appears in return position (``get`` produces a T,
# never consumes one), so a repository of a more specific artifact type is
# assignable wherever a repository of a more general one is expected.
T = TypeVar("T", covariant=True)


class ArtifactRepository(Protocol[T]):
    """Structural contract satisfied by every concrete offering repository.

    Kept intentionally minimal -- two methods, the only ones the retyped call
    sites in ``charter.activation.context`` / ``charter.activation.progressive_disclosure`` invoke.
    Widen this Protocol rather than introducing a second one if a future call
    site needs another repository method (keep one clean typed seam).
    """

    def get(self, artifact_id: str) -> T | None:  # pragma: no cover -- Protocol stub, never executed
        """Return the artifact for *artifact_id*, or ``None`` if absent."""
        ...

    def get_provenance(self, artifact_id: str) -> str | None:  # pragma: no cover -- Protocol stub, never executed
        """Return the source layer (``"builtin"``/``"org"``/``"project"``) for *artifact_id*, or ``None``."""
        ...
