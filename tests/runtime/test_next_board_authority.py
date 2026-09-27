"""Board-authority acceptance tests for ``runtime_bridge`` (#4980 / #4975).

Holds the P0 board-authority parity tests (review-reject re-dispatch, coord
implement dispatch, the blocked floor, snapshot immutability and the
single-authority negative guard) plus the two composed-guard fail-closed
direct-call tests. They drive the REAL engine against real on-disk mission
scaffolds (``tests/runtime/_next_mission_scaffold.py``) and never touch the
#2531 two-run parity oracle (``tests/runtime/test_bridge_parity.py`` /
``tests/runtime/_bridge_oracle.py``), so the oracle stays retirable in
isolation (#5116) and these tests never pay for its module-scoped
``ledger_results`` fixture.

The guard tests at the top of this module keep that independence
non-fakeable: they scan this module and the scaffold for any oracle import or
wide-scoped fixture, pin the expected test-function names, and confirm via
``pytest --setup-plan`` that ``ledger_results`` is never set up.
"""

from __future__ import annotations

import ast
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from mission_runtime import MissionTopology as _MissionTopology
from runtime.next.decision import DecisionKind
from tests.integration.test_placement_partition_golden_path import (
    _create_mission as _golden_create_mission,
    _init_git_repo as _golden_init_git_repo,
)
from tests.runtime._next_mission_scaffold import (
    advance_to_step,
    reject_wp_on_status_surface,
    scaffold_coord_software_dev,
    scaffold_software_dev,
    seed_wp_lane,
    write_wp_task_files,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Oracle-independence guard (FR-017 / NFR-002 / US3-AS3)
# ---------------------------------------------------------------------------

_THIS_MODULE = Path(__file__).resolve()
_SCAFFOLD_MODULE = _THIS_MODULE.parent / "_next_mission_scaffold.py"
_REPO_ROOT = _THIS_MODULE.parents[2]

_ORACLE_MODULES: frozenset[str] = frozenset({"tests.runtime._bridge_oracle", "tests.runtime.test_bridge_parity"})
_ORACLE_SUBMODULE_NAMES: frozenset[str] = frozenset({"_bridge_oracle", "test_bridge_parity"})
_WIDE_FIXTURE_SCOPES: frozenset[str] = frozenset({"module", "package", "session"})
_ORACLE_FIXTURE_NAME = "ledger_results"

_GUARD_TESTS: frozenset[str] = frozenset(
    {
        "test_board_authority_module_does_not_import_the_oracle",
        "test_oracle_coupling_scan_flags_planted_imports",
        "test_board_authority_tests_never_set_up_the_oracle_fixture",
    }
)

# Hard-coded from the planning-base capture of tests/runtime/test_bridge_parity.py
# (3717c7ea): the 13 P0 board-authority functions + the 2 fail-closed
# direct-call functions. A name set, not a count, so dropping a moved test
# cannot be masked by the guard tests themselves.
_EXPECTED_BOARD_AUTHORITY_TESTS: frozenset[str] = frozenset(
    {
        "test_research_fail_closed_default_direct_call",
        "test_documentation_fail_closed_default_direct_call",
        "test_review_reject_redispatches_implement_single_branch",
        "test_coord_implement_dispatch_reaches_wp01",
        "test_review_reject_redispatches_implement_coord_family",
        "test_lanes_with_coord_implement_dispatch",
        "test_approve_control_unchanged",
        "test_early_reject_redispatches_implement",
        "test_multi_wp_dependency_order_reject_redispatch",
        "test_blocked_floor_all_in_review_has_named_recovery",
        "test_blocked_floor_no_actionable_wp_has_named_recovery",
        "test_blocked_floor_dependency_walled_has_named_recovery",
        "test_unmaterialized_coord_surfaces_typed_blocked_reason",
        "test_deleted_coord_branch_surfaces_flatten_blocked_reason",
        "test_snapshot_byte_identical_across_redispatch",
        "test_no_advancing_path_emits_unauthorized_step",
    }
)
# 16 functions; ``test_review_reject_redispatches_implement_coord_family`` is
# parametrized x2, giving 17 collected nodes. (#5166 added
# ``test_deleted_coord_branch_surfaces_flatten_blocked_reason``, re-homed here
# from the retired ``test_bridge_parity`` location #5104 split.)
_EXPECTED_BOARD_AUTHORITY_NODES = 17


def _is_oracle_module(module: str) -> bool:
    return module in _ORACLE_MODULES


def _import_offenders(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [f"line {node.lineno}: import {alias.name}" for alias in node.names if _is_oracle_module(alias.name)]
    module = node.module or ""
    if _is_oracle_module(module):
        return [f"line {node.lineno}: from {module} import ..."]
    if module == "tests.runtime":
        return [f"line {node.lineno}: from tests.runtime import {alias.name}" for alias in node.names if alias.name in _ORACLE_SUBMODULE_NAMES]
    return []


def _fixture_scope(decorator: ast.expr) -> str | None:
    """Return the literal ``scope=`` of a ``pytest.fixture(...)`` decorator, if any."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    is_fixture = (isinstance(func, ast.Attribute) and func.attr == "fixture") or (isinstance(func, ast.Name) and func.id == "fixture")
    if not is_fixture:
        return None
    for keyword in decorator.keywords:
        if keyword.arg == "scope" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _wide_fixture_offenders(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    offenders: list[str] = []
    for decorator in node.decorator_list:
        scope = _fixture_scope(decorator)
        if scope in _WIDE_FIXTURE_SCOPES:
            offenders.append(f"line {node.lineno}: {scope}-scoped fixture {node.name}")
    return offenders


def _oracle_coupling_offenders(source: str) -> list[str]:
    """Flag every coupling to the parity oracle in ``source``.

    Flags any ``import`` / ``from`` of ``tests.runtime._bridge_oracle`` or
    ``tests.runtime.test_bridge_parity`` (at any nesting depth, including
    function-local imports) and any fixture declared with
    ``scope="module"`` / ``"package"`` / ``"session"`` (the oracle's
    ``ledger_results`` shape).
    """
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import | ast.ImportFrom):
            offenders.extend(_import_offenders(node))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            offenders.extend(_wide_fixture_offenders(node))
    return offenders


def _top_level_test_names(source: str) -> set[str]:
    return {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")}


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_board_authority_module_does_not_import_the_oracle() -> None:
    """The board-authority tests and their scaffold never couple to the oracle,
    and every expected board-authority test function lives here (by name)."""
    module_source = _THIS_MODULE.read_text(encoding="utf-8")
    scaffold_source = _read_optional(_SCAFFOLD_MODULE)

    assert _oracle_coupling_offenders(module_source) == []
    assert _oracle_coupling_offenders(scaffold_source) == []

    moved = _top_level_test_names(module_source) - _GUARD_TESTS
    missing = sorted(_EXPECTED_BOARD_AUTHORITY_TESTS - moved)
    unexpected = sorted(moved - _EXPECTED_BOARD_AUTHORITY_TESTS)
    assert not missing, f"expected board-authority tests missing from this module: {missing}"
    assert not unexpected, f"unexpected non-guard tests in this module: {unexpected}"


def test_oracle_coupling_scan_flags_planted_imports() -> None:
    """Self-mutation: the same scanner the guard uses flags each planted coupling."""
    planted = {
        "from-oracle": "from tests.runtime._bridge_oracle import canonical\n",
        "import-parity": "import tests.runtime.test_bridge_parity\n",
        "from-package": "from tests.runtime import _bridge_oracle\n",
        "local-import": "def f() -> None:\n    from tests.runtime.test_bridge_parity import ledger_results\n",
        "module-fixture": ("import pytest\n\n\n@pytest.fixture(scope='module')\ndef heavy() -> int:\n    return 1\n"),
        "session-fixture": ("from pytest import fixture\n\n\n@fixture(scope='session')\ndef heavy() -> int:\n    return 1\n"),
    }
    for label, source in planted.items():
        assert _oracle_coupling_offenders(source), f"planted coupling not flagged: {label}"

    clean = "import pytest\nfrom tests.runtime._next_mission_scaffold import scaffold_software_dev\n\n\n@pytest.fixture\ndef light() -> int:\n    return 1\n"
    assert _oracle_coupling_offenders(clean) == []


_PLANNED_NODE_RE = re.compile(r"::(test_\w+)(\[[^\]]*\])?")


def test_board_authority_tests_never_set_up_the_oracle_fixture() -> None:
    """US3-AS3: ``--setup-plan`` (executes nothing) never plans ``ledger_results``
    for this module, and plans every moved board-authority node."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--setup-plan",
            "-q",
            "-p",
            "no:cacheprovider",
            str(_THIS_MODULE.relative_to(_REPO_ROOT)),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output

    assert _ORACLE_FIXTURE_NAME not in output
    planned = {
        match.group(1) + (match.group(2) or "") for line in output.splitlines() if (match := _PLANNED_NODE_RE.search(line)) and match.group(1) not in _GUARD_TESTS
    }
    assert len(planned) >= _EXPECTED_BOARD_AUTHORITY_NODES, f"expected >= {_EXPECTED_BOARD_AUTHORITY_NODES} board-authority nodes planned, got {sorted(planned)}"


# ---------------------------------------------------------------------------
# Direct-call regression coverage for the two composed-guard fail-closed
# defaults. NOT counted toward the entry-driven coverage floor above -- see
# test_coverage_floor_is_met's docstring and the WP01 completion report for
# why these are not reachable from their owning public entry with a valid
# charter-resolved action_sequence. Mirrors the existing proven pattern in
# tests/integration/test_research_runtime_walk.py::
# test_unknown_research_action_fails_closed.
# ---------------------------------------------------------------------------


def test_research_fail_closed_default_direct_call(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import _check_composed_action_guard

    feature_dir = tmp_path / "kitty-specs" / "research-fail-closed"
    feature_dir.mkdir(parents=True)
    failures = _check_composed_action_guard("totally-unknown-action", feature_dir, mission="research")
    assert failures == ["No guard registered for research action: totally-unknown-action"]


def test_documentation_fail_closed_default_direct_call(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import _check_composed_action_guard

    feature_dir = tmp_path / "kitty-specs" / "documentation-fail-closed"
    feature_dir.mkdir(parents=True)
    failures = _check_composed_action_guard("totally-unknown-action", feature_dir, mission="documentation")
    assert failures == ["No guard registered for documentation action: totally-unknown-action"]


# ===========================================================================
# advancing-next-board-unification-01M3BGQ0 -- T001-T003: board-authority
# parity for review-reject re-dispatch (#4980) and coord implement dispatch
# (#4975). Contract: kitty-specs/advancing-next-board-unification-01M3BGQ0/
# contracts/advance-query-parity.md (CT-1..CT-7).
# ===========================================================================


def test_review_reject_redispatches_implement_single_branch(tmp_path: Path) -> None:
    """#4980 (T001, CT-2): a WP rejected to ``planned`` while the run is
    issued on ``review`` (single_branch) MUST re-dispatch ``implement WP01``,
    exit 0, equal to query mode -- never the WP-less ``action=review,
    wp_id=null`` composition placeholder (the placeholder-spin bug).

    Pre-fix this was RED: ``_state_to_action("review", ...)`` finds no
    ``for_review`` WP (it was just rejected to ``planned``) and falls
    through to generic ``review.md`` template resolution, returning
    ``action="review", wp_id=None`` -- a *non-None* action, so
    ``_build_wp_iteration_decision``'s ``action is None`` blocked check never
    fires and the WP-less composed placeholder is emitted instead (see
    ``research.md`` Decision 2)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-reject-sb"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert (advance_decision.action, advance_decision.wp_id) == (
        query_decision.mission_state,
        query_decision.wp_id,
    ), "advance and query must agree on the actionable step/WP (CT-1)"
    assert not (advance_decision.action == "review" and advance_decision.wp_id is None), "must never re-emit the WP-less review composition placeholder (FR-005)"


def test_coord_implement_dispatch_reaches_wp01(tmp_path: Path) -> None:
    """#4975 (T002, CT-3): on the default ``coord`` topology, a WP ready in
    ``planned`` MUST dispatch ``implement WP01``, exit 0 -- never
    ``kind=blocked reason="No action mapped for WP step 'implement'"``.

    Pre-fix this was RED: ``_state_to_action("implement", mission_slug,
    feature_dir, ...)`` calls ``preview_claimable_wp(feature_dir)`` with NO
    ``status_dir`` and ``feature_dir`` (the coord-aware runtime feature dir)
    carries no ``tasks/`` under coord topology (a PRIMARY-partition
    artifact) -- ``preview_claimable_wp`` sees no WP files at all and
    returns ``wp_id=None``, cascading to the generic 'No action mapped'
    blocked decision."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-implement"
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(repo, mission_slug, _MissionTopology.COORD, wps={"WP01": "planned"})
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert query_decision.wp_id == "WP01"  # absolute anchor on the query side
    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert advance_decision.reason != "No action mapped for WP step 'implement'"


@pytest.mark.parametrize("topology", [_MissionTopology.COORD, _MissionTopology.LANES_WITH_COORD])
def test_review_reject_redispatches_implement_coord_family(tmp_path: Path, topology: _MissionTopology) -> None:
    """US3 (combined cell): review-reject re-dispatch on ``coord`` AND
    ``lanes_with_coord`` simultaneously -- the load-bearing proof the two
    #4980/#4975 faces are unified at ONE authority, not separately patched
    (a branch-by-branch fix could pass the single_branch review test AND the
    coord implement test while still diverging on exactly this combined
    cell -- the #4860 near-miss shape)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = f"coord-anbu-reject-{topology.value.replace('_', '-')}"
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(repo, mission_slug, topology, wps={"WP01": "for_review"})
    advance_to_step(repo, mission_slug, "software-dev", "review")
    reject_wp_on_status_surface(coord_mission_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert (advance_decision.action, advance_decision.wp_id) == (
        query_decision.mission_state,
        query_decision.wp_id,
    )


def test_lanes_with_coord_implement_dispatch(tmp_path: Path) -> None:
    """CT-3 absolute anchor on the second coord-family topology, whose lane
    model differs from plain ``coord``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-lwc-implement"
    scaffold_coord_software_dev(repo, mission_slug, _MissionTopology.LANES_WITH_COORD, wps={"WP01": "planned"})
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"


def test_approve_control_unchanged(tmp_path: Path) -> None:
    """US1 S4: the approve control is unchanged -- approving the reviewed WP
    still advances past ``review`` (``kind=step action=accept``), never
    re-dispatching an already-approved WP."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-approve"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id="approve-WP01",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-02T00:00:00+00:00",
            actor="reviewer-fixture",
            force=True,
            execution_mode="worktree",
        ),
    )

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "accept"


def test_early_reject_redispatches_implement(tmp_path: Path) -> None:
    """Edge case: a reject issued while the run is still on ``implement``
    (before hand-off ever reached ``review``) MUST continue to re-dispatch
    ``implement WP01`` unchanged (FR-006)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-early-reject"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "planned"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"


def test_multi_wp_dependency_order_reject_redispatch(tmp_path: Path) -> None:
    """US1 S5: WP01 (no deps) rejected mid-mission back to ``planned`` while
    WP02 (depends on WP01) is dependency-gated -- advance MUST re-dispatch
    exactly ``implement WP01``; WP02's dependency order stays undisturbed
    (never surfaced as claimable ahead of its unmet dependency)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-multi-wp"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks" / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ndependencies: [WP01]\ntitle: WP02 depends on WP01\n"
        "role: implementer\nrequirement_refs: [FR-001]\n---\n"
        "## Work Package WP02: depends on WP01\n\n### Requirements\n- FR-001\n\nDo it.\n",
        encoding="utf-8",
    )
    seed_wp_lane(feature_dir, mission_slug, "WP02", "planned")
    advance_to_step(repo, mission_slug, "software-dev", "review")
    reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.discovery import preview_claimable_wp
    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    query_decision = query_current_state("pedro", mission_slug, repo)
    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.step
    assert advance_decision.action == "implement"
    assert advance_decision.wp_id == "WP01"
    assert query_decision.wp_id == "WP01"
    # WP02 stays dependency-gated -- the claimable-WP authority still refuses
    # it, dependency order undisturbed.
    wp02_preview = preview_claimable_wp(feature_dir)
    assert wp02_preview.wp_id == "WP01", "WP02 must not become claimable ahead of its unmet dependency"


def test_blocked_floor_all_in_review_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S2: every WP ``in_review`` (claimed by another reviewer)
    MUST be ``kind=blocked``, exit 1, with a runnable named recovery
    command -- never a silent no-op."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-all-in-review"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "in_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    assert advance_decision.wp_id is None
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_blocked_floor_no_actionable_wp_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S1: a board with no actionable WP for the issued step
    (e.g. the only WP is ``blocked``) MUST be ``kind=blocked``, exit 1, with
    a runnable named recovery command -- never the WP-less composed
    placeholder."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-no-actionable"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "blocked"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    assert advance_decision.wp_id is None
    assert not (advance_decision.action == "review" and advance_decision.wp_id is None and advance_decision.kind == DecisionKind.step)
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_blocked_floor_dependency_walled_has_named_recovery(tmp_path: Path) -> None:
    """CT-4 / US4 S3: the only claimable-by-lane WP is dependency-gated by an
    un-approved dependency -- MUST be ``kind=blocked``, exit 1, with a
    runnable recovery command, never exit-0 ``kind=step``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-dep-walled"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "in_review"},
    )
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks" / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ndependencies: [WP01]\ntitle: WP02 depends on WP01\n"
        "role: implementer\nrequirement_refs: [FR-001]\n---\n"
        "## Work Package WP02: depends on WP01\n\n### Requirements\n- FR-001\n\nDo it.\n",
        encoding="utf-8",
    )
    seed_wp_lane(feature_dir, mission_slug, "WP02", "planned")
    advance_to_step(repo, mission_slug, "software-dev", "implement")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance_decision = decide_next_via_runtime("pedro", mission_slug, "success", repo)

    assert advance_decision.kind == DecisionKind.blocked
    _assert_reason_has_runnable_recovery_command(advance_decision.reason, mission_slug)


def test_unmaterialized_coord_surfaces_typed_blocked_reason(tmp_path: Path) -> None:
    """CT-5 / NFR-003: an unmaterialized coordination worktree MUST surface a
    blocked reason naming the unmaterialized surface -- NOT the generic
    ``no_actionable_wp`` floor, and never a fabricated empty-primary read
    (ADR 2026-09-24-2). Reuses the same ``_create_mission``-without-
    materializing shape as
    ``tests/mission_runtime/test_coord_read_seam.py::
    test_unmaterialized_coord_read_raises_instead_of_empty_primary``.

    Drives the selector (``_resolve_wp_board_action``) DIRECTLY rather than
    through ``decide_next_via_runtime``: bootstrap's own
    ``_wrap_with_decision_git_log`` (``DecisionGitLog`` construction) calls
    ``CoordinationWorkspace.resolve``, which materializes the coordination
    worktree as a side effect ("creating it on first call") BEFORE the
    dependency-gate phase ever reaches this selector -- so the unmaterialized
    state is not observable through the full advancing pipeline once
    bootstrap has run (a pre-existing property of ``_wrap_with_decision_git_
    log``, unrelated to and unchanged by this fix). The selector's own
    fail-closed behavior is independently correct and testable at its own
    seam, exactly as ``tests/next/test_finalized_task_routing.py``'s mapping-
    pin tests already exercise it directly."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-unmat"
    _golden_init_git_repo(repo)
    result = _golden_create_mission(repo, mission_slug, _MissionTopology.COORD)
    # deliberately never materialize the coord worktree (CoordState.UNMATERIALIZED)
    write_wp_task_files(result.feature_dir, {"WP01": "planned"})
    (result.feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "seed unmaterialized-coord fixture"],
        capture_output=True,
        check=True,
    )

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    board = _resolve_wp_board_action(mission_slug=result.mission_slug, repo_root=repo)

    assert board.action is None
    assert board.blocked_reason is not None
    assert "unmaterializ" in board.blocked_reason.lower(), f"blocked reason must name the unmaterialized coordination surface, got: {board.blocked_reason!r}"
    assert "no actionable" not in board.blocked_reason.lower(), "must NOT collapse into the generic no-actionable-wp floor (CT-5)"
    # #5113 / FR-014: the recovery command must actually materialize the
    # worktree (unlike the retired `doctor workspaces --fix`, #2240), and must
    # name the real mission slug rather than a `<mission>` placeholder. Per the
    # landing reconciliation with the already-merged #5113 WP07, `doctor
    # coordination --fix` is the primary remedy and `git worktree add` its
    # manual fallback.
    assert f"spec-kitty doctor coordination --mission {result.mission_slug} --fix" in board.blocked_reason


def test_deleted_coord_branch_surfaces_flatten_blocked_reason(tmp_path: Path) -> None:
    """#5113: the split ``CoordinationBranchDeleted`` except-arm in
    ``_resolve_wp_board_action`` must surface its OWN flatten-guidance
    ``next_step`` -- never the sibling ``CoordinationWorktreeUnmaterialized``
    arm's "Materialize it" text, since a deleted branch cannot be materialized
    (split from the former single ``except (Unmaterialized, Deleted)`` arm that
    gave both states the same "Materialize it" text)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "coord-anbu-deleted"
    _golden_init_git_repo(repo)
    result = _golden_create_mission(repo, mission_slug, _MissionTopology.COORD)
    write_wp_task_files(result.feature_dir, {"WP01": "planned"})
    (result.feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "seed deleted-coord-branch fixture"],
        capture_output=True,
        check=True,
    )
    # Delete the declared coordination branch entirely (no worktree, no
    # remote-tracking ref either) -- CoordState.DELETED, never UNMATERIALIZED.
    coord_branch = f"kitty/mission-{result.mission_slug}"
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-D", coord_branch],
        capture_output=True,
        check=True,
    )

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    board = _resolve_wp_board_action(mission_slug=result.mission_slug, repo_root=repo)

    assert board.action is None
    assert board.blocked_reason is not None
    assert "materialize it" not in board.blocked_reason.lower(), (
        f"a DELETED coord branch must NOT get the sibling unmaterialized arm's 'Materialize it' text -- got: {board.blocked_reason!r}"
    )
    assert "flatten" in board.blocked_reason.lower(), f"the deleted-branch arm must surface its own flatten-guidance next_step, got: {board.blocked_reason!r}"


def test_snapshot_byte_identical_across_redispatch(tmp_path: Path) -> None:
    """CT-6 / NFR-001: evaluating the re-dispatch decision performs no
    persisted run/engine-state write -- ``state.json`` and
    ``run.events.jsonl`` under the run dir are byte-identical before and
    after the call."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mission_slug = "042-anbu-snapshot"
    scaffold_software_dev(
        repo,
        mission_slug,
        with_spec=True,
        with_plan=True,
        with_tasks_md=True,
        wps={"WP01": "for_review"},
    )
    advance_to_step(repo, mission_slug, "software-dev", "review")
    feature_dir = repo / "kitty-specs" / mission_slug
    reject_wp_on_status_surface(feature_dir, mission_slug, "WP01")

    from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run

    run_ref = get_or_start_run(mission_slug, repo, "software-dev")
    run_dir = Path(run_ref.run_dir)
    state_path = run_dir / "state.json"
    events_path = run_dir / "run.events.jsonl"
    pre_state = state_path.read_bytes()
    pre_events = events_path.read_bytes() if events_path.exists() else b""

    decide_next_via_runtime("pedro", mission_slug, "success", repo)

    post_state = state_path.read_bytes()
    post_events = events_path.read_bytes() if events_path.exists() else b""
    assert post_state == pre_state, "re-dispatch must not write the run's state.json (NFR-001)"
    assert post_events == pre_events, "re-dispatch must not append run.events.jsonl (NFR-001)"


def test_no_advancing_path_emits_unauthorized_step(tmp_path: Path) -> None:
    """NFR-002 / CT-7 negative single-authority guard: every advancing
    WP-iteration ``(action, wp_id)`` this matrix produces is exactly what the
    board authority (``_resolve_wp_board_action``) independently derives for
    the same repo state -- no advancing path may emit a step/WP the board
    authority did not produce."""
    from runtime.next.runtime_bridge import _resolve_wp_board_action, decide_next_via_runtime

    cases: list[tuple[Path, str]] = []

    repo1 = tmp_path / "neg-implement"
    repo1.mkdir()
    mission1 = "042-anbu-neg-implement"
    scaffold_software_dev(repo1, mission1, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
    advance_to_step(repo1, mission1, "software-dev", "implement")
    cases.append((repo1, mission1))

    repo2 = tmp_path / "neg-reject"
    repo2.mkdir()
    mission2 = "042-anbu-neg-reject"
    scaffold_software_dev(repo2, mission2, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "for_review"})
    advance_to_step(repo2, mission2, "software-dev", "review")
    reject_wp_on_status_surface(repo2 / "kitty-specs" / mission2, mission2, "WP01")
    cases.append((repo2, mission2))

    repo3 = tmp_path / "neg-coord"
    repo3.mkdir()
    mission3 = "coord-anbu-neg"
    scaffold_coord_software_dev(repo3, mission3, _MissionTopology.COORD, wps={"WP01": "planned"})
    advance_to_step(repo3, mission3, "software-dev", "implement")
    cases.append((repo3, mission3))

    for repo_root, mission_slug in cases:
        decision = decide_next_via_runtime("pedro", mission_slug, "success", repo_root)
        board = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo_root)
        assert (decision.action, decision.wp_id) == (
            board.action,
            board.wp_id,
        ), f"{mission_slug}: advancing emitted {(decision.action, decision.wp_id)!r} but the board authority independently yields {(board.action, board.wp_id)!r}"


def _assert_reason_has_runnable_recovery_command(reason: str | None, mission_slug: str) -> None:
    """CT-4: the blocked reason must embed a runnable ``spec-kitty``
    invocation (parses as a command), not merely be non-empty."""
    assert reason, "blocked decision must carry a non-empty reason"
    match = re.search(r"`(spec-kitty [^`]+)`", reason)
    assert match is not None, f"reason has no backtick-delimited spec-kitty command: {reason!r}"
    command = match.group(1)
    tokens = shlex.split(command)
    assert tokens[0] == "spec-kitty", f"recovery command does not start with 'spec-kitty': {command!r}"
    assert len(tokens) >= 2, f"recovery command has no subcommand: {command!r}"
