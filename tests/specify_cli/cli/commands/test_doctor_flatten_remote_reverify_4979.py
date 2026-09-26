"""Repro #4979 (FR-004) — doctor flatten remote re-verification guard.

``doctor coordination --fix`` must re-verify a ``COORDINATION_WORKTREE_NEVER_CREATED``
finding's ``coordination_branch`` against the remote (via the WP01 shared
``remote_branch_lookup`` primitive, C-001) BEFORE calling
``flatten_coordination_metadata``. This is belt-and-suspenders behind WP01's
source fix at the CHECK site (``_coord_branch_exists``): WP02 guards the
destructive FIX site independently, so a remote-present branch can never be
flattened even if a ``NEVER_CREATED`` finding is somehow reached (a future
probe regression, a race).

RED-first (T007): a mission whose declared ``coordination_branch`` is
genuinely still pushed to a real bare ``origin`` remote must NOT be flattened
by ``_fix_never_created_branches`` / ``_apply_never_created_fix``. Pre-fix,
neither function consults the remote at all, so the flatten proceeds
unconditionally regardless of remote state — RED. Real git plumbing (a
genuine bare origin + a genuine push), not a mocked subprocess boundary,
mirrors the ATDD real-vector convention used by the sibling probe repro
(``tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands import _coordination_doctor as cd

pytestmark = [pytest.mark.unit, pytest.mark.git_repo, pytest.mark.regression]

MISSION_SLUG = "remote-guard-4979-01J7AA00"
MISSION_ID = "01J7AA00ABCDEFGHJKMNPQRSTV"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _seed_repo_with_origin(tmp_path: Path, name: str = "repo") -> tuple[Path, Path]:
    """A local checkout with a real bare ``origin`` remote configured."""
    origin = tmp_path / f"{name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")

    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@x.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")
    return repo, origin


def _repo_with_coord_branch_pushed_to_origin(tmp_path: Path) -> Path:
    """A checkout whose coordination branch is genuinely pushed to origin,
    then stripped locally (no local head, no already-fetched
    ``refs/remotes/`` ref) — mirrors the remote-only checkout #4979 is about,
    so the only way to discover the branch is a fresh ``git ls-remote``.
    """
    repo, _origin = _seed_repo_with_origin(tmp_path)
    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "push", "-q", "origin", COORD_BRANCH)
    _git(repo, "branch", "-D", COORD_BRANCH)
    _git(repo, "update-ref", "-d", f"refs/remotes/origin/{COORD_BRANCH}")
    return repo


def _write_meta(repo: Path, slug: str, mission_id: str, coord_branch: str) -> Path:
    spec_dir = repo / "kitty-specs" / slug
    spec_dir.mkdir(parents=True)
    meta_path = spec_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": mission_id,
                "coordination_branch": coord_branch,
                "topology": "coord",
            }
        )
    )
    return meta_path


def _never_created_finding(meta_path: Path) -> cd.DoctorFinding:
    return cd.DoctorFinding(
        severity="warning",
        message="branch absent (per stale local check)",
        error_code="COORDINATION_WORKTREE_NEVER_CREATED",
        extra={"meta_path": str(meta_path)},
    )


def test_remote_present_branch_is_not_flattened(tmp_path: Path) -> None:
    """FR-004: a NEVER_CREATED finding whose branch is genuinely still pushed
    to origin must NOT be flattened — ``coordination_branch`` survives the fix.

    RED on unmodified ``_fix_never_created_branches`` (it flattens
    unconditionally, never consulting the remote). GREEN once T008 wires the
    WP01 ``remote_branch_lookup`` re-verify guard in ahead of
    ``flatten_coordination_metadata``.
    """
    repo = _repo_with_coord_branch_pushed_to_origin(tmp_path)
    meta_path = _write_meta(repo, MISSION_SLUG, MISSION_ID, COORD_BRANCH)
    finding = _never_created_finding(meta_path)

    fixed = cd._fix_never_created_branches([finding], repo)

    assert fixed == [], "a coordination branch still present on a remote must be skipped, never flattened — the fixed-slugs list must stay empty"
    written = json.loads(meta_path.read_text())
    assert written.get("coordination_branch") == COORD_BRANCH, "meta.json must be left completely unchanged when the remote still has the branch"
    assert written.get("topology") == "coord"


def test_apply_never_created_fix_end_to_end_leaves_meta_unchanged(tmp_path: Path) -> None:
    """Same guard exercised through the real ``--fix`` dispatch entry point
    (``_apply_never_created_fix``), not just the lower-level helper.
    """
    repo = _repo_with_coord_branch_pushed_to_origin(tmp_path)
    meta_path = _write_meta(repo, MISSION_SLUG, MISSION_ID, COORD_BRANCH)
    finding = _never_created_finding(meta_path)

    cd._apply_never_created_fix([finding], repo)

    written = json.loads(meta_path.read_text())
    assert written.get("coordination_branch") == COORD_BRANCH
    assert written.get("topology") == "coord"


def test_genuinely_absent_branch_still_flattens(tmp_path: Path) -> None:
    """FR-002 preserved: a branch gone from every remote (CLEAN_MISS) still
    flattens exactly as it did before the guard was added.
    """
    repo, _origin = _seed_repo_with_origin(tmp_path, name="repo-clean-miss")
    absent_branch = "kitty/mission-genuinely-gone-00000000"
    meta_path = _write_meta(repo, "genuinely-gone-01J7BB00", "01J7BB00ABCDEFGHJKMNPQRSTV", absent_branch)
    finding = _never_created_finding(meta_path)

    fixed = cd._fix_never_created_branches([finding], repo)

    assert fixed == ["genuinely-gone-01J7BB00"]
    written = json.loads(meta_path.read_text())
    assert "coordination_branch" not in written


def test_no_remote_configured_still_flattens(tmp_path: Path) -> None:
    """A repo with zero configured remotes (NO_REMOTE) retains local-only
    authority and still flattens — matches every pre-existing unit test for
    ``_fix_never_created_branches`` that never configures a remote at all.
    """
    repo = tmp_path / "repo-no-remote"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@x.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")

    meta_path = _write_meta(
        repo,
        "no-remote-01J7CC00",
        "01J7CC00ABCDEFGHJKMNPQRSTV",
        "kitty/mission-no-remote-never-created",
    )
    finding = _never_created_finding(meta_path)

    fixed = cd._fix_never_created_branches([finding], repo)

    assert fixed == ["no-remote-01J7CC00"]
    written = json.loads(meta_path.read_text())
    assert "coordination_branch" not in written


def test_inconclusive_remote_error_is_fail_closed_not_flattened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002 (fail-closed): an inconclusive network condition (RemoteLookup.ERROR
    — an unreachable / timing-out / auth-prompting remote) must NEVER be read as
    "safe to destroy". The flatten is skipped and meta.json is left unchanged,
    exactly like the HIT case. Pins the most safety-critical branch of
    ``_coord_branch_remote_skip_reason``.
    """
    from specify_cli.git import remote_probes as rp

    repo, _origin = _seed_repo_with_origin(tmp_path, name="repo-error")
    meta_path = _write_meta(repo, "error-01J7EE00", "01J7EE00ABCDEFGHJKMNPQRSTV", COORD_BRANCH)
    finding = _never_created_finding(meta_path)

    # Force the shared primitive to report an inconclusive/erroring remote.
    monkeypatch.setattr(rp, "remote_branch_lookup", lambda *_a, **_k: rp.RemoteLookup.ERROR)

    fixed = cd._fix_never_created_branches([finding], repo)

    assert fixed == [], "an inconclusive remote (ERROR) must fail closed — never flatten"
    written = json.loads(meta_path.read_text())
    assert written.get("coordination_branch") == COORD_BRANCH, "meta.json must be untouched on an inconclusive remote"
    assert written.get("topology") == "coord"


def test_omitted_repo_root_preserves_legacy_unconditional_flatten(tmp_path: Path) -> None:
    """Backward compatibility: callers that omit ``repo_root`` (every
    pre-existing unit test in ``test_coordination_doctor.py`` /
    ``test_doctor_coordination.py``) keep the original unconditional-flatten
    behaviour — the remote re-verify guard only activates when a caller opts
    in by passing ``repo_root``.
    """
    mission_dir = tmp_path / "kitty-specs" / "legacy-caller-01J7DD00"
    mission_dir.mkdir(parents=True)
    meta_path = mission_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "mission_slug": "legacy-caller-01J7DD00",
                "coordination_branch": "kitty/mission-legacy-caller-01J7DD00",
            }
        )
    )
    finding = _never_created_finding(meta_path)

    fixed = cd._fix_never_created_branches([finding])

    assert fixed == ["legacy-caller-01J7DD00"]
    written = json.loads(meta_path.read_text())
    assert "coordination_branch" not in written
