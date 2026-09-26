"""Terminus Reconciliation Gate — the tree-authoritative merge-outcome verifier.

Mission ``terminus-merge-integrity-01M380R6`` WP06 (S-D / FR-001, FR-002,
FR-012; NFR-005). This module is the executable form of the epic invariant
(:doc:`contracts/terminus-reconciliation`):

    After a terminus command returns, *if* its exit code is 0 *then*
    ``MergeOutcomeVerifier.verify(target, approved_wp_set) == PASS`` held
    **before any teardown ran** — every approved WP's approved commits are
    reachable from the target tree, and no excluded (canceled/removed) commit
    is, matched by **patch-id equivalence** so cherry-picked/re-lettered copies
    of canceled code are caught too.

Why a tree-authoritative gate (D3): the pre-fix asserts
(``_assert_merged_wps_done_on_target``, ``_phase_porcelain_invariant``) check
derived rows/meta the *same run* wrote — circular. Git reachability is the only
authority the wrong bookkeeping cannot fake.

Claim integrity (D3+, non-negotiable):

* approved commit SHAs come from **lane-branch git tips**, never status rows —
  forbids the vacuous ``_assert_merged_wps_done_on_target`` pattern;
* WP membership (approved vs canceled) is read through the **Lamport** reduction
  wrapper (:func:`specify_cli.status.reducer.materialize_snapshot`), never LWW
  ``reduce_parsed`` — so a wall-clock-later approval cannot green-wash a
  committed rejection *in the gate's own claim*. This routing choice lives
  entirely inside ``specify_cli``; it does NOT import or touch
  ``spec_kitty_events`` (C-002);
* the claim is **fail-closed**: an unresolved/unmaterialized coord surface, or a
  claim that is empty while the manifest lists WPs, refuses rather than passing
  vacuously (closes PP-F3). This claim-integrity refusal is **strategy-
  independent** — it fires for squash too, ABOVE the squash content-deferral
  early-return, so an empty-claim squash can never pass vacuously (#5001
  FOLD-1). A production claim whose excluded window base cannot be resolved, and
  a git probe that errors mid-window, also refuse rather than skipping to PASS
  (fail-closed, #5001 FOLD-3).

Scope note (FR-013): the PASS result is scoped to **approved-WP commit
reachability** only, NOT verdict integrity — the residual LWW-reducer
wall-clock ordering bug (#4941; #4990 closed the rejection-after-approval
case) is out of scope for this mission and stays named-open in the docs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import LanesManifest
from specify_cli.merge.git_probes import (
    GitProbeError,
    blob_id_at,
    changed_paths_in_range,
    changed_paths_of,
    commits_in_range,
    first_parent_commits_in_range,
    patch_id_of,
    patch_ids_in_range,
    sha_reachable_from,
)
from specify_cli.merge.workspace import get_merge_runtime_dir

# Lanes that count as "approved" (an acceptable, merge-ready ending) for claim
# membership. ``done`` is included so a resume that already baked ``done`` for a
# WP still recognizes it as claimed (never re-derived here — the strings mirror
# ``status.models.Lane`` values, the single lane vocabulary).
_APPROVED_MEMBERSHIP_LANES: frozenset[str] = frozenset({"approved", "done"})

# NFR-005 concrete floor: the six terminus entry points that MUST route through
# the reconciliation gate. Shrink-only — adding a terminus path that mutates
# refs/worktrees without adding it here means :func:`route_terminus` refuses it,
# and the self-mutation test proves a seventh, unrouted path fails the gate.
TERMINUS_ENTRY_POINTS: frozenset[str] = frozenset(
    {
        "merge",
        "merge --resume",
        "merge --abort",
        "upgrade",
        "agent issue-verdict",
        "doctor coordination --fix",
    }
)

# FR-012: the marker a post-fix merge writes at transaction start. Its ABSENCE
# on an in-flight (resumed) merge means the state was created by pre-fix code,
# whose shape the new guarantees cannot be retro-applied to (D6) — refuse.
_POST_FIX_MARKER_FILENAME = "reconciliation.post-fix"

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

# A repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan (#2251) — anchored to the
# repo root (``^``), never anywhere-in-tree, so a product-source path that merely
# CONTAINS a ``kitty-ops/`` segment deeper in the tree is not mistaken for the
# toolchain's own Op-record ledger. Mirrors the ULID shape
# ``coordination/coherence.py`` uses for its (deliberately broader, whole-tree)
# dirty-state-gate classifier.
_KITTY_OPS_ROOT_RECORD = re.compile(r"^kitty-ops/[0-9A-HJKMNP-TV-Z]{26}\.jsonl$")


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


class UnroutedTerminusPathError(RuntimeError):
    """Raised when a terminus path not on the NFR-005 allowlist tries to route."""


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
    """

    missing_approved: tuple[tuple[str, str], ...] = ()
    reachable_excluded: tuple[tuple[str, str], ...] = ()
    unattributable_content: tuple[tuple[str, str], ...] = ()
    unattributable_blobs: tuple[tuple[str, str], ...] = ()
    unattributable_deletions: tuple[str, ...] = ()

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
        return "; ".join(parts) if parts else "no divergence"


@dataclass(frozen=True)
class VerifyResult:
    """Result of a single :meth:`MergeOutcomeVerifier.verify` call."""

    status: VerifyStatus
    divergence: Divergence | None = None
    refusal_reason: str | None = None

    @property
    def is_pass(self) -> bool:
        return self.status is VerifyStatus.PASS

    def recovery_guidance(self) -> str:
        """What the operator should do — printed on a non-PASS gate result."""
        if self.status is VerifyStatus.REFUSE:
            return (
                f"Reconciliation refused (fail-closed): {self.refusal_reason}. "
                "Nothing was torn down and no refs/worktrees were mutated. Resolve "
                "the coordination-surface issue, then re-run the merge."
            )
        detail = self.divergence.describe() if self.divergence else "unknown divergence"
        return (
            f"Reconciliation FAILED: {detail}. Nothing was torn down and no "
            "refs/worktrees were mutated beyond what already landed. Inspect the "
            "target branch and the lane tips, then re-run the merge."
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


@dataclass(frozen=True)
class ApprovedWpCommitSet:
    """The claim the verifier trusts — derived once per terminus transaction.

    ``approved`` maps each claimed WP id to its approved commit SHAs, read from
    **lane-branch git tips** (never status rows). ``excluded_shas`` /
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

    @property
    def is_vacuous_against_manifest(self) -> bool:
        """True when the derived claim is empty while the manifest lists WPs."""
        return not self.approved and bool(self.manifest_wp_ids)


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
        reaches the reachability checks). Steps 1-3 are **strategy-independent
        claim integrity** — they run for squash too (#5001 FOLD-1: pre-fix the
        squash early-return short-circuited to PASS before the vacuous-manifest
        check, so an empty-claim squash passed vacuously, defeating PP-F3):

        1. an explicit ``refusal`` on the claim → REFUSE;
        2. an unresolved/unmaterialized coord surface → REFUSE;
        3. an empty claim while the manifest lists WPs → REFUSE (PP-F3);
        4. (squash / ``verify_reachability=False``) the squash-sound closed-world
           BLOB-attribution axis (#5013 WS1): a production claim with empty
           authorship or a ``None`` window base → REFUSE, a git probe error →
           REFUSE, a target A/M path whose blob is authored by no approved lane →
           FAIL(un-attributable); a hand-built (non-production) claim → PASS;
        5. (production merge/rebase claim) an unresolvable excluded window base →
           REFUSE (#5001 FOLD-3: the excluded/closed-world axes cannot be evaluated);
        6. any approved SHA unreachable from *target_ref* → FAIL(missing);
        7. any excluded SHA/patch-id reachable from *target_ref* → FAIL(excluded);
        8. (closed-world) any CONTENT commit in the merge window attributable to
           no approved WP → FAIL(un-attributable);
        9. a git probe error while scanning the window → REFUSE (#5001 FOLD-3);
        10. otherwise → PASS.
        """
        refusal = self._refusal_reason(approved_wp_set)
        if refusal is not None:
            return VerifyResult.refused(refusal)

        # Claim integrity is STRATEGY-INDEPENDENT (#5001 FOLD-1): an empty derived
        # claim while the manifest lists WPs is a vacuous-pass risk (PP-F3) and
        # must refuse for ALL strategies — hoisted ABOVE the squash early-return so
        # a squash merge whose claim came back empty can no longer pass vacuously.
        if approved_wp_set.is_vacuous_against_manifest:
            return VerifyResult.refused(f"derived claim is empty while the manifest lists {len(approved_wp_set.manifest_wp_ids)} WP(s)")

        # Squash (and any strategy that does not preserve content identity):
        # claim integrity held, but SHA/patch-id reachability is unsound (a squash
        # destroys lane-tip SHAs AND per-commit patch-ids). The squash-sound
        # closed-world BLOB-attribution axis runs instead (#5013 WS1). Every
        # fail-closed guard — empty authorship, an unresolvable window base, a git
        # probe error — fires INSIDE that branch, strictly above any PASS (F1
        # corollary), so a squash can no longer short-circuit to a vacuous pass the
        # way the pre-#5013 early-return did.
        if not approved_wp_set.verify_reachability:
            return self._verify_squash_content(target_ref, approved_wp_set)

        # Reachability-path fail-closed (#5001 FOLD-3): a production claim
        # (``enforce_closed_world``) whose excluded window base could not be
        # resolved cannot evaluate the excluded/closed-world axes at all. Skipping
        # them silently collapsed to PASS (fail-OPEN); refuse instead.
        if approved_wp_set.enforce_closed_world and approved_wp_set.excluded_window_base is None:
            return VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)

        try:
            missing = self._missing_approved(target_ref, approved_wp_set)
            excluded = self._reachable_excluded(target_ref, approved_wp_set)
            unattributable = self._unattributable_content(target_ref, approved_wp_set)
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
            window = patch_ids_in_range(self._repo, claim.excluded_window_base, target_ref)
            already = {pid for _sha, pid in reachable}
            for pid in claim.excluded_patch_ids:
                if pid in window and pid not in already:
                    reachable.append(("", pid))
        return reachable

    def _unattributable_content(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        """Closed-world axis: window CONTENT commits not attributable to any approved WP.

        Every content commit reachable in the merge window
        (``excluded_window_base..target``) must be attributable — by SHA or
        patch-id — to an approved WP's OWN authorship (:attr:`authored_shas` /
        :attr:`authored_patch_ids`, the first-parent spine of approved lanes). A
        content commit that is not is a removed/canceled WP's commit that rode a
        carrier lane onto the target (#4945/#4977/#4981) — it is returned as a
        ``(sha, patch_id)`` divergence.

        NON-content commits are never flagged: merge commits (empty patch-id) and
        spec-kitty housekeeping commits (status/meta/matrix/retrospective
        projections — every changed path is bookkeeping) are excluded from the
        content set so a legitimate merge never false-fails (NFR-004). Bounded to
        the window — O(#window commits), never O(repo history) (NFR-003).

        Off unless ``enforce_closed_world`` is set (only the production claim
        builder turns it on), so a hand-built claim keeps the pre-widening
        behavior; also a no-op when the window base is unknown.
        """
        if not claim.enforce_closed_world or claim.excluded_window_base is None:
            return []
        unattributable: list[tuple[str, str]] = []
        for sha in commits_in_range(self._repo, claim.excluded_window_base, target_ref):
            pid = patch_id_of(self._repo, sha)
            if not pid:
                continue  # merge commit / empty diff — never content
            if not self._commit_is_content(sha, claim):
                continue  # spec-kitty housekeeping — status/meta/matrix/retrospective
            if sha in claim.authored_shas or pid in claim.authored_patch_ids:
                continue  # attributable to an approved WP's own authorship
            unattributable.append((sha, pid))
        return unattributable

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

        Mirrors :meth:`_unattributable_content_squash`'s bookkeeping + deletion-
        authority filter, without reading blobs — this only asks WHETHER
        attributable content exists, never WHICH blob it is (there is no
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
            if status.startswith("D") and path in claim.authored_deletions:
                continue  # an approved lane's own final-state deletion — not content
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
        first-parent spine ends by deleting it); otherwise it is a canceled/removed
        WP's deletion that rode a carrier lane onto the target and is unattributable.
        Bounded by the squash diff size (NFR-003).
        """
        unattributable_blobs: list[tuple[str, str]] = []
        unattributable_deletions: list[str] = []
        for status, path in changed_paths_in_range(self._repo, window_base, target_ref):
            if self._is_bookkeeping_path(path, claim):
                continue  # status/meta/matrix/retrospective/planning churn — not content
            if status.startswith("D"):
                if path not in claim.authored_deletions:
                    unattributable_deletions.append(path)
                continue
            blob = blob_id_at(self._repo, target_ref, path)  # raises → REFUSE (F1)
            if (path, blob) not in claim.authored_blobs:
                unattributable_blobs.append((path, blob))
        return unattributable_blobs, unattributable_deletions

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

        Anchored to three mission/toolchain-owned roots — never a global
        basename match — closing a silent-data-loss defect (Epic #5001 landing
        remediation): this method used to delegate to
        :func:`~specify_cli.coordination.coherence.is_toolchain_generated_churn`,
        a DIRTY-STATE-gate classifier that is CORRECT for its own callers but
        matches by bare basename anywhere in the repository
        (``PurePosixPath(path).name == "meta.json"`` matches ``src/config/
        meta.json`` just as readily as the mission's own ``kitty-specs/<slug>/
        meta.json``). In the squash content axis a path this classifier calls
        bookkeeping is skipped BEFORE authored-blob attribution, so a removed/
        canceled WP's commit touching an ordinary product-source file merely
        NAMED like a toolchain artifact rode a carrier lane onto the target and
        shipped at exit 0. ``coherence.py`` itself is intentionally UNCHANGED —
        its whole-tree breadth is correct for the dirty-state gates that consume
        it; only this axis's classification is narrowed.

        A path counts as bookkeeping only when it is anchored to:

        * a ``kitty-specs/<slug>/`` segment sequence where ``<slug>`` is THIS
          claim's own :attr:`ApprovedWpCommitSet.mission_slug` — covers the
          mission's own ``meta.json``, ``status.events.jsonl``, issue-matrix,
          ``traces/``, ``decisions/``, retrospective, tasks, and plan artifacts,
          wherever that segment sequence occurs in the path (the repo-root
          ``kitty-specs/<slug>/…`` a merge commit lands directly, AND a
          coordination-topology worktree's nested copy alike);
        * :attr:`ApprovedWpCommitSet.planning_prefix` as an exact prefix
          (belt-and-suspenders for a hand-built claim that sets the prefix
          without a ``mission_slug``);
        * a repo-ROOT ``.kittify/`` prefix — encoding-provenance,
          mission-state-audit, and other toolchain-owned state;
        * a repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan
          (:data:`_KITTY_OPS_ROOT_RECORD`).

        Any other path — including one that merely shares a bookkeeping
        basename — is real content, subject to the closed-world attribution
        check.
        """
        normalized = path.rstrip("/")
        mission_slug = claim.mission_slug
        if mission_slug:
            parts = normalized.split("/")
            try:
                specs_index = parts.index(KITTY_SPECS_DIR)
            except ValueError:
                specs_index = -1
            # ``kitty-specs`` segment immediately followed by THIS mission's own
            # slug, wherever it occurs in the path (not just at a literal prefix
            # match). Mission-scoped, never a bare basename: a product path can
            # never satisfy this unless it is literally nested under the
            # mission's own planning directory. Anchoring on the SEGMENT SEQUENCE
            # (not ``claim.planning_prefix`` alone) closes a real mismatch: under
            # coordination topology ``planning_prefix`` is derived from the
            # STATUS_STATE placement's ``feature_dir`` (the coord WORKTREE's
            # nested copy, e.g. ``.worktrees/<slug>-<mid8>-coord/kitty-specs/
            # <slug>``), while the commits this axis scans land the mission's
            # bookkeeping directly at the repo-root ``kitty-specs/<slug>/`` — the
            # two paths never share a common prefix, so relying on
            # ``planning_prefix`` alone silently stopped recognizing the
            # mission's own ``status.json`` / ``status.events.jsonl`` / etc. as
            # bookkeeping once the whole-tree churn classifier was dropped.
            if specs_index != -1 and specs_index + 1 < len(parts) and parts[specs_index + 1] == mission_slug:
                return True
        prefix = claim.planning_prefix
        if prefix and (normalized == prefix or normalized.startswith(prefix + "/")):
            return True
        if normalized == KITTIFY_DIR or normalized.startswith(KITTIFY_DIR + "/"):
            return True
        return bool(_KITTY_OPS_ROOT_RECORD.match(normalized))


def route_terminus(entry_point: str) -> None:
    """Assert *entry_point* is on the NFR-005 allowlist before it runs the gate.

    Raises :class:`UnroutedTerminusPathError` for any terminus path not in
    :data:`TERMINUS_ENTRY_POINTS`. The self-mutation test drives a synthetic
    seventh path through here to prove an unrouted terminus command fails the
    gate rather than silently bypassing it (DIRECTIVE_043).
    """
    if entry_point not in TERMINUS_ENTRY_POINTS:
        raise UnroutedTerminusPathError(
            f"terminus entry point {entry_point!r} is not routed through the "
            "reconciliation gate; add it to TERMINUS_ENTRY_POINTS and wire the "
            "gate before it tears down any ref/worktree (NFR-005)"
        )


def _post_fix_marker_path(repo_root: Path, mission_id: str) -> Path:
    marker: Path = get_merge_runtime_dir(mission_id, repo_root) / _POST_FIX_MARKER_FILENAME
    return marker


def write_post_fix_marker(repo_root: Path, mission_id: str) -> None:
    """Stamp the FR-012 post-fix marker for this in-flight merge transaction."""
    path = _post_fix_marker_path(repo_root, mission_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("terminus-reconciliation-gate\n", encoding="utf-8")


def clear_post_fix_marker(repo_root: Path, mission_id: str) -> None:
    """Remove the post-fix marker at terminus finalize (best-effort)."""
    _post_fix_marker_path(repo_root, mission_id).unlink(missing_ok=True)


def detect_legacy_in_flight_state(repo_root: Path, mission_id: str, *, is_resume: bool) -> str | None:
    """FR-012: return a recovery message when a pre-fix in-flight state is found.

    A resumed merge whose transaction was started by pre-fix code carries no
    post-fix marker. The new tree-authoritative guarantees cannot be
    retro-applied to that unknown-shape state (D6, operator-confirmed), so the
    command must REFUSE with a recovery instruction rather than auto-heal.
    A fresh (non-resume) merge is never legacy — it writes the marker itself at
    transaction start. Returns ``None`` when the state is post-fix (safe to
    proceed).
    """
    if not is_resume:
        return None
    if _post_fix_marker_path(repo_root, mission_id).exists():
        return None
    return (
        "a pre-fix in-flight merge state was detected (no reconciliation marker). "
        "The terminus reconciliation guarantees cannot be retro-applied to it. "
        "Run `spec-kitty merge --abort` to clear the stale state, verify the target "
        "branch and lane tips by hand, then start a fresh `spec-kitty merge`."
    )


def build_approved_wp_set(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    coord_base_ref: str,
    excluded_canceled_wp_ids: Iterable[str] = (),
    excluded_window_base: str | None = None,
) -> ApprovedWpCommitSet:
    """Derive the fail-closed, Lamport-sourced claim once per transaction (T027).

    * WP membership is read through the **Lamport** reduction wrapper
      :func:`specify_cli.status.reducer.materialize_snapshot` (never LWW
      ``reduce_parsed``), so a wall-clock-later approval cannot override a
      committed rejection in the claim (C-002 preserved — no ``spec_kitty_events``
      edit);
    * approved commit SHAs come from **lane-branch git tips** relative to
      *coord_base_ref* (never status rows);
    * fail-closed: an unmaterializable coord surface, or a claim that is empty
      while the manifest lists WPs, yields a REFUSE-shaped claim.
    """
    # Imported lazily so this module stays import-light and the status facade is
    # resolved through ``specify_cli.status`` (C-002: the Lamport wrapper only).
    from specify_cli.status import materialize_snapshot

    manifest_wp_ids = frozenset(wp for lane in lanes_manifest.lanes for wp in lane.wp_ids)
    planning_prefix = _planning_prefix(repo_root, feature_dir)
    try:
        snapshot = materialize_snapshot(feature_dir)
    except Exception as exc:  # noqa: BLE001 — any unmaterializable surface fails closed
        return ApprovedWpCommitSet(
            manifest_wp_ids=manifest_wp_ids,
            excluded_window_base=excluded_window_base,
            surface_resolved=False,
            refusal=f"coordination surface could not be materialized: {exc}",
            mission_slug=lanes_manifest.mission_slug,
            planning_prefix=planning_prefix,
        )

    work_packages = snapshot.work_packages or {}
    approved = _collect_approved_shas(repo_root, lanes_manifest, work_packages, coord_base_ref)
    # Authored (WP1/WP2 shared prerequisite): computed BEFORE the excluded axis so
    # #5018's commit-level narrowing (below) can subtract it. Collectors stay pure
    # (WP2 note) — no shared mutable state, just a value threaded as a parameter.
    authored_shas, authored_patch_ids, authored_blobs, authored_deletions = _collect_authored(repo_root, lanes_manifest, work_packages, coord_base_ref)
    excluded_shas, excluded_patch_ids = _collect_excluded(
        repo_root,
        lanes_manifest,
        coord_base_ref,
        frozenset(excluded_canceled_wp_ids),
        authored_shas=authored_shas,
        authored_patch_ids=authored_patch_ids,
    )
    return ApprovedWpCommitSet(
        approved=approved,
        excluded_shas=excluded_shas,
        excluded_patch_ids=excluded_patch_ids,
        manifest_wp_ids=manifest_wp_ids,
        excluded_window_base=excluded_window_base,
        surface_resolved=True,
        enforce_closed_world=True,
        authored_shas=authored_shas,
        authored_patch_ids=authored_patch_ids,
        authored_blobs=authored_blobs,
        authored_deletions=authored_deletions,
        mission_slug=lanes_manifest.mission_slug,
        planning_prefix=planning_prefix,
    )


def _planning_prefix(repo_root: Path, feature_dir: Path) -> str | None:
    """Repo-relative posix path of the mission planning dir (``kitty-specs/<slug>``).

    Returns ``None`` when *feature_dir* is not under *repo_root* — the closed-world
    content check then falls back to the toolchain-churn denylist alone.
    """
    try:
        relative = feature_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    return relative.as_posix()


def _lane_branch_for(lanes_manifest: LanesManifest, lane_id: str) -> str:
    """Resolve a lane's branch name from the manifest identity."""
    branch: str = lane_branch_name(
        lanes_manifest.mission_slug,
        lane_id,
        planning_base_branch=lanes_manifest.target_branch,
        mission_id=lanes_manifest.mission_id,
    )
    return branch


def _lane_tip_commits(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """Commits on a lane tip, TOLERATING an unresolvable range at claim-build time.

    Claim building has always tolerated a lane branch (or coord base) that does not
    resolve — a fully-canceled lane has no branch, and some topologies cut the
    branch after this read — yielding no commits for that lane rather than aborting
    the whole merge. The #5001 FOLD-3 fail-closed window-error signal
    (:class:`GitProbeError`) is scoped to the VERIFIER's window scan
    (:meth:`MergeOutcomeVerifier._reachable_excluded` /
    ``_unattributable_content``), where an unevaluable window must refuse; the claim
    BUILDER keeps its pre-existing tolerant behavior here so a legitimate merge
    (e.g. a canceled-lane survivor merge) is never turned into a spurious refusal.
    """
    try:
        commits: list[str] = commits_in_range(repo_root, coord_base_ref, branch)
    except GitProbeError:
        return []
    return commits


def _collect_approved_shas(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
) -> dict[str, tuple[str, ...]]:
    """Approved WPs → their lane-tip commit SHAs (Lamport membership + git tips)."""
    approved: dict[str, tuple[str, ...]] = {}
    for lane in lanes_manifest.lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        for wp_id in lane.wp_ids:
            state = work_packages.get(wp_id)
            if state is None:
                continue
            lane_value = str(state.get("lane", ""))
            if lane_value in _APPROVED_MEMBERSHIP_LANES:
                approved[wp_id] = tuple(_lane_tip_commits(repo_root, coord_base_ref, branch))
    return approved


def _collect_excluded(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    coord_base_ref: str,
    excluded_canceled_wp_ids: frozenset[str],
    *,
    authored_shas: frozenset[str] = frozenset(),
    authored_patch_ids: frozenset[str] = frozenset(),
) -> tuple[frozenset[str], frozenset[str]]:
    """Canceled WP ids → their lane-tip commit SHAs + patch-ids (RN-F4), COMMIT-granular (#5018).

    Sourced from ``acceptably_canceled_wp_ids`` (mapped to lane tips by the
    caller) so a canceled lane's commits — including cherry-picked/re-lettered
    copies caught by patch-id — never land. Empty when no provenance-canceled WP
    exists; the verifier's excluded check stays non-vacuous regardless.

    A lane qualifies (the ``any(...)`` guard) the moment it lists ANY
    canceled-with-provenance WP — that stays LANE-granular, because a lane is one
    shared branch and there is no cheaper way to find "does this lane need
    narrowing at all". Within a qualifying (possibly MIXED) lane, though, the
    excluded set is narrowed to COMMIT granularity (C-001: granularity, not
    strictness) by subtracting *authored_shas* / *authored_patch_ids* — the
    approved lanes' OWN first-parent authorship (:func:`_collect_authored`,
    computed BEFORE this call in :func:`build_approved_wp_set`) — from the
    qualifying lane's tip commits: ``excluded_shas ← lane_tips − authored_shas``,
    ``excluded_patch_ids ← lane_patch_ids − authored_patch_ids``. A survivor WP
    sharing a mixed lane with a canceled sibling therefore keeps its own
    legitimately-approved commits OUT of the excluded set, closing #5018's
    false-FAIL, while a commit NOT on any approved lane's first-parent spine — a
    canceled WP's own work, OR a removed WP's commit smuggled into the lane via a
    merge's SECOND parent (#4977's mechanism; ``_lane_tip_commits`` walks ALL
    ancestry, first- and second-parent alike, so a smuggled second-parent commit
    is present here but absent from the first-parent-only ``authored_*`` sets) —
    is never subtracted and stays excluded. A fully-canceled lane (no approved
    WP at all) never contributes to *authored_shas*/*authored_patch_ids*
    (:func:`_collect_authored` skips it), so the subtraction is a no-op and every
    one of its tip commits stays excluded, unchanged from the pre-#5018 behavior.
    """
    shas: set[str] = set()
    patch_ids: set[str] = set()
    for lane in lanes_manifest.lanes:
        if not any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        lane_tip_shas = set(_lane_tip_commits(repo_root, coord_base_ref, branch))
        lane_patch_ids = {pid for sha in lane_tip_shas if (pid := patch_id_of(repo_root, sha))}
        shas |= lane_tip_shas - authored_shas
        patch_ids |= lane_patch_ids - authored_patch_ids
    return frozenset(shas), frozenset(patch_ids)


def _lane_is_approved(lane: object, work_packages: Mapping[str, Mapping[str, object]]) -> bool:
    """True when at least one of *lane*'s WPs is in an approved membership lane."""
    wp_ids = getattr(lane, "wp_ids", ())
    return any(str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES for wp in wp_ids)


def _lane_first_parent_spine(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """First-parent SHAs (newest-first) for a lane, TOLERATING an unresolvable range.

    Mirrors :func:`_lane_tip_commits`' claim-build tolerance: an unresolvable lane
    branch / coord base (a fully-canceled lane has no branch; some topologies cut it
    after this read) yields no authorship rather than turning a legitimate merge into
    a spurious refusal. The #5013 F7 fail-closed ``GitProbeError`` signal is scoped to
    the VERIFIER's window scan, not the claim BUILDER.
    """
    try:
        spine: list[str] = first_parent_commits_in_range(repo_root, coord_base_ref, branch)
        return spine
    except GitProbeError:
        return []


def _final_authored_walk(repo_root: Path, first_parent_shas: list[str]) -> tuple[set[tuple[str, str]], set[str]]:
    """FINAL ``(path, blob)``s AND final DELETED paths across a lane's first-parent spine (F5, #5022).

    Walks the spine newest→oldest (``git rev-list`` order) and, per path, keeps
    only the FIRST (hence newest, hence final) state seen — so a superseded
    intermediate ``v1`` is dropped in favor of the lane's final ``v2``, and a path
    deleted-then-re-added ends up present (in ``blobs``), never in ``deletions``. A
    merge commit on the spine contributes nothing (its combined diff is empty for
    a clean auto-merge), so a second-parent-smuggled blob/deletion is never
    recorded as authored. A path whose newest touching commit deletes it has no
    blob at that commit (:func:`blob_id_at` raises); it is marked seen and
    recorded in ``deletions`` instead of ``blobs`` — the lane's own final state for
    that path IS "deleted", so it is legitimate authored authority for the squash
    deletion-attribution axis (#5022), not merely "no shippable blob".

    Computed in ONE spine walk (not two) so :func:`_collect_authored` — the sole
    production caller — never re-reads the same commits' diffs twice.

    FIX D (#5001 landing remediation) — the invariant this axis rests on: the
    squash content axis's soundness depends on lanes being sliced by DISJOINT
    write-scope (project doctrine: lanes collapse by write-scope, not
    dependency — each lane owns a distinct set of paths). Under that invariant
    each content path is authored by exactly ONE approved lane, so "the FINAL
    first-parent blob per (lane, path), unioned across approved lanes" and "the
    final blob per path, full stop" coincide — there is no path two approved
    lanes both touch to disambiguate between. If a future topology ever allowed
    two approved lanes to modify the SAME path, this axis would false-FAIL
    whenever their independently-resolved final blobs differ from the squash's
    (correctly merged/rebased) resolution — see
    ``test_squash_three_way_merge_resolution_is_unattributable`` (pinned
    ``xfail(strict=True)``). That is the SAFE direction (refuse/rollback a
    legitimate merge, never ship unattributed content), but it means this
    assumption must be revisited before write-scope disjointness is relaxed.
    """
    seen_paths: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for sha in first_parent_shas:
        for path in changed_paths_of(repo_root, sha):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                blobs.add((path, blob_id_at(repo_root, sha, path)))
            except GitProbeError:
                deletions.add(path)  # deleted at this (newest touching) commit — final state deleted
    return blobs, deletions


def _final_authored_blobs(repo_root: Path, first_parent_shas: list[str]) -> set[tuple[str, str]]:
    """FINAL ``(path, blob)`` per path across a lane's first-parent spine (F5).

    Thin wrapper over :func:`_final_authored_walk` kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    blobs, _deletions = _final_authored_walk(repo_root, first_parent_shas)
    return blobs


def _final_authored_deletions(repo_root: Path, first_parent_shas: list[str]) -> set[str]:
    """FINAL deleted paths across a lane's first-parent spine (#5022 / WP1 T002).

    A path P is a member iff the FIRST (newest) commit on the spine that touches
    P deletes it — the lane's own final state for P is "deleted". A path
    added-then-deleted within the lane IS a member (final state deleted); a path
    deleted-then-re-added is NOT (its final state is present, and it is in
    :func:`_final_authored_blobs` instead — see :func:`_final_authored_walk` for
    the shared newest-first spine walk both draw from).

    Thin wrapper over :func:`_final_authored_walk`, kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    _blobs, deletions = _final_authored_walk(repo_root, first_parent_shas)
    return deletions


def _collect_authored(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
) -> tuple[frozenset[str], frozenset[str], frozenset[tuple[str, str]], frozenset[str]]:
    """Approved lanes → their OWN first-parent SHAs + patch-ids + FINAL blobs + FINAL deletions.

    The authorship claim the closed-world content checks attribute against. A lane
    contributes its authorship only when at least one of its WPs is approved/done (a
    fully-canceled lane's commits are NOT approved authorship). Authorship is the
    lane's **first-parent** spine (``git rev-list --first-parent``): a commit a lane
    merged IN from another branch (a removed WP's commit smuggled via a carrier
    merge's second parent) is excluded, so it is never mistaken for approved work.
    Merge commits on the spine yield an empty patch-id and contribute only their SHA.

    ``authored_blobs`` (#5013 WS1) is the squash-sound content axis's authority: the
    FINAL first-parent blob per (lane, path), unioned across approved lanes.
    ``authored_deletions`` (#5022 / WP1) is its deletion analogue: the FINAL
    first-parent-DELETED path per lane, unioned across approved lanes — the
    squash deletion-attribution axis's authority for a legitimate approved
    deletion.
    """
    shas: set[str] = set()
    patch_ids: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for lane in lanes_manifest.lanes:
        if not _lane_is_approved(lane, work_packages):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        first_parent = _lane_first_parent_spine(repo_root, coord_base_ref, branch)
        for sha in first_parent:
            shas.add(sha)
            pid = patch_id_of(repo_root, sha)
            if pid:
                patch_ids.add(pid)
        lane_blobs, lane_deletions = _final_authored_walk(repo_root, first_parent)
        blobs |= lane_blobs
        deletions |= lane_deletions
    return frozenset(shas), frozenset(patch_ids), frozenset(blobs), frozenset(deletions)


__all__ = [
    "ApprovedWpCommitSet",
    "Divergence",
    "MergeOutcomeVerifier",
    "TERMINUS_ENTRY_POINTS",
    "UnroutedTerminusPathError",
    "VerifyResult",
    "VerifyStatus",
    "build_approved_wp_set",
    "clear_post_fix_marker",
    "detect_legacy_in_flight_state",
    "route_terminus",
    "write_post_fix_marker",
]
