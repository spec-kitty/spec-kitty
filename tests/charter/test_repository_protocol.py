"""Structural-typing seam tests for ``charter.repository_protocol`` (FR-010, NFR-005).

``ArtifactRepository`` is a pure typing ``Protocol`` -- its two method bodies
(``...``) are never executed at runtime; every consuming import site
(``charter.activation.context``, ``charter.activation.progressive_disclosure``) pulls the name in
under ``if TYPE_CHECKING:`` only, so nothing in production code ever imports
this module at runtime either. mypy verifies structural conformance
statically, not by calling the stub bodies -- see ``src/charter/repository_protocol.py``
for the two method stubs, which carry ``# pragma: no cover`` because they are
inherently unexecutable (coverage cannot run a body that is never invoked).

These tests pin the module's importable public surface -- the ``__all__``
export and the two method names every concrete doctrine repository (e.g.
``BaseArtifactRepository`` in ``src/charter/offering/base.py``) must keep exposing --
without instantiating the Protocol or faking a repository that "implements"
it (structural typing needs no such thing).
"""

from __future__ import annotations

import pytest

from charter.repository_protocol import ArtifactRepository

pytestmark = pytest.mark.fast


def test_module_exports_only_artifact_repository() -> None:
    """The typing seam's public surface is exactly ``ArtifactRepository`` (NFR-005)."""
    import charter.repository_protocol as repository_protocol_module

    assert repository_protocol_module.__all__ == ["ArtifactRepository"]


def test_artifact_repository_declares_get_and_get_provenance() -> None:
    """Pins the two-method structural contract every doctrine repository satisfies.

    ``charter.activation.context`` / ``charter.activation.progressive_disclosure`` retype their
    ``.get(...)`` / ``.get_provenance(...)`` call sites against these exact
    names (see the module docstring in ``repository_protocol.py``); losing
    either one silently would reopen the ``# type: ignore[attr-defined]``
    suppressions this Protocol exists to remove.
    """
    assert callable(ArtifactRepository.get)
    assert callable(ArtifactRepository.get_provenance)
