"""Drift gate for subsystems retired by the convergence programme.

The gate is intentionally broader than a raw text search: paths, imports, the
live CLI surface, packaging configuration, and shipped prose each need a
different detector. Every helper accepts a root so its negative test can plant
a synthetic violation in a temporary fixture without mutating the checkout.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from scripts.docs._typer_walker import walk
from tests.architectural.test_docs_cli_reference_parity import _build_live_app

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]

_RETIRED_PATHS = (
    "src/specify_cli/sync",
    "src/specify_cli/delivery",
    "src/specify_cli/event_journal",
    "src/specify_cli/saas",
    "src/specify_cli/egress.py",
    "src/specify_cli/egress_consent.py",
    "src/specify_cli/cli/commands/sync.py",
    "src/specify_cli/cli/commands/_daemon_doctor.py",
    "src/specify_cli/saas_client/admission.py",
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
_RETIRED_PATH_GLOBS = (
    "tests/cli/commands/test_sync_*.py",
    "tests/architectural/census/sync_deactivate_*.txt",
)

_AST_SCAN_ROOTS = ("src", "tests", "scripts", "packs")
_DOTTED = chr(46)
_HYPHEN = chr(45)
_SPECIFY_CLI = "specify_cli" + _DOTTED
_ORPHAN_DAEMONS = "orphan" + _HYPHEN + "daemons"
_RESTART_DAEMON = "restart" + _HYPHEN + "daemon"
_SYNC_DAEMON = "sync" + _HYPHEN + "daemon"
_PROJECT_SYNC_STORE = "Project" + "SyncStore"
_DELIVERY_RECEIVER = "Delivery" + "Receiver"
_READONLY_IDENTITY = "SPEC_KITTY_SYNC_" + "READONLY_IDENTITY"
_STRICT_ADMISSION = "SPEC_KITTY_SYNC_" + "STRICT_ADMISSION"
_NO_AUTO_CUTOVER = "SPEC_KITTY_" + "NO_AUTO_CUTOVER"
_RETIRED_SYNC_DOCTOR = " ".join(("spec-kitty", "sync", "doctor"))
_BANNED_IMPORT_PREFIXES = (
    _SPECIFY_CLI + "sync",
    _SPECIFY_CLI + "delivery",
    _SPECIFY_CLI + "event_journal",
    _SPECIFY_CLI + "saas",
    _SPECIFY_CLI + "egress",
    _SPECIFY_CLI + "egress_consent",
    _SPECIFY_CLI + "cli.commands.sync",
    _SPECIFY_CLI + "cli.commands._daemon_doctor",
    _SPECIFY_CLI + "dossier.emitter_adapter",
    _SPECIFY_CLI + "dossier.drift_detector",
    _SPECIFY_CLI + "team_projection",
    _SPECIFY_CLI + "core.batch_partition",
    _SPECIFY_CLI + "migration.envelope_seam",
    "websockets",
    # Mission dead-port-disposition-01M1TZVN (FR-004): the mission-DSL v1 runtime and
    # its state-machine library are retired everywhere, not only on the mission_v1
    # import path pinned by tests/specify_cli/mission_v1/test_import_hygiene.py.
    "transitions",
    _SPECIFY_CLI + "mission_v1.compat",
    _SPECIFY_CLI + "mission_v1.runner",
    _SPECIFY_CLI + "mission_v1.guards",
    _SPECIFY_CLI + "mission_v1.schema",
)

_MANIFEST_PATH = _REPO_ROOT / "src/specify_cli/_completion_manifest.json"
_RUFF_PATH = _REPO_ROOT / "ruff.toml"
_RETIRED_CLI_PREFIXES = (
    ("sync",),
    ("doctor", _ORPHAN_DAEMONS),
    ("doctor", _RESTART_DAEMON),
    ("team-projection",),
)
_REQUIRED_CLI_PATHS = {
    ("tracker", "sync", "publish"),
    ("charter", "sync"),
    ("agent", "config", "sync"),
}
_DOCTOR_FAST_PATH_RE = re.compile(rf'\[\s*"doctor"\s*,\s*"{_RESTART_DAEMON}"\s*\]')
_DOCTOR_FAST_PATH_FUNCTION = "_is_doctor_restart_daemon_fast_path"
_DOCTOR_FAST_PATH_MARKER = f"doctor {_RESTART_DAEMON} fast path"

_RETIRED_SYNC_SUBCOMMANDS = (
    "archive",
    "diagnose",
    "doctor",
    "gc",
    "import-history",
    "migrate",
    "mode",
    "now",
    "opt-in",
    "opt-out",
    "project_store_history",
    "project_store_migrate",
    "project_store_preview",
    "project_store_quarantine",
    "project_store_status",
    "purge",
    "routes",
    "server",
    "share",
    "status",
    "unshare",
    "workspace",
)
_SHIPPED_SURFACE_ROOTS = (
    "src/charter",
    "src/doctrine",
    "packs",
    "src/specify_cli/templates",
    "src/specify_cli/missions",
    "docs/api",
    "README.md",
)
_HISTORICAL_PREFIXES = (
    ("kitty-specs",),
    ("docs", "adr"),
    ("docs", "changelog"),
    ("docs", "plans"),
    ("docs", "operations"),
    ("docs", "guides"),
)
_HISTORICAL_FILES = ("AGENTS.md", "state/contract.py")
_RETIRED_SURFACE_RE = re.compile(
    rf"(?<![\w]){re.escape(_READONLY_IDENTITY)}(?![\w])"
    rf"|(?<![\w]){re.escape(_STRICT_ADMISSION)}(?![\w])"
    rf"|(?<![\w]){re.escape(_NO_AUTO_CUTOVER)}(?![\w])"
    r"|(?<![\w])SPEC_KITTY_DIR(?![\w])"
    rf"|(?<![\w-])spec-kitty sync (?:{'|'.join(map(re.escape, _RETIRED_SYNC_SUBCOMMANDS))})(?![\w-])"
    rf"|(?<![\w]){re.escape(_ORPHAN_DAEMONS)}(?![\w])"
    rf"|(?<![\w]){re.escape(_RESTART_DAEMON)}(?![\w])"
    rf"|(?<![\w]){re.escape(_SYNC_DAEMON)}(?![\w])"
    rf"|(?<![\w]){re.escape(_PROJECT_SYNC_STORE)}(?![\w])"
    rf"|(?<![\w]){re.escape(_DELIVERY_RECEIVER)}(?![\w])"
    r"|(?<![\w])event_journal(?![\w])"
)

# Mission dead-port-disposition-01M1TZVN retired the mission-DSL v1 runtime and
# deleted the ``states:``/``transitions:`` blocks from every shipped
# ``mission.yaml``; its DRIFT-1 follow-up (#3961) stripped the remaining
# compat-ignored blocks (``mission:``/``initial:``/``guards:``/``inputs:``/
# ``outputs:``) from the shipped catalogs, so the ratchet now covers the whole
# retired key set. Unlike ``_RETIRED_SURFACE_RE`` above (arbitrary prose,
# anywhere in a matched surface file), these keys are only ever *top-level*
# YAML mapping keys re-appearing in a ``mission.yaml`` — so the detector is
# scoped to that filename and anchored to column 0, and it does not fire on
# the words appearing in prose or nested/indented YAML. Third-party packs and
# project ``.kittify/overrides`` mission.yaml files are intentionally out of
# scope: MISSION_COMPAT_IGNORED_FIELDS tolerates the keys there by design
# (src/specify_cli/mission.py); this gate governs only our shipped surface.
_MISSION_DSL_V1_KEY_RE = re.compile(r"^(mission|initial|states|transitions|guards|inputs|outputs):")


def _retired_path_violations(root: Path) -> list[str]:
    violations = {path for path in _RETIRED_PATHS if (root / path).exists()}
    for pattern in _RETIRED_PATH_GLOBS:
        violations.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
    return sorted(violations)


def _has_banned_prefix(target: str) -> bool:
    target_segments = target.split(".")
    return any(target_segments[: len(prefix.split("."))] == prefix.split(".") for prefix in _BANNED_IMPORT_PREFIXES)


def _call_string_target(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    function = node.func
    name = ""
    if isinstance(function, ast.Attribute):
        name = function.attr
    elif isinstance(function, ast.Name):
        name = function.id
    if name not in {"import_module", "setattr", "patch"}:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return None


def _absolute_import_from_targets(node: ast.ImportFrom, aliases: list[ast.alias]) -> list[str]:
    if node.level or not node.module:
        return []
    targets = [node.module]
    targets.extend(f"{node.module}.{alias.name}" for alias in aliases if alias.name != "*")
    return targets


def _relative_import_from_targets(
    node: ast.ImportFrom,
    aliases: list[ast.alias],
    module_parts: tuple[str, ...],
) -> list[str]:
    if not node.level:
        return []
    package = module_parts[:-1]
    base = package[: max(len(package) - (node.level - 1), 0)]
    if node.module:
        base = (*base, *node.module.split("."))
    targets = [".".join(base)]
    targets.extend(".".join((*base, alias.name)) for alias in aliases if alias.name != "*")
    return targets


def _retired_import_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for scan_root_name in _AST_SCAN_ROOTS:
        scan_root = root / scan_root_name
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            module_parts = path.relative_to(scan_root).with_suffix("").parts
            targets: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    targets.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    targets.extend(_absolute_import_from_targets(node, node.names))
                    targets.extend(_relative_import_from_targets(node, node.names, module_parts))
                else:
                    string_target = _call_string_target(node)
                    if string_target is not None:
                        targets.append(string_target)
            for target in targets:
                if _has_banned_prefix(target):
                    violations.append(f"{path.relative_to(root).as_posix()}: {target}")
    return sorted(set(violations))


def _manifest_command_paths(node: dict[str, Any], prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for name, child in node.get("commands", {}).items():
        path = (*prefix, name)
        paths.add(path)
        paths.update(_manifest_command_paths(child, path))
    return paths


def _has_retired_cli_prefix(paths: set[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return sorted(path for path in paths if any(path[: len(prefix)] == prefix for prefix in _RETIRED_CLI_PREFIXES))


def _cli_surface_violations(app_paths: set[tuple[str, ...]], manifest_path: Path, root: Path) -> list[str]:
    violations = [f"live CLI path: {' '.join(path)}" for path in _has_retired_cli_prefix(app_paths)]
    missing_controls = _REQUIRED_CLI_PATHS - app_paths
    violations.extend(f"missing negative-control CLI path: {' '.join(path)}" for path in sorted(missing_controls))

    manifest_paths = _manifest_command_paths(json.loads(manifest_path.read_text(encoding="utf-8")))
    violations.extend(f"completion manifest path: {' '.join(path)}" for path in _has_retired_cli_prefix(manifest_paths))

    init_path = root / "src/specify_cli/__init__.py"
    commands_init_path = root / "src/specify_cli/cli/commands/__init__.py"
    if _DOCTOR_FAST_PATH_RE.search(init_path.read_text(encoding="utf-8")):
        violations.append(f"src/specify_cli/__init__.py: {_DOCTOR_FAST_PATH_MARKER}")
    if _DOCTOR_FAST_PATH_FUNCTION in commands_init_path.read_text(encoding="utf-8"):
        violations.append(f"src/specify_cli/cli/commands/__init__.py: {_DOCTOR_FAST_PATH_MARKER} helper")
    return sorted(violations)


def _is_historical_surface(relative_path: Path) -> bool:
    posix_path = relative_path.as_posix()
    if posix_path in _HISTORICAL_FILES:
        return True
    return any(relative_path.parts[: len(prefix)] == prefix for prefix in _HISTORICAL_PREFIXES)


def _retired_surface_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for surface in _SHIPPED_SURFACE_ROOTS:
        path = root / surface
        files = [path] if path.is_file() else sorted(path.rglob("*")) if path.exists() else []
        for file_path in files:
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(root)
            if _is_historical_surface(relative_path):
                continue
            for line_number, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                violations.extend(f"{relative_path.as_posix()}:{line_number}: {match.group(0)}" for match in _RETIRED_SURFACE_RE.finditer(line))
    return sorted(violations)


def _mission_dsl_v1_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for surface in _SHIPPED_SURFACE_ROOTS:
        path = root / surface
        if path.is_file():
            candidates = [path] if path.name == "mission.yaml" else []
        elif path.exists():
            candidates = sorted(path.rglob("mission.yaml"))
        else:
            candidates = []
        for file_path in candidates:
            relative_path = file_path.relative_to(root)
            if _is_historical_surface(relative_path):
                continue
            for line_number, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                match = _MISSION_DSL_V1_KEY_RE.match(line)
                if match:
                    violations.append(f"{relative_path.as_posix()}:{line_number}: {match.group(0)}")
    return sorted(violations)


def _retired_ruff_ignore_violations(path: Path) -> list[str]:
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    lint = config.get("lint", {})
    per_file_ignores = {
        **lint.get("per-file-ignores", {}),
        **lint.get("extend-per-file-ignores", {}),
    }
    return sorted(
        f"retired Ruff per-file ignore: {pattern}"
        for pattern in per_file_ignores
        if any(pattern == retired_path or pattern.startswith(f"{retired_path}/") for retired_path in _RETIRED_PATHS)
    )


def test_no_retired_paths_exist() -> None:
    assert _retired_path_violations(_REPO_ROOT) == []


def test_retired_path_guard_rejects_planted_fixture(tmp_path: Path) -> None:
    (tmp_path / "src/specify_cli/sync").mkdir(parents=True)
    (tmp_path / "src/specify_cli/saas_client").mkdir(parents=True)
    (tmp_path / "src/specify_cli/saas_client/client.py").write_text("", encoding="utf-8")
    (tmp_path / "tests/cli/commands").mkdir(parents=True)
    (tmp_path / "tests/cli/commands/test_sync_status.py").write_text("", encoding="utf-8")
    assert _retired_path_violations(tmp_path) == [
        "src/specify_cli/sync",
        "tests/cli/commands/test_sync_status.py",
    ]


def test_no_retired_import_targets_exist() -> None:
    assert _retired_import_violations(_REPO_ROOT) == []


def test_import_guard_rejects_planted_fixture_and_keeps_saas_client(tmp_path: Path) -> None:
    fixture = tmp_path / "src/specify_cli/cli/commands/planted.py"
    fixture.parent.mkdir(parents=True)
    retired_sync = _SPECIFY_CLI + "sync"
    retired_commands_sync = _SPECIFY_CLI + "cli.commands.sync"
    retired_delivery = _SPECIFY_CLI + "delivery"
    retired_saas = _SPECIFY_CLI + "saas.core"
    retired_egress = _SPECIFY_CLI + "egress.consent"
    fixture.write_text(
        "\n".join(
            [
                f"import {retired_sync}",
                f"import {retired_commands_sync}",
                f"from specify_cli import {retired_delivery.split(_DOTTED, 1)[1]}",
                "from ... import sync",
                f'importlib.import_module("{retired_saas}")',
                f'monkeypatch.setattr("{retired_egress}.consent", None)',
                'patch("websockets.client")',
                "from specify_cli import saas_client",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    violations = _retired_import_violations(tmp_path)
    targets = {violation.split(": ", 1)[1] for violation in violations}
    assert targets == {
        retired_commands_sync,
        retired_delivery,
        retired_egress + ".consent",
        retired_saas,
        retired_sync,
        "websockets.client",
    }


def test_live_cli_and_completion_manifest_have_no_retired_surface() -> None:
    app_paths = {entry.path for entry in walk(_build_live_app())}
    assert _cli_surface_violations(app_paths, _MANIFEST_PATH, _REPO_ROOT) == []


def test_cli_guard_rejects_planted_fixture(tmp_path: Path) -> None:
    (tmp_path / "src/specify_cli/cli/commands").mkdir(parents=True)
    (tmp_path / "src/specify_cli/__init__.py").write_text(f'COMMANDS = ["doctor", "{_RESTART_DAEMON}"]\n', encoding="utf-8")
    (tmp_path / "src/specify_cli/cli/commands/__init__.py").write_text(
        "def _is_doctor_restart_daemon_fast_path():\n    return False\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "_completion_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "commands": {
                    "sync": {"commands": {}},
                    "doctor": {"commands": {_ORPHAN_DAEMONS: {}}},
                    "team-projection": {"commands": {}},
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    planted_paths = {
        ("sync",),
        ("doctor", _ORPHAN_DAEMONS),
        ("team-projection",),
    }
    violations = _cli_surface_violations(planted_paths, manifest_path, tmp_path)
    assert "live CLI path: sync" in violations
    assert f"completion manifest path: doctor {_ORPHAN_DAEMONS}" in violations
    assert f"src/specify_cli/__init__.py: {_DOCTOR_FAST_PATH_MARKER}" in violations
    assert f"src/specify_cli/cli/commands/__init__.py: {_DOCTOR_FAST_PATH_MARKER} helper" in violations
    assert "missing negative-control CLI path: tracker sync publish" in violations


def test_shipped_prose_has_no_retired_surface() -> None:
    assert _retired_surface_violations(_REPO_ROOT) == []


def test_shipped_mission_yaml_has_no_mission_dsl_v1_keys() -> None:
    assert _mission_dsl_v1_violations(_REPO_ROOT) == []


def test_mission_dsl_v1_guard_rejects_planted_blocks_but_ignores_indented_and_prose_uses(
    tmp_path: Path,
) -> None:
    planted_mission = tmp_path / "packs/mission-x"
    planted_mission.mkdir(parents=True)
    (planted_mission / "mission.yaml").write_text(
        "\n".join(
            (
                "mission:",
                "  name: mission-x",
                "",
                "initial: start",
                "",
                "states:",
                "  - name: start",
                "",
                "transitions:",
                "  - trigger: advance",
                "",
                "workflow:",
                "  # indented occurrences of the same words must not fire",
                "  states: nested",
                "  transitions: nested",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    # A non-mission.yaml file using the same words in prose is out of scope.
    other_dir = tmp_path / "packs/mission-x/docs"
    other_dir.mkdir(parents=True)
    (other_dir / "notes.md").write_text("states: and transitions: are retired.\n", encoding="utf-8")
    violations = _mission_dsl_v1_violations(tmp_path)
    assert violations == [
        "packs/mission-x/mission.yaml:1: mission:",
        "packs/mission-x/mission.yaml:4: initial:",
        "packs/mission-x/mission.yaml:6: states:",
        "packs/mission-x/mission.yaml:9: transitions:",
    ]


def test_ruff_has_no_retired_per_file_ignores() -> None:
    assert _retired_ruff_ignore_violations(_RUFF_PATH) == []


def test_ruff_guard_rejects_retired_entries_in_both_tables(tmp_path: Path) -> None:
    ruff_path = tmp_path / "ruff.toml"
    ruff_path.write_text(
        "\n".join(
            (
                "[lint.per-file-ignores]",
                '"src/specify_cli/saas/readiness.py" = ["F401"]',
                "",
                "[lint.extend-per-file-ignores]",
                '"tests/sync/test_daemon.py" = ["F401"]',
                "",
            )
        ),
        encoding="utf-8",
    )
    assert _retired_ruff_ignore_violations(ruff_path) == [
        "retired Ruff per-file ignore: src/specify_cli/saas/readiness.py",
        "retired Ruff per-file ignore: tests/sync/test_daemon.py",
    ]


def test_prose_guard_rejects_planted_fixture_but_allows_sanctioned_tokens(tmp_path: Path) -> None:
    (tmp_path / "src/doctrine").mkdir(parents=True)
    planted_surface = " ".join(
        (
            _READONLY_IDENTITY,
            "SPEC_KITTY_DIR",
            _RETIRED_SYNC_DOCTOR,
            _ORPHAN_DAEMONS,
            _PROJECT_SYNC_STORE,
            _DELIVERY_RECEIVER,
            "event_journal",
        )
    )
    (tmp_path / "src/doctrine/planted.md").write_text(
        f"{planted_surface}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "SPEC_KITTY_SYNC_DISABLE, SPEC_KITTY_SYNC_MINIMAL_IMPORT, SPEC_KITTY_ENABLE_SAAS_SYNC, and [sync].server_url remain allowed.\n",
        encoding="utf-8",
    )
    violations = _retired_surface_violations(tmp_path)
    assert violations == sorted(
        {
            f"src/doctrine/planted.md:1: {_READONLY_IDENTITY}",
            "src/doctrine/planted.md:1: SPEC_KITTY_DIR",
            f"src/doctrine/planted.md:1: {_RETIRED_SYNC_DOCTOR}",
            f"src/doctrine/planted.md:1: {_ORPHAN_DAEMONS}",
            f"src/doctrine/planted.md:1: {_PROJECT_SYNC_STORE}",
            f"src/doctrine/planted.md:1: {_DELIVERY_RECEIVER}",
            "src/doctrine/planted.md:1: event_journal",
        }
    )
