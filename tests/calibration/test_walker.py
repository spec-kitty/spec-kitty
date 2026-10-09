"""Tests for the calibration walker.

T054: For each in-scope mission, walk every step and assert InequalityResult.holds
is True after the calibration overlays are applied.

Also includes unit tests for the walker itself (overlay loading, graph building,
edge-change recommendations).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from charter.offering.drg.loader import built_in_graph_source
from specify_cli.calibration.walker import (
    _REQUIRED_SCOPE,
    CalibrationFinding,
    EdgeChange,
    walk_mission,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Repo root is three levels above tests/calibration/ in the worktree.

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path(__file__).parent.parent.parent


def _copy_built_in_graph_source(dest_dir: Path) -> None:
    """Copy the shipped built-in DRG graph source file(s) into *dest_dir*.

    Copies whatever layout the WP03 seam exposes — the ``graph.yaml`` monolith
    today, ``*.graph.yaml`` fragments after WP05 — so the overlay tests survive
    the monolith->fragment migration without a hardcoded ``graph.yaml`` path.
    """
    source = built_in_graph_source()
    single = source / "graph.yaml"
    graph_files = [single] if single.is_file() else sorted(source.glob("*.graph.yaml"))
    for graph_file in graph_files:
        shutil.copy(graph_file, dest_dir / graph_file.name)


# ---------------------------------------------------------------------------
# T054: §4.5.1 inequality holds for every step in the four missions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mission_key",
    ["software-dev", "research", "documentation", "erp-custom"],
)
def test_inequality_holds_for_all_steps(mission_key: str) -> None:
    """Every step in every in-scope mission passes §4.5.1 after overlays."""
    findings = walk_mission(mission_key=mission_key, repo_root=_REPO_ROOT)

    assert findings, f"No findings returned for mission '{mission_key}'"

    failures = [
        f"{f.step_id} (action={f.action_id}): "
        f"missing={sorted(f.inequality.missing_urns)}, "
        f"over_broad={sorted(f.inequality.over_broad_urns)}"
        for f in findings
        if not f.inequality.holds
    ]
    assert not failures, (
        f"Mission '{mission_key}' has {len(failures)} failing step(s):\n"
        + "\n".join(f"  {line}" for line in failures)
    )


@pytest.mark.parametrize(
    "mission_key,expected_steps",
    [
        ("software-dev", ["specify", "plan", "tasks", "implement", "review", "retrospect"]),
        ("research", ["scoping", "methodology", "gathering", "synthesis", "output", "retrospect"]),
        ("documentation", ["audit", "design", "discover", "generate", "publish", "validate", "retrospect"]),
        ("erp-custom", ["query-erp", "lookup-provider", "ask-user", "create-js", "refactor-function", "write-report", "retrospective"]),
    ],
)
def test_expected_steps_present(mission_key: str, expected_steps: list[str]) -> None:
    """Walker returns one finding per expected step."""
    findings = walk_mission(mission_key=mission_key, repo_root=_REPO_ROOT)
    step_ids = [f.step_id for f in findings]
    assert step_ids == expected_steps


# ---------------------------------------------------------------------------
# Byte-stability guard: named constants must equal the exact URN literals they
# replaced. Expected sets are spelled with raw strings so the assertion is
# independent of the module constants (a constant value drift fails here).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key,expected",
    [
        (
            ("software-dev", "action:software-dev/specify"),
            frozenset({
                "directive:DIRECTIVE_003",
                "directive:DIRECTIVE_010",
                "tactic:requirements-validation-workflow",
            }),
        ),
        (
            ("software-dev", "action:software-dev/implement"),
            frozenset({
                "directive:DIRECTIVE_024",
                "directive:DIRECTIVE_025",
                "directive:DIRECTIVE_028",
                "directive:DIRECTIVE_029",
                "directive:DIRECTIVE_030",
                "directive:DIRECTIVE_034",
                "tactic:acceptance-test-first",
                "tactic:autonomous-operation-protocol",
                "tactic:change-apply-smallest-viable-diff",
                "tactic:quality-gate-verification",
                "tactic:stopping-conditions",
                "tactic:tdd-red-green-refactor",
                "toolguide:efficient-local-tooling",
            }),
        ),
        (
            # Pins the two re-inlined-constant fixes (DIRECTIVE_010, DIRECTIVE_037),
            # plus DIRECTIVE_003 (mission governance-at-the-gate WP03, FR-005):
            # moved off `implement` onto `review` as a REQUIRED positive guard
            # (no longer a silently-tolerated calibrator-sourced extra).
            ("software-dev", "action:software-dev/review"),
            frozenset({
                "directive:DIRECTIVE_003",
                "directive:DIRECTIVE_010",
                "directive:DIRECTIVE_024",
                "directive:DIRECTIVE_025",
                "directive:DIRECTIVE_028",
                "directive:DIRECTIVE_029",
                "directive:DIRECTIVE_030",
                "directive:DIRECTIVE_034",
                "directive:DIRECTIVE_037",
                "tactic:acceptance-test-first",
                "tactic:usage-examples-sync",
                "tactic:quality-gate-verification",
                "tactic:review-intent-and-risk-first",
                "tactic:stopping-conditions",
            }),
        ),
        (
            ("erp-custom", "action:software-dev/implement"),
            frozenset({
                "directive:DIRECTIVE_024",
                "directive:DIRECTIVE_025",
                "directive:DIRECTIVE_028",
                "directive:DIRECTIVE_029",
                "directive:DIRECTIVE_030",
                "directive:DIRECTIVE_034",
                "tactic:acceptance-test-first",
                "tactic:autonomous-operation-protocol",
                "tactic:change-apply-smallest-viable-diff",
                "tactic:quality-gate-verification",
                "tactic:stopping-conditions",
                "tactic:tdd-red-green-refactor",
                "toolguide:efficient-local-tooling",
            }),
        ),
    ],
)
def test_required_scope_membership_is_byte_stable(
    key: tuple[str, str], expected: frozenset[str]
) -> None:
    """Constant-backed frozensets equal the exact URN literals they replaced."""
    assert _REQUIRED_SCOPE[key] == expected


# ---------------------------------------------------------------------------
# Unit tests: CalibrationFinding shape
# ---------------------------------------------------------------------------


def test_finding_has_required_fields() -> None:
    findings = walk_mission(mission_key="software-dev", repo_root=_REPO_ROOT)
    for f in findings:
        assert isinstance(f, CalibrationFinding)
        assert isinstance(f.step_id, str)
        assert f.action_id.startswith("action:")
        assert f.profile_id.startswith("agent_profile:")
        assert isinstance(f.resolved_scope, frozenset)
        assert isinstance(f.required_scope, frozenset)
        assert isinstance(f.known_irrelevant, frozenset)
        assert isinstance(f.recommended_edge_changes, list)


def test_resolved_scope_is_superset_of_required() -> None:
    """resolved_scope must contain all required_scope URNs (half-1 check)."""
    for mission_key in ["software-dev", "research", "documentation", "erp-custom"]:
        findings = walk_mission(mission_key=mission_key, repo_root=_REPO_ROOT)
        for f in findings:
            assert f.required_scope.issubset(f.resolved_scope), (
                f"{mission_key}/{f.step_id}: required URNs not in resolved_scope: "
                f"{f.required_scope - f.resolved_scope}"
            )


def test_no_recommended_changes_when_all_pass() -> None:
    """When the inequality holds, recommended_edge_changes is empty."""
    for mission_key in ["software-dev", "research", "documentation", "erp-custom"]:
        findings = walk_mission(mission_key=mission_key, repo_root=_REPO_ROOT)
        for f in findings:
            if f.inequality.holds:
                assert f.recommended_edge_changes == [], (
                    f"{mission_key}/{f.step_id}: unexpected edge changes: "
                    f"{f.recommended_edge_changes}"
                )


# ---------------------------------------------------------------------------
# Unit tests: overlay loading
# ---------------------------------------------------------------------------


def test_overlay_loading_does_not_break_when_file_absent(tmp_path: Path) -> None:
    """Walker works when no overlay file exists for the mission."""
    # tmp_path has no graph source; seed it from the repo's shipped built-in DRG
    # via the seam so the walker can resolve a real graph from repo_root=tmp_path.
    src_dir = tmp_path / "src" / "charter" / "offering"
    src_dir.mkdir(parents=True)
    _copy_built_in_graph_source(src_dir)

    # No .kittify/charter-packs/overlays/ directory → should not raise
    findings = walk_mission(mission_key="software-dev", repo_root=tmp_path)
    assert len(findings) == 6


def test_overlay_add_edge_extends_resolved_scope(tmp_path: Path) -> None:
    """An overlay add_edge increases the resolved scope for the targeted action."""
    src_dir = tmp_path / "src" / "charter" / "offering"
    src_dir.mkdir(parents=True)
    _copy_built_in_graph_source(src_dir)

    overlays_dir = tmp_path / ".kittify" / "charter-packs" / "overlays"
    overlays_dir.mkdir(parents=True)

    # Add a scope edge from software-dev/specify to a tactic that is not yet scoped
    overlay_yaml = overlays_dir / "calibration-software-dev.yaml"
    overlay_yaml.write_text(
        "add_edge:\n"
        "  - source: action:software-dev/specify\n"
        "    target: tactic:adr-drafting-workflow\n"
        "    relation: scope\n"
        "    reason: test overlay\n",
        encoding="utf-8",
    )

    findings = walk_mission(mission_key="software-dev", repo_root=tmp_path)
    specify_finding = next(f for f in findings if f.step_id == "specify")
    # adr-drafting-workflow should be in the resolved scope after overlay
    assert "tactic:adr-drafting-workflow" in specify_finding.resolved_scope


# ---------------------------------------------------------------------------
# Unit tests: unknown mission key
# ---------------------------------------------------------------------------


def test_unknown_mission_key_raises() -> None:
    with pytest.raises(KeyError):
        walk_mission(mission_key="no-such-mission", repo_root=_REPO_ROOT)


# ---------------------------------------------------------------------------
# Unit tests: EdgeChange model
# ---------------------------------------------------------------------------


def test_edge_change_immutable() -> None:
    ec = EdgeChange(kind="add_edge", source="action:a/b", target="tactic:X", relation="scope")
    assert ec.kind == "add_edge"
    assert ec.new_target is None
