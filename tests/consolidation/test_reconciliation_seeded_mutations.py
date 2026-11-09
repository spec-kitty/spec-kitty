"""Seeded-mutation harness: every check the reconciliation split moves is guarded by a corpus cell (NFR-008, SC-005, C-008, DIRECTIVE_043).

A characterization corpus that cannot fail proves nothing. Each row of :data:`MUTATIONS` seeds ONE
deterministic mutation of one check, installed in THIS process (where
``characterization_support.compute_cells`` computes the verdicts) through the reconciliation-family
helpers, and recomputes only the corpus cells the row names. Every named cell must now differ from
its golden value; :func:`test_unmutated_cells_match_golden` recomputes the same cells without a
mutation and shows they equal the golden value, so the mutation, not the fixture, moved them.

The tables below are the reviewable form of :data:`MUTATIONS`; ``test_docstring_table_matches_mutations``
keeps them in agreement (check id, target and expected red cells).

================================== ======================================================== ================================================
check                              target                                                   mutation
================================== ======================================================== ================================================
kernel-bookkeeping                 ``_is_bookkeeping``                                      every path is bookkeeping (never content)
kernel-anchors                     ``_closed_world_anchors``                                the lane's own branch is an anchor (too wide)
kernel-anchors-frozen              ``_closed_world_anchors``                                a resume reads live dependency tips (extra row)
closed-world                       ``_collect_excluded``                                    nothing is excluded as canceled content
external-dependency-refs           ``resolve_external_dependency_refs``                     a ref naming Mission work is accepted
external-dependency-refs-exemption ``resolve_external_dependency_refs``                     declared refs exempt no commit (extra row)
approved-bound                     ``_approved_bound_verdict``                              the stamp bound never refuses
write-branch                       ``_write_branch_verdict``                                the Mission-branch bound never refuses
lane-window-tier-two               ``_lane_verdict``                                        the lane window check (tier 2) never refuses
lane-window-canceled-exempt        ``_canceled_window_exempt``                              canceled commits are not exempt from tier 2
lane-tip-recheck                   ``lane_tips_moved_refusal``                              the gate re-check never refuses
mixed-lane                         ``_resolve_mixed_lane``                                  a mixed lane resolves clean
canceled-dependency                ``_resolve_canceled_dependency_lanes``                   no canceled dependency content is carried
authorship                         ``_final_authored_walk``                                 no authored blob survives the walk
authorship-read-error              ``_final_authored_walk``                                 an unreadable history path is a deletion (extra row)
presence                           ``unmet_approved_content``                               no approved content is ever missing
verifier-squash-axis               ``MergeOutcomeVerifier._unattributable_content_squash``  no path is unattributable
verifier-presence-axis             ``MergeOutcomeVerifier._approved_content_divergence``    no presence divergence
verifier-canceled-axis             ``MergeOutcomeVerifier._canceled_content_divergence``    no canceled-content divergence
rendering                          ``_describe_approved_content_missing``                   the divergence clause renders empty
claim-orchestration                ``build_approved_wp_set``                                the claim's refusal is removed
================================== ======================================================== ================================================

Every row of :data:`PHASE3_CHECKS` WEAKENS its check (a verdict forced to pass, a lost refusal,
dropped evidence or an over-wide exemption) and turns each of its cells red in status, refusal
codes or ``Divergence`` fields. The extra rows (``-frozen``, ``-exemption``, ``-read-error`` and the two
``lane-window-`` rows) are not PHASE3 checks. ``lane-window-tier-two`` (WP19 review cycle 1, F1) witnesses the lane
window check on its own: no other row reaches tier 2 alone. ``lane-window-canceled-exempt`` (WP19 R1, operator ruling
2026-11-09) guards the opposite direction: a canceled work package's own commits are exempt from tier 2, and losing
that exemption over-refuses ``LANE_MOVED_AFTER_APPROVAL``. ``-exemption`` guards the opposite direction; ``-frozen`` (WP18) and ``-read-error`` (WP16) reinstate the
behaviour a Phase 4 fix removed, and ``kernel-anchors-frozen`` changes only the pinned text of its cells. WP18 replaced the
earlier strengthening row ``kernel-anchors-strict`` (no anchor exempts anything): once a resume reads its frozen anchor set
(FR-015), dropping every anchor yields the very verdict of its two cells, and no other corpus cell witnesses it.

Expected red cells (full corpus keys; each differs from its golden value under the row's mutation)::

    kernel-bookkeeping        ``fresh|single_lane|unattributable_squash_path``
    kernel-anchors            ``forecast|single_lane|post_approval_commit``
                              ``resume|mixed_lane_canceled_wp|stamp=present|window=recorded|dependency_lane_advanced``
    kernel-anchors-frozen     ``resume|mixed_lane_canceled_wp|stamp=present|window=recorded|dependency_lane_advanced``
                              ``resume|dependency_chain|stamp=present|window=recorded|dependency_lane_advanced_and_merged``
    closed-world              ``fresh|fully_canceled_dependency|canceled_content_reachable|strategy=merge``
    external-dependency-refs  ``fresh|single_lane|dependency_ref_names_mission_work``
    external-dependency-refs-exemption ``fresh|single_lane|dependency_ref``
    approved-bound            ``fresh|single_lane|stamp=missing|window=any``
                              ``forecast|single_lane|post_approval_commit``
    write-branch              ``fresh|single_branch|stamp=missing|window=any``
    lane-window-tier-two      ``fresh|two_wp_lane|stamp=present|window=recorded|commit_between_approvals``
                              ``fresh|two_wp_lane|stamp=present|window=recorded|rewound``
    lane-window-canceled-exempt ``fresh|mixed_lane_canceled_wp|stamp=present|window=recorded|canceled_commit_before_window``
                              ``fresh|mixed_lane_canceled_wp|stamp=present|window=recorded|canceled_commit_before_window_superseded``
    lane-tip-recheck          ``fresh|single_lane|lane_commit_during_run``
    mixed-lane                ``fresh|mixed_lane_canceled_wp|canceled_content_leaks``
    canceled-dependency       ``fresh|fully_canceled_dependency|canceled_content_reachable``
    authorship                ``fresh|single_lane|stamp=present|window=recorded``
                              ``fresh|two_wp_lane|stamp=present|window=recorded``
    authorship-read-error     ``fresh|single_lane|stamp=present|window=recorded|history_read_error``
    presence                  ``fresh|single_lane|approved_content_missing_released``
    verifier-squash-axis      ``fresh|single_lane|unattributable_squash_path``
    verifier-presence-axis    ``fresh|single_lane|approved_content_missing_released``
    verifier-canceled-axis    ``fresh|mixed_lane_canceled_wp|canceled_content_leaks``
    rendering                 ``fresh|single_lane|approved_content_missing_released``
    claim-orchestration       ``fresh|single_lane|stamp=missing|window=any``
                              ``forecast|single_lane|post_approval_commit``

Patching rules (WP04 guard): a function target is patched with
:func:`~tests.consolidation.reconciliation_family.setattr_reconciliation_family`, which patches every
family module that binds the name AND the by-name consumers (``phase_claim``, ``phase_gate``,
``forecast``); that is how ``build_approved_wp_set`` and ``lane_tips_moved_refusal`` reach their
callers. A method target patches the class attribute of ``MergeOutcomeVerifier``, whose class object
is identical before and after the split. No row patches a facade string target. Fakes that must keep
a result's type wrap the real function (looked up through the family helper, never through the
facade) and strip one field with :func:`dataclasses.replace`.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import specify_cli.consolidation.reconciliation_authorship as _authorship
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier
from tests.consolidation import characterization_support as cs
from tests.consolidation.reconciliation_family import family_modules_binding, setattr_reconciliation_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@dataclass(frozen=True)
class Mutation:
    """One seeded mutation: the check it guards, where it is installed, and the cells that must turn red."""

    check: str
    target: str
    mutation: str
    apply: Callable[[pytest.MonkeyPatch], None]
    expected_red_cells: tuple[str, ...]


# ---- helpers


def _real(name: str) -> Callable[..., Any]:
    """The un-mutated function bound to *name* in the reconciliation family (the facade is never asked)."""
    real: Callable[..., Any] = getattr(family_modules_binding(name)[0], name)
    return real


def _patch_function(monkeypatch: pytest.MonkeyPatch, name: str, fake: Callable[..., Any]) -> None:
    setattr_reconciliation_family(monkeypatch, name, fake)


def _patch_verifier_method(monkeypatch: pytest.MonkeyPatch, name: str, fake: Callable[..., Any]) -> None:
    monkeypatch.setattr(MergeOutcomeVerifier, name, fake)


def _wrapping(name: str, edit: Callable[[Any], Any]) -> Callable[..., Any]:
    """A fake that calls the real *name* and returns ``edit(result)``."""
    real = _real(name)

    def _fake(*args: Any, **kwargs: Any) -> Any:
        return edit(real(*args, **kwargs))

    return _fake


# ---- the mutations (one named function per row)


def _mutate_kernel_bookkeeping(monkeypatch: pytest.MonkeyPatch) -> None:
    def _everything_is_bookkeeping(path: str, mission_slug: str | None = None, planning_prefix: str | None = None) -> bool:
        return True

    _patch_function(monkeypatch, "_is_bookkeeping", _everything_is_bookkeeping)


def _mutate_kernel_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widen the anchors by the lane's OWN branch: its tip reaches every commit on the lane, so none is ever post-approval."""
    real = _real("_closed_world_anchors")
    lane_branch_for = _real("_lane_branch_for")

    def _own_branch_is_an_anchor(lanes_manifest: Any, lane: Any, target_base: str | None, **kwargs: Any) -> list[str]:
        return [*real(lanes_manifest, lane, target_base, **kwargs), lane_branch_for(lanes_manifest, lane.lane_id)]

    _patch_function(monkeypatch, "_closed_world_anchors", _own_branch_is_an_anchor)


def _mutate_kernel_anchors_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop a resume's frozen anchor set: every dependency lane is anchored on its LIVE branch again (pre-WP18, FR-015)."""
    real = _real("_closed_world_anchors")

    def _live_dependency_tips(lanes_manifest: Any, lane: Any, target_base: str | None, **kwargs: Any) -> list[str]:
        kwargs.pop("frozen_tips", None)
        return list(real(lanes_manifest, lane, target_base, **kwargs))

    _patch_function(monkeypatch, "_closed_world_anchors", _live_dependency_tips)


def _mutate_closed_world(monkeypatch: pytest.MonkeyPatch) -> None:
    def _nothing_excluded(*_args: object, **_kwargs: object) -> tuple[frozenset[str], frozenset[str]]:
        return frozenset(), frozenset()

    _patch_function(monkeypatch, "_collect_excluded", _nothing_excluded)


def _mutate_external_dependency_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "resolve_external_dependency_refs", _wrapping("resolve_external_dependency_refs", _without_refusal))


def _mutate_external_dependency_refs_exemption(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "resolve_external_dependency_refs", _wrapping("resolve_external_dependency_refs", _exempt_nothing))


def _exempt_nothing(attribution: Any) -> Any:
    return dataclasses.replace(attribution, shas=frozenset(), blobs=frozenset(), deletions=frozenset())


def _mutate_approved_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "_approved_bound_verdict", _wrapping("_approved_bound_verdict", _without_refusal))


def _without_refusal(result: Any) -> Any:
    return dataclasses.replace(result, refusal=None)


def _mutate_write_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "_write_branch_verdict", _wrapping("_write_branch_verdict", _without_refusal))


def _mutate_lane_window_tier_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lane window check (tier 2) never refuses: every lane keeps only its tier-1 verdict (WP19 review cycle 1, F1)."""

    def _without_tier_two(verdict: Any) -> Any:
        return dataclasses.replace(verdict, tier_two=())

    _patch_function(monkeypatch, "_lane_verdict", _wrapping("_lane_verdict", _without_tier_two))


def _mutate_lane_window_canceled_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A canceled work package's attributed commits are not exempt from tier 2 (the pre-ruling behaviour, WP19 R1)."""

    def _nothing_exempt(*_args: object, **_kwargs: object) -> frozenset[str]:
        return frozenset()

    _patch_function(monkeypatch, "_canceled_window_exempt", _nothing_exempt)


def _mutate_lane_tip_recheck(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never_moved(*_args: object, **_kwargs: object) -> None:
        return None

    _patch_function(monkeypatch, "lane_tips_moved_refusal", _never_moved)


def _mutate_mixed_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    def _resolves_clean(*_args: object, **_kwargs: object) -> tuple[set[Any], list[str], frozenset[str]]:
        return set(), [], frozenset()

    _patch_function(monkeypatch, "_resolve_mixed_lane", _resolves_clean)


def _mutate_canceled_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def _carries_nothing(resolution: Any) -> Any:
        return dataclasses.replace(resolution, unapproved_commits=frozenset(), content=frozenset(), refusal=None)

    _patch_function(monkeypatch, "_resolve_canceled_dependency_lanes", _wrapping("_resolve_canceled_dependency_lanes", _carries_nothing))


def _mutate_authorship(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_authored_blobs(walk: tuple[set[tuple[str, str]], set[str]]) -> tuple[set[tuple[str, str]], set[str]]:
        _blobs, deletions = walk
        return set(), deletions

    _patch_function(monkeypatch, "_final_authored_walk", _wrapping("_final_authored_walk", _no_authored_blobs))


def _mutate_authorship_read_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable history path is a deletion again: the pre-WP16 behaviour (#5048(b)).

    The corpus fault installs its own ``path_state_at`` fake AFTER this row's ``apply()``, which would overwrite a plain patch
    of that name. So the mutation acts at CALL TIME: it wraps the walk and, for the duration of one call, swallows whatever
    ``path_state_at`` is bound to by then.
    """
    real_walk = _real("_final_authored_walk")

    def _walk_that_reads_errors_as_deletions(*args: Any, **kwargs: Any) -> Any:
        installed: Callable[[Path, str, str], str | None] = _authorship.path_state_at

        def _swallow(repo_root: Path, ref: str, path: str) -> str | None:
            try:
                return installed(repo_root, ref, path)
            except GitProbeError:
                return None

        with pytest.MonkeyPatch.context() as inner:
            setattr_reconciliation_family(inner, "path_state_at", _swallow)
            return real_walk(*args, **kwargs)

    _patch_function(monkeypatch, "_final_authored_walk", _walk_that_reads_errors_as_deletions)


def _mutate_presence(monkeypatch: pytest.MonkeyPatch) -> None:
    def _nothing_missing(*_args: object, **_kwargs: object) -> list[Any]:
        return []

    _patch_function(monkeypatch, "unmet_approved_content", _nothing_missing)


def _mutate_verifier_squash_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _nothing_unattributable(self: object, *_args: object, **_kwargs: object) -> tuple[list[tuple[str, str]], list[str]]:
        return [], []

    _patch_verifier_method(monkeypatch, "_unattributable_content_squash", _nothing_unattributable)


def _mutate_verifier_presence_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_divergence(self: object, *_args: object, **_kwargs: object) -> tuple[list[Any], None]:
        return [], None

    _patch_verifier_method(monkeypatch, "_approved_content_divergence", _no_divergence)


def _mutate_verifier_canceled_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_divergence(self: object, *_args: object, **_kwargs: object) -> tuple[list[Any], None]:
        return [], None

    _patch_verifier_method(monkeypatch, "_canceled_content_divergence", _no_divergence)


def _mutate_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    def _renders_nothing(*_args: object, **_kwargs: object) -> str:
        return ""

    _patch_function(monkeypatch, "_describe_approved_content_missing", _renders_nothing)


def _mutate_claim_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_function(monkeypatch, "build_approved_wp_set", _wrapping("build_approved_wp_set", _without_refusal))


# ---- the table


def _key(mode: str, shape: str, *rest: str) -> str:
    return "|".join((mode, shape, *rest))


_STAMP_MISSING = _key("fresh", "single_lane", "stamp=missing", "window=any")
_SINGLE_LANE_RECORDED = _key("fresh", "single_lane", "stamp=present", "window=recorded")
_HISTORY_READ_ERROR = cs.NAMED_KEYS["d_history_read_error"]
_TWO_WP_RECORDED = _key("fresh", "two_wp_lane", "stamp=present", "window=recorded")
_CANCELED_CONTENT_LEAKS = cs.NAMED_KEYS["mut_canceled_content_leaks"]
_CANCELED_DEPENDENCY_REACHABLE = cs.NAMED_KEYS["mut_canceled_dependency_reachable"]
_CANCELED_DEPENDENCY_REACHABLE_MERGE = cs.NAMED_KEYS["mut_canceled_dependency_reachable_merge"]
_DEPENDENCY_REF_MISSION_WORK = cs.NAMED_KEYS["mut_dependency_ref_mission_work"]
_SQUASH_PATH = cs.NAMED_KEYS["mut_unattributable_squash_path"]
_PRESENCE_RELEASED = cs.NAMED_KEYS["mut_approved_content_missing_released"]
_LANE_COMMIT_DURING_RUN = cs.NAMED_KEYS["mut_lane_commit_during_run"]
_DEPENDENCY_REF = cs.NAMED_KEYS["mut_dependency_ref"]
_R09_FORECAST = cs.NAMED_KEYS["r09_post_approval_forecast"]
_RESUME_CLOSED_WORLD = cs.NAMED_KEYS["e_resume_closed_world"]
_RESUME_APPROVED_BOUND = cs.NAMED_KEYS["f_resume_approved_bound"]
_SINGLE_BRANCH_STAMP_MISSING = _key("fresh", "single_branch", "stamp=missing", "window=any")
_WINDOW_STRAY = cs.NAMED_KEYS["a_commit_between_approvals"]
_WINDOW_REWOUND = cs.NAMED_KEYS["c_rewound_lanes"]
_CANCELED_BEFORE_WINDOW = cs.NAMED_KEYS["x_canceled_commit_before_window"]
_CANCELED_BEFORE_WINDOW_SUPERSEDED = cs.NAMED_KEYS["x_canceled_commit_before_window_superseded"]

MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "kernel-bookkeeping",
        "_is_bookkeeping",
        "every path is bookkeeping, so no path is ever content",
        _mutate_kernel_bookkeeping,
        (_SQUASH_PATH,),
    ),
    Mutation(
        "kernel-anchors",
        "_closed_world_anchors",
        "the lane's own branch is an anchor, so no commit on the lane is ever after its approval",
        _mutate_kernel_anchors,
        (_R09_FORECAST, _RESUME_CLOSED_WORLD),
    ),
    Mutation(
        "kernel-anchors-frozen",
        "_closed_world_anchors",
        "a resume anchors on the live dependency-lane branches again, not its frozen tips (the pre-WP18 behaviour; extra row)",
        _mutate_kernel_anchors_frozen,
        (_RESUME_CLOSED_WORLD, _RESUME_APPROVED_BOUND),
    ),
    Mutation(
        "closed-world",
        "_collect_excluded",
        "nothing is excluded, so a canceled commit reachable from the target under --strategy merge goes unreported",
        _mutate_closed_world,
        (_CANCELED_DEPENDENCY_REACHABLE_MERGE,),
    ),
    Mutation(
        "external-dependency-refs",
        "resolve_external_dependency_refs",
        "a declared ref naming Mission work is accepted (its refusal is dropped)",
        _mutate_external_dependency_refs,
        (_DEPENDENCY_REF_MISSION_WORK,),
    ),
    Mutation(
        "external-dependency-refs-exemption",
        "resolve_external_dependency_refs",
        "a declared ref is honoured but exempts no commit, blob or deletion (strengthening)",
        _mutate_external_dependency_refs_exemption,
        (_DEPENDENCY_REF,),
    ),
    Mutation(
        "approved-bound",
        "_approved_bound_verdict",
        "the approval-stamp bound never refuses",
        _mutate_approved_bound,
        (_STAMP_MISSING, _R09_FORECAST),
    ),
    Mutation(
        "write-branch",
        "_write_branch_verdict",
        "the single_branch Mission-branch bound never refuses",
        _mutate_write_branch,
        (_SINGLE_BRANCH_STAMP_MISSING,),
    ),
    Mutation(
        "lane-window-tier-two",
        "_lane_verdict",
        "the lane window check (tier 2) never refuses; only tier 1 judges a lane (extra row)",
        _mutate_lane_window_tier_two,
        (_WINDOW_STRAY, _WINDOW_REWOUND),
    ),
    Mutation(
        "lane-window-canceled-exempt",
        "_canceled_window_exempt",
        "a canceled work package's own commits are judged by the window check again (extra row)",
        _mutate_lane_window_canceled_exempt,
        (_CANCELED_BEFORE_WINDOW, _CANCELED_BEFORE_WINDOW_SUPERSEDED),
    ),
    Mutation(
        "lane-tip-recheck",
        "lane_tips_moved_refusal",
        "the gate re-check never finds a lane that moved",
        _mutate_lane_tip_recheck,
        (_LANE_COMMIT_DURING_RUN,),
    ),
    Mutation(
        "mixed-lane",
        "_resolve_mixed_lane",
        "a mixed lane resolves clean and carries no canceled content",
        _mutate_mixed_lane,
        (_CANCELED_CONTENT_LEAKS,),
    ),
    Mutation(
        "canceled-dependency",
        "_resolve_canceled_dependency_lanes",
        "a fully-canceled dependency carries no commit, no content and no refusal",
        _mutate_canceled_dependency,
        (_CANCELED_DEPENDENCY_REACHABLE,),
    ),
    Mutation(
        "authorship",
        "_final_authored_walk",
        "no authored blob survives the spine walk",
        _mutate_authorship,
        (_SINGLE_LANE_RECORDED, _TWO_WP_RECORDED),
    ),
    Mutation(
        "authorship-read-error",
        "_final_authored_walk",
        "an unreadable history path is recorded as a deletion again (the pre-WP16 behaviour; extra row)",
        _mutate_authorship_read_error,
        (_HISTORY_READ_ERROR,),
    ),
    Mutation(
        "presence",
        "unmet_approved_content",
        "no approved content is ever missing from the target",
        _mutate_presence,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "verifier-squash-axis",
        "MergeOutcomeVerifier._unattributable_content_squash",
        "no path of the squashed diff is unattributable",
        _mutate_verifier_squash_axis,
        (_SQUASH_PATH,),
    ),
    Mutation(
        "verifier-presence-axis",
        "MergeOutcomeVerifier._approved_content_divergence",
        "the presence axis reports no divergence",
        _mutate_verifier_presence_axis,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "verifier-canceled-axis",
        "MergeOutcomeVerifier._canceled_content_divergence",
        "the canceled-content axis reports no divergence",
        _mutate_verifier_canceled_axis,
        (_CANCELED_CONTENT_LEAKS,),
    ),
    Mutation(
        "rendering",
        "_describe_approved_content_missing",
        "the presence divergence clause renders empty, so its refusal code leaves the output",
        _mutate_rendering,
        (_PRESENCE_RELEASED,),
    ),
    Mutation(
        "claim-orchestration",
        "build_approved_wp_set",
        "the claim's refusal is removed after the checks ran",
        _mutate_claim_orchestration,
        (_STAMP_MISSING, _R09_FORECAST),
    ),
)

#: Every check the split moves (plan IC-10 / IC-11): one id each, 16 in all.
PHASE3_CHECKS = frozenset(
    {
        "kernel-bookkeeping",
        "kernel-anchors",
        "closed-world",
        "external-dependency-refs",
        "approved-bound",
        "write-branch",
        "lane-tip-recheck",
        "mixed-lane",
        "canceled-dependency",
        "authorship",
        "presence",
        "verifier-squash-axis",
        "verifier-presence-axis",
        "verifier-canceled-axis",
        "rendering",
        "claim-orchestration",
    }
)

#: Forked workers inherit a patch applied in this process, so a row may compute its cells in parallel.
_ROW_WORKERS = 4


def _recompute(cells: Iterable[str], workdir: Path, *, workers: int = 1) -> dict[str, Any]:
    names = sorted(set(cells))
    return cs.compute_cells(names, workdir, workers=min(workers, len(names)))


def _row_id(mutation: Mutation) -> str:
    return mutation.check


@pytest.mark.timeout(300)
@pytest.mark.parametrize("mutation", MUTATIONS, ids=_row_id)
def test_seeded_mutation_turns_cells_red(mutation: Mutation, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Install the row's mutation, recompute only its cells, and require every one to differ from the golden value."""
    golden = cs.load_golden()
    missing = [cell for cell in mutation.expected_red_cells if cell not in golden]
    assert not missing, f"{mutation.check}: cells absent from the golden file: {missing}"
    mutation.apply(monkeypatch)

    recomputed = _recompute(mutation.expected_red_cells, tmp_path, workers=_ROW_WORKERS)

    still_green = [cell for cell in mutation.expected_red_cells if recomputed[cell] == golden[cell]]
    header = f"{mutation.check} ({mutation.target}: {mutation.mutation})"
    assert not still_green, "\n".join(
        f"{header} left cell {cell} at its golden value:\n  golden:     {golden[cell]}\n  recomputed: {recomputed[cell]}" for cell in still_green
    )


@pytest.mark.timeout(600)
def test_unmutated_cells_match_golden(tmp_path: Path) -> None:
    """Control: the union of every row's cells, recomputed with NO mutation, equals the golden file (the mutation caused the red)."""
    cells = sorted({cell for mutation in MUTATIONS for cell in mutation.expected_red_cells})
    cs.assert_cells_match(_recompute(cells, tmp_path, workers=_ROW_WORKERS))


def test_every_moved_check_has_a_mutation() -> None:
    checks = [mutation.check for mutation in MUTATIONS]
    assert len(checks) == len(set(checks)), "one row per check"
    assert set(checks) >= PHASE3_CHECKS, f"checks without a mutation row: {sorted(PHASE3_CHECKS - set(checks))}"
    assert len(PHASE3_CHECKS) == 16


def test_every_row_has_a_real_target_and_cells() -> None:
    """A typo in a target or a cell key must fail here, not silently pin nothing."""
    golden = cs.load_golden()
    for mutation in MUTATIONS:
        assert mutation.expected_red_cells, f"{mutation.check}: no expected red cell"
        assert all(cell in golden for cell in mutation.expected_red_cells), mutation.check
        owner, _, method = mutation.target.rpartition(".")
        if owner:
            assert owner == "MergeOutcomeVerifier" and hasattr(MergeOutcomeVerifier, method), f"{mutation.check}: {mutation.target} is not a verifier method"
        else:
            assert family_modules_binding(mutation.target), mutation.check


_TABLE_ROW = re.compile(r"^([a-z]+(?:-[a-z]+)*)\s+``([^`]+)``")
_CELLS_ROW = re.compile(r"^([a-z]+(?:-[a-z]+)*)\s+``")
_CELL_KEY = re.compile(r"``([^`]+)``")


def _docstring_targets_and_cells() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    doc = __doc__ or ""
    table, _, cells = doc.partition("Expected red cells")
    targets = {m.group(1): m.group(2) for line in table.splitlines() if (m := _TABLE_ROW.match(line))}
    expected: dict[str, list[str]] = {}
    current = ""
    for line in cells.splitlines():
        if not line.strip():
            current = ""  # a blank line ends a row block
            continue
        row = _CELLS_ROW.match(line.strip())
        if row:
            current = row.group(1)
            expected[current] = []
        if current:
            expected[current].extend(_CELL_KEY.findall(line))
    return targets, {check: tuple(keys) for check, keys in expected.items()}


def test_docstring_table_matches_mutations() -> None:
    targets, cells = _docstring_targets_and_cells()
    assert targets == {mutation.check: mutation.target for mutation in MUTATIONS}
    assert cells == {mutation.check: mutation.expected_red_cells for mutation in MUTATIONS}


def test_no_row_patches_a_facade_string_target() -> None:
    """The WP04 guard covers string patches across the corpus; this file also never spells one (it patches through the family helper)."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    string_targets = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"setattr", "patch"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert not string_targets, f"string patch targets at lines {string_targets}"
