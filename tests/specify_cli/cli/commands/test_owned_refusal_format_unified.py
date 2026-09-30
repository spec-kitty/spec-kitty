"""Red-first regression: three commands' IN-BODY owned refusals now match the
unified ``emit_owned_refusal`` output contract (#5445).

Before this fix, ``agent tasks move-task``, ``agent mission
check-prerequisites`` and ``agent tasks mark-status`` each carried a bespoke
``except`` branch that rendered an owned-checkout refusal as ``[red]CODE:
message[/red]`` on **stdout** (human mode) and compact JSON (``--json``
mode) -- diverging from the canonical ``emit_owned_refusal`` contract
(``specify_cli.cli.commands._owned_checkout``): ``Error: [<CODE>] <message>``
on **stderr**, indented JSON carrying ``error_code``/``error`` under
``--json``. Each test below drives the real in-body except branch (not the
Typer-edge ``resolve_owned_or_refuse`` refusal, which already used the
canonical renderer) with a minimal, fast, in-process fact minted via
``tests._owned_fixtures.mint_test_fact`` -- no real git checkout.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from mission_runtime import ActionContextError, MissionTopology, OwnedRefusalCode
from tests._owned_fixtures import mint_test_fact

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "unit-owned-refusal-mission"


def _fact(tmp_path: Path) -> object:
    """A minimal, fast :class:`OwnedCheckout` fact -- no git repo required.

    ``mint_test_fact`` (the canonical unit-test door onto ``OwnedCheckout._mint``,
    see its own docstring) needs only path shape, never git state, for the
    three call sites under test here: none of them read ownership-validated
    git facts off the fact itself except ``mark-status``'s recovery-detail
    builder, which only needs ``owned_root`` to exist as a real directory (for
    its best-effort ``git status`` probe) -- ``tmp_path`` already does.
    """
    owned_root = tmp_path
    mission_dir = owned_root / "kitty-specs" / _SLUG
    return mint_test_fact(
        repository_root=tmp_path / "repository-root",
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        write_branch="codex/owned",
        topology=MissionTopology.SINGLE_BRANCH,
    )


# ---------------------------------------------------------------------------
# move-task
# ---------------------------------------------------------------------------


def test_move_task_owned_refusal_is_unified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.agent import tasks_move_task

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise ActionContextError(OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED, "owned move-task refusal")

    monkeypatch.setattr(tasks_move_task, "_mt_resolve_targets", _raise)
    fact = _fact(tmp_path)

    def _build_args(*, json_output: bool) -> tasks_move_task._MoveTaskArgs:
        return tasks_move_task._MoveTaskArgs(
            task_id="WP01",
            to="doing",
            mission=_SLUG,
            agent=None,
            assignee=None,
            shell_pid=None,
            note=None,
            review_feedback_file=None,
            approval_ref=None,
            reviewer=None,
            self_review_fallback=False,
            intended_reviewer=None,
            reviewer_failure_reason=None,
            done_override_reason=None,
            force=False,
            tracker_ref=None,
            skip_review_artifact_check=False,
            auto_commit=True,
            json_output=json_output,
            owned=fact,
        )

    # -- human mode: stderr, never stdout -----------------------------------
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        tasks_move_task._do_move_task(_build_args(json_output=False))
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: [OWNED_OPTION_UNSUPPORTED] owned move-task refusal"
    assert "Error:" not in captured.out
    assert "OWNED_OPTION_UNSUPPORTED" not in captured.out

    # -- json mode: indented, on stdout --------------------------------------
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        tasks_move_task._do_move_task(_build_args(json_output=True))
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("{\n")
    payload = json.loads(captured.out)
    assert payload["error_code"] == "OWNED_OPTION_UNSUPPORTED"
    assert payload["error"] == "owned move-task refusal"
    assert captured.err == ""


# ---------------------------------------------------------------------------
# check-prerequisites
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.mission.locate_project_root")
def test_check_prerequisites_owned_refusal_is_unified(
    mock_locate: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from specify_cli.cli.commands.agent import mission_check_prerequisites

    mock_locate.return_value = tmp_path  # type: ignore[attr-defined]
    fact = _fact(tmp_path)
    monkeypatch.setattr(mission_check_prerequisites, "resolve_owned_or_refuse", lambda *a, **k: fact)

    def _invoke(*, json_output: bool) -> None:
        mission_check_prerequisites.check_prerequisites(
            feature=_SLUG,
            json_output=json_output,
            paths_only=False,
            resume_probe=True,
            include_tasks=False,
            require_tasks=False,
            owned_checkout=tmp_path,
        )

    # -- human mode: stderr, never stdout -----------------------------------
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        _invoke(json_output=False)
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Error: [OWNED_OPTION_UNSUPPORTED]" in captured.err
    assert "OWNED_OPTION_UNSUPPORTED" not in captured.out

    # -- json mode: indented, on stdout --------------------------------------
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        _invoke(json_output=True)
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("{\n")
    payload = json.loads(captured.out)
    assert payload["error_code"] == "OWNED_OPTION_UNSUPPORTED"
    assert "error" in payload
    assert captured.err == ""


# ---------------------------------------------------------------------------
# mark-status
# ---------------------------------------------------------------------------


def test_mark_status_owned_refusal_is_unified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.agent import tasks_mark_status

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise ActionContextError(OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED, "owned mark-status refusal")

    monkeypatch.setattr(tasks_mark_status, "_ms_validate_inputs", _raise)
    fact = _fact(tmp_path)

    # -- human mode: stderr, never stdout -----------------------------------
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        tasks_mark_status._do_mark_status(["WP01"], "doing", _SLUG, True, False, owned=fact)
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: [OWNED_OPTION_UNSUPPORTED] owned mark-status refusal"
    assert "Error:" not in captured.out
    assert "OWNED_OPTION_UNSUPPORTED" not in captured.out

    # -- json mode: indented, on stdout, with the rich recovery envelope ----
    capsys.readouterr()
    with pytest.raises(typer.Exit) as excinfo:
        tasks_mark_status._do_mark_status(["WP01"], "doing", _SLUG, True, True, owned=fact)
    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("{\n")
    payload = json.loads(captured.out)
    assert payload["error_code"] == "OWNED_OPTION_UNSUPPORTED"
    assert payload["error"] == "owned mark-status refusal"
    # The rich recovery envelope (#3865) is preserved verbatim, not collapsed
    # to the generic 2-key ``emit_owned_refusal`` shape.
    assert "event_ids" in payload
    assert "applied_wps" in payload
    assert "destination_ref" in payload
    assert captured.err == ""
