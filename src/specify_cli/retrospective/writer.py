"""Atomic round-trip writer for retrospective.yaml.

Uses ruamel.yaml round-trip dumper for stable byte output, and os.replace
for atomic rename so a crash never leaves a partially-written canonical file.

WP03 additions:
  - ``write_gen_record(record, mode, repo_root)`` for GenRetrospectiveRecord with
    error / overwrite / update semantics.
  - ``RecordExistsError`` raised by mode="error" when canonical path exists.
  - Defense-in-depth ``synthesize_fabricate ⇒ ran_no_findings`` check (T014).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML

from kernel.yaml_io import write_mapping_atomic
from charter.activation.mission_type_key import read_mission_type
from specify_cli.core.constants import RETROSPECTIVE_FILENAME
from specify_cli.retrospective.schema import (
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
    RecordValidationError,
    RetrospectiveRecord,
    validate_record,
)


def resolve_retrospective_home(repo_root: Path, mission_slug: str) -> Path:
    """Return the durable PRIMARY home dir for a mission's retrospective record.

    The SINGLE home-resolution authority for ``retrospective.yaml`` (FR-001/003,
    #2119). Every retrospective placement site routes through THIS function so the
    record lands in the durable tracked home (``kitty-specs/<slug>/``) for EVERY
    topology — never the ephemeral coordination worktree (the #1771 coord-leak
    this mission cures). Re-introducing an independent resolution (a coord-aware
    ``resolve_feature_dir_for_*`` call, or a hardcoded ``.kittify/missions/...``
    payload) at any placement site is a regression the FR-003 structural test
    (``test_home_resolution_single_authority``) fails the build on.

    The retrospective is a terminal PRIMARY-partition artifact
    (:attr:`MissionArtifactKind.RETROSPECTIVE`, gated below); the home is the
    topology-blind module-private leaf
    :func:`~specify_cli.missions._read_path_resolver._compose_primary_feature_dir`
    join primitive.

    FR-011 write leg (#2136): the blind primitive composes its handle verbatim,
    so the caller canonicalizes the handle here FIRST — mirroring the read leg's
    caller-side fold (:func:`resolve_planning_read_dir`) and reusing the SAME
    shared canonicalizer (no bespoke resolver — C-006). An *ambiguous* handle
    propagates :class:`MissionSelectorAmbiguous` — no silent pick (C-009).

    **Foundation site (read-side-seam-primary-primitive-closure-01KYKMMT WP03,
    Ledger cycle-1 B1/B2) — this call MUST target the module-private leaf
    ``_compose_primary_feature_dir``, never the public wrapper
    ``primary_feature_dir_for_mission``.** This function is itself the callee
    :func:`mission_runtime.resolution.PlacementSeam.read_dir` dispatches
    ``RETROSPECTIVE`` reads to (the seam's kind-specific chokepoint,
    ``resolution.py:1454``), *beneath* ``read_dir`` in the call graph. The
    public wrapper's body now delegates to
    ``placement_seam(repo_root, slug).read_dir(PRIMARY_METADATA)`` (WP03 T019)
    — so calling the wrapper from here closes a
    ``read_dir → resolve_retrospective_home → wrapper → read_dir`` cycle
    (NFR-009). No ``RecursionError`` fires only because the wrapper's
    ``PRIMARY_METADATA`` leg happens not to re-enter; that is a property of the
    constant, not of the call graph, and does not make the cycle safe. This
    site therefore joins the four FR-005 foundation sites
    (``core/paths.py`` x2, ``core/git_ops.py``,
    ``coordination/surface_resolver.py``) that call the leaf directly and
    permanently, even after WP08 deletes the public wrapper — it is NOT a
    call site WP06 routes through the seam; WP06 verifies it stays a leaf call
    and does not touch it.

    Raises:
        AssertionError: If the partition predicate ever stops classifying
            ``RETROSPECTIVE`` as a PRIMARY kind (a guard against a silent
            re-partition reintroducing the coord-leak).
        MissionSelectorAmbiguous: When ``mission_slug`` matches >1 mission.
        ValueError: When ``mission_slug`` is not a safe path segment.
    """
    from mission_runtime import MissionArtifactKind, is_primary_artifact_kind
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    # The retrospective is a PRIMARY-partition kind by contract (FR-002): assert
    # the partition before resolving so a future re-partition that quietly demotes
    # RETROSPECTIVE to a coord kind is caught here, not by a re-leaked record.
    assert is_primary_artifact_kind(MissionArtifactKind.RETROSPECTIVE)
    # FR-011 write leg (#2136/#2164): the topology-blind primitive composes its
    # handle verbatim, so the caller folds the handle FIRST through the SAME proven
    # full-fold the PRIMARY read leg uses (``_canonicalize_primary_read_handle`` —
    # identity forms + bare-human-slug). The prior ``_canonicalize_bare_modern_handle``
    # only folded a bare *human slug*; a bare ``mid8`` / full ULID / numeric prefix
    # therefore composed a DIVERGENT dir on the write leg while the read leg resolved
    # the real one (the #2136 read/write divergence this closes). An *ambiguous*
    # handle propagates :class:`MissionSelectorAmbiguous` — no silent pick (C-009).
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP03 cycle-1 fix (B1):
    # call the module-private leaf directly, NEVER the public wrapper
    # ``primary_feature_dir_for_mission`` — see the foundation-site paragraph
    # above. This restores this write leg's pre-WP03 behaviour exactly (the
    # leaf's body is byte-identical to what the wrapper composed before Half B
    # made it delegate to the seam), so no NFR-001 divergence remains on this
    # write path: no backfill recovery, no double handle-fold.
    canonical = _canonicalize_primary_read_handle(repo_root, mission_slug)
    feature_dir: Path = _compose_primary_feature_dir(repo_root, canonical)
    return feature_dir


def canonical_record_path(repo_root: Path, mission_slug: str) -> Path:
    """Return the canonical (tracked) retrospective.yaml path for a mission.

    FR-001/003 (#2119): the record lives in the mission's durable PRIMARY home
    (``kitty-specs/<slug>/retrospective.yaml``), resolved through the single
    :func:`resolve_retrospective_home` authority for every topology — never the
    ephemeral coordination worktree (the #1771 coord-leak).
    """
    path: Path = resolve_retrospective_home(repo_root, mission_slug) / RETROSPECTIVE_FILENAME
    return path


def repo_relative_record_path(path: Path, repo_root: Path) -> str:
    """Return ``path`` as a POSIX path relative to the main repository root.

    The SINGLE authority for the ``record_path`` persisted into tracked event
    payloads (#5868): an absolute path would leak the operator's home directory
    into ``status.events.jsonl``. Anchored on ``get_main_repo_root(repo_root)`` --
    the same base :func:`resolve_retrospective_home` composes the durable home
    from -- so a worktree or unresolved ``repo_root`` cannot make it raise for a
    path produced by :func:`canonical_record_path`.

    Fail-closed: a path outside the main repo root raises ``ValueError`` (from
    ``Path.relative_to``) rather than falling back to the absolute path, which
    would silently reintroduce the leak.
    """
    from specify_cli.core.paths import get_main_repo_root

    return path.relative_to(get_main_repo_root(repo_root)).as_posix()


def _legacy_record_path(repo_root: Path, mission_id: str) -> Path:
    """Return the pre-#1771 (gitignored) record path for back-compat reads only.

    Records authored before the FR-006 relocation live at
    ``.kittify/missions/<mission_id>/retrospective.yaml`` (gitignored). New
    writes never target this path; readers fall back to it so archived/legacy
    records remain visible.
    """
    path: Path = repo_root / ".kittify" / "missions" / mission_id / RETROSPECTIVE_FILENAME
    return path


def resolve_existing_record_path(
    repo_root: Path,
    mission_slug: str,
    mission_id: str,
) -> Path:
    """Return the record path to READ for a mission, preferring the tracked home.

    Resolution order (FR-006 #1771):
    1. Tracked ``kitty-specs/<slug>/retrospective.yaml`` if it exists.
    2. Legacy gitignored ``.kittify/missions/<id>/retrospective.yaml`` if it
       exists (back-compat for records authored before relocation).
    3. The tracked path (so callers report the canonical location when neither
       exists — e.g. RETROSPECTIVE_RECORD_MISSING).
    """
    tracked = canonical_record_path(repo_root, mission_slug)
    if tracked.exists():
        return tracked
    legacy = _legacy_record_path(repo_root, mission_id)
    if legacy.exists():
        return legacy
    return tracked


class WriterError(Exception):
    """Raised when the writer cannot persist a retrospective record."""


class RecordExistsError(WriterError):
    """Raised by write_gen_record(mode='error') when canonical path already exists.

    Attributes:
        path: The canonical path that already exists.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            f"Retrospective record already exists at {path}. "
            "Use mode='overwrite' to replace it wholesale, or mode='update' to "
            "merge with the existing record. "
            "CLI flags: --overwrite / --update"
        )


def _atomic_write_yaml(data: dict[str, Any], canonical: Path, target_dir: Path) -> None:
    """Atomically write a dict as YAML to ``canonical``.

    Shared primitive used by both ``write_record`` and ``write_gen_record``.
    Delegates the serialize + fsync + atomic-rename sequence to the
    kernel-layer :func:`kernel.yaml_io.write_mapping_atomic` primitive, which
    every caller here already invokes with ``target_dir == canonical.parent``
    (both call sites ``mkdir`` the target directory before reaching this
    function) — asserted below so a future caller that passes a divergent
    directory fails loudly instead of silently fsyncing the wrong directory.

    Width stays 120 here (not the kernel's wider 4096 default) — deliberately,
    per the #3059 decision. The kernel default exists for writers whose
    scalars must never fragment (hashes, round-trip-sensitive frontmatter);
    retrospective.yaml is the opposite case, a git-committed document meant
    to be read directly, carrying prose fields up to 2000 chars (``Finding.note``,
    ``GenFinding.details``, proposal ``rationale``) that would otherwise land
    as one unreadable line. Wrapping at 120 keeps those fields reviewable in
    a diff or terminal; the #3057 normalizer (invoked inside
    ``write_mapping_atomic``) strips the trailing-whitespace artifact that
    wrapping produces, so the two are a deliberate pairing, not competing
    patches. ``test_atomic_write_yaml_wraps_prose_scalars_at_120_columns``
    (tests/retrospective/test_writer_atomicity.py) writes a >120-char prose
    scalar through this function and asserts it wraps with no line over 120
    columns, so it goes RED if this width is raised — do not raise it to 4096
    to "align" with the kernel default.

    Raises:
        WriterError: On any IO or serialization error.  The tempfile is
            unlinked on failure so no partial file remains.
    """
    if target_dir != canonical.parent:
        raise WriterError(
            f"target_dir {target_dir} must equal canonical.parent {canonical.parent}"
        )

    try:
        write_mapping_atomic(data, canonical, width=120)
    except OSError as exc:
        raise WriterError(f"IO error writing retrospective record: {exc}") from exc
    except Exception as exc:
        raise WriterError(f"Unexpected error writing retrospective record: {exc}") from exc


def write_record(record: RetrospectiveRecord, *, repo_root: Path) -> Path:
    """Atomically write a retrospective record to its canonical path.

    Steps:
    1. Validate the record via a Pydantic round-trip.
    2. Compute the canonical tracked path: <feature_dir>/retrospective.yaml
       (FR-006 #1771 — kitty-specs/<slug>/, never the gitignored .kittify tree).
    3. Create the target directory if needed.
    4. Serialize and persist atomically via :func:`_atomic_write_yaml`.

    Returns the absolute canonical path that was written.

    Raises:
        WriterError: record has status='pending', validation fails, or an IO error occurs.
    """
    # Refuse pending records before doing any I/O.
    if record.status == "pending":
        raise WriterError(
            "Cannot persist a retrospective record with status='pending'. "
            "Transition to completed/skipped/failed first."
        )

    # Pydantic round-trip validation to catch any remaining issues.
    try:
        validated = RetrospectiveRecord.model_validate(record.model_dump())
    except Exception as exc:
        raise WriterError(f"Schema validation failed: {exc}") from exc

    # Canonical (tracked) path: kitty-specs/<slug>/retrospective.yaml (FR-006 #1771).
    canonical = canonical_record_path(repo_root, validated.mission.mission_slug)
    target_dir = canonical.parent

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WriterError(f"Cannot create target directory {target_dir}: {exc}") from exc

    # Convert the model to a plain dict and delegate atomic write to shared helper.
    data = validated.model_dump(mode="python")
    _atomic_write_yaml(data, canonical, target_dir)

    return canonical


# ---------------------------------------------------------------------------
# WP03: GenRetrospectiveRecord writer with error / overwrite / update modes
# ---------------------------------------------------------------------------


def _gen_record_to_dict(record: GenRetrospectiveRecord) -> dict[str, Any]:
    """Serialize a GenRetrospectiveRecord to a plain Python dict for YAML."""
    def _actor_to_dict(a: GenActor) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": a.kind, "id": a.id}
        if a.display is not None:
            d["display"] = a.display
        return d

    def _provenance_to_dict(p: GenProvenance) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": p.kind,
            "invoked_at": p.invoked_at,
            "policy_resolved_from": dict(p.policy_resolved_from),
        }
        if p.command is not None:
            d["command"] = p.command
        return d

    def _evidence_ref_to_dict(e: GenEvidenceRef) -> dict[str, Any]:
        d: dict[str, Any] = {"id": e.id, "kind": e.kind}
        if e.path is not None:
            d["path"] = e.path
        if e.range is not None:
            d["range"] = e.range
        if e.url is not None:
            d["url"] = e.url
        return d

    def _finding_to_dict(f: GenFinding) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": f.id,
            "category": f.category,
            "summary": f.summary,
            "evidence_refs": list(f.evidence_refs),
        }
        if f.details is not None:
            d["details"] = f.details
        return d

    def _proposal_to_dict(p: GenProposal) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": p.id,
            "category": p.category,
            "risk_class": p.risk_class,
            "summary": p.summary,
            "evidence_refs": list(p.evidence_refs),
            "suggested_action": p.suggested_action,
            "auto_applicable": p.auto_applicable,
        }
        if p.details is not None:
            d["details"] = p.details
        return d

    return {
        "schema_version": record.schema_version,
        "mission_id": record.mission_id,
        "mission_slug": record.mission_slug,
        "mission_number": record.mission_number,
        "friendly_name": record.friendly_name,
        "mission_type": record.mission_type,
        "target_branch": record.target_branch,
        "created_at": record.created_at,
        "created_by": _actor_to_dict(record.created_by),
        "provenance": _provenance_to_dict(record.provenance),
        "policy_source": dict(record.policy_source),
        "findings_status": record.findings_status,
        "helped": [_finding_to_dict(f) for f in record.helped],
        "not_helpful": [_finding_to_dict(f) for f in record.not_helpful],
        "gaps": [_finding_to_dict(f) for f in record.gaps],
        "proposals": [_proposal_to_dict(p) for p in record.proposals],
        "evidence_refs": [_evidence_ref_to_dict(e) for e in record.evidence_refs],
        "generator_version": record.generator_version,
        "provenance_history": [_provenance_to_dict(p) for p in record.provenance_history],
    }


def _dict_to_gen_record(data: dict[str, Any]) -> GenRetrospectiveRecord:
    """Deserialize a plain dict (from YAML) into a GenRetrospectiveRecord.

    FR-008 / #2139 triage note (OUT): the `target_branch=data.get("target_branch", "")`
    below is a dataclass-hydration default for a PERSISTED retrospective RECORD
    field, not a meta.json reader -- it mirrors GenRetrospectiveRecord's own
    schema-wide "" default (schema.py) applied identically to every other
    legacy-optional string field on this same dataclass (mission_id,
    mission_slug, friendly_name, mission_type, created_at, ...). This function
    only receives an already-loaded record dict (used by write_gen_record's
    "update" merge path); no feature_dir/repo_root is available here, and
    resolving against LIVE meta.json would silently substitute a historical
    record's field with the mission's CURRENT branch (also moot for "update"
    merges -- `_merge_gen_records` always takes `target_branch` from the NEW
    record, never `existing`). Different contract by design; not routed
    through read_target_branch_from_meta.
    """
    def _dict_to_actor(d: dict[str, Any]) -> GenActor:
        return GenActor(kind=d["kind"], id=d["id"], display=d.get("display"))

    def _dict_to_provenance(d: dict[str, Any]) -> GenProvenance:
        return GenProvenance(
            kind=d["kind"],
            invoked_at=d["invoked_at"],
            policy_resolved_from=dict(d.get("policy_resolved_from", {})),
            command=d.get("command"),
        )

    def _dict_to_evidence_ref(d: dict[str, Any]) -> GenEvidenceRef:
        return GenEvidenceRef(
            id=d["id"],
            kind=d["kind"],
            path=d.get("path"),
            range=d.get("range"),
            url=d.get("url"),
        )

    def _dict_to_finding(d: dict[str, Any]) -> GenFinding:
        return GenFinding(
            id=d["id"],
            category=d["category"],
            summary=d["summary"],
            evidence_refs=list(d.get("evidence_refs", [])),
            details=d.get("details"),
        )

    def _dict_to_proposal(d: dict[str, Any]) -> GenProposal:
        return GenProposal(
            id=d["id"],
            category=d["category"],
            risk_class=d["risk_class"],
            summary=d["summary"],
            evidence_refs=list(d.get("evidence_refs", [])),
            suggested_action=d["suggested_action"],
            auto_applicable=d["auto_applicable"],
            details=d.get("details"),
        )

    return GenRetrospectiveRecord(
        schema_version=data.get("schema_version", 1),
        mission_id=data.get("mission_id", ""),
        mission_slug=data.get("mission_slug", ""),
        mission_number=data.get("mission_number"),
        friendly_name=data.get("friendly_name", ""),
        mission_type=read_mission_type(data) or "",  # rc3 M5 (FR-001): shared reader parity
        target_branch=data.get("target_branch", ""),
        created_at=data.get("created_at", ""),
        created_by=_dict_to_actor(data.get("created_by", {"kind": "runtime", "id": "unknown"})),
        provenance=_dict_to_provenance(data.get("provenance", {"kind": "runtime_post_completion", "invoked_at": ""})),
        policy_source=dict(data.get("policy_source", {})),
        findings_status=data.get("findings_status", "ran_no_findings"),
        helped=[_dict_to_finding(f) for f in data.get("helped", [])],
        not_helpful=[_dict_to_finding(f) for f in data.get("not_helpful", [])],
        gaps=[_dict_to_finding(f) for f in data.get("gaps", [])],
        proposals=[_dict_to_proposal(p) for p in data.get("proposals", [])],
        evidence_refs=[_dict_to_evidence_ref(e) for e in data.get("evidence_refs", [])],
        generator_version=data.get("generator_version", ""),
        provenance_history=[_dict_to_provenance(p) for p in data.get("provenance_history", [])],
    )


def _merge_gen_records(existing: GenRetrospectiveRecord, new: GenRetrospectiveRecord) -> GenRetrospectiveRecord:
    """Merge two GenRetrospectiveRecords per data-model.md merge semantics.

    Rules:
    - helped / not_helpful / gaps / proposals: deduplicate by (category, summary.lower()).
      New entries append with their original ids (caller is responsible for uniqueness).
    - evidence_refs: deduplicate by (kind, path, range, url). New entries append.
    - policy_source: replaced wholesale with new.
    - provenance: new becomes active; prior prepended to provenance_history.
    - findings_status: recomputed from final lists.
    """
    # Deduplicate findings by (category, summary.lower())
    def _merge_findings(old: list[GenFinding], new_items: list[GenFinding]) -> list[GenFinding]:
        seen: set[tuple[str, str]] = {(f.category, f.summary.lower()) for f in old}
        merged = list(old)
        for f in new_items:
            key = (f.category, f.summary.lower())
            if key not in seen:
                seen.add(key)
                merged.append(f)
        return merged

    # Deduplicate proposals by (category, summary.lower())
    def _merge_proposals(old: list[GenProposal], new_items: list[GenProposal]) -> list[GenProposal]:
        seen: set[tuple[str, str]] = {(p.category, p.summary.lower()) for p in old}
        merged = list(old)
        for p in new_items:
            key = (p.category, p.summary.lower())
            if key not in seen:
                seen.add(key)
                merged.append(p)
        return merged

    # Deduplicate evidence_refs by (kind, path, range, url)
    def _evidence_key(e: GenEvidenceRef) -> tuple[str, str | None, str | None, str | None]:
        return (e.kind, e.path, e.range, e.url)

    existing_ev_keys: set[tuple[str, str | None, str | None, str | None]] = {_evidence_key(e) for e in existing.evidence_refs}
    merged_evidence = list(existing.evidence_refs)
    for e in new.evidence_refs:
        if _evidence_key(e) not in existing_ev_keys:
            existing_ev_keys.add(_evidence_key(e))
            merged_evidence.append(e)

    merged_helped = _merge_findings(existing.helped, new.helped)
    merged_not_helpful = _merge_findings(existing.not_helpful, new.not_helpful)
    merged_gaps = _merge_findings(existing.gaps, new.gaps)
    merged_proposals = _merge_proposals(existing.proposals, new.proposals)

    # Recompute findings_status from final lists.
    has_any = bool(merged_helped or merged_not_helpful or merged_gaps or merged_proposals)
    findings_status: Literal["has_findings", "ran_no_findings"] = "has_findings" if has_any else "ran_no_findings"

    # Provenance: new replaces existing; existing prepended to history.
    new_history = [existing.provenance] + list(existing.provenance_history)

    return dataclasses.replace(
        new,
        helped=merged_helped,
        not_helpful=merged_not_helpful,
        gaps=merged_gaps,
        proposals=merged_proposals,
        evidence_refs=merged_evidence,
        findings_status=findings_status,
        provenance_history=new_history,
    )


def write_gen_record(
    record: GenRetrospectiveRecord,
    *,
    mode: Literal["error", "overwrite", "update"],
    repo_root: Path,
) -> Path:
    """Atomically write a generator record to its canonical path with three modes.

    Canonical tracked path: <feature_dir>/retrospective.yaml — i.e.
    ``kitty-specs/<mission_slug>/retrospective.yaml`` (FR-006 #1771). Never the
    gitignored ``.kittify/missions/`` tree.

    Args:
        record: The generator record to persist.
        mode: Write mode:
            "error"     — raise RecordExistsError if canonical path exists.
            "overwrite" — replace wholesale regardless of prior record.
            "update"    — merge with existing record per data-model.md merge semantics.
        repo_root: Root of the spec-kitty project.

    Returns:
        The absolute canonical path that was written.

    Raises:
        RecordExistsError: mode="error" and canonical path already exists.
        RecordValidationError: Record violates invariants (including
            synthesize_fabricate ⇒ ran_no_findings).
        WriterError: IO error during write.
    """
    # Run validate_record for schema invariants (WP02).
    validate_record(record)

    # T014 defense-in-depth: reject synthesize_fabricate with findings.
    # Note: validate_record() (above) already enforces this invariant.  This
    # secondary guard is a belt-and-suspenders safety net for callers that
    # bypass the schema-level check.  Mark it no-cover so coverage tooling
    # does not demand a redundant test.
    if (  # pragma: no cover
        record.provenance.kind == "synthesize_fabricate"
        and record.findings_status != "ran_no_findings"
    ):
        raise RecordValidationError(  # pragma: no cover
            violation="synthesize_fabricate_findings_status_mismatch",
            detail=(
                "synthesize_fabricate provenance MUST imply findings_status=ran_no_findings; "
                f"got findings_status={record.findings_status!r}. "
                "See data-model.md invariants."
            ),
        )

    if not record.mission_slug:
        raise WriterError("record.mission_slug must be non-empty to determine canonical path")

    # Canonical (tracked) path: kitty-specs/<slug>/retrospective.yaml (FR-006 #1771).
    canonical = canonical_record_path(repo_root, record.mission_slug)
    target_dir = canonical.parent
    # Back-compat: a record authored before relocation lives at the legacy
    # gitignored path. error/update modes must treat it as the prior record.
    legacy = _legacy_record_path(repo_root, record.mission_id) if record.mission_id else None
    legacy_prior = legacy if legacy and legacy.exists() else None
    prior = canonical if canonical.exists() else legacy_prior

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WriterError(f"Cannot create target directory {target_dir}: {exc}") from exc

    if mode == "error":
        if prior is not None:
            raise RecordExistsError(prior)
        final_record = record

    elif mode == "overwrite":
        final_record = record

    elif mode == "update":
        if prior is not None:
            # Load and validate the existing record (tracked or legacy path).
            yaml_safe = YAML(typ="safe")
            try:
                raw_text = prior.read_text(encoding="utf-8")
                existing_data = yaml_safe.load(raw_text)
            except Exception as exc:
                raise WriterError(
                    f"Cannot load existing record at {prior} for merge: {exc}"
                ) from exc

            if not isinstance(existing_data, dict):
                raise WriterError(
                    f"Existing record at {prior} is not a YAML mapping"
                )

            try:
                existing = _dict_to_gen_record(existing_data)
                validate_record(existing)
            except RecordValidationError as exc:
                raise WriterError(
                    f"Existing record at {prior} fails validation: {exc}"
                ) from exc

            final_record = _merge_gen_records(existing, record)
            # Re-validate merged record.
            validate_record(final_record)
        else:
            # No existing record; behave like "error" mode (first write).
            final_record = record

    else:
        raise WriterError(f"Unknown write mode {mode!r}; expected 'error', 'overwrite', or 'update'")

    data = _gen_record_to_dict(final_record)
    _atomic_write_yaml(data, canonical, target_dir)

    return canonical
