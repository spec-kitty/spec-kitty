"""Pure-Python retrospective generator for Spec Kitty missions.

Reads mission artifacts from disk and produces a schema-valid GenRetrospectiveRecord.
The output is byte-deterministic given the same (mission_handle, policy, repo_root) inputs.

Source-of-truth spec: kitty-specs/retrospective-default-policy-01KS049J/spec.md
Data model:           kitty-specs/retrospective-default-policy-01KS049J/data-model.md
FR refs: FR-006, FR-007, FR-010

Design decision:
- Pure-Python; no subprocess calls.
- Missing optional artifacts are recorded as gaps entries, NOT exceptions.
- Generation MUST NOT mutate doctrine / DRG / glossary. Proposals are data only.
- findings_status values in persisted records: ONLY "has_findings" or "ran_no_findings".
  "missing" and "failed" are event-payload-only states per data-model invariants.
"""

from __future__ import annotations

from charter.activation.mission_type_key import read_mission_type
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import resolve_primary_branch
from specify_cli.core.paths import read_target_branch_from_meta
from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import resolve_mid8
import contextlib
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML as _YAML
from ruamel.yaml.error import YAMLError as _YAMLError

from specify_cli.analysis_report import VERDICT_UNKNOWN as _ANALYSIS_VERDICT_UNKNOWN
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.retrospective.schema import (
    FindingsStatus,
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
    ProvenanceKind,
    validate_record,
)
# NOTE: ``REVIEWER_SELF_APPROVAL`` and ``Lane`` are imported lazily inside the
# consuming functions rather than at module scope. This module is reached
# during ``status`` package initialization via:
#   status/__init__.py → status/models.py → retrospective/__init__.py → generator.py
# A module-level ``from specify_cli.status import ...`` or
# ``from specify_cli.status.models import ...`` would form a circular import
# against the partially-initialized status package. The lazy imports keep
# the consumers on the public facade without triggering the cycle.
# The former lazy → module-level conversion was attempted but reverted because
# Python initializes retrospective.__init__ before retrospective.schema when
# any sub-module of retrospective is imported, triggering generator.py before
# status.models finishes loading.

if TYPE_CHECKING:
    from specify_cli.retrospective.policy import RetrospectivePolicy

_LOGGER = logging.getLogger(__name__)

# Public constant: version this generator so future tooling can reason about
# field-by-field freshness.
GENERATOR_VERSION = "1.0"

# Only "flag_not_helpful" proposals are low-risk.  Everything else is structural.
# Proposal.suggested_action must start with one of these values (e.g.
# "flag_not_helpful: <term>") for risk_class to be "low".
LOW_RISK_PROPOSAL_KINDS: frozenset[str] = frozenset({"flag_not_helpful"})

# Regex to detect open clarification markers in spec.md
_NEEDS_CLARIFICATION_RE = re.compile(r"\[NEEDS CLARIFICATION:", re.IGNORECASE)

# Regex to detect FR references in WP task files
_FR_REF_RE = re.compile(r"\b(FR-\d{3,})\b")

_WP_ID_RE = re.compile(r"^\w{2,5}\d{2,3}$")

# FR-008: the absent-``data-model.md`` gap is conditional on the spec declaring
# concrete domain entities. A spec "declares domain entities" when it carries a
# populated "Key Entities" section — at least one real ``- **Name**:`` bullet, not
# the unfilled template placeholder ``- **[Entity 1]**``.
_KEY_ENTITIES_HEADING_RE = re.compile(r"^#{1,6}\s+Key Entities", re.IGNORECASE | re.MULTILINE)
_ENTITY_BULLET_RE = re.compile(r"^\s*[-*]\s+\*\*(?!\[)[^*\n]+\*\*", re.MULTILINE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)

# FR-007: tracer ingestion. A tracer entry is a numbered/bulleted item with a bold
# lead, e.g. ``1. **[implement] symptom ...**`` or ``- **symptom**``.
_TRACE_ENTRY_RE = re.compile(r"(?m)^\s*(?:\d+\.|[-*])\s+\*\*(.+?)\*\*")
# Disposition keyword markers used to route a tracer entry to a findings channel.
# Gap markers take precedence (an explicit "candidate gap" beats an otherwise-clean
# disposition).
_TRACE_GAP_MARKERS: tuple[str, ...] = (
    "candidate gap",
    "candidate-gap",
    "open (",
    "open)",
    "**open",
)
_TRACE_HELPED_MARKERS: tuple[str, ...] = (
    "no gap",
    "expected",
    "worked as designed",
    "**fixed",
    "fixed —",
    "fixed -",
)


def _spec_declares_domain_entities(spec_text: str) -> bool:
    """Return True when spec.md declares concrete domain entities (FR-008).

    Detects a populated "Key Entities" section: the heading is present AND at least
    one entity bullet carries a real name (not the ``- **[Entity 1]**`` template
    placeholder). Missions with no Key Entities section — or only unfilled
    placeholders — are treated as having no domain entities, so the absent-
    ``data-model.md`` gap is suppressed for governance/wiring missions.
    """
    if not spec_text:
        return False
    heading = _KEY_ENTITIES_HEADING_RE.search(spec_text)
    if heading is None:
        return False
    section = spec_text[heading.end():]
    next_heading = _ANY_HEADING_RE.search(section)
    if next_heading is not None:
        section = section[: next_heading.start()]
    return _ENTITY_BULLET_RE.search(section) is not None


# ---------------------------------------------------------------------------
# Mission resolution helpers
# ---------------------------------------------------------------------------


def _resolve_mission_dir(mission_handle: str, repo_root: Path) -> Path | None:
    """Resolve a mission handle to its kitty-specs directory.

    Resolution order:
    1. Exact match of handle to directory name under kitty-specs/.
    2. Partial match: handle is a prefix (e.g. slug without mission_number prefix).
    3. Match against mission_id / mid8 in meta.json.

    Returns the feature_dir Path on success, or None if not found.
    """
    specs_root = repo_root / KITTY_SPECS_DIR
    if not specs_root.exists():
        return None

    # Direct match
    candidate: Path = specs_root / mission_handle
    if candidate.exists() and candidate.is_dir():
        return candidate

    # Partial match: scan all dirs, match by slug or mission_id
    for child in sorted(specs_root.iterdir(), key=lambda p: p.name):
        child_path = Path(child)
        if not child_path.is_dir():
            continue
        # Match directory name prefix
        if child_path.name == mission_handle or child_path.name.endswith(f"-{mission_handle}"):
            return child_path
        # Match via meta.json mission_id or mission_slug.
        # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
        # malformed meta.json to {}, matching the previous try/except-continue.
        meta = load_meta_or_empty(child_path)
        if meta:
            mid = str(meta.get("mission_id", ""))
            slug = str(meta.get("mission_slug", ""))
            # SELECTOR prefix-match, not a name compose: compute the canonical
            # mid8 via the authoritative resolver and compare it to the handle
            # (FR-001). resolve_mid8 returns "" for an empty/short mission_id,
            # so an identity-less meta never spuriously matches a mid8 handle.
            candidate_mid8 = resolve_mid8(slug, mission_id=mid)
            if mid == mission_handle or candidate_mid8 == mission_handle or slug == mission_handle:
                return child_path

    return None


def _read_optional_text(path: Path) -> str | None:
    """Read a text file; return None if it does not exist."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None
    return None


def _load_events(feature_dir: Path) -> list[dict[str, Any]]:
    """Load all status events from status.events.jsonl.

    Returns a list of event dicts sorted by natural file order (append order).
    """
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _load_wp_files(feature_dir: Path) -> list[tuple[str, str]]:
    """Load tasks/WP*.md files; return sorted (filename, content) pairs."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    wp_files = sorted(tasks_dir.glob("WP*.md"), key=lambda p: p.name)
    result = []
    for wp_path in wp_files:
        with contextlib.suppress(OSError):
            result.append((wp_path.name, wp_path.read_text(encoding="utf-8")))
    return result


def _load_traces(repo_root: Path, feature_dir: Path) -> list[tuple[str, str]]:
    """Load tracer markdown files from the ``TRACER_FILE`` read surface (FR-007).

    Returns sorted ``(rel_path, text)`` pairs. Best-effort: a tracer that cannot be
    read as UTF-8 text (binary/corrupt) is skipped with a warning rather than
    crashing the generator (#2217 edge case). An empty/structureless tracer reads
    cleanly and simply contributes no findings downstream.

    coord-write-placement-closure-01KYCF83 WP02 reclassified ``traces/`` from
    PRIMARY to COORD (FR-006); this is the WP07 read-side closure (T055,
    documented leeway — this module is not WP07-owned, but the reader edit is
    a direct consequence of the read-authority routing and no other WP claims
    it). ``persist -> destroy`` (``coordination/teardown.py``) means the
    coordination worktree is still materialised when this runs, so a
    ``feature_dir / "traces"`` read anchored to the PRIMARY checkout would
    silently miss every tracer WP03's writers land on the coordination
    surface under a coord-routing topology. Routing through
    :func:`mission_runtime.placement_seam` resolves the coordination
    worktree for that case while a coord-less topology (``SINGLE_BRANCH`` /
    ``LANES``) still resolves the SAME primary ``feature_dir`` it always did
    (AH-2 — no behaviour change there). The reported ``rel`` path below stays
    primary-anchored (``kitty-specs/<slug>/traces/...``) regardless of which
    physical surface the bytes were actually read from — it is a stable
    evidence-provenance label, not a filesystem path.

    WP06 (FR-006, C-READ-1): a coord mission whose ``coordination_branch`` is
    declared in ``meta.json`` but has been deleted from git raises
    :class:`~specify_cli.coordination.surface_resolver.CoordinationBranchDeleted`
    from ``read_dir`` (a #1848 data-loss signal, elsewhere handled loudly).
    Here it is degraded to an empty trace list instead — consistent with this
    function's documented best-effort contract (FR-007 docstring above) and
    scoped to this single call site only (C-003); it must not widen to a bare
    ``Exception`` and must not touch the broader #2922 read-side set. The
    degrade is logged at ``WARNING`` (not the cutover resolver's ``DEBUG`` —
    this is evidence loss, not a benign resolver miss) naming the mission and
    the declared coordination branch, so an operator reading a retrospective
    with zero tracer evidence can grep for *why* rather than mistake it for a
    mission that genuinely had no tracer files.
    """
    from mission_runtime import (
        MissionArtifactKind,
        ReadDegradeStrategy,
        resolve_read_dir_or_degrade,
    )
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    decision = resolve_read_dir_or_degrade(
        repo_root,
        feature_dir.name,
        MissionArtifactKind.TRACER_FILE,
        strategy=ReadDegradeStrategy.ZERO_EVIDENCE,
        caught=(CoordinationBranchDeleted, StatusReadPathNotFound),
        degrade_target=feature_dir,
    )
    if decision.degraded:
        return []
    traces_dir = decision.read_dir / "traces"
    if not traces_dir.is_dir():
        return []
    result: list[tuple[str, str]] = []
    for trace_path in sorted(traces_dir.glob("*.md"), key=lambda p: p.name):
        try:
            text = trace_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _LOGGER.warning("Skipping unreadable tracer %s: %s", trace_path.name, exc)
            continue
        rel = f"kitty-specs/{feature_dir.name}/traces/{trace_path.name}"
        result.append((rel, text))
    return result


# ---------------------------------------------------------------------------
# Evidence reference helpers
# ---------------------------------------------------------------------------


def _make_evidence_counter() -> list[int]:
    return [0]


def _next_evidence_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"e-{counter[0]:03d}"


def _next_finding_id(prefix: str, counter: dict[str, list[int]]) -> str:
    """Generate stable finding ids like h-001, g-001, n-001."""
    if prefix not in counter:
        counter[prefix] = [0]
    counter[prefix][0] += 1
    return f"{prefix}-{counter[prefix][0]:03d}"


def _next_proposal_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"p-{counter[0]:03d}"


# ---------------------------------------------------------------------------
# Findings classification helpers (T009)
# ---------------------------------------------------------------------------


def _has_review_feedback(event: dict[str, Any]) -> bool:
    """Return True when a lane event carries documented review feedback."""
    # Lazy import (cycle-breaker; see module note above _LOGGER).
    from specify_cli.status import is_changes_requested

    if event.get("review_ref"):
        return True
    evidence = event.get("evidence")
    if isinstance(evidence, dict):
        review = evidence.get("review")
        if isinstance(review, dict):
            return bool(review.get("reference")) and is_changes_requested(
                review.get("verdict")
            )
    return isinstance(evidence, str) and bool(evidence.strip())


_BACKWARD_LANE_MOVES: frozenset[tuple[str, str]] = frozenset({
    ("for_review", "planned"),
    ("for_review", "in_progress"),
    ("for_review", "claimed"),
    ("in_review", "planned"),
    ("in_review", "in_progress"),
    ("in_review", "claimed"),
    ("in_progress", "planned"),
    ("in_progress", "claimed"),
    # Rejection after approval: ``approved -> planned`` / ``approved -> in_progress``
    # are documented rework edges of the lane matrix (docs/architecture/
    # status-model.md), and ``move-task --to <lane> --force`` can rewind from any
    # lane — including terminal ``done`` — so all rewinds out of ``approved`` and
    # ``done`` toward implementation lanes count as backward moves (#3687).
    ("approved", "planned"),
    ("approved", "in_progress"),
    ("approved", "claimed"),
    ("done", "planned"),
    ("done", "in_progress"),
    ("done", "claimed"),
})


def _is_backward_lane_event(event: dict[str, Any]) -> bool:
    return (event.get("from_lane", ""), event.get("to_lane", "")) in _BACKWARD_LANE_MOVES


def _is_review_rejection_event(event: dict[str, Any]) -> bool:
    """A documented reviewer-feedback rewind out of in_review or approved.

    Rewinds out of ``in_review`` are the classic rejection; rewinds out of
    ``approved`` are rejection-after-approval (a later verification pass sent
    an already-approved WP back, e.g. ``move-task --to planned --force
    --review-feedback-file <path>``).  Both count as rejections only when the
    event carries documented review feedback; feedback-free force rewinds out
    of ``approved`` are lane friction (#3687).
    """
    return (
        event.get("from_lane", "") in ("in_review", "approved")
        and event.get("to_lane", "") in ("planned", "in_progress", "claimed")
        and _has_review_feedback(event)
    )


def _is_lane_friction_event(event: dict[str, Any]) -> bool:
    return _is_backward_lane_event(event) and not _is_review_rejection_event(event)


def _detect_rejection_cycles(events: list[dict[str, Any]]) -> dict[str, int]:
    """Return a mapping of wp_id -> rejection_cycle_count.

    A rejection cycle is a documented reviewer-feedback rewind out of
    in_review or approved.  Earlier for_review rewinds and feedback-free
    force moves are lane friction, not review rejections.
    """
    rejection_counts: dict[str, int] = {}
    for event in events:
        wp_id = event.get("wp_id", "")
        if not wp_id:
            continue
        if _is_review_rejection_event(event):
            rejection_counts[wp_id] = rejection_counts.get(wp_id, 0) + 1
    return rejection_counts


def _detect_lane_friction(events: list[dict[str, Any]]) -> dict[str, int]:
    """Return backward lane moves that are not documented reviewer rejections."""
    friction_counts: dict[str, int] = {}
    for event in events:
        wp_id = event.get("wp_id", "")
        if not wp_id:
            continue
        if _is_lane_friction_event(event):
            friction_counts[wp_id] = friction_counts.get(wp_id, 0) + 1
    return friction_counts


def _detect_done_wps(events: list[dict[str, Any]]) -> set[str]:
    """Return wp_ids that reached 'done' or 'approved' state."""
    done_wps: set[str] = set()
    for event in events:
        to_lane = event.get("to_lane", "")
        wp_id = event.get("wp_id", "")
        if wp_id and to_lane in ("done", "approved"):
            done_wps.add(wp_id)
    return done_wps


# ---------------------------------------------------------------------------
# T039 / FR-010 (F-04): --force transitions, arbiter overrides, implementation cycles
# ---------------------------------------------------------------------------

# Bootstrap actors emit force=True legitimately (e.g., finalize-tasks creating
# the initial planned→planned synthetic event).  They are not "force overrides"
# in the retrospective sense and must be excluded.
_BOOTSTRAP_ACTORS: frozenset[str] = frozenset({
    "finalize-tasks",
    "bootstrap",
    "migrate",
})

# Arbiter override markers in the `note` / `reason` fields.  Case-insensitive
# substring match keeps the heuristic simple while staying generous toward
# operator phrasing.
_ARBITER_MARKERS: tuple[str, ...] = (
    "arbiter",
    "arbiter-override",
    "arbiter override",
    "override arbiter",
)


def _is_force_override_event(event: dict[str, Any]) -> bool:
    """Return True if this event is a meaningful operator-driven --force override.

    Excludes finalize-tasks / bootstrap synthetic events whose force=True is a
    structural artifact, not an override.  Also excludes no-op transitions
    (from_lane == to_lane) which carry no signal.
    """
    if not event.get("force"):
        return False
    actor = str(event.get("actor", "")).lower()
    if actor in _BOOTSTRAP_ACTORS:
        return False
    return event.get("from_lane") != event.get("to_lane")


def _detect_force_overrides(events: list[dict[str, Any]]) -> dict[str, int]:
    """Count operator-driven --force transitions per WP."""
    counts: dict[str, int] = {}
    for event in events:
        wp_id = event.get("wp_id", "")
        if not wp_id:
            continue
        if _is_force_override_event(event):
            counts[wp_id] = counts.get(wp_id, 0) + 1
    return counts


def _event_wp_id(event: dict[str, Any]) -> str:
    """Return WP id from status event top-level fields or lifecycle payload."""
    wp_id = event.get("wp_id")
    if isinstance(wp_id, str) and wp_id:
        return wp_id
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload_wp_id = payload.get("wp_id")
        if isinstance(payload_wp_id, str):
            return payload_wp_id
    return ""


def _is_reviewer_self_approval_event(event: dict[str, Any]) -> bool:
    from specify_cli.status import REVIEWER_SELF_APPROVAL

    return bool(event.get("event_type") == REVIEWER_SELF_APPROVAL)


def _detect_reviewer_self_approvals(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if not _is_reviewer_self_approval_event(event):
            continue
        wp_id = _event_wp_id(event)
        if wp_id:
            counts[wp_id] = counts.get(wp_id, 0) + 1
    return counts


def _event_note(event: dict[str, Any]) -> str:
    """Return the human-readable note/reason text from an event, lower-cased."""
    parts: list[str] = []
    reason = event.get("reason")
    if isinstance(reason, str) and reason.strip():
        parts.append(reason)
    evidence = event.get("evidence")
    if isinstance(evidence, dict):
        for key in ("note", "reason"):
            value = evidence.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return " ".join(parts).lower()


def _is_arbiter_event(event: dict[str, Any]) -> bool:
    """Return True if event note/reason contains an arbiter override marker."""
    note = _event_note(event)
    if not note:
        return False
    return any(marker in note for marker in _ARBITER_MARKERS)


def _arbiter_override_signature(event: dict[str, Any]) -> str:
    """Grouping key for arbiter-override events: the text one invocation shares.

    ``move-task`` emits one event per lane hop and every hop of a single
    invocation carries the same operator ``reason`` (bound once, passed
    unchanged per hop), so the reason identifies the decision, not the hop
    (#3793). Events matched only through their evidence (no top-level
    reason) group on the evidence text instead.
    """
    reason = event.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip().lower()
    return _event_note(event)


def _detect_arbiter_overrides(events: list[dict[str, Any]]) -> dict[str, int]:
    """Count arbiter-override decisions per WP.

    Matching events are grouped by ``(wp_id, signature)`` where the signature
    is the operator reason one ``move-task`` invocation shares across all its
    lane hops — counting raw events would count hops, not overrides (#3793).
    """
    groups: set[tuple[str, str]] = set()
    for event in events:
        wp_id = event.get("wp_id", "")
        if not wp_id:
            continue
        if _is_arbiter_event(event):
            groups.add((wp_id, _arbiter_override_signature(event)))
    counts: dict[str, int] = {}
    for wp_id, _signature in groups:
        counts[wp_id] = counts.get(wp_id, 0) + 1
    return counts


def _detect_implementation_cycles(events: list[dict[str, Any]]) -> dict[str, int]:
    """Count distinct planned→in_progress (or claimed→in_progress) cycles per WP.

    A WP that needs >1 implementation cycle indicates rework that didn't
    surface as a documented review rejection.  Bootstrap and synthetic
    transitions are excluded.
    """
    from specify_cli.status import Lane as _Lane  # cycle-breaker; see module note
    counts: dict[str, int] = {}
    for event in events:
        wp_id = event.get("wp_id", "")
        if not wp_id:
            continue
        actor = str(event.get("actor", "")).lower()
        if actor in _BOOTSTRAP_ACTORS:
            continue
        from_lane = event.get("from_lane", "")
        to_lane = event.get("to_lane", "")
        if from_lane in (_Lane.PLANNED, _Lane.CLAIMED) and to_lane == _Lane.IN_PROGRESS:
            counts[wp_id] = counts.get(wp_id, 0) + 1
    # Only WPs with MORE THAN ONE cycle are interesting (the first cycle is normal).
    return {wp: n for wp, n in counts.items() if n > 1}


def _collect_fr_references(wp_files: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Return mapping of FR-id -> set of WP filenames that reference it."""
    fr_to_wps: dict[str, set[str]] = {}
    for filename, content in wp_files:
        for fr_id in _FR_REF_RE.findall(content):
            if fr_id not in fr_to_wps:
                fr_to_wps[fr_id] = set()
            fr_to_wps[fr_id].add(filename)
    return fr_to_wps


def _find_unmapped_frs(spec_text: str, fr_to_wps: dict[str, set[str]]) -> list[str]:
    """Find FR ids mentioned in spec.md but not referenced in any WP task file."""
    spec_frs = set(_FR_REF_RE.findall(spec_text))
    return sorted(fr for fr in spec_frs if fr not in fr_to_wps)


def _classify_risk(suggested_action: str) -> tuple[str, bool]:
    """Return (risk_class, auto_applicable) for a proposal suggested_action.

    risk_class is "low" if the suggested_action starts with a LOW_RISK_PROPOSAL_KINDS
    marker (e.g. "flag_not_helpful: <term>"); otherwise "structural".
    auto_applicable is always False at generation time — the runtime/CLI sets it
    based on policy.permissions.apply_low_risk_changes at apply time.
    """
    action_prefix = suggested_action.split(":")[0].strip().lower()
    if action_prefix in LOW_RISK_PROPOSAL_KINDS:
        return "low", False
    return "structural", False


def _event_id_range_for(
    events: list[dict[str, Any]],
    wp_id: str,
    predicate: Any,
) -> str:
    """Return ``first..last`` (or single id) for events matching ``predicate`` on a WP."""
    ids = [
        str(ev.get("event_id", ""))
        for ev in events
        if _event_wp_id(ev) == wp_id and predicate(ev)
    ]
    if len(ids) > 1:
        return f"{ids[0]}..{ids[-1]}"
    return ids[0] if ids else ""


def _build_event_mining_findings(
    *,
    events: list[dict[str, Any]],
    events_rel: str,
    finding_id_counters: dict[str, list[int]],
    ev_reg: _EvidenceRegistry,
) -> tuple[list[GenFinding], list[GenFinding]]:
    """Build T039 / FR-010 (F-04) findings — force, arbiter, implementation cycles.

    Returns ``(not_helpful_additions, gaps_additions)``.
    """
    not_helpful: list[GenFinding] = []
    gaps: list[GenFinding] = []

    # Force overrides → not_helpful
    for wp_id, count in sorted(_detect_force_overrides(events).items()):
        range_str = _event_id_range_for(events, wp_id, _is_force_override_event)
        ev_id = ev_reg.add_event_range(events_rel, range_str or "force_override", f"force_override_{wp_id}")
        not_helpful.append(
            GenFinding(
                id=_next_finding_id("n", finding_id_counters),
                category="process",
                summary=f"{wp_id} required {count} --force override(s) during workflow",
                details=(
                    f"WP {wp_id} required {count} operator-driven --force lane transition(s). "
                    "Force overrides typically indicate the runtime guard failed or "
                    "the operator routed around it; investigate the underlying cause."
                ),
                evidence_refs=[ev_id],
            )
        )

    # Self-review fallback → not_helpful
    for wp_id, count in sorted(_detect_reviewer_self_approvals(events).items()):
        range_str = _event_id_range_for(events, wp_id, _is_reviewer_self_approval_event)
        ev_id = ev_reg.add_event_range(events_rel, range_str or "reviewer_self_approval", f"reviewer_self_approval_{wp_id}")
        matching_payloads = [
            ev.get("payload", {})
            for ev in events
            if _event_wp_id(ev) == wp_id and _is_reviewer_self_approval_event(ev)
        ]
        first_payload = matching_payloads[0] if matching_payloads and isinstance(matching_payloads[0], dict) else {}
        intended = str(first_payload.get("intended_reviewer") or "unknown")
        actor = str(first_payload.get("implementing_actor") or "unknown")
        reason = str(first_payload.get("failure_reason") or "reviewer_failed")
        not_helpful.append(
            GenFinding(
                id=_next_finding_id("n", finding_id_counters),
                category="process",
                summary=f"{wp_id} used self-review fallback instead of independent review",
                details=(
                    f"WP {wp_id} recorded {count} ReviewerSelfApproval event(s): "
                    f"{actor} self-reviewed after intended reviewer {intended} failed "
                    f"({reason}). Treat this as a review-independence gap."
                ),
                evidence_refs=[ev_id],
            )
        )

    # Arbiter overrides → gaps
    for wp_id, count in sorted(_detect_arbiter_overrides(events).items()):
        range_str = _event_id_range_for(events, wp_id, _is_arbiter_event)
        ev_id = ev_reg.add_event_range(events_rel, range_str or "arbiter", f"arbiter_{wp_id}")
        # The "recurring use" reading only holds for count > 1 — a first and
        # only override must not read as a pattern (#4065, cf. #3793 §2).
        recurring_note = (
            " Recurring use suggests the normal review path is blocked and "
            "the underlying policy/guard may need adjustment."
            if count > 1
            else ""
        )
        gaps.append(
            GenFinding(
                id=_next_finding_id("g", finding_id_counters),
                category="process",
                summary=f"Arbiter override needed for {wp_id} ({count}x)",
                details=(
                    f"WP {wp_id} required {count} arbiter override(s). Arbiter overrides "
                    f"are an escape hatch.{recurring_note}"
                ),
                evidence_refs=[ev_id],
            )
        )

    # Multi-cycle implementations → not_helpful
    for wp_id, count in sorted(_detect_implementation_cycles(events).items()):
        ev_id = ev_reg.add_event_range(events_rel, "implementation_cycles", f"impl_cycles_{wp_id}")
        not_helpful.append(
            GenFinding(
                id=_next_finding_id("n", finding_id_counters),
                category="implementation",
                summary=f"{wp_id} needed {count} implementation cycles",
                details=(
                    f"WP {wp_id} entered in_progress {count} times. Multiple implementation "
                    "cycles suggest rework not captured as a documented review rejection; "
                    "the WP scope or contract may need refinement."
                ),
                evidence_refs=[ev_id],
            )
        )

    return not_helpful, gaps


def _build_lane_friction_findings(
    *,
    events: list[dict[str, Any]],
    lane_friction_counts: dict[str, int],
    events_rel: str,
    finding_id_counters: dict[str, list[int]],
    ev_reg: _EvidenceRegistry,
) -> list[GenFinding]:
    findings: list[GenFinding] = []
    for wp_id in sorted(lane_friction_counts):
        count = lane_friction_counts[wp_id]
        friction_event_ids = [
            str(ev.get("event_id", ""))
            for ev in events
            if ev.get("wp_id") == wp_id
            and _is_lane_friction_event(ev)
        ]
        if len(friction_event_ids) > 1:
            range_str = f"{friction_event_ids[0]}..{friction_event_ids[-1]}"
        elif friction_event_ids:
            range_str = friction_event_ids[0]
        else:
            range_str = ""
        ev_id = ev_reg.add_event_range(events_rel, range_str or "lane_friction", f"lane_friction_{wp_id}")
        findings.append(
            GenFinding(
                id=_next_finding_id("n", finding_id_counters),
                category="process",
                summary=f"{wp_id} had {count} lane bounce(s) before approval",
                details=(
                    f"WP {wp_id} moved backward across workflow lanes {count} time(s) "
                    "outside the documented reviewer-feedback flow."
                ),
                evidence_refs=[ev_id],
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Evidence registry — mutable accumulator passed through generation pipeline
# ---------------------------------------------------------------------------


class _EvidenceRegistry:
    """Mutable accumulator for evidence_refs.  Keeps generate_retrospective complexity low."""

    def __init__(self) -> None:
        self._counter: list[int] = [0]
        self._map: dict[str, str] = {}
        self.refs: list[GenEvidenceRef] = []

    def add_file(self, rel_path: str) -> str:
        """Register a file as an evidence_ref; return its id (idempotent)."""
        if rel_path not in self._map:
            eid = _next_evidence_id(self._counter)
            self._map[rel_path] = eid
            self.refs.append(GenEvidenceRef(id=eid, kind="file", path=rel_path))
        return self._map[rel_path]

    def add_event_range(self, rel_path: str, range_str: str, range_key: str) -> str:
        """Register an event range as an evidence_ref; return its id (idempotent)."""
        key = f"{rel_path}:{range_key}"
        if key not in self._map:
            eid = _next_evidence_id(self._counter)
            self._map[key] = eid
            self.refs.append(GenEvidenceRef(id=eid, kind="event_range", path=rel_path, range=range_str))
        return self._map[key]


def _resolve_mission_number(raw: object) -> int | None:
    """Coerce raw meta.json mission_number to int or None."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


# ---------------------------------------------------------------------------
# Mission-local ingestor findings (T036, T037) — extracted for complexity budget
# ---------------------------------------------------------------------------


def _parse_trace_entries(text: str) -> list[tuple[str, str]]:
    """Split tracer markdown into ``(summary, body)`` entries (FR-007).

    An entry begins at a numbered/bulleted item with a bold lead and runs until the
    next such item (or end of file). The bold lead is the summary; the full span is
    the body (used for disposition classification). Content with no structured
    entries yields ``[]`` — best-effort, never raises.
    """
    matches = list(_TRACE_ENTRY_RE.finditer(text))
    entries: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        summary = match.group(1).strip()
        if not summary:
            continue
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[match.start():body_end].strip()
        entries.append((summary, body))
    return entries


def _classify_trace_disposition(body: str) -> str:
    """Route a tracer entry to a findings channel by its documented disposition.

    Returns one of ``"gap"`` / ``"helped"`` / ``"not_helpful"``. Gap markers win
    over helped markers; an entry with neither is treated as documented friction
    (not_helpful).
    """
    lowered = body.lower()
    if any(marker in lowered for marker in _TRACE_GAP_MARKERS):
        return "gap"
    if any(marker in lowered for marker in _TRACE_HELPED_MARKERS):
        return "helped"
    return "not_helpful"


def _build_trace_findings(
    *,
    traces: list[tuple[str, str]],
    finding_id_counters: dict[str, list[int]],
    ev_reg: _EvidenceRegistry,
) -> tuple[list[GenFinding], list[GenFinding], list[GenFinding]]:
    """Build ``(helped, not_helpful, gaps)`` tooling findings from tracers (FR-007).

    Each tracer entry becomes a ``tooling``-category finding routed by its
    disposition. Tracers with no structured entries contribute nothing.
    """
    helped: list[GenFinding] = []
    not_helpful: list[GenFinding] = []
    gaps: list[GenFinding] = []
    bucket: dict[str, tuple[list[GenFinding], str]] = {
        "helped": (helped, "h"),
        "not_helpful": (not_helpful, "n"),
        "gap": (gaps, "g"),
    }
    for trace_rel, text in traces:
        for summary, body in _parse_trace_entries(text):
            target, prefix = bucket[_classify_trace_disposition(body)]
            target.append(
                GenFinding(
                    id=_next_finding_id(prefix, finding_id_counters),
                    category="tooling",
                    summary=f"Tracer: {summary}"[:200],
                    details=body[:1000],
                    evidence_refs=[ev_reg.add_file(trace_rel)],
                )
            )
    return helped, not_helpful, gaps


def _parse_leading_frontmatter(text: str) -> dict[str, Any] | None:
    """Parse a report artifact's leading YAML frontmatter block, leniently.

    Both T037 artifacts persist their findings as frontmatter (written by
    ``specify_cli.analysis_report.write_analysis_report`` and
    ``cli.commands.review._report.write_review_report``). This is the
    read-path counterpart to those writers: it returns ``None`` when the text
    carries no leading ``---`` block or the block does not parse, so a caller
    can distinguish "checked and empty" from "not machine-readable" (#3793).
    """
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    closing = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing = idx
            break
    if closing == -1:
        return None
    try:
        parsed = _YAML(typ="safe").load("\n".join(lines[1:closing]))
    except _YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return dict(parsed)


def _report_findings_count(frontmatter: dict[str, Any] | None) -> int | None:
    """Finding count a report's frontmatter records, or ``None`` if unusable.

    ``analysis-report.md`` frontmatter carries a ``findings`` list;
    ``mission-review-report.md`` frontmatter carries a ``findings`` integer.
    ``None`` means no usable field was present — the caller must then report
    presence without claiming content it never checked (#3793).
    """
    if frontmatter is None:
        return None
    findings = frontmatter.get("findings")
    if isinstance(findings, list):
        return len(findings)
    if isinstance(findings, int) and not isinstance(findings, bool):
        return int(findings)
    return None


def _build_ingestor_findings(
    *,
    workflow_failures_text: str | None,
    analysis_report_text: str | None,
    review_report_text: str | None,
    workflow_failures_rel: str,
    analysis_report_rel: str,
    review_report_rel: str,
    finding_id_counters: dict[str, list[int]],
    ev_reg: _EvidenceRegistry,
    traces: list[tuple[str, str]] | None = None,
) -> tuple[list[GenFinding], list[GenFinding], list[GenFinding]]:
    """Build helped/not_helpful/gaps findings from mission-local ingestor artifacts.

    Returns (helped_additions, not_helpful_additions, gaps_additions).
    All ingestors are optional: if the file is absent (text is None) the ingestor
    is a no-op and the generator continues without raising. The tracer ingestor
    (FR-007) extends this same seam — ``traces`` feed the same finding channels as
    the workflow-failures-log / analysis-report / mission-review artifacts.
    """
    helped: list[GenFinding] = []
    not_helpful: list[GenFinding] = []
    gaps: list[GenFinding] = []

    # workflow-failures-log.md ingestor (T036)
    if workflow_failures_text is not None:
        failure_lines = [
            line.strip()
            for line in workflow_failures_text.splitlines()
            if line.strip().startswith(("- [ ] FAIL:", "### FAIL:"))
        ]
        if failure_lines:
            for failure_line in failure_lines:
                not_helpful.append(
                    GenFinding(
                        id=_next_finding_id("n", finding_id_counters),
                        category="process",
                        summary=failure_line[:200],
                        details=(
                            "Workflow failure recorded in workflow-failures-log.md. "
                            f"Entry: {failure_line}"
                        ),
                        evidence_refs=[ev_reg.add_file(workflow_failures_rel)],
                    )
                )
        else:
            # File present but no structured failure entries
            helped.append(
                GenFinding(
                    id=_next_finding_id("h", finding_id_counters),
                    category="process",
                    summary="workflow-failures-log.md present with no recorded failures",
                    details=(
                        "A workflow-failures-log.md file is present but contains no "
                        "structured failure entries (lines starting with '- [ ] FAIL:' "
                        "or '### FAIL:'). This may indicate all workflows completed cleanly."
                    ),
                    evidence_refs=[ev_reg.add_file(workflow_failures_rel)],
                )
            )

    # analysis-report.md ingestor (T037) — content-checked, not presence-only
    # (#3793). The finding must assert only what the parsed frontmatter
    # establishes; a present-but-unstructured report is reported as exactly
    # that, never as "findings".
    if analysis_report_text is not None:
        frontmatter = _parse_leading_frontmatter(analysis_report_text)
        count = _report_findings_count(frontmatter)
        verdict = frontmatter.get("verdict") if frontmatter is not None else None
        # A legacy report (no analysis-findings/v1 carrier) records
        # ``verdict: unknown`` with an empty findings list — its body may
        # still carry unstructured prose findings, so an empty list there
        # does not establish "no findings". A report with no ``verdict`` key
        # at all is in the same boat: the count may parse cleanly, but
        # without a resolved verdict this ingestor asserts nothing from it
        # (#4065) — the fallback must say that, not claim the count itself
        # was unreadable.
        if count is not None and verdict not in (None, _ANALYSIS_VERDICT_UNKNOWN):
            if count > 0:
                not_helpful.append(
                    GenFinding(
                        id=_next_finding_id("n", finding_id_counters),
                        category="doc",
                        summary=f"analysis-report.md records {count} finding(s)",
                        details=(
                            "The analysis-report.md artifact for this mission "
                            f"records {count} finding(s) in its structured "
                            "frontmatter. Review them to understand documented "
                            "issues and decisions."
                        ),
                        evidence_refs=[ev_reg.add_file(analysis_report_rel)],
                    )
                )
            else:
                helped.append(
                    GenFinding(
                        id=_next_finding_id("h", finding_id_counters),
                        category="doc",
                        summary="analysis-report.md present with no recorded findings",
                        details=(
                            "An analysis-report.md artifact is present and its "
                            "frontmatter records zero findings with a resolved "
                            "verdict — the analysis raised nothing."
                        ),
                        evidence_refs=[ev_reg.add_file(analysis_report_rel)],
                    )
                )
        elif count is not None:
            # Count parsed cleanly but the verdict is absent or the legacy
            # ``unknown`` marker — the count is machine-readable, yet not
            # assertable without a resolved verdict (#4065).
            not_helpful.append(
                GenFinding(
                    id=_next_finding_id("n", finding_id_counters),
                    category="doc",
                    summary="analysis-report.md present; findings not machine-readable",
                    details=(
                        "An analysis-report.md artifact is present for this "
                        "mission and its frontmatter carries a machine-readable "
                        "findings count, but no resolved verdict (the verdict "
                        "key is absent or records the legacy 'unknown' marker), "
                        "so the count is not asserted; review it manually."
                    ),
                    evidence_refs=[ev_reg.add_file(analysis_report_rel)],
                )
            )
        else:
            not_helpful.append(
                GenFinding(
                    id=_next_finding_id("n", finding_id_counters),
                    category="doc",
                    summary="analysis-report.md present; findings not machine-readable",
                    details=(
                        "An analysis-report.md artifact is present for this "
                        "mission, but its leading frontmatter does not carry a "
                        "machine-readable findings count; review it manually."
                    ),
                    evidence_refs=[ev_reg.add_file(analysis_report_rel)],
                )
            )

    # mission-review-report.md ingestor (T037) — content-checked, not
    # presence-only (#3793), same rule as the analysis-report ingestor above.
    if review_report_text is not None:
        review_frontmatter = _parse_leading_frontmatter(review_report_text)
        review_count = _report_findings_count(review_frontmatter)
        if review_count is not None:
            if review_count > 0:
                not_helpful.append(
                    GenFinding(
                        id=_next_finding_id("n", finding_id_counters),
                        category="review_loop",
                        summary=f"mission-review-report.md records {review_count} finding(s)",
                        details=(
                            "The mission-review-report.md artifact for this "
                            f"mission records {review_count} finding(s) in its "
                            "frontmatter. Review them to understand documented "
                            "review outcomes."
                        ),
                        evidence_refs=[ev_reg.add_file(review_report_rel)],
                    )
                )
            else:
                helped.append(
                    GenFinding(
                        id=_next_finding_id("h", finding_id_counters),
                        category="review_loop",
                        summary="mission-review-report.md present with no findings",
                        details=(
                            "A mission-review-report.md artifact is present and "
                            "its frontmatter records zero findings — the review "
                            "pass raised nothing."
                        ),
                        evidence_refs=[ev_reg.add_file(review_report_rel)],
                    )
                )
        else:
            not_helpful.append(
                GenFinding(
                    id=_next_finding_id("n", finding_id_counters),
                    category="review_loop",
                    summary="mission-review-report.md present; findings not machine-readable",
                    details=(
                        "A mission-review-report.md artifact is present for "
                        "this mission, but its leading frontmatter does not "
                        "carry a machine-readable findings count; review it "
                        "manually."
                    ),
                    evidence_refs=[ev_reg.add_file(review_report_rel)],
                )
            )

    # Tracer ingestor (T012 / FR-007) — extends this seam, same finding channels.
    trace_helped, trace_not_helpful, trace_gaps = _build_trace_findings(
        traces=traces or [],
        finding_id_counters=finding_id_counters,
        ev_reg=ev_reg,
    )
    helped.extend(trace_helped)
    not_helpful.extend(trace_not_helpful)
    gaps.extend(trace_gaps)

    return helped, not_helpful, gaps


# ---------------------------------------------------------------------------
# Findings classification (T009) — extracted to keep generate_retrospective simple
# ---------------------------------------------------------------------------


def _build_findings(
    *,
    events: list[dict[str, Any]],
    spec_text: str,
    research_text: str | None,
    data_model_text: str | None,
    workflow_failures_text: str | None,
    analysis_report_text: str | None,
    review_report_text: str | None,
    traces: list[tuple[str, str]],
    wp_files: list[tuple[str, str]],
    wp_evidence_ids: dict[str, str],
    events_rel: str,
    spec_rel: str,
    workflow_failures_rel: str,
    analysis_report_rel: str,
    review_report_rel: str,
    generate_proposals: bool,
    ev_reg: _EvidenceRegistry,
) -> tuple[list[GenFinding], list[GenFinding], list[GenFinding], list[GenProposal]]:
    """Classify events and artifacts into (helped, not_helpful, gaps, proposals).

    Extracted from generate_retrospective to keep its cyclomatic complexity within limits.
    Evidence-ref registration is done via the ev_reg accumulator.
    """
    finding_id_counters: dict[str, list[int]] = {}
    helped: list[GenFinding] = []
    not_helpful: list[GenFinding] = []
    gaps: list[GenFinding] = []
    proposals: list[GenProposal] = []

    rejection_counts = _detect_rejection_cycles(events)
    lane_friction_counts = _detect_lane_friction(events)
    impl_cycle_counts = _detect_implementation_cycles(events)
    done_wps = _detect_done_wps(events)

    # --- Helped: WPs completed without rejection cycles.
    # Notable by contrast when rejection/friction exists; always notable when
    # ingestor artifacts (workflow-failures-log, analysis-report, mission-review-report)
    # are present, because those records document concrete failures that the
    # clean WPs avoided.
    has_ingestor_content = bool(
        workflow_failures_text or analysis_report_text or review_report_text
    )
    # A WP that needed >1 implementation cycle already carries a not_helpful
    # finding; it must never also appear in helped, whatever the lane-history
    # taxonomy says (#3687 — the two detectors use different definitions of
    # "this WP had rework", and helped must lose every disagreement).
    clean_wps = [
        wp
        for wp in sorted(done_wps)
        if rejection_counts.get(wp, 0) == 0
        and lane_friction_counts.get(wp, 0) == 0
        and impl_cycle_counts.get(wp, 0) == 0
    ]
    if rejection_counts or lane_friction_counts or has_ingestor_content:
        for wp_id in clean_wps:
            wp_file_name = f"{wp_id}.md"
            if wp_file_name in wp_evidence_ids:
                ev_refs = [wp_evidence_ids[wp_file_name]]
            elif events:
                ev_refs = [ev_reg.add_file(events_rel)]
            else:
                ev_refs = []

            if ev_refs:
                helped.append(
                    GenFinding(
                        id=_next_finding_id("h", finding_id_counters),
                        category="implementation",
                        summary=f"{wp_id} completed without rejection cycles",
                        details=None,
                        evidence_refs=ev_refs,
                    )
                )

    # --- Not-helpful: WPs with ≥1 rejection cycle
    for wp_id in sorted(rejection_counts.keys()):
        count = rejection_counts[wp_id]
        range_str = _event_id_range_for(events, wp_id, _is_review_rejection_event)
        ev_id = ev_reg.add_event_range(events_rel, range_str or "rejection", f"rejection_{wp_id}")
        not_helpful.append(
            GenFinding(
                id=_next_finding_id("n", finding_id_counters),
                category="review_loop",
                summary=f"{wp_id} required {count} rejection cycle(s) before approval",
                details=(
                    f"WP {wp_id} was sent back from review/approval to an earlier "
                    f"lane {count} time(s)."
                ),
                evidence_refs=[ev_id],
            )
        )

    not_helpful.extend(
        _build_lane_friction_findings(
            events=events,
            lane_friction_counts=lane_friction_counts,
            events_rel=events_rel,
            finding_id_counters=finding_id_counters,
            ev_reg=ev_reg,
        )
    )

    # --- T039 / FR-010 (F-04): force-override, arbiter, and impl-cycle findings
    _new_not_helpful, _new_gaps = _build_event_mining_findings(
        events=events,
        events_rel=events_rel,
        finding_id_counters=finding_id_counters,
        ev_reg=ev_reg,
    )
    not_helpful.extend(_new_not_helpful)
    gaps.extend(_new_gaps)

    # --- Gaps: open [NEEDS CLARIFICATION:] markers in spec.md
    if spec_text:
        for match in _NEEDS_CLARIFICATION_RE.finditer(spec_text):
            line_num = spec_text[: match.start()].count("\n") + 1
            spec_ev_id = ev_reg.add_file(spec_rel)
            gaps.append(
                GenFinding(
                    id=_next_finding_id("g", finding_id_counters),
                    category="spec_quality",
                    summary=f"Unresolved clarification marker in spec.md (line {line_num})",
                    details=(
                        f"Found '[NEEDS CLARIFICATION:' marker at line {line_num} of spec.md. "
                        "This indicates a specification gap that was not resolved before implementation."
                    ),
                    evidence_refs=[spec_ev_id],
                )
            )

    # --- Gaps: FRs in spec.md with no WP coverage
    if spec_text and wp_files:
        fr_to_wps_map = _collect_fr_references(wp_files)
        for fr_id in _find_unmapped_frs(spec_text, fr_to_wps_map):
            spec_ev_id = ev_reg.add_file(spec_rel)
            gaps.append(
                GenFinding(
                    id=_next_finding_id("g", finding_id_counters),
                    category="spec_quality",
                    summary=f"{fr_id} defined in spec.md has no WP coverage",
                    details=(
                        f"Requirement {fr_id} appears in spec.md but is not referenced by "
                        "any work package task file. It may be unimplemented."
                    ),
                    evidence_refs=[ev_reg.add_file(spec_rel)],
                )
            )

    # --- Gaps: missing optional documentation artifacts (only when spec.md is present)
    if spec_text:
        if research_text is None:
            gaps.append(
                GenFinding(
                    id=_next_finding_id("g", finding_id_counters),
                    category="doc",
                    summary="research.md absent",
                    details=(
                        "spec.md is present but research.md is missing. "
                        "Research artifacts help future maintainers understand design decisions."
                    ),
                    evidence_refs=[ev_reg.add_file(spec_rel)],
                )
            )
        # FR-008: only flag the absent data-model when the spec declares concrete
        # domain entities. Governance/wiring missions with no Key Entities section
        # legitimately have no data model, so the gap would be a false positive.
        if data_model_text is None and _spec_declares_domain_entities(spec_text):
            gaps.append(
                GenFinding(
                    id=_next_finding_id("g", finding_id_counters),
                    category="doc",
                    summary="data-model.md absent",
                    details=(
                        "spec.md declares domain entities but data-model.md is missing. "
                        "A data model document clarifies domain entity relationships."
                    ),
                    evidence_refs=[ev_reg.add_file(spec_rel)],
                )
            )

    # --- Mission-local ingestor findings (T036, T037, T012/FR-007 tracers)
    ingestor_helped, ingestor_not_helpful, ingestor_gaps = _build_ingestor_findings(
        workflow_failures_text=workflow_failures_text,
        analysis_report_text=analysis_report_text,
        review_report_text=review_report_text,
        workflow_failures_rel=workflow_failures_rel,
        analysis_report_rel=analysis_report_rel,
        review_report_rel=review_report_rel,
        traces=traces,
        finding_id_counters=finding_id_counters,
        ev_reg=ev_reg,
    )
    helped.extend(ingestor_helped)
    not_helpful.extend(ingestor_not_helpful)
    gaps.extend(ingestor_gaps)

    # Stable sort: byte-deterministic output
    helped.sort(key=lambda f: (f.category, f.summary))
    not_helpful.sort(key=lambda f: (f.category, f.summary))
    gaps.sort(key=lambda f: (f.category, f.summary))
    if generate_proposals:
        proposals.sort(key=lambda p: (p.category, p.summary))

    return helped, not_helpful, gaps, proposals


# ---------------------------------------------------------------------------
# Main generator function (T008)
# ---------------------------------------------------------------------------


def generate_retrospective(
    mission_handle: str,
    policy: RetrospectivePolicy,
    repo_root: Path,
    *,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
    invoked_at: str | None = None,
    actor: GenActor | None = None,
    policy_source: dict[str, str] | None = None,
) -> GenRetrospectiveRecord:
    """Generate a deterministic retrospective record for the given mission.

    Reads mission artifacts in canonical order:
    meta.json → spec.md → plan.md → research.md → data-model.md
    → tasks.md → tasks/WP*.md → status.events.jsonl
    → workflow-failures-log.md → analysis-report.md → mission-review-report.md.

    Missing optional artifacts become 'gaps' entries, NOT exceptions.

    Args:
        mission_handle: The mission slug, mission_id, or directory name under kitty-specs/.
        policy:         Resolved RetrospectivePolicy (caller already resolved it).
        repo_root:      Absolute path to the project root.
        provenance_kind: Kind of provenance to record (default: runtime_post_completion).
        invoked_at:     RFC 3339 timestamp; defaults to utcnow.
        actor:          Who invoked the generator; defaults to a runtime actor.
        policy_source:  source_map from resolve_policy(); if None, uses empty dict.

    Returns:
        A validated GenRetrospectiveRecord. validate_record() is called before return.

    Raises:
        FileNotFoundError: If the mission directory cannot be resolved.
        RecordValidationError: If the generator produces an invalid record (indicates a bug).
    """
    if invoked_at is None:
        invoked_at = now_utc_iso()

    if actor is None:
        actor = GenActor(kind="runtime", id="spec-kitty-generator", display="Spec Kitty Generator")

    if policy_source is None:
        policy_source = {}

    # ------------------------------------------------------------------
    # Step 1: Resolve mission directory
    # ------------------------------------------------------------------
    feature_dir = _resolve_mission_dir(mission_handle, repo_root)
    if feature_dir is None:
        raise FileNotFoundError(
            f"Mission {mission_handle!r} not found under {repo_root / KITTY_SPECS_DIR}. "
            "Check the mission handle (slug, mission_id, or directory name)."
        )

    # ------------------------------------------------------------------
    # Step 2: Read artifacts in canonical order
    # ------------------------------------------------------------------
    meta = load_meta_or_empty(feature_dir)

    spec_text = _read_optional_text(feature_dir / "spec.md") or ""
    plan_text = _read_optional_text(feature_dir / "plan.md") or ""
    tasks_text = _read_optional_text(feature_dir / "tasks.md") or ""

    # Optional artifacts
    research_text = _read_optional_text(feature_dir / "research.md")
    data_model_text = _read_optional_text(feature_dir / "data-model.md")

    # Mission-local ingestor artifacts (T036, T037)
    workflow_failures_text = _read_optional_text(feature_dir / "workflow-failures-log.md")
    analysis_report_text = _read_optional_text(feature_dir / "analysis-report.md")
    review_report_text = _read_optional_text(feature_dir / "mission-review-report.md")

    # Tracer artifacts (T012 / FR-007): traces/*.md feed the ingestor seam.
    traces = _load_traces(repo_root, feature_dir)

    wp_files = _load_wp_files(feature_dir)
    events = _load_events(feature_dir)

    # ------------------------------------------------------------------
    # Step 3: Build evidence_refs via registry (stable, sorted order)
    # ------------------------------------------------------------------
    ev_reg = _EvidenceRegistry()
    spec_rel = f"kitty-specs/{feature_dir.name}/spec.md"
    plan_rel = f"kitty-specs/{feature_dir.name}/plan.md"
    tasks_rel = f"kitty-specs/{feature_dir.name}/tasks.md"
    events_rel = f"kitty-specs/{feature_dir.name}/status.events.jsonl"
    meta_rel = f"kitty-specs/{feature_dir.name}/meta.json"
    workflow_failures_rel = f"kitty-specs/{feature_dir.name}/workflow-failures-log.md"
    analysis_report_rel = f"kitty-specs/{feature_dir.name}/analysis-report.md"
    review_report_rel = f"kitty-specs/{feature_dir.name}/mission-review-report.md"

    if meta:
        ev_reg.add_file(meta_rel)
    if spec_text:
        ev_reg.add_file(spec_rel)
    if plan_text:
        ev_reg.add_file(plan_rel)
    if tasks_text:
        ev_reg.add_file(tasks_rel)

    wp_evidence_ids: dict[str, str] = {}
    for wp_name, _ in wp_files:
        wp_rel = f"kitty-specs/{feature_dir.name}/tasks/{wp_name}"
        wp_evidence_ids[wp_name] = ev_reg.add_file(wp_rel)

    if events:
        ev_reg.add_file(events_rel)

    # ------------------------------------------------------------------
    # Step 4: Classify findings (T009)
    # generate_proposals from policy gates whether proposals are populated.
    # ------------------------------------------------------------------
    helped, not_helpful, gaps, proposals = _build_findings(
        events=events,
        spec_text=spec_text,
        research_text=research_text,
        data_model_text=data_model_text,
        workflow_failures_text=workflow_failures_text,
        analysis_report_text=analysis_report_text,
        review_report_text=review_report_text,
        traces=traces,
        wp_files=wp_files,
        wp_evidence_ids=wp_evidence_ids,
        events_rel=events_rel,
        spec_rel=spec_rel,
        workflow_failures_rel=workflow_failures_rel,
        analysis_report_rel=analysis_report_rel,
        review_report_rel=review_report_rel,
        generate_proposals=policy.generate_proposals,
        ev_reg=ev_reg,
    )

    # ------------------------------------------------------------------
    # Step 5: findings_status resolution (T010)
    # NOTE: "missing" and "failed" are event-payload-only states and
    # MUST NOT appear in a persisted RetrospectiveRecord.
    # ------------------------------------------------------------------
    findings_status: FindingsStatus = "has_findings" if any([helped, not_helpful, gaps, proposals]) else "ran_no_findings"

    # ------------------------------------------------------------------
    # Step 6: Resolve mission identity from meta.json
    # ------------------------------------------------------------------
    mission_id = str(meta.get("mission_id") or "")
    mission_slug = str(meta.get("mission_slug") or meta.get("slug") or feature_dir.name)
    friendly_name = str(meta.get("friendly_name") or meta.get("name") or mission_slug)
    # rc3 M5 (FR-003): canonical field via the one shared reader — drop the
    # silent `software-dev` default; a typeless mission records "" (neutral).
    mission_type = read_mission_type(meta) or ""
    # FR-008 / #2139: delegate to the single read_target_branch_from_meta
    # authority instead of re-embedding a local "main" default; apply the
    # documented primary-branch fallback only when the field is genuinely
    # absent (mirrors resolve_target_branch/get_feature_target_branch).
    _target_branch = read_target_branch_from_meta(feature_dir)
    target_branch = _target_branch if _target_branch is not None else resolve_primary_branch(repo_root)
    mission_number = _resolve_mission_number(meta.get("mission_number"))

    # ------------------------------------------------------------------
    # Step 7: Assemble the record
    # ------------------------------------------------------------------
    provenance = GenProvenance(
        kind=provenance_kind,
        command=None,
        invoked_at=invoked_at,
        policy_resolved_from=dict(policy_source),
    )

    record = GenRetrospectiveRecord(
        schema_version=1,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mission_number=mission_number,
        friendly_name=friendly_name,
        mission_type=mission_type,
        target_branch=target_branch,
        created_at=invoked_at,
        created_by=actor,
        provenance=provenance,
        policy_source=dict(policy_source),
        findings_status=findings_status,
        helped=helped,
        not_helpful=not_helpful,
        gaps=gaps,
        proposals=proposals,
        evidence_refs=ev_reg.refs,
        generator_version=GENERATOR_VERSION,
        provenance_history=[],
    )

    # ------------------------------------------------------------------
    # Step 8: Validate before returning.
    # Validation failure is a generator bug — raise immediately.
    # ------------------------------------------------------------------
    validate_record(record)

    return record
