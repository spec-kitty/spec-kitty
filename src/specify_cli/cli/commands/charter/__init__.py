"""Per-subcommand modules for the ``spec-kitty charter`` typer app.

Behaviour-preserving split of the legacy single-file ``charter.py`` (MS-1 from
the post-mission-122 architectural review / WP06 of mission
``test-stabilization-and-debt-pass-01KSF9HJ``). The legacy file lived at
``src/specify_cli/cli/commands/charter.py``; this package replaces it. Python's
package-import resolution prefers the directory over the sibling ``.py`` file
when both exist, but the legacy module has been deleted to avoid drift.

All previously-exported names are re-exported here so existing imports such as
``from specify_cli.cli.commands.charter import app`` (or any of the underscore
helpers tests reach for) keep working.
"""
from __future__ import annotations

# Re-export ``find_repo_root`` and ``_dm_service`` at the package level so
# legacy ``patch("specify_cli.cli.commands.charter.find_repo_root", ...)`` test
# fixtures keep working. The submodules look up these names on the package at
# call time (see e.g. ``synthesize._charter_pkg.find_repo_root()``); patches
# therefore propagate correctly across the WP06 split.
from charter.activation.sync import ensure_charter_bundle_fresh  # noqa: F401
from specify_cli.decisions import service as _dm_service  # noqa: F401
from specify_cli.task_utils import find_repo_root  # noqa: F401

# Charter typer app + bundle subapp wiring + shared module-level state.
from specify_cli.cli.commands.charter._app import (  # noqa: F401
    METADATA_FILENAME,
    app,
    charter_app,
    console,
    logger,
)

# Common helpers (paths, parsing, charter-md resolution, bundle compatibility).
from specify_cli.cli.commands.charter._common import (  # noqa: F401
    _assert_bundle_compatible,
    _display_path,
    _interview_path,
    _parse_csv_option,
    _resolve_actor,
    _resolve_charter_path,
    default_interview,
)

# Subcommand handlers (importing each module registers the handler with the
# typer app via its ``@charter_app.command(...)`` decorator). The names below
# are also re-exported under their legacy spellings for downstream consumers.
from specify_cli.cli.commands.charter.interview import interview  # noqa: F401
from specify_cli.cli.commands.charter.generate import (  # noqa: F401
    _build_doctrine_service_with_org_layer,
    _ensure_gitignore_entries,
    _is_inside_git_worktree,
    _stage_charter_files,
    generate,
)
from specify_cli.cli.commands.charter.context import context  # noqa: F401
from specify_cli.cli.commands.charter.sync import sync  # noqa: F401
from specify_cli.cli.commands.charter.status import status  # noqa: F401
from specify_cli.cli.commands.charter.synthesize import charter_synthesize  # noqa: F401
from specify_cli.cli.commands.charter.resynthesize import charter_resynthesize  # noqa: F401
from specify_cli.cli.commands.charter.lint import charter_lint  # noqa: F401

# Status-collection helpers (legacy test fixtures reach for them by name).
from specify_cli.cli.commands.charter._status_collectors import (  # noqa: F401
    _collect_charter_sync_status,
    _collect_generated_input_status,
    _collect_governance_reference_status,
    _collect_manifest_status,
    _collect_org_layer_status,
    _collect_provenance_status,
    _collect_synthesis_status,
    _summarize_evidence,
)

# Synthesis helpers (used by the legacy public synthesis tests).
from specify_cli.cli.commands.charter._synthesis import (  # noqa: F401
    _MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE,
    _build_synthesis_request,
    _build_synthesis_validation_callback,
    _collect_evidence_result,
    _extract_artifact_id_from_provenance,
    _has_generated_artifacts,
    _list_resynthesis_topics,
    _load_written_artifacts_from_manifest,
    _materialize_fresh_doctrine,
    _planned_fresh_doctrine_deletes,
    _planned_fresh_doctrine_paths,
    _provenance_to_planned_artifacts,
    _read_written_artifacts_from_manifest,
    _run_synthesis_dry_run,
    _run_synthesis_dry_run_with_artifacts,
    _staged_to_planned_artifacts,
)

# Widen-mode helpers (importable by tests, by sibling modules, and from the
# external ``missions/plan/*`` callers that historically did
# ``from specify_cli.cli.commands.charter import _run_blocked_prompt_loop``).
from specify_cli.cli.commands.charter._widen import (  # noqa: F401
    _WIDEN_PREREQS_ABSENT_CACHE,
    _defer_from_blocked_prompt,
    _dispatch_widen_input,
    _fetch_and_review_from_blocked,
    _get_mission_id,
    _get_widen_prereqs_absent,
    _is_already_widened,
    _prompt_one_question,
    _render_waiting_panel,
    _resolve_dm_terminal,
    _resolve_locally,
    _run_blocked_prompt_loop,
    _schedule_inactivity_reminder,
)

# Activate command's full-synthesize seam. Re-exported at the package level so
# ``run_full_synthesize`` (a live public symbol -- the activate/deactivate
# ``--resynthesize`` full generate+synthesize pipeline, invoked in-module via
# ``recompile_or_notify``) has a cross-module consumer, matching how the rest
# of the charter command surface is re-exported here for downstream imports.
from specify_cli.cli.commands.charter.activate import run_full_synthesize  # noqa: F401

# Linter banner helper (kept here for symmetry; tests do not reach for it
# directly today but it is part of the legacy public surface).
from specify_cli.cli.commands.charter.lint import _print_charter_lint_banner  # noqa: F401

# Register ``charter preflight`` (WP03 FR-006..FR-008) — the implementation
# lives in its own package (``specify_cli.charter_runtime.preflight``); we plug
# the handler into the typer app here so the subcommand appears alongside the
# rest of the ``charter`` surface.
from specify_cli.charter_runtime.preflight.cli import charter_preflight as _charter_preflight  # noqa: E402

charter_app.command("preflight")(_charter_preflight)

# WP14 (FR-016): ``charter mission-type`` sub-group — re-export for downstream
# imports and test fixtures.
from specify_cli.cli.commands.charter.mission_type import (  # noqa: E402, F401
    charter_mission_type_app,
    charter_mission_type_list,
)

__all__ = [
    # WP14 mission-type sub-group
    "charter_mission_type_app",
    "charter_mission_type_list",
    # Test-patch surface (legacy ``patch("…charter.X", …)`` consumers)
    "find_repo_root",
    "_dm_service",
    # Typer app + module-level state
    "app",
    "charter_app",
    "console",
    "logger",
    "METADATA_FILENAME",
    # Common helpers
    "default_interview",
    "_resolve_charter_path",
    "_resolve_actor",
    "_parse_csv_option",
    "_interview_path",
    "_display_path",
    "_assert_bundle_compatible",
    # Subcommand handlers
    "interview",
    "generate",
    "context",
    "sync",
    "status",
    "charter_synthesize",
    "charter_resynthesize",
    "charter_lint",
    # Generate helpers
    "_build_doctrine_service_with_org_layer",
    "_is_inside_git_worktree",
    "_stage_charter_files",
    "_ensure_gitignore_entries",
    # Status collectors
    "_collect_charter_sync_status",
    "_collect_generated_input_status",
    "_collect_governance_reference_status",
    "_collect_manifest_status",
    "_collect_provenance_status",
    "_summarize_evidence",
    "_collect_synthesis_status",
    "_collect_org_layer_status",
    # Synthesis helpers
    "_build_synthesis_request",
    "_collect_evidence_result",
    "_build_synthesis_validation_callback",
    "_read_written_artifacts_from_manifest",
    "_provenance_to_planned_artifacts",
    "_staged_to_planned_artifacts",
    "_run_synthesis_dry_run",
    "_run_synthesis_dry_run_with_artifacts",
    "_load_written_artifacts_from_manifest",
    "_extract_artifact_id_from_provenance",
    "_list_resynthesis_topics",
    "_has_generated_artifacts",
    "_materialize_fresh_doctrine",
    "_planned_fresh_doctrine_paths",
    "_MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE",
    # Widen helpers
    "_get_widen_prereqs_absent",
    "_get_mission_id",
    "_is_already_widened",
    "_schedule_inactivity_reminder",
    "_render_waiting_panel",
    "_resolve_locally",
    "_defer_from_blocked_prompt",
    "_fetch_and_review_from_blocked",
    "_resolve_dm_terminal",
    "_prompt_one_question",
    "_dispatch_widen_input",
    "_run_blocked_prompt_loop",
    "_WIDEN_PREREQS_ABSENT_CACHE",
    # Lint helper
    "_print_charter_lint_banner",
    # Activate full-synthesize seam
    "run_full_synthesize",
]
