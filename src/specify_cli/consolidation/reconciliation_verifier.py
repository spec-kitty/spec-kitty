"""The merge-outcome verifier of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP12).

``VerifyStatus``, ``Divergence`` (whole, with its clause text and order), ``VerifyResult``,
``MergeOutcomeVerifier`` with the helpers only they use, and ``claim_integrity_refusal`` (it and
``MergeOutcomeVerifier`` call each other, so they share this module). Moved verbatim out of ``reconciliation.py``;
that module re-exports every name, so no caller changes (C-005, C-006).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path

from specify_cli.consolidation.git_probes import (
    GitProbeError,
    blob_id_at,
    changed_paths_in_range,
    changed_paths_of,
    commits_in_range,
    is_merge_commit,
    merge_own_changed_paths,
    merge_tree_write_tree_available,
    patch_id_of,
    patch_ids_in_range,
    path_state_at,
    sha_reachable_from,
    three_way_merge_blob,
)
from specify_cli.consolidation.reconciliation_authorship import unmet_approved_content
from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet, CanceledDependencyContent, MissingApprovedContent
from specify_cli.consolidation.reconciliation_kernel import _is_bookkeeping
from specify_cli.consolidation.reconciliation_rendering import (
    _RECOVERY_TAIL,
    _attest_tail,
    _describe_approved_content_missing,
    _describe_canceled_content,
    _describe_canceled_reachable,
)
from specify_cli.consolidation.wp_attribution import CanceledPathState


# Fail-closed REFUSE reasons (hoisted per Sonar S1192 — the window-base reason is
# shared by the merge/rebase reachability path and the squash blob-attribution
# path, which must refuse identically when the window base cannot be resolved).
_REFUSE_WINDOW_BASE_UNRESOLVED = "the excluded-content window base could not be resolved; the excluded/closed-world axes cannot be verified (fail-closed)"


# Squash-only (#5013 F1 corollary, widened by #5022): a production claim whose
# authorship set came back empty — BOTH blobs and deletions — while it lists
# approved WPs cannot attribute any target blob or deletion — the empty loop
# would PASS vacuously, so refuse instead.
_REFUSE_EMPTY_AUTHORED_BLOBS = (
    "the approved-authorship blob and deletion sets are both empty while approved WPs are claimed; "
    "the squash content axis cannot attribute any target blob or deletion (fail-closed)"
)


# FIX C (#5001 landing remediation): NO approved lane resolved any commits and no
# authored blob exists, yet the squash window carries a non-bookkeeping A/M path —
# there is no authorship authority to attribute that content against at all.
_REFUSE_NO_AUTHORSHIP_AUTHORITY = (
    "no approved lane resolved any commits and the authored-blob set is empty, "
    "but the squash window carries non-bookkeeping content; there is no "
    "authorship authority to attribute it against (fail-closed)"
)


class VerifyStatus(Enum):
    """Outcome of :meth:`MergeOutcomeVerifier.verify`.

    ``PASS`` alone permits teardown. ``FAIL`` (a proven divergence) and
    ``REFUSE`` (a fail-closed claim that cannot even be evaluated) both forbid
    teardown and force a non-zero exit — the contrapositive of the epic
    invariant.
    """

    # ``auto()`` (not string literals): identity comparison only — the values are
    # never serialized — and it keeps the ruff S105 hardcoded-secret heuristic
    # from misreading a member literally named ``PASS``.
    PASS = auto()
    FAIL = auto()
    REFUSE = auto()


@dataclass(frozen=True)
class Divergence:
    """The specific way the target tree diverged from the approved-WP claim.

    ``missing_approved`` — ``(wp_id, sha)`` pairs whose approved commit is NOT
    reachable from the target (approved work was dropped). ``reachable_excluded``
    — ``(sha, patch_id)`` pairs of excluded (canceled/removed) content that IS
    reachable from the target (removed code shipped); ``sha``/``patch_id`` is
    ``""`` when the match was made on the other axis. ``unattributable_content`` —
    ``(sha, patch_id)`` pairs of CONTENT commits in the merge window that belong to
    NO approved WP's authorship (the closed-world axis: a removed WP's commit that
    rode a carrier lane into the target — #4945/#4977/#4981). ``unattributable_blobs``
    — ``(path, blob)`` pairs from the SQUASH blob-attribution axis
    (:meth:`MergeOutcomeVerifier._unattributable_content_squash`, #5013 WS1): a
    squash destroys commit SHAs and patch-ids, so that axis names a repo-relative
    PATH and a blob sha instead — a distinct shape from ``unattributable_content``,
    rendered with its own vocabulary (Epic #5001 landing fix; the two fields were
    previously conflated, mislabeling a path as a "content commit" truncated to 10
    chars and a blob as a "patch-id"). ``unattributable_deletions`` — repo-relative
    PATHS (no blob — the path no longer has one) from the SQUASH DELETION axis
    (#5022 / WP1): a target path deleted in ``B..target`` that is not attributable
    to any approved lane's own first-parent authored deletion, distinct from
    ``unattributable_blobs`` (which names an Added/Modified path plus its blob).
    ``canceled_content`` — :class:`~specify_cli.consolidation.wp_attribution.CanceledPathState`
    entries (mixed-lane-authorship-soundness / #5046, WP05): a MIXED lane's
    canceled-with-provenance WP left its own, unsuperseded content on the
    target (or undid a surviving WP's approved change — SC-007). Distinct from
    every axis above — those all reason about commits/blobs the manifest never
    approved at all; this one reasons about ONE canceled WP's specific
    per-path content inside a lane the manifest DOES otherwise approve, which
    neither SHA/patch-id reachability (squash destroys them) nor blob-union
    attribution (the survivor's own authored blobs never covered the
    canceled WP's distinct paths) can see.
    """

    missing_approved: tuple[tuple[str, str], ...] = ()
    reachable_excluded: tuple[tuple[str, str], ...] = ()
    unattributable_content: tuple[tuple[str, str], ...] = ()
    unattributable_blobs: tuple[tuple[str, str], ...] = ()
    unattributable_deletions: tuple[str, ...] = ()
    canceled_content: tuple[CanceledPathState, ...] = ()

    #: #5571: approved lane content absent from / not applied to the target and
    #: not superseded by a later approved lane.
    approved_content_missing: tuple[MissingApprovedContent, ...] = ()

    #: #5569/#5613: a fully-canceled dependency lane's content that an approved
    #: lane carries and that is on the target. Never attest-liftable.
    canceled_reachable_via_dependency: tuple[CanceledDependencyContent, ...] = ()

    def describe(self) -> str:
        """Operator-facing, one-line-per-divergence explanation."""
        parts: list[str] = []
        for wp_id, sha in self.missing_approved:
            parts.append(f"approved {wp_id} commit {sha[:10]} is NOT reachable from the target — approved work would be dropped")
        for sha, pid in self.reachable_excluded:
            ident = sha[:10] if sha else f"patch-id {pid[:12]}"
            parts.append(f"excluded (canceled/removed) commit {ident} IS reachable from the target — removed code would ship")
        for sha, pid in self.unattributable_content:
            ident = sha[:10] if sha else f"patch-id {pid[:12]}"
            parts.append(
                f"content commit {ident} (patch-id {pid[:12]}) IS reachable from the "
                "target but belongs to NO approved WP — un-attributable "
                "(removed/canceled work would ship)"
            )
        for path, blob in self.unattributable_blobs:
            parts.append(
                f"file '{path}' (blob {blob[:10]}) IS reachable on the target but belongs to NO approved WP — un-attributable (removed/canceled work would ship)"
            )
        for path in self.unattributable_deletions:
            parts.append(
                f"file '{path}' was DELETED from the target but that deletion is NOT "
                "attributable to any approved WP's own authorship — un-attributable "
                "(data loss: approved content may have been silently removed)"
            )
        for entry in self.canceled_content:
            parts.append(_describe_canceled_content(entry))
        for missing in self.approved_content_missing:
            parts.append(_describe_approved_content_missing(missing))
        for carried in self.canceled_reachable_via_dependency:
            parts.append(_describe_canceled_reachable(carried))
        return "; ".join(parts) if parts else "no divergence"


def _with_attribution_hint(result: VerifyResult, claim: ApprovedWpCommitSet) -> VerifyResult:
    """Add the #6771 recovery to an un-attributable FAIL that declared no external dependency.

    A mission whose work-package branch brought a dependency branch's newer head in (with a
    real ``git merge --no-ff``, so the reviewed commits stand) sees every one of that
    branch's commits reported as un-attributable, which reads as "removed work would ship" and
    names no way out. The hint names the declaration that resolves it. It is added ONLY when
    the claim declared nothing (a declared run is refused for a different, self-explaining
    reason) and only to the un-attributable axes — never to a refusal, and never to a
    divergence this change does not own.
    """
    if result.divergence is None or claim.external_dependency_refs:
        return result
    divergence = result.divergence
    if not (divergence.unattributable_content or divergence.unattributable_blobs or divergence.unattributable_deletions):
        return result
    hint = (
        "If a work-package branch brought an external dependency branch's newer head in, declare it and re-run: "
        "spec-kitty consolidate --dependency-ref <ref>. Only a ref the mission branch or one of its lane branches reaches, "
        "on which no commit of any mission lane or mission branch sits, is accepted — mission-authored work is never exempt."
    )
    return replace(result, attribution_hint=hint)


#: #5318/#5296 (FR-009): printed BEFORE the single rollback authority runs, so it
#: describes the restore as in progress and defers to the per-branch report that
#: follows; it never claims that nothing was mutated.
_RESTORE_IN_PROGRESS = (
    "Every branch this consolidation moved (target, mission and coordination "
    "branches) is being restored to its pre-consolidation commit; the rollback "
    "report below names each branch, and a branch marked NOT restored still "
    "carries this run's commits."
)


@dataclass(frozen=True)
class VerifyResult:
    """Result of a single :meth:`MergeOutcomeVerifier.verify` call."""

    status: VerifyStatus
    divergence: Divergence | None = None
    refusal_reason: str | None = None
    #: #6771: on a FAIL whose divergence is un-attributable content and whose claim declared no
    #: external dependency ref, the recovery that names the declaration. Set by :meth:`verify`,
    #: printed by :meth:`recovery_guidance` — ``Divergence.describe()``'s wording is pinned by the
    #: terminus suites and stays untouched.
    attribution_hint: str | None = None

    @property
    def is_pass(self) -> bool:
        return self.status is VerifyStatus.PASS

    def recovery_guidance(self) -> str:
        """What the operator should do — printed on a non-PASS gate result."""
        if self.status is VerifyStatus.REFUSE:
            # D-4b (FR-010): the mission→target advance already landed before this
            # gate runs, so a REFUSE (a claim that could not even be evaluated, not
            # "known good") is rolled back the same as a FAIL. This text is printed
            # BEFORE the best-effort compare-and-swap restore runs, so it describes
            # the restore as in progress; the executor warns separately if it could
            # not be applied. Reasons that already end in a period are not doubled.
            reason = (self.refusal_reason or "").rstrip(".")
            return f"Reconciliation refused (fail-closed): {reason}. {_RESTORE_IN_PROGRESS} no teardown ran. Resolve the issue above, then re-run the merge."
        detail = self.divergence.describe() if self.divergence else "unknown divergence"
        hint = f" {self.attribution_hint}" if self.attribution_hint else ""
        return (
            f"Reconciliation FAILED: {detail.rstrip('.')}.{hint} {_RESTORE_IN_PROGRESS} "
            "nothing was torn down. Inspect the target branch and the lane tips, then "
            "re-run the merge."
        )

    @classmethod
    def passed(cls) -> VerifyResult:
        return cls(status=VerifyStatus.PASS)

    @classmethod
    def failed(cls, divergence: Divergence) -> VerifyResult:
        return cls(status=VerifyStatus.FAIL, divergence=divergence)

    @classmethod
    def refused(cls, reason: str) -> VerifyResult:
        return cls(status=VerifyStatus.REFUSE, refusal_reason=reason)


def _refuse_merged_independent_change(entry: CanceledPathState) -> str:
    """C3's final row / D-4 (R2): the target is neither the canceled state, the
    pre-state, nor the window-base state — the canceled change was merged with
    an independent one and the gate cannot prove the canceled content is
    absent. Names the lane, the WP, and the path (NFR-003 / contract C4)."""
    return (
        f"mixed lane {entry.lane_id}: canceled {entry.wp_id}'s change to '{entry.path}' was merged with an "
        f"independent change; the gate cannot prove it is absent. Recovery: revert {entry.wp_id}'s change to "
        f"'{entry.path}' on the lane through a surviving WP's governed work, {_RECOVERY_TAIL}; or, after "
        f"verifying by hand that none of {entry.wp_id}'s canceled change remains in '{entry.path}', "
        f"{_attest_tail(entry.wp_id)}."
    )


def _merge_canceled_content_into_result(result: VerifyResult, canceled_fail: list[CanceledPathState]) -> VerifyResult:
    """Fold the canceled-content FAIL candidates into a strategy axis result (T024).

    A strategy REFUSE always wins unchanged (REFUSE precedes FAIL by
    construction throughout this module). Otherwise, with no canceled-content
    entries this is a no-op (byte-identical for every existing claim); with
    entries, a strategy PASS becomes a FAIL carrying only the canceled-content
    divergence, and a strategy FAIL gets the entries merged onto its existing
    :class:`Divergence` (never replacing its other axes).

    LOAD-BEARING COUPLING (#5046; flagged by two independent review lenses at
    landing): under the default squash strategy the #5013 blob-attribution axis
    is NOT canceled-aware — it attributes the union of the lane's authored blobs,
    which INCLUDES the canceled WP's, so it would treat canceled content as
    approved. This canceled-content axis (`_canceled_content_divergence`,
    strategy-independent, run above the squash branch in `verify`) is therefore
    the SOLE thing that stops canceled content shipping under squash. The two
    axes compose as a fail-closed union here; a future change that narrows,
    short-circuits or empties the canceled-content axis MUST NOT assume the blob
    axis backstops it. Keep the canceled axis running for every mixed lane.
    """
    return _fold_divergence(result, "canceled_content", canceled_fail)


def _fold_divergence(result: VerifyResult, field_name: str, entries: Sequence[object]) -> VerifyResult:
    """Fold one strategy-independent axis's FAIL *entries* into a strategy axis result.

    *field_name* is the tuple field of :class:`Divergence` the entries belong to.
    The composition every such axis shares (see
    :func:`_merge_canceled_content_into_result` for the canceled-content one): a
    REFUSE wins unchanged, no entries is a no-op, a PASS becomes a FAIL carrying
    only these entries, and a FAIL gets them appended to that field while keeping
    its other axes.
    """
    if result.status is VerifyStatus.REFUSE or not entries:
        return result
    existing = result.divergence or Divergence()
    return VerifyResult.failed(replace(existing, **{field_name: (*getattr(existing, field_name), *entries)}))


class MergeOutcomeVerifier:
    """Verifies the merge outcome against the approved-WP claim by reachability.

    Constructed with the repository root; :meth:`verify` is pure with respect to
    the repository — it reads git refs and NEVER mutates (a FAIL/REFUSE leaves
    the ref store, worktrees, and merge state exactly as found).
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo = repo_root

    def verify(self, target_ref: str, approved_wp_set: ApprovedWpCommitSet) -> VerifyResult:
        """Return PASS / FAIL(divergence) / REFUSE for the tree at *target_ref*.

        Order (fail-closed first, so a claim that cannot be evaluated never
        reaches the reachability checks). Steps 1-4 are **strategy-independent**
        — they run for squash too (#5001 FOLD-1: pre-fix the squash early-return
        short-circuited to PASS before the vacuous-manifest check, so an
        empty-claim squash passed vacuously, defeating PP-F3):

        1. an explicit ``refusal`` on the claim → REFUSE;
        2. an unresolved/unmaterialized coord surface → REFUSE;
        3. an empty claim while the manifest lists WPs → REFUSE (PP-F3);
        4. (mixed-lane canceled-content axis, #5046 WP05) a mixed lane's
           canceled-with-provenance WP whose content on the target can neither
           be proven absent nor a merge of the canceled change with an
           independent one → REFUSE; an unresolved window base while entries
           exist → REFUSE; unsuperseded canceled-content entries are collected
           as FAIL candidates and merged into whichever axis below runs next
           (a REFUSE from either axis wins; a FAIL from both axes combines);
        4b. (approved-content presence axis, #5571) an approved lane's final content
           absent from / unchanged on the target with no later approved lane built
           atop it superseding the path → FAIL candidate ``APPROVED_CONTENT_MISSING``
           (merged like step 4's; a git probe error → REFUSE);
        5. (squash / ``verify_reachability=False``) the squash-sound closed-world
           BLOB-attribution axis (#5013 WS1): a production claim with empty
           authorship or a ``None`` window base → REFUSE, a git probe error →
           REFUSE, a target A/M path whose blob is authored by no approved lane →
           FAIL(un-attributable); a hand-built (non-production) claim → PASS;
        6. (production merge/rebase claim) an unresolvable excluded window base →
           REFUSE (#5001 FOLD-3: the excluded/closed-world axes cannot be evaluated);
        7. any approved SHA unreachable from *target_ref* → FAIL(missing);
        8. any excluded SHA/patch-id reachable from *target_ref* → FAIL(excluded);
        9. (closed-world) any CONTENT commit in the merge window attributable to
           no approved WP → FAIL(un-attributable);
        10. a git probe error while scanning the window → REFUSE (#5001 FOLD-3);
        11. otherwise → PASS (or FAIL, if step 4 collected canceled-content entries).
        """
        # Claim integrity is STRATEGY-INDEPENDENT (#5001 FOLD-1) and has ONE
        # authority (#5338): the same predicate refuses at claim time, before any
        # mutation, so a claim reaching this gate normally passes it. The empty-claim
        # check stays hoisted ABOVE the squash early-return (PP-F3).
        refusal = claim_integrity_refusal(approved_wp_set)
        if refusal is not None:
            return VerifyResult.refused(refusal)

        # Mixed-lane canceled-content axis (#5046 WP05): strategy-independent,
        # same as the claim-integrity checks above — it runs for squash too.
        canceled_fail, canceled_refuse = self._canceled_content_divergence(target_ref, approved_wp_set)
        if canceled_refuse is not None:
            return VerifyResult.refused(canceled_refuse)

        # #5571: an approved lane's final content absent from / not applied to the
        # target. Strategy-independent: the ancestry skip (`_lane_already_integrated`)
        # hides it under both squash and merge.
        missing_content, missing_refuse = self._approved_content_divergence(target_ref, approved_wp_set)
        if missing_refuse is not None:
            return VerifyResult.refused(missing_refuse)

        # #5569/#5613: a fully-canceled dependency lane's content carried by an
        # approved lane. Strategy-independent; never lifted by an attestation.
        carried, carried_refuse = self._canceled_dependency_divergence(target_ref, approved_wp_set)
        if carried_refuse is not None:
            return VerifyResult.refused(carried_refuse)

        # Squash (and any strategy that does not preserve content identity):
        # claim integrity held, but SHA/patch-id reachability is unsound (a squash
        # destroys lane-tip SHAs AND per-commit patch-ids). The squash-sound
        # closed-world BLOB-attribution axis runs instead (#5013 WS1). Every
        # fail-closed guard — empty authorship, an unresolvable window base, a git
        # probe error — fires INSIDE that branch, strictly above any PASS (F1
        # corollary), so a squash can no longer short-circuit to a vacuous pass the
        # way the pre-#5013 early-return did.
        if not approved_wp_set.verify_reachability:
            strategy_result = self._verify_squash_content(target_ref, approved_wp_set)
        # Reachability-path fail-closed (#5001 FOLD-3): a production claim
        # (``enforce_closed_world``) whose excluded window base could not be
        # resolved cannot evaluate the excluded/closed-world axes at all. Skipping
        # them silently collapsed to PASS (fail-OPEN); refuse instead.
        elif approved_wp_set.enforce_closed_world and approved_wp_set.excluded_window_base is None:
            strategy_result = VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        else:
            strategy_result = self._verify_merge_reachability(target_ref, approved_wp_set)
        with_canceled = _merge_canceled_content_into_result(strategy_result, canceled_fail)
        with_missing = _fold_divergence(with_canceled, "approved_content_missing", missing_content)
        return _with_attribution_hint(_fold_divergence(with_missing, "canceled_reachable_via_dependency", carried), approved_wp_set)

    def _verify_merge_reachability(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """The Tier-0 merge/rebase axis: per-SHA reachability + excluded/closed-world.

        Extracted from :meth:`verify` (Sonar complexity ceiling) — steps 7-10 of
        its docstring, unchanged in behaviour.
        """
        try:
            missing = self._missing_approved(target_ref, claim)
            excluded = self._reachable_excluded(target_ref, claim)
            unattributable = self._unattributable_content(target_ref, claim)
        except GitProbeError as exc:
            # A window probe errored mid-scan (#5001 FOLD-3): we cannot prove the
            # tree is clean, so refuse rather than pass on unevaluated content.
            return VerifyResult.refused(f"a git probe failed while verifying the merge window: {exc}")
        if missing or excluded or unattributable:
            return VerifyResult.failed(
                Divergence(
                    missing_approved=tuple(missing),
                    reachable_excluded=tuple(excluded),
                    unattributable_content=tuple(unattributable),
                )
            )
        return VerifyResult.passed()

    def _canceled_content_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[CanceledPathState], str | None]:
        """Mixed-lane canceled-content axis (D-4, contract C3; #5046 WP05).

        Evaluates every :class:`CanceledPathState` :attr:`ApprovedWpCommitSet.
        canceled_content` entry the claim builder resolved. Returns
        ``(fail_entries, refuse_reason)`` — a non-``None`` *refuse_reason* means
        the caller must REFUSE outright (claim/window-base integrity, or one
        entry whose target state is a merge of the canceled change with an
        independent one — R2); *fail_entries* otherwise holds every entry whose
        canceled content is still unsuperseded on the target (C3 rows 4-5),
        to be merged into whichever strategy axis runs next. A no-op — ``([],
        None)`` — when the claim carries no canceled-content entries at all
        (every existing claim, and every non-mixed-lane production claim).
        """
        if not claim.canceled_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        fail_entries: list[CanceledPathState] = []
        try:
            for entry in sorted(claim.canceled_content, key=lambda e: (e.lane_id, e.wp_id, e.path)):
                target_state = path_state_at(self._repo, target_ref, entry.path)
                window_state = path_state_at(self._repo, window_base, entry.path)
                if target_state == entry.canceled_state:
                    # C3 rows 4-5: the target still carries the canceled state.
                    # FAIL unless the window base ALSO already carried it AND the
                    # pre-state was merely inherited (never produced on the lane
                    # by a surviving commit) — R4.
                    if window_state != entry.canceled_state or entry.pre_state_by_survivor:
                        fail_entries.append(entry)
                    continue
                if target_state == entry.pre_state or target_state == window_state:
                    continue  # C3 row 3: the canceled change did not land.
                if entry.wp_id in claim.attested_canceled_wp_ids:
                    continue  # FR-012: the operator attested this WP's content is superseded.
                return fail_entries, _refuse_merged_independent_change(entry)
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying the canceled-content window: {exc}"
        return fail_entries, None

    def _approved_content_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[MissingApprovedContent], str | None]:
        """#5571: approved lane content absent from the target, as ``(missing, refuse_reason)``.

        For every approved code lane's final authored path state the target must
        hold it, unless a later approved lane built atop that lane superseded the
        path, the lane left the path net unchanged, or the target moved the path
        itself since the lane was cut (:func:`unmet_approved_content`). Paths a
        canceled WP touches (``canceled_content`` -- judged by its own axis)
        and mission bookkeeping are not judged here. A no-op for a claim without
        ``approved_lane_content`` (every hand-built claim). The probe is read-only;
        a failing FAIL rolls back through the single rollback authority in the
        executor, exactly like every other divergence.
        """
        if not claim.enforce_closed_world or not claim.approved_lane_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        canceled_paths = frozenset(entry.path for entry in claim.canceled_content)
        try:
            missing = unmet_approved_content(
                claim.approved_lane_content,
                target_state=lambda path: path_state_at(self._repo, target_ref, path),
                base_state=lambda path: path_state_at(self._repo, window_base, path),
                skip=lambda path: path in canceled_paths or self._is_bookkeeping_path(path, claim),
                state_at=lambda ref, path: path_state_at(self._repo, ref, path),
            )
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying approved content presence: {exc}"
        return missing, None

    def _canceled_dependency_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[CanceledDependencyContent], str | None]:
        """#5569/#5613: carried canceled-dependency content on the target, as ``(hits, refuse_reason)``.

        An entry is a hit when the target holds the state the canceled commit left
        at its path and the window base did not already hold it (then this
        consolidation did not ship it). A no-op when the claim carries none.
        """
        if not claim.canceled_dependency_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        hits: list[CanceledDependencyContent] = []
        try:
            for entry in sorted(claim.canceled_dependency_content, key=lambda e: (e.carrier_lane_id, e.canceled_lane_id, e.path)):
                if path_state_at(self._repo, target_ref, entry.path) != entry.state:
                    continue
                if path_state_at(self._repo, window_base, entry.path) != entry.state:
                    hits.append(entry)
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying canceled dependency content: {exc}"
        return hits, None

    @staticmethod
    def _refusal_reason(claim: ApprovedWpCommitSet) -> str | None:
        # Fail-closed claim integrity — applies to BOTH strategies, ahead of the
        # (strategy-dependent) content reachability checks.
        if claim.refusal is not None:
            return claim.refusal
        if not claim.surface_resolved:
            return "coordination surface is unresolved or unmaterialized"
        return None

    def _missing_approved(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        missing: list[tuple[str, str]] = []
        for wp_id, shas in claim.approved.items():
            for sha in shas:
                if not sha_reachable_from(self._repo, sha, target_ref):
                    missing.append((wp_id, sha))
        return missing

    def _reachable_excluded(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        # Non-vacuous even when the canceled set is empty: both loops always
        # run; an empty excluded set simply yields no matches (never a silent
        # short-circuit to PASS). The patch-id axis catches cherry-picked /
        # re-lettered copies a SHA match would miss.
        reachable: list[tuple[str, str]] = []
        for sha in claim.excluded_shas:
            if sha_reachable_from(self._repo, sha, target_ref):
                reachable.append((sha, patch_id_of(self._repo, sha)))
        if claim.excluded_patch_ids and claim.excluded_window_base is not None:
            window = self._window_patch_ids(claim.excluded_window_base, target_ref, claim)
            already = {pid for _sha, pid in reachable}
            for pid in claim.excluded_patch_ids:
                if pid in window and pid not in already:
                    reachable.append(("", pid))
        return reachable

    def _window_patch_ids(self, window_base: str, target_ref: str, claim: ApprovedWpCommitSet) -> set[str]:
        """Patch-ids of the window ``window_base..target`` that a canceled WP's change can be reached through.

        With no pre-Mission history this is :func:`patch_ids_in_range`, unchanged and with no extra
        probe (NFR-001/NFR-002). Otherwise (#7560) a window commit that IS pre-Mission history,
        by exact SHA, does not count: a canceled WP's patch-id equal to a pre-Mission commit's is
        reported only when another window commit carries it. A re-lettered copy of a pre-Mission
        commit (new SHA, same patch) still counts (fail-closed residual). The per-commit cost
        equals :func:`patch_ids_in_range`'s.
        """
        ids: set[str]
        if not claim.pre_mission_shas:
            ids = patch_ids_in_range(self._repo, window_base, target_ref)  # typed local: the probe module is mypy-skipped (#7334)
            return ids
        ids = set()
        for sha in commits_in_range(self._repo, window_base, target_ref):
            if sha in claim.pre_mission_shas:
                continue
            pid: str = patch_id_of(self._repo, sha)
            if pid:
                ids.add(pid)
        return ids

    def _unattributable_content(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        """Closed-world axis: window CONTENT commits not attributable to any approved WP.

        Every content commit reachable in the merge window
        (``excluded_window_base..target``) must be attributable — by SHA or
        patch-id — to an approved WP's OWN authorship (:attr:`authored_shas` /
        :attr:`authored_patch_ids`, the first-parent spine of approved lanes). A
        content commit that is not is a removed/canceled WP's commit that rode a
        carrier lane onto the target (#4945/#4977/#4981) — it is returned as a
        ``(sha, patch_id)`` divergence.

        A commit in :attr:`ApprovedWpCommitSet.external_dependency_shas` is NOT a
        divergence: that set is the verified result of the operator's explicit
        ``--dependency-ref`` declaration (#6771), and its commits are the external
        dependency a work-package branch brought in — content that predates the mission's own work,
        with the same standing as commits already on the target. The set is empty
        unless the operator declared a ref that passed every guard, so this never
        widens attribution on its own (see
        :func:`resolve_external_dependency_refs`).

        Pre-Mission history (#7560) has the same standing: a commit in
        :attr:`ApprovedWpCommitSet.pre_mission_shas` (``window_base..mission_base``, history the
        target lacks below the Mission base) is not a divergence. The exemption is by exact SHA
        only: a re-lettered copy of a pre-Mission commit (new SHA, same patch, e.g. after a
        rebase) is still judged as window content (fail-closed residual).

        NON-content commits are never flagged: a merge commit that adds nothing beyond
        its parents (empty ``--remerge-diff``, #7307; a merge with its own content is
        content, attributable only as an approved lane's reviewed dependency merge) and
        spec-kitty housekeeping commits (status/meta/matrix/retrospective
        projections — every changed path is bookkeeping) are excluded from the
        content set so a legitimate merge never false-fails (NFR-004). Bounded to
        the window — O(#window commits), never O(repo history) (NFR-003).

        Off unless ``enforce_closed_world`` is set (only the production claim
        builder turns it on), so a hand-built claim keeps the pre-widening
        behavior; also a no-op when the window base is unknown.
        """
        return self._unattributable_in((target_ref,), claim)

    def _unattributable_in(self, refs: Sequence[str], claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        """The closed-world window scan, over every commit *refs* reach (ONE authority).

        :meth:`_unattributable_content` scans the landed target under merge / rebase; the
        ``--dry-run`` forecast (#6771) scans the refs a merge / rebase landing WOULD
        introduce (the mission branch, its lanes and the target) so the refusal is
        predictable before any ref moves. Both run this same per-commit filter. A squash
        run never runs it (:meth:`_verify_squash_content` attributes blobs instead), so
        the forecast routes a squash through :meth:`forecast_content_verdict` (#7244).
        """
        if not claim.enforce_closed_world or claim.excluded_window_base is None:
            return []
        unattributable: dict[str, str] = {}
        for ref in refs:
            for sha in commits_in_range(self._repo, claim.excluded_window_base, ref):
                if sha in unattributable:
                    continue
                pid = self._unattributable_patch_id(sha, claim)
                if pid is not None:
                    unattributable[sha] = pid
        return list(unattributable.items())

    def _unattributable_patch_id(self, sha: str, claim: ApprovedWpCommitSet) -> str | None:
        """*sha*'s patch-id when it is un-attributable window content, else ``None`` (one commit of the scan).

        A merge commit is judged by what it adds beyond its parents (#7307,
        :func:`merge_own_changed_paths`), never by its ``--cc`` patch-id: a clean merge
        adds nothing; a resolution is content that only an approved lane's own
        dependency merge (by SHA, :func:`_own_dependency_merges`) attributes.
        """
        if sha in claim.authored_shas:
            return None  # an approved WP's own authorship, or its lane's own dependency merge (#7307)
        if sha in claim.external_dependency_shas:
            return None  # a declared, verified external dependency (#6771) — predates the window
        if sha in claim.pre_mission_shas:
            return None  # history below the Mission base the target lacks (#7560) — predates the Mission
        if is_merge_commit(self._repo, sha):
            own_paths = merge_own_changed_paths(self._repo, sha)
            if not any(not self._is_bookkeeping_path(path, claim) for path in own_paths):
                return None  # a clean merge, or one resolving only bookkeeping — no content of its own
            # ``patch_id_of`` comes from a mypy-skipped module (#7334): the typed
            # local keeps the return honest instead of leaking ``Any``.
            merge_pid: str = patch_id_of(self._repo, sha)
            return merge_pid
        pid: str = patch_id_of(self._repo, sha)
        if not pid:
            return None  # empty diff — never content
        if not self._commit_is_content(sha, claim):
            return None  # spec-kitty housekeeping — status/meta/matrix/retrospective
        if pid in claim.authored_patch_ids:
            return None  # a copy of an approved WP's own change
        return pid

    def forecast_content_verdict(self, landing_refs: Sequence[str], claim: ApprovedWpCommitSet, *, squashed_tree: str | None) -> VerifyResult:
        """The content verdict the real run's strategy would reach, judged before the landing (#7244).

        The ``--dry-run`` forecast's ONE entry into this verifier, so the preview runs the
        content check the real run runs, never a second implementation of it:

        * *squashed_tree* given (a squash whose clean squash the forecast staged): the
          squash-sound blob attribution :meth:`_verify_squash_content` over that tree. The tree
          holds only the mission branch, because lanes are not folded in yet (#7268), so on a
          PASS the lane refs still get the per-commit scan: without it, un-attributable lane
          content the real squash gate refuses would forecast clean (#6771);
        * otherwise (merge / rebase, or no squash could be previewed): the per-commit
          closed-world scan :meth:`_unattributable_in` over *landing_refs*.

        A git probe error during the per-commit scan propagates as :class:`GitProbeError`
        (the forecast renders it); the squash check REFUSEs on one itself.
        """
        if squashed_tree is not None:
            verdict = _with_attribution_hint(self._verify_squash_content(squashed_tree, claim), claim)
            if verdict.status is not VerifyStatus.PASS:
                return verdict
            landing_refs = landing_refs[1:]
        unattributable = self._unattributable_in(landing_refs, claim)
        if not unattributable:
            return VerifyResult.passed()
        return _with_attribution_hint(VerifyResult.failed(Divergence(unattributable_content=tuple(unattributable))), claim)

    def _verify_squash_content(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """Squash-sound content verdict via closed-world BLOB attribution (#5013 WS1).

        A squash merge preserves neither lane-tip SHAs nor per-commit patch-ids, so
        the reachability/patch-id axes are inert under it. This axis compares
        **tree/blob content** instead, which a squash DOES preserve: every
        non-bookkeeping Added/Modified path of the aggregate squash diff
        ``B..target`` must carry a blob authored by an approved lane
        (:attr:`ApprovedWpCommitSet.authored_blobs`); one that is not is
        removed/canceled content that shipped ⇒ FAIL ⇒ the executor's existing
        rollback path reverts the squash advance.

        The axis is opt-in: only a production claim (``enforce_closed_world``, set by
        :func:`build_approved_wp_set`) runs it. A hand-built claim keeps the
        pre-#5013 deferral PASS byte-for-byte. Fail-closed guards fire ABOVE any
        PASS (F1 corollary): a ``None`` window base and a git probe error REFUSE
        rather than pass on unevaluated content.

        Empty ``authored_blobs`` **and** empty ``authored_deletions`` (#5022 — a
        lane whose sole approved contribution is a deletion legitimately has an
        empty ``authored_blobs`` but a non-empty ``authored_deletions``, which is
        real authorship authority, not an absence of one) is split by whether any
        approved lane RESOLVED to commits. When the claim carries approved commit
        SHAs but no authored blobs/deletions at all, the axis cannot attribute
        against a claim it should have been able to build ⇒ REFUSE (fail-closed).
        When NO approved lane resolved to commits at all — the tolerant "lane
        branch absent / already consolidated" state the claim builder legitimately
        yields as empty tuples (``{"WP01": ()}``) — there is no authorship
        authority to attribute against, so the axis defers to the pre-#5013 PASS
        rather than false-fail every target path (NFR-004). This matches the claim
        builder's own lane-resolution tolerance (:func:`_lane_tip_commits` /
        :func:`_lane_first_parent_spine`).
        """
        if not claim.enforce_closed_world:
            return VerifyResult.passed()
        if not claim.authored_blobs and not claim.authored_deletions:
            if any(shas for shas in claim.approved.values()):
                return VerifyResult.refused(_REFUSE_EMPTY_AUTHORED_BLOBS)
            return self._verify_squash_vacuous_authorship(target_ref, claim)
        window_base = claim.excluded_window_base
        if window_base is None:
            return VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        try:
            unattributable_blobs, unattributable_deletions = self._unattributable_content_squash(target_ref, claim, window_base)
        except GitProbeError as exc:
            return VerifyResult.refused(f"a git probe failed while verifying the squash window: {exc}")
        if unattributable_blobs or unattributable_deletions:
            return VerifyResult.failed(
                Divergence(
                    unattributable_blobs=tuple(unattributable_blobs),
                    unattributable_deletions=tuple(unattributable_deletions),
                )
            )
        return VerifyResult.passed()

    def _verify_squash_vacuous_authorship(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """FIX C (#5001 landing remediation): no lane resolved commits AND
        ``authored_blobs`` is empty — there is no authorship authority at all
        (distinct from the F1-corollary case above, where ``approved`` names
        non-empty SHA tuples but authorship failed to build).

        The pre-#5001 behavior PASSed unconditionally here — a fail-OPEN vacuous
        PASS: a target that carries real, un-evaluated content ships with no
        attribution check ever running. Now the window diff is inspected; a
        non-bookkeeping Added/Modified path with no authorship authority behind
        it REFUSEs (fail-closed) rather than passing silently. A genuinely
        content-free window (every window path absent, or bookkeeping-only)
        keeps the original PASS deferral (NFR-004) — this matches the claim
        builder's own tolerance for a fully-canceled / already-consolidated lane
        (:func:`_lane_tip_commits` / :func:`_lane_first_parent_spine`).
        """
        window_base = claim.excluded_window_base
        if window_base is None:
            return VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        try:
            has_content = self._window_has_non_bookkeeping_change(target_ref, claim, window_base)
        except GitProbeError as exc:
            return VerifyResult.refused(f"a git probe failed while verifying the squash window: {exc}")
        if has_content:
            return VerifyResult.refused(_REFUSE_NO_AUTHORSHIP_AUTHORITY)
        return VerifyResult.passed()

    def _window_has_non_bookkeeping_change(self, target_ref: str, claim: ApprovedWpCommitSet, window_base: str) -> bool:
        """True iff ``window_base..target`` carries any un-authorized A/M/D path.

        Inherited history is not content (the same two sources the squash axes exempt, through
        :func:`_inherited_deletion` / :func:`_inherited_blob`): a ``D`` path a declared dependency
        (#6771) or pre-Mission history (#7560) last deleted, and an A/M path whose target blob is
        such history's final blob. Only the blob check reads a blob, and only when an inherited
        blob set is non-empty.

        Mirrors :meth:`_unattributable_content_squash`'s bookkeeping + deletion-
        authority filter; it reads a blob only for the inherited-blob check above — this
        only asks WHETHER attributable content exists, never WHICH blob it is (there is no
        authorship set to attribute against here; ``claim.authored_deletions`` is
        always empty in the caller's context, :meth:`_verify_squash_vacuous_authorship`
        — no lane resolved any commits — so a ``D`` path here is never skipped as
        authored, only as bookkeeping). A bookkeeping OR authored-deletion ``D``
        path is not content (#5022); any other path — Added, Modified, or an
        un-authored Deleted — is.
        """
        for status, path in changed_paths_in_range(self._repo, window_base, target_ref):
            if self._is_bookkeeping_path(path, claim):
                continue
            if status.startswith("D"):
                if path in claim.authored_deletions or _inherited_deletion(path, claim):
                    continue  # an approved lane's own, or inherited (#6771, #7560), final-state deletion — not content
                return True
            if (claim.pre_mission_blobs or claim.external_dependency_blobs) and _inherited_blob(path, blob_id_at(self._repo, target_ref, path), claim):
                continue  # inherited final content (#6771, #7560) — not content of this Mission
            return True
        return False

    def _unattributable_content_squash(self, target_ref: str, claim: ApprovedWpCommitSet, window_base: str) -> tuple[list[tuple[str, str]], list[str]]:
        """``(unattributable_blobs, unattributable_deletions)`` in ``B..target`` (#5013 / #5022).

        Iterates ``git diff --name-status --no-renames window_base..target``
        (:func:`changed_paths_in_range`). A mission-bookkeeping path is skipped
        entirely (status/meta/matrix/retrospective/planning churn — never content).
        For each **Added/Modified** path, reads the target blob (:func:`blob_id_at`;
        an unexpected probe error propagates as :class:`GitProbeError` ⇒ the caller
        REFUSEs); a ``(path, blob)`` absent from
        :attr:`ApprovedWpCommitSet.authored_blobs` is unattributable. For each
        **Deleted** path (#5022 — previously unconditionally skipped, the silent
        data-loss escape), the path is attributable iff it is in
        :attr:`ApprovedWpCommitSet.authored_deletions` (an approved lane's own
        first-parent spine ends by deleting it), in a declared dependency's deletions (#6771) or in
        the pre-Mission deletions (#7560); otherwise it is a canceled/removed
        WP's deletion that rode a carrier lane onto the target and is unattributable.
        Bounded by the squash diff size (NFR-003).

        An Added/Modified path whose blob is NOT in ``authored_blobs`` (a single
        approved lane's own final content) gets one more, strictly fail-closed
        chance: :func:`is_legitimate_three_way_resolution` (terminus-merge-
        resolution-attribution / #5051-adjacent, FR-002/003) — a path authored by
        EXACTLY TWO approved lanes whose target blob equals the deterministic
        ``git merge-tree`` resolution of those two lanes' own contributions is a
        genuine merge resolution, not removed content, and is attributed too.
        Every other shape (>2 lanes, a single-lane mismatch, binary, a
        conflicting resolution, git<2.38) stays unattributable — this second
        chance never attributes vacuously; see that function's docstring for the
        full fail-closed ordering.
        """
        unattributable_blobs: list[tuple[str, str]] = []
        unattributable_deletions: list[str] = []
        for status, path in changed_paths_in_range(self._repo, window_base, target_ref):
            if self._is_bookkeeping_path(path, claim):
                continue  # status/meta/matrix/retrospective/planning churn — not content
            if status.startswith("D"):
                if not _deletion_attributed(path, claim):
                    unattributable_deletions.append(path)
                continue
            blob = blob_id_at(self._repo, target_ref, path)  # raises → REFUSE (F1)
            if (path, blob) in claim.authored_blobs:
                continue
            if not self._attributed_outside_mission(path, blob, claim):
                unattributable_blobs.append((path, blob))
        return unattributable_blobs, unattributable_deletions

    def _attributed_outside_mission(self, path: str, blob: str, claim: ApprovedWpCommitSet) -> bool:
        """True when an Added/Modified *path* at *blob* is attributable beyond a single approved lane's own blob.

        The three second chances of :meth:`_unattributable_content_squash`, in order: a declared,
        verified external dependency's final content (#6771), the pre-Mission final content the
        target lacks (#7560), and a legitimate three-way resolution of a path two approved lanes
        both authored. Each is keyed on the exact ``(path, blob)``, so a post-base change of the
        path (a different blob) is not covered.
        """
        if _inherited_blob(path, blob, claim):
            return True
        return is_legitimate_three_way_resolution(self._repo, claim, path, blob)

    def _commit_is_content(self, sha: str, claim: ApprovedWpCommitSet) -> bool:
        """True when *sha* changes at least one path that is NOT mission bookkeeping.

        A commit is spec-kitty housekeeping (NOT content) when every path it
        changed is either toolchain-generated churn (the canonical status/meta/
        matrix denylist) or lives under the mission's planning/status directory
        (``planning_prefix`` — covers the retrospective/tasks/plan artifacts that
        are not status-state kinds). A commit with any other changed path is real
        content, subject to the closed-world attribution check above.
        """
        paths = changed_paths_of(self._repo, sha)
        if not paths:
            return False
        return any(not self._is_bookkeeping_path(path, claim) for path in paths)

    @staticmethod
    def _is_bookkeeping_path(path: str, claim: ApprovedWpCommitSet) -> bool:
        """True when *path* is the MISSION's OWN planning/toolchain surface.

        Thin delegation to the module-level :func:`_is_bookkeeping` (extracted,
        mixed-lane-authorship-soundness / #5046 WP05, so
        :func:`build_approved_wp_set` can hand ``wp_attribution.resolve_canceled_wp``
        the SAME denylist via ``functools.partial`` — never a duplicate one — even
        though the claim does not exist yet at that call site). See that
        function's docstring for the full anchoring rules.
        """
        return _is_bookkeeping(path, claim.mission_slug, claim.planning_prefix)


def _inherited_deletion(path: str, claim: ApprovedWpCommitSet) -> bool:
    """True when *path*'s final deletion is inherited history: a declared dependency's (#6771) or pre-Mission (#7560)."""
    return path in claim.external_dependency_deletions or path in claim.pre_mission_deletions


def _inherited_blob(path: str, blob: str, claim: ApprovedWpCommitSet) -> bool:
    """True when ``(path, blob)`` is inherited history's final content: a declared dependency's (#6771) or pre-Mission (#7560)."""
    return (path, blob) in claim.external_dependency_blobs or (path, blob) in claim.pre_mission_blobs


def _deletion_attributed(path: str, claim: ApprovedWpCommitSet) -> bool:
    """True when a squash-window deletion of *path* is an approved lane's or inherited history's."""
    return path in claim.authored_deletions or _inherited_deletion(path, claim)


def is_legitimate_three_way_resolution(
    repo_root: Path,
    claim: ApprovedWpCommitSet,
    path: str,
    target_blob: str,
) -> bool:
    """True iff *target_blob* is the deterministic 2-way merge of *path*'s two
    approved-lane contributions (Seam A merge-resolution recognizer,
    terminus-merge-resolution-attribution / #5051-adjacent, FR-002/FR-003).

    Called ONLY as :meth:`MergeOutcomeVerifier._unattributable_content_squash`'s
    second chance, after the ``authored_blobs`` single-lane fast path has already
    missed — every guard below fires strictly ABOVE any attribution (F1
    corollary), so this never attributes vacuously:

    1. *path* absent from :attr:`ApprovedWpCommitSet.multi_lane_paths` (not
       authored by exactly two approved lanes: zero, one, or three-or-more) →
       ``False`` — the simulation never even runs (Decision 2, ``research.md``:
       2-way ``merge-tree`` folding is order-dependent/nondeterministic for N>2).
    2. The installed git does not support ``git merge-tree --write-tree`` (git<
       2.38, :func:`~specify_cli.consolidation.git_probes.merge_tree_write_tree_available`)
       → ``False`` (Decision 3: fail-closed fallback, no unsound raw-``merge-
       file`` substitute).
    3. Smuggled-tip guard (#5124 landing fold — closes the reopened #4977
       carrier-lane threat): ``lane_commit`` is a raw lane TIP and CAN be a
       merge commit. ``three_way_merge_blob`` below feeds it that commit's
       FULL tree, not just its first-parent authorship — so if a contributing
       lane's tip is a merge commit that smuggled a disjoint SECOND-parent hunk
       into *path* (content ``_final_authored_walk``/``authored_blobs``
       deliberately excludes, being first-parent-only), the simulation would
       reproduce the smuggled hunk right along with the legitimate edit, and a
       target that shipped it would match. The guard: for each of the two
       contributions, the lane's OWN tip-tree blob at *path*
       (:func:`~specify_cli.consolidation.git_probes.blob_id_at`) must equal that
       contribution's recorded first-parent-authored blob
       (:attr:`LaneContribution.authored_blob`) — the value the same spine walk
       already vetted as pure first-parent authorship. A mismatch means the
       tip carries unvetted content beyond what was authored → refuse to
       simulate → ``False`` (the path stays unattributable, FAILing the gate
       and CAS-reverting the target, never shipping the smuggled hunk). A
       :class:`~specify_cli.consolidation.git_probes.GitProbeError` from ``blob_id_at``
       here is NOT caught — it propagates to the caller
       (:meth:`MergeOutcomeVerifier._unattributable_content_squash`), which lets
       it bubble to :meth:`MergeOutcomeVerifier._verify_squash_content`'s
       ``except GitProbeError`` → REFUSE, the fail-closed outcome for an
       unevaluable probe. The legitimate clean disjoint-hunk case (each lane's
       tip IS its own authored blob — no second parent, or a merge commit whose
       combined diff was empty) passes this guard unchanged.
    4. Otherwise, simulate the 2-way merge of the two lanes' OWN commits
       (:func:`~specify_cli.consolidation.git_probes.three_way_merge_blob` — the ONLY
       inputs are those two commits; git derives their common ancestor, so no
       third input, e.g. a canceled/removed hunk, can ever be smuggled in) and
       compare its result for *path* to *target_blob*. A conflicting resolution,
       a binary conflict, or an absent result path all come back as ``None``
       from the simulation and compare unequal → ``False``.

    This is the PER-SEAM recognizer (research open-item 3): it is intentionally
    NOT physically shared with Seam B's presence-under-union check — blob-merge
    and block-presence are conceptually and mechanically distinct questions.
    """
    contributions = claim.multi_lane_paths.get(path)
    if contributions is None:
        return False
    if not merge_tree_write_tree_available(repo_root):
        return False
    lane_a, lane_b = contributions
    for contribution in (lane_a, lane_b):
        if blob_id_at(repo_root, contribution.lane_commit, path) != contribution.authored_blob:
            return False
    resolved_blob: str | None = three_way_merge_blob(repo_root, lane_a.lane_commit, lane_b.lane_commit, path)
    return resolved_blob == target_blob


def claim_integrity_refusal(claim: ApprovedWpCommitSet) -> str | None:
    """Strategy-independent claim-integrity refusal (``verify()`` steps 1-3), or ``None``.

    #5338: the single claim-integrity authority for CLAIM time (acted on in
    ``_capture_reconciliation_claim`` before any mutation). It covers exactly the
    three strategy-independent checks: an explicit ``claim.refusal``, an
    unresolved coordination surface, and a claim that is empty while the manifest
    lists WPs. The squash "empty authored-blob set" REFUSE and every other
    content check stay gate-time (they need the post-merge target).

    ``MergeOutcomeVerifier.verify`` calls this same predicate for its steps 1-3,
    so claim time and gate time cannot drift.
    """
    reason = MergeOutcomeVerifier._refusal_reason(claim)
    if reason is not None:
        return reason
    if claim.is_vacuous_against_manifest:
        return f"derived claim is empty while the manifest lists {len(claim.manifest_wp_ids)} WP(s)"
    return None


__all__ = [
    "Divergence",
    "MergeOutcomeVerifier",
    "VerifyResult",
    "VerifyStatus",
    "_REFUSE_EMPTY_AUTHORED_BLOBS",
    "_REFUSE_NO_AUTHORSHIP_AUTHORITY",
    "_REFUSE_WINDOW_BASE_UNRESOLVED",
    "_RESTORE_IN_PROGRESS",
    "_fold_divergence",
    "_merge_canceled_content_into_result",
    "_refuse_merged_independent_change",
    "_with_attribution_hint",
    "claim_integrity_refusal",
    "is_legitimate_three_way_resolution",
]
