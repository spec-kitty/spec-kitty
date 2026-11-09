"""Claim record types of the terminus reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP10).

``ApprovedWpCommitSet`` (whole, field order unchanged: some constructions are positional) and the
content records it carries. Moved verbatim out of ``reconciliation.py``; that module re-exports every
name, so no caller changes (C-005, C-006).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from specify_cli.consolidation.wp_attribution import CanceledPathState, GapEntry


#: How the target fails to hold an approved lane's content (:class:`MissingApprovedContent`):
#: the path is not there at all, or it still holds the pre-consolidation state.
PresenceGap = Literal["absent", "unchanged"]


_GAP_ABSENT: PresenceGap = "absent"


_GAP_UNCHANGED: PresenceGap = "unchanged"


@dataclass(frozen=True)
class MissingApprovedContent:
    """One path whose approved final content is not on the target (#5571, ``APPROVED_CONTENT_MISSING``).

    ``wp_ids`` / ``lane_ids`` name every approved WP (and its lane) whose final
    authored state for ``path`` equals the unmet ``expected`` state, so a
    dependency chain names the WP that authored the content as well as the lane
    that carried it. ``expected`` is the blob the lane ended on, or ``None`` for a
    deletion that did not land. ``found`` is the :data:`PresenceGap`: ``"absent"``
    (the path is not on the target) or ``"unchanged"`` (the target still holds the
    pre-consolidation state).
    """

    wp_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    path: str
    expected: str | None
    found: PresenceGap


@dataclass(frozen=True)
class CanceledDependencyContent:
    """One path a fully-canceled dependency lane left on an approved lane (``CANCELED_REACHABLE_VIA_DEPENDENCY``).

    ``wp_ids`` are the canceled lane's WPs (the lane is the unit the allocator
    merges, so the content is named by all of them), ``canceled_lane_id`` is that
    lane and ``carrier_lane_id`` the approved lane whose first-parent spine carries
    its commit. ``state`` is the carrier lane's FINAL blob at ``path`` — the content
    the integrated target carries, which embeds the surviving canceled content even
    when an approved commit later appended to the same file (#5932) — or ``None`` when
    the path is absent in that final state.
    """

    wp_ids: tuple[str, ...]
    canceled_lane_id: str
    carrier_lane_id: str
    path: str
    state: str | None
    #: #6309: the canceled path when a carrier commit renamed it; ``path`` is then
    #: the new path, where the carried content lives and the target is compared.
    renamed_from: str | None = None


@dataclass(frozen=True)
class ApprovedLaneContent:
    """An approved code lane's FINAL authored state, per path (#5571 presence axis).

    The lane is the unit git integrates, so the final state is per lane and named
    by the lane's approved WPs. ``final_state`` maps a repo-relative path to the
    blob the lane's own first-parent spine ends on, or ``None`` when its final
    state for the path is a deletion (a rename contributes its source as ``None``).
    ``ancestors`` are the lane ids this lane transitively depends on: such a lane
    was built atop them, so its final state supersedes theirs for any path both
    hold. Built from the SAME spine walk as ``authored_blobs`` -- never a second one.

    The last three fields let the presence axis judge only the lane's OWN NET
    change (:func:`unmet_approved_content`); no path is read for them at claim
    build. ``tip`` is the lane tip. ``fork_point`` is the commit the lane was cut
    from (the first parent of its oldest own first-parent commit), the lane's own
    base. ``dependency_forks`` maps a dependency lane id to the commit of that
    lane this lane was built on. A hand-built content leaves them unset, which
    reads as "cut from the pre-consolidation target, and every held path is its own".
    """

    lane_id: str
    wp_ids: tuple[str, ...]
    ancestors: frozenset[str]
    final_state: Mapping[str, str | None]
    tip: str | None = None
    fork_point: str | None = None
    dependency_forks: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LaneContribution:
    """One approved lane's contribution to a multi-lane-authored content path,
    PER (lane, path) — never lane-only.

    ``terminus-merge-resolution-attribution`` / FR-009 (widened by the #5124
    landing fold's smuggled-tip guard). ``lane_commit`` is a raw SHA — the
    newest commit on the lane's own first-parent spine — never a branch name,
    so it stays resolvable via git's object store for the lifetime of the
    merge transaction even after a lane branch ref is deleted at teardown.
    ``lane_commit`` CAN be a merge commit (a lane's tip is whatever its own
    first-parent spine's newest commit is, merge or not); its FULL tree can
    therefore carry content beyond the lane's own first-parent authorship — a
    disjoint second-parent hunk merged in from an unrelated (e.g. removed)
    lane, the #4977 carrier mechanism. ``authored_blob`` is the fail-closed
    guard input that catches that: the lane's FINAL first-parent-AUTHORED blob
    for THIS path (the same value :attr:`ApprovedWpCommitSet.authored_blobs`
    would record for this (lane, path)), read straight from
    :func:`_final_authored_walk` at contribution-build time — never
    recomputed. :func:`is_legitimate_three_way_resolution` refuses to simulate
    unless each contributing lane's tip-tree blob at *path* equals this value,
    so a merge-commit tip that smuggled extra content can never feed the
    simulation. Used to supply
    :func:`~specify_cli.consolidation.git_probes.three_way_merge_blob`'s two merge
    inputs (via ``lane_commit``) plus the guard check (via ``authored_blob``);
    blob-identity attribution ITSELF (the actual accepted content) continues
    to come from :attr:`ApprovedWpCommitSet.authored_blobs`, never from here.
    """

    lane_id: str
    lane_commit: str
    authored_blob: str


@dataclass(frozen=True)
class ApprovedWpCommitSet:
    """The claim the verifier trusts — derived once per terminus transaction.

    ``approved`` maps each claimed WP id to its approved commit SHAs, read from
    **lane-branch git tips** (never status rows) after the approved-bound check
    (#5668) found each lane within what its approval stamps name. ``excluded_shas`` /
    ``excluded_patch_ids`` are the canceled/removed commits that must NOT be
    reachable from the target. ``manifest_wp_ids`` is the full set the manifest
    lists (the empty-vs-manifest fail-closed cross-check). ``excluded_window_base``
    bounds the patch-id scan to ``base..target`` (NFR-003). ``surface_resolved``
    is ``False`` and/or ``refusal`` is set when the claim could not be built
    fail-closed — the verifier then REFUSES instead of evaluating.
    """

    approved: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    excluded_shas: frozenset[str] = frozenset()
    excluded_patch_ids: frozenset[str] = frozenset()
    manifest_wp_ids: frozenset[str] = frozenset()
    excluded_window_base: str | None = None
    surface_resolved: bool = True
    refusal: str | None = None
    # Closed-world excluded check (S-D widening; #4945/#4977/#4981). The
    # TRACKED-excluded axis (``excluded_shas``/``excluded_patch_ids``, derived
    # from ``acceptably_canceled_wp_ids``) only names commits whose WP the status
    # surface still lists as canceled. A REMOVED WP's commit merged INTO an
    # approved carrier lane is in no lane / no status row, so the tracked axis
    # never names it and the lane-range approved set counts it as approved — it
    # ships. The closed-world axis closes that: every CONTENT commit in the merge
    # window (``excluded_window_base..target``) must be attributable to an approved
    # WP's OWN authorship (by SHA or patch-id); one that is not is a FAIL. The
    # authorship is the first-parent spine of every approved lane (``authored_*``),
    # so a commit smuggled in via a merge's second parent is never mistaken for
    # approved work. ``enforce_closed_world`` gates the whole check: only the
    # production claim builder (:func:`build_approved_wp_set`) turns it on, so a
    # hand-built claim (unit tests that populate only ``approved``) keeps the
    # pre-widening behavior byte-for-byte.
    enforce_closed_world: bool = False
    authored_shas: frozenset[str] = frozenset()
    authored_patch_ids: frozenset[str] = frozenset()
    # Squash-sound closed-world authorship (#5013 / WS1). The **FINAL**
    # first-parent-authored blob **per (lane, path)** across approved lanes, as
    # ``(repo_rel_path, blob_sha)`` tuples. Content identity (blob), never lane-tip
    # SHAs or per-commit patch-ids (both destroyed by squash), so it survives the
    # DEFAULT squash strategy. Taking the FINAL blob per (lane, path) — not the
    # union of every first-parent commit's blob — is the F5 crux: the union would
    # admit a superseded intermediate ``v1`` and false-PASS a canceled blob matching
    # it. Always the ``(path, blob)`` tuple, never blob-only (F10 — catches
    # identical-content-different-path). Populated by ``_collect_authored`` only in
    # the production claim builder; a hand-built claim leaves it empty and the squash
    # axis stays off (``enforce_closed_world`` unset), preserving pre-widening
    # behavior byte-for-byte.
    authored_blobs: frozenset[tuple[str, str]] = frozenset()
    # Squash-sound closed-world DELETION authority (#5022 / WP1). A path P is a
    # member iff, walking an approved lane's first-parent spine newest→oldest,
    # the FIRST (newest) commit that touches P DELETES it — i.e. the lane's own
    # final state for P is "deleted" (mirrors ``authored_blobs``'s "final blob
    # per path", the deletion analogue). A path added-then-deleted within a lane
    # is a member (final state deleted); a path deleted-then-re-added is NOT (its
    # final state is present, and it is in ``authored_blobs`` instead). Populated
    # by ``_collect_authored`` only in the production claim builder, in the SAME
    # spine walk that produces ``authored_blobs`` (:func:`_final_authored_walk`) —
    # a hand-built claim leaves it empty and the squash deletion axis then treats
    # every ``D`` path as unattributable unless it is bookkeeping, preserving
    # pre-#5022 behavior for any claim that never populates it.
    authored_deletions: frozenset[str] = frozenset()
    # Merge-resolution-aware Seam A attribution (terminus-merge-resolution-
    # attribution / #5051-adjacent, FR-009; smuggled-tip guard added by the
    # #5124 landing fold). For each content path authored by EXACTLY TWO
    # approved lanes (a path outside the disjoint-write-scope invariant
    # `_final_authored_walk` documents), the two contributing lanes' PER-PATH
    # :class:`LaneContribution`s — their still-resolvable pre-squash lane
    # commit SHAs (which CAN be a merge commit) plus, per (lane, path), the
    # lane's own first-parent-AUTHORED blob for that path (the guard input
    # that catches a merge-commit tip smuggling extra content — see
    # :class:`LaneContribution`). One ``LaneContribution`` is now recorded PER
    # (lane, path) — never one shared object reused across every path a lane
    # touches — because the authored blob differs per path.
    # Populated in the SAME first-parent spine walk that builds
    # ``authored_blobs`` (:func:`_collect_authored` / :func:`_final_authored_walk`)
    # — never a second walk. Absent (no key) for a single-lane path (the
    # existing ``authored_blobs`` fast path already attributes those) and for a
    # path touched by three-or-more approved lanes (2-way `merge-tree` folding
    # is order-dependent/nondeterministic for N>2 — Decision 2, ``research.md``
    # — so those stay fail-closed, never simulated). The "exactly two lanes"
    # count is still one contribution per (lane, path) — i.e. per lane per
    # path — so a path is a member iff exactly two DISTINCT lanes recorded a
    # contribution for it, unchanged by the per-path widening. Supplies
    # ``is_legitimate_three_way_resolution``'s two merge inputs AND its
    # fail-closed guard; it never itself supplies the FINAL blob identity that
    # is attributed — that authority stays with ``authored_blobs``.
    # Populated by ``_collect_authored`` only in the production claim builder; a
    # hand-built claim leaves it empty and the merge-resolution recognizer never
    # fires, preserving pre-widening behavior byte-for-byte.
    multi_lane_paths: Mapping[str, tuple[LaneContribution, LaneContribution]] = field(default_factory=dict)
    mission_slug: str | None = None
    # Repo-relative posix path of the mission's planning/status directory
    # (``kitty-specs/<slug>``). A window commit that touches ONLY paths under this
    # prefix (plus toolchain churn) is spec-kitty housekeeping, never content.
    planning_prefix: str | None = None
    # Content reachability (approved-SHA ancestry + excluded SHA/patch-id) is only
    # SOUND for ancestry-preserving strategies (merge/rebase): a squash merge
    # preserves neither lane-tip SHAs, per-lane tree equality, nor per-lane
    # patch-ids (verified empirically), AND the post-merge target carries
    # legitimate bookkeeping commits (mission_number bake, done-transition record)
    # that make even an aggregate mission→target tree comparison diverge. Proving
    # approved content landed under squash therefore requires the projection seam
    # WP07/WP08 own. When ``verify_reachability`` is ``False`` (squash), the
    # verifier still runs the squash-sound blob-attribution content axis (#5013,
    # :meth:`MergeOutcomeVerifier._unattributable_content_squash`) plus fail-closed
    # claim integrity (surface + refusal); only the per-SHA approved-reachability
    # check (structurally unsatisfiable once squash mints new SHAs) is deferred —
    # never false-failing a legitimate squash merge (NFR-004). Fail-closed
    # integrity applies to both strategies. ``True`` (merge/rebase — the Tier-0
    # clean-merge strategy) runs the full per-SHA reachability + excluded checks.
    verify_reachability: bool = True
    # Declared external dependency refs (#6771) and the sets they contribute, computed ONCE
    # by :func:`resolve_external_dependency_refs` in the production claim builder. The
    # verifier treats these exactly like content that predates the window: ``shas`` are
    # skipped by the closed-world commit axis (merge/rebase), ``blobs``/``deletions`` by the
    # squash blob/deletion axis. All four are empty for a hand-built claim and for a run with
    # no declaration, so the pre-#6771 behavior holds byte-for-byte (NFR-003). A declaration
    # never widens what is attributed to a WORK PACKAGE; it narrows what is flagged.
    external_dependency_refs: tuple[str, ...] = ()
    #: ``ref -> SHA`` each declared ref was verified against (:attr:`ExternalDependencyAttribution.pins`);
    #: the gate re-checks them so a ref moved after the claim refuses (``DEPENDENCY_REF_MOVED``).
    external_dependency_pins: Mapping[str, str] = field(default_factory=dict)
    external_dependency_shas: frozenset[str] = frozenset()
    external_dependency_blobs: frozenset[tuple[str, str]] = frozenset()
    external_dependency_deletions: frozenset[str] = frozenset()
    # Mixed-lane canceled-content axis (mixed-lane-authorship-soundness / #5046,
    # WP05). Every :class:`~specify_cli.consolidation.wp_attribution.CanceledPathState`
    # resolved for a canceled-with-provenance WP sharing an approved lane with a
    # surviving WP (contract C2 "mixed lane") that entered implementation. NOT
    # reused from ``excluded_shas``/``excluded_patch_ids``: those are SHA/patch-id
    # reachability, which (a) a squash destroys entirely, and (b) even under
    # merge/rebase only proves the canceled WP's OWN commit objects are
    # unreachable — never that a LATER survivor commit didn't carry the exact
    # same bytes forward unchanged (see the corrected ``_collect_excluded``
    # docstring). This axis compares per-path CONTENT instead (blob identity),
    # which both strategies preserve. Populated by ``build_approved_wp_set`` only
    # (via ``wp_attribution.resolve_canceled_wp``); a hand-built claim leaves it
    # empty, so :meth:`MergeOutcomeVerifier._canceled_content_divergence` is a
    # no-op and every existing claim keeps pre-#5046 behaviour byte-for-byte.
    canceled_content: frozenset[CanceledPathState] = frozenset()
    # Operator-attested canceled WPs (FR-012, ``canceled_attestation``): read
    # from the same event log the mixed-lane resolution reads. For these WPs the
    # verifier lifts the "merged with an independent change" REFUSE; a FAIL on
    # their visible canceled content still stands. Empty on a hand-built claim.
    attested_canceled_wp_ids: frozenset[str] = frozenset()

    # #5571: each approved CODE lane's FINAL authored state per path, in dependency
    # order (a lane after every lane it depends on; ties by lane id). The approved-
    # content presence axis (:meth:`MergeOutcomeVerifier._approved_content_divergence`)
    # requires the target to hold it unless a later approved lane built atop this
    # one superseded the path. A NEW field: the ``authored_*`` claim fields are
    # untouched. Populated by ``_collect_authored`` in the same spine walk as
    # ``authored_blobs``; a hand-built claim leaves it empty, which turns the axis off.
    approved_lane_content: tuple[ApprovedLaneContent, ...] = ()

    # #5569/#5613: per-path content a fully-canceled dependency lane left on an
    # approved ("carrier") lane's first-parent spine. The commits behind it are
    # already out of ``authored_*``, so the strategy axes fail on their own; this
    # field lets the verifier name the canceled WP, both lanes and the stable code.
    # Empty on a hand-built claim and on every mission without such a lane.
    canceled_dependency_content: frozenset[CanceledDependencyContent] = frozenset()

    # #5668: the lane tip (branch name, SHA) the approved-bound check validated for every
    # code lane it covered, each resolved once when the lane was checked. The reconciliation
    # gate asks whether content arrived on a lane after exactly these tips. Empty on a
    # hand-built claim and on a mission with no checked lane.
    bound_lane_tips: tuple[tuple[str, str], ...] = ()

    # S8 (#7283): ``(lane id, branch)`` for every lane the approved-bound check read through a
    # branch other than its created lane branch: a ``single_branch`` Mission's ``lane-planning``
    # is read through its Mission branch (its created-branch alias resolves to the target). The
    # gate re-check reads each lane through this map. Empty on every other claim.
    bound_lane_branches: tuple[tuple[str, str], ...] = ()

    # #6715: approved WPs whose IMPLEMENTATION_MISSING refusal a no-implementation attestation
    # (``policy_metadata.attestation == "no_implementation"``) lifted, so ``consolidate`` can
    # name them in its output. Never an approval, a stamp or a review. Empty on a hand-built claim.
    no_implementation_attested_wp_ids: frozenset[str] = frozenset()

    # FR-009 (Mission consolidation-window-provenance-01M6Y84D, WP19): every approved work package
    # of a code lane the approved bound judged by its degraded window (no usable window-open SHA),
    # sorted by ``(lane_id, wp_id)``. Set on a passing claim and on a claim the bound refused; empty
    # on a hand-built claim and on a compound refusal. Appended last so positional constructions stay valid.
    window_gaps: tuple[GapEntry, ...] = ()

    @property
    def is_vacuous_against_manifest(self) -> bool:
        """True when the derived claim is empty while the manifest lists WPs."""
        return not self.approved and bool(self.manifest_wp_ids)


__all__ = [
    "ApprovedLaneContent",
    "ApprovedWpCommitSet",
    "CanceledDependencyContent",
    "LaneContribution",
    "MissingApprovedContent",
    "PresenceGap",
    "_GAP_ABSENT",
    "_GAP_UNCHANGED",
]
