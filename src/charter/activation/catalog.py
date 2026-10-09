"""Offering catalog loading for deterministic governance validation."""

from __future__ import annotations

import importlib.resources
import logging
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.shared.scoping import applies_to_languages_match, normalize_languages
from charter.offering.yaml_utils import parse_shipped_yaml
from kernel.paths import get_package_asset_root as _get_package_asset_root

__all__ = [
    "OfferingCatalog",
    "load_offering_catalog",
    "resolve_offering_root",
]


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OfferingCatalog:
    """Deterministic offering catalog derived from the on-disk built-in artifacts.

    ``domains_present`` records which built-in artifact domains have a ``built-in/``
    subdirectory on disk.  A domain that is present but has an empty ``built-in/``
    directory contributes an *empty* frozenset to the corresponding field — which
    means every selection against that domain is invalid.  A domain that is
    completely absent (directory does not exist) is *not* included in
    ``domains_present``, and the resolver should skip validation for it.
    """

    paradigms: frozenset[str]
    directives: frozenset[str]
    template_sets: frozenset[str]
    tactics: frozenset[str]
    styleguides: frozenset[str]
    toolguides: frozenset[str]
    procedures: frozenset[str]
    agent_profiles: frozenset[str]
    domains_present: frozenset[str] = frozenset()

def load_offering_catalog(
    *,
    include_proposed: bool = False,
    active_languages: list[str] | tuple[str, ...] | None = None,
) -> OfferingCatalog:
    """Load the offering catalog from package assets with development fallbacks.

    Only canonised ``packs/built-in/<kind>/`` artifacts participate in the
    catalog. ``include_proposed`` is accepted for call-site compatibility but
    has no effect: no shipped built-in content dir carries a nested
    ``_proposed/`` subdirectory to opt into post-relocation (mission
    doctrine-built-in-seam-consolidation-01KYW3TX, WP02).

    ``OfferingCatalog.domains_present`` records which artifact domains have a
    ``packs/built-in/<kind>/`` directory on disk.  The resolver uses this to
    distinguish between "domain not deployed in this install" (safe to skip
    validation) and "domain present but built-in set is empty" (every
    selection is invalid).
    """
    offering_root = resolve_offering_root()
    # Built-in artifact content was flattened out of ``src/charter/offering/<kind>/built-in``
    # into ``packs/built-in/<kind>`` (relocation mission); resolve it through the
    # shared ``built_in_dir`` seam per-kind (mission
    # doctrine-built-in-seam-consolidation-01KYW3TX, WP02) rather than a local
    # variable joined by hand. ``offering_root`` is still passed for template sets
    # (resolved through ``MissionTemplateRepository``). Fail-closed: a missing pack root raises
    # rather than silently yielding empty catalogs (the BLOCKER guard).
    normalized_languages = None if active_languages is None else normalize_languages(active_languages)

    domains_present: set[str] = set()

    paradigms, paradigms_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.PARADIGM),
        "**/*.paradigm.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if paradigms_present:
        domains_present.add("paradigms")

    directives, directives_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.DIRECTIVE),
        "**/*.directive.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if directives_present:
        domains_present.add("directives")

    template_sets, template_sets_present = _load_template_sets_with_presence(offering_root)
    if template_sets_present:
        domains_present.add("template_sets")

    tactics, tactics_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.TACTIC),
        "**/*.tactic.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if tactics_present:
        domains_present.add("tactics")

    styleguides, styleguides_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.STYLEGUIDE),
        "**/*.styleguide.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if styleguides_present:
        domains_present.add("styleguides")

    toolguides, toolguides_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.TOOLGUIDE),
        "**/*.toolguide.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if toolguides_present:
        domains_present.add("toolguides")

    procedures, procedures_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.PROCEDURE),
        "**/*.procedure.yaml",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if procedures_present:
        domains_present.add("procedures")

    profiles, profiles_present = _load_yaml_id_catalog_with_presence(
        built_in_dir(ArtifactKind.AGENT_PROFILE),
        "**/*.agent.yaml",
        id_field="profile-id",
        include_proposed=include_proposed,
        active_languages=normalized_languages,
    )
    if profiles_present:
        domains_present.add("agent_profiles")

    return OfferingCatalog(
        paradigms=frozenset(sorted(paradigms)),
        directives=frozenset(sorted(directives)),
        template_sets=frozenset(sorted(template_sets)),
        tactics=frozenset(sorted(tactics)),
        styleguides=frozenset(sorted(styleguides)),
        toolguides=frozenset(sorted(toolguides)),
        procedures=frozenset(sorted(procedures)),
        agent_profiles=frozenset(sorted(profiles)),
        domains_present=frozenset(sorted(domains_present)),
    )


def resolve_offering_root() -> Path:
    """Resolve the ``charter.offering`` package root in installed and development layouts."""
    try:
        offering_pkg = importlib.resources.files("charter.offering")
        offering_root = Path(str(offering_pkg))
        if offering_root.is_dir():
            return offering_root
    except (ModuleNotFoundError, TypeError):
        _log.debug("offering: importlib.resources lookup failed, trying dev layout")

    # ``catalog.py`` lives one level deeper than before (moved into
    # ``charter/activation/`` by mission charter-activation-split-01M16ZSE,
    # MAP-A MOVE), hence the extra ``.parent``.
    dev_root = Path(__file__).parent.parent / "offering"
    if dev_root.is_dir():
        _log.debug("offering: resolved via dev layout at %s", dev_root)
        return dev_root

    # 3. Installed layout: the offering is not a separate package on PyPI.
    #    Fall back to the parent of the resolved missions root so that callers
    #    can still discover missions/ (via get_package_asset_root) and receive
    #    empty sets for paradigms/directives which don't ship in the wheel.
    #    Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H
    #    (FR-005/R-08) relocated the missions data (and, per a prior mission,
    #    every other built-in artifact kind) to packs/built-in/ -- so
    #    _get_package_asset_root() now resolves packs/built-in/missions, and
    #    this fallback's ``.parent`` correctly yields packs/built-in, the ONE
    #    root that actually still carries paradigms/directives/missions
    #    together (an improvement over the pre-relocation src/doctrine
    #    fallback, which no longer carries any of them). R-01 (kernel.paths)
    #    and this fallback must be read together: repointing one without the
    #    other would silently reintroduce a wrong root here.
    try:
        result = _get_package_asset_root().parent
        _log.debug("offering: resolved via package asset root fallback")
        return result
    except FileNotFoundError:
        pass

    raise FileNotFoundError("Cannot locate the charter.offering root. Ensure the built-in artifacts are packaged.")


def _load_yaml_id_catalog(
    directory: Path,
    pattern: str,
    *,
    id_field: str = "id",
    include_proposed: bool = False,
    active_languages: list[str] | tuple[str, ...] | None = None,
) -> set[str]:
    """Load ID values from charter.offering YAML files in a directory.

    Args:
        directory: Artifact root directory to search.
        pattern: Glob pattern (supports ``**`` for recursive search).
        id_field: YAML key containing the artifact ID. Defaults to ``"id"``.
                  Use ``"profile-id"`` for agent profile files.
        include_proposed: accepted for call-site compatibility; has no effect
                  post-relocation (see :func:`_resolve_scan_roots`).
    """
    ids, _ = _load_yaml_id_catalog_with_presence(
        directory,
        pattern,
        id_field=id_field,
        include_proposed=include_proposed,
        active_languages=active_languages,
    )
    return ids


def _extract_artifact_id(
    path: Path,
    id_field: str,
    active_languages: list[str] | tuple[str, ...] | None,
    yaml: object,
) -> str | None:
    """Return the artifact ID from a single YAML file, or None to skip.

    The catalog reads only shipped built-in directories, so each file is parsed
    at most once per change (#5526).
    """
    try:
        data = parse_shipped_yaml(path, lambda p: yaml.load(p.read_text(encoding="utf-8")), variant="safe-text") or {}  # type: ignore[attr-defined]
    except (OSError, YAMLError, TypeError):
        return None
    if isinstance(data, dict) and not applies_to_languages_match(
        data.get("applies_to_languages"), active_languages
    ):
        return None
    if isinstance(data, dict):
        raw_id = str(data.get(id_field, "")).strip()
        if raw_id:
            return raw_id
    fallback = path.stem.split(".")[0].strip()
    return fallback or None


def _collect_ids_from_roots(
    scan_roots: list[Path],
    pattern: str,
    id_field: str,
    active_languages: list[str] | tuple[str, ...] | None = None,
) -> set[str]:
    """Collect artifact IDs from one or more scan roots.

    Args:
        scan_roots: Directories to scan (each already a flat content dir).
        pattern: Glob pattern for artifact files (supports ``**``).
        id_field: YAML key containing the artifact ID.

    Returns:
        Set of discovered IDs (falls back to stem when YAML id_field is absent).
    """
    yaml = YAML(typ="safe")
    ids: set[str] = set()
    for scan_root in scan_roots:
        for path in sorted(scan_root.glob(pattern)):
            artifact_id = _extract_artifact_id(path, id_field, active_languages, yaml)
            if artifact_id:
                ids.add(artifact_id)
    return ids


def _resolve_scan_roots(
    directory: Path,
    *,
    _include_proposed: bool,
) -> tuple[list[Path], bool]:
    """Return the scan root for *directory* (always the flat content dir itself).

    Built-in artifact content is flat directly under ``packs/built-in/<kind>/``
    (the WP01 ``built_in_dir`` authority); the pre-relocation nested
    ``built-in/``/``_proposed/`` subdirectory dual-read fallback for the
    emptied ``src/charter/offering/<kind>/`` pre-move shape was removed in mission
    doctrine-built-in-seam-consolidation-01KYW3TX (WP02) -- exactly one
    location contract (the authority) remains. ``_include_proposed`` is
    accepted for call-site compatibility but has no effect: no shipped
    ``packs/built-in/<kind>/`` tree carries a nested ``_proposed/``
    subdirectory to opt into.

    Returns:
        Tuple of (scan_roots, present); ``present`` is always ``True`` -- the
        caller (:func:`_load_yaml_id_catalog_with_presence`) already guards on
        ``directory.is_dir()`` before calling this helper.
    """
    return [directory], True


def _load_yaml_id_catalog_with_presence(
    directory: Path,
    pattern: str,
    *,
    id_field: str = "id",
    include_proposed: bool = False,
    active_languages: list[str] | tuple[str, ...] | None = None,
) -> tuple[set[str], bool]:
    """Load ID values from charter.offering YAML files, also reporting domain presence.

    Returns:
        Tuple of (ids, present) where ``present`` is ``True`` when the artifact
        directory exists (a flat ``packs/built-in/<kind>/`` content dir).
        A ``True`` ``present`` value with an empty id set means the built-in
        catalog is explicitly empty — every selection against this domain is
        invalid.  A ``False`` ``present`` value means the domain is not
        deployed in this install and validation should be skipped.

    Args:
        directory: Artifact root directory to search.
        pattern: Glob pattern (supports ``**`` for recursive search).
        id_field: YAML key containing the artifact ID. Defaults to ``"id"``.
                  Use ``"profile-id"`` for agent profile files.
        include_proposed: accepted for call-site compatibility; has no effect
                  post-relocation (see :func:`_resolve_scan_roots`).
    """
    if not directory.is_dir():
        return set(), False

    scan_roots, present = _resolve_scan_roots(directory, _include_proposed=include_proposed)
    ids = _collect_ids_from_roots(
        scan_roots,
        pattern,
        id_field,
        active_languages,
    )
    return ids, present


def _load_template_sets_with_presence(_offering_root: Path) -> tuple[set[str], bool]:
    """Load available template set IDs, also reporting domain presence.

    Returns:
        Tuple of (template_sets, present) where ``present`` is ``True`` when the
        missions directory exists.  An empty set with ``present=True`` means no
        mission directories were found — every template-set selection is invalid.
        ``present=False`` means the missions directory is not deployed.
    """
    from charter.offering.missions import MissionTemplateRepository

    repo = MissionTemplateRepository.default()
    mission_names = repo.list_missions()

    if not mission_names and not repo._missions_root.is_dir():
        return set(), False

    template_sets = {f"{name}-default" for name in mission_names}
    return template_sets, True
