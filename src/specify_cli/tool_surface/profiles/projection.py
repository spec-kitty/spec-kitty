"""Project Spec Kitty agent profiles into host-native agent files.

:class:`ProfileProjector` reads resolved profiles from an
:class:`~charter.profiles.AgentProfileRepository` and renders
each into a :class:`~specify_cli.tool_surface.model.NativeAgentProfile` for a
given tool, using the per-harness renderer registry in :mod:`.renderers`.

The projector is *read-only* with respect to the profile model: it calls only
the repository's public query API (``list_all`` / ``get_provenance``) and never
mutates profiles, the DRG, or the scoring model. Tools without a native
named-agent primitive (no renderer) project to an empty list -- the provider
turns that into a research-gap finding.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, replace

from charter.activation.active_charter_service_builder import _build_active_charter_service
from charter.profiles import AgentProfile, AgentProfileRepository, SkippedProfile
from charter.provenance import to_portable_source_path

from specify_cli.invocation.org_profiles import resolve_activated_org_profiles

from ..findings import (
    PROFILE_NAME_INVALID,
    PROFILE_OVERLAY_CONFLICT,
    PROFILE_SENTINEL_SKIPPED,
    PROFILE_SOURCE_INVALID,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SurfaceFinding,
    make_finding,
)
from ..model import NativeAgentProfile, SurfaceSelection
from ..operations import FileState
from .manifest import PROJECTION_VERSION, hash_file as hash_source_file
from .renderers import ProfileRenderer, get_renderer, native_name_violation

# Provenance layers exposed by ``AgentProfileRepository.get_provenance``.
LAYER_BUILTIN = "builtin"
LAYER_ORG = "org"
LAYER_PROJECT = "project"

_PROJECT_PROFILE_SUBDIR = ".kittify/agent_profiles"

_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind agent-profile --fix"


@dataclass(frozen=True)
class PreparedProfileBatch:
    """Opaque owner payload with immutable native projections for bundle consumers.

    Consumers read ``projections``; only the profile owner applies ``contents``
    after checking the complete retained input and destination observations.
    ``entries`` records original ownership, not speculative successful writes.
    """

    projections: tuple[PreparedProjection, ...]
    contents: tuple[tuple[Path, bytes], ...]
    entries: tuple[NativeAgentProfile, ...]
    input_roots: tuple[Path, ...]
    input_states: tuple[tuple[Path, FileState], ...]
    destinations: tuple[tuple[Path, FileState], ...]
    selections: tuple[SurfaceSelection, ...]


def _profile_urn(profile: AgentProfile) -> str:
    """Return the DRG-style URN for ``profile`` (``agent_profile:<id>``)."""
    return f"agent_profile:{profile.profile_id}"


def _manifest_source_path(source_path: Path | None, project_root: Path) -> str | None:
    """Return the manifest-stored SOURCE provenance string for *source_path*.

    Routed through the shared portable-provenance normalizer
    (:func:`charter.provenance.to_portable_source_path`, C-PRV-1/2/6): a
    built-in-pack profile source becomes a
    ``${SPEC_KITTY_PACKS_ROOT}/built-in/...`` token, an in-tree (project/org)
    source becomes repo-relative, anything else stays absolute. This is the
    manifest half of the normalizer's two call sites -- the OUTPUT path
    (``manifest.py``'s ``output_path`` field, via :func:`relativize_under_root`)
    is a distinct, deliberately-excluded carrier and must stay repo-relative
    only (contracts/provenance-and-channel.md C-PRV-6).
    """
    if source_path is None:
        return None
    # ``to_portable_source_path`` is typed ``-> str`` at its ``doctrine.provenance``
    # definition, but the ``charter.provenance`` re-export widens it to ``Any``
    # for mypy; pin the declared type back on a local so ``--strict`` sees the
    # concrete ``str`` return (no suppression).
    portable: str = to_portable_source_path(source_path, project_root=project_root)
    return portable


def _source_hash(source_path: Path | None) -> str | None:
    if source_path is None or not source_path.exists():
        return None
    try:
        return str(hash_source_file(source_path))
    except OSError:
        return None


def default_profile_repository(project_root: Path) -> AgentProfileRepository:
    """Build the standard repository for ``project_root``.

    Built-in profiles always load from package data. Project overlay profiles
    load from ``.kittify/agent_profiles/`` (``_PROJECT_PROFILE_SUBDIR``) when
    that directory exists; the repository treats a missing overlay gracefully
    (no project layer).

    The base repository is now obtained through the sanctioned builder
    ``charter.active_charter_service_builder._build_active_charter_service``
    with ``org_roots=[]`` (C-008: an org-free base — see the call site) and
    ``agent_profile_overlay_dir=project_root / _PROJECT_PROFILE_SUBDIR``
    (the #3176 builder overlay seam, WP02). That seam resolves the inner
    ``charter.offering.service.CharterOfferingService``'s agent-profile project overlay at
    ``.kittify/agent_profiles`` — the path the builder's default
    ``resolve_project_root`` candidates (``.kittify/doctrine`` / ``src/doctrine``
    / ``doctrine``) never reach — so every seeded ``.kittify/agent_profiles/
    *.agent.yaml`` stays visible with ``project`` provenance. ``specify_cli``
    consuming the ``charter`` builder is the correct dependency direction
    (C-001); the param lives in ``charter``/``doctrine``.

    The **charter-activation-admitted** org-pack profiles are then merged on top
    of the project layer (#2166). They are obtained exclusively through WP02's
    :func:`resolve_activated_org_profiles`, which applies the charter activation
    gate, so a *de-activated* org profile never reaches the host surface. A raw
    ``org_dirs=`` splice is intentionally NOT used here: it would bypass the gate
    and surface declared-but-de-activated profiles (C-008).

    This compatibility API returns admission only. Assessments use
    :meth:`ProfileProjector.from_project` to retain source health as well.
    """
    repo, _ = _profile_repository_inputs(project_root)
    return repo


def _profile_repository_inputs(project_root: Path) -> tuple[AgentProfileRepository, tuple[SkippedProfile, ...]]:
    """Load admission and canonical org failures together, without a rescan."""
    # ``org_roots=[]`` is load-bearing for C-008: the base repository must carry
    # NO org layer, because org profiles enter EXCLUSIVELY through the
    # activation-gated ``_merge_activated_org_profiles`` below. The public
    # ``build_active_charter_service`` self-resolves org roots
    # (FR-008), which would pre-populate the base with *unfiltered* org
    # profiles — the very raw-``org_dirs`` splice this function forbids, letting
    # de-activated org profiles leak onto the host surface. The private builder
    # with an explicit empty ``org_roots`` suppresses that self-resolution while
    # still threading the ``agent_profile_overlay_dir`` seam that reaches
    # ``.kittify/agent_profiles`` (#3176).
    repo = _build_active_charter_service(
        project_root,
        org_roots=[],
        agent_profile_overlay_dir=project_root / _PROJECT_PROFILE_SUBDIR,
    ).agent_profile_repository
    skipped = _merge_activated_org_profiles(repo, project_root)
    return repo, skipped


def _merge_activated_org_profiles(
    repo: AgentProfileRepository, repo_root: Path
) -> tuple[SkippedProfile, ...]:
    """Merge WP02's activation-admitted org profiles onto ``repo`` in place.

    Consumes the provenance-preserving :class:`ResolvedOrgProfile` records so the
    projection manifest records each org agent with a non-builtin ``source_layer``
    (``"org"``) and its on-disk ``source_path`` — the #2166 acceptance hinge. The
    project (``.kittify/agent_profiles``) and built-in layers are left untouched;
    with no declared org packs the resolver returns an empty list and projection
    is byte-identical to the pre-mission output (NFR-001).
    """
    resolution = resolve_activated_org_profiles(repo_root)
    skipped: tuple[SkippedProfile, ...] = resolution.skipped_profiles
    for resolved in resolution:
        repo.register_overlay(
            resolved.profile,
            layer=resolved.source_layer,
            source_path=resolved.source_path,
        )
    return skipped


class ProfileProjector:
    """Project agent profiles into native agent files for a tool."""

    def __init__(self, profile_repo: AgentProfileRepository, *, org_load_failures: tuple[SkippedProfile, ...] = ()) -> None:
        self._repo = profile_repo
        self._org_load_failures = org_load_failures

    @classmethod
    def from_project(cls, project_root: Path) -> ProfileProjector:
        """Retain canonical source health independently of admitted profiles."""
        repo, skipped = _profile_repository_inputs(project_root)
        return cls(repo, org_load_failures=skipped)

    def _skipped_profiles(self) -> tuple[SkippedProfile, ...]:
        return (*self._repo.skipped_profiles(), *self._org_load_failures)

    def prepare(self, tool_key: str, project_root: Path) -> tuple[PreparedProjection, ...]:
        """Freeze real admitted projections and their exact renderer bytes for consumers."""
        result = []
        for native in self.project(tool_key, project_root):
            body = self.render(tool_key, native.profile_urn)
            if body is None:
                raise ValueError(f"Unable to render required profile: {native.profile_urn}")
            from .manifest import hash_content

            result.append(PreparedProjection(replace(native, file_hash=hash_content(body)), body.encode("utf-8")))
        return tuple(result)

    def source_paths(self) -> tuple[Path, ...]:
        """Return source identities from the resolved repository, including sentinels."""
        return tuple(sorted({p for profile in self._repo.list_all() if (p := self._repo.get_source_path(profile.profile_id)) is not None}))

    def project(
        self,
        tool_key: str,
        project_root: Path,
        source_layers: list[str] | None = None,
    ) -> list[NativeAgentProfile]:
        """Project available profiles into native format for ``tool_key``.

        ``source_layers`` filters by provenance (``builtin``/``org``/
        ``project``); ``None`` projects every layer. Sentinel profiles (workflow
        routing signals, not agent identities) are never projected. Returns an
        empty list for tools without a native named-agent primitive.
        """
        renderer = get_renderer(tool_key)
        if renderer is None:
            return []
        layer_filter = set(source_layers) if source_layers is not None else None
        return [
            self._project_one(renderer, tool_key, profile, project_root)
            for profile in self._repo.list_all()
            if self._include(profile, layer_filter)
        ]

    def _include(
        self, profile: AgentProfile, layer_filter: set[str] | None
    ) -> bool:
        if profile.sentinel:
            return False
        if layer_filter is None:
            return True
        layer = self._repo.get_provenance(profile.profile_id) or LAYER_BUILTIN
        return layer in layer_filter

    def _project_one(
        self,
        renderer: ProfileRenderer,
        tool_key: str,
        profile: AgentProfile,
        project_root: Path,
    ) -> NativeAgentProfile:
        output_path = renderer.output_path(tool_key, profile, project_root)
        layer = self._repo.get_provenance(profile.profile_id) or LAYER_BUILTIN
        source_path = self._repo.get_source_path(profile.profile_id)
        return NativeAgentProfile(
            profile_urn=_profile_urn(profile),
            source_layer=layer,
            tool_key=tool_key,
            output_path=output_path,
            format=renderer.format_key,
            file_hash=None,
            source_path=_manifest_source_path(source_path, project_root),
            source_hash=_source_hash(source_path),
            projection_version=PROJECTION_VERSION,
        )

    def render(self, tool_key: str, profile_urn: str) -> str | None:
        """Render the native file body for one ``profile_urn`` and ``tool_key``.

        Returns ``None`` when the tool has no renderer or the profile id is not
        loaded. Used by the provider's repair path to obtain file content for a
        single projected surface without re-projecting the whole set.
        """
        renderer = get_renderer(tool_key)
        if renderer is None:
            return None
        profile_id = profile_urn.split(":", 1)[1] if ":" in profile_urn else profile_urn
        profile = self._repo.get(profile_id)
        if profile is None:
            return None
        return str(renderer.render(profile))

    def diagnose(self, tool_key: str, project_root: Path) -> list[SurfaceFinding]:
        """Return findings for profile-projection conditions for ``tool_key``.

        Emits the four #1940 diagnostic codes from their *real* triggering
        conditions (never a dead constant):

        * ``profile-source-invalid`` (error) — every profile the repository
          recorded as a skipped/invalid source.
        * ``profile-overlay-conflict`` (error) — an id that is both loaded in
          one layer and rejected in another (ambiguous/unsafe overlay).
        * ``profile-name-invalid`` (error) — a loaded, non-sentinel profile id
          illegal for the native filename stem.
        * ``profile-sentinel-skipped`` (info) — each sentinel profile, recorded
          rather than silently dropped.

        Tools without a native renderer yield no projection-specific findings
        here (the provider reports their research gap separately).
        """
        # ``project_root`` is accepted for call-site symmetry with ``project``
        # (the provider passes the same arguments); the diagnostics below read
        # only the repository, which already resolved its layers at load time.
        _ = project_root
        if get_renderer(tool_key) is None:
            return []
        findings: list[SurfaceFinding] = []
        findings.extend(self._source_invalid_findings(tool_key))
        findings.extend(self._overlay_conflict_findings(tool_key))
        findings.extend(self._name_invalid_findings(tool_key))
        findings.extend(self._sentinel_findings(tool_key))
        return findings

    def _source_invalid_findings(self, tool_key: str) -> list[SurfaceFinding]:
        out: list[SurfaceFinding] = []
        for skip in self._skipped_profiles():
            label = skip.profile_id or skip.path
            out.append(
                make_finding(
                    PROFILE_SOURCE_INVALID,
                    SEVERITY_ERROR,
                    f"Agent profile source is invalid: {label} ({skip.error_summary})",
                    tool_key=tool_key,
                    surface_id=skip.profile_id,
                    repair_command=_REPAIR_HINT,
                    details={
                        "layer": skip.layer,
                        "path": skip.path,
                        "reason": skip.error_summary,
                    },
                )
            )
        return out

    def _overlay_conflict_findings(self, tool_key: str) -> list[SurfaceFinding]:
        """One finding per id present in both the loaded set and a skipped layer.

        Such an id was successfully loaded from one layer yet rejected when an
        overlay layer tried to redefine it — an ambiguous resolution across
        layers that must not be presented as healthy.
        """
        loaded = {p.profile_id for p in self._repo.list_all()}
        conflicts = sorted(
            {
                skip.profile_id
                for skip in self._skipped_profiles()
                if skip.profile_id and skip.profile_id in loaded
            }
        )
        return [
            make_finding(
                PROFILE_OVERLAY_CONFLICT,
                SEVERITY_ERROR,
                (
                    f"Agent profile {profile_id!r} is defined in multiple layers "
                    "with an incompatible overlay; resolution is ambiguous."
                ),
                tool_key=tool_key,
                surface_id=profile_id,
                repair_command=_REPAIR_HINT,
            )
            for profile_id in conflicts
        ]

    def _name_invalid_findings(self, tool_key: str) -> list[SurfaceFinding]:
        out: list[SurfaceFinding] = []
        for profile in self._repo.list_all():
            if profile.sentinel:
                continue
            reason = native_name_violation(profile.profile_id)
            if reason is None:
                continue
            out.append(
                make_finding(
                    PROFILE_NAME_INVALID,
                    SEVERITY_ERROR,
                    f"Agent profile id {profile.profile_id!r} is invalid: {reason}",
                    tool_key=tool_key,
                    surface_id=profile.profile_id,
                    details={"reason": reason},
                )
            )
        return out

    def _sentinel_findings(self, tool_key: str) -> list[SurfaceFinding]:
        return [
            make_finding(
                PROFILE_SENTINEL_SKIPPED,
                SEVERITY_INFO,
                (
                    f"Sentinel profile {profile.profile_id!r} is a workflow "
                    "routing signal and is intentionally not projected."
                ),
                tool_key=tool_key,
                surface_id=_profile_urn(profile),
            )
            for profile in self._repo.list_all()
            if profile.sentinel
        ]


@dataclass(frozen=True)
class PreparedProjection:
    """Immutable bundle/owner input: original native provenance and exact UTF-8 bytes."""

    native: NativeAgentProfile
    content: bytes
