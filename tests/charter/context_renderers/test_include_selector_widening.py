"""`--include` selector widening for glossary_pack + anti_pattern (WP04 / #2981).

Red-first: on `main` the `_render_offering_artifact_include` renderers dict has no
`glossary_pack` or `anti_pattern` entry, so both fall through to the caller's
"Unsupported --include selector kind" error even though they are legitimate
charter-activatable kinds. After WP04 every charter-activatable kind is a
recognised selector kind (glossary_pack renders; anti_pattern resolves to a
standard not-found) — never "unsupported" (FR-006 / SC-003 / S1).
"""

from __future__ import annotations

import pytest

from charter.activation.context_renderers.template_include import (
    _render_offering_artifact_include,
)
from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, ArtifactKind
from charter.offering.glossary_packs.models import GlossaryPack, GlossaryTerm

pytestmark = [pytest.mark.fast, pytest.mark.unit]


class _Repo:
    def __init__(self, items: dict[str, object]) -> None:
        self._items = items

    def get(self, artifact_id: str) -> object | None:
        return self._items.get(artifact_id)


def _pack() -> GlossaryPack:
    return GlossaryPack(
        id="spec-kitty-core",
        provenance="builtin",
        description="Core Spec Kitty terminology.",
        terms=[
            GlossaryTerm(
                surface="Mission",
                definition="A unit of work.",
                status="active",
                confidence=1.0,
            )
        ],
    )


class _ServiceWithGlossary:
    def __init__(self) -> None:
        self.glossary_packs = _Repo({"spec-kitty-core": _pack()})


class _EmptyService:
    """A service exposing no doctrine repositories."""


# ── T020: glossary_pack renders ───────────────────────────────────────────────


def test_glossary_pack_selector_renders() -> None:
    out = _render_offering_artifact_include(_ServiceWithGlossary(), "glossary_pack", "spec-kitty-core")
    assert out is not None
    assert "Glossary pack spec-kitty-core" in out
    assert "Mission: A unit of work." in out


def test_glossary_pack_missing_id_is_not_found_not_unsupported() -> None:
    with pytest.raises(ValueError, match="No glossary_pack found for selector"):
        _render_offering_artifact_include(_ServiceWithGlossary(), "glossary_pack", "does-not-exist")


# ── T021: anti_pattern recognised (not-found, never "unsupported") ────────────


def test_anti_pattern_selector_is_recognised_not_found() -> None:
    """`anti_pattern` has no service repo/files → recognised not-found form."""
    with pytest.raises(ValueError, match="No anti_pattern found for selector"):
        _render_offering_artifact_include(_EmptyService(), "anti_pattern", "x")


# ── T024: S1 — every charter-activatable kind is a recognised selector kind ───


@pytest.mark.parametrize("kind", sorted(k.value for k in CHARTER_ACTIVATABLE_KINDS))
def test_every_activatable_kind_is_recognised(kind: str) -> None:
    """No charter-activatable kind returns None (which the caller turns into
    "Unsupported --include selector kind"). Each resolves or is a not-found.
    """
    try:
        result = _render_offering_artifact_include(_EmptyService(), kind, "missing-id")
    except ValueError as exc:
        assert "found for selector" in str(exc)  # recognised not-found
    else:
        # A renderer that returns None would signal an unsupported kind.
        assert result is not None, f"{kind} returned None -> would be 'unsupported'"


@pytest.mark.parametrize("kind", ["template", "asset"])
def test_non_activatable_kinds_return_none_unsupported(kind: str) -> None:
    """`template`/`asset` are not charter-activatable → still return None."""
    assert _render_offering_artifact_include(_EmptyService(), kind, "x") is None
    # sanity: these are genuinely excluded from the activatable set
    assert ArtifactKind(kind) not in CHARTER_ACTIVATABLE_KINDS
