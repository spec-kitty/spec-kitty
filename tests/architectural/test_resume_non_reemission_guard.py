"""Class-closing guard (#2711 / FR-008 / SC-005): resume never re-emits an
already-recorded ``done`` transition.

Un-marked ``@pytest.mark.regression`` (landing fold: make
``@pytest.mark.regression`` mean exactly one thing). This module is a
PERMANENT behavioral guard, not a red-first P0 reproduction — it is
expected to stay green as long as the resume non-re-emission invariant
holds; see the module-level "Non-vacuity" note below for how the guard
proves it is not a tautology without ever needing marker-visible red.

This is the WP06 *property* guard that closes the "rollback leaves the ledger
split-brain; ``--resume`` re-emits duplicate ``done`` transitions" defect class
**by construction**, not by re-running the WP02 reproduction. It complements
``tests/merge/test_issue_2711_merge_rollback_resume_coherence.py`` (WP02),
which drives the full merge executor with an injected target-advance failure:
that test proves the end-to-end *outcome* on ONE fixed scenario. This guard
instead pins the *invariant* the Option-A fix rests on — resume derives progress
from the durable committed event log, never from the roll-backable
``ConsolidationState.completed_wps`` bytes — and quantifies it over an ARBITRARY committed
coordination log crossed with an arbitrary (possibly rolled-back / stale)
``ConsolidationState``. No merge executor, no injected failure: just the real resume
progress-derivation seam over a git-backed committed coordination ref.

Binding property (identity-idempotence, spec FR-008 / SC-005 / US3):
    For any committed coordination log whose durably-``done`` WP set is ``D`` and
    any ``ConsolidationState`` whose ``completed_wps`` is arbitrary, the resume derivation
    re-emits ``done`` for **no** WP already recorded ``done`` on the durable ref:

        ``resume_reemit(log, state) ∩ D == ∅``.

    Equivalently, every durably-``done`` WP is recognized as already-recorded and
    is skipped rather than re-emitted, so its committed ``done`` identity is
    byte-stable across ``--resume``.

    **WP02 empirical note (folded here):** the invariant is framed as
    set-disjointness / no-re-emit of an already-recorded ``done`` — NOT as a tip
    ``count == 1`` on the coordination ref. The transactional safe-commit REPLACES
    the tip, so a ``count == 1`` assertion is green-on-base (vacuous). Byte-stable
    identity of the already-committed ``done`` is the discriminating contract.

The guard drives the REAL product surfaces
(:func:`_reconcile_completed_wps_for_resume`,
:func:`_durable_done_wps_on_coordination_ref` and the per-WP dedup guard
:func:`_has_transition_to`) so a product regression flips it. Non-vacuity is
witnessed in-test (the durable ref genuinely carries the ``done`` events) and was
verified by reintroducing the "resume trusts ``completed_wps``" derivation in
``done_bookkeeping`` — the guard goes RED, as required by SC-005.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest

# Import the status package before any coordination submodule (mirrors the
# production ``specify_cli/__init__`` import order) to avoid the known
# ``coordination -> transaction -> status`` mid-initialization import cycle when a
# test module reaches ``merge`` first.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.consolidation.done_bookkeeping import (
    _durable_done_wps_on_coordination_ref,
    _has_transition_to,
    _reconcile_completed_wps_for_resume,
)
from specify_cli.consolidation.state import ConsolidationState

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: subprocess git

# ---------------------------------------------------------------------------
# Coord-topology identity (slug ends with ``-<mid8>`` so the coordination branch
# IS the lanes-manifest mission branch — the production 083+ coord layout).
# ---------------------------------------------------------------------------

MID8 = "0GUARD26"
MISSION_ID = MID8 + "0" * (26 - len(MID8))  # 26-char ULID-shaped id; mid8 == prefix
MISSION_SLUG = f"resume-guard-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
ALL_WPS: tuple[str, ...] = ("WP01", "WP02", "WP03")
_EVENTS_REL = f"kitty-specs/{MISSION_SLUG}/status.events.jsonl"


def _representative_done_subsets() -> list[tuple[str, ...]]:
    """Representative durably-``done`` subsets spanning the property's boundaries.

    ``()`` (nothing recorded), a singleton, a prefix pair, a non-prefix pair, and
    the full set — enough to exercise every disjointness/fidelity boundary while
    keeping this git-backed guard's runtime bounded. (A full powerset is a strict
    superset of these and passes identically; these are the discriminating cases.)
    """
    return [(), ("WP01",), ("WP01", "WP02"), ("WP02", "WP03"), ALL_WPS]


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _event(*, wp_id: str, from_lane: str, to_lane: str, event_id: str) -> dict[str, object]:
    """One status event matching the append-only log schema the reducer reads."""
    return {
        "actor": "merge",
        "at": now_utc_iso(),
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": f"review-{wp_id}",
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _events_for(done_subset: tuple[str, ...]) -> list[dict[str, object]]:
    """Build the committed log: every WP reaches ``approved``; the ``done_subset``
    additionally reaches ``done`` (so ``D`` is genuinely the durably-done set)."""
    events: list[dict[str, object]] = []
    for wp_id in ALL_WPS:
        events.append(
            _event(
                wp_id=wp_id,
                from_lane="in_review",
                to_lane="approved",
                event_id=f"01APPROVED{wp_id}00000000000",
            )
        )
    for wp_id in done_subset:
        events.append(
            _event(
                wp_id=wp_id,
                from_lane="approved",
                to_lane="done",
                event_id=f"01DONE{wp_id}0000000000000000",
            )
        )
    return events


def _write_meta(feature_dir: Path) -> None:
    """meta.json declaring a coordination_branch => coord topology, so the resume
    reads route to the COMMITTED coordination ref (no worktree materialized)."""
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "resume non-reemission class guard (#2711)",
        "purpose_context": "resume must derive progress from the durable event log",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _bootstrap_coord_ref(repo: Path, done_subset: tuple[str, ...]) -> Path:
    """Commit meta + the arbitrary event log, then branch the coordination ref.

    Deliberately does NOT materialize a ``CoordinationWorkspace`` worktree: with
    the coord branch present and no worktree, the transactional reads resolve the
    COMMITTED coordination ref (``EventLogReadContract.coordination_branch_ref``) —
    the exact durable authority the Option-A resume derives progress from.
    Returns the primary feature dir.
    """
    _git(["init", "-qb", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test User"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir)
    lines = "".join(
        json.dumps(evt, sort_keys=True) + "\n" for evt in _events_for(done_subset)
    )
    (feature_dir / "status.events.jsonl").write_text(lines, encoding="utf-8")

    _git(["add", "."], repo)
    _git(["commit", "-qm", f"bootstrap coord mission (done={','.join(done_subset)})"], repo)
    # Coordination/mission branch at the current tip (carries the committed log).
    _git(["branch", COORD_BRANCH], repo)
    return feature_dir


def _committed_done_ground_truth(repo: Path) -> set[str]:
    """Independently reduce the COMMITTED coord ref to its ``done`` WP set.

    Deliberately NOT via the product reader under test (avoids a circular oracle):
    a raw ``git show <coord-ref>:<events>`` + latest-``to_lane`` reduction.
    """
    committed_text = subprocess.run(
        ["git", "show", f"{COORD_BRANCH}:{_EVENTS_REL}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    latest: dict[str, str] = {}
    for line in committed_text.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        latest[str(event["wp_id"])] = str(event["to_lane"])
    return {wp for wp, lane in latest.items() if lane == "done"}


def _resume_reemit_set(
    *, feature_dir: Path, repo: Path, merge_state: ConsolidationState
) -> set[str]:
    """The WPs the resume WOULD re-emit ``done`` for — the real skip decision.

    Mirrors ``_record_merged_wps_done_for_merge`` exactly: a WP is skipped (not
    re-emitted) iff the reconcile derivation confirms it OR the per-WP dedup guard
    already sees a durable ``done`` transition. Both are product surfaces that read
    the durable committed ref, so a regression in either flips this set.
    """
    reconcile_skip: set[str] = _reconcile_completed_wps_for_resume(
        feature_dir=feature_dir,
        mission_slug=MISSION_SLUG,
        merge_state=merge_state,
        repo_root=repo,
    )
    reemit: set[str] = set()
    for wp_id in merge_state.wp_order:
        if wp_id in reconcile_skip:
            continue
        if _has_transition_to(feature_dir, MISSION_SLUG, wp_id, "done", repo):
            continue
        reemit.add(wp_id)
    return reemit


def _completed_wps_variants(done_subset: tuple[str, ...]) -> list[list[str]]:
    """Arbitrary (possibly rolled-back / stale) ``ConsolidationState.completed_wps`` values.

    Covers the #2711 trigger (``[]`` — the "0/N already done" full rollback), the
    coherent hint (matches the durable set), and the whole wp_order (a maximal
    STALE superset: for a partial ``done_subset`` every non-durably-done WP is a
    stale completed_wps entry the resume must NOT trust — the split-brain a
    rollback strands).
    """
    variants = [[], list(done_subset), list(ALL_WPS)]
    # De-duplicate while preserving order (sets of lists aren't hashable).
    seen: list[list[str]] = []
    for variant in variants:
        if variant not in seen:
            seen.append(variant)
    return seen


@pytest.mark.architectural
@pytest.mark.parametrize(
    "done_subset", _representative_done_subsets(), ids=lambda s: "-".join(s) or "none"
)
def test_resume_never_reemits_a_durably_recorded_done(
    tmp_path: Path, done_subset: tuple[str, ...]
) -> None:
    """#2711 / FR-008 / SC-005: resume re-emits ``done`` for no already-recorded WP.

    Property over an arbitrary committed coordination log (``done`` set == the
    parametrized ``done_subset``) crossed with arbitrary rolled-back / stale
    ``ConsolidationState.completed_wps`` values. The Option-A resume derives progress from
    the durable committed ref, so:

    * (fidelity) reconcile confirms exactly the listed-AND-durably-done WPs — it
      NEVER trusts a stale ``completed_wps`` entry that lacks durable evidence; and
    * (idempotence) the resume re-emits ``done`` for no durably-done WP.

    Reintroducing "resume trusts ``completed_wps``" (``return
    set(merge_state.completed_wps)``) breaks the fidelity assertion on the stale
    variant; a dedup-guard that reads roll-backable working bytes breaks the
    idempotence assertion on the ``[]`` variant. Both were verified RED.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = _bootstrap_coord_ref(repo, done_subset)

    # --- Non-vacuity witness: the durable committed ref genuinely carries the
    # ``done`` events (guards against a vacuous "no ``done`` was ever recorded"
    # pass). Ground truth is read independently of the product surface. ---
    committed_done = _committed_done_ground_truth(repo)
    assert committed_done == set(done_subset), (
        "precondition: the committed coordination ref must carry exactly the "
        f"parametrized done set; expected {set(done_subset)}, got {committed_done}"
    )

    # The product durable-authority read must agree with the independent oracle
    # over the full candidate set (pins that resume's authority IS the durable ref).
    product_durable_done: set[str] = _durable_done_wps_on_coordination_ref(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        candidate_wps=list(ALL_WPS),
    )
    assert product_durable_done == committed_done, (
        "resume durable-progress authority disagreed with the committed ref: "
        f"product read {product_durable_done} != committed {committed_done}"
    )

    for completed_wps in _completed_wps_variants(done_subset):
        merge_state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            target_branch="main",
            wp_order=list(ALL_WPS),
            completed_wps=list(completed_wps),
        )

        # --- Fidelity (SC-005): reconcile confirms ONLY listed WPs that are
        # durably done — never a stale completed_wps entry. This is the assertion a
        # "resume trusts completed_wps" reintroduction turns RED. ---
        confirmed: set[str] = _reconcile_completed_wps_for_resume(
            feature_dir=feature_dir,
            mission_slug=MISSION_SLUG,
            merge_state=merge_state,
            repo_root=repo,
        )
        assert confirmed == committed_done & set(completed_wps), (
            "resume reconcile trusted completed_wps instead of the durable ref "
            f"(done={set(done_subset)}, completed_wps={completed_wps}): "
            f"confirmed {confirmed} != durable∩listed {committed_done & set(completed_wps)}"
        )

        # --- Identity-idempotence (FR-008): resume re-emits ``done`` for NO WP
        # already recorded ``done`` on the durable ref. ``resume ∩ D == ∅``. ---
        reemit = _resume_reemit_set(
            feature_dir=feature_dir, repo=repo, merge_state=merge_state
        )
        assert reemit & committed_done == set(), (
            "#2711 duplicate-emit: resume would re-emit ``done`` for already-"
            f"recorded WP(s) {sorted(reemit & committed_done)} "
            f"(done={set(done_subset)}, completed_wps={completed_wps}). Resume must "
            "derive progress from the durable event log, not the rolled-back state."
        )
