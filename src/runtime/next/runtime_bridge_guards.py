"""CLI guard facts and the WP-advance guard of the runtime bridge (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved this cluster out of
``runtime_bridge.py`` verbatim, so the io and composition seams can read it
without reaching back into the bridge:

* the planning-surface guard facts ``runtime_bridge_io.gather_artifact_presence``
  reads (``_check_requirement_mapping_ready``,
  ``_check_bare_prose_requirements_ready``, ``_occurrence_gate_failures``,
  ``_has_raw_dependencies_field``) with their helpers
  (``_load_wps_manifest_findings``, ``_log_requirement_extraction_warnings``,
  ``_log_requirement_extraction_warnings_safely``) and the ``SPEC_ARTIFACT`` /
  ``TASKS_ARTIFACT`` file names;
* the WP-advance guard ``_should_advance_wp_step`` (with ``_wp_blocks_step``)
  that the bridge's CLI guards, its dependency gate and the composition seam's
  composed-action guard consult.

``_check_cli_guards`` stays in the bridge: it composes these facts with io's
artifact-presence fact port for the advance path.

Import rule (pinned by ``tests/runtime/test_runtime_bridge_query_seam_layout.py``):
this module imports ``runtime_bridge_cores`` and ``runtime_bridge_decision_mapping``
and never the bridge, io, composition or the engine adapter, so io and
composition import it at their top level.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from mission_runtime import OwnedCheckout
from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_decision_mapping as _mapping
from specify_cli.status import Lane, wp_state_for
from specify_cli.status_lanes import is_acceptable_ending

logger = logging.getLogger(__name__)


def _should_advance_wp_step(
    step_id: str,
    feature_dir: Path,
    *,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
    owned: OwnedCheckout | None = None,
) -> bool:
    """Check if all WPs are done for this phase, meaning we should advance.

    For implement: all WPs must be handed off, accepted, done, or reach an
    acceptable ending (operator-canceled).
    For review: all WPs must be approved, done, or canceled-with-operator-
    provenance (#3780, D2/D6/D11).

    Routes through WP01's :func:`committed_authority.wp_ending` — a single
    status reduction per WP that yields lane AND operator-provenance in one
    read (C-004), fronted by the same explicit fail-loud event-log gate
    ``get_wp_lane`` used (C-003/D6): a genuinely-absent committed status log
    still raises ``CanonicalStatusNotFoundError`` here, never a silent
    ``False``.

    FR-009 (#3884): when the caller opts in by supplying ``repo_root`` (no
    separate flag, mirroring the #3704 precedent), the ``tasks/`` directory
    this function reads is anchored via ``mission_runtime.placement_seam``'s
    PRIMARY-partition resolution for ``MissionArtifactKind.WORK_PACKAGE_TASK``
    instead of the raw ``feature_dir`` -- a coord-topology mission's
    coordination-worktree ``feature_dir`` never receives ``tasks/WP*.md``
    (a PRIMARY-partition artifact), so the unanchored read hit this
    function's own no-``tasks/``-dir early return below and skipped the
    per-WP loop entirely, regardless of whether FR-004's disjunct exists. Any
    coord-less topology (``SINGLE_BRANCH``/``LANES``) -- where ``feature_dir``
    already IS the primary directory -- sees no behavior change: the anchor
    resolves to the same directory for both. May raise ``MissionSelectorAmbiguous`` for a genuinely
    ambiguous ``mission_slug`` handle -- caught at this function's one real
    call site (``_dn_dependency_gate``, FR-010).
    """
    anchor_dir = feature_dir
    if repo_root is not None:
        from mission_runtime import MissionArtifactKind, placement_seam

        # Fail closed on a missing handle rather than silently falling back to
        # ``feature_dir.name`` (#3981): at this call ``feature_dir`` is a
        # coord-worktree / status dir whose ``.name`` is NOT a kitty-specs
        # mission handle, so the old fallback would feed a wrong (and possibly
        # ambiguous) handle into ``placement_seam``. Matches this function's own
        # no-silent-fallback stance on ``MissionSelectorAmbiguous`` (C-009): a
        # caller that anchors (``repo_root=``) must name the mission explicitly.
        if mission_slug is None:
            raise ValueError("_should_advance_wp_step: mission_slug is required when repo_root is supplied (anchoring); feature_dir.name is not a mission handle.")
        anchor_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

    tasks_dir = anchor_dir / "tasks"
    # A file-based WP count cannot distinguish an empty pre-finalize board
    # from finalized lane state whose canonical task file disappeared. Keep
    # the run in its WP step so the board selector can emit the canonical
    # task-read error instead of advancing through composition.
    # ``mission_slug is not None`` always holds here (the anchoring branch above
    # raises otherwise); spelled out so the type checker sees it (#2560).
    if repo_root is not None and mission_slug is not None and _mapping._wp_task_surface_error(anchor_dir, feature_dir, mission_slug) is not None:
        return False

    if not tasks_dir.is_dir():
        return True  # no WPs to iterate over

    wp_files = sorted(tasks_dir.glob(_mapping.TASKS_GLOB))
    if not wp_files:
        return True

    from runtime.next import committed_authority
    from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

    for wp_file in wp_files:
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        wp_id = wp_match.group(1) if wp_match else wp_file.stem
        ending = committed_authority.wp_ending(feature_dir, wp_id)
        try:
            state = wp_state_for(ending.lane)
        except ValueError:
            # A lane string outside _STATE_MAP (a genuinely-unknown / malformed
            # value -- note "uninitialized" and "genesis" ARE in _STATE_MAP and
            # are handled by _wp_blocks_step's disjunct, not here). Treat an
            # unknown lane as not-yet-handed-off, so this WP blocks advancement.
            return False
        has_provenance = ending.reason_source == OPERATOR_REASON_SOURCE
        if _wp_blocks_step(step_id, state, has_provenance=has_provenance):
            return False

    return True


def _wp_blocks_step(step_id: str, state: Any, has_provenance: bool = False) -> bool:
    """Return whether a WP state blocks advancement for ``step_id``.

    ``has_provenance`` (#3780, defaulted so the single caller above stays the
    only 3-arg call site) is folded through the shipped
    :func:`specify_cli.status_lanes.is_acceptable_ending` authority for the
    ``review`` branch (D2/C-001): approved/done are unconditionally
    acceptable; canceled is acceptable only with operator-authored
    provenance (synthetic cancellations stay fail-closed); every other lane
    still blocks. The ``implement`` branch is unchanged — a canceled WP is
    never run-affecting there regardless of provenance.
    """
    lane = state.lane
    if is_acceptable_ending(
        str(lane),
        has_provenance=has_provenance,
    ):
        return False
    if step_id == "implement":
        # Advance past implement only when the WP has been handed off
        # (for_review or approved) or reaches an acceptable ending.
        # is_run_affecting is True for all active lanes; we further restrict
        # to only allow advancement for the "handed off" active lanes.
        # FR-004 (#3884): the two NON_DISPLAY_LANES -- Lane.UNINITIALIZED and
        # Lane.GENESIS -- are neither is_blocked nor is_run_affecting (neither
        # ever entered an active lane), so both fell through the run-affecting
        # disjunct and silently did not block. A WP that was never claimed
        # (UNINITIALIZED) or never lifecycled past creation (GENESIS) must not
        # be conflated with a genuinely-exempt handed-off state -- either one
        # is pending work that has to block the implement -> review advance.
        return lane in (Lane.UNINITIALIZED, Lane.GENESIS) or state.is_blocked or (state.is_run_affecting and lane not in (Lane.FOR_REVIEW, Lane.APPROVED))
    if step_id == "review":
        return not is_acceptable_ending(str(lane), has_provenance=has_provenance)
    return False


SPEC_ARTIFACT = "spec.md"


TASKS_ARTIFACT = "tasks.md"


def _occurrence_gate_failures(feature_dir: Path) -> list[str]:
    """Bulk-edit occurrence-map gate errors (empty when not bulk_edit or map is valid).

    Reuses the existing ``ensure_occurrence_classification_ready`` enforcement
    (C-001: no new validation logic). Self-conditions on stored ``change_mode``
    (C-003), so it is safe to call unconditionally at the tasks_finalize
    boundary — non-bulk-edit missions and valid-admissible bulk-edit missions
    both return an empty list.
    """
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready

    return list(ensure_occurrence_classification_ready(feature_dir).errors)


def _log_requirement_extraction_warnings(feature_dir: Path, warnings: list[str]) -> None:
    """#3394 F1 advisory, folded into this path's diagnostics too.

    :func:`specify_cli.requirement_mapping.find_undeclared_requirement_citations`
    was originally wired into ``finalize-tasks``/``map-requirements`` only;
    this path (``spec-kitty next``'s requirement-mapping preflight) got
    nothing, so an operator whose spec.md cites requirement-shaped tokens in
    an undeclared shape had no "why" surfaced here. Logged (never appended to
    the returned failures list), so it stays purely advisory: a log line,
    never a guard failure.
    """
    for warning in warnings:
        logger.warning("[%s] %s", feature_dir.name, warning)


def _log_requirement_extraction_warnings_safely(feature_dir: Path, spec_content: str) -> None:
    """Compute and log the #3394 F1 advisory without ever gating on it.

    #3394 focused-review F3 (severity 2): the advisory call used to sit
    directly inside ``_check_requirement_mapping_ready``'s broad
    ``except Exception``, which exists to fail-closed on genuine extraction
    crashes (``parse_requirement_ids_from_spec_md``, the WPs manifest load,
    the tasks.md ref parse). That means an exception raised by the advisory
    *computation* itself -- not its content, which is never appended to the
    returned failures -- would propagate to that handler and turn into a
    "Requirement mapping preflight failed" gate failure, contradicting the
    "advisory can never gate" property. ``find_undeclared_requirement_
    citations`` is pure regex/string-splitting with no I/O and currently has
    no failure mode, so this was near-zero practical risk -- but true by
    luck of the function, not by construction. This wrapper makes it true by
    construction: any exception here is swallowed and logged at DEBUG, never
    re-raised, so it cannot reach the enclosing fail-closed handler. Scoped
    to this one call; the surrounding broad ``except Exception`` is
    untouched and still fail-closed for the other three extraction calls.
    """
    try:
        from specify_cli.requirement_mapping import find_undeclared_requirement_citations

        _log_requirement_extraction_warnings(feature_dir, find_undeclared_requirement_citations(spec_content))
    except Exception:
        logger.debug(
            "[%s] Requirement-citation advisory computation failed; skipping (non-blocking)",
            feature_dir.name,
            exc_info=True,
        )


def _load_wps_manifest_findings(feature_dir: Path) -> tuple[object | None, list[str] | None]:
    """Load ``wps.yaml`` via :func:`load_wps_manifest`, translating a corrupt
    manifest into a findings-list entry instead of a raw traceback.

    Mission cli-error-surface-seam WP07/#4746 (T026): pre-fix, a corrupt
    ``wps.yaml`` (or any of the three OTHER operations sharing
    :func:`_check_requirement_mapping_ready`'s ``try`` block) collapsed into
    the SAME indistinguishable generic string via that function's broad
    ``except Exception``. Catching :class:`WpsManifestReadError` narrowly
    here — before it can reach that broad catch — gives the corrupt-manifest
    case its own typed, actionable message while leaving the broad catch's
    fail-closed behavior for the other three operations completely
    unchanged (see the companion assertion in
    ``tests/specify_cli/test_audit_tail_readers.py``).

    This is a gather-only internal preflight, not a CLI command boundary
    (see :func:`_check_requirement_mapping_ready`'s docstring) — so a
    corrupt manifest is reported as a finding string, never re-raised.

    Returns:
        ``(manifest, None)`` on success — ``manifest`` is ``None`` when
        ``wps.yaml`` is legitimately absent (D5, the legacy-mission case
        :func:`load_wps_manifest` itself resolves to ``None``). ``(None,
        [finding])`` when ``wps.yaml`` exists but is corrupt.
    """
    from specify_cli.core.wps_manifest import WpsManifestReadError, load_wps_manifest

    try:
        return load_wps_manifest(feature_dir), None
    except WpsManifestReadError as exc:
        return None, [f"Requirement mapping preflight failed: wps.yaml is corrupt: {exc}"]


def _check_requirement_mapping_ready(feature_dir: Path) -> list[str]:
    """Validate requirement coverage before issuing the finalize-tasks prompt.

    This intentionally mirrors ``agent mission finalize-tasks`` requirement
    source precedence: WP frontmatter is primary, and ``tasks.md`` is only a
    legacy fallback when no ``wps.yaml`` manifest is present.

    Gather-only shell (#2531 WP06, T023): reads spec.md/tasks.md/the WPs
    manifest and builds a :class:`runtime_bridge_cores.RequirementMappingFacts`
    bundle; the missing/unknown/unmapped decision itself (former CC~22 tail)
    now lives in the pure :func:`runtime_bridge_cores._evaluate_requirement_
    mapping` — the ``# noqa: C901`` this function used to carry is REMOVED,
    not relocated (FR-004/NFR-002).

    Also logs any :func:`specify_cli.requirement_mapping.
    find_undeclared_requirement_citations` advisory as a non-blocking
    diagnostic -- see :func:`_log_requirement_extraction_warnings_safely` for
    the full rationale, including why its computation is isolated from this
    function's own fail-closed ``except Exception`` below.

    WP07/#4746 (T026): the ``load_wps_manifest`` call below is routed
    through :func:`_load_wps_manifest_findings`, which catches the typed
    ``WpsManifestReadError`` (mission cli-error-surface-seam WP01/WP07)
    narrowly and returns its own findings entry -- so a corrupt manifest no
    longer masquerades behind the SAME generic
    "Requirement mapping preflight failed: {exc}" string this function's
    broad ``except Exception`` below still produces, unchanged, for the
    other three operations sharing this ``try`` block
    (``spec_md.read_text``, ``parse_requirement_ids_from_spec_md``,
    ``read_all_wp_raw_requirement_refs``, and the ``tasks_md.read_text`` prose
    fallback).
    """
    spec_md = feature_dir / SPEC_ARTIFACT
    if not spec_md.exists():
        return []

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return []

    try:
        from specify_cli.requirement_mapping import (
            grammar,
            parse_requirement_ids_from_spec_md,
            read_all_wp_raw_requirement_refs,
        )

        spec_content = spec_md.read_text(encoding="utf-8")
        spec_ids = parse_requirement_ids_from_spec_md(spec_content)
        all_spec_requirement_ids = set(spec_ids["all"])
        functional_requirement_ids = set(spec_ids["functional"])

        _log_requirement_extraction_warnings_safely(feature_dir, spec_content)

        wps_manifest, manifest_findings = _load_wps_manifest_findings(feature_dir)
        if manifest_findings is not None:
            return manifest_findings
        # WP04 (C-002): the WP01 unified RAW reader, not the normalising
        # one -- classification (FR-019) needs the raw authored tokens, the
        # same source ``mission_finalize.py``'s finalize classifies, so a
        # malformed or foreign-qualified ref does not silently vanish
        # before the injected grammar's verdict table ever sees it.
        wp_requirement_refs = read_all_wp_raw_requirement_refs(tasks_dir)

        if wps_manifest is None:
            tasks_md = feature_dir / TASKS_ARTIFACT
            if tasks_md.exists():
                tasks_md_refs = _cores._parse_requirement_refs_from_tasks_md(tasks_md.read_text(encoding="utf-8"), grammar=grammar)
                for wp_id, refs in tasks_md_refs.items():
                    if refs and not wp_requirement_refs.get(wp_id):
                        wp_requirement_refs[wp_id] = refs
    except Exception as exc:
        return [f"Requirement mapping preflight failed: {exc}"]

    wp_ids = tuple(sorted(wp_file.stem.split("-", 1)[0] for wp_file in tasks_dir.glob(_mapping.TASKS_GLOB)))
    facts = _cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset(all_spec_requirement_ids),
        functional_requirement_ids=frozenset(functional_requirement_ids),
        wp_ids=wp_ids,
        wp_requirement_refs={wp_id: tuple(refs) for wp_id, refs in wp_requirement_refs.items()},
        feature_dir_name=feature_dir.name,
        grammar=grammar,
    )
    return _cores._evaluate_requirement_mapping(facts)


def _check_bare_prose_requirements_ready(feature_dir: Path) -> list[str]:
    """WP05 (#3396) T023 — gather-only residual for the bare-prose
    requirement signal (fact-port/pure-core split, mirroring
    ``_check_requirement_mapping_ready``).

    Deliberately independent of ``tasks_dir``/WP-file state (FR-002): reads
    ONLY spec.md, so the signal is available and populated in
    ``status_facts`` regardless of whether any WP file exists yet -- the
    guards (``runtime_bridge_cores.py``) read it BEFORE their own
    ``tasks_dir`` readiness checks, closing the exact dead-path shape the
    reverted ``3823f2b00`` left open.

    Fail-loud, textually separate from the advisory (Story 5 / FR-007 /
    FR-008): this does NOT route through
    ``_log_requirement_extraction_warnings_safely`` -- that wrapper's "never
    crash into a gate" contract is the opposite of this detector's "never
    silently report clean" contract. Any exception here becomes an explicit,
    non-empty, blocking failure via ``BareProseRequirementFacts.
    classification_error`` (NFR-002: silent-success prohibition) --
    mirroring ``_check_requirement_mapping_ready``'s own
    ``except Exception as exc: return [...]`` shape one function up, never
    a bare traceback and never downgraded to a log line.
    """
    spec_md = feature_dir / SPEC_ARTIFACT
    if not spec_md.exists():
        return []

    try:
        from specify_cli.requirement_mapping import find_bare_prose_requirement_ids

        spec_content = spec_md.read_text(encoding="utf-8")
        candidates = find_bare_prose_requirement_ids(spec_content)
        facts = _cores.BareProseRequirementFacts(
            flagged={candidate.section_heading: tuple(candidate.ids) for candidate in candidates},
            classification_error=None,
        )
    except Exception as exc:
        facts = _cores.BareProseRequirementFacts(
            flagged={},
            classification_error=(
                f"Bare-prose requirement detection failed to classify {feature_dir.name}'s spec.md: "
                f"{exc!r} -- treating as blocking (never silently clean, NFR-002)."
            ),
        )
    return _cores._evaluate_bare_prose_requirements(facts)


def _has_raw_dependencies_field(wp_file: Path) -> bool:
    """Check if WP file has an explicit 'dependencies' field in raw frontmatter.

    Reads raw text to avoid auto-injection by read_frontmatter().
    """
    try:
        text = wp_file.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("---", 3)
    if end == -1:
        return False
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies:"):
            return True
    return False
