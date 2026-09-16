"""Regression test for issue #3466.

``spec-kitty agent mission finalize-tasks`` documents a ``--target-branch``
escape hatch: "Override the canonical merge target branch read from
meta.json. Use this for legacy missions created before WP07 persisted
target_branch in meta.json (FR-012 escape hatch)."

The reported defect: a mission whose ``meta.json`` carries
``target_branch: "main"`` cannot finalize even when the operator supplies
``--target-branch <real-branch>`` explicitly. The override is accepted at the
CLI boundary (``finalize_tasks``'s own local ``target_branch`` variable) but
never reaches the WP-status-transition bookkeeping
(``specify_cli.status.bootstrap.bootstrap_canonical_state`` ->
``emit_status_transition_transactional`` -> ``get_feature_target_branch``),
which re-reads ``meta.json`` directly and still resolves ``"main"`` --
tripping the protected-branch guard with a byte-identical refusal naming
``destination ref 'main'`` regardless of the override.

This test builds a REAL git repo (via the ``protected_target_repo`` fixture:
``main`` is protected, ``.kittify/`` present so the guard actually engages)
with a mission whose ``meta.json`` says ``target_branch: "main"`` and NO
``coordination_branch`` (flattened topology -- mirrors the real #3391-style
fixture this issue was found against), checked out on a real, non-protected
feature branch as HEAD. It runs the real ``finalize-tasks`` CLI command
(no mocking of ``bootstrap_canonical_state`` or the commit machinery) with
``--target-branch <that feature branch>`` and asserts the mission completes
-- rather than refusing on "main".
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    protected_target_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "issue-3466-target-branch-override"
FEATURE_BRANCH = "kitty/mission-issue-3466-lane-01"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _scaffold_mission_pinned_to_main(repo: Path) -> Path:
    """A flattened-topology mission whose meta.json wrongly says target_branch=main.

    No ``coordination_branch`` -- mirrors the real fixture this issue was
    found against (``pr/sync-durability-hole-...`` in a sibling mission
    workspace, ``target_branch: "main"``, no coordination topology).
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        # Full required-field set (mission_metadata.REQUIRED_FIELDS) -- a real
        # mission, not the pre-meta.json legacy case, so ``set_target_branch``'s
        # validate=True write succeeds.
        "slug": MISSION_SLUG,
        "mission_slug": MISSION_SLUG,
        "friendly_name": "Issue 3466 target-branch override",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
        "mission_id": "01ISSUE3466OVERRIDE0000001",
        "mid8": "01ISSUE3",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_wp01/**\n"
        "authoritative_surface: src/module_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed mission pinned to main")

    # The operator is actually working on a real, non-protected feature
    # branch -- exactly the reported repro ("I ran it explicitly with a real
    # feature branch"). Checking it out as HEAD mirrors that.
    _git(repo, "checkout", "-q", "-b", FEATURE_BRANCH)

    return feature_dir


def _run_finalize_with_override(
    repo: Path, target_branch_override: str, *, mission_slug: str = MISSION_SLUG
) -> Result:
    # ``finalize-tasks`` enforces write-ownership from the invoking checkout,
    # not the mocked ``locate_project_root``. #3786 moved that read to the
    # command's single identity seam — ``resolve_checkout_identity`` at the
    # ``mission_finalize`` entrypoint — so inject a self-owned
    # ``CheckoutIdentity`` value object rooted at ``repo`` (a standalone git
    # repo whose ``.git`` is a directory → self-owned) instead of ``chdir``-ing
    # into it (the #3778 technique this replaces): the ownership check sees an
    # owned checkout deterministically, from any worktree running the suite.
    # This is a shared helper: the injection is inert for the callers that
    # assert exit-1 revert/error paths (they never reach the ownership gate) —
    # it only un-blocks the ``exit_code == 0`` callers, and their git-state
    # assertions already pass an explicit ``cwd=repo``.
    from specify_cli.core.checkout_identity import CheckoutIdentity

    with (
        patch(
            "specify_cli.cli.commands.agent.mission_finalize.resolve_checkout_identity",
            side_effect=lambda _cwd, intent: CheckoutIdentity(
                invoking_root=repo,
                canonical_target=repo,
                is_owner=True,
                intent=intent,
            ),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        return runner.invoke(
            app,
            [
                "finalize-tasks",
                "--mission",
                mission_slug,
                "--target-branch",
                target_branch_override,
                "--json",
            ],
            catch_exceptions=False,
        )


@pytest.fixture(autouse=True)
def _disable_saas_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *a, **k: None)


def test_target_branch_override_reaches_wp_status_bookkeeping(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """#3466: --target-branch must reach the WP-status-transition bookkeeping.

    Before the fix, ``bootstrap_canonical_state`` re-derives its commit
    destination from meta.json's literal ``target_branch`` ("main") and the
    protected-branch guard refuses -- byte-identical to the reported repro --
    even though the CLI was given an explicit, real, non-protected
    ``--target-branch``.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()
    protected_target_repo.assert_target_is_protected()

    _scaffold_mission_pinned_to_main(repo)

    result = _run_finalize_with_override(repo, FEATURE_BRANCH)

    assert result.exit_code == 0, (
        "finalize-tasks --target-branch must not refuse a real, non-protected "
        f"override (exit {result.exit_code}):\n{result.output}"
    )
    assert "PROTECTED_BRANCH_REFUSED" not in result.output, (
        f"WP-status bookkeeping still resolved the protected 'main' branch "
        f"instead of the --target-branch override:\n{result.output}"
    )
    assert "destination ref 'main'" not in result.output, (
        f"refusal still named 'main' despite the --target-branch override:\n"
        f"{result.output}"
    )

    # The WP-status bootstrap seed event landed on the feature branch, not main:
    # status.events.jsonl carries WP01's seeded "planned" transition there.
    events_on_feature_branch = subprocess.run(
        [
            "git",
            "show",
            f"{FEATURE_BRANCH}:kitty-specs/{MISSION_SLUG}/status.events.jsonl",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert '"wp_id":"WP01"' in events_on_feature_branch or '"wp_id": "WP01"' in events_on_feature_branch, (
        f"expected WP01's bootstrap-seeded status event committed on "
        f"{FEATURE_BRANCH!r}:\n{events_on_feature_branch}"
    )

    # The corrected value is now canonical: meta.json on the resolved branch
    # reflects the override, so every other target_branch consumer converges
    # on it too (DIRECTIVE_044 -- single canonical authority, no side-channel
    # override left dangling only in this command's local variable).
    meta_show = subprocess.run(
        ["git", "show", f"{FEATURE_BRANCH}:kitty-specs/{MISSION_SLUG}/meta.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(meta_show)["target_branch"] == FEATURE_BRANCH


def test_branch_contract_write_ownership_uses_target_mission_checkout(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """The write gate follows the mission directory, not the primary-repo shape.

    #3786: the guard takes the invoking checkout as an injected
    ``CheckoutIdentity`` value object (resolved once at the ``finalize_tasks``
    entrypoint) — no ``chdir`` and no internal-symbol patch needed to make the
    three invocation shapes deterministic.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _enforce_branch_contract_write_ownership
    from specify_cli.core.checkout_identity import CheckoutIdentity, Intent, resolve_checkout_identity
    from typer import Exit

    def _identity(checkout: Path) -> CheckoutIdentity:
        # A real value object resolved from an EXPLICIT checkout path — not the
        # ambient cwd — so a linked worktree honestly reports ``is_owner=False``
        # with the worktree itself as ``invoking_root``.
        return resolve_checkout_identity(checkout, Intent.WRITE)

    repo = protected_target_repo.repo_root
    mission_dir = repo / "kitty-specs" / "issue-3466-write-ownership"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "kitty-specs/issue-3466-write-ownership")
    _git(repo, "commit", "-q", "-m", "seed write-ownership mission")

    owner = repo.parent / "write-ownership-owner"
    foreign = repo.parent / "write-ownership-foreign"
    _git(repo, "worktree", "add", "-q", "-b", "op/write-ownership-owner", str(owner))
    _git(repo, "worktree", "add", "-q", "-b", "op/write-ownership-foreign", str(foreign))

    owner_mission = owner / "kitty-specs" / "issue-3466-write-ownership"
    _enforce_branch_contract_write_ownership(
        owner_mission, invocation_identity=_identity(owner), json_output=False
    )

    with pytest.raises(Exit):
        _enforce_branch_contract_write_ownership(
            owner_mission, invocation_identity=_identity(foreign), json_output=False
        )

    with pytest.raises(Exit):
        _enforce_branch_contract_write_ownership(
            mission_dir, invocation_identity=_identity(owner), json_output=False
        )


# ---------------------------------------------------------------------------
# SK3466-R-001: a failed downstream validation gate must not leave the
# --target-branch persist dangling, uncommitted, in the working tree.
# ---------------------------------------------------------------------------

R001_MISSION_SLUG = "issue-3466-r001-revert-on-failure"
R001_FEATURE_BRANCH = "kitty/mission-issue-3466-r001-lane-01"


def _scaffold_mission_pinned_to_main_without_tasks_dir(repo: Path) -> Path:
    """Same shape as ``_scaffold_mission_pinned_to_main`` but with NO ``tasks/`` dir.

    Reproduces SK3466-R-001's evidence: the missing-``tasks_dir`` gate
    (mission_finalize.py's ``if not tasks_dir.exists()`` check) fires AFTER
    ``_persist_target_branch_override`` has already rewritten meta.json on
    disk, so it is a real downstream-gate failure that happens strictly
    after the persist.
    """
    feature_dir = repo / "kitty-specs" / R001_MISSION_SLUG
    feature_dir.mkdir(parents=True)

    meta = {
        "slug": R001_MISSION_SLUG,
        "mission_slug": R001_MISSION_SLUG,
        "friendly_name": "Issue 3466 R-001 revert on failure",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
        "mission_id": "01ISSUE3466R001REVERT00001",
        "mid8": "01ISSUR1",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed R-001 mission pinned to main, no tasks dir")

    _git(repo, "checkout", "-q", "-b", R001_FEATURE_BRANCH)

    return feature_dir


def test_failed_downstream_gate_reverts_uncommitted_target_branch_persist(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """SK3466-R-001: a run that fails AFTER the persist must not leave meta.json dirty.

    ``_persist_target_branch_override`` rewrites meta.json to disk as soon as
    the override differs from the on-disk value -- well before the
    "Tasks directory not found" gate (and ~7 other validation gates) that can
    still raise ``typer.Exit(1)``. Before the fix, a failure there left
    meta.json mutated and UNCOMMITTED in the working tree: ``git status
    --porcelain`` showed ``M kitty-specs/<slug>/meta.json`` and the on-disk
    file's ``target_branch`` already read the override value, even though the
    command exited 1 and never committed anything.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()

    feature_dir = _scaffold_mission_pinned_to_main_without_tasks_dir(repo)
    meta_path = feature_dir / "meta.json"
    original_meta_text = meta_path.read_text(encoding="utf-8")

    result = _run_finalize_with_override(repo, R001_FEATURE_BRANCH, mission_slug=R001_MISSION_SLUG)

    assert result.exit_code == 1, (
        f"expected the missing-tasks_dir gate to fail the run (exit {result.exit_code}):\n{result.output}"
    )
    assert "Tasks directory not found" in result.output, result.output

    # The working tree must show NO uncommitted mutation of meta.json --
    # either it was never written, or it was written and then reverted.
    status_out = subprocess.run(
        ["git", "status", "--porcelain", "--", f"kitty-specs/{R001_MISSION_SLUG}/meta.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status_out.strip() == "", (
        f"meta.json was left dirty/uncommitted after a failed finalize-tasks run:\n{status_out}"
    )

    # The on-disk content must be byte-identical to what was committed --
    # the override must not have silently taken effect without a commit.
    assert meta_path.read_text(encoding="utf-8") == original_meta_text
    assert json.loads(meta_path.read_text(encoding="utf-8"))["target_branch"] == "main"


# ---------------------------------------------------------------------------
# SK3466-RR-001: a dangling, uncommitted meta.json write left by a PRIOR
# crashed finalize-tasks run must not be silently skipped when a LATER run's
# own --target-branch override happens to match that dangling value.
# ---------------------------------------------------------------------------

RR001_MISSION_SLUG = "issue-3466-rr001-dangling-meta"
RR001_FEATURE_BRANCH = "kitty/mission-issue-3466-rr001-lane-01"


def _scaffold_mission_pinned_to_main_rr001(repo: Path) -> Path:
    """Same shape as ``_scaffold_mission_pinned_to_main`` -- a full, valid mission.

    Unlike the R-001 scaffold (no ``tasks/`` dir, deliberately fails a
    downstream gate), this mission is complete so the run can succeed
    end-to-end -- the point of SK3466-RR-001 is what happens to a DANGLING
    meta.json write on a run that otherwise SUCCEEDS.
    """
    feature_dir = repo / "kitty-specs" / RR001_MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "slug": RR001_MISSION_SLUG,
        "mission_slug": RR001_MISSION_SLUG,
        "friendly_name": "Issue 3466 RR-001 dangling meta.json",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
        "mission_id": "01ISSUE3466RR001DANGLING01",
        "mid8": "01ISSRR1",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_rr001_wp01/**\n"
        "authoritative_surface: src/module_rr001_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed RR-001 mission pinned to main")

    _git(repo, "checkout", "-q", "-b", RR001_FEATURE_BRANCH)

    return feature_dir


def test_dangling_uncommitted_meta_write_is_folded_into_finalize_commit(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """SK3466-RR-001: a retry with the SAME override as a dangling prior write must commit it.

    Simulates a prior finalize-tasks run that persisted ``--target-branch``
    into meta.json (rewriting ``target_branch`` on disk) but crashed/was
    killed before ``_commit_finalize_artifacts`` folded that write into a
    commit -- leaving meta.json dirty in the working tree. A SECOND
    finalize-tasks run, invoked with the SAME override value, must still fold
    that dangling edit into ITS finalize commit even though
    ``_persist_target_branch_override`` sees ``previous_value == target_
    branch`` and treats its OWN persist call as a no-op (nothing to
    (re)write). Before the fix, meta.json's inclusion in the finalize commit
    was gated entirely on THIS invocation's own persist outcome, so the
    dangling write from the earlier crashed run was never swept up: the
    command exited 0, reported ``"result": "success"``, and meta.json stayed
    dirty forever.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()

    feature_dir = _scaffold_mission_pinned_to_main_rr001(repo)
    meta_path = feature_dir / "meta.json"

    # Simulate the crashed prior run: meta.json already rewritten to the
    # override value, but never committed -- a real dirty working tree.
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["target_branch"] = RR001_FEATURE_BRANCH
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")

    dirty_status_before = subprocess.run(
        ["git", "status", "--porcelain", "--", f"kitty-specs/{RR001_MISSION_SLUG}/meta.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert dirty_status_before.strip(), "test setup did not actually leave meta.json dirty"

    result = _run_finalize_with_override(repo, RR001_FEATURE_BRANCH, mission_slug=RR001_MISSION_SLUG)

    assert result.exit_code == 0, (
        f"finalize-tasks with a --target-branch matching a dangling prior "
        f"write must still succeed (exit {result.exit_code}):\n{result.output}"
    )

    # The dangling edit must now be durable git history, not a working-tree
    # mutation left dirty forever.
    dirty_status_after = subprocess.run(
        ["git", "status", "--porcelain", "--", f"kitty-specs/{RR001_MISSION_SLUG}/meta.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert dirty_status_after.strip() == "", (
        f"meta.json is still dirty/uncommitted after finalize-tasks reported "
        f"success -- the dangling override was silently skipped:\n{dirty_status_after}"
    )

    committed_meta = subprocess.run(
        ["git", "show", f"HEAD:kitty-specs/{RR001_MISSION_SLUG}/meta.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(committed_meta)["target_branch"] == RR001_FEATURE_BRANCH


# ---------------------------------------------------------------------------
# SK3466-R-002: a --json caller must get an explicit diagnostic when the
# meta.json persist itself fails (as opposed to silently no-op'ing).
# ---------------------------------------------------------------------------


def test_persist_target_branch_override_surfaces_write_failure_in_json_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SK3466-R-002: a failed persist must be attributable, even under --json.

    Before the fix, ``_persist_target_branch_override``'s except clause only
    ever printed a Rich warning gated on ``not json_output``; a ``--json``
    caller got ZERO diagnostic when ``set_target_branch`` raised (e.g.
    because meta.json is missing another required field -- a realistic shape
    for the legacy-mission population this escape hatch is documented to
    serve). The bare ``bool`` return also could not distinguish that failure
    from the harmless "already correct" no-op.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _persist_target_branch_override

    feature_dir = tmp_path / "kitty-specs" / "r002-legacy-mission"
    feature_dir.mkdir(parents=True)
    # Missing "friendly_name" (a REQUIRED_FIELDS entry) -- write_meta's
    # validate_meta rejects this, so set_target_branch raises ValueError.
    incomplete_meta = {
        "slug": "r002-legacy-mission",
        "mission_slug": "r002-legacy-mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
    }
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps(incomplete_meta) + "\n", encoding="utf-8")

    outcome = _persist_target_branch_override(
        feature_dir,
        "kitty/real-feature-branch",
        target_branch_override="kitty/real-feature-branch",
        json_output=True,
    )

    assert outcome.persisted is False
    assert outcome.previous_value == "main"
    assert outcome.persist_error, "a --json caller must be able to tell a write FAILURE apart from a no-op"

    captured = capsys.readouterr()
    assert captured.out.strip(), "a --json caller got zero diagnostic for the failed persist"
    last_line = captured.out.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload.get("warning") == "target_branch_override_not_persisted"
    assert payload.get("target_branch_override") == "kitty/real-feature-branch"

    # The failed write must not have partially applied.
    on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk["target_branch"] == "main"


def test_persist_target_branch_override_surfaces_corrupt_meta_json_as_structured_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SK3466-RR-002: a CORRUPT (not just field-incomplete) meta.json must also be attributable.

    Before the fix, ``_persist_target_branch_override``'s except tuple was
    ``(FileNotFoundError, ValueError)`` -- it did not cover
    ``MissionMetaReadError`` (a ``RuntimeError`` subclass,
    ``core/paths.py``), which ``set_target_branch`` -> ``_require_meta`` ->
    ``_load_meta_fail_closed`` raises when meta.json EXISTS but is corrupt /
    malformed JSON. A realistic shape for the legacy-mission population this
    ``--target-branch`` escape hatch is explicitly documented to serve. When
    it fired, the structured ``{"warning": "target_branch_override_not_
    persisted", ...}`` diagnostic contract was bypassed entirely and the
    exception propagated uncaught out of this function.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _persist_target_branch_override

    feature_dir = tmp_path / "kitty-specs" / "rr002-corrupt-meta"
    feature_dir.mkdir(parents=True)
    meta_path = feature_dir / "meta.json"
    # Malformed JSON (truncated) -- `load_meta_or_empty`'s "empty" contract
    # silently returns {} for `previous_value` (so the no-op-comparison arm
    # does not short-circuit before reaching `set_target_branch`), but
    # `set_target_branch`'s OWN fail-closed re-read of the same file raises
    # MissionMetaReadError.
    meta_path.write_text('{"target_branch": "main", "slug": ', encoding="utf-8")

    outcome = _persist_target_branch_override(
        feature_dir,
        "kitty/real-feature-branch",
        target_branch_override="kitty/real-feature-branch",
        json_output=True,
    )

    assert outcome.persisted is False
    assert outcome.persist_error, (
        "a corrupt meta.json must surface as an attributable persist failure, "
        "not an uncaught exception"
    )

    captured = capsys.readouterr()
    assert captured.out.strip(), "a --json caller got zero diagnostic for the corrupt-meta.json persist failure"
    last_line = captured.out.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload.get("warning") == "target_branch_override_not_persisted"
    assert payload.get("target_branch_override") == "kitty/real-feature-branch"

    # The corrupt file must be left untouched -- no partial write.
    assert meta_path.read_text(encoding="utf-8") == '{"target_branch": "main", "slug": '


# ---------------------------------------------------------------------------
# SK3466-RR-003: a failure in the REVERT write itself must not propagate as
# a second, unrelated, uncaught exception -- it must be reported alongside
# the original error, never left silent, never a raw traceback.
# ---------------------------------------------------------------------------


def test_meta_json_delta_is_finalize_attributable_unit(tmp_path: Path) -> None:
    """SK3466-REV-001 unit coverage for ``_meta_json_delta_is_finalize_attributable``.

    Exercises each branch directly against a small REAL git repo (no mocks):
    a foreign-only field delta must be rejected, a ``target_branch``-only
    delta (this run's own write, or a dangling one) must be accepted, a
    MIXED delta (both) must be rejected -- the whole file, not just the
    foreign field -- and a meta.json never committed at HEAD must be
    accepted (nothing to attribute against).
    """
    from specify_cli.cli.commands.agent.mission_finalize import (
        _meta_json_delta_is_finalize_attributable,
    )

    repo = tmp_path
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    meta_path = repo / "meta.json"
    committed_meta = {
        "slug": "rev001-unit",
        "target_branch": "main",
        "vcs": "git",
        "vcs_locked_at": "2026-08-01T00:00:00+00:00",
    }
    meta_path.write_text(json.dumps(committed_meta), encoding="utf-8")
    _git(repo, "add", "meta.json")
    _git(repo, "commit", "-q", "-m", "seed committed meta.json")

    # target_branch-only delta (this run's own persist, or a dangling one
    # from an earlier crashed finalize-tasks run) -- attributable.
    only_target_branch = dict(committed_meta, target_branch="kitty/feature")
    meta_path.write_text(json.dumps(only_target_branch), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(meta_path, repo) is True

    # foreign-only delta (mimics `implement --no-auto-commit`'s vcs-lock
    # write) -- NOT attributable to finalize-tasks.
    only_foreign = dict(committed_meta, vcs_locked_at="2026-08-15T00:00:00+00:00")
    meta_path.write_text(json.dumps(only_foreign), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(meta_path, repo) is False

    # Mixed delta: both a target_branch change AND a foreign field change
    # pending simultaneously -- the WHOLE file is excluded, not just the
    # foreign field (no partial-file commit).
    mixed = dict(committed_meta, target_branch="kitty/feature", vcs_locked_at="2026-08-15T00:00:00+00:00")
    meta_path.write_text(json.dumps(mixed), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(meta_path, repo) is False

    # No delta at all -- trivially attributable (subset of the empty set).
    meta_path.write_text(json.dumps(committed_meta), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(meta_path, repo) is True

    # Never committed at HEAD -- nothing to diff against, so the whole file
    # is new content, not a foreign edit riding alongside ours.
    new_meta_path = repo / "brand-new-meta.json"
    new_meta_path.write_text(json.dumps({"target_branch": "main", "vcs": "git"}), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(new_meta_path, repo) is True


def test_meta_json_delta_attribution_is_side_specific_on_decode_failure(tmp_path: Path) -> None:
    """#3466 landing: a malformed WORKING-TREE meta.json is EXCLUDED; a malformed
    HEAD copy with a valid working-tree copy is INCLUDED.

    finalize-tasks did NOT commit meta.json before this change, so the
    conservative default for a corrupt on-disk file is to never commit it --
    committing a truncated meta.json would break every fail-closed reader. The
    two directions are asymmetric: an unreadable committed (HEAD) copy is
    superseded by our valid working-tree fix, so that direction still includes.
    Reverting either branch to the pre-landing unconditional ``True`` reds this.
    """
    from specify_cli.cli.commands.agent.mission_finalize import (
        _meta_json_delta_is_finalize_attributable,
    )

    valid = {"slug": "decode-unit", "target_branch": "main", "vcs": "git"}

    # (a) Working-tree copy truncated mid-write (crash) while HEAD is valid
    # -> EXCLUDE: never commit a corrupt file over fail-closed readers.
    wt_repo = tmp_path / "wt_malformed"
    wt_repo.mkdir()
    _git(wt_repo, "init", "-q")
    _git(wt_repo, "config", "user.email", "test@example.com")
    _git(wt_repo, "config", "user.name", "Test")
    wt_meta = wt_repo / "meta.json"
    wt_meta.write_text(json.dumps(valid), encoding="utf-8")
    _git(wt_repo, "add", "meta.json")
    _git(wt_repo, "commit", "-q", "-m", "seed valid meta.json")
    wt_meta.write_text('{"target_branch": "kitty/feature", "vcs": "gi', encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(wt_meta, wt_repo) is False

    # (b) Committed (HEAD) copy malformed but working-tree copy valid
    # -> INCLUDE: the corrective write supersedes a bad HEAD.
    head_repo = tmp_path / "head_malformed"
    head_repo.mkdir()
    _git(head_repo, "init", "-q")
    _git(head_repo, "config", "user.email", "test@example.com")
    _git(head_repo, "config", "user.name", "Test")
    head_meta = head_repo / "meta.json"
    head_meta.write_text('{"target_branch": "main", "vcs": "gi', encoding="utf-8")
    _git(head_repo, "add", "meta.json")
    _git(head_repo, "commit", "-q", "-m", "seed malformed HEAD meta.json")
    head_meta.write_text(json.dumps(valid), encoding="utf-8")
    assert _meta_json_delta_is_finalize_attributable(head_meta, head_repo) is True


# ---------------------------------------------------------------------------
# SK3466-REV-001: a foreign meta.json edit made by a DIFFERENT command
# (mimicking `implement --no-auto-commit`'s vcs-lock write) must NOT be
# silently swept into a finalize-tasks commit just because it happens to be
# dirty at the same time as finalize-tasks' own artifacts.
# ---------------------------------------------------------------------------

REV001_MISSION_SLUG = "issue-3466-rev001-foreign-meta-edit"
REV001_FEATURE_BRANCH = "kitty/mission-issue-3466-rev001-lane-01"


def _scaffold_mission_on_own_target_branch(repo: Path, mission_slug: str, feature_branch: str) -> Path:
    """A complete mission whose meta.json ALREADY names ``feature_branch``.

    Unlike the override-repro scaffolds above, ``target_branch`` matches the
    checkout -- no ``--target-branch`` override is needed, isolating the
    foreign-field-attribution behavior from the override-persist behavior
    those other tests already cover.
    """
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Issue 3466 REV-001 foreign meta edit",
        "mission_type": "software-dev",
        "target_branch": feature_branch,
        "created_at": "2026-08-01T00:00:00+00:00",
        "mission_id": "01ISSUE3466REV001FOREIGN01",
        "mid8": "01ISREV1",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_rev001_wp01/**\n"
        "authoritative_surface: src/module_rev001_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", f"seed {mission_slug} pinned to its own target branch")

    _git(repo, "checkout", "-q", "-b", feature_branch)

    return feature_dir


def _run_finalize_no_override(repo: Path, *, mission_slug: str) -> Result:
    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        return runner.invoke(
            app,
            ["finalize-tasks", "--mission", mission_slug, "--json"],
            catch_exceptions=False,
        )


def test_foreign_meta_json_edit_is_not_swept_into_finalize_commit(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """SK3466-REV-001: a foreign (non-finalize-tasks) meta.json edit must survive uncommitted.

    Simulates ``implement --no-auto-commit``'s real, documented behavior:
    ``_ensure_vcs_in_meta`` writes ``vcs``/``vcs_locked_at`` into meta.json
    unconditionally on a WP's first claim, but ``_commit_wp_claim_status``
    explicitly gates the COMMIT of that write on ``auto_commit`` -- with
    ``--no-auto-commit``, the write lands on disk but is deliberately left
    staged/uncommitted. Before this fix, ``_collect_finalize_artifacts``'s
    unconditional meta.json sweep (RR-001) meant a LATER, unrelated
    finalize-tasks run silently folded that foreign write into its own
    commit. This asserts finalize-tasks still succeeds, but the foreign
    ``vcs``/``vcs_locked_at`` write is NOT part of its commit -- it remains
    exactly as dirty as ``implement --no-auto-commit`` left it.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()

    feature_dir = _scaffold_mission_on_own_target_branch(repo, REV001_MISSION_SLUG, REV001_FEATURE_BRANCH)
    meta_path = feature_dir / "meta.json"

    # Simulate `implement --no-auto-commit`'s real, unconditional vcs-lock
    # write (`_ensure_vcs_in_meta` -> `set_vcs_lock`) -- a real dirty
    # working tree, target_branch untouched.
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = "2026-08-15T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")

    rel_meta_path = f"kitty-specs/{REV001_MISSION_SLUG}/meta.json"
    dirty_status_before = subprocess.run(
        ["git", "status", "--porcelain", "--", rel_meta_path],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert dirty_status_before.strip(), "test setup did not actually leave meta.json dirty"

    result = _run_finalize_no_override(repo, mission_slug=REV001_MISSION_SLUG)

    assert result.exit_code == 0, (
        f"finalize-tasks must still succeed alongside an unrelated, foreign "
        f"meta.json edit (exit {result.exit_code}):\n{result.output}"
    )

    # The foreign edit must NOT have been folded into finalize-tasks' commit:
    # meta.json must still show as dirty (the vcs write is still pending).
    dirty_status_after = subprocess.run(
        ["git", "status", "--porcelain", "--", rel_meta_path],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert dirty_status_after.strip(), (
        "a foreign meta.json edit (vcs/vcs_locked_at) was silently swept "
        f"into the finalize-tasks commit -- meta.json is clean when it must "
        f"still carry the pending foreign write:\n{dirty_status_after!r}"
    )

    committed_meta = json.loads(
        subprocess.run(
            ["git", "show", f"HEAD:{rel_meta_path}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert "vcs" not in committed_meta, "the foreign vcs write must not appear in finalize-tasks' own commit"
    assert "vcs_locked_at" not in committed_meta

    # The on-disk foreign write is preserved untouched (not reverted either --
    # only finalize-tasks' OWN unpersisted writes get reverted on failure;
    # this run succeeded and the foreign write was never finalize-tasks' to
    # revert).
    on_disk_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk_meta["vcs"] == "git"
    assert on_disk_meta["vcs_locked_at"] == "2026-08-15T00:00:00+00:00"


def test_revert_unpersisted_target_branch_override_reports_its_own_write_failure(
    tmp_path: Path,
) -> None:
    """SK3466-RR-003: the revert's own write failure must surface, not raise.

    Before the fix, ``_revert_unpersisted_target_branch_override``'s
    ``meta_path.write_text(...)`` call had no error handling at all. Called
    from inside ``finalize_tasks``'s own ``except`` blocks (with no
    surrounding try/except there), a NEW exception raised from this
    function -- e.g. the TOCTOU class this module already reasons about,
    meta.json's parent replaced/removed between the persist and the revert
    attempt -- would propagate out of ``finalize_tasks`` entirely uncaught,
    replacing the graceful ``{"error": str(e)}`` JSON contract with an
    unhandled Python traceback for a ``--json`` caller.

    Reproduced here by pointing ``meta_path`` at a DIRECTORY (not a file):
    ``Path.write_text`` raises ``IsADirectoryError`` (an ``OSError``
    subclass) in that case -- a real, not contrived, write failure.
    """
    from specify_cli.cli.commands.agent.mission_finalize import (
        _MetaBranchOverrideProgress,
        _revert_unpersisted_target_branch_override,
    )

    meta_path_that_is_a_directory = tmp_path / "meta.json"
    meta_path_that_is_a_directory.mkdir()

    revert_error = _revert_unpersisted_target_branch_override(
        meta_path_that_is_a_directory,
        "original meta.json content",
        meta_json_persisted=True,
        meta_commit_progress=_MetaBranchOverrideProgress(committed=False),
    )

    assert revert_error is not None, (
        "a failed revert write must be reported to the caller, not silently swallowed"
    )
    assert isinstance(revert_error, str) and revert_error.strip()


# ---------------------------------------------------------------------------
# SK3466-REV2-001/002: round-3 taught ``_commit_finalize_artifacts`` to
# exclude meta.json from the finalize commit entirely when its pending delta
# is MIXED (our own ``target_branch`` write plus a foreign field) -- but two
# call sites downstream of that decision were never updated to learn about
# this third outcome state. These tests reproduce both.
# ---------------------------------------------------------------------------

REV2_001_MISSION_SLUG = "issue-3466-rev2-001-mixed-delta"
REV2_001_FEATURE_BRANCH = "kitty/mission-issue-3466-rev2-001-lane-01"


def _scaffold_mission_pinned_to_main_rev2_001(repo: Path) -> Path:
    """Same full-mission shape as the RR-001 scaffold, pinned to ``main``."""
    feature_dir = repo / "kitty-specs" / REV2_001_MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "slug": REV2_001_MISSION_SLUG,
        "mission_slug": REV2_001_MISSION_SLUG,
        "friendly_name": "Issue 3466 REV2-001 mixed-delta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-01T00:00:00+00:00",
        "mission_id": "01ISSUE3466REV2001MIXED01",
        "mid8": "01ISRV21",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_rev2001_wp01/**\n"
        "authoritative_surface: src/module_rev2001_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed REV2-001 mission pinned to main")

    _git(repo, "checkout", "-q", "-b", REV2_001_FEATURE_BRANCH)

    return feature_dir


def test_downstream_failure_after_mixed_delta_exclusion_still_reverts_target_branch_override(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """SK3466-REV2-001: a downstream failure after a MIXED-delta exclusion must still revert.

    Composite regression for the round-2 finding: an active --target-branch
    override is persisted into meta.json WHILE a foreign field
    (``vcs``/``vcs_locked_at``, mimicking ``implement --no-auto-commit``) is
    already pending in the same file. ``_meta_json_delta_is_finalize_
    attributable`` correctly excludes meta.json from this commit (the
    whole-file mixed-case rule from SK3466-REV-001) -- but before this fix,
    ``_run_commit_pipeline`` flipped ``meta_commit_progress.committed = True``
    UNCONDITIONALLY right after ``_commit_finalize_artifacts`` returned,
    regardless of that exclusion. When a later step
    (the post-commit success report) then raises, ``finalize_tasks``'s ``except``
    handler's revert guard (``not meta_commit_progress.committed``) was
    fooled into skipping the revert -- leaving the --target-branch write
    dangling, uncommitted, forever. This asserts the override IS reverted:
    meta.json's on-disk ``target_branch`` goes back to ``"main"``, while the
    pre-existing foreign ``vcs``/``vcs_locked_at`` edit (untouched by
    finalize-tasks either way) survives exactly as it was.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()

    feature_dir = _scaffold_mission_pinned_to_main_rev2_001(repo)
    meta_path = feature_dir / "meta.json"

    # A foreign, already-dirty edit pending BEFORE finalize-tasks runs at
    # all -- mimics `implement --no-auto-commit`'s vcs-lock write.
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = "2026-08-15T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    meta_with_foreign_edit_only = meta_path.read_text(encoding="utf-8")

    with patch(
        "specify_cli.cli.commands.agent.mission_finalize._emit_success_report",
        side_effect=RuntimeError("SK3466-REV2-001 test: simulated downstream failure"),
    ):
        result = _run_finalize_with_override(
            repo, REV2_001_FEATURE_BRANCH, mission_slug=REV2_001_MISSION_SLUG
        )

    assert result.exit_code == 1, (
        f"expected the simulated downstream failure to fail the run "
        f"(exit {result.exit_code}):\n{result.output}"
    )

    # The --target-branch override must be REVERTED -- not left dangling as
    # an uncommitted mutation just because meta.json's mixed delta was
    # excluded from this run's commit.
    reverted_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert reverted_meta["target_branch"] == "main", (
        "the --target-branch override was left dangling on disk after a "
        f"downstream failure, instead of being reverted: {reverted_meta}"
    )

    # The pre-existing FOREIGN edit is untouched either way -- finalize-tasks
    # never owned it and must not have reverted or committed it.
    assert reverted_meta["vcs"] == "git"
    assert reverted_meta["vcs_locked_at"] == "2026-08-15T00:00:00+00:00"

    # meta.json must be byte-identical to its state right before the persist
    # call (foreign edit present, no target_branch override).
    assert meta_path.read_text(encoding="utf-8") == meta_with_foreign_edit_only

    # And it must NOT have been committed either -- the exclusion still
    # holds; only the dangling write was undone.
    committed_meta = json.loads(
        subprocess.run(
            ["git", "show", f"HEAD:kitty-specs/{REV2_001_MISSION_SLUG}/meta.json"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert committed_meta["target_branch"] == "main"
    assert "vcs" not in committed_meta


def test_json_payload_signals_persisted_but_not_committed_on_mixed_delta_exclusion(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """SK3466-REV2-002: a --json caller must be able to tell "committed" from "written but dangling".

    Same mixed-delta setup as the REV2-001 revert test above, but the run
    SUCCEEDS end-to-end (no downstream failure injected) -- exactly the case
    ``_meta_json_delta_is_finalize_attributable``'s own docstring says is
    intentionally left dangling ("waits for a future run"). Before this fix,
    the terminal JSON payload's ``target_branch_override.persisted`` field
    was ``true`` with no way to tell that meta.json's write never reached
    this commit: a ``--json`` caller checking ``persisted`` alone -- its
    documented use -- would wrongly conclude the FR-012 escape hatch had
    taken effect.
    """
    repo = protected_target_repo.repo_root
    protected_target_repo.assert_is_spec_kitty_project()

    feature_dir = _scaffold_mission_pinned_to_main_rev2_001(repo)
    meta_path = feature_dir / "meta.json"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = "2026-08-15T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")

    result = _run_finalize_with_override(repo, REV2_001_FEATURE_BRANCH, mission_slug=REV2_001_MISSION_SLUG)

    assert result.exit_code == 0, (
        f"a mixed meta.json delta must not fail the run outright (exit {result.exit_code}):\n{result.output}"
    )

    last_line = result.output.strip().splitlines()[-1]
    payload = json.loads(last_line)
    override_report = payload["target_branch_override"]
    assert override_report.get("persisted") is True, (
        f"the override write itself DID happen this run -- 'persisted' must stay True: {override_report}"
    )
    assert override_report.get("committed") is False, (
        "meta.json's mixed delta was excluded from this commit -- a --json caller must be able to "
        f"tell 'persisted' apart from 'committed': {override_report}"
    )

    # The write is still dangling on disk (by design -- REV-001's own
    # mixed-case rule), and the on-disk target_branch already reads the
    # override even though it never reached git history yet.
    on_disk_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk_meta["target_branch"] == REV2_001_FEATURE_BRANCH
    committed_meta = json.loads(
        subprocess.run(
            ["git", "show", f"HEAD:kitty-specs/{REV2_001_MISSION_SLUG}/meta.json"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert committed_meta["target_branch"] == "main"
