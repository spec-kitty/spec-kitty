"""Acceptance matrix — derived evidence view for feature acceptance.

The acceptance matrix is NOT an authoritative state source. The canonical
state authority remains status.events.jsonl + meta.json. This module
provides a structured evidence artifact that the acceptance gate reads
to validate evidence completeness before emitting transitions through
the existing event pipeline.

Persisted at kitty-specs/{mission_slug}/acceptance-matrix.json.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from kernel.atomic import atomic_write
from specify_cli.configured_command import ConfiguredCommandUnsupported, run_configured_command
from specify_cli.mission_metadata import mission_identity_fields, resolve_mission_identity
from specify_cli.status import BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS, mission_write_lock

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout
    from specify_cli.acceptance.execution_context import GateExecutionContext
    from specify_cli.coordination.write_seam import ProtectionPolicyLike, WriteSeamResult

_T = TypeVar("_T")

CRITERION_VERDICTS = frozenset({"pass", "fail", "pending"})

# The negative-invariant results that represent an *actual, established
# judgement* (data-model.md Result state machine). Membership in this set is the
# NI-2 preservation guard: a terminal result is never re-judged or overwritten
# (C3). ``deferred_to_consolidation`` is deliberately EXCLUDED — it is a
# scheduled-not-yet-judged state (NI-4), so freezing it here would make its
# post-consolidation verification (C6) impossible.
TERMINAL_INVARIANT_RESULTS = frozenset({"confirmed_absent", "still_present", "verification_error"})

# The fourth Result value (NI / data-model.md): a ``pending`` invariant whose
# subject cannot exist on the current surface defers here rather than reporting a
# false ``still_present`` (FR-003 / C4).
DEFERRED_TO_CONSOLIDATION = "deferred_to_consolidation"

NEGATIVE_INVARIANT_RESULTS = TERMINAL_INVARIANT_RESULTS | {"pending", DEFERRED_TO_CONSOLIDATION}

# Provenance origin vocabulary (data-model.md NI-1). ``recorded`` requires full
# provenance; ``legacy_unrecorded`` is the FR-014 sentinel for results captured
# before provenance existed and permits null provenance for THAT origin only.
# ``legacy_unrecorded`` is a ``provenance_origin`` value, NEVER a
# ``TopologySurface`` member (the surface enum's anti-phantom rule).
PROVENANCE_RECORDED = "recorded"
PROVENANCE_LEGACY_UNRECORDED = "legacy_unrecorded"
PROVENANCE_ORIGINS = frozenset({PROVENANCE_RECORDED, PROVENANCE_LEGACY_UNRECORDED})

# The fourth ``overall_verdict`` value (NI-5): deferral contributes neither a
# ``fail`` nor a silent ``pass`` — acceptance is not blocked, but the mission
# cannot reach ``done`` while any invariant is still deferred.
VERDICT_PASS_PENDING_CONSOLIDATION = "pass_pending_consolidation"  # noqa: S105  # verdict name, not a secret

# The phase name a deferred invariant is scheduled to be judged at (NI-4 / C4).
# Stored as the ``LifecyclePhase.POST_CONSOLIDATION`` member NAME (a plain string)
# so the matrix serialises without importing the phase enum into its storage.
POST_CONSOLIDATION_PHASE_NAME = "POST_CONSOLIDATION"

# Marker dropped into scaffolded criteria so operators (and reviewers) can
# tell a placeholder row apart from a real, authored acceptance criterion.
# Load-bearing in two directions (#3231): the scaffold writer
# (``scaffold_acceptance_matrix``) stamps it into an empty placeholder
# criterion's ``description``, and ``overall_verdict`` reads it back via
# :func:`_is_empty_scaffold` to exempt ONLY that contentless placeholder from
# the pending-dominates rule. A future rename must touch both call sites.
SCAFFOLD_TODO_MARKER = "TODO: replace with a real acceptance criterion"

# FR-008 (governance-at-the-gate WP04 / IC-04): the ONLY ``proof_type`` a
# criterion row is auto-populated from WP review evidence. Design decision
# (recorded here, not just in the mission's tasks.md): population is
# AUTO-DERIVED, never a hand-filled artifact (NFR-005) -- but it is scoped
# to ``code_review`` because that is the one proof type whose evidence IS
# "every tracked WP carries a durable, gate-captured review verdict" (the
# exact fact T1/T2 now record). ``automated_test``/``manual_qa`` criteria
# need their own evidence this gate cannot fabricate without lying about
# what was actually verified, and ``negative_invariant`` rows already have
# a dedicated, independent verification engine
# (:func:`enforce_negative_invariants`) -- auto-passing either from mere WP
# approval would be a fabricated verdict, not a derived one.
AUTO_DERIVABLE_PROOF_TYPES: frozenset[str] = frozenset({"code_review"})

# The auto-derivation note appended to a populated criterion's ``notes`` so an
# operator reading the matrix can tell a gate-derived row apart from one a
# reviewer hand-verified through ``agent mission acceptance-verdict``.
_AUTO_DERIVED_NOTE = "Auto-derived from WP review evidence (IC-04 gate-side capture, FR-008)."


def _is_empty_scaffold(criterion: AcceptanceCriterion) -> bool:
    """True iff ``criterion`` is the empty ``finalize-tasks`` placeholder row.

    C-003: the discriminator is ``description`` — and ONLY ``description`` —
    because that is the sole field unique to the empty placeholder written by
    ``scaffold_acceptance_matrix`` (:data:`SCAFFOLD_TODO_MARKER` docstring).
    Seeded-but-unauthored per-requirement rows carry a REAL ``description``
    (e.g. ``"Verify FR-001 is satisfied"``) and only put the marker in
    ``notes`` — discriminating on ``notes`` would false-accept those rows
    through the gate. Discriminating on ``criterion_id == "AC-001"`` would
    false-accept a genuine, still-pending, hand-authored ``AC-001``.
    """
    return criterion.description == SCAFFOLD_TODO_MARKER


def _pending_dominant_criterion_results(criteria: list[AcceptanceCriterion]) -> list[str]:
    """Criterion ``pass_fail`` values that participate in the pending-dominates check.

    An empty scaffold placeholder (:func:`_is_empty_scaffold`) is excluded
    from pending-dominates ONLY when at least one non-scaffold criterion also
    exists — a real criterion has been authored, so the leftover placeholder
    should not block acceptance. If every criterion is an empty placeholder
    (or the matrix has none), there is nothing real to accept yet, so the
    verdict must stay ``pending``: fall back to the unfiltered results.
    """
    non_scaffold = [c.pass_fail for c in criteria if not _is_empty_scaffold(c)]
    if non_scaffold:
        return non_scaffold
    return [c.pass_fail for c in criteria]


class AcceptanceMatrixParseError(ValueError):
    """Raised by :meth:`AcceptanceMatrix.from_dict` on a malformed item (T021).

    WP05 (post-merge-write-authoring-finish-01KYRRM5) / squad hardening
    (renata M2): the crash this closes is ``AcceptanceMatrix.from_dict`` ->
    ``NegativeInvariant.from_dict``/``AcceptanceCriterion.from_dict`` at load
    time (the mgifford ``accept --diagnose`` defect — a crash BEFORE
    diagnosis). ``read_acceptance_matrix``/``from_dict`` are SHARED by
    ``acceptance/gates_core.py`` and ``coordination/post_consolidation.py``,
    so ``from_dict`` deliberately does NOT drop the malformed item or decide
    an exit code itself — silently accepting a partial matrix would change
    gate behaviour (a partial matrix passing is worse than a crash). It
    raises this TYPED error instead of an unhandled ``TypeError``/``KeyError``,
    so the ONE caller equipped to report "which item, why" and choose an exit
    code — the ``accept --diagnose`` CLI layer
    (``cli/commands/accept.py::accept``) — can catch it. Every other caller
    that does not catch it still fails loudly on malformed input, exactly as
    before (gate behaviour for well-formed input, and the loud-failure
    contract for malformed input, are both unchanged).
    """

    def __init__(self, *, section: str, item_index: int, reason: str) -> None:
        self.section = section
        self.item_index = item_index
        self.reason = reason
        super().__init__(f"{section}[{item_index}]: malformed shape ({reason})")


def _parse_items(
    raw_items: list[Any],
    parser: Callable[[dict[str, Any]], _T],
    *,
    section: str,
) -> list[_T]:
    """Parse each raw dict via ``parser``, wrapping a shape failure per item (T021).

    A per-dataclass ``from_dict`` failure (missing required field, wrong
    type) surfaces as ``TypeError``/``KeyError`` from the dataclass
    constructor. This translates it into the typed, item-addressable
    :class:`AcceptanceMatrixParseError` WITHOUT dropping the item or
    continuing past it — the caller decides what "malformed" means for its
    context, this helper only makes the failure identifiable.
    """
    parsed: list[_T] = []
    for idx, raw in enumerate(raw_items):
        try:
            parsed.append(parser(raw))
        except (TypeError, KeyError) as exc:
            raise AcceptanceMatrixParseError(section=section, item_index=idx, reason=str(exc)) from exc
    return parsed


def _is_allowed_value(value: Any, allowed: frozenset[str]) -> bool:
    return isinstance(value, str) and value in allowed


# FR-004 defense-in-depth: a stray, unresolved git conflict marker left in a
# string field is a symptom of a botched merge, not an authored value. Left
# unrejected, it round-trips through ``from_dict`` and — for a field that
# feeds :attr:`AcceptanceMatrix.overall_verdict` (``pass_fail`` / ``result``)
# — silently coerces the verdict to ``"fail"`` via the existing
# out-of-domain-value branch (:func:`_is_allowed_value`), while a marker
# landing in a prose-only field (e.g. ``notes``) leaves no such signal at
# all. Either way the merge damage goes undetected. This is the read-side
# guard; the write-side guard (merge-driver conflict-marker rejection) is a
# separate module (WP01, ``consolidation/drivers.py`` since #5119).
_CONFLICT_MARKERS: tuple[str, ...] = ("<<<<<<<", "=======", ">>>>>>>")


def _reject_conflict_markers(field_name: str, value: Any, *, section: str, item_index: int, row_key: str) -> None:
    """Raise :class:`AcceptanceMatrixParseError` if ``value`` carries a raw marker.

    Only the three literal conflict-marker tokens are rejected — an
    authored, merely out-of-domain string (e.g. an unrecognized
    ``pass_fail`` value) is left alone; it still flows through
    :func:`_is_allowed_value` unchanged (C-001), so ``overall_verdict``'s
    existing out-of-domain-value handling is untouched by this guard.
    """
    if not isinstance(value, str):
        return
    for marker in _CONFLICT_MARKERS:
        if marker in value:
            raise AcceptanceMatrixParseError(
                section=section,
                item_index=item_index,
                reason=(f"field {field_name!r} on row {row_key!r} contains an unresolved conflict marker {marker!r}"),
            )


def _reject_criteria_conflict_markers(criteria: list[AcceptanceCriterion]) -> None:
    for idx, criterion in enumerate(criteria):
        for item_field in fields(criterion):
            if item_field.name == "extras":
                continue
            _reject_conflict_markers(
                item_field.name,
                getattr(criterion, item_field.name),
                section="criteria",
                item_index=idx,
                row_key=criterion.criterion_id,
            )


def _reject_invariant_conflict_markers(invariants: list[NegativeInvariant]) -> None:
    for idx, invariant in enumerate(invariants):
        for item_field in fields(invariant):
            if item_field.name == "extras":
                continue
            _reject_conflict_markers(
                item_field.name,
                getattr(invariant, item_field.name),
                section="negative_invariants",
                item_index=idx,
                row_key=invariant.invariant_id,
            )


def _split_known_fields(
    cls: type[Any],
    data: dict[str, Any],
    *,
    exclude: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    excluded = exclude or set()
    known = {f.name for f in fields(cls)} - {"extras"} - excluded
    kwargs = {key: value for key, value in data.items() if key in known}
    extras = {key: value for key, value in data.items() if key not in known and key not in excluded}
    return kwargs, extras


@dataclass
class AcceptanceCriterion:
    """A single acceptance criterion with evidence."""

    criterion_id: str
    description: str
    proof_type: str  # "automated_test" | "manual_qa" | "code_review" | "negative_invariant"
    evidence: str | None = None
    pass_fail: str = "pending"  # noqa: S105  # "pass" | "fail" | "pending"
    verified_by: str | None = None
    verified_at: str | None = None
    notes: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptanceCriterion:
        kwargs, extras = _split_known_fields(cls, data)
        return cls(**kwargs, extras=extras)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        extras = data.pop("extras", {}) or {}
        data.update(extras)
        return data


@dataclass
class NegativeInvariant:
    """A negative invariant — something that must NOT exist."""

    invariant_id: str
    description: str
    verification_method: str  # "grep_absence" | "route_check" | "custom_command"
    verification_command: str | None = None
    result: str = "pending"  # see NEGATIVE_INVARIANT_RESULTS (incl. deferred_to_consolidation)
    evidence: str | None = None
    # Optional path-scope for ``grep_absence``: whitespace-separated repo-relative
    # search root(s). When set, the grep runs only under these paths instead of
    # the whole repo, so a pattern that a mission's OWN spec/plan/WP prose
    # mentions does not false-positive as "still_present" (#1834). Default
    # (``None``) preserves the whole-repo search (unchanged behaviour).
    scope: str | None = None
    # --- Provenance (data-model.md NI-1 / contract C1-C2). A judgement states
    # the surface and ref it was established against so it is attributable and
    # never silently re-judged from a surface that cannot hold it. ---
    # The git ref the outcome was established against (null until judged).
    verified_ref: str | None = None
    # The ``TopologySurface`` value (e.g. ``"primary"`` / ``"coord"`` /
    # ``"consolidated"``) that established the outcome. Stored as the plain enum
    # VALUE, never the sentinel ``legacy_unrecorded`` (which is a
    # ``provenance_origin``, not a surface — the anti-phantom rule).
    verified_surface_kind: str | None = None
    # Why judgement was postponed, when ``result == deferred_to_consolidation``.
    deferred_reason: str | None = None
    # The ``LifecyclePhase`` NAME the deferral will be judged at (NI-4).
    deferred_to_phase: str | None = None
    # ``recorded`` requires full provenance; ``legacy_unrecorded`` (the FR-014
    # sentinel) permits null provenance for pre-schema results. The default is
    # ``legacy_unrecorded`` so an existing on-disk matrix — which predates these
    # fields — round-trips through ``validate_matrix_evidence`` unchanged (its
    # terminal results carry no provenance yet, and the FR-014 backfill has not
    # run). The gate stamps ``recorded`` explicitly when it judges an invariant.
    provenance_origin: str = PROVENANCE_LEGACY_UNRECORDED
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NegativeInvariant:
        kwargs, extras = _split_known_fields(cls, data)
        return cls(**kwargs, extras=extras)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        extras = data.pop("extras", {}) or {}
        # Omit unset optional keys so existing matrices are not rewritten with a
        # ``null`` key on their next serialization (byte-stability across the
        # ~160 tracked matrices). C2 round-trip is preserved: an omitted key
        # restores to its ``None`` default via ``from_dict``.
        for key in (
            "scope",
            "verified_ref",
            "verified_surface_kind",
            "deferred_reason",
            "deferred_to_phase",
        ):
            if data.get(key) is None:
                data.pop(key, None)
        # ``legacy_unrecorded`` is the default; omit it so pre-schema matrices
        # stay byte-stable. A ``recorded`` origin is always emitted.
        if data.get("provenance_origin") == PROVENANCE_LEGACY_UNRECORDED:
            data.pop("provenance_origin", None)
        data.update(extras)
        return data


@dataclass
class AcceptanceMatrix:
    """Complete acceptance matrix for a feature.

    This is a derived evidence view. It does NOT participate in state
    transitions. The acceptance gate reads it to validate evidence
    completeness, then emits transitions through the event pipeline.
    """

    mission_slug: str
    criteria: list[AcceptanceCriterion] = field(default_factory=list)
    negative_invariants: list[NegativeInvariant] = field(default_factory=list)
    mission_number: str | None = None
    mission_type: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_verdict(self) -> str:
        """Compute verdict from individual results."""
        criterion_results = [c.pass_fail for c in self.criteria]
        invariant_results = [ni.result for ni in self.negative_invariants]
        if not criterion_results and not invariant_results:
            return "pending"
        if any(not _is_allowed_value(v, CRITERION_VERDICTS) for v in criterion_results):
            return "fail"
        if any(not _is_allowed_value(v, NEGATIVE_INVARIANT_RESULTS) for v in invariant_results):
            return "fail"
        if any(v == "fail" for v in criterion_results):
            return "fail"
        if any(v in {"still_present", "verification_error"} for v in invariant_results):
            return "fail"
        pending_dominant_results = _pending_dominant_criterion_results(self.criteria)
        if any(v == "pending" for v in pending_dominant_results + invariant_results):
            return "pending"
        # NI-5: a deferred invariant is neither a failure nor a silent pass. It
        # yields the fourth verdict — acceptance is NOT blocked (C5), but the
        # verdict is distinguishable from a clean ``pass`` so the mission cannot
        # reach ``done`` while a deferral is outstanding. Checked AFTER ``pending``
        # so an unverified criterion still dominates.
        if any(v == DEFERRED_TO_CONSOLIDATION for v in invariant_results):
            return VERDICT_PASS_PENDING_CONSOLIDATION
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        data = {
            **mission_identity_fields(
                self.mission_slug,
                self.mission_number,
                self.mission_type,
            ),
            "overall_verdict": self.overall_verdict,
            "criteria": [c.to_dict() for c in self.criteria],
            "negative_invariants": [ni.to_dict() for ni in self.negative_invariants],
        }
        data.update(self.extras)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcceptanceMatrix:
        """Reconstruct a matrix, raising :class:`AcceptanceMatrixParseError`
        (T021) on a malformed ``criteria``/``negative_invariants`` item
        instead of an unhandled ``TypeError`` — see that class's docstring
        for why the drop/exit decision is NOT made here.
        """
        kwargs, extras = _split_known_fields(cls, data, exclude={"overall_verdict"})
        identity = mission_identity_fields(
            data["mission_slug"],
            data.get("mission_number"),
            data.get("mission_type"),
        )
        criteria = _parse_items(data.get("criteria", []), AcceptanceCriterion.from_dict, section="criteria")
        negative_invariants = _parse_items(
            data.get("negative_invariants", []),
            NegativeInvariant.from_dict,
            section="negative_invariants",
        )
        _reject_criteria_conflict_markers(criteria)
        _reject_invariant_conflict_markers(negative_invariants)
        return cls(
            mission_slug=identity["mission_slug"],
            criteria=criteria,
            negative_invariants=negative_invariants,
            mission_number=kwargs.get("mission_number", identity["mission_number"]),
            mission_type=kwargs.get("mission_type", identity["mission_type"]),
            extras=extras,
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

MATRIX_FILENAME = "acceptance-matrix.json"


def write_acceptance_matrix(feature_dir: Path, matrix: AcceptanceMatrix) -> Path:
    """Write acceptance-matrix.json to the feature directory.

    #4858 (C-003/FR-009/NFR-004): routes through :func:`kernel.atomic.
    atomic_write` (tempfile-write + rename in ``feature_dir``) instead of a
    bare ``path.write_text`` — no reader can ever observe a torn/partial
    file. This is the ONE shared writer every acceptance-matrix caller
    (the verdict command, the scaffold, the accept residual sweep, ...)
    goes through, so every one of them benefits.
    """
    if (feature_dir / "meta.json").exists():
        identity = resolve_mission_identity(feature_dir)
        matrix.mission_slug = identity.mission_slug
        matrix.mission_number = str(identity.mission_number) if identity.mission_number is not None else None
        matrix.mission_type = identity.mission_type
    path = feature_dir / MATRIX_FILENAME
    atomic_write(path, json.dumps(matrix.to_dict(), indent=2) + "\n")
    return path


def write_and_commit_acceptance_matrix(
    repo_root: Path,
    mission_slug: str,
    matrix_dir: Path,
    matrix: AcceptanceMatrix,
    *,
    entry_id: str,
    message: str,
    policy: ProtectionPolicyLike | None = None,
    owned: OwnedCheckout | None = None,
) -> WriteSeamResult:
    """Write ``acceptance-matrix.json`` and commit it through the WP03 write seam.

    WP04 / T015 / T017 (write-side-seam-matrix-tracer-01KYP3MH,
    ``contracts/write-seam-adoption.md``): composes the unchanged raw writer
    (:func:`write_acceptance_matrix` — kept byte-identical for the many
    fixture call sites that write straight to a ``tmp_path`` with no git repo
    at all) with :func:`specify_cli.coordination.write_seam.write_artifact`
    (FR-007 core / FR-011 zero-write refusal / FR-012 idempotence): the bytes
    land on disk exactly as before, then the WP03 seam resolves the
    kind-aware commit target and materialises the commit, replacing a
    hand-derived "write now, rely on a separate later commit sweep to find
    the dirt" two-step with one routed call.

    Deliberately NOT used by ``acceptance/gates_core.py``'s
    ``_evaluate_acceptance_matrix``: the ``--no-commit`` / ``--diagnose``
    accept legs (#1883 / #1908) may MUTATE this accept-owned file but must
    NEVER commit anything — see
    ``tests/specify_cli/test_accept_no_commit_readonly.py::
    test_accept_no_commit_via_cli_converges_and_leaves_tree_clean`` (asserts
    HEAD is unchanged). That call site keeps calling
    :func:`write_acceptance_matrix` directly; the real accept-commit path
    picks the resulting dirt up via ``cli/commands/accept.py``'s residual
    sweep, itself routed through this same seam.

    WP05 (post-merge-write-authoring-finish-01KYRRM5) / T024 (#3073 no-residue
    thunk): the on-disk write now happens INSIDE a ``stage=`` thunk passed to
    :func:`~specify_cli.coordination.write_seam.write_artifact`, not
    eagerly before it — mirrors ``retrospective/tracer_writer.py``'s WP04/T015
    migration (the write-seam module docstring names this call site as one of
    exactly three ``stage=`` migration candidates). ``write_artifact`` invokes
    the thunk ONLY after its routability probe succeeds, so a refused write
    (unroutable mission, off-checkout) never touches disk and leaves zero
    untracked residue.
    """
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination.write_seam import write_artifact
    from specify_cli.git.protection_policy import ProtectionPolicy

    resolved_policy = policy if policy is not None else ProtectionPolicy.resolve(repo_root)
    matrix_path = matrix_dir / MATRIX_FILENAME

    def _stage() -> tuple[Path, ...]:
        return (write_acceptance_matrix(matrix_dir, matrix),)

    return write_artifact(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        stage=_stage,
        message=message,
        policy=resolved_policy,
        entry_id=entry_id,
        # WP10 (T057/B4, cycle 2 correction): when ``matrix_dir`` is the
        # OWNING write location (``write_dir(ACCEPTANCE_MATRIX)`` for
        # ``acceptance_verdict.py``'s two commit=True legs; the already-
        # resolved declared/write ``home`` for ``scaffold_acceptance_matrix``
        # below, on a MATERIALIZED coordination Mission), the write lands IN
        # PLACE under the coordination worktree and this entry is never
        # matched by ``_cleanup_staging_residue`` (no COPY ever happens for
        # an already-in-place source -- see ``commit_router
        # ._classify_stage_path``'s IN_PLACE branch). Kept (not emptied)
        # because ``scaffold_acceptance_matrix`` can still legitimately stage
        # at the PRIMARY ``feature_dir`` for a pre-materialization EMPTY
        # coordination Mission (AH-2's declared-read fallback for ``home``) --
        # that case still relies on this residue-cleanup eligibility once the
        # router's on-demand copy confirms the coordination surface holds a
        # byte-identical copy. WP16's accept-residual leg and WP20's router
        # flip are the only other callers this frozenset still serves.
        primary_paths_created_this_invocation=frozenset({matrix_path}),
        owned=owned,
    )


def read_acceptance_matrix(feature_dir: Path) -> AcceptanceMatrix | None:
    """Read acceptance-matrix.json. Returns None if absent."""
    path = feature_dir / MATRIX_FILENAME
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AcceptanceMatrix.from_dict(data)


def locked_reread_splice_and_write(
    *,
    repo_root: Path,
    mission_slug: str,
    matrix_dir: Path,
    splice: Callable[[AcceptanceMatrix], None],
    commit: bool,
    entry_id: str | None = None,
    message: str | None = None,
    timeout: float | None = None,
) -> tuple[AcceptanceMatrix, WriteSeamResult | Path]:
    """The ONE locked read-modify-write critical section for the acceptance matrix.

    Lifted from the #4858 verdict-command-private
    ``_locked_reread_splice_and_write`` (#4887/FR-001): every acceptance-matrix
    writer -- the verdict command AND the accept gate -- now shares this ONE
    critical section instead of each carrying its own copy, closing the
    lost-update class #4887 named as the root cause of #4974.

    ``matrix_dir`` MUST be resolved ONCE by the caller, BEFORE any slow
    check/subprocess AND before this lock is acquired, and reused unchanged
    as both the re-read base and the write target (C-004): the lock key is
    the Mission's canonical key (:func:`specify_cli.status.mission_lock_key`,
    one key for the primary and the coordination directory of a Mission),
    resolved before the lock is entered -- never re-derived inside this
    function or after the lock is released.

    Under :func:`specify_cli.status.mission_write_lock` (NFR-002's bounded
    ``timeout`` -- read at CALL TIME via the ``timeout`` parameter, never
    baked into a default argument, so a test can shorten it), this:

    1. Re-reads ``matrix_dir`` (:func:`read_acceptance_matrix`). If the file
       vanished between the caller's pre-lock existence check and this
       re-read, an empty, schema-valid :class:`AcceptanceMatrix` is used as
       the re-read base instead of crashing (matches the #4858 contract).
    2. Applies ``splice(fresh)`` IN PLACE -- the caller's row-ownership logic
       (e.g. :func:`splice_owned_rows`, or a single-row splice like the
       verdict command's).
    3. Writes: ``commit=True`` routes through
       :func:`write_and_commit_acceptance_matrix` (requires ``entry_id`` and
       ``message``); ``commit=False`` calls the raw
       :func:`write_acceptance_matrix` (matches the accept gate's
       ``--no-commit`` contract, C-003 -- HEAD must stay unchanged).

    The re-read, splice and write ALL happen while the lock is held (NFR-001
    is about what happens OUTSIDE this function: slow checks / review-evidence
    population run before this is called, never inside it). Fails CLOSED
    (FR-001/FR-005): a lock-acquisition timeout raises
    :class:`~specify_cli.status.FeatureStatusLockTimeoutError` before the
    re-read or any write, so a timeout NEVER degrades to an unlocked write.
    """
    if timeout is None:
        timeout = BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
    with mission_write_lock(matrix_dir, repo_root=repo_root, timeout=timeout):
        fresh_matrix = read_acceptance_matrix(matrix_dir)
        if fresh_matrix is None:
            # The matrix vanished between the pre-lock existence check and
            # this re-read -- start from an empty, schema-valid matrix rather
            # than crashing; the splice below still inserts exactly the
            # row(s) this invocation owns.
            fresh_matrix = AcceptanceMatrix(mission_slug=mission_slug)
        splice(fresh_matrix)
        write_result: WriteSeamResult | Path
        if commit:
            if entry_id is None or message is None:
                raise ValueError("entry_id and message are required when commit=True")
            write_result = write_and_commit_acceptance_matrix(
                repo_root,
                mission_slug,
                matrix_dir,
                fresh_matrix,
                entry_id=entry_id,
                message=message,
            )
        else:
            write_result = write_acceptance_matrix(matrix_dir, fresh_matrix)
    return fresh_matrix, write_result


@dataclass(frozen=True)
class _RowOwnershipSpec:
    """Which fields identify, judge and define one matrix row kind (FR-003)."""

    section: str
    id_attr: str
    result_attr: str
    pending_value: str
    definition_attrs: tuple[str, ...]


# spec.md "Row ownership rule (FR-003)": a criterion's judgement-defining
# fields are ``proof_type``/``description``.
_CRITERION_OWNERSHIP = _RowOwnershipSpec(
    section="criteria",
    id_attr="criterion_id",
    result_attr="pass_fail",
    pending_value="pending",
    definition_attrs=("proof_type", "description"),
)

# spec.md "Row ownership rule (FR-003)": a negative invariant's
# judgement-defining fields are ``verification_method``/``verification_command``/``scope``.
_INVARIANT_OWNERSHIP = _RowOwnershipSpec(
    section="negative_invariants",
    id_attr="invariant_id",
    result_attr="result",
    pending_value="pending",
    definition_attrs=("verification_method", "verification_command", "scope"),
)


def _rows_for(matrix: Any, section: str) -> list[Any]:
    """``getattr(matrix, section, None) or []`` -- tolerates a test double
    (unit-test ``SimpleNamespace``/mock) that carries no ``criteria`` /
    ``negative_invariants`` attribute at all, treating it as empty."""
    return getattr(matrix, section, None) or []


def _row_is_owned(
    spec: _RowOwnershipSpec,
    snapshot_row: Any | None,
    fresh_row: Any | None,
    judged_row: Any,
) -> bool:
    """The four FR-003 conditions, evaluated for one candidate row."""
    if snapshot_row is None or fresh_row is None:
        return False
    if getattr(snapshot_row, spec.result_attr) != spec.pending_value:
        return False
    if getattr(judged_row, spec.result_attr) == spec.pending_value:
        return False
    if getattr(fresh_row, spec.result_attr) != spec.pending_value:
        return False
    snapshot_definition = tuple(getattr(snapshot_row, attr) for attr in spec.definition_attrs)
    fresh_definition = tuple(getattr(fresh_row, attr) for attr in spec.definition_attrs)
    return snapshot_definition == fresh_definition


def _replace_row_by_id(rows: list[Any], id_attr: str, row_id: Any, new_row: Any) -> None:
    for idx, existing in enumerate(rows):
        if getattr(existing, id_attr) == row_id:
            rows[idx] = new_row
            return


def _splice_owned_rows_for_spec(fresh: Any, snapshot: Any, judged: Any, spec: _RowOwnershipSpec) -> None:
    fresh_rows = _rows_for(fresh, spec.section)
    if not fresh_rows:
        return
    snapshot_by_id = {getattr(row, spec.id_attr): row for row in _rows_for(snapshot, spec.section)}
    fresh_by_id = {getattr(row, spec.id_attr): row for row in fresh_rows}
    for judged_row in _rows_for(judged, spec.section):
        row_id = getattr(judged_row, spec.id_attr)
        if _row_is_owned(spec, snapshot_by_id.get(row_id), fresh_by_id.get(row_id), judged_row):
            _replace_row_by_id(fresh_rows, spec.id_attr, row_id, judged_row)


def splice_owned_rows(fresh: AcceptanceMatrix, snapshot: AcceptanceMatrix, judged: AcceptanceMatrix) -> None:
    """Splice INTO ``fresh`` (in place) only the rows accept owns (FR-003).

    spec.md "Row ownership rule (FR-003)": for a row R, ``judged``'s value
    replaces ``fresh``'s value ONLY when ALL of:

    1. R was ``pending`` in ``snapshot`` (accept's pre-check read);
    2. ``judged``'s value for R is no longer ``pending`` (accept judged it);
    3. R is STILL ``pending`` in ``fresh`` (the freshly re-read matrix);
    4. R's judgement-defining fields are UNCHANGED between ``snapshot`` and
       ``fresh`` (a negative invariant re-registered with a different
       command/method/scope, or a criterion re-authored with a different
       proof_type/description, is a NEW row, and accept's stale judgement of
       the OLD definition must not apply to it).

    A row present only in ``fresh`` (added concurrently) is left untouched
    (kept). A row present only in ``snapshot`` (removed concurrently, or
    simply not present in the freshly re-read matrix) is never re-added --
    condition 3 already requires the row to exist in ``fresh``. Applies to
    BOTH ``criteria`` and ``negative_invariants`` with the same rule, using
    each row kind's own id/result/definition fields.

    Every one of ``fresh``/``snapshot``/``judged`` may be a plain object
    (e.g. a unit-test double) that lacks a ``criteria`` or
    ``negative_invariants`` attribute entirely -- that section is then
    treated as empty rather than raising.
    """
    _splice_owned_rows_for_spec(fresh, snapshot, judged, _CRITERION_OWNERSHIP)
    _splice_owned_rows_for_spec(fresh, snapshot, judged, _INVARIANT_OWNERSHIP)


class AcceptanceVerdictNotReadyError(RuntimeError):
    """Raised by :func:`locked_acceptance_verdict_guard` on a non-ready verdict.

    FR-010's locked pre-stamp re-check: host ``accept`` and
    ``accept-mission`` must refuse to record acceptance unless the matrix,
    read FRESH under the lock immediately before the stamp, carries a
    ``pass`` or ``VERDICT_PASS_PENDING_CONSOLIDATION`` verdict. Defined here
    (matrix-level), not as an :class:`~specify_cli.acceptance.AcceptanceError`
    subclass, so this module never imports ``specify_cli.acceptance``'s
    package ``__init__`` (a circular import -- that package is the one that
    imports FROM ``matrix.py``). The caller (host accept / accept-mission,
    WP02) catches this and translates it into its own structured, non-zero
    exit / envelope error.
    """

    def __init__(self, *, matrix_dir: Path, verdict: str) -> None:
        self.matrix_dir = matrix_dir
        self.verdict = verdict
        super().__init__(f"Acceptance matrix at {matrix_dir} carries verdict {verdict!r}, not pass; refusing to record acceptance.")


@contextmanager
def locked_acceptance_verdict_guard(
    repo_root: Path,
    matrix_dir: Path,
    *,
    timeout: float | None = None,
) -> Iterator[AcceptanceMatrix]:
    """FR-010 primitive: hold the lock across the pre-stamp verdict re-check.

    Takes the SAME per-mission lock (keyed on the Mission's canonical lock
    key, C-004) as :func:`locked_reread_splice_and_write`, re-reads the matrix
    fresh, and raises :class:`AcceptanceVerdictNotReadyError` unless its
    ``overall_verdict`` is ``"pass"`` or
    :data:`VERDICT_PASS_PENDING_CONSOLIDATION` -- then YIELDS the fresh
    matrix while STILL HOLDING THE LOCK, so the caller's own in-process
    acceptance-record write (never a subprocess -- that could deadlock on
    this same lock) happens inside the same critical section a concurrently
    committed failing verdict would also need to acquire. A missing matrix
    (``read_acceptance_matrix`` returns ``None``) is treated as ``"pending"``
    -- never ready.

    ``timeout`` is read at CALL TIME (never bound into a default argument),
    mirroring :func:`locked_reread_splice_and_write`, so a test can shorten
    it to exercise the fail-closed timeout path.
    """
    if timeout is None:
        timeout = BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
    with mission_write_lock(matrix_dir, repo_root=repo_root, timeout=timeout):
        fresh_matrix = read_acceptance_matrix(matrix_dir)
        if fresh_matrix is None:
            # Treated as "pending" -- never ready -- and raised explicitly
            # here (rather than via an ``assert`` further down) so the
            # missing-matrix path is a real, always-enforced control-flow
            # branch, not a runtime invariant that ``python -O`` could strip.
            raise AcceptanceVerdictNotReadyError(matrix_dir=matrix_dir, verdict="pending")
        verdict = fresh_matrix.overall_verdict
        if verdict not in ("pass", VERDICT_PASS_PENDING_CONSOLIDATION):
            raise AcceptanceVerdictNotReadyError(matrix_dir=matrix_dir, verdict=verdict)
        yield fresh_matrix


def scaffold_acceptance_matrix(
    feature_dir: Path,
    mission_slug: str,
    requirement_ids: list[str] | None = None,
    *,
    home_dir: Path | None = None,
    repo_root: Path | None = None,
    policy: ProtectionPolicyLike | None = None,
    owned: OwnedCheckout | None = None,
) -> Path | None:
    """Author a minimal, schema-valid ``acceptance-matrix.json`` for a feature.

    Lane-based features require ``acceptance-matrix.json`` to exist before the
    acceptance gate will run (see ``specify_cli.acceptance``). This helper
    scaffolds a minimal but schema-valid matrix at task-finalization time so the
    artifact is never silently missing.

    The scaffold is **idempotent**: an existing ``acceptance-matrix.json`` is
    never overwritten, so operator-curated criteria survive re-runs.

    **FR-010 / C8 / AH-3 — single authoritative home.** The idempotency check
    consults the matrix's DECLARED HOME (``home_dir``, when supplied by the
    caller from the same surface resolver the gate reads through), not merely the
    ``feature_dir`` staging location. Under coordination topology the authoritative
    matrix lives on the coord surface; without this check a re-finalize would find
    no matrix at the primary ``feature_dir`` and scaffold a *second*, divergent
    primary copy alongside the real coord one (#2882). Consulting the declared home
    means exactly one copy is ever authored, so the provenance fields cannot
    diverge across copies. When ``home_dir`` is omitted the check falls back to
    ``feature_dir`` (the flat/create-window case, where primary IS the home).

    **write-surface-coherence WP08 (#2804 / #2404) — no PRIMARY husk under
    coord topology.** ``home_dir`` (:func:`~specify_cli.acceptance.gates_core.
    _acceptance_matrix_read_dir`) is materialization-AWARE: when the mission's
    stored topology routes through coordination but the coord worktree has not
    been materialized yet (finalize can run before it does), it affirmatively
    substitutes PRIMARY for READS (AH-2) — a legitimate read-time degrade.
    When ``repo_root`` is supplied, the write routes through
    :func:`write_and_commit_acceptance_matrix` (the WP03 write-seam) staged
    at ``home`` -- never the PRIMARY ``feature_dir`` (WP10 cycle 2, B4 /
    decision ``plan.design.owning-copy-flip-allocation``): for a MATERIALIZED
    coordination Mission ``home`` already IS the coordination Mission dir, so
    the write lands IN PLACE and the router's legacy ``shutil.copy2`` never
    fires; for the pre-materialization EMPTY window ``home`` still resolves
    to PRIMARY (the same AH-2 read fallback), the scaffold stages there as
    before, and the FIRST real coordination write (any ``write_dir`` caller)
    carries it over as part of that write's own EMPTY-surface seed -- never
    an add/add divergence, because there is still only ONE declared home at
    any given time. This mirrors the sibling, already-fixed
    ``issue-matrix.json`` scaffold (:func:`~specify_cli.tasks.issue_matrix.
    scaffold_issue_matrix`). A coord-less topology (``SINGLE_BRANCH`` /
    ``LANES``) resolves to the SAME primary ``target_branch`` either way — no
    behaviour change there. Omitting ``repo_root`` (the historical contract;
    every existing caller/test) preserves the byte-identical bare write.

    When ``requirement_ids`` are supplied (e.g. functional requirement ids from
    ``spec.md``), one ``pending`` criterion is derived per requirement. When no
    requirement ids are available, a single placeholder criterion carrying
    :data:`SCAFFOLD_TODO_MARKER` is written so the file is valid yet obviously
    awaiting real content.

    Args:
        feature_dir: The ``kitty-specs/<slug>/`` directory for the mission (the
            staging location the finalize flow collects and routes from).
        mission_slug: Feature slug (e.g. ``010-lane-only-runtime``).
        requirement_ids: Optional functional requirement ids to seed criteria.
        home_dir: The matrix's declared home directory, when the caller has
            resolved it. Used for the single-home idempotency check.
        repo_root: Primary checkout root. Supplying this opts the WRITE into
            the coord-aware write-seam (T040/T041); omitted, the scaffold
            writes directly to ``feature_dir`` exactly as before.
        policy: An optional pre-resolved protection policy for the write-seam
            path; resolved from ``repo_root`` when omitted.

    Returns:
        Path to the scaffolded (or pre-existing) ``acceptance-matrix.json``,
        or ``None`` when a ``repo_root``-routed write was refused (FR-011
        zero-write refusal — e.g. an unroutable mission) rather than authored
        on the wrong surface.
    """
    # The exists checks and the write are ONE hold of the Mission write lock, so a verdict recorded
    # between them is never overwritten by the placeholder scaffold (mirrors ``scaffold_issue_matrix``).
    lock_root = repo_root if repo_root is not None else (owned.repository_root if owned is not None else None)
    with mission_write_lock(feature_dir, repo_root=lock_root):
        return _scaffold_acceptance_matrix_locked(feature_dir, mission_slug, requirement_ids, home_dir=home_dir, repo_root=repo_root, policy=policy, owned=owned)


def _scaffold_acceptance_matrix_locked(
    feature_dir: Path,
    mission_slug: str,
    requirement_ids: list[str] | None,
    *,
    home_dir: Path | None,
    repo_root: Path | None,
    policy: ProtectionPolicyLike | None,
    owned: OwnedCheckout | None,
) -> Path | None:
    """The body of :func:`scaffold_acceptance_matrix`: runs with the Mission write lock held."""
    home = home_dir if home_dir is not None else feature_dir
    home_path = home / MATRIX_FILENAME
    if home_path.exists():
        # C8 / AH-3: the single declared home already holds the matrix — never
        # author a second (primary-scaffold) copy that could diverge on the new
        # provenance fields.
        return home_path
    path = feature_dir / MATRIX_FILENAME
    if path.exists():
        # Respect operator-curated content; idempotent re-runs must not clobber.
        return path

    criteria: list[AcceptanceCriterion] = []
    for req_id in requirement_ids or []:
        criteria.append(
            AcceptanceCriterion(
                criterion_id=req_id,
                description=f"Verify {req_id} is satisfied",
                proof_type="automated_test",
                pass_fail="pending",  # noqa: S106
                notes=SCAFFOLD_TODO_MARKER,
            )
        )

    if not criteria:
        # Empty-but-valid scaffold with an explicit TODO marker. A single
        # placeholder keeps the JSON schema-valid while signalling clearly that
        # no real criteria have been authored yet.
        criteria.append(
            AcceptanceCriterion(
                criterion_id="AC-001",
                description=SCAFFOLD_TODO_MARKER,
                proof_type="automated_test",
                pass_fail="pending",  # noqa: S106
                notes=SCAFFOLD_TODO_MARKER,
            )
        )

    matrix = AcceptanceMatrix(mission_slug=mission_slug, criteria=criteria)
    if repo_root is not None:
        # WP10 cycle 2 (B4, decision plan.design.owning-copy-flip-allocation):
        # stage at ``home`` (the declared/write home the caller already
        # resolved, above), NEVER the PRIMARY ``feature_dir`` -- staging at
        # ``feature_dir`` for a MATERIALIZED coordination Mission left the
        # router's legacy ``shutil.copy2`` as the only thing that ever moved
        # the scaffold onto the coordination surface, and the function
        # returned the stray PRIMARY path even once the coordination copy
        # existed. For a MATERIALIZED mission ``home`` is already the
        # coordination Mission dir (physically under ``.worktrees/``), so the
        # write lands IN PLACE (``commit_router``'s IN_PLACE classification)
        # and the router never copies. For the pre-materialization EMPTY
        # window ``home`` still resolves to PRIMARY (AH-2's declared read
        # fallback) -- the scaffold stages there exactly as before, and the
        # FIRST real coordination write (any ``write_dir`` caller) carries it
        # over as part of its own EMPTY-surface seed.
        result = write_and_commit_acceptance_matrix(
            repo_root,
            mission_slug,
            home,
            matrix,
            entry_id="finalize-scaffold",
            message=f"chore({mission_slug}): scaffold acceptance-matrix",
            policy=policy,
            owned=owned,
        )
        if result.status in ("committed", "unchanged"):
            return home_path
        if owned is not None:
            raise RuntimeError(result.diagnostic or "Owned acceptance matrix write failed.")
        # FR-011 zero-write refusal (or a genuine commit error): never fall
        # back to a bare PRIMARY write here — that is exactly the silent
        # degrade this fix retires. The caller treats ``None`` as "nothing
        # scaffolded this run" (a convenience artifact, never finalize-blocking).
        return None
    return write_acceptance_matrix(feature_dir, matrix)


# ---------------------------------------------------------------------------
# Evidence validation
# ---------------------------------------------------------------------------


def validate_manual_evidence(criterion: AcceptanceCriterion) -> list[str]:
    """Validate that manual QA criteria have required evidence fields.

    Returns list of error messages. Empty means valid.
    """
    errors: list[str] = []
    if criterion.proof_type != "manual_qa":
        return errors
    if not criterion.evidence:
        errors.append(f"{criterion.criterion_id}: manual QA requires evidence (URL/screenshot)")
    if not criterion.verified_at:
        errors.append(f"{criterion.criterion_id}: manual QA requires verified_at timestamp")
    if not criterion.verified_by:
        errors.append(f"{criterion.criterion_id}: manual QA requires verified_by identity")
    return errors


def validate_matrix_evidence(matrix: AcceptanceMatrix) -> list[str]:
    """Validate all evidence in the matrix. Returns list of errors."""
    errors: list[str] = []
    for criterion in matrix.criteria:
        if not _is_allowed_value(criterion.pass_fail, CRITERION_VERDICTS):
            allowed = ", ".join(sorted(CRITERION_VERDICTS))
            errors.append(f"{criterion.criterion_id}: pass_fail must be one of {allowed}; got {criterion.pass_fail!r}")
        errors.extend(validate_manual_evidence(criterion))
    for invariant in matrix.negative_invariants:
        errors.extend(_validate_invariant_provenance(invariant))
    return errors


def _validate_invariant_provenance(invariant: NegativeInvariant) -> list[str]:
    """NI-1: enforce provenance on a recorded judgement, with the legacy escape.

    A ``recorded`` TERMINAL result must carry both ``verified_ref`` and
    ``verified_surface_kind``; a provenance-less ``recorded`` terminal result is a
    validation error (C1). A ``legacy_unrecorded`` result may carry null
    provenance — that origin, and only that origin, permits the absence (the
    FR-014 sentinel for pre-schema results). ``pending`` and
    ``deferred_to_consolidation`` are scheduled-not-yet-judged states and are
    exempt: they have no surface to attribute a judgement to.
    """
    errors: list[str] = []
    result = invariant.result
    if not _is_allowed_value(result, NEGATIVE_INVARIANT_RESULTS):
        allowed = ", ".join(sorted(NEGATIVE_INVARIANT_RESULTS))
        errors.append(f"{invariant.invariant_id}: result must be one of {allowed}; got {result!r}")
        return errors
    if not _is_allowed_value(invariant.provenance_origin, PROVENANCE_ORIGINS):
        allowed = ", ".join(sorted(PROVENANCE_ORIGINS))
        errors.append(f"{invariant.invariant_id}: provenance_origin must be one of {allowed}; got {invariant.provenance_origin!r}")
        return errors
    if (
        result in TERMINAL_INVARIANT_RESULTS
        and invariant.provenance_origin == PROVENANCE_RECORDED
        and (invariant.verified_ref is None or invariant.verified_surface_kind is None)
    ):
        errors.append(f"{invariant.invariant_id}: a recorded {result!r} result requires both verified_ref and verified_surface_kind (NI-1)")
    return errors


# ---------------------------------------------------------------------------
# Negative invariant enforcement
# ---------------------------------------------------------------------------


def enforce_negative_invariants(
    repo_root: Path,
    invariants: list[NegativeInvariant],
    *,
    context: GateExecutionContext | None = None,
) -> list[NegativeInvariant]:
    """Run all negative invariant checks. Returns updated invariants.

    Verification methods:
    - grep_absence: Run grep for pattern in repo; exit code 1 means absent.
    - custom_command: Run a command, check exit code (0 = absent/pass).

    **NI-2 / C3 (preservation).** A negative invariant that already carries a
    TERMINAL ``result`` (``confirmed_absent`` / ``still_present`` /
    ``verification_error``) is NOT re-verified: it is preserved verbatim, provenance
    included. The guard keys on TERMINAL-SET MEMBERSHIP, not ``result != "pending"``
    — so the fourth value ``deferred_to_consolidation`` is *not* frozen (it must
    remain re-judgeable at ``POST_CONSOLIDATION`` per NI-4), while a recorded
    judgement stays immutable. This matters because the gate runs both during per-WP
    review (from the integrated lane worktree, where mission-added files exist) and
    again at ``accept`` (from the pre-merge primary root, where they do not — they
    land only via ``spec-kitty merge``); re-running a recorded invariant against the
    pre-merge tree would clobber an honest ``confirmed_absent`` with a false
    ``still_present`` (#1834).

    **NI-3 / C4 / C9 (deferral).** When a ``context`` is supplied and a ``pending``
    invariant's subject cannot exist on the current surface (a ``grep_absence``
    scoped to a source dir that is absent pre-consolidation), it transitions to
    ``deferred_to_consolidation`` with a ``deferred_reason`` and
    ``deferred_to_phase = POST_CONSOLIDATION`` — never to a false ``still_present``.
    An unscoped grep, or a scoped grep whose dir already exists (C9), is judged
    normally. A freshly judged terminal result is stamped ``recorded`` with the
    context's surface + ref (NI-1 provenance). Without a ``context`` the legacy
    behaviour is preserved (judge ``pending``, no provenance stamp, no deferral).
    """
    results: list[NegativeInvariant] = []
    for ni in invariants:
        if ni.result in TERMINAL_INVARIANT_RESULTS:
            results.append(ni)  # NI-2 / C3: a recorded judgement is never overwritten.
            continue
        if ni.result == DEFERRED_TO_CONSOLIDATION:
            # NI-4: not terminal, but judged by the post-consolidation op (C6),
            # not re-judged here pre-consolidation. Left intact.
            results.append(ni)
            continue
        # ``pending`` — the scaffolded default, so this is the common path.
        if context is not None and _should_defer(repo_root, ni, context):
            results.append(_defer_invariant(ni, context))
            continue
        updated = _check_invariant(repo_root, ni)
        results.append(_stamp_provenance(updated, context))
    return results


def populate_criteria_from_review_evidence(status_feature_dir: Path, criteria: list[AcceptanceCriterion]) -> list[AcceptanceCriterion]:
    """FR-008 (IC-04): auto-derive ``pending`` ``code_review`` rows from WP evidence.

    Closes the "criterion rows never populated" gap (governance-at-the-gate
    WP04, US2): before this, a criterion's ``pass_fail`` never left the
    ``scaffold_acceptance_matrix`` default of ``"pending"`` unless an operator
    hand-invoked ``agent mission acceptance-verdict`` — forcing every accept
    onto ``--allow-fail``. Design decision (see :data:`AUTO_DERIVABLE_
    PROOF_TYPES`): population is auto-derived from the decision already made
    (NFR-005) — the T1/T2 gate-side evidence capture (an approval event's
    ``policy_metadata``/``review_ref`` and its ``review-cycle-N.md``) — never
    a fresh hand-filled judgement; it is intentionally scoped to
    ``code_review``-typed criteria only.

    Forward-only (NI-2-style preservation, mirrored from
    :func:`enforce_negative_invariants`): a criterion already judged
    (``pass_fail != "pending"``) is left untouched — this NEVER re-judges a
    standing verdict, including one an operator hand-authored via
    ``acceptance-verdict``. The empty ``finalize-tasks`` scaffold placeholder
    (:func:`_is_empty_scaffold`) is also skipped — it carries no real
    ``code_review`` intent to auto-derive.

    All-or-nothing per mission: population only fires when EVERY tracked WP
    is ``approved``/``done`` AND every one of them carries a durable
    event-sourced review verdict whose ``verdict`` is itself ``"approved"``
    (:func:`~specify_cli.status.reducer.event_sourced_review_result`). The
    verdict check (not just slot-presence) matters because the reducer
    carries a WP's ``review_result`` slot FORWARD across any transition that
    does not leave ``in_review`` (``reducer._wp_state_from_event``) — a WP
    force-approved from a non-``in_review`` lane after a genuine rejection
    can be lane-``approved`` while its event-sourced slot still holds the
    REJECTING reviewer's ``changes_requested`` result. Reading that as proof
    would fabricate an approval attribution. A mission with any WP short of
    a genuine approved verdict is left exactly as it was — ``pending`` —
    rather than derive a partial, misleading pass; the existing
    pending-verdict block in ``gates_core._evaluate_acceptance_matrix``
    continues to hold accept closed in that case, unchanged.

    A missing/corrupted status log degrades to a no-op (returns ``criteria``
    unchanged) rather than raising — this is an additive enrichment layered
    on top of the pre-existing block-on-pending gate, not a new hard
    dependency the gate can be broken by.
    """
    pending_targets = {
        c.criterion_id
        for c in criteria
        if c.pass_fail == "pending"  # noqa: S105  # verdict value, not a secret
        and c.proof_type in AUTO_DERIVABLE_PROOF_TYPES
        and not _is_empty_scaffold(c)
    }
    if not pending_targets:
        return criteria

    from specify_cli.status import (
        StoreError,
        event_sourced_review_result,
        read_event_stream,
        reduce,
    )

    try:
        stream = read_event_stream(status_feature_dir)
        wp_states = reduce(stream.transitions, stream.annotations).work_packages
    except StoreError:
        # Degrade to a no-op (leave rows pending → the block-on-pending gate still
        # holds accept closed) rather than break an otherwise-passing accept when
        # ``read_event_stream`` cannot read a missing/corrupt status log. The
        # ``reduce()`` call is kept inside this ``try`` defensively (pre-merge review
        # MINOR: it was outside the guard), though it operates on already-parsed
        # events and does not itself raise ``StoreError``.
        return criteria
    if not wp_states:
        return criteria
    if not all(state.get("lane") in ("approved", "done") for state in wp_states.values()):
        return criteria

    reviewers: list[str] = []
    references: list[str] = []
    for wp_id in sorted(wp_states):
        lookup = event_sourced_review_result(status_feature_dir, wp_id)
        if not lookup.slot_present or lookup.result is None or lookup.result.verdict != "approved":
            # Incomplete evidence chain (a WP approved before T1/T2 landed,
            # or via a path that never recorded review_result) -- stay
            # pending rather than derive a verdict this gate cannot prove.
            # M1 (WP04 review, evidence-integrity): a WP whose lane is
            # approved/done but whose event-sourced ``review_result`` slot
            # is NOT itself ``verdict == "approved"`` (e.g. a stale
            # ``changes_requested`` result the reducer carries forward
            # because a force-approve bypassed a fresh in_review exit,
            # ``reducer._wp_state_from_event``'s ``from_lane != IN_REVIEW``
            # inheritance) must NEVER be read as approval proof -- that
            # would stamp the criterion ``pass`` citing the REJECTING
            # reviewer and the rejection's own review-cycle reference, a
            # fabricated approval attribution.
            return criteria
        reviewers.append(lookup.result.reviewer)
        references.append(f"{wp_id}:{lookup.result.reference}")

    from kernel.clock import now_utc_iso

    verified_at = now_utc_iso()
    evidence = "; ".join(references)
    verified_by = ", ".join(dict.fromkeys(reviewers))
    return [
        replace(
            c,
            pass_fail="pass",  # noqa: S106  # verdict value, not a secret
            verified_by=verified_by,
            verified_at=verified_at,
            evidence=evidence,
            notes=(f"{c.notes} {_AUTO_DERIVED_NOTE}" if c.notes else _AUTO_DERIVED_NOTE),
        )
        if c.criterion_id in pending_targets
        else c
        for c in criteria
    ]


def _should_defer(repo_root: Path, ni: NegativeInvariant, context: GateExecutionContext) -> bool:
    """NI-3 / C9: does this ``pending`` invariant's subject exist on the surface?

    Only a ``grep_absence`` SCOPED to a source directory can defer: if any of its
    scoped roots is absent under ``repo_root`` (the tree the grep runs against),
    the subject cannot yet exist, so the invariant defers rather than reporting a
    false ``still_present`` (FR-003). A scoped root that already exists (C9) or an
    unscoped whole-repo grep is judgeable now. Deferral only applies before
    ``POST_CONSOLIDATION`` — at/after that phase the consolidated tree holds the
    subject and it is judged (C6).
    """
    if context.phase.name == POST_CONSOLIDATION_PHASE_NAME:
        return False
    if ni.verification_method != "grep_absence" or not ni.scope:
        return False
    return any(not (repo_root / root).exists() for root in ni.scope.split())


def _defer_invariant(ni: NegativeInvariant, context: GateExecutionContext) -> NegativeInvariant:
    """Transition a ``pending`` invariant to ``deferred_to_consolidation`` (C4)."""
    surface = context.surface_kind.value
    return replace(
        ni,
        result=DEFERRED_TO_CONSOLIDATION,
        evidence=(f"Scoped subject {ni.scope!r} is absent on the {surface} surface pre-consolidation; deferred to post-consolidation verification."),
        deferred_reason=(
            f"Scoped path(s) {ni.scope!r} do not exist on the {surface} surface at "
            f"ref {context.ref!r}; judging here would report a false still_present "
            "(FR-003). Deferred to the post-consolidation verification op."
        ),
        deferred_to_phase=POST_CONSOLIDATION_PHASE_NAME,
    )


def _stamp_provenance(ni: NegativeInvariant, context: GateExecutionContext | None) -> NegativeInvariant:
    """NI-1: stamp a freshly judged result with the surface + ref it was established against.

    A terminal result gets ``provenance_origin = recorded`` plus the context's
    surface and ref, so it satisfies NI-1 and is attributable. A result that stays
    ``pending`` (unknown method / missing command) is left unstamped — provenance
    attaches to judgements, not to unjudged rows. Without a ``context`` (legacy
    callers) nothing is stamped.
    """
    if context is None or ni.result not in TERMINAL_INVARIANT_RESULTS:
        return ni
    return replace(
        ni,
        provenance_origin=PROVENANCE_RECORDED,
        verified_ref=context.ref,
        verified_surface_kind=context.surface_kind.value,
    )


def _check_invariant(repo_root: Path, ni: NegativeInvariant) -> NegativeInvariant:
    """Run a single negative invariant check."""
    if ni.verification_method == "grep_absence":
        return _check_grep_absence(repo_root, ni)
    elif ni.verification_method == "custom_command":
        return _check_custom_command(repo_root, ni)
    else:
        # Unknown method — leave as pending
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="pending",
            evidence=f"Unknown verification method: {ni.verification_method}",
            extras=ni.extras,
        )


def _check_grep_absence(repo_root: Path, ni: NegativeInvariant) -> NegativeInvariant:
    """Grep for pattern; exit code 1 means confirmed absent."""
    if not ni.verification_command:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="pending",
            evidence="No grep pattern specified in verification_command",
            scope=ni.scope,
            extras=ni.extras,
        )

    # A scoped invariant restricts the grep to its declared repo-relative
    # search root(s); an unscoped one searches the whole repo (``.``), as before.
    search_roots = ni.scope.split() if ni.scope else ["."]

    try:
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--exclude=acceptance-matrix.json",
                "--exclude-dir=.git",
                "--",
                ni.verification_command,
                *search_roots,
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="verification_error",
            evidence=f"grep failed to start: {exc}",
            scope=ni.scope,
            extras=ni.extras,
        )
    if result.returncode == 1:
        # No matches — pattern is absent
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="confirmed_absent",
            evidence="grep found zero matches",
            scope=ni.scope,
            extras=ni.extras,
        )
    if result.returncode == 0:
        matches = result.stdout.strip().splitlines()[:5]
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="still_present",
            evidence=f"grep found matches: {'; '.join(matches)}",
            scope=ni.scope,
            extras=ni.extras,
        )
    details = (result.stderr or result.stdout).strip()[:500]
    return NegativeInvariant(
        invariant_id=ni.invariant_id,
        description=ni.description,
        verification_method=ni.verification_method,
        verification_command=ni.verification_command,
        result="verification_error",
        evidence=f"grep verification failed (exit {result.returncode}): {details}",
        scope=ni.scope,
        extras=ni.extras,
    )


def _check_custom_command(repo_root: Path, ni: NegativeInvariant) -> NegativeInvariant:
    """Run custom command — exit code 0 means confirmed absent."""
    if not ni.verification_command:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="pending",
            evidence="No command specified in verification_command",
            extras=ni.extras,
        )

    try:
        result = run_configured_command(
            ni.verification_command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
    except ConfiguredCommandUnsupported as exc:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="pending",
            evidence=str(exc),
            extras=ni.extras,
        )
    except OSError as exc:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="still_present",
            evidence=f"Command failed to start: {exc}",
            extras=ni.extras,
        )
    if result.returncode == 0:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="confirmed_absent",
            evidence=f"Command exited 0: {result.stdout.strip()[:200]}",
            extras=ni.extras,
        )
    else:
        return NegativeInvariant(
            invariant_id=ni.invariant_id,
            description=ni.description,
            verification_method=ni.verification_method,
            verification_command=ni.verification_command,
            result="still_present",
            evidence=f"Command exited {result.returncode}: {result.stderr.strip()[:200]}",
            extras=ni.extras,
        )
