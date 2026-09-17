"""Marker->job completeness invariant (FR-001, mission ci-suite-map-bind WP04).

Every marker registered in ``pytest.ini`` must occupy exactly one of three CI
states, so the documented authoring-default marker (``unit``) — and every other
registered marker — can never be silently CI-invisible (#2034 root cause):

  (i)   ROUTED-BY-MARKER  — positively referenced (negation-aware token walk via
        pytest's own ``Expression``) by >=1 gate's ``-m`` expression across the
        four suite-running workflows. Verified collection-free.
  (ii)  ROUTED-BY-PATH    — every collected test carrying the marker is selected
        by >=1 gate. VERIFIED against the ``_gate_coverage`` orphan model (a
        marker with even one orphan carrier is NOT routed-by-path).
  (iii) CI_INVISIBLE       — a reasoned allowlist entry for a genuinely-unrun
        marker (zero collected carriers). Every entry carries a non-empty reason
        (C-003) and must be REGISTERED (reverse containment).

``unit`` and ``contract`` are HARD-ASSERTED ROUTED-BY-MARKER: ineligible for
(ii) and (iii). The allowlist path is written so it can never absorb them
(renata MEDIUM-3 — otherwise the ledger could hide the exact hole the mission
closes).

Honest three-state split (re-derived live at implement, 2026-07-04, NFR-004;
37 registered markers; `_gate_coverage.load_gates()` + `collect_universe()`):

  ROUTED-BY-MARKER (12): architectural, contract, fast, git_repo, integration,
      quarantine, regression, slow, stress, timing, unit, windows_ci
      (`stress` is routed by the ci-nightly `-m "stress and not windows_ci"`
      lane — the concurrency/load suite is deselected from the per-PR AND full
      module-tests slices, so the nightly is its sole home, mirroring how
      `performance`/`e2e` are nightly-only.)
      (`quarantine` is routed by the NON-BLOCKING `quarantine-visibility` gate —
      the spec's documented edge case: a job selects it, so it is ROUTED;
      blocking-ness is a separate axis. Its held-out population is governed by
      #2295/#2309 (17) + #2342 (`test_200_missions_under_5s`) and is never
      hard-pinned here. `regression` is routed by marker to the `-m regression`
      gate `regression-tests`, which — unlike `quarantine-visibility` — is
      BLOCKING (a member of `quality-gate.needs`): a red-first P0 reproduction
      is expected to red mainline and, because CI is the release authority, must
      gate releases; a non-blocking regression lane would fake green on P0s
      (#2772-family course-correction of the #2774 visibility-only design). Its
      orphan carriers by path — e.g. `tests/delivery/` reaches no path gate —
      make an explicit `-m regression` job their required CI home rather than a
      silent CI_INVISIBLE entry.)
  ROUTED-BY-PATH (12): adversarial, agent, asyncio, distribution, doctrine,
      e2e, no_git_tmp_path, no_readiness_stub, non_sandbox,
      requires_symlinks, timeout, upgrade
      (each has >=1 collected carrier and ZERO orphan carriers — verified via
      the orphan model; NOT hand-asserted. The spec's illustrative
      `non_sandbox`/`timeout`/`asyncio` invisible-guesses were
      SUPERSEDED by this live derivation: their carriers all reach a path gate,
      so they are routed-by-path, not invisible — shrink-preferred, C-003.)
  CI_INVISIBLE (13): the ``CI_INVISIBLE`` ledger below — markers with ZERO
      collected carriers today (reserved/opt-out markers no gate selects).

The name-level completeness here is complementary to the set-level orphan
route oracle (``test_ci_collection_completeness.py``): that pins every test's marker SET reaches a
gate; this pins every registered marker NAME has a routing home (Decision 4).

The interim convergence topology restores only the ``windows_ci`` marker gate.
The live routing check below re-opens that subset; the former multi-marker
routing ledger remains retired with the deferred suite-topology workflows.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.architectural import _gate_coverage as gc
from tests.architectural._workflow_fixtures import write_workflow

if TYPE_CHECKING:
    from typing import Any

pytestmark = pytest.mark.architectural

_ROUTE_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/test-sanitation/assertive-test-suite-sanitation-01KZME3P/raw/"
    "wp07-route-manifest.yaml"
)

# ``unit``/``contract`` are the authoring-taxonomy defaults the mission routes;
# they are structurally ineligible for any routing exemption.
INELIGIBLE_FOR_EXEMPTION = frozenset({"unit", "contract"})

_ORCH_REASON = (
    "Orchestrator agent-contract marker; no gate selects `-m orchestrator_*` "
    "and zero collected tests currently carry it."
)

# Reasoned allowlist (state iii): markers with ZERO collected carriers today, so
# no test runs under them and no gate need select them. Each reason states the
# empirical basis (zero carriers) and WHY the marker exists. Additions are LOUD
# (this test names an unrouted marker); removals silent (C-003 shrink-only).
CI_INVISIBLE: dict[str, str] = {
    "flaky": (
        "Mutation/forking instability debt marker retained in the taxonomy; "
        "the sanitation census removed its final carrier, so zero collected "
        "tests currently carry it."
    ),
    "platform_darwin": (
        "macOS-only tests; no suite-running workflow configures a macOS runner "
        "and no collected test carries the marker (reserved OS marker)."
    ),
    "platform_linux": (
        "Linux-only OS marker; no gate selects `-m platform_linux` and zero "
        "collected tests carry it (reserved)."
    ),
    "live_adapter": (
        "Calls the real Anthropic API; every suite deselects it via "
        "`-m 'not live_adapter'` and no collected test carries it."
    ),
    "exploratory": (
        "Human-driven exploratory tests explicitly opted out of CI (pytest.ini "
        "documents `-m 'not exploratory'`); zero collected carriers."
    ),
    "core_agent": (
        "Core-tier agent availability gate (fails if the agent is absent); no "
        "CI job selects `-m core_agent` and zero collected tests carry it."
    ),
    "extended_agent": (
        "Extended-tier agent gate (skips if unavailable); no CI job selects it "
        "and zero collected tests carry it."
    ),
    "orchestrator_availability": _ORCH_REASON,
    "orchestrator_fixtures": _ORCH_REASON,
    "orchestrator_happy_path": _ORCH_REASON,
    "orchestrator_parallel": _ORCH_REASON,
    "orchestrator_review_cycles": _ORCH_REASON,
    "orchestrator_smoke": _ORCH_REASON,
}


# ---------------------------------------------------------------------------
# Pure classifier primitives (collection-free; the fault-injection substrate).
# ---------------------------------------------------------------------------


def structural_marker_violations(
    *,
    registered: set[str],
    routed_by_marker: set[str],
    ci_invisible: dict[str, str],
) -> list[str]:
    """Collection-free state rules: containment, reasons, ineligibility, overlap.

    Returns human-readable violation strings; ``[]`` == healthy. These are the
    NFR-001 sub-second checks — no test collection required.
    """
    inv = set(ci_invisible)
    out: list[str] = []
    out += [
        f"CI_INVISIBLE marker {m!r} is not registered in pytest.ini "
        "(reverse-containment: a marker deleted from the registry but left in "
        "the ledger must red)"
        for m in sorted(inv - registered)
    ]
    out += [
        f"CI_INVISIBLE marker {m!r} has an empty reason (C-003 shrink-only "
        "ledgers require a per-entry reason)"
        for m in sorted(inv)
        if not (ci_invisible.get(m) or "").strip()
    ]
    for m in sorted(INELIGIBLE_FOR_EXEMPTION):
        if m in inv:
            out.append(
                f"{m!r} is INELIGIBLE for CI_INVISIBLE — the authoring-default "
                "marker must be positively selected by a real gate, never "
                "exempted (renata MEDIUM-3)"
            )
        if m not in routed_by_marker:
            out.append(
                f"{m!r} MUST be ROUTED-BY-MARKER — a gate's `-m` must positively "
                "select it (the #2034 core guarantee); it currently is not"
            )
    out += [
        f"{m!r} is both ROUTED-BY-MARKER and CI_INVISIBLE — pick exactly one state"
        for m in sorted(routed_by_marker & inv)
    ]
    return out


def reachability_marker_violations(
    *,
    registered: set[str],
    routed_by_marker: set[str],
    ci_invisible: set[str],
    reachable_by_path: set[str],
) -> list[str]:
    """Completeness + anti-dumping rules (require the orphan-model reachability).

    ``reachable_by_path`` = markers with >=1 collected carrier where EVERY
    carrier reaches a gate. Zero-carrier markers are NOT in this set (so they
    are forced into a reasoned CI_INVISIBLE home rather than silently passing).
    """
    out: list[str] = []
    for m in sorted(registered):
        if m in routed_by_marker or m in ci_invisible or m in reachable_by_path:
            continue
        out.append(
            f"marker {m!r} has NO CI home: not routed-by-marker, not "
            "verified-routed-by-path (its carriers do not all reach a gate, or "
            "it has none), and not in the reasoned CI_INVISIBLE ledger"
        )
    out += [
        f"marker {m!r} is CI_INVISIBLE but has collected carriers that reach a "
        "gate — it is actually ROUTED-BY-PATH (C-003 dumping-ground: an unrun "
        "label must not cover running tests)"
        for m in sorted(ci_invisible & reachable_by_path)
    ]
    return out


def _all_marker_names(marker_expr: str) -> set[str]:
    tree = ast.parse(marker_expr, mode="eval")
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def negated_marker_tokens(marker_expr: str) -> frozenset[str]:
    """Names referenced under an ODD number of ``not`` operators (the excluded set)."""
    return frozenset(_all_marker_names(marker_expr) - gc.positive_marker_tokens(marker_expr))


# ---------------------------------------------------------------------------
# Live collection-free checks (NFR-001: sub-second, no pytest collection).
# ---------------------------------------------------------------------------


def _live_registered() -> set[str]:
    return set(gc.registered_markers())


def test_restored_windows_ci_marker_is_routed_live() -> None:
    """The restored direct suite runner positively selects ``windows_ci``.

    The ci-pipeline-reinstatement mission reinstated the modular test CI, so the
    routed-marker set is no longer *only* ``windows_ci`` — the module matrix and
    nightly workflows also positively route tier markers (``fast``/``unit``/
    ``e2e``/``performance``). Assert ``windows_ci`` is *among* the routed markers
    (a superset check) rather than pinning the exact set, which would be a brittle
    shape guard the mission's own P2 directive discourages.
    """
    assert "windows_ci" in gc.routed_marker_names(gc.load_gates())


def test_ci_invisible_keys_are_registered_live() -> None:
    """Reverse containment on live data: no stale ledger entry."""
    assert set(CI_INVISIBLE) <= _live_registered()


def test_wp07_changed_classes_have_one_owner_and_only_secondary_overlap() -> None:
    """Route role is explicit: one owner; every overlap is a secondary role."""
    manifest: dict[str, Any] = yaml.safe_load(_ROUTE_MANIFEST.read_text(encoding="utf-8"))
    routes = {route["route_id"]: route for route in manifest["routes"]}
    secondary_roles = {"coverage", "platform", "hard_gate"}
    for class_id, changed_class in manifest["changed_classes"].items():
        owner = routes[changed_class["owner_route"]]
        assert owner["role"] == "owner", f"{class_id} owner is not role=owner"
        for route_id in changed_class["secondary_routes"]:
            assert routes[route_id]["role"] in secondary_roles, (
                f"{class_id} overlap {route_id} is not an explicit secondary role"
            )


def test_negated_marker_tokens_is_sign_aware() -> None:
    """Unit-level guard for the excluded-set extractor backing the ⊇ check."""
    assert negated_marker_tokens("(unit or contract) and not (fast or slow)") == frozenset(
        {"fast", "slow"}
    )
    assert negated_marker_tokens("not not fast") == frozenset()


# ---------------------------------------------------------------------------
# Grammar-divergence guard (renata residual: _gate_coverage.py:321-326).
# ---------------------------------------------------------------------------


def test_positive_marker_tokens_grammar_divergence_guard() -> None:
    """An expr pytest accepts but stdlib ast rejects raises the loud guard.

    ``1foo`` compiles under pytest's own ``Expression`` grammar (a superset) but
    is a ``SyntaxError`` under ``ast.parse`` — exercising the previously-untested
    RuntimeError branch that demands the sign walker be extended before its
    output is trusted.
    """
    with pytest.raises(RuntimeError, match="not under stdlib ast"):
        gc.positive_marker_tokens("1foo")


# ---------------------------------------------------------------------------
# MANDATORY fault-injection (T011 DoD) — all collection-free (pure classifier).
# ---------------------------------------------------------------------------


def test_faultinjection_derouted_unit_reds(tmp_path: Path) -> None:
    """(b) A fixture gate set WITHOUT the unit-selecting residual reds on ``unit``."""
    # A residual job dropped from the gate set: `unit` is no longer positively
    # selected by any gate. Built from a real parsed workflow (not a hand set).
    wf = write_workflow(
        tmp_path,
        """\
        name: fixture
        on: pull_request
        jobs:
          residual-without-unit:
            runs-on: ubuntu-latest
            steps:
              - run: uv run pytest tests/ -m "contract and not fast"
        """,
    )
    routed = set(gc.routed_marker_names(gc.parse_workflow(wf)))
    assert "unit" not in routed  # the fixture de-routed it

    violations = structural_marker_violations(
        registered=_live_registered(),
        routed_by_marker=routed,
        ci_invisible=CI_INVISIBLE,
    )
    assert any("'unit'" in v and "ROUTED-BY-MARKER" in v for v in violations), violations


def test_faultinjection_residual_missing_routed_marker_reds() -> None:
    """A residual expression that forgets to negate a routed marker reds (⊇ arm)."""
    # `fast` is routed-by-marker but this residual fails to exclude it.
    expr = "(unit or contract) and not (integration or git_repo)"
    negated = negated_marker_tokens(expr)
    runnable = {"fast", "integration", "git_repo"}
    missing = runnable - negated
    assert missing == {"fast"}, missing

