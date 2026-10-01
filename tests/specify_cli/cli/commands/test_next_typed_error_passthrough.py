"""WP02 / C-IC02: ``next`` (+ ``context mission-resolve``) typed-error pass-through.

Live repro #15: a mission whose ``meta.json`` declares a ``coordination_branch``
but whose coord branch has been deleted from git (and whose coord worktree was
never materialized) makes the resolver raise a precise typed
:class:`ActionContextError` — code ``COORDINATION_BRANCH_DELETED`` (a
``STATUS_READ_PATH_NOT_FOUND`` subclass) — carrying the real read-path
remediation. Before this WP, ``next`` discarded all of that and substituted a
generic ``MISSION_NOT_FOUND`` + "run mission list", pointing the operator the
wrong way (the mission is not missing; the read path is broken).

These tests pin the **most-specific witnessed code** (``COORDINATION_BRANCH_DELETED``)
and the non-empty checked-paths + read-path remediation, and assert ``next``
NEVER emits ``MISSION_NOT_FOUND`` for this read-path miss. They are topology-true
(a real git repo, a 26-char ULID ``mission_id``, no fabricated short id) and were
written to FAIL FIRST on HEAD (HEAD emits ``MISSION_NOT_FOUND``).

Verification-by-deletion (C-IC02): removing the collapse at the four next-family
catch-sites keeps this suite green because the typed envelope now flows through.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# A full 26-char Crockford-base32 ULID — NOT a fabricated short id (NFR-002).
MISSION_ID = "01KV8NPC9ZQ4M3T7XR2WB5K6DA"
MID8 = MISSION_ID[:8]  # "01KV8NPC"
SLUG = f"read-path-error-fidelity-adoption-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG}"

# The most-specific code the live resolver produces for the #15 topology. We pin
# THIS, not the parent ``STATUS_READ_PATH_NOT_FOUND`` and not "any
# non-mission-not-found code".
WITNESSED_CODE = "COORDINATION_BRANCH_DELETED"
# The broken-baseline expectation: HEAD collapses to this. Asserting it makes the
# pre-fix delta visible (T007 captured-red contract).
BROKEN_BASELINE_CODE = "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_preflight_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass charter preflight + worktree-location guard.

    These tests exercise the typed read-path error surfacing, not charter
    freshness or git-context detection.
    """
    from pathlib import Path as _Path

    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
    from specify_cli.core.context_validation import CurrentContext, ExecutionContext

    ok = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_a, **_kw: ok,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only",
        lambda *_a, **_kw: ok,
    )
    _fake_ctx = CurrentContext(
        location=ExecutionContext.MAIN_REPO,
        cwd=_Path.cwd(),
        repo_root=_Path.cwd(),
        worktree_name=None,
        worktree_path=None,
    )
    monkeypatch.setattr(
        "specify_cli.core.context_validation.get_current_context",
        lambda: _fake_ctx,
    )


@pytest.fixture()
def coord_branch_deleted_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Build the topology-true #15 fixture and point the CLI at it.

    A real git repo with exactly one mission whose ``meta.json`` declares a
    ``coordination_branch``, but with NO coord branch in git and NO coord
    worktree materialized — the #1718/#1889-R3 fail-closed trigger. The mission
    dir + spec exist on disk; only the read-path topology is broken.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)

    # .kittify marker so locate_project_root resolves even without SPECIFY_REPO_ROOT.
    kittify = repo / ".kittify"
    kittify.mkdir()
    # context mission-resolve reads project.uuid before resolving the mission dir;
    # supply a minimal config so the command reaches the typed-error catch-site.
    (kittify / "config.yaml").write_text(
        "project:\n  uuid: 01KV8NPCPROJECT0000000000A\n",
        encoding="utf-8",
    )

    mission_dir = repo / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "mission_slug": SLUG,
                "coordination_branch": COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec", encoding="utf-8")

    # Authoritative override so the CLI resolves the fixture repo regardless of cwd.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)
    return repo


# ---------------------------------------------------------------------------
# Pre-fix witness: the resolver already produces the precise typed code.
# ---------------------------------------------------------------------------


def test_resolver_witnesses_coordination_branch_deleted(
    coord_branch_deleted_repo: Path,
) -> None:
    """Ground truth: ``resolve_action_context`` produces the precise typed code.

    This proves the disease is `next` discarding the signal, not the resolver
    failing to produce it (C-001 — adopt, do not build).
    """
    from mission_runtime import ActionContextError, resolve_action_context

    with pytest.raises(ActionContextError) as excinfo:
        resolve_action_context(
            coord_branch_deleted_repo, action="tasks", feature=SLUG
        )
    assert excinfo.value.code == WITNESSED_CODE
    # The remediation is a read-path repair, never "run mission list".
    assert "mission list" not in str(excinfo.value)
    assert "worktree repair" in str(excinfo.value) or "coordination_branch" in str(
        excinfo.value
    )


# ---------------------------------------------------------------------------
# T007: next query path surfaces the typed code, NOT MISSION_NOT_FOUND.
# ---------------------------------------------------------------------------


def _run_next_query_json(handle: str) -> tuple[int, dict]:
    result = runner.invoke(
        cli_app,
        ["next", "--mission", handle, "--json"],
        catch_exceptions=False,
    )
    payload = json.loads(result.output)
    return result.exit_code, payload


class TestNextQueryTypedPassthrough:
    """``next --mission <slug> --json`` on the #15 topology (query path)."""

    def test_emits_witnessed_code_not_mission_not_found(
        self, coord_branch_deleted_repo: Path
    ) -> None:
        exit_code, payload = _run_next_query_json(SLUG)
        assert exit_code == 1
        assert payload.get("error_code") == WITNESSED_CODE, (
            "next must surface the resolver's most-specific typed code "
            f"({WITNESSED_CODE}); got: {payload}"
        )
        # The whole point: NEVER the broken baseline for a read-path miss.
        assert payload.get("error_code") != BROKEN_BASELINE_CODE

    def test_payload_carries_non_empty_checked_paths_with_coord_candidate(
        self, coord_branch_deleted_repo: Path
    ) -> None:
        _, payload = _run_next_query_json(SLUG)
        checked = payload.get("checked_paths")
        assert isinstance(checked, list) and checked, (
            f"expected non-empty checked_paths; got: {payload}"
        )
        joined = "\n".join(checked)
        assert SLUG in joined
        # The coord candidate path must be among the checked paths.
        assert any(".worktrees" in p and "-coord" in p for p in checked), (
            f"expected the coord candidate path in checked_paths; got: {checked}"
        )

    def test_remediation_is_read_path_not_mission_list(
        self, coord_branch_deleted_repo: Path
    ) -> None:
        _, payload = _run_next_query_json(SLUG)
        remediation = (payload.get("next_step") or "") + (
            payload.get("remediation") or ""
        )
        assert "mission list" not in remediation, (
            f"remediation must be a read-path repair, not mission-list; got: {payload}"
        )
        assert "worktree repair" in remediation or "coordination_branch" in remediation


# ---------------------------------------------------------------------------
# M1 / T038: context mission-resolve preserves the typed code.
# ---------------------------------------------------------------------------


class TestContextMissionResolveTypedPassthrough:
    """``context mission-resolve`` is the same disease on a different door (M1)."""

    def test_emits_resolver_code_not_check_the_slug(
        self, coord_branch_deleted_repo: Path
    ) -> None:
        result = runner.invoke(
            cli_app,
            ["context", "mission-resolve", "--wp", "WP01", "--mission", SLUG],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        # The flatten the M1 fix removes: "Check that the mission slug is correct."
        assert "Check that the mission slug is correct" not in result.output, (
            f"M1 flatten must be gone; got: {result.output}"
        )
        # The typed code (or its read-path remediation) must survive.
        assert (
            WITNESSED_CODE in result.output
            or "worktree repair" in result.output
            or "coordination_branch" in result.output
        ), f"expected the resolver's typed signal to survive; got: {result.output}"
