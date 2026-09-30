"""check-prerequisites command family for ``agent mission`` (#2056 WP05).

Hosts the ``check-prerequisites`` command and its dedicated emit helpers
(``_emit_check_prerequisites_detection_error``, ``_emit_check_prerequisites_result``,
``_paths_only_payload``) plus the small ``meta.json`` readers
(``_read_meta_for_pr_bound``, ``_read_meta_for_emission``) the create/finalize
lifecycle shares.

The command is defined here as a plain callable; ``mission`` registers it on its
Typer ``app`` (and re-exports the name so ``mission.check_prerequisites`` — the
documented agent-alias dispatch target and patch target — keeps resolving). The
command resolves the not-yet-relocated ``_enforce_git_preflight`` preflight guard
through the ``mission`` module at call time so the existing
``mission._enforce_git_preflight`` patch seam is preserved without an import
cycle (the guard relocates with the setup-plan family in WP06).

One-way leaf (INV-8): imports lower layers + sibling Seam B/C/D leaves only,
never back into ``mission`` at module scope. Behavior is preserved byte-for-byte
from the pre-decomposition ``mission.py``; the WP01 golden harness is the
regression net.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

from specify_cli.cli.console import console
import typer

from mission_runtime import ActionContextError, OwnedCheckout, OwnedRefusalCode
from specify_cli.cli.commands._owned_checkout import (
    OwnedCheckoutOption,
    emit_owned_refusal,
    flat_error_envelope,
    resolve_owned_or_refuse,
)
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES

from specify_cli.cli.commands.agent.mission_branch_context import (
    _inject_branch_contract,
    _resolve_feature_target_branch,
)
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _build_setup_plan_detection_error,
)
from specify_cli.cli.commands.agent.mission_parsing import (
    _emit_console_or_json_error,
    _emit_json,
    _with_cli_version,
)


PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
PROJECT_ROOT_NOT_FOUND_MESSAGE = f"{PROJECT_ROOT_NOT_FOUND}. Run from within spec-kitty repository."

_RESUME_REQUIRED_META_FIELDS = (
    "mission_id",
    "slug",
    "mission_slug",
    "mission_type",
    "friendly_name",
    "purpose_tldr",
    "purpose_context",
    "target_branch",
    "topology",
    "created_at",
)

_MISSION_CREATED_SNAPSHOT_FIELDS = (
    "mission_id",
    "mission_slug",
    "mission_number",
    "mission_type",
    "friendly_name",
    "purpose_tldr",
    "purpose_context",
    "target_branch",
    "created_at",
)


def _is_canonical_ulid(value: object) -> bool:
    from ulid import ULID

    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return str(ULID.from_str(value)) == value
    except (TypeError, ValueError):
        return False


def _is_timezone_aware_iso8601(value: object) -> bool:
    from kernel.clock import parse_iso

    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return parse_iso(value.replace("Z", "+00:00")).utcoffset() is not None
    except (TypeError, ValueError):
        return False


def _mission_created_envelope_problems(created: dict[str, Any]) -> list[str]:
    from spec_kitty_events import normalize_event_id

    problems: list[str] = []
    event_id = created.get("event_id")
    try:
        if not isinstance(event_id, str):
            raise ValueError
        normalize_event_id(event_id)
    except (TypeError, ValueError):
        problems.append("MissionCreated envelope event_id is not a valid ULID or UUID")
    if created.get("schema_version") != "5.0.0":
        problems.append("MissionCreated envelope schema_version is not canonical local version '5.0.0'")
    if not _is_timezone_aware_iso8601(created.get("timestamp")):
        problems.append("MissionCreated envelope timestamp is not a timezone-aware ISO-8601 timestamp")
    return problems


def _matching_resume_probe_dirs(repo_root: Path, handle: str) -> list[Path]:
    """Return every canonical or partial scaffold matching ``handle``."""
    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )
    from specify_cli.core.constants import KITTY_SPECS_DIR
    from specify_cli.core.paths import assert_safe_path_segment, get_main_repo_root
    from specify_cli.lanes.branch_naming import mid8_from_slug, strip_numeric_prefix

    safe_handle = assert_safe_path_segment(handle)
    main_root = get_main_repo_root(repo_root)
    matches: set[Path] = set()

    try:
        matches.add(resolve_mission(safe_handle, main_root).feature_dir.resolve())
    except AmbiguousHandleError as exc:
        matches.update(candidate.feature_dir.resolve() for candidate in exc.candidates)
    except MissionNotFoundError:
        pass

    specs_dir = main_root / KITTY_SPECS_DIR
    if not specs_dir.is_dir():
        return sorted(matches)

    handle_mid8 = mid8_from_slug(safe_handle)
    human_handle = strip_numeric_prefix(safe_handle)
    for candidate in sorted(specs_dir.iterdir()):
        if not candidate.is_dir():
            continue
        candidate_mid8 = mid8_from_slug(candidate.name)
        candidate_human = candidate.name[: -(len(candidate_mid8) + 1)] if candidate_mid8 else candidate.name
        if candidate.name == safe_handle or (not handle_mid8 and strip_numeric_prefix(candidate_human) == human_handle):
            matches.add(candidate.resolve())
    return sorted(matches)


def _load_resume_probe_meta(feature_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read resume metadata once through the fail-closed authority."""
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        return load_meta_fail_closed(feature_dir), None
    except MissionMetaReadError as exc:
        return None, str(exc.cause)


def _resume_probe_candidate_summary(feature_dir: Path) -> dict[str, object]:
    """Build a non-throwing identity summary for ambiguity diagnostics."""
    meta, _read_error = _load_resume_probe_meta(feature_dir)
    meta = meta or {}
    return {
        "mission_slug": feature_dir.name,
        "mission_id": str(meta.get("mission_id", "")),
        "mission_dir": str(feature_dir),
        "feature_dir": str(feature_dir),  # legacy alias of mission_dir (#5206)
    }


def _is_assigned_mission_number(value: object) -> bool:
    """Return true only for a positive merged-Mission display number.

    Delegates to the single canonical leaf definition (#4900):
    :func:`specify_cli.consolidation.mission_number.is_assigned_mission_number`.
    """
    from specify_cli.consolidation.mission_number import is_assigned_mission_number

    return is_assigned_mission_number(value)


def _resume_meta_problems(meta: dict[str, Any], feature_dir: Path) -> list[str]:
    """Validate metadata fields shared by resumable and numbered Missions."""
    from mission_runtime import MissionTopology

    problems: list[str] = []
    for field in _RESUME_REQUIRED_META_FIELDS:
        value = meta.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"meta.json field {field!r} is missing or empty")
    for field in ("slug", "mission_slug"):
        value = meta.get(field)
        if isinstance(value, str) and value.strip() and value != feature_dir.name:
            problems.append(f"meta.json field {field!r} does not match directory name")
    if "pr_bound" in meta and not isinstance(meta["pr_bound"], bool):
        problems.append("meta.json field 'pr_bound' must be a boolean when present")
    mission_number = meta.get("mission_number")
    if "mission_number" not in meta:
        problems.append("meta.json field 'mission_number' is missing")
    elif mission_number is not None and not _is_assigned_mission_number(mission_number):
        problems.append("meta.json field 'mission_number' must be null or a positive integer")

    mission_id = meta.get("mission_id")
    if isinstance(mission_id, str) and mission_id.strip() and not _is_canonical_ulid(mission_id):
        problems.append("meta.json field 'mission_id' is not a canonical ULID")

    created_at = meta.get("created_at")
    if isinstance(created_at, str) and created_at.strip() and not _is_timezone_aware_iso8601(created_at):
        problems.append("meta.json field 'created_at' is not a valid timezone-aware ISO-8601 timestamp")

    topology = meta.get("topology")
    if isinstance(topology, str) and topology.strip():
        try:
            MissionTopology(topology)
        except ValueError:
            problems.append("meta.json field 'topology' is not a recognized Mission topology")
    return problems


def _mission_created_snapshot_problems(
    feature_dir: Path,
    meta: dict[str, Any],
) -> list[str]:
    """Validate the one canonical MissionCreated event against ``meta.json``."""
    event_log = feature_dir / "status.events.jsonl"
    if not event_log.is_file():
        return ["status.events.jsonl is missing"]

    try:
        rows = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"status.events.jsonl is unreadable or malformed: {exc}"]
    if any(not isinstance(row, dict) for row in rows):
        return ["status.events.jsonl contains a non-object event"]

    created_rows = [row for row in rows if row.get("event_type") == "MissionCreated"]
    if len(created_rows) != 1:
        return [f"expected exactly one MissionCreated event, found {len(created_rows)}"]
    payload = created_rows[0].get("payload")
    if not isinstance(payload, dict):
        return ["MissionCreated payload is missing or not an object"]

    problems: list[str] = []
    try:
        from spec_kitty_events.conformance import validate_event

        conformance = validate_event(payload, "MissionCreated", strict=True)
        violations = [f"{violation.field}: {violation.message}" for violation in conformance.model_violations] + [
            f"{violation.json_path}: {violation.message}" for violation in conformance.schema_violations
        ]
        if violations:
            problems.append("MissionCreated payload fails canonical schema: " + "; ".join(violations))
    except Exception as exc:  # noqa: BLE001 - malformed external-contract payload
        problems.append(f"MissionCreated payload validation failed: {exc}")

    created = created_rows[0]
    if created.get("aggregate_id") != meta.get("mission_id"):
        problems.append("MissionCreated aggregate_id disagrees with meta.json mission_id")
    if created.get("aggregate_type") != "Mission":
        problems.append("MissionCreated aggregate_type is not 'Mission'")
    problems.extend(_mission_created_envelope_problems(created))
    if payload.get("wp_count") != 0:
        problems.append("MissionCreated wp_count must be zero at creation")
    for field in _MISSION_CREATED_SNAPSHOT_FIELDS:
        expected = None if field == "mission_number" else meta.get(field)
        if payload.get(field) != expected:
            problems.append(f"MissionCreated field {field!r} disagrees with canonical creation metadata")
    return problems


def _build_resume_probe_payload(repo_root: Path, handle: str) -> dict[str, object]:
    """Return a structured resume result without misclassifying valid history."""
    from specify_cli.core.paths import get_main_repo_root
    from specify_cli.lanes.branch_naming import mid8_from_slug
    from specify_cli.missions._substantive import is_committed, is_substantive

    candidates = _matching_resume_probe_dirs(repo_root, handle)
    if not candidates:
        return {
            "result": "success",
            "resume_state": "not_found",
            "handle": handle,
        }
    if len(candidates) > 1:
        return {
            "error_code": "MISSION_RESUME_AMBIGUOUS",
            "error": f"Mission handle {handle!r} matches multiple existing or partial scaffolds.",
            "resume_state": "ambiguous",
            "handle": handle,
            "candidates": [_resume_probe_candidate_summary(path) for path in candidates],
            "remediation": "Select one candidate by exact mission_slug or mission_id; do not create another Mission.",
        }

    feature_dir = candidates[0]
    invalid: list[str] = []
    meta, meta_read_error = _load_resume_probe_meta(feature_dir)
    if meta_read_error is not None:
        invalid.append(f"meta.json is malformed or unreadable: {meta_read_error}")
    if meta is None:
        if meta_read_error is None:
            invalid.append("meta.json is missing")
        meta = {}
    invalid.extend(_resume_meta_problems(meta, feature_dir))
    mission_number = meta.get("mission_number")

    declared_mission_id = str(meta.get("mission_id", ""))
    embedded_mid8 = mid8_from_slug(feature_dir.name)
    if mission_number is None:
        if not embedded_mid8:
            invalid.append("pre-merge Mission directory is missing its canonical mission-id mid8 suffix")
        elif declared_mission_id and not declared_mission_id.startswith(embedded_mid8):
            invalid.append("directory mid8 does not match meta.json mission_id")
    spec_file = feature_dir / "spec.md"
    identity_payload: dict[str, object] = {
        "handle": handle,
        "mission_id": declared_mission_id,
        "mission_slug": feature_dir.name,
        "mission_type": str(meta.get("mission_type", "")),
        "friendly_name": str(meta.get("friendly_name", "")),
        "purpose_tldr": str(meta.get("purpose_tldr", "")),
        "purpose_context": str(meta.get("purpose_context", "")),
        "target_branch": str(meta.get("target_branch", "")),
        "topology": str(meta.get("topology", "")),
        "pr_bound": bool(meta.get("pr_bound", False)),
        "created_at": str(meta.get("created_at", "")),
        "mission_dir": str(feature_dir),
        "feature_dir": str(feature_dir),  # legacy alias of mission_dir (#5206)
        "spec_file": str(spec_file),
        "meta_file": str(feature_dir / "meta.json"),
    }
    if _is_assigned_mission_number(mission_number):
        if not spec_file.is_file():
            invalid.append("spec.md is missing")
        return {
            "error_code": "MISSION_RESUME_EXISTING",
            "error": (f"Mission {feature_dir.name!r} is numbered history and cannot be reused as an interrupted specify scaffold."),
            "resume_state": "existing",
            "mission_number": mission_number,
            **identity_payload,
            "integrity_warnings": invalid,
            "remediation": ("Preserve this Mission; do not repair or remove it. Choose a new slug, or operate on the existing Mission by its exact identity."),
        }

    if not spec_file.is_file():
        invalid.append("spec.md is missing")
    invalid.extend(_mission_created_snapshot_problems(feature_dir, meta))

    if invalid:
        return {
            "error_code": "MISSION_RESUME_MALFORMED",
            "error": f"Mission scaffold {feature_dir.name!r} is incomplete or malformed.",
            "resume_state": "malformed",
            "handle": handle,
            "mission_slug": feature_dir.name,
            "mission_dir": str(feature_dir),
            "feature_dir": str(feature_dir),  # legacy alias of mission_dir (#5206)
            "problems": invalid,
            "remediation": "Repair or remove the partial scaffold explicitly; do not create through it.",
        }

    main_root = get_main_repo_root(repo_root)
    spec_is_committed = is_committed(spec_file, main_root)
    mission_type = str(meta["mission_type"])
    # Decision 5 (#3832): this ``kind="spec"`` guard stays BEHAVIOURALLY
    # UNCHANGED by the #3832 template-derived substantive-gate fix — this is
    # a documented reconciliation, not an oversight. ``is_substantive(...,
    # "spec")`` routes to ``_has_substantive_fr_row``, which is anchored to
    # ``FR-###`` rows; ``research``'s and ``plan``'s own spec templates
    # (research-spec-template.md, plan-spec-skeleton.md) contain ZERO
    # ``FR-###`` rows (verified via ``grep -n "FR-"`` over both), so there is
    # no FR-vocabulary in either type's spec template to derive a
    # template-derived spec check from. The non-``software-dev`` branch of
    # this guard therefore stays a blanket ``True`` (no FR-row check at all)
    # for every other mission type, exactly as before this fix.
    return {
        "result": "success",
        "resume_state": "found",
        **identity_payload,
        "spec_committed_and_substantive": (spec_is_committed and (mission_type != "software-dev" or is_substantive(spec_file, "spec"))),
    }


def _emit_resume_probe_payload(payload: dict[str, object], *, json_output: bool) -> None:
    """Emit the structured resume-probe result for JSON or human callers."""
    if json_output:
        _emit_json(payload)
        return
    state = str(payload["resume_state"])
    if state in {"found", "not_found"}:
        console.print(f"[green]Resume probe:[/green] {state}")
    else:
        console.print(f"[red]Resume probe:[/red] {state}: {payload.get('error', '')}")


def _read_meta_for_pr_bound(feature_dir: Path) -> dict[str, Any]:
    """Read ``meta.json`` for the ``pr_bound`` write-back, silent-empty contract.

    Routes through the canonical ``mission_metadata.load_meta`` authority
    (FR-009 / SC-004) via ``load_meta_or_empty``: a missing *or* malformed file
    degrades to ``{}`` so the write-back is skipped, preserving the prior
    ``except (OSError, JSONDecodeError): pass`` (a corrupt meta never crashes
    the create flow).
    """
    from specify_cli.mission_metadata import load_meta_or_empty

    return cast(dict[str, Any], load_meta_or_empty(feature_dir))


def _read_meta_for_emission(feature_dir: Path) -> dict[str, Any] | None:
    """Read ``meta.json`` for finalize-tasks event emission, silent-none contract.

    Routes through the canonical ``mission_metadata.load_meta`` authority
    (FR-009 / SC-004) with ``on_malformed="none"``: a missing *or* malformed
    file degrades to ``None`` (the caller warns and skips emission), preserving
    the prior ``except (JSONDecodeError, OSError)`` warn-and-continue behavior.
    """
    from specify_cli.mission_metadata import load_meta

    return cast(
        dict[str, Any] | None,
        load_meta(feature_dir, allow_missing=True, on_malformed="none"),
    )


def _emit_check_prerequisites_detection_error(
    *,
    repo_root: Path,
    detection_error: ValueError | ActionContextError,
    feature: str | None,
    json_output: bool,
    paths_only: bool,
    include_tasks: bool,
) -> None:
    """Emit the existing feature-detection payload for prerequisite checks."""
    command_args: list[str] = []
    if json_output:
        command_args.append("--json")
    if paths_only:
        command_args.append("--paths-only")
    if include_tasks:
        command_args.append("--include-tasks")

    payload = _build_setup_plan_detection_error(
        repo_root,
        str(detection_error),
        feature,
        error_code="FEATURE_CONTEXT_UNRESOLVED",
        command_name="check-prerequisites",
        command_args=command_args,
    )
    if json_output:
        _emit_json(payload)
        return

    console.print(f"[red]Error:[/red] {payload['error']}")
    for slug in cast(list[str], payload.get("available_missions", []))[:10]:
        console.print(f"  - {slug}")
    if "example_command" in payload:
        console.print(f"  {payload['example_command']}")


def _paths_only_payload(validation_result: dict[str, object]) -> dict[str, object]:
    """Build the legacy paths-only payload shape for prerequisite checks."""
    paths_payload = dict(cast(dict[str, object], validation_result["paths"]))
    paths_payload["artifact_files"] = validation_result.get("artifact_files", {})
    paths_payload["artifact_dirs"] = validation_result.get("artifact_dirs", {})
    paths_payload["available_docs"] = validation_result.get("available_docs", [])
    paths_payload["FEATURE_DIR"] = paths_payload.get("feature_dir", "")
    paths_payload["SPEC_FILE"] = paths_payload.get("spec_file", "")
    paths_payload["PLAN_FILE"] = paths_payload.get("plan_file", "")
    paths_payload["TASKS_FILE"] = paths_payload.get("tasks_file", "")
    paths_payload["FEATURE_SPEC"] = paths_payload.get("spec_file", "")
    paths_payload["IMPL_PLAN"] = paths_payload.get("plan_file", "")
    paths_payload["TASKS"] = paths_payload.get("tasks_file", "")
    feature_dir_value = str(paths_payload.get("feature_dir", ""))
    paths_payload["SPECS_DIR"] = str(Path(feature_dir_value).parent) if feature_dir_value else ""
    return paths_payload


def _emit_check_prerequisites_result(
    *,
    validation_result: dict[str, object],
    feature_dir: Path,
    json_output: bool,
    paths_only: bool,
    target_branch: str,
    current_branch: str,
) -> None:
    """Emit prerequisite-check output in JSON or human form."""
    if json_output:
        payload = _paths_only_payload(validation_result) if paths_only else dict(validation_result)
        _emit_json(
            _inject_branch_contract(
                payload,
                target_branch=target_branch,
                current_branch=current_branch,
            )
        )
        return

    if validation_result["valid"]:
        console.print("[green]✓[/green] Prerequisites check passed")
        console.print(f"   Mission: {feature_dir.name}")
    else:
        console.print("[red]✗[/red] Prerequisites check failed")
        for error in cast(list[str], validation_result["errors"]):
            console.print(f"   • {error}")

    warnings = cast(list[str], validation_result["warnings"])
    for warning in warnings:
        if warning == warnings[0]:
            console.print("\n[yellow]Warnings:[/yellow]")
        console.print(f"   • {warning}")


def _run_resume_probe(
    repo_root: Path,
    feature: str | None,
    *,
    paths_only: bool,
    include_tasks: bool,
    require_tasks: bool,
    json_output: bool,
) -> None:
    """Validate the resume-only options and report the existing resume contract."""
    if not feature or not feature.strip():
        _emit_console_or_json_error(
            json_output=json_output,
            message="--resume-probe requires --mission <provisional-slug>",
        )
        raise typer.Exit(1) from None
    if paths_only or include_tasks or require_tasks:
        _emit_console_or_json_error(
            json_output=json_output,
            message="--resume-probe cannot be combined with task/path validation flags",
        )
        raise typer.Exit(1) from None
    try:
        resume_payload = _build_resume_probe_payload(repo_root, feature.strip())
    except ValueError as exc:
        _emit_console_or_json_error(json_output=json_output, message=str(exc))
        raise typer.Exit(1) from None
    _emit_resume_probe_payload(resume_payload, json_output=json_output)
    if resume_payload["resume_state"] in {"existing", "ambiguous", "malformed"}:
        raise typer.Exit(1)


def _refusal_envelope(code: str, message: str) -> dict[str, object]:
    """The ``error``/``error_code`` payload this command's JSON surface carries, plus the CLI version."""
    enriched: dict[str, object] = _with_cli_version(flat_error_envelope(code, message))
    return enriched


def _refuse_resume_probe_with_owned(owned: OwnedCheckout | None, *, resume_probe: bool) -> None:
    """``--resume-probe`` never opts into an owned checkout: refuse it once ownership is validated."""
    if owned is not None and resume_probe:
        raise ActionContextError(OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED, "--resume-probe is not supported with --owned-checkout.")


def check_prerequisites(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., '020-my-mission')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    paths_only: Annotated[bool, typer.Option("--paths-only", help="Only output path variables")] = False,
    resume_probe: Annotated[
        bool,
        typer.Option(
            "--resume-probe",
            help="Return structured found/not_found/existing/ambiguous/malformed state for safe specify resume",
        ),
    ] = False,
    include_tasks: Annotated[bool, typer.Option("--include-tasks", help="Include tasks.md in validation")] = False,
    require_tasks: Annotated[
        bool,
        typer.Option("--require-tasks", hidden=True, help="Deprecated alias for --include-tasks"),
    ] = False,
    owned_checkout: OwnedCheckoutOption = None,
) -> None:
    """Validate mission structure and prerequisites.

    This command is designed for AI agents to call programmatically.

    Examples:
        spec-kitty agent mission check-prerequisites --json
        spec-kitty agent mission check-prerequisites --mission 020-my-feature --paths-only --json
        spec-kitty agent mission check-prerequisites --mission my-feature --resume-probe --json
    """
    # Deferred import keeps this leaf free of an import cycle while honoring the
    # historical ``mission.<name>`` patch seams (tests patch ``locate_project_root``
    # / ``_enforce_git_preflight`` / ``_primary_anchored_feature_dir`` /
    # ``_find_feature_directory`` / ``validate_feature_structure`` /
    # ``get_current_branch`` on the ``mission`` module).
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        if require_tasks and not include_tasks:
            include_tasks = True
            if not json_output:
                console.print("[yellow]Warning:[/yellow] --require-tasks is deprecated; use --include-tasks.")

        repo_root = _mission.locate_project_root()
        if repo_root is None:
            _emit_console_or_json_error(
                json_output=json_output,
                message=PROJECT_ROOT_NOT_FOUND_MESSAGE,
            )
            raise typer.Exit(1) from None

        # Validate --owned-checkout (or adopt the caller's checkout) exactly once; the
        # raw option value goes straight into the shared helper. A flagless
        # --resume-probe skips adoption so the repository-root probe is unchanged; an
        # explicit flag is refused after validation, so an invalid checkout still
        # reports its ownership code first.
        owned = (
            None
            if resume_probe and owned_checkout is None
            else resolve_owned_or_refuse(
                repo_root,
                owned_checkout,
                feature,
                cwd=Path.cwd(),
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
                json_output=json_output,
                envelope=_refusal_envelope,
            )
        )
        _refuse_resume_probe_with_owned(owned, resume_probe=resume_probe)
        if owned is not None:
            repo_root = owned.owned_root

        if resume_probe:
            _run_resume_probe(
                repo_root,
                feature,
                paths_only=paths_only,
                include_tasks=include_tasks,
                require_tasks=require_tasks,
                json_output=json_output,
            )
            return

        _mission._enforce_git_preflight(
            repo_root,
            json_output=json_output,
            command_name="spec-kitty agent mission check-prerequisites",
        )

        # Determine feature directory (main repo or worktree).
        #
        # #2017-class surface-split fix: the planning-authoring surface this
        # command reports MUST agree with where ``finalize-tasks`` reads its
        # inputs. ``finalize-tasks`` deliberately anchors to the PRIMARY checkout
        # (``primary_feature_dir_for_mission`` — CWD/topology-invariant, the same
        # anchoring ``resolve_placement_only`` uses). The coord-aware read
        # resolver, by contrast, returns the coordination worktree once it is
        # materialized — so an agent authoring tasks at the reported ``feature_dir``
        # would write to coord while finalize reads primary, and finalize parses an
        # empty primary ``tasks/``. Delegate to the SAME primary anchor finalize
        # uses so the two agree by construction; fall back to the coord-aware
        # resolver only when the mission has no primary-surface directory (e.g. a
        # coord-only legacy materialization). The full topology-aware unification
        # of every planning command onto one surface authority is tracked by the
        # single-authority-topology-cleanup mission (#1716 write-surface coherence).
        cwd = Path.cwd().resolve()
        try:
            feature_dir = owned.mission_dir if owned else _mission._primary_anchored_feature_dir(repo_root, feature)
            if feature_dir is None:
                feature_dir = _mission._find_feature_directory(
                    repo_root,
                    cwd,
                    explicit_feature=feature,
                )
        except (ValueError, ActionContextError) as detection_error:
            _emit_check_prerequisites_detection_error(
                repo_root=repo_root,
                detection_error=detection_error,
                feature=feature,
                json_output=json_output,
                paths_only=paths_only,
                include_tasks=include_tasks,
            )
            raise typer.Exit(1) from None

        validation_result = _mission.validate_feature_structure(feature_dir, check_tasks=include_tasks)
        target_branch = _resolve_feature_target_branch(feature_dir, repo_root)
        current_branch = _mission.get_current_branch(repo_root) or target_branch
        _emit_check_prerequisites_result(
            validation_result=validation_result,
            feature_dir=feature_dir,
            json_output=json_output,
            paths_only=paths_only,
            target_branch=target_branch,
            current_branch=current_branch,
        )

    except typer.Exit:
        raise
    except ActionContextError as e:
        # Unified owned-refusal output (#5445): route through the canonical
        # ``emit_owned_refusal`` renderer with this command's own
        # ``_refusal_envelope`` so human mode lands on stderr as
        # ``Error: [<CODE>] <message>`` and ``--json`` mode is indented, matching
        # the ``resolve_owned_or_refuse`` call above. The only code that reaches
        # this generic handler today is ``OWNED_OPTION_UNSUPPORTED`` (raised by
        # ``_refuse_resume_probe_with_owned``), which is registered.
        emit_owned_refusal(e, json_output=json_output, envelope=_refusal_envelope)
    except Exception as e:
        if json_output:
            _emit_json({"error": str(e)})
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
