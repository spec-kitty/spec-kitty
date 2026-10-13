"""In-process projection of canonical next, including bounded prompt bodies."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import typer

from specify_cli.design.context import DesignContextError, bounded_content
from . import _common
from .envelope import make_envelope

__all__ = ["runtime_next"]


def _decode(raw: str) -> dict[str, Any] | None:
    """Return the payload only when stdout is exactly one JSON object.

    Native ``next --json`` keeps stdout to a single document (its notices and
    preflight output go to stderr), so any leading or trailing text, or a second
    document, means the capture cannot be trusted and fails closed.
    """
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


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


def _fail_native_refusal(cmd: str, mission: str, payload: dict[str, Any]) -> None:
    """Fail the verb for a native refusal, keeping the envelope shape stable.

    A design-authoring refusal (native ``next`` emits ``{kind: error, error, reason,
    details?}`` for it, #5879) projects to the same ``message`` and
    ``data = {mission_slug, reason, **details}`` this verb always returned for it;
    any other native error keeps the generic message with the raw payload.
    """
    reason = payload.get("reason")
    if payload.get("kind") == "error" and isinstance(reason, str) and isinstance(payload.get("error"), str):
        details = payload.get("details")
        _common._fail(
            cmd,
            "RUNTIME_NEXT_FAILED",
            payload["error"],
            {"mission_slug": mission, "reason": reason, **(details if isinstance(details, dict) else {})},
        )
    _common._fail(cmd, "RUNTIME_NEXT_FAILED", "Native next refused the request", payload)


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
        # #5879: the marker-gated stale-content refusal now lives in the shared
        # native seam (``next_cmd.next_step``), so this verb inherits it by driving
        # native ``next`` directly — one canonical enforcement authority.
        payload, failed = _run_native(arguments)
        if payload is None:
            raise DesignContextError("RUNTIME_NEXT_FAILED", "Native next produced no parseable JSON", {"mission_slug": mission})
        payload.setdefault("mission_slug", mission)
        if failed or payload.get("kind") == "error" or "error" in payload:
            _fail_native_refusal(cmd, mission, payload)
        if payload.get("kind") == "blocked":
            _common._fail(cmd, "RUNTIME_BLOCKED", "Native next is blocked", payload)
        _project_prompt(payload)
    except typer.Exit:
        raise
    except (DesignContextError, OSError, ValueError, RuntimeError) as exc:
        _common._fail(
            cmd, "RUNTIME_NEXT_FAILED", str(exc), {"mission_slug": mission, "reason": getattr(exc, "code", type(exc).__name__), **getattr(exc, "details", {})}
        )
    else:
        _common._emit(make_envelope(command=cmd, success=True, data=payload))
