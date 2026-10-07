"""Thin projections over governed planning authoring and canonical prerequisites."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

import typer

from specify_cli.design.authoring import read_artifact, submit_artifacts
from specify_cli.design.context import DesignContextError
from specify_cli.design.errors import DesignError
from specify_cli.design.models import MAX_REQUEST_BYTES
from specify_cli.design.validation import validate_stage
from specify_cli.orchestrator_api import _common
from specify_cli.orchestrator_api._common import _HELP_MISSION_SLUG, _HELP_POLICY, _emit, _fail, _parse_policy_or_fail
from specify_cli.orchestrator_api.envelope import make_envelope


def _invoke(cmd: str, mission: str, operation: Callable[[Path, str], dict[str, object]]) -> None:
    root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, root, mission)
    identity = _common._mission_identity_payload(mission_dir)
    try:
        data = operation(root, mission_dir.name)
    except (DesignError, DesignContextError) as exc:
        _fail(cmd, exc.code, exc.message, {**identity, **exc.details})
    except (OSError, UnicodeError) as exc:
        _fail(cmd, "DESIGN_IO_FAILED", "The host could not read or persist design content", {**identity, "reason": type(exc).__name__})
    _emit(make_envelope(command=cmd, success=True, data={**identity, **data}))


def artifact_read(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    kind: str = typer.Option(..., "--kind", help="Registered authoring artifact kind"),
    artifact_id: str | None = typer.Option(None, "--artifact-id", help="Declared package key or contract basename"),
) -> None:
    """Read bounded canonical content and its exact revision (absent is explicit)."""
    _invoke("artifact-read", mission, lambda root, slug: read_artifact(root, slug, kind, artifact_id))


def artifact_submit(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    request_json: str = typer.Option(..., "--request-json", help="Closed bounded artifact batch JSON; '-' reads UTF-8 stdin"),
    actor: str = typer.Option(..., "--actor", help="Accountable author"),
    policy: str | None = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Submit design content through host placement, validators and commit authority."""
    if policy is None:
        _fail("artifact-submit", "POLICY_METADATA_REQUIRED", "--policy is required for artifact-submit")
    _parse_policy_or_fail("artifact-submit", policy)
    _invoke("artifact-submit", mission, lambda root, slug: submit_artifacts(root, slug, _request_body(request_json), actor))


def design_validate(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    stage: str = typer.Option(..., "--stage", help="specify | plan | tasks"),
) -> None:
    """Check current canonical prerequisites without completing a lifecycle step."""
    _invoke("design-validate", mission, lambda root, slug: validate_stage(root, slug, stage))


def _request_body(request_json: str) -> str:
    """Read a finite CLI request without exposing caller-selected host paths."""
    if request_json != "-":
        return request_json
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    except OSError as exc:
        raise DesignError("DESIGN_IO_FAILED", "Could not read bounded request input") from exc
    if len(raw) > MAX_REQUEST_BYTES:
        raise DesignError("DESIGN_BOUNDS_EXCEEDED", "Request exceeds the JSON transport bound")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DesignError("DESIGN_REQUEST_INVALID", "Request input must be UTF-8") from exc
