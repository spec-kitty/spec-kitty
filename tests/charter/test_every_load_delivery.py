"""WP11 — governance is in force on *every* context load (FR-010, FR-012).

The defect these tests pin: activation reaches the boundary on the **first**
load and then evaporates. The second (steady-state) render fires a compact
early-return *before* the action-doctrine bundle is computed, so an agent that
reloads context mid-work package sees zero directives, zero tactics, zero
styleguides, zero toolguides — governance declared, not in force.

Four control-flow sites carry the bug (T060): the two ``build_charter_context``
returns (non-bootstrap action / depth-below-minimum) and the **two** in
``build_charter_context_json`` — the ``--json`` path is where the reproduction
is observed and where SC-001/002 are measured. A second, independent gate on
the same integer (``_EXTENDED_CONTEXT_DEPTH``) drops styleguides and toolguides
out of the *bootstrap* render entirely (T059): at the delivered depths (d=1,
d=2) the extended tier never renders.

SC-001/SC-002 are asserted through the **shipped** command surface
(``spec-kitty charter context``), not by calling ``build_charter_context``
directly — a test that supplies the grain itself proves nothing about the CLI
(T063, US3 scenario 9).

NFR-007 (T064) — steady-state render latency, measured on this branch (median
of 5, ``software-dev`` implement grain, this checkout):

    BEFORE (empty compact, pre-FR-010): ~1002 ms
    AFTER  (delivers the full bundle):  ~2052 ms   (~2.05x)

This matches the plan's recorded ~982 ms → ~1.94 s baseline. Per the operator
ruling 2026-07-28 the ~2x regression is **accepted, not gated**: this WP adds no
caching obligation (the memoization option is on record in the plan for a later
mission). The figures are recorded so a *later* regression is distinguishable
from this accepted one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures — a real-doctrine project copy, isolated so ``mark_loaded`` writes
# ``context-state.json`` into the tmp tree rather than polluting the checkout.
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


def _make_project(root: Path) -> Path:
    """Copy the checkout's activated charter into an isolated project at ``root``.

    The built-in doctrine graph ships in the installed package, so only the
    project-local activation surface (``.kittify/charter`` + ``config.yaml``)
    needs copying for the action bundle to resolve exactly as it does in the
    checkout.
    """
    src = _repo_root()
    dst_kittify = root / ".kittify"
    dst_kittify.mkdir()
    # ``context-state.json`` is gitignored ambient state recording prior
    # ``spec-kitty`` invocations in the source checkout; copying it would leak
    # the invoking developer's local load history into what every test in
    # this file expects to be a virgin (never-loaded) project.
    shutil.copytree(
        src / ".kittify" / "charter",
        dst_kittify / "charter",
        ignore=shutil.ignore_patterns("context-state.json"),
    )
    shutil.copy(src / ".kittify" / "config.yaml", dst_kittify / "config.yaml")
    # The checkout's own charter.yaml now carries the WP04 (C-A1)
    # ``mission_type_activations`` provisioning key (emitted by the charter
    # generation path — ``charter.activation.compiler.provision_mission_type_activations``),
    # so the COPY inherits it and ``PackContext.from_config`` resolves without a
    # fixture-side append. ``software-dev`` — the grain every test in this
    # module resolves — is one of the provisioned built-in mission types.
    subprocess.run(["git", "init", "--quiet", str(root)], check=False, capture_output=True)
    return root


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Every file path and its bytes under ``root`` (proves a shared tree stayed read-only)."""
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """A virgin project per test, for tests that load with ``mark_loaded=True`` (they write ``context-state.json``)."""
    yield _make_project(tmp_path)
    try:
        from charter.resolution import resolve_canonical_repo_root

        resolve_canonical_repo_root.cache_clear()
    except Exception:
        pass


@pytest.fixture(scope="module")
def shared_project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """One virgin project shared by the tests that never mark a load.

    They render with ``mark_loaded=False`` or through ``build_charter_context_json``
    and only read, so copying and re-resolving the project per test was pure
    cost. The snapshot taken up front is asserted unchanged at teardown to prove
    the shared tree stayed read-only (and the ``git init`` travels with it).
    """
    repo = _make_project(tmp_path_factory.mktemp("everyload"))
    before = _tree_snapshot(repo)
    yield repo
    assert _tree_snapshot(repo) == before, "a read-only test mutated the shared project"


# A directive, a styleguide and a toolguide known to be reachable at the
# implement grain for ``software-dev`` (present at both d=1 and d=2).
_DELIVERED_DIRECTIVE = "DIRECTIVE_001"
_DELIVERED_STYLEGUIDE = "python-conventions"
_DELIVERED_TOOLGUIDE = "efficient-local-tooling"


# ===========================================================================
# T065 / T060 (sites 1 & 2) — delivery on every load, text surface
# ===========================================================================


class TestEveryLoadTextDelivery:
    def test_artefact_on_first_load_is_present_on_second_load(self, project: Path) -> None:
        """T065 (red-first): the second load renders zero today.

        An activated directive/styleguide/toolguide present on the first load
        MUST still be present on a subsequent load. Today the steady-state
        render fires a compact early-return before the bundle is computed.
        """
        from charter.activation.context import build_charter_context

        first = build_charter_context(
            project, action="implement", mark_loaded=True, mission_type="software-dev"
        )
        assert first.mode == "bootstrap"
        assert _DELIVERED_DIRECTIVE in first.text

        second = build_charter_context(
            project, action="implement", mark_loaded=True, mission_type="software-dev"
        )
        assert not second.first_load, "second load must be a steady-state render"
        assert _DELIVERED_DIRECTIVE in second.text, (
            "directive present on load one vanished on load two — governance is "
            "declared, not in force"
        )
        assert _DELIVERED_STYLEGUIDE in second.text
        assert _DELIVERED_TOOLGUIDE in second.text

    def test_explicit_steady_state_depth_delivers_bundle(self, shared_project: Path) -> None:
        """T060 site 2: depth below the bootstrap minimum still delivers."""
        from charter.activation.context import build_charter_context

        result = build_charter_context(
            shared_project,
            action="implement",
            mark_loaded=False,
            mission_type="software-dev",
            depth=1,
        )
        assert _DELIVERED_DIRECTIVE in result.text
        assert _DELIVERED_STYLEGUIDE in result.text


# ===========================================================================
# T059 — the extended-tier depth gate no longer drops delivered kinds
# ===========================================================================


class TestBootstrapRendersExtendedKinds:
    def test_styleguides_and_toolguides_render_at_bootstrap_depth(self, shared_project: Path) -> None:
        """T059 (red-first): ``_EXTENDED_CONTEXT_DEPTH`` gates these out today.

        At the delivered depths (d=1/d=2) the styleguide/toolguide render rows
        are gated out, so an activated styleguide never reaches the agent even
        on the bootstrap load.
        """
        from charter.activation.context import build_charter_context

        result = build_charter_context(
            shared_project, action="implement", mark_loaded=False, mission_type="software-dev"
        )
        assert result.mode == "bootstrap"
        assert "Styleguides:" in result.text
        assert _DELIVERED_STYLEGUIDE in result.text
        assert "Toolguides:" in result.text
        assert _DELIVERED_TOOLGUIDE in result.text


# ===========================================================================
# T060 (sites 3 & 4) — the --json payload builder delivers on every load
# ===========================================================================


class TestJsonEveryLoadDelivery:
    def test_json_delivers_at_steady_state_depth(self, shared_project: Path) -> None:
        """T060 site 4 (red-first): depth<minimum returns an empty payload today."""
        from charter.activation.context import build_charter_context_json

        payload = build_charter_context_json(
            shared_project, action="implement", depth=1, mission_type="software-dev"
        )
        assert payload.get("directives"), "steady-state --json must carry directives"
        assert payload.get("styleguides"), "steady-state --json must carry styleguides"
        assert payload.get("toolguides"), "steady-state --json must carry toolguides"

    def test_json_non_bootstrap_action_is_explicitly_ruled_out(self, shared_project: Path) -> None:
        """T060 site 3 (B-6) — REVERSED (WP02, #3596, ADR
        2026-08-21-1-charter-gate-predicate-inversion, reversal A).

        ``tasks`` is a DRG-declared ``action:software-dev/tasks`` node
        (``packs/built-in/action.graph.yaml``); it now delivers its grain
        instead of being coarsely ruled out by the old
        ``action in BOOTSTRAP_ACTIONS`` membership test. This assertion was
        the opposite before the ADR — do NOT restore the old ``compact``/
        empty-arrays assertion; that re-breaks the fix.
        """
        from charter.activation.context import build_charter_context_json

        payload = build_charter_context_json(
            shared_project, action="tasks", mission_type="software-dev"
        )
        assert payload.get("mode") == "bootstrap"
        assert payload.get("directives"), "declared 'tasks' action must deliver directives"

    @pytest.mark.parametrize("mission_type", ["documentation", "research"])
    def test_json_retrospect_delivers_for_documentation_and_research(
        self, shared_project: Path, mission_type: str
    ) -> None:
        """AC-3 retrospect half (WP02, #3596, ADR
        2026-08-21-1-charter-gate-predicate-inversion, reversal A).

        ``action:documentation/retrospect`` and ``action:research/retrospect``
        are DRG-declared nodes (``packs/built-in/action.graph.yaml``) reached
        only via direct ``action:<type>/<step>`` URN construction, NOT the
        ``mission_type -> action requires`` sequence edge (FR-015 — the three
        ``*/retrospect`` nodes are sequence-orphans yet still deliver). A
        regression that starves them via a coarse action-name gate must red
        here.
        """
        from charter.activation.context import build_charter_context_json

        payload = build_charter_context_json(
            shared_project, action="retrospect", mission_type=mission_type
        )
        assert payload.get("mode") == "bootstrap"
        assert payload.get("directives"), (
            f"declared 'retrospect' action ({mission_type}) must deliver directives"
        )


# ===========================================================================
# T063 — SC-001/SC-002 through the shipped CLI (`spec-kitty charter context`)
# ===========================================================================


def _cli_payload(runner: CliRunner, project: Path) -> dict[str, object]:
    from specify_cli.cli.commands.charter._app import charter_app

    with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=project):
        result = runner.invoke(
            charter_app,
            ["context", "--action", "implement", "--mission-type", "software-dev", "--json"],
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)  # type: ignore[no-any-return]


class TestShippedCliDelivery:
    def test_sc001_both_loads_deliver_through_cli(self, project: Path) -> None:
        """SC-001 (T063): activate a kind, observe it on BOTH loads via the CLI."""
        runner = CliRunner()

        first = _cli_payload(runner, project)
        assert first["first_load"] is True
        first_directives = {d["id"] for d in first["directives"]}  # type: ignore[index,union-attr]
        assert _DELIVERED_DIRECTIVE in first_directives
        first_styleguides = {s["id"] for s in first["styleguides"]}  # type: ignore[index,union-attr]
        assert _DELIVERED_STYLEGUIDE in first_styleguides

        second = _cli_payload(runner, project)
        assert second["first_load"] is False, "second CLI invocation must be steady state"
        second_directives = {d["id"] for d in second["directives"]}  # type: ignore[index,union-attr]
        second_styleguides = {s["id"] for s in second["styleguides"]}  # type: ignore[index,union-attr]
        assert _DELIVERED_DIRECTIVE in second_directives, (
            "SC-001: the directive vanished on the subsequent CLI load"
        )
        assert _DELIVERED_STYLEGUIDE in second_styleguides, (
            "SC-001: the styleguide vanished on the subsequent CLI load"
        )

        # SC-002 (T063), folded in from its own test so both CLI loads are
        # shared: a kind that resolves to nothing is absent, not phantom. A
        # directive id outside the implement grain must not appear on either
        # load -- delivery is the activated-and-reachable set, both times.
        for payload in (first, second):
            directive_ids = {d["id"] for d in payload["directives"]}  # type: ignore[index,union-attr]
            assert "DIRECTIVE_999_NOT_ACTIVATED" not in directive_ids


# ===========================================================================
# T062 — the two omitting callers supply the mission-type grain (FR-012)
# ===========================================================================


class TestGrainCallersForwardMissionType:
    def test_executor_render_forwards_mission_type(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent import workflow_executor as wx

        captured: dict[str, object] = {}

        class _Result:
            mode = "bootstrap"
            text = "stub"

        def _spy(repo_root: Path, **kwargs: object) -> _Result:
            captured.update(kwargs)
            return _Result()

        with patch.object(wx, "_wf") as wf:
            wf.return_value.build_charter_context = _spy
            wx.render_charter_context_text(tmp_path, "implement", mission_type="software-dev")
        assert captured.get("mission_type") == "software-dev", (
            "render_charter_context_text MUST forward the mission-type grain so "
            "the action bundle resolves rather than degrading to typeless (FR-012)"
        )

    def test_workflow_render_forwards_mission_type(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent import workflow as wf

        captured: dict[str, object] = {}

        class _Result:
            mode = "bootstrap"
            text = "stub"

        def _spy(repo_root: Path, **kwargs: object) -> _Result:
            captured.update(kwargs)
            return _Result()

        with patch.object(wf, "build_charter_context", _spy):
            wf._render_charter_context(tmp_path, "implement", mission_type="software-dev")
        assert captured.get("mission_type") == "software-dev"


# ===========================================================================
# B-9 — build_with_scope forwards the feature_dir grain (coverage added, not
# assumed: removing scope_router's forwarding currently breaks no test).
# ===========================================================================


class TestScopeRouterForwardsGrain:
    def test_build_with_scope_forwards_feature_dir(self, tmp_path: Path) -> None:
        from charter.activation import scope_router

        feature_dir = tmp_path / "kitty-specs" / "999-demo"
        feature_dir.mkdir(parents=True)
        captured: dict[str, object] = {}

        def _spy(repo_root: Path, **kwargs: object) -> object:
            captured.update(kwargs)
            return object()

        with patch.object(scope_router, "build_charter_context", _spy):
            scope_router.build_with_scope(tmp_path, feature_dir, action="implement")
        assert captured.get("feature_dir") == feature_dir, (
            "build_with_scope MUST forward feature_dir so the action grain keys "
            "off meta.json mission_type (removing line 71 must redden this)"
        )
