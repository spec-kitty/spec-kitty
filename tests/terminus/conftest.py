"""Shared mock-free harness for the terminus-integrity red-first repros (WP01, #5001).

Every helper here builds a REAL on-disk git coordination mission and drives the
REAL ``spec-kitty`` CLI through ``subprocess`` -- ``_run_git`` / ``subprocess``
is NEVER mocked, so each repro exercises ``git/ref_advance.py``'s real
``update-ref`` argv (contract §"Property test"). Approved commit SHAs are ALWAYS
read from lane-branch git tips, never from ``status.events.jsonl`` rows (RN-Q3 /
contract Preconditions -- forbids the vacuous ``_assert_merged_wps_done_on_target``
pattern).

The harness is intentionally O(#WPs), not O(repo history) (NFR-003): reachability
is probed with ``git merge-base --is-ancestor`` and patch-id equivalence over the
small ``pre-merge-target..post-merge-target`` window, never a full history walk.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest

from kernel.clock import now_utc_iso
from tests._support.git_cli import git_out


def _now_iso() -> str:
    """UTC ISO-8601 timestamp via the repo's canonical clock seam."""
    return now_utc_iso()


# ---------------------------------------------------------------------------
# Real-CLI wiring: run THIS worktree's ``src`` via ``python -m specify_cli`` so
# the subprocess exercises the pre-fix (and, after the fix WPs, post-fix) code.
# No installed-wheel dependency, no ``_run_git`` / subprocess seam patched.
# ---------------------------------------------------------------------------

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SRC = _WORKTREE_ROOT / "src"

# Fixture construction imports ``specify_cli`` / ``kernel`` from THIS worktree's
# ``src`` so the builders match the CLI-under-test exactly, regardless of how the
# venv / editable install resolves those packages. ``pytest.ini``'s
# ``pythonpath = src`` already puts this worktree's ``src`` on THIS process's
# ``sys.path`` at the matching rootdir, so no manual insert is needed for
# in-process imports here; ``_SRC`` itself is still needed below to build the
# subprocess's ``PYTHONPATH``.
_MISSION_TYPE = "software-dev"
_STATUS_EVENTS_FILENAME = "status.events.jsonl"

# The canonical 9-lane happy path a WP walks to become merge-ready.
_APPROVE_CHAIN: tuple[tuple[str, str], ...] = (
    ("planned", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
)


# ---------------------------------------------------------------------------
# Low-level git helpers (real git, real subprocess)
# ---------------------------------------------------------------------------


def _run(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _git_out(repo: Path, *args: str) -> str:
    return git_out(repo, *args)


def git_rev(repo: Path, ref: str) -> str:
    """Resolve *ref* to a commit SHA (``""`` when the ref does not exist)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def commits_between(repo: Path, base: str, tip: str) -> list[str]:
    """Return the SHAs reachable from *tip* but not *base* (``git rev-list base..tip``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-list", f"{base}..{tip}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def patch_id(repo: Path, sha: str) -> str:
    """Return the stable patch-id of *sha* (identity of the change, not the commit).

    Patch-id equivalence lets the excluded-commit check catch cherry-picked,
    rebased, or re-lettered copies of canceled code -- the same diff under a new
    SHA (contract postcondition 1 / #4945 / #4977).
    """
    show = subprocess.run(
        ["git", "-C", str(repo), "show", sha],
        capture_output=True,
        text=True,
        check=False,
    )
    pid = subprocess.run(
        ["git", "-C", str(repo), "patch-id", "--stable"],
        input=show.stdout,
        capture_output=True,
        text=True,
        check=False,
    )
    first = pid.stdout.split()
    return first[0] if first else ""


def blob_present_at(repo: Path, ref: str, path: str) -> bool:
    """True iff *path* exists as a blob in *ref*'s tree.

    The **squash-sound** observable. A squash merge preserves neither lane-tip
    SHAs nor per-commit patch-ids, so ``sha_reachable`` / ``patch_ids_in_window``
    are structurally unable to answer "did a removed file ship" under squash (the
    aggregate squash commit re-diffs and drops ancestry). Tree/blob presence is the
    only content observable that survives squash: it asks whether the *content path*
    is materialized on *ref*, independent of which commit authored it.

    Implemented with ``git cat-file -e <ref>:<path>`` — a deterministic real
    subprocess, never mocked (harness contract). Returns ``False`` for an absent
    path or an unresolvable ref (a deleted/absent file ships no content).
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def output_names_content_fail(result: subprocess.CompletedProcess[str]) -> bool:
    """True iff a merge's output NAMES a reconciliation FAIL / un-attributable content.

    The squash-content repros pin the FAIL **cause**, not mere file absence (post-plan
    renata: absence is trivially true on any abort/refusal, so it cannot distinguish
    the content axis from an unrelated early error). A correct default-squash gate
    FAILs with the operator-facing ``Reconciliation FAILED: … un-attributable …``
    recovery line (``VerifyResult.recovery_guidance`` in ``consolidation/reconciliation.py``).

    Whitespace is collapsed to single spaces first so a rich-console line-wrap
    (``Reconciliation\\nFAILED``) still matches; the ``attributable`` token matches
    the ``un-attributable`` divergence detail even if the hyphen wraps.
    """
    flat = " ".join((result.stdout + "\n" + result.stderr).split()).lower()
    return "reconciliation failed" in flat or "attributable" in flat


def reached_reconciliation_verdict(result: subprocess.CompletedProcess[str]) -> bool:
    """True iff *result*'s output NAMES one of the gate's three verdicts.

    ``VerifyResult.recovery_guidance()`` / ``_reconciliation_pass_message()``
    (``consolidation/reconciliation.py`` / ``consolidation/executor.py``) always
    prefix the operator-facing line with ``"Reconciliation verified"`` (PASS),
    ``"Reconciliation FAILED"`` (FAIL), or ``"Reconciliation refused"`` (REFUSE)
    — a run that reached the gate says one of these, whatever it decided (T004:
    "reached the verdict", not which one). Whitespace-collapsed so a
    rich-console line wrap still matches (mirrors
    :func:`output_names_content_fail`).
    """
    flat = " ".join((result.stdout + "\n" + result.stderr).split()).lower()
    return any(marker in flat for marker in ("reconciliation verified", "reconciliation failed", "reconciliation refused"))


def sha_reachable(repo: Path, sha: str, ref: str) -> bool:
    """True iff *sha* is an ancestor of (reachable from) *ref*."""
    if not sha:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def patch_ids_in_window(repo: Path, base: str, tip: str) -> set[str]:
    """Patch-ids of every commit in ``base..tip`` (the small post-merge window)."""
    ids: set[str] = set()
    for sha in commits_between(repo, base, tip):
        pid = patch_id(repo, sha)
        if pid:
            ids.add(pid)
    return ids


# ---------------------------------------------------------------------------
# Coordination-mission fixture (real repo, coord topology, materialized worktree)
# ---------------------------------------------------------------------------


@dataclass
class CoordMission:
    """A real on-disk coord-topology mission the terminus commands operate on."""

    repo: Path
    home: Path
    feature_dir: Path
    slug: str
    mission_id: str
    mid8: str
    coord_branch: str
    target_branch: str
    lane_branches: dict[str, str] = field(default_factory=dict)
    canceled_wps: set[str] = field(default_factory=set)
    _event_seq: int = 0

    # -- git conveniences -------------------------------------------------

    def rev(self, ref: str) -> str:
        return git_rev(self.repo, ref)

    def lane_branch(self, wp_id: str) -> str:
        return self.lane_branches[wp_id]

    def approved_shas_from_lane_tips(self, wp_ids: Iterable[str]) -> dict[str, list[str]]:
        """Approved commit SHAs, read from lane-branch git tips ONLY (RN-Q3).

        Never consults ``status.events.jsonl``; the claim the property/repro
        assertions compare against is the set of commits a lane tip carries
        beyond the coordination base. This reads the lane TIPS: it equals the
        approved content only because the product refuses a lane that moved
        after its approval, so a test that adds a lane commit after approval
        must not use it as the approved set.
        """
        out: dict[str, list[str]] = {}
        for wp_id in wp_ids:
            branch = self.lane_branches[wp_id]
            out[wp_id] = commits_between(self.repo, self.coord_branch, branch)
        return out


def _write_meta(mission: CoordMission) -> None:
    meta = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": _MISSION_TYPE,
        "target_branch": mission.target_branch,
        "coordination_branch": mission.coord_branch,
        "purpose_tldr": "#5001 terminus-integrity red-first harness",
        "purpose_context": "every approved WP reachable from target, nothing excluded is",
    }
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(mission: CoordMission, wp_ids: Sequence[str]) -> None:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    lanes = [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + idx)}",
            wp_ids=(wp_id,),
            write_scope=(f"src/pkg/{wp_id.lower()}.py",),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for idx, wp_id in enumerate(wp_ids)
    ]
    manifest = LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=lanes,
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)


def _write_wp_file(mission: CoordMission, wp_id: str) -> None:
    (mission.feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\nagent: implementer-ivan\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _event(
    mission: CoordMission,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    *,
    policy_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    mission._event_seq += 1
    event: dict[str, object] = {
        "actor": "reviewer-renata" if to_lane == "approved" else "implementer-ivan",
        "at": _now_iso(),
        "event_id": f"01HXYZ5001{mission._event_seq:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission.slug,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": f"review-{wp_id}" if to_lane == "approved" else None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }
    if policy_metadata is not None:
        event["policy_metadata"] = policy_metadata
    return event


def _approve_events(mission: CoordMission, wp_id: str) -> list[dict[str, object]]:
    """The approval chain with NO ``lane_head`` stamp (a hand-built, unstamped log).

    Kept for the few callers that build their own status log by hand; the shared
    builders use :func:`_stamped_approve_events` instead.
    """
    return [_event(mission, wp_id, frm, to) for frm, to in _APPROVE_CHAIN]


def _stamped_approve_events(mission: CoordMission, wp_id: str, *, claim_head: str, approved_head: str) -> list[dict[str, object]]:
    """The approval chain, every event stamped with a real lane tip (the real governed workflow).

    ``claim_head`` is the lane tip when the WP was claimed (before its own commit);
    ``approved_head`` is the lane tip once its content was committed. The caller
    reads both from git, never a constant, and writes the log AFTER the lane's
    commits exist so each stamp names a tip that was real.
    """
    return [
        _event(mission, wp_id, frm, to, policy_metadata={"lane_head": claim_head if idx < 2 else approved_head}) for idx, (frm, to) in enumerate(_APPROVE_CHAIN)
    ]


def _commit_status_events(mission: CoordMission, events: Sequence[dict[str, object]], message: str) -> None:
    """Write the status log, commit it on the target branch, and fast-forward the coordination branch to it.

    Runs AFTER every lane commit exists (so each ``lane_head`` stamp names a real
    tip) and BEFORE the coordination worktree is materialized. Lane branches keep
    their own base, so ``commits_between(coord_branch, lane_branch)`` still names
    exactly the lane's own commits.
    """
    _git(mission.repo, "checkout", "-q", mission.target_branch)
    events_path = mission.feature_dir / _STATUS_EVENTS_FILENAME
    events_path.write_text("".join(json.dumps(ev, sort_keys=True) + "\n" for ev in events), encoding="utf-8")
    _git(mission.repo, "add", str(events_path.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", message)
    _git(mission.repo, "branch", "-f", mission.coord_branch, mission.target_branch)


_GITIGNORE_WORKTREES_LINE = ".worktrees/"


def _merged_gitignore_content(extra_base_files: Mapping[str, str] | None) -> str:
    """Build the init commit's ``.gitignore`` content (T002 fixture hygiene).

    Every fixture repo ignores ``.worktrees/`` so a POST-build ``git status``
    never sees the coordination worktree as an untracked/dirty path (the
    gitlink hazard T002 closes). Merged with any caller-supplied
    ``.gitignore`` passed via ``extra_base_files`` (``test_resume_phantom_only.py``
    passes one) so neither line set is lost; lines are de-duplicated and the
    caller's own ordering is preserved after the ``.worktrees/`` line.
    """
    lines = [_GITIGNORE_WORKTREES_LINE]
    caller_gitignore = (extra_base_files or {}).get(".gitignore", "")
    for line in caller_gitignore.splitlines():
        if line and line not in lines:
            lines.append(line)
    return "\n".join(lines) + "\n"


def _init_fixture_repo(
    tmp_path: Path,
    *,
    mid8: str,
    slug: str,
    target_branch: str,
    extra_base_files: Mapping[str, str] | None = None,
) -> CoordMission:
    """Materialize the base repo + isolated HOME shared by every coord-mission
    builder (T001): real ``git init``, test identity config, and a single
    init commit carrying ``README.md`` and a ``.gitignore`` that always
    ignores ``.worktrees/`` (merged with any ``extra_base_files[".gitignore"]``
    — see :func:`_merged_gitignore_content`). Every other ``extra_base_files``
    entry is committed alongside as genuinely PRE-EXISTING content, before the
    coordination branch or any lane branch is cut (#5022: a canceled WP's
    deletion of a pre-existing product file no approved lane re-authors).

    Stages the init commit with EXPLICIT paths (never ``git add .`` / ``-A``
    — T002): today every builder runs a blanket ``git add`` before
    :meth:`CoordinationWorkspace.resolve` materializes the coordination
    worktree, so the gitlink hazard only bites a POST-build ``git add .``
    (which then trips the dirty-target refusal in ``git/ref_advance.py``);
    this helper simply never introduces that risk in the first place.

    Returns a :class:`CoordMission` with empty ``lane_branches`` — the caller
    still owns writing planning artifacts, cutting the coordination branch
    (:func:`_cut_coord_branch`), cutting lane branches
    (:func:`_cut_lane_branch`), and finishing (:func:`_finish_coord_mission`).
    """
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    shutil.copytree(_bootstrapped_home_template(), home, dirs_exist_ok=True)
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_branch = CoordinationWorkspace.branch_name(slug, mid8)

    mission = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=coord_branch,
        target_branch=target_branch,
    )

    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", target_branch, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Terminus Test")
    _git(repo, "config", "commit.gpgsign", "false")

    (repo / "README.md").write_text("init\n", encoding="utf-8")
    (repo / ".gitignore").write_text(_merged_gitignore_content(extra_base_files), encoding="utf-8")
    staged = ["README.md", ".gitignore"]
    for rel_path, content in (extra_base_files or {}).items():
        if rel_path == ".gitignore":
            continue
        base_file = repo / rel_path
        base_file.parent.mkdir(parents=True, exist_ok=True)
        base_file.write_text(content, encoding="utf-8")
        staged.append(rel_path)
    _git(repo, "add", *staged)
    _git(repo, "commit", "-qm", "init")
    return mission


def _cut_coord_branch(mission: CoordMission) -> None:
    """Cut the coordination branch at the current HEAD of ``mission.repo``."""
    _git(mission.repo, "branch", mission.coord_branch)


def _commit_planning_artifacts(mission: CoordMission, message: str) -> None:
    """Stage the whole ``kitty-specs/<slug>/`` planning-artifact tree with an
    EXPLICIT path (never ``git add .`` / ``-A`` — T002) and commit it.
    """
    repo = mission.repo
    _git(repo, "add", str(mission.feature_dir.relative_to(repo)))
    _git(repo, "commit", "-qm", message)


def _cut_lane_branch(
    mission: CoordMission,
    lane_id: str,
    commits: Sequence[Callable[[Path], None]],
    *,
    base: str | None = None,
) -> str:
    """Cut one lane branch off *base* (default: the coordination branch),
    check it out, run each of ``commits`` in order, then return to
    ``mission.target_branch``.

    Each callable in ``commits`` receives the repo path and is responsible
    for its own file writes, EXPLICIT-path ``git add`` (T002 — never
    ``git add .`` / ``-A``), and ``git commit``. Returns the lane branch
    name; callers register ``mission.lane_branches[wp_id] = branch`` for
    every WP the lane carries, since the WP<->lane mapping differs per
    builder (one lane per WP vs. one shared lane for several WPs).
    """
    repo = mission.repo
    lane_branch = f"kitty/mission-{mission.slug}-{lane_id}"
    _git(repo, "branch", lane_branch, base or mission.coord_branch)
    _git(repo, "checkout", "-q", lane_branch)
    for commit in commits:
        commit(repo)
    _git(repo, "checkout", "-q", mission.target_branch)
    return lane_branch


def _finish_coord_mission(mission: CoordMission) -> CoordMission:
    """Materialize the coordination worktree (production topology) and
    return *mission*. Callers finish planting on every branch FIRST — this
    is always the LAST step of a builder (T005: no post-build mutation is
    needed for a correct fixture, but planting after resolve is untested and
    unnecessary).
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    CoordinationWorkspace.resolve(mission.repo, mission.slug, mission.mid8)
    return mission


def build_coord_mission(
    tmp_path: Path,
    *,
    wps: Sequence[str] = ("WP01",),
    target_branch: str = "main",
    mid8: str = "01M5001A",
    extra_base_files: dict[str, str] | None = None,
) -> CoordMission:
    """Materialize a real coord-topology mission with every WP approved.

    Returns a :class:`CoordMission`. Each WP gets its own lane branch carrying a
    real code commit beyond the coordination base; the status log walks each WP to
    ``approved`` so the terminus commands' merge-ready precondition is satisfied
    and control reaches the terminus phase where the bug lives (not an unrelated
    early gate).

    ``mid8`` is an uppercase ULID-style disambiguator; the slug ends with it so the
    coordination branch is ``kitty/mission-<slug>`` (the production 083+ layout
    ``CoordinationWorkspace.branch_name`` reconstructs verbatim).

    ``extra_base_files`` (``{repo_relative_path: content}``) are committed as part
    of the repo's INIT commit — i.e. BEFORE the coordination branch and every lane
    branch are cut — so every lane inherits them as genuinely PRE-EXISTING content
    (#5022: a canceled WP's deletion of a pre-existing product file no approved
    lane re-authors).
    """
    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch=target_branch, extra_base_files=extra_base_files)

    # -- planning artifacts (the approved status log is written after the lanes exist) --
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    _write_manifest(mission, wps)
    for wp_id in wps:
        _write_wp_file(mission, wp_id)
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap coord mission")

    # -- coordination branch at the bootstrap tip --------------------------
    _cut_coord_branch(mission)

    # -- one lane branch per WP, each carrying real approved code ----------
    events: list[dict[str, object]] = []
    for idx, wp_id in enumerate(wps):

        def _plant_code(repo: Path, wp_id: str = wp_id, idx: int = idx) -> None:
            code = repo / "src" / "pkg" / f"{wp_id.lower()}.py"
            code.parent.mkdir(parents=True, exist_ok=True)
            code.write_text(f"def {wp_id.lower()}() -> int:\n    return {idx}\n", encoding="utf-8")
            _git(repo, "add", str(code))
            _git(repo, "commit", "-qm", f"feat({slug}): {wp_id} approved code")

        lane_id = f"lane-{chr(ord('a') + idx)}"
        claim_head = mission.rev(mission.coord_branch)
        mission.lane_branches[wp_id] = _cut_lane_branch(mission, lane_id, [_plant_code])
        events.extend(_stamped_approve_events(mission, wp_id, claim_head=claim_head, approved_head=mission.rev(mission.lane_branches[wp_id])))

    # -- the approved status log, stamped with the real lane tips ----------
    _commit_status_events(mission, events, f"chore({slug}): approve coord mission WPs")

    # -- materialize the coordination worktree (production topology) -------
    return _finish_coord_mission(mission)


def _cancel_event(
    mission: CoordMission,
    wp_id: str,
    *,
    from_lane: str = "planned",
    policy_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """A single operator-authored canceled-with-provenance transition event.

    ``reason_source: "operator"`` is set explicitly (mirrors
    :data:`specify_cli.status_lanes.OPERATOR_REASON_SOURCE`) so
    ``has_operator_provenance`` / ``is_acceptable_ending`` recognize the
    cancellation as an acceptable mission ending — the #5018 mixed-lane
    fixture needs a WP that is genuinely canceled-with-provenance, not a
    synthetic/unauthorized cancellation.
    """
    mission._event_seq += 1
    event: dict[str, object] = {
        "actor": "operator",
        "at": _now_iso(),
        "event_id": f"01HXYZ5001{mission._event_seq:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission.slug,
        "force": False,
        "from_lane": from_lane,
        "reason": "operator: scope removed from mission",
        "reason_source": "operator",
        "review_ref": None,
        "to_lane": "canceled",
        "wp_id": wp_id,
    }
    if policy_metadata is not None:
        event["policy_metadata"] = policy_metadata
    return event


def build_coord_mission_mixed_lane(
    tmp_path: Path,
    *,
    survivor_wp: str = "WP01",
    canceled_wp: str = "WP02",
    target_branch: str = "main",
    mid8: str = "01M5018A",
) -> CoordMission:
    """A SINGLE write-scope lane holding an approved survivor + a canceled sibling (#5018).

    ``_collect_excluded`` (pre-fix) is LANE-granular: it adds ALL of a lane's tip
    commits to the excluded set the moment the lane lists ANY canceled WP — even
    the survivor's own legitimately-approved first-parent commits. This fixture is
    the minimal real-CLI shape that exercises exactly that granularity bug: ONE
    lane branch (``lane-a``) whose ``wp_ids`` list both *survivor_wp* (walked to
    ``approved``) and *canceled_wp* (canceled-with-provenance, via
    :func:`_cancel_event`, BEFORE it ever commits any code). The lane branch
    therefore carries exactly one commit, and that commit is 100% *survivor_wp*'s
    own authored work — so a correct, commit-granular exclusion must never
    exclude it, while the pre-fix lane-granular exclusion does.

    **Record correction (T005 / FR-008):** contrary to an earlier claim
    elsewhere in this file, a fixture built by this function DOES tolerate a
    post-build lane-branch ref mutation and a post-build coordination-worktree
    content mutation once :meth:`CoordinationWorkspace.resolve` has run — see
    ``build_coord_mission_shared_file``'s docstring and
    ``tests/terminus/test_fixture_mixed_lane_canceled.py`` for the pinned
    observed behaviour and the real "unmaterialized" trigger.
    """
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch=target_branch)

    # -- planning artifacts: ONE lane, TWO WPs, mixed status ----------------
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(survivor_wp, canceled_wp),
                write_scope=(f"src/pkg/{survivor_wp.lower()}.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture-mixed-lane",
    )
    write_lanes_json(mission.feature_dir, manifest)
    _write_wp_file(mission, survivor_wp)
    _write_wp_file(mission, canceled_wp)
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap mixed-lane coord mission")

    # -- coordination branch at the bootstrap tip --------------------------
    _cut_coord_branch(mission)

    # -- ONE shared lane branch, carrying ONLY the survivor's real commit ---
    def _plant_survivor_code(repo: Path) -> None:
        code = repo / "src" / "pkg" / f"{survivor_wp.lower()}.py"
        code.parent.mkdir(parents=True, exist_ok=True)
        code.write_text(f"def {survivor_wp.lower()}() -> int:\n    return 0\n", encoding="utf-8")
        _git(repo, "add", str(code))
        _git(repo, "commit", "-qm", f"feat({slug}): {survivor_wp} approved code")

    claim_head = mission.rev(mission.coord_branch)
    lane_branch = _cut_lane_branch(mission, "lane-a", [_plant_survivor_code])
    mission.lane_branches[survivor_wp] = lane_branch
    mission.lane_branches[canceled_wp] = lane_branch
    mission.canceled_wps.add(canceled_wp)

    # -- the status log, written once the lane commit exists: every event stamped
    # with the real lane tip. The canceled sibling never committed, so its
    # cancellation carries the same final tip.
    lane_tip = mission.rev(lane_branch)
    events = [
        *_stamped_approve_events(mission, survivor_wp, claim_head=claim_head, approved_head=lane_tip),
        _cancel_event(mission, canceled_wp, policy_metadata={"lane_head": lane_tip}),
    ]
    _commit_status_events(mission, events, f"chore({slug}): mixed-lane coord mission events")

    # -- materialize the coordination worktree (production topology) -------
    return _finish_coord_mission(mission)


def build_coord_mission_shared_file(
    tmp_path: Path,
    *,
    wps: Sequence[str],
    edits: Mapping[str, tuple[int, str]],
    target_branch: str = "main",
    mid8: str = "01M5051A",
    shared_path: str = "src/pkg/shared.py",
    initial_lines: Sequence[str] | None = None,
) -> CoordMission:
    """A squash-capable coord mission whose approved lanes ALL edit ONE shared
    file at DISJOINT hunks (terminus-merge-resolution-attribution / #5051-
    adjacent, WP01 T004).

    ``build_coord_mission`` gives every WP its OWN write-scope file, and
    ``build_coord_mission_mixed_lane`` supports only ``--strategy merge``. This
    is an ADDITIVE new builder, not a mutation of either: every lane branch
    commits its edit INLINE, during construction, and the coordination
    worktree is materialized exactly ONCE at the very end -- mirroring
    ``build_coord_mission_mixed_lane``'s "build it all, then resolve once"
    shape. WP02 (Seam B) reuses this builder.

    **Record correction (T005 / FR-008, grounded 2026-09-28):** an earlier
    revision of this docstring claimed ``build_coord_mission_mixed_lane``
    "cannot tolerate a lane-branch mutation after construction (it
    de-materializes the coordination worktree)". That claim does not hold:
    ``tests/terminus/test_fixture_mixed_lane_canceled.py::
    test_post_build_lane_update_ref_still_consolidates`` plants an EXTRA
    commit on the lane branch (via ``commit-tree`` + a CAS ``update-ref``)
    AFTER a builder has already resolved the coordination worktree, and the
    run still reaches the reconciliation verdict -- a post-build lane-ref or
    coordination-worktree-content mutation is fine. What actually triggers the
    "coordination branch ... is unmaterialized" abort is the coordination
    WORKTREE DIRECTORY being missing (``git worktree remove --force``), pinned
    by that same file's ``test_missing_coord_worktree_dir_is_the_unmaterialized_
    trigger``. The one genuine fixture hazard is staging the repository ROOT
    with ``git add .`` / ``-A`` AFTER a builder has resolved the coordination
    worktree, which would stage the coordination worktree's gitlink into a
    lane commit -- every builder here (and this one) only ever stages
    EXPLICIT paths, and only BEFORE resolving, so the hazard never triggers.

    ``edits`` maps each WP id to ``(line_index, replacement_line)`` -- the
    caller picks DISJOINT indices so the lanes' own diffs never overlap and the
    aggregate squash resolves cleanly via ``git``'s own 3-way merge machinery.
    """
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    lines = list(initial_lines or (f"line {i}\n" for i in range(1, 11)))
    mission = _init_fixture_repo(
        tmp_path,
        mid8=mid8,
        slug=slug,
        target_branch=target_branch,
        extra_base_files={shared_path: "".join(lines)},
    )
    shared_file = mission.repo / shared_path

    # -- planning artifacts: one lane per WP, ALL declaring shared_path --------
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    lanes = [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + idx)}",
            wp_ids=(wp_id,),
            write_scope=(shared_path,),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for idx, wp_id in enumerate(wps)
    ]
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=target_branch,
        lanes=lanes,
        computed_at=_now_iso(),
        computed_from="terminus-shared-file-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)
    for wp_id in wps:
        _write_wp_file(mission, wp_id)
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap shared-file coord mission")

    # -- coordination branch at the bootstrap tip ------------------------------
    _cut_coord_branch(mission)

    # -- one lane branch per WP, each committing its OWN disjoint-hunk edit ----
    events: list[dict[str, object]] = []
    for idx, wp_id in enumerate(wps):

        def _plant_edit(repo: Path, wp_id: str = wp_id) -> None:
            line_index, replacement = edits[wp_id]
            edited = shared_file.read_text(encoding="utf-8").splitlines(keepends=True)
            edited[line_index] = replacement
            shared_file.write_text("".join(edited), encoding="utf-8")
            _git(repo, "add", shared_path)
            _git(repo, "commit", "-qm", f"feat({slug}): {wp_id} edits {shared_path}@{line_index}")

        lane_id = f"lane-{chr(ord('a') + idx)}"
        claim_head = mission.rev(mission.coord_branch)
        mission.lane_branches[wp_id] = _cut_lane_branch(mission, lane_id, [_plant_edit])
        events.extend(_stamped_approve_events(mission, wp_id, claim_head=claim_head, approved_head=mission.rev(mission.lane_branches[wp_id])))

    # -- the approved status log, stamped with the real lane tips --------------
    _commit_status_events(mission, events, f"chore({slug}): approve shared-file coord mission WPs")

    # -- materialize the coordination worktree ONCE (production topology) -----
    return _finish_coord_mission(mission)


@dataclass(frozen=True)
class PlantedChange:
    """One file-level edit to plant as its own real commit.

    ``content is None`` means DELETE *path* (the path must already exist in
    the lane's tree at that point — e.g. seeded via ``extra_base_files``, or
    added by an earlier :class:`PlantedChange`). Any other ``content`` value
    is written verbatim and added/committed (create or overwrite).
    """

    path: str
    content: str | None


def _plant_change(repo: Path, change: PlantedChange, *, message: str) -> None:
    if change.content is None:
        _git(repo, "rm", "-q", change.path)
    else:
        target = repo / change.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.content, encoding="utf-8")
        _git(repo, "add", change.path)
    _git(repo, "commit", "-qm", message)


def _plant_lane_sync_merge(mission: CoordMission, lane_branch: str) -> None:
    """Merge a side commit into *lane_branch* (already checked out) so the
    lane spine carries a merge commit inside the canceled WP's session
    (``lane_sync_merge_in_canceled_session``).

    The side commit touches a harmless path under the mission's OWN planning
    dir (``kitty-specs/<slug>/notes/``) -- never ``status.events.jsonl``
    itself, whose exact content other assertions depend on. A planning-dir
    path is mission bookkeeping, which the squash content-attribution axis
    (``consolidation/reconciliation.py::_unattributable_content_squash``)
    already excludes, so this merge can never trip the very check the T003
    shapes exist to exercise — mirroring how a real "sync the lane with the
    coordination branch" workflow merge behaves (Edge Cases, spec.md).
    """
    repo = mission.repo
    side_branch = f"kitty/mission-{mission.slug}-lane-a-sync"
    _git(repo, "branch", side_branch, lane_branch)
    _git(repo, "checkout", "-q", side_branch)
    marker = mission.feature_dir / "notes" / "lane-sync-touch.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("lane sync marker\n", encoding="utf-8")
    _git(repo, "add", str(marker.relative_to(repo)))
    _git(repo, "commit", "-qm", f"chore({mission.slug}): lane-sync side commit")
    _git(repo, "checkout", "-q", lane_branch)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", side_branch)
    _git(repo, "branch", "-qD", side_branch)


def build_coord_mission_mixed_lane_canceled(
    tmp_path: Path,
    *,
    canceled_changes: Sequence[PlantedChange],
    survivor_after: Sequence[PlantedChange] = (),
    survivor_before: Sequence[PlantedChange] = (),
    survivor_reapproved: bool = False,
    lane_sync_merge_in_canceled_session: bool = False,
    stamp_attribution: bool = True,
    canceled_entered_implementation: bool = True,
    canceled_lifecycle: Literal["synthetic", "none"] = "synthetic",
    wp02_final: Literal["canceled", "approved"] = "canceled",
    mid8: str = "01M5046A",
    extra_base_files: Mapping[str, str] | None = None,
) -> CoordMission:
    """One shared lane holding a real committed-then-canceled WP02 beside an
    approved WP01 (FR-007, SC-005, T003) — the fixture that reproduces #5046's
    shapes in ONE builder call, with no post-build lane mutation, so the
    default squash strategy AND ``--strategy merge`` both reach the
    reconciliation gate.

    **Parameters, in terms of the spec's scenarios:**

    - ``canceled_changes`` — WP02's own real commits (US1, add/modify/delete
      via :class:`PlantedChange`), planted DURING WP02's ``in_progress``
      session, each its own explicit-path commit on the shared lane branch.
      This is the "canceled work cannot ship silently" core shape (US1
      Acceptance Scenarios 1–4): nothing on the target branch may end up
      carrying this content unless a survivor later re-authors it.
    - ``survivor_after`` — WP01 commits planted AFTER WP02's cancel stamp,
      inside a synthesized WP01 REWORK window (US2 "superseded canceled work
      does not block a good consolidation"): when every path
      ``canceled_changes`` touched is later rewritten (or restored) by
      ``survivor_after``, consolidation must exit 0 (US2 Acceptance Scenario
      1) — including the survivor-undone shapes SC-007 pins (an add the
      survivor later deletes; a change the survivor later reverts to base).
    - ``survivor_reapproved`` — WP01 goes back to ``in_progress`` and is approved
      again AFTER WP02's cancel stamp, with no commit of its own (the
      ``survivor_after`` rework window, empty). WP02's commits land after WP01's
      first approval, so without a new approval the approval-stamp bound refuses
      the lane (``LANE_MOVED_AFTER_APPROVAL``, #5720) before any canceled-content
      verdict. A test whose subject is that verdict sets this: review then approved
      the lane as it stands, WP02's content included.
    - ``survivor_before`` — WP01 commits planted BEFORE WP02's session opens,
      used to seed content that ``canceled_changes`` or ``survivor_after``
      then edits/deletes (US2 Acceptance Scenario 2/3's pre-state).
    - ``lane_sync_merge_in_canceled_session`` — plants a workflow-shaped merge
      commit (touching only a mission-bookkeeping path) INSIDE WP02's window,
      so the lane spine has a merge commit the gate must not mistake for
      WP02's own content (Edge Cases: "workflow merges on the lane ... never
      counted as the canceled WP's content").
    - ``stamp_attribution`` — when ``True`` (default), WP02's claim/in_progress
      and cancel events (and the ``survivor_after`` rework window's open/close
      events, when planted) carry ``policy_metadata.lane_head`` the way the
      real governed workflow records it (US5). ``False`` omits the key
      everywhere, producing US3's "no commit attribution exists" REFUSE shape.
    - ``canceled_entered_implementation`` — ``False`` cancels WP02 straight
      from ``planned`` with NO commits and NO claim/in_progress events (US2
      Acceptance Scenario 4 — "canceled before it entered implementation").
      ``canceled_changes`` is ignored in this mode.
    - ``canceled_lifecycle`` — ``"none"`` leaves WP02 at ``planned`` with NO
      events and NO commits at all (for WP06, which drives WP02 through the
      real governed CLI shells instead of hand-writing its events/commits —
      US5). ``"synthetic"`` (default) is this builder's own hand-written
      lifecycle.
    - ``wp02_final`` — ``"approved"`` walks WP02 to ``approved`` instead of
      canceling it (an all-approved-lane legacy twin used to prove a fixture
      change did not regress the ordinary case, distinct from the mixed-lane
      shape this builder exists for).
    - ``extra_base_files`` (``{repo_relative_path: content}``) — committed as
      part of the repo's INIT commit, BEFORE the coordination branch or
      ``lane-a`` are cut (mirrors :func:`build_coord_mission`'s parameter of
      the same name), so a path here is genuinely PRE-EXISTING at the mission
      base rather than authored on the lane. Needed for the US1 "canceled WP
      modifies/deletes a file that pre-dates the mission" shapes and for the
      SC-007 revert-to-mission-base residual, neither of which
      ``survivor_before`` (which authors content ON the lane, after the
      coordination branch is cut) can express (WP02 review cycle 1).

    **Stamping**: each ``lane_head`` is the REAL
    ``git rev-parse refs/heads/<lane branch>`` at the moment the event is
    appended — planting order is always event → commits → event, matching how
    the real workflow would observe the lane tip.

    **Event surface (FR-008 / T003)**: this builder writes ONE
    ``status.events.jsonl`` — into *mission*'s PRIMARY feature dir
    (``mission.repo / "kitty-specs" / mission.slug``), committed on
    ``target_branch`` as its own commit AFTER the coordination branch is cut
    and the lane's commits/events are known (so ``policy_metadata.lane_head``
    can name a real SHA), then ``coord_branch`` is fast-forwarded to that same
    commit before :func:`_finish_coord_mission` materializes the coordination
    worktree — so the coordination worktree's COPY carries byte-identical
    content. ``spec-kitty consolidate``'s reconciliation claim
    (``build_approved_wp_set(..., feature_dir=run.feature_dir, ...)``) reads
    whichever of the two the resolved status surface names (coord branch for
    coord topologies); WP06, which appends further events after this builder
    returns through the production shells, should therefore write to BOTH
    copies (or resolve the same coordination surface this builder used) to
    keep them in sync.

    **No post-build mutation (SC-005)**: every commit, merge, and event is
    planted BEFORE :func:`_finish_coord_mission` resolves the coordination
    worktree — the single call this function makes.
    """
    survivor_wp, canceled_wp = "WP01", "WP02"
    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"

    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main", extra_base_files=extra_base_files)

    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    planted_paths = {pc.path for pc in (*canceled_changes, *survivor_after, *survivor_before)}
    write_scope = tuple(sorted(planted_paths)) or (f"src/pkg/{survivor_wp.lower()}.py",)
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(survivor_wp, canceled_wp),
                write_scope=write_scope,
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture-mixed-lane-canceled",
    )
    write_lanes_json(mission.feature_dir, manifest)
    _write_wp_file(mission, survivor_wp)
    _write_wp_file(mission, canceled_wp)
    # No status.events.jsonl yet -- the lane doesn't exist, so no lane_head
    # SHA can be known. Committed separately below once the lane is built.
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap mixed-lane-canceled coord mission")

    _cut_coord_branch(mission)

    lane_branch = f"kitty/mission-{slug}-lane-a"
    _git(mission.repo, "branch", lane_branch, mission.coord_branch)
    _git(mission.repo, "checkout", "-q", lane_branch)
    mission.lane_branches[survivor_wp] = lane_branch
    mission.lane_branches[canceled_wp] = lane_branch

    def _lane_head() -> str:
        return git_rev(mission.repo, lane_branch)

    # WP01's own approve chain, stamped like a real governed workflow would
    # (contract C1) when stamp_attribution=True -- NOT the shared, never-
    # stamped `_approve_events` helper: WP01 shares this lane with canceled
    # WP02, and `wp_attribution.resolve_canceled_wp` refuses the WHOLE
    # resolution (never silently narrows it) when ANY sibling that entered
    # implementation has an unresolvable window (review cycle 1, issue 1) --
    # an unstamped WP01 would turn every mixed-lane FAIL/PASS scenario below
    # into a spurious REFUSE naming WP01 instead of WP02.
    #
    # ``survivor_before`` commits are WP01's OWN work, so they are planted
    # INSIDE WP01's implementation window (after ``claimed -> in_progress``,
    # before ``in_progress -> for_review``), each stamp read at the moment its
    # event is appended. Planting them after the whole approve chain (the
    # pre-FR-013 order) left them outside every WP window — a shape the
    # real governed workflow never produces and the FR-013 closed world
    # (ADR 2026-09-29-1) now correctly REFUSEs.
    def _stamped(frm: str, to: str) -> dict[str, object]:
        return _event(mission, survivor_wp, frm, to, policy_metadata={"lane_head": _lane_head()} if stamp_attribution else None)

    events: list[dict[str, object]] = [_stamped(frm, to) for frm, to in _APPROVE_CHAIN[:2]]
    for idx, change in enumerate(survivor_before):
        _plant_change(mission.repo, change, message=f"feat({slug}): {survivor_wp} {change.path} (before #{idx})")
    events.extend(_stamped(frm, to) for frm, to in _APPROVE_CHAIN[2:])

    if canceled_lifecycle == "none":
        pass  # WP02 stays `planned`; no events, no commits (WP06 drives it live).
    elif wp02_final == "approved":
        events.extend(_approve_events(mission, canceled_wp))
        for idx, change in enumerate(canceled_changes):
            _plant_change(mission.repo, change, message=f"feat({slug}): {canceled_wp} {change.path} (#{idx})")
    elif not canceled_entered_implementation:
        events.append(_cancel_event(mission, canceled_wp, from_lane="planned"))
    else:
        # Stamp BOTH the claim and the claimed->in_progress transitions (not
        # claimed->in_progress alone): the lane branch already exists by the
        # time WP02 (sharing lane-a with WP01) is claimed, so a real governed
        # workflow would stamp planned->claimed too (contract C1, "every
        # persisted transition"). wp_attribution._windows() records a
        # window's open_head from the FIRST transition into its class only
        # (same-class continuations never overwrite it) -- an unstamped
        # planned->claimed would therefore leave the whole implementation
        # window unattributable (NO_STAMP) even with stamp_attribution=True,
        # which is not the scenario this parameter is documented to produce.
        head_at_planned_claimed = _lane_head()
        events.append(
            _event(
                mission,
                canceled_wp,
                "planned",
                "claimed",
                policy_metadata={"lane_head": head_at_planned_claimed} if stamp_attribution else None,
            )
        )
        head_at_claim = _lane_head()
        events.append(
            _event(
                mission,
                canceled_wp,
                "claimed",
                "in_progress",
                policy_metadata={"lane_head": head_at_claim} if stamp_attribution else None,
            )
        )
        for idx, change in enumerate(canceled_changes):
            _plant_change(mission.repo, change, message=f"feat({slug}): {canceled_wp} {change.path} (#{idx})")
        if lane_sync_merge_in_canceled_session:
            _plant_lane_sync_merge(mission, lane_branch)
        head_after_last_commit = _lane_head()
        events.append(
            _cancel_event(
                mission,
                canceled_wp,
                from_lane="in_progress",
                policy_metadata={"lane_head": head_after_last_commit} if stamp_attribution else None,
            )
        )

    if survivor_after or survivor_reapproved:
        head_at_rework_open = _lane_head()
        events.append(
            _event(
                mission,
                survivor_wp,
                "approved",
                "in_progress",
                policy_metadata={"lane_head": head_at_rework_open} if stamp_attribution else None,
            )
        )
        for idx, change in enumerate(survivor_after):
            _plant_change(mission.repo, change, message=f"feat({slug}): {survivor_wp} {change.path} (after #{idx})")
        head_at_rework_close = _lane_head()
        # This closes the rework IMPLEMENTATION window (`_windows()` reads the
        # CLOSING event's own stamp, not the opening one) -- must carry the
        # SAME real stamp as the "approved" event below, or WP01's rework
        # window is unresolvable (NO_STAMP) and REFUSEs the whole mixed-lane
        # attribution, same rationale as the approve-chain fix above.
        events.append(
            _event(
                mission,
                survivor_wp,
                "in_progress",
                "for_review",
                policy_metadata={"lane_head": head_at_rework_close} if stamp_attribution else None,
            )
        )
        events.append(_event(mission, survivor_wp, "for_review", "in_review"))
        events.append(
            _event(
                mission,
                survivor_wp,
                "in_review",
                "approved",
                policy_metadata={"lane_head": head_at_rework_close} if stamp_attribution else None,
            )
        )

    if canceled_lifecycle != "none" and wp02_final == "canceled":
        mission.canceled_wps.add(canceled_wp)

    _git(mission.repo, "checkout", "-q", mission.target_branch)
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text(
        "".join(json.dumps(ev, sort_keys=True) + "\n" for ev in events),
        encoding="utf-8",
    )
    _git(mission.repo, "add", str((mission.feature_dir / _STATUS_EVENTS_FILENAME).relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", f"chore({slug}): mixed-lane-canceled events")
    # Fast-forward coord_branch to include the events commit; this does NOT
    # change lane_branch's own base (still the earlier bootstrap-artifacts
    # commit), so `commits_between(coord_branch, lane_branch)` still names
    # exactly the lane's own planted commits.
    _git(mission.repo, "branch", "-f", mission.coord_branch, mission.target_branch)

    return _finish_coord_mission(mission)


def fold_lanes_into_mission_branch(mission: CoordMission, wp_ids: Sequence[str]) -> None:
    """Fold every WP's lane branch into the MISSION branch itself -- never into
    each other's OWN branch (terminus-merge-resolution-attribution / #5051-
    adjacent, WP01 T004 real-CLI repro).

    ``spec-kitty merge``'s lane-based fold (``lanes/consolidation.py::
    consolidate_lane_into_mission``) processes lanes SEQUENTIALLY and refuses
    (``lanes/stale_check.py``) a later lane whose OWN branch overlaps a file
    the mission branch already advanced on, UNLESS that lane's branch first
    incorporates the mission branch -- which would fold the earlier lane's
    content INTO the later lane's own first-parent spine, contaminating
    ``ApprovedWpCommitSet.authored_blobs`` (a lane's "own" final blob would then
    already equal the combined result, masking the very false-FAIL this WP
    fixes). Folding directly into the MISSION branch instead -- a real, clean
    ``git merge`` this helper performs itself, never touching a lane branch --
    keeps each lane's own spine PURE while still advancing the branch
    ``_phase_merge_lanes``'s ancestry check (``lane_integrated_by_tree_or_
    ancestry``) reads, so a SUBSEQUENT ``spec-kitty merge --resume`` finds
    every lane already integrated and skips re-folding (no stale check ever
    runs). Call this AFTER a real, failed first ``spec-kitty merge`` attempt
    (whose stale-lane abort persists ``pre_mutation_coord_sha`` -- the
    coordination tip AT TRANSACTION START -- to
    ``.kittify/merge-state.json``), so the resumed run's reconciliation claim
    is anchored to that persisted base rather than re-deriving a live
    checkpoint that would, by resume time, already reflect this fold.

    Operates inside the materialized COORDINATION WORKTREE
    (``.worktrees/<slug>-<mid8>-coord``), never the main repo checkout: the
    coordination branch is checked out THERE (production topology,
    :func:`~specify_cli.coordination.workspace.CoordinationWorkspace.resolve`),
    and git refuses a second checkout of a branch already checked out
    elsewhere.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_worktree = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    for wp_id in wp_ids:
        _git(coord_worktree, "merge", "-q", "--no-edit", mission.lane_branches[wp_id])


def restamp_approvals_at_lane_tips(mission: CoordMission) -> None:
    """Record that review approved every lane branch's CURRENT tip (#5668), in every copy of the log.

    The truthful stamp for a test that moves a lane AFTER its builder approved it, when the
    test's subject is the content axes that run after the approved-bound check (a canceled
    commit riding a carrier lane, a removed deletion): the planted lane state is then "what
    review approved". A test whose subject IS "content arrived after approval" does not call
    this. Rewrites each ``approved`` event of a work package that has a lane branch and
    commits the log where it lives: the coordination worktree on a coordination mission (the
    target branch does not move), the root checkout otherwise.
    """
    tips = {wp_id: git_rev(mission.repo, branch) for wp_id, branch in mission.lane_branches.items()}
    logs = [log for log in mission.repo.rglob(_STATUS_EVENTS_FILENAME) if ".git" not in log.parts]
    # A coordination mission reads its status from the coordination worktree: stamp that copy
    # and leave the root checkout's (and so the target branch) untouched.
    coord_logs = [log for log in logs if ".worktrees" in log.relative_to(mission.repo).parts]
    for log in coord_logs or logs:
        original = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        rewritten: list[dict[str, object]] = []
        for event in original:
            if event.get("to_lane") == "approved" and event.get("wp_id") in tips:
                event = {**event, "policy_metadata": {**(event.get("policy_metadata") or {}), "lane_head": tips[str(event["wp_id"])]}}
            rewritten.append(event)
        if rewritten == original:
            continue
        log.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in rewritten), encoding="utf-8")
        _git(log.parent, "add", str(log))
        _git(log.parent, "commit", "-qm", "test: record that review approved the lane tips")


def plant_canceled_commit(
    mission: CoordMission,
    *,
    canceled_wp: str,
    carrier_wp: str,
    path: str | None = None,
) -> tuple[str, str, str]:
    """Plant a canceled/removed WP's commit so it rides a dependent lane's history.

    Mirrors the #4977 / #4945 mechanism: a WP whose code was CANCELED/removed still
    has a real commit that a *dependent* (carrier) lane merged in, so the removed
    diff travels into the carrier's history and — absent an excluded-commit gate —
    into the target at merge. The planted commit is NOT in ``lanes.json`` (it is
    removed work, not an approved lane), so the mission stays merge-ready and the
    "derived canceled set" the gate would compute from status is empty — exactly
    the non-vacuous case (contract postcondition 3).

    ``path`` overrides the default planted path (``src/pkg/<wp>_removed.py``) —
    used by the #5001 bookkeeping-over-exclusion repro to plant the removed
    content at a path that is itself NAMED like a bookkeeping file (e.g.
    ``src/config/meta.json``) while remaining ordinary product source, never
    mission planning/toolchain output.

    Returns ``(canceled_sha, canceled_patch_id, planted_path)`` where
    ``planted_path`` is the repo-relative path of the removed file
    (``src/pkg/<wp>_removed.py`` by default). The SHA/patch-id observables serve
    the ``--strategy merge`` repros (a distinct, patch-id-identifiable node
    survives a merge consolidation); ``planted_path`` serves the **default-
    squash** repros, whose only squash-sound observable is tree/blob presence via
    :func:`blob_present_at` (squash destroys the SHA/patch-id identity #5013).
    """
    repo = mission.repo
    slug = mission.slug
    cancel_branch = f"kitty/mission-{slug}-lane-canceled"

    # A real commit that must NEVER reach the target.
    _git(repo, "branch", cancel_branch, mission.coord_branch)
    _git(repo, "checkout", "-q", cancel_branch)
    planted_path = path if path is not None else f"src/pkg/{canceled_wp.lower()}_removed.py"
    canceled_code = repo / planted_path
    canceled_code.parent.mkdir(parents=True, exist_ok=True)
    canceled_code.write_text(
        f'# CANCELED {canceled_wp} -- must not ship\ndef {canceled_wp.lower()}_removed() -> str:\n    return "leaked"\n',
        encoding="utf-8",
    )
    _git(repo, "add", str(canceled_code))
    _git(repo, "commit", "-qm", f"feat({slug}): {canceled_wp} code (later CANCELED)")
    canceled_sha = git_rev(repo, cancel_branch)
    canceled_pid = patch_id(repo, canceled_sha)

    # Carrier lane merges the canceled commit in -> it now rides carrier history.
    carrier_branch = mission.lane_branches[carrier_wp]
    _git(repo, "checkout", "-q", carrier_branch)
    _git(repo, "merge", "-q", "--no-edit", cancel_branch)
    _git(repo, "checkout", "-q", mission.target_branch)
    _git(repo, "branch", "-qD", cancel_branch)

    mission.canceled_wps.add(canceled_wp)
    restamp_approvals_at_lane_tips(mission)
    return canceled_sha, canceled_pid, planted_path


def plant_canceled_deletion(
    mission: CoordMission,
    *,
    canceled_wp: str,
    carrier_wp: str,
    path: str,
) -> tuple[str, str]:
    """Plant a canceled/removed WP's DELETION of a pre-existing file (#5022).

    Mirrors :func:`plant_canceled_commit`'s carrier-merge mechanism, but the
    canceled commit DELETES *path* (which must already exist on
    ``mission.coord_branch`` — see ``build_coord_mission``'s ``extra_base_files``)
    instead of adding new content. This is the #5022 data-loss shape: a canceled
    WP's deletion of a pre-existing product file that no approved lane re-authors,
    riding a carrier lane's history into the target under the DEFAULT squash.

    Returns ``(canceled_sha, canceled_patch_id)``.
    """
    repo = mission.repo
    slug = mission.slug
    cancel_branch = f"kitty/mission-{slug}-lane-canceled-del"

    _git(repo, "branch", cancel_branch, mission.coord_branch)
    _git(repo, "checkout", "-q", cancel_branch)
    _git(repo, "rm", "-q", path)
    _git(repo, "commit", "-qm", f"fix({slug}): {canceled_wp} removes {path} (later CANCELED)")
    canceled_sha = git_rev(repo, cancel_branch)
    canceled_pid = patch_id(repo, canceled_sha)

    # Carrier lane merges the canceled deletion in -> it now rides carrier history.
    carrier_branch = mission.lane_branches[carrier_wp]
    _git(repo, "checkout", "-q", carrier_branch)
    _git(repo, "merge", "-q", "--no-edit", cancel_branch)
    _git(repo, "checkout", "-q", mission.target_branch)
    _git(repo, "branch", "-qD", cancel_branch)

    mission.canceled_wps.add(canceled_wp)
    restamp_approvals_at_lane_tips(mission)
    return canceled_sha, canceled_pid


# ---------------------------------------------------------------------------
# Real terminus command driver (subprocess -- nothing mocked)
# ---------------------------------------------------------------------------


_HOME_TEMPLATE: Path | None = None


def _cli_env(home: Path) -> dict[str, str]:
    process_env = os.environ.copy()
    process_env["PYTHONPATH"] = str(_SRC)
    process_env["HOME"] = str(home)
    process_env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    process_env.pop("VIRTUAL_ENV", None)
    # An operator's exported origin-check mode must not change a CLI run; a test that needs one overlays it with ``env=``.
    process_env.pop("SPEC_KITTY_ORIGIN_CHECK", None)
    return process_env


def _bootstrapped_home_template() -> Path:
    """A HOME the CLI has already bootstrapped, built once per test process.

    The first CLI command in an empty HOME installs the global runtime, agent
    commands and skills, which costs about 25s; a copy of an already
    bootstrapped HOME costs well under a second and is still one HOME per
    mission, so nothing is shared between tests. ``consolidate --help`` from
    outside any repository runs exactly that bootstrap and nothing else.
    """
    global _HOME_TEMPLATE
    if _HOME_TEMPLATE is None:
        template = Path(tempfile.mkdtemp(prefix="terminus-home-"))
        atexit.register(shutil.rmtree, template, ignore_errors=True)
        subprocess.run(
            [sys.executable, "-m", "specify_cli", "consolidate", "--help"],
            cwd=str(template),
            env=_cli_env(template),
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        _HOME_TEMPLATE = template
    return _HOME_TEMPLATE


def run_terminus(
    mission: CoordMission,
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the REAL ``spec-kitty`` CLI in *mission*'s repo (no mocking).

    Runs ``python -m specify_cli <args>`` against this worktree's ``src`` with an
    isolated ``HOME`` so the whole terminus stack -- including
    ``git/ref_advance.py``'s ``update-ref`` argv -- executes for real.

    ``env`` optionally overlays extra variables onto the environment this
    helper builds by default (WP06) -- it is applied LAST, so a caller can
    override any of the defaults above (including ``HOME``) as well as add
    new ones.
    """
    process_env = _cli_env(mission.home)
    if env is not None:
        process_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=str(mission.repo),
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def coord_mission(tmp_path: Path) -> CoordMission:
    """A single-WP, approved, merge-ready coord mission."""
    return build_coord_mission(tmp_path, wps=("WP01",))


@pytest.fixture
def terminus_env() -> dict[str, object]:
    """Expose the harness helpers to tests that prefer explicit imports-by-fixture."""
    return {
        "build_coord_mission": build_coord_mission,
        "plant_canceled_commit": plant_canceled_commit,
        "run_terminus": run_terminus,
    }


def build_coord_mission_mixed_lane_with_dependency(
    tmp_path: Path,
    *,
    canceled_leaks: bool,
    mid8: str = "01M5046D",
) -> CoordMission:
    """A mixed lane (``lane-b``: approved WP01 + canceled WP02) that DEPENDS on
    another lane (``lane-a``: approved WP03) — the governed allocator shape
    (``lanes/worktree_allocator.py`` merges a dependency lane into the dependent
    lane WITHOUT ``--no-ff``, so ``lane-a``'s WP03 commit fast-forwards onto
    ``lane-b``'s first-parent history BEFORE ``lane-b``'s first claim stamp).

    Every WP commit lands inside its own stamped window. ``canceled_leaks``
    plants one WP02 file inside WP02's window (unsuperseded → FAIL); otherwise
    WP02 is canceled without commits (→ exit 0).
    """
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main")
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)

    def _lane(lane_id: str, wp_ids: tuple[str, ...], deps: tuple[str, ...]) -> ExecutionLane:
        return ExecutionLane(
            lane_id=lane_id,
            wp_ids=wp_ids,
            write_scope=("src/pkg",),
            predicted_surfaces=("code",),
            depends_on_lanes=deps,
            parallel_group=0,
        )

    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[_lane("lane-a", ("WP03",), ()), _lane("lane-b", ("WP01", "WP02"), ("lane-a",))],
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture-dependency-lane",
    )
    write_lanes_json(mission.feature_dir, manifest)
    for wp in ("WP01", "WP02", "WP03"):
        _write_wp_file(mission, wp)
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap dependency-lane coord mission")
    _cut_coord_branch(mission)

    repo = mission.repo
    lane_a = f"kitty/mission-{slug}-lane-a"
    lane_b = f"kitty/mission-{slug}-lane-b"
    events: list[dict[str, object]] = []

    def _stamped(wp: str, frm: str, to: str, branch: str) -> dict[str, object]:
        return _event(mission, wp, frm, to, policy_metadata={"lane_head": git_rev(repo, branch)})

    def _approved_session(wp: str, branch: str, path: str) -> None:
        events.extend(_stamped(wp, frm, to, branch) for frm, to in _APPROVE_CHAIN[:2])
        _plant_change(repo, PlantedChange(path, f"{wp} = 'approved work'\n"), message=f"feat({slug}): {wp} work")
        events.extend(_stamped(wp, frm, to, branch) for frm, to in _APPROVE_CHAIN[2:])

    # lane-a: WP03's approved work.
    _git(repo, "branch", lane_a, mission.coord_branch)
    _git(repo, "checkout", "-q", lane_a)
    _approved_session("WP03", lane_a, "src/pkg/wp03.py")

    # lane-b: cut at the coord base, then the allocator's dependency merge
    # (fast-forward — no --no-ff) BEFORE any lane-b claim.
    _git(repo, "branch", lane_b, mission.coord_branch)
    _git(repo, "checkout", "-q", lane_b)
    _git(repo, "merge", "--no-edit", "-m", "Merge dependency lane lane-a into lane-b", lane_a)
    _approved_session("WP01", lane_b, "src/pkg/wp01.py")
    events.append(_stamped("WP02", "planned", "claimed", lane_b))
    events.append(_stamped("WP02", "claimed", "in_progress", lane_b))
    if canceled_leaks:
        _plant_change(repo, PlantedChange("src/pkg/wp02_new.py", "WP02 = 'canceled work'\n"), message=f"feat({slug}): WP02 work")
    events.append(_cancel_event(mission, "WP02", from_lane="in_progress", policy_metadata={"lane_head": git_rev(repo, lane_b)}))

    mission.lane_branches.update({"WP03": lane_a, "WP01": lane_b, "WP02": lane_b})
    mission.canceled_wps.add("WP02")
    _git(repo, "checkout", "-q", mission.target_branch)
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("".join(json.dumps(ev, sort_keys=True) + "\n" for ev in events), encoding="utf-8")
    _git(repo, "add", str((mission.feature_dir / _STATUS_EVENTS_FILENAME).relative_to(repo)))
    _git(repo, "commit", "-qm", f"chore({slug}): dependency-lane events")
    _git(repo, "branch", "-f", mission.coord_branch, mission.target_branch)
    return _finish_coord_mission(mission)
