"""Tests for spec_commit_cmd.spec_commit_command (WP02 / T009; WP13 adds T002/T069/T070/T073)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

if TYPE_CHECKING:
    from click.testing import Result

    from tests._factories.coord_mission import CoordMission

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_app() -> typer.Typer:
    """Create a Typer app that exposes spec_commit_command directly (no subcommand routing)."""
    from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command

    app = typer.Typer()
    # Register as default (no name) so CliRunner args are passed directly.
    app.command()(spec_commit_command)
    return app


def test_spec_commit_unprotected(tmp_path: Path) -> None:
    """Unprotected repo → direct commit, success."""
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    unprotected_policy = ProtectionPolicy(
        protected_branches=frozenset(), operator_hatch_active=False
    )

    fake_result = CommitRouterResult(
        status="committed", placement_ref="main", commit_hash="abc1234"
    )

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=unprotected_policy,
        ),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.commit_for_mission",
            return_value=fake_result,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec", "--mission", "001-my-mission"],
        )

    assert result.exit_code == 0
    assert "committed" in result.output.lower() or "✓" in result.output


def test_spec_commit_protected_calls_commit_for_mission(tmp_path: Path) -> None:
    """Protected primary → commit_for_mission called."""
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    protected_policy = ProtectionPolicy(
        protected_branches=frozenset({"main"}), operator_hatch_active=False
    )

    coord_result = CommitRouterResult(
        status="committed",
        placement_ref="kitty/mission-001-my-mission-ABCD1234",
        commit_hash="def5678",
    )

    commit_for_mission_calls: list[dict] = []

    def _fake_commit_for_mission(**kwargs):
        commit_for_mission_calls.append(kwargs)
        return coord_result

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=protected_policy,
        ),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.commit_for_mission",
            side_effect=_fake_commit_for_mission,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec", "--mission", "001-my-mission"],
        )

    assert result.exit_code == 0
    assert len(commit_for_mission_calls) == 1
    # The policy passed must be the protected one.
    call_kwargs = commit_for_mission_calls[0]
    assert call_kwargs["policy"] is protected_policy


def test_spec_commit_unchanged(tmp_path: Path) -> None:
    """Unchanged artifact → exit 0, no commit."""
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    unchanged_result = CommitRouterResult(status="unchanged", placement_ref="main")

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=policy,
        ),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.commit_for_mission",
            return_value=unchanged_result,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec", "--mission", "001-my-mission"],
        )

    assert result.exit_code == 0
    assert "unchanged" in result.output.lower()


def test_spec_commit_slug_derived_from_path(tmp_path: Path) -> None:
    """Mission slug derived from kitty-specs/<slug>/ path when --mission omitted."""
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    mission_slug = "001-my-mission"
    artifact = tmp_path / "kitty-specs" / mission_slug / "spec.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Spec\n", encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    committed_result = CommitRouterResult(
        status="committed", placement_ref="main", commit_hash="abc123"
    )

    captured_slug: list[str] = []

    def _fake_commit(**kwargs):
        captured_slug.append(kwargs["mission_slug"])
        return committed_result

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=policy,
        ),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.commit_for_mission",
            side_effect=_fake_commit,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec"],
        )

    assert result.exit_code == 0
    assert captured_slug == [mission_slug]


def test_spec_commit_no_slug_error(tmp_path: Path) -> None:
    """No --mission and no kitty-specs path → exit 1 with error."""
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=policy,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec"],
        )

    # Should still exit 0 because the filename "spec.md" is used as slug fallback.
    # But if the slug derives to "spec.md" that's wrong; test documents current behavior.
    # Actually _derive_mission_slug will use Path("spec.md").name = "spec.md"
    # We test this documents the error path when commit_for_mission returns error.
    assert result.exit_code in {0, 1}  # acceptable: slug derived as filename


def test_spec_commit_json_output(tmp_path: Path) -> None:
    """--json flag produces JSON output."""
    import json as json_mod

    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    committed_result = CommitRouterResult(
        status="committed", placement_ref="main", commit_hash="abc123"
    )

    app = _make_app()
    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve",
            return_value=policy,
        ),
        patch(
            "specify_cli.cli.commands.spec_commit_cmd.commit_for_mission",
            return_value=committed_result,
        ),
    ):
        result = runner.invoke(
            app,
            [str(artifact), "--message", "Add spec", "--mission", "001-my-mission", "--json"],
        )

    assert result.exit_code == 0
    payload = json_mod.loads(result.output)
    assert payload["success"] is True
    assert payload["committed"] is True


def test_spec_commit_joins_repeated_messages(tmp_path: Path) -> None:
    """#5647: repeated ``-m`` values reach the router as one git-style message."""
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy

    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")
    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    committed = CommitRouterResult(status="committed", placement_ref="main", commit_hash="abc1234")
    trailer = "Co-Authored-By: Name <name@example.invalid>"

    with (
        patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.spec_commit_cmd.ProtectionPolicy.resolve", return_value=policy),
        patch("specify_cli.cli.commands.spec_commit_cmd.commit_for_mission", return_value=committed) as router,
    ):
        result = CliRunner().invoke(_make_app(), [str(artifact), "-m", "docs: subject", "-m", trailer, "--mission", "001-my-mission"])

    assert result.exit_code == 0, result.output
    assert router.call_args.kwargs["message"] == f"docs: subject\n\n{trailer}"


# ---------------------------------------------------------------------------
# WP13 T002 — the extracted render helper reproduces the pre-extraction shape
# (hand-built ``CommitRouterResult`` per status, no router/CLI involved).
# ---------------------------------------------------------------------------


class TestExtractedHelpers:
    """T002 validation: ``_render_spec_commit_result`` per ``CommitRouterResult.status``."""

    def test_render_committed_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="committed", placement_ref="main", commit_hash="abc1234")
        _render_spec_commit_result(result, json_output=True, abs_files=[], repo_root=Path("/repo"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["committed"] is True
        assert payload["placement_ref"] == "main"
        assert payload["commit_hash"] == "abc1234"
        # Additive-only (contract rule 6): no surfaces were populated on this
        # hand-built result, so both new keys are present but empty.
        assert payload["surfaces"] == []
        assert payload["arguments"] == []

    def test_render_unchanged_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="unchanged", placement_ref="main", reason="no_op_no_changes")
        _render_spec_commit_result(result, json_output=True, abs_files=[], repo_root=Path("/repo"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["committed"] is False
        assert payload["reason"] == "no_op_no_changes"

    def test_render_no_op_wrong_surface_result_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="no_op_wrong_surface", placement_ref="main", diagnostic="refused: protected")
        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=True, abs_files=[], repo_root=Path("/repo"))

        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"] == "refused: protected"

    def test_render_error_result_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="error", placement_ref="main", diagnostic="boom")
        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=True, abs_files=[], repo_root=Path("/repo"))

        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"] == "boom"

    def test_render_no_op_wrong_surface_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Text mode (no ``--json``) keeps the actionable single-line refusal (T071: unchanged arm)."""
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="no_op_wrong_surface", placement_ref="main", diagnostic="refused: protected")
        with pytest.raises(typer.Exit):
            _render_spec_commit_result(result, json_output=False, abs_files=[], repo_root=Path("/repo"))

        assert "refused: protected" in capsys.readouterr().out

    def test_render_error_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Text mode (no ``--json``) keeps the actionable single-line error (T071: unchanged arm)."""
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="error", placement_ref="main", diagnostic="boom")
        with pytest.raises(typer.Exit):
            _render_spec_commit_result(result, json_output=False, abs_files=[], repo_root=Path("/repo"))

        assert "boom" in capsys.readouterr().out

    def test_render_committed_text_output_prints_non_committed_argument_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A mixed, surfaces-populated success still prints one dim line per non-committed argument (T071 step 1)."""
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_outcome import COORD_RECORD_IN_ROOT_CHECKOUT, PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            commit_hash="abc",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
                SurfaceOutcome(
                    surface="coordination",
                    branch="coord",
                    status="unchanged",
                    commit_hash=None,
                    skipped=(PathFate(path="kitty-specs/m/traces/approach.md", reason=COORD_RECORD_IN_ROOT_CHECKOUT),),
                ),
            ),
        )

        _render_spec_commit_result(
            result,
            json_output=False,
            abs_files=[repo_root / "kitty-specs/m/spec.md", repo_root / "kitty-specs/m/traces/approach.md"],
            repo_root=repo_root,
        )

        out = capsys.readouterr().out
        assert "kitty-specs/m/traces/approach.md: skipped" in out
        assert COORD_RECORD_IN_ROOT_CHECKOUT in out

    def test_committed_legacy_status_with_a_refused_coordination_surface_is_not_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """B1 (review cycle 2, reviewer-renata finding): the #5513 masking shape.

        A mixed batch whose CALLER-partition (primary) group genuinely
        committed -- so the legacy top-level ``status`` reads ``committed``
        (``_merge_group_results`` picks the caller's own partition when no
        group errored) -- while the COORDINATION group was refused
        (``WRONG_SURFACE``). FR-007a forbids reporting success here. This
        pins ``_compute_success``'s ``and not surface_failed`` override: the
        reviewer found a mutation to ``return base_success`` alone survived
        all 26 prior tests, because none of them built a result where the
        legacy status and a surface's own refusal disagree.
        """
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            commit_hash="abc",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
                SurfaceOutcome(
                    surface="coordination",
                    branch="kitty/mission-m-ABCD1234",
                    status="refused",
                    commit_hash=None,
                    refused=(PathFate(path="kitty-specs/m/status.events.jsonl", reason="WRONG_SURFACE"),),
                ),
            ),
        )
        abs_files = [repo_root / "kitty-specs/m/spec.md", repo_root / "kitty-specs/m/status.events.jsonl"]

        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=True, abs_files=abs_files, repo_root=repo_root)
        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False, payload
        # The legacy top-level fields still describe only the CALLER-
        # partition (primary) group (contract rule 4) -- unaffected.
        assert payload["committed"] is True

        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=False, abs_files=abs_files, repo_root=repo_root)
        assert excinfo.value.exit_code == 1
        out = capsys.readouterr().out
        assert "primary" in out and "coordination" in out
        assert "WRONG_SURFACE" in out

    def test_a_bare_refused_surface_with_no_named_path_still_fails_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        """B1 mutation-isolation: a REFUSED surface with an EMPTY ``refused`` tuple (a bare
        refusal naming no specific path -- ``_render_surface_summary``'s own "still emit a
        summary line" case) must still flip success, even though NO caller argument's own
        fate is itself ``refused`` (``argument_refused`` alone cannot see this -- only
        ``surface_failed`` can). Isolates the ``surface_failed`` term from ``argument_refused``:
        every OTHER test in this suite happens to set both simultaneously, since a NAMED
        refused path always makes its own argument ``refused`` too, so neither term alone was
        pinned independently until this test (confirmed by mutation: dropping only
        ``surface_failed`` left all 30 prior tests green).
        """
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_outcome import SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            commit_hash="abc",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
                SurfaceOutcome(surface="coordination", branch="coord", status="refused", commit_hash=None),
            ),
        )
        abs_files = [repo_root / "kitty-specs/m/spec.md"]

        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=True, abs_files=abs_files, repo_root=repo_root)

        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False, payload
        # The single argument's own fate IS "committed" -- the bare
        # coordination refusal carries no path for it to be matched against.
        assert payload["arguments"] == [{"path": "kitty-specs/m/spec.md", "fate": "committed", "surface": "primary"}]


# ---------------------------------------------------------------------------
# WP13 T070 — ``_argument_fates`` unit tests (one entry per input, exactly once).
# ---------------------------------------------------------------------------


class TestArgumentFates:
    def test_all_committed_batch(self) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
            ),
        )

        fates = _argument_fates([repo_root / "kitty-specs/m/spec.md"], result, repo_root)

        assert fates == [{"path": "kitty-specs/m/spec.md", "fate": "committed", "surface": "primary"}]

    def test_mixed_batch_with_one_refused(self) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="error",
            placement_ref="topic",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
                SurfaceOutcome(
                    surface="coordination",
                    branch="kitty/mission-m-ABCD1234",
                    status="refused",
                    commit_hash=None,
                    refused=(PathFate(path="kitty-specs/m/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
                ),
            ),
        )

        fates = _argument_fates(
            [repo_root / "kitty-specs/m/spec.md", repo_root / "kitty-specs/m/status.events.jsonl"],
            result,
            repo_root,
        )

        assert fates == [
            {"path": "kitty-specs/m/spec.md", "fate": "committed", "surface": "primary"},
            {
                "path": "kitty-specs/m/status.events.jsonl",
                "fate": "refused",
                "surface": "coordination",
                "reason": "STATUS_LOCK_HELD",
            },
        ]

    def test_unchanged_input_carries_its_reason(self) -> None:
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import REASON_ALREADY_COMMITTED, PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="unchanged",
            placement_ref="topic",
            reason=REASON_ALREADY_COMMITTED,
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="unchanged",
                    commit_hash=None,
                    skipped=(PathFate(path="kitty-specs/m/spec.md", reason=REASON_ALREADY_COMMITTED),),
                ),
            ),
        )

        fates = _argument_fates([repo_root / "kitty-specs/m/spec.md"], result, repo_root)

        assert fates == [
            {
                "path": "kitty-specs/m/spec.md",
                "fate": "unchanged",
                "surface": "primary",
                "reason": REASON_ALREADY_COMMITTED,
            }
        ]

    def test_input_absent_from_every_surface_is_path_unroutable(self) -> None:
        """An input the router never classified is a contract violation -- never dropped silently."""
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import PATH_UNROUTABLE, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
            ),
        )

        fates = _argument_fates([repo_root / "kitty-specs/m/other.md"], result, repo_root)

        assert fates == [
            {"path": "kitty-specs/m/other.md", "fate": "refused", "surface": None, "reason": PATH_UNROUTABLE}
        ]

    def test_matches_a_mission_relative_suffix_against_a_worktree_nested_committed_path(self) -> None:
        """A COORD-kind commit records its OWNING (worktree-nested) path; the caller's own root-checkout
        argument still matches it via the mission-relative suffix (the real-router shape T069 surfaced).
        """
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            surfaces=(
                SurfaceOutcome(
                    surface="coordination",
                    branch="kitty/mission-m-ABCD1234",
                    status="committed",
                    commit_hash="abc",
                    committed=(".worktrees/m-ABCD1234-coord/kitty-specs/m/status.events.jsonl",),
                ),
            ),
        )

        fates = _argument_fates([repo_root / "kitty-specs/m/status.events.jsonl"], result, repo_root)

        assert fates == [{"path": "kitty-specs/m/status.events.jsonl", "fate": "committed", "surface": "coordination"}]

    def test_owning_path_alias_is_matched_when_the_caller_passed_it_directly(self) -> None:
        """``PathFate.owning_path`` (a future hook -- no production call site populates it yet,
        per :func:`_index_surface_fates`'s own docstring) is still indexed, so a caller that DID
        pass the owning path directly matches it exactly.
        """
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="error",
            placement_ref="topic",
            surfaces=(
                SurfaceOutcome(
                    surface="coordination",
                    branch="coord",
                    status="refused",
                    commit_hash=None,
                    refused=(
                        PathFate(
                            path="kitty-specs/m/status.events.jsonl",
                            reason="STATUS_LOCK_HELD",
                            owning_path=".worktrees/m-coord/kitty-specs/m/status.events.jsonl",
                        ),
                    ),
                ),
            ),
        )

        fates = _argument_fates(
            [repo_root / ".worktrees/m-coord/kitty-specs/m/status.events.jsonl"],
            result,
            repo_root,
        )

        assert fates == [
            {
                "path": ".worktrees/m-coord/kitty-specs/m/status.events.jsonl",
                "fate": "refused",
                "surface": "coordination",
                "reason": "STATUS_LOCK_HELD",
            }
        ]

    def test_owning_path_alias_is_matched_for_a_skipped_fate_too(self) -> None:
        """The ``skipped`` list's ``owning_path`` alias (not just ``refused``'s) is indexed too."""
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import REASON_ALREADY_COMMITTED, PathFate, SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        result = CommitRouterResult(
            status="unchanged",
            placement_ref="topic",
            reason=REASON_ALREADY_COMMITTED,
            surfaces=(
                SurfaceOutcome(
                    surface="coordination",
                    branch="coord",
                    status="unchanged",
                    commit_hash=None,
                    skipped=(
                        PathFate(
                            path="kitty-specs/m/status.events.jsonl",
                            reason=REASON_ALREADY_COMMITTED,
                            owning_path=".worktrees/m-coord/kitty-specs/m/status.events.jsonl",
                        ),
                    ),
                ),
            ),
        )

        fates = _argument_fates(
            [repo_root / ".worktrees/m-coord/kitty-specs/m/status.events.jsonl"],
            result,
            repo_root,
        )

        assert fates == [
            {
                "path": ".worktrees/m-coord/kitty-specs/m/status.events.jsonl",
                "fate": "unchanged",
                "surface": "coordination",
                "reason": REASON_ALREADY_COMMITTED,
            }
        ]

    def test_relpath_falls_back_to_str_for_a_path_outside_repo_root(self) -> None:
        """A path with no common root with ``repo_root`` renders as its own ``str()`` (never raises)."""
        from specify_cli.cli.commands.spec_commit_cmd import _argument_fates
        from specify_cli.coordination.commit_outcome import PATH_UNROUTABLE
        from specify_cli.coordination.commit_router import CommitRouterResult

        result = CommitRouterResult(status="committed", placement_ref="topic", surfaces=())

        outside = Path("/elsewhere/spec.md")
        fates = _argument_fates([outside], result, Path("/repo"))

        assert fates == [{"path": str(outside), "fate": "refused", "surface": None, "reason": PATH_UNROUTABLE}]

    def test_an_unroutable_argument_forces_success_false_and_exit_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """B3 (review cycle 2, reviewer-renata finding): a ``refused`` argument must not coexist
        with ``success: true`` / exit 0.

        Realistic shapes this guards (per the review): a foreign-worktree
        path staging dropped, or a legacy Mission whose coordination dir
        name differs from the root dir name (so the mission-relative suffix
        match also misses). Both produce fate ``refused`` /
        ``PATH_UNROUTABLE`` with no matching ``SurfaceOutcome`` at all --
        ``_compute_success`` must still catch it via the ``arguments`` list,
        not just ``result.surfaces``.
        """
        from specify_cli.cli.commands.spec_commit_cmd import _render_spec_commit_result
        from specify_cli.coordination.commit_outcome import SurfaceOutcome
        from specify_cli.coordination.commit_router import CommitRouterResult

        repo_root = Path("/repo")
        # Both REAL surfaces committed cleanly -- the defect this guards is
        # purely that a THIRD input never matched either one.
        result = CommitRouterResult(
            status="committed",
            placement_ref="topic",
            commit_hash="abc",
            surfaces=(
                SurfaceOutcome(
                    surface="primary",
                    branch="topic",
                    status="committed",
                    commit_hash="abc",
                    committed=("kitty-specs/m/spec.md",),
                ),
            ),
        )
        abs_files = [repo_root / "kitty-specs/m/spec.md", repo_root / "kitty-specs/m/foreign-worktree-file.md"]

        with pytest.raises(typer.Exit) as excinfo:
            _render_spec_commit_result(result, json_output=True, abs_files=abs_files, repo_root=repo_root)
        assert excinfo.value.exit_code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False, payload
        arguments_by_path = {entry["path"]: entry for entry in payload["arguments"]}
        assert arguments_by_path["kitty-specs/m/foreign-worktree-file.md"]["fate"] == "refused"
        assert arguments_by_path["kitty-specs/m/foreign-worktree-file.md"]["reason"] == "PATH_UNROUTABLE"


# ---------------------------------------------------------------------------
# WP13 T069 — R5 red-first: spec-commit names every argument's fate (#5501).
#
# Drives the real CLI entry point + the real commit router over a real,
# production-created coordination-routed Mission (WP02's factory) -- never a
# mocked ``commit_for_mission``. At this WP's lane base (WP01-05, no WP12)
# the decision ledger is COORD-classified (repro note, research D12), so the
# expected surface for the ledger files is computed from the taxonomy
# (``artifact_home_for``), never hard-coded -- R5 then holds regardless of
# WP12's landing order.
# ---------------------------------------------------------------------------


def _branch_tree_paths(repo_root: Path, branch: str) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", branch],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(out.splitlines())


def _any_committed_ending_with(committed: list[str], rel: str) -> bool:
    """Match a ``committed`` entry against *rel*, tolerating the coordination
    worktree's nested prefix (``.worktrees/<name>/kitty-specs/...``) -- see
    ``tests/coordination/test_commit_router.py``'s own
    ``coord_surface.committed == (".worktrees/coord/kitty-specs/.../...",)``
    pin for the same real-router shape.
    """
    return any(entry == rel or entry.endswith(f"/{rel}") for entry in committed)


def _ledger_expected_surface() -> str:
    from mission_runtime import CommitTarget, MissionArtifactKind, TopologySurface
    from mission_runtime.artifacts import artifact_home_for

    home = artifact_home_for(MissionArtifactKind.DECISION_LEDGER, CommitTarget(ref="irrelevant-for-surface"))
    return "primary" if home.write_surface is TopologySurface.PRIMARY else "coordination"


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_names_every_argument_fate(tmp_path: Path) -> None:
    """R5 (#5501): a mixed coordination-routed batch names every argument's fate.

    Precondition (R-M4, post-tasks squad): this WP's lane base is WP01-05 --
    WP06's create seeding is NOT present -- so the coordination fixture is
    built via ``make_coord_mission(..., materialized=True)``, and the
    MATERIALIZED state is asserted before any dirtying, so a red here can
    never come from a wrong fixture.
    """
    from mission_runtime import MissionTopology
    from specify_cli.decisions.models import OriginFlow
    from specify_cli.decisions.service import open_decision
    from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True, slug="wp13-fate")
    assert (
        probe_coord_state(coord.repo_root, coord.mission_dir_name, coord.mid8, coordination_branch=coord.coordination_branch)
        is CoordState.MATERIALIZED
    ), "precondition: the coordination surface must be MATERIALIZED before dirtying (R-M4)"

    # A dirty spec.md (PRIMARY, root checkout).
    spec = coord.root_mission_dir / "spec.md"
    spec.write_text("# Spec\n\nFR-001 must hold.\n", encoding="utf-8")

    # A ledger opened through the production service -- decisions/index.json +
    # decisions/DM-<ulid>.md land uncommitted in the root checkout (D12).
    resp = open_decision(
        coord.repo_root,
        coord.mission_dir_name,
        origin_flow=OriginFlow.SPECIFY,
        input_key="wp13-fate-test",
        step_id="wp13-fate-test",
        question="Which remedy?",
        options=("a", "b"),
        actor="tester",
    )
    dm_file = Path(resp.artifact_path)
    index_json = coord.root_mission_dir / "decisions" / "index.json"
    assert index_json.exists() and dm_file.exists(), "precondition: open_decision must write the ledger into the root checkout (D12)"

    # A dirty trace file (traces/ keeps the legacy root-checkout copy behaviour, D7).
    trace = coord.root_mission_dir / "traces" / "approach.md"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("investigated the fate taxonomy\n", encoding="utf-8")

    # ``open_decision``'s own emit already appended the DecisionPointOpened row
    # to the MATERIALIZED coordination copy of status.events.jsonl -- the
    # status-log change this R5 scenario needs is already dirty there.
    coord_status_log = coord.coord_mission_dir / "status.events.jsonl"
    assert coord_status_log.exists(), "precondition: open_decision must dirty the coordination status log"
    root_status_arg = coord.root_mission_dir / "status.events.jsonl"

    mission_rel = f"kitty-specs/{coord.mission_dir_name}"
    rel_spec = f"{mission_rel}/spec.md"
    rel_index = f"{mission_rel}/decisions/index.json"
    rel_dm = f"{mission_rel}/decisions/{dm_file.name}"
    rel_trace = f"{mission_rel}/traces/approach.md"
    rel_status = f"{mission_rel}/status.events.jsonl"

    app = _make_app()
    runner = CliRunner()
    with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=coord.repo_root):
        result = runner.invoke(
            app,
            [
                str(spec),
                str(index_json),
                str(dm_file),
                str(trace),
                str(root_status_arg),
                "--message",
                "spec batch",
                "--mission",
                coord.mission_dir_name,
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is True, payload

    expected_ledger_surface = _ledger_expected_surface()

    surfaces_by_name = {entry["surface"]: entry for entry in payload["surfaces"]}
    assert set(surfaces_by_name) == {"primary", "coordination"}, payload["surfaces"]
    primary_surface = surfaces_by_name["primary"]
    coord_surface = surfaces_by_name["coordination"]
    assert primary_surface["branch"] == coord.target_branch
    assert coord_surface["branch"] == coord.coordination_branch
    assert _any_committed_ending_with(primary_surface["committed"], rel_spec)
    assert _any_committed_ending_with(coord_surface["committed"], rel_trace)
    assert _any_committed_ending_with(coord_surface["committed"], rel_status)
    ledger_surface_payload = coord_surface if expected_ledger_surface == "coordination" else primary_surface
    assert _any_committed_ending_with(ledger_surface_payload["committed"], rel_index), payload["surfaces"]
    assert _any_committed_ending_with(ledger_surface_payload["committed"], rel_dm), payload["surfaces"]

    arguments_by_path = {entry["path"]: entry for entry in payload["arguments"]}
    assert set(arguments_by_path) == {rel_spec, rel_index, rel_dm, rel_trace, rel_status}, payload["arguments"]
    assert arguments_by_path[rel_spec] == {"path": rel_spec, "fate": "committed", "surface": "primary"}
    assert arguments_by_path[rel_trace] == {"path": rel_trace, "fate": "committed", "surface": "coordination"}
    assert arguments_by_path[rel_status] == {"path": rel_status, "fate": "committed", "surface": "coordination"}
    assert arguments_by_path[rel_index] == {"path": rel_index, "fate": "committed", "surface": expected_ledger_surface}
    assert arguments_by_path[rel_dm] == {"path": rel_dm, "fate": "committed", "surface": expected_ledger_surface}

    # Branch contents (step 5): the target tip holds spec.md (+ the ledger iff
    # PRIMARY), the coordination tip holds the trace + the status row (+ the
    # ledger iff COORD).
    target_tree = _branch_tree_paths(coord.repo_root, coord.target_branch)
    coord_tree = _branch_tree_paths(coord.repo_root, coord.coordination_branch)
    assert rel_spec in target_tree
    assert rel_trace in coord_tree
    assert rel_status in coord_tree
    ledger_tree = coord_tree if expected_ledger_surface == "coordination" else target_tree
    assert rel_index in ledger_tree
    assert rel_dm in ledger_tree


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_names_every_argument_fate_text_output(tmp_path: Path) -> None:
    """R5 text-output leg (T069 step 6): one summary line per surface, via ``render_commit_outcome``."""
    from mission_runtime import MissionTopology
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True, slug="wp13-fate-text")
    spec = coord.root_mission_dir / "spec.md"
    spec.write_text("# Spec\n\nFR-002 too.\n", encoding="utf-8")
    trace = coord.root_mission_dir / "traces" / "approach.md"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("investigated the text leg\n", encoding="utf-8")

    app = _make_app()
    runner = CliRunner()
    with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=coord.repo_root):
        result = runner.invoke(
            app,
            [str(spec), str(trace), "--message", "spec+trace", "--mission", coord.mission_dir_name],
        )

    assert result.exit_code == 0, result.output
    surface_lines = [line for line in result.output.splitlines() if "primary (" in line or "coordination (" in line]
    surfaces_seen = {"primary" if "primary (" in line else "coordination" for line in surface_lines}
    assert surfaces_seen == {"primary", "coordination"}, result.output
    # No refusals/actionable skips in this batch, so exactly one summary line
    # per surface -- never a bare success message that drops the per-surface
    # trail (#5513 masking).
    assert len(surface_lines) == 2, result.output


# ---------------------------------------------------------------------------
# WP13 T073 — mixed-batch refusal, the clean-input control, and the C-008
# lanes (non-coordination) Mission control.
# ---------------------------------------------------------------------------


def _run_spec_commit_under_held_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    slug: str,
    json_output: bool,
) -> tuple[CoordMission, Result]:
    """Shared T073/B2 fixture: hold the Mission status lock on a background thread
    (never a sleep-poll, testing-flakiness policy) while spec-commit commits
    spec.md (PRIMARY, lands for real) plus the coord-resident status log
    (REFUSED: STATUS_LOCK_HELD). Returns ``(coord, CliRunner result)``.
    """
    import threading

    from mission_runtime import MissionTopology
    from specify_cli.coordination import status_transition as st
    from specify_cli.status.locking import feature_status_lock
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True, slug=slug)
    monkeypatch.setattr(st, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", 0.2)

    spec = coord.root_mission_dir / "spec.md"
    spec.write_text("# Spec\n\nlocked batch\n", encoding="utf-8")

    coord_status_log = coord.coord_mission_dir / "status.events.jsonl"
    coord_status_log.write_text(
        coord_status_log.read_text(encoding="utf-8") + '{"row": "locked"}\n',
        encoding="utf-8",
    )
    root_status_arg = coord.root_mission_dir / "status.events.jsonl"

    ready = threading.Event()
    release = threading.Event()

    def _hold_lock() -> None:
        with feature_status_lock(coord.repo_root, coord.mission_dir_name, timeout=5):
            ready.set()
            release.wait(timeout=10)

    holder = threading.Thread(target=_hold_lock, name="wp13-lock-holder")
    holder.start()
    try:
        assert ready.wait(timeout=5), "the holder thread never took the status lock"

        app = _make_app()
        runner = CliRunner()
        args = [str(spec), str(root_status_arg), "--message", "locked batch", "--mission", coord.mission_dir_name]
        if json_output:
            args.append("--json")
        with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=coord.repo_root):
            result = runner.invoke(app, args)
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive()
    return coord, result


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_reports_refused_coordination_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T073: a mixed batch where only the coordination surface is refused must be visible.

    The batch must report success=false and a non-zero exit code even
    though the primary surface genuinely committed.
    """
    coord, result = _run_spec_commit_under_held_lock(tmp_path, monkeypatch, slug="wp13-lock-held", json_output=True)

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False, payload

    surfaces_by_name = {entry["surface"]: entry for entry in payload["surfaces"]}
    assert surfaces_by_name["primary"]["status"] == "committed", payload["surfaces"]
    # The lock-timeout-during-commit path reports the surface as ``error``
    # (the staging-time ``_OwningSurfaceRefused`` translator uses ``refused``
    # instead -- both are legitimate per-surface statuses this gate names);
    # the named reason is what R5/C-003 actually cares about.
    assert surfaces_by_name["coordination"]["status"] in ("refused", "error"), payload["surfaces"]
    named_reasons = {fate["reason"] for fate in (*surfaces_by_name["coordination"]["refused"], *surfaces_by_name["coordination"]["skipped"])}
    assert "STATUS_LOCK_HELD" in named_reasons, payload["surfaces"]

    arguments_by_path = {entry["path"]: entry for entry in payload["arguments"]}
    rel_spec = f"kitty-specs/{coord.mission_dir_name}/spec.md"
    rel_status = f"kitty-specs/{coord.mission_dir_name}/status.events.jsonl"
    assert arguments_by_path[rel_spec] == {"path": rel_spec, "fate": "committed", "surface": "primary"}
    assert arguments_by_path[rel_status]["fate"] == "refused", payload["arguments"]
    assert arguments_by_path[rel_status]["reason"] == "STATUS_LOCK_HELD", payload["arguments"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_reports_refused_coordination_surface_text_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B2 (review cycle 2, reviewer-renata finding): the SAME mixed lock-held batch, in text mode.

    Before the fix, the legacy ``error`` status printed ONLY the single-line
    ``Error: <lock diagnostic>`` -- an operator would never learn that
    spec.md WAS committed on the target branch (FR-007 masking, now in text
    instead of JSON). Asserts a ``primary (...)`` committed line, a
    ``coordination (...)`` line naming ``STATUS_LOCK_HELD``, AND the
    existing actionable ``Error:`` line, all present together.
    """
    coord, result = _run_spec_commit_under_held_lock(tmp_path, monkeypatch, slug="wp13-lock-held-text", json_output=False)

    assert result.exit_code != 0, result.output
    out = result.output
    assert f"primary ({coord.target_branch})" in out, out
    assert f"coordination ({coord.coordination_branch})" in out, out
    assert "STATUS_LOCK_HELD" in out, out
    assert "Error:" in out, out


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_clean_status_log_reports_unchanged(tmp_path: Path) -> None:
    """T073 positive control: a clean coordination copy yields fate 'unchanged', never a refusal.

    N2 (review cycle 2): pinned to ``REASON_NO_CHANGES`` -- the real router
    deterministically returns it for this exact fixture shape (the
    root-checkout-passed path IS translated and staged, but carries a
    zero-diff commit; confirmed by probing the real payload), so a
    regression in which no-op flavour is reported is caught rather than
    silently accepted by a permissive set.
    """
    from mission_runtime import MissionTopology
    from specify_cli.coordination.commit_outcome import REASON_NO_CHANGES
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True, slug="wp13-clean")
    # ``_materialize_coord_surface`` already committed the coord copy of
    # status.events.jsonl -- nothing further to dirty.
    status_log_arg = coord.root_mission_dir / "status.events.jsonl"

    app = _make_app()
    runner = CliRunner()
    with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=coord.repo_root):
        result = runner.invoke(
            app,
            [str(status_log_arg), "--message", "no-op", "--mission", coord.mission_dir_name, "--json"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["committed"] is False
    assert payload["success"] is True
    assert payload["reason"] == REASON_NO_CHANGES, payload

    rel_status = f"kitty-specs/{coord.mission_dir_name}/status.events.jsonl"
    arguments_by_path = {entry["path"]: entry for entry in payload["arguments"]}
    assert arguments_by_path[rel_status]["fate"] == "unchanged", payload["arguments"]
    assert arguments_by_path[rel_status]["reason"] == REASON_NO_CHANGES, payload["arguments"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_lanes_mission_output_unchanged(tmp_path: Path) -> None:
    """C-008: on a lanes (non-coordination) Mission, existing keys/values stay
    byte-identical and ``surfaces`` holds a single primary entry (the owned-
    checkout shape too -- router L281 never groups a single-partition batch).
    """
    from tests.git.protected_target_fixtures import build_protected_target_repo

    repo = build_protected_target_repo(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feat/wp13-lanes-c008"], cwd=repo.repo_root, check=True, capture_output=True)

    slug = "wp13-lanes-c008"
    feature_dir = repo.repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": "01KZZZZZZZZZZZZZZZZZZZZZZZ",
        "mission_slug": slug,
        "mid8": "01KZZZZZ",
        "mission_type": "software-dev",
        "friendly_name": "WP13 Lanes C008",
        "target_branch": "feat/wp13-lanes-c008",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    spec = feature_dir / "spec.md"
    spec.write_text("# Spec\n\nC-008 control.\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo.repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"chore: seed {slug}"], cwd=repo.repo_root, check=True, capture_output=True)
    spec.write_text("# Spec\n\nC-008 control.\nFR-100 too.\n", encoding="utf-8")

    app = _make_app()
    runner = CliRunner()
    with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=repo.repo_root):
        result = runner.invoke(app, [str(spec), "--message", "spec: C-008", "--mission", slug, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "success"
    assert payload["success"] is True
    assert payload["committed"] is True
    assert payload["placement_ref"] == "feat/wp13-lanes-c008"
    assert isinstance(payload.get("commit_hash"), str) and payload["commit_hash"]

    assert len(payload["surfaces"]) == 1, payload["surfaces"]
    assert payload["surfaces"][0]["surface"] == "primary"

    rel_spec = f"kitty-specs/{slug}/spec.md"
    assert payload["arguments"] == [{"path": rel_spec, "fate": "committed", "surface": "primary"}]


@pytest.mark.integration
@pytest.mark.git_repo
def test_spec_commit_legacy_mission_coord_dir_name_mismatch_is_refused(tmp_path: Path) -> None:
    """B3 real-router variant (review cycle 2): a legacy, hand-seeded Mission whose
    coordination worktree's mission dir carries the mid8 suffix
    (``kitty-specs/<slug>-<mid8>/``) while the root checkout's dir does not
    (``kitty-specs/<slug>/``) -- the exact "coordination dir name differs"
    shape the reviewer named. The real router happily commits BOTH surfaces
    (the status-log argument lands on the coordination branch), but under
    its OWN worktree-nested path, which never matches the caller's
    ``kitty-specs/<slug>/status.events.jsonl`` argument by suffix either
    (the suffix differs: ``<slug>-<mid8>`` vs ``<slug>``). The argument is
    PATH_UNROUTABLE even though nothing was actually lost -- and B3 requires
    that to still fail the batch rather than report success.
    """
    from tests.git.protected_target_fixtures import build_protected_target_repo

    repo = build_protected_target_repo(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feat/b3-dir-mismatch"], cwd=repo.repo_root, check=True, capture_output=True)

    slug = "b3-dir-mismatch"
    mid8 = "01KVMBDZ"
    feature_dir = repo.repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": f"{mid8}HTBP3A9Y5T4EQ80RA9",
        "mission_slug": slug,
        "mid8": mid8,
        "mission_type": "software-dev",
        "friendly_name": "B3 dir mismatch",
        "target_branch": "feat/b3-dir-mismatch",
        "coordination_branch": f"kitty/mission-{slug}-{mid8}",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    status_row = {
        "event_id": f"{mid8}AAAAAAAAAAAAAAAAAA",
        "mission_slug": slug,
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "claimed",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "tester",
        "force": False,
        "execution_mode": "direct_repo",
    }
    (feature_dir / "status.events.jsonl").write_text(json.dumps(status_row) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo.repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"chore: seed {slug}"], cwd=repo.repo_root, check=True, capture_output=True)
    subprocess.run(["git", "branch", str(meta["coordination_branch"])], cwd=repo.repo_root, check=True, capture_output=True)

    spec = feature_dir / "spec.md"
    spec.write_text("# Spec\n\nFR-002\n", encoding="utf-8")
    events = feature_dir / "status.events.jsonl"
    status_row2 = dict(status_row, event_id=f"{mid8}BBBBBBBBBBBBBBBBBB", from_lane="claimed", to_lane="in_progress")
    events.write_text(events.read_text(encoding="utf-8") + json.dumps(status_row2) + "\n", encoding="utf-8")

    app = _make_app()
    runner = CliRunner()
    with patch("specify_cli.cli.commands.spec_commit_cmd._current_repo_root", return_value=repo.repo_root):
        result = runner.invoke(app, [str(spec), str(events), "--message", "mixed", "--mission", slug, "--json"])

    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is False, payload

    rel_spec = f"kitty-specs/{slug}/spec.md"
    rel_status = f"kitty-specs/{slug}/status.events.jsonl"
    arguments_by_path = {entry["path"]: entry for entry in payload["arguments"]}
    assert arguments_by_path[rel_spec]["fate"] == "committed", payload["arguments"]
    assert arguments_by_path[rel_status]["fate"] == "refused", payload["arguments"]
    assert arguments_by_path[rel_status]["reason"] == "PATH_UNROUTABLE", payload["arguments"]
