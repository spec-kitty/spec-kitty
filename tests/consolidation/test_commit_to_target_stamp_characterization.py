"""Characterization (#7578, R8 / IC-06a): commit-to-target ``single_branch`` verdicts around the window stamp.

A commit-to-target ``single_branch`` Mission (``--commit-to-target``: the write branch IS the target)
recorded no ``lane_head`` and no ``wp_window`` before #7578. Each cell pins one consolidation or accept
verdict of such a Mission and proves the reader it names actually ran on the Mission's status events, so
"no verdict change" can never pass as a no-op:

* (a) approved-only: ``consolidate`` (``MergeOutcomeVerifier.verify``) and ``accept``;
* (b) approved + canceled on the planning lane: ``reconciliation_canceled._mixed_lanes`` and the
  canceled-work attribution ``resolve_canceled_wp``;
* (c) ``consolidate --dependency-ref``: ``reconciliation_closed_world._recorded_lane_heads``;
* (d) ``consolidate --attest-approved-reviewed``: ``approved_attestation._has_review_approval_stamp``.

:data:`STAMPED` says which state the cells pin: ``False`` before the stamp (the keys are absent from the
status events), ``True`` after it (the keys are present). Lifecycle moves run in-process through the shared
``single_branch_window_support`` helpers; ``consolidate`` and ``accept`` run in-process through
``CliRunner`` so a ``monkeypatch`` spy sees the reader.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.consolidation import approved_attestation, reconciliation_canceled, reconciliation_claim
from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, read_status_events, resolve_status_read
from tests._support.ansi import strip_ansi
from tests.consolidation.characterization_support import _ensure_bootstrapped_home
from tests.integration.single_branch_window_support import (
    TARGET,
    Mission,
    build_and_approve,
    build_template,
    claim,
    cli_env,
    commit_file,
    emit,
    git,
    implement,
    tip,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Whether the status events of a commit-to-target Mission carry ``lane_head`` / ``wp_window`` (#7578).
STAMPED = False

_BANNER = "Reconciliation verified"
_OPENING_LANES = frozenset({"claimed", "in_progress"})


# --------------------------------------------------------------------------- fixture and runners


@pytest.fixture(scope="module")
def ctt_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """One commit-to-target ``single_branch`` Mission (WP01 owns src/m1, WP02 src/m2), built once and copied per cell."""
    return build_template(tmp_path_factory.mktemp("ctt-char"), commit_to_target=True)


@pytest.fixture
def mission(ctt_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    source, slug = ctt_template
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    monkeypatch.chdir(repo)
    for key, value in cli_env(tmp_path).items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            monkeypatch.setenv(key, value)
    for leaked in ("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE"):
        monkeypatch.delenv(leaked, raising=False)
    _ensure_bootstrapped_home(tmp_path / "home")
    m = Mission(repo, slug, tmp_path)
    assert "mission_branch" not in (repo / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"), "fixture: commit-to-target"
    return m


@dataclass
class Spy:
    """Every call of one wrapped reader and what it returned."""

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)


def spy_on(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str) -> Spy:
    """Wrap ``owner.name`` (where its caller looks it up) with a recorder that delegates to the original."""
    spy = Spy()
    original: Callable[..., Any] = getattr(owner, name)

    def _recording(*args: Any, **kwargs: Any) -> Any:
        spy.calls.append((args, kwargs))
        result = original(*args, **kwargs)
        spy.results.append(result)
        return result

    monkeypatch.setattr(owner, name, _recording)
    return spy


def run(*args: str) -> tuple[int, str]:
    """``spec-kitty <args>`` in this process: exit code and the whitespace-normalized output."""
    from specify_cli import app as cli_app

    result = CliRunner().invoke(cli_app, list(args))
    output = strip_ansi(result.output + (result.stderr if result.stderr_bytes is not None else ""))
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        output += f"\n{type(result.exception).__name__}: {result.exception}"
    return result.exit_code, " ".join(output.split())


def consolidate(m: Mission, *extra: str) -> tuple[int, str]:
    return run("consolidate", "--mission", m.slug, "--yes", *extra)


# --------------------------------------------------------------------------- reachability: the stamps on the inputs


def assert_stamp_state(m: Mission, wp_ids: tuple[str, ...]) -> None:
    """Every lifecycle move of *wp_ids* carries ``lane_head`` (and every opening move a ``wp_window.open_sha``) iff :data:`STAMPED`."""
    events = read_status_events(resolve_status_read(m.repo, m.slug))
    for wp_id in wp_ids:
        moves = [e for e in events if e.wp_id == wp_id and not str(e.actor).startswith("migration:") and str(e.to_lane) != "planned"]
        assert moves, f"fixture: {wp_id} has no lifecycle move"
        openers = [e for e in moves if str(e.to_lane) in _OPENING_LANES]
        assert openers, f"fixture: {wp_id} never opened a window"
        for event in moves:
            metadata = event.policy_metadata or {}
            assert (LANE_HEAD_KEY in metadata) is STAMPED, (wp_id, str(event.to_lane), metadata)
        for event in openers:
            window = (event.policy_metadata or {}).get(WP_WINDOW_KEY)
            if STAMPED:
                assert isinstance(window, dict) and window.get("open_sha"), (wp_id, str(event.to_lane), window)
            else:
                assert window is None, (wp_id, str(event.to_lane), window)


# --------------------------------------------------------------------------- the cells


def test_a_approved_only_consolidate_and_accept(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) Pins the approved-only gate (``MergeOutcomeVerifier.verify``) and the ``accept`` verdict."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    assert_stamp_state(mission, ("WP01", "WP02"))
    verify = spy_on(monkeypatch, MergeOutcomeVerifier, "verify")

    accept_rc, accept_out = run("accept", "--mission", mission.slug, "--no-commit", "--json")
    rc, out = consolidate(mission)

    # accept is blocked by the fixture's path conventions (no tests/, docs/, contracts/), never by the stamp.
    assert accept_rc == 1, accept_out
    assert '"all_done": true' in accept_out and '"ok": false' in accept_out, accept_out
    assert "expects tests path" in accept_out, accept_out
    assert rc == 0 and _BANNER in out, out
    assert [result.status.name for result in verify.results] == ["PASS"], verify.results


def test_b_mixed_approved_and_canceled_planning_lane(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) Pins ``_mixed_lanes`` and the canceled-work attribution (``resolve_canceled_wp``) on the planning lane."""
    build_and_approve(mission, "WP01")
    claim(mission, "WP02")
    implement(mission, "WP02")
    emit(mission, "WP02", "canceled", "alice", "--force", "--reason", "dropped from scope")
    assert_stamp_state(mission, ("WP01", "WP02"))
    mixed = spy_on(monkeypatch, reconciliation_canceled, "_mixed_lanes")
    attribution = spy_on(monkeypatch, reconciliation_canceled, "resolve_canceled_wp")

    rc, out = consolidate(mission)

    assert [[lane.lane_id for lane in result] for result in mixed.results] == [["lane-planning"]], mixed.results
    assert [type(result).__name__ for result in attribution.results] == ["Unattributable"], attribution.results
    assert attribution.results[0].reason.value == "no_stamp", attribution.results
    assert rc == 1 and _BANNER not in out, out
    assert "Reconciliation refused (fail-closed) at claim time" in out, out
    assert "mixed lane lane-planning: canceled WP02 cannot be attributed" in out, out
    assert "lifecycle events carry no commit attribution" in out, out
    assert "--attest-canceled-superseded WP02" in out, out


def test_c_dependency_ref(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) Pins ``_recorded_lane_heads`` (the "names Mission work" guard of ``--dependency-ref``)."""
    base = tip(mission, TARGET)
    git(mission.repo, "checkout", "-q", "-b", "ext/dependency", base)
    commit_file(mission, "vendor/dep.py", "DEP = 1\n", "feat: external dependency")
    git(mission.repo, "checkout", "-q", TARGET)
    build_and_approve(mission, "WP01")
    git(mission.repo, "merge", "-q", "--no-ff", "--no-edit", "ext/dependency")
    build_and_approve(mission, "WP02")
    assert_stamp_state(mission, ("WP01", "WP02"))
    heads = spy_on(monkeypatch, reconciliation_claim, "_recorded_lane_heads")

    rc, out = consolidate(mission, "--dependency-ref", "ext/dependency")

    assert heads.results == [frozenset()], heads.results
    assert rc == 0 and _BANNER in out, out
    assert "Declared dependency ref(s): ext/dependency" in out, out


def test_d_attest_approved_reviewed(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """(d) Pins ``_has_review_approval_stamp`` (whether ``--attest-approved-reviewed`` is accepted)."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    assert_stamp_state(mission, ("WP01", "WP02"))
    stamped = spy_on(monkeypatch, approved_attestation, "_has_review_approval_stamp")

    rc, out = consolidate(mission, "--attest-approved-reviewed", "WP01", "--attest-reason", "reviewed in PR #123")

    assert stamped.results == [False], stamped.results
    assert rc == 0 and _BANNER in out, out
    assert "Operator attestation recorded for approved WP01" in out, out


def test_residual_late_commit_after_last_approval(mission: Mission) -> None:
    """Pins ``test_commit_to_target_unbounded_residual``: a late commit after the last approval is NOT refused (FR-078).

    No consolidation bound reaches a commit-to-target Mission: ``reconciliation_bound._bound_write_branch``
    returns ``None`` (it reads ``minted_mission_branch``), so ``write_branch_bound`` never runs.
    """
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    commit_file(mission, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change after the last approval")

    rc, out = consolidate(mission)

    assert rc == 0 and _BANNER in out, out
    assert "LANE_MOVED_AFTER_APPROVAL" not in out, out
