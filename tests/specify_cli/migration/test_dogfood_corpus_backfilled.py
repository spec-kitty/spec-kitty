"""Durable guard: this repo's dogfood corpus is backfilled to the event log.

Locks the acceptance from mission #2816 WP03 / IC-01b. After the runtime-state
corpus cutover, every runtime-bearing dogfood mission under ``kitty-specs/``
carries its frontmatter/``tasks.md``-checkbox runtime state as **seed events**
(an ``InnerStateChanged`` annotation quartet + a seed ``planned -> claimed``
transition) and a ``meta.json`` ``status_phase = "1"`` flip. This guard fails
loudly if a later change empties, staples, or de-seeds the committed corpus —
the exact regression that would make WP04's *unconditional* snapshot readers
reduce to an empty snapshot and go red.

It is **read-only** over the committed corpus in this test file's own checkout.
The path is deliberately not resolved through the ambient project root: CI runs
from a detached git worktree, and the production resolver intentionally follows
that worktree back to the sibling main checkout. Using it here would combine
PR-head code with main-head corpus data. The proof surface is the reduced
snapshot + the WP01
:func:`verify_backfill` fail-closed parity check — not a synthetic fixture.

Scope notes:

* The actively-running cutover mission itself (:data:`_SELF_MISSION`) is
  intentionally **excluded** from the backfill (WP03 self-interference guard):
  it is event-sourced live via its own transitions and must not be seeded/flipped
  mid-flight. It is skipped here so this guard never depends on the live
  mission's momentary phase.
* Never-claimed / no-runtime missions legitimately reduce to an empty snapshot;
  the guard only asserts on missions that *carry* runtime state.

WP10 re-key (FR-010 / C-003 / NFR-006 / IC-09): eligibility
(:func:`~specify_cli.status.cutover_eligibility.eligible_runtime_missions`)
used to key on the frontmatter ``has_evictable_state()`` signal. WP04/WP05
retired frontmatter runtime authoring, so that signal goes permanently empty
for every mission born after the retirement — a future regression in the
WP09 birth-cutover seam would leave such a mission un-flipped/empty and this
guard would never see it (a vacuous pass). Eligibility is now keyed on
independent evidence read directly from ``status.events.jsonl`` (see
:func:`~specify_cli.status.cutover_eligibility.mission_carries_event_log_runtime`)
— never on the retired frontmatter signal, and never on ``status_phase``
itself (circular: that is exactly the field this guard verifies was
flipped). See ``test_reked_lock_reds_on_born_un_reconciled_mission`` for the
non-vacuity proof.

WP03 (mission runtime-state-birth-cutover-all-paths, FR-002/FR-009): the
eligibility predicate and the birth-invariant assertion body were extracted
to :mod:`specify_cli.status.cutover_eligibility` (a pure move,
behavior-preserving) so the diff-scoped pre-merge guard
(``spec-kitty cutover-guard``) can share the exact same authority instead of
forking a second copy.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.migration.backfill_runtime_state import (
    _claim_anchors,
    _seed_id,
    read_legacy_runtime,
)
from specify_cli.status import (
    Lane,
    StatusEvent,
    build_claim_policy_metadata,
)
from specify_cli.status._unsafe import append_events_atomic_verified
from specify_cli.status import emit as _emit
from specify_cli.status.cutover_eligibility import (
    assert_birth_invariant_holds as _assert_birth_invariant_holds,
)
from specify_cli.status.cutover_eligibility import (
    eligible_runtime_missions as _eligible_runtime_missions,
)
from specify_cli.status.cutover_eligibility import runtime_wps as _runtime_wps
from specify_cli.status.cutover_eligibility import is_stamped as _is_stamped

pytestmark = [pytest.mark.integration, pytest.mark.slow]

#: The cutover mission itself — event-sourced live, intentionally NOT backfilled
#: (WP03 self-interference guard). Excluded from every assertion below.
_SELF_MISSION = "runtime-state-corpus-cutover-01KXZ0AX"

#: Non-vacuous floor. The corpus carried ~285 runtime-bearing missions at cutover;
#: a stale/emptied/de-seeded corpus (the regression this guards) collapses toward
#: zero. Kept well under the live count so ordinary corpus growth/archival never
#: makes this brittle, while a catastrophic emptying still fails loudly.
_MIN_BACKFILLED_RUNTIME_MISSIONS = 100

def _test_checkout_root() -> Path:
    """Return the checkout containing this guard, including in a CI worktree."""
    return Path(__file__).resolve().parents[3]


def _kitty_specs() -> Path:
    """Return the committed ``kitty-specs/`` corpus from this exact checkout."""
    corpus = _test_checkout_root() / "kitty-specs"
    if corpus.is_dir():
        return corpus
    raise AssertionError(f"no kitty-specs corpus in this test checkout: {corpus}")


def test_kitty_specs_is_pinned_to_this_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard never follows an ambient root override to another corpus."""
    (tmp_path / "kitty-specs").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    assert _kitty_specs() == _test_checkout_root() / "kitty-specs"


def test_kitty_specs_fails_when_corpus_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A moved test or relocated corpus cannot turn the guard into a vacuous skip."""
    moved_test = tmp_path / "tests" / "specify_cli" / "migration" / "test_guard.py"
    moved_test.parent.mkdir(parents=True)
    moved_test.write_text("# moved test anchor\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "__file__", str(moved_test))

    with pytest.raises(AssertionError, match="no kitty-specs corpus"):
        _kitty_specs()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.git_repo
def test_kitty_specs_is_pinned_to_real_worktree_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard does not follow a linked worktree's ``.git`` pointer to its primary.

    This exercises the production resolver's Tier 2 channel that caused #874: CI can
    invoke this test from a detached worktree whose canonical project root is a
    sibling primary checkout. Both ``cwd`` and the test-file anchor point into the
    worktree, so reintroducing ambient project-root resolution must resolve to the
    primary and fail this assertion.
    """
    primary = tmp_path / "primary"
    primary.mkdir()
    (primary / ".kittify").mkdir()
    corpus_marker = primary / "kitty-specs" / "checkout-marker.txt"
    corpus_marker.parent.mkdir()
    corpus_marker.write_text("committed corpus\n", encoding="utf-8")
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "dogfood-corpus-guard@spec-kitty.test")
    _git(primary, "config", "user.name", "dogfood corpus guard test")
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "baseline")

    worktree = tmp_path / "detached-ci-worktree"
    _git(primary, "worktree", "add", "-q", "-b", "issue-890-corpus-lane", str(worktree))
    worktree_test = (
        worktree / "tests" / "specify_cli" / "migration" / "test_dogfood_corpus_backfilled.py"
    )
    worktree_test.parent.mkdir(parents=True)
    worktree_test.write_text("# detached CI test anchor\n", encoding="utf-8")

    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.chdir(worktree)
    monkeypatch.setattr(sys.modules[__name__], "__file__", str(worktree_test))

    assert _kitty_specs() == worktree / "kitty-specs"


def _backfilled_runtime_missions(corpus: Path) -> list[Path]:
    """All backfilled (``status_phase>=1``), runtime-carrying missions, minus self."""
    out: list[Path] = []
    for mission_dir in sorted(corpus.iterdir()):
        if not mission_dir.is_dir() or mission_dir.name == _SELF_MISSION:
            continue
        if _is_stamped(mission_dir) and _runtime_wps(mission_dir):
            out.append(mission_dir)
    return out


def _first_complete_wp_with_roster(missions: list[Path]) -> tuple[Path, str] | None:
    """Find the first (mission, wp) that is complete under the frontmatter-roster model.

    Complete means: a NON-EMPTY authored ``subtasks:`` frontmatter roster whose
    every id is ``done`` in the reduced snapshot. This is exactly the
    non-vacuous shape ``_infer_subtasks_complete`` treats as complete since
    #2816 IC-10 (roster from frontmatter, completion from the event-sourced
    snapshot).
    """
    from specify_cli.core.subtask_rows import authored_subtask_roster

    for mission_dir in missions:
        for wp_id, state in _runtime_wps(mission_dir).items():
            subtasks = state.get("subtasks") or {}
            done_ids = {tid for tid, status in subtasks.items() if str(status) == "done"}
            roster = authored_subtask_roster(mission_dir, wp_id)
            if roster and all(tid in done_ids for tid in roster):
                return mission_dir, wp_id
    return None


def test_corpus_is_backfilled_non_vacuous() -> None:
    """The committed corpus carries a substantial backfilled runtime population.

    Fails loudly on a stale/emptied/de-seeded corpus — the core WP04 regression
    (an empty snapshot reducing every runtime read to ``None``/``False``).
    """
    missions = _backfilled_runtime_missions(_kitty_specs())
    assert len(missions) >= _MIN_BACKFILLED_RUNTIME_MISSIONS, (
        f"only {len(missions)} backfilled runtime-carrying missions found "
        f"(expected >= {_MIN_BACKFILLED_RUNTIME_MISSIONS}); the dogfood corpus "
        "looks stale/emptied/de-seeded — WP03 backfill (#2816) regressed"
    )


@pytest.mark.timeout(600)
def test_all_eligible_missions_snapshot_non_empty_and_verify_ok() -> None:
    """Every eligible mission (real committed corpus) is flipped and populated.

    See :func:`~specify_cli.status.cutover_eligibility.assert_birth_invariant_holds`
    for the assertion body shared with the anti-vacuity fixture test. The
    live cutover mission itself is excluded (module docstring: WP03
    self-interference guard).
    """
    _assert_birth_invariant_holds(_kitty_specs(), exclude={_SELF_MISSION})


def test_reked_lock_reds_on_born_un_reconciled_mission(tmp_path: Path) -> None:
    """T049 anti-vacuity proof (FR-010 / IC-09) — the whole point of WP10.

    Builds a synthetic mission that is authoring-retired (no frontmatter
    runtime state anywhere on disk — the FR-008/WP05 shape) but whose event
    log carries a genuine LIVE claim (real ``policy_metadata``, exactly the
    shape a born mission gets at the WP09 birth-cutover seam) while
    ``status_phase`` was never flipped — a drifted, un-birth-stamped mission
    (the fixture Mission is accepted but unstamped: terminal evidence).

    Two things must both hold, or the re-key is wrong:

    1. The HARD-FORBIDDEN frontmatter predicate (``has_evictable_state()``)
       does NOT see this mission as eligible at all — proving that keying
       eligibility there (the pre-WP10 shape) would make the guard silently
       skip it (a vacuous pass), never asserting anything and never redding.
    2. The re-keyed
       :func:`~specify_cli.status.cutover_eligibility.eligible_runtime_missions`
       DOES see it, and
       :func:`~specify_cli.status.cutover_eligibility.assert_birth_invariant_holds`
       REDS on it (the un-flipped ``status_phase`` assertion fires) — proving
       the re-keyed lock is a genuine, non-vacuous guard against exactly this
       future regression.
    """
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    mission_dir = corpus / "drifted-un-birth-stamped-01KZQXTR"
    mission_dir.mkdir()
    tasks = mission_dir / "tasks"
    tasks.mkdir()

    mission_id = "01KZQXTRH8T2X6R4N9YV3D5C7B"
    # No status_phase key at all in meta.json — genuinely un-flipped/un-birthed.
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_dir.name,
                "mission_type": "software-dev",
                # Accepted but never stamped: a pre-accept Mission is exempt (#5835).
                "accepted_at": "2026-07-25T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    # Authoring-retired WP frontmatter (FR-008/WP05 shape): no shell_pid /
    # agent / assignee / tracker_refs anywhere — zero evictable state on disk.
    (tasks / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Drifted Demo\nexecution_mode: code_change\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    # No tasks.md checkbox rows either — post-retirement, subtask completion
    # is entirely event-sourced (the checkbox proxy is retired, not merely
    # frontmatter). A checkbox row (even unchecked) would make the legacy
    # reader's ``subtasks`` dict non-empty and defeat the anti-vacuity proof
    # below (Sonar-safe finding: verified empirically against the real reader).
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01 Demo\n\n", encoding="utf-8")
    # A genuine LIVE claim — the exact wire shape a real born mission carries
    # (real policy_metadata, not a backfill seed).
    claim = StatusEvent(
        event_id="01DRIFTDRIFTDRIFTDRIFTDRIF",
        mission_slug=mission_dir.name,
        mission_id=mission_id,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-07-25T09:00:00+00:00",
        actor="claude:sonnet:pedro",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=55221,
            shell_pid_created_at="2026-07-25T08:59:00+00:00",
            agent="claude:sonnet:pedro",
        ),
    )
    append_events_atomic_verified(mission_dir, [claim])

    # (1) Anti-vacuity call-out: the HARD-FORBIDDEN predicate is blind here.
    legacy = read_legacy_runtime(mission_dir)
    anchors = _claim_anchors(mission_dir)
    forbidden_predicate_would_see_it = any(
        row.has_evictable_state() and wp_id in anchors for wp_id, row in legacy.items()
    )
    assert forbidden_predicate_would_see_it is False, (
        "fixture must be invisible to the retired has_evictable_state() "
        "predicate, or this is not proving the vacuity WP10 closes"
    )

    # (2) The re-keyed predicate sees it...
    assert mission_dir in _eligible_runtime_missions(corpus)

    # ...and the lock genuinely REDS on it (non-vacuous).
    with pytest.raises(AssertionError, match="not cut over"):
        _assert_birth_invariant_holds(corpus)


def _born_claimed_mission(corpus: Path, slug: str, extra_meta: dict[str, object]) -> Path:
    """A natively-born, claimed Mission: empty-template WP frontmatter, no stamp."""
    mission_dir = corpus / slug
    (mission_dir / "tasks").mkdir(parents=True)
    mission_id = "01KZEXEMPTCORPUS000000001"
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": mission_id, "mission_slug": slug, **extra_meta}),
        encoding="utf-8",
    )
    # Empty template claim fields (agent/assignee/shell_pid) read as no runtime.
    (mission_dir / "tasks" / "WP01-demo.md").write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Demo"\nagent: ""\nassignee: ""\nshell_pid: ""\n---\n\n# WP01\n',
        encoding="utf-8",
    )
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01 Demo\n\n- [x] T001 ref\n", encoding="utf-8")
    claim = StatusEvent(
        event_id="01KZEXEMPTCORPUS000000CLM1",
        mission_slug=slug,
        mission_id=mission_id,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-10-06T09:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=4242,
            shell_pid_created_at="2026-10-06T08:59:00+00:00",
            agent="claude",
        ),
    )
    append_events_atomic_verified(mission_dir, [claim])
    return mission_dir


def test_pre_accept_mission_is_not_eligible_but_accepted_twin_is(tmp_path: Path) -> None:
    """#5300: ``assert_birth_invariant_holds`` shares the pre-accept exemption.

    A claimed, never-accepted Mission with no legacy frontmatter runtime is not
    eligible (its stamp is deferred to accept), while an otherwise identical
    Mission with ``accepted_at`` and no stamp stays eligible and so still REDS
    the invariant. A fully healthy stamped Mission is not built here (it would
    need a backfill run), so eligibility is asserted directly.
    """
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    exempt = _born_claimed_mission(corpus, "in-flight-01KZEXEMPT", {})
    accepted = _born_claimed_mission(corpus, "accepted-unstamped-01KZEXEMPT", {"accepted_at": "2026-10-06T10:00:00+00:00"})

    assert _eligible_runtime_missions(corpus) == [accepted]
    assert exempt not in _eligible_runtime_missions(corpus)
    with pytest.raises(AssertionError, match="accepted-unstamped"):
        _assert_birth_invariant_holds(corpus)


def test_sampled_complete_wp_reads_complete_via_public_gate() -> None:
    """A complete WP reads complete through the public frontmatter-roster gate.

    Proves the committed corpus reads green under the #2816 IC-10 model: the
    subtask roster is the authored ``subtasks:`` frontmatter list and completion
    is resolved solely from the event-sourced snapshot. A WP with a non-empty
    authored roster whose every id is ``done`` in the snapshot must read complete
    through the public :func:`_infer_subtasks_complete` — the ``tasks.md``
    checkbox proxy and the phase-1 authority predicate are both retired.
    """
    missions = _backfilled_runtime_missions(_kitty_specs())
    found = _first_complete_wp_with_roster(missions)
    if found is None:
        pytest.skip("no complete-with-authored-roster WP in the backfilled corpus to sample")
        return
    mission_dir, wp_id = found

    assert _emit._infer_subtasks_complete(mission_dir, wp_id) is True, (
        f"{mission_dir.name}:{wp_id}: public subtask-completeness gate is not True "
        "despite a fully-done authored roster — the seeded corpus reads incomplete"
    )


def test_no_repo_root_event_file() -> None:
    """INV-5 / #2815: the backfill created no event file at the repository root.

    All seed writes resolve through ``canonicalize_feature_dir`` inside the
    library, so no ``status.events.jsonl`` ever lands beside the repo root.
    """
    root = _test_checkout_root()
    assert not (root / "status.events.jsonl").exists(), (
        "a status.events.jsonl exists at the repository root — a backfill write "
        "escaped canonicalize_feature_dir (INV-5 / #2815 regression)"
    )


def test_corpus_contains_no_authored_derived_resolved_binding_seed_rows() -> None:
    """C-011: historical authored recommendations never masquerade as actuals.

    An earlier in-mission backfill revision emitted deterministic
    ``resolved_binding`` seed rows copied from WP frontmatter. The binding ADR
    forbids that provenance. Closeout removed those rows precisely by their
    namespaced seed ids; this corpus guard prevents any rerun from restoring
    the fabricated actuals while leaving genuine runtime annotations untouched.
    """
    offenders: list[str] = []
    for mission_dir in sorted(_kitty_specs().iterdir()):
        meta_path = mission_dir / "meta.json"
        events_path = mission_dir / "status.events.jsonl"
        if not mission_dir.is_dir() or not meta_path.is_file() or not events_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mission_id = str(meta.get("mission_id") or "").strip()
        if not mission_id:
            continue
        for line_number, raw_line in enumerate(
            events_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            payload = json.loads(raw_line)
            wp_id = str(payload.get("wp_id") or "").strip()
            if wp_id and payload.get("event_id") == _seed_id(
                mission_id,
                wp_id,
                "resolved_binding",
            ):
                offenders.append(f"{mission_dir.name}:{line_number}:{wp_id}")

    assert offenders == [], (
        "authored-derived resolved_binding seed rows reappeared in the corpus: "
        + ", ".join(offenders[:20])
    )
