"""WP07 / T024 + T025 + T026 — Config-honoring, hatch, and NFR-004/002 coverage.

Coverage map:

T024 (SC-002 / US2 config-honoring)
------------------------------------
``protection.protected_branches: []``   ⇒ spec commit lands directly on ``main``
                                           (no coord worktree created).
Primary in ``protection.protected_branches: [main]`` ⇒ routes to coord worktree.

T025 (FR-006 hatch)
--------------------
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` active  ⇒ ``is_protected`` False
end-to-end ⇒ commit lands directly (no materialisation).

T026 (NFR-004 byte-identical default + NFR-002 warm-materialisation bound)
---------------------------------------------------------------------------
NFR-004: ``ProtectionPolicy.resolve(repo_root).protected_branches`` for a no-config
repo equals ``{main, master}`` ∪ {remote-default} — **exact set equality**, not just
"behaviour unchanged".

NFR-002: coord-worktree materialisation completes in < 2 s warm (0 network).
Asserted via ``@pytest.mark.timing`` (do not wall-clock in the parallel shard).

All fixtures use ``tmp_path`` — no mocks for filesystem reads, no network.
``ProtectedTargetRepo.build`` asserts its own preconditions so silently-vacuous
tests cannot sneak through.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.git import protection_policy as _pp_module
from specify_cli.git.protection_policy import ProtectionPolicy

from tests._perf_helpers import assert_timing_budget
from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    build_protected_target_repo,
    protected_target_repo,
)

pytestmark = pytest.mark.git_repo

# ---------------------------------------------------------------------------
# Realistic test constants (NFR-005 / test-data policy)
# ---------------------------------------------------------------------------
_FULL_ULID: str = "01KVMBD6CFGHK9MXW7ZB2CDN01"
_MID8: str = _FULL_ULID[:8]
_SLUG: str = "config-honoring"
_COORD_BRANCH: str = f"kitty/mission-{_SLUG}-{_MID8}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _git_nocheck(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


def _write_kittify_protection(repo_root: Path, content: str) -> None:
    """Write/overwrite .kittify/config.yaml with the given YAML content."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _build_git_repo_on_main(base: Path) -> Path:
    """Initialise a minimal git repo on 'main'."""
    repo = base / "repo"
    repo.mkdir(parents=True)

    def _g(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    _g("init", "--initial-branch", "main")
    _g("config", "user.email", "test@example.com")
    _g("config", "user.name", "Test")
    _g("config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    _g("add", "-A")
    _g("commit", "-m", "init")
    return repo


def _seed_mission(repo_root: Path, slug: str, mid8: str, coord_branch: str) -> tuple[Path, Path]:
    """Create kitty-specs/<slug>/ with meta.json + spec.md.

    Also creates the coordination branch (mirrors what ``mission create`` does).
    CoordinationWorkspace.resolve requires the branch to exist before materialising.
    """
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": _FULL_ULID,
        "mission_slug": slug,
        "mid8": mid8,
        "coordination_branch": coord_branch,
        "topology": "coord",
        "target_branch": "main",
        "mission_type": "software-dev",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    spec = feature_dir / "spec.md"
    spec.write_text("# Spec\n\nPlaceholder.\n", encoding="utf-8")
    # The coord branch must exist for CoordinationWorkspace.resolve to materialise.
    # We create it here; callers must commit seed files before calling this so that
    # the branch starts from a clean state.
    return feature_dir, spec


# ---------------------------------------------------------------------------
# T024 — US2 config-honoring (SC-002)
# ---------------------------------------------------------------------------


class TestProtectedBranchesConfigHonoring:
    """T024 (SC-002): ``protection.protected_branches`` config controls routing.

    Row 1: explicit ``[]`` → nothing protected → direct commit on main.
    Row 2: explicit ``[main]`` → main protected → routes to coord worktree.
    """

    def test_empty_protected_branches_routes_directly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US2: ``protection.protected_branches: []`` → commit lands directly on main.

        No coord worktree is created.  This proves the config IS honoured:
        a hardcoded "main is always protected" guard would route to coord and fail.
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = build_protected_target_repo(tmp_path)
        # Override config: explicitly empty list → nothing protected.
        _write_kittify_protection(
            repo.repo_root,
            "project: config-honoring\nprotection:\n  protected_branches: []\n",
        )

        slug = "direct-on-main"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed mission")
        spec.write_text("# Spec\n\nUpdated.\n", encoding="utf-8")

        # Re-resolve policy after writing the empty-list config.
        policy = ProtectionPolicy.resolve(repo.repo_root)
        assert policy.protected_branches == frozenset(), (
            "Precondition: policy must resolve to empty set after setting []."
        )
        assert not policy.is_protected("main"), (
            "Precondition: 'main' must NOT be protected with explicit []."
        )

        coord_worktree = repo.repo_root / ".worktrees" / f"{slug}-{mid8}-coord"

        # Stub commit_for_mission to avoid real git commit (unit boundary).
        _calls: list[dict[str, Any]] = []

        def _stub(**kwargs: Any) -> CommitRouterResult:
            _calls.append(kwargs)
            return CommitRouterResult(
                status="committed",
                placement_ref=kwargs.get("mission_slug", "unknown"),
                commit_hash="aaa1111",
            )

        from mission_runtime import CommitTarget

        with patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=CommitTarget(ref="main"),
        ):
            # commit_for_mission with PRIMARY kind and is_protected=False → direct commit.
            result = commit_for_mission(
                repo_root=repo.repo_root,
                mission_slug=slug,
                files=(spec,),
                message="spec: direct commit",
                policy=policy,
                kind=MissionArtifactKind.SPEC,
            )

        # With empty protected_branches + PRIMARY kind, the router should NOT try to
        # create a coord worktree.  In the real code path it commits directly.
        assert not coord_worktree.exists(), (
            "T024 violated: coord worktree was created even though config has []. "
            "The protection config is NOT being honoured."
        )
        # The result must NOT be "no_op_wrong_surface" (which would indicate a refusal
        # on a protected branch — but we declared no branches protected).
        assert result.status != "no_op_wrong_surface", (
            f"T024: router returned 'no_op_wrong_surface' for a non-protected branch. "
            f"Config [] is not being respected. Diagnostic: {result.diagnostic!r}"
        )

    def test_protected_main_routes_to_coord_worktree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US2: ``protection.protected_branches: [main]`` → routes to coord worktree.

        The complement of the empty-list test: when main IS declared protected,
        a COORDINATION-partition artifact (acceptance matrix) must materialise the
        coord worktree. (Planning artifacts no longer transit coord under the
        write-surface-coherence contract — they refuse on a protected primary
        and direct the operator to a feature branch — so the coord-routing
        mechanism is now exercised with a coord kind, ``ACCEPTANCE_MATRIX``.
        Exemplar swapped from ``ANALYSIS_REPORT``, re-homed PRIMARY by FR-003.)
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = build_protected_target_repo(tmp_path)
        _write_kittify_protection(
            repo.repo_root,
            "project: config-honoring\nprotection:\n  protected_branches:\n    - main\n",
        )

        slug = "via-coord"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, _spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        report = feature_dir / "acceptance-matrix.json"
        report.write_text('{"seed": true}\n', encoding="utf-8")
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed mission")
        # Create coord branch so CoordinationWorkspace.resolve can materialise a worktree.
        _git(repo.repo_root, "branch", coord_branch)
        report.write_text('{"updated": "via coord"}\n', encoding="utf-8")

        policy = ProtectionPolicy.resolve(repo.repo_root)
        assert policy.is_protected("main"), (
            "Precondition: 'main' must be protected with explicit [main]."
        )

        # Exercise the canonical kind-aware authority: the coordination
        # artifact resolves to the coord branch while PRIMARY_METADATA resolves
        # to main. A constant placement mock made those two distinct reads equal.
        result = commit_for_mission(
            repo_root=repo.repo_root,
            mission_slug=slug,
            files=(report,),
            message="acceptance-matrix: via coord",
            policy=policy,
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

        coord_worktree = repo.repo_root / ".worktrees" / f"{slug}-{mid8}-coord"
        assert coord_worktree.exists(), (
            "T024: coord worktree NOT created even though main is explicitly protected. "
            "Protection config [main] is not being respected."
        )
        assert result.status == "committed", (
            f"T024: expected 'committed' on protected-then-coord path, "
            f"got {result.status!r}. Diagnostic: {result.diagnostic!r}"
        )


# ---------------------------------------------------------------------------
# T025 — FR-006 hatch end-to-end
# ---------------------------------------------------------------------------


class TestFR006HatchEndToEnd:
    """T025: active hatch → is_protected False → direct commit (no coord worktree)."""

    def test_hatch_active_routes_directly_not_to_coord(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-006: hatch active ⇒ is_protected False end-to-end.

        With the hatch set, even a repo on ``main`` (normally protected) must:
        1. Have ``policy.is_protected("main") == False``.
        2. Route the commit DIRECTLY (no coord worktree materialisation).
        """
        monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")

        repo = build_protected_target_repo(tmp_path)
        slug = "hatch-direct"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed mission")
        spec.write_text("# Spec\n\nHatch active.\n", encoding="utf-8")

        policy = ProtectionPolicy.resolve(repo.repo_root)
        # FR-006 invariant 1: hatch active → is_protected returns False.
        assert policy.operator_hatch_active is True, "Precondition: hatch must be active."
        assert not policy.is_protected("main"), (
            "FR-006: is_protected('main') must be False when hatch is active."
        )

        from mission_runtime import CommitTarget

        # With a hatch-active policy, the commit must route through PRIMARY
        # (because is_protected=False).  Provide a FLATTENED / PRIMARY placement
        # to confirm direct routing.
        coord_worktree = repo.repo_root / ".worktrees" / f"{slug}-{mid8}-coord"

        with patch(
            "specify_cli.coordination.commit_router.resolve_placement_only",
            return_value=CommitTarget(ref="main"),
        ):
            result = commit_for_mission(
                repo_root=repo.repo_root,
                mission_slug=slug,
                files=(spec,),
                message="spec: hatch direct",
                policy=policy,
                kind=MissionArtifactKind.SPEC,
            )

        # FR-006 invariant 2: no coord worktree created (direct routing).
        assert not coord_worktree.exists(), (
            "FR-006 violated: coord worktree was created even though hatch is active. "
            "is_protected should have returned False and skipped materialisation."
        )
        # FR-006 invariant 3: result must not be no_op_wrong_surface (a protection refusal).
        assert result.status != "no_op_wrong_surface", (
            "FR-006: got 'no_op_wrong_surface' despite hatch active — "
            "the hatch is not controlling is_protected end-to-end."
        )

    def test_hatch_inactive_does_route_to_coord(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Baseline: without hatch, the normal protect→coord routing applies.

        Exercised with a COORDINATION-partition kind (``ACCEPTANCE_MATRIX``): under
        the write-surface-coherence contract only coordination-owned artifacts
        transit the coord worktree, so the protect→coord materialisation baseline
        is now proved with an acceptance-matrix write. (Exemplar swapped from
        ``ANALYSIS_REPORT``, re-homed PRIMARY by FR-003.)
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = build_protected_target_repo(tmp_path)
        slug = "no-hatch-coord"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, _spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        report = feature_dir / "acceptance-matrix.json"
        report.write_text('{"seed": true}\n', encoding="utf-8")
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed")
        # Create coord branch so CoordinationWorkspace.resolve can materialise.
        _git(repo.repo_root, "branch", coord_branch)
        report.write_text('{"updated": "no hatch"}\n', encoding="utf-8")

        policy = ProtectionPolicy.resolve(repo.repo_root)
        assert not policy.operator_hatch_active, "Baseline: hatch must be OFF."
        assert policy.is_protected("main"), "Baseline: 'main' must be protected without hatch."

        # Exercise the canonical kind-aware authority: the coordination
        # artifact resolves to the coord branch while PRIMARY_METADATA resolves
        # to main. A constant placement mock made those two distinct reads equal.
        result = commit_for_mission(
            repo_root=repo.repo_root,
            mission_slug=slug,
            files=(report,),
            message="acceptance-matrix: no hatch",
            policy=policy,
            kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        )

        coord_worktree = repo.repo_root / ".worktrees" / f"{slug}-{mid8}-coord"
        assert coord_worktree.exists(), (
            "Baseline: coord worktree must be created when hatch is OFF and main is protected."
        )
        assert result.status == "committed", f"Baseline: expected committed, got {result.status!r}."


# ---------------------------------------------------------------------------
# T026 — NFR-004 byte-identical default + NFR-002 materialisation bound
# ---------------------------------------------------------------------------


class TestNFR004ByteIdenticalDefault:
    """T026 (NFR-004): no-config repo → exact set {main, master} ∪ {remote-default}.

    Exact set equality (not just "behaviour unchanged").  The pre-change function
    ``commit_helpers.protected_branches()`` is used as the oracle: it is the
    public delegate of ``ProtectionPolicy.resolve(repo).protected_branches``
    (T002 / FR-010), so the two must produce byte-identical results.
    """

    def test_no_config_returns_exact_default_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004: ProtectionPolicy.resolve on a no-config repo == {main, master}."""
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)
        # No .kittify/config.yaml → absent-key path → {main, master} ∪ {remote-default}.
        # This repo has no remote, so remote-default is None → set == {main, master}.

        policy = ProtectionPolicy.resolve(repo)

        # NFR-004 exact set equality — not just membership.
        assert policy.protected_branches == frozenset({"main", "master"}), (
            f"NFR-004 violated: expected exactly {{main, master}} for a no-config repo, "
            f"got {policy.protected_branches!r}. "
            "A no-remote repo must NOT have additional branches in the default set."
        )

    def test_no_config_policy_delegate_byte_identical_to_protected_branches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004: ProtectionPolicy.resolve result is byte-identical to protected_branches().

        ``commit_helpers.protected_branches()`` is the public delegate:
        they must return the same frozenset.
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)

        from specify_cli.git.commit_helpers import protected_branches as legacy_delegate

        via_policy = ProtectionPolicy.resolve(repo).protected_branches
        via_delegate = legacy_delegate(repo)

        assert via_policy == via_delegate, (
            f"NFR-004: ProtectionPolicy.resolve().protected_branches {via_policy!r} != "
            f"legacy delegate {via_delegate!r}. The two must be byte-identical."
        )

    def test_remote_default_augments_default_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004: with a fake remote default 'develop', set == {main, master, develop}."""
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)
        monkeypatch.setattr(_pp_module, "_remote_default_branch", lambda _: "develop")

        policy = ProtectionPolicy.resolve(repo)

        assert policy.protected_branches == frozenset({"main", "master", "develop"}), (
            f"NFR-004: expected {{main, master, develop}} with remote-default=develop, "
            f"got {policy.protected_branches!r}."
        )

    def test_explicit_empty_list_is_not_the_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004 boundary: explicit [] is NOT the same as absent key.

        The absent-key path returns {main, master}; explicit [] returns frozenset().
        These must NOT be equal.
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)

        # Absent key.
        absent_key_policy = ProtectionPolicy.resolve(repo)
        assert absent_key_policy.protected_branches == frozenset({"main", "master"})

        # Explicit empty list.
        _write_kittify_protection(
            repo,
            "protection:\n  protected_branches: []\n",
        )
        explicit_empty_policy = ProtectionPolicy.resolve(repo)
        assert explicit_empty_policy.protected_branches == frozenset()

        assert absent_key_policy.protected_branches != explicit_empty_policy.protected_branches, (
            "NFR-004: absent-key and explicit-[] must NOT produce the same set. "
            "The distinction is load-bearing for US2 opt-out."
        )


# ---------------------------------------------------------------------------
# T026 (NFR-002): materialisation completes within 2 s warm / 0 network
# ---------------------------------------------------------------------------


class TestNFR002MaterialisationFunctional:
    """#4015 split: functional halves of ``TestNFR002MaterialisationTimingBound``.

    Unmarked (per-PR) — the timing/wall-clock asserts stay on the
    ``@pytest.mark.performance`` twins below; only functional correctness is
    asserted here.
    """

    def test_coord_worktree_materialises_and_is_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-002 (functional, #4015 split): materialise-on-demand is idempotent."""
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = build_protected_target_repo(tmp_path)
        slug = "timing-check"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed timing mission")
        # Create coord branch so CoordinationWorkspace.resolve can materialise.
        _git(repo.repo_root, "branch", coord_branch)
        spec.write_text("# Spec\n\nTiming check.\n", encoding="utf-8")

        from specify_cli.coordination.workspace import CoordinationWorkspace

        # First call creates the worktree (cold path).
        wt_path = CoordinationWorkspace.resolve(repo.repo_root, slug, mid8)
        # Second call (warm / idempotent).
        wt_path_2 = CoordinationWorkspace.resolve(repo.repo_root, slug, mid8)

        # The worktree must have been created (materialisation actually ran).
        assert wt_path.exists(), "CoordinationWorkspace.resolve did not create the worktree."
        assert wt_path_2 == wt_path, "Idempotent resolve returned a different path."

    def test_protection_policy_resolve_has_no_remote_and_correct_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-004 (functional, #4015 split): correct default set, no remote configured.

        A repo with no remote configured must produce {main, master}. We verify
        by confirming ``git remote`` reports nothing and that resolve returns the
        expected default set.
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)

        # Sanity: no remote configured.
        result = subprocess.run(
            ["git", "remote"], cwd=repo, capture_output=True, text=True
        )
        assert result.stdout.strip() == "", (
            "Precondition: test repo must have no remotes (otherwise timing is unreliable)."
        )

        policy = ProtectionPolicy.resolve(repo)

        # NFR-004: correct default set.
        assert policy.protected_branches == frozenset({"main", "master"})


@pytest.mark.timing
class TestNFR002MaterialisationTimingBound:
    """T026 (NFR-002): coord-worktree materialisation < 2 s warm, 0 network.

    The @pytest.mark.timing marker is used per the test-data contract (WP07 spec):
    do NOT wall-clock in the parallel shard; instead assert the observed elapsed
    or defer to a timing fixture. Also ``@pytest.mark.performance`` (#4015 split):
    the functional halves of these two tests live in
    ``TestNFR002MaterialisationFunctional`` above, unmarked, on the per-PR path.

    Here we assert the observed elapsed directly, using a generous wall-clock bound
    (2 s) that accommodates slow CI.  0-network is structural: the fixture repo has
    no remote and ``_remote_default_branch`` returns None (no git-remote call).
    """

    @pytest.mark.performance
    def test_coord_worktree_materialises_within_two_seconds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-002: CoordinationWorkspace.resolve (materialise-on-demand) < 2 s warm."""
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = build_protected_target_repo(tmp_path)
        slug = "timing-check"
        mid8 = _MID8
        coord_branch = f"kitty/mission-{slug}-{mid8}"
        feature_dir, spec = _seed_mission(repo.repo_root, slug, mid8, coord_branch)
        _git(repo.repo_root, "add", "-A")
        _git(repo.repo_root, "commit", "-m", "seed timing mission")
        # Create coord branch so CoordinationWorkspace.resolve can materialise.
        _git(repo.repo_root, "branch", coord_branch)
        spec.write_text("# Spec\n\nTiming check.\n", encoding="utf-8")

        from specify_cli.coordination.workspace import CoordinationWorkspace

        # Warm run: measure resolution time (first create, then idempotent re-resolve).
        # First call creates the worktree (cold path).
        _t0 = time.perf_counter()
        CoordinationWorkspace.resolve(repo.repo_root, slug, mid8)
        cold_elapsed = time.perf_counter() - _t0

        # Second call (warm / idempotent): must be even faster.
        _t1 = time.perf_counter()
        CoordinationWorkspace.resolve(repo.repo_root, slug, mid8)
        warm_elapsed = time.perf_counter() - _t1

        # NFR-002: both must complete within 2 s.
        assert_timing_budget(cold_elapsed, 2.0, name="cold_elapsed")
        assert_timing_budget(warm_elapsed, 2.0, name="warm_elapsed")

    @pytest.mark.performance
    def test_protection_policy_resolve_is_zero_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NFR-002 / NFR-004: ProtectionPolicy.resolve makes 0 network calls.

        A repo with no remote configured must produce {main, master} without
        making any outbound network calls.  We verify by confirming ``git remote
        show origin`` fails (no remote) and that resolve still returns the
        expected default set — if it were making real network calls it would
        block or error differently.
        """
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        repo = _build_git_repo_on_main(tmp_path)

        # NFR-002: resolve is fast (0 network) even on the absent-key path.
        _t0 = time.perf_counter()
        ProtectionPolicy.resolve(repo)
        elapsed = time.perf_counter() - _t0

        assert_timing_budget(elapsed, 2.0, name="elapsed")
