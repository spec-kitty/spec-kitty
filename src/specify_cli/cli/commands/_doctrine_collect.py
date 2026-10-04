"""Doctrine-health DATA COLLECTORS for the ``doctor doctrine`` command (WP03, #2059).

This module completes the doctrine-health seam that #1623 left behind. #1623
scoped its extraction to the RENDER layer only (``_profile_health_render``) and
left the collectors in ``doctor.py``. This module moves Cluster J — the data
collectors — beside the existing MODEL (:mod:`._doctrine_health`) and RENDER
(:mod:`._profile_health_render`) modules, finishing the MODEL/RENDER/COLLECT
triad.

Import discipline (one-way graph, I-2): collect → model / render / shared. This
module imports from :mod:`._doctrine_health` (MODEL types), from
:mod:`._profile_health_render` (the ``_SELECTION_KIND_PLURALS`` constant), and
from :mod:`._doctor_shared` if shared infra is needed. It must NEVER import
``doctor.py`` (the orchestrator re-exports FROM here).
"""

from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from charter.bundle import CHARTER_YAML

from ._profile_health_render import _SELECTION_KIND_PLURALS

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from charter.drg import DRGGraph, OrgDRGConflictError
    from charter.glossary_packs import GlossaryPack

    from ._doctrine_health import (
        DoctrineHealthReport,
        GlossaryPackHealth,
        PackSkillHealth,
        SkippedGlossaryPack,
        SkippedPackSkill,
    )

#: Parses the fixed ``"Skipping invalid <layer> <kind> <file>: <reason>"``
#: shape ``charter.offering.base.BaseDoctrineRepository`` emits on an unloadable
#: glossary-pack file (``_load_built_in_items`` / ``_apply_overlay_layer``).
#: ``re.DOTALL`` so a multi-line pydantic ``ValidationError`` reason is
#: captured in full, not truncated at the first newline.
_SKIPPED_GLOSSARY_PACK_PATTERN = re.compile(
    r"^Skipping invalid (?P<layer>\S+) \S+ (?P<filename>\S+): (?P<reason>.*)$",
    re.DOTALL,
)

# ``__all__`` lists the collectors re-exported through the ``doctor`` shim
# (FR-006) plus the collectors ``doctor.py`` delegates to. The remaining
# helpers are intra-module (used here + by this module's own unit tests) and
# are deliberately NOT exported — listing them would register orphan public
# symbols under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "_resolve_pack_version",
    "_count_pack_artifacts",
    "_collect_profile_health",
    "_run_cross_grain_check",
    "_run_operating_procedures_check",
    "_attach_pack_health",
    "_build_pack_entries",
    "_collect_doctrine_collisions",
    "_collect_org_layer_data",
    "_build_selection_block",
]


_ORG_ARTIFACT_DIRS: tuple[str, ...] = (
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "paradigms",
    "procedures",
    "agent_profiles",
    "mission_step_contracts",
)


def _read_authored_pack_version(pack_root: Path) -> str | None:
    """Read ``pack_version`` from an authored ``pack.yaml`` sibling, if any.

    IC-06 / FR-008 (pack-metadata-manifest-unification-01M052PT, WP04):
    mirrors :func:`specify_cli.doctrine.pack_assembler._read_authored_pack_version`
    (duplicated rather than imported to keep this collect-layer module's
    import discipline — collect → model/render/shared, never reaching into
    the assembler — intact). Returns ``None`` when no authored descriptor
    exists, it fails to parse, or it carries no ``pack_version`` field —
    callers fall back to the generated value (derive-else-fallback).
    """
    descriptor = pack_root / "pack.yaml"
    if not descriptor.is_file():
        return None
    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        data = yaml.load(descriptor.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("pack_version")
    return str(version) if version else None


def _resolve_pack_version(snapshot_path: Path) -> tuple[str, str | None, bool]:
    """Return ``(pack_version, fetched_at, is_git_pack)`` for a pack snapshot.

    Derive-else-fallback (IC-06/FR-008): an authored ``pack.yaml`` sibling's
    ``pack_version`` (the built-in pack) wins when present; ``fetched_at`` is
    ``None`` in that case (authored data carries no fetch provenance). Else,
    for git-managed snapshots, ``pack_version`` is the ``git describe --tags
    --always`` output; ``fetched_at`` is ``None``.  For non-git snapshots
    with no authored descriptor, the version + timestamp are read from
    ``pack-manifest.yaml`` when present (fetched/org packs — genuine
    fetch-time provenance, unchanged). Falls back to ``"unknown"`` if none of
    these sources yields a value.
    """
    authored_version = _read_authored_pack_version(snapshot_path)
    if authored_version is not None:
        return authored_version, None, False

    import subprocess as _sp

    is_git_pack = (snapshot_path / ".git").exists()
    if is_git_pack:
        try:
            version = _sp.check_output(
                ["git", "-C", str(snapshot_path), "describe", "--tags", "--always"],
                stderr=_sp.DEVNULL,
                text=True,
            ).strip()
            return version or "git (version unavailable)", None, True
        except (_sp.CalledProcessError, OSError):
            return "git (version unavailable)", None, True

    manifest_path = snapshot_path / "pack-manifest.yaml"
    if manifest_path.exists():
        try:
            from ruamel.yaml import YAML

            yaml = YAML(typ="safe")
            data = yaml.load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return "unknown", None, False
        if isinstance(data, dict):
            version = str(data.get("pack_version") or "unknown")
            fetched_at = data.get("fetched_at")
            return version, str(fetched_at) if fetched_at else None, False
    return "unknown", None, False


def _count_pack_artifacts(snapshot_path: Path) -> dict[str, int]:
    """Return per-artifact YAML counts for an org snapshot directory."""
    counts: dict[str, int] = {}
    for artifact_type in _ORG_ARTIFACT_DIRS:
        adir = snapshot_path / artifact_type
        if adir.exists():
            counts[artifact_type] = len(list(adir.glob("*.yaml")))
    return counts


def _summarize_org_charter(snapshot_path: Path) -> dict[str, object]:
    """Inspect ``org-charter.yaml`` in *snapshot_path* and return a JSON-able summary.

    Gracefully degrades when the optional
    ``specify_cli.doctrine.org_charter`` module is not yet shipped (WP09).
    """
    charter_path = snapshot_path / "org-charter.yaml"
    if not charter_path.exists():
        return {"present": False}

    try:
        from specify_cli.doctrine.org_charter import load_org_charter_policy
    except ImportError:
        # Module not yet shipped — surface presence without policy details.
        return {"present": True, "module_available": False}

    try:
        policy = load_org_charter_policy(snapshot_path)
    except Exception:  # noqa: BLE001
        return {"present": True, "module_available": True, "load_error": True}
    if policy is None:
        return {"present": False}

    return {
        "present": True,
        "module_available": True,
        "interview_defaults_count": len(getattr(policy, "interview_defaults", {}) or {}),
        "required_directives_count": len(getattr(policy, "required_directives", []) or []),
        "governance_policies_count": len(getattr(policy, "governance_policies", []) or []),
    }


def _collect_profile_health(repo_root: Path) -> DoctrineHealthReport:
    """Build the agent-profile + org-DRG health report once (WP08, NFR-001).

    Instantiates a single :class:`~charter.offering.service.DoctrineService` rooted at
    the configured org packs, reads the WP05
    ``AgentProfileRepository.skipped_profiles()`` diagnostics (no regex
    scraping), and groups valid + skipped counts into one ``PackHealth`` per
    layer.  The org-DRG state is collected here too so the human and JSON
    surfaces share a single DRG load (the old double-load was the main
    NFR-001 cost).

    Diagnostics are READ-ONLY and must never crash on operator
    misconfiguration. A profile-load failure no longer degrades to a silent,
    vacuously-green empty report (the #1584 false-healthy class): the crash is
    *recorded* (into ``org_drg["errors"]``) so the report is honestly unhealthy
    and "collector crashed" is distinguishable from "genuinely zero profiles".

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T013):
    diagnostic-completeness rationale -- this collector must see every
    profile regardless of charter activation state (a deactivated pack's
    profiles still need to be counted/health-checked so the operator sees
    the true installed set, not the currently-activated subset), so the raw
    inner service is wrapped via ``charter.activation.resolver.DoctrineService(inner,
    pack_context=None)`` -- the sanctioned unfiltered-diagnostic construction
    (data-model.md "unfiltered-diagnostic contract") -- rather than
    constructing ``charter.offering.service.DoctrineService`` directly. The
    ``AgentProfileRepository``-specific ``get_provenance()`` /
    ``skipped_profiles()`` calls below need the raw repository object (a
    ``dict`` has neither method), so this reads through the wrapper's
    ``agent_profile_repository`` accessor (FR-001) rather than the gated
    ``agent_profiles`` property, which always returns a filtered ``dict``.
    """
    from ._doctrine_health import DoctrineHealthReport, build_pack_health_by_layer

    from charter.profiles import SkippedProfile

    provenance_by_layer: dict[str, int] = {}
    skipped: list[SkippedProfile] = []
    load_error: str | None = None
    try:
        from charter.offering.service import DoctrineService as RawDoctrineService
        from charter.activation.resolver import DoctrineService as ActivationAwareDoctrineService
        from charter.drg import resolve_org_roots

        org_roots = resolve_org_roots(repo_root)
        project_doctrine = repo_root / ".kittify" / "doctrine"
        project_root = project_doctrine if project_doctrine.exists() else None
        inner = RawDoctrineService(
            org_roots=list(org_roots),
            project_root=project_root,
        )
        service = ActivationAwareDoctrineService(inner, pack_context=None)
        repo = service.agent_profile_repository
        for profile in repo.list_all():
            layer = repo.get_provenance(profile.profile_id) or "unknown"
            provenance_by_layer[layer] = provenance_by_layer.get(layer, 0) + 1
        skipped = list(repo.skipped_profiles())
    except Exception as exc:  # noqa: BLE001 — diagnostics must never crash
        provenance_by_layer = {}
        skipped = []
        load_error = f"profile-health load error: {exc}"

    packs = build_pack_health_by_layer(
        provenance_by_layer=provenance_by_layer,
        skipped_profiles=skipped,
    )
    org_drg = _collect_org_layer_data(repo_root)
    if load_error is not None:
        # Record the crash so the honest ``healthy`` flag (which checks
        # ``org_drg['errors']``) reports unhealthy rather than vacuously green.
        if isinstance(org_drg, dict):
            existing = org_drg.get("errors")
            errors = list(existing) if isinstance(existing, list) else []
            errors.append(load_error)
            org_drg["errors"] = errors
        else:  # pragma: no cover — _collect_org_layer_data always returns a dict
            org_drg = {"errors": [load_error]}
    glossary_pack_health = _collect_glossary_pack_health(repo_root)
    return DoctrineHealthReport(
        packs=packs,
        org_drg=org_drg,
        glossary_packs=glossary_pack_health,
        skills=_collect_pack_skill_health(repo_root),
    )


def _parse_skipped_glossary_pack_warning(message: object) -> SkippedGlossaryPack:
    """Turn one captured ``UserWarning`` into a structured skip record.

    ``BaseDoctrineRepository`` emits ``"Skipping invalid <layer> <kind> <file>:
    <reason>"`` (see ``charter.offering.base._load_built_in_items`` /
    ``_apply_overlay_layer``); this parses that fixed shape rather than
    inventing a second diagnostic format. A message that doesn't match (the
    production emitter's shape is pinned, so this is defensive only) degrades
    to an ``"unknown"`` layer/path with the full text as the reason, so a
    format drift still surfaces a diagnostic instead of raising.
    """
    from ._doctrine_health import SkippedGlossaryPack

    text = str(message)
    match = _SKIPPED_GLOSSARY_PACK_PATTERN.match(text)
    if match is None:
        return SkippedGlossaryPack(layer="unknown", path="unknown", error_summary=text)
    return SkippedGlossaryPack(
        layer=match.group("layer"),
        path=match.group("filename"),
        error_summary=match.group("reason"),
    )


def _collect_glossary_pack_health(repo_root: Path) -> GlossaryPackHealth:
    """Build the glossary-pack health dimension (FR-012, SC-001, WP05).

    Sourced from ``DoctrineService``'s glossary-pack repository — the real
    production repository (WP02), not a re-implemented loader. Unlike
    ``AgentProfileRepository``, ``GlossaryPackRepository`` (a plain
    ``BaseDoctrineRepository``) has no structured skip-diagnostics list: an
    unloadable pack file only ever surfaces as a ``UserWarning`` emitted
    during the repository's (lazy) ``_load()``. This collector captures those
    warnings during the first access to the repository and turns each into a
    :class:`~._doctrine_health.SkippedGlossaryPack` record — the same
    surfaced-not-swallowed pattern :func:`_collect_profile_health` already
    applies to agent profiles — so an invalid pack degrades the aggregate
    ``healthy`` (SC-001) instead of vanishing silently.

    Diagnostics are READ-ONLY and must never crash ``doctor doctrine`` on
    operator misconfiguration: a hard load crash (e.g. a completely
    unreadable doctrine root) degrades to zero packs plus one synthetic
    invalid-pack record, rather than a silent, vacuously-healthy empty report.

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T013):
    diagnostic-completeness rationale -- glossary-pack health must reflect
    every installed pack regardless of charter activation state (the whole
    point is auditing what is on disk, not what is currently activated), so
    the raw inner service is wrapped via ``charter.activation.resolver.DoctrineService(
    inner, pack_context=None)`` -- the sanctioned unfiltered-diagnostic
    construction (data-model.md "unfiltered-diagnostic contract") -- rather
    than constructing ``charter.offering.service.DoctrineService`` directly. FR-005
    made ``glossary_packs`` a gated property that always returns a filtered
    ``dict`` (no ``.list_all()``), so this reads through
    :meth:`~charter.activation.resolver.DoctrineService.raw_repository` to reach the raw
    repository's ``list_all()``.
    """
    from charter.offering.service import DoctrineService as RawDoctrineService
    from charter.activation.resolver import DoctrineService as ActivationAwareDoctrineService
    from charter.drg import resolve_org_roots

    from ._doctrine_health import GlossaryPackHealth, SkippedGlossaryPack

    packs: list[GlossaryPack] = []
    invalid: list[SkippedGlossaryPack] = []
    try:
        org_roots = resolve_org_roots(repo_root)
        project_doctrine = repo_root / ".kittify" / "doctrine"
        project_root = project_doctrine if project_doctrine.exists() else None
        inner = RawDoctrineService(
            org_roots=list(org_roots), project_root=project_root
        )
        service = ActivationAwareDoctrineService(inner, pack_context=None)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            packs = service.raw_repository("glossary_packs").list_all()
        invalid = [
            _parse_skipped_glossary_pack_warning(w.message)
            for w in captured
            if issubclass(w.category, UserWarning)
        ]
    except Exception as exc:  # noqa: BLE001 — diagnostics must never crash
        invalid = [
            SkippedGlossaryPack(
                layer="unknown",
                path="unknown",
                error_summary=f"glossary-pack health load error: {exc}",
            )
        ]

    term_count = sum(len(pack.terms) for pack in packs)
    return GlossaryPackHealth(
        pack_count=len(packs), term_count=term_count, invalid_packs=invalid
    )


def _parse_skipped_pack_skill_warning(message: object) -> SkippedPackSkill:
    """Turn one captured ``UserWarning`` into a structured skip record.

    Shares the fixed ``"Skipping invalid <layer> <kind> <file>: <reason>"``
    shape (and defensive ``unknown`` fallback) with the glossary-pack parser.
    """
    from ._doctrine_health import SkippedPackSkill

    text = str(message)
    match = _SKIPPED_GLOSSARY_PACK_PATTERN.match(text)
    if match is None:
        return SkippedPackSkill(layer="unknown", path="unknown", error_summary=text)
    return SkippedPackSkill(
        layer=match.group("layer"),
        path=match.group("filename"),
        error_summary=match.group("reason"),
    )


def _collect_pack_skill_health(repo_root: Path) -> PackSkillHealth:
    """Build the pack-skill health dimension (FR-015), mirroring glossary packs.

    Reads the raw (unfiltered) skill repository through the sole sanctioned
    builder (``build_activation_aware_doctrine_service``) and
    :meth:`~charter.activation.resolver.DoctrineService.raw_repository`, so
    every installed skill is audited regardless of activation. Load warnings
    become :class:`~._doctrine_health.SkippedPackSkill` records; a hard load
    failure (for example two sibling org packs declaring the same skill id)
    degrades to zero skills plus one synthetic invalid record instead of
    crashing ``doctor doctrine``.
    """
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    from ._doctrine_health import PackSkillHealth, SkippedPackSkill

    loaded = 0
    invalid: list[SkippedPackSkill] = []
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            service = build_activation_aware_doctrine_service(repo_root)
            loaded = len(service.raw_repository("skills").list_all())
        invalid = [_parse_skipped_pack_skill_warning(w.message) for w in captured if issubclass(w.category, UserWarning)]
    except Exception as exc:  # noqa: BLE001 — diagnostics must never crash
        invalid = [SkippedPackSkill(layer="unknown", path="unknown", error_summary=f"pack-skill health load error: {exc}")]
    return PackSkillHealth(skill_count=loaded, invalid_skills=invalid)


def _run_cross_grain_check(report: DoctrineHealthReport) -> None:
    """Fold the FR-013 built-in cross-grain scan into *report* in place (#2666).

    Runs :func:`charter.activation.action_grain.scan_builtin_cross_grain_duplicates` — the
    single IC-11 dup-scan authority (C-002) — against the shipped built-in
    missions tree. Scope is deliberately built-in only (the scan's own scope
    cap): no project/org multi-root engine is built here.

    On :class:`~charter.activation.mission_type_profiles.CrossGrainDoubleDeclarationError`
    this mutates ``report.org_drg`` in place, mirroring the fail-loud pattern
    :func:`_collect_profile_health` already uses for a collector crash:

    * appends a human-readable message to ``org_drg["errors"]`` — the honest
      ``DoctrineHealthReport.healthy`` flag reads this list, so a collision
      forces the report unhealthy (RC=1) without a parallel health field.
    * adds a structured ``org_drg["cross_grain_collisions"]`` finding
      (``kind`` / ``artifact``) so both the ``--json`` payload and the human
      renderer (:func:`._profile_health_render._render_cross_grain_findings`)
      can surface *what* collided, not just *that* something collided.

    On success (every shipped mission type disjoint) this is a no-op —
    ``report`` is left untouched and the exit code is unaffected.

    Diagnostics are READ-ONLY and must never crash ``doctor doctrine`` on a
    genuine collision: the exception is caught and folded into the report,
    not re-raised.
    """
    from charter.activation.action_grain import scan_builtin_cross_grain_duplicates
    from charter.activation.mission_type_profiles import CrossGrainDoubleDeclarationError

    try:
        scan_builtin_cross_grain_duplicates()
    except CrossGrainDoubleDeclarationError as exc:
        org_drg = report.org_drg
        if not isinstance(org_drg, dict):  # pragma: no cover — defensive; _collect_org_layer_data always returns a dict
            return
        message = (
            f"cross-grain doctrine-integrity violation (FR-013): artifact "
            f"{exc.artifact!r} ({exc.kind}) is declared in both the type grain "
            "and the action grain for a shipped mission type."
        )
        existing_errors = org_drg.get("errors")
        errors = list(existing_errors) if isinstance(existing_errors, list) else []
        errors.append(message)
        org_drg["errors"] = errors
        org_drg["cross_grain_collisions"] = [
            {"kind": exc.kind, "artifact": exc.artifact}
        ]


def _run_operating_procedures_check(report: DoctrineHealthReport) -> None:
    """Fold the built-in ``operating-procedures`` resolution scan into *report*.

    Every ``collaboration.operating-procedures`` entry on a built-in agent
    profile must resolve to a real ``procedure:`` DRG node. This surfaces the
    ones that do not (fictional or wrong-kind) so the diagnostic is discoverable
    outside the architectural gate. Scope is built-in only (C-006): org/project
    tiers are guarded at edge-emission time, not hard-failed here.

    Mirrors :func:`_run_cross_grain_check`'s fail-loud pattern — a non-empty set
    appends to ``org_drg["errors"]`` (so ``DoctrineHealthReport.healthy`` reports
    unhealthy) and always records a structured
    ``org_drg["operating_procedures_unresolved"]`` finding (present-and-empty on
    a healthy tree). Read-only; never raises ``doctor doctrine``.
    """
    from charter.offering.agent_profiles.operating_procedures import (
        collect_operating_procedure_entries,
        node_universe,
        resolve_operating_procedure_entries,
    )
    from charter.offering.drg.loader import load_built_in_graph
    from charter.offering.artifact_kinds import ArtifactKind
    from charter.offering.pack_paths import built_in_dir

    org_drg = report.org_drg
    if not isinstance(org_drg, dict):  # pragma: no cover — always a dict
        return
    try:
        procedure_urns, urns_by_kind = node_universe(load_built_in_graph().nodes)
        entries = collect_operating_procedure_entries(
            built_in_dir(ArtifactKind.AGENT_PROFILE)
        )
        unresolved = resolve_operating_procedure_entries(
            entries, procedure_urns, urns_by_kind
        )
    except Exception as exc:  # noqa: BLE001 — diagnostics must never crash
        existing = org_drg.get("errors")
        errors = list(existing) if isinstance(existing, list) else []
        errors.append(f"operating-procedures scan error: {exc}")
        org_drg["errors"] = errors
        return

    org_drg["operating_procedures_unresolved"] = [
        {
            "profile_id": u.profile_id,
            "entry": u.entry,
            "reason": u.reason,
            "resolved_kind": u.resolved_kind,
        }
        for u in unresolved
    ]
    if unresolved:
        noun = "entry" if len(unresolved) == 1 else "entries"
        message = (
            f"{len(unresolved)} built-in operating-procedures {noun} resolve to "
            "no procedure node (fictional or wrong-kind)"
        )
        existing = org_drg.get("errors")
        errors = list(existing) if isinstance(existing, list) else []
        errors.append(message)
        org_drg["errors"] = errors


def _attach_pack_health(
    pack_entries: list[dict[str, object]], report: DoctrineHealthReport
) -> None:
    """Attach per-layer ``PackHealth`` to registry pack entries for FR-010 rendering.

    Org-pack registry entries are org-layer snapshots, so each present pack is
    annotated with the report's ``org`` layer health (if any).  This is what
    makes the human renderer color the pack header from derived health rather
    than snapshot presence.
    """
    org_pack = next((p for p in report.packs if p.layer == "org"), None)
    if org_pack is None:
        return
    health_dict = org_pack.to_dict()
    for entry in pack_entries:
        if entry.get("snapshot_present"):
            entry["pack_health"] = health_dict


def _build_pack_entries(registry: object, repo_root: Path) -> list[dict[str, object]]:
    """Build per-pack registry entries (name/version/counts/charter) for rendering."""
    pack_entries: list[dict[str, object]] = []
    for pack in registry.packs:  # type: ignore[attr-defined]
        snapshot_path = pack.effective_root(repo_root)
        entry: dict[str, object] = {
            "name": pack.name,
            "local_path": str(snapshot_path),
            "source_type": pack.source_type,
            "url": pack.url,
            "ref": pack.ref,
            "snapshot_present": snapshot_path.exists(),
        }
        if snapshot_path.exists():
            version, fetched_at, is_git = _resolve_pack_version(snapshot_path)
            entry["pack_version"] = version
            entry["fetched_at"] = fetched_at
            entry["is_git_pack"] = is_git
            entry["artifact_counts"] = _count_pack_artifacts(snapshot_path)
            entry["org_charter"] = _summarize_org_charter(snapshot_path)
        pack_entries.append(entry)
    return pack_entries


def _collect_doctrine_collisions(repo_root: Path) -> list[dict[str, object]]:
    """Run the doctrine resolver and collect any layer-collision warnings.

    Returns a list of structured collision descriptors (kind, item_id,
    higher_layer, lower_layer, replaced, inherited) for surfacing via
    ``doctor doctrine`` (FR-003 wording per ADR 2026-05-16-1).

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T013):
    diagnostic-completeness rationale -- collision detection must scan every
    layer regardless of charter activation state (a collision between a
    deactivated pack's artifact and a built-in one is still a real
    cross-layer collision the operator needs to see), so the raw inner
    service is wrapped via ``charter.activation.resolver.DoctrineService(inner,
    pack_context=None)`` -- the sanctioned unfiltered-diagnostic construction
    (data-model.md "unfiltered-diagnostic contract") -- rather than
    constructing ``charter.offering.service.DoctrineService`` directly. Each gated
    property below still triggers the same eager, warning-emitting
    repository ``_load()`` as the raw accessor did (``BaseDoctrineRepository.
    __init__`` loads eagerly); only the return *value* is now a filtered
    ``dict`` (irrelevant here -- this loop only cares about the load
    side-effect, not the returned mapping).
    """
    import re
    import warnings as _warnings

    from charter.drg import DoctrineLayerCollisionWarning
    from charter.offering.service import DoctrineService as RawDoctrineService
    from charter.activation.resolver import DoctrineService as ActivationAwareDoctrineService
    from charter.drg import resolve_org_roots

    org_roots = resolve_org_roots(repo_root)
    project_doctrine = repo_root / ".kittify" / "doctrine"
    project_root = project_doctrine if project_doctrine.exists() else None

    inner = RawDoctrineService(
        org_roots=list(org_roots),
        project_root=project_root,
    )
    service = ActivationAwareDoctrineService(inner, pack_context=None)

    # Touch every repository so each one runs through its loader and emits
    # any collision warnings.
    accessors = (
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "mission_step_contracts",
        "agent_profiles",
    )

    collisions: list[dict[str, object]] = []
    pattern = re.compile(
        r"Doctrine override: (?P<kind>\S+) (?P<item_id>\S+) "
        r"from (?P<higher>\S+) shadowed (?P<lower>\S+) "
        r"\((?P<replaced>\d+) field\(s\) replaced; "
        r"(?P<inherited>\d+) field\(s\) inherited\)\."
    )

    with _warnings.catch_warnings(record=True) as captured:
        _warnings.simplefilter("always")
        for name in accessors:
            try:
                getattr(service, name)
            except Exception:  # noqa: BLE001, S112 — doctor must not fail on a single repo's load error
                continue
    for w in captured:
        if not isinstance(w.message, DoctrineLayerCollisionWarning):
            continue
        m = pattern.match(str(w.message))
        if not m:
            continue
        collisions.append(
            {
                "kind": m.group("kind"),
                "item_id": m.group("item_id"),
                "higher_layer": m.group("higher"),
                "lower_layer": m.group("lower"),
                "replaced": int(m.group("replaced")),
                "inherited": int(m.group("inherited")),
            }
        )
    return collisions


def _collect_org_layer_data(repo_root: Path) -> dict[str, object]:
    """Return structured org-layer data for ``doctor doctrine --json`` (FR-007).

    Mirrors the human-readable output of :func:`_render_org_layer_section`
    but as a dict suitable for JSON serialisation.  Always returns a dict
    with an ``"org_drg"`` key so callers can rely on its presence.
    """
    from charter.drg import (
        OrgDRGConflictError,
        OrgPackMissingError,
        load_built_in_graph,
    )
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    result: dict[str, object] = {
        "configured_packs": [],
        "collision_warnings": [],
        # Unconditionally present. It used to be written only when non-empty, so
        # a missing key conflated "the completeness check ran and found nothing"
        # with "the check never ran" — the ambiguity the broad handler below is
        # commented against ("a check that could not RUN is not a check that
        # PASSED"). An absent key is not a finding of absence. When the merge
        # refuses the graph the check genuinely cannot run; that case is not
        # signalled by this key but by the hard-failure entry in ``errors``,
        # which is the channel the health verdict reads.
        "dangling_endpoints": [],
        "errors": [],
    }

    try:
        fragments = load_org_drg(repo_root)
    except OrgPackMissingError as exc:
        result["errors"] = [str(exc)]
        return result
    except Exception as exc:  # noqa: BLE001
        result["errors"] = [f"org-DRG load error: {exc}"]
        return result

    packs = []
    for frag in fragments:
        packs.append(
            {
                "name": frag.pack_name,
                "source_kind": frag.source_kind,
                "source_ref": frag.source_ref,
                "layer_index": frag.layer_index,
                "node_count": len(frag.nodes),
                "edge_count": len(frag.edges),
                "fetched": True,
            }
        )
    result["configured_packs"] = packs

    if not fragments:
        return result

    # The merge is the ONLY thing in this try. The post-merge checks used to sit
    # inside it, which cost twice: a hard-fail raise aborted the block before
    # they ran (so a refused pack reported no dangling endpoints and no
    # unsanctioned overrides — "more breakage" read as "fewer findings"), and a
    # crash in either check was attributed to "merge check failed". Separating
    # them lets each defect report itself.
    built_in = None
    merged = None
    try:
        built_in = load_built_in_graph()
        # WP08 (FR-010): reuse the SAME merge the org-layer section already runs
        # (C-006 — no new DRG plumbing). The merged graph is now captured, not
        # discarded, so the promoted predicates can adjudicate built-in overrides.
        merged = merge_three_layers(
            built_in=built_in, org_fragments=fragments, project=None
        )
    except OrgDRGConflictError as exc:
        _record_org_conflicts(result, exc)
    except Exception as exc:  # noqa: BLE001 — doctor must not crash on a bad pack
        # A check that could not RUN is not a check that PASSED. This handler
        # used to be a bare ``pass``; since the block also decides org-layer
        # completeness, swallowing meant a crashed merge produced ``errors: []``
        # and ``DoctrineHealthReport.healthy`` read that as clean — RC=0 having
        # verified nothing. Report it on the same channel the load failure above
        # already uses, so the diagnostic degrades loudly instead of silently.
        _append_org_errors(result, [f"org-layer merge check failed: {exc}"])

    if merged is None or built_in is None:
        # No graph: the post-merge checks have nothing to inspect. ``errors``
        # already carries why, so the report is unhealthy without inventing a
        # verdict for a check that never ran.
        return result

    try:
        _run_post_merge_org_checks(result, merged, built_in, repo_root)
    except Exception as exc:  # noqa: BLE001 — doctor must not crash on a bad pack
        # Same principle, its own attribution: the merge succeeded, so blaming
        # this on the merge would send the operator to the wrong artefact.
        _append_org_errors(result, [f"org-layer post-merge check failed: {exc}"])

    return result


def _record_org_conflicts(result: dict[str, object], exc: OrgDRGConflictError) -> None:
    """Route a refused merge onto BOTH the advisory and the verdict channels.

    ``merge_three_layers`` raises with every conflict it found, mixing advisory
    precedence records with the fatal refusals that caused the raise. All of
    them keep their typed record in ``collision_warnings`` (a flat error string
    is too lossy to drive tooling), but only the fatal ones are copied into
    ``errors``.

    That copy is the fix for this module's headline defect: ``errors`` is the
    only channel ``DoctrineHealthReport.healthy`` reads, so writing a hard
    failure exclusively to ``collision_warnings`` reported a graph the merge
    layer had *refused to assemble* as ``healthy: True`` with ``RC=0``.
    Partitioning by ``resolution_applied`` is delegated to
    ``OrgDRGConflictError`` rather than re-derived here, so all three collectors
    agree on what "fatal" means.
    """
    result["collision_warnings"] = [
        {
            "kind": c.kind,
            "target_id": c.target_id,
            "conflicting_layers": c.conflicting_layers,
            "resolution": c.resolution_applied,
        }
        for c in exc.conflicts
    ]
    _append_org_errors(result, exc.hard_failure_messages)


def _run_post_merge_org_checks(
    result: dict[str, object],
    merged: DRGGraph,
    built_in: DRGGraph,
    repo_root: Path,
) -> None:
    """Run the checks that need an assembled graph, and record their findings.

    The endpoint policy's post-assembly half. ``merge_three_layers`` accepts a
    fully-qualified endpoint verbatim (a sibling pack or a later layer may
    supply the node) and only WARNs when it binds to nothing, because it cannot
    know whether its caller merged the whole graph or a deliberate subset.

    The rule for running the escalation is a predicate on the merge, not a
    property of this command: run it iff you merged the COMPLETE graph — the
    real shipped built-in against every configured pack. The caller satisfies
    that, so a dangling endpoint is an error here. Its two siblings
    (``_render_org_layer_section``, ``_collect_org_layer_status``) build the
    same merge from the same inputs and run it for the same reason; ``charter
    lint`` merges against an intentionally EMPTY built-in and therefore must
    not. The predicate lives on ``validate_dangling_references``; use the
    canonical check rather than a doctor-local restatement of "dangling".
    """
    from charter.drg import validate_dangling_references  # noqa: PLC0415

    dangling = validate_dangling_references(merged)
    if dangling:
        result["dangling_endpoints"] = dangling
        _append_org_errors(result, dangling)

    built_in_urns = frozenset(node.urn for node in built_in.nodes)
    unsanctioned = _adjudicate_org_overrides(merged, built_in_urns, repo_root)
    if unsanctioned:
        # Dedicated key for precise rendering (human/JSON) AND an entry in
        # ``errors`` so the honest ``DoctrineHealthReport.healthy`` predicate
        # flips the report unhealthy (RC=1) without a parallel health path.
        result["unsanctioned_overrides"] = unsanctioned
        _append_org_errors(
            result,
            [
                f"unsanctioned built-in override: {f['urn']} ({f['kind']}) — {f['why']}"
                for f in unsanctioned
            ],
        )


def _append_org_errors(result: dict[str, object], messages: list[str]) -> None:
    """Append *messages* to ``result['errors']`` with isinstance narrowing.

    ``DoctrineHealthReport.healthy`` treats a non-empty ``org_drg['errors']`` as
    unhealthy, so this is the in-ownership channel that flips the exit code when
    an unsanctioned override is found (no edit to ``_doctrine_health.py``).
    """
    existing = result.get("errors")
    errors = list(existing) if isinstance(existing, list) else []
    errors.extend(messages)
    result["errors"] = errors


def _adjudicate_org_overrides(
    merged: DRGGraph,
    built_in_urns: frozenset[str],
    repo_root: Path,
) -> list[dict[str, str]]:
    """Adjudicate org overrides of built-in DRG nodes against the repo allowlist.

    Pure governance helper extracted from :func:`_collect_org_layer_data` to keep
    that collector at complexity ≤ 15 (NFR-003). It reuses the WP07-promoted
    predicates over an ALREADY-MERGED graph and runs no merge of its own
    (C-006). Only ``org:``-provenance overrides are adjudicated; project-tier
    (``.kittify/doctrine/``) overrides are intentionally ungoverned (FR-012).

    Returns a JSON-serialisable list of ``{"urn", "kind", "why"}`` findings —
    empty when every override is sanctioned by
    ``.kittify/doctrine/replaceable-builtins.yaml`` (or none exist).
    """
    from charter.offering.drg.override_policy import (  # noqa: PLC0415
        find_overridden_builtin_urns,
        find_unsanctioned_overrides,
        load_replaceable_builtins,
    )

    targets = find_overridden_builtin_urns(merged, built_in_urns)
    if not targets:
        return []
    policy = load_replaceable_builtins(repo_root)
    findings = find_unsanctioned_overrides(targets, policy)
    return [{"urn": f.urn, "kind": f.kind, "why": f.why} for f in findings]


class _RawRepositorySource(Protocol):
    """Structural type for a *service* exposing ``raw_repository(kind)``.

    Matches :meth:`charter.activation.resolver.DoctrineService.raw_repository` (FR-002
    Option A) without importing ``charter.activation.resolver`` at module scope —
    :func:`_resolve_artifact_source` only needs this one method's shape, and
    the module keeps its existing import discipline (I-2: collect → model /
    render / shared; ``charter.activation.resolver`` is not one of those).
    """

    def raw_repository(self, kind: str) -> Any: ...


def _resolve_artifact_source(
    item_id: str,
    plural: str,
    service: _RawRepositorySource,
    org_required: dict[str, list[str]],
    project_selected: set[str],
) -> str:
    """Return a stable ``source: <token>`` annotation for *item_id*.

    The annotation tokens are deliberately compact so the snapshot test
    can pin them byte-for-byte:

    * ``built-in`` — artifact comes from the built-in doctrine layer
    * ``project`` — artifact lives under ``.kittify/doctrine/``
    * ``org`` — artifact lives in an org pack (per-pack attribution is
      not yet tracked at the repository layer; see ``_collect_org_source_map``
      in charter.activation.context for the same limitation)
    * ``charter`` — declared selected in the project charter but the
      DoctrineService does not (yet) know about it (e.g. typo or
      missing snapshot)
    * ``org-required`` — required by an org pack's ``org-charter.yaml``
      but not present in the resolved catalog

    *service* is a :class:`charter.activation.resolver.DoctrineService` and MUST be
    queried via its ``raw_repository(plural)`` accessor, not
    ``getattr(service, plural)`` (WP03, charter-sole-door-bypass-closure-
    01KZ3WAA, FR-002/T013): the gated ``plural`` property always returns a
    filtered ``dict``, which has no ``.get_provenance()`` — the same
    "filtered dict can't do repository ops" problem
    :func:`_collect_profile_health` solves via the more specific
    ``agent_profile_repository`` accessor. *service* is typed via the
    ``_RawRepositorySource`` structural protocol above (rather than
    importing ``charter.activation.resolver.DoctrineService`` directly) so this
    diagnostic helper does not force a hard ``charter`` import at module
    scope.
    """
    repo = service.raw_repository(plural)
    if repo is not None:
        try:
            provenance = repo.get_provenance(item_id)
        except (AttributeError, KeyError):
            provenance = None
        if provenance == "builtin":
            return "built-in"
        if provenance == "project":
            return "project"
        if provenance == "org":
            return "org"
    # Not loaded — distinguish "project charter declared it" vs "org pack
    # required it" so the operator can find the right config file.
    if item_id in project_selected:
        return "charter"
    if item_id in (org_required.get(plural) or []):
        return "org-required"
    return "unknown"


def _read_project_selections(repo_root: Path) -> dict[str, list[str]]:
    """Read project-charter ``selected_<kind>`` lists (best-effort, FR-018).

    We intentionally bypass ``charter.activation.sync.load_governance_config`` here: that
    loader resolves the canonical (main-checkout) repo root, which requires a
    git repository. The Selections section is a diagnostic — it MUST work in
    any working tree, including freshly-bootstrapped tmp fixtures and non-git
    operator workspaces. Reading ``charter.yaml``'s ``governance:`` section
    directly (IC-04 / WP04 — re-pointed from the retired ``governance.yaml``)
    preserves accuracy while keeping the diagnostic side-effect-free and
    git-independent. Missing/malformed YAML degrades to empty lists.
    """
    selections: dict[str, list[str]] = {kind: [] for kind in _SELECTION_KIND_PLURALS}
    charter_yaml = repo_root / CHARTER_YAML
    if not charter_yaml.exists():
        return selections
    try:
        from charter.activation.charter_yaml_io import load_charter_yaml

        data = load_charter_yaml(charter_yaml)
        governance_block = (data or {}).get("governance") or {}
        # CR-01 (charter-authority-flip-01M14RB3 WP03): the selection block's
        # key was renamed doctrine -> charter. This diagnostic reads the raw
        # dict directly (see the docstring above) rather than through
        # charter.activation.sync.load_governance_config's warn-once compat shim, so it
        # carries its own narrow read of both keys, preferring the canonical
        # one.
        doctrine_block = governance_block.get("charter") or governance_block.get("doctrine") or {}
        for kind in _SELECTION_KIND_PLURALS:
            value = doctrine_block.get(f"selected_{kind}")
            if isinstance(value, list):
                selections[kind] = [str(v) for v in value]
    except Exception:  # noqa: BLE001 — diagnostics must never crash on malformed yaml
        pass
    return selections


def _read_org_required(repo_root: Path) -> dict[str, list[str]]:
    """Read merged org-charter ``required_<kind>`` lists (best-effort, FR-018).

    Missing or invalid org config degrades to empty lists; diagnostics must
    never crash.
    """
    from charter.drg import (
        OrgPackEnvVarUnsetError,
        OrgPackSubdirEscapeError,
    )

    org_required: dict[str, list[str]] = {kind: [] for kind in _SELECTION_KIND_PLURALS}
    try:
        from charter.activation.invocation_context import ProjectContext
        from specify_cli.doctrine.org_charter import load_org_charter_policies

        _pack_ctx = None
        try:
            _ctx = ProjectContext.from_repo(repo_root)
            _pack_ctx = _ctx.require_pack_context()
        except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError) as exc:
            # Diagnostics must never crash (this function's own contract), but a
            # fail-closed pack-config error must not vanish silently either —
            # surface it at WARNING so `doctor doctrine` output is explainable.
            logger.warning("org pack context unavailable for selection diagnostics: %s", exc)
        except Exception:  # noqa: BLE001 — pack_context is best-effort
            pass

        policy = load_org_charter_policies(repo_root, pack_context=_pack_ctx)
        for kind in _SELECTION_KIND_PLURALS:
            org_required[kind] = list(getattr(policy, f"required_{kind}", []) or [])
    except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError) as exc:
        logger.warning("org-charter policy load failed for selection diagnostics: %s", exc)
    except Exception:  # noqa: BLE001 — diagnostics must never crash on missing/invalid org
        pass
    return org_required


def _build_selection_block(repo_root: Path) -> dict[str, list[dict[str, str]]]:
    """Return ``{plural: [{"id": ..., "source": ...}, ...]}`` for FR-018.

    Composes the union of project charter ``selected_<kind>`` and merged
    org ``required_<kind>`` lists, dedupes per-kind (preserving order:
    project-charter ids first, org-required ids appended), and tags each
    entry with the resolved source layer.

    Mission-type-profile selections are intentionally excluded here:
    profiles apply per-mission (gated by ``meta.json mission_type``)
    while ``doctor doctrine`` is a project-wide diagnostic.  The
    selections block reflects the *globally* active set so the operator
    can audit charter intent without picking a specific mission.

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T013):
    diagnostic-completeness rationale -- provenance lookup here answers
    "which layer supplies this charter-selected/org-required artifact" and
    must consult the full installed catalog, not the currently-activated
    subset (a selection that is charter-declared but not currently activated
    still needs its true provenance reported, not an activation-narrowed
    miss), so the raw inner service is wrapped via
    ``charter.activation.resolver.DoctrineService(inner, pack_context=None)`` -- the
    sanctioned unfiltered-diagnostic construction (data-model.md
    "unfiltered-diagnostic contract") -- rather than constructing
    ``charter.offering.service.DoctrineService`` directly.
    ``_resolve_artifact_source`` reads through the wrapper's
    ``raw_repository(plural)`` accessor (FR-002 Option A) to reach
    ``get_provenance()``, since the gated per-kind properties always return
    a filtered ``dict``.
    """
    from charter.offering.service import DoctrineService as RawDoctrineService
    from charter.activation.resolver import DoctrineService as ActivationAwareDoctrineService
    from charter.drg import resolve_org_roots

    project_selections = _read_project_selections(repo_root)
    org_required = _read_org_required(repo_root)

    # DoctrineService instance for provenance lookup.
    org_roots = resolve_org_roots(repo_root)
    project_doctrine = repo_root / ".kittify" / "doctrine"
    project_root = project_doctrine if project_doctrine.exists() else None
    inner = RawDoctrineService(
        org_roots=list(org_roots),
        project_root=project_root,
    )
    service = ActivationAwareDoctrineService(inner, pack_context=None)

    result: dict[str, list[dict[str, str]]] = {}
    for kind in _SELECTION_KIND_PLURALS:
        seen: set[str] = set()
        ordered: list[str] = []
        for item_id in project_selections[kind] + org_required[kind]:
            if item_id in seen:
                continue
            seen.add(item_id)
            ordered.append(item_id)
        project_set = set(project_selections[kind])
        entries: list[dict[str, str]] = []
        for item_id in ordered:
            entries.append({
                "id": item_id,
                "source": _resolve_artifact_source(
                    item_id, kind, service, org_required, project_set
                ),
            })
        result[kind] = entries
    return result
