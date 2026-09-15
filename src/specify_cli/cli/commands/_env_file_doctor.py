"""Env-file health doctor sibling (T019).

Self-registering ``doctor env-file`` subcommand: reports on the two-tier
``.kitty.env`` operator env-file scaffold (contracts/kitty-env-loader.md) --
presence, ignore coverage (C-SEC-2), the ``SPEC_KITTY_HOME``/config.yaml
pointer, and which governed vars are set from which tier. Reuses the
provision migration's governed-var vocabulary
(``m_3_2_8_provision_kitty_env.GOVERNED_OPERATOR_VARS`` /
``GOVERNED_SECRET_VARS``) so "doctor reports" and "provision seeds" never
drift apart, and the fail-closed allowlist
(``core.secret_redaction.redact``) so a governed var's VALUE is only ever
rendered when it is on the printable allowlist (C-SEC-1) -- names/presence
only otherwise.

**Auto-discovery seam (T015/T019).** Mirrors ``_provenance_doctor.py``: this
module never requires an edit to ``doctor.py`` -- ``doctor.py``'s
``_auto_discover_doctor_siblings`` loop imports every ``cli/commands/_*_doctor.py``
module and calls ``register(app)`` when the module exposes one.

Import discipline (mirrors ``_provenance_doctor.py``): shared console/output
infra comes from ``._doctor_shared``; this module never imports ``doctor.py``
itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated

import typer

from kernel.env_expand import expand_env_template
from kernel.paths import get_runtime_state_root
from specify_cli.core.paths import locate_project_root
from specify_cli.core.secret_redaction import redact
from specify_cli.upgrade.migrations.m_3_2_8_provision_kitty_env import (
    GOVERNED_OPERATOR_VARS,
    GOVERNED_SECRET_VARS,
)

from ._doctor_shared import _emit_not_in_project, console

__all__ = ["register", "run_env_file_health"]

_KITTIFY_DIRNAME = ".kittify"
_ENV_FILENAME = ".kitty.env"
_CONFIG_YAML_FILENAME = "config.yaml"
_GITIGNORE_FILENAME = ".gitignore"
_CLAUDEIGNORE_FILENAME = ".claudeignore"
_ENV_FILE_IGNORE_ENTRY = ".kittify/.kitty.env"
_ENV_FILE_CONFIG_KEY = "env_file"
_ENV_FILE_CONFIG_PREFIX = f"{_ENV_FILE_CONFIG_KEY}:"
# The SPEC_KITTY_HOME locator name is spelled inline (never bound to a module
# constant) per the home-pin census SC-002b inert sub-form: a
# ``NAME = "SPEC_KITTY_HOME"`` binding is forbidden tree-wide
# (isolated-home-pin-guard-r1a). As a fragment of this larger template literal
# it is not an assignment-bound pin.
_DEFAULT_ENV_FILE_TEMPLATE = f"${{SPEC_KITTY_HOME}}/{_ENV_FILENAME}"

#: All governed vars this facet reports tier/presence for -- the union of
#: the provision migration's printable-operator and secret-template
#: vocabularies (kept as one authority, see module docstring).
_ALL_GOVERNED_VARS: tuple[str, ...] = (*GOVERNED_OPERATOR_VARS, *GOVERNED_SECRET_VARS)


@dataclass(frozen=True)
class GovernedVarReport:
    """One governed var's reported tier + redacted value (T019)."""

    name: str
    tier: str
    present: bool
    value: str | None


def _repo_root_kittify(repo_root: Path) -> Path:
    return repo_root / _KITTIFY_DIRNAME


def _repo_env_path(repo_root: Path) -> Path:
    return _repo_root_kittify(repo_root) / _ENV_FILENAME


def _config_env_file_pointer(repo_root: Path) -> str | None:
    """Targeted top-level ``env_file:`` scan -- mirrors the loader's own C-LDR-5
    scan (``bootstrap.env_file._read_config_env_file_pointer``), duplicated
    here (not imported: that helper is private to WP02's module) rather than
    reaching across the WP boundary for a ~10-line targeted scan.
    """
    config_path = _repo_root_kittify(repo_root) / _CONFIG_YAML_FILENAME
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw_line in text.splitlines():
        if not raw_line.startswith(_ENV_FILE_CONFIG_PREFIX):
            continue
        value = raw_line[len(_ENV_FILE_CONFIG_PREFIX) :].strip()
        value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value or None
    return None


def _home_env_path(repo_root: Path) -> tuple[Path, str]:
    """Resolve the home-tier path + a human-readable source label."""
    pointer = _config_env_file_pointer(repo_root)
    source = "config.yaml env_file key" if pointer else "default (${SPEC_KITTY_HOME}/.kitty.env)"
    raw = pointer or _DEFAULT_ENV_FILE_TEMPLATE
    environ = dict(os.environ)
    environ.setdefault("SPEC_KITTY_HOME", str(get_runtime_state_root()))
    expanded = expand_env_template(raw, inject_defaults=True, environ=environ)
    return Path(expanded), source


def _ignore_file_entries(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _is_gitignored(repo_root: Path) -> bool:
    return _ENV_FILE_IGNORE_ENTRY in _ignore_file_entries(repo_root / _GITIGNORE_FILENAME)


def _is_claudeignored(repo_root: Path) -> bool:
    return _ENV_FILE_IGNORE_ENTRY in _ignore_file_entries(repo_root / _CLAUDEIGNORE_FILENAME)


def _tier_for(*, real_env_present: bool, repo_present: bool, home_present: bool) -> str:
    if real_env_present:
        return "real_env"
    if repo_present:
        return "repo"
    if home_present:
        return "home"
    return "unset"


def _read_tier_file(path: Path) -> dict[str, str]:
    """Best-effort ``.kitty.env`` tier read for reporting only (never raises).

    Uses ``bootstrap.env_file.parse_env_file`` (public API) for the grammar,
    so the doctor's parsing agrees with the loader's; a read failure is
    reported as an empty tier rather than raised -- this facet is advisory.
    """
    from specify_cli.bootstrap.env_file import parse_env_file  # noqa: PLC0415 -- lazy (C-002)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_env_file(text)


def _raw_tier_value(var: str, *, real_present: bool, repo_present: bool, repo_values: dict[str, str], home_values: dict[str, str]) -> str | None:
    if real_present:
        return os.environ[var]
    if repo_present:
        return repo_values[var]
    return home_values.get(var)


def _governed_var_reports(repo_values: dict[str, str], home_values: dict[str, str]) -> list[GovernedVarReport]:
    reports: list[GovernedVarReport] = []
    for var in _ALL_GOVERNED_VARS:
        real_present = var in os.environ
        repo_present = var in repo_values
        home_present = var in home_values
        present = real_present or repo_present or home_present
        tier = _tier_for(real_env_present=real_present, repo_present=repo_present, home_present=home_present)
        value = None
        if present:
            raw_value = _raw_tier_value(
                var, real_present=real_present, repo_present=repo_present, repo_values=repo_values, home_values=home_values
            )
            redacted = redact({var: raw_value} if raw_value is not None else {})
            value = redacted[0].value if redacted else None
        reports.append(GovernedVarReport(name=var, tier=tier, present=present, value=value))
    return reports


def run_env_file_health(repo_root: Path, *, json_output: bool) -> None:
    """Entry point for ``doctor env-file``.

    Advisory (matches ``doctor provenance``'s informational shape): exits 1
    when a coverage issue is found (present-but-ungitignored/unclaudeignored)
    so CI can gate on it if desired, but never mutates anything -- fixing is
    a separate, explicit ``spec-kitty migrate`` step.
    """
    repo_env_path = _repo_env_path(repo_root)
    repo_exists = repo_env_path.exists()
    home_env_path, home_source = _home_env_path(repo_root)
    home_exists = home_env_path.exists()

    gitignored = _is_gitignored(repo_root)
    claudeignored = _is_claudeignored(repo_root)

    repo_values = _read_tier_file(repo_env_path) if repo_exists else {}
    home_values = _read_tier_file(home_env_path) if home_exists else {}
    governed = _governed_var_reports(repo_values, home_values)

    issues: list[str] = []
    if repo_exists and not gitignored:
        issues.append(f"{_ENV_FILE_IGNORE_ENTRY} exists but is not covered by .gitignore (C-SEC-2)")
    if repo_exists and not claudeignored:
        issues.append(f"{_ENV_FILE_IGNORE_ENTRY} exists but is not covered by .claudeignore (C-SEC-2)")

    if json_output:
        payload = {
            "repo_env_file": {"path": str(repo_env_path), "exists": repo_exists},
            "home_env_file": {"path": str(home_env_path), "exists": home_exists, "source": home_source},
            "gitignored": gitignored,
            "claudeignored": claudeignored,
            "governed_vars": [asdict(report) for report in governed],
            "issues": issues,
        }
        console.print_json(json.dumps(payload, indent=2))
        raise typer.Exit(1 if issues else 0)

    console.print("\n[bold]Env-file health[/bold]\n")
    repo_status = "[green]exists[/green]" if repo_exists else "[dim]not provisioned[/dim]"
    console.print(f"  Repo tier   ({repo_env_path}): {repo_status}")
    if repo_exists:
        gi_status = "[green]yes[/green]" if gitignored else "[red]no[/red]"
        ci_status = "[green]yes[/green]" if claudeignored else "[red]no[/red]"
        console.print(f"    gitignored: {gi_status}    claudeignored: {ci_status}")
    console.print(
        f"  Home tier   ({home_env_path}): "
        f"{'[green]exists[/green]' if home_exists else '[dim]not provisioned[/dim]'} "
        f"[dim]({home_source})[/dim]"
    )

    console.print("\n  Governed vars:")
    for report in governed:
        if not report.present:
            console.print(f"    [dim]{report.name}: unset[/dim]")
        elif report.value is not None:
            console.print(f"    {report.name} [{report.tier}]: {report.value}")
        else:
            console.print(f"    {report.name} [{report.tier}]: [dim]<redacted>[/dim]")

    if issues:
        console.print("\n[bold yellow]Issue(s):[/bold yellow]")
        for issue in issues:
            console.print(f"  • [yellow]{issue}[/yellow]")
        console.print("\n  [dim]Fix with:[/dim] spec-kitty migrate  # applies m_3_2_8_provision_kitty_env\n")
        raise typer.Exit(1)

    console.print()
    raise typer.Exit(0)


def register(app: typer.Typer) -> None:
    """Register the ``env-file`` subcommand onto *app* (doctor.py auto-discovery seam)."""

    @app.command(name="env-file")
    def env_file(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Machine-readable JSON output"),
        ] = False,
    ) -> None:
        """Report ``.kitty.env`` operator env-file health (presence/tier/ignore).

        Reads the repo- and home-tier ``.kitty.env`` files and the
        config.yaml ``env_file`` pointer, and reports which governed vars
        are set and from which tier -- names/presence only for anything not
        on the printable-var allowlist (C-SEC-1), values never leaked.
        Read-only -- never mutates state.

        Examples:
            spec-kitty doctor env-file
            spec-kitty doctor env-file --json
        """
        try:
            repo_root = locate_project_root()
        except Exception as exc:
            _emit_not_in_project(json_output)
            raise typer.Exit(1) from exc
        if repo_root is None:
            _emit_not_in_project(json_output)
            raise typer.Exit(1)
        run_env_file_health(repo_root, json_output=json_output)
