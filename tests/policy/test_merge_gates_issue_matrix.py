"""Merge issue-matrix gate partition split + terminal-verdict enforcement.

Mission ``issue-matrix-partition-integrity-01M3H10A`` WP04 (#4943, FR-003,
FR-004, FR-006). Covers both IC-03 and IC-04:

* **IC-03 (FR-003 discovery, half-by-half axis 1)**: the merge completeness
  gate (``_evaluate_issue_matrix_completeness_gate``) must discover gating
  references from the PRIMARY partition -- never the coordination husk -- on
  every topology. A coord mission citing a gating issue with no matrix row
  anywhere must FAIL (never "nothing to enforce"); a coord-less (``lanes``)
  mission with the identical shape must FAIL identically (parity).
* **IC-03/FR-004 (verdict read, half-by-half axis 2)**: once a row exists on
  both partitions, the completeness gate reads matrix content through the
  COORD partition (materialized dir, or -- post-consolidation -- the
  coordination branch ref via the WP02 shared helper), never the stale
  PRIMARY residue. A divergent fixture (primary ``in-mission``, coord
  ``fixed``) must resolve cleanly (terminality gate reads ``fixed``); the
  same fixture inverted (primary ``fixed``, coord ``in-mission``) must FAIL
  via the terminal-verdict sibling gate -- proving discovery (axis 1) and
  verdict-read (axis 2) are each independently exercised.
* **IC-04 (FR-006 terminality)**: a sibling gate reuses
  ``_issue_matrix_approval_blocker`` (``tasks_parsing_validation.py``) with
  ``target_lane=Lane.DONE`` so an ``in-mission`` (or schema-invalid
  ``unknown``) gating row refuses in ``block`` mode (naming the row) and
  warns (without blocking) in ``warn`` mode; a terminal verdict advances
  clean in either mode (positive control).

RED on base (before T013/T014 land): ``_evaluate_issue_matrix_completeness_gate``
does not accept ``(repo_root, mission_slug, is_blocking)`` and no
``issue_matrix_verdict_terminality`` gate exists at all -- every assertion
below raises ``TypeError`` / ``StopIteration`` (``next()`` on an empty
generator when the gate name is absent from ``result.gates``) until the fix
lands.

Fixtures build REAL git repos through the actual merge-time bookkeeping entry
point, mirroring ``tests/mission_runtime/test_issue_matrix_content_source.py``
(WP02) and ``tests/mission_runtime/test_issue_matrix_ref_read.py`` (WP01).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.merge.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta
from specify_cli.policy.config import MergeGateConfig
from specify_cli.policy.merge_gates import GateVerdict, evaluate_merge_gates

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_ISSUE_KEY = "#1234"
_GATING_SPEC_TEXT = f"Fixes {_ISSUE_KEY} in this mission.\n"
_COMPLETENESS_GATE = "issue_matrix_completeness"
_TERMINALITY_GATE = "issue_matrix_verdict_terminality"


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors WP01/WP02 test files)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    topology: str,
    coordination_branch: str | None = None,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": topology,
        "friendly_name": "Merge issue-matrix gate fixture",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matrix_json(rows: dict[str, str]) -> str:
    return json.dumps({"rows": {issue: {"verdict": verdict, "evidence_ref": "PR #1"} for issue, verdict in rows.items()}})


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_git_repo(r)
    return r


def _run_gates(repo: Path, mission_slug: str, *, mode: str, feature_dir: Path | None = None) -> tuple[bool, list]:
    result = evaluate_merge_gates(
        feature_dir if feature_dir is not None else repo / "kitty-specs" / mission_slug,
        mission_slug,
        [],
        MergeGateConfig(mode=mode),
        repo,
    )
    return result.overall_pass, result.gates


def _coord_husk_dir(tmp_path: Path, mission_slug: str) -> Path:
    """A STATUS-ONLY coordination worktree stand-in: carries no ``spec.md``
    or issue-matrix content of its own -- exactly the shape the real merge
    flow hands ``evaluate_merge_gates`` on a coord-topology mission (a
    coordination worktree/husk, distinct from the PRIMARY checkout that
    holds ``spec.md``). Reproduces the pre-fix bug precisely: passing THIS
    directory as ``feature_dir`` must not blind reference discovery once it
    is routed through the seam (``repo_root``/``mission_slug``) instead of
    the caller-supplied ``feature_dir``.
    """
    husk = tmp_path / f"{mission_slug}-coord-husk"
    husk.mkdir(parents=True, exist_ok=True)
    return husk


def _gate(gates: list, gate_name: str):
    return next(g for g in gates if g.gate_name == gate_name)


# ---------------------------------------------------------------------------
# Coord fixture builder: post-consolidation (worktree gone, branch retained)
# ---------------------------------------------------------------------------


def _build_coord_mission(
    repo: Path,
    *,
    mid8: str,
    primary_matrix: dict[str, str] | None,
    coord_matrix: dict[str, str] | None,
) -> tuple[str, Path]:
    """A CONSOLIDATED coord mission: primary residue vs authored coord ref
    may diverge -- the caller controls each partition's matrix independently
    to exercise discovery (FR-003) and verdict-read (FR-004) separately.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="coord",
        coordination_branch=coordination_branch,
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(_GATING_SPEC_TEXT, encoding="utf-8")
    if primary_matrix is not None:
        (feature_dir / "issue-matrix.json").write_text(_matrix_json(primary_matrix), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    # Branch coordination AFTER the scaffold so it starts from the same
    # (primary) state, then overwrite with the coord-authored matrix.
    _git(repo, "branch", coordination_branch, target_branch)

    record_baseline_merge_commit(feature_dir, scaffold_sha, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): record baseline_merge_commit (E1 consolidation)")

    _git(repo, "checkout", "-q", coordination_branch)
    matrix_path = feature_dir / "issue-matrix.json"
    if coord_matrix is not None:
        matrix_path.write_text(_matrix_json(coord_matrix), encoding="utf-8")
        _git(repo, "add", ".")
        if _git(repo, "status", "--porcelain").stdout.strip():
            _git(repo, "commit", "-m", f"chore({mission_slug}): author issue-matrix verdict")
    elif matrix_path.exists():
        _git(repo, "rm", "-q", str(matrix_path.relative_to(repo)))
        _git(repo, "commit", "-m", f"chore({mission_slug}): remove issue-matrix (no coord row)")
    # HEAD returns to the target branch -- the coordination branch is only a
    # retained REF; there is no coord worktree materialized on disk (the
    # post-consolidation case FR-005 threads through).
    _git(repo, "checkout", "-q", target_branch)

    return mission_slug, feature_dir


def _build_lanes_mission(repo: Path, *, mid8: str, primary_matrix: dict[str, str] | None) -> str:
    """Coord-less (``lanes``) mission -- the parity arm for FR-003."""
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"lanes-catalog-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="lanes",
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(_GATING_SPEC_TEXT, encoding="utf-8")
    if primary_matrix is not None:
        (feature_dir / "issue-matrix.json").write_text(_matrix_json(primary_matrix), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    return mission_slug


# ---------------------------------------------------------------------------
# FR-003 -- discovery from PRIMARY, coord-vs-lanes parity
# ---------------------------------------------------------------------------


class TestCompletenessGateDiscoveryParity:
    def test_coord_mission_with_no_row_fails_not_nothing_to_enforce(self, repo: Path, tmp_path: Path) -> None:
        mission_slug, _feature_dir = _build_coord_mission(repo, mid8="01KZR100", primary_matrix=None, coord_matrix={})

        # Simulate the real merge flow's call shape: it hands in the coord
        # husk (no spec.md) as ``feature_dir`` -- discovery must NOT go
        # blind just because the caller-supplied dir carries no spec.
        overall_pass, gates = _run_gates(repo, mission_slug, mode="block", feature_dir=_coord_husk_dir(tmp_path, mission_slug))
        gate = _gate(gates, _COMPLETENESS_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is True
        assert _ISSUE_KEY in gate.details
        assert "nothing to enforce" not in gate.details.lower()
        assert overall_pass is False

    def test_lanes_mission_with_no_row_fails_identically(self, repo: Path) -> None:
        mission_slug = _build_lanes_mission(repo, mid8="01KZR101", primary_matrix=None)

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _COMPLETENESS_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is True
        assert _ISSUE_KEY in gate.details
        assert overall_pass is False


# ---------------------------------------------------------------------------
# FR-004 -- verdict read from COORD, half-by-half proof (divergent/inverted)
# ---------------------------------------------------------------------------


class TestVerdictReadPartition:
    def test_divergent_fixture_coord_terminal_passes(self, repo: Path) -> None:
        """Primary residue is non-terminal (in-mission); coord is fixed.

        Overall PASS proves the terminality gate resolves the verdict from
        COORD, not the stale primary residue (which would fail if read).
        """
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR102",
            primary_matrix={_ISSUE_KEY: "in-mission"},
            coord_matrix={_ISSUE_KEY: "fixed"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")

        assert _gate(gates, _COMPLETENESS_GATE).verdict == GateVerdict.PASS
        assert _gate(gates, _TERMINALITY_GATE).verdict == GateVerdict.PASS
        assert overall_pass is True

    def test_inverted_fixture_coord_non_terminal_fails(self, repo: Path) -> None:
        """Primary residue is terminal (fixed); coord is in-mission.

        Overall FAIL, naming the row, proves the verdict is read from COORD
        -- if it read PRIMARY it would wrongly see 'fixed' and pass.
        """
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR103",
            primary_matrix={_ISSUE_KEY: "fixed"},
            coord_matrix={_ISSUE_KEY: "in-mission"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        completeness = _gate(gates, _COMPLETENESS_GATE)
        terminality = _gate(gates, _TERMINALITY_GATE)

        # Row PRESENCE is unaffected by verdict value -- completeness passes
        # on both fixtures; only the terminality axis differs (half-by-half).
        assert completeness.verdict == GateVerdict.PASS
        assert terminality.verdict == GateVerdict.FAIL
        assert terminality.blocking is True
        assert _ISSUE_KEY in terminality.details
        assert overall_pass is False


# ---------------------------------------------------------------------------
# FR-006 -- terminal-verdict enforcement (block/warn/control), reuse of the
# existing rule, and the schema-validity ('unknown') leg.
# ---------------------------------------------------------------------------


class TestTerminalVerdictEnforcement:
    def test_in_mission_block_mode_refuses_and_names_row(self, repo: Path) -> None:
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR104",
            primary_matrix={_ISSUE_KEY: "in-mission"},
            coord_matrix={_ISSUE_KEY: "in-mission"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is True
        assert _ISSUE_KEY in gate.details
        assert overall_pass is False

    def test_in_mission_warn_mode_advances_but_prints_list(self, repo: Path) -> None:
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR105",
            primary_matrix={_ISSUE_KEY: "in-mission"},
            coord_matrix={_ISSUE_KEY: "in-mission"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="warn")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is False
        assert overall_pass is True
        assert any(_TERMINALITY_GATE in warning for warning in _fmt_warnings(gates))
        assert _ISSUE_KEY in gate.details

    def test_terminal_verdict_advances_clean_positive_control(self, repo: Path) -> None:
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR106",
            primary_matrix={_ISSUE_KEY: "fixed"},
            coord_matrix={_ISSUE_KEY: "fixed"},
        )

        for mode in ("block", "warn"):
            overall_pass, gates = _run_gates(repo, mission_slug, mode=mode)
            gate = _gate(gates, _TERMINALITY_GATE)
            assert gate.verdict == GateVerdict.PASS
            assert overall_pass is True

    def test_unknown_verdict_is_also_non_terminal_schema_validity_leg(self, repo: Path) -> None:
        """A gating row at a SCHEMA-INVALID verdict string ('unknown') must
        also refuse at 'done' -- distinct from the in-mission lever. A
        hand-rolled 'reject the in-mission set' mirror would miss this leg;
        reusing ``_issue_matrix_approval_blocker`` (which also checks
        ``result.passed``) does not.
        """
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR107",
            primary_matrix={_ISSUE_KEY: "unknown"},
            coord_matrix={_ISSUE_KEY: "unknown"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is True
        assert overall_pass is False

    def test_post_consolidation_coord_ref_read_feeds_terminality(self, repo: Path) -> None:
        """The coord-post-consolidation arm (FR-005 threaded through IC-04):
        the coordination WORKTREE was never materialized -- only the branch
        ref is retained -- yet the terminality gate still resolves the
        authored (non-terminal) verdict from it, not the stale primary
        residue that happens to already say 'fixed'.
        """
        mission_slug, _feature_dir = _build_coord_mission(
            repo,
            mid8="01KZR108",
            primary_matrix={_ISSUE_KEY: "fixed"},
            coord_matrix={_ISSUE_KEY: "in-mission"},
        )

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert overall_pass is False


def _fmt_warnings(gates: list) -> list[str]:
    return [f"{g.gate_name}: {g.details}" for g in gates if g.verdict == GateVerdict.FAIL and not g.blocking]
