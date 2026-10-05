"""Residual pins for the canceled-content divergence axis (WP06 T030, FR-009, C-007).

Each test below is a git-backed, strict ``xfail`` that asserts the **ideal**
verdict for a known, documented limitation of the mixed-lane canceled-content
axis (``wp_attribution.resolve_canceled_wp`` + ``MergeOutcomeVerifier.
_canceled_content_divergence``, mission ``mixed-lane-authorship-soundness-
01M3M7Y0`` WP04/WP05). Hunk-level supersession, the other-lane-identical
direction, the never-claimed-WP shape, the post-cancel-reintroduction shape,
and the never-entered-implementation-sibling misattribution shape are
explicitly out of scope for a fix in this mission (spec.md C-007); pinning
them here means any future
change to the axis that silently alters this behaviour turns the test RED
(``strict=True``) rather than drifting unnoticed (charter tactic
``delete-the-assertion-not-the-test``).

Every scenario is driven through the SAME production seam WP06's other
subtasks use: real git commits on a real lane branch, real
``status.events.jsonl`` events, ``build_approved_wp_set`` +
``MergeOutcomeVerifier.verify`` called directly (never a hand-built
``ApprovedWpCommitSet`` — the resolver's own supersession/window logic is
exactly what each residual exercises). The target ref for every case is a
real ``git merge --squash`` of the lane onto the mission's target branch —
the default-strategy shape the squash-sound blob-attribution axis (#5013)
and the canceled-content axis both run against — so ``verify_reachability``
is set ``False`` (:func:`dataclasses.replace`) to match production squash
claims (``consolidation/executor.py``'s own ``replace(captured,
verify_reachability=False)``).

**FR-013 update (closed world on mixed lanes, ADR 2026-09-29-1).** Two former
residuals no longer leak: the post-cancel reintroduction (residual 3) and the
never-claimed-WP commit (residual 4) both land a content commit outside every
resolved WP window, which the closed-world check now REFUSEs. Their leak is
closed (the verdict is a safe non-PASS), so they are regular tests pinning the
REFUSE instead of strict ``xfail`` pins. Residuals 1, 2 and 5 stay strict
``xfail`` (their commits all sit inside a resolved window). Residual 6
(landing review, #5330) is a gap of the closed-world ANCHORS: a pre-claim
out-of-workflow commit (first-claim anchor), still a strict ``xfail``.

**#5569 update.** Residual 7 (a fully-canceled dependency lane's content exempt
via the dependency-tip anchor) is FIXED: a fully-canceled lane's own commits are
subtracted from the authored claim and never exempt from the closed world, so
it is a regular test pinning the REFUSE
(``test_fully_canceled_dependency_lane_content_does_not_ship``), not a ``xfail``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, CANCELED_SUPERSEDED
from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier, VerifyResult, VerifyStatus, build_approved_wp_set
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_TARGET = "main"
# FR-013 closed-world REFUSE wording (wp_attribution._DETAIL_TEMPLATES).
_OUTSIDE_WINDOWS_WORDING = "outside every WP's recorded work window"
_APPROVE_CHAIN: tuple[tuple[str, str], ...] = (
    ("planned", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
)


# --------------------------------------------------------------------------- #
# real-git helpers (no mocking) -- self-contained; this file owns no shared
# fixture with the other WPs' test modules (owned_files: this file only).
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _rev(repo: Path, ref: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _init_repo(tmp_path: Path, *, slug: str, wp_ids: tuple[str, ...]) -> tuple[Path, Path, LanesManifest, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    mission_id = ("01RESID" + slug.upper().replace("-", ""))[:26].ljust(26, "0")
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": slug, "mission_id": mission_id, "mission_type": "software-dev", "target_branch": _TARGET}),
        encoding="utf-8",
    )
    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=wp_ids,
        write_scope=("src/pkg",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{slug}",
        target_branch=_TARGET,
        lanes=[lane],
        computed_at="2026-09-28T00:00:00+00:00",
        computed_from="wp06-canceled-content-residuals",
    )
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap")
    return repo, feature_dir, manifest, _rev(repo)


def _event(seq: int, wp: str, frm: str, to: str, *, slug: str, at: str, stamp: str | None) -> dict[str, object]:
    ev: dict[str, object] = {
        "actor": "implementer-ivan",
        "at": at,
        "event_id": f"01RESID{seq:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": slug,
        "force": False,
        "from_lane": frm,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": wp,
    }
    if stamp is not None:
        ev["policy_metadata"] = {"lane_head": stamp}
    return ev


def _wp01_approved_again(events: list[dict[str, object]], first_seq: int, *, slug: str, lane_tip: str) -> None:
    """Record that review approved WP01 AGAIN at *lane_tip*, the lane as it now stands.

    The approval-stamp bound refuses any content commit on a lane after the approval it
    names, so a fixture whose lane commits land after WP01's first approval re-approves
    WP01 at the final tip; the rework adds no commit of its own.
    """
    rework = (("approved", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved"))
    for step, (frm, to) in enumerate(rework):
        stamp = None if to == "in_review" else lane_tip
        events.append(_event(first_seq + step, "WP01", frm, to, slug=slug, at=f"2026-01-09T00:0{step}:00+00:00", stamp=stamp))


def _write_events(repo: Path, feature_dir: Path, events: list[dict[str, object]]) -> None:
    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8")
    _git(repo, "add", str(events_path.relative_to(repo)))
    _git(repo, "commit", "-qm", "record events")


def _squash_target(repo: Path, base: str, lane_branch: str) -> str:
    """A real ``git merge --squash`` of *lane_branch* onto *base* -- the
    default-strategy target shape (a single new commit with no ancestry link
    to the lane's own commits, matching production squash consolidation)."""
    _git(repo, "checkout", "-q", "-b", "target-squash", base)
    result = subprocess.run(["git", "merge", "--squash", "-q", lane_branch], cwd=repo, capture_output=True, text=True, check=True)
    del result
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        _git(repo, "commit", "-qm", f"squash {lane_branch}")
    return "target-squash"


def _verify_today_result(
    repo: Path,
    feature_dir: Path,
    manifest: LanesManifest,
    coord_base: str,
    target_ref: str,
    excluded_wp_ids: frozenset[str],
) -> VerifyResult:
    """Like :func:`_verify_today` but returns the FULL ``VerifyResult``
    (status + divergence), for residuals whose ideal assertion needs to
    inspect WHICH WP a ``canceled_content`` finding names, not merely the
    top-level status."""
    claim = build_approved_wp_set(
        repo,
        feature_dir,
        manifest,
        coord_base_ref=coord_base,
        excluded_canceled_wp_ids=excluded_wp_ids,
        excluded_window_base=coord_base,
    )
    squash_claim = replace(claim, verify_reachability=False)
    return MergeOutcomeVerifier(repo).verify(target_ref, squash_claim)


def _verify_today(
    repo: Path,
    feature_dir: Path,
    manifest: LanesManifest,
    coord_base: str,
    target_ref: str,
    excluded_wp_ids: frozenset[str],
) -> VerifyStatus:
    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, excluded_wp_ids)
    return result.status


# --------------------------------------------------------------------------- #
# Residual 1 -- hunk-level supersession (FR-009, plan.md IC-05/IC-06, C-007)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="hunk-level supersession residual (FR-009, C-007) — follow-up under the parent epic")
def test_hunk_level_supersession_ideally_fails(tmp_path: Path) -> None:
    """A survivor's rework edits ON TOP of the canceled WP's change, keeping
    PART of its content verbatim (the final blob still contains WP02's line,
    concatenated with WP01's own new line).

    The axis compares whole-path blobs, not hunks (``wp_attribution.
    _canceled_content_walk``'s R7 rule: a path only produces a
    ``CanceledPathState`` when its NEWEST toucher IS a canceled commit — any
    later non-canceled toucher, even one that only partially rewrites the
    blob, drops the path from ``canceled_content`` entirely). TODAY: the
    canceled content still literally ships (embedded in WP01's rework blob)
    and the gate PASSes. IDEAL: FAIL, since the canceled WP's content did
    not fully leave the tree. Explicitly out of scope for a fix in this
    mission (spec.md C-007 "hunk-level supersession... become follow-up
    issues"; plan.md IC-05/IC-06).
    """
    slug = "residual-hunk"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    path = "src/pkg/shared.py"
    (repo / path).parent.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / path).write_text("BASE = 'shared base'\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp01 seeds shared.py")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))

    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    (repo / path).write_text("BASE = 'shared base'\nWP02 = 'wp02 unique content'\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp02 adds its own line")
    events.append(_event(8, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))

    # WP01 rework: edits ON TOP of WP02's canceled change, keeping its line.
    events.append(_event(9, "WP01", "approved", "in_progress", slug=slug, at="2026-01-03T00:00:00+00:00", stamp=_rev(repo)))
    (repo / path).write_text(
        "BASE = 'shared base'\nWP02 = 'wp02 unique content'\nWP01_REWORK = 'wp01 rework line'\n",
        encoding="utf-8",
    )
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp01 reworks shared.py, keeping wp02's line")
    events.append(_event(10, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-03T00:01:00+00:00", stamp=_rev(repo)))
    events.append(_event(11, "WP01", "for_review", "in_review", slug=slug, at="2026-01-03T00:02:00+00:00", stamp=None))
    events.append(_event(12, "WP01", "in_review", "approved", slug=slug, at="2026-01-03T00:03:00+00:00", stamp=_rev(repo)))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)

    status = _verify_today(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02"}))
    assert status == VerifyStatus.FAIL, "ideal: hunk-level supersession must still FAIL (canceled content survives, embedded)"


# --------------------------------------------------------------------------- #
# Residual 2 -- another approved lane authored the identical (path, blob)
# (research.md R-9 row R4, "another-lane-identical", deferred_with_rationale;
# FAIL is documented as the safe direction)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="other-lane-identical residual (research.md R-9 R4, safe direction) — follow-up under the parent epic",
)
def test_other_lane_identical_content_ideally_passes(tmp_path: Path) -> None:
    """WP02 (canceled, lane-a) commits a path whose content byte-for-byte
    equals content an ENTIRELY SEPARATE approved lane (WP03, lane-b)
    independently authored at the SAME path.

    The canceled-content axis only ever compares WP02's own lane spine
    against the target/window-base (``wp_attribution.resolve_canceled_wp``
    is invoked per-lane); it has no visibility into ``authored_blobs``
    (WP05's OWN squash-sound authorship set, which DOES already carry the
    ``(path, blob)`` pair from lane-b). TODAY: the axis FAILs, naming WP02,
    even though the content genuinely ships via an approved lane's own
    authorship. IDEAL: PASS, since the target's content is fully accounted
    for by approved work. research.md R-9 row R4 records this as
    ``deferred_with_rationale`` — FAIL is the SAFE direction (over-blocking,
    never under-blocking), so this residual is pinned, not fixed, in this
    mission.
    """
    slug = "residual-otherlane"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_a = lane_branch_name(slug, "lane-a", target_branch=_TARGET)

    lane_b = ExecutionLane(
        lane_id="lane-b",
        wp_ids=("WP03",),
        write_scope=("src/pkg",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = replace(manifest, lanes=[*manifest.lanes, lane_b])
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add lane-b to manifest")
    coord_base = _rev(repo)

    lane_branch_b = lane_branch_name(slug, "lane-b", target_branch=_TARGET)
    _git(repo, "branch", lane_a, coord_base)
    _git(repo, "branch", lane_branch_b, coord_base)

    path = "src/pkg/same_content.py"
    blob_content = "SHARED_VALUE = 'identical content authored independently'\n"

    _git(repo, "checkout", "-q", lane_a)
    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / "src/pkg/wp01_own.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))

    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(blob_content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp02 canceled content")
    events.append(_event(8, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))

    _git(repo, "checkout", "-q", lane_branch_b)
    events.append(_event(9, "WP03", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(10, "WP03", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(blob_content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp03 independently authors identical content")
    events.append(_event(11, "WP03", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(12, "WP03", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(13, "WP03", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))
    _wp01_approved_again(events, 14, slug=slug, lane_tip=_rev(repo, lane_a))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)

    _git(repo, "checkout", "-q", "-b", "target-squash", _TARGET)
    _git(repo, "merge", "--squash", "-q", lane_a)
    _git(repo, "commit", "-qm", "squash lane-a")
    _git(repo, "merge", "--squash", "-q", lane_branch_b)
    post_b_status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    if post_b_status.stdout.strip():
        _git(repo, "commit", "-qm", "squash lane-b")

    status = _verify_today(repo, feature_dir, manifest, coord_base, "target-squash", frozenset({"WP02"}))
    assert status == VerifyStatus.PASS, "ideal: content authored by another approved lane must PASS"


# --------------------------------------------------------------------------- #
# Former residual 3 -- commit after the canceled WP's cancel stamp still
# carries its work (research.md R-9 row R6). CLOSED by FR-013: pinned REFUSE.
# --------------------------------------------------------------------------- #


def test_post_cancel_reintroduction_is_refused_by_closed_world(tmp_path: Path) -> None:
    """After WP02's cancel stamp, two OUT-OF-WORKFLOW commits land on the
    lane (no accompanying status events): the first changes the path away,
    the second re-introduces WP02's exact canceled content verbatim.

    Both commits fall entirely OUTSIDE WP02's resolved window (its window
    closed at the cancel stamp), so ``wp_attribution._canceled_content_walk``
    never sweeps them into ``canceled_commits`` at all -- the second stray
    commit is simply the newest, non-canceled toucher of the path, dropping
    it from ``canceled_content`` (R7 supersession) exactly as an ordinary
    approved rework would. Before FR-013 the gate PASSed even though the
    target shipped WP02's canceled content byte-for-byte (research.md R-9
    row R6). NOW: both commits lie outside every resolved WP window, so the
    FR-013 closed world REFUSEs (``commit_outside_windows``) — the content
    cannot ship silently. FAIL (naming WP02) would be more precise, but
    REFUSE is the safe direction, so the leak is closed.
    """
    slug = "residual-postcancel"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / "src/pkg/wp01_own.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))

    path = "src/pkg/canceled_content.py"
    canceled_content = "WP02_VALUE = 'canceled content'\n"

    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(canceled_content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp02 commits its content")
    events.append(_event(8, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))

    (repo / path).write_text("WP02_VALUE = 'something else entirely'\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "out-of-workflow: change it away")

    (repo / path).write_text(canceled_content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "out-of-workflow: re-introduce wp02's exact content")

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)

    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02"}))
    # FR-013: both out-of-workflow commits lie outside every resolved window,
    # so the closed world REFUSEs — the leak is closed (safe non-PASS).
    assert result.status == VerifyStatus.REFUSE, f"post-cancel content must not ship: {result}"
    assert result.refusal_reason is not None
    assert _OUTSIDE_WINDOWS_WORDING in result.refusal_reason
    assert "'src/pkg/canceled_content.py'" in result.refusal_reason


# --------------------------------------------------------------------------- #
# Former residual 4 -- commits by a WP that never entered implementation
# (research.md R-10 B8, issue 5069). CLOSED by FR-013: pinned REFUSE.
# --------------------------------------------------------------------------- #


def test_never_claimed_wp_commit_is_refused_by_closed_world(tmp_path: Path) -> None:
    """WP02 is canceled straight from ``planned`` (never claimed, never
    entered implementation per the events gate) but a real, out-of-workflow
    commit landed on the lane under its nominal ownership before the cancel.

    ``wp_attribution.resolve_canceled_wp`` has no canceled content to
    attribute for a canceled WP that never reached ``claimed``/``in_progress``
    (T020) -- so this real commit's content is never examined by the
    canceled-content axis itself.
    It still ships (attributed only via the lane's own blob-authorship
    walk, ``_collect_authored``, which does not distinguish WPs within a
    lane). Before FR-013 the gate PASSed. NOW: WP01's windows all resolve
    and the stray commit lies in none of them, so the FR-013 closed world
    REFUSEs (``commit_outside_windows``) — never approved content cannot ship
    silently (issue 5069's shape is closed for stamped lanes).
    """
    slug = "residual-neverclaimed"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / "src/pkg/wp01_own.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))

    # WP02's out-of-workflow commit -- no claim/in_progress event precedes it.
    path = "src/pkg/wp02_neverclaimed.py"
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("def wp02_neverclaimed():\n    return 'unclaimed commit'\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "out-of-workflow commit, WP02 never claimed")

    events.append(_event(6, "WP02", "planned", "canceled", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=None))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)

    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02"}))
    # FR-013: WP01's windows all resolved and the stray commit lies in none of
    # them, so the closed world REFUSEs — the leak is closed (safe non-PASS).
    assert result.status == VerifyStatus.REFUSE, f"a never-claimed WP's content must not ship: {result}"
    assert result.refusal_reason is not None
    assert _OUTSIDE_WINDOWS_WORDING in result.refusal_reason
    assert "'src/pkg/wp02_neverclaimed.py'" in result.refusal_reason


# --------------------------------------------------------------------------- #
# Residual 5 -- a sibling that never entered implementation makes an
# out-of-workflow commit INSIDE the canceled WP's window, and that commit is
# misattributed to the canceled WP (traces/design-decisions.md, WP04 review
# cycle 3, "Pinned with the other residuals in WP06"; issue 5069)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="sibling-never-entered-implementation misattribution residual (WP04 cycle-3 decision, issue 5069) — follow-up under the parent epic",
)
def test_sibling_never_entered_implementation_commit_ideally_not_attributed_to_canceled_wp(tmp_path: Path) -> None:
    """A THIRD WP (WP03) shares the lane, going ``planned -> blocked ->
    canceled`` -- it never reaches ``claimed``/``in_progress``, so it never
    "enters implementation" (``wp_attribution._entered_implementation``).
    While canceled WP02's implementation window is still open (between its
    ``in_progress`` open stamp and its ``canceled`` close stamp), an
    out-of-workflow commit lands on the lane under WP03's nominal ownership
    (no accompanying claim/in_progress event for WP03 -- it is never even
    resolved as a "sibling" the contested check considers, since
    ``resolve_canceled_wp`` explicitly SKIPS siblings that fail
    ``_entered_implementation`` (wp_attribution.py ~L453) BEFORE computing
    ``sibling_impl``/``sibling_review``).

    ``wp_attribution._window_commits`` bounds WP02's window purely
    chronologically (every first-parent commit between its own open/close
    stamps, via ``first_parent_commits_in_range`` -- see the module
    docstring's "R6" reference and ``_canceled_content_walk``'s per-commit
    ``is_canceled = sha in canceled_commits`` check): it does not care who
    authored a commit, only whether it falls inside the range. WP03's stray
    commit therefore ends up IN ``canceled_commits`` and, since nothing
    later touches its path, is walked into a real ``CanceledPathState``
    entry -- but tagged ``wp_id="WP02"`` (the resolver call's own
    ``canceled_wp_id`` parameter), not WP03, the WP that actually made the
    commit.

    TODAY: the target carries WP03's content unsuperseded, so the axis FAILs
    -- but the finding NAMES WP02, which never touched this path at all
    (verified empirically before pinning: ``canceled_content ==
    {CanceledPathState(wp_id='WP02', ...)}``, ``verdict == FAIL``).

    Today's FAIL is the SAFE (over-blocking) direction -- WP03's content was
    never approved by any governed window either (T020, the same
    ``_entered_implementation`` gate the canceled WP itself must pass), so
    refusing to let it ship unsuperseded is correct; ONLY the WP the finding
    NAMES is wrong (review cycle 2, reviewer-renata, Issue 1: an earlier
    version of this test pinned PASS as the ideal -- WRONG, because PASS is
    the UNSAFE direction here: if a future change made this shape PASS,
    unapproved content would ship silently, this strict xfail would XPASS,
    and the natural response -- dropping the xfail -- would lock in the
    unsafe behaviour as "fixed". Pinning PASS also contradicted residual #4
    in this same file, which pins FAIL as the ideal for the identical
    issue-5069 class "content never approved by any governed window").

    IDEAL: the verdict must still NOT be PASS (this scenario's only
    ``canceled_content`` candidate is real, unapproved, unsuperseded
    content -- letting it ship silently is never correct), AND no
    ``canceled_content`` finding for this path may name WP02 (the WP that
    never touched it) -- either the finding correctly names WP03 (the WP
    that actually made the commit), or the gate REFUSEs the whole claim as
    unresolvable. traces/design-decisions.md records this exact shape as the
    residual accepted at WP04's review cycle 3 ("its effect equals the
    documented 'commit outside any governed window' limitation (issue 5069)
    -- no approved work is undone. Pinned with the other residuals in
    WP06."); the root cause (chronological window sweep, not per-author) is
    explicitly out of scope for a fix here (C-007) -- only the pin's
    DIRECTION was wrong, not its existence.
    """
    slug = "residual-siblingneverentered"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02", "WP03"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=coord_base))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=coord_base))
    (repo / "src/pkg/wp01_own.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))

    # WP02 opens its implementation window (no commit of its own yet).
    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))

    # WP03 -- never enters implementation: planned -> blocked (no stamp).
    events.append(_event(8, "WP03", "planned", "blocked", slug=slug, at="2026-01-02T00:05:00+00:00", stamp=None))

    # WP03's OUT-OF-WORKFLOW commit lands INSIDE WP02's still-open window.
    path = "src/pkg/wp03_stray.py"
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("def wp03_stray():\n    return 'never approved'\n", encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", "wp03 out-of-workflow commit (never entered implementation)")

    events.append(_event(9, "WP03", "blocked", "canceled", slug=slug, at="2026-01-02T00:06:00+00:00", stamp=None))

    # WP02 closes its window AFTER WP03's stray commit -- the commit falls
    # squarely inside WP02's open..close range.
    events.append(_event(10, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:07:00+00:00", stamp=_rev(repo)))
    _wp01_approved_again(events, 11, slug=slug, lane_tip=_rev(repo))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)

    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02", "WP03"}))

    assert result.status != VerifyStatus.PASS, f"ideal: unapproved content must never silently ship -- PASS is the UNSAFE direction here, got {result.status}"
    # Guard for `divergence is None` (the REFUSE arm of the ideal) so a PASS
    # fails on the assertion ABOVE rather than raising a different exception
    # here -- keeps `raises=AssertionError` meaningful (review cycle 2).
    misattributed_to_wp02 = ()
    if result.divergence is not None:
        misattributed_to_wp02 = tuple(entry for entry in result.divergence.canceled_content if entry.path == "src/pkg/wp03_stray.py" and entry.wp_id == "WP02")
    assert not misattributed_to_wp02, (
        f"ideal: no canceled-content finding for 'src/pkg/wp03_stray.py' may name WP02 (it never touched this path) "
        f"-- the ideal names WP03 or REFUSEs; got {misattributed_to_wp02}"
    )


# --------------------------------------------------------------------------- #
# Residual 6 -- an out-of-workflow commit on the lane BEFORE the first governed
# claim is exempt via the first-claim lane-head anchor (landing review; #5330)
# --------------------------------------------------------------------------- #


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="pre-claim out-of-workflow commit exempt via the first-claim anchor (#5330) — follow-up under the parent epic",
)
def test_pre_claim_out_of_workflow_commit_ideally_refuses(tmp_path: Path) -> None:
    """A content commit lands on the lane before any WP claims it (no status
    event owns it). The FR-013 closed world anchors at the lane head of the first
    governed claim so that allocation-time merges (dependency lanes fast-forwarded
    without ``--no-ff``, the planning-commit merge) are not stragglers — which
    also exempts this commit. TODAY: PASS, the commit ships. IDEAL: REFUSE
    (``commit_outside_windows``), as FR-013 did before the anchor was added.
    """
    slug = "residual-preclaim"
    repo, feature_dir, manifest, coord_base = _init_repo(tmp_path, slug=slug, wp_ids=("WP01", "WP02"))
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    _git(repo, "branch", lane_branch, coord_base)
    _git(repo, "checkout", "-q", lane_branch)

    stray = "src/pkg/pre_claim_stray.py"
    (repo / stray).parent.mkdir(parents=True, exist_ok=True)
    (repo / stray).write_text("STRAY = 'no governed WP owns this'\n", encoding="utf-8")
    _git(repo, "add", stray)
    _git(repo, "commit", "-qm", "out-of-workflow commit before any claim")

    events: list[dict[str, object]] = []
    events.append(_event(1, "WP01", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(2, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=_rev(repo)))
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(3, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(4, "WP01", "for_review", "in_review", slug=slug, at="2026-01-01T00:03:00+00:00", stamp=None))
    events.append(_event(5, "WP01", "in_review", "approved", slug=slug, at="2026-01-01T00:04:00+00:00", stamp=_rev(repo)))
    events.append(_event(6, "WP02", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    events.append(_event(8, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, lane_branch)

    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02"}))
    assert result.status == VerifyStatus.REFUSE, f"ideal: a pre-claim out-of-workflow commit must REFUSE, got {result.status}"


# --------------------------------------------------------------------------- #
# Former residual 7 -- a FULLY-canceled dependency lane's content fast-forwards
# into a dependent mixed lane (#5330 gap, fixed by #5569)
# --------------------------------------------------------------------------- #


def test_fully_canceled_dependency_lane_content_does_not_ship(tmp_path: Path) -> None:
    """lane-a holds only canceled WP03, which committed content; lane-b (approved
    WP01 + canceled WP02) depends on lane-a and fast-forwards it. lane-a is not
    mixed, so its canceled content was never checked; in lane-b it was exempt via
    the first-claim and dependency-tip anchors and authored on lane-b's
    first-parent spine (#5569).

    Fixed: a fully-canceled lane's own commits are subtracted from the authored
    claim and are never exempt from the closed world, so the verdict is a REFUSE
    (``commit_outside_windows``), never PASS.
    """
    slug = "residual-canceled-dep"
    repo, feature_dir, manifest, _base = _init_repo(tmp_path, slug=slug, wp_ids=("WP03",))
    lane_b = ExecutionLane(
        lane_id="lane-b",
        wp_ids=("WP01", "WP02"),
        write_scope=("src/pkg",),
        predicted_surfaces=("code",),
        depends_on_lanes=("lane-a",),
        parallel_group=0,
    )
    manifest = replace(manifest, lanes=[*manifest.lanes, lane_b])
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add lane-b to manifest")
    coord_base = _rev(repo)
    branch_a = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    branch_b = lane_branch_name(slug, "lane-b", target_branch=_TARGET)

    events: list[dict[str, object]] = []
    _git(repo, "branch", branch_a, coord_base)
    _git(repo, "checkout", "-q", branch_a)
    events.append(_event(1, "WP03", "planned", "claimed", slug=slug, at="2026-01-01T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(2, "WP03", "claimed", "in_progress", slug=slug, at="2026-01-01T00:01:00+00:00", stamp=_rev(repo)))
    canceled_path = "src/pkg/wp03_canceled.py"
    (repo / canceled_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / canceled_path).write_text("WP03 = 'canceled dependency work'\n", encoding="utf-8")
    _git(repo, "add", canceled_path)
    _git(repo, "commit", "-qm", "wp03 canceled work")
    events.append(_event(3, "WP03", "in_progress", "canceled", slug=slug, at="2026-01-01T00:02:00+00:00", stamp=_rev(repo)))

    _git(repo, "branch", branch_b, coord_base)
    _git(repo, "checkout", "-q", branch_b)
    _git(repo, "merge", "-q", "--no-edit", branch_a)  # fast-forward, as the allocator does
    events.append(_event(4, "WP01", "planned", "claimed", slug=slug, at="2026-01-02T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(5, "WP01", "claimed", "in_progress", slug=slug, at="2026-01-02T00:01:00+00:00", stamp=_rev(repo)))
    (repo / "src/pkg/wp01_own.py").write_text("WP01 = 'own work'\n", encoding="utf-8")
    _git(repo, "add", "src/pkg/wp01_own.py")
    _git(repo, "commit", "-qm", "wp01 own commit")
    events.append(_event(6, "WP01", "in_progress", "for_review", slug=slug, at="2026-01-02T00:02:00+00:00", stamp=_rev(repo)))
    events.append(_event(7, "WP01", "for_review", "in_review", slug=slug, at="2026-01-02T00:03:00+00:00", stamp=None))
    events.append(_event(8, "WP01", "in_review", "approved", slug=slug, at="2026-01-02T00:04:00+00:00", stamp=_rev(repo)))
    events.append(_event(9, "WP02", "planned", "claimed", slug=slug, at="2026-01-03T00:00:00+00:00", stamp=_rev(repo)))
    events.append(_event(10, "WP02", "claimed", "in_progress", slug=slug, at="2026-01-03T00:01:00+00:00", stamp=_rev(repo)))
    events.append(_event(11, "WP02", "in_progress", "canceled", slug=slug, at="2026-01-03T00:02:00+00:00", stamp=_rev(repo)))

    _git(repo, "checkout", "-q", _TARGET)
    _write_events(repo, feature_dir, events)
    target_ref = _squash_target(repo, _TARGET, branch_b)

    result = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02", "WP03"}))
    assert result.status == VerifyStatus.REFUSE, f"a canceled dependency lane's content must not ship, got {result.status}"
    assert "wp03_canceled.py" in (result.refusal_reason or "")
    # C-003: an attestation can never lift this refusal, so it is never offered as the fix.
    refusal = result.refusal_reason or ""
    assert "fully-canceled" in refusal, refusal
    assert "cannot be overridden" in refusal, refusal
    assert "--attest-canceled-superseded" not in refusal, refusal

    # ... and an attested run of the same shape still refuses, with the same advice.
    attestation = _event(12, "WP02", "canceled", "canceled", slug=slug, at="2026-01-04T00:00:00+00:00", stamp=_rev(repo, branch_b))
    attestation.update(
        actor="operator",
        force=True,
        reason="operator attests canceled content absent or superseded: checked",
        reason_source="operator",
        policy_metadata={ATTESTATION_KEY: CANCELED_SUPERSEDED, "lane_head": _rev(repo, branch_b)},
    )
    _write_events(repo, feature_dir, [*events, attestation])
    attested = _verify_today_result(repo, feature_dir, manifest, coord_base, target_ref, frozenset({"WP02", "WP03"}))
    assert attested.status == VerifyStatus.REFUSE, f"an attestation must not lift a canceled-lane refusal, got {attested.status}"
    assert "--attest-canceled-superseded" not in (attested.refusal_reason or ""), attested.refusal_reason
