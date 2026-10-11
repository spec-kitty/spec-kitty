"""WP05 — single write-surface authority for planning commits (FR-007, #2063, SC-004).

Covers:

* **T025** — ``safe_commit_cmd`` separates its two responsibilities (NFR-002): the
  generic operator-file path keeps ``--to-branch``/HEAD inference; the
  mission-aware planning path (a ``kitty-specs/<slug>/`` artifact for a resolvable
  mission) resolves its destination via the WP03 seam, never from
  ``get_current_branch``.
* **T026 (re-pinned, WP02 FR-003 / C-005)** — under the converged write path a
  coord-topology **planning** commit (``spec.md``, a ``SPEC`` kind) lands on the
  **primary** ``target_branch`` (NOT the coordination worktree), and the committed
  ``spec.md`` is **read back** from the same **primary** surface via the
  next-command read leg (the #2063 round-trip, now coherent on the *primary*
  seam per WP03 T012's "preserved and corrected" note). The paired coord-side
  assertion proves the **bifurcation** still holds: a ``STATUS_STATE`` (C-001
  coordination-partition) commit on the SAME mission still routes to the
  coordination branch — so the test fails red if planning ever regressed back to
  coord, *or* if status ever leaked onto primary.

These tests exercise the REAL kind-aware seam (``resolve_placement_only`` /
``candidate_feature_dir_for_mission``) on a real protected-primary repo — a test
that only mocks the router or asserts the WRITE leg is insufficient (renata /
SC-004).

WP02 history (delete-the-assertion-not-the-test): this class previously asserted
the *removed* planning→coord contract (``placement_ref == _COORD_BRANCH``, read
back from ``.worktrees/<slug>-coord/``). FR-003 removes that path and C-005
forbids preserving it as a fallback (FR-002: "the coordination worktree is never
the authoring/read surface for planning artifacts"). The round-trip structure and
the anti-fakeable negative proof are KEPT and re-targeted onto the primary seam,
not deleted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.coordination.commit_router import commit_for_mission
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    build_protected_target_repo,
    protected_target_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Realistic identity (NFR-005 / test-data policy): full ULID, derived mid8, and a
# production-shaped slug whose tail IS the mid8 (the mission-identity naming the
# read-path resolver's mid8_from_slug heuristic recovers).
_FULL_ULID = "01KVPR00WP05AUTH0000000001"
_MID8 = _FULL_ULID[:8]
_SLUG = f"write-surface-authority-{_MID8}"
# The coord branch reconstructs VERBATIM and is idempotent on an already-embedded
# ``-<mid8>`` tail (coord_reconstruct_branch), so the mid8 appears ONCE.
_COORD_BRANCH = f"kitty/mission-{_SLUG}"
_SPEC_BODY = "# Spec\n\nFR-003: the planning commit lands on the PRIMARY target branch.\n"
# Coordination-partition artifact (C-001 / STATUS_STATE) — proves the bifurcation:
# planning moves to primary while status stays on the coordination branch.
_STATUS_BODY = '{"wp_id":"WP01","to_lane":"planned"}\n'


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _seed_coord_mission(repo_root: Path) -> tuple[Path, Path, Path]:
    """Seed a coord-topology mission (meta + spec.md + status) + the coordination branch.

    Returns the feature dir, the planning ``spec.md`` path, and the coordination
    ``status.events.jsonl`` path (the C-001 partition artifact the bifurcation
    assertion commits with a ``STATUS_STATE`` kind).
    """
    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": _FULL_ULID,
        "mission_slug": _SLUG,
        "mid8": _MID8,
        "coordination_branch": _COORD_BRANCH,
        "mission_type": "software-dev",
        "friendly_name": "Write Surface Authority E2E",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(_SPEC_BODY, encoding="utf-8")
    status_path = feature_dir / "status.events.jsonl"
    status_path.write_text(_STATUS_BODY, encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "chore: seed coord-topology mission")
    _git(repo_root, "branch", _COORD_BRANCH)
    return feature_dir, spec_path, status_path


# ---------------------------------------------------------------------------
# T026 (re-pinned) — coord-topology PLANNING commit WRITES to + READS BACK from
# the PRIMARY surface, while a coordination-partition commit stays on coord.
# ---------------------------------------------------------------------------


class TestCoordTopologyPlanningCommitRoundTrip:
    """#2063 / SC-004 / FR-003: planning round-trips on PRIMARY; status stays coord.

    Re-pinned for write-surface-coherence WP02 (FR-003 / C-005). The pre-WP02
    contract (planning→coord worktree) is removed; preserving it as a fallback is
    forbidden (C-005, FR-002). The round-trip and the anti-fakeable negative proof
    are kept and re-targeted onto the **primary** seam.
    """

    def test_spec_planning_commit_lands_and_reads_back_from_primary_surface(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Allow the planning commit to land on the protected primary ``main`` so the
        # write→read-back round-trip is observable hermetically. WP02's contract is
        # that a SPEC (a planning kind) routes to the primary ``target_branch`` for
        # EVERY topology; the protected-ref refusal path is WP03's deadlock-removal
        # responsibility (T015), not this round-trip's concern.
        monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
        repo = build_protected_target_repo(tmp_path)
        repo.assert_target_is_protected()
        _feature_dir, spec_path, status_path = _seed_coord_mission(repo.repo_root)

        # New spec content so there is something to commit.
        spec_path.write_text(_SPEC_BODY + "\nFR-009: status emission converges.\n", encoding="utf-8")
        expected_body = spec_path.read_text(encoding="utf-8")

        # WRITE leg: route through the REAL kind-aware seam. No router mock — the
        # placement_ref is the value resolve_placement_only computes for SPEC, not
        # a stub. Under FR-003 a SPEC kind resolves to the PRIMARY target branch.
        policy = ProtectionPolicy.resolve(repo.repo_root)
        result = commit_for_mission(
            repo_root=repo.repo_root,
            mission_slug=_SLUG,
            files=(spec_path,),
            message="spec: kind-resolved planning commit",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
        )

        assert result.status == "committed", f"diagnostic={result.diagnostic!r}"
        assert result.placement_ref == repo.target_branch, (
            "WRITE leg: a planning (SPEC) commit must land on the PRIMARY "
            f"target branch ({repo.target_branch!r}) under FR-003, NOT the "
            f"coordination branch; got {result.placement_ref!r}"
        )
        assert result.placement_ref != _COORD_BRANCH, (
            "WRITE leg: the removed planning→coord route regressed — the SPEC "
            f"commit landed on the coordination branch {_COORD_BRANCH!r} (FR-003/C-005)."
        )

        # READ-BACK leg (SC-004): resolve the next-command read surface the way
        # /spec-kitty.tasks would (candidate_feature_dir_for_mission) and assert the
        # committed spec.md content is recoverable from THAT surface — the #2063
        # round-trip, now coherent on the PRIMARY seam (not merely placement_ref).
        read_surface = candidate_feature_dir_for_mission(repo.repo_root, _SLUG)
        read_back_spec = read_surface / "spec.md"
        assert read_back_spec.exists(), (
            "READ-BACK leg: the next-command read surface "
            f"({read_surface}) does not expose the committed spec.md — the write "
            "and read legs diverge (the #2063 desync)."
        )
        assert read_back_spec.read_text(encoding="utf-8") == expected_body, (
            "READ-BACK leg: spec.md read from the resolved surface does not "
            "match the committed content — SC-004 round-trip is broken."
        )

        # The read surface must be the PRIMARY feature dir (NOT a coordination
        # worktree), proving the round-trip is on the SAME primary surface as the
        # write — the inverse of the removed planning→coord contract.
        assert ".worktrees" not in str(read_surface), (
            "READ-BACK leg: a planning artifact's read surface must be the PRIMARY "
            f"feature dir, never a coordination worktree (FR-002); got {read_surface}"
        )

        # BIFURCATION leg (C-001): a coordination-partition artifact on the SAME
        # mission still routes to the coordination branch. This is what makes the
        # test fail red if planning regressed to coord (placement collapse) OR if
        # status leaked onto primary — proving the partition, not just "planning moved".
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
        status_path.write_text(_STATUS_BODY + '{"wp_id":"WP01","to_lane":"claimed"}\n', encoding="utf-8")
        status_result = commit_for_mission(
            repo_root=repo.repo_root,
            mission_slug=_SLUG,
            files=(status_path,),
            message="status: coordination-partition commit",
            policy=policy,
            kind=MissionArtifactKind.STATUS_STATE,
        )
        assert status_result.placement_ref == _COORD_BRANCH, (
            "BIFURCATION leg: a STATUS_STATE (C-001 coordination partition) commit "
            f"must stay on the coordination branch {_COORD_BRANCH!r}; got "
            f"{status_result.placement_ref!r}. If this equals the primary target "
            "branch the partition has collapsed (status leaked onto primary)."
        )
        assert status_result.placement_ref != repo.target_branch, (
            "BIFURCATION leg: status routed to the PRIMARY target branch — the "
            "planning/coordination partition (FR-003 + C-001) has collapsed."
        )

    def test_negative_planning_commit_is_on_primary_not_coord_worktree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Anti-fakeable inverse: the planning commit IS on primary and NOT on coord.

        Proves the write actually landed on primary HEAD (so the round-trip above
        is not vacuous) AND that it did not also leak onto the coordination branch
        — the inverse of the removed planning→coord contract (FR-003 / C-005).
        """
        monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
        repo = build_protected_target_repo(tmp_path)
        _feature_dir, spec_path, _status_path = _seed_coord_mission(repo.repo_root)
        new_body = _SPEC_BODY + "\nonly-on-primary marker.\n"
        spec_path.write_text(new_body, encoding="utf-8")

        policy = ProtectionPolicy.resolve(repo.repo_root)
        commit_for_mission(
            repo_root=repo.repo_root,
            mission_slug=_SLUG,
            files=(spec_path,),
            message="spec: primary-only marker",
            policy=policy,
            kind=MissionArtifactKind.SPEC,
        )

        # POSITIVE: the committed content IS on the primary target branch HEAD.
        primary_show = subprocess.run(
            ["git", "show", f"{repo.target_branch}:kitty-specs/{_SLUG}/spec.md"],
            cwd=repo.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "only-on-primary marker" in primary_show.stdout, (
            f"primary target branch ({repo.target_branch}) does NOT carry the "
            "planning marker — a SPEC commit must land on primary (FR-003)."
        )

        # NEGATIVE (anti-fakeable): the planning change must NOT have leaked onto
        # the coordination branch. The removed planning→coord route would have put
        # it there — its absence proves the route is gone (C-005).
        coord_show = subprocess.run(
            ["git", "show", f"{_COORD_BRANCH}:kitty-specs/{_SLUG}/spec.md"],
            cwd=repo.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "only-on-primary marker" not in coord_show.stdout, (
            f"the coordination branch ({_COORD_BRANCH}) carries the planning "
            "marker — the removed planning→coord route regressed (FR-003 / C-005)."
        )


# ---------------------------------------------------------------------------
# T025 — safe-commit separates its two responsibilities (FR-007 / NFR-002)
# ---------------------------------------------------------------------------


class TestSafeCommitTwoResponsibilities:
    """The generic operator-file path stays HEAD-driven; the mission-aware path uses the seam."""

    def test_generic_path_resolves_from_to_branch_not_the_seam(self, tmp_path: Path) -> None:
        """A non-mission file with --to-branch resolves the explicit ref (generic path)."""
        from specify_cli.cli.commands.safe_commit_cmd import _resolve_commit_target

        operator_file = tmp_path / "notes.txt"
        operator_file.write_text("operator note\n", encoding="utf-8")

        target = _resolve_commit_target(
            explicit_to_branch="lane-x",
            repo_root=tmp_path,
            files=[operator_file],
        )
        assert target.ref == "lane-x"

    def test_generic_path_without_to_branch_uses_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-mission file without --to-branch infers HEAD (generic path preserved)."""
        import specify_cli.cli.commands.safe_commit_cmd as mod

        operator_file = tmp_path / "config.toml"
        operator_file.write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(mod, "get_current_branch", lambda _root: "lane-head")

        target = mod._resolve_commit_target(
            explicit_to_branch=None,
            repo_root=tmp_path,
            files=[operator_file],
        )
        assert target.ref == "lane-head", "generic HEAD inference must be preserved (NFR-002)"

    def test_mission_aware_path_resolves_via_seam_not_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A kitty-specs/<slug>/ artifact for a resolvable mission resolves via the seam.

        Asserts the seam value is used AND that ``get_current_branch`` is never
        consulted as the destination decision (the #2063 root) on this path.
        """
        import specify_cli.cli.commands.safe_commit_cmd as mod
        from mission_runtime import CommitTarget

        spec = tmp_path / "kitty-specs" / "001-demo" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Spec\n", encoding="utf-8")

        head_consulted = False

        def _spy_head(_root: Path) -> str:
            nonlocal head_consulted
            head_consulted = True
            return "should-not-be-the-destination"

        monkeypatch.setattr(mod, "get_current_branch", _spy_head)
        # write-surface-coherence WP03 / T012: the seam is now kind-aware — the
        # safe-commit command threads the artifact kind into resolve_placement_only.
        monkeypatch.setattr(
            "mission_runtime.resolve_placement_only",
            lambda _root, _slug, *, kind: CommitTarget(ref="kitty/mission-001-demo-AAAA1111"),
        )

        target = mod._resolve_commit_target(
            explicit_to_branch=None,
            repo_root=tmp_path,
            files=[spec],
        )
        assert target.ref == "kitty/mission-001-demo-AAAA1111"
        assert not head_consulted, (
            "mission-aware path consulted get_current_branch as the destination "
            "decision (the #2063 root); it must resolve via the WP03 seam instead."
        )

    def test_unresolvable_mission_path_falls_back_to_generic_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A kitty-specs-looking path whose seam can't resolve degrades to the generic path.

        Guards against the discriminator hard-failing a legitimate commit when the
        mission isn't resolvable yet (no churn for missing missions).
        """
        import specify_cli.cli.commands.safe_commit_cmd as mod
        from mission_runtime import ActionContextError

        spec = tmp_path / "kitty-specs" / "ghost" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Spec\n", encoding="utf-8")

        def _raise(_root: Path, _slug: str, *, kind: object) -> object:
            raise ActionContextError("MISSION_CONTEXT_UNRESOLVED", "no such mission")

        monkeypatch.setattr("mission_runtime.resolve_placement_only", _raise)
        monkeypatch.setattr(mod, "get_current_branch", lambda _root: "fallback-head")

        target = mod._resolve_commit_target(
            explicit_to_branch=None,
            repo_root=tmp_path,
            files=[spec],
        )
        assert target.ref == "fallback-head", (
            "an unresolvable mission path must fall back to the generic HEAD path, "
            "not raise — keeping legitimate commits functional."
        )

    def test_mission_slug_discriminator_only_fires_for_kitty_specs_paths(self, tmp_path: Path) -> None:
        """The discriminator returns a slug only for kitty-specs/<slug>/ artifacts."""
        from specify_cli.cli.commands.safe_commit_cmd import _mission_slug_from_paths

        operator = tmp_path / "src" / "main.py"
        operator.parent.mkdir(parents=True)
        operator.write_text("x\n", encoding="utf-8")
        assert _mission_slug_from_paths(tmp_path, [operator]) is None

        spec = tmp_path / "kitty-specs" / "042-mission" / "plan.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("y\n", encoding="utf-8")
        assert _mission_slug_from_paths(tmp_path, [spec]) == "042-mission"
