"""Scope guards for the mission-scoped ``commit_to_target`` bypass (WP08 cycle 5).

Two seams that decide WHICH writes may ride the bypass onto protected ``main``:

* ``git.commit_helpers._single_mission_slug`` -- a commit only counts as one
  mission's own write when EVERY path is under a single ``kitty-specs/<slug>/``;
  a mixed ``src/`` + mission commit, two missions, or an unflagged mission must
  stay refused (real ``preflight_commit`` on a real repo, hatch env unset).
* ``coordination.commit_router._mission_scoped`` -- callers that pass an UNSCOPED
  ``ProtectionPolicy.resolve(...)`` to ``commit_for_mission`` (setup-plan,
  record-analysis, spec-commit, acceptance, write_seam, orchestrator) depend on
  the router folding the mission's ``commit_to_target`` in.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind, MissionTopology
from specify_cli.coordination import commit_router
from specify_cli.git.commit_helpers import ProtectedBranchRefused, _single_mission_slug, preflight_commit
from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.git_repo]

CTT = "ctt-mission"
OTHER = "plain-mission"
OTHER_CTT = "ctt-mission-two"


@pytest.fixture(autouse=True)
def _hatch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    for slug, flag in ((CTT, True), (OTHER_CTT, True), (OTHER, None)):
        mission_dir = repo / "kitty-specs" / slug
        mission_dir.mkdir(parents=True)
        meta: dict[str, object] = {"mission_slug": slug, "target_branch": "main", "topology": "single_branch"}
        if flag is not None:
            meta["commit_to_target"] = flag
        (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _preflight(repo: Path, *paths: str) -> list[str]:
    normalized: list[str] = preflight_commit(
        repo_root=repo,
        worktree_root=repo,
        target=CommitTarget(ref="main"),
        message="test",
        paths=tuple(repo / p for p in paths),
    )
    return normalized


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["kitty-specs/m/spec.md", "kitty-specs/m/tasks.md"], "m"),
        (["kitty-specs/m/spec.md", "src/x.py"], None),
        (["src/x.py"], None),
        (["kitty-specs/a/spec.md", "kitty-specs/b/spec.md"], None),
        (["kitty-specs/m"], None),
        ([], None),
    ],
)
def test_single_mission_slug(paths: list[str], expected: str | None) -> None:
    assert _single_mission_slug(paths) == expected


def test_preflight_ctt_only_paths_ride_the_bypass(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    assert _preflight(repo, f"kitty-specs/{CTT}/spec.md") == [f"kitty-specs/{CTT}/spec.md"]


def test_preflight_mixed_code_and_ctt_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(ProtectedBranchRefused):
        _preflight(repo, f"kitty-specs/{CTT}/spec.md", "src/x.py")


def test_preflight_two_missions_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(ProtectedBranchRefused):
        _preflight(repo, f"kitty-specs/{CTT}/spec.md", f"kitty-specs/{OTHER_CTT}/spec.md")


def test_preflight_unflagged_mission_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(ProtectedBranchRefused):
        _preflight(repo, f"kitty-specs/{OTHER}/spec.md")


def test_preflight_ambiguous_selector_yields_no_bypass_instead_of_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A6: an ambiguous/unresolvable selector must fail closed (no bypass, so
    the protected-branch refusal fires) rather than raising
    ``MissionSelectorAmbiguous`` out of ``preflight_commit``."""
    from specify_cli.git import protection_policy
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    def _ambiguous(_root: Path, handle: str) -> tuple[dict[str, object], bool]:
        raise MissionSelectorAmbiguous(handle=handle, candidates=["a-01AAAAAA", "a-01BBBBBB"])

    # The mission-meta read goes through the sanctioned primary-meta primitive,
    # whose handle canonicalization is where an ambiguous selector surfaces.
    monkeypatch.setattr("specify_cli.missions._read_path_resolver.read_primary_meta", _ambiguous)
    repo = _repo(tmp_path)

    with pytest.raises(ProtectedBranchRefused):
        _preflight(repo, f"kitty-specs/{CTT}/spec.md")
    assert protection_policy.ProtectionPolicy.resolve_for_mission(repo, CTT).is_protected("main") is True


@pytest.fixture
def _router_on_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commit_router, "resolve_placement_only", lambda _r, _s, *, kind, **_kw: CommitTarget(ref="main"))
    monkeypatch.setattr(commit_router, "resolve_topology", lambda _r, _s: MissionTopology.SINGLE_BRANCH)
    monkeypatch.setattr(commit_router, "_resolve_mission_target_branch", lambda _r, _s: "main")


def _commit_spec(repo: Path, slug: str) -> commit_router.CommitRouterResult:
    spec = repo / "kitty-specs" / slug / "spec.md"
    spec.write_text("# spec changed\n", encoding="utf-8")
    # An UNSCOPED policy, exactly as setup-plan / record-analysis / spec-commit pass it.
    return commit_router.commit_for_mission(
        repo,
        slug,
        (spec,),
        "chore: spec",
        ProtectionPolicy.resolve(repo),
        kind=MissionArtifactKind.SPEC,
    )


@pytest.mark.usefixtures("_router_on_main")
def test_router_folds_commit_to_target_for_unscoped_policy(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")

    result = _commit_spec(repo, CTT)

    assert result.status == commit_router._STATUS_COMMITTED, result
    assert _git(repo, "rev-parse", "HEAD") != before
    assert _git(repo, "branch", "--show-current") == "main"


@pytest.mark.usefixtures("_router_on_main")
def test_router_still_refuses_unflagged_mission_on_protected_main(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _git(repo, "rev-parse", "HEAD")

    result = _commit_spec(repo, OTHER)

    assert result.status == commit_router._STATUS_NO_OP_WRONG_SURFACE, result
    assert _git(repo, "rev-parse", "HEAD") == before
