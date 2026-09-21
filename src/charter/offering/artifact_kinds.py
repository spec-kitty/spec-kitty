"""Canonical enumeration of all doctrine artifact kinds.

Single source of truth for artifact type names, plural forms, and glob patterns.
Zero-dependency: no imports from specify_cli or other doctrine subpackages.

Canonical charter kind universe (R-009)
---------------------------------------
The charter command surfaces (``activate`` / ``deactivate`` / ``list`` /
``context --include``) operate over the *charter kind universe*, which is::

    the 9 activatable ``ArtifactKind`` kinds  +  ``mission-type``

``mission-type`` is **not** an :class:`ArtifactKind` member — it is a mission-tier
concept handled separately (see FR-032 / WP04). Callers route a mission-type
token explicitly; :meth:`ArtifactKind.from_operator_token` raises the distinct,
documented :class:`MissionTypeNotAnArtifactKind` for it rather than silently
mapping it to an artifact kind (R-009 / CL-1: no silent fallback).

``template`` *is* an :class:`ArtifactKind` member but is resolved specially
(mission-tier, empty glob — see :attr:`ArtifactKind.glob_pattern`); it is not one
of the 9 non-template artifact tokens enumerated in :data:`CHARTER_KIND_TOKENS`.

``anti_pattern`` *is* an :class:`ArtifactKind` member (mission
``doctrine-tension-edges-01KY1WPC``, D2) but is also excluded from the charter
kind universe via :data:`_NON_AUGMENTATION_ELIGIBLE_KINDS`: an anti-pattern
node is never activated as a live rule and is never hand-authored as a
standalone artifact file, so it is not one of the 9 charter-activatable
artifact tokens either.

Consumers must route every operator kind string through
:meth:`ArtifactKind.from_operator_token` (CC-4) — no second kind enumeration
may be re-declared elsewhere.
"""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import quote


class MissionTypeNotAnArtifactKind(ValueError):
    """Raised when ``mission-type`` is passed to :meth:`ArtifactKind.from_operator_token`.

    ``mission-type`` is part of the charter kind universe but is *not* an
    :class:`ArtifactKind` member. Callers must route it explicitly to the
    mission-tier handling path. This is a distinct, documented error (a
    :class:`ValueError` subclass) so callers can catch it specifically and
    branch, instead of treating mission-type as an unknown token.
    """

_PLURALS: dict[str, str] = {
    "directive": "directives",
    "tactic": "tactics",
    "styleguide": "styleguides",
    "toolguide": "toolguides",
    "paradigm": "paradigms",
    "procedure": "procedures",
    "agent_profile": "agent_profiles",
    "mission_step_contract": "mission_step_contracts",
    "template": "templates",
    "asset": "assets",
    "glossary_pack": "glossary_packs",
    "anti_pattern": "anti_patterns",
}

#: Single source of truth for "does this kind ship a `packs/built-in/<plural>/`
#: content directory". Backs :attr:`ArtifactKind.has_built_in_content_dir`
#: (mission ``doctrine-built-in-seam-consolidation-01KYW3TX``, WP01). Exactly
#: 9 kinds are ``True`` -- ``agent_profile``, ``asset``, ``directive``,
#: ``glossary_pack``, ``paradigm``, ``procedure``, ``styleguide``, ``tactic``,
#: ``toolguide``. The 3-kind carve-out (``mission_step_contract``, ``template``,
#: ``anti_pattern``) is ``False``: these are package-resource/graph-only kinds
#: with no shipped content directory (see mission #3091 for the step-contract/
#: template relocation). Do NOT reuse :data:`_NON_AUGMENTATION_ELIGIBLE_KINDS`
#: for this purpose -- it is a *different* exclusion set (it carries ``asset``,
#: which HAS a content dir, and omits ``mission_step_contract``, which does
#: NOT). ``charter.offering.pack_paths.built_in_dir`` derives its refusal-complement
#: from this attribute; it must never hand-list the complement itself
#: (FR-005 / NFR-005).
_HAS_BUILT_IN_CONTENT_DIR: dict[str, bool] = {
    "directive": True,
    "tactic": True,
    "styleguide": True,
    "toolguide": True,
    "paradigm": True,
    "procedure": True,
    "agent_profile": True,
    "mission_step_contract": False,
    "template": False,
    "asset": True,
    "glossary_pack": True,
    "anti_pattern": False,
}

_PATTERNS: dict[str, str] = {
    "directive": "*.directive.yaml",
    "tactic": "*.tactic.yaml",
    "styleguide": "*.styleguide.yaml",
    "toolguide": "*.toolguide.yaml",
    "paradigm": "*.paradigm.yaml",
    "procedure": "*.procedure.yaml",
    "agent_profile": "*.agent.yaml",
    "mission_step_contract": "*.step-contract.yaml",
    "template": "",
    "asset": "*.asset.yaml",
    "glossary_pack": "*.glossary-pack.yaml",
    # anti_pattern nodes are hand-authored inside existing graph fragments
    # (re-kinded/tagged paradigm/tactic nodes, D2) -- there is no dedicated
    # `*.anti_pattern.yaml` artifact file convention. The pattern is declared
    # for consistency with every other ArtifactKind member (avoids a KeyError
    # in generic `for kind in ArtifactKind: kind.glob_pattern` consumers) but
    # is not expected to match any file on disk.
    "anti_pattern": "*.anti_pattern.yaml",
}

#: Operator token (hyphenated CLI surface) that callers must explicitly route to
#: the mission-tier path; it is part of the charter kind universe but not an
#: :class:`ArtifactKind` member. See :class:`MissionTypeNotAnArtifactKind`.
# Not a secret: ruff's bandit-derived S105 check flags any string literal
# assigned to a name containing "TOKEN". The value is an operator-facing CLI
# token, not a credential, so the S105 finding is suppressed on the line below.
MISSION_TYPE_TOKEN = "mission-type"  # noqa: S105


class ArtifactKind(StrEnum):
    """All doctrine artifact types.

    String values are the canonical singular form stored in YAML ``type`` fields.
    Use :attr:`plural` for directory names and :attr:`glob_pattern` for file discovery.
    """

    DIRECTIVE = "directive"
    TACTIC = "tactic"
    STYLEGUIDE = "styleguide"
    TOOLGUIDE = "toolguide"
    PARADIGM = "paradigm"
    PROCEDURE = "procedure"
    AGENT_PROFILE = "agent_profile"
    MISSION_STEP_CONTRACT = "mission_step_contract"
    TEMPLATE = "template"
    ASSET = "asset"
    GLOSSARY_PACK = "glossary_pack"
    ANTI_PATTERN = "anti_pattern"

    @property
    def plural(self) -> str:
        """Plural directory name (e.g. ``"directives"``, ``"agent_profiles"``)."""
        return _PLURALS[self.value]

    @property
    def glob_pattern(self) -> str:
        """File glob pattern for this artifact type.

        Returns an empty string for ``TEMPLATE`` (no dedicated extension).
        """
        return _PATTERNS[self.value]

    @property
    def has_built_in_content_dir(self) -> bool:
        """Whether this kind ships a ``packs/built-in/<plural>/`` content dir.

        ``True`` for exactly the 9 shipped content-dir kinds; ``False`` for the
        derived 3-kind carve-out (``MISSION_STEP_CONTRACT``, ``TEMPLATE``,
        ``ANTI_PATTERN``), which are package-resource/graph-only kinds (see
        mission #3091 for the step-contract/template relocation). This is the
        single source of truth :func:`charter.offering.pack_paths.built_in_dir` reads
        to compute its refusal-complement -- never hand-list the complement
        elsewhere.
        """
        return _HAS_BUILT_IN_CONTENT_DIR[self.value]

    @property
    def operator_token(self) -> str:
        """Hyphenated operator token for this kind (CLI surface, help text).

        Inverse of :meth:`from_operator_token`. The token is the canonical
        singular value with underscores replaced by hyphens
        (e.g. ``ArtifactKind.AGENT_PROFILE.operator_token == "agent-profile"``).
        """
        return self.value.replace("_", "-")

    @classmethod
    def from_plural(cls, plural: str) -> ArtifactKind:
        """Return the enum member matching a plural directory name.

        Raises :class:`KeyError` if *plural* is not a known plural form.
        """
        for member in cls:
            if member.plural == plural:
                return member
        raise KeyError(f"No ArtifactKind with plural {plural!r}")

    @classmethod
    def from_operator_token(cls, token: str) -> ArtifactKind:
        """Return the :class:`ArtifactKind` for a documented operator token.

        Normalizes the operator token (the hyphenated CLI surface form) to the
        canonical underscore singular and resolves it. Accepts both the
        hyphenated form (``agent-profile``) and the already-canonical underscore
        form (``agent_profile``); matching is case-insensitive.

        This is the **single** entry point charter surfaces use to turn a kind
        string into a canonical kind — no surface may re-declare the kind set
        (R-009 / CC-4).

        Args:
            token: Operator kind token, e.g. ``"agent-profile"``,
                ``"mission-step-contract"``, ``"directive"``.

        Returns:
            The matching :class:`ArtifactKind` member.

        Raises:
            MissionTypeNotAnArtifactKind: if *token* is ``"mission-type"``. This
                is part of the charter kind universe but is mission-tier, not an
                artifact kind — callers must route it explicitly.
            ValueError: if *token* is not a documented operator token. The error
                message lists the valid operator tokens (no silent fallback —
                R-009 / CL-1).
        """
        normalized = token.strip().lower().replace("-", "_")
        if normalized == MISSION_TYPE_TOKEN.replace("-", "_"):
            raise MissionTypeNotAnArtifactKind(
                "'mission-type' is part of the charter kind universe but is not "
                "an ArtifactKind; route it through the mission-tier handler."
            )
        for member in cls:
            if member.value == normalized:
                return member
        valid = ", ".join(member.operator_token for member in cls)
        raise ValueError(
            f"Unknown artifact kind token {token!r}. "
            f"Valid operator tokens: {valid}."
        )


#: Canonical set of :class:`ArtifactKind` members that are never eligible for
#: pack augmentation (``enhances``/``overrides``) or the charter kind universe.
#: ``TEMPLATE`` is mission-tier and resolves specially (empty glob); ``ASSET``
#: is a loose-contract kind excluded from the same surfaces (FR-005/FR-011).
#: ``ANTI_PATTERN`` (mission ``doctrine-tension-edges-01KY1WPC``, D2) is
#: excluded for the same reason: it is never activated as a live rule and is
#: never hand-authored as a standalone artifact file -- it is a re-kinded/
#: tagged node inside an existing graph fragment, referenced only via
#: ``rejects`` edges. This is the **single** canonical exclusion set —
#: downstream modules (``org_pack_loader.py``, the charter cascade) must
#: import this rather than re-declaring their own exclusion list.
_NON_AUGMENTATION_ELIGIBLE_KINDS: frozenset[ArtifactKind] = frozenset(
    {ArtifactKind.TEMPLATE, ArtifactKind.ASSET, ArtifactKind.ANTI_PATTERN}
)


#: Charter kind universe: the non-excluded artifact operator tokens + the
#: special ``mission-type`` token. Members of :data:`_NON_AUGMENTATION_ELIGIBLE_KINDS`
#: (``template``, ``asset``, ``anti_pattern``) resolve specially and are *not*
#: listed here.
CHARTER_KIND_TOKENS: tuple[str, ...] = tuple(
    member.operator_token
    for member in ArtifactKind
    if member not in _NON_AUGMENTATION_ELIGIBLE_KINDS
) + (MISSION_TYPE_TOKEN,)


#: The runtime-managed kinds whose **project-tier overlay** directory is the
#: *singular* form (``.kittify/doctrine/directive/``, …) rather than the plural.
#: These four kinds carry per-project overlays that the live loader reads from a
#: singular directory; every other kind uses its plural. This is the *only*
#: place that asymmetry is declared.
_SINGULAR_PROJECT_DIR_KINDS: frozenset[ArtifactKind] = frozenset(
    {
        ArtifactKind.DIRECTIVE,
        ArtifactKind.TACTIC,
        ArtifactKind.STYLEGUIDE,
        ArtifactKind.PROCEDURE,
    }
)


#: **Canonical project-tier directory authority** (WP03 / R-009 / CC-4).
#:
#: Maps every :class:`ArtifactKind` to the directory name its artifacts live
#: under in a project overlay (``.kittify/doctrine/<dir>/``). This is the single
#: source of truth the ``doctrine new`` scaffolder, :class:`DoctrineService`'s
#: project-dir resolver (``charter.offering.service``), and the charter resolvers
#: (``charter.activation.kind_vocabulary`` / ``charter.activation.pack_manager``) all import — **no
#: consumer re-declares it** (the module docstring's "no second kind
#: enumeration" rule). ``doctrine`` is the lowest layer, so charter and
#: specify_cli import *down* into it (C-001-legal).
#:
#: Declared as an explicit, **total** literal (not a comprehension) so the
#: kind-mapping totality guard
#: (``tests/doctrine/drg/test_kind_mapping_totality.py``) discovers it via its
#: AST scan and certifies exhaustiveness: a new :class:`ArtifactKind` added
#: without an entry here fails that guard rather than falling through a silent
#: ``.get`` default. Fail-closed — there is no fallback; a missing key is a
#: :class:`KeyError`. The four :data:`_SINGULAR_PROJECT_DIR_KINDS` map to their
#: singular value; every other kind maps to its :attr:`ArtifactKind.plural`
#: (asserted in ``tests/doctrine/test_artifact_kinds.py``).
PROJECT_KIND_DIRS: dict[ArtifactKind, str] = {
    ArtifactKind.DIRECTIVE: "directive",
    ArtifactKind.TACTIC: "tactic",
    ArtifactKind.STYLEGUIDE: "styleguide",
    ArtifactKind.PROCEDURE: "procedure",
    ArtifactKind.TOOLGUIDE: "toolguides",
    ArtifactKind.PARADIGM: "paradigms",
    ArtifactKind.AGENT_PROFILE: "agent_profiles",
    ArtifactKind.MISSION_STEP_CONTRACT: "mission_step_contracts",
    ArtifactKind.TEMPLATE: "templates",
    ArtifactKind.ASSET: "assets",
    ArtifactKind.GLOSSARY_PACK: "glossary_packs",
    ArtifactKind.ANTI_PATTERN: "anti_patterns",
}


#: **Canonical charter-activatable kind set** (FR-004 / FR-005 / C-003).
#:
#: Every :class:`ArtifactKind` *except* the two that resolve specially and are
#: never activated as a live governance rule: ``TEMPLATE`` (mission-tier, empty
#: glob) and ``ASSET`` (loose-contract blob manifest). This is **10 kinds,
#: including ``ANTI_PATTERN``** — deliberately distinct from both
#: :data:`CHARTER_KIND_TOKENS` (9 tokens; also drops ``anti_pattern`` via
#: :data:`_NON_AUGMENTATION_ELIGIBLE_KINDS`) and that exclusion set itself
#: (which additionally drops ``anti_pattern``). C-003/FR-005 require the
#: ``anti_pattern`` entry be preserved here, so this set uses its own two-kind
#: exclusion rather than reusing ``_NON_AUGMENTATION_ELIGIBLE_KINDS``.
#:
#: This is the single authority the charter activation-kind vocabulary
#: (``charter.activation.activations`` plural↔singular maps,
#: ``charter.activation._activation_render``
#: render/inference maps) is derived from — no charter module re-declares a
#: plural↔singular kind dict (FR-004).
CHARTER_ACTIVATABLE_KINDS: frozenset[ArtifactKind] = frozenset(ArtifactKind) - {
    ArtifactKind.TEMPLATE,
    ArtifactKind.ASSET,
}

#: Derived singular→plural map over the charter-activatable kinds (10 entries).
#: Ordered by :class:`ArtifactKind` declaration so downstream first-match
#: semantics (e.g. ``_infer_kind``) are stable.
CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL: dict[str, str] = {
    kind.value: kind.plural
    for kind in ArtifactKind
    if kind in CHARTER_ACTIVATABLE_KINDS
}

#: Derived plural→singular inverse of
#: :data:`CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL`.
CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR: dict[str, str] = {
    plural: singular
    for singular, plural in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.items()
}

#: **Canonical registration-writing (direct-write) kind set** (WP01 / NFR-002).
#:
#: The five artifact kinds that are authored directly into a project's
#: ``.kittify/doctrine/<dir>/`` overlay and flow through the project scanner and
#: the synthesis manifest. This is the single source of truth the DRG project
#: scanner (``charter.offering.drg.project_scan``) reads instead of re-declaring
#: its own five-kind tuple; the synthesis manifest's
#: ``ManifestArtifactEntry.kind`` ``Literal`` is kept aligned by-test
#: (``tests/charter/test_direct_write_kinds_parity.py``) because a ``Literal``
#: cannot consume a runtime tuple.
#:
#: Order is load-bearing: the scanner pairs this tuple positionally with a
#: parallel ``schemas`` tuple (``directive`` → ``Directive`` …), so a reorder
#: here must be mirrored there.
DIRECT_WRITE_KINDS: tuple[str, ...] = (
    "directive",
    "tactic",
    "styleguide",
    "procedure",
    "agent_profile",
)


def slug_for(kind: str, identifier: str) -> str:
    """Return the canonical, filesystem-safe slug for an artifact identity.

    This is the **single producer-side slug derivation** (the anti-drift
    authority for WP03's convergence invariant). It is pure: deterministic, no
    IO, no global state — the same ``(kind, identifier)`` always yields the same
    slug. Extracted verbatim from the pre-refactor inline expression in
    ``charter.activation.project_registration`` so the extraction is provably
    byte-identical::

        quote(id.lower().replace("_", "-") if kind == "directive" else id, safe="")

    ``kind == "directive"`` ids are case-folded and underscore→hyphen normalized
    (``LOVE_THY_ENEMY`` → ``love-thy-enemy``); every other kind's identifier is
    preserved as-authored.

    ``quote(..., safe="")`` is **load-bearing, not decoration**: it collapses a
    slash-bearing URN identity (e.g. ``agent_profile:team/ops-responder`` →
    ``team%2Fops-responder``) into a single safe path component so a downstream
    ``provenance_path_for`` cannot escape ``.kittify/charter/provenance/``.

    Id-grammar precondition: directive ids match ``^[A-Z][A-Z0-9_-]*$``;
    non-directive ids are lowercase-kebab and URN-safe. Under this grammar
    ``quote`` is a no-op for well-formed ids, but it is retained as
    defense-in-depth. Because a directive id always has a leading letter, the
    result never begins with a pure-digit segment, so an optional downstream
    ``NNN-`` prefix strip cannot truncate it.
    """
    normalized = identifier.lower().replace("_", "-") if kind == "directive" else identifier
    return quote(normalized, safe="")


__all__ = [
    "ArtifactKind",
    "CHARTER_ACTIVATABLE_KINDS",
    "CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR",
    "CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL",
    "CHARTER_KIND_TOKENS",
    "DIRECT_WRITE_KINDS",
    "MISSION_TYPE_TOKEN",
    "PROJECT_KIND_DIRS",
    "MissionTypeNotAnArtifactKind",
    "slug_for",
]
