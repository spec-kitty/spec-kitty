"""
Agent profile repository with two-source loading (built-in + project).

Provides:
- Two-source YAML loading (built-in package data + project filesystem)
- Field-level merge semantics for project overrides
- Query methods (list_all, get, find_by_role)
- Hierarchy traversal (get_children, get_ancestors, get_hierarchy_tree)
- Hierarchy validation (cycle detection, orphaned references)
- Context-based matching with weighted scoring
- Save/delete for project profiles
"""

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.discovery_recursion import overlay_scan_is_recursive
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.loader import DRGLoadError, load_built_in_graph
from charter.offering.drg.models import DRGGraph, NodeKind, Relation
from charter.offering.drg.reachability import agent_profile_seed_urns, profile_channel_reachable
from charter.offering.pack_paths import built_in_dir
from charter.offering.shared.exceptions import InlineReferenceRejectedError
from charter.offering.shared.scoping import applies_to_languages_match, normalize_languages

from .diagnostics import SkippedProfile
from .profile import AgentProfile, Role, TaskContext
from .validation import reject_agent_profile_inline_refs, validate_agent_profile_yaml

_MAX_LOW_WORKLOAD = 2
_MAX_MEDIUM_WORKLOAD = 4
_AGENT_PROFILE_GLOB = "*.agent.yaml"

#: Layer ordinals used to sort skipped-profile diagnostics deterministically
#: (NFR-002). Built-in records come first, then org, then project; within a
#: layer records are ordered by path.
_LAYER_RANK: dict[str, int] = {"builtin": 0, "org": 1, "project": 2}


_URN_SEP = ":"


def _profile_urn(profile_id: str) -> str:
    """Return the DRG node URN for an agent-profile id."""
    return f"{NodeKind.AGENT_PROFILE.value}{_URN_SEP}{profile_id}"


def _profile_id_from_urn(urn: str) -> str:
    """Return the profile id from an ``agent_profile:<id>`` URN."""
    return urn.split(":", 1)[1] if ":" in urn else urn


def _filter_candidates_by_role(candidates: list[AgentProfile], required_role: str | None) -> list[AgentProfile]:
    """Return candidates matching required_role at any role position, or all candidates when role is unset.

    Normalizes required_role to lowercase before comparison since Role instances are stored lowercased.
    """
    if not required_role:
        return candidates
    normalized = str(required_role).lower()
    return [
        p for p in candidates
        if normalized in p.roles or p.profile_id == normalized
    ]


def _language_signal(context: TaskContext, profile: AgentProfile) -> float:
    """Return 1.0 if the context language matches the profile's specialization."""
    if context.language and profile.specialization_context and context.language.lower() in [
        lang.lower() for lang in profile.specialization_context.languages
    ]:
        return 1.0
    return 0.0


def _framework_signal(context: TaskContext, profile: AgentProfile) -> float:
    """Return 1.0 if the context framework matches the profile's specialization."""
    if context.framework and profile.specialization_context and context.framework.lower() in [
        fw.lower() for fw in profile.specialization_context.frameworks
    ]:
        return 1.0
    return 0.0


def _file_pattern_signal(context: TaskContext, profile: AgentProfile) -> float:
    """Return 1.0 if any context file path matches a profile file pattern."""
    if context.file_paths and profile.specialization_context:
        for file_path in context.file_paths:
            for pattern in profile.specialization_context.file_patterns:
                if fnmatch(file_path, pattern):
                    return 1.0
    return 0.0


def _keyword_signal(context: TaskContext, profile: AgentProfile) -> float:
    """Return 1.0 if any context keyword matches a profile domain keyword."""
    if context.keywords and profile.specialization_context:
        profile_kws = [kw.lower() for kw in profile.specialization_context.domain_keywords]
        for keyword in context.keywords:
            if keyword.lower() in profile_kws:
                return 1.0
    return 0.0


def _exact_id_signal(context: TaskContext, profile: AgentProfile) -> float:
    """Score required_role match: 1.0 for profile_id or primary role, 0.5 for secondary role, 0.0 for none."""
    req = context.required_role
    if req is None:
        return 0.0
    if req == profile.profile_id or req == profile.roles[0]:
        return 1.0
    if req in profile.roles[1:]:
        return 0.5
    return 0.0


def _workload_penalty(workload: int) -> float:
    """Return score multiplier based on current workload (DDR-011)."""
    if workload <= _MAX_LOW_WORKLOAD:
        return 1.0
    if workload <= _MAX_MEDIUM_WORKLOAD:
        return 0.85
    return 0.70


def _complexity_adjustment(is_specialist: bool, complexity: str) -> float:
    """Return score multiplier based on specialist/generalist × task complexity."""
    if is_specialist:
        return {"low": 0.9, "medium": 1.0, "high": 1.1}.get(complexity, 1.0)
    return {"low": 1.0, "medium": 1.0, "high": 0.9}.get(complexity, 1.0)


def _score_profile(
    context: TaskContext,
    profile: AgentProfile,
    *,
    is_specialist: bool = False,
) -> float:
    """Compute the full adjusted DDR-011 score for a profile against a task context.

    ``is_specialist`` reflects whether the profile has a lineage parent. Lineage
    is no longer carried on the profile itself (FR-002): it is resolved from the
    DRG ``specializes_from`` edges by the caller and passed in here.
    """
    base_score = (
        _language_signal(context, profile) * 0.40
        + _framework_signal(context, profile) * 0.20
        + _file_pattern_signal(context, profile) * 0.20
        + _keyword_signal(context, profile) * 0.10
        + _exact_id_signal(context, profile) * 0.10
    )
    penalty = _workload_penalty(context.current_workload or 0)
    complexity_adj = _complexity_adjustment(
        is_specialist,
        context.complexity or "medium",
    )
    # When no context signals match (base_score=0), routing_priority becomes dominant.
    return (base_score + profile.routing_priority / 100.0) * penalty * complexity_adj


# ── Profile inheritance helpers ───────────────────────────────────────────────

# List-type profile fields merged by union rather than child-replaces-parent.
_LIST_FIELDS: frozenset[str] = frozenset({
    "capabilities", "directive-references", "canonical-verbs", "mode-defaults",
    "tactic-references",
})


def _item_key(item: Any) -> str:
    """Extract a stable identity key for deduplication and exclusion matching.

    For DirectiveRef dicts, uses the 'code' field. For artifact refs, uses
    the 'id' field.
    For other dicts, falls back to full string repr.
    For plain values, uses str().
    """
    if isinstance(item, dict) and "code" in item:
        return str(item["code"])
    if isinstance(item, dict) and "id" in item:
        return str(item["id"])
    return str(item)


def _union_merge(parent_data: dict[str, Any], child_data: dict[str, Any]) -> dict[str, Any]:
    """Merge two profile data dicts with union semantics for list-type fields."""
    merged = parent_data.copy()
    for key, child_value in child_data.items():
        parent_value = merged.get(key)
        if key in _LIST_FIELDS and isinstance(parent_value, list) and isinstance(child_value, list):
            seen = {_item_key(item) for item in parent_value}
            merged[key] = parent_value + [item for item in child_value if _item_key(item) not in seen]
        elif isinstance(parent_value, dict) and isinstance(child_value, dict):
            nested = parent_value.copy()
            nested.update(child_value)
            merged[key] = nested
        else:
            merged[key] = child_value
    return merged


def _apply_excluding(
    merged: dict[str, Any],
    excluding: list[str] | dict[str, list[str]],
) -> dict[str, Any]:
    """Apply excluding declarations to the merged profile data dict."""
    if isinstance(excluding, list):
        for field_name in excluding:
            merged.pop(field_name, None)
    else:
        for field_name, values_to_remove in excluding.items():
            if field_name in merged and isinstance(merged[field_name], list):
                remove_set = {str(v) for v in values_to_remove}
                merged[field_name] = [
                    item for item in merged[field_name] if _item_key(item) not in remove_set
                ]
    return merged


class AgentProfileRepository:
    """Repository for loading and managing agent profiles from YAML files."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
        active_languages: list[str] | tuple[str, ...] | None = None,
        drg: DRGGraph | None = None,
    ):
        """Initialize repository with built-in, org, and/or project directories.

        Args:
            built_in_dir: Directory containing built-in profiles (defaults to package data)
            org_dirs: Ordered list of org-level profile directories. Each pack
                overlays the previous in declaration order; later packs override
                earlier ones for the same profile-id (FR-006, C-004).
            project_dir: Directory containing project-specific profiles (optional)
            active_languages: Language filter; None means no filtering
            drg: Doctrine Relationship Graph used to resolve profile lineage
                (``specializes_from`` edges). When ``None``, the shipped built-in
                graph (the ``packs/built-in/*.graph.yaml`` fragments) is loaded.
                Lineage is read
                exclusively from this graph; the retired ``specializes-from``
                profile field is no longer consulted (FR-002, C-009).
        """
        self._profiles: dict[str, AgentProfile] = {}
        self._provenance: dict[str, str] = {}
        self._source_paths: dict[str, Path] = {}
        self._skipped: list[SkippedProfile] = []
        self._scope_filtered_ids: set[str] = set()
        self._built_in_dir = built_in_dir or self._default_built_in_dir()
        self._org_dirs: list[Path] = list(org_dirs) if org_dirs else []
        self._project_dir = project_dir
        self._active_languages = None if active_languages is None else normalize_languages(active_languages)
        self._drg: DRGGraph = drg if drg is not None else self._default_drg()
        self._hierarchy_index: dict[str, list[str]] | None = None
        self._load()

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Return the shipped built-in profiles directory (``packs/built-in/agent_profiles/``)."""
        return built_in_dir(ArtifactKind.AGENT_PROFILE)

    @classmethod
    def _default_drg(cls) -> DRGGraph:
        """Load the shipped DRG graph used to resolve lineage.

        Routes through the canonical :func:`load_built_in_graph` seam (WP03,
        mission #2680) so the built-in graph is read in exactly one place. The
        seam resolves the ``packs/built-in/`` pack root and merges its per-kind
        ``*.graph.yaml`` fragments, so this method needed no edit when the
        monolith was sharded or when the fragments moved to the pack root.

        If the shipped graph cannot be loaded, lineage resolution degrades to an
        empty graph (no parents) rather than crashing the whole repository load.
        """
        try:
            return load_built_in_graph()
        except DRGLoadError:
            return DRGGraph(
                schema_version="1.0",
                generated_at="1970-01-01T00:00:00Z",
                generated_by="agent_profiles.repository:_default_drg",
                nodes=[],
                edges=[],
            )

    def _record_skip(
        self,
        *,
        layer: str,
        path: Path | str,
        profile_id: str | None,
        error_summary: str,
    ) -> None:
        """Record a skipped profile file for later diagnostic inspection."""
        self._skipped.append(
            SkippedProfile(
                layer=layer,
                path=str(path),
                profile_id=profile_id,
                error_summary=error_summary,
            )
        )

    def skipped_profiles(self) -> list[SkippedProfile]:
        """Return a deterministically-sorted copy of skipped-profile diagnostics.

        Records are sorted by ``(layer_rank, path)`` so two loads of the same
        inputs produce identical ordering (NFR-002). For valid built-in inputs
        this list is empty (NFR-005). ``list_all()`` is unaffected and remains
        valid-only (FR-006).
        """
        return sorted(
            self._skipped,
            key=lambda s: (_LAYER_RANK.get(s.layer, len(_LAYER_RANK)), s.path),
        )

    @property
    def scope_filtered_ids(self) -> frozenset[str]:
        """IDs of profiles excluded by the active language scope filter.

        A profile appears here when its YAML exists on disk and passed
        schema validation, but its ``applies_to_languages`` field did
        not overlap with the active language set configured at
        construction time. Parity with
        :class:`charter.offering.base.BaseDoctrineRepository`'s property
        of the same name (FR-013): the catalog-miss diagnosis
        (:func:`charter.activation.context_renderers.catalog_diagnosis._diagnose_catalog_miss`)
        reads this set so a present-but-scoped profile surfaces
        ``SCOPE_FILTERED`` rather than ``MISSING_ARTIFACT`` (#4572).
        The set is populated during :meth:`_load` and is read-only
        after that; an id that a later layer successfully re-admits
        is removed.
        """
        return frozenset(self._scope_filtered_ids)

    def _load(self) -> None:
        """Load profiles from built-in, org, and project layers.

        All three layers share a single per-layer loader (:meth:`_load_layer`).
        Built-in profiles are loaded first (root layer), then each org pack in
        declaration order, then the project layer; later layers override
        earlier ones for the same profile-id (FR-006, C-004). Files that cannot
        be loaded are recorded via :meth:`_record_skip` rather than dropped
        silently (FR-005/006/007).
        """
        yaml = YAML(typ="safe")

        # Built-in layer is the merge base. Its successfully-loaded profiles are
        # the override targets for org/project layers.
        built_in_profiles = self._load_layer(
            yaml,
            directory=self._built_in_dir,
            layer="builtin",
            built_in_profiles={},
            recursive=True,
        )

        # Org packs, then project, overlay onto the same store in order. Org and
        # project overlay discovery is recursive via the single doctrine
        # recursion authority (unconditional per C-001), matching the built-in
        # layer above so a nested `agent_profiles/<sub>/x.agent.yaml` is not
        # silently dropped (#3490). This was the third, separate recursion
        # divergence site (org/project were `recursive=False` while built-in was
        # `True`); it now reads the same authority the base loader and the
        # charter resolver consult.
        overlay_recursive = overlay_scan_is_recursive(ArtifactKind.AGENT_PROFILE)
        for org_dir in self._org_dirs:
            self._load_layer(
                yaml,
                directory=org_dir,
                layer="org",
                built_in_profiles=built_in_profiles,
                recursive=overlay_recursive,
            )

        if self._project_dir is not None:
            self._load_layer(
                yaml,
                directory=self._project_dir,
                layer="project",
                built_in_profiles=built_in_profiles,
                recursive=overlay_recursive,
            )

    def _load_layer(
        self,
        yaml: YAML,
        *,
        directory: Path,
        layer: str,
        built_in_profiles: dict[str, AgentProfile],
        recursive: bool,
    ) -> dict[str, AgentProfile]:
        """Load every profile file from one layer directory into ``self._profiles``.

        This is the single shared loader for the built-in, org, and project
        layers (R-011-B: collapse the three duplicated loops). Scans are sorted
        so record/override order is deterministic (NFR-002). Each unloadable
        file is recorded with :meth:`_record_skip`; valid files are stored and
        tagged with ``layer`` provenance.

        For the built-in layer, the loaded profiles double as the override
        targets returned to the caller. For org/project layers, a profile-id
        already present in ``built_in_profiles`` is field-merged onto the
        built-in base; otherwise it is added as a new profile. Collisions with
        an already-loaded profile emit a layer-collision warning.

        Returns the mapping of profile-id -> profile loaded from this layer
        (used by the caller to seed ``built_in_profiles``).
        """
        loaded: dict[str, AgentProfile] = {}
        if not directory.exists():
            return loaded

        scan = directory.rglob(_AGENT_PROFILE_GLOB) if recursive else directory.glob(_AGENT_PROFILE_GLOB)
        for yaml_file in sorted(scan):
            profile = self._parse_profile_from_file(
                yaml, yaml_file, layer=layer, built_in_profiles=built_in_profiles
            )
            if profile is None:
                continue

            self._profiles[profile.profile_id] = profile
            self._provenance[profile.profile_id] = layer
            self._source_paths[profile.profile_id] = yaml_file
            loaded[profile.profile_id] = profile
            # A successful load re-admits the id even if an earlier
            # layer's copy was scope-filtered (an org/project overlay
            # can widen or drop the applies_to_languages scope) — the
            # record must never outlive the drop it describes (#4572).
            self._scope_filtered_ids.discard(profile.profile_id)

        return loaded

    def _parse_profile_from_file(
        self,
        yaml: YAML,
        yaml_file: Path,
        *,
        layer: str,
        built_in_profiles: dict[str, AgentProfile],
    ) -> AgentProfile | None:
        """Parse, validate, and (for org/project) merge one profile YAML file.

        Extracted from :meth:`_load_layer` (R-011-B) to keep its cognitive
        complexity within the ruff C901 limit (15); the per-file gate chain
        now starts at nesting level 0. Every failure path records a skip via
        :meth:`_record_skip` and returns ``None`` in place of the original
        loop's ``continue``. On success this also fires the layer-collision
        diagnostic for org/project profiles — the caller is responsible only
        for the final ``self._profiles``/``self._provenance``/
        ``self._source_paths`` writes and ``loaded`` bookkeeping.
        """
        try:
            data = yaml.load(yaml_file)
        except (YAMLError, OSError) as exc:
            self._record_skip(
                layer=layer,
                path=yaml_file,
                profile_id=None,
                error_summary=f"YAML/read error: {exc}",
            )
            return None

        if data is None:
            self._record_skip(
                layer=layer,
                path=yaml_file,
                profile_id=None,
                error_summary="Empty profile file (no YAML document)",
            )
            return None

        profile_id = data.get("profile-id") or data.get("profile_id") if isinstance(data, dict) else None

        # Inline-reference rejection is a *surfaced skip*, consistent with the
        # ``diagnostics.py`` docstring (FR-003 / I-9). Loading is eager and
        # all-or-nothing: a propagated raise would abort the whole layer load
        # and blank out valid sibling profiles (the #1584 false-healthy
        # class). We catch it here — where the YAML is in hand, so we can
        # populate ``profile_id`` (the exception lacks it, DD-2) and a clear,
        # readable ``error_summary`` (forbidden field + migration hint) — and
        # record it via ``_record_skip``. Valid siblings keep loading.
        try:
            reject_agent_profile_inline_refs(data, file_path=str(yaml_file))
        except InlineReferenceRejectedError as exc:
            self._record_skip(
                layer=layer,
                path=yaml_file,
                profile_id=profile_id,
                error_summary=(
                    f"Forbidden inline-reference field '{exc.forbidden_field}'. "
                    f"{exc.migration_hint}"
                ),
            )
            return None

        if not profile_id:
            schema_errors = (
                validate_agent_profile_yaml(data) if isinstance(data, dict) else []
            )
            summary = (
                "; ".join(schema_errors)
                if schema_errors
                else "Missing required 'profile-id'"
            )
            self._record_skip(
                layer=layer,
                path=yaml_file,
                profile_id=None,
                error_summary=summary,
            )
            return None

        try:
            if layer != "builtin" and profile_id in built_in_profiles:
                profile = self._merge_profiles(built_in_profiles[profile_id], data)
            else:
                profile = AgentProfile.model_validate(data)
        except ValidationError as exc:
            schema_errors = (
                validate_agent_profile_yaml(data) if isinstance(data, dict) else []
            )
            summary = "; ".join(schema_errors) if schema_errors else str(exc)
            self._record_skip(
                layer=layer,
                path=yaml_file,
                profile_id=profile_id,
                error_summary=summary,
            )
            return None

        if not applies_to_languages_match(profile.applies_to_languages, self._active_languages):
            # #4572: record the drop instead of vanishing silently.
            # Without this record the catalog-miss diagnosis could not
            # distinguish a present-but-language-scoped profile from
            # one that never existed, so a charter-selected profile
            # that ``agent profile list`` reports available was
            # diagnosed ``MISSING_ARTIFACT``. Parity with
            # ``BaseDoctrineRepository.scope_filtered_ids`` (FR-013).
            self._scope_filtered_ids.add(profile_id)
            return None

        if layer != "builtin":
            self._record_profile_collision_if_present(
                profile_id=profile.profile_id,
                higher_layer=layer,
                higher_data=data,
            )

        return profile

    def _record_profile_collision_if_present(
        self,
        *,
        profile_id: str,
        higher_layer: str,
        higher_data: dict[str, Any],
    ) -> None:
        """Emit a DoctrineLayerCollisionWarning iff ``profile_id`` is already loaded.

        Called at write time so the lower-layer dump is still available for
        field-count accounting (FR-003 wording per ADR 2026-05-16-1).
        """
        from charter.offering.base import _emit_collision_warning

        if profile_id not in self._profiles:
            return
        existing = self._profiles[profile_id]
        lower_layer = self._provenance.get(profile_id, "unknown")
        _emit_collision_warning(
            kind="agent_profile",
            item_id=profile_id,
            higher_layer=higher_layer,
            lower_layer=lower_layer,
            higher_data=higher_data,
            lower_dump=existing.model_dump(),
        )

    def _merge_profiles(self, built_in: AgentProfile, project_data: dict[str, Any]) -> AgentProfile:
        """Merge project data into built-in profile at field level.

        Uses exclude_unset=True to detect explicitly set fields in project data.

        Args:
            built_in: Built-in profile to use as base
            project_data: Project profile data (dict from YAML)

        Returns:
            Merged profile with project fields overriding built-in fields
        """
        # Get built-in profile as dict (with by_alias to use kebab-case)
        built_in_dict = built_in.model_dump(by_alias=True)

        # Normalize project data keys to match YAML format (kebab-case)
        def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
            """Recursively merge dictionaries at field level."""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    # Recursively merge nested dicts
                    result[key] = deep_merge(result[key], value)
                else:
                    # Override with project value
                    result[key] = value
            return result

        merged_dict = deep_merge(built_in_dict, project_data)

        return AgentProfile.model_validate(merged_dict)

    def list_all(self) -> list[AgentProfile]:
        """Return all loaded profiles sorted by profile_id."""
        return sorted(self._profiles.values(), key=lambda p: p.profile_id)

    def get(self, profile_id: str) -> AgentProfile | None:
        """Get profile by ID or None if not found."""
        return self._profiles.get(profile_id)

    def get_provenance(self, profile_id: str) -> str | None:
        """Return the source layer for the given profile ID.

        Returns one of ``"builtin"``, ``"org"``, or ``"project"``, or
        ``None`` if the profile is not loaded.
        """
        return self._provenance.get(profile_id)

    def get_source_path(self, profile_id: str) -> Path | None:
        """Return the YAML file path that supplied the loaded profile."""
        return self._source_paths.get(profile_id)

    def register_overlay(
        self,
        profile: AgentProfile,
        *,
        layer: str,
        source_path: Path | None,
    ) -> None:
        """Overlay an externally-resolved ``profile`` onto this repository.

        Public entry point so callers (e.g. the charter-activation-admitted org
        subset) merge a profile without reaching into the private
        ``_profiles``/``_provenance``/``_source_paths`` maps. The overlay is
        applied only when ``layer`` ranks at or above the id's current
        provenance per ``_LAYER_RANK``: an ``org`` overlay replaces a
        ``builtin`` entry, but never clobbers a higher-ranked ``project`` entry.
        A previously-unseen id is always admitted. ``source_path`` is recorded
        only when provided (``None`` leaves any existing path untouched).
        """
        profile_id = profile.profile_id
        existing_layer = self._provenance.get(profile_id)
        if existing_layer is not None and _LAYER_RANK.get(layer, -1) < _LAYER_RANK.get(
            existing_layer, -1
        ):
            return
        self._profiles[profile_id] = profile
        self._provenance[profile_id] = layer
        if source_path is not None:
            self._source_paths[profile_id] = source_path

    def find_by_role(self, role: Role | str) -> list[AgentProfile]:
        """Find all profiles that list the given role (primary or secondary position).

        Args:
            role: Role or string to match against each profile's full roles list

        Returns:
            List of all profiles where role appears at any position in profile.roles
        """
        role_value = str(role)
        if not role_value:
            return []
        normalized_role = Role(role_value)
        return [p for p in self._profiles.values() if normalized_role in p.roles]

    def _lineage_parent(self, profile_id: str) -> str | None:
        """Return the lineage parent of ``profile_id`` via the DRG, or ``None``.

        Lineage is authored as ``specializes_from`` edges in the DRG
        (``agent_profile:<child> --specializes_from--> agent_profile:<parent>``)
        and is the single source of truth (FR-002, C-009). The retired
        ``specializes-from`` profile field is no longer consulted.

        A profile may declare at most one lineage parent; if several edges are
        present the first by sorted target id is returned for determinism.
        """
        edges = self._drg.edges_from(_profile_urn(profile_id), Relation.SPECIALIZES_FROM)
        if not edges:
            return None
        parents = sorted(_profile_id_from_urn(e.target) for e in edges)
        return parents[0]

    def _build_hierarchy_index(self) -> None:
        """Build hierarchy index mapping parent_id -> [child_ids] from the DRG."""
        if self._hierarchy_index is not None:
            return

        index: dict[str, list[str]] = {}

        for profile_id in self._profiles:
            parent_id = self._lineage_parent(profile_id)
            if parent_id:
                index.setdefault(parent_id, []).append(profile_id)

        self._hierarchy_index = index

    def get_children(self, profile_id: str) -> list[AgentProfile]:
        """Get direct children of a profile.

        Args:
            profile_id: Parent profile ID

        Returns:
            List of profiles that specialize from this profile
        """
        self._build_hierarchy_index()

        if self._hierarchy_index is None:
            return []

        child_ids = self._hierarchy_index.get(profile_id, [])
        return [self._profiles[cid] for cid in child_ids if cid in self._profiles]

    def get_ancestors(self, profile_id: str) -> list[str]:
        """Get ancestor chain from profile to root.

        Args:
            profile_id: Starting profile ID

        Returns:
            Ordered list of ancestor profile IDs (immediate parent first)
        """
        ancestors: list[str] = []
        current_id = profile_id
        visited: set[str] = {profile_id}

        while True:
            parent_id = self._lineage_parent(current_id)
            if not parent_id:
                break
            if parent_id in visited:
                # Cycle detected - stop
                break

            ancestors.append(parent_id)
            visited.add(parent_id)
            current_id = parent_id

        return ancestors

    def get_hierarchy_tree(self) -> dict[str, Any]:
        """Get hierarchy as nested dict suitable for Rich Tree rendering.

        Returns:
            Nested dict: {root_id: {"children": {child_id: {...}}}}
        """
        self._build_hierarchy_index()

        # Find roots (profiles with no lineage parent in the DRG)
        roots = [
            profile_id
            for profile_id in self._profiles
            if not self._lineage_parent(profile_id)
        ]

        def build_subtree(profile_id: str) -> dict[str, Any]:
            """Recursively build subtree for a profile."""
            children_dict = {}
            for child in self.get_children(profile_id):
                children_dict[child.profile_id] = build_subtree(child.profile_id)
            return {"children": children_dict}

        tree = {}
        for root_id in roots:
            tree[root_id] = build_subtree(root_id)

        return tree

    def validate_hierarchy(self) -> list[str]:
        """Validate hierarchy for cycles, orphans, duplicates.

        Returns:
            List of error/warning messages (empty if valid)
        """
        errors = []

        # Check for cycles using DFS
        visited: set[str] = set()
        in_stack: set[str] = set()

        def has_cycle(profile_id: str) -> bool:
            """DFS to detect cycles via DRG lineage edges."""
            if profile_id in in_stack:
                return True
            if profile_id in visited:
                return False

            visited.add(profile_id)
            in_stack.add(profile_id)

            parent_id = self._lineage_parent(profile_id)
            if parent_id and has_cycle(parent_id):
                return True

            in_stack.remove(profile_id)
            return False

        for profile_id in self._profiles:
            if profile_id not in visited and has_cycle(profile_id):
                errors.append(f"Cycle detected in hierarchy involving {profile_id}")

        # Check for orphaned references (lineage parent not loaded as a profile)
        for profile_id in self._profiles:
            parent_id = self._lineage_parent(profile_id)
            if parent_id and parent_id not in self._profiles:
                errors.append(
                    f"Orphaned reference: {profile_id} specializes from "
                    f"nonexistent {parent_id}"
                )

        return errors

    def find_best_match(self, context: TaskContext) -> AgentProfile | None:
        """Find best matching profile for given task context using weighted scoring.

        Scoring algorithm (DDR-011):
            score = language_match × 0.40
                  + framework_match × 0.20
                  + file_pattern_match × 0.20
                  + keyword_match × 0.10
                  + exact_id_match × 0.10

        Adjustments:
            - workload_penalty: 0-2=1.0, 3-4=0.85, 5+=0.70
            - complexity_adjustment: specialist/generalist × complexity
            - routing_priority / 100

        Args:
            context: Task context with language, framework, file_paths, etc.

        Returns:
            Profile with highest adjusted score, or None if no profiles
        """
        if not self._profiles:
            return None

        candidates = [self.resolve_profile(profile_id) for profile_id in self._profiles]
        candidates = _filter_candidates_by_role(candidates, context.required_role)

        if not candidates:
            return None

        # A profile is a "specialist" when it has a lineage parent in the DRG.
        return max(
            candidates,
            key=lambda p: _score_profile(
                context,
                p,
                is_specialist=self._lineage_parent(p.profile_id) is not None,
            ),
        )

    def resolve_profile(self, profile_id: str) -> AgentProfile:
        """Resolve a profile with inherited fields from its ancestor chain.

        Merge semantics are intentionally shallow within sections:
        - scalar/list fields: child replaces parent
        - dict section fields: child keys override one level deep,
          parent keys not present in child are preserved
        """
        profile = self.get(profile_id)
        if profile is None:
            raise KeyError(f"Profile '{profile_id}' not found")

        chain: list[AgentProfile] = [profile]
        visited: set[str] = {profile.profile_id}
        current_id = profile.profile_id

        while True:
            parent_id = self._lineage_parent(current_id)
            if not parent_id:
                break
            if parent_id in visited:
                raise ValueError(f"Cycle detected while resolving profile '{profile_id}'")

            parent = self.get(parent_id)
            if parent is None:
                raise KeyError(
                    f"Profile '{profile_id}' references missing parent '{parent_id}'. "
                    "Ensure the parent profile exists in built-in/ or _proposed/ before resolving."
                )

            visited.add(parent.profile_id)
            chain.append(parent)
            current_id = parent.profile_id

        # Build from root -> ... -> child using union merge for list-type fields.
        merged: dict[str, Any] = {}
        for node in reversed(chain):
            node_data = node.model_dump(by_alias=True, exclude_unset=True)
            merged = _union_merge(merged, node_data)

        # Apply excluding from the resolving (child/leaf) profile.
        # Exclusion is applied to the final merged result, not per-ancestor.
        if profile.excluding is not None:
            merged = _apply_excluding(merged, profile.excluding)

        return AgentProfile.model_validate(merged)

    @property
    def drg(self) -> DRGGraph:
        """The DRG graph this repository resolves profile lineage against.

        Exposed read-only so the charter render layer can project the profile
        channel's ``suggests`` deliveries (``when`` clauses live on graph edges,
        surfaced by ``charter.activation.progressive_disclosure.profile_channel_references``)
        against the *same* graph this repository walked — the doctrine layer holds
        the graph but must not import the charter projection (layer direction:
        charter → doctrine).
        """
        return self._drg

    def profile_channel_reached(self, profile_id: str) -> frozenset[str]:
        """Every artefact URN a loaded *profile* reaches through the profile channel.

        The profile channel is :func:`profile_channel_reachable` — a
        ``walk_edges({requires, specializes_from, suggests})`` transitive closure
        seeded from the profile URN (WP01/FR-001 widened it to follow
        ``suggests``). It is deliberately **not** ``resolve_context``:
        ``agent_profile`` nodes carry zero outbound ``scope`` edges, so a
        ``resolve_context`` seed would measure zero at any depth (R-3).

        **Fail-closed on the seed's *identity*, not merely its edges:** the seed
        must be a real ``agent_profile`` node in the graph
        (:func:`agent_profile_seed_urns`). A URN that is absent, or that names a
        node of another kind (e.g. a mistaken ``directive:…`` handle), reaches
        nothing here rather than walking that node's own outbound edges — a
        stronger guarantee than "an unknown URN happens to have no edges".

        Returns the raw reached artefact URNs (profile seeds stripped by the
        walk); the render layer applies its NodeKind delivery table (C4).
        """
        seed = _profile_urn(profile_id)
        if seed not in agent_profile_seed_urns(self._drg):
            return frozenset()
        return profile_channel_reachable(self._drg, {seed})

    def profile_channel_procedure_ids(self, profile_id: str) -> list[str]:
        """Procedure ids a loaded *profile* delivers through the profile channel.

        A procedures-only filter over :meth:`profile_channel_reached` (the shared
        profile-channel walk). This is the mechanism that carries the PR #3007
        exemplar ``procedure:onboard-external-agent-to-pack`` — reached from
        ``agent_profile:doctrine-daphne`` by a ``requires`` edge — to the agent.

        The channel is fail-closed: an unknown ``profile_id`` reaches nothing
        rather than falling open to the whole graph.

        Returns the reached procedure ids (URN prefix stripped), sorted for
        deterministic render order.
        """
        prefix = f"{NodeKind.PROCEDURE.value}{_URN_SEP}"
        reached = self.profile_channel_reached(profile_id)
        return sorted(urn[len(prefix):] for urn in reached if urn.startswith(prefix))

    def save(self, profile: AgentProfile) -> None:
        """Save profile to project directory.

        Args:
            profile: Profile to save

        Raises:
            ValueError: If project_dir is not configured
        """
        if self._project_dir is None:
            raise ValueError("Cannot save profile: project_dir not configured")

        # Ensure project_dir exists
        self._project_dir.mkdir(parents=True, exist_ok=True)

        # Write YAML file
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / f"{profile.profile_id}.agent.yaml"

        # Convert profile to dict, excluding unset fields to keep YAML clean
        profile_dict = profile.model_dump(mode='json', by_alias=True, exclude_unset=True)

        with yaml_file.open("w") as f:
            yaml.dump(profile_dict, f)

        # Update in-memory profiles
        self._profiles[profile.profile_id] = profile
        # A saved profile is loaded regardless of scope state — clear any
        # stale scope-filtered record for it (#4572).
        self._scope_filtered_ids.discard(profile.profile_id)

        # Invalidate hierarchy index
        self._hierarchy_index = None

    def delete(self, profile_id: str) -> bool:
        """Delete profile from project directory.

        Only deletes from project_dir (cannot delete built-in profiles).
        If profile exists in built-in, reverts to built-in version.

        Args:
            profile_id: Profile ID to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If project_dir is not configured
        """
        if self._project_dir is None:
            raise ValueError("Cannot delete profile: project_dir not configured")

        yaml_file = self._project_dir / f"{profile_id}.agent.yaml"

        if not yaml_file.exists():
            return False

        # Remove file
        yaml_file.unlink()

        # Check if profile exists in built-in
        built_in_profile = None
        if self._built_in_dir.exists():
            built_in_yaml = self._built_in_dir / f"{profile_id}.agent.yaml"
            if built_in_yaml.exists():
                try:
                    yaml = YAML(typ="safe")
                    data = yaml.load(built_in_yaml)
                    built_in_profile = AgentProfile.model_validate(data)
                except (YAMLError, ValidationError, TypeError) as exc:
                    # Record rather than silently swallow the failed revert so the
                    # skipped built-in remains observable (FR-005/006/007).
                    self._record_skip(
                        layer="builtin",
                        path=built_in_yaml,
                        profile_id=profile_id,
                        error_summary=f"Failed to revert to built-in during delete(): {exc}",
                    )

        if built_in_profile:
            # Revert to built-in version
            self._profiles[profile_id] = built_in_profile
            self._scope_filtered_ids.discard(profile_id)
        else:
            # Remove from profiles (was project-only)
            self._profiles.pop(profile_id, None)

        # Invalidate hierarchy index
        self._hierarchy_index = None

        return True
