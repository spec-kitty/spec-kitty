"""Guard-capability regression suite (PR #1850 validated P1 guard-bypass, M1/M2).

Production task/workflow/finalize surfaces must not assert a protected-flow
``GuardCapability`` (``TEST_MODE`` / ``MERGE_BOOKKEEPING``) for ordinary status
bookkeeping, and the ambient ``SPEC_KITTY_TEST_MODE`` env must not waive the
protected-branch pre-checks. The ONE sanctioned ambient channel is the
documented operator escape hatch ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``.

Coverage map:

* ``workflow._commit_via_legacy_safe_commit`` — behavioral refusal on a
  protected target with zero env (no commit lands).
* ``workflow`` baseline-artifact commit, the three ``agent tasks`` commit
  sites (move-task / mark-status / map-requirements), and the
  ``bootstrap_canonical_state`` seeding calls — call-site capability parity:
  the capability asserted at each production call site must be refused by
  ``commit_guard.evaluate`` on a protected destination.
* ``mark-status`` CLI — ``SPEC_KITTY_TEST_MODE`` no longer waives the
  protected-branch pre-check (the validation's live repro, inverted).
* The ``mark-status``/``implement`` pre-checks ignore the test-mode env and
  honor only the operator hatch (M2).
* ``DecisionGitLog`` — a refused decision-record commit is swallowed
  (warning), the event line is preserved, and nothing lands on the
  protected ref.
"""

from __future__ import annotations

import ast
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mission_runtime import CommitTarget
from specify_cli.core.commit_guard import (
    GuardCapability,
    ProtectionState,
    evaluate,
)
from specify_cli.git.commit_helpers import ProtectedBranchRefused

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    protected_target_repo,
)

pytestmark = pytest.mark.git_repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPECIFY_CLI_SRC = _REPO_ROOT / "src" / "specify_cli"


@pytest.fixture(autouse=True)
def _clear_env_hatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test env-clean; individual tests opt in to a single channel."""
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)


def _head_sha(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


# ---------------------------------------------------------------------------
# Call-site capability parity: the capability each production call site
# asserts must be REFUSED by the ONE policy decision on a protected ref.
# ---------------------------------------------------------------------------


def _capabilities_at_call_sites(path: Path, callee: str) -> list[GuardCapability]:
    """Extract the ``capability=`` value of every ``callee(...)`` call in ``path``.

    A call without a ``capability`` keyword contributes ``STANDARD`` (the
    documented default of both ``safe_commit`` and
    ``bootstrap_canonical_state``).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    capabilities: list[GuardCapability] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else None
        )
        if name != callee:
            continue
        capability = GuardCapability.STANDARD
        for keyword in node.keywords:
            if keyword.arg != "capability":
                continue
            value = keyword.value
            assert isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id == "GuardCapability", (
                f"{path.name}:{node.lineno} passes a non-literal capability; "
                "this parity test needs the asserted-at-the-surface literal"
            )
            capability = GuardCapability[value.attr]
        capabilities.append(capability)
    return capabilities


@pytest.mark.parametrize(
    ("module_rel", "callee", "expected_sites"),
    [
        # (b) legacy workflow commit. coord-authority-trio-degod-01KX7094 WP02
        # (T009) relocated the sibling baseline-artifact commit call site into
        # ``workflow_executor.implement_capture_baseline`` -- see the adjacent
        # ``workflow_executor.py`` parametrize entry below for its capability
        # parity (moved call site, same STANDARD assertion, unchanged).
        ("cli/commands/agent/workflow.py", "safe_commit", 1),
        ("cli/commands/agent/workflow_executor.py", "safe_commit", 1),
        # (d) move-task / mark-status / map-requirements auto-commits now route
        # through the canonical ``commit_for_mission`` router (WP07 / #2058 / FR-006);
        # the single ``safe_commit`` site they share lives in the router and must
        # still assert STANDARD (refused on a protected destination).
        ("coordination/commit_router.py", "safe_commit", 1),
        # (c) finalize-tasks canonical seeding (both finalize surfaces) — the
        # #2056 decomposition relocated these seeding call sites out of the
        # ``mission`` god module into the ``mission_finalize`` seam. The raw
        # ``bootstrap_canonical_state`` calls now live inside the
        # ``_bootstrap_canonical_state_via_mission`` patch-seam wrapper (which
        # forwards ``capability`` as a variable, not a surface literal); every
        # wrapper call site resolves to STANDARD (refused on a protected
        # destination). Re-pinned 2 -> 4 (2026-09-30, landing #5405 / #5403):
        # ``fix(finalize): make planning refresh atomic and fail closed``
        # (505c6aeeb5) added two ``refresh_bootstrap_result`` call sites that
        # both default to STANDARD; the count pin was never joined, so this test
        # was red on main. Re-pinned 4 -> 3 (2026-09-30, #5100): the second of
        # those sites was a duplicate re-plan fallback, replaced by a fail-closed
        # refusal. The per-site protected-refusal assertion below still checks
        # every remaining site (each is STANDARD); only the count changed.
        ("cli/commands/agent/mission_finalize.py", "_bootstrap_canonical_state_via_mission", 3),
        # Wave 2 degod (#2305) relocated the finalize-tasks family out of the
        # tasks.py shim; its canonical-seeding call site now lives in
        # tasks_finalize.py (routed ``_tasks.bootstrap_canonical_state(...)`` —
        # the AST counter matches attribute calls, so the capability parity
        # still drives the real site).
        ("cli/commands/agent/tasks_finalize.py", "bootstrap_canonical_state", 1),
    ],
)
def test_status_bookkeeping_call_sites_are_refused_on_protected_destination(
    module_rel: str, callee: str, expected_sites: int
) -> None:
    """No ordinary bookkeeping call site may assert a protected-flow capability.

    Drives ``commit_guard.evaluate`` with the exact capability each production
    call site asserts: on a protected destination every one of these sites
    must be REFUSED (they are not the release / upgrade / merge bookkeeping
    flows). Failing here means a production surface regrew a protected-branch
    waiver (PR #1850 M1).
    """
    module_path = _SPECIFY_CLI_SRC / module_rel
    capabilities = _capabilities_at_call_sites(module_path, callee)
    assert len(capabilities) == expected_sites, (
        f"expected {expected_sites} {callee} call site(s) in {module_rel}, "
        f"found {len(capabilities)} — update this parity test alongside the "
        "call-site change"
    )

    target = CommitTarget(ref="main")
    protected = ProtectionState(is_protected=True)
    for capability in capabilities:
        verdict = evaluate(target, protected, capability)
        assert not verdict.allowed, (
            f"{module_rel} asserts {capability!r} at a {callee} call site, "
            "which evaluate() ALLOWS on a protected ref — ordinary status "
            "bookkeeping must be refused there (assert STANDARD)"
        )


# ---------------------------------------------------------------------------
# Wrapper capability-forwarding parity (#2056 decomposition): the AST parity
# test above eyes the ``_bootstrap_canonical_state_via_mission`` call-site
# literals, NOT the raw ``bootstrap_canonical_state`` call inside the wrapper.
# That makes it blind to a wrapper that silently substitutes a protected-flow
# capability while its call sites pass STANDARD. This test restores the named
# guard-parity teeth by driving the wrapper directly and asserting the
# capability it FORWARDS to the underlying ``bootstrap_canonical_state`` is
# exactly the one each call site intends (no capability-crossing).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("call_kwargs", "expected_capability"),
    [
        # Dry-run call site (mission_finalize.py:~936): no ``capability`` kwarg,
        # so the wrapper must NOT inject one — the underlying callee then applies
        # its STANDARD default. A wrapper that forced MERGE_BOOKKEEPING here would
        # be caught.
        ({"dry_run": True}, GuardCapability.STANDARD),
        # Non-dry-run call site (mission_finalize.py:~1396): passes
        # ``GuardCapability.STANDARD`` explicitly; the wrapper must forward that
        # exact literal, not substitute a protected-flow capability.
        ({"dry_run": False, "capability": GuardCapability.STANDARD}, GuardCapability.STANDARD),
    ],
)
def test_bootstrap_wrapper_forwards_call_site_capability(
    call_kwargs: dict[str, object], expected_capability: GuardCapability
) -> None:
    """``_bootstrap_canonical_state_via_mission`` must not cross the capability.

    The wrapper routes through the ``mission`` patch seam; we replace the seam's
    ``bootstrap_canonical_state`` with a spy and assert the capability it RECEIVES
    matches the call site's intent. When the call site omits ``capability`` the
    wrapper must omit it too (the callee then defaults to STANDARD); when the call
    site passes a literal the wrapper must forward that exact value. A wrapper that
    silently forwards a protected-flow capability (e.g. ``MERGE_BOOKKEEPING``) would
    fail here — closing the gap the AST call-site parity test cannot see.
    """
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.cli.commands.agent.mission_finalize import (
        _bootstrap_canonical_state_via_mission,
    )

    captured: dict[str, object] = {}
    sentinel = object()

    def _spy(feature_dir, mission_slug, *, dry_run=False, capability=GuardCapability.STANDARD):  # type: ignore[no-untyped-def]
        # Record the capability the wrapper actually hands the real callee. The
        # default mirrors the production ``bootstrap_canonical_state`` signature so
        # an omitted forward resolves to STANDARD exactly as production does.
        captured["capability"] = capability
        return sentinel

    with patch.object(_mission, "bootstrap_canonical_state", _spy):
        result = _bootstrap_canonical_state_via_mission(
            Path("/nonexistent/planning"), "001-guard-regression", **call_kwargs  # type: ignore[arg-type]
        )

    assert result is sentinel
    assert captured["capability"] is expected_capability, (
        "_bootstrap_canonical_state_via_mission forwarded "
        f"{captured['capability']!r} to bootstrap_canonical_state but the call "
        f"site intends {expected_capability!r} — the wrapper crossed the asserted "
        "GuardCapability (a protected-flow waiver invisible to the AST call-site "
        "parity test above)"
    )


# ---------------------------------------------------------------------------
# (a) Behavioral: the legacy workflow commit path is refused env-clean.
# ---------------------------------------------------------------------------


def test_legacy_workflow_commit_refused_on_protected_target(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """``_commit_via_legacy_safe_commit`` on a protected target lands nothing."""
    from specify_cli.cli.commands.agent import workflow

    repo = protected_target_repo
    repo.assert_target_is_protected()
    changed = repo.write("kitty-specs/100-legacy/notes.md", "workflow bookkeeping\n")
    head_before = _head_sha(repo.repo_root)

    with pytest.raises(ProtectedBranchRefused):
        workflow._commit_via_legacy_safe_commit(
            repo_root=repo.repo_root,
            target_branch=repo.target_branch,
            paths=[changed],
            message="chore: workflow status bookkeeping",
            wp_id="WP01",
        )

    assert _head_sha(repo.repo_root) == head_before, (
        "the legacy workflow safe_commit path landed a commit on the "
        "protected target with zero env — the TEST_MODE capability waiver "
        "regressed (PR #1850 M1)"
    )


# ---------------------------------------------------------------------------
# (M2) The command pre-checks: SPEC_KITTY_TEST_MODE is not a waiver; the
# operator hatch is the ONE sanctioned ambient channel.
# ---------------------------------------------------------------------------


def test_status_commit_prechecks_ignore_test_mode_env(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SPEC_KITTY_TEST_MODE`` must not waive the protected-branch refusal."""
    from specify_cli.cli.commands.agent.tasks import (
        _protected_branch_status_commit_error as tasks_precheck,
    )
    from specify_cli.cli.commands.implement import (
        _protected_branch_status_commit_error as implement_precheck,
    )

    repo = protected_target_repo
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")

    assert tasks_precheck(repo.target_branch, repo.repo_root, "spec-kitty agent tasks mark-status") is not None, (
        "SPEC_KITTY_TEST_MODE waived the tasks-command protected-branch "
        "pre-check (PR #1850 M2)"
    )
    assert implement_precheck(repo.target_branch, repo.repo_root) is not None, (
        "SPEC_KITTY_TEST_MODE waived the implement protected-branch "
        "pre-check (PR #1850 M2)"
    )


def test_status_commit_prechecks_honor_operator_hatch(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented operator hatch is the ONE ambient pre-check waiver."""
    from specify_cli.cli.commands.agent.tasks import (
        _protected_branch_status_commit_error as tasks_precheck,
    )
    from specify_cli.cli.commands.implement import (
        _protected_branch_status_commit_error as implement_precheck,
    )

    repo = protected_target_repo
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")

    assert tasks_precheck(repo.target_branch, repo.repo_root, "spec-kitty agent tasks mark-status") is None
    assert implement_precheck(repo.target_branch, repo.repo_root) is None


# ---------------------------------------------------------------------------
# (d) Behavioral CLI repro: event-only mark-status on a protected target must
# never create a git commit, including under SPEC_KITTY_TEST_MODE.
# ---------------------------------------------------------------------------


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
    del repo_root, mission_slug
    yield


def test_mark_status_test_mode_env_lands_no_commit_on_protected_target(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``mark-status --auto-commit`` on protected main remains commit-free.

    Completion is event-sourced after #2816, so ``--auto-commit`` is a
    compatibility input and no authored task artifact is committed. The
    command succeeds locally while HEAD remains untouched. (``"true"`` is
    used so the version-checker's
    ``SPEC_KITTY_TEST_MODE == "1"`` coupling stays out of the picture.)
    """
    from specify_cli.cli.commands.agent.tasks import app

    repo = protected_target_repo
    slug = "001-guard-regression"
    mission_dir = repo.repo_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01GUARDREGRESSIONMISSION00"}), encoding="utf-8"
    )
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\nSubtasks: T001\n", encoding="utf-8"
    )

    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "true")
    head_before = _head_sha(repo.repo_root)

    runner = CliRunner()
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo.repo_root),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch(
            "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
            return_value=(repo.repo_root, repo.target_branch),
        ),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = runner.invoke(
            app,
            [
                "mark-status",
                "T001",
                "--status",
                "done",
                "--mission",
                slug,
                "--auto-commit",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    assert _head_sha(repo.repo_root) == head_before, (
        "event-only mark-status landed a commit on the protected target"
    )


# ---------------------------------------------------------------------------
# The coordination pre-flight gate: env-clean STANDARD is refused on a
# protected destination; the operator hatch acts on its ProtectionState input
# exactly as it does for safe_commit (e47bc2c0 parity).
# ---------------------------------------------------------------------------


def _legacy_bookkeeping_change_set(repo: ProtectedTargetRepo):  # type: ignore[no-untyped-def]
    from specify_cli.coordination.types import GitChangeSet

    return GitChangeSet(
        destination_ref=repo.target_branch,
        repo_root=repo.repo_root,
        worktree_root=repo.repo_root,
        paths=("kitty-specs/001-guard-regression/status.events.jsonl",),
        message="chore: record status transition WP01",
        operation="status transition WP01",
        capability=GuardCapability.STANDARD,
    )


def test_coordination_gate_refuses_standard_on_protected_destination_env_clean(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """Env-clean STANDARD bookkeeping onto protected main is refused pre-flight."""
    from specify_cli.coordination.policy import WorkflowMutationPolicy
    from specify_cli.coordination.types import Refused

    verdict = WorkflowMutationPolicy.assert_allowed(
        _legacy_bookkeeping_change_set(protected_target_repo)
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "PROTECTED_BRANCH_REFUSED"


def test_coordination_gate_honors_operator_hatch_on_protection_state(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The operator hatch declares the branch unprotected for the gate too.

    Legacy-topology missions route status bookkeeping through the
    coordination pre-flight gate with ``destination_ref == target_branch``;
    a solo-fork operator who set the documented hatch must not be refused
    there when ``safe_commit`` downstream would allow the same commit
    (e47bc2c0 routes the hatch into the ProtectionState input).
    """
    from specify_cli.coordination.policy import WorkflowMutationPolicy
    from specify_cli.coordination.types import Allowed

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    verdict = WorkflowMutationPolicy.assert_allowed(
        _legacy_bookkeeping_change_set(protected_target_repo)
    )
    assert isinstance(verdict, Allowed), (
        f"gate refused despite the operator hatch: {verdict!r} — the "
        "pre-flight ProtectionState input must honor the ONE retained "
        "operator channel exactly as safe_commit does"
    )


# ---------------------------------------------------------------------------
# Decision-record commits: refusal is graceful, the event line survives.
# ---------------------------------------------------------------------------


def test_decision_log_refusal_preserves_event_and_lands_no_commit(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """A protected-destination decision commit is refused, not landed.

    ``DecisionGitLog._trigger_commit`` swallows the ``ProtectedBranchRefused``
    (a ``SafeCommitError``) into a WARNING after the event line is already on
    disk — mission execution continues, nothing lands on the protected ref.
    """
    from runtime.next._internal_runtime.events import NullEmitter
    from specify_cli.events.decision_log import DecisionGitLog

    from spec_kitty_events.mission_next import (
        DecisionInputAnsweredPayload,
        RuntimeActorIdentity,
    )

    repo = protected_target_repo
    head_before = _head_sha(repo.repo_root)

    log = DecisionGitLog(
        repo_root=repo.repo_root,
        worktree_root=repo.repo_root,
        destination_ref=repo.target_branch,
        mission_slug="001-guard-regression",
        inner=NullEmitter(),
        target=CommitTarget(ref=repo.target_branch),
    )
    log.emit_decision_input_answered(
        DecisionInputAnsweredPayload(
            run_id="run-001",
            decision_id="dec-001",
            answer="A",
            actor=RuntimeActorIdentity(actor_id="guard-suite", actor_type="llm"),
        )
    )

    decisions_file = repo.repo_root / "kitty-specs" / "001-guard-regression" / "decisions.events.jsonl"
    assert decisions_file.exists(), "the decision event write must survive the refusal"
    assert len(decisions_file.read_text(encoding="utf-8").splitlines()) == 1
    assert _head_sha(repo.repo_root) == head_before, (
        "a decision-record commit landed on the protected ref — the "
        "MERGE_BOOKKEEPING capability misassertion regressed (PR #1850)"
    )
