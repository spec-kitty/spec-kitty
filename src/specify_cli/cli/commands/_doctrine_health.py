"""Single-source doctrine health model for ``spec-kitty doctor charter-packs`` (WP08).

Both the human-readable renderer and the ``--json`` emitter consume one
:class:`DoctrineHealthReport`; neither assembles its own parallel view of the
data (research R-011-C found the old command built the two surfaces
independently and let pack health "green" on snapshot *presence* rather than on
whether every discovered profile actually loaded).

The two invariants this module enforces:

* **I-H1 (derived health):** a pack/layer is healthy iff every discovered
  profile loaded *and* there are no invalid-profile diagnostics
  (``valid_count == discovered_count and not invalid_profiles``).  Health is
  never inferred from snapshot presence (FR-010).
* **Single source:** :meth:`DoctrineHealthReport.to_dict` is the only JSON
  shape, and the human renderer reads the same dataclasses, so the two output
  surfaces can never drift.

Invalid-profile diagnostics are a verbatim passthrough of the WP05
:class:`~charter.offering.agent_profiles.diagnostics.SkippedProfile` records returned by
``AgentProfileRepository.skipped_profiles()`` — they are *not* scraped from
warning text (FR-008/FR-009).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from charter.profiles import SkippedProfile

__all__ = [
    "PackHealth",
    "DoctrineHealthReport",
    "build_pack_health_by_layer",
    "GlossaryPackHealth",
    "SkippedGlossaryPack",
    "PackSkillHealth",
    "SkippedPackSkill",
]

#: Operator-facing reading order for doctrine layers.
_LAYER_ORDER: tuple[str, ...] = ("builtin", "org", "project")


def _skipped_to_dict(skipped: SkippedProfile) -> dict[str, object]:
    """Serialise one :class:`SkippedProfile` to a stable JSON dict.

    The field set is pinned (``layer``/``path``/``profile_id``/
    ``error_summary``) so downstream tooling can rely on it (T034 validation).
    """
    return {
        "layer": skipped.layer,
        "path": skipped.path,
        "profile_id": skipped.profile_id,
        "error_summary": skipped.error_summary,
    }


@dataclass(frozen=True)
class PackHealth:
    """Health of the agent-profile surface for a single doctrine layer.

    Attributes:
        pack_id: Stable identifier for the surface (the layer name, since
            agent-profile health is attributed per layer, not per org pack).
        layer: One of ``"builtin"``, ``"org"``, ``"project"``.
        discovered_count: Profile files discovered for this layer
            (valid + invalid).
        valid_count: Profile files that loaded successfully for this layer.
        invalid_profiles: WP05 ``SkippedProfile`` records for this layer
            (verbatim passthrough, never regex-scraped).
    """

    pack_id: str
    layer: str
    discovered_count: int
    valid_count: int
    invalid_profiles: list[SkippedProfile] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Derived health (I-H1 / FR-010).

        Healthy iff every discovered profile loaded *and* there are no
        invalid-profile diagnostics — never inferred from snapshot presence.
        """
        return self.valid_count == self.discovered_count and not self.invalid_profiles

    def to_dict(self) -> dict[str, object]:
        """JSON-able view; ``healthy`` is emitted explicitly for callers."""
        return {
            "pack_id": self.pack_id,
            "layer": self.layer,
            "discovered_count": self.discovered_count,
            "valid_count": self.valid_count,
            "healthy": self.healthy,
            "invalid_profiles": [
                _skipped_to_dict(profile) for profile in self.invalid_profiles
            ],
        }


@dataclass(frozen=True)
class SkippedGlossaryPack:
    """A single glossary-pack YAML file skipped during repository load (FR-012).

    ``GlossaryPackRepository`` is a plain ``BaseArtifactRepository`` and does
    not carry a WP05-style ``SkippedProfile`` diagnostics list — an
    unloadable pack file (bad YAML, a missing required field, a duplicate
    term surface) is only ever surfaced today as a ``UserWarning`` emitted
    during ``_load()``. This dataclass turns that warning into the same
    surfaced-not-swallowed shape the agent-profile dimension already uses
    (see :class:`PackHealth`/``SkippedProfile``), so an invalid glossary pack
    is never silently absent from the report.

    Attributes:
        layer: The doctrine layer the file belongs to — one of ``"built-in"``,
            ``"org"``, or ``"project"``, or ``"unknown"`` if it could not be
            determined.
        path: The skipped file's name (or ``"unknown"``).
        error_summary: Human-readable reason the file was skipped.
    """

    layer: str
    path: str
    error_summary: str


@dataclass(frozen=True)
class GlossaryPackHealth:
    """Health of the glossary-pack surface (FR-012, SC-001).

    Mirrors :class:`PackHealth`'s counts + health shape but for the
    glossary-pack dimension: ``pack_count``/``term_count`` describe what
    loaded successfully; ``invalid_packs`` carries every skipped pack file.
    An invalid member pack degrades ``healthy`` — a glossary-pack surface
    with even one broken pack file is never reported healthy just because
    other packs loaded fine (the exact anti-pattern SC-001 forbids).

    Attributes:
        pack_count: Number of glossary packs that loaded successfully.
        term_count: Total term count across all successfully-loaded packs.
        invalid_packs: Skipped pack files (verbatim passthrough, never
            regex-scraped from a rendered warning by the caller).
    """

    pack_count: int
    term_count: int
    invalid_packs: list[SkippedGlossaryPack] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Healthy iff no pack file was skipped during load (SC-001)."""
        return not self.invalid_packs

    def to_dict(self) -> dict[str, object]:
        """JSON-able view; ``healthy`` is emitted explicitly for callers."""
        return {
            "pack_count": self.pack_count,
            "term_count": self.term_count,
            "healthy": self.healthy,
            "invalid_packs": [
                {
                    "layer": pack.layer,
                    "path": pack.path,
                    "error_summary": pack.error_summary,
                }
                for pack in self.invalid_packs
            ],
        }


@dataclass(frozen=True)
class SkippedPackSkill:
    """A single pack-skill YAML file skipped during repository load.

    Same surfaced-not-swallowed shape as :class:`SkippedGlossaryPack`: an
    unloadable skill (bad YAML, schema violation, reserved prefix, ``scripts/``
    directory, ``allowed-tools`` frontmatter, an illegal ``enhances``) is never
    silently absent from the report.
    """

    layer: str
    path: str
    error_summary: str


@dataclass(frozen=True)
class PackSkillHealth:
    """Health of the pack-skill surface (FR-015).

    ``skill_count`` is what loaded; ``invalid_skills`` is every skipped file.
    Unhealthy when anything was skipped, so a malformed skill cannot hide
    behind its healthy siblings.
    """

    skill_count: int
    invalid_skills: list[SkippedPackSkill] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Healthy iff no skill file was skipped during load."""
        return not self.invalid_skills

    def to_dict(self) -> dict[str, object]:
        """JSON-able view; ``healthy`` is emitted explicitly for callers."""
        return {
            "skill_count": self.skill_count,
            "loaded": self.skill_count,
            "skipped": len(self.invalid_skills),
            "healthy": self.healthy,
            "invalid_skills": [
                {"layer": skill.layer, "path": skill.path, "error_summary": skill.error_summary}
                for skill in self.invalid_skills
            ],
        }


def _default_glossary_pack_health() -> GlossaryPackHealth:
    """Default glossary-pack health for a report built with no such data.

    Zero packs discovered is treated as healthy (never invented as an
    error) — the empty-report anti-pattern I-H1 guards against is specific
    to the agent-profile dimension (see ``DoctrineHealthReport.healthy``),
    which always expects at least one discovered profile layer.
    """
    return GlossaryPackHealth(pack_count=0, term_count=0)


@dataclass(frozen=True)
class DoctrineHealthReport:
    """Aggregate doctrine health consumed by both human and JSON surfaces.

    Attributes:
        packs: Per-layer agent-profile health (see :class:`PackHealth`).
        org_drg: Structured org-layer DRG state (configured packs, node/edge
            counts, collision warnings, errors) — produced once by the report
            builder so the human and JSON surfaces share a single org-DRG load.
        glossary_packs: Glossary-pack health (FR-012, SC-001) — nested here
            (rather than as a sibling top-level JSON key) so
            ``_emit_doctrine_json`` stays an unmodified passthrough of
            :meth:`to_dict`.
    """

    packs: list[PackHealth] = field(default_factory=list)
    org_drg: dict[str, object] = field(default_factory=dict)
    glossary_packs: GlossaryPackHealth = field(
        default_factory=_default_glossary_pack_health
    )
    skills: PackSkillHealth = field(
        default_factory=lambda: PackSkillHealth(skill_count=0)
    )

    @property
    def healthy(self) -> bool:
        """The whole doctrine surface is healthy iff it is *honestly* green.

        Four conditions, all required (WP01 fail-to-green hardening):

        * ``bool(self.packs)`` — an empty pack list is **not** vacuously healthy.
          ``all([]) == True`` previously reported green-when-broken whenever the
          profile load crashed and degraded to an empty report (the #1584
          false-healthy class).
        * every pack/layer is individually healthy.
        * ``not self.org_drg.get("errors")`` — a non-empty org-DRG error list is
          no longer a blind spot; an org-DRG load failure forces unhealthy.
        * ``self.glossary_packs.healthy`` — an invalid glossary-pack file
          degrades the aggregate too (FR-012, SC-001).
        """
        org_errors = (
            self.org_drg.get("errors") if isinstance(self.org_drg, dict) else None
        )
        return (
            bool(self.packs)
            and all(pack.healthy for pack in self.packs)
            and not org_errors
            and self.glossary_packs.healthy
            and self.skills.healthy
        )

    @property
    def invalid_profiles(self) -> list[SkippedProfile]:
        """Flattened invalid-profile diagnostics across all layers."""
        flattened: list[SkippedProfile] = []
        for pack in self.packs:
            flattened.extend(pack.invalid_profiles)
        return flattened

    def to_dict(self) -> dict[str, object]:
        """The single JSON shape for ``doctor charter-packs --json``."""
        return {
            "healthy": self.healthy,
            "packs": [pack.to_dict() for pack in self.packs],
            "org_drg": self.org_drg,
            "glossary_packs": self.glossary_packs.to_dict(),
            "skills": self.skills.to_dict(),
        }


def build_pack_health_by_layer(
    *,
    provenance_by_layer: dict[str, int],
    skipped_profiles: list[SkippedProfile],
) -> list[PackHealth]:
    """Group valid + skipped profile counts into one :class:`PackHealth` per layer.

    Args:
        provenance_by_layer: ``{layer: valid_count}`` — number of profiles that
            loaded successfully for each layer (from
            ``AgentProfileRepository`` provenance).
        skipped_profiles: WP05 ``SkippedProfile`` diagnostics (any layer).

    Only layers that actually have profiles (valid or skipped) produce a
    ``PackHealth``; a layer with zero discovered profiles is omitted so the
    report does not invent empty surfaces.  ``discovered_count`` is the sum of
    valid + skipped for the layer, so ``healthy`` is purely derived (I-H1).
    """
    skipped_by_layer: dict[str, list[SkippedProfile]] = {}
    for skipped in skipped_profiles:
        skipped_by_layer.setdefault(skipped.layer, []).append(skipped)

    layers = set(provenance_by_layer) | set(skipped_by_layer)
    ordered = [layer for layer in _LAYER_ORDER if layer in layers]
    ordered.extend(sorted(layer for layer in layers if layer not in _LAYER_ORDER))

    packs: list[PackHealth] = []
    for layer in ordered:
        valid = provenance_by_layer.get(layer, 0)
        invalid = skipped_by_layer.get(layer, [])
        packs.append(
            PackHealth(
                pack_id=layer,
                layer=layer,
                discovered_count=valid + len(invalid),
                valid_count=valid,
                invalid_profiles=invalid,
            )
        )
    return packs
