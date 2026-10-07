"""In-process projection of canonical next, including bounded prompt bodies."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import typer

from specify_cli.design.context import DesignContextError, bounded_content
from . import _common
from .envelope import make_envelope

__all__ = ["runtime_next"]


def _decode(raw: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for position, character in enumerate(raw):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[position:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _run_native(arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    from specify_cli.cli.commands.next_cmd import next_step

    capture = io.StringIO()
    failed = False
    with contextlib.redirect_stdout(capture):
        try:
            next_step(**arguments)
        except typer.Exit as exc:
            failed = exc.exit_code != 0
    return _decode(capture.getvalue()), failed


@contextlib.contextmanager
def _completion_gate(arguments: dict[str, Any]) -> Iterator[None]:
    """Guard API-authored content while the native authority completes its step.

    The native persisted snapshot identifies the issued step, never a planner
    preview or caller-supplied stage. Initial issuance and legacy manual authoring preserve native behavior.
    The lock coordinates API writers; native/manual writers remain outside it.
    """
    if arguments["result"] != "success":
        yield
        return
    from specify_cli.design.receipts import api_authoring_enabled, authoring_lock
    from specify_cli.design.validation import validate_stage
    from runtime.next.runtime_bridge_query import issued_step_id_for_mission, MissionNotFoundError

    root = _common._get_main_repo_root()
    slug = _common._resolve_mission_dir_or_fail("next", root, arguments["mission"]).name
    with authoring_lock(root, slug):
        if api_authoring_enabled(root, slug):
            try:
                issued_stage = issued_step_id_for_mission(slug, root)
            except MissionNotFoundError as exc:
                raise DesignContextError("RUNTIME_NEXT_FAILED", "Native issued state is unavailable") from exc
            if issued_stage in {"specify", "plan", "tasks"}:
                validate_stage(root, slug, issued_stage)
        yield


def _run_governed(arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    with _completion_gate(arguments):
        return _run_native(arguments)


def _project_prompt(payload: dict[str, Any]) -> None:
    path = payload.get("prompt_file")
    if not path:
        if payload.get("kind") == "step":
            raise DesignContextError("RUNTIME_NEXT_FAILED", "Native step omitted its prompt")
        return
    if not isinstance(path, str):
        raise DesignContextError("RUNTIME_NEXT_FAILED", "Native prompt identity is invalid")
    try:
        payload["prompt"] = bounded_content(Path(path))
    except OSError as exc:
        raise DesignContextError("RUNTIME_NEXT_FAILED", "Native prompt is unreadable", {"reason": type(exc).__name__}) from exc
    payload.pop("prompt_file", None)


def runtime_next(
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    agent: str | None = typer.Option(None, "--agent", help="Agent required for advancement"),
    result: str | None = typer.Option(None, "--result", help="Prior result; omit for read-only query"),
    answer: str | None = typer.Option(None, "--answer", help="Native pending decision answer"),
    decision_id: str | None = typer.Option(None, "--decision-id", help="Native decision identity"),
    policy: str | None = typer.Option(None, "--policy", help="Policy JSON required for advancement"),
) -> None:
    """Query or advance exactly the same authority and lifecycle as native next."""
    cmd = "next"
    if result is not None and not policy:
        _common._fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required when advancing next")
    if policy:
        _common._parse_policy_or_fail(cmd, policy)
    if answer is not None and len(answer.encode("utf-8")) > 262144:
        _common._fail(cmd, "RUNTIME_NEXT_FAILED", "Decision input exceeds the inline byte limit")
    root = _common._get_main_repo_root()
    mission = _common._resolve_mission_dir_or_fail(cmd, root, mission).name
    arguments = {"agent": agent, "result": result, "mission": mission, "json_output": True, "answer": answer, "decision_id": decision_id, "owned_checkout": None}
    try:
        payload, failed = _run_governed(arguments)
        if payload is None:
            raise DesignContextError("RUNTIME_NEXT_FAILED", "Native next produced no parseable JSON", {"mission_slug": mission})
        payload.setdefault("mission_slug", mission)
        if failed or payload.get("kind") == "error" or "error" in payload:
            _common._fail(cmd, "RUNTIME_NEXT_FAILED", "Native next refused the request", payload)
        if payload.get("kind") == "blocked":
            _common._fail(cmd, "RUNTIME_BLOCKED", "Native next is blocked", payload)
        _project_prompt(payload)
    except typer.Exit:
        raise
    except (DesignContextError, OSError, ValueError, RuntimeError) as exc:
        _common._fail(
            cmd, "RUNTIME_NEXT_FAILED", str(exc), {"mission_slug": mission, "reason": getattr(exc, "code", type(exc).__name__), **getattr(exc, "details", {})}
        )
    _common._emit(make_envelope(command=cmd, success=True, data=payload))
