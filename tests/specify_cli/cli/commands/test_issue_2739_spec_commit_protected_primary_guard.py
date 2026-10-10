"""Issue #2739 — permanent guards for spec-commit / commit-router integrity on
protected-primary + coord-topology missions (fixed; these guard against
recurrence).

EPIC #2739 bundled several commit-router / commit-boundary defects that shared
one root cause: the commit-router's file-kind filter, the protected-primary
refusal path, and coord routing disagreed on where primary/planning artifacts
go, and the ``spec-commit`` CLI surfaced this as misleading guidance and
success-shaped no-ops instead of accurate errors. The sub-cases below are now
FIXED; each test is a permanent regression guard driving the real
``spec-commit`` entry point over a real git repo.

Guards (each was RED-first, now GREEN — the defect is fixed):

* **B01** — ``spec-commit --help`` and the protected-primary refusal message no
  longer advise the impossible "materialise the coordination worktree and retry"
  hint (a primary/planning artifact never routes to coordination). Both surfaces
  now name the two real remedies: create/check out a non-protected feature branch
  (``--start-branch``) or set ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1``.
  (squad) ``no_op_wrong_surface`` has three producers and only ONE of them is
  about a protected branch; the feature-branch/env-hatch remedies are now
  scoped to that producer (``policy.is_protected(result.placement_ref)``)
  instead of padding every wrong-surface refusal.

* **B03** — a ``committed:false`` success now carries a machine-readable
  ``reason`` (``no_op_already_committed`` / ``no_op_no_changes``), so a caller can
  tell "nothing to do" from "silently wrong".

* **B11** — a directory argument is rejected early with a clear files-only
  message instead of the opaque safe-commit "unexpected paths" backstop.

* **B16** — a coordination-kind write authored in the primary tree that routes to
  the coord partition (where staging skips it) no longer reports a false
  ``success:true, committed:false`` benign no-op; the router returns a wrong-
  surface refusal so a write that never landed is never reported as success.
  Overlaps #2694.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command
from tests.git.protected_target_fixtures import build_protected_target_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The impossible hint the epic (B01) called out — a primary/planning artifact
# never routes to coordination, so "materialise the coordination worktree and
# retry" can never succeed. Named once so every B01 assertion checks the SAME
# forbidden phrasing.
_IMPOSSIBLE_COORD_HINT_MARKERS = ("materialis", "coordination worktree")
_ENV_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_START_BRANCH_REMEDY = "start-branch"


def _make_app() -> typer.Typer:
    """Expose ``spec_commit_command`` as the default command (mirrors the sibling
    unit harness in ``tests/specify_cli/cli/commands/test_spec_commit_cmd.py``)."""
    app = typer.Typer()
    app.command()(spec_commit_command)
    return app


def _spec_commit_help_text() -> str:
    """Return ``spec-commit``'s command help STRING (the docstring source), lowercased.

    B01 is a property of the help *content*, not of rich's panel rendering. An
    earlier version rendered ``--help`` through ``CliRunner`` and asserted on the
    captured output, but that goes through a rich Panel whose contents vary by
    Typer/Click/rich version and terminal width — under the CI toolchain the
    command description rendered as an EMPTY panel (borders only), hiding the
    docstring and reddening this guard while it passed locally. Read the resolved
    Click command's ``.help`` directly instead: it is the exact docstring Typer
    assigns as the command help (what a user sees rendered), with zero dependence
    on the fragile panel layer. A callback forces group mode so the subcommand is
    addressable by name across Typer versions.
    """
    from typer.main import get_command

    from tests import _click_universe as typer_click

    app = typer.Typer(add_completion=False)

    @app.callback()
    def _root() -> None:  # a callback forces multi-command (group) mode
        """spec-commit help harness."""

    app.command("spec-commit")(spec_commit_command)
    group = get_command(app)
    assert isinstance(group, typer_click.Group)  # the callback above forces group mode
    command = group.commands["spec-commit"]
    return (command.help or "").lower()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


# Realistic identity constants (NFR-005 test-data policy; mirrors the e2e suite).
_FULL_ULID = "01KVMBD6HTBP3A9Y5T4EQ80RA9"
_MID8 = _FULL_ULID[:8]


def _seed_mission(repo_root: Path, slug: str, *, target_branch: str, coord: bool) -> Path:
    """Seed ``kitty-specs/<slug>/`` with meta.json + spec.md and commit it.

    ``coord=True`` mints the coordination branch (mirrors ``mission create`` on a
    coord-topology mission) so the router can resolve the coord placement.
    Returns the mission feature dir.
    """
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": _FULL_ULID,
        "mission_slug": slug,
        "mid8": _MID8,
        "mission_type": "software-dev",
        "friendly_name": slug.replace("-", " ").title(),
        "target_branch": target_branch,
    }
    coord_branch = f"kitty/mission-{slug}-{_MID8}"
    if coord:
        meta["coordination_branch"] = coord_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001 must hold.\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", f"chore: seed {slug}")
    if coord:
        _git(repo_root, "branch", coord_branch)
    return feature_dir


# ---------------------------------------------------------------------------
# B01 — un-followable "materialise the coordination worktree" guidance (fixed)
# ---------------------------------------------------------------------------


def test_b01_spec_commit_help_no_impossible_coord_hint() -> None:
    """#2739 B01 (fixed) — ``spec-commit --help`` must not advise the impossible
    coord-worktree retry, and must name the two real remedies.

    Primary/planning artifacts never route to coordination, so the retired
    "materialise the coordination worktree and retry" hint is un-followable. The
    help text now drops it and names the two real remedies (create with
    ``--start-branch`` onto a feature branch, or
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1``).
    """
    help_text = _spec_commit_help_text()

    for marker in _IMPOSSIBLE_COORD_HINT_MARKERS:
        assert marker not in help_text, (
            "spec-commit --help still advises the impossible coord-worktree "
            f"retry (found {marker!r}). Primary/planning artifacts never route "
            "to coordination; drop the hint (#2739 B01)."
        )
    assert _START_BRANCH_REMEDY in help_text, "spec-commit --help does not name the --start-branch feature-branch remedy (#2739 B01)."
    assert _ENV_HATCH.lower() in help_text, f"spec-commit --help does not name the {_ENV_HATCH} operator hatch remedy (#2739 B01)."


def test_b01_protected_refusal_drops_impossible_hint_and_names_env_hatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2739 B01 (fixed) — the protected-primary refusal message must not append
    the impossible coord-worktree retry, and must name the env-var hatch remedy.

    Drives the REAL router over a real protected ``main`` repo (no stubbed
    router), so the message under test is the one an operator actually sees. The
    refusal now names ONLY the two real remedies (feature branch + env hatch) and
    drops the coord-worktree hint.
    """
    monkeypatch.delenv(_ENV_HATCH, raising=False)
    repo = build_protected_target_repo(tmp_path)
    repo.assert_is_spec_kitty_project()
    repo.assert_target_is_protected()

    slug = "b01-refusal"
    feature_dir = _seed_mission(repo.repo_root, slug, target_branch="main", coord=True)
    spec = feature_dir / "spec.md"
    # Create an uncommitted change so there is a real diff the router must place.
    spec.write_text("# Spec\n\nFR-001 must hold.\nFR-002 too.\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.cli.commands.spec_commit_cmd._current_repo_root",
        lambda: repo.repo_root,
    )

    result = CliRunner().invoke(
        _make_app(),
        [str(spec), "-m", "spec: FR-002", "--mission", slug, "--json"],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    message = str(payload.get("error", "")).lower()
    assert message, f"expected an error message in the refusal payload: {payload!r}"

    for marker in _IMPOSSIBLE_COORD_HINT_MARKERS:
        assert marker not in message, (
            "The protected-primary refusal still appends the impossible "
            f"coord-worktree retry hint (found {marker!r}). It can never "
            "succeed for a primary/planning artifact (#2739 B01)."
        )
    assert _ENV_HATCH.lower() in message, f"The protected-primary refusal does not name the {_ENV_HATCH} operator hatch — one of the two real remedies (#2739 B01)."


def test_b01_non_protected_wrong_surface_omits_protected_primary_remedies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2739 B01 (squad) — a ``no_op_wrong_surface`` NOT caused by a protected
    branch must not be padded with the feature-branch/env-hatch remedies.

    ``no_op_wrong_surface`` has three producers in ``commit_for_mission``: the
    protected-primary refusal (whose own diagnostic already names the two real
    remedies), ``_paths_uncommitted_in_primary`` (#2739 B16), and
    ``_any_path_absent`` (the artifact is missing at the resolved placement).
    Only the protected-primary refusal is actually about a protected branch;
    this drives the ``_any_path_absent`` producer — a missing artifact on an
    UNPROTECTED feature branch — and asserts the resulting error carries no
    feature-branch / env-hatch remedy text, since there is no protection
    problem to remedy.
    """
    monkeypatch.delenv(_ENV_HATCH, raising=False)
    repo = build_protected_target_repo(tmp_path)
    _git(repo.repo_root, "checkout", "-b", "feat/b01-missing")

    slug = "b01-missing-artifact"
    feature_dir = _seed_mission(repo.repo_root, slug, target_branch="feat/b01-missing", coord=False)
    missing = feature_dir / "never-written.md"  # never created on disk

    monkeypatch.setattr(
        "specify_cli.cli.commands.spec_commit_cmd._current_repo_root",
        lambda: repo.repo_root,
    )

    result = CliRunner().invoke(
        _make_app(),
        [str(missing), "-m", "spec: missing", "--mission", slug, "--json"],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload.get("success") is False, payload
    message = str(payload.get("error", "")).lower()
    assert message, f"expected an error message in the refusal payload: {payload!r}"

    assert _START_BRANCH_REMEDY not in message, (
        "A non-protected wrong-surface refusal (missing artifact) must not "
        "carry the protected-primary feature-branch remedy — there is no "
        f"protection problem here (#2739 B01 squad). Message: {message!r}"
    )
    assert _ENV_HATCH.lower() not in message, (
        "A non-protected wrong-surface refusal (missing artifact) must not "
        "carry the protected-primary env-hatch remedy — there is no "
        f"protection problem here (#2739 B01 squad). Message: {message!r}"
    )


# ---------------------------------------------------------------------------
# B03 — success-shaped no-op must carry a machine-readable reason (fixed)
# ---------------------------------------------------------------------------


def test_b03_spec_commit_json_no_op_carries_machine_readable_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2739 B03 (fixed) — a ``committed:false`` success result must carry a
    machine-readable reason.

    Drives the REAL entry point over a real repo on an unprotected feature branch
    with an already-committed, no-diff ``spec.md``. The JSON payload now carries a
    ``reason`` (e.g. ``no_op_no_changes``), so a caller can tell "nothing to do"
    from "silently wrong".
    """
    monkeypatch.delenv(_ENV_HATCH, raising=False)
    repo = build_protected_target_repo(tmp_path)
    _git(repo.repo_root, "checkout", "-b", "feat/b03")

    slug = "b03-no-op"
    feature_dir = _seed_mission(repo.repo_root, slug, target_branch="feat/b03", coord=False)
    spec = feature_dir / "spec.md"  # already committed, no pending diff

    monkeypatch.setattr(
        "specify_cli.cli.commands.spec_commit_cmd._current_repo_root",
        lambda: repo.repo_root,
    )

    result = CliRunner().invoke(
        _make_app(),
        [str(spec), "-m", "spec: no change", "--mission", slug, "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload.get("committed") is False, f"precondition: expected a committed:false no-op result, got {payload!r}"
    assert payload.get("success") is True, payload
    reason = payload.get("reason")
    assert reason, (
        "A committed:false success result carries no machine-readable 'reason' — "
        "the caller cannot distinguish 'nothing to do' from 'silently wrong' "
        f"(#2739 B03). Payload: {payload!r}"
    )


# ---------------------------------------------------------------------------
# B11 — directory argument aborts with the opaque safe-commit backstop (fixed)
# ---------------------------------------------------------------------------


def test_b11_spec_commit_directory_argument_no_opaque_backstop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2739 B11 (fixed) — a directory argument must not fail with the opaque
    safe-commit "unexpected paths" backstop.

    ``spec-commit`` now rejects a directory argument early with a clear files-only
    message; the operator no longer sees the opaque staging-area backstop that the
    generic ``FILES...`` help never warned about.
    """
    monkeypatch.delenv(_ENV_HATCH, raising=False)
    repo = build_protected_target_repo(tmp_path)
    _git(repo.repo_root, "checkout", "-b", "feat/b11")

    slug = "b11-dir-arg"
    feature_dir = _seed_mission(repo.repo_root, slug, target_branch="feat/b11", coord=False)
    decisions = feature_dir / "decisions"
    decisions.mkdir()
    (decisions / "d1.md").write_text("# D1\n", encoding="utf-8")
    (decisions / "d2.md").write_text("# D2\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.cli.commands.spec_commit_cmd._current_repo_root",
        lambda: repo.repo_root,
    )

    result = CliRunner().invoke(
        _make_app(),
        [str(decisions), "-m", "decisions", "--mission", slug, "--json"],
    )

    combined = result.output.lower()
    assert "staging area contains unexpected paths" not in combined, (
        "spec-commit on a directory argument aborts with the opaque safe-commit "
        "backstop instead of expanding the directory or erroring early with a "
        f"clear files-only message (#2739 B11). Output: {result.output!r}"
    )


# ---------------------------------------------------------------------------
# B16 — false success for a coordination-kind file that lands nowhere (fixed)
# ---------------------------------------------------------------------------


def test_b16_spec_commit_coord_kind_file_false_success_lands_nowhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2739 B16 (fixed) — spec-commit must not report success for a
    coordination-kind write that never lands.

    A STATUS-kind file (``status.events.jsonl``) written into the primary tree is
    re-grouped by ``commit_for_mission`` to the coord partition, where staging
    skips it. The router now returns a wrong-surface refusal instead of a benign
    ``unchanged`` no-op, so a write that never landed is never reported as
    success. Overlaps #2694.

    Drives the REAL entry point over a real coord-topology mission repo.
    """
    monkeypatch.delenv(_ENV_HATCH, raising=False)
    repo = build_protected_target_repo(tmp_path)
    _git(repo.repo_root, "checkout", "-b", "feat/b16")

    slug = "b16-coord-kind"
    feature_dir = _seed_mission(repo.repo_root, slug, target_branch="feat/b16", coord=True)
    events = feature_dir / "status.events.jsonl"
    events.write_text('{"event":"created"}\n', encoding="utf-8")  # uncommitted

    monkeypatch.setattr(
        "specify_cli.cli.commands.spec_commit_cmd._current_repo_root",
        lambda: repo.repo_root,
    )

    result = CliRunner().invoke(
        _make_app(),
        [str(events), "-m", "status: created", "--mission", slug, "--json"],
    )
    payload = json.loads(result.output)

    # The file was never committed anywhere; a coord-branch placement_ref plus
    # success:true is the false-success this sub-case reported before the fix.
    reported_success_but_nothing_landed = result.exit_code == 0 and payload.get("success") is True and payload.get("committed") is False
    assert not reported_success_but_nothing_landed, (
        "spec-commit reported success for a coordination-kind write that never "
        f"landed (payload={payload!r}). It must fail with an accurate error or "
        "actually commit the artifact (#2739 B16 / #2694)."
    )
