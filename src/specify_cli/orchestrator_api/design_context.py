"""Thin context/interview projections over the shared design application."""

from __future__ import annotations

import json

import typer

from specify_cli.design.context import DesignContextError, build_design_context, record_interview_answers
from . import _common
from .envelope import make_envelope

__all__ = ["design_context", "interview_record"]


def design_context(
    mission: str | None = typer.Option(None, "--mission", help="Mission handle; omitted before creation"),
    stage: str = typer.Option("specify", "--stage", help="specify | plan | tasks"),
    mission_type: str | None = typer.Option(None, "--mission-type", help="Activated mission type before creation"),
) -> None:
    """Read bounded resolved templates, governance and required interview slots."""
    root = _common._get_main_repo_root()
    slug = _common._resolve_mission_dir_or_fail("design-context", root, mission).name if mission else None
    try:
        payload = build_design_context(root, slug, stage, mission_type)
    except DesignContextError as exc:
        _common._fail("design-context", exc.code, exc.message, exc.details)
    _common._emit(make_envelope(command="design-context", success=True, data=payload))


def interview_record(
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    stage: str = typer.Option(..., "--stage", help="specify | plan"),
    answers: str = typer.Option(..., "--answers", help="JSON mapping of canonical question IDs to nonempty answers"),
    actor: str = typer.Option(..., "--actor", help="Actor identity"),
    policy: str | None = typer.Option(None, "--policy", help="Required orchestrator policy JSON"),
) -> None:
    """Record incremental interview answers through the existing decision service."""
    cmd = "interview-record"
    if not policy:
        _common._fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for interview-record")
    _common._parse_policy_or_fail(cmd, policy)
    root = _common._get_main_repo_root()
    slug = _common._resolve_mission_dir_or_fail(cmd, root, mission).name
    try:
        if len(answers.encode("utf-8")) > 262144:
            raise DesignContextError("DESIGN_INTERVIEW_INVALID", "Interview JSON exceeds the inline byte limit")
        payload = record_interview_answers(root, slug, stage, json.loads(answers), actor)
    except (DesignContextError, json.JSONDecodeError) as exc:
        if isinstance(exc, DesignContextError):
            _common._fail(cmd, exc.code, exc.message, exc.details)
        _common._fail(cmd, "DESIGN_INTERVIEW_INVALID", "--answers must be valid JSON")
    _common._emit(make_envelope(command=cmd, success=True, data=payload))
