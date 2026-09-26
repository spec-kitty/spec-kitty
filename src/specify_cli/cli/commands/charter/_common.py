"""Shared helpers used by multiple ``charter`` subcommands.

Lifted unchanged from the legacy ``charter.py`` during the WP06 MS-1 split.
Keep these helpers behaviour-preserving; if you need to specialise behaviour
for one subcommand, copy the helper into that subcommand module instead of
forking this file.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.markup import escape

from charter.bundle import CHARTER_YAML
from charter.versioning import check_bundle_compatibility, get_bundle_schema_version

from specify_cli.task_utils import TaskCliError


def default_interview(*args: Any, **kwargs: Any) -> Any:
    """Patchable lazy wrapper for default charter interview generation."""
    from charter.activation.interview import default_interview as _default_interview

    return _default_interview(*args, **kwargs)


def _resolve_charter_path(repo_root: Path) -> Path:
    """Find charter.md in canonical location only.

    Does not fall back to legacy locations. Users with pre-charter state
    must run 'spec-kitty upgrade' first (handled by the charter-rename migration).
    """
    charter_path = repo_root / ".kittify" / "charter" / "charter.md"
    if charter_path.exists():
        return charter_path

    raise TaskCliError(
        f"Charter not found at {charter_path}\n"
        "  Run 'spec-kitty charter interview' to create one,\n"
        "  or 'spec-kitty upgrade' if migrating from an older version."
    )


def _resolve_charter_bundle_path(repo_root: Path) -> Path:
    """Find charter.yaml -- the authoritative bundle -- in canonical location only.

    FR-005 sibling of :func:`_resolve_charter_path`: that function resolves
    the display-only ``charter.md`` and is consumed by prose-rendering
    commands (``status``/``resynthesize``) -- it is NOT retargeted in place.
    This sibling resolves the authoritative ``charter.yaml`` bundle for
    CLI-layer *presence* / "governance exists" gates, so those gates survive
    ``charter.md`` deletion (SC-002). Reuses the shared
    ``charter.bundle.CHARTER_YAML`` constant rather than a fresh literal
    (Sonar S1192).  Does not fall back to legacy locations.
    """
    # Explicit annotation: the ``charter.*`` mypy override (pyproject.toml
    # [[tool.mypy.overrides]]) sets follow_imports="skip" for intra-package
    # imports crossing into ``charter.bundle`` from this CLI-layer module,
    # which erases ``CHARTER_YAML``'s declared ``Path`` type to ``Any`` at
    # this call site. Annotating recovers the real type without a
    # suppression comment (mirrors ``charter/bundle.py``'s
    # ``compute_bundle_content_hash`` precedent for the identical pattern).
    charter_yaml_path: Path = repo_root / CHARTER_YAML
    if charter_yaml_path.exists():
        return charter_yaml_path

    raise TaskCliError(
        f"Charter bundle not found at {charter_yaml_path}\n"
        "  Run 'spec-kitty charter interview' to create one,\n"
        "  or 'spec-kitty upgrade' if migrating from an older version."
    )


def _resolve_actor() -> str:
    """Return the git user email or ``"cli"`` as fallback."""
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        email = result.stdout.strip()
        if email:
            return email
    except Exception:  # noqa: BLE001 — git may be absent or misconfigured; fall back to "cli" identity
        pass
    return "cli"


def _parse_csv_option(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    values = [part.strip() for part in raw.split(",")]
    normalized = [value for value in values if value]
    return normalized if normalized else []


def _interview_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _emit_error(console: Any, *, json_output: bool, message: str, unexpected: bool = False) -> None:
    """Emit a charter command error while preserving ``--json`` parseability."""
    if json_output:
        print(
            json.dumps(
                {
                    "result": "error",
                    "success": False,
                    "error": message,
                },
                sort_keys=True,
            )
        )
        return

    label = "Unexpected error" if unexpected else "Error"
    # Escape the message so Rich does not eat bracketed tokens in it (e.g. a
    # doctrine selector like ``[build]`` or ``tactic:<id>`` echoed in an error).
    # The ``[red]…[/red]`` label is intentional markup and stays literal; only
    # the data-derived ``message`` is escaped (sibling of the #5061 body fix).
    console.print(f"[red]{label}:[/red] {escape(message)}")


def _assert_bundle_compatible(charter_dir: Path) -> None:
    """Raise TaskCliError if the bundle at charter_dir is not compatible with this CLI.

    Called by ``status``, ``resynthesize``, and ``bundle validate`` when the
    charter bundle directory is known to exist.  Fresh synthesis (no prior
    bundle) must NOT call this function — ``metadata.yaml`` would be absent.
    """
    bundle_version = get_bundle_schema_version(charter_dir)
    result = check_bundle_compatibility(bundle_version)
    if not result.is_compatible:
        raise TaskCliError(result.message)
