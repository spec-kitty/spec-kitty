"""Acceptance test: owned-checkout ``agent mission setup-plan`` for a documentation-type mission (WP09 review cycle 1, issue 1).

owned-checkout-lifecycle-authority WP09. Red-first (C-007): reproduces the
review-cycle-1 defect through the pre-existing entry point
(``agent mission setup-plan --owned-checkout P``) before the fix.

Observed base (pre-fix) behaviour, per the reviewer's probe: a
documentation-type owned single_branch mission (``iteration_mode:
gap_filling``) reaches ``_run_documentation_gap_analysis`` and
``_detect_and_configure_generators``, both of which call
``commit_for_mission(repo_root=P, owned=None)`` -- P is passed as a bare
``repo_root`` with no ``owned=`` fact, so:

* with NO stale R copy, ``commit_for_mission`` cannot resolve a placement
  for P (P is not R and carries no owned fact), returns
  ``no_op_wrong_surface``, which ``contextlib.suppress(Exception)`` does
  NOT catch (it is not an exception) -- so P is left dirty
  (``meta.json`` modified, ``gap-analysis.md`` untracked), yet the command
  payload still reports non-null ``gap_analysis`` / ``generators_detected``
  as if the commit landed;
* WITH a stale R copy (``stale_root_copy``), ``commit_for_mission``
  resolves against R's copy instead and the commit lands on R -- the
  exact fact-less, stale-copy-dependent routing FR-005/FR-007 forbid.

Confirmed red in a scratch detached worktree against this cycle's base
(before the fix commit that threads ``owned=`` into both helpers).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _clear_repo_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


def _payload(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(result.output)
    assert isinstance(data, dict), f"expected a JSON object, got {type(data).__name__}: {result.output!r}"
    return data


def _make_documentation_mission(owned_checkouts: OwnedCheckouts) -> None:
    """Turn P's default software-dev mission into a ``gap_filling`` documentation mission.

    Adds ``docs/`` (gap analysis needs a real directory to analyze) and
    ``pyproject.toml`` (triggers ``SphinxGenerator.detect``), rewrites
    ``meta.json`` with ``mission_type: documentation`` +
    ``documentation_state.iteration_mode: gap_filling``, and activates the
    ``documentation`` mission type (this suite never runs `spec-kitty init`,
    so template resolution needs the explicit activation -- see
    ``test_owned_lifecycle_acceptance_status.py::_activate_mission_type``).
    """
    from tests.integration.conftest import _git

    p_root = owned_checkouts.owned_root
    mission_dir = owned_checkouts.mission_dir

    (p_root / "docs").mkdir(exist_ok=True)
    (p_root / "docs" / "index.md").write_text("# Docs\n\nSome existing documentation.\n", encoding="utf-8")
    (p_root / "pyproject.toml").write_text('[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding="utf-8")

    meta_file = mission_dir / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["mission_type"] = "documentation"
    meta["documentation_state"] = {
        "iteration_mode": "gap_filling",
        "divio_types_selected": ["reference"],
        "generators_configured": [],
        "target_audience": "developers",
        "last_audit_date": None,
        "coverage_percentage": None,
    }
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    config_path = p_root / ".kittify" / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    if "mission_type_activations" not in text:
        config_path.write_text(f"{text}mission_type_activations: [software-dev, documentation]\n", encoding="utf-8")

    _git(p_root, "add", ".")
    _git(p_root, "commit", "-qm", "convert to a gap_filling documentation mission")


def _setup_plan(*args: str) -> Any:
    return CliRunner().invoke(mission_app, ["setup-plan", *args])


@pytest.mark.parametrize("with_stale_copy", [False, True])
def test_documentation_owned_mission_commits_gap_analysis_and_generators_in_p(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
    with_stale_copy: bool,
) -> None:
    """Target: a documentation-type owned mission commits gap-analysis + generator config in P, R untouched, regardless of a stale R copy."""
    _make_documentation_mission(owned_checkouts)
    if with_stale_copy:
        stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    from tests.integration.conftest import _git

    before = r_snapshot.take()
    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")

    result = _setup_plan(
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("result") != "error", (payload, result.output)

    # The defect's tell: a non-null, non-false claim that the commit landed.
    assert payload.get("gap_analysis") not in (None, False), payload
    assert payload.get("generators_detected"), payload

    head_after = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    assert head_after != head_before, payload

    # P must not carry the DIRTY, no-op-wrong-surface residue the defect
    # left behind (a modified-but-uncommitted meta.json / untracked
    # gap-analysis.md). Status-lifecycle-event bookkeeping (a SEPARATE,
    # unowned subsystem) may still leave its own untracked
    # ``status.events.jsonl`` -- not this WP's concern.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=owned_checkouts.owned_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    dirty_lines = [line for line in porcelain.splitlines() if "status.events.jsonl" not in line]
    assert not dirty_lines, f"P must be clean (besides status.events.jsonl) after the commit, got:\n{porcelain}"

    touched = _git(owned_checkouts.owned_root, "log", "-1", "--name-only", "--pretty=format:")
    assert "gap-analysis.md" in touched or "meta.json" in touched, touched

    r_snapshot.assert_unchanged(
        before,
        r_snapshot.take(),
        tolerate_status_mutex_for=owned_checkouts.mission_slug,
    )
