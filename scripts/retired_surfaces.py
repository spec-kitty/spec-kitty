"""The retired surfaces: one authority for the code gate and the docs gate (#7520).

``tests/architectural/test_no_retired_subsystems.py`` keeps the retired code paths and
CLI commands from coming back into the tree. ``scripts/docs/retired_surface_gate.py`` and
``scripts/docs/staleness_audit.py`` keep the published living pages from naming them.
Both read the lists here, so the two cannot drift.

* :data:`RETIRED_PATHS`: repository paths that must not exist again. Only its ``src/``
  entries are docs surfaces: the ``tests/``, ``scripts/`` and ``.github/workflows/`` entries
  are retired test files, benchmarks and workflows that a living page never documents, so
  matching them would only flag history pages, which the docs gate does not read.
* :data:`RETIRED_CLI_PREFIXES`: ``spec-kitty`` command prefixes that must not exist again.
* :data:`RETIRED_SLASH_COMMANDS`: slash commands Spec Kitty no longer installs.
* :data:`DOC_RETIRED_SURFACES`: retirements a page can still name that the code gate
  checks another way (a package moved rather than deleted, a renamed command, a retired
  CI producer, the hosted product).

:func:`docs_retired_surfaces` merges the three into the docs gate's patterns, and
:func:`surfaces_named` finds them in a page. Standard
library only.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

__all__ = [
    "DOC_RETIRED_SURFACES",
    "RETIRED_CLI_PREFIXES",
    "RETIRED_PATHS",
    "RETIRED_SLASH_COMMANDS",
    "RetiredSurface",
    "docs_retired_surfaces",
    "surfaces_named",
]

# Built from parts so this module never contains the literal retired command names
# that the code gate's prose scan looks for elsewhere.
_HYPHEN: Final[str] = chr(45)
_ORPHAN_DAEMONS: Final[str] = "orphan" + _HYPHEN + "daemons"
_RESTART_DAEMON: Final[str] = "restart" + _HYPHEN + "daemon"

RETIRED_PATHS: Final[tuple[str, ...]] = (
    "src/specify_cli/sync",
    "src/specify_cli/delivery",
    "src/specify_cli/event_journal",
    "src/specify_cli/saas",
    "src/specify_cli/egress.py",
    "src/specify_cli/egress_consent.py",
    "src/specify_cli/cli/commands/sync.py",
    "src/specify_cli/cli/commands/_daemon_doctor.py",
    # Frozen hosted / sync / drain surfaces removed from open-core (#6164).
    "src/specify_cli/saas_client",
    "src/specify_cli/zeitgeist_client",
    "src/specify_cli/auth",
    "src/specify_cli/live_work",
    "src/specify_cli/widen",
    "src/specify_cli/core/hosted_posture.py",
    "src/specify_cli/core/saas_sync_config.py",
    "src/specify_cli/core/toml_table.py",
    "src/specify_cli/status/zeitgeist_bridge.py",
    "src/specify_cli/events/runtime_moments.py",
    "src/specify_cli/readiness/auth.py",
    "src/specify_cli/readiness/render.py",
    "src/specify_cli/tracker/saas_client.py",
    "src/specify_cli/tracker/saas_service.py",
    "src/specify_cli/tracker/saas_readiness.py",
    "src/specify_cli/tracker/feature_flags.py",
    "src/specify_cli/tracker/origin.py",
    "src/specify_cli/tracker/origin_consumer.py",
    "src/specify_cli/tracker/origin_models.py",
    "src/specify_cli/tracker/discovery.py",
    "src/specify_cli/tracker/ticket_context.py",
    "src/specify_cli/cli/commands/auth.py",
    "src/specify_cli/cli/commands/live_work.py",
    "src/specify_cli/cli/commands/moments.py",
    "src/specify_cli/cli/commands/routes.py",
    "src/specify_cli/cli/commands/zeitgeist.py",
    "src/specify_cli/dossier/emitter_adapter.py",
    "src/specify_cli/dossier/drift_detector.py",
    # The whole package: after the D1 publish pipeline was retired only an
    # 8-line docstring tombstone survived (mission dead-port-disposition-01M1TZVN,
    # FR-014). A package-level ban subsumes the former write/attestation rows.
    "src/specify_cli/team_projection",
    "src/specify_cli/core/batch_partition.py",
    "src/specify_cli/migration/envelope_seam.py",
    "src/specify_cli/cli/commands/agent/setup_plan_hosted.py",
    "src/specify_cli/cli/commands/agent/setup_plan_hosted_effects.py",
    # The bundled local dashboard (``spec-kitty dashboard``) and its generator
    # skill were removed in #5530; the retiring migration
    # (``m_4_0_0rc5_retire_bundled_dashboard.py``) and the ``skills/retired.py``
    # registry entry for it are the sanctioned survivors and stay off this list.
    "src/specify_cli/dashboard",
    "src/specify_cli/cli/commands/dashboard.py",
    "src/specify_cli/charter_runtime/preflight/dashboard_warning.py",
    "src/charter/offering/skills/spk-admin-dashboard",
    "tests/test_dashboard",
    "tests/dashboard",
    "tests/specify_cli/dashboard",
    "tests/cross_cutting/dashboard",
    "tests/ui/test_dashboard_wp_modal.py",
    "tests/cli_gate/test_dashboard_modes.py",
    "tests/status/test_dashboard_status_parity.py",
    "tests/integration/test_dashboard_counters.py",
    "tests/regressions/test_issue_71_dashboard_empty.py",
    "tests/architectural/test_no_process_name_wide_dashboard_kill.py",
    "tests/sync",
    "tests/delivery",
    "tests/event_journal",
    "tests/saas",
    "tests/deactivation",
    "tests/specify_cli/sync",
    "tests/_real_port_suites.py",
    "tests/support/sync_transport_barriers.py",
    "tests/_support/consented_batches.py",
    "tests/agent/cli/commands/test_sync.py",
    "tests/architectural/test_sync_deactivate_census.py",
    "tests/architectural/test_sync_env_census.py",
    "tests/architectural/test_sync_no_early_bind.py",
    "tests/architectural/test_sync_two_authority.py",
    "tests/architectural/test_sync_writer_census.py",
    "tests/architectural/test_status_sync_boundary.py",
    "tests/architectural/test_dossier_sync_boundary.py",
    "tests/architectural/test_project_store_boundary.py",
    "tests/architectural/test_unfiltered_journal_read_boundary.py",
    "scripts/benchmarks/bench_project_discovery.py",
    "scripts/benchmarks/bench_queue_enqueue.py",
    "scripts/mutants/nonterminating_dispatch_3115.py",
    ".github/workflows/drift-detector.yml",
    ".github/workflows/project-sync-consent-evidence.yml",
)

RETIRED_CLI_PREFIXES: Final[tuple[tuple[str, ...], ...]] = (
    ("sync",),
    ("doctor", _ORPHAN_DAEMONS),
    ("doctor", _RESTART_DAEMON),
    ("team-projection",),
    # The local bundled ``spec-kitty dashboard`` command (#5530) — not the
    # hosted Team Kitty SaaS dashboard, which is a web surface, never a CLI
    # command, so it cannot collide with this prefix.
    ("dashboard",),
)


#: How the docs gate words the retirement of a code path or command from the lists above.
_CODE_RETIREMENT: Final[str] = "removed from the code tree; no replacement (tests/architectural/test_no_retired_subsystems.py)"
_SOURCE_PREFIX: Final[str] = "src/"
_PY_SUFFIX: Final[str] = ".py"
_CLI: Final[str] = "spec-kitty"


@dataclass(frozen=True)
class RetiredSurface:
    """A retired surface a page must not newly name: its id, its pattern and what retired it."""

    id: str
    pattern: re.Pattern[str]
    retired_by: str

    def __post_init__(self) -> None:
        if not self.retired_by.strip():
            raise ValueError(f"retired surface {self.id!r} must say what retired it (retired_by)")


def _surface(surface_id: str, pattern: str, retired_by: str, flags: int = 0) -> RetiredSurface:
    return RetiredSurface(id=surface_id, pattern=re.compile(pattern, flags), retired_by=retired_by)


def _command_pattern(words: tuple[str, ...]) -> str:
    """``spec-kitty <words>`` as a whole command: never a prefix of a longer live one (``merge-driver-*``)."""
    return r"(?<![\w-])" + re.escape(" ".join((_CLI, *words))) + r"(?![\w-])"


#: Slash commands Spec Kitty once installed as ``spec-kitty.<cmd>.md`` and installs no more,
#: with what replaced each. Source of truth: ``HISTORICAL_COMMANDS`` in
#: ``src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py`` minus
#: ``CANONICAL_COMMANDS`` in ``src/specify_cli/skills/command_installer.py``; a test pins the
#: two equal (``tests/docs/test_retired_surface_gate.py``).
RETIRED_SLASH_COMMANDS: Final[Mapping[str, str]] = {
    "checklist": "removed (m_2_1_4_enforce_command_file_state); no replacement",
    "clarify": "removed (m_2_0_11_remove_clarify_command); no replacement",
    "constitution": "renamed to /spec-kitty.charter (m_3_1_1_charter_rename)",
    "dashboard": "#5530: the bundled dashboard was removed; no replacement",
    "merge": "#3080: renamed to /spec-kitty.consolidate",
    "profile-context": "removed (m_3_2_0rc43_retire_profile_context_command); no replacement",
}


def _slash_pattern(command: str) -> str:
    """``/spec-kitty.<command>`` or its command file ``spec-kitty.<command>.md``; never a prefix of a live name."""
    return r"(?<![\w.-])/?spec-kitty\." + re.escape(command) + r"(?:\.(?:md|toml))?(?![\w-])"


#: Retirements a page can name that :data:`RETIRED_PATHS` and :data:`RETIRED_CLI_PREFIXES` do not cover.
DOC_RETIRED_SURFACES: Final[tuple[RetiredSurface, ...]] = (
    _surface("src/doctrine", r"(?<![\w./-])src/doctrine(?![\w-])", "#3881: moved to src/charter/offering/"),
    _surface("src/specify_cli/glossary", r"(?<![\w-])specify_cli[/.]glossary(?![\w-])", "moved to src/glossary/"),
    _surface("spec-kitty merge", _command_pattern(("merge",)), "#3080: renamed to spec-kitty consolidate"),
    # Identifiers only: the runner label and the removed client modules. Prose that explains a retirement
    # (the Blacksmith producer, the Zeitgeist relay) is the retirement notice, not a stale instruction.
    _surface(
        "Blacksmith",
        r"(?<![\w-])blacksmith-\d[\w-]*|\buseblacksmith\b|\bruns-on:\s*blacksmith\b",
        "#3995: the CI producer, replaced by the modular GitHub CI",
    ),
    _surface("Zeitgeist", r"(?<![\w-])zeitgeist_(?:client|bridge)(?![\w-])", "#6164: hosted surfaces removed from open-core"),
    _surface("saas_client", r"(?<![\w-])saas_client(?![\w-])", "#6164: hosted surfaces removed from open-core"),
    *(
        _surface(f"{_CLI} {command}", _command_pattern((command,)), "#6164: hosted surfaces removed from open-core")
        for command in ("auth", "issue-search", "live-work", "moments", "routes", "zeitgeist")
    ),
    *(_surface(f"/spec-kitty.{command}", _slash_pattern(command), note) for command, note in sorted(RETIRED_SLASH_COMMANDS.items())),
)


def _path_surface(path: str) -> RetiredSurface:
    """A retired source path, named with or without ``src/``, as a path or a dotted module."""
    module = path.removeprefix(_SOURCE_PREFIX).removesuffix(_PY_SUFFIX)
    slashed = re.escape(module) + (re.escape(_PY_SUFFIX) + "?" if path.endswith(_PY_SUFFIX) else "")
    dotted = re.escape(module.replace("/", "."))
    return _surface(path, rf"(?<![\w-])(?:{slashed}|{dotted})(?![\w-])", _CODE_RETIREMENT)


@functools.cache
def docs_retired_surfaces() -> tuple[RetiredSurface, ...]:
    """Every retired surface the docs gate looks for, in a stable order."""
    paths = tuple(_path_surface(path) for path in RETIRED_PATHS if path.startswith(_SOURCE_PREFIX))
    commands = tuple(_surface(" ".join((_CLI, *prefix)), _command_pattern(prefix), _CODE_RETIREMENT) for prefix in RETIRED_CLI_PREFIXES)
    return (*paths, *commands, *DOC_RETIRED_SURFACES)


def surfaces_named(text: str) -> dict[str, list[int]]:
    """The retired surfaces *text* names, each with the 1-based lines that name it."""
    surfaces = docs_retired_surfaces()
    hits: dict[str, list[int]] = {}
    for number, line in enumerate(text.splitlines(), 1):
        for surface in surfaces:
            if surface.pattern.search(line):
                hits.setdefault(surface.id, []).append(number)
    return hits
