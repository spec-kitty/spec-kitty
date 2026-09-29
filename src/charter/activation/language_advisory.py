"""Consumer-facing advice for projects whose language has no specialist guidance.

Spec Kitty doctrine is technology-agnostic: it never ships guidance for one
language on behalf of another.  When a project's language is unrecognised
(the reserved ``unknown`` value), the right next step is to extend the local
charter rather than to add languages to shipped artifacts.

This is product code, not a doctrine pack artifact.
"""

from __future__ import annotations

__all__ = ["CHARTER_EXTENSION_ADVISORY"]

CHARTER_EXTENSION_ADVISORY = (
    "No specialist guidance exists for this project's language; add "
    "tech-specific guidelines to your local charter "
    "(see 'Extend your charter for an unsupported language')."
)
